"""The scope a worker runs the client's own work under (client-budget CB3).

A run naming no study is the client's own work. The worker's scope for it is issued only
against the held lease, for the run's client, with the worker's permissions and no study.
Under it the workflow repository sees only the client's own runs, reserves and charges
the client, and refuses everything that needs a study; egress attributes the call to the
client with no study; the gateway's execution context accepts it.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.scope import ScopeResolver
from aia_core.domain.ai_execution import ExecutionContext
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone, evaluate_egress
from aia_core.domain.scope import (
    WORKER_PERMISSIONS,
    ClientStatus,
    ClientWorkContext,
    ScopeDenied,
    StudyContext,
    payer_study_id,
)
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import ClientRow, ProjectRow, StudyRow, WorkflowRunRow
from aia_core.infrastructure.workflow_repository import (
    BudgetExceeded,
    ClaimedWork,
    WorkflowNotFound,
    WorkflowRepository,
)

ROUTE = ProviderRoute(
    route_id="eu-managed-inference",
    provider="approved_eu_managed",
    zone=ResidencyZone.EU,
    eu_processing_approved=True,
    excluded_from_training=True,
    retention_days=0,
    approved_for=frozenset({DataClass.CLASS_A_CLIENT_CONFIDENTIAL}),
)


def _claimed(session: Session, scoped: Any, key: str, *, client_paid: bool) -> ClaimedWork:
    """A claimed one-step run; made the client's own (no study) when ``client_paid``."""
    study_scope = scoped.scope(user="lead", study="primary")
    repo = WorkflowRepository(session, study_scope)
    project, _ = ProjectRepository(session, study_scope).create(title=key, content={"g": 1})
    run_id = repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key=key,
    )
    work = repo.claim_next(worker_id="worker-1")
    assert work is not None and work.run_id == run_id
    if client_paid:
        run = session.get(WorkflowRunRow, run_id)
        prj = session.get(ProjectRow, project.project_id)
        assert run is not None and prj is not None
        prj.owner, prj.study_id, run.study_id = "client_sources", None, None
        session.flush()
    return work


def _issue(session: Session, work: ClaimedWork, worker: str = "worker-1") -> Any:
    return ScopeResolver(session).execution_context(attempt_id=work.attempt_id, worker_id=worker)


def test_a_client_run_gets_the_clients_work_scope_and_no_study(
    session: Session, scoped: Any
) -> None:
    work = _claimed(session, scoped, "client", client_paid=True)
    scope = _issue(session, work)
    assert isinstance(scope, ClientWorkContext)
    assert (scope.organization_id, scope.client_id) == (
        scoped.organization_id,
        scoped.clients["primary"].client_id,
    )
    assert scope.permissions == WORKER_PERMISSIONS
    assert payer_study_id(scope) is None
    assert not hasattr(scope, "study_id")
    # A study run keeps its study's scope, exactly as before.
    study_work = _claimed(session, scoped, "study", client_paid=False)
    assert isinstance(_issue(session, study_work), StudyContext)


def test_it_is_issued_only_against_the_lease_and_never_for_an_archived_client(
    session: Session, scoped: Any
) -> None:
    work = _claimed(session, scoped, "lease", client_paid=True)
    with pytest.raises(ScopeDenied) as other_worker:
        _issue(session, work, worker="worker-2")
    assert other_worker.value.reason == "lease_not_held"
    client = session.get(ClientRow, scoped.clients["primary"].client_id)
    assert client is not None
    client.status = ClientStatus.ARCHIVED.value
    session.flush()
    with pytest.raises(ScopeDenied) as archived:
        _issue(session, work)
    assert archived.value.reason == "client_archived"


def test_under_it_the_repository_sees_the_clients_work_alone_and_charges_the_client(
    session: Session, scoped: Any
) -> None:
    client = session.get(ClientRow, scoped.clients["primary"].client_id)
    study = session.get(StudyRow, scoped.studies["primary"].study_id)
    assert client is not None and study is not None
    client.budget_usd, study.budget_usd = 5.0, 100.0
    session.flush()
    study_work = _claimed(session, scoped, "a study run", client_paid=False)
    work = _claimed(session, scoped, "the client's run", client_paid=True)
    repo = WorkflowRepository(session, _issue(session, work))

    with pytest.raises(BudgetExceeded):
        repo.reserve_budget(
            attempt_id=work.attempt_id,
            worker_id="worker-1",
            amount_usd=6.0,
            provider=Provider.ANTHROPIC,
        )
    hold = repo.reserve_budget(
        attempt_id=work.attempt_id,
        worker_id="worker-1",
        amount_usd=4.0,
        provider=Provider.ANTHROPIC,
    )
    assert hold is not None
    repo.settle_paid_call(
        work.attempt_id, worker_id="worker-1", reservation_id=hold, actual_cost_usd=1.5
    )
    session.refresh(client)
    session.refresh(study)
    assert (client.spent_usd, study.spent_usd) == (1.5, 0.0)

    # A study's run is not in the client's work scope, and nothing about a study is open.
    with pytest.raises(WorkflowNotFound):
        repo.reserve_budget(
            attempt_id=study_work.attempt_id,
            worker_id="worker-1",
            amount_usd=1.0,
            provider=Provider.ANTHROPIC,
        )
    with pytest.raises(ScopeDenied) as no_study:
        repo.budget_position()
    assert no_study.value.reason == "client_work_scope"


def test_egress_and_the_gateway_attribute_client_work_to_the_client_with_no_study(
    session: Session, scoped: Any
) -> None:
    scope = _issue(session, _claimed(session, scoped, "egress", client_paid=True))
    decision = evaluate_egress(
        scope=scope, data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL, route=ROUTE
    )
    assert (decision.client_id, decision.study_id) == (scope.client_id, None)
    ExecutionContext(scope=scope, runtime_version="t", journal=object())  # type: ignore[arg-type]
    # A forged grant is refused before anything can use it.
    with pytest.raises(ScopeDenied) as forged:
        dataclasses.replace(scope, grant=object())  # type: ignore[arg-type]
    assert forged.value.reason == "forged_scope"
