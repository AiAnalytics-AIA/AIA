"""The Common Crawl adapters: Athena's JSON API, archived records by range, the settings.

No network and no AWS. Athena answers come from a scripted wire shaped like the
service model's (botocore ``athena/2017-05-18``); archive files are built here
from fictional pages, one gzip member per record.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest

from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.common_crawl import (
    INDEX_COLUMNS,
    AthenaPricing,
    IndexRow,
    IndexTable,
)
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.infrastructure.common_crawl import (
    ArchiveFetcher,
    ArchiveRangeTransport,
    AthenaUrlIndex,
    IndexQueryFailed,
    PostResponse,
    RecordedArchiveTransport,
    common_crawl_settings,
)
from aia_core.infrastructure.model_adapters.bedrock import SigningUnavailable
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedResolver,
    ToolCallFailed,
)

TABLE = IndexTable(database="ccindex", table="ccindex")
CRAWL = "CC-MAIN-2024-10"
FILE = f"crawl-data/{CRAWL}/segments/1700000000000.10/warc/CC-MAIN-20240101-00001.warc.gz"
FILE_URL = f"https://data.commoncrawl.org/{FILE}"
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)

# --------------------------------------------------------------------------- #
# Athena
# --------------------------------------------------------------------------- #


class _Signer:
    def __init__(self, refuse: bool = False) -> None:
        self.refuse = refuse

    def sign(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, str]:
        if self.refuse:
            raise SigningUnavailable("no role")
        return {**headers, "authorization": "AWS4-HMAC-SHA256 test"}


@dataclass
class _Wire:
    """Answers each action from a queue of (status, payload); records what was sent."""

    answers: dict[str, list[tuple[int, Any]]]
    sent: list[tuple[str, dict[str, Any], Mapping[str, str]]] = field(default_factory=list)

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, max_bytes: int
    ) -> PostResponse:
        action = headers["x-amz-target"].split(".", 1)[1]
        self.sent.append((action, json.loads(body), headers))
        queue = self.answers.get(action) or [(200, {})]
        status, payload = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(payload, Exception):
            raise payload
        return PostResponse(
            status=status, headers={}, body=json.dumps(payload).encode(), truncated=False
        )

    def actions(self) -> list[str]:
        return [action for action, _, _ in self.sent]


def _execution(state: str, scanned: int | None = None, error: str | None = None) -> dict[str, Any]:
    execution: dict[str, Any] = {"QueryExecutionId": "q-1", "Status": {"State": state}}
    if scanned is not None:
        execution["Statistics"] = {"DataScannedInBytes": scanned}
    if error:
        execution["Status"]["AthenaError"] = {"ErrorType": error}
    return {"QueryExecution": execution}


def _results(rows: list[list[str | None]]) -> dict[str, Any]:
    header = [{"VarCharValue": c} for c in INDEX_COLUMNS]
    return {
        "ResultSet": {
            "ResultSetMetadata": {
                "ColumnInfo": [{"Name": c, "Type": "varchar"} for c in INDEX_COLUMNS]
            },
            "Rows": [{"Data": header}]
            + [{"Data": [{} if v is None else {"VarCharValue": v} for v in r]} for r in rows],
        }
    }


ROW = [
    "https://stats.example/zprava/2023",
    "2024-02-21 10:11:12.000",
    "200",
    "text/html",
    None,
    FILE,
    "0",
    "100",
    CRAWL,
]


def _index(wire: _Wire, *, signer: _Signer | None = None, timeout_s: float = 10.0) -> Any:
    clock = {"t": 0.0}

    def sleep(seconds: float) -> None:
        clock["t"] += seconds

    return AthenaUrlIndex(
        workgroup="aia-ccindex",
        table=TABLE,
        signer=signer or _Signer(),
        wire=wire,
        poll_interval_s=1.0,
        timeout_s=timeout_s,
        monotonic=lambda: clock["t"],
        sleep=sleep,
    )


def test_a_statement_runs_in_the_workgroup_and_its_rows_and_scan_come_back() -> None:
    wire = _Wire(
        answers={
            "StartQueryExecution": [(200, {"QueryExecutionId": "q-1"})],
            "GetQueryExecution": [
                (200, _execution("QUEUED")),
                (200, _execution("RUNNING")),
                (200, _execution("SUCCEEDED", scanned=123_456_789)),
            ],
            "GetQueryResults": [(200, _results([ROW]))],
        }
    )
    index = _index(wire)
    assert index.retrieval_mode is RetrievalMode.LIVE
    result = index.run("SELECT 1", request_token="00000000-0000-4000-8000-000000000001", max_rows=5)
    assert wire.actions() == [
        "StartQueryExecution",
        "GetQueryExecution",
        "GetQueryExecution",
        "GetQueryExecution",
        "GetQueryResults",
    ]
    _, start, headers = wire.sent[0]
    assert start == {
        "QueryString": "SELECT 1",
        "ClientRequestToken": "00000000-0000-4000-8000-000000000001",
        "WorkGroup": "aia-ccindex",
        "QueryExecutionContext": {"Database": "ccindex"},
    }
    assert headers["content-type"] == "application/x-amz-json-1.1"
    assert headers["x-amz-target"] == "AmazonAthena.StartQueryExecution"
    assert headers["host"] == "athena.us-east-1.amazonaws.com"
    assert "authorization" in headers
    assert wire.sent[-1][1] == {"QueryExecutionId": "q-1", "MaxResults": 6}
    # The header row Athena repeats is dropped; the data row stays.
    assert result.columns == INDEX_COLUMNS
    assert result.rows == (tuple(ROW),)
    assert result.data_scanned_bytes == 123_456_789
    assert result.execution_id == "q-1"


def test_a_query_refused_at_start_scanned_nothing() -> None:
    wire = _Wire(
        answers={
            "StartQueryExecution": [
                (400, {"__type": "InvalidRequestException", "Message": "no output location"})
            ]
        }
    )
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "athena_InvalidRequestException"
    assert caught.value.delivery is Delivery.RESPONDED
    assert caught.value.data_scanned_bytes == 0


def test_a_server_error_at_start_may_have_run_so_its_scan_is_unknown() -> None:
    wire = _Wire(answers={"StartQueryExecution": [(500, {"__type": "InternalServerException"})]})
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.delivery is Delivery.UNKNOWN
    assert caught.value.data_scanned_bytes is None


def test_no_role_means_nothing_is_sent() -> None:
    wire = _Wire(answers={})
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire, signer=_Signer(refuse=True)).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "signing_unavailable"
    assert caught.value.delivery is Delivery.NOT_SENT
    assert caught.value.data_scanned_bytes == 0
    assert wire.sent == []


def test_a_failed_query_reports_what_it_scanned() -> None:
    wire = _Wire(
        answers={
            "StartQueryExecution": [(200, {"QueryExecutionId": "q-1"})],
            "GetQueryExecution": [(200, _execution("CANCELLED", 10_500_000, "BYTES_SCANNED"))],
        }
    )
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "athena_cancelled"
    assert caught.value.delivery is Delivery.RESPONDED
    assert caught.value.data_scanned_bytes == 10_500_000
    assert caught.value.execution_id == "q-1"


def test_a_query_that_does_not_end_in_time_is_stopped_and_its_cost_is_unknown() -> None:
    wire = _Wire(
        answers={
            "StartQueryExecution": [(200, {"QueryExecutionId": "q-1"})],
            "GetQueryExecution": [(200, _execution("RUNNING"))],
        }
    )
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire, timeout_s=3.0).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "athena_timeout"
    assert caught.value.delivery is Delivery.UNKNOWN
    assert caught.value.data_scanned_bytes is None
    assert wire.actions()[-1] == "StopQueryExecution"
    assert wire.sent[-1][1] == {"QueryExecutionId": "q-1"}


def test_a_lost_state_answer_stops_the_query_and_leaves_its_cost_unknown() -> None:
    lost = ToolCallFailed("reset", reason="transport_failed", delivery=Delivery.UNKNOWN)
    wire = _Wire(
        answers={
            "StartQueryExecution": [(200, {"QueryExecutionId": "q-1"})],
            "GetQueryExecution": [(200, lost)],
        }
    )
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "athena_state_unknown"
    assert caught.value.data_scanned_bytes is None
    assert wire.actions()[-1] == "StopQueryExecution"


def test_unreadable_results_still_report_the_scan() -> None:
    wire = _Wire(
        answers={
            "StartQueryExecution": [(200, {"QueryExecutionId": "q-1"})],
            "GetQueryExecution": [(200, _execution("SUCCEEDED", scanned=42))],
            "GetQueryResults": [(200, {"ResultSet": {"Rows": "not a list"}})],
        }
    )
    with pytest.raises(IndexQueryFailed) as caught:
        _index(wire).run("SELECT 1", request_token="t", max_rows=1)
    assert caught.value.reason == "athena_results_failed"
    assert caught.value.data_scanned_bytes == 42


def test_the_instance_role_signer_signs_for_athena_in_us_east_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("botocore")
    from botocore.credentials import Credentials

    from aia_core.infrastructure.model_adapters import aws_signing

    role = Credentials("ASIATESTNOTREAL00000", "test-secret", "test-token", method="iam-role")

    class Session:
        def get_credentials(self) -> Credentials:
            return role

    monkeypatch.setattr("botocore.session.get_session", lambda: Session())
    signer = aws_signing.InstanceRoleSigner(region="us-east-1", service="athena")
    headers = signer.sign(
        method="POST",
        url="https://athena.us-east-1.amazonaws.com/",
        headers={"content-type": "application/x-amz-json-1.1"},
        body=b"{}",
    )
    assert "/us-east-1/athena/aws4_request" in headers["authorization"]


# --------------------------------------------------------------------------- #
# Archived records
# --------------------------------------------------------------------------- #

PAGE = (
    "<html><head><title>Zpráva 2023</title></head><body>"
    "<p>Fiktivní statistický úřad uvádí, že spotřeba rostlinných nápojů vzrostla o 12 %.</p>"
    "</body></html>"
).encode()


def warc_member(
    body: bytes = PAGE, *, target: str = "https://stats.example/zprava/2023", status: str = "200"
) -> bytes:
    block = (
        f"HTTP/1.1 {status} OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n".encode() + body
    )
    digest = base64.b32encode(hashlib.sha1(body).digest()).decode()
    head = (
        "WARC/1.0\r\n"
        "WARC-Type: response\r\n"
        "WARC-Date: 2024-02-21T10:11:12Z\r\n"
        "WARC-Record-ID: <urn:uuid:00000000-0000-4000-8000-000000000002>\r\n"
        f"WARC-Target-URI: {target}\r\n"
        "Content-Type: application/http; msgtype=response\r\n"
        f"WARC-Payload-Digest: sha1:{digest}\r\n"
        f"Content-Length: {len(block)}\r\n\r\n"
    ).encode()
    return gzip.compress(head + block + b"\r\n\r\n", mtime=0)


def _row(offset: int, length: int, **overrides: Any) -> IndexRow:
    values: dict[str, Any] = {
        "url": "https://stats.example/zprava/2023",
        "captured_at": datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC),
        "status": 200,
        "mime_type": "text/html",
        "digest": None,
        "warc_filename": FILE,
        "warc_record_offset": offset,
        "warc_record_length": length,
        "crawl": CRAWL,
    }
    values.update(overrides)
    return IndexRow(**values)


def _fetcher(files: Mapping[str, bytes]) -> tuple[ArchiveFetcher, RecordedArchiveTransport]:
    transport = RecordedArchiveTransport(files=files)
    fetcher = ArchiveFetcher(
        transport=transport,
        resolver=RecordedResolver(hosts={"data.commoncrawl.org": ["18.160.0.10"]}),
        adapter_id="recorded-archive-v1",
        clock=lambda: NOW,
    )
    return fetcher, transport


def test_the_record_the_index_names_is_read_from_its_range_and_says_it_is_archived() -> None:
    first = warc_member(b"<p>Jina fiktivni stranka, jiny zaznam.</p>", target="https://x.example/")
    second = warc_member()
    fetcher, transport = _fetcher({FILE_URL: first + second})
    page = fetcher.fetch(_row(len(first), len(second)))
    assert transport.calls == [(FILE_URL, len(first), len(second))]
    snapshot = page.snapshot
    assert snapshot.url == "https://stats.example/zprava/2023"
    assert snapshot.title == "Zpráva 2023" and "vzrostla o 12 %" in snapshot.text
    assert snapshot.retrieval_mode is RetrievalMode.RECORDED
    assert snapshot.retrieved_at == NOW
    capture = snapshot.archive
    assert capture is not None
    assert capture.captured_at == datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC)
    assert (capture.crawl, capture.warc_filename) == (CRAWL, FILE)
    assert (capture.warc_record_offset, capture.warc_record_length) == (len(first), len(second))
    assert capture.payload_digest is not None and capture.payload_digest.startswith("sha1:")


@pytest.mark.parametrize(
    ("row_of", "reason"),
    [
        (lambda n: _row(0, n - 7), "archive_record_truncated"),  # the member is cut
        (lambda n: _row(0, n, url="https://stats.example/jina"), "archive_record_mismatch"),
        (lambda n: _row(0, n + 50), "range_mismatch"),  # the file ends first: a shorter range
    ],
)
def test_a_range_that_is_not_exactly_the_named_record_is_refused(row_of: Any, reason: str) -> None:
    member = warc_member()
    fetcher, _ = _fetcher({FILE_URL: member})
    with pytest.raises(FetchRefused) as caught:
        fetcher.fetch(row_of(len(member)))
    assert caught.value.reason == reason


def test_an_archived_redirect_is_not_a_page() -> None:
    member = warc_member(status="301")
    fetcher, _ = _fetcher({FILE_URL: member})
    with pytest.raises(FetchRefused) as caught:
        fetcher.fetch(_row(0, len(member), status=301))
    assert caught.value.reason == "archive_not_a_page"


def test_a_missing_file_is_the_archive_s_answer_and_an_ignored_range_is_refused() -> None:
    fetcher, _ = _fetcher({})
    with pytest.raises(ToolCallFailed) as caught:
        fetcher.fetch(_row(0, 100))
    assert caught.value.reason == "http_404" and caught.value.delivery is Delivery.RESPONDED

    class WholeFile(RecordedArchiveTransport):
        def get_range(self, url: str, *, address: str, offset: int, length: int) -> FetchedResponse:
            return FetchedResponse(status=200, headers={}, body=b"x" * length, truncated=True)

    ignoring = ArchiveFetcher(
        transport=WholeFile(files={}),
        resolver=RecordedResolver(hosts={"data.commoncrawl.org": ["18.160.0.10"]}),
        adapter_id="recorded-archive-v1",
    )
    with pytest.raises(FetchRefused) as refused:
        ignoring.fetch(_row(0, 100))
    assert refused.value.reason == "range_ignored"


@dataclass
class _HttpsWire:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def get(
        self, *, address: str, host: str, target: str, headers: Mapping[str, str], max_bytes: int
    ) -> FetchedResponse:
        self.calls.append(
            {"address": address, "host": host, "target": target, "headers": dict(headers)}
        )
        return FetchedResponse(
            status=206,
            headers={"content-range": "bytes 10-19/100"},
            body=b"0123456789",
            truncated=False,
        )


def test_the_live_range_transport_asks_for_exactly_the_record_from_the_pinned_host() -> None:
    wire = _HttpsWire()
    transport = ArchiveRangeTransport(contact="ops@aia.example", wire=wire, min_interval_s=0)
    response = transport.get_range(FILE_URL, address="18.160.0.10", offset=10, length=10)
    assert response.status == 206
    (call,) = wire.calls
    assert call["host"] == "data.commoncrawl.org" and call["target"] == f"/{FILE}"
    assert call["headers"]["Range"] == "bytes=10-19"
    assert call["headers"]["Accept-Encoding"] == "identity"
    assert call["headers"]["User-Agent"] == "AIA-research/1 (+mailto:ops@aia.example)"
    with pytest.raises(FetchRefused) as caught:
        transport.get_range("https://stats.example/a", address="18.160.0.10", offset=0, length=1)
    assert caught.value.reason == "host_scope"
    with pytest.raises(FetchRefused):
        transport.get_range(FILE_URL, address="10.0.0.1", offset=0, length=1)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

ENV = {
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_WORKGROUP": "aia-ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_DATABASE": "ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_TABLE": "ccindex",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES": "20000000000",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED": "5",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_MIN_BILLED_BYTES": "10000000",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_BILLING_INCREMENT_BYTES": "1000000",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF": "2026-10-06",
}


def test_the_settings_are_read_whole_and_the_reservation_is_the_cutoff_billed() -> None:
    settings = common_crawl_settings(ENV)
    assert settings.workgroup == "aia-ccindex" and settings.table == TABLE
    assert settings.pricing == AthenaPricing(5.0, 10_000_000, 1_000_000)
    assert settings.prices_as_of == date(2026, 10, 6)
    assert settings.reservation_usd == pytest.approx(0.1)


@pytest.mark.parametrize("key", sorted(ENV))
def test_every_setting_is_required_and_a_missing_one_names_itself(key: str) -> None:
    env = {k: v for k, v in ENV.items() if k != key}
    with pytest.raises(ValueError, match=key):
        common_crawl_settings(env)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES", "1000"),
        ("AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED", "0"),
        ("AIA_DEEP_RESEARCH_COMMON_CRAWL_USD_PER_TB_SCANNED", "five"),
        ("AIA_DEEP_RESEARCH_COMMON_CRAWL_TABLE", "cc index"),
        ("AIA_DEEP_RESEARCH_COMMON_CRAWL_PRICES_AS_OF", "October"),
    ],
)
def test_an_invalid_setting_is_refused(key: str, value: str) -> None:
    with pytest.raises(ValueError):
        common_crawl_settings({**ENV, key: value})
