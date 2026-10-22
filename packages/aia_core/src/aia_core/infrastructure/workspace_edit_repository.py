"""The working copy's operation log, one Study's (ADR 0029 decision 3, M1).

The only reader and writer of ``workspace_edit_ops`` (``make layer_check``). Every method takes
the issued :class:`~aia_core.domain.scope.StudyContext` it was built with and filters by all three
scope columns. The log is insert-once: a row is never rewritten. ``apply_edit_ops`` (WCE2c) is its
one writer, inside the transaction that writes the working revision the rows name.

The caller owns the transaction.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.edit_log import ActorKind, EditLogRow, OpSource, WriteBy
from ..domain.scope import Permission, StudyContext
from .tables import WorkspaceEditOpRow

__all__ = ["WorkspaceEditRepository"]


def _to_domain(row: WorkspaceEditOpRow) -> EditLogRow:
    return EditLogRow(
        op_id=row.op_id,
        batch_id=row.batch_id,
        base_revision=row.base_revision,
        result_revision=row.result_revision,
        by=WriteBy(
            actor_kind=ActorKind(row.actor_kind),
            actor_user_id=row.actor_user_id,
            source=OpSource(row.source),
            source_ref=row.source_ref,
        ),
        item_key=row.item_key,
        field=row.field,
        op=dict(row.op),
        inverse=dict(row.inverse) if row.inverse is not None else None,
    )


class WorkspaceEditRepository:
    """The logged changes of the working copy of the Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("WorkspaceEditRepository needs an issued StudyContext")
        self._session = session
        self._scope = scope

    def _study(self) -> tuple[Any, ...]:
        s = self._scope
        return (
            WorkspaceEditOpRow.organization_id == s.organization_id,
            WorkspaceEditOpRow.client_id == s.client_id,
            WorkspaceEditOpRow.study_id == s.study_id,
        )

    def append(self, rows: Sequence[EditLogRow]) -> None:
        """Log ``rows`` against the Study in scope. Needs ``EDIT_STUDY``: only a writer of the
        working copy logs, and only the one it wrote."""
        self._scope.require(Permission.EDIT_STUDY)
        s = self._scope
        for row in rows:
            self._session.add(
                WorkspaceEditOpRow(
                    op_id=row.op_id,
                    organization_id=s.organization_id,
                    client_id=s.client_id,
                    study_id=s.study_id,
                    batch_id=row.batch_id,
                    base_revision=row.base_revision,
                    result_revision=row.result_revision,
                    actor_kind=row.by.actor_kind.value,
                    actor_user_id=row.by.actor_user_id,
                    source=row.by.source.value,
                    source_ref=row.by.source_ref,
                    item_key=row.item_key,
                    field=row.field,
                    op=dict(row.op),
                    inverse=dict(row.inverse) if row.inverse is not None else None,
                )
            )
        self._session.flush()

    def rows(self, *, after_revision: int = 0) -> list[EditLogRow]:
        """The changes logged after working revision ``after_revision``, in the order of the
        revisions they wrote, then by item and field."""
        found = self._session.scalars(
            select(WorkspaceEditOpRow)
            .where(*self._study(), WorkspaceEditOpRow.result_revision > after_revision)
            .order_by(
                WorkspaceEditOpRow.result_revision,
                WorkspaceEditOpRow.item_key,
                WorkspaceEditOpRow.field,
                WorkspaceEditOpRow.op_id,
            )
        ).all()
        return [_to_domain(r) for r in found]
