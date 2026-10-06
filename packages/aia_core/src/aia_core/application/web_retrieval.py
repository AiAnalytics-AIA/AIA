"""The retrieval gate: the only way a Deep Research query or URL leaves AIA.

ADR 0017 decisions 1-2 as amended (plan decisions I-1, I-2, I-6). Every search and
every fetch passes, in this order, and each refusal is recorded with its reason and
never rerouted:

1. **classify** -- the query's class is the most restrictive of its context, its
   client terms and any Class A overlap (``domain.deep_research.classification``);
   a Class A query never leaves. A URL is classified the same way from a public
   context: it came from a search result, and a client term in it still raises it.
2. **egress** -- ``evaluate_egress`` for that class over the tool's own route
   (ADR 0008). A route not approved for the class refuses; there is no other route.
   A URL a host's robots.txt (already read in this run) forbids is refused here too.
3. **metering** -- a route with a price is refused unless the meter holds tool spend
   against the study's budget (it cannot yet: the generalized ledger does not exist);
   otherwise the call is reserved, and ``dispatching`` is journaled **durably
   before** it leaves.
4. **the call** -- through the route's adapter; its outcome is journaled: succeeded,
   failed (known), or uncertain (charged at its ceiling, never retried here).

A fetch a run has already made is not made again: with a :class:`RunSnapshotCache`,
a URL whose canonical form this run already captured (after steps 1-2, so a
refusal stays a refusal) is answered from it and journaled ``CACHED`` -- nothing
dispatched, nothing reserved, nothing charged -- and :attr:`FetchOutcome.cached`
says so.

**Common Crawl** (plan chunk 18), when the composition gives the gate an
:class:`ArchiveRetrieval`, takes the same steps over its own two routes.
:meth:`RetrievalGate.query_url_index` writes the index statement from a validated
:class:`~aia_core.domain.deep_research.common_crawl.UrlIndexQuery` -- no model
writes SQL -- and classifies **the statement that leaves** (it names the host or
URL asked about) in the caller's context; the index route is in ``us-east-1``
and approved for Class C only, so ``evaluate_egress`` refuses anything else
(``residency_violation`` or ``route_not_approved_for_class``). It reserves the
most a query can cost (the workgroup's scan cutoff, billed) and settles on the
bytes Athena reports it scanned; when those are unknown, the reservation is
charged. :meth:`RetrievalGate.fetch_archived` reads the WARC record an index row
names, by byte range, over the archive route: the snapshot says it is an
archived capture, and it is never put in the run's snapshot cache, so a later
live fetch of the same URL is never answered with an archive's copy.

A fetch may be confined to hosts the caller names (a crawl stays on its host):
a URL elsewhere is refused before dispatch, a redirect elsewhere before the hop
is requested. A document read for what it lists rather than what it says (a
sitemap) is fetched with :meth:`RetrievalGate.fetch_resource`: the same steps,
bytes back, no snapshot, nothing cached.

A dataset query (plan ``deep-research-web-search.md`` § 5.3) passes the same four
steps over its connector's own route: its text (the dataset id and its filters) is
classified like a search query, and only a Class C query is sent -- a dataset
interface is a public source, and nothing derived from a client is asked of it.

An archive lookup (Wayback CDX, plan § 5.3 ``archive`` and § 7 rung 9) is a dataset
query over the archive's own ``archive_lookup`` route, with one more condition before
the four steps: an :class:`~aia_core.domain.deep_research.archive.ArchivePermit` for
the same URL, which only ``decide_archive_use`` issues, from a live attempt that found
the page dead, moved or changed. Without one it is refused and journaled; the archive
is never a first choice and never a way round a paywall.

What a call is charged is decided here, once, and never in AIA's favour: a success or
a failure the provider answered costs the route's price (a provider that answered has
served the request); a failure that sent nothing costs nothing; an uncertain call and
a page refused after its dispatch cost the ceiling, because either may have been
served. Recorded routes have no price, so none of this moves money today.

The gate holds the issued ``StudyContext`` it was built with; nothing a model wrote
can name another scope. ``ToolBudgetExhausted`` and the worker's ``StopExecution``
propagate untouched: the first ends a track on its budget, the second stops the
step before anything more is sent.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import uuid4

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.archive import AccessBarrier, ArchivePermit, LiveAttempt
from ..domain.deep_research.classification import classify_query
from ..domain.deep_research.common_crawl import (
    ARCHIVE_HOST,
    AthenaPricing,
    IndexRow,
    IndexRowInvalid,
    UrlIndexQuery,
    archive_url,
    build_index_sql,
    parse_index_rows,
)
from ..domain.deep_research.contracts import (
    ClientTerm,
    QueryDecision,
    QueryRecord,
    RetrievalMode,
    SourceSnapshot,
)
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.legacy import canonical_url
from ..domain.deep_research.tooling import (
    ToolKind,
    ToolMeter,
    ToolOutcome,
    ToolReservation,
    ToolRoute,
    ToolUsageEvent,
    new_tool_call_id,
    new_tool_event_id,
)
from ..domain.deep_research.web import (
    HOST_OUT_OF_SCOPE,
    REDIRECT_OUT_OF_SCOPE,
    FetchRefused,
    SearchHit,
    check_url,
)
from ..domain.residency import DataClass, EgressDenied, evaluate_egress
from ..domain.scope import ScopeDenied, ScopeGrant, StudyContext
from ..infrastructure.common_crawl import ArchiveFetcher, IndexQueryFailed, UrlIndex
from ..infrastructure.dataset_connectors import DatasetConnector, dataset_snapshot
from ..infrastructure.web_retrieval import (
    FetchedPage,
    FetchedResource,
    HostFilter,
    SearchAdapter,
    ToolCallFailed,
    WebFetcher,
)

__all__ = [
    "ArchiveRetrieval",
    "DatasetAccess",
    "DatasetOutcome",
    "FetchOutcome",
    "IndexOutcome",
    "ResourceOutcome",
    "RetrievalGate",
    "RunSnapshotCache",
    "SearchOutcome",
    "WebRetrieval",
    "live_attempt",
]

_Fetched = TypeVar("_Fetched", FetchedPage, FetchedResource)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WebRetrieval:
    """One composition's web retrieval: two routes, their adapters, their mode."""

    search_route: ToolRoute
    fetch_route: ToolRoute
    search: SearchAdapter
    fetcher: WebFetcher

    def __post_init__(self) -> None:
        if self.search_route.tool is not ToolKind.WEB_SEARCH:
            raise ValueError("the search route must be a web_search route")
        if self.fetch_route.tool is not ToolKind.WEB_FETCH:
            raise ValueError("the fetch route must be a web_fetch route")
        if self.search.adapter_id != self.search_route.adapter_id:
            raise ValueError("the search adapter is not the one its route names")
        if self.fetcher.adapter_id != self.fetch_route.adapter_id:
            raise ValueError("the fetcher is not the one its route names")
        if self.search_route.retrieval_mode is not self.fetch_route.retrieval_mode:
            # Recorded search results fetched live, or the reverse, would be evidence
            # of neither kind.
            raise ValueError("search and fetch must both be recorded or both be live")
        # An adapter states its own mode and cannot be configured out of it, so a
        # recorded replay can never stand behind a live route (nor the reverse).
        if self.search.retrieval_mode is not self.search_route.retrieval_mode:
            raise ValueError("the search adapter's retrieval mode is not its route's")
        if self.fetcher.retrieval_mode is not self.fetch_route.retrieval_mode:
            raise ValueError("the fetcher's retrieval mode is not its route's")

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return self.search_route.retrieval_mode

    def identity(self) -> dict[str, Any]:
        """What a web track's result depends on: part of its fingerprint."""
        return {
            route.tool.value: [
                route.route_id,
                route.adapter_id,
                route.retrieval_mode.value,
                route.price_usd_per_call,
            ]
            for route in (self.search_route, self.fetch_route)
        }


@dataclass(frozen=True, slots=True)
class ArchiveRetrieval:
    """Common Crawl for one composition: the URL index and the archive, each on its route.

    A live index route's price is what one query may cost -- the workgroup's
    bytes-scanned cutoff, billed by ``pricing`` -- and it is the reservation every
    query holds; the charge is settled from the bytes scanned. A recorded index
    has no price and no pricing. Both routes, and their adapters, are recorded or
    both are live.
    """

    index_route: ToolRoute
    archive_route: ToolRoute
    index: UrlIndex
    fetcher: ArchiveFetcher
    pricing: AthenaPricing | None = None
    scan_cutoff_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.index_route.tool is not ToolKind.URL_INDEX_QUERY:
            raise ValueError("the index route must be a url_index_query route")
        if self.archive_route.tool is not ToolKind.ARCHIVE_FETCH:
            raise ValueError("the archive route must be an archive_fetch route")
        if self.index.adapter_id != self.index_route.adapter_id:
            raise ValueError("the index adapter is not the one its route names")
        if self.fetcher.adapter_id != self.archive_route.adapter_id:
            raise ValueError("the archive fetcher is not the one its route names")
        if self.index.retrieval_mode is not self.index_route.retrieval_mode:
            raise ValueError("the index adapter's retrieval mode is not its route's")
        if self.fetcher.retrieval_mode is not self.archive_route.retrieval_mode:
            raise ValueError("the archive fetcher's retrieval mode is not its route's")
        if self.index_route.retrieval_mode is not self.archive_route.retrieval_mode:
            raise ValueError("the index and the archive must both be recorded or both be live")
        if self.index_route.retrieval_mode is RetrievalMode.RECORDED:
            if self.pricing is not None or self.scan_cutoff_bytes is not None:
                raise ValueError("a recorded index has no price")
            return
        if self.pricing is None or self.scan_cutoff_bytes is None:
            raise ValueError("a live index needs its price and its scan cutoff")
        ceiling = self.pricing.cost_usd(self.scan_cutoff_bytes)
        if abs(self.index_route.price_usd_per_call - ceiling) > 1e-12:
            raise ValueError(
                "the index route's price must be its scan cutoff, billed "
                f"(${ceiling:.6f}): it is what each query reserves"
            )

    def scan_cost_usd(self, scanned_bytes: int | None) -> float:
        """What a query that scanned ``scanned_bytes`` is charged; unknown is the ceiling."""
        if self.pricing is None:
            return 0.0
        if scanned_bytes is None:
            return self.index_route.price_usd_per_call
        return self.pricing.cost_usd(scanned_bytes)


@dataclass(frozen=True, slots=True)
class IndexOutcome:
    """One URL index query: the statement code wrote, and what came of it."""

    statement: str
    data_class: DataClass
    rows: tuple[IndexRow, ...]
    #: Why no rows were kept: a refusal before sending, or the failure after.
    reason: str | None
    uncertain: bool
    #: Bytes Athena reported scanned; None when unknown or nothing was sent.
    data_scanned_bytes: int | None = None
    cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class DatasetAccess:
    """One dataset connector (or archive index) and the route it leaves AIA by."""

    route: ToolRoute
    connector: DatasetConnector

    def __post_init__(self) -> None:
        if self.route.tool not in (ToolKind.DATASET_QUERY, ToolKind.ARCHIVE_LOOKUP):
            raise ValueError("a connector's route is a dataset_query or archive_lookup route")
        # The connector's class fixes what it is: an archive cannot be given as a dataset.
        if self.connector.tool_kind is not self.route.tool:
            raise ValueError("the connector is not of its route's tool kind")
        if self.connector.connector_id != self.route.adapter_id:
            raise ValueError("the connector is not the one its route names")
        # A connector states its own mode and cannot be configured out of it.
        if self.connector.retrieval_mode is not self.route.retrieval_mode:
            raise ValueError("the connector's retrieval mode is not its route's")


@dataclass(frozen=True, slots=True)
class DatasetOutcome:
    record: QueryRecord
    snapshot: SourceSnapshot | None
    uncertain: bool


def live_attempt(outcome: FetchOutcome, *, barrier: AccessBarrier | None) -> LiveAttempt:
    """What a live fetch found, for ``decide_archive_use``.

    ``barrier`` is what the page's reader found between it and the text; it is
    stated for a captured page (``UNKNOWN`` when nobody looked) and ignored for a
    failed fetch.
    """
    if outcome.page is None:
        return LiveAttempt(
            url=outcome.url, failure=outcome.reason or "no_page", uncertain=outcome.uncertain
        )
    snapshot = outcome.page.snapshot
    return LiveAttempt(
        url=outcome.url,
        failure=None,
        uncertain=False,
        final_url=snapshot.final_url,
        text=snapshot.text,
        barrier=barrier if barrier is not None else AccessBarrier.UNKNOWN,
    )


@dataclass(frozen=True, slots=True)
class SearchOutcome:
    record: QueryRecord
    hits: tuple[SearchHit, ...]
    uncertain: bool


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    url: str
    page: FetchedPage | None
    #: Why nothing was kept: a refusal before sending, or the failure after.
    reason: str | None
    uncertain: bool
    #: The page came from this run's snapshot cache: nothing was sent or charged.
    cached: bool = False


@dataclass(frozen=True, slots=True)
class ResourceOutcome:
    """A document fetched for what it lists (a sitemap): bytes, never a snapshot."""

    url: str
    resource: FetchedResource | None
    #: Why nothing was kept: a refusal before sending, or the failure after.
    reason: str | None
    uncertain: bool


class RunSnapshotCache:
    """The pages one run has captured, by canonical URL, held in this process.

    Keyed by URL, never by snapshot id: a URL is answered only with the page
    that URL itself returned (under its requested or its final URL). The id is
    content-addressed, so two URLs whose pages extract to the same text -- a
    mirrored article, two script-only shells with no text at all -- share it;
    answering one from the other would attach the wrong URL and title to a
    citation. One cache serves one run -- the caller builds it with the run's
    gate and drops it with the run; nothing here is shared across runs or
    stored. Only a page that was kept is cached: a refusal or a failure is
    asked again.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pages: dict[str, FetchedPage] = {}

    @staticmethod
    def _key(url: str) -> str:
        return canonical_url(url) or url

    def get(self, url: str) -> FetchedPage | None:
        with self._lock:
            return self._pages.get(self._key(url))

    def put(self, url: str, page: FetchedPage) -> None:
        with self._lock:
            for each in (url, page.snapshot.final_url):
                self._pages.setdefault(self._key(each), page)

    def __len__(self) -> int:
        """The captures held (a page under two URLs is one)."""
        with self._lock:
            return len({id(page) for page in self._pages.values()})


class RetrievalGate:
    """Search and fetch for one step, under one issued scope and one meter."""

    def __init__(
        self,
        *,
        retrieval: WebRetrieval,
        scope: StudyContext,
        meter: ToolMeter,
        client_terms: Sequence[ClientTerm],
        class_a_texts: Sequence[str],
        clock: Callable[[], datetime] = _utcnow,
        datasets: Sequence[DatasetAccess] = (),
        archives: Sequence[DatasetAccess] = (),
        cache: RunSnapshotCache | None = None,
        archive: ArchiveRetrieval | None = None,
    ) -> None:
        if not isinstance(scope, StudyContext) or not isinstance(scope.grant, ScopeGrant):
            raise ScopeDenied(
                "retrieval requires an issued study context", reason="unauthorised_scope"
            )
        self._retrieval = retrieval
        self._scope = scope
        self._meter = meter
        self._terms = tuple(client_terms)
        self._class_a = tuple(class_a_texts)
        self._clock = clock
        self._datasets = {d.connector.connector_id: d for d in datasets}
        self._archives = {a.connector.connector_id: a for a in archives}
        if len(self._datasets) != len(datasets) or len(self._archives) != len(archives):
            raise ValueError("each dataset connector at most once")
        if any(d.route.tool is not ToolKind.DATASET_QUERY for d in datasets):
            raise ValueError("a dataset is given on a dataset_query route")
        if any(a.route.tool is not ToolKind.ARCHIVE_LOOKUP for a in archives):
            raise ValueError("an archive is given on an archive_lookup route")
        if any(
            d.route.retrieval_mode is not retrieval.retrieval_mode for d in (*datasets, *archives)
        ):
            # Recorded tables beside live pages would be evidence of neither kind.
            raise ValueError("dataset routes are recorded or live as web retrieval is")
        self._cache = cache
        self._archive = archive

    # ---------------------------------------------------------------- shared --

    def _event(
        self,
        route: ToolRoute,
        *,
        call_id: str,
        outcome: ToolOutcome,
        data_class: DataClass,
        track_id: str,
        sent: str,
        reservation: ToolReservation | None = None,
        cost: float = 0.0,
        charged_credits: int = 0,
        provider_request_id: str | None = None,
        note: str = "",
    ) -> ToolUsageEvent:
        return ToolUsageEvent(
            event_id=new_tool_event_id(),
            call_id=call_id,
            tool=route.tool,
            outcome=outcome,
            route_id=route.route_id,
            retrieval_mode=route.retrieval_mode,
            data_class=data_class,
            track_id=track_id,
            reservation_id=reservation.reservation_id if reservation else None,
            request_fingerprint=_fingerprint(sent),
            provider_request_id=provider_request_id,
            credits=charged_credits,
            cost_usd=cost,
            ceiling_usd=route.price_usd_per_call,
            occurred_at=self._clock(),
            note=note[:500],
        )

    def _refusal(self, route: ToolRoute, *, data_class: DataClass) -> str | None:
        """Why this call may not leave, or None. Egress first, then metering."""
        try:
            evaluate_egress(scope=self._scope, data_class=data_class, route=route.route)
        except EgressDenied as exc:
            return f"egress_{exc.reason}"
        if route.price_usd_per_call > 0 and not self._meter.charges_study_budget:
            return "tool_metering_unavailable"
        return None

    def refusal_for_class(self, data_class: DataClass) -> str | None:
        """Why every query written from a context of ``data_class`` would be refused.

        ``None`` when such a query could leave. Journals nothing: nothing was
        proposed. The planning step asks first, so that no model is paid to write
        queries that can never be sent. A fetch is judged for the public class its
        URLs start from.
        """
        if data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL:
            return "class_a_query"
        search = self._refusal(self._retrieval.search_route, data_class=data_class)
        if search is not None:
            return search
        fetch = self._refusal(self._retrieval.fetch_route, data_class=DataClass.CLASS_C_INTERNAL)
        return None if fetch is None else f"fetch_{fetch}"

    def known_sitemaps(self, host: str) -> tuple[str, ...] | None:
        """The ``Sitemap:`` URLs ``host``'s robots.txt declares, if this run already read it.

        Sends nothing and journals nothing: the robots.txt was read as part of a
        fetch this gate already journaled. None when it has not been read.
        """
        return self._retrieval.fetcher.known_sitemaps(host)

    def _refuse(
        self, route: ToolRoute, *, reason: str, data_class: DataClass, track_id: str, sent: str
    ) -> None:
        self._meter.outcome(
            self._event(
                route,
                call_id=new_tool_call_id(),
                outcome=ToolOutcome.REFUSED,
                data_class=data_class,
                track_id=track_id,
                sent=sent,
                note=reason,
            )
        )

    def _open(
        self, route: ToolRoute, *, data_class: DataClass, track_id: str, sent: str
    ) -> tuple[str, ToolReservation]:
        """Reserve, then journal the dispatch durably. Raises before anything is sent."""
        reservation = self._meter.reserve(
            tool=route.tool,
            route_id=route.route_id,
            track_id=track_id,
            amount_usd=route.price_usd_per_call,
        )
        call_id = new_tool_call_id()
        self._meter.dispatching(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.DISPATCHED,
                data_class=data_class,
                track_id=track_id,
                sent=sent,
                reservation=reservation,
            )
        )
        return call_id, reservation

    def _close_failure(
        self,
        route: ToolRoute,
        exc: ToolCallFailed,
        *,
        call_id: str,
        reservation: ToolReservation,
        data_class: DataClass,
        track_id: str,
        sent: str,
    ) -> bool:
        """Journal a failed call; True when its outcome is unknown (charged at its ceiling).

        A failure the provider answered is charged its price: it served the request.
        """
        uncertain = exc.delivery is Delivery.UNKNOWN
        self._meter.outcome(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.UNCERTAIN if uncertain else ToolOutcome.FAILED,
                data_class=data_class,
                track_id=track_id,
                sent=sent,
                reservation=reservation,
                cost=route.price_usd_per_call if exc.delivery is Delivery.RESPONDED else 0.0,
                note=exc.reason,
            )
        )
        return uncertain

    # ---------------------------------------------------------------- search --

    def search(
        self, query: str, *, context_class: DataClass, track_id: str, max_results: int
    ) -> SearchOutcome:
        """One proposed query: classified, authorised, reserved, journaled, sent -- or refused."""
        route = self._retrieval.search_route
        classified = classify_query(
            query,
            context_class=context_class,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        )
        cls = classified.data_class

        def record(
            decision: QueryDecision,
            *,
            refusal: str | None = None,
            failure: str | None = None,
            call_id: str | None = None,
            hits: int = 0,
        ) -> QueryRecord:
            return QueryRecord(
                text=query,
                data_class=cls,
                class_reasons=classified.reasons,
                decision=decision,
                refusal=refusal,
                call_id=call_id,
                hits=hits,
                failure=failure,
            )

        reason = (
            "class_a_query"
            if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
            else self._refusal(route, data_class=cls)
        )
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=query)
            return SearchOutcome(record(QueryDecision.REFUSED, refusal=reason), (), False)

        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=query)
        try:
            response = self._retrieval.search.search(query, max_results=max_results)
        except ToolCallFailed as exc:
            uncertain = self._close_failure(
                route,
                exc,
                call_id=call_id,
                reservation=reservation,
                data_class=cls,
                track_id=track_id,
                sent=query,
            )
            return SearchOutcome(
                record(QueryDecision.SENT, failure=exc.reason, call_id=call_id), (), uncertain
            )
        self._meter.outcome(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.SUCCEEDED,
                data_class=cls,
                track_id=track_id,
                sent=query,
                reservation=reservation,
                cost=route.price_usd_per_call,
                charged_credits=response.credits,
                provider_request_id=response.provider_request_id,
            )
        )
        return SearchOutcome(
            record(QueryDecision.SENT, call_id=call_id, hits=len(response.hits)),
            response.hits,
            False,
        )

    # ----------------------------------------------------------------- fetch --

    def _fetch_admission(
        self, url: str, *, host_allowed: HostFilter | None
    ) -> tuple[DataClass, str | None]:
        """A URL's class, and why it may not be requested (address, scope, class, egress)."""
        cls = classify_query(
            url,
            context_class=DataClass.CLASS_C_INTERNAL,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        ).data_class
        try:
            host = check_url(url)
        except FetchRefused as exc:
            return cls, exc.reason
        if host_allowed is not None and not host_allowed(host):
            return cls, HOST_OUT_OF_SCOPE
        if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL:
            return cls, "class_a_url"
        return cls, self._refusal(self._retrieval.fetch_route, data_class=cls)

    def _fetch_call(
        self,
        url: str,
        *,
        cls: DataClass,
        track_id: str,
        call: Callable[[], _Fetched],
        request_id: Callable[[_Fetched], str | None],
        note: Callable[[_Fetched], str] = lambda _: "",
        route: ToolRoute | None = None,
    ) -> tuple[_Fetched | None, str | None, bool]:
        """Reserve, journal, send, journal: (what came back, why not, uncertain).

        ``url`` is what was sent (its fingerprint is journaled); ``route`` is the
        fetch route unless another is named (an archive's).
        """
        route = route or self._retrieval.fetch_route
        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=url)
        try:
            result = call()
        except FetchRefused as exc:
            # Refused on a later hop or by the response itself; nothing kept. A hop
            # may already have been served, so it is charged as if it was.
            self._meter.outcome(
                self._event(
                    route,
                    call_id=call_id,
                    outcome=ToolOutcome.FAILED,
                    data_class=cls,
                    track_id=track_id,
                    sent=url,
                    reservation=reservation,
                    cost=route.price_usd_per_call,
                    note=exc.reason,
                )
            )
            return None, exc.reason, False
        except ToolCallFailed as exc:
            uncertain = self._close_failure(
                route,
                exc,
                call_id=call_id,
                reservation=reservation,
                data_class=cls,
                track_id=track_id,
                sent=url,
            )
            return None, exc.reason, uncertain
        self._meter.outcome(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.SUCCEEDED,
                data_class=cls,
                track_id=track_id,
                sent=url,
                reservation=reservation,
                cost=route.price_usd_per_call,
                provider_request_id=request_id(result),
                note=note(result),
            )
        )
        return result, None, False

    def fetch(
        self, url: str, *, track_id: str, host_allowed: HostFilter | None = None
    ) -> FetchOutcome:
        """One page: checked, authorised, reserved, journaled, fetched -- or refused.

        ``host_allowed`` confines the fetch to the hosts it allows (a crawl's own
        host): a URL elsewhere is refused before dispatch (``host_out_of_scope``),
        a redirect elsewhere before the hop is requested (``redirect_out_of_scope``),
        and a cached page whose final URL is elsewhere is refused, not served.
        """
        route = self._retrieval.fetch_route
        cls, reason = self._fetch_admission(url, host_allowed=host_allowed)
        if reason is None and self._cache is not None:
            hit = self._cache.get(url)
            if hit is not None:
                final_host = check_url(hit.snapshot.final_url)
                if host_allowed is not None and not host_allowed(final_host):
                    reason = REDIRECT_OUT_OF_SCOPE
                else:
                    self._meter.outcome(
                        self._event(
                            route,
                            call_id=new_tool_call_id(),
                            outcome=ToolOutcome.CACHED,
                            data_class=cls,
                            track_id=track_id,
                            sent=url,
                            note=f"run_snapshot_cache {hit.snapshot.snapshot_id}",
                        )
                    )
                    return FetchOutcome(
                        url=url, page=hit, reason=None, uncertain=False, cached=True
                    )
        if reason is None:
            # A robots.txt the transport already holds: refused before any dispatch.
            reason = self._retrieval.fetcher.known_refusal(url)
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=url)
            return FetchOutcome(url=url, page=None, reason=reason, uncertain=False)

        fetcher = self._retrieval.fetcher
        page, failure, uncertain = self._fetch_call(
            url,
            cls=cls,
            track_id=track_id,
            call=lambda: fetcher.fetch(url, host_allowed=host_allowed),
            request_id=lambda fetched: fetched.snapshot.request_id,
        )
        if page is None:
            return FetchOutcome(url=url, page=None, reason=failure, uncertain=uncertain)
        if self._cache is not None:
            self._cache.put(url, page)
        return FetchOutcome(url=url, page=page, reason=None, uncertain=False)

    # --------------------------------------------------------------- dataset --

    def dataset(
        self, query: DatasetQuery, *, context_class: DataClass, track_id: str
    ) -> DatasetOutcome:
        """One dataset query: classified, authorised, reserved, journaled, asked -- or refused.

        Class C only: a query the classifier raises (a client term, Class A overlap,
        a client-derived context) is refused and never sent. A connector this gate
        was not given is refused without a journal entry: there is no route to
        journal it against, and nothing was proposed to one.
        """
        return self._ask(
            self._datasets.get(query.connector_id),
            query,
            context_class=context_class,
            track_id=track_id,
            archive=False,
            permit=None,
        )

    def archive(
        self,
        query: DatasetQuery,
        *,
        permit: ArchivePermit | None,
        context_class: DataClass,
        track_id: str,
    ) -> DatasetOutcome:
        """One archive lookup for ``query.dataset_id`` (a page URL), only with its permit.

        As :meth:`dataset`, and first: the permit must be one ``decide_archive_use``
        issued for this very URL, or the lookup is refused (``archive_not_permitted``)
        and journaled, and nothing is sent.
        """
        return self._ask(
            self._archives.get(query.connector_id),
            query,
            context_class=context_class,
            track_id=track_id,
            archive=True,
            permit=permit,
        )

    def _ask(
        self,
        access: DatasetAccess | None,
        query: DatasetQuery,
        *,
        context_class: DataClass,
        track_id: str,
        archive: bool,
        permit: ArchivePermit | None,
    ) -> DatasetOutcome:
        """The path every connector call takes; an archive's needs its permit first."""
        sent = query.text()
        classified = classify_query(
            sent,
            context_class=context_class,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        )
        cls = classified.data_class

        def record(
            decision: QueryDecision,
            *,
            refusal: str | None = None,
            failure: str | None = None,
            call_id: str | None = None,
            hits: int = 0,
        ) -> QueryRecord:
            return QueryRecord(
                text=sent,
                data_class=cls,
                class_reasons=classified.reasons,
                decision=decision,
                refusal=refusal,
                call_id=call_id,
                hits=hits,
                failure=failure,
            )

        if access is None:
            return DatasetOutcome(
                record(QueryDecision.REFUSED, refusal="dataset_connector_unavailable"), None, False
            )
        route = access.route
        reason: str | None
        if archive and not (isinstance(permit, ArchivePermit) and permit.url == query.dataset_id):
            reason = "archive_not_permitted"
        elif cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL:
            reason = "class_a_query"
        elif cls is not DataClass.CLASS_C_INTERNAL:
            reason = "dataset_class_c_only"
        else:
            reason = self._refusal(route, data_class=cls)
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=sent)
            return DatasetOutcome(record(QueryDecision.REFUSED, refusal=reason), None, False)

        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=sent)
        try:
            response = access.connector.query(query)
            if response.result.query != query:
                raise ToolCallFailed(
                    "the connector answered another query",
                    reason="response_contract",
                    delivery=Delivery.RESPONDED,
                )
            snapshot = dataset_snapshot(response, retrieval_mode=route.retrieval_mode)
        except ToolCallFailed as exc:
            uncertain = self._close_failure(
                route,
                exc,
                call_id=call_id,
                reservation=reservation,
                data_class=cls,
                track_id=track_id,
                sent=sent,
            )
            return DatasetOutcome(
                record(QueryDecision.SENT, failure=exc.reason, call_id=call_id), None, uncertain
            )
        self._meter.outcome(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.SUCCEEDED,
                data_class=cls,
                track_id=track_id,
                sent=sent,
                reservation=reservation,
                cost=route.price_usd_per_call,
                charged_credits=response.credits,
                provider_request_id=response.provider_request_id,
            )
        )
        return DatasetOutcome(
            record(QueryDecision.SENT, call_id=call_id, hits=len(response.result.rows)),
            snapshot,
            False,
        )

    def fetch_resource(
        self,
        url: str,
        *,
        track_id: str,
        media_types: frozenset[str],
        max_bytes: int,
        host_allowed: HostFilter | None = None,
    ) -> ResourceOutcome:
        """One document a crawl reads for what it lists (a sitemap), through the same gate.

        Classified, scope- and egress-checked, robots-checked, reserved and
        journaled exactly like :meth:`fetch` (its success notes ``resource
        <media type>``); only what comes back differs: bytes of one of
        ``media_types``, at most ``max_bytes``, and no snapshot -- a resource is
        never evidence, and it is not put in the run's snapshot cache.
        """
        route = self._retrieval.fetch_route
        cls, reason = self._fetch_admission(url, host_allowed=host_allowed)
        if reason is None:
            reason = self._retrieval.fetcher.known_refusal(url)
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=url)
            return ResourceOutcome(url=url, resource=None, reason=reason, uncertain=False)
        fetcher = self._retrieval.fetcher
        resource, failure, uncertain = self._fetch_call(
            url,
            cls=cls,
            track_id=track_id,
            call=lambda: fetcher.fetch_resource(
                url, media_types=media_types, max_bytes=max_bytes, host_allowed=host_allowed
            ),
            request_id=lambda fetched: fetched.request_id,
            note=lambda fetched: f"resource {fetched.media_type}",
        )
        return ResourceOutcome(url=url, resource=resource, reason=failure, uncertain=uncertain)

    # ---------------------------------------------------------- common crawl --

    def query_url_index(
        self, query: UrlIndexQuery, *, context_class: DataClass, track_id: str
    ) -> IndexOutcome:
        """One URL index query: written, classified, authorised, reserved, run, settled.

        The statement is written by code from ``query`` and classified in
        ``context_class`` (the class of what the query was derived from) with the
        client's terms; a Class A statement never leaves, and the index route's
        egress decides the rest. The call reserves the route's price (the most a
        query can cost) and is charged the bytes it scanned; an unknown scan is
        charged the reservation. Rows of another shape are refused whole, and the
        scan they cost is still charged.
        """
        archive = self._archive
        if archive is None:
            raise ValueError("this gate has no Common Crawl route")
        route = archive.index_route
        statement = build_index_sql(query, archive.index.table)
        cls = classify_query(
            statement,
            context_class=context_class,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        ).data_class
        reason = (
            "class_a_query"
            if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
            else self._refusal(route, data_class=cls)
        )
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=statement)
            return IndexOutcome(statement, cls, (), reason, False)

        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=statement)

        def close(
            outcome: ToolOutcome,
            scanned: int | None,
            *,
            note: str,
            request_id: str | None,
        ) -> float:
            cost = archive.scan_cost_usd(scanned)
            self._meter.outcome(
                self._event(
                    route,
                    call_id=call_id,
                    outcome=outcome,
                    data_class=cls,
                    track_id=track_id,
                    sent=statement,
                    reservation=reservation,
                    cost=cost,
                    charged_credits=scanned or 0,
                    provider_request_id=request_id,
                    note=f"{note}; scanned {'unknown' if scanned is None else scanned} bytes",
                )
            )
            return cost

        try:
            result = archive.index.run(statement, request_token=str(uuid4()), max_rows=query.limit)
        except IndexQueryFailed as exc:
            uncertain = exc.delivery is Delivery.UNKNOWN
            cost = close(
                ToolOutcome.UNCERTAIN if uncertain else ToolOutcome.FAILED,
                exc.data_scanned_bytes,
                note=exc.reason,
                request_id=exc.execution_id,
            )
            return IndexOutcome(
                statement, cls, (), exc.reason, uncertain, exc.data_scanned_bytes, cost
            )
        scanned = result.data_scanned_bytes
        try:
            rows = parse_index_rows(result.columns, result.rows)
        except IndexRowInvalid as exc:
            cost = close(
                ToolOutcome.FAILED,
                scanned,
                note=f"index_rows_invalid: {exc}",
                request_id=result.execution_id,
            )
            return IndexOutcome(statement, cls, (), "index_rows_invalid", False, scanned, cost)
        cost = close(
            ToolOutcome.SUCCEEDED,
            scanned,
            note=f"{len(rows)} rows",
            request_id=result.execution_id,
        )
        return IndexOutcome(statement, cls, rows, None, False, scanned, cost)

    def fetch_archived(self, row: IndexRow, *, track_id: str) -> FetchOutcome:
        """The archived capture an index row names, by byte range -- or refused.

        Classified (the WARC file's URL, from a public index), egress-checked over
        the archive route, reserved and journaled like a fetch; what was sent is
        the file URL and its range. The snapshot carries its
        :class:`~aia_core.domain.deep_research.contracts.ArchivedCapture`, and is
        not put in the run's snapshot cache: the cache answers live fetches only.
        """
        archive = self._archive
        if archive is None:
            raise ValueError("this gate has no Common Crawl route")
        route = archive.archive_route
        url = archive_url(row)
        last = row.warc_record_offset + row.warc_record_length - 1
        sent = f"{url} bytes={row.warc_record_offset}-{last}"
        cls = classify_query(
            url,
            context_class=DataClass.CLASS_C_INTERNAL,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        ).data_class
        reason: str | None
        try:
            reason = None if check_url(url) == ARCHIVE_HOST else HOST_OUT_OF_SCOPE
        except FetchRefused as exc:
            reason = exc.reason
        if reason is None:
            reason = (
                "class_a_url"
                if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
                else self._refusal(route, data_class=cls)
            )
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=sent)
            return FetchOutcome(url=row.url, page=None, reason=reason, uncertain=False)
        fetcher = archive.fetcher
        page, failure, uncertain = self._fetch_call(
            sent,
            cls=cls,
            track_id=track_id,
            call=lambda: fetcher.fetch(row),
            request_id=lambda fetched: fetched.snapshot.request_id,
            note=lambda _: f"archived {row.crawl} {row.captured_at.date().isoformat()}",
            route=route,
        )
        return FetchOutcome(url=row.url, page=page, reason=failure, uncertain=uncertain)
