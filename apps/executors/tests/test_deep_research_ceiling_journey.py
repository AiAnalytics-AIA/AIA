"""A recorded run never makes more calls of any kind than its cost ceiling counts (chunk 22).

``call_bounds`` is a claim about the executors: how many requests each agent can be asked
and how many searches and pages a run can send. Here it is held against what the real
worker loop sent over the three recorded journeys -- the planned mode (``pass_one``, QUICK,
both channels), the agent-directed mode (``directed_run``, STANDARD) and the lead
(``led_run``, STANDARD, with a re-plan and a budget move) -- counted from the requests that
reached the recorded model route and the tool journal.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.budgets import CallKind, ResearchMode, call_bounds, track_counts
from aia_core.domain.deep_research.contracts import Channel
from aia_core.domain.deep_research.planning import preset
from aia_core.domain.deep_research.tooling import ToolOutcome
from test_deep_research_investigator_journey import (  # type: ignore[import-not-found]
    Directed,
    directed_run,  # noqa: F401  (a fixture)
)
from test_deep_research_journey import (  # type: ignore[import-not-found]
    Journey,
    RecordedAgents,
    ResearchWorld,
    pass_one,  # noqa: F401  (a fixture)
    research,  # noqa: F401  (a fixture)
    tool_events,
)
from test_deep_research_lead_journey import (  # type: ignore[import-not-found]
    Led,
    led_run,  # noqa: F401  (a fixture)
)

#: The recorded route's tool names, by the kind of call the ceiling prices.
ROLES = {
    "planner": CallKind.PLANNER,
    "web_investigator": CallKind.INVESTIGATOR,
    "investigator": CallKind.INVESTIGATOR,
    "internal_investigator": CallKind.INTERNAL_INVESTIGATOR,
    "verifier": CallKind.VERIFIER,
    "independent_verifier": CallKind.VERIFIER,
    "synthesizer": CallKind.SYNTHESIZER,
    "brief_synthesizer": CallKind.SYNTHESIZER,
    "lead": CallKind.LEAD,
    "lead_replan": CallKind.LEAD,
}
TOOLS = {"web_search": CallKind.SEARCH, "web_fetch": CallKind.FETCH}


def sent(world: ResearchWorld, run_id: str, agents: RecordedAgents) -> Counter[CallKind]:
    """Every model request that reached the route and every tool call that left, by kind."""
    calls: Counter[CallKind] = Counter()
    for role, n in agents.roles().items():
        calls[ROLES[role]] += n
    for event in tool_events(world, run_id):
        if event["payload"]["outcome"] == ToolOutcome.DISPATCHED.value:
            calls[TOOLS[event["payload"]["tool"]]] += 1
    return calls


def bounds_of(world: ResearchWorld, run_id: str, mode: ResearchMode) -> Any:
    with world.sessions() as session:
        runs = DeepResearchRuns(session, world.lead_scope(session))
        meta = runs.get(run_id)["metadata"]
        request = runs.freeze(
            design_revision_id=str(meta["design_revision_id"]),
            preset_name=str(meta["preset"]),
            channels=[Channel(c) for c in meta["channels"]],
        )
    depth = preset(request.preset)
    return call_bounds(depth, track_counts(request, depth), mode)


def assert_within(calls: Counter[CallKind], bounds: Any) -> None:
    assert calls, "the journey sent nothing: the comparison would say nothing"
    over = {k.value: (n, bounds[k]) for k, n in calls.items() if n > bounds[k]}
    assert over == {}, over


def test_the_planned_journey_stays_within_its_bounds(pass_one: Journey) -> None:  # noqa: F811
    calls = sent(pass_one.world, pass_one.run_id, pass_one.agents)
    assert calls[CallKind.SEARCH] > 0 and calls[CallKind.VERIFIER] > 0
    assert_within(calls, bounds_of(pass_one.world, pass_one.run_id, ResearchMode.PLANNED))


def test_the_agent_directed_journey_stays_within_its_bounds(
    directed_run: Directed,  # noqa: F811
) -> None:
    calls = sent(directed_run.world, directed_run.run_id, directed_run.agents)
    assert calls[CallKind.INVESTIGATOR] > 0
    assert_within(
        calls, bounds_of(directed_run.world, directed_run.run_id, ResearchMode.AGENT_DIRECTED)
    )


def test_the_lead_journey_stays_within_its_bounds(led_run: Led) -> None:  # noqa: F811
    calls = sent(led_run.world, led_run.run_id, led_run.agents)
    assert calls[CallKind.LEAD] >= 2  # the plan and a re-plan
    assert_within(calls, bounds_of(led_run.world, led_run.run_id, ResearchMode.LEAD))
