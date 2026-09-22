"""The eight analysis modules: identity, order, focus, and the fingerprint that makes each durable.

Reference ``analysis_agent.py`` runs "exactly one durable analysis module. Each
module is independently fingerprinted by the workflow and may be resumed or
provider-switched without repeating already completed modules." The eight, in
the reference's output order (``ANALYSIS_01_EXECUTIVE`` ... ``ANALYSIS_08_LIMITATIONS``),
are executive, research questions, objects, audience, segments, hypotheses,
implications and limitations (``docs/architecture/domain-map.md``).

Parity is SEMANTIC on each module's prose and EXACT on evidence discipline
(``rebuild-contract.md`` ``analysis.modules``). So the module identity, order and
fingerprint are fixed here; the *focus* text is production copy, not recovered
prompt text; and every module shares one draft schema and one evidence gate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ..pipeline import fingerprint

__all__ = [
    "ANALYSIS_MODULES",
    "AnalysisModuleId",
    "AnalysisModuleSpec",
    "module_input_fingerprint",
    "module_spec",
    "modules_to_run",
]


class AnalysisModuleId(StrEnum):
    EXECUTIVE = "executive"
    RESEARCH_QUESTIONS = "research_questions"
    OBJECTS = "objects"
    AUDIENCE = "audience"
    SEGMENTS = "segments"
    HYPOTHESES = "hypotheses"
    IMPLICATIONS = "implications"
    LIMITATIONS = "limitations"


@dataclass(frozen=True, slots=True)
class AnalysisModuleSpec:
    module_id: AnalysisModuleId
    ordinal: int
    focus: str
    answers_research_questions: bool = False

    @property
    def artifact_name(self) -> str:
        return f"ANALYSIS_{self.ordinal:02d}_{self.module_id.value.upper()}"


ANALYSIS_MODULES: Final[tuple[AnalysisModuleSpec, ...]] = (
    AnalysisModuleSpec(
        AnalysisModuleId.EXECUTIVE,
        1,
        "State the decision-relevant answer to the client's question and the few findings "
        "that carry it. Answer the question; do not describe tables.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.RESEARCH_QUESTIONS,
        2,
        "Answer every research question in turn, from the evidence only. Where the evidence "
        "cannot answer a question, say so rather than guessing.",
        answers_research_questions=True,
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.OBJECTS,
        3,
        "Compare the tracked objects (brands, offers, policies) on the measures in the "
        "evidence, and say where the differences are and are not supported.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.AUDIENCE,
        4,
        "Describe the target audience as the evidence shows it, with each figure's scope.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.SEGMENTS,
        5,
        "Describe only the segments present in the evidence table. Do not invent segments, "
        "and do not describe a segment by a relationship the evidence does not contain.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.HYPOTHESES,
        6,
        "State which study hypotheses the evidence supports, contradicts or cannot decide. "
        "Do not infer causality.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.IMPLICATIONS,
        7,
        "Draw the implications for the client's decision that follow from the findings, "
        "keeping each tied to the evidence it rests on.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.LIMITATIONS,
        8,
        "State the limits of this evidence: that it is synthetic, modelled research; which "
        "cells were suppressed or are indicative; and what cannot be claimed from it.",
    ),
)

_BY_ID: Final = {spec.module_id: spec for spec in ANALYSIS_MODULES}


def module_spec(module_id: AnalysisModuleId | str) -> AnalysisModuleSpec:
    return _BY_ID[AnalysisModuleId(module_id)]


def module_input_fingerprint(
    module_id: AnalysisModuleId,
    *,
    evidence_fingerprint: str,
    research_questions: Sequence[str],
    field_dictionary_sha256: str,
    joint_certificate: str,
    prompt_template_sha256: str,
    surface: str,
    language: str,
) -> str:
    """Everything that makes a module's output valid. Change any of it and the module reruns.

    The provider and model are deliberately absent: a provider switch after a
    quota failure must not force completed modules to rerun (reference
    ``analysis_agent.py``); the model that produced each module is provenance on
    its result, not an input to its validity.
    """
    return fingerprint(
        {
            "module": module_id.value,
            "evidence": evidence_fingerprint,
            "research_questions": list(research_questions),
            "field_dictionary": field_dictionary_sha256,
            "joint_certificate": joint_certificate,
            "prompt_template": prompt_template_sha256,
            "surface": surface,
            "language": language,
        }
    )


def modules_to_run(
    current: Mapping[AnalysisModuleId, str], completed: Mapping[AnalysisModuleId, str]
) -> tuple[AnalysisModuleId, ...]:
    """Modules still to run, in module order: missing, or completed on different inputs.

    A quota failure after module 5 resumes at module 6; an evidence change reruns all.
    """
    missing = [m.module_id for m in ANALYSIS_MODULES if m.module_id not in current]
    if missing:
        raise ValueError(f"no input fingerprint for {', '.join(missing)}")
    return tuple(
        spec.module_id
        for spec in ANALYSIS_MODULES
        if completed.get(spec.module_id) != current[spec.module_id]
    )
