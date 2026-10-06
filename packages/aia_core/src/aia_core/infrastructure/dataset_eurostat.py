"""Eurostat: one dataset, filtered by dimension code, as a table. Registered by nothing yet.

The interface, as recorded in ``docs/architecture/deep-research-connectors.md``
(2026-10-06): Eurostat's dissemination "API Statistics" answers ``GET
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset code}``
in JSON-stat 2.0, with ``<DIMENSION>=<CODE>`` filters (one parameter per code, the
same dimension repeated for several), ``time=`` for a period, ``lang=`` for the
labels, and ``format=JSON``. Every one of those facts is **unverified** -- the
official pages were not reachable from where they were recorded -- so this
connector holds the answer to JSON-stat 2.0 and refuses anything else
(``response_contract``) rather than read it loosely.

What it sends is fixed by code: one GET to ``ec.europa.eu`` only, the dataset code
in the path, the query's filters and period as parameters in a deterministic
order, ``format=JSON`` and ``lang=EN``. No key, no cookie, no redirect followed.
The filters are sent (Eurostat's datasets are far larger than one table may be)
*and* checked again on the answer by :mod:`.jsonstat`: a category the answer does
not carry is a known failure, never a silently wider table.

Eurostat's documents carry no ``role`` (a third party's statement, unverified), so
the time dimension is named: ``time``, used only when the document declares none.
Its unit of measure is an ordinary dimension (``unit``), so it is a note or a part
of a row's label, never stamped on a cell as a guessed unit.

An answer of ``{"warning": {"status": 413, ...}}`` -- recorded as Eurostat's word
for "too large, treated asynchronously" -- is ``dataset_asynchronous``: the
provider answered, and there is no table. Nothing polls for it.

The licence is not stamped: Eurostat's reuse terms were seen only second-hand, so
a result says ``licence: None`` until they are read first-hand and recorded.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Final
from urllib.parse import quote, urlencode

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.tooling import ToolKind
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result
from .jsonstat import jsonstat_table
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "EUROSTAT_CONNECTOR_ID",
    "EUROSTAT_HOST",
    "EurostatConnector",
]

EUROSTAT_CONNECTOR_ID: Final = "eurostat-statistics-1"
EUROSTAT_HOST: Final = "ec.europa.eu"
EUROSTAT_DATA_API: Final = f"https://{EUROSTAT_HOST}/eurostat/api/dissemination/statistics/1.0/data"
EUROSTAT_PUBLISHER: Final = "Eurostat"
#: Unverified (connectors doc): None until Eurostat's reuse terms are read first-hand.
EUROSTAT_LICENCE: Final[str | None] = None
#: The labels' language; fixed, so the same query is always the same table.
EUROSTAT_LANGUAGE: Final = "EN"
#: The time dimension's id in Eurostat's documents (unverified; used only without a role).
EUROSTAT_TIME_DIMENSION: Final = "time"
EUROSTAT_MAX_BYTES: Final = 5_000_000
#: A dataset code as this connector will put it in a path (``nama_10_gdp``, ``ilc_li02``).
_DATASET_CODE: Final = re.compile(r"^[A-Za-z0-9_]{1,64}$")
#: A dimension and a category code as this connector will put them in a parameter.
_PARAM_CODE: Final = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_CATEGORY_CODE: Final = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
#: Parameters the connector writes itself; a filter may not name one.
_RESERVED: Final = frozenset(
    {"format", "lang", "time", "sinceTimePeriod", "untilTimePeriod", "lastTimePeriod", "geoLevel"}
)


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


class EurostatConnector:
    """One Eurostat dataset per query, filtered by code, read as JSON-stat 2.0."""

    connector_id: Final = EUROSTAT_CONNECTOR_ID
    tool_kind: Final = ToolKind.DATASET_QUERY

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = HostScopedClient(
            host=EUROSTAT_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json",),
            max_bytes=EUROSTAT_MAX_BYTES,
        )
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The one URL a query becomes, or a refusal before anything is sent."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if _DATASET_CODE.fullmatch(query.dataset_id) is None:
            raise _not_sent(
                "a Eurostat dataset code is letters, digits and _", "dataset_id_invalid"
            )
        params: list[tuple[str, str]] = [("format", "JSON"), ("lang", EUROSTAT_LANGUAGE)]
        for wanted in sorted(query.filters, key=lambda f: f.dimension):
            if _PARAM_CODE.fullmatch(wanted.dimension) is None or wanted.dimension in _RESERVED:
                raise _not_sent("a filter names a dimension by its code", "filter_invalid")
            if any(_CATEGORY_CODE.fullmatch(v) is None for v in wanted.values):
                raise _not_sent("a filter names categories by their codes", "filter_invalid")
            params += [(wanted.dimension, value) for value in wanted.values]
        if query.period is not None:
            params.append(("time", query.period))
        return f"{EUROSTAT_DATA_API}/{quote(query.dataset_id, safe='')}?{urlencode(params)}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(url)
        _refuse_warning(response.body)
        fields = jsonstat_table(response.body, query=query, time_dimension=EUROSTAT_TIME_DIMENSION)
        result = build_result(
            **fields,
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            publisher=EUROSTAT_PUBLISHER,
            licence=EUROSTAT_LICENCE,
            source_url=url,
            retrieved_at=self._clock(),
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
        )


def _refuse_warning(body: bytes) -> None:
    """Eurostat's "asynchronous" answer is a known failure; anything else goes on to the reader."""
    try:
        doc = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return  # the reader says what it is
    warning = doc.get("warning") if isinstance(doc, Mapping) else None
    if isinstance(warning, Mapping) and str(warning.get("status")) == "413":
        raise ToolCallFailed(
            "the provider would answer this query asynchronously",
            reason="dataset_asynchronous",
            delivery=Delivery.RESPONDED,
        )
