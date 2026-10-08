"""The ``deep_research`` workflow: its six steps, their kinds and their artifacts.

``plan → investigate → merge → verify → synthesize → publish`` (ADR 0017), pinned
to one Design Revision of a research Study and filed under ``DEEP_RESEARCH``.

This module *defines* the graph; it does not register it. Registration --
``workflow_templates.WORKFLOW_TYPES`` / ``steps_for_workflow`` and the production
executor registry -- is the integrator's (plan decision I-9), which is why a run
is created from :func:`deep_research_steps` by the Deep Research application
service directly. A step without an executor must never be registered, because a
step no worker can claim would leave a run "running" forever.

Retries follow the cost of repeating a step. ``investigate`` and ``verify`` are
checkpointed per track and per batch (a retry re-buys nothing already stored), so
they may retry a transient failure; ``plan`` and ``synthesize`` make one model
request each, and a lost settled answer must not be bought again automatically
(the design jobs' rule, ``docs/architecture/research-agents.md``). ``merge`` and
``publish`` are deterministic.
"""

from __future__ import annotations

from typing import Final

from ..workflow import StepDefinition, child_node_key

__all__ = [
    "ARTIFACT_TYPES",
    "DEEP_RESEARCH",
    "DEEP_RESEARCH_KINDS",
    "DEEP_RESEARCH_STAGE",
    "INVESTIGATE_TRACK_KIND",
    "NODE_ORDER",
    "TRACK_STEP_PREFIX",
    "deep_research_steps",
    "track_step_key",
]

#: The workflow type a Deep Research run is created with.
DEEP_RESEARCH: Final = "deep_research"

#: The lifecycle stage every step is filed under (``pipeline.RESEARCH_STAGES``).
DEEP_RESEARCH_STAGE: Final = "DEEP_RESEARCH"

NODE_ORDER: Final[tuple[str, ...]] = (
    "plan",
    "investigate",
    "merge",
    "verify",
    "synthesize",
    "publish",
)

#: Node key -> step kind: what an executor registers for.
DEEP_RESEARCH_KINDS: Final[dict[str, str]] = {n: f"deep_research_{n}" for n in NODE_ORDER}

#: Every artifact type a Deep Research run writes, by what it is.
ARTIFACT_TYPES: Final[dict[str, str]] = {
    "plan": "deep_research_plan",
    "track": "deep_research_track",
    "snapshot": "deep_research_source_snapshot",
    "investigation": "deep_research_investigation",
    "merge": "deep_research_merge",
    "verification": "deep_research_verification",
    "verify": "deep_research_verify",
    "synthesis": "deep_research_synthesis",
    "bundle": "deep_research_bundle",
    # Agent-directed tracks (chunk 9): each turn's answer and record (this run's
    # own), and the track's transcript (keyed like the track).
    "turn_answer": "deep_research_turn_answer",
    "turn": "deep_research_turn",
    "transcript": "deep_research_transcript",
    # A lead-planned run (chunk 11): the lead's plan and each re-plan (this run's own).
    "lead_plan": "deep_research_lead_plan",
    "replan": "deep_research_lead_replan",
    # Fan-out (chunk 21): a URL the run captured, by canonical URL, naming the
    # snapshot's content address -- the run's cache across its track steps.
    "url_capture": "deep_research_url_capture",
    # A cited work's standing (chunk 46): each DOI the merge asked about, this run's own,
    # stored as it returns so a merge that runs again asks nothing twice.
    "work_standing": "deep_research_work_standing",
    # A planned web track's rounds (this run's own): each search, each fetch, each
    # round once its fetches resolved, and each round's investigator answer -- every
    # external outcome durable before the next call, so a step that runs again
    # continues the track and sends nothing twice.
    "planned_search": "deep_research_planned_search",
    "planned_fetch": "deep_research_planned_fetch",
    "planned_round": "deep_research_planned_round",
    "planned_round_answer": "deep_research_planned_round_answer",
}

#: The kind of a track handed out to its own step by a fanned-out ``investigate``
#: (chunk 21, ``docs/architecture/deep-research-fan-out.md``). Not a node of the
#: graph: the join adds one per track it hands out, while the run executes.
INVESTIGATE_TRACK_KIND: Final = "deep_research_investigate_track"

#: The node-key prefix of a track's step: ``investigate/<track id>``.
TRACK_STEP_PREFIX: Final = "investigate"


def track_step_key(track_id: str) -> str:
    """The node key of the step a track is handed out to: the same track, the same key."""
    return child_node_key(TRACK_STEP_PREFIX, track_id)


#: The artifact each step records as its output.
_STEP_ARTIFACT: Final[dict[str, str]] = {
    "plan": ARTIFACT_TYPES["plan"],
    "investigate": ARTIFACT_TYPES["investigation"],
    "merge": ARTIFACT_TYPES["merge"],
    "verify": ARTIFACT_TYPES["verify"],
    "synthesize": ARTIFACT_TYPES["synthesis"],
    "publish": ARTIFACT_TYPES["bundle"],
}

_MAX_ATTEMPTS: Final[dict[str, int]] = {
    "plan": 1,
    "investigate": 3,
    "merge": 3,
    "verify": 3,
    "synthesize": 1,
    "publish": 3,
}


def deep_research_steps() -> list[StepDefinition]:
    """The step graph of one Deep Research run: a chain, each step on the one before."""
    return [
        StepDefinition(
            node_key=node,
            kind=DEEP_RESEARCH_KINDS[node],
            depends_on=(NODE_ORDER[i - 1],) if i else (),
            stage_type=DEEP_RESEARCH_STAGE,
            artifact_target=_STEP_ARTIFACT[node],
            max_attempts=_MAX_ATTEMPTS[node],
        )
        for i, node in enumerate(NODE_ORDER)
    ]
