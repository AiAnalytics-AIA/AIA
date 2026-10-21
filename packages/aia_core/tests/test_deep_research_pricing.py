"""The Deep Research prices, from the deployment's keys, in the application layer.

Plan ``deep-research-web-search.md`` chunk 55 (DRL-0, F-DRL-3): what the API router priced
from its own environment copy is now :class:`DeepResearchPricingSettings`, which any
composition root builds. Each case below is a combination of keys a deployment can state;
an unknown price is never zero.
"""

from __future__ import annotations

import pytest

from aia_core.application.deep_research_pricing import DeepResearchPricingSettings
from aia_core.domain.deep_research.budgets import CallKind, ResearchMode
from aia_core.domain.deep_research.request_limits import RESEARCH_KINDS

ROUTE = DeepResearchPricingSettings(
    input_usd_per_mtok=3.0,
    output_usd_per_mtok=15.0,
    context_window_tokens=200_000,
    max_output_tokens=8_192,
)
WHOLE = 2 * (200_000 * 3.0 + 8_192 * 15.0) / 1_000_000
CRAWL = {
    "wikipedia_enabled": True,
    "common_crawl": True,
    "common_crawl_max_scan_bytes": 1_000_000_000,
    "common_crawl_usd_per_tb_scanned": 5.0,
    "common_crawl_min_billed_bytes": 10_485_760,
    "common_crawl_billing_increment_bytes": 1_048_576,
}


def _with(**changes: object) -> DeepResearchPricingSettings:
    from dataclasses import replace

    return replace(ROUTE, **changes)  # type: ignore[arg-type]


def test_off_sends_nothing_and_prices_the_models() -> None:
    prices = ROUTE.prices()
    assert ROUTE.search_route() == "off"
    for kind in (CallKind.SEARCH, CallKind.FETCH, CallKind.CONNECTOR, CallKind.URL_INDEX_QUERY):
        assert prices[kind].state == "off"
    assert prices[CallKind.PLANNER].usd == pytest.approx(WHOLE)
    assert prices.paid_routes() == ()


def test_a_model_key_missing_makes_every_model_kind_unknown() -> None:
    missing = _with(context_window_tokens=None)
    assert missing.budgets() is None
    assert all(missing.prices()[k].state == "unknown" for k in RESEARCH_KINDS)


def test_wikipedia_is_free_and_named_by_either_key() -> None:
    for settings in (_with(wikipedia_enabled=True), _with(web_search="wikipedia")):
        prices = settings.prices()
        assert settings.search_route() == "wikipedia"
        assert (prices[CallKind.SEARCH].usd, prices[CallKind.FETCH].usd) == (0.0, 0.0)
        assert prices.paid_routes() == ()
    # The route by name wins over the old switch.
    assert _with(wikipedia_enabled=True, web_search="off").search_route() == "off"


def test_brave_is_priced_per_request_and_unknown_without_its_price() -> None:
    priced = _with(web_search="brave", brave_usd_per_1000=5.0).prices()
    assert priced[CallKind.SEARCH].usd == pytest.approx(0.005)
    assert priced.paid_routes() == (CallKind.SEARCH,)
    unpriced = _with(web_search="brave").prices()
    assert unpriced[CallKind.SEARCH].state == "unknown"


def test_common_crawl_full_is_priced_at_its_cutoff_and_partial_is_unknown() -> None:
    full = _with(**CRAWL).prices()  # type: ignore[arg-type]
    index = full[CallKind.URL_INDEX_QUERY]
    assert (index.state, index.usd) == ("priced", pytest.approx(954 * 1_048_576 * 5 / 1e12))
    assert full[CallKind.ARCHIVE_FETCH].usd == 0.0
    assert full.paid_routes() == (CallKind.URL_INDEX_QUERY,)
    for missing in (
        {"common_crawl_usd_per_tb_scanned": None},
        {"common_crawl_min_billed_bytes": None},
        {"common_crawl_max_scan_bytes": 5_000},  # below the cutoff the worker accepts
    ):
        partial = _with(**{**CRAWL, **missing}).prices()  # type: ignore[arg-type]
        assert partial[CallKind.URL_INDEX_QUERY].state == "unknown"
    alone = _with(**{**CRAWL, "wikipedia_enabled": False}).prices()  # type: ignore[arg-type]
    assert alone[CallKind.URL_INDEX_QUERY].state == "off"


def test_connectors_are_free_beside_a_search_route_only() -> None:
    assert _with(connectors="datastat").prices()[CallKind.CONNECTOR].state == "off"
    listed = _with(connectors="datastat", wikipedia_enabled=True).prices()[CallKind.CONNECTOR]
    assert (listed.state, listed.usd) == ("priced", 0.0)


def test_the_mode_follows_the_switches() -> None:
    assert ROUTE.mode() is ResearchMode.PLANNED
    assert _with(agent_directed=True).mode() is ResearchMode.AGENT_DIRECTED
    assert _with(agent_directed=True, engine_lead=True).mode() is ResearchMode.LEAD


def test_the_runtime_switch_is_unknown_unless_given() -> None:
    assert DeepResearchPricingSettings().enabled is None
