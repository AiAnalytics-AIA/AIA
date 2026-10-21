"""Stable item ids (domain/item_ids.py, design_fields.py; working-copy-edit-ops WCE1).

The case file tests/fixtures/item_ids/cases.json is read here and by the web
(apps/web/src/research/item-ids.test.ts). Its expectations pin the ids content written before
WCE1 is read with: they are that content's identity from now on, so a change to how an id is
derived re-keys every stored design and must change the file on purpose.
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from aia_core.domain import edit_ops as e
from aia_core.domain.design_fields import changed_fields
from aia_core.domain.design_items import (
    Documents,
    ItemKey,
    design_items,
    from_legacy_keys,
    legacy_keys,
    merge_items,
)
from aia_core.domain.item_ids import (
    SIDECAR_KEYS,
    _entries,
    derived_id,
    fnv10,
    fold,
    ids_by_kind,
    reconcile,
    section_ids,
    settle_item_ids,
    with_item_ids,
)
from aia_core.domain.research_design import ResearchSpecification, compile_design
from aia_core.domain.research_lead import FOCUS_ID
from aia_core.domain.research_trace import trace_research

FIXTURES = Path(__file__).parent / "fixtures"
CASES: dict[str, Any] = json.loads((FIXTURES / "item_ids/cases.json").read_text("utf-8"))
EDIT = TypeAdapter(e.EditOp)


# --------------------------------------------------------------------------- the shared cases


@pytest.mark.parametrize("case", CASES["hashes"], ids=lambda c: repr(c["text"]))
def test_the_hash(case: dict[str, str]) -> None:
    assert fnv10(case["text"]) == case["fnv10"]


def test_a_lone_surrogate_hashes_as_the_browser_encodes_it() -> None:
    assert fnv10("\ud800 osamocený") == fnv10("\ufffd osamocený")


@pytest.mark.parametrize("case", CASES["folds"], ids=lambda c: repr(c["text"]))
def test_the_fold(case: dict[str, str]) -> None:
    assert fold(case["text"]) == case["fold"]


@pytest.mark.parametrize("case", CASES["derived"], ids=lambda c: f"{c['kind']}:{c['text']}")
def test_a_derived_id(case: dict[str, Any]) -> None:
    got = derived_id(case["prefix"], case["kind"], case["text"], case["occurrence"])
    assert got == case["id"]
    assert e.is_item_id(got)


@pytest.mark.parametrize("case", CASES["reconcile"], ids=lambda c: c["name"])
def test_a_list_s_ids(case: dict[str, Any]) -> None:
    previous = case["previous"]
    ids = reconcile(
        case["texts"],
        prefix="rq_",
        kind="research_question",
        entries=_entries(case["entries"]),
        previous=[tuple(p) for p in previous] if previous is not None else None,
    )
    assert ids == case["ids"]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("case", CASES["sections"], ids=lambda c: c["name"])
def test_the_compiler_s_section_ids(case: dict[str, Any]) -> None:
    assert section_ids(case["sections"]) == case["ids"]


@pytest.mark.parametrize("case", CASES["designs"], ids=lambda c: c["name"])
def test_a_design_with_its_ids(case: dict[str, Any]) -> None:
    content, analysis = with_item_ids(case["content"], case["analysis"])
    assert {"content": content, "analysis": analysis} == case["expect"]
    # Idempotent: a design read with its ids is read the same again.
    assert with_item_ids(content, analysis) == (content, analysis)
    # Nothing is changed but the ids written in.
    assert _without_ids(content) == _without_ids(case["content"]) | (
        {"sections": _without_ids(content)["sections"]}
    )


@pytest.mark.parametrize("case", CASES["settle"], ids=lambda c: c["name"])
def test_a_change_settled(case: dict[str, Any]) -> None:
    content, _ = settle_item_ids((case["before"], None), (case["after"], None))
    assert content == case["expect"]


def _without_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_ids(v) for k, v in value.items() if k not in SIDECAR_KEYS}
    if isinstance(value, list):
        return [_without_ids(v) for v in value]
    return value


# --------------------------------------------------------------------------- nothing compiled moves


def _contents() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for case in json.loads((FIXTURES / "design_items/cases.json").read_text("utf-8"))["cases"]:
        out += [case["before"]["content"], case["after"]["content"]]
    out += list(
        json.loads((FIXTURES / "edit_ops/cases.json").read_text("utf-8"))["contents"].values()
    )
    out += [c["content"] for c in CASES["designs"]]
    out += [{"sections": c["sections"]} for c in CASES["sections"]]
    return out


def _random_sections(rng: random.Random) -> list[Any]:
    titles = ["Nákup", "nákup", "1. blok", "", "Značky", "Značky", "sec", "x_2", "X 2"]
    sections: list[Any] = []
    for i in range(rng.randint(1, 7)):
        kind = rng.choice(["questions", "object_battery", "intro", None])
        sec: dict[str, Any] = {"title": rng.choice(titles)}
        if kind is not None:
            sec["type"] = kind
        if rng.random() < 0.3:
            sec["id"] = rng.choice(["nakup", "nakup_2", "Sec X", "", "znacky"])
        if kind == "object_battery":
            sec |= {"object_family": "značky", "objects": ["A", "B", "C", "D"]}
        else:
            sec["questions"] = [
                {"id": f"q{i}_{j}", "text": f"Otázka {j}?", "typ": "otevrena"}
                for j in range(rng.randint(0, 2))
            ]
        sections.append(sec if rng.random() > 0.05 else "not a section")
    return sections


def _spec(content: dict[str, Any]) -> tuple[ResearchSpecification | None, tuple[str, ...]]:
    spec, problems = compile_design(copy.deepcopy(content))
    return spec, tuple(p.code for p in problems)


def test_ids_change_nothing_a_run_compiles() -> None:
    """A section given the compiler's id compiles to the same specification, fingerprint and
    respondent columns; an id list is no field the compiler reads. COMPILER_VERSION stays."""
    rng = random.Random(1501)
    contents = _contents() + [{"sections": _random_sections(rng)} for _ in range(300)]
    compiled = 0
    for content in contents:
        before, problems = _spec(content)
        after, problems_after = _spec(with_item_ids(content)[0])
        assert problems == problems_after
        if before is None:
            assert after is None
            continue
        assert after is not None
        assert after.fingerprint() == before.fingerprint()
        assert after.model_dump(mode="json") == before.model_dump(mode="json")
        assert after.battery_questions() == before.battery_questions()
        compiled += 1
    assert compiled > 50  # the property was exercised, not vacuously true


def test_every_id_is_one_the_interface_can_focus() -> None:
    for case in CASES["designs"]:
        content, _ = with_item_ids(case["content"], case["analysis"])
        named = list(ids_by_kind(content))
        assert {kind for kind, _ in named} >= {"research_question", "section", "option", "object"}
        for kind, ident in named:
            assert e.is_item_id(ident)
            holder = (
                "section" if kind == "section" else "question" if kind == "question" else "plan"
            )
            assert FOCUS_ID.fullmatch(f"{holder}:{ident}")


# --------------------------------------------------------------------------- the plan's tests

PLAN_BASE: dict[str, Any] = CASES["designs"][0]["content"]


def test_a_reword_keeps_its_research_question_links() -> None:
    """The research question keeps its id, so it is one changed item, and the questionnaire
    items that measure it still do: nothing is left dangling."""
    before, _ = with_item_ids(PLAN_BASE)
    after = copy.deepcopy(before)
    after["research_plan"]["research_questions"][1] = "Kdo si kávu kupuje?"
    settled, _ = settle_item_ids((before, None), (after, None))
    rq = next(
        k
        for k in design_items({"content": before}, {"content": settled})
        if k.kind == "research_question"
    )
    assert {
        k
        for k in design_items({"content": before}, {"content": settled})
        if k.kind == "research_question"
    } == {rq}
    spec, _ = compile_design(settled)
    assert spec is not None
    stated = tuple(settled["research_plan"]["research_questions"])
    trace = trace_research(spec, stated, ())
    assert not trace.dangling
    reworded = next(t for t in trace.questions if t.text == "Kdo si kávu kupuje?")
    assert "q1" in reworded.measures  # the compiled id of Q1
    # The same change without the links followed would leave Q1 measuring nothing stated.
    unfollowed, _ = compile_design(with_item_ids(after)[0])
    assert unfollowed is not None and trace_research(unfollowed, stated, ()).dangling
    assert settled["research_plan"]["research_question_comparisons"] == {
        "Kdo si kávu kupuje?": "describe"
    }
    # Without ids of its own the reword is, as before, one research question gone and one new.
    bare = copy.deepcopy(PLAN_BASE)
    bare["research_plan"]["research_questions"][1] = "Kdo si kávu kupuje?"
    assert (
        len(
            [
                k
                for k in design_items({"content": PLAN_BASE}, {"content": bare})
                if k.kind == "research_question"
            ]
        )
        == 2
    )


def test_two_people_adding_questions_to_one_section_touch_different_keys() -> None:
    content = CASES["designs"][0]["expect"]["content"]
    add = {
        "op": "question_add",
        "section_id": "uvod",
        "qtype": "otevrena",
        "options": [],
        "why": "x",
    }
    mine = e.touches(
        EDIT.validate_python(add | {"text": "Co pijete?"}), content, new_id=lambda k: "Q_mine"
    )
    theirs = e.touches(
        EDIT.validate_python(add | {"text": "Kdy pijete?"}), content, new_id=lambda k: "Q_theirs"
    )
    assert mine == {(ItemKey("content", "question", "Q_mine"), "item")}
    assert theirs == {(ItemKey("content", "question", "Q_theirs"), "item")}
    assert not {k for k, _ in mine} & {k for k, _ in theirs}


def test_a_section_move_is_an_item() -> None:
    before, _ = with_item_ids(PLAN_BASE)
    after = copy.deepcopy(before)
    after["sections"].reverse()
    assert changed_fields({"content": before}, {"content": after}) == {
        (ItemKey("content", "order", "sections"), "order")
    }
    # Adding a section moves nothing.
    added = copy.deepcopy(before)
    added["sections"].insert(
        1, {"id": "sec_new", "type": "questions", "title": "Nová", "questions": []}
    )
    assert changed_fields({"content": before}, {"content": added}) == {
        (ItemKey("content", "section", "sec_new"), "item")
    }


def test_a_question_moved_between_sections_changes_its_section_field() -> None:
    questions = [{"id": "q1", "text": "A?"}, {"id": "q2", "text": "B?"}]
    before = {
        "sections": [
            {"id": "s1", "type": "questions", "questions": questions},
            {"id": "s2", "type": "questions", "questions": []},
        ]
    }
    after = copy.deepcopy(before)
    after["sections"][1]["questions"].append(after["sections"][0]["questions"].pop())
    assert changed_fields({"content": before}, {"content": after}) == {
        (ItemKey("content", "question", "q2"), "section")
    }


def test_rewording_a_question_and_changing_its_options_touch_two_fields() -> None:
    before, _ = with_item_ids(PLAN_BASE)
    worded, optioned = copy.deepcopy(before), copy.deepcopy(before)
    worded["sections"][0]["questions"][0]["text"] = "Pijete kávu?"
    optioned["sections"][0]["questions"][0]["kategorie"] = ["Ano, denně", "Ne"]
    q1 = ItemKey("content", "question", "Q1")
    assert changed_fields({"content": before}, {"content": worded}) == {(q1, "text")}
    assert changed_fields({"content": before}, {"content": optioned}) == {(q1, "kategorie")}


# --------------------------------------------------------------------------- reading what is stored


def test_content_with_stale_id_lists_reads_the_same_everywhere() -> None:
    """A writer that kept the id lists but changed the lists beside them (a proposal spread over
    its baseline) is read by the bindings: the same ids on every read, never shifted by place."""
    before, _ = with_item_ids(PLAN_BASE)
    spread = copy.deepcopy(before)
    spread["research_plan"]["research_questions"] = ["Nová otázka?", "Jak cena mění zájem?"]
    content, _ = with_item_ids(spread)
    ids = [x["id"] for x in content["research_plan"]["research_question_ids"]]
    old = [x["id"] for x in before["research_plan"]["research_question_ids"]]
    assert ids[1] == old[0]  # the kept question kept its id although it moved
    assert ids[0] not in old  # the new one is new, never the removed one's
    assert with_item_ids(spread) == with_item_ids(spread)


def test_a_merge_keeps_the_person_s_id_lists_lined_up() -> None:
    base_content, base_analysis = with_item_ids(PLAN_BASE, CASES["designs"][0]["analysis"])
    base = Documents(content=base_content, analysis=base_analysis)
    proposed = copy.deepcopy(base)
    proposed.content["research_plan"]["hypotheses"] = ["Sleva zvýší nákup", "Cena nerozhoduje"]
    proposed.content["research_plan"].pop("hypothesis_ids")  # a model's list carries none
    touched = design_items(base, proposed)
    current = copy.deepcopy(base)
    current.content["research_plan"]["objectives"].append("Popsat segmenty")
    current.content["research_plan"]["objective_ids"].append({"id": "obj_mine", "bound": "x"})
    assert not touched & design_items(base, current)
    merged = merge_items(proposed, current, touched, baseline=base)
    plan = merged.content["research_plan"]
    assert plan["hypotheses"] == ["Sleva zvýší nákup", "Cena nerozhoduje"]
    assert len(plan["hypothesis_ids"]) == 2
    assert plan["hypothesis_ids"][0] == base_content["research_plan"]["hypothesis_ids"][0]
    assert plan["objective_ids"][-1]["id"] == "obj_mine"
    assert (
        with_item_ids(merged.content)[0]["research_plan"]["hypothesis_ids"]
        == plan["hypothesis_ids"]
    )


def test_a_merge_of_content_without_ids_writes_none() -> None:
    """Behind the switch: content no writer gave ids is merged as before, nothing written in."""
    base = Documents(content=copy.deepcopy(PLAN_BASE))
    proposed = copy.deepcopy(base)
    proposed.content["research_plan"]["hypotheses"].append("Cena nerozhoduje")
    merged = merge_items(proposed, base, design_items(base, proposed), baseline=base)
    assert merged.content == proposed.content


def test_keys_recorded_before_ids_are_read_as_the_ids_they_name() -> None:
    """A job recorded its touched items as text keys before the deploy; accepted after it."""
    base = {"content": copy.deepcopy(PLAN_BASE)}
    proposed = copy.deepcopy(base)
    proposed["content"]["research_plan"]["research_questions"] = ["Jak cena mění zájem?", "Proč?"]
    recorded = {
        ItemKey("content", "research_question", "kdo kupuje?"),
        ItemKey("content", "research_question", "proč?"),
        ItemKey("content", "brief", "goal"),
    }
    now = design_items(base, proposed)
    assert from_legacy_keys(recorded, base, proposed) == now | {ItemKey("content", "brief", "goal")}
    assert legacy_keys(now, base, proposed) == recorded - {ItemKey("content", "brief", "goal")}
    assert from_legacy_keys(now, base, proposed) == now  # already ids: kept
