"""A study's wallet, Peněženka (ADR 0028 decision 2, lead-orchestration LO1, migration M4).

The cap is the researcher's act inside the client's wallet ceiling and the study's budget, written
once to the approval ledger; a charge holds one started run's **ceiling**, insert-once, under the
study row's lock, so concurrent charges never exceed the cap (proved on PostgreSQL); an unknown
ceiling is refused, never charged as zero; off, nothing reads or writes a wallet row.
"""

from __future__ import annotations

import importlib.util
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.application.wallet import StudyWallets, WalletDisabled, set_study_status
from aia_core.application.workflows import start_workflow
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.money import RaiseVerdict, WalletVerdict
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.scope import OrganizationRole, ScopeDenied, StudyStatus
from aia_core.domain.wallet import (
    CHARGE_AUTHORITIES,
    CHARGE_DECISION,
    ChargeKind,
    StudyWallet,
    WalletChargeRefused,
    WalletRaiseRefused,
    effective_cap,
)
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.study_wallet_repository import StudyWalletRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    ClientRow,
    StudyRow,
    StudyWalletChargeRow,
    StudyWalletRaiseRow,
    StudyWalletRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository

REPO = Path(__file__).resolve().parents[3]
MIGRATION = (
    REPO / "migrations/versions/20261021_60ccc9ff42cf_the_study_wallet_its_raises_and_charges.py"
)


# --------------------------------------------------------------------------- helpers


def _run(session: Session, scope: Any, key: str) -> str:
    project, _ = ProjectRepository(session, scope).create(
        title=f"Wallet {key}", project_type=ProjectType.RESEARCH, content={"title": key}
    )
    started = start_workflow(
        session,
        scope,
        project_id=project.project_id,
        workflow_type=DEVELOP_SNAPSHOT,
        idempotency_key=key,
    )
    return started.run_id


def _authority(
    session: Session,
    scope: Any,
    run_id: str | None,
    subject: ApprovalSubject = ApprovalSubject.CHAT_START,
    *,
    subject_id: str = "start-1",
    decision: str = CHARGE_DECISION,
) -> int:
    """A ledger row of a start that consults the wallet, naming the run it started. Its writers
    (LO5's chat start, LO3's plan step) do not exist yet, so the test writes the row the way
    they will: the run, the decision ``start``, a plan step's id as its subject."""
    row = ApprovalDecisionRow(
        organization_id=scope.organization_id,
        client_id=scope.client_id,
        study_id=scope.study_id,
        subject_type=subject,
        subject_id=subject_id,
        run_id=run_id,
        approver_user_id=scope.actor_id,
        decision=decision,
    )
    session.add(row)
    session.flush()
    return int(row.decision_id)


def _ceiling(session: Session, scope: Any, value: float | None) -> None:
    client = session.get(ClientRow, scope.client_id)
    assert client is not None
    client.wallet_ceiling_usd = value
    session.flush()


def _wallet(session: Session, scoped: Any, **kwargs: Any) -> StudyWalletRepository:
    return StudyWalletRepository(session, scoped.scope(**kwargs))


# --------------------------------------------------------------------------- the domain


def test_the_effective_cap_is_the_smallest_bound() -> None:
    assert effective_cap(40.0, study_budget_usd=500.0, client_ceiling_usd=None) == 40.0
    assert effective_cap(40.0, study_budget_usd=500.0, client_ceiling_usd=25.0) == 25.0
    assert effective_cap(40.0, study_budget_usd=30.0, client_ceiling_usd=None) == 30.0
    assert effective_cap(40.0, study_budget_usd=0.0, client_ceiling_usd=100.0) == 0.0


def test_remaining_is_by_ceilings_and_never_negative() -> None:
    wallet = StudyWallet(
        wallet_id="WAL-1",
        study_id="STU-1",
        cap_usd=10.0,
        study_budget_usd=500.0,
        client_ceiling_usd=None,
        charged_usd=12.0,
        created_at=datetime.now(UTC),
    )
    assert wallet.remaining_usd == 0.0


def test_a_charge_is_authorised_only_by_a_start_that_consults_the_wallet() -> None:
    # A Lead card's start is judged as the person's typed start (LO5a.2, migration M3b).
    assert {
        ApprovalSubject.CHAT_START,
        ApprovalSubject.PLAN_STEP,
        ApprovalSubject.LEAD_CARD,
    } == CHARGE_AUTHORITIES


def test_the_charge_kinds_are_the_four_plan_steps() -> None:
    assert [k.value for k in ChargeKind] == [
        "research_run",
        "agent_job",
        "deep_research",
        "interpretation_research",
    ]


# --------------------------------------------------------------------------- the cap


def test_no_wallet_until_the_researcher_sets_one(session: Session, scoped: Any) -> None:
    repo = _wallet(session, scoped)
    assert repo.wallet() is None
    assert repo.raises() == [] and repo.charges() == []
    assert repo.quote(1.0) == (WalletVerdict.OUTSIDE, None)


def test_a_raise_inside_the_bounds_is_recorded_once_in_the_ledger(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    wallet = repo.set_cap(40.0)
    assert (wallet.cap_usd, wallet.effective_cap_usd, wallet.remaining_usd) == (40.0, 40.0, 40.0)
    assert wallet.study_budget_usd == 500.0 and wallet.client_ceiling_usd is None

    (raised,) = repo.raises()
    assert (raised.from_cap_usd, raised.to_cap_usd, raised.raised_by) == (0.0, 40.0, scope.actor_id)
    (entry,) = WorkflowRepository(session, scope).ledger([ApprovalSubject.WALLET])
    assert entry.decision_id == raised.approval_decision_id
    assert (entry.subject_id, entry.decision) == (wallet.wallet_id, "set_cap")
    assert '"to_cap_usd": 40.0' in entry.comment

    # The same cap again writes nothing; a change writes one more of each.
    repo.set_cap(40.0)
    assert len(repo.raises()) == 1
    repo.set_cap(60.0)
    assert [r.to_cap_usd for r in repo.raises()] == [40.0, 60.0]
    assert len(WorkflowRepository(session, scope).ledger([ApprovalSubject.WALLET])) == 2
    assert session.scalar(select(func.count()).select_from(StudyWalletRow)) == 1


def test_a_raise_above_the_clients_ceiling_is_refused_naming_who_can_raise_it(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    _ceiling(session, scope, 25.0)
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(25.0)
    with pytest.raises(WalletRaiseRefused) as refused:
        repo.set_cap(25.01)
    assert refused.value.verdict is RaiseVerdict.ABOVE_CLIENT_CEILING
    assert refused.value.bound_usd == 25.0
    assert refused.value.who_can_raise == (OrganizationRole.OWNER, OrganizationRole.ADMIN)
    assert [r.to_cap_usd for r in repo.raises()] == [25.0]


def test_a_raise_above_the_study_budget_is_refused(session: Session, scoped: Any) -> None:
    repo = _wallet(session, scoped)
    with pytest.raises(WalletRaiseRefused) as refused:
        repo.set_cap(500.5)
    assert refused.value.verdict is RaiseVerdict.ABOVE_STUDY_BUDGET
    assert refused.value.who_can_raise == ()
    assert repo.wallet() is None  # nothing opened by a refused raise
    assert session.scalar(select(func.count()).select_from(StudyWalletRow)) == 0


def test_a_lowered_ceiling_or_budget_bounds_the_wallet_at_once(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(100.0)
    _ceiling(session, scope, 30.0)
    wallet = repo.wallet()
    assert wallet is not None
    assert (wallet.cap_usd, wallet.effective_cap_usd, wallet.remaining_usd) == (100.0, 30.0, 30.0)
    study = session.get(StudyRow, scope.study_id)
    assert study is not None
    study.budget_usd = 20.0
    session.flush()
    wallet = repo.wallet()
    assert wallet is not None and wallet.effective_cap_usd == 20.0


def test_the_worker_cannot_set_the_wallet(session: Session, scoped: Any) -> None:
    from dataclasses import replace

    from aia_core.domain.scope import WORKER_PERMISSIONS

    worker = replace(scoped.scope(), permissions=frozenset(WORKER_PERMISSIONS))
    with pytest.raises(ScopeDenied):
        StudyWalletRepository(session, worker).set_cap(10.0)


def test_a_negative_or_non_number_cap_is_refused(session: Session, scoped: Any) -> None:
    repo = _wallet(session, scoped)
    for bad in (-1.0, float("nan")):
        with pytest.raises(ValueError):
            repo.set_cap(bad)


# --------------------------------------------------------------------------- charges


def _started(session: Session, scope: Any, key: str, **authority: Any) -> tuple[str, int]:
    run_id = _run(session, scope, key)
    return run_id, _authority(session, scope, run_id, **authority)


def test_a_charge_holds_the_runs_ceiling_once(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    run_id, decision = _started(session, scope, "a")
    charge = repo.charge(
        run_id=run_id, kind=ChargeKind.DEEP_RESEARCH, ceiling_usd=4.0, approval_decision_id=decision
    )
    assert (charge.kind, charge.ceiling_usd, charge.plan_id, charge.plan_step_id) == (
        ChargeKind.DEEP_RESEARCH,
        4.0,
        None,
        None,
    )
    wallet = repo.wallet()
    assert wallet is not None and (wallet.charged_usd, wallet.remaining_usd) == (4.0, 6.0)

    # A start that finds its run already charged charges nothing again.
    again = repo.charge(
        run_id=run_id, kind=ChargeKind.DEEP_RESEARCH, ceiling_usd=9.0, approval_decision_id=decision
    )
    assert again.charge_id == charge.charge_id and again.ceiling_usd == 4.0
    assert [c.run_id for c in repo.charges()] == [run_id]
    assert repo.quote(6.0) == (WalletVerdict.FITS, 6.0)
    assert repo.quote(6.01) == (WalletVerdict.OUTSIDE, 6.0)


def test_an_exact_fit_is_charged_despite_binary_floats(session: Session, scoped: Any) -> None:
    """USD 0.30 less 0.10 is 0.20 exactly, so a 0.20 start fits it: in binary floats the
    remainder is 0.19999999999999998 and the start was refused."""
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(0.30)
    for key, ceiling in (("a", 0.10), ("b", 0.20)):
        run_id, decision = _started(session, scope, key)
        repo.charge(
            run_id=run_id,
            kind=ChargeKind.AGENT_JOB,
            ceiling_usd=ceiling,
            approval_decision_id=decision,
        )
    wallet = repo.wallet()
    assert wallet is not None and (wallet.charged_usd, wallet.remaining_usd) == (0.3, 0.0)


def test_a_charge_above_what_remains_is_refused_and_writes_nothing(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(5.0)
    run_id, decision = _started(session, scope, "a")
    with pytest.raises(WalletChargeRefused) as refused:
        repo.charge(
            run_id=run_id,
            kind=ChargeKind.RESEARCH_RUN,
            ceiling_usd=5.5,
            approval_decision_id=decision,
        )
    assert (refused.value.reason, refused.value.remaining_usd) == ("outside_wallet", 5.0)
    assert repo.charges() == []


def test_an_unknown_ceiling_is_refused_never_charged_as_zero(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(5.0)
    run_id, decision = _started(session, scope, "a")
    with pytest.raises(WalletChargeRefused) as refused:
        repo.charge(
            run_id=run_id,
            kind=ChargeKind.AGENT_JOB,
            ceiling_usd=None,
            approval_decision_id=decision,
        )
    assert refused.value.reason == "ceiling_unknown"
    assert repo.quote(None) == (WalletVerdict.CEILING_UNKNOWN, 5.0)
    assert repo.charges() == []


def test_no_wallet_refuses_a_charge(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    run_id, decision = _started(session, scope, "a")
    with pytest.raises(WalletChargeRefused) as refused:
        StudyWalletRepository(session, scope).charge(
            run_id=run_id,
            kind=ChargeKind.RESEARCH_RUN,
            ceiling_usd=0.0,
            approval_decision_id=decision,
        )
    assert refused.value.reason == "no_wallet"


def _refused(repo: StudyWalletRepository, run_id: str, decision: int, **extra: Any) -> str:
    with pytest.raises(ScopeDenied) as refused:
        repo.charge(
            run_id=run_id,
            kind=ChargeKind.RESEARCH_RUN,
            ceiling_usd=1.0,
            approval_decision_id=decision,
            **extra,
        )
    return refused.value.reason


def test_a_charge_needs_this_runs_start_decision(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    run_id = _run(session, scope, "a")
    other_run = _run(session, scope, "b")
    sibling = scoped.scope(study="sibling")

    spend = _authority(session, scope, run_id, ApprovalSubject.SPEND)
    assert _refused(repo, run_id, spend) == "not_a_start_decision"
    foreign = _authority(session, sibling, run_id, ApprovalSubject.CHAT_START)
    assert _refused(repo, run_id, foreign) == "not_a_start_decision"
    assert _refused(repo, run_id, 999_999) == "not_a_start_decision"
    another = _authority(session, scope, other_run)
    assert _refused(repo, run_id, another) == "decision_names_another_run"
    unnamed = _authority(session, scope, None)
    assert _refused(repo, run_id, unnamed) == "decision_names_another_run"
    declined = _authority(session, scope, run_id, decision="decline")
    assert _refused(repo, run_id, declined) == "decision_not_a_start"
    chat = _authority(session, scope, run_id)
    assert _refused(repo, run_id, chat, plan_id="PLAN-1") == "chat_start_names_a_plan"
    assert repo.charges() == []


def test_one_chat_start_row_cannot_authorise_a_second_run(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    run_id, decision = _started(session, scope, "a")
    repo.charge(
        run_id=run_id, kind=ChargeKind.RESEARCH_RUN, ceiling_usd=1.0, approval_decision_id=decision
    )
    second = _run(session, scope, "b")
    # The row names the first run; were it unnamed, the unique key would refuse it as well.
    assert _refused(repo, second, decision) == "decision_names_another_run"
    assert [c.run_id for c in repo.charges()] == [run_id]


def test_a_used_decision_is_refused_and_the_table_holds_it_once(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    wallet = repo.set_cap(10.0)
    run_id, decision = _started(session, scope, "a")
    repo.charge(
        run_id=run_id, kind=ChargeKind.RESEARCH_RUN, ceiling_usd=1.0, approval_decision_id=decision
    )
    second = _run(session, scope, "b")
    session.add(
        StudyWalletChargeRow(
            wallet_id=wallet.wallet_id,
            study_id=scope.study_id,
            run_id=second,
            kind="research_run",
            ceiling_usd=1.0,
            approval_decision_id=decision,
        )
    )
    with pytest.raises(
        IntegrityError,
        match=r"wallet_charge_decision_once|study_wallet_charges\.approval_decision_id",
    ):
        session.flush()


def test_a_plan_step_charge_names_its_step_and_plan(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    run_id, decision = _started(
        session, scope, "a", subject=ApprovalSubject.PLAN_STEP, subject_id="STEP-1"
    )
    assert _refused(repo, run_id, decision) == "plan_step_mismatch"
    assert _refused(repo, run_id, decision, plan_id="PLAN-1") == "plan_step_mismatch"
    assert (
        _refused(repo, run_id, decision, plan_id="PLAN-1", plan_step_id="STEP-2")
        == "plan_step_mismatch"
    )
    charge = repo.charge(
        run_id=run_id,
        kind=ChargeKind.INTERPRETATION_RESEARCH,
        ceiling_usd=1.0,
        approval_decision_id=decision,
        plan_id="PLAN-1",
        plan_step_id="STEP-1",
    )
    assert (charge.plan_id, charge.plan_step_id) == ("PLAN-1", "STEP-1")


def test_another_studys_run_is_never_charged(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    sibling = scoped.scope(study="sibling")
    sibling_run = _run(session, sibling, "s")
    assert _refused(repo, sibling_run, _authority(session, scope, sibling_run)) == "unknown_run"
    # ... and a charged run of one study is not another study's either.
    own, decision = _started(session, scope, "o")
    repo.charge(
        run_id=own, kind=ChargeKind.RESEARCH_RUN, ceiling_usd=1.0, approval_decision_id=decision
    )
    sibling_repo = StudyWalletRepository(session, sibling)
    sibling_repo.set_cap(10.0)
    assert _refused(sibling_repo, own, _authority(session, sibling, own)) == "unknown_run"
    wallet = sibling_repo.wallet()
    assert wallet is not None and wallet.charged_usd == 0.0


def test_a_closed_wallet_holds_nothing_and_a_new_one_opens_fresh(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    first = repo.set_cap(10.0)
    assert repo.close() is True
    assert repo.wallet() is None and repo.close() is False
    second = repo.set_cap(5.0)
    assert second.wallet_id != first.wallet_id
    assert [r.from_cap_usd for r in repo.raises()] == [0.0]


def test_a_closed_study_refuses_a_raise_a_quote_and_a_charge(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    repo.set_cap(10.0)
    run_id, decision = _started(session, scope, "a")
    for status in ("DELIVERED", "ARCHIVED", "CANCELLED"):
        study = session.get(StudyRow, scope.study_id)
        assert study is not None
        study.status = status
        session.flush()
        for call in (
            lambda: repo.set_cap(20.0),
            lambda: repo.quote(1.0),
            lambda: repo.charge(
                run_id=run_id,
                kind=ChargeKind.RESEARCH_RUN,
                ceiling_usd=1.0,
                approval_decision_id=decision,
            ),
        ):
            with pytest.raises(ScopeDenied) as refused:
                call()
            assert refused.value.reason == "study_closed"
    assert repo.charges() == [] and len(repo.raises()) == 1


@pytest.mark.parametrize(
    "status", [StudyStatus.DELIVERED, StudyStatus.ARCHIVED, StudyStatus.CANCELLED]
)
def test_closing_the_study_closes_its_wallet_when_the_wallet_is_on(
    session: Session, scoped: Any, status: StudyStatus
) -> None:
    scope = scoped.scope()
    StudyWalletRepository(session, scope).set_cap(10.0)
    set_study_status(session, scope, status, wallet_enabled=True)
    assert StudyWalletRepository(session, scope).wallet() is None
    row = session.scalars(select(StudyWalletRow)).one()
    assert row.closed_at is not None


def test_a_status_change_that_keeps_the_study_open_keeps_its_wallet(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    StudyWalletRepository(session, scope).set_cap(10.0)
    set_study_status(session, scope, StudyStatus.IN_REVIEW, wallet_enabled=True)
    assert StudyWalletRepository(session, scope).wallet() is not None


def test_off_a_status_change_reads_no_wallet(
    session: Session, scoped: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def untouched(*_: Any, **__: Any) -> Any:
        raise AssertionError("the wallet was read with the switch off")

    monkeypatch.setattr(StudyWalletRepository, "__init__", untouched)
    study = set_study_status(session, scoped.scope(), StudyStatus.ARCHIVED, wallet_enabled=False)
    assert study.status is StudyStatus.ARCHIVED


def test_the_tables_refuse_a_second_open_wallet_and_a_second_charge(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    wallet = repo.set_cap(10.0)
    savepoint = session.begin_nested()
    session.add(
        StudyWalletRow(
            wallet_id="WAL-second",
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=scope.study_id,
            cap_usd=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    savepoint.rollback()

    run_id, decision = _started(session, scope, "a")
    repo.charge(
        run_id=run_id, kind=ChargeKind.RESEARCH_RUN, ceiling_usd=1.0, approval_decision_id=decision
    )
    session.add(
        StudyWalletChargeRow(
            wallet_id=wallet.wallet_id,
            study_id=scope.study_id,
            run_id=run_id,
            kind="research_run",
            ceiling_usd=1.0,
            approval_decision_id=_authority(session, scope, run_id, subject_id="start-2"),
        )
    )
    with pytest.raises(
        IntegrityError, match=r"wallet_charge_run_once|study_wallet_charges\.run_id"
    ):
        session.flush()


def test_the_table_refuses_an_unknown_charge_kind(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    wallet = StudyWalletRepository(session, scope).set_cap(10.0)
    run_id, decision = _started(session, scope, "a")
    session.add(
        StudyWalletChargeRow(
            wallet_id=wallet.wallet_id,
            study_id=scope.study_id,
            run_id=run_id,
            kind="lead_turn",
            ceiling_usd=1.0,
            approval_decision_id=decision,
        )
    )
    with pytest.raises(IntegrityError, match="wallet_charge_kind_known"):
        session.flush()


# --------------------------------------------------------------------------- the switch


def test_off_nothing_reads_or_writes_a_wallet(
    session: Session, scoped: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def untouched(*_: Any, **__: Any) -> Any:
        raise AssertionError("the repository was built with the wallet off")

    monkeypatch.setattr(StudyWalletRepository, "__init__", untouched)
    wallets = StudyWallets(session, scoped.scope(), enabled=False)
    for call in (
        wallets.read,
        lambda: wallets.set_cap(1.0),
        lambda: wallets.quote(1.0),
        lambda: wallets.charge(
            run_id="RUN-x", kind=ChargeKind.RESEARCH_RUN, ceiling_usd=1.0, approval_decision_id=1
        ),
    ):
        with pytest.raises(WalletDisabled):
            call()
    for table in (StudyWalletRow, StudyWalletRaiseRow, StudyWalletChargeRow):
        assert session.scalar(select(func.count()).select_from(table)) == 0


def test_on_the_application_reads_and_sets_the_wallet(session: Session, scoped: Any) -> None:
    wallets = StudyWallets(session, scoped.scope(), enabled=True)
    assert wallets.read() == (None, [], [])
    wallets.set_cap(12.0)
    wallet, raises, charges = wallets.read()
    assert wallet is not None and wallet.remaining_usd == 12.0
    assert len(raises) == 1 and charges == []


# --------------------------------------------------------------------------- PostgreSQL


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    return engine


def test_concurrent_charges_never_exceed_the_cap(
    postgres: Any, session: Session, scoped: Any
) -> None:
    """Eight starts race for a USD 10 wallet, each charging USD 3: exactly three fit (USD 9), the
    other five are refused ``outside_wallet``, and the charged sum never passes the cap. Every
    thread holds its transaction open after its decision until all have decided, so a missing
    lock would let more than three read "10 remains" and insert."""
    from aia_core.infrastructure.db import create_session_factory

    scope = scoped.scope()
    StudyWalletRepository(session, scope).set_cap(10.0)
    runs = [_run(session, scope, f"r{i}") for i in range(8)]
    decisions = [_authority(session, scope, run_id) for run_id in runs]
    session.commit()

    factory = create_session_factory(postgres)
    barrier = threading.Barrier(len(runs))
    outcomes: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def start(run_id: str, decision: int) -> None:
        try:
            barrier.wait(30)
            with factory() as own:
                try:
                    StudyWalletRepository(own, scope).charge(
                        run_id=run_id,
                        kind=ChargeKind.RESEARCH_RUN,
                        ceiling_usd=3.0,
                        approval_decision_id=decision,
                    )
                    time.sleep(0.05)  # hold the lock a moment: a racer must wait, not pass
                    own.commit()
                    result = "charged"
                except WalletChargeRefused as exc:
                    own.rollback()
                    result = exc.reason
            with lock:
                outcomes.append(result)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    threads = [
        threading.Thread(target=start, args=pair) for pair in zip(runs, decisions, strict=True)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    assert sorted(outcomes) == ["charged"] * 3 + ["outside_wallet"] * 5
    session.expire_all()
    wallet = StudyWalletRepository(session, scope).wallet()
    assert wallet is not None
    assert (wallet.charged_usd, wallet.remaining_usd) == (9.0, 1.0)


def test_a_charge_waits_for_a_concurrent_cap_change_and_reads_it(
    postgres: Any, session: Session, scoped: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cap lowered from USD 10 to USD 2 is held after its decision; a USD 5 charge started
    meanwhile must wait on the study row and then be refused against the new cap, never pass
    on the old one."""
    from aia_core.infrastructure.db import create_session_factory

    scope = scoped.scope()
    StudyWalletRepository(session, scope).set_cap(10.0)
    run_id, decision = _started(session, scope, "r")
    session.commit()

    lowered, go = threading.Event(), threading.Event()
    factory = create_session_factory(postgres)
    outcome: list[str] = []
    errors: list[BaseException] = []

    def lower() -> None:
        try:
            with factory() as own:
                StudyWalletRepository(own, scope).set_cap(2.0)
                lowered.set()
                assert go.wait(30)
                own.commit()
        except BaseException as exc:
            errors.append(exc)

    def charge() -> None:
        try:
            with factory() as own:
                try:
                    StudyWalletRepository(own, scope).charge(
                        run_id=run_id,
                        kind=ChargeKind.RESEARCH_RUN,
                        ceiling_usd=5.0,
                        approval_decision_id=decision,
                    )
                    own.commit()
                    outcome.append("charged")
                except WalletChargeRefused as exc:
                    outcome.append(exc.reason)
        except BaseException as exc:
            errors.append(exc)

    a = threading.Thread(target=lower)
    a.start()
    assert lowered.wait(30)
    b = threading.Thread(target=charge)
    b.start()
    time.sleep(1.0)  # room for the charge to finish if nothing holds it
    assert outcome == []  # it waits on the study row
    go.set()
    a.join(30)
    b.join(30)
    assert not errors, errors
    assert outcome == ["outside_wallet"]


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("the_study_wallet", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tables(connection: Any) -> set[str]:
    return set(
        connection.execute(
            text("SELECT tablename FROM pg_tables WHERE tablename LIKE 'study_wallet%'")
        ).scalars()
    )


def test_the_migration_lists_the_domain_charge_kinds() -> None:
    migration = _migration()
    assert tuple(k.value for k in ChargeKind) == migration._KINDS
    assert migration.down_revision == "b5d7f9a1c3e6"


def test_the_downgrade_takes_the_wallet_back_and_the_upgrade_restores_it(postgres: Any) -> None:
    migration = _migration()
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert _tables(connection) == set()
                migration.upgrade()
            assert _tables(connection) == {
                "study_wallets",
                "study_wallet_raises",
                "study_wallet_charges",
            }
        finally:
            transaction.rollback()  # PostgreSQL DDL is transactional


def test_the_downgrade_refuses_while_a_raise_is_stored(
    postgres: Any, session: Session, scoped: Any
) -> None:
    StudyWalletRepository(session, scoped.scope()).set_cap(1.0)
    session.commit()
    migration = _migration()
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with (
                Operations.context(MigrationContext.configure(connection)),
                pytest.raises(RuntimeError, match="insert-once"),
            ):
                migration.downgrade()
        finally:
            transaction.rollback()


def test_a_first_cap_of_zero_is_recorded_like_any_other(session: Session, scoped: Any) -> None:
    """Opening a wallet is a person's act, even at USD 0: one raise and one ledger row."""
    scope = scoped.scope()
    repo = StudyWalletRepository(session, scope)
    wallet = repo.set_cap(0.0)
    assert (wallet.cap_usd, wallet.remaining_usd) == (0.0, 0.0)
    assert [(r.from_cap_usd, r.to_cap_usd) for r in repo.raises()] == [(0.0, 0.0)]
    assert len(WorkflowRepository(session, scope).ledger([ApprovalSubject.WALLET])) == 1
    repo.set_cap(0.0)  # the same cap on an open wallet writes nothing
    assert len(repo.raises()) == 1
