"""The worker contract (lead-orchestration LO9a): one row per worker, every field required.

The eight design workers are rows (``domain/research_agents.py`` ``WORKERS``), held to the fixture
``tests/fixtures/lead_workers/workers.json``; the job's request is built from its row, so the row
is the definition and not a description beside it. A row missing a field is refused at
registration, by name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.lead_workers import (
    FIELDS,
    CardKind,
    LeadWorkerSpec,
    ResultKind,
    WorkerRefused,
    WorkerRegistry,
)
from aia_core.domain.research_agents import (
    CONTRACTS,
    DESIGN_ACTIONS,
    WORKERS,
    ResearchAction,
    agent_request,
    context_snapshot,
    prompt_version_for,
    worker_for,
)
from aia_core.domain.residency import DataClass

REPO = Path(__file__).resolve().parents[3]
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/lead_workers/workers.json").read_text(encoding="utf-8")
)


def _row(**changes: Any) -> dict[str, Any]:
    return {**FIXTURE["workers"][0], **changes}


def _contracts() -> dict[str, type[BaseModel]]:
    return {c.__name__: c for c in CONTRACTS.values()}


def _validated(row: dict[str, Any]) -> dict[str, Any]:
    """A fixture row with its contract resolved to the class, as registration takes it."""
    resolved = _contracts().get(row.get("output_contract", ""), row.get("output_contract"))
    return {**row, "output_contract": resolved} if "output_contract" in row else row


def test_the_rows_are_the_fixture_s() -> None:
    assert FIXTURE["fields"] == list(FIELDS)
    assert WORKERS.fixture() == FIXTURE["workers"]
    assert list(WORKERS) == [a.value for a in ResearchAction]


@pytest.mark.parametrize("action", list(ResearchAction))
def test_each_design_worker_s_row_is_what_its_job_runs(action: ResearchAction) -> None:
    row = worker_for(action)
    assert row.output_contract is CONTRACTS[action]
    assert row.prompt_version == prompt_version_for(action)
    assert (row.card_kind is CardKind.PROPOSAL) == (action in DESIGN_ACTIONS)
    assert (row.result_kind is ResultKind.ADVICE) == (action not in DESIGN_ACTIONS)
    # The request is built from the row: capability, prompt and repairs are the row's.
    request = agent_request(
        action,
        context_snapshot({"title": "Fictional"}, []),
        instruction="",
        policy_version="test",
        max_output_tokens=4096,
    )
    assert request.agent.capability is row.capability
    assert request.agent.prompt_id == row.prompt_id == request.agent.agent_id
    assert request.agent.schema_repair_attempts == row.schema_repairs
    assert request.agent.output_contract is row.output_contract
    # The rules' worst case: approved knowledge is Class A, so a route must carry Class A.
    assert row.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert row.capability is (
        ModelCapability.CRITIC
        if action is ResearchAction.CRITIQUE
        else ModelCapability.RESEARCH_REASONING
    )


def test_the_worker_reads_the_switch_and_reservation_its_rows_name() -> None:
    source = (REPO / "apps/executors/src/aia_executors/ai_runtime.py").read_text(encoding="utf-8")
    for row in WORKERS.values():
        assert f'"{row.switch}"' in source and f'"{row.reservation_key}"' in source


@pytest.mark.parametrize("field", FIELDS)
def test_a_row_missing_any_field_is_refused_at_registration(field: str) -> None:
    row = _validated(_row(worker_id="new_worker", prompt_id="aia.research.new_worker"))
    del row[field]
    with pytest.raises(WorkerRefused) as refused:
        WorkerRegistry([row])
    assert refused.value.fields == (field,)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"worker_id": ""}, "worker_id"),
        ({"material_rules": []}, "material_rules"),
        ({"material_rules": ["rule:design", "rule:design"]}, "material_rules"),
        ({"material_rules": ["rule:invented"]}, "material_rules"),
        ({"capability": "SOME_MODEL"}, "capability"),
        ({"reservation_key": "AIA_AI_RESEARCH_PRICE"}, "reservation_key"),
        ({"switch": "AIA_AI_RESEARCH_AGENTS"}, "switch"),
        ({"schema_repairs": 3}, "schema_repairs"),
        ({"prompt_version": "latest"}, "prompt_version"),
        ({"prompt_id": "research.analyze"}, "prompt_id"),
        ({"cost_usd": 0.0}, "cost_usd"),
    ],
)
def test_a_row_of_the_wrong_shape_is_refused_by_name(changes: dict[str, Any], field: str) -> None:
    row = _validated(_row(worker_id="new_worker", prompt_id="aia.research.new_worker"))
    with pytest.raises(WorkerRefused) as refused:
        WorkerRegistry([{**row, **changes}])
    assert field in refused.value.fields


def test_an_open_contract_and_a_card_that_does_not_fit_its_result_are_refused() -> None:
    class Open(BaseModel):
        model_config = ConfigDict(extra="allow")

    base = _validated(_row(worker_id="new_worker", prompt_id="aia.research.new_worker"))
    with pytest.raises(WorkerRefused, match="closed contract"):
        WorkerRegistry([{**base, "output_contract": Open}])
    with pytest.raises(WorkerRefused, match="advice card"):
        WorkerRegistry([{**base, "card_kind": "advice"}])


def test_one_id_and_one_prompt_per_worker() -> None:
    registry = WorkerRegistry(WORKERS.values())
    first = next(iter(WORKERS.values()))
    with pytest.raises(WorkerRefused, match="registered already"):
        registry.register(first)
    with pytest.raises(WorkerRefused, match="another worker has this prompt"):
        registry.register(first.model_copy(update={"worker_id": "another_worker"}))
    assert len(registry) == len(WORKERS) == 8


def test_a_spec_has_no_defaults() -> None:
    assert all(f.is_required() for f in LeadWorkerSpec.model_fields.values())
