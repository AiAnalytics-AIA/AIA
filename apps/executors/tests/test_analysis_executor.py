"""The analysis step under the real worker loop, over recorded Bedrock exchanges.

A research run's eight analysis modules are drafted by a model and decided by the
evidence gate. Everything is real except the network: the database, the lease and
heartbeat, the reservations, the ledger, the artifact store, the scope, the gateway and
its Bedrock adapter. ``ScriptedModels`` is an ``HttpTransport`` standing in for Bedrock
Converse: it answers each analysis turn with a draft built from the evidence the turn
itself sends (or with the recorded failure a test asks for), and each respondent block
as ``test_ai_fieldwork.py`` does.

The analysis nodes are added to the research graph here the way the workflow
integration will add them to the template (``analysis_step_definitions``, each
depending on ``aggregate`` alone); the template itself is not edited by this job.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from aia_core.application.analysis import ModuleOutcomeKind
from aia_core.application.analysis_results import (
    AGGREGATE_ARTIFACT,
    DATASET_ARTIFACT,
    SPECIFICATION_ARTIFACT,
    DatasetMaterial,
    SourcesRefused,
    reconstruct_run,
)
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.ai_contracts import Delivery, UsageOutcome
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    ANALYSIS_TURN_ARTIFACT,
    parse_module_artifact,
)
from aia_core.domain.analysis.steps import (
    ANALYSIS_STEP_KIND,
    analysis_node_key,
    analysis_step_definitions,
    analysis_step_inputs,
)
from aia_core.domain.deep_research.contracts import Channel, EvidenceOrigin, RetrievalMode
from aia_core.domain.deep_research.grounding import locate_quote, normalise_text
from aia_core.domain.deep_research.integration import (
    AnalysisModuleTarget,
    DeepResearchPurpose,
    InterpretationLineage,
    SociomapTarget,
)
from aia_core.domain.deep_research.quarantine import RecordedEvidenceRefused, require_live_evidence
from aia_core.domain.deep_research.workflow import deep_research_steps
from aia_core.domain.evidence import AdmittedClaim, ClaimSurface, ViolationCode
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.residency import DataClass
from aia_core.domain.sociomap import SociomapArtifactV3, read_artifact
from aia_core.domain.workflow import (
    RUNTIME_UNAVAILABLE_REASON,
    FailureClass,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.domain.workflow_templates import RESEARCH, steps_for_workflow
from aia_core.infrastructure.ai_usage_repository import AIUsageRepository
from aia_core.infrastructure.artifact_repository import ArtifactStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import BudgetReservationRow, StudyRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors import analysis, research
from aia_executors.ai_runtime import (
    AIRuntimeConfigError,
    AIRuntimeSettings,
    build_ai_fieldwork,
    build_gateway,
)
from aia_executors.analysis import (
    ANALYSIS_UNCONFIGURED,
    CONTEXT_WINDOW_EXCEEDED,
    AnalysisConfig,
    analysis_registry,
)
from aia_executors.deep_research import DeepResearchRuntime
from aia_executors.registry import registry_for
from aia_executors.report import REPORT_ARTIFACT_TYPE
from aia_executors.workbench import workbench_registry_for
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select

PROFILE = "eu.example.analysis-model-v1:0"  # a test id; the real one is configuration
ANALYSIS_TOOL = "aia_analysis_module"
QUESTIONS = ("Co lidé ráno pijí?", "Jak často pijí kávu?")
MODULES = [m.value for m in AnalysisModuleId]

DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "n": 200,
    "research_plan": {"research_questions": list(QUESTIONS)},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        }
    ],
}


def _env(world: Any, **overrides: str) -> dict[str, str]:
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
        # Today RESEARCH_REASONING is bound only with the design agents' switch; the
        # analysis switch and its binding are the activation work's (see the plan).
        "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
        "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
        "AIA_AI_RESEARCH_RESERVATION_USD": "2",
        "AIA_AI_FICTIONAL_CLIENT_IDS": world.client_id,
        "AIA_AI_MATERIAL_CLASSIFICATIONS": "["
        + ",".join(
            MaterialApproval(
                sha256=material_sha256(content),
                data_class=DataClass.CLASS_C_INTERNAL,
                provenance="generated wholly by this test",
            ).model_dump_json()
            for content in (
                DESIGN,
                {**DESIGN, "research_plan": {"research_questions": ["Proč lidé pijí čaj?"]}},
                {k: v for k, v in DESIGN.items() if k != "research_plan"},
                {**DESIGN, "n": 150},
            )
        )
        + "]",
    }
    env.update(overrides)
    return env


def _settings(world: Any, **overrides: str) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env(_env(world, **overrides))
    assert settings is not None
    return settings


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


# --------------------------------------------------------------------------- #
# the recorded model
# --------------------------------------------------------------------------- #


def _shown(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def grounded_draft(payload: Mapping[str, Any]) -> dict[str, Any]:
    """What a careful analyst returns: one cited number, written as the table gives it."""
    rows = payload["evidence"]
    row = next(
        (r for r in rows if ".pct." in r["evidence_ref"] or r["evidence_ref"].endswith(".mean")),
        rows[0],
    )
    shown = _shown(row["value"])
    return {
        "module": payload["module"],
        "summary": f"Podle fiktivních respondentů je odhad {shown}; jde o modelovaný údaj.",
        "research_question_answers": [
            {"question": q, "answer": f"Modelovaný odhad je {shown}.", "claim_ids": ["c1"]}
            for q in payload["research_questions"]
        ],
        "key_findings": [{"text": f"Modelovaný odhad: {shown}.", "claim_ids": ["c1"]}],
        "numeric_claims": [
            {
                "claim_id": "c1",
                "evidence_ref": row["evidence_ref"],
                "metric": row["metric"],
                "value": row["value"],
                "unit": row["unit"],
            }
        ],
    }


def invented_draft(payload: Mapping[str, Any]) -> dict[str, Any]:
    """A draft whose number is in no evidence row: the gate refuses it every time."""
    return {
        "module": payload["module"],
        "summary": "Kávu pije 55 % fiktivních respondentů.",
        "research_question_answers": [
            {"question": q, "answer": "Nelze doložit.", "claim_ids": []}
            for q in payload["research_questions"]
        ],
        "key_findings": [],
        "numeric_claims": [],
    }


def _respondent(schema: Mapping[str, Any]) -> dict[str, Any]:
    def resolve(node: Mapping[str, Any]) -> Mapping[str, Any]:
        ref = node.get("$ref")
        return schema["$defs"][ref.rsplit("/", 1)[-1]] if isinstance(ref, str) else node

    out: dict[str, Any] = {}
    for item_id, node in schema["properties"].items():
        props = resolve(node)["properties"]
        if "probabilities" in props:
            k = int(props["probabilities"]["minItems"])
            out[item_id] = {"probabilities": [0.6] + [0.4 / (k - 1)] * (k - 1)}
        elif "selected" in props:
            out[item_id] = {"selected": [1]}
        else:
            out[item_id] = {"text": "Fiktivní odpověď."}
    return out


@dataclass
class ScriptedModels:
    """An ``HttpTransport`` for Bedrock Converse. Records every request it is sent.

    Analysis requests are counted per module: ``(module, n)`` is that module's n-th call.
    A repair turn sends the evidence, the last draft and the repair, not the history, so
    which *turn* a call answered is the executor's to record (``CallRecord``), not this
    double's to infer.
    """

    #: modules whose every draft cites a number no evidence row holds
    invent: set[str] = field(default_factory=set)
    #: (module, n) whose draft cites a number no evidence row holds
    invent_calls: set[tuple[str, int]] = field(default_factory=set)
    #: (module, n) answered with a draft that breaks the output contract
    off_contract: set[tuple[str, int]] = field(default_factory=set)
    #: (module, n) -> a recorded failure: an HttpResponse or a TransportFailure
    failures: dict[tuple[str, int], HttpResponse | TransportFailure] = field(default_factory=dict)
    #: called with (module, n) before an analysis call is answered
    hook: Callable[[str, int], None] | None = None
    requests: list[HttpRequest] = field(default_factory=list)
    asked: list[tuple[str, int]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def calls(self, module: str) -> list[int]:
        return [n for m, n in self.asked if m == module]

    def messages(self, module: str, n: int) -> list[str]:
        """The texts of the messages a module's n-th call sent."""
        request = self.requests[self._index[(module, n)]]
        return [m["content"][0]["text"] for m in request.body["messages"]]

    def __post_init__(self) -> None:
        self._index: dict[tuple[str, int], int] = {}

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        tool = request.body["toolConfig"]["tools"][0]["toolSpec"]
        with self.lock:
            self.requests.append(request)
            number = len(self.requests)
            payload: dict[str, Any] = {}
            if tool["name"] == ANALYSIS_TOOL:
                payload = json.loads(request.body["messages"][0]["content"][0]["text"])
                key = (payload["module"], len(self.calls(payload["module"])) + 1)
                self.asked.append(key)
                self._index[key] = number - 1
        if tool["name"] == ANALYSIS_TOOL:
            if self.hook is not None:
                self.hook(*key)
            failure = self.failures.get(key)
            if isinstance(failure, TransportFailure):
                raise failure
            if isinstance(failure, HttpResponse):
                return failure
            if key in self.off_contract:
                answer: dict[str, Any] = {**grounded_draft(payload), "confidence": "high"}
            elif payload["module"] in self.invent or key in self.invent_calls:
                answer = invented_draft(payload)
            else:
                answer = grounded_draft(payload)
            usage = {"inputTokens": 2400, "outputTokens": 380, "totalTokens": 2780}
        else:
            answer = _respondent(tool["inputSchema"]["json"])
            usage = {"inputTokens": 900, "outputTokens": 120, "totalTokens": 1020}
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
                "usage": usage,
                "metrics": {"latencyMs": 900},
            },
        )


ANALYSIS_CALL_USD = (2400 * 3 + 380 * 15) / 1_000_000


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #


def _start(
    world: Any,
    design: dict[str, Any] = DESIGN,
    *,
    source: FieldworkSource = FieldworkSource.SYNTHETIC_FIXTURE,
    surface: ClaimSurface | None = ClaimSurface.INTERNAL,
) -> str:
    """A research run with the eight analysis nodes, as the integration will build it."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        designs = StudyDesignRepository(session, scope)
        revision, _ = designs.submit(content=design, source_stage="run")
        project_id = designs.project_id()
        assert project_id is not None
        run_id = WorkflowRepository(session, scope).create_run(
            project_id=project_id,
            project_revision=revision.revision,
            workflow_type=RESEARCH,
            steps=[
                *steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH),
                *analysis_step_definitions(),
            ],
            idempotency_key=f"{RESEARCH}:{revision.revision_id}:{uuid.uuid4().hex}",
            metadata={
                "design_revision_id": revision.revision_id,
                "design_revision": revision.revision,
                "fieldwork_source": source.value,
            },
            step_inputs={
                "compile": {"design_revision_id": revision.revision_id},
                "run": {"fieldwork_source": source.value},
                **(
                    analysis_step_inputs(surface)
                    if surface is not None
                    else {  # a step that does not say which surface it writes for
                        analysis_node_key(m): {"analysis_module": m.value} for m in AnalysisModuleId
                    }
                ),
            },
        )
        session.commit()
        return run_id


@pytest.fixture
def run_with(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: BuildIdentity
) -> Callable[..., Worker]:
    def make(
        transport: ScriptedModels | None,
        *,
        env: dict[str, str] | None = None,
        config: AnalysisConfig | None = None,
        ai_fieldwork: bool = False,
        deep_research: DeepResearchRuntime | None = None,
    ) -> Worker:
        settings = AIRuntimeSettings.from_env(env if env is not None else _env(world))
        assert settings is not None
        gateway = (
            build_gateway(settings, transport=transport, signer=Signer())
            if transport is not None
            else None
        )
        if gateway is not None and config is None:
            config = AnalysisConfig.from_settings(
                settings, max_output_tokens=4096, reservation_usd=1.0
            )
        upstream: dict[str, StepExecutor] = (
            registry_for(
                store=store,
                build=build,
                ai_runtime=build_ai_fieldwork(
                    settings, build=build, transport=transport, signer=Signer()
                ),
                deep_research=deep_research,
            )
            if ai_fieldwork
            else workbench_registry_for(store=store, build=build)
        )
        return Worker(
            session_factory=world.sessions,
            executors={
                **upstream,
                **analysis_registry(
                    store=store,
                    build=build,
                    gateway=gateway,
                    config=config if gateway is not None else None,
                ),
            },
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="analysis-worker",
                lease_seconds=30,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return make


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _unfinished(world: Any, run_id: str) -> list[tuple[str, str, Any]]:
    """Every step that did not succeed, with its last error: the message of a failed test."""
    return [
        (s["node_key"], s["status"].value, s["attempts"][-1]["error"] if s["attempts"] else None)
        for s in _run(world, run_id)["steps"]
        if s["status"] is not StepRunStatus.SUCCEEDED
    ]


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _analysis(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_node = {s["node_key"]: s for s in run["steps"]}
    return {m: by_node[analysis_node_key(AnalysisModuleId(m))] for m in MODULES}


def _reconstruct(world: Any, store: InMemoryArtifactStore, run_id: str) -> Any:
    with world.sessions() as session:
        return reconstruct_run(session, world.lead_scope(session), store, run_id=run_id)


def _record(world: Any, store: InMemoryArtifactStore, artifact_id: str) -> Any:
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        return parse_module_artifact(repo.read_json(artifact_id))


def _ledger(world: Any, run_id: str) -> list[Any]:
    with world.sessions() as session:
        return AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)


def _reservations(world: Any, run_id: str) -> list[BudgetReservationRow]:
    with world.sessions() as session:
        return list(
            session.scalars(
                select(BudgetReservationRow).where(BudgetReservationRow.run_id == run_id)
            ).all()
        )


# --------------------------------------------------------------------------- #
# the acceptance run
# --------------------------------------------------------------------------- #


def test_native_research_start_and_worker_complete_the_composed_analysis_graph(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """Exercise the application template, not a graph assembled by the test."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    run_id = started.run_id
    assert len(started.run["steps"]) == 14
    assert sum(step["kind"] == ANALYSIS_STEP_KIND for step in started.run["steps"]) == 8
    models = ScriptedModels()
    assert _drain(run_with(models)) == ["completed"] * 14, _unfinished(world, run_id)
    assert _reconstruct(world, store, run_id).complete
    report_step = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "report")
    assert report_step["status"] is StepRunStatus.SUCCEEDED
    report_id = report_step["output"]["artifact_id"]
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        report = repo.get(report_id)
        document = repo.read(report_id)
        dependencies = repo.dependencies(report_id)
    assert report.artifact_type == REPORT_ARTIFACT_TYPE
    assert report.metadata["review_state"] == "DRAFT_UNAPPROVED"
    assert report.metadata["synthetic"] is True
    assert report.is_approved is False
    assert len(dependencies) == 8
    assert {d.artifact_type for d in dependencies} == {ANALYSIS_MODULE_ARTIFACT}
    assert document.startswith(b"PK")
    assert lint_docx(document) == []


@pytest.mark.parametrize(
    ("n", "report_ready", "include_deep_research"),
    [
        pytest.param(60, False, False, id="insufficient-support"),
        pytest.param(150, True, False, id="internal-report"),
        pytest.param(150, True, True, id="deep-research-and-internal-report"),
    ],
)
def test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    n: int,
    report_ready: bool,
    include_deep_research: bool,
    deep_research_fixture: Any,
    record_property: Callable[[str, object], None],
) -> None:
    """The application-owned chain must connect AI answers, a real map and the report.

    The earlier AI fixture builds its graph directly and has no object battery;
    the application-owned report fixture uses deterministic fixture fieldwork.
    This exercises the connection with only the external transport replaced.
    Deep Research uses the same frozen design and worker; its review-only bundle
    stays sealed; interpretation executes over the resulting map and an admitted module.
    """
    design = {
        **DESIGN,
        "n": n,
        "sections": [
            *DESIGN["sections"],
            {
                "type": "object_battery",
                "title": "Service concepts",
                "object_type": "services",
                "objects": ["Service A", "Service B", "Service C"],
                "object_question": "How do you rate",
            },
        ],
    }
    if include_deep_research:
        design = {
            **deep_research_fixture.DESIGN_2,
            "n": n,
            "sections": [
                deep_research_fixture.DESIGN_2["sections"][0],
                {
                    **deep_research_fixture.DESIGN_2["sections"][1],
                    "object_family": "nápoje",
                    "scale": [1, 10],
                },
            ],
        }
    approval = MaterialApproval(
        sha256=material_sha256(design),
        data_class=DataClass.CLASS_C_INTERNAL,
        provenance="generated wholly by this test",
    )
    env = _env(world, AIA_AI_MATERIAL_CLASSIFICATIONS=f"[{approval.model_dump_json()}]")
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=design, source_stage="run"
        )
        session.commit()

    record_property("design_revision_id", revision.revision_id)
    record_property("design_content_sha256", revision.content_sha256)
    record_property("fixture_origin", "SYNTHETIC_AI_FICTIONAL_AND_RECORDED_WEB")
    models = ScriptedModels()
    agents = deep_research_fixture.RecordedAgents(deep_research_fixture.ANSWERS)
    deep_runtime = (
        deep_research_fixture.recorded(
            world, agents, approved_for=deep_research_fixture.DEVELOP_ROUTE, contents=(design,)
        )
        if include_deep_research
        else None
    )
    worker = run_with(models, env=env, ai_fieldwork=True, deep_research=deep_runtime)
    deep_run_id = None
    bundle_seal = None
    if include_deep_research:
        with world.sessions() as session:
            runs = DeepResearchRuns(session, world.lead_scope(session))
            deep_run_id = runs.start(
                design_revision_id=revision.revision_id,
                preset_name="QUICK",
                channels=(Channel.WEB,),
            ).run_id
            session.commit()
        assert _drain(worker) == ["completed"] * len(deep_research_steps())
        with world.sessions() as session:
            scope = world.lead_scope(session)
            runs = DeepResearchRuns(session, scope)
            deep_run = runs.get(deep_run_id)
            bundle = runs.bundle(deep_run_id, store=store)
            provenance = runs.provenance(deep_run_id, store=store)
            assert deep_run["status"] is WorkflowRunStatus.COMPLETED
            assert all(step["status"] is StepRunStatus.SUCCEEDED for step in deep_run["steps"])
            assert bundle.verify() and bundle.accepted and bundle.snapshots
            assert bundle.design_revision_id == revision.revision_id
            assert bundle.origins == (EvidenceOrigin.RECORDED_FIXTURE,)
            assert bundle.fictional_client and not bundle.client_facing
            assert provenance.purpose is DeepResearchPurpose.DESIGN_RESEARCH
            assert provenance.lineage.design_revision_id == revision.revision_id
            assert provenance.lineage.design_content_sha256 == revision.content_sha256
            bundle_seal = bundle.sha256
            assert provenance.evidence_bundle_seal == bundle_seal
            record_property("design_research_run_id", deep_run_id)
            record_property("design_research_bundle_id", provenance.evidence_bundle_artifact_id)
            record_property("design_research_bundle_seal", bundle_seal)
            for accepted in bundle.accepted:
                item = accepted.evidence
                snapshot = runs.snapshot(deep_run_id, item.source_ref, store=store)
                assert snapshot.retrieval_mode is RetrievalMode.RECORDED
                assert locate_quote(snapshot.text, normalise_text(item.quote)) == item.quote_span
                assert item.source_url in (snapshot.url, snapshot.final_url)
            designs = StudyDesignRepository(session, scope)
            assert designs.content(revision.revision_id) == design
            assert designs.latest() == revision
        assert agents.requests
        with pytest.raises(RecordedEvidenceRefused):
            require_live_evidence(bundle)

    with world.sessions() as session:
        scope = world.lead_scope(session)
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.AI_RUNTIME,
            analysis_enabled=True,
        )
        session.commit()

    record_property("research_run_id", started.run_id)
    endings = _drain(worker)
    back = _reconstruct(world, store, started.run_id)
    expected = ["completed"] * 13 + ["completed" if report_ready else "failed"]
    assert endings == expected, (
        _unfinished(world, started.run_id),
        {module.value: result.violations for module, result in back.modules.items()},
    )
    run = _run(world, started.run_id)
    steps = {step["node_key"]: step for step in run["steps"]}
    record_property("sociomap_artifact_id", steps["sociomap"]["output"]["artifact_id"])
    assert len(models.requests) >= design["n"]
    if not report_ready:
        assert run["status"] is WorkflowRunStatus.FAILED
        assert steps["sociomap"]["status"] is StepRunStatus.SUCCEEDED
        assert not back.complete
        assert models.asked == [], "unsupported evidence must be refused before analysis calls"
        assert all(result.outcome is ModuleOutcomeKind.BLOCKED for result in back.modules.values())
        assert all(
            any(v.code is ViolationCode.SUPPORT_SUPPRESSED for v in result.violations)
            for result in back.modules.values()
        )
        assert steps["report"]["attempts"][-1]["error"]["reason"] == "report_inputs_refused"
        with world.sessions() as session:
            stored = research_artifacts(session, world.lead_scope(session), store).recent(limit=100)
        assert REPORT_ARTIFACT_TYPE not in {artifact.artifact_type for artifact in stored}
        return

    assert run["status"] is WorkflowRunStatus.COMPLETED
    assert sorted(models.asked) == sorted((module, 1) for module in MODULES)
    assert back.complete
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        dataset = repo.read_json(steps["run"]["output"]["artifact_id"])
        mapped = repo.read_json(steps["sociomap"]["output"]["artifact_id"])["sociomap"]
        report_id = steps["report"]["output"]["artifact_id"]
        report = repo.get(report_id)
        document = repo.read(report_id)
        dependencies = repo.dependencies(report_id)

    assert dataset["dataset"]["origin"] == "SYNTHETIC_AI_FICTIONAL"
    assert len(dataset["dataset"]["respondents"]) == design["n"]
    assert mapped["methodology_status"] == "INTERNAL_ONLY"
    assert len(mapped["batteries"]) == 1
    battery = mapped["batteries"][0]
    assert len(battery["sociomap"]["layout"]["object_xy"]) == 3
    assert battery["sociomap"]["layout"]["respondent_ids"]
    assert battery["object_scores"]["primary"] == [obj["id"] for obj in battery["objects"]]
    pinned = run["metadata"]["sociomap_methods"]
    assert mapped["methods"] == [
        {"method_id": method["method_id"], "spec_fingerprint": method["spec_fingerprint"]}
        for method in pinned
    ]
    v2 = read_artifact(battery["maps"]["aia-sociomap-2"])
    assert isinstance(v2, SociomapArtifactV3)
    assert v2.support.respondents == n
    assert v2.spec.fingerprint() == next(
        method["spec_fingerprint"] for method in pinned if method["method_id"] == "aia-sociomap-2"
    )
    assert report.artifact_type == REPORT_ARTIFACT_TYPE
    assert report.metadata["run_id"] == started.run_id
    assert report.metadata["review_state"] == "DRAFT_UNAPPROVED"
    assert report.metadata["synthetic"] is True and report.is_approved is False
    assert {dep.artifact_id for dep in dependencies} == {
        steps[analysis_node_key(module)]["output"]["artifact_id"] for module in AnalysisModuleId
    }
    assert document.startswith(b"PK") and lint_docx(document) == []
    record_property("report_artifact_id", report_id)
    record_property("report_sha256", report.sha256)
    record_property("report_review_state", report.metadata["review_state"])

    if include_deep_research:
        assert deep_run_id is not None
        deep_calls = len(agents.requests)
        fieldwork_analysis_calls = len(models.requests)
        with world.sessions() as session:
            scope = world.lead_scope(session)
            runs = DeepResearchRuns(session, scope)
            assert runs.bundle(deep_run_id, store=store).sha256 == bundle_seal
            provenance = runs.provenance(deep_run_id, store=store)
            # The current internal report consumes analysis modules, not this review bundle.
            assert provenance.evidence_bundle_artifact_id not in {
                dep.artifact_id for dep in dependencies
            }
            target = SociomapTarget(
                kind="SOCIOMAP",
                research_run_id=started.run_id,
                sociomap_artifact_id=steps["sociomap"]["output"]["artifact_id"],
                battery_id=battery["battery_id"],
            )
            frozen = runs.freeze_interpretation(target=target, preset_name="QUICK", store=store)
            assert isinstance(frozen.lineage, InterpretationLineage)
            assert frozen.lineage.research_run_id == started.run_id
            assert frozen.lineage.design.design_revision_id == revision.revision_id
            repo = research_artifacts(session, scope, store)
            assert {
                pin.node_key: (pin.artifact_id, pin.sha256) for pin in frozen.lineage.artifacts
            } == {
                node: (
                    steps[node]["output"]["artifact_id"],
                    repo.get(steps[node]["output"]["artifact_id"]).sha256,
                )
                for node in ("compile", "run", "aggregate", "sociomap")
            }
            assert [run["run_id"] for run in runs.runs()] == [deep_run_id]
        interpretation_ids = []
        module_target = AnalysisModuleTarget(
            kind="ANALYSIS_MODULE",
            research_run_id=started.run_id,
            analysis_artifact_id=steps[analysis_node_key(AnalysisModuleId.OBJECTS)]["output"][
                "artifact_id"
            ],
            module_id=AnalysisModuleId.OBJECTS,
        )
        for result_target in (target, module_target):
            with world.sessions() as session:
                runs = DeepResearchRuns(session, world.lead_scope(session))
                frozen = runs.freeze_interpretation(
                    target=result_target, preset_name="QUICK", store=store, channels=(Channel.WEB,)
                )
                assert frozen.engine_request.subjects
                assert all(
                    subject.origin.startswith(f"interpretation:{result_target.kind}:")
                    for subject in frozen.engine_request.subjects
                )
                interpreted = runs.start_interpretation(
                    target=result_target, preset_name="QUICK", store=store, channels=(Channel.WEB,)
                )
                interpretation_ids.append(interpreted.run_id)
                session.commit()
            assert _drain(worker) == ["completed"] * len(deep_research_steps())
            with world.sessions() as session:
                runs = DeepResearchRuns(session, world.lead_scope(session))
                assert runs.get(interpreted.run_id)["status"] is WorkflowRunStatus.COMPLETED
                evidence = runs.bundle(interpreted.run_id, store=store)
                assert evidence.verify() and evidence.accepted
                provenance = runs.provenance(interpreted.run_id, store=store)
                assert provenance.purpose is DeepResearchPurpose.INTERPRETATION_RESEARCH
                assert provenance.target == result_target
                assert provenance.lineage == frozen.lineage
                assert runs.resolve_lineage(interpreted.run_id, store=store) == frozen.lineage
                record_property(f"interpretation_{result_target.kind}_run_id", interpreted.run_id)
                record_property(f"interpretation_{result_target.kind}_bundle_seal", evidence.sha256)
                record_property(
                    f"interpretation_{result_target.kind}_lineage", frozen.lineage.model_dump_json()
                )
        with world.sessions() as session:
            scope = world.lead_scope(session)
            runs = DeepResearchRuns(session, scope)
            assert {run["run_id"] for run in runs.runs()} == {deep_run_id, *interpretation_ids}
            assert runs.bundle(deep_run_id, store=store).sha256 == bundle_seal
            assert research_artifacts(session, scope, store).get(report_id).sha256 == report.sha256
        assert len(agents.requests) > deep_calls
        assert len(models.requests) == fieldwork_analysis_calls
        assert worker.run_once() is None


def test_report_step_finishes_with_a_reason_when_an_analysis_module_is_blocked(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    endings = _drain(run_with(ScriptedModels(invent={"objects"})))
    assert endings[-1] == "failed"
    run = _run(world, started.run_id)
    assert run["status"] is WorkflowRunStatus.FAILED
    report = next(s for s in run["steps"] if s["node_key"] == "report")
    assert report["status"] is StepRunStatus.FAILED
    assert report["attempts"][-1]["error"]["reason"] == "report_inputs_refused"


def test_cancellation_during_report_render_does_not_store_a_document(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    worker = run_with(ScriptedModels())
    assert [worker.run_once().ending for _ in range(13)] == ["completed"] * 13
    original_render = DocxRenderer.render

    def cancel_during_render(renderer: DocxRenderer, document: Any) -> bytes:
        data = original_render(renderer, document)
        with world.sessions() as session:
            WorkflowRepository(session, world.lead_scope(session)).request_cancel(started.run_id)
            session.commit()
        time.sleep(0.25)  # let the worker heartbeat carry the cancellation signal
        return data

    monkeypatch.setattr(DocxRenderer, "render", cancel_during_render)
    report_result = worker.run_once()
    assert report_result is not None and report_result.ending == "abandoned"
    assert _run(world, started.run_id)["status"] is WorkflowRunStatus.CANCELLED
    with world.sessions() as session:
        stored = research_artifacts(session, world.lead_scope(session), store).recent(limit=50)
    assert REPORT_ARTIFACT_TYPE not in {artifact.artifact_type for artifact in stored}


def test_a_completed_run_is_interpreted_module_by_module_and_reads_back_by_readmission(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    run_id = _start(world)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED

    # One call per module: every draft passed the gate on its first turn.
    assert sorted(models.asked) == sorted((m, 1) for m in MODULES)
    sent = "".join(r.raw_body.decode() for r in models.requests if r.raw_body)
    for secret in (world.study_id, world.client_id, world.organization_id):
        assert secret not in sent, "scope is never sent to a provider"
    assert all(
        r.url.endswith("/model/eu.example.analysis-model-v1%3A0/converse") for r in models.requests
    )
    assert "simulated" in models.requests[0].body["system"][0]["text"]

    steps = _analysis(run)
    for module, step in steps.items():
        output = step["output"]
        assert step["status"] is StepRunStatus.SUCCEEDED
        assert output["artifact_type"] == ANALYSIS_MODULE_ARTIFACT
        assert (output["analysis_module"], output["outcome"], output["surface"]) == (
            module,
            "COMPLETED",
            "INTERNAL",
        )
        assert (output["calls_sent"], output["calls_replayed"], output["reused"]) == (1, 0, False)
        assert output["cost_usd"] == pytest.approx(ANALYSIS_CALL_USD)
        assert output["method_status"].startswith("synthetic/modelled research")

    # The stored outcome: a draft, never a claim; its sources, turns and labels.
    record = _record(world, store, steps["executive"]["output"]["artifact_id"])
    assert record.outcome == "COMPLETED" and record.draft is not None
    assert "claims" not in record.model_dump(mode="json")
    assert record.labels.internal_only and record.labels.simulated_respondents
    assert record.evidence.data_origin.value == "SYNTHETIC_FIXTURE"
    assert record.harness.max_calls == 3 and record.harness.agent_id == "aia.analysis.module"
    (call,) = record.calls
    assert (call.turn, call.answer, call.replayed) == (1, "DRAFT", False)
    assert call.model == PROFILE and call.route_id == "bedrock-eu-primary"
    assert call.policy_version == "aia-model-policy-test-1"
    assert record.produced_by.run_id == run_id and record.produced_by.kind == ANALYSIS_STEP_KIND
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        depends = {
            a.artifact_type for a in repo.dependencies(steps["executive"]["output"]["artifact_id"])
        }
    assert depends == {
        SPECIFICATION_ARTIFACT,
        DATASET_ARTIFACT,
        AGGREGATE_ARTIFACT,
        ANALYSIS_TURN_ARTIFACT,
    }

    # Read back: the gate mints the claims now, from the run's own evidence.
    back = _reconstruct(world, store, run_id)
    assert back.complete and list(back.modules) == list(AnalysisModuleId)
    for module in back.modules.values():
        assert module.result is not None and module.result.claims
        assert all(isinstance(c, AdmittedClaim) for c in module.result.claims)
        assert module.result.surface is ClaimSurface.INTERNAL

    # Every call is on the ledger twice, Class C, attributed from the issued scope;
    # one reservation each, settled at the real cost, and the study charged that.
    events = _ledger(world, run_id)
    assert sorted(e.outcome.value for e in events) == sorted(["DISPATCHED", "SUCCEEDED"] * 8)
    for e in events:
        assert (e.organization_id, e.client_id, e.study_id) == (
            world.organization_id,
            world.client_id,
            world.study_id,
        )
        assert e.data_class.value == "CLASS_C_INTERNAL" and e.agent_id == "aia.analysis.module"
        assert e.capability.value == "RESEARCH_REASONING"
    spent = sum(e.cost_usd for e in events if e.outcome is UsageOutcome.SUCCEEDED)
    assert spent == pytest.approx(8 * ANALYSIS_CALL_USD)
    reservations = _reservations(world, run_id)
    assert len(reservations) == 8 and {r.status for r in reservations} == {"SETTLED"}
    with world.sessions() as session:
        study = session.scalar(select(StudyRow).where(StudyRow.study_id == world.study_id))
    assert study is not None and study.spent_usd == pytest.approx(spent)


# --------------------------------------------------------------------------- #
# reuse: complete inputs only, and whatever the research steps reused
# --------------------------------------------------------------------------- #


def test_changed_research_questions_run_every_module_again_over_the_reused_aggregate(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """Only the research questions change: the questionnaire compiles to the same
    specification, so fieldwork and the aggregate are reused -- and every module, whose
    fingerprint holds the questions, is asked again."""
    models = ScriptedModels()
    first = _start(world)
    _drain(run_with(models))
    edited = {**DESIGN, "research_plan": {"research_questions": ["Proč lidé pijí čaj?"]}}
    second = _start(world, edited)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, second)
    one, two = _run(world, first), _run(world, second)
    steps_one = {s["node_key"]: s for s in one["steps"]}
    steps_two = {s["node_key"]: s for s in two["steps"]}
    assert (
        steps_two["compile"]["output"]["artifact_id"]
        != steps_one["compile"]["output"]["artifact_id"]
    )
    for node in ("run", "aggregate"):
        assert steps_two[node]["output"]["reused"] is True
        assert steps_two[node]["output"]["artifact_id"] == steps_one[node]["output"]["artifact_id"]
    assert len(models.asked) == 16, "every module asked again"
    back = _reconstruct(world, store, second)
    assert back.complete
    assert {m.record.research_questions for m in back.modules.values()} == {
        ("Proč lidé pijí čaj?",)
    }


def test_a_second_run_over_the_same_evidence_reuses_every_outcome_and_sends_nothing(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    first = _start(world)
    _drain(run_with(models))
    second = _start(world)  # the same Design Revision: every upstream artifact is reused
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, second)
    assert len(models.asked) == 8, "nothing is asked twice"
    one, two = _analysis(_run(world, first)), _analysis(_run(world, second))
    for module in MODULES:
        assert two[module]["output"]["reused"] is True
        assert two[module]["output"]["artifact_id"] == one[module]["output"]["artifact_id"]
    assert _ledger(world, second) == [] and _reservations(world, second) == []
    assert _reconstruct(world, store, second).complete


def test_a_design_edited_and_edited_back_reuses_its_outcomes_and_reads_them_back(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """The compile step reuses the first revision's specification for the third, which
    has the same content; the outcomes computed over it are the third run's too."""
    models = ScriptedModels()
    first = _start(world)
    _drain(run_with(models))
    with world.sessions() as session:
        StudyDesignRepository(session, world.lead_scope(session)).submit(
            content={**DESIGN, "title": "Mezitím jiný název"}, source_stage="run"
        )
        session.commit()
    again = _start(world)  # DESIGN once more: a third revision with the first's content
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, again)
    assert len(models.asked) == 8
    revisions = {_run(world, r)["metadata"]["design_revision_id"] for r in (first, again)}
    assert len(revisions) == 2
    assert _reconstruct(world, store, again).complete


# --------------------------------------------------------------------------- #
# the gate decides: blocked is an outcome, stored, and strands no other module
# --------------------------------------------------------------------------- #


def test_a_module_whose_drafts_cite_nothing_is_blocked_after_three_calls_and_strands_no_other(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels(invent={"objects"})
    run_id = _start(world)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    assert _run(world, run_id)["status"] is WorkflowRunStatus.COMPLETED
    assert models.calls("objects") == [1, 2, 3], "the first turn and two repairs, never more"
    assert all(models.calls(m) == [1] for m in MODULES if m != "objects")
    _payload, previous, repair = models.messages("objects", 3)
    assert "55 %" in previous, "a repair turn shows the model its last draft"
    assert "evidence gate" in repair and "UNCITED_NUMBER" in repair

    output = _analysis(_run(world, run_id))["objects"]["output"]
    assert (output["outcome"], output["calls_sent"]) == ("BLOCKED", 3)
    record = _record(world, store, output["artifact_id"])
    assert record.draft is None and record.attempts == 3
    assert {v.code for v in record.violations} == {ViolationCode.UNCITED_NUMBER}
    assert [c.answer for c in record.calls] == ["DRAFT"] * 3

    back = _reconstruct(world, store, run_id)
    assert not back.complete
    blocked = back.modules[AnalysisModuleId.OBJECTS]
    assert blocked.outcome is ModuleOutcomeKind.BLOCKED and blocked.result is None
    assert [m.outcome for m in back.modules.values()].count(ModuleOutcomeKind.COMPLETED) == 7
    # Every call was paid for and is on the ledger, the refused drafts' too.
    answered = [e for e in _ledger(world, run_id) if e.outcome is UsageOutcome.SUCCEEDED]
    assert len(answered) == 10


def test_an_answer_off_the_output_contract_is_one_counted_turn_that_the_next_repairs(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels(off_contract={("executive", 1)})
    run_id = _start(world)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    assert models.calls("executive") == [1, 2], "no schema repair hidden inside the turn"
    _payload, previous, repair = models.messages("executive", 2)
    assert previous.startswith("(no draft")
    assert "output schema check of the previous answer reported" in repair

    output = _analysis(_run(world, run_id))["executive"]["output"]
    assert (output["outcome"], output["calls_sent"]) == ("COMPLETED", 2)
    record = _record(world, store, output["artifact_id"])
    assert [c.answer for c in record.calls] == ["SCHEMA_INVALID", "DRAFT"]
    assert record.calls[0].cost_usd == pytest.approx(ANALYSIS_CALL_USD), "the refused answer cost"
    terminal = [e for e in _ledger(world, run_id) if e.outcome.is_terminal]
    assert len(terminal) == 9 and {e.purpose.value for e in terminal} == {"PRIMARY"}


def test_the_research_questions_module_without_a_question_is_blocked_while_the_rest_run(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    run_id = _start(world, {k: v for k, v in DESIGN.items() if k != "research_plan"})
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    output = _analysis(_run(world, run_id))["research_questions"]["output"]
    assert (output["outcome"], output["calls_sent"]) == ("BLOCKED", 0)
    assert len(models.asked) == 7 and "research_questions" not in dict(models.asked)
    record = _record(world, store, output["artifact_id"])
    assert [v.code for v in record.violations] == [ViolationCode.RESEARCH_QUESTION_UNANSWERED]


# --------------------------------------------------------------------------- #
# refused before anything is reserved or sent
# --------------------------------------------------------------------------- #


def test_client_facing_modules_are_blocked_before_any_call_configured_or_not(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world, surface=ClaimSurface.CLIENT_FACING)
    assert _drain(run_with(None)) == ["completed"] * 13, _unfinished(world, run_id)
    for step in _analysis(_run(world, run_id)).values():
        output = step["output"]
        assert (output["outcome"], output["calls_sent"], output["surface"]) == (
            "BLOCKED",
            0,
            "CLIENT_FACING",
        )
        record = _record(world, store, output["artifact_id"])
        assert record.attempts == 0 and record.calls == ()
        assert {v.code for v in record.violations} >= {
            ViolationCode.FIELD_INTERNAL_ONLY,
            ViolationCode.SYNTHETIC_DATA_ORIGIN,
            ViolationCode.JOINT_CERTIFICATE_DEGRADED,
        }
    assert _ledger(world, run_id) == [] and _reservations(world, run_id) == []
    assert not _reconstruct(world, store, run_id).complete


def test_unconfigured_analysis_parks_every_module_and_sends_nothing(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world)
    endings = _drain(run_with(None))
    assert sorted(endings) == sorted(["completed"] * 5 + ["failed"] * 8)
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    for step in _analysis(run).values():
        assert step["status"] is StepRunStatus.WAITING_PROVIDER
        assert step["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
        assert step["attempts"][-1]["error"]["reason"] == ANALYSIS_UNCONFIGURED
    assert _ledger(world, run_id) == [] and _reservations(world, run_id) == []


def test_a_real_clients_design_is_class_a_and_parks_before_any_reservation(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    """A content-bound Class A declaration cannot use the Class C route."""
    models = ScriptedModels()
    run_id = _start(world)
    _drain(
        run_with(
            models,
            env=_env(
                world,
                AIA_AI_MATERIAL_CLASSIFICATIONS="["
                + MaterialApproval(
                    sha256=material_sha256(DESIGN),
                    data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
                    provenance="test material explicitly classified as confidential",
                ).model_dump_json()
                + "]",
            ),
        )
    )
    assert models.requests == [], "nothing may reach the adapter"
    for step in _analysis(_run(world, run_id)).values():
        assert step["status"] is StepRunStatus.WAITING_PROVIDER
        error = step["attempts"][-1]["error"]
        assert error["reason"] == "egress_route_not_approved_for_class"
        assert error["data_class"] == "CLASS_A_CLIENT_CONFIDENTIAL"
    assert _ledger(world, run_id) == [] and _reservations(world, run_id) == []


def test_a_dataset_that_recorded_no_lineage_is_refused_by_the_licence_gate(
    world: Any, run_with: Callable[..., Worker], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analysis,
        "dataset_material",
        lambda *a, **k: DatasetMaterial(lineage=None, respondents_fictional=True),
    )
    models = ScriptedModels()
    run_id = _start(world)
    _drain(run_with(models))
    assert models.requests == []
    for step in _analysis(_run(world, run_id)).values():
        assert step["status"] is StepRunStatus.WAITING_PROVIDER
        assert step["attempts"][-1]["error"]["reason"] == "licence_lineage_undeclared"
        assert step["attempts"][-1]["error"]["lineage"] is None


def test_a_study_without_budget_parks_awaiting_budget_before_any_call(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    run_id = _start(world)
    config = AnalysisConfig.from_settings(
        _settings(world), max_output_tokens=4096, reservation_usd=30.0
    )  # the study's budget is 25
    _drain(run_with(models, config=config))
    assert models.requests == []
    for step in _analysis(_run(world, run_id)).values():
        assert step["status"] is StepRunStatus.AWAITING_BUDGET


def test_a_turn_the_model_window_cannot_hold_fails_before_any_reservation(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    run_id = _start(world)
    small = AnalysisConfig(
        policy_version="aia-model-policy-test-1",
        max_output_tokens=4096,
        context_window_tokens=30_000,
        reservation_usd=1.0,
        fictional_client_ids=frozenset({world.client_id}),
        material_approvals=_settings(world).material_approvals,
    )
    _drain(run_with(models, config=small))
    assert models.requests == [] and _reservations(world, run_id) == []
    failed = [s for s in _analysis(_run(world, run_id)).values() if s["attempts"]]
    assert failed and all(s["status"] is StepRunStatus.FAILED for s in failed)
    assert failed[0]["attempts"][-1]["error"]["reason"] == CONTEXT_WINDOW_EXCEEDED


# --------------------------------------------------------------------------- #
# provider failures belong to the worker, and a retry never pays twice
# --------------------------------------------------------------------------- #


def _error(status: int, error_type: str, **headers: str) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={"x-amzn-requestid": "req-err", "x-amzn-errortype": error_type, **headers},
        body={"message": error_type},
    )


def test_throttling_parks_the_module_for_quota_and_charges_nothing(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels(
        failures={("executive", 1): _error(429, "ThrottlingException", **{"retry-after": "60"})}
    )
    run_id = _start(world)
    _drain(run_with(models))
    steps = _analysis(_run(world, run_id))
    executive = steps["executive"]
    assert executive["status"] is StepRunStatus.WAITING_PROVIDER
    assert executive["attempts"][-1]["failure_class"] is FailureClass.QUOTA
    assert executive["output"] in (None, {}), "a provider failure is not an outcome"
    assert models.calls("executive") == [1], "no in-call retry, no second provider"
    assert all(steps[m]["status"] is StepRunStatus.SUCCEEDED for m in MODULES if m != "executive")
    outcomes = [e.outcome for e in _ledger(world, run_id) if e.step_id == executive["step_id"]]
    assert outcomes == [UsageOutcome.DISPATCHED, UsageOutcome.FAILED]


def test_an_uncertain_turn_waits_for_a_person_and_recovery_replays_what_was_answered(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels(
        invent_calls={("executive", 1)},
        failures={("executive", 2): TransportFailure("read timeout", delivery=Delivery.UNKNOWN)},
    )
    run_id = _start(world)
    worker = run_with(models)
    _drain(worker)
    step = _analysis(_run(world, run_id))["executive"]
    assert step["status"] is StepRunStatus.RECOVERY_REQUIRED
    assert models.calls("executive") == [1, 2], "the uncertain call is not sent again"
    assert all(models.calls(m) == [1] for m in MODULES if m != "executive")
    outcomes = [e.outcome for e in _ledger(world, run_id) if e.step_id == step["step_id"]]
    assert outcomes == [
        UsageOutcome.DISPATCHED,
        UsageOutcome.SUCCEEDED,
        UsageOutcome.DISPATCHED,
        UsageOutcome.UNCERTAIN,
    ]
    assert [r.status for r in _reservations(world, run_id)].count("SETTLED_UNCERTAIN") == 1

    # A person reconciled the call with the provider and resumes the module: the turn
    # it answered is replayed from its checkpoint, and only the lost one is sent.
    with world.sessions() as session:
        WorkflowRepository(session, world.lead_scope(session)).force_step_status(
            step["step_id"], StepRunStatus.RUNNABLE, reason="reconciled: the call was not billed"
        )
        session.commit()
    assert _drain(worker) == ["completed"]
    assert models.calls("executive") == [1, 2, 3], "one more call: the lost turn, not both"
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    output = _analysis(run)["executive"]["output"]
    assert (output["outcome"], output["calls_sent"], output["calls_replayed"]) == (
        "COMPLETED",
        1,
        1,
    )
    record = _record(world, store, output["artifact_id"])
    assert [(c.turn, c.replayed) for c in record.calls] == [(1, True), (2, False)]
    assert _reconstruct(world, store, run_id).complete


def test_cancellation_between_turns_keeps_the_answered_turn_and_sends_no_other(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    run_id = _start(world)
    models = ScriptedModels(invent_calls={(m, 1) for m in MODULES})

    def cancel(module: str, n: int) -> None:
        if len(models.asked) == 1:
            with world.sessions() as session:
                WorkflowRepository(session, world.lead_scope(session)).request_cancel(run_id)
                session.commit()
            time.sleep(0.5)  # the heartbeat carries the cancellation back

    models.hook = cancel
    _drain(run_with(models))
    assert _run(world, run_id)["status"] is WorkflowRunStatus.CANCELLED
    assert len(models.asked) == 1, "no repair turn is sent once the run is cancelled"
    assert [e.outcome for e in _ledger(world, run_id)] == [
        UsageOutcome.DISPATCHED,
        UsageOutcome.SUCCEEDED,
    ]
    with world.sessions() as session:
        stored = research_artifacts(session, world.lead_scope(session), store).recent(limit=50)
    kinds = [a.artifact_type for a in stored]
    assert kinds.count(ANALYSIS_TURN_ARTIFACT) == 1, "the answered turn is kept"
    assert ANALYSIS_MODULE_ARTIFACT not in kinds


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #


def test_the_configuration_refuses_what_would_fail_at_run_time(
    world: Any, store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    settings = _settings(world)
    # One call at the ceilings: 200 000 input tokens at $3/Mtok + 4 096 output at $15/Mtok.
    assert AnalysisConfig.from_settings(
        settings, max_output_tokens=4096, reservation_usd=0.67
    ).fictional_client_ids == frozenset({world.client_id})
    with pytest.raises(AIRuntimeConfigError, match="exceeds the model limit"):
        AnalysisConfig.from_settings(settings, max_output_tokens=9000, reservation_usd=5.0)
    with pytest.raises(AIRuntimeConfigError, match="one call at the model ceilings"):
        AnalysisConfig.from_settings(settings, max_output_tokens=4096, reservation_usd=0.66)
    unbound = _settings(world, AIA_AI_RESEARCH_AGENTS_ENABLED="false")
    with pytest.raises(AIRuntimeConfigError, match="does not bind"):
        AnalysisConfig.from_settings(unbound, max_output_tokens=4096, reservation_usd=1.0)
    with pytest.raises(ValueError, match="names its model policy"):
        AnalysisConfig(
            policy_version="",
            max_output_tokens=1,
            context_window_tokens=1,
            reservation_usd=1.0,
            fictional_client_ids=frozenset(),
        )
    gateway = build_gateway(settings, transport=ScriptedModels(), signer=Signer())
    with pytest.raises(ValueError, match="come together"):
        analysis_registry(store=store, build=build, gateway=gateway)


def test_the_research_steps_store_the_artifact_types_the_analysis_reads() -> None:
    """The application layer names them without importing an app; they must not drift."""
    assert (SPECIFICATION_ARTIFACT, DATASET_ARTIFACT, AGGREGATE_ARTIFACT) == (
        research.SPECIFICATION,
        research.FIELDWORK_DATASET,
        research.AGGREGATE,
    )


# --------------------------------------------------------------------------- #
# the whole chain: AI respondents, then their interpretation
# --------------------------------------------------------------------------- #


def test_ai_respondents_answer_and_the_eight_modules_interpret_them_in_one_run(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """One gateway, one route, Class C throughout: 150 fictional AI respondents answer,
    the aggregate is computed from their answers, and the modules interpret it."""
    models = ScriptedModels()
    run_id = _start(world, {**DESIGN, "n": 150}, source=FieldworkSource.AI_RUNTIME)
    assert _drain(run_with(models, ai_fieldwork=True)) == ["completed"] * 13, _unfinished(
        world, run_id
    )
    assert len(models.requests) == 150 + 8
    assert sorted(models.asked) == sorted((m, 1) for m in MODULES)
    back = _reconstruct(world, store, run_id)
    assert back.complete
    record = back.modules[AnalysisModuleId.EXECUTIVE].record
    assert record.evidence.data_origin.value == "SYNTHETIC_AI_FICTIONAL"
    assert record.labels.simulated_respondents and record.labels.internal_only
    events = [e for e in _ledger(world, run_id) if e.agent_id == "aia.analysis.module"]
    assert len(events) == 16
    assert {e.data_class.value for e in events} == {"CLASS_C_INTERNAL"}


@pytest.mark.parametrize("how", ["tampered", "missing"])
def test_a_corrupt_ai_dataset_fails_the_module_and_stays_marked_corrupt(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker], how: str
) -> None:
    """A module reads the AI runtime's dataset for its lineage. Bytes that fail their hash,
    or an object that is gone, fail it by reason before any call, and the CORRUPT mark the
    read made is committed with the failure (OI-77): read from a session of its own, the
    dataset is CORRUPT, so no later step or run reuses it."""
    models = ScriptedModels()
    run_id = _start(world, {**DESIGN, "n": 150}, source=FieldworkSource.AI_RUNTIME)
    worker = run_with(models, ai_fieldwork=True)
    research = {"compile", "preflight", "run", "aggregate", "sociomap"}
    while not research <= {
        s["node_key"]
        for s in _run(world, run_id)["steps"]
        if s["status"] is StepRunStatus.SUCCEEDED
    }:
        assert worker.run_once() is not None, _unfinished(world, run_id)
    assert not any(s["attempts"] for s in _analysis(_run(world, run_id)).values())
    dataset_id = next(
        s["output"]["artifact_id"] for s in _run(world, run_id)["steps"] if s["node_key"] == "run"
    )
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        key = repo.get(dataset_id).storage_key
    if how == "tampered":
        store.put(key, b'{"kind": "tampered"}')
    else:
        store.delete(key)
    sent = len(models.requests)

    _drain(worker)
    assert len(models.requests) == sent
    failed = [s for s in _analysis(_run(world, run_id)).values() if s["attempts"]]
    assert failed
    attempt = failed[0]["attempts"][-1]
    assert attempt["failure_class"] is FailureClass.SCHEMA_VIOLATION
    assert attempt["error"]["reason"] == "source_corrupt"
    assert key not in json.dumps(attempt, default=str)
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        assert repo.get(dataset_id).status is ArtifactStatus.CORRUPT


def test_a_checkpoint_whose_bytes_changed_is_never_replayed_and_the_turn_is_asked_again(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels(
        invent_calls={("executive", 1), ("executive", 3)},
        failures={("executive", 2): TransportFailure("read timeout", delivery=Delivery.UNKNOWN)},
    )
    run_id = _start(world)
    worker = run_with(models)
    _drain(worker)
    step = _analysis(_run(world, run_id))["executive"]
    assert step["status"] is StepRunStatus.RECOVERY_REQUIRED
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        (checkpoint,) = [
            a
            for a in repo.recent(limit=50)
            if a.artifact_type == ANALYSIS_TURN_ARTIFACT
            and a.metadata.get("analysis_module") == "executive"
        ]
    tampered = json.loads(store.get(checkpoint.storage_key))
    tampered["draft"]["summary"] = "Kávu pije 99 % fiktivních respondentů."
    store.put(checkpoint.storage_key, json.dumps(tampered).encode("utf-8"))

    with world.sessions() as session:
        WorkflowRepository(session, world.lead_scope(session)).force_step_status(
            step["step_id"], StepRunStatus.RUNNABLE, reason="reconciled: the call was not billed"
        )
        session.commit()
    assert _drain(worker) == ["completed"]
    # The altered answer was refused by its hash and asked again (call 3, refused by the
    # gate again), then the repair turn was sent (call 4).
    assert models.calls("executive") == [1, 2, 3, 4]
    output = _analysis(_run(world, run_id))["executive"]["output"]
    record = _record(world, store, output["artifact_id"])
    assert [(c.turn, c.replayed) for c in record.calls] == [(1, False), (2, False)]
    assert "99 %" not in json.dumps(record.model_dump(mode="json"), ensure_ascii=False)


def test_a_step_that_does_not_name_its_surface_fails_and_nothing_is_guessed(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    models = ScriptedModels()
    run_id = _start(world, surface=None)
    _drain(run_with(models))
    assert models.requests == []
    failed = [s for s in _analysis(_run(world, run_id)).values() if s["attempts"]]
    assert failed and all(s["status"] is StepRunStatus.FAILED for s in failed)
    error = failed[0]["attempts"][-1]
    assert error["failure_class"] is FailureClass.MISSING_CONFIGURATION
    assert error["error"]["reason"] == "analysis_step_unnamed"


def test_sources_that_do_not_describe_one_computation_fail_the_step_before_any_call(
    world: Any, run_with: Callable[..., Worker], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*_: Any, **__: Any) -> Any:
        raise SourcesRefused("aggregate_lineage", "the aggregate records another dataset")

    monkeypatch.setattr(analysis, "native_sources", refused)
    models = ScriptedModels()
    run_id = _start(world)
    _drain(run_with(models))
    assert models.requests == []
    failed = [s for s in _analysis(_run(world, run_id)).values() if s["attempts"]]
    error = failed[0]["attempts"][-1]
    assert error["failure_class"] is FailureClass.SCHEMA_VIOLATION
    assert error["error"]["reason"] == "aggregate_lineage"
