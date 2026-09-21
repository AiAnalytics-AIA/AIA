"""Characterization of the legacy ``job_store.py``.

**Phase 3 step 1.** These tests describe what the prototype's durable job engine
actually does, before any of it is reimplemented. They are the specification the
new PostgreSQL engine must satisfy, and they are written against the *legacy*
implementation so they cannot be quietly bent to match a new one.

`job_store.py` is 295 dense lines that have absorbed real operational experience:
leases, heartbeats, idempotency keys, cooperative cancellation, cost reservations,
and a lease-recovery path that distinguishes work which is safe to retry from work
that may already have been billed. Casually redesigning that would lose money and
lose studies.

Every test runs against a temporary database. **The reference is never written
to** -- ``JobStore(path)`` is given a tmp path, because its default points at the
reference's own ``data/research_os.sqlite``.

Where a test documents behaviour we intend to change, it says so and names the
replacement. It still asserts the legacy behaviour, so the suite tells us if the
reference ever differs from what we believe.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.parity


@pytest.fixture
def legacy_job_store_module(legacy_root: Any) -> Iterator[Any]:
    """Import the legacy ``job_store`` module."""
    import sys

    sys.path.insert(0, str(legacy_root))
    try:
        import job_store

        yield job_store
    finally:
        sys.path.remove(str(legacy_root))


@pytest.fixture
def store(legacy_job_store_module: Any, tmp_path: Any) -> Any:
    """A legacy JobStore backed by a temporary database.

    The path is explicit because the default is the reference's own database, and
    the reference is read-only.
    """
    return legacy_job_store_module.JobStore(tmp_path / "research_os.sqlite")


@pytest.fixture
def workflow(store: Any) -> str:
    """A workflow with a project linkage, as the real engine creates them."""
    return store.create_workflow(
        project_id="PRJ-test", project_revision=1, workflow_type="persistent_research_project"
    )


def _job(store: Any, workflow_id: str, node_key: str = "compile", **kwargs: Any) -> str:
    """Add a job with sensible defaults."""
    return store.add_job(workflow_id, node_key, kwargs.pop("kind", "project_compile"), **kwargs)


# --------------------------------------------------------------------------- #
# The state machine
# --------------------------------------------------------------------------- #


def test_status_set_is_exactly_these_fourteen(legacy_job_store_module: Any) -> None:
    """The legacy status vocabulary, recorded verbatim.

    The brief's required conceptual states map onto these. Two legacy states have
    no direct counterpart in the brief and must be accounted for in the new
    design: DRAFT (created but not yet published to the graph) and
    RECOVERY_REQUIRED (a lease expired on work that may have had a side effect).

    The brief also names WAITING_BUDGET, which legacy does **not** have -- budget
    exhaustion currently routes through WAITING_USER via an approval. That is the
    one genuine addition in the new state machine.
    """
    assert {
        "DRAFT",
        "READY",
        "QUEUED",
        "RUNNING",
        "WAITING_DEPENDENCY",
        "WAITING_USER",
        "WAITING_CAPACITY",
        "WAITING_CREDITS",
        "PAUSED",
        "RETRYING",
        "RECOVERY_REQUIRED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    } == legacy_job_store_module.STATUSES


def test_allowed_transition_map_verbatim(legacy_job_store_module: Any) -> None:
    """The full transition table, so a port can be diffed against it."""
    assert {
        "DRAFT": {"READY", "CANCELLED"},
        "READY": {"QUEUED", "CANCELLED"},
        "QUEUED": {"RUNNING", "PAUSED", "CANCELLED"},
        "RUNNING": {
            "COMPLETED",
            "FAILED",
            "WAITING_USER",
            "WAITING_CAPACITY",
            "WAITING_CREDITS",
            "RETRYING",
            "PAUSED",
            "CANCELLED",
            "RECOVERY_REQUIRED",
        },
        "WAITING_DEPENDENCY": {"QUEUED", "CANCELLED"},
        "WAITING_USER": {"QUEUED", "CANCELLED"},
        "WAITING_CAPACITY": {"QUEUED", "PAUSED", "CANCELLED"},
        "WAITING_CREDITS": {"QUEUED", "PAUSED", "CANCELLED"},
        "PAUSED": {"QUEUED", "CANCELLED"},
        "RETRYING": {"QUEUED", "RUNNING", "FAILED", "CANCELLED"},
        "RECOVERY_REQUIRED": {"QUEUED", "CANCELLED", "FAILED"},
        "FAILED": {"RETRYING", "QUEUED", "CANCELLED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
    } == legacy_job_store_module.ALLOWED


def test_completed_and_cancelled_are_terminal(store: Any, workflow: str) -> None:
    """Nothing leaves COMPLETED or CANCELLED.

    This is what makes a finished stage trustworthy: it cannot be reopened in
    place, only superseded by a new revision.
    """
    done = _job(store, workflow, "done")
    store.transition(done, "QUEUED")
    store.transition(done, "RUNNING")
    store.transition(done, "COMPLETED")

    for target in ("QUEUED", "RUNNING", "FAILED", "RETRYING", "CANCELLED"):
        with pytest.raises(ValueError, match="Illegal job transition"):
            store.transition(done, target)


def test_failed_is_not_terminal(store: Any, workflow: str) -> None:
    """FAILED can be retried or requeued -- a failure is recoverable by an operator."""
    job = _job(store, workflow, "flaky")
    store.transition(job, "QUEUED")
    store.transition(job, "RUNNING")
    store.transition(job, "FAILED", error={"message": "provider error"})

    store.transition(job, "RETRYING")
    assert store.get_job(job)["status"] == "RETRYING"


def test_illegal_transition_raises_and_changes_nothing(store: Any, workflow: str) -> None:
    """An invalid transition is rejected rather than coerced."""
    job = _job(store, workflow, "strict")
    assert store.get_job(job)["status"] == "READY"

    with pytest.raises(ValueError, match="Illegal job transition"):
        store.transition(job, "COMPLETED")
    assert store.get_job(job)["status"] == "READY"


def test_force_bypasses_the_state_machine(store: Any, workflow: str) -> None:
    """``force=True`` is an operator escape hatch and skips validation.

    Worth carrying forward, and worth restricting: in the new engine this must be
    an audited administrative action rather than an ordinary keyword argument,
    because it can move a job out of a terminal state.
    """
    job = _job(store, workflow, "forced")
    store.transition(job, "COMPLETED", force=True)
    assert store.get_job(job)["status"] == "COMPLETED"

    store.transition(job, "QUEUED", force=True)
    assert store.get_job(job)["status"] == "QUEUED"


def test_transition_to_same_status_is_allowed(store: Any, workflow: str) -> None:
    """A no-op transition is permitted, which makes idempotent retries simpler."""
    job = _job(store, workflow, "same")
    store.transition(job, "READY")
    assert store.get_job(job)["status"] == "READY"


def test_unknown_status_is_rejected(store: Any, workflow: str) -> None:
    """A typo cannot invent a state."""
    job = _job(store, workflow, "typo")
    with pytest.raises(ValueError):
        store.transition(job, "ALMOST_DONE")


def test_terminal_transition_clears_the_lease(store: Any, workflow: str) -> None:
    """A finished job holds no lease, so recovery never picks it up."""
    job = _job(store, workflow, "leased")
    store.transition(job, "QUEUED")
    claimed = store.claim("worker-1")
    assert claimed["lease_owner"] == "worker-1"

    store.transition(job, "COMPLETED")
    row = store.get_job(job)
    assert row["lease_owner"] is None
    assert row["lease_until"] is None
    assert row["finished_at"] is not None


# --------------------------------------------------------------------------- #
# Idempotency and duplicate execution
# --------------------------------------------------------------------------- #


def test_duplicate_idempotency_key_returns_the_existing_job(store: Any, workflow: str) -> None:
    """The guarantee that makes at-least-once delivery survivable.

    A second attempt to create the same logical job returns the original id
    rather than a duplicate, so a retried enqueue cannot double-run a stage.
    """
    first = store.add_job(workflow, "compile", "project_compile", idempotency_key="wf:compile")
    second = store.add_job(
        workflow, "compile-again", "project_compile", idempotency_key="wf:compile"
    )
    assert second == first


def test_idempotency_key_defaults_to_workflow_and_node(store: Any, workflow: str) -> None:
    """Without an explicit key, ``{workflow_id}:{node_key}`` is used.

    So re-adding the same node to the same workflow deduplicates automatically.
    """
    first = _job(store, workflow, "design")
    second = _job(store, workflow, "design")
    assert second == first


def test_attempt_counter_increments_on_every_claim(store: Any, workflow: str) -> None:
    """Attempts are counted, and counted on claim rather than on failure.

    The new model makes each attempt an append-only StepAttempt row; this test
    records where the legacy counter moves so the port keeps the same semantics.
    """
    job = _job(store, workflow, "counted")
    store.transition(job, "QUEUED")

    store.claim("worker-1")
    assert store.get_job(job)["attempt"] == 1

    store.transition(job, "RETRYING")
    store.queue_ready_jobs()
    store.claim("worker-1")
    assert store.get_job(job)["attempt"] == 2


def test_attempt_history_is_only_a_counter(store: Any, workflow: str) -> None:
    """DEVIATION TO COME: legacy keeps a count, not a history.

    ``attempt`` is an integer and ``error_json`` holds only the most recent
    error, so a job that failed three different ways retains one. The brief
    requires ``StepAttempt`` rows as append-only history, which is a genuine
    improvement -- this test pins what is being replaced.

    The event log does retain per-attempt entries, which is the closest thing
    legacy has to attempt history.
    """
    job = _job(store, workflow, "history")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "FAILED", error={"message": "first failure"})
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "FAILED", error={"message": "second failure"})

    row = store.get_job(job)
    assert row["attempt"] == 2
    assert row["error"] == {"message": "second failure"}, "only the latest error survives"

    statuses = [e for e in store.updates() if e["job_id"] == job and e["event_type"] == "STATUS"]
    assert len(statuses) >= 4, "the event log is the only per-attempt record"


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #


def test_a_job_is_not_queued_until_dependencies_complete(store: Any, workflow: str) -> None:
    """Dependency gating, which is what makes the 24-node DAG sequential."""
    first = _job(store, workflow, "compile")
    second = _job(store, workflow, "research")
    store.add_dependency(second, first)

    store.queue_ready_jobs(workflow)
    assert store.get_job(first)["status"] == "QUEUED"
    assert store.get_job(second)["status"] == "READY", "blocked by its dependency"

    store.transition(first, "RUNNING")
    store.transition(first, "COMPLETED")
    assert store.get_job(second)["status"] == "QUEUED"


def test_completion_automatically_queues_dependants(store: Any, workflow: str) -> None:
    """``transition`` to COMPLETED calls ``queue_ready_jobs`` itself.

    So the DAG advances without an external scheduler tick.
    """
    first = _job(store, workflow, "a")
    second = _job(store, workflow, "b")
    third = _job(store, workflow, "c")
    store.add_dependency(second, first)
    store.add_dependency(third, second)
    store.activate_workflow_graph(workflow)

    store.transition(first, "RUNNING")
    store.transition(first, "COMPLETED")

    assert store.get_job(second)["status"] == "QUEUED"
    assert store.get_job(third)["status"] == "READY", "still blocked by b"


def test_claim_never_returns_a_job_with_incomplete_dependencies(store: Any, workflow: str) -> None:
    """The claim query re-checks dependencies.

    Belt and braces: even if a job were wrongly marked QUEUED, claim would not
    hand it to a worker.
    """
    first = _job(store, workflow, "a")
    second = _job(store, workflow, "b")
    store.add_dependency(second, first)

    with store.cx() as connection:
        connection.execute("UPDATE jobs SET status='QUEUED' WHERE job_id=?", (second,))

    claimed = store.claim("worker-1")
    assert claimed is not None
    assert claimed["job_id"] == first, "the blocked job must not be claimable"


def test_a_failed_dependency_blocks_dependants_indefinitely(store: Any, workflow: str) -> None:
    """A dependant waits for COMPLETED specifically, not merely for a terminal state.

    So a failed upstream stage stalls the pipeline rather than letting downstream
    work run on missing inputs. The new engine must keep this: the alternative is
    an analysis built on an absent evidence pack.
    """
    first = _job(store, workflow, "a")
    second = _job(store, workflow, "b")
    store.add_dependency(second, first)
    store.activate_workflow_graph(workflow)

    store.transition(first, "RUNNING")
    store.transition(first, "FAILED", error={"message": "no"})

    store.queue_ready_jobs()
    assert store.get_job(second)["status"] == "READY"
    assert store.claim("worker-1") is None


def test_workflow_dependencies_gate_an_entire_workflow(store: Any) -> None:
    """One workflow can wait for another, used for batch simulation runs."""
    upstream = store.create_workflow(project_id="PRJ-1", project_revision=1)
    downstream = store.create_workflow(project_id="PRJ-1", project_revision=1)

    upstream_job = _job(store, upstream, "a")
    downstream_job = _job(store, downstream, "b")
    store.add_workflow_dependency(downstream, upstream)

    store.activate_workflow_graph(downstream)
    assert store.get_job(downstream_job)["status"] != "QUEUED"

    store.transition(upstream_job, "QUEUED")
    store.transition(upstream_job, "RUNNING")
    store.transition(upstream_job, "COMPLETED")

    store.queue_ready_jobs()
    assert store.get_job(downstream_job)["status"] == "QUEUED"


# --------------------------------------------------------------------------- #
# Claiming, leases and heartbeats
# --------------------------------------------------------------------------- #


def test_claim_is_exclusive(store: Any, workflow: str) -> None:
    """Two workers cannot hold the same job.

    Legacy achieves this with ``BEGIN IMMEDIATE`` plus a conditional update that
    checks ``total_changes``. The new engine must achieve it with a
    ``SELECT … FOR UPDATE SKIP LOCKED`` or an equivalent conditional update -- the
    property is what matters, not the mechanism.
    """
    job = _job(store, workflow, "contested")
    store.transition(job, "QUEUED")

    first = store.claim("worker-1")
    second = store.claim("worker-2")

    assert first is not None and first["job_id"] == job
    assert second is None, "the job was already claimed"
    assert store.get_job(job)["lease_owner"] == "worker-1"


def test_claim_sets_a_lease_and_running_state(store: Any, workflow: str) -> None:
    """A claimed job is RUNNING, owned, and has a deadline."""
    job = _job(store, workflow, "leased")
    store.transition(job, "QUEUED")
    claimed = store.claim("worker-1")

    assert claimed["status"] == "RUNNING"
    assert claimed["lease_owner"] == "worker-1"
    assert claimed["lease_until"] is not None
    assert claimed["started_at"] is not None


def test_claim_honours_priority_then_creation_order(store: Any, workflow: str) -> None:
    """Higher priority first; ties broken by creation order, so nothing starves."""
    low = _job(store, workflow, "low", priority=10)
    high = _job(store, workflow, "high", priority=90)
    store.activate_workflow_graph(workflow)

    assert store.claim("worker-1")["job_id"] == high
    assert store.claim("worker-2")["job_id"] == low


def test_claim_respects_run_after(store: Any, workflow: str) -> None:
    """A scheduled job is not claimable before its time.

    This is the mechanism behind quota resume: a job parked on a quota limit gets
    a ``run_after`` of the reset time.
    """
    future = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 3600))
    job = _job(store, workflow, "later", run_after=future)
    store.transition(job, "QUEUED")

    assert store.claim("worker-1") is None

    past = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 60))
    with store.cx() as connection:
        connection.execute("UPDATE jobs SET run_after=? WHERE job_id=?", (past, job))
    assert store.claim("worker-1")["job_id"] == job


def test_heartbeat_extends_the_lease(store: Any, workflow: str) -> None:
    """A long-running job keeps its lease alive."""
    job = _job(store, workflow, "long")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    with store.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )
    store.heartbeat(job, "worker-1")

    assert store.get_job(job)["lease_until"] > "2020-01-01T00:00:00"


def test_heartbeat_from_a_non_owner_is_ignored(store: Any, workflow: str) -> None:
    """Only the lease owner may extend a lease.

    Otherwise a stale worker that lost its lease could keep a job alive and two
    workers would run it.
    """
    job = _job(store, workflow, "owned")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    stale = store.get_job(job)["lease_until"]

    store.heartbeat(job, "worker-2")
    assert store.get_job(job)["lease_until"] == stale


def test_heartbeat_on_a_finished_job_is_ignored(store: Any, workflow: str) -> None:
    """A completed job cannot be resurrected by a late heartbeat."""
    job = _job(store, workflow, "finished")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "COMPLETED")

    store.heartbeat(job, "worker-1")
    row = store.get_job(job)
    assert row["status"] == "COMPLETED"
    assert row["lease_until"] is None


# --------------------------------------------------------------------------- #
# Lease recovery -- the most important behaviour in the file
# --------------------------------------------------------------------------- #


def test_expired_lease_retries_when_work_is_safe_to_repeat(store: Any, workflow: str) -> None:
    """A crashed worker's job returns to RETRYING when repeating it is harmless.

    "Harmless" means idempotent local work, or a subscription runtime where a
    repeated call costs nothing.
    """
    job = _job(store, workflow, "safe", kind="project_compile")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    with store.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )

    assert store.recover_expired() == 1
    row = store.get_job(job)
    assert row["status"] in {"RETRYING", "QUEUED"}
    assert row["lease_owner"] is None

    events = [e for e in store.updates() if e["event_type"] == "RECOVERY"]
    assert events[-1]["payload"]["reason"] == "expired_lease_idempotent_or_subscription"


def test_expired_lease_does_not_retry_a_possibly_billed_paid_call(
    store: Any, workflow: str
) -> None:
    """The subtlest and most valuable rule in the legacy engine.

    When a worker dies mid-flight on a **paid** provider call, the system cannot
    know whether that call was already billed. Retrying could double-charge a
    client's study; assuming it succeeded could lose the work. Legacy refuses to
    guess: the job goes to RECOVERY_REQUIRED for a human, and any outstanding
    reservation is converted to conservative *actual* exposure so the budget
    reflects money that may already be gone.

    This must survive the port. Losing it turns a worker crash into a silent
    double-spend.
    """
    job = _job(
        store,
        workflow,
        "paid",
        kind="respondent_run",
        input_data={
            "mode": "live",
            "project": {"run_policy": {"provider": "anthropic"}},
        },
    )
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    with store.cx() as connection:
        connection.execute(
            "INSERT INTO cost_reservations VALUES(?,?,?,?,?,?,?)",
            ("RES-1", workflow, job, 4.25, "RESERVED", "2026-01-01T00:00:00", None),
        )
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )

    assert store.recover_expired() == 1

    row = store.get_job(job)
    assert row["status"] == "RECOVERY_REQUIRED", "must not auto-retry a paid call"
    assert row["actual_cost_usd"] == pytest.approx(4.25), "exposure recorded as actual"

    with store.cx() as connection:
        reservation = connection.execute(
            "SELECT status FROM cost_reservations WHERE reservation_id='RES-1'"
        ).fetchone()
    assert reservation["status"] == "SETTLED_UNCERTAIN"

    events = [e for e in store.updates() if e["event_type"] == "RECOVERY"]
    assert events[-1]["payload"]["reason"] == "paid_external_call_side_effect_uncertain"
    assert events[-1]["payload"]["conservative_cost_exposure_usd"] == pytest.approx(4.25)


def test_subscription_provider_is_safe_to_retry_even_when_live(store: Any, workflow: str) -> None:
    """A live run on the Claude Code subscription retries freely.

    Only the metered providers trigger the uncertain-billing path, because a
    repeated subscription call has no marginal cost. This is why the provider
    distinction has to reach the recovery logic.
    """
    job = _job(
        store,
        workflow,
        "subscription",
        kind="respondent_run",
        input_data={
            "mode": "live",
            "project": {"run_policy": {"provider": "claude_code_subscription"}},
        },
    )
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    with store.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )

    store.recover_expired()
    assert store.get_job(job)["status"] in {"RETRYING", "QUEUED"}


def test_dry_run_is_safe_to_retry(store: Any, workflow: str) -> None:
    """A dry run makes no provider call, so it always retries."""
    job = _job(
        store,
        workflow,
        "dry",
        kind="respondent_run",
        input_data={"mode": "dry", "project": {"run_policy": {"provider": "anthropic"}}},
    )
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    with store.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )

    store.recover_expired()
    assert store.get_job(job)["status"] in {"RETRYING", "QUEUED"}


def test_exhausted_attempts_go_to_recovery_not_retry(store: Any, workflow: str) -> None:
    """Retries are bounded; past the limit a human is required."""
    job = _job(store, workflow, "exhausted", max_attempts=1)
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    with store.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )

    store.recover_expired()
    assert store.get_job(job)["status"] == "RECOVERY_REQUIRED"


def test_recovery_ignores_jobs_with_a_live_lease(store: Any, workflow: str) -> None:
    """A healthy long-running job is not disturbed."""
    job = _job(store, workflow, "healthy")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    assert store.recover_expired() == 0
    assert store.get_job(job)["status"] == "RUNNING"


def test_recovery_survives_a_restart(store: Any, legacy_job_store_module: Any) -> None:
    """State is durable: a new store over the same file sees the same jobs.

    This is the restart guarantee -- an API or worker process dying loses nothing,
    because the queue is in the database rather than in memory.
    """
    workflow_id = store.create_workflow(project_id="PRJ-1", project_revision=1)
    job = _job(store, workflow_id, "durable")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    reopened = legacy_job_store_module.JobStore(store.path)
    row = reopened.get_job(job)
    assert row["status"] == "RUNNING"
    assert row["lease_owner"] == "worker-1"

    with reopened.cx() as connection:
        connection.execute(
            "UPDATE jobs SET lease_until='2000-01-01T00:00:00' WHERE job_id=?", (job,)
        )
    assert reopened.recover_expired() == 1


# --------------------------------------------------------------------------- #
# Cancellation
# --------------------------------------------------------------------------- #


def test_cancelling_a_running_job_is_cooperative(store: Any, workflow: str) -> None:
    """A RUNNING job is flagged, not killed.

    The worker polls ``cancel_requested`` at checkpoints, so cancellation leaves a
    consistent artifact state instead of a half-written one. The new engine must
    keep this rather than terminating a task.
    """
    job = _job(store, workflow, "running")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    assert store.request_cancel(job, source="api", reason="user asked")

    row = store.get_job(job)
    assert row["status"] == "RUNNING", "still running until the worker notices"
    assert row["cancel_requested"] == 1
    assert store.cancel_requested(job)


def test_cancelling_a_queued_job_is_immediate(store: Any, workflow: str) -> None:
    """Nothing is in flight, so there is nothing to co-operate with."""
    job = _job(store, workflow, "queued")
    store.transition(job, "QUEUED")

    store.request_cancel(job)
    row = store.get_job(job)
    assert row["status"] == "CANCELLED"
    assert row["finished_at"] is not None
    assert row["lease_owner"] is None


def test_cancelling_a_finished_job_changes_nothing(store: Any, workflow: str) -> None:
    """A completed job stays completed."""
    job = _job(store, workflow, "done")
    store.transition(job, "QUEUED")
    store.transition(job, "RUNNING")
    store.transition(job, "COMPLETED")

    assert store.request_cancel(job) is True, "legacy returns True regardless"
    assert store.get_job(job)["status"] == "COMPLETED"


def test_cancelling_an_unknown_job_returns_false(store: Any) -> None:
    """A missing job is reported, not invented."""
    assert store.request_cancel("JOB-nonexistent") is False


def test_cancellation_also_cancels_a_pending_approval(store: Any, workflow: str) -> None:
    """A cancelled job leaves no approval sitting in someone's queue."""
    job = _job(store, workflow, "awaiting")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.create_approval(job, "Continue on the paid API?", ["cancel", "continue_later"])

    assert len(store.pending_approvals()) == 1
    store.request_cancel(job)
    assert store.pending_approvals() == []


# --------------------------------------------------------------------------- #
# Waiting states
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("waiting", ["WAITING_USER", "WAITING_CAPACITY", "WAITING_CREDITS"])
def test_waiting_states_are_reachable_and_resumable(
    store: Any, workflow: str, waiting: str
) -> None:
    """Each waiting state is entered from RUNNING and left to QUEUED.

    They are parked states, not failures: a job in WAITING_CREDITS has not failed,
    it is waiting for a quota window to reset.
    """
    job = _job(store, workflow, f"wait-{waiting}")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, waiting)
    assert store.get_job(job)["status"] == waiting

    store.transition(job, "QUEUED")
    assert store.get_job(job)["status"] == "QUEUED"


def test_a_waiting_job_is_not_claimable(store: Any, workflow: str) -> None:
    """Parked work is not handed to a worker."""
    job = _job(store, workflow, "parked")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "WAITING_CREDITS")

    assert store.claim("worker-2") is None


def test_waiting_states_can_be_paused_but_not_completed(store: Any, workflow: str) -> None:
    """A parked job cannot jump straight to done."""
    job = _job(store, workflow, "parked")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "WAITING_CREDITS")

    with pytest.raises(ValueError):
        store.transition(job, "COMPLETED")
    store.transition(job, "PAUSED")
    assert store.get_job(job)["status"] == "PAUSED"


def test_budget_exhaustion_has_no_dedicated_state(
    legacy_job_store_module: Any,
) -> None:
    """DEVIATION TO COME: legacy has no WAITING_BUDGET.

    Budget exhaustion currently routes through WAITING_USER via an approval
    carrying ``increase_budget`` as an option. The brief requires a distinct
    WAITING_BUDGET state, which is a real improvement: "waiting for a person to
    decide something" and "blocked because this study is out of money" need
    different dashboards and different alerts.

    Recorded here so the addition is a deliberate design change rather than an
    accident.
    """
    assert "WAITING_BUDGET" not in legacy_job_store_module.STATUSES
    assert "WAITING_USER" in legacy_job_store_module.STATUSES


# --------------------------------------------------------------------------- #
# Approvals
# --------------------------------------------------------------------------- #


def test_creating_an_approval_parks_the_job(store: Any, workflow: str) -> None:
    """Requesting a decision moves the job to WAITING_USER."""
    job = _job(store, workflow, "gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    approval_id = store.create_approval(
        job, "Continue on the paid API?", ["use_anthropic_api", "cancel"]
    )

    assert store.get_job(job)["status"] == "WAITING_USER"
    pending = store.pending_approvals()
    assert len(pending) == 1
    assert pending[0]["approval_id"] == approval_id


def test_approval_option_must_be_one_of_the_offered_options(store: Any, workflow: str) -> None:
    """A decision cannot invent an option.

    The options are the cost and provenance choices presented to the user, so
    accepting an arbitrary string would mean acting on a decision nobody made.
    """
    job = _job(store, workflow, "gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Continue?", ["cancel", "continue_later"])

    for bad in ("", "yes", "use_anthropic_api", None):
        with pytest.raises(ValueError, match="approval"):
            store.decide_approval(approval_id, {"option": bad})


def test_deciding_twice_is_refused(store: Any, workflow: str) -> None:
    """An approval is decided once, so a replayed request cannot re-spend."""
    job = _job(store, workflow, "gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Continue?", ["continue_later", "cancel"])

    store.decide_approval(approval_id, {"option": "continue_later"})
    with pytest.raises(ValueError, match="already decided"):
        store.decide_approval(approval_id, {"option": "cancel"})


@pytest.mark.parametrize(
    ("option", "expected_status"),
    [("cancel", "CANCELLED"), ("continue_later", "PAUSED"), ("proceed", "QUEUED")],
)
def test_approval_option_determines_the_resulting_state(
    store: Any, workflow: str, option: str, expected_status: str
) -> None:
    """The three outcomes of a gate decision."""
    job = _job(store, workflow, f"gate-{option}")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Continue?", [option])

    store.decide_approval(approval_id, {"option": option})
    assert store.get_job(job)["status"] == expected_status


def test_paid_provider_approval_requires_a_cost_estimate(store: Any, workflow: str) -> None:
    """Authorising paid spend without showing a figure is refused.

    A user cannot consent to a cost they were never told. This is the
    no-silent-paid-fallback rule expressed at the approval boundary.
    """
    job = _job(store, workflow, "paid-gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(
        job, "Continue on the paid API?", ["use_anthropic_api"], context={}
    )

    with pytest.raises(ValueError, match="cost estimate"):
        store.decide_approval(approval_id, {"option": "use_anthropic_api"})


def test_paid_provider_approval_records_the_estimate_shown(store: Any, workflow: str) -> None:
    """The figure the user saw is persisted with their decision.

    So a later cost dispute can be answered with what was actually presented.
    """
    job = _job(store, workflow, "paid-gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(
        job,
        "Continue on the paid API?",
        ["use_anthropic_api"],
        context={"provider_estimates_usd": {"anthropic": 12.5}},
    )

    updated = store.decide_approval(approval_id, {"option": "use_anthropic_api"})
    decision = updated["input"]["approval_decisions"][-1]

    assert decision["provider"] == "anthropic"
    assert decision["estimated_cost_usd"] == pytest.approx(12.5)
    assert updated["status"] == "QUEUED"


def test_increase_budget_raises_the_workflow_cap(store: Any, workflow: str) -> None:
    """An approval can lift the budget, and does so atomically with the decision."""
    job = _job(store, workflow, "budget-gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Raise the budget?", ["increase_budget"])

    store.decide_approval(approval_id, {"option": "increase_budget", "budget_usd": 75.0})
    assert store.get_workflow(workflow)["budget_usd"] == pytest.approx(75.0)


def test_increase_budget_rejects_a_non_positive_cap(store: Any, workflow: str) -> None:
    """Raising a budget to zero is not a budget increase."""
    job = _job(store, workflow, "budget-gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Raise?", ["increase_budget"])

    with pytest.raises(ValueError, match="budget_usd"):
        store.decide_approval(approval_id, {"option": "increase_budget", "budget_usd": 0})


def test_reduce_n_rewrites_the_job_input(store: Any, workflow: str) -> None:
    """A user can shrink a run to fit the budget, and the job input is updated.

    Note the input mutation: the approval decision changes what the job will do,
    not merely whether it proceeds.
    """
    job = _job(store, workflow, "n-gate", input_data={"project": {"n": 1000, "title": "t"}})
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    approval_id = store.create_approval(job, "Reduce the sample?", ["reduce_n"])

    updated = store.decide_approval(approval_id, {"option": "reduce_n", "n": 250})
    assert updated["input"]["project"]["n"] == 250
    assert updated["input"]["project"]["title"] == "t", "other fields are preserved"


def test_approval_decisions_accumulate(store: Any, workflow: str) -> None:
    """Decisions are appended, so the consent history of a job is retained."""
    job = _job(store, workflow, "multi-gate")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    first = store.create_approval(job, "One?", ["proceed"])
    store.decide_approval(first, {"option": "proceed"})
    store.claim("worker-1")
    second = store.create_approval(job, "Two?", ["proceed"])
    store.decide_approval(second, {"option": "proceed"})

    decisions = store.get_job(job)["input"]["approval_decisions"]
    assert len(decisions) == 2


# --------------------------------------------------------------------------- #
# Workflow status derivation
# --------------------------------------------------------------------------- #


def test_workflow_completes_only_when_every_job_completes(store: Any, workflow: str) -> None:
    """A workflow is done when all of its jobs are."""
    first = _job(store, workflow, "a")
    second = _job(store, workflow, "b")
    store.activate_workflow_graph(workflow)

    for job in (first, second):
        store.transition(job, "RUNNING")
        store.transition(job, "COMPLETED")

    assert store.get_workflow(workflow)["status"] == "COMPLETED"
    assert store.get_workflow(workflow)["finished_at"] is not None


def test_one_failed_job_fails_the_workflow(store: Any, workflow: str) -> None:
    """Failure is visible at the workflow level."""
    first = _job(store, workflow, "a")
    _job(store, workflow, "b")
    store.activate_workflow_graph(workflow)

    store.transition(first, "RUNNING")
    store.transition(first, "FAILED", error={"message": "no"})

    assert store.get_workflow(workflow)["status"] == "FAILED"


def test_workflow_status_precedence(store: Any, workflow: str) -> None:
    """Derivation order, which drives the operator dashboard.

    FAILED outranks every waiting state, and WAITING_USER outranks
    WAITING_CAPACITY and WAITING_CREDITS -- a decision a person must make is more
    urgent than a condition that will clear itself.
    """
    waiting_user = _job(store, workflow, "a")
    waiting_credits = _job(store, workflow, "b")
    store.activate_workflow_graph(workflow)

    store.claim("worker-1")
    store.transition(waiting_credits, "WAITING_CREDITS", force=True)
    assert store.get_workflow(workflow)["status"] == "WAITING_CREDITS"

    store.transition(waiting_user, "WAITING_USER", force=True)
    assert store.get_workflow(workflow)["status"] == "WAITING_USER"

    store.transition(waiting_user, "FAILED", force=True)
    assert store.get_workflow(workflow)["status"] == "FAILED"


def test_paused_workflow_stops_queueing(store: Any, workflow: str) -> None:
    """Pausing a workflow halts it without cancelling anything."""
    job = _job(store, workflow, "a")

    with store.cx() as connection:
        connection.execute("UPDATE workflows SET status='PAUSED' WHERE workflow_id=?", (workflow,))

    store.queue_ready_jobs(workflow)
    assert store.get_job(job)["status"] == "READY"
    assert store.claim("worker-1") is None


# --------------------------------------------------------------------------- #
# Configuration and the event log
# --------------------------------------------------------------------------- #


def test_a_running_job_cannot_be_reconfigured(store: Any, workflow: str) -> None:
    """Changing a provider mid-flight would make provenance unanswerable."""
    job = _job(store, workflow, "a")
    store.transition(job, "QUEUED")
    store.claim("worker-1")

    with pytest.raises(ValueError):
        store.configure_job(job, provider="anthropic")


def test_a_queued_job_can_be_reconfigured(store: Any, workflow: str) -> None:
    """Before it runs, a phase's provider and model may be overridden."""
    job = _job(store, workflow, "a")
    store.transition(job, "QUEUED")

    updated = store.configure_job(job, provider="anthropic", model="opus")
    assert updated["provider_policy"] == "anthropic"
    assert updated["model"] == "opus"
    assert updated["input"]["phase_policy"] == {"provider": "anthropic", "model": "opus"}


def test_event_log_is_append_only_and_ordered(store: Any, workflow: str) -> None:
    """Events are the audit trail and the progress feed.

    ``updates(since=)`` is monotonic by ``event_id``, which is what lets a
    reconnecting client resume without gaps or duplicates.
    """
    job = _job(store, workflow, "a")
    store.transition(job, "QUEUED")
    store.claim("worker-1")
    store.transition(job, "COMPLETED")

    events = store.updates()
    ids = [e["event_id"] for e in events]
    assert ids == sorted(ids)

    types = [e["event_type"] for e in events if e["job_id"] == job]
    assert types[0] == "CREATED"
    assert "CLAIMED" in types
    assert "STATUS" in types

    midpoint = ids[len(ids) // 2]
    later = store.updates(since=midpoint)
    assert all(e["event_id"] > midpoint for e in later)


def test_worker_heartbeat_upserts(store: Any) -> None:
    """Worker liveness is tracked, so a dashboard can show a dead worker."""
    store.worker_heartbeat("worker-1", pid=123, status="BUSY", current_job_id="JOB-x")
    store.worker_heartbeat("worker-1", pid=123, status="READY", current_job_id=None)

    workers = store.workers()
    assert len(workers) == 1
    assert workers[0]["status"] == "READY"


def test_timestamps_are_naive_local_time(store: Any, workflow: str) -> None:
    """DEVIATION TO COME: legacy timestamps are naive local-time strings.

    ``time.strftime('%Y-%m-%dT%H:%M:%S')`` with no offset. Lease expiry, run_after
    and audit ordering therefore all depend on the host's timezone, and comparing
    across a DST boundary or between hosts in different zones is ambiguous.

    The new schema uses ``TIMESTAMP WITH TIME ZONE`` in UTC. Recorded so the
    change is deliberate, and so anyone importing legacy rows knows they carry no
    offset.
    """
    job = _job(store, workflow, "a")
    created = store.get_job(job)["created_at"]

    assert len(created) == 19
    assert "+" not in created
    assert not created.endswith("Z")
