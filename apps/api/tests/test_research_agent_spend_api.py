"""An agent job's start and rebuild over HTTP meet the study's confirmation threshold
(lead-orchestration LO15), as a run's start does (``test_research_spend_api.py``).

The deployment's ``AIA_AI_RESEARCH_RESERVATION_USD`` is the job's ceiling; the request never
names it. Before LO15 a direct start or rebuild read no ``spend_confirm_usd`` at all, and only the
Lead's approve path asked.
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
RESERVATION = 2.0


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_research_reservation_usd": RESERVATION})


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _jobs(world: Any) -> str:
    return f"{_study(world)}/research/agent-jobs"


def _revision(c: TestClient, world: Any) -> str:
    made = world.design(c, {"title": "Fictional", "goal": "Test concept"}, source_stage="brief")
    assert made.status_code in (200, 201), made.text
    return str(made.json()["revision_id"])


def _limit(c: TestClient, world: Any, usd: float | None) -> None:
    assert c.put(f"{_study(world)}/spend-confirm", json={"limit_usd": usd}).status_code == 200


def _spend_rows(app: FastAPI) -> list[Any]:
    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
            ).all()
        )


def test_a_direct_start_above_the_threshold_asks_then_starts_on_a_covering_yes(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    rid = _revision(researcher, world)
    _limit(researcher, world, 1.0)
    body = {"design_revision_id": rid, "action": "analyze_brief"}
    asked = researcher.post(_jobs(world), json=body)
    assert asked.status_code == 409, asked.text
    assert asked.json()["code"] == "cost_confirmation_required"
    assert asked.json()["details"] == {"ceiling_usd": RESERVATION, "limit_usd": 1.0}
    assert researcher.get(_jobs(world)).json() == []
    low = researcher.post(_jobs(world), json={**body, "confirm_cost_usd": RESERVATION - 0.5})
    assert low.status_code == 409 and _spend_rows(app) == []

    started = researcher.post(_jobs(world), json={**body, "confirm_cost_usd": RESERVATION})
    assert started.status_code == 201, started.text
    [row] = _spend_rows(app)
    assert row.run_id == started.json()["run_id"] and row.decision == "confirm"
    # The same ask again follows the job: no second confirmation, no second row.
    again = researcher.post(_jobs(world), json=body)
    assert again.status_code == 200 and again.json()["run_id"] == started.json()["run_id"]
    assert len(_spend_rows(app)) == 1


def test_a_rebuild_above_the_threshold_asks_too(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    rid = _revision(researcher, world)
    first = researcher.post(
        _jobs(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    )
    assert first.status_code == 201, first.text
    _limit(researcher, world, 1.0)
    url = f"{_jobs(world)}/{first.json()['run_id']}/rebuild"
    asked = researcher.post(url, json={"design_revision_id": rid})
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    rebuilt = researcher.post(
        url, json={"design_revision_id": rid, "confirm_cost_usd": RESERVATION}
    )
    assert rebuilt.status_code == 201, rebuilt.text
    assert rebuilt.json()["rebuild_of"] == first.json()["run_id"]
    [row] = _spend_rows(app)
    assert row.run_id == rebuilt.json()["run_id"]


def test_below_the_threshold_or_without_one_nothing_asks(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    rid = _revision(researcher, world)
    _limit(researcher, world, RESERVATION + 1.0)
    started = researcher.post(
        _jobs(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    )
    assert started.status_code == 201, started.text
    _limit(researcher, world, None)
    other = researcher.post(
        _jobs(world), json={"design_revision_id": rid, "action": "critique_design"}
    )
    assert other.status_code == 201, other.text
    assert _spend_rows(app) == []


def test_an_unconfigured_reservation_is_unknown_never_zero(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_research_reservation_usd": None})
    rid = _revision(researcher, world)
    _limit(researcher, world, 1.0)
    refused = researcher.post(
        _jobs(world),
        json={"design_revision_id": rid, "action": "analyze_brief", "confirm_cost_usd": 50.0},
    )
    assert refused.status_code == 409 and refused.json()["code"] == "cost_ceiling_unknown"
    assert refused.json()["details"]["reason"] == "research_reservation_missing"


def test_the_request_cannot_name_the_ceiling(researcher: TestClient, world: Any) -> None:
    rid = _revision(researcher, world)
    for extra in ({"ceiling_usd": 0.0}, {"confirm_cost_usd": -1.0}, {"reservation_usd": 0.0}):
        r = researcher.post(
            _jobs(world), json={"design_revision_id": rid, "action": "analyze_brief", **extra}
        )
        assert r.status_code == 422, extra
