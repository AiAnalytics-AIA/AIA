"""What a model is told for one module, rendered from the same types the gate enforces.

The prompt is a courtesy to the model, not a control. Every rule it states is
enforced after the fact by :func:`.draft.check_analysis_draft`, and the parts
that could drift -- the allowed metrics, their units, the evidence rows -- are
generated from :mod:`aia_core.domain.evidence` rather than written as prose. A
prompt edit can make a model worse at passing the gate; it cannot widen what the
gate admits.

Parity is SEMANTIC (``rebuild-contract.md`` ``analysis.modules``): the reference
prompts are Czech and are recorded only as excerpts, so this is production copy
stating the same five rules (methodology-ledger M17).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any, Final

from ..evidence import (
    EvidenceTable,
    MetricKind,
    Violation,
    allowed_metric_spellings,
    unit_for,
)
from .modules import AnalysisModuleSpec

__all__ = [
    "PROMPT_TEMPLATE_VERSION",
    "module_payload",
    "prompt_template_sha256",
    "repair_prompt",
    "system_prompt",
]

PROMPT_TEMPLATE_VERSION: Final = "analysis-module-v2"

_SYSTEM: Final = """\
You are a senior research director writing one module of a client analysis: {module}.
Focus: {focus}

Answer the research questions; do not describe tables. Write prose in {language}.

Rules. A deterministic evidence gate checks every one of them after you answer, and
a draft that breaks any rule is returned to you or discarded:

1. Every number in summary, research_question_answers and key_findings must be the
   value of a numeric claim. Cite it: put the claim's id in that item's claim_ids.
2. Each numeric claim names an evidence_ref from the evidence table, a metric from
   the allowed set, and the value and unit exactly as the table gives them.
   Allowed metrics: {metrics}.
   Units: {units}.
3. Copy values exactly from the evidence. Do not recompute, round or combine them.
4. External research is context only. It is not evidence and cannot be cited.
5. Do not invent segments, causes, or relationships the evidence does not contain.

Work from the supplied evidence, questions and harness labels, never imagined context.
First check whether the measured construct actually answers the research question.
A question about visits cannot establish what services are offered. State that mismatch
before secondary findings; a technically valid frequency is not an answer to another question.
Describe fictional outputs explicitly as this test's simulated answers, never as surveyed
residents, market demand or population facts. A completed workflow does not validate a model.
Do not recommend real spending, targeting, staffing or campaigns from fictional test outputs;
recommend the specific instrument or real evidence needed to assess that decision.

Write only this module's contribution. Prefer a short candid statement of unavailable
analysis to repeating the same distribution under every heading. Do not invent objects,
segments, hypotheses, demographics, report sections or source content absent from the payload.
If module context is missing, name the missing input without claiming it never existed.
No geometry, ranking, map quality or causal inference without corresponding supplied evidence.
Suppressions are unavailable evidence, never zero, small, or an inferred complementary share.
Do not convert an answer category into a validated segment or an indicative result into a fact.

Plan a compact response: summary about 600 characters, a few distinct key findings,
and one direct answer per applicable research question. Avoid introductory praise, generic
method checklists and redundant restatements. Non-question modules may use an empty
research_question_answers array. Preserve each supplied question's wording when answering it.
Every numeral, including a count or year mentioned in passing, must pass the evidence gate.
Create only numeric_claims actually used; each claim_id is unique. Finding claim_ids and
answer claim_ids must reference those declarations. Summary has no claim_ids field:
use only numbers covered by declared claims, or use qualitative prose. Empty arrays are valid.
Return a complete corrected object on repair, fix all violations, and remove unsupported
assertions rather than disguising their numbers as words. Do not change the evidence.

Return JSON with exactly these keys: module ("{module}"), summary,
research_question_answers [{{question, answer, claim_ids}}],
key_findings [{{text, claim_ids}}], numeric_claims
[{{claim_id, evidence_ref, metric, value, unit}}]. Nothing else.
"""

_REPAIR: Final = """\
The previous draft did not pass the evidence gate. Fix every problem below and
return the complete corrected draft with the same schema. Remove any claim you
cannot back from the evidence table rather than changing its value.

{violations}
"""


def _units() -> str:
    return "; ".join(
        f"{spelling} -> {unit_for(kind).value}"
        for spelling, kind in zip(allowed_metric_spellings(), MetricKind, strict=True)
    )


def system_prompt(spec: AnalysisModuleSpec, *, language: str) -> str:
    return _SYSTEM.format(
        module=spec.module_id.value,
        focus=spec.focus,
        language=language,
        metrics=", ".join(allowed_metric_spellings()),
        units=_units(),
    )


def repair_prompt(violations: Sequence[Violation]) -> str:
    return _REPAIR.format(violations="\n".join(f"- {v}" for v in violations))


def prompt_template_sha256() -> str:
    """Identity of the templates and the rendered rule set, for provenance and fingerprints."""
    material = "\x1f".join(
        (PROMPT_TEMPLATE_VERSION, _SYSTEM, _REPAIR, ", ".join(allowed_metric_spellings()), _units())
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def module_payload(
    spec: AnalysisModuleSpec,
    table: EvidenceTable,
    *,
    research_questions: Sequence[str],
    external_context: Sequence[str] = (),
) -> dict[str, Any]:
    """The user turn: the evidence table as citable rows, and context marked as context."""
    return {
        "module": spec.module_id.value,
        "research_questions": list(research_questions),
        "evidence": [
            {
                "evidence_ref": row.evidence_ref,
                "question_id": row.question_id,
                "cell": row.cell,
                "metric": str(row.metric),
                "value": row.value,
                "unit": row.unit.value,
                "basis": row.basis.value,
                "support": row.support.status.value,
            }
            for row in (table.rows[k] for k in sorted(table.rows))
        ],
        "suppressed_evidence": sorted(table.suppressed),
        "external_context_not_evidence": list(external_context),
    }
