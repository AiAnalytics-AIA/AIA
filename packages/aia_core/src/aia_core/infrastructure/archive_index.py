"""What :class:`~aia_core.application.web_retrieval.RetrievalGate` asks of a URL index
and an archive fetcher: the protocols and the failure, no implementation.

The live implementations are in :mod:`.common_crawl` (Athena's index, the archive's
byte ranges) over the wires of :mod:`.web_retrieval_live`. The gate imports this
module, never those, so naming the gate does not load a network wire.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.common_crawl import IndexRow, IndexTable
from ..domain.deep_research.contracts import RetrievalMode
from .web_retrieval import FetchedPage, ToolCallFailed

__all__ = [
    "ArchiveRecordFetcher",
    "IndexQueryFailed",
    "IndexQueryResult",
    "UrlIndex",
]


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


class ArchiveRecordFetcher(Protocol):
    """One archived capture, from the index row that names it, as a snapshot."""

    @property
    def adapter_id(self) -> str: ...

    @property
    def retrieval_mode(self) -> RetrievalMode: ...

    def fetch(self, row: IndexRow) -> FetchedPage:
        """The record ``row`` names, read and checked. Raises FetchRefused or ToolCallFailed."""
        ...
