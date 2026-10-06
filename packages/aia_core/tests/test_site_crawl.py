"""A focused crawl of one host: sitemaps first, then breadth-first, every request through the gate.

The site is fictional (``stats.example``) and nothing touches a network: the
real ``PublicHttpsTransport`` (robots.txt, pacing) runs over a scripted wire, a
scripted resolver and a fake clock, under the real ``WebFetcher`` and
``RetrievalGate`` with a run cache and an in-memory ledger.
"""

from __future__ import annotations

import gzip
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import pytest

from aia_core.application.site_crawl import (
    CrawlCandidate,
    CrawlOrigin,
    SiteCrawl,
    StopReason,
)
from aia_core.application.web_retrieval import RetrievalGate, RunSnapshotCache, WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.crawl import CrawlLimits
from aia_core.domain.deep_research.sitemaps import MAX_SITEMAP_BYTES
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.web_retrieval import FetchedResponse, WebFetcher
from aia_core.infrastructure.web_retrieval_live import PublicHttpsTransport

HOST = "stats.example"
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
HTML = {"content-type": "text/html; charset=utf-8"}
XML = {"content-type": "application/xml"}
ROBOTS = (
    "User-agent: *\nDisallow: /interni/\n"
    "Sitemap: https://stats.example/sitemap-index.xml\n"
    "Sitemap: https://other.example/sitemap.xml\n"
)


# --------------------------------------------------------------------------- the site


def _page(title: str, *links: tuple[str, str]) -> FetchedResponse:
    anchors = "".join(f'<a href="{href}">{text}</a> ' for href, text in links)
    body = f"<html><head><title>{title}</title></head><body><p>{title} text.</p>{anchors}</body>"
    return FetchedResponse(status=200, headers=HTML, body=body.encode(), truncated=False)


def _doc(body: bytes | str, headers: Mapping[str, str] = XML) -> FetchedResponse:
    raw = body.encode() if isinstance(body, str) else body
    return FetchedResponse(status=200, headers=dict(headers), body=raw, truncated=False)


def _urlset(*entries: tuple[str, str | None]) -> str:
    body = "".join(
        f"<url><loc>{loc}</loc>" + (f"<lastmod>{mod}</lastmod>" if mod else "") + "</url>"
        for loc, mod in entries
    )
    return f'<?xml version="1.0"?><urlset {NS}>{body}</urlset>'


def _index(*locs: str) -> str:
    body = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f"<sitemapindex {NS}>{body}</sitemapindex>"


_CALENDAR = re.compile(r"^/kalendar/(\d+)/(\d+)$")


def _calendar(target: str) -> FetchedResponse | None:
    """An infinite calendar: every month links to the next one, forever."""
    match = _CALENDAR.match(target)
    if match is None:
        return None
    year, month = int(match[1]), int(match[2])
    following = (year + month // 12, month % 12 + 1)
    return _page(f"Kalendář {year}/{month}", (f"/kalendar/{following[0]}/{following[1]}", "další"))


def _site() -> dict[tuple[str, str], FetchedResponse]:
    return {
        (HOST, "/robots.txt"): _doc(ROBOTS, {"content-type": "text/plain"}),
        (HOST, "/sitemap-index.xml"): _doc(
            _index(
                "https://stats.example/sitemaps/publikace.xml",
                "https://stats.example/sitemaps/zpravy.xml.gz",
                "https://other.example/sitemaps/cizi.xml",
            )
        ),
        (HOST, "/sitemaps/publikace.xml"): _doc(
            _urlset(
                ("https://stats.example/publikace/mzdy-2019", "2019-03-01"),
                ("https://stats.example/publikace/inflace-2026", "2026-09-30"),
                ("https://stats.example/publikace/bez-data", None),
                ("https://stats.example/interni/tajne", "2026-10-01"),
                ("https://other.example/publikace/x", "2026-10-01"),
            )
        ),
        (HOST, "/sitemaps/zpravy.xml.gz"): _doc(
            gzip.compress(_urlset(("https://stats.example/zpravy/a", "2026-05-05")).encode()),
            {"content-type": "application/x-gzip"},
        ),
        (HOST, "/"): _page(
            "Úvod",
            ("/publikace/inflace-2026", "Inflace"),
            ("/o-nas", "O nás"),
            ("/kalendar/2026/10", "Kalendář"),
            ("/odkaz-ven", "Partner"),
            ("https://other.example/", "Jinde"),
            ("/interni/x", "Interní"),
            ("/seznam?b=1&a=2", "Seznam"),
            ("/seznam?a=2&b=1&utm_source=web", "Seznam znovu"),
        ),
        (HOST, "/o-nas"): _page("O nás", ("/", "Domů"), ("/o-nas/tym", "Tým")),
        (HOST, "/o-nas/tym"): _page("Tým"),
        (HOST, "/odkaz-ven"): FetchedResponse(
            status=302,
            headers={"Location": "https://other.example/landing"},
            body=b"",
            truncated=False,
        ),
        (HOST, "/seznam?a=2&b=1"): _page("Seznam"),
        (HOST, "/publikace/inflace-2026"): _page("Inflace 2026", ("/", "Domů")),
        (HOST, "/publikace/mzdy-2019"): _page("Mzdy 2019"),
        (HOST, "/publikace/bez-data"): _page("Bez data"),
        (HOST, "/zpravy/a"): _page("Zpráva A"),
    }


@dataclass
class Clock:
    now: float = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@dataclass
class Wire:
    clock: Clock
    answers: dict[tuple[str, str], FetchedResponse]
    dynamic: Callable[[str], FetchedResponse | None] = _calendar
    sent: list[tuple[float, str, str]] = field(default_factory=list)

    def get(
        self, *, address: str, host: str, target: str, headers: Mapping[str, str], max_bytes: int
    ) -> FetchedResponse:
        self.sent.append((self.clock.now, host, target))
        answer = self.answers.get((host, target))
        if answer is None and host == HOST:
            answer = self.dynamic(target)
        return answer or FetchedResponse(status=404, headers={}, body=b"", truncated=False)

    def targets(self) -> list[str]:
        return [f"{host}{target}" for _, host, target in self.sent]


@dataclass
class Resolver:
    def resolve(self, host: str) -> tuple[str, ...]:
        return {
            "stats.example": ("93.184.215.14",),
            "data.stats.example": ("93.184.215.16",),
            "other.example": ("93.184.215.15",),
        }.get(host, ())


def _route(tool: ToolKind, price: float = 0.0) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-live",
            provider="public",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id="live-search-v1" if tool is ToolKind.WEB_SEARCH else "public-https-1",
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=price,
    )


@dataclass
class _LiveSearch:
    adapter_id: str = "live-search-v1"
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> Any:
        raise AssertionError("a crawl never searches")


class _ChargingLedger(InMemoryToolLedger):
    @property
    def charges_study_budget(self) -> bool:
        return True


@dataclass
class World:
    gate: RetrievalGate
    ledger: InMemoryToolLedger
    wire: Wire
    clock: Clock
    cache: RunSnapshotCache

    def crawl(self, **options: Any) -> SiteCrawl:
        return SiteCrawl(gate=self.gate, host=HOST, monotonic=self.clock.monotonic, **options)

    def requests(self) -> list[str]:
        """Every request but robots.txt (which the transport reads inside a journaled fetch)."""
        return [t for t in self.wire.targets() if not t.endswith("/robots.txt")]


def _world(
    scoped: Any,
    answers: dict[tuple[str, str], FetchedResponse] | None = None,
    *,
    ledger: InMemoryToolLedger | None = None,
    price: float = 0.0,
) -> World:
    clock = Clock()
    wire = Wire(clock, _site() if answers is None else answers)
    resolver = Resolver()
    transport = PublicHttpsTransport(
        contact="research-desk@aia.example",
        resolver=resolver,
        wire=wire,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    ledger = ledger or InMemoryToolLedger(budget_usd=1.0)
    cache = RunSnapshotCache()
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH, price),
            search=_LiveSearch(),
            fetcher=WebFetcher(
                transport=transport,
                resolver=resolver,
                adapter_id="public-https-1",
                clock=lambda: NOW,
            ),
        ),
        scope=scoped.scope(),
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
        cache=cache,
    )
    return World(gate, ledger, wire, clock, cache)


# --------------------------------------------------------------------------- tests


def test_sitemaps_first_most_recent_page_first_and_nothing_off_the_host(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=0)).run(track_id="T", seeds=())
    assert world.requests() == [
        "stats.example/sitemap.xml",  # 404: robots.txt was read on the way
        "stats.example/sitemap-index.xml",
        "stats.example/sitemaps/publikace.xml",
        "stats.example/sitemaps/zpravy.xml.gz",
        "stats.example/publikace/inflace-2026",  # 2026-09-30
        "stats.example/zpravy/a",  # 2026-05-05
        "stats.example/publikace/mzdy-2019",
        "stats.example/publikace/bez-data",  # no date: last, never guessed recent
        "stats.example/",  # then the root, breadth-first (depth 0 only here)
    ]
    assert {host for _, host, _ in world.wire.sent} == {HOST}
    report = result.report
    assert report.stopped is StopReason.COMPLETE
    assert report.sitemaps_fetched == 3 and report.sitemap_entries == 9
    assert report.errors["http_404"] == 1  # /sitemap.xml
    assert report.skipped["off_host"] == 3  # robots' foreign sitemap, the index's, one entry
    assert report.refused_by_robots == 1  # /interni/tajne: refused before dispatch
    assert [p.origin for p in result.pages] == [CrawlOrigin.SITEMAP] * 4 + [CrawlOrigin.SEED]
    assert result.snapshot_ids == tuple(s.snapshot_id for s in result.snapshots)
    assert len(set(result.snapshot_ids)) == 5
    as_dict = report.as_dict()
    assert as_dict["pages_fetched"] == 5 and as_dict["host"] == HOST


def test_every_request_is_journaled_through_the_gate_and_paced(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=2)).run(track_id="T-crawl", seeds=())
    events = world.ledger.events()
    dispatched = [e for e in events if e.outcome is ToolOutcome.DISPATCHED]
    # One journaled dispatch for every request but robots.txt, made inside one of them.
    assert len(dispatched) == len(world.requests())
    closed = {e.call_id for e in events if e.outcome.is_terminal}
    assert {e.call_id for e in dispatched} <= closed
    assert {e.track_id for e in events} == {"T-crawl"}
    assert all(e.tool is ToolKind.WEB_FETCH for e in events)
    # One request at a time to the host, at least the minimum interval apart.
    times = [at for at, _, _ in world.wire.sent]
    assert all(b - a >= 1.0 for a, b in pairwise(times))
    assert result.report.pages_fetched == len(result.pages)


def test_breadth_first_keeps_to_the_host_robots_and_one_form_per_page(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=2, max_per_shape=3)).run(
        track_id="T", use_sitemaps=False
    )
    requests = world.requests()
    assert requests[:1] == ["stats.example/"]
    assert "stats.example/interni/x" not in requests  # robots.txt: refused before dispatch
    assert requests.count("stats.example/seznam?a=2&b=1") == 1  # three spellings, one page
    assert "stats.example/odkaz-ven" in requests
    assert {host for _, host, _ in world.wire.sent} == {HOST}  # the redirect was not followed
    report = result.report
    assert report.refused_by_robots == 1
    assert report.errors["redirect_out_of_scope"] == 1
    assert report.skipped["off_host"] >= 1
    assert report.skipped["duplicate"] >= 2
    depths = {p.url: p.depth for p in result.pages}
    assert depths["https://stats.example/"] == 0
    assert depths["https://stats.example/o-nas"] == 1
    assert depths["https://stats.example/o-nas/tym"] == 2


def test_an_infinite_calendar_ends_however_deep_the_crawl_may_go(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=500, max_per_shape=4)).run(
        track_id="T", use_sitemaps=False
    )
    calendar = [t for t in world.requests() if "/kalendar/" in t]
    assert len(calendar) == 4
    assert result.report.skipped["shape_cap"] == 1
    assert result.report.stopped is StopReason.COMPLETE


def test_a_hostile_sitemap_is_refused_and_the_crawl_goes_on(scoped: Any) -> None:
    site = _site()
    site[(HOST, "/sitemap-index.xml")] = _doc(
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]>'
        f"<urlset {NS}><url><loc>https://stats.example/&lol2;</loc></url></urlset>"
    )
    site[(HOST, "/sitemap.xml")] = _doc(
        gzip.compress(b" " * (MAX_SITEMAP_BYTES + 1), compresslevel=9),
        {"content-type": "application/gzip"},
    )
    world = _world(scoped, site)
    result = world.crawl(limits=CrawlLimits(max_depth=0)).run(track_id="T")
    assert result.report.errors["sitemap_dtd"] == 1
    assert result.report.errors["sitemap_too_large"] == 1
    assert result.report.sitemap_entries == 0
    assert world.requests() == [
        "stats.example/sitemap.xml",
        "stats.example/sitemap-index.xml",
        "stats.example/",
    ]


def test_a_nested_index_is_not_read_and_the_sitemap_count_is_capped(scoped: Any) -> None:
    site = _site()
    site[(HOST, "/sitemaps/publikace.xml")] = _doc(_index("https://stats.example/hloubeji.xml"))
    world = _world(scoped, site)
    result = world.crawl(limits=CrawlLimits(max_depth=0)).run(track_id="T")
    assert result.report.skipped["sitemap_nesting"] == 1
    assert "stats.example/hloubeji.xml" not in world.requests()
    capped = _world(scoped)
    report = capped.crawl(limits=CrawlLimits(max_depth=0, max_sitemaps=2)).run(track_id="T").report
    assert report.skipped["sitemap_cap"] == 2  # the two sitemaps the index named
    assert "stats.example/sitemaps/publikace.xml" not in capped.requests()


def test_the_page_cap_and_the_sitemap_share(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_pages=2)).run(track_id="T")
    assert len(result.pages) == 2 and result.report.stopped is StopReason.PAGE_CAP
    assert [p.url for p in result.pages] == [
        "https://stats.example/publikace/inflace-2026",
        "https://stats.example/zpravy/a",
    ]
    shared = _world(scoped)
    result = shared.crawl(limits=CrawlLimits(max_pages=3, max_sitemap_pages=1)).run(track_id="T")
    assert [p.origin for p in result.pages] == [
        CrawlOrigin.SITEMAP,
        CrawlOrigin.SEED,
        CrawlOrigin.LINK,
    ]
    assert result.report.skipped["sitemap_page_share"] == 3


def test_sitemap_entries_kept_for_ranking_are_capped(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=0, max_sitemap_entries=2)).run(track_id="T")
    # publikace.xml is read first: its first two same-host entries are all that is kept.
    assert result.report.skipped["sitemap_entry_cap"] == 3
    assert [p.url for p in result.pages if p.origin is CrawlOrigin.SITEMAP] == [
        "https://stats.example/publikace/inflace-2026",
        "https://stats.example/publikace/mzdy-2019",
    ]
    assert "stats.example/zpravy/a" not in world.requests()


def test_subdomains_only_when_asked(scoped: Any) -> None:
    site = _site()
    site[(HOST, "/")] = _page("Úvod", ("https://data.stats.example/tabulka", "Data"))
    exact = _world(scoped, site)
    exact.crawl(limits=CrawlLimits(max_depth=1)).run(track_id="T", use_sitemaps=False)
    assert {host for _, host, _ in exact.wire.sent} == {HOST}
    wide = _world(scoped, site)
    result = wide.crawl(limits=CrawlLimits(max_depth=1, include_subdomains=True)).run(
        track_id="T", use_sitemaps=False
    )
    assert wide.requests() == ["stats.example/", "data.stats.example/tabulka"]
    assert "data.stats.example/robots.txt" in wide.wire.targets()  # its own robots.txt
    assert result.report.errors["http_404"] == 1  # the fictional subdomain has no page


def test_the_depth_cap(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_depth=1)).run(track_id="T", use_sitemaps=False)
    assert max(p.depth for p in result.pages) == 1
    assert "stats.example/o-nas/tym" not in world.requests()


def test_the_time_cap_counts_the_pacing(scoped: Any) -> None:
    world = _world(scoped)
    result = world.crawl(limits=CrawlLimits(max_seconds=2.5)).run(track_id="T")
    assert result.report.stopped is StopReason.TIME_CAP
    # One second between requests: robots.txt and three more fit, the fifth never starts.
    assert len(world.wire.sent) == 4
    assert result.report.elapsed_s >= 3.0


def test_a_url_the_run_already_captured_costs_nothing(scoped: Any) -> None:
    world = _world(scoped)
    earlier = world.gate.fetch("https://stats.example/o-nas", track_id="T-search")
    assert earlier.page is not None
    before = len(world.wire.sent)
    result = world.crawl(limits=CrawlLimits(max_depth=1)).run(track_id="T", use_sitemaps=False)
    assert world.requests().count("stats.example/o-nas") == 1  # the earlier fetch only
    assert len(world.wire.sent) > before
    cached = [p for p in result.pages if p.cached]
    assert [p.url for p in cached] == ["https://stats.example/o-nas"]
    assert result.report.pages_cached == 1
    hit = [e for e in world.ledger.events() if e.outcome is ToolOutcome.CACHED]
    assert len(hit) == 1 and hit[0].track_id == "T" and hit[0].cost_usd == 0


def test_the_relevance_hook_orders_and_filters_what_is_requested(scoped: Any) -> None:
    world = _world(scoped)
    seen: list[CrawlCandidate] = []

    def relevance(candidate: CrawlCandidate) -> float | None:
        seen.append(candidate)
        if "nás" in candidate.anchor_text or "mzdy" in candidate.url:
            return None
        return 2.0 if "seznam" in candidate.url else 1.0

    result = world.crawl(limits=CrawlLimits(max_depth=1), relevance=relevance).run(track_id="T")
    requests = world.requests()
    assert "stats.example/o-nas" not in requests
    assert "stats.example/publikace/mzdy-2019" not in requests
    level_one = [t for t in requests if t.startswith("stats.example/seznam")] + [
        t for t in requests if t.startswith("stats.example/kalendar")
    ]
    assert requests.index(level_one[0]) < requests.index(level_one[-1])
    assert result.report.skipped["irrelevant"] >= 2
    links = [c for c in seen if c.origin is CrawlOrigin.LINK]
    assert links and all(c.referrer == "https://stats.example/" for c in links)
    assert any(c.anchor_text == "Kalendář" for c in links)


def test_the_tool_budget_ends_the_crawl_with_what_it_has(scoped: Any) -> None:
    world = _world(scoped, ledger=_ChargingLedger(budget_usd=0.0025), price=0.001)
    result = world.crawl().run(track_id="T")
    assert result.report.stopped is StopReason.TOOL_BUDGET
    assert len(world.requests()) == 2
    assert world.ledger.committed_usd() == pytest.approx(0.002)


def test_a_crawl_runs_once_and_names_one_host(scoped: Any) -> None:
    world = _world(scoped)
    crawl = world.crawl(limits=CrawlLimits(max_pages=1))
    crawl.run(track_id="T")
    with pytest.raises(RuntimeError):
        crawl.run(track_id="T")
    for bad in ("https://stats.example/", "localhost", "10.0.0.8"):
        with pytest.raises(ValueError):
            SiteCrawl(gate=world.gate, host=bad)
