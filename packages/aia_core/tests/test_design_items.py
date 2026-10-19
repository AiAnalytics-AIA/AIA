"""design_items: a design's items, which differ, and a proposal merged item by item (ADR 0026 d5-6).

The cases in ``fixtures/design_items/cases.json`` are shared with the web
(``apps/web/src/research/proposal-diff.items.test.ts``), which reads the same file.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.design_items import (
    Documents,
    ItemKey,
    brief_signature,
    design_items,
    item_values,
    merge_items,
    occurrence_keys,
)

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "design_items" / "cases.json").read_text("utf-8")
)
BASE: dict[str, Any] = CASES["cases"][0]["before"]


def docs(value: dict[str, Any]) -> Documents:
    return Documents.of(copy.deepcopy(value))


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["name"])
def test_the_shared_cases(case: dict[str, Any]) -> None:
    items = design_items(case["before"], case["after"])
    assert sorted(str(k) for k in items) == case["items"], case["note"]
    # The difference is symmetric: what was added one way is removed the other.
    assert design_items(case["after"], case["before"]) == items


@pytest.mark.parametrize("case", CASES["merges"], ids=lambda c: c["name"])
def test_the_shared_merges(case: dict[str, Any]) -> None:
    """Order is no item, so a merge keeps the person's order (a reorder was undone before)."""
    base, current, proposed = docs(case["base"]), docs(case["current"]), docs(case["proposed"])
    touched = design_items(base, proposed)
    assert not touched & design_items(base, current), case["note"]
    merged = merge_items(proposed, current, touched)
    assert {"content": merged.content, "analysis": merged.analysis} == case["merged"]


@pytest.mark.parametrize("sig", CASES["brief_signatures"], ids=lambda s: s["name"])
def test_the_brief_signature_is_the_browsers(sig: dict[str, Any]) -> None:
    assert brief_signature(sig["content"]) == sig["signature"]


def test_an_item_key_reads_back_what_it_wrote() -> None:
    for text in ("content:objective:zjistit cenu", "content:n:", "analysis:field:a:b"):
        assert str(ItemKey.parse(text)) == text
    assert ItemKey.parse("analysis:field:a:b").key == "a:b"
    for bad in ("", "content", "other:brief:goal", "content::x"):
        with pytest.raises(ValueError):
            ItemKey.parse(bad)


def test_a_shape_the_rules_do_not_know_is_one_item_whole() -> None:
    before = {"content": {"research_plan": {"objectives": ["A", 3]}, "sections": "x"}}
    after = {"content": {"research_plan": {"objectives": ["A", 4]}, "sections": "y"}}
    assert {str(k) for k in design_items(before, after)} == {
        "content:plan:objectives",
        "content:field:sections",
    }
    # A plan that is not an object is one field; so is an analysis list of objects.
    values = item_values(Documents(content={"research_plan": "free text"}))
    assert ItemKey("content", "field", "research_plan") in values


def test_a_set_with_an_id_is_keyed_by_it() -> None:
    before = {"content": {"research_plan": {"tracked_sets": [{"id": "S1", "title": "A"}]}}}
    after = {"content": {"research_plan": {"tracked_sets": [{"id": "S1", "title": "B"}]}}}
    assert {str(k) for k in design_items(before, after)} == {"content:tracked_set:S1"}


def test_untouched_edits_survive_a_merge() -> None:
    base = docs(BASE)
    proposed = copy.deepcopy(BASE)
    proposed["content"]["research_plan"]["objectives"] = ["Zjistit cenovou citlivost", "Nový cíl"]
    proposed["analysis"]["objectives"] = ["Zjistit cenovou citlivost", "Nový cíl"]
    touched = design_items(base, docs(proposed))
    current = copy.deepcopy(BASE)
    current["content"]["goal"] = "Upravený cíl studie"
    current["content"]["research_plan"]["hypotheses"].append("Moje hypotéza")
    current["content"]["sections"][0]["questions"][0]["text"] = "Upravená otázka?"
    assert not touched & design_items(base, docs(current))

    merged = merge_items(docs(proposed), docs(current), touched)
    assert merged.content["goal"] == "Upravený cíl studie"
    plan = merged.content["research_plan"]
    assert plan["objectives"] == ["Zjistit cenovou citlivost", "Nový cíl"]
    assert plan["hypotheses"] == ["Sleva zvýší nákup", "Moje hypotéza"]
    assert merged.content["sections"][0]["questions"][0]["text"] == "Upravená otázka?"
    assert merged.analysis is not None and merged.analysis["objectives"][1] == "Nový cíl"
    # Nothing else moved: the merge is exactly the person's copy with the touched items.
    assert design_items(docs(current), merged) == touched


def test_a_questionnaire_replacement_merges_by_section_and_question() -> None:
    base = docs(BASE)
    proposed = copy.deepcopy(BASE)
    proposed["content"]["sections"] = [
        BASE["content"]["sections"][1],
        {
            "id": "ai_section_1",
            "type": "questions",
            "title": "AI",
            "questions": [{"id": "ai_q_1_1", "text": "Nová otázka?"}],
        },
    ]
    touched = design_items(base, docs(proposed))
    assert {str(k) for k in touched} == {
        "content:section:s1",
        "content:question:q1",
        "content:question:q2",
        "content:section:ai_section_1",
        "content:question:ai_q_1_1",
    }
    current = copy.deepcopy(BASE)
    current["content"]["sections"].append(
        {"id": "mine", "type": "questions", "title": "Moje", "questions": []}
    )
    current["content"]["sections"][1]["title"] = "Značky (moje)"
    assert not touched & design_items(base, docs(current))
    merged = merge_items(docs(proposed), docs(current), touched)
    ids = [s["id"] for s in merged.content["sections"]]
    assert ids == ["b1", "ai_section_1", "mine"]
    assert merged.content["sections"][0]["title"] == "Značky (moje)"


def test_an_analysis_the_proposal_leaves_alone_is_kept_never_cleared() -> None:
    base = docs(BASE)
    proposed = copy.deepcopy(BASE)
    proposed["content"]["n"] = 500
    touched = design_items(base, docs(proposed))
    merged = merge_items(docs(proposed), docs(BASE), touched)
    assert merged.content["n"] == 500
    assert merged.analysis == BASE["analysis"]
    no_analysis = merge_items(docs(proposed), Documents(content=dict(BASE["content"])), touched)
    assert no_analysis.analysis is None


def test_a_removed_item_is_removed_and_a_new_field_is_added() -> None:
    base = Documents(content={"goal": "a", "notes": [1]}, analysis={"x": 1})
    proposed = Documents(content={"goal": "a", "extra": True}, analysis={"x": 2, "y": 3})
    touched = design_items(base, proposed)
    merged = merge_items(proposed, base, touched)
    assert merged.content == {"goal": "a", "extra": True}
    assert merged.analysis == {"x": 2, "y": 3}


def test_a_briefing_field_merges_alone() -> None:
    base = Documents(content={"briefing": {"situation": "a", "constraints": "b"}})
    proposed = Documents(content={"briefing": {"situation": "z", "constraints": "b"}})
    current = Documents(content={"briefing": {"situation": "a", "constraints": "mine"}})
    touched = design_items(base, proposed)
    merged = merge_items(proposed, current, touched)
    assert merged.content["briefing"] == {"situation": "z", "constraints": "mine"}


def test_two_sets_of_one_title_are_both_kept_through_a_merge() -> None:
    """Keyed by title, the second "Značky" collapsed into the first: a proposal adding "Ceny"
    touched nothing the person edited, and the merge dropped the second set with its edit."""
    case = next(c for c in CASES["cases"] if c["name"] == "duplicate_set_titles")
    base = docs(case["before"])
    current = docs(case["after"])  # the person edited the second "Značky kávy"
    proposed = copy.deepcopy(case["before"])
    ceny = {"title": "Ceny", "objects": ["50 Kč", "70 Kč", "90 Kč", "110 Kč"]}
    proposed["content"]["research_plan"]["tracked_sets"].append(ceny)
    touched = design_items(base, docs(proposed))
    assert {str(k) for k in touched} == {"content:tracked_set:ceny"}
    assert not touched & design_items(base, current)
    merged = merge_items(docs(proposed), current, touched)
    sets = merged.content["research_plan"]["tracked_sets"]
    assert [s["title"] for s in sets] == ["Značky kávy", "Značky kávy", "Ceny"]
    assert sets[1]["objects"][-1] == "Pellini"
    assert design_items(current, merged) == touched


def test_a_repeated_key_is_counted_never_collapsed() -> None:
    assert occurrence_keys(["a", "b", "a", "a#2", "a"]) == ["a", "b", "a#2", "a#2#2", "a#3"]
    values = item_values(
        Documents(
            content={
                "research_plan": {"objectives": ["Cena", "cena "]},
                "sections": [
                    {"id": "s", "type": "questions", "questions": [{"id": "q"}, {"id": "q"}]},
                    {"id": "s", "type": "questions", "questions": [{"id": "q"}]},
                ],
            }
        )
    )
    keys = {str(k) for k in values}
    assert {"content:objective:cena", "content:objective:cena#2"} <= keys
    assert {"content:section:s", "content:section:s#2"} <= keys
    assert {"content:question:q", "content:question:q#2", "content:question:q#3"} <= keys
