"""Common Crawl, composed (plan ``deep-research-web-search.md`` chunk 23e).

``AIA_DEEP_RESEARCH_COMMON_CRAWL=true`` builds the Athena URL index and the archive fetcher
beside the search route and the public fetch, from the deployment's keys alone. The index route
is live, outside the EU, Class C only and priced at the workgroup's scan cutoff, billed: what
every query reserves against the study (23c), and a priced route needs its organization's
sign-off (44). The ladder's archive rung is given the crawls. Building it sends nothing; a
missing or invalid key stops the worker naming it.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.residency import DataClass, ResidencyZone
from aia_core.infrastructure.common_crawl import AthenaUrlIndex
from aia_executors.ai_runtime import AIRuntimeConfigError
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

#: Illustrative values for these tests only: the price is the proposed $5 per TB, 10 MB minimum,
#: 1 MB increments; the cutoff 1 GB. Never configuration.
CRAWL = {
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL": "true",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP": "aia-ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_DATABASE": "ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_TABLE": "ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES": "1000000000",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED": "5",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_MIN_BILLED_BYTES": "10485760",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_BILLING_INCREMENT_BYTES": "1048576",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF": "2026-10-09",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS": "CC-MAIN-2026-35,CC-MAIN-2026-30",
}
#: The 10^9-byte cutoff billed in whole MB (954 of them) at $5 per 10^12 bytes.
RESERVATION = 954 * 1_048_576 * 5 / 1e12


def _compose(world: ResearchWorld, **env: str) -> Any:
    return deep_research_runtime(
        ai_settings(world.client_id, approved_for=DEVELOP_ROUTE),
        env=env,
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )


def test_common_crawl_is_a_priced_class_c_route_outside_the_eu_the_ladder_can_ask(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _compose(research, **CRAWL)
    archive = runtime.archive
    assert archive is not None and isinstance(archive.index, AthenaUrlIndex)
    for route in (archive.index_route, archive.archive_route):
        assert route.retrieval_mode is RetrievalMode.LIVE
        assert route.route.zone is ResidencyZone.NON_EU
        assert route.route.approved_for == frozenset({DataClass.CLASS_C_INTERNAL})
    assert archive.index_route.price_usd_per_call == pytest.approx(RESERVATION)
    assert archive.archive_route.price_usd_per_call == 0
    assert archive.scan_cutoff_bytes == 1_000_000_000
    assert runtime.sign_off_routes() == ("common-crawl-athena-index",)
    assert runtime.ladder is not None
    assert runtime.ladder.crawls == ("CC-MAIN-2026-35", "CC-MAIN-2026-30")
    # The archive joins a web track's identity, so a run planned without it reuses nothing.
    identity = runtime.web_identity()
    assert identity is not None and "archive" in identity


def test_with_the_switch_off_nothing_of_common_crawl_is_composed(
    research: ResearchWorld,  # noqa: F811
) -> None:
    off = {k: v for k, v in CRAWL.items() if not k.startswith("AIA_DEEP_RESEARCH_COMMON_CRAWL")}
    runtime = _compose(research, **off)
    assert runtime.archive is None and runtime.ladder.crawls == ()
    assert "archive" not in (runtime.web_identity() or {})


@pytest.mark.parametrize(
    ("change", "names"),
    [
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP": ""}, "COMMON_CRAWL_WORKGROUP is required"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES": "5000"}, "at least 10000000"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES": "1e9"}, "MAX_SCAN_BYTES is a whole"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED": "free"}, "TB_SCANNED is a number"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED": "0"}, "finite, positive"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF": "soon"}, "PRICES_AS_OF is a date"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF": "2999-01-01"}, "in the future"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS": ""}, "COMMON_CRAWL_CRAWLS is required"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS": "latest"}, "is not CC-MAIN-YYYY-WW"),
        (
            {"AIA_DEEP_RESEARCH_COMMON_CRAWL_CRAWLS": "CC-MAIN-2026-35,CC-MAIN-2026-35"},
            "names a crawl twice",
        ),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP": "a b"}, "workgroup name"),
        ({"AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": ""}, "COMMON_CRAWL needs a search route"),
        ({"AIA_DEEP_RESEARCH_COMMON_CRAWL": "maybe"}, "AIA_DEEP_RESEARCH_COMMON_CRAWL"),
    ],
)
def test_a_common_crawl_route_that_cannot_be_composed_stops_the_worker_naming_its_key(
    research: ResearchWorld,  # noqa: F811
    change: dict[str, str],
    names: str,
) -> None:
    with pytest.raises((AIRuntimeConfigError, ValueError), match=names):
        _compose(research, **{**CRAWL, **change})


def test_the_switch_is_refused_without_deep_research(research: ResearchWorld) -> None:  # noqa: F811
    """Off, Deep Research has no search route for the archive to answer beside."""
    with pytest.raises(AIRuntimeConfigError, match="COMMON_CRAWL needs a search route"):
        _compose(research, AIA_DEEP_RESEARCH_COMMON_CRAWL="true")
