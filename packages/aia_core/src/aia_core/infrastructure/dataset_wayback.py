"""The Wayback Machine's CDX index: the captures of one URL, as a table. Registered by nothing yet.

The interface, as recorded in ``docs/architecture/deep-research-connectors.md``
(2026-10-06, read first-hand from the Internet Archive's own CDX server README):
``GET /cdx/search/cdx?url=<url>`` on ``web.archive.org`` answers the captures of
that exact URL (``matchType=exact`` is the default); ``output=json`` answers a JSON
array whose first row names the fields; ``fl=`` picks the fields; ``from=`` and
``to=`` bound the timestamps (1 to 14 digits, inclusive); ``collapse=digest`` drops
adjacent captures with the same content; ``limit=`` caps the rows; the answer is
gzip-encoded unless ``gzip=false``.

This connector is the ``archive`` tool's lookup (plan § 5.3, § 7 rung 9). It is
asked only through :meth:`RetrievalGate.archive`, which requires an
:class:`~aia_core.domain.deep_research.archive.ArchivePermit` for the same URL:
the live page first, the archive only for a dead or moved page. Its tool kind is
``archive_lookup``, so it cannot be given to the gate as a dataset connector.

What it sends is fixed by code: one GET to ``web.archive.org`` only, the page URL
(a public ``http``/``https`` URL under AIA's own fetch rules) and, when the query
has a period, ``from`` and ``to`` both set to it. No key, no cookie, no redirect.
At most :data:`WAYBACK_LIMIT` rows are asked for; an answer that reaches it is
refused (``dataset_too_large``), never read as if it were every capture.

The table: one row per capture, in the index's order, with the six fields asked for
as published, and the replay URL ``https://web.archive.org/web/<timestamp>/<original>``
-- a form **unverified** here (the README shows only the calendar's
``/web/*/<url>``). Fetching an archived page is not done here: no public-web fetch
exists on this branch's base (plan chunk 5); :func:`nearest_capture` names the
capture a later fetch would take.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Final
from urllib.parse import urlencode

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery, DatasetResult
from ..domain.deep_research.tooling import ToolKind
from ..domain.deep_research.web import FetchRefused, check_url
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result, contract_failure
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "WAYBACK_CONNECTOR_ID",
    "WAYBACK_FIELDS",
    "WAYBACK_HOST",
    "WaybackCdxConnector",
    "capture_url",
    "nearest_capture",
]

WAYBACK_CONNECTOR_ID: Final = "wayback-cdx-1"
WAYBACK_HOST: Final = "web.archive.org"
WAYBACK_CDX: Final = f"https://{WAYBACK_HOST}/cdx/search/cdx"
WAYBACK_PUBLISHER: Final = "Internet Archive (Wayback Machine CDX index)"
WAYBACK_MAX_BYTES: Final = 1_000_000
#: Rows asked for; an answer that reaches it is refused, never cut short.
WAYBACK_LIMIT: Final = 200
#: The fields asked for, in order; the answer's header row must name exactly these.
WAYBACK_FIELDS: Final = ("timestamp", "original", "mimetype", "statuscode", "digest", "length")
_LABELS: Final = {
    "timestamp": "Timestamp (timestamp)",
    "original": "Original URL (original)",
    "mimetype": "MIME type (mimetype)",
    "statuscode": "HTTP status (statuscode)",
    "digest": "Content digest (digest)",
    "length": "Length (length)",
    "archived_url": "Replay URL",
}
#: A period as the CDX takes it: 4 to 14 digits, whole date parts.
_PERIOD: Final = re.compile(r"^[0-9]{4}(?:[0-9]{2}){0,5}$")
_TIMESTAMP: Final = re.compile(r"^[0-9]{14}$")
_STATUS: Final = re.compile(r"^(?:[0-9]{3}|-)$")
_DIGEST: Final = re.compile(r"^[A-Za-z0-9+/=:_-]{1,128}$")
_LENGTH: Final = re.compile(r"^(?:[0-9]{1,15}|-)$")


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


def _captures(body: bytes) -> list[list[str]]:
    """The capture rows of a CDX JSON answer, header checked and removed; refused otherwise."""
    try:
        doc = json.loads(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise contract_failure("JSON") from exc
    if not isinstance(doc, list) or not all(isinstance(row, list) for row in doc):
        raise contract_failure("a CDX JSON array")
    if not doc:
        return []  # no capture at all (unverified shape: see the connectors doc)
    header, rows = doc[0], doc[1:]
    if tuple(header) != WAYBACK_FIELDS:
        raise contract_failure("a CDX answer with the fields asked for")
    for row in rows:
        if len(row) != len(WAYBACK_FIELDS) or not all(isinstance(v, str) for v in row):
            raise contract_failure("a CDX answer with one text value per field")
        timestamp, original, mimetype, status, digest, length = row
        if (
            _TIMESTAMP.fullmatch(timestamp) is None
            or _STATUS.fullmatch(status) is None
            or _DIGEST.fullmatch(digest) is None
            or _LENGTH.fullmatch(length) is None
            or not _valid_instant(timestamp)
            or not mimetype
            or not original
            or any(ch.isspace() for ch in original + mimetype)
        ):
            raise contract_failure("a CDX answer whose fields are well formed")
    return rows


def _valid_instant(timestamp: str) -> bool:
    try:
        _instant(timestamp)
    except ValueError:
        return False
    return True


def capture_url(timestamp: str, original: str) -> str:
    """The replay URL of one capture (form unverified; see the module docstring)."""
    return f"https://{WAYBACK_HOST}/web/{timestamp}/{original}"


class WaybackCdxConnector:
    """The captures of one URL per query, from the Wayback Machine's CDX index."""

    connector_id: Final = WAYBACK_CONNECTOR_ID
    tool_kind: Final = ToolKind.ARCHIVE_LOOKUP

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = HostScopedClient(
            host=WAYBACK_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json", "text/plain"),
            max_bytes=WAYBACK_MAX_BYTES,
        )
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The one URL a query becomes, or a refusal before anything is sent."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if query.filters:
            raise _not_sent("a capture lookup takes no filter", "filters_unsupported")
        page = query.dataset_id
        try:
            check_url(page)
        except FetchRefused as exc:
            raise _not_sent("the page is a public http(s) URL", "dataset_id_invalid") from exc
        params: list[tuple[str, str]] = [
            ("url", page),
            ("output", "json"),
            ("gzip", "false"),
            ("fl", ",".join(WAYBACK_FIELDS)),
            ("collapse", "digest"),
            ("limit", str(WAYBACK_LIMIT)),
        ]
        if query.period is not None:
            if _PERIOD.fullmatch(query.period) is None:
                raise _not_sent("a capture period is 4 to 14 digits", "period_invalid")
            params += [("from", query.period), ("to", query.period)]
        return f"{WAYBACK_CDX}?{urlencode(params)}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(url)
        rows = _captures(response.body)
        if len(rows) >= WAYBACK_LIMIT:
            raise ToolCallFailed(
                f"the index answered {WAYBACK_LIMIT} or more captures",
                reason="dataset_too_large",
                delivery=Delivery.RESPONDED,
            )
        notes = [] if rows else ["The index holds no capture of this URL for the query asked."]
        result = build_result(
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            title=f"Wayback Machine captures of {query.dataset_id}"[:500],
            publisher=WAYBACK_PUBLISHER,
            licence=None,
            source_url=url,
            retrieved_at=self._clock(),
            notes=notes,
            columns=[{"key": k, "label": _LABELS[k]} for k in (*WAYBACK_FIELDS, "archived_url")],
            rows=[
                {
                    "key": f"c{i}",
                    "label": f"{i}. capture {row[0]}",
                    "values": [*row, capture_url(row[0], row[1])],
                }
                for i, row in enumerate(rows, 1)
            ],
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
        )


def _instant(timestamp: str) -> datetime:
    """A 14-digit CDX timestamp as a UTC instant; ValueError for an impossible date."""
    return datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)


def _padded(period: str) -> datetime:
    """A 4-to-14-digit period as the first second it names (``2023`` is 2023-01-01 00:00:00)."""
    if _PERIOD.fullmatch(period) is None:
        raise ValueError("a period is 4 to 14 digits")
    filler = "0101000000"  # month, day, hour, minute, second
    return _instant(period + filler[len(period) - 4 :])


def nearest_capture(result: DatasetResult, cited: str) -> str | None:
    """The row key of the HTTP 200 capture nearest ``cited`` (earlier on a tie), or None.

    Only a capture the archive itself recorded as a 200 answer is a copy of the page;
    a capture of a redirect or an error page is not.
    """
    if result.connector_id != WAYBACK_CONNECTOR_ID:
        raise ValueError("not a capture table")
    target = _padded(cited)
    index = {c.key: i for i, c in enumerate(result.columns)}
    best: tuple[float, datetime, str] | None = None
    for row in result.rows:
        values: Sequence[str | None] = row.values
        if values[index["statuscode"]] != "200":
            continue
        stamp = _instant(values[index["timestamp"]] or "")
        candidate = (abs((stamp - target).total_seconds()), stamp, row.key)
        if best is None or candidate < best:
            best = candidate
    return None if best is None else best[2]
