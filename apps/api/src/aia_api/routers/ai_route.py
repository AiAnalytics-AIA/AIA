"""Settings → AI běh → Trasa modelu as the worker composed it (lead-orchestration LO12b).

``GET /settings/ai-route``: the AI route the newest worker start recorded -- its zone, the
operator's confirmations, its retention and approved classes, the class gates -- and, for each
data class, whether that route carries it by the gateway's own checks, or which refusal it would
meet (an ``egress_`` code, as a parked step names it). ``recorded: false`` when no worker has
recorded a route: nothing is presumed carried. The record says what the newest start composed,
not that a worker runs now. Any member; read-only. 404 unless AIA_AI_ROUTE_PREFLIGHT_ENABLED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from aia_core.application.deep_research_reach import newest_composition
from aia_core.domain.ai_route_reach import class_reach, lead_preflight
from aia_core.domain.residency import DataClass
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..dependencies import OrganizationDep, SessionDep, SettingsDep
from ..schemas.projects import ErrorResponse

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    404: {"model": ErrorResponse, "description": "Not a member, or the pre-flight read is off"},
}

router = APIRouter(prefix="/settings", tags=["settings"], responses=_RESPONSES)

_LETTER: dict[DataClass, Literal["A", "B", "C"]] = {
    DataClass.CLASS_A_CLIENT_CONFIDENTIAL: "A",
    DataClass.CLASS_B_DERIVED_CLIENT: "B",
    DataClass.CLASS_C_INTERNAL: "C",
}


class ClassOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_class: Literal["A", "B", "C"]
    #: Why the route refuses it (``egress_…``); ``null``: carried.
    refusal: str | None
    #: Carried only because advisory class gates pass a class-only refusal (develop).
    advisory: bool


class AiRouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded: bool
    worker: str | None = None
    build_sha: str | None = None
    composed_at: datetime | None = None
    #: AIA_AI_RUNTIME_ENABLED as the worker composed it.
    runtime: bool | None = None
    route_id: str | None = None
    region: str | None = None
    zone: str | None = None
    eu_processing_approved: bool | None = None
    excluded_from_training: bool | None = None
    #: ``null`` with a route: unspecified, which is not zero.
    retention_days: int | None = None
    approved_for: list[Literal["A", "B", "C"]] = []
    class_gates: str | None = None
    #: ``off``, ``unconfigured`` (every turn parks) or ``configured``.
    study_lead: str | None = None
    classes: list[ClassOut] = []
    #: The reason a study Lead turn would park on this composition; ``null``: none recorded.
    lead_refusal: str | None = None


@router.get("/ai-route", response_model=AiRouteResponse, summary="The AI route the worker composed")
def get_ai_route(
    scope: OrganizationDep, session: SessionDep, settings: SettingsDep
) -> AiRouteResponse:
    if not settings.ai_route_preflight_enabled:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {"code": "ai_route_preflight_off", "message": "The AI route pre-flight read is off."},
        )
    composition = newest_composition(session, scope)
    reach = composition.ai_route if composition is not None else None
    if composition is None or reach is None:
        return AiRouteResponse(recorded=False)
    route = reach.route
    return AiRouteResponse(
        recorded=True,
        worker=composition.worker,
        build_sha=composition.build_sha,
        composed_at=composition.composed_at,
        runtime=reach.runtime,
        route_id=route.route_id if route else None,
        region=reach.region,
        zone=route.zone.value if route else None,
        eu_processing_approved=route.eu_processing_approved if route else None,
        excluded_from_training=route.excluded_from_training if route else None,
        retention_days=route.retention_days if route else None,
        approved_for=sorted(_LETTER[c] for c in route.approved_for) if route else [],
        class_gates=reach.class_gates.value,
        study_lead=reach.study_lead.value,
        classes=[
            ClassOut(data_class=_LETTER[v.data_class], refusal=v.refusal, advisory=v.advisory)
            for v in sorted(class_reach(reach).values(), key=lambda v: _LETTER[v.data_class])
        ],
        lead_refusal=lead_preflight(reach),
    )
