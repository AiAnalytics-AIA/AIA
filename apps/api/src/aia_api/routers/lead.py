"""The Research Lead ("Vedoucí výzkumu"): a researcher's conversation, and their own Lead.

ADR 0026 and the product owner's 2026-10-19 decisions. The API enqueues and reads; the worker
owns every model call. Two routers:

* ``/studies/{study_id}/lead`` -- the caller's own conversation in the Study (``StudyScopeDep``:
  a Study outside the caller's scope is a 404). A message queues a Lead turn; what the turn
  proposes changes nothing until the person decides here, on the server: edits through
  ``…/edits`` (the approval ledger, ADR 0019 gate 1), a prepared design job through
  ``…/request`` (the spend limit and the ledger, ADR 0026 decision 7).
* ``/lead`` -- the caller's own Lead, read-only but for hatching it once and its preferences
  (``PUT /lead/preferences``); its files change only through chat, by the Lead's
  ``self_update``.

No route takes a client, organization or user id: the scope says whose it is.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.lead_chat_start import ChatStartRefused
from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.application.research_lead import (
    LeadAlreadyHatched,
    LeadBusy,
    LeadCardStale,
    LeadContextTooLarge,
    LeadEditsStale,
    LeadNotHatched,
    LeadProfile,
    LeadRejected,
    LeadSelfUpdateDecided,
    LeadSelfUpdateNone,
    LeadTurnNotFound,
    LeadTurnNotReady,
    LeadUnavailable,
    NotAPaidRequest,
    ResearchLead,
    WorkspaceConflict,
    worker_readiness,
)
from aia_core.domain.design import DesignRejected
from aia_core.domain.lead_commands import COMMANDS
from aia_core.domain.research_agents import AgentContextTooLarge
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.wallet import WalletChargeRefused
from aia_core.domain.workspace import WorkspaceRejected
from fastapi import APIRouter, HTTPException, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from ..dependencies import (
    OrganizationDep,
    RunPopulationDep,
    SessionDep,
    SettingsDep,
    StudyScopeDep,
)
from ..schemas.projects import ErrorResponse
from .research import run_start_errors, run_start_settings

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    403: {"model": ErrorResponse, "description": "Insufficient role, or the study is closed"},
    404: {"model": ErrorResponse, "description": "Not found, or not accessible"},
}

router = APIRouter(prefix="/studies/{study_id}", tags=["research-lead"], responses=_RESPONSES)
profile_router = APIRouter(prefix="/lead", tags=["research-lead"], responses=_RESPONSES)

TurnIdPath = Annotated[str, Path(max_length=64, pattern=r"^LDT-[0-9a-f]{1,32}$")]

#: Why the conversation is not offered, when the deployment has not switched the Lead on.
_DISABLED = "research_lead_disabled"


# --------------------------------------------------------------------------- schemas


class Focus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)


class TurnPost(BaseModel):
    """A message, or the greeting a Study's screen asks for when it opens."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["message", "greeting"]
    text: str | None = Field(default=None, max_length=4000)
    stage: str = Field(min_length=1, max_length=32)
    focus: Focus | None = None


class EditDecision(BaseModel):
    """A decision on edits a Lead turn proposed. ``base_revision`` is the working revision
    the edits were shown on (``null`` before any content); an accept on any other is 409."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["accept", "dismiss"]
    indices: list[Annotated[int, Field(ge=0, le=63)]] = Field(min_length=1, max_length=12)
    base_revision: int | None = Field(default=None, ge=1)
    #: The accept is the researcher's standing choice to accept the Lead's text edits, sent by
    #: their screen when a turn completes, not a click (plan inline-decisions chunk 2). Refused
    #: (422 ``auto_accept_off``) unless their Lead has it on; a non-text edit is ``refused``.
    auto: StrictBool = False


class RequestApproval(BaseModel):
    """A person's approval of the design job a Lead turn prepared; ``confirm_cost_usd`` is the
    ceiling they confirm when the study's spend limit asks."""

    model_config = ConfigDict(extra="forbid")
    confirm_cost_usd: float | None = Field(default=None, ge=0, le=1_000_000, allow_inf_nan=False)
    #: The working revision the person approves the job on, sent only after a ``stale_card``
    #: refusal and their yes: the card then runs on the design as it is now (LO10).
    workspace_revision: int | None = Field(default=None, ge=1)


class EditStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "dismissed"]
    reason: str | None = None
    #: Accepted by the researcher's standing choice, not a click (the ledger's ``"auto"``).
    auto: bool = False


class RequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved"]
    run_id: str | None


class SelfUpdateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "dismissed"]
    #: Files the accept left because they changed since the turn saw them.
    stale: list[Literal["name", "soul", "user"]] = []


class ForgetWaiting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_id: str
    #: The note as the turn was shown it (``null`` when the turn was not shown it).
    text: str | None


class SelfUpdateWaiting(BaseModel):
    """What a turn wants to keep or drop for all of the researcher's work, in their words."""

    model_config = ConfigDict(extra="forbid")
    name: str | None
    soul: str | None
    user: str | None
    #: Personal notes to keep.
    remember: list[str]
    #: Personal notes to forget.
    forget: list[ForgetWaiting]


class SelfUpdateDecide(BaseModel):
    """The researcher's decision on what a Lead turn wants to keep for all of their work."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["accept", "dismiss"]


class SelfUpdateDecided(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "dismissed"]
    #: What the accept applied (``null`` for a dismiss).
    changes: dict[str, Any] | None
    #: Files the accept left because another turn changed them since this one saw them: the
    #: researcher asks the Lead again. Notes have no base and applied regardless.
    stale: list[Literal["name", "soul", "user"]]


class LeadTurn(BaseModel):
    """One turn. A person's is ``COMPLETED`` with no output; a Lead turn carries its run's
    status (QUEUED, RUNNING, COMPLETED, FAILED, WAITING with its reason code, CANCELLED), its
    output once completed, what the Lead changed in its own files (``changes``), what
    grounding dropped, and the ledger's decisions on its edits and its prepared job."""

    model_config = ConfigDict(extra="forbid")
    turn_id: str
    sequence_no: int
    actor: Literal["person", "lead"]
    kind: Literal["message", "greeting"]
    stage: str
    text: str | None
    focus: dict[str, str] | None
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "WAITING", "CANCELLED"]
    reason: str | None
    output: dict[str, Any] | None
    changes: dict[str, Any] | None
    dropped: list[dict[str, Any]]
    edit_decisions: dict[str, EditStatus]
    request_decision: RequestDecision | None
    #: The researcher's decision on what the turn wanted to keep for all of their work.
    self_update_decision: SelfUpdateDecision | None
    #: Whether such a self-update waits for that decision (a personal note, SOUL, USER, name).
    self_update_pending: bool
    #: What waits (or waited) for that decision; ``null`` when nothing did.
    self_update_waiting: SelfUpdateWaiting | None
    run_id: str | None
    workspace_revision: int | None
    created_at: datetime
    created_by: str
    #: The typed start the server matched in a person's message (lead-orchestration LO5:
    #: ``agent_job:<action>`` or ``research_run``); its card is approved through ``…/request``
    #: as the person's own, a ``chat_start``. ``null`` on every other turn.
    command: str | None = None


class TypedCommand(BaseModel):
    """One of the composer's typed start commands (lead-orchestration LO5), as the server
    matches it: the phrase, the start it names, the card's label, and whether an instruction
    may follow after a colon. The browser shows them; only the server matches them."""

    model_config = ConfigDict(extra="forbid")
    phrase: str
    start: str
    label: str
    takes_instruction: bool


class LeadState(BaseModel):
    """The conversation and whether it is offered. ``available`` is the API's switch alone;
    ``worker_ready`` is whether a worker can answer a turn, ``null`` when that is unknown and
    never ``true`` without a source that shows it (research-lead-workbench 27a/27b)."""

    model_config = ConfigDict(extra="forbid")
    available: bool
    unavailable_reason: str | None
    #: ``false`` only on evidence (the source says which); ``null``: unknown. Until the worker
    #: publishes its composition (lead-orchestration LO12b) nothing here reports ``true``.
    worker_ready: bool | None
    #: Where ``worker_ready`` was read: ``newest_turn`` (this conversation's newest decided Lead
    #: turn parked for a reason naming the worker's composition), or ``null`` with no source.
    worker_ready_source: Literal["newest_turn"] | None
    #: Why the worker is not ready (a park code, e.g. ``research_lead_unconfigured``); ``null``
    #: unless ``worker_ready`` is ``false``. The name ``lib/lead-availability.ts`` reads.
    worker_reason: str | None
    #: The typed start commands the composer takes, with the Lead on or off (Q43).
    commands: list[TypedCommand]
    busy: bool
    turns: list[LeadTurn]


class LeadTurns(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turns: list[LeadTurn]


class EditResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int
    status: Literal["accepted", "dismissed", "refused"]
    reason: str | None


class EditDecisions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_revision: int | None
    results: list[EditResult]


class ApprovedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    design_revision_id: str
    status: str


class LeadFiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    soul: str
    user: str


class LeadMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_id: str
    scope: Literal["personal", "client"]
    client_id: str | None
    client_name: str | None
    text: str
    created_at: datetime
    source_turn_id: str | None


class LeadPreferences(BaseModel):
    """The researcher's own choices for their Lead (plan inline-decisions chunk 2)."""

    model_config = ConfigDict(extra="forbid")
    #: Accept the Lead's text edits (wording, never structure or the sample) without a click.
    auto_accept_text_edits: StrictBool


class ResearcherLead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_id: str
    name: str
    hatched_at: datetime
    updated_at: datetime
    files: LeadFiles
    memories: list[LeadMemory]
    preferences: LeadPreferences


class LeadProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hatched: bool
    lead: ResearcherLead | None


# --------------------------------------------------------------------------- errors


def _error(code: int, name: str, message: str, **details: Any) -> HTTPException:
    detail: dict[str, Any] = {"code": name, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=code, detail=detail)


@contextmanager
def _lead_errors() -> Iterator[None]:
    try:
        yield
    except ScopeDenied as exc:
        name = "study_closed" if exc.reason == "study_closed" else "insufficient_role"
        raise _error(
            status.HTTP_403_FORBIDDEN, name, "Your role does not permit that.", reason=exc.reason
        ) from exc
    except LeadTurnNotFound as exc:
        raise _error(status.HTTP_404_NOT_FOUND, exc.reason, "No such resource.") from exc
    except LeadUnavailable as exc:
        raise _error(409, exc.reason, "The Research Lead is not switched on here.") from exc
    except LeadNotHatched as exc:
        raise _error(409, exc.reason, "Hatch your Research Lead first.") from exc
    except LeadAlreadyHatched as exc:
        raise _error(409, exc.reason, "Your Research Lead is already hatched.") from exc
    except LeadBusy as exc:
        raise _error(409, exc.reason, "The Lead is still answering your last message.") from exc
    except LeadTurnNotReady as exc:
        raise _error(409, exc.reason, "The Lead has not finished this turn.") from exc
    except LeadSelfUpdateDecided as exc:
        raise _error(409, exc.reason, "This turn's self-update is already decided.") from exc
    except LeadSelfUpdateNone as exc:
        raise _error(409, exc.reason, "This turn left nothing waiting for you.") from exc
    except LeadCardStale as exc:
        raise _error(
            409,
            exc.reason,
            "The working content changed since the Lead prepared this card.",
            current_revision=exc.current_revision,
            turn_revision=exc.turn_revision,
        ) from exc
    except AgentContextTooLarge as exc:
        raise _error(
            422, exc.reason, "The study is too large for a design job to read; nothing started."
        ) from exc
    except LeadEditsStale as exc:
        raise _error(
            409,
            exc.reason,
            "The working content changed since these edits were shown.",
            current_revision=exc.current_revision,
        ) from exc
    except WorkspaceConflict as exc:
        raise _error(409, exc.reason, str(exc), current_revision=exc.current_revision) from exc
    except CostConfirmationRequired as exc:
        raise _error(
            409,
            "cost_confirmation_required",
            "This job can cost up to the ceiling shown; confirm it to start.",
            ceiling_usd=exc.ceiling_usd,
            limit_usd=exc.limit_usd,
        ) from exc
    except CostCeilingUnknown as exc:
        raise _error(
            409,
            "cost_ceiling_unknown",
            "The study has a spend limit and this job's cost ceiling cannot be worked out, so "
            "it is not started.",
            reason=exc.reason.value,
            limit_usd=exc.limit_usd,
        ) from exc
    except ChatStartRefused as exc:
        raise _error(
            409,
            exc.reason,
            "This start is not inside the study's wallet, or names nothing that can start.",
            ceiling_usd=exc.ceiling_usd,
            remaining_usd=exc.remaining_usd,
        ) from exc
    except WalletChargeRefused as exc:
        raise _error(
            409,
            exc.reason,
            "This start is not inside the study's wallet.",
            ceiling_usd=exc.ceiling_usd,
            remaining_usd=exc.remaining_usd,
        ) from exc
    except NotAPaidRequest as exc:
        raise _error(422, exc.reason, "This turn prepared no paid job.") from exc
    except LeadContextTooLarge as exc:
        raise _error(422, exc.reason, str(exc)) from exc
    except LeadRejected as exc:
        raise _error(422, exc.reason, str(exc)) from exc
    except DesignRejected as exc:
        raise _error(409, exc.reason, str(exc)) from exc
    except WorkspaceRejected as exc:
        raise _error(422, exc.reason, str(exc)) from exc


# --------------------------------------------------------------------------- the conversation


@router.get("/lead", response_model=LeadState)
def read_lead(scope: StudyScopeDep, session: SessionDep, settings: SettingsDep) -> LeadState:
    """The caller's own conversation in the Study, oldest first, and whether the Lead is on."""
    with _lead_errors():
        lead = ResearchLead(session, scope, enabled=settings.research_lead_on)
        state = lead.state()
    on = settings.research_lead_on
    ready, source, reason = worker_readiness(state["turns"])
    return LeadState(
        available=on,
        unavailable_reason=None if on else _DISABLED,
        worker_ready=ready,
        worker_ready_source=source,
        worker_reason=reason,
        commands=[
            TypedCommand(
                phrase=c.phrase,
                start=c.start,
                label=c.label,
                takes_instruction=c.takes_instruction,
            )
            for c in COMMANDS
        ],
        busy=state["busy"],
        turns=[LeadTurn.model_validate(t) for t in _public(state["turns"])],
    )


def _public(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A turn as the browser reads it: not the class it was sent as, nor the stored detail
    of what waits (the browser reads that from the turn's output)."""
    hidden = {"data_class", "pending_self_update", "self_update_base", "awaiting_budget"}
    return [{k: v for k, v in t.items() if k not in hidden} for t in turns]


@router.post(
    "/lead/turns",
    response_model=LeadTurns,
    status_code=201,
    responses={
        409: {"model": ErrorResponse, "description": "Off, not hatched, or the Lead is busy"},
        422: {"model": ErrorResponse, "description": "Invalid turn, or its context is too large"},
    },
)
def post_turn(
    body: TurnPost,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
    response: Response,
) -> LeadTurns:
    """Store the message and queue the Lead's turn: 201 with the turns stored, or 200 with
    none for a greeting the Lead has already given in the last eight hours."""
    with _lead_errors():
        turns = ResearchLead(session, scope, enabled=settings.research_lead_on).post(
            kind=body.kind,
            stage=body.stage,
            text=body.text,
            focus=body.focus.model_dump() if body.focus else None,
        )
    if not turns:
        response.status_code = status.HTTP_200_OK
    return LeadTurns(turns=[LeadTurn.model_validate(t) for t in _public(turns)])


@router.post(
    "/lead/turns/{turn_id}/edits",
    response_model=EditDecisions,
    responses={409: {"model": ErrorResponse, "description": "Stale, or the turn is not done"}},
)
def decide_edits(
    turn_id: TurnIdPath, body: EditDecision, scope: StudyScopeDep, session: SessionDep
) -> EditDecisions:
    """Accept or dismiss edits the caller's own Lead turn proposed: the working copy saved and
    each decision written to the approval ledger, in one transaction."""
    with _lead_errors():
        decided = ResearchLead(session, scope).decide_edits(
            turn_id,
            decision=body.decision,
            indices=body.indices,
            base_revision=body.base_revision,
            auto=body.auto,
        )
    return EditDecisions.model_validate(decided)


@router.post(
    "/lead/turns/{turn_id}/self-update",
    response_model=SelfUpdateDecided,
    responses={409: {"model": ErrorResponse, "description": "Already decided, or nothing waits"}},
)
def decide_self_update(
    turn_id: TurnIdPath, body: SelfUpdateDecide, scope: StudyScopeDep, session: SessionDep
) -> SelfUpdateDecided:
    """Accept or dismiss what the caller's own Lead turn wants to keep for all of their work
    (a personal note, a SOUL, USER or name change): applied on accept, recorded in the approval
    ledger either way, once. An accept leaves a file another turn changed since this one saw
    it and names it in ``stale``; it is still an accept (its notes applied), so a 200."""
    with _lead_errors():
        decided = ResearchLead(session, scope).decide_self_update(turn_id, decision=body.decision)
    return SelfUpdateDecided.model_validate(decided)


@router.post(
    "/lead/turns/{turn_id}/request",
    response_model=ApprovedRequest,
    responses={
        409: {
            "model": ErrorResponse,
            "description": "The spend limit asks, or it is unknown; the Lead is switched off; "
            "or the working copy moved since the card was prepared (stale_card)",
        },
        422: {
            "model": ErrorResponse,
            "description": "The turn prepared no paid job, or the study is too large for it",
        },
    },
)
def approve_request(
    turn_id: TurnIdPath,
    body: RequestApproval,
    request: Request,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
    population: RunPopulationDep,
) -> ApprovedRequest:
    """Approve the design job the caller's own Lead turn prepared: held to the study's spend
    limit, started and recorded in the approval ledger, once. With the Lead switched off, a
    card its model prepared is 409 ``research_lead_disabled`` and nothing is written (Q42).

    The caller's own typed start (a person's turn naming a ``command``, LO5) is approved here
    too, with the Lead on or off (Q43): a design job, or a research run on the deployment's
    run settings (the ones ``POST …/research/runs`` uses), held to the same threshold and, with
    ``AIA_STUDY_WALLET_ENABLED``, to the wallet (409 ``outside_wallet``, ``ceiling_unknown``),
    and recorded as ``chat_start``. A run start's refusals are that route's."""
    with _lead_errors(), run_start_errors():
        started = ResearchLead(session, scope, enabled=settings.research_lead_on).approve_request(
            turn_id,
            confirm_cost_usd=body.confirm_cost_usd,
            reservation_usd=settings.ai_research_reservation_usd,
            run_start=run_start_settings(request, population),
            wallet_enabled=settings.study_wallet_enabled,
            workspace_revision=body.workspace_revision,
        )
    return ApprovedRequest.model_validate(started)


# --------------------------------------------------------------------------- the caller's Lead


@profile_router.get("", response_model=LeadProfileResponse)
def read_profile(org: OrganizationDep, session: SessionDep) -> LeadProfileResponse:
    """The caller's own Lead, read-only: its name, files and active notes."""
    with _lead_errors():
        return LeadProfileResponse.model_validate(LeadProfile(session, org).read())


@profile_router.post(
    "",
    response_model=LeadProfileResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse, "description": "Already hatched"}},
)
def hatch(org: OrganizationDep, session: SessionDep) -> LeadProfileResponse:
    """Hatch the caller's Lead with its defaults, once. No body: what it becomes is said in
    chat, and the Lead changes its own files when asked."""
    with _lead_errors():
        return LeadProfileResponse.model_validate(LeadProfile(session, org).hatch())


@profile_router.put(
    "/preferences",
    response_model=LeadProfileResponse,
    responses={409: {"model": ErrorResponse, "description": "Not hatched"}},
)
def set_preferences(
    body: LeadPreferences, org: OrganizationDep, session: SessionDep
) -> LeadProfileResponse:
    """Set the caller's own Lead's preferences, audited: whether its text edits are accepted
    without a click (off by default; ADR 0026: the researcher's standing choice is their
    decision). Nobody sets another researcher's."""
    with _lead_errors():
        return LeadProfileResponse.model_validate(
            LeadProfile(session, org).set_preferences(
                auto_accept_text_edits=body.auto_accept_text_edits
            )
        )
