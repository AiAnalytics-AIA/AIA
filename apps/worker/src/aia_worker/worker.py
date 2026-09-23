"""The execution loop: claim, execute, record -- and reconcile on the side.

::

    loop until stopping:
        every maintenance_seconds:  recover lapsed leases, resume due parks
        claim one step of a kind we can execute         (one transaction)
        issue the execution scope from the lease        (same transaction)
        start the heartbeat
        executor.execute(step, context)                 (no transaction held)
        record the outcome: complete / fail / gate /
            abandon / release                           (one transaction)
        stop the heartbeat

What each way of ending becomes:

====================================  ==========================================
The executor…                         The attempt becomes…
====================================  ==========================================
returns ``Succeeded``                 ``complete_attempt``
returns ``Failed`` / raises           ``fail_attempt`` with its class; the domain
``StepFailed``                        decides retry, park or stop
returns ``NeedsApproval``             ``fail_attempt(APPROVAL_REQUIRED)`` + a gate
lets ``BudgetExceeded`` escape        ``fail_attempt(BUDGET_EXCEEDED)``
raises anything else                  ``fail_attempt(UNKNOWN)`` -- permanent: an
                                      error nobody classified is not retried
                                      against a paid provider
stops at ``CancellationRequested``    ``abandon_attempt``; hold returned
stops at ``ShutdownRequested``        ``release_attempt``; runnable at once
stops at ``LeaseRevoked``             nothing -- another worker owns it now
is killed (``SIGKILL``, OOM, …)       nothing here; the lease lapses and any
                                      worker's reconciler recovers it
====================================  ==========================================

Nothing here decides what a failure *means*: that is
``aia_core.domain.workflow.decide_recovery``. Nothing here knows what a step
*does*: that is the executor registered for its kind.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from aia_core.application.scope import ScopeResolver
from aia_core.domain.scope import ScopeDenied, StudyContext
from aia_core.domain.workflow import FailureClass, StepRunStatus
from aia_core.infrastructure.workflow_repository import (
    BudgetExceeded,
    ClaimedWork,
    LeaseLost,
    WorkflowRepository,
    WorkQueue,
)
from sqlalchemy.orm import Session, sessionmaker

from .context import AttemptContext, AttemptSignals, in_transaction
from .executor import (
    CancellationRequested,
    ExecutorRegistry,
    Failed,
    GateDecision,
    LeaseRevoked,
    NeedsApproval,
    ShutdownRequested,
    StepExecutor,
    StepFailed,
    StepInput,
    StepOutcome,
    Succeeded,
)
from .heartbeat import Heartbeat
from .observability import attempt_context, redact_text
from .settings import WorkerSettings

__all__ = ["AttemptResult", "Worker"]

log = logging.getLogger("aia_worker.worker")


@dataclass(frozen=True, slots=True)
class AttemptResult:
    """What one :meth:`Worker.run_once` did. Returned for tests and for logs."""

    attempt_id: str
    step_id: str
    ending: str
    """``completed``, ``failed``, ``gated``, ``abandoned``, ``released``,
    ``lease_lost``, ``refused`` or ``unrecorded`` (recording itself failed)."""
    step_status: StepRunStatus | None = None


@dataclass(frozen=True, slots=True)
class _Claim:
    work: ClaimedWork
    scope: StudyContext
    step: StepInput


class Worker:
    """One worker's loop. Several may run against one database, in any processes."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        executors: ExecutorRegistry,
        settings: WorkerSettings,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not executors:
            raise ValueError("a worker needs at least one executor; it would claim nothing")
        self._factory = session_factory
        self._executors: Mapping[str, StepExecutor] = dict(executors)
        self._kinds = frozenset(self._executors)
        self._settings = settings
        self._clock = clock
        self._stopping = threading.Event()
        self._last_maintenance: float | None = None

    @property
    def worker_id(self) -> str:
        return self._settings.worker_id

    @property
    def stopping(self) -> bool:
        return self._stopping.is_set()

    def request_stop(self) -> None:
        """Stop claiming, and ask the executing step to stop at its next checkpoint.

        Safe to call from a signal handler: it only sets an event.
        """
        self._stopping.set()

    # -------------------------------------------------------------------- loop --

    def run_forever(self) -> None:
        """Run until :meth:`request_stop`. Never raises for a failed iteration."""
        log.info(
            "worker started",
            extra={"fields": {"kinds": sorted(self._kinds), "build_sha": self._settings.build_sha}},
        )
        while not self._stopping.is_set():
            did_work = False
            try:
                self.maintain_if_due()
                did_work = self.run_once() is not None
            except Exception:
                # The database being unreachable is the usual cause. The loop must
                # outlive it: log, back off, try again.
                log.exception("worker iteration failed")
            if not did_work:
                self._stopping.wait(self._idle_delay())
        log.info("worker stopped")

    def _idle_delay(self) -> float:
        # Jittered, so a fleet started together does not poll in lockstep.
        base = self._settings.poll_seconds
        return base * random.uniform(0.8, 1.2)

    def maintain_if_due(self) -> None:
        now = self._clock()
        last = self._last_maintenance
        if last is None or now - last >= self._settings.maintenance_seconds:
            self._last_maintenance = now
            self.maintain()

    def maintain(self) -> tuple[int, int]:
        """Recover lapsed leases and resume due parks, across every study.

        Every worker does this; both are ``FOR UPDATE SKIP LOCKED``, so several
        doing it at once each handle a disjoint set. Returns (recovered, resumed).
        """
        recovered = resumed = 0
        try:
            with self._factory() as session:
                recovered = len(WorkQueue(session).recover_expired_attempts())
                session.commit()
        except Exception:
            log.exception("recovery sweep failed")
        try:
            with self._factory() as session:
                resumed = len(
                    WorkQueue(session).resume_waiting_steps(
                        capacity_backoff_seconds=self._settings.capacity_backoff_seconds,
                        quota_fallback_seconds=self._settings.quota_fallback_seconds,
                    )
                )
                session.commit()
        except Exception:
            log.exception("resume sweep failed")
        if recovered or resumed:
            log.info("maintenance", extra={"fields": {"recovered": recovered, "resumed": resumed}})
        return recovered, resumed

    # ------------------------------------------------------------------- claim --

    def run_once(self) -> AttemptResult | None:
        """Claim and execute one step. Returns None when there was nothing to do."""
        if self._stopping.is_set():
            return None
        claimed = self._claim()
        if claimed is None or isinstance(claimed, AttemptResult):
            return claimed
        return self._execute(claimed)

    def _claim(self) -> _Claim | AttemptResult | None:
        """Claim one step and issue its scope, in one transaction."""
        with self._factory() as session:
            queue = WorkQueue(session)
            work = queue.claim_next(
                worker_id=self.worker_id,
                kinds=self._kinds,
                lease_seconds=self._settings.lease_seconds,
            )
            if work is None:
                session.commit()
                return None
            try:
                scope = ScopeResolver(session).execution_context(
                    attempt_id=work.attempt_id, worker_id=self.worker_id
                )
            except ScopeDenied as denied:
                # Fail closed, recorded -- not left for the lease to lapse and be
                # retried into the same refusal.
                decision = queue.refuse(
                    work.attempt_id, worker_id=self.worker_id, reason=denied.reason
                )
                session.commit()
                log.warning(
                    "claimed work refused",
                    extra={"fields": {"attempt_id": work.attempt_id, "reason": denied.reason}},
                )
                return AttemptResult(work.attempt_id, work.step_id, "refused", decision.step_status)
            gates = WorkflowRepository(session, scope).decided_gates(work.step_id)
            session.commit()

        step = StepInput(
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
            gate_decisions=tuple(
                GateDecision(
                    gate_id=g["gate_id"],
                    gate_type=g["gate_type"],
                    option=g["option"],
                    note=g["note"],
                    decided_by_user_id=g["decided_by_user_id"],
                )
                for g in gates
            ),
        )
        return _Claim(work=work, scope=scope, step=step)

    # ----------------------------------------------------------------- execute --

    def _execute(self, claim: _Claim) -> AttemptResult:
        work, step = claim.work, claim.step
        signals = AttemptSignals(stopping=self._stopping)
        context = AttemptContext(
            session_factory=self._factory,
            scope=claim.scope,
            step=step,
            worker_id=self.worker_id,
            signals=signals,
            write_attempts=self._settings.finish_attempts,
        )
        heartbeat = Heartbeat(
            session_factory=self._factory,
            scope=claim.scope,
            attempt_id=work.attempt_id,
            step_id=work.step_id,
            worker_id=self.worker_id,
            lease_seconds=self._settings.lease_seconds,
            interval_seconds=self._settings.heartbeat_seconds,
            signals=signals,
        )
        token = attempt_context.set(
            {"run_id": work.run_id, "step_id": work.step_id, "attempt_id": work.attempt_id}
        )
        log.info(
            "executing",
            extra={"fields": {"kind": work.kind, "attempt_number": work.attempt_number}},
        )
        heartbeat.start()
        try:
            return self._run_executor(claim, context)
        finally:
            heartbeat.stop()
            attempt_context.reset(token)

    def _run_executor(self, claim: _Claim, context: AttemptContext) -> AttemptResult:
        executor = self._executors.get(claim.work.kind)
        if executor is None:  # pragma: no cover - the claim filter makes this unreachable
            return self._record_failure(
                claim, Failed(FailureClass.MISSING_CONFIGURATION, {"kind": claim.work.kind})
            )

        try:
            outcome: StepOutcome = executor.execute(claim.step, context)
        except LeaseRevoked:
            log.warning("lease lost during execution; result discarded")
            return AttemptResult(claim.work.attempt_id, claim.work.step_id, "lease_lost")
        except CancellationRequested:

            def abandon(repo: WorkflowRepository) -> StepRunStatus:
                repo.abandon_attempt(
                    claim.work.attempt_id, worker_id=self.worker_id, reason="cancelled"
                )
                return StepRunStatus.CANCELLED

            return self._record(claim, "abandoned", abandon)
        except ShutdownRequested:
            return self._record(
                claim,
                "released",
                lambda repo: (
                    repo.release_attempt(
                        claim.work.attempt_id, worker_id=self.worker_id
                    ).step_status
                ),
            )
        except BudgetExceeded as exceeded:
            return self._record_failure(
                claim,
                Failed(
                    FailureClass.BUDGET_EXCEEDED,
                    {
                        "requested_usd": exceeded.requested,
                        "remaining_usd": exceeded.remaining,
                        "budget_usd": exceeded.limit,
                    },
                ),
            )
        except StepFailed as failed:
            return self._record_failure(
                claim,
                Failed(failed.failure, _redacted(failed.error), failed.quota_reset_at),
            )
        except Exception as error:
            log.exception("executor raised an unclassified error")
            return self._record_failure(
                claim,
                Failed(
                    FailureClass.UNKNOWN,
                    {"type": type(error).__name__, "message": redact_text(str(error))},
                ),
            )

        if isinstance(outcome, Succeeded):
            return self._record(
                claim,
                "completed",
                lambda repo: repo.complete_attempt(
                    claim.work.attempt_id,
                    worker_id=self.worker_id,
                    output=outcome.output,
                    actual_cost_usd=outcome.actual_cost_usd,
                ),
            )
        if isinstance(outcome, NeedsApproval):
            return self._record(claim, "gated", lambda repo: self._open_gate(repo, claim, outcome))
        return self._record_failure(claim, outcome)

    def _open_gate(
        self, repo: WorkflowRepository, claim: _Claim, request: NeedsApproval
    ) -> StepRunStatus:
        """End the attempt as awaiting approval and open the gate, atomically."""
        decision = repo.fail_attempt(
            claim.work.attempt_id,
            worker_id=self.worker_id,
            failure=FailureClass.APPROVAL_REQUIRED,
            error={"question": request.question},
        )
        if decision.step_status is not StepRunStatus.AWAITING_GATE:
            # Cancelled meanwhile: there is nothing left to approve.
            return decision.step_status
        repo.open_gate(
            step_id=claim.work.step_id,
            question=request.question,
            options=list(request.options),
            context=dict(request.context),
            gate_type=request.gate_type,
        )
        return StepRunStatus.AWAITING_GATE

    def _record_failure(self, claim: _Claim, failed: Failed) -> AttemptResult:
        return self._record(
            claim,
            "failed",
            lambda repo: (
                repo.fail_attempt(
                    claim.work.attempt_id,
                    worker_id=self.worker_id,
                    failure=failed.failure,
                    error=failed.error,
                    quota_reset_at=failed.quota_reset_at,
                ).step_status
            ),
        )

    def _record(
        self,
        claim: _Claim,
        ending: str,
        write: Callable[[WorkflowRepository], StepRunStatus],
    ) -> AttemptResult:
        """Record how the attempt ended, retrying transient database failures.

        ``LeaseLost`` here means another worker owns the step now, and whatever
        this worker computed is discarded. Any other failure to record leaves the
        attempt held; the lease lapses and a reconciler applies the recovery
        table, which is exactly what would have happened had this process died.
        """
        attempt_id, step_id = claim.work.attempt_id, claim.work.step_id
        try:
            status = in_transaction(
                self._factory, claim.scope, write, attempts=self._settings.finish_attempts
            )
        except LeaseLost:
            log.warning("lease lost before the outcome was recorded; result discarded")
            return AttemptResult(attempt_id, step_id, "lease_lost")
        except Exception:
            log.exception("could not record the outcome; the lease will lapse")
            return AttemptResult(attempt_id, step_id, "unrecorded")
        log.info(ending, extra={"fields": {"step_status": status.value}})
        return AttemptResult(attempt_id, step_id, ending, status)


def _redacted(error: dict[str, Any]) -> dict[str, Any]:
    """Redact string values an executor put in an error payload."""
    return {k: redact_text(v) if isinstance(v, str) else v for k, v in error.items()}
