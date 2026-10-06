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

A fetch may be confined to hosts the caller names (a crawl stays on its host):
a URL elsewhere is refused before dispatch, a redirect elsewhere before the hop
is requested. A document read for what it lists rather than what it says (a
sitemap) is fetched with :meth:`RetrievalGate.fetch_resource`: the same steps,
bytes back, no snapshot, nothing cached.

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

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.classification import classify_query
from ..domain.deep_research.contracts import (
    ClientTerm,
    QueryDecision,
    QueryRecord,
    RetrievalMode,
)
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
from ..infrastructure.web_retrieval import (
    FetchedPage,
    FetchedResource,
    HostFilter,
    LanguageSearch,
    SearchAdapter,
    SearchResponse,
    ToolCallFailed,
    WebFetcher,
)

__all__ = [
    "FetchOutcome",
    "PendingFetch",
    "PendingSearch",
    "ResourceOutcome",
    "RetrievalGate",
    "RunSnapshotCache",
    "SearchOutcome",
    "WebRetrieval",
    "request_fingerprint",
    "sent_search",
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
class SearchOutcome:
    record: QueryRecord
    hits: tuple[SearchHit, ...]
    uncertain: bool
    #: SHA256 of what was journaled as sent; None when nothing was dispatched.
    request_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    url: str
    page: FetchedPage | None
    #: Why nothing was kept: a refusal before sending, or the failure after.
    reason: str | None
    uncertain: bool
    #: The page came from this run's snapshot cache: nothing was sent or charged.
    cached: bool = False
    #: The class the URL was judged at, and the dispatched call (None when none was).
    data_class: DataClass | None = None
    call_id: str | None = None
    request_fingerprint: str | None = None


def request_fingerprint(sent: str) -> str:
    """What the journal keeps of a sent query or URL: its SHA256, never the text."""
    return _fingerprint(sent)


def sent_search(query: str, lang: str | None) -> str:
    """What a search sends, as journaled: the text, and its language when one is asked."""
    return query if lang is None else f"{query}\n[lang={lang}]"


@dataclass(slots=True)
class PendingSearch:
    """A search reserved and journaled ``DISPATCHED``, not yet sent.

    :meth:`send` is the only part that may run off the step's thread: it calls the
    adapter and keeps what came back, journaling nothing. The gate's
    :meth:`RetrievalGate.finish_search` journals the outcome on the step's thread.
    """

    query: str
    lang: str | None
    max_results: int
    track_id: str
    data_class: DataClass
    class_reasons: tuple[str, ...]
    call_id: str
    reservation: ToolReservation
    adapter: SearchAdapter
    response: SearchResponse | None = None
    failure: ToolCallFailed | None = None
    error: BaseException | None = None

    @property
    def sent(self) -> str:
        return sent_search(self.query, self.lang)

    def send(self) -> None:
        try:
            if self.lang is not None and isinstance(self.adapter, LanguageSearch):
                self.response = self.adapter.search_in(
                    self.query, lang=self.lang, max_results=self.max_results
                )
            else:
                self.response = self.adapter.search(self.query, max_results=self.max_results)
        except ToolCallFailed as exc:
            self.failure = exc
        except Exception as exc:  # re-raised by finish_search, on the step's thread
            self.error = exc


@dataclass(slots=True)
class PendingFetch:
    """A fetch reserved and journaled ``DISPATCHED``, not yet sent (see :class:`PendingSearch`)."""

    url: str
    track_id: str
    data_class: DataClass
    call_id: str
    reservation: ToolReservation
    fetcher: WebFetcher
    #: The hosts this fetch is confined to, every redirect hop included (None: any).
    host_allowed: HostFilter | None = None
    page: FetchedPage | None = None
    refused: FetchRefused | None = None
    failure: ToolCallFailed | None = None
    error: BaseException | None = None

    def send(self) -> None:
        try:
            self.page = self.fetcher.fetch(self.url, host_allowed=self.host_allowed)
        except FetchRefused as exc:
            self.refused = exc
        except ToolCallFailed as exc:
            self.failure = exc
        except Exception as exc:  # re-raised by finish_fetch, on the step's thread
            self.error = exc


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
        cache: RunSnapshotCache | None = None,
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
        self._cache = cache

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

    def remember(self, url: str, page: FetchedPage) -> None:
        """Hold a page this run captured in an earlier attempt (read back from its store).

        A resumed step replays what its earlier attempt fetched without fetching it;
        with this, a later action asking for the same URL is a cache hit, as it
        would have been had the attempt not been interrupted. No cache: nothing.
        Journals nothing: nothing was sent or answered.
        """
        if self._cache is not None:
            self._cache.put(url, page)

    # ---------------------------------------------------------------- search --

    def search(
        self,
        query: str,
        *,
        context_class: DataClass,
        track_id: str,
        max_results: int,
        lang: str | None = None,
    ) -> SearchOutcome:
        """One proposed query: classified, authorised, reserved, journaled, sent -- or refused."""
        begun = self.begin_search(
            query,
            context_class=context_class,
            track_id=track_id,
            max_results=max_results,
            lang=lang,
        )
        if isinstance(begun, SearchOutcome):
            return begun
        begun.send()
        return self.finish_search(begun)

    def begin_search(
        self,
        query: str,
        *,
        context_class: DataClass,
        track_id: str,
        max_results: int,
        lang: str | None = None,
    ) -> SearchOutcome | PendingSearch:
        """Classify, authorise, reserve and journal ``DISPATCHED``; or refuse and journal that.

        Sends nothing: a :class:`PendingSearch` is sent by its own :meth:`~PendingSearch.send`
        and closed by :meth:`finish_search`. A caller may begin several, so that every
        dispatch is on record before any of them leaves. ``lang`` asks a search adapter
        that offers languages (:class:`LanguageSearch`) for one; it is journaled with
        the query.
        """
        route = self._retrieval.search_route
        classified = classify_query(
            query,
            context_class=context_class,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        )
        cls = classified.data_class
        sent = sent_search(query, lang)
        reason = (
            "class_a_query"
            if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
            else self._refusal(route, data_class=cls)
        )
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=sent)
            record = QueryRecord(
                text=query,
                data_class=cls,
                class_reasons=classified.reasons,
                decision=QueryDecision.REFUSED,
                refusal=reason,
                call_id=None,
                hits=0,
            )
            return SearchOutcome(record, (), False)
        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=sent)
        return PendingSearch(
            query=query,
            lang=lang,
            max_results=max_results,
            track_id=track_id,
            data_class=cls,
            class_reasons=classified.reasons,
            call_id=call_id,
            reservation=reservation,
            adapter=self._retrieval.search,
        )

    def finish_search(self, pending: PendingSearch) -> SearchOutcome:
        """Journal a sent search's outcome. An adapter's unexpected error is raised here."""
        if pending.error is not None:
            raise pending.error
        route = self._retrieval.search_route
        cls, call_id, sent = pending.data_class, pending.call_id, pending.sent

        def record(*, failure: str | None = None, hits: int = 0) -> QueryRecord:
            return QueryRecord(
                text=pending.query,
                data_class=cls,
                class_reasons=pending.class_reasons,
                decision=QueryDecision.SENT,
                refusal=None,
                call_id=call_id,
                hits=hits,
                failure=failure,
            )

        fingerprint = _fingerprint(sent)
        if pending.failure is not None:
            uncertain = self._close_failure(
                route,
                pending.failure,
                call_id=call_id,
                reservation=pending.reservation,
                data_class=cls,
                track_id=pending.track_id,
                sent=sent,
            )
            return SearchOutcome(record(failure=pending.failure.reason), (), uncertain, fingerprint)
        response = pending.response
        assert response is not None, "a pending search is finished only after it was sent"
        self._meter.outcome(
            self._event(
                route,
                call_id=call_id,
                outcome=ToolOutcome.SUCCEEDED,
                data_class=cls,
                track_id=pending.track_id,
                sent=sent,
                reservation=pending.reservation,
                cost=route.price_usd_per_call,
                charged_credits=response.credits,
                provider_request_id=response.provider_request_id,
            )
        )
        return SearchOutcome(record(hits=len(response.hits)), response.hits, False, fingerprint)

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

    def _fetch_close(
        self,
        route: ToolRoute,
        *,
        call_id: str,
        reservation: ToolReservation,
        cls: DataClass,
        track_id: str,
        sent: str,
        result: _Fetched | None,
        refused: FetchRefused | None,
        failure: ToolCallFailed | None,
        request_id: Callable[[_Fetched], str | None],
        note: Callable[[_Fetched], str] = lambda _: "",
    ) -> tuple[_Fetched | None, str | None, bool]:
        """Journal a dispatched fetch's outcome: (what came back, why not, uncertain)."""
        if refused is not None:
            # Refused on a later hop or by the response itself; nothing kept. A hop
            # may already have been served, so it is charged as if it was.
            self._meter.outcome(
                self._event(
                    route,
                    call_id=call_id,
                    outcome=ToolOutcome.FAILED,
                    data_class=cls,
                    track_id=track_id,
                    sent=sent,
                    reservation=reservation,
                    cost=route.price_usd_per_call,
                    note=refused.reason,
                )
            )
            return None, refused.reason, False
        if failure is not None:
            uncertain = self._close_failure(
                route,
                failure,
                call_id=call_id,
                reservation=reservation,
                data_class=cls,
                track_id=track_id,
                sent=sent,
            )
            return None, failure.reason, uncertain
        assert result is not None, "a dispatched fetch is closed only after it was sent"
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
                provider_request_id=request_id(result),
                note=note(result),
            )
        )
        return result, None, False

    def _fetch_call(
        self,
        url: str,
        *,
        cls: DataClass,
        track_id: str,
        call: Callable[[], _Fetched],
        request_id: Callable[[_Fetched], str | None],
        note: Callable[[_Fetched], str] = lambda _: "",
    ) -> tuple[_Fetched | None, str | None, bool]:
        """Reserve, journal, send, journal: (what came back, why not, uncertain)."""
        route = self._retrieval.fetch_route
        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=url)
        result: _Fetched | None = None
        refused: FetchRefused | None = None
        failure: ToolCallFailed | None = None
        try:
            result = call()
        except FetchRefused as exc:
            refused = exc
        except ToolCallFailed as exc:
            failure = exc
        return self._fetch_close(
            route,
            call_id=call_id,
            reservation=reservation,
            cls=cls,
            track_id=track_id,
            sent=url,
            result=result,
            refused=refused,
            failure=failure,
            request_id=request_id,
            note=note,
        )

    def fetch(
        self, url: str, *, track_id: str, host_allowed: HostFilter | None = None
    ) -> FetchOutcome:
        """One page: checked, authorised, reserved, journaled, fetched -- or refused.

        ``host_allowed`` confines the fetch to the hosts it allows (a crawl's own
        host): a URL elsewhere is refused before dispatch (``host_out_of_scope``),
        a redirect elsewhere before the hop is requested (``redirect_out_of_scope``),
        and a cached page whose final URL is elsewhere is refused, not served.
        """
        begun = self.begin_fetch(url, track_id=track_id, host_allowed=host_allowed)
        if isinstance(begun, FetchOutcome):
            return begun
        begun.send()
        return self.finish_fetch(begun)

    def begin_fetch(
        self, url: str, *, track_id: str, host_allowed: HostFilter | None = None
    ) -> FetchOutcome | PendingFetch:
        """Check, classify (the whole URL: host, path and query), confine to
        ``host_allowed``, authorise; answer from the run's cache; or reserve and
        journal ``DISPATCHED``. Sends nothing (see :meth:`begin_search`)."""
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
                        url=url,
                        page=hit,
                        reason=None,
                        uncertain=False,
                        cached=True,
                        data_class=cls,
                    )
        if reason is None:
            # A robots.txt the transport already holds: refused before any dispatch.
            reason = self._retrieval.fetcher.known_refusal(url)
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=url)
            return FetchOutcome(url=url, page=None, reason=reason, uncertain=False, data_class=cls)
        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=url)
        return PendingFetch(
            url=url,
            track_id=track_id,
            data_class=cls,
            call_id=call_id,
            reservation=reservation,
            fetcher=self._retrieval.fetcher,
            host_allowed=host_allowed,
        )

    def finish_fetch(self, pending: PendingFetch) -> FetchOutcome:
        """Journal a sent fetch's outcome; cache a kept page. Unexpected errors raise here."""
        if pending.error is not None:
            raise pending.error
        url, cls, call_id = pending.url, pending.data_class, pending.call_id
        page, reason, uncertain = self._fetch_close(
            self._retrieval.fetch_route,
            call_id=call_id,
            reservation=pending.reservation,
            cls=cls,
            track_id=pending.track_id,
            sent=url,
            result=pending.page,
            refused=pending.refused,
            failure=pending.failure,
            request_id=lambda fetched: fetched.snapshot.request_id,
        )
        if page is not None and self._cache is not None:
            self._cache.put(url, page)
        return FetchOutcome(
            url=url,
            page=page,
            reason=reason,
            uncertain=uncertain,
            data_class=cls,
            call_id=call_id,
            request_fingerprint=_fingerprint(url),
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
