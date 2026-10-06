"""Triage many pages in parallel, under a limiter, through the governed gateway.

Plan ``deep-research-web-search.md`` chunk 20. :func:`triage_pages` builds one
``RESEARCH_TRIAGE`` request per page (:mod:`aia_core.domain.deep_research.triage`),
asks the caller to preflight one of them -- every request shares the capability,
class and lineage, so one refusal refuses them all, and nothing is sent -- then sends
them concurrently, never more at once than the :class:`ConcurrencyLimiter` allows, and
grounds every answer's candidate quotes before anything is returned.

**The seam.** The runner holds a :class:`TriageCaller` and nothing else: no search,
no fetch, no tool meter, so a triage reader can send nothing but its own model
request. The caller is where the worker's obligations live -- one budget reservation
per logical request (the primary and its one schema repair), dispatch journaled
before the call leaves, the reservation settled once -- as
``aia_executors.ai_step.StepModelCaller`` keeps them for one call at a time.

**The limiter** is a seam the runner asks for a slot around each send, and nothing
more. :class:`SemaphoreLimiter` bounds the calls in flight of one run of the runner;
:class:`SharedSlotLimiter` (chunk 21) puts each send in one of the deployment's model
slots (``infrastructure.fan_out_coordination.ModelSlots``: below the account's quota,
across every worker process); :class:`CombinedLimiter` holds a slot of each, so a triage
burst is bounded per run *and* across the deployment. With a shared limiter the caller
must not take a slot of its own for the same send (``StepModelCaller`` without a
``limiter``): the send would hold two.

**Failures, page by page.** A request that fails with a known outcome (a schema
violation after its repair, a provider refusal) leaves that page ``FAILED`` and the
others continue. An *uncertain* outcome stops new dispatch: pages not yet sent are
``NOT_SENT``, calls already in flight finish, and nothing is resent. Anything else the
caller raises (a budget refusal, a stop from the worker) also stops new dispatch, lets
the calls in flight finish, and is raised once they have.

**Order.** Results come back in the order the pages were given, whatever order the
answers arrived in. Which pages a stop leaves ``NOT_SENT`` depends on timing, and the
result says so page by page.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    asynccontextmanager,
)
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from aia_core.domain.ai_contracts import ModelCallFailed, ModelRequest, ModelResult
from aia_core.domain.deep_research.triage import (
    DroppedQuote,
    GroundedQuote,
    TriagePage,
    TriagePart,
    TriageQuestion,
    TriageVerdict,
    page_part,
    review_verdict,
    triage_request,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.residency import DataClass

__all__ = [
    "CombinedLimiter",
    "ConcurrencyLimiter",
    "SemaphoreLimiter",
    "SharedSlotLimiter",
    "SlotPool",
    "TriageCaller",
    "TriageOutcome",
    "TriageRun",
    "TriageStatus",
    "triage_pages",
]


class ConcurrencyLimiter(Protocol):
    """At most so many model calls in flight. Chunk 21's limiter takes this shape."""

    def slot(self) -> AbstractAsyncContextManager[None]:
        """Hold one slot for the duration of the ``async with`` block."""
        ...


class SemaphoreLimiter:
    """A bound on calls in flight, for one event loop.

    The semaphore is made on first use in the running loop, so one limiter is not
    shared by accident across ``asyncio.run`` calls (a semaphore belongs to a loop).
    """

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("a limiter allows at least one call in flight")
        self._limit = limit
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def limit(self) -> int:
        return self._limit

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._semaphore, self._loop = asyncio.Semaphore(self._limit), loop
        async with self._semaphore:
            yield


class SlotPool(Protocol):
    """Model slots shared across processes (``fan_out_coordination.ModelSlots``)."""

    def hold(
        self, *, holder_attempt_id: str, checkpoint: Callable[[], None]
    ) -> AbstractContextManager[int]:
        """Hold one slot for the block (blocking), or raise once the wait runs out."""
        ...


class SharedSlotLimiter:
    """Each send in one of the deployment's model slots, held in the attempt's name.

    The pool is synchronous (a database round trip, then a sleep while it is full), so
    the slot is taken and given back on a worker thread, never on the event loop: the
    other sends keep running while one waits. A wait that runs out raises out of the
    runner, as any refusal from the caller does once the calls in flight have finished.
    """

    def __init__(
        self,
        slots: SlotPool,
        *,
        holder_attempt_id: str,
        checkpoint: Callable[[], None] = lambda: None,
    ) -> None:
        self._slots = slots
        self._holder = holder_attempt_id
        self._checkpoint = checkpoint

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        held = self._slots.hold(holder_attempt_id=self._holder, checkpoint=self._checkpoint)
        await asyncio.to_thread(held.__enter__)
        try:
            yield
        finally:
            await asyncio.to_thread(held.__exit__, None, None, None)


class CombinedLimiter:
    """A slot of every limiter, taken in order and given back in reverse."""

    def __init__(self, *limiters: ConcurrencyLimiter) -> None:
        if not limiters:
            raise ValueError("a combined limiter combines at least one")
        self._limiters = limiters

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for limiter in self._limiters:
                await stack.enter_async_context(limiter.slot())
            yield


class TriageCaller(Protocol):
    """How the runner reaches the gateway: preflight, and one metered logical request."""

    def preflight(self, request: ModelRequest) -> object:
        """Would ``request`` be allowed out? Raise ``ModelCallFailed``; spend nothing."""
        ...

    async def invoke(self, request: ModelRequest) -> ModelResult:
        """Reserve once, send through the gateway, settle once; raise ``ModelCallFailed``."""
        ...


class TriageStatus(StrEnum):
    """What happened to one page."""

    #: Answered and reviewed; its grounded quotes may be handed off.
    TRIAGED = "TRIAGED"
    #: The request failed with a known outcome (nothing uncertain was left).
    FAILED = "FAILED"
    #: The request's outcome is unknown: never resent; new dispatch stopped.
    UNCERTAIN = "UNCERTAIN"
    #: A gate refused before anything was sent (preflight).
    REFUSED = "REFUSED"
    #: Not sent: dispatch had stopped (an uncertain outcome, or the caller stopped).
    NOT_SENT = "NOT_SENT"


@dataclass(frozen=True, slots=True)
class TriageOutcome:
    """One page's result. Only a ``TRIAGED``, relevant page hands anything off."""

    snapshot_id: str
    status: TriageStatus
    part: TriagePart
    relevant: bool = False
    sub_question: str | None = None
    quotes: tuple[GroundedQuote, ...] = ()
    dropped: tuple[DroppedQuote, ...] = ()
    #: The verdict's rejection, the gateway's failure reason, or the refusal.
    reason: str = ""
    call_ids: tuple[str, ...] = ()
    cost_usd: float = 0.0

    @property
    def hand_off(self) -> tuple[GroundedQuote, ...]:
        """What an investigator may see: grounded quotes of a relevant, triaged page."""
        if self.status is TriageStatus.TRIAGED and self.relevant:
            return self.quotes
        return ()


@dataclass(frozen=True, slots=True)
class TriageRun:
    """Every page's outcome, in the order the pages were given, and the counts."""

    outcomes: tuple[TriageOutcome, ...]
    #: Set when dispatch stopped early: the first uncertain page, or the refusal.
    stopped: str = ""
    by_status: dict[str, int] = field(default_factory=dict)
    dropped_by_reason: dict[str, int] = field(default_factory=dict)

    @property
    def relevant(self) -> tuple[TriageOutcome, ...]:
        """Triaged pages the reader judged relevant (with or without a grounded quote)."""
        return tuple(o for o in self.outcomes if o.status is TriageStatus.TRIAGED and o.relevant)

    @property
    def quotes_grounded(self) -> int:
        return sum(len(o.hand_off) for o in self.outcomes)

    @property
    def quotes_dropped(self) -> int:
        return sum(len(o.dropped) for o in self.outcomes)

    @property
    def cost_usd(self) -> float:
        return sum(o.cost_usd for o in self.outcomes)


def _counted(outcomes: Sequence[TriageOutcome], stopped: str) -> TriageRun:
    return TriageRun(
        outcomes=tuple(outcomes),
        stopped=stopped,
        by_status=dict(sorted(Counter(o.status.value for o in outcomes).items())),
        dropped_by_reason=dict(
            sorted(Counter(d.reason for o in outcomes for d in o.dropped).items())
        ),
    )


async def triage_pages(
    pages: Sequence[TriagePage],
    questions: Sequence[TriageQuestion],
    *,
    caller: TriageCaller,
    limiter: ConcurrencyLimiter,
    data_class: DataClass,
    lineage: DataLineage,
    policy_version: str,
    max_output_tokens: int,
) -> TriageRun:
    """Triage ``pages`` against ``questions``; see the module docstring for the rules."""
    ids = [p.snapshot_id for p in pages]
    if len(set(ids)) != len(ids):
        raise ValueError("a page is triaged once per run")
    parts = [page_part(p.text) for p in pages]
    requests = [
        triage_request(
            page,
            part,
            questions,
            data_class=data_class,
            lineage=lineage,
            policy_version=policy_version,
            max_output_tokens=max_output_tokens,
        )
        for page, part in zip(pages, parts, strict=True)
    ]
    if not requests:
        return _counted((), "")
    try:
        caller.preflight(requests[0])
    except ModelCallFailed as refused:
        return _counted(
            [
                TriageOutcome(p.snapshot_id, TriageStatus.REFUSED, part, reason=refused.reason)
                for p, part in zip(pages, parts, strict=True)
            ],
            f"refused:{refused.reason}",
        )

    results: list[TriageOutcome | None] = [None] * len(pages)
    stop: list[str] = []
    fatal: list[BaseException] = []

    async def one(index: int) -> None:
        page, part, request = pages[index], parts[index], requests[index]
        async with limiter.slot():
            if stop:
                results[index] = TriageOutcome(
                    page.snapshot_id, TriageStatus.NOT_SENT, part, reason=stop[0]
                )
                return
            try:
                answer = await caller.invoke(request)
            except ModelCallFailed as failed:
                spent = sum(e.cost_usd for e in failed.usage_events if e.outcome.is_terminal)
                calls = tuple(dict.fromkeys(e.call_id for e in failed.usage_events))
                if failed.outcome_known:
                    status = TriageStatus.FAILED
                else:
                    status = TriageStatus.UNCERTAIN
                    stop.append(f"uncertain:{page.snapshot_id}")
                results[index] = TriageOutcome(
                    page.snapshot_id,
                    status,
                    part,
                    reason=failed.reason,
                    call_ids=calls,
                    cost_usd=spent,
                )
                return
            except asyncio.CancelledError:
                raise
            except BaseException as error:  # a budget refusal or the worker's stop
                stop.append(f"stopped:{type(error).__name__}")
                fatal.append(error)
                results[index] = TriageOutcome(
                    page.snapshot_id, TriageStatus.NOT_SENT, part, reason=stop[0]
                )
                return
        verdict = answer.output
        if not isinstance(verdict, TriageVerdict):  # pragma: no cover - the gateway validated
            raise TypeError("a triage answer is a TriageVerdict")
        review = review_verdict(page, part, questions, verdict)
        results[index] = TriageOutcome(
            page.snapshot_id,
            TriageStatus.TRIAGED,
            part,
            relevant=review.relevant,
            sub_question=review.sub_question,
            quotes=review.quotes,
            dropped=review.dropped,
            reason=review.rejected,
            call_ids=tuple(dict.fromkeys(e.call_id for e in answer.usage_events)),
            cost_usd=answer.total_cost_usd,
        )

    await asyncio.gather(*(one(i) for i in range(len(pages))))
    if fatal:
        raise fatal[0]
    done = [r for r in results if r is not None]
    assert len(done) == len(pages)
    return _counted(done, stop[0] if stop else "")
