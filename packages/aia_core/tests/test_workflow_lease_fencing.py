"""The lease is the fence: only the worker holding an attempt may write about it.

These are the engine guarantees a worker process leans on, each written against
the defect that motivated it (``.planning/plans/done/worker-process.md`` W1-W3):

* a stale worker -- one whose lease was recovered -- cannot complete, fail or
  abandon the attempt, so a step never carries two outcomes;
* completion is idempotent for its owner, so retrying a commit whose
  acknowledgement was lost charges nothing twice.

The heartbeat resurrection race (W1) needs two real connections and lives in
``test_workflow_concurrency.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.workflow import (
    AttemptStatus,
    FailureClass,
    StepDefinition,
    StepRunStatus,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import StepAttemptRow, StudyRow, WorkflowEventRow
from aia_core.infrastructure.workflow_repository import LeaseLost, WorkflowRepository


@pytest.fixture
def engine_repo(session: Session, scoped: Any) -> WorkflowRepository:
    """Workflow repository as a LEAD on the primary study."""
    return WorkflowRepository(session, scoped.scope(user="lead", study="primary"))


@pytest.fixture
def run(engine_repo: WorkflowRepository, session: Session, scoped: Any) -> str:
    """A one-step run, so every claim is for the same step."""
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Fencing host", content={"goal": "g"}
    )
    return engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key="fencing-run",
    )


def _expire(session: Session, attempt_id: str) -> None:
    """Force an attempt's lease into the past, simulating a stalled worker."""
    attempt = session.get(StepAttemptRow, attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()


def _step_status(repo: WorkflowRepository, run_id: str) -> StepRunStatus:
    """The single step's status."""
    status: StepRunStatus = repo.get_run(run_id)["steps"][0]["status"]
    return status


def _recovered_and_reclaimed(repo: WorkflowRepository, session: Session) -> tuple[Any, Any]:
    """Claim as worker-1, let the lease lapse, recover, and re-claim as worker-2."""
    stale = repo.claim_next(worker_id="worker-1")
    assert stale is not None
    _expire(session, stale.attempt_id)
    assert len(repo.recover_expired_attempts()) == 1
    fresh = repo.claim_next(worker_id="worker-2")
    assert fresh is not None
    assert fresh.step_id == stale.step_id
    return stale, fresh


def test_a_claim_carries_its_owner_and_scope(engine_repo: WorkflowRepository, run: str) -> None:
    """The claim names the worker and the study, so fenced calls can name them back."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    assert claimed.worker_id == "worker-1"
    assert claimed.study_id == engine_repo.scope.study_id
    assert claimed.client_id == engine_repo.scope.client_id
    assert claimed.organization_id == engine_repo.scope.organization_id


def test_a_stale_worker_cannot_complete_a_step_it_no_longer_owns(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """**W2.** The worker whose lease was recovered must not record an outcome.

    Before the fence, the stale worker's completion marked the step SUCCEEDED
    while worker-2 was still running attempt 2 -- two executions, and whichever
    finished last decided what the step's output was.
    """
    stale, fresh = _recovered_and_reclaimed(engine_repo, session)

    with pytest.raises(LeaseLost) as refused:
        engine_repo.complete_attempt(stale.attempt_id, worker_id="worker-1", output={"x": 1})

    assert refused.value.status == AttemptStatus.EXPIRED.value
    assert _step_status(engine_repo, run) is StepRunStatus.RUNNING, "worker-2 still owns it"
    history = engine_repo.attempt_history(stale.step_id)
    assert [a["status"] for a in history] == [AttemptStatus.EXPIRED, AttemptStatus.CLAIMED]

    # The rightful owner still can.
    engine_repo.complete_attempt(fresh.attempt_id, worker_id="worker-2", output={"x": 2})
    assert _step_status(engine_repo, run) is StepRunStatus.SUCCEEDED


def test_a_stale_worker_cannot_fail_or_abandon_a_step_it_no_longer_owns(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """The same fence on the other two outcomes. A guard on one path only is A8."""
    stale, _ = _recovered_and_reclaimed(engine_repo, session)

    with pytest.raises(LeaseLost):
        engine_repo.fail_attempt(
            stale.attempt_id, worker_id="worker-1", failure=FailureClass.AUTHENTICATION
        )
    with pytest.raises(LeaseLost):
        engine_repo.abandon_attempt(stale.attempt_id, worker_id="worker-1")

    assert _step_status(engine_repo, run) is StepRunStatus.RUNNING


def test_a_non_owner_cannot_write_about_a_live_attempt(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """Holding the attempt id is not holding the lease."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    with pytest.raises(LeaseLost) as refused:
        engine_repo.complete_attempt(claimed.attempt_id, worker_id="impostor")
    assert refused.value.owner == "worker-1"
    with pytest.raises(LeaseLost):
        engine_repo.fail_attempt(
            claimed.attempt_id, worker_id="impostor", failure=FailureClass.TRANSPORT
        )

    assert _step_status(engine_repo, run) is StepRunStatus.RUNNING


def test_an_owner_whose_deadline_passed_but_was_not_recovered_may_still_finish(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """The deadline triggers recovery; it is not the fence.

    Until a reconciler recovers the attempt nobody else can claim the step, so
    discarding the owner's finished work would waste it for no safety gain.
    """
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    _expire(session, claimed.attempt_id)

    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1")

    assert _step_status(engine_repo, run) is StepRunStatus.SUCCEEDED
    assert engine_repo.recover_expired_attempts() == [], "nothing left to recover"


def test_completion_is_idempotent_for_its_owner(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """**W3.** A retried completion must not charge or record anything twice.

    A worker whose commit acknowledgement was lost cannot tell whether the commit
    landed, so it retries. Before this, the retry charged ``actual_cost_usd`` to
    the study a second time.
    """
    study = session.get(StudyRow, engine_repo.scope.study_id)
    assert study is not None
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()

    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    first = engine_repo.complete_attempt(
        claimed.attempt_id, worker_id="worker-1", actual_cost_usd=4.0, output={"n": 1}
    )
    second = engine_repo.complete_attempt(
        claimed.attempt_id, worker_id="worker-1", actual_cost_usd=4.0, output={"n": 2}
    )

    assert first is second is StepRunStatus.SUCCEEDED
    assert engine_repo.budget_position()["spent_usd"] == pytest.approx(4.0)
    succeeded_events = session.scalars(
        select(WorkflowEventRow).where(
            WorkflowEventRow.run_id == run, WorkflowEventRow.event_type == "STEP_SUCCEEDED"
        )
    ).all()
    assert len(succeeded_events) == 1
    assert engine_repo.get_run(run)["steps"][0]["attempts"][0]["status"] is (
        AttemptStatus.SUCCEEDED
    )


def test_a_completed_attempt_cannot_then_be_failed(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """Idempotency covers the same outcome only; a different one is refused."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1")

    with pytest.raises(LeaseLost):
        engine_repo.fail_attempt(
            claimed.attempt_id, worker_id="worker-1", failure=FailureClass.TRANSPORT
        )
    assert _step_status(engine_repo, run) is StepRunStatus.SUCCEEDED


def test_another_workers_completion_is_not_mistaken_for_a_retry(
    engine_repo: WorkflowRepository, run: str
) -> None:
    """Idempotency is for the owner. A different worker completing is refused."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1")

    with pytest.raises(LeaseLost):
        engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-2")


def test_heartbeat_is_refused_once_the_attempt_was_recovered(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A recovered attempt stays recovered; the late heartbeat does not revive it."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None
    _expire(session, claimed.attempt_id)
    engine_repo.recover_expired_attempts()

    assert engine_repo.heartbeat(claimed.attempt_id, worker_id="worker-1") is False
    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    session.refresh(attempt)
    assert attempt.status == AttemptStatus.EXPIRED.value


def test_assert_lease_passes_for_the_owner_and_refuses_anyone_else(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    """The fence an executor's own transaction is built on."""
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    engine_repo.assert_lease(claimed.attempt_id, worker_id="worker-1")
    with pytest.raises(LeaseLost):
        engine_repo.assert_lease(claimed.attempt_id, worker_id="worker-2")

    _expire(session, claimed.attempt_id)
    engine_repo.recover_expired_attempts()
    with pytest.raises(LeaseLost):
        engine_repo.assert_lease(claimed.attempt_id, worker_id="worker-1")


def test_progress_is_recorded_for_the_owner_only(
    engine_repo: WorkflowRepository, run: str, session: Session
) -> None:
    claimed = engine_repo.claim_next(worker_id="worker-1")
    assert claimed is not None

    engine_repo.record_progress(
        claimed.attempt_id,
        worker_id="worker-1",
        message="respondent 240 of 300",
        payload={"n": 240},
    )
    with pytest.raises(LeaseLost):
        engine_repo.record_progress(claimed.attempt_id, worker_id="worker-2", message="forged")

    progress = [e for e in engine_repo.events(run) if e["event_type"] == "STEP_PROGRESS"]
    assert [(e["message"], e["payload"], e["attempt_id"]) for e in progress] == [
        ("respondent 240 of 300", {"n": 240}, claimed.attempt_id)
    ]
