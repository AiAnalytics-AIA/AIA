"""The report editor's lines, versions and sessions (artifact-report RPT8c).

The only reader and writer of ``report_editor_versions`` and ``report_editor_sessions``. Every
method takes the issued :class:`~aia_core.domain.scope.StudyContext` it was built with and filters
by all three scope columns. The one read without a scope is :func:`session_by_key`: a callback
from the Document Server carries no person's session, only the document key its JWT signs, and
the key names whose study it is, so the caller can resolve that scope before anything else.

The caller owns the transaction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..domain.report.editor import LineHead
from ..domain.scope import StudyContext
from .tables import ReportEditorSessionRow, ReportEditorVersionRow, as_utc

__all__ = [
    "EditorSession",
    "EditorVersion",
    "ReportEditorRepository",
    "session_by_key",
]


@dataclass(frozen=True)
class EditorVersion:
    artifact_id: str
    line_id: str
    koncept: int
    run_id: str
    variant: str
    deep_research_run_id: str | None
    sha256: str
    changes_artifact_id: str | None
    authors: tuple[str, ...]
    saved_at: datetime


@dataclass(frozen=True)
class EditorSession:
    document_key: str
    line_id: str
    session_no: int
    version_artifact_id: str
    organization_id: str
    study_id: str
    run_id: str
    users: tuple[str, ...]
    opened_by: str
    opened_at: datetime
    last_seen_at: datetime
    closed_at: datetime | None
    closed_reason: str | None


def _version(row: ReportEditorVersionRow) -> EditorVersion:
    return EditorVersion(
        artifact_id=row.artifact_id,
        line_id=row.line_id,
        koncept=row.koncept,
        run_id=row.run_id,
        variant=row.variant,
        deep_research_run_id=row.deep_research_run_id,
        sha256=row.sha256,
        changes_artifact_id=row.changes_artifact_id,
        authors=tuple(row.authors or ()),
        saved_at=as_utc(row.saved_at),
    )


def _session(row: ReportEditorSessionRow) -> EditorSession:
    return EditorSession(
        document_key=row.document_key,
        line_id=row.line_id,
        session_no=row.session_no,
        version_artifact_id=row.version_artifact_id,
        organization_id=row.organization_id,
        study_id=row.study_id,
        run_id=row.run_id,
        users=tuple(row.users or ()),
        opened_by=row.opened_by,
        opened_at=as_utc(row.opened_at),
        last_seen_at=as_utc(row.last_seen_at),
        closed_at=as_utc(row.closed_at) if row.closed_at is not None else None,
        closed_reason=row.closed_reason,
    )


def session_by_key(session: Session, document_key: str) -> EditorSession | None:
    """The session ``document_key`` names, whoever's it is: for a callback, which carries no
    person's session, to learn whose study to resolve a scope for. Nothing else reads it."""
    row = session.get(ReportEditorSessionRow, document_key)
    return _session(row) if row is not None else None


class ReportEditorRepository:
    """The editor's lines, versions and sessions in the Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("ReportEditorRepository needs an issued StudyContext")
        self._session = session
        self._scope = scope

    def _versions_in_scope(self) -> tuple[Any, ...]:
        s = self._scope
        return (
            ReportEditorVersionRow.organization_id == s.organization_id,
            ReportEditorVersionRow.client_id == s.client_id,
            ReportEditorVersionRow.study_id == s.study_id,
        )

    def _sessions_in_scope(self) -> tuple[Any, ...]:
        s = self._scope
        return (
            ReportEditorSessionRow.organization_id == s.organization_id,
            ReportEditorSessionRow.client_id == s.client_id,
            ReportEditorSessionRow.study_id == s.study_id,
        )

    # -- versions ------------------------------------------------------------

    def versions(self, line_id: str, *, for_update: bool = False) -> list[EditorVersion]:
        """``line_id``'s versions, koncept 1 first; with ``for_update`` its rows are locked, so
        two writers on one line take their turn (PostgreSQL; SQLite has one writer)."""
        query = (
            select(ReportEditorVersionRow)
            .where(*self._versions_in_scope(), ReportEditorVersionRow.line_id == line_id)
            .order_by(ReportEditorVersionRow.koncept)
        )
        if for_update:
            query = query.with_for_update()
        return [_version(r) for r in self._session.scalars(query)]

    def version(self, artifact_id: str) -> EditorVersion | None:
        row = self._session.scalar(
            select(ReportEditorVersionRow).where(
                *self._versions_in_scope(), ReportEditorVersionRow.artifact_id == artifact_id
            )
        )
        return _version(row) if row is not None else None

    def heads(
        self, *, run_id: str, variant: str, deep_research_run_id: str | None
    ) -> list[LineHead]:
        """Every line of the run and variant, each with its newest version."""
        newest = (
            select(
                ReportEditorVersionRow.line_id,
                func.max(ReportEditorVersionRow.koncept).label("koncept"),
            )
            .where(
                *self._versions_in_scope(),
                ReportEditorVersionRow.run_id == run_id,
                ReportEditorVersionRow.variant == variant,
                ReportEditorVersionRow.deep_research_run_id.is_(None)
                if deep_research_run_id is None
                else ReportEditorVersionRow.deep_research_run_id == deep_research_run_id,
            )
            .group_by(ReportEditorVersionRow.line_id)
            .subquery()
        )
        rows = self._session.scalars(
            select(ReportEditorVersionRow).join(
                newest,
                (ReportEditorVersionRow.line_id == newest.c.line_id)
                & (ReportEditorVersionRow.koncept == newest.c.koncept),
            )
        )
        return [LineHead(r.line_id, r.koncept, r.artifact_id, as_utc(r.saved_at)) for r in rows]

    def add_version(
        self,
        *,
        artifact_id: str,
        line_id: str,
        koncept: int,
        run_id: str,
        variant: str,
        deep_research_run_id: str | None,
        sha256: str,
        saved_at: datetime,
        authors: Sequence[str] = (),
        changes_artifact_id: str | None = None,
    ) -> EditorVersion:
        s = self._scope
        row = ReportEditorVersionRow(
            artifact_id=artifact_id,
            line_id=line_id,
            koncept=koncept,
            organization_id=s.organization_id,
            client_id=s.client_id,
            study_id=s.study_id,
            run_id=run_id,
            variant=variant,
            deep_research_run_id=deep_research_run_id,
            sha256=sha256,
            changes_artifact_id=changes_artifact_id,
            authors=list(authors),
            saved_at=saved_at,
        )
        self._session.add(row)
        self._session.flush()
        return _version(row)

    # -- sessions ------------------------------------------------------------

    def open_session(self, line_id: str) -> EditorSession | None:
        """``line_id``'s session that is not closed, if one is."""
        row = self._session.scalar(
            select(ReportEditorSessionRow).where(
                *self._sessions_in_scope(),
                ReportEditorSessionRow.line_id == line_id,
                ReportEditorSessionRow.closed_at.is_(None),
            )
        )
        return _session(row) if row is not None else None

    def session(self, document_key: str) -> EditorSession | None:
        row = self._session.scalar(
            select(ReportEditorSessionRow).where(
                *self._sessions_in_scope(), ReportEditorSessionRow.document_key == document_key
            )
        )
        return _session(row) if row is not None else None

    def last_session_no(self, line_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.max(ReportEditorSessionRow.session_no)).where(
                    *self._sessions_in_scope(), ReportEditorSessionRow.line_id == line_id
                )
            )
            or 0
        )

    def start_session(
        self,
        *,
        document_key: str,
        line_id: str,
        session_no: int,
        version_artifact_id: str,
        run_id: str,
        now: datetime,
    ) -> EditorSession:
        s = self._scope
        row = ReportEditorSessionRow(
            document_key=document_key,
            line_id=line_id,
            session_no=session_no,
            version_artifact_id=version_artifact_id,
            organization_id=s.organization_id,
            client_id=s.client_id,
            study_id=s.study_id,
            run_id=run_id,
            users=[s.actor_id],
            opened_by=s.actor_id,
            opened_at=now,
            last_seen_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return _session(row)

    def touch(self, document_key: str, *, now: datetime, user_id: str | None = None) -> None:
        """A config signed or a callback received for the session: it is in use. ``user_id``,
        when given, may now be named an author."""
        row = self._session.scalar(
            select(ReportEditorSessionRow).where(
                *self._sessions_in_scope(), ReportEditorSessionRow.document_key == document_key
            )
        )
        if row is None:
            raise LookupError(document_key)
        row.last_seen_at = now
        if user_id is not None and user_id not in (row.users or []):
            row.users = [*(row.users or []), user_id]
        self._session.flush()

    def close(self, document_key: str, *, now: datetime, reason: str) -> None:
        self._session.execute(
            update(ReportEditorSessionRow)
            .where(
                *self._sessions_in_scope(),
                ReportEditorSessionRow.document_key == document_key,
                ReportEditorSessionRow.closed_at.is_(None),
            )
            .values(closed_at=now, closed_reason=reason)
        )
        self._session.flush()
