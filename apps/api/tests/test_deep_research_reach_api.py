"""Settings → Deep Research → Dosah over HTTP (deep-research-web-search 52, SB6)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aia_core.domain.deep_research_reach import ReachKind, ReachState, RouteReach
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.deep_research_composition_repository import record_composition
from fastapi import FastAPI
from fastapi.testclient import TestClient

URL = "/api/v1/settings/deep-research/reach"
C = (DataClass.CLASS_C_INTERNAL,)


def _record(app: FastAPI, *, class_gates: str = "enforce") -> None:
    routes = [
        RouteReach(
            "brave-web-search",
            ReachKind.SEARCH,
            ReachState.ACTIVE,
            classes=C,
            priced=True,
            zone="NON_EU",
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
            worker="worker-1",
            build_sha="abc1234",
            composed_at=datetime.now(UTC),
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


def test_advisory_gates_say_so_and_do_not_refuse(app: FastAPI, as_user: Any) -> None:
    _record(app, class_gates="advisory")
    body = as_user("researcher").get(URL, params={"data_class": "B"}).json()
    fetch = next(r for r in body["routes"] if r["route"] == "public-web-fetch")
    assert fetch["state"] == "active" and fetch["class_advisory"] is True


def test_without_a_session_nothing_is_read(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
