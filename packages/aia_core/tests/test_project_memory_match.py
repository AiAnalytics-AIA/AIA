"""Project memory's match (plans/project-memory-reuse.md M1a), pure.

Every word must occur, accent- and case-folded, somewhere in the study; the answer names the
fields that matched. Dimensions are matched by their titles: the canonical ones from
:data:`DIMENSION_LABELS`, held here equal to the web's ``PERSONA_DIM_LABELS``, and a client's
own from its knowledge.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aia_core.domain.project_memory import (
    DIMENSION_LABELS,
    FIELDS,
    fold,
    match,
    query_words,
    study_text,
)
from aia_core.domain.research_template import research_template

PERSONA_TS = (
    Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "research" / "persona.ts"
)


def _web_labels() -> dict[str, str]:
    source = PERSONA_TS.read_text(encoding="utf-8")
    block = source.split("export const PERSONA_DIM_LABELS", 1)[1].split("};", 1)[0]
    return dict(re.findall(r'^\s+(\w+): "([^"]*)",$', block, re.M))


def test_the_dimension_titles_are_the_webs() -> None:
    web = _web_labels()
    assert len(web) == 18
    assert dict(DIMENSION_LABELS) == web


def test_fold_drops_accents_and_case() -> None:
    assert fold("Zdraví a NÁKUPNÍ chování") == "zdravi a nakupni chovani"
    assert query_words("  Zdraví  zdravi Káva ") == ("zdravi", "kava")


def _design(**over: Any) -> dict[str, Any]:
    content = research_template()
    content.update(
        title="Ranní káva",
        goal="Zjistit, zda nový nápoj dává smysl dojíždějícím.",
        decision_use="Rozhodnutí o uvedení na trh",
        sections=[
            {"title": "Návyky", "type": "questions", "questions": []},
            {"title": "Značky", "type": "object_battery", "object_family": "Kávové značky"},
        ],
    )
    content["research_plan"]["research_questions"] = [
        "Kdo pije kávu ráno?",
        {"text": "Kde ji kupuje?"},
    ]
    content["research_plan"]["objectives"] = ["Velikost trhu"]
    content["persona_dimensions"] = {"approved": ["zdravi", "KN-own", "neznama"]}
    content.update(over)
    return content


def test_a_study_reads_its_name_and_its_designs_fields() -> None:
    text = study_text("Káva 2026", _design(), client_dimension_titles={"KN-own": "Ranní rituály"})
    assert set(text.fields) == set(FIELDS)
    assert text.fields["name"] == ("Káva 2026",)
    assert text.fields["research_questions"] == ("Kdo pije kávu ráno?", "Kde ji kupuje?")
    assert text.fields["sections"] == ("Návyky", "Značky", "Kávové značky")
    # Canonical by its title, the client's by its knowledge title, anything else by its id.
    assert text.fields["dimensions"] == ("Zdraví", "Ranní rituály", "neznama")


def test_a_word_finds_its_other_cases_through_its_stem() -> None:
    text = study_text("X", {"title": "Kdo pije kávu ráno?"}, client_dimension_titles={})
    assert match(query_words("káva"), text) is not None  # "kav" in "kavu"
    assert match(query_words("kávou"), text) is None  # "kavo" is not in it
    assert match(query_words("kdo"), text) is not None  # short words are matched whole


def test_every_word_must_occur_somewhere() -> None:
    text = study_text("Káva 2026", _design(), client_dimension_titles={})
    assert match(query_words("kava dojizdejici"), text) is not None
    assert match(query_words("kava pivo"), text) is None
    assert match((), text) is None


def test_the_answer_names_each_field_that_matched() -> None:
    text = study_text("Káva 2026", _design(), client_dimension_titles={})
    found = match(query_words("kava"), text)
    assert found is not None
    assert [f.field for f in found] == ["name", "title", "research_questions", "sections"]
    assert {f.field: f.texts for f in found}["research_questions"] == ("Kdo pije kávu ráno?",)


def test_a_dimension_is_found_by_its_czech_title_and_by_the_clients_own() -> None:
    text = study_text("X", _design(), client_dimension_titles={"KN-own": "Ranní rituály"})
    by_title = match(query_words("Zdraví"), text)
    assert by_title is not None and [f.field for f in by_title] == ["dimensions"]
    own = match(query_words("rituály"), text)
    assert own is not None and [f.field for f in own] == ["dimensions"]


def test_a_study_without_a_design_is_its_name_and_malformed_content_is_skipped() -> None:
    bare = study_text("Cenové scénáře", None, client_dimension_titles={})
    assert bare.fields["name"] == ("Cenové scénáře",)
    assert all(not v for k, v in bare.fields.items() if k != "name")
    odd = study_text(
        "X",
        {
            "title": 7,
            "research_plan": "nope",
            "sections": ["a", {"title": ""}],
            "persona_dimensions": [],
        },
        client_dimension_titles={},
    )
    assert all(not v for k, v in odd.fields.items() if k != "name")
