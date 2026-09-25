"""Design Revisions: the research design a run executes (ADR 0016 decision 1).

Every method takes an issued ``StudyContext``; the design project is found from
the Study, never from anything the caller names. A revision is written through
``ProjectRepository.save``, which deduplicates identical content and never
rewrites a revision, so the content under an existing run cannot change.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.design import (
    DESIGN_SOURCE_STAGES,
    DesignRejected,
    DesignRevision,
    validate_design,
)
from ..domain.pipeline import ProjectType
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyKind
from .repositories import ProjectRepository
from .tables import ProjectRevisionRow, StudyDesignRow, StudyRow, as_utc

__all__ = ["DesignRevisionNotFound", "StudyDesignRepository"]

#: ``project_revisions.reason`` for a design submitted from a stage: the provenance
#: of a Design Revision without a column of its own.
_REASON_PREFIX: Final = "design:"


class DesignRevisionNotFound(LookupError):
    """No Design Revision with this id in the Study in scope."""


def _to_domain(row: ProjectRevisionRow, study_id: str) -> DesignRevision:
    reason = row.reason or ""
    stage = reason[len(_REASON_PREFIX) :] if reason.startswith(_REASON_PREFIX) else reason
    return DesignRevision(
        revision_id=row.revision_id,
        study_id=study_id,
        revision=row.revision,
        content_sha256=row.content_sha256,
        parent_revision=row.parent_revision,
        source_stage=stage,
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

    def _require_research(self) -> StudyRow:
        s = self._scope
        study = self._session.scalar(
            select(StudyRow).where(
                StudyRow.study_id == s.study_id,
                StudyRow.client_id == s.client_id,
            )
        )
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

    def submit(self, *, content: Any, source_stage: str) -> tuple[DesignRevision, bool]:
        """Store ``content`` as the Study's newest Design Revision.

        Returns the revision and whether it is new: content identical to the
        newest revision is not a new revision. Needs ``EDIT_STUDY`` on an open
        research Study. The first design creates the Study's design project.
        """
        s = self._scope
        s.require(Permission.EDIT_STUDY)
        s.require_open_study()
        if source_stage not in DESIGN_SOURCE_STAGES:
            raise DesignRejected("unknown source stage", reason="unknown_source_stage")
        design = validate_design(content)
        study = self._require_research()
        projects = ProjectRepository(self._session, s)
        reason = _REASON_PREFIX + source_stage

        row = self._design()
        if row is None:
            project, outcome = projects.create(
                title=study.name,
                project_type=ProjectType.RESEARCH,
                content=design,
                created_by=s.actor_id,
            )
            # create() records "project_created"; the revision is the design's
            # first, so it says where it came from like every later one.
            first = self._revision_row(project.project_id, outcome.revision)
            first.reason = reason
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

        outcome = projects.save(row.project_id, content=design, reason=reason, actor_id=s.actor_id)
        revision = self._revision_row(row.project_id, outcome.revision)
        return _to_domain(revision, s.study_id), not outcome.deduplicated

    # -- reads --------------------------------------------------------------

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
