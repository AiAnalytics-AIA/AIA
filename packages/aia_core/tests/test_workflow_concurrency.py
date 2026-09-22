"""Concurrency and transaction-semantics tests against real PostgreSQL.

**Phase 3 is not complete without these.** Everything here uses genuinely
concurrent transactions on separate connections -- real threads, real locks --
rather than sequential calls that merely look concurrent. A sequential mock
cannot detect the bug these exist to catch: two workers claiming the same step.

The tests are marked ``postgres`` and skip on SQLite, which has no
``FOR UPDATE SKIP LOCKED`` and a single-writer model, so it cannot express the
contention being tested. Skipping is honest; pretending to pass would not be.

Run with a real database:

    DATABASE_URL=postgresql+psycopg://... pytest -m postgres
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import (
    AttemptStatus,
    RecoveryAction,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import (
    Base,
    BudgetReservationRow,
    StepAttemptRow,
    StudyRow,
)
from aia_core.infrastructure.workflow_repository import (
    BudgetExceeded,
    LeaseLost,
    WorkflowRepository,
)

pytestmark = pytest.mark.postgres


def _database_url() -> str | None:
    """Return the PostgreSQL URL, or None when only SQLite is configured."""
    url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith("postgresql") else None


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    """A PostgreSQL engine, skipping the module when one is not configured.

    A dedicated engine, because the point of these tests is contention and the
    shared engine's default pool is too small for eight simultaneous workers.

    It **creates but never drops** the schema. The session-scoped ``engine``
    fixture in conftest owns the schema's lifecycle; dropping it here tore the
    tables out from under every other test module that had already started,
    which surfaced as a hundred unrelated errors. ``create_all`` is idempotent,
    so calling it is harmless.
    """
    url = _database_url()
    if url is None:
        message = (
            "concurrency tests require PostgreSQL; set DATABASE_URL to a "
            "postgresql:// URL. SQLite cannot express FOR UPDATE SKIP LOCKED."
        )
        # CI sets AIA_REQUIRE_POSTGRES=1 so that a missing database is a
        # FAILURE, not a skip. These tests are the only thing that detects two
        # workers claiming one step, a lock convoy, or a budget overspend race,
        # and every one of those passed the sequential suite. A silent skip
        # would let the build go green with none of them checked.
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)

    engine = create_app_engine(url, pool_size=12, max_overflow=8)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def _truncate_all(factory: sessionmaker[Session]) -> None:
    """Empty every table, in dependency order."""
    with factory() as cleanup:
        for table in reversed(Base.metadata.sorted_tables):
            cleanup.execute(table.delete())
        cleanup.commit()


@pytest.fixture
def pg_sessions(pg_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """A session factory over PostgreSQL, with the tables emptied around each test.

    Cleaned at **setup as well as teardown**. These tests commit from several
    connections, so a test killed mid-run (a deadlock, a timeout, an interrupt)
    leaves committed rows behind and the next run then fails on a unique
    constraint -- a confusing failure that has nothing to do with the code under
    test. Cleaning on the way in makes the suite self-healing.
    """
    factory = create_session_factory(pg_engine)
    _truncate_all(factory)
    try:
        yield factory
    finally:
        _truncate_all(factory)


@pytest.fixture
def world(pg_sessions: sessionmaker[Session], scope_builder: Any) -> dict[str, Any]:
    """A committed scope graph, a project, and a run with parallel steps.

    Everything is committed, because concurrent transactions on other
    connections cannot see uncommitted rows.
    """
    with pg_sessions() as session:
        scoped = scope_builder(session)
        scope = scoped.scope(user="lead", study="primary")

        project, _ = ProjectRepository(session, scope).create(title="Concurrency host")

        study = session.get(StudyRow, scope.study_id)
        assert study is not None
        study.budget_usd = 100.0
        study.spent_usd = 0.0

        engine_repo = WorkflowRepository(session, scope)
        # Four independent steps, so several workers can contend for work
        # without the DAG serialising them.
        run_id = engine_repo.create_run(
            project_id=project.project_id,
            project_revision=1,
            workflow_type="parallel",
            steps=[StepDefinition(node_key=f"s{i}", kind="k") for i in range(4)],
            idempotency_key="concurrency-run",
        )
        session.commit()

        return {
            "run_id": run_id,
            "project_id": project.project_id,
            "organization_id": scope.organization_id,
            "client_id": scope.client_id,
            "study_id": scope.study_id,
            "users": dict(scoped.users),
            "studies": {k: v.study_id for k, v in scoped.studies.items()},
        }


def _repo_in_new_session(
    factory: sessionmaker[Session], world: dict[str, Any], *, user: str = "lead"
) -> tuple[Session, WorkflowRepository]:
    """Build a repository on a fresh connection, re-resolving scope.

    Scope is deliberately not serialisable, so a worker on another connection
    resolves it again from the database -- which is what a real worker does.
    """
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver

    session = factory()
    resolver = ScopeResolver(session)
    scope = resolver.study_context(
        AuthenticatedPrincipal(
            user_id=world["users"][user], organization_id=world["organization_id"]
        ),
        study_id=world["studies"]["primary"],
    )
    return session, WorkflowRepository(session, scope)


def _run_concurrently(count: int, work: Callable[[int], Any]) -> list[Any]:
    """Run ``work`` on ``count`` threads released simultaneously.

    A barrier is essential. Without it the threads start staggered and the test
    silently degrades into a sequential one that cannot detect a race.
    """
    barrier = threading.Barrier(count)

    def task(index: int) -> Any:
        barrier.wait(timeout=30)
        return work(index)

    with ThreadPoolExecutor(max_workers=count) as pool:
        return [
            future.result(timeout=60) for future in [pool.submit(task, i) for i in range(count)]
        ]


# --------------------------------------------------------------------------- #
# 1. Lease and concurrency correctness
# --------------------------------------------------------------------------- #


def test_simultaneous_claims_never_hand_one_step_to_two_workers(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**The central concurrency guarantee.**

    Eight workers race for four steps. Each step must be claimed exactly once.
    Duplicate execution here means two workers running the same AI step against
    the same study -- doubling its cost and racing to write the same artifact.
    """

    def claim(index: int) -> str | None:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            claimed = repo.claim_next(worker_id=f"worker-{index}")
            session.commit()
            return claimed.step_id if claimed else None
        finally:
            session.close()

    results = _run_concurrently(8, claim)
    claimed_steps = [step_id for step_id in results if step_id is not None]

    assert len(claimed_steps) == 4, "all four steps should be claimed"
    assert len(set(claimed_steps)) == 4, (
        f"each step claimed exactly once; got duplicates in {claimed_steps}"
    )
    assert results.count(None) == 4, "the other four workers find no work"


def test_each_step_has_exactly_one_attempt_after_a_claim_race(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """The database is the proof, not the return values.

    Even if two claims somehow returned the same step, the attempt table would
    show it -- and the unique constraint on (step_id, attempt_number) would have
    rejected the second insert.
    """

    def claim(index: int) -> None:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            repo.claim_next(worker_id=f"worker-{index}")
            session.commit()
        finally:
            session.close()

    _run_concurrently(10, claim)

    with pg_sessions() as session:
        attempts = session.scalars(select(StepAttemptRow)).all()
        assert len(attempts) == 4

        per_step: dict[str, list[int]] = {}
        for attempt in attempts:
            per_step.setdefault(attempt.step_id, []).append(attempt.attempt_number)
        assert all(numbers == [1] for numbers in per_step.values()), per_step
        assert len({a.worker_id for a in attempts}) == 4, "four distinct workers"


def test_concurrent_settlements_compose_rather_than_overwrite(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**Deterministic regression for the lost update on `studies.spent_usd`.**

    `test_concurrent_reconcilers_recover_each_attempt_once` caught this once in
    CI, as ``assert 5.0 == 10.0``, and then passed on rerun. It was not
    flakiness. `_charge_study` was a read-modify-write with no lock, and
    PostgreSQL runs READ COMMITTED, so two transactions settling two different
    reservations each read `spent_usd` as it stood before the other committed and
    the last writer won. Money a client had spent was not recorded, and
    unrecorded spend is headroom the budget check hands out again.

    That test only fails when the interleaving happens to line up -- it did not
    reproduce in 25 consecutive runs here. This one holds every transaction at a
    barrier until all have started and puts eight of them on one study row, so the
    interleaving is forced rather than hoped for: measured at 12 failures in 12
    runs against the old implementation, and it passes against the atomic
    increment.

    Eight settlements of $5 must record $40. Any lower figure is a lost update.
    """
    setup_session, setup_repo = _repo_in_new_session(pg_sessions, world)
    reservations: list[str] = []
    try:
        # Two reservations per attempt, so eight transactions contend for one
        # study row. Four was enough to fail most of the time; eight makes the
        # loser of the race overwhelmingly likely to exist.
        for index in range(4):
            work = setup_repo.claim_next(worker_id=f"settler-{index}")
            assert work is not None
            for _ in range(2):
                reservation_id = setup_repo.reserve_budget(
                    attempt_id=work.attempt_id,
                    worker_id=work.worker_id,
                    amount_usd=5.0,
                    provider=Provider.ANTHROPIC,
                )
                assert reservation_id is not None
                reservations.append(reservation_id)
        setup_session.commit()
    finally:
        setup_session.close()

    def settle(index: int) -> None:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            repo.settle_reservation(reservations[index], actual_cost_usd=5.0)
            session.commit()
        finally:
            session.close()

    _run_concurrently(len(reservations), settle)

    with pg_sessions() as session:
        study = session.get(StudyRow, world["study_id"])
        assert study is not None
        assert study.spent_usd == pytest.approx(40.0), (
            "eight concurrent $5 settlements must record $40; a lower figure is a "
            "lost update on studies.spent_usd, which under-records client spend "
            "and hands the difference back as budget headroom"
        )


def test_concurrent_reconcilers_recover_each_attempt_once(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Two reconcilers must not both recover the same lapsed attempt.

    Double recovery of an uncertain paid call would double-count its exposure and
    charge the study twice for money that may have been spent once.
    """
    setup_session, setup_repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = []
        for index in range(4):
            work = setup_repo.claim_next(worker_id=f"worker-{index}")
            assert work is not None
            claimed.append(work)

        # Reserve for two of them and dispatch, so recovery must settle
        # uncertain exposure -- the expensive path to double-count.
        for work in claimed[:2]:
            setup_repo.reserve_budget(
                attempt_id=work.attempt_id,
                worker_id=work.worker_id,
                amount_usd=5.0,
                provider=Provider.ANTHROPIC,
            )
            setup_repo.mark_paid_call_dispatched(work.attempt_id, worker_id=work.worker_id)

        for work in claimed:
            attempt = setup_session.get(StepAttemptRow, work.attempt_id)
            assert attempt is not None
            attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
        setup_session.commit()
    finally:
        setup_session.close()

    def reconcile(_: int) -> list[RecoveryAction]:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            decisions = repo.recover_expired_attempts()
            session.commit()
            return [d.action for d in decisions]
        finally:
            session.close()

    results = _run_concurrently(4, reconcile)
    total = sum(len(actions) for actions in results)

    assert total == 4, f"each attempt recovered exactly once, got {total}"

    with pg_sessions() as session:
        # Exposure counted once: two reservations of $5.
        study = session.get(StudyRow, world["study_id"])
        assert study is not None
        assert study.spent_usd == pytest.approx(10.0), (
            "uncertain exposure must be charged once per reservation, not once per reconciler"
        )
        uncertain = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.status == "SETTLED_UNCERTAIN")
        ).all()
        assert len(uncertain) == 2


def test_a_recovered_step_can_be_reclaimed_with_the_next_attempt_number(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """After recovery the step is claimable again, as attempt 2.

    Append-only numbering must survive a concurrent recovery: no reused numbers,
    no gaps that suggest a lost attempt.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        first = repo.claim_next(worker_id="worker-1")
        assert first is not None
        attempt = session.get(StepAttemptRow, first.attempt_id)
        assert attempt is not None
        attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()

        assert repo.recover_expired_attempts()[0].action is RecoveryAction.RETRY
        session.commit()
    finally:
        session.close()

    def reclaim(index: int) -> int | None:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            claimed = r.claim_next(worker_id=f"retry-worker-{index}")
            s.commit()
            return claimed.attempt_number if claimed else None
        finally:
            s.close()

    numbers = [n for n in _run_concurrently(6, reclaim) if n is not None]

    with pg_sessions() as check:
        attempts = check.scalars(
            select(StepAttemptRow)
            .where(StepAttemptRow.step_id == first.step_id)
            .order_by(StepAttemptRow.attempt_number)
        ).all()
        assert [a.attempt_number for a in attempts] == [1, 2], (
            "the retry is attempt 2, recorded once"
        )
        assert attempts[0].status == AttemptStatus.EXPIRED.value
        assert 2 in numbers


def test_concurrent_cancellation_requests_are_idempotent(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Two users cancelling at once must not corrupt the run."""
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        repo.claim_next(worker_id="worker-1")
        session.commit()
    finally:
        session.close()

    def cancel(_: int) -> str:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            status = r.request_cancel(world["run_id"], reason="concurrent cancel")
            s.commit()
            return status.value
        finally:
            s.close()

    statuses = _run_concurrently(4, cancel)
    assert all(s in {"CANCELLED", "RUNNING"} for s in statuses), statuses

    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        state = repo.get_run(world["run_id"])
        assert state["cancel_requested"] is True
        assert all(
            s["status"] in (StepRunStatus.CANCELLED, StepRunStatus.RUNNING) for s in state["steps"]
        )
    finally:
        session.close()


def test_cancellation_racing_a_claim_never_starts_new_work(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """A cancelling run must not hand out new steps.

    The race is real: a claim in flight when cancellation commits. Afterwards no
    step may be RUNNABLE, because that would be work started on a cancelled
    study.
    """

    def act(index: int) -> None:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            if index == 0:
                repo.request_cancel(world["run_id"], reason="race")
            else:
                repo.claim_next(worker_id=f"worker-{index}")
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    _run_concurrently(6, act)

    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        state = repo.get_run(world["run_id"])
        assert state["cancel_requested"] is True
        assert not any(s["status"] is StepRunStatus.RUNNABLE for s in state["steps"]), (
            "no step may remain runnable on a cancelled run"
        )
        assert repo.claim_next(worker_id="late-worker") is None
    finally:
        session.close()


def test_heartbeat_races_do_not_transfer_a_lease(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Concurrent heartbeats from non-owners must all be refused.

    If one succeeded, two workers would believe they own the step.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="owner")
        assert claimed is not None
        session.commit()
    finally:
        session.close()

    def beat(index: int) -> bool:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            worker = "owner" if index == 0 else f"impostor-{index}"
            accepted = r.heartbeat(claimed.attempt_id, worker_id=worker)
            s.commit()
            return accepted
        finally:
            s.close()

    results = _run_concurrently(6, beat)
    assert results.count(True) == 1, "only the owner's heartbeat is accepted"

    with pg_sessions() as check:
        attempt = check.get(StepAttemptRow, claimed.attempt_id)
        assert attempt is not None
        assert attempt.worker_id == "owner"


def test_regression_a_heartbeat_cannot_resurrect_an_attempt_recovered_under_it(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**W1.** A reconciler's verdict must survive a heartbeat that read first.

    The interleaving is forced rather than raced, so the test fails every time on
    the defect instead of occasionally:

    1. the worker's session has the attempt loaded -- as a heartbeat that has
       done its read would;
    2. a reconciler on another connection expires and recovers it, and commits;
    3. the worker's heartbeat proceeds.

    Before the fix, step 3 wrote ``EXECUTING`` and a fresh deadline back over
    ``EXPIRED`` by primary key, while the step was already ``RUNNABLE`` -- so a
    second worker claimed it and two workers ran one step. Measured: fails 1 of 1
    against the read-check-write heartbeat, passes against the conditional update.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="owner")
        assert claimed is not None
        attempt = session.get(StepAttemptRow, claimed.attempt_id)
        assert attempt is not None
        attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    finally:
        session.close()

    worker_session, worker_repo = _repo_in_new_session(pg_sessions, world)
    try:
        # (1) the worker has read the attempt; it is CLAIMED in its identity map.
        stale = worker_session.get(StepAttemptRow, claimed.attempt_id)
        assert stale is not None
        assert stale.status == AttemptStatus.CLAIMED.value

        # (2) a reconciler recovers it on another connection, and commits.
        reconciler_session, reconciler_repo = _repo_in_new_session(pg_sessions, world)
        try:
            assert len(reconciler_repo.recover_expired_attempts()) == 1
            reconciler_session.commit()
        finally:
            reconciler_session.close()

        # (3) the worker's heartbeat must now be refused.
        assert worker_repo.heartbeat(claimed.attempt_id, worker_id="owner") is False
        worker_session.commit()
    finally:
        worker_session.close()

    with pg_sessions() as check:
        attempt = check.get(StepAttemptRow, claimed.attempt_id)
        assert attempt is not None
        assert attempt.status == AttemptStatus.EXPIRED.value, "the recovery verdict stands"

    # And the step is claimable by a new owner.
    successor_session, successor_repo = _repo_in_new_session(pg_sessions, world)
    try:
        assert successor_repo.claim_next(worker_id="successor") is not None
        successor_session.commit()
    finally:
        successor_session.close()


def test_completion_racing_recovery_leaves_exactly_one_outcome(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**W2 under contention.** The owner finishing as the reconciler fires.

    Either the completion wins -- the attempt is SUCCEEDED and recovery finds
    nothing -- or recovery wins and the completion is refused with ``LeaseLost``.
    What must never happen is both: a SUCCEEDED step that recovery also made
    RUNNABLE again. Repeated, because a race lost once proves little.
    """
    for round_number in range(8):
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            # A fresh one-step run per round, claimed at a priority above the
            # fixture's steps, so every round races over a step of its own.
            repo.create_run(
                project_id=world["project_id"],
                project_revision=1,
                workflow_type="race",
                steps=[StepDefinition(node_key="only", kind="k", priority=99)],
                idempotency_key=f"race-{round_number}",
            )
            claimed = repo.claim_next(worker_id=f"owner-{round_number}")
            assert claimed is not None
            attempt = session.get(StepAttemptRow, claimed.attempt_id)
            assert attempt is not None
            attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
            session.commit()
        finally:
            session.close()

        def act(index: int, work: Any = claimed) -> str:
            s, r = _repo_in_new_session(pg_sessions, world)
            try:
                if index == 0:
                    try:
                        r.complete_attempt(work.attempt_id, worker_id=work.worker_id)
                    except LeaseLost:
                        s.rollback()
                        return "refused"
                    s.commit()
                    return "completed"
                recovered = r.recover_expired_attempts()
                s.commit()
                return f"recovered:{len(recovered)}"
            finally:
                s.close()

        outcome = _run_concurrently(2, act)
        assert sorted(outcome) in (
            ["completed", "recovered:0"],
            ["recovered:1", "refused"],
        ), f"round {round_number}: {outcome}"

        with pg_sessions() as check:
            attempts = check.scalars(
                select(StepAttemptRow).where(StepAttemptRow.step_id == claimed.step_id)
            ).all()
            statuses = sorted(a.status for a in attempts)
            assert statuses.count(AttemptStatus.SUCCEEDED.value) <= 1


# --------------------------------------------------------------------------- #
# 2. Idempotency under concurrency
# --------------------------------------------------------------------------- #


def test_concurrent_run_creation_with_one_key_creates_one_run(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Two triggers firing at once must not start two pipelines.

    The unique constraint on ``idempotency_key`` is the backstop: whichever
    transaction loses the race sees a violation and must resolve to the winner's
    run rather than creating a duplicate.
    """
    steps = [StepDefinition(node_key="only", kind="k")]

    def create(_: int) -> str | None:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            run_id = repo.create_run(
                project_id=world["project_id"],
                project_revision=1,
                workflow_type="dedup",
                steps=steps,
                idempotency_key="the-one-key",
            )
            session.commit()
            return run_id
        except Exception:
            # A losing transaction must fail cleanly, not half-create a run.
            session.rollback()
            return None
        finally:
            session.close()

    results = _run_concurrently(6, create)
    created = [r for r in results if r is not None]

    assert created, "at least one creation must succeed"
    assert len(set(created)) == 1, f"all winners agree on one run, got {set(created)}"

    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        # And a later, uncontended call resolves to the same run.
        assert (
            repo.create_run(
                project_id=world["project_id"],
                project_revision=1,
                workflow_type="dedup",
                steps=steps,
                idempotency_key="the-one-key",
            )
            == created[0]
        )
    finally:
        session.close()


def test_a_duplicate_delivery_after_success_does_not_re_execute(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """A worker woken again after the step succeeded must find nothing to do.

    A SUCCEEDED step is not claimable, so the second worker does no work rather
    than repeating an AI call. This is what makes a duplicate wake-up harmless --
    from a crash recovery today, or from an at-least-once delivery if a wake-up
    mechanism is ever added in front of the claim.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        repo.complete_attempt(claimed.attempt_id, worker_id=claimed.worker_id, output={"ok": True})
        session.commit()
        completed_step = claimed.step_id
    finally:
        session.close()

    def wake(index: int) -> str | None:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            work = r.claim_next(worker_id=f"redelivered-{index}")
            s.commit()
            return work.step_id if work else None
        finally:
            s.close()

    picked = [step for step in _run_concurrently(5, wake) if step is not None]
    assert completed_step not in picked, "a succeeded step must never be re-claimed"

    with pg_sessions() as check:
        attempts = check.scalars(
            select(StepAttemptRow).where(StepAttemptRow.step_id == completed_step)
        ).all()
        assert len(attempts) == 1, "no second attempt was created"


# --------------------------------------------------------------------------- #
# 4. Accounting transactionality
# --------------------------------------------------------------------------- #


def test_concurrent_reservations_cannot_exceed_the_budget(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**The overspend guard, under real contention.**

    Four workers each try to reserve $40 against a $100 budget. At most two can
    succeed. Without reservations counting as spent, all four would see $100
    available and together commit $160 of a client's money.
    """
    claims: list[str] = []
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        for index in range(4):
            work = repo.claim_next(worker_id=f"worker-{index}")
            assert work is not None
            claims.append(work.attempt_id)
        session.commit()
    finally:
        session.close()

    def reserve(index: int) -> bool:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            r.reserve_budget(
                attempt_id=claims[index],
                worker_id=f"worker-{index}",
                amount_usd=40.0,
                provider=Provider.ANTHROPIC,
            )
            s.commit()
            return True
        except (BudgetExceeded, Exception):
            s.rollback()
            return False
        finally:
            s.close()

    results = _run_concurrently(4, reserve)
    granted = results.count(True)

    assert granted <= 2, f"at most two $40 reservations fit in $100, got {granted}"

    with pg_sessions() as check:
        reservations = check.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.status == "RESERVED")
        ).all()
        total = sum(r.amount_usd for r in reservations)
        assert total <= 100.0 + 1e-9, f"reserved {total} exceeds the budget"


def test_a_failed_reservation_leaves_no_partial_state(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """A refused reservation must not leave a row behind.

    Otherwise a rejected call would still hold budget, and the study would drift
    towards a false exhaustion.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        session.commit()

        with pytest.raises(BudgetExceeded):
            repo.reserve_budget(
                attempt_id=claimed.attempt_id,
                worker_id=claimed.worker_id,
                amount_usd=1_000.0,
                provider=Provider.ANTHROPIC,
            )
        session.rollback()
    finally:
        session.close()

    with pg_sessions() as check:
        assert check.scalars(select(BudgetReservationRow)).all() == []
        study = check.get(StudyRow, world["study_id"])
        assert study is not None
        assert study.spent_usd == pytest.approx(0.0)


def test_an_attempt_and_its_reservation_commit_or_roll_back_together(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**"A provider was called but no attempt exists" must be unrepresentable.**

    The attempt, its reservation and the execution state are one unit of work,
    written before any external dispatch. Rolling the transaction back must leave
    neither half.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        repo.reserve_budget(
            attempt_id=claimed.attempt_id,
            worker_id=claimed.worker_id,
            amount_usd=10.0,
            provider=Provider.ANTHROPIC,
        )
        # Simulate a crash between preparing the call and dispatching it.
        session.rollback()
    finally:
        session.close()

    with pg_sessions() as check:
        assert check.scalars(select(StepAttemptRow)).all() == [], "no attempt survived the rollback"
        assert check.scalars(select(BudgetReservationRow)).all() == [], (
            "and no reservation survived either"
        )
        study = check.get(StudyRow, world["study_id"])
        assert study is not None
        assert study.spent_usd == pytest.approx(0.0)


def test_uncertain_settlement_is_charged_exactly_once_under_contention(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Concurrent recovery of one uncertain paid call charges the study once.

    Double-charging here would inflate a client's spend for a call that may have
    happened once -- the exact accounting lie the design exists to avoid.
    """
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = repo.claim_next(worker_id="worker-1")
        assert claimed is not None
        repo.reserve_budget(
            attempt_id=claimed.attempt_id,
            worker_id=claimed.worker_id,
            amount_usd=7.5,
            provider=Provider.ANTHROPIC,
        )
        repo.mark_paid_call_dispatched(
            claimed.attempt_id, worker_id=claimed.worker_id, provider_request_id="req_x"
        )
        attempt = session.get(StepAttemptRow, claimed.attempt_id)
        assert attempt is not None
        attempt.lease_until = datetime.now(UTC) - timedelta(minutes=10)
        session.commit()
    finally:
        session.close()

    def reconcile(_: int) -> int:
        s, r = _repo_in_new_session(pg_sessions, world)
        try:
            decisions = r.recover_expired_attempts()
            s.commit()
            return len(decisions)
        except Exception:
            s.rollback()
            return 0
        finally:
            s.close()

    assert sum(_run_concurrently(5, reconcile)) == 1, "recovered exactly once"

    with pg_sessions() as check:
        study = check.get(StudyRow, world["study_id"])
        assert study is not None
        assert study.spent_usd == pytest.approx(7.5), "charged once, not five times"

        reservations = check.scalars(select(BudgetReservationRow)).all()
        assert len(reservations) == 1
        assert reservations[0].status == "SETTLED_UNCERTAIN"


# --------------------------------------------------------------------------- #
# Transaction isolation
# --------------------------------------------------------------------------- #


def test_uncommitted_work_is_invisible_to_other_connections(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """A worker must not see another's uncommitted claim.

    This is why the claim path relies on row locks rather than on reading state:
    at READ COMMITTED, an uncommitted claim is invisible, so without a lock two
    workers would both believe a step is free.
    """
    writer, writer_repo = _repo_in_new_session(pg_sessions, world)
    # The reader needs only its session: it queries directly to prove what is
    # visible, rather than going through the repository.
    reader, _ = _repo_in_new_session(pg_sessions, world)
    try:
        claimed = writer_repo.claim_next(worker_id="writer")
        assert claimed is not None
        # Deliberately not committed.

        visible = reader.scalars(
            select(StepAttemptRow).where(StepAttemptRow.attempt_id == claimed.attempt_id)
        ).all()
        assert visible == [], "an uncommitted attempt is invisible elsewhere"

        writer.commit()
        reader.commit()  # end the reader's snapshot

        assert (
            reader.scalars(
                select(StepAttemptRow).where(StepAttemptRow.attempt_id == claimed.attempt_id)
            ).all()
            != []
        ), "and visible once committed"
    finally:
        writer.close()
        reader.close()


def test_skip_locked_lets_a_second_worker_proceed_without_blocking(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """``SKIP LOCKED`` is why a busy queue does not serialise.

    Worker A holds a lock on one step inside an open transaction. Worker B must
    get a *different* step immediately rather than waiting for A to commit. With
    plain ``FOR UPDATE`` this test would block until the timeout.
    """
    first_session, first_repo = _repo_in_new_session(pg_sessions, world)
    second_session, second_repo = _repo_in_new_session(pg_sessions, world)
    try:
        first = first_repo.claim_next(worker_id="worker-a")
        assert first is not None
        # first_session stays open, holding its lock.

        second = second_repo.claim_next(worker_id="worker-b")
        assert second is not None, "the second worker must not block"
        assert second.step_id != first.step_id, "it must get a different step"

        first_session.commit()
        second_session.commit()
    finally:
        first_session.close()
        second_session.close()


def test_cross_client_isolation_holds_under_concurrency(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """Concurrency must not weaken the client boundary.

    A worker on another client's study, polling hard at the same time, must never
    receive work from this one.
    """
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver

    def poll_other_client(_: int) -> Any:
        session = pg_sessions()
        try:
            resolver = ScopeResolver(session)
            scope = resolver.study_context(
                AuthenticatedPrincipal(
                    user_id=world["users"]["other_lead"],
                    organization_id=world["organization_id"],
                ),
                study_id=world["studies"]["other_client"],
            )
            claimed = WorkflowRepository(session, scope).claim_next(worker_id="intruder")
            session.commit()
            return claimed
        finally:
            session.close()

    def poll_own_client(index: int) -> Any:
        session, repo = _repo_in_new_session(pg_sessions, world)
        try:
            claimed = repo.claim_next(worker_id=f"legit-{index}")
            session.commit()
            return claimed
        finally:
            session.close()

    def work(index: int) -> tuple[str, Any]:
        if index % 2 == 0:
            return ("other", poll_other_client(index))
        return ("own", poll_own_client(index))

    results = _run_concurrently(8, work)

    intruder_results = [claimed for label, claimed in results if label == "other"]
    assert all(claimed is None for claimed in intruder_results), (
        "another client's worker must never receive this study's work"
    )
    assert any(claimed is not None for label, claimed in results if label == "own")


# --------------------------------------------------------------------------- #
# Run-level derivation under concurrent step transitions (W8)
# --------------------------------------------------------------------------- #


def _create_run(
    pg_sessions: sessionmaker[Session],
    world: dict[str, Any],
    steps: list[StepDefinition],
    key: str,
) -> str:
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        run_id = repo.create_run(
            project_id=world["project_id"],
            project_revision=1,
            workflow_type=key,
            steps=steps,
            idempotency_key=key,
        )
        session.commit()
        return run_id
    finally:
        session.close()


def _claim_all(pg_sessions: sessionmaker[Session], world: dict[str, Any], run_id: str) -> list[Any]:
    """Claim every currently runnable step of one run, one worker each."""
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        claims = []
        while (work := repo.claim_next(worker_id=f"w{len(claims)}")) is not None:
            if work.run_id == run_id:
                claims.append(work)
        session.commit()
        return claims
    finally:
        session.close()


def _complete_interleaved(
    pg_sessions: sessionmaker[Session], world: dict[str, Any], first: Any, second: Any
) -> None:
    """Complete two attempts in overlapping transactions, the first committing last-but-one.

    ``first`` completes and holds its transaction open; ``second`` completes on
    another thread; then ``first`` commits, then ``second``. Without serialisation
    the second transaction derives everything from a snapshot in which the first
    step is still RUNNING.
    """
    s1, r1 = _repo_in_new_session(pg_sessions, world)
    s2, r2 = _repo_in_new_session(pg_sessions, world)
    try:
        r1.complete_attempt(first.attempt_id, worker_id=first.worker_id)

        done = threading.Event()

        def complete_second() -> None:
            r2.complete_attempt(second.attempt_id, worker_id=second.worker_id)
            done.set()

        thread = threading.Thread(target=complete_second)
        thread.start()
        # Long enough for the second completion to finish if nothing makes it
        # wait; it is a bound, not a measurement.
        done.wait(1.0)
        s1.commit()
        thread.join(30)
        assert not thread.is_alive()
        s2.commit()
    finally:
        s1.close()
        s2.close()


def test_regression_the_last_two_steps_finishing_together_complete_the_run(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**W8.** Two workers finish a run's last two steps at the same moment.

    Each transaction derived the run's status from a snapshot in which the
    *other* step was still RUNNING, so each wrote RUNNING -- which, since the
    derivation writes only on change, meant neither wrote anything -- and the run
    read RUNNING forever with every step SUCCEEDED.
    """
    run_id = _create_run(
        pg_sessions, world, [StepDefinition(node_key=k, kind="k", priority=99) for k in "ab"], "w8"
    )
    first, second = _claim_all(pg_sessions, world, run_id)[:2]

    _complete_interleaved(pg_sessions, world, first, second)

    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        run = repo.get_run(run_id)
        assert [s["status"] for s in run["steps"]] == [StepRunStatus.SUCCEEDED] * 2
        assert run["status"] is WorkflowRunStatus.COMPLETED
    finally:
        session.close()


def test_regression_a_join_step_is_released_when_both_parents_finish_together(
    pg_sessions: sessionmaker[Session], world: dict[str, Any]
) -> None:
    """**W8, the worse half.** A diamond: ``root → (left, right) → join``.

    ``left`` and ``right`` finish concurrently; each saw the other RUNNING, so
    neither released ``join``, and the pipeline stalled with nothing runnable.
    """
    steps = [
        StepDefinition(node_key="root", kind="k", priority=99),
        StepDefinition(node_key="left", kind="k", depends_on=("root",), priority=99),
        StepDefinition(node_key="right", kind="k", depends_on=("root",), priority=99),
        StepDefinition(node_key="join", kind="k", depends_on=("left", "right"), priority=99),
    ]
    run_id = _create_run(pg_sessions, world, steps, "w8-diamond")
    [root] = _claim_all(pg_sessions, world, run_id)
    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        repo.complete_attempt(root.attempt_id, worker_id=root.worker_id)
        session.commit()
    finally:
        session.close()
    left, right = _claim_all(pg_sessions, world, run_id)

    _complete_interleaved(pg_sessions, world, left, right)

    session, repo = _repo_in_new_session(pg_sessions, world)
    try:
        statuses = {s["node_key"]: s["status"] for s in repo.get_run(run_id)["steps"]}
        assert statuses["join"] is StepRunStatus.RUNNABLE, statuses
    finally:
        session.close()


# Population promotion under contention
# --------------------------------------------------------------------------- #


def test_concurrent_live_promotions_have_exactly_one_winner(
    pg_sessions: sessionmaker[Session], synthetic_population: Any
) -> None:
    """Eight operators promote the LIVE population at once, all from the same version.

    Every one of them passed the domain check against the same snapshot. The
    row lock plus the compare-and-set update must still let exactly one through;
    the rest see ``PromotionConflict`` and change nothing.
    """
    from aia_core.application.population import PopulationRuntime
    from aia_core.domain.population import PopulationKind, PromotionConflict, VersionStatus

    pop = synthetic_population
    workers = 8

    def runtime(session: Session) -> PopulationRuntime:
        return PopulationRuntime(session, contract=pop.contract, source=pop.source)

    with pg_sessions() as setup:
        rt = runtime(setup)
        versions = {}
        for label in ("v1_BASE", "v1_1", "v1_4"):
            versions[label] = rt.import_version(
                label=label,
                panel_location=pop.location(label),
                dictionary_location=pop.dictionary_location,
                provenance="synthetic",
                imported_by="importer",
            )
        candidates = []
        for i in range(workers):
            location = f"panels/candidate_{i}.csv.gz"
            pop.source.put(
                location,
                pop.rebuild("v1_4", lambda rows, i=i: rows[0].update(segment=f"candidate-{i}")),
            )
            candidates.append(
                rt.import_version(
                    label=f"candidate_{i}",
                    panel_location=location,
                    dictionary_location=pop.dictionary_location,
                    provenance="synthetic",
                    imported_by="importer",
                    parent_version_id=versions["v1_4"].version_id,
                ).version_id
            )
        rt.establish(
            population_id="SYN_STATIC",
            kind=PopulationKind.STATIC,
            version_id=versions["v1_1"].version_id,
            actor_id="owner",
            reason="establish",
        )
        rt.establish(
            population_id="SYN_LIVE",
            kind=PopulationKind.LIVE,
            version_id=versions["v1_4"].version_id,
            actor_id="owner",
            reason="establish",
        )
        setup.commit()

    barrier = threading.Barrier(workers)
    expected = versions["v1_4"].version_id

    def promote(target: str) -> str:
        with pg_sessions() as session:
            barrier.wait(timeout=30)
            try:
                runtime(session).promote_live(
                    population_id="SYN_LIVE",
                    target_version_id=target,
                    expected_current_version_id=expected,
                    actor_id="operator",
                    reason="race",
                )
                session.commit()
                return "won"
            except PromotionConflict:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(promote, candidates))

    assert outcomes.count("won") == 1
    assert outcomes.count("conflict") == workers - 1
    with pg_sessions() as check:
        rt = runtime(check)
        winner = candidates[outcomes.index("won")]
        assert rt.version_status(winner) is VersionStatus.LIVE_CURRENT
        assert rt.version_status(expected) is VersionStatus.SUPERSEDED
        losers = [c for c in candidates if c != winner]
        assert all(rt.version_status(c) is VersionStatus.REGISTERED for c in losers)
