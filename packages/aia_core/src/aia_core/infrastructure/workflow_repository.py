"""Persistence and execution control for the durable workflow engine.

This is the only module permitted to write `workflow_runs`, `step_runs`,
`step_attempts`, `budget_reservations`, `workflow_gates` and `workflow_events`.

Four properties are enforced here rather than trusted to callers:

* **Scope isolation.** Constructed from a :class:`StudyContext`; every statement
  filters on organization, client and study.
* **Exclusive claiming.** ``SELECT … FOR UPDATE SKIP LOCKED`` on PostgreSQL, with
  a conditional-update fallback on SQLite. Two workers cannot hold one attempt.
* **Accounting transactionality.** The attempt, its budget reservation and the
  execution state are written in one unit of work **before** any external
  dispatch, so "a provider was called but no attempt exists" is unrepresentable.
* **Append-only attempt history.** An attempt row is never reused. A retry
  creates attempt *n+1*.

Decision logic lives in ``aia_core.domain.workflow``; this module executes it.
The behavioural contract is
``packages/aia_core/tests/test_legacy_job_store_characterization.py``.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from ..domain.population import (
    JointState,
    PopulationBinding,
    PopulationBindingConflict,
    PopulationBindingMissing,
    PopulationBindingRequired,
    PopulationView,
    ResolutionMode,
)
from ..domain.providers import Provider, is_paid
from ..domain.scope import (
    ApprovalIndependence,
    Permission,
    StudyContext,
    observe_approval_independence,
    require_approval_independence,
)
from ..domain.workflow import (
    DEFAULT_CAPACITY_BACKOFF_SECONDS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_QUOTA_FALLBACK_SECONDS,
    AttemptStatus,
    FailureClass,
    InteractionMode,
    RecoveryAction,
    RecoveryDecision,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
    apply_cancellation,
    decide_deferral,
    decide_recovery,
    decide_release,
    derive_run_status,
    is_lease_expired,
    lease_deadline,
    new_attempt_id,
    new_reservation_id,
    new_run_id,
    new_step_id,
    resume_due,
    runtime_park_can_resume,
    validate_dag,
)
from .tables import (
    ApprovalDecisionRow,
    BudgetReservationRow,
    RunPopulationBindingRow,
    StepAttemptRow,
    StepDependencyRow,
    StepRunRow,
    StudyRow,
    WorkflowEventRow,
    WorkflowGateRow,
    WorkflowRunRow,
    as_utc,
    utcnow,
)

__all__ = [
    "BudgetExceeded",
    "ClaimedWork",
    "LeaseLost",
    "ReservationClosed",
    "RuntimeParkNotResumable",
    "WorkQueue",
    "WorkflowNotFound",
    "WorkflowRepository",
]


def _binding(row: RunPopulationBindingRow) -> PopulationBinding:
    return PopulationBinding(
        dataset_id=row.dataset_id,
        version_id=row.version_id,
        version_label=row.version_label,
        content_sha256=row.content_sha256,
        contract_id=row.contract_id,
        population_id=row.population_id,
        resolution=ResolutionMode(row.resolution),
        weight_role=row.weight_role,
        weight_column=row.weight_column,
        view=PopulationView(row.view),
        resolved_at=as_utc(row.resolved_at),
        dictionary_sha256=row.dictionary_sha256,
        field_policy_version=row.field_policy_version,
        companion_set_sha256=row.companion_set_sha256,
        joint_state=JointState(row.joint_state),
    )


def _binding_identity(binding: PopulationBinding | None) -> tuple[str, ...] | None:
    """What makes two bindings the same population. ``resolved_at`` is not part of it."""
    if binding is None:
        return None
    return (
        binding.version_id,
        binding.content_sha256,
        binding.contract_id,
        binding.weight_role,
        binding.weight_column,
        binding.view.value,
        binding.dictionary_sha256,
        binding.field_policy_version,
        binding.companion_set_sha256,
        binding.joint_state.value,
    )


class WorkflowNotFound(LookupError):
    """The run, step or attempt does not exist, or is not in the caller's scope.

    Indistinguishable on purpose: acknowledging a run the caller may not see
    would disclose another client's engagement.
    """


class BudgetExceeded(RuntimeError):
    """A paid call would exceed the study's budget.

    Raised instead of proceeding, and instead of choosing a cheaper provider. The
    caller must park the step in ``AWAITING_BUDGET`` and ask.
    """

    def __init__(self, *, requested: float, remaining: float, limit: float) -> None:
        super().__init__(
            f"budget exceeded: requested {requested:.2f}, remaining {remaining:.2f} of {limit:.2f}"
        )
        self.requested = requested
        self.remaining = remaining
        self.limit = limit


class RuntimeParkNotResumable(ValueError):
    """The step is not an unbilled park waiting for runtime activation."""


class BudgetWaitNotLiftable(ValueError):
    """The step is not waiting for budget (any more), or its run is being cancelled."""


class ReservationClosed(ValueError):
    """A paid call was about to be dispatched against a hold that is no longer open.

    Raised before the call leaves, so nothing is sent: a settled or released hold
    has no budget behind it, and a call recorded against it could never be
    charged as uncertain by recovery.
    """

    def __init__(self, reservation_id: str, status: str) -> None:
        super().__init__(f"reservation {reservation_id} is {status}, not RESERVED")
        self.reservation_id = reservation_id
        self.status = status


class LeaseLost(RuntimeError):
    """The caller no longer holds the attempt's lease, so it may write nothing.

    Raised by every lease-fenced write -- complete, fail, abandon, release and
    per-call metering -- when the attempt has already ended or belongs to another
    worker. The only correct response is to stop: the attempt was recovered, and
    another worker may already be running the step. Recording anything would put
    two outcomes on one step.
    """

    def __init__(self, attempt_id: str, *, worker_id: str, owner: str | None, status: str) -> None:
        super().__init__(
            f"lease on {attempt_id} is not held by {worker_id} (owner {owner}, status {status})"
        )
        self.attempt_id = attempt_id
        self.worker_id = worker_id
        self.owner = owner
        self.status = status


@dataclass(frozen=True, slots=True)
class ClaimedWork:
    """A step and attempt a worker now owns.

    ``worker_id`` is carried so that the lease-fenced calls that follow name the
    same owner the claim recorded; the scope ids are carried so a worker that
    claimed across studies can have the matching scope issued
    (:meth:`aia_core.application.scope.ScopeResolver.execution_context`).
    """

    run_id: str
    step_id: str
    attempt_id: str
    attempt_number: int
    node_key: str
    kind: str
    stage_type: str
    artifact_target: str
    input_fingerprint: str
    interaction_mode: InteractionMode
    lease_until: datetime
    payload: dict[str, Any]
    project_id: str
    project_revision: int
    worker_id: str
    organization_id: str
    client_id: str
    study_id: str


class WorkflowRepository:
    """Durable workflow state within one authorised study scope.

    The caller owns the transaction. Methods flush so generated values are
    available, but never commit -- which is what lets the attempt, its
    reservation and the state change be one atomic unit.
    """

    def __init__(self, session: Session, scope: StudyContext) -> None:
        if not isinstance(scope, StudyContext):
            raise TypeError(
                "WorkflowRepository requires a StudyContext issued by the "
                "authorization layer; unscoped access is not permitted"
            )
        self._session = session
        self._scope: StudyContext | None = scope

    @classmethod
    def _across_studies(cls, session: Session) -> WorkflowRepository:
        """An unscoped instance, for :class:`WorkQueue` in this module only.

        Every query then runs without the study predicate, which is exactly what
        claiming and reconciling across studies need and exactly what nothing
        else may have. It is reachable only through ``WorkQueue``, which exposes
        four operations and no read of research data; any scoped public method
        called on it raises, because :attr:`scope` refuses.
        """
        repo = cls.__new__(cls)
        repo._session = session
        repo._scope = None
        return repo

    @property
    def scope(self) -> StudyContext:
        """The authorised scope this repository operates in."""
        if self._scope is None:
            raise RuntimeError("this repository is the unscoped work queue and has no study scope")
        return self._scope

    # ---------------------------------------------------------------- helpers --

    def _scope_filter(self) -> tuple[Any, ...]:
        """The isolation predicate applied to every run query.

        Empty only for the work queue's unscoped instance (:meth:`_across_studies`).
        """
        if self._scope is None:
            return ()
        return (
            WorkflowRunRow.organization_id == self.scope.organization_id,
            WorkflowRunRow.client_id == self.scope.client_id,
            WorkflowRunRow.study_id == self.scope.study_id,
        )

    def _run(self, run_id: str) -> WorkflowRunRow:
        """Fetch a run inside scope, or raise."""
        row = self._session.scalar(
            select(WorkflowRunRow).where(WorkflowRunRow.run_id == run_id, *self._scope_filter())
        )
        if row is None:
            raise WorkflowNotFound(run_id)
        return row

    def _step(self, step_id: str) -> StepRunRow:
        """Fetch a step inside scope, or raise.

        Joined through the run so the scope predicate applies to the step too. A
        step is never addressable by id alone.
        """
        row = self._session.scalar(
            select(StepRunRow)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(StepRunRow.step_id == step_id, *self._scope_filter())
        )
        if row is None:
            raise WorkflowNotFound(step_id)
        return row

    def _attempt(self, attempt_id: str) -> StepAttemptRow:
        """Fetch an attempt inside scope, or raise."""
        row = self._session.scalar(
            select(StepAttemptRow)
            .join(StepRunRow, StepRunRow.step_id == StepAttemptRow.step_id)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(StepAttemptRow.attempt_id == attempt_id, *self._scope_filter())
        )
        if row is None:
            raise WorkflowNotFound(attempt_id)
        return row

    def _locked_attempt(self, attempt_id: str) -> StepAttemptRow:
        """Fetch an attempt inside scope, row-locked, with its current values.

        The lock is **blocking**, not ``skip_locked``: a worker finishing an attempt
        that a reconciler is recovering right now must wait for the reconciler's
        verdict and then see it, never skip past it. ``populate_existing`` matters
        as much as the lock -- without it an attempt already in this session's
        identity map keeps the status it had when first read, and the fence below
        would check a stale value.
        """
        query = (
            select(StepAttemptRow)
            .join(StepRunRow, StepRunRow.step_id == StepAttemptRow.step_id)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(StepAttemptRow.attempt_id == attempt_id, *self._scope_filter())
            .execution_options(populate_existing=True)
        )
        if self._is_postgres:
            query = query.with_for_update(of=StepAttemptRow)
        row = self._session.scalar(query)
        if row is None:
            raise WorkflowNotFound(attempt_id)
        return row

    @staticmethod
    def _require_lease(attempt: StepAttemptRow, worker_id: str) -> None:
        """Raise :class:`LeaseLost` unless ``worker_id`` holds ``attempt``'s lease.

        Ownership is the attempt's status plus its ``worker_id``, read under the
        row lock. The lease *deadline* is deliberately not consulted: it is the
        trigger for recovery, not the fence. An attempt whose deadline passed but
        which no reconciler has recovered yet is still exclusively this worker's
        -- claiming requires the step to be ``RUNNABLE``, and only recovery, which
        takes this same lock, makes it so.
        """
        if attempt.worker_id != worker_id or not AttemptStatus(attempt.status).holds_lease:
            raise LeaseLost(
                attempt.attempt_id,
                worker_id=worker_id,
                owner=attempt.worker_id,
                status=attempt.status,
            )

    def _held_attempt(self, attempt_id: str, *, worker_id: str) -> StepAttemptRow:
        """Lock an attempt and return it only while ``worker_id`` holds its lease."""
        attempt = self._locked_attempt(attempt_id)
        self._require_lease(attempt, worker_id)
        return attempt

    def _event(
        self,
        run_id: str,
        *,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
        step_id: str | None = None,
        attempt_id: str | None = None,
        level: str = "INFO",
    ) -> None:
        """Append to the run's history and progress feed."""
        self._session.add(
            WorkflowEventRow(
                run_id=run_id,
                step_id=step_id,
                attempt_id=attempt_id,
                event_type=event_type,
                level=level,
                message=message,
                payload_json=payload or {},
            )
        )

    @property
    def _is_postgres(self) -> bool:
        """True when the session is bound to PostgreSQL."""
        bind = self._session.get_bind()
        return bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------ create --

    def create_run(
        self,
        *,
        project_id: str,
        project_revision: int,
        workflow_type: str,
        steps: Sequence[StepDefinition],
        idempotency_key: str,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
        step_inputs: dict[str, dict[str, Any]] | None = None,
        fingerprints: dict[str, str] | None = None,
        population: PopulationBinding | None = None,
    ) -> str:
        """Create a run and its step graph, or return an existing run.

        Idempotent on ``idempotency_key``: re-submitting the same logical run
        returns the existing run id rather than starting a second, duplicate
        pipeline. This is what makes an at-least-once trigger safe.

        The DAG is validated here rather than at execution time, because a cycle
        discovered mid-run would strand a study with some steps already paid for.

        ``population`` is the resolved binding every population-consuming step
        will read through. It is required when any step declares
        ``consumes_population`` and is recorded once, with the run, in the same
        unit of work. A re-submission that resolves to a different binding is
        refused rather than handed the old run: that would silently substitute
        the recorded population for the one the caller asked for.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()

        existing = self._session.scalar(
            select(WorkflowRunRow).where(
                WorkflowRunRow.idempotency_key == idempotency_key, *self._scope_filter()
            )
        )
        if existing is not None:
            self._require_same_binding(existing.run_id, population)
            return existing.run_id

        step_list = list(steps)
        validate_dag(step_list)
        consumers = sorted(s.node_key for s in step_list if s.consumes_population)
        if consumers and population is None:
            raise PopulationBindingRequired(
                f"steps {consumers} read population data; the run needs a resolved "
                "population binding"
            )

        run_id = new_run_id()
        self._session.add(
            WorkflowRunRow(
                run_id=run_id,
                organization_id=self.scope.organization_id,
                client_id=self.scope.client_id,
                study_id=self.scope.study_id,
                project_id=project_id,
                project_revision=int(project_revision),
                workflow_type=workflow_type,
                status=WorkflowRunStatus.PENDING.value,
                priority=int(priority),
                idempotency_key=idempotency_key,
                triggered_by=self.scope.actor_id,
                metadata_json=metadata or {},
            )
        )
        self._session.flush()
        if population is not None:
            self._record_binding(run_id, population)

        ids: dict[str, str] = {}
        for ordinal, definition in enumerate(step_list):
            step_id = new_step_id()
            ids[definition.node_key] = step_id
            self._session.add(
                StepRunRow(
                    step_id=step_id,
                    run_id=run_id,
                    node_key=definition.node_key,
                    kind=definition.kind,
                    # A step with no dependencies is immediately runnable; the
                    # rest start BLOCKED and are released as dependencies finish.
                    status=(
                        StepRunStatus.RUNNABLE.value
                        if not definition.depends_on
                        else StepRunStatus.BLOCKED.value
                    ),
                    ordinal=ordinal,
                    priority=definition.priority,
                    stage_type=definition.stage_type,
                    artifact_target=definition.artifact_target,
                    interaction_mode=definition.interaction_mode.value,
                    input_fingerprint=(fingerprints or {}).get(definition.node_key, ""),
                    max_attempts=definition.max_attempts,
                    input_json=(step_inputs or {}).get(definition.node_key, {}),
                )
            )
        self._session.flush()

        for definition in step_list:
            for dependency in definition.depends_on:
                self._session.add(
                    StepDependencyRow(
                        step_id=ids[definition.node_key],
                        depends_on_step_id=ids[dependency],
                    )
                )

        self._event(
            run_id,
            event_type="RUN_CREATED",
            message=f"{workflow_type} created with {len(step_list)} steps",
            payload={
                "workflow_type": workflow_type,
                "step_count": len(step_list),
                "project_id": project_id,
                "project_revision": int(project_revision),
                "population": population.as_record() if population is not None else None,
            },
        )
        self._refresh_run(run_id)
        self._session.flush()
        return run_id

    # ------------------------------------------------------ population binding --

    def _record_binding(self, run_id: str, binding: PopulationBinding) -> None:
        self._session.add(
            RunPopulationBindingRow(
                run_id=run_id,
                dataset_id=binding.dataset_id,
                version_id=binding.version_id,
                version_label=binding.version_label,
                content_sha256=binding.content_sha256,
                contract_id=binding.contract_id,
                population_id=binding.population_id,
                resolution=binding.resolution.value,
                weight_role=binding.weight_role,
                weight_column=binding.weight_column,
                view=binding.view.value,
                resolved_at=binding.resolved_at,
                dictionary_sha256=binding.dictionary_sha256,
                field_policy_version=binding.field_policy_version,
                companion_set_sha256=binding.companion_set_sha256,
                joint_state=binding.joint_state.value,
            )
        )
        self._session.flush()

    def _binding_row(self, run_id: str) -> RunPopulationBindingRow | None:
        return self._session.get(RunPopulationBindingRow, run_id)

    def _require_same_binding(self, run_id: str, requested: PopulationBinding | None) -> None:
        row = self._binding_row(run_id)
        recorded = _binding(row) if row is not None else None
        if _binding_identity(recorded) != _binding_identity(requested):
            raise PopulationBindingConflict(
                f"run {run_id} was recorded against "
                f"{recorded.version_id if recorded else 'no population'}; this submission "
                f"resolves to {requested.version_id if requested else 'no population'}"
            )

    def find_run_by_idempotency_key(self, idempotency_key: str) -> str | None:
        """Return the id of the run created with this key in scope, or None."""
        return self._session.scalar(
            select(WorkflowRunRow.run_id).where(
                WorkflowRunRow.idempotency_key == idempotency_key, *self._scope_filter()
            )
        )

    def list_runs(
        self, *, project_id: str, limit: int = 50, workflow_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Return a project's runs, newest first, without their steps.

        A listing for a screen; :meth:`get_run` returns one run in full.
        """
        filters = [WorkflowRunRow.project_id == project_id, *self._scope_filter()]
        if workflow_type is not None:
            filters.append(WorkflowRunRow.workflow_type == workflow_type)
        rows = self._session.scalars(
            select(WorkflowRunRow)
            .where(*filters)
            .order_by(WorkflowRunRow.created_at.desc())
            .limit(max(1, min(int(limit), 200)))
        ).all()
        # Which runs a worker has picked up at all: one query for the page, so a
        # screen can tell "queued" from "running" without reading every step.
        attempted = set(
            self._session.scalars(
                select(StepRunRow.run_id)
                .join(StepAttemptRow, StepAttemptRow.step_id == StepRunRow.step_id)
                .where(StepRunRow.run_id.in_([r.run_id for r in rows]))
                .distinct()
            ).all()
        )
        return [
            {
                "run_id": r.run_id,
                "status": WorkflowRunStatus(r.status),
                "workflow_type": r.workflow_type,
                "project_id": r.project_id,
                "project_revision": r.project_revision,
                "cancel_requested": r.cancel_requested,
                "created_at": r.created_at,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "metadata": dict(r.metadata_json or {}),
                "attempted": r.run_id in attempted,
            }
            for r in rows
        ]

    def population_binding(self, run_id: str) -> PopulationBinding:
        """Return the population binding a run recorded, or raise.

        The only way a population-consuming step learns which population to load.
        There is deliberately no "resolve the current one instead" path: a run
        with no recorded binding reads no population.
        """
        self._run(run_id)  # scope check: a run outside this study is not found
        row = self._binding_row(run_id)
        if row is None:
            raise PopulationBindingMissing(f"run {run_id} recorded no population binding")
        return _binding(row)

    # ------------------------------------------------------------ status logic --

    def _lock_run(self, run_id: str) -> None:
        """Serialise every step transition in one run on the run's row.

        **Taken before any step row is touched, and held to the end of the
        transaction.** Everything that derives something from the *set* of a
        run's steps -- the run's business status, and which blocked steps are now
        released -- reads the other steps' statuses. Under READ COMMITTED, two
        transactions finishing two steps of one run each read the other's step as
        still ``RUNNING``, so neither derived ``COMPLETED`` (and, since the
        derivation writes only on change, neither wrote anything), and in a
        diamond neither released the join step: the run read ``RUNNING`` forever
        with nothing left to run. Holding the run row makes the second
        transaction wait for the first to commit and then read what it wrote.

        Lock order is attempt → run → steps everywhere, which is also
        ``request_cancel``'s run → steps, so no two paths can wait on each other
        in a cycle. Claiming does not take it: a claim only makes a step
        ``RUNNING``, which no concurrent transition can derive differently, and
        serialising claims per run is the lock convoy ``_refresh_run`` was
        rewritten to avoid.

        A no-op on SQLite, whose single writer already serialises everything.
        """
        if self._is_postgres:
            self._session.execute(
                select(WorkflowRunRow.run_id)
                .where(WorkflowRunRow.run_id == run_id)
                .with_for_update()
            )

    def _lock_run_for(self, step: StepRunRow) -> None:
        """Lock the step's run, then re-read the step as it now stands.

        The step was read before the lock; a transition that committed while this
        transaction waited (a cancellation, say) is only visible after a refresh.
        """
        self._lock_run(step.run_id)
        self._session.refresh(step)

    def _refresh_run(self, run_id: str) -> WorkflowRunStatus:
        """Recompute a run's business state from its steps."""
        run = self._session.scalar(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.run_id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is None:
            raise WorkflowNotFound(run_id)

        statuses = [
            StepRunStatus(value)
            for value in self._session.scalars(
                select(StepRunRow.status).where(StepRunRow.run_id == run_id)
            ).all()
        ]
        derived = derive_run_status(statuses, cancel_requested=run.cancel_requested)

        # Write to the run row ONLY when something actually changes.
        #
        # This is not a micro-optimisation. Every claim, completion and recovery
        # calls this method, and `workflow_runs` has one row per run. An
        # unconditional `UPDATE ... SET updated_at` took a row lock that every
        # concurrent worker on the same run then queued behind -- a lock convoy
        # that serialised the whole engine and defeated the point of
        # FOR UPDATE SKIP LOCKED in `claim_next`. With eight workers contending it
        # deadlocked outright.
        #
        # Most calls derive the same status the run already has (RUNNING stays
        # RUNNING), so they now issue no write at all and take no lock.
        needs_started = derived is WorkflowRunStatus.RUNNING and run.started_at is None
        needs_finished = derived.is_terminal and run.finished_at is None
        status_changed = run.status != derived.value

        if not (status_changed or needs_started or needs_finished):
            return derived

        if status_changed:
            self._event(
                run_id,
                event_type="RUN_STATUS",
                message=f"{run.status} -> {derived.value}",
                payload={"from": run.status, "to": derived.value},
                level="ERROR" if derived is WorkflowRunStatus.FAILED else "INFO",
            )
            run.status = derived.value
        if needs_started:
            run.started_at = utcnow()
        if needs_finished:
            run.finished_at = utcnow()
        run.updated_at = utcnow()
        return derived

    def release_ready_steps(self, run_id: str) -> int:
        """Mark BLOCKED steps RUNNABLE once their dependencies have succeeded.

        A dependant waits for ``SUCCEEDED`` or ``SKIPPED`` specifically -- not
        merely a terminal state -- so a failed upstream step stalls the pipeline
        rather than letting downstream work run on missing inputs.
        """
        run = self._run(run_id)
        if run.cancel_requested or WorkflowRunStatus(run.status).is_terminal:
            return 0

        blocked = self._session.scalars(
            select(StepRunRow).where(
                StepRunRow.run_id == run_id,
                StepRunRow.status == StepRunStatus.BLOCKED.value,
            )
        ).all()

        released = 0
        for step in blocked:
            dependency_statuses = self._session.scalars(
                select(StepRunRow.status)
                .join(
                    StepDependencyRow,
                    StepDependencyRow.depends_on_step_id == StepRunRow.step_id,
                )
                .where(StepDependencyRow.step_id == step.step_id)
            ).all()

            if all(StepRunStatus(value).satisfies_dependency for value in dependency_statuses):
                step.status = StepRunStatus.RUNNABLE.value
                step.updated_at = utcnow()
                released += 1
                self._event(
                    run_id,
                    event_type="STEP_RUNNABLE",
                    message=f"{step.node_key} dependencies satisfied",
                    step_id=step.step_id,
                )

        if released:
            self._refresh_run(run_id)
            self._session.flush()
        return released

    # ------------------------------------------------------------------- claim --

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: datetime | None = None,
        kinds: Collection[str] | None = None,
    ) -> ClaimedWork | None:
        """Claim one runnable step, creating attempt *n+1*, or return None.

        ``kinds`` restricts the claim to step kinds the caller can execute. A
        worker that claimed a kind it has no executor for could only fail it, and
        in a rolling deploy that adds a kind the old workers would do exactly
        that. ``None`` means any kind; an empty collection claims nothing.

        Exclusivity is the whole point. On PostgreSQL this uses
        ``FOR UPDATE SKIP LOCKED``: the row is locked for this transaction, and a
        concurrent claimer skips it rather than blocking, so two workers never
        contend for the same step and neither waits.

        On SQLite (tests, offline development) the lock clauses are unavailable,
        so a conditional update guarded by the observed status provides the same
        guarantee more slowly.

        A step is claimable only when it is RUNNABLE, its run is live and not
        cancelling, and ``runnable_after`` has passed -- which is how a quota park
        becomes a resume.
        """
        moment = now or datetime.now(UTC)
        if kinds is not None and not kinds:
            return None

        candidates = (
            select(StepRunRow)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(
                StepRunRow.status == StepRunStatus.RUNNABLE.value,
                StepRunRow.cancel_requested.is_(False),
                WorkflowRunRow.cancel_requested.is_(False),
                WorkflowRunRow.status.notin_(
                    [
                        WorkflowRunStatus.CANCELLED.value,
                        WorkflowRunStatus.COMPLETED.value,
                        WorkflowRunStatus.FAILED.value,
                    ]
                ),
                (StepRunRow.runnable_after.is_(None)) | (StepRunRow.runnable_after <= moment),
                *self._scope_filter(),
            )
            # Priority first, then creation order, so nothing starves.
            .order_by(StepRunRow.priority.desc(), StepRunRow.created_at, StepRunRow.ordinal)
            .limit(1)
        )

        if kinds is not None:
            candidates = candidates.where(StepRunRow.kind.in_(sorted(kinds)))
        if self._is_postgres:
            candidates = candidates.with_for_update(skip_locked=True, of=StepRunRow)

        step = self._session.scalar(candidates)
        if step is None:
            return None

        if not self._is_postgres:
            # SQLite: re-assert the status we selected on. If another claimer got
            # there first the update affects no rows and we report no work.
            #
            # `rowcount` is on CursorResult, which is what a DML execute returns;
            # SQLAlchemy types `execute` as the wider `Result`, so the cast is a
            # typing accommodation rather than an assumption about behaviour.
            result = cast(
                CursorResult[Any],
                self._session.execute(
                    update(StepRunRow)
                    .where(
                        StepRunRow.step_id == step.step_id,
                        StepRunRow.status == StepRunStatus.RUNNABLE.value,
                    )
                    .values(status=StepRunStatus.RUNNING.value, updated_at=utcnow())
                ),
            )
            if result.rowcount != 1:
                return None
            self._session.refresh(step)
        else:
            step.status = StepRunStatus.RUNNING.value
            step.updated_at = utcnow()

        run = self._session.scalar(
            select(WorkflowRunRow).where(WorkflowRunRow.run_id == step.run_id)
        )
        assert run is not None  # guaranteed by the join above

        # Append-only history: a retry is attempt n+1, never a reused row.
        # `attempts_recorded` is monotonic so attempt numbers never collide, even
        # when a non-consuming failure lowers `attempts_consumed`.
        step.attempts_recorded += 1
        step.attempts_consumed += 1
        deadline = lease_deadline(now=moment, seconds=lease_seconds)
        attempt_id = new_attempt_id()
        self._session.add(
            StepAttemptRow(
                attempt_id=attempt_id,
                step_id=step.step_id,
                attempt_number=step.attempts_recorded,
                status=AttemptStatus.CLAIMED.value,
                worker_id=worker_id,
                lease_until=deadline,
                heartbeat_at=moment,
                started_at=moment,
            )
        )
        self._event(
            step.run_id,
            event_type="ATTEMPT_CLAIMED",
            message=f"{step.node_key} claimed by {worker_id}",
            payload={
                "worker_id": worker_id,
                "attempt_number": step.attempts_recorded,
                "lease_until": deadline.isoformat(),
            },
            step_id=step.step_id,
            attempt_id=attempt_id,
        )
        self._refresh_run(step.run_id)
        self._session.flush()

        return ClaimedWork(
            run_id=step.run_id,
            step_id=step.step_id,
            attempt_id=attempt_id,
            attempt_number=step.attempts_recorded,
            node_key=step.node_key,
            kind=step.kind,
            stage_type=step.stage_type,
            artifact_target=step.artifact_target,
            input_fingerprint=step.input_fingerprint,
            interaction_mode=InteractionMode(step.interaction_mode),
            lease_until=deadline,
            payload=dict(step.input_json or {}),
            project_id=run.project_id,
            project_revision=run.project_revision,
            worker_id=worker_id,
            organization_id=run.organization_id,
            client_id=run.client_id,
            study_id=run.study_id,
        )

    def heartbeat(
        self, attempt_id: str, *, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS
    ) -> bool:
        """Extend an attempt's lease. Returns False when refused.

        Only the lease owner may extend, and only while the attempt is live.
        Otherwise a worker that already lost its lease could keep a step alive and
        two workers would run it.

        **One conditional statement, never a read followed by a write.** It was a
        read-check-write, and a reconciler that expired the attempt between the
        read and the write was silently overwritten: the ORM's update by primary
        key put the attempt back to ``EXECUTING`` while its step was already
        ``RUNNABLE`` again, so a second worker claimed it and two workers ran one
        step. The ``WHERE`` clause below is re-evaluated by the database against
        the committed row, so an attempt expired a moment ago is refused.
        """
        self._attempt(attempt_id)  # scope check: an attempt outside scope is not found

        moment = utcnow()
        result = cast(
            CursorResult[Any],
            self._session.execute(
                update(StepAttemptRow)
                .where(
                    StepAttemptRow.attempt_id == attempt_id,
                    StepAttemptRow.worker_id == worker_id,
                    StepAttemptRow.status.in_(
                        [AttemptStatus.CLAIMED.value, AttemptStatus.EXECUTING.value]
                    ),
                )
                .values(
                    status=AttemptStatus.EXECUTING.value,
                    heartbeat_at=moment,
                    lease_until=lease_deadline(now=moment, seconds=lease_seconds),
                )
                .execution_options(synchronize_session="fetch")
            ),
        )
        self._session.flush()
        return result.rowcount == 1

    def assert_lease(self, attempt_id: str, *, worker_id: str) -> None:
        """Raise :class:`LeaseLost` unless ``worker_id`` holds the attempt.

        Takes the attempt's row lock and keeps it until the caller's transaction
        ends. That is the point: an executor's own writes made in the same
        transaction commit only if the lease is still held *at commit*, because a
        reconciler cannot recover a locked attempt (it skips it) until then.
        """
        self._held_attempt(attempt_id, worker_id=worker_id)

    def record_progress(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Append a progress event for a live attempt. Lease-fenced.

        Real counts and real transitions only -- "respondent 240 of 300", never a
        synthesised percentage (``docs/architecture/workflows.md`` § Progress).
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)
        self._event(
            step.run_id,
            event_type="STEP_PROGRESS",
            message=message,
            payload=payload,
            step_id=step.step_id,
            attempt_id=attempt_id,
        )
        self._session.flush()

    # ------------------------------------------------------- budget and costs --

    def _outstanding_reservations(self, study_id: str) -> float:
        """Sum of reservations still holding budget."""
        total = self._session.scalar(
            select(func.coalesce(func.sum(BudgetReservationRow.amount_usd), 0.0)).where(
                BudgetReservationRow.study_id == study_id,
                BudgetReservationRow.status == ReservationStatus.RESERVED.value,
            )
        )
        return float(total or 0.0)

    def reserve_budget(
        self,
        *,
        attempt_id: str,
        worker_id: str,
        amount_usd: float,
        provider: Provider,
        reason: str = "",
    ) -> str | None:
        """Hold budget for a paid call, or raise :class:`BudgetExceeded`.

        Lease-fenced: a worker that no longer holds the attempt cannot reserve
        against it (:class:`LeaseLost`), so it cannot go on to make the call.

        Called **before** dispatch, inside the same transaction as the attempt, so
        a crash cannot leave a call with no reservation behind it.

        Reservations count as spent, so a later check sees earlier holds. A
        subscription runtime needs no reservation and returns ``None``: its
        marginal cost is zero.

        **The study row is locked for the duration of the check.** Reading the
        outstanding total and then inserting is a read-modify-write, and without a
        lock every concurrent worker reads the same total, every one passes, and
        together they commit more than the budget. Four workers reserving $40
        against a $100 budget all succeeded before this lock existed -- $160 of a
        client's money, from code whose sequential tests passed.

        Serialising reservations per study is cheap: a handful of researchers run
        a handful of studies, and the lock is held only across this check.
        """
        if not is_paid(provider):
            return None

        # Attempt before study: every path that locks both takes them in this
        # order -- completion and recovery lock the attempt, then charge the
        # study -- so no two of them can wait on each other in a cycle.
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)
        run = self._run(step.run_id)

        study_query = select(StudyRow).where(StudyRow.study_id == run.study_id)
        if self._is_postgres:
            # Blocking, NOT skip_locked: a concurrent reserver must wait and then
            # re-read the total, never skip the check.
            study_query = study_query.with_for_update()

        study = self._session.scalar(study_query)
        if study is None:
            raise WorkflowNotFound(run.study_id)

        requested = max(0.0, float(amount_usd))
        outstanding = self._outstanding_reservations(run.study_id)
        remaining = max(0.0, study.budget_usd - study.spent_usd - outstanding)

        # Epsilon so an exact-limit reservation is permitted despite float drift.
        if requested > remaining + 1e-9:
            raise BudgetExceeded(requested=requested, remaining=remaining, limit=study.budget_usd)

        reservation_id = new_reservation_id()
        self._session.add(
            BudgetReservationRow(
                reservation_id=reservation_id,
                study_id=run.study_id,
                run_id=run.run_id,
                step_id=step.step_id,
                attempt_id=attempt_id,
                amount_usd=requested,
                status=ReservationStatus.RESERVED.value,
                reason=reason or f"{step.node_key}:{provider.value}",
            )
        )
        attempt.estimated_cost_usd = requested
        attempt.provider = provider.value
        self._session.flush()
        return reservation_id

    def mark_paid_call_dispatched(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        reservation_id: str,
        provider_request_id: str | None = None,
    ) -> None:
        """Record that a metered call against ``reservation_id`` is about to leave.

        Called, and **committed**, before the call is sent. From this point the
        attempt cannot be auto-retried until *this call's* outcome is known: a
        lapsed lease becomes ``RECOVERY_REQUIRED`` rather than a retry, because the
        call may already have been billed.

        The mark is on the hold, not only on the attempt. An attempt that sends two
        calls at once has two outcomes outstanding; one flag on the attempt was
        closed by whichever answered first, and a worker that died then was retried
        with the other call possibly billed (:meth:`_paid_call_outcome_known`).

        Lease-fenced, and this is the fence that matters most: a worker that lost
        its lease learns it here, *before* it spends the client's money. A hold that
        is no longer open refuses the dispatch: a call with no open hold behind it
        has no budget behind it, and recovery could not charge it.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        reservation = self._attempt_reservation(attempt_id, reservation_id)
        if reservation.status != ReservationStatus.RESERVED.value:
            raise ReservationClosed(reservation_id, reservation.status)
        reservation.paid_call_in_flight = True
        attempt.paid_call_dispatched = True
        attempt.paid_call_outcome_known = False
        if provider_request_id:
            attempt.provider_request_id = provider_request_id
        self._session.flush()

    def mark_paid_call_outcome_known(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        reservation_id: str,
        actual_cost_usd: float = 0.0,
        provider_request_id: str | None = None,
    ) -> None:
        """Record that the call dispatched against ``reservation_id`` has a known outcome.

        Once every dispatched call of the attempt has one, the attempt is safe to
        retry again if it later fails for an unrelated reason, because there is no
        longer an unresolved billing question.

        The cost is **added** to the attempt's known spend, which is charged when
        the attempt ends (:meth:`_close_open_reservations`) -- including when it
        ends in failure. Prefer :meth:`settle_paid_call`, which charges at once
        against the call's own reservation.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        reservation = self._attempt_reservation(attempt_id, reservation_id)
        reservation.paid_call_in_flight = False
        attempt.actual_cost_usd = float(attempt.actual_cost_usd or 0.0) + max(
            0.0, float(actual_cost_usd)
        )
        if provider_request_id:
            attempt.provider_request_id = provider_request_id
        self._session.flush()
        attempt.paid_call_outcome_known = self._paid_call_outcome_known(attempt)
        self._session.flush()

    def settle_paid_call(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        reservation_id: str,
        actual_cost_usd: float,
        provider_request_id: str | None = None,
    ) -> None:
        """Record one metered call's known outcome and charge its real cost.

        The per-call half of accounting transactionality: ``reserve`` →
        ``mark_paid_call_dispatched`` → send → ``settle_paid_call``, each committed
        on its own. The reservation is settled at the actual cost *now*, so an
        attempt that makes several calls and then fails still charges every call
        that completed, and an attempt that crashes afterwards has nothing left for
        the uncertain branch to over-charge.

        A call the provider rejected before billing is settled at zero. Settling a
        reservation twice is a no-op, so retrying after a lost acknowledgement
        charges once.

        Settling closes *this* call's question only. Another call of the same
        attempt still in flight keeps the attempt's outcome unknown, so a worker
        that dies now is ``RECOVERY_REQUIRED``, not retried.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        reservation = self._attempt_reservation(attempt_id, reservation_id)
        reservation.paid_call_in_flight = False
        if provider_request_id:
            attempt.provider_request_id = provider_request_id
        if reservation.status == ReservationStatus.RESERVED.value:
            actual = max(0.0, float(actual_cost_usd))
            attempt.actual_cost_usd = float(attempt.actual_cost_usd or 0.0) + actual
            reservation.status = ReservationStatus.SETTLED.value
            reservation.settled_amount_usd = actual
            reservation.settled_at = utcnow()
            self._charge_study(reservation.study_id, actual)
        self._session.flush()
        attempt.paid_call_outcome_known = self._paid_call_outcome_known(attempt)
        self._session.flush()

    def _attempt_reservation(self, attempt_id: str, reservation_id: str) -> BudgetReservationRow:
        """The hold ``reservation_id``, only if it belongs to ``attempt_id``."""
        reservation = self._session.scalar(
            select(BudgetReservationRow).where(
                BudgetReservationRow.reservation_id == reservation_id,
                BudgetReservationRow.attempt_id == attempt_id,
            )
        )
        if reservation is None:
            raise WorkflowNotFound(reservation_id)
        return reservation

    def _paid_call_outcome_known(self, attempt: StepAttemptRow) -> bool:
        """True when no paid call of ``attempt`` is dispatched and still unanswered.

        Derived from the holds, every time it is asked: an open hold whose call
        was dispatched (``paid_call_in_flight``) is a call that may already have
        been billed. The attempt's own ``paid_call_outcome_known`` column records
        this answer for readers; it is never the input to a decision, because a
        single flag cannot say "one of two calls answered".
        """
        in_flight = self._session.scalar(
            select(func.count())
            .select_from(BudgetReservationRow)
            .where(
                BudgetReservationRow.attempt_id == attempt.attempt_id,
                BudgetReservationRow.status == ReservationStatus.RESERVED.value,
                BudgetReservationRow.paid_call_in_flight.is_(True),
            )
        )
        return not in_flight

    def settle_reservation(self, reservation_id: str, *, actual_cost_usd: float) -> None:
        """Settle a reservation against the real cost and charge the study."""
        reservation = self._session.scalar(
            select(BudgetReservationRow).where(
                BudgetReservationRow.reservation_id == reservation_id,
                BudgetReservationRow.study_id == self.scope.study_id,
            )
        )
        if reservation is None:
            raise WorkflowNotFound(reservation_id)
        if reservation.status != ReservationStatus.RESERVED.value:
            return

        actual = max(0.0, float(actual_cost_usd))
        reservation.status = ReservationStatus.SETTLED.value
        reservation.settled_amount_usd = actual
        reservation.settled_at = utcnow()
        self._charge_study(reservation.study_id, actual)
        self._session.flush()

    def release_reservation(self, reservation_id: str, *, reason: str = "") -> None:
        """Release a reservation without charging.

        Used when a paid call failed *before* dispatch: nothing was billed, so the
        held budget returns to the study.
        """
        reservation = self._session.scalar(
            select(BudgetReservationRow).where(
                BudgetReservationRow.reservation_id == reservation_id,
                BudgetReservationRow.study_id == self.scope.study_id,
            )
        )
        if reservation is None:
            raise WorkflowNotFound(reservation_id)
        if reservation.status != ReservationStatus.RESERVED.value:
            return

        reservation.status = ReservationStatus.RELEASED.value
        reservation.settled_amount_usd = 0.0
        reservation.settled_at = utcnow()
        reservation.reason = reason or reservation.reason
        self._session.flush()

    def _settle_uncertain(self, attempt: StepAttemptRow) -> float:
        """Convert an attempt's reservations to uncertain actual exposure.

        The accounting decision behind ``RECOVERY_REQUIRED``. Money that *may*
        already be gone must appear as spent rather than available, because the
        alternative is a study that believes it has budget it does not have.
        Returns the exposure recorded.
        """
        reservations = self._session.scalars(
            select(BudgetReservationRow).where(
                BudgetReservationRow.attempt_id == attempt.attempt_id,
                BudgetReservationRow.status == ReservationStatus.RESERVED.value,
            )
        ).all()

        exposure = 0.0
        for reservation in reservations:
            amount = float(reservation.amount_usd or 0.0)
            exposure += amount
            reservation.status = ReservationStatus.SETTLED_UNCERTAIN.value
            reservation.settled_amount_usd = amount
            reservation.settled_at = utcnow()
            reservation.reason = "paid_external_call_side_effect_uncertain"
            # The reservation's own study, not this repository's: the cross-study
            # work queue recovers attempts without a study scope of its own.
            self._charge_study(reservation.study_id, amount)

        if exposure:
            attempt.actual_cost_usd = float(attempt.actual_cost_usd or 0.0) + exposure
        return exposure

    def _close_open_reservations(self, attempt: StepAttemptRow, *, reason: str) -> float:
        """Close every reservation an ending attempt still holds. Returns exposure.

        One rule for every way an attempt ends -- completed, failed, abandoned,
        released, recovered -- because accounting must not depend on *why* the work
        stopped:

        1. a call was dispatched and its outcome is unknown → every open
           reservation becomes ``SETTLED_UNCERTAIN`` actual exposure;
        2. otherwise, known spend not yet charged (recorded by
           :meth:`mark_paid_call_outcome_known`, or passed to completion) is
           settled onto the first open reservation, or charged directly when
           there is none;
        3. whatever is still open was never spent, and is released.

        Before this, two paths got it wrong. ``abandon_attempt`` closed nothing, so
        a cancelled paid step held its reservation forever and the study's
        available budget shrank permanently. And a failure *released* the
        reservation of a call whose cost was already known, so money that had been
        spent was never charged -- under-recorded spend, which the budget check then
        hands back out.
        """
        if attempt.paid_call_dispatched and not self._paid_call_outcome_known(attempt):
            return self._settle_uncertain(attempt)

        reservations = self._session.scalars(
            select(BudgetReservationRow)
            .where(BudgetReservationRow.attempt_id == attempt.attempt_id)
            .order_by(BudgetReservationRow.created_at, BudgetReservationRow.reservation_id)
        ).all()
        charged = sum(
            float(r.settled_amount_usd or 0.0)
            for r in reservations
            if r.status == ReservationStatus.SETTLED.value
        )
        unbilled = max(0.0, float(attempt.actual_cost_usd or 0.0) - charged)

        study_id: str | None = None
        for reservation in reservations:
            if reservation.status != ReservationStatus.RESERVED.value:
                continue
            study_id = reservation.study_id
            reservation.settled_at = utcnow()
            if unbilled > 1e-12:
                reservation.status = ReservationStatus.SETTLED.value
                reservation.settled_amount_usd = unbilled
                self._charge_study(reservation.study_id, unbilled)
                unbilled = 0.0
            else:
                reservation.status = ReservationStatus.RELEASED.value
                reservation.settled_amount_usd = 0.0
                reservation.reason = reason or reservation.reason

        if unbilled > 1e-12:
            # Known spend with no reservation behind it -- a cost reported at
            # completion for work that reserved nothing. Charged, not dropped.
            if study_id is None:
                step = self._session.scalar(
                    select(StepRunRow).where(StepRunRow.step_id == attempt.step_id)
                )
                run = (
                    self._session.scalar(
                        select(WorkflowRunRow).where(WorkflowRunRow.run_id == step.run_id)
                    )
                    if step is not None
                    else None
                )
                study_id = run.study_id if run is not None else None
            if study_id is not None:
                self._charge_study(study_id, unbilled)
        return 0.0

    def _charge_study(self, study_id: str, amount_usd: float) -> None:
        """Add to a study's recorded spend, atomically.

        **This must never be a read-modify-write.** It was one, and the result was
        a lost update: two reconcilers settling two different uncertain attempts
        each read ``spent_usd`` as 0 and each wrote 5, so a study that had spent
        $10 recorded $5. PostgreSQL runs READ COMMITTED, so each transaction saw
        the value as it stood before the other committed, and the last writer won.

        That surfaced once in CI as a flaky assertion. It is not flakiness: it is
        a client's spend being under-recorded, and under-recorded spend is
        headroom the budget check will then hand out. It is the same defect as the
        concurrent-overspend bug fixed in the reservation path, in the settlement
        half -- reserving was made safe and settling was not.

        ``UPDATE … SET spent_usd = spent_usd + :amount`` is evaluated by the
        database against the current row, and a concurrent writer blocks and then
        re-reads, so the increments compose. A ``SELECT … FOR UPDATE`` before the
        read would also be correct, but it holds a lock across the round trip for
        no gain over letting the database do the arithmetic.

        ``synchronize_session="fetch"`` refreshes any StudyRow already loaded in
        this session, so a caller that read the study before the charge does not
        keep a stale figure and write it back later.
        """
        amount = max(0.0, float(amount_usd))
        if not amount:
            return
        self._session.execute(
            update(StudyRow)
            .where(StudyRow.study_id == study_id)
            .values(spent_usd=StudyRow.spent_usd + amount)
            .execution_options(synchronize_session="fetch")
        )

    def budget_position(self) -> dict[str, float]:
        """Return the study's budget position including outstanding reservations."""
        self.scope.require(Permission.VIEW_COSTS)
        study = self._session.scalar(
            select(StudyRow).where(StudyRow.study_id == self.scope.study_id)
        )
        if study is None:
            raise WorkflowNotFound(self.scope.study_id)

        reserved = self._outstanding_reservations(self.scope.study_id)
        uncertain = self._session.scalar(
            select(func.coalesce(func.sum(BudgetReservationRow.settled_amount_usd), 0.0)).where(
                BudgetReservationRow.study_id == self.scope.study_id,
                BudgetReservationRow.status == ReservationStatus.SETTLED_UNCERTAIN.value,
            )
        )
        return {
            "budget_usd": study.budget_usd,
            "spent_usd": study.spent_usd,
            "reserved_usd": reserved,
            "uncertain_usd": float(uncertain or 0.0),
            "available_usd": max(0.0, study.budget_usd - study.spent_usd - reserved),
        }

    # ---------------------------------------------------------- finish or fail --

    def complete_attempt(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        output: dict[str, Any] | None = None,
        actual_cost_usd: float = 0.0,
        reservation_id: str | None = None,
    ) -> StepRunStatus:
        """Record a successful attempt and mark its step SUCCEEDED.

        Lease-fenced: only the worker holding the attempt may complete it, so a
        worker whose lease was recovered cannot put a second outcome on a step
        another worker is now running. Raises :class:`LeaseLost` otherwise.

        **Idempotent for its owner.** Completing an attempt this worker already
        completed returns ``SUCCEEDED`` and writes nothing. That is the retry of a
        commit whose acknowledgement was lost -- the first commit landed, the
        worker could not know -- and it must not charge the study a second time.
        """
        attempt = self._locked_attempt(attempt_id)
        if attempt.status == AttemptStatus.SUCCEEDED.value and attempt.worker_id == worker_id:
            return StepRunStatus.SUCCEEDED
        self._require_lease(attempt, worker_id)
        step = self._step(attempt.step_id)
        self._lock_run_for(step)

        attempt.status = AttemptStatus.SUCCEEDED.value
        attempt.finished_at = utcnow()
        attempt.output_json = output or {}
        attempt.lease_until = None

        if reservation_id:
            self.settle_reservation(reservation_id, actual_cost_usd=actual_cost_usd)
            attempt.actual_cost_usd = max(
                float(attempt.actual_cost_usd or 0.0), max(0.0, float(actual_cost_usd))
            )
        elif actual_cost_usd:
            attempt.actual_cost_usd = float(attempt.actual_cost_usd or 0.0) + max(
                0.0, float(actual_cost_usd)
            )
        # A completed attempt whose paid call has no recorded outcome still owes an
        # answer about that money: the closing rule settles it as uncertain rather
        # than releasing it. The flag is set only after the rule has looked.
        self._close_open_reservations(attempt, reason="completed")
        attempt.paid_call_outcome_known = True

        step.status = StepRunStatus.SUCCEEDED.value
        step.output_json = output or {}
        step.finished_at = utcnow()
        step.waiting_reason = None
        step.runnable_after = None
        step.updated_at = utcnow()

        self._event(
            step.run_id,
            event_type="STEP_SUCCEEDED",
            message=f"{step.node_key} completed",
            payload={"attempt_number": attempt.attempt_number},
            step_id=step.step_id,
            attempt_id=attempt_id,
        )
        self._session.flush()
        self.release_ready_steps(step.run_id)
        self._refresh_run(step.run_id)
        self._session.flush()
        return StepRunStatus.SUCCEEDED

    def fail_attempt(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        failure: FailureClass,
        error: dict[str, Any] | None = None,
        reservation_id: str | None = None,
        quota_reset_at: datetime | None = None,
    ) -> RecoveryDecision:
        """Record a failed attempt and apply the recovery decision.

        The decision comes from :func:`aia_core.domain.workflow.decide_recovery`;
        this method executes it -- including converting a reservation to
        ``SETTLED_UNCERTAIN`` when a dispatched paid call's outcome is unknown.

        Lease-fenced like :meth:`complete_attempt`; raises :class:`LeaseLost` when
        the caller no longer holds the attempt.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)

        attempt.status = AttemptStatus.FAILED.value
        attempt.failure_class = failure.value
        attempt.error_json = error or {}
        attempt.finished_at = utcnow()
        attempt.lease_until = None

        # The retry limit is checked against consumed attempts, not recorded
        # ones: a step parked three times on quota has used no retries.
        decision = decide_recovery(
            failure=failure,
            attempt_number=step.attempts_consumed,
            max_attempts=step.max_attempts,
            paid_call_dispatched=attempt.paid_call_dispatched,
            paid_call_outcome_known=self._paid_call_outcome_known(attempt),
            quota_reset_at=quota_reset_at,
        )
        return self._apply_recovery(step, attempt, decision, reservation_id=reservation_id)

    def defer_attempt(
        self,
        attempt_id: str,
        *,
        worker_id: str,
        children: Sequence[StepDefinition],
        child_inputs: dict[str, dict[str, Any]] | None = None,
        child_fingerprints: dict[str, str] | None = None,
        output: dict[str, Any] | None = None,
    ) -> StepRunStatus:
        """End an attempt that handed its work to child steps; the step waits for them.

        In one unit of work: each child is added to the run (``RUNNABLE``, at the
        parent's priority, after every existing step) unless a step with its node key
        already exists -- the same work handed out again names the same child -- and
        the parent depends on every child; the attempt ends ``DEFERRED`` and its open
        holds are closed by the one closing rule; the parent becomes ``BLOCKED`` and
        is released, as a new attempt, by :meth:`release_ready_steps` when every
        child has succeeded (at once, when they all already have). The attempt does
        not count against ``max_attempts`` (:func:`decide_deferral`).

        A child that fails stalls the parent, and the run reads ``FAILED`` or
        ``RECOVERY_REQUIRED`` from it, exactly as a failed upstream step would. A
        cancellation that arrived meanwhile cancels the parent and adds no child; a
        paid call in flight with no known outcome makes the parent
        ``RECOVERY_REQUIRED`` and adds no child either.

        Lease-fenced like :meth:`complete_attempt`.
        """
        definitions = list(children)
        if not definitions:
            raise ValueError("a deferral names at least one child step")
        keys = [d.node_key for d in definitions]
        if len(set(keys)) != len(keys):
            raise ValueError("a deferral names each child once")
        if any(d.depends_on for d in definitions):
            raise ValueError("a child depends on nothing but its parent's progress")

        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)
        self._lock_run_for(step)
        existing = {
            row.node_key: row
            for row in self._session.scalars(
                select(StepRunRow).where(StepRunRow.run_id == step.run_id)
            ).all()
        }
        if step.node_key in keys:
            raise ValueError("a step cannot be its own child")
        clash = sorted(
            d.node_key
            for d in definitions
            if d.node_key in existing and existing[d.node_key].kind != d.kind
        )
        if clash:
            raise ValueError(f"node keys already name other steps of this run: {clash}")

        attempt.status = AttemptStatus.DEFERRED.value
        attempt.finished_at = utcnow()
        attempt.lease_until = None
        attempt.output_json = output or {}

        decision = apply_cancellation(
            decide_deferral(
                paid_call_dispatched=attempt.paid_call_dispatched,
                paid_call_outcome_known=self._paid_call_outcome_known(attempt),
            ),
            cancel_requested=step.cancel_requested,
        )
        exposure = self._close_open_reservations(attempt, reason=decision.reason)
        if not decision.consumes_attempt and step.attempts_consumed > 0:
            step.attempts_consumed -= 1

        added: list[str] = []
        if decision.action is RecoveryAction.DEFER:
            ordinal = max((s.ordinal for s in existing.values()), default=0)
            depends = set(
                self._session.scalars(
                    select(StepDependencyRow.depends_on_step_id).where(
                        StepDependencyRow.step_id == step.step_id
                    )
                ).all()
            )
            for definition in definitions:
                child = existing.get(definition.node_key)
                if child is None:
                    ordinal += 1
                    child = StepRunRow(
                        step_id=new_step_id(),
                        run_id=step.run_id,
                        node_key=definition.node_key,
                        kind=definition.kind,
                        status=StepRunStatus.RUNNABLE.value,
                        ordinal=ordinal,
                        priority=step.priority,
                        stage_type=definition.stage_type,
                        artifact_target=definition.artifact_target,
                        interaction_mode=definition.interaction_mode.value,
                        input_fingerprint=(child_fingerprints or {}).get(definition.node_key, ""),
                        max_attempts=definition.max_attempts,
                        input_json=(child_inputs or {}).get(definition.node_key, {}),
                    )
                    self._session.add(child)
                    self._session.flush()
                    added.append(definition.node_key)
                if child.step_id not in depends:
                    self._session.add(
                        StepDependencyRow(step_id=step.step_id, depends_on_step_id=child.step_id)
                    )
                    depends.add(child.step_id)

        step.status = decision.step_status.value
        step.waiting_reason = None
        step.runnable_after = None
        step.updated_at = utcnow()
        if decision.step_status.is_terminal:
            step.finished_at = utcnow()

        payload: dict[str, Any] = {
            "action": decision.action.value,
            "reason": decision.reason,
            "attempt_number": attempt.attempt_number,
            "children": len(definitions),
            "added": len(added),
        }
        if exposure:
            payload["conservative_cost_exposure_usd"] = exposure
        self._event(
            step.run_id,
            event_type="STEP_DEFERRED",
            message=f"{step.node_key}: {decision.reason}",
            payload=payload,
            step_id=step.step_id,
            attempt_id=attempt.attempt_id,
            level="WARN" if decision.needs_human else "INFO",
        )
        self._session.flush()
        if decision.action is RecoveryAction.DEFER:
            # Children that already succeeded (the same work handed out again)
            # release the parent at once.
            self.release_ready_steps(step.run_id)
        self._refresh_run(step.run_id)
        self._session.flush()
        self._session.refresh(step)
        return StepRunStatus(step.status)

    def _apply_recovery(
        self,
        step: StepRunRow,
        attempt: StepAttemptRow,
        decision: RecoveryDecision,
        *,
        reservation_id: str | None = None,
    ) -> RecoveryDecision:
        """Apply a recovery decision to a step and its reservations.

        Returns the decision actually applied, which differs from the one passed
        in when the run was cancelled while the attempt was in flight
        (:func:`aia_core.domain.workflow.apply_cancellation`).
        """
        self._lock_run_for(step)
        decision = apply_cancellation(decision, cancel_requested=step.cancel_requested)
        # `settle_reservation_as_uncertain` is true exactly when a dispatched
        # call's outcome is unknown, which is the first branch of the closing
        # rule -- so the rule applies it, and applies it on every other path too.
        exposure = self._close_open_reservations(attempt, reason=decision.reason)
        if reservation_id:
            # Legacy callers name a reservation; one belonging to this attempt is
            # already closed, and this is a no-op for it.
            self.release_reservation(reservation_id, reason=decision.reason)

        # A non-consuming failure -- quota, budget, approval -- must not count
        # against max_attempts. None is a failure of the work, and counting them
        # would eventually fail a project that was only waiting.
        if not decision.consumes_attempt and step.attempts_consumed > 0:
            step.attempts_consumed -= 1

        step.status = decision.step_status.value
        step.waiting_reason = decision.reason if decision.step_status.is_waiting else None
        step.runnable_after = decision.retry_after
        step.updated_at = utcnow()
        if decision.step_status.is_terminal:
            step.finished_at = utcnow()

        payload: dict[str, Any] = {
            "action": decision.action.value,
            "reason": decision.reason,
            "attempt_number": attempt.attempt_number,
            "consumes_attempt": decision.consumes_attempt,
        }
        if exposure:
            payload["conservative_cost_exposure_usd"] = exposure
        if decision.retry_after:
            payload["retry_after"] = decision.retry_after.isoformat()

        self._event(
            step.run_id,
            event_type="STEP_RECOVERY",
            message=f"{step.node_key}: {decision.reason}",
            payload=payload,
            step_id=step.step_id,
            attempt_id=attempt.attempt_id,
            level="WARN" if decision.needs_human else "INFO",
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()
        return decision

    # -------------------------------------------------------------- reconciler --

    def recover_expired_attempts(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> list[RecoveryDecision]:
        """Recover attempts whose lease lapsed. Returns the decisions applied.

        This is what makes a worker crash survivable. It is safe to run
        concurrently: each attempt is locked with ``FOR UPDATE SKIP LOCKED`` on
        PostgreSQL, so two reconcilers cannot both recover the same attempt and
        double-count its exposure.
        """
        moment = now or datetime.now(UTC)

        query = (
            select(StepAttemptRow)
            .join(StepRunRow, StepRunRow.step_id == StepAttemptRow.step_id)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(
                StepAttemptRow.status.in_(
                    [AttemptStatus.CLAIMED.value, AttemptStatus.EXECUTING.value]
                ),
                *self._scope_filter(),
            )
            # Run order, so concurrent reconcilers take run locks (`_lock_run`) in
            # one order and cannot wait on each other in a cycle.
            .order_by(StepRunRow.run_id, StepAttemptRow.attempt_id)
            .limit(max(1, int(limit)))
        )
        if self._is_postgres:
            # Only lapsed leases are selected, and so locked. Selecting every live
            # attempt too made each sweep hold the lock on attempts whose workers
            # were heartbeating and finishing them, so those workers waited on the
            # sweep. The Python check below stays authoritative; SQLite, which
            # returns naive timestamps, relies on it alone.
            query = query.where(
                (StepAttemptRow.lease_until.is_(None)) | (StepAttemptRow.lease_until <= moment)
            ).with_for_update(skip_locked=True, of=StepAttemptRow)

        decisions: list[RecoveryDecision] = []
        for attempt in self._session.scalars(query).all():
            if not is_lease_expired(attempt.lease_until, now=moment):
                continue

            step = self._session.scalar(
                select(StepRunRow).where(StepRunRow.step_id == attempt.step_id)
            )
            if step is None:  # pragma: no cover - guaranteed by the join
                continue

            attempt.status = AttemptStatus.EXPIRED.value
            attempt.finished_at = utcnow()
            attempt.lease_until = None

            # `failure=None` means "the lease lapsed", not "the work failed": the
            # worker died without reporting anything.
            decision = decide_recovery(
                failure=None,
                attempt_number=step.attempts_consumed,
                max_attempts=step.max_attempts,
                paid_call_dispatched=attempt.paid_call_dispatched,
                paid_call_outcome_known=self._paid_call_outcome_known(attempt),
            )
            decisions.append(self._apply_recovery(step, attempt, decision))

        return decisions

    def release_attempt(
        self, attempt_id: str, *, worker_id: str, reason: str = "worker_shutdown"
    ) -> RecoveryDecision:
        """Give an attempt back without failing it -- a clean worker shutdown.

        The step is ``RUNNABLE`` again immediately, so another worker can pick it
        up without waiting for the lease to lapse, and the attempt does not count
        against ``max_attempts``. A paid call in flight with unknown outcome makes
        it ``RECOVERY_REQUIRED`` instead, exactly as a crash would
        (:func:`aia_core.domain.workflow.decide_release`). Lease-fenced.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)

        attempt.status = AttemptStatus.ABANDONED.value
        attempt.finished_at = utcnow()
        attempt.lease_until = None
        attempt.error_json = {"reason": reason}

        decision = decide_release(
            paid_call_dispatched=attempt.paid_call_dispatched,
            paid_call_outcome_known=self._paid_call_outcome_known(attempt),
        )
        return self._apply_recovery(step, attempt, decision)

    def resume_waiting_steps(
        self,
        *,
        now: datetime | None = None,
        capacity_backoff_seconds: int = DEFAULT_CAPACITY_BACKOFF_SECONDS,
        quota_fallback_seconds: int = DEFAULT_QUOTA_FALLBACK_SECONDS,
        limit: int = 100,
    ) -> list[str]:
        """Offer parked provider waits to workers again. Returns the step ids.

        Only ``WAITING_PROVIDER`` and ``WAITING_CAPACITY`` are considered, and the
        rule for each is :func:`aia_core.domain.workflow.resume_due`. Nothing a
        person owes a decision on -- ``AWAITING_*``, ``RECOVERY_REQUIRED`` -- is
        ever touched here.

        Before this existed nothing moved a park back to ``RUNNABLE``, so a quota
        wall or a capacity blip stranded its step until an operator forced it.

        Safe to run concurrently: steps are locked ``FOR UPDATE SKIP LOCKED`` on
        PostgreSQL, so two workers sweeping at once resume each step once.
        """
        moment = now or datetime.now(UTC)
        query = (
            select(StepRunRow)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
            .where(
                StepRunRow.status.in_(
                    [StepRunStatus.WAITING_PROVIDER.value, StepRunStatus.WAITING_CAPACITY.value]
                ),
                StepRunRow.cancel_requested.is_(False),
                WorkflowRunRow.cancel_requested.is_(False),
                *self._scope_filter(),
            )
            .order_by(StepRunRow.updated_at)
            .limit(max(1, int(limit)))
        )
        if self._is_postgres:
            # The run row too, and skipped when locked: `_lock_run` order is
            # run → steps, and a run a worker is finishing a step in right now is
            # simply resumed on the next sweep.
            query = query.with_for_update(skip_locked=True, of=(StepRunRow, WorkflowRunRow))

        resumed: list[str] = []
        touched_runs: set[str] = set()
        for step in self._session.scalars(query).all():
            if not resume_due(
                StepRunStatus(step.status),
                runnable_after=step.runnable_after,
                parked_at=step.updated_at,
                now=moment,
                capacity_backoff_seconds=capacity_backoff_seconds,
                quota_fallback_seconds=quota_fallback_seconds,
                waiting_reason=step.waiting_reason,
            ):
                continue
            previous = step.status
            step.status = StepRunStatus.RUNNABLE.value
            step.waiting_reason = None
            step.runnable_after = None
            step.updated_at = utcnow()
            resumed.append(step.step_id)
            touched_runs.add(step.run_id)
            self._event(
                step.run_id,
                event_type="STEP_RESUMED",
                message=f"{step.node_key}: {previous} -> RUNNABLE",
                payload={"from": previous},
                step_id=step.step_id,
            )

        if resumed:
            self._session.flush()
            for run_id in sorted(touched_runs):
                self._refresh_run(run_id)
            self._session.flush()
        return resumed

    def resume_runtime_park(self, step_id: str) -> bool:
        """Reoffer an unbilled runtime park after an explicit researcher action.

        The Study scope and the run lock guard this transition. A repeated action
        after the first has made the step runnable or claimed is a no-op; an
        uncertain or already billed attempt can never enter through this path.
        """
        self.scope.require(Permission.RUN_WORKFLOW)
        step = self._step(step_id)
        self._lock_run_for(step)
        if StepRunStatus(step.status) in (StepRunStatus.RUNNABLE, StepRunStatus.RUNNING):
            return False
        run = self._run(step.run_id)
        self._session.refresh(run)
        dispatched = bool(
            self._session.scalar(
                select(func.count())
                .select_from(StepAttemptRow)
                .where(
                    StepAttemptRow.step_id == step_id,
                    StepAttemptRow.paid_call_dispatched.is_(True),
                )
            )
        )
        if not runtime_park_can_resume(
            StepRunStatus(step.status),
            waiting_reason=step.waiting_reason,
            paid_call_dispatched=dispatched,
            cancel_requested=bool(run.cancel_requested or step.cancel_requested),
            attempts_consumed=step.attempts_consumed,
            max_attempts=step.max_attempts,
        ):
            raise RuntimeParkNotResumable("only an unbilled runtime park may be resumed")
        step.status = StepRunStatus.RUNNABLE.value
        step.waiting_reason = None
        step.runnable_after = None
        step.updated_at = utcnow()
        self._event(
            step.run_id,
            event_type="STEP_RESUMED",
            message=f"{step.node_key}: runtime enabled; offered after user action",
            payload={"from": StepRunStatus.WAITING_PROVIDER.value, "actor_id": self.scope.actor_id},
            step_id=step_id,
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()
        return True

    def resume_budget_wait(
        self, step_id: str, *, note: str = "", budget_before: float, budget_after: float
    ) -> None:
        """Let a step that stopped at the budget cap go on, after a person lifts the cap.

        A reservation that would pass the study's budget parks the step in
        ``AWAITING_BUDGET`` without spending an attempt, and nothing resumed it: the
        provider sweep never touches an ``AWAITING_*`` step, and raising the budget
        only changes a number (plan 5b.1). This is the person's act. It needs
        ``APPROVE_BUDGET``, which the worker's scope does not hold (ADR 0019 decision
        6), and writes the decision to the append-only approval ledger like a gate.

        The caller raises the budget first (``ScopeRepository.set_study_budget``, which
        audits it) and passes both figures so the event shows what was lifted. The step
        becomes runnable again; if the budget is still too small it parks again at the
        next reservation. Refused when the step is not waiting for budget, which also
        makes a second lift a no-op, and when the run is being cancelled.
        """
        self.scope.require(Permission.APPROVE_BUDGET)
        step = self._step(step_id)
        self._lock_run_for(step)
        run = self._run(step.run_id)
        self._session.refresh(run)
        if StepRunStatus(step.status) is not StepRunStatus.AWAITING_BUDGET:
            raise BudgetWaitNotLiftable("only a step waiting for budget can be lifted")
        if run.cancel_requested or step.cancel_requested:
            raise BudgetWaitNotLiftable("a run that is being cancelled is not resumed")

        independence = observe_approval_independence(
            producer_user_id=run.triggered_by,
            approving_user_id=self.scope.actor_id,
            policy=self.scope.self_approval,
        )
        self._session.add(
            ApprovalDecisionRow(
                organization_id=self.scope.organization_id,
                client_id=self.scope.client_id,
                study_id=self.scope.study_id,
                subject_type="budget",
                subject_id=step_id,
                run_id=step.run_id,
                step_id=step_id,
                gate_type="budget",
                decision="lift",
                comment=note,
                request_id=self.scope.request_id,
                **independence.audit_fields(),
            )
        )
        step.status = StepRunStatus.RUNNABLE.value
        step.waiting_reason = None
        step.runnable_after = None
        step.updated_at = utcnow()
        self._event(
            step.run_id,
            event_type="STEP_RESUMED",
            message=(
                f"{step.node_key}: budget lifted from {budget_before:.2f} to {budget_after:.2f}"
            ),
            payload={
                "from": StepRunStatus.AWAITING_BUDGET.value,
                "actor_id": self.scope.actor_id,
                "budget_before_usd": budget_before,
                "budget_after_usd": budget_after,
                "note": note,
                **independence.audit_fields(),
            },
            step_id=step_id,
            level="WARN" if independence.self_approved else "INFO",
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()

    def record_spend_confirmation(
        self, run_id: str, *, ceiling_usd: float, limit_usd: float, confirmed_usd: float
    ) -> None:
        """Write the person's yes to what a run can cost, in the append-only approval ledger.

        The start of a research run asks when its cost ceiling reaches the study's limit
        (plan 5b.2). The person who starts it is the one who confirms, so the row records
        who, whether that was the run's own starter, and the three figures: the ceiling the
        server worked out, the limit it was held against, and what the person confirmed.
        Needs ``APPROVE_BUDGET``, which the worker's scope does not hold (ADR 0019
        decision 6): a step cannot confirm the spend it is about to make.
        """
        self.scope.require(Permission.APPROVE_BUDGET)
        run = self._run(run_id)
        independence = observe_approval_independence(
            producer_user_id=run.triggered_by,
            approving_user_id=self.scope.actor_id,
            policy=self.scope.self_approval,
        )
        self._session.add(
            ApprovalDecisionRow(
                organization_id=self.scope.organization_id,
                client_id=self.scope.client_id,
                study_id=self.scope.study_id,
                subject_type="spend",
                subject_id=run_id,
                run_id=run_id,
                gate_type="spend",
                decision="confirm",
                comment=json.dumps(
                    {
                        "ceiling_usd": ceiling_usd,
                        "limit_usd": limit_usd,
                        "confirmed_usd": confirmed_usd,
                    },
                    sort_keys=True,
                ),
                request_id=self.scope.request_id,
                **independence.audit_fields(),
            )
        )
        self._session.flush()

    def record_ai_proposal_acceptance(
        self,
        run_id: str,
        *,
        action: str,
        revision_id: str,
        project_id: str,
        project_revision: int,
        created: bool,
        artifact_id: str,
    ) -> bool:
        """Write a person's accept of what an agent job proposed, once, in the approval ledger.

        ADR 0019 gate 1 (plan 5b.3): "who accepted what the AI produced" is answered by the same
        append-only ledger as every other decision. The row names the job (``subject_id``), what
        it was asked to do (``gate_type``), who asked (``producer_user_id``, the job's starter),
        who accepted and whether that was the same person, and in ``comment`` the Design Revision
        the accept wrote, whether it was a new one, and the proposal artifact.

        Needs ``APPROVE_GATE``, which the worker's scope does not hold (ADR 0019 decision 6).
        Returns ``False`` and writes nothing when this job's accept is already recorded: an
        unchanged proposal can be accepted again, and that is not a second decision. The caller
        holds the Study row lock (``StudyDesignRepository.submit_if_current``), so two accepts
        cannot both pass the check.
        """
        self.scope.require(Permission.APPROVE_GATE)
        run = self._run(run_id)
        recorded = self._session.scalar(
            select(ApprovalDecisionRow.decision_id).where(
                ApprovalDecisionRow.study_id == self.scope.study_id,
                ApprovalDecisionRow.subject_type == "ai_proposal",
                ApprovalDecisionRow.subject_id == run_id,
            )
        )
        if recorded is not None:
            return False
        independence = observe_approval_independence(
            producer_user_id=run.triggered_by,
            approving_user_id=self.scope.actor_id,
            policy=self.scope.self_approval,
        )
        self._session.add(
            ApprovalDecisionRow(
                organization_id=self.scope.organization_id,
                client_id=self.scope.client_id,
                study_id=self.scope.study_id,
                subject_type="ai_proposal",
                subject_id=run_id,
                run_id=run_id,
                project_id=project_id,
                project_revision=project_revision,
                artifact_type="research_agent_proposal",
                gate_type=action,
                decision="accept",
                comment=json.dumps(
                    {
                        "revision_id": revision_id,
                        "revision_created": created,
                        "artifact_id": artifact_id,
                    },
                    sort_keys=True,
                ),
                request_id=self.scope.request_id,
                **independence.audit_fields(),
            )
        )
        self._session.flush()
        return True

    # ------------------------------------------------------------ cancellation --

    def request_cancel(self, run_id: str, *, reason: str = "") -> WorkflowRunStatus:
        """Request cancellation of a run.

        Cooperative for work in flight: a running step is flagged and its worker
        notices at the next checkpoint, so cancellation leaves a consistent
        artifact state rather than a half-written one. Steps not yet started are
        cancelled immediately, and pending gates are closed so nothing is left in
        someone's queue.
        """
        self.scope.require(Permission.CANCEL_WORKFLOW)
        run = self._run(run_id)
        if WorkflowRunStatus(run.status).is_terminal:
            return WorkflowRunStatus(run.status)

        run.cancel_requested = True
        run.updated_at = utcnow()

        steps = self._session.scalars(select(StepRunRow).where(StepRunRow.run_id == run_id)).all()
        for step in steps:
            step.cancel_requested = True
            if step.status == StepRunStatus.RUNNING.value:
                continue  # cooperative: the worker will notice
            if not StepRunStatus(step.status).is_terminal:
                step.status = StepRunStatus.CANCELLED.value
                step.finished_at = utcnow()
            step.updated_at = utcnow()

        self._session.execute(
            update(WorkflowGateRow)
            .where(
                WorkflowGateRow.run_id == run_id,
                WorkflowGateRow.status == "PENDING",
            )
            .values(status="CANCELLED", decided_at=utcnow())
        )

        self._event(
            run_id,
            event_type="RUN_CANCEL_REQUESTED",
            message=reason or "cancellation requested",
            payload={"reason": reason, "actor_id": self.scope.actor_id},
            level="WARN",
        )
        self._session.flush()
        return self._refresh_run(run_id)

    def is_cancel_requested(self, step_id: str) -> bool:
        """True when a worker should stop at its next checkpoint."""
        step = self._step(step_id)
        return bool(step.cancel_requested)

    def abandon_attempt(
        self, attempt_id: str, *, worker_id: str, reason: str = "cancelled"
    ) -> None:
        """Mark an in-flight attempt abandoned after a cooperative cancellation.

        Lease-fenced; raises :class:`LeaseLost` when the caller no longer holds
        the attempt.
        """
        attempt = self._held_attempt(attempt_id, worker_id=worker_id)
        step = self._step(attempt.step_id)
        self._lock_run_for(step)

        attempt.status = AttemptStatus.ABANDONED.value
        attempt.finished_at = utcnow()
        attempt.lease_until = None
        attempt.error_json = {"reason": reason}
        # A cancelled paid step must give its hold back -- or, if a call is in
        # flight with no known outcome, record it as uncertain exposure.
        exposure = self._close_open_reservations(attempt, reason=reason)

        step.status = StepRunStatus.CANCELLED.value
        step.finished_at = utcnow()
        step.updated_at = utcnow()

        self._event(
            step.run_id,
            event_type="ATTEMPT_ABANDONED",
            message=f"{step.node_key}: {reason}",
            payload={"conservative_cost_exposure_usd": exposure} if exposure else None,
            step_id=step.step_id,
            attempt_id=attempt_id,
            level="WARN",
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()

    # -------------------------------------------------------------------- gates --

    def open_gate(
        self,
        *,
        step_id: str,
        question: str,
        options: list[str],
        context: dict[str, Any] | None = None,
        gate_type: str = "approval",
        produced_by_user_id: str | None = None,
    ) -> str:
        """Park a step on a human decision.

        The gate records who produced the work, so the separation-of-duties check
        on decision has something to compare against.
        """
        step = self._step(step_id)
        if not options:
            raise ValueError("a gate must offer at least one option")
        self._lock_run_for(step)

        gate_id = "GATE-" + new_attempt_id()[4:]
        self._session.add(
            WorkflowGateRow(
                gate_id=gate_id,
                run_id=step.run_id,
                step_id=step_id,
                status="PENDING",
                gate_type=gate_type,
                question=question,
                options_json={"options": list(options)},
                context_json=context or {},
                produced_by_user_id=produced_by_user_id or self.scope.actor_id,
            )
        )
        step.status = StepRunStatus.AWAITING_GATE.value
        step.waiting_reason = f"gate:{gate_type}"
        step.updated_at = utcnow()

        self._event(
            step.run_id,
            event_type="GATE_OPENED",
            message=question,
            payload={"gate_id": gate_id, "options": list(options), "gate_type": gate_type},
            step_id=step_id,
            level="WARN",
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()
        return gate_id

    def decide_gate(self, gate_id: str, *, option: str, note: str = "") -> StepRunStatus:
        """Record a human decision on a gate and release or stop the step.

        Three checks, and each has bitten a real system:

        1. The option must be one of those offered. Accepting an arbitrary string
           means acting on a decision nobody made.
        2. The gate must still be pending, so a replayed request cannot re-decide.
        3. For an ``approval`` gate the decider must not be the producer where a
           level of the scope hierarchy has turned self-approval off. Since ADR 0019
           self-approval is allowed by default and a Researcher holds both edit and
           approval authority, so the permission check alone cannot stop one person
           authoring and approving; the policy check is what makes independent
           review a deliberate, configured choice for a scope that wants it. Gates
           that are not approvals record the same facts without enforcing
           independence.

        ``APPROVE_GATE`` is required either way. Policy permitting self-approval
        never substitutes for the permission: it only removes the independence
        objection for someone who could already approve.

        Every decision is written to the append-only ``approval_decisions``
        ledger, with the policy that allowed it and where that policy came from.
        """
        self.scope.require(Permission.APPROVE_GATE)

        gate = self._session.scalar(
            select(WorkflowGateRow)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == WorkflowGateRow.run_id)
            .where(WorkflowGateRow.gate_id == gate_id, *self._scope_filter())
        )
        if gate is None:
            raise WorkflowNotFound(gate_id)
        if gate.status != "PENDING":
            raise ValueError("gate already decided")

        allowed = list((gate.options_json or {}).get("options") or [])
        if option not in allowed:
            raise ValueError(
                f"invalid gate option {option!r}; allowed: {', '.join(sorted(allowed))}"
            )

        independence: ApprovalIndependence
        if gate.gate_type == "approval":
            independence = require_approval_independence(
                producer_user_id=gate.produced_by_user_id,
                approving_user_id=self.scope.actor_id,
                policy=self.scope.self_approval,
                what="this gate's work",
            )
        else:
            # A clarification or methodology question is not a sign-off, and the
            # producer is often the only person who can answer it. Recorded, not
            # gated.
            independence = observe_approval_independence(
                producer_user_id=gate.produced_by_user_id,
                approving_user_id=self.scope.actor_id,
                policy=self.scope.self_approval,
            )

        gate.status = "DECIDED"
        gate.decision_json = {"option": option, "note": note, **independence.audit_fields()}
        gate.decided_by_user_id = self.scope.actor_id
        gate.decided_at = utcnow()

        self._session.add(
            ApprovalDecisionRow(
                organization_id=self.scope.organization_id,
                client_id=self.scope.client_id,
                study_id=self.scope.study_id,
                subject_type="gate",
                subject_id=gate_id,
                run_id=gate.run_id,
                step_id=gate.step_id,
                gate_type=gate.gate_type,
                decision=option,
                comment=note,
                request_id=self.scope.request_id,
                **independence.audit_fields(),
            )
        )

        step = self._step(gate.step_id)
        self._lock_run_for(step)
        if option == "cancel":
            step.status = StepRunStatus.CANCELLED.value
            step.finished_at = utcnow()
            resulting = StepRunStatus.CANCELLED
        else:
            step.status = StepRunStatus.RUNNABLE.value
            resulting = StepRunStatus.RUNNABLE
        step.waiting_reason = None
        step.updated_at = utcnow()

        self._event(
            gate.run_id,
            event_type="GATE_DECIDED",
            message=f"{option} by {self.scope.actor_id}",
            payload={
                "gate_id": gate_id,
                "option": option,
                "note": note,
                **independence.audit_fields(),
            },
            step_id=gate.step_id,
            level="WARN" if independence.self_approved else "INFO",
        )
        self._session.flush()
        self._refresh_run(gate.run_id)
        self._session.flush()
        return resulting

    def decided_gates(self, step_id: str) -> list[dict[str, Any]]:
        """Return the decisions recorded on a step's gates, oldest first.

        What an executor re-running after a gate needs: without it, a step that
        parked to ask for approval would ask again on every attempt.
        """
        self._step(step_id)
        rows = self._session.scalars(
            select(WorkflowGateRow)
            .where(WorkflowGateRow.step_id == step_id, WorkflowGateRow.status == "DECIDED")
            .order_by(WorkflowGateRow.decided_at, WorkflowGateRow.gate_id)
        ).all()
        return [
            {
                "gate_id": g.gate_id,
                "gate_type": g.gate_type,
                "question": g.question,
                "option": str((g.decision_json or {}).get("option", "")),
                "note": str((g.decision_json or {}).get("note", "")),
                "decided_by_user_id": g.decided_by_user_id,
                "decided_at": g.decided_at,
            }
            for g in rows
        ]

    def pending_gates(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """Return gates awaiting a decision, newest last."""
        query = (
            select(WorkflowGateRow)
            .join(WorkflowRunRow, WorkflowRunRow.run_id == WorkflowGateRow.run_id)
            .where(WorkflowGateRow.status == "PENDING", *self._scope_filter())
            .order_by(WorkflowGateRow.created_at)
        )
        if run_id:
            query = query.where(WorkflowGateRow.run_id == run_id)

        return [
            {
                "gate_id": g.gate_id,
                "run_id": g.run_id,
                "step_id": g.step_id,
                "gate_type": g.gate_type,
                "question": g.question,
                "options": list((g.options_json or {}).get("options") or []),
                "context": dict(g.context_json or {}),
                "produced_by_user_id": g.produced_by_user_id,
                "created_at": g.created_at,
            }
            for g in self._session.scalars(query).all()
        ]

    # -------------------------------------------------------------------- reads --

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return a run with its steps and each step's attempt history."""
        run = self._run(run_id)
        steps = self._session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id).order_by(StepRunRow.ordinal)
        ).all()

        binding_row = self._binding_row(run_id)
        return {
            "run_id": run.run_id,
            "status": WorkflowRunStatus(run.status),
            "workflow_type": run.workflow_type,
            "project_id": run.project_id,
            "project_revision": run.project_revision,
            "cancel_requested": run.cancel_requested,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "metadata": dict(run.metadata_json or {}),
            "population": _binding(binding_row).as_record() if binding_row is not None else None,
            "steps": [
                {
                    "step_id": s.step_id,
                    "node_key": s.node_key,
                    "kind": s.kind,
                    "status": StepRunStatus(s.status),
                    "stage_type": s.stage_type,
                    "attempts_recorded": s.attempts_recorded,
                    "attempts_consumed": s.attempts_consumed,
                    "max_attempts": s.max_attempts,
                    "waiting_reason": s.waiting_reason,
                    "runnable_after": s.runnable_after,
                    "updated_at": s.updated_at,
                    "finished_at": s.finished_at,
                    "output": dict(s.output_json or {}),
                    "attempts": self.attempt_history(s.step_id),
                }
                for s in steps
            ],
        }

    def attempt_history(self, step_id: str) -> list[dict[str, Any]]:
        """Return every attempt for a step, oldest first.

        Append-only: a step that failed three different ways retains all three
        errors, each with its own provider, model, cost and timing. The prototype
        kept only the latest.
        """
        rows = self._session.scalars(
            select(StepAttemptRow)
            .where(StepAttemptRow.step_id == step_id)
            .order_by(StepAttemptRow.attempt_number)
        ).all()
        return [
            {
                "attempt_id": a.attempt_id,
                "attempt_number": a.attempt_number,
                "status": AttemptStatus(a.status),
                "worker_id": a.worker_id,
                "provider": a.provider,
                "model": a.model,
                "failure_class": FailureClass(a.failure_class) if a.failure_class else None,
                "error": dict(a.error_json or {}),
                "paid_call_dispatched": a.paid_call_dispatched,
                "paid_call_outcome_known": a.paid_call_outcome_known,
                "provider_request_id": a.provider_request_id,
                "estimated_cost_usd": a.estimated_cost_usd,
                "actual_cost_usd": a.actual_cost_usd,
                "started_at": a.started_at,
                "finished_at": a.finished_at,
            }
            for a in rows
        ]

    def events(self, run_id: str, *, since: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        """Return run events after ``since``, in order.

        Monotonic ids let a reconnecting client resume without gaps or duplicates.
        """
        self._run(run_id)
        rows = self._session.scalars(
            select(WorkflowEventRow)
            .where(
                WorkflowEventRow.run_id == run_id,
                WorkflowEventRow.event_id > int(since),
            )
            .order_by(WorkflowEventRow.event_id)
            .limit(max(1, min(int(limit), 2000)))
        ).all()
        return [
            {
                "event_id": e.event_id,
                "run_id": e.run_id,
                "step_id": e.step_id,
                "attempt_id": e.attempt_id,
                "event_type": e.event_type,
                "level": e.level,
                "message": e.message,
                "payload": dict(e.payload_json or {}),
                "created_at": e.created_at,
            }
            for e in rows
        ]

    def runs_needing_attention(self) -> list[dict[str, Any]]:
        """Return runs blocked on a person, for an operator dashboard.

        ``WAITING_PROVIDER`` and ``WAITING_CAPACITY`` are excluded: both clear
        without anyone acting.
        """
        statuses = [s.value for s in WorkflowRunStatus if s.needs_attention]
        rows = self._session.scalars(
            select(WorkflowRunRow)
            .where(WorkflowRunRow.status.in_(statuses), *self._scope_filter())
            .order_by(WorkflowRunRow.updated_at.desc())
        ).all()
        return [
            {
                "run_id": r.run_id,
                "status": WorkflowRunStatus(r.status),
                "workflow_type": r.workflow_type,
                "project_id": r.project_id,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]

    def force_step_status(self, step_id: str, status: StepRunStatus, *, reason: str) -> None:
        """Administrative override of a step's status.

        The prototype exposed this as a ``force=True`` keyword on an ordinary
        transition, which made it reachable by accident. Here it is a separate,
        explicitly named method that requires ``MANAGE_STUDY_ACCESS`` and always
        records a reason -- because it can move a step out of a terminal state.
        """
        self.scope.require(Permission.MANAGE_STUDY_ACCESS)
        if not reason:
            raise ValueError("an administrative override requires a reason")

        step = self._step(step_id)
        self._lock_run_for(step)
        previous = step.status
        step.status = status.value
        step.updated_at = utcnow()

        self._event(
            step.run_id,
            event_type="STEP_FORCED",
            message=f"{previous} -> {status.value}: {reason}",
            payload={
                "from": previous,
                "to": status.value,
                "reason": reason,
                "actor_id": self.scope.actor_id,
            },
            step_id=step_id,
            level="WARN",
        )
        self._session.flush()
        self._refresh_run(step.run_id)
        self._session.flush()


class WorkQueue:
    """The cross-study operations a worker needs, and nothing else.

    :class:`WorkflowRepository` is study-scoped, and stays that way. A worker has
    to find work in *any* study, so this is the one place allowed to query
    without a study predicate -- and it exposes exactly four operations, none of
    which returns research data:

    * :meth:`claim_next` -- take one runnable step, anywhere;
    * :meth:`recover_expired_attempts` -- the reconciler;
    * :meth:`resume_waiting_steps` -- clear provider parks that are due;
    * :meth:`refuse` -- fail a claimed attempt that may not execute.

    Everything else a worker does happens through a scoped repository built from
    :meth:`aia_core.application.scope.ScopeResolver.execution_context`, which is
    issued only against a lease this worker holds.
    """

    def __init__(self, session: Session) -> None:
        self._engine = WorkflowRepository._across_studies(session)

    def claim_next(
        self,
        *,
        worker_id: str,
        kinds: Collection[str] | None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        now: datetime | None = None,
    ) -> ClaimedWork | None:
        """Claim one runnable step in any study. See :meth:`WorkflowRepository.claim_next`."""
        return self._engine.claim_next(
            worker_id=worker_id, lease_seconds=lease_seconds, now=now, kinds=kinds
        )

    def recover_expired_attempts(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> list[RecoveryDecision]:
        """Recover lapsed leases in every study. Safe to run from every worker."""
        return self._engine.recover_expired_attempts(now=now, limit=limit)

    def resume_waiting_steps(
        self,
        *,
        now: datetime | None = None,
        capacity_backoff_seconds: int = DEFAULT_CAPACITY_BACKOFF_SECONDS,
        quota_fallback_seconds: int = DEFAULT_QUOTA_FALLBACK_SECONDS,
        limit: int = 100,
    ) -> list[str]:
        """Resume due provider parks in every study."""
        return self._engine.resume_waiting_steps(
            now=now,
            capacity_backoff_seconds=capacity_backoff_seconds,
            quota_fallback_seconds=quota_fallback_seconds,
            limit=limit,
        )

    def refuse(self, attempt_id: str, *, worker_id: str, reason: str) -> RecoveryDecision:
        """Fail a claimed attempt permanently because it may not execute at all.

        Used when no execution scope can be issued for it -- its client was
        archived after the run started, say. Fail closed: the step is ``FAILED``
        with a ``PERMISSION`` failure and the reason, rather than left for the
        lease to lapse and be retried into the same refusal. Lease-fenced.
        """
        return self._engine.fail_attempt(
            attempt_id,
            worker_id=worker_id,
            failure=FailureClass.PERMISSION,
            error={"reason": reason},
        )
