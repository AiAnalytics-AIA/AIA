"""ČSÚ DataStat: a predefined selection (``výběr``) as a table. Registered by nothing yet.

The interface, as recorded in ``docs/architecture/deep-research-connectors.md``
(2026-10-05): DataStat's data API at ``https://data.csu.gov.cz/api/dotaz/v1``
answers ``GET /data/vybery/{selection code}`` with the selection's data in
JSON-stat. That record is **unverified** -- the official page was not reachable
from where it was written -- so this connector holds the answer to the format and
refuses anything else (``response_contract``) rather than read it loosely. Chunk 23
captures a real answer before any composition names this connector.

What it sends is fixed by code: one GET to one host, the selection code in the
path, nothing else. Filters and a period are applied to the answer by category
code (:mod:`.jsonstat`), never written into the request. No key, no cookie, no
redirect followed.

The licence is not stamped: the terms ČSÚ publishes for its data were seen only
second-hand (the connectors doc), so a result says ``licence: None`` -- "not stated
by the provider" -- until the terms are verified and recorded.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final
from urllib.parse import quote

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.tooling import ToolKind
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result
from .jsonstat import jsonstat_table
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = ["DATASTAT_CONNECTOR_ID", "DATASTAT_HOST", "DataStatConnector"]

DATASTAT_CONNECTOR_ID: Final = "csu-datastat-1"
DATASTAT_HOST: Final = "data.csu.gov.cz"
DATASTAT_DATA_API: Final = f"https://{DATASTAT_HOST}/api/dotaz/v1"
DATASTAT_PUBLISHER: Final = "Český statistický úřad"
#: Unverified (connectors doc): None until ČSÚ's terms are read first-hand and recorded.
DATASTAT_LICENCE: Final[str | None] = None
DATASTAT_MAX_BYTES: Final = 5_000_000
#: A selection code as this connector will put it in a path.
_SELECTION: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class DataStatConnector:
    """One predefined DataStat selection per query, read as JSON-stat 2.0."""

    tool_kind: Final = ToolKind.DATASET_QUERY
    connector_id: Final = DATASTAT_CONNECTOR_ID

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = HostScopedClient(
            host=DATASTAT_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json",),
            max_bytes=DATASTAT_MAX_BYTES,
        )
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The one URL a query becomes, or a refusal before anything is sent."""
        if query.connector_id != self.connector_id:
            raise ToolCallFailed(
                "the query is for another connector",
                reason="connector_mismatch",
                delivery=Delivery.NOT_SENT,
            )
        if _SELECTION.fullmatch(query.dataset_id) is None:
            raise ToolCallFailed(
                "a DataStat selection code is letters, digits, _ and -",
                reason="dataset_id_invalid",
                delivery=Delivery.NOT_SENT,
            )
        return f"{DATASTAT_DATA_API}/data/vybery/{quote(query.dataset_id, safe='')}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(url)
        fields = jsonstat_table(response.body, query=query)
        result = build_result(
            **fields,
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            publisher=DATASTAT_PUBLISHER,
            licence=DATASTAT_LICENCE,
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
