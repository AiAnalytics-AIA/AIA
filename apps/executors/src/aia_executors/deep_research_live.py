"""Deep Research's live retrieval: Czech Wikipedia or Brave, any public host, the connectors.

What a deployment may compose, each Class C only. Every route here costs nothing per call
but Brave's search, which is priced and charged to the study (plan
``deep-research-web-search.md`` chunks 23c-23d) and needs its organization's sign-off
(chunk 44):

- **Wikipedia search** (``wikipedia_retrieval``): the bounded Czech Wikipedia search,
  and pages fetched from that one host. The first live acceptance's route.
- **The public web** (``public_retrieval``): the same search, with pages fetched from
  any public host (``PublicHttpsTransport``, chunk 5): every hop's address checked,
  ``robots.txt`` read and obeyed, crawl delay kept, one request at a time per host, an
  identifying user agent carrying the deployment's contact address. What the ladder
  and the investigator open beyond Wikipedia -- a cited table, a publisher's index, an
  open-access copy -- is reached this way.
- **Brave search** (``brave_retrieval``): Brave Web Search, priced per request, with pages
  fetched from any public host as above. Its key is a credential reference
  (``env:AIA_DEEP_RESEARCH_BRAVE_API_KEY``), read at each call and never stored.
- **The public dataset connectors** (``connector_accesses``, chunks 14-16): ČSÚ
  DataStat, the national open-data catalogue, Eurostat, OpenAlex, ARES and the Wayback
  CDX index, each pinned to its own host; and Crossref, which the merge asks whether a
  cited work was retracted (chunk 46).

Its editorial status is provisional and all resulting evidence stays internal. This
composition does not approve client-data queries: every route is approved for
``CLASS_C_INTERNAL`` alone, and the gate refuses any other class before it leaves.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

from aia_core.application.web_retrieval import DatasetAccess, WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTable
from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.dataset_ares import ARES_HOST, AresConnector
from aia_core.infrastructure.dataset_connectors import DatasetConnector
from aia_core.infrastructure.dataset_crossref import CROSSREF_HOST, CrossrefConnector
from aia_core.infrastructure.dataset_datastat import DATASTAT_HOST, DataStatConnector
from aia_core.infrastructure.dataset_eurostat import EUROSTAT_HOST, EurostatConnector
from aia_core.infrastructure.dataset_nkod import NKOD_HOST, NkodConnector
from aia_core.infrastructure.dataset_openalex import OPENALEX_HOST, OpenAlexConnector
from aia_core.infrastructure.dataset_wayback import WAYBACK_HOST, WaybackCdxConnector
from aia_core.infrastructure.host_pacing import HostPacer, PacedTransport
from aia_core.infrastructure.model_adapters.transport import CredentialSource
from aia_core.infrastructure.web_retrieval import FetchTransport, Resolver, WebFetcher
from aia_core.infrastructure.web_retrieval_brave import (
    BRAVE_CREDENTIAL_REF,
    BRAVE_SEARCH_ID,
    BraveHttpsTransport,
    BraveSearch,
)
from aia_core.infrastructure.web_retrieval_live import (
    SEARCH_ID,
    HostPinnedHttpsTransport,
    PinnedHttpsTransport,
    PublicHttpsTransport,
    SystemResolver,
    WikipediaSearch,
    public_user_agent,
)

__all__ = [
    "BRAVE_ROUTE_ID",
    "CONNECTORS",
    "UNAVAILABLE_CONNECTORS",
    "brave_retrieval",
    "connector_accesses",
    "public_retrieval",
    "wikipedia_retrieval",
]

#: Brave's search route: priced, outside the EU (plan § 10), Class C only.
BRAVE_ROUTE_ID: Final = "brave-web-search"

_FETCH_ID = "pinned-public-https-1"
#: The public fetch's adapter: any public host, robots.txt obeyed (plan chunk 5).
PUBLIC_FETCH_ID: Final = "public-https-1"
#: The pace a shared pacer keeps for a route's host: the public transport's minimum
#: interval (chunk 5). Unpaced before fan-out: one process asked it serially.
PACED_INTERVAL_S = 1.0


def _provider_route(
    route_id: str, provider: str, zone: ResidencyZone = ResidencyZone.UNKNOWN
) -> ProviderRoute:
    """A free public route: nothing about its processing is approved, Class C rides it."""
    return ProviderRoute(
        route_id=route_id,
        provider=provider,
        zone=zone,
        eu_processing_approved=False,
        excluded_from_training=False,
        retention_days=None,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=_provider_route(f"wikipedia-public-{tool.value}", "wikimedia"),
        tool=tool,
        adapter_id=SEARCH_ID if tool is ToolKind.WEB_SEARCH else _FETCH_ID,
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=0.0,
    )


def _table() -> SourceTable:
    return SOURCE_TABLE_V1.extended(
        "aia-source-table-1+wikipedia-public-1",
        {"wikipedia.org": SourceClass.MEDIA},
    )


def _paced(transport: FetchTransport, pacer: HostPacer | None) -> FetchTransport:
    if pacer is None:
        return transport
    return PacedTransport(transport, pacer=pacer, interval_s=PACED_INTERVAL_S)


def wikipedia_retrieval(pacer: HostPacer | None = None) -> tuple[WebRetrieval, SourceTable]:
    """Build live, fee-free retrieval with a low-scoring provisional source class.

    ``pacer``: the deployment's shared host pacer (fan-out, chunk 21), which every
    search and page request then waits for; ``None`` sends as before.
    """
    resolver = SystemResolver()
    transport = _paced(PinnedHttpsTransport(), pacer)
    return (
        WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=_route(ToolKind.WEB_FETCH),
            search=WikipediaSearch(resolver=resolver, transport=transport),
            fetcher=WebFetcher(transport=transport, resolver=resolver, adapter_id=_FETCH_ID),
        ),
        _table(),
    )


def public_retrieval(
    contact: str, pacer: HostPacer | None = None
) -> tuple[WebRetrieval, SourceTable]:
    """Wikipedia's search, with pages fetched from any public host (plan chunk 23b).

    ``contact`` is the address every request's user agent carries (one plain e-mail
    address; anything else raises ``ValueError``). One transport serves the process,
    so a host's robots.txt is read once in its 24-hour lifetime and its pace is kept
    across every track; with ``pacer`` (fan-out) across every worker too.
    """
    public_user_agent(contact)
    resolver = SystemResolver()
    search = _paced(PinnedHttpsTransport(), pacer)
    pages = PublicHttpsTransport(contact=contact, resolver=resolver, pacer=pacer)
    return (
        WebRetrieval(
            search_route=_route(ToolKind.WEB_SEARCH),
            fetch_route=ToolRoute(
                route=_provider_route("public-web-fetch", "public-web"),
                tool=ToolKind.WEB_FETCH,
                adapter_id=PUBLIC_FETCH_ID,
                retrieval_mode=RetrievalMode.LIVE,
                price_usd_per_call=0.0,
            ),
            search=WikipediaSearch(resolver=resolver, transport=search),
            fetcher=WebFetcher(transport=pages, resolver=resolver, adapter_id=PUBLIC_FETCH_ID),
        ),
        _table(),
    )


def brave_retrieval(
    contact: str,
    *,
    price_usd_per_call: float,
    credentials: CredentialSource,
    pacer: HostPacer | None = None,
) -> tuple[WebRetrieval, SourceTable]:
    """Brave Web Search, with pages fetched from any public host (plan chunk 23d).

    ``price_usd_per_call`` is the deployment's dated price (per 1,000 requests / 1,000):
    every search reserves it against the study before it leaves (chunk 23c), and a route
    with a price needs its organization's sign-off (chunk 44). ``credentials`` resolves the
    key's reference at each call; nothing here reads it. The search goes to Brave's one
    host over its own pinned transport; pages as :func:`public_retrieval`'s.
    """
    if not price_usd_per_call > 0:
        raise ValueError("Brave's search is priced: a price above zero is required")
    public_user_agent(contact)
    resolver = SystemResolver()
    pages = PublicHttpsTransport(contact=contact, resolver=resolver, pacer=pacer)
    return (
        WebRetrieval(
            search_route=ToolRoute(
                route=_provider_route(BRAVE_ROUTE_ID, "brave", ResidencyZone.NON_EU),
                tool=ToolKind.WEB_SEARCH,
                adapter_id=BRAVE_SEARCH_ID,
                retrieval_mode=RetrievalMode.LIVE,
                price_usd_per_call=price_usd_per_call,
            ),
            fetch_route=ToolRoute(
                route=_provider_route("public-web-fetch", "public-web"),
                tool=ToolKind.WEB_FETCH,
                adapter_id=PUBLIC_FETCH_ID,
                retrieval_mode=RetrievalMode.LIVE,
                price_usd_per_call=0.0,
            ),
            search=BraveSearch(
                credentials=credentials,
                credential_ref=BRAVE_CREDENTIAL_REF,
                resolver=resolver,
                transport=BraveHttpsTransport(),
            ),
            fetcher=WebFetcher(transport=pages, resolver=resolver, adapter_id=PUBLIC_FETCH_ID),
        ),
        _table(),
    )


# --------------------------------------------------------------------------- #
# The public dataset connectors
# --------------------------------------------------------------------------- #

_Build = Callable[[FetchTransport, Resolver, str], DatasetConnector]


def _connector_specs() -> dict[str, tuple[str, str, ResidencyZone, _Build]]:
    """name -> (host, accept, where its operator processes a request, build)."""
    return {
        "datastat": (
            DATASTAT_HOST,
            "application/json",
            ResidencyZone.EU,
            lambda t, r, _c: DataStatConnector(transport=t, resolver=r),
        ),
        "nkod": (
            NKOD_HOST,
            "application/sparql-results+json, application/json",
            ResidencyZone.EU,
            lambda t, r, _c: NkodConnector(transport=t, resolver=r),
        ),
        "eurostat": (
            EUROSTAT_HOST,
            "application/json",
            ResidencyZone.EU,
            lambda t, r, _c: EurostatConnector(transport=t, resolver=r),
        ),
        "ares": (
            ARES_HOST,
            "application/json",
            ResidencyZone.EU,
            lambda t, r, _c: AresConnector(transport=t, resolver=r),
        ),
        "openalex": (
            OPENALEX_HOST,
            "application/json",
            ResidencyZone.NON_EU,
            lambda t, r, c: OpenAlexConnector(transport=t, resolver=r, mailto=c),
        ),
        "crossref": (
            CROSSREF_HOST,
            "application/json",
            ResidencyZone.NON_EU,
            lambda t, r, c: CrossrefConnector(transport=t, resolver=r, mailto=c),
        ),
        "wayback": (
            WAYBACK_HOST,
            "application/json, text/plain",
            ResidencyZone.NON_EU,
            lambda t, r, _c: WaybackCdxConnector(transport=t, resolver=r),
        ),
    }


#: The names a deployment may list, in the order they are composed.
CONNECTORS: Final = tuple(_connector_specs())
#: Built, but with no live source to compose: named so a deployment that lists one is
#: told why rather than told the name is unknown.
UNAVAILABLE_CONNECTORS: Final = {
    "procurement": "no live notice source exists yet (dataset_procurement.py); recorded only",
}


def connector_accesses(
    names: Sequence[str], *, contact: str, pacer: HostPacer | None = None
) -> tuple[tuple[DatasetAccess, ...], tuple[DatasetAccess, ...]]:
    """The listed connectors as (datasets, archives), each on its own fee-free route.

    A name the composition does not know, or one listed twice, raises ``ValueError``;
    the runtime's composition turns it into a start-up refusal naming its key.
    """
    if len(names) != len(set(names)):
        raise ValueError("a connector is listed once")
    specs = _connector_specs()
    resolver = SystemResolver()
    datasets: list[DatasetAccess] = []
    archives: list[DatasetAccess] = []
    for name in names:
        if name in UNAVAILABLE_CONNECTORS:
            raise ValueError(f"{name}: {UNAVAILABLE_CONNECTORS[name]}")
        if name not in specs:
            raise ValueError(f"{name!r} is not a connector ({', '.join(CONNECTORS)})")
        host, accept, zone, build = specs[name]
        transport = _paced(HostPinnedHttpsTransport(host=host, accept=accept), pacer)
        connector = build(transport, resolver, contact)
        access = DatasetAccess(
            route=ToolRoute(
                route=_provider_route(f"connector-{name}", name, zone),
                tool=connector.tool_kind,
                adapter_id=connector.connector_id,
                retrieval_mode=RetrievalMode.LIVE,
                price_usd_per_call=0.0,
            ),
            connector=connector,
        )
        (archives if connector.tool_kind is ToolKind.ARCHIVE_LOOKUP else datasets).append(access)
    return tuple(datasets), tuple(archives)
