"""The eight analysis modules: identity, order, fingerprints, resume, prompts."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.analysis import (
    ANALYSIS_MODULES,
    PROMPT_TEMPLATE_VERSION,
    AnalysisModuleId,
    module_input_fingerprint,
    module_payload,
    module_spec,
    modules_to_run,
    prompt_template_sha256,
    repair_prompt,
    system_prompt,
)
from aia_core.domain.evidence import (
    EvidenceTable,
    SupportEvidence,
    Violation,
    ViolationCode,
    allowed_metric_spellings,
    assess_support,
)


def test_eight_modules_in_reference_order() -> None:
    assert [m.artifact_name for m in ANALYSIS_MODULES] == [
        "ANALYSIS_01_EXECUTIVE",
        "ANALYSIS_02_RESEARCH_QUESTIONS",
        "ANALYSIS_03_OBJECTS",
        "ANALYSIS_04_AUDIENCE",
        "ANALYSIS_05_SEGMENTS",
        "ANALYSIS_06_HYPOTHESES",
        "ANALYSIS_07_IMPLICATIONS",
        "ANALYSIS_08_LIMITATIONS",
    ]
    assert [m.module_id for m in ANALYSIS_MODULES] == list(AnalysisModuleId)


def test_only_the_research_questions_module_must_answer_every_question() -> None:
    assert [m.module_id for m in ANALYSIS_MODULES if m.answers_research_questions] == [
        AnalysisModuleId.RESEARCH_QUESTIONS
    ]


def test_module_spec_lookup() -> None:
    assert module_spec("segments").ordinal == 5
    with pytest.raises(ValueError):
        module_spec("appendix")


def _fp(**overrides: Any) -> str:
    args: dict[str, Any] = {
        "evidence_fingerprint": "e" * 64,
        "research_questions": ["Jaký je zájem?"],
        "field_dictionary_sha256": "d" * 64,
        "joint_certificate": "c" * 64,
        "prompt_template_sha256": prompt_template_sha256(),
        "surface": "CLIENT_FACING",
        "language": "cs",
    }
    module = overrides.pop("module", AnalysisModuleId.EXECUTIVE)
    args.update(overrides)
    return module_input_fingerprint(module, **args)


@pytest.mark.parametrize(
    "change",
    [
        {"evidence_fingerprint": "f" * 64},
        {"research_questions": ["Jiná otázka?"]},
        {"field_dictionary_sha256": "0" * 64},
        {"joint_certificate": "DEGRADED:MISSING"},
        {"prompt_template_sha256": "1" * 64},
        {"surface": "INTERNAL"},
        {"language": "en"},
        {"module": AnalysisModuleId.LIMITATIONS},
    ],
)
def test_fingerprint_moves_with_every_input(change: dict[str, Any]) -> None:
    assert _fp(**change) != _fp()


def test_resume_after_module_five_continues_at_six() -> None:
    current = {m.module_id: _fp(module=m.module_id) for m in ANALYSIS_MODULES}
    completed = {m.module_id: current[m.module_id] for m in ANALYSIS_MODULES[:5]}
    assert modules_to_run(current, completed) == (
        AnalysisModuleId.HYPOTHESES,
        AnalysisModuleId.IMPLICATIONS,
        AnalysisModuleId.LIMITATIONS,
    )


def test_changed_evidence_reruns_everything() -> None:
    old = {m.module_id: _fp(module=m.module_id) for m in ANALYSIS_MODULES}
    new = {
        m.module_id: _fp(module=m.module_id, evidence_fingerprint="9" * 64)
        for m in ANALYSIS_MODULES
    }
    assert modules_to_run(new, old) == tuple(AnalysisModuleId)
    assert modules_to_run(new, new) == ()


def test_resume_refuses_an_incomplete_fingerprint_set() -> None:
    with pytest.raises(ValueError, match="no input fingerprint"):
        modules_to_run({AnalysisModuleId.EXECUTIVE: "x"}, {})


# --- prompts ------------------------------------------------------------------------------


def test_system_prompt_states_the_allowed_set_from_the_enum() -> None:
    prompt = system_prompt(module_spec("executive"), language="cs")
    assert ", ".join(allowed_metric_spellings()) in prompt
    assert "pct:<exact answer> -> %" in prompt
    assert "External research is context only" in prompt
    assert '"executive"' in prompt


def test_repair_prompt_lists_every_violation() -> None:
    text = repair_prompt(
        [
            Violation(ViolationCode.VALUE_MISMATCH, "c1", "45 cited, row is 42.5"),
            Violation(ViolationCode.UNCITED_NUMBER, "summary", "2025 is not backed"),
        ]
    )
    assert "VALUE_MISMATCH: c1" in text and "UNCITED_NUMBER: summary" in text


def test_prompt_template_identity_is_stable_and_versioned() -> None:
    assert prompt_template_sha256() == prompt_template_sha256()
    assert len(prompt_template_sha256()) == 64
    assert PROMPT_TEMPLATE_VERSION == "analysis-module-v1"


def test_payload_offers_only_citable_rows_and_marks_context(evidence_row: Any) -> None:
    thin = assess_support(SupportEvidence(n=30, effective_n=20.0))
    table = EvidenceTable.build(
        [evidence_row("E2"), evidence_row("E1"), evidence_row("E3", support=thin)]
    )
    payload = module_payload(
        module_spec("objects"),
        table,
        research_questions=["Jaký je zájem?"],
        external_context=["Tisková zpráva konkurence"],
    )
    assert [r["evidence_ref"] for r in payload["evidence"]] == ["E1", "E2"]
    assert payload["suppressed_evidence"] == ["E3"]
    assert payload["external_context_not_evidence"] == ["Tisková zpráva konkurence"]
    assert payload["evidence"][0]["unit"] == "%"
