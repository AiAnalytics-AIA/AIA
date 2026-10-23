"""Deep Research's reach as data (deep-research-web-search 52), pure."""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research_reach import (
    ReachKind,
    ReachState,
    RouteReach,
    order_reach,
    reach_from_record,
    reach_record,
)
from aia_core.domain.residency import DataClass


def test_waiting_then_active_then_what_is_off() -> None:
    routes = [
        RouteReach("b", ReachKind.SEARCH, ReachState.BUILT),
        RouteReach("a", ReachKind.FETCH, ReachState.ACTIVE),
        RouteReach("r", ReachKind.CONNECTOR, ReachState.REFUSED),
        RouteReach("w", ReachKind.SEARCH, ReachState.WAITING),
    ]
    assert [r.route for r in order_reach(routes)] == ["w", "a", "r", "b"]


def test_a_record_reads_back_as_written_and_an_unknown_state_is_refused() -> None:
    routes = [
        RouteReach(
            "brave-web-search",
            ReachKind.SEARCH,
            ReachState.ACTIVE,
            classes=(DataClass.CLASS_C_INTERNAL,),
            priced=True,
            zone="NON_EU",
            any_class_when_advisory=True,
        ),
        RouteReach("public-web-fetch", ReachKind.FETCH, ReachState.ACTIVE),
    ]
    assert reach_from_record(reach_record(routes)) == routes
    bad = reach_record(routes)
    bad[0]["state"] = "maybe"
    with pytest.raises(ValueError):
        reach_from_record(bad)
