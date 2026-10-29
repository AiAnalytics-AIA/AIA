"""A run's approval-ledger rows over HTTP: read only, found through the Study, names not e-mails.

``GET …/research/runs/{run_id}/approvals`` answers what people decided on a run (the spend
confirmation here) with who and when. Another study's run, and any run asked by a user of another
organization, is the 404 an absent run gets.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Settings

API = "/api/v1"
ABSENT_RUN = "RUN-0000000000000000"
DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        }
    ],
}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_fieldwork_reservation_usd": 0.5})


def _confirmed_run(c: TestClient, world: Any) -> tuple[str, float]:
    """A run started with a spend confirmation: (its id, the ceiling the person confirmed)."""
    study = f"{API}/studies/{world.study_id()}"
    made = world.design(c, DESIGN)
    assert made.status_code in (200, 201), made.text
    revision = made.json()["revision_id"]
    assert c.put(f"{study}/spend-confirm", json={"limit_usd": 1.0}).status_code == 200
    ceiling = c.get(f"{study}/research/readiness?design_revision_id={revision}").json()[
        "cost_ceiling_usd"
    ]
    started = c.post(
        f"{study}/research/runs",
        json={"design_revision_id": revision, "confirm_cost_usd": ceiling},
    )
    assert started.status_code == 201, started.text
    return str(started.json()["run_id"]), float(ceiling)


def _other_organization(app: FastAPI) -> TestClient:
    """The owner of a second organization, signed in."""
    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.scope_repository import ScopeRepository

    email = "o@elsewhere.example"
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).create_organization(
            slug="elsewhere", name="Elsewhere", owner_email=email
        )
        session.commit()
    app.state.identity_provider.register("token-elsewhere", subject=email, email=email)
    client = TestClient(app)
    client.headers.update({"Authorization": "Bearer token-elsewhere"})
    return client


def test_a_run_s_spend_confirmation_is_read_with_who_and_when(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    run_id, _ = _confirmed_run(researcher, world)
    url = f"{API}/studies/{world.study_id()}/research/runs/{run_id}/approvals"
    read = viewer.get(url)  # any member of the organization reads it
    assert read.status_code == 200, read.text
    [row] = read.json()
    assert (row["subject"], row["subject_id"], row["decision"]) == ("spend", run_id, "confirm")
    assert row["by"] == "researcher" and row["self_approved"] is True
    assert row["at"]
    assert "@" not in read.text, "a person is named by display name, never an e-mail"


def test_a_run_with_no_decision_reads_empty(researcher: TestClient, world: Any) -> None:
    made = world.design(researcher, DESIGN)
    study = f"{API}/studies/{world.study_id()}"
    started = researcher.post(
        f"{study}/research/runs", json={"design_revision_id": made.json()["revision_id"]}
    )
    assert started.status_code == 201, started.text
    read = researcher.get(f"{study}/research/runs/{started.json()['run_id']}/approvals")
    assert (read.status_code, read.json()) == (200, [])


def test_another_study_s_run_is_an_absent_run(researcher: TestClient, world: Any) -> None:
    run_id, _ = _confirmed_run(researcher, world)
    sibling = f"{API}/studies/{world.study_id('sibling')}/research/runs"
    across = researcher.get(f"{sibling}/{run_id}/approvals")
    absent = researcher.get(f"{sibling}/{ABSENT_RUN}/approvals")
    assert across.status_code == absent.status_code == 404
    assert across.json()["code"] == absent.json()["code"]


def test_a_user_of_another_organization_gets_404(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    run_id, _ = _confirmed_run(researcher, world)
    stranger = _other_organization(app)
    url = f"{API}/studies/{world.study_id()}/research/runs"
    across = stranger.get(f"{url}/{run_id}/approvals")
    absent = stranger.get(f"{url}/{ABSENT_RUN}/approvals")
    assert across.status_code == absent.status_code == 404
    assert across.json()["code"] == absent.json()["code"]


def test_the_route_writes_nothing(researcher: TestClient, world: Any) -> None:
    run_id, _ = _confirmed_run(researcher, world)
    url = f"{API}/studies/{world.study_id()}/research/runs/{run_id}/approvals"
    assert researcher.get(url).json() == researcher.get(url).json()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(researcher, method)(url).status_code == 405
