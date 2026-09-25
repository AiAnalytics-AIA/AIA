"""The usage ledger and the durable journal, against a real workflow attempt.

The case that matters most here is the one no unit test of the gateway can
show: a worker that dies *after* a paid call left and *before* it could record
anything else. The dispatch record must already be committed by then, so that
the reconciler parks the step as RECOVERY_REQUIRED instead of retrying it -- and
the ledger must already hold the call, so someone can find and reconcile it.

One test runs the same crash with a journal that only flushes, to show what the
commit is buying: the dispatch mark rolls back and the step is retried.
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    AgentDefinition,
    AIUsageEvent,
    CallPurpose,
    CostBasis,
    Delivery,
    FinishReason,
    Message,
    ModelCallFailed,
    ModelRequest,
    ModelUsage,
    ProviderError,
    ProviderErrorKind,
    UsageOutcome,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView, recovery_inputs
from aia_core.domain.ai_models import ModelCapability, ModelRegistry
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workflow import (
    RecoveryAction,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
)
from aia_core.infrastructure.ai_call_journal import WorkflowCallJournal
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository, LedgerConflict
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import AIUsageEventRow, BudgetReservationRow, StepAttemptRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

WORKER = "worker-1"

LICENCE = recorded_policy()


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str


class WorkerKilled(BaseException):
    """The process died. Not an Exception: nothing in the gateway may catch it."""


class Adapter:
    def __init__(self, script: Sequence[AdapterResponse | BaseException]) -> None:
        self._script = list(script)
        self.requests: list[AdapterRequest] = []

    @property
    def provider(self) -> Provider:
        return Provider.OPENAI

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        self.requests.append(request)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


OK = AdapterResponse(
    text='{"verdict": "fine"}',
    finish_reason=FinishReason.COMPLETED,
    usage=ModelUsage(input_tokens=1000, output_tokens=200),
    provider_request_id="req_ledger",
)
EGRESS = EgressPolicy(
    routes=(
        ProviderRoute(
            route_id="openai-direct",
            provider="openai",
            zone=ResidencyZone.NON_EU,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
    )
)
REQUEST = ModelRequest(
    agent=AgentDefinition(
        agent_id="ledger-agent",
        version="1",
        capability=ModelCapability.FAST_EXTRACTION,
        prompt_id="p",
        prompt_version="1",
        output_contract=Answer,
        max_output_tokens=500,
    ),
    policy_version="policy-test-v1",
    data_classification=DataClass.CLASS_C_INTERNAL,
    data_lineage=DataLineage.none(),
    system="s",
    messages=(Message(role="user", content="u"),),
)


@dataclasses.dataclass
class Attempt:
    """One claimed, budgeted attempt, and everything needed to call a model in it."""

    session: Session
    scope: Any
    workflow: WorkflowRepository
    usage: AIUsageRepository
    run_id: str
    step_id: str
    attempt_id: str
    reservation_id: str
    commits: list[int]

    def journal(self, *, durable: bool = True) -> WorkflowCallJournal:
        def commit() -> None:
            self.commits.append(1)
            if durable:
                self.session.commit()

        return WorkflowCallJournal(
            workflow=self.workflow,
            usage=self.usage,
            attempt_id=self.attempt_id,
            worker_id=WORKER,
            commit=commit,
        )

    def context(self, journal: WorkflowCallJournal) -> ExecutionContext:
        return ExecutionContext(
            scope=self.scope,
            runtime_version="rv",
            journal=journal,
            run_id=self.run_id,
            step_id=self.step_id,
            attempt_id=self.attempt_id,
            reservation=ReservationView(reservation_id=self.reservation_id, amount_usd=1.0),
        )

    def invoke(self, adapter: Adapter, registry: ModelRegistry, *, durable: bool = True) -> Any:
        gateway = GovernedModelGateway(
            registry=registry, egress=EGRESS, licence=LICENCE, adapters={"openai-direct": adapter}
        )
        return asyncio.run(gateway.invoke(REQUEST, self.context(self.journal(durable=durable))))

    def attempt_row(self) -> StepAttemptRow:
        self.session.expire_all()
        row = self.session.get(StepAttemptRow, self.attempt_id)
        assert row is not None
        return row

    def reservation_row(self) -> BudgetReservationRow:
        self.session.expire_all()
        row = self.session.get(BudgetReservationRow, self.reservation_id)
        assert row is not None
        return row


@pytest.fixture
def attempt(session: Session, scoped: Any) -> Attempt:
    scope = scoped.scope(user="lead", study="primary")
    project, _ = ProjectRepository(session, scope).create(title="Ledger host", content={})
    workflow = WorkflowRepository(session, scope)
    run_id = workflow.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="ai_runtime_ledger_test",
        steps=[StepDefinition(node_key="analyse", kind="analysis")],
        idempotency_key=f"{project.project_id}:ledger",
    )
    claimed = workflow.claim_next(worker_id=WORKER)
    assert claimed is not None
    reservation_id = workflow.reserve_budget(
        attempt_id=claimed.attempt_id, worker_id=WORKER, amount_usd=1.0, provider=Provider.OPENAI
    )
    assert reservation_id is not None
    session.commit()
    return Attempt(
        session=session,
        scope=scope,
        workflow=workflow,
        usage=AIUsageRepository(session, scope),
        run_id=run_id,
        step_id=claimed.step_id,
        attempt_id=claimed.attempt_id,
        reservation_id=reservation_id,
        commits=[],
    )


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)


# --------------------------------------------------------------------------- #
# The durable journal
# --------------------------------------------------------------------------- #


def test_successful_call_is_ledgered_and_closes_the_billing_question(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    result = attempt.invoke(Adapter([OK]), model_registry)

    entries = attempt.usage.events(attempt_id=attempt.attempt_id)
    assert [e.outcome for e in entries] == [UsageOutcome.DISPATCHED, UsageOutcome.SUCCEEDED]
    assert entries[1].provider_request_id == "req_ledger"
    assert entries[1].cost_usd == pytest.approx(result.actual_cost_usd)
    # Round-trips every field it wrote.
    assert entries == list(result.usage_events)
    assert entries[0].input_fingerprint is not None
    assert entries[0].input_fingerprint == entries[1].input_fingerprint

    row = attempt.attempt_row()
    assert row.paid_call_dispatched is True
    assert row.paid_call_outcome_known is True
    assert row.provider_request_id == "req_ledger"
    assert row.actual_cost_usd == pytest.approx(result.actual_cost_usd)
    # Dispatch (fence + ledger row), then the outcome's ledger row, then the
    # fenced attempt write: the ledger commit never waits on the lease.
    assert len(attempt.commits) == 3

    attempt.workflow.complete_attempt(
        attempt.attempt_id,
        worker_id=WORKER,
        output={"verdict": "fine"},
        actual_cost_usd=result.total_cost_usd,
        reservation_id=attempt.reservation_id,
    )
    assert attempt.reservation_row().status == ReservationStatus.SETTLED.value
    assert attempt.usage.total_cost_usd() == pytest.approx(
        attempt.workflow.budget_position()["spent_usd"]
    )


def test_worker_killed_mid_call_parks_for_a_person_and_the_ledger_can_find_it(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """The case the contract exists for."""
    with pytest.raises(WorkerKilled):
        attempt.invoke(Adapter([WorkerKilled()]), model_registry)
    # Everything the dying process had not committed is gone.
    attempt.session.rollback()

    decisions = attempt.workflow.recover_expired_attempts(now=_future())
    assert [d.action for d in decisions] == [RecoveryAction.RECOVERY_REQUIRED]
    assert decisions[0].settle_reservation_as_uncertain is True
    assert attempt.reservation_row().status == ReservationStatus.SETTLED_UNCERTAIN.value

    [orphan] = attempt.usage.uncertain_calls()
    assert orphan.terminal is None
    assert orphan.dispatched.attempt_id == attempt.attempt_id
    assert orphan.dispatched.ceiling_usd > 0

    # Later, a person checks the provider's usage console and records the fact.
    resolution = attempt.usage.resolve_uncertain(
        orphan.call_id, billed=True, actual_cost_usd=0.00027, provider_request_id="req_found"
    )
    assert resolution.outcome is UsageOutcome.RESOLVED_BILLED
    assert resolution.cost_basis is CostBasis.COMPENSATION
    assert resolution.supersedes_event_id == orphan.dispatched.event_id
    assert resolution.actor_id == attempt.scope.actor_id
    assert attempt.usage.uncertain_calls() == []
    assert attempt.usage.total_cost_usd() == pytest.approx(0.00027)


def test_without_a_committed_dispatch_the_same_crash_is_retried(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """Characterises the defect a flush-only journal would ship: the dispatch
    mark rolls back, the lapsed lease looks safe, and the step is retried -- a
    second paid call for work that may already have been billed."""
    with pytest.raises(WorkerKilled):
        attempt.invoke(Adapter([WorkerKilled()]), model_registry, durable=False)
    attempt.session.rollback()

    decisions = attempt.workflow.recover_expired_attempts(now=_future())
    assert [d.action for d in decisions] == [RecoveryAction.RETRY]
    assert attempt.usage.uncertain_calls() == []


def test_uncertain_outcome_leaves_the_attempt_unknown_and_resolves_to_zero(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    timeout = ProviderError(
        "read timed out", kind=ProviderErrorKind.TRANSPORT, delivery=Delivery.UNKNOWN
    )
    with pytest.raises(ModelCallFailed) as exc:
        attempt.invoke(Adapter([timeout]), model_registry)

    row = attempt.attempt_row()
    assert row.paid_call_dispatched is True
    assert row.paid_call_outcome_known is False

    inputs = recovery_inputs(exc.value)
    decision = attempt.workflow.fail_attempt(
        attempt.attempt_id,
        worker_id=WORKER,
        failure=inputs.failure,
        error=dict(inputs.error),
        reservation_id=attempt.reservation_id,
    )
    assert decision.step_status is StepRunStatus.RECOVERY_REQUIRED
    assert attempt.reservation_row().status == ReservationStatus.SETTLED_UNCERTAIN.value

    [call] = attempt.usage.uncertain_calls()
    assert call.terminal is not None
    assert call.terminal.outcome is UsageOutcome.UNCERTAIN
    assert call.recorded_exposure_usd == pytest.approx(call.dispatched.ceiling_usd)

    attempt.usage.resolve_uncertain(call.call_id, billed=False, actual_cost_usd=0.0)
    assert attempt.usage.total_cost_usd() == pytest.approx(0.0)


def test_rebuilt_journal_remembers_what_the_attempt_already_spent(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    result = attempt.invoke(Adapter([OK]), model_registry)
    assert attempt.journal().committed_usd() == pytest.approx(result.actual_cost_usd)


def test_journal_refuses_another_attempts_entries(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    result = attempt.invoke(Adapter([OK]), model_registry)
    foreign = dataclasses.replace(result.usage_events[0], attempt_id="ATT-other")
    journal = attempt.journal()
    with pytest.raises(ValueError, match="different attempt"):
        journal.record_dispatch(foreign)
    with pytest.raises(ValueError, match="different attempt"):
        journal.record_outcome(foreign)


def test_journal_requires_one_scope(attempt: Attempt, scoped: Any) -> None:
    other = AIUsageRepository(attempt.session, scoped.scope(user="lead", study="primary"))
    with pytest.raises(ValueError, match="share one scope"):
        WorkflowCallJournal(
            workflow=attempt.workflow,
            usage=other,
            attempt_id=attempt.attempt_id,
            worker_id=WORKER,
            commit=lambda: None,
        )


# --------------------------------------------------------------------------- #
# Integration with the lease-fenced workflow engine (merge of main into #28)
# --------------------------------------------------------------------------- #


def test_a_worker_that_lost_the_lease_never_sends_and_ledgers_nothing(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """The dispatch mark is the lease fence. A worker whose attempt was recovered
    learns it there -- before the adapter is reached and before a ledger row
    claims a call that never happened."""
    from aia_core.infrastructure.workflow_repository import LeaseLost

    attempt.workflow.recover_expired_attempts(now=_future())
    attempt.session.commit()
    adapter = Adapter([OK])
    with pytest.raises(LeaseLost):
        attempt.invoke(adapter, model_registry)
    attempt.session.rollback()
    assert adapter.requests == []
    assert attempt.usage.events(attempt_id=attempt.attempt_id) == []


def test_several_calls_in_one_attempt_are_charged_once_each(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """The repository *adds* each outcome's cost to the attempt. A journal that
    reported the running total instead would charge a primary-plus-repair
    attempt three calls' worth for two."""
    bad = dataclasses.replace(OK, text='{"verdict": 1}')
    result = attempt.invoke(Adapter([bad, OK]), model_registry)
    two_calls = result.total_cost_usd
    assert two_calls == pytest.approx(2 * result.actual_cost_usd)
    assert attempt.attempt_row().actual_cost_usd == pytest.approx(two_calls)

    attempt.workflow.complete_attempt(
        attempt.attempt_id,
        worker_id=WORKER,
        output={"verdict": "fine"},
        actual_cost_usd=two_calls,
        reservation_id=attempt.reservation_id,
    )
    attempt.session.commit()
    assert attempt.workflow.budget_position()["spent_usd"] == pytest.approx(two_calls)
    assert attempt.usage.total_cost_usd() == pytest.approx(two_calls)


def test_a_failed_attempt_is_charged_for_every_billed_call(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """Both answers were billed and both failed validation. The attempt fails,
    and the study is charged for the two calls -- not zero, not the reservation."""
    bad = dataclasses.replace(OK, text='{"verdict": 1}')
    with pytest.raises(ModelCallFailed) as exc:
        attempt.invoke(Adapter([bad, bad]), model_registry)
    billed = sum(e.cost_usd for e in exc.value.usage_events if e.outcome.is_terminal)
    assert billed > 0

    inputs = recovery_inputs(exc.value)
    attempt.workflow.fail_attempt(
        attempt.attempt_id,
        worker_id=WORKER,
        failure=inputs.failure,
        error=dict(inputs.error),
        reservation_id=attempt.reservation_id,
    )
    attempt.session.commit()
    assert attempt.workflow.budget_position()["spent_usd"] == pytest.approx(billed)
    assert attempt.usage.total_cost_usd() == pytest.approx(billed)


def test_outcome_is_ledgered_even_when_the_lease_is_lost_mid_call(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    """The call happened whatever the lease says. The terminal entry is committed
    before the fenced attempt write, so the reconciler's uncertain settlement has
    the provider's real answer beside it."""
    from aia_core.infrastructure.workflow_repository import LeaseLost

    class LosesLeaseMidCall(Adapter):
        async def send(self, request: AdapterRequest) -> AdapterResponse:
            attempt.workflow.recover_expired_attempts(now=_future())
            attempt.session.commit()
            return await super().send(request)

    with pytest.raises(LeaseLost):
        attempt.invoke(LosesLeaseMidCall([OK]), model_registry)
    attempt.session.rollback()
    outcomes = [e.outcome for e in attempt.usage.events(attempt_id=attempt.attempt_id)]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.SUCCEEDED]
    assert attempt.reservation_row().status == ReservationStatus.SETTLED_UNCERTAIN.value


# --------------------------------------------------------------------------- #
# Ledger guards
# --------------------------------------------------------------------------- #


@pytest.fixture
def ledgered(attempt: Attempt, model_registry: ModelRegistry) -> list[AIUsageEvent]:
    return list(attempt.invoke(Adapter([OK]), model_registry).usage_events)


def test_entry_for_another_study_is_refused(
    attempt: Attempt, scoped: Any, ledgered: list[AIUsageEvent]
) -> None:
    sibling = AIUsageRepository(attempt.session, scoped.scope(user="lead", study="sibling"))
    with pytest.raises(ScopeDenied) as exc:
        sibling.append(dataclasses.replace(ledgered[0], call_id="CALL-x", event_id="AUE-x"))
    assert exc.value.reason == "cross_scope_ledger_write"


def test_reads_are_confined_to_the_scope(
    attempt: Attempt, scoped: Any, ledgered: list[AIUsageEvent]
) -> None:
    for study in ("sibling", "other_client"):
        user = "other_lead" if study == "other_client" else "lead"
        repo = AIUsageRepository(attempt.session, scoped.scope(user=user, study=study))
        assert repo.events() == []
        assert repo.total_cost_usd() == 0.0
        assert repo.uncertain_calls() == []


def test_reading_costs_requires_view_costs(attempt: Attempt, scoped: Any) -> None:
    viewer = AIUsageRepository(attempt.session, scoped.scope(user="viewer", study="primary"))
    with pytest.raises(ScopeDenied):
        viewer.events()
    with pytest.raises(ScopeDenied):
        viewer.total_cost_usd()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda e: dataclasses.replace(e, event_id="AUE-dup"), "already has a DISPATCHED"),
        (
            lambda e: dataclasses.replace(
                e, event_id="AUE-orphan", call_id="CALL-never", outcome=UsageOutcome.SUCCEEDED
            ),
            "never dispatched",
        ),
        (
            lambda e: dataclasses.replace(e, event_id="AUE-second", outcome=UsageOutcome.FAILED),
            "already has a terminal",
        ),
    ],
)
def test_ledger_refuses_contradictions(
    attempt: Attempt, ledgered: list[AIUsageEvent], mutate: Any, message: str
) -> None:
    with pytest.raises(LedgerConflict, match=message):
        attempt.usage.append(mutate(ledgered[0]))


def test_a_known_call_cannot_be_resolved(attempt: Attempt, ledgered: list[AIUsageEvent]) -> None:
    with pytest.raises(LedgerConflict, match="not an open uncertain call"):
        attempt.usage.resolve_uncertain(ledgered[0].call_id, billed=True, actual_cost_usd=1.0)


def test_resolution_is_a_budget_act(
    attempt: Attempt, scoped: Any, model_registry: ModelRegistry
) -> None:
    with pytest.raises(WorkerKilled):
        attempt.invoke(Adapter([WorkerKilled()]), model_registry)
    [call] = attempt.usage.uncertain_calls()

    researcher = AIUsageRepository(
        attempt.session, scoped.scope(user="researcher", study="primary")
    )
    with pytest.raises(ScopeDenied):
        researcher.resolve_uncertain(call.call_id, billed=False, actual_cost_usd=0.0)

    with pytest.raises(ValueError, match="unbilled call costs nothing"):
        attempt.usage.resolve_uncertain(call.call_id, billed=False, actual_cost_usd=0.5)
    with pytest.raises(ValueError):
        attempt.usage.resolve_uncertain(call.call_id, billed=True, actual_cost_usd=-1.0)
    # Codex P2 on #28: NaN passes every comparison; inf is not a cost.
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            attempt.usage.resolve_uncertain(call.call_id, billed=True, actual_cost_usd=bad)

    attempt.usage.resolve_uncertain(call.call_id, billed=False, actual_cost_usd=0.0)
    with pytest.raises(LedgerConflict):
        attempt.usage.resolve_uncertain(call.call_id, billed=True, actual_cost_usd=0.1)


def test_database_refuses_a_negative_cost_that_is_not_a_compensation(
    attempt: Attempt, ledgered: list[AIUsageEvent]
) -> None:
    """Defence in depth under the domain check, for anything that bypasses it."""
    source = attempt.session.get(AIUsageEventRow, ledgered[1].event_id)
    assert source is not None
    columns = {c.name: getattr(source, c.name) for c in AIUsageEventRow.__table__.columns}
    columns.update(event_id="AUE-raw", call_id="CALL-raw", cost_usd=-5.0, cost_basis="METERED")
    attempt.session.add(AIUsageEventRow(**columns))
    with pytest.raises(IntegrityError):
        attempt.session.flush()
    attempt.session.rollback()


def test_entries_keep_their_purpose_and_null_usage(
    attempt: Attempt, model_registry: ModelRegistry
) -> None:
    unreported = dataclasses.replace(OK, usage=ModelUsage())
    result = attempt.invoke(Adapter([unreported]), model_registry)
    [dispatched, terminal] = attempt.usage.events(call_id=result.call_id)
    assert dispatched.purpose is CallPurpose.PRIMARY
    assert terminal.usage.input_tokens is None  # not reported is not zero
    assert terminal.cost_basis is CostBasis.CEILING
