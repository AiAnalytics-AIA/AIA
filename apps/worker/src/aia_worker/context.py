"""The :class:`~aia_worker.executor.StepContext` a worker hands its executor.

Every write here is its own short transaction, committed before the method
returns, and every one is lease-fenced by the repository. No transaction is held
open across an executor's work: a step may run for tens of minutes, and a
transaction that long would hold row locks the reconciler and the API need.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from aia_core.domain.providers import Provider, is_paid
from aia_core.domain.scope import StudyContext
from aia_core.infrastructure.workflow_repository import LeaseLost, WorkflowRepository
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from .executor import (
    CancellationRequested,
    LeaseRevoked,
    PaidCall,
    ShutdownRequested,
    StepInput,
)

__all__ = ["AttemptContext", "AttemptSignals", "in_transaction"]

log = logging.getLogger("aia_worker.context")


@dataclass(slots=True)
class AttemptSignals:
    """What the heartbeat and the signal handler tell the executing thread.

    ``stopping`` is the worker's, shared by every attempt it runs; the other two
    belong to one attempt.
    """

    stopping: threading.Event
    cancel: threading.Event = field(default_factory=threading.Event)
    lease_lost: threading.Event = field(default_factory=threading.Event)


def _is_transient(error: BaseException) -> bool:
    """True for a database error worth retrying: a dropped or refused connection."""
    if isinstance(error, OperationalError):
        return True
    return isinstance(error, DBAPIError) and bool(error.connection_invalidated)


def in_transaction[T](
    session_factory: sessionmaker[Session],
    scope: StudyContext,
    work: Callable[[WorkflowRepository], T],
    *,
    attempts: int = 3,
    backoff_seconds: float = 0.2,
) -> T:
    """Run ``work`` in one transaction and commit, retrying transient failures.

    A retry after a commit whose acknowledgement was lost repeats ``work``; every
    write the worker makes through here is idempotent for its owner (completion,
    settlement, dispatch marking) or conservative when repeated (a second budget
    hold, released when the attempt ends). ``LeaseLost`` is never retried.
    """
    for attempt in range(1, max(1, attempts) + 1):
        session = session_factory()
        try:
            result = work(WorkflowRepository(session, scope))
            session.commit()
            return result
        except Exception as error:
            session.rollback()
            if isinstance(error, LeaseLost) or not _is_transient(error) or attempt >= attempts:
                raise
            log.warning(
                "transient database error; retrying",
                extra={"fields": {"attempt": attempt, "error": type(error).__name__}},
            )
            time.sleep(backoff_seconds * attempt)
        finally:
            session.close()
    raise AssertionError("unreachable")  # pragma: no cover


class AttemptContext:
    """One claimed attempt's view of the world. Implements ``StepContext``."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        scope: StudyContext,
        step: StepInput,
        worker_id: str,
        signals: AttemptSignals,
        write_attempts: int = 3,
    ) -> None:
        self._factory = session_factory
        self._scope = scope
        self._step = step
        self._worker_id = worker_id
        self._signals = signals
        self._write_attempts = write_attempts

    @property
    def scope(self) -> StudyContext:
        return self._scope

    @property
    def step(self) -> StepInput:
        return self._step

    # ------------------------------------------------------------ checkpoints --

    def checkpoint(self) -> None:
        """Raise when the executor must stop.

        Order matters. A lost lease comes first: nothing more may be written at
        all. Cancellation before shutdown: if both are true, the researcher asked
        for the step to stop, and releasing it to another worker would run it
        again.
        """
        if self._signals.lease_lost.is_set():
            raise LeaseRevoked(self._step.attempt_id)
        if self._signals.cancel.is_set():
            raise CancellationRequested(self._step.run_id)
        if self._signals.stopping.is_set():
            raise ShutdownRequested(self._worker_id)

    def _write[T](self, work: Callable[[WorkflowRepository], T]) -> T:
        """A fenced write; a refused fence becomes :class:`LeaseRevoked`."""
        try:
            return in_transaction(self._factory, self._scope, work, attempts=self._write_attempts)
        except LeaseLost as lost:
            self._signals.lease_lost.set()
            raise LeaseRevoked(self._step.attempt_id) from lost

    # --------------------------------------------------------------- metering --

    def reserve(self, *, amount_usd: float, provider: Provider, reason: str = "") -> PaidCall:
        self.checkpoint()
        if not is_paid(provider):
            return PaidCall(provider=provider, amount_usd=0.0, reservation_id=None)
        reservation_id = self._write(
            lambda repo: repo.reserve_budget(
                attempt_id=self._step.attempt_id,
                worker_id=self._worker_id,
                amount_usd=amount_usd,
                provider=provider,
                reason=reason,
            )
        )
        return PaidCall(provider=provider, amount_usd=amount_usd, reservation_id=reservation_id)

    def dispatching(self, call: PaidCall, *, provider_request_id: str | None = None) -> None:
        # The last point at which stopping costs nothing: after this, the call is
        # in flight and its billing is the client's.
        self.checkpoint()
        if call.reservation_id is None:
            return
        self._write(
            lambda repo: repo.mark_paid_call_dispatched(
                self._step.attempt_id,
                worker_id=self._worker_id,
                provider_request_id=provider_request_id,
            )
        )

    def settled(
        self, call: PaidCall, *, actual_cost_usd: float, provider_request_id: str | None = None
    ) -> None:
        # No checkpoint first: the call happened, and its cost is recorded even if
        # the step was cancelled meanwhile. Only a lost lease stops it -- and then
        # recovery has already charged the reservation as uncertain.
        reservation_id = call.reservation_id
        if reservation_id is None:
            return
        self._write(
            lambda repo: repo.settle_paid_call(
                self._step.attempt_id,
                worker_id=self._worker_id,
                reservation_id=reservation_id,
                actual_cost_usd=actual_cost_usd,
                provider_request_id=provider_request_id,
            )
        )

    def not_billed(self, call: PaidCall, *, provider_request_id: str | None = None) -> None:
        self.settled(call, actual_cost_usd=0.0, provider_request_id=provider_request_id)

    # ------------------------------------------------------------------ other --

    def progress(self, message: str, **payload: Any) -> None:
        self._write(
            lambda repo: repo.record_progress(
                self._step.attempt_id,
                worker_id=self._worker_id,
                message=message,
                payload=payload,
            )
        )

    @contextmanager
    def transaction(self) -> Iterator[tuple[Session, WorkflowRepository]]:
        """A unit of work that commits only while this worker holds the lease.

        The attempt row is locked at the start and held until commit, so a
        reconciler cannot recover the attempt mid-transaction, and a worker that
        already lost the lease is refused before it writes anything. Keep it
        short: the heartbeat waits on the same lock.
        """
        session = self._factory()
        try:
            repo = WorkflowRepository(session, self._scope)
            try:
                repo.assert_lease(self._step.attempt_id, worker_id=self._worker_id)
            except LeaseLost as lost:
                self._signals.lease_lost.set()
                raise LeaseRevoked(self._step.attempt_id) from lost
            yield session, repo
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
