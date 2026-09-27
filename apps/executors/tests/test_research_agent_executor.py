"""Native design jobs through the real worker, gateway, adapter and ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from aia_core.application.research import ResearchAgentJobs
from aia_core.domain.design import DesignRejected
from aia_core.domain.research_agents import ResearchAction
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors.ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_gateway
from aia_executors.registry import registry_for
from aia_executors.research_agents import ResearchAgentConfig, ResearchAgentExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker

ANSWER = {
    "title": "Concept",
    "problem_summary": "Test a fictional concept",
    "decision_use": "Launch",
    "objectives": ["Test appeal"],
    "research_questions": ["Why?"],
    "hypotheses": [],
    "recommended_topics": [],
    "tracked_sets": [],
    "non_object_measures": [],
    "questions_for_user": [],
    "complexity": "short",
    "method_reason": "Short study",
    "ready_for_questionnaire": True,
}


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


@dataclass
class RecordedBedrock:
    requests: list[HttpRequest] = field(default_factory=list)
    uncertain: bool = False

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        self.requests.append(request)
        if self.uncertain:
            from aia_core.domain.ai_contracts import Delivery

            raise TransportFailure("lost response", delivery=Delivery.UNKNOWN)
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": "design-request-1"},
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
                "usage": {"inputTokens": 900, "outputTokens": 200, "totalTokens": 1100},
            },
        )


def settings(client_id: str, **overrides: str) -> AIRuntimeSettings:
    env = {
        "AIA_ENV": "test",
        "AIA_AI_RUNTIME_ENABLED": "true",
        "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
        "AIA_BEDROCK_REGION": "eu-central-1",
        "AIA_BEDROCK_MODEL_ID": "eu.test-design-v1:0",
        "AIA_AI_POLICY_VERSION": "test-v1",
        "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
        "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
        "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
        "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
        "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
        "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
        "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
        "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
        "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
        "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
        "AIA_AI_RESEARCH_RESERVATION_USD": "2",
        "AIA_AI_FICTIONAL_CLIENT_IDS": client_id,
        **overrides,
    }
    result = AIRuntimeSettings.from_env(env)
    assert result is not None
    return result


def start(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content={"title": "Fictional concept", "goal": "Test concept", "sections": []},
            source_stage="brief",
        )
        job = ResearchAgentJobs(session, scope).start(
            design_revision_id=revision.revision_id, action=ResearchAction.ANALYZE
        )
        session.commit()
        return job.run_id


def worker(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
    transport: RecordedBedrock,
    *,
    enabled: bool = True,
    fictional: bool = True,
) -> Worker:
    cfg = settings(world.client_id if fictional else "")
    executor = ResearchAgentExecutor(
        store=store,
        build=build,
        gateway=build_gateway(cfg, transport=transport, signer=Signer()) if enabled else None,
        config=ResearchAgentConfig(
            policy_version=cfg.policy_version,
            max_output_tokens=cfg.research_max_output_tokens,
            context_window_tokens=cfg.context_window_tokens,
            reservation_usd=cfg.research_reservation_usd,
            fictional_client_ids=cfg.fictional_client_ids,
        )
        if enabled
        else None,
    )
    return Worker(
        session_factory=world.sessions,
        executors=registry_for(store=store, build=build, research_agent=executor),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="design-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def test_worker_stores_proposal_and_review_creates_a_new_revision(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
) -> None:
    run_id = start(world)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    assert w.run_once()
    assert not w.run_once()
    assert len(transport.requests) == 1
    with world.sessions() as session:
        jobs = ResearchAgentJobs(session, world.lead_scope(session))
        job = jobs.get(run_id)
        assert job["status"] is WorkflowRunStatus.COMPLETED
        payload = jobs.result(run_id, store=store)
        assert payload["provenance"]["provider_request_id"] == "design-request-1"
        assert payload["provenance"]["status"] == "PROPOSED"
        baseline = job["metadata"]["design_revision_id"]
        designs = StudyDesignRepository(session, world.lead_scope(session))
        assert designs.latest().revision_id == baseline
        accepted, created = jobs.accept(run_id, store=store, expected_revision_id=baseline)
        assert created and accepted.parent_revision == 1
        assert designs.content(baseline).get("research_plan") is None
        with pytest.raises(DesignRejected):
            jobs.accept(run_id, store=store, expected_revision_id=baseline)
        session.commit()


@pytest.mark.parametrize("enabled,fictional", [(False, True), (True, False)])
def test_unconfigured_or_confidential_design_never_calls_bedrock(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
    enabled: bool,
    fictional: bool,
) -> None:
    run_id = start(world)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport, enabled=enabled, fictional=fictional)
    assert w.run_once()
    assert not w.run_once()
    assert transport.requests == []
    with world.sessions() as session:
        assert (
            ResearchAgentJobs(session, world.lead_scope(session)).get(run_id)["status"]
            is WorkflowRunStatus.WAITING_PROVIDER
        )


def test_unknown_delivery_waits_for_recovery_without_resending(
    world: Any,
    database_url: str,
    store: Any,
    build: Any,
) -> None:
    run_id = start(world)
    transport = RecordedBedrock(uncertain=True)
    w = worker(world, database_url, store, build, transport)
    assert w.run_once()
    assert not w.run_once()
    assert len(transport.requests) == 1
    with world.sessions() as session:
        assert (
            ResearchAgentJobs(session, world.lead_scope(session)).get(run_id)["status"]
            is WorkflowRunStatus.RECOVERY_REQUIRED
        )


def test_reservation_must_cover_primary_and_repair_at_verified_prices() -> None:
    with pytest.raises(AIRuntimeConfigError, match="two calls"):
        settings("fictional", AIA_AI_RESEARCH_RESERVATION_USD="0.25")
    with pytest.raises(AIRuntimeConfigError, match="output limit"):
        settings("fictional", AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS="9000")


def test_identical_model_context_does_not_reuse_a_different_revision_baseline(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    first = start(world)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    assert w.run_once()
    with world.sessions() as session:
        scope = world.lead_scope(session)
        designs = StudyDesignRepository(session, scope)
        baseline = designs.content(designs.latest().revision_id)
        # Provider is deliberately absent from model context, but remains part
        # of the saved project baseline. An old full-project artifact is unsafe.
        revision, _ = designs.submit(
            content={**baseline, "provider": "historical-selection"}, source_stage="brief"
        )
        second = ResearchAgentJobs(session, scope).start(
            design_revision_id=revision.revision_id, action=ResearchAction.ANALYZE
        )
        session.commit()
    assert w.run_once()
    assert len(transport.requests) == 2
    with world.sessions() as session:
        jobs = ResearchAgentJobs(session, world.lead_scope(session))
        first_result = jobs.result(first, store=store)
        second_result = jobs.result(second.run_id, store=store)
        assert (
            first_result["provenance"]["context_sha256"]
            == second_result["provenance"]["context_sha256"]
        )
        assert (
            first_result["provenance"]["design_revision_id"]
            != second_result["provenance"]["design_revision_id"]
        )
        assert second_result["result"]["project"]["provider"] == "historical-selection"
