"""Lifting the client's own work over its budget (client-budget CB4).

A step of the client's work parks AWAITING_BUDGET when the client's budget cannot hold
its call. A person who may manage the client's budget raises it and the step goes on;
the decision is a ``budget`` approval naming the client and no study.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.application.client_work import lift_client_budget_wait, start_client_work
from aia_core.application.research import BudgetNotRaised
from aia_core.domain.scope import ClientContext, ClientPermission, ClientWorkContext, ScopeDenied
from aia_core.domain.workflow import StepRunStatus
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    ApprovalDecisionRow,
    ClientRow,
    StepRunRow,
)
from aia_core.infrastructure.workflow_repository import BudgetWaitNotLiftable, WorkflowNotFound


def scopes(
    scoped: Any, user: str = "lead", client: str = "primary"
) -> tuple[ClientContext, ClientWorkContext]:
    principal = scoped.principal(scoped.users[user])
    client_id = scoped.clients[client].client_id
    return (
        scoped.resolver.client_context(principal, client_id=client_id),
        scoped.resolver.client_work_context(principal, client_id=client_id),
    )


def parked(session: Session, scoped: Any) -> tuple[str, str]:
    """A client run whose step is waiting for budget; the client's budget $1."""
    _, work = scopes(scoped)
    started = start_client_work(session, work, workflow_type=DEVELOP_SNAPSHOT, idempotency_key="p")
    step = session.scalars(select(StepRunRow).where(StepRunRow.run_id == started.run_id)).first()
    assert step is not None
    step.status = StepRunStatus.AWAITING_BUDGET.value
    client = session.get(ClientRow, work.client_id)
    assert client is not None
    client.budget_usd = 1.0
    session.flush()
    return started.run_id, step.node_key


def test_a_person_lifts_the_wait_by_raising_the_clients_budget(
    session: Session, scoped: Any
) -> None:
    run_id, node = parked(session, scoped)
    client, work = scopes(scoped)
    run = lift_client_budget_wait(
        session, client, work, run_id, node, budget_usd=4.0, note="víc podkladů"
    )
    assert next(s for s in run["steps"] if s["node_key"] == node)["status"] is (
        StepRunStatus.RUNNABLE
    )
    row = session.get(ClientRow, client.client_id)
    assert row is not None and row.budget_usd == 4.0
    [decision] = session.scalars(
        select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "budget")
    ).all()
    assert (decision.client_id, decision.study_id, decision.decision, decision.comment) == (
        client.client_id,
        None,
        "lift",
        "víc podkladů",
    )
    assert session.scalars(
        select(AccessAuditRow.reason).where(AccessAuditRow.action == "CLIENT_BUDGET_CHANGED")
    ).all() == ["1.0 -> 4.0"]
    # A second lift finds nothing waiting.
    with pytest.raises(BudgetWaitNotLiftable):
        lift_client_budget_wait(session, client, work, run_id, node, budget_usd=4.0)


def test_a_lift_is_refused_before_anything_is_written(session: Session, scoped: Any) -> None:
    run_id, node = parked(session, scoped)
    client, work = scopes(scoped)
    with pytest.raises(BudgetNotRaised):
        lift_client_budget_wait(session, client, work, run_id, node, budget_usd=0.5)
    without = dataclasses.replace(
        client,
        permissions=frozenset(
            p for p in client.permissions if p is not ClientPermission.MANAGE_CLIENT_BUDGET
        ),
    )
    with pytest.raises(ScopeDenied):
        lift_client_budget_wait(session, without, work, run_id, node, budget_usd=4.0)
    other_client, other_work = scopes(scoped, "other_lead", "other")
    with pytest.raises(ScopeDenied):
        lift_client_budget_wait(session, other_client, work, run_id, node, budget_usd=4.0)
    with pytest.raises(WorkflowNotFound):
        lift_client_budget_wait(session, other_client, other_work, run_id, node, budget_usd=4.0)
    row = session.get(ClientRow, client.client_id)
    assert row is not None and row.budget_usd == 1.0
    assert session.scalars(select(ApprovalDecisionRow)).all() == []
