"""Opening a run's report in the editor: which line, which version, which session (RPT8c).

A run's report is edited as a **line**: koncept 1 is a draft code composed, each save its next
version (``domain/report/editor.py``). :meth:`ReportEditor.open` starts the current
composition's line if it has none, picks the line to open (the one asked for, else the one with
the newest version), and gives the editing session's document key: the open session's, so a
second researcher joins it, else a new one on the line's newest version. The routes that sign a
config and take the Document Server's callbacks are the API's; the save itself is stored by the
callback's chunk.

The client report is never a line: it opens nowhere (:class:`NotEditable`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from aia_core.application.contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.domain.report.editor import (
    EDITABLE_VARIANTS,
    LineHead,
    SessionState,
    default_line,
    document_key,
    reuse_session,
)
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactStatus
from aia_core.infrastructure.report_editor_repository import (
    EditorSession,
    EditorVersion,
    ReportEditorRepository,
    session_by_key,
)

__all__ = [
    "EditorSession",
    "EditorVersion",
    "LineNotFound",
    "NotEditable",
    "OpenedLine",
    "ReportEditor",
    "session_by_key",
]

#: The composed draft each variant's line starts at.
_COMPOSED_TYPES = {
    "internal": INTERNAL_REPORT_ARTIFACT_TYPE,
    "context": CONTEXT_REPORT_ARTIFACT_TYPE,
}


class NotEditable(ValueError):
    """Not a draft the editor opens: the client report, another type, another run's report."""


class LineNotFound(LookupError):
    """The line asked for is not one of this run's and variant's."""


@dataclass(frozen=True)
class OpenedLine:
    """What a config for the editor names: the session's key and the line's newest version."""

    line_id: str
    version: EditorVersion
    session: EditorSession
    #: Whether this open started the session; false when it joined one already open.
    started: bool


class ReportEditor:
    """A run's report lines in the Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        scope.require(Permission.EDIT_STUDY)
        self._scope = scope
        self._repo = ReportEditorRepository(session, scope)

    def _check(
        self, composed: Artifact, *, run_id: str, variant: str, deep_research_run_id: str | None
    ) -> None:
        if variant not in EDITABLE_VARIANTS:
            raise NotEditable(f"the {variant!r} report does not open in the editor")
        if (
            composed.artifact_type != _COMPOSED_TYPES[variant]
            or composed.status is not ArtifactStatus.VALID
            or composed.metadata.get("run_id") != run_id
            or (
                variant == "context"
                and composed.metadata.get("deep_research_run_id") != deep_research_run_id
            )
        ):
            raise NotEditable(composed.artifact_id)

    def start_line(
        self,
        composed: Artifact,
        *,
        run_id: str,
        variant: str,
        deep_research_run_id: str | None = None,
    ) -> list[EditorVersion]:
        """``composed``'s line, started (koncept 1) if it had none, its versions locked for the
        caller's transaction."""
        self._check(
            composed, run_id=run_id, variant=variant, deep_research_run_id=deep_research_run_id
        )
        # The composed row, not the versions: before the first open there are none to lock.
        self._repo.lock_line(composed.artifact_id)
        versions = self._repo.versions(composed.artifact_id, for_update=True)
        if versions:
            return versions
        first = self._repo.add_version(
            artifact_id=composed.artifact_id,
            line_id=composed.artifact_id,
            koncept=1,
            run_id=run_id,
            variant=variant,
            deep_research_run_id=deep_research_run_id if variant == "context" else None,
            sha256=composed.sha256,
            saved_at=composed.created_at or datetime.now(UTC),
        )
        return [first]

    def display_name(self) -> str:
        """The caller's name for co-editors, never their e-mail (empty when none)."""
        return self._repo.display_name()

    def names(self, user_ids: Sequence[str]) -> dict[str, str]:
        """The display names of those of ``user_ids`` in the organization, never an e-mail."""
        return self._repo.names(user_ids)

    def newest(self, line_id: str) -> EditorVersion | None:
        """``line_id``'s newest version: the one a save after the one read would have replaced."""
        versions = self._repo.versions(line_id)
        return versions[-1] if versions else None

    def version_of(self, session: EditorSession, artifact_id: str) -> EditorVersion | None:
        """``artifact_id`` when it is a version of ``session``'s line, else ``None``."""
        version = self._repo.version(artifact_id)
        return version if version is not None and version.line_id == session.line_id else None

    def keep_open(self, session: EditorSession, *, now: datetime) -> None:
        """A callback for ``session`` came: it is in use."""
        self._repo.touch(session.document_key, now=now)

    def close(self, session: EditorSession, *, now: datetime, reason: str) -> None:
        self._repo.close(session.document_key, now=now, reason=reason)

    def note_problem(self, session: EditorSession, *, now: datetime, problem: str) -> None:
        self._repo.note_problem(session.document_key, now=now, problem=problem)

    def lines(
        self, *, run_id: str, variant: str, deep_research_run_id: str | None = None
    ) -> list[LineHead]:
        """Every line of the run and variant with its newest version, newest first."""
        heads = self._repo.heads(
            run_id=run_id,
            variant=variant,
            deep_research_run_id=deep_research_run_id if variant == "context" else None,
        )
        return sorted(heads, key=lambda h: (h.saved_at, h.koncept, h.line_id), reverse=True)

    def open(
        self,
        composed: Artifact,
        *,
        run_id: str,
        variant: str,
        deep_research_run_id: str | None = None,
        line_id: str | None = None,
        now: datetime | None = None,
    ) -> OpenedLine:
        """The session a config for ``run_id``'s ``variant`` names, on ``line_id`` or, when none
        is asked, the line with the newest version. ``composed`` is the run's current draft: its
        line always exists after this."""
        now = now or datetime.now(UTC)
        self.start_line(
            composed, run_id=run_id, variant=variant, deep_research_run_id=deep_research_run_id
        )
        heads = self.lines(
            run_id=run_id, variant=variant, deep_research_run_id=deep_research_run_id
        )
        if line_id is None:
            head = default_line(heads)
            if head is None:  # pragma: no cover - the composed draft's line was just started
                raise LineNotFound(composed.artifact_id)
            line_id = head.line_id
        elif line_id not in {h.line_id for h in heads}:
            raise LineNotFound(line_id)
        if line_id != composed.artifact_id:
            self._repo.lock_line(line_id)  # after the composed row, always in that order
        versions = self._repo.versions(line_id, for_update=True)
        current = self._repo.open_session(line_id)
        if current is not None and reuse_session(_state(current), now):
            self._repo.touch(current.document_key, now=now, user_id=self._scope.actor_id)
            joined = self._repo.session(current.document_key) or current
            # A force-save keeps the key, so the open session holds the newest version: the
            # one a Document Server that lost its cache fetches again, and the one shown.
            return OpenedLine(line_id, versions[-1], joined, started=False)
        if current is not None:
            self._repo.close(current.document_key, now=now, reason="idle")
        newest = versions[-1]
        number = self._repo.last_session_no(line_id) + 1
        started = self._repo.start_session(
            document_key=document_key(line_id, newest.sha256, number),
            line_id=line_id,
            session_no=number,
            version_artifact_id=newest.artifact_id,
            run_id=run_id,
            now=now,
        )
        return OpenedLine(line_id, newest, started, started=True)


def _state(session: EditorSession) -> SessionState:
    return SessionState(
        session.document_key, session.session_no, session.last_seen_at, session.closed_at
    )
