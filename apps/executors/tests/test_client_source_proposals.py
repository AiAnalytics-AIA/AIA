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
from aia_core.application.source_proposals import (
    latest_source_proposals,
    start_source_proposals,
)
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
        "AIA_AI_CLIENT_SOURCE_RESERVATION_USD": "0.5",
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
    internal: bool = False,
) -> tuple[str, str]:
    """Keep the document, set the client's budget and start the proposals: (run, source).
    ``internal``: a person marked it "Interní dokument" first."""
    with world.sessions() as session:
        client = session.get(ClientRow, world.client_id)
        assert client is not None
        client.budget_usd, client.spent_usd = budget, 0.0
        sources = ClientSourceRepository(session, store)
        record, _ = sources.add(client_scope(world, session), filename=filename, data=data)
        if internal:
            record, _ = sources.mark_internal(
                client_scope(world, session), record.source_id, internal=True
            )
        if record.family.value == "DOCUMENT":
            # As a person asks: the API's start (lifecycle K2d4).
            run_id = start_source_proposals(
                session,
                client_scope(world, session),
                work_scope(world, session),
                store,
                record.source_id,
            ).run_id
        else:
            # A source the start refuses, queued by hand to show the step refuses it too.
            pin = sources.reading_pin(client_scope(world, session), record.source_id)
            run_id = start_client_work(
                session,
                work_scope(world, session),
                workflow_type=CLIENT_SOURCE_PROPOSALS,
                idempotency_key=f"by-hand:{record.source_id}",
                step_inputs={
                    "extract": {
                        "source_id": record.source_id,
                        "reading_sha256": pin.reading_sha256,
                        "harness_version": HARNESS_VERSION,
                    }
                },
            ).run_id
        session.commit()
        return run_id, record.source_id


def run_state(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return WorkflowRepository(session, work_scope(world, session)).get_run(run_id)


def latest(world: Any, store: Any) -> Any:
    """The run as a person follows it (lifecycle K2d4)."""
    with world.sessions() as session:
        sources = ClientSourceRepository(session, store).sources(client_scope(world, session))
        return latest_source_proposals(
            session,
            client_scope(world, session),
            work_scope(world, session),
            store,
            sources[0].source_id,
        )


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
        "sent": 1,
        "replayed": 0,
        "proposed": 2,
        "dropped": {"quote_not_found": 1, "unknown_segment": 1},
        "data_class": "CLASS_A_CLIENT_CONFIDENTIAL",
        "class_source": "rule:client_source",
        "answer_classes": ["CLASS_A_CLIENT_CONFIDENTIAL"],
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
    # A person following it reads the step's own reason, not the worker's general one.
    followed = latest(world, store)
    assert followed is not None and followed.run_id == run_id
    assert (followed.step_status, followed.reason) == (
        "WAITING_PROVIDER",
        "client_source_proposals_unconfigured",
    )
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


def test_a_source_marked_internal_is_sent_as_class_c_on_a_route_for_class_c(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """The owner's rule of 2026-10-19: a person marked the document "Interní dokument", an
    internal AIA document, so it is Class C and a route approved for Class C alone takes it;
    each proposal says which rule classified what it came from."""
    run_id, source_id = start(world, store, internal=True)
    transport = RecordedBedrock()
    w = worker(
        world, database_url, store, build, transport, AIA_AI_ROUTE_APPROVED_FOR="CLASS_C_INTERNAL"
    )
    assert w.run_once()
    assert len(transport.requests) == 1
    step = run_state(world, run_id)["steps"][0]
    assert (step["output"]["data_class"], step["output"]["class_source"]) == (
        "CLASS_C_INTERNAL",
        "rule:internal_document",
    )
    with world.sessions() as session:
        proposals = ClientKnowledgeRepository(session).proposals(client_scope(world, session))
    assert proposals and all(
        (p.provenance["data_class"], p.provenance["class_source"])
        == ("CLASS_C_INTERNAL", "rule:internal_document")
        for p in proposals
    )
    assert all(p.provenance["source_id"] == source_id for p in proposals)


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
    run_id, _ = start(world, store, budget=0.25)  # the hold is $0.50
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert step["status"] is StepRunStatus.AWAITING_BUDGET
    followed = latest(world, store)
    assert followed is not None and followed.reason == step["waiting_reason"]
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


def test_the_reservation_covers_two_calls_at_the_request_window_not_the_models() -> None:
    """K2d6: a request is bounded by bytes, so its hold is two calls at its own window
    (48,588 tokens at 4,096 out: $0.4144 at $3 / $15), not at the model's 200,000 ($1.32)."""
    from aia_executors.ai_runtime import AIRuntimeConfigError

    with pytest.raises(AIRuntimeConfigError, match="client source reservation"):
        settings(AIA_AI_CLIENT_SOURCE_RESERVATION_USD="0.41")
    assert (
        settings(AIA_AI_CLIENT_SOURCE_RESERVATION_USD="0.42").client_source_reservation_usd == 0.42
    )


def test_a_document_over_the_request_cap_is_refused_before_any_call(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """Short lines of four-byte characters: within the reading's character cap, far over
    the requests a document may take. Refused by name; nothing sent, nothing spent."""
    text = ("😀😀😀😀\n\n" * 50_000).encode()
    run_id, _ = start(world, store, filename="emoji.txt", data=text)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    run = run_state(world, run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    assert run["steps"][0]["attempts"][-1]["error"]["reason"] == "too_many_requests"
    assert transport.requests == []
    assert spent(world) == (0.0, 0.0)


def test_a_document_parked_between_batches_resumes_without_paying_twice(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """Two batches; the client's budget holds the first request ($0.50) and not the
    second on top of what the first spent. Parked, then lifted: the step asks only the
    second batch -- the first is replayed from the journal, never re-sent or re-charged."""
    page = ("Fiktivní pivovar Lupínek vaří světlé pivo v Kolíně. " * 300).strip()
    two_batches = f"{page}\n\n{page} Druhá strana.".encode()
    run_id, _ = start(world, store, budget=0.505, filename="dlouhy.txt", data=two_batches)
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert step["status"] is StepRunStatus.AWAITING_BUDGET
    assert len(transport.requests) == 1
    first_charge = spent(world)[0]
    assert first_charge > 0

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
    run = run_state(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert len(transport.requests) == 2  # the first batch was not sent again
    output = run["steps"][0]["output"]
    assert (output["batches"], output["sent"], output["replayed"]) == (2, 1, 1)
    # Charged for two requests, not three.
    assert spent(world)[0] == pytest.approx(2 * first_charge)


def test_a_replayed_answer_keeps_the_class_it_was_sent_as_when_the_mark_changes(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """Codex on #487: the first batch is sent as Class C (the document marked "Interní
    dokument"), the step parks at the budget, a person unmarks it, and the resumed step sends
    the second batch as Class A. The first answer is replayed, and its proposals still say
    Class C -- the class it was sent as, not the mark the source carries when replayed."""
    # Each batch holds one segment the recorded answer quotes: the first batch segment 0,
    # the second segment 1, so each batch files one proposal of its own.
    first = ("Fiktivní pivovar Lupínek vaří od roku 1998 v Kolíně. " * 300).strip()
    second = ("Podle průzkumu zná značku 41 % dospělých v kraji. " * 300).strip()
    two_batches = f"{first}\n\n{second}".encode()
    run_id, source_id = start(
        world, store, budget=0.505, filename="dlouhy.txt", data=two_batches, internal=True
    )
    transport = RecordedBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    assert run_state(world, run_id)["steps"][0]["status"] is StepRunStatus.AWAITING_BUDGET
    assert len(transport.requests) == 1

    with world.sessions() as session:
        ClientSourceRepository(session, store).mark_internal(
            client_scope(world, session), source_id, internal=False
        )
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
    run = run_state(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    output = run["steps"][0]["output"]
    assert (output["sent"], output["replayed"]) == (1, 1)
    assert (output["data_class"], output["class_source"]) == (
        "CLASS_A_CLIENT_CONFIDENTIAL",
        "rule:client_source",
    )
    assert output["answer_classes"] == ["CLASS_A_CLIENT_CONFIDENTIAL", "CLASS_C_INTERNAL"]
    with world.sessions() as session:
        proposals = ClientKnowledgeRepository(session).proposals(client_scope(world, session))
    by_call: dict[str, set[tuple[str, str]]] = {}
    for p in proposals:
        by_call.setdefault(p.provenance["call_id"], set()).add(
            (p.provenance["data_class"], p.provenance["class_source"])
        )
    assert sorted(by_call.values(), key=sorted) == sorted(
        [
            {("CLASS_A_CLIENT_CONFIDENTIAL", "rule:client_source")},
            {("CLASS_C_INTERNAL", "rule:internal_document")},
        ],
        key=sorted,
    )


def test_unmarking_a_source_mid_run_stops_the_requests_not_yet_sent(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """Independent review of #487: a person unmarks "Interní dokument" while the run is
    between its batches (here, while the first request is answered). The second request
    was built as Class C; it is not sent. The step fails by name, the first answer stays
    kept, and nothing more is charged."""
    first = ("Fiktivní pivovar Lupínek vaří od roku 1998 v Kolíně. " * 300).strip()
    second = ("Podle průzkumu zná značku 41 % dospělých v kraji. " * 300).strip()
    run_id, source_id = start(
        world, store, filename="dlouhy.txt", data=f"{first}\n\n{second}".encode(), internal=True
    )

    @dataclass
    class UnmarkingBedrock(RecordedBedrock):
        async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
            if not self.requests:
                with world.sessions() as session:
                    ClientSourceRepository(session, store).mark_internal(
                        client_scope(world, session), source_id, internal=False
                    )
                    session.commit()
            return await super().send(request, timeout_s=timeout_s)

    transport = UnmarkingBedrock()
    w = worker(world, database_url, store, build, transport)
    w.run_once()
    step = run_state(world, run_id)["steps"][0]
    assert len(transport.requests) == 1  # the second batch, built as Class C, was not sent
    assert step["attempts"][-1]["error"]["reason"] == "source_class_changed"
    assert step["status"] is not StepRunStatus.SUCCEEDED
