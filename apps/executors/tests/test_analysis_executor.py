"""The analysis step under the real worker loop, over recorded Bedrock exchanges.

A research run's eight analysis modules are drafted by a model and decided by the
evidence gate. Everything is real except the network: the database, the lease and
heartbeat, the reservations, the ledger, the artifact store, the scope, the gateway and
its Bedrock adapter. ``RecordedModels`` (``aia_executors.recorded_models``) is an ``HttpTransport``
standing in for Bedrock Converse: it answers each analysis turn with a draft built from the
evidence the turn itself sends (or with the recorded failure a test asks for), and each
respondent block as ``test_ai_fieldwork.py`` does.

The analysis nodes are added to the research graph here the way the workflow
integration will add them to the template (``analysis_step_definitions``, each
depending on ``aggregate`` alone); the template itself is not edited by this job.
"""

from __future__ import annotations

import hashlib
import io
import json
import time
import uuid
import zipfile
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from aia_core.application.analysis import ModuleOutcomeKind
from aia_core.application.analysis_results import (
    AGGREGATE_ARTIFACT,
    DATASET_ARTIFACT,
    SPECIFICATION_ARTIFACT,
    AnalysisNotRetryable,
    DatasetMaterial,
    ReconstructionRefused,
    SourcesRefused,
    native_sources,
    reconstruct_run,
    retry_failed_modules,
    stored_analysis,
)
from aia_core.application.contextual_report import contextual_report, stored_contextual_report
from aia_core.application.deep_research import DeepResearchRuns, run_settings
from aia_core.application.report import ReportCompositionRefused
from aia_core.application.report_variants import prepared_context_report
from aia_core.application.research import FrozenDataset, ResearchRuns, research_artifacts
from aia_core.domain.ai_contracts import Delivery, UsageOutcome
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    ANALYSIS_TURN_ARTIFACT,
    finding_diagnostic,
    no_supported_finding,
    parse_module_artifact,
)
from aia_core.domain.analysis.external import external_context_lines, public_context
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
from aia_core.domain.deep_research.quarantine import (
    RecordedEvidenceRefused,
    analysis_context,
    require_live_evidence,
)
from aia_core.domain.deep_research.workflow import deep_research_steps
from aia_core.domain.evidence import AdmittedClaim, ClaimSurface, ViolationCode
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.report.document_model import DOCUMENT_MODEL_CONTRACT, read_document_payload
from aia_core.domain.report.model import Callout
from aia_core.domain.report.review import REVIEW_STAMP_CONTRACT, ReviewMark, ReviewState
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
    HttpResponse,
    TransportFailure,
)
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.report_docx.review_stamp import stamp_review
from aia_core.infrastructure.report_pdf import PdfConversionFailed, PdfConverter
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
from aia_executors.recorded_models import PROFILE, RecordedModels, RecordedSigner, runtime_env
from aia_executors.registry import registry_for
from aia_executors.report import (
    REPORT_ARTIFACT_TYPE,
    REPORT_DOCUMENT_ARTIFACT_TYPE,
    report_registry,
)
from aia_executors.workbench import workbench_registry_for
from aia_worker.executor import ShutdownRequested, StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select

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
    return runtime_env(
        world.client_id,
        (
            DESIGN,
            {**DESIGN, "research_plan": {"research_questions": ["Proč lidé pijí čaj?"]}},
            {k: v for k, v in DESIGN.items() if k != "research_plan"},
            {**DESIGN, "n": 150},
            {**DESIGN, "n": 50},
        ),
        **overrides,
    )


def _settings(world: Any, **overrides: str) -> AIRuntimeSettings:
    settings = AIRuntimeSettings.from_env(_env(world, **overrides))
    assert settings is not None
    return settings


#: One analysis call as RecordedModels reports it, at the test prices of ``runtime_env``.
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
        revision, _ = designs.submit_as_working_copy(content=design, source_stage="run")
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
        transport: RecordedModels | None,
        *,
        env: dict[str, str] | None = None,
        config: AnalysisConfig | None = None,
        ai_fieldwork: bool = False,
        deep_research: DeepResearchRuntime | None = None,
        pdf: PdfConverter | None = None,
    ) -> Worker:
        settings = AIRuntimeSettings.from_env(env if env is not None else _env(world))
        assert settings is not None
        gateway = (
            build_gateway(settings, transport=transport, signer=RecordedSigner())
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
                    settings, build=build, transport=transport, signer=RecordedSigner()
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
                **(report_registry(store=store, build=build, pdf=pdf) if pdf is not None else {}),
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


def _payload(world: Any, store: InMemoryArtifactStore, artifact_id: str) -> Any:
    with world.sessions() as session:
        return research_artifacts(session, world.lead_scope(session), store).read_json(artifact_id)


def _ledger(world: Any, run_id: str) -> list[Any]:
    with world.sessions() as session:
        return AIUsageRepository(session, world.lead_scope(session)).events(run_id=run_id)


def _states_its_approval_in_its_footers_alone(data: bytes, artifact_id: str, sha256: str) -> None:
    """The stored version ``data``, once approved: its export says SCHVÁLENO in every footer and
    states no status anywhere else. The stamp reads only the renderer's own status marks (a
    study's words may say "neschválení"), so a composer's own words are held here, where the
    stored report is rendered (D2; the literature chapter once called itself part of an
    unapproved draft under a SCHVÁLENO footer, cross-review)."""
    approved = stamp_review(
        data, ReviewMark(ReviewState.APPROVED, artifact_id, sha256, date(2026, 10, 18))
    )
    with zipfile.ZipFile(io.BytesIO(approved)) as package:
        for part in package.namelist():
            words = package.read(part).decode(errors="ignore")
            if part.startswith("word/footer"):
                assert "SCHVÁLENO" in words and "KONCEPT" not in words, part
            elif part.endswith(".xml"):
                assert "neschválen" not in words.casefold(), part
                assert "KONCEPT" not in words, part


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
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
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
    models = RecordedModels()
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
    assert report.metadata["data_origin"] == "SYNTHETIC_FIXTURE"
    assert report.is_approved is False
    assert len(dependencies) == 9
    assert {d.artifact_type for d in dependencies} == {
        ANALYSIS_MODULE_ARTIFACT,
        "research_sociomap",
    }
    assert document.startswith(b"PK")
    assert lint_docx(document) == []
    # Every question's numbers are in the report, after the methodology (complete-study-report B1a).
    body = zipfile.ZipFile(io.BytesIO(document)).read("word/document.xml").decode()
    assert "Výsledky jednotlivých otázek" in body
    assert body.index("Metodika a způsob interpretace") < body.index("Výsledky jednotlivých otázek")
    # The design it ran, and its questionnaire as an appendix (B1b).
    assert body.index("Návrh studie") < body.index("Metodika a způsob interpretace")
    assert body.index("Výsledky jednotlivých otázek") < body.rindex("Dotazník")
    # Who answered, and how the run computed, before the numbers (B1c).
    assert (
        body.index("Metodika a způsob interpretace")
        < body.index("Respondenti a výpočet")
        < body.index("Výsledky jednotlivých otázek")
    )
    assert "smyšlení respondenti" in body
    assert report.metadata["report_contract"] == "aia-internal-report-13"
    # The methodology chapter states the rules the run pinned (artifact-chain CHN9).
    assert "Pravidlo podpory aia-support-1" in body and "Agregace: metodika" in body
    # The document the DOCX was rendered from, beside it (report-delivery RD5a).
    stored = report_step["output"]["document"]
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        model = repo.get(stored["artifact_id"])
        payload = read_document_payload(repo.read(stored["artifact_id"]))
        model_dependencies = repo.dependencies(stored["artifact_id"])
    assert model.artifact_type == REPORT_DOCUMENT_ARTIFACT_TYPE
    assert model.sha256 == stored["sha256"]
    assert model.input_fingerprint == report.input_fingerprint
    assert model.metadata["docx_artifact_id"] == report_id
    assert model.metadata["docx_sha256"] == report.sha256
    assert [d.artifact_id for d in model_dependencies] == [report_id]
    section_ids = [section["id"] for section in payload["sections"]]
    assert (
        section_ids[0] == "intro" and "methodology" in section_ids and "ch-questions" in section_ids
    )
    assert section_ids[-1] == "app-audit"
    titles = [section["title"] for section in payload["sections"]]
    assert "Výsledky jednotlivých otázek" in titles
    cited = {ref for s in payload["sections"] for ref in s["refs"]}
    assert cited and cited == set(payload["ledger"]["refs"])
    # Every section names its sources, stored with the document (artifact-chain CHN1): the map
    # chapters the run's Sociomap, the questions the aggregate, who answered the dataset.
    assert payload["contract"] == DOCUMENT_MODEL_CONTRACT
    sources = {s["id"]: s["sources"] for s in payload["sections"]}
    assert all(sources.values()), [k for k, v in sources.items() if not v]
    named = {k: {x.get("artifact_type") for x in v} for k, v in sources.items()}
    assert "research_aggregate" in named["ch-questions"]
    assert "research_fieldwork_dataset" in named["ch-method"]
    assert all("research_sociomap" in v for k, v in named.items() if k.startswith("ch-native-map"))
    assert [k for k, v in sources.items() if any(x["kind"] == "fixed" for x in v)] == [
        "methodology"
    ]
    assert payload["unread"] == []
    assert "Zdroje · Výsledky jednotlivých otázek" in body


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
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=design, source_stage="run"
        )
        session.commit()

    record_property("design_revision_id", revision.revision_id)
    record_property("design_content_sha256", revision.content_sha256)
    record_property("fixture_origin", "SYNTHETIC_AI_FICTIONAL_AND_RECORDED_WEB")
    models = RecordedModels()
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
    pinned = run["metadata"]["sociomap_methods"]
    assert mapped["methods"] == [
        {"method_id": method["method_id"], "spec_fingerprint": method["spec_fingerprint"]}
        for method in pinned
    ]
    v2 = read_artifact(battery["maps"]["aia-sociomap-3"])
    assert isinstance(v2, SociomapArtifactV3)
    assert v2.scores["primary"] == [obj["id"] for obj in battery["objects"]]
    assert v2.support.respondents == n
    assert v2.spec.fingerprint() == next(
        method["spec_fingerprint"] for method in pinned if method["method_id"] == "aia-sociomap-3"
    )
    assert report.artifact_type == REPORT_ARTIFACT_TYPE
    assert report.metadata["run_id"] == started.run_id
    assert report.metadata["review_state"] == "DRAFT_UNAPPROVED"
    assert report.metadata["synthetic"] is True and report.is_approved is False
    # The step tried the stamp on the bytes it stored and recorded that it takes them: a
    # template change the stamp refuses would leave every approved report unstamped, every
    # path "correct" (cross-review of the stamp record).
    assert report.metadata.get("review_stamp") == REVIEW_STAMP_CONTRACT
    assert {dep.artifact_id for dep in dependencies} == {
        *[steps[analysis_node_key(module)]["output"]["artifact_id"] for module in AnalysisModuleId],
        steps["sociomap"]["output"]["artifact_id"],
    }
    assert document.startswith(b"PK") and lint_docx(document) == []
    _states_its_approval_in_its_footers_alone(document, report_id, report.sha256)
    # The map of aia-sociomap-3 prints the register's approval, never "awaiting" (B4).
    body = zipfile.ZipFile(io.BytesIO(document)).read("word/document.xml").decode()
    assert "schválil k použití ve zprávách" in body
    assert "Mapa metodou aia-sociomap-3 je interním výstupem" not in body
    # The run recorded its research questions as gaps at start (the design links none): the
    # stored report marks the introduction's list and each answer, the reason once (review 3:
    # unwiring the gaps from the worker left every test green).
    recorded = run["metadata"]["answerability"]["gaps"]
    assert recorded and all(g["reasons"] == ["unlinked_design"] for g in recorded)
    assert "bez doložené odpovědi, viz kapitola Respondenti a výpočet" in body
    assert body.count("Bez doložené odpovědi") == len(recorded)
    assert "Ani tuto odpověď nečtěte jako doloženou" in body
    # Results reads the same record (PC2): the analysis route marks every answer to a gap, in
    # the words the report prints, so the screen never reads one as measured.
    from aia_api.routers.research import run_analysis

    with world.sessions() as session:
        shown = run_analysis(started.run_id, world.lead_scope(session), session, store)
    answers = [a for m in shown["modules"].values() for a in m["research_question_answers"]]
    gapped = {" ".join(str(g["research_question"]).split()) for g in recorded}
    to_gaps = [a for a in answers if " ".join(a["question"].split()) in gapped]
    assert to_gaps and all(a["gap"] and a["gap"] in body for a in to_gaps)
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
                combined = contextual_report(
                    session,
                    world.lead_scope(session),
                    store,
                    run_id=started.run_id,
                    deep_research_run_id=interpreted.run_id,
                )
                assert any(s.id == "literature" for s in combined.sections)
                # The report with literature takes the same recorded gaps (review 3).
                assert any(
                    isinstance(b, Callout) and b.title == "Bez doložené odpovědi"
                    for s in combined.sections
                    for b in s.blocks
                )
                assert any((s.id or "").startswith("ch-native-map-") for s in combined.sections)
                # The same study's report: the same design, method and question chapters.
                assert {"ch-design", "ch-method", "ch-questions", "app-questionnaire"} <= {
                    s.id for s in combined.sections
                }
                assert DocxRenderer().render(combined).startswith(b"PK")
                # Stored once as an unapproved draft; the next download reads that artifact.
                stored, data = stored_contextual_report(
                    session,
                    world.lead_scope(session),
                    store,
                    run_id=started.run_id,
                    deep_research_run_id=interpreted.run_id,
                )
                again, same = stored_contextual_report(
                    session,
                    world.lead_scope(session),
                    store,
                    run_id=started.run_id,
                    deep_research_run_id=interpreted.run_id,
                )
                assert data.startswith(b"PK") and same == data
                # The front matter and the literature chapter name one seal, the one the bundle
                # verifies (research-integrity-report 4: they printed two different hashes).
                printed = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
                assert printed.count(evidence.sha256) == 2
                assert "Pečeť balíčku" in printed and "Pečeť ověřeného balíčku" in printed
                # The source table's approval is the review's own pin: this one runs under the
                # code's proposed defaults, so the table reads as not yet approved (review 3).
                assert run_settings(runs.get(interpreted.run_id)["metadata"]) is not None
                assert "dosud neschválila" in printed and "nezaznamenala" not in printed
                assert again.artifact_id == stored.artifact_id and not stored.is_approved
                # Once approved, its export states that in every footer and nowhere says
                # otherwise: the literature chapter called itself part of an unapproved draft
                # under a SCHVÁLENO footer (cross-review, D2).
                _states_its_approval_in_its_footers_alone(data, stored.artifact_id, stored.sha256)
                assert stored.metadata["review_state"] == "DRAFT_UNAPPROVED"
                assert stored.metadata["deep_research_run_id"] == interpreted.run_id
                # The literature chapter is stampable too, as stored_contextual_report recorded.
                assert stored.metadata.get("review_stamp") == REVIEW_STAMP_CONTRACT
                # A newer draft of the same pair (the study renamed and prepared again), then the
                # first sources once more: prepare stores its draft again so the draft it asks a
                # PDF for is the one every read names (review 2: they were two drafts).
                drafts = research_artifacts(session, world.lead_scope(session), store)
                renamed, _ = drafts.put(
                    project_id=stored.project_id,
                    revision=stored.revision,
                    stage_type=stored.stage_type,
                    artifact_type=stored.artifact_type,
                    data=b"PK renamed",
                    input_fingerprint="renamed",
                    metadata=dict(stored.metadata),
                )
                restored, restored_data = stored_contextual_report(
                    session,
                    world.lead_scope(session),
                    store,
                    run_id=started.run_id,
                    deep_research_run_id=interpreted.run_id,
                )
                assert restored.artifact_id not in (stored.artifact_id, renamed.artifact_id)
                assert restored_data == data
                current = prepared_context_report(
                    session,
                    world.lead_scope(session),
                    store,
                    run_id=started.run_id,
                    deep_research_run_id=interpreted.run_id,
                )
                assert current is not None and current.artifact_id == restored.artifact_id
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
            with pytest.raises(ReportCompositionRefused, match="does not interpret"):
                contextual_report(
                    session, scope, store, run_id=started.run_id, deep_research_run_id=deep_run_id
                )
        assert len(agents.requests) > deep_calls
        assert len(models.requests) == fieldwork_analysis_calls
        assert worker.run_once() is None


class _FakePdf:
    """A converter that renders a PDF naming the DOCX it was given, or fails."""

    version = "fake-pdf 1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def convert(self, docx: bytes) -> bytes:
        self.calls += 1
        if self.fail:
            raise PdfConversionFailed("exited 1")
        return b"%PDF-1.7 rendering of " + hashlib.sha256(docx).hexdigest().encode()


def _start_report_run(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    return started.run_id


def test_a_run_pins_its_design_research_and_every_module_is_shown_it_as_context(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    deep_research_fixture: Any,
) -> None:
    """evidence-integrity 7: with the switch on, a run pins the Study's newest sealed Design
    Research bundle when it starts, and every module is shown its accepted findings as external
    context: in the payload and the fingerprint, never as evidence. A pin that no longer names
    that bundle is refused, never read as no context."""
    design = {
        **deep_research_fixture.DESIGN_2,
        "n": 150,
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
        revision, _ = StudyDesignRepository(
            session, world.lead_scope(session)
        ).submit_as_working_copy(content=design, source_stage="run")
        session.commit()
    models = RecordedModels()
    agents = deep_research_fixture.RecordedAgents(deep_research_fixture.ANSWERS)
    deep_runtime = deep_research_fixture.recorded(
        world, agents, approved_for=deep_research_fixture.DEVELOP_ROUTE, contents=(design,)
    )
    worker = run_with(models, env=env, ai_fieldwork=True, deep_research=deep_runtime)
    with world.sessions() as session:
        deep_run_id = (
            DeepResearchRuns(session, world.lead_scope(session))
            .start(
                design_revision_id=revision.revision_id,
                preset_name="QUICK",
                channels=(Channel.WEB,),
            )
            .run_id
        )
        session.commit()
    _drain(worker)
    with world.sessions() as session:
        scope = world.lead_scope(session)
        bundle = DeepResearchRuns(session, scope).bundle(deep_run_id, store=store)
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.AI_RUNTIME,
            analysis_enabled=True,
            external_context=True,
        )
        session.commit()
    lines = list(external_context_lines(public_context(bundle)))
    assert lines == list(external_context_lines(analysis_context(bundle))), "every finding public"
    assert lines and all(line.startswith("[") for line in lines)
    # A finding drawn from the client's own knowledge is never sent under the module's class.
    first = bundle.accepted[0]
    private = first.model_copy(
        update={
            "evidence": first.evidence.model_copy(
                update={"data_class": DataClass.CLASS_A_CLIENT_CONFIDENTIAL}
            )
        }
    )
    mixed = bundle.model_copy(update={"accepted": (private, *bundle.accepted[1:])})
    assert len(external_context_lines(public_context(mixed))) == len(lines) - 1
    _drain(worker)

    run = _run(world, started.run_id)
    pin = run["metadata"]["analysis_context"]
    assert pin["deep_research_run_id"] == deep_run_id
    with world.sessions() as session:
        published = next(
            x
            for x in DeepResearchRuns(session, world.lead_scope(session)).get(deep_run_id)["steps"]
            if x["node_key"] == "publish"
        )["output"]
    assert (pin["artifact_id"], pin["sha256"]) == (published["artifact_id"], published["sha256"])
    assert run["status"] is WorkflowRunStatus.COMPLETED, _unfinished(world, started.run_id)
    for module in MODULES:
        payload = json.loads(models.messages(module, 1)[0])
        assert payload["external_context_not_evidence"] == lines, module
    assert _reconstruct(world, store, started.run_id).complete

    for broken, reason in (
        ({**pin, "sha256": "0" * 64}, "context_moved"),
        ({**pin, "artifact_id": "elsewhere"}, "context_moved"),
        ({**pin, "deep_research_run_id": str(uuid.uuid4())}, "context_not_found"),
        ({"deep_research_run_id": deep_run_id}, "context_pin"),
    ):
        with world.sessions() as session, pytest.raises(SourcesRefused) as refused:
            native_sources(
                session,
                world.lead_scope(session),
                store,
                {**run, "metadata": {**run["metadata"], "analysis_context": broken}},
            )
        assert refused.value.reason == reason, broken


def test_without_the_switch_a_run_pins_no_context_and_its_modules_are_shown_none(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels()
    worker = run_with(models)
    run_id = _started_with_analysis(world)
    _drain(worker)
    assert "analysis_context" not in _run(world, run_id)["metadata"]
    assert json.loads(models.messages("executive", 1)[0])["external_context_not_evidence"] == []


def test_the_report_step_stores_its_docx_rendered_as_pdf_beside_it(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """Complete-study-report B3: the PDF is the stored DOCX's rendering, never a second
    composition, and depends on it."""
    run_id = _start_report_run(world)
    pdf = _FakePdf()
    assert _drain(run_with(RecordedModels(), pdf=pdf)) == ["completed"] * 14
    output = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "report")["output"]
    assert output["pdf"]["state"] == "READY" and pdf.calls == 1
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        docx = repo.read(output["artifact_id"])
        stored = repo.get(output["pdf"]["artifact_id"])
        data = repo.read(stored.artifact_id)
        dependencies = repo.dependencies(stored.artifact_id)
    assert data == b"%PDF-1.7 rendering of " + hashlib.sha256(docx).hexdigest().encode()
    assert stored.artifact_type == "research_internal_pdf"
    assert stored.content_type == "application/pdf"
    assert stored.metadata["rendering_of"] == output["artifact_id"]
    assert stored.metadata["run_id"] == run_id
    assert stored.metadata["converter"] == "fake-pdf 1"
    assert [d.artifact_id for d in dependencies] == [output["artifact_id"]]


class _ShutdownOnce(_FakePdf):
    """A converter whose first conversion meets the worker shutting down: the attempt is
    released after its DOCX was stored, and the step runs again."""

    def convert(self, docx: bytes) -> bytes:
        if self.calls == 0:
            self.calls += 1
            raise ShutdownRequested("worker stopping")
        return super().convert(docx)


def test_the_steps_pdf_renders_the_stored_docx_when_the_step_reuses_it(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A step that runs again finds the DOCX it stored by fingerprint, which holds the
    contract and the inputs, never the renderer: rendering again may give other bytes (a
    deploy between the attempts). The PDF beside the stored DOCX renders the stored bytes."""
    rendered: list[bytes] = []
    render = DocxRenderer.render

    def renders_differently(self: DocxRenderer, doc: Any) -> bytes:
        rendered.append(render(self, doc) + (b"\0" * len(rendered)))
        return rendered[-1]

    monkeypatch.setattr(DocxRenderer, "render", renders_differently)
    run_id = _start_report_run(world)
    pdf = _ShutdownOnce()
    assert "released" in _drain(run_with(RecordedModels(), pdf=pdf))
    report = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "report")
    output = report["output"]
    assert report["status"] is StepRunStatus.SUCCEEDED and output["reused"] is True
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        docx = repo.read(output["artifact_id"])
        stored_pdf = repo.read(output["pdf"]["artifact_id"])
    assert len(rendered) == 2 and docx == rendered[0] != rendered[1]
    assert stored_pdf == b"%PDF-1.7 rendering of " + hashlib.sha256(docx).hexdigest().encode()
    # Its document model was stored once, beside the stored DOCX, and found again (RD5a): the
    # ids every later edit names do not move when the step runs again.
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        stored_docx = repo.get(output["artifact_id"])
        models = [
            a
            for a in repo.list_for_stage(
                project_id=stored_docx.project_id,
                revision=stored_docx.revision,
                stage_type=stored_docx.stage_type,
            )
            if a.artifact_type == REPORT_DOCUMENT_ARTIFACT_TYPE
        ]
    assert [m.artifact_id for m in models] == [output["document"]["artifact_id"]]
    assert models[0].metadata["docx_artifact_id"] == output["artifact_id"]


def test_a_pdf_that_cannot_be_made_is_said_so_and_the_report_still_stands(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    run_id = _start_report_run(world)
    assert _drain(run_with(RecordedModels(), pdf=_FakePdf(fail=True))) == ["completed"] * 14
    step = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "report")
    assert step["status"] is StepRunStatus.SUCCEEDED
    assert step["output"]["artifact_id"]
    assert step["output"]["pdf"] == {
        "state": "FAILED",
        "reason": "pdf_conversion_failed",
        "message": "exited 1",
    }


def test_without_the_switch_the_report_step_makes_no_pdf(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    run_id = _start_report_run(world)
    assert _drain(run_with(RecordedModels())) == ["completed"] * 14
    step = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "report")
    assert "pdf" not in step["output"]


def test_report_step_finishes_with_a_reason_when_an_analysis_module_is_blocked(
    world: Any, run_with: Callable[..., Worker]
) -> None:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    endings = _drain(run_with(RecordedModels(invent={"objects"})))
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
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    worker = run_with(RecordedModels())
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
    models = RecordedModels()
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
        # The design is Class B by the owner's rule (2026-10-19): the operator's Class C for
        # its bytes does not lower it, and the fictional dataset's Class C does not either.
        assert e.data_class.value == "CLASS_B_DERIVED_CLIENT"
        assert e.agent_id == "aia.analysis.module"
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
    models = RecordedModels()
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
    models = RecordedModels()
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
    models = RecordedModels()
    first = _start(world)
    _drain(run_with(models))
    with world.sessions() as session:
        StudyDesignRepository(session, world.lead_scope(session)).submit_as_working_copy(
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
    models = RecordedModels(invent={"objects"})
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


def _started_with_analysis(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    return started.run_id


def _retry_analysis(world: Any, store: InMemoryArtifactStore, run_id: str) -> Any:
    with world.sessions() as session:
        started = retry_failed_modules(session, world.lead_scope(session), store, run_id=run_id)
        session.commit()
    return started


def test_retrying_failed_modules_asks_only_them_over_the_same_data(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """The live failure: data collected, a module blocked after three paid turns, the report
    refused. A retry collects nothing, reuses every completed module, asks the blocked one
    again in a new round, and the report composes once all eight complete."""
    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    original = _run(world, first)
    assert original["status"] is WorkflowRunStatus.FAILED, "the report refused, as it must"
    assert _reconstruct(world, store, first).retryable == (AnalysisModuleId.OBJECTS,)
    dataset = next(s for s in original["steps"] if s["node_key"] == "run")["output"]
    asked_before = list(models.asked)

    models.invent.clear()  # the model now answers within the evidence
    retry = _retry_analysis(world, store, first)
    assert retry.created
    assert _retry_analysis(world, store, first).run_id == retry.run_id, "idempotent"
    _drain(worker)

    second = _run(world, retry.run_id)
    assert second["status"] is WorkflowRunStatus.COMPLETED, _unfinished(world, retry.run_id)
    assert models.asked[len(asked_before) :] == [("objects", 4)], "only the failed module, once"
    steps = {s["node_key"]: s for s in second["steps"]}
    assert steps["run"]["output"]["artifact_id"] == dataset["artifact_id"]
    assert steps["run"]["output"]["frozen_from_run"] == first
    assert steps["run"]["output"]["reused"] is True
    assert second["metadata"]["retry_of"] == first
    assert second["metadata"]["analysis_retry"]["round"] == 1
    assert second["metadata"]["analysis_retry"]["modules"] == ["objects"]
    reused = [m for m, step in _analysis(second).items() if step["output"]["reused"]]
    assert sorted(reused) == sorted(m for m in MODULES if m != "objects")
    assert _reconstruct(world, store, retry.run_id).complete
    assert steps["report"]["status"] is StepRunStatus.SUCCEEDED

    with pytest.raises(AnalysisNotRetryable) as nothing:
        _retry_analysis(world, store, retry.run_id)
    assert nothing.value.reason == "nothing_to_retry"


def test_a_retry_of_a_run_an_earlier_compiler_compiled_reuses_its_specification(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """input-interactions 3b, review of #538: a run compiled before compile-2 is retried over
    its own stored specification, by id and SHA-256, never compiled again. Compiled again, its
    specification's bytes would move every completed module's reuse key: each would be asked
    (paid) again while the ceiling counted it reused."""
    from aia_core.application import research as research_app
    from aia_core.domain import research_design

    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    monkeypatch.setattr(research_design, "COMPILER_VERSION", "aia-research-compile-1")
    first = _started_with_analysis(world)
    _drain(worker)
    monkeypatch.undo()
    assert research_design.COMPILER_VERSION == "aia-research-compile-3"
    original = _run(world, first)
    compiled = next(s for s in original["steps"] if s["node_key"] == "compile")["output"]
    spec_payload = _payload(world, store, compiled["artifact_id"])
    assert spec_payload["specification"]["compiler_version"] == "aia-research-compile-1"
    asked_before = list(models.asked)

    ceilings: list[int] = []
    real = research_app.ResearchRuns.retry_analysis

    def spy(self: Any, run_id: str, *, frozen_dataset: FrozenDataset, **kw: Any) -> Any:
        ceilings.append(frozen_dataset.modules_asked)
        return real(self, run_id, frozen_dataset=frozen_dataset, **kw)

    monkeypatch.setattr(research_app.ResearchRuns, "retry_analysis", spy)
    models.invent.clear()
    retry = _retry_analysis(world, store, first)
    _drain(worker)

    second = _run(world, retry.run_id)
    assert second["status"] is WorkflowRunStatus.COMPLETED, _unfinished(world, retry.run_id)
    steps = {s["node_key"]: s for s in second["steps"]}
    assert steps["compile"]["output"]["artifact_id"] == compiled["artifact_id"]
    assert steps["compile"]["output"]["sha256"] == compiled["sha256"]
    assert steps["compile"]["output"]["frozen_from_run"] == first
    # Zero new calls for the completed modules; the ceiling counted exactly what was asked.
    new = models.asked[len(asked_before) :]
    assert new == [("objects", 4)]
    assert ceilings == [len({m for m, _ in new})] == [1]
    reused = [m for m, step in _analysis(second).items() if step["output"]["reused"]]
    assert sorted(reused) == sorted(m for m in MODULES if m != "objects")


def _stored_spec(world: Any, store: InMemoryArtifactStore, like: str, payload: Any) -> Any:
    """``payload`` stored as a specification artifact of ``like``'s project and revision."""
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        model = repo.get(like)
        artifact, _ = repo.put_json(
            payload=payload,
            project_id=model.project_id,
            revision=model.revision,
            stage_type=model.stage_type,
            artifact_type=model.artifact_type,
            input_fingerprint=f"test:{uuid.uuid4().hex}",
            reuse=False,
        )
        session.commit()
    return artifact


@pytest.mark.parametrize(
    ("shape", "reason"),
    [
        ("other_bytes", "frozen_specification_mismatch"),
        ("no_specification", "frozen_specification_corrupt"),
        ("not_a_specification", "frozen_specification_corrupt"),
        ("unknown_revision", "frozen_specification_mismatch"),
    ],
)
def test_a_retry_whose_specification_does_not_read_is_refused_by_name(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    shape: str,
    reason: str,
) -> None:
    """Never compiled again, never an unclassified crash: a named specification with other
    bytes, without one, that does not validate, or of a revision that is not here, fails the
    retry's compile step by name, before any module is asked."""
    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    original = _run(world, first)
    dataset = next(s for s in original["steps"] if s["node_key"] == "run")["output"]
    compiled = next(s for s in original["steps"] if s["node_key"] == "compile")["output"]
    named_id, named_sha = compiled["artifact_id"], compiled["sha256"]
    stored = _payload(world, store, compiled["artifact_id"])
    if shape == "other_bytes":
        named_sha = "0" * 64
    else:
        payload = {
            "no_specification": {k: v for k, v in stored.items() if k != "specification"},
            "not_a_specification": {**stored, "specification": {"title": "jen název"}},
            "unknown_revision": {**stored, "design_revision_id": "DRV-not-here"},
        }[shape]
        artifact = _stored_spec(world, store, compiled["artifact_id"], payload)
        named_id, named_sha = artifact.artifact_id, artifact.sha256
    with world.sessions() as session:
        started = ResearchRuns(session, world.lead_scope(session)).start(
            design_revision_id=original["metadata"]["design_revision_id"],
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
            retry_of=first,
            frozen_dataset=FrozenDataset(
                run_id=first,
                artifact_id=dataset["artifact_id"],
                sha256=dataset["sha256"],
                analysis_round=1,
                retried=("objects",),
                modules_asked=1,
                specification_artifact_id=named_id,
                specification_sha256=named_sha,
            ),
        )
        session.commit()
    _drain(worker)
    steps = {s["node_key"]: s for s in _run(world, started.run_id)["steps"]}
    assert steps["compile"]["status"] is StepRunStatus.FAILED
    last = steps["compile"]["attempts"][-1]
    assert last["error"]["reason"] == reason
    assert last["failure_class"] is FailureClass.SCHEMA_VIOLATION
    assert not any(s["attempts"] for s in _analysis(_run(world, started.run_id)).values())


def test_the_hypotheses_module_is_given_the_design_s_stated_hypotheses(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """Q72: before this, the module answered "none supplied" whatever the design stated."""
    stated = ["Mladší pijí víc čaje než starší."]
    design = {**DESIGN, "research_plan": {**DESIGN["research_plan"], "hypotheses": stated}}
    models = RecordedModels()
    worker = run_with(models)
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=design, source_stage="run"
        )
        ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
        )
        session.commit()
    _drain(worker)
    assert json.loads(models.messages("hypotheses", 1)[0])["stated_hypotheses"] == stated
    assert "stated_hypotheses" not in json.loads(models.messages("executive", 1)[0])


def test_a_module_completed_without_a_finding_is_asked_again_over_the_same_data(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    """MVPQ-04, evidence-integrity 9a: the executive summary, always expected to find, completed
    with no key finding carries a diagnostic, never a finding, and a same-data retry asks it
    again in a new round instead of reusing the empty answer; every other module is reused."""
    models = RecordedModels(no_findings={"executive"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    with world.sessions() as session:
        stored = stored_analysis(session, world.lead_scope(session), store, run_id=first)
    record = stored.records[AnalysisModuleId.EXECUTIVE]
    assert record.outcome == "COMPLETED" and record.finding_expected is True
    assert no_supported_finding(record)
    assert stored.retryable == (AnalysisModuleId.EXECUTIVE,)
    # Results reads it beside the module, never as a finding (the analysis route).
    from aia_api.routers.research import run_analysis

    with world.sessions() as session:
        shown = run_analysis(first, world.lead_scope(session), session, store)
    executive = shown["modules"]["executive"]
    assert executive["key_findings"] == []
    assert executive["diagnostic"] == finding_diagnostic(record)
    assert executive["diagnostic"]["reason"] == "no_supported_finding"
    asked_before = len(models.asked)

    models.no_findings.clear()
    retry = _retry_analysis(world, store, first)
    _drain(worker)
    assert models.asked[asked_before:] == [("executive", 2)], "only the empty module, once"
    reused = [
        m for m, step in _analysis(_run(world, retry.run_id)).items() if step["output"]["reused"]
    ]
    assert sorted(reused) == sorted(m for m in MODULES if m != "executive")
    with world.sessions() as session:
        again = stored_analysis(session, world.lead_scope(session), store, run_id=retry.run_id)
    assert not no_supported_finding(again.records[AnalysisModuleId.EXECUTIVE])
    assert again.retryable == ()


@pytest.mark.parametrize(("stated", "held"), [(True, True), (False, False)])
def test_no_context_from_the_hypotheses_module_holds_only_when_the_design_states_some(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    stated: bool,
    held: bool,
) -> None:
    """Q72 (A), the guard: whether the hypotheses' context exists is decided by code from the
    design, never from the model's "no context". With hypotheses stated, an empty answer holds
    and is offered a same-data round; with none, it is context_missing and holds nothing."""
    plan = {
        **DESIGN["research_plan"],
        **({"hypotheses": ["Mladší pijí víc čaje."]} if stated else {}),
    }
    models = RecordedModels(no_findings={"hypotheses"})
    worker = run_with(models)
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content={**DESIGN, "research_plan": plan}, source_stage="run"
        )
        run_id = (
            ResearchRuns(session, scope)
            .start(
                design_revision_id=revision.revision_id,
                fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
                analysis_enabled=True,
            )
            .run_id
        )
        session.commit()
    _drain(worker)
    with world.sessions() as session:
        stored = stored_analysis(session, world.lead_scope(session), store, run_id=run_id)
    record = stored.records[AnalysisModuleId.HYPOTHESES]
    assert no_supported_finding(record) is held
    assert (stored.retryable == (AnalysisModuleId.HYPOTHESES,)) is held
    diagnostic = finding_diagnostic(record)
    assert diagnostic is not None
    assert diagnostic["reason"] == ("no_supported_finding" if held else "context_missing")


def test_a_retry_round_asks_again_what_the_model_refused_and_replays_nothing_old(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    retry = _retry_analysis(world, store, first)
    _drain(worker)  # still inventing: three new turns, blocked again
    assert models.calls("objects") == [1, 2, 3, 4, 5, 6]
    assert _run(world, retry.run_id)["status"] is WorkflowRunStatus.FAILED
    again = _retry_analysis(world, store, retry.run_id)
    assert _run(world, again.run_id)["metadata"]["analysis_retry"]["round"] == 2


def test_a_run_stored_under_the_previous_harness_can_still_be_repaired(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runs this repairs were stored under harness 1, which reconstruct_run refuses to
    re-admit. The retry reads their outcomes as stored, and asks again every module whose
    reuse key the harness change moved."""
    import aia_core.application.analysis_results as analysis_results

    today = analysis_results.harness_summary

    def earlier(**kw: Any) -> Any:
        return today(**kw).model_copy(update={"harness_version": "aia-analysis-harness-1"})

    monkeypatch.setattr(analysis_results, "harness_summary", earlier)
    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    monkeypatch.undo()
    models.invent.clear()
    with pytest.raises(ReconstructionRefused) as old:
        _reconstruct(world, store, first)
    assert old.value.reason == "fingerprint_mismatch"
    with world.sessions() as session:
        stored = stored_analysis(session, world.lead_scope(session), store, run_id=first)
    # The blocked module, and every module completed under the earlier harness (PC3): today's
    # refuses to re-admit them, and the retry below asks every one again.
    assert stored.retryable == tuple(AnalysisModuleId)
    assert set(stored.stale) == set(AnalysisModuleId) - {AnalysisModuleId.OBJECTS}

    asked_before = len(models.asked)
    retry = _retry_analysis(world, store, first)
    _drain(worker)
    assert _run(world, retry.run_id)["status"] is WorkflowRunStatus.COMPLETED
    assert sorted(m for m, _ in models.asked[asked_before:]) == sorted(MODULES)
    assert _reconstruct(world, store, retry.run_id).complete


def test_a_run_whose_every_module_an_earlier_harness_completed_is_repaired_over_its_data(
    world: Any,
    store: InMemoryArtifactStore,
    run_with: Callable[..., Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PC3: all eight modules completed, then the harness or a prompt moved. The run's analysis
    was refused whole (fingerprint_mismatch), and with nothing BLOCKED or FAILED there was
    nothing to retry: the analysis, its literature report and its Interpretation Research
    stayed dark for good, or cost a whole run with new fieldwork. Now the modules are asked
    again over the same dataset, and the run's own data is never collected again."""
    import aia_core.application.analysis_results as analysis_results

    today = analysis_results.harness_summary

    def earlier(**kw: Any) -> Any:
        return today(**kw).model_copy(update={"harness_version": "aia-analysis-harness-1"})

    monkeypatch.setattr(analysis_results, "harness_summary", earlier)
    models = RecordedModels()
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    assert _run(world, first)["status"] is WorkflowRunStatus.COMPLETED
    monkeypatch.undo()

    with pytest.raises(ReconstructionRefused) as dark:
        _reconstruct(world, store, first)
    assert dark.value.reason == "fingerprint_mismatch"
    with world.sessions() as session:
        stored = stored_analysis(session, world.lead_scope(session), store, run_id=first)
    assert stored.retryable == stored.stale == tuple(AnalysisModuleId)

    dataset = next(s for s in _run(world, first)["steps"] if s["node_key"] == "run")["output"]
    asked_before = len(models.asked)
    retry = _retry_analysis(world, store, first)
    _drain(worker)
    second = _run(world, retry.run_id)
    assert second["status"] is WorkflowRunStatus.COMPLETED, _unfinished(world, retry.run_id)
    assert sorted(m for m, _ in models.asked[asked_before:]) == sorted(MODULES)
    fieldwork = next(s for s in second["steps"] if s["node_key"] == "run")["output"]
    assert (fieldwork["artifact_id"], fieldwork["reused"]) == (dataset["artifact_id"], True)
    assert _reconstruct(world, store, retry.run_id).complete

    with pytest.raises(AnalysisNotRetryable) as nothing:
        _retry_analysis(world, store, retry.run_id)
    assert nothing.value.reason == "nothing_to_retry"


def test_a_run_cancelled_after_fieldwork_has_its_cancelled_modules_asked_over_its_data(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels()
    worker = run_with(models)
    first = _started_with_analysis(world)
    while not any(
        s["node_key"] == "aggregate" and s["status"] is StepRunStatus.SUCCEEDED
        for s in _run(world, first)["steps"]
    ):
        assert worker.run_once() is not None, _unfinished(world, first)
    with world.sessions() as session:
        ResearchRuns(session, world.lead_scope(session)).cancel(first)
        session.commit()
    _drain(worker)
    assert _run(world, first)["status"] is WorkflowRunStatus.CANCELLED
    asked_before = len(models.asked)

    retry = _retry_analysis(world, store, first)
    _drain(worker)
    assert _run(world, retry.run_id)["status"] is WorkflowRunStatus.COMPLETED
    before = {m for m, _ in models.asked[:asked_before]}
    after = [m for m, _ in models.asked[asked_before:]]
    # Each module asked once over the frozen data: the cancelled ones now, none twice.
    assert sorted(after) == sorted(set(MODULES) - before)
    assert _reconstruct(world, store, retry.run_id).complete


def test_a_retry_whose_dataset_does_not_match_its_bytes_is_refused_not_collected_again(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels(invent={"objects"})
    worker = run_with(models)
    first = _started_with_analysis(world)
    _drain(worker)
    original = _run(world, first)
    dataset = next(s for s in original["steps"] if s["node_key"] == "run")["output"]
    with world.sessions() as session:
        started = ResearchRuns(session, world.lead_scope(session)).start(
            design_revision_id=original["metadata"]["design_revision_id"],
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            analysis_enabled=True,
            retry_of=first,
            frozen_dataset=FrozenDataset(
                run_id=first,
                artifact_id=dataset["artifact_id"],
                sha256="0" * 64,
                analysis_round=1,
                retried=("objects",),
                modules_asked=1,
            ),
        )
        session.commit()
    _drain(worker)
    steps = {s["node_key"]: s for s in _run(world, started.run_id)["steps"]}
    assert steps["run"]["status"] is StepRunStatus.FAILED
    assert steps["run"]["attempts"][-1]["error"]["reason"] == "frozen_dataset_mismatch"
    assert not any(s["attempts"] for s in _analysis(_run(world, started.run_id)).values())


def test_a_retry_refuses_a_run_that_has_not_finished_or_ran_no_analysis(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    first = _started_with_analysis(world)
    with pytest.raises(AnalysisNotRetryable) as early:
        _retry_analysis(world, store, first)
    assert early.value.reason == "run_not_finished"
    plain = _start(world)
    _drain(run_with(RecordedModels()))
    with pytest.raises(AnalysisNotRetryable) as none:
        _retry_analysis(world, store, plain)
    assert none.value.reason == "analysis_not_in_run"


def test_an_answer_off_the_output_contract_is_one_counted_turn_that_the_next_repairs(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels(off_contract={("executive", 1)})
    run_id = _start(world)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    assert models.calls("executive") == [1, 2], "no schema repair hidden inside the turn"
    _payload, previous, repair = models.messages("executive", 2)
    assert json.loads(previous)["confidence"] == "high", "the repair shows the refused answer"
    assert "output schema check of the previous answer reported" in repair
    assert "confidence" in repair, "and names the field it broke"

    output = _analysis(_run(world, run_id))["executive"]["output"]
    assert (output["outcome"], output["calls_sent"]) == ("COMPLETED", 2)
    record = _record(world, store, output["artifact_id"])
    assert [c.answer for c in record.calls] == ["SCHEMA_INVALID", "DRAFT"]
    assert record.calls[0].cost_usd == pytest.approx(ANALYSIS_CALL_USD), "the refused answer cost"
    terminal = [e for e in _ledger(world, run_id) if e.outcome.is_terminal]
    assert len(terminal) == 9 and {e.purpose.value for e in terminal} == {"PRIMARY"}


def test_a_module_off_the_contract_every_turn_is_blocked_naming_the_field_and_replays_free(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels(off_contract={("executive", n) for n in (1, 2, 3)})
    run_id = _start(world)
    assert _drain(run_with(models)) == ["completed"] * 13, _unfinished(world, run_id)
    assert models.calls("executive") == [1, 2, 3]
    _payload, previous, _repair = models.messages("executive", 3)
    assert json.loads(previous)["confidence"] == "high"

    output = _analysis(_run(world, run_id))["executive"]["output"]
    assert (output["outcome"], output["calls_sent"]) == ("BLOCKED", 3)
    record = _record(world, store, output["artifact_id"])
    assert [c.answer for c in record.calls] == ["SCHEMA_INVALID"] * 3
    # The stored outcome says which field failed, not "the draft is not a JSON object".
    assert [(v.code, v.subject) for v in record.violations] == [
        (ViolationCode.SCHEMA_INVALID, "confidence")
    ]
    assert "high" not in record.violations[0].detail, "a path and a reason, never a value"


def test_the_research_questions_module_without_a_question_is_blocked_while_the_rest_run(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker]
) -> None:
    models = RecordedModels()
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
    """A content-bound Class A declaration raises the design above its rule's Class B, and a
    route approved for B and C refuses it; the park says who raised it."""
    models = RecordedModels()
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
        assert error["design_class"] == {
            "data_class": "CLASS_A_CLIENT_CONFIDENTIAL",
            "source": "operator",
        }
    assert _ledger(world, run_id) == [] and _reservations(world, run_id) == []


def test_a_dataset_that_recorded_no_lineage_is_refused_by_the_licence_gate(
    world: Any, run_with: Callable[..., Worker], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        analysis,
        "dataset_material",
        lambda *a, **k: DatasetMaterial(lineage=None, respondents_fictional=True),
    )
    models = RecordedModels()
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
    models = RecordedModels()
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
    models = RecordedModels()
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
    models = RecordedModels(
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
    models = RecordedModels(
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
    models = RecordedModels(invent_calls={(m, 1) for m in MODULES})

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


def test_the_step_events_switch_reaches_the_analysis_configuration(world: Any) -> None:
    """AIA_AI_STEP_EVENTS: each module turn's model request writes its sent and answered."""
    off = AnalysisConfig.from_settings(
        _settings(world), max_output_tokens=4096, reservation_usd=1.0
    )
    on = AnalysisConfig.from_settings(
        _settings(world, AIA_AI_STEP_EVENTS="true"), max_output_tokens=4096, reservation_usd=1.0
    )
    assert (off.step_events, on.step_events) == (False, True)


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
    gateway = build_gateway(settings, transport=RecordedModels(), signer=RecordedSigner())
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
    models = RecordedModels()
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
    assert {e.data_class.value for e in events} == {"CLASS_B_DERIVED_CLIENT"}  # the design's


@pytest.mark.parametrize("n", [50, 150])
def test_the_support_forecast_is_what_the_aggregate_then_computes(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker], n: int
) -> None:
    """Readiness forecasts a run's donors and support from the roster fieldwork will draw
    (plan run-recovery-and-truth 2a). After the run, every question the respondents all
    answered carries exactly that: 50 fictional respondents are suppressed, 150 are not."""
    from aia_core.domain.evidence.support import AIA_SUPPORT_V1
    from aia_core.domain.fieldwork import PersonaSource
    from aia_core.domain.research_design import ResearchSpecification
    from aia_core.domain.support_forecast import forecast_support

    models = RecordedModels()
    run_id = _start(world, {**DESIGN, "n": n}, source=FieldworkSource.AI_RUNTIME)
    worker = run_with(models, ai_fieldwork=True)
    while not {"compile", "aggregate"} <= {
        s["node_key"]
        for s in _run(world, run_id)["steps"]
        if s["status"] is StepRunStatus.SUCCEEDED
    }:
        assert worker.run_once() is not None, _unfinished(world, run_id)
    steps = {s["node_key"]: s for s in _run(world, run_id)["steps"]}
    with world.sessions() as session:
        repo = research_artifacts(session, world.lead_scope(session), store)
        spec = ResearchSpecification.model_validate(
            repo.read_json(steps["compile"]["output"]["artifact_id"])["specification"]
        )
        aggregate = repo.read_json(steps["aggregate"]["output"]["artifact_id"])["aggregate"]
    forecast = forecast_support(
        spec, support=AIA_SUPPORT_V1, persona_source=PersonaSource.FICTIONAL_ROSTER
    )
    answered_by_all = [q for q in aggregate["questions"].values() if q["n_chybi"] == 0]
    assert answered_by_all
    assert {q["n_unique_layer_donors"] for q in answered_by_all} == {forecast.donors}
    assert {q["support_status"] for q in answered_by_all} == {forecast.results.value}
    assert (forecast.results.value == "SUPPRESS") is (n == 50)


@pytest.mark.parametrize("how", ["tampered", "missing"])
def test_a_corrupt_ai_dataset_fails_the_module_and_stays_marked_corrupt(
    world: Any, store: InMemoryArtifactStore, run_with: Callable[..., Worker], how: str
) -> None:
    """A module reads the AI runtime's dataset for its lineage. Bytes that fail their hash,
    or an object that is gone, fail it by reason before any call, and the CORRUPT mark the
    read made is committed with the failure (OI-77): read from a session of its own, the
    dataset is CORRUPT, so no later step or run reuses it."""
    models = RecordedModels()
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
    models = RecordedModels(
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
    models = RecordedModels()
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
    models = RecordedModels()
    run_id = _start(world)
    _drain(run_with(models))
    assert models.requests == []
    failed = [s for s in _analysis(_run(world, run_id)).values() if s["attempts"]]
    error = failed[0]["attempts"][-1]
    assert error["failure_class"] is FailureClass.SCHEMA_VIOLATION
    assert error["error"]["reason"] == "aggregate_lineage"
