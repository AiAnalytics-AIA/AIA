"""A step that hands its work to child steps, and waits for them.

Plan ``deep-research-web-search.md`` chunk 21 (fan-out): a join step returns its
tracks as child steps of the same run, any worker claims them, and the join runs
again -- a new attempt -- once every child has succeeded. The rules:

* **Domain.** Waiting is not a failure (``consumes_attempt`` is False); a paid call
  in flight with no known outcome is ``RECOVERY_REQUIRED`` and starts no child, as a
  crash at that moment would be; a cancellation wins.
* **Repository.** Children are added once per node key, claimable at once, at the
  parent's priority; the parent is ``BLOCKED`` until they succeed; a child that fails
  stalls it; the run's status follows the children.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import (
    MAX_NODE_KEY_LENGTH,
    AttemptStatus,
    FailureClass,
    RecoveryAction,
    ReservationStatus,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
    apply_cancellation,
    child_node_key,
    decide_deferral,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import BudgetReservationRow, StepDependencyRow, StudyRow
from aia_core.infrastructure.workflow_repository import (
    ClaimedWork,
    LeaseLost,
    WorkflowRepository,
)

# --------------------------------------------------------------------------- #
# Domain
# --------------------------------------------------------------------------- #


def test_a_deferral_waits_blocked_and_consumes_no_attempt() -> None:
    decision = decide_deferral(paid_call_dispatched=False, paid_call_outcome_known=False)

    assert decision.action is RecoveryAction.DEFER
    assert decision.step_status is StepRunStatus.BLOCKED
    assert decision.consumes_attempt is False
    assert decision.settle_reservation_as_uncertain is False
    assert decision.needs_human is False


def test_a_deferral_after_a_known_outcome_still_defers() -> None:
    decision = decide_deferral(paid_call_dispatched=True, paid_call_outcome_known=True)
    assert decision.action is RecoveryAction.DEFER


def test_a_deferral_with_a_call_in_flight_is_recovery_required() -> None:
    """For billing a deferral mid-call is a crash mid-call: nobody may start more work."""
    decision = decide_deferral(paid_call_dispatched=True, paid_call_outcome_known=False)

    assert decision.action is RecoveryAction.RECOVERY_REQUIRED
    assert decision.step_status is StepRunStatus.RECOVERY_REQUIRED
    assert decision.settle_reservation_as_uncertain is True


def test_a_cancellation_wins_over_a_deferral() -> None:
    decision = apply_cancellation(
        decide_deferral(paid_call_dispatched=False, paid_call_outcome_known=False),
        cancel_requested=True,
    )
    assert decision.action is RecoveryAction.CANCEL
    assert decision.step_status is StepRunStatus.CANCELLED


def test_deferred_is_a_terminal_attempt_that_holds_no_lease() -> None:
    assert AttemptStatus.DEFERRED.is_terminal
    assert not AttemptStatus.DEFERRED.holds_lease


def test_a_child_key_is_stable_and_fits_the_column() -> None:
    assert child_node_key("investigate", "DRT-W-q-0123456789ab") == (
        "investigate/DRT-W-q-0123456789ab"
    )
    long_a = child_node_key("investigate", "DRT-W-q-0123456789ab-" + "a" * 80)
    long_b = child_node_key("investigate", "DRT-W-q-0123456789ab-" + "a" * 79 + "b")
    assert len(long_a) == len(long_b) == MAX_NODE_KEY_LENGTH
    assert long_a != long_b, "two long names never collide"
    assert long_a == child_node_key("investigate", "DRT-W-q-0123456789ab-" + "a" * 80)


@pytest.mark.parametrize("prefix", ["", "a/b"])
def test_a_child_key_prefix_is_a_plain_node_key(prefix: str) -> None:
    with pytest.raises(ValueError, match="plain node key"):
        child_node_key(prefix, "x")


# --------------------------------------------------------------------------- #
# Repository
# --------------------------------------------------------------------------- #


@pytest.fixture
def repo(session: Session, scoped: Any) -> WorkflowRepository:
    repo = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    study = session.get(StudyRow, repo.scope.study_id)
    assert study is not None
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()
    return repo


@pytest.fixture
def run(repo: WorkflowRepository, session: Session, scoped: Any) -> str:
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Deferral host", content={"goal": "g"}
    )
    return repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="join",
        steps=[
            StepDefinition(node_key="join", kind="join", priority=70),
            StepDefinition(node_key="after", kind="after", depends_on=("join",)),
        ],
        idempotency_key="deferral-run",
    )


def _children(*names: str) -> list[StepDefinition]:
    return [
        StepDefinition(
            node_key=child_node_key("join", n),
            kind="track",
            stage_type="DEEP_RESEARCH",
            artifact_target="deep_research_track",
            max_attempts=3,
        )
        for n in names
    ]


def _steps(repo: WorkflowRepository, run_id: str) -> dict[str, dict[str, Any]]:
    return {s["node_key"]: s for s in repo.get_run(run_id)["steps"]}


def _claim(repo: WorkflowRepository, kind: str, worker: str = "w") -> ClaimedWork:
    work = repo.claim_next(worker_id=worker, kinds={kind})
    assert work is not None, f"nothing of kind {kind!r} to claim"
    return work


def _defer(repo: WorkflowRepository, work: ClaimedWork, *names: str) -> StepRunStatus:
    return repo.defer_attempt(
        work.attempt_id,
        worker_id="w",
        children=_children(*names),
        child_inputs={child_node_key("join", n): {"track": n} for n in names},
        child_fingerprints={child_node_key("join", n): f"fp-{n}" for n in names},
        output={"deferred": len(names)},
    )


def test_deferring_adds_claimable_children_and_blocks_the_parent(
    repo: WorkflowRepository, run: str, session: Session
) -> None:
    join = _claim(repo, "join")

    assert _defer(repo, join, "a", "b") is StepRunStatus.BLOCKED

    steps = _steps(repo, run)
    assert steps["join"]["status"] is StepRunStatus.BLOCKED
    assert steps["join"]["attempts_consumed"] == 0, "waiting is not a failure"
    assert steps["join"]["attempts"][0]["status"] is AttemptStatus.DEFERRED
    children = {k: v for k, v in steps.items() if k.startswith("join/")}
    assert set(children) == {"join/a", "join/b"}
    assert {c["status"] for c in children.values()} == {StepRunStatus.RUNNABLE}
    assert repo.get_run(run)["status"] is WorkflowRunStatus.RUNNING

    first = _claim(repo, "track")
    assert first.payload == {"track": "a"}, "children are claimed in the order handed out"
    assert first.input_fingerprint == "fp-a"
    assert first.stage_type == "DEEP_RESEARCH" and first.artifact_target == "deep_research_track"
    edges = set(
        session.scalars(
            select(StepDependencyRow.depends_on_step_id).where(
                StepDependencyRow.step_id == steps["join"]["step_id"]
            )
        ).all()
    )
    assert {c["step_id"] for c in children.values()} <= edges


def test_the_parent_runs_again_once_every_child_has_succeeded(
    repo: WorkflowRepository, run: str
) -> None:
    _defer(repo, _claim(repo, "join"), "a", "b")
    a = _claim(repo, "track")
    repo.complete_attempt(a.attempt_id, worker_id="w", output={"artifact_id": "ART-a"})
    assert _steps(repo, run)["join"]["status"] is StepRunStatus.BLOCKED, "one child still runs"
    assert repo.claim_next(worker_id="w", kinds={"join"}) is None

    b = _claim(repo, "track")
    repo.complete_attempt(b.attempt_id, worker_id="w", output={"artifact_id": "ART-b"})

    again = _claim(repo, "join")
    assert again.attempt_number == 2
    repo.complete_attempt(again.attempt_id, worker_id="w")
    after = _claim(repo, "after")
    repo.complete_attempt(after.attempt_id, worker_id="w")
    assert repo.get_run(run)["status"] is WorkflowRunStatus.COMPLETED


def test_handing_out_the_same_work_again_names_the_same_children(
    repo: WorkflowRepository, run: str
) -> None:
    """A wave handed out after an earlier one: only the new child is added."""
    _defer(repo, _claim(repo, "join"), "a")
    a = _claim(repo, "track")
    repo.complete_attempt(a.attempt_id, worker_id="w")

    _defer(repo, _claim(repo, "join"), "a", "b")
    steps = _steps(repo, run)
    assert sorted(k for k in steps if k.startswith("join/")) == ["join/a", "join/b"]
    assert steps["join/a"]["attempts_recorded"] == 1, "a succeeded child is not run again"
    assert steps["join"]["attempts_consumed"] == 0
    assert steps["join"]["status"] is StepRunStatus.BLOCKED


def test_children_that_all_succeeded_release_the_parent_at_once(
    repo: WorkflowRepository, run: str
) -> None:
    _defer(repo, _claim(repo, "join"), "a")
    a = _claim(repo, "track")
    repo.complete_attempt(a.attempt_id, worker_id="w")

    assert _defer(repo, _claim(repo, "join"), "a") is StepRunStatus.RUNNABLE


def test_a_failed_child_stalls_the_parent_and_fails_the_run(
    repo: WorkflowRepository, run: str
) -> None:
    _defer(repo, _claim(repo, "join"), "a", "b")
    a = _claim(repo, "track")
    repo.fail_attempt(a.attempt_id, worker_id="w", failure=FailureClass.SCHEMA_VIOLATION)

    steps = _steps(repo, run)
    assert steps["join/a"]["status"] is StepRunStatus.FAILED
    assert steps["join"]["status"] is StepRunStatus.BLOCKED
    assert repo.get_run(run)["status"] is WorkflowRunStatus.FAILED
    # A failed run is claimed no further: its other children and the join wait for a
    # person (a retry is a new run), as a failed sequential step would leave them.
    assert repo.claim_next(worker_id="w", kinds={"track", "join"}) is None


def test_a_deferral_with_a_call_in_flight_starts_no_child(
    repo: WorkflowRepository, run: str, session: Session
) -> None:
    join = _claim(repo, "join")
    hold = repo.reserve_budget(
        attempt_id=join.attempt_id, worker_id="w", amount_usd=2.0, provider=Provider.ANTHROPIC
    )
    assert hold is not None
    repo.mark_paid_call_dispatched(join.attempt_id, worker_id="w", reservation_id=hold)

    assert _defer(repo, join, "a") is StepRunStatus.RECOVERY_REQUIRED

    assert not any(k.startswith("join/") for k in _steps(repo, run))
    reservation = session.get(BudgetReservationRow, hold)
    assert reservation is not None
    assert reservation.status == ReservationStatus.SETTLED_UNCERTAIN.value
    assert repo.get_run(run)["status"] is WorkflowRunStatus.RECOVERY_REQUIRED


def test_a_deferral_charges_what_the_attempt_spent(
    repo: WorkflowRepository, run: str, session: Session
) -> None:
    """A re-plan paid for before the wave was handed out is charged, not dropped."""
    join = _claim(repo, "join")
    hold = repo.reserve_budget(
        attempt_id=join.attempt_id, worker_id="w", amount_usd=2.0, provider=Provider.ANTHROPIC
    )
    assert hold is not None
    repo.mark_paid_call_dispatched(join.attempt_id, worker_id="w", reservation_id=hold)
    repo.settle_paid_call(join.attempt_id, worker_id="w", reservation_id=hold, actual_cost_usd=0.5)
    idle = repo.reserve_budget(
        attempt_id=join.attempt_id, worker_id="w", amount_usd=1.0, provider=Provider.ANTHROPIC
    )

    assert _defer(repo, join, "a") is StepRunStatus.BLOCKED

    position = repo.budget_position()
    assert position["spent_usd"] == pytest.approx(0.5)
    assert position["reserved_usd"] == pytest.approx(0.0)
    released = session.get(BudgetReservationRow, idle)
    assert released is not None and released.status == ReservationStatus.RELEASED.value


def test_a_cancelled_run_adds_no_child_and_cancels_the_parent(
    repo: WorkflowRepository, run: str
) -> None:
    join = _claim(repo, "join")
    repo.request_cancel(run)

    assert _defer(repo, join, "a") is StepRunStatus.CANCELLED
    assert not any(k.startswith("join/") for k in _steps(repo, run))
    assert repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


def test_cancelling_a_waiting_run_cancels_the_parent_and_its_children(
    repo: WorkflowRepository, run: str
) -> None:
    _defer(repo, _claim(repo, "join"), "a", "b")
    running = _claim(repo, "track")

    repo.request_cancel(run)

    steps = _steps(repo, run)
    assert steps["join"]["status"] is StepRunStatus.CANCELLED
    assert steps["join/b"]["status"] is StepRunStatus.CANCELLED
    assert steps["join/a"]["status"] is StepRunStatus.RUNNING, "cooperative: its worker stops"
    repo.abandon_attempt(running.attempt_id, worker_id="w")
    assert repo.get_run(run)["status"] is WorkflowRunStatus.CANCELLED


def test_only_the_lease_holder_defers(repo: WorkflowRepository, run: str) -> None:
    join = _claim(repo, "join")
    with pytest.raises(LeaseLost):
        repo.defer_attempt(join.attempt_id, worker_id="someone-else", children=_children("a"))


@pytest.mark.parametrize(
    ("children", "message"),
    [
        ([], "at least one child"),
        (_children("a", "a"), "each child once"),
        ([StepDefinition(node_key="join/x", kind="track", depends_on=("join",))], "depends on"),
    ],
)
def test_a_malformed_deferral_is_refused(
    repo: WorkflowRepository, run: str, children: list[StepDefinition], message: str
) -> None:
    join = _claim(repo, "join")
    with pytest.raises(ValueError, match=message):
        repo.defer_attempt(join.attempt_id, worker_id="w", children=children)


def test_a_child_cannot_take_another_steps_node_key(repo: WorkflowRepository, run: str) -> None:
    join = _claim(repo, "join")
    with pytest.raises(ValueError, match="already name other steps"):
        repo.defer_attempt(
            join.attempt_id,
            worker_id="w",
            children=[StepDefinition(node_key="after", kind="track")],
        )
    with pytest.raises(ValueError, match="its own child"):
        repo.defer_attempt(
            join.attempt_id,
            worker_id="w",
            children=[StepDefinition(node_key="join", kind="join")],
        )
