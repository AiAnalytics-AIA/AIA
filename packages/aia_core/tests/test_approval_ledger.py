"""The approval ledger's closed set of subjects, and migration M3 (lead-orchestration LO16).

The domain names every subject once (``domain/approval_ledger.py``); the table's CHECK is built
from it; migration 5054d4d610c2 admits the MVP lane's seven subjects literally; a study reads its
own decisions through ``WorkflowRepository.ledger`` and nobody else's.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.approval_ledger import (
    LANE_M3_SUBJECTS,
    SUBJECTS,
    ApprovalSubject,
    LedgerEntry,
    subject_check_sql,
)
from aia_core.infrastructure.tables import ApprovalDecisionRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

REPO = Path(__file__).resolve().parents[3]
MIGRATION = (
    REPO / "migrations/versions/20261020_5054d4d610c2_the_approval_ledger_admits_the_mvp_lane_.py"
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ledger_admits_the_mvp_lane", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- the closed set


def test_every_subject_is_listed_once_and_says_who_writes_it() -> None:
    listed = [s.subject for s in SUBJECTS]
    assert sorted(listed) == sorted(ApprovalSubject)
    assert len(listed) == len(set(listed))
    assert all(s.subject_id and s.written_by for s in SUBJECTS)


def test_the_lane_admits_exactly_the_seven_subjects_lo16_names() -> None:
    assert {s.value for s in LANE_M3_SUBJECTS} == {
        "wallet",
        "lead_plan",
        "plan_step",
        "chat_start",
        "data_contract",
        "map_snapshot",
        "sociomap_unlock",
    }


def test_the_table_checks_exactly_the_domain_subjects() -> None:
    checks = [
        c
        for c in ApprovalDecisionRow.__table__.constraints
        if isinstance(c, CheckConstraint) and str(c.name).endswith("approval_subject_type_known")
    ]
    assert len(checks) == 1
    assert str(checks[0].sqltext) == subject_check_sql()
    assert subject_check_sql([ApprovalSubject.SPEND, ApprovalSubject.GATE]) == (
        "subject_type in ('gate','spend')"
    )


def test_the_migration_names_the_same_subjects_in_the_same_order() -> None:
    """Written out in the migration, never imported: it must still be the domain's set."""
    migration = _migration()
    written = migration._BEFORE + migration._ADDED
    assert written == tuple(s.subject.value for s in SUBJECTS)
    assert set(migration._ADDED) == {s.value for s in LANE_M3_SUBJECTS}
    assert migration.down_revision == "57eaa96a5538"


# --------------------------------------------------------------------------- rows and reads


def _row(scope: Any, subject: str, subject_id: str = "S-1", **extra: Any) -> ApprovalDecisionRow:
    return ApprovalDecisionRow(
        organization_id=extra.pop("organization_id", scope.organization_id),
        client_id=extra.pop("client_id", scope.client_id),
        study_id=extra.pop("study_id", scope.study_id),
        subject_type=subject,
        subject_id=subject_id,
        approver_user_id=scope.actor_id,
        decision="approve",
        **extra,
    )


def test_every_subject_round_trips_through_the_study_ledger(session: Session, scoped: Any) -> None:
    scope = scoped.scope()
    for spec in SUBJECTS:
        session.add(_row(scope, spec.subject.value, f"{spec.subject.value}-1"))
    session.flush()

    entries = WorkflowRepository(session, scope).ledger()
    assert [e.subject for e in entries] == [s.subject for s in SUBJECTS]
    assert all(isinstance(e, LedgerEntry) for e in entries)
    wallet = next(e for e in entries if e.subject is ApprovalSubject.WALLET)
    assert (wallet.subject_id, wallet.decision, wallet.approver_user_id) == (
        "wallet-1",
        "approve",
        scope.actor_id,
    )
    assert wallet.created_at.tzinfo is not None

    lane = WorkflowRepository(session, scope).ledger(LANE_M3_SUBJECTS)
    assert {e.subject for e in lane} == set(LANE_M3_SUBJECTS)
    assert WorkflowRepository(session, scope).ledger(()) == []


def test_a_subject_outside_the_set_is_refused_by_the_table(session: Session, scoped: Any) -> None:
    session.add(_row(scoped.scope(), "qc_decision"))
    with pytest.raises(IntegrityError, match="approval_subject_type_known"):
        session.flush()


def test_a_study_reads_only_its_own_decisions(session: Session, scoped: Any) -> None:
    """The isolation predicate: organization, client and study, all three."""
    primary = scoped.scope(study="primary")
    sibling = scoped.scope(study="sibling")
    other = scoped.scope(user="other_lead", study="other_client")
    session.add(_row(primary, "wallet", "mine"))
    session.add(_row(sibling, "wallet", "sibling"))
    session.add(_row(other, "wallet", "other-client"))
    # A row carrying this study's id under another organization's columns is not this study's.
    session.add(_row(primary, "wallet", "forged", organization_id="ORG-elsewhere"))
    session.flush()

    assert [e.subject_id for e in WorkflowRepository(session, primary).ledger()] == ["mine"]
    assert [e.subject_id for e in WorkflowRepository(session, sibling).ledger()] == ["sibling"]
    assert [e.subject_id for e in WorkflowRepository(session, other).ledger()] == ["other-client"]


# --------------------------------------------------------------------------- the migration


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("the migration alters a CHECK constraint, which SQLite cannot outside a batch")
    return engine


def _subjects_admitted(connection: Any) -> str:
    return str(
        connection.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_approval_decisions_approval_subject_type_known'"
            )
        ).scalar_one()
    )


def test_the_upgrade_admits_the_lane_and_the_downgrade_takes_it_back(
    postgres: Any,
) -> None:
    migration = _migration()
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
                assert "'wallet'" not in _subjects_admitted(connection)
                assert "'lead_self_update'" in _subjects_admitted(connection)
                migration.upgrade()
            admitted = _subjects_admitted(connection)
            assert all(f"'{s.value}'" in admitted for s in ApprovalSubject)
        finally:
            transaction.rollback()  # PostgreSQL DDL is transactional: the schema is as it was


def test_the_downgrade_refuses_while_the_ledger_holds_a_lane_decision(
    postgres: Any, session: Session, scoped: Any
) -> None:
    session.add(_row(scoped.scope(), "sociomap_unlock"))
    session.commit()
    migration = _migration()
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with (
                Operations.context(MigrationContext.configure(connection)),
                pytest.raises(RuntimeError, match="append-only"),
            ):
                migration.downgrade()
        finally:
            transaction.rollback()


# ------------------------------------------- the warnings column's downgrade (3abba24ff47c)

WARNINGS_MIGRATION = REPO / "migrations/versions/20261024_3abba24ff47c_approval_warnings.py"


def _downgrade_warnings(engine: Any) -> None:
    spec = importlib.util.spec_from_file_location("approval_warnings", WARNINGS_MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Operations.context(MigrationContext.configure(connection)):
                module.downgrade()
        finally:
            transaction.rollback()  # PostgreSQL DDL is transactional: the schema is as it was


def test_an_approval_that_recorded_no_warning_does_not_hold_the_downgrade(
    postgres: Any, session: Session, scoped: Any
) -> None:
    """[] is a check that found nothing (RD7): nothing the downgrade would erase."""
    session.add(_row(scoped.scope(), "artifact", warnings=[]))
    session.add(_row(scoped.scope(), "artifact", subject_id="S-2"))  # NULL: nothing checked
    session.commit()
    _downgrade_warnings(postgres)


def test_an_approval_that_recorded_a_warning_holds_the_downgrade(
    postgres: Any, session: Session, scoped: Any
) -> None:
    warning = {"code": "unsupported_comparison", "where": "ch-a.1", "message": "srovnání"}
    session.add(_row(scoped.scope(), "artifact", warnings=[warning]))
    session.add(_row(scoped.scope(), "artifact", subject_id="S-2", warnings=[]))
    session.commit()
    with pytest.raises(RuntimeError, match="1 approval"):
        _downgrade_warnings(postgres)
