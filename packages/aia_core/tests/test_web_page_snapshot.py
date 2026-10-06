"""Every captured page, live or archived, becomes a snapshot through one path.

An archived capture is stamped on its snapshot and gives it an id of its own; a
live snapshot serialises exactly as it did before the field existed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.application.web_retrieval import RetrievalGate, WebRetrieval
from aia_core.domain.deep_research.contracts import (
    ArchivedCapture,
    RetrievalMode,
    SourceSnapshot,
)
from aia_core.domain.deep_research.tooling import (
    InMemoryToolLedger,
    ToolKind,
    ToolOutcome,
    ToolRoute,
)
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.web_retrieval import (
    RecordedFetchTransport,
    RecordedResolver,
    RecordedSearch,
    WebFetcher,
    page_snapshot,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
BODY = (
    "<html><head><title>Zpráva</title></head><body>"
    "<p>Fiktivní spotřeba vzrostla o 4 %.</p><a href='/dalsi'>Další</a></body></html>"
).encode()
CAPTURE = ArchivedCapture(
    archive="common_crawl",
    crawl="CC-MAIN-2024-10",
    captured_at=datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC),
    target_uri="https://stats.example/zprava",
    warc_filename="crawl-data/CC-MAIN-2024-10/segments/1/warc/a.warc.gz",
    warc_record_offset=100,
    warc_record_length=2000,
    warc_record_id="<urn:uuid:00000000-0000-4000-8000-000000000001>",
)


def _snapshot(archive: ArchivedCapture | None = None) -> SourceSnapshot:
    return page_snapshot(
        url="https://stats.example/zprava",
        final_url="https://stats.example/zprava",
        redirects=(),
        http_status=200,
        content_type="text/html; charset=utf-8",
        body=BODY,
        request_id=None,
        adapter_id="test-v1",
        retrieval_mode=RetrievalMode.RECORDED,
        retrieved_at=NOW,
        archive=archive,
    ).snapshot


def test_a_live_snapshot_has_no_archive_key_and_its_id_is_its_text() -> None:
    live = _snapshot()
    assert live.archive is None
    assert "archive" not in live.model_dump(mode="json")
    assert live.snapshot_id == "SNP-" + live.text_sha256[:24]
    assert live.title == "Zpráva" and "4 %" in live.text
    assert [link.url for link in live.links] == ["https://stats.example/dalsi"]


def test_an_archived_snapshot_says_so_and_is_never_the_live_one() -> None:
    live, archived = _snapshot(), _snapshot(CAPTURE)
    assert archived.text == live.text and archived.text_sha256 == live.text_sha256
    assert archived.snapshot_id != live.snapshot_id
    assert archived.archive == CAPTURE
    dumped = archived.model_dump(mode="json")
    assert dumped["archive"]["crawl"] == "CC-MAIN-2024-10"
    assert SourceSnapshot.model_validate(dumped) == archived
    moved = _snapshot(CAPTURE.model_copy(update={"warc_record_offset": 101}))
    assert moved.snapshot_id != archived.snapshot_id


def test_a_type_no_snapshot_keeps_is_refused() -> None:
    with pytest.raises(FetchRefused) as caught:
        page_snapshot(
            url="https://stats.example/a.pdf",
            final_url="https://stats.example/a.pdf",
            redirects=(),
            http_status=200,
            content_type="application/pdf",
            body=b"%PDF-1.7",
            request_id=None,
            adapter_id="test-v1",
            retrieval_mode=RetrievalMode.RECORDED,
            retrieved_at=NOW,
        )
    assert caught.value.reason == "content_type"


def _recorded_route(tool: ToolKind) -> ToolRoute:
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


def test_a_charset_nobody_can_read_is_refused_and_the_call_is_closed(scoped: Any) -> None:
    """Regression: an unknown charset raised LookupError through the gate, leaving
    the call DISPATCHED with no outcome and ending the step."""
    with pytest.raises(FetchRefused) as caught:
        page_snapshot(
            url="https://stats.example/a",
            final_url="https://stats.example/a",
            redirects=(),
            http_status=200,
            content_type="text/html; charset=x-unknown",
            body=b"<p>x</p>",
            request_id=None,
            adapter_id="test-v1",
            retrieval_mode=RetrievalMode.RECORDED,
            retrieved_at=NOW,
        )
    assert caught.value.reason == "charset_unknown"

    ledger = InMemoryToolLedger(budget_usd=1.0)
    gate = RetrievalGate(
        retrieval=WebRetrieval(
            search_route=_recorded_route(ToolKind.WEB_SEARCH),
            fetch_route=_recorded_route(ToolKind.WEB_FETCH),
            search=RecordedSearch(adapter_id="recorded-search-v1", exchanges={}),
            fetcher=WebFetcher(
                transport=RecordedFetchTransport(
                    pages={
                        "https://stats.example/a": {
                            "body": "<p>x</p>",
                            "headers": {"content-type": "text/html; charset=x-unknown"},
                        }
                    }
                ),
                resolver=RecordedResolver(hosts={"stats.example": ["93.184.215.14"]}),
                adapter_id="recorded-fetch-v1",
            ),
        ),
        scope=scoped.scope(),
        meter=ledger,
        client_terms=(),
        class_a_texts=(),
    )
    outcome = gate.fetch("https://stats.example/a", track_id="T")
    assert outcome.page is None and outcome.reason == "charset_unknown"
    assert [e.outcome for e in ledger.events()] == [ToolOutcome.DISPATCHED, ToolOutcome.FAILED]
