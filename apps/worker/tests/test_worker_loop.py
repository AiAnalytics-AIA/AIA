"""The worker loop, in process: every way an attempt can end.

Each test drives a real :class:`~aia_worker.worker.Worker` against a real database
(PostgreSQL in CI, a file-backed SQLite otherwise) with the scripted executor, and
asserts on the persisted state -- never on the worker's own report alone. The
multi-process suite (``test_worker_processes.py``) covers contention and
termination; this file covers the outcome table in ``aia_worker.worker``.

Timing waits are generous on purpose (``CLAUDE.md`` §7): they bound how long a
test may take on a slow CI runner, not how fast the worker is expected to be.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.scope import ClientStatus
from aia_core.domain.workflow import (
    AttemptStatus,
    FailureClass,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.tables import (
    BudgetReservationRow,
    ClientRow,
    StepAttemptRow,
    WorkflowEventRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository, WorkQueue
from aia_worker.context import in_transaction
from aia_worker.worker import AttemptResult, Worker
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

MakeWorker = Callable[..., Worker]
WAIT = 20.0


def _wait_for(condition: Callable[[], bool], *, timeout: float = WAIT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(f"condition not met within {timeout}s")


def _in_thread(worker: Worker) -> tuple[threading.Thread, list[AttemptResult | None]]:
    """Run one ``run_once`` on a thread; the result lands in the returned list."""
    results: list[AttemptResult | None] = []
    thread = threading.Thread(target=lambda: results.append(worker.run_once()), daemon=True)
    thread.start()
    return thread, results


def _ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _step(study: Any, run_id: str) -> dict[str, Any]:
    step: dict[str, Any] = study.run(run_id)["steps"][0]
    return step


def _attempt_statuses(sessions: sessionmaker[Session], run_step: dict[str, Any]) -> list[str]:
    with sessions() as session:
        rows = session.scalars(
            select(StepAttemptRow)
            .where(StepAttemptRow.step_id == run_step["step_id"])
            .order_by(StepAttemptRow.attempt_number)
        ).all()
        return [r.status for r in rows]


# --------------------------------------------------------------------------- #
# Completion
# --------------------------------------------------------------------------- #


def test_an_idle_worker_finds_nothing(study: Any, make_worker: MakeWorker) -> None:
    assert make_worker().run_once() is None


def test_a_step_is_executed_and_completed(
    study: Any, make_worker: MakeWorker, tmp_path: Path
) -> None:
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run({"ledger": str(ledger)})

    result = make_worker().run_once()

    assert result is not None
    assert result.ending == "completed"
    step = _step(study, run_id)
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED
    assert [e["event"] for e in _ledger(ledger)] == ["start", "end"]


def test_a_paid_call_is_charged_its_real_cost_once(study: Any, make_worker: MakeWorker) -> None:
    run_id = study.create_run({"paid": {"reserve": 2.0, "cost": 1.5}})

    assert make_worker().run_once() is not None

    assert _step(study, run_id)["status"] is StepRunStatus.SUCCEEDED
    budget = study.budget()
    assert budget["spent_usd"] == pytest.approx(1.5)
    assert budget["reserved_usd"] == pytest.approx(0.0)
    assert budget["uncertain_usd"] == pytest.approx(0.0)


def test_a_retried_completion_after_a_lost_ack_charges_once(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    """The commit landed, the acknowledgement did not, and the worker retried.

    Simulated by committing inside the unit of work and then raising a transient
    error, so ``in_transaction`` retries a completion that already happened.
    """
    study.create_run({})
    with sessions() as session:
        work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
        assert work is not None
        from aia_core.application.scope import ScopeResolver

        scope = ScopeResolver(session).execution_context(attempt_id=work.attempt_id, worker_id="w")
        session.commit()

    calls = 0

    def complete_then_lose_the_ack(repo: WorkflowRepository) -> StepRunStatus:
        nonlocal calls
        calls += 1
        status = repo.complete_attempt(work.attempt_id, worker_id="w", actual_cost_usd=2.0)
        if calls == 1:
            repo._session.commit()
            raise OperationalError("COMMIT", {}, Exception("connection reset"))
        return status

    status = in_transaction(sessions, scope, complete_then_lose_the_ack, backoff_seconds=0)

    assert calls == 2
    assert status is StepRunStatus.SUCCEEDED
    assert study.budget()["spent_usd"] == pytest.approx(2.0), "charged once"
    with sessions() as session:
        succeeded = session.scalars(
            select(WorkflowEventRow).where(WorkflowEventRow.event_type == "STEP_SUCCEEDED")
        ).all()
        assert len(succeeded) == 1


# --------------------------------------------------------------------------- #
# Failure
# --------------------------------------------------------------------------- #


def test_a_retryable_failure_is_retried_as_a_new_attempt(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    run_id = study.create_run({"fail": FailureClass.TRANSPORT.value, "fail_until_attempt": 2})
    worker = make_worker()

    first = worker.run_once()
    assert first is not None
    assert first.ending == "failed"
    assert first.step_status is StepRunStatus.RUNNABLE

    second = worker.run_once()
    assert second is not None
    assert second.ending == "completed"
    step = _step(study, run_id)
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert _attempt_statuses(sessions, step) == [
        AttemptStatus.FAILED.value,
        AttemptStatus.SUCCEEDED.value,
    ]


def test_a_non_retryable_failure_stops_the_step(study: Any, make_worker: MakeWorker) -> None:
    run_id = study.create_run({"fail": FailureClass.AUTHENTICATION.value})
    worker = make_worker()

    result = worker.run_once()

    assert result is not None
    assert result.step_status is StepRunStatus.FAILED
    assert study.run(run_id)["status"] is WorkflowRunStatus.FAILED
    assert worker.run_once() is None, "never retried"


def test_an_unclassified_exception_is_permanent_and_its_message_redacted(
    study: Any, make_worker: MakeWorker
) -> None:
    """Unknown is not retried against a paid provider, and a key in the text is scrubbed."""
    run_id = study.create_run({"raise": "boom with sk-ant-api03-abcdefghijklmnopqrstuvwxyz"})

    result = make_worker().run_once()

    assert result is not None
    assert result.step_status is StepRunStatus.FAILED
    attempt = _step(study, run_id)["attempts"][0]
    assert attempt["failure_class"] is FailureClass.UNKNOWN
    assert attempt["error"]["type"] == "RuntimeError"
    assert "sk-ant" not in attempt["error"]["message"]
    assert "[redacted]" in attempt["error"]["message"]


def test_a_possibly_billed_failure_is_recovery_required_and_never_retried(
    study: Any, make_worker: MakeWorker
) -> None:
    """A timeout after sending: the call may have been billed. A person decides."""
    run_id = study.create_run({"paid": {"reserve": 3.0, "crash_in_flight": True}})
    worker = make_worker()

    result = worker.run_once()

    assert result is not None
    assert result.step_status is StepRunStatus.RECOVERY_REQUIRED
    assert study.run(run_id)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED
    budget = study.budget()
    assert budget["uncertain_usd"] == pytest.approx(3.0)
    assert budget["spent_usd"] == pytest.approx(3.0), "shown as spent, not available"
    assert worker.run_once() is None, "no automatic retry of a possibly-billed call"


def test_running_out_of_budget_parks_awaiting_budget(study: Any, make_worker: MakeWorker) -> None:
    run_id = study.create_run({"paid": {"reserve": 500.0, "cost": 1.0}})

    result = make_worker().run_once()

    assert result is not None
    assert result.step_status is StepRunStatus.AWAITING_BUDGET
    assert study.run(run_id)["status"] is WorkflowRunStatus.AWAITING_BUDGET
    assert _step(study, run_id)["attempts_consumed"] == 0, "not a failure of the work"


def test_a_capacity_park_is_resumed_by_maintenance_and_then_completes(
    study: Any, make_worker: MakeWorker
) -> None:
    run_id = study.create_run(
        {"fail": FailureClass.PROVIDER_CAPACITY.value, "fail_until_attempt": 2}
    )
    worker = make_worker(capacity_backoff_seconds=0)

    parked = worker.run_once()
    assert parked is not None
    assert parked.step_status is StepRunStatus.WAITING_CAPACITY
    assert worker.run_once() is None, "a park is not claimable"

    assert worker.maintain() == (0, 1)
    done = worker.run_once()

    assert done is not None
    assert done.ending == "completed"
    assert _step(study, run_id)["attempts_consumed"] == 1, "the park consumed nothing"


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #


def test_an_approval_parks_the_step_and_the_decision_reaches_the_next_attempt(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    run_id = study.create_run({"approval": "Proceed with fieldwork?"})
    worker = make_worker()

    gated = worker.run_once()
    assert gated is not None
    assert gated.ending == "gated"
    assert study.run(run_id)["status"] is WorkflowRunStatus.AWAITING_GATE

    with sessions() as session:
        reviewer = WorkflowRepository(session, study.scope_for(session, study.reviewer_id))
        [gate] = reviewer.pending_gates(run_id)
        assert gate["question"] == "Proceed with fieldwork?"
        assert gate["produced_by_user_id"] == study.lead_id, "the person who started the run"
        reviewer.decide_gate(gate["gate_id"], option="approve")
        session.commit()

    done = worker.run_once()

    assert done is not None
    assert done.ending == "completed"
    assert _step(study, run_id)["attempts"][-1]["status"] is AttemptStatus.SUCCEEDED
    with sessions() as session:
        output = WorkflowRepository(session, study.lead_scope(session)).get_run(run_id)
    assert output["status"] is WorkflowRunStatus.COMPLETED


# --------------------------------------------------------------------------- #
# Cancellation, lease loss, shutdown
# --------------------------------------------------------------------------- #


def test_cancellation_is_observed_at_a_checkpoint_and_returns_the_hold(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    run_id = study.create_run({"hold": 5.0, "work_seconds": 30})
    worker = make_worker(heartbeat_seconds=0.05)

    thread, results = _in_thread(worker)
    _wait_for(lambda: _step(study, run_id)["status"] is StepRunStatus.RUNNING)
    _wait_for(lambda: study.budget()["reserved_usd"] > 0)
    study.cancel(run_id)
    thread.join(WAIT)

    assert results and results[0] is not None
    assert results[0].ending == "abandoned"
    assert study.run(run_id)["status"] is WorkflowRunStatus.CANCELLED
    assert _step(study, run_id)["attempts"][0]["status"] is AttemptStatus.ABANDONED
    assert study.budget()["reserved_usd"] == pytest.approx(0.0), "the hold came back"
    assert study.budget()["available_usd"] == pytest.approx(100.0)


def test_a_worker_that_loses_its_lease_stops_and_writes_nothing(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    """Another worker's reconciler recovers the attempt mid-execution.

    The first worker's next heartbeat is refused, its checkpoint raises, and it
    records nothing. The successor runs the step and records the one outcome.
    """
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run({"ledger": str(ledger), "work_seconds": 1.0})
    stalled = make_worker("stalled", heartbeat_seconds=0.05)

    thread, results = _in_thread(stalled)
    _wait_for(lambda: len(_ledger(ledger)) == 1)
    with sessions() as session:
        session.execute(
            update(StepAttemptRow).values(lease_until=StepAttemptRow.started_at)
        )  # the lease lapses
        assert len(WorkQueue(session).recover_expired_attempts()) == 1
        session.commit()
    thread.join(WAIT)

    assert results and results[0] is not None
    assert results[0].ending == "lease_lost"

    successor = make_worker("successor").run_once()
    assert successor is not None
    assert successor.ending == "completed"

    step = _step(study, run_id)
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert [a["status"] for a in step["attempts"]] == [
        AttemptStatus.EXPIRED,
        AttemptStatus.SUCCEEDED,
    ]
    events = _ledger(ledger)
    assert [e["event"] for e in events].count("end") == 1, "one completed execution"


def test_graceful_shutdown_releases_the_attempt_for_another_worker(
    study: Any, make_worker: MakeWorker
) -> None:
    run_id = study.create_run({"hold": 2.0, "work_seconds": 30})
    leaving = make_worker("leaving")

    thread, results = _in_thread(leaving)
    _wait_for(lambda: study.budget()["reserved_usd"] > 0)
    leaving.request_stop()
    thread.join(WAIT)

    assert results and results[0] is not None
    assert results[0].ending == "released"
    step = _step(study, run_id)
    assert step["status"] is StepRunStatus.RUNNABLE
    assert step["attempts_consumed"] == 0, "a shutdown is not a failed attempt"
    assert study.budget()["reserved_usd"] == pytest.approx(0.0)

    taker = make_worker("taker")
    thread, results = _in_thread(taker)
    _wait_for(lambda: _step(study, run_id)["status"] is StepRunStatus.RUNNING)
    taker.request_stop()
    thread.join(WAIT)
    assert [a["worker_id"] for a in _step(study, run_id)["attempts"]] == ["leaving", "taker"]


def test_a_stopping_worker_claims_nothing(study: Any, make_worker: MakeWorker) -> None:
    study.create_run({})
    worker = make_worker()
    worker.request_stop()
    assert worker.run_once() is None
    with study.sessions() as session:
        assert session.scalars(select(StepAttemptRow)).all() == []


def test_run_forever_drains_work_and_stops_on_request(
    study: Any, make_worker: MakeWorker, tmp_path: Path
) -> None:
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run(*({"ledger": str(ledger)} for _ in range(3)))
    worker = make_worker()

    thread = threading.Thread(target=worker.run_forever, daemon=True)
    thread.start()
    _wait_for(lambda: study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED)
    worker.request_stop()
    thread.join(WAIT)

    assert not thread.is_alive()
    assert [e["event"] for e in _ledger(ledger)].count("end") == 3


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #


def test_work_for_an_archived_client_is_refused_and_fails_closed(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session], tmp_path: Path
) -> None:
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run({"ledger": str(ledger)})
    with sessions() as session:
        client = session.get(ClientRow, study.client_id)
        assert client is not None
        client.status = ClientStatus.ARCHIVED.value
        session.commit()

    result = make_worker().run_once()

    assert result is not None
    assert result.ending == "refused"
    assert _ledger(ledger) == [], "the executor never ran"
    with sessions() as session:
        client = session.get(ClientRow, study.client_id)
        assert client is not None
        client.status = ClientStatus.ACTIVE.value
        session.commit()
    step = _step(study, run_id)
    assert step["status"] is StepRunStatus.FAILED
    assert step["attempts"][0]["error"] == {"reason": "client_archived"}


def test_a_worker_claims_only_the_kinds_it_has_executors_for(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    with sessions() as session:
        WorkflowRepository(session, study.lead_scope(session)).create_run(
            project_id=study.project_id,
            project_revision=1,
            workflow_type="other",
            steps=[StepDefinition(node_key="n", kind="not-mine")],
            idempotency_key="not-mine",
        )
        session.commit()

    assert make_worker().run_once() is None


def test_reservations_never_outlive_their_attempt(
    study: Any, make_worker: MakeWorker, sessions: sessionmaker[Session]
) -> None:
    """Across every ending above, nothing is left RESERVED once the attempt ends."""
    study.create_run(
        {"paid": {"reserve": 1.0, "cost": 0.5}},
        {"hold": 1.0, "fail": FailureClass.AUTHENTICATION.value},
        {"hold": 1.0},
        key="many",
    )
    worker = make_worker()
    while worker.run_once() is not None:
        pass

    with sessions() as session:
        open_holds = session.scalars(
            select(BudgetReservationRow).where(
                BudgetReservationRow.status == ReservationStatus.RESERVED.value
            )
        ).all()
    assert open_holds == []
    assert study.budget()["spent_usd"] == pytest.approx(0.5)
