"""A scale's labels on every point survive every rewrite of the questionnaire (#559 review).

Every contract that writes a questionnaire carries a scale's two ends only (an agent's
``Question.popisky_skaly``, the classic optimiser's schema), so a rewrite would drop the inner
labels a person gave every point without a word. ``keep_point_labels`` keeps them; the agent's
proposal and the accept's merge both go through it.
"""

from __future__ import annotations

import copy
from typing import Any

from aia_core.domain.design_items import Documents, design_items, merge_items
from aia_core.domain.research_agents import (
    QuestionnaireProposal,
    ResearchAction,
    context_snapshot,
    proposal_result,
)
from aia_core.domain.research_design import keep_point_labels

POINTS = ["vůbec", "spíše ne", "nevím", "spíše ano", "zcela"]
TEXT = "Jak moc vás produkt zaujal?"


def _scale(
    qid: str | None, text: str, labels: list[str], scale: list[int] | None = None
) -> dict[str, Any]:
    q: dict[str, Any] = {"text": text, "typ": "skala", "skala": scale or [1, 5]}
    if qid is not None:
        q["id"] = qid
    q["popisky_skaly"] = labels
    return q


def _sections(*questions: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"id": "s1", "type": "questions", "title": "A", "questions": list(questions)}]


def _labels(sections: Any, i: int = 0) -> Any:
    return sections[0]["questions"][i]["popisky_skaly"]


STORED = _sections(_scale("Q1", TEXT, POINTS))


def test_kept_by_id_by_wording_and_by_the_two_ends() -> None:
    by_id = keep_point_labels(_sections(_scale("Q1", "Jiné znění?", ["a", "b"])), STORED)
    assert _labels(by_id) == POINTS
    by_text = keep_point_labels(
        _sections(_scale("ai_q_1_1", f"  {TEXT.upper()} ", ["a", "b"])), STORED
    )
    assert _labels(by_text) == POINTS
    by_ends = keep_point_labels(_sections(_scale("ai_q_1_1", "Jiné?", ["Vůbec", "ZCELA"])), STORED)
    assert _labels(by_ends) == POINTS
    absent = keep_point_labels(
        _sections({"id": "Q1", "text": TEXT, "typ": "skala", "skala": [1, 5]}), STORED
    )
    assert _labels(absent) == POINTS
    assert _labels(STORED) == POINTS  # nothing written into the stored copy


def test_left_as_written_when_nothing_or_more_than_one_matches() -> None:
    other_range = _sections(_scale("Q1", TEXT, ["a", "b"], [1, 7]))
    assert keep_point_labels(other_range, STORED) == other_range
    unmatched = _sections(_scale("ai_q", "Jiné?", ["nízké", "vysoké"]))
    assert keep_point_labels(unmatched, STORED) == unmatched
    rewritten_points = _sections(_scale("Q1", TEXT, ["1", "2", "3", "4", "5"]))
    assert keep_point_labels(rewritten_points, STORED) == rewritten_points
    again = _scale("Q9", TEXT, list(reversed(POINTS)))
    twice = [*STORED, {"id": "s2", "type": "questions", "questions": [again]}]
    by_text = _sections(_scale("ai_q", TEXT, ["a", "b"]))
    assert keep_point_labels(by_text, twice) == by_text
    not_scale = _sections({"id": "Q1", "text": TEXT, "typ": "otevrena"})
    assert keep_point_labels(not_scale, STORED) == not_scale


def test_only_valid_labels_on_every_point_are_kept() -> None:
    rewrite = _sections(_scale("Q1", TEXT, ["a", "b"]))
    for stored in (["a", "", "c", "d", "e"], ["a", "A", "c", "d", "e"], ["a", "b", "c"]):
        assert keep_point_labels(rewrite, _sections(_scale("Q1", TEXT, stored))) == rewrite
    decimal = _sections(_scale("Q1", TEXT, POINTS, [1, 5]))
    decimal[0]["questions"][0]["skala"] = [1.0, 5]
    assert keep_point_labels(rewrite, decimal) == rewrite


def _proposal(text: str, labels: list[str]) -> QuestionnaireProposal:
    return QuestionnaireProposal.model_validate(
        {
            "message": "Návrh",
            "warnings": [],
            "sections": [
                {
                    "type": "questions",
                    "title": "Zájem",
                    "purpose": "Koncept",
                    "questions": [
                        {
                            "text": text,
                            "typ": "skala",
                            "kategorie": [],
                            "skala": [1, 5],
                            "popisky_skaly": labels,
                            "povolit_nevim": False,
                            "max_slov": 20,
                            "topics": [],
                            "research_questions": [],
                        }
                    ],
                }
            ],
            "comparisons": [],
        }
    )


def test_an_optimised_questionnaire_keeps_the_baseline_s_labels_on_every_point() -> None:
    baseline = {"title": "Fictional", "goal": "Test", "sections": STORED}
    result = proposal_result(
        ResearchAction.OPTIMIZE,
        baseline,
        _proposal(TEXT, ["vůbec", "zcela"]),
        context_snapshot(baseline, []),
    )
    assert _labels(result["project"]["sections"]) == POINTS
    # The proposal as the model wrote it is kept as written: only the design keeps the labels.
    assert result["proposal"]["sections"][0]["questions"][0]["popisky_skaly"] == ["vůbec", "zcela"]


def test_a_built_questionnaire_with_new_scales_is_left_as_written() -> None:
    baseline = {"title": "Fictional", "goal": "Test", "sections": STORED}
    result = proposal_result(
        ResearchAction.BUILD,
        baseline,
        _proposal("Úplně jiná otázka?", ["nízké", "vysoké"]),
        context_snapshot(baseline, []),
    )
    assert _labels(result["project"]["sections"]) == ["nízké", "vysoké"]


def test_an_accepted_proposal_keeps_the_person_s_labels_on_every_point() -> None:
    """A proposal made before the fix (or by any writer whose contract has two ends) is
    accepted without dropping them: the merge keeps the person's labels."""
    base = Documents(content={"title": "Fictional", "sections": STORED})
    proposed = copy.deepcopy(base.content)
    question = proposed["sections"][0]["questions"][0]
    question["text"] = "Jak moc vás zaujal?"
    question["popisky_skaly"] = ["vůbec", "zcela"]
    touched = design_items(base, Documents(content=proposed))
    merged = merge_items(Documents(content=proposed), base, touched, baseline=base)
    q = merged.content["sections"][0]["questions"][0]
    assert q["text"] == "Jak moc vás zaujal?"
    assert q["popisky_skaly"] == POINTS
