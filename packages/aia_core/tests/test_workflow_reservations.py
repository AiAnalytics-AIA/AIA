"""Every way an attempt ends closes its reservations by one rule.

``WorkflowRepository._close_open_reservations`` is the rule; these tests pin each
branch and the two defects it replaced (``.planning/plans/worker-process.md``):

* **W4** -- cancelling a paid step left its reservation ``RESERVED`` forever, so
  the study's available budget shrank permanently;
* **W5** -- a failure *released* the reservation of a call whose cost was already
  known, so money that had been spent was never charged.

Also here: per-call metering (``settle_paid_call``) and the lease fence on every
metering write, because a worker that lost its lease must learn it *before* it
dispatches a paid call, not after.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import (
    FailureClass,
    RecoveryAction,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import BudgetReservationRow, StepAttemptRow, StudyRow
from aia_core.infrastructure.workflow_repository import (
    ClaimedWork,
    LeaseLost,
    WorkflowRepository,
)


@pytest.fixture
def engine_repo(session: Session, scoped: Any) -> WorkflowRepository:
    """Workflow repository as a LEAD on the primary study, funded with $100."""
    repo = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    study = session.get(StudyRow, repo.scope.study_id)
    assert study is not None
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()
    return repo


@pytest.fixture
def run(engine_repo: WorkflowRepository, session: Session, scoped: Any) -> str:
    """A one-step run."""
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Metering host", content={"goal": "g"}
    )
    return engine_repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key="metering-run",
    )


@pytest.fixture
def claimed(engine_repo: WorkflowRepository, run: str) -> ClaimedWork:
    """The run's step, claimed by worker-1."""
    work = engine_repo.claim_next(worker_id="worker-1")
    assert work is not None
    return work


def _reserve(repo: WorkflowRepository, work: ClaimedWork, amount: float) -> str:
    """Reserve for a paid call and return the reservation id."""
    reservation_id = repo.reserve_budget(
        attempt_id=work.attempt_id,
        worker_id=work.worker_id,
        amount_usd=amount,
        provider=Provider.ANTHROPIC,
    )
    assert reservation_id is not None
    return reservation_id


def _reservation(session: Session, reservation_id: str) -> BudgetReservationRow:
    row = session.get(BudgetReservationRow, reservation_id)
    assert row is not None
    session.refresh(row)
    return row


def _position(repo: WorkflowRepository) -> dict[str, float]:
    return repo.budget_position()


# --------------------------------------------------------------------------- #
# W4 -- cancellation gives the hold back
# --------------------------------------------------------------------------- #


def test_regression_cancelling_a_paid_step_releases_its_reservation(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork, session: Session
) -> None:
    """**W4.** Before, the $5 stayed reserved forever and available read $95."""
    reservation_id = _reserve(engine_repo, claimed, 5.0)
    engine_repo.request_cancel(run)

    engine_repo.abandon_attempt(claimed.attempt_id, worker_id="worker-1")

    assert _reservation(session, reservation_id).status == ReservationStatus.RELEASED.value
    position = _position(engine_repo)
    assert position["reserved_usd"] == pytest.approx(0.0)
    assert position["available_usd"] == pytest.approx(100.0)
    assert position["spent_usd"] == pytest.approx(0.0)


def test_cancelling_with_a_call_in_flight_records_uncertain_exposure(
    engine_repo: WorkflowRepository, run: str, claimed: ClaimedWork, session: Session
) -> None:
    """Cancelling does not make an in-flight call's cost go away.

    The step is cancelled, as the researcher asked, but the money that may be
    gone is shown as spent.
    """
    reservation_id = _reserve(engine_repo, claimed, 3.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.request_cancel(run)

    engine_repo.abandon_attempt(claimed.attempt_id, worker_id="worker-1")

    assert _reservation(session, reservation_id).status == ReservationStatus.SETTLED_UNCERTAIN.value
    assert _position(engine_repo)["spent_usd"] == pytest.approx(3.0)
    assert engine_repo.get_run(run)["steps"][0]["status"] is StepRunStatus.CANCELLED


# --------------------------------------------------------------------------- #
# W5 -- known spend is charged even when the attempt then fails
# --------------------------------------------------------------------------- #


def test_regression_known_spend_is_charged_when_the_attempt_then_fails(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """**W5.** The call cost $1.80 and the provider said so. Then the step failed.

    Before, the reservation was released and spent read $0.00: money gone, and
    handed back to the budget as available.
    """
    reservation_id = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.mark_paid_call_outcome_known(
        claimed.attempt_id, worker_id="worker-1", actual_cost_usd=1.80
    )

    decision = engine_repo.fail_attempt(
        claimed.attempt_id,
        worker_id="worker-1",
        failure=FailureClass.TRANSPORT,
        reservation_id=reservation_id,
    )

    assert decision.action is RecoveryAction.RETRY
    reservation = _reservation(session, reservation_id)
    assert reservation.status == ReservationStatus.SETTLED.value
    assert reservation.settled_amount_usd == pytest.approx(1.80)
    assert _position(engine_repo)["spent_usd"] == pytest.approx(1.80)
    assert _position(engine_repo)["reserved_usd"] == pytest.approx(0.0)


def test_known_spend_is_charged_when_the_lease_lapses(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """The same rule on the recovery path: a known cost is a cost."""
    _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.mark_paid_call_outcome_known(
        claimed.attempt_id, worker_id="worker-1", actual_cost_usd=1.25
    )
    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()

    decisions = engine_repo.recover_expired_attempts()

    assert decisions[0].action is RecoveryAction.RETRY
    assert _position(engine_repo)["spent_usd"] == pytest.approx(1.25)


# --------------------------------------------------------------------------- #
# The closing rule, branch by branch
# --------------------------------------------------------------------------- #


def test_a_reservation_that_was_never_dispatched_is_released_on_completion(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """Reserved, then the executor decided it did not need the call."""
    reservation_id = _reserve(engine_repo, claimed, 4.0)

    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1")

    assert _reservation(session, reservation_id).status == ReservationStatus.RELEASED.value
    assert _position(engine_repo)["available_usd"] == pytest.approx(100.0)


def test_completion_with_an_unsettled_dispatched_call_is_charged_as_uncertain(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """The work succeeded but nobody recorded what the call cost.

    Unknown is not zero: the reservation is charged as uncertain exposure rather
    than released. Scoring unknown as good is the anti-pattern this avoids.
    """
    reservation_id = _reserve(engine_repo, claimed, 2.5)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")

    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1", output={"ok": 1})

    assert _reservation(session, reservation_id).status == ReservationStatus.SETTLED_UNCERTAIN.value
    assert _position(engine_repo)["spent_usd"] == pytest.approx(2.5)


def test_cost_reported_at_completion_without_a_reservation_is_charged_once(
    engine_repo: WorkflowRepository, claimed: ClaimedWork
) -> None:
    """The unreserved path: charged directly, and not again on a retried commit."""
    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1", actual_cost_usd=0.75)
    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1", actual_cost_usd=0.75)

    assert _position(engine_repo)["spent_usd"] == pytest.approx(0.75)


def test_a_legacy_settle_at_completion_is_not_charged_twice(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """Outcome recorded, then the same cost passed to completion with the id."""
    reservation_id = _reserve(engine_repo, claimed, 5.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.mark_paid_call_outcome_known(
        claimed.attempt_id, worker_id="worker-1", actual_cost_usd=3.0
    )

    engine_repo.complete_attempt(
        claimed.attempt_id,
        worker_id="worker-1",
        actual_cost_usd=3.0,
        reservation_id=reservation_id,
    )

    assert _position(engine_repo)["spent_usd"] == pytest.approx(3.0)
    assert _reservation(session, reservation_id).settled_amount_usd == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# Per-call metering
# --------------------------------------------------------------------------- #


def test_each_call_is_charged_when_its_outcome_is_known(
    engine_repo: WorkflowRepository, claimed: ClaimedWork
) -> None:
    """Two calls in one attempt, each settled at its real cost as it returns."""
    first = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.settle_paid_call(
        claimed.attempt_id, worker_id="worker-1", reservation_id=first, actual_cost_usd=1.5
    )
    assert _position(engine_repo)["spent_usd"] == pytest.approx(1.5), "charged at once"

    second = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.settle_paid_call(
        claimed.attempt_id, worker_id="worker-1", reservation_id=second, actual_cost_usd=1.0
    )

    engine_repo.complete_attempt(claimed.attempt_id, worker_id="worker-1")

    position = _position(engine_repo)
    assert position["spent_usd"] == pytest.approx(2.5)
    assert position["reserved_usd"] == pytest.approx(0.0)
    assert engine_repo.attempt_history(claimed.step_id)[0]["actual_cost_usd"] == pytest.approx(2.5)


def test_a_settled_call_survives_a_later_crash_without_being_over_charged(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """Call one settled at $1; call two in flight when the worker dies.

    Only call two's reservation is uncertain. Call one is not charged again at
    its reserved ceiling.
    """
    first = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.settle_paid_call(
        claimed.attempt_id, worker_id="worker-1", reservation_id=first, actual_cost_usd=1.0
    )
    second = _reserve(engine_repo, claimed, 3.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()

    decisions = engine_repo.recover_expired_attempts()

    assert decisions[0].action is RecoveryAction.RECOVERY_REQUIRED
    assert _reservation(session, first).status == ReservationStatus.SETTLED.value
    assert _reservation(session, second).status == ReservationStatus.SETTLED_UNCERTAIN.value
    position = _position(engine_repo)
    assert position["spent_usd"] == pytest.approx(4.0)
    assert position["uncertain_usd"] == pytest.approx(3.0)


def test_settling_a_call_twice_charges_once(
    engine_repo: WorkflowRepository, claimed: ClaimedWork
) -> None:
    """A retried settle after a lost acknowledgement."""
    reservation_id = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    for _ in range(2):
        engine_repo.settle_paid_call(
            claimed.attempt_id,
            worker_id="worker-1",
            reservation_id=reservation_id,
            actual_cost_usd=1.2,
        )

    assert _position(engine_repo)["spent_usd"] == pytest.approx(1.2)


def test_a_call_rejected_before_billing_settles_at_zero(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """The provider refused it; the outcome is known and nothing was billed."""
    reservation_id = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    engine_repo.settle_paid_call(
        claimed.attempt_id, worker_id="worker-1", reservation_id=reservation_id, actual_cost_usd=0
    )

    decision = engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.TRANSPORT
    )

    assert decision.action is RecoveryAction.RETRY, "outcome known, so safe to retry"
    assert _position(engine_repo)["spent_usd"] == pytest.approx(0.0)
    assert _position(engine_repo)["available_usd"] == pytest.approx(100.0)


def test_a_reservation_of_another_attempt_cannot_be_settled_through_this_one(
    engine_repo: WorkflowRepository, claimed: ClaimedWork
) -> None:
    """The reservation must belong to the attempt named."""
    from aia_core.infrastructure.workflow_repository import WorkflowNotFound

    with pytest.raises(WorkflowNotFound):
        engine_repo.settle_paid_call(
            claimed.attempt_id,
            worker_id="worker-1",
            reservation_id="RSV-not-this-attempts",
            actual_cost_usd=1.0,
        )


# --------------------------------------------------------------------------- #
# The fence on metering
# --------------------------------------------------------------------------- #


def test_a_worker_that_lost_its_lease_cannot_meter_against_it(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """Reserve, dispatch and settle are all refused once the lease is gone.

    Dispatch is the one that matters: a stale worker learns it lost the lease
    *before* sending a call that would be billed to the client twice.
    """
    reservation_id = _reserve(engine_repo, claimed, 1.0)
    attempt = session.get(StepAttemptRow, claimed.attempt_id)
    assert attempt is not None
    attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
    session.flush()
    engine_repo.recover_expired_attempts()

    with pytest.raises(LeaseLost):
        _reserve(engine_repo, claimed, 1.0)
    with pytest.raises(LeaseLost):
        engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")
    with pytest.raises(LeaseLost):
        engine_repo.settle_paid_call(
            claimed.attempt_id,
            worker_id="worker-1",
            reservation_id=reservation_id,
            actual_cost_usd=1.0,
        )
    with pytest.raises(LeaseLost):
        engine_repo.mark_paid_call_outcome_known(claimed.attempt_id, worker_id="worker-1")

    open_holds = session.scalars(
        select(BudgetReservationRow).where(
            BudgetReservationRow.status == ReservationStatus.RESERVED.value
        )
    ).all()
    assert open_holds == [], "recovery released the never-dispatched hold"


def test_a_park_with_a_call_in_flight_still_records_the_exposure(
    engine_repo: WorkflowRepository, claimed: ClaimedWork, session: Session
) -> None:
    """Accounting does not depend on why the attempt stopped.

    A quota failure reported while a dispatched call has no recorded outcome
    parks the step (the domain's precedence, unchanged) -- but the reservation is
    charged as uncertain rather than released. See OI-6 for the step-state
    question this leaves open.
    """
    reservation_id = _reserve(engine_repo, claimed, 2.0)
    engine_repo.mark_paid_call_dispatched(claimed.attempt_id, worker_id="worker-1")

    decision = engine_repo.fail_attempt(
        claimed.attempt_id, worker_id="worker-1", failure=FailureClass.QUOTA
    )

    assert decision.action is RecoveryAction.PARK_PROVIDER
    assert _reservation(session, reservation_id).status == ReservationStatus.SETTLED_UNCERTAIN.value
    assert _position(engine_repo)["spent_usd"] == pytest.approx(2.0)
