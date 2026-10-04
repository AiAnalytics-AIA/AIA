"""The spend confirmation over HTTP (plan 5b.2): a study's limit, a run's ceiling, the yes.

The deployment's settings carry what the worker reserves per request; the page is shown the
ceiling that gives, a study may set a limit, and a start whose ceiling reaches it must carry a
confirmation that covers it. The request never names the ceiling: the server works it out.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ApprovalDecisionRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"

#: 450 respondents, seven closed items in one block, 0.5 reserved per request.
CEILING = 450 * 0.5

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
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_fieldwork_reservation_usd": 0.5})


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _revision(c: TestClient, world: Any) -> str:
    made = c.post(
        f"{_study(world)}/design/revisions", json={"content": DESIGN, "source_stage": "run"}
    )
    assert made.status_code in (200, 201), made.text
    return str(made.json()["revision_id"])


def _limit(c: TestClient, world: Any, usd: float | None) -> Any:
    return c.put(f"{_study(world)}/spend-confirm", json={"limit_usd": usd})


def _start(c: TestClient, world: Any, revision: str, **body: Any) -> Any:
    return c.post(f"{_study(world)}/research/runs", json={"design_revision_id": revision, **body})


def _spend_rows(app: FastAPI) -> list[Any]:
    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
            ).all()
        )


def test_readiness_shows_the_ceiling_and_whether_starting_will_ask(
    researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    url = f"{_study(world)}/research/readiness?design_revision_id={revision}"
    plain = researcher.get(url).json()
    assert plain["cost_ceiling_usd"] == CEILING
    assert plain["fieldwork_requests"] == 450 and plain["analysis_calls"] == 0
    assert plain["cost_ceiling_unknown"] is None
    assert plain["spend_confirm_usd"] is None and plain["confirmation_required"] is False

    assert _limit(researcher, world, CEILING).status_code == 200  # at the limit asks
    asks = researcher.get(url).json()
    assert asks["spend_confirm_usd"] == CEILING and asks["confirmation_required"] is True

    assert _limit(researcher, world, CEILING + 1.0).status_code == 200
    assert researcher.get(url).json()["confirmation_required"] is False


def test_a_limit_is_set_read_back_cleared_and_validated(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    assert viewer.get(_study(world)).json()["spend_confirm_usd"] is None
    set_ = _limit(researcher, world, 40.0)
    assert set_.status_code == 200, set_.text
    assert set_.json()["spend_confirm_usd"] == 40.0
    assert viewer.get(_study(world)).json()["spend_confirm_usd"] == 40.0  # any member reads it
    assert _limit(researcher, world, None).json()["spend_confirm_usd"] is None
    for bad in ({"limit_usd": -1.0}, {}, {"limit_usd": 1.0, "extra": 1}, {"limit_usd": "x"}):
        assert researcher.put(f"{_study(world)}/spend-confirm", json=bad).status_code == 422


def test_a_start_whose_ceiling_reaches_the_limit_asks_and_creates_no_run(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409, asked.text
    body = asked.json()
    assert body["code"] == "cost_confirmation_required"
    assert body["details"] == {"ceiling_usd": CEILING, "limit_usd": 100.0}
    assert researcher.get(f"{_study(world)}/research/runs").json()["items"] == []
    assert _spend_rows(app) == []


def test_a_confirmation_that_covers_the_ceiling_starts_the_run_and_is_recorded(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    # The page confirms what the server showed it, not a figure of its own.
    shown = researcher.get(
        f"{_study(world)}/research/readiness?design_revision_id={revision}"
    ).json()["cost_ceiling_usd"]
    started = _start(researcher, world, revision, confirm_cost_usd=shown)
    assert started.status_code == 201, started.text
    [row] = _spend_rows(app)
    assert row.run_id == started.json()["run_id"] and row.decision == "confirm"


def test_a_confirmation_below_the_ceiling_is_refused(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    low = _start(researcher, world, revision, confirm_cost_usd=CEILING - 1.0)
    assert low.status_code == 409 and low.json()["code"] == "cost_confirmation_required"
    assert _spend_rows(app) == []


def test_a_retry_asks_again(researcher: TestClient, world: Any, app: FastAPI) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    run_id = _start(researcher, world, revision, confirm_cost_usd=CEILING).json()["run_id"]
    runs = f"{_study(world)}/research/runs"
    assert researcher.post(f"{runs}/{run_id}/cancel").status_code == 200

    asked = researcher.post(f"{runs}/{run_id}/retry")
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    retried = researcher.post(f"{runs}/{run_id}/retry", json={"confirm_cost_usd": CEILING})
    assert retried.status_code == 201, retried.text
    assert len(_spend_rows(app)) == 2


def test_an_unknown_ceiling_is_refused_when_there_is_a_limit_and_not_otherwise(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The API was not given what the worker reserves: that is not a cheap run."""
    app.state.settings = app.state.settings.model_copy(
        update={"ai_fieldwork_reservation_usd": None}
    )
    revision = _revision(researcher, world)
    url = f"{_study(world)}/research/readiness?design_revision_id={revision}"
    shown = researcher.get(url).json()
    assert shown["cost_ceiling_usd"] is None
    assert shown["cost_ceiling_unknown"] == "fieldwork_reservation_missing"

    _limit(researcher, world, 100.0)
    refused = _start(researcher, world, revision)
    assert refused.status_code == 409 and refused.json()["code"] == "cost_ceiling_unknown"
    assert refused.json()["details"]["reason"] == "fieldwork_reservation_missing"

    _limit(researcher, world, None)
    assert _start(researcher, world, revision).status_code == 201


def test_the_limit_route_needs_a_signed_in_member(client: TestClient, world: Any) -> None:
    assert client.put(f"{_study(world)}/spend-confirm", json={"limit_usd": 1.0}).status_code == 401


def test_the_request_cannot_name_the_ceiling(researcher: TestClient, world: Any) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    forged = _start(researcher, world, revision, ceiling_usd=1.0)
    assert forged.status_code == 422  # extra fields are refused, so there is nothing to forge
