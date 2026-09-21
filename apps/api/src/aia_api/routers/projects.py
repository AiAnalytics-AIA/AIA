"""Projects API.

Route handlers contain no business logic. They validate input, delegate to the
repository (which delegates decisions to the domain layer), and map the result to
a response model. Anything resembling a rule belongs in ``aia_core.domain``.

The resource layout is REST for state and command sub-resources for workflow
actions, because "save producing a revision" and "move to trash" are genuinely
commands rather than field updates.
"""

from __future__ import annotations

from typing import Annotated

from aia_core.domain.pipeline import ProjectType, impact_preview, stage_ids
from aia_core.domain.project import Project, ProjectStatus, StageState
from aia_core.domain.providers import ui_label
from aia_core.infrastructure.repositories import ProjectNotFound
from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from ..dependencies import PrincipalDep, ProjectRepositoryDep
from ..observability import request_id_var
from ..schemas.projects import (
    ErrorResponse,
    EventResponse,
    ImpactResponse,
    PageMeta,
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectSaveRequest,
    ProjectSettingsRequest,
    RevisionResponse,
    SaveResponse,
    StageResponse,
)

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Not found, or not in your organization"},
    },
)

ProjectIdPath = Annotated[
    str,
    Path(
        min_length=4,
        max_length=64,
        pattern=r"^PRJ-[0-9a-f]{1,32}$",
        description="Project identifier.",
    ),
]


def _not_found(project_id: str) -> HTTPException:
    """Return the 404 used for both 'missing' and 'belongs to another tenant'."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "project_not_found",
            "message": "No such project.",
            "details": {"project_id": project_id},
        },
    )


def _project_response(project: Project) -> ProjectResponse:
    """Map the domain project to its public representation."""
    return ProjectResponse(
        project_id=project.project_id,
        title=project.title,
        project_type=project.project_type.value,
        status=project.status.value,
        current_revision=project.current_revision,
        current_stage=project.current_stage,
        last_completed_stage=project.last_completed_stage,
        parent_project_id=project.parent_project_id,
        preferred_provider=project.preferred_provider.value,
        provider_label=ui_label(project.preferred_provider),
        provider_policy=project.provider_policy.value,
        max_api_cost_usd=project.max_api_cost_usd,
        tags=list(project.tags),
        pinned=project.pinned,
        archived=project.archived,
        created_at=project.created_at,
        modified_at=project.modified_at,
    )


def _stage_response(stage: StageState) -> StageResponse:
    """Map a stage to its public representation.

    The full input fingerprint stays server-side; only a short prefix is exposed,
    enough for an operator to correlate against logs.
    """
    return StageResponse(
        stage_type=stage.stage_type,
        ordinal=stage.ordinal,
        status=stage.status.value,
        label=stage.label,
        provider=stage.provider.value if stage.provider else None,
        provider_label=ui_label(stage.provider) if stage.provider else None,
        model=stage.model,
        artifact_count=len(stage.artifact_ids),
        waiting_reason=stage.waiting_reason,
        quota_reset_at=stage.quota_reset_at,
        started_at=stage.started_at,
        finished_at=stage.finished_at,
        fingerprint_prefix=stage.input_fingerprint[:12],
        is_complete=stage.is_complete,
    )


def _impact_response(payload: dict) -> ImpactResponse:
    """Map an impact dict to its response model."""
    return ImpactResponse(
        root_stage=payload.get("root_stage"),
        invalidate=list(payload.get("invalidate") or []),
        preserve=list(payload.get("preserve") or []),
        presentation_only=bool(payload.get("presentation_only")),
    )


@router.post(
    "",
    response_model=ProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
def create_project(
    body: ProjectCreateRequest,
    repo: ProjectRepositoryDep,
    principal: PrincipalDep,
    response: Response,
) -> ProjectDetailResponse:
    """Create a project and persist its first revision immediately.

    A project exists from the moment work starts, so an interrupted session leaves
    something resumable rather than nothing.
    """
    project, _ = repo.create(
        title=body.title,
        project_type=body.project_type,
        content=body.content,
        preferred_provider=body.preferred_provider or "claude_code_subscription",
        provider_policy=body.provider_policy or "CLAUDE_CODE_ONLY",
        max_api_cost_usd=body.max_api_cost_usd,
        parent_project_id=body.parent_project_id,
        created_by=principal.user_id,
        request_id=request_id_var.get() or None,
    )

    response.headers["Location"] = f"/api/v1/projects/{project.project_id}"
    return ProjectDetailResponse(
        **_project_response(project).model_dump(),
        stages=[_stage_response(s) for s in repo.stages(project.project_id)],
        content=repo.content(project.project_id),
    )


@router.get("", response_model=ProjectListResponse, summary="List projects")
def list_projects(
    repo: ProjectRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    project_type: Annotated[str | None, Query(pattern="^(research|simulation)$")] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=32)] = None,
    include_archived: bool = False,
    include_trashed: bool = False,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> ProjectListResponse:
    """Return a page of the caller's projects, pinned first then newest."""
    parsed_status: ProjectStatus | None = None
    if status_filter:
        try:
            parsed_status = ProjectStatus(status_filter.upper())
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_status",
                    "message": "Unknown project status.",
                    "details": {"allowed": [s.value for s in ProjectStatus]},
                },
            ) from exc

    page = repo.list_projects(
        limit=limit,
        offset=offset,
        project_type=ProjectType.coerce(project_type) if project_type else None,
        status=parsed_status,
        include_archived=include_archived,
        include_trashed=include_trashed,
        search=search,
    )

    return ProjectListResponse(
        items=[_project_response(p) for p in page.items],
        page=PageMeta(
            total=page.total, limit=page.limit, offset=page.offset, has_more=page.has_more
        ),
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse, summary="Get a project")
def get_project(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    revision: Annotated[int | None, Query(ge=1)] = None,
) -> ProjectDetailResponse:
    """Return a project with the stages and content of one revision."""
    try:
        project = repo.get(project_id)
        return ProjectDetailResponse(
            **_project_response(project).model_dump(),
            stages=[_stage_response(s) for s in repo.stages(project_id, revision)],
            content=repo.content(project_id, revision),
        )
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc


@router.put(
    "/{project_id}/content",
    response_model=SaveResponse,
    summary="Save project content",
)
def save_project(
    project_id: ProjectIdPath,
    body: ProjectSaveRequest,
    repo: ProjectRepositoryDep,
    principal: PrincipalDep,
) -> SaveResponse:
    """Save content, creating an immutable revision only if it materially changed.

    An unchanged save returns ``deduplicated: true`` and the existing revision
    number. This is the expected result of an idle autosave and is not an error.
    """
    try:
        outcome = repo.save(
            project_id,
            content=body.content,
            reason=body.reason,
            force_new_revision=body.force_new_revision,
            explicit_stage=body.explicit_stage,
            actor_id=principal.user_id,
            request_id=request_id_var.get() or None,
        )
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc

    project = repo.get(project_id)
    return SaveResponse(
        project_id=outcome.project_id,
        revision=outcome.revision,
        revision_id=outcome.revision_id,
        deduplicated=outcome.deduplicated,
        content_sha256=outcome.content_sha256,
        changed_fields=list(outcome.changed_fields),
        impact=_impact_response(outcome.impact),
        current_stage=project.current_stage,
        status=project.status.value,
    )


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Update settings")
def update_settings(
    project_id: ProjectIdPath,
    body: ProjectSettingsRequest,
    repo: ProjectRepositoryDep,
    principal: PrincipalDep,
) -> ProjectResponse:
    """Update header settings such as title, tags, provider and budget.

    Provider and budget changes are audited because they alter cost and
    provenance. They do not invalidate completed work.
    """
    try:
        project = repo.update_settings(
            project_id,
            title=body.title,
            tags=body.tags,
            pinned=body.pinned,
            preferred_provider=body.preferred_provider,
            provider_policy=body.provider_policy,
            max_api_cost_usd=body.max_api_cost_usd,
            actor_id=principal.user_id,
        )
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_settings", "message": str(exc)},
        ) from exc

    return _project_response(project)


@router.get(
    "/{project_id}/impact",
    response_model=ImpactResponse,
    summary="Preview what an edit would invalidate",
)
def preview_impact(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    field: Annotated[list[str] | None, Query(description="Project fields about to change")] = None,
    explicit_stage: Annotated[str | None, Query(max_length=64)] = None,
) -> ImpactResponse:
    """Report which stages an edit would reopen, before the user commits to it.

    This powers the "editing this will re-run fieldwork" warning, so a user never
    discards expensive completed work without being told first.
    """
    try:
        project = repo.get(project_id)
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc

    if explicit_stage and explicit_stage not in stage_ids(project.project_type):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unknown_stage",
                "message": "That stage does not exist in this project's pipeline.",
                "details": {"allowed": stage_ids(project.project_type)},
            },
        )

    result = impact_preview(project.project_type, field or [], explicit_stage=explicit_stage)
    return _impact_response(result.as_dict())


@router.get(
    "/{project_id}/revisions",
    response_model=list[RevisionResponse],
    summary="Revision history",
)
def list_revisions(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[RevisionResponse]:
    """Return revision history, newest first."""
    try:
        rows = repo.revisions(project_id, limit=limit)
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc

    return [
        RevisionResponse(
            revision=r.revision,
            revision_id=r.revision_id,
            parent_revision=r.parent_revision,
            content_sha256=r.content_sha256,
            reason=r.reason,
            changed_fields=list(r.changed_fields or []),
            impact=_impact_response(dict(r.impact or {})),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/{project_id}/events",
    response_model=list[EventResponse],
    summary="Project history and audit trail",
)
def list_events(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[EventResponse]:
    """Return the append-only project history, newest first."""
    try:
        rows = repo.events(project_id, limit=limit)
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc

    return [
        EventResponse(
            event_id=e.event_id,
            event_type=e.event_type,
            level=e.level,
            message=e.message,
            revision=e.revision,
            stage_type=e.stage_type,
            payload=dict(e.payload or {}),
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.post(
    "/{project_id}/trash",
    response_model=ProjectResponse,
    summary="Move a project to the trash",
)
def trash_project(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    principal: PrincipalDep,
) -> ProjectResponse:
    """Soft-delete a project. Nothing is destroyed and the action is reversible."""
    try:
        return _project_response(repo.move_to_trash(project_id, actor_id=principal.user_id))
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc


@router.post(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    summary="Restore a project from the trash",
)
def restore_project(
    project_id: ProjectIdPath,
    repo: ProjectRepositoryDep,
    principal: PrincipalDep,
) -> ProjectResponse:
    """Restore a soft-deleted project."""
    try:
        return _project_response(repo.restore_from_trash(project_id, actor_id=principal.user_id))
    except ProjectNotFound as exc:
        raise _not_found(project_id) from exc
