"""The cross-study work queue, and the scope a worker executes under.

A worker must find work in any study, but nothing may read any study's research
data without an issued scope. The split is:

* ``WorkQueue`` -- claim, recover, resume, refuse; across studies; returns no
  research data;
* ``ScopeResolver.execution_context`` -- issues a ``StudyContext`` **only against
  a lease the worker holds**, with the worker's permission set
  (``WORKER_PERMISSIONS``, ADR 0019: the Researcher's work, never its approvals).

These tests pin both halves, and the isolation between them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.scope import (
    WORKER_PERMISSIONS,
    ClientStatus,
    Permission,
    ScopeDenied,
    ScopeRole,
)
from aia_core.domain.workflow import (
    FailureClass,
    RecoveryAction,
    StepDefinition,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    ClientRow,
    StepAttemptRow,
    StudyRow,
)
from aia_core.infrastructure.workflow_repository import (
    WorkflowNotFound,
    WorkflowRepository,
    WorkQueue,
)


def _run_in(session: Session, scoped: Any, study: str, *, user: str, kind: str = "k") -> str:
    """Create a one-step run in a study, as ``user``."""
    scope = scoped.scope(user=user, study=study)
    project, _ = ProjectRepository(session, scope).create(title=f"{study} host")
    return WorkflowRepository(session, scope).create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind=kind)],
        idempotency_key=f"{study}-{kind}",
    )


@pytest.fixture
def two_clients(session: Session, scoped: Any) -> dict[str, str]:
    """A run in the primary client's study and one in the other client's."""
    return {
        "primary": _run_in(session, scoped, "primary", user="lead"),
        "other_client": _run_in(session, scoped, "other_client", user="other_lead"),
    }


# --------------------------------------------------------------------------- #
# WorkQueue
# --------------------------------------------------------------------------- #


def test_the_queue_claims_work_from_every_study(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    queue = WorkQueue(session)

    first = queue.claim_next(worker_id="w", kinds=None)
    second = queue.claim_next(worker_id="w", kinds=None)

    assert first is not None and second is not None
    assert {first.run_id, second.run_id} == set(two_clients.values())
    assert {first.study_id, second.study_id} == {
        scoped.studies["primary"].study_id,
        scoped.studies["other_client"].study_id,
    }
    assert queue.claim_next(worker_id="w", kinds=None) is None


def test_the_queue_claims_only_kinds_the_worker_can_execute(session: Session, scoped: Any) -> None:
    """An old worker in a rolling deploy must not claim, and then fail, a new kind."""
    known = _run_in(session, scoped, "primary", user="lead", kind="known")
    _run_in(session, scoped, "sibling", user="lead", kind="brand_new")
    queue = WorkQueue(session)

    claimed = queue.claim_next(worker_id="w", kinds={"known"})
    assert claimed is not None
    assert claimed.run_id == known
    assert queue.claim_next(worker_id="w", kinds={"known"}) is None
    assert queue.claim_next(worker_id="w", kinds=set()) is None, "no executors, no claims"
    assert queue.claim_next(worker_id="w", kinds={"brand_new"}) is not None


def test_the_queue_recovers_across_studies_and_charges_each_its_own_exposure(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    """Uncertain exposure lands on the study that reserved it, not the caller's."""
    queue = WorkQueue(session)
    for study in ("primary", "other_client"):
        row = session.get(StudyRow, scoped.studies[study].study_id)
        assert row is not None
        row.budget_usd, row.spent_usd = 50.0, 0.0
    session.flush()

    amounts = {}
    for amount in (2.0, 3.0):
        work = queue.claim_next(worker_id="w", kinds=None)
        assert work is not None
        context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
        repo = WorkflowRepository(session, context)
        repo.reserve_budget(
            attempt_id=work.attempt_id,
            worker_id="w",
            amount_usd=amount,
            provider=Provider.ANTHROPIC,
        )
        repo.mark_paid_call_dispatched(work.attempt_id, worker_id="w")
        attempt = session.get(StepAttemptRow, work.attempt_id)
        assert attempt is not None
        attempt.lease_until = datetime.now(UTC) - timedelta(minutes=5)
        amounts[work.study_id] = amount
    session.flush()

    decisions = queue.recover_expired_attempts()

    assert [d.action for d in decisions] == [RecoveryAction.RECOVERY_REQUIRED] * 2
    for study_id, amount in amounts.items():
        row = session.get(StudyRow, study_id)
        assert row is not None
        session.refresh(row)
        assert row.spent_usd == pytest.approx(amount)


def test_the_queue_resumes_parks_across_studies(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    queue = WorkQueue(session)
    for _ in two_clients:
        work = queue.claim_next(worker_id="w", kinds=None)
        assert work is not None
        context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
        WorkflowRepository(session, context).fail_attempt(
            work.attempt_id, worker_id="w", failure=FailureClass.PROVIDER_CAPACITY
        )

    assert len(queue.resume_waiting_steps(capacity_backoff_seconds=0)) == 2
    assert queue.claim_next(worker_id="w", kinds=None) is not None


def test_refusing_an_attempt_fails_it_closed(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    queue = WorkQueue(session)
    work = queue.claim_next(worker_id="w", kinds=None)
    assert work is not None

    decision = queue.refuse(work.attempt_id, worker_id="w", reason="client_archived")

    assert decision.action is RecoveryAction.FAIL
    lead = WorkflowRepository(
        session,
        scoped.scope(
            user="lead" if work.run_id == two_clients["primary"] else "other_lead",
            study="primary" if work.run_id == two_clients["primary"] else "other_client",
        ),
    )
    run = lead.get_run(work.run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    assert run["steps"][0]["attempts"][0]["error"] == {"reason": "client_archived"}


def test_the_queue_exposes_no_scoped_repository(session: Session) -> None:
    """The unscoped engine inside the queue refuses anything that needs a scope."""
    queue = WorkQueue(session)
    engine = queue._engine
    with pytest.raises(RuntimeError):
        _ = engine.scope
    with pytest.raises(RuntimeError):
        engine.budget_position()


# --------------------------------------------------------------------------- #
# ScopeResolver.execution_context
# --------------------------------------------------------------------------- #


def test_the_execution_context_names_the_claimed_study_and_nothing_else(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None

    context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")

    assert (context.organization_id, context.client_id, context.study_id) == (
        work.organization_id,
        work.client_id,
        work.study_id,
    )
    assert context.request_id == f"{work.run_id}/{work.attempt_id}"


def test_the_execution_role_does_the_work_and_never_approves_it(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    """The worker runs, edits and uploads -- but no gate, no budget, no access changes.

    ADR 0019 decision 6: a Researcher now holds every permission, so the worker's
    narrower ``WORKER_PERMISSIONS`` is what keeps the AI's executor from accepting
    its own work.
    """
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None
    context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")

    assert context.role is ScopeRole.RESEARCHER
    assert context.has(Permission.RUN_WORKFLOW)
    assert context.permissions == WORKER_PERMISSIONS
    assert frozenset(Permission) > WORKER_PERMISSIONS
    for withheld in (
        Permission.APPROVE_GATE,
        Permission.APPROVE_BUDGET,
        Permission.MANAGE_STUDY_ACCESS,
        Permission.MANAGE_STUDY_BUDGET,
        Permission.SIGN_OFF_DELIVERABLE,
    ):
        with pytest.raises(ScopeDenied):
            context.require(withheld)


def test_the_execution_actor_is_the_person_who_started_the_run(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    """So a gate the worker opens records that person as the producer."""
    queue = WorkQueue(session)
    for _ in two_clients:
        work = queue.claim_next(worker_id="w", kinds=None)
        assert work is not None
        context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
        expected = "lead" if work.run_id == two_clients["primary"] else "other_lead"
        assert context.actor_id == scoped.users[expected]


def _open_gate_under_execution_scope(session: Session, scoped: Any) -> tuple[Any, str]:
    """A run triggered by the lead, claimed by a worker that opens an approval gate."""
    _run_in(session, scoped, "primary", user="lead")
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None
    context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    gate_id = WorkflowRepository(session, context).open_gate(
        step_id=work.step_id, question="Proceed?", options=["approve", "cancel"]
    )
    return context, gate_id


def test_a_gate_opened_under_execution_scope_cannot_be_decided_by_the_execution_scope(
    session: Session, scoped: Any
) -> None:
    """ADR 0019 decision 6: the worker holds no gate authority, whatever the policy says.

    The trigger's own self-approval policy is permissive by default, and the
    execution context carries it (``self_approval.allowed``), yet it still cannot
    decide: independence is not authority, and the permission is withheld.
    """
    context, gate_id = _open_gate_under_execution_scope(session, scoped)
    assert context.self_approval.allowed is True
    assert not context.has(Permission.APPROVE_GATE)

    with pytest.raises(ScopeDenied):
        WorkflowRepository(session, context).decide_gate(gate_id, option="approve")


def test_the_person_who_triggered_a_run_may_decide_its_gate_by_default(
    session: Session, scoped: Any
) -> None:
    """ADR 0019: the gate the worker opened is the trigger's to accept, and it says so."""
    _, gate_id = _open_gate_under_execution_scope(session, scoped)

    WorkflowRepository(session, scoped.scope(user="lead")).decide_gate(gate_id, option="approve")

    record = session.scalars(select(ApprovalDecisionRow)).one()
    assert record.producer_user_id == record.approver_user_id == scoped.users["lead"]
    assert record.self_approved is True
    assert record.self_approval_source == "default"


def test_a_gate_opened_under_execution_scope_cannot_be_self_approved_where_the_policy_is_off(
    session: Session, scoped: Any
) -> None:
    """Separation of duties still holds when the worker is the one asking and a scope demands it."""
    from aia_core.domain.scope import SeparationOfDutiesViolation

    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, client_id=scoped.clients["primary"].client_id
    )
    session.flush()
    _, gate_id = _open_gate_under_execution_scope(session, scoped)

    with pytest.raises(SeparationOfDutiesViolation):
        WorkflowRepository(session, scoped.scope(user="lead")).decide_gate(
            gate_id, option="approve"
        )

    # A different person may still decide it.
    WorkflowRepository(session, scoped.scope(user="reviewer")).decide_gate(
        gate_id, option="approve"
    )


@pytest.mark.parametrize("worker_id", ["someone-else", ""])
def test_only_the_lease_holder_gets_an_execution_context(
    session: Session, scoped: Any, two_clients: dict[str, str], worker_id: str
) -> None:
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None

    with pytest.raises(ScopeDenied) as denied:
        scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id=worker_id)
    assert denied.value.reason == "lease_not_held"


def test_a_finished_attempt_gets_no_execution_context(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None
    context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    WorkflowRepository(session, context).complete_attempt(work.attempt_id, worker_id="w")

    with pytest.raises(ScopeDenied) as denied:
        scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    assert denied.value.reason == "lease_not_held"


def test_an_unknown_attempt_gets_no_execution_context(scoped: Any) -> None:
    with pytest.raises(ScopeDenied) as denied:
        scoped.resolver.execution_context(attempt_id="ATT-nope", worker_id="w")
    assert denied.value.reason == "unknown_attempt"


def test_an_archived_clients_work_fails_closed(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    work = WorkQueue(session).claim_next(worker_id="w", kinds=None)
    assert work is not None
    client = session.get(ClientRow, work.client_id)
    assert client is not None
    client.status = ClientStatus.ARCHIVED.value
    session.flush()

    with pytest.raises(ScopeDenied) as denied:
        scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    assert denied.value.reason == "client_archived"


def test_an_execution_context_cannot_reach_another_studys_attempt(
    session: Session, scoped: Any, two_clients: dict[str, str]
) -> None:
    """The context is the claimed study's, and the repository enforces it."""
    queue = WorkQueue(session)
    first = queue.claim_next(worker_id="w", kinds=None)
    second = queue.claim_next(worker_id="w", kinds=None)
    assert first is not None and second is not None
    assert first.client_id != second.client_id

    context = scoped.resolver.execution_context(attempt_id=first.attempt_id, worker_id="w")
    repo = WorkflowRepository(session, context)

    with pytest.raises(WorkflowNotFound):
        repo.complete_attempt(second.attempt_id, worker_id="w")
    with pytest.raises(WorkflowNotFound):
        repo.heartbeat(second.attempt_id, worker_id="w")
    assert repo.get_run(first.run_id)["steps"][0]["status"] is StepRunStatus.RUNNING


def test_decided_gates_are_readable_by_the_step_that_asked(session: Session, scoped: Any) -> None:
    """A step re-run after approval must see the decision, or it asks forever."""
    _run_in(session, scoped, "primary", user="researcher")
    queue = WorkQueue(session)
    work = queue.claim_next(worker_id="w", kinds=None)
    assert work is not None
    context = scoped.resolver.execution_context(attempt_id=work.attempt_id, worker_id="w")
    repo = WorkflowRepository(session, context)
    repo.fail_attempt(work.attempt_id, worker_id="w", failure=FailureClass.APPROVAL_REQUIRED)
    gate_id = repo.open_gate(step_id=work.step_id, question="Go?", options=["approve", "cancel"])
    WorkflowRepository(session, scoped.scope(user="lead")).decide_gate(
        gate_id, option="approve", note="fine"
    )

    again = queue.claim_next(worker_id="w", kinds=None)
    assert again is not None
    assert again.step_id == work.step_id
    decisions = WorkflowRepository(
        session, scoped.resolver.execution_context(attempt_id=again.attempt_id, worker_id="w")
    ).decided_gates(again.step_id)
    assert [(d["gate_id"], d["option"], d["note"]) for d in decisions] == [
        (gate_id, "approve", "fine")
    ]
