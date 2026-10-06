"""Common Crawl: the URL index through Amazon Athena, and archived records by byte range.

Plan chunk 18. Everything here sits *under*
:class:`~aia_core.application.web_retrieval.RetrievalGate`, which writes the index
statement from validated values, classifies it, checks egress, reserves, journals
and settles; nothing here decides whether to send, and nothing retries, reroutes
or substitutes.

* :class:`AthenaUrlIndex` -- one statement through Athena's JSON API
  (``StartQueryExecution``, then ``GetQueryExecution`` until it ends, then one
  page of ``GetQueryResults``) at ``https://athena.us-east-1.amazonaws.com/``,
  SigV4-signed for service ``athena`` by the instance or container role
  (:class:`~aia_core.infrastructure.model_adapters.aws_signing.InstanceRoleSigner`,
  the one place botocore is imported). The request shapes follow botocore's
  Athena service model (``athena/2017-05-18``); the adapter has not yet been run
  against AWS (``docs/architecture/deep-research-common-crawl.md``). A query runs
  in a workgroup whose own configuration -- enforced -- names the results bucket
  and the bytes-scanned cutoff, so nothing here chooses where results go or how
  much a query may scan. Every outcome states the bytes Athena reported scanned,
  or ``None`` when that is not known, which the gate charges at its ceiling.
* :class:`ArchiveFetcher` -- one WARC record from ``data.commoncrawl.org`` by an
  HTTPS ``Range`` request for exactly the bytes the index names, through
  :class:`ArchiveRangeTransport` (the checked address, the host pinned, one
  request at a time); the gzip member is inflated with a bound, the record read
  strictly (``domain.deep_research.warc``) and checked against its index row, and
  the body becomes a snapshot through :func:`~.web_retrieval.page_snapshot`, the
  path a live page takes, stamped as an archived capture.
* :func:`common_crawl_settings` -- the configuration, every key required: the
  workgroup, database and table, the scan cutoff and the dated price.

The recorded doubles (:class:`RecordedUrlIndex`, :class:`RecordedArchiveTransport`)
are test doubles beside the adapters, as for web retrieval: they state
``RECORDED`` and nothing else, and ``make layer_check`` keeps them out of every
composition but the local recorded one.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Final, Protocol

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.common_crawl import (
    ARCHIVE_HOST,
    ATHENA_REGION,
    MAX_INDEX_ROWS,
    AthenaPricing,
    IndexRow,
    IndexTable,
    archive_url,
)
from ..domain.deep_research.contracts import ArchivedCapture, RetrievalMode
from ..domain.deep_research.warc import inflate_member, parse_response_record
from ..domain.deep_research.web import (
    MAX_BODY_BYTES,
    FetchRefused,
    check_address,
    check_resolution,
    check_url,
)
from .web_retrieval import FetchedPage, FetchedResponse, Resolver, ToolCallFailed, page_snapshot
from .web_retrieval_live import HttpsWire, UrllibWire, public_user_agent

__all__ = [
    "ATHENA_SIGNING_SERVICE",
    "ArchiveFetcher",
    "ArchiveRangeTransport",
    "AthenaUrlIndex",
    "AwsSigner",
    "CommonCrawlSettings",
    "IndexQueryFailed",
    "IndexQueryResult",
    "JsonPostWire",
    "PostResponse",
    "RangeTransport",
    "RecordedArchiveTransport",
    "RecordedUrlIndex",
    "UrlIndex",
    "UrllibPostWire",
    "athena_endpoint",
    "common_crawl_settings",
]

#: The SigV4 signing name of Athena (botocore service model ``metadata.signingName``
#: is absent, so the endpoint prefix ``athena`` signs).
ATHENA_SIGNING_SERVICE: Final = "athena"
#: The JSON protocol's target prefix (service model ``metadata.targetPrefix``).
_TARGET_PREFIX: Final = "AmazonAthena"
_CONTENT_TYPE: Final = "application/x-amz-json-1.1"
#: An Athena answer AIA reads: one page of at most 1,000 short rows fits easily.
MAX_ATHENA_RESPONSE_BYTES: Final = 4_000_000
_TERMINAL: Final = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
_RUNNING: Final = frozenset({"QUEUED", "RUNNING"})
_CONTENT_RANGE: Final = re.compile(r"^bytes (\d+)-(\d+)/(\d+|\*)$")


def athena_endpoint(region: str = ATHENA_REGION) -> str:
    """``https://athena.{region}.amazonaws.com/`` (botocore's endpoint rule set)."""
    return f"https://athena.{region}.amazonaws.com/"


# --------------------------------------------------------------------------- #
# The index
# --------------------------------------------------------------------------- #


class IndexQueryFailed(ToolCallFailed):
    """A URL index query that returned no rows. ``data_scanned_bytes`` is what it cost.

    ``None`` means the bytes scanned are not known -- the query may have run --
    and the gate charges the call's ceiling. ``0`` means nothing was scanned (the
    query was refused before it was created).
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        delivery: Delivery,
        data_scanned_bytes: int | None,
        execution_id: str | None = None,
    ) -> None:
        super().__init__(message, reason=reason, delivery=delivery)
        self.data_scanned_bytes = data_scanned_bytes
        self.execution_id = execution_id


@dataclass(frozen=True, slots=True)
class IndexQueryResult:
    """One statement's answer: its columns, its rows as text, and what it scanned."""

    execution_id: str | None
    columns: tuple[str, ...]
    rows: tuple[tuple[str | None, ...], ...]
    #: Athena's ``Statistics.DataScannedInBytes``; ``None`` when it was not reported.
    data_scanned_bytes: int | None


class UrlIndex(Protocol):
    """A URL index that runs one statement the gate wrote. Never retries."""

    @property
    def adapter_id(self) -> str: ...

    @property
    def retrieval_mode(self) -> RetrievalMode: ...

    @property
    def table(self) -> IndexTable:
        """The database and table the gate's statement names."""
        ...

    def run(self, statement: str, *, request_token: str, max_rows: int) -> IndexQueryResult:
        """Run ``statement`` once, or raise :class:`IndexQueryFailed`."""
        ...


class AwsSigner(Protocol):
    """SigV4 for one service and region; the headers to send, auth included."""

    def sign(
        self, *, method: str, url: str, headers: Mapping[str, str], body: bytes
    ) -> dict[str, str]: ...


@dataclass(frozen=True, slots=True)
class PostResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    truncated: bool


class JsonPostWire(Protocol):
    """One HTTPS POST. No redirect, no retry; a failure states its delivery."""

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, max_bytes: int
    ) -> PostResponse:
        """Raise :class:`ToolCallFailed` when no answer was read."""
        ...


class UrllibPostWire:
    """:class:`JsonPostWire` over urllib3: no retry, no redirect, delivery from the failure.

    The same rules as the model transport (``model_adapters.live_transport``): a
    failure before any byte is written (connection refused, connect timeout, the
    certificate refused) is ``NOT_SENT``; anything else may have been served.
    """

    def __init__(self, *, connect_timeout_s: float = 8.0, read_timeout_s: float = 20.0) -> None:
        import urllib3

        self._urllib3 = urllib3
        self._timeout = urllib3.Timeout(connect=connect_timeout_s, read=read_timeout_s)
        self._pool = urllib3.PoolManager(retries=False, maxsize=2, block=True)

    def post(
        self, url: str, *, headers: Mapping[str, str], body: bytes, max_bytes: int
    ) -> PostResponse:
        from .model_adapters.live_transport import _certificate_refused

        u = self._urllib3
        response: Any = None
        try:
            response = self._pool.request(
                "POST",
                url,
                body=body,
                headers=dict(headers),
                timeout=self._timeout,
                retries=False,
                redirect=False,
                preload_content=False,
            )
            data = bytearray()
            while len(data) <= max_bytes:
                chunk = response.read(min(65_536, max_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            return PostResponse(
                status=int(response.status),
                headers={k.lower(): str(v) for k, v in response.headers.items()},
                body=bytes(data[:max_bytes]),
                truncated=len(data) > max_bytes,
            )
        except (u.exceptions.ConnectTimeoutError, u.exceptions.NewConnectionError) as exc:
            raise ToolCallFailed(
                str(exc), reason="connect_failed", delivery=Delivery.NOT_SENT
            ) from exc
        except u.exceptions.SSLError as exc:
            delivery = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
            raise ToolCallFailed(str(exc), reason="tls_failed", delivery=delivery) from exc
        except u.exceptions.HTTPError as exc:
            raise ToolCallFailed(
                str(exc), reason="transport_failed", delivery=Delivery.UNKNOWN
            ) from exc
        finally:
            if response is not None:
                response.release_conn()


class _AthenaRefused(Exception):
    """Athena answered an action with an error. ``server`` for a 5xx (it may have acted)."""

    def __init__(self, code: str, message: str, *, status: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.server = status >= 500


def _error_code(headers: Mapping[str, str], payload: Any) -> str:
    raw = headers.get("x-amzn-errortype", "")
    if not raw and isinstance(payload, Mapping):
        raw = str(payload.get("__type") or payload.get("code") or "")
    return raw.split(":", 1)[0].rsplit("#", 1)[-1] or "Unknown"


def _scanned(execution: Mapping[str, Any]) -> int | None:
    statistics = execution.get("Statistics")
    value = statistics.get("DataScannedInBytes") if isinstance(statistics, Mapping) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


class AthenaUrlIndex:
    """The Common Crawl URL index through Athena, in its workgroup, one statement at a time.

    Live: every request is SigV4-signed by ``signer`` (an instance or container
    role) and sent once through ``wire``. ``timeout_s`` bounds the wait for a
    query to end; at the bound the query is asked to stop and its cost is
    unknown. The workgroup must enforce its own configuration (results bucket,
    encryption, bytes-scanned cutoff): this adapter sends no result location.
    """

    adapter_id: Final = "athena-ccindex-1"

    def __init__(
        self,
        *,
        workgroup: str,
        table: IndexTable,
        signer: AwsSigner,
        wire: JsonPostWire,
        region: str = ATHENA_REGION,
        poll_interval_s: float = 1.0,
        timeout_s: float = 120.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", workgroup):
            raise ValueError("an Athena workgroup name is 1 to 128 of [A-Za-z0-9._-]")
        if not 0 < poll_interval_s <= timeout_s:
            raise ValueError("the poll interval is positive and within the timeout")
        self._workgroup = workgroup
        self._table = table
        self._signer = signer
        self._wire = wire
        self._url = athena_endpoint(region)
        self._host = check_url(self._url)
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._monotonic = monotonic
        self._sleep = sleep

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    @property
    def table(self) -> IndexTable:
        return self._table

    def _call(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """One signed JSON action. Raises ToolCallFailed (no answer) or _AthenaRefused."""
        from .model_adapters.bedrock import SigningUnavailable

        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        unsigned = {
            "host": self._host,
            "content-type": _CONTENT_TYPE,
            "x-amz-target": f"{_TARGET_PREFIX}.{action}",
        }
        try:
            headers = self._signer.sign(method="POST", url=self._url, headers=unsigned, body=body)
        except SigningUnavailable as exc:
            raise ToolCallFailed(
                str(exc), reason="signing_unavailable", delivery=Delivery.NOT_SENT
            ) from exc
        response = self._wire.post(
            self._url, headers=headers, body=body, max_bytes=MAX_ATHENA_RESPONSE_BYTES
        )
        if response.truncated:
            raise _AthenaRefused(
                "ResponseTooLarge", "answer past its bound", status=response.status
            )
        try:
            parsed: Any = json.loads(response.body) if response.body else {}
        except (UnicodeDecodeError, ValueError):
            parsed = None
        if response.status != 200:
            code = _error_code(response.headers, parsed)
            message = str(parsed.get("Message", "")) if isinstance(parsed, Mapping) else ""
            raise _AthenaRefused(code, message[:300], status=response.status)
        if not isinstance(parsed, Mapping):
            raise _AthenaRefused("InvalidResponse", "the answer is not a JSON object", status=200)
        return parsed

    def _stop(self, execution_id: str) -> None:
        """Ask Athena to stop a query whose end we will not wait for. Best effort."""
        with contextlib.suppress(ToolCallFailed, _AthenaRefused):
            self._call("StopQueryExecution", {"QueryExecutionId": execution_id})

    def _start(self, statement: str, request_token: str) -> str:
        try:
            started = self._call(
                "StartQueryExecution",
                {
                    "QueryString": statement,
                    "ClientRequestToken": request_token,
                    "WorkGroup": self._workgroup,
                    "QueryExecutionContext": {"Database": self._table.database},
                },
            )
        except _AthenaRefused as exc:
            # A 4xx: no query was created and nothing scanned. A 5xx: it may have been.
            raise IndexQueryFailed(
                str(exc),
                reason=f"athena_{exc.code}",
                delivery=Delivery.UNKNOWN if exc.server else Delivery.RESPONDED,
                data_scanned_bytes=None if exc.server else 0,
            ) from exc
        except ToolCallFailed as exc:
            raise IndexQueryFailed(
                str(exc),
                reason=exc.reason,
                delivery=exc.delivery,
                data_scanned_bytes=0 if exc.delivery is Delivery.NOT_SENT else None,
            ) from exc
        execution_id = started.get("QueryExecutionId")
        if not isinstance(execution_id, str) or not execution_id:
            raise IndexQueryFailed(
                "Athena started no query it named",
                reason="athena_contract",
                delivery=Delivery.UNKNOWN,
                data_scanned_bytes=None,
            )
        return execution_id

    def _wait(self, execution_id: str) -> tuple[str, Mapping[str, Any]]:
        deadline = self._monotonic() + self._timeout_s
        while True:
            try:
                answer = self._call("GetQueryExecution", {"QueryExecutionId": execution_id})
                execution = answer.get("QueryExecution")
                if not isinstance(execution, Mapping):
                    raise _AthenaRefused("InvalidResponse", "no QueryExecution", status=200)
                status = execution.get("Status")
                state = status.get("State") if isinstance(status, Mapping) else None
                if state not in _TERMINAL and state not in _RUNNING:
                    raise _AthenaRefused("InvalidResponse", f"state {state!r}", status=200)
            except (ToolCallFailed, _AthenaRefused) as exc:
                self._stop(execution_id)
                raise IndexQueryFailed(
                    f"the query's state could not be read: {exc}",
                    reason="athena_state_unknown",
                    delivery=Delivery.UNKNOWN,
                    data_scanned_bytes=None,
                    execution_id=execution_id,
                ) from exc
            if state in _TERMINAL:
                return str(state), execution
            if self._monotonic() >= deadline:
                self._stop(execution_id)
                raise IndexQueryFailed(
                    f"the query did not end within {self._timeout_s:g} s",
                    reason="athena_timeout",
                    delivery=Delivery.UNKNOWN,
                    data_scanned_bytes=None,
                    execution_id=execution_id,
                )
            self._sleep(self._poll_interval_s)

    def _results(
        self, execution_id: str, max_rows: int
    ) -> tuple[tuple[str, ...], tuple[tuple[str | None, ...], ...]]:
        answer = self._call(
            "GetQueryResults",
            {"QueryExecutionId": execution_id, "MaxResults": min(MAX_INDEX_ROWS, max_rows + 1)},
        )
        result = answer.get("ResultSet")
        if not isinstance(result, Mapping):
            raise _AthenaRefused("InvalidResponse", "no ResultSet", status=200)
        metadata = result.get("ResultSetMetadata")
        info = metadata.get("ColumnInfo") if isinstance(metadata, Mapping) else None
        if not isinstance(info, list) or not all(
            isinstance(c, Mapping) and isinstance(c.get("Name"), str) for c in info
        ):
            raise _AthenaRefused("InvalidResponse", "no column names", status=200)
        columns = tuple(str(c["Name"]) for c in info)
        raw_rows = result.get("Rows")
        if not isinstance(raw_rows, list):
            raise _AthenaRefused("InvalidResponse", "no rows", status=200)
        rows: list[tuple[str | None, ...]] = []
        for raw in raw_rows:
            data = raw.get("Data") if isinstance(raw, Mapping) else None
            if not isinstance(data, list):
                raise _AthenaRefused("InvalidResponse", "a row without data", status=200)
            values: list[str | None] = []
            for datum in data:
                value = datum.get("VarCharValue") if isinstance(datum, Mapping) else None
                if value is not None and not isinstance(value, str):
                    raise _AthenaRefused("InvalidResponse", "a value is not text", status=200)
                values.append(value)
            rows.append(tuple(values))
        # A SELECT's first row repeats the column names; drop it when it does.
        if rows and rows[0] == columns:
            rows = rows[1:]
        return columns, tuple(rows[:max_rows])

    def run(self, statement: str, *, request_token: str, max_rows: int) -> IndexQueryResult:
        if not 1 <= max_rows <= MAX_INDEX_ROWS:
            raise ValueError(f"a query returns 1 to {MAX_INDEX_ROWS} rows")
        execution_id = self._start(statement, request_token)
        state, execution = self._wait(execution_id)
        scanned = _scanned(execution)
        if state != "SUCCEEDED":
            status = execution.get("Status")
            error = status.get("AthenaError") if isinstance(status, Mapping) else None
            kind = error.get("ErrorType") if isinstance(error, Mapping) else None
            raise IndexQueryFailed(
                f"the query ended {state} ({kind})",
                reason=f"athena_{state.lower()}",
                delivery=Delivery.RESPONDED,
                data_scanned_bytes=scanned,
                execution_id=execution_id,
            )
        try:
            columns, rows = self._results(execution_id, max_rows)
        except (ToolCallFailed, _AthenaRefused) as exc:
            raise IndexQueryFailed(
                f"the query's results could not be read: {exc}",
                reason="athena_results_failed",
                delivery=Delivery.RESPONDED,
                data_scanned_bytes=scanned,
                execution_id=execution_id,
            ) from exc
        return IndexQueryResult(
            execution_id=execution_id, columns=columns, rows=rows, data_scanned_bytes=scanned
        )


# --------------------------------------------------------------------------- #
# Archived records
# --------------------------------------------------------------------------- #


class RangeTransport(Protocol):
    @property
    def retrieval_mode(self) -> RetrievalMode: ...

    def get_range(self, url: str, *, address: str, offset: int, length: int) -> FetchedResponse:
        """GET exactly bytes ``offset`` .. ``offset + length - 1`` of ``url``, from ``address``."""
        ...


class ArchiveRangeTransport:
    """HTTPS range requests to Common Crawl's data host, from the checked address.

    The host is pinned (:data:`ARCHIVE_HOST`); the request carries the operator's
    contact in its user agent, asks for no compression and for one byte range,
    and reads at most ``length + 1`` bytes (so a server that ignored the range is
    seen, not read). Requests are made one at a time, at least ``min_interval_s``
    apart.
    """

    def __init__(
        self,
        *,
        contact: str,
        wire: HttpsWire | None = None,
        min_interval_s: float = 1.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if min_interval_s < 0:
            raise ValueError("the interval between requests is not negative")
        self.user_agent = public_user_agent(contact)
        self._wire = wire or UrllibWire()
        self._min_interval_s = min_interval_s
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: float | None = None

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get_range(self, url: str, *, address: str, offset: int, length: int) -> FetchedResponse:
        host = check_url(url)
        if host != ARCHIVE_HOST or not url.startswith("https://"):
            raise FetchRefused(
                f"archived records are read only from {ARCHIVE_HOST}", reason="host_scope"
            )
        check_address(address)
        if offset < 0 or length <= 0:
            raise ValueError("a range is a non-negative offset and a positive length")
        target = url[len(f"https://{host}") :] or "/"
        with self._lock:
            if self._last is not None:
                wait = self._last + self._min_interval_s - self._monotonic()
                if wait > 0:
                    self._sleep(wait)
            try:
                return self._wire.get(
                    address=address,
                    host=host,
                    target=target,
                    headers={
                        "Host": host,
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "identity",
                        "Range": f"bytes={offset}-{offset + length - 1}",
                    },
                    max_bytes=length,
                )
            finally:
                self._last = self._monotonic()


class ArchiveFetcher:
    """One archived capture, from the index row that names it, as a snapshot."""

    def __init__(
        self,
        *,
        transport: RangeTransport,
        resolver: Resolver,
        adapter_id: str,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._transport = transport
        self._resolver = resolver
        self.adapter_id = adapter_id
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return self._transport.retrieval_mode

    def fetch(self, row: IndexRow) -> FetchedPage:
        """The record ``row`` names, read and checked. Raises FetchRefused or ToolCallFailed."""
        url = archive_url(row)
        host = check_url(url)
        addresses = self._resolver.resolve(host)
        check_resolution(host, addresses)
        response = self._transport.get_range(
            url,
            address=addresses[0],
            offset=row.warc_record_offset,
            length=row.warc_record_length,
        )
        if response.status == 200:
            raise FetchRefused("the server ignored the byte range", reason="range_ignored")
        if response.status != 206:
            raise ToolCallFailed(
                f"HTTP {response.status} for {url}",
                reason=f"http_{response.status}",
                delivery=Delivery.RESPONDED,
            )
        last = row.warc_record_offset + row.warc_record_length - 1
        headers = {k.lower(): v for k, v in response.headers.items()}
        answered = _CONTENT_RANGE.match(headers.get("content-range", "").strip())
        if answered is None or (int(answered[1]), int(answered[2])) != (
            row.warc_record_offset,
            last,
        ):
            raise FetchRefused("the server answered another range", reason="range_mismatch")
        if response.truncated or len(response.body) != row.warc_record_length:
            raise FetchRefused(
                "the range is not the record's length", reason="archive_record_truncated"
            )
        record = parse_response_record(inflate_member(response.body))
        if record.target_uri != row.url:
            raise FetchRefused(
                "the record is of another URL than its index row", reason="archive_record_mismatch"
            )
        if not 200 <= record.http_status < 300:
            raise FetchRefused(
                f"the archived response is HTTP {record.http_status}", reason="archive_not_a_page"
            )
        if len(record.body) > MAX_BODY_BYTES:
            raise FetchRefused(
                f"the archived page is larger than {MAX_BODY_BYTES} bytes", reason="body_too_large"
            )
        capture = ArchivedCapture(
            archive="common_crawl",
            crawl=row.crawl,
            captured_at=record.captured_at,
            target_uri=record.target_uri,
            warc_filename=row.warc_filename,
            warc_record_offset=row.warc_record_offset,
            warc_record_length=row.warc_record_length,
            warc_record_id=record.record_id[:200],
            payload_digest=record.payload_digest[:200] if record.payload_digest else None,
            payload_truncated=record.truncated[:100] if record.truncated else None,
        )
        return page_snapshot(
            url=row.url,
            final_url=row.url,
            redirects=(),
            http_status=record.http_status,
            content_type=record.http_headers.get("content-type", ""),
            body=record.body,
            request_id=response.provider_request_id,
            adapter_id=self.adapter_id,
            retrieval_mode=self.retrieval_mode,
            retrieved_at=self._clock(),
            archive=capture,
        )


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

_KEY: Final = "AIA_DEEP_RESEARCH_COMMON_CRAWL_"
_KEYS: Final = (
    "WORKGROUP",
    "DATABASE",
    "TABLE",
    "MAX_SCAN_BYTES",
    "USD_PER_TB_SCANNED",
    "MIN_BILLED_BYTES",
    "BILLING_INCREMENT_BYTES",
    "PRICES_AS_OF",
)
#: Athena refuses a workgroup cutoff below 10 MB (service model ``BytesScannedCutoffValue``).
MIN_SCAN_CUTOFF_BYTES: Final = 10_000_000


@dataclass(frozen=True, slots=True)
class CommonCrawlSettings:
    """The Common Crawl route's configuration. Every value is required; none has a default.

    ``max_scan_bytes`` must equal the workgroup's enforced bytes-scanned cutoff:
    it is the most one query may scan, so its cost is the reservation each query
    holds. The price is dated (``prices_as_of``), as every paid route's is.
    """

    workgroup: str
    table: IndexTable
    max_scan_bytes: int
    pricing: AthenaPricing
    prices_as_of: date

    def __post_init__(self) -> None:
        if self.max_scan_bytes < MIN_SCAN_CUTOFF_BYTES:
            raise ValueError(f"the scan cutoff is at least {MIN_SCAN_CUTOFF_BYTES} bytes")

    @property
    def reservation_usd(self) -> float:
        """What one query may cost: its cutoff, billed."""
        return self.pricing.cost_usd(self.max_scan_bytes)


def common_crawl_settings(environ: Mapping[str, str]) -> CommonCrawlSettings:
    """Read ``AIA_DEEP_RESEARCH_COMMON_CRAWL_*``; a missing or invalid key names itself.

    Not called by any composition yet (plan chunk 23 wires it).
    """
    values: dict[str, str] = {}
    for key in _KEYS:
        raw = environ.get(_KEY + key, "").strip()
        if not raw:
            raise ValueError(f"{_KEY + key} is required")
        values[key] = raw

    def integer(key: str) -> int:
        if not values[key].isdigit():
            raise ValueError(f"{_KEY + key} is a whole number of bytes")
        return int(values[key])

    try:
        price = float(values["USD_PER_TB_SCANNED"])
    except ValueError as exc:
        raise ValueError(f"{_KEY}USD_PER_TB_SCANNED is a number") from exc
    if not math.isfinite(price):
        raise ValueError(f"{_KEY}USD_PER_TB_SCANNED is a finite number")
    try:
        as_of = date.fromisoformat(values["PRICES_AS_OF"])
    except ValueError as exc:
        raise ValueError(f"{_KEY}PRICES_AS_OF is a date (YYYY-MM-DD)") from exc
    return CommonCrawlSettings(
        workgroup=values["WORKGROUP"],
        table=IndexTable(database=values["DATABASE"], table=values["TABLE"]),
        max_scan_bytes=integer("MAX_SCAN_BYTES"),
        pricing=AthenaPricing(
            usd_per_tb_scanned=price,
            minimum_billed_bytes=integer("MIN_BILLED_BYTES"),
            billing_increment_bytes=integer("BILLING_INCREMENT_BYTES"),
        ),
        prices_as_of=as_of,
    )


# --------------------------------------------------------------------------- #
# Recorded doubles
# --------------------------------------------------------------------------- #


def _statement_key(statement: str) -> str:
    return " ".join(statement.split())


@dataclass(slots=True)
class RecordedUrlIndex:
    """Replays captured index answers by statement; an unrecorded statement has no rows.

    An exchange is ``{"columns": [...], "rows": [[...]], "scanned": int}`` or a
    failure ``{"fail": reason, "delivery": "RESPONDED" | "UNKNOWN", "scanned": int|None}``.
    """

    table: IndexTable
    exchanges: Mapping[str, Mapping[str, Any]]
    adapter_id: str = "recorded-ccindex-v1"
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def run(self, statement: str, *, request_token: str, max_rows: int) -> IndexQueryResult:
        self.calls.append(statement)
        exchange = {_statement_key(k): v for k, v in self.exchanges.items()}.get(
            _statement_key(statement), {"columns": [], "rows": [], "scanned": 0}
        )
        if "fail" in exchange:
            raise IndexQueryFailed(
                "recorded: the query failed",
                reason=str(exchange["fail"]),
                delivery=Delivery(exchange.get("delivery", "RESPONDED")),
                data_scanned_bytes=exchange.get("scanned"),
            )
        rows: Sequence[Sequence[str | None]] = exchange.get("rows", [])
        return IndexQueryResult(
            execution_id=exchange.get("execution_id"),
            columns=tuple(exchange.get("columns", [])),
            rows=tuple(tuple(r) for r in rows)[:max_rows],
            data_scanned_bytes=exchange.get("scanned"),
        )


@dataclass(slots=True)
class RecordedArchiveTransport:
    """Serves byte ranges of captured archive files by URL; an unrecorded file is a 404."""

    files: Mapping[str, bytes]
    calls: list[tuple[str, int, int]] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def get_range(self, url: str, *, address: str, offset: int, length: int) -> FetchedResponse:
        self.calls.append((url, offset, length))
        data = self.files.get(url)
        if data is None:
            return FetchedResponse(status=404, headers={}, body=b"", truncated=False)
        part = data[offset : offset + length]
        return FetchedResponse(
            status=206,
            headers={"content-range": f"bytes {offset}-{offset + len(part) - 1}/{len(data)}"},
            body=part,
            truncated=False,
        )
