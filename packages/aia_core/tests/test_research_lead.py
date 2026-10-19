"""The Research Lead's pure half: its closed output, grounding, numbers, edits and context.

ADR 0026 and the product owner's 2026-10-19 decisions. No database, no model.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.ai_contracts import (
    AgentDefinition,
    canonical_json,
    validate_structured_output,
)
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.research_agents import FIXED_PREFIX
from aia_core.domain.research_lead import (
    CONTEXT_MAX_BYTES,
    DEFAULT_LEAD_NAME,
    DEFAULT_SOUL,
    LEAD_PROMPT_ID,
    STAGES,
    TEXT_EDIT_OPS,
    LeadContextTooLarge,
    LeadOutput,
    QuestionAdd,
    QuestionEdit,
    Refused,
    SelfUpdate,
    apply_edit,
    context_bytes,
    freeze_context,
    ground_edits,
    ground_self_update,
    is_text_edit,
    layer,
    lead_contract,
    lead_prompt,
    lead_request,
    lead_request_window_tokens,
    model_message,
    number_tokens,
    question_add_problem,
    split_self_update,
    unreadable_numbers,
    waiting_self_update,
)
from aia_core.domain.residency import DataClass

WHY = "Protože to zadání potřebuje."


def _output(**fields: Any) -> dict[str, Any]:
    return {"reply": "Dobrý den.", **fields}


def _valid(value: dict[str, Any], allowed: str = "") -> Any:
    return validate_structured_output(lead_contract(allowed), structured=value, text="")


# --------------------------------------------------------------------------- the contract

VALID_EDITS = [
    {"op": "set_text", "field": "goal", "value": "Nový cíl", "why": WHY},
    {"op": "set_text", "field": "briefing.situation", "value": "Situace", "why": WHY},
    {"op": "list_add", "list": "plan.objectives", "value": "Cíl", "why": WHY},
    {"op": "list_replace", "list": "plan.hypotheses", "old": "A", "value": "B", "why": WHY},
    {"op": "list_remove", "list": "plan.research_questions", "old": "Proč?", "why": WHY},
    {
        "op": "question_add",
        "section_id": None,
        "text": "Znáte značku?",
        "qtype": "vyber",
        "options": ["Ano", "Ne"],
        "why": WHY,
    },
    {"op": "question_add", "text": "Proč?", "qtype": "otevrena", "why": WHY},
    {"op": "question_edit", "question_id": "q3", "text": "Jinak", "options": None, "why": WHY},
    {"op": "question_remove", "question_id": "q3", "why": WHY},
    {"op": "set_n", "value": 30, "why": WHY},
    {"op": "set_n", "value": 40000, "why": WHY},
]

INVALID_EDITS = [
    {"op": "set_text", "field": "audience", "value": "x", "why": WHY},  # not an editable field
    {"op": "set_text", "field": "goal", "value": "x"},  # no why
    {"op": "list_add", "list": "plan.topics", "value": "x", "why": WHY},  # not a plan list
    {"op": "list_add", "list": "plan.objectives", "value": "", "why": WHY},
    {"op": "question_add", "text": "Q", "qtype": "vyber", "options": ["Jen jedna"], "why": WHY},
    {"op": "question_add", "text": "Q", "qtype": "matice", "why": WHY},
    {"op": "question_edit", "question_id": "q3", "why": WHY},  # changes nothing
    {"op": "set_n", "value": 29, "why": WHY},
    {"op": "set_n", "value": 40001, "why": WHY},
    {"op": "set_n", "value": True, "why": WHY},  # strict: a boolean is not a count
    {"op": "set_n", "value": "300", "why": WHY},
    {"op": "delete_study", "why": WHY},
    {"op": "set_n", "value": 300, "why": WHY, "approved": True},  # closed
]


@pytest.mark.parametrize("edit", VALID_EDITS)
def test_each_edit_op_is_accepted_in_its_closed_shape(edit: dict[str, Any]) -> None:
    verdict = _valid(_output(edits=[edit]))
    assert verdict.ok, verdict.violations


@pytest.mark.parametrize("edit", INVALID_EDITS)
def test_an_edit_outside_its_shape_is_a_violation(edit: dict[str, Any]) -> None:
    assert not _valid(_output(edits=[edit])).ok


#: Plan inline-decisions chunk 2: wording only, never structure or the sample.
TEXT_EDITS = [
    {"op": "set_text", "field": "goal", "value": "Nový cíl", "why": WHY},
    {"op": "set_text", "field": "plan.problem_summary", "value": "Shrnutí", "why": WHY},
    {"op": "list_replace", "list": "plan.hypotheses", "old": "A", "value": "B", "why": WHY},
    {"op": "question_edit", "question_id": "q3", "text": "Jinak", "why": WHY},
]
STRUCTURAL_EDITS = [
    {"op": "list_add", "list": "plan.objectives", "value": "Cíl", "why": WHY},
    {"op": "list_remove", "list": "plan.research_questions", "old": "Proč?", "why": WHY},
    {"op": "question_add", "text": "Proč?", "qtype": "otevrena", "why": WHY},
    {"op": "question_edit", "question_id": "q3", "options": ["Ano", "Ne"], "why": WHY},
    {
        "op": "question_edit",
        "question_id": "q3",
        "text": "Jinak",
        "options": ["A", "B"],
        "why": WHY,
    },
    {"op": "question_remove", "question_id": "q3", "why": WHY},
    {"op": "set_n", "value": 400, "why": WHY},
]


@pytest.mark.parametrize("edit", TEXT_EDITS)
def test_a_text_edit_changes_wording_only(edit: dict[str, Any]) -> None:
    [parsed] = LeadOutput.model_validate(_output(edits=[edit])).edits
    assert parsed.op in TEXT_EDIT_OPS and is_text_edit(parsed)


@pytest.mark.parametrize("edit", STRUCTURAL_EDITS)
def test_an_edit_that_adds_removes_reoptions_or_resizes_is_no_text_edit(
    edit: dict[str, Any],
) -> None:
    [parsed] = LeadOutput.model_validate(_output(edits=[edit])).edits
    assert not is_text_edit(parsed)


def test_the_text_edit_ops_are_exactly_three() -> None:
    assert {"set_text", "question_edit", "list_replace"} == TEXT_EDIT_OPS


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_can_be_opened(stage: str) -> None:
    assert _valid(_output(view=[{"op": "open_stage", "stage": stage}])).ok


@pytest.mark.parametrize(
    "view",
    [
        {"op": "open_stage", "stage": "sampling"},
        {"op": "focus", "target": "q3"},  # not a data-aia id
        {"op": "focus", "target": "question:q3; drop"},
        {"op": "navigate", "url": "https://example.org"},
    ],
)
def test_a_view_command_outside_its_shape_is_refused(view: dict[str, Any]) -> None:
    assert not _valid(_output(view=[view])).ok


def test_focus_targets_name_an_item_by_its_data_aia_id() -> None:
    for target in ("question:q3", "brief:goal", "plan:research_questions"):
        assert _valid(_output(view=[{"op": "focus", "target": target}])).ok


def test_bounds_on_lists_reply_and_follow() -> None:
    assert not _valid(_output(view=[{"op": "open_stage", "stage": "brief"}] * 4)).ok
    assert not _valid(_output(edits=[VALID_EDITS[0]] * 13)).ok
    assert _valid(_output(edits=[VALID_EDITS[0]] * 12)).ok
    assert not _valid(_output(follow=["a", "b", "c", "d"])).ok
    assert not _valid({"reply": "x" * 4001}).ok
    assert not _valid({"reply": ""}).ok
    assert not _valid({}).ok  # a reply is required


@pytest.mark.parametrize(
    "request_",
    [
        {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
        {"kind": "agent_job", "action": "critique_design", "why": WHY},
        {"kind": "research_run", "why": WHY},
        {"kind": "design_research", "why": WHY},
        {"kind": "interpretation_research", "why": WHY},
    ],
)
def test_a_prepared_request_is_one_of_four_kinds(request_: dict[str, Any]) -> None:
    assert _valid(_output(request=request_)).ok


@pytest.mark.parametrize(
    "request_",
    [
        {"kind": "agent_job", "action": "web_research", "why": WHY},
        {"kind": "agent_job", "action": "analyze_brief"},
        {"kind": "budget_lift", "why": WHY},
        {"kind": "research_run", "why": WHY, "confirm_cost_usd": 5},
    ],
)
def test_a_request_outside_the_four_is_refused(request_: dict[str, Any]) -> None:
    assert not _valid(_output(request=request_)).ok


def test_only_one_request_can_be_prepared() -> None:
    one = {"kind": "research_run", "why": WHY}
    assert not _valid(_output(request=[one, one])).ok


def test_self_update_is_closed_and_bounded() -> None:
    good = {
        "name": "Vedoucí",
        "soul": "# Já\n- stručně",
        "user": "Pracuje ráno.",
        "remember": [{"scope": "personal", "text": "Chce stručné odpovědi."}],
        "forget": ["LMM-0123456789abcdef0123"],
    }
    assert _valid(_output(self_update=good)).ok
    for bad in (
        {**good, "name": "x" * 41},
        {**good, "soul": "x" * 2001},
        {**good, "user": "x" * 2001},
        {**good, "remember": [{"scope": "personal", "text": "a"}] * 3},
        {**good, "remember": [{"scope": "team", "text": "a"}]},
        {**good, "remember": [{"scope": "personal", "text": "x" * 301}]},
        {**good, "forget": ["LMM-a"] * 6},
        {**good, "forget": ["MEM-1"]},
        {**good, "approve": True},
    ):
        assert not _valid(_output(self_update=bad)).ok


def test_the_contract_is_a_closed_agent_contract_the_gateway_accepts() -> None:
    AgentDefinition(
        agent_id=LEAD_PROMPT_ID,
        version="1",
        capability=ModelCapability.RESEARCH_REASONING,
        prompt_id=LEAD_PROMPT_ID,
        prompt_version="1",
        output_contract=lead_contract("context"),
    )


# --------------------------------------------------------------------------- numbers


def test_number_tokens_are_canonical_and_never_part_of_an_id() -> None:
    assert number_tokens("q3 a brief:goal2") == frozenset()
    assert number_tokens("12,50 a 12.5") == {"12.5"}
    assert number_tokens("1\u00a0234 osob, 1 234 a 1234") == {"1234"}
    assert number_tokens("rozpočet 500.0") == {"500"}
    assert number_tokens("2026-10-19") == {"2026", "10", "19"}


def test_a_reply_writes_only_numbers_the_context_holds() -> None:
    allowed = canonical_json({"study": {"budget_usd": 500.0, "n": 1200}})
    assert _valid({"reply": "Rozpočet je 500 a vzorek 1\u00a0200."}, allowed).ok
    refused = _valid({"reply": "Doporučuji 350 respondentů."}, allowed)
    assert not refused.ok
    assert "350" in refused.violations[0]


def test_a_sign_is_part_of_the_number() -> None:
    """Codex P2 on #484: -5 passed when the context held 5."""
    assert number_tokens("pokles o -5 a \u22122,5") == {"-5", "-2.5"}
    # A hyphen joining words or numbers is not a sign: the digits after it are unsigned.
    assert number_tokens("2026-10-19, q-3 a A-5") == {"2026", "10", "19", "3", "5"}
    assert number_tokens("-0 a 0") == {"0"}
    only_five = canonical_json({"change": 5})
    refused = _valid({"reply": "Změna je -5."}, only_five)
    assert not refused.ok and "-5" in refused.violations[0]
    assert not _valid({"reply": "Změna je \u22125."}, only_five).ok
    minus_five = canonical_json({"change": -5})
    assert _valid({"reply": "Změna je -5."}, minus_five).ok
    assert _valid({"reply": "Změna je \u22125."}, minus_five).ok
    assert not _valid({"reply": "Změna je 5."}, minus_five).ok
    # A hyphen between words or numbers is not a sign.
    assert _valid({"reply": "Období 2026-10-19."}, canonical_json({"date": "2026-10-19"})).ok


def test_a_number_the_guard_cannot_read_is_refused_not_guessed() -> None:
    """Codex P2 on #484: 1e6 produced no token at all, so any exponent passed."""
    allowed = canonical_json({"n": 1000000, "x": 1, "y": 6})
    for reply in ("Je to 1e6 lidí.", "Asi 2,5E-3.", "Hodnota -1e6."):
        refused = _valid({"reply": reply}, allowed)
        assert not refused.ok, reply
        assert "cannot be checked" in refused.violations[0]
    assert unreadable_numbers("1e6 a 2,5E-3 a q1e6") == ["1e6", "2,5E-3"]
    assert _valid({"reply": "Je to 1\u00a0000\u00a0000 lidí."}, allowed).ok


@pytest.mark.parametrize(
    ("reply", "number"),
    [
        ("Zvyšte to 7x.", 7),
        ("Zeptejte se 3krát.", 3),
        ("Cílíme na 18letých.", 18),
        ("Vzorek 1\u00a0200respondentů.", 1200),
        ("Podíl 2,5násobný.", 2.5),
    ],
)
def test_a_number_glued_to_its_word_is_still_read(reply: str, number: float) -> None:
    """The review of baac33d5: ``(?![\\w])`` let a number touching a letter pass unread."""
    refused = _valid({"reply": reply}, canonical_json({"n": 999}))
    assert not refused.ok, reply
    assert _valid({"reply": reply}, canonical_json({"n": number})).ok, reply


def test_an_identifiers_digits_are_still_no_number() -> None:
    """The digits of ``Q1``, ``B2`` or ``goal2`` belong to the identifier, before and after."""
    assert number_tokens("Q1, B2, q3 a brief:goal2, s1.q12") == frozenset()
    assert _valid({"reply": "Otázka Q1 a blok B2 platí."}, canonical_json({"ids": ["Q1"]})).ok


def test_a_number_in_another_field_is_not_the_replys() -> None:
    """The rule reads the reply; an edit's value is a proposal a person accepts."""
    assert _valid(_output(edits=[{"op": "set_n", "value": 300, "why": WHY}]), "").ok


# --------------------------------------------------------------------------- grounding

CONTENT: dict[str, Any] = {
    "title": "Studie",
    "goal": "Cíl",
    "sections": [
        {"id": "s1", "type": "questions", "questions": [{"id": "q1", "text": "Znáte?"}]},
        {"id": "b1", "type": "object_battery", "questions": [{"id": "qb", "text": "Hodnoťte"}]},
    ],
    "research_plan": {"objectives": ["Ověřit  zájem"], "hypotheses": ["H1"]},
}


def test_ground_edits_drops_what_the_content_does_not_hold_and_names_it() -> None:
    output = LeadOutput.model_validate(
        _output(
            edits=[
                {"op": "question_edit", "question_id": "q1", "text": "Znáte značku?", "why": WHY},
                {"op": "question_remove", "question_id": "q9", "why": WHY},
                {"op": "question_remove", "question_id": "qb", "why": WHY},  # a battery's
                {
                    "op": "question_add",
                    "section_id": "s9",
                    "text": "Q",
                    "qtype": "otevrena",
                    "why": WHY,
                },
                {
                    "op": "question_add",
                    "section_id": "s1",
                    "text": "Q",
                    "qtype": "otevrena",
                    "why": WHY,
                },
                {
                    "op": "list_remove",
                    "list": "plan.objectives",
                    "old": " ověřit zájem ",
                    "why": WHY,
                },
                {
                    "op": "list_replace",
                    "list": "plan.objectives",
                    "old": "Nic",
                    "value": "X",
                    "why": WHY,
                },
                {"op": "list_add", "list": "plan.hypotheses", "value": "h1", "why": WHY},
                {"op": "set_n", "value": 300, "why": WHY},
            ]
        )
    )
    kept, dropped = ground_edits(output, CONTENT)
    assert [e.op for e in kept.edits] == ["question_edit", "question_add", "list_remove", "set_n"]
    assert [(d.index, d.reason) for d in dropped] == [
        (1, "unknown_question"),
        (2, "unknown_question"),
        (3, "unknown_section"),
        (6, "unknown_item"),
        (7, "already_present"),
    ]


def test_plan_lists_are_read_from_the_analysis_first() -> None:
    output = LeadOutput.model_validate(
        _output(
            edits=[{"op": "list_remove", "list": "plan.objectives", "old": "Z analýzy", "why": WHY}]
        )
    )
    kept, dropped = ground_edits(output, CONTENT, {"objectives": ["Z analýzy"]})
    assert len(kept.edits) == 1 and dropped == []
    kept, dropped = ground_edits(output, CONTENT)
    assert kept.edits == [] and dropped[0].reason == "unknown_item"


def test_a_forget_reaches_only_notes_the_turn_was_shown() -> None:
    update = SelfUpdate(forget=["LMM-aa", "LMM-bb", "LMM-aa"], remember=[])
    kept, dropped = ground_self_update(update, ["LMM-aa"])
    assert kept is not None and kept.forget == ["LMM-aa"]
    assert [(d.index, d.reason) for d in dropped] == [(1, "unknown_memory"), (2, "unknown_memory")]
    nothing, _ = ground_self_update(SelfUpdate(forget=["LMM-cc"]), [])
    assert nothing is None  # an update with nothing left is no update
    assert ground_self_update(None, []) == (None, [])


SHOWN_NOTES: list[dict[str, Any]] = [
    {"memory_id": "LMM-aa", "scope": "client", "text": "Klientská stará"},
    {"memory_id": "LMM-bb", "scope": "personal", "text": "Osobní stará"},
]


def test_only_what_stays_inside_the_turns_client_applies_at_once() -> None:
    """Codex P1 on #484: a personal note or a file change reaches every client's studies, so
    it waits for the researcher; client notes and forgetting a client note apply with the
    turn."""
    update = SelfUpdate.model_validate(
        {
            "name": "Můj",
            "soul": "# S",
            "user": "U",
            "remember": [
                {"scope": "client", "text": "Klientská"},
                {"scope": "personal", "text": "Osobní"},
            ],
            "forget": ["LMM-aa"],
        }
    )
    now, waits = split_self_update(update, SHOWN_NOTES)
    assert now is not None and waits is not None
    assert [(n.scope, n.text) for n in now.remember] == [("client", "Klientská")]
    assert now.forget == ["LMM-aa"] and (now.name, now.soul, now.user) == (None, None, None)
    assert [(n.scope, n.text) for n in waits.remember] == [("personal", "Osobní")]
    assert (waits.name, waits.soul, waits.user, waits.forget) == ("Můj", "# S", "U", [])
    only_client = SelfUpdate.model_validate({"remember": [{"scope": "client", "text": "K"}]})
    assert split_self_update(only_client, SHOWN_NOTES)[1] is None
    only_personal = SelfUpdate.model_validate({"remember": [{"scope": "personal", "text": "P"}]})
    assert split_self_update(only_personal, SHOWN_NOTES)[0] is None
    assert split_self_update(None, SHOWN_NOTES) == (None, None)


def test_forgetting_a_personal_note_waits_for_the_researcher() -> None:
    """The review of baac33d5: a personal note loads into every client's studies, so dropping
    it changes them all, as keeping one does; only a client note's forget applies now. A
    forget the shown notes do not name as a client note waits too (unknown is not client)."""
    update = SelfUpdate.model_validate({"forget": ["LMM-bb", "LMM-aa", "LMM-cc"]})
    now, waits = split_self_update(update, SHOWN_NOTES)
    assert now is not None and now.forget == ["LMM-aa"]
    assert waits is not None and waits.forget == ["LMM-bb", "LMM-cc"]
    only_personal = SelfUpdate.model_validate({"forget": ["LMM-bb"]})
    assert split_self_update(only_personal, SHOWN_NOTES) == (None, only_personal)
    assert waiting_self_update(waits.model_dump(mode="json"), SHOWN_NOTES) == {
        "name": None,
        "soul": None,
        "user": None,
        "remember": [],
        "forget": [
            {"memory_id": "LMM-bb", "text": "Osobní stará"},
            {"memory_id": "LMM-cc", "text": None},
        ],
    }
    assert waiting_self_update(None, SHOWN_NOTES) is None


# --------------------------------------------------------------------------- applying an edit


def _edit(**fields: Any) -> Any:
    return LeadOutput.model_validate(_output(edits=[{"why": WHY, **fields}])).edits[0]


def test_a_brief_edit_clears_the_analysis_and_a_title_edit_keeps_it() -> None:
    analysis = {"objectives": ["A"]}
    content, kept = apply_edit(CONTENT, analysis, _edit(op="set_text", field="title", value="T"))
    assert content["title"] == "T" and kept == analysis
    for field in ("goal", "decision_use", "briefing.situation", "briefing.constraints"):
        applied = apply_edit(CONTENT, analysis, _edit(op="set_text", field=field, value="V"))
        assert not isinstance(applied, Refused)
        content, cleared = applied
        assert cleared is None, field
    content, _ = apply_edit(
        {**CONTENT, "briefing": {"situation": "old", "other": "kept"}},
        None,
        _edit(op="set_text", field="briefing.situation", value="new"),
    )
    assert content["briefing"] == {"situation": "new", "other": "kept"}
    assert CONTENT.get("briefing") is None  # the input is not changed


def test_the_plan_narrative_is_written_to_both_homes_and_marked_manual() -> None:
    content, analysis = apply_edit(
        CONTENT, None, _edit(op="set_text", field="plan.problem_summary", value="Shrnutí")
    )
    assert content["research_plan"]["problem_summary"] == "Shrnutí"
    # With no analysis, it starts from the plan.
    assert analysis == {**CONTENT["research_plan"], "problem_summary": "Shrnutí"}
    assert content["ui_state"]["plan_manual_changed"] is True

    content, analysis = apply_edit(
        CONTENT,
        {"objectives": ["Ověřit zájem"], "complexity": "short"},
        _edit(op="list_replace", list="plan.objectives", old="OVĚŘIT   zájem", value="Nový"),
    )
    assert content["research_plan"]["objectives"] == ["Nový"]
    assert analysis == {"objectives": ["Nový"], "complexity": "short"}


def test_list_edits_refuse_what_they_cannot_find_or_already_hold() -> None:
    assert apply_edit(
        CONTENT, None, _edit(op="list_add", list="plan.hypotheses", value=" h1 ")
    ) == Refused(reason="already_present")
    assert apply_edit(
        CONTENT, None, _edit(op="list_remove", list="plan.hypotheses", old="H2")
    ) == Refused(reason="unknown_item")
    content, analysis = apply_edit(
        CONTENT, None, _edit(op="list_remove", list="plan.hypotheses", old="h1")
    )
    assert content["research_plan"]["hypotheses"] == [] and analysis["hypotheses"] == []
    content, _ = apply_edit(
        CONTENT, None, _edit(op="list_add", list="plan.research_questions", value="Proč?")
    )
    assert content["research_plan"]["research_questions"] == ["Proč?"]


@pytest.mark.parametrize(
    "qtype,options,expected",
    [
        (
            "skala",
            ["málo", "hodně"],
            {"typ": "skala", "skala": [1, 10], "popisky_skaly": ["málo", "hodně"]},
        ),
        ("skala", [], {"typ": "skala", "skala": [1, 10], "popisky_skaly": ["vůbec", "zcela"]}),
        ("otevrena", [], {"typ": "otevrena"}),
        ("vyber", ["A", "B"], {"typ": "vyber", "kategorie": ["A", "B"]}),
        ("multi", ["A", "B", "C"], {"typ": "multi", "kategorie": ["A", "B", "C"]}),
    ],
)
def test_question_add_writes_the_webs_question_shape(
    qtype: str, options: list[str], expected: dict[str, Any]
) -> None:
    content, _ = apply_edit(
        CONTENT, None, _edit(op="question_add", text="Otázka", qtype=qtype, options=options)
    )
    added = content["sections"][0]["questions"][-1]
    assert added["id"].startswith("Q_") and added["text"] == "Otázka"
    assert added["povolit_nevim"] is False
    assert {k: v for k, v in added.items() if k not in ("id", "text", "povolit_nevim")} == expected


@pytest.mark.parametrize(
    "qtype,options,reason",
    [
        ("otevrena", ["A"], "options_on_open_question"),
        ("otevrena", ["A", "B"], "options_on_open_question"),
        ("skala", ["jen jeden konec"], "scale_labels_not_two"),
        ("skala", ["a", "b", "c"], "scale_labels_not_two"),
        ("vyber", ["Jediná"], "too_few_options"),
        ("multi", [], "too_few_options"),
    ],
)
def test_a_new_question_carries_only_options_it_can_keep(
    qtype: str, options: list[str], reason: str
) -> None:
    """Codex P2 on #484: options shown to the researcher and silently dropped on accept."""
    edit = {"op": "question_add", "text": "Q", "qtype": qtype, "options": options, "why": WHY}
    assert not _valid(_output(edits=[edit])).ok
    assert question_add_problem(qtype, options) == reason
    # An output stored before the contract said so: refused when applied, dropped when grounded.
    stored = QuestionAdd.model_construct(
        op="question_add", section_id=None, text="Q", qtype=qtype, options=options, why=WHY
    )
    assert apply_edit(CONTENT, None, stored) == Refused(reason=reason)
    output = LeadOutput.model_construct(
        reply="x", view=[], edits=[stored], request=None, follow=[], self_update=None
    )
    kept, dropped = ground_edits(output, CONTENT)
    assert kept.edits == [] and [d.reason for d in dropped] == [reason]


@pytest.mark.parametrize(
    "qtype,options",
    [("otevrena", []), ("skala", []), ("skala", ["málo", "hodně"]), ("vyber", ["A", "B"])],
)
def test_options_a_new_question_keeps_are_accepted(qtype: str, options: list[str]) -> None:
    edit = {"op": "question_add", "text": "Q", "qtype": qtype, "options": options, "why": WHY}
    assert _valid(_output(edits=[edit])).ok
    assert question_add_problem(qtype, options) is None


def test_question_add_goes_to_the_named_or_first_questions_section_or_a_new_one() -> None:
    assert apply_edit(
        CONTENT, None, _edit(op="question_add", section_id="b1", text="Q", qtype="otevrena")
    ) == Refused(reason="unknown_section")
    content, _ = apply_edit(
        {"sections": [{"id": "b1", "type": "object_battery"}]},
        None,
        _edit(op="question_add", text="Q", qtype="otevrena"),
    )
    created = content["sections"][-1]
    assert created["id"].startswith("sec_") and created["type"] == "questions"
    assert (created["title"], created["purpose"]) == ("Hlavní otázky", "")
    assert len(created["questions"]) == 1


def test_question_edit_sets_text_and_options_only_for_selection_questions() -> None:
    content = {
        "sections": [
            {
                "id": "s1",
                "type": "questions",
                "questions": [
                    {"id": "v", "text": "a", "typ": "vyber", "kategorie": ["x", "y"]},
                    {"id": "o", "text": "b", "typ": "otevrena"},
                ],
            }
        ]
    }
    edited, _ = apply_edit(
        content, None, _edit(op="question_edit", question_id="v", options=["1", "2"])
    )
    assert edited["sections"][0]["questions"][0] == {
        "id": "v",
        "text": "a",
        "typ": "vyber",
        "kategorie": ["1", "2"],
    }
    edited, _ = apply_edit(content, None, _edit(op="question_edit", question_id="o", text="c"))
    assert edited["sections"][0]["questions"][1] == {"id": "o", "text": "c", "typ": "otevrena"}
    removed, _ = apply_edit(content, None, _edit(op="question_remove", question_id="o"))
    assert [q["id"] for q in removed["sections"][0]["questions"]] == ["v"]
    assert apply_edit(content, None, _edit(op="question_remove", question_id="z")) == Refused(
        reason="unknown_question"
    )


@pytest.mark.parametrize("typ", ["otevrena", "skala", None])
def test_options_on_a_question_that_has_none_are_refused_not_accepted_as_nothing(
    typ: str | None,
) -> None:
    """Codex P2 on #484: an options-only edit of an open or scale question changed nothing
    and was recorded as accepted."""
    question: dict[str, Any] = {"id": "o", "text": "b"}
    if typ is not None:
        question["typ"] = typ
    content = {"sections": [{"id": "s1", "type": "questions", "questions": [question]}]}
    for edit in (
        _edit(op="question_edit", question_id="o", options=["1", "2"]),
        _edit(op="question_edit", question_id="o", text="nový", options=["1", "2"]),
    ):
        assert apply_edit(content, None, edit) == Refused(reason="options_on_non_selection")
        output = LeadOutput.model_validate(_output(edits=[edit.model_dump()]))
        kept, dropped = ground_edits(output, content)
        assert kept.edits == [] and [d.reason for d in dropped] == ["options_on_non_selection"]


def test_a_selection_question_keeps_at_least_two_options() -> None:
    """Codex P2 on #484: a replacement with fewer than two options left no real choice."""
    for options in ([], ["Jen jedna"]):
        assert not _valid(
            _output(
                edits=[{"op": "question_edit", "question_id": "v", "options": options, "why": WHY}]
            )
        ).ok
    content = {
        "sections": [
            {
                "id": "s1",
                "type": "questions",
                "questions": [{"id": "v", "text": "a", "typ": "multi", "kategorie": ["x", "y"]}],
            }
        ]
    }
    # An output stored before the contract said so is refused when applied, too.
    stored = QuestionEdit.model_construct(
        op="question_edit", question_id="v", text=None, options=["Jen jedna"], why=WHY
    )
    assert apply_edit(content, None, stored) == Refused(reason="too_few_options")
    kept, dropped = ground_edits(
        LeadOutput.model_validate(
            _output(
                edits=[
                    {"op": "question_edit", "question_id": "v", "options": ["1", "2"], "why": WHY}
                ]
            )
        ),
        content,
    )
    assert len(kept.edits) == 1 and dropped == []


def test_set_n_sets_the_sample_size() -> None:
    content, analysis = apply_edit(CONTENT, {"a": 1}, _edit(op="set_n", value=800))
    assert content["n"] == 800 and analysis == {"a": 1}


# --------------------------------------------------------------------------- the context

APPROVED_DESIGN = {"title": "Fiktivní", "goal": "Test"}


def _context(**overrides: Any) -> dict[str, Any]:
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    fields: dict[str, Any] = {
        "prompt": slot.baseline_pin(),
        "lead": {
            "name": DEFAULT_LEAD_NAME,
            "soul": DEFAULT_SOUL,
            "user": "",
            "notes": [],
            "first_conversation": True,
        },
        "knowledge": [],
        "omitted_knowledge_ids": [],
        "study": {
            "name": "S",
            "client_name": "C",
            "budget_usd": 25.0,
            "spent_usd": 0.0,
            "spend_confirm_usd": None,
        },
        "design": {
            "workspace_revision": 1,
            "design_revision_id": "REV-1",
            "content": APPROVED_DESIGN,
            "analysis": None,
        },
        "runs": [],
        "view": {"kind": "greeting", "stage": "brief", "focus": None, "message": None},
        "conversation": [],
    }
    fields.update(overrides)
    return freeze_context(**fields)


def test_the_context_holds_its_layers_in_the_adrs_order() -> None:
    context = _context()
    assert [entry["layer"] for entry in context["layers"]] == [
        "prompt",
        "lead",
        "knowledge",
        "study",
        "design",
        "runs",
        "view",
        "conversation",
    ]
    # The prompt is the system turn; the model's user turn is every other layer.
    assert '"layer":"prompt"' not in model_message(context)


def test_only_the_newest_twelve_turns_are_kept_and_the_oldest_go_first() -> None:
    turns = [{"actor": "person", "stage": "brief", "text": f"zpráva {i}"} for i in range(20)]
    kept = layer(_context(conversation=turns), "conversation")
    assert [t["text"] for t in kept["turns"]] == [f"zpráva {i}" for i in range(8, 20)]
    assert kept["omitted_turns"] == 8

    big = [{"actor": "person", "stage": "brief", "text": "x" * 4000} for _ in range(12)]
    design = {**APPROVED_DESIGN, "notes": "y" * (CONTEXT_MAX_BYTES - 30_000)}
    context = _context(
        conversation=big,
        design={
            "workspace_revision": 1,
            "design_revision_id": "R",
            "content": design,
            "analysis": None,
        },
    )
    assert context_bytes(context) <= CONTEXT_MAX_BYTES
    trimmed = layer(context, "conversation")
    assert 0 < len(trimmed["turns"]) < 12 and trimmed["omitted_turns"] == 12 - len(trimmed["turns"])


def test_a_context_over_its_bound_with_no_turn_left_is_refused() -> None:
    design = {"notes": "y" * CONTEXT_MAX_BYTES}
    with pytest.raises(LeadContextTooLarge):
        _context(
            design={
                "workspace_revision": 1,
                "design_revision_id": "R",
                "content": design,
                "analysis": None,
            }
        )


def _approve(value: Any, data_class: DataClass = DataClass.CLASS_C_INTERNAL) -> MaterialApproval:
    return MaterialApproval(
        sha256=material_sha256(value),
        data_class=data_class,
        provenance="generated by this test; no client input",
    )


IDENTITY = _approve({"study": "S", "client": "C"})
DESIGN_OK = _approve(APPROVED_DESIGN)


def _request(context: dict[str, Any], *approvals: MaterialApproval) -> Any:
    return lead_request(
        context, policy_version="p1", max_output_tokens=1500, material_approvals=approvals
    )


def test_the_request_is_the_research_reasoning_capability_with_no_tools_and_one_repair() -> None:
    request = _request(_context(), IDENTITY, DESIGN_OK)
    agent = request.agent
    assert agent.capability is ModelCapability.RESEARCH_REASONING
    assert agent.capability is not ModelCapability.RESEARCH_LEAD
    assert agent.allowed_tools == frozenset() and agent.schema_repair_attempts == 1
    assert request.system == lead_prompt() and request.system.startswith(FIXED_PREFIX)
    assert request.data_classification is DataClass.CLASS_C_INTERNAL


def test_unclassified_material_refuses_dispatch_whatever_else_is_known() -> None:
    assert _request(_context(), IDENTITY).data_classification is None  # the design
    assert _request(_context(), DESIGN_OK).data_classification is None  # the study's identity
    message = _context(
        view={"kind": "message", "stage": "brief", "focus": None, "message": "Nová zpráva"}
    )
    assert _request(message, IDENTITY, DESIGN_OK).data_classification is None
    assert (
        _request(message, IDENTITY, DESIGN_OK, _approve("Nová zpráva")).data_classification
        is DataClass.CLASS_C_INTERNAL
    )


def test_an_unapproved_focus_label_refuses_dispatch_like_a_message() -> None:
    """The review of baac33d5: the focus label is text from the browser that reached the
    model unclassified."""
    view = {
        "kind": "message",
        "stage": "brief",
        "focus": {"id": "question:q1", "label": "Acme: tajný plán"},
        "message": "Nová zpráva",
    }
    message = _approve("Nová zpráva")
    assert _request(_context(view=view), IDENTITY, DESIGN_OK, message).data_classification is None
    label = _approve("Acme: tajný plán", DataClass.CLASS_A_CLIENT_CONFIDENTIAL)
    assert (
        _request(_context(view=view), IDENTITY, DESIGN_OK, message, label).data_classification
        is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    )
    unlabelled = {**view, "focus": {"id": "question:q1", "label": ""}}
    assert (
        _request(_context(view=unlabelled), IDENTITY, DESIGN_OK, message).data_classification
        is DataClass.CLASS_C_INTERNAL
    )


def test_knowledge_and_client_notes_make_the_turn_class_a() -> None:
    knowledge = [{"item_id": "K1", "revision": 1, "kind": "FACT", "title": "t", "summary": "s"}]
    assert (
        _request(_context(knowledge=knowledge), IDENTITY, DESIGN_OK).data_classification
        is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    )
    note = {"memory_id": "LMM-1", "scope": "client", "text": "Klient chce rychle."}
    lead = {
        "name": DEFAULT_LEAD_NAME,
        "soul": DEFAULT_SOUL,
        "user": "",
        "notes": [note],
        "first_conversation": False,
    }
    approved_note = _approve("Klient chce rychle.")
    assert (
        _request(_context(lead=lead), IDENTITY, DESIGN_OK, approved_note).data_classification
        is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    )
    personal = {**lead, "notes": [{**note, "scope": "personal"}]}
    assert (
        _request(_context(lead=personal), IDENTITY, DESIGN_OK, approved_note).data_classification
        is DataClass.CLASS_C_INTERNAL
    )
    # An unclassified note, or a changed SOUL, refuses like any unclassified material.
    assert _request(_context(lead=personal), IDENTITY, DESIGN_OK).data_classification is None
    souled = {**lead, "notes": [], "soul": "# Jiná povaha"}
    assert _request(_context(lead=souled), IDENTITY, DESIGN_OK).data_classification is None


def test_an_earlier_reply_carries_the_class_its_turn_was_sent_as() -> None:
    reply = {"actor": "lead", "stage": "brief", "reply": "Ahoj.", "data_class": "CLASS_C_INTERNAL"}
    assert (
        _request(_context(conversation=[reply]), IDENTITY, DESIGN_OK).data_classification
        is DataClass.CLASS_C_INTERNAL
    )
    unknown = {**reply, "data_class": None}
    assert (
        _request(_context(conversation=[unknown]), IDENTITY, DESIGN_OK).data_classification is None
    )


def test_a_dataset_in_the_knowledge_declares_its_lineage() -> None:
    knowledge = [{"item_id": "K1", "revision": 1, "kind": "DATASET", "title": "t", "summary": "s"}]
    request = _request(_context(knowledge=knowledge), IDENTITY, DESIGN_OK)
    assert request.data_lineage is not None and request.data_lineage.datasets


def test_the_window_bounds_a_turn_and_its_repair() -> None:
    assert lead_request_window_tokens(1500) > CONTEXT_MAX_BYTES + 5 * 1500
    assert lead_request_window_tokens(3000) - lead_request_window_tokens(1500) == 5 * 1500
