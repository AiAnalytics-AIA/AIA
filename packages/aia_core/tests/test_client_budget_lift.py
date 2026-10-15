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


def test_a_lift_decided_on_a_stale_budget_never_lowers_one_raised_meanwhile(
    session: Session, scoped: Any, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two of the client's steps wait. B decides to lift its step to $8 and is held just
    before it writes; meanwhile A lifts the other to $10. A must wait for B's lock and
    then raise over B's $8, never be overwritten by it: the budget ends at $10.

    PostgreSQL only: the guard is the client row's lock, which SQLite does not take (it
    serialises writers instead)."""
    import threading
    import time

    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.scope_repository import ScopeRepository

    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    first_run, node = parked(session, scoped)
    _, work = scopes(scoped)
    second = start_client_work(session, work, workflow_type=DEVELOP_SNAPSHOT, idempotency_key="q")
    step = session.scalars(select(StepRunRow).where(StepRunRow.run_id == second.run_id)).one()
    step.status = StepRunStatus.AWAITING_BUDGET.value
    session.commit()
    client, work = scopes(scoped)

    b_decided, b_go = threading.Event(), threading.Event()
    real = ScopeRepository.set_client_budget

    def held(self: ScopeRepository, scope: ClientContext, budget_usd: float) -> Any:
        if budget_usd == 8.0:  # B: decided, now held before it writes
            b_decided.set()
            assert b_go.wait(30)
        return real(self, scope, budget_usd)

    monkeypatch.setattr(ScopeRepository, "set_client_budget", held)
    factory = create_session_factory(engine)
    errors: list[BaseException] = []

    def lift(run_id: str, amount: float) -> None:
        try:
            with factory() as own:
                lift_client_budget_wait(own, client, work, run_id, node, budget_usd=amount)
                own.commit()
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    b = threading.Thread(target=lift, args=(second.run_id, 8.0))
    b.start()
    assert b_decided.wait(30)
    a = threading.Thread(target=lift, args=(first_run, 10.0))
    a.start()
    # Room for A to finish if nothing holds it; with the lock it waits for B.
    time.sleep(1.0)
    b_go.set()
    b.join(30)
    a.join(30)
    assert not errors, errors
    row = session.get(ClientRow, client.client_id)
    assert row is not None
    session.refresh(row)
    assert row.budget_usd == 10.0


def test_a_lift_takes_the_run_before_the_client_as_a_completing_step_does(
    session: Session, scoped: Any, engine: Any
) -> None:
    """A worker finishing another step of the same run holds the run, then charges the
    client; a lift must take the same locks in the same order (run, then client), or
    the two deadlock and PostgreSQL aborts one of them.

    PostgreSQL only: SQLite takes no row locks."""
    import threading
    import time

    from sqlalchemy import update

    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.workflow_repository import WorkflowRepository

    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    run_id, node = parked(session, scoped)
    session.commit()
    client, work = scopes(scoped)
    factory = create_session_factory(engine)
    holding, errors = threading.Event(), []

    def completing_step() -> None:
        # As complete_attempt: the run first, then (settling a hold) the client.
        try:
            with factory() as own:
                WorkflowRepository._across_studies(own)._lock_run(run_id)
                holding.set()
                time.sleep(1.0)
                own.execute(
                    update(ClientRow)
                    .where(ClientRow.client_id == client.client_id)
                    .values(spent_usd=ClientRow.spent_usd + 0.25)
                )
                own.commit()
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    def lifting() -> None:
        try:
            with factory() as own:
                lift_client_budget_wait(own, client, work, run_id, node, budget_usd=4.0)
                own.commit()
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=completing_step)
    worker.start()
    assert holding.wait(30)
    lift = threading.Thread(target=lifting)
    lift.start()
    worker.join(30)
    lift.join(30)
    assert not errors, errors
    row = session.get(ClientRow, client.client_id)
    assert row is not None
    session.refresh(row)
    assert (row.budget_usd, row.spent_usd) == (4.0, 0.25)
