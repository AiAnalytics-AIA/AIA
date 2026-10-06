"""The bridge from the worker's ``StepContext`` to ``GovernedModelGateway`` (the contract's ask 1).

``docs/architecture/ai-step-executor-contract.md`` fixes three obligations across
this seam; this module is where a step executor keeps them without editing either
side:

1. **Scope is issued, never supplied.** The ``ExecutionContext`` gets
   ``StepContext.scope`` -- the Study scope ``ScopeResolver`` issued against the held
   lease -- and the run, step and attempt ids of the claimed attempt.
2. **The budget is the reservation (PROGRESS D11, resolved here).** One reservation
   per *logical request*: :meth:`StepModelCaller.invoke` reserves through
   ``StepContext.reserve``, the gateway checks every call it makes (the primary and
   an allowed schema repair) against that reservation plus what the request has
   already spent, and the reservation is settled **once**, with the request's total,
   when ``invoke`` returns or fails with a known outcome. Settling per call would
   no-op the repair's cost: a reservation settles only once.
3. **Dispatch is durable, and fenced, before the call leaves.** ``record_dispatch``
   calls ``StepContext.dispatching`` -- a checkpoint (a cancelled, stopping or
   lease-less executor stops *here*, before money) and the fenced, committed
   ``paid_call_dispatched`` mark -- and then commits the ``DISPATCHED`` ledger row.
   ``record_outcome`` commits the terminal row through ``StepContext.record_usage``,
   which is deliberately unfenced: a lease lost mid-call still leaves the provider's
   answer on the ledger.

What each failure becomes is the gateway's classification, passed on unchanged as
a :class:`~aia_worker.executor.StepFailed`; the worker's ``fail_attempt`` reads
the billing flags from the attempt row. An uncertain outcome is left dispatched
and unsettled, so recovery is ``RECOVERY_REQUIRED`` -- never an automatic retry.
No fallback policy is built here: a request carries none, so none can run.

Long calls: ``invoke`` blocks this thread; the worker's heartbeat thread keeps the
lease and carries cancellation meanwhile, and the next checkpoint acts on it.

**Concurrency** (Deep Research fan-out, ``docs/architecture/deep-research-fan-out.md``
section 4). Given a ``limiter`` -- the deployment's model slots for the route -- ``invoke``
holds one slot around the whole logical request: the reservation, the call, its one
schema repair, the settlement. The slot is taken *before* the reservation, so a request
waiting for one holds no budget; the wait checkpoints, so a cancelled or stopping step
stops waiting; and a wait that runs out is ``PROVIDER_CAPACITY`` -- nothing reserved,
nothing sent -- which parks the step ``WAITING_CAPACITY`` without consuming an attempt.
Without a limiter nothing changes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import (
    AIUsageEvent,
    CostBasis,
    ModelCallFailed,
    ModelRequest,
    ModelResult,
    UsageOutcome,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView, recovery_inputs
from aia_core.domain.ai_models import ModelResolution
from aia_core.domain.providers import Provider
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.fan_out_coordination import ModelSlotsBusy
from aia_worker.executor import PaidCall, StepContext, StepFailed, StopExecution

__all__ = ["MODEL_CONCURRENCY_WAIT", "ModelConcurrency", "StepCallJournal", "StepModelCaller"]

#: Why a request failed before anything was reserved: no model slot came free.
MODEL_CONCURRENCY_WAIT = "model_concurrency_wait"


class ModelConcurrency(Protocol):
    """Model requests in flight, bounded across processes (``fan_out_coordination.ModelSlots``)."""

    def hold(
        self, *, holder_attempt_id: str, checkpoint: Callable[[], None]
    ) -> AbstractContextManager[int]:
        """Hold one slot for the block, or raise ``ModelSlotsBusy`` past the wait."""
        ...


class StepCallJournal:
    """``CallJournal`` for one logical request, over ``StepContext``."""

    def __init__(self, context: StepContext, call: PaidCall) -> None:
        self._context = context
        self._call = call
        self._spent = 0.0
        self.uncertain = False

    def record_dispatch(self, event: AIUsageEvent) -> None:
        if event.attempt_id != self._context.step.attempt_id:
            raise ValueError("dispatch is for a different attempt")
        if event.cost_basis is not CostBasis.SUBSCRIPTION:
            # Checkpoint + the fenced, committed dispatch mark. Raises StopExecution
            # (cancelled, stopping, lease lost) before anything is written or sent.
            self._context.dispatching(self._call)
        else:
            self._context.checkpoint()
        self._context.record_usage(event)

    def record_outcome(self, event: AIUsageEvent) -> None:
        if event.attempt_id != self._context.step.attempt_id:
            raise ValueError("outcome is for a different attempt")
        self._context.record_usage(event)
        self._spent += event.cost_usd
        if event.outcome is UsageOutcome.UNCERTAIN:
            self.uncertain = True

    def committed_usd(self) -> float:
        return self._spent


class StepModelCaller:
    """The only way a step executor calls a model: one gateway, one attempt, one scope."""

    def __init__(
        self,
        *,
        gateway: GovernedModelGateway,
        context: StepContext,
        runtime_version: str,
        provider: Provider,
        reservation_usd: float,
        limiter: ModelConcurrency | None = None,
    ) -> None:
        if reservation_usd <= 0:
            raise ValueError("a metered request needs a positive reservation")
        self._gateway = gateway
        self._context = context
        self._runtime_version = runtime_version or "unknown-build"
        self._provider = provider
        self._reservation_usd = reservation_usd
        self._limiter = limiter

    def _stop_requested(self) -> bool:
        try:
            self._context.checkpoint()
        except StopExecution:
            return True
        return False

    def _execution_context(self, journal: object, call: PaidCall | None) -> ExecutionContext:
        step = self._context.step
        reservation = (
            ReservationView(call.reservation_id, call.amount_usd)
            if call is not None and call.reservation_id is not None
            else None
        )
        return ExecutionContext(
            scope=self._context.scope,
            runtime_version=self._runtime_version,
            journal=journal,  # type: ignore[arg-type]
            run_id=step.run_id,
            step_id=step.step_id,
            attempt_id=step.attempt_id,
            reservation=reservation,
            is_cancelled=self._stop_requested,
        )

    def preflight(self, request: ModelRequest) -> ModelResolution:
        """Would ``request`` be allowed out? Raises ``ModelCallFailed``; spends nothing."""
        return self._gateway.preflight(request, self._execution_context(_NoJournal(), None))

    def invoke(self, request: ModelRequest) -> ModelResult:
        """Reserve, send through the gateway, settle once. Raises ``StepFailed`` on failure.

        ``BudgetExceeded`` from the reservation and every ``StopExecution`` propagate
        untouched: the worker turns them into a budget park, an abandoned attempt, a
        released attempt or a discarded result. With a limiter, the request first
        waits for a model slot (see the module docstring).
        """
        if self._limiter is None:
            return self._invoke(request)
        try:
            slot = self._limiter.hold(
                holder_attempt_id=self._context.step.attempt_id,
                checkpoint=self._context.checkpoint,
            )
            with slot:
                return self._invoke(request)
        except ModelSlotsBusy as busy:
            raise StepFailed(
                FailureClass.PROVIDER_CAPACITY,
                str(busy),
                error={
                    "reason": MODEL_CONCURRENCY_WAIT,
                    "pool": busy.pool,
                    "limit": busy.limit,
                    "waited_s": round(busy.waited_s, 1),
                },
            ) from busy

    def _invoke(self, request: ModelRequest) -> ModelResult:
        call = self._context.reserve(
            amount_usd=self._reservation_usd,
            provider=self._provider,
            reason=f"{request.agent.agent_id}:{request.agent.version}",
        )
        journal = StepCallJournal(self._context, call)
        try:
            result = asyncio.run(
                self._gateway.invoke(request, self._execution_context(journal, call))
            )
        except ModelCallFailed as failure:
            if failure.outcome_known and not journal.uncertain:
                self._context.settled(
                    call,
                    actual_cost_usd=journal.committed_usd(),
                    provider_request_id=failure.provider_request_id,
                )
            # A cancellation or a lost lease the gateway saw as "cancelled before
            # dispatch" surfaces as itself, not as a failed attempt.
            self._context.checkpoint()
            inputs = recovery_inputs(failure)
            raise StepFailed(
                inputs.failure,
                str(failure),
                error=dict(inputs.error),
                quota_reset_at=inputs.quota_reset_at,
            ) from failure
        self._context.settled(
            call,
            actual_cost_usd=journal.committed_usd(),
            provider_request_id=result.provider_request_id,
        )
        return result


class _NoJournal:
    """Preflight writes nothing; a journal call here would be a defect."""

    def record_dispatch(self, event: AIUsageEvent) -> None:
        raise AssertionError("preflight must not dispatch")

    def record_outcome(self, event: AIUsageEvent) -> None:
        raise AssertionError("preflight must not record an outcome")

    def committed_usd(self) -> float:
        return 0.0
