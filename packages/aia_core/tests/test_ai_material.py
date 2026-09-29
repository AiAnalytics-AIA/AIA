"""Classifications describe exact material, never the containing client."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_material import (
    MaterialApproval,
    classify_material,
    material_sha256,
    most_restrictive_material,
)
from aia_core.domain.research_agents import ResearchAction, agent_request, context_snapshot
from aia_core.domain.residency import DataClass

DESIGN: dict[str, Any] = {
    "title": "Generated fictional concept",
    "briefing": {"text": "Generated fictional brief", "attachments": []},
    "sections": [],
}


def approval(value: Any, data_class: DataClass = DataClass.CLASS_C_INTERNAL) -> MaterialApproval:
    return MaterialApproval(
        sha256=material_sha256(value),
        data_class=data_class,
        provenance="generated wholly within this test",
    )


def request(design: dict[str, Any], *, instruction: str = "") -> Any:
    return agent_request(
        ResearchAction.ANALYZE,
        context_snapshot(design, []),
        instruction=instruction,
        policy_version="test",
        max_output_tokens=1024,
        material_approvals=(approval(DESIGN),),
    )


def test_generated_fixture_is_classified_by_exact_material() -> None:
    assert request(DESIGN).data_classification is DataClass.CLASS_C_INTERNAL
    assert classify_material(DESIGN, ()).data_class is None
    assert material_sha256(dict(reversed(list(DESIGN.items())))) == material_sha256(DESIGN)


@pytest.mark.parametrize(
    "briefing",
    [
        {"text": "New pasted text with no provenance", "attachments": []},
        {
            "text": "Generated fictional brief",
            "attachments": [{"kind": "file", "context_excerpt": "Unclassified upload"}],
        },
        {"text": "Generated fictional brief", "attachments": [], "client_text": "Confidential"},
    ],
)
def test_changed_upload_or_pasted_input_has_no_classification(briefing: dict[str, Any]) -> None:
    assert request({**DESIGN, "briefing": briefing}).data_classification is None


def test_new_instruction_does_not_inherit_the_design_class() -> None:
    assert request(DESIGN, instruction="New client details").data_classification is None


def test_knowledge_cannot_be_downgraded_by_a_classified_synthetic_design() -> None:
    snapshot = context_snapshot(DESIGN, [])
    snapshot["knowledge"] = [{"kind": "ENTITY", "title": "Client", "summary": "Private"}]
    result = agent_request(
        ResearchAction.ANALYZE,
        snapshot,
        instruction="",
        policy_version="test",
        max_output_tokens=1024,
        material_approvals=(approval(DESIGN),),
    )
    assert result.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL


def test_most_restrictive_material_includes_unknown_and_client_classes() -> None:
    a, b, c = DataClass
    assert most_restrictive_material([c, b]) is b
    assert most_restrictive_material([a, c]) is a
    assert most_restrictive_material([a, None]) is None
    assert most_restrictive_material([]) is None


def test_approval_needs_a_digest_and_source_and_is_unambiguous() -> None:
    with pytest.raises(ValidationError):
        MaterialApproval(sha256="client-id", data_class=DataClass.CLASS_C_INTERNAL, provenance="")
    with pytest.raises(ValueError, match="duplicate"):
        classify_material(DESIGN, (approval(DESIGN), approval(DESIGN)))
