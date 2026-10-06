"""Every captured page, live or archived, becomes a snapshot through one path.

An archived capture is stamped on its snapshot and gives it an id of its own; a
live snapshot serialises exactly as it did before the field existed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aia_core.domain.deep_research.contracts import (
    ArchivedCapture,
    RetrievalMode,
    SourceSnapshot,
)
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.infrastructure.web_retrieval import page_snapshot

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
