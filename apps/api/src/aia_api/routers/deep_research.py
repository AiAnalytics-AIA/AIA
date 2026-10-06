"""Study-scoped durable Deep Research jobs and their sealed internal evidence.

Every run says why it ran, what it researched and which immutable state it rests on
(ADR 0021): ``purpose``, ``target`` and ``lineage`` on each run, and
``GET …/runs/{run_id}/provenance`` for what a later consumer cites. A start that names no
``purpose`` -- the deployed client's shape -- is a new ``DESIGN_RESEARCH`` run, recorded
``purpose_source: LEGACY_DEFAULT``; only ``DESIGN_RESEARCH`` may be started here.
Interpretation Research is frozen but never enqueued until chunk 30 (409
``interpretation_not_ready``, e.g. on the retry of such a row). A run stored before ADR 0021 reads
``integration_contract: legacy-unversioned`` with no purpose.

A start or a retry on a Study with a spend limit asks first (ADR 0019 gate 2): the
server works out the run's cost ceiling from the deployment's prices
(:func:`deep_research_prices`) and answers 409 ``cost_confirmation_required`` with it,
or 409 ``cost_ceiling_unknown`` when a price it needs is not configured, as a research
run's start does.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.deep_research import (
    BundleNotReady,
    DeepResearchRunNotFound,
    DeepResearchRunNotRetryable,
    DeepResearchRuns,
    InterpretationNotReady,
    LineageChanged,
    NothingToResearch,
    ResearchTargetInvalid,
    ResearchTargetNotFound,
    RunNotGoverned,
    RunSpecCorrupt,
    governed_record,
)
from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.domain.deep_research.budgets import CallKind, ResearchMode
from aia_core.domain.deep_research.contracts import Channel
from aia_core.domain.deep_research.integration import LEGACY_UNVERSIONED, PurposeSource
from aia_core.domain.deep_research.planning import UnknownPreset
from aia_core.domain.run_cost import DeepResearchPrices, RoutePrice
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import DesignRevisionNotFound
from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..config import Settings
from ..dependencies import ArtifactStoreDep, SessionDep, StudyScopeDep
from ..schemas.projects import ErrorResponse
from ..schemas.runs import RunEventResponse
from .research import _cost_refused
from .runs import artifact_corrupt

router = APIRouter(
    prefix="/studies/{study_id}/deep-research",
    tags=["deep-research"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
RunId = Annotated[str, Path(max_length=64, pattern=r"^RUN-[0-9a-f]{1,32}$")]
SnapshotId = Annotated[str, Path(max_length=64, pattern=r"^SNP-[0-9a-f]{1,32}$")]


class DeepResearchStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    design_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    preset_name: Literal["QUICK", "STANDARD", "DEEP", "EXHAUSTIVE"]
    channels: tuple[Channel, ...] = Field(default=(Channel.WEB,), min_length=1, max_length=2)
    #: Why the run runs (ADR 0021). Omitted -- the deployed client's shape -- is
    #: ``DESIGN_RESEARCH`` by the compatibility rule, recorded as such.
    purpose: Literal["DESIGN_RESEARCH"] | None = None
    #: A person's name for the run: shown, never part of its identity.
    title: str | None = Field(default=None, max_length=200)
    #: What the person confirms the run can cost at most. Read only when the study has a
    #: limit the run's ceiling reaches; the server works the ceiling out and holds this to it.
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("channels")
    @classmethod
    def _unique_channels(cls, value: tuple[Channel, ...]) -> tuple[Channel, ...]:
        if len(set(value)) != len(value):
            raise ValueError("channels must be distinct")
        return value


class DeepResearchRetry(BaseModel):
    """A retry's confirmation, when the study's limit asks for one."""

    model_config = ConfigDict(extra="forbid")
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000)


class DeepResearchStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_key: str
    status: str
    waiting_reason: str | None
    attempts_recorded: int
    artifact_id: str | None
    error_message: str | None


class DeepResearchRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    study_id: str
    #: ``aia-deep-research-run-spec-1``, or ``legacy-unversioned`` for a run stored before
    #: ADR 0021: then ``purpose``, ``target``, ``lineage`` and the fingerprint are null.
    integration_contract: str
    purpose: str | None
    purpose_source: str | None
    target: dict[str, Any] | None
    lineage: dict[str, Any] | None
    run_spec_fingerprint: str | None
    title: str | None
    design_revision_id: str
    preset: str
    channels: list[str]
    status: str
    phase: str
    is_terminal: bool
    needs_attention: bool
    retryable: bool
    created: bool | None
    created_at: datetime | None
    steps: list[DeepResearchStep]
    actual_cost_usd: float | None


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "deep_research_not_found", "message": "No such resource."}
    )


def _refused(exc: ScopeDenied) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": "study_closed" if exc.reason == "study_closed" else "insufficient_role",
            "message": "This study does not permit that operation.",
        },
    )


def deep_research_prices(settings: Settings) -> DeepResearchPrices:
    """What each kind of call a Deep Research run makes may cost, as this deployment says.

    Every research agent reserves the research agents' configured reservation per request
    (``aia_executors.deep_research_runtime`` composes them so); unset, it is unknown. The
    only retrieval a deployment composes is the public Wikipedia route, priced at zero
    (``aia_executors.deep_research_live``); off, nothing is searched. Triage, the focused
    crawl, the connectors and Common Crawl are composed by no deployment yet (chunk 23
    wires them with their dated prices), so nothing is sent on them.
    """
    research = RoutePrice.of(settings.ai_research_reservation_usd)
    web = RoutePrice.per_call(0.0) if settings.deep_research_wikipedia_enabled else RoutePrice.off()
    off = RoutePrice.off()
    return DeepResearchPrices(
        {
            CallKind.PLANNER: research,
            CallKind.LEAD: research,
            CallKind.INTERNAL_INVESTIGATOR: research,
            CallKind.INVESTIGATOR: research,
            CallKind.VERIFIER: research,
            CallKind.SYNTHESIZER: research,
            CallKind.SEARCH: web,
            CallKind.FETCH: web,
            CallKind.TRIAGE: off,
            CallKind.CRAWL_FETCH: off,
            CallKind.CONNECTOR: off,
            CallKind.URL_INDEX_QUERY: off,
            CallKind.ARCHIVE_FETCH: off,
        }
    )


def deep_research_mode(settings: Settings) -> ResearchMode:
    """The mode the worker composes from the same switches (the lead needs agent-directed)."""
    if settings.deep_research_lead:
        return ResearchMode.LEAD
    if settings.deep_research_agent_directed:
        return ResearchMode.AGENT_DIRECTED
    return ResearchMode.PLANNED


@contextmanager
def _errors(session: SessionDep) -> Iterator[None]:
    try:
        yield
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except (DeepResearchRunNotFound, DesignRevisionNotFound, ResearchTargetNotFound) as exc:
        raise _not_found() from exc
    except (NothingToResearch, UnknownPreset, ResearchTargetInvalid) as exc:
        raise HTTPException(
            status_code=422, detail={"code": "research_input", "message": str(exc)}
        ) from exc
    except InterpretationNotReady as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except LineageChanged as exc:
        raise HTTPException(
            status_code=409, detail={"code": "lineage_changed", "message": str(exc)}
        ) from exc
    except RunSpecCorrupt as exc:
        raise HTTPException(
            status_code=409, detail={"code": "run_spec_corrupt", "message": str(exc)}
        ) from exc
    except RunNotGoverned as exc:
        raise HTTPException(
            status_code=409, detail={"code": "run_not_governed", "message": str(exc)}
        ) from exc
    except DeepResearchRunNotRetryable as exc:
        raise HTTPException(
            status_code=409, detail={"code": "run_not_retryable", "message": str(exc)}
        ) from exc
    except (BundleNotReady, ValidationError) as exc:
        raise HTTPException(
            status_code=409, detail={"code": "bundle_not_ready", "message": str(exc)}
        ) from exc
    except (IntegrityError, ObjectNotFound) as exc:
        raise artifact_corrupt(session) from exc


def _response(
    run: dict[str, Any], scope: StudyContext, *, created: bool | None = None
) -> DeepResearchRun:
    steps = run.get("steps") or []
    meta = run["metadata"]
    record = governed_record(meta)
    return DeepResearchRun(
        run_id=run["run_id"],
        study_id=scope.study_id,
        integration_contract=str(meta["integration_contract"])
        if record is not None
        else LEGACY_UNVERSIONED,
        purpose=record.purpose.value if record is not None else None,
        purpose_source=record.purpose_source.value if record is not None else None,
        target=record.target.model_dump(mode="json") if record is not None else None,
        lineage=record.lineage.model_dump(mode="json") if record is not None else None,
        run_spec_fingerprint=record.run_spec_fingerprint if record is not None else None,
        title=record.title if record is not None else None,
        design_revision_id=str(meta["design_revision_id"]),
        preset=str(meta["preset"]),
        channels=list(meta["channels"]),
        status=run["status"].value,
        phase=run["phase"].value if "phase" in run else "QUEUED",
        is_terminal=run["status"].is_terminal,
        needs_attention=run["status"].needs_attention,
        retryable=bool(run.get("retryable", False)),
        created=created,
        created_at=run.get("created_at"),
        steps=[
            DeepResearchStep(
                node_key=step["node_key"],
                status=step["status"].value,
                waiting_reason=step.get("waiting_reason"),
                attempts_recorded=step["attempts_recorded"],
                artifact_id=(step.get("output") or {}).get("artifact_id"),
                error_message=str((step["attempts"][-1].get("error") or {}).get("message"))
                if step.get("attempts") and (step["attempts"][-1].get("error") or {}).get("message")
                else None,
            )
            for step in steps
        ],
        actual_cost_usd=sum(
            float(attempt.get("actual_cost_usd") or 0)
            for step in steps
            for attempt in step.get("attempts", [])
        )
        if scope.has(Permission.VIEW_COSTS)
        else None,
    )


@router.post("/runs", response_model=DeepResearchRun, status_code=201)
def start(
    body: DeepResearchStart,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    response: Response,
) -> DeepResearchRun:
    settings = request.app.state.settings
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        started = runs.start(
            design_revision_id=body.design_revision_id,
            preset_name=body.preset_name,
            channels=body.channels,
            prices=deep_research_prices(settings),
            modes=(deep_research_mode(settings),),
            confirm_cost_usd=body.confirm_cost_usd,
            purpose_source=(
                PurposeSource.EXPLICIT if body.purpose is not None else PurposeSource.LEGACY_DEFAULT
            ),
            title=body.title,
        )
        if not started.created:
            response.status_code = 200
        else:
            response.headers["Location"] = (
                f"/api/v1/studies/{scope.study_id}/deep-research/runs/{started.run_id}"
            )
        return _response(runs.get(started.run_id), scope, created=started.created)
    raise AssertionError("unreachable")


@router.get("/runs", response_model=list[DeepResearchRun])
def list_runs(
    scope: StudyScopeDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DeepResearchRun]:
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        return [_response(runs.get(r["run_id"]), scope) for r in runs.runs(limit=limit)]
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}", response_model=DeepResearchRun)
def get(run_id: RunId, scope: StudyScopeDep, session: SessionDep) -> DeepResearchRun:
    with _errors(session):
        return _response(DeepResearchRuns(session, scope).get(run_id), scope)
    raise AssertionError("unreachable")


@router.post("/runs/{run_id}/cancel", response_model=DeepResearchRun)
def cancel(run_id: RunId, scope: StudyScopeDep, session: SessionDep) -> DeepResearchRun:
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        runs.cancel(run_id)
        return _response(runs.get(run_id), scope)
    raise AssertionError("unreachable")


@router.post("/runs/{run_id}/retry", response_model=DeepResearchRun, status_code=201)
def retry(
    run_id: RunId,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    response: Response,
    body: DeepResearchRetry | None = None,
) -> DeepResearchRun:
    settings = request.app.state.settings
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        started = runs.retry(
            run_id,
            prices=deep_research_prices(settings),
            modes=(deep_research_mode(settings),),
            confirm_cost_usd=body.confirm_cost_usd if body else None,
            store=store,
        )
        if not started.created:
            response.status_code = 200
        return _response(runs.get(started.run_id), scope, created=started.created)
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}/events", response_model=list[RunEventResponse])
def events(
    run_id: RunId,
    scope: StudyScopeDep,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[RunEventResponse]:
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        records = DeepResearchRuns(session, scope).events(run_id, since=since, limit=limit)
        return [
            RunEventResponse(
                event_id=event["event_id"],
                step_id=event.get("step_id"),
                attempt_id=event.get("attempt_id"),
                event_type=event["event_type"],
                level=event["level"],
                message=event["message"],
                payload=dict(event.get("payload") or {}),
                created_at=event.get("created_at"),
            )
            for event in records
        ]
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}/bundle", response_model=dict[str, Any])
def bundle(
    run_id: RunId, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        return DeepResearchRuns(session, scope).bundle(run_id, store=store).model_dump(mode="json")
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}/provenance", response_model=dict[str, Any])
def provenance(
    run_id: RunId, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """Purpose, target, lineage and the sealed bundle's identity (ADR 0021).

    409 ``run_not_governed`` for a run stored before ADR 0021, ``bundle_not_ready`` while
    nothing is published.
    """
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        return (
            DeepResearchRuns(session, scope).provenance(run_id, store=store).model_dump(mode="json")
        )
    raise AssertionError("unreachable")


@router.get("/runs/{run_id}/snapshots/{snapshot_id}", response_model=dict[str, Any])
def snapshot(
    run_id: RunId,
    snapshot_id: SnapshotId,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> dict[str, Any]:
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        return (
            DeepResearchRuns(session, scope)
            .snapshot(run_id, snapshot_id, store=store)
            .model_dump(mode="json")
        )
    raise AssertionError("unreachable")
