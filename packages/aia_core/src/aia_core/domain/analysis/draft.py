"""The draft a model returns for one module, and the check that stands between it and a result.

The draft is untrusted input. :func:`check_analysis_draft` parses it against a
closed schema, admits its numeric claims through the evidence gate
(:func:`aia_core.domain.evidence.admit_numeric_claims`), and then enforces the
rule the reference stated only in its prompt: *every number in the research
question answers and the key findings must appear in numeric_claims*
(methodology-ledger M17). The reference's validator never read the prose: it
checked declared claims within 0.051 and passed when 95 % of the findings cited
evidence. This one requires every number in the prose to be a cited claim's, copied
exactly; a finding that states no number cites nothing, which the reference would
have counted against its coverage (decision ANL-4, ``test_analysis_gate_parity.py``).

A number in prose is covered when it is

* a cited claim's value, allowing only the rounding the prose itself shows
  (``42`` covers 42.4; ``42,4`` does not cover 42.46), or
* part of the *name* of what was cited -- the prose writes a range or bound
  that the cell label of a row the item cites (``vek 18-29``), or the research
  question it answers, also contains. The whole form must match: citing
  ``vek 18-29`` licenses "18\u201329 let", never a stray "29 %". A bare number in a
  label licenses nothing.

Anything else is an uncited number, including a year or a count written in
passing. That is the trade-off: some innocent drafts go back for repair, and no
invented figure reaches a client.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..evidence import (
    Admission,
    ClaimSurface,
    EvidenceTable,
    FieldPolicyBook,
    GateDecision,
    JointStatus,
    NumericClaim,
    ViolationCode,
    admit_numeric_claims,
    block,
    combine,
)
from .modules import AnalysisModuleSpec

__all__ = [
    "AnalysisDraft",
    "DraftCheck",
    "FindingDraft",
    "NumericClaimDraft",
    "ResearchQuestionAnswerDraft",
    "check_analysis_draft",
    "numbers_in",
    "uncovered_numbers",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NumericClaimDraft(_Strict):
    claim_id: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: float = Field(allow_inf_nan=False, strict=True)
    unit: str = Field(min_length=1)


class FindingDraft(_Strict):
    text: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = ()


class ResearchQuestionAnswerDraft(_Strict):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = ()


class AnalysisDraft(_Strict):
    """What a model may return. Nothing else: no method status, no support labels."""

    module: str
    summary: str = Field(min_length=1)
    research_question_answers: tuple[ResearchQuestionAnswerDraft, ...] = ()
    key_findings: tuple[FindingDraft, ...] = ()
    numeric_claims: tuple[NumericClaimDraft, ...] = ()


# A number as prose writes it: digits, optionally grouped in threes by a space,
# optionally with a decimal comma or point. Not part of an identifier (q1, E12,
# vote_2021), and signs are ignored because no allowed metric is negative.
_NUMBER: Final = re.compile(
    r"(?<![\w.,])(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?(?!\w)"
)


# The forms in which a number is part of a *name* rather than a claim: a range
# (18-29, 18\u201329, 18 až 29, 18 to 29) or a bound (65+, <30, \u226565). A bare number
# in a label is not one of them -- "cohort 2021" gives no licence to write 2021 --
# because a bare number in a name cannot be told apart from a bare figure in prose.
_NUM: Final = r"(?<![\w.,])\d+(?:[.,]\d+)?"
_NAME_FORM: Final = re.compile(
    rf"(?P<lo>{_NUM})\s*(?:[-\u2013\u2014\u2212]|\ba\u017e\b|\bto\b)\s*(?P<hi>{_NUM})(?!\w)"
    rf"|(?P<plus>{_NUM})\s*\+"
    rf"|(?P<op>[<>\u2264\u2265])\s*(?P<bound>{_NUM})"
)


def _as_float(raw: str) -> float:
    return float(re.sub(r"[ \u00a0\u202f]", "", raw).replace(",", "."))


def _name_forms(text: str) -> list[tuple[tuple[object, ...], int, int]]:
    """Every range or bound in ``text``, as (canonical key, start, end)."""
    forms: list[tuple[tuple[object, ...], int, int]] = []
    for m in _NAME_FORM.finditer(text):
        if m.group("lo") is not None:
            key: tuple[object, ...] = ("range", _as_float(m["lo"]), _as_float(m["hi"]))
        elif m.group("plus") is not None:
            key = ("bound", ">=", _as_float(m["plus"]))
        else:
            op = {"<": "<", ">": ">", "\u2264": "<=", "\u2265": ">="}[m["op"]]
            key = ("bound", op, _as_float(m["bound"]))
        forms.append((key, m.start(), m.end()))
    return forms


def _numbers_at(text: str) -> list[tuple[float, int, int]]:
    """Every number in prose, as (value, decimals shown, start offset)."""
    found: list[tuple[float, int, int]] = []
    for match in _NUMBER.finditer(text):
        raw = re.sub(r"[ \u00a0\u202f]", "", match.group(0)).replace(",", ".")
        decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
        found.append((float(raw), decimals, match.start()))
    return found


def numbers_in(text: str) -> tuple[tuple[float, int], ...]:
    """Every number in prose, as (value, decimals shown)."""
    return tuple((value, decimals) for value, decimals, _ in _numbers_at(text))


def _covers(value: float, decimals: int, backing: Iterable[float]) -> bool:
    tolerance = 0.5 * 10.0**-decimals + 1e-9
    return any(math.isfinite(v) and abs(value - v) <= tolerance for v in backing)


def uncovered_numbers(
    text: str, values: Iterable[float], identifiers: Iterable[str]
) -> tuple[float, ...]:
    """Numbers in ``text`` backed neither by a cited value nor by a cited name.

    A number is part of a cited name only where the prose writes the name's
    range or bound itself: ``vek 18-29`` exempts the 18 and the 29 of "18\u201329 let",
    and nothing in "zájem má 29 %".
    """
    backing = list(values)
    allowed = {key for label in identifiers for key, _, _ in _name_forms(label)}
    named_spans = [(start, end) for key, start, end in _name_forms(text) if key in allowed]
    return tuple(
        n
        for n, d, at in _numbers_at(text)
        if not any(start <= at < end for start, end in named_spans) and not _covers(n, d, backing)
    )


@dataclass(frozen=True, slots=True)
class DraftCheck:
    """The outcome of checking one draft. ``admission`` is set once the schema parsed."""

    decision: GateDecision
    draft: AnalysisDraft | None
    admission: Admission | None


def _schema_errors(exc: ValidationError) -> GateDecision:
    return combine(
        block(
            ViolationCode.SCHEMA_INVALID,
            ".".join(str(p) for p in err["loc"]) or "draft",
            err["msg"],
        )
        for err in exc.errors()[:20]
    )


def _coverage(
    draft: AnalysisDraft, table: EvidenceTable, research_questions: Sequence[str]
) -> GateDecision:
    claims = {c.claim_id: c for c in draft.numeric_claims}

    def cells(ids: Iterable[str]) -> list[str]:
        rows = (table.rows.get(claims[i].evidence_ref) for i in ids if i in claims)
        return [row.cell for row in rows if row is not None]

    decisions: list[GateDecision] = []

    def check(where: str, text: str, ids: Sequence[str], names: list[str]) -> None:
        for dangling in (i for i in ids if i not in claims):
            decisions.append(
                block(ViolationCode.DANGLING_CLAIM_REF, where, f"cites unknown claim {dangling!r}")
            )
        values = [claims[i].value for i in ids if i in claims]
        for number in uncovered_numbers(text, values, names + cells(ids)):
            decisions.append(
                block(
                    ViolationCode.UNCITED_NUMBER,
                    where,
                    f"{number:g} is not backed by a claim this item cites",
                )
            )

    for i, answer in enumerate(draft.research_question_answers):
        check(f"research_question_answers[{i}]", answer.answer, answer.claim_ids, [answer.question])
    for i, finding in enumerate(draft.key_findings):
        check(f"key_findings[{i}]", finding.text, finding.claim_ids, [])
    # The summary cites nothing itself, so it may use any claim the draft makes.
    check("summary", draft.summary, list(claims), list(research_questions))
    return combine(decisions)


def _questions(
    draft: AnalysisDraft, spec: AnalysisModuleSpec, research_questions: Sequence[str]
) -> GateDecision:
    asked = set(research_questions)
    answered = [a.question for a in draft.research_question_answers]
    decisions = [
        block(
            ViolationCode.RESEARCH_QUESTION_UNKNOWN, q, "answers a question the study did not ask"
        )
        for q in answered
        if q not in asked
    ]
    if spec.answers_research_questions:
        decisions.extend(
            block(ViolationCode.RESEARCH_QUESTION_UNANSWERED, q, "every question needs an answer")
            for q in research_questions
            if q not in answered
        )
    return combine(decisions)


def check_analysis_draft(
    raw: object,
    spec: AnalysisModuleSpec,
    table: EvidenceTable,
    *,
    book: FieldPolicyBook,
    joint_status: JointStatus,
    surface: ClaimSurface,
    research_questions: Sequence[str],
) -> DraftCheck:
    """Check one module draft completely. Every violation is reported for the repair turn."""
    if not isinstance(raw, Mapping):
        return DraftCheck(
            block(ViolationCode.SCHEMA_INVALID, "draft", "the draft is not a JSON object"),
            None,
            None,
        )
    try:
        draft = AnalysisDraft.model_validate(dict(raw))
    except ValidationError as exc:
        return DraftCheck(_schema_errors(exc), None, None)

    decisions: list[GateDecision] = []
    if draft.module != spec.module_id.value:
        decisions.append(
            block(
                ViolationCode.MODULE_MISMATCH,
                draft.module,
                f"this turn runs the {spec.module_id} module",
            )
        )
    admission = admit_numeric_claims(
        [
            NumericClaim(c.claim_id, c.evidence_ref, c.metric, c.value, c.unit)
            for c in draft.numeric_claims
        ],
        table,
        book=book,
        joint_status=joint_status,
        surface=surface,
    )
    decisions.append(admission.decision)
    decisions.append(_questions(draft, spec, research_questions))
    decisions.append(_coverage(draft, table, research_questions))
    return DraftCheck(combine(decisions), draft, admission)
