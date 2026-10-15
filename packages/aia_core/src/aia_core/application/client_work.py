"""Starting the client's own work, paid by the client's budget (client-budget CB3b).

Work on the client itself -- AI proposals from its documents -- belongs to no study. It
runs in the client's own project (``projects.owner = client_sources``, no study), created
on first use and seen by no generic route, and its runs name no study, so every hold and
charge falls on the client's budget. A person starts it under a :class:`ClientWorkContext`
that :meth:`ScopeResolver.client_work_context` issues to a member holding
``RUN_CLIENT_WORK``; nothing here takes a client id from the caller.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from aia_core.domain.pipeline import ProjectType
from aia_core.domain.scope import (
    CLIENT_WORK_PROJECT_OWNER,
    ClientContext,
    ClientPermission,
    ClientWorkContext,
    Permission,
    ScopeDenied,
)
from aia_core.domain.workflow import StepRunStatus
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.workflow_repository import BudgetWaitNotLiftable, WorkflowRepository

from .research import BudgetNotRaised, ResearchStepNotFound
from .workflows import StartedRun, start_workflow

__all__ = ["client_work_project", "lift_client_budget_wait", "start_client_work"]


def client_work_project(session: Session, scope: ClientWorkContext) -> str:
    """The client's own project, created on first use: one per client, no study."""
    projects = ProjectRepository(session, scope, owner=CLIENT_WORK_PROJECT_OWNER)
    found = projects.list_projects(limit=1).items
    if found:
        return found[0].project_id
    project, _ = projects.create(
        title="Práce na klientovi",
        project_type=ProjectType.RESEARCH,
        content={},
        created_by=scope.actor_id,
        reason="client_work",
    )
    return project.project_id


def start_client_work(
    session: Session,
    scope: ClientWorkContext,
    *,
    workflow_type: str,
    idempotency_key: str,
    step_inputs: dict[str, dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StartedRun:
    """Enqueue ``workflow_type`` as the client's own work, or find the run already made.

    The run names no study; the client's budget pays for every call it makes. Refused
    (``ScopeDenied``) without ``RUN_WORKFLOW`` on the scope, before anything is written.
    """
    scope.require(Permission.RUN_WORKFLOW)
    return start_workflow(
        session,
        scope,
        project_id=client_work_project(session, scope),
        workflow_type=workflow_type,
        idempotency_key=idempotency_key,
        step_inputs=step_inputs,
        metadata=metadata,
        owner=CLIENT_WORK_PROJECT_OWNER,
    )


def lift_client_budget_wait(
    session: Session,
    client: ClientContext,
    work: ClientWorkContext,
    run_id: str,
    node_key: str,
    *,
    budget_usd: float,
    note: str = "",
) -> dict[str, Any]:
    """Raise the client's budget to ``budget_usd`` and let its waiting step go on (CB4).

    A step of the client's own work whose hold would pass the client's budget stops in
    ``AWAITING_BUDGET`` without spending an attempt. A person who holds
    ``MANAGE_CLIENT_BUDGET`` lifts it: the budget is raised (audited) and the decision is
    a ``budget`` approval naming the client and no study. ``client`` and ``work`` are the
    same person's scopes on the same client. Equal to the current budget lifts the wait
    without changing it; below it is refused. Checked before anything is written.
    """
    if (client.organization_id, client.client_id, client.actor_id) != (
        work.organization_id,
        work.client_id,
        work.actor_id,
    ):
        raise ScopeDenied("not found", reason="scope_mismatch")
    client.require(ClientPermission.MANAGE_CLIENT_BUDGET)
    workflows = WorkflowRepository(session, work)
    run = workflows.get_run(run_id)
    step = next((s for s in run["steps"] if s["node_key"] == node_key), None)
    if step is None:
        raise ResearchStepNotFound(node_key)
    if step["status"] is not StepRunStatus.AWAITING_BUDGET:
        raise BudgetWaitNotLiftable("only a step waiting for budget can be lifted")
    scopes = ScopeRepository(session)
    # Locked before it is compared: a concurrent lift waits here, then reads what the
    # first committed, so a raise is never overwritten by a smaller one decided earlier.
    current = scopes.client_budget(client, for_update=True).budget_usd
    if budget_usd < current:
        raise BudgetNotRaised(offered=budget_usd, current=current)
    if budget_usd > current:
        scopes.set_client_budget(client, budget_usd)
    workflows.resume_client_budget_wait(
        client, step["step_id"], note=note, budget_before=current, budget_after=budget_usd
    )
    return workflows.get_run(run_id)
