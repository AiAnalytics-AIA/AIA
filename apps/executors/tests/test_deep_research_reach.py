"""Deep Research's reach, read from the composition itself (deep-research-web-search 52).

A composition without Brave shows Brave ``built``, not ``active``; a Class B ask shows every
Class C route ``refused: class``; a priced route waits for the organization's settings; the
worker's record is kept and read back, and a worker that cannot write it still starts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aia_core.domain.deep_research_reach import ReachState, for_organization
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.deep_research_composition_repository import (
    DeepResearchCompositions,
    record_composition,
)
from aia_executors.deep_research_reach import reach_of, record_reach
from aia_executors.deep_research_runtime import deep_research_runtime
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ANSWERS,
    DEVELOP_ROUTE,
    RecordedAgents,
    ResearchWorld,
    Signer,
    ai_settings,
    research,  # noqa: F401  (a fixture)
)

WIKIPEDIA = {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_WEB_SEARCH": "wikipedia"}
BRAVE = {
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "fictional-brave-key-0000",
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-09",
    "AIA_DEEP_RESEARCH_CONNECTORS": "datastat,wayback,crossref,openalex",
}


def _reach(world: ResearchWorld, env: dict[str, str]) -> dict[str, Any]:
    runtime = deep_research_runtime(
        ai_settings(world.client_id, approved_for=DEVELOP_ROUTE),
        env=env,
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )
    return {r.route: r for r in reach_of(runtime, env)}


def test_a_composition_without_brave_shows_it_built_not_active(
    research: ResearchWorld,  # noqa: F811
) -> None:
    routes = _reach(research, WIKIPEDIA)
    assert routes["wikipedia-public-web_search"].state is ReachState.ACTIVE
    brave = routes["brave-web-search"]
    assert (brave.state, brave.reason) == (ReachState.BUILT, "search_route_other")
    assert "AIA_DEEP_RESEARCH_WEB_SEARCH=wikipedia" in (brave.detail or "")
    assert routes["connector-datastat"].reason == "connector_not_listed"
    assert routes["connector-procurement"].state is ReachState.REFUSED
    assert routes["common-crawl-athena-index"].reason == "common_crawl_off"


def test_with_brave_and_connectors_composed_each_says_what_it_is(
    research: ResearchWorld,  # noqa: F811
) -> None:
    routes = _reach(research, BRAVE)
    brave = routes["brave-web-search"]
    assert brave.state is ReachState.ACTIVE and brave.priced and brave.zone == "NON_EU"
    assert brave.classes == (DataClass.CLASS_C_INTERNAL,)
    assert routes["public-web-fetch"].state is ReachState.ACTIVE
    # Composed, but only the agent-directed ladder asks a connector, and it is off.
    datastat = routes["connector-datastat"]
    assert (datastat.state, datastat.reason) == (ReachState.BUILT, "agent_directed_off")
    assert routes["connector-wayback"].reason == "agent_directed_off"
    assert routes["wikipedia-public-web_search"].state is ReachState.BUILT


def test_for_an_organization_a_priced_route_waits_and_a_class_b_ask_is_refused(
    research: ResearchWorld,  # noqa: F811
) -> None:
    routes = list(_reach(research, BRAVE).values())
    waiting = for_organization(routes, missing_for_live=["prices.brave"])
    assert waiting[0].route == "brave-web-search" and waiting[0].state is ReachState.WAITING
    assert waiting[0].missing_settings == ("prices.brave",)
    asked_b = {
        r.route: r
        for r in for_organization(
            routes, missing_for_live=[], data_class=DataClass.CLASS_B_DERIVED_CLIENT
        )
    }
    composed_c = [r for r in routes if DataClass.CLASS_C_INTERNAL in r.classes]
    assert composed_c
    for r in composed_c:
        if r.state is ReachState.ACTIVE:
            assert (asked_b[r.route].state, asked_b[r.route].reason) == (
                ReachState.REFUSED,
                "class",
            )
    advisory = for_organization(
        routes,
        missing_for_live=[],
        data_class=DataClass.CLASS_B_DERIVED_CLIENT,
        class_gates_advisory=True,
    )
    by_route = {r.route: r for r in advisory}
    brave = by_route["brave-web-search"]
    assert brave.state is ReachState.ACTIVE and brave.class_advisory
    # Every other Class-C-only route is still refused by residency under advisory gates.
    for r in composed_c:
        if r.state is ReachState.ACTIVE and r.route != "brave-web-search":
            assert not r.any_class_when_advisory
            assert (by_route[r.route].state, by_route[r.route].reason) == (
                ReachState.REFUSED,
                "class",
            )
    # A route refused by its class names no setting to approve, even when settings are missing.
    refused = for_organization(
        routes, missing_for_live=["prices.brave"], data_class=DataClass.CLASS_B_DERIVED_CLIENT
    )
    brave_refused = next(r for r in refused if r.route == "brave-web-search")
    assert brave_refused.state is ReachState.REFUSED and brave_refused.missing_settings == ()


def test_off_everything_is_built_and_says_deep_research_is_off() -> None:
    routes = reach_of(None, {})
    assert routes and {r.state for r in routes} <= {ReachState.BUILT, ReachState.REFUSED}
    assert {r.reason for r in routes if r.state is ReachState.BUILT} == {"deep_research_off"}


def test_the_record_is_kept_and_read_back(world: Any) -> None:
    sessions = world.sessions
    routes = reach_of(None, {})
    with sessions() as session:
        record_composition(
            session,
            worker="w1",
            build_sha="abc1234",
            composed_at=datetime.now(UTC),
            agent_directed=False,
            class_gates=None,
            routes=routes,
        )
        session.commit()
    with sessions() as session:
        latest = DeepResearchCompositions(session, world.admin_context(session)).latest()
    assert latest is not None and latest.worker == "w1"
    assert [r.route for r in latest.routes] == [r.route for r in routes]


def test_a_worker_that_cannot_record_still_starts() -> None:
    assert (
        record_reach(None, {"DATABASE_URL": "postgresql+psycopg://nobody@/nowhere?host=/nope"})
        is False
    )
    assert record_reach(None, {}) is False


def test_a_standing_index_is_reached_in_the_planned_mode_too(
    research: ResearchWorld,  # noqa: F811
) -> None:
    """The merge step asks Crossref and OpenAlex for a work's standing whatever the mode
    (deep_research/standing.py): with the ladder off they are still reached, and said so."""
    routes = _reach(research, BRAVE)
    for name in ("connector-crossref", "connector-openalex"):
        assert routes[name].state is ReachState.ACTIVE, routes[name]


def test_nothing_is_recorded_when_the_composition_fails_after_deep_research(
    monkeypatch: Any,
) -> None:
    """A worker that fails to start (here its PDF renderer) records no composition: a crash
    loop would otherwise write one per restart, each claiming routes no worker ran."""
    import pytest
    from aia_executors import registry

    def broken(_env: Any) -> Any:
        raise RuntimeError("AIA_REPORT_PDF_ENABLED needs soffice")

    monkeypatch.setattr(registry, "report_pdf_from_env", broken)
    seen: list[object] = []
    with pytest.raises(RuntimeError):
        registry.compose_registry(on_deep_research=seen.append)
    assert seen == []
    monkeypatch.undo()
    registry.compose_registry(on_deep_research=seen.append)
    assert len(seen) == 1


# ----------------------------------------------------------------- the AI route (LO12b)

AI_ENV = {
    "AIA_ENV": "test",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.test.route-model:1",
    "AIA_AI_POLICY_VERSION": "test-route-reach-v1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_RESEARCH_LEAD_ENABLED": "true",
    "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS": "1500",
    "AIA_AI_RESEARCH_LEAD_RESERVATION_USD": "5",
}


def test_the_ai_route_is_the_one_the_gateway_judges() -> None:
    from aia_core.domain.ai_route_reach import LeadComposition, lead_preflight
    from aia_executors.ai_runtime import AIRuntimeSettings
    from aia_executors.deep_research_reach import ai_route_of

    reach = ai_route_of(AI_ENV)
    settings = AIRuntimeSettings.from_env(AI_ENV)
    assert settings is not None and reach.route == settings.route()
    assert (reach.runtime, reach.region, reach.study_lead) == (
        True,
        "eu-central-1",
        LeadComposition.CONFIGURED,
    )
    # Class C alone and no retention stated: every Lead turn (Class B at least) is refused.
    assert lead_preflight(reach) == "egress_route_not_approved_for_class"
    unconfigured = {k: v for k, v in AI_ENV.items() if not k.startswith("AIA_AI_RESEARCH_LEAD_MAX")}
    assert ai_route_of(unconfigured).study_lead is LeadComposition.UNCONFIGURED
    # Runtime off: no route, and gates the runtime never validated cost the record nothing.
    off = ai_route_of({"AIA_ENV": "staging", "AIA_DATA_CLASS_GATES": "advisory"})
    assert (off.runtime, off.route, off.study_lead) == (False, None, LeadComposition.OFF)


def test_the_ai_route_is_kept_and_read_back(world: Any) -> None:
    from aia_executors.deep_research_reach import ai_route_of

    reach = ai_route_of(AI_ENV)
    with world.sessions() as session:
        record_composition(
            session,
            worker="w1",
            build_sha=None,
            composed_at=datetime.now(UTC),
            agent_directed=False,
            class_gates=None,
            routes=[],
            ai_route=reach,
        )
        session.commit()
    with world.sessions() as session:
        latest = DeepResearchCompositions(session, world.admin_context(session)).latest()
    assert latest is not None and latest.ai_route == reach
