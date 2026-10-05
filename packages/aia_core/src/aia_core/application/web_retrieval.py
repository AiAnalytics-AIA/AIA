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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.classification import classify_query
from ..domain.deep_research.contracts import (
    ClientTerm,
    QueryDecision,
    QueryRecord,
    RetrievalMode,
)
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
from ..domain.deep_research.web import FetchRefused, SearchHit, check_url
from ..domain.residency import DataClass, EgressDenied, evaluate_egress
from ..domain.scope import ScopeDenied, ScopeGrant, StudyContext
from ..infrastructure.web_retrieval import FetchedPage, SearchAdapter, ToolCallFailed, WebFetcher

__all__ = ["FetchOutcome", "RetrievalGate", "SearchOutcome", "WebRetrieval"]


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


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    url: str
    page: FetchedPage | None
    #: Why nothing was kept: a refusal before sending, or the failure after.
    reason: str | None
    uncertain: bool


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

    def fetch(self, url: str, *, track_id: str) -> FetchOutcome:
        """One page a search returned: checked, authorised, reserved, journaled, fetched."""
        route = self._retrieval.fetch_route
        cls = classify_query(
            url,
            context_class=DataClass.CLASS_C_INTERNAL,
            client_terms=self._terms,
            class_a_texts=self._class_a,
        ).data_class
        reason: str | None
        try:
            check_url(url)
        except FetchRefused as exc:
            reason = exc.reason
        else:
            reason = (
                "class_a_url"
                if cls is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
                else self._refusal(route, data_class=cls)
            )
        if reason is None:
            # A robots.txt the transport already holds: refused before any dispatch.
            reason = self._retrieval.fetcher.known_refusal(url)
        if reason is not None:
            self._refuse(route, reason=reason, data_class=cls, track_id=track_id, sent=url)
            return FetchOutcome(url=url, page=None, reason=reason, uncertain=False)

        call_id, reservation = self._open(route, data_class=cls, track_id=track_id, sent=url)
        try:
            page = self._retrieval.fetcher.fetch(url)
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
            return FetchOutcome(url=url, page=None, reason=exc.reason, uncertain=False)
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
            return FetchOutcome(url=url, page=None, reason=exc.reason, uncertain=uncertain)
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
                provider_request_id=page.snapshot.request_id,
            )
        )
        return FetchOutcome(url=url, page=page, reason=None, uncertain=False)
