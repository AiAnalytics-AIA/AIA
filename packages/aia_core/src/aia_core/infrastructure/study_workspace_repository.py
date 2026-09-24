"""Persistence for the study workspace bridge (ADR 0015 decision 5, OI-58).

Every method takes an issued scope. There is deliberately no method that finds a
study from a unit project id: the unit id is data the study's scope yields, never
an input that yields a scope.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.scope import ClientContext, Permission, StudyContext
from ..domain.workspace import STAGE_KEYS, UNIT_PROJECT_ID, StudyWorkspace
from .tables import StudyWorkspaceRow, as_utc

__all__ = ["StudyWorkspaceRepository", "WorkspaceConflict"]


class WorkspaceConflict(Exception):
    """The binding cannot be written: the study is bound elsewhere, or the unit project is."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def _to_domain(row: StudyWorkspaceRow) -> StudyWorkspace:
    return StudyWorkspace(
        study_id=row.study_id,
        unit_project_id=row.unit_project_id,
        last_stage=row.last_stage,
        bound_at=as_utc(row.bound_at),
        modified_at=as_utc(row.modified_at),
    )


class StudyWorkspaceRepository:
    """Reads and writes study workspaces. The caller owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _row(self, scope: StudyContext) -> StudyWorkspaceRow | None:
        # All three scope columns, as every client-data predicate (ADR 0004).
        return self._session.scalar(
            select(StudyWorkspaceRow).where(
                StudyWorkspaceRow.study_id == scope.study_id,
                StudyWorkspaceRow.client_id == scope.client_id,
                StudyWorkspaceRow.organization_id == scope.organization_id,
            )
        )

    def get(self, scope: StudyContext) -> StudyWorkspace | None:
        """The workspace of the study in scope, or ``None`` when nothing is bound yet."""
        row = self._row(scope)
        return _to_domain(row) if row else None

    def bind(self, scope: StudyContext, *, unit_project_id: str) -> StudyWorkspace:
        """Bind the study in scope to the unit project holding its working content.

        Written once: binding the same unit project again is a no-op, a different
        one is a conflict, and so is a unit project already bound to any other
        study. Needs ``EDIT_STUDY`` on the study, and an open study.
        """
        scope.require(Permission.EDIT_STUDY)
        scope.require_open_study()
        if not UNIT_PROJECT_ID.fullmatch(unit_project_id):
            raise ValueError("not a unit project id")
        existing = self._row(scope)
        if existing is not None:
            if existing.unit_project_id == unit_project_id:
                return _to_domain(existing)
            raise WorkspaceConflict("study already bound", reason="study_already_bound")
        taken = self._session.scalar(
            select(StudyWorkspaceRow.study_id).where(
                StudyWorkspaceRow.unit_project_id == unit_project_id
            )
        )
        if taken is not None:
            # Not which study: that would disclose another engagement.
            raise WorkspaceConflict("unit project already bound", reason="unit_project_taken")
        row = StudyWorkspaceRow(
            study_id=scope.study_id,
            organization_id=scope.organization_id,
            client_id=scope.client_id,
            unit_project_id=unit_project_id,
            bound_by=scope.actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def record_stage(self, scope: StudyContext, *, stage: str) -> StudyWorkspace | None:
        """Remember the stage the study was opened on.

        A no-op without a binding or without ``EDIT_STUDY``.
        """
        if stage not in STAGE_KEYS:
            raise ValueError("unknown stage")
        if not scope.has(Permission.EDIT_STUDY):
            return self.get(scope)
        row = self._row(scope)
        if row is None:
            return None
        if row.last_stage != stage:
            row.last_stage = stage
            self._session.flush()
        return _to_domain(row)

    def in_client(self, scope: ClientContext) -> dict[str, StudyWorkspace]:
        """The workspaces of the studies the client scope may open, keyed by study id."""
        if not scope.study_ids:
            return {}
        rows = self._session.scalars(
            select(StudyWorkspaceRow).where(
                StudyWorkspaceRow.organization_id == scope.organization_id,
                StudyWorkspaceRow.client_id == scope.client_id,
                StudyWorkspaceRow.study_id.in_(sorted(scope.study_ids)),
            )
        ).all()
        return {r.study_id: _to_domain(r) for r in rows}
