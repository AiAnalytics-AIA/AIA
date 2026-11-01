"""The typed run start: what every way of starting a research run names (ADR 0028 decision 3;
lead-orchestration LO2, interface I3 of the MVP master plan).

Three callers start a run over one ``ResearchRuns.start``: the Run stage's button, a person's typed
start in the composer (``chat_start``, LO5) and, from LO3, a step of an approved plan. Each names
the run as a :class:`StartRun`: the Design Revision it executes, who answers it, the population
child it records and the answerability acknowledgement, every one explicit, never "the latest".

The command carries **no confirmation of its cost**. A confirmation is a person's act, issued only
by ``application/spend_confirmation.py`` to a scope holding ``APPROVE_BUDGET``, and passed beside
the command; a plan step reads the confirmation its plan's approval recorded and never makes one.
"""

from __future__ import annotations

from dataclasses import dataclass

from .answerability import Acknowledgement
from .fieldwork import PersonaSource

__all__ = ["StartRun"]


@dataclass(frozen=True, slots=True, kw_only=True)
class StartRun:
    """One research run start, as its caller names it. Every field is required: a caller that
    means the deployment's default persona source, LIVE or no acknowledgement says so."""

    design_revision_id: str
    persona_source: PersonaSource
    #: A materialized child of the study's client (P4e2); ``None``: LIVE.
    population_version_id: str | None
    #: A person's decision to run a design with unanswerable research questions, or ``None``.
    acknowledge: Acknowledgement | None
