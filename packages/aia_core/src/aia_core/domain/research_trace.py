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
says which question answers what. Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .question_outlook import QuestionOutlook, Verdict
from .research_design import CheckStatus, Readiness, ReadinessCheck, ResearchSpecification

__all__ = [
    "RESEARCH_TRACE_CHECK",
    "DanglingLink",
    "ResearchQuestionTrace",
    "ResearchTrace",
    "TraceReason",
    "trace_research",
    "with_research_trace",
]

#: The readiness check this module adds.
RESEARCH_TRACE_CHECK: Final = "research_question_coverage"

#: Best first: a research question is as answerable as its best measure.
_BEST: Final = (Verdict.ANSWERABLE, Verdict.AT_RISK, Verdict.UNKNOWN, Verdict.UNANSWERABLE)


class TraceReason(StrEnum):
    #: No question or tracked set declares that it measures this research question.
    UNMEASURED = "unmeasured"
    #: The design declares no link at all, so nothing says what measures this one.
    UNLINKED_DESIGN = "unlinked_design"


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
) -> ResearchTrace:
    """Each of ``research_questions`` (as the analysis reads them: ``research_questions_of``)
    with the items of ``spec`` that measure it, judged by their ``outlook``."""
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
        traces.append(
            ResearchQuestionTrace(text=text, measures=measures, verdict=verdict, reasons=reasons)
        )
    return ResearchTrace(questions=tuple(traces), dangling=dangling, linked=linked)


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
        q.text for q in trace.questions if q.measures and q.verdict is Verdict.UNANSWERABLE
    ]
    parts: list[str] = []
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
