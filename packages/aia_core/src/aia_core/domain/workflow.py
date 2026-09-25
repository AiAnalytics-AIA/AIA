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

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final
from uuid import uuid4

__all__ = [
    "DEFAULT_CAPACITY_BACKOFF_SECONDS",
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_QUOTA_FALLBACK_SECONDS",
    "RUNTIME_UNAVAILABLE_REASON",
    "AttemptStatus",
    "FailureClass",
    "InteractionMode",
    "RecoveryAction",
    "RecoveryDecision",
    "ReservationStatus",
    "StepRunStatus",
    "WorkflowRunStatus",
    "apply_cancellation",
    "classify_failure",
    "decide_recovery",
    "decide_release",
    "derive_run_status",
    "is_lease_expired",
    "lease_deadline",
    "new_attempt_id",
    "new_reservation_id",
    "new_run_id",
    "new_step_id",
    "resume_due",
]


DEFAULT_LEASE_SECONDS: Final = 120
DEFAULT_MAX_ATTEMPTS: Final = 3

# How long a capacity park waits before its step is offered again. Capacity has
# no reset instant -- the provider is overloaded now and will not say until when
# -- so the resume is a fixed back-off rather than a scheduled time.
DEFAULT_CAPACITY_BACKOFF_SECONDS: Final = 60

# A quota park whose provider gave no reset instant. Without a fallback the step
# would wait for a `runnable_after` that never comes; with one, the worst case is
# one refused call every fifteen minutes, which costs nothing (a refusal is not
# billed) and needs nobody to notice.
DEFAULT_QUOTA_FALLBACK_SECONDS: Final = 900


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

    The vocabulary is the frozen Architecture v2.1 contract, and the two prefixes
    mean different things. ``AWAITING_*`` is *a person owes us a decision*:
    nothing moves until a human acts. ``WAITING_*`` is *a system owes us
    capacity*: it clears without anyone doing anything. A dashboard that mixes the
    two cannot tell an operator whether to go and find somebody.

    ``AWAITING_BUDGET`` is new relative to the prototype, which routed budget
    exhaustion through an approval in ``WAITING_USER``. "A person must decide
    something" and "this study is out of money" need different dashboards and
    different alerts.

    ``WAITING_PROVIDER`` and ``WAITING_CAPACITY`` are **deliberately separate**.
    They were merged in an earlier draft on the grounds that a researcher does not
    care which; that was wrong operationally, because they recover differently.
    ``WAITING_PROVIDER`` is a provider-side entitlement wait -- quota exhausted,
    the account cannot call until a reset window passes -- and it carries a
    ``runnable_after``. ``WAITING_CAPACITY`` is an execution-capacity condition --
    the provider is overloaded right now -- which clears on its own in seconds to
    minutes and needs no scheduled resume. Collapsing them makes a quota wall look
    like a blip, so nobody raises a limit, and makes a blip look like a quota
    wall, so somebody is paged for nothing.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_GATE = "AWAITING_GATE"
    AWAITING_BUDGET = "AWAITING_BUDGET"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    WAITING_CAPACITY = "WAITING_CAPACITY"
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

        ``WAITING_PROVIDER`` and ``WAITING_CAPACITY`` are excluded: both clear
        without anyone acting.
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
        WorkflowRunStatus.AWAITING_GATE,
        WorkflowRunStatus.AWAITING_BUDGET,
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
    AWAITING_GATE = "AWAITING_GATE"
    AWAITING_BUDGET = "AWAITING_BUDGET"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    WAITING_CAPACITY = "WAITING_CAPACITY"
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
        StepRunStatus.AWAITING_GATE,
        StepRunStatus.AWAITING_BUDGET,
        StepRunStatus.WAITING_PROVIDER,
        StepRunStatus.WAITING_CAPACITY,
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
    # Park until someone deploys what the step needs: the runtime it would run on
    # does not exist yet (ADR 0016: AI fieldwork before the Agent Runtime). Not a
    # failure of the work, and no timer can clear it.
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"

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
    {
        FailureClass.QUOTA,
        FailureClass.RUNTIME_UNAVAILABLE,
        FailureClass.BUDGET_EXCEEDED,
        FailureClass.APPROVAL_REQUIRED,
    }
)

#: The waiting reason of a step parked for a runtime that is not deployed.
#: :func:`resume_due` never resumes it: only deploying the runtime can.
RUNTIME_UNAVAILABLE_REASON: Final = "ai_runtime_unavailable"


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
    # Two provider parks, because the two waits recover differently: a quota park
    # resumes at a reset instant, a capacity park resumes as soon as the provider
    # has room. See :class:`WorkflowRunStatus`.
    PARK_PROVIDER = "PARK_PROVIDER"
    PARK_CAPACITY = "PARK_CAPACITY"
    PARK_BUDGET = "PARK_BUDGET"
    PARK_GATE = "PARK_GATE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    FAIL = "FAIL"
    # The run was cancelled while the attempt was in flight; whatever the attempt
    # would otherwise have become, the step is cancelled. See `apply_cancellation`.
    CANCEL = "CANCEL"


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
            step_status=StepRunStatus.AWAITING_GATE,
            reason="approval_required",
            consumes_attempt=False,
        )
    if failure is FailureClass.BUDGET_EXCEEDED:
        return RecoveryDecision(
            action=RecoveryAction.PARK_BUDGET,
            step_status=StepRunStatus.AWAITING_BUDGET,
            reason="budget_exceeded",
            consumes_attempt=False,
        )

    # Quota is a park, not a retry, and must not consume an attempt. It is the
    # entitlement wait: the account may not call again until the reset instant,
    # which is why this branch alone carries a `retry_after`.
    if failure is FailureClass.QUOTA:
        return RecoveryDecision(
            action=RecoveryAction.PARK_PROVIDER,
            step_status=StepRunStatus.WAITING_PROVIDER,
            reason="provider_quota_exhausted",
            consumes_attempt=False,
            retry_after=quota_reset_at,
        )

    # The runtime the step needs is not deployed. The step waits, visibly, with a
    # reason no timer clears; nothing downstream runs and nothing is fabricated.
    if failure is FailureClass.RUNTIME_UNAVAILABLE:
        return RecoveryDecision(
            action=RecoveryAction.PARK_PROVIDER,
            step_status=StepRunStatus.WAITING_PROVIDER,
            reason=RUNTIME_UNAVAILABLE_REASON,
            consumes_attempt=False,
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
        # Capacity, not quota: the account may call, the provider has no room
        # right now. It clears on its own with no reset instant to wait for, so
        # it parks in its own state rather than behind a quota window.
        return RecoveryDecision(
            action=RecoveryAction.PARK_CAPACITY,
            step_status=StepRunStatus.WAITING_CAPACITY,
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


def decide_release(
    *, paid_call_dispatched: bool, paid_call_outcome_known: bool
) -> RecoveryDecision:
    """Decide what happens when a live worker gives an attempt back.

    A release is a worker shutting down cleanly at a checkpoint: the work did not
    fail, so the step becomes ``RUNNABLE`` again at once and the attempt does
    **not** count against ``max_attempts``. Counting it would let three rolling
    deploys fail a step that never did anything wrong.

    The one exception is the same invariant :func:`decide_recovery` protects. A
    worker releasing with a paid call dispatched and its outcome unknown is, for
    billing purposes, indistinguishable from a worker that crashed at that
    moment, so it gets the same answer: ``RECOVERY_REQUIRED`` and uncertain
    exposure, never an automatic retry.
    """
    if paid_call_dispatched and not paid_call_outcome_known:
        return RecoveryDecision(
            action=RecoveryAction.RECOVERY_REQUIRED,
            step_status=StepRunStatus.RECOVERY_REQUIRED,
            reason="paid_external_call_side_effect_uncertain",
            settle_reservation_as_uncertain=True,
        )
    return RecoveryDecision(
        action=RecoveryAction.RETRY,
        step_status=StepRunStatus.RUNNABLE,
        reason="released_by_worker",
        consumes_attempt=False,
    )


def apply_cancellation(decision: RecoveryDecision, *, cancel_requested: bool) -> RecoveryDecision:
    """Let a cancellation that arrived mid-attempt win over the attempt's outcome.

    ``request_cancel`` deliberately leaves a ``RUNNING`` step for its worker to
    stop at a checkpoint. If that worker instead dies, fails, or releases the
    attempt, the ordinary decision would put the step back to ``RUNNABLE`` or a
    park -- and a step with ``cancel_requested`` set is never claimed again, so
    the run would sit in ``RUNNING`` forever with nothing able to finish it.

    The step state becomes ``CANCELLED``. The **accounting half is kept**:
    ``settle_reservation_as_uncertain`` survives, because cancelling does not make
    an in-flight call's cost go away. A decision that is already terminal is
    returned unchanged -- a permanent failure is still a failure.
    """
    if not cancel_requested or decision.step_status.is_terminal:
        return decision
    return replace(
        decision,
        action=RecoveryAction.CANCEL,
        step_status=StepRunStatus.CANCELLED,
        reason=f"cancelled_after_{decision.reason}",
        retry_after=None,
    )


def resume_due(
    status: StepRunStatus,
    *,
    runnable_after: datetime | None,
    parked_at: datetime | None,
    now: datetime | None = None,
    capacity_backoff_seconds: int = DEFAULT_CAPACITY_BACKOFF_SECONDS,
    quota_fallback_seconds: int = DEFAULT_QUOTA_FALLBACK_SECONDS,
    waiting_reason: str | None = None,
) -> bool:
    """True when a parked step should be offered to workers again.

    Only the two ``WAITING_*`` parks ever resume on their own, which is the
    contract of the prefix: a system owes us capacity, and it clears without
    anyone acting. ``AWAITING_*`` and ``RECOVERY_REQUIRED`` return False
    unconditionally -- a person owes a decision, and a timer resuming them would
    be the system deciding on their behalf.

    * ``WAITING_PROVIDER`` resumes at its ``runnable_after`` (the provider's reset
      instant), or after ``quota_fallback_seconds`` when none was given.
    * ``WAITING_CAPACITY`` resumes after ``capacity_backoff_seconds``.

    A missing ``parked_at`` counts as parked long ago. The alternative strands the
    step forever, and resuming costs at most one refused call.

    A step parked for a runtime that is not deployed (``RUNTIME_UNAVAILABLE_REASON``)
    is never resumed here: a timer cannot deploy it, and resuming would only
    re-park it on every sweep.
    """
    if waiting_reason == RUNTIME_UNAVAILABLE_REASON:
        return False
    moment = as_utc(now) or datetime.now(UTC)
    parked = as_utc(parked_at)

    def waited(seconds: int) -> bool:
        return parked is None or parked + timedelta(seconds=max(0, int(seconds))) <= moment

    if status is StepRunStatus.WAITING_PROVIDER:
        reset = as_utc(runnable_after)
        if reset is not None:
            return reset <= moment
        return waited(quota_fallback_seconds)
    if status is StepRunStatus.WAITING_CAPACITY:
        return waited(capacity_backoff_seconds)
    return False


# --------------------------------------------------------------------------- #
# Run status derivation
# --------------------------------------------------------------------------- #

# Precedence when deriving run status from step statuses. Lower sorts first and
# wins. Ordering rationale:
#   - FAILED outranks everything: a failed study needs attention immediately.
#   - RECOVERY_REQUIRED next: money may be at stake.
#   - AWAITING_BUDGET and AWAITING_GATE outrank the provider waits, because they
#     need a person while provider waits clear on their own.
#   - WAITING_PROVIDER outranks WAITING_CAPACITY: a quota wall lasts until a reset
#     instant and may warrant raising a limit, while a capacity blip clears in
#     minutes. Reporting the longer wait is the more actionable of the two.
_STEP_TO_RUN_PRECEDENCE: Final[tuple[tuple[StepRunStatus, WorkflowRunStatus], ...]] = (
    (StepRunStatus.FAILED, WorkflowRunStatus.FAILED),
    (StepRunStatus.RECOVERY_REQUIRED, WorkflowRunStatus.RECOVERY_REQUIRED),
    (StepRunStatus.AWAITING_BUDGET, WorkflowRunStatus.AWAITING_BUDGET),
    (StepRunStatus.AWAITING_GATE, WorkflowRunStatus.AWAITING_GATE),
    (StepRunStatus.WAITING_PROVIDER, WorkflowRunStatus.WAITING_PROVIDER),
    (StepRunStatus.WAITING_CAPACITY, WorkflowRunStatus.WAITING_CAPACITY),
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
    #: True when the step reads population data. A run containing such a step
    #: cannot be created without a recorded population binding, and the step
    #: obtains its data only through that binding -- never by resolving its own.
    consumes_population: bool = False


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
