"""The gate confines a fetch to the hosts its caller names, and reads a sitemap as bytes.

Two seams a focused crawl needs (plan chunk 17), both through the same gate as
every other fetch: ``host_allowed`` (nothing is sent to a host outside it, not
even on a redirect hop) and ``fetch_resource`` (a document read for what it
lists: journaled like a page, returned as bytes, never a snapshot, never cached).
No network: the gate runs over a recorded fetcher.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from aia_core.application.web_retrieval import RetrievalGate, RunSnapshotCache, WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.web_retrieval import (
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
PAGE = "<html><head><title>Trh</title></head><body><p>Spotřeba vzrostla.</p></body></html>"
XML = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
SITEMAP_TYPES = frozenset({"application/xml", "text/xml"})


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-recorded",
            provider="recorded",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=f"recorded-{tool.value.split('_')[1]}-v1",
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


def _gate(
    scope: Any, cache: RunSnapshotCache | None = None
) -> tuple[RetrievalGate, InMemoryToolLedger, RecordedFetchTransport]:
    transport = RecordedFetchTransport(
        pages={
            "https://stats.example/a": {"body": PAGE},
            "https://stats.example/away": {
                "status": 302,
                "headers": {"location": "https://other.example/landing"},
            },
            "https://stats.example/moved": {"status": 301, "headers": {"location": "/a"}},
            "https://other.example/landing": {"body": PAGE},
            "https://stats.example/sitemap.xml": {
                "body": XML,
                "headers": {"content-type": "application/xml; charset=utf-8"},
                "request_id": "req-sm",
            },
            "https://stats.example/sitemap.html": {"body": PAGE},
            "https://stats.example/big.xml": {
                "body": XML + " " * 5000,
                "headers": {"content-type": "text/xml"},
            },
        }
    )
    ledger = InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
            fetcher=WebFetcher(
                transport=transport,
                resolver=RecordedResolver(
                    hosts={"stats.example": ["93.184.215.14"], "other.example": ["93.184.215.15"]}
                ),
                adapter_id="recorded-fetch-v1",
                clock=lambda: NOW,
            ),
        ),
        scope=scope,
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
        clock=lambda: NOW,
        cache=cache,
    )
    return gate, ledger, transport


def _stats_only(host: str) -> bool:
    return host == "stats.example"


def test_a_url_outside_the_confinement_is_refused_before_dispatch(scoped: Any) -> None:
    gate, ledger, transport = _gate(scoped.scope())
    outcome = gate.fetch("https://other.example/landing", track_id="T", host_allowed=_stats_only)
    assert outcome.page is None and outcome.reason == "host_out_of_scope"
    assert transport.calls == []
    assert [(e.outcome, e.note) for e in ledger.events()] == [
        (ToolOutcome.REFUSED, "host_out_of_scope")
    ]


def test_a_redirect_off_the_host_is_refused_before_the_hop_is_requested(scoped: Any) -> None:
    gate, ledger, transport = _gate(scoped.scope())
    outcome = gate.fetch("https://stats.example/away", track_id="T", host_allowed=_stats_only)
    assert outcome.page is None and outcome.reason == "redirect_out_of_scope"
    assert transport.calls == ["https://stats.example/away"]  # other.example never asked
    assert [(e.outcome, e.note) for e in ledger.events()] == [
        (ToolOutcome.DISPATCHED, ""),
        (ToolOutcome.FAILED, "redirect_out_of_scope"),
    ]
    # A redirect inside the host is followed; unconfined, the off-host one is too.
    inside = gate.fetch("https://stats.example/moved", track_id="T", host_allowed=_stats_only)
    assert inside.page is not None and inside.page.snapshot.final_url == "https://stats.example/a"
    assert gate.fetch("https://stats.example/away", track_id="T").page is not None


def test_a_cached_page_that_ended_off_the_host_is_not_served_to_a_confined_fetch(
    scoped: Any,
) -> None:
    gate, ledger, transport = _gate(scoped.scope(), RunSnapshotCache())
    assert gate.fetch("https://stats.example/away", track_id="T1").page is not None
    sent = list(transport.calls)
    confined = gate.fetch("https://stats.example/away", track_id="T2", host_allowed=_stats_only)
    assert confined.page is None and confined.reason == "redirect_out_of_scope"
    assert not confined.cached and transport.calls == sent
    assert ledger.events()[-1].outcome is ToolOutcome.REFUSED
    # The unconfined caller is still answered from the cache.
    assert gate.fetch("https://stats.example/away", track_id="T3").cached


def test_a_resource_is_journaled_like_a_page_and_returned_as_bytes(scoped: Any) -> None:
    cache = RunSnapshotCache()
    gate, ledger, transport = _gate(scoped.scope(), cache)
    outcome = gate.fetch_resource(
        "https://stats.example/sitemap.xml",
        track_id="T",
        media_types=SITEMAP_TYPES,
        max_bytes=10_000,
        host_allowed=_stats_only,
    )
    assert outcome.resource is not None and outcome.reason is None and not outcome.uncertain
    assert outcome.resource.body == XML.encode()
    assert outcome.resource.media_type == "application/xml"
    assert outcome.resource.final_url == "https://stats.example/sitemap.xml"
    events = ledger.events()
    assert [e.outcome for e in events] == [ToolOutcome.DISPATCHED, ToolOutcome.SUCCEEDED]
    assert events[1].note == "resource application/xml"
    assert events[1].provider_request_id == "req-sm"
    assert events[0].call_id == events[1].call_id and events[0].tool is ToolKind.WEB_FETCH
    # Never a snapshot, never cached: asked again, it is sent again.
    assert len(cache) == 0
    gate.fetch_resource(
        "https://stats.example/sitemap.xml",
        track_id="T",
        media_types=SITEMAP_TYPES,
        max_bytes=10_000,
    )
    assert transport.calls == ["https://stats.example/sitemap.xml"] * 2


def test_a_resource_of_the_wrong_type_or_size_or_place_is_not_kept(scoped: Any) -> None:
    gate, ledger, _ = _gate(scoped.scope())

    def reason(url: str, **options: Any) -> str | None:
        return gate.fetch_resource(
            url, track_id="T", media_types=SITEMAP_TYPES, max_bytes=1000, **options
        ).reason

    assert reason("https://stats.example/sitemap.html") == "content_type"
    assert reason("https://stats.example/big.xml") == "body_too_large"
    assert reason("https://stats.example/none.xml") == "http_404"
    assert reason("https://stats.example/away", host_allowed=_stats_only) == (
        "redirect_out_of_scope"
    )
    assert reason("https://other.example/s.xml", host_allowed=_stats_only) == "host_out_of_scope"
    assert reason("http://169.254.169.254/latest/") == "address_not_public"
    failed = [e.note for e in ledger.events() if e.outcome is ToolOutcome.FAILED]
    assert failed == ["content_type", "body_too_large", "http_404", "redirect_out_of_scope"]
