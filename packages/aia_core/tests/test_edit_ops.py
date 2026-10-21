"""The working copy's edit vocabulary (domain/edit_ops.py; ADR 0029 decision 1, WCE0).

The case file tests/fixtures/edit_ops/cases.json is read here and by the web
(apps/web/src/lib/edit-ops.cases.test.ts): the closed set, each applied operation's result on a
working copy or the word it is refused with, the text-only marker, what each operation touches,
the Sociomap lock and the trace's reading of research questions.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import TypeAdapter

from aia_core.domain import edit_ops as e
from aia_core.domain.analysis.native import research_questions_of
from aia_core.domain.design_items import Documents, ItemKey
from aia_core.domain.research_lead import FOCUS_ID, LeadOutput
from aia_core.domain.research_trace import comparisons_of

CASES: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures/edit_ops/cases.json").read_text(encoding="utf-8")
)
EDIT = TypeAdapter(e.EditOp)


def _ids() -> Callable[[e.IdKind], str]:
    suffixes: Iterator[str] = iter(CASES["ids"])
    return lambda kind: e.ID_PREFIX[e.IdKind(kind)] + next(suffixes)


def _content(name_or_doc: Any) -> Any:
    return CASES["contents"][name_or_doc] if isinstance(name_or_doc, str) else name_or_doc


# --------------------------------------------------------------------------- the closed set


def test_the_case_file_holds_the_catalogue_exactly() -> None:
    written = [
        {
            "op": s.name.value,
            "kinds": [k.value for k in s.kinds],
            "fields": list(s.fields),
            "text": s.text.value,
            "may_touch_locked": s.may_touch_locked,
            "in_lead_output": s.in_lead_output,
            "availability": s.availability.value,
            "chunk": s.chunk,
        }
        for s in e.CATALOGUE.values()
    ]
    assert CASES["catalogue"] == written
    assert CASES["refusals"] == sorted(e.REFUSALS)


def test_every_operation_has_one_entry_and_the_names_are_unique() -> None:
    assert list(e.CATALOGUE) == list(e.OpName)
    assert all(spec.name is name for name, spec in e.CATALOGUE.items())
    assert all(spec.kinds and spec.fields and spec.chunk for spec in e.CATALOGUE.values())


def _payload_ops() -> set[str]:
    members = get_args(get_args(e.EditOp)[0])
    return {get_args(m.model_fields["op"].annotation)[0] for m in members}


def test_the_applied_operations_are_exactly_the_payloads_this_module_has() -> None:
    applied = {n.value for n, s in e.CATALOGUE.items() if s.availability is e.Availability.APPLIED}
    assert applied == _payload_ops()


def test_the_lead_output_carries_exactly_the_operations_marked_so() -> None:
    """The Lead's closed output is the vocabulary's today, no more: widening it is WCE10's."""
    schema = LeadOutput.model_json_schema()
    in_schema = {
        definition["properties"]["op"]["const"]
        for definition in schema["$defs"].values()
        if "op" in definition.get("properties", {})
        and definition["properties"]["op"].get("const")
        not in ("open_stage", "focus")  # the view's commands, not edits
    }
    marked = {n.value for n, s in e.CATALOGUE.items() if s.in_lead_output}
    assert in_schema == marked == _payload_ops()


def test_a_declared_operation_is_refused_by_name_until_its_chunk() -> None:
    for name, spec in e.CATALOGUE.items():
        expected = None if spec.availability is e.Availability.APPLIED else "op_not_available"
        assert e.op_refusal(name.value) == expected
    assert e.op_refusal("question_teleport") == "unknown_edit"
    assert e.spec_of("question_teleport") is None


def test_the_sociomap_unlock_is_no_operation() -> None:
    """The unlock is a person's recorded act (ledger ``sociomap_unlock``, WCE8), never something
    an operation batch, let alone the Lead, can express."""
    assert e.spec_of("sociomap_unlock") is None
    assert not any("unlock" in n.value for n in e.OpName)


# --------------------------------------------------------------------------- ids


def test_new_ids_take_their_kind_s_prefix_and_the_item_grammar() -> None:
    for kind, prefix in e.ID_PREFIX.items():
        made = e.new_item_id(kind)
        assert made.startswith(prefix)
        assert e.is_item_id(made)
    assert set(e.ID_PREFIX) == set(e.IdKind)
    assert e.ID_PREFIX[e.IdKind.QUESTION] == "Q_" and e.ID_PREFIX[e.IdKind.SECTION] == "sec_"
    assert e.new_item_id("question") != e.new_item_id("question")


def test_an_item_id_is_what_the_interface_can_focus() -> None:
    for good in ("Q1", "sec_a", "o_tchibo", "Q_3f9a.b-c"):
        assert e.is_item_id(good)
        assert FOCUS_ID.fullmatch(f"question:{good}")
    for bad in ("", "a b", "q:1", "x" * 81, None, 7):
        assert not e.is_item_id(bad)


def test_an_operation_id_is_its_own() -> None:
    made = e.new_op_id()
    assert made.startswith("EOP-") and len(made) == 36 and made != e.new_op_id()


# --------------------------------------------------------------------------- apply


@pytest.mark.parametrize("case", CASES["apply"], ids=[c["name"] for c in CASES["apply"]])
def test_an_edit_applies_as_the_case_says(case: dict[str, Any]) -> None:
    edit = EDIT.validate_python(case["edit"])
    before = case["before"]
    got = e.apply_edit(before["content"], before["analysis"], edit, new_id=_ids())
    expect = case["expect"]
    if "refused" in expect:
        assert isinstance(got, e.Refused)
        assert got.reason == expect["refused"]
        assert got.reason in e.REFUSALS
        # The grounding refuses with the same word before anything is applied.
        assert e.refusal(edit, before["content"], before["analysis"]) == expect["refused"]
        return
    assert not isinstance(got, e.Refused)
    assert {"content": got[0], "analysis": got[1]} == expect
    assert e.refusal(edit, before["content"], before["analysis"]) is None


def test_apply_changes_nothing_it_was_given() -> None:
    case = next(c for c in CASES["apply"] if c["name"] == "a research question added")
    before = json.loads(json.dumps(case["before"]))
    e.apply_edit(before["content"], before["analysis"], EDIT.validate_python(case["edit"]))
    assert before == case["before"]


# --------------------------------------------------------------------------- text only


@pytest.mark.parametrize("case", CASES["text_edits"], ids=lambda c: json.dumps(c["edit"]))
def test_the_text_only_marker(case: dict[str, Any]) -> None:
    assert e.is_text_edit(EDIT.validate_python(case["edit"])) is case["text"]


def test_only_a_by_payload_operation_can_be_a_text_edit() -> None:
    """The default automatic accept takes text edits only; a structural operation never is one,
    and a declared one is not either until its chunk rules on its payload."""
    by_payload = {n.value for n, s in e.CATALOGUE.items() if s.text is e.TextRuling.BY_PAYLOAD}
    assert by_payload >= e.TEXT_EDIT_OPS
    assert not e.is_text_edit(TypeAdapter(Any).validate_python({"op": "section_edit"}))


# --------------------------------------------------------------------------- touches


@pytest.mark.parametrize("case", CASES["touches"], ids=lambda c: json.dumps(c["edit"]))
def test_what_an_edit_touches_per_item_and_field(case: dict[str, Any]) -> None:
    edit = EDIT.validate_python(case["edit"])
    got = sorted(f"{key}|{field}" for key, field in e.touches(edit, _content(case["content"])))
    assert got == case["touches"]
    spec = e.CATALOGUE[e.OpName(edit.op)]
    assert {field for _, field in e.touches(edit, _content(case["content"]))} <= set(spec.fields)


def test_two_edits_of_one_question_conflict_only_on_the_same_field() -> None:
    """D-06: a rewording and a re-optioning of Q1 touch different (item, field) pairs."""
    content = CASES["contents"]["base"]
    words = e.touches(EDIT.validate_python(CASES["touches"][3]["edit"]), content)
    options = e.touches(EDIT.validate_python(CASES["touches"][4]["edit"]), content)
    assert (
        {k for k, _ in words} == {k for k, _ in options} == {ItemKey("content", "question", "Q1")}
    )
    assert not words & options


# --------------------------------------------------------------------------- the lock


@pytest.mark.parametrize("case", CASES["lock"], ids=[c["name"] for c in CASES["lock"]])
def test_the_lock_on_an_edit(case: dict[str, Any]) -> None:
    edit = EDIT.validate_python(case["edit"])
    content = _content(case["content"])
    assert e.lock_refusal(edit, content, unlocked=case["unlocked"]) == case["refused"]
    if case["refused"]:
        assert e.CATALOGUE[e.OpName(edit.op)].may_touch_locked


@pytest.mark.parametrize(
    "case", CASES["whole_copy_lock"], ids=[c["name"] for c in CASES["whole_copy_lock"]]
)
def test_the_lock_on_a_whole_copy_write(case: dict[str, Any]) -> None:
    before = Documents(content=_content(case["before"]))
    after = {"content": case["after"]}
    assert e.whole_copy_lock_refusal(before, after, unlocked=case["unlocked"]) == case["refused"]


def test_the_lock_covers_the_declared_inputs_and_the_sets_they_rate() -> None:
    """D-30: the rating question and every tracked set of the questionnaire; nothing else."""
    assert e.locked_items(CASES["contents"]["base"]) == frozenset()
    assert e.locked_items(CASES["contents"]["locked"]) == {
        ItemKey("content", "question", "Q2"),
        ItemKey("content", "battery", "bat_1"),
    }
    only_roles = json.loads(json.dumps(CASES["contents"]["base"]))
    only_roles["sections"][1]["context_objects"] = []
    assert e.declares_sociomap_inputs(only_roles)  # declaring no context object is a declaration
    assert e.locked_items(only_roles) == {ItemKey("content", "battery", "bat_1")}


# --------------------------------------------------------------------------- the trace


@pytest.mark.parametrize("case", CASES["link_keys"], ids=lambda c: repr(c["text"]))
def test_a_link_is_keyed_as_the_trace_keys_it(case: dict[str, str]) -> None:
    design = {"research_plan": {"research_question_comparisons": {case["text"]: "describe"}}}
    assert list(comparisons_of(design)) == [case["key"]]


@pytest.mark.parametrize(
    "case", CASES["research_questions_of"], ids=[c["name"] for c in CASES["research_questions_of"]]
)
def test_the_research_questions_are_read_as_the_case_says(case: dict[str, Any]) -> None:
    assert list(research_questions_of(case["design"])) == case["expect"]
