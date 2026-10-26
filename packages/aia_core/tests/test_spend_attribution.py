"""Per-researcher spend (``develop-spend-attribution`` 7, Q40, the product owner 2026-10-21).

A charge is booked to whoever approved or started the paid work: the hold records the person
when it is made (``budget_reservations.charged_to_user_id``), the usage row copies its hold's,
and the per-person read lets OWNER and ADMIN see everyone and a researcher only themself, in the
query. Unknown stays null and is listed as unattributed, never booked to someone by guess.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from aia_core.application.researcher_spend import researcher_spend_report
from aia_core.application.scope import ScopeResolver
from aia_core.domain.ai_contracts import (
    AIUsageEvent,
    CallPurpose,
    CostBasis,
    ModelUsage,
    UsageOutcome,
    new_usage_event_id,
)
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.analysis.steps import ANALYSIS_STAGE
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.spend_attribution import (
    CARD_APPROVAL,
    START_APPROVALS,
    ActivitySpend,
    HoldFact,
    SpendActivity,
    SpendPeriod,
    UsageFact,
    activity_of,
    charged_to,
    period_bounds,
    researcher_spend,
    run_spend,
    runs_spend,
)
from aia_core.domain.workflow import FailureClass, StepDefinition
from aia_core.domain.workflow_templates import RESEARCH, RESEARCH_LEAD
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.researcher_spend_repository import (
    ResearcherSpendRepository,
    run_spend_facts,
)
from aia_core.infrastructure.tables import (
    AIUsageEventRow,
    ApprovalDecisionRow,
    BudgetReservationRow,
    StudyRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import ClaimedWork, WorkflowRepository

REPO = Path(__file__).resolve().parents[3]
MIGRATION = REPO / "migrations/versions/20261021_568761e1c719_per_researcher_spend_attribution.py"
WORKER = "worker-1"


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("per_researcher_spend", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- the rule


def test_the_rule_books_the_lift_then_the_one_approver_then_the_starter() -> None:
    assert charged_to(lift_approver="B", start_approvers={"C"}, starter="A") == "B"
    assert charged_to(lift_approver=None, start_approvers={"C"}, starter="A") == "C"
    assert charged_to(lift_approver=None, start_approvers=(), starter="A") == "A"
    # Two approvers is no single approver: booked to nobody, never to one of them by guess.
    assert charged_to(lift_approver=None, start_approvers={"C", "D"}, starter="A") is None
    assert charged_to(lift_approver=None, start_approvers=(), starter=None) is None


def test_the_activities_follow_the_workflows_and_stages_they_name() -> None:
    """The domain writes the workflow names out; they are held to the constants here."""
    assert activity_of(RESEARCH_LEAD, "BRIEF") is SpendActivity.LEAD
    assert activity_of(DEEP_RESEARCH, "RESEARCH") is SpendActivity.DEEP_RESEARCH
    assert activity_of(RESEARCH, "FIELDWORK") is SpendActivity.FIELDWORK
    assert activity_of(RESEARCH, ANALYSIS_STAGE) is SpendActivity.ANALYSIS_REPORT
    assert activity_of(RESEARCH, "REPORT") is SpendActivity.ANALYSIS_REPORT
    assert activity_of("research_agent", "BRIEF") is SpendActivity.OTHER
    assert activity_of(None, None) is SpendActivity.OTHER


def test_the_start_approvals_are_ledger_subjects() -> None:
    assert {s.value for s in START_APPROVALS} == set(_migration()._START_APPROVALS)
    assert CARD_APPROVAL.value == _migration()._CARD
    assert _migration().down_revision == "c663617cf79b"


def test_the_periods_are_utc_months_and_the_year() -> None:
    now = datetime(2026, 1, 14, 9, 30, tzinfo=UTC)
    assert period_bounds(SpendPeriod.THIS_MONTH, now) == (datetime(2026, 1, 1, tzinfo=UTC), now)
    assert period_bounds(SpendPeriod.LAST_MONTH, now) == (
        datetime(2025, 12, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert period_bounds(SpendPeriod.YEAR_TO_DATE, now) == (datetime(2026, 1, 1, tzinfo=UTC), now)
    may = datetime(2026, 5, 3, tzinfo=UTC)
    assert period_bounds(SpendPeriod.LAST_MONTH, may)[0] == datetime(2026, 4, 1, tzinfo=UTC)


# --------------------------------------------------------------------------- the fold

_T0 = datetime(2026, 10, 1, tzinfo=UTC)
_T1 = datetime(2026, 11, 1, tzinfo=UTC)


def _u(call: str, outcome: str, cost: float, who: str | None = "A", **kw: Any) -> UsageFact:
    base: dict[str, Any] = {
        "call_id": call,
        "outcome": outcome,
        "cost_usd": cost,
        "charged_to": who,
        "client_id": "CLI-1",
        "study_id": "STU-1",
        "activity": SpendActivity.FIELDWORK,
        "occurred_at": _T0 + timedelta(days=3),
    }
    return UsageFact(**{**base, **kw})


def _h(rid: str, status: str, amount: float, settled: float, **kw: Any) -> HoldFact:
    base: dict[str, Any] = {
        "reservation_id": rid,
        "status": status,
        "amount_usd": amount,
        "settled_amount_usd": settled,
        "charged_to": "A",
        "client_id": "CLI-1",
        "study_id": "STU-1",
        "activity": SpendActivity.DEEP_RESEARCH,
        "in_ledger": False,
        "settled_at": _T0 + timedelta(days=4),
    }
    return HoldFact(**{**base, **kw})


def test_the_fold_separates_model_tool_reserved_and_uncertain() -> None:
    usage = [
        _u("c1", "DISPATCHED", 0.0),
        _u("c1", "SUCCEEDED", 0.40),
        # Uncertain, carried at its ceiling: counted, and its exposure stays in the total.
        _u("c2", "DISPATCHED", 0.0, activity=SpendActivity.ANALYSIS_REPORT),
        _u("c2", "UNCERTAIN", 1.00, activity=SpendActivity.ANALYSIS_REPORT),
        # Died in flight: no terminal row, nothing recorded, still uncertain -- never zero.
        _u("c3", "DISPATCHED", 0.0),
        # Uncertain and then resolved: not uncertain any more, the compensation counts.
        _u("c4", "DISPATCHED", 0.0),
        _u("c4", "UNCERTAIN", 1.00),
        _u("c4", "RESOLVED_BILLED", -0.70),
        # Outside the period: not this month's spend.
        _u("c5", "SUCCEEDED", 5.0, occurred_at=_T1 + timedelta(days=1)),
    ]
    holds = [
        _h("r1", "SETTLED", 0.10, 0.04),  # a tool call: outside the ledger
        _h("r2", "SETTLED_UNCERTAIN", 0.10, 0.10),  # a tool call nobody knows the bill of
        _h("r3", "RESERVED", 2.0, 0.0, settled_at=None),  # open now
        _h("r4", "SETTLED", 0.40, 0.40, in_ledger=True),  # a model hold: the ledger carries it
        _h("r5", "RELEASED", 1.0, 0.0),  # nothing spent
    ]
    out = researcher_spend(usage, holds, start=_T0, end=_T1, people=["A", "B"])
    a = out["A"]
    assert a.model_usd == pytest.approx(0.40 + 1.00 + 0.30)
    assert a.outside_ledger_usd == pytest.approx(0.14)
    assert a.total_usd == pytest.approx(1.84)
    assert a.reserved_usd == pytest.approx(2.0)
    assert a.uncertain_calls == 3  # c2, c3 and the uncertain tool hold
    assert a.by_activity[SpendActivity.ANALYSIS_REPORT].uncertain_calls == 1
    assert a.by_activity[SpendActivity.DEEP_RESEARCH].total_usd == pytest.approx(0.14)
    assert a.study_count == 1
    # A member with nothing booked is listed at a known zero.
    assert out["B"].total_usd == 0.0 and out["B"].uncertain_calls == 0
    # The parts add up to the whole, by activity and by study.
    assert sum(x.total_usd for x in a.by_activity.values()) == pytest.approx(a.total_usd)
    assert sum(x.total_usd for x in a.studies.values()) == pytest.approx(a.total_usd)


def test_a_runs_spend_is_every_persons_over_its_whole_life() -> None:
    usage = [
        _u("c1", "SUCCEEDED", 0.40, who="A"),
        _u("c2", "SUCCEEDED", 0.20, who="B", occurred_at=_T1 + timedelta(days=40)),
        _u("c3", "DISPATCHED", 0.0, who=None),  # died in flight: uncertain, never zero
    ]
    holds = [
        _h("r1", "SETTLED", 0.10, 0.05, charged_to="B"),
        _h("r2", "RESERVED", 1.5, 0.0, settled_at=None, charged_to=None),
    ]
    spend = run_spend(usage, holds)
    assert spend.total_usd == pytest.approx(0.65)
    assert spend.reserved_usd == pytest.approx(1.5)
    assert spend.uncertain_calls == 1
    empty = run_spend([], [])
    assert (empty.total_usd, empty.reserved_usd, empty.uncertain_calls) == (0.0, 0.0, 0)


def test_the_fold_keeps_the_unattributed_apart() -> None:
    out = researcher_spend(
        [_u("c1", "SUCCEEDED", 0.5, who=None)], [], start=_T0, end=_T1, people=["A"]
    )
    assert out[None].total_usd == 0.5 and out["A"].total_usd == 0.0


# --------------------------------------------------------------------------- the world


@pytest.fixture
def lead_repo(session: Session, scoped: Any) -> WorkflowRepository:
    repo = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    study = session.get(StudyRow, repo.scope.study_id)
    assert study is not None
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()
    return repo


def _run(
    repo: WorkflowRepository,
    session: Session,
    scoped: Any,
    key: str,
    *,
    workflow_type: str = RESEARCH,
    stage: str = "FIELDWORK",
) -> str:
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title=f"Spend {key}", content={"goal": key}
    )
    return repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type=workflow_type,
        steps=[StepDefinition(node_key="only", kind="k", stage_type=stage)],
        idempotency_key=f"spend-{key}",
    )


def _claim(repo: WorkflowRepository, run_id: str) -> ClaimedWork:
    work = repo.claim_next(worker_id=WORKER)
    assert work is not None and work.run_id == run_id
    return work


def _hold(repo: WorkflowRepository, work: ClaimedWork, amount: float = 1.0) -> BudgetReservationRow:
    rid = repo.reserve_budget(
        attempt_id=work.attempt_id,
        worker_id=work.worker_id,
        amount_usd=amount,
        provider=Provider.ANTHROPIC,
    )
    assert rid is not None
    row = repo._session.get(BudgetReservationRow, rid)
    assert row is not None
    return row


def _ledger(session: Session, scope: Any, subject: ApprovalSubject, run_id: str, **kw: Any) -> None:
    """A ledger row the way its writer will write it (the chat start and the plan step have no
    writer yet: LO5, LO3)."""
    session.add(
        ApprovalDecisionRow(
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=scope.study_id,
            subject_type=subject,
            subject_id=kw.pop("subject_id", run_id),
            run_id=run_id,
            approver_user_id=scope.actor_id,
            decision=kw.pop("decision", "start"),
            **kw,
        )
    )
    session.flush()


# --------------------------------------------------------------------------- the hypothesis


def test_the_ledgers_actor_is_the_runs_starter_or_the_worker_never_the_payer(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    """**Settles the plan's hypothesis.** ``ai_usage_events.actor_id`` is the egress decision's
    actor, which for a worker is the execution context's: the run's ``triggered_by`` when it
    names one, else the lease identity ``worker:<id>`` (``application/scope.py``
    ``execution_context``). It is never an approver, so it is not Q40's attribution."""
    run_id = _run(lead_repo, session, scoped, "actor")
    work = _claim(lead_repo, run_id)
    resolver = ScopeResolver(session)
    issued = resolver.execution_context(attempt_id=work.attempt_id, worker_id=WORKER)
    assert issued.actor_id == scoped.users["lead"]

    run = session.get(WorkflowRunRow, run_id)
    assert run is not None
    run.triggered_by = None
    session.flush()
    nobody = resolver.execution_context(attempt_id=work.attempt_id, worker_id=WORKER)
    assert nobody.actor_id == f"worker:{WORKER}"


# --------------------------------------------------------------------------- who pays, per path


def test_a_persons_own_start_is_booked_to_them(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "direct")
    assert _hold(lead_repo, _claim(lead_repo, run_id)).charged_to_user_id == scoped.users["lead"]


def test_a_spend_confirmation_books_the_person_who_confirmed(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "confirm")
    confirmer = WorkflowRepository(session, scoped.scope(user="researcher", study="primary"))
    confirmer.record_spend_confirmation(run_id, ceiling_usd=5, limit_usd=4, confirmed_usd=5)
    hold = _hold(lead_repo, _claim(lead_repo, run_id))
    assert hold.charged_to_user_id == scoped.users["researcher"]


def test_a_lead_card_books_the_person_who_approved_it(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    lead_turn = _run(lead_repo, session, scoped, "turn", workflow_type=RESEARCH_LEAD)
    job = _run(lead_repo, session, scoped, "job", workflow_type="research_agent")
    approver = WorkflowRepository(session, scoped.scope(user="reviewer", study="primary"))
    approver.record_lead_job_approval(
        lead_turn,
        turn_id="TURN-1",
        agent_run_id=job,
        design_revision_id="DREV-1",
        action="build",
        spend=None,
    )
    # The turn itself (claimed first, the older run) is the researcher's who posted it.
    turn_hold = _hold(lead_repo, _claim(lead_repo, lead_turn))
    assert turn_hold.charged_to_user_id == scoped.users["lead"]
    job_hold = _hold(lead_repo, _claim(lead_repo, job))
    assert job_hold.charged_to_user_id == scoped.users["reviewer"]


@pytest.mark.parametrize("subject", [ApprovalSubject.CHAT_START, ApprovalSubject.PLAN_STEP])
def test_a_wallet_start_books_its_decisions_approver(
    lead_repo: WorkflowRepository, session: Session, scoped: Any, subject: ApprovalSubject
) -> None:
    """The decision a wallet charge names (LO1) is the same row the hold is booked by, so a
    researcher's total and the wallet agree."""
    run_id = _run(lead_repo, session, scoped, f"wallet-{subject}")
    _ledger(session, scoped.scope(user="viewer", study="primary"), subject, run_id)
    hold = _hold(lead_repo, _claim(lead_repo, run_id))
    assert hold.charged_to_user_id == scoped.users["viewer"]


def test_two_approvers_book_nobody(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "two")
    _ledger(session, scoped.scope(user="viewer"), ApprovalSubject.SPEND, run_id)
    _ledger(session, scoped.scope(user="reviewer"), ApprovalSubject.ANSWERABILITY, run_id)
    assert _hold(lead_repo, _claim(lead_repo, run_id)).charged_to_user_id is None


def test_a_starter_who_is_no_member_is_no_person(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "worker")
    run = session.get(WorkflowRunRow, run_id)
    assert run is not None
    run.triggered_by = "worker:elsewhere"
    session.flush()
    assert _hold(lead_repo, _claim(lead_repo, run_id)).charged_to_user_id is None


def test_a_budget_lift_books_the_holds_after_it_to_the_lifter(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "lift")
    first = _claim(lead_repo, run_id)
    before = _hold(lead_repo, first)
    lead_repo.settle_reservation(before.reservation_id, actual_cost_usd=0.5)
    lead_repo.fail_attempt(first.attempt_id, worker_id=WORKER, failure=FailureClass.BUDGET_EXCEEDED)
    WorkflowRepository(session, scoped.scope(user="researcher")).resume_budget_wait(
        first.step_id, note="", budget_before=100.0, budget_after=200.0
    )
    after = _hold(lead_repo, _claim(lead_repo, run_id))
    assert before.charged_to_user_id == scoped.users["lead"]
    assert after.charged_to_user_id == scoped.users["researcher"]


def _append(
    usage: AIUsageRepository,
    scope: Any,
    work: ClaimedWork,
    reservation_id: str | None,
    outcome: UsageOutcome,
    cost: float,
    *,
    call_id: str,
    **kw: Any,
) -> AIUsageEvent:
    event = AIUsageEvent(
        event_id=new_usage_event_id(),
        call_id=call_id,
        outcome=outcome,
        purpose=CallPurpose.PRIMARY,
        organization_id=scope.organization_id,
        client_id=scope.client_id,
        study_id=scope.study_id,
        actor_id=scope.actor_id,
        run_id=work.run_id,
        step_id=work.step_id,
        attempt_id=work.attempt_id,
        reservation_id=reservation_id,
        agent_id="spend",
        agent_version="1",
        prompt_id="p",
        prompt_version="1",
        capability=ModelCapability.FAST_EXTRACTION,
        policy_version="pv",
        runtime_version="rv",
        provider=Provider.ANTHROPIC,
        model="m",
        served_model="m",
        route_id="r",
        data_class=DataClass.CLASS_C_INTERNAL,
        residency_zone="EU",
        provider_request_id=None,
        error_kind=None,
        failure_class=None,
        finish_reason=None,
        usage=ModelUsage(),
        cost_usd=cost,
        cost_basis=kw.pop("cost_basis", CostBasis.METERED),
        schema_fingerprint=None,
        substituted_from=None,
        fallback_from=None,
        fallback_authorised_by=None,
        occurred_at=kw.pop("occurred_at", datetime.now(UTC)),
        **kw,
    )
    usage.append(event)
    return event


def _booked(session: Session, call_id: str) -> set[str | None]:
    return set(
        session.scalars(
            select(AIUsageEventRow.charged_to_user_id).where(AIUsageEventRow.call_id == call_id)
        )
    )


def test_a_usage_row_takes_its_holds_person_and_a_resolution_keeps_it(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id = _run(lead_repo, session, scoped, "usage")
    confirmer = WorkflowRepository(session, scoped.scope(user="researcher"))
    confirmer.record_spend_confirmation(run_id, ceiling_usd=1, limit_usd=1, confirmed_usd=1)
    work = _claim(lead_repo, run_id)
    hold = _hold(lead_repo, work)
    scope = lead_repo.scope
    usage = AIUsageRepository(session, scope)
    _append(usage, scope, work, hold.reservation_id, UsageOutcome.DISPATCHED, 0.0, call_id="k1")
    _append(
        usage,
        scope,
        work,
        hold.reservation_id,
        UsageOutcome.UNCERTAIN,
        1.0,
        call_id="k1",
        cost_basis=CostBasis.CEILING,
    )
    # A budget manager resolves it: the resolution's actor is the manager, its payer unchanged.
    manager = AIUsageRepository(session, scoped.scope(user="owner"))
    resolved = manager.resolve_uncertain("k1", billed=True, actual_cost_usd=0.2)
    assert resolved.actor_id == scoped.users["owner"]
    assert _booked(session, "k1") == {scoped.users["researcher"]}

    # A call with no hold (a subscription runtime) takes the run's person by the same rule.
    _append(usage, scope, work, None, UsageOutcome.DISPATCHED, 0.0, call_id="k2")
    assert _booked(session, "k2") == {scoped.users["researcher"]}


# --------------------------------------------------------------------------- the read


def _spend_world(lead_repo: WorkflowRepository, session: Session, scoped: Any) -> tuple[str, str]:
    """lead: a fieldwork call (USD 0.40) and an open hold (USD 2); researcher: an analysis call
    (USD 0.25) in the sibling study; nobody: a hold whose run names no person (USD 0.30)."""
    run_id = _run(lead_repo, session, scoped, "lead-work")
    work = _claim(lead_repo, run_id)
    hold = _hold(lead_repo, work, 0.5)
    usage = AIUsageRepository(session, lead_repo.scope)
    _append(
        usage,
        lead_repo.scope,
        work,
        hold.reservation_id,
        UsageOutcome.DISPATCHED,
        0.0,
        call_id="w1",
    )
    _append(
        usage,
        lead_repo.scope,
        work,
        hold.reservation_id,
        UsageOutcome.SUCCEEDED,
        0.40,
        call_id="w1",
    )
    lead_repo.settle_reservation(hold.reservation_id, actual_cost_usd=0.40)
    _hold(lead_repo, work, 2.0)

    sibling = WorkflowRepository(session, scoped.scope(user="researcher", study="sibling"))
    sib_study = session.get(StudyRow, sibling.scope.study_id)
    assert sib_study is not None
    sib_study.budget_usd = 100.0
    project, _ = ProjectRepository(session, sibling.scope).create(title="S", content={"g": 1})
    sib_run = sibling.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type=RESEARCH,
        steps=[StepDefinition(node_key="only", kind="k", stage_type=ANALYSIS_STAGE)],
        idempotency_key="spend-sibling",
    )
    sib_work = sibling.claim_next(worker_id=WORKER)
    assert sib_work is not None and sib_work.run_id == sib_run
    sib_hold = sibling.reserve_budget(
        attempt_id=sib_work.attempt_id,
        worker_id=WORKER,
        amount_usd=1.0,
        provider=Provider.ANTHROPIC,
    )
    sib_usage = AIUsageRepository(session, sibling.scope)
    _append(
        sib_usage, sibling.scope, sib_work, sib_hold, UsageOutcome.DISPATCHED, 0.0, call_id="s1"
    )
    _append(
        sib_usage, sibling.scope, sib_work, sib_hold, UsageOutcome.SUCCEEDED, 0.25, call_id="s1"
    )
    assert sib_hold is not None
    sibling.settle_reservation(sib_hold, actual_cost_usd=0.25)

    orphan = _run(lead_repo, session, scoped, "orphan")
    run = session.get(WorkflowRunRow, orphan)
    assert run is not None
    run.triggered_by = None
    session.flush()
    orphan_hold = _hold(lead_repo, _claim(lead_repo, orphan), 0.3)
    lead_repo.settle_reservation(orphan_hold.reservation_id, actual_cost_usd=0.30)
    return run_id, orphan


def test_an_administrator_reads_everyone_and_the_unattributed(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    _spend_world(lead_repo, session, scoped)
    report = researcher_spend_report(session, scoped.admin_context, SpendPeriod.THIS_MONTH)
    assert report.everyone is True
    by = {n.person.user_id if n.person else None: n.spend for n in report.people}
    lead, researcher = by[scoped.users["lead"]], by[scoped.users["researcher"]]
    assert (lead.model_usd, lead.reserved_usd, lead.study_count) == pytest.approx((0.40, 2.0, 1))
    assert lead.by_activity[SpendActivity.FIELDWORK].total_usd == pytest.approx(0.40)
    assert researcher.by_activity[SpendActivity.ANALYSIS_REPORT].total_usd == pytest.approx(0.25)
    assert [s for (_, s) in researcher.studies] == [scoped.studies["sibling"].study_id]
    # Outside the ledger and booked to nobody: listed apart, last.
    assert by[None].outside_ledger_usd == pytest.approx(0.30)
    assert report.people[-1].person is None
    # Every member is listed, a member with nothing at a known zero.
    assert by[scoped.users["outsider"]].total_usd == 0.0
    assert report.studies[scoped.studies["sibling"].study_id].name == "Acme pricing"
    # The aggregate equals the rows within USD 0.01.
    ledger = sum(session.scalars(select(AIUsageEventRow.cost_usd)))
    outside = 0.30
    total = sum(n.spend.total_usd for n in report.people)
    assert abs(total - (ledger + outside)) < 0.01


def test_a_runs_facts_are_its_own_whoever_they_are_booked_to(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    run_id, orphan = _spend_world(lead_repo, session, scoped)
    scope = lead_repo.scope

    def spend(run: str) -> tuple[float, float, int]:
        usage, holds = run_spend_facts(
            session, organization_id=scope.organization_id, study_id=scope.study_id, run_ids=[run]
        )
        s = run_spend(usage, holds)
        return s.total_usd, s.reserved_usd, s.uncertain_calls

    assert spend(run_id) == pytest.approx((0.40, 2.0, 0))
    # Booked to nobody, outside the ledger: still the run's own.
    assert spend(orphan) == pytest.approx((0.30, 0.0, 0))
    # Another study's run is not found through this study.
    sibling_run = session.scalars(
        select(WorkflowRunRow.run_id).where(WorkflowRunRow.idempotency_key == "spend-sibling")
    ).one()
    assert spend(sibling_run) == (0.0, 0.0, 0)


def test_a_page_of_runs_is_read_at_once_each_as_it_reads_alone(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    """The listings read every run's spend in one query; each run's is what it reads alone."""
    run_id, orphan = _spend_world(lead_repo, session, scoped)
    scope = lead_repo.scope
    runs = [run_id, orphan, "RUN-without-facts"]
    usage, holds = run_spend_facts(
        session, organization_id=scope.organization_id, study_id=scope.study_id, run_ids=runs
    )
    together = runs_spend(runs, usage, holds)
    for run in runs:
        alone = run_spend(
            *run_spend_facts(
                session,
                organization_id=scope.organization_id,
                study_id=scope.study_id,
                run_ids=[run],
            )
        )
        assert together[run] == alone
    assert together["RUN-without-facts"].known_usd == 0.0


def test_a_researcher_reads_only_themself_in_the_query(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    _spend_world(lead_repo, session, scoped)
    principal = scoped.principal(scoped.users["researcher"])
    mine = scoped.resolver.organization_context(principal)
    assert mine.may_administer is False
    repo = ResearcherSpendRepository(session, mine)
    since = datetime.now(UTC) - timedelta(days=40)
    # The rows themselves, before any fold: none of another person's or the unattributed.
    assert {f.charged_to for f in repo.usage(since=since)} == {scoped.users["researcher"]}
    assert {h.charged_to for h in repo.holds(since=since)} == {scoped.users["researcher"]}
    report = researcher_spend_report(session, mine, SpendPeriod.THIS_MONTH)
    assert report.everyone is False
    assert [n.person.user_id for n in report.people if n.person] == [scoped.users["researcher"]]
    assert all(n.person is not None for n in report.people)
    assert report.people[0].spend.total_usd == pytest.approx(0.25)


def test_last_month_holds_none_of_this_months_spend(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    _spend_world(lead_repo, session, scoped)
    report = researcher_spend_report(session, scoped.admin_context, SpendPeriod.LAST_MONTH)
    by = {n.person.user_id if n.person else None: n.spend for n in report.people}
    assert by[scoped.users["lead"]].total_usd == 0.0
    # An open hold is open now, whatever the period.
    assert by[scoped.users["lead"]].reserved_usd == pytest.approx(2.0)


# --------------------------------------------------------------------------- the migration


def test_the_backfill_takes_only_what_the_ledger_names(
    lead_repo: WorkflowRepository, session: Session, scoped: Any
) -> None:
    named = _run(lead_repo, session, scoped, "named")
    confirmer = WorkflowRepository(session, scoped.scope(user="researcher"))
    confirmer.record_spend_confirmation(named, ceiling_usd=1, limit_usd=1, confirmed_usd=1)
    started_only = _run(lead_repo, session, scoped, "started")
    card_job = _run(lead_repo, session, scoped, "card", workflow_type="research_agent")
    WorkflowRepository(session, scoped.scope(user="viewer")).record_lead_job_approval(
        started_only,
        turn_id="T",
        agent_run_id=card_job,
        design_revision_id="D",
        action="build",
        spend=None,
    )
    holds = [_hold(lead_repo, _claim(lead_repo, r)) for r in (named, started_only, card_job)]
    for hold in holds:
        session.add(
            AIUsageEventRow(
                event_id=new_usage_event_id(),
                call_id=f"b-{hold.reservation_id}",
                outcome="SUCCEEDED",
                purpose="PRIMARY",
                organization_id=lead_repo.scope.organization_id,
                client_id=lead_repo.scope.client_id,
                study_id=lead_repo.scope.study_id,
                actor_id="a",
                run_id=hold.run_id,
                reservation_id=hold.reservation_id,
                agent_id="a",
                agent_version="1",
                prompt_id="p",
                prompt_version="1",
                capability="FAST_EXTRACTION",
                policy_version="p",
                runtime_version="r",
                provider="anthropic",
                model="m",
                route_id="r",
                data_class="CLASS_C_INTERNAL",
                residency_zone="EU",
                cost_usd=0.1,
                cost_basis="METERED",
                occurred_at=datetime.now(UTC),
            )
        )
    session.flush()
    # As before the column: nothing booked.
    for hold in holds:
        hold.charged_to_user_id = None
    session.query(AIUsageEventRow).update({AIUsageEventRow.charged_to_user_id: None})
    session.flush()

    booked = _migration().backfill(session.connection())
    session.expire_all()
    people = {h.run_id: h.charged_to_user_id for h in session.scalars(select(BudgetReservationRow))}
    assert booked == 2
    assert people[named] == scoped.users["researcher"]  # the confirmation names them
    assert people[card_job] == scoped.users["viewer"]  # the card's comment names the job
    assert people[started_only] is None  # triggered_by is not the ledger: not inferred
    rows = {
        r.reservation_id: r.charged_to_user_id for r in session.scalars(select(AIUsageEventRow))
    }
    by_hold = {h.reservation_id: people[h.run_id] for h in holds}
    assert rows == by_hold
    assert (
        json.loads(
            session.scalars(
                select(ApprovalDecisionRow.comment).where(
                    ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_JOB_REQUEST
                )
            ).one()
        )["agent_run_id"]
        == card_job
    )


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("the migration's DDL round trip runs on PostgreSQL")
    return engine


def test_the_downgrade_drops_the_columns_and_the_upgrade_restores_them(postgres: Any) -> None:
    migration = _migration()

    def columns(connection: Any, table: str) -> set[str]:
        return {c["name"] for c in inspect(connection).get_columns(table)}

    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert "charged_to_user_id" not in columns(connection, "budget_reservations")
                assert "charged_to_user_id" not in columns(connection, "ai_usage_events")
                migration.upgrade()
            assert "charged_to_user_id" in columns(connection, "budget_reservations")
            assert "charged_to_user_id" in columns(connection, "ai_usage_events")
        finally:
            transaction.rollback()  # PostgreSQL DDL is transactional


def test_a_total_with_an_unknown_call_is_not_a_known_cost() -> None:
    """F-R10: ``known_usd`` is the total only while no call's outcome is unknown, never a total
    read as the cost with one left out."""
    assert ActivitySpend(model_usd=0.4, outside_ledger_usd=0.25).known_usd == pytest.approx(0.65)
    assert ActivitySpend().known_usd == 0.0  # nothing spent is known, not unknown (OI-4)
    assert ActivitySpend(model_usd=0.4, uncertain_calls=1).known_usd is None
