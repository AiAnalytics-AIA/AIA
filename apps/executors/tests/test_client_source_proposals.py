"""AI proposals from a client's document, through the real worker, gateway and ledger
(client-knowledge-lifecycle K2d3; client-budget CB5).

The run is the client's own work: no study, the client's budget holds and pays every
call, and the study's ledger does not move. Only grounded proposals are filed, as AI
proposals a person decides on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from aia_core.application.client_work import lift_client_budget_wait, start_client_work
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.knowledge import ProposalStatus
from aia_core.domain.scope import ClientContext, ClientWorkContext
from aia_core.domain.source_proposals import HARNESS_VERSION
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.domain.workflow_templates import CLIENT_SOURCE_PROPOSALS
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.client_source_repository import ClientSourceRepository
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_core.infrastructure.tables import ClientRow, StudyRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.ai_runtime import AIRuntimeSettings, build_gateway
from aia_executors.client_source_proposals import (
    ClientSourceProposalsExecutor,
    SourceProposalsConfig,
)
from aia_executors.registry import registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker

DOCUMENT = (
    "Fiktivní pivovar Lupínek vaří od roku 1998 v Kolíně.\n\n"
    "Podle vlastního průzkumu z roku 2025 zná značku 41 % dospělých v kraji.\n\n"
    "Výčepní pivo je u nich označení pro světlé pivo do 10 °.\n"
).encode()

ANSWER = {
    "proposals": [
        {
            "kind": "FACT",
            "title": "Pivovar vaří od roku 1998",
            "summary": "Pivovar Lupínek vaří od roku 1998 v Kolíně.",
            "quote": "vaří od roku 1998 v Kolíně",
            "segment": 0,
        },
        {
            "kind": "FINDING",
            "title": "Znalost značky 41 %",
            "summary": "Značku zná 41 % dospělých v kraji (vlastní průzkum 2025).",
            "quote": "zná značku 41 % dospělých v kraji",
            "segment": 1,
        },
        # A quote the document does not hold: dropped and counted.
        {
            "kind": "FACT",
            "title": "Vymyšlené",
            "summary": "",
            "quote": "zná značku 62 % dospělých",
            "segment": 1,
        },
        # A segment the request did not carry: dropped and counted.
        {
            "kind": "TERM",
            "title": "Neexistující",
            "summary": "",
            "quote": "Výčepní pivo",
            "segment": 9,
        },
    ]
}


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


@dataclass
class RecordedBedrock:
    requests: list[HttpRequest] = field(default_factory=list)

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"source-request-{len(self.requests)}"},
            body={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "test-tool",
                                    "name": tool["name"],
                                    "input": ANSWER,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 1000, "outputTokens": 400, "totalTokens": 1400},
            },
        )


def settings(**overrides: str) -> AIRuntimeSettings:
    env = {
        "AIA_ENV": "test",
        "AIA_AI_RUNTIME_ENABLED": "true",
        "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
        "AIA_BEDROCK_REGION": "eu-central-1",
        "AIA_BEDROCK_MODEL_ID": "eu.test-extract-v1:0",
        "AIA_AI_POLICY_VERSION": "test-v1",
        "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
        "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
        "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
        "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
        "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
        "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_C_INTERNAL",
        # Class A egress needs the route's retention stated (unset is unspecified, never 0).
        "AIA_AI_ROUTE_RETENTION_DAYS": "0",
        "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
        "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
        "AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED": "true",
        "AIA_AI_CLIENT_SOURCE_MAX_OUTPUT_TOKENS": "4096",
        "AIA_AI_CLIENT_SOURCE_RESERVATION_USD": "1.5",
        **overrides,
    }
    result = AIRuntimeSettings.from_env(env)
    assert result is not None
    return result


def worker(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
    transport: RecordedBedrock,
    *,
    enabled: bool = True,
    **overrides: str,
) -> Worker:
    cfg = settings(**overrides)
    executor = ClientSourceProposalsExecutor(
        store=store,
        build=build,
        gateway=build_gateway(cfg, transport=transport, signer=Signer()) if enabled else None,
        config=SourceProposalsConfig(
            policy_version=cfg.policy_version,
            max_output_tokens=cfg.client_source_max_output_tokens,
            reservation_usd=cfg.client_source_reservation_usd,
        )
        if enabled
        else None,
    )
    return Worker(
        session_factory=world.sessions,
        executors=registry_for(store=store, build=build, client_source_proposals=executor),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="source-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def principal(world: Any) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id)


def client_scope(world: Any, session: Any) -> ClientContext:
    return ScopeResolver(session).client_context(principal(world), client_id=world.client_id)


def work_scope(world: Any, session: Any) -> ClientWorkContext:
    return ScopeResolver(session).client_work_context(principal(world), client_id=world.client_id)


def start(
    world: Any,
    store: Any,
    *,
    budget: float = 10.0,
    filename: str = "lupinek.txt",
    data: bytes = DOCUMENT,
) -> tuple[str, str]:
    """Keep the document, set the client's budget and start the proposals: (run, source)."""
    with world.sessions() as session:
        client = session.get(ClientRow, world.client_id)
        assert client is not None
        client.budget_usd, client.spent_usd = budget, 0.0
        sources = ClientSourceRepository(session, store)
        record, _ = sources.add(client_scope(world, session), filename=filename, data=data)
        pin = sources.reading_pin(client_scope(world, session), record.source_id)
        started = start_client_work(
            session,
            work_scope(world, session),
            workflow_type=CLIENT_SOURCE_PROPOSALS,
            idempotency_key=f"proposals:{record.source_id}:{pin.reading_sha256}",
            step_inputs={
                "extract": {
                    "source_id": record.source_id,
                    "reading_sha256": pin.reading_sha256,
                    "harness_version": HARNESS_VERSION,
                }
            },
        )
        session.commit()
        return started.run_id, record.source_id


def run_state(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return WorkflowRepository(session, work_scope(world, session)).get_run(run_id)


def spent(world: Any) -> tuple[float, float]:
    """(the client's spend, the study's spend)."""
    with world.sessions() as session:
        client = session.get(ClientRow, world.client_id)
        study = session.get(StudyRow, world.study_id)
        assert client is not None and study is not None
        return client.spent_usd, study.spent_usd


def test_grounded_proposals_are_filed_and_the_client_pays(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id, source_id = start(world, store)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    assert w.run_once()
    assert not w.run_once()
    assert len(transport.requests) == 1  # three short paragraphs: one batch

    run = run_state(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    step = run["steps"][0]
    assert step["output"] == {
        "source_id": source_id,
        "reading_sha256": step["output"]["reading_sha256"],
        "batches": 1,
        "proposed": 2,
        "dropped": {"quote_not_found": 1, "unknown_segment": 1},
    }

    with world.sessions() as session:
        proposals = ClientKnowledgeRepository(session).proposals(client_scope(world, session))
    assert {p.title for p in proposals} == {"Pivovar vaří od roku 1998", "Znalost značky 41 %"}
    for p in proposals:
        assert p.status is ProposalStatus.PROPOSED
        assert p.study_id is None and p.proposed_by == world.lead_id
        assert p.provenance["authored"] == "ai" and p.provenance["run_id"] == run_id
        assert p.provenance["source_id"] == source_id
    # The locator is the segment's as the reader placed it, never one the model wrote.
    assert {p.provenance["segment"]: p.content["locator"] for p in proposals} == {
        0: {"line": 1},
        1: {"line": 3},
    }
    finding = next(p for p in proposals if p.kind.value == "FINDING")
    assert finding.content["quote"] == "zná značku 41 % dospělých v kraji"

    client_spent, study_spent = spent(world)
    assert client_spent > 0
    assert study_spent == 0


def test_unconfigured_it_parks_without_a_call_or_an_attempt(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id, _ = start(world, store)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport, enabled=False)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert step["status"] is not StepRunStatus.SUCCEEDED
    assert step["attempts"][-1]["error"]["reason"] == "client_source_proposals_unconfigured"
    assert transport.requests == []
    assert spent(world) == (0.0, 0.0)


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"AIA_AI_ROUTE_RETENTION_DAYS": ""}, "egress_retention_unspecified"),
        ({"AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL"}, "egress_route_not_approved_for_class"),
    ],
)
def test_a_route_not_cleared_for_client_material_parks_before_any_call(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
    override: dict[str, str],
    reason: str,
) -> None:
    """The document is Class A: egress refuses it on a route not cleared for it."""
    run_id, _ = start(world, store)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport, **override)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert step["status"] is not StepRunStatus.SUCCEEDED
    assert step["attempts_consumed"] == 0
    assert step["attempts"][-1]["error"]["reason"] == reason
    assert transport.requests == []
    assert spent(world) == (0.0, 0.0)


def test_a_dataset_is_refused_by_name_before_any_call(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    table = "značka;znalost\nLupínek;41\nKolín;12\n".encode()
    run_id, _ = start(world, store, filename="znalost.csv", data=table)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    run = run_state(world, run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    assert run["steps"][0]["attempts"][-1]["error"]["reason"] == "dataset_not_extracted"
    assert transport.requests == []


def test_a_budget_that_cannot_hold_the_call_waits_and_a_lift_lets_it_finish(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id, _ = start(world, store, budget=1.0)  # the hold is $1.50
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert step["status"] is StepRunStatus.AWAITING_BUDGET
    assert transport.requests == []
    assert spent(world) == (0.0, 0.0)

    with world.sessions() as session:
        lift_client_budget_wait(
            session,
            client_scope(world, session),
            work_scope(world, session),
            run_id,
            "extract",
            budget_usd=5.0,
        )
        session.commit()
    assert w.run_once()
    assert run_state(world, run_id)["status"] is WorkflowRunStatus.COMPLETED
    assert len(transport.requests) == 1
    client_spent, study_spent = spent(world)
    assert 0 < client_spent <= 5.0 and study_spent == 0


@pytest.mark.parametrize("enabled", ["false", ""])
def test_settings_bind_extraction_only_when_enabled(enabled: str) -> None:
    on = settings()
    assert on.client_source_proposals_enabled
    assert "FAST_EXTRACTION" in on.model_document()["policies"][0]["bindings"]
    off = settings(AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED=enabled)
    assert not off.client_source_proposals_enabled
    assert "FAST_EXTRACTION" not in off.model_document()["policies"][0]["bindings"]


def test_a_reservation_below_two_calls_at_the_ceilings_stops_the_worker() -> None:
    from aia_executors.ai_runtime import AIRuntimeConfigError

    with pytest.raises(AIRuntimeConfigError, match="client source reservation"):
        settings(AIA_AI_CLIENT_SOURCE_RESERVATION_USD="0.01")
