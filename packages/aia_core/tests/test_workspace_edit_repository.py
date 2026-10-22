"""The working copy's operation log, stored (working-copy-edit-ops WCE2b, M1)."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.design_items import Documents
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy, whole_copy_rows
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.tables import WorkspaceEditOpRow
from aia_core.infrastructure.workspace_edit_repository import WorkspaceEditRepository

MIGRATION = next(
    (Path(__file__).resolve().parents[3] / "migrations" / "versions").glob(
        "*_the_working_copy_operation_log.py"
    )
)


def _rows(by: WriteBy, *, base: int | None, result: int, batch: str = "B1") -> tuple:
    return whole_copy_rows(
        Documents(content={"title": "a", "n": 100}),
        Documents(content={"title": "b", "n": 200}),
        reason="autosave",
        by=by,
        batch_id=batch,
        base_revision=base,
        result_revision=result,
    )


def test_a_logged_write_reads_back_as_it_was_logged(scoped: Any, session: Session) -> None:
    scope = scoped.scope(user="lead")
    repo = WorkspaceEditRepository(session, scope)
    by = WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI)
    first, second = _rows(by, base=1, result=2), _rows(by, base=2, result=3, batch="B2")
    repo.append(first)
    repo.append(second)
    assert repo.rows() == [*first, *second]
    assert repo.rows(after_revision=2) == list(second)
    assert [(r.item_key, r.field) for r in second] == [
        ("content:brief:title", "text"),
        ("content:n:", "value"),
    ]


def test_another_studys_log_is_never_read(scoped: Any, session: Session) -> None:
    scope = scoped.scope(user="lead")
    WorkspaceEditRepository(session, scope).append(
        _rows(WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI), base=None, result=1)
    )
    for study in ("sibling", "other_client"):
        other = scoped.scope(user="other_lead" if study == "other_client" else "lead", study=study)
        assert WorkspaceEditRepository(session, other).rows() == []


def test_only_a_writer_of_the_copy_logs(scoped: Any, session: Session) -> None:
    scope = scoped.scope(user="lead")
    reader = dataclasses.replace(scope, permissions=frozenset())
    with pytest.raises(ScopeDenied):
        WorkspaceEditRepository(session, reader).append(
            _rows(WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI), base=None, result=1)
        )


def test_a_logged_change_is_never_rewritten(scoped: Any, session: Session) -> None:
    scope = scoped.scope(user="lead")
    WorkspaceEditRepository(session, scope).append(
        _rows(WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI), base=None, result=1)
    )
    row = session.query(WorkspaceEditOpRow).first()
    assert row is not None
    row.field = "other"
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()


def test_the_database_refuses_a_persons_write_without_its_author(
    scoped: Any, session: Session
) -> None:
    """WriteBy refuses it in code; the table refuses it too, so no writer can skip the rule. A
    revision migrated from 18.6.6 is the one write logged without its author."""
    scope = scoped.scope(user="lead")
    repo = WorkspaceEditRepository(session, scope)
    repo.append(_rows(WriteBy(ActorKind.PERSON, None, OpSource.MIGRATION), base=None, result=1))
    assert {r.by.actor_user_id for r in repo.rows()} == {None}
    session.add(
        WorkspaceEditOpRow(
            op_id="EOP-" + "0" * 32,
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            study_id=scope.study_id,
            batch_id="B",
            base_revision=None,
            result_revision=2,
            actor_kind="person",
            actor_user_id=None,
            source="ui",
            item_key="content:copy:",
            field="value",
            op={"op": "whole_copy", "reason": "autosave"},
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# --------------------------------------------------------------------------- the migration


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("the_working_copy_operation_log", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("the migration chain runs on PostgreSQL")
    return engine


def test_the_downgrade_refuses_while_the_log_holds_a_change(
    postgres: Any, session: Session, scoped: Any
) -> None:
    scope = scoped.scope(user="lead")
    WorkspaceEditRepository(session, scope).append(
        _rows(WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI), base=None, result=1)
    )
    session.commit()
    with postgres.connect() as connection:
        transaction = connection.begin()
        try:
            with (
                Operations.context(MigrationContext.configure(connection)),
                pytest.raises(RuntimeError, match="insert-once"),
            ):
                _migration().downgrade()
        finally:
            transaction.rollback()
