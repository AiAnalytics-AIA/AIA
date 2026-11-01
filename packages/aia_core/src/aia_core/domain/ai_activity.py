"""Which AI activity a model call belongs to, and each activity's last answered call.

Settings → AI běh says an activity is switched on in configuration, never that it works: the API
cannot see the worker, and nothing there calls a model. The one truthful signal that an activity
*has* worked is the usage ledger's last ``SUCCEEDED`` call of it (OI-75; the product owner,
2026-10-25, choice (a): an organization-level aggregate of the last success time, model and build
per activity, no client or study named, owners and admins only; ``settings-redesign`` F14).

A call's activity is read from what the gateway recorded of its agent: the agent id each
activity's code sends (a test holds every id here to the code that sends it), and for Deep
Research the capability that tells its lead researcher from the rest. A call no activity names
(an AI proposal from a client's document, an operator's calibration) is left out, never folded
into one it is not.

"Answered" is a fact about the past: an activity with no answered call reads as none recorded,
never as working, and a newer failure is not hidden by it -- the page says when it last answered,
not that it answers now.

Pure: stdlib only, beside the agent ids the domain already declares.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from .ai_models import ModelCapability
from .ai_respondent import AGENT_ID as RESPONDENT_AGENT_ID
from .analysis.harness import AGENT_ID as ANALYSIS_AGENT_ID
from .deep_research.agents import AGENT_IDS as DEEP_RESEARCH_AGENT_IDS
from .deep_research.triage import TRIAGE_AGENT_ID
from .research_agents import ResearchAction, worker_for
from .research_lead import LEAD_AGENT_ID

__all__ = [
    "ACTIVITY_AGENT_IDS",
    "UNKNOWN_BUILDS",
    "AnsweredCall",
    "LastAnswered",
    "RuntimeActivity",
    "activity_of_call",
    "last_answered",
]


class RuntimeActivity(StrEnum):
    """The native AI activities Settings lists (``routers/settings.py`` ``_native_runtime``)."""

    RESPONDENT_FIELDWORK = "respondent_fieldwork"
    DESIGN_AGENTS = "design_agents"
    RESEARCH_ANALYSIS = "research_analysis"
    DEEP_RESEARCH = "deep_research"
    DEEP_RESEARCH_LEAD = "deep_research_lead"
    STUDY_LEAD = "study_lead"


_DESIGN_AGENT_IDS: Final = frozenset(worker_for(a).prompt_id for a in ResearchAction)
_DEEP_RESEARCH_IDS: Final = frozenset({*DEEP_RESEARCH_AGENT_IDS.values(), TRIAGE_AGENT_ID})

#: Every agent id a listed activity's code sends: what the organization-level read asks for, one
#: indexed lookup each.
ACTIVITY_AGENT_IDS: Final = tuple(
    sorted(
        {
            RESPONDENT_AGENT_ID,
            ANALYSIS_AGENT_ID,
            LEAD_AGENT_ID,
            *_DESIGN_AGENT_IDS,
            *_DEEP_RESEARCH_IDS,
        }
    )
)

#: What a step records as its build when the worker knew none (``ai_step.StepModelCaller``): not
#: a build, so it reads as unknown.
UNKNOWN_BUILDS: Final = frozenset({"", "unknown-build"})


def activity_of_call(agent_id: str, capability: str) -> RuntimeActivity | None:
    """The activity a recorded call belongs to; ``None`` for a call no listed activity makes."""
    if agent_id == RESPONDENT_AGENT_ID:
        return RuntimeActivity.RESPONDENT_FIELDWORK
    if agent_id in _DESIGN_AGENT_IDS:
        return RuntimeActivity.DESIGN_AGENTS
    if agent_id == ANALYSIS_AGENT_ID:
        return RuntimeActivity.RESEARCH_ANALYSIS
    if agent_id == LEAD_AGENT_ID:
        return RuntimeActivity.STUDY_LEAD
    if agent_id in _DEEP_RESEARCH_IDS:
        if capability == ModelCapability.RESEARCH_LEAD.value:
            return RuntimeActivity.DEEP_RESEARCH_LEAD
        return RuntimeActivity.DEEP_RESEARCH
    return None


@dataclass(frozen=True, slots=True)
class AnsweredCall:
    """The latest answered call of one agent and capability, as the ledger recorded it."""

    agent_id: str
    capability: str
    occurred_at: datetime
    model: str
    served_model: str
    runtime_version: str


@dataclass(frozen=True, slots=True)
class LastAnswered:
    """An activity's last answered call: when, on which model, by which build (``None``:
    the worker recorded none). Nothing about whose study it was."""

    activity: RuntimeActivity
    at: datetime
    model: str
    build: str | None


def last_answered(calls: Iterable[AnsweredCall]) -> dict[RuntimeActivity, LastAnswered]:
    """Each activity's newest answered call; an activity with none is absent, never invented.

    The model is the one that served the call where the provider said so, else the one asked.
    """
    latest: dict[RuntimeActivity, LastAnswered] = {}
    for call in calls:
        activity = activity_of_call(call.agent_id, call.capability)
        if activity is None:
            continue
        held = latest.get(activity)
        if held is not None and held.at >= call.occurred_at:
            continue
        latest[activity] = LastAnswered(
            activity=activity,
            at=call.occurred_at,
            model=call.served_model or call.model,
            build=None if call.runtime_version in UNKNOWN_BUILDS else call.runtime_version,
        )
    return latest
