"""The recorded Deep Research composition: the whole path on captured exchanges, locally.

Web search and fetch replay a recorded exchange file; nothing leaves the process.
It refuses to build unless ``AIA_ENV`` is ``local`` or ``test`` (unset refuses), no
production composition imports it, and no deployment may name it (``make
layer_check``): a recorded source can never stand in for a live one. The adapters
say ``RECORDED`` themselves and cannot be configured out of it, so a snapshot they
take, and every bundle built on one, is marked ``RECORDED_FIXTURE`` -- which the
client-facing gate (``require_live_evidence``) refuses.

The exchange file::

    {
      "recorded_at": "2026-09-01T09:00:00+00:00",   # when the pages were captured
      "source_classes": {"stats.example": "OFFICIAL_STATISTICS", ...},
      "search": {"<query>": {"hits": [{"url": ..., "title": ..., "snippet": ...}],
                             "credits": 1, "request_id": ...} | {"fail": "known" | "uncertain"}},
      "pages": {"<url>": {"status": 200, "headers": {...}, "body": "<html>..."}
                         | {"fail": "uncertain"}},
      "hosts": {"stats.example": ["93.184.215.14"], ...}
    }

Its SHA256 is part of the adapter ids, and so of every web track's fingerprint: a
changed recording is a different retrieval, and nothing researched on the old one
is reused on the new. ``source_classes`` extends the declared source table under a
version of its own (``aia-source-table-1+recorded-<sha>``), for the fixture's hosts.

The model side is whatever gateway the caller builds -- in the tests, the real
gateway and Bedrock adapter over a recorded transport.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Final

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.application.web_retrieval import WebRetrieval
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTable
from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.web_retrieval import WebFetcher, load_recorded_web

from .deep_research import DeepResearchConfig, DeepResearchRuntime

__all__ = ["ALLOWED_ENVIRONMENTS", "recorded_retrieval", "recorded_runtime"]

#: Where recorded retrieval may exist. Anything else refuses at build.
ALLOWED_ENVIRONMENTS: Final = frozenset({"local", "test"})


def _route(tool: ToolKind) -> ProviderRoute:
    """A local replay's route: nothing leaves the process, and it says so."""
    return ProviderRoute(
        route_id=f"recorded-{tool.value.replace('_', '-')}",
        provider="recorded",
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        retention_days=0,
        # Only what the fictional authorization covers: no client material rides it.
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )


def recorded_retrieval(fixture: Path) -> tuple[WebRetrieval, SourceTable]:
    """Recorded search and fetch over one exchange file, and its extended source table."""
    raw = fixture.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()[:12]
    data = json.loads(raw)
    recorded_at = datetime.fromisoformat(str(data["recorded_at"]))
    if recorded_at.tzinfo is None:
        raise ValueError("recorded_at names its timezone")
    search_id, fetch_id = f"recorded-search-v1:{sha}", f"recorded-fetch-v1:{sha}"
    web = load_recorded_web(fixture, adapter_id=search_id)
    retrieval = WebRetrieval(
        search_route=ToolRoute(
            route=_route(ToolKind.WEB_SEARCH),
            tool=ToolKind.WEB_SEARCH,
            adapter_id=search_id,
            retrieval_mode=RetrievalMode.RECORDED,
            price_usd_per_call=0.0,
        ),
        fetch_route=ToolRoute(
            route=_route(ToolKind.WEB_FETCH),
            tool=ToolKind.WEB_FETCH,
            adapter_id=fetch_id,
            retrieval_mode=RetrievalMode.RECORDED,
            price_usd_per_call=0.0,
        ),
        search=web.search,
        # A replayed page was captured when it was recorded, not when it is replayed.
        fetcher=WebFetcher(
            transport=web.transport,
            resolver=web.resolver,
            adapter_id=fetch_id,
            clock=lambda: recorded_at,
        ),
    )
    table = SOURCE_TABLE_V1.extended(
        f"{SOURCE_TABLE_V1.version}+recorded-{sha}",
        {host: SourceClass(cls) for host, cls in data.get("source_classes", {}).items()},
    )
    return retrieval, table


def recorded_runtime(
    *,
    gateway: GovernedModelGateway,
    config: DeepResearchConfig,
    fixture: Path,
    env: Mapping[str, str] | None = None,
) -> DeepResearchRuntime:
    """The recorded composition; refuses outside ``local`` and ``test``."""
    environment = ((os.environ if env is None else env).get("AIA_ENV") or "").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "aia_executors.deep_research_recorded replays recorded web exchanges and refuses "
            f"AIA_ENV={environment!r}; no deployment composes it"
        )
    retrieval, table = recorded_retrieval(fixture)
    return DeepResearchRuntime(
        gateway=gateway, config=config, retrieval=retrieval, source_table=table
    )
