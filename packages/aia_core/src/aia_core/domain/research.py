"""How a research run's canonical state reads to a person (ADR 0016 decision 2).

The engine's :class:`~aia_core.domain.workflow.WorkflowRunStatus` is the state;
this module only groups it into the six phases a researcher needs -- queued,
running, waiting, completed, failed, cancelled -- and says whether a run may be
retried. No state is invented and no percentage is computed: progress is the
steps' own checkpoints. Pure: no I/O.
"""

from __future__ import annotations

from enum import StrEnum

from .workflow import WorkflowRunStatus

__all__ = ["ResearchPhase", "phase_of", "retryable"]


class ResearchPhase(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_WAITING = frozenset(
    {
        WorkflowRunStatus.AWAITING_GATE,
        WorkflowRunStatus.AWAITING_BUDGET,
        WorkflowRunStatus.WAITING_PROVIDER,
        WorkflowRunStatus.WAITING_CAPACITY,
        WorkflowRunStatus.RECOVERY_REQUIRED,
    }
)


def phase_of(status: WorkflowRunStatus, *, attempted: bool) -> ResearchPhase:
    """The phase a run is in. A run no worker has attempted a step of is queued.

    Not ``started_at``: the engine derives ``RUNNING`` -- and stamps it -- as soon
    as the first step is runnable, which is at creation, before any worker exists.
    """
    if status is WorkflowRunStatus.COMPLETED:
        return ResearchPhase.COMPLETED
    if status is WorkflowRunStatus.FAILED:
        return ResearchPhase.FAILED
    if status is WorkflowRunStatus.CANCELLED:
        return ResearchPhase.CANCELLED
    if status in _WAITING:
        return ResearchPhase.WAITING
    return ResearchPhase.RUNNING if attempted else ResearchPhase.QUEUED


def retryable(status: WorkflowRunStatus) -> bool:
    """True when starting the run again could end differently.

    A failed or cancelled run may be retried, as a new run linked to it. A waiting
    run may not: it resumes when what it waits for arrives, and a retry would wait
    for the same thing.
    """
    return status in (WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED)
