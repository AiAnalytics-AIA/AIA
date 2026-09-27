"""Persistence for a research Study's workspace and working content (ADR 0018, OI-58).

Every method takes an issued scope. The working content lives in the Study's
working project (``projects.owner = study_workspace``), written through
:class:`~aia_core.infrastructure.repositories.ProjectRepository` -- immutable
revisions, deduplicated when nothing changed, with the project's event history --
and found only through the Study's ``study_workspaces`` row. There is deliberately
no method that finds a Study from a project id or from an 18.6.6 unit project id:
those are data a Study's scope yields, never inputs that yield a scope.

Saves are serialized per Study by locking the Study row, as design submissions are
(``StudyDesignRepository``), and a save names the revision it was edited from: a
save from a stale copy is refused (:class:`WorkspaceConflict`, ``stale_revision``)
rather than silently overwriting a newer one saved elsewhere.

A brief's attachments are artifacts of the same working project, in AIA's artifact
storage (:meth:`StudyWorkspaceRepository.attach`); the brief keeps their records,
and only :meth:`StudyWorkspaceRepository.attachment` serves their bytes.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.attachments import (
    ATTACHMENT_ARTIFACT_TYPE,
    ATTACHMENT_STAGE,
    AttachmentRecord,
    attachment_record,
    content_type_of,
    extension_of,
    validate_attachment,
)
from ..domain.pipeline import ProjectType, fingerprint
from ..domain.scope import ClientContext, Permission, ScopeDenied, StudyContext, StudyKind
from ..domain.workspace import (
    SAVE_REASON,
    STAGE_KEYS,
    WORKSPACE_PROJECT_OWNER,
    ContentState,
    StudyWorkspace,
    WorkingContent,
    WorkingRevision,
    WorkingSave,
    WorkspaceRejected,
    validate_working_content,
)
from .artifact_repository import Artifact, ArtifactNotFound, ArtifactRepository
from .document_text import extract_text
from .repositories import ProjectRepository
from .storage import ArtifactStore
from .tables import (
    ProjectRevisionRow,
    ProjectRow,
    StudyRow,
    StudyWorkspaceRow,
    as_utc,
    utcnow,
)

__all__ = ["StudyWorkspaceRepository", "WorkspaceConflict"]


class WorkspaceConflict(Exception):
    """The save cannot be applied as asked: a newer revision exists, or the state forbids it."""

    def __init__(self, message: str, *, reason: str, current_revision: int | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.current_revision = current_revision


def _to_domain(row: StudyWorkspaceRow) -> StudyWorkspace:
    return StudyWorkspace(
        study_id=row.study_id,
        state=ContentState(row.content_state),
        project_id=row.project_id,
        unit_project_id=row.unit_project_id,
        lineage=dict(row.lineage or {}),
        last_stage=row.last_stage,
        bound_at=as_utc(row.bound_at),
        modified_at=as_utc(row.modified_at),
    )


def _revision(row: ProjectRevisionRow) -> WorkingRevision:
    return WorkingRevision(
        revision=row.revision,
        revision_id=row.revision_id,
        parent_revision=row.parent_revision,
        reason=row.reason,
        content_sha256=row.content_sha256,
        created_at=as_utc(row.created_at),
        created_by=row.created_by,
    )


class StudyWorkspaceRepository:
    """Reads and writes Study workspaces and their working content.

    The caller owns the transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # -- rows ----------------------------------------------------------------

    def _row(self, scope: StudyContext) -> StudyWorkspaceRow | None:
        # All three scope columns, as every client-data predicate (ADR 0004).
        return self._session.scalar(
            select(StudyWorkspaceRow).where(
                StudyWorkspaceRow.study_id == scope.study_id,
                StudyWorkspaceRow.client_id == scope.client_id,
                StudyWorkspaceRow.organization_id == scope.organization_id,
            )
        )

    def _projects(self, scope: StudyContext) -> ProjectRepository:
        return ProjectRepository(self._session, scope, owner=WORKSPACE_PROJECT_OWNER)

    def _lock_research_study(self, scope: StudyContext) -> StudyRow:
        """Lock the Study row: saves to one Study are applied one at a time."""
        study = self._session.scalar(
            select(StudyRow)
            .where(StudyRow.study_id == scope.study_id, StudyRow.client_id == scope.client_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if study is None:  # pragma: no cover - an issued scope names an existing study
            raise ScopeDenied("not found", reason="unknown_study")
        if study.kind != StudyKind.RESEARCH.value:
            raise WorkspaceRejected(
                "only a research study has research working content", reason="not_research"
            )
        return study

    def _current(self, row: StudyWorkspaceRow) -> ProjectRevisionRow | None:
        if row.project_id is None:
            return None
        project = self._session.get(ProjectRow, row.project_id)
        if project is None or project.current_revision < 1:  # pragma: no cover - FK + create
            return None
        return self._session.get(ProjectRevisionRow, (row.project_id, project.current_revision))

    # -- reads ---------------------------------------------------------------

    def get(self, scope: StudyContext) -> StudyWorkspace | None:
        """The workspace of the Study in scope, or ``None`` when it has none yet."""
        row = self._row(scope)
        return _to_domain(row) if row else None

    def state(self, scope: StudyContext) -> ContentState:
        """Where the Study's working content stands; ``EMPTY`` without a workspace."""
        row = self._row(scope)
        return ContentState(row.content_state) if row else ContentState.EMPTY

    def content(self, scope: StudyContext) -> WorkingContent:
        """The Study's working content: its state and, when it has one, its current revision.

        Readable by anyone who may read the Study; no permission beyond the scope.
        """
        row = self._row(scope)
        if row is None:
            return WorkingContent(study_id=scope.study_id, state=ContentState.EMPTY)
        state = ContentState(row.content_state)
        current = self._current(row) if state.has_content else None
        if current is None:
            return WorkingContent(
                study_id=scope.study_id, state=state, lineage=dict(row.lineage or {})
            )
        return WorkingContent(
            study_id=scope.study_id,
            state=state,
            revision=current.revision,
            revision_id=current.revision_id,
            content=dict(current.content or {}),
            analysis=dict(current.analysis) if current.analysis else None,
            saved_at=as_utc(current.created_at),
            saved_by=current.created_by,
            lineage=dict(row.lineage or {}),
        )

    def revisions(self, scope: StudyContext, *, limit: int = 100) -> list[WorkingRevision]:
        """The Study's saved revisions, newest first."""
        row = self._row(scope)
        if row is None or row.project_id is None:
            return []
        return [_revision(r) for r in self._projects(scope).revisions(row.project_id, limit=limit)]

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

    # -- writes --------------------------------------------------------------

    def save(
        self,
        scope: StudyContext,
        *,
        content: Any,
        analysis: Any = None,
        base_revision: int | None,
        reason: str = "autosave",
    ) -> WorkingSave:
        """Save the Study's working content as its newest revision.

        ``base_revision`` is the revision the content was edited from: ``None`` only
        for a Study with no content yet. A save from any other revision than the
        current one is refused (``stale_revision``), so two editors cannot silently
        overwrite each other. Content and analysis identical to the current revision
        write nothing (``deduplicated``). Needs ``EDIT_STUDY`` on an open research
        Study whose content is not awaiting migration. The first save creates the
        Study's working project.
        """
        scope.require(Permission.EDIT_STUDY)
        scope.require_open_study()
        if not SAVE_REASON.fullmatch(reason):
            raise WorkspaceRejected("not a save reason", reason="bad_reason")
        body, analysis_body = validate_working_content(content, analysis)
        self._lock_research_study(scope)

        row = self._row(scope)
        state = ContentState(row.content_state) if row else ContentState.EMPTY
        if not state.editable:
            raise WorkspaceConflict(
                "the Study's content awaits migration from 18.6.6", reason="awaiting_migration"
            )
        current = self._current(row) if row is not None and state.has_content else None
        current_revision = current.revision if current is not None else None
        if base_revision != current_revision:
            raise WorkspaceConflict(
                "the working content changed since it was loaded",
                reason="stale_revision",
                current_revision=current_revision,
            )

        projects = self._projects(scope)
        if row is None or row.project_id is None:
            study = self._session.get(StudyRow, scope.study_id)
            project, outcome = projects.create(
                title=str(body.get("title") or (study.name if study else "")) or None,
                project_type=ProjectType.RESEARCH,
                content=body,
                analysis=analysis_body,
                created_by=scope.actor_id,
                request_id=scope.request_id,
                reason=reason,
            )
            lineage: dict[str, Any] = dict(row.lineage or {}) if row is not None else {}
            if state is ContentState.UNRECOVERABLE:
                # Started again, explicitly, after nothing could be recovered: the
                # record of that stays with the Study.
                lineage["restarted_after_unrecoverable"] = {
                    "by": scope.actor_id,
                    "revision_id": outcome.revision_id,
                }
            if row is None:
                row = StudyWorkspaceRow(
                    study_id=scope.study_id,
                    organization_id=scope.organization_id,
                    client_id=scope.client_id,
                    content_state=ContentState.NATIVE.value,
                    project_id=project.project_id,
                    lineage=lineage,
                    bound_by=scope.actor_id,
                )
                self._session.add(row)
            else:
                row.content_state = ContentState.NATIVE.value
                row.project_id = project.project_id
                row.lineage = lineage
            self._session.flush()
            return WorkingSave(
                study_id=scope.study_id,
                state=ContentState(row.content_state),
                revision=outcome.revision,
                revision_id=outcome.revision_id or "",
                deduplicated=False,
            )

        assert current is not None  # has_content and a project: the current revision exists
        # A changed analysis is a change even when the document is not: plan_save
        # compares the content only, so the analysis forces the new revision.
        analysis_changed = fingerprint(analysis_body or {}) != fingerprint(current.analysis or {})
        outcome = projects.save(
            row.project_id,
            content=body,
            analysis=analysis_body,
            reason=reason,
            force_new_revision=analysis_changed,
            actor_id=scope.actor_id,
            request_id=scope.request_id,
        )
        if outcome.deduplicated:
            revision_id = current.revision_id
        else:
            revision_id = outcome.revision_id or ""
            row.modified_at = utcnow()
        self._session.flush()
        return WorkingSave(
            study_id=scope.study_id,
            state=ContentState(row.content_state),
            revision=outcome.revision,
            revision_id=revision_id,
            deduplicated=outcome.deduplicated,
        )

    # -- attachments ---------------------------------------------------------

    def _artifacts(self, scope: StudyContext, store: ArtifactStore) -> ArtifactRepository:
        return ArtifactRepository(self._session, scope, store, owner=WORKSPACE_PROJECT_OWNER)

    def attach(
        self, scope: StudyContext, store: ArtifactStore, *, filename: str, data: bytes
    ) -> AttachmentRecord:
        """Keep a file for the Study's brief, in AIA's storage, and return its record.

        The bytes become an artifact of the Study's working project (stage ``BRIEF``)
        and the text the unit would have read of them becomes the record's excerpt.
        Nothing in the working content changes here: the stage adds the record to the
        brief and saves it, as any other edit. Needs ``EDIT_STUDY`` on an open Study
        whose working content exists in AIA -- one with nothing saved yet has nothing
        to attach to (``not_saved``), one awaiting migration is not editable
        (``awaiting_migration``).
        """
        scope.require(Permission.EDIT_STUDY)
        scope.require_open_study()
        name = validate_attachment(filename, data)
        row = self._row(scope)
        state = ContentState(row.content_state) if row else ContentState.EMPTY
        if not state.editable:
            raise WorkspaceConflict(
                "the Study's content awaits migration from 18.6.6", reason="awaiting_migration"
            )
        if row is None or row.project_id is None:
            raise WorkspaceConflict(
                "the Study's working content has not been saved yet", reason="not_saved"
            )
        project = self._session.get(ProjectRow, row.project_id)
        assert project is not None  # the row's foreign key
        text = extract_text(data, name)
        artifact, _ = self._artifacts(scope, store).put(
            project_id=row.project_id,
            revision=project.current_revision,
            stage_type=ATTACHMENT_STAGE,
            artifact_type=ATTACHMENT_ARTIFACT_TYPE,
            data=data,
            content_type=content_type_of(name),
            metadata={
                "filename": name,
                "extension": extension_of(name),
                "text_extracted": bool(text),
                "text_chars": len(text),
            },
            reuse=False,
        )
        return attachment_record(
            attachment_id=artifact.artifact_id,
            filename=name,
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            text=text,
        )

    def attachment(
        self, scope: StudyContext, store: ArtifactStore, attachment_id: str
    ) -> tuple[Artifact, bytes]:
        """One of the Study's attachments and its bytes, verified against the recorded hash.

        Only an attachment of this Study's working project: any other id -- another
        Study's attachment, a run's or a design's artifact -- is
        :class:`~aia_core.infrastructure.artifact_repository.ArtifactNotFound`.
        Readable by anyone who may read the Study, as its working content is.
        """
        artifacts = self._artifacts(scope, store)
        artifact = artifacts.get(attachment_id)
        if artifact.artifact_type != ATTACHMENT_ARTIFACT_TYPE:
            raise ArtifactNotFound(attachment_id)
        return artifact, artifacts.read(attachment_id)

    def record_stage(self, scope: StudyContext, *, stage: str) -> StudyWorkspace | None:
        """Remember the stage the study was opened on.

        A no-op without a workspace or without ``EDIT_STUDY``.
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
