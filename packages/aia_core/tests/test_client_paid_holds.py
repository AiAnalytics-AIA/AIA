"""A study or the client as the payer (client-budget CB2).

A run with no study is the client's own work, paid by the client's budget. These tests
pin the schema and the repository's money paths for it: the hold names its client, is
checked against the client's budget alone and charged to the client alone; a study's
holds and spend never move the client's, nor the client's any study's. Until CB3 issues
a client run through the worker, the run here is a study run made the client's by hand,
exactly the rows a client-owned project and run will have.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import ReservationStatus, StepDefinition
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import (
    BudgetReservationRow,
    ClientRow,
    ProjectRow,
    StudyRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import (
    BudgetExceeded,
    ClaimedWork,
    WorkflowRepository,
)


def _run_and_claim(
    session: Session, scoped: Any, key: str
) -> tuple[WorkflowRepository, ClaimedWork]:
    repo = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title=key, content={"goal": "g"}
    )
    repo.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="only", kind="k")],
        idempotency_key=key,
    )
    work = repo.claim_next(worker_id="worker-1")
    assert work is not None
    return repo, work


def _make_client_paid(session: Session, run_id: str) -> None:
    """The rows CB3's client run will have: a client-owned project and no study."""
    run = session.get(WorkflowRunRow, run_id)
    assert run is not None
    project = session.get(ProjectRow, run.project_id)
    assert project is not None
    project.owner, project.study_id = "client_sources", None
    run.study_id = None
    session.flush()


def _reserve(queue: WorkflowRepository, work: ClaimedWork, amount: float) -> str:
    reservation_id = queue.reserve_budget(
        attempt_id=work.attempt_id,
        worker_id=work.worker_id,
        amount_usd=amount,
        provider=Provider.ANTHROPIC,
    )
    assert reservation_id is not None
    return reservation_id


@pytest.fixture
def funded(session: Session, scoped: Any) -> tuple[ClientRow, StudyRow]:
    client = session.get(ClientRow, scoped.clients["primary"].client_id)
    study = session.get(StudyRow, scoped.studies["primary"].study_id)
    assert client is not None and study is not None
    client.budget_usd, client.spent_usd = 10.0, 0.0
    study.budget_usd, study.spent_usd = 100.0, 0.0
    session.flush()
    return client, study


def test_a_study_hold_names_its_client_and_charges_the_study_alone(
    session: Session, scoped: Any, funded: tuple[ClientRow, StudyRow]
) -> None:
    client, study = funded
    repo, work = _run_and_claim(session, scoped, "study-paid")
    reservation_id = _reserve(repo, work, 4.0)
    hold = session.get(BudgetReservationRow, reservation_id)
    assert hold is not None
    assert (hold.client_id, hold.study_id) == (client.client_id, study.study_id)
    repo.settle_paid_call(
        work.attempt_id, worker_id="worker-1", reservation_id=reservation_id, actual_cost_usd=3.0
    )
    session.refresh(client)
    session.refresh(study)
    assert (study.spent_usd, client.spent_usd) == (3.0, 0.0)


def test_a_client_hold_is_checked_against_and_charged_to_the_client_alone(
    session: Session, scoped: Any, funded: tuple[ClientRow, StudyRow]
) -> None:
    client, study = funded
    _, work = _run_and_claim(session, scoped, "client-paid")
    _make_client_paid(session, work.run_id)
    queue = WorkflowRepository._across_studies(session)

    # The study's $100 is not the client's: $11 exceeds the client's $10.
    with pytest.raises(BudgetExceeded) as refused:
        _reserve(queue, work, 11.0)
    assert (refused.value.remaining, refused.value.limit) == (10.0, 10.0)

    reservation_id = _reserve(queue, work, 6.0)
    hold = session.get(BudgetReservationRow, reservation_id)
    assert hold is not None
    assert (hold.client_id, hold.study_id) == (client.client_id, None)
    # The client's budget says what is held: $6 of $10, $4 left (never the study's).
    position = ScopeRepository(session).client_budget(
        scoped.resolver.client_context(
            scoped.principal(scoped.users["lead"]), client_id=client.client_id
        )
    )
    assert (position.reserved_usd, position.available_usd) == (6.0, 4.0)
    # The client's own hold counts against the client's next one.
    with pytest.raises(BudgetExceeded):
        _reserve(queue, work, 5.0)

    queue.settle_paid_call(
        work.attempt_id, worker_id="worker-1", reservation_id=reservation_id, actual_cost_usd=2.5
    )
    session.refresh(hold)
    session.refresh(client)
    session.refresh(study)
    assert hold.status == ReservationStatus.SETTLED.value
    assert (client.spent_usd, study.spent_usd) == (2.5, 0.0)


def test_a_study_hold_does_not_use_up_the_clients_budget(
    session: Session, scoped: Any, funded: tuple[ClientRow, StudyRow]
) -> None:
    repo, study_work = _run_and_claim(session, scoped, "study-first")
    _reserve(repo, study_work, 50.0)
    _, client_work = _run_and_claim(session, scoped, "client-second")
    _make_client_paid(session, client_work.run_id)
    # The study's $50 hold is outstanding; the client's $10 is still all there.
    _reserve(WorkflowRepository._across_studies(session), client_work, 10.0)


def test_only_the_clients_own_project_may_name_no_study(session: Session, scoped: Any) -> None:
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="ordinary", content={"goal": "g"}
    )
    row = session.get(ProjectRow, project.project_id)
    assert row is not None
    row.study_id = None
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
