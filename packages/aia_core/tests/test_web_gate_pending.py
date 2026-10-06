"""Calls begun together: every dispatch journaled before any leaves, outcomes closed after.

The agent-directed investigator sends up to five actions concurrently. The gate splits
each call in three -- begin (classify, authorise, reserve, journal ``DISPATCHED``), send
(the adapter only, any thread), finish (journal the outcome) -- and ``search``/``fetch``
are exactly those three in a row. No network: recorded search and fetch.
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.web_retrieval import (
    FetchOutcome,
    PendingFetch,
    PendingSearch,
    RetrievalGate,
    RunSnapshotCache,
    SearchOutcome,
    WebRetrieval,
    request_fingerprint,
)
from aia_core.domain.deep_research.contracts import ClientTerm, QueryDecision, RetrievalMode
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
    SearchResponse,
    WebFetcher,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
PAGE = "<html><head><title>Trh</title></head><body><p>Spotřeba vzrostla.</p></body></html>"
C = DataClass.CLASS_C_INTERNAL


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-recorded",
            provider="recorded",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({C}),
        ),
        tool=tool,
        adapter_id=f"recorded-{tool.value.split('_')[1]}-v1",
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


class _Journal(InMemoryToolLedger):
    """The ledger, and what had left (by the transports) when each entry was written."""

    def __init__(self, left: list[str]) -> None:
        super().__init__(budget_usd=1.0)
        self._left = left
        self.order: list[tuple[ToolOutcome, int]] = []

    def dispatching(self, event: Any) -> None:
        super().dispatching(event)
        self.order.append((event.outcome, len(self._left)))

    def outcome(self, event: Any) -> None:
        super().outcome(event)
        self.order.append((event.outcome, len(self._left)))


def _gate(
    scope: Any, cache: RunSnapshotCache | None = None
) -> tuple[RetrievalGate, _Journal, list[str]]:
    left: list[str] = []
    lock = threading.Lock()

    class Search(RecordedSearch):
        def search(self, query: str, *, max_results: int) -> SearchResponse:
            with lock:
                left.append(query)
            return RecordedSearch.search(self, query, max_results=max_results)

    class Transport(RecordedFetchTransport):
        def get(self, url: str, *, address: str, max_bytes: int) -> Any:
            with lock:
                left.append(url)
            return RecordedFetchTransport.get(self, url, address=address, max_bytes=max_bytes)

    search = Search(
        adapter_id="recorded-search-v1",
        exchanges={
            "trh nápojů": {"hits": [{"url": "https://stats.example/a", "title": "Trh"}]},
            "plant drinks": {"hits": []},
            "ztracený": {"fail": "uncertain"},
        },
    )
    journal = _Journal(left)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=search,
            fetcher=WebFetcher(
                transport=Transport(pages={"https://stats.example/a": {"body": PAGE}}),
                resolver=RecordedResolver(hosts={"stats.example": ["93.184.215.14"]}),
                adapter_id="recorded-fetch-v1",
                clock=lambda: NOW,
            ),
        ),
        scope=scope,
        meter=journal,
        client_terms=(ClientTerm(term="Acme", source="client.name"),),
        class_a_texts=(),
        clock=lambda: NOW,
        cache=cache,
    )
    return gate, journal, left


def test_every_begun_call_is_journaled_before_any_leaves(scoped: Any) -> None:
    gate, journal, left = _gate(scoped.scope())
    pending = [
        gate.begin_search("trh nápojů", context_class=C, track_id="T", max_results=3, lang="cs"),
        gate.begin_search("plant drinks", context_class=C, track_id="T", max_results=3, lang="en"),
        gate.begin_search("ztracený", context_class=C, track_id="T", max_results=3),
        gate.begin_fetch("https://stats.example/a", track_id="T"),
        gate.begin_fetch("https://stats.example/missing", track_id="T"),
    ]
    assert all(isinstance(p, PendingSearch | PendingFetch) for p in pending)
    assert left == []  # nothing has left; five dispatches are on record
    assert journal.order == [(ToolOutcome.DISPATCHED, 0)] * 5
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda p: p.send(), pending))
    assert len(left) == 5 and journal.order[5:] == []  # sent; no outcome written off-thread
    a, b, lost, page, missing = pending
    assert isinstance(a, PendingSearch) and isinstance(b, PendingSearch)
    assert isinstance(lost, PendingSearch)
    assert isinstance(page, PendingFetch) and isinstance(missing, PendingFetch)
    first, second, third = gate.finish_search(a), gate.finish_search(b), gate.finish_search(lost)
    fetched, failed = gate.finish_fetch(page), gate.finish_fetch(missing)
    assert [o for o, _ in journal.order[5:]] == [
        ToolOutcome.SUCCEEDED,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.UNCERTAIN,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.FAILED,
    ]
    assert len(first.hits) == 1 and second.hits == () and third.uncertain
    assert first.request_fingerprint == request_fingerprint("trh nápojů\n[lang=cs]")
    assert fetched.page is not None and fetched.call_id == page.call_id
    assert failed.reason == "http_404" and failed.data_class is C


def test_a_language_reaches_an_adapter_that_offers_one(scoped: Any) -> None:
    gate, _journal, _left = _gate(scoped.scope())
    gate.search("trh nápojů", context_class=C, track_id="T", max_results=3, lang="en")
    gate.search("plant drinks", context_class=C, track_id="T", max_results=3)
    search = gate._retrieval.search
    assert isinstance(search, RecordedSearch) and search.languages == ["en"]


def test_a_refused_call_begins_as_its_outcome_and_sends_nothing(scoped: Any) -> None:
    gate, journal, left = _gate(scoped.scope())
    refused = gate.begin_search("Acme nápoje", context_class=C, track_id="T", max_results=3)
    assert isinstance(refused, SearchOutcome)
    assert refused.record.decision is QueryDecision.REFUSED and refused.request_fingerprint is None
    private = gate.begin_fetch("http://10.0.0.8/a", track_id="T")
    assert isinstance(private, FetchOutcome) and private.reason == "address_not_public"
    assert left == [] and [o for o, _ in journal.order] == [ToolOutcome.REFUSED] * 2


def test_a_cached_page_begins_as_its_outcome(scoped: Any) -> None:
    gate, _journal, left = _gate(scoped.scope(), RunSnapshotCache())
    gate.fetch("https://stats.example/a", track_id="T")
    again = gate.begin_fetch("https://www.stats.example/a/", track_id="T2")
    assert isinstance(again, FetchOutcome) and again.cached and left == ["https://stats.example/a"]


def test_a_remembered_page_is_a_cache_hit_and_journals_nothing_until_asked(scoped: Any) -> None:
    first, _journal, _left = _gate(scoped.scope(), RunSnapshotCache())
    page = first.fetch("https://stats.example/a", track_id="T").page
    assert page is not None
    gate, journal, left = _gate(scoped.scope(), RunSnapshotCache())
    gate.remember("https://stats.example/a", page)
    assert journal.order == []
    assert gate.fetch("https://stats.example/a", track_id="T").cached and left == []
    uncached, uncached_journal, _ = _gate(scoped.scope(), None)
    uncached.remember("https://stats.example/a", page)  # no cache: nothing held
    assert not uncached.fetch("https://stats.example/a", track_id="T").cached
    assert uncached_journal.order[0][0] is ToolOutcome.DISPATCHED


def test_an_adapter_error_is_raised_where_the_outcome_would_be_journaled(scoped: Any) -> None:
    gate, journal, _left = _gate(scoped.scope())
    pending = gate.begin_search("trh nápojů", context_class=C, track_id="T", max_results=3)
    assert isinstance(pending, PendingSearch)
    pending.error = RuntimeError("bug in an adapter")
    with pytest.raises(RuntimeError, match="bug in an adapter"):
        gate.finish_search(pending)
    # The dispatch stays open: a later attempt closes it uncertain, and never resends it.
    assert [o for o, _ in journal.order] == [ToolOutcome.DISPATCHED]


def test_the_journal_keeps_a_fingerprint_of_what_was_sent(scoped: Any) -> None:
    gate, journal, _left = _gate(scoped.scope())
    gate.search("trh nápojů", context_class=C, track_id="T", max_results=3, lang="cs")
    sent = journal.events()[0].request_fingerprint
    assert sent == hashlib.sha256("trh nápojů\n[lang=cs]".encode()).hexdigest()
    gate.search("plant drinks", context_class=C, track_id="T", max_results=3)
    # Without a language the journal is what it always was: the query's own hash.
    assert journal.events()[2].request_fingerprint == request_fingerprint("plant drinks")
