"""Run one analysis module: the model drafts, the evidence gate decides, and failure blocks.

Reference ``analysis_agent.py``: one durable module per turn; a failed evidence
gate triggers a repair prompt listing the violations, at most twice
(``_repairs < 2``); the call site passes ``allow_fallback=False``. Ported here
with the generator behind a protocol, so the rule holds whichever provider sits
behind it, and with two production additions, both fail closed:

* **Pre-flight before spend.** A client-facing module on a degraded
  ``CORE_JOINT_STATUS`` certificate cannot admit a single claim, so it is
  blocked before the model is called at all -- a paid call whose every output
  is certain to be refused is money spent on nothing.
* **Blocked is terminal for the attempt.** After the last repair the module is
  ``BLOCKED`` with every violation from the final draft. There is no partial
  result, no coverage threshold and no "publish with warnings".

Provider failures are not swallowed: an exception from the generator propagates
to the workflow, whose retry classification and waiting states decide what
happens next (``aia_core.domain.workflow``). Only a *draft* is judged here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final, Protocol

from ..domain.analysis import ANALYSIS_MODULES as _MODULES
from ..domain.analysis import (
    AnalysisModuleId,
    AnalysisModuleResult,
    check_analysis_draft,
    module_input_fingerprint,
    module_payload,
    module_spec,
    modules_to_run,
    prompt_template_sha256,
    repair_prompt,
    result_from_check,
    system_prompt,
)
from ..domain.evidence import (
    ClaimSurface,
    EvidenceTable,
    FieldPolicyBook,
    JointStatus,
    ValidationState,
    Violation,
    ViolationCode,
    method_status,
)

__all__ = [
    "MAX_REPAIRS",
    "AnalysisGenerator",
    "AnalysisInputs",
    "GenerationTurn",
    "ModuleOutcome",
    "ModuleOutcomeKind",
    "input_fingerprint",
    "run_analysis_module",
    "run_pending_modules",
]

# analysis_agent.py:90 -- `_repairs < 2`.
MAX_REPAIRS: Final = 2


@dataclass(frozen=True, slots=True)
class GenerationTurn:
    """One request to the model. ``repair`` is set on every turn after the first."""

    module_id: AnalysisModuleId
    attempt: int
    system: str
    payload: Mapping[str, Any]
    repair: str | None = None
    previous: object | None = None


class AnalysisGenerator(Protocol):
    """Anything that turns a turn into a draft: a provider gateway, or a test double.

    It returns the parsed JSON object the model produced -- untrusted -- and
    raises on a provider failure. It never falls back to another provider.
    """

    def generate(self, turn: GenerationTurn) -> object: ...


@dataclass(frozen=True, slots=True)
class AnalysisInputs:
    """Everything a module is judged against. Built by the caller from issued state."""

    table: EvidenceTable
    book: FieldPolicyBook
    joint_status: JointStatus
    surface: ClaimSurface
    research_questions: tuple[str, ...]
    language: str
    system_fingerprint: str
    validation: ValidationState | None = None
    external_context: tuple[str, ...] = ()


class ModuleOutcomeKind(StrEnum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ModuleOutcome:
    kind: ModuleOutcomeKind
    module_id: AnalysisModuleId
    input_fingerprint: str
    attempts: int
    result: AnalysisModuleResult | None = None
    violations: tuple[Violation, ...] = ()

    def __post_init__(self) -> None:
        if (self.kind is ModuleOutcomeKind.COMPLETED) != (self.result is not None):
            raise ValueError("a completed module has a result and a blocked one does not")
        if self.kind is ModuleOutcomeKind.BLOCKED and not self.violations:
            raise ValueError("a blocked module says why")


def input_fingerprint(module_id: AnalysisModuleId, inputs: AnalysisInputs) -> str:
    joint = inputs.joint_status
    certificate = (
        joint.panel_sha256
        if joint.certified and joint.panel_sha256
        else f"DEGRADED:{joint.degradation}"
    )
    return module_input_fingerprint(
        module_id,
        evidence_fingerprint=inputs.table.fingerprint(),
        research_questions=inputs.research_questions,
        field_dictionary_sha256=inputs.book.source_sha256,
        joint_certificate=certificate,
        prompt_template_sha256=prompt_template_sha256(),
        surface=inputs.surface.value,
        language=inputs.language,
    )


def run_analysis_module(
    module_id: AnalysisModuleId,
    inputs: AnalysisInputs,
    generator: AnalysisGenerator,
    *,
    max_repairs: int = MAX_REPAIRS,
) -> ModuleOutcome:
    """Run one module to COMPLETED or BLOCKED. Never returns an ungated result."""
    if not 0 <= max_repairs <= MAX_REPAIRS:
        raise ValueError(f"max_repairs must be 0..{MAX_REPAIRS}, got {max_repairs}")
    spec = module_spec(module_id)
    fingerprint = input_fingerprint(module_id, inputs)

    joint = inputs.joint_status
    if inputs.surface is ClaimSurface.CLIENT_FACING and not joint.certified:
        return ModuleOutcome(
            ModuleOutcomeKind.BLOCKED,
            module_id,
            fingerprint,
            attempts=0,
            violations=(
                Violation(
                    ViolationCode.JOINT_CERTIFICATE_DEGRADED,
                    "preflight",
                    f"{joint.degradation}: {joint.detail}; no client claim can be admitted",
                ),
            ),
        )

    system = system_prompt(spec, language=inputs.language)
    payload = module_payload(
        spec,
        inputs.table,
        research_questions=inputs.research_questions,
        external_context=inputs.external_context,
    )
    stamp = method_status(inputs.validation, inputs.system_fingerprint)

    turn = GenerationTurn(module_id, 1, system, payload)
    while True:
        raw = generator.generate(turn)
        check = check_analysis_draft(
            raw,
            spec,
            inputs.table,
            book=inputs.book,
            joint_status=joint,
            surface=inputs.surface,
            research_questions=inputs.research_questions,
        )
        if check.decision.allowed:
            result = result_from_check(
                check,
                module_id=module_id,
                surface=inputs.surface,
                method_status=stamp,
                input_fingerprint=fingerprint,
                research_questions=inputs.research_questions,
            )
            return ModuleOutcome(
                ModuleOutcomeKind.COMPLETED, module_id, fingerprint, turn.attempt, result
            )
        if turn.attempt > max_repairs:
            return ModuleOutcome(
                ModuleOutcomeKind.BLOCKED,
                module_id,
                fingerprint,
                turn.attempt,
                violations=check.decision.violations,
            )
        turn = GenerationTurn(
            module_id,
            turn.attempt + 1,
            system,
            payload,
            repair=repair_prompt(check.decision.violations),
            previous=raw,
        )


def run_pending_modules(
    inputs: AnalysisInputs,
    generator: AnalysisGenerator,
    completed: Mapping[AnalysisModuleId, str],
) -> Sequence[ModuleOutcome]:
    """Run, in order, every module not already completed on these exact inputs.

    Modules are independent: one blocked module does not stop the next, and
    each outcome is returned for the workflow to record.
    """
    current = {spec.module_id: input_fingerprint(spec.module_id, inputs) for spec in _MODULES}
    return [
        run_analysis_module(module_id, inputs, generator)
        for module_id in modules_to_run(current, completed)
    ]
