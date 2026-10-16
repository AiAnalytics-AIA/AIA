"""Whether a run can answer the research questions its design states, before it starts.

Readiness (``research_design.assess_readiness``) decides whether a design is **technically
runnable**: it compiles, its sample is in bounds and fieldwork can ask every question. It says
nothing about whether the run is **capable of answering the stated research questions**. A
fictional Fio run on develop (``RUN-9b6e0f5e6e0e4345``, 2026-10-16) stated four research
questions, linked none of them to a questionnaire item, started with every readiness check
green or amber, and its analysis could not answer three of them. The trace
(:mod:`.research_trace`) had said so, as a WARN that a start never read.

This module turns the trace into one decision a start reads:

* **capable**: every stated research question has at least one measure whose numbers the
  analysis may cite (ANSWERABLE or AT_RISK, not open-ended and not excluded from analysis), or
  whose support is decided only at fieldwork;
* such a research question whose verdict is UNKNOWN is **pending**: not a defect of the design,
  and never scored as answerable either -- the report says it was decided by fieldwork;
* every other research question is a :class:`AnswerabilityGap`, with its reasons
  (:class:`GapReason`, always at least one): nothing measures it, its measures cannot be
  answered, only open questions or items the analysis may not cite measure it, its declared
  comparison cannot be carried or is unknown, or the design links no item to any research
  question (``unlinked_design``: nothing says what answers what). A design with no research
  question at all is one gap of its own.

A start over a design that is not capable is refused unless a person acknowledges these exact
gaps (:attr:`Answerability.digest`) with a reason; the acknowledgement is recorded in the
approval ledger and in the run's metadata, and the report prints it. Nothing here lowers a gap
to a pass: an acknowledgement records a person's decision to run anyway, it never makes a
research question answerable. Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .pipeline import fingerprint
from .question_outlook import OutlookReason, QuestionOutlook, Verdict
from .research_trace import ResearchTrace, TraceReason

__all__ = [
    "ANSWERABILITY_RULES",
    "MAX_ACKNOWLEDGEMENT_CHARS",
    "MIN_ACKNOWLEDGEMENT_CHARS",
    "Acknowledgement",
    "AcknowledgementRefused",
    "Answerability",
    "AnswerabilityGap",
    "GapKind",
    "GapReason",
    "answerability",
    "answerability_note",
    "read_answerability_note",
]

#: The rules a run records with its answerability; a change to what counts as a gap is a new id.
ANSWERABILITY_RULES: Final = "aia-answerability-1"
MIN_ACKNOWLEDGEMENT_CHARS: Final = 10
MAX_ACKNOWLEDGEMENT_CHARS: Final = 1000


class GapReason(StrEnum):
    """Why a research question is a gap. Closed: the report and the screen word every one."""

    UNMEASURED = TraceReason.UNMEASURED.value
    UNLINKED_DESIGN = TraceReason.UNLINKED_DESIGN.value
    COMPARISON_NEEDS_TRACKED_SET = TraceReason.COMPARISON_NEEDS_TRACKED_SET.value
    COMPARISON_NEEDS_CONCEPT_SET = TraceReason.COMPARISON_NEEDS_CONCEPT_SET.value
    SEGMENTS_UNAVAILABLE = TraceReason.SEGMENTS_UNAVAILABLE.value
    COMPARISON_UNKNOWN = TraceReason.COMPARISON_UNKNOWN.value
    #: Measured only by items the run will not answer (conditional, familiarity, refused,
    #: suppressed support).
    MEASURES_UNANSWERABLE = "measures_unanswerable"
    #: Measured only by open questions or items the analysis may not cite: the research
    #: questions module would have no number to answer it with.
    NO_CITABLE_MEASURE = "no_citable_measure"


#: Trace reasons that make a research question a gap even when its verdict is not UNANSWERABLE.
_GAP_REASONS: Final = frozenset({TraceReason.UNLINKED_DESIGN, TraceReason.COMPARISON_UNKNOWN})
#: An item with any of these is answered, but the analysis cites none of its numbers.
_NOT_CITABLE: Final = frozenset({OutlookReason.OPEN_ENDED, OutlookReason.SUPPORT_ANALYSIS_EXCLUDED})
#: Best first, as the trace orders verdicts (``research_trace``): "worse" is later.
_ORDER: Final = (Verdict.ANSWERABLE, Verdict.AT_RISK, Verdict.UNKNOWN, Verdict.UNANSWERABLE)


def _worse(a: Verdict, b: Verdict) -> Verdict:
    return max(a, b, key=_ORDER.index)


class GapKind(StrEnum):
    #: The design states no research question: the research questions module will block.
    NO_RESEARCH_QUESTIONS = "no_research_questions"
    #: This research question has no measure the run can answer.
    NOT_ANSWERABLE = "not_answerable"


@dataclass(frozen=True, slots=True)
class AnswerabilityGap:
    kind: GapKind
    #: The research question's text; ``None`` for :attr:`GapKind.NO_RESEARCH_QUESTIONS`.
    research_question: str | None = None
    verdict: Verdict | None = None
    reasons: tuple[str, ...] = ()
    #: The item ids that declare they measure it (none: nothing does).
    measures: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "research_question": self.research_question,
            "verdict": self.verdict.value if self.verdict else None,
            "reasons": list(self.reasons),
            "measures": list(self.measures),
        }


@dataclass(frozen=True, slots=True)
class Answerability:
    capable: bool
    gaps: tuple[AnswerabilityGap, ...]
    #: Names these exact gaps under these rules: an acknowledgement covers only the gaps it was
    #: given for (the design revision and rules are recorded beside it in the ledger).
    digest: str
    #: Research questions measured, whose support only fieldwork decides (UNKNOWN): not gaps,
    #: never answerable either.
    pending: tuple[str, ...] = ()


class AcknowledgementRefused(ValueError):
    """An acknowledgement that does not name the gaps, or gives no reason."""


@dataclass(frozen=True, slots=True)
class Acknowledgement:
    """A person's decision to run a design whose research questions it cannot all answer."""

    digest: str
    reason: str

    def __post_init__(self) -> None:
        reason = " ".join(self.reason.split())
        if not MIN_ACKNOWLEDGEMENT_CHARS <= len(reason) <= MAX_ACKNOWLEDGEMENT_CHARS:
            raise AcknowledgementRefused(
                f"the reason must be {MIN_ACKNOWLEDGEMENT_CHARS}-{MAX_ACKNOWLEDGEMENT_CHARS} "
                "characters"
            )
        object.__setattr__(self, "reason", reason)

    def covers(self, answer: Answerability) -> bool:
        return self.digest == answer.digest


def answerability(trace: ResearchTrace, outlook: Sequence[QuestionOutlook] = ()) -> Answerability:
    """The gaps between ``trace``'s research questions and what the run can answer.

    ``outlook`` is every item's verdict (:func:`~.question_outlook.question_outlook`), the one
    the trace was built from: it says which measures the analysis may cite at all, and which
    the run will answer.

    The trace's verdict is the best over *all* measures, so an open question (AT_RISK, never
    cited) beside a conditional one (UNANSWERABLE) read as at risk and passed, with no measure
    the research questions module could cite (review, 2026-10-16). Only measures the analysis
    may cite and the run will answer decide here: none of them is a gap, and their best verdict
    decides whether support is left to fieldwork (pending)."""
    reasons_of = {o.question_id: set(o.reasons) for o in outlook}
    verdict_of = {o.question_id: o.verdict for o in outlook}
    gaps: list[AnswerabilityGap] = []
    pending: list[str] = []
    if not trace.questions:
        gaps.append(AnswerabilityGap(kind=GapKind.NO_RESEARCH_QUESTIONS))
    for q in trace.questions:
        why = [GapReason(r.value) for r in q.reasons]
        citable = [m for m in q.measures if not reasons_of.get(m, set()) & _NOT_CITABLE]
        # A measure the outlook does not know is UNKNOWN, never answerable; with no outlook at
        # all there is nothing to judge measures by, and the trace's verdict stands.
        usable = [
            m for m in citable if verdict_of.get(m, Verdict.UNKNOWN) is not Verdict.UNANSWERABLE
        ]
        verdict = q.verdict
        if outlook and usable:
            best = min((verdict_of.get(m, Verdict.UNKNOWN) for m in usable), key=_ORDER.index)
            verdict = _worse(q.verdict, best)
        if q.verdict is Verdict.UNANSWERABLE or set(q.reasons) & _GAP_REASONS:
            if not why:
                why = [GapReason.MEASURES_UNANSWERABLE]
        elif q.measures and not citable:
            why.append(GapReason.NO_CITABLE_MEASURE)
        elif q.measures and outlook and not usable:
            # Every measure it could cite is one the run will not answer.
            why.append(GapReason.MEASURES_UNANSWERABLE)
            verdict = Verdict.UNANSWERABLE
        else:
            if verdict is Verdict.UNKNOWN:
                pending.append(q.text)
            continue
        gaps.append(
            AnswerabilityGap(
                kind=GapKind.NOT_ANSWERABLE,
                research_question=q.text,
                verdict=verdict,
                reasons=tuple(r.value for r in dict.fromkeys(why)),
                measures=q.measures,
            )
        )
    digest = fingerprint({"rules": ANSWERABILITY_RULES, "gaps": [g.to_json() for g in gaps]})
    return Answerability(capable=not gaps, gaps=tuple(gaps), digest=digest, pending=tuple(pending))


def answerability_note(
    trace: ResearchTrace,
    answer: Answerability,
    *,
    acknowledged_by: str | None = None,
    acknowledgement: Acknowledgement | None = None,
    inherited_from: str | None = None,
) -> dict[str, Any]:
    """What a run records of its answerability at start: every research question with its
    verdict and measures, the gaps, and the acknowledgement that let a run with gaps start.

    It is the frozen record the report reads, never today's design. A run started where the
    gate was off records its gaps with ``enforced: false`` and no acknowledgement."""
    note: dict[str, Any] = {
        "rules": ANSWERABILITY_RULES,
        "capable": answer.capable,
        "digest": answer.digest,
        "linked": trace.linked,
        "research_questions": [
            {
                "text": q.text,
                "verdict": q.verdict.value,
                "reasons": [r.value for r in q.reasons],
                "measures": list(q.measures),
                "comparison": q.comparison.value if q.comparison else None,
            }
            for q in trace.questions
        ],
        "gaps": [g.to_json() for g in answer.gaps],
        "pending": list(answer.pending),
    }
    if acknowledgement is not None:
        note["acknowledgement"] = {
            "reason": acknowledgement.reason,
            "by": acknowledged_by,
            **({"inherited_from": inherited_from} if inherited_from else {}),
        }
    return note


def read_answerability_note(meta: Mapping[str, Any]) -> dict[str, Any] | None:
    """A run's recorded answerability, or ``None`` for a run started before it was recorded
    (or one whose record AIA cannot read: never read as capable)."""
    note = meta.get("answerability")
    if (
        not isinstance(note, Mapping)
        or note.get("rules") != ANSWERABILITY_RULES
        or not isinstance(note.get("capable"), bool)
        or not isinstance(note.get("research_questions"), list)
        or not isinstance(note.get("gaps"), list)
    ):
        return None
    return dict(note)
