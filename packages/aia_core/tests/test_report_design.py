"""The internal report's design chapter and questionnaire appendix (complete-study-report B1b)."""

from __future__ import annotations

from typing import Any

from aia_core.application.report_design import compose_design_sections
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
