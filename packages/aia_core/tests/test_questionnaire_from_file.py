"""A questionnaire table given to the Lead, made a proposal (lead-orchestration LO18b).

Nahradit replaces the question sections as an AI build does; Doplnit adds only what is not there;
imported ids never collide with the copy's; nothing is asked of a copy with no questions.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.questionnaire_from_file import (
    IMPORT_MAX_BYTES,
    ImportMode,
    ImportTooLarge,
    has_question_sections,
    import_proposal,
)


def _q(qid: str, text: str, section: str) -> dict[str, Any]:
    return {"id": qid, "text": text, "typ": "skala", "metadata": {"research_section": section}}


INSTRUMENT = {
    "id": "nps",
    "type": "questions",
    "title": "NPS",
    "metadata": {"standard_instrument": True},
    "questions": [_q("nps_q", "Doporučil byste nás?", "nps")],
}
EXISTING = {
    "id": "sec_import_1",
    "type": "questions",
    "title": "Nákupní záměr",
    "questions": [_q("q1", "Jak pravděpodobně koupíte?", "sec_import_1")],
}
BATTERY = {"id": "obj_media", "type": "object_battery", "title": "Média", "objects": ["TV"]}


def _imported() -> list[dict[str, Any]]:
    return [
        {
            "id": "sec_import_1",
            "type": "questions",
            "title": "nákupní  ZÁMĚR",
            "questions": [
                _q("q1", "Jak  pravděpodobně koupíte?", "sec_import_1"),
                _q("q2", "Kolik byste zaplatil?", "sec_import_1"),
            ],
        },
        {
            "id": "sec_import_2",
            "type": "questions",
            "title": "Bariéry",
            "questions": [_q("q3", "Co vám brání?", "sec_import_2")],
        },
        {"id": "obj_media", "type": "object_battery", "title": "média", "objects": ["Rádio"]},
        {"id": "obj_znacky", "type": "object_battery", "title": "Značky", "objects": ["A"]},
    ]


def _ids(sections: list[dict[str, Any]]) -> list[str]:
    return [s["id"] for s in sections] + [q["id"] for s in sections for q in s.get("questions", [])]


def test_a_copy_without_questions_is_never_asked() -> None:
    assert not has_question_sections({"sections": [INSTRUMENT]})
    assert not has_question_sections({})
    assert has_question_sections({"sections": [EXISTING]})
    assert has_question_sections({"sections": [BATTERY]})


def test_nahradit_replaces_the_question_sections_and_keeps_an_instrument() -> None:
    baseline = {"title": "S", "sections": [INSTRUMENT, EXISTING, BATTERY]}
    result = import_proposal(baseline, _imported(), ImportMode.REPLACE)
    sections = result["project"]["sections"]
    assert sections[0] == INSTRUMENT
    assert [s["title"] for s in sections[1:]] == ["nákupní  ZÁMĚR", "Bariéry", "média", "Značky"]
    assert len(set(_ids(sections))) == len(_ids(sections))
    assert result["proposal"]["mode"] == "replace" and len(result["proposal"]["sections"]) == 4
    # The baseline itself is untouched.
    assert baseline["sections"] == [INSTRUMENT, EXISTING, BATTERY]


def test_doplnit_adds_only_what_is_not_there() -> None:
    baseline = {"sections": [INSTRUMENT, EXISTING, BATTERY]}
    sections = import_proposal(baseline, _imported(), ImportMode.ADD)["project"]["sections"]
    texts = [q["text"] for s in sections for q in s.get("questions", [])]
    # The same wording (case and spaces folded) is there already; the new question joins the
    # section of the same title, under the copy's own section id.
    assert texts.count("Jak pravděpodobně koupíte?") == 1
    assert "Jak  pravděpodobně koupíte?" not in texts
    home = next(s for s in sections if s["title"] == "Nákupní záměr")
    assert [q["text"] for q in home["questions"]] == [
        "Jak pravděpodobně koupíte?",
        "Kolik byste zaplatil?",
    ]
    assert home["questions"][1]["metadata"]["research_section"] == home["id"]
    # A new section of its own, and the tracked set only when no set has its title.
    assert [s["title"] for s in sections] == ["NPS", "Nákupní záměr", "Média", "Bariéry", "Značky"]
    assert len(set(_ids(sections))) == len(_ids(sections))


def test_doplnit_never_adds_into_a_standard_instrument() -> None:
    imported = [
        {
            "id": "sec_import_1",
            "type": "questions",
            "title": "nps",
            "questions": [_q("q9", "Co byste zlepšili?", "sec_import_1")],
        }
    ]
    sections = import_proposal({"sections": [INSTRUMENT]}, imported, ImportMode.ADD)["project"][
        "sections"
    ]
    assert sections[0] == INSTRUMENT
    assert [q["text"] for q in sections[1]["questions"]] == ["Co byste zlepšili?"]
    assert sections[1]["id"] != INSTRUMENT["id"]


def test_doplnit_with_everything_there_changes_nothing() -> None:
    baseline = {"sections": [EXISTING]}
    imported = [{**EXISTING, "questions": [dict(EXISTING["questions"][0])]}]
    assert import_proposal(baseline, imported, ImportMode.ADD)["project"] == baseline


def test_an_import_over_the_bound_is_refused_by_name() -> None:
    big = [{"id": "s", "type": "questions", "title": "x" * (IMPORT_MAX_BYTES + 1), "questions": []}]
    with pytest.raises(ImportTooLarge) as refused:
        import_proposal({}, big, ImportMode.REPLACE)
    assert refused.value.reason == "questionnaire_too_large"
