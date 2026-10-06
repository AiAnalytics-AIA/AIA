"""The state every worker process shares when Deep Research fans out (chunk 21).

``docs/architecture/deep-research-fan-out.md`` §§ 3-4:

* :class:`SharedHostPacer` -- one request at a time per host, the next no sooner than
  the last one's end plus its interval, refused unsent past its wait; a dead holder
  lapses.
* :class:`ModelSlots` -- at most ``limit`` requests of a pool in flight; a slot expires
  with its holder attempt's lease; a lower limit holds at once; a wait is bounded and
  checkpointed.

Each rule is first checked deterministically on a file-backed SQLite database (a fake
clock: no sleeping); then the contention tests run real threads on separate connections
against PostgreSQL -- marked ``postgres``, skipped without it and failed instead when
``AIA_REQUIRE_POSTGRES=1`` (SQLite is single-writer and cannot show contention).
"""

from __future__ import annotations

import itertools
import os
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from aia_core.domain.deep_research.web import FetchRefused
from aia_core.domain.workflow import AttemptStatus, StepDefinition
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.fan_out_coordination import (
    ModelSlots,
    ModelSlotsBusy,
    SharedHostPacer,
)
from aia_core.infrastructure.host_pacing import HOST_WAIT_EXCEEDED
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import (
    Base,
    HostPolitenessRow,
    ModelConcurrencySlotRow,
    StepAttemptRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository

T0 = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


@dataclass
class FakeTime:
    """One clock for the UTC instants and the monotonic waits; sleeping advances it."""

    now: datetime = T0
    slept: list[float] = field(default_factory=list)

    def clock(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return (self.now - T0).total_seconds()

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def sqlite_sessions(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_app_engine(f"sqlite+pysqlite:///{tmp_path / 'coordination.db'}")
    Base.metadata.create_all(engine)
    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def _attempts(sessions: sessionmaker[Session], scope_builder: Any, n: int) -> list[str]:
    """``n`` live attempts (claimed, leased for five minutes), committed."""
    with sessions() as session:
        scope = scope_builder(session).scope(user="lead", study="primary")
        project, _ = ProjectRepository(session, scope).create(title="Slot holders")
        repo = WorkflowRepository(session, scope)
        repo.create_run(
            project_id=project.project_id,
            project_revision=1,
            workflow_type="holders",
            steps=[StepDefinition(node_key=f"h{i}", kind="h") for i in range(n)],
            idempotency_key="holders",
        )
        ids = []
        for _ in range(n):
            work = repo.claim_next(worker_id="w", lease_seconds=300)
            assert work is not None
            ids.append(work.attempt_id)
        session.commit()
        return ids


def _expire(sessions: sessionmaker[Session], attempt_id: str) -> None:
    """The holder's lease lapsed (its worker was killed): what the reconciler would see."""
    with sessions() as session:
        session.execute(
            update(StepAttemptRow)
            .where(StepAttemptRow.attempt_id == attempt_id)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        session.commit()


# --------------------------------------------------------------------------- #
# Hosts, deterministically
# --------------------------------------------------------------------------- #


def _pacer(sessions: sessionmaker[Session], fake: FakeTime, **kwargs: Any) -> SharedHostPacer:
    return SharedHostPacer(
        sessions, clock=fake.clock, monotonic=fake.monotonic, sleep=fake.sleep, **kwargs
    )


def test_the_next_request_starts_an_interval_after_the_last_one_ended(
    sqlite_sessions: sessionmaker[Session],
) -> None:
    fake = FakeTime()
    pacer = _pacer(sqlite_sessions, fake)
    starts: list[float] = []
    for _ in range(3):
        with pacer.turn("stats.example", 2.0):
            starts.append(fake.monotonic())
            fake.advance(0.5)  # the request takes half a second

    assert starts == [0.0, 2.5, 5.0], "end of the last + 2 s"
    assert fake.slept == [2.0, 2.0]


def test_hosts_are_paced_apart(sqlite_sessions: sessionmaker[Session]) -> None:
    fake = FakeTime()
    pacer = _pacer(sqlite_sessions, fake)
    with pacer.turn("a.example", 5.0):
        pass
    with pacer.turn("b.example", 5.0):
        pass
    assert fake.slept == [], "another host owes nothing to this one"


def test_two_pacers_share_one_host_through_the_database(
    sqlite_sessions: sessionmaker[Session],
) -> None:
    """Two processes' pacers: the second waits for the first's interval."""
    fake = FakeTime()
    first, second = _pacer(sqlite_sessions, fake), _pacer(sqlite_sessions, fake)
    with first.turn("stats.example", 3.0):
        fake.advance(1.0)
    with second.turn("stats.example", 3.0):
        started = fake.monotonic()
    assert started == pytest.approx(4.0)


def test_a_host_held_by_another_request_is_waited_for(
    sqlite_sessions: sessionmaker[Session],
) -> None:
    fake = FakeTime()
    holder, waiter = _pacer(sqlite_sessions, fake), _pacer(sqlite_sessions, fake, poll_s=0.25)
    turn = holder.turn("stats.example", 1.0)
    turn.__enter__()  # in flight in "another process"
    calls = 0
    real_sleep = fake.sleep

    def sleep_then_release(seconds: float) -> None:
        nonlocal calls
        calls += 1
        real_sleep(seconds)
        if calls == 4:
            turn.__exit__(None, None, None)  # the holder's request ends

    waiter._sleep = sleep_then_release
    with waiter.turn("stats.example", 1.0):
        started = fake.monotonic()

    assert fake.slept[:4] == [0.25] * 4, "polled while the host was in flight"
    assert started == pytest.approx(2.0), "then its interval after the holder's end"


def test_a_turn_that_would_come_too_late_is_refused_before_anything_is_sent(
    sqlite_sessions: sessionmaker[Session],
) -> None:
    fake = FakeTime()
    pacer = _pacer(sqlite_sessions, fake, max_wait_s=10.0)
    with pacer.turn("slow.example", 30.0):
        pass
    sent = []
    with pytest.raises(FetchRefused) as refused, pacer.turn("slow.example", 30.0):
        sent.append("request")
    assert refused.value.reason == HOST_WAIT_EXCEEDED
    assert sent == [] and fake.slept == [], "refused at once: waiting would not help"


def test_a_dead_holder_lapses_after_its_hold(sqlite_sessions: sessionmaker[Session]) -> None:
    fake = FakeTime()
    dead, live = (
        _pacer(sqlite_sessions, fake, hold_s=20.0),
        _pacer(sqlite_sessions, fake, poll_s=5.0),
    )
    # Its process dies in flight: never released. (Held in a name: a dropped context
    # manager is closed by the garbage collector, which would release it.)
    in_flight = dead.turn("stats.example", 1.0)
    in_flight.__enter__()
    with live.turn("stats.example", 1.0):
        started = fake.monotonic()
    assert started == pytest.approx(20.0), "free once the hold lapsed"
    assert in_flight is not None


def test_idle_host_rows_are_pruned(sqlite_sessions: sessionmaker[Session]) -> None:
    fake = FakeTime()
    pacer = _pacer(sqlite_sessions, fake)
    with pacer.turn("old.example", 1.0):
        pass
    fake.advance(2 * 86_400)
    fresh = _pacer(sqlite_sessions, fake)  # its first take prunes
    with fresh.turn("new.example", 1.0):
        pass
    with sqlite_sessions() as session:
        hosts = set(session.scalars(select(HostPolitenessRow.host)).all())
    assert hosts == {"new.example"}


def test_a_negative_interval_is_refused(sqlite_sessions: sessionmaker[Session]) -> None:
    pacer = _pacer(sqlite_sessions, FakeTime())
    with pytest.raises(ValueError, match="not negative"), pacer.turn("a.example", -1.0):
        pass


# --------------------------------------------------------------------------- #
# Model slots, deterministically
# --------------------------------------------------------------------------- #


def _slots(
    sessions: sessionmaker[Session], fake: FakeTime | None = None, **kwargs: Any
) -> ModelSlots:
    timing: dict[str, Any] = (
        {"clock": lambda: datetime.now(UTC), "monotonic": fake.monotonic, "sleep": fake.sleep}
        if fake is not None
        else {}
    )
    return ModelSlots(sessions, pool="bedrock:test", **{**timing, **kwargs})


def test_at_most_limit_slots_are_held_and_a_release_frees_one(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    a, b, c = _attempts(sqlite_sessions, scope_builder, 3)
    fake = FakeTime()
    slots = _slots(sqlite_sessions, fake, limit=2, max_wait_s=1.0, poll_s=0.5)

    with slots.hold(holder_attempt_id=a) as first, slots.hold(holder_attempt_id=b) as second:
        assert {first, second} == {0, 1}
        assert slots.in_flight() == 2
        checkpoints = []
        waiting = slots.hold(holder_attempt_id=c, checkpoint=lambda: checkpoints.append(1))
        with pytest.raises(ModelSlotsBusy), waiting:
            pass
        assert checkpoints and fake.slept, "it waited, checkpointing, before giving up"
    with slots.hold(holder_attempt_id=c) as third:
        assert third == 0
    assert slots.in_flight() == 0


def test_a_slot_expires_with_its_holder_attempts_lease(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    killed, survivor = _attempts(sqlite_sessions, scope_builder, 2)
    slots = _slots(sqlite_sessions, limit=1, max_wait_s=0.0)
    orphan = slots.hold(holder_attempt_id=killed)
    orphan.__enter__()  # its worker is killed mid-call: never released

    with pytest.raises(ModelSlotsBusy), slots.hold(holder_attempt_id=survivor):
        pass
    _expire(sqlite_sessions, killed)
    with slots.hold(holder_attempt_id=survivor) as slot:
        assert slot == 0, "the dead attempt's slot came back with its lease"
    assert orphan is not None


def test_a_finished_holders_slot_is_free_too(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    done, next_ = _attempts(sqlite_sessions, scope_builder, 2)
    slots = _slots(sqlite_sessions, limit=1, max_wait_s=0.0)
    never_released = slots.hold(holder_attempt_id=done)
    never_released.__enter__()
    with pytest.raises(ModelSlotsBusy), slots.hold(holder_attempt_id=next_):
        pass
    with sqlite_sessions() as session:
        session.execute(
            update(StepAttemptRow)
            .where(StepAttemptRow.attempt_id == done)
            .values(status=AttemptStatus.SUCCEEDED.value)
        )
        session.commit()
    with slots.hold(holder_attempt_id=next_):
        pass
    assert never_released is not None


def test_a_lower_limit_holds_at_once(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    a, b = _attempts(sqlite_sessions, scope_builder, 2)
    with _slots(sqlite_sessions, limit=3).hold(holder_attempt_id=a):
        pass
    lowered = _slots(sqlite_sessions, limit=1, max_wait_s=0.0)
    with (
        lowered.hold(holder_attempt_id=a),
        pytest.raises(ModelSlotsBusy),
        lowered.hold(holder_attempt_id=b),
    ):
        pass
    with sqlite_sessions() as session:
        assert session.scalars(select(ModelConcurrencySlotRow.slot)).all() == [0, 1, 2]


def test_one_attempt_may_hold_several_slots(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    """A triage burst: one attempt, several requests in flight, each its own slot."""
    (attempt,) = _attempts(sqlite_sessions, scope_builder, 1)
    slots = _slots(sqlite_sessions, limit=2, max_wait_s=0.0)
    with (
        slots.hold(holder_attempt_id=attempt),
        slots.hold(holder_attempt_id=attempt),
        pytest.raises(ModelSlotsBusy),
        slots.hold(holder_attempt_id=attempt),
    ):
        pass


def test_a_stop_while_waiting_holds_nothing(
    sqlite_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    a, b = _attempts(sqlite_sessions, scope_builder, 2)
    slots = _slots(sqlite_sessions, FakeTime(), limit=1, max_wait_s=60.0)

    class Stop(BaseException):
        pass

    def stop() -> None:
        raise Stop

    with slots.hold(holder_attempt_id=a):
        with pytest.raises(Stop), slots.hold(holder_attempt_id=b, checkpoint=stop):
            pass
        assert slots.in_flight() == 1


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"limit": 0}, "between 1 and 256"),
        ({"limit": 257}, "between 1 and 256"),
        ({"limit": 1, "pool": ""}, "named"),
        ({"limit": 1, "poll_s": 0}, "positive"),
    ],
)
def test_a_pool_is_configured_within_bounds(
    sqlite_sessions: sessionmaker[Session], kwargs: dict[str, Any], message: str
) -> None:
    options = {"pool": "bedrock:test", **kwargs}
    with pytest.raises(ValueError, match=message):
        ModelSlots(sqlite_sessions, **options)


# --------------------------------------------------------------------------- #
# Contention, on PostgreSQL
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def pg_engine() -> Iterator[Engine]:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        message = "contention needs PostgreSQL: set DATABASE_URL to a postgresql:// URL"
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)
    engine = create_app_engine(url, pool_size=20, max_overflow=10)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_sessions(pg_engine: Engine) -> Iterator[sessionmaker[Session]]:
    factory = create_session_factory(pg_engine)

    def truncate() -> None:
        with factory() as session:
            for table in reversed(Base.metadata.sorted_tables):
                session.execute(table.delete())
            session.commit()

    truncate()
    try:
        yield factory
    finally:
        truncate()


@pytest.mark.postgres
def test_eight_threads_never_hold_more_slots_than_the_limit(
    pg_sessions: sessionmaker[Session], scope_builder: Any
) -> None:
    holders = _attempts(pg_sessions, scope_builder, 8)
    slots = ModelSlots(pg_sessions, pool="bedrock:contention", limit=3, poll_s=0.005)
    guard = threading.Lock()
    in_flight, peak, done = 0, 0, 0

    def work(attempt_id: str) -> None:
        nonlocal in_flight, peak, done
        for _ in range(5):
            with slots.hold(holder_attempt_id=attempt_id):
                with guard:
                    in_flight += 1
                    peak = max(peak, in_flight)
                time.sleep(0.01)
                with guard:
                    in_flight -= 1
                    done += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, holders))

    assert done == 40
    assert peak == 3, f"the limit was reached and never passed (peak {peak})"
    assert slots.in_flight() == 0


@pytest.mark.postgres
def test_six_threads_on_one_host_never_overlap_and_keep_its_interval(
    pg_sessions: sessionmaker[Session],
) -> None:
    pacer = SharedHostPacer(pg_sessions, poll_s=0.002)
    interval = 0.03
    guard = threading.Lock()
    spans: list[tuple[float, float]] = []

    def work(_: int) -> None:
        for _ in range(4):
            with pacer.turn("stats.example", interval):
                start = time.monotonic()
                time.sleep(0.005)
                end = time.monotonic()
            with guard:
                spans.append((start, end))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(work, range(6)))

    spans.sort()
    assert len(spans) == 24
    gaps = [b[0] - a[1] for a, b in itertools.pairwise(spans)]
    assert min(gaps) >= interval * 0.95, f"a request started {min(gaps):.4f} s after the last"
