"""Regression checks for failures observed in the fictional develop sandbox.

These validate guidance examples and the unchanged rejection boundaries. They
do not assert that prose instructions guarantee a model's compliance.
"""

import json

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.agents import AgentRole, agent_definition, prompt_for
from aia_core.domain.deep_research.synthesizer import BRIEF_TASK, BriefProposal
from aia_core.domain.prompt_slots import get_slot, slots
from aia_core.domain.research_agents import Advice, ResearchAction, baseline_task


@pytest.mark.parametrize("action", [ResearchAction.CRITIQUE, ResearchAction.MEMORY])
def test_advice_guidance_example_matches_the_actual_contract(action: ResearchAction) -> None:
    task = baseline_task(action)
    start = task.index('{"answer":')
    example, _ = json.JSONDecoder().raw_decode(task[start:])
    advice = Advice.model_validate(example)
    assert advice.source_ids == []
    assert isinstance(advice.followup_questions, list)
    assert isinstance(advice.limitations, list)
    # The original paid-call failure remains a rejection, never coercion.
    with pytest.raises(ValidationError):
        Advice.model_validate({**example, "limitations": "Missing results"})


def test_brief_guidance_uses_the_current_contract_bounds_and_keeps_them_enforced() -> None:
    summary_bound = BriefProposal.model_json_schema()["properties"]["summary"]["maxLength"]
    assert str(summary_bound) in BRIEF_TASK
    valid = {
        "summary": "Služby popisuje přijatý zdroj; nejde o výsledek panelu.",
        "answers": [
            {"subject_key": "services", "text": "Doložená nabídka.", "evidence_ids": ["E1"]}
        ],
        "conflict_notes": [],
        "limitations": ["Nelze z toho odvodit využívání služeb."],
    }
    BriefProposal.model_validate(valid)
    answer_schema = BriefProposal.model_json_schema()["$defs"]["BriefAnswerDraft"]
    answer_bound = answer_schema["properties"]["text"]["maxLength"]
    assert str(answer_bound) in BRIEF_TASK
    with pytest.raises(ValidationError):
        BriefProposal.model_validate(
            {**valid, "answers": [{**valid["answers"][0], "text": "x" * (answer_bound + 1)}]}
        )
    with pytest.raises(ValidationError):
        BriefProposal.model_validate({**valid, "limitations": "Not an array"})


@pytest.mark.parametrize("role", list(AgentRole))
def test_catalogue_reports_the_actual_role_version(role: AgentRole) -> None:
    agent = agent_definition(role, max_output_tokens=2048)
    slot = get_slot(agent.prompt_id)
    assert slot is not None
    assert slot.baseline_version == agent.prompt_version
    assert agent.prompt_version == ("5" if role is AgentRole.INVESTIGATOR else "2")


def test_every_live_editable_task_passes_the_same_store_validation() -> None:
    editable = [s for s in slots() if s.wired]
    assert len(editable) == len(ResearchAction)
    for slot in editable:
        assert slot.check(slot.baseline_text) == slot.baseline_text.strip()
        assert slot.baseline_version == "2"


def test_wikipedia_guidance_names_its_scope_and_requires_reading_original_sources() -> None:
    task = prompt_for(AgentRole.INVESTIGATOR)
    assert "search_scope" in task and "lang en" in task
    assert "bibliografický odkaz nejsou přečtenou studií" in task
    assert "původní studie" in task
