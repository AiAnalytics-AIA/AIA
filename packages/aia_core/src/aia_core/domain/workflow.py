"""Durable workflow domain: runs, steps, attempts and recovery.

Two levels of state, deliberately separated (see
``docs/architecture/workflows.md``):

* :class:`WorkflowRunStatus` is **business** state -- what a researcher is waiting
  for. It is what a dashboard shows and what an alert fires on.
* :class:`AttemptStatus` is **technical execution** state -- what one worker is
  doing with one step right now.

The prototype used a single 14-value status for both, which muddled
``RECOVERY_REQUIRED`` (a human must decide; money may already be gone) with an
ordinary ``FAILED`` attempt. Keeping them apart is the point.

Nothing here performs I/O. Persistence lives in
``aia_core.infrastructure.workflow_repository``; the rules live here so they can
be tested without a database and reused by the worker.

The behavioural contract is
``packages/aia_core/tests/test_legacy_job_store_characterization.py`` -- 64 tests
describing the validated prototype engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

__all__ = [
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "AttemptStatus",
    "FailureClass",
    "InteractionMode",
    "RecoveryAction",
    "RecoveryDecision",
    "ReservationStatus",
    "StepRunStatus",
    "WorkflowRunStatus",
    "classify_failure",
    "decide_recovery",
    "derive_run_status",
    "is_lease_expired",
    "lease_deadline",
    "new_attempt_id",
    "new_reservation_id",
    "new_run_id",
    "new_step_id",
]


DEFAULT_LEASE_SECONDS: Final = 120
DEFAULT_MAX_ATTEMPTS: Final = 3


def new_run_id() -> str:
    """Return a new workflow run id."""
    return "RUN-" + uuid4().hex[:16]


def new_step_id() -> str:
    """Return a new step run id."""
    return "STP-" + uuid4().hex[:16]


def new_attempt_id() -> str:
    """Return a new attempt id."""
    return "ATT-" + uuid4().hex[:16]


def new_reservation_id() -> str:
    """Return a new budget reservation id."""
    return "RSV-" + uuid4().hex[:16]


# --------------------------------------------------------------------------- #
# Business state
# --------------------------------------------------------------------------- #


class WorkflowRunStatus(StrEnum):
    """What a study is waiting for. Business state, shown to people.

    ``WAITING_BUDGET`` is new relative to the prototype, which routed budget
    exhaustion through an approval in ``WAITING_USER``. "A person must decide
    something" and "this study is out of money" need different dashboards and
    different alerts.

    ``WAITING_PROVIDER`` merges the prototype's ``WAITING_CREDITS`` and
    ``WAITING_CAPACITY`` at this level, because a researcher does not care which.
    The distinction survives where it matters -- on the attempt's
    :class:`FailureClass`, which decides the retry behaviour.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_GATE = "WAITING_GATE"
    WAITING_BUDGET = "WAITING_BUDGET"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """True when no further work will happen without a new run."""
        return self in _TERMINAL_RUN_STATUSES

    @property
    def needs_attention(self) -> bool:
        """True when a person has to do something before work continues.

        ``WAITING_PROVIDER`` is excluded: it clears on its own.
        """
        return self in _ATTENTION_RUN_STATUSES


_TERMINAL_RUN_STATUSES: Final = frozenset(
    {
        WorkflowRunStatus.COMPLETED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    }
)
_ATTENTION_RUN_STATUSES: Final = frozenset(
    {
        WorkflowRunStatus.WAITING_GATE,
        WorkflowRunStatus.WAITING_BUDGET,
        WorkflowRunStatus.RECOVERY_REQUIRED,
    }
)


class StepRunStatus(StrEnum):
    """One pipeline node's state. The record that a step is done.

    Distinct from :class:`AttemptStatus`: a step can be ``RUNNABLE`` while its
    third attempt is ``EXPIRED``.
    """

    BLOCKED = "BLOCKED"
    RUNNABLE = "RUNNABLE"
    RUNNING = "RUNNING"
    WAITING_GATE = "WAITING_GATE"
    WAITING_BUDGET = "WAITING_BUDGET"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"

    @property
    def is_terminal(self) -> bool:
        """True when this step will not run again in this run."""
        return self in _TERMINAL_STEP_STATUSES

    @property
    def satisfies_dependency(self) -> bool:
        """True when a dependant step may proceed.

        Only ``SUCCEEDED`` and ``SKIPPED`` qualify -- **not** merely "terminal".
        A failed upstream step must stall the pipeline rather than let downstream
        work run on missing inputs; an analysis built on an absent evidence pack
        is worse than no analysis.
        """
        return self in (StepRunStatus.SUCCEEDED, StepRunStatus.SKIPPED)

    @property
    def is_waiting(self) -> bool:
        """True while the step is parked awaiting an external condition."""
        return self in _WAITING_STEP_STATUSES


_TERMINAL_STEP_STATUSES: Final = frozenset(
    {
        StepRunStatus.SUCCEEDED,
        StepRunStatus.FAILED,
        StepRunStatus.CANCELLED,
        StepRunStatus.SKIPPED,
    }
)
_WAITING_STEP_STATUSES: Final = frozenset(
    {
        StepRunStatus.WAITING_GATE,
        StepRunStatus.WAITING_BUDGET,
        StepRunStatus.WAITING_PROVIDER,
    }
)


# --------------------------------------------------------------------------- #
# Technical execution state
# --------------------------------------------------------------------------- #


class AttemptStatus(StrEnum):
    """One execution of one step. Append-only history.

    The prototype kept an ``attempt`` integer and only the latest error, so a step
    that failed three different ways retained one. Each attempt is now its own
    row with its own error, provider, model, cost and timing.
    """

    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"

    @property
    def is_terminal(self) -> bool:
        """True when this attempt is over, however it ended."""
        return self in _TERMINAL_ATTEMPT_STATUSES

    @property
    def holds_lease(self) -> bool:
        """True when a worker owns this attempt and must be heartbeating."""
        return self in (AttemptStatus.CLAIMED, AttemptStatus.EXECUTING)


_TERMINAL_ATTEMPT_STATUSES: Final = frozenset(
    {
        AttemptStatus.SUCCEEDED,
        AttemptStatus.FAILED,
        AttemptStatus.EXPIRED,
        AttemptStatus.ABANDONED,
    }
)


class InteractionMode(StrEnum):
    """Whether a step may proceed unattended.

    ``REVIEW_IF_WARNING`` is carried over from the prototype's ``preflight`` node:
    a methodological warning pauses for a human instead of proceeding.
    """

    AUTO = "auto"
    REVIEW_IF_WARNING = "review_if_warning"
    ALWAYS_REVIEW = "always_review"


class ReservationStatus(StrEnum):
    """Lifecycle of a budget reservation.

    ``SETTLED_UNCERTAIN`` is the important one: a paid call whose billing status
    cannot be determined. The reserved amount is converted to *actual* exposure,
    so the study budget reflects money that may already be gone.
    """

    RESERVED = "RESERVED"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"
    SETTLED_UNCERTAIN = "SETTLED_UNCERTAIN"


# --------------------------------------------------------------------------- #
# Failure classification
# --------------------------------------------------------------------------- #


class FailureClass(StrEnum):
    """Why an attempt failed. Decides whether to retry, park or stop.

    Ported from the prototype's ``ai_router.classify_provider_exception``. The
    classification must happen *before* any retry decision: retrying an
    authentication failure burns quota and hides a misconfiguration, and retrying
    a quota failure eventually exhausts ``max_attempts`` and fails a project that
    was only waiting.
    """

    # Retryable
    TRANSPORT = "TRANSPORT"
    PROVIDER_CAPACITY = "PROVIDER_CAPACITY"
    TRANSIENT = "TRANSIENT"

    # Park, not retry. A quota pause is not a failed attempt.
    QUOTA = "QUOTA"

    # Needs a person
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

    # Permanent
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    MAX_TURNS = "MAX_TURNS"
    SDK_OUTDATED = "SDK_OUTDATED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

    @property
    def is_retryable(self) -> bool:
        """True when repeating the attempt could succeed."""
        return self in _RETRYABLE_FAILURES

    @property
    def is_permanent(self) -> bool:
        """True when repeating the attempt cannot succeed.

        Retrying these wastes quota and hides the real problem.
        """
        return self in _PERMANENT_FAILURES

    @property
    def consumes_attempt(self) -> bool:
        """True when this failure should count against ``max_attempts``.

        Quota, budget and approval do **not** consume an attempt: none is a
        failure of the work, and counting them would eventually fail a project
        that was merely waiting. This is the prototype's retry-counter reset,
        expressed as a property of the failure rather than a special case in the
        recovery path.
        """
        return self not in _NON_CONSUMING_FAILURES


_RETRYABLE_FAILURES: Final = frozenset(
    {FailureClass.TRANSPORT, FailureClass.PROVIDER_CAPACITY, FailureClass.TRANSIENT}
)
_PERMANENT_FAILURES: Final = frozenset(
    {
        FailureClass.AUTHENTICATION,
        FailureClass.PERMISSION,
        FailureClass.MISSING_CONFIGURATION,
        FailureClass.MODEL_UNAVAILABLE,
        FailureClass.SCHEMA_VIOLATION,
        FailureClass.MAX_TURNS,
        FailureClass.SDK_OUTDATED,
        FailureClass.CANCELLED,
        # UNKNOWN is permanent deliberately. An error we cannot classify must not
        # be retried against a metered provider on the assumption that it is
        # transient -- that assumption costs money and hides the real fault.
        FailureClass.UNKNOWN,
    }
)
_NON_CONSUMING_FAILURES: Final = frozenset(
    {FailureClass.QUOTA, FailureClass.BUDGET_EXCEEDED, FailureClass.APPROVAL_REQUIRED}
)


# Provider error tags to failure classes. The prototype matched a bracketed tag
# in the exception text; keeping the mapping as data makes it testable and lets
# the gateway supply a class directly once ADR 0005 lands.
_TAG_TO_CLASS: Final[dict[str, FailureClass]] = {
    "MISSING": FailureClass.MISSING_CONFIGURATION,
    "AUTHENTICATION": FailureClass.AUTHENTICATION,
    "PERMISSION": FailureClass.PERMISSION,
    "QUOTA": FailureClass.QUOTA,
    "CAPACITY": FailureClass.PROVIDER_CAPACITY,
    "MODEL": FailureClass.MODEL_UNAVAILABLE,
    "SCHEMA": FailureClass.SCHEMA_VIOLATION,
    "TRANSPORT": FailureClass.TRANSPORT,
    "SDK_OUTDATED": FailureClass.SDK_OUTDATED,
    "MAX_TURNS": FailureClass.MAX_TURNS,
    "OTHER": FailureClass.UNKNOWN,
}


def classify_failure(tag: str | None) -> FailureClass:
    """Map a provider error tag to a :class:`FailureClass`.

    An unrecognised tag becomes ``UNKNOWN``, which is permanent. That is
    deliberate: an error we do not understand must not be retried against a paid
    provider on the assumption that it is transient.
    """
    return _TAG_TO_CLASS.get(str(tag or "").strip().upper(), FailureClass.UNKNOWN)


# --------------------------------------------------------------------------- #
# Leases
# --------------------------------------------------------------------------- #


def lease_deadline(
    *, now: datetime | None = None, seconds: int = DEFAULT_LEASE_SECONDS
) -> datetime:
    """Return the UTC instant at which a lease expires."""
    base = now or datetime.now(UTC)
    return base + timedelta(seconds=max(1, int(seconds)))


def as_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as a timezone-aware UTC datetime.

    Every timestamp this system *writes* is UTC-aware, but not every backend
    gives one back. PostgreSQL round-trips ``TIMESTAMP WITH TIME ZONE`` faithfully;
    **SQLite does not store an offset at all**, so a value written as aware UTC is
    read back naive. Comparing the two raises ``TypeError``.

    A naive value is therefore interpreted as UTC, which is safe precisely because
    writes are UTC-only. This is not a cosmetic fix: the comparison it protects
    decides whether a lease has lapsed, and therefore whether work is recovered.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_lease_expired(lease_until: datetime | None, *, now: datetime | None = None) -> bool:
    """True when a lease has lapsed.

    A missing deadline counts as expired: an attempt holding the lease with no
    deadline is a bug, and treating it as live would strand the step forever.

    Both sides are normalised through :func:`as_utc` because a deadline read from
    SQLite arrives without an offset.
    """
    if lease_until is None:
        return True

    deadline = as_utc(lease_until)
    moment = as_utc(now) or datetime.now(UTC)
    assert deadline is not None  # guarded above
    return deadline <= moment


# --------------------------------------------------------------------------- #
# Recovery
# --------------------------------------------------------------------------- #


class RecoveryAction(StrEnum):
    """What to do with a step whose attempt lapsed or failed."""

    RETRY = "RETRY"
    PARK_PROVIDER = "PARK_PROVIDER"
    PARK_BUDGET = "PARK_BUDGET"
    PARK_GATE = "PARK_GATE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """The outcome of recovering one lapsed or failed attempt.

    ``settle_reservation_as_uncertain`` is the flag that protects a client's
    budget from a double charge. When true, the caller must convert the
    outstanding reservation to ``SETTLED_UNCERTAIN`` and add it to actual cost --
    money that may already be gone must appear as spent, not as available.
    """

    action: RecoveryAction
    step_status: StepRunStatus
    reason: str
    consumes_attempt: bool = True
    settle_reservation_as_uncertain: bool = False
    retry_after: datetime | None = None

    @property
    def needs_human(self) -> bool:
        """True when work stops until a person decides."""
        return self.action in (
            RecoveryAction.RECOVERY_REQUIRED,
            RecoveryAction.PARK_BUDGET,
            RecoveryAction.PARK_GATE,
        )


def decide_recovery(
    *,
    failure: FailureClass | None,
    attempt_number: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    paid_call_dispatched: bool,
    paid_call_outcome_known: bool,
    quota_reset_at: datetime | None = None,
) -> RecoveryDecision:
    """Decide what happens to a step after an attempt ends badly.

    This function is the heart of the engine's durability, and the argument that
    matters most is the pair ``paid_call_dispatched`` / ``paid_call_outcome_known``.

    When a worker dies after dispatching a **metered** provider call, the system
    cannot know which of three things happened: the provider never received it,
    it processed it but the response was lost, or it processed it and billing
    occurred. So:

    * automatic retry -> possible double billing;
    * assume success  -> possible missing output;
    * assume failure  -> an accounting lie.

    None is acceptable, so the work is parked as ``RECOVERY_REQUIRED`` for a
    person and the reservation is settled as *uncertain* actual exposure. This is
    carried over verbatim from the prototype and is treated as a fundamental
    invariant.

    A subscription runtime never reaches that branch, because a repeated call
    there has no marginal cost -- which is why the provider distinction has to
    reach this decision rather than being handled at the transport layer.
    """
    # Approval and budget stop the work regardless of attempt count: neither is a
    # failure of the work, and neither clears without a person.
    if failure is FailureClass.APPROVAL_REQUIRED:
        return RecoveryDecision(
            action=RecoveryAction.PARK_GATE,
            step_status=StepRunStatus.WAITING_GATE,
            reason="approval_required",
            consumes_attempt=False,
        )
    if failure is FailureClass.BUDGET_EXCEEDED:
        return RecoveryDecision(
            action=RecoveryAction.PARK_BUDGET,
            step_status=StepRunStatus.WAITING_BUDGET,
            reason="budget_exceeded",
            consumes_attempt=False,
        )

    # Quota is a park, not a retry, and must not consume an attempt.
    if failure is FailureClass.QUOTA:
        return RecoveryDecision(
            action=RecoveryAction.PARK_PROVIDER,
            step_status=StepRunStatus.WAITING_PROVIDER,
            reason="provider_quota_exhausted",
            consumes_attempt=False,
            retry_after=quota_reset_at,
        )

    # A dispatched paid call with an unknown outcome must never be auto-retried.
    # Checked before the permanence and attempt-count branches, because the
    # billing uncertainty outranks both: even a "permanent" error leaves the
    # question of whether the call was billed.
    if paid_call_dispatched and not paid_call_outcome_known:
        return RecoveryDecision(
            action=RecoveryAction.RECOVERY_REQUIRED,
            step_status=StepRunStatus.RECOVERY_REQUIRED,
            reason="paid_external_call_side_effect_uncertain",
            settle_reservation_as_uncertain=True,
        )

    if failure is not None and failure.is_permanent:
        return RecoveryDecision(
            action=RecoveryAction.FAIL,
            step_status=StepRunStatus.FAILED,
            reason=f"permanent_failure_{failure.value.lower()}",
        )

    if failure is FailureClass.PROVIDER_CAPACITY:
        return RecoveryDecision(
            action=RecoveryAction.PARK_PROVIDER,
            step_status=StepRunStatus.WAITING_PROVIDER,
            reason="provider_capacity_unavailable",
            consumes_attempt=False,
        )

    # Retryable, or a lapsed lease on work that is safe to repeat.
    if attempt_number < max_attempts:
        return RecoveryDecision(
            action=RecoveryAction.RETRY,
            step_status=StepRunStatus.RUNNABLE,
            reason=(
                "expired_lease_idempotent_or_subscription"
                if failure is None
                else f"retryable_{failure.value.lower()}"
            ),
        )

    # Attempts exhausted. RECOVERY_REQUIRED rather than FAILED, matching the
    # prototype: a person may still be able to complete the work.
    return RecoveryDecision(
        action=RecoveryAction.RECOVERY_REQUIRED,
        step_status=StepRunStatus.RECOVERY_REQUIRED,
        reason="max_attempts_exhausted",
    )


# --------------------------------------------------------------------------- #
# Run status derivation
# --------------------------------------------------------------------------- #

# Precedence when deriving run status from step statuses. Lower sorts first and
# wins. Ordering rationale:
#   - FAILED outranks everything: a failed study needs attention immediately.
#   - RECOVERY_REQUIRED next: money may be at stake.
#   - WAITING_BUDGET and WAITING_GATE outrank WAITING_PROVIDER, because they need
#     a person while provider waits clear on their own.
_STEP_TO_RUN_PRECEDENCE: Final[tuple[tuple[StepRunStatus, WorkflowRunStatus], ...]] = (
    (StepRunStatus.FAILED, WorkflowRunStatus.FAILED),
    (StepRunStatus.RECOVERY_REQUIRED, WorkflowRunStatus.RECOVERY_REQUIRED),
    (StepRunStatus.WAITING_BUDGET, WorkflowRunStatus.WAITING_BUDGET),
    (StepRunStatus.WAITING_GATE, WorkflowRunStatus.WAITING_GATE),
    (StepRunStatus.WAITING_PROVIDER, WorkflowRunStatus.WAITING_PROVIDER),
    (StepRunStatus.RUNNING, WorkflowRunStatus.RUNNING),
    (StepRunStatus.RUNNABLE, WorkflowRunStatus.RUNNING),
)


def derive_run_status(
    step_statuses: list[StepRunStatus], *, cancel_requested: bool = False
) -> WorkflowRunStatus:
    """Derive business state from the states of a run's steps.

    A run with no steps is ``PENDING``, not ``COMPLETED`` -- an empty run has not
    succeeded at anything, and reporting it as complete would let a caller
    believe work was done.
    """
    if not step_statuses:
        return WorkflowRunStatus.PENDING

    if all(s is StepRunStatus.CANCELLED for s in step_statuses):
        return WorkflowRunStatus.CANCELLED

    if all(s.satisfies_dependency for s in step_statuses):
        return WorkflowRunStatus.COMPLETED

    # Cancellation of a partly-finished run: everything has stopped and at least
    # one step was cancelled.
    if cancel_requested and all(s.is_terminal for s in step_statuses):
        return WorkflowRunStatus.CANCELLED

    present = set(step_statuses)
    for step_status, run_status in _STEP_TO_RUN_PRECEDENCE:
        if step_status in present:
            return run_status

    return WorkflowRunStatus.PENDING


@dataclass(frozen=True, slots=True)
class StepDefinition:
    """One node of a pipeline DAG, as declared by a workflow template.

    Mirrors the prototype's ``workflow_engine.STANDARD`` tuples so the 24-node
    research DAG can be carried over as data rather than rewritten.
    """

    node_key: str
    kind: str
    depends_on: tuple[str, ...] = ()
    stage_type: str = ""
    artifact_target: str = ""
    interaction_mode: InteractionMode = InteractionMode.AUTO
    priority: int = 50
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    metadata: dict[str, Any] | None = None


def validate_dag(steps: list[StepDefinition]) -> None:
    """Raise when a step list is not a usable DAG.

    Checked at template definition time rather than at execution time, because a
    cycle discovered mid-run would strand a study with some steps already paid
    for.
    """
    keys = [s.node_key for s in steps]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        raise ValueError(f"duplicate node keys: {sorted(duplicates)}")

    known = set(keys)
    for step in steps:
        unknown = set(step.depends_on) - known
        if unknown:
            raise ValueError(f"{step.node_key} depends on unknown steps: {sorted(unknown)}")
        if step.node_key in step.depends_on:
            raise ValueError(f"{step.node_key} depends on itself")

    # Kahn's algorithm: anything left over is in a cycle.
    remaining = {s.node_key: set(s.depends_on) for s in steps}
    while True:
        ready = {k for k, deps in remaining.items() if not deps}
        if not ready:
            break
        for key in ready:
            del remaining[key]
        for deps in remaining.values():
            deps -= ready

    if remaining:
        raise ValueError(f"dependency cycle among: {sorted(remaining)}")
