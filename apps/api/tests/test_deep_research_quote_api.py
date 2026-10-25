"""``POST …/deep-research/quote``: what a Deep Research start would cost and answer, read-only.

Plan ``deep-research-web-search.md`` chunk 55 (DRL-0). The quote freezes the spec as the
start does and prices it by the start's own admission, so its ceiling is the one the start
asks to confirm; a study with no confirmation threshold still gets a ceiling (F-DRL-2);
nothing is reserved, recorded or started; the route is study-scoped (404 outside the study);
and it answers with ``AIA_DEEP_RESEARCH_ENABLED`` off, saying a run would park.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.deep_research.budgets import CallKind
from aia_core.domain.deep_research.settings import effective
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    BudgetReservationRow,
    StepRunRow,
    WorkflowRunRow,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from aia_api.config import Settings

API = "/api/v1"
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}
#: As ``test_deep_research_spend_api.py``: $3 / $15 per MTok, a 200,000-token window.
ROUTE = {
    "bedrock_input_usd_per_mtok": 3.0,
    "bedrock_output_usd_per_mtok": 15.0,
    "bedrock_context_window_tokens": 200_000,
    "ai_research_max_output_tokens": 8_192,
}


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(update=ROUTE)


def _study(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}"


def _revision(c: TestClient, world: Any) -> str:
    made = world.design(c, DESIGN, source_stage="brief")
    assert made.status_code == 201, made.text
    return str(made.json()["revision_id"])


def _quote(c: TestClient, world: Any, revision: str, study: str = "primary", **body: Any) -> Any:
    return c.post(
        f"{_study(world, study)}/deep-research/quote",
        json={
            "purpose": "DESIGN_RESEARCH",
            "design_revision_id": revision,
            "preset_name": "STANDARD",
            **body,
        },
    )


def _start(c: TestClient, world: Any, revision: str, **body: Any) -> Any:
    return c.post(
        f"{_study(world)}/deep-research/runs",
        json={"design_revision_id": revision, "preset_name": "STANDARD", **body},
    )


def _counts(app: FastAPI) -> tuple[int, ...]:
    with create_session_factory(app.state.engine)() as session:
        return tuple(
            int(session.scalar(select(func.count()).select_from(t)) or 0)
            for t in (WorkflowRunRow, StepRunRow, ApprovalDecisionRow, BudgetReservationRow)
        )


def test_a_study_with_no_threshold_gets_a_ceiling_and_the_start_stores_it(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    quoted = _quote(researcher, world, revision)
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    assert body["threshold_usd"] is None
    assert body["ceiling_usd"] is not None and body["ceiling_usd"] > 0
    assert body["start_verdict"] == "start"
    assert body["ceiling_mode"] == "planned"
    assert body["paid_routes"] == [] and body["live_settings_missing"] == []
    assert set(body["usd_by_kind"]) == {k.value for k in CallKind}
    assert body["budget"] is not None and body["budget"]["budget_usd"] >= 0
    assert len(body["settings_digest"]) == 64
    started = _start(researcher, world, revision)
    assert started.status_code == 201, started.text
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, started.json()["run_id"])
        assert row is not None
        meta = row.metadata_json
    assert meta["cost_ceiling_usd"] == pytest.approx(body["ceiling_usd"])


def test_a_quote_writes_nothing_and_agrees_with_the_start_under_a_threshold(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    assert (
        researcher.put(f"{_study(world)}/spend-confirm", json={"limit_usd": 0.01}).status_code
        == 200
    )
    before = _counts(app)
    quoted = _quote(researcher, world, revision)
    assert quoted.status_code == 200, quoted.text
    assert _counts(app) == before
    assert quoted.json()["start_verdict"] == "confirm"
    assert quoted.json()["threshold_usd"] == 0.01
    asked = _start(researcher, world, revision)
    assert asked.status_code == 409
    assert asked.json()["details"]["ceiling_usd"] == quoted.json()["ceiling_usd"]
    started = _start(researcher, world, revision, confirm_cost_usd=quoted.json()["ceiling_usd"])
    assert started.status_code == 201, started.text
    again = _quote(researcher, world, revision)
    assert again.json()["start_verdict"] == "exists"
    assert again.json()["existing_run_id"] == started.json()["run_id"]


def test_the_route_is_scoped_to_the_study(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    for member in (researcher, other_client_lead):
        foreign = _quote(member, world, revision, study="other_client")
        assert foreign.status_code == 404, foreign.text
    unknown = _quote(researcher, world, "REV-0000000000000000")
    assert unknown.status_code == 404


def test_a_malformed_quote_is_422(researcher: TestClient, world: Any) -> None:
    revision = _revision(researcher, world)
    for body in (
        {"confirm_cost_usd": 1.0},  # a quote confirms nothing
        {"purpose": "INTERPRETATION_RESEARCH"},  # interpretation names a target, not a revision
        {"preset_name": "SHALLOW"},
    ):
        assert _quote(researcher, world, revision, **body).status_code == 422


def test_the_quote_answers_with_deep_research_off_and_says_a_run_would_park(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    unknown = _quote(researcher, world, revision).json()["runtime"]
    assert unknown == {
        "switch": "AIA_DEEP_RESEARCH_ENABLED",
        "enabled": None,
        "runs_would_park": None,
        "park_reason": None,
    }
    app.state.settings = app.state.settings.model_copy(update={"deep_research_enabled": False})
    off = _quote(researcher, world, revision)
    assert off.status_code == 200 and off.json()["ceiling_usd"] is not None
    assert off.json()["runtime"]["runs_would_park"] is True
    assert off.json()["runtime"]["park_reason"] == "deep_research_unconfigured"
    app.state.settings = app.state.settings.model_copy(update={"deep_research_enabled": True})
    on = _quote(researcher, world, revision).json()["runtime"]
    assert (on["enabled"], on["runs_would_park"], on["park_reason"]) == (True, False, None)


def test_a_priced_route_names_what_live_still_needs(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    app.state.settings = app.state.settings.model_copy(
        update={"deep_research_web_search": "brave", "deep_research_brave_usd_per_1000": 5.0}
    )
    quoted = _quote(researcher, world, revision).json()
    assert quoted["paid_routes"] == ["search"]
    assert quoted["live_settings_missing"] == list(effective({}).missing_for_live())
    assert quoted["start_verdict"] == "live_settings_unapproved"
    refused = _start(researcher, world, revision)
    assert refused.status_code == 409
    assert refused.json()["details"]["missing"] == quoted["live_settings_missing"]


def test_an_unpriced_route_is_null_never_zero(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    app.state.settings = app.state.settings.model_copy(update={"deep_research_web_search": "brave"})
    quoted = _quote(researcher, world, revision).json()
    assert quoted["ceiling_usd"] is None
    assert quoted["ceiling_unknown"] == "deep_research_price_missing"
    assert quoted["unknown_kinds"] == ["search"]
    assert quoted["usd_by_kind"]["search"] is None


def test_an_adaptive_route_model_is_priced_without_the_thinking_budget() -> None:
    """The worker sends an adaptive route model no budget (sonnet-5-5-switch), so the ceiling
    the API quotes leaves it out too; a budgeted model keeps it, as before."""
    budget = {"deep_research_thinking_budget_tokens": 2_048}
    assert Settings(**ROUTE, **budget).deep_research_pricing().thinking_budget_tokens == 2_048
    assert (
        Settings(**ROUTE, **budget, bedrock_thinking="budget")
        .deep_research_pricing()
        .thinking_budget_tokens
        == 2_048
    )
    adaptive = Settings(**ROUTE, **budget, bedrock_thinking="adaptive")
    assert adaptive.deep_research_pricing().thinking_budget_tokens is None
    # Read as the worker reads it: stripped, in any case.
    assert Settings(**ROUTE, bedrock_thinking=" Adaptive ").bedrock_thinking == "adaptive"  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bedrock_thinking"):
        Settings(**ROUTE, bedrock_thinking="enabled")  # type: ignore[arg-type]


def test_the_api_settings_name_every_pricing_key() -> None:
    """Each key the ceiling is priced from reaches the application layer's settings."""
    settings = Settings(
        **ROUTE,
        bedrock_cache_read_usd_per_mtok=0.3,
        bedrock_cache_write_usd_per_mtok=3.75,
        deep_research_thinking_budget_tokens=1_024,
        deep_research_web_search="brave",
        deep_research_brave_usd_per_1000=5.0,
        deep_research_common_crawl=True,
        deep_research_common_crawl_max_scan_bytes=1_000_000_000,
        deep_research_common_crawl_usd_per_tb_scanned=5.0,
        deep_research_common_crawl_min_billed_bytes=10_485_760,
        deep_research_common_crawl_billing_increment_bytes=1_048_576,
        deep_research_connectors="datastat",
        deep_research_agent_directed=True,
        deep_research_lead=True,
        deep_research_enabled=True,
    )
    pricing = settings.deep_research_pricing()
    assert (pricing.input_usd_per_mtok, pricing.cache_write_usd_per_mtok) == (3.0, 3.75)
    assert pricing.thinking_budget_tokens == 1_024
    assert pricing.search_route() == "brave" and pricing.brave_usd_per_1000 == 5.0
    assert pricing.common_crawl_billing_increment_bytes == 1_048_576
    assert pricing.connectors == "datastat" and pricing.engine_lead and pricing.enabled
    assert set(pricing.__dataclass_fields__) == {
        "input_usd_per_mtok",
        "output_usd_per_mtok",
        "cache_read_usd_per_mtok",
        "cache_write_usd_per_mtok",
        "context_window_tokens",
        "max_output_tokens",
        "thinking_budget_tokens",
        "web_search",
        "wikipedia_enabled",
        "brave_usd_per_1000",
        "common_crawl",
        "common_crawl_max_scan_bytes",
        "common_crawl_usd_per_tb_scanned",
        "common_crawl_min_billed_bytes",
        "common_crawl_billing_increment_bytes",
        "connectors",
        "agent_directed",
        "engine_lead",
        "enabled",
    }


def test_a_closed_study_is_refused_before_anything_is_frozen(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    closed = researcher.put(f"{_study(world)}/status", json={"status": "ARCHIVED"})
    assert closed.status_code == 200, closed.text
    before = _counts(app)
    refused = _quote(researcher, world, revision)
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "study_closed"
    assert _counts(app) == before
