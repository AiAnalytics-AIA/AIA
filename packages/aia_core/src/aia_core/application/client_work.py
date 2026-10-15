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
from aia_core.domain.scope import CLIENT_WORK_PROJECT_OWNER, ClientWorkContext, Permission
from aia_core.infrastructure.repositories import ProjectRepository

from .workflows import StartedRun, start_workflow

__all__ = ["client_work_project", "start_client_work"]


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
