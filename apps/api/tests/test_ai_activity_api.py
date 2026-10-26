"""Settings → AI běh over HTTP: each activity's last answered call (settings-redesign F14).

Every activity the settings document lists, in its order, with its last answered call or null;
the newest answered row wins and a failure is not an answer; OWNER and ADMIN only; nothing in an
answer names a client, study or person.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.analysis.harness import AGENT_ID as ANALYSIS
from aia_core.domain.research_lead import LEAD_AGENT_ID
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import AIUsageEventRow
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.routers.settings import _native_runtime

API = "/api/v1/settings/ai-activity"
T0 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def _row(world: Any, n: int, agent: str, at: datetime, outcome: str, **kw: str) -> AIUsageEventRow:
    return AIUsageEventRow(
        event_id=f"EV-{n}",
        call_id=f"CALL-{n}",
        outcome=outcome,
        purpose="PRIMARY",
        organization_id=world.organization_id,
        client_id=world.client_id(),
        study_id=world.study_id(),
        actor_id="USR-1",
        agent_id=agent,
        agent_version="1",
        prompt_id=agent,
        prompt_version="1",
        capability=kw.get("capability", ModelCapability.RESEARCH_REASONING.value),
        policy_version="p",
        runtime_version=kw.get("build", "0123abc"),
        provider="bedrock",
        model="eu.asked",
        served_model=kw.get("served", ""),
        route_id="bedrock-eu-primary",
        data_class="CLASS_C_INTERNAL",
        residency_zone="EU",
        cost_usd=0.02,
        cost_basis="METERED",
        occurred_at=at,
    )


def test_every_listed_activity_in_order_null_where_nothing_answered(owner: TestClient) -> None:
    body = owner.get(API).json()
    assert [a["key"] for a in body["activities"]] == [a.key for a in _native_runtime().activities]
    assert all(a["last_answered"] is None for a in body["activities"])


def test_the_newest_answered_call_with_its_model_and_build(
    app: FastAPI, owner: TestClient, world: Any
) -> None:
    with create_session_factory(app.state.engine)() as session:
        session.add_all(
            [
                _row(world, 1, ANALYSIS, T0, "SUCCEEDED"),
                _row(world, 2, ANALYSIS, T0 + timedelta(hours=1), "SUCCEEDED", served="eu.served"),
                _row(world, 3, ANALYSIS, T0 + timedelta(hours=2), "FAILED"),
                _row(
                    world,
                    4,
                    LEAD_AGENT_ID,
                    T0,
                    "SUCCEEDED",
                    capability=ModelCapability.STUDY_LEAD.value,
                    build="unknown-build",
                ),
            ]
        )
        session.commit()
    body = owner.get(API).json()
    by_key = {a["key"]: a["last_answered"] for a in body["activities"]}
    assert by_key["research_analysis"] == {
        "at": "2026-10-25T13:00:00Z",
        "model": "eu.served",
        "build": "0123abc",
    }
    assert by_key["study_lead"] == {
        "at": "2026-10-25T12:00:00Z",
        "model": "eu.asked",
        "build": None,
    }
    assert by_key["respondent_fieldwork"] is None
    text = owner.get(API).text
    for named in (world.client_id(), world.study_id(), "USR-1", "0.02"):
        assert named not in text


def test_a_researcher_is_refused(researcher: TestClient) -> None:
    refused = researcher.get(API)
    assert refused.status_code == 403 and refused.json()["code"] == "insufficient_role"
