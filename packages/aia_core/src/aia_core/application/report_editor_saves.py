"""A save the Document Server sent, stored as a line's next version (artifact-report RPT8c).

:func:`store_save` fetches the file the callback names (only from the editor's own origin, under
``/cache/files/``: :func:`~aia_core.infrastructure.editor_fetch.allowed`, checked before any
fetcher is called), checks it is a DOCX that opens, and stores it as the line's next koncept: an
artifact depending on the version before it, with what it changed in the numbers code wrote
beside it (RPT8b, ``saved_changes``, compared with the line's koncept 1). The same bytes are never
a line's version twice. A save not stored is :class:`SaveNotStored` with a stable reason, which
the session keeps for the pane to say (``last_problem``); the next stored save clears it.

Its authors are the people the Document Server names, each of whom a config was signed for.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from aia_core.application.report import INTERNAL_REPORT_MEDIA_TYPE
from aia_core.application.research import research_artifacts
from aia_core.domain.deep_research.documents import DocumentRefused
from aia_core.domain.report.editor import CHANGES_ARTIFACT_TYPE, EDIT_ARTIFACT_TYPES
from aia_core.domain.report.saved_changes import (
    SavedChanges,
    changes_payload,
    compare,
    read_changes_payload,
)
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.editor_fetch import SaveFetcher, SaveFetchRefused, allowed
from aia_core.infrastructure.report_docx.census import census
from aia_core.infrastructure.report_editor_repository import (
    EditorSession,
    EditorVersion,
    ReportEditorRepository,
)
from aia_core.infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound

__all__ = ["SaveNotStored", "StoredSave", "VersionNotFound", "store_save", "version_changes"]


class VersionNotFound(LookupError):
    """Not a version of one of this run's report lines."""


class SaveNotStored(Exception):
    """A save not stored. ``reason`` is stable: the pane says it in words."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class StoredSave:
    version: EditorVersion
    #: False when the same bytes were already a version of the line: nothing stored again.
    created: bool


def store_save(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    editor_session: EditorSession,
    *,
    url: str,
    origin: str,
    fetcher: SaveFetcher,
    authors: Sequence[str],
    now: datetime,
) -> StoredSave:
    """The file at ``url`` stored as ``editor_session``'s line's next version, or
    :class:`SaveNotStored` (noted on the session, in the caller's transaction)."""
    scope.require(Permission.EDIT_STUDY)
    repo = ReportEditorRepository(session, scope)
    try:
        stored = _store(
            session, scope, store, repo, editor_session, url, origin, fetcher, authors, now
        )
    except SaveNotStored as refused:
        repo.note_problem(editor_session.document_key, now=now, problem=refused.reason)
        raise
    repo.note_problem(editor_session.document_key, now=now, problem=None)
    return stored


def _store(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    repo: ReportEditorRepository,
    editor_session: EditorSession,
    url: str,
    origin: str,
    fetcher: SaveFetcher,
    authors: Sequence[str],
    now: datetime,
) -> StoredSave:
    if not authors or not set(authors) <= set(editor_session.users):
        raise SaveNotStored("unknown_author")
    if not allowed(url, origin):
        raise SaveNotStored("not_the_editors_file")
    try:
        data = fetcher(url)
    except SaveFetchRefused as exc:
        raise SaveNotStored(exc.reason) from exc
    try:
        saved = census(data)
    except DocumentRefused as exc:
        raise SaveNotStored("save_unreadable") from exc
    versions = repo.versions(editor_session.line_id, for_update=True)
    sha256 = hashlib.sha256(data).hexdigest()
    same = next((v for v in versions if v.sha256 == sha256), None)
    if same is not None:
        return StoredSave(same, created=False)
    first, previous = versions[0], versions[-1]
    artifacts = research_artifacts(session, scope, store)
    composed = artifacts.get(first.artifact_id)
    try:
        baseline = census(artifacts.read(first.artifact_id))
    except (DocumentRefused, IntegrityError, ObjectNotFound):
        baseline = None  # not comparable, and said so; the save is still kept
    changes = compare(baseline, saved)
    koncept = previous.koncept + 1
    meta = {
        "run_id": previous.run_id,
        "report_kind": "internal",
        "line_id": editor_session.line_id,
        "koncept": koncept,
        "edited_from": previous.artifact_id,
        "authors": list(authors),
        "review_state": "DRAFT_UNAPPROVED",
    }
    if previous.deep_research_run_id is not None:
        meta["deep_research_run_id"] = previous.deep_research_run_id
    version, _ = artifacts.put(
        project_id=composed.project_id,
        revision=composed.revision,
        stage_type=composed.stage_type,
        artifact_type=EDIT_ARTIFACT_TYPES[previous.variant],
        data=data,
        content_type=INTERNAL_REPORT_MEDIA_TYPE,
        metadata=meta,
        depends_on=[previous.artifact_id],
        reuse=False,
    )
    changed, _ = artifacts.put_json(
        payload=changes_payload(changes),
        project_id=composed.project_id,
        revision=composed.revision,
        stage_type=composed.stage_type,
        artifact_type=CHANGES_ARTIFACT_TYPE,
        metadata={
            "run_id": previous.run_id,
            "line_id": editor_session.line_id,
            "version_artifact_id": version.artifact_id,
        },
        depends_on=[version.artifact_id],
        reuse=False,
    )
    added = repo.add_version(
        artifact_id=version.artifact_id,
        line_id=editor_session.line_id,
        koncept=koncept,
        run_id=previous.run_id,
        variant=previous.variant,
        deep_research_run_id=previous.deep_research_run_id,
        sha256=version.sha256,
        saved_at=now,
        authors=authors,
        changes_artifact_id=changed.artifact_id,
    )
    return StoredSave(added, created=True)


def version_changes(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str, artifact_id: str
) -> tuple[EditorVersion, SavedChanges | None]:
    """A version of one of ``run_id``'s lines and what it changed in the numbers code wrote,
    as stored beside it; ``None`` for koncept 1, the composer's own, which changed nothing."""
    version = ReportEditorRepository(session, scope).version(artifact_id)
    if version is None or version.run_id != run_id:
        raise VersionNotFound(artifact_id)
    if version.changes_artifact_id is None:
        return version, None
    data = research_artifacts(session, scope, store).read(version.changes_artifact_id)
    return version, read_changes_payload(json.loads(data))
