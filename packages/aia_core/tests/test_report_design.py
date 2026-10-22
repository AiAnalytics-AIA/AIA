"""The internal report's design chapter and questionnaire appendix (complete-study-report B1b)."""

from __future__ import annotations

from typing import Any

from aia_core.application.report_design import compose_design_sections
from aia_core.application.report_tables import scale_notes
from aia_core.domain.report.model import BulletList, Heading, Paragraph, Text
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


def test_the_audiences_description_and_subpanel_are_kept_and_printed_when_given() -> None:
    """Compiler 3 keeps what a person said about the audience (artifact-chain CHN5): the
    description and the built-in subpanel, each only when given, printed before the filters."""
    stated = {
        **DESIGN,
        "audience": {
            **DESIGN["audience"],
            "description": "Pražané, kteří ráno pijí kávu",
            "builtin_subpanel": "young_18_29",
        },
    }
    spec, problems = compile_design(stated)
    assert spec is not None, problems
    assert spec.audience["description"] == "Pražané, kteří ráno pijí kávu"
    assert spec.audience["builtin_subpanel"] == "young_18_29"
    words = _words(compose_design_sections(spec, ()).chapter.blocks)
    assert "Cílová skupina podle návrhu: Pražané, kteří ráno pijí kávu." in words
    assert "vestavěného podpanelu young_18_29" in words
    assert "kraj: Praha" in words

    plain, _ = compile_design(DESIGN)
    assert plain is not None
    # Neither given: the body has neither key, so its fingerprint is what it was under this
    # compiler, and the chapter says nothing it was not told.
    assert set(plain.audience) == {"source_mode", "strategy", "has_filters"}
    blank, _ = compile_design({**DESIGN, "audience": {**DESIGN["audience"], "description": "  "}})
    assert blank is not None and blank.fingerprint() == plain.fingerprint()
    assert "podle návrhu" not in _words(compose_design_sections(plain, ()).chapter.blocks)


def test_a_subpanel_left_from_a_population_choice_is_not_an_external_audiences() -> None:
    """The audience step keeps the last built-in subpanel when the source moves outside AIA's
    population (OI-51); an external audience did not come from it, so it is neither compiled
    nor printed (Codex on #587)."""
    external = {
        **DESIGN,
        "audience": {
            **DESIGN["audience"],
            "source_mode": "customer",
            "builtin_subpanel": "young_18_29",
        },
    }
    spec, problems = compile_design(external)
    assert spec is not None, problems
    assert "builtin_subpanel" not in spec.audience
    words = _words(compose_design_sections(spec, ()).chapter.blocks)
    assert "podpanelu" not in words
    assert "mimo populaci AIA" in words


def test_the_chapter_opens_with_what_the_brief_asked_for_before_how_it_was_measured() -> None:
    """F19: the draft said "co měl výzkum zjistit" and printed only how it measured it."""
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    blocks = compose_design_sections(
        spec,
        ("Co lidé ráno pijí?",),
        goal="Zjistit, zda dojíždějící koupí ranní nápoj do 60 Kč.",
        decision_use="Rozhodnutí o uvedení nápoje.",
    ).chapter.blocks
    chapter = _words(blocks)
    goal, use, question = (
        chapter.index("Zjistit, zda dojíždějící koupí ranní nápoj do 60 Kč."),
        chapter.index("Rozhodnutí o uvedení nápoje."),
        chapter.index("Co lidé ráno pijí?"),
    )
    assert goal < use < question
    headings = [b.text for b in blocks if isinstance(b, Heading)]
    assert headings[:3] == ["Cíl studie", "Rozhodnutí, které má výzkum podpořit", "Výzkumné otázky"]


def test_an_empty_brief_adds_no_heading_of_its_own() -> None:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    blocks = compose_design_sections(spec, (), goal=None, decision_use=None).chapter.blocks
    headings = [b.text for b in blocks if isinstance(b, Heading)]
    assert "Cíl studie" not in headings
    assert "Rozhodnutí, které má výzkum podpořit" not in headings


def test_a_goal_in_two_paragraphs_prints_as_two() -> None:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    blocks = compose_design_sections(
        spec, (), goal="První odstavec.\n\nDruhý odstavec."
    ).chapter.blocks
    written = [_words((b,)) for b in blocks if isinstance(b, Paragraph)]
    assert "První odstavec." in written and "Druhý odstavec." in written
