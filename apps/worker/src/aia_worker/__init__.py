"""AIA worker: the durable workflow engine's execution loop.

Layer 4 in ``ARCHITECTURE.md §2``. It claims steps from PostgreSQL, hands each to
the executor registered for its kind, and records the outcome -- with heartbeats,
cooperative cancellation, per-call metering and lease fencing. It performs no work
of its own; executors do, through :mod:`aia_worker.executor`.
"""

from .executor import (
    CancellationRequested,
    ExecutorRegistry,
    Failed,
    GateDecision,
    LeaseRevoked,
    NeedsApproval,
    PaidCall,
    ShutdownRequested,
    StepContext,
    StepExecutor,
    StepFailed,
    StepInput,
    StepOutcome,
    StopExecution,
    Succeeded,
)
from .settings import WorkerSettings
from .worker import AttemptResult, Worker

__all__ = [
    "AttemptResult",
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
    "Worker",
    "WorkerSettings",
]
