"""Each AI activity's last answered call (settings-redesign F14, OI-75 (a)).

A call's activity is read from the agent id its code sends; the settings document lists the same
activities; an activity with no answered call is absent, never working; the newest answered call
wins; a build the worker did not know reads as unknown; and the organization-level read names no
client, study, person or cost and reads another organization's ledger never.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from aia_core.domain.ai_activity import (
    ACTIVITY_AGENT_IDS,
    AnsweredCall,
    RuntimeActivity,
    activity_of_call,
    last_answered,
)
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.ai_respondent import AGENT_ID as RESPONDENT
from aia_core.domain.analysis.harness import AGENT_ID as ANALYSIS
from aia_core.domain.deep_research.agents import AGENT_IDS, AgentRole
from aia_core.domain.research_agents import ResearchAction, worker_for
from aia_core.domain.research_lead import LEAD_AGENT_ID
from aia_core.domain.source_proposals import PROMPT_ID as SOURCE_PROPOSALS
from aia_core.infrastructure.ai_usage_repository import last_answered_calls
from aia_core.infrastructure.tables import AIUsageEventRow, Base

T0 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
RR = ModelCapability.RESEARCH_REASONING.value


def test_each_activity_is_read_from_the_agent_its_code_sends() -> None:
    assert (
        activity_of_call(RESPONDENT, ModelCapability.SIMULATION.value)
        is RuntimeActivity.RESPONDENT_FIELDWORK
    )
    for action in ResearchAction:
        agent = worker_for(action)
        assert (
            activity_of_call(agent.prompt_id, agent.capability.value)
            is RuntimeActivity.DESIGN_AGENTS
        )
    assert activity_of_call(ANALYSIS, RR) is RuntimeActivity.RESEARCH_ANALYSIS
    assert (
        activity_of_call(LEAD_AGENT_ID, ModelCapability.STUDY_LEAD.value)
        is RuntimeActivity.STUDY_LEAD
    )
    assert activity_of_call(AGENT_IDS[AgentRole.PLANNER], RR) is RuntimeActivity.DEEP_RESEARCH
    # Deep Research's lead researcher is its own activity, told by its capability.
    lead = ModelCapability.RESEARCH_LEAD.value
    assert activity_of_call(AGENT_IDS[AgentRole.LEAD], lead) is RuntimeActivity.DEEP_RESEARCH_LEAD
    # A call no listed activity makes is left out, never folded into one.
    assert activity_of_call(SOURCE_PROPOSALS, RR) is None
    assert activity_of_call("aia.unknown", RR) is None
    # The organization read asks for exactly the agents an activity names.
    assert all(activity_of_call(a, RR) is not None for a in ACTIVITY_AGENT_IDS)
    assert SOURCE_PROPOSALS not in ACTIVITY_AGENT_IDS


def _call(
    agent: str, at: datetime, *, capability: str = RR, served: str = "", build: str = "abc1234"
) -> AnsweredCall:
    return AnsweredCall(agent, capability, at, "eu.model-asked", served, build)


def test_the_newest_answered_call_of_each_activity_and_none_where_none() -> None:
    folded = last_answered(
        [
            _call(ANALYSIS, T0),
            _call(ANALYSIS, T0 + timedelta(hours=1), served="eu.model-served"),
            _call(ANALYSIS, T0 - timedelta(hours=1)),
            _call(
                RESPONDENT, T0, capability=ModelCapability.SIMULATION.value, build="unknown-build"
            ),
            _call(SOURCE_PROPOSALS, T0 + timedelta(days=1)),
        ]
    )
    assert set(folded) == {RuntimeActivity.RESEARCH_ANALYSIS, RuntimeActivity.RESPONDENT_FIELDWORK}
    analysis = folded[RuntimeActivity.RESEARCH_ANALYSIS]
    assert (analysis.at, analysis.model, analysis.build) == (
        T0 + timedelta(hours=1),
        "eu.model-served",
        "abc1234",
    )
    respondents = folded[RuntimeActivity.RESPONDENT_FIELDWORK]
    assert (respondents.model, respondents.build) == ("eu.model-asked", None)
    assert RuntimeActivity.STUDY_LEAD not in folded


_ids = count(1)


def _row(
    org: str,
    agent: str,
    at: datetime,
    outcome: str = "SUCCEEDED",
    *,
    model: str = "eu.m",
    capability: str = RR,
) -> AIUsageEventRow:
    n = next(_ids)
    return AIUsageEventRow(
        event_id=f"EV-{n}",
        call_id=f"CALL-{n}",
        outcome=outcome,
        purpose="PRIMARY",
        organization_id=org,
        client_id="CLI-1",
        study_id=None,
        actor_id="USR-1",
        agent_id=agent,
        agent_version="1",
        prompt_id=agent,
        prompt_version="1",
        capability=capability,
        policy_version="p",
        runtime_version="sha-1",
        provider="bedrock",
        model=model,
        served_model="",
        route_id="r",
        data_class="CLASS_C_INTERNAL",
        residency_zone="EU",
        cost_usd=0.01,
        cost_basis="METERED",
        occurred_at=at,
    )


def test_the_organization_read_is_the_newest_answered_row_per_agent_and_its_own_alone() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                _row("ORG-A", ANALYSIS, T0, model="eu.old"),
                _row("ORG-A", ANALYSIS, T0 + timedelta(hours=2), model="eu.new"),
                # A newer failure is not an answer; another organization's answer is not ours.
                _row("ORG-A", ANALYSIS, T0 + timedelta(hours=3), "FAILED", model="eu.failed"),
                _row("ORG-A", ANALYSIS, T0 + timedelta(hours=3), "DISPATCHED", model="eu.sent"),
                _row("ORG-B", ANALYSIS, T0 + timedelta(hours=4), model="eu.theirs"),
                _row("ORG-B", LEAD_AGENT_ID, T0, capability=ModelCapability.STUDY_LEAD.value),
            ]
        )
        session.commit()
        calls = last_answered_calls(session, organization_id="ORG-A", agent_ids=ACTIVITY_AGENT_IDS)
    assert [(c.agent_id, c.model, c.occurred_at) for c in calls] == [
        (ANALYSIS, "eu.new", T0 + timedelta(hours=2))
    ]
    folded = last_answered(calls)
    assert set(folded) == {RuntimeActivity.RESEARCH_ANALYSIS}
    # The read carries what answered and when: nothing names a client, study, person, text or cost.
    assert set(AnsweredCall.__dataclass_fields__) == {
        "agent_id",
        "capability",
        "occurred_at",
        "model",
        "served_model",
        "runtime_version",
    }


def test_an_index_holds_the_answered_rows_by_organization_and_agent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    indexes = {i["name"]: i for i in inspect(engine).get_indexes("ai_usage_events")}
    assert indexes["ix_usage_org_answered"]["column_names"] == [
        "organization_id",
        "agent_id",
        "occurred_at",
    ]
