"""The analysis runner: one module, a bounded repair loop, and blocking that cannot be softened."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from aia_core.application.analysis import (
    MAX_REPAIRS,
    AnalysisInputs,
    GenerationTurn,
    ModuleOutcome,
    ModuleOutcomeKind,
    input_fingerprint,
    run_analysis_module,
    run_pending_modules,
)
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.evidence import (
    METHOD_STATUS_HOLDOUT_VALIDATED,
    METHOD_STATUS_PENDING,
    ClaimSurface,
    EvidenceTable,
    ValidationState,
    ValidationStatus,
    ViolationCode,
)

SYSTEM_FP = "a" * 64
QUESTIONS = ("Jaký je zájem o nabídku?",)


class ScriptedGenerator:
    """A test double at the generator protocol: returns scripted drafts, records turns."""

    def __init__(self, drafts: list[object]) -> None:
        self._drafts: Iterator[object] = iter(drafts)
        self.turns: list[GenerationTurn] = []

    def generate(self, turn: GenerationTurn) -> object:
        self.turns.append(turn)
        return next(self._drafts)


class FailingGenerator:
    def generate(self, turn: GenerationTurn) -> object:
        raise ConnectionError("provider unavailable")


def good(module: str = "executive") -> dict[str, Any]:
    return {
        "module": module,
        "summary": "Zájem projevuje 42,5 % populace.",
        "key_findings": [{"text": "Zájem má 42,5 %.", "claim_ids": ["c1"]}],
        "numeric_claims": [
            {"claim_id": "c1", "evidence_ref": "E1", "metric": "top2box_pct", "value": 42.5,
             "unit": "%"}
        ],
    }  # fmt: skip


def bad(module: str = "executive") -> dict[str, Any]:
    return {**good(module), "summary": "Zájem projevuje 55 % populace."}


@pytest.fixture
def inputs(field_book: Any, joint_status: Any, evidence_row: Any) -> AnalysisInputs:
    return AnalysisInputs(
        table=EvidenceTable.build([evidence_row("E1")]),
        book=field_book,
        joint_status=joint_status,
        surface=ClaimSurface.CLIENT_FACING,
        research_questions=QUESTIONS,
        language="cs",
        system_fingerprint=SYSTEM_FP,
    )


def test_a_passing_first_draft_completes(inputs: AnalysisInputs) -> None:
    generator = ScriptedGenerator([good()])
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, generator)
    assert outcome.kind is ModuleOutcomeKind.COMPLETED and outcome.attempts == 1
    assert outcome.result is not None
    assert [c.claim_id for c in outcome.result.claims] == ["c1"]
    assert outcome.result.method_status == METHOD_STATUS_PENDING
    assert outcome.input_fingerprint == input_fingerprint(AnalysisModuleId.EXECUTIVE, inputs)
    assert generator.turns[0].repair is None
    assert "42.5" in str(generator.turns[0].payload["evidence"])


def test_a_failed_gate_triggers_a_repair_listing_the_violations(inputs: AnalysisInputs) -> None:
    generator = ScriptedGenerator([bad(), good()])
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, generator)
    assert outcome.kind is ModuleOutcomeKind.COMPLETED and outcome.attempts == 2
    repair = generator.turns[1]
    assert repair.repair is not None and "UNCITED_NUMBER" in repair.repair
    assert repair.previous == bad()


def test_two_repairs_then_blocked_with_every_violation(inputs: AnalysisInputs) -> None:
    generator = ScriptedGenerator([bad(), bad(), bad(), good()])
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, generator)
    assert outcome.kind is ModuleOutcomeKind.BLOCKED
    assert outcome.attempts == 1 + MAX_REPAIRS == 3
    assert len(generator.turns) == 3
    assert outcome.result is None
    assert {v.code for v in outcome.violations} == {ViolationCode.UNCITED_NUMBER}


def test_zero_repairs_blocks_on_the_first_failure(inputs: AnalysisInputs) -> None:
    generator = ScriptedGenerator([bad(), good()])
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, generator, max_repairs=0)
    assert outcome.kind is ModuleOutcomeKind.BLOCKED and len(generator.turns) == 1


@pytest.mark.parametrize("repairs", [-1, 3])
def test_repair_budget_is_bounded(inputs: AnalysisInputs, repairs: int) -> None:
    with pytest.raises(ValueError, match="max_repairs"):
        run_analysis_module(
            AnalysisModuleId.EXECUTIVE, inputs, ScriptedGenerator([]), max_repairs=repairs
        )


def test_garbage_from_the_model_is_repaired_or_blocked(inputs: AnalysisInputs) -> None:
    generator = ScriptedGenerator(["not json", ["a list"], None])
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, generator)
    assert outcome.kind is ModuleOutcomeKind.BLOCKED
    assert {v.code for v in outcome.violations} == {ViolationCode.SCHEMA_INVALID}


def test_degraded_certificate_blocks_before_any_model_call(
    inputs: AnalysisInputs, degraded_joint_status: Any
) -> None:
    generator = ScriptedGenerator([good()])
    degraded = AnalysisInputs(**{**_fields(inputs), "joint_status": degraded_joint_status})
    outcome = run_analysis_module(AnalysisModuleId.EXECUTIVE, degraded, generator)
    assert outcome.kind is ModuleOutcomeKind.BLOCKED and outcome.attempts == 0
    assert generator.turns == []
    assert outcome.violations[0].code is ViolationCode.JOINT_CERTIFICATE_DEGRADED


def test_provider_failure_propagates_to_the_workflow(inputs: AnalysisInputs) -> None:
    with pytest.raises(ConnectionError):
        run_analysis_module(AnalysisModuleId.EXECUTIVE, inputs, FailingGenerator())


def test_method_status_comes_from_the_validation_in_force(inputs: AnalysisInputs) -> None:
    validated = AnalysisInputs(
        **{
            **_fields(inputs),
            "validation": ValidationState(ValidationStatus.HOLDOUT_VALIDATED, SYSTEM_FP),
        }
    )
    outcome = run_analysis_module(
        AnalysisModuleId.EXECUTIVE, validated, ScriptedGenerator([good()])
    )
    assert outcome.result is not None
    assert outcome.result.method_status == METHOD_STATUS_HOLDOUT_VALIDATED


def test_outcome_shape_is_enforced() -> None:
    with pytest.raises(ValueError):
        ModuleOutcome(ModuleOutcomeKind.COMPLETED, AnalysisModuleId.EXECUTIVE, "f", 1)
    with pytest.raises(ValueError):
        ModuleOutcome(ModuleOutcomeKind.BLOCKED, AnalysisModuleId.EXECUTIVE, "f", 1)


def test_pending_modules_resume_where_the_last_run_stopped(inputs: AnalysisInputs) -> None:
    ids = list(AnalysisModuleId)
    completed = {m: input_fingerprint(m, inputs) for m in ids[:5]}
    generator = ScriptedGenerator([good(m.value) for m in ids[5:]])
    outcomes = run_pending_modules(inputs, generator, completed)
    assert [o.module_id for o in outcomes] == ids[5:]
    assert all(o.kind is ModuleOutcomeKind.COMPLETED for o in outcomes)


def test_a_blocked_module_does_not_stop_the_next(inputs: AnalysisInputs) -> None:
    ids = list(AnalysisModuleId)
    completed = {m: input_fingerprint(m, inputs) for m in ids[:6]}
    drafts: list[object] = [bad("implications")] * 3 + [good("limitations")]
    outcomes = run_pending_modules(inputs, ScriptedGenerator(drafts), completed)
    assert [o.kind for o in outcomes] == [ModuleOutcomeKind.BLOCKED, ModuleOutcomeKind.COMPLETED]


def _fields(inputs: AnalysisInputs) -> dict[str, Any]:
    return {name: getattr(inputs, name) for name in AnalysisInputs.__dataclass_fields__}


# --- review findings: what the resume fingerprint must see ------------------------------


def test_a_revoked_certificate_permission_reruns_completed_modules(
    inputs: AnalysisInputs, certificate_bytes: Any
) -> None:
    """Same panel, narrower certificate: a result the new one would refuse is not reused."""
    from aia_core.domain.evidence import load_joint_status

    narrower = load_joint_status(
        certificate_bytes(matched_block_outputs_allowed=False, matched_blocks=[]),
        measured_panel_sha256=inputs.joint_status.panel_sha256,
    )
    assert narrower.certified and narrower.panel_sha256 == inputs.joint_status.panel_sha256
    changed = AnalysisInputs(**{**_fields(inputs), "joint_status": narrower})
    for module_id in AnalysisModuleId:
        assert input_fingerprint(module_id, changed) != input_fingerprint(module_id, inputs)


def test_a_changed_validation_or_external_context_reruns_completed_modules(
    inputs: AnalysisInputs,
) -> None:
    validated = AnalysisInputs(
        **{
            **_fields(inputs),
            "validation": ValidationState(ValidationStatus.HOLDOUT_VALIDATED, SYSTEM_FP),
        }
    )
    new_context = AnalysisInputs(**{**_fields(inputs), "external_context": ("nová zpráva",)})
    new_system = AnalysisInputs(**{**_fields(inputs), "system_fingerprint": "c" * 64})
    module_id = AnalysisModuleId.EXECUTIVE
    base = input_fingerprint(module_id, inputs)
    assert input_fingerprint(module_id, validated) != base
    assert input_fingerprint(module_id, new_context) != base
    assert input_fingerprint(module_id, new_system) != base


def test_revoking_a_holdout_does_not_reuse_the_validated_stamp(inputs: AnalysisInputs) -> None:
    validated = AnalysisInputs(
        **{
            **_fields(inputs),
            "validation": ValidationState(ValidationStatus.HOLDOUT_VALIDATED, SYSTEM_FP),
        }
    )
    ids = list(AnalysisModuleId)
    completed = {m: input_fingerprint(m, validated) for m in ids}
    answers = [{"question": QUESTIONS[0], "answer": "Zájem má 42,5 %.", "claim_ids": ["c1"]}]
    drafts: list[object] = [
        {**good(m.value), "research_question_answers": answers}
        if m is AnalysisModuleId.RESEARCH_QUESTIONS
        else good(m.value)
        for m in ids
    ]
    generator = ScriptedGenerator(drafts)
    outcomes = run_pending_modules(inputs, generator, completed)
    assert [o.module_id for o in outcomes] == ids
    assert all(o.result is not None and o.result.method_status == METHOD_STATUS_PENDING
               for o in outcomes)  # fmt: skip
