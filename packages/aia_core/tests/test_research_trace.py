"""Each research question traced to what measures it, before a run (plan
run-recovery-and-truth 3a)."""

from __future__ import annotations

import copy
from typing import Any

from aia_core.domain.analysis.native import research_questions_of
from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.fieldwork import PersonaSource
from aia_core.domain.question_outlook import Verdict, question_outlook
from aia_core.domain.research_design import CheckStatus, assess_readiness, compile_design
from aia_core.domain.research_trace import (
    RESEARCH_TRACE_CHECK,
    TraceReason,
    trace_research,
    with_research_trace,
)
from aia_core.domain.support_forecast import forecast_support

RQ_HABIT = "Jak často lidé pijí kávu?"
RQ_PRICE = "Kolik by lidé za kávu zaplatili?"
RQ_IMAGE = "Jak lidé vnímají ranní nápoje?"

#: Three research questions: one measured, one measured only by a refused question, one by a set.
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "n": 400,
    "research_plan": {"research_questions": [RQ_HABIT, RQ_PRICE, RQ_IMAGE]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často pijete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "research_questions": [RQ_HABIT],
                },
                {
                    "id": "q2",
                    "text": "Kolik Kč byste maximálně zaplatili za kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "research_questions": [f"  {RQ_PRICE}  "],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
            "research_questions": [RQ_IMAGE],
        },
    ],
}


#: The fingerprint of DESIGN without its links, as the compiler before 3a computed it.
UNLINKED_FINGERPRINT = "cbb4709a8e613fe48f517e04606880065645fdc1ff1338be5b0b3ab5167a053f"


def _compile(design: dict[str, Any]) -> Any:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


def _trace(design: dict[str, Any]) -> Any:
    spec = _compile(design)
    forecast = forecast_support(
        spec, support=AIA_SUPPORT_V1, persona_source=PersonaSource.FICTIONAL_ROSTER
    )
    return trace_research(spec, research_questions_of(design), question_outlook(spec, forecast))


def _check(design: dict[str, Any]) -> Any:
    spec = _compile(design)
    readiness = with_research_trace(assess_readiness(spec, pair_n_min=30), _trace(design))
    return next(c for c in readiness.checks if c.id == RESEARCH_TRACE_CHECK)


def test_a_link_is_compiled_as_declared_and_an_undeclared_one_keeps_the_fingerprint() -> None:
    spec = _compile(DESIGN)
    assert spec.questions[0].research_questions == (RQ_HABIT,)
    assert spec.questions[1].research_questions == (RQ_PRICE,)  # whitespace collapsed
    assert spec.batteries[0].research_questions == (RQ_IMAGE,)

    unlinked = copy.deepcopy(DESIGN)
    for section in unlinked["sections"]:
        section.pop("research_questions", None)
        for q in section.get("questions", []):
            q.pop("research_questions", None)
    plain = _compile(unlinked)
    # What this design compiled to before links existed (computed at 2b's head, aabe3bc2).
    assert plain.fingerprint() == UNLINKED_FINGERPRINT
    # An empty declaration is no declaration: the fingerprint a design always had.
    empty = copy.deepcopy(unlinked)
    empty["sections"][0]["questions"][0]["research_questions"] = []
    assert _compile(empty).fingerprint() == plain.fingerprint()
    assert spec.fingerprint() != plain.fingerprint()


def test_a_link_that_is_not_a_list_of_texts_is_a_problem_never_guessed() -> None:
    bad = copy.deepcopy(DESIGN)
    bad["sections"][0]["questions"][0]["research_questions"] = RQ_HABIT
    spec, problems = compile_design(bad)
    assert spec is None
    assert [p.code for p in problems] == ["invalid_research_question_links"]


def test_each_research_question_is_as_answerable_as_its_best_measure() -> None:
    trace = _trace(DESIGN)
    by_text = {q.text: q for q in trace.questions}
    assert by_text[RQ_HABIT].measures == ("q1",)
    assert by_text[RQ_HABIT].verdict is Verdict.ANSWERABLE
    assert by_text[RQ_PRICE].verdict is Verdict.UNANSWERABLE  # its one measure is refused
    assert len(by_text[RQ_IMAGE].measures) == 5  # every object of the set
    assert trace.linked and trace.dangling == ()

    check = _check(DESIGN)
    assert check.status is CheckStatus.WARN
    assert RQ_PRICE in check.message and RQ_HABIT not in check.message


def test_a_research_question_nothing_measures_is_unanswerable_and_named() -> None:
    design = copy.deepcopy(DESIGN)
    design["sections"][1].pop("research_questions")
    trace = _trace(design)
    image = next(q for q in trace.questions if q.text == RQ_IMAGE)
    assert image.measures == ()
    assert image.verdict is Verdict.UNANSWERABLE
    assert image.reasons == (TraceReason.UNMEASURED,)
    assert RQ_IMAGE in _check(design).message


def test_a_link_to_a_research_question_the_plan_does_not_state_is_listed_apart() -> None:
    design = copy.deepcopy(DESIGN)
    design["research_plan"]["research_questions"] = [RQ_HABIT, RQ_IMAGE]
    trace = _trace(design)
    assert [(d.question_id, d.research_question) for d in trace.dangling] == [("q2", RQ_PRICE)]
    assert "neuvádí" in _check(design).message


def test_coverage_is_unknown_without_links_and_passes_only_when_every_question_is_measured() -> (
    None
):
    unlinked = copy.deepcopy(DESIGN)
    for section in unlinked["sections"]:
        section.pop("research_questions", None)
        for q in section.get("questions", []):
            q.pop("research_questions", None)
    trace = _trace(unlinked)
    assert not trace.linked
    assert {q.verdict for q in trace.questions} == {Verdict.UNKNOWN}
    assert all(q.reasons == (TraceReason.UNLINKED_DESIGN,) for q in trace.questions)
    assert _check(unlinked).status is CheckStatus.WARN

    covered = copy.deepcopy(DESIGN)
    covered["research_plan"]["research_questions"] = [RQ_HABIT, RQ_IMAGE]
    covered["sections"][0]["questions"][1].pop("research_questions")
    assert _check(covered).status is CheckStatus.PASS

    nothing = copy.deepcopy(covered)
    nothing.pop("research_plan")
    nothing.pop("title")
    assert research_questions_of(nothing) == ()
    assert _check(nothing).status is CheckStatus.WARN


def test_a_question_whose_id_is_a_set_items_id_is_refused_not_merged() -> None:
    """Review (Codex on #421): a question with a set item's id would share that item's
    answers and its links; the compiler refuses it by name instead."""
    design = copy.deepcopy(DESIGN)
    design["sections"][1]["id"] = "set"
    design["sections"][0]["questions"][0]["id"] = "set_obj_kava"
    spec, problems = compile_design(design)
    assert spec is None
    assert [(p.code, p.where) for p in problems] == [("item_id_collision", "set_obj_kava")]
