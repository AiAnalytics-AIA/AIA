"""Tests for the durable workflow engine.

These are the four categories Phase 3 must prove, plus the state machine itself:

1. **Lease and concurrency correctness** -- see ``test_workflow_concurrency.py``,
   which uses genuinely concurrent PostgreSQL transactions.
2. **Idempotency** -- a duplicate wake-up produces one execution, not two.
3. **Recovery semantics** -- every row of the recovery table.
4. **Accounting transactionality** -- impossible states are unrepresentable.

The behavioural contract they implement is
``test_legacy_job_store_characterization.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.scope import ScopeDenied, SeparationOfDutiesViolation
from aia_core.domain.workflow import (
    AttemptStatus,
    FailureClass,
    RecoveryAction,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
    classify_failure,
    decide_recovery,
    derive_run_status,
    is_lease_expired,
    validate_dag,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import BudgetReservationRow, StudyRow
from aia_core.infrastructure.workflow_repository import (
    BudgetExceeded,
    WorkflowNotFound,
    WorkflowRepository,
)

# A small three-node pipeline: compile -> research -> report.
PIPELINE = [
    StepDefinition(node_key="compile", kind="project_compile", stage_type="BRIEF"),
    StepDefinition(
        node_key="research",
        kind="background_research",
        depends_on=("compile",),
        stage_type="DEEP_RESEARCH",
    ),
    StepDefinition(
        node_key="report",
        kind="final_report",
        depends_on=("research",),
        stage_type="REPORT",
    ),
]


@pytest.fixture
def project(session: Session, scoped: Any) -> Any:
    """A project to hang runs off."""
    repo = ProjectRepository(session, scoped.scope(user="lead", study="primary"))
    created, _ = repo.create(title="Workflow host", content={"goal": "g"})
    return created


@pytest.fixture
def engine_repo(session: Session, scoped: Any) -> WorkflowRepository:
    """Workflow repository as a LEAD on the primary study."""
    return WorkflowRepository(session, scoped.scope(user="lead", study="primary"))


@pytest.fixture
def run(engine_repo: WorkflowRepository, project: Any) -> str:
    """A created run over PIPELINE."""
    return engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=PIPELINE,
        idempotency_key=f"{project.project_id}:rev1:research",
    )


def _step_id(repo: WorkflowRepository, run_id: str, node_key: str) -> str:
    """Return a step id by node key."""
    return next(s["step_id"] for s in repo.get_run(run_id)["steps"] if s["node_key"] == node_key)


def _status(repo: WorkflowRepository, run_id: str, node_key: str) -> StepRunStatus:
    """Return a step's status by node key."""
    return next(s["status"] for s in repo.get_run(run_id)["steps"] if s["node_key"] == node_key)


# --------------------------------------------------------------------------- #
# DAG validation
# --------------------------------------------------------------------------- #


def test_dag_validation_accepts_a_valid_pipeline() -> None:
    """The happy path, including a diamond."""
    validate_dag(
        [
            StepDefinition(node_key="a", kind="k"),
            StepDefinition(node_key="b", kind="k", depends_on=("a",)),
            StepDefinition(node_key="c", kind="k", depends_on=("a",)),
            StepDefinition(node_key="d", kind="k", depends_on=("b", "c")),
        ]
    )


def test_dag_validation_rejects_a_cycle() -> None:
    """Checked at definition time, not execution time.

    A cycle discovered mid-run would strand a study with some steps already paid
    for.
    """
    with pytest.raises(ValueError, match="cycle"):
        validate_dag(
            [
                StepDefinition(node_key="a", kind="k", depends_on=("b",)),
                StepDefinition(node_key="b", kind="k", depends_on=("a",)),
            ]
        )


def test_dag_validation_rejects_self_dependency_and_unknown_nodes() -> None:
    """A typo in a dependency is a definition error, not a runtime surprise."""
    with pytest.raises(ValueError, match="itself"):
        validate_dag([StepDefinition(node_key="a", kind="k", depends_on=("a",))])
    with pytest.raises(ValueError, match="unknown"):
        validate_dag([StepDefinition(node_key="a", kind="k", depends_on=("ghost",))])
    with pytest.raises(ValueError, match="duplicate"):
        validate_dag(
            [StepDefinition(node_key="a", kind="k"), StepDefinition(node_key="a", kind="k")]
        )


def test_create_run_rejects_an_invalid_dag(engine_repo: WorkflowRepository, project: Any) -> None:
    """Validation happens before anything is persisted."""
    with pytest.raises(ValueError, match="cycle"):
        engine_repo.create_run(
            project_id=project.project_id,
            project_revision=1,
            workflow_type="broken",
            steps=[
                StepDefinition(node_key="a", kind="k", depends_on=("b",)),
                StepDefinition(node_key="b", kind="k", depends_on=("a",)),
            ],
            idempotency_key="broken",
        )


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #


def test_duplicate_run_creation_returns_the_existing_run(
    engine_repo: WorkflowRepository, project: Any
) -> None:
    """The guarantee that makes an at-least-once trigger safe.

    Re-submitting the same logical run must not start a second, duplicate
    pipeline -- which would double every AI call in it.
    """
    key = f"{project.project_id}:rev1:research"
    first = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=PIPELINE,
        idempotency_key=key,
    )
    second = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=PIPELINE,
        idempotency_key=key,
    )

    assert second == first
    assert len(engine_repo.get_run(first)["steps"]) == 3


def test_duplicate_wake_up_produces_one_execution_not_two(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """**SQS delivers at least once. This is the guard.**

    Two workers both woken for the same run must not both execute the same step.
    Ownership lives in PostgreSQL, not in the queue, so the second claimer gets
    the *next* step or nothing -- never a second attempt at the same one.
    """
    first = engine_repo.claim_next(worker_id="worker-1")
    second = engine_repo.claim_next(worker_id="worker-2")

    assert first is not None
    assert first.node_key == "compile"
    assert second is None, "no other step is runnable, and compile is taken"

    history = engine_repo.attempt_history(first.step_id)
    assert len(history) == 1, "exactly one attempt exists"
    assert history[0]["worker_id"] == "worker-1"


def test_a_claimed_step_is_not_reclaimable(engine_repo: WorkflowRepository, run: str) -> None:
    """Repeated claim attempts by the same worker do not stack attempts."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    for _ in range(3):
        assert engine_repo.claim_next(worker_id="worker-1") is None

    assert len(engine_repo.attempt_history(claimed.step_id)) == 1


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #


def test_only_dependency_free_steps_start_runnable(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """The DAG is sequential from creation, not from a scheduler tick."""
    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNABLE
    assert _status(engine_repo, run, "research") is StepRunStatus.BLOCKED
    assert _status(engine_repo, run, "report") is StepRunStatus.BLOCKED


def test_success_releases_the_next_step(engine_repo: WorkflowRepository, run: str) -> None:
    """Completion advances the DAG one level, not all of it."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id, output={"ok": True})

    assert _status(engine_repo, run, "compile") is StepRunStatus.SUCCEEDED
    assert _status(engine_repo, run, "research") is StepRunStatus.RUNNABLE
    assert _status(engine_repo, run, "report") is StepRunStatus.BLOCKED


def test_a_failed_dependency_stalls_the_pipeline(engine_repo: WorkflowRepository, run: str) -> None:
    """A dependant waits for SUCCEEDED specifically, not merely a terminal state.

    Otherwise an analysis would run on a missing evidence pack -- worse than no
    analysis, because it looks like a result.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.fail_attempt(
        claimed.attempt_id,
        failure=FailureClass.AUTHENTICATION,
        error={"message": "bad key"},
    )

    assert _status(engine_repo, run, "compile") is StepRunStatus.FAILED
    assert _status(engine_repo, run, "research") is StepRunStatus.BLOCKED
    assert engine_repo.claim_next(worker_id="worker-2") is None
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.FAILED


def test_claim_honours_priority_then_creation_order(
    engine_repo: WorkflowRepository, project: Any
) -> None:
    """Higher priority first, ties by creation order, so nothing starves."""
    run_id = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="parallel",
        steps=[
            StepDefinition(node_key="low", kind="k", priority=10),
            StepDefinition(node_key="high", kind="k", priority=90),
            StepDefinition(node_key="mid", kind="k", priority=50),
        ],
        idempotency_key="parallel-1",
    )

    order = []
    for worker in ("w1", "w2", "w3"):
        claimed = engine_repo.claim_next(worker_id=worker)
        assert claimed is not None
        order.append(claimed.node_key)

    assert order == ["high", "mid", "low"]
    assert engine_repo.get_run(run_id)["status"] is WorkflowRunStatus.RUNNING


# --------------------------------------------------------------------------- #
# Leases and heartbeats
# --------------------------------------------------------------------------- #


def test_claim_sets_a_lease_and_running_state(engine_repo: WorkflowRepository, run: str) -> None:
    """A claimed step is RUNNING, its attempt is CLAIMED, and it has a deadline."""
    claimed = engine_repo.claim_next(worker_id="worker-1", lease_seconds=60)
    assert claimed is not None

    assert claimed.lease_until > datetime.now(UTC)
    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNING
    assert engine_repo.attempt_history(claimed.step_id)[0]["status"] is (AttemptStatus.CLAIMED)


def test_heartbeat_extends_the_lease_for_the_owner_only(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """Only the lease owner may extend.

    Otherwise a worker that already lost its lease could keep a step alive and
    two workers would run it.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    assert engine_repo.heartbeat(claimed.attempt_id, worker_id="worker-1") is True
    assert engine_repo.heartbeat(claimed.attempt_id, worker_id="worker-2") is False

    assert engine_repo.attempt_history(claimed.step_id)[0]["status"] is (AttemptStatus.EXECUTING)


def test_heartbeat_on_a_finished_attempt_is_refused(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """A completed attempt cannot be resurrected by a late heartbeat."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id)

    assert engine_repo.heartbeat(claimed.attempt_id, worker_id="worker-1") is False


def test_a_missing_lease_deadline_counts_as_expired() -> None:
    """An attempt holding a lease with no deadline is a bug.

    Treating it as live would strand the step forever, so it is treated as
    expired and recovered.
    """
    assert is_lease_expired(None) is True
    assert is_lease_expired(datetime.now(UTC) - timedelta(seconds=1)) is True
    assert is_lease_expired(datetime.now(UTC) + timedelta(hours=1)) is False


# --------------------------------------------------------------------------- #
# Recovery semantics -- every row of the table
# --------------------------------------------------------------------------- #


def test_recovery_retries_a_free_deterministic_step(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A crashed worker on safe-to-repeat work returns the step to RUNNABLE."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    _expire(session, claimed.attempt_id)

    decisions = engine_repo.recover_expired_attempts()
    assert [d.action for d in decisions] == [RecoveryAction.RETRY]
    assert decisions[0].reason == "expired_lease_idempotent_or_subscription"
    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNABLE

    again = engine_repo.claim_next(worker_id="worker-2")
    assert again is not None
    assert again.attempt_number == 2, "a retry is attempt 2, not a reused attempt 1"


def test_recovery_does_not_retry_a_possibly_billed_paid_call(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """**The double-billing guard. The most important test in this file.**

    A worker dies after dispatching a metered provider call. The system cannot
    know whether the provider never received it, processed it and lost the
    response, or processed it and billed. So:

        automatic retry  = possible double billing
        assume success   = possible missing output
        assume failure   = an accounting lie

    RECOVERY_REQUIRED plus SETTLED_UNCERTAIN is the only responsible answer.
    """
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    reservation_id = engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=2.00, provider=Provider.ANTHROPIC
    )
    assert reservation_id is not None
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, provider_request_id="req_abc123")
    _expire(session, claimed.attempt_id)

    decisions = engine_repo.recover_expired_attempts()

    assert [d.action for d in decisions] == [RecoveryAction.RECOVERY_REQUIRED]
    assert decisions[0].reason == "paid_external_call_side_effect_uncertain"
    assert decisions[0].settle_reservation_as_uncertain is True
    assert _status(engine_repo, run, "compile") is StepRunStatus.RECOVERY_REQUIRED
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED

    # The reservation became uncertain actual exposure, and the study was charged.
    reservation = session.get(BudgetReservationRow, reservation_id)
    assert reservation is not None
    assert reservation.status == ReservationStatus.SETTLED_UNCERTAIN.value
    assert reservation.settled_amount_usd == pytest.approx(2.00)

    position = engine_repo.budget_position()
    assert position["uncertain_usd"] == pytest.approx(2.00)
    assert position["spent_usd"] == pytest.approx(2.00), (
        "money that may already be gone must appear as spent, not available"
    )
    assert position["reserved_usd"] == pytest.approx(0.0)

    # The provider request id survives, so the call can later be reconciled.
    history = engine_repo.attempt_history(claimed.step_id)
    assert history[0]["provider_request_id"] == "req_abc123"
    assert history[0]["actual_cost_usd"] == pytest.approx(2.00)


def test_recovery_retries_a_paid_call_that_never_dispatched(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """Nothing left the process, so nothing was billed: safe to retry."""
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=2.00, provider=Provider.ANTHROPIC
    )
    # paid_call_dispatched stays False.
    _expire(session, claimed.attempt_id)

    decisions = engine_repo.recover_expired_attempts()
    assert decisions[0].action is RecoveryAction.RETRY
    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNABLE


def test_recovery_retries_a_paid_call_whose_outcome_is_known(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """Once the outcome is known there is no billing question left."""
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=2.00, provider=Provider.ANTHROPIC
    )
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id)
    engine_repo.mark_paid_call_outcome_known(claimed.attempt_id, actual_cost_usd=1.80)
    _expire(session, claimed.attempt_id)

    decisions = engine_repo.recover_expired_attempts()
    assert decisions[0].action is RecoveryAction.RETRY
    assert decisions[0].settle_reservation_as_uncertain is False


def test_subscription_runtime_is_always_safe_to_retry(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A repeated subscription call has no marginal cost, so no reservation.

    This is why the provider distinction must reach the recovery decision rather
    than being handled at the transport layer.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    assert (
        engine_repo.reserve_budget(
            attempt_id=claimed.attempt_id,
            amount_usd=5.0,
            provider=Provider.CLAUDE_CODE,
        )
        is None
    ), "a subscription runtime needs no reservation"

    _expire(session, claimed.attempt_id)
    assert engine_repo.recover_expired_attempts()[0].action is RecoveryAction.RETRY


def test_quota_parks_and_does_not_consume_an_attempt(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """**A quota pause is not a failed attempt.**

    Counting it would eventually exhaust max_attempts and fail a project that was
    only waiting for a quota window to reset.
    """
    reset_at = datetime.now(UTC) + timedelta(hours=1)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    decision = engine_repo.fail_attempt(
        claimed.attempt_id, failure=FailureClass.QUOTA, quota_reset_at=reset_at
    )

    assert decision.action is RecoveryAction.PARK_PROVIDER
    assert decision.consumes_attempt is False
    assert _status(engine_repo, run, "compile") is StepRunStatus.WAITING_PROVIDER
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.WAITING_PROVIDER

    step = next(s for s in engine_repo.get_run(run)["steps"] if s["node_key"] == "compile")
    assert step["attempts_consumed"] == 0, "the attempt was not counted against the limit"
    assert step["attempts_recorded"] == 1, "but the attempt itself is still in history"
    assert step["runnable_after"] is not None, "a resume time was scheduled"

    # And it is not claimable until the reset time.
    assert engine_repo.claim_next(worker_id="worker-2") is None


def test_a_parked_quota_step_becomes_claimable_after_its_reset_time(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """The resume mechanism: runnable_after gates the claim query."""
    past = datetime.now(UTC) - timedelta(minutes=5)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.fail_attempt(claimed.attempt_id, failure=FailureClass.QUOTA, quota_reset_at=past)

    # WAITING_PROVIDER is not RUNNABLE, so an operator or reconciler must release
    # it; simulate that, then confirm the time gate has passed.
    engine_repo.force_step_status(
        _step_id(engine_repo, run, "compile"),
        StepRunStatus.RUNNABLE,
        reason="quota window reset",
    )
    assert engine_repo.claim_next(worker_id="worker-2") is not None


def test_provider_capacity_parks_without_consuming_an_attempt(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """Capacity clears on its own, so it is a park, not a failure.

    It parks in ``WAITING_CAPACITY``, **not** ``WAITING_PROVIDER``: the two waits
    are separate states in the frozen v2.1 vocabulary because they recover
    differently. See :func:`test_provider_quota_and_capacity_are_separate_states`.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    decision = engine_repo.fail_attempt(claimed.attempt_id, failure=FailureClass.PROVIDER_CAPACITY)
    assert decision.action is RecoveryAction.PARK_CAPACITY
    assert decision.consumes_attempt is False
    assert _status(engine_repo, run, "compile") is StepRunStatus.WAITING_CAPACITY


def test_provider_quota_and_capacity_are_separate_states(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """**The two provider waits must not be merged.**

    An earlier draft collapsed them on the grounds that a researcher does not care
    which. Operationally they are different conditions with different recovery:
    quota is an entitlement wall that clears at a reset instant and may warrant
    raising a limit, capacity is an overload that clears by itself in minutes.
    Merged, a quota wall looks like a blip so nobody raises the limit, and a blip
    looks like a quota wall so somebody is paged for nothing.

    Both remain self-clearing, so neither appears on an operator's attention list.
    """
    reset_at = datetime.now(UTC) + timedelta(hours=1)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    quota = engine_repo.fail_attempt(
        claimed.attempt_id, failure=FailureClass.QUOTA, quota_reset_at=reset_at
    )

    second = WorkflowRepository(session, scoped.scope(user="lead", study="sibling"))
    project = ProjectRepository(session, scoped.scope(user="lead", study="sibling")).create(
        title="Capacity host", content={"goal": "g"}
    )[0]
    other_run = second.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=PIPELINE,
        idempotency_key=f"{project.project_id}:rev1:capacity",
    )
    other_claim = second.claim_next(worker_id="worker-2")
    assert other_claim is not None
    capacity = second.fail_attempt(other_claim.attempt_id, failure=FailureClass.PROVIDER_CAPACITY)

    assert quota.step_status is StepRunStatus.WAITING_PROVIDER
    assert capacity.step_status is StepRunStatus.WAITING_CAPACITY
    assert quota.step_status is not capacity.step_status
    assert quota.action is RecoveryAction.PARK_PROVIDER
    assert capacity.action is RecoveryAction.PARK_CAPACITY

    # Only the quota park schedules a resume; capacity has no reset instant.
    assert quota.retry_after == reset_at
    assert capacity.retry_after is None

    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert second.get_run(other_run)["status"] is WorkflowRunStatus.WAITING_CAPACITY

    assert WorkflowRunStatus.WAITING_PROVIDER.needs_attention is False
    assert WorkflowRunStatus.WAITING_CAPACITY.needs_attention is False
    assert StepRunStatus.WAITING_CAPACITY.is_waiting is True


def test_a_capacity_failure_does_not_bypass_the_uncertain_paid_call_guard() -> None:
    """**Splitting the provider waits must not weaken paid-call recovery.**

    A capacity error arriving after a metered call was dispatched still leaves the
    billing question open, so it must reach RECOVERY_REQUIRED and settle its
    reservation as uncertain -- not park as though nothing had been spent. The
    ordering inside `decide_recovery` is what guarantees it, and this asserts the
    ordering rather than trusting it.
    """
    decision = decide_recovery(
        failure=FailureClass.PROVIDER_CAPACITY,
        attempt_number=0,
        paid_call_dispatched=True,
        paid_call_outcome_known=False,
    )
    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert decision.step_status is StepRunStatus.RECOVERY_REQUIRED
    assert decision.settle_reservation_as_uncertain is True
    assert decision.reason == "paid_external_call_side_effect_uncertain"


def test_the_canonical_business_state_vocabulary_is_frozen() -> None:
    """The v2.1 contract, asserted so a rename cannot happen by accident.

    Two vocabularies active at once is the failure this guards against: a
    dashboard filtering on one set and an engine writing the other produces a
    study that is stuck with nothing on anyone's screen.
    """
    assert {s.value for s in WorkflowRunStatus} == {
        "PENDING",
        "RUNNING",
        "AWAITING_GATE",
        "AWAITING_BUDGET",
        "WAITING_PROVIDER",
        "WAITING_CAPACITY",
        "RECOVERY_REQUIRED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
    stale = {"WAITING_GATE", "WAITING_BUDGET"}
    assert not stale & {s.value for s in WorkflowRunStatus}
    assert not stale & {s.value for s in StepRunStatus}


def test_budget_exhaustion_parks_in_its_own_state(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """AWAITING_BUDGET is distinct from AWAITING_GATE.

    The prototype routed budget exhaustion through an approval in WAITING_USER.
    "A person must decide something" and "this study is out of money" need
    different dashboards and different alerts.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    decision = engine_repo.fail_attempt(claimed.attempt_id, failure=FailureClass.BUDGET_EXCEEDED)

    assert decision.action is RecoveryAction.PARK_BUDGET
    assert decision.consumes_attempt is False
    assert _status(engine_repo, run, "compile") is StepRunStatus.AWAITING_BUDGET
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.AWAITING_BUDGET


@pytest.mark.parametrize(
    "failure",
    [
        FailureClass.AUTHENTICATION,
        FailureClass.PERMISSION,
        FailureClass.MISSING_CONFIGURATION,
        FailureClass.SCHEMA_VIOLATION,
        FailureClass.UNKNOWN,
    ],
)
def test_permanent_failures_are_not_retried(
    engine_repo: WorkflowRepository, run: str, failure: FailureClass
) -> None:
    """Retrying these burns quota and hides a real misconfiguration.

    UNKNOWN is included deliberately: an error we do not understand must not be
    retried against a paid provider on the assumption that it is transient.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    decision = engine_repo.fail_attempt(claimed.attempt_id, failure=failure)
    assert decision.action is RecoveryAction.FAIL
    assert _status(engine_repo, run, "compile") is StepRunStatus.FAILED


def test_exhausted_attempts_need_a_human_rather_than_failing(
    engine_repo: WorkflowRepository, project: Any
) -> None:
    """Past the retry limit a person is required, matching the prototype.

    RECOVERY_REQUIRED rather than FAILED: a person may still be able to complete
    the work.
    """
    run_id = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k", max_attempts=2)],
        idempotency_key="single-1",
    )

    for _ in range(2):
        claimed = engine_repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        decision = engine_repo.fail_attempt(claimed.attempt_id, failure=FailureClass.TRANSPORT)

    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert decision.reason == "max_attempts_exhausted"
    assert engine_repo.get_run(run_id)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED


def test_attempt_history_is_append_only(engine_repo: WorkflowRepository, project: Any) -> None:
    """**Each attempt keeps its own error, provider and cost.**

    The prototype kept a counter and only the latest error, so a step that failed
    three different ways retained one. This is the improvement that replaces it.
    """
    run_id = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="retrying",
        steps=[StepDefinition(node_key="only", kind="k", max_attempts=3)],
        idempotency_key="retrying-1",
    )

    errors = ["first transport blip", "second transport blip"]
    for message in errors:
        claimed = engine_repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        engine_repo.fail_attempt(
            claimed.attempt_id,
            failure=FailureClass.TRANSPORT,
            error={"message": message},
        )

    step_id = _step_id(engine_repo, run_id, "only")
    history = engine_repo.attempt_history(step_id)

    assert [a["attempt_number"] for a in history] == [1, 2]
    assert [a["error"]["message"] for a in history] == errors, (
        "every attempt's error survives, not just the latest"
    )
    assert all(a["status"] is AttemptStatus.FAILED for a in history)


# --------------------------------------------------------------------------- #
# Accounting transactionality
# --------------------------------------------------------------------------- #


def test_reservations_prevent_concurrent_overspend(
    engine_repo: WorkflowRepository, project: Any, session: Session
) -> None:
    """Reserved funds count as spent, so two workers cannot both pass the check.

    Without this, two workers each seeing $6 of a $10 budget would both approve a
    $3 call and together spend $12.
    """
    _fund_study(session, engine_repo.scope.study_id, 10.0)
    run_id = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="parallel-paid",
        steps=[
            StepDefinition(node_key="a", kind="k"),
            StepDefinition(node_key="b", kind="k"),
        ],
        idempotency_key="parallel-paid-1",
    )

    first = engine_repo.claim_next(worker_id="worker-1")
    second = engine_repo.claim_next(worker_id="worker-2")
    assert first is not None and second is not None

    engine_repo.reserve_budget(
        attempt_id=first.attempt_id, amount_usd=8.0, provider=Provider.ANTHROPIC
    )
    with pytest.raises(BudgetExceeded) as exc:
        engine_repo.reserve_budget(
            attempt_id=second.attempt_id, amount_usd=8.0, provider=Provider.ANTHROPIC
        )

    assert exc.value.remaining == pytest.approx(2.0)
    assert engine_repo.budget_position()["available_usd"] == pytest.approx(2.0)
    assert engine_repo.get_run(run_id)["status"] is WorkflowRunStatus.RUNNING


def test_an_exact_limit_reservation_is_permitted(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """Spending exactly the budget is allowed; float drift must not block it."""
    _fund_study(session, engine_repo.scope.study_id, 10.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    assert (
        engine_repo.reserve_budget(
            attempt_id=claimed.attempt_id, amount_usd=10.0, provider=Provider.ANTHROPIC
        )
        is not None
    )


def test_settling_a_reservation_charges_the_actual_cost(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A completed call charges what it really cost, not the estimate."""
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    reservation_id = engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=5.0, provider=Provider.ANTHROPIC
    )

    engine_repo.complete_attempt(
        claimed.attempt_id, actual_cost_usd=3.25, reservation_id=reservation_id
    )

    position = engine_repo.budget_position()
    assert position["spent_usd"] == pytest.approx(3.25)
    assert position["reserved_usd"] == pytest.approx(0.0)
    assert position["available_usd"] == pytest.approx(96.75)


def test_releasing_a_reservation_charges_nothing(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A pre-dispatch failure returns the held budget to the study."""
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    reservation_id = engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=5.0, provider=Provider.ANTHROPIC
    )

    engine_repo.fail_attempt(
        claimed.attempt_id,
        failure=FailureClass.TRANSPORT,
        reservation_id=reservation_id,
    )

    position = engine_repo.budget_position()
    assert position["spent_usd"] == pytest.approx(0.0)
    assert position["reserved_usd"] == pytest.approx(0.0)
    assert position["available_usd"] == pytest.approx(100.0)


def test_every_reservation_resolves_to_a_study(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """Usage with no corresponding study must be unrepresentable.

    ``study_id`` is non-null and foreign-keyed, so a reservation cannot exist
    without the study it bills.
    """
    _fund_study(session, engine_repo.scope.study_id, 50.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    reservation_id = engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=1.0, provider=Provider.ANTHROPIC
    )

    reservation = session.get(BudgetReservationRow, reservation_id)
    assert reservation is not None
    assert reservation.study_id == engine_repo.scope.study_id
    assert reservation.run_id == run
    assert reservation.attempt_id == claimed.attempt_id


def test_a_reservation_requires_an_existing_attempt(engine_repo: WorkflowRepository) -> None:
    """A provider call with no attempt behind it must be impossible.

    The attempt is committed before dispatch, so reserving against an unknown
    attempt is refused outright.
    """
    with pytest.raises(WorkflowNotFound):
        engine_repo.reserve_budget(
            attempt_id="ATT-does-not-exist",
            amount_usd=1.0,
            provider=Provider.ANTHROPIC,
        )


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


def test_cancelling_a_running_step_is_cooperative(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """A running step is flagged, not killed.

    The worker polls at checkpoints, so cancellation leaves a consistent artifact
    state rather than a half-written one.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    engine_repo.request_cancel(run, reason="user changed their mind")

    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNING
    assert engine_repo.is_cancel_requested(claimed.step_id) is True
    # Not-yet-started steps are cancelled immediately.
    assert _status(engine_repo, run, "research") is StepRunStatus.CANCELLED


def test_a_cancelled_run_yields_no_more_work(engine_repo: WorkflowRepository, run: str) -> None:
    """No worker picks up a step from a cancelling run."""
    engine_repo.request_cancel(run)
    assert engine_repo.claim_next(worker_id="worker-1") is None
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


def test_abandoning_an_attempt_completes_the_cancellation(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """The worker noticing the flag closes out the attempt and the run."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.request_cancel(run)

    engine_repo.abandon_attempt(claimed.attempt_id, reason="cancel observed")

    assert engine_repo.attempt_history(claimed.step_id)[0]["status"] is (AttemptStatus.ABANDONED)
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


def test_cancelling_a_finished_run_changes_nothing(
    engine_repo: WorkflowRepository, project: Any
) -> None:
    """A completed run stays completed."""
    run_id = engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key="single-done",
    )
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id)

    assert engine_repo.request_cancel(run_id) is WorkflowRunStatus.COMPLETED


def test_cancellation_closes_pending_gates(engine_repo: WorkflowRepository, run: str) -> None:
    """A cancelled run leaves nothing sitting in someone's approval queue."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.open_gate(
        step_id=claimed.step_id, question="Continue?", options=["proceed", "cancel"]
    )
    assert len(engine_repo.pending_gates(run)) == 1

    engine_repo.request_cancel(run)
    assert engine_repo.pending_gates(run) == []


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #


def test_opening_a_gate_parks_the_step_and_the_run(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """A gate is a business state, not a framework interrupt.

    It may sit unanswered for days and must survive a deploy, which is why it is
    a row rather than a suspended coroutine.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    engine_repo.open_gate(
        step_id=claimed.step_id,
        question="Continue on the paid API?",
        options=["use_anthropic_api", "cancel"],
        context={"provider_estimates_usd": {"anthropic": 12.5}},
    )

    assert _status(engine_repo, run, "compile") is StepRunStatus.AWAITING_GATE
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.AWAITING_GATE

    gates = engine_repo.pending_gates(run)
    assert gates[0]["options"] == ["use_anthropic_api", "cancel"]
    assert gates[0]["context"]["provider_estimates_usd"]["anthropic"] == 12.5


def test_gate_option_must_be_one_of_those_offered(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """Accepting an arbitrary string means acting on a decision nobody made."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Continue?", options=["proceed", "cancel"]
    )

    reviewer = WorkflowRepository(session, scoped.scope(user="reviewer", study="primary"))
    for bad in ("", "yes", "use_anthropic_api"):
        with pytest.raises(ValueError, match="invalid gate option"):
            reviewer.decide_gate(gate_id, option=bad)


def test_a_gate_is_decided_once(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """A replayed decision cannot re-spend or re-release."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Continue?", options=["proceed", "cancel"]
    )

    reviewer = WorkflowRepository(session, scoped.scope(user="reviewer", study="primary"))
    reviewer.decide_gate(gate_id, option="proceed")
    with pytest.raises(ValueError, match="already decided"):
        reviewer.decide_gate(gate_id, option="cancel")


def test_regression_gate_producer_cannot_decide_their_own_gate(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """**Independent review is the default.** Self-approval is off unless enabled.

    A LEAD holds both EDIT_STUDY and APPROVE_GATE, so the permission check alone
    would let one person produce the work and clear its own review gate by
    switching hats. Independent review means a different person, not a different
    permission.

    This fixture configures no self-approval anywhere, so the policy resolves to
    the default of false and the approval is refused. The cases where policy
    permits it are in ``test_self_approval_policy.py``; what is permanent is that
    a deployment which has configured nothing gets this behaviour.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Approve this report?", options=["proceed"]
    )

    with pytest.raises(SeparationOfDutiesViolation) as exc:
        engine_repo.decide_gate(gate_id, option="proceed")
    assert exc.value.reason == "separation_of_duties"
    assert _status(engine_repo, run, "compile") is StepRunStatus.AWAITING_GATE


def test_a_different_reviewer_can_decide_the_gate(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """Independence satisfied: the step is released."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Approve?", options=["proceed"]
    )

    reviewer = WorkflowRepository(session, scoped.scope(user="reviewer", study="primary"))
    assert reviewer.decide_gate(gate_id, option="proceed") is StepRunStatus.RUNNABLE
    assert engine_repo.claim_next(worker_id="worker-2") is not None


def test_deciding_cancel_on_a_gate_cancels_the_step(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """A gate is also a way to stop work."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Continue?", options=["proceed", "cancel"]
    )

    reviewer = WorkflowRepository(session, scoped.scope(user="reviewer", study="primary"))
    assert reviewer.decide_gate(gate_id, option="cancel") is StepRunStatus.CANCELLED


def test_a_researcher_cannot_decide_a_gate(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """Approval authority is a permission, checked before independence."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    gate_id = engine_repo.open_gate(
        step_id=claimed.step_id, question="Approve?", options=["proceed"]
    )

    researcher = WorkflowRepository(session, scoped.scope(user="researcher", study="primary"))
    with pytest.raises(ScopeDenied):
        researcher.decide_gate(gate_id, option="proceed")


# --------------------------------------------------------------------------- #
# Run status derivation
# --------------------------------------------------------------------------- #


def test_run_status_precedence() -> None:
    """Derivation order drives the operator dashboard.

    FAILED outranks everything. RECOVERY_REQUIRED next, because money may be at
    stake. AWAITING_BUDGET and AWAITING_GATE outrank the provider waits, because they
    need a person while a provider wait clears itself.
    """
    running = [StepRunStatus.RUNNING, StepRunStatus.BLOCKED]
    assert derive_run_status(running) is WorkflowRunStatus.RUNNING

    assert (
        derive_run_status([*running, StepRunStatus.WAITING_PROVIDER])
        is WorkflowRunStatus.WAITING_PROVIDER
    )
    assert (
        derive_run_status([*running, StepRunStatus.WAITING_PROVIDER, StepRunStatus.AWAITING_GATE])
        is WorkflowRunStatus.AWAITING_GATE
    )
    assert (
        derive_run_status([*running, StepRunStatus.AWAITING_GATE, StepRunStatus.AWAITING_BUDGET])
        is WorkflowRunStatus.AWAITING_BUDGET
    )
    assert (
        derive_run_status(
            [*running, StepRunStatus.AWAITING_BUDGET, StepRunStatus.RECOVERY_REQUIRED]
        )
        is WorkflowRunStatus.RECOVERY_REQUIRED
    )
    assert (
        derive_run_status([*running, StepRunStatus.RECOVERY_REQUIRED, StepRunStatus.FAILED])
        is WorkflowRunStatus.FAILED
    )


def test_an_empty_run_is_pending_not_completed() -> None:
    """A run with no steps has not succeeded at anything.

    Reporting COMPLETED would let a caller believe work was done.
    """
    assert derive_run_status([]) is WorkflowRunStatus.PENDING


def test_a_skipped_step_satisfies_a_dependency() -> None:
    """A deliberately skipped step does not stall the pipeline, unlike a failure."""
    assert StepRunStatus.SKIPPED.satisfies_dependency is True
    assert StepRunStatus.SUCCEEDED.satisfies_dependency is True
    assert StepRunStatus.FAILED.satisfies_dependency is False
    assert StepRunStatus.CANCELLED.satisfies_dependency is False

    assert (
        derive_run_status([StepRunStatus.SUCCEEDED, StepRunStatus.SKIPPED])
        is WorkflowRunStatus.COMPLETED
    )


def test_runs_needing_attention_excludes_self_clearing_waits(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """An operator dashboard should not nag about a provider wait."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.fail_attempt(claimed.attempt_id, failure=FailureClass.PROVIDER_CAPACITY)

    assert engine_repo.runs_needing_attention() == []

    engine_repo.force_step_status(claimed.step_id, StepRunStatus.AWAITING_BUDGET, reason="test")
    assert [r["run_id"] for r in engine_repo.runs_needing_attention()] == [run]


# --------------------------------------------------------------------------- #
# Failure classification
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("QUOTA", FailureClass.QUOTA),
        ("CAPACITY", FailureClass.PROVIDER_CAPACITY),
        ("AUTHENTICATION", FailureClass.AUTHENTICATION),
        ("PERMISSION", FailureClass.PERMISSION),
        ("MISSING", FailureClass.MISSING_CONFIGURATION),
        ("MODEL", FailureClass.MODEL_UNAVAILABLE),
        ("SCHEMA", FailureClass.SCHEMA_VIOLATION),
        ("TRANSPORT", FailureClass.TRANSPORT),
        ("SDK_OUTDATED", FailureClass.SDK_OUTDATED),
        ("MAX_TURNS", FailureClass.MAX_TURNS),
        ("OTHER", FailureClass.UNKNOWN),
        ("something_unrecognised", FailureClass.UNKNOWN),
        (None, FailureClass.UNKNOWN),
    ],
)
def test_failure_tags_map_to_classes(tag: str | None, expected: FailureClass) -> None:
    """The prototype's taxonomy, preserved as data."""
    assert classify_failure(tag) is expected


def test_unknown_failures_are_permanent_not_retryable() -> None:
    """An error we do not understand must not be retried against a paid provider."""
    assert FailureClass.UNKNOWN.is_permanent is True
    assert FailureClass.UNKNOWN.is_retryable is False


def test_non_consuming_failures_are_exactly_quota_budget_and_approval() -> None:
    """These three are not failures of the work, so they do not count attempts."""
    non_consuming = {f for f in FailureClass if not f.consumes_attempt}
    assert non_consuming == {
        FailureClass.QUOTA,
        FailureClass.BUDGET_EXCEEDED,
        FailureClass.APPROVAL_REQUIRED,
    }


def test_approval_required_parks_without_consuming_an_attempt() -> None:
    """A gate is not a failed attempt either."""
    decision = decide_recovery(
        failure=FailureClass.APPROVAL_REQUIRED,
        attempt_number=3,
        max_attempts=3,
        paid_call_dispatched=False,
        paid_call_outcome_known=True,
    )
    assert decision.action is RecoveryAction.PARK_GATE
    assert decision.consumes_attempt is False


def test_uncertain_billing_outranks_permanence_and_attempt_count() -> None:
    """Even a permanent error leaves the question of whether the call was billed.

    So the uncertain-paid-call branch is checked before permanence and before the
    attempt limit.
    """
    decision = decide_recovery(
        failure=FailureClass.AUTHENTICATION,
        attempt_number=99,
        max_attempts=1,
        paid_call_dispatched=True,
        paid_call_outcome_known=False,
    )
    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert decision.settle_reservation_as_uncertain is True


# --------------------------------------------------------------------------- #
# Scope isolation and events
# --------------------------------------------------------------------------- #


def test_workflow_repository_requires_a_study_context(session: Session) -> None:
    """Unscoped workflow access is not constructible."""
    for bogus in (None, "STU-1", {"study_id": "STU-1"}):
        with pytest.raises(TypeError, match="requires a StudyContext"):
            WorkflowRepository(session, bogus)  # type: ignore[arg-type]


def test_runs_are_invisible_across_clients(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """A run is never addressable by id alone."""
    other = WorkflowRepository(session, scoped.scope(user="other_lead", study="other_client"))

    # Reads and writes alike raise WorkflowNotFound -- not ScopeDenied -- even
    # though this caller is a LEAD on their own study and therefore *does* hold
    # CANCEL_WORKFLOW. The run simply does not exist in their scope, which is
    # exactly the answer that discloses nothing about another client.
    for operation in (
        lambda: other.get_run(run),
        lambda: other.events(run),
        lambda: other.request_cancel(run),
        lambda: other.release_ready_steps(run),
    ):
        with pytest.raises(WorkflowNotFound):
            operation()

    assert other.claim_next(worker_id="worker-x") is None


def test_a_viewer_cannot_start_a_run(session: Session, scoped: Any, project: Any) -> None:
    """Running a workflow spends money, so it needs more than read access."""
    viewer = WorkflowRepository(session, scoped.scope(user="viewer", study="primary"))
    with pytest.raises(ScopeDenied):
        viewer.create_run(
            project_id=project.project_id,
            project_revision=1,
            workflow_type="x",
            steps=PIPELINE,
            idempotency_key="viewer-attempt",
        )


def test_events_are_ordered_and_resumable(engine_repo: WorkflowRepository, run: str) -> None:
    """Monotonic ids let a reconnecting client resume without gaps or duplicates."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id)

    events = engine_repo.events(run)
    ids = [e["event_id"] for e in events]
    assert ids == sorted(ids)

    types = [e["event_type"] for e in events]
    assert types[0] == "RUN_CREATED"
    assert "ATTEMPT_CLAIMED" in types
    assert "STEP_SUCCEEDED" in types

    midpoint = ids[len(ids) // 2]
    assert all(e["event_id"] > midpoint for e in engine_repo.events(run, since=midpoint))


def test_recovery_of_a_paid_call_is_logged_with_its_exposure(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """The operator needs the figure, not just the state.

    This payload is what the UI renders as "Accounting: $2.00 uncertain".
    """
    _fund_study(session, engine_repo.scope.study_id, 100.0)
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id, amount_usd=2.0, provider=Provider.ANTHROPIC
    )
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id)
    _expire(session, claimed.attempt_id)
    engine_repo.recover_expired_attempts()

    recovery = [e for e in engine_repo.events(run) if e["event_type"] == "STEP_RECOVERY"]
    assert recovery[-1]["payload"]["conservative_cost_exposure_usd"] == pytest.approx(2.0)
    assert recovery[-1]["level"] == "WARN"


def test_forcing_a_status_requires_authority_and_a_reason(
    engine_repo: WorkflowRepository, run: str, scoped: Any, session: Session
) -> None:
    """The prototype's ``force=True`` keyword was reachable by accident.

    Here it is a separate named method requiring MANAGE_STUDY_ACCESS and a
    recorded reason, because it can move a step out of a terminal state.
    """
    step_id = _step_id(engine_repo, run, "compile")

    with pytest.raises(ValueError, match="reason"):
        engine_repo.force_step_status(step_id, StepRunStatus.SUCCEEDED, reason="")

    researcher = WorkflowRepository(session, scoped.scope(user="researcher", study="primary"))
    with pytest.raises(ScopeDenied):
        researcher.force_step_status(step_id, StepRunStatus.SUCCEEDED, reason="I know better")

    engine_repo.force_step_status(
        step_id, StepRunStatus.SKIPPED, reason="already delivered manually"
    )
    forced = [e for e in engine_repo.events(run) if e["event_type"] == "STEP_FORCED"]
    assert "already delivered manually" in forced[-1]["message"]
    assert forced[-1]["level"] == "WARN"


# --------------------------------------------------------------------------- #
# Restart durability
# --------------------------------------------------------------------------- #


def test_state_survives_a_new_repository_and_session(
    engine_repo: WorkflowRepository, run: str, session: Session, scoped: Any
) -> None:
    """The restart guarantee: the queue is in the database, not in memory.

    An API or worker process dying loses nothing.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    session.commit()

    reopened = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    state = reopened.get_run(run)

    assert state["status"] is WorkflowRunStatus.RUNNING
    assert reopened.attempt_history(claimed.step_id)[0]["worker_id"] == "worker-1"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _fund_study(session: Session, study_id: str, budget_usd: float) -> None:
    """Give a study a budget, bypassing the permission check."""
    study = session.get(StudyRow, study_id)
    assert study is not None
    study.budget_usd = budget_usd
    study.spent_usd = 0.0
    session.flush()


def _expire(session: Session, attempt_id: str) -> None:
    """Force an attempt's lease into the past, simulating a dead worker."""
    from aia_core.infrastructure.tables import StepAttemptRow

    attempt = session.get(StepAttemptRow, attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()


def test_helpers_are_used_only_for_setup() -> None:
    """Guard against a helper drifting into production use.

    ``_fund_study`` and ``_expire`` write state that production reaches only
    through permission-checked paths, so they must stay in the test module.
    """
    import aia_core.infrastructure.workflow_repository as module

    source = select  # keep the import referenced
    assert source is not None
    assert not hasattr(module, "_fund_study")
    assert not hasattr(module, "_expire")


# --------------------------------------------------------------------------- #
# Timezone portability -- a regression the two-engine CI caught
# --------------------------------------------------------------------------- #


def test_regression_lease_comparison_survives_a_naive_timestamp() -> None:
    """**A lease deadline read from SQLite has no offset. Handle it.**

    PostgreSQL round-trips ``TIMESTAMP WITH TIME ZONE`` faithfully; SQLite stores
    no offset at all, so a deadline written as aware UTC comes back naive.
    Comparing the two raised ``TypeError`` and crashed every recovery path on
    SQLite while passing on PostgreSQL -- found only because CI runs both.

    Every timestamp this system writes is UTC, so a naive value is interpreted as
    UTC. That assumption is what makes the normalisation safe.
    """
    from aia_core.domain.workflow import as_utc

    naive_past = datetime(2020, 1, 1, 0, 0, 0)
    naive_future = datetime(2099, 1, 1, 0, 0, 0)

    assert is_lease_expired(naive_past) is True
    assert is_lease_expired(naive_future) is False

    # Mixed awareness, in both directions, must not raise.
    assert is_lease_expired(naive_past, now=datetime.now(UTC)) is True
    assert is_lease_expired(datetime.now(UTC), now=naive_future) is True

    assert as_utc(naive_past) == naive_past.replace(tzinfo=UTC)
    assert as_utc(None) is None


def test_regression_recovery_works_when_the_backend_drops_timezones(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """Recovery must work on both backends, with a naive stored deadline.

    This exercises the whole path rather than the comparison in isolation: a
    naive `lease_until` is exactly what SQLite hands back, and recovery is
    safety-critical.
    """
    from aia_core.infrastructure.tables import StepAttemptRow

    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    # Naive, as SQLite would return it.
    attempt.lease_until = datetime(2020, 1, 1, 0, 0, 0)
    session.flush()

    decisions = engine_repo.recover_expired_attempts()
    assert [d.action for d in decisions] == [RecoveryAction.RETRY]
    assert _status(engine_repo, run, "compile") is StepRunStatus.RUNNABLE
