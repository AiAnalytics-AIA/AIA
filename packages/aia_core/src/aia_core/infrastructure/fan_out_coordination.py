"""What every worker process of a deployment shares when Deep Research fans out.

Plan ``deep-research-web-search.md`` chunk 21; ``docs/architecture/deep-research-fan-out.md``
§§ 3-4. ADR 0002 keeps shared state in PostgreSQL, so both pieces are rows, each written
in a short transaction of its own -- never inside an attempt's fenced unit of work, and
never across a network call:

* :class:`SharedHostPacer` -- a :class:`~aia_core.infrastructure.host_pacing.HostPacer`
  over ``host_politeness``: one request at a time per host, the next starting no
  sooner than the last one's end plus the interval the host is owed, for every
  process at once.
* :class:`ModelSlots` -- a counting semaphore over ``model_concurrency_slots``: at most
  ``limit`` model requests of one pool in flight across every process. A slot expires
  with the lease of the attempt that took it.

Both are correct on either engine through conditional ``UPDATE`` statements checked by
their row counts (``AGENTS.md`` § SQLAlchemy: the condition is in the statement); on
PostgreSQL the reads also lock (``FOR UPDATE``), so concurrent takers queue on the row
instead of racing it. SQLite is single-writer: there the same statements serialise,
which is what the offline path needs and all it can prove.

Instants come from the injected UTC clock of each process, not the database's: the
interval a host is owed is measured where the request is sent. On develop every
worker runs on one host, so the clocks are one clock.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from ..domain.deep_research.web import FetchRefused
from ..domain.workflow import AttemptStatus, as_utc
from .host_pacing import HOST_WAIT_EXCEEDED
from .tables import HostPolitenessRow, ModelConcurrencySlotRow, StepAttemptRow

__all__ = [
    "HOST_HOLD_SECONDS",
    "HOST_MAX_WAIT_SECONDS",
    "MODEL_SLOT_MAX_WAIT_SECONDS",
    "ModelSlots",
    "ModelSlotsBusy",
    "SharedHostPacer",
]

#: The longest a request waits for its host's turn before it is refused unsent:
#: twice the longest crawl delay a public transport accepts (``max_crawl_delay_s``).
HOST_MAX_WAIT_SECONDS: Final = 60.0
#: How long a host stays held by a request whose process died before releasing it:
#: above the public transport's connect (8 s) and read (20 s per read) timeouts.
HOST_HOLD_SECONDS: Final = 120.0
#: How long a model request waits for a slot before its step parks WAITING_CAPACITY.
MODEL_SLOT_MAX_WAIT_SECONDS: Final = 120.0
#: Rows of hosts nobody has requested for this long are pruned when a turn is taken.
_HOST_IDLE_PRUNE: Final = timedelta(days=1)
#: A process prunes on one take in this many (and on its first).
_PRUNE_EVERY: Final = 500

_LIVE: Final = (AttemptStatus.CLAIMED.value, AttemptStatus.EXECUTING.value)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _rowcount(result: Any) -> int:
    return int(cast(CursorResult[Any], result).rowcount)


def _is_postgres(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _insert_ignore(session: Session, table: Any, rows: list[dict[str, Any]]) -> None:
    """Insert rows, leaving any that already exist (a concurrent insert included)."""
    if not rows:
        return
    statement = (pg_insert if _is_postgres(session) else sqlite_insert)(table).values(rows)
    session.execute(statement.on_conflict_do_nothing())


# --------------------------------------------------------------------------- #
# Hosts
# --------------------------------------------------------------------------- #


class SharedHostPacer:
    """The deployment's turn per host, in ``host_politeness`` (see the module docstring).

    A turn: take the host (a short transaction), send outside any transaction, release
    it with ``next_allowed_at = end + interval`` (another). While another request holds
    the host, or its interval has not passed, the taker sleeps -- the exact remainder of
    an interval, ``poll_s`` while a request is in flight -- and refuses before sending
    once the wait would pass ``max_wait_s``. Keyed by host alone: a crawl delay is owed
    by AIA's user agent, which every run shares.
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        max_wait_s: float = HOST_MAX_WAIT_SECONDS,
        hold_s: float = HOST_HOLD_SECONDS,
        poll_s: float = 0.05,
        clock: Callable[[], datetime] = _utcnow,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_wait_s < 0 or hold_s <= 0 or poll_s <= 0:
            raise ValueError("a host's wait is not negative and its hold and poll are positive")
        self._sessions = sessions
        self._max_wait_s = max_wait_s
        self._hold = timedelta(seconds=hold_s)
        self._poll_s = poll_s
        self._clock = clock
        self._monotonic = monotonic
        self._sleep = sleep
        self._takes = 0
        self._guard = threading.Lock()

    @contextmanager
    def turn(self, host: str, interval_s: float) -> Iterator[None]:
        if interval_s < 0:
            raise ValueError("a host's interval is not negative")
        token = uuid.uuid4().hex
        started = self._monotonic()
        while True:
            wait = self._take(host, token)
            if wait <= 0:
                break
            if self._monotonic() - started + wait > self._max_wait_s:
                raise FetchRefused(
                    f"{host} would not be free within {self._max_wait_s:g} s; nothing was sent",
                    reason=HOST_WAIT_EXCEEDED,
                )
            self._sleep(wait)
        try:
            yield
        finally:
            self._release(host, token, interval_s)

    def _take(self, host: str, token: str) -> float:
        """Take ``host`` for ``token`` (0.0), or the seconds to wait before asking again."""
        with self._sessions() as session:
            now = self._clock()
            self._maybe_prune(session, now)
            _insert_ignore(
                session, HostPolitenessRow.__table__, [{"host": host, "updated_at": now}]
            )
            query = (
                select(HostPolitenessRow)
                .where(HostPolitenessRow.host == host)
                .execution_options(populate_existing=True)
            )
            if _is_postgres(session):
                query = query.with_for_update()
            row = session.scalars(query).one()
            held_until = as_utc(row.held_until)
            if row.holder_token is not None and held_until is not None and held_until > now:
                session.rollback()
                return self._poll_s
            next_allowed = as_utc(row.next_allowed_at)
            if next_allowed is not None and next_allowed > now:
                session.rollback()
                return max((next_allowed - now).total_seconds(), 1e-3)
            observed = row.holder_token
            taken = session.execute(
                update(HostPolitenessRow)
                .where(
                    HostPolitenessRow.host == host,
                    HostPolitenessRow.holder_token.is_(None)
                    if observed is None
                    else HostPolitenessRow.holder_token == observed,
                )
                .values(holder_token=token, held_until=now + self._hold, updated_at=now)
                .execution_options(synchronize_session=False)
            )
            if _rowcount(taken) != 1:
                session.rollback()
                return self._poll_s
            session.commit()
            return 0.0

    def _release(self, host: str, token: str, interval_s: float) -> None:
        with self._sessions() as session:
            end = self._clock()
            session.execute(
                update(HostPolitenessRow)
                .where(HostPolitenessRow.host == host, HostPolitenessRow.holder_token == token)
                .values(
                    holder_token=None,
                    held_until=None,
                    next_allowed_at=end + timedelta(seconds=interval_s),
                    updated_at=end,
                )
                .execution_options(synchronize_session=False)
            )
            session.commit()

    def _maybe_prune(self, session: Session, now: datetime) -> None:
        with self._guard:
            due = self._takes % _PRUNE_EVERY == 0
            self._takes += 1
        if due:
            session.execute(
                delete(HostPolitenessRow).where(
                    HostPolitenessRow.updated_at < now - _HOST_IDLE_PRUNE,
                    HostPolitenessRow.holder_token.is_(None),
                )
            )


# --------------------------------------------------------------------------- #
# Model calls
# --------------------------------------------------------------------------- #


class ModelSlotsBusy(RuntimeError):
    """No slot of the pool came free within the wait: nothing was reserved or sent."""

    def __init__(self, pool: str, limit: int, waited_s: float) -> None:
        super().__init__(
            f"no model slot of {pool!r} (limit {limit}) came free in {waited_s:.1f} s; "
            "nothing was reserved or sent"
        )
        self.pool = pool
        self.limit = limit
        self.waited_s = waited_s


@dataclass(frozen=True, slots=True)
class _Held:
    slot: int
    token: str


class ModelSlots:
    """At most ``limit`` model requests of ``pool`` in flight, across every process.

    :meth:`hold` takes a slot for one logical request, in the name of the attempt
    making it (``holder_attempt_id``), and gives it back when the block ends. A slot
    is free when nobody holds it or its holder attempt no longer holds its lease --
    the one read here of ``step_attempts`` across studies, and only of liveness -- so a
    killed worker's slots come back when its step could be recovered, with no
    heartbeat of their own. Slots at or above the limit are never taken: lowering the
    limit takes effect at the next acquisition.

    The limit is configured (``AIA_DEEP_RESEARCH_MODEL_CONCURRENCY``), never defaulted:
    it must sit below the account's quota for the route's model.
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        pool: str,
        limit: int,
        max_wait_s: float = MODEL_SLOT_MAX_WAIT_SECONDS,
        poll_s: float = 0.05,
        clock: Callable[[], datetime] = _utcnow,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not pool or len(pool) > 128:
            raise ValueError("a pool is named, in at most 128 characters")
        if not 1 <= limit <= 256:
            raise ValueError("a model concurrency limit is between 1 and 256")
        if max_wait_s < 0 or poll_s <= 0:
            raise ValueError("a slot's wait is not negative and its poll is positive")
        self._sessions = sessions
        self.pool = pool
        self.limit = limit
        self._max_wait_s = max_wait_s
        self._poll_s = poll_s
        self._clock = clock
        self._monotonic = monotonic
        self._sleep = sleep
        self._ensured = False
        self._guard = threading.Lock()

    @contextmanager
    def hold(
        self, *, holder_attempt_id: str, checkpoint: Callable[[], None] = lambda: None
    ) -> Iterator[int]:
        """Hold one slot for the block; the slot number is yielded (for the record).

        Waits, calling ``checkpoint`` between polls (a stopping or cancelled step stops
        here, holding nothing), and raises :class:`ModelSlotsBusy` past ``max_wait_s``.
        """
        token = uuid.uuid4().hex
        started = self._monotonic()
        held = self._acquire(holder_attempt_id, token)
        while held is None:
            checkpoint()
            waited = self._monotonic() - started
            if waited >= self._max_wait_s:
                raise ModelSlotsBusy(self.pool, self.limit, waited)
            self._sleep(self._poll_s)
            held = self._acquire(holder_attempt_id, token)
        try:
            yield held.slot
        finally:
            self._release(held)

    def in_flight(self) -> int:
        """Slots of this pool held now by a live attempt (for tests and an operator)."""
        with self._sessions() as session:
            rows = session.scalars(
                select(ModelConcurrencySlotRow).where(
                    ModelConcurrencySlotRow.pool == self.pool,
                    ModelConcurrencySlotRow.holder_token.is_not(None),
                )
            ).all()
            live = self._live(session, {r.holder_attempt_id for r in rows if r.holder_attempt_id})
            return sum(1 for r in rows if r.holder_attempt_id in live)

    def _ensure(self, session: Session) -> None:
        with self._guard:
            if self._ensured:
                return
        _insert_ignore(
            session,
            ModelConcurrencySlotRow.__table__,
            [{"pool": self.pool, "slot": n} for n in range(self.limit)],
        )
        session.commit()
        with self._guard:
            self._ensured = True

    def _live(self, session: Session, holders: set[str]) -> set[str]:
        """The holder attempts that still hold their lease."""
        if not holders:
            return set()
        now = self._clock()
        rows = session.execute(
            select(StepAttemptRow.attempt_id, StepAttemptRow.lease_until).where(
                StepAttemptRow.attempt_id.in_(sorted(holders)),
                StepAttemptRow.status.in_(_LIVE),
            )
        ).all()
        return {
            attempt_id
            for attempt_id, lease_until in rows
            if (deadline := as_utc(lease_until)) is not None and deadline > now
        }

    def _acquire(self, holder_attempt_id: str, token: str) -> _Held | None:
        with self._sessions() as session:
            self._ensure(session)
            query = (
                select(ModelConcurrencySlotRow)
                .where(
                    ModelConcurrencySlotRow.pool == self.pool,
                    ModelConcurrencySlotRow.slot < self.limit,
                )
                .order_by(ModelConcurrencySlotRow.slot)
                .execution_options(populate_existing=True)
            )
            if _is_postgres(session):
                query = query.with_for_update(skip_locked=True)
            rows = session.scalars(query).all()
            live = self._live(
                session,
                {r.holder_attempt_id for r in rows if r.holder_token and r.holder_attempt_id},
            )
            for row in rows:
                if row.holder_token is not None and row.holder_attempt_id in live:
                    continue
                observed = row.holder_token
                taken = session.execute(
                    update(ModelConcurrencySlotRow)
                    .where(
                        ModelConcurrencySlotRow.pool == self.pool,
                        ModelConcurrencySlotRow.slot == row.slot,
                        ModelConcurrencySlotRow.holder_token.is_(None)
                        if observed is None
                        else ModelConcurrencySlotRow.holder_token == observed,
                    )
                    .values(
                        holder_attempt_id=holder_attempt_id,
                        holder_token=token,
                        acquired_at=self._clock(),
                    )
                    .execution_options(synchronize_session=False)
                )
                if _rowcount(taken) == 1:
                    session.commit()
                    return _Held(slot=row.slot, token=token)
            session.rollback()
            return None

    def _release(self, held: _Held) -> None:
        with self._sessions() as session:
            session.execute(
                update(ModelConcurrencySlotRow)
                .where(
                    ModelConcurrencySlotRow.pool == self.pool,
                    ModelConcurrencySlotRow.slot == held.slot,
                    ModelConcurrencySlotRow.holder_token == held.token,
                )
                .values(holder_attempt_id=None, holder_token=None, acquired_at=None)
                .execution_options(synchronize_session=False)
            )
            session.commit()
