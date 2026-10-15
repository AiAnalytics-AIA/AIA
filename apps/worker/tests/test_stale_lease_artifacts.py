"""A worker that outlives its lease, against real PostgreSQL: what it can still write.

The B-then-A case. Worker A claims a step and stalls; its lease lapses; a reconciler
marks A's attempt ``EXPIRED``; worker B claims the step, writes an artifact and
completes. Then A -- its process still alive -- tries to carry on: open
``context.transaction()``, store an artifact, complete.

The fence is ``AttemptContext.transaction()``: it takes the attempt's row lock and
checks the lease before the executor's block runs, and holds the lock to commit.
These tests pin three things about it, each on the persisted state and the store's
contents rather than on what a worker reports:

* a stale A is refused before its block runs, so no object reaches the store and
  B's result and artifact are untouched;
* an A that opened the fence while it still held the lease keeps the reconciler
  off the attempt until it commits or rolls back -- and when its block fails after
  the upload, the object stays in the store with no row (the orphan);
* an A whose artifact committed before the lease lapsed leaves a row a successor
  reuses by fingerprint.

**PostgreSQL only.** The behaviour is the row lock and ``SKIP LOCKED``; SQLite has
neither (``AGENTS.md`` § SQLAlchemy). The module skips without PostgreSQL, and
fails instead when ``AIA_REQUIRE_POSTGRES=1``.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import pytest
from aia_core.application.scope import ScopeResolver
from aia_core.domain.scope import StudyContext, WorkScope
from aia_core.domain.workflow import AttemptStatus, StepRunStatus
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import ProjectArtifactRow, StepAttemptRow
from aia_core.infrastructure.workflow_repository import ClaimedWork, LeaseLost, WorkQueue
from aia_worker.context import AttemptContext, AttemptSignals, in_transaction
from aia_worker.executor import LeaseRevoked, StepInput
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.postgres

FINGERPRINT = "fp-b-then-a"


@pytest.fixture(autouse=True)
def _require_postgres(database_url: str) -> None:
    if not database_url.startswith("postgresql"):
        message = "stale-lease tests need PostgreSQL; set DATABASE_URL to a postgresql:// URL"
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)


class _Worker:
    """One claimed attempt, driven by hand: the claim, its scope and its context."""

    def __init__(self, sessions: sessionmaker[Session], worker_id: str) -> None:
        self.worker_id = worker_id
        self.signals = AttemptSignals(stopping=threading.Event())
        with sessions() as session:
            work = WorkQueue(session).claim_next(worker_id=worker_id, kinds=None)
            assert work is not None, f"{worker_id} found nothing to claim"
            scope = ScopeResolver(session).execution_context(
                attempt_id=work.attempt_id, worker_id=worker_id
            )
            session.commit()
        self.work: ClaimedWork = work
        self.scope: WorkScope = scope
        self._sessions = sessions
        self.context = AttemptContext(
            session_factory=sessions,
            scope=scope,
            step=StepInput(
                run_id=work.run_id,
                step_id=work.step_id,
                attempt_id=work.attempt_id,
                attempt_number=work.attempt_number,
                node_key=work.node_key,
                kind=work.kind,
                stage_type=work.stage_type,
                artifact_target=work.artifact_target,
                input_fingerprint=work.input_fingerprint,
                interaction_mode=work.interaction_mode,
                payload=dict(work.payload),
                project_id=work.project_id,
                project_revision=work.project_revision,
            ),
            worker_id=worker_id,
            signals=self.signals,
        )

    def put(
        self, artifacts: ArtifactRepository, payload: dict[str, Any], *, reuse: bool = True
    ) -> tuple[str, bool]:
        """Store ``payload`` the way an executor does. Returns ``(artifact_id, created)``."""
        artifact, created = artifacts.put_json(
            payload=payload,
            project_id=self.work.project_id,
            revision=self.work.project_revision,
            stage_type=self.work.stage_type,
            artifact_type="b_then_a",
            input_fingerprint=FINGERPRINT,
            produced_by_job_id=self.work.attempt_id,
            reuse=reuse,
        )
        return artifact.artifact_id, created

    def complete(self, output: dict[str, Any]) -> None:
        """Record success the way the worker loop does: one fenced short write."""
        in_transaction(
            self._sessions,
            self.scope,
            lambda repo: repo.complete_attempt(
                self.work.attempt_id, worker_id=self.worker_id, output=output
            ),
        )


def _study_scope(worker: _Worker) -> StudyContext:
    assert isinstance(worker.scope, StudyContext)
    return worker.scope


def _lapse(sessions: sessionmaker[Session], attempt_id: str) -> None:
    """Move one attempt's lease deadline into the past. Recovery is a separate step."""
    with sessions() as session:
        session.execute(
            update(StepAttemptRow)
            .where(StepAttemptRow.attempt_id == attempt_id)
            .values(lease_until=StepAttemptRow.started_at)
        )
        session.commit()


def _recover(sessions: sessionmaker[Session]) -> int:
    """Run one reconciler sweep on its own connection. Returns the decisions applied."""
    with sessions() as session:
        decisions = WorkQueue(session).recover_expired_attempts()
        session.commit()
    return len(decisions)


def _lapse_and_recover(sessions: sessionmaker[Session], attempt_id: str) -> int:
    _lapse(sessions, attempt_id)
    return _recover(sessions)


def _artifact_rows(sessions: sessionmaker[Session]) -> list[tuple[str, str, str | None]]:
    """Every artifact row as ``(artifact_id, storage_key, produced_by_job_id)``."""
    with sessions() as session:
        return [
            (row.artifact_id, row.storage_key, row.produced_by_job_id)
            for row in session.scalars(
                select(ProjectArtifactRow).order_by(ProjectArtifactRow.artifact_id)
            )
        ]


def _attempts(sessions: sessionmaker[Session], step_id: str) -> list[tuple[str, str]]:
    with sessions() as session:
        return [
            (row.worker_id or "", row.status)
            for row in session.scalars(
                select(StepAttemptRow)
                .where(StepAttemptRow.step_id == step_id)
                .order_by(StepAttemptRow.attempt_number)
            )
        ]


def test_a_stale_worker_is_refused_before_it_reaches_the_store(
    study: Any, sessions: sessionmaker[Session]
) -> None:
    """B finished the step; A wakes up and tries to store and complete. Nothing lands.

    The refusal comes from ``assert_lease`` at the top of ``transaction()``, before
    the executor's block runs, so ``store.put`` is never reached: the store holds
    B's object and nothing else, and B's row, bytes and output are as B left them.
    """
    run_id = study.create_run({}, key="stale-refused")
    store = InMemoryArtifactStore()

    stale = _Worker(sessions, "worker-a")
    assert _lapse_and_recover(sessions, stale.work.attempt_id) == 1

    successor = _Worker(sessions, "worker-b")
    assert successor.work.step_id == stale.work.step_id
    with successor.context.transaction() as (session, _workflow):
        b_artifact, created = successor.put(
            ArtifactRepository(session, _study_scope(successor), store), {"by": "B"}
        )
    assert created
    successor.complete({"artifact_id": b_artifact})

    rows_before = _artifact_rows(sessions)
    keys_before = store.keys
    b_bytes = store.get(rows_before[0][1])

    entered = False
    with (
        pytest.raises(LeaseRevoked) as refused,
        stale.context.transaction() as (session, _workflow),
    ):
        entered = True
        stale.put(ArtifactRepository(session, _study_scope(stale), store), {"by": "A"})
    assert isinstance(refused.value.__cause__, LeaseLost)
    assert refused.value.__cause__.owner == "worker-a"
    assert refused.value.__cause__.status == AttemptStatus.EXPIRED.value
    assert not entered, "the executor's block ran under a lost lease"
    assert stale.signals.lease_lost.is_set()
    with pytest.raises(LeaseRevoked):
        stale.context.checkpoint()

    with pytest.raises(LeaseLost):
        stale.complete({"artifact_id": "ART-from-a"})

    assert store.keys == keys_before, "an object reached the store under a lost lease"
    assert store.get(rows_before[0][1]) == b_bytes
    assert _artifact_rows(sessions) == rows_before
    assert rows_before[0][2] == successor.work.attempt_id
    step = study.run(run_id)["steps"][0]
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert step["output"] == {"artifact_id": b_artifact}
    assert _attempts(sessions, stale.work.step_id) == [
        ("worker-a", AttemptStatus.EXPIRED.value),
        ("worker-b", AttemptStatus.SUCCEEDED.value),
    ]


def test_a_put_inside_the_fence_holds_off_recovery_and_a_failed_block_orphans_its_object(
    study: Any, sessions: sessionmaker[Session]
) -> None:
    """A is inside ``transaction()`` and has uploaded when its lease deadline passes.

    Two observations, pinned:

    1. **The fence holds recovery off.** While A's transaction holds the attempt's
       row lock, a reconciler sweep skips the attempt (``SKIP LOCKED``) and B finds
       nothing to claim. A lapsed deadline alone does not let B in; only a sweep
       that runs after A's transaction ends does. So "A's put before B completes"
       can happen only in a transaction that began while A held the lease, and B
       cannot even claim until that transaction is over.
    2. **A failed block orphans the object.** ``ArtifactRepository.put`` uploads
       before it adds the row. When A's block then raises, the row rolls back and
       the object stays in the store, referenced by no row. Nothing reaps it: B's
       run completes normally and the orphan is still there afterwards.
    """
    run_id = study.create_run({}, key="orphan")
    store = InMemoryArtifactStore()

    stale = _Worker(sessions, "worker-a")
    # The deadline passes before A opens the fence; no sweep has run yet, so the
    # attempt is still A's (the deadline triggers recovery, it is not the fence).
    _lapse(sessions, stale.work.attempt_id)
    orphan_key: str | None = None

    class _ExecutorFailed(RuntimeError):
        pass

    with (
        pytest.raises(_ExecutorFailed),
        stale.context.transaction() as (session, _workflow),
    ):
        stale.put(ArtifactRepository(session, _study_scope(stale), store), {"by": "A"})
        [orphan_key] = store.keys

        assert _recover(sessions) == 0, (
            "a reconciler recovered an attempt whose holder is mid-transaction"
        )
        with sessions() as other:
            assert WorkQueue(other).claim_next(worker_id="worker-b", kinds=None) is None
            other.commit()
        raise _ExecutorFailed("A fails after its upload, before commit")

    assert orphan_key is not None
    assert _artifact_rows(sessions) == [], "the row rolled back with A's transaction"
    assert store.keys == [orphan_key], "the uploaded object outlived its rollback"

    # The lock is gone with A's transaction; the next sweep takes the lapsed attempt.
    assert _recover(sessions) == 1
    successor = _Worker(sessions, "worker-b")
    with successor.context.transaction() as (session, _workflow):
        b_artifact, created = successor.put(
            ArtifactRepository(session, _study_scope(successor), store), {"by": "B"}
        )
    assert created
    successor.complete({"artifact_id": b_artifact})

    [(row_id, b_key, produced_by)] = _artifact_rows(sessions)
    assert (row_id, produced_by) == (b_artifact, successor.work.attempt_id)
    assert b_key != orphan_key
    assert store.keys == sorted([orphan_key, b_key]), (
        "the orphan is still in the store after the step completed: nothing reaps it"
    )
    step = study.run(run_id)["steps"][0]
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert step["output"] == {"artifact_id": b_artifact}


def test_an_artifact_committed_before_the_lease_lapsed_is_reused_by_the_successor(
    study: Any, sessions: sessionmaker[Session]
) -> None:
    """A stores and commits under its lease, then loses the lease before completing.

    The artifact row is legitimate -- the lease was held at commit -- and survives
    A's recovery; A's completion is refused. B, putting with the same fingerprint,
    gets A's artifact back (``created`` is false) and uploads nothing, so the step
    B completes cites an artifact whose ``produced_by_job_id`` is A's expired
    attempt. Reuse by fingerprint is designed (``ArtifactRepository.put``); this pins
    that it reaches across a lost lease.
    """
    run_id = study.create_run({}, key="committed-then-lost")
    store = InMemoryArtifactStore()

    stale = _Worker(sessions, "worker-a")
    with stale.context.transaction() as (session, _workflow):
        a_artifact, created = stale.put(
            ArtifactRepository(session, _study_scope(stale), store), {"by": "A"}
        )
    assert created
    assert _lapse_and_recover(sessions, stale.work.attempt_id) == 1
    with pytest.raises(LeaseLost):
        stale.complete({"artifact_id": a_artifact})

    successor = _Worker(sessions, "worker-b")
    keys_before = store.keys
    with successor.context.transaction() as (session, _workflow):
        b_artifact, created = successor.put(
            ArtifactRepository(session, _study_scope(successor), store), {"by": "B"}
        )
    assert not created
    assert b_artifact == a_artifact
    assert store.keys == keys_before, "a reused artifact uploads nothing"
    successor.complete({"artifact_id": b_artifact})

    [(_, _, produced_by)] = _artifact_rows(sessions)
    assert produced_by == stale.work.attempt_id
    step = study.run(run_id)["steps"][0]
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert step["output"] == {"artifact_id": a_artifact}
    assert _attempts(sessions, stale.work.step_id) == [
        ("worker-a", AttemptStatus.EXPIRED.value),
        ("worker-b", AttemptStatus.SUCCEEDED.value),
    ]
