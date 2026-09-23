"""A completed analysis module. It cannot hold an unchecked number.

:class:`AnalysisModuleResult` accepts claims only as
:class:`~aia_core.domain.evidence.AdmittedClaim` -- which only the evidence gate
can mint -- and re-runs the prose coverage check against those admitted claims
on construction. So a result built by any path, including one that skipped
:func:`.draft.check_analysis_draft`, still refuses prose that carries a number
no admitted claim backs. The method-status stamp is one of the two values code
computes; a model's wording cannot be stamped.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..evidence import (
    METHOD_STATUS_HOLDOUT_VALIDATED,
    METHOD_STATUS_PENDING,
    AdmittedClaim,
    ClaimSurface,
)
from .draft import DraftCheck, uncovered_numbers
from .modules import AnalysisModuleId

__all__ = [
    "AnalysisModuleResult",
    "Finding",
    "ResearchQuestionAnswer",
    "UnbackedResult",
    "result_from_check",
]


class UnbackedResult(ValueError):
    """A result was about to carry something the evidence gate did not admit."""


@dataclass(frozen=True, slots=True)
class ResearchQuestionAnswer:
    question: str
    answer: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Finding:
    text: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisModuleResult:
    module_id: AnalysisModuleId
    summary: str
    research_question_answers: tuple[ResearchQuestionAnswer, ...]
    key_findings: tuple[Finding, ...]
    claims: tuple[AdmittedClaim, ...]
    surface: ClaimSurface
    method_status: str
    input_fingerprint: str
    research_questions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(isinstance(c, AdmittedClaim) for c in self.claims):
            raise UnbackedResult("a result holds only admitted claims")
        if any(c.surface is not self.surface for c in self.claims):
            raise UnbackedResult("every claim must be admitted for the result's surface")
        if self.method_status not in {METHOD_STATUS_PENDING, METHOD_STATUS_HOLDOUT_VALIDATED}:
            raise UnbackedResult(f"unknown method status {self.method_status!r}")

        by_id = {c.claim_id: c for c in self.claims}
        if len(by_id) != len(self.claims):
            raise UnbackedResult("claim ids are unique")

        def require(where: str, text: str, ids: tuple[str, ...], names: list[str]) -> None:
            missing = [i for i in ids if i not in by_id]
            if missing:
                raise UnbackedResult(f"{where} cites claims that were not admitted: {missing}")
            cited = [by_id[i] for i in ids]
            loose = uncovered_numbers(
                text, [c.value for c in cited], names + [c.row.cell for c in cited]
            )
            if loose:
                raise UnbackedResult(f"{where} carries numbers no admitted claim backs: {loose}")

        for i, a in enumerate(self.research_question_answers):
            require(f"research_question_answers[{i}]", a.answer, a.claim_ids, [a.question])
        for i, f in enumerate(self.key_findings):
            require(f"key_findings[{i}]", f.text, f.claim_ids, [])
        require("summary", self.summary, tuple(by_id), list(self.research_questions))

    @property
    def indicative_claims(self) -> tuple[AdmittedClaim, ...]:
        return tuple(c for c in self.claims if c.indicative)


def result_from_check(
    check: DraftCheck,
    *,
    module_id: AnalysisModuleId,
    surface: ClaimSurface,
    method_status: str,
    input_fingerprint: str,
    research_questions: tuple[str, ...],
) -> AnalysisModuleResult:
    """Turn a passing check into a result. A failing check raises; it is never softened."""
    if not check.decision.allowed or check.draft is None or check.admission is None:
        raise UnbackedResult("; ".join(str(v) for v in check.decision.violations) or "no draft")
    draft = check.draft
    return AnalysisModuleResult(
        module_id=module_id,
        summary=draft.summary,
        research_question_answers=tuple(
            ResearchQuestionAnswer(a.question, a.answer, a.claim_ids)
            for a in draft.research_question_answers
        ),
        key_findings=tuple(Finding(f.text, f.claim_ids) for f in draft.key_findings),
        claims=check.admission.admitted,
        surface=surface,
        method_status=method_status,
        input_fingerprint=input_fingerprint,
        research_questions=research_questions,
    )
