"""The executor seam: the only thing a step implementation needs to know.

A worker claims a step, hands it to the :class:`StepExecutor` registered for the
step's ``kind``, and records what comes back. Everything an executor may do to the
outside world goes through the :class:`StepContext` it is given, which is what
lets the worker keep its guarantees without knowing anything about the work:

* **Checkpoints.** Call :meth:`StepContext.checkpoint` between units of work. It
  raises a :class:`StopExecution` when the step was cancelled, the worker is
  shutting down, or the lease was lost. Let it propagate.
* **Per-call metering.** Every metered provider call is bracketed:
  ``reserve`` → ``dispatching`` → *send* → ``settled`` (or ``not_billed``). Each
  step is committed before the next, so the attempt and its reservation are
  durable before any money can be spent, and a call's cost is charged the moment
  it is known.
* **Fenced writes.** :meth:`StepContext.transaction` yields a session whose
  commit holds the attempt's lease, so an executor's own writes land only while
  it still owns the step.

**Executors must be idempotent.** Execution is at-least-once: a worker that stalls
past its lease may have run an executor whose result is then discarded, and the
step runs again. Artifact reuse by input fingerprint is what makes that cheap. The
engine guarantees one *recorded* completion, one charge per call, and no automatic
re-run of a call whose billing is uncertain.

This module deliberately imports nothing domain-specific. An AI or research
executor depends on it; it never depends on them (``tools/layer_check.sh``).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from aia_core.domain.providers import Provider
from aia_core.domain.scope import StudyContext
from aia_core.domain.workflow import FailureClass, InteractionMode
from aia_core.infrastructure.workflow_repository import BudgetExceeded, WorkflowRepository
from sqlalchemy.orm import Session

__all__ = [
    "BudgetExceeded",
    "CancellationRequested",
    "ExecutorRegistry",
    "Failed",
    "GateDecision",
    "LeaseRevoked",
    "NeedsApproval",
    "PaidCall",
    "ShutdownRequested",
    "StepContext",
    "StepExecutor",
    "StepFailed",
    "StepInput",
    "StepOutcome",
    "StopExecution",
    "Succeeded",
]


# --------------------------------------------------------------------------- #
# What the executor is given
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class GateDecision:
    """A decision a person recorded on one of this step's gates."""

    gate_id: str
    gate_type: str
    option: str
    note: str
    decided_by_user_id: str | None


@dataclass(frozen=True, slots=True)
class StepInput:
    """One claimed attempt of one step, as the executor sees it.

    ``gate_decisions`` carries every decision already made on this step's gates,
    so a step that parked to ask for approval sees the answer when it runs again
    instead of asking forever.
    """

    run_id: str
    step_id: str
    attempt_id: str
    attempt_number: int
    node_key: str
    kind: str
    stage_type: str
    artifact_target: str
    input_fingerprint: str
    interaction_mode: InteractionMode
    payload: Mapping[str, Any]
    project_id: str
    project_revision: int
    gate_decisions: tuple[GateDecision, ...] = ()


@dataclass(frozen=True, slots=True)
class PaidCall:
    """A handle on one metered provider call, from :meth:`StepContext.reserve`.

    ``reservation_id`` is ``None`` for a provider with no marginal cost (a
    subscription runtime): no budget is held, and the context's metering calls
    are checkpoints only.
    """

    provider: Provider
    amount_usd: float
    reservation_id: str | None


# --------------------------------------------------------------------------- #
# What the executor returns
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Succeeded:
    """The step's work is done. ``output`` becomes the step's recorded output.

    ``actual_cost_usd`` is for metered cost that went through no reservation;
    reserved calls are charged by :meth:`StepContext.settled` as they return.
    """

    output: dict[str, Any] = field(default_factory=dict)
    actual_cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class Failed:
    """The attempt failed; ``failure`` decides whether it retries, parks or stops.

    The classification is the executor's to make, and it must be made honestly:
    ``UNKNOWN`` is permanent, because an error nobody understands must not be
    retried against a paid provider on the assumption that it is transient.

    **A provider refusal must settle its call first.** A quota or capacity
    refusal is an answer -- the outcome is known and nothing was billed -- so
    call :meth:`StepContext.not_billed` before returning ``QUOTA``. Returning it
    with the call still marked in flight parks the step *and* charges the
    reservation as uncertain (``open-items.md`` OI-21).
    """

    failure: FailureClass
    error: dict[str, Any] = field(default_factory=dict)
    quota_reset_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class NeedsApproval:
    """Park the step on a human decision.

    The worker opens the gate; when a person decides it the step runs again as
    a new attempt with the decision in :attr:`StepInput.gate_decisions`.
    """

    question: str
    options: tuple[str, ...] = ("approve", "cancel")
    context: dict[str, Any] = field(default_factory=dict)
    gate_type: str = "approval"


StepOutcome = Succeeded | Failed | NeedsApproval


class StepFailed(Exception):
    """Raise instead of returning :class:`Failed`, from deep inside a call stack."""

    def __init__(
        self,
        failure: FailureClass,
        message: str = "",
        *,
        error: dict[str, Any] | None = None,
        quota_reset_at: datetime | None = None,
    ) -> None:
        super().__init__(message or failure.value)
        self.failure = failure
        self.error = dict(error or {})
        if message and "message" not in self.error:
            self.error["message"] = message
        self.quota_reset_at = quota_reset_at


# --------------------------------------------------------------------------- #
# Control flow the executor must not swallow
# --------------------------------------------------------------------------- #


class StopExecution(BaseException):
    """Stop now; the worker decides what the attempt becomes.

    A ``BaseException``, deliberately, like ``asyncio.CancelledError``: executor
    code full of ``except Exception`` must not be able to swallow a cancellation
    or a lost lease and carry on spending money on a step it no longer owns.
    """


class CancellationRequested(StopExecution):
    """The run was cancelled. The attempt is abandoned; its hold is returned."""


class ShutdownRequested(StopExecution):
    """The worker is shutting down. The attempt is released for another worker."""


class LeaseRevoked(StopExecution):
    """This worker no longer holds the attempt. Nothing more may be written."""


# --------------------------------------------------------------------------- #
# The two protocols
# --------------------------------------------------------------------------- #


class StepContext(Protocol):
    """Everything an executor may do beyond computing.

    Each method that writes commits its own short transaction and returns; no
    transaction is held open across the executor's work.
    """

    @property
    def scope(self) -> StudyContext:
        """The execution scope: the claimed study, RESEARCHER permissions."""
        ...

    @property
    def step(self) -> StepInput:
        """The attempt being executed."""
        ...

    def checkpoint(self) -> None:
        """Raise :class:`StopExecution` if the executor must stop now."""
        ...

    def reserve(self, *, amount_usd: float, provider: Provider, reason: str = "") -> PaidCall:
        """Hold budget for one call, or raise :class:`BudgetExceeded`."""
        ...

    def dispatching(self, call: PaidCall, *, provider_request_id: str | None = None) -> None:
        """Record that ``call`` is about to be sent. Call it immediately before sending.

        Also a checkpoint: a cancelled, stopping or lease-less executor is stopped
        here, *before* the money is spent.
        """
        ...

    def settled(
        self, call: PaidCall, *, actual_cost_usd: float, provider_request_id: str | None = None
    ) -> None:
        """Record ``call``'s known outcome and charge its real cost."""
        ...

    def not_billed(self, call: PaidCall, *, provider_request_id: str | None = None) -> None:
        """Record that the provider answered ``call`` without billing it."""
        ...

    def progress(self, message: str, **payload: Any) -> None:
        """Emit a progress event: real counts and transitions, never a guess."""
        ...

    def transaction(self) -> AbstractContextManager[tuple[Session, WorkflowRepository]]:
        """A unit of work that commits only while this worker holds the lease."""
        ...


@runtime_checkable
class StepExecutor(Protocol):
    """Executes one kind of step. Registered by kind; see :data:`ExecutorRegistry`."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        """Do the step's work and say how it ended."""
        ...


ExecutorRegistry = Mapping[str, StepExecutor]
"""Step ``kind`` → the executor for it. The worker claims only these kinds."""
