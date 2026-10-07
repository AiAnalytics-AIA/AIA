"""Deep Research's policy values: read by any member, changed by an administrator (ADR 0022).

Organization-level, like members and system prompts: every route takes an
``OrganizationContext``, which carries no client or study and reads no research data.

* ``GET  /deep-research/settings`` -- every catalogued setting, what is in force (an approved
  value or the code's proposed default) and what live still needs approved.
* ``GET  /deep-research/settings/{key}`` -- one setting, its proposed versions and its
  approval history.
* ``POST /deep-research/settings/{key}/versions`` -- propose a value (an administrator); it is
  not in force until approved.
* ``PUT  /deep-research/settings/{key}/approval`` -- approve a version, or with
  ``version_number: null`` return to the proposed default (an administrator).

An approval changes only runs enqueued afterwards (chunk 43 pins them). Switches, secrets and
the model route are not here: they stay in the deployment, and no setting can switch a rail
off. This module only reads and writes the settings store; it starts nothing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from aia_core.domain.deep_research.settings import (
    CATALOGUE_VERSION,
    Effective,
    SettingDefinition,
    SettingValue,
)
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsReader,
    DeepResearchSettingsRepository,
    SettingApproval,
    SettingOverview,
    SettingRefused,
    StoredSettingVersion,
)
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

router = APIRouter(
    prefix="/deep-research/settings",
    tags=["deep-research-settings"],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not an organization administrator"},
        404: {"model": ErrorResponse, "description": "No such setting or version"},
    },
)

SettingKey = Annotated[str, Path(max_length=128, pattern=r"^[a-z0-9_.]+$")]

#: How a refusal reads on the wire. Anything not listed is the caller's input: 422.
_STATUS: dict[str, int] = {
    "unknown_setting": 404,
    "unknown_version": 404,
    "self_approval_not_allowed": 403,
    "concurrent_edit": 409,
    "approved_value_invalid": 409,
}


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


def _wire(value: SettingValue) -> Any:
    return list(value) if isinstance(value, tuple) else value


class SettingSummary(BaseModel):
    """One setting: what it is, its bounds, and what is in force."""

    model_config = ConfigDict(extra="forbid")

    key: str
    group: str
    type: str
    label: str
    unit: str
    minimum: float | None
    maximum: float | None
    #: A cap: an approved value may lower the code's default and never raise it.
    lower_only: bool
    required_for_live: bool
    #: The value shapes a run's result, so runs made under different values share no work.
    method: bool
    #: The code's proposed default; ``null`` where the code holds nothing (unknown, never zero).
    default: Any
    default_source: str
    #: What a run enqueued now would use.
    value: Any
    origin: str  # "approved" | "proposed_default"
    version: int | None
    approved_by: str | None
    approved_at: datetime | None
    version_count: int
    latest_number: int | None


class SettingsOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalogue_version: str
    #: Whether the caller may propose and approve (an organization OWNER or ADMIN).
    may_administer: bool
    #: Every setting live still needs approved (as ``approved``, for a table's status).
    missing_for_live: list[str]
    settings: list[SettingSummary]


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_number: int
    value: Any
    value_sha256: str
    source_url: str
    note: str
    created_by: str
    created_at: datetime


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: int
    #: ``null``: the approval was withdrawn and the code's default came back into force.
    version_number: int | None
    approved_by: str
    reason: str
    approved_at: datetime


class SettingDetail(SettingSummary):
    versions: list[VersionResponse]
    history: list[ApprovalResponse]


class ProposeRequest(BaseModel):
    """A value for the setting, as JSON: a number, text, yes/no, or a list of text."""

    model_config = ConfigDict(extra="forbid")

    value: Any
    #: Where the value comes from (a terms page, a quota letter): an https URL, or empty.
    source_url: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=255)


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: The version to put in force; ``null`` returns to the code's proposed default.
    version_number: int | None = Field(ge=1)
    reason: str = Field(default="", max_length=255)


def _summary(
    defn: SettingDefinition, item: Effective, count: int, latest: int | None
) -> SettingSummary:
    return SettingSummary(
        key=defn.key,
        group=defn.group.value,
        type=defn.type.value,
        label=defn.label,
        unit=defn.unit,
        minimum=defn.minimum,
        maximum=defn.maximum,
        lower_only=defn.lower_only,
        required_for_live=defn.required_for_live,
        method=defn.method,
        default=_wire(defn.default),
        default_source=defn.default_source,
        value=_wire(item.value),
        origin=item.origin.value,
        version=item.version,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        version_count=count,
        latest_number=latest,
    )


def _from_overview(o: SettingOverview) -> SettingSummary:
    return _summary(o.definition, o.effective, o.version_count, o.latest_number)


def _version(v: StoredSettingVersion) -> VersionResponse:
    return VersionResponse(
        version_number=v.version_number,
        value=_wire(v.value),
        value_sha256=v.value_sha256,
        source_url=v.source_url,
        note=v.note,
        created_by=v.created_by,
        created_at=v.created_at,
    )


def _approval(a: SettingApproval) -> ApprovalResponse:
    return ApprovalResponse(
        approval_id=a.approval_id,
        version_number=a.version_number,
        approved_by=a.approved_by,
        reason=a.reason,
        approved_at=a.approved_at,
    )


def _refused(exc: ScopeDenied | SettingRefused) -> HTTPException:
    if isinstance(exc, ScopeDenied):
        return HTTPException(
            status_code=403,
            detail={
                "code": "insufficient_role",
                "message": "Changing Deep Research settings requires an organization OWNER or "
                "ADMIN.",
                "details": {"reason": exc.reason},
            },
        )
    return HTTPException(
        status_code=_STATUS.get(exc.reason, 422),
        detail={"code": exc.reason, "message": str(exc)},
    )


def _one(reader: DeepResearchSettingsReader, key: str) -> SettingOverview:
    item = next((o for o in reader.overview() if o.definition.key == key), None)
    if item is None:
        raise SettingRefused(f"{key}: is not a Deep Research setting", reason="unknown_setting")
    return item


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.get("", response_model=SettingsOverview, summary="Every setting and what is in force")
def list_settings(org: OrganizationDep, session: SessionDep) -> SettingsOverview:
    try:
        reader = DeepResearchSettingsReader(session, org)
        overview = reader.overview()
        missing = reader.effective().missing_for_live()
    except SettingRefused as exc:
        raise _refused(exc) from exc
    return SettingsOverview(
        catalogue_version=CATALOGUE_VERSION,
        may_administer=org.may_administer,
        missing_for_live=list(missing),
        settings=[_from_overview(o) for o in overview],
    )


@router.get("/{key}", response_model=SettingDetail, summary="One setting, its versions and log")
def read_setting(key: SettingKey, org: OrganizationDep, session: SessionDep) -> SettingDetail:
    try:
        reader = DeepResearchSettingsReader(session, org)
        item = _one(reader, key)
        return SettingDetail(
            **_from_overview(item).model_dump(),
            versions=[_version(v) for v in reader.versions(key)],
            history=[_approval(a) for a in reader.history(key)],
        )
    except SettingRefused as exc:
        raise _refused(exc) from exc


@router.post(
    "/{key}/versions",
    response_model=VersionResponse,
    status_code=201,
    summary="Propose a value (it is not in force until approved)",
)
def propose(
    key: SettingKey, body: ProposeRequest, org: OrganizationDep, session: SessionDep
) -> VersionResponse:
    try:
        stored = DeepResearchSettingsRepository(session, org).propose(
            key, body.value, source_url=body.source_url, note=body.note
        )
    except (ScopeDenied, SettingRefused) as exc:
        raise _refused(exc) from exc
    return _version(stored)


@router.put(
    "/{key}/approval",
    response_model=SettingSummary,
    summary="Put a version in force, or return to the proposed default",
)
def approve(
    key: SettingKey, body: ApproveRequest, org: OrganizationDep, session: SessionDep
) -> SettingSummary:
    """Takes effect for runs enqueued afterwards; a run already enqueued keeps its settings."""
    try:
        DeepResearchSettingsRepository(session, org).approve(
            key, body.version_number, reason=body.reason
        )
        return _from_overview(_one(DeepResearchSettingsReader(session, org), key))
    except (ScopeDenied, SettingRefused) as exc:
        raise _refused(exc) from exc
