"""Technically runnable is not capable of answering (plan research-integrity-report chunk 1).

The fictional Fio run on develop (``RUN-9b6e0f5e6e0e4345``, 2026-10-16, 200 fictional
respondents) stated four research questions, linked none of them to a questionnaire item, and
started: readiness was ``ready`` because the research-question coverage check is a WARN. Its
analysis then could not answer three of them. These tests pin the decision that replaces the
WARN at the start: a run that cannot answer what it asks starts only with a person's
acknowledgement of exactly those gaps, recorded in the approval ledger and with the run, and a
retry inherits it only while the gaps are the same. All designs are fictional.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.research import ResearchQuestionsUnanswerable, ResearchRuns
from aia_core.domain.answerability import (
    ANSWERABILITY_RULES,
    Acknowledgement,
    AcknowledgementRefused,
    GapKind,
    GapReason,
    answerability,
    answerability_note,
    read_answerability_note,
)
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.question_outlook import Verdict, question_outlook
from aia_core.domain.research_design import compile_design
from aia_core.domain.research_trace import trace_research
from aia_core.domain.scope import WORKER_PERMISSIONS, ScopeDenied
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

AI = FieldworkSource.AI_RUNTIME
RQS = [
    "Jak klienti důvěřují digitálnímu běžnému účtu?",
    "Co klienty odrazuje od založení účtu online?",
    "Jak se liší důvěra mezi věkovými skupinami?",
    "Které značky klienti považují za nejbezpečnější?",
]


def _design(links: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """A fictional four-question study; ``links`` maps a question id to the RQs it measures."""
    questions: list[dict[str, Any]] = [
        {
            "id": "q1",
            "text": "Nakolik důvěřujete bankovnictví v mobilu?",
            "typ": "skala",
            "skala": [1, 5],
        },
        {
            "id": "q2",
            "text": "Co vás odrazuje od založení účtu online?",
            "typ": "vyber",
            "kategorie": ["Bezpečnost", "Složitost", "Nic"],
        },
    ]
    for q in questions:
        if links and links.get(q["id"]):
            q["research_questions"] = links[q["id"]]
    return {
        "title": "Důvěra v digitální účet (fiktivní)",
        "goal": "Pochopit důvěru v digitální běžný účet.",
        "n": 200,
        "research_plan": {"research_questions": list(RQS)},
        "sections": [{"type": "questions", "questions": questions}],
    }


FIO_LIKE = _design()  # four research questions, nothing linked
PARTLY = _design({"q1": [RQS[0]], "q2": [RQS[1]]})
COVERED = {
    **_design({"q1": [RQS[0], RQS[2]], "q2": [RQS[1], RQS[3]]}),
}


def _answer(content: dict[str, Any]) -> Any:
    spec, problems = compile_design(content)
    assert spec is not None, problems
    items = question_outlook(spec, None)
    trace = trace_research(spec, content["research_plan"]["research_questions"], items)
    return trace, answerability(trace, items)


# --------------------------------------------------------------------------- #
# The domain rule
# --------------------------------------------------------------------------- #


def test_an_unlinked_design_is_runnable_but_not_capable_of_answering() -> None:
    _trace, answer = _answer(FIO_LIKE)
    assert not answer.capable
    assert [g.research_question for g in answer.gaps] == RQS
    assert {g.reasons for g in answer.gaps} == {("unlinked_design",)}
    assert all(g.verdict is Verdict.UNKNOWN for g in answer.gaps)


def test_an_unmeasured_research_question_is_a_gap_and_a_measured_one_is_not() -> None:
    _trace, answer = _answer(PARTLY)
    assert [g.research_question for g in answer.gaps] == RQS[2:]
    assert all(
        g.kind is GapKind.NOT_ANSWERABLE and g.reasons == ("unmeasured",) for g in answer.gaps
    )


def test_support_decided_only_at_fieldwork_is_not_a_design_gap() -> None:
    # Without a forecast every measure is UNKNOWN (support_unknown): never scored as good,
    # and not a defect of the design either.
    trace, answer = _answer(COVERED)
    assert {q.verdict for q in trace.questions} == {Verdict.UNKNOWN}
    assert answer.capable and answer.gaps == ()
    # Never answerable either: the report names them as decided by fieldwork.
    assert answer.pending == tuple(RQS)


def test_a_question_measured_only_by_an_open_question_is_a_gap() -> None:
    """The analysis cites no open answer: the research questions module would have no number."""
    content = copy.deepcopy(PARTLY)
    content["sections"][0]["questions"].append(
        {
            "id": "q3",
            "text": "Co by vás přesvědčilo?",
            "typ": "otevrena",
            "research_questions": [RQS[2]],
        }
    )
    _trace, answer = _answer(content)
    gap = next(g for g in answer.gaps if g.research_question == RQS[2])
    assert gap.reasons == ("no_citable_measure",) and gap.measures == ("q3",)
    # No number to cite is known before the run: never "could answer it with risk".
    assert gap.verdict is Verdict.UNANSWERABLE


def test_a_question_measured_only_by_items_the_run_will_not_answer_names_why() -> None:
    content = copy.deepcopy(PARTLY)
    content["sections"][0]["questions"].append(
        {
            "id": "q3",
            "text": "Kolik byste zaplatil?",
            "typ": "skala",
            "skala": [1, 5],
            "filtr": {"q": "q1"},
            "research_questions": [RQS[2]],
        }
    )
    _trace, answer = _answer(content)
    gap = next(g for g in answer.gaps if g.research_question == RQS[2])
    assert gap.verdict is Verdict.UNANSWERABLE and gap.reasons == ("measures_unanswerable",)


def test_an_open_question_beside_one_the_run_will_not_answer_is_still_a_gap() -> None:
    """Review, 2026-10-16: the open question's AT_RISK was the trace's best verdict, so the
    research question passed with no measure the analysis could cite and the run answer."""
    content = copy.deepcopy(PARTLY)
    content["sections"][0]["questions"] += [
        {"id": "q3", "text": "Proč?", "typ": "otevrena", "research_questions": [RQS[2]]},
        # An item the run refuses to answer (an absolute willingness to pay): a conditional
        # one cannot show this, readiness refuses conditional questions first (review 3).
        {
            "id": "q4",
            "text": "Kolik Kč byste maximálně zaplatili za účet?",
            "typ": "skala",
            "skala": [1, 5],
            "research_questions": [RQS[2]],
        },
    ]
    trace, answer = _answer(content)
    spec, _ = compile_design(content)
    assert spec is not None
    (refused,) = (o for o in question_outlook(spec, None) if o.question_id == "q4")
    assert refused.verdict is Verdict.UNANSWERABLE
    assert "fidelity_refused" in [r.value for r in refused.reasons]
    assert next(q for q in trace.questions if q.text == RQS[2]).verdict is Verdict.AT_RISK
    gap = next(g for g in answer.gaps if g.research_question == RQS[2])
    assert gap.verdict is Verdict.UNANSWERABLE and gap.reasons == ("measures_unanswerable",)
    assert gap.measures == ("q3", "q4")


def test_support_left_to_fieldwork_is_pending_even_beside_an_open_question() -> None:
    """The open question's AT_RISK must not lift a citable measure's unknown support."""
    content = copy.deepcopy(COVERED)
    content["sections"][0]["questions"].append(
        {"id": "q3", "text": "Proč?", "typ": "otevrena", "research_questions": [RQS[0]]}
    )
    trace, answer = _answer(content)
    assert next(q for q in trace.questions if q.text == RQS[0]).verdict is Verdict.AT_RISK
    assert answer.capable and RQS[0] in answer.pending


def test_every_gap_carries_a_reason() -> None:
    for design in (FIO_LIKE, PARTLY):
        assert all(g.reasons for g in _answer(design)[1].gaps)


def test_the_web_words_exactly_the_reasons_a_gap_can_have() -> None:
    # The Run screen words each reason (apps/web/src/lib/answerability.ts GAP_REASONS, each with
    # its words, answerability.test.ts); a reason added here without words there would print a
    # placeholder where a researcher needs the cause.
    source = (Path(__file__).resolve().parents[3] / "apps/web/src/lib/answerability.ts").read_text(
        "utf-8"
    )
    listed = re.search(r"GAP_REASONS = \[(.*?)\] as const", source, re.S)
    assert listed is not None
    assert re.findall(r'"([a-z_]+)"', listed.group(1)) == [r.value for r in GapReason]


def test_a_design_with_no_research_question_is_one_gap() -> None:
    content = copy.deepcopy(FIO_LIKE)
    spec, _ = compile_design(content)
    assert spec is not None
    answer = answerability(trace_research(spec, [], question_outlook(spec, None)))
    assert not answer.capable
    assert [g.kind for g in answer.gaps] == [GapKind.NO_RESEARCH_QUESTIONS]


def test_the_digest_names_the_exact_gaps() -> None:
    _, fio = _answer(FIO_LIKE)
    _, partly = _answer(PARTLY)
    assert fio.digest != partly.digest
    assert _answer(FIO_LIKE)[1].digest == fio.digest


def test_an_acknowledgement_needs_a_reason_and_covers_only_its_gaps() -> None:
    _, fio = _answer(FIO_LIKE)
    _, partly = _answer(PARTLY)
    with pytest.raises(AcknowledgementRefused):
        Acknowledgement(digest=fio.digest, reason="  ok  ")
    ack = Acknowledgement(digest=fio.digest, reason="Ověřujeme jen postup,   ne závěry.")
    assert ack.reason == "Ověřujeme jen postup, ne závěry."
    assert ack.covers(fio) and not ack.covers(partly)


def test_the_note_records_every_question_and_reads_back() -> None:
    trace, answer = _answer(PARTLY)
    note = answerability_note(
        trace,
        answer,
        acknowledged_by="u1",
        acknowledgement=Acknowledgement(digest=answer.digest, reason="Pilotní ověření postupu."),
    )
    assert note["rules"] == ANSWERABILITY_RULES and note["capable"] is False
    assert [q["text"] for q in note["research_questions"]] == RQS
    assert note["research_questions"][0]["measures"] == ["q1"]
    assert note["acknowledgement"] == {"reason": "Pilotní ověření postupu.", "by": "u1"}
    assert read_answerability_note({"answerability": note}) == note
    assert read_answerability_note({}) is None
    assert read_answerability_note({"answerability": {**note, "rules": "other"}}) is None


# --------------------------------------------------------------------------- #
# The start
# --------------------------------------------------------------------------- #


@pytest.fixture
def runs(session: Any, scoped: Any) -> Any:
    return lambda **kw: ResearchRuns(session, scoped.scope(**kw))


@pytest.fixture
def design(session: Any, scoped: Any) -> Any:
    def submit(content: dict[str, Any]) -> str:
        repo = StudyDesignRepository(session, scoped.scope(user="lead"))
        revision, _ = repo.submit(content=content, source_stage="run")
        return revision.revision_id

    return submit


def _rows(session: Any) -> list[Any]:
    return list(
        session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "answerability")
        ).all()
    )


def _start(runs: Any, revision: str, **kw: Any) -> Any:
    return runs(user="researcher").start(
        design_revision_id=revision, fieldwork_source=AI, require_answerability=True, **kw
    )


def test_a_start_that_cannot_answer_its_questions_is_refused_and_creates_nothing(
    session: Any, runs: Any, design: Any
) -> None:
    revision = design(FIO_LIKE)
    with pytest.raises(ResearchQuestionsUnanswerable) as refused:
        _start(runs, revision)
    assert [g.research_question for g in refused.value.answerability.gaps] == RQS
    assert runs(user="researcher").runs() == []
    assert _rows(session) == []


def test_readiness_says_ready_and_not_capable_side_by_side(runs: Any, design: Any) -> None:
    outlook = runs(user="researcher").outlook(design(FIO_LIKE), fieldwork_source=AI)
    assert outlook.readiness.ready is True
    assert outlook.answerability is not None and outlook.answerability.capable is False


def test_an_acknowledged_start_records_the_gaps_who_and_why(
    session: Any, runs: Any, design: Any
) -> None:
    revision = design(FIO_LIKE)
    digest = runs(user="researcher").outlook(revision, fieldwork_source=AI).answerability.digest
    ack = Acknowledgement(digest=digest, reason="Fiktivní test postupu; závěry nečteme.")
    started = _start(runs, revision, acknowledge=ack)
    assert started.created
    meta = runs(user="researcher").get(started.run_id)["metadata"]
    note = read_answerability_note(meta)
    assert note is not None and note["capable"] is False and note["digest"] == digest
    assert note["acknowledgement"]["reason"] == ack.reason
    assert note["acknowledgement"]["by"]
    (row,) = _rows(session)
    assert row.run_id == started.run_id and row.decision == "acknowledge"
    comment = json.loads(row.comment)
    assert comment["digest"] == digest and len(comment["gaps"]) == 4
    # Self-contained: what the gaps were computed under, by name.
    assert comment["rules"] == ANSWERABILITY_RULES and comment["design_revision_id"] == revision


def test_an_acknowledgement_of_other_gaps_is_not_one(runs: Any, design: Any) -> None:
    other = runs(user="researcher").outlook(design(PARTLY), fieldwork_source=AI).answerability
    with pytest.raises(ResearchQuestionsUnanswerable):
        _start(
            runs,
            design(FIO_LIKE),
            acknowledge=Acknowledgement(digest=other.digest, reason="Jiné mezery, jiný návrh."),
        )


def test_a_capable_design_starts_without_asking_and_records_that(
    session: Any, runs: Any, design: Any
) -> None:
    started = _start(runs, design(COVERED))
    note = read_answerability_note(runs(user="researcher").get(started.run_id)["metadata"])
    assert note is not None and note["capable"] is True and "acknowledgement" not in note
    assert _rows(session) == []


def test_with_the_gate_off_a_run_with_gaps_starts_and_says_so(runs: Any, design: Any) -> None:
    started = runs(user="researcher").start(
        design_revision_id=design(FIO_LIKE), fieldwork_source=AI
    )
    note = read_answerability_note(runs(user="researcher").get(started.run_id)["metadata"])
    assert note is not None and note["capable"] is False and note["enforced"] is False


def test_a_retry_inherits_the_acknowledgement_of_the_same_gaps(
    session: Any, runs: Any, design: Any
) -> None:
    revision = design(FIO_LIKE)
    digest = runs(user="researcher").outlook(revision, fieldwork_source=AI).answerability.digest
    first = _start(
        runs, revision, acknowledge=Acknowledgement(digest=digest, reason="Pilotní test postupu.")
    )
    runs(user="researcher").cancel(first.run_id)
    retried = runs(user="researcher").retry(
        first.run_id, fieldwork_source=AI, require_answerability=True
    )
    note = read_answerability_note(runs(user="researcher").get(retried.run_id)["metadata"])
    assert note is not None
    assert note["acknowledgement"]["inherited_from"] == first.run_id
    assert note["acknowledgement"]["reason"] == "Pilotní test postupu."
    assert len(_rows(session)) == 1  # the person decided once


def test_a_retry_of_a_run_started_before_the_gate_asks(runs: Any, design: Any) -> None:
    # The Fio run itself: started with gaps and no acknowledgement.
    first = runs(user="researcher").start(design_revision_id=design(FIO_LIKE), fieldwork_source=AI)
    runs(user="researcher").cancel(first.run_id)
    with pytest.raises(ResearchQuestionsUnanswerable):
        runs(user="researcher").retry(first.run_id, fieldwork_source=AI, require_answerability=True)


def test_an_analysis_retry_is_never_refused_and_says_it_was_exempt(runs: Any, design: Any) -> None:
    from aia_core.application.research import FrozenDataset

    first = runs(user="researcher").start(
        design_revision_id=design(FIO_LIKE), fieldwork_source=AI, analysis_enabled=True
    )
    frozen = FrozenDataset(
        run_id=first.run_id,
        artifact_id="ART-dataset",
        sha256="a" * 64,
        analysis_round=1,
        retried=("research_questions",),
        modules_asked=1,
    )
    retried = runs(user="researcher").start(
        design_revision_id=runs(user="researcher").get(first.run_id)["metadata"][
            "design_revision_id"
        ],
        fieldwork_source=AI,
        analysis_enabled=True,
        retry_of=first.run_id,
        frozen_dataset=frozen,
        require_answerability=True,
    )
    note = read_answerability_note(runs(user="researcher").get(retried.run_id)["metadata"])
    assert note is not None and note["capable"] is False
    assert note["exempt"] == "analysis_retry" and "enforced" not in note


def test_the_worker_cannot_acknowledge_a_design(
    session: Any, scoped: Any, runs: Any, design: Any
) -> None:
    started = _start(runs, design(COVERED))
    worker = dataclasses.replace(scoped.scope(user="researcher"), permissions=WORKER_PERMISSIONS)
    with pytest.raises(ScopeDenied):
        WorkflowRepository(session, worker).record_answerability_acknowledgement(
            started.run_id,
            digest="0" * 64,
            reason="nelze",
            gaps=[],
            rules="aia-answerability-1",
            design_revision_id="REV-0",
        )


# Review of the branch, 2026-10-16.


def test_an_acknowledgement_read_for_one_revision_never_covers_another() -> None:
    spec, _ = compile_design(FIO_LIKE)
    assert spec is not None
    items = question_outlook(spec, None)
    trace = trace_research(spec, RQS, items)
    first = answerability(trace, items, design_revision_id="REV-1")
    second = answerability(trace, items, design_revision_id="REV-2")
    assert first.gaps == second.gaps and first.digest != second.digest
    assert not Acknowledgement(digest=first.digest, reason="Ověřujeme jen postup.").covers(second)


def test_every_research_question_records_the_verdict_decided_for_it() -> None:
    """The decided verdict, never the trace's: a question only an open item measures is AT_RISK
    by the trace and UNANSWERABLE by the decision (review 3: the test could not tell them apart)."""
    content = copy.deepcopy(PARTLY)
    content["sections"][0]["questions"].append(
        {"id": "q3", "text": "Proč?", "typ": "otevrena", "research_questions": [RQS[2]]}
    )
    trace, answer = _answer(content)
    decided = dict(answer.verdicts)
    assert set(decided) == set(RQS)
    assert decided[RQS[2]] is Verdict.UNANSWERABLE
    note = answerability_note(trace, answer)
    row = next(r for r in note["research_questions"] if r["text"] == RQS[2])
    assert row["verdict"] == "UNANSWERABLE" and row["trace_verdict"] == "AT_RISK"


def test_an_unknown_comparison_never_hides_that_nothing_measures_it_citably() -> None:
    """Review 3: a trace reason (an unknown comparison) skipped the measure checks, so a
    question measured only by an open item read UNKNOWN instead of UNANSWERABLE."""
    from aia_core.domain.research_trace import comparisons_of

    rq = RQS[0]
    content = {
        **copy.deepcopy(PARTLY),
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {"id": "q1", "text": "Proč?", "typ": "otevrena", "research_questions": [rq]}
                ],
            }
        ],
        "research_plan": {
            "research_questions": [rq],
            "research_question_comparisons": {rq: "cluster"},
        },
    }
    spec, problems = compile_design(content)
    assert spec is not None, problems
    items = question_outlook(spec, None)
    trace = trace_research(spec, [rq], items, comparisons_of(content))
    (gap,) = answerability(trace, items).gaps
    assert gap.verdict is Verdict.UNANSWERABLE
    assert gap.reasons == ("comparison_unknown", "no_citable_measure")


def test_a_ranking_whose_set_the_run_will_not_answer_says_so() -> None:
    """Not "measured only by questions the run will not answer": another measure is answered.
    The trace (research_trace._judge) calls such a ranking UNANSWERABLE with no reason of its
    own when its carrying set is not answered as a whole."""
    from aia_core.domain.question_outlook import OutlookReason, QuestionOutlook
    from aia_core.domain.research_trace import Comparison, ResearchQuestionTrace, ResearchTrace

    rq = "Které značky lidé preferují?"
    measures = ("q9", "b1_a", "b1_b")
    trace = ResearchTrace(
        questions=(
            ResearchQuestionTrace(
                text=rq,
                measures=measures,
                verdict=Verdict.UNANSWERABLE,
                reasons=(),
                comparison=Comparison.RANK_OBJECTS,
            ),
        ),
        dangling=(),
        linked=True,
    )
    outlook = (
        QuestionOutlook("q9", "Nakolik?", "s1", None, Verdict.ANSWERABLE, ()),
        *(
            QuestionOutlook(m, m, "s2", "b1", Verdict.UNANSWERABLE, (OutlookReason.FAMILIARITY,))
            for m in measures[1:]
        ),
    )
    (gap,) = answerability(trace, outlook).gaps
    assert gap.reasons == ("comparison_set_unanswerable",)
    # With nothing answered at all, it is what measures it that the run will not answer.
    unanswered = (
        QuestionOutlook("q9", "Nakolik?", "s1", None, Verdict.UNANSWERABLE, ()),
        *outlook[1:],
    )
    (gap,) = answerability(trace, unanswered).gaps
    assert gap.reasons == ("measures_unanswerable",)


def test_readiness_shows_one_verdict_and_never_passes_beside_a_gap() -> None:
    from aia_core.domain.answerability import decided_trace, with_answerability
    from aia_core.domain.research_design import CheckStatus
    from aia_core.domain.research_trace import RESEARCH_TRACE_CHECK, with_research_trace

    content = copy.deepcopy(COVERED)
    content["sections"][0]["questions"][0]["research_questions"] = [RQS[0]]
    content["sections"][0]["questions"].append(
        {"id": "q3", "text": "Proč?", "typ": "otevrena", "research_questions": [RQS[2]]}
    )
    from aia_core.domain.research_design import prepare

    spec, readiness = prepare(content, pair_n_min=30)
    assert spec is not None
    items = question_outlook(spec, None)
    trace = trace_research(spec, content["research_plan"]["research_questions"], items)
    answer = answerability(trace, items)
    shown = decided_trace(trace, answer)
    gap = next(g for g in answer.gaps if g.research_question == RQS[2])
    assert next(q for q in shown.questions if q.text == RQS[2]).verdict is gap.verdict
    checked = with_answerability(with_research_trace(readiness, trace), answer)
    check = next(c for c in checked.checks if c.id == RESEARCH_TRACE_CHECK)
    assert check.status is CheckStatus.WARN and RQS[2] in check.message
