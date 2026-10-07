"""The settings document: who may read what, and that values come from the code."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from aia_core.domain import ai_respondent
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.ai_respondent import Block, Item, respondent_agent
from aia_core.domain.deep_research.agents import AgentRole, agent_definition
from aia_core.domain.deep_research.contracts import HARNESS_VERSION as DR_HARNESS_VERSION
from aia_core.domain.deep_research.settings import CATALOGUE_VERSION
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH_KINDS
from aia_core.domain.evidence import REFERENCE_THRESHOLDS
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.providers import (
    DEFAULT_MAX_API_COST_USD,
    DEFAULT_POLICY,
    DEFAULT_PROVIDER,
    NATIVE_PROVIDERS,
    Provider,
    ProviderPolicy,
    is_paid,
)
from aia_core.domain.research_agents import (
    HARNESS_VERSION,
    ResearchAction,
    agent_request,
    context_snapshot,
)
from aia_core.domain.scope import ROLE_PERMISSIONS, OrganizationRole, StudyStatus
from aia_core.domain.workflow import DEFAULT_LEASE_SECONDS
from aia_core.domain.workflow_templates import RESEARCH, RESEARCH_AGENT, steps_for_workflow
from fastapi.testclient import TestClient

from aia_api.routers.settings import _database_backend

API = "/api/v1"

#: Every identifier the prototype's provider world persisted. None may be presented
#: as something AIA does now.
_HISTORICAL = {p.value for p in Provider if p not in NATIVE_PROVIDERS} | {
    p.value for p in ProviderPolicy
}


def _groups(body: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    return {g["key"]: {i["key"]: i for i in g["items"]} for g in body["groups"]}


def _strings(node: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every string in a JSON document, with where it sits."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for n, value in enumerate(node):
            yield from _strings(value, f"{path}[{n}]")


def _activities(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["key"]: a for a in body["ai_runtime"]["activities"]}


def test_settings_require_authentication(client: TestClient, world: Any) -> None:
    assert client.get(f"{API}/settings").status_code == 401


def test_an_owner_sees_the_deployment_group(owner: TestClient) -> None:
    response = owner.get(f"{API}/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["your_role"] == "OWNER"
    assert body["may_administer"] is True
    deployment = _groups(body)["deployment"]
    assert deployment["env"]["value"] == "test"
    assert deployment["env"]["control"] == "DEPLOYMENT"
    assert deployment["env"]["source"] == "AIA_ENV"
    assert deployment["identity_provider"]["value"] == "test"


def test_a_member_does_not_see_the_deployment_group(researcher: TestClient) -> None:
    body = researcher.get(f"{API}/settings").json()
    assert body["your_role"] == "MEMBER"
    assert body["may_administer"] is False
    assert "deployment" not in _groups(body)
    # Everything else is the same document.
    assert "studies" in _groups(body)


def test_no_secret_reaches_the_document(owner: TestClient) -> None:
    raw = owner.get(f"{API}/settings").text
    # The test database URL is a path, not a secret, but a production URL carries a
    # password: only the backend name may appear.
    deployment = _groups(owner.get(f"{API}/settings").json())["deployment"]
    # CI's SQLite job runs with DATABASE_URL="" (not configured), the PostgreSQL job
    # with a URL: either way the document carries a backend name or null, never a URL.
    assert deployment["database_backend"]["value"] in {None, "sqlite", "postgresql"}
    assert "://" not in raw
    assert deployment["cognito_configured"]["value"] is False


@pytest.mark.parametrize(
    ("url", "backend"),
    [
        ("", None),
        ("   ", None),
        ("sqlite+pysqlite:///:memory:", "sqlite"),
        ("postgresql+psycopg://aia:s3cret@db.internal:5432/aia", "postgresql"),
        ("postgres://aia:s3cret@db.internal/aia", "postgresql"),
    ],
)
def test_a_database_url_is_reduced_to_its_backend(url: str, backend: str | None) -> None:
    """Unset is null, not a guessed default; a password never survives."""
    assert _database_backend(url) == backend


def test_values_are_the_domain_constants(owner: TestClient) -> None:
    groups = _groups(owner.get(f"{API}/settings").json())
    history = groups["ai_history"]
    assert history["default_project_max_api_cost"]["value"] == DEFAULT_MAX_API_COST_USD
    assert history["project_default_provider"]["value"] == DEFAULT_PROVIDER.value
    assert history["project_default_provider_policy"]["value"] == DEFAULT_POLICY.value
    assert groups["workflow"]["lease_seconds"]["value"] == DEFAULT_LEASE_SECONDS
    assert groups["evidence"]["min_cell"]["value"] == REFERENCE_THRESHOLDS.min_cell
    assert groups["evidence"]["tier_C_permits"]["value"] == ["internal_experimental"]


def test_every_item_states_its_control_and_source(owner: TestClient) -> None:
    body = owner.get(f"{API}/settings").json()
    for group in body["groups"]:
        assert group["items"], group["key"]
        for item in group["items"]:
            assert item["control"] in {"API", "DEPLOYMENT", "CODE", "INVARIANT"}
            assert item["source"].strip(), item["key"]


def test_invariants_are_in_force_and_not_editable(owner: TestClient) -> None:
    body = owner.get(f"{API}/settings").json()
    invariants = [i for g in body["groups"] for i in g["items"] if i["control"] == "INVARIANT"]
    assert {i["key"] for i in invariants} >= {
        "no_silent_provider_fallback",
        "no_spend_past_budget",
        "no_invented_certainty",
        "no_fake_progress",
        "no_visualisation_mutation",
        "eu_residency",
    }
    assert all(i["value"] is True for i in invariants)


def test_the_settings_say_membership_is_access_and_offer_no_grants(owner: TestClient) -> None:
    """ADR 0019: nothing in the document may still promise client or study grants."""
    access = _groups(owner.get(f"{API}/settings").json())["access"]
    assert access["membership_is_access"]["control"] == "INVARIANT"
    assert access["membership_is_access"]["value"] is True
    assert {"client_grants", "study_grants", "membership_grants_no_data"}.isdisjoint(access)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/members", {"email": "new@art-chain.io", "role": "MEMBER"}),
        ("put", "/self-approval", {"allowed": False}),
    ],
)
def test_a_researcher_cannot_change_the_system_settings(
    researcher: TestClient, method: str, path: str, body: dict[str, Any]
) -> None:
    """Administration is the Admin's; a Researcher holds every study permission, not this."""
    response = getattr(researcher, method)(f"{API}{path}", json=body)
    assert response.status_code == 403, response.text


def test_api_controls_name_a_route_that_exists(owner: TestClient, app: Any) -> None:
    routes = {
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    body = owner.get(f"{API}/settings").json()
    for group in body["groups"]:
        for item in group["items"]:
            if item["control"] == "API":
                assert item["source"] in routes, item


def test_vocabularies_are_the_domain_enums(researcher: TestClient) -> None:
    vocab = researcher.get(f"{API}/settings").json()["vocabularies"]
    assert vocab["organization_roles"] == [r.value for r in OrganizationRole]
    assert vocab["study_statuses"] == [s.value for s in StudyStatus]
    assert vocab["provider_policies"] == [p.value for p in ProviderPolicy]
    assert [p["id"] for p in vocab["providers"]] == [p.value for p in Provider]
    paid = {p["id"]: p["paid"] for p in vocab["providers"]}
    assert paid == {p.value: is_paid(p) for p in Provider}
    # How an old record reads: the prototype's subscription runtime recorded no
    # per-token charge, its per-token APIs did.
    assert paid["claude_code_subscription"] is False
    assert paid["anthropic"] is True
    # Every id stays readable; only Bedrock is something AIA calls.
    assert {p["id"]: p["use"] for p in vocab["providers"]} == {
        "aws_bedrock": "NATIVE",
        "claude_code_subscription": "HISTORICAL",
        "anthropic": "HISTORICAL",
        "openai": "HISTORICAL",
    }
    by_role = {r["role"]: set(r["permissions"]) for r in vocab["scope_roles"]}
    assert by_role == {
        role.value: {p.value for p in granted} for role, granted in ROLE_PERMISSIONS.items()
    }
    assert len(vocab["research_stages"]) == 13
    assert len(vocab["simulation_stages"]) == 13


# --------------------------------------------------------------------------- #
# What powers AIA: native from code, history only as history
# --------------------------------------------------------------------------- #


def test_no_native_choice_or_default_is_spelled_as_the_prototype(owner: TestClient) -> None:
    """claude_code_subscription and CLAUDE_CODE_ONLY survive only where records are read."""
    body = owner.get(f"{API}/settings").json()
    history_items = {i["key"] for i in _groups(body)["ai_history"].values()}
    historical_providers = {
        n for n, p in enumerate(body["vocabularies"]["providers"]) if p["use"] == "HISTORICAL"
    }
    places = [path for path, value in _strings(body) if value in _HISTORICAL]
    assert places, "the history must stay readable"
    for path in places:
        in_history_group = any(
            path.startswith(f".groups[{n}]")
            for n, g in enumerate(body["groups"])
            if g["key"] == "ai_history"
        )
        in_historical_vocabulary = path.startswith(".vocabularies.provider_policies") or any(
            path.startswith(f".vocabularies.providers[{n}]") for n in historical_providers
        )
        assert in_history_group or in_historical_vocabulary, path
    assert history_items == {
        "project_default_provider",
        "project_default_provider_policy",
        "project_provider_policy",
        "default_project_max_api_cost",
        "project_max_api_cost",
    }
    # The Study budget is the ceiling a native call is checked against; the
    # prototype's per-project ceiling is not offered next to it.
    assert set(_groups(body)["studies"]) == {
        "studies",
        "study_status",
        "study_budget",
        "no_spend_past_budget",
    }


def test_the_runtime_is_bedrock_from_code_and_claims_no_connection(owner: TestClient) -> None:
    body = owner.get(f"{API}/settings").json()
    runtime = body["ai_runtime"]
    assert runtime["providers"] == [
        {"id": "aws_bedrock", "label": "Amazon Bedrock", "paid": True, "use": "NATIVE"}
    ]
    assert runtime["credential"] == "INSTANCE_ROLE"
    # A description, never a state: nothing in it can read as "on", "healthy",
    # "connected" or "verified" -- the API cannot see the worker, and probes nothing.
    assert set(runtime) == {
        "providers",
        "credential",
        "switch",
        "strict_switches",
        "activities",
        "unused_capabilities",
    }
    # Every activity needs the runtime's own switch first.
    assert runtime["switch"] == "AIA_AI_RUNTIME_ENABLED"
    assert all(a["switches"][0] == runtime["switch"] for a in runtime["activities"])
    for activity in runtime["activities"]:
        assert set(activity) == {
            "key",
            "step_kind",
            "capabilities",
            "versions",
            "switches",
            "actions",
        }
    ai = _groups(body)["ai"]
    assert {i["control"] for i in ai.values()} == {"INVARIANT"}
    assert ai["configuration_is_not_verification"]["value"] is True
    # The switches are named for the worker's environment, and nothing else of it
    # is: no route id, price, retention or fictional-client list.
    switches = {s for a in runtime["activities"] for s in a["switches"]}
    assert switches == {
        "AIA_AI_RUNTIME_ENABLED",
        "AIA_AI_RESEARCH_AGENTS_ENABLED",
        "AIA_AI_ANALYSIS_ENABLED",
        "AIA_DEEP_RESEARCH_ENABLED",
        "AIA_DEEP_RESEARCH_AGENT_DIRECTED",
        "AIA_DEEP_RESEARCH_LEAD",
    }
    # Deep Research's switches are read whatever the runtime's switch says.
    assert runtime["strict_switches"] == [
        "AIA_DEEP_RESEARCH_ENABLED",
        "AIA_DEEP_RESEARCH_AGENT_DIRECTED",
        "AIA_DEEP_RESEARCH_LEAD",
    ]
    assert set(runtime["strict_switches"]) <= switches
    raw = owner.get(f"{API}/settings").text
    for internal in ("AIA_AI_ROUTE_ID", "USD_PER_MTOK", "AIA_AI_FICTIONAL_CLIENT_IDS"):
        assert internal not in raw
    # Nor a model id: which inference profile runs is the deployment's, shown by /config.
    assert not [path for path, value in _strings(body) if value.startswith("eu.")]


def test_each_activity_is_what_its_agents_ask_for(owner: TestClient) -> None:
    """The capabilities, versions and step kinds are the domain's own, not a copy."""
    activities = _activities(owner.get(f"{API}/settings").json())
    assert list(activities) == [
        "respondent_fieldwork",
        "design_agents",
        "research_analysis",
        "deep_research",
        "deep_research_lead",
    ]

    fieldwork = activities["respondent_fieldwork"]
    agent = respondent_agent(Block(0, (Item("q1", "open", "Proč?"),)), max_output_tokens=100)
    assert fieldwork["capabilities"] == [agent.capability.value]
    assert {v["name"]: v["value"] for v in fieldwork["versions"]} == {
        "generator": ai_respondent.GENERATOR,
        "agent": f"{agent.agent_id}@{agent.version}",
        "prompt": f"{agent.prompt_id}@{agent.prompt_version}",
        "contract": ai_respondent.CONTRACT_VERSION,
        "roster": ai_respondent.ROSTER_VERSION,
    }
    research = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH)
    assert fieldwork["step_kind"] in {s.kind for s in research if s.stage_type == "FIELDWORK"}
    assert fieldwork["switches"] == ["AIA_AI_RUNTIME_ENABLED"]
    assert fieldwork["actions"] == []

    design = activities["design_agents"]
    snapshot = context_snapshot({"title": "Fictional", "sections": []}, [])
    asked = {
        agent_request(
            action,
            snapshot,
            instruction="",
            policy_version="test",
            max_output_tokens=100,
        ).agent.capability.value
        for action in ResearchAction
    }
    assert set(design["capabilities"]) == asked
    assert design["versions"] == [{"name": "harness", "value": HARNESS_VERSION}]
    assert design["actions"] == [a.value for a in ResearchAction]
    (step,) = steps_for_workflow(RESEARCH_AGENT, project_type=ProjectType.RESEARCH)
    assert design["step_kind"] == step.kind
    # Design jobs need the runtime and their own switch, in that order.
    assert design["switches"] == ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED"]

    analysis = activities["research_analysis"]
    assert analysis["capabilities"] == [ModelCapability.RESEARCH_REASONING.value]
    assert analysis["step_kind"] in {
        s.kind
        for s in steps_for_workflow(
            RESEARCH, project_type=ProjectType.RESEARCH, analysis_enabled=True
        )
        if s.node_key.startswith("analysis_")
    }
    assert analysis["switches"] == ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_ANALYSIS_ENABLED"]
    assert analysis["actions"] == []

    # Deep Research: what its agents ask for, the lead's own entry apart behind its switch.
    lead_roles = {AgentRole.LEAD, AgentRole.LEAD_REPLAN}
    asked_by = {
        role: agent_definition(role, max_output_tokens=100).capability.value for role in AgentRole
    }
    research = activities["deep_research"]
    assert set(research["capabilities"]) == {
        c for role, c in asked_by.items() if role not in lead_roles
    }
    assert research["step_kind"] == DEEP_RESEARCH_KINDS["plan"]
    assert research["versions"] == [
        {"name": "harness", "value": DR_HARNESS_VERSION},
        {"name": "settings", "value": CATALOGUE_VERSION},
    ]
    assert research["switches"] == [
        "AIA_AI_RUNTIME_ENABLED",
        "AIA_AI_RESEARCH_AGENTS_ENABLED",
        "AIA_DEEP_RESEARCH_ENABLED",
    ]
    lead = activities["deep_research_lead"]
    assert set(lead["capabilities"]) == {asked_by[r] for r in lead_roles}
    assert lead["switches"] == [
        *research["switches"],
        "AIA_DEEP_RESEARCH_AGENT_DIRECTED",
        "AIA_DEEP_RESEARCH_LEAD",
    ]

    used = {c for a in activities.values() for c in a["capabilities"]}
    unused = owner.get(f"{API}/settings").json()["ai_runtime"]["unused_capabilities"]
    assert unused == [c.value for c in ModelCapability if c.value not in used]
    assert set(unused) | used == {c.value for c in ModelCapability}


def test_a_member_reads_what_powers_aia_but_not_the_deployment(
    owner: TestClient, researcher: TestClient
) -> None:
    member = researcher.get(f"{API}/settings").json()
    assert member["may_administer"] is False
    assert "deployment" not in _groups(member)
    assert member["ai_runtime"] == owner.get(f"{API}/settings").json()["ai_runtime"]
    assert "ai_history" in _groups(member)


def test_the_runtime_needs_a_signed_in_member(client: TestClient, world: Any) -> None:
    response = client.get(f"{API}/settings")
    assert response.status_code == 401
    assert "ai_runtime" not in response.text


def test_deep_research_says_how_its_values_are_set_and_what_no_value_changes(
    researcher: TestClient,
) -> None:
    """The group points at the approval route; the rails are invariants, not settings."""
    group = _groups(researcher.get(f"{API}/settings").json())["deep_research"]
    assert {k: i["control"] for k, i in group.items()} == {
        "deep_research_settings": "API",
        "deep_research_catalogue": "CODE",
        "deep_research_harness": "CODE",
        "deep_research_switches_in_deployment": "INVARIANT",
        "deep_research_public_sources_only": "INVARIANT",
        "deep_research_grounded_findings": "INVARIANT",
    }
    assert group["deep_research_settings"]["source"] == (
        "PUT /api/v1/deep-research/settings/{key}/approval"
    )
    assert group["deep_research_catalogue"]["value"] == CATALOGUE_VERSION
    assert group["deep_research_harness"]["value"] == DR_HARNESS_VERSION
