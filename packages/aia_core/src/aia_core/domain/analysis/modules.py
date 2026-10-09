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
        "Lead with whether the client decision can be answered. Summarize only the decisive "
        "supported conclusions and the next necessary evidence. In a fictional test, "
        "describe workflow and instrument adequacy, not a real-world recommendation.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.RESEARCH_QUESTIONS,
        2,
        "Answer each supplied research question exactly once. State answered, partly "
        "answerable or not answerable in prose, explaining the measured construct and the "
        "missing evidence. Do not substitute a convenient table for the requested answer.",
        answers_research_questions=True,
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.OBJECTS,
        3,
        "Compare only tracked objects for which evidence rows actually provide comparable "
        "measures. Discuss supported differences and unresolved comparisons, not generic "
        "response frequencies. With no object evidence, explain what a comparable-object "
        "battery must supply. Do not infer map proximity or rank from unrelated rows.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.AUDIENCE,
        4,
        "Describe only the audience scope and attributes actually present in the payload. "
        "Do not infer demographics, attitudes or experience from a fictional roster or "
        "answer distribution. Distinguish the intended audience from the respondent "
        "evidence; name missing audience attributes and selection limits.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.SEGMENTS,
        5,
        "Discuss only explicitly supplied segment evidence and supported within-segment "
        "findings. Answer options are not validated segments. Without segment evidence, say "
        "segmentation cannot be assessed; do not rename yes/no groups as personas or repeat "
        "their frequencies.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.HYPOTHESES,
        6,
        "Evaluate only hypotheses explicitly supplied in context against matching evidence: "
        "supported, contradicted or undecided in prose. If none are supplied, say "
        "hypotheses cannot be assessed from this payload. Do not manufacture hypotheses, "
        "significance tests or causal explanations.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.IMPLICATIONS,
        7,
        "Connect each implication to a supplied supported finding and its decision scope. "
        "Separate what may be decided, what needs further measurement and what remains "
        "uncertain. Fictional output supports test and design improvements only; never "
        "advise real budgets, campaigns or staffing from it.",
    ),
    AnalysisModuleSpec(
        AnalysisModuleId.LIMITATIONS,
        8,
        "Explain the specific limits that change use of these results: fictional origin, "
        "construct mismatch, missing object/segment evidence, suppression, indicative "
        "support and lack of real-world validation as supplied. Separate limitations from "
        "findings; do not repeat distributions or invent missing metadata values.",
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
    method_status: str,
    system_fingerprint: str,
    external_context: Sequence[str],
) -> str:
    """Everything that makes a module's output valid. Change any of it and the module reruns.

    ``joint_certificate`` is the fingerprint of the whole certificate in force,
    not its panel hash: a certificate re-issued for the same panel with a
    permission revoked must rerun what the old one allowed. ``method_status`` and
    ``system_fingerprint`` are there because the stamp is part of the result;
    ``external_context`` because it is part of what the model was shown.

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
            "method_status": method_status,
            "system": system_fingerprint,
            "external_context": list(external_context),
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
