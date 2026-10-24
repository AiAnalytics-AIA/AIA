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

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session

from ..domain.report.editor import MAX_PAGES_PER_SESSION, EditMark, LineHead
from ..domain.scope import StudyContext
from .tables import (
    OrganizationMemberRow,
    ProjectArtifactRow,
    ReportEditorEditRow,
    ReportEditorSessionRow,
    ReportEditorVersionRow,
    UserRow,
    as_utc,
)

__all__ = [
    "EditorSession",
    "EditorVersion",
    "ReportEditorRepository",
    "TooManyPages",
    "session_by_key",
]


class TooManyPages(Exception):
    """A session already keeps edit reports for its most pages (RPT8f)."""


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
    #: What the latest save of these bytes said the version holds (RPT8f); ``None`` when none said.
    content_at: datetime | None = None
    last_saved_at: datetime | None = None


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
    last_problem: str | None = None
    last_problem_at: datetime | None = None


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
        content_at=as_utc(row.content_at) if row.content_at is not None else None,
        last_saved_at=as_utc(row.last_saved_at) if row.last_saved_at is not None else None,
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
        last_problem=row.last_problem,
        last_problem_at=as_utc(row.last_problem_at) if row.last_problem_at is not None else None,
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

    def lock_line(self, line_id: str) -> None:
        """Hold ``line_id``'s composed artifact row for the caller's transaction (PostgreSQL;
        SQLite has one writer): it exists before the line's first version does, so two first
        opens of one line take their turn instead of both inserting koncept 1. The caller
        found the artifact through the Study's own research artifacts."""
        self._session.execute(
            select(ProjectArtifactRow.artifact_id)
            .where(ProjectArtifactRow.artifact_id == line_id)
            .with_for_update()
        )

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

    def approved_edits(
        self, *, run_id: str, variant: str, deep_research_run_id: str | None
    ) -> list[EditorVersion]:
        """The versions a person saved (koncept 2 on) of the run's lines of ``variant`` whose
        artifact a person approved: one query, whatever the length of the line's history."""
        rows = self._session.scalars(
            select(ReportEditorVersionRow)
            .join(
                ProjectArtifactRow,
                ProjectArtifactRow.artifact_id == ReportEditorVersionRow.artifact_id,
            )
            .where(
                *self._versions_in_scope(),
                ReportEditorVersionRow.run_id == run_id,
                ReportEditorVersionRow.variant == variant,
                ReportEditorVersionRow.deep_research_run_id.is_(None)
                if deep_research_run_id is None
                else ReportEditorVersionRow.deep_research_run_id == deep_research_run_id,
                ReportEditorVersionRow.koncept > 1,
                ProjectArtifactRow.is_approved.is_(True),
            )
            .order_by(ReportEditorVersionRow.saved_at, ReportEditorVersionRow.koncept)
        )
        return [_version(r) for r in rows]

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
        content_at: datetime | None = None,
        last_saved_at: datetime | None = None,
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
            content_at=content_at,
            last_saved_at=last_saved_at,
        )
        self._session.add(row)
        self._session.flush()
        return _version(row)

    def cover(self, artifact_id: str, *, saved_at: datetime, content_at: datetime | None) -> None:
        """A later save held exactly ``artifact_id``'s bytes: AIA received it at ``saved_at``, its
        last change at ``content_at``. The version holds what that save holds too; never moved
        back."""
        row = self._session.scalar(
            select(ReportEditorVersionRow).where(
                *self._versions_in_scope(), ReportEditorVersionRow.artifact_id == artifact_id
            )
        )
        if row is None:
            raise LookupError(artifact_id)
        if row.last_saved_at is None or as_utc(row.last_saved_at) < saved_at:
            row.last_saved_at = saved_at
        if content_at is not None and (
            row.content_at is None or as_utc(row.content_at) < content_at
        ):
            row.content_at = content_at
        self._session.flush()

    def display_name(self) -> str:
        """The caller's name as the editor shows it to co-editors: their display name, never
        their e-mail; empty when none is recorded."""
        row = self._session.get(UserRow, self._scope.actor_id)
        name = (row.display_name if row is not None else "") or ""
        return "" if "@" in name else name

    def names(self, user_ids: Sequence[str]) -> dict[str, str]:
        """Each of ``user_ids`` who is a member of the organization in scope, by display name,
        never an e-mail; a person with neither is left out (the pane says "Člen týmu")."""
        if not user_ids:
            return {}
        rows = self._session.execute(
            select(UserRow.user_id, UserRow.display_name)
            .join(OrganizationMemberRow, OrganizationMemberRow.user_id == UserRow.user_id)
            .where(
                OrganizationMemberRow.organization_id == self._scope.organization_id,
                UserRow.user_id.in_(list(user_ids)),
            )
        )
        return {uid: name for uid, name in rows if name and "@" not in name}

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

    def note_problem(self, document_key: str, *, now: datetime, problem: str | None) -> None:
        """Why the session's newest save was not stored, or ``None`` once one is."""
        self._session.execute(
            update(ReportEditorSessionRow)
            .where(*self._sessions_in_scope(), ReportEditorSessionRow.document_key == document_key)
            .values(last_problem=problem, last_problem_at=now if problem else None)
        )
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

    # -- edit starts ---------------------------------------------------------

    def record_edit(
        self, document_key: str, *, page: str, seq: int, clean: bool, now: datetime
    ) -> None:
        """``page``'s report in the session, received ``now``: edit start ``seq``, or with
        ``clean`` that its edits up to ``seq`` reached the Document Server. Each keeps the page's
        highest, so a report that arrives late or twice changes nothing. The session's row is
        locked first, so two reports of one session take their turn (PostgreSQL);
        :class:`TooManyPages` for a new page beyond :data:`MAX_PAGES_PER_SESSION`."""
        self._session.execute(
            select(ReportEditorSessionRow.document_key)
            .where(*self._sessions_in_scope(), ReportEditorSessionRow.document_key == document_key)
            .with_for_update()
        )
        in_scope = (
            ReportEditorEditRow.organization_id == self._scope.organization_id,
            ReportEditorEditRow.client_id == self._scope.client_id,
            ReportEditorEditRow.study_id == self._scope.study_id,
            ReportEditorEditRow.document_key == document_key,
        )
        row = self._session.scalar(
            select(ReportEditorEditRow).where(*in_scope, ReportEditorEditRow.page == page)
        )
        if row is None:
            pages = self._session.scalar(
                select(func.count()).select_from(ReportEditorEditRow).where(*in_scope)
            )
            if (pages or 0) >= MAX_PAGES_PER_SESSION:
                raise TooManyPages(document_key)
            s = self._scope
            row = ReportEditorEditRow(
                document_key=document_key,
                page=page,
                organization_id=s.organization_id,
                client_id=s.client_id,
                study_id=s.study_id,
                user_id=s.actor_id,
                seq=0,
                received_at=now,
                clean_seq=0,
            )
            self._session.add(row)
        if clean:
            if seq > (row.clean_seq or 0):
                row.clean_seq, row.clean_at = seq, now
        elif seq > row.seq:
            row.seq, row.received_at = seq, now
        self._session.flush()

    def edit_marks(self, line_id: str, *, also: str | None = None) -> list[EditMark]:
        """The edit starts of ``line_id``'s open session, and of the session ``also`` names
        when it is the line's (the approving page's, closed or not)."""
        open_or_named: ColumnElement[bool] = ReportEditorSessionRow.closed_at.is_(None)
        if also is not None:
            open_or_named = open_or_named | (ReportEditorSessionRow.document_key == also)
        rows = self._session.scalars(
            select(ReportEditorEditRow)
            .join(
                ReportEditorSessionRow,
                ReportEditorSessionRow.document_key == ReportEditorEditRow.document_key,
            )
            .where(
                *self._sessions_in_scope(),
                ReportEditorSessionRow.line_id == line_id,
                open_or_named,
            )
        )
        return [
            EditMark(
                r.document_key,
                r.page,
                r.seq,
                as_utc(r.received_at),
                r.clean_seq,
                as_utc(r.clean_at) if r.clean_at is not None else None,
            )
            for r in rows
        ]
