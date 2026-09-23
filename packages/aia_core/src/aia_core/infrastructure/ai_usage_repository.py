"""The AI usage ledger: append, read, and resolve uncertain calls.

The ledger is authoritative for model-call cost (ADR 0006: "cost is not
aggregated from LangGraph"). It is **append-only**: this repository has no
update and no delete. A call whose billing is uncertain is closed by appending a
compensating entry, so the per-call sum of ``cost_usd`` is the truth and the way
it was reached stays on the record -- an accounting record that can be edited
after the fact cannot be reconciled against an invoice.

Every read and write is confined to one issued ``StudyContext``. An entry whose
attribution names a different study, client or organization is refused, so a
bug upstream cannot write one client's spend onto another's ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from aia_core.domain.ai_contracts import (
    AIUsageEvent,
    CallPurpose,
    CostBasis,
    FinishReason,
    ModelUsage,
    ProviderErrorKind,
    UsageOutcome,
    new_usage_event_id,
)
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import Permission, ScopeDenied, StudyContext
from aia_core.domain.workflow import FailureClass, as_utc

from .tables import AIUsageEventRow, utcnow

__all__ = ["AIUsageRepository", "LedgerConflict", "UncertainCall"]


class LedgerConflict(ValueError):
    """An append would contradict what the ledger already says."""


@dataclass(frozen=True, slots=True)
class UncertainCall:
    """A call whose billing is not known: the list someone has to reconcile.

    ``dispatched`` always exists. ``terminal`` is the ``UNCERTAIN`` entry when the
    process survived to write one, and ``None`` when it died in flight -- the
    worker-killed case, found only because the dispatch was written first.
    """

    call_id: str
    dispatched: AIUsageEvent
    terminal: AIUsageEvent | None

    @property
    def recorded_exposure_usd(self) -> float:
        """What the ledger currently carries for this call."""
        return self.terminal.cost_usd if self.terminal is not None else 0.0

    @property
    def provider_request_id(self) -> str | None:
        """The provider's id for the call, if any response carried one."""
        return self.terminal.provider_request_id if self.terminal is not None else None


def _row(event: AIUsageEvent) -> AIUsageEventRow:
    return AIUsageEventRow(
        event_id=event.event_id,
        call_id=event.call_id,
        outcome=event.outcome.value,
        purpose=event.purpose.value,
        organization_id=event.organization_id,
        client_id=event.client_id,
        study_id=event.study_id,
        actor_id=event.actor_id,
        run_id=event.run_id,
        step_id=event.step_id,
        attempt_id=event.attempt_id,
        reservation_id=event.reservation_id,
        agent_id=event.agent_id,
        agent_version=event.agent_version,
        prompt_id=event.prompt_id,
        prompt_version=event.prompt_version,
        capability=event.capability.value,
        policy_version=event.policy_version,
        runtime_version=event.runtime_version,
        provider=event.provider.value,
        model=event.model,
        served_model=event.served_model,
        route_id=event.route_id,
        data_class=event.data_class.value,
        residency_zone=event.residency_zone,
        provider_request_id=event.provider_request_id,
        error_kind=event.error_kind.value if event.error_kind else None,
        failure_class=event.failure_class.value if event.failure_class else None,
        finish_reason=event.finish_reason.value if event.finish_reason else None,
        input_tokens=event.usage.input_tokens,
        output_tokens=event.usage.output_tokens,
        cache_read_input_tokens=event.usage.cache_read_input_tokens,
        cache_write_input_tokens=event.usage.cache_write_input_tokens,
        cost_usd=event.cost_usd,
        cost_basis=event.cost_basis.value,
        ceiling_usd=event.ceiling_usd,
        schema_fingerprint=event.schema_fingerprint,
        substituted_from=event.substituted_from,
        fallback_from=event.fallback_from,
        fallback_authorised_by=event.fallback_authorised_by,
        occurred_at=event.occurred_at,
        latency_ms=event.latency_ms,
        supersedes_event_id=event.supersedes_event_id,
        note=event.note,
    )


def _event(row: AIUsageEventRow) -> AIUsageEvent:
    occurred = as_utc(row.occurred_at)
    assert occurred is not None  # non-nullable column
    return AIUsageEvent(
        event_id=row.event_id,
        call_id=row.call_id,
        outcome=UsageOutcome(row.outcome),
        purpose=CallPurpose(row.purpose),
        organization_id=row.organization_id,
        client_id=row.client_id,
        study_id=row.study_id,
        actor_id=row.actor_id,
        run_id=row.run_id,
        step_id=row.step_id,
        attempt_id=row.attempt_id,
        reservation_id=row.reservation_id,
        agent_id=row.agent_id,
        agent_version=row.agent_version,
        prompt_id=row.prompt_id,
        prompt_version=row.prompt_version,
        capability=ModelCapability(row.capability),
        policy_version=row.policy_version,
        runtime_version=row.runtime_version,
        provider=Provider(row.provider),
        model=row.model,
        served_model=row.served_model,
        route_id=row.route_id,
        data_class=DataClass(row.data_class),
        residency_zone=row.residency_zone,
        provider_request_id=row.provider_request_id,
        error_kind=ProviderErrorKind(row.error_kind) if row.error_kind else None,
        failure_class=FailureClass(row.failure_class) if row.failure_class else None,
        finish_reason=FinishReason(row.finish_reason) if row.finish_reason else None,
        usage=ModelUsage(
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cache_read_input_tokens=row.cache_read_input_tokens,
            cache_write_input_tokens=row.cache_write_input_tokens,
        ),
        cost_usd=row.cost_usd,
        cost_basis=CostBasis(row.cost_basis),
        ceiling_usd=row.ceiling_usd,
        schema_fingerprint=row.schema_fingerprint,
        substituted_from=row.substituted_from,
        fallback_from=row.fallback_from,
        fallback_authorised_by=row.fallback_authorised_by,
        occurred_at=occurred,
        latency_ms=row.latency_ms,
        supersedes_event_id=row.supersedes_event_id,
        note=row.note,
    )


class AIUsageRepository:
    """The ledger within one authorised study scope.

    Like the other repositories, it flushes and never commits: the caller owns
    the transaction. The one place that must commit promptly -- the dispatch
    record -- is the journal's responsibility, not this repository's.
    """

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError(
                "AIUsageRepository requires a StudyContext issued by the authorization layer"
            )
        self._session = session
        self._scope = scope

    @property
    def scope(self) -> StudyContext:
        """The authorised scope this repository operates in."""
        return self._scope

    # --------------------------------------------------------------- writes --

    def append(self, event: AIUsageEvent) -> None:
        """Append one entry, or raise.

        Refused: an entry attributed to another scope, a second entry of the same
        outcome for a call, a terminal entry for a call that was never
        dispatched, and a resolution of a call that is not uncertain.
        """
        scope = self._scope
        if (event.organization_id, event.client_id, event.study_id) != (
            scope.organization_id,
            scope.client_id,
            scope.study_id,
        ):
            raise ScopeDenied(
                "usage entry is attributed to a different scope", reason="cross_scope_ledger_write"
            )

        existing = {e.outcome: e for e in self._events(call_id=event.call_id)}
        if event.outcome in existing:
            raise LedgerConflict(f"call {event.call_id} already has a {event.outcome.value} entry")
        if event.outcome is not UsageOutcome.DISPATCHED and UsageOutcome.DISPATCHED not in existing:
            raise LedgerConflict(f"call {event.call_id} was never dispatched")
        if event.outcome.is_resolution:
            if any(o.is_resolution for o in existing):
                raise LedgerConflict(f"call {event.call_id} is already resolved")
            closed = [o for o in existing if o.is_terminal and not o.is_resolution]
            if closed and closed != [UsageOutcome.UNCERTAIN]:
                raise LedgerConflict(f"call {event.call_id} is not uncertain")
        elif event.outcome.is_terminal and any(
            o.is_terminal and not o.is_resolution for o in existing
        ):
            raise LedgerConflict(f"call {event.call_id} already has a terminal entry")

        self._session.add(_row(event))
        self._session.flush()

    def resolve_uncertain(
        self,
        call_id: str,
        *,
        billed: bool,
        actual_cost_usd: float,
        provider_request_id: str | None = None,
        note: str = "",
        at: datetime | None = None,
    ) -> AIUsageEvent:
        """Close an uncertain call with a compensating entry.

        The compensation is ``actual - recorded exposure``: an uncertain call
        carried at its ceiling and found to have cost less is reduced to the
        truth; one that died in flight (no exposure recorded) and was billed is
        raised to it. Either way the per-call sum becomes the actual cost.

        Deciding what a provider actually charged is a budget act, so it needs
        ``MANAGE_STUDY_BUDGET``, and the resolver is recorded as the actor.
        """
        self._scope.require(Permission.MANAGE_STUDY_BUDGET)
        actual = float(actual_cost_usd)
        if actual < 0 or (not billed and actual != 0):
            raise ValueError("an unbilled call costs nothing; a billed one cannot cost less")

        pending = {c.call_id: c for c in self.uncertain_calls()}
        call = pending.get(call_id)
        if call is None:
            raise LedgerConflict(f"call {call_id} is not an open uncertain call")

        base = call.terminal or call.dispatched
        resolution = AIUsageEvent(
            **{
                **{f: getattr(base, f) for f in AIUsageEvent.__dataclass_fields__},
                "event_id": new_usage_event_id(),
                "outcome": (
                    UsageOutcome.RESOLVED_BILLED if billed else UsageOutcome.RESOLVED_NOT_BILLED
                ),
                "actor_id": self._scope.actor_id,
                "provider_request_id": provider_request_id or call.provider_request_id,
                "cost_usd": actual - call.recorded_exposure_usd,
                "cost_basis": CostBasis.COMPENSATION,
                "occurred_at": at or utcnow(),
                "latency_ms": None,
                "supersedes_event_id": base.event_id,
                "note": note,
            }
        )
        self.append(resolution)
        return resolution

    # ---------------------------------------------------------------- reads --

    def _scoped(self) -> tuple[ColumnElement[bool], ...]:
        return (
            AIUsageEventRow.organization_id == self._scope.organization_id,
            AIUsageEventRow.client_id == self._scope.client_id,
            AIUsageEventRow.study_id == self._scope.study_id,
        )

    def events(
        self,
        *,
        call_id: str | None = None,
        run_id: str | None = None,
        attempt_id: str | None = None,
    ) -> list[AIUsageEvent]:
        """Ledger entries in this study, oldest first. Requires ``VIEW_COSTS``."""
        self._scope.require(Permission.VIEW_COSTS)
        return self._events(call_id=call_id, run_id=run_id, attempt_id=attempt_id)

    def _events(
        self,
        *,
        call_id: str | None = None,
        run_id: str | None = None,
        attempt_id: str | None = None,
    ) -> list[AIUsageEvent]:
        # Unchecked: used by the write path, which records on behalf of whoever is
        # running the work and must not depend on that person seeing costs.
        query = select(AIUsageEventRow).where(*self._scoped())
        if call_id is not None:
            query = query.where(AIUsageEventRow.call_id == call_id)
        if run_id is not None:
            query = query.where(AIUsageEventRow.run_id == run_id)
        if attempt_id is not None:
            query = query.where(AIUsageEventRow.attempt_id == attempt_id)
        query = query.order_by(AIUsageEventRow.occurred_at, AIUsageEventRow.recorded_at)
        return [_event(r) for r in self._session.scalars(query)]

    def uncertain_calls(self) -> list[UncertainCall]:
        """Calls dispatched with no known outcome and no resolution yet.

        Unchecked by permission for the same reason as the write path: the
        recovery flow must be able to find these whoever is running it.
        """
        by_call: dict[str, dict[UsageOutcome, AIUsageEvent]] = {}
        for event in self._events():
            by_call.setdefault(event.call_id, {})[event.outcome] = event

        open_calls: list[UncertainCall] = []
        for call_id, entries in by_call.items():
            dispatched = entries.get(UsageOutcome.DISPATCHED)
            if dispatched is None or any(o.is_resolution for o in entries):
                continue
            terminal = [o for o in entries if o.is_terminal]
            if not terminal or terminal == [UsageOutcome.UNCERTAIN]:
                open_calls.append(
                    UncertainCall(
                        call_id=call_id,
                        dispatched=dispatched,
                        terminal=entries.get(UsageOutcome.UNCERTAIN),
                    )
                )
        return open_calls

    def attempt_spend_usd(self, attempt_id: str) -> float:
        """What this attempt's terminal entries carry, uncertain ones at ceiling.

        Unchecked by permission: it is the journal's starting balance, read on
        behalf of whoever runs the work.
        """
        return sum(e.cost_usd for e in self._events(attempt_id=attempt_id) if e.outcome.is_terminal)

    def total_cost_usd(self, *, run_id: str | None = None) -> float:
        """Net AI spend recorded in this study (or run), compensations included."""
        self._scope.require(Permission.VIEW_COSTS)
        query = select(func.coalesce(func.sum(AIUsageEventRow.cost_usd), 0.0)).where(
            *self._scoped()
        )
        if run_id is not None:
            query = query.where(AIUsageEventRow.run_id == run_id)
        # SUM over no rows is genuinely zero spend, not an unknown (OI-4).
        return float(self._session.scalar(query) or 0.0)
