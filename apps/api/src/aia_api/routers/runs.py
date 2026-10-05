"""Workflow runs and artifacts, under a project, under a study.

Starting a run is the one write here, and the handler makes no decision about
it: the workflow type names a template the domain owns, the application use
case validates the project and creates the rows, and a worker does the work
later. Nothing in this module claims, completes or fails an attempt -- that is
the layering rule `tools/layer_check.sh` enforces on this package.
"""

from __future__ import annotations

from typing import Annotated, Any

from aia_core.application.workflows import start_workflow
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.domain.workflow_templates import UnknownWorkflowType
from aia_core.infrastructure.artifact_repository import (
    Artifact,
    ArtifactNotFound,
    ArtifactRepository,
)
from aia_core.infrastructure.repositories import ProjectNotFound
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from aia_core.infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..dependencies import (
    ArtifactStoreDep,
    SessionDep,
    StudyIdPath,
    StudyScopeDep,
    require_permission,
)
from ..schemas.projects import ErrorResponse
from ..schemas.runs import (
    ArtifactResponse,
    AttemptResponse,
    RunCreateRequest,
    RunEventResponse,
    RunListResponse,
    RunResponse,
    RunSummaryResponse,
    StepRunResponse,
)

router = APIRouter(
    prefix="/studies/{study_id}/projects/{project_id}",
    tags=["runs"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        404: {"model": ErrorResponse, "description": "Not found, or not in your organization"},
    },
)

ProjectIdPath = Annotated[str, Path(max_length=64, pattern=r"^PRJ-[0-9a-f]{1,32}$")]
RunIdPath = Annotated[str, Path(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]
ArtifactIdPath = Annotated[str, Path(max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")]

# JSON payloads above this size are not inlined; the client reads them by URL later.
_INLINE_PAYLOAD_LIMIT = 1024 * 1024


def _not_found(code: str, what: str) -> HTTPException:
    """One 404 for missing and for another tenant's, so existence is not disclosed."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": code, "message": f"No such {what}."},
    )


def _denied(exc: ScopeDenied) -> HTTPException:
    """A role or study-state refusal on a study the caller demonstrably holds is 403.

    Anything else -- an unknown study, another organization's -- stays 404, exactly as
    `dependencies.get_study_context` renders it.
    """
    if exc.reason in ("insufficient_role", "study_closed"):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "insufficient_role"
                if exc.reason == "insufficient_role"
                else "study_closed",
                "message": str(exc),
                "details": {"reason": exc.reason},
            },
        )
    return _not_found("not_found", "resource")


def _summary(run: dict[str, Any]) -> dict[str, Any]:
    run_status = WorkflowRunStatus(run["status"])
    return {
        "run_id": run["run_id"],
        "status": run_status.value,
        "needs_attention": run_status.needs_attention,
        "is_terminal": run_status.is_terminal,
        "workflow_type": run["workflow_type"],
        "project_id": run["project_id"],
        "project_revision": run["project_revision"],
        "cancel_requested": bool(run.get("cancel_requested", False)),
        "created_at": run.get("created_at"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
    }


def _run_response(run: dict[str, Any], *, created: bool | None = None) -> RunResponse:
    return RunResponse(
        **_summary(run),
        created=created,
        steps=[
            StepRunResponse(
                step_id=s["step_id"],
                node_key=s["node_key"],
                kind=s["kind"],
                status=s["status"].value,
                stage_type=s["stage_type"],
                attempts_recorded=s["attempts_recorded"],
                attempts_consumed=s["attempts_consumed"],
                max_attempts=s["max_attempts"],
                waiting_reason=s.get("waiting_reason"),
                runnable_after=s.get("runnable_after"),
                output=dict(s.get("output") or {}),
                attempts=[
                    AttemptResponse(
                        attempt_id=a["attempt_id"],
                        attempt_number=a["attempt_number"],
                        status=a["status"].value,
                        worker_id=a.get("worker_id"),
                        failure_class=a["failure_class"].value if a.get("failure_class") else None,
                        error=dict(a.get("error") or {}),
                        provider=a.get("provider"),
                        model=a.get("model"),
                        estimated_cost_usd=a.get("estimated_cost_usd"),
                        actual_cost_usd=a.get("actual_cost_usd"),
                        started_at=a.get("started_at"),
                        finished_at=a.get("finished_at"),
                    )
                    for a in s.get("attempts", [])
                ],
            )
            for s in run["steps"]
        ],
    )


def artifact_response(artifact: Artifact, payload: Any) -> ArtifactResponse:
    """An artifact's metadata and provenance, with its payload when one was read."""
    return ArtifactResponse(
        artifact_id=artifact.artifact_id,
        project_id=artifact.project_id,
        revision=artifact.revision,
        stage_type=artifact.stage_type,
        artifact_type=artifact.artifact_type,
        content_type=artifact.content_type,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        status=artifact.status.value,
        input_fingerprint_prefix=artifact.input_fingerprint[:12],
        provider=artifact.provider.value if artifact.provider else None,
        model=artifact.model,
        runtime_version=artifact.runtime_version,
        produced_by_job_id=artifact.produced_by_job_id,
        created_at=artifact.created_at,
        payload=payload,
    )


def artifact_corrupt(session: SessionDep) -> HTTPException:
    """Commit the artifact's CORRUPT mark, then build the 409 that reports it.

    ``ArtifactRepository.read`` flushes the mark into this request's transaction
    and raises. ``get_session`` rolls that transaction back when the exception
    leaves the route, so without this commit the mark goes with it and the
    artifact reads ``VALID`` again -- in every listing, and to ``find_reusable``.
    The same reason ``panel.open_session`` commits its refusal's audit row.

    It commits the whole request, so a route calls it only before it has written
    anything the refusal should undo.
    """
    session.commit()
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "artifact_corrupt",
            "message": "The stored bytes are missing or do not match the recorded hash.",
        },
    )


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


@router.post(
    "/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a workflow run",
)
def create_run(
    study_id: StudyIdPath,
    project_id: ProjectIdPath,
    body: RunCreateRequest,
    scope: Annotated[StudyContext, Depends(require_permission(Permission.RUN_WORKFLOW))],
    session: SessionDep,
    response: Response,
) -> RunResponse:
    """Create a run of the named workflow against the project's current revision.

    Idempotent per revision: starting the same workflow twice on an unchanged
    project returns the existing run with ``created: false`` and a 200, so a
    double click never executes twice. A worker executes the run; this request
    only records it.
    """
    try:
        started = start_workflow(
            session, scope, project_id=project_id, workflow_type=body.workflow_type
        )
    except ProjectNotFound as exc:
        raise _not_found("project_not_found", "project") from exc
    except UnknownWorkflowType as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_workflow_type", "message": str(exc)},
        ) from exc
    except ScopeDenied as exc:
        raise _denied(exc) from exc

    if started.created:
        response.headers["Location"] = (
            f"/api/v1/studies/{study_id}/projects/{project_id}/runs/{started.run_id}"
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _run_response(started.run, created=started.created)


@router.get("/runs", response_model=RunListResponse, summary="List a project's runs")
def list_runs(
    study_id: StudyIdPath,
    project_id: ProjectIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RunListResponse:
    """Newest first, without steps."""
    runs = WorkflowRepository(session, scope).list_runs(project_id=project_id, limit=limit)
    return RunListResponse(items=[RunSummaryResponse(**_summary(r)) for r in runs])


@router.get("/runs/{run_id}", response_model=RunResponse, summary="Get a run")
def get_run(
    study_id: StudyIdPath,
    project_id: ProjectIdPath,
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
) -> RunResponse:
    """The run, its steps, each step's output and append-only attempt history."""
    try:
        run = WorkflowRepository(session, scope).get_run(run_id)
    except WorkflowNotFound as exc:
        raise _not_found("run_not_found", "run") from exc
    if run["project_id"] != project_id:
        raise _not_found("run_not_found", "run")
    return _run_response(run)


@router.get(
    "/runs/{run_id}/events",
    response_model=list[RunEventResponse],
    summary="A run's event feed",
)
def run_events(
    study_id: StudyIdPath,
    project_id: ProjectIdPath,
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunEventResponse]:
    """Events after ``since``, in order. Monotonic ids let a client resume without gaps."""
    repo = WorkflowRepository(session, scope)
    try:
        run = repo.get_run(run_id)
        if run["project_id"] != project_id:
            raise _not_found("run_not_found", "run")
        events = repo.events(run_id, since=since, limit=limit)
    except WorkflowNotFound as exc:
        raise _not_found("run_not_found", "run") from exc
    return [
        RunEventResponse(
            event_id=e["event_id"],
            step_id=e.get("step_id"),
            attempt_id=e.get("attempt_id"),
            event_type=e["event_type"],
            level=e["level"],
            message=e["message"],
            payload=dict(e.get("payload") or {}),
            created_at=e.get("created_at"),
        )
        for e in events
    ]


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    summary="Get an artifact",
)
def get_artifact(
    study_id: StudyIdPath,
    project_id: ProjectIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ArtifactResponse:
    """Metadata and provenance; the decoded payload when it is small JSON.

    The bytes are hash-verified on read. A mismatch or a missing object marks the
    artifact CORRUPT, durably, and answers 409 rather than serving content that
    may have been altered.
    """
    repo = ArtifactRepository(session, scope, store)
    try:
        artifact = repo.get(artifact_id)
    except ArtifactNotFound as exc:
        raise _not_found("artifact_not_found", "artifact") from exc
    if artifact.project_id != project_id:
        raise _not_found("artifact_not_found", "artifact")

    payload: Any = None
    if artifact.content_type == "application/json" and artifact.size_bytes <= _INLINE_PAYLOAD_LIMIT:
        try:
            payload = repo.read_json(artifact_id)
        except (IntegrityError, ObjectNotFound) as exc:
            raise artifact_corrupt(session) from exc
    return artifact_response(artifact, payload)
