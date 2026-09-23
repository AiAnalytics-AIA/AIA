"""The heartbeat: keeps one attempt's lease alive and carries cancellation back.

A daemon thread per executing attempt. Every ``interval`` seconds it extends the
lease and reads the step's cancellation flag, in one short transaction. It never
touches the executor; it only sets the attempt's signals, which the executor
observes at its next checkpoint.

The lease is considered **lost** when:

* the repository refuses the heartbeat -- the attempt was recovered, finished, or
  belongs to someone else; or
* no heartbeat has succeeded for a whole lease period, because the database is
  unreachable. By then a reconciler elsewhere may already have recovered the
  attempt, so continuing would be betting the client's money that it has not.

Cancellation is therefore observed within one heartbeat interval.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from aia_core.domain.scope import StudyContext
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from sqlalchemy.orm import Session, sessionmaker

from .context import AttemptSignals

__all__ = ["Heartbeat"]

log = logging.getLogger("aia_worker.heartbeat")


class Heartbeat(threading.Thread):
    """Extend one attempt's lease until stopped, or until the lease is lost."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        scope: StudyContext,
        attempt_id: str,
        step_id: str,
        worker_id: str,
        lease_seconds: int,
        interval_seconds: float,
        signals: AttemptSignals,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(name=f"heartbeat-{attempt_id}", daemon=True)
        self._factory = session_factory
        self._scope = scope
        self._attempt_id = attempt_id
        self._step_id = step_id
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._interval = interval_seconds
        self._signals = signals
        self._clock = clock
        self._halt = threading.Event()
        self.beats = 0

    def stop(self, *, timeout: float = 10.0) -> None:
        """Stop beating and wait for the thread to finish its current beat."""
        self._halt.set()
        if self.is_alive():
            self.join(timeout)

    def _fields(self, **extra: object) -> dict[str, object]:
        return {"attempt_id": self._attempt_id, "step_id": self._step_id, **extra}

    def beat(self) -> bool:
        """One heartbeat. Returns False when the lease was refused."""
        session = self._factory()
        try:
            repo = WorkflowRepository(session, self._scope)
            accepted = repo.heartbeat(
                self._attempt_id, worker_id=self._worker_id, lease_seconds=self._lease_seconds
            )
            cancel = repo.is_cancel_requested(self._step_id) if accepted else False
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
        if accepted:
            self.beats += 1
            if cancel and not self._signals.cancel.is_set():
                log.info("cancellation observed", extra={"fields": self._fields()})
                self._signals.cancel.set()
        return accepted

    def run(self) -> None:
        last_success = self._clock()
        while not self._halt.wait(self._interval):
            try:
                accepted = self.beat()
            except Exception as error:
                silent_for = self._clock() - last_success
                log.warning(
                    "heartbeat failed",
                    extra={
                        "fields": self._fields(error=type(error).__name__, silent_for=silent_for)
                    },
                )
                if silent_for >= self._lease_seconds:
                    log.error(
                        "no heartbeat for a whole lease; treating the lease as lost",
                        extra={"fields": self._fields()},
                    )
                    self._signals.lease_lost.set()
                    return
                continue
            if not accepted:
                if not self._halt.is_set():
                    log.warning("heartbeat refused; lease lost", extra={"fields": self._fields()})
                self._signals.lease_lost.set()
                return
            last_success = self._clock()
