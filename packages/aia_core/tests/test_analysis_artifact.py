"""The analysis artifact contract, its identities, and the graph a research run adds."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_ARTIFACT_CONTRACT,
    HarnessSummary,
    ModuleSources,
    module_reuse_fingerprint,
    parse_module_artifact,
    parse_turn_artifact,
    turn_fingerprint,
)
from aia_core.domain.analysis.steps import (
    ANALYSIS_STEP_KIND,
    analysis_node_key,
    analysis_step_definitions,
    analysis_step_inputs,
    module_of_node,
)
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.workflow import validate_dag
from aia_core.domain.workflow_templates import RESEARCH, steps_for_workflow

SHA = "a" * 64
DRAFT = {"module": "executive", "summary": "Shrnutí bez čísel.", "numeric_claims": []}


def call(turn: int, **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "turn": turn,
        "request_sha256": SHA,
        "answer": "DRAFT",
        "turn_artifact_id": f"ART-{turn}",
        "replayed": False,
        "call_id": f"call-{turn}",
        "provider_request_id": f"req-{turn}",
        "model": "eu.test-v1:0",
        "route_id": "bedrock-eu-primary",
        "policy_version": "test-v1",
        "cost_usd": 0.01,
        "cost_basis": "METERED",
    }
    record.update(overrides)
    return record


def harness() -> dict[str, Any]:
    return {
        "harness_version": "aia-analysis-harness-1",
        "harness_sha256": SHA,
        "prompt_template_version": "analysis-module-v1",
        "prompt_template_sha256": SHA,
        "agent_id": "aia.analysis.module",
        "agent_version": "1",
        "capability": "RESEARCH_REASONING",
        "schema_fingerprint": "schema",
        "language": "cs",
        "max_repairs": 2,
        "max_calls": 3,
    }


def sources() -> dict[str, Any]:
    ref = {"artifact_id": "ART-x", "sha256": SHA}
    return {
        "design_revision_id": "REV-1",
        "specification": ref,
        "specification_fingerprint": SHA,
        "dataset": ref,
        "aggregate": ref,
    }


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "research_analysis_module",
        "contract_version": ANALYSIS_ARTIFACT_CONTRACT,
        "module_id": "executive",
        "ordinal": 1,
        "artifact_name": "ANALYSIS_01_EXECUTIVE",
        "outcome": "COMPLETED",
        "surface": "INTERNAL",
        "method_status": "synthetic/modelled research; external predictive certification pending",
        "input_fingerprint": SHA,
        "reuse_fingerprint": SHA,
        "research_questions": ["Co lidé ráno pijí?"],
        "draft": DRAFT,
        "violations": [],
        "attempts": 1,
        "sources": sources(),
        "evidence": {
            "adapter_version": "aia-native-evidence-1",
            "table_fingerprint": SHA,
            "rows": 10,
            "suppressed": ["q5.n"],
            "data_origin": "SYNTHETIC_FIXTURE",
        },
        "authority": {
            "field_policy_version": "aia-instrument-evidence-1",
            "field_policy_sha256": SHA,
            "joint_status_fingerprint": SHA,
            "joint_degradation": "MISSING",
            "validation": None,
            "system_fingerprint": SHA,
        },
        "harness": harness(),
        "calls": [call(1)],
        "labels": {
            "surface": "INTERNAL",
            "data_origin": "SYNTHETIC_FIXTURE",
            "simulated_respondents": True,
            "internal_only": True,
        },
        "produced_by": {
            "run_id": "RUN-1",
            "step_id": "STEP-1",
            "attempt_id": "ATT-1",
            "kind": "research_analysis",
        },
        "runtime_version": "abc",
    }
    base.update(overrides)
    return base


BLOCKED = {
    "outcome": "BLOCKED",
    "draft": None,
    "violations": [{"code": "UNCITED_NUMBER", "subject": "summary", "detail": "55 is not backed"}],
    "attempts": 3,
    "calls": [call(1), call(2), call(3, answer="SCHEMA_INVALID")],
}


def test_a_completed_and_a_blocked_outcome_parse() -> None:
    done = parse_module_artifact(payload())
    assert done.outcome == "COMPLETED" and done.draft is not None
    assert done.module_id is AnalysisModuleId.EXECUTIVE and done.surface is ClaimSurface.INTERNAL
    blocked = parse_module_artifact(payload(**BLOCKED))
    assert blocked.draft is None
    assert [v.violation().code.value for v in blocked.violations] == ["UNCITED_NUMBER"]
    preflight = parse_module_artifact(payload(**{**BLOCKED, "attempts": 0, "calls": []}))
    assert preflight.attempts == 0


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"contract_version": "aia-analysis-module-artifact-0"}, "contract_version"),
        ({"claims": []}, "Extra inputs"),
        ({"outcome": "BLOCKED"}, "blocked module"),
        ({"draft": None}, "completed module"),
        ({"violations": BLOCKED["violations"]}, "completed module"),
        ({"ordinal": 2}, "module 1"),
        ({"draft": {**DRAFT, "module": "objects"}}, "another module"),
        ({"draft": {**DRAFT, "invented": 1}}, "Extra inputs"),
        ({"attempts": 2}, "exactly one call record"),
        ({"calls": [call(2)]}, "exactly one call record"),
        ({"reuse_fingerprint": "short"}, "SHA-256"),
        ({"surface": "CLIENT_FACING"}, "labels disagree"),
        ({"outcome": "PUBLISHED"}, "outcome"),
    ],
)
def test_a_stored_outcome_that_breaks_the_contract_is_refused(
    overrides: dict[str, Any], match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        parse_module_artifact(payload(**overrides))


def test_more_turns_than_the_harness_allows_are_refused() -> None:
    with pytest.raises(ValidationError, match="more turns"):
        parse_module_artifact(
            payload(**{**BLOCKED, "attempts": 4, "calls": [call(i) for i in range(1, 5)]})
        )


def test_parsing_is_strict_json_semantics() -> None:
    bad = payload()
    bad["attempts"] = "1"
    with pytest.raises(ValidationError):
        parse_module_artifact(bad)
    nested = copy.deepcopy(payload())
    nested["calls"][0]["cost_usd"] = "0.01"
    with pytest.raises(ValidationError):
        parse_module_artifact(nested)


def turn(**overrides: Any) -> dict[str, Any]:
    base = {
        "kind": "research_analysis_turn",
        "contract_version": "aia-analysis-turn-1",
        "module_id": "executive",
        "turn": 1,
        "reuse_fingerprint": SHA,
        "request_sha256": SHA,
        "answer": "DRAFT",
        "draft": DRAFT,
        "schema_violations": [],
        "call_id": "c",
        "provider_request_id": "r",
        "model": "m",
        "route_id": "route",
        "policy_version": "p",
        "cost_usd": 0.0,
        "cost_basis": "METERED",
        "produced_by": payload()["produced_by"],
        "runtime_version": None,
    }
    base.update(overrides)
    return base


def test_a_turn_checkpoint_carries_its_answer_or_its_schema_failure() -> None:
    assert parse_turn_artifact(turn()).draft is not None
    failed = parse_turn_artifact(turn(answer="SCHEMA_INVALID", draft=None, schema_violations=["x"]))
    assert failed.schema_violations == ("x",)
    with pytest.raises(ValidationError, match="DRAFT turn"):
        parse_turn_artifact(turn(answer="SCHEMA_INVALID"))
    with pytest.raises(ValidationError, match="says what failed"):
        parse_turn_artifact(turn(answer="SCHEMA_INVALID", draft=None))


def test_the_reuse_key_moves_with_the_module_the_sources_and_the_harness() -> None:
    src = ModuleSources.model_validate(sources())
    har = HarnessSummary.model_validate(harness())
    base = module_reuse_fingerprint(module_fingerprint=SHA, sources=src, harness=har)
    other_src = ModuleSources.model_validate(
        {**sources(), "aggregate": {"artifact_id": "ART-x", "sha256": "b" * 64}}
    )
    variants = {
        module_reuse_fingerprint(module_fingerprint="b" * 64, sources=src, harness=har),
        module_reuse_fingerprint(module_fingerprint=SHA, sources=other_src, harness=har),
        module_reuse_fingerprint(
            module_fingerprint=SHA,
            sources=src,
            harness=HarnessSummary.model_validate({**harness(), "max_repairs": 1}),
        ),
    }
    assert base not in variants and len(variants) == 3
    renamed = ModuleSources.model_validate(
        {**sources(), "aggregate": {"artifact_id": "ART-renamed", "sha256": SHA}}
    )
    assert module_reuse_fingerprint(module_fingerprint=SHA, sources=renamed, harness=har) == base
    assert turn_fingerprint(reuse_fingerprint=base, turn=1, request_sha256=SHA) != turn_fingerprint(
        reuse_fingerprint=base, turn=2, request_sha256=SHA
    )


# --- the graph ------------------------------------------------------------------------------


def test_eight_nodes_each_depending_on_aggregate_alone() -> None:
    steps = analysis_step_definitions()
    assert [s.node_key for s in steps] == [analysis_node_key(m) for m in AnalysisModuleId]
    assert {s.kind for s in steps} == {ANALYSIS_STEP_KIND}
    assert {s.depends_on for s in steps} == {("aggregate",)}
    assert {s.stage_type for s in steps} == {"ANALYSIS"}
    assert all(not s.consumes_population for s in steps)
    assert steps[0].artifact_target == "research_analysis_executive"


def test_the_nodes_join_the_research_graph_as_a_valid_dag() -> None:
    graph = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH)
    validate_dag([*graph, *analysis_step_definitions()])


def test_node_keys_and_modules_round_trip() -> None:
    for module in AnalysisModuleId:
        assert module_of_node(analysis_node_key(module)) is module
    assert module_of_node("aggregate") is None
    assert module_of_node("analysis_unknown") is None


def test_step_inputs_name_the_module_and_the_surface() -> None:
    inputs = analysis_step_inputs(ClaimSurface.INTERNAL)
    assert inputs["analysis_objects"] == {
        "analysis_module": "objects",
        "analysis_surface": "INTERNAL",
    }
    assert len(inputs) == 8
