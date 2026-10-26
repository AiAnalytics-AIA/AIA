"""The organization's spend over HTTP (settings-backends SB3, develop-spend-attribution 6).

OWNER and ADMIN read what the organization spent, held and could not price, and the open
studies at 90 % of their budget or more; anyone else is refused before a row is read.
"""

from __future__ import annotations

from typing import Any

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.providers import Provider
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import StudyRow, WorkflowRunRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

URL = "/api/v1/settings/organization-spend"


def _spend(
    app: FastAPI,
    world: Any,
    user: str,
    amount: float,
    *,
    key: str,
    nobody: bool = False,
    settle: bool = True,
) -> None:
    """A hold of ``amount`` on a run ``user`` started (or naming nobody), settled or left
    open."""
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(
                user_id=world.users[user], organization_id=world.organization_id
            ),
            study_id=world.study_id("primary"),
        )
        repo = WorkflowRepository(session, scope)
        project, _ = ProjectRepository(session, scope).create(title=key, content={"g": key})
        run_id = repo.create_run(
            project_id=project.project_id,
            project_revision=1,
            workflow_type="deep_research",
            steps=[StepDefinition(node_key="only", kind="k", stage_type="RESEARCH")],
            idempotency_key=key,
        )
        if nobody:
            run = session.get(WorkflowRunRow, run_id)
            assert run is not None
            run.triggered_by = None
        work = repo.claim_next(worker_id="w")
        assert work is not None and work.run_id == run_id
        hold = repo.reserve_budget(
            attempt_id=work.attempt_id,
            worker_id="w",
            amount_usd=amount,
            provider=Provider.ANTHROPIC,
        )
        assert hold is not None
        if settle:
            repo.settle_reservation(hold, actual_cost_usd=amount)
            repo.complete_attempt(work.attempt_id, worker_id="w", output={})
        session.commit()


def _study(app: FastAPI, world: Any, name: str, **values: Any) -> None:
    with create_session_factory(app.state.engine)() as session:
        row = session.get(StudyRow, world.study_id(name))
        assert row is not None
        for k, v in values.items():
            setattr(row, k, v)
        session.commit()


def test_an_owner_reads_the_organizations_spend_with_nobody_included(
    app: FastAPI, world: Any, owner: TestClient
) -> None:
    _spend(app, world, "lead", 0.4, key="a")
    _spend(app, world, "researcher", 0.25, key="b")
    _spend(app, world, "lead", 0.3, key="c", nobody=True)
    _spend(app, world, "lead", 0.5, key="d", settle=False)
    response = owner.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period"] == "this_month" and body["currency"] == "USD"
    # Tool holds settled outside the ledger; the unattributed one is the organization's too.
    assert body["tools_usd"] == 0.95 and body["model_usd"] == 0.0
    assert body["spent_usd"] == 0.95
    assert body["reserved_usd"] == 0.5 and body["uncertain_calls"] == 0
    deep = next(a for a in body["by_activity"] if a["activity"] == "deep_research")
    assert deep["spent_usd"] == 0.95
    assert [a["activity"] for a in body["by_activity"]] == [
        "lead",
        "fieldwork",
        "analysis_report",
        "deep_research",
        "other",
    ]


def test_open_studies_from_ninety_percent_of_their_budget_are_listed_fullest_first(
    app: FastAPI, world: Any, owner: TestClient
) -> None:
    _spend(app, world, "lead", 0.5, key="held", settle=False)
    _study(app, world, "primary", budget_usd=1.0, spent_usd=0.45)  # 0.45 + 0.5 held: 95 %
    _study(app, world, "sibling", budget_usd=200.0, spent_usd=180.0)  # 90 %, at the line
    _study(app, world, "other_client", budget_usd=300.0, spent_usd=299.0, status="ARCHIVED")
    body = owner.get(URL).json()
    listed = [(n["study_name"], n["client_name"], round(n["share"], 4)) for n in body["near_limit"]]
    assert listed == [("Acme brand", "Acme Corp", 0.95), ("Acme pricing", "Acme Corp", 0.9)]
    first = body["near_limit"][0]
    assert (first["spent_usd"], first["held_usd"], first["used_usd"]) == (0.45, 0.5, 0.95)
    assert body["near_limit_share"] == 0.9


def test_a_researcher_is_refused_and_reads_nothing(
    app: FastAPI, world: Any, researcher: TestClient
) -> None:
    _spend(app, world, "researcher", 0.25, key="b")
    refused = researcher.get(URL)
    assert refused.status_code == 403
    assert refused.json()["code"] == "insufficient_role"
    assert "0.25" not in refused.text


def test_the_period_is_one_of_three(owner: TestClient) -> None:
    for period in ("this_month", "last_month", "year_to_date"):
        assert owner.get(URL, params={"period": period}).status_code == 200
    assert owner.get(URL, params={"period": "forever"}).status_code == 422


def test_without_a_session_nothing_is_read(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
