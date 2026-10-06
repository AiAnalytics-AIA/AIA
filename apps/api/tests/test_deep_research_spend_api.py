"""A Deep Research start asks first over HTTP when its ceiling reaches the study's limit.

Plan ``deep-research-web-search.md`` chunk 22, ADR 0019 gate 2, as a research run's start
does it (``test_research_spend_api.py``). The deployment's settings carry the research
agents' reservation per request and the mode switches the worker composes from; the server
works the ceiling out, and the request never names it.
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
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}

#: One web track, EXHAUSTIVE, the planned mode, 0.5 reserved per request: the planner (1), a
#: request per search (10), the verifier over min(10 x 12, 16 - 1 + 12) = 27 candidates in
#: batches of 12 (3), the synthesizer (1) -- 15 requests. No retrieval route is on.
EXHAUSTIVE_PLANNED = 15 * 0.5
#: The same under the lead: its plan and 6 re-plans (7), its ceiling's 720 turns, 50 tasks'
#: verification at 3 batches each (150), the brief synthesizer and its one repair (2) --
#: 879 requests.
EXHAUSTIVE_LEAD = 879 * 0.5


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_research_reservation_usd": 0.5})


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _url(world: Any) -> str:
    return f"{_study(world)}/deep-research/runs"


def _revision(c: TestClient, world: Any) -> str:
    made = c.post(
        f"{_study(world)}/design/revisions", json={"content": DESIGN, "source_stage": "brief"}
    )
    assert made.status_code == 201, made.text
    return str(made.json()["revision_id"])


def _limit(c: TestClient, world: Any, usd: float | None) -> None:
    assert c.put(f"{_study(world)}/spend-confirm", json={"limit_usd": usd}).status_code == 200


def _start(
    c: TestClient, world: Any, revision: str, preset: str = "EXHAUSTIVE", **body: Any
) -> Any:
    return c.post(
        _url(world),
        json={"design_revision_id": revision, "preset_name": preset, "channels": ["WEB"], **body},
    )


def _spend_rows(app: FastAPI) -> list[Any]:
    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
            ).all()
        )


def test_an_exhaustive_run_over_the_limit_asks_then_starts_on_a_yes_recorded_once(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 5.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409, asked.text
    assert asked.json()["code"] == "cost_confirmation_required"
    assert asked.json()["details"] == {"ceiling_usd": EXHAUSTIVE_PLANNED, "limit_usd": 5.0}
    assert researcher.get(_url(world)).json() == []
    low = _start(researcher, world, revision, confirm_cost_usd=EXHAUSTIVE_PLANNED - 0.5)
    assert low.status_code == 409

    started = _start(researcher, world, revision, confirm_cost_usd=EXHAUSTIVE_PLANNED)
    assert started.status_code == 201, started.text
    assert started.json()["preset"] == "EXHAUSTIVE"
    [row] = _spend_rows(app)
    assert row.run_id == started.json()["run_id"] and row.decision == "confirm"
    # The same submission again: the run that exists, nothing asked, nothing more recorded.
    again = _start(researcher, world, revision)
    assert again.status_code == 200 and again.json()["run_id"] == started.json()["run_id"]
    assert len(_spend_rows(app)) == 1


def test_under_the_limit_it_does_not_ask(researcher: TestClient, world: Any, app: FastAPI) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, EXHAUSTIVE_PLANNED + 0.5)
    assert _start(researcher, world, revision).status_code == 201
    assert _spend_rows(app) == []


def test_the_ceiling_is_the_mode_the_worker_composes(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(
        update={"deep_research_agent_directed": True, "deep_research_lead": True}
    )
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409
    assert asked.json()["details"]["ceiling_usd"] == EXHAUSTIVE_LEAD


def test_a_retry_asks_again(researcher: TestClient, world: Any, app: FastAPI) -> None:
    revision = _revision(researcher, world)
    _limit(researcher, world, 5.0)
    run_id = _start(researcher, world, revision, confirm_cost_usd=EXHAUSTIVE_PLANNED).json()[
        "run_id"
    ]
    assert researcher.post(f"{_url(world)}/{run_id}/cancel").status_code == 200
    asked = researcher.post(f"{_url(world)}/{run_id}/retry")
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    retried = researcher.post(
        f"{_url(world)}/{run_id}/retry", json={"confirm_cost_usd": EXHAUSTIVE_PLANNED}
    )
    assert retried.status_code == 201, retried.text
    assert len(_spend_rows(app)) == 2


def test_an_unset_reservation_is_refused_with_a_limit_and_not_without(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_research_reservation_usd": None})
    revision = _revision(researcher, world)
    _limit(researcher, world, 100.0)
    refused = _start(researcher, world, revision)
    assert refused.status_code == 409 and refused.json()["code"] == "cost_ceiling_unknown"
    details = refused.json()["details"]
    assert details["reason"] == "deep_research_price_missing"
    assert details["kinds"] == ["planner", "investigator", "verifier", "synthesizer"]
    _limit(researcher, world, None)
    assert _start(researcher, world, revision).status_code == 201


def test_the_request_cannot_name_the_ceiling(researcher: TestClient, world: Any) -> None:
    revision = _revision(researcher, world)
    named = _start(researcher, world, revision, ceiling_usd=0.01)
    assert named.status_code == 422
