"""The Wayback CDX index: one URL's captures as a table, and the capture nearest a date.

The fixture is FICTIONAL (an invented page on a reserved ``.example`` host, invented
digests and lengths) in the shape the Internet Archive's CDX server README documents
for ``output=json``: a header row naming the fields, then one row per capture
(``docs/architecture/deep-research-connectors.md``). No network: the transport is a double.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.datasets import DatasetQuery
from aia_core.domain.deep_research.grounding import ground_cell
from aia_core.domain.deep_research.tooling import ToolKind
from aia_core.infrastructure.dataset_connectors import dataset_snapshot
from aia_core.infrastructure.dataset_wayback import (
    WAYBACK_CONNECTOR_ID,
    WAYBACK_LIMIT,
    WaybackCdxConnector,
    nearest_capture,
)
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedFetchTransport,
    RecordedResolver,
    ToolCallFailed,
)

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
PUBLIC = "93.184.215.14"
BODY = (
    Path(__file__).parent / "fixtures" / "dataset_connectors" / "wayback_cdx_fictional.json"
).read_bytes()
PAGE = "https://zpravy.example/fiktivni-zprava-2022"


class _Transport:
    def __init__(self, response: FetchedResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append((url, address))
        return self.response


def _answer(body: bytes = BODY, **over: Any) -> FetchedResponse:
    fields: dict[str, Any] = {
        "status": 200,
        "headers": {"content-type": "text/plain"},
        "body": body,
        "truncated": False,
    }
    fields.update(over)
    return FetchedResponse(**fields)


def _connector(response: FetchedResponse | None = None) -> tuple[WaybackCdxConnector, _Transport]:
    transport = _Transport(response or _answer())
    return (
        WaybackCdxConnector(
            transport=transport,
            resolver=RecordedResolver(hosts={"web.archive.org": [PUBLIC]}),
            clock=lambda: NOW,
        ),
        transport,
    )


def _query(**over: Any) -> DatasetQuery:
    return DatasetQuery.model_validate(
        {"connector_id": WAYBACK_CONNECTOR_ID, "dataset_id": PAGE, **over}
    )


def test_one_get_to_the_index_for_the_exact_url_and_period() -> None:
    connector, transport = _connector()
    response = connector.query(_query(period="2023"))
    [(url, address)] = transport.calls
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path, address) == (
        "https",
        "web.archive.org",
        "/cdx/search/cdx",
        PUBLIC,
    )
    assert parse_qsl(parts.query) == [
        ("url", PAGE),
        ("output", "json"),
        ("gzip", "false"),
        ("fl", "timestamp,original,mimetype,statuscode,digest,length"),
        ("collapse", "digest"),
        ("limit", str(WAYBACK_LIMIT)),
        ("from", "2023"),
        ("to", "2023"),
    ]
    assert response.result.licence is None and response.result.source_url == url
    assert connector.tool_kind is ToolKind.ARCHIVE_LOOKUP


def test_every_capture_is_a_row_with_its_fields_as_published() -> None:
    result = _connector()[0].query(_query()).result
    assert [r.key for r in result.rows] == ["c1", "c2", "c3", "c4"]
    first = result.rows[0]
    assert first.label == "1. capture 20221230080000"
    assert first.values == (
        "20221230080000",
        PAGE,
        "text/html",
        "200",
        "FIKTIVNI2022AAAAAAAAAAAAAAAAAAAA",
        "5120",
        f"https://web.archive.org/web/20221230080000/{PAGE}",
    )
    # A capture's status is grounded like any cell.
    snapshot = dataset_snapshot(_connector()[0].query(_query()), retrieval_mode=RetrievalMode.LIVE)
    assert ground_cell(
        snapshot=snapshot,
        locator=f"{PAGE}!c4/statuscode",
        quote="4. capture 20240615000000 | HTTP status (statuscode) = 404",
    ).grounded


@pytest.mark.parametrize(
    ("cited", "key"),
    [
        ("20230115", "c1"),  # 16 days after c1, 45 before c3; the 301 at c2 is no copy
        ("2023", "c1"),
        ("202303", "c3"),
        ("20300101", "c3"),  # the 404 capture of 2024 is no copy of the page
    ],
)
def test_the_nearest_capture_is_a_200_copy_nearest_the_cited_date(cited: str, key: str) -> None:
    result = _connector()[0].query(_query()).result
    assert nearest_capture(result, cited) == key


def test_no_capture_is_an_empty_table_said_in_words() -> None:
    result = _connector(_answer(b"[]"))[0].query(_query()).result
    assert result.rows == () and nearest_capture(result, "2023") is None
    assert result.notes == ("The index holds no capture of this URL for the query asked.",)


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"dataset_id": "https://localhost/private"}, "dataset_id_invalid"),
        ({"dataset_id": "ftp://zpravy.example/x"}, "dataset_id_invalid"),
        ({"dataset_id": "https://10.0.0.1/x"}, "dataset_id_invalid"),
        ({"period": "2023-Q1"}, "period_invalid"),
        ({"period": "20231"}, "period_invalid"),
        ({"filters": [{"dimension": "statuscode", "values": ["200"]}]}, "filters_unsupported"),
        ({"connector_id": "eurostat-statistics-1"}, "connector_mismatch"),
    ],
)
def test_a_lookup_this_connector_cannot_put_is_never_sent(
    over: dict[str, Any], reason: str
) -> None:
    connector, transport = _connector()
    with pytest.raises(ToolCallFailed) as failed:
        connector.query(_query(**over))
    assert failed.value.reason == reason and failed.value.delivery is Delivery.NOT_SENT
    assert transport.calls == []


def _rows(*rows: list[str]) -> bytes:
    header = ["timestamp", "original", "mimetype", "statuscode", "digest", "length"]
    return json.dumps([header, *rows]).encode()


_OK = ["20230101000000", PAGE, "text/html", "200", "FIKTIVNI", "1"]


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_answer(b"not json"), "response_contract"),
        (_answer(b'{"captures": []}'), "response_contract"),
        (_answer(json.dumps([["urlkey", "timestamp"], ["x", "y"]]).encode()), "response_contract"),
        (_answer(_rows([*_OK[:5]])), "response_contract"),
        (_answer(_rows(["2023", *_OK[1:]])), "response_contract"),
        (_answer(_rows(["20231301000000", *_OK[1:]])), "response_contract"),
        (_answer(_rows([*_OK[:3], "ok", *_OK[4:]])), "response_contract"),
        (_answer(_rows([_OK[0], "a page", *_OK[2:]])), "response_contract"),
        (_answer(_rows(*[_OK] * WAYBACK_LIMIT)), "dataset_too_large"),
        (_answer(headers={"content-type": "text/html"}), "content_type"),
        (_answer(status=503), "http_503"),
        (_answer(truncated=True), "body_too_large"),
    ],
)  # fmt: skip
def test_an_answer_outside_the_cdx_format_is_refused(
    response: FetchedResponse, reason: str
) -> None:
    with pytest.raises(ToolCallFailed) as failed:
        _connector(response)[0].query(_query())
    assert failed.value.reason == reason and failed.value.delivery is Delivery.RESPONDED


def test_the_connector_requires_a_live_transport() -> None:
    with pytest.raises(ValueError):
        WaybackCdxConnector(
            transport=RecordedFetchTransport(pages={}), resolver=RecordedResolver(hosts={})
        )
