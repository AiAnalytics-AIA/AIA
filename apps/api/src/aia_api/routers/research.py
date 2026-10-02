"""Research execution under the Study: Design Revisions, and the runs that execute them.

ADR 0016. Every route resolves the Study through ``ScopeResolver`` first
(``StudyScopeDep``): a Study outside the caller's scope is a 404, and so is a
revision or run that is not the Study's own. Inside a Study the caller can see,
a missing permission is a 403. No route takes a client, organization or unit
project id: the browser supplies content, never authority.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any

from aia_core.application.analysis_results import ReconstructionRefused, reconstruct_run
from aia_core.application.research import (
    DesignNotReady,
    ResearchAgentJobs,
    ResearchRunNotFound,
    ResearchRunNotRetryable,
    ResearchRuns,
    research_artifacts,
)
from aia_core.application.workflows import StartedRun
from aia_core.domain.design import DesignRejected, DesignRevision
from aia_core.domain.research_agents import ResearchAction
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from aia_core.infrastructure.artifact_repository import ArtifactNotFound
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.workflow_repository import RuntimeParkNotResumable
from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import ArtifactStoreDep, SessionDep, StudyScopeDep
from ..schemas.projects import ErrorResponse
from ..schemas.runs import ArtifactResponse, RunEventResponse
from .runs import artifact_corrupt, artifact_response

router = APIRouter(
    prefix="/studies/{study_id}",
    tags=["research"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

RevisionIdPath = Annotated[str, Path(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")]
RunIdPath = Annotated[str, Path(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]
ArtifactIdPath = Annotated[str, Path(max_length=64, pattern=r"^ART-[0-9a-f]{1,32}$")]

# JSON payloads above this size are not inlined (as for project artifacts).
_INLINE_PAYLOAD_LIMIT = 1024 * 1024

# Respondent-level data is never inlined to the browser, whatever its size: the
# results screens read what was computed from it, not the rows (ADR 0016).
_NEVER_INLINED = frozenset({"research_fieldwork_dataset"})

# INTERNAL_ONLY while PROGRESS D6 is open (ADR 0016 decision 6): the Study's own
# researchers may inspect it; a viewer or reviewer may not.
_RESEARCHERS_ONLY = frozenset({"research_sociomap", "research_analysis_module"})


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class DesignSubmission(BaseModel):
    """The design the browser holds. Content only: identity comes from the Study."""

    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]
    source_stage: str = Field(max_length=32)


class DesignRevisionResponse(BaseModel):
    """One immutable Design Revision of the Study."""

    model_config = ConfigDict(extra="forbid")

    revision_id: str
    study_id: str
    revision: int
    content_sha256: str
    parent_revision: int | None
    source_stage: str
    created_by: str | None
    created_at: datetime
    created: bool | None = None
    content: dict[str, Any] | None = None


class DesignRevisionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DesignRevisionResponse]


class RunStart(BaseModel):
    """Start the research workflow over one Design Revision of this Study."""

    model_config = ConfigDict(extra="forbid")

    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")


class ResearchStepResponse(BaseModel):
    """One step of a research run: its state, its checkpoint, what it produced."""

    model_config = ConfigDict(extra="forbid")

    node_key: str
    kind: str
    stage_type: str
    status: str
    waiting_reason: str | None
    attempts_recorded: int
    max_attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    failure_class: str | None
    error_message: str | None
    artifact_id: str | None
    #: ``SYNTHETIC_FIXTURE`` when the step's output came from fictional fieldwork.
    data_origin: str | None = None


class ResearchRunResponse(BaseModel):
    """A research run of this Study, as a person needs to read it (ADR 0016)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    study_id: str
    design_revision_id: str
    design_revision: int
    status: str
    phase: str
    needs_attention: bool
    is_terminal: bool
    retryable: bool
    cancel_requested: bool
    fieldwork_source: str
    retry_of: str | None
    created: bool | None = None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[ResearchStepResponse] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    #: Only with ``VIEW_COSTS``; ``None`` otherwise, never zero.
    actual_cost_usd: float | None = None


class ResearchRunList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResearchRunResponse]


class ReadinessCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    message: str


class ReadinessResponse(BaseModel):
    """Whether a Design Revision can run in AIA: AIA's structural checks, by name."""

    model_config = ConfigDict(extra="forbid")

    design_revision_id: str
    rules: str
    ready: bool
    checks: list[ReadinessCheckResponse]
    questions: int
    batteries: int
    objects: int
    n: int | None
    #: The deployment's fieldwork source: ``ai_runtime`` parks until it exists.
    fieldwork_source: str


def _not_ready(readiness: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "design_not_ready",
            "message": "The design does not pass the readiness checks.",
            "details": {
                "failed": [
                    c.model_dump(mode="json") for c in readiness.checks if c.status == "FAIL"
                ]
            },
        },
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _not_found(what: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": f"{what}_not_found", "message": "No such resource."},
    )


def _refused(exc: ScopeDenied) -> HTTPException:
    """A permission or lifecycle refusal inside a Study the caller can see: 403."""
    code = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
    message = (
        "The study no longer accepts changes."
        if code == "study_closed"
        else "Your role on this study does not permit that."
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message, "details": {"reason": exc.reason}},
    )


def _revision(
    r: DesignRevision, *, created: bool | None = None, content: dict[str, Any] | None = None
) -> DesignRevisionResponse:
    return DesignRevisionResponse(
        revision_id=r.revision_id,
        study_id=r.study_id,
        revision=r.revision,
        content_sha256=r.content_sha256,
        parent_revision=r.parent_revision,
        source_stage=r.source_stage,
        created_by=r.created_by,
        created_at=r.created_at,
        created=created,
        content=content,
    )


# --------------------------------------------------------------------------- #
# Design Revisions
# --------------------------------------------------------------------------- #


@router.post(
    "/design/revisions",
    response_model=DesignRevisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the research design as a new Design Revision",
    responses={200: {"description": "Identical to the newest revision: nothing new"}},
)
def submit_design(
    body: DesignSubmission, scope: StudyScopeDep, session: SessionDep, response: Response
) -> DesignRevisionResponse:
    """Store the design as an immutable, Study-scoped revision (ADR 0016 decision 1).

    Needs ``EDIT_STUDY`` on an open research Study. Content identical to the
    newest revision answers 200 with that revision; anything else is a new one.
    """
    try:
        revision, created = StudyDesignRepository(session, scope).submit(
            content=body.content, source_stage=body.source_stage
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.reason, "message": str(exc)},
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return _revision(revision, created=created)


@router.get(
    "/design/revisions",
    response_model=DesignRevisionList,
    summary="The Study's Design Revisions, newest first",
)
def list_designs(
    scope: StudyScopeDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> DesignRevisionList:
    items = StudyDesignRepository(session, scope).revisions(limit=limit)
    return DesignRevisionList(items=[_revision(r) for r in items])


@router.get(
    "/design/revisions/{revision_id}",
    response_model=DesignRevisionResponse,
    summary="One Design Revision, with its content",
)
def get_design(
    revision_id: RevisionIdPath, scope: StudyScopeDep, session: SessionDep
) -> DesignRevisionResponse:
    """A revision of this Study only; another Study's revision id is a 404."""
    repo = StudyDesignRepository(session, scope)
    try:
        return _revision(repo.get(revision_id), content=repo.content(revision_id))
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc


# --------------------------------------------------------------------------- #
# Research runs
# --------------------------------------------------------------------------- #


def _fieldwork_source(request: Request) -> Any:
    """The composition's fieldwork source: settings decide, never the request."""
    return request.app.state.settings.research_fieldwork_source


def _step(s: dict[str, Any]) -> ResearchStepResponse:
    attempts = s.get("attempts") or []
    last = attempts[-1] if attempts else None
    error = (last or {}).get("error") or {}
    output = s.get("output") or {}
    return ResearchStepResponse(
        node_key=s["node_key"],
        kind=s["kind"],
        stage_type=s["stage_type"],
        status=s["status"].value,
        waiting_reason=s.get("waiting_reason"),
        attempts_recorded=s["attempts_recorded"],
        max_attempts=s["max_attempts"],
        started_at=attempts[0]["started_at"] if attempts else None,
        finished_at=s.get("finished_at"),
        failure_class=last["failure_class"].value if last and last["failure_class"] else None,
        error_message=str(error.get("message")) if error.get("message") else None,
        artifact_id=str(output["artifact_id"]) if output.get("artifact_id") else None,
        data_origin=str(output["data_origin"]) if output.get("data_origin") else None,
    )


def _run(
    run: dict[str, Any], scope: StudyContext, *, created: bool | None = None
) -> ResearchRunResponse:
    meta = run.get("metadata") or {}
    steps = [_step(s) for s in run.get("steps", [])]
    cost: float | None = None
    if scope.has(Permission.VIEW_COSTS) and "steps" in run:
        cost = sum(
            float(a.get("actual_cost_usd") or 0.0)
            for s in run["steps"]
            for a in s.get("attempts", [])
        )
    return ResearchRunResponse(
        run_id=run["run_id"],
        study_id=scope.study_id,
        design_revision_id=str(meta.get("design_revision_id", "")),
        design_revision=int(meta.get("design_revision", run.get("project_revision", 0))),
        status=run["status"].value,
        phase=run["phase"].value,
        needs_attention=run["status"].needs_attention,
        is_terminal=run["status"].is_terminal,
        retryable=bool(run["retryable"]),
        cancel_requested=bool(run["cancel_requested"]),
        fieldwork_source=str(meta.get("fieldwork_source", "")),
        retry_of=meta.get("retry_of"),
        created=created,
        created_at=run.get("created_at"),
        started_at=run.get("started_at"),
        finished_at=run.get("finished_at"),
        steps=steps,
        artifact_ids=[s.artifact_id for s in steps if s.artifact_id],
        actual_cost_usd=cost,
    )


def _started(runs: ResearchRuns, started: StartedRun, response: Response) -> ResearchRunResponse:
    if started.created:
        response.headers["Location"] = (
            f"/api/v1/studies/{runs.scope.study_id}/research/runs/{started.run_id}"
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _run(runs.get(started.run_id), runs.scope, created=started.created)


@router.get(
    "/research/readiness",
    response_model=ReadinessResponse,
    summary="Can this Design Revision run in AIA?",
)
def readiness(
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    design_revision_id: Annotated[str, Query(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")],
) -> ReadinessResponse:
    """Compile the revision and run AIA's structural checks, without starting anything.

    The 18.6.6 technical preflight is not these checks and is not claimed.
    """
    try:
        spec, result = ResearchRuns(session, scope).readiness(design_revision_id)
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
    return ReadinessResponse(
        design_revision_id=design_revision_id,
        rules=result.rules,
        ready=result.ready,
        checks=[
            ReadinessCheckResponse(id=c.id, status=c.status.value, message=c.message)
            for c in result.checks
        ],
        questions=len(spec.questions) if spec else 0,
        batteries=len(spec.batteries) if spec else 0,
        objects=sum(len(b.objects) for b in spec.batteries) if spec else 0,
        n=spec.n if spec else None,
        fieldwork_source=str(_fieldwork_source(request).value),
    )


@router.post(
    "/research/runs",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the research workflow over a Design Revision",
    responses={200: {"description": "This revision already has a run: that run"}},
)
def start_run(
    body: RunStart,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
) -> ResearchRunResponse:
    """Idempotent per Design Revision: a double submission gets the existing run.

    Needs ``RUN_WORKFLOW`` on an open Study. The fieldwork source is the
    deployment's, never the request's.
    """
    runs = ResearchRuns(session, scope)
    try:
        started = runs.start(
            design_revision_id=body.design_revision_id,
            fieldwork_source=_fieldwork_source(request),
            analysis_enabled=request.app.state.settings.ai_analysis_enabled,
        )
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except DesignRevisionNotFound as exc:
        raise _not_found("design_revision") from exc
    except DesignNotReady as exc:
        raise _not_ready(exc.readiness) from exc
    return _started(runs, started, response)


@router.get("/research/runs", response_model=ResearchRunList, summary="The Study's research runs")
def list_runs(
    scope: StudyScopeDep, session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> ResearchRunList:
    runs = ResearchRuns(session, scope)
    return ResearchRunList(items=[_run(r, scope) for r in runs.runs(limit=limit)])


@router.get(
    "/research/runs/{run_id}", response_model=ResearchRunResponse, summary="One research run"
)
def get_run(run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep) -> ResearchRunResponse:
    try:
        return _run(ResearchRuns(session, scope).get(run_id), scope)
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc


@router.get(
    "/research/runs/{run_id}/events",
    response_model=list[RunEventResponse],
    summary="The run's events after a cursor",
)
def run_events(
    run_id: RunIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunEventResponse]:
    try:
        events = ResearchRuns(session, scope).events(run_id, since=since, limit=limit)
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    return [
        RunEventResponse(
            event_id=e["event_id"],
            step_id=e["step_id"],
            attempt_id=e["attempt_id"],
            event_type=e["event_type"],
            level=e["level"],
            message=e["message"],
            payload=e["payload"],
            created_at=e["created_at"],
        )
        for e in events
    ]


@router.post(
    "/research/runs/{run_id}/cancel",
    response_model=ResearchRunResponse,
    summary="Cancel a research run",
)
def cancel_run(run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep) -> ResearchRunResponse:
    """Needs ``CANCEL_WORKFLOW``. A running step stops at its next checkpoint."""
    runs = ResearchRuns(session, scope)
    try:
        runs.cancel(run_id)
        return _run(runs.get(run_id), scope)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc


@router.post(
    "/research/runs/{run_id}/retry",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a failed or cancelled run again",
    responses={
        200: {"description": "This run was already retried: that retry"},
        409: {"model": ErrorResponse, "description": "The run is not failed or cancelled"},
    },
)
def retry_run(
    run_id: RunIdPath,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
) -> ResearchRunResponse:
    """A new run over the same Design Revision, linked to the one it retries."""
    runs = ResearchRuns(session, scope)
    try:
        started = runs.retry(run_id, fieldwork_source=_fieldwork_source(request))
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    except DesignNotReady as exc:
        raise _not_ready(exc.readiness) from exc
    except ResearchRunNotRetryable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "run_not_retryable",
                "message": "Only a failed or cancelled run can be started again.",
                "details": {"status": exc.status.value},
            },
        ) from exc
    return _started(runs, started, response)


@router.get(
    "/research/runs/{run_id}/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
    summary="An artifact the run produced",
)
def run_artifact(
    run_id: RunIdPath,
    artifact_id: ArtifactIdPath,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> ArtifactResponse:
    """Only an artifact this run's steps produced; any other id is a 404.

    Needs ``VIEW_RESULTS``. The bytes are hash-verified on read; a mismatch or a
    missing object marks the artifact CORRUPT, durably, and answers 409 rather
    than serving content that may have been altered.
    """
    try:
        scope.require(Permission.VIEW_RESULTS)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    try:
        produced = ResearchRuns(session, scope).artifact_ids(run_id)
    except ResearchRunNotFound as exc:
        raise _not_found("run") from exc
    if artifact_id not in produced:
        raise _not_found("artifact")
    repo = research_artifacts(session, scope, store)
    try:
        artifact = repo.get(artifact_id)
    except ArtifactNotFound as exc:  # pragma: no cover - a step output names a stored artifact
        raise _not_found("artifact") from exc
    if artifact.artifact_type in _RESEARCHERS_ONLY:
        try:
            scope.require(Permission.EDIT_STUDY)
        except ScopeDenied as exc:
            raise _refused(exc) from exc
    payload: Any = None
    if (
        artifact.content_type == "application/json"
        and artifact.size_bytes <= _INLINE_PAYLOAD_LIMIT
        and artifact.artifact_type not in _NEVER_INLINED
    ):
        try:
            payload = repo.read_json(artifact_id)
        except (IntegrityError, ObjectNotFound) as exc:
            raise artifact_corrupt(session) from exc
    return artifact_response(artifact, payload)


@router.get(
    "/research/runs/{run_id}/analysis",
    response_model=dict[str, Any],
    summary="Evidence-checked internal analysis outcomes of a research run",
)
def run_analysis(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """Recheck stored outcomes against the frozen sources before showing prose."""
    try:
        scope.require(Permission.EDIT_STUDY)
        analysis = reconstruct_run(session, scope, store, run_id=run_id)
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except ReconstructionRefused as exc:
        if exc.reason == "run_not_found":
            raise _not_found("run") from exc
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    return {
        "run_id": run_id,
        "complete": analysis.complete,
        "internal_only": True,
        "synthetic": any(o.record.labels.simulated_respondents for o in analysis.modules.values()),
        "pending": {module.value: state for module, state in analysis.pending.items()},
        "modules": {
            module.value: {
                "outcome": outcome.outcome.value,
                "artifact_id": outcome.artifact_id,
                "summary": outcome.result.summary if outcome.result else None,
                "research_question_answers": [
                    {
                        "question": answer.question,
                        "answer": answer.answer,
                        "claim_ids": answer.claim_ids,
                    }
                    for answer in outcome.result.research_question_answers
                ]
                if outcome.result
                else [],
                "key_findings": [
                    {"text": finding.text, "claim_ids": finding.claim_ids}
                    for finding in outcome.result.key_findings
                ]
                if outcome.result
                else [],
                "claims": [
                    {
                        "claim_id": claim.claim_id,
                        "evidence_ref": claim.row.evidence_ref,
                        "value": claim.value,
                        "indicative": claim.indicative,
                        "data_origin": claim.row.data_origin.value
                        if claim.row.data_origin
                        else None,
                    }
                    for claim in outcome.result.claims
                ]
                if outcome.result
                else [],
                "violations": [
                    {
                        "code": violation.code.value,
                        "subject": violation.subject,
                        "detail": violation.detail,
                    }
                    for violation in outcome.violations
                ],
            }
            for module, outcome in analysis.modules.items()
        },
    }


# Native agent jobs: the API enqueues and reads; the worker owns every model call.
class AgentJobStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    action: ResearchAction
    instruction: str = Field(default="", max_length=8000)
    #: A stored prompt version to run instead of the active one, to test a draft (ADR 0019).
    #: Organization administrators only; the job records which prompt it ran.
    prompt_version: int | None = Field(default=None, ge=1)


class AgentProposalAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")


class AgentJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    design_revision_id: str
    action: str
    status: str
    is_terminal: bool
    needs_attention: bool
    context_sha256: str
    harness_version: str
    #: The prompt this job was queued with (``1`` or ``e<n>``) and whether the code's
    #: wording or an administrator's edit ran. ``None`` for a job queued before ADR 0019.
    prompt_version: str | None = None
    prompt_origin: str | None = None
    created_at: datetime | None
    steps: list[ResearchStepResponse]
    actual_cost_usd: float | None


def _agent_response(run: dict[str, Any], scope: StudyContext) -> AgentJobResponse:
    meta = run["metadata"]
    return AgentJobResponse(
        run_id=run["run_id"],
        design_revision_id=meta["design_revision_id"],
        action=meta["action"],
        status=run["status"].value,
        is_terminal=run["status"].is_terminal,
        needs_attention=run["status"].needs_attention,
        context_sha256=meta["context_sha256"],
        harness_version=meta["harness_version"],
        prompt_version=meta.get("prompt_version"),
        prompt_origin=meta.get("prompt_origin"),
        created_at=run.get("created_at"),
        steps=[_step(s) for s in run["steps"]],
        actual_cost_usd=sum(
            float(a.get("actual_cost_usd") or 0) for s in run["steps"] for a in s["attempts"]
        )
        if scope.has(Permission.VIEW_COSTS)
        else None,
    )


@contextmanager
def _agent_errors(session: SessionDep) -> Iterator[None]:
    try:
        yield
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except (ResearchRunNotFound, DesignRevisionNotFound) as exc:
        raise _not_found("agent_job") from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    except RuntimeParkNotResumable as exc:
        raise HTTPException(
            status_code=409, detail={"code": "runtime_park_not_resumable", "message": str(exc)}
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        # The proposal's bytes failed verification on read: keep its CORRUPT mark.
        raise artifact_corrupt(session) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_agent_input", "message": str(exc)}
        ) from exc


@router.post("/research/agent-jobs", response_model=AgentJobResponse, status_code=201)
def start_agent_job(
    body: AgentJobStart, scope: StudyScopeDep, session: SessionDep, response: Response
) -> AgentJobResponse:
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        started = jobs.start(
            design_revision_id=body.design_revision_id,
            action=body.action,
            instruction=body.instruction,
            prompt_version=body.prompt_version,
        )
        if not started.created:
            response.status_code = 200
        return _agent_response(jobs.get(started.run_id), scope)


@router.get("/research/agent-jobs", response_model=list[AgentJobResponse])
def list_agent_jobs(scope: StudyScopeDep, session: SessionDep) -> list[AgentJobResponse]:
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        return [_agent_response(jobs.get(r["run_id"]), scope) for r in jobs.jobs()]


@router.get("/research/agent-jobs/{run_id}", response_model=AgentJobResponse)
def read_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    with _agent_errors(session):
        return _agent_response(ResearchAgentJobs(session, scope).get(run_id), scope)


@router.post("/research/agent-jobs/{run_id}/cancel", response_model=AgentJobResponse)
def cancel_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        jobs.cancel(run_id)
        return _agent_response(jobs.get(run_id), scope)


@router.post("/research/agent-jobs/{run_id}/resume", response_model=AgentJobResponse)
def resume_agent_job(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> AgentJobResponse:
    """Retry only a frozen, unbilled job parked before its runtime was available."""
    with _agent_errors(session):
        jobs = ResearchAgentJobs(session, scope)
        jobs.resume_runtime_park(run_id)
        return _agent_response(jobs.get(run_id), scope)


@router.get("/research/agent-jobs/{run_id}/result", response_model=dict[str, Any])
def read_agent_result(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    with _agent_errors(session):
        result = ResearchAgentJobs(session, scope).result(run_id, store=store)
        if not scope.has(Permission.VIEW_COSTS):
            result["provenance"].pop("cost_usd", None)
        return result


@router.post("/research/agent-jobs/{run_id}/accept", response_model=DesignRevisionResponse)
def accept_agent_result(
    run_id: RunIdPath,
    body: AgentProposalAccept,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> DesignRevisionResponse:
    with _agent_errors(session):
        revision, created = ResearchAgentJobs(session, scope).accept(
            run_id, store=store, expected_revision_id=body.expected_revision_id
        )
        return _revision(revision, created=created)
