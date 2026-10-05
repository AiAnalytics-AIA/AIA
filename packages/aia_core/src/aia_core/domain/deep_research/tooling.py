"""The cost contract for non-model tools: web search and fetch (plan decision I-6).

A search or a page fetch through a provider can cost money exactly as a model
call does, so it gets the same bracket a model call has in
``docs/architecture/ai-step-executor-contract.md``: **reserve → dispatching →
send → outcome**. ``dispatching`` is recorded, durably, before anything leaves the
process, and an outcome whose delivery is unknown is carried at its ceiling,
never as a free call.

What does not exist yet is a place for these entries in the study's budget: the
usage ledger (``ai_usage_events``) and ``StepContext.reserve`` speak only of model
providers. Until the generalized ledger lands (PROGRESS *Next* 2, a migration), a
:class:`ToolMeter` says whether it charges the study budget
(:attr:`ToolMeter.charges_study_budget`), and the retrieval gate refuses a route
with a price when it does not. Recorded routes have no price and say so.

Pure: stdlib and Pydantic only. :class:`InMemoryToolLedger` keeps its entries in
memory; a worker's meter journals them through the step's context.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..residency import DataClass, ProviderRoute
from .contracts import RetrievalMode

__all__ = [
    "TOOL_EVENT_KINDS",
    "InMemoryToolLedger",
    "ToolBudgetExhausted",
    "ToolKind",
    "ToolMeter",
    "ToolOutcome",
    "ToolReservation",
    "ToolRoute",
    "ToolUsageEvent",
    "new_tool_call_id",
    "new_tool_event_id",
]


def new_tool_call_id() -> str:
    """AIA's id for one tool call, fixed before dispatch and recorded first."""
    return "TOOL-" + uuid4().hex[:20]


def new_tool_event_id() -> str:
    return "TUE-" + uuid4().hex[:20]


class ToolKind(StrEnum):
    WEB_SEARCH = "web_search"
    WEB_FETCH = "web_fetch"


class ToolOutcome(StrEnum):
    """The ledger state of one tool call; the model-call ledger's vocabulary."""

    #: Written before the call leaves. Alone, it is a call whose process died in flight.
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    #: The provider answered with a failure; the outcome is known.
    FAILED = "FAILED"
    #: No answer arrived and the request may have been served (and billed).
    UNCERTAIN = "UNCERTAIN"
    #: AIA refused it before anything was sent (class, route, address, budget).
    REFUSED = "REFUSED"
    #: Answered from what this run already captured: nothing was sent, nothing charged.
    CACHED = "CACHED"

    @property
    def is_terminal(self) -> bool:
        return self is not ToolOutcome.DISPATCHED


#: Progress event messages a worker journals tool calls under (one per outcome).
TOOL_EVENT_KINDS: Final = {o: f"deep_research_tool_{o.value.lower()}" for o in ToolOutcome}


@dataclass(frozen=True, slots=True)
class ToolRoute:
    """One way a search or fetch may leave AIA: residency facts, adapter, price.

    ``route`` is an ADR 0008 route and is judged by ``evaluate_egress`` like any
    model route. A **recorded** route replays captured exchanges and costs
    nothing, which it must declare (a price of zero); a recorded route with a
    price, or a live route without an adapter id, is a configuration error.
    """

    route: ProviderRoute
    tool: ToolKind
    adapter_id: str
    retrieval_mode: RetrievalMode
    price_usd_per_call: float

    def __post_init__(self) -> None:
        if not self.adapter_id.strip():
            raise ValueError("a tool route names the adapter that carries it")
        if not math.isfinite(self.price_usd_per_call) or self.price_usd_per_call < 0:
            raise ValueError("a tool price is a finite, non-negative number")
        if self.retrieval_mode is RetrievalMode.RECORDED and self.price_usd_per_call != 0:
            raise ValueError("a recorded route replays captured exchanges; it has no price")

    @property
    def route_id(self) -> str:
        return self.route.route_id


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolReservation(_Closed):
    """Budget held for one tool call before it is made."""

    reservation_id: str
    tool: ToolKind
    route_id: str
    track_id: str
    amount_usd: float = Field(ge=0.0)


class ToolUsageEvent(_Closed):
    """One entry in the tool-call journal. Append-only, like ``AIUsageEvent``.

    ``request_fingerprint`` identifies what was sent (the query, or the URL), so a
    call can be reconciled with a provider's records without storing a client's
    query text in the provider-facing log. ``credits`` is the provider's own unit
    (a search credit), ``cost_usd`` AIA's charge for it; an uncertain call is
    charged ``ceiling_usd``.
    """

    event_id: str
    call_id: str
    tool: ToolKind
    outcome: ToolOutcome
    route_id: str
    retrieval_mode: RetrievalMode
    data_class: DataClass
    track_id: str
    reservation_id: str | None
    request_fingerprint: str
    provider_request_id: str | None
    credits: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    ceiling_usd: float = Field(ge=0.0)
    occurred_at: datetime
    note: str = Field(default="", max_length=500)


class ToolBudgetExhausted(Exception):
    """A tool reservation does not fit what is left. Park and ask; never overspend."""

    def __init__(self, *, requested: float, remaining: float) -> None:
        super().__init__(f"tool call needs ${requested:.6f}; ${remaining:.6f} remains")
        self.requested = requested
        self.remaining = remaining


class ToolMeter(Protocol):
    """Reserve, journal and charge tool calls. The executor side of the cost contract."""

    @property
    def charges_study_budget(self) -> bool:
        """True only when reservations are held against the study's own budget."""
        ...

    def reserve(
        self, *, tool: ToolKind, route_id: str, track_id: str, amount_usd: float
    ) -> ToolReservation:
        """Hold budget for one call, or raise :class:`ToolBudgetExhausted`."""
        ...

    def dispatching(self, event: ToolUsageEvent) -> None:
        """Record that a call is about to leave. **Durable** by the time it returns."""
        ...

    def outcome(self, event: ToolUsageEvent) -> None:
        """Record a call's terminal entry and settle its reservation."""
        ...

    def committed_usd(self) -> float:
        """What terminal entries have charged so far."""
        ...

    def events(self) -> tuple[ToolUsageEvent, ...]:
        """Every entry recorded through this meter, in order."""
        ...


@dataclass(slots=True)
class InMemoryToolLedger:
    """A :class:`ToolMeter` over a ceiling, in memory. It never charges a study.

    Used by tests and inside a worker's meter, which adds the durable journal.
    """

    budget_usd: float
    _events: list[ToolUsageEvent] = field(default_factory=list)
    _held: dict[str, float] = field(default_factory=dict)
    _spent: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.budget_usd) or self.budget_usd < 0:
            raise ValueError("a tool budget is a finite, non-negative amount")

    @property
    def charges_study_budget(self) -> bool:
        return False

    def reserve(
        self, *, tool: ToolKind, route_id: str, track_id: str, amount_usd: float
    ) -> ToolReservation:
        if not math.isfinite(amount_usd) or amount_usd < 0:
            raise ValueError("a reservation is a finite, non-negative amount")
        remaining = self.budget_usd - self._spent - sum(self._held.values())
        if amount_usd > remaining + 1e-12:
            raise ToolBudgetExhausted(requested=amount_usd, remaining=max(0.0, remaining))
        reservation = ToolReservation(
            reservation_id="TRS-" + uuid4().hex[:20],
            tool=tool,
            route_id=route_id,
            track_id=track_id,
            amount_usd=amount_usd,
        )
        self._held[reservation.reservation_id] = amount_usd
        return reservation

    def dispatching(self, event: ToolUsageEvent) -> None:
        if event.outcome is not ToolOutcome.DISPATCHED:
            raise ValueError("dispatching records a DISPATCHED entry")
        if event.reservation_id is not None and event.reservation_id not in self._held:
            raise ValueError("dispatch names a reservation this ledger does not hold")
        self._events.append(event)

    def outcome(self, event: ToolUsageEvent) -> None:
        if not event.outcome.is_terminal:
            raise ValueError("an outcome is a terminal entry")
        if event.outcome is ToolOutcome.CACHED and (event.cost_usd or event.reservation_id):
            raise ValueError("a cached answer sent nothing: it holds and costs nothing")
        if event.outcome not in (ToolOutcome.REFUSED, ToolOutcome.CACHED) and not any(
            e.call_id == event.call_id and e.outcome is ToolOutcome.DISPATCHED for e in self._events
        ):
            raise ValueError("an outcome closes a dispatched call")
        charge = event.ceiling_usd if event.outcome is ToolOutcome.UNCERTAIN else event.cost_usd
        if event.reservation_id is not None:
            self._held.pop(event.reservation_id, None)
        self._spent += charge
        self._events.append(event)

    def adopt(
        self, journal: Sequence[ToolUsageEvent], *, closed_at: datetime
    ) -> tuple[ToolUsageEvent, ...]:
        """Take over what earlier attempts of a step journaled, and close what they left open.

        Every entry is kept once (by its id), and each terminal entry's charge counts
        as spent: its reservation went with its attempt. A ``DISPATCHED`` entry with no
        terminal entry is a call whose process stopped in flight -- it died, or lost
        its lease -- so it may have been served: it is closed ``UNCERTAIN``, charged at
        its ceiling, and never sent again. Returns those closures, for the caller to
        journal. Only an empty ledger adopts: the journal is history, not a reservation.
        """
        if self._events or self._held:
            raise ValueError("a ledger adopts a journal before its own first entry")
        seen: set[str] = set()
        closed = {e.call_id for e in journal if e.outcome.is_terminal}
        open_calls: dict[str, ToolUsageEvent] = {}
        for event in journal:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            self._events.append(event)
            if event.outcome.is_terminal:
                self._spent += (
                    event.ceiling_usd if event.outcome is ToolOutcome.UNCERTAIN else event.cost_usd
                )
            elif event.call_id not in closed:
                open_calls.setdefault(event.call_id, event)
        closures = tuple(
            ToolUsageEvent.model_validate(
                {
                    **dispatched.model_dump(),
                    "event_id": new_tool_event_id(),
                    "outcome": ToolOutcome.UNCERTAIN,
                    "provider_request_id": None,
                    "credits": 0,
                    "cost_usd": 0.0,
                    "occurred_at": closed_at,
                    "note": "its attempt stopped before the outcome was recorded",
                }
            )
            for dispatched in open_calls.values()
        )
        for closure in closures:
            self._events.append(closure)
            self._spent += closure.ceiling_usd
        return closures

    def committed_usd(self) -> float:
        return self._spent

    def events(self) -> tuple[ToolUsageEvent, ...]:
        return tuple(self._events)
