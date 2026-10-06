"""A run fetches a URL once: a second fetch is answered from its snapshot cache, for free.

No network: the gate runs over a recorded fetcher.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.web_retrieval import RetrievalGate, RunSnapshotCache, WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.tooling import (
    TOOL_EVENT_KINDS,
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
    ToolUsageEvent,
    new_tool_call_id,
    new_tool_event_id,
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
    scope: Any, cache: RunSnapshotCache | None
) -> tuple[RetrievalGate, InMemoryToolLedger, RecordedFetchTransport]:
    transport = RecordedFetchTransport(
        pages={
            "https://stats.example/a": {"body": PAGE},
            "https://stats.example/old": {"status": 301, "headers": {"location": "/new"}},
            "https://stats.example/new": {"body": PAGE.replace("Trh", "Nový")},
            # Same text as /a under another title: the same content address.
            "https://other.example/copy": {"body": PAGE.replace("Trh", "Kopie")},
            # Two script-only shells: no text at all, so one content address.
            "https://stats.example/app": {"body": "<html><head><title>App</title></head></html>"},
            "https://other.example/app": {"body": "<html><head><title>Jiná</title></head></html>"},
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


def test_a_cache_hit_sends_nothing_and_is_journaled_at_no_cost(scoped: Any) -> None:
    cache = RunSnapshotCache()
    gate, ledger, transport = _gate(scoped.scope(), cache)
    first = gate.fetch("https://stats.example/a", track_id="T1")
    assert first.page is not None and not first.cached
    # The same page by its canonical form, from another track of the same run.
    again = gate.fetch("https://www.stats.example/a/", track_id="T2")
    assert again.cached and again.reason is None and again.page == first.page
    assert transport.calls == ["https://stats.example/a"]
    events = ledger.events()
    assert [e.outcome for e in events] == [
        ToolOutcome.DISPATCHED,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.CACHED,
    ]
    hit = events[-1]
    assert hit.cost_usd == 0 and hit.reservation_id is None and hit.track_id == "T2"
    assert hit.note == f"run_snapshot_cache {first.page.snapshot.snapshot_id}"
    assert ledger.committed_usd() == 0 and len(cache) == 1


def test_a_redirected_page_is_cached_under_its_final_url_too(scoped: Any) -> None:
    gate, _, transport = _gate(scoped.scope(), RunSnapshotCache())
    gate.fetch("https://stats.example/old", track_id="T")
    assert gate.fetch("https://stats.example/new", track_id="T").cached
    assert gate.fetch("https://stats.example/old", track_id="T").cached
    assert transport.calls == ["https://stats.example/old", "https://stats.example/new"]


@pytest.mark.parametrize(
    ("first_url", "second_url"),
    [
        ("https://stats.example/a", "https://other.example/copy"),
        ("https://stats.example/app", "https://other.example/app"),
    ],
)
def test_a_url_is_only_ever_answered_with_its_own_capture(
    scoped: Any, first_url: str, second_url: str
) -> None:
    # Two URLs whose pages extract to the same text share a snapshot id; the
    # cache must still answer each with the page that URL itself returned.
    gate, _, transport = _gate(scoped.scope(), RunSnapshotCache())
    first = gate.fetch(first_url, track_id="T")
    second = gate.fetch(second_url, track_id="T")
    assert first.page is not None and second.page is not None
    assert first.page.snapshot.snapshot_id == second.page.snapshot.snapshot_id
    again = gate.fetch(second_url, track_id="T")
    assert again.cached and again.page == second.page
    assert again.page.snapshot.final_url == second_url
    assert again.page.snapshot.title == second.page.snapshot.title
    assert gate.fetch(first_url, track_id="T").page == first.page
    assert transport.calls == [first_url, second_url]


def test_failures_are_not_cached_and_refusals_stay_refusals(scoped: Any) -> None:
    gate, ledger, transport = _gate(scoped.scope(), RunSnapshotCache())
    assert gate.fetch("https://stats.example/missing", track_id="T").reason == "http_404"
    assert gate.fetch("https://stats.example/missing", track_id="T").reason == "http_404"
    assert transport.calls == ["https://stats.example/missing"] * 2
    assert gate.fetch("http://10.0.0.8/a", track_id="T").reason == "address_not_public"
    assert ToolOutcome.CACHED not in [e.outcome for e in ledger.events()]


def test_without_a_cache_every_fetch_is_sent_and_runs_do_not_share(scoped: Any) -> None:
    gate, _, transport = _gate(scoped.scope(), None)
    gate.fetch("https://stats.example/a", track_id="T")
    assert not gate.fetch("https://stats.example/a", track_id="T").cached
    assert len(transport.calls) == 2
    one, other = RunSnapshotCache(), RunSnapshotCache()
    first, _, _ = _gate(scoped.scope(), one)
    second, _, second_transport = _gate(scoped.scope(), other)
    first.fetch("https://stats.example/a", track_id="T")
    assert not second.fetch("https://stats.example/a", track_id="T").cached
    assert second_transport.calls == ["https://stats.example/a"]


def _event(outcome: ToolOutcome, **fields: Any) -> ToolUsageEvent:
    return ToolUsageEvent(
        event_id=new_tool_event_id(),
        call_id=new_tool_call_id(),
        tool=ToolKind.WEB_FETCH,
        outcome=outcome,
        route_id="r",
        retrieval_mode=RetrievalMode.RECORDED,
        data_class=DataClass.CLASS_C_INTERNAL,
        track_id="T",
        reservation_id=fields.pop("reservation_id", None),
        request_fingerprint="0" * 64,
        provider_request_id=None,
        credits=0,
        cost_usd=fields.pop("cost_usd", 0.0),
        ceiling_usd=0.0,
        occurred_at=NOW,
    )


def test_a_cached_entry_is_terminal_closes_nothing_and_cannot_charge() -> None:
    ledger = InMemoryToolLedger(budget_usd=1.0)
    ledger.outcome(_event(ToolOutcome.CACHED))
    assert ToolOutcome.CACHED.is_terminal
    assert TOOL_EVENT_KINDS[ToolOutcome.CACHED] == "deep_research_tool_cached"
    with pytest.raises(ValueError):
        ledger.outcome(_event(ToolOutcome.CACHED, cost_usd=0.01))
    with pytest.raises(ValueError):
        ledger.outcome(_event(ToolOutcome.CACHED, reservation_id="TRS-x"))
    assert ledger.committed_usd() == 0
    # A journal holding a cache hit is adopted as history and closes nothing.
    adopted = InMemoryToolLedger(budget_usd=1.0)
    assert adopted.adopt(ledger.events(), closed_at=NOW) == ()
