"""Public dataset connectors: the seam under the retrieval gate, and its recorded double.

Plan ``deep-research-web-search.md`` § 5.3 (the ``dataset`` tool) and § 7 rung 4. A
connector answers one :class:`~aia_core.domain.deep_research.datasets.DatasetQuery`
from one publisher's data interface (ČSÚ DataStat, the national catalogue NKOD, and
later Eurostat, OpenAlex …) with a table. Like a search adapter it translates and
enforces, and never retries, reroutes or substitutes:

* :class:`DatasetConnector` -- ``query`` returns a :class:`DatasetResponse` or raises
  :class:`~aia_core.infrastructure.web_retrieval.ToolCallFailed` with a
  :class:`~aia_core.domain.ai_contracts.Delivery`, and nothing else, so the gate can
  always journal what happened: ``NOT_SENT`` (refused before a byte left),
  ``RESPONDED`` (the provider answered, unusably), ``UNKNOWN`` (it may have been
  served; never resent).
* :class:`HostScopedClient` -- the one way a live connector reaches its host: the
  host fixed at construction, every address checked, a pinned transport (no proxy,
  no redirect), a byte cap, a declared content type, fixed error text.
* :func:`dataset_snapshot` -- a response as a content-addressed
  :class:`~aia_core.domain.deep_research.contracts.SourceSnapshot` whose text is the
  table's rendering, so a cell is grounded like any quote, and exactly by its locator.
* :class:`RecordedDatasetConnector` -- replays captured answers; a test double, never
  a fallback (it can only say ``RECORDED``, and ``make layer_check`` keeps it out of
  every composition but the recorded one).

The connectors themselves live in their own modules (``dataset_datastat``,
``dataset_nkod``) and are registered by no composition yet (plan chunk 23).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode, SourceSnapshot
from ..domain.deep_research.datasets import DATASET_MEDIA_TYPE, DatasetQuery, DatasetResult
from ..domain.deep_research.grounding import detect_instructions
from ..domain.deep_research.web import FetchRefused, check_resolution, check_url
from .web_retrieval import FetchedResponse, FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "DatasetConnector",
    "DatasetResponse",
    "HostScopedClient",
    "RecordedDatasetConnector",
    "dataset_snapshot",
]


@dataclass(frozen=True, slots=True)
class DatasetResponse:
    """One connector answer: the table, and what the provider's bytes were."""

    result: DatasetResult
    #: SHA256 and length of the provider's response body, as received.
    raw_sha256: str
    raw_bytes: int
    http_status: int
    provider_request_id: str | None
    #: The provider's own unit of charge; the public interfaces here charge none.
    credits: int = 0


class DatasetConnector(Protocol):
    """One publisher's data interface, over one host. Translates; never retries or reroutes."""

    @property
    def connector_id(self) -> str: ...

    @property
    def retrieval_mode(self) -> RetrievalMode:
        """``RECORDED`` for a replay, ``LIVE`` for the provider. Fixed by the connector."""
        ...

    def query(self, query: DatasetQuery) -> DatasetResponse:
        """Answer one query as a table, or raise :class:`ToolCallFailed` -- nothing else."""
        ...


def dataset_snapshot(response: DatasetResponse, *, retrieval_mode: RetrievalMode) -> SourceSnapshot:
    """A connector's answer as a snapshot: the rendering is the text, the table rides along.

    Content-addressed like a page: the same table is the same snapshot id however
    often it is asked for, and a revised figure is a new one.
    """
    result = response.result
    text = result.render()
    text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceSnapshot(
        snapshot_id="SNP-" + text_sha[:24],
        url=result.source_url,
        canonical_url=result.source_url,
        final_url=result.source_url,
        redirects=(),
        title=f"{result.title} [{result.dataset_id}]"[:500],
        retrieved_at=result.retrieved_at,
        http_status=response.http_status,
        content_type=DATASET_MEDIA_TYPE,
        raw_sha256=response.raw_sha256,
        raw_bytes=response.raw_bytes,
        text=text,
        text_sha256=text_sha,
        truncated=False,
        adapter=result.connector_id,
        request_id=response.provider_request_id,
        retrieval_mode=retrieval_mode,
        instructions_detected=detect_instructions(text),
        dataset=result,
    )


def contract_failure(what: str) -> ToolCallFailed:
    """The provider answered with something this connector does not read. Fixed text."""
    return ToolCallFailed(
        f"the provider's answer is not {what}",
        reason="response_contract",
        delivery=Delivery.RESPONDED,
    )


def build_result(**fields: Any) -> DatasetResult:
    """A :class:`DatasetResult` from a parsed answer, or the contract failure it is."""
    try:
        return DatasetResult.model_validate(fields)
    except ValidationError as exc:
        raise contract_failure("a table this contract holds") from exc


class HostScopedClient:
    """GET from one host only, over a pinned transport, mapping every failure to a delivery."""

    def __init__(
        self,
        *,
        host: str,
        transport: FetchTransport,
        resolver: Resolver,
        media_types: Collection[str],
        max_bytes: int,
    ) -> None:
        if transport.retrieval_mode is not RetrievalMode.LIVE:
            raise ValueError("a live connector requires a live transport")
        if max_bytes <= 0 or not media_types:
            raise ValueError("a client declares its byte cap and the types it reads")
        self.host = host
        self._transport = transport
        self._resolver = resolver
        self._media = frozenset(m.lower() for m in media_types)
        self._max_bytes = max_bytes

    def get(self, url: str) -> FetchedResponse:
        """The answer to one GET, or :class:`ToolCallFailed`. No redirect is followed."""
        try:
            if check_url(url) != self.host or not url.startswith("https://"):
                raise FetchRefused("outside the connector's host", reason="host_scope")
            addresses = self._resolver.resolve(self.host)
            check_resolution(self.host, addresses)
        except FetchRefused as exc:
            raise ToolCallFailed(
                "the request was refused before it was sent",
                reason=f"refused_{exc.reason}",
                delivery=Delivery.NOT_SENT,
            ) from exc
        try:
            response = self._transport.get(url, address=addresses[0], max_bytes=self._max_bytes)
        except ToolCallFailed:
            raise
        except FetchRefused as exc:
            raise ToolCallFailed(
                "the request was refused before it was sent",
                reason=f"refused_{exc.reason}",
                delivery=Delivery.NOT_SENT,
            ) from exc
        except Exception as exc:
            # Anything else after the transport took the request may have been served.
            raise ToolCallFailed(
                "the request failed in transport",
                reason="transport_error",
                delivery=Delivery.UNKNOWN,
            ) from exc
        if 300 <= response.status < 400:
            raise ToolCallFailed(
                "the provider redirected; redirects are not followed",
                reason="redirect_refused",
                delivery=Delivery.RESPONDED,
            )
        if not 200 <= response.status < 300:
            raise ToolCallFailed(
                f"the provider answered HTTP {response.status}",
                reason=f"http_{response.status}",
                delivery=Delivery.RESPONDED,
            )
        if response.truncated:
            raise ToolCallFailed(
                f"the answer is larger than {self._max_bytes} bytes",
                reason="body_too_large",
                delivery=Delivery.RESPONDED,
            )
        headers = {k.lower(): v for k, v in response.headers.items()}
        media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media not in self._media:
            raise ToolCallFailed(
                "the answer is not of a type this connector reads",
                reason="content_type",
                delivery=Delivery.RESPONDED,
            )
        return response


# --------------------------------------------------------------------------- #
# Recorded double
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RecordedDatasetConnector:
    """Replays captured answers by query text; an unrecorded query is a provider 404.

    An exchange is ``{"result": <DatasetResult fields without query/retrieved_at>,
    "raw": "<body>"}``, or a failure: ``{"fail": "not_sent" | "known" | "uncertain"}``.
    """

    connector_id: str
    exchanges: Mapping[str, Mapping[str, Any]]
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def query(self, query: DatasetQuery) -> DatasetResponse:
        self.calls.append(query.text())
        exchange = self.exchanges.get(query.text())
        if exchange is None:
            raise ToolCallFailed(
                "recorded: no such dataset", reason="http_404", delivery=Delivery.RESPONDED
            )
        failure = exchange.get("fail")
        if failure == "not_sent":
            raise ToolCallFailed(
                "recorded: refused", reason="refused_recorded", delivery=Delivery.NOT_SENT
            )
        if failure == "uncertain":
            raise ToolCallFailed("recorded: no answer", reason="lost", delivery=Delivery.UNKNOWN)
        if failure == "known":
            raise ToolCallFailed(
                "recorded: provider error", reason="provider_error", delivery=Delivery.RESPONDED
            )
        raw = str(exchange.get("raw", "")).encode("utf-8")
        result = build_result(
            **{
                **exchange["result"],
                "connector_id": self.connector_id,
                "dataset_id": query.dataset_id,
                "query": query,
                "retrieved_at": self.clock(),
            }
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(raw).hexdigest(),
            raw_bytes=len(raw),
            http_status=200,
            provider_request_id=exchange.get("request_id"),
        )
