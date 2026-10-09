"""A Deep Research start asks first over HTTP when its ceiling reaches the study's limit.

Plan ``deep-research-web-search.md`` chunk 22, ADR 0019 gate 2, as a research run's start
does it (``test_research_spend_api.py``). The deployment's settings carry the route's prices,
the model's window, the research output limit, the thinking budget and the mode switches the
worker composes from; the server works each kind's reservation and the ceiling out
(``request_limits``, chunk 23), and the request never names it.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ApprovalDecisionRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}

#: The route: $3 / $15 per MTok, a 200,000-token window, 8,192 research output tokens. Each
#: kind reserves two calls at its window and output limit: the planner, the lead and the
#: synthesizer the model's; the investigator 144,000 and 6,144; the verifier 112,000 and 4,096.
ROUTE = {
    "bedrock_input_usd_per_mtok": 3.0,
    "bedrock_output_usd_per_mtok": 15.0,
    "bedrock_context_window_tokens": 200_000,
    "ai_research_max_output_tokens": 8_192,
}
WHOLE = 2 * (200_000 * 3.0 + 8_192 * 15.0) / 1_000_000
INVESTIGATOR = 2 * (144_000 * 3.0 + 6_144 * 15.0) / 1_000_000
VERIFIER = 2 * (112_000 * 3.0 + 4_096 * 15.0) / 1_000_000
#: One web track, EXHAUSTIVE, the planned mode: the planner (1), a request per search (10),
#: the verifier over min(10 x 12, 16 - 1 + 12) = 27 candidates in batches of 12 (3), the
#: synthesizer (1) -- 15 requests. No retrieval route is on.
EXHAUSTIVE_PLANNED = WHOLE + 10 * INVESTIGATOR + 3 * VERIFIER + WHOLE
#: The same under the lead: its plan and 6 re-plans (7), its ceiling's 720 turns, 50 tasks'
#: verification at 3 batches each (150), the brief synthesizer and its one repair (2) --
#: 879 requests.
EXHAUSTIVE_LEAD = 7 * WHOLE + 720 * INVESTIGATOR + 150 * VERIFIER + 2 * WHOLE


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update=ROUTE)


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _url(world: Any) -> str:
    return f"{_study(world)}/deep-research/runs"


def _revision(c: TestClient, world: Any) -> str:
    made = c.post(
        f"{_study(world)}/design/revisions", json={"content": DESIGN, "source_stage": "brief"}
    )
    assert made.status_code == 201, made.text
    return str(made.json()["revision_id"])


def _limit(c: TestClient, world: Any, usd: float | None) -> None:
    assert c.put(f"{_study(world)}/spend-confirm", json={"limit_usd": usd}).status_code == 200


def _start(
    c: TestClient, world: Any, revision: str, preset: str = "EXHAUSTIVE", **body: Any
) -> Any:
    return c.post(
        _url(world),
        json={"design_revision_id": revision, "preset_name": preset, "channels": ["WEB"], **body},
    )


def _spend_rows(app: FastAPI) -> list[Any]:
    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
            ).all()
        )


def test_an_exhaustive_run_over_the_limit_asks_then_starts_on_a_yes_recorded_once(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 5.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409, asked.text
    assert asked.json()["code"] == "cost_confirmation_required"
    assert asked.json()["details"] == {
        "ceiling_usd": pytest.approx(EXHAUSTIVE_PLANNED),
        "limit_usd": 5.0,
    }
    ceiling = asked.json()["details"]["ceiling_usd"]
    assert researcher.get(_url(world)).json() == []
    low = _start(researcher, world, revision, confirm_cost_usd=ceiling - 0.5)
    assert low.status_code == 409

    started = _start(researcher, world, revision, confirm_cost_usd=ceiling)
    assert started.status_code == 201, started.text
    assert started.json()["preset"] == "EXHAUSTIVE"
    [row] = _spend_rows(app)
    assert row.run_id == started.json()["run_id"] and row.decision == "confirm"
    # The same submission again: the run that exists, nothing asked, nothing more recorded.
    again = _start(researcher, world, revision)
    assert again.status_code == 200 and again.json()["run_id"] == started.json()["run_id"]
    assert len(_spend_rows(app)) == 1


def test_under_the_limit_it_does_not_ask(researcher: TestClient, world: Any, app: FastAPI) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, EXHAUSTIVE_PLANNED + 0.5)
    assert _start(researcher, world, revision).status_code == 201
    assert _spend_rows(app) == []


def test_the_ceiling_is_the_mode_the_worker_composes(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(
        update={"deep_research_agent_directed": True, "deep_research_lead": True}
    )
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409
    assert asked.json()["details"]["ceiling_usd"] == pytest.approx(EXHAUSTIVE_LEAD)


def test_each_kind_reserves_its_own_and_the_ceiling_is_below_one_flat_reservation(
    researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 1.0)
    ceiling = _start(researcher, world, revision).json()["details"]["ceiling_usd"]
    # Before chunk 23 every one of the 15 requests reserved the whole window's amount.
    assert ceiling == pytest.approx(EXHAUSTIVE_PLANNED) and ceiling < 15 * WHOLE


def test_thinking_is_priced_into_each_kinds_output(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(
        update={"deep_research_thinking_budget_tokens": 2048}
    )
    revision = _revision(researcher, world)
    _limit(researcher, world, 1.0)
    ceiling = _start(researcher, world, revision).json()["details"]["ceiling_usd"]
    # The investigator's 6,144 + 2,048 and the verifier's 4,096 + 2,048 output tokens.
    thinking_investigator = 2 * (144_000 * 3.0 + 8_192 * 15.0) / 1_000_000
    thinking_verifier = 2 * (112_000 * 3.0 + 6_144 * 15.0) / 1_000_000
    assert ceiling == pytest.approx(2 * WHOLE + 10 * thinking_investigator + 3 * thinking_verifier)


def test_a_retry_asks_again(researcher: TestClient, world: Any, app: FastAPI) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 5.0)
    ceiling = _start(researcher, world, revision).json()["details"]["ceiling_usd"]
    run_id = _start(researcher, world, revision, confirm_cost_usd=ceiling).json()["run_id"]
    assert researcher.post(f"{_url(world)}/{run_id}/cancel").status_code == 200
    asked = researcher.post(f"{_url(world)}/{run_id}/retry")
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    retried = researcher.post(
        f"{_url(world)}/{run_id}/retry",
        json={"confirm_cost_usd": asked.json()["details"]["ceiling_usd"]},
    )
    assert retried.status_code == 201, retried.text
    assert len(_spend_rows(app)) == 2


@pytest.mark.parametrize(
    "unset",
    [
        "bedrock_input_usd_per_mtok",
        "bedrock_output_usd_per_mtok",
        "bedrock_context_window_tokens",
        "ai_research_max_output_tokens",
    ],
)
def test_an_unset_price_or_limit_is_refused_with_a_limit_and_not_without(
    researcher: TestClient, world: Any, app: FastAPI, unset: str
) -> None:
    app.state.settings = app.state.settings.model_copy(update={unset: None})
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    refused = _start(researcher, world, revision)
    assert refused.status_code == 409 and refused.json()["code"] == "cost_ceiling_unknown"
    details = refused.json()["details"]
    assert details["reason"] == "deep_research_price_missing"
    assert details["kinds"] == ["planner", "investigator", "verifier", "synthesizer"]
    _limit(researcher, world, None)
    assert _start(researcher, world, revision).status_code == 201


def test_the_request_cannot_name_the_ceiling(researcher: TestClient, world: Any) -> None:
    revision = _revision(researcher, world)
    named = _start(researcher, world, revision, ceiling_usd=0.01)
    assert named.status_code == 422


def test_listed_connectors_are_stated_free_beside_a_search_route(settings: Settings) -> None:
    """Chunk 23b: the connectors the worker composes cost nothing per call, and say so."""
    from aia_core.domain.deep_research.budgets import CallKind

    from aia_api.routers.deep_research import deep_research_prices

    off = settings.model_copy(update={"deep_research_wikipedia_enabled": True})
    listed = off.model_copy(update={"deep_research_connectors": "datastat,wayback"})
    alone = settings.model_copy(update={"deep_research_connectors": "datastat"})
    assert deep_research_prices(off)[CallKind.CONNECTOR].state == "off"
    assert deep_research_prices(alone)[CallKind.CONNECTOR].state == "off"
    connector = deep_research_prices(listed)[CallKind.CONNECTOR]
    assert (connector.state, connector.usd) == ("priced", 0.0)


def test_an_approved_request_limit_prices_the_ceiling_a_start_is_asked_about(
    researcher: TestClient, owner: TestClient, world: Any
) -> None:
    """Chunk 43c: the ceiling is priced by the request limits the run will pin, as the worker
    will reserve: the verifier's answer limit lowered to 2,048 tokens takes each of its three
    batches' reservation down by two calls' worth of the 2,048 tokens it no longer writes."""
    key = "limits.verifier.answer_tokens"
    made = owner.post(f"{API}/deep-research/settings/{key}/versions", json={"value": 2048})
    assert made.status_code == 201, made.text
    approved = owner.put(
        f"{API}/deep-research/settings/{key}/approval",
        json={"version_number": made.json()["version_number"]},
    )
    assert approved.status_code == 200, approved.text
    revision = _revision(researcher, world)
    _limit(researcher, world, 5.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409, asked.text
    verifier = 2 * (112_000 * 3.0 + 2_048 * 15.0) / 1_000_000
    assert asked.json()["details"]["ceiling_usd"] == pytest.approx(
        EXHAUSTIVE_PLANNED - 3 * VERIFIER + 3 * verifier
    )


def test_a_start_on_a_paid_live_route_is_refused_naming_what_live_still_needs(
    researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chunk 44: no route the API prices today has a price (Wikipedia, the public fetch, the
    connectors are fee-free), so a deployment's paid search is stood in for here."""
    from aia_api.routers import deep_research as router
    from aia_core.domain.deep_research.budgets import CallKind
    from aia_core.domain.deep_research.settings import effective
    from aia_core.domain.run_cost import DeepResearchPrices, RoutePrice

    def paid(settings: Any, session: Any, scope: Any) -> DeepResearchPrices:
        free = router.deep_research_prices(settings)
        return DeepResearchPrices({**free.prices, CallKind.SEARCH: RoutePrice.per_call(0.005)})

    monkeypatch.setattr(router, "_study_prices", paid)
    refused = _start(researcher, world, _revision(researcher, world))
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "live_settings_unapproved"
    assert refused.json()["details"] == {
        "missing": list(effective({}).missing_for_live()),
        "routes": ["search"],
    }
    assert researcher.get(_url(world)).json() == []


def test_brave_search_is_priced_from_its_dated_key_and_unknown_without_it(
    settings: Settings,
) -> None:
    """Chunk 23d: the ceiling prices Brave's search as the worker reserves it, per request;
    a deployment that names Brave without its price has an unknown ceiling, never a free one,
    and its paid route is what a start asks the sign-off for (chunk 44)."""
    from aia_core.domain.deep_research.budgets import CallKind

    from aia_api.routers.deep_research import deep_research_prices

    brave = settings.model_copy(
        update={"deep_research_web_search": "brave", "deep_research_brave_usd_per_1000": 5.0}
    )
    search = deep_research_prices(brave)[CallKind.SEARCH]
    assert (search.state, search.usd) == ("priced", pytest.approx(0.005))
    assert deep_research_prices(brave)[CallKind.FETCH].usd == 0.0
    assert deep_research_prices(brave).paid_routes() == (CallKind.SEARCH,)
    unpriced = brave.model_copy(update={"deep_research_brave_usd_per_1000": None})
    assert deep_research_prices(unpriced)[CallKind.SEARCH].state == "unknown"
    wikipedia = settings.model_copy(update={"deep_research_web_search": "wikipedia"})
    assert deep_research_prices(wikipedia).paid_routes() == ()
    assert deep_research_prices(wikipedia)[CallKind.SEARCH].usd == 0.0
