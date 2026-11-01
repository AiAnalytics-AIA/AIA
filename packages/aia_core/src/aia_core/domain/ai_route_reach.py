"""The AI route as the worker composed it, read before a turn is sent (lead-orchestration LO12b).

The API cannot evaluate a model call's class against the route: the route's facts (its zone,
the operator's confirmations, its retention, the classes it is approved for) exist only in the
worker's environment. So the worker records them at start, beside Deep Research's reach in the
same composition row (deep-research-web-search 52), and the API reads that record:

* :func:`class_reach`: for each data class, the reason :func:`residency.route_refusal` gives
  for it over the recorded route, or ``None`` when the route carries it -- the gateway's own
  checks, never a copy of them;
* :func:`lead_preflight`: the reason a study Lead turn would park on this composition, or
  ``None``. A turn always carries the design, Class B by rule (``material_rules``), so a route
  that refuses B refuses every turn. Whether a turn's knowledge raises it to Class A depends on
  its content: that is never claimed here.

The record says what the newest worker start was composed to do, not that a worker is running.
Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .deployment import DataClassGates
from .residency import DataClass, ProviderRoute, ResidencyZone, route_refusal

__all__ = [
    "LEAD_TURN_CLASS",
    "LEAD_UNCONFIGURED",
    "AiRouteReach",
    "ClassVerdict",
    "LeadComposition",
    "ai_route_from_record",
    "ai_route_record",
    "class_reach",
    "lead_preflight",
]

#: The least a Lead turn carries: its design and the researcher's message (``material_rules``).
LEAD_TURN_CLASS: Final = DataClass.CLASS_B_DERIVED_CLIENT
#: The park a turn meets when the composition cannot answer it (``aia_executors.research_lead``).
LEAD_UNCONFIGURED: Final = "research_lead_unconfigured"


class LeadComposition(StrEnum):
    #: ``AIA_AI_RESEARCH_LEAD_ENABLED`` is not true.
    OFF = "off"
    #: Switched on, without its output cap and reservation: every turn parks.
    UNCONFIGURED = "unconfigured"
    CONFIGURED = "configured"


@dataclass(frozen=True, slots=True)
class AiRouteReach:
    #: ``AIA_AI_RUNTIME_ENABLED``: ``False`` and there is no route.
    runtime: bool
    route: ProviderRoute | None
    region: str | None
    class_gates: DataClassGates
    study_lead: LeadComposition


def ai_route_record(reach: AiRouteReach) -> dict[str, Any]:
    """``reach`` as stored: the route's facts, nothing priced and no invocation target."""
    route = reach.route
    return {
        "runtime": reach.runtime,
        "class_gates": reach.class_gates.value,
        "study_lead": reach.study_lead.value,
        "region": reach.region,
        "route": None
        if route is None
        else {
            "route_id": route.route_id,
            "provider": route.provider,
            "zone": route.zone.value,
            "eu_processing_approved": route.eu_processing_approved,
            "excluded_from_training": route.excluded_from_training,
            "retention_days": route.retention_days,
            "approved_for": sorted(c.value for c in route.approved_for),
        },
    }


def _retention(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("retention_days")
    return value


def ai_route_from_record(record: Mapping[str, Any] | None) -> AiRouteReach | None:
    """A stored record, or ``None`` when there is none or it does not read: an unreadable
    record is unknown, never a route that carries anything."""
    if not isinstance(record, Mapping):
        return None
    try:
        raw = record["route"]
        route = None
        if raw is not None:
            for key in ("eu_processing_approved", "excluded_from_training"):
                if not isinstance(raw[key], bool):
                    raise ValueError(key)
            route = ProviderRoute(
                route_id=str(raw["route_id"]),
                provider=str(raw["provider"]),
                zone=ResidencyZone(raw["zone"]),
                eu_processing_approved=raw["eu_processing_approved"],
                excluded_from_training=raw["excluded_from_training"],
                retention_days=_retention(raw["retention_days"]),
                approved_for=frozenset(DataClass(c) for c in raw["approved_for"]),
            )
        runtime = record["runtime"]
        if not isinstance(runtime, bool) or (runtime and route is None):
            raise ValueError("runtime")
        region = record["region"]
        return AiRouteReach(
            runtime=runtime,
            route=route,
            region=None if region is None else str(region),
            class_gates=DataClassGates(record["class_gates"]),
            study_lead=LeadComposition(record["study_lead"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class ClassVerdict:
    data_class: DataClass
    #: Why the route refuses it, an ``egress_`` code as a turn's park names it; ``None``: carried.
    refusal: str | None
    #: Carried only because advisory class gates pass a class-only refusal (develop).
    advisory: bool


def class_reach(reach: AiRouteReach) -> dict[DataClass, ClassVerdict]:
    """For each class, whether the recorded route carries it, by the gateway's own checks
    (``residency.route_refusal``). No runtime: no route, for every class."""
    route = reach.route if reach.runtime else None
    out: dict[DataClass, ClassVerdict] = {}
    for data_class in DataClass:
        reason = route_refusal(route, data_class, class_gates=reach.class_gates)
        out[data_class] = ClassVerdict(
            data_class,
            None if reason is None else f"egress_{reason}",
            advisory=reason is None and route is not None and data_class not in route.approved_for,
        )
    return out


def lead_preflight(reach: AiRouteReach) -> str | None:
    """The reason a study Lead turn would park on this composition, or ``None`` when it was
    composed to answer one (which proves nothing about a worker running now)."""
    if not reach.runtime or reach.study_lead is not LeadComposition.CONFIGURED:
        return LEAD_UNCONFIGURED
    return class_reach(reach)[LEAD_TURN_CLASS].refusal
