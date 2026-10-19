"""The Research Lead ("Vedoucí výzkumu"): a researcher's conversation, and their own Lead.

ADR 0026 and the product owner's 2026-10-19 decisions. The API enqueues and reads; the worker
owns every model call. Two routers:

* ``/studies/{study_id}/lead`` -- the caller's own conversation in the Study (``StudyScopeDep``:
  a Study outside the caller's scope is a 404). A message queues a Lead turn; what the turn
  proposes changes nothing until the person decides here, on the server: edits through
  ``…/edits`` (the approval ledger, ADR 0019 gate 1), a prepared design job through
  ``…/request`` (the spend limit and the ledger, ADR 0026 decision 7).
* ``/lead`` -- the caller's own Lead, read-only but for hatching it once; its files change
  only through chat, by the Lead's ``self_update``.

No route takes a client, organization or user id: the scope says whose it is.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.application.research_lead import (
    LeadAlreadyHatched,
    LeadBusy,
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
)
from aia_core.domain.design import DesignRejected
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workspace import WorkspaceRejected
from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import OrganizationDep, SessionDep, SettingsDep, StudyScopeDep
from ..schemas.projects import ErrorResponse

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


class RequestApproval(BaseModel):
    """A person's approval of the design job a Lead turn prepared; ``confirm_cost_usd`` is the
    ceiling they confirm when the study's spend limit asks."""

    model_config = ConfigDict(extra="forbid")
    confirm_cost_usd: float | None = Field(default=None, ge=0)


class EditStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "dismissed"]
    reason: str | None = None


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


class LeadState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    unavailable_reason: str | None
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


class ResearcherLead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_id: str
    name: str
    hatched_at: datetime
    updated_at: datetime
    files: LeadFiles
    memories: list[LeadMemory]


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
        lead = ResearchLead(session, scope, enabled=settings.ai_research_lead_enabled)
        state = lead.state()
    on = settings.ai_research_lead_enabled
    return LeadState(
        available=on,
        unavailable_reason=None if on else _DISABLED,
        busy=state["busy"],
        turns=[LeadTurn.model_validate(t) for t in _public(state["turns"])],
    )


def _public(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A turn as the browser reads it: not the class it was sent as, nor the stored detail
    of what waits (the browser reads that from the turn's output)."""
    hidden = {"data_class", "pending_self_update", "self_update_base"}
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
        turns = ResearchLead(session, scope, enabled=settings.ai_research_lead_enabled).post(
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
    ledger either way, once."""
    with _lead_errors():
        decided = ResearchLead(session, scope).decide_self_update(turn_id, decision=body.decision)
    stale = decided.pop("stale")
    if stale:
        # The notes applied and the decision is recorded; the stale files were left. That is
        # kept (committed here, as the answer is an error) and said as a conflict.
        session.commit()
        raise _error(
            409,
            "stale_self_update",
            "A file changed since this turn saw it; ask the Lead again.",
            stale=stale,
            changes=decided["changes"],
        )
    return SelfUpdateDecided.model_validate(decided)


@router.post(
    "/lead/turns/{turn_id}/request",
    response_model=ApprovedRequest,
    responses={
        409: {"model": ErrorResponse, "description": "The spend limit asks, or it is unknown"},
        422: {"model": ErrorResponse, "description": "The turn prepared no paid job"},
    },
)
def approve_request(
    turn_id: TurnIdPath,
    body: RequestApproval,
    scope: StudyScopeDep,
    session: SessionDep,
    settings: SettingsDep,
) -> ApprovedRequest:
    """Approve the design job the caller's own Lead turn prepared: held to the study's spend
    limit, started and recorded in the approval ledger, once."""
    with _lead_errors():
        started = ResearchLead(session, scope).approve_request(
            turn_id,
            confirm_cost_usd=body.confirm_cost_usd,
            reservation_usd=settings.ai_research_reservation_usd,
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
