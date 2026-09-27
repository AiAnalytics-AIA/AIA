"""The analysis harness: one turn, one request, one call; material classified, never assumed."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aia_core.domain.ai_contracts import validate_structured_output
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.analysis import (
    PROMPT_TEMPLATE_VERSION,
    AnalysisDraft,
    AnalysisModuleId,
    module_spec,
    prompt_template_sha256,
    system_prompt,
)
from aia_core.domain.analysis.harness import (
    ANALYSIS_HARNESS_VERSION,
    InvalidStructuredOutput,
    analysis_agent,
    analysis_request,
    classify_analysis_material,
    harness_frame,
    harness_labels,
    harness_sha256,
    request_sha256,
)
from aia_core.domain.evidence import ClaimSurface
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.licence import DataLineage, LicenceDenied
from aia_core.domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET, recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone

PAYLOAD = {"module": "executive", "evidence": [{"evidence_ref": "q1.mean", "value": 3.1}]}
LINEAGE = DataLineage.of(SYNTHETIC_FIXTURE_DATASET)
FICTIONAL = DataOrigin.SYNTHETIC_AI_FICTIONAL


def request(**overrides: Any) -> Any:
    args: dict[str, Any] = {
        "system": system_prompt(module_spec(AnalysisModuleId.EXECUTIVE), language="cs"),
        "payload": PAYLOAD,
        "frame": harness_frame(origin=FICTIONAL, surface=ClaimSurface.INTERNAL),
        "repair": None,
        "previous": None,
        "policy_version": "test-v1",
        "data_class": DataClass.CLASS_C_INTERNAL,
        "lineage": LINEAGE,
        "max_output_tokens": 4096,
    }
    args.update(overrides)
    return analysis_request(**args)


def test_one_agent_one_capability_and_no_schema_repair_inside_a_turn() -> None:
    agent = analysis_agent(max_output_tokens=4096)
    assert agent.capability is ModelCapability.RESEARCH_REASONING
    assert agent.output_contract is AnalysisDraft
    assert agent.schema_repair_attempts == 0
    assert agent.allowed_tools == frozenset()
    assert agent.prompt_version == PROMPT_TEMPLATE_VERSION


def test_the_first_turn_sends_the_evidence_and_the_framed_prompt() -> None:
    first = request()
    assert [m.role for m in first.messages] == ["user"]
    assert json.loads(first.messages[0].content) == PAYLOAD
    assert first.system.startswith("You are a senior research director")
    assert "simulated (SYNTHETIC_AI_FICTIONAL)" in first.system
    assert "INTERNAL surface" in first.system
    assert first.data_classification is DataClass.CLASS_C_INTERNAL
    assert first.data_lineage == LINEAGE
    assert first.output_token_limit == 4096
    assert first.fallback_policy.alternates == ()


def test_a_repair_turn_shows_the_last_draft_and_the_violations() -> None:
    previous = {"module": "executive", "summary": "Zájem má 55 %."}
    repair = request(
        repair="Fix every problem below.\n- UNCITED_NUMBER: summary", previous=previous
    )
    assert [m.role for m in repair.messages] == ["user", "assistant", "user"]
    assert json.loads(repair.messages[1].content) == previous
    assert repair.messages[2].content.startswith("Fix every problem below.")
    assert "output schema check" not in repair.messages[2].content


def test_a_schema_failure_reaches_the_next_turn_as_its_violations() -> None:
    failed = InvalidStructuredOutput(tuple(f"field_{i}: required" for i in range(23)))
    repair = request(repair="Fix every problem below.", previous=failed)
    assert repair.messages[1].content.startswith("(no draft")
    text = repair.messages[2].content
    assert "output schema check" in text and "field_0: required" in text
    assert "field_19: required" in text and "field_20" not in text
    assert "and 3 more" in text


def test_the_contract_is_closed_and_strict() -> None:
    contract = analysis_agent(max_output_tokens=10).output_contract
    assert contract is not None
    ok = validate_structured_output(
        contract,
        structured={"module": "executive", "summary": "Shrnutí bez čísel."},
        text="",
    )
    assert ok.ok
    invented = validate_structured_output(
        contract,
        structured={"module": "executive", "summary": "s", "method_status": "validated"},
        text="",
    )
    assert not invented.ok and any("method_status" in v for v in invented.violations)


@pytest.mark.parametrize(
    ("fictional_client", "origin", "fictional_respondents", "expected"),
    [
        (True, DataOrigin.SYNTHETIC_AI_FICTIONAL, True, DataClass.CLASS_C_INTERNAL),
        (True, DataOrigin.SYNTHETIC_FIXTURE, True, DataClass.CLASS_C_INTERNAL),
        (False, DataOrigin.SYNTHETIC_AI_FICTIONAL, True, DataClass.CLASS_A_CLIENT_CONFIDENTIAL),
        (True, DataOrigin.SYNTHETIC_AI_FICTIONAL, False, DataClass.CLASS_A_CLIENT_CONFIDENTIAL),
        (True, None, True, DataClass.CLASS_A_CLIENT_CONFIDENTIAL),
    ],
)
def test_class_c_only_when_nothing_in_the_request_is_a_clients(
    fictional_client: bool,
    origin: DataOrigin | None,
    fictional_respondents: bool,
    expected: DataClass,
) -> None:
    assert (
        classify_analysis_material(
            client_declared_fictional=fictional_client,
            origin=origin,
            respondents_fictional=fictional_respondents,
        )
        is expected
    )


def test_labels_say_what_every_reader_is_looking_at() -> None:
    assert harness_labels(origin=FICTIONAL, surface=ClaimSurface.INTERNAL) == {
        "surface": "INTERNAL",
        "data_origin": "SYNTHETIC_AI_FICTIONAL",
        "simulated_respondents": True,
        "internal_only": True,
    }
    assert "CLIENT_FACING" in harness_frame(origin=FICTIONAL, surface=ClaimSurface.CLIENT_FACING)


def test_the_harness_has_its_own_identity_beside_the_domain_prompt() -> None:
    assert harness_sha256() == harness_sha256()
    assert len(harness_sha256()) == 64
    assert harness_sha256() != prompt_template_sha256()
    assert ANALYSIS_HARNESS_VERSION == "aia-analysis-harness-1"


def test_an_undeclared_lineage_is_sent_as_undeclared_for_the_licence_gate_to_refuse() -> None:
    """No default lineage: a dataset that recorded none must not become ``none()`` here."""
    undeclared = request(lineage=None)
    assert undeclared.data_lineage is None
    route = ProviderRoute(
        route_id="bedrock-eu-primary",
        provider=Provider.AWS_BEDROCK.value,
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        retention_days=None,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )
    with pytest.raises(LicenceDenied) as denied:
        recorded_policy().authorise(lineage=undeclared.data_lineage, route=route)
    assert denied.value.reason == "lineage_undeclared"
    assert request_sha256(undeclared) != request_sha256(request())


def test_a_request_is_identified_by_what_it_sends() -> None:
    base = request_sha256(request())
    assert base == request_sha256(request())
    variants = {
        request_sha256(request(payload={**PAYLOAD, "module": "objects"})),
        request_sha256(request(data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL)),
        request_sha256(request(lineage=DataLineage.of("other"))),
        request_sha256(request(max_output_tokens=2048)),
        request_sha256(request(repair="Fix.", previous={"module": "executive"})),
        request_sha256(request(frame="other frame")),
    }
    assert base not in variants and len(variants) == 6
    assert request_sha256(request(policy_version="other")) == base
