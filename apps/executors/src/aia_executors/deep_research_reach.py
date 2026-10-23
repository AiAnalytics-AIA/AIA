"""What this worker's Deep Research composition reaches, recorded at start
(deep-research-web-search 52, settings-backends SB6).

:func:`reach_of` reads the composed :class:`DeepResearchRuntime` itself -- its retrieval, its
connectors, its archives and Common Crawl, each a ``ToolRoute`` with its classes and price --
and names every route the code builds that it does not compose, with the switch that decides
it. :func:`record_reach` keeps that at worker start (``build_registry``), best effort: a worker
that cannot write it starts anyway and says so in its log.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Final

from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.deep_research_reach import ReachKind, ReachState, RouteReach, order_reach
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.deep_research_composition_repository import record_composition

from .deep_research import DeepResearchRuntime
from .deep_research.standing import STANDING_CONNECTORS
from .deep_research_live import (
    BRAVE_ROUTE_ID,
    COMMON_CRAWL_ARCHIVE_ROUTE_ID,
    COMMON_CRAWL_INDEX_ROUTE_ID,
    CONNECTORS,
    UNAVAILABLE_CONNECTORS,
)
from .deep_research_runtime import (
    AGENT_DIRECTED_KEY,
    COMMON_CRAWL_KEY,
    CONNECTORS_KEY,
    ENABLED_KEY,
    PUBLIC_FETCH_CONTACT_KEY,
    WEB_SEARCH_KEY,
    agent_directed,
    common_crawl,
    connectors,
    deep_research_enabled,
    public_fetch_contact,
    web_search,
)

__all__ = ["reach_of", "record_reach"]

log = logging.getLogger(__name__)

WIKIPEDIA_SEARCH: Final = "wikipedia-public-web_search"
WIKIPEDIA_FETCH: Final = "wikipedia-public-web_fetch"
PUBLIC_FETCH: Final = "public-web-fetch"
#: The archive lookups among the connectors (an archive, not a dataset).
_ARCHIVE_CONNECTORS: Final = frozenset({"wayback"})

_KIND: Final = {
    ToolKind.WEB_SEARCH: ReachKind.SEARCH,
    ToolKind.WEB_FETCH: ReachKind.FETCH,
    ToolKind.DATASET_QUERY: ReachKind.CONNECTOR,
    ToolKind.ARCHIVE_LOOKUP: ReachKind.ARCHIVE,
    ToolKind.URL_INDEX_QUERY: ReachKind.INDEX,
    ToolKind.ARCHIVE_FETCH: ReachKind.ARCHIVE,
}


def _composed(runtime: DeepResearchRuntime | None) -> list[tuple[ToolRoute, bool]]:
    """Every composed route, and whether only the agent-directed ladder asks it."""
    if runtime is None:
        return []
    routes: list[tuple[ToolRoute, bool]] = []
    if runtime.retrieval is not None:
        routes += [(runtime.retrieval.search_route, False), (runtime.retrieval.fetch_route, False)]
    # A standing index (Crossref, OpenAlex) is asked by the merge step in either mode
    # (standing.py); every other connector and archive only by the agent-directed ladder.
    routes += [
        (d.route, d.connector.connector_id not in STANDING_CONNECTORS) for d in runtime.datasets
    ]
    routes += [(a.route, True) for a in runtime.archives]
    if runtime.archive is not None:
        routes += [(runtime.archive.index_route, True), (runtime.archive.archive_route, True)]
    return routes


def _active(route: ToolRoute, *, ladder_only: bool, directed: bool) -> RouteReach:
    """A composed route: active, unless only the ladder asks it and the ladder never runs."""
    idle = ladder_only and not directed
    return RouteReach(
        route=route.route_id,
        kind=_KIND[route.tool],
        state=ReachState.BUILT if idle else ReachState.ACTIVE,
        reason="agent_directed_off" if idle else None,
        detail=(
            f"composed, but only the agent-directed ladder asks it ({AGENT_DIRECTED_KEY})"
            if idle
            else None
        ),
        classes=tuple(sorted(route.route.approved_for, key=lambda c: c.value)),
        priced=route.needs_sign_off,
        zone=route.route.zone.value,
    )


def reach_of(runtime: DeepResearchRuntime | None, env: Mapping[str, str]) -> list[RouteReach]:
    """Every route the code builds, as this composition made it, waiting/active/off order."""
    enabled = deep_research_enabled(env)
    search = web_search(env)
    contact = public_fetch_contact(env)
    listed = set(connectors(env))
    crawl = common_crawl(env)
    directed = agent_directed(env)
    composed = {r.route_id: (r, ladder) for r, ladder in _composed(runtime)}
    out: list[RouteReach] = [
        _active(route, ladder_only=ladder, directed=directed) for route, ladder in composed.values()
    ]

    def off(route: str, kind: ReachKind, reason: str, detail: str) -> None:
        if route in composed:
            return
        if not enabled or runtime is None:
            reason, detail = "deep_research_off", f"{ENABLED_KEY} is not true"
        out.append(RouteReach(route, kind, ReachState.BUILT, reason, detail))

    off(
        WIKIPEDIA_SEARCH,
        ReachKind.SEARCH,
        "search_route_other",
        f"{WEB_SEARCH_KEY}={search}",
    )
    off(
        BRAVE_ROUTE_ID,
        ReachKind.SEARCH,
        "search_route_other",
        f"{WEB_SEARCH_KEY}={search}",
    )
    off(
        WIKIPEDIA_FETCH,
        ReachKind.FETCH,
        "search_route_other",
        "pages are fetched by the public fetch" if contact else f"{WEB_SEARCH_KEY}={search}",
    )
    off(
        PUBLIC_FETCH,
        ReachKind.FETCH,
        "public_fetch_off",
        f"{PUBLIC_FETCH_CONTACT_KEY} is not set"
        if contact is None
        else f"{WEB_SEARCH_KEY}={search}",
    )
    for name in CONNECTORS:
        off(
            f"connector-{name}",
            ReachKind.ARCHIVE if name in _ARCHIVE_CONNECTORS else ReachKind.CONNECTOR,
            "connector_not_listed",
            f"not in {CONNECTORS_KEY}"
            if name not in listed
            else f"{PUBLIC_FETCH_CONTACT_KEY} is not set",
        )
    for name, why in UNAVAILABLE_CONNECTORS.items():
        out.append(
            RouteReach(
                f"connector-{name}", ReachKind.CONNECTOR, ReachState.REFUSED, "unavailable", why
            )
        )
    detail = f"{COMMON_CRAWL_KEY} is not true" if not crawl else f"{WEB_SEARCH_KEY}={search}"
    off(COMMON_CRAWL_INDEX_ROUTE_ID, ReachKind.INDEX, "common_crawl_off", detail)
    off(COMMON_CRAWL_ARCHIVE_ROUTE_ID, ReachKind.ARCHIVE, "common_crawl_off", detail)
    return order_reach(out)


def record_reach(runtime: DeepResearchRuntime | None, env: Mapping[str, str] | None = None) -> bool:
    """Keep this worker's reach for Settings; ``False`` (and a log line) when it cannot. Never
    raises: what Settings shows is not a reason for a worker not to start."""
    values = os.environ if env is None else env
    url = values.get("DATABASE_URL", "").strip()
    if not url or url.startswith("sqlite"):
        return False
    try:
        routes = reach_of(runtime, values)
        engine = create_app_engine(url, pool_size=1, max_overflow=0)
        try:
            with create_session_factory(engine)() as session:
                record_composition(
                    session,
                    worker=values.get("HOSTNAME", "").strip()[:128] or "worker",
                    build_sha=BuildIdentity.from_env().sha,
                    composed_at=datetime.now(UTC),
                    agent_directed=agent_directed(values),
                    class_gates=(runtime.config.class_gates.value if runtime is not None else None),
                    routes=routes,
                )
                session.commit()
        finally:
            engine.dispose()
    except Exception:  # Settings' record is not a reason to stop a worker
        log.warning("deep research reach: not recorded", exc_info=True)
        return False
    return True
