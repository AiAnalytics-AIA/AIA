"""Design Revisions: the research design a run executes (ADR 0016 decision 1).

Every method takes an issued ``StudyContext``; the design project is found from
the Study, never from anything the caller names. The design project is owned
(``projects.owner = study_design``): only this repository names that owner, so no
other path -- the generic project routes included -- can see or write it, and
every revision of it passed :func:`~aia_core.domain.design.validate_design`. A
revision is written through ``ProjectRepository.save``, which deduplicates identical
content and never rewrites a revision, so the content under an existing run cannot
change.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.design import (
    DESIGN_PROJECT_OWNER,
    DESIGN_SOURCE_STAGES,
    DesignRejected,
    DesignRevision,
    validate_design,
)
from ..domain.design_reuse import DesignSource, SourceLabels
from ..domain.edit_log import ActorKind, OpSource, WriteBy
from ..domain.pipeline import ProjectType, fingerprint
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyKind
from .repositories import ProjectRepository
from .study_workspace_repository import StudyWorkspaceRepository
from .tables import (
    ProjectRevisionRow,
    StudyDesignRow,
    StudyDesignSourceRow,
    StudyRow,
    as_utc,
)

__all__ = [
    "AUTHORED_REASON",
    "DesignRevisionNotFound",
    "StudyDesignRepository",
    "erase_client_designs",
]

#: ``project_revisions.reason`` for a design submitted from a stage: the provenance
#: of a Design Revision without a column of its own.
_REASON_PREFIX: Final = "design:"
#: What follows the stage in ``reason``: the working revision the design came from.
_WORKSPACE_MARK: Final = "@w"
#: ``project_revisions.reason`` of the working revision a server-side author writes
#: (:meth:`StudyDesignRepository.submit_as_working_copy`).
AUTHORED_REASON: Final = "design_authored"


class DesignRevisionNotFound(LookupError):
    """No Design Revision with this id in the Study in scope."""


def _provenance(reason: str) -> tuple[str, int | None]:
    """The stage and the working revision a Design Revision's ``reason`` records."""
    body = reason[len(_REASON_PREFIX) :] if reason.startswith(_REASON_PREFIX) else reason
    stage, mark, number = body.partition(_WORKSPACE_MARK)
    if mark and number.isdigit():
        return stage, int(number)
    return body, None


def _to_domain(row: ProjectRevisionRow, study_id: str) -> DesignRevision:
    stage, workspace_revision = _provenance(row.reason or "")
    return DesignRevision(
        revision_id=row.revision_id,
        study_id=study_id,
        revision=row.revision,
        content_sha256=row.content_sha256,
        parent_revision=row.parent_revision,
        source_stage=stage,
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
        workspace_revision=workspace_revision,
    )


def _source_to_domain(row: StudyDesignSourceRow) -> DesignSource:
    return DesignSource(
        study_id=row.study_id,
        revision_id=row.revision_id,
        source_study_id=row.source_study_id,
        source_revision_id=row.source_revision_id,
        source_revision=row.source_revision,
        source_content_sha256=row.source_content_sha256,
        labels=SourceLabels.model_validate(row.labels),
        created_by=row.created_by,
        created_at=as_utc(row.created_at),
    )


class StudyDesignRepository:
    """Reads and writes the Design Revisions of the research Study in scope."""

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError("StudyDesignRepository needs an issued StudyContext")
        self._session = session
        self._scope = scope

    # -- the design project -------------------------------------------------

    def _design(self) -> StudyDesignRow | None:
        s = self._scope
        return self._session.scalar(
            select(StudyDesignRow).where(
                StudyDesignRow.study_id == s.study_id,
                StudyDesignRow.client_id == s.client_id,
                StudyDesignRow.organization_id == s.organization_id,
            )
        )

    def _require_research(self, *, lock: bool = False) -> StudyRow:
        s = self._scope
        stmt = select(StudyRow).where(
            StudyRow.study_id == s.study_id,
            StudyRow.client_id == s.client_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        study = self._session.scalar(stmt)
        if study is None:  # pragma: no cover - an issued scope names an existing study
            raise ScopeDenied("not found", reason="unknown_study")
        if study.kind != StudyKind.RESEARCH.value:
            raise DesignRejected(
                "only a research study has a research design", reason="not_research"
            )
        return study

    def project_id(self) -> str | None:
        """The design project of the Study, or ``None`` before the first design."""
        row = self._design()
        return row.project_id if row else None

    # -- writes -------------------------------------------------------------

    def lock(self) -> None:
        """Lock the Study row, as every design and working-copy writer does. The caller commits.

        A writer that reads before it writes -- an accept that checks the working copy, merges
        and then writes both -- takes it first, so nothing moves between its read and its writes.
        """
        self._require_research(lock=True)

    def submit(
        self, *, content: Any, source_stage: str, workspace_revision: int
    ) -> tuple[DesignRevision, bool]:
        """Store ``content`` as the Study's newest Design Revision.

        Returns the revision and whether it is new: content identical to the
        newest revision is not a new revision. Needs ``EDIT_STUDY`` on an open
        research Study. The first design creates the Study's design project.

        ``workspace_revision`` is the working revision the design came from (ADR 0026 decision
        5). ``content`` must be exactly its content, by canonical hash; anything else, or a
        revision the Study's working copy never wrote, is refused (``design_not_from_workspace``).
        Content identical to a newest revision that names no working revision (one written
        before the rule) is written again as a new revision that names this one: a revision
        without a baseline is never handed to a submit that has one.
        """
        s = self._scope
        s.require(Permission.EDIT_STUDY)
        s.require_open_study()
        if source_stage not in DESIGN_SOURCE_STAGES:
            raise DesignRejected("unknown source stage", reason="unknown_source_stage")
        design = validate_design(content)
        study = self._require_research(lock=True)
        working = StudyWorkspaceRepository(self._session).at_revision(s, workspace_revision)
        if working is None or fingerprint(working.content or {}) != fingerprint(design):
            raise DesignRejected(
                "the design is not the working revision it names",
                reason="design_not_from_workspace",
            )
        projects = ProjectRepository(self._session, s, owner=DESIGN_PROJECT_OWNER)
        reason = f"{_REASON_PREFIX}{source_stage}{_WORKSPACE_MARK}{workspace_revision}"

        row = self._design()
        if row is None:
            project, outcome = projects.create(
                title=study.name,
                project_type=ProjectType.RESEARCH,
                content=design,
                created_by=s.actor_id,
                reason=reason,
            )
            first = self._revision_row(project.project_id, outcome.revision)
            self._session.add(
                StudyDesignRow(
                    study_id=s.study_id,
                    organization_id=s.organization_id,
                    client_id=s.client_id,
                    project_id=project.project_id,
                    created_by=s.actor_id,
                )
            )
            self._session.flush()
            return _to_domain(first, s.study_id), True

        newest = self.latest()
        outcome = projects.save(
            row.project_id,
            content=design,
            reason=reason,
            actor_id=s.actor_id,
            force_new_revision=newest is not None and newest.workspace_revision is None,
        )
        revision = self._revision_row(row.project_id, outcome.revision)
        return _to_domain(revision, s.study_id), not outcome.deduplicated

    def submit_as_working_copy(
        self, *, content: Any, source_stage: str, reason: str = AUTHORED_REASON
    ) -> tuple[DesignRevision, bool]:
        """A design the server authored itself: saved as the working copy, then submitted.

        For a writer that is the design's author -- a reused design written into an empty study
        (``design_reuse``), an operator's seed, a test -- not for a person's edit, which the
        browser saves and submits itself. The working copy's newest revision becomes ``content``
        (a new revision, so nothing earlier is lost, and a browser holding an older copy is
        refused its next save as stale, never overwritten), and the Design Revision names it.
        The write is logged as authored by the server on the calling person's action
        (``OpSource.AUTHORED``, working-copy-edit-ops WCE2).
        """
        workspaces = StudyWorkspaceRepository(self._session)
        self._require_research(lock=True)
        current = workspaces.content(self._scope)
        saved = workspaces.save(
            self._scope,
            content=content,
            base_revision=current.revision,
            reason=reason,
            by=WriteBy(ActorKind.PERSON, self._scope.actor_id, OpSource.AUTHORED),
        )
        stored = workspaces.at_revision(self._scope, saved.revision)
        assert stored is not None  # save has just written or found it
        return self.submit(
            content=stored.content, source_stage=source_stage, workspace_revision=saved.revision
        )

    def submit_if_current(
        self,
        *,
        content: Any,
        source_stage: str,
        expected_revision_id: str,
        workspace_revision: int,
    ) -> tuple[DesignRevision, bool]:
        """Apply a reviewed proposal only against its unchanged baseline.

        The same Study row lock serializes ordinary submit() and proposal
        acceptance, including first-design creation. ``workspace_revision`` is the working
        revision the accept wrote, as :meth:`submit` requires. The caller commits.
        """
        self._scope.require(Permission.EDIT_STUDY)
        self._scope.require_open_study()
        self._require_research(lock=True)
        self.get(expected_revision_id)
        latest = self.latest()
        if latest is None or latest.revision_id != expected_revision_id:
            raise DesignRejected(
                "the proposal's design baseline has changed", reason="stale_proposal"
            )
        return self.submit(
            content=content, source_stage=source_stage, workspace_revision=workspace_revision
        )

    def record_source(
        self,
        *,
        revision_id: str,
        source_study_id: str,
        source_revision_id: str,
        source_revision: int,
        source_content_sha256: str,
        labels: SourceLabels,
    ) -> DesignSource:
        """Record, once, that the Study's design was reused from a past study's revision.

        ``revision_id`` must be this Study's own revision (the reused design, submitted
        first). A second citation is refused (``source_already_recorded``): a Study's design
        comes from one place. The caller has resolved the source under its own scope; this
        records what it was told, and the caller commits.
        """
        s = self._scope
        s.require(Permission.EDIT_STUDY)
        s.require_open_study()
        self._require_research(lock=True)
        self.get(revision_id)
        if self._source_row() is not None:
            raise DesignRejected(
                "the Study's design already has a source", reason="source_already_recorded"
            )
        row = StudyDesignSourceRow(
            study_id=s.study_id,
            organization_id=s.organization_id,
            client_id=s.client_id,
            revision_id=revision_id,
            source_study_id=source_study_id,
            source_revision_id=source_revision_id,
            source_revision=source_revision,
            source_content_sha256=source_content_sha256,
            labels=labels.model_dump(mode="json"),
            created_by=s.actor_id,
        )
        self._session.add(row)
        self._session.flush()
        return _source_to_domain(row)

    # -- reads --------------------------------------------------------------

    def _source_row(self) -> StudyDesignSourceRow | None:
        s = self._scope
        return self._session.scalar(
            select(StudyDesignSourceRow).where(
                StudyDesignSourceRow.study_id == s.study_id,
                StudyDesignSourceRow.client_id == s.client_id,
                StudyDesignSourceRow.organization_id == s.organization_id,
            )
        )

    def source(self) -> DesignSource | None:
        """Where the Study's design came from, or ``None`` when it was not reused."""
        row = self._source_row()
        return _source_to_domain(row) if row is not None else None

    def _revision_row(self, project_id: str, revision: int) -> ProjectRevisionRow:
        found = self._session.scalar(
            select(ProjectRevisionRow).where(
                ProjectRevisionRow.project_id == project_id,
                ProjectRevisionRow.revision == revision,
            )
        )
        if found is None:  # pragma: no cover - save() has just written or found it
            raise DesignRevisionNotFound(f"{project_id} r{revision}")
        return found

    def _by_id(self, revision_id: str) -> ProjectRevisionRow:
        row = self._design()
        if row is None:
            raise DesignRevisionNotFound(revision_id)
        # The id alone is never enough: it must belong to this Study's design.
        found = self._session.scalar(
            select(ProjectRevisionRow).where(
                ProjectRevisionRow.project_id == row.project_id,
                ProjectRevisionRow.revision_id == revision_id,
            )
        )
        if found is None:
            raise DesignRevisionNotFound(revision_id)
        return found

    def get(self, revision_id: str) -> DesignRevision:
        """One Design Revision of the Study in scope, or :class:`DesignRevisionNotFound`."""
        return _to_domain(self._by_id(revision_id), self._scope.study_id)

    def content(self, revision_id: str) -> dict[str, Any]:
        """The design exactly as the revision recorded it."""
        return dict(self._by_id(revision_id).content)

    def latest(self) -> DesignRevision | None:
        """The Study's newest Design Revision, or ``None`` before the first design."""
        page = self.revisions(limit=1)
        return page[0] if page else None

    def revisions(self, *, limit: int = 50) -> list[DesignRevision]:
        """The Study's Design Revisions, newest first."""
        row = self._design()
        if row is None:
            return []
        rows = self._session.scalars(
            select(ProjectRevisionRow)
            .where(ProjectRevisionRow.project_id == row.project_id)
            .order_by(ProjectRevisionRow.revision.desc())
            .limit(max(1, min(int(limit), 200)))
        ).all()
        return [_to_domain(r, self._scope.study_id) for r in rows]


def erase_client_designs(session: Session, *, client_id: str) -> None:
    """Delete a deleted client's Design Revision rows and reused-design citations (SB5); their
    design projects go with the client's projects, after these."""
    session.execute(delete(StudyDesignSourceRow).where(StudyDesignSourceRow.client_id == client_id))
    session.execute(delete(StudyDesignRow).where(StudyDesignRow.client_id == client_id))
    session.flush()
