"""A native run's analysis in the application layer: sources, preparation, reconstruction.

The upstream steps are driven through the real workflow repository, and outcomes are
stored with the one builder the executor uses; nothing here trusts a stored number.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from typing import Any

import pytest

from aia_core.application.analysis import ModuleOutcomeKind
from aia_core.application.analysis_results import (
    AGGREGATE_ARTIFACT,
    DATASET_ARTIFACT,
    SPECIFICATION_ARTIFACT,
    ReconstructionRefused,
    SourcesRefused,
    dataset_material,
    module_artifact,
    native_sources,
    prepare_module,
    reconstruct_module,
    reconstruct_run,
)
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    CallRecord,
    ProducedBy,
    parse_module_artifact,
)
from aia_core.domain.analysis.steps import (
    ANALYSIS_STEP_KIND,
    analysis_step_definitions,
    analysis_step_inputs,
)
from aia_core.domain.evidence import (
    AdmittedClaim,
    ClaimSurface,
    Violation,
    ViolationCode,
)
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource
from aia_core.domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from aia_core.domain.pipeline import ProjectType, fingerprint
from aia_core.domain.research_aggregate import aggregate_dataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.domain.workflow_templates import RESEARCH, steps_for_workflow
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 200,
    "research_plan": {"research_questions": ["Co lidé ráno pijí?"]},
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
INTERNAL = ClaimSurface.INTERNAL


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


class World:
    """One Study's run with analysis nodes, driven step by step like a worker would."""

    def __init__(self, session: Any, scoped: Any, store: InMemoryArtifactStore) -> None:
        self.session, self.scoped, self.store = session, scoped, store
        self.scope = scoped.scope()
        self.engine = WorkflowRepository(session, self.scope)

    def start(self, design: dict[str, Any] = DESIGN) -> str:
        designs = StudyDesignRepository(self.session, self.scope)
        revision, _ = designs.submit(content=design, source_stage="run")
        project_id = designs.project_id()
        assert project_id is not None
        steps = [
            *steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH),
            *analysis_step_definitions(),
        ]
        return self.engine.create_run(
            project_id=project_id,
            project_revision=revision.revision,
            workflow_type=RESEARCH,
            steps=steps,
            idempotency_key=f"{RESEARCH}:{revision.revision_id}:{uuid.uuid4().hex}",
            metadata={
                "design_revision_id": revision.revision_id,
                "fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE.value,
            },
            step_inputs={
                "compile": {"design_revision_id": revision.revision_id},
                "run": {"fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE.value},
                **analysis_step_inputs(INTERNAL),
            },
        )

    def _complete(self, kind: str, build: Any) -> str | None:
        work = self.engine.claim_next(worker_id="w", kinds={kind})
        assert work is not None, kind
        artifact_id = build(work)
        self.engine.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={"artifact_id": artifact_id} if artifact_id else {},
        )
        return artifact_id

    def put(self, work: Any, payload: Any, artifact_type: str, **kw: Any) -> str:
        artifact, _ = research_artifacts(self.session, self.scope, self.store).put_json(
            payload=payload,
            project_id=work.project_id,
            revision=work.project_revision,
            stage_type=work.stage_type,
            artifact_type=artifact_type,
            input_fingerprint=fingerprint({"run": work.run_id, "node": work.node_key}),
            produced_by_job_id=work.attempt_id,
            **kw,
        )
        return artifact.artifact_id

    def upstream(self, *, lineage: bool = True, stop_before: str | None = None) -> None:
        """compile, preflight, run and aggregate, as their executors store them."""
        latest = StudyDesignRepository(self.session, self.scope).latest()
        assert latest is not None
        revision_id = latest.revision_id
        content = StudyDesignRepository(self.session, self.scope).content(revision_id)
        spec, _ = compile_design(content)
        assert spec is not None
        dataset = synthetic_dataset(spec, seed=20260816)
        ids: dict[str, str] = {}

        def compile_(work: Any) -> str:
            ids["spec"] = self.put(
                work,
                {
                    "kind": SPECIFICATION_ARTIFACT,
                    "design_revision_id": revision_id,
                    "specification": spec.model_dump(mode="json"),
                    "specification_fingerprint": spec.fingerprint(),
                },
                SPECIFICATION_ARTIFACT,
            )
            return ids["spec"]

        def fieldwork(work: Any) -> str:
            ids["dataset"] = self.put(
                work,
                {"kind": DATASET_ARTIFACT, "dataset": dataset.model_dump(mode="json")},
                DATASET_ARTIFACT,
                depends_on=[ids["spec"]],
                metadata={
                    "data_origin": DataOrigin.SYNTHETIC_FIXTURE.value,
                    "fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE.value,
                },
            )
            return ids["dataset"]

        def aggregate(work: Any) -> str:
            return self.put(
                work,
                {"kind": AGGREGATE_ARTIFACT, "aggregate": aggregate_dataset(spec, dataset)},
                AGGREGATE_ARTIFACT,
                depends_on=[ids["spec"], ids["dataset"]] if lineage else [ids["spec"]],
                metadata={"data_origin": DataOrigin.SYNTHETIC_FIXTURE.value},
            )

        for kind, build in (
            ("research_compile", compile_),
            ("research_preflight", lambda w: None),
            ("research_fieldwork", fieldwork),
            ("research_aggregate", aggregate),
        ):
            if stop_before == kind:
                return
            self._complete(kind, build)

    def run(self, run_id: str) -> dict[str, Any]:
        return self.engine.get_run(run_id)

    def sources(self, run_id: str) -> Any:
        return native_sources(self.session, self.scope, self.store, self.run(run_id))

    def store_outcomes(self, run_id: str, decide: Any, *, count: int = 8) -> dict[str, str]:
        """Claim ``count`` analysis steps and store the outcome ``decide(prepared)`` builds."""
        stored: dict[str, str] = {}
        sources = self.sources(run_id)
        for _ in range(count):

            def build(work: Any) -> str:
                module = AnalysisModuleId(work.payload["analysis_module"])
                prepared = prepare_module(
                    sources, module_id=module, surface=INTERNAL, language="cs"
                )
                record = decide(prepared)
                stored[module.value] = self.put(
                    work,
                    record.model_dump(mode="json") if hasattr(record, "model_dump") else record,
                    ANALYSIS_MODULE_ARTIFACT,
                )
                return stored[module.value]

            self._complete(ANALYSIS_STEP_KIND, build)
        return stored


@pytest.fixture
def world(session: Any, scoped: Any, store: InMemoryArtifactStore) -> World:
    return World(session, scoped, store)


PRODUCED = ProducedBy(run_id="RUN", step_id="STEP", attempt_id="ATT", kind=ANALYSIS_STEP_KIND)


def call(turn: int = 1) -> CallRecord:
    return CallRecord(
        turn=turn,
        request_sha256="c" * 64,
        answer="DRAFT",
        turn_artifact_id=f"ART-turn-{turn}",
        replayed=False,
        call_id=f"call-{turn}",
        provider_request_id=f"req-{turn}",
        model="eu.test-v1:0",
        route_id="bedrock-eu-primary",
        policy_version="test-v1",
        cost_usd=0.01,
        cost_basis="METERED",
    )


def good_draft(prepared: Any) -> dict[str, Any]:
    row = prepared.inputs.table.rows["q1.mean"]
    value = f"{row.value:.2f}".replace(".", ",")
    rq = [
        {"question": q, "answer": f"Průměr je {value} bodu.", "claim_ids": ["c1"]}
        for q in prepared.inputs.research_questions
    ]
    return {
        "module": prepared.module_id.value,
        "summary": f"Fiktivní respondenti pijí kávu v průměru {value} bodu na škále.",
        "research_question_answers": rq,
        "key_findings": [{"text": f"Průměr je {value}.", "claim_ids": ["c1"]}],
        "numeric_claims": [
            {
                "claim_id": "c1",
                "evidence_ref": "q1.mean",
                "metric": "mean",
                "value": row.value,
                "unit": "scale_mean",
            }
        ],
    }


def completed(prepared: Any) -> Any:
    return module_artifact(
        prepared,
        outcome=ModuleOutcomeKind.COMPLETED,
        draft=good_draft(prepared),
        violations=(),
        calls=(call(),),
        produced_by=PRODUCED,
        runtime_version="abc",
    )


def blocked(prepared: Any) -> Any:
    return module_artifact(
        prepared,
        outcome=ModuleOutcomeKind.BLOCKED,
        draft=None,
        violations=(Violation(ViolationCode.UNCITED_NUMBER, "summary", "55 is not backed"),),
        calls=(call(1), call(2), call(3)),
        produced_by=PRODUCED,
        runtime_version="abc",
    )


# --- sources --------------------------------------------------------------------------------


def test_sources_are_the_runs_own_artifacts_checked_against_each_other(world: World) -> None:
    run_id = world.start()
    world.upstream()
    sources = world.sources(run_id)
    assert sources.run_id == run_id
    assert sources.research_questions == ("Co lidé ráno pijí?",)
    assert sources.dataset_origin is DataOrigin.SYNTHETIC_FIXTURE
    assert sources.fieldwork_source == "synthetic_fixture"
    assert sources.refs.specification_fingerprint == sources.specification.fingerprint()
    material = dataset_material(world.session, world.scope, world.store, sources)
    assert material.respondents_fictional
    assert material.lineage is not None and material.lineage.datasets == {SYNTHETIC_FIXTURE_DATASET}


def test_a_run_whose_upstream_has_not_finished_has_no_sources(world: World) -> None:
    run_id = world.start()
    world.upstream(stop_before="research_aggregate")
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == "missing_upstream"


def test_an_aggregate_that_does_not_record_the_runs_dataset_is_refused(world: World) -> None:
    run_id = world.start()
    world.upstream(lineage=False)
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == "aggregate_lineage"


def test_a_source_of_the_wrong_type_is_refused(world: World) -> None:
    run_id = world.start()
    world.upstream()
    run = world.run(run_id)
    for step in run["steps"]:
        if step["node_key"] == "aggregate":
            step["output"] = {
                "artifact_id": next(
                    s["output"]["artifact_id"] for s in run["steps"] if s["node_key"] == "run"
                )
            }
    with pytest.raises(SourcesRefused) as refused:
        native_sources(world.session, world.scope, world.store, run)
    assert refused.value.reason == "source_type"


# --- preparation ----------------------------------------------------------------------------


def test_preparation_is_deterministic_and_fingerprints_what_validity_rests_on(
    world: World,
) -> None:
    run_id = world.start()
    world.upstream()
    sources = world.sources(run_id)
    module = AnalysisModuleId.EXECUTIVE
    a = prepare_module(sources, module_id=module, surface=INTERNAL, language="cs")
    b = prepare_module(sources, module_id=module, surface=INTERNAL, language="cs")
    assert (a.module_fingerprint, a.reuse_fingerprint) == (
        b.module_fingerprint,
        b.reuse_fingerprint,
    )
    assert a.preflight == () and a.inputs.table.rows
    variants = [
        prepare_module(
            dataclasses.replace(sources, research_questions=("Jiná otázka?",)),
            module_id=module,
            surface=INTERNAL,
            language="cs",
        ),
        prepare_module(sources, module_id=module, surface=INTERNAL, language="en"),
        prepare_module(
            sources, module_id=AnalysisModuleId.OBJECTS, surface=INTERNAL, language="cs"
        ),
        prepare_module(sources, module_id=module, surface=INTERNAL, language="cs", max_repairs=1),
    ]
    assert len({v.reuse_fingerprint for v in variants} | {a.reuse_fingerprint}) == 5
    client = prepare_module(
        sources, module_id=module, surface=ClaimSurface.CLIENT_FACING, language="cs"
    )
    assert {v.code for v in client.preflight} >= {
        ViolationCode.SYNTHETIC_DATA_ORIGIN,
        ViolationCode.FIELD_INTERNAL_ONLY,
        ViolationCode.JOINT_CERTIFICATE_DEGRADED,
    }


# --- reconstruction -------------------------------------------------------------------------


def test_a_completed_outcome_comes_back_with_claims_the_gate_just_minted(world: World) -> None:
    run_id = world.start()
    world.upstream()
    stored = world.store_outcomes(run_id, completed)
    back = reconstruct_module(
        world.session, world.scope, world.store, run_id=run_id, module_id=AnalysisModuleId.EXECUTIVE
    )
    assert back.outcome is ModuleOutcomeKind.COMPLETED and back.violations == ()
    assert back.artifact_id == stored["executive"]
    assert back.result is not None
    claims = back.result.claims
    assert [c.claim_id for c in claims] == ["c1"] and all(
        isinstance(c, AdmittedClaim) for c in claims
    )
    assert claims[0].row is back.inputs.table.rows["q1.mean"]
    assert back.result.surface is INTERNAL
    assert back.result.method_status.startswith("synthetic/modelled research")
    assert back.record.labels.internal_only and back.record.labels.simulated_respondents


def test_a_whole_run_reads_back_and_is_complete_only_with_eight_completed(world: World) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed, count=7)
    partial = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert len(partial.modules) == 7 and len(partial.pending) == 1
    assert list(partial.pending.values()) == ["RUNNABLE"]
    assert not partial.complete
    world.store_outcomes(run_id, completed, count=1)
    whole = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert whole.complete and list(whole.modules) == list(AnalysisModuleId)


def test_a_blocked_outcome_comes_back_with_its_violations_and_no_result(world: World) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, blocked)
    back = reconstruct_module(
        world.session, world.scope, world.store, run_id=run_id, module_id=AnalysisModuleId.OBJECTS
    )
    assert back.outcome is ModuleOutcomeKind.BLOCKED and back.result is None
    assert [v.code for v in back.violations] == [ViolationCode.UNCITED_NUMBER]
    assert not reconstruct_run(world.session, world.scope, world.store, run_id=run_id).complete


def invented(prepared: Any) -> Any:
    """A 'completed' record whose draft the gate refuses: a value that is not the row's."""
    draft = good_draft(prepared)
    draft["numeric_claims"][0]["value"] = 4.99
    draft["summary"] = "Fiktivní respondenti pijí kávu v průměru 4,99 bodu."
    draft["key_findings"] = [{"text": "Průměr je 4,99.", "claim_ids": ["c1"]}]
    draft["research_question_answers"] = [
        {**a, "answer": "Průměr je 4,99 bodu."} for a in draft["research_question_answers"]
    ]
    return module_artifact(
        prepared,
        outcome=ModuleOutcomeKind.COMPLETED,
        draft=draft,
        violations=(),
        calls=(call(),),
        produced_by=PRODUCED,
        runtime_version=None,
    )


def stale(prepared: Any) -> Any:
    """A record judged on other research questions than the run's design states."""
    other = dataclasses.replace(prepared.sources, research_questions=("Jiná otázka?",))
    return completed(
        prepare_module(other, module_id=prepared.module_id, surface=INTERNAL, language="cs")
    )


def moved(prepared: Any) -> Any:
    record = completed(prepared).model_dump(mode="json")
    record["sources"]["aggregate"]["sha256"] = "e" * 64
    return parse_module_artifact(record)


def extra_key(prepared: Any) -> Any:
    return {**completed(prepared).model_dump(mode="json"), "claims": [{"value": 99}]}


@pytest.mark.parametrize(
    ("decide", "reason"),
    [
        (invented, "readmission_refused"),
        (stale, "fingerprint_mismatch"),
        (moved, "sources_moved"),
        (extra_key, "contract"),
    ],
)
def test_an_outcome_that_no_longer_holds_is_refused_not_trusted(
    world: World, decide: Any, reason: str
) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, decide)
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_module(
            world.session,
            world.scope,
            world.store,
            run_id=run_id,
            module_id=AnalysisModuleId.EXECUTIVE,
        )
    assert refused.value.reason == reason


def test_tampered_bytes_are_refused(world: World) -> None:
    run_id = world.start()
    world.upstream()
    stored = world.store_outcomes(run_id, completed)
    repo = research_artifacts(world.session, world.scope, world.store)
    artifact = repo.get(stored["executive"])
    record = json.loads(world.store.get(artifact.storage_key))
    record["draft"]["numeric_claims"][0]["value"] = 4.99
    world.store.put(artifact.storage_key, json.dumps(record).encode("utf-8"))
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_module(
            world.session,
            world.scope,
            world.store,
            run_id=run_id,
            module_id=AnalysisModuleId.EXECUTIVE,
        )
    assert refused.value.reason == "outcome_corrupt"


def test_an_outcome_is_read_only_in_its_study_and_internal_ones_by_its_researchers(
    world: World,
) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed)
    module = AnalysisModuleId.EXECUTIVE
    researcher = world.scoped.scope(user="researcher")
    assert reconstruct_module(
        world.session, researcher, world.store, run_id=run_id, module_id=module
    ).result
    for user in ("viewer", "reviewer"):
        with pytest.raises(ScopeDenied):
            reconstruct_module(
                world.session,
                world.scoped.scope(user=user),
                world.store,
                run_id=run_id,
                module_id=module,
            )
    other = world.scoped.scope(user="other_lead", study="other_client")
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_module(world.session, other, world.store, run_id=run_id, module_id=module)
    assert refused.value.reason == "run_not_found"


def test_a_module_with_no_stored_outcome_says_so(world: World) -> None:
    run_id = world.start()
    world.upstream()
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_module(
            world.session,
            world.scope,
            world.store,
            run_id=run_id,
            module_id=AnalysisModuleId.EXECUTIVE,
        )
    assert refused.value.reason == "no_outcome"
    empty = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert empty.modules == {} and len(empty.pending) == 8 and not empty.complete
