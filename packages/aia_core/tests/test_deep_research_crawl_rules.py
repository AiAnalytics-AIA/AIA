"""The focused crawler's rules: one host, one form per page, and no trap without an end."""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research.crawl import (
    CrawlLimits,
    CrawlScope,
    TrapGuard,
    crawl_key,
    crawl_url,
)
from aia_core.domain.deep_research.web import FetchRefused


def test_a_page_has_one_form_whatever_the_link_said() -> None:
    assert crawl_url("HTTPS://Stats.Example") == "https://stats.example/"
    assert (
        crawl_url("https://stats.example/a?utm_source=x&b=2&a=1&fbclid=z#part")
        == "https://stats.example/a?a=1&b=2"
    )
    assert crawl_url("https://stats.example/a?utm_medium=mail") == "https://stats.example/a"
    assert crawl_key(crawl_url("https://www.stats.example/a/")) == crawl_key(
        crawl_url("https://stats.example/a")
    )
    with pytest.raises(FetchRefused):
        crawl_url("https://localhost/a")


def test_the_scope_is_the_host_exactly_unless_subdomains_are_asked_for() -> None:
    exact = CrawlScope.of("Stats.Example.")
    assert exact.host == "stats.example"
    assert exact.refusal("https://stats.example/a") is None
    assert exact.refusal("https://data.stats.example/a") == "off_host"
    assert exact.refusal("https://evilstats.example/a") == "off_host"
    assert exact.refusal("https://example/a") == "url_internal_host"
    assert exact.refusal("http://stats.example/a") == "https_only"
    assert exact.refusal("https://stats.example:8443/a") == "url_port"
    wide = CrawlScope.of("stats.example", include_subdomains=True)
    assert wide.refusal("https://data.stats.example/a") is None
    assert wide.refusal("https://evilstats.example/a") == "off_host"
    assert not wide.allows_host("example")  # never a parent
    for bad in ("", "https://stats.example/", "localhost", "10.0.0.8", "stats.example/a"):
        with pytest.raises(ValueError):
            CrawlScope.of(bad)


def test_limits_refuse_nonsense() -> None:
    for bad in (
        {"max_pages": 0},
        {"max_depth": -1},
        {"max_seconds": 0},
        {"max_seconds": float("inf")},
        {"max_sitemap_pages": -1},
        {"max_query_variants": -1},
        {"prefix_segments": 0},
    ):
        with pytest.raises(ValueError):
            CrawlLimits(**bad)  # type: ignore[arg-type]


def test_an_infinite_calendar_ends_by_its_shape() -> None:
    guard = TrapGuard(CrawlLimits(max_per_shape=5, max_per_prefix=1000))
    admitted = [
        url
        for year in range(2020, 2040)
        for month in range(1, 13)
        if guard.admit(url := f"https://stats.example/kalendar/{year}/{month}") is None
    ]
    assert len(admitted) == 5
    assert guard.refusal("https://stats.example/kalendar/2099/1") == "shape_cap"
    # Another shape on the same host is not affected.
    assert guard.admit("https://stats.example/publikace/inflace") is None


def test_repeated_segments_deep_paths_and_long_urls_are_cut() -> None:
    guard = TrapGuard(CrawlLimits(max_path_segments=6, max_url_chars=120))
    assert guard.admit("https://stats.example/a/b/a/b/a") == "repeated_segment"
    assert guard.admit("https://stats.example/kalendar/next/Next/NEXT") == "repeated_segment"
    assert guard.admit("https://stats.example/2026/10/2026/10/2026") == "repeated_segment"
    assert guard.admit("https://stats.example/a/a") is None  # twice is allowed
    assert guard.admit("https://stats.example/1/2/3/4/5/6/7") == "path_too_deep"
    assert guard.admit("https://stats.example/" + "x" * 120) == "url_too_long"


def test_query_variants_of_one_path_are_capped() -> None:
    guard = TrapGuard(CrawlLimits(max_query_variants=2))
    results = [guard.admit(f"https://stats.example/list?page={n}") for n in range(5)]
    assert results == [None, None, "query_variant_cap", "query_variant_cap", "query_variant_cap"]
    assert guard.admit("https://stats.example/list") is None  # the bare path is not a variant
    none = TrapGuard(CrawlLimits(max_query_variants=0))
    assert none.admit("https://stats.example/list?page=1") == "query_variant_cap"


def test_one_directory_cannot_take_the_whole_budget() -> None:
    guard = TrapGuard(CrawlLimits(max_per_prefix=3, prefix_segments=1))
    results = [guard.admit(f"https://stats.example/zpravy/clanek-{chr(97 + n)}") for n in range(5)]
    assert results.count(None) == 3 and results[-1] == "prefix_cap"
    assert guard.admit("https://stats.example/publikace/a") is None
    # A refusal counts nothing: the same URL is refused again for the same reason.
    assert guard.refusal("https://stats.example/zpravy/x") == "prefix_cap"
