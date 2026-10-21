"""Per-researcher spend over HTTP (``develop-spend-attribution`` 7, Q40).

OWNER and ADMIN read everyone's spend and what is booked to nobody; a researcher reads only
their own, and asking cannot widen it. The figures are what the rows hold, never a zero for an
unknown.
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

URL = "/api/v1/settings/researcher-spend"


def _spend(
    app: FastAPI, world: Any, user: str, amount: float, *, key: str, nobody: bool = False
) -> None:
    """A settled hold of ``amount`` on a run ``user`` started (or one naming nobody)."""
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(
                user_id=world.users[user], organization_id=world.organization_id
            ),
            study_id=world.study_id("primary"),
        )
        repo = WorkflowRepository(session, scope)
        study = session.get(StudyRow, scope.study_id)
        assert study is not None
        study.budget_usd = 100.0
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
        repo.settle_reservation(hold, actual_cost_usd=amount)
        repo.complete_attempt(work.attempt_id, worker_id="w", output={})
        session.commit()


def test_an_owner_reads_everyone_and_the_unattributed(
    app: FastAPI, world: Any, owner: TestClient
) -> None:
    _spend(app, world, "lead", 0.4, key="a")
    _spend(app, world, "researcher", 0.25, key="b")
    _spend(app, world, "lead", 0.3, key="c", nobody=True)
    response = owner.get(URL)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["everyone"] is True and body["period"] == "this_month"
    by = {p["user_id"]: p for p in body["people"]}
    assert by[world.users["lead"]]["outside_ledger_usd"] == 0.4
    assert by[world.users["researcher"]]["total_usd"] == 0.25
    assert by[None]["total_usd"] == 0.3 and body["people"][-1]["user_id"] is None
    lead = by[world.users["lead"]]
    assert [a["activity"] for a in lead["by_activity"]] == [
        "lead",
        "fieldwork",
        "analysis_report",
        "deep_research",
        "other",
    ]
    deep = next(a for a in lead["by_activity"] if a["activity"] == "deep_research")
    assert deep["total_usd"] == 0.4
    assert lead["study_count"] == 1
    [study] = lead["studies"]
    assert (study["study_name"], study["client_name"]) == ("Acme brand", "Acme Corp")
    # A member with nothing booked is a known zero.
    assert by[world.users["outsider"]]["total_usd"] == 0.0


def test_a_researcher_sees_only_themself(app: FastAPI, world: Any, researcher: TestClient) -> None:
    _spend(app, world, "lead", 0.4, key="a")
    _spend(app, world, "researcher", 0.25, key="b")
    _spend(app, world, "lead", 0.3, key="c", nobody=True)
    body = researcher.get(URL).json()
    assert body["everyone"] is False
    assert [p["user_id"] for p in body["people"]] == [world.users["researcher"]]
    assert body["people"][0]["total_usd"] == 0.25
    # Nothing in the answer names the other person's figures or the unattributed row.
    assert world.users["lead"] not in str(body)


def test_the_period_is_one_of_three(app: FastAPI, world: Any, owner: TestClient) -> None:
    for period in ("this_month", "last_month", "year_to_date"):
        assert owner.get(URL, params={"period": period}).status_code == 200
    assert owner.get(URL, params={"period": "forever"}).status_code == 422


def test_without_a_session_nothing_is_read(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
