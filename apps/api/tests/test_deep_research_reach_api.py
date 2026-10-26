"""Settings → Deep Research → Dosah over HTTP (deep-research-web-search 52, SB6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aia_core.domain.deep_research_reach import ReachKind, ReachState, RouteReach
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.deep_research_composition_repository import record_composition
from fastapi import FastAPI
from fastapi.testclient import TestClient

URL = "/api/v1/settings/deep-research/reach"
C = (DataClass.CLASS_C_INTERNAL,)


def _record(
    app: FastAPI,
    *,
    class_gates: str = "enforce",
    worker: str = "worker-1",
    composed_at: datetime | None = None,
) -> None:
    routes = [
        RouteReach(
            "brave-web-search",
            ReachKind.SEARCH,
            ReachState.ACTIVE,
            classes=C,
            priced=True,
            zone="NON_EU",
            any_class_when_advisory=True,
        ),
        RouteReach(
            "public-web-fetch", ReachKind.FETCH, ReachState.ACTIVE, classes=C, zone="UNKNOWN"
        ),
        RouteReach(
            "common-crawl-athena-index",
            ReachKind.INDEX,
            ReachState.BUILT,
            "common_crawl_off",
            "AIA_DEEP_RESEARCH_COMMON_CRAWL is not true",
        ),
    ]
    with create_session_factory(app.state.engine)() as session:
        record_composition(
            session,
            worker=worker,
            build_sha="abc1234",
            composed_at=composed_at or datetime.now(UTC),
            agent_directed=False,
            class_gates=class_gates,
            routes=routes,
        )
        session.commit()


def test_nothing_recorded_presumes_nothing(as_user: Any) -> None:
    body = as_user("researcher").get(URL).json()
    assert body["recorded"] is False and body["routes"] == []


def test_a_member_reads_the_newest_composition_waiting_first(app: FastAPI, as_user: Any) -> None:
    _record(app)
    body = as_user("researcher").get(URL).json()
    assert body["recorded"] is True and body["worker"] == "worker-1"
    states = [(r["route"], r["state"]) for r in body["routes"]]
    # Brave is priced and this organization has approved nothing: it waits.
    assert states == [
        ("brave-web-search", "waiting"),
        ("public-web-fetch", "active"),
        ("common-crawl-athena-index", "built"),
    ]
    assert body["routes"][0]["reason"] == "settings_unapproved"
    assert body["routes"][0]["missing_settings"] == body["missing_for_live"] != []
    assert body["routes"][1]["classes"] == ["C"]


def test_a_class_b_ask_refuses_every_class_c_route(app: FastAPI, as_user: Any) -> None:
    _record(app)
    body = as_user("researcher").get(URL, params={"data_class": "B"}).json()
    composed = [r for r in body["routes"] if r["classes"]]
    assert composed and {(r["state"], r["reason"]) for r in composed} == {("refused", "class")}
    assert body["data_class"] == "B"
    assert as_user("researcher").get(URL, params={"data_class": "D"}).status_code == 422


def test_a_refused_priced_route_names_no_missing_setting(app: FastAPI, as_user: Any) -> None:
    _record(app)
    body = as_user("researcher").get(URL, params={"data_class": "B"}).json()
    brave = next(r for r in body["routes"] if r["route"] == "brave-web-search")
    # Refused by class: approving the settings would not let it run, so none are named.
    assert (brave["state"], brave["reason"]) == ("refused", "class")
    assert brave["missing_settings"] == []


def test_advisory_gates_lift_only_a_route_that_declares_it(app: FastAPI, as_user: Any) -> None:
    _record(app, class_gates="advisory")
    body = as_user("researcher").get(URL, params={"data_class": "B"}).json()
    routes = {r["route"]: r for r in body["routes"]}
    # Brave declares any_class_when_advisory: it waits on its settings, not its class.
    assert routes["brave-web-search"]["state"] == "waiting"
    assert routes["brave-web-search"]["class_advisory"] is True
    # The fetch declares nothing: residency still refuses it, so Dosah says refused.
    fetch = routes["public-web-fetch"]
    assert (fetch["state"], fetch["reason"]) == ("refused", "class")
    assert "residency" in fetch["detail"]


def test_the_newest_is_the_last_recorded_not_the_latest_clock(app: FastAPI, as_user: Any) -> None:
    _record(
        app, worker="worker-early-clock-ahead", composed_at=datetime.now(UTC) + timedelta(hours=1)
    )
    _record(
        app, worker="worker-late-clock-behind", composed_at=datetime.now(UTC) - timedelta(hours=1)
    )
    body = as_user("researcher").get(URL).json()
    assert body["worker"] == "worker-late-clock-behind"


def test_without_a_session_nothing_is_read(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
