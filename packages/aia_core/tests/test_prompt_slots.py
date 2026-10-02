"""The prompt registry and the pin: what is editable, and that nothing else moved.

The baseline is the contract with the past: wiring prompts as data must not change a
byte the model was sent before an administrator edits anything.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_respondent import PROMPT_SHA256, SYSTEM_PROMPT
from aia_core.domain.prompt_slots import get_slot, slots, wired_prompt_ids
from aia_core.domain.prompts import (
    PROMPT_TEXT_MAX_CHARS,
    PromptPin,
    PromptRejected,
    prompt_sha256,
    stored_version_label,
    validate_prompt_text,
)
from aia_core.domain.research_agents import (
    BASELINE_PROMPT_VERSION,
    FIXED_PREFIX,
    ResearchAction,
    agent_request,
    prompt_for,
)

SNAPSHOT = {"design": {"title": "Fictional"}, "knowledge": [], "omitted_knowledge_ids": []}


def _request(action: ResearchAction, *, prompt: PromptPin | None = None):
    return agent_request(
        action,
        SNAPSHOT,
        instruction="",
        policy_version="p1",
        max_output_tokens=1000,
        prompt=prompt,
    )


# ------------------------------------------------------------------ the registry


def test_every_research_action_is_a_wired_slot() -> None:
    expected = {f"aia.research.{a.value}" for a in ResearchAction}
    assert expected <= wired_prompt_ids()
    assert wired_prompt_ids() == expected  # nothing else claims to be editable yet


def test_ids_are_unique() -> None:
    ids = [s.prompt_id for s in slots()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("action", list(ResearchAction))
def test_baseline_renders_byte_identical_to_the_prompt_the_code_always_sent(
    action: ResearchAction,
) -> None:
    slot = get_slot(f"aia.research.{action.value}")
    assert slot is not None and slot.wired
    assert slot.assemble(slot.baseline_text) == prompt_for(action)
    assert slot.fixed_prefix == FIXED_PREFIX
    assert slot.baseline_version == BASELINE_PROMPT_VERSION
    assert slot.baseline_pin().text_sha256 == prompt_sha256(slot.baseline_text)


@pytest.mark.parametrize("action", list(ResearchAction))
def test_no_pin_sends_the_baseline_as_version_one(action: ResearchAction) -> None:
    request = _request(action)
    assert request.system == prompt_for(action)
    assert request.agent.prompt_id == f"aia.research.{action.value}"
    assert request.agent.prompt_version == "1"


def test_a_stored_pin_replaces_only_the_task_and_keeps_the_rails() -> None:
    pin = PromptPin.of(
        prompt_id="aia.research.critique_design",
        version=stored_version_label(3),
        origin="stored",
        text="Zkritizuj návrh stručně.",
    )
    request = _request(ResearchAction.CRITIQUE, prompt=pin)
    assert request.system == FIXED_PREFIX + "Zkritizuj návrh stručně."
    assert request.system.startswith(FIXED_PREFIX)  # the rails are not editable
    assert request.agent.prompt_version == "e3"
    assert request.agent.prompt_id == "aia.research.critique_design"


def test_a_pin_for_another_prompt_is_refused() -> None:
    pin = PromptPin.of(
        prompt_id="aia.research.analyze_brief", version="e1", origin="stored", text="x"
    )
    with pytest.raises(ValueError, match="does not belong"):
        _request(ResearchAction.CRITIQUE, prompt=pin)


def test_the_build_prompt_must_keep_the_placeholder_its_contract_validates() -> None:
    slot = get_slot("aia.research.build_questionnaire")
    assert slot is not None
    assert "{object}" in slot.baseline_text  # the baseline itself keeps it
    with pytest.raises(PromptRejected) as refused:
        slot.check("Sestav dotazník bez zástupného znaku.")
    assert refused.value.reason == "missing_required_text"
    assert slot.check("  Sestav dotazník; baterie má otázku s {object}.  ").startswith("Sestav")


def test_unwired_slots_are_listed_with_a_reason_and_their_baseline() -> None:
    respondent = get_slot("aia.respondent.block")
    assert respondent is not None and not respondent.wired
    assert respondent.unwired_reason == "feeds_a_reuse_fingerprint"
    assert respondent.baseline_text == SYSTEM_PROMPT
    assert prompt_sha256(respondent.baseline_text) == PROMPT_SHA256  # same identity as provenance
    for slot in slots():
        if not slot.wired:
            assert slot.baseline_text.strip()
    assert get_slot("aia.nope") is None


# ------------------------------------------------------------------ validation


def test_validation_trims_the_edges_and_keeps_the_inside() -> None:
    assert validate_prompt_text("  a\n\n  b  \n") == "a\n\n  b"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"),
        ("   \n\t ", "empty"),
        ("a\x00b", "invalid_character"),
        ("x" * (PROMPT_TEXT_MAX_CHARS + 1), "too_long"),
    ],
)
def test_validation_refuses(text: str, reason: str) -> None:
    with pytest.raises(PromptRejected) as refused:
        validate_prompt_text(text)
    assert refused.value.reason == reason


def test_the_length_limit_is_inclusive() -> None:
    assert len(validate_prompt_text("x" * PROMPT_TEXT_MAX_CHARS)) == PROMPT_TEXT_MAX_CHARS


def test_stored_versions_cannot_collide_with_baseline_versions() -> None:
    assert stored_version_label(1) == "e1"
    for slot in slots():
        assert slot.baseline_version != stored_version_label(1)
    with pytest.raises(ValueError):
        stored_version_label(0)


# ------------------------------------------------------------------ the pin


def test_a_pin_whose_text_was_altered_is_refused() -> None:
    pin = PromptPin.of(prompt_id="aia.research.copilot", version="e1", origin="stored", text="a")
    tampered = pin.model_dump()
    tampered["text"] = "b"
    with pytest.raises(ValidationError, match="does not match its hash"):
        PromptPin(**tampered)


def test_a_pin_hash_is_sha256_of_the_utf8_text() -> None:
    pin = PromptPin.of(prompt_id="p", version="v", origin="baseline", text="Čeština ✓")
    assert pin.text_sha256 == hashlib.sha256("Čeština ✓".encode()).hexdigest()


def test_a_pin_is_closed_and_frozen() -> None:
    pin = PromptPin.of(prompt_id="p", version="v", origin="baseline", text="a")
    with pytest.raises(ValidationError):
        PromptPin(**{**pin.model_dump(), "extra": 1})
    with pytest.raises(ValidationError):
        pin.text = "b"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        PromptPin.of(prompt_id="", version="v", origin="baseline", text="a")
