"""Before a run: each research question, the measures that answer it, and the ones nothing does.

The analysis module ``research_questions`` must answer every research question the design
states (``analysis/draft.py``: ``RESEARCH_QUESTION_UNANSWERED``), and it can only cite the
numbers the run produces. A research question that no question or tracked set measures
was found out only after fieldwork, as a blocked module. Nothing tied a measure to a
research question at all.

A question or a tracked set now declares the research questions it measures
(``research_questions``, their text as the plan states them; see
:class:`~.research_design.SpecQuestion`). :func:`trace_research` follows each stated
research question to the items that declare it, and gives it the best verdict among
them (:mod:`.question_outlook`): a research question is as answerable as its best
measure. So:

* **no measure**: UNANSWERABLE, ``unmeasured``;
* **measures, but none the run can answer**: the best of their verdicts, so UNANSWERABLE,
  or UNKNOWN when support is decided only at fieldwork; unknown is never answerable;
* a link naming a research question the plan does not state (its text was edited, or the
  question removed) is listed apart as ``dangling``: it measures nothing it can be
  checked against.

A design that declares no link at all is traced as unknown, never covered: nothing
says which question answers what.

**How a research question is answered** (3c). The plan may declare, for each research
question, the comparison that answers it (``research_plan.research_question_comparisons``:
its text -> a :class:`Comparison`). The trace then checks that its measures can carry it:

* ``describe``: any measure;
* ``rank_objects``: a tracked set among its measures, with at least two primary objects; the
  research question is as answerable as that set;
* ``ab_test``: a concept-test set (``test_konceptu``) of at least two concepts among them;
* ``compare_segments``: no AIA run gives its analysis segment evidence yet (the segments
  module says segmentation cannot be assessed without it), so it is unanswerable, by name;
* a kind AIA does not know is unknown, never answerable.

An undeclared comparison is not checked; it is a declaration not made. Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .question_outlook import QuestionOutlook, Verdict
from .research_design import (
    CheckStatus,
    Readiness,
    ReadinessCheck,
    ResearchSpecification,
    SpecBattery,
)

__all__ = [
    "RESEARCH_TRACE_CHECK",
    "Comparison",
    "DanglingLink",
    "ResearchQuestionTrace",
    "ResearchTrace",
    "TraceReason",
    "comparisons_of",
    "trace_research",
    "with_research_trace",
]

#: The readiness check this module adds.
RESEARCH_TRACE_CHECK: Final = "research_question_coverage"

#: Best first: a research question is as answerable as its best measure.
_BEST: Final = (Verdict.ANSWERABLE, Verdict.AT_RISK, Verdict.UNKNOWN, Verdict.UNANSWERABLE)


class Comparison(StrEnum):
    """How a research question is answered, as the plan declares it."""

    DESCRIBE = "describe"
    RANK_OBJECTS = "rank_objects"
    COMPARE_SEGMENTS = "compare_segments"
    AB_TEST = "ab_test"


class TraceReason(StrEnum):
    #: No question or tracked set declares that it measures this research question.
    UNMEASURED = "unmeasured"
    #: The design declares no link at all, so nothing says what measures this one.
    UNLINKED_DESIGN = "unlinked_design"
    #: Ranking objects needs a tracked set among its measures.
    COMPARISON_NEEDS_TRACKED_SET = "comparison_needs_tracked_set"
    #: An A/B test needs a concept-test set of at least two concepts among its measures.
    COMPARISON_NEEDS_CONCEPT_SET = "comparison_needs_concept_set"
    #: No AIA run gives its analysis segment evidence yet.
    SEGMENTS_UNAVAILABLE = "segments_unavailable"
    #: The declared comparison is not one AIA knows.
    COMPARISON_UNKNOWN = "comparison_unknown"


#: The output type a concept-test set declares (``research_design`` ``output_type``).
_CONCEPT_TEST: Final = "test_konceptu"


@dataclass(frozen=True, slots=True)
class ResearchQuestionTrace:
    """One stated research question and what measures it.

    ``measures`` are the item ids (:class:`QuestionOutlook.question_id`) that declare it,
    in questionnaire order; a tracked set contributes every one of its objects.
    """

    text: str
    measures: tuple[str, ...]
    verdict: Verdict
    reasons: tuple[TraceReason, ...]
    #: The comparison the plan declares for it; ``None`` when none is declared or the
    #: declared one is unknown (``comparison_unknown`` says which).
    comparison: Comparison | None = None


@dataclass(frozen=True, slots=True)
class DanglingLink:
    """An item that names a research question the plan does not state."""

    question_id: str
    research_question: str


@dataclass(frozen=True, slots=True)
class ResearchTrace:
    questions: tuple[ResearchQuestionTrace, ...]
    dangling: tuple[DanglingLink, ...]
    #: Whether any item declares a link; without one, coverage is unknown.
    linked: bool


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def comparisons_of(design: Mapping[str, Any]) -> dict[str, Comparison | None]:
    """``research_plan.research_question_comparisons``, keyed by research question text
    (whitespace collapsed). A value AIA does not know maps to ``None``: declared, unknown."""
    plan = design.get("research_plan")
    raw = plan.get("research_question_comparisons") if isinstance(plan, Mapping) else None
    if not isinstance(raw, Mapping):
        return {}
    known = {c.value: c for c in Comparison}
    return {
        _key(text): known.get(kind) if isinstance(kind, str) else None
        for text, kind in raw.items()
        if isinstance(text, str) and _key(text)
    }


def _worse(a: Verdict, b: Verdict) -> Verdict:
    return max(a, b, key=_BEST.index)


def _batteries(spec: ResearchSpecification) -> dict[str, SpecBattery]:
    return {b.question_id(o): b for b in spec.batteries for o in b.objects}


def _primary(battery: SpecBattery) -> int:
    return sum(1 for o in battery.objects if o.id not in battery.context_objects)


def _judge(
    comparison: Comparison,
    measures: tuple[str, ...],
    verdict: Verdict,
    verdicts: Mapping[str, Verdict],
    batteries: Mapping[str, SpecBattery],
) -> tuple[Verdict, tuple[TraceReason, ...]]:
    """The research question's verdict once its comparison is checked against its measures."""
    if comparison is Comparison.COMPARE_SEGMENTS:
        return Verdict.UNANSWERABLE, (TraceReason.SEGMENTS_UNAVAILABLE,)
    if comparison is Comparison.DESCRIBE:
        return verdict, ()
    if comparison is Comparison.RANK_OBJECTS:
        carrying = [m for m in measures if m in batteries and _primary(batteries[m]) >= 2]
        missing = TraceReason.COMPARISON_NEEDS_TRACKED_SET
    else:
        carrying = [
            m
            for m in measures
            if m in batteries
            and batteries[m].output_type == _CONCEPT_TEST
            and len(batteries[m].objects) >= 2
        ]
        missing = TraceReason.COMPARISON_NEEDS_CONCEPT_SET
    if not carrying:
        return Verdict.UNANSWERABLE, (missing,)
    # Only the measures that can carry the comparison answer it.
    return min((verdicts.get(m, Verdict.UNKNOWN) for m in carrying), key=_BEST.index), ()


def _links(spec: ResearchSpecification) -> dict[str, tuple[str, ...]]:
    """Every item id with the research questions it declares, a set's for each object."""
    out = {q.id: q.research_questions for q in spec.questions}
    for b in spec.batteries:
        for o in b.objects:
            out[b.question_id(o)] = b.research_questions
    return out


def trace_research(
    spec: ResearchSpecification,
    research_questions: Sequence[str],
    outlook: Sequence[QuestionOutlook],
    comparisons: Mapping[str, Comparison | None] | None = None,
) -> ResearchTrace:
    """Each of ``research_questions`` (as the analysis reads them: ``research_questions_of``)
    with the items of ``spec`` that measure it, judged by their ``outlook`` and by the
    comparison ``comparisons`` declares for it (:func:`comparisons_of`)."""
    declared = comparisons or {}
    batteries = _batteries(spec)
    links = _links(spec)
    verdicts = {o.question_id: o.verdict for o in outlook}
    stated = {_key(t): t for t in research_questions}
    linked = any(links.values())
    dangling = tuple(
        DanglingLink(question_id=item, research_question=rq)
        for item, rqs in links.items()
        for rq in rqs
        if _key(rq) not in stated
    )
    traces: list[ResearchQuestionTrace] = []
    for text in research_questions:
        measures = tuple(
            item for item, rqs in links.items() if any(_key(rq) == _key(text) for rq in rqs)
        )
        if measures:
            verdict = min((verdicts.get(m, Verdict.UNKNOWN) for m in measures), key=_BEST.index)
            reasons: tuple[TraceReason, ...] = ()
        elif linked:
            verdict, reasons = Verdict.UNANSWERABLE, (TraceReason.UNMEASURED,)
        else:
            verdict, reasons = Verdict.UNKNOWN, (TraceReason.UNLINKED_DESIGN,)
        comparison: Comparison | None = None
        if _key(text) in declared:
            comparison = declared[_key(text)]
            if comparison is None:
                verdict = _worse(verdict, Verdict.UNKNOWN)
                reasons = (*reasons, TraceReason.COMPARISON_UNKNOWN)
            else:
                judged, more = _judge(comparison, measures, verdict, verdicts, batteries)
                # Ranking or testing only through the set that carries it; anything the
                # comparison itself cannot be is never better than what measured it.
                verdict = judged if measures and not more else _worse(verdict, judged)
                reasons = (*reasons, *more)
        traces.append(
            ResearchQuestionTrace(
                text=text,
                measures=measures,
                verdict=verdict,
                reasons=reasons,
                comparison=comparison,
            )
        )
    return ResearchTrace(questions=tuple(traces), dangling=dangling, linked=linked)


#: A comparison its measures cannot carry, in the check's words, then the questions named.
_COMPARISON_WORDS: Final[dict[TraceReason, str]] = {
    TraceReason.COMPARISON_NEEDS_TRACKED_SET: (
        "Pořadí položek vyžaduje sledovanou sadu, ale žádná ji neměří: "
    ),
    TraceReason.COMPARISON_NEEDS_CONCEPT_SET: (
        "Test A/B vyžaduje sadu testu konceptů s alespoň dvěma koncepty: "
    ),
    TraceReason.SEGMENTS_UNAVAILABLE: (
        "Srovnání segmentů AIA zatím neumí: analýza nedostává žádnou segmentovou evidenci: "
    ),
    TraceReason.COMPARISON_UNKNOWN: "Neznámý způsob srovnání u: ",
}


def _check(trace: ResearchTrace) -> ReadinessCheck:
    def check(status: CheckStatus, message: str) -> ReadinessCheck:
        return ReadinessCheck(id=RESEARCH_TRACE_CHECK, status=status, message=message)

    if not trace.questions:
        return check(
            CheckStatus.WARN,
            "Návrh neuvádí žádnou výzkumnou otázku: modul výzkumných otázek nebude mít na co "
            "odpovědět a zablokuje se.",
        )
    if not trace.linked:
        return check(
            CheckStatus.WARN,
            "U žádné otázky není uvedeno, na kterou výzkumnou otázku odpovídá, takže nelze "
            "předem ověřit, že běh odpoví na všechny.",
        )
    unmeasured = [q.text for q in trace.questions if TraceReason.UNMEASURED in q.reasons]
    unanswered = [
        q.text
        for q in trace.questions
        if q.measures
        and q.verdict is Verdict.UNANSWERABLE
        and not set(q.reasons) & set(_COMPARISON_WORDS)
    ]
    parts: list[str] = []
    for reason, words in _COMPARISON_WORDS.items():
        named = [q.text for q in trace.questions if reason in q.reasons]
        if named:
            parts.append(words + "; ".join(named) + ".")
    if unmeasured:
        parts.append(
            "Na tyto výzkumné otázky žádná otázka neodpovídá: " + "; ".join(unmeasured) + "."
        )
    if unanswered:
        parts.append(
            "Tyto výzkumné otázky měří jen otázky, na které běh neodpoví: "
            + "; ".join(unanswered)
            + "."
        )
    if trace.dangling:
        parts.append(
            "Některé otázky odkazují na výzkumnou otázku, kterou plán neuvádí: "
            + "; ".join(sorted({d.research_question for d in trace.dangling}))
            + "."
        )
    if parts:
        return check(CheckStatus.WARN, " ".join(parts))
    return check(
        CheckStatus.PASS,
        f"Každou z {len(trace.questions)} výzkumných otázek měří alespoň jedna otázka.",
    )


def with_research_trace(readiness: Readiness, trace: ResearchTrace) -> Readiness:
    """``readiness`` with the trace's check after its own. It never FAILs: what to measure
    stays the person's call, and the analysis gate still decides after the run."""
    return Readiness(
        rules=readiness.rules,
        ready=readiness.ready,
        checks=(*readiness.checks, _check(trace)),
    )
