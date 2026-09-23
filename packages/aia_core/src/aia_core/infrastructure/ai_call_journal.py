"""Call journals: where the model gateway records each call as it happens.

:class:`~aia_core.domain.ai_execution.CallJournal` is the contract; this module
holds its implementations.

* :class:`WorkflowCallJournal` -- the durable one. Writes the usage ledger and
  marks the attempt through ``WorkflowRepository``'s **public** methods only, so
  the AI runtime integrates with the workflow engine without editing it.
* :class:`InMemoryCallJournal` -- the test double, and the reference for what
  the durable one must observe.
"""

from __future__ import annotations

from collections.abc import Callable

from aia_core.domain.ai_contracts import AIUsageEvent, CostBasis, UsageOutcome

from .ai_usage_repository import AIUsageRepository
from .workflow_repository import WorkflowRepository

__all__ = ["InMemoryCallJournal", "WorkflowCallJournal"]


def _is_metered(event: AIUsageEvent) -> bool:
    return event.cost_basis is not CostBasis.SUBSCRIPTION


class WorkflowCallJournal:
    """The journal over the workflow attempt and the usage ledger.

    ``commit`` is called after the dispatch record and after each outcome. It
    is injected because the step executor owns the transaction; it is required
    because a dispatch mark that is only *flushed* rolls back with a dying
    worker, the lapsed lease then looks safe to retry, and the retry is a
    second paid call for work that may already have been billed.

    ``committed_usd`` counts every terminal entry this journal wrote, uncertain
    ones at their ceiling. It starts from the attempt's own ledger entries, so a
    journal rebuilt mid-attempt does not forget what was already spent.
    """

    def __init__(
        self,
        *,
        workflow: WorkflowRepository,
        usage: AIUsageRepository,
        attempt_id: str,
        commit: Callable[[], None],
    ) -> None:
        if workflow.scope is not usage.scope:
            raise ValueError("workflow and usage repositories must share one scope")
        self._workflow = workflow
        self._usage = usage
        self._attempt_id = attempt_id
        self._commit = commit
        self._committed = sum(
            e.cost_usd for e in usage._events(attempt_id=attempt_id) if e.outcome.is_terminal
        )

    def record_dispatch(self, event: AIUsageEvent) -> None:
        if event.attempt_id != self._attempt_id:
            raise ValueError("dispatch is for a different attempt")
        self._usage.append(event)
        if _is_metered(event):
            self._workflow.mark_paid_call_dispatched(self._attempt_id)
        self._commit()

    def record_outcome(self, event: AIUsageEvent) -> None:
        if event.attempt_id != self._attempt_id:
            raise ValueError("outcome is for a different attempt")
        self._usage.append(event)
        self._committed += event.cost_usd
        if _is_metered(event) and event.outcome is not UsageOutcome.UNCERTAIN:
            # Known outcome: the billing question for this attempt is closed at
            # the cumulative figure. An UNCERTAIN outcome deliberately leaves the
            # attempt dispatched-and-unknown, which is what makes fail_attempt
            # choose RECOVERY_REQUIRED instead of a retry.
            self._workflow.mark_paid_call_outcome_known(
                self._attempt_id,
                actual_cost_usd=self._committed,
                provider_request_id=event.provider_request_id,
            )
        self._commit()

    def committed_usd(self) -> float:
        return self._committed


class InMemoryCallJournal:
    """Records every journal call in order. Nothing is durable.

    ``committed_usd`` sums the terminal entries, which is the rule any durable
    journal must also follow: an uncertain call counts at its ceiling, because
    money that may be gone is not headroom.
    """

    def __init__(self) -> None:
        self.dispatched: list[AIUsageEvent] = []
        self.outcomes: list[AIUsageEvent] = []

    def record_dispatch(self, event: AIUsageEvent) -> None:
        if event.outcome is not UsageOutcome.DISPATCHED:
            raise ValueError("record_dispatch takes a DISPATCHED entry")
        self.dispatched.append(event)

    def record_outcome(self, event: AIUsageEvent) -> None:
        if not event.outcome.is_terminal:
            raise ValueError("record_outcome takes a terminal entry")
        if event.call_id not in {e.call_id for e in self.dispatched}:
            raise ValueError(f"outcome for {event.call_id}, which was never dispatched")
        self.outcomes.append(event)

    def committed_usd(self) -> float:
        return sum(e.cost_usd for e in self.outcomes)
