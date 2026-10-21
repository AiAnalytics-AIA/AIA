"""The internal report's design chapter and questionnaire appendix (complete-study-report B1b)."""

from __future__ import annotations

from typing import Any

from aia_core.application.report_design import compose_design_sections
from aia_core.application.report_tables import scale_notes
from aia_core.domain.report.model import BulletList, Paragraph, Text
from aia_core.domain.research_design import compile_design

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 300,
    "audience": {
        "strategy": "filters",
        "source_mode": "population",
        "filters": {"vek": {"min": 25, "max": 55}, "kraj": ["Praha"]},
    },
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
                {"id": "q3", "text": "Proč?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


def _words(blocks: Any) -> str:
    out: list[str] = []
    for b in blocks:
        if isinstance(b, Paragraph):
            out.append("".join(i.text for i in b.content if isinstance(i, Text)))
        elif isinstance(b, BulletList):
            out.extend(
                "".join(i.text for i in item.content if isinstance(i, Text)) for item in b.items
            )
    return "\n".join(out)


def test_the_chapter_names_the_sets_the_sample_and_the_audience_the_design_stated() -> None:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    design = compose_design_sections(spec, ("Co lidé ráno pijí?",))
    chapter = _words(design.chapter.blocks)
    assert "Co lidé ráno pijí?" in chapter
    assert "Nápoje" in chapter and all(o in chapter for o in ("Káva", "Čaj", "Kakao", "Džus"))
    assert "„Jak hodnotíte …?“" in chapter and "1 (" in chapter and "10 (" in chapter
    assert "300 respondenty" in chapter
    assert "zúžil podle faktorů populace" in chapter
    assert "vek: 25\u201355" in chapter and "kraj: Praha" in chapter


def test_a_design_that_states_no_sample_or_audience_says_so_rather_than_guessing() -> None:
    spec, problems = compile_design({**DESIGN, "n": None, "audience": {}})
    assert spec is not None, problems
    chapter = _words(compose_design_sections(spec, ()).chapter.blocks)
    assert "Návrh neuvádí velikost vzorku" in chapter
    assert "Cílovou skupinou je celá populace." in chapter


def test_the_appendix_lists_every_question_as_asked_and_each_set() -> None:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    appendix = compose_design_sections(spec, ()).appendix
    assert appendix.appendix and appendix.id == "app-questionnaire"
    words = _words(appendix.blocks)
    assert "Jak často pijete kávu? — škála 1\u20135" in words
    assert "Co si ráno koupíte? — jedna odpověď: Kávu, Čaj, Nic" in words
    assert "Proč? — otevřená odpověď" in words
    assert "Káva, Čaj, Kakao, Džus" in words


def test_a_sets_count_agrees_with_its_words() -> None:
    # "4 položek hodnocených" broke Czech agreement in every report with a 2-4 item set
    # (cross-review); 2-4 take "položky hodnocené", 5 and more "položek hodnocených".
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    assert "Nápoje — 4 položky hodnocené otázkou „Jak hodnotíte …?“" in _words(
        compose_design_sections(spec, ()).chapter.blocks
    )
    battery = {**DESIGN["sections"][1], "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"]}
    spec, problems = compile_design({**DESIGN, "sections": [DESIGN["sections"][0], battery]})
    assert spec is not None, problems
    assert "Nápoje — 5 položek hodnocených otázkou" in _words(
        compose_design_sections(spec, ()).chapter.blocks
    )


def test_a_scales_labels_are_printed_beside_its_values() -> None:
    """input-interactions 3b: what respondents were told a point means is in the appendix and
    under the point's table, the two ends or every point."""
    every = [f"bod {i}" for i in range(1, 11)]
    labelled = {
        **DESIGN,
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {**DESIGN["sections"][0]["questions"][0], "popisky_skaly": ["nikdy", "denně"]},
                    *DESIGN["sections"][0]["questions"][1:],
                ],
            },
            {**DESIGN["sections"][1], "scale_labels": every},
        ],
    }
    spec, problems = compile_design(labelled)
    assert spec is not None, problems
    words = _words(compose_design_sections(spec, ()).appendix.blocks)
    assert "Jak často pijete kávu? — škála 1\u20135 (1 = nikdy, 5 = denně)" in words
    assert "škála 1\u201310 (1 = bod 1, 2 = bod 2," in words and "10 = bod 10)" in words
    chapter = _words(compose_design_sections(spec, ()).chapter.blocks)
    assert "na škále 1 (bod 1) až 10 (bod 10)" in chapter
    notes = scale_notes(spec)
    assert notes["q1"] == "Škála: 1 = nikdy, 5 = denně."
    assert notes["napoje_obj_kava"].startswith("Škála: 1 = bod 1, 2 = bod 2,")
    assert "q2" not in notes
    bare, _ = compile_design(DESIGN)
    assert bare is not None and "q1" not in scale_notes(bare)
    assert scale_notes(bare)["napoje_obj_kava"] == "Škála: 1 = vůbec, 10 = velmi."
