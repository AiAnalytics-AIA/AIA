"""Study-scoped durable Deep Research jobs and their sealed internal evidence.

Every run says why it ran, what it researched and which immutable state it rests on
(ADR 0021): ``purpose``, ``target`` and ``lineage`` on each run, and
``GET …/runs/{run_id}/provenance`` for what a later consumer cites. A start that names no
``purpose`` -- the deployed client's shape -- is a new ``DESIGN_RESEARCH`` run, recorded
``purpose_source: LEGACY_DEFAULT``; only ``DESIGN_RESEARCH`` may be started there.
``POST …/runs/interpretation`` starts ``INTERPRETATION_RESEARCH`` over one result of this
Study (a typed target: a question's or a battery object's result, an analysis module, a
Sociomap, one of its objects or a pair of them): its lineage is pinned and its mission built
from the target by code (plan ``deep-research-web-search.md`` chunk 30). A target of another
Study is 404; an entity its artifact does not hold, or a design target, 422. Its retry
re-freezes the stored target and answers 409 ``lineage_changed`` when the result no longer
reads as pinned. A run stored before ADR 0021 reads ``integration_contract:
legacy-unversioned`` with no purpose.

A start or a retry on a Study with a spend limit asks first (ADR 0019 gate 2): the
server works out the run's cost ceiling from the deployment's prices
(:func:`deep_research_prices`) and answers 409 ``cost_confirmation_required`` with it,
or 409 ``cost_ceiling_unknown`` when a price it needs is not configured, as a research
run's start does. Every new run stores its ceiling, threshold or not.

``POST …/deep-research/quote`` answers what a start would cost and answer, read-only: the
ceiling by kind for the purpose and preset asked, the priced routes and the live settings
they still need (ADR 0022), the threshold, the budget and whether Deep Research is switched
on in this deployment's keys (off: a run would park). It is priced by the same admission
the start acts on (``DeepResearchRuns.quote``; plan ``deep-research-web-search.md`` 55), so
the two cannot disagree. Nothing is reserved, recorded or started.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.deep_research import (
    BundleNotReady,
    DeepResearchQuote,
    DeepResearchRunNotFound,
    DeepResearchRunNotRetryable,
    DeepResearchRuns,
    FocusUnknown,
    InterpretationMissionMismatch,
    LineageChanged,
    LiveNotApproved,
    NothingToResearch,
    ResearchTargetInvalid,
    ResearchTargetNotFound,
    RunNotGoverned,
    RunSpecCorrupt,
    governed_record,
)
from aia_core.application.design_research import DesignResearchProposals
from aia_core.application.errors import (
    BudgetWaitNotLiftable,
    RuntimeParkNotResumable,
    WorkspaceConflict,
)
from aia_core.application.proposal_accept import StaleProposal
from aia_core.application.research import (
    BudgetNotRaised,
    CostCeilingUnknown,
    CostConfirmationRequired,
)
from aia_core.application.verified_sources import SourceNotInRun, add_verified_source
from aia_core.domain.deep_research.budgets import CallKind, ResearchMode
from aia_core.domain.deep_research.contracts import Channel
from aia_core.domain.deep_research.integration import (
    LEGACY_UNVERSIONED,
    DeepResearchPurpose,
    PurposeSource,
    ResearchTargetRef,
)
from aia_core.domain.deep_research.planning import UnknownPreset
from aia_core.domain.deep_research.request_limits import REQUEST_LIMITS, RequestLimits
from aia_core.domain.design import DesignRejected
from aia_core.domain.run_cost import CeilingUnknown, DeepResearchPrices
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from aia_core.infrastructure.storage import IntegrityError, ObjectNotFound
from aia_core.infrastructure.study_design_repository import DesignRevisionNotFound
from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from ..config import Settings
from ..dependencies import (
    ArtifactStoreDep,
    PrincipalDep,
    ResolverDep,
    SessionDep,
    StudyScopeDep,
)
from ..schemas.projects import ErrorResponse
from ..schemas.runs import RunEventResponse
from .research import (
    DesignRevisionResponse,
    _code,
    _cost_refused,
    _revision,
    stale_proposal,
    workspace_stale,
)
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


#: A research question's id as the design gives it (``item_ids``), the Lead's focus grammar.
FocusId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.\-]{1,80}$")]


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
    #: The research questions the run is limited to, by their ids (Q45); empty: the design.
    focus: list[FocusId] = Field(default_factory=list, max_length=12)
    #: What the person confirms the run can cost at most. Read only when the study has a
    #: limit the run's ceiling reaches; the server works the ceiling out and holds this to it.
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("channels")
    @classmethod
    def _unique_channels(cls, value: tuple[Channel, ...]) -> tuple[Channel, ...]:
        if len(set(value)) != len(value):
            raise ValueError("channels must be distinct")
        return value


class InterpretationStart(BaseModel):
    """Interpretation Research over one result of this Study (ADR 0021, chunk 30)."""

    model_config = ConfigDict(extra="forbid")
    #: The exact result: a research run of this Study and the artifact and entity it names.
    target: ResearchTargetRef
    preset_name: Literal["QUICK", "STANDARD", "DEEP", "EXHAUSTIVE"]
    channels: tuple[Channel, ...] = Field(default=(Channel.WEB,), min_length=1, max_length=2)
    #: A person's name for the run: shown, never part of its identity.
    title: str | None = Field(default=None, max_length=200)
    #: As for a design run: read only when the study's limit is reached by the ceiling.
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


class DeepResearchQuoteRequest(BaseModel):
    """A start to price, without its confirmation: a design run over a revision, or an
    Interpretation Research run over one result of this Study (plan chunk 55)."""

    model_config = ConfigDict(extra="forbid")
    purpose: Literal["DESIGN_RESEARCH", "INTERPRETATION_RESEARCH"]
    #: Design Research: the revision it would research.
    design_revision_id: str | None = Field(
        default=None, max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$"
    )
    #: Interpretation Research: the exact result it would interpret.
    target: ResearchTargetRef | None = None
    #: Design Research: the research questions it would be limited to, by id (Q45).
    focus: list[FocusId] = Field(default_factory=list, max_length=12)
    preset_name: Literal["QUICK", "STANDARD", "DEEP", "EXHAUSTIVE"]
    channels: tuple[Channel, ...] = Field(default=(Channel.WEB,), min_length=1, max_length=2)

    @field_validator("channels")
    @classmethod
    def _unique_channels(cls, value: tuple[Channel, ...]) -> tuple[Channel, ...]:
        if len(set(value)) != len(value):
            raise ValueError("channels must be distinct")
        return value

    @model_validator(mode="after")
    def _one_subject(self) -> DeepResearchQuoteRequest:
        if self.purpose == "DESIGN_RESEARCH":
            if self.design_revision_id is None or self.target is not None:
                raise ValueError("Design Research is quoted over a design_revision_id alone")
        elif self.target is None or self.design_revision_id is not None or self.focus:
            raise ValueError("Interpretation Research is quoted over a target alone")
        return self


class DeepResearchRuntimeState(BaseModel):
    """Whether Deep Research is switched on, as this deployment's keys say -- never whether a
    worker composed it (that is the worker's record, ``lead-orchestration#LO12b``)."""

    model_config = ConfigDict(extra="forbid")
    switch: Literal["AIA_DEEP_RESEARCH_ENABLED"] = "AIA_DEEP_RESEARCH_ENABLED"
    #: The key's value in the API's environment; ``null``: not given to the API, unknown.
    enabled: bool | None
    #: True when the key is off: a started run parks at its plan step
    #: (``deep_research_unconfigured``) before anything is sent; ``null`` when unknown.
    runs_would_park: bool | None
    park_reason: Literal["deep_research_unconfigured"] | None


class DeepResearchBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    budget_usd: float
    spent_usd: float
    reserved_usd: float
    #: Settled from calls whose outcome is uncertain (they may have been billed).
    uncertain_usd: float
    available_usd: float


class DeepResearchQuoteResponse(BaseModel):
    """What a start would cost and answer; nothing was reserved, recorded or started."""

    model_config = ConfigDict(extra="forbid")
    study_id: str
    purpose: str
    preset: str
    #: The most the run can cost; ``null`` when a price it needs is not configured.
    ceiling_usd: float | None
    #: The mode the ceiling is priced in (planned, agent-directed or the engine's lead mode).
    ceiling_mode: str | None
    #: Why the ceiling is unknown, and the kinds of call whose price is missing.
    ceiling_unknown: str | None
    unknown_kinds: list[str]
    #: Every kind of call: the most it can cost (``null``: unknown, never 0) and its bound.
    usd_by_kind: dict[str, float | None]
    calls_by_kind: dict[str, int]
    #: The priced live routes the run would use (Brave's ``search``, Common Crawl's
    #: ``url_index_query``) and the live settings they still need approved (ADR 0022).
    paid_routes: list[str]
    live_settings_missing: list[str]
    #: The study's confirmation threshold (``spend_confirm_usd``); ``null``: never asks.
    threshold_usd: float | None
    #: The study's budget position; ``null`` without the permission to see costs.
    budget: DeepResearchBudget | None
    #: What ``POST …/runs`` (or ``…/runs/interpretation``) with no confirmation would answer:
    #: ``start``, ``confirm`` (409 cost_confirmation_required), ``ceiling_unknown``,
    #: ``live_settings_unapproved``, or ``exists`` (the same spec's run, returned as it is).
    start_verdict: str
    existing_run_id: str | None
    #: The digest of the Deep Research settings in force, which a run would pin.
    settings_digest: str
    runtime: DeepResearchRuntimeState


class DesignProposalAccept(BaseModel):
    """A person's accept of a Design Research proposal: the items taken, on which baseline."""

    model_config = ConfigDict(extra="forbid")
    item_ids: list[Annotated[str, Field(pattern=r"^DRP-[0-9a-f]{24}$")]] = Field(
        min_length=1, max_length=500
    )
    expected_revision_id: str = Field(max_length=64, pattern=r"^REV-[0-9a-f]{1,32}$")
    #: The working revision the person has: the items go into it too (ADR 0026 decision 6).
    expected_workspace_revision: int = Field(ge=1)


class VerifiedSourceAdd(BaseModel):
    """A person checked a captured source: the accepted finding of the run that cites it."""

    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(max_length=64, pattern=r"^EV-[0-9a-f]{16}$")


class VerifiedSourceAdded(BaseModel):
    """What the click did. ``added``: knowledge now; ``proposed``: the client turned
    self-approval off, so it waits for someone else; ``exists``: the client already holds or
    awaits a source at this URL, and nothing was written. ``item_id`` is the item, when one
    exists."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["added", "proposed", "exists"]
    item_id: str | None
    proposal_id: str | None
    client_id: str
    url: str
    title: str


class DeepResearchStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: The id the run's events name: which step reported what.
    step_id: str
    node_key: str
    status: str
    waiting_reason: str | None
    attempts_recorded: int
    #: When its first attempt started; null before one has.
    started_at: datetime | None = None
    artifact_id: str | None
    error_message: str | None
    #: The code the last attempt recorded beside its message, as on a research step.
    error_reason: str | None = None


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


def deep_research_prices(
    settings: Settings, limits: Mapping[CallKind, RequestLimits] = REQUEST_LIMITS
) -> DeepResearchPrices:
    """What each kind of call a Deep Research run makes may cost, as this deployment says
    (:meth:`~aia_core.application.deep_research_pricing.DeepResearchPricingSettings.prices`,
    plan chunk 55: the application layer prices it, the router only names the keys)."""
    return settings.deep_research_pricing().prices(limits)


def _study_prices(
    settings: Settings, session: SessionDep, scope: StudyContext
) -> DeepResearchPrices:
    """The prices under the request limits the study's run would pin (chunk 43c)."""
    return settings.deep_research_pricing().study_prices(session, scope)


def deep_research_mode(settings: Settings) -> ResearchMode:
    """The mode the worker composes from the same switches (the engine's lead mode needs
    agent-directed)."""
    return settings.deep_research_pricing().mode()


@contextmanager
def _errors(session: SessionDep) -> Iterator[None]:
    try:
        yield
    except ScopeDenied as exc:
        raise _refused(exc) from exc
    except (CostConfirmationRequired, CostCeilingUnknown) as exc:
        raise _cost_refused(exc) from exc
    except LiveNotApproved as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "live_settings_unapproved",
                "message": "Deep Research's live settings are not all approved.",
                "details": {"missing": list(exc.missing), "routes": list(exc.kinds)},
            },
        ) from exc
    except (DeepResearchRunNotFound, DesignRevisionNotFound, ResearchTargetNotFound) as exc:
        raise _not_found() from exc
    except FocusUnknown as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.reason,
                "message": str(exc),
                "details": {"unknown": list(exc.unknown)},
            },
        ) from exc
    except (NothingToResearch, UnknownPreset, ResearchTargetInvalid) as exc:
        raise HTTPException(
            status_code=422, detail={"code": "research_input", "message": str(exc)}
        ) from exc
    except StaleProposal as exc:
        raise stale_proposal(exc) from exc
    except WorkspaceConflict as exc:
        raise workspace_stale(exc) from exc
    except DesignRejected as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.reason, "message": str(exc)}
        ) from exc
    except InterpretationMissionMismatch as exc:
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
    except RuntimeParkNotResumable as exc:
        raise HTTPException(
            status_code=409, detail={"code": "runtime_park_not_resumable", "message": str(exc)}
        ) from exc
    except BudgetWaitNotLiftable as exc:
        raise HTTPException(
            status_code=409, detail={"code": "not_waiting_for_budget", "message": str(exc)}
        ) from exc
    except BudgetNotRaised as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "budget_not_raised",
                "message": f"The study's budget is already {exc.current:.2f}; offer at least that.",
            },
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
                step_id=step["step_id"],
                node_key=step["node_key"],
                status=step["status"].value,
                started_at=step["attempts"][0]["started_at"] if step.get("attempts") else None,
                waiting_reason=step.get("waiting_reason"),
                attempts_recorded=step["attempts_recorded"],
                artifact_id=(step.get("output") or {}).get("artifact_id"),
                error_message=str((step["attempts"][-1].get("error") or {}).get("message"))
                if step.get("attempts") and (step["attempts"][-1].get("error") or {}).get("message")
                else None,
                error_reason=_code((step["attempts"][-1].get("error") or {}).get("reason"))
                if step.get("attempts")
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


def _quote_response(
    quote: DeepResearchQuote, scope: StudyContext, settings: Settings
) -> DeepResearchQuoteResponse:
    ceiling = quote.ceiling
    unknown = set(ceiling.unknown_kinds) if ceiling is not None else set(CallKind)
    enabled = settings.deep_research_pricing().enabled
    return DeepResearchQuoteResponse(
        study_id=scope.study_id,
        purpose=quote.purpose.value,
        preset=quote.preset,
        ceiling_usd=None if ceiling is None else ceiling.total_usd,
        ceiling_mode=None if ceiling is None else ceiling.mode.value,
        ceiling_unknown=(
            CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING.value
            if ceiling is None
            else (ceiling.unknown.value if ceiling.unknown is not None else None)
        ),
        unknown_kinds=[] if ceiling is None else [k.value for k in ceiling.unknown_kinds],
        usd_by_kind={
            kind.value: None if kind in unknown or ceiling is None else ceiling.usd.get(kind, 0.0)
            for kind in CallKind
        },
        calls_by_kind={} if ceiling is None else {k.value: n for k, n in ceiling.calls.items()},
        paid_routes=[k.value for k in quote.paid_routes],
        live_settings_missing=list(quote.live_missing),
        threshold_usd=quote.threshold_usd,
        budget=None if quote.budget is None else DeepResearchBudget(**quote.budget),
        start_verdict=quote.verdict.value,
        existing_run_id=quote.existing_run_id,
        settings_digest=quote.settings_digest,
        runtime=DeepResearchRuntimeState(
            enabled=enabled,
            runs_would_park=None if enabled is None else not enabled,
            park_reason="deep_research_unconfigured" if enabled is False else None,
        ),
    )


@router.post("/quote", response_model=DeepResearchQuoteResponse)
def quote(
    body: DeepResearchQuoteRequest,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> DeepResearchQuoteResponse:
    """What starting this Deep Research run would cost and answer, read-only (chunk 55).

    The spec is frozen as the start freezes it and priced by the start's own admission, so
    ``ceiling_usd`` is the figure the start asks to confirm. Nothing is reserved, recorded,
    marked or started: the permission and an open study are checked before any freeze, and a
    pinned artifact that fails verification is 409 ``artifact_corrupt`` with no CORRUPT mark.
    It answers whatever ``AIA_DEEP_RESEARCH_ENABLED`` says, and says when a run would park.
    404 for a revision or a target that is not this Study's; 422 as the start's.
    """
    settings = request.app.state.settings
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        # The start's own order: its permission and an open study before anything is frozen
        # or read, so a closed study is 403 study_closed and nothing is touched.
        runs.require_start()
        try:
            if body.purpose == DeepResearchPurpose.DESIGN_RESEARCH.value:
                assert body.design_revision_id is not None
                spec = runs.freeze_design(
                    design_revision_id=body.design_revision_id,
                    preset_name=body.preset_name,
                    channels=body.channels,
                    focus=body.focus,
                )
            else:
                assert body.target is not None
                spec = runs.freeze_interpretation(
                    target=body.target,
                    preset_name=body.preset_name,
                    store=store,
                    channels=body.channels,
                )
        except (IntegrityError, ObjectNotFound) as exc:
            # A quote is read-only: a pinned artifact that fails verification is reported,
            # never marked. The CORRUPT mark the read flushed is rolled back here, not
            # committed (``artifact_corrupt`` commits it); a start over it marks it.
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "artifact_corrupt",
                    "message": "A result the run would rest on fails verification; "
                    "the quote marked nothing.",
                },
            ) from exc
        quoted = runs.quote(
            spec,
            prices=_study_prices(settings, session, scope),
            modes=(deep_research_mode(settings),),
        )
        return _quote_response(quoted, scope, settings)
    raise AssertionError("unreachable")


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
            prices=_study_prices(settings, session, scope),
            modes=(deep_research_mode(settings),),
            confirm_cost_usd=body.confirm_cost_usd,
            purpose_source=(
                PurposeSource.EXPLICIT if body.purpose is not None else PurposeSource.LEGACY_DEFAULT
            ),
            title=body.title,
            focus=body.focus,
        )
        if not started.created:
            response.status_code = 200
        else:
            response.headers["Location"] = (
                f"/api/v1/studies/{scope.study_id}/deep-research/runs/{started.run_id}"
            )
        return _response(runs.get(started.run_id), scope, created=started.created)
    raise AssertionError("unreachable")


@router.post("/runs/interpretation", response_model=DeepResearchRun, status_code=201)
def start_interpretation(
    body: InterpretationStart,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    response: Response,
) -> DeepResearchRun:
    """Start Interpretation Research over one result, answering the run as ``POST …/runs``.

    201 with the run (200 when the same spec's run exists); 404 for a target that is not this
    Study's; 422 for an entity its artifact does not hold, a design target or nothing to
    research; the spend limit's 409s as for a design run.
    """
    settings = request.app.state.settings
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        started = runs.start_interpretation(
            target=body.target,
            preset_name=body.preset_name,
            store=store,
            channels=body.channels,
            prices=_study_prices(settings, session, scope),
            modes=(deep_research_mode(settings),),
            confirm_cost_usd=body.confirm_cost_usd,
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


@router.post("/runs/{run_id}/resume", response_model=DeepResearchRun)
def resume(run_id: RunId, scope: StudyScopeDep, session: SessionDep) -> DeepResearchRun:
    """Needs ``RUN_WORKFLOW`` on an open Study: a run parked for the AI runtime (Deep Research
    not composed on the worker, or a gateway refusal before any call) offered to a worker
    again once it is, the same run with its frozen spec, pin and ceiling. 409
    ``runtime_park_not_resumable`` when nothing in it waits for the runtime."""
    with _errors(session):
        return _response(DeepResearchRuns(session, scope).resume(run_id), scope)
    raise AssertionError("unreachable")


class DeepResearchBudgetLift(BaseModel):
    """The budget the study is raised to, and why. Never a lower one."""

    model_config = ConfigDict(extra="forbid")

    budget_usd: float = Field(ge=0, le=1_000_000)
    note: str = Field(default="", max_length=500)


@router.post("/runs/{run_id}/budget", response_model=DeepResearchRun)
def lift_budget(
    run_id: RunId, body: DeepResearchBudgetLift, scope: StudyScopeDep, session: SessionDep
) -> DeepResearchRun:
    """Needs ``APPROVE_BUDGET`` and ``MANAGE_STUDY_BUDGET`` on an open Study: the study's
    budget raised to ``budget_usd`` and every step of the run stopped at the cap offered to a
    worker again, each lift an approval in the ledger. 409 ``not_waiting_for_budget`` when
    none waits; 422 ``budget_not_raised`` below the current budget. The cap stays hard."""
    with _errors(session):
        runs = DeepResearchRuns(session, scope)
        return _response(
            runs.lift_budget_wait(run_id, budget_usd=body.budget_usd, note=body.note), scope
        )
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
            prices=_study_prices(settings, session, scope),
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


@router.get("/runs/{run_id}/coverage", response_model=dict[str, Any])
def coverage(
    run_id: RunId, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """What the run looked at: searches, pages, refusals, set-aside findings, by reason.

    Counted by code from the sealed bundle and the run's tool journal (chunk 47); 409
    ``bundle_not_ready`` while nothing is published.
    """
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        return (
            DeepResearchRuns(session, scope).coverage(run_id, store=store).model_dump(mode="json")
        )
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


@router.get("/runs/{run_id}/design-proposal", response_model=dict[str, Any])
def design_proposal(
    run_id: RunId, scope: StudyScopeDep, session: SessionDep, store: ArtifactStoreDep
) -> dict[str, Any]:
    """What a completed Design Research run proposes, from its own sealed bundle (chunk 29).

    One item per subject: its accepted findings, or a gap. 409 ``proposal_not_ready`` before
    the run completes, ``not_design_research`` for a legacy or interpretation run.
    """
    with _errors(session):
        scope.require(Permission.EDIT_STUDY)
        return (
            DesignResearchProposals(session, scope)
            .proposal(run_id, store=store)
            .model_dump(mode="json")
        )
    raise AssertionError("unreachable")


@router.post("/runs/{run_id}/design-proposal/accept", response_model=DesignRevisionResponse)
def accept_design_proposal(
    run_id: RunId,
    body: DesignProposalAccept,
    scope: StudyScopeDep,
    session: SessionDep,
    store: ArtifactStoreDep,
) -> DesignRevisionResponse:
    """A person takes the chosen items into a new Design Revision (ADR 0019 gate 1).

    The items go into the working copy at ``expected_workspace_revision`` in the same
    transaction (ADR 0026 decision 6); the revision answers with its content and the working
    revision it names. 409 ``stale_proposal`` (with ``details.reason`` and the conflicting
    items) when the expected revision is not the one the run researched or not the Study's
    newest, or an item changed in the working copy; ``stale_revision`` for an older working
    copy; ``inadmissible``, ``unknown_item``, ``block_too_large``; 403 without gate authority.
    """
    with _errors(session):
        accepted = DesignResearchProposals(session, scope).accept(
            run_id,
            item_ids=body.item_ids,
            expected_revision_id=body.expected_revision_id,
            expected_workspace_revision=body.expected_workspace_revision,
            store=store,
        )
        return _revision(
            accepted.revision, created=accepted.created, content=accepted.merged.content
        )
    raise AssertionError("unreachable")


@router.post(
    "/runs/{run_id}/sources/{source_ref}/knowledge",
    response_model=VerifiedSourceAdded,
    status_code=201,
    responses={
        200: {"model": VerifiedSourceAdded, "description": "Already in the client's knowledge"},
        404: {"model": ErrorResponse, "description": "No such run, or the source is not in it"},
        409: {"model": ErrorResponse, "description": "The run has published no bundle"},
    },
)
def add_source_to_knowledge(
    run_id: RunId,
    source_ref: SnapshotId,
    body: VerifiedSourceAdd,
    scope: StudyScopeDep,
    principal: PrincipalDep,
    resolver: ResolverDep,
    session: SessionDep,
    store: ArtifactStoreDep,
    response: Response,
) -> VerifiedSourceAdded:
    """ "Ověřeno, přidat zdroj": a person who checked a source the run captured adds it to the
    Study's client's knowledge as a ``SOURCE`` item (plan inline-decisions chunk 1).

    The URL, title, quote and hash are the run's sealed bundle's, never the request's: the
    snapshot ``source_ref`` and the accepted finding ``evidence_id`` citing it must both be in
    it (404 ``source_not_in_run``). Once per client and URL: a second add answers 200
    ``exists`` with the item and writes nothing. Needs the client's knowledge permissions;
    where the client or the Study turned self-approval off it answers 201 ``proposed``.
    """
    try:
        client = resolver.client_context(principal, client_id=scope.client_id)
    except ScopeDenied as exc:
        raise _not_found() from exc
    with _errors(session):
        try:
            verified = add_verified_source(
                session,
                scope,
                client,
                run_id=run_id,
                snapshot_id=source_ref,
                evidence_id=body.evidence_id,
                store=store,
            )
        except SourceNotInRun as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": exc.reason,
                    "message": "The run's evidence holds no such source.",
                },
            ) from exc
        if verified.added.status == "exists":
            response.status_code = 200
        return VerifiedSourceAdded(
            status=verified.added.status,
            item_id=verified.added.item_id,
            proposal_id=verified.added.proposal_id,
            client_id=client.client_id,
            url=verified.url,
            title=verified.title,
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
