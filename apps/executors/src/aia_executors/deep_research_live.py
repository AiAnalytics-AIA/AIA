"""Public Czech Wikipedia retrieval for fictional Class C Deep Research.

The site is a bounded, free public source for the first live acceptance. Its
editorial status is provisional and all resulting evidence stays internal. This
composition does not approve arbitrary web search or client-data queries.
"""

from __future__ import annotations

from aia_core.application.web_retrieval import WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTable
from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.web_retrieval import WebFetcher
from aia_core.infrastructure.web_retrieval_live import (
    SEARCH_ID,
    PinnedHttpsTransport,
    SystemResolver,
    WikipediaSearch,
)

__all__ = ["wikipedia_retrieval"]

_FETCH_ID = "pinned-public-https-1"


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"wikipedia-public-{tool.value}",
            provider="wikimedia",
            zone=ResidencyZone.UNKNOWN,
            eu_processing_approved=False,
            excluded_from_training=False,
            retention_days=None,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=SEARCH_ID if tool is ToolKind.WEB_SEARCH else _FETCH_ID,
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=0.0,
    )


def wikipedia_retrieval() -> tuple[WebRetrieval, SourceTable]:
    """Build live, fee-free retrieval with a low-scoring provisional source class."""
    resolver = SystemResolver()
    transport = PinnedHttpsTransport()
    return (
        WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=WikipediaSearch(resolver=resolver, transport=transport),
            fetcher=WebFetcher(transport=transport, resolver=resolver, adapter_id=_FETCH_ID),
        ),
        SOURCE_TABLE_V1.extended(
            "aia-source-table-1+wikipedia-public-1",
            {"wikipedia.org": SourceClass.MEDIA},
        ),
    )
