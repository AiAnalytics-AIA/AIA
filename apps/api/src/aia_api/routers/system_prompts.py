"""System prompts: what each step tells the model, edited by an administrator (ADR 0020).

Organization-level administration, so every route takes an ``OrganizationContext`` and
refuses anyone who may not administer the organization. The prompt text is never
returned to an ordinary member: it is the product's method. This module only reads and
writes the prompt store; it calls no model. A prompt is *tested* by queuing a normal
agent job pinned to a stored version (``POST .../research/agent-jobs``), which the worker
runs like any other.

A saved version does not run. Putting one live is a second, deliberate act
(``PUT .../active``). By default the person who wrote a version may put it live (ADR 0019:
no approval between people); an organization that has turned independent review back on
gets a refusal for the author instead, as for every other approval in AIA.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from aia_core.domain.prompt_slots import PromptSlot
from aia_core.domain.prompts import PROMPT_TEXT_MAX_CHARS
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.prompt_repository import (
    ActiveState,
    PromptOverview,
    PromptRefused,
    PromptRepository,
    StoredVersion,
)
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/system-prompts",
    tags=["system-prompts"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not an organization administrator"},
        404: {"model": ErrorResponse, "description": "No such prompt or version"},
    },
)

PromptId = Annotated[str, Path(max_length=128, pattern=r"^[a-z0-9_.]+$")]

#: How a refusal reads on the wire. Anything not listed is the caller's input: 422.
_STATUS: dict[str, int] = {
    "unknown_prompt": 404,
    "unknown_version": 404,
    "self_activation_not_allowed": 403,
    "concurrent_edit": 409,
    "not_editable": 409,
}


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class ActiveResponse(BaseModel):
    """What runs now. ``origin`` ``baseline`` is the wording shipped in code."""

    model_config = ConfigDict(extra="forbid")

    version_number: int | None
    label: str
    origin: str
    text_sha256: str
    activated_by: str | None
    activated_at: datetime | None
    reason: str


class SlotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    family: str
    #: A wired prompt is read by a running step, so an edit takes effect. Otherwise
    #: ``unwired_reason`` says why not; the page words it and offers no editor.
    wired: bool
    unwired_reason: str | None
    baseline_version: str
    baseline_chars: int
    active: ActiveResponse
    version_count: int
    latest_number: int | None


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_number: int
    label: str
    text: str
    text_sha256: str
    based_on: str
    note: str
    created_by: str
    created_at: datetime


class ActivationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_id: int
    version_number: int | None
    label: str | None
    activated_by: str
    reason: str
    activated_at: datetime


class SlotDetail(SlotSummary):
    #: The code-owned text placed in front of the instruction. Shown, never editable.
    fixed_prefix: str
    #: The wording this code ships: the editable part's baseline.
    baseline_text: str
    required_literals: list[str]
    max_chars: int
    versions: list[VersionResponse]
    history: list[ActivationResponse]


class VersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=PROMPT_TEXT_MAX_CHARS * 2)
    note: str = Field(default="", max_length=255)
    #: The label this was edited from (``baseline`` or ``e<n>``). Context only.
    based_on: str | None = Field(default=None, max_length=64)


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: A stored version, or ``null`` for the wording shipped in code.
    version_number: int | None = Field(ge=1)
    reason: str = Field(default="", max_length=255)


# --------------------------------------------------------------------------- #
# Mapping
# --------------------------------------------------------------------------- #


def _active(state: ActiveState) -> ActiveResponse:
    return ActiveResponse(
        version_number=state.version_number,
        label=state.label,
        origin=state.origin,
        text_sha256=state.text_sha256,
        activated_by=state.activated_by,
        activated_at=state.activated_at,
        reason=state.reason,
    )


def _summary(item: PromptOverview) -> SlotSummary:
    slot: PromptSlot = item.slot
    return SlotSummary(
        prompt_id=slot.prompt_id,
        family=slot.family,
        wired=slot.wired,
        unwired_reason=slot.unwired_reason,
        baseline_version=slot.baseline_version,
        baseline_chars=len(slot.baseline_text),
        active=_active(item.active),
        version_count=item.version_count,
        latest_number=item.latest_number,
    )


def _version(v: StoredVersion) -> VersionResponse:
    return VersionResponse(
        version_number=v.version_number,
        label=v.label,
        text=v.text,
        text_sha256=v.text_sha256,
        based_on=v.based_on,
        note=v.note,
        created_by=v.created_by,
        created_at=v.created_at,
    )


def _refused(exc: ScopeDenied | PromptRefused) -> HTTPException:
    if isinstance(exc, ScopeDenied):
        return HTTPException(
            status_code=403,
            detail={
                "code": "insufficient_role",
                "message": "Editing system prompts requires an organization OWNER or ADMIN.",
                "details": {"reason": exc.reason},
            },
        )
    return HTTPException(
        status_code=_STATUS.get(exc.reason, 422),
        detail={"code": exc.reason, "message": str(exc)},
    )


def _detail(repo: PromptRepository, prompt_id: str) -> SlotDetail:
    item = next((o for o in repo.overview() if o.slot.prompt_id == prompt_id), None)
    if item is None:
        raise PromptRefused(f"unknown prompt {prompt_id}", reason="unknown_prompt")
    slot = item.slot
    return SlotDetail(
        **_summary(item).model_dump(),
        fixed_prefix=slot.fixed_prefix,
        baseline_text=slot.baseline_text,
        required_literals=list(slot.required_literals),
        max_chars=PROMPT_TEXT_MAX_CHARS,
        versions=[_version(v) for v in repo.versions(prompt_id)],
        history=[ActivationResponse(**h) for h in repo.history(prompt_id)],
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[SlotSummary], summary="Every system prompt and what runs")
def list_prompts(admin: OrganizationDep, session: SessionDep) -> list[SlotSummary]:
    try:
        return [_summary(o) for o in PromptRepository(session, admin).overview()]
    except ScopeDenied as exc:
        raise _refused(exc) from exc


@router.get(
    "/{prompt_id}", response_model=SlotDetail, summary="One prompt, its versions and history"
)
def read_prompt(prompt_id: PromptId, admin: OrganizationDep, session: SessionDep) -> SlotDetail:
    try:
        return _detail(PromptRepository(session, admin), prompt_id)
    except (ScopeDenied, PromptRefused) as exc:
        raise _refused(exc) from exc


@router.post(
    "/{prompt_id}/versions",
    response_model=VersionResponse,
    status_code=201,
    summary="Save an edit as a new version (it does not run until activated)",
)
def create_version(
    prompt_id: PromptId, body: VersionCreate, admin: OrganizationDep, session: SessionDep
) -> VersionResponse:
    try:
        version = PromptRepository(session, admin).create_version(
            prompt_id, body.text, note=body.note, based_on=body.based_on
        )
    except (ScopeDenied, PromptRefused) as exc:
        raise _refused(exc) from exc
    return _version(version)


@router.put(
    "/{prompt_id}/active",
    response_model=ActiveResponse,
    summary="Put a version live, or return to the wording shipped in code",
)
def activate(
    prompt_id: PromptId, body: ActivateRequest, admin: OrganizationDep, session: SessionDep
) -> ActiveResponse:
    """Takes effect for jobs queued afterwards; a job already queued keeps its prompt."""
    try:
        return _active(
            PromptRepository(session, admin).activate(
                prompt_id, body.version_number, reason=body.reason
            )
        )
    except (ScopeDenied, PromptRefused) as exc:
        raise _refused(exc) from exc
