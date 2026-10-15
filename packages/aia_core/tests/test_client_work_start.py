"""A person starts the client's own work (client-budget CB3b).

The scope is issued by the resolver to a member allowed to run client work, never built
from a request. The work runs in the client's own project -- created once, no study,
invisible to every study -- and its run names no study, so the client's budget pays.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.application.client_work import client_work_project, start_client_work
from aia_core.domain.scope import (
    CLIENT_WORK_PROJECT_OWNER,
    WORKER_PERMISSIONS,
    ClientPermission,
    ClientStatus,
    ClientWorkContext,
    ScopeDenied,
)
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import ClientRow, ProjectRow, WorkflowRunRow


def work_scope(scoped: Any, user: str = "lead", client: str = "primary") -> ClientWorkContext:
    return scoped.resolver.client_work_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_a_member_who_may_run_client_work_gets_its_scope_and_approves_nothing(
    scoped: Any, session: Session
) -> None:
    lead_client = scoped.resolver.client_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients["primary"].client_id
    )
    assert lead_client.has(ClientPermission.RUN_CLIENT_WORK)
    scope = work_scope(scoped)
    assert (scope.client_id, scope.actor_id) == (
        scoped.clients["primary"].client_id,
        scoped.users["lead"],
    )
    assert scope.permissions == WORKER_PERMISSIONS
    client = session.get(ClientRow, scope.client_id)
    assert client is not None
    client.status = ClientStatus.ARCHIVED.value
    session.flush()
    with pytest.raises(ScopeDenied):
        work_scope(scoped)


def test_the_work_runs_in_the_clients_own_project_and_names_no_study(
    scoped: Any, session: Session
) -> None:
    scope = work_scope(scoped)
    started = start_client_work(
        session, scope, workflow_type=DEVELOP_SNAPSHOT, idempotency_key="extract:SRC-1"
    )
    assert started.created
    run = session.get(WorkflowRunRow, started.run_id)
    project = session.get(ProjectRow, started.project_id)
    assert run is not None and project is not None
    assert (run.client_id, run.study_id, run.triggered_by) == (
        scope.client_id,
        None,
        scoped.users["lead"],
    )
    assert (project.owner, project.study_id) == (CLIENT_WORK_PROJECT_OWNER, None)

    # The same key finds the same run; another key reuses the one project.
    again = start_client_work(
        session, scope, workflow_type=DEVELOP_SNAPSHOT, idempotency_key="extract:SRC-1"
    )
    assert (again.run_id, again.created) == (started.run_id, False)
    other = start_client_work(
        session, scope, workflow_type=DEVELOP_SNAPSHOT, idempotency_key="extract:SRC-2"
    )
    assert other.project_id == started.project_id
    assert client_work_project(session, scope) == started.project_id
    owned = session.scalars(
        select(ProjectRow).where(ProjectRow.owner == CLIENT_WORK_PROJECT_OWNER)
    ).all()
    assert len(owned) == 1


def test_no_study_and_no_other_client_reaches_the_clients_own_project(
    scoped: Any, session: Session
) -> None:
    started = start_client_work(
        session, work_scope(scoped), workflow_type=DEVELOP_SNAPSHOT, idempotency_key="k"
    )
    study = scoped.scope(user="lead", study="primary")
    assert started.project_id not in {
        p.project_id for p in ProjectRepository(session, study).list_projects(limit=50).items
    }
    for owner in (None, CLIENT_WORK_PROJECT_OWNER):
        assert started.project_id not in {
            p.project_id
            for p in ProjectRepository(session, study, owner=owner).list_projects(limit=50).items
        }
    other = work_scope(scoped, "other_lead", "other")
    assert client_work_project(session, other) != started.project_id
    with pytest.raises(TypeError):
        ProjectRepository(session, work_scope(scoped))  # no owner: a study's projects
