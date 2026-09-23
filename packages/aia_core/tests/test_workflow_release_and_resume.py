"""Releasing an attempt on shutdown, resuming provider parks, and cancel-wins.

Three rules a worker needs that the engine did not have
(``.planning/plans/done/worker-process.md``):

* **Release.** A worker shutting down cleanly gives its attempt back: the step
  is runnable at once and the attempt is not counted -- unless a paid call is in
  flight, which is ``RECOVERY_REQUIRED`` exactly as a crash would be.
* **Resume (W6).** ``WAITING_PROVIDER`` and ``WAITING_CAPACITY`` were never moved
  back to ``RUNNABLE`` by anything; a park stranded its step.
* **Cancel wins (W7).** A run cancelled while its step was running, whose worker
  then died, recovered the step to ``RUNNABLE`` -- which a cancel-requested step
  never leaves -- so the run stayed ``RUNNING`` forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import (
    DEFAULT_CAPACITY_BACKOFF_SECONDS,
    DEFAULT_QUOTA_FALLBACK_SECONDS,
    AttemptStatus,
    FailureClass,
    RecoveryAction,
    RecoveryDecision,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
    apply_cancellation,
    decide_recovery,
    decide_release,
    resume_due,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import (
    BudgetReservationRow,
    StepAttemptRow,
    StepRunRow,
    StudyRow,
)
from aia_core.infrastructure.workflow_repository import ClaimedWork, WorkflowRepository

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Domain: decide_release
# --------------------------------------------------------------------------- #


def test_a_release_is_a_non_consuming_retry() -> None:
    """Three rolling deploys must not fail a step that never did anything wrong."""
    decision = decide_release(paid_call_dispatched=False, paid_call_outcome_known=False)

    assert decision.action is RecoveryAction.RETRY
    assert decision.step_status is StepRunStatus.RUNNABLE
    assert decision.consumes_attempt is False
    assert decision.settle_reservation_as_uncertain is False


def test_a_release_after_a_known_outcome_is_still_a_retry() -> None:
    """Once the call's outcome is recorded there is no billing question."""
    decision = decide_release(paid_call_dispatched=True, paid_call_outcome_known=True)
    assert decision.action is RecoveryAction.RETRY


def test_a_release_with_a_call_in_flight_is_recovery_required() -> None:
    """For billing purposes a release mid-call is a crash mid-call."""
    released = decide_release(paid_call_dispatched=True, paid_call_outcome_known=False)
    crashed = decide_recovery(
        failure=None, attempt_number=1, paid_call_dispatched=True, paid_call_outcome_known=False
    )

    assert released.action is crashed.action is RecoveryAction.RECOVERY_REQUIRED
    assert released.settle_reservation_as_uncertain is True
    assert released.reason == crashed.reason


# --------------------------------------------------------------------------- #
# Domain: apply_cancellation
# --------------------------------------------------------------------------- #


def test_cancellation_turns_a_retry_into_a_cancel() -> None:
    retry = decide_recovery(
        failure=None, attempt_number=1, paid_call_dispatched=False, paid_call_outcome_known=False
    )
    decision = apply_cancellation(retry, cancel_requested=True)

    assert decision.action is RecoveryAction.CANCEL
    assert decision.step_status is StepRunStatus.CANCELLED
    assert decision.reason == "cancelled_after_expired_lease_idempotent_or_subscription"


def test_cancellation_keeps_the_accounting_half_of_an_uncertain_decision() -> None:
    """Cancelling does not make an in-flight call's cost go away."""
    uncertain = decide_recovery(
        failure=None, attempt_number=1, paid_call_dispatched=True, paid_call_outcome_known=False
    )
    decision = apply_cancellation(uncertain, cancel_requested=True)

    assert decision.step_status is StepRunStatus.CANCELLED
    assert decision.settle_reservation_as_uncertain is True


@pytest.mark.parametrize(
    "decision",
    [
        RecoveryDecision(
            action=RecoveryAction.PARK_PROVIDER,
            step_status=StepRunStatus.WAITING_PROVIDER,
            reason="q",
            consumes_attempt=False,
            retry_after=NOW,
        ),
        RecoveryDecision(
            action=RecoveryAction.PARK_GATE,
            step_status=StepRunStatus.AWAITING_GATE,
            reason="g",
            consumes_attempt=False,
        ),
    ],
)
def test_cancellation_also_wins_over_a_park(decision: RecoveryDecision) -> None:
    cancelled = apply_cancellation(decision, cancel_requested=True)
    assert cancelled.step_status is StepRunStatus.CANCELLED
    assert cancelled.retry_after is None


def test_a_terminal_decision_is_left_alone() -> None:
    """A permanent failure is still a failure, cancelled or not."""
    failed = decide_recovery(
        failure=FailureClass.AUTHENTICATION,
        attempt_number=1,
        paid_call_dispatched=False,
        paid_call_outcome_known=False,
    )
    assert apply_cancellation(failed, cancel_requested=True) is failed


def test_no_cancellation_changes_nothing() -> None:
    retry = decide_release(paid_call_dispatched=False, paid_call_outcome_known=False)
    assert apply_cancellation(retry, cancel_requested=False) is retry


# --------------------------------------------------------------------------- #
# Domain: resume_due
# --------------------------------------------------------------------------- #


def test_a_quota_park_resumes_at_its_reset_instant() -> None:
    reset = NOW + timedelta(minutes=10)
    kwargs: dict[str, Any] = {"runnable_after": reset, "parked_at": NOW - timedelta(hours=1)}

    assert resume_due(StepRunStatus.WAITING_PROVIDER, now=NOW, **kwargs) is False
    assert resume_due(StepRunStatus.WAITING_PROVIDER, now=reset, **kwargs) is True


def test_a_quota_park_with_no_reset_instant_falls_back_rather_than_strands() -> None:
    parked = NOW
    before = parked + timedelta(seconds=DEFAULT_QUOTA_FALLBACK_SECONDS - 1)
    after = parked + timedelta(seconds=DEFAULT_QUOTA_FALLBACK_SECONDS)

    def due(now: datetime) -> bool:
        return resume_due(
            StepRunStatus.WAITING_PROVIDER, runnable_after=None, parked_at=parked, now=now
        )

    assert due(before) is False
    assert due(after) is True


def test_a_capacity_park_resumes_after_its_back_off() -> None:
    parked = NOW
    assert (
        resume_due(
            StepRunStatus.WAITING_CAPACITY,
            runnable_after=None,
            parked_at=parked,
            now=parked + timedelta(seconds=DEFAULT_CAPACITY_BACKOFF_SECONDS - 1),
        )
        is False
    )
    assert (
        resume_due(
            StepRunStatus.WAITING_CAPACITY,
            runnable_after=None,
            parked_at=parked,
            now=parked + timedelta(seconds=DEFAULT_CAPACITY_BACKOFF_SECONDS),
        )
        is True
    )


@pytest.mark.parametrize(
    "status",
    [
        StepRunStatus.AWAITING_GATE,
        StepRunStatus.AWAITING_BUDGET,
        StepRunStatus.RECOVERY_REQUIRED,
        StepRunStatus.RUNNING,
        StepRunStatus.BLOCKED,
        StepRunStatus.FAILED,
    ],
)
def test_nothing_a_person_owes_a_decision_on_ever_resumes_by_timer(
    status: StepRunStatus,
) -> None:
    """``AWAITING_*`` means a person decides. A timer resuming it decides for them."""
    long_ago = NOW - timedelta(days=30)
    assert resume_due(status, runnable_after=long_ago, parked_at=long_ago, now=NOW) is False


def test_resume_due_reads_naive_timestamps_as_utc() -> None:
    """SQLite hands timestamps back without an offset; see ``as_utc``."""
    naive_reset = datetime(2026, 9, 22, 11, 0)
    assert (
        resume_due(
            StepRunStatus.WAITING_PROVIDER, runnable_after=naive_reset, parked_at=None, now=NOW
        )
        is True
    )


# --------------------------------------------------------------------------- #
# Repository fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def engine_repo(session: Session, scoped: Any) -> WorkflowRepository:
    repo = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    study = session.get(StudyRow, repo.scope.study_id)
    assert study is not None
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()
    return repo


@pytest.fixture
def run(engine_repo: WorkflowRepository, session: Session, scoped: Any) -> str:
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Release host", content={"goal": "g"}
    )
    return engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key="release-run",
    )


@pytest.fixture
def claimed(engine_repo: WorkflowRepository, run: str) -> ClaimedWork:
    work = engine_repo.claim_next(worker_id="worker-1")
    assert work is not None
    return work


def _step(repo: WorkflowRepository, run_id: str) -> dict[str, Any]:
    step: dict[str, Any] = repo.get_run(run_id)["steps"][0]
    return step


def _park(session: Session, step_id: str, status: StepRunStatus, **fields: Any) -> None:
    """Put a step straight into a parked state, as a failed attempt would."""
    step = session.get(StepRunRow, step_id)
    assert step is not None
    step.status = status.value
    for name, value in fields.items():
        setattr(step, name, value)
    session.flush()


# --------------------------------------------------------------------------- #
# Repository: release_attempt
# --------------------------------------------------------------------------- #


def test_releasing_makes_the_step_claimable_at_once_without_consuming_an_attempt(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork, session: Session
) -> None:
    reservation_id = engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id,
        worker_id="worker-1",
        amount_usd=2.0,
        provider=Provider.ANTHROPIC,
    )

    decision = engine_repo.release_attempt(claimed.attempt_id, worker_id="worker-1")

    assert decision.action is RecoveryAction.RETRY
    step = _step(engine_repo, run)
    assert step["status"] is StepRunStatus.RUNNABLE
    assert step["attempts_consumed"] == 0
    assert step["attempts"][0]["status"] is AttemptStatus.ABANDONED
    reservation = session.get(BudgetReservationRow, reservation_id)
    assert reservation is not None
    assert reservation.status == ReservationStatus.RELEASED.value

    successor = engine_repo.claim_next(worker_id="worker-2")
    assert successor is not None, "no lease to wait out"
    assert successor.attempt_number == 2


def test_releasing_with_a_call_in_flight_is_recovery_required(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork
) -> None:
    engine_repo.reserve_budget(
        attempt_id=claimed.attempt_id,
        worker_id="worker-1",
        amount_usd=2.0,
        provider=Provider.ANTHROPIC,
    )
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")

    decision = engine_repo.release_attempt(claimed.attempt_id, worker_id="worker-1")

    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert _step(engine_repo, run)["status"] is StepRunStatus.RECOVERY_REQUIRED
    assert engine_repo.budget_position()["uncertain_usd"] == pytest.approx(2.0)
    assert engine_repo.claim_next(worker_id="worker-2") is None


def test_releasing_a_cancelled_step_cancels_it(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork
) -> None:
    """Shutdown and cancellation arriving together: cancellation wins."""
    engine_repo.request_cancel(run)

    decision = engine_repo.release_attempt(claimed.attempt_id, worker_id="worker-1")

    assert decision.action is RecoveryAction.CANCEL
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


# --------------------------------------------------------------------------- #
# Repository: cancel wins on recovery (W7)
# --------------------------------------------------------------------------- #


def test_regression_a_cancelled_run_whose_worker_died_finishes_cancelled(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork, session: Session
) -> None:
    """**W7.** Before: recovery said RETRY, the step went RUNNABLE, nothing could
    ever claim it, and the run read RUNNING indefinitely.
    """
    engine_repo.request_cancel(run)
    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()

    decisions = engine_repo.recover_expired_attempts()

    assert [d.action for d in decisions] == [RecoveryAction.CANCEL]
    assert _step(engine_repo, run)["status"] is StepRunStatus.CANCELLED
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


def test_a_failure_reported_after_cancellation_cancels_the_step(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork
) -> None:
    engine_repo.request_cancel(run)

    decision = engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.TRANSPORT
    )

    assert decision.action is RecoveryAction.CANCEL
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


# --------------------------------------------------------------------------- #
# Repository: resume_waiting_steps (W6)
# --------------------------------------------------------------------------- #


def test_regression_a_quota_park_resumes_once_its_reset_passes(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork
) -> None:
    """**W6.** Before, the step stayed WAITING_PROVIDER until an operator forced it."""
    reset = datetime.now(UTC) + timedelta(minutes=30)
    engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.QUOTA, quota_reset_at=reset
    )

    assert engine_repo.resume_waiting_steps() == [], "not before the reset"
    assert engine_repo.resume_waiting_steps(now=reset + timedelta(seconds=1)) == [claimed.step_id]

    assert _step(engine_repo, run)["status"] is StepRunStatus.RUNNABLE
    assert engine_repo.get_run(run)["status"] is WorkflowRunStatus.RUNNING
    assert engine_repo.claim_next(worker_id="worker-2") is not None


def test_a_capacity_park_resumes_after_the_back_off(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork
) -> None:
    engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.PROVIDER_CAPACITY
    )

    assert engine_repo.resume_waiting_steps(capacity_backoff_seconds=3600) == []
    assert engine_repo.resume_waiting_steps(capacity_backoff_seconds=0) == [claimed.step_id]
    assert _step(engine_repo, run)["status"] is StepRunStatus.RUNNABLE


@pytest.mark.parametrize(
    "status",
    [StepRunStatus.AWAITING_GATE, StepRunStatus.AWAITING_BUDGET, StepRunStatus.RECOVERY_REQUIRED],
)
def test_the_sweep_never_resumes_what_a_person_must_decide(
    engine_repo: WorkflowRepository,
    run: str,
    claimed: ClaimedWork,
    session: Session,
    status: StepRunStatus,
) -> None:
    long_ago = datetime.now(UTC) - timedelta(days=30)
    _park(session, claimed.step_id, status, runnable_after=long_ago, updated_at=long_ago)

    assert engine_repo.resume_waiting_steps(capacity_backoff_seconds=0) == []
    assert _step(engine_repo, run)["status"] is status


def test_the_sweep_leaves_a_cancelled_runs_parks_alone(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork, session: Session
) -> None:
    engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.PROVIDER_CAPACITY
    )
    engine_repo.request_cancel(run)

    assert engine_repo.resume_waiting_steps(capacity_backoff_seconds=0) == []
