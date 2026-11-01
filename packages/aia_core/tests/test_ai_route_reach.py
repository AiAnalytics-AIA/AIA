"""The AI route as the worker composed it, read before a turn is sent (lead-orchestration LO12b).

The pre-flight must say exactly what the gateway would: ``route_refusal`` is held to
``evaluate_egress`` over every route shape, class and gate mode, and the record a worker keeps
reads back as written, or as unknown.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.research_lead import WorkerPreflight, worker_readiness
from aia_core.domain.ai_route_reach import (
    AiRouteReach,
    LeadComposition,
    ai_route_from_record,
    ai_route_record,
    class_reach,
    lead_preflight,
)
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.residency import (
    DataClass,
    EgressDenied,
    ProviderRoute,
    ResidencyZone,
    evaluate_egress,
    route_refusal,
)

A, B, C = (
    DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    DataClass.CLASS_B_DERIVED_CLIENT,
    DataClass.CLASS_C_INTERNAL,
)


def _route(
    *,
    classes: frozenset[DataClass] = frozenset({A, B, C}),
    zone: ResidencyZone = ResidencyZone.EU,
    eu: bool = True,
    training: bool = True,
    retention: int | None = 0,
) -> ProviderRoute:
    return ProviderRoute(
        route_id="bedrock-eu-primary",
        provider="aws_bedrock",
        zone=zone,
        eu_processing_approved=eu,
        excluded_from_training=training,
        retention_days=retention,
        approved_for=classes,
    )


def _reach(
    route: ProviderRoute | None = None,
    *,
    gates: DataClassGates = DataClassGates.ENFORCE,
    lead: LeadComposition = LeadComposition.CONFIGURED,
) -> AiRouteReach:
    route = _route() if route is None else route
    return AiRouteReach(True, route, "eu-central-1", gates, lead)


# --------------------------------------------------------------- one rule with the gateway


def _subsets() -> list[frozenset[DataClass]]:
    every = list(DataClass)
    return [frozenset(s) for n in range(4) for s in itertools.combinations(every, n)]


def test_route_refusal_says_what_evaluate_egress_does_over_every_route(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope(user="lead", study="primary")
    cases = 0
    for classes, zone, eu, training, retention, data_class, gates in itertools.product(
        _subsets(),
        list(ResidencyZone),
        (True, False),
        (True, False),
        (None, 0, 30),
        list(DataClass),
        list(DataClassGates),
    ):
        route = _route(classes=classes, zone=zone, eu=eu, training=training, retention=retention)
        try:
            evaluate_egress(scope=scope, data_class=data_class, route=route, class_gates=gates)
            expected = None
        except EgressDenied as exc:
            expected = exc.reason
        assert route_refusal(route, data_class, class_gates=gates) == expected, (
            route,
            data_class,
            gates,
        )
        cases += 1
    assert cases == 8 * 3 * 2 * 2 * 3 * 3 * 2


def test_no_route_is_refused_as_the_gateway_refuses_it(session: Session, scoped: Any) -> None:
    scope = scoped.scope(user="lead", study="primary")
    with pytest.raises(EgressDenied) as denied:
        evaluate_egress(scope=scope, data_class=C, route=None)
    assert route_refusal(None, C) == denied.value.reason == "no_approved_route"


# --------------------------------------------------------------- what a Lead turn meets


@pytest.mark.parametrize(
    ("route", "reason"),
    [
        (_route(classes=frozenset({C})), "egress_route_not_approved_for_class"),
        (_route(eu=False), "egress_residency_violation"),
        (_route(zone=ResidencyZone.UNKNOWN), "egress_residency_violation"),
        (_route(training=False), "egress_training_exclusion_missing"),
        (_route(retention=None), "egress_retention_unspecified"),
    ],
)
def test_a_route_that_cannot_carry_class_b_refuses_every_lead_turn(
    route: ProviderRoute, reason: str
) -> None:
    assert lead_preflight(_reach(route)) == reason


def test_a_route_that_carries_class_b_refuses_no_turn_for_its_terms() -> None:
    # Class A not approved: a turn whose knowledge raises it may still refuse; never claimed.
    assert lead_preflight(_reach(_route(classes=frozenset({B, C})))) is None


def test_advisory_gates_pass_the_class_but_never_residency() -> None:
    advisory = DataClassGates.ADVISORY
    assert lead_preflight(_reach(_route(classes=frozenset({C})), gates=advisory)) is None
    verdict = class_reach(_reach(_route(classes=frozenset({C})), gates=advisory))[B]
    assert (verdict.refusal, verdict.advisory) == (None, True)
    assert (
        lead_preflight(_reach(_route(classes=frozenset({C}), retention=None), gates=advisory))
        == "egress_retention_unspecified"
    )


@pytest.mark.parametrize("lead", [LeadComposition.OFF, LeadComposition.UNCONFIGURED])
def test_a_lead_not_configured_parks_every_turn_whatever_the_route(lead: LeadComposition) -> None:
    assert lead_preflight(_reach(lead=lead)) == "research_lead_unconfigured"


def test_no_runtime_parks_the_lead_and_carries_no_class() -> None:
    off = AiRouteReach(False, None, None, DataClassGates.ENFORCE, LeadComposition.OFF)
    assert lead_preflight(off) == "research_lead_unconfigured"
    assert {v.refusal for v in class_reach(off).values()} == {"egress_no_approved_route"}


# --------------------------------------------------------------- the stored record


def test_the_record_reads_back_as_written_and_names_no_price_or_target() -> None:
    reach = _reach(_route(classes=frozenset({B, C}), retention=None))
    record = ai_route_record(reach)
    assert ai_route_from_record(record) == reach
    flat = repr(record).lower()
    for word in ("usd", "price", "arn", "invocation", "model_id"):
        assert word not in flat


@pytest.mark.parametrize(
    "record",
    [
        None,
        {},
        {
            "runtime": True,
            "route": None,
            "region": None,
            "class_gates": "enforce",
            "study_lead": "configured",
        },
        {**ai_route_record(_reach()), "class_gates": "maybe"},
        {**ai_route_record(_reach()), "runtime": "yes"},
        {
            **ai_route_record(_reach()),
            "route": {**ai_route_record(_reach())["route"], "retention_days": "0"},
        },
        {
            **ai_route_record(_reach()),
            "route": {**ai_route_record(_reach())["route"], "excluded_from_training": 1},
        },
        {
            **ai_route_record(_reach()),
            "route": {**ai_route_record(_reach())["route"], "approved_for": ["CLASS_D"]},
        },
    ],
)
def test_a_record_that_does_not_read_is_unknown_never_a_route(record: Any) -> None:
    assert ai_route_from_record(record) is None


# --------------------------------------------------------------- the Lead's readiness


NOW = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)


def _turn(status: str, reason: str | None, decided_at: datetime | None) -> dict[str, Any]:
    return {"actor": "lead", "status": status, "reason": reason, "decided_at": decided_at}


def _preflight(reach: AiRouteReach | None = None) -> WorkerPreflight:
    return WorkerPreflight(_reach() if reach is None else reach, NOW, "abc1234")


def test_without_the_preflight_only_a_parked_turn_is_read_and_never_ready() -> None:
    assert worker_readiness([]) == (None, None, None)
    assert worker_readiness([_turn("COMPLETED", None, NOW)]) == (None, None, None)
    assert worker_readiness([_turn("WAITING", "research_lead_unconfigured", NOW)]) == (
        False,
        "newest_turn",
        "research_lead_unconfigured",
    )


def test_a_composition_that_refuses_nothing_is_ready_from_its_record() -> None:
    """Nigel, 2026-10-28: true from the record, its time shown beside it."""
    assert worker_readiness([], _preflight()) == (True, "composition", None)


def test_no_record_is_never_ready() -> None:
    assert worker_readiness([], WorkerPreflight(None)) == (None, None, None)


def test_the_composition_names_the_refusal_before_any_turn() -> None:
    preflight = _preflight(_reach(_route(classes=frozenset({C}))))
    assert worker_readiness([], preflight) == (
        False,
        "composition",
        "egress_route_not_approved_for_class",
    )
    # A turn answered since proves nothing about the route: the record still refuses Class B.
    assert worker_readiness([_turn("COMPLETED", None, NOW)], preflight)[1] == "composition"


def test_a_turn_parked_at_or_after_the_newest_start_wins_over_its_record() -> None:
    for decided in (NOW, NOW + timedelta(minutes=1)):
        turns = [_turn("WAITING", "ai_runtime_unavailable", decided)]
        assert worker_readiness(turns, _preflight()) == (
            False,
            "newest_turn",
            "ai_runtime_unavailable",
        )


def test_a_turn_parked_before_a_worker_restarted_yields_to_the_newer_start() -> None:
    turns = [_turn("WAITING", "research_lead_unconfigured", NOW - timedelta(minutes=1))]
    assert worker_readiness(turns, _preflight()) == (True, "composition", None)


def test_a_parked_turn_with_no_decision_time_is_never_overruled() -> None:
    turns = [_turn("FAILED", "research_lead_unconfigured", None)]
    assert worker_readiness(turns, _preflight())[:2] == (False, "newest_turn")


def test_a_turn_refused_for_its_own_material_says_nothing_about_the_worker() -> None:
    """A turn whose knowledge raised it to Class A, over a route approved for B and C, is that
    turn's refusal (its pane shows it), never the worker's."""
    turns = [_turn("WAITING", "egress_route_not_approved_for_class", NOW + timedelta(minutes=1))]
    preflight = _preflight(_reach(_route(classes=frozenset({B, C}))))
    assert worker_readiness(turns, preflight) == (True, "composition", None)
