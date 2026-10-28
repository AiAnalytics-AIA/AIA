"""Settings → AI běh → Trasa modelu as the worker composed it, over HTTP (LO12b)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aia_core.domain.ai_route_reach import AiRouteReach, LeadComposition
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.deep_research_composition_repository import record_composition
from fastapi import FastAPI

from aia_api.config import Settings

URL = "/api/v1/settings/ai-route"


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"ai_route_preflight_enabled": True})


def _record(app: FastAPI, ai_route: AiRouteReach | None) -> None:
    with create_session_factory(app.state.engine)() as session:
        record_composition(
            session,
            worker="worker-1",
            build_sha="abc1234",
            composed_at=datetime.now(UTC),
            agent_directed=False,
            class_gates=None,
            routes=[],
            ai_route=ai_route,
        )
        session.commit()


def test_it_is_off_unless_its_switch_is_on(app: FastAPI, as_user: Any) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_route_preflight_enabled": False})
    response = as_user("researcher").get(URL)
    assert response.status_code == 404
    assert response.json()["code"] == "ai_route_preflight_off"


def test_nothing_recorded_presumes_nothing(app: FastAPI, as_user: Any) -> None:
    body = as_user("researcher").get(URL).json()
    assert (body["recorded"], body["classes"], body["lead_refusal"]) == (False, [], None)
    # A row a worker wrote before LO12b carries no route: unknown too.
    _record(app, None)
    assert as_user("researcher").get(URL).json()["recorded"] is False


def test_each_class_is_judged_by_the_gateways_checks(app: FastAPI, as_user: Any) -> None:
    route = ProviderRoute(
        route_id="bedrock-eu-primary",
        provider="aws_bedrock",
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        retention_days=None,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL, DataClass.CLASS_B_DERIVED_CLIENT}),
    )
    _record(
        app,
        AiRouteReach(
            True, route, "eu-central-1", DataClassGates.ENFORCE, LeadComposition.CONFIGURED
        ),
    )
    body = as_user("researcher").get(URL).json()
    assert body["recorded"] is True and body["worker"] == "worker-1"
    assert (body["route_id"], body["zone"], body["retention_days"]) == (
        "bedrock-eu-primary",
        "EU",
        None,
    )
    assert body["approved_for"] == ["B", "C"]
    assert body["classes"] == [
        {"data_class": "A", "refusal": "egress_route_not_approved_for_class", "advisory": False},
        # Retention unspecified: client material is refused even where the class is approved.
        {"data_class": "B", "refusal": "egress_retention_unspecified", "advisory": False},
        {"data_class": "C", "refusal": None, "advisory": False},
    ]
    assert body["lead_refusal"] == "egress_retention_unspecified"
