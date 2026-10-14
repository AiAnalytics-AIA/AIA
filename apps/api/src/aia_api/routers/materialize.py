"""A client's dimension materialized from a study (plan ``population-operations.md`` P4d4).

``POST /studies/{study_id}/population/materializations`` -- check a dimension's definition
against LIVE's kept policy and start the ``population_materialize`` run that makes it the
client's owned child (``prepare_materialization`` + ``start_materialization``). The owner is
the study's organization and client, from the scope, never the request. Asking again for the
same child from the same study returns the run that exists (200).

``GET /studies/{study_id}/population/materializations`` and ``…/{run_id}`` -- the study's
materialize runs and one run: where it stands, why it waits, and once it has succeeded the
child's id with the target beside what was achieved (``target_met`` never presumed).

Found only through the Study, like every run; another study's run is a 404.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from aia_core.application.materialize import (
    MaterializationNotFound,
    MaterializationRefused,
    materialization_run,
    materialization_runs,
    prepare_materialization,
    start_materialization,
)
from aia_core.domain.population import MaterializedKind, PopulationError, target_met
from aia_core.domain.population.definition import (
    DEFINITION_CONTRACT,
    DefinitionRefused,
    DimensionDefinition,
    MissingnessRule,
)
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import SessionDep, StudyScopeDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/studies/{study_id}/population",
    tags=["population"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
        404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
    },
)

RunIdPath = Annotated[str, Path(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceBody(_Model):
    knowledge_item_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    span: str = Field(min_length=1, max_length=2000)


class PredictorBody(_Model):
    field: str = Field(min_length=1, max_length=128)
    negative: bool = False
    strength: float = Field(default=1.0, gt=0, le=10)


class DefinitionBody(_Model):
    """A dimension's definition: the K5 contract, checked again by the domain on arrival."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    dimension_id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1)
    #: ``construct`` on the wire; renamed here only because Pydantic's BaseModel has one.
    construct_text: str = Field(alias="construct", min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=200)
    kind: MaterializedKind
    target: float
    evidence: EvidenceBody
    predictors: list[PredictorBody] = Field(min_length=1, max_length=20)
    missingness: MissingnessRule = MissingnessRule.PREDICTOR_MEAN
    range: tuple[float, float]

    def definition(self) -> DimensionDefinition:
        payload: dict[str, Any] = {
            "contract": DEFINITION_CONTRACT,
            **self.model_dump(mode="json", by_alias=True),
        }
        payload["range"] = list(self.range)
        return DimensionDefinition.from_payload(payload)


class MaterializationStart(_Model):
    definition: DefinitionBody


class ChildResult(_Model):
    """What the step registered: the child, and the target beside what it achieved."""

    version_id: str
    label: str
    created: bool
    target: float
    achieved: float
    target_met: bool
    usable_predictors: list[str]


class MaterializationResponse(_Model):
    run_id: str
    status: WorkflowRunStatus
    created: bool | None = None
    created_at: datetime
    finished_at: datetime | None
    dimension_id: str | None
    definition_sha256: str | None
    child_key: str | None
    base_version_id: str | None
    #: The materialize step's state, and why it waits or failed (by name, never guessed).
    step_status: StepRunStatus | None
    waiting_reason: str | None
    refusal_reason: str | None
    child: ChildResult | None


class MaterializationList(_Model):
    items: list[MaterializationResponse]


def _refused(reason: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "materialization_refused",
            "message": message,
            "details": {"reason": reason},
        },
    )


def _forbidden(exc: ScopeDenied) -> HTTPException:
    code = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": str(exc), "details": {"reason": exc.reason}},
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "materialization_not_found", "message": "No such resource."},
    )


def _child(step: dict[str, Any], kind: MaterializedKind | None) -> ChildResult | None:
    output = step.get("output") or {}
    target, achieved = output.get("target"), output.get("achieved")
    if (
        step["status"] is not StepRunStatus.SUCCEEDED
        or kind is None
        or not isinstance(output.get("version_id"), str)
        or not isinstance(target, int | float)
        or not isinstance(achieved, int | float)
    ):
        return None
    return ChildResult(
        version_id=output["version_id"],
        label=str(output.get("label", "")),
        created=bool(output.get("created")),
        target=float(target),
        achieved=float(achieved),
        target_met=target_met(kind, float(target), float(achieved)),
        usable_predictors=[str(p) for p in output.get("usable_predictors", ())],
    )


def _response(run: dict[str, Any], *, created: bool | None = None) -> MaterializationResponse:
    metadata = run.get("metadata") or {}
    steps = run.get("steps") or []
    step = steps[0] if steps else None
    recorded_kind = metadata.get("kind")
    kind = (
        MaterializedKind(recorded_kind)
        if recorded_kind in {k.value for k in MaterializedKind}
        else None
    )
    refusal = None
    if step is not None and step.get("attempts"):
        error = step["attempts"][-1].get("error") or {}
        refusal = error.get("reason") if isinstance(error, dict) else None
    return MaterializationResponse(
        run_id=run["run_id"],
        status=run["status"],
        created=created,
        created_at=run["created_at"],
        finished_at=run.get("finished_at"),
        dimension_id=metadata.get("dimension_id"),
        definition_sha256=metadata.get("definition_sha256"),
        child_key=metadata.get("child_key"),
        base_version_id=metadata.get("base_version_id"),
        step_status=step["status"] if step is not None else None,
        waiting_reason=step.get("waiting_reason") if step is not None else None,
        refusal_reason=refusal,
        child=_child(step, kind) if step is not None else None,
    )


@router.post(
    "/materializations",
    response_model=MaterializationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Materialize a dimension as this study's client's owned child",
    responses={
        200: {"description": "This study already asked for this child: that run"},
        422: {"model": ErrorResponse, "description": "The definition cannot become a child"},
    },
)
def start(
    body: MaterializationStart,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
) -> MaterializationResponse:
    """Check the definition against LIVE and enqueue the run; nothing is derived here."""
    try:
        definition = body.definition.definition()
        request = prepare_materialization(session, scope, definition=definition)
        started = start_materialization(session, scope, request)
    except ScopeDenied as exc:
        raise _forbidden(exc) from exc
    except DefinitionRefused as exc:
        raise _refused(exc.reason, str(exc)) from exc
    except MaterializationRefused as exc:
        raise _refused(exc.reason, str(exc)) from exc
    except PopulationError as exc:
        # LIVE exists but cannot be resolved now (an unusable version, a contract mismatch).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "population_unavailable",
                "message": "LIVE cannot be used as a base now.",
                "details": {"reason": exc.reason},
            },
        ) from exc
    if started.created:
        response.headers["Location"] = (
            f"/api/v1/studies/{scope.study_id}/population/materializations/{started.run_id}"
        )
    else:
        response.status_code = status.HTTP_200_OK
    run = materialization_run(session, scope, started.run_id)
    return _response(run, created=started.created)


@router.get(
    "/materializations",
    response_model=MaterializationList,
    summary="This study's materialize runs",
)
def list_materializations(
    scope: StudyScopeDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MaterializationList:
    items = []
    for summary in materialization_runs(session, scope, limit=limit):
        items.append(_response(materialization_run(session, scope, summary["run_id"])))
    return MaterializationList(items=items)


@router.get(
    "/materializations/{run_id}",
    response_model=MaterializationResponse,
    summary="One materialize run of this study",
)
def get_materialization(
    run_id: RunIdPath, scope: StudyScopeDep, session: SessionDep
) -> MaterializationResponse:
    try:
        return _response(materialization_run(session, scope, run_id))
    except MaterializationNotFound as exc:
        raise _not_found() from exc
