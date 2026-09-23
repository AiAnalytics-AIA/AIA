"""The contract between the AI runtime and the step executor.

This is the **whole** surface the workflow side (platform-runtime) and the AI
side (ai-runtime) share. It is deliberately small, so that neither side edits the
other's implementation to integrate: the step executor builds an
:class:`ExecutionContext`, calls :meth:`ModelGateway.invoke`, and turns a
:class:`~aia_core.domain.ai_contracts.ModelCallFailed` into ``fail_attempt``
arguments with :func:`recovery_inputs`. Everything else is private to one side.
See ``docs/architecture/ai-step-executor-contract.md``.

Three obligations run across the boundary, and each exists because its absence
double-bills a client or loses a record:

1. **Scope is issued, never supplied.** The context holds a ``StudyContext`` from
   the authorization layer. Neither a request, nor a tool argument, nor a model's
   output can name whose data a call carries (``ExecutionContext.__post_init__``
   refuses anything else, by type).
2. **The budget is the reservation.** The step executor reserves budget through
   ``WorkflowRepository.reserve_budget`` before invoking, and passes the
   reservation it got back. The gateway checks each call's ceiling against it.
   A reservation amount taken from a request would be a budget the caller
   chose for itself.
3. **Dispatch is durable before the call leaves.** :meth:`CallJournal.record_dispatch`
   must have *committed* by the time it returns. A flushed-but-uncommitted
   dispatch mark rolls back with a dying worker, the lapsed lease then looks
   safe to retry, and the retry is a second paid call for the same work.

No I/O here: the journal is a protocol the step executor implements.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from .ai_contracts import AIUsageEvent, ModelCallFailed, ModelRequest, ModelResult
from .scope import ScopeDenied, ScopeGrant, StudyContext
from .workflow import FailureClass

__all__ = [
    "CallJournal",
    "ExecutionContext",
    "ModelGateway",
    "RecoveryInputs",
    "ReservationView",
    "recovery_inputs",
]


class CallJournal(Protocol):
    """Where the gateway records calls, in order, as they happen.

    Implemented by the step executor over the durable store. The gateway never
    touches ``StepAttempt`` or the usage ledger directly; it tells the journal,
    and the journal decides how that becomes rows.
    """

    def record_dispatch(self, event: AIUsageEvent) -> None:
        """Record that a call is about to leave the process. **Must be committed.**

        For a paid provider this is where the attempt is marked
        ``paid_call_dispatched`` -- from here on a lapsed lease is
        ``RECOVERY_REQUIRED``, never a retry.
        """
        ...

    def record_outcome(self, event: AIUsageEvent) -> None:
        """Record a call's terminal ledger entry.

        Unless ``event.outcome`` is ``UNCERTAIN``, the call's outcome is now known
        and the attempt's billing question is closed at ``event.cost_usd``.
        """
        ...

    def committed_usd(self) -> float:
        """Spend already recorded against this attempt's reservation."""
        ...


@dataclass(frozen=True, slots=True)
class ReservationView:
    """The budget reservation the durable layer granted for this attempt."""

    reservation_id: str
    amount_usd: float

    def __post_init__(self) -> None:
        if not self.reservation_id.strip():
            raise ValueError("a reservation needs an id")
        if self.amount_usd < 0:
            raise ValueError("a reservation cannot be negative")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _never_cancelled() -> bool:
    return False


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Everything the gateway needs that a request must not be able to supply.

    ``scope`` is an issued :class:`StudyContext`. ``reservation`` comes from the
    workflow repository, not the caller. ``journal`` is the durable record.
    ``is_cancelled`` is polled at checkpoints (cooperative cancellation, as the
    workflow engine already does between steps). ``clock`` is injectable so
    ledger timestamps are testable.
    """

    scope: StudyContext
    runtime_version: str
    journal: CallJournal
    run_id: str | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    reservation: ReservationView | None = None
    is_cancelled: Callable[[], bool] = field(default=_never_cancelled)
    clock: Callable[[], datetime] = field(default=_utcnow)

    def __post_init__(self) -> None:
        # By type, not by shape: a dict with the right keys, or any object a model
        # could have produced, is refused. Only the authorization layer can issue
        # a StudyContext, and layer_check keeps it that way.
        if not isinstance(self.scope, StudyContext) or not isinstance(self.scope.grant, ScopeGrant):
            raise ScopeDenied(
                "model calls require an issued study context", reason="unauthorised_scope"
            )
        if not self.runtime_version.strip():
            raise ValueError("runtime_version is required for provenance")


class ModelGateway(Protocol):
    """ADR 0005 decision A: AIA's provider-neutral model call boundary."""

    async def invoke(self, request: ModelRequest, context: ExecutionContext) -> ModelResult:
        """Run one logical request, or raise :class:`ModelCallFailed`."""
        ...


@dataclass(frozen=True, slots=True)
class RecoveryInputs:
    """The arguments ``WorkflowRepository.fail_attempt`` takes, from a failure."""

    failure: FailureClass
    quota_reset_at: datetime | None
    error: Mapping[str, Any]


def recovery_inputs(error: ModelCallFailed) -> RecoveryInputs:
    """Translate a gateway failure into ``fail_attempt`` arguments.

    The billing flags are *not* passed: ``fail_attempt`` reads
    ``paid_call_dispatched`` and ``paid_call_outcome_known`` from the attempt
    row, which the journal already wrote. Passing them again would create a
    second source of the one fact ``decide_recovery`` must get right.
    """
    return RecoveryInputs(
        failure=error.failure,
        quota_reset_at=error.retry_after,
        error={
            "reason": error.reason,
            "message": str(error),
            "error_kind": error.error_kind.value if error.error_kind else None,
            "provider_request_id": error.provider_request_id,
            "violations": list(error.violations),
            "call_ids": sorted({e.call_id for e in error.usage_events}),
        },
    )
