"""Settings → Deep Research → Dosah (deep-research-web-search 52, settings-backends SB6).

``GET /settings/deep-research/reach[?data_class=A|B|C]``: every route and connector the code
builds, as the newest worker's composition made it -- ``waiting`` (a priced route whose live
settings the organization has not all approved), ``active``, ``refused`` (it cannot be
composed, or, asked for a data class, it does not take it) or ``built`` (in the code, not
composed, and which switch decides it) -- in that order. ``recorded: false`` when no worker has
recorded a composition: nothing is presumed reachable. Any member; read-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from aia_core.application.deep_research_reach import deep_research_reach
from aia_core.domain.deep_research_reach import ReachKind, ReachState
from aia_core.domain.residency import DataClass
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    404: {"model": ErrorResponse, "description": "Not a member of the organization"},
}

router = APIRouter(prefix="/settings/deep-research", tags=["settings"], responses=_RESPONSES)

_CLASSES: dict[str, DataClass] = {
    "A": DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    "B": DataClass.CLASS_B_DERIVED_CLIENT,
    "C": DataClass.CLASS_C_INTERNAL,
}
_LETTER = {v: k for k, v in _CLASSES.items()}


class RouteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: str
    kind: ReachKind
    state: ReachState
    reason: str | None
    detail: str | None
    #: The data classes it is approved for, as letters; empty when not composed.
    classes: list[str]
    priced: bool
    zone: str | None
    missing_settings: list[str]
    #: Advisory class gates (develop): a class refusal would be recorded and passed.
    class_advisory: bool


class ReachResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded: bool
    worker: str | None
    build_sha: str | None
    composed_at: datetime | None
    agent_directed: bool | None
    class_gates: str | None
    data_class: Literal["A", "B", "C"] | None
    #: Every setting live still needs approved by this organization (ADR 0022).
    missing_for_live: list[str]
    routes: list[RouteOut]


@router.get("/reach", response_model=ReachResponse, summary="What Deep Research can reach")
def get_reach(
    scope: OrganizationDep,
    session: SessionDep,
    data_class: Annotated[Literal["A", "B", "C"] | None, Query()] = None,
) -> ReachResponse:
    reach = deep_research_reach(
        session, scope, data_class=_CLASSES[data_class] if data_class else None
    )
    c = reach.composition
    return ReachResponse(
        recorded=c is not None,
        worker=c.worker if c else None,
        build_sha=c.build_sha if c else None,
        composed_at=c.composed_at if c else None,
        agent_directed=c.agent_directed if c else None,
        class_gates=c.class_gates if c else None,
        data_class=data_class,
        missing_for_live=list(reach.missing_for_live),
        routes=[
            RouteOut(
                route=r.route,
                kind=r.kind,
                state=r.state,
                reason=r.reason,
                detail=r.detail,
                classes=[_LETTER[k] for k in r.classes],
                priced=r.priced,
                zone=r.zone,
                missing_settings=list(r.missing_settings),
                class_advisory=r.class_advisory,
            )
            for r in reach.routes
        ],
    )
