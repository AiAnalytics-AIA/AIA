"""AI respondent fieldwork under the real worker loop, over recorded Bedrock exchanges.

The acceptance run of the Agent Runtime Foundation: a research run whose recorded
source is ``ai_runtime`` is answered by AI respondents on the fictional roster,
through ``GovernedModelGateway`` and the Bedrock adapter, over a route approved for
Class C only -- and then continues through the existing Aggregate and Sociomap. No
network: ``ScriptedBedrock`` is an ``HttpTransport`` that answers each Converse
request with what the request's own tool schema asks for (a recorded double, in the
shape of ``fixtures/model_adapters/bedrock/``), or with a recorded failure.

Everything else is real: the database, the lease, the heartbeat, the reservations,
the ledger, the artifact store and the scope ``ScopeResolver`` issues.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.ai_contracts import Delivery, UsageOutcome
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import (
    RUNTIME_UNAVAILABLE_REASON,
    FailureClass,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import BudgetReservationRow, StepAttemptRow, StudyRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors import ai_fieldwork
from aia_executors.ai_runtime import AIRuntimeConfigError, AIRuntimeSettings, build_ai_fieldwork
from aia_executors.registry import build_registry, registry_for
from aia_executors.research import FIELDWORK_DATASET
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

PROFILE = "eu.example.respondent-model-v1:0"  # a test id; the real one is configuration
N = 20

DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "n": N,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q_sex",
                    "text": "Jaké je vaše pohlaví?",
                    "typ": "vyber",
                    "kategorie": ["muž", "žena"],
                },
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                    "povolit_nevim": True,
                },
                {"id": "q3", "text": "Proč právě to?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}
#: Blocks per respondent for DESIGN: [q1, q2] closed, [q3] open, [5 battery objects].
BLOCKS = 3


def _env(**overrides: str) -> dict[str, str]:
    env = {
        "AIA_ENV": "test",
        "AIA_AI_RUNTIME_ENABLED": "true",
        "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
        "AIA_BEDROCK_REGION": "eu-central-1",
        "AIA_BEDROCK_MODEL_ID": PROFILE,
        "AIA_AI_POLICY_VERSION": "aia-model-policy-test-1",
        # Test prices, not Bedrock's: the real entry is dated configuration (ADR 0010).
        "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
        "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
        "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
        "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
        "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
        "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
        "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
        "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
        "AIA_AI_MATERIAL_CLASSIFICATIONS": "["
        + MaterialApproval(
            sha256=material_sha256(DESIGN),
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            provenance="test material explicitly classified as confidential",
        ).model_dump_json()
        + "]",
    }
    env.update(overrides)
    return env


class Signer:
    def __init__(self) -> None:
        self.count = 0

    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        self.count += 1
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


def _resolve(schema: Mapping[str, Any], node: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node.get("$ref")
    if isinstance(ref, str):
        return schema["$defs"][ref.rsplit("/", 1)[-1]]
    return node


def _answer_for(schema: Mapping[str, Any], seed: str) -> dict[str, Any]:
    """What a well-behaved respondent returns: a valid object for this block's schema."""
    out: dict[str, Any] = {}
    for item_id, node in schema["properties"].items():
        props = _resolve(schema, node)["properties"]
        if "probabilities" in props:
            k = int(props["probabilities"]["minItems"])
            peak = int(hashlib.sha256((seed + item_id).encode()).hexdigest(), 16) % k
            out[item_id] = {
                "probabilities": [0.7 if i == peak else 0.3 / (k - 1) for i in range(k)]
            }
        elif "selected" in props:
            out[item_id] = {"selected": [1]}
        else:
            out[item_id] = {"text": "Protože mi to chutná (fiktivní odpověď)."}
    return out


@dataclass
class ScriptedBedrock:
    """An ``HttpTransport`` standing in for Bedrock Converse. Records every request."""

    #: call number (1-based) -> a recorded failure: an HttpResponse or a TransportFailure
    failures: dict[int, HttpResponse | TransportFailure] = field(default_factory=dict)
    #: call number -> a replacement tool input (an off-contract answer)
    answers: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: called with the call number before answering, on the transport's thread
    hook: Callable[[int], None] | None = None
    requests: list[HttpRequest] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        with self.lock:
            self.requests.append(request)
            number = len(self.requests)
        if self.hook is not None:
            self.hook(number)
        failure = self.failures.get(number)
        if isinstance(failure, TransportFailure):
            raise failure
        if isinstance(failure, HttpResponse):
            return failure
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]
        schema = tool["inputSchema"]["json"]
        answer = self.answers.get(number) or _answer_for(schema, str(number))
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{number:05d}"},
            body={
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": f"t{number}",
                                    "name": tool["name"],
                                    "input": answer,
                                }
                            }
                        ],
                    }
                },
                "stopReason": "tool_use",
                "usage": {"inputTokens": 900, "outputTokens": 120, "totalTokens": 1020},
                "metrics": {"latencyMs": 640},
            },
        )


def _error(status: int, error_type: str, **headers: str) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={"x-amzn-requestid": "req-err", "x-amzn-errortype": error_type, **headers},
        body={"message": error_type},
    )


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #


@pytest.fixture
def run_with(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Callable[..., Worker]:
    def make(
        transport: ScriptedBedrock | None,
        *,
        env: dict[str, str] | None = None,
        lease_seconds: int = 30,
    ) -> Worker:
        settings = AIRuntimeSettings.from_env(env if env is not None else _env())
        ai = (
            build_ai_fieldwork(settings, build=build, transport=transport, signer=Signer())
            if settings is not None
            else None
        )
        executors: dict[str, StepExecutor] = registry_for(store=store, build=build, ai_runtime=ai)
        return Worker(
            session_factory=sessions,
            executors=executors,
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="ai-worker",
                lease_seconds=lease_seconds,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return make


def _start(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, fieldwork_source=FieldworkSource.AI_RUNTIME
        )
        session.commit()
        return started.run_id


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _steps(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["node_key"]: s for s in run["steps"]}


def _ledger(world: Any, run_id: str) -> list[Any]:
    with world.sessions() as session:
        return AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)


def _fictional(world: Any) -> dict[str, str]:
    return _env(
        AIA_AI_FICTIONAL_CLIENT_IDS=world.client_id,
        AIA_AI_MATERIAL_CLASSIFICATIONS="["
        + MaterialApproval(
            sha256=material_sha256(DESIGN),
            data_class=DataClass.CLASS_C_INTERNAL,
            provenance="generated wholly by this test",
        ).model_dump_json()
        + "]",
    )


# --------------------------------------------------------------------------- #
# the acceptance run
# --------------------------------------------------------------------------- #


def test_ai_respondents_answer_and_the_run_continues_through_aggregate_and_sociomap(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock()
    run_id = _start(world)
    assert _drain(run_with(bedrock, env=_fictional(world))) == ["completed"] * 5
    run = _run(world, run_id)
    steps = _steps(run)
    assert run["status"] is WorkflowRunStatus.COMPLETED

    # One call per respondent per block; the fact question was never asked.
    assert len(bedrock.requests) == N * BLOCKS
    sent = "".join(r.raw_body.decode() for r in bedrock.requests if r.raw_body)
    assert "(ID q_sex)" not in sent  # shown only as history, answered by code
    for secret in (world.study_id, world.client_id, world.organization_id):
        assert secret not in sent, "scope must never be sent to a provider"
    assert all(
        r.url.endswith("/model/eu.example.respondent-model-v1%3A0/converse")
        for r in bedrock.requests
    )
    assert all(
        json.loads(r.raw_body)["inferenceConfig"]["temperature"] == 0.0
        for r in bedrock.requests
        if r.raw_body
    )

    output = steps["run"]["output"]
    assert output["artifact_type"] == FIELDWORK_DATASET
    assert output["data_origin"] == DataOrigin.SYNTHETIC_AI_FICTIONAL.value
    assert output["respondents"] == N
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        payload = research.read_json(output["artifact_id"])
    dataset, provenance = payload["dataset"], payload["provenance"]
    assert dataset["source"] == "ai_runtime" and dataset["origin"] == "SYNTHETIC_AI_FICTIONAL"
    assert all(r["respondent_id"].startswith("FIC-R") for r in dataset["respondents"])
    # The fact is code's: every respondent's sex answer is its persona's own.
    assert {r["answers"]["q_sex"] for r in dataset["respondents"]} <= {"muž", "žena"}
    assert provenance["agent"] == {"id": "aia.research.respondent", "version": "1"}
    assert (
        provenance["prompt"]["id"] == "aia.respondent.block"
        and len(provenance["prompt"]["sha256"]) == 64
    )
    assert provenance["data_class"] == "CLASS_C_INTERNAL"
    assert provenance["lineage"] == ["aia_synthetic_fixture"]
    assert provenance["route_id"] == "bedrock-eu-primary" and provenance["model"] == PROFILE
    assert len(provenance["calls"]) == N * BLOCKS
    assert {c["provider_request_id"] for c in provenance["calls"]} == {
        f"req-{i:05d}" for i in range(1, N * BLOCKS + 1)
    }

    # Every call is on the ledger twice (dispatched, then succeeded), attributed from the scope.
    events = _ledger(world, run_id)
    by_outcome: dict[UsageOutcome, int] = {}
    for e in events:
        by_outcome[e.outcome] = by_outcome.get(e.outcome, 0) + 1
        assert (e.organization_id, e.client_id, e.study_id) == (
            world.organization_id,
            world.client_id,
            world.study_id,
        )
        assert e.route_id == "bedrock-eu-primary" and e.data_class.value == "CLASS_C_INTERNAL"
    assert by_outcome == {UsageOutcome.DISPATCHED: N * BLOCKS, UsageOutcome.SUCCEEDED: N * BLOCKS}
    ledgered = sum(e.cost_usd for e in events if e.outcome is UsageOutcome.SUCCEEDED)
    assert ledgered == pytest.approx(provenance["total_cost_usd"])
    assert ledgered == pytest.approx(N * BLOCKS * (900 * 3 + 120 * 15) / 1_000_000)

    # One reservation per request, each settled once at its real cost; the study was charged.
    with world.sessions() as session:
        reservations = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
        ).all()
        study = session.scalar(select(StudyRow).where(StudyRow.study_id == world.study_id))
    assert len(reservations) == N * BLOCKS
    assert {r.status for r in reservations} == {"SETTLED"}
    assert study is not None and study.spent_usd == pytest.approx(ledgered)

    # Aggregate and Sociomap ran over that dataset, unchanged, and carry its origin.
    for node in ("aggregate", "sociomap"):
        assert steps[node]["status"] is StepRunStatus.SUCCEEDED
        assert steps[node]["output"]["data_origin"] == "SYNTHETIC_AI_FICTIONAL"
    assert steps["sociomap"]["output"]["methodology_status"] == "INTERNAL_ONLY"


# --------------------------------------------------------------------------- #
# the gates: refused before any network use, and the run parks
# --------------------------------------------------------------------------- #


def _assert_parked_before_network(
    world: Any, run_id: str, bedrock: ScriptedBedrock
) -> dict[str, Any]:
    run = _run(world, run_id)
    fieldwork = _steps(run)["run"]
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert fieldwork["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    assert bedrock.requests == [], "nothing may reach the adapter"
    assert _ledger(world, run_id) == []
    assert _steps(run)["aggregate"]["status"] is StepRunStatus.BLOCKED
    error = fieldwork["attempts"][-1]["error"]
    assert fieldwork["attempts"][-1]["failure_class"] is FailureClass.RUNTIME_UNAVAILABLE
    return error


def test_a_real_clients_design_is_class_a_and_the_class_c_route_refuses_it(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    """Residency: without the operator's declaration the questionnaire is client material."""
    bedrock = ScriptedBedrock()
    run_id = _start(world)
    assert _drain(run_with(bedrock)) == ["completed", "completed", "failed"]
    error = _assert_parked_before_network(world, run_id, bedrock)
    assert error["reason"] == "egress_route_not_approved_for_class"
    assert error["data_class"] == "CLASS_A_CLIENT_CONFIDENTIAL"


def test_client_allowlist_does_not_classify_an_unknown_questionnaire(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock()
    run_id = _start(world)
    env = _fictional(world) | {"AIA_AI_MATERIAL_CLASSIFICATIONS": "[]"}
    assert _drain(run_with(bedrock, env=env)) == ["completed", "completed", "failed"]
    error = _assert_parked_before_network(world, run_id, bedrock)
    assert error["reason"] == "egress_unclassified_material"


def test_panel_derived_personas_are_refused_by_the_licence_gate_on_any_route(
    world: Any, run_with: Callable[..., Worker], monkeypatch: pytest.MonkeyPatch
) -> None:
    """OI-61: even over a route approved for client material, panel lineage never leaves."""
    real = ai_fieldwork.fictional_roster

    def panel_roster(n: int, *, seed: int) -> Any:
        return tuple(
            p.model_copy(
                update={"lineage": frozenset({"czech_population_panel"}), "fictional": False}
            )
            for p in real(n, seed=seed)
        )

    monkeypatch.setattr(ai_fieldwork, "fictional_roster", panel_roster)
    bedrock = ScriptedBedrock()
    env = _env(
        AIA_AI_ROUTE_APPROVED_FOR="CLASS_A_CLIENT_CONFIDENTIAL,CLASS_C_INTERNAL",
        AIA_AI_ROUTE_RETENTION_DAYS="0",
    )
    run_id = _start(world)
    assert _drain(run_with(bedrock, env=env)) == ["completed", "completed", "failed"]
    error = _assert_parked_before_network(world, run_id, bedrock)
    assert error["reason"] == "licence_undetermined"
    assert error["lineage"] == ["czech_population_panel"]


def test_a_route_approved_for_nothing_parks(world: Any, run_with: Callable[..., Worker]) -> None:
    bedrock = ScriptedBedrock()
    run_id = _start(world)
    _drain(
        run_with(
            bedrock,
            env=_env(AIA_AI_ROUTE_APPROVED_FOR="", AIA_AI_FICTIONAL_CLIENT_IDS=world.client_id),
        )
    )
    assert _assert_parked_before_network(world, run_id, bedrock)["reason"].startswith("egress_")


def test_without_an_ai_runtime_the_production_registry_still_parks_and_never_substitutes(
    world: Any, run_with: Callable[..., Worker], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(_env()):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    registry = build_registry()
    fieldwork = registry["research_fieldwork"]
    assert fieldwork._ai is None
    assert fieldwork._producers == {}, "no fixture producer in production"
    run_id = _start(world)
    assert _drain(run_with(None, env={})) == ["completed", "completed", "failed"]
    fw = _steps(_run(world, run_id))["run"]
    assert fw["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    assert "nic nebylo vymyšleno" in fw["attempts"][-1]["error"]["message"]


# --------------------------------------------------------------------------- #
# configuration fails closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"AIA_BEDROCK_MODEL_ID": "eu.anthropic.claude-latest"}, "pinned"),
        ({"AIA_BEDROCK_MODEL_ID": "anthropic.claude-x-v1:0"}, "EU inference profile"),
        ({"AIA_BEDROCK_REGION": "us-east-1"}, "not an EU region"),
        ({"AIA_BEDROCK_INPUT_USD_PER_MTOK": ""}, "INPUT_USD_PER_MTOK is required"),
        ({"AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "maybe"}, "not true or false"),
        ({"AIA_AI_FIELDWORK_RESERVATION_USD": "0"}, "must be positive"),
        ({"AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "99999"}, "exceeds"),
        ({"AIA_AI_ROUTE_APPROVED_FOR": "CLASS_Z"}, "unknown data class"),
        ({"AIA_ENV": "production", "AIA_AI_FICTIONAL_CLIENT_IDS": "C1"}, "refused in production"),
    ],
)
def test_an_enabled_runtime_with_unsafe_configuration_refuses_to_start(
    overrides: dict[str, str], match: str
) -> None:
    with pytest.raises(AIRuntimeConfigError, match=match):
        AIRuntimeSettings.from_env(_env(**overrides))


def test_missing_route_approval_keys_refuse_and_retention_is_never_assumed() -> None:
    env = _env()
    del env["AIA_AI_ROUTE_APPROVED_FOR"]
    with pytest.raises(AIRuntimeConfigError, match="APPROVED_FOR is required"):
        AIRuntimeSettings.from_env(env)
    settings = AIRuntimeSettings.from_env(_env())
    assert settings is not None and settings.route().retention_days is None
    assert AIRuntimeSettings.from_env({"AIA_AI_RUNTIME_ENABLED": "false"}) is None


# --------------------------------------------------------------------------- #
# provider errors, recovery, no fallback
# --------------------------------------------------------------------------- #


def test_throttling_parks_for_quota_after_one_request_and_charges_nothing(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock(
        failures={1: _error(429, "ThrottlingException", **{"retry-after": "60"})}
    )
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world)))
    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.WAITING_PROVIDER
    assert fw["attempts"][-1]["failure_class"] is FailureClass.QUOTA
    assert len(bedrock.requests) == 1, "no in-call retry, no second provider"
    outcomes = [e.outcome for e in _ledger(world, run_id)]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.FAILED]
    with world.sessions() as session:
        (reservation,) = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
        ).all()
    assert (reservation.status, reservation.settled_amount_usd) == ("SETTLED", 0.0)


def test_access_denied_fails_permanently_without_fallback(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock(failures={1: _error(403, "AccessDeniedException")})
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world)))
    run = _run(world, run_id)
    assert _steps(run)["run"]["status"] is StepRunStatus.FAILED
    assert _steps(run)["run"]["attempts"][-1]["failure_class"] is FailureClass.PERMISSION
    assert len(bedrock.requests) == 1


def test_an_uncertain_call_needs_recovery_and_is_never_retried(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock(
        failures={1: TransportFailure("read timeout", delivery=Delivery.UNKNOWN)}
    )
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world)))
    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.RECOVERY_REQUIRED
    assert len(bedrock.requests) == 1
    outcomes = [e.outcome for e in _ledger(world, run_id)]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.UNCERTAIN]
    with world.sessions() as session:
        (reservation,) = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
        ).all()
    assert reservation.status == "SETTLED_UNCERTAIN"


def test_an_off_question_answer_gets_one_repair_then_fails_the_attempt(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    off = {"q_invented": {"probabilities": [1.0]}}
    bedrock = ScriptedBedrock(answers={1: off, 2: off})
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world)))
    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.FAILED
    assert fw["attempts"][-1]["failure_class"] is FailureClass.SCHEMA_VIOLATION
    assert len(bedrock.requests) == 2, "the primary and exactly one repair"
    events = _ledger(world, run_id)
    assert [e.purpose.value for e in events if e.outcome is UsageOutcome.FAILED] == [
        "PRIMARY",
        "SCHEMA_REPAIR",
    ]
    with world.sessions() as session:
        (reservation,) = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
        ).all()
    # Both calls were answered and billed; the one reservation settled at their sum.
    assert reservation.settled_amount_usd == pytest.approx(
        sum(e.cost_usd for e in events if e.outcome.is_terminal)
    )


def test_a_repaired_answer_is_used_and_both_calls_are_charged(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock(answers={1: {"q1": {"probabilities": [1.0]}}})
    run_id = _start(world)
    assert _drain(run_with(bedrock, env=_fictional(world))) == ["completed"] * 5
    assert len(bedrock.requests) == N * BLOCKS + 1
    purposes = [e.purpose.value for e in _ledger(world, run_id) if e.outcome.is_terminal]
    assert purposes.count("SCHEMA_REPAIR") == 1


def test_a_probability_vector_with_no_mass_fails_the_attempt_rather_than_leaving_a_blank(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    zero = {"q1": {"probabilities": [0, 0, 0, 0, 0]}, "q2": {"probabilities": [1, 0, 0, 0]}}
    bedrock = ScriptedBedrock(answers={1: zero})
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world)))
    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.FAILED
    assert fw["attempts"][-1]["error"]["reason"] == "respondent_output_invalid"


def test_a_study_without_budget_parks_awaiting_budget_before_any_call(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    bedrock = ScriptedBedrock()
    run_id = _start(world)
    _drain(run_with(bedrock, env=_fictional(world) | {"AIA_AI_FIELDWORK_RESERVATION_USD": "30"}))
    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.AWAITING_BUDGET
    assert bedrock.requests == []


# --------------------------------------------------------------------------- #
# cancellation, the lease, the heartbeat
# --------------------------------------------------------------------------- #


def test_cancellation_during_a_call_charges_that_call_and_sends_no_other(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world)

    def cancel(number: int) -> None:
        if number == 1:
            with world.sessions() as session:
                WorkflowRepository(session, world.lead_scope(session)).request_cancel(run_id)
                session.commit()
            time.sleep(0.5)  # the heartbeat carries the cancellation back

    bedrock = ScriptedBedrock(hook=cancel)
    _drain(run_with(bedrock, env=_fictional(world)))
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.CANCELLED
    assert len(bedrock.requests) == 1
    outcomes = [e.outcome for e in _ledger(world, run_id)]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.SUCCEEDED]
    with world.sessions() as session:
        study = session.scalar(select(StudyRow).where(StudyRow.study_id == world.study_id))
    assert study is not None and study.spent_usd > 0, "the answered call was charged"


def test_a_lease_lost_mid_call_still_leaves_the_answer_on_the_ledger(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world)

    def steal(number: int) -> None:
        if number == 1:
            with world.sessions() as session:
                attempt = session.scalar(
                    select(StepAttemptRow).where(
                        StepAttemptRow.status.in_(("CLAIMED", "EXECUTING"))
                    )
                )
                assert attempt is not None
                attempt.worker_id = "another-worker"
                session.commit()

    bedrock = ScriptedBedrock(hook=steal)
    worker = run_with(bedrock, env=_fictional(world))
    endings = [worker.run_once().ending for _ in range(3)]  # type: ignore[union-attr]
    assert endings[-1] == "lease_lost"
    assert len(bedrock.requests) == 1, "nothing more is sent once the lease is gone"
    outcomes = [e.outcome for e in _ledger(world, run_id)]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.SUCCEEDED]
    assert _ledger(world, run_id)[-1].provider_request_id == "req-00001"


def test_the_heartbeat_keeps_the_lease_through_a_call_longer_than_the_lease(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world)
    seen: list[Any] = []

    def slow(number: int) -> None:
        if number == 1:
            for _ in range(3):
                with world.sessions() as session:
                    attempt = session.scalar(
                        select(StepAttemptRow).where(
                            StepAttemptRow.status.in_(("CLAIMED", "EXECUTING"))
                        )
                    )
                    assert attempt is not None
                    seen.append(attempt.lease_until)
                time.sleep(1.2)

    bedrock = ScriptedBedrock(hook=slow)
    assert _drain(run_with(bedrock, env=_fictional(world), lease_seconds=2)) == ["completed"] * 5
    assert seen[0] < seen[-1], "the lease was extended while the call was in flight"
    fw = _steps(_run(world, run_id))["run"]
    assert len(fw["attempts"]) == 1


# --------------------------------------------------------------------------- #
# Study isolation
# --------------------------------------------------------------------------- #


def test_calls_are_attributed_to_the_runs_study_and_invisible_to_another(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    """The scope comes from the lease; a sibling Study of the same client sees nothing."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.scope import StudyStatus
    from aia_core.infrastructure.scope_repository import ScopeRepository
    from aia_core.infrastructure.tables import UserRow

    with world.sessions() as session:
        owner = session.scalar(select(UserRow).where(UserRow.email == "owner@art-chain.io"))
        assert owner is not None
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=world.organization_id)
        )
        sibling = ScopeRepository(session).create_study(
            admin, client_id=world.client_id, slug="other", name="Other", budget_usd=25.0
        )
        session.flush()
        sibling_scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
            study_id=sibling.study_id,
        )
        ScopeRepository(session).set_study_status(sibling_scope, StudyStatus.ACTIVE)
        session.commit()
        sibling_id = sibling.study_id

    run_id = _start(world)
    assert _drain(run_with(ScriptedBedrock(), env=_fictional(world))) == ["completed"] * 5
    events = _ledger(world, run_id)
    assert events and {e.study_id for e in events} == {world.study_id}
    with world.sessions() as session:
        other = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
            study_id=sibling_id,
        )
        assert AIUsageRepository(session, other).events() == []
        assert AIUsageRepository(session, other).events(run_id=run_id) == []


def test_the_develop_worker_passes_every_ai_runtime_key_and_no_credential() -> None:
    """A key the settings read but Compose does not pass would be silently absent on the host."""
    import re
    from pathlib import Path

    import aia_executors.ai_runtime as runtime

    root = Path(__file__).resolve().parents[3]
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    compose = (root / "deploy" / "develop" / "docker-compose.yml").read_text(encoding="utf-8")
    example = (root / "deploy" / "develop" / "env.example").read_text(encoding="utf-8")
    read = set(re.findall(r'"(AIA_(?:AI|BEDROCK)_[A-Z_]+)"', source))
    # The worker's block ends where the next service begins (two-space indent).
    worker = re.split(r"\n  [a-z][a-z-]*:\n", compose.split("\n  worker:\n", 1)[1], maxsplit=1)[0]
    passed = set(re.findall(r"^\s+(AIA_(?:AI|BEDROCK)_[A-Z_]+):", worker, flags=re.M))
    assert read and read == passed
    assert read <= set(re.findall(r"^(AIA_(?:AI|BEDROCK)_[A-Z_]+)=", example, flags=re.M))
    assert "AWS_ACCESS_KEY_ID" not in compose and "AWS_SECRET_ACCESS_KEY" not in compose


def test_the_settings_page_reads_the_switch_with_the_workers_vocabulary() -> None:
    """Compose hands the web and the worker the same AIA_AI_RUNTIME_ENABLED; if /config
    parsed it differently, Settings could say off while respondent calls ran."""
    import re
    from pathlib import Path

    import aia_executors.ai_runtime as runtime

    root = Path(__file__).resolve().parents[3]
    route = (root / "apps" / "web" / "src" / "app" / "config" / "route.ts").read_text(
        encoding="utf-8"
    )

    def spelled(name: str) -> set[str]:
        found = re.search(rf"const {name} = new Set\(\[([^\]]*)\]\)", route)
        assert found, f"route.ts no longer declares {name}"
        return set(re.findall(r'"([^"]*)"', found.group(1)))

    assert spelled("TRUE") == runtime._TRUE
    assert spelled("FALSE") == runtime._FALSE


# --------------------------------------------------------------------------- #
# A TLS failure after sending, over the real transport: uncertain, never free
# --------------------------------------------------------------------------- #


def test_an_ssl_failure_after_sending_needs_recovery_and_is_never_settled_as_free(
    world: Any, run_with: Callable[..., Worker], tmp_path: Any
) -> None:
    """The real Urllib3Transport against a local TLS server that reads the whole
    request and then corrupts the response stream. The call may have been billed:
    it is ledgered UNCERTAIN at its ceiling, the reservation is SETTLED_UNCERTAIN
    (not settled at zero), the step needs a person, and nothing is sent again."""
    import os
    import shutil
    import socket
    import ssl
    import subprocess

    from aia_core.infrastructure.model_adapters.live_transport import Urllib3Transport

    openssl = shutil.which("openssl")
    assert openssl, "the TLS test needs the openssl CLI (present on every CI runner)"
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    received: list[int] = []

    def serve() -> None:
        while True:
            try:
                raw, _ = listener.accept()
            except OSError:
                return
            tls = context.wrap_socket(raw, server_side=True)
            data = b""
            while b"\r\n\r\n" not in data:
                data += tls.recv(65536)
            head, _, body = data.partition(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in head.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            while len(body) < length:
                body += tls.recv(65536)
            received.append(len(body))
            os.write(tls.fileno(), b"\x17\x03\x03\x00\x20" + b"\x00" * 32)  # forged record
            time.sleep(0.2)
            raw.close()

    threading.Thread(target=serve, daemon=True).start()

    live = Urllib3Transport(ca_certs=str(cert))

    class ToStub:
        """Sends the adapter's exact request to the local server instead of AWS."""

        async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
            path = request.url.split("amazonaws.com", 1)[1]
            return await live.send(
                HttpRequest(
                    method=request.method,
                    url=f"https://127.0.0.1:{port}{path}",
                    headers=request.headers,
                    body=request.body,
                    raw_body=request.raw_body,
                ),
                timeout_s=timeout_s,
            )

    try:
        run_id = _start(world)
        _drain(run_with(ToStub(), env=_fictional(world)))
    finally:
        listener.close()

    fw = _steps(_run(world, run_id))["run"]
    assert fw["status"] is StepRunStatus.RECOVERY_REQUIRED
    assert len(fw["attempts"]) == 1, "an uncertain call was retried"
    assert len(received) == 1 and received[0] > 0, "the request reached the server once"
    events = _ledger(world, run_id)
    assert [e.outcome for e in events] == [UsageOutcome.DISPATCHED, UsageOutcome.UNCERTAIN]
    uncertain = events[-1]
    assert uncertain.cost_basis.value == "CEILING" and uncertain.cost_usd > 0
    with world.sessions() as session:
        (reservation,) = session.scalars(
            select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
        ).all()
        attempt = session.scalar(
            select(StepAttemptRow).where(StepAttemptRow.step_id == fw["step_id"])
        )
    assert reservation.status == "SETTLED_UNCERTAIN", "never settled as a known zero-cost failure"
    assert attempt is not None
    assert attempt.paid_call_dispatched and not attempt.paid_call_outcome_known
