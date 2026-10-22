"""The Lead composer's typed start commands, matched by code (lead-orchestration LO5).

The vocabulary is pinned in ``fixtures/lead_commands/commands.json``, which the web reads too;
a near-match is never a command, because a start must be the person's exact typed command and
never a guess at what they meant.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.lead_commands import (
    ANALYSIS_RETRY,
    COMMANDS,
    INSTRUCTION_MAX_CHARS,
    RESEARCH_RUN,
    command_for,
    match_command,
)
from aia_core.domain.research_agents import ResearchAction

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "lead_commands" / "commands.json").read_text("utf-8")
)


def test_the_vocabulary_is_the_fixtures() -> None:
    assert [
        {
            "phrase": c.phrase,
            "start": c.start,
            "label": c.label,
            "takes_instruction": c.takes_instruction,
        }
        for c in COMMANDS
    ] == FIXTURE["commands"]


def test_every_design_worker_the_run_and_the_analysis_retry_has_exactly_one_command() -> None:
    starts = [c.start for c in COMMANDS]
    assert len(starts) == len(set(starts))
    assert sorted(starts) == sorted(
        [f"agent_job:{a.value}" for a in ResearchAction] + [RESEARCH_RUN, ANALYSIS_RETRY]
    )
    phrases = [c.phrase.casefold() for c in COMMANDS]
    assert len(phrases) == len(set(phrases))
    for command in COMMANDS:
        assert command_for(command.start) is command
        assert (command.action is None) == (command.start in {RESEARCH_RUN, ANALYSIS_RETRY})
    assert command_for("design_research") is None


@pytest.mark.parametrize("case", FIXTURE["matches"], ids=lambda c: c["text"])
def test_a_typed_command_is_matched(case: dict[str, str]) -> None:
    matched = match_command(case["text"])
    assert matched is not None
    assert (matched.start, matched.instruction) == (case["start"], case["instruction"])


@pytest.mark.parametrize("text", FIXTURE["not_matches"])
def test_anything_else_is_a_message(text: str) -> None:
    assert match_command(text) is None


def test_none_and_an_overlong_instruction_are_not_commands() -> None:
    assert match_command(None) is None
    assert match_command("Navrhni dotazník: " + "x" * INSTRUCTION_MAX_CHARS) is not None
    assert match_command("Navrhni dotazník: " + "x" * (INSTRUCTION_MAX_CHARS + 1)) is None
