"""Real worker processes against real PostgreSQL: contention, termination, shutdown.

Every test here starts ``python -m aia_worker`` as separate OS processes and then
does to them what production will: runs several at once over one queue, kills one
with ``SIGKILL`` mid-step and mid-paid-call, stops one with ``SIGTERM``, sends a
second signal. Assertions are on the database and on an append-only ledger the
executor writes from inside each process -- never on what a worker says it did.

**PostgreSQL only.** SQLite is single-writer and has no ``SKIP LOCKED``; worker
processes contending over it would prove nothing (``AGENTS.md`` § SQLAlchemy). The
module skips without PostgreSQL, and fails instead when ``AIA_REQUIRE_POSTGRES=1``
-- which CI sets, so a missing database cannot masquerade as a pass.

Timings: a 3-second lease, heartbeats every 0.5 s, maintenance every 0.5 s. The
waits are sized far above those (``CLAUDE.md`` §7): they bound a slow runner, they
do not measure the worker.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.workflow import (
    AttemptStatus,
    ReservationStatus,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.tables import BudgetReservationRow, StepAttemptRow
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.postgres

WAIT = 60.0
LEASE_SECONDS = 3


@pytest.fixture(autouse=True)
def _require_postgres(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        message = "worker process tests need PostgreSQL; set DATABASE_URL to a postgresql:// URL"
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)


class WorkerProcess:
    """One ``python -m aia_worker`` process, logging to a file."""

    def __init__(self, name: str, *, database_url: str, log_dir: Path) -> None:
        self.name = name
        self.log_path = log_dir / f"{name}.log"
        env = {
            **os.environ,
            "DATABASE_URL": database_url,
            "AIA_WORKER_EXECUTORS": "aia_worker.testing:build_registry",
            "AIA_WORKER_ID": name,
            "AIA_WORKER_LEASE_SECONDS": str(LEASE_SECONDS),
            "AIA_WORKER_HEARTBEAT_SECONDS": "0.5",
            "AIA_WORKER_POLL_SECONDS": "0.1",
            "AIA_WORKER_MAINTENANCE_SECONDS": "0.5",
            "AIA_WORKER_CAPACITY_BACKOFF_SECONDS": "0",
            "AIA_LOG_LEVEL": "INFO",
        }
        self._log = self.log_path.open("wb")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "aia_worker"],
            env=env,
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )

    def signal(self, signum: int) -> None:
        self.process.send_signal(signum)

    def wait(self, timeout: float = WAIT) -> int:
        return self.process.wait(timeout)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(10)
        self._log.close()

    def log(self) -> str:
        return self.log_path.read_text(errors="replace")


@pytest.fixture
def spawn(database_url: str, tmp_path: Path) -> Iterator[Callable[[str], WorkerProcess]]:
    started: list[WorkerProcess] = []

    def start(name: str) -> WorkerProcess:
        worker = WorkerProcess(name, database_url=database_url, log_dir=tmp_path)
        started.append(worker)
        return worker

    try:
        yield start
    finally:
        for worker in started:
            worker.close()


def _wait_for(condition: Callable[[], bool], *, what: str, timeout: float = WAIT) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}")


def _ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _attempts(sessions: sessionmaker[Session]) -> list[StepAttemptRow]:
    with sessions() as session:
        return list(
            session.scalars(
                select(StepAttemptRow).order_by(
                    StepAttemptRow.step_id, StepAttemptRow.attempt_number
                )
            ).all()
        )


def _open_reservations(sessions: sessionmaker[Session]) -> int:
    with sessions() as session:
        return len(
            session.scalars(
                select(BudgetReservationRow).where(
                    BudgetReservationRow.status == ReservationStatus.RESERVED.value
                )
            ).all()
        )


def _stop(*workers: WorkerProcess) -> None:
    for worker in workers:
        worker.signal(signal.SIGTERM)
    for worker in workers:
        assert worker.wait() == 0, worker.log()


# --------------------------------------------------------------------------- #
# Contention
# --------------------------------------------------------------------------- #


def test_three_processes_share_one_queue_without_double_execution_or_charge(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Twelve paid steps, three workers. Each step runs once and is charged once."""
    ledger = tmp_path / "ledger.jsonl"
    steps = 12
    run_id = study.create_run(
        *(
            {"ledger": str(ledger), "work_seconds": 0.2, "paid": {"reserve": 1.0, "cost": 0.25}}
            for _ in range(steps)
        )
    )
    workers = [spawn(f"proc-{i}") for i in range(3)]

    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED,
        what="the run to complete",
    )
    _stop(*workers)

    events = _ledger(ledger)
    starts = Counter(e["step_id"] for e in events if e["event"] == "start")
    ends = Counter(e["step_id"] for e in events if e["event"] == "end")
    assert len(starts) == steps
    assert set(starts.values()) == {1}, f"a step was executed twice: {starts}"
    assert set(ends.values()) == {1}
    assert len({e["pid"] for e in events}) >= 2, "the work was actually shared"

    attempts = _attempts(sessions)
    assert len(attempts) == steps, "one attempt per step -- no claim was duplicated"
    assert {a.status for a in attempts} == {AttemptStatus.SUCCEEDED.value}
    assert len({a.worker_id for a in attempts}) >= 2

    budget = study.budget()
    assert budget["spent_usd"] == pytest.approx(steps * 0.25), "each call charged once"
    assert budget["reserved_usd"] == pytest.approx(0.0)
    assert _open_reservations(sessions) == 0


def test_children_of_a_deferred_step_run_across_processes_once_each(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A join hands out twelve paid children; three processes share them; it then completes."""
    ledger = tmp_path / "ledger.jsonl"
    children = 12
    run_id = study.create_run(
        {
            "ledger": str(ledger),
            "defer": [
                {"ledger": str(ledger), "work_seconds": 0.2, "paid": {"reserve": 1.0, "cost": 0.25}}
                for _ in range(children)
            ],
        }
    )
    workers = [spawn(f"proc-{i}") for i in range(3)]

    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED,
        what="the join to complete after its children",
    )
    _stop(*workers)

    run = study.run(run_id)
    join = next(s for s in run["steps"] if s["node_key"] == "s0")
    events = _ledger(ledger)
    child_starts = Counter(
        e["step_id"] for e in events if e["event"] == "start" and e["step_id"] != join["step_id"]
    )
    assert len(child_starts) == children and set(child_starts.values()) == {1}
    assert len({e["pid"] for e in events}) >= 2, "the children were actually shared"
    assert [a["status"] for a in join["attempts"]] == [
        AttemptStatus.DEFERRED,
        AttemptStatus.SUCCEEDED,
    ]
    assert study.budget()["spent_usd"] == pytest.approx(children * 0.25)
    assert _open_reservations(sessions) == 0


# --------------------------------------------------------------------------- #
# Termination
# --------------------------------------------------------------------------- #


def test_a_killed_worker_s_step_is_recovered_and_finished_by_another(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """``SIGKILL`` mid-step: no cleanup runs at all. The lease is the only record."""
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run({"ledger": str(ledger), "work_seconds": 120, "slow_attempts": 1})
    doomed = spawn("doomed")
    _wait_for(lambda: len(_ledger(ledger)) == 1, what="the first execution to start")

    doomed.signal(signal.SIGKILL)
    doomed.wait()
    survivor = spawn("survivor")
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED,
        what="the survivor to finish the step",
    )
    _stop(survivor)

    attempts = _attempts(sessions)
    assert [(a.worker_id, a.status) for a in attempts] == [
        ("doomed", AttemptStatus.EXPIRED.value),
        ("survivor", AttemptStatus.SUCCEEDED.value),
    ]
    assert [e["event"] for e in _ledger(ledger)] == ["start", "start", "end"]


def test_a_worker_killed_during_a_paid_call_is_never_retried_or_double_charged(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """The fundamental invariant, end to end, across a real process death.

    The call was dispatched and the worker died before its outcome was known. It
    may have been billed. It must not be retried automatically, and the $4 must
    appear as spent exactly once -- even though a second worker's reconciler is
    the one that finds it.
    """
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run(
        {"ledger": str(ledger), "paid": {"reserve": 4.0, "cost": 1.0, "hang_seconds": 120}}
    )
    doomed = spawn("doomed")

    def dispatched() -> bool:
        return any(a.paid_call_dispatched for a in _attempts(sessions))

    _wait_for(dispatched, what="the paid call to be dispatched")
    doomed.signal(signal.SIGKILL)
    doomed.wait()
    reconciler = spawn("reconciler")
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED,
        what="recovery to require a person",
    )
    # Give the reconciler several more sweeps in which it could misbehave.
    time.sleep(2.0)
    _stop(reconciler)

    assert [(a.worker_id, a.status) for a in _attempts(sessions)] == [
        ("doomed", AttemptStatus.EXPIRED.value)
    ], "no second attempt: a possibly-billed call is never retried automatically"
    assert [e["event"] for e in _ledger(ledger)] == ["start"]
    budget = study.budget()
    assert budget["spent_usd"] == pytest.approx(4.0), "charged once, at the reserved ceiling"
    assert budget["uncertain_usd"] == pytest.approx(4.0)
    assert study.run(run_id)["steps"][0]["status"] is StepRunStatus.RECOVERY_REQUIRED


def test_a_worker_killed_with_one_of_two_calls_answered_is_never_retried(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Two calls in flight at once, one settled, then ``SIGKILL``.

    The answered call is charged its real $1; the other may have been billed, so
    the reconciler must not retry the step and must charge its $3 at the ceiling.
    Before, the first settle closed the attempt's single outcome flag and the
    reconciler retried the step with the second hold released.
    """
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run(
        {
            "ledger": str(ledger),
            "paid_overlapping": {"reserve": [1.0, 3.0], "cost": 1.0, "hang_seconds": 120},
        }
    )
    doomed = spawn("doomed")

    def one_answered() -> bool:
        with sessions() as session:
            statuses = session.scalars(select(BudgetReservationRow.status)).all()
        return ReservationStatus.SETTLED.value in statuses

    _wait_for(one_answered, what="the first of two calls to be settled")
    doomed.signal(signal.SIGKILL)
    doomed.wait()
    reconciler = spawn("reconciler")
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED,
        what="recovery to require a person",
    )
    time.sleep(2.0)
    _stop(reconciler)

    assert [(a.worker_id, a.status) for a in _attempts(sessions)] == [
        ("doomed", AttemptStatus.EXPIRED.value)
    ], "no second attempt while a call may have been billed"
    assert [e["event"] for e in _ledger(ledger)] == ["start"]
    with sessions() as session:
        holds = session.scalars(
            select(BudgetReservationRow).order_by(BudgetReservationRow.amount_usd)
        ).all()
        assert [(h.status, h.settled_amount_usd) for h in holds] == [
            (ReservationStatus.SETTLED.value, 1.0),
            (ReservationStatus.SETTLED_UNCERTAIN.value, 3.0),
        ]
    budget = study.budget()
    assert budget["spent_usd"] == pytest.approx(4.0)
    assert budget["uncertain_usd"] == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# Shutdown
# --------------------------------------------------------------------------- #


def test_sigterm_releases_the_step_at_once_and_exits_cleanly(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A rolling deploy: the step goes back without waiting out a lease, uncounted."""
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run(
        {"ledger": str(ledger), "hold": 2.0, "work_seconds": 120, "slow_attempts": 1}
    )
    leaving = spawn("leaving")
    _wait_for(lambda: len(_ledger(ledger)) == 1, what="execution to start")

    started = time.monotonic()
    leaving.signal(signal.SIGTERM)
    assert leaving.wait() == 0, leaving.log()
    assert time.monotonic() - started < LEASE_SECONDS * 3, "released, not left to lapse"

    step = study.run(run_id)["steps"][0]
    assert step["status"] is StepRunStatus.RUNNABLE
    assert step["attempts_consumed"] == 0
    assert _open_reservations(sessions) == 0

    arriving = spawn("arriving")
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.COMPLETED,
        what="the next worker to finish it",
    )
    _stop(arriving)
    assert [(a.worker_id, a.status) for a in _attempts(sessions)] == [
        ("leaving", AttemptStatus.ABANDONED.value),
        ("arriving", AttemptStatus.SUCCEEDED.value),
    ]


def test_a_second_signal_exits_at_once_and_the_lease_is_recovered(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Stuck inside a paid call with no checkpoint: the first SIGTERM cannot land.

    The second forces the exit. Nothing is written on the way out; the lease
    lapses, and another worker's reconciler applies the recovery table -- here,
    ``RECOVERY_REQUIRED``, because the call is in flight.
    """
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run(
        {"ledger": str(ledger), "paid": {"reserve": 1.5, "hang_seconds": 120}}
    )
    stuck = spawn("stuck")
    _wait_for(
        lambda: any(a.paid_call_dispatched for a in _attempts(sessions)),
        what="the paid call to be dispatched",
    )

    stuck.signal(signal.SIGTERM)
    time.sleep(1.0)
    assert stuck.process.poll() is None, "the first signal waits for a checkpoint"
    stuck.signal(signal.SIGTERM)
    assert stuck.wait() == 130, stuck.log()

    reconciler = spawn("reconciler")
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED,
        what="the lapsed lease to be recovered",
    )
    _stop(reconciler)
    assert study.budget()["spent_usd"] == pytest.approx(1.5)


def test_cancellation_reaches_a_worker_in_another_process(
    study: Any,
    spawn: Callable[[str], WorkerProcess],
    sessions: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger.jsonl"
    run_id = study.create_run({"ledger": str(ledger), "hold": 3.0, "work_seconds": 120})
    worker = spawn("busy")
    _wait_for(lambda: len(_ledger(ledger)) == 1, what="execution to start")

    study.cancel(run_id)
    _wait_for(
        lambda: study.run(run_id)["status"] is WorkflowRunStatus.CANCELLED,
        what="the worker to observe the cancellation",
    )
    _stop(worker)

    assert [a.status for a in _attempts(sessions)] == [AttemptStatus.ABANDONED.value]
    assert study.budget()["reserved_usd"] == pytest.approx(0.0)
    assert study.budget()["spent_usd"] == pytest.approx(0.0)
