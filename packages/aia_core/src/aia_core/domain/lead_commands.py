"""The typed start commands of the Lead's composer, matched by code (lead-orchestration LO5).

A start is authorised by a person's own typed command that the server matched, never by a
model's reading of their text (LO5's security condition; D22, Q43). So this module is the whole
matcher: a closed vocabulary of Czech imperatives, each naming one start in the card registry's
words (``agent_job:<action>``, ``research_run``, ``analysis_retry``), compared with the person's
whole message after a fixed normalisation. Nothing is guessed: a message that is not exactly a
command is a message, and goes to the Lead (or, with the Lead off, is refused).

The normalisation: Unicode NFC, case folded, surrounding whitespace and one trailing ``.`` or
``!`` removed, inner whitespace collapsed, and an optional leading ``/``. Diacritics are kept
exactly: "spust vyzkum" is not "spusť výzkum", because a near-match is a guess. A design job
may carry the person's own instruction after a colon ("Navrhni dotazník: krátce, do 10
otázek"); the research run and the analysis retry take none, since nothing in their starts
reads one.

The vocabulary is pinned in ``tests/fixtures/lead_commands/commands.json``, which the web's
composer reads too, so the two cannot drift.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from .research_agents import ResearchAction

__all__ = [
    "ANALYSIS_RETRY",
    "COMMANDS",
    "INSTRUCTION_MAX_CHARS",
    "RESEARCH_RUN",
    "Command",
    "MatchedCommand",
    "agent_job_start",
    "command_for",
    "match_command",
    "normalise",
]

#: The card registry's name of a research run's start.
RESEARCH_RUN: Final = "research_run"
#: The card registry's name of a finished run's failed analysis asked again over its own data.
ANALYSIS_RETRY: Final = "analysis_retry"
#: An instruction typed after a design job's command, at most (the job's own bound is 8 KB).
INSTRUCTION_MAX_CHARS: Final = 2000


def agent_job_start(action: ResearchAction) -> str:
    """The card registry's name of a design job's start: ``agent_job:<action>``."""
    return f"agent_job:{action.value}"


@dataclass(frozen=True, slots=True)
class Command:
    """One typed command: the phrase a person types, the start it names, and the card's label."""

    phrase: str
    start: str
    label: str
    #: The design job this starts; ``None`` for the research run and the analysis retry.
    action: ResearchAction | None
    #: Whether the phrase may be followed by ``: <instruction>``.
    takes_instruction: bool


def _job(phrase: str, action: ResearchAction, label: str) -> Command:
    return Command(phrase, agent_job_start(action), label, action, True)


#: The closed vocabulary, one phrase per start. The labels are the job panel's
#: (``lib/research-agent-jobs.ts`` ``ACTION_LABELS``).
COMMANDS: Final[tuple[Command, ...]] = (
    _job("Analyzuj zadání", ResearchAction.ANALYZE, "Analýza zadání"),
    _job("Navrhni dotazník", ResearchAction.BUILD, "Návrh dotazníku"),
    _job("Uprav dotazník", ResearchAction.OPTIMIZE, "Úprava dotazníku"),
    _job("Navrhni audienci", ResearchAction.AUDIENCE, "Návrh audience"),
    _job("Navrhni dimenze", ResearchAction.DIMENSIONS, "Návrh dimenzí"),
    _job("Zkontroluj návrh", ResearchAction.CRITIQUE, "Kontrola návrhu"),
    _job("Pomoz s návrhem", ResearchAction.COPILOT, "Pomoc s návrhem"),
    _job("Zeptej se na klientské znalosti", ResearchAction.MEMORY, "Klientské znalosti"),
    Command("Spusť výzkum", RESEARCH_RUN, "Spuštění výzkumu", None, False),
    Command("Zopakuj analýzu", ANALYSIS_RETRY, "Opakování analýzy", None, False),
)

_WHITESPACE: Final = re.compile(r"\s+")


def normalise(text: str) -> str:
    """A message as the matcher compares it (see the module docstring)."""
    t = unicodedata.normalize("NFC", text).strip()
    t = _WHITESPACE.sub(" ", t).casefold()
    if t.startswith("/"):
        t = t[1:].lstrip()
    if t.endswith((".", "!")):
        t = t[:-1].rstrip()
    return t


_BY_PHRASE: Final = {normalise(c.phrase): c for c in COMMANDS}
_BY_START: Final = {c.start: c for c in COMMANDS}


@dataclass(frozen=True, slots=True)
class MatchedCommand:
    command: Command
    #: The person's own instruction for a design job ("" when none was typed).
    instruction: str

    @property
    def start(self) -> str:
        return self.command.start


def command_for(start: str) -> Command | None:
    """The command naming ``start`` (a stored turn's), or ``None`` for a name no command has."""
    return _BY_START.get(start)


def match_command(text: str | None) -> MatchedCommand | None:
    """The command ``text`` is exactly, with its instruction; ``None`` when it is not one."""
    if not text:
        return None
    head, sep, rest = text.partition(":")
    command = _BY_PHRASE.get(normalise(head))
    if command is None:
        return None
    if not sep:
        return MatchedCommand(command, "")
    if not command.takes_instruction:
        return None
    instruction = _WHITESPACE.sub(" ", rest).strip()
    if not instruction or len(instruction) > INSTRUCTION_MAX_CHARS:
        return None
    return MatchedCommand(command, instruction)
