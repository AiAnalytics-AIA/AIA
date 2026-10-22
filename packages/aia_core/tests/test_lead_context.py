"""The Lead's declared layers and a turn's manifest (ADR 0041 decisions 2-3, plan
lead-conversation LC1)."""

from __future__ import annotations

from typing import Any

from aia_core.domain.lead_context import (
    LEAD_LAYERS,
    MANIFEST_IDS_MAX,
    PART_LAYERS,
    context_manifest,
)
from aia_core.domain.prompt_slots import get_slot
from aia_core.domain.research_lead import (
    CONTEXT_MAX_BYTES,
    DEFAULT_LEAD_NAME,
    DEFAULT_SOUL,
    EXTERNAL_LAYER,
    HISTORY_TURNS,
    LEAD_PROMPT_ID,
    context_bytes,
    context_classification,
    context_sha256,
    freeze_context,
    layer,
)
from aia_core.domain.residency import DataClass


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
            "content": {"title": "Fiktivní", "goal": "Test"},
            "analysis": None,
        },
        "runs": [],
        "view": {"kind": "greeting", "stage": "brief", "focus": None, "message": None},
        "conversation": [],
    }
    fields.update(overrides)
    return freeze_context(**fields)


def _row(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    return next(r for r in manifest["layers"] if r["layer"] == name)


def test_every_layer_of_the_context_is_declared_in_its_order() -> None:
    external = {"pin": {"deep_research_run_id": "RUN-1"}, "lines": ["[EV-1] Fiktivní nález."]}
    context = _context(external=external)
    assert [entry["layer"] for entry in context["layers"]] == [s.name for s in LEAD_LAYERS]
    manifest = context_manifest(context, context_classification(context, (), _pin()))
    row = _row(manifest, EXTERNAL_LAYER)
    assert row["bound"] is not None
    assert row["data_class"] == DataClass.CLASS_C_INTERNAL.value


def _pin() -> Any:
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    return slot.baseline_pin()


def test_every_classified_part_belongs_to_a_declared_layer() -> None:
    names = {s.name for s in LEAD_LAYERS}
    assert set(PART_LAYERS.values()) <= names


def test_the_manifest_reads_the_context_without_moving_it() -> None:
    context = _context()
    before = context_sha256(context)
    manifest = context_manifest(context)
    assert context_sha256(context) == before
    assert manifest == context_manifest(context)
    assert manifest["total_bytes"] == context_bytes(context)
    assert manifest["ceiling_bytes"] == CONTEXT_MAX_BYTES
    # The external layer is there only when a Design Research run's findings are.
    assert [r["layer"] for r in manifest["layers"]] == [
        s.name for s in LEAD_LAYERS if s.name != EXTERNAL_LAYER
    ]
    assert sum(r["bytes"] for r in manifest["layers"]) <= manifest["total_bytes"]


def test_knowledge_left_out_is_named_with_its_reason() -> None:
    items = [
        {"item_id": f"K-{i}", "revision": 1, "kind": "FACT", "title": "t", "summary": "s"}
        for i in range(3)
    ]
    manifest = context_manifest(_context(knowledge=items, omitted_knowledge_ids=["K-9", "K-8"]))
    row = _row(manifest, "knowledge")
    assert row["included"] == ["K-0", "K-1", "K-2"]
    assert row["omitted"] == [
        {"id": "K-9", "reason": "over_budget"},
        {"id": "K-8", "reason": "over_budget"},
    ]
    assert row["omitted_count"] == 2
    assert row["ceiling_bytes"] is not None


def test_turns_outside_the_history_window_are_counted() -> None:
    conversation = [
        {"actor": "person", "stage": "brief", "text": f"zpráva {i}"}
        for i in range(HISTORY_TURNS + 3)
    ]
    manifest = context_manifest(_context(conversation=conversation))
    row = _row(manifest, "conversation")
    assert row["omitted_count"] == 3
    assert row["omitted"] == []
    assert len(layer(_context(conversation=conversation), "conversation")["turns"]) == HISTORY_TURNS


def test_a_layer_lists_at_most_the_bound_and_counts_the_rest() -> None:
    omitted = [f"K-{i}" for i in range(MANIFEST_IDS_MAX + 20)]
    row = _row(context_manifest(_context(omitted_knowledge_ids=omitted)), "knowledge")
    assert len(row["omitted"]) == MANIFEST_IDS_MAX
    assert row["omitted_count"] == MANIFEST_IDS_MAX + 20


def test_the_manifest_is_bounded_by_layers_not_history() -> None:
    small = context_manifest(_context(omitted_knowledge_ids=[f"K-{i}" for i in range(100)]))
    large = context_manifest(_context(omitted_knowledge_ids=[f"K-{i}" for i in range(1000)]))
    # Ten times the history leaves the stored manifest the same size, but for its counts.
    assert abs(len(str(small)) - len(str(large))) < 20
    assert _row(small, "knowledge")["omitted"] == _row(large, "knowledge")["omitted"]


def test_notes_runs_and_the_focus_are_named_by_id() -> None:
    lead = {
        "name": DEFAULT_LEAD_NAME,
        "soul": DEFAULT_SOUL,
        "user": "",
        "notes": [{"memory_id": "LMM-1", "scope": "personal", "text": "stručně"}],
        "first_conversation": False,
    }
    manifest = context_manifest(
        _context(
            lead=lead,
            runs=[{"run_id": "RUN-1", "status": "SUCCEEDED", "design_revision_id": "REV-1"}],
            view={
                "kind": "message",
                "stage": "questionnaire",
                "focus": {"id": "question:q1", "label": "Otázka 1"},
                "message": "Zkontroluj otázku.",
            },
        )
    )
    assert _row(manifest, "lead")["included"] == ["LMM-1"]
    assert _row(manifest, "runs")["included"] == ["RUN-1"]
    assert _row(manifest, "view")["included"] == ["question:q1"]


def test_without_a_classification_no_layer_claims_a_class() -> None:
    manifest = context_manifest(_context())
    assert all("data_class" not in r for r in manifest["layers"])


def test_each_layer_takes_the_most_restrictive_class_of_its_parts() -> None:
    context = _context(
        knowledge=[{"item_id": "K-1", "revision": 1, "kind": "FACT", "title": "t", "summary": "s"}],
        view={"kind": "message", "stage": "brief", "focus": None, "message": "Ahoj"},
    )
    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None
    classification = context_classification(context, (), slot.baseline_pin())
    manifest = context_manifest(context, classification)
    assert _row(manifest, "knowledge")["data_class"] == DataClass.CLASS_A_CLIENT_CONFIDENTIAL.value
    assert _row(manifest, "design")["data_class"] == DataClass.CLASS_B_DERIVED_CLIENT.value
    assert _row(manifest, "lead")["data_class"] == DataClass.CLASS_C_INTERNAL.value
    assert _row(manifest, "view")["class_sources"]
    # The runs layer has no classified part, so it claims no class.
    assert "data_class" not in _row(manifest, "runs")


def test_a_part_of_unknown_class_makes_its_layer_unknown() -> None:
    context = _context()
    classification = [
        {"part": "design", "data_class": DataClass.CLASS_B_DERIVED_CLIENT.value, "source": "rule"},
        {"part": "design_analysis", "data_class": None, "source": "unknown"},
    ]
    assert _row(context_manifest(context, classification), "design")["data_class"] is None


# ------------------------------------------------------------------ byte bounds (LC1)


def test_the_lead_prompt_slot_bounds_its_pin_in_bytes_not_characters() -> None:
    import pytest

    from aia_core.domain.prompts import PromptRejected
    from aia_core.domain.research_lead import LEAD_PROMPT_MAX_PIN_BYTES

    slot = get_slot(LEAD_PROMPT_ID)
    assert slot is not None and slot.max_pin_bytes == LEAD_PROMPT_MAX_PIN_BYTES
    assert slot.pin_bytes(slot.baseline_text) <= LEAD_PROMPT_MAX_PIN_BYTES
    slot.check("Stručně a česky.")
    with pytest.raises(PromptRejected) as refused:
        slot.check("😀" * 4000)  # 4,000 characters, 16,000 bytes
    assert refused.value.reason == "too_large_for_context"


def test_a_new_answer_over_the_files_byte_bounds_is_refused_and_a_stored_one_still_reads() -> None:
    import pytest
    from pydantic import ValidationError

    from aia_core.domain.research_lead import SOUL_MAX_BYTES, LeadOutput, lead_contract

    wide = {"reply": "Zapamatuji si to.", "self_update": {"soul": "ž" * 1500}}  # 3,000 bytes
    contract = lead_contract("")
    with pytest.raises(ValidationError, match="lead_file_too_large"):
        contract.model_validate(wide)
    contract.model_validate({"reply": "Ano.", "self_update": {"soul": "ž" * (SOUL_MAX_BYTES // 2)}})
    # A turn stored before the bound is read as it was, so its edits and cards stay decidable.
    assert LeadOutput.model_validate(wide).self_update is not None


def test_a_full_notes_layer_is_within_its_ceiling() -> None:
    from aia_core.domain.research_lead import NOTE_MAX_CHARS, NOTES_IN_CONTEXT, notes_layer

    notes = notes_layer(
        [
            {"memory_id": f"LMM-{i:x}", "scope": "personal", "text": "ž" * NOTE_MAX_CHARS}
            for i in range(NOTES_IN_CONTEXT)
        ]
    )
    lead = {
        "name": DEFAULT_LEAD_NAME,
        "soul": "s" * 2000,
        "user": "u" * 2000,
        "notes": notes,
        "first_conversation": False,
    }
    manifest = context_manifest(_context(lead=lead))
    for row in manifest["layers"]:
        if row["ceiling_bytes"] is not None:
            assert row["bounded_bytes"] <= row["ceiling_bytes"], row["layer"]
    assert _row(manifest, "lead")["bytes"] > _row(manifest, "lead")["bounded_bytes"]


def test_every_part_the_classification_emits_maps_to_a_layer() -> None:
    context = _context(
        lead={
            "name": DEFAULT_LEAD_NAME,
            "soul": DEFAULT_SOUL,
            "user": "",
            "notes": [
                {"memory_id": "LMM-1", "scope": "personal", "text": "stručně"},
                {"memory_id": "LMM-2", "scope": "client", "text": "fiktivní klient"},
            ],
            "first_conversation": False,
        },
        knowledge=[{"item_id": "K-1", "revision": 1, "kind": "FACT", "title": "t", "summary": "s"}],
        design={
            "workspace_revision": 1,
            "design_revision_id": "REV-1",
            "content": {"title": "Fiktivní"},
            "analysis": {"objectives": ["Ověřit"]},
        },
        view={
            "kind": "message",
            "stage": "brief",
            "focus": {"id": "brief:goal", "label": "Cíl"},
            "message": "Ahoj",
        },
        conversation=[
            {"actor": "person", "stage": "brief", "text": "Dřív"},
            {
                "actor": "lead",
                "stage": "brief",
                "reply": "Ano",
                "data_class": "CLASS_B_DERIVED_CLIENT",
            },
        ],
        external={"pin": {"deep_research_run_id": "RUN-1"}, "lines": ["[EV-1] Fiktivní."]},
    )
    parts = {p["part"] for p in context_classification(context, (), _pin())}
    assert parts <= set(PART_LAYERS), parts - set(PART_LAYERS)
