"""Persistence for the durable project graph.

This is the only module permitted to write ``projects``, ``project_revisions``,
``project_stages`` and ``project_events``. Keeping writes in one place is what
makes the immutability of a revision enforceable.

Two rules are enforced here rather than trusted to callers:

* **Scope isolation.** The repository is constructed from a :class:`StudyContext`,
  which only the authorization layer can issue. Every read and write filters on
  ``organization_id``, ``client_id`` *and* ``study_id`` in the same statement that
  finds the row, so there is no unscoped path a handler could forget -- and no way
  for an AI tool argument to widen scope, because scope does not come from
  arguments at all.
* **Revision immutability.** A saved revision is inserted, never updated. The
  decision of *what* to save comes from the pure planner in
  ``aia_core.domain.project.plan_save``; this module only executes it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..domain.pipeline import ProjectType, StageStatus
from ..domain.project import (
    Project,
    ProjectStatus,
    SaveOutcome,
    StageState,
    initial_stages,
    new_project_id,
    plan_save,
    resolve_provider_defaults,
)
from ..domain.providers import DEFAULT_MAX_API_COST_USD, Provider, ProviderPolicy
from ..domain.scope import Permission, StudyContext
from .tables import (
    ProjectEventRow,
    ProjectRevisionRow,
    ProjectRow,
    ProjectStageRow,
    utcnow,
)

__all__ = ["ProjectNotFound", "ProjectPage", "ProjectRepository"]


class ProjectNotFound(LookupError):
    """Raised when a project does not exist *or* belongs to another tenant.

    The two cases are deliberately indistinguishable to callers: telling a user
    that a project exists but is not theirs leaks the existence of other tenants'
    data. The API maps this to 404 in both cases.
    """


@dataclass(frozen=True, slots=True)
class ProjectPage:
    """One page of a project listing."""

    items: list[Project]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """True when further pages exist."""
        return self.offset + len(self.items) < self.total


def _to_domain(row: ProjectRow) -> Project:
    """Map a project row to the domain model."""
    return Project(
        project_id=row.project_id,
        title=row.title,
        project_type=ProjectType.coerce(row.project_type),
        status=ProjectStatus(row.status),
        current_revision=row.current_revision,
        current_stage=row.current_stage,
        last_completed_stage=row.last_completed_stage,
        parent_project_id=row.parent_project_id,
        preferred_provider=Provider(row.preferred_provider),
        provider_policy=ProviderPolicy(row.provider_policy),
        max_api_cost_usd=row.max_api_cost_usd,
        runtime_version=row.runtime_version,
        tags=list(row.tags or []),
        pinned=row.pinned,
        archived=row.archived,
        created_at=row.created_at,
        modified_at=row.modified_at,
    )


def _default_title(project_type: ProjectType) -> str:
    """Czech placeholder title, matching the prototype's wording."""
    return "Nová simulace" if project_type is ProjectType.SIMULATION else "Nový výzkum"


def _stage_to_domain(row: ProjectStageRow) -> StageState:
    """Map a stage row to the domain model."""
    return StageState(
        stage_type=row.stage_type,
        ordinal=row.ordinal,
        status=StageStatus(row.status),
        label=row.label,
        input_fingerprint=row.input_fingerprint,
        provider=Provider(row.provider) if row.provider else None,
        model=row.model,
        current_job_id=row.current_job_id,
        last_checkpoint=row.last_checkpoint,
        waiting_reason=row.waiting_reason,
        quota_reset_at=row.quota_reset_at,
        artifact_ids=list(row.artifact_ids or []),
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class ProjectRepository:
    """Tenant-scoped persistence for projects, revisions and stages.

    The caller owns the transaction: this class flushes so that generated values
    are available, but never commits. That lets an application service perform a
    save, write an event and enqueue a job atomically.
    """

    def __init__(self, session: Session, scope: StudyContext, *, owner: str | None = None) -> None:
        """``owner`` names the repository this one acts for (``projects.owner``).

        ``None`` -- every ordinary caller, the API included -- sees only ordinary
        projects. A Study's design project is owned by the design repository and is
        invisible here unless its owner is named, so nothing else can write it.
        """
        if not isinstance(scope, StudyContext):
            raise TypeError(
                "ProjectRepository requires a StudyContext issued by the "
                "authorization layer; unscoped access is not permitted"
            )
        self._session = session
        self._scope = scope
        self._owner = owner

    @property
    def scope(self) -> StudyContext:
        """The authorised scope this repository operates in."""
        return self._scope

    # ---------------------------------------------------------------- reads --

    def _scope_filter(self) -> tuple[Any, ...]:
        """The isolation predicate applied to every statement.

        All three levels are asserted, not just the narrowest. ``study_id`` alone
        would be sufficient given the foreign keys, but checking client and
        organization too means a corrupted or mis-migrated row cannot be read
        under the wrong authorisation.
        """
        return (
            ProjectRow.organization_id == self._scope.organization_id,
            ProjectRow.client_id == self._scope.client_id,
            ProjectRow.study_id == self._scope.study_id,
            ProjectRow.owner.is_(None) if self._owner is None else ProjectRow.owner == self._owner,
        )

    def _row(self, project_id: str) -> ProjectRow:
        """Fetch a project row within scope, or raise :class:`ProjectNotFound`."""
        row = self._session.scalar(
            select(ProjectRow).where(ProjectRow.project_id == project_id, *self._scope_filter())
        )
        if row is None:
            raise ProjectNotFound(project_id)
        return row

    def get(self, project_id: str) -> Project:
        """Return a project header."""
        return _to_domain(self._row(project_id))

    def list_projects(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        project_type: ProjectType | None = None,
        status: ProjectStatus | None = None,
        include_archived: bool = False,
        include_trashed: bool = False,
        search: str | None = None,
    ) -> ProjectPage:
        """Return a page of projects, newest first, pinned projects first.

        ``limit`` is clamped to a sane maximum so a caller cannot request the whole
        table and exhaust memory.
        """
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        filters = [*self._scope_filter()]
        if not include_archived:
            filters.append(ProjectRow.archived.is_(False))
        if not include_trashed:
            filters.append(ProjectRow.trashed_at.is_(None))
        if project_type is not None:
            filters.append(ProjectRow.project_type == project_type.value)
        if status is not None:
            filters.append(ProjectRow.status == status.value)
        if search:
            filters.append(ProjectRow.title.ilike(f"%{search.strip()}%"))

        total = self._session.scalar(select(func.count()).select_from(ProjectRow).where(*filters))
        rows = self._session.scalars(
            select(ProjectRow)
            .where(*filters)
            .order_by(ProjectRow.pinned.desc(), ProjectRow.modified_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return ProjectPage(
            items=[_to_domain(r) for r in rows],
            total=int(total or 0),
            limit=limit,
            offset=offset,
        )

    def content(self, project_id: str, revision: int | None = None) -> dict[str, Any]:
        """Return the stored content of a revision, defaulting to the current one."""
        row = self._row(project_id)
        target = revision if revision is not None else row.current_revision
        if target < 1:
            return {}

        rev = self._session.scalar(
            select(ProjectRevisionRow).where(
                ProjectRevisionRow.project_id == project_id,
                ProjectRevisionRow.revision == target,
            )
        )
        if rev is None:
            raise ProjectNotFound(f"{project_id}@{target}")
        return dict(rev.content or {})

    def revisions(self, project_id: str, *, limit: int = 100) -> list[ProjectRevisionRow]:
        """Return revision history, newest first."""
        self._row(project_id)
        return list(
            self._session.scalars(
                select(ProjectRevisionRow)
                .where(ProjectRevisionRow.project_id == project_id)
                .order_by(ProjectRevisionRow.revision.desc())
                .limit(max(1, min(int(limit), 500)))
            ).all()
        )

    def stages(self, project_id: str, revision: int | None = None) -> list[StageState]:
        """Return the ordered stages of a revision, defaulting to the current one."""
        row = self._row(project_id)
        target = revision if revision is not None else row.current_revision
        if target < 1:
            return []

        rows = self._session.scalars(
            select(ProjectStageRow)
            .where(
                ProjectStageRow.project_id == project_id,
                ProjectStageRow.revision == target,
            )
            .order_by(ProjectStageRow.ordinal)
        ).all()
        return [_stage_to_domain(r) for r in rows]

    def events(self, project_id: str, *, limit: int = 200) -> list[ProjectEventRow]:
        """Return project history, newest first."""
        self._row(project_id)
        return list(
            self._session.scalars(
                select(ProjectEventRow)
                .where(ProjectEventRow.project_id == project_id)
                .order_by(ProjectEventRow.event_id.desc())
                .limit(max(1, min(int(limit), 1000)))
            ).all()
        )

    # --------------------------------------------------------------- writes --

    def record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
        revision: int | None = None,
        stage_type: str | None = None,
        level: str = "INFO",
        actor_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Append an immutable history entry."""
        self._session.add(
            ProjectEventRow(
                project_id=project_id,
                revision=revision,
                stage_type=stage_type,
                event_type=event_type,
                level=level,
                message=message,
                payload=payload or {},
                actor_id=actor_id,
                request_id=request_id,
            )
        )

    def create(
        self,
        *,
        title: str | None = None,
        project_type: ProjectType | str = ProjectType.RESEARCH,
        content: dict[str, Any] | None = None,
        preferred_provider: Any = Provider.CLAUDE_CODE,
        provider_policy: Any = ProviderPolicy.CLAUDE_CODE_ONLY,
        max_api_cost_usd: float | None = None,
        parent_project_id: str | None = None,
        runtime_version: str = "",
        created_by: str | None = None,
        request_id: str | None = None,
        reason: str = "project_created",
        analysis: dict[str, Any] | None = None,
        panel_version: str = "",
        author_unknown: bool = False,
    ) -> tuple[Project, SaveOutcome]:
        """Create a project and its first revision in one transaction.

        A project exists from the moment work begins, so that an interrupted
        session leaves a resumable project rather than nothing. The first revision
        is written immediately, which is why this returns a :class:`SaveOutcome`
        alongside the project. ``analysis`` and ``panel_version`` go onto that first
        revision, as :meth:`save` would put them on a later one.

        The first revision is attributed to ``created_by``, else to the scope's
        actor. ``author_unknown`` attributes it to nobody: for content written
        into AIA by someone who did not author it (the 18.6.6 migration, whose
        source never recorded an author), where naming the writer would stamp a
        guess.
        """
        self._scope.require(Permission.EDIT_STUDY)
        self._scope.require_open_study()

        ptype = ProjectType.coerce(project_type)
        provider, policy = resolve_provider_defaults(
            preferred_provider=preferred_provider, provider_policy=provider_policy
        )

        project = Project(
            project_id=new_project_id(),
            title=(title or "").strip() or _default_title(ptype),
            project_type=ptype,
            parent_project_id=parent_project_id,
            preferred_provider=provider,
            provider_policy=policy,
            runtime_version=runtime_version,
            max_api_cost_usd=(
                DEFAULT_MAX_API_COST_USD if max_api_cost_usd is None else max_api_cost_usd
            ),
        )

        body = dict(content or {})
        body.setdefault("title", project.title)

        row = ProjectRow(
            project_id=project.project_id,
            title=project.title,
            project_type=ptype.value,
            status=ProjectStatus.DRAFT.value,
            current_revision=0,
            current_stage=project.stage_ids[0],
            parent_project_id=parent_project_id,
            organization_id=self._scope.organization_id,
            client_id=self._scope.client_id,
            study_id=self._scope.study_id,
            created_by=created_by,
            preferred_provider=provider.value,
            provider_policy=policy.value,
            max_api_cost_usd=project.max_api_cost_usd,
            runtime_version=runtime_version,
            tags=[],
            owner=self._owner,
        )
        self._session.add(row)
        self._session.flush()

        outcome = self.save(
            project.project_id,
            content=body,
            reason=reason,
            analysis=analysis,
            panel_version=panel_version,
            actor_id=None if author_unknown else (created_by or self._scope.actor_id),
            request_id=request_id or self._scope.request_id,
        )
        self.record_event(
            project.project_id,
            event_type="PROJECT_CREATED",
            message="Projekt byl vytvořen okamžitě při zahájení práce.",
            payload={
                "project_type": ptype.value,
                "provider": provider.value,
                "provider_policy": policy.value,
            },
            revision=outcome.revision,
            actor_id=created_by,
            request_id=request_id,
        )
        return self.get(project.project_id), outcome

    def save(
        self,
        project_id: str,
        *,
        content: dict[str, Any],
        reason: str = "autosave",
        force_new_revision: bool = False,
        explicit_stage: str | None = None,
        panel_version: str = "",
        analysis: dict[str, Any] | None = None,
        actor_id: str | None = None,
        request_id: str | None = None,
    ) -> SaveOutcome:
        """Persist project content, creating an immutable revision when it changed.

        The decision logic lives in :func:`aia_core.domain.project.plan_save`; this
        method applies it. When the planner deduplicates, only ``modified_at`` is
        touched and no revision row is written.
        """
        self._scope.require(Permission.EDIT_STUDY)

        row = self._row(project_id)
        project = _to_domain(row)

        previous_content: dict[str, Any] | None = None
        previous_stages: list[StageState] = []
        if row.current_revision >= 1:
            previous_content = self.content(project_id)
            previous_stages = self.stages(project_id)

        outcome = plan_save(
            project=project,
            content=content,
            previous_content=previous_content,
            previous_stages=previous_stages,
            reason=reason,
            force_new_revision=force_new_revision,
            explicit_stage=explicit_stage,
        )

        if outcome.deduplicated:
            row.modified_at = utcnow()
            row.title = str(content.get("title") or row.title)
            self._session.flush()
            return outcome

        self._session.add(
            ProjectRevisionRow(
                project_id=project_id,
                revision=outcome.revision,
                revision_id=outcome.revision_id or "",
                parent_revision=(
                    project.current_revision if project.current_revision >= 1 else None
                ),
                content_sha256=outcome.content_sha256,
                content=dict(content),
                analysis=analysis or {},
                changed_fields=list(outcome.changed_fields),
                impact=dict(outcome.impact),
                reason=reason,
                questionnaire_version=str(content.get("schema_version", "")),
                panel_version=panel_version,
                model=str(content.get("model", "")),
                created_by=actor_id,
            )
        )
        self._session.flush()

        stages = outcome.stages or initial_stages(project.project_type)
        for stage in stages:
            self._session.add(
                ProjectStageRow(
                    project_id=project_id,
                    revision=outcome.revision,
                    stage_type=stage.stage_type,
                    ordinal=stage.ordinal,
                    status=stage.status.value,
                    label=stage.label,
                    input_fingerprint=stage.input_fingerprint,
                    provider=stage.provider.value if stage.provider else None,
                    model=stage.model,
                    current_job_id=stage.current_job_id,
                    last_checkpoint=stage.last_checkpoint,
                    waiting_reason=stage.waiting_reason,
                    quota_reset_at=stage.quota_reset_at,
                    artifact_ids=list(stage.artifact_ids),
                    started_at=stage.started_at,
                    finished_at=stage.finished_at,
                )
            )

        row.current_revision = outcome.revision
        row.title = str(content.get("title") or row.title)
        row.status = outcome.project_status.value
        row.current_stage = outcome.current_stage
        row.last_completed_stage = outcome.last_completed_stage
        row.modified_at = utcnow()

        self.record_event(
            project_id,
            event_type="REVISION_SAVED",
            message="Vznikla neměnná revize projektu.",
            payload={
                "reason": reason,
                "sha256": outcome.content_sha256,
                "revision_id": outcome.revision_id,
                "changed_fields": list(outcome.changed_fields),
                "impact": dict(outcome.impact),
            },
            revision=outcome.revision,
            actor_id=actor_id,
            request_id=request_id,
        )
        self._session.flush()
        return outcome

    def update_settings(
        self,
        project_id: str,
        *,
        title: str | None = None,
        tags: Sequence[str] | None = None,
        pinned: bool | None = None,
        preferred_provider: Any = None,
        provider_policy: Any = None,
        max_api_cost_usd: float | None = None,
        actor_id: str | None = None,
    ) -> Project:
        """Update project header settings.

        Provider and budget changes are recorded as project events because they
        alter cost and provenance behaviour, and must be auditable after the fact.
        """
        self._scope.require(Permission.EDIT_STUDY)

        row = self._row(project_id)
        changes: dict[str, Any] = {}

        if title is not None and title.strip():
            row.title = title.strip()
            changes["title"] = row.title
        if tags is not None:
            row.tags = list(tags)
            changes["tags"] = row.tags
        if pinned is not None:
            row.pinned = bool(pinned)
        if preferred_provider is not None:
            provider, policy = resolve_provider_defaults(
                preferred_provider=preferred_provider,
                provider_policy=provider_policy
                if provider_policy is not None
                else row.provider_policy,
            )
            changes["provider"] = {"from": row.preferred_provider, "to": provider.value}
            row.preferred_provider = provider.value
            row.provider_policy = policy.value
        elif provider_policy is not None:
            from ..domain.providers import normalize_policy

            changes["provider_policy"] = {
                "from": row.provider_policy,
                "to": normalize_policy(provider_policy).value,
            }
            row.provider_policy = normalize_policy(provider_policy).value
        if max_api_cost_usd is not None:
            if max_api_cost_usd < 0:
                raise ValueError("max_api_cost_usd must not be negative")
            changes["max_api_cost_usd"] = {"from": row.max_api_cost_usd, "to": max_api_cost_usd}
            row.max_api_cost_usd = float(max_api_cost_usd)

        row.modified_at = utcnow()

        if changes:
            self.record_event(
                project_id,
                event_type="SETTINGS_UPDATED",
                message="Nastavení projektu bylo změněno.",
                payload=changes,
                revision=row.current_revision,
                actor_id=actor_id,
            )
        self._session.flush()
        return _to_domain(row)

    def move_to_trash(self, project_id: str, *, actor_id: str | None = None) -> Project:
        """Soft-delete a project. Bytes and history are retained."""
        self._scope.require(Permission.EDIT_STUDY)
        row = self._row(project_id)
        row.trashed_at = utcnow()
        row.status = ProjectStatus.TRASHED.value
        self.record_event(
            project_id,
            event_type="PROJECT_TRASHED",
            message="Projekt byl přesunut do koše.",
            revision=row.current_revision,
            actor_id=actor_id,
        )
        self._session.flush()
        return _to_domain(row)

    def restore_from_trash(self, project_id: str, *, actor_id: str | None = None) -> Project:
        """Restore a soft-deleted project."""
        self._scope.require(Permission.EDIT_STUDY)
        row = self._session.scalar(
            select(ProjectRow).where(ProjectRow.project_id == project_id, *self._scope_filter())
        )
        if row is None:
            raise ProjectNotFound(project_id)
        row.trashed_at = None
        has_content = row.current_revision >= 1
        row.status = (
            ProjectStatus.READY_TO_CONTINUE.value if has_content else ProjectStatus.DRAFT.value
        )
        self.record_event(
            project_id,
            event_type="PROJECT_RESTORED",
            message="Projekt byl obnoven z koše.",
            revision=row.current_revision,
            actor_id=actor_id,
        )
        self._session.flush()
        return _to_domain(row)

    def purge(self, project_id: str) -> None:
        """Permanently delete a trashed project and everything under it.

        Only a project already in the trash can be purged, so a hard delete is
        always a deliberate second action, and it needs delete authority rather
        than ordinary edit rights.
        """
        self._scope.require(Permission.DELETE_STUDY)
        row = self._row(project_id)
        if row.trashed_at is None:
            raise ValueError("only a trashed project can be purged")
        self._session.execute(delete(ProjectRow).where(ProjectRow.project_id == project_id))
        self._session.flush()
