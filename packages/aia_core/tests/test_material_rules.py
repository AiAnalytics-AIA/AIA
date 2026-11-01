"""The owner's class rules (2026-10-19): a rule decides, an operator can only make it stricter."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.material_rules import (
    DESIGN_CLASS,
    OPERATOR_SOURCE,
    RULE_CLASSES,
    STUDY_CLASS,
    MaterialRule,
    classify_by_rule,
    rule_class,
    source_rule,
)
from aia_core.domain.prompts import PromptPin
from aia_core.domain.research_agents import (
    context_snapshot,
    design_classification,
    instruction_classification,
    prompt_class_source,
)
from aia_core.domain.residency import DataClass

A, B, C = (
    DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    DataClass.CLASS_B_DERIVED_CLIENT,
    DataClass.CLASS_C_INTERNAL,
)


def approval(value: Any, data_class: DataClass) -> MaterialApproval:
    return MaterialApproval(
        sha256=material_sha256(value), data_class=data_class, provenance="operator review"
    )


def test_every_rule_has_the_class_the_owner_decided() -> None:
    assert STUDY_CLASS is B and DESIGN_CLASS is B
    assert dict(RULE_CLASSES) == {
        MaterialRule.DESIGN: B,
        MaterialRule.STUDY_NAME: B,
        MaterialRule.LEAD_MESSAGE: B,
        MaterialRule.JOB_INSTRUCTION: B,
        MaterialRule.LEAD_FILES: C,
        MaterialRule.CLIENT_NOTE: A,
        MaterialRule.KNOWLEDGE: A,
        MaterialRule.CLIENT_SOURCE: A,
        MaterialRule.INTERNAL_DOCUMENT: C,
        MaterialRule.LEAD_HATCH: C,
    }
    assert all(rule.value.startswith("rule:") for rule in MaterialRule)
    with pytest.raises(TypeError):
        RULE_CLASSES[MaterialRule.DESIGN] = C  # type: ignore[index]


@pytest.mark.parametrize("rule", list(MaterialRule))
def test_a_rule_classifies_any_bytes_with_no_operator_step(rule: MaterialRule) -> None:
    ruled = classify_by_rule({"any": "edited text"}, rule, ())
    assert ruled.data_class is rule_class(rule)
    assert ruled.source == rule.value
    assert ruled.operator_class is None and ruled.operator_provenance is None
    assert ruled.sha256 == material_sha256({"any": "edited text"})


def test_an_operator_can_raise_a_rule_and_is_named_for_it() -> None:
    ruled = classify_by_rule("Acme", MaterialRule.DESIGN, (approval("Acme", A),))
    assert (ruled.data_class, ruled.source) == (A, OPERATOR_SOURCE)
    assert ruled.operator_provenance == "operator review"


@pytest.mark.parametrize(
    ("rule", "operator"),
    [
        (MaterialRule.DESIGN, C),
        (MaterialRule.LEAD_MESSAGE, C),
        (MaterialRule.CLIENT_SOURCE, B),
        (MaterialRule.CLIENT_SOURCE, C),
        (MaterialRule.KNOWLEDGE, C),
    ],
)
def test_an_operator_can_never_lower_a_rule(rule: MaterialRule, operator: DataClass) -> None:
    ruled = classify_by_rule("x", rule, (approval("x", operator),))
    assert ruled.data_class is rule_class(rule)
    assert ruled.source == rule.value and ruled.operator_class is operator


def test_an_operator_who_agrees_with_the_rule_leaves_the_rule_as_the_source() -> None:
    ruled = classify_by_rule("x", MaterialRule.DESIGN, (approval("x", B),))
    assert (ruled.data_class, ruled.source, ruled.operator_class) == (B, "rule:design", B)


def test_a_duplicate_operator_classification_is_still_refused() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        classify_by_rule("x", MaterialRule.DESIGN, (approval("x", A), approval("x", A)))


def test_a_client_source_is_class_a_unless_a_person_marked_it_internal() -> None:
    assert source_rule(internal=False) is MaterialRule.CLIENT_SOURCE
    assert rule_class(source_rule(internal=False)) is A
    assert source_rule(internal=True) is MaterialRule.INTERNAL_DOCUMENT
    assert rule_class(source_rule(internal=True)) is C


def test_a_jobs_design_and_instruction_are_classified_by_rule() -> None:
    snapshot = context_snapshot({"title": "Edited by a person"}, [])
    design = design_classification(snapshot, ())
    assert (design.data_class, design.source) == (B, "rule:design")
    assert instruction_classification("", ()) is None  # holds no material
    instruction = instruction_classification("Zaměř se na ceny", ())
    assert instruction is not None
    assert (instruction.data_class, instruction.source) == (B, "rule:job_instruction")


def test_a_prompts_class_source_names_who_answered_for_it() -> None:
    assert prompt_class_source(None, ()) == "code"
    baseline = PromptPin.of(prompt_id="p", version="v", origin="baseline", text="t")
    assert prompt_class_source(baseline, ()) == "code"
    declared = PromptPin.of(
        prompt_id="p",
        version="e1",
        origin="stored",
        text="t",
        declared_class="CLASS_C_INTERNAL",
        declared_by="USR-1",
    )
    undeclared = PromptPin.of(prompt_id="p", version="e1", origin="stored", text="t")
    operator = (approval("t", C),)
    assert prompt_class_source(declared, ()) == "declaration"
    assert prompt_class_source(undeclared, operator) == "operator"
    assert prompt_class_source(declared, operator) == "declaration+operator"
    assert prompt_class_source(undeclared, ()) == "unknown"  # neither: the class is unknown
