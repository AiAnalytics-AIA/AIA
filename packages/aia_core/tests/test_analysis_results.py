"""A native run's analysis in the application layer: sources, preparation, reconstruction.

The upstream steps are driven through the real workflow repository, and outcomes are
stored with the one builder the executor uses; nothing here trusts a stored number.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from aia_core.application import analysis_results
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
    stored_analysis,
)
from aia_core.application.report import ReportCompositionRefused, compose_internal_report
from aia_core.application.report_design import compose_design_sections
from aia_core.application.report_method import compose_method_section
from aia_core.application.report_tables import compose_question_tables, scale_notes
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    CallRecord,
    ProducedBy,
    parse_module_artifact,
)
from aia_core.domain.analysis.native import NativeEvidenceRefused, native_evidence, native_items
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
from aia_core.domain.evidence.instrument import instrument_policy_book
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, REFERENCE_THRESHOLDS
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource
from aia_core.domain.licence_determinations import SYNTHETIC_FIXTURE_DATASET
from aia_core.domain.pipeline import ProjectType, fingerprint
from aia_core.domain.report.model import (
    AuditBlock,
    BulletList,
    Callout,
    Classification,
    NumberCell,
    Paragraph,
    ParagraphRole,
    ReportKind,
    ReportMeta,
    Section,
    Table,
    Text,
    TextCell,
    text,
)
from aia_core.domain.report.validation import cited_refs
from aia_core.domain.research_aggregate import AIA_AGGREGATE_V1, aggregate_dataset
from aia_core.domain.research_design import (
    AIA_READINESS_V1,
    ResearchSpecification,
    compile_design,
)
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.domain.workflow_templates import RESEARCH, steps_for_workflow
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ProjectArtifactRow
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
        revision, _ = designs.submit_as_working_copy(content=design, source_stage="run")
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

    def upstream(
        self,
        *,
        lineage: bool = True,
        stop_before: str | None = None,
        spec_revision: str | None = None,
        spec_design: dict[str, Any] | None = None,
        reused: dict[str, str] | None = None,
        payloads: dict[str, Any] | None = None,
    ) -> None:
        """compile, preflight, run and aggregate, as their executors store them.

        ``spec_revision`` names the revision the specification records, as when the
        compile step reused the artifact of an earlier revision; ``spec_design`` is the
        content it is compiled from, and the fieldwork and aggregate built around, when
        that is not the revision it records; ``reused`` maps a step kind to an earlier
        run's artifact that step reuses instead of storing one; ``payloads`` replaces
        what ``compile`` or ``aggregate`` stores with exactly that JSON.
        """
        latest = StudyDesignRepository(self.session, self.scope).latest()
        assert latest is not None
        revision_id = latest.revision_id
        content = StudyDesignRepository(self.session, self.scope).content(revision_id)
        spec, _ = compile_design(spec_design if spec_design is not None else content)
        stored = payloads or {}
        assert spec is not None
        dataset = synthetic_dataset(spec, seed=20260816)
        ids: dict[str, str] = {}

        def compile_(work: Any) -> str:
            ids["spec"] = self.put(
                work,
                stored.get(
                    "compile",
                    {
                        "kind": SPECIFICATION_ARTIFACT,
                        "design_revision_id": spec_revision or revision_id,
                        "specification": spec.model_dump(mode="json"),
                        "specification_fingerprint": spec.fingerprint(),
                    },
                ),
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
                stored.get(
                    "aggregate",
                    {
                        "kind": AGGREGATE_ARTIFACT,
                        "aggregate": aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1),
                    },
                ),
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
            if reused and kind in reused:
                self._complete(kind, lambda w, found=reused[kind]: found)
            else:
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


def test_a_specification_reused_from_an_identical_revision_is_the_runs_own(
    world: World,
) -> None:
    """The compile step keys its artifact on the design's content, so a design edited and
    edited back runs on the earlier revision's specification. It is the run's own."""
    designs = StudyDesignRepository(world.session, world.scope)
    first, _ = designs.submit_as_working_copy(content=DESIGN, source_stage="run")
    designs.submit_as_working_copy(content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run")
    run_id = world.start()  # the same content again: a third revision
    world.upstream(spec_revision=first.revision_id)
    run_revision = world.run(run_id)["metadata"]["design_revision_id"]
    assert run_revision != first.revision_id
    assert world.sources(run_id).refs.design_revision_id == run_revision


def _outputs(world: World, run_id: str) -> dict[str, str]:
    return {
        s["node_key"]: s["output"]["artifact_id"]
        for s in world.run(run_id)["steps"]
        if (s.get("output") or {}).get("artifact_id")
    }


def test_an_aggregate_reused_over_the_same_questionnaire_is_the_runs_own(world: World) -> None:
    """Editing only the research questions compiles to the same specification, so the
    fieldwork and aggregate steps reuse the earlier run's artifacts, which record the
    earlier specification artifact."""
    first = world.start()
    world.upstream()
    earlier = _outputs(world, first)
    second = world.start({**DESIGN, "research_plan": {"research_questions": ["Jiná otázka?"]}})
    world.upstream(
        reused={"research_fieldwork": earlier["run"], "research_aggregate": earlier["aggregate"]}
    )
    sources = world.sources(second)
    assert sources.refs.aggregate.artifact_id == earlier["aggregate"]
    assert sources.refs.specification.artifact_id != earlier["compile"]
    assert sources.research_questions == ("Jiná otázka?",)


def test_an_aggregate_of_another_questionnaire_is_refused(world: World) -> None:
    first = world.start()
    world.upstream()
    earlier = _outputs(world, first)
    second = world.start({**DESIGN, "title": "Jiný dotazník"})  # another specification
    world.upstream(
        reused={"research_fieldwork": earlier["run"], "research_aggregate": earlier["aggregate"]}
    )
    with pytest.raises(SourcesRefused) as refused:
        world.sources(second)
    assert refused.value.reason == "aggregate_lineage"


def test_a_specification_of_another_design_is_refused(world: World) -> None:
    designs = StudyDesignRepository(world.session, world.scope)
    other, _ = designs.submit_as_working_copy(
        content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run"
    )
    run_id = world.start()
    world.upstream(spec_revision=other.revision_id)
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == "design_revision"
    world_run = world.run(run_id)
    world_run["metadata"] = {**world_run["metadata"], "design_revision_id": "REV-not-here"}
    with pytest.raises(SourcesRefused) as unknown:
        native_sources(world.session, world.scope, world.store, world_run)
    assert unknown.value.reason == "design_revision"


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


def test_a_specification_compiled_from_other_content_is_refused_whatever_it_records(
    world: World,
) -> None:
    """The specification is checked against the revision itself, not only against the
    revision it names: compiled from another questionnaire, with the fieldwork and the
    aggregate built around it, it is not this run's although it says it is."""
    run_id = world.start()
    first_question = DESIGN["sections"][0]["questions"][0]
    world.upstream(
        spec_design={**DESIGN, "sections": [{"type": "questions", "questions": [first_question]}]}
    )
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == "design_revision"


def test_the_specification_is_recompiled_under_the_readiness_limits_the_run_pinned(
    world: World,
) -> None:
    """A run compiles under the readiness limits it pinned (plan methodology-tab V1a), so its
    specification is checked by compiling under the same limits: under limits its sets do not
    keep it is not the revision compiled, and a pin that does not read is refused by name."""
    battery = {
        "type": "object_battery",
        "title": "Nápoje",
        "object_family": "nápoje",
        "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
        "scale": [1, 10],
    }
    run_id = world.start({**DESIGN, "sections": [*DESIGN["sections"], battery]})
    world.upstream()
    assert world.sources(run_id).refs.design_revision_id
    run = world.run(run_id)
    narrow = AIA_READINESS_V1.model_dump(mode="json")
    narrow["tracked_set"] = {"min": 3, "max": 4, "recommended_min": 3, "recommended_max": 4}
    for pin, reason in ((narrow, "design_revision"), ({"sample_size": {}}, "readiness_pin")):
        run["metadata"] = {**run["metadata"], "readiness": pin}
        with pytest.raises(SourcesRefused) as refused:
            native_sources(world.session, world.scope, world.store, run)
        assert refused.value.reason == reason


@pytest.mark.parametrize("names_the_run", [True, False], ids=["the-run", "another"])
def test_another_compilers_specification_is_held_to_the_revision_it_records(
    world: World, names_the_run: bool
) -> None:
    """This system cannot recompile what another compiler produced, and a run parked
    across a deploy must still be analysed: such a specification is held to the revision
    it records, which must be the run's (or an identical one's) as for any other."""
    designs = StudyDesignRepository(world.session, world.scope)
    other, _ = designs.submit_as_working_copy(
        content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run"
    )
    run_id = world.start()
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    older = spec.model_copy(update={"compiler_version": "aia-research-compile-0"})
    run_revision = world.run(run_id)["metadata"]["design_revision_id"]
    world.upstream(
        payloads={
            "compile": {
                "kind": SPECIFICATION_ARTIFACT,
                "design_revision_id": run_revision if names_the_run else other.revision_id,
                "specification": older.model_dump(mode="json"),
                "specification_fingerprint": older.fingerprint(),
            }
        }
    )
    if names_the_run:
        assert world.sources(run_id).specification.compiler_version == "aia-research-compile-0"
    else:
        with pytest.raises(SourcesRefused) as refused:
            world.sources(run_id)
        assert refused.value.reason == "design_revision"


def test_a_run_stored_before_scale_labels_compiled_reads_as_stored(world: World) -> None:
    """input-interactions 3b: a run of a labelled design whose compile step stored the develop
    specification (compile-1, no scale_labels) is read, reconstructed and reported as stored --
    never recompiled under compile-2 and refused for the fingerprint the labels moved."""
    labelled = copy.deepcopy(DESIGN)
    labelled["sections"][0]["questions"][0]["popisky_skaly"] = ["vůbec", "zcela"]
    run_id = world.start(labelled)
    spec, _ = compile_design(labelled)
    assert spec is not None and spec.questions[0].scale_labels == ("vůbec", "zcela")
    body = spec.model_dump(mode="json")
    body["compiler_version"] = "aia-research-compile-1"
    for question in body["questions"]:
        del question["scale_labels"]
    develop = ResearchSpecification.model_validate(body)
    assert develop.fingerprint() != spec.fingerprint()
    world.upstream(
        payloads={
            "compile": {
                "kind": SPECIFICATION_ARTIFACT,
                "design_revision_id": world.run(run_id)["metadata"]["design_revision_id"],
                "specification": body,
                "specification_fingerprint": develop.fingerprint(),
            }
        }
    )
    sources = world.sources(run_id)
    assert sources.specification.compiler_version == "aia-research-compile-1"
    assert sources.specification.questions[0].scale_labels == ()
    world.store_outcomes(run_id, completed)
    run = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert len(run.modules) == len(ANALYSIS_MODULES)
    stored = stored_analysis(world.session, world.scope, world.store, run_id=run_id)
    assert set(stored.records) == set(run.modules)
    tables = compose_question_tables(
        run,
        native_items(sources.specification),
        source="Zmrazený běh",
        scales=scale_notes(sources.specification),
    )
    (chapter,) = tables.sections
    assert all(t.notes == () for t in chapter.blocks if isinstance(t, Table))


@pytest.mark.parametrize(
    ("step", "payload", "reason"),
    [
        ("compile", ["kind", SPECIFICATION_ARTIFACT], "specification_shape"),
        (
            "compile",
            {"kind": SPECIFICATION_ARTIFACT, "specification": {"title": "Jiný tvar"}},
            "specification_shape",
        ),
        ("aggregate", ["kind", AGGREGATE_ARTIFACT], "aggregate_shape"),
    ],
    ids=["specification-not-an-object", "specification-unreadable", "aggregate-not-an-object"],
)
def test_a_source_of_another_shape_is_refused_not_raised(
    world: World, step: str, payload: Any, reason: str
) -> None:
    """Hash-valid JSON of another shape -- an older producer's artifact, say -- is a
    refusal with a reason, never an AttributeError or a validation error."""
    run_id = world.start()
    world.upstream(payloads={step: payload})
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == reason


def _damage(world: World, artifact_id: str, how: str) -> str:
    """Tamper with an artifact's bytes, or remove its object. Returns its storage key."""
    key = research_artifacts(world.session, world.scope, world.store).get(artifact_id).storage_key
    if how == "tampered":
        world.store.put(key, b'{"kind": "tampered"}')
    else:
        world.store.delete(key)
    return key


@pytest.mark.parametrize("how", ["tampered", "missing"])
@pytest.mark.parametrize("node", ["compile", "aggregate"])
def test_a_corrupt_source_is_refused_by_reason_without_its_storage_key(
    world: World, node: str, how: str
) -> None:
    """Bytes that fail their hash, or an object that is gone: refused by reason, and the
    message carries no storage key, since it reaches a step's error and a reader."""
    run_id = world.start()
    world.upstream()
    key = _damage(world, _outputs(world, run_id)[node], how)
    with pytest.raises(SourcesRefused) as refused:
        world.sources(run_id)
    assert refused.value.reason == "source_corrupt"
    assert key not in str(refused.value)


@pytest.mark.parametrize("how", ["tampered", "missing"])
def test_a_corrupt_ai_dataset_is_refused_by_reason_not_raised(world: World, how: str) -> None:
    """An AI runtime dataset is read for its lineage. Bytes that fail their hash are a
    refusal by reason like any other source's, not a storage error: an executor returns
    it from inside its transaction, which then keeps the CORRUPT mark (OI-77)."""
    run_id = world.start()
    world.upstream()
    sources = dataclasses.replace(
        world.sources(run_id), fieldwork_source=FieldworkSource.AI_RUNTIME.value
    )
    key = _damage(world, sources.refs.dataset.artifact_id, how)
    with pytest.raises(SourcesRefused) as refused:
        dataset_material(world.session, world.scope, world.store, sources)
    assert refused.value.reason == "source_corrupt"
    assert key not in str(refused.value)


def test_an_earlier_specification_of_another_shape_is_not_the_runs(world: World) -> None:
    """An aggregate reused from an earlier run is the run's own only through a
    specification of the run's fingerprint; one that cannot be read is not one."""
    first = world.start()
    world.upstream(payloads={"compile": ["kind", SPECIFICATION_ARTIFACT]})
    earlier = _outputs(world, first)
    second = world.start({**DESIGN, "research_plan": {"research_questions": ["Jiná otázka?"]}})
    world.upstream(
        reused={"research_fieldwork": earlier["run"], "research_aggregate": earlier["aggregate"]}
    )
    with pytest.raises(SourcesRefused) as refused:
        world.sources(second)
    assert refused.value.reason == "aggregate_lineage"


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


def test_reconstructed_analysis_composes_an_internal_branded_draft(
    world: World, tmp_path: Path
) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed, count=7)
    incomplete = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    with pytest.raises(ReportCompositionRefused, match="all eight"):
        compose_internal_report(
            incomplete, report_meta("synthetic/modelled research; holdout pending")
        )

    world.store_outcomes(run_id, completed, count=1)
    run = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    first = run.modules[AnalysisModuleId.EXECUTIVE].result
    assert first is not None
    doc = compose_internal_report(run, report_meta(first.method_status))
    assert len(doc.sections) == 12  # Introduction, methods, eight modules, evidence, audit.
    assert doc.sections[0].id == "intro"
    ids = [s.id for s in doc.sections]
    assert ids.index("methodology") < ids.index("ch-4") < ids.index("ch-3")
    # Every admitted authored paragraph survives the new academic order.
    for spec in ANALYSIS_MODULES:
        result = run.modules[spec.module_id].result
        assert result is not None
        section = next(s for s in doc.sections if s.id == f"ch-{spec.ordinal}")
        rendered_text = "\n".join(
            "".join(i.text for i in b.content if isinstance(i, Text))
            for b in section.blocks
            if isinstance(b, Paragraph)
        )
        assert result.summary in rendered_text
        for answer in result.research_question_answers:
            assert answer.question in rendered_text and answer.answer in rendered_text
        for finding in result.key_findings:
            assert finding.text in rendered_text
    intro = doc.sections[0].blocks
    assert isinstance(intro[0], Paragraph) and intro[0].role is ParagraphRole.LEDE
    assert "Ranní nápoj" in "".join(i.text for i in intro[0].content if isinstance(i, Text))
    assert any(isinstance(b, BulletList) for b in intro)
    assert any(isinstance(b, Callout) and b.title == "Rámec interpretace" for b in intro)
    # 18.6.6's own aggregation: no deviation is claimed anywhere (G3c).
    assert run.aggregation_deviation is None
    assert not any(isinstance(b, Callout) and b.title == "Odchylka od 18.6.6" for b in intro)
    assert "q1.mean" in cited_refs(doc)
    assert doc.ledger.surface is ClaimSurface.INTERNAL
    assert doc.sections[-1].appendix
    rendered = DocxRenderer().render(doc)
    assert not lint_docx(rendered)
    (tmp_path / "internal-report.docx").write_bytes(rendered)

    with pytest.raises(ReportCompositionRefused, match="unapproved internal"):
        compose_internal_report(
            run,
            dataclasses.replace(
                report_meta(first.method_status),
                kind=ReportKind.CLIENT,
                classification=Classification.CLIENT_CONFIDENTIAL,
            ),
        )
    with pytest.raises(ReportCompositionRefused, match="method status"):
        compose_internal_report(run, report_meta("holdout_validated"))

    bad = dataclasses.replace(
        run.modules[AnalysisModuleId.AUDIENCE].inputs, surface=ClaimSurface.CLIENT_FACING
    )
    modules = dict(run.modules)
    modules[AnalysisModuleId.AUDIENCE] = dataclasses.replace(
        modules[AnalysisModuleId.AUDIENCE], inputs=bad
    )
    with pytest.raises(ReportCompositionRefused, match="internal admission"):
        compose_internal_report(
            dataclasses.replace(run, modules=modules), report_meta(first.method_status)
        )


def _callout_texts(blocks: Any) -> list[str]:
    return [
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in blocks
        if isinstance(b, Callout)
    ]


def _paragraph_texts(blocks: Any) -> str:
    return "\n".join(
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in blocks
        if isinstance(b, Paragraph)
    )


def test_a_modelled_run_is_framed_as_modelled_in_the_introduction_and_the_limits(
    world: World,
) -> None:
    """ADR 0024 §7: the report says "modelováno: AI respondenti z populace", never synthetic,
    and never leaves a modelled run unframed as plain research."""
    from aia_core.application.report import RESEARCH_SUBTITLE
    from aia_core.domain.fieldwork import OriginKind

    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed, count=8)
    run = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    first = run.modules[AnalysisModuleId.EXECUTIVE].result
    assert first is not None
    modules = {}
    for module_id, module in run.modules.items():
        labels = module.record.labels.model_copy(
            update={
                "data_origin": DataOrigin.MODELLED_AI_PANEL,
                "simulated_respondents": False,
                "modelled_respondents": True,
            }
        )
        record = module.record.model_copy(update={"labels": labels})
        modules[module_id] = dataclasses.replace(module, record=record)
    doc = compose_internal_report(
        dataclasses.replace(run, modules=modules), report_meta(first.method_status)
    )
    intro = " ".join(_callout_texts(doc.sections[0].blocks))
    assert "modelováno: AI respondenti z populace" in intro
    assert "syntetičtí" not in intro
    limits = " ".join(_callout_texts(next(s for s in doc.sections if s.title == "Limity").blocks))
    assert "modelováno: AI respondenti z populace" in limits and "syntetičtí" not in limits
    # One meaning per word (cross-review): "návrh" is the study's design, never what is not a
    # measurement; "varianta" is the base report or the one with literature, "verze" the
    # stored version only.
    assert "Tato studie není měřením skutečných osob." in limits and "návrh" not in limits
    assert (
        "Tato varianta je základní zprávou běhu: literární rešerše není její součástí."
        in _paragraph_texts(doc.sections[0].blocks)
    )
    with_literature = compose_internal_report(
        dataclasses.replace(run, modules=modules),
        report_meta(first.method_status),
        context_sections=(
            Section(
                "Literární rešerše a externí kontext", (Paragraph(text("—")),), id="literature"
            ),
        ),
    )
    lead = _paragraph_texts(with_literature.sections[0].blocks)
    assert "Tato varianta zprávy obsahuje literární rešerši vybranou k tomuto běhu." in lead
    assert "Tato verze" not in lead + _paragraph_texts(doc.sections[0].blocks)
    assert RESEARCH_SUBTITLE[OriginKind.MODELLED] == "Modelovaný výzkum"
    assert set(RESEARCH_SUBTITLE) == set(OriginKind)


def report_meta(method_status: str) -> ReportMeta:
    return ReportMeta(
        kind=ReportKind.INTERNAL,
        title="Interní analytický přehled",
        subtitle="Syntetický výzkum",
        client_name="Fiktivní klient",
        study_name="Ranní nápoj",
        study_id="STU-test",
        issued_on=date(2026, 10, 1),
        revision=1,
        method_status=method_status,
        classification=Classification.INTERNAL,
    )


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


def renamed(prepared: Any) -> Any:
    """Sources recorded under other names and another revision, with the same content:
    an outcome reused from a run over an identical design."""
    record = completed(prepared).model_dump(mode="json")
    record["sources"]["aggregate"]["artifact_id"] = "ART-another-run"
    record["sources"]["design_revision_id"] = "REV-identical-content"
    return parse_module_artifact(record)


def test_an_outcome_over_the_same_content_reads_back_whatever_its_sources_are_called(
    world: World,
) -> None:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, renamed)
    back = reconstruct_module(
        world.session, world.scope, world.store, run_id=run_id, module_id=AnalysisModuleId.EXECUTIVE
    )
    assert back.outcome is ModuleOutcomeKind.COMPLETED and back.result is not None
    assert back.record.sources.design_revision_id == "REV-identical-content"


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


def _rewrite(world: World, artifact_id: str, payload: Any) -> None:
    """Store ``payload`` as the artifact's bytes and record their hash: valid bytes of
    another shape, as an older producer might have left them."""
    data = json.dumps(payload).encode("utf-8")
    row = world.session.get(ProjectArtifactRow, artifact_id)
    assert row is not None
    world.store.put(row.storage_key, data)
    row.sha256 = hashlib.sha256(data).hexdigest()
    row.size_bytes = len(data)
    world.session.flush()


def test_a_source_that_became_another_shape_refuses_the_reconstruction(world: World) -> None:
    """A reader gets a refusal with its reason, whatever the source's bytes became."""
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed)
    _rewrite(world, _outputs(world, run_id)["compile"], ["kind", SPECIFICATION_ARTIFACT])
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert refused.value.reason == "sources_refused"
    assert str(refused.value).startswith("specification_shape:")


def test_evidence_the_adapter_now_refuses_refuses_the_reconstruction(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same sources, read by an adapter that refuses them (a later one, say): a
    refusal with its reason, not the adapter's exception."""
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed)

    def refuse(*_: Any, **__: Any) -> Any:
        raise NativeEvidenceRefused("this adapter does not read that aggregate")

    monkeypatch.setattr(analysis_results, "native_evidence", refuse)
    with pytest.raises(ReconstructionRefused) as refused:
        reconstruct_module(
            world.session,
            world.scope,
            world.store,
            run_id=run_id,
            module_id=AnalysisModuleId.EXECUTIVE,
        )
    assert refused.value.reason == "evidence_refused"


def test_an_outcome_is_read_only_in_its_study_and_internal_ones_by_everyone_with_the_study(
    world: World,
) -> None:
    """ADR 0019: an internal outcome needs EDIT_STUDY, which every person with the study holds.

    The viewer and the reviewer were refused it, and so was a member with no grant; none is
    refused now (ADR 0019). What still bounds the read is the study: a run is found only
    through the study it belongs to.
    """
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed)
    module = AnalysisModuleId.EXECUTIVE
    researcher = world.scoped.scope(user="researcher")
    expected = reconstruct_module(
        world.session, researcher, world.store, run_id=run_id, module_id=module
    ).result
    assert expected
    for user in ("viewer", "reviewer", "outsider"):
        read = reconstruct_module(
            world.session,
            world.scoped.scope(user=user),
            world.store,
            run_id=run_id,
            module_id=module,
        )
        assert read.result == expected, user
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


def test_report_preserves_admitted_paragraphs_without_rewriting_claims(world: World) -> None:
    run_id = world.start()
    world.upstream()

    def paragraphs(prepared: Any) -> Any:
        draft = good_draft(prepared)
        draft["summary"] += "\n\nDalší krok je ověřit výsledky v reálném výzkumu."
        return module_artifact(
            prepared,
            outcome=ModuleOutcomeKind.COMPLETED,
            draft=draft,
            violations=(),
            calls=(call(),),
            produced_by=PRODUCED,
            runtime_version="abc",
        )

    world.store_outcomes(run_id, paragraphs)
    run = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    executive = run.modules[AnalysisModuleId.EXECUTIVE].result
    assert executive is not None
    doc = compose_internal_report(run, report_meta(executive.method_status))
    for section in (s for s in doc.sections if s.id and s.id.startswith("ch-")):
        first, second = section.blocks[:2]
        assert isinstance(first, Paragraph) and first.role is ParagraphRole.BODY
        assert isinstance(second, Paragraph) and second.role is ParagraphRole.BODY
        assert "".join(i.text for i in second.content if isinstance(i, Text)) == (
            "Další krok je ověřit výsledky v reálném výzkumu."
        )
    assert "q1.mean" in cited_refs(doc)
    assert doc.ledger.surface is ClaimSurface.INTERNAL


def test_a_runs_pinned_support_rules_reach_its_analysis(world: World) -> None:
    """Plan methodology-tab G1c: analysis gates by the rule the run pinned."""
    run_id = world.start()
    world.upstream()
    assert world.sources(run_id).support == AIA_SUPPORT_V1
    edited = AIA_SUPPORT_V1.model_copy(
        update={
            "methodology_version": "aia-support-1+e1",
            "analysis": AIA_SUPPORT_V1.analysis.model_copy(update={"min_cell": 7}),
        }
    )
    pinned = world.run(run_id)
    pinned["metadata"] = {**pinned["metadata"], "support": edited.model_dump(mode="json")}
    assert native_sources(world.session, world.scope, world.store, pinned).support == edited
    unpinned = world.run(run_id)
    unpinned["metadata"] = {k: v for k, v in unpinned["metadata"].items() if k != "support"}
    # A run started before support was pinned was computed under aia-support-1.
    assert native_sources(world.session, world.scope, world.store, unpinned).support == (
        AIA_SUPPORT_V1
    )


def test_a_support_pin_that_does_not_read_is_refused_by_name(world: World) -> None:
    run_id = world.start()
    world.upstream()
    broken = world.run(run_id)
    broken["metadata"] = {**broken["metadata"], "support": {"methodology_version": "x"}}
    with pytest.raises(SourcesRefused) as refused:
        native_sources(world.session, world.scope, world.store, broken)
    assert refused.value.reason == "support_pin"


def _text(blocks: Any) -> str:
    return "\n".join(
        "".join(i.text for i in b.content if isinstance(i, Text))
        for b in blocks
        if isinstance(b, (Paragraph, Callout))
    )


def test_an_aggregate_that_is_not_the_units_port_says_so_in_analysis_and_the_report(
    world: World,
) -> None:
    """Plan methodology-tab G3c: the deviation the aggregate records reaches the analysis
    (its system fingerprint, so no validation of the unit's method vouches for it) and the
    internal report (introduction, methodology, limitations, audit)."""
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    dataset = synthetic_dataset(spec, seed=20260816)
    method = AIA_AGGREGATE_V1.model_copy(
        update={"methodology_version": "aia-aggregate-1+e1", "top_box": 1}
    )
    deviating = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1, method=method)
    unit = aggregate_dataset(spec, dataset, support=AIA_SUPPORT_V1)
    assert deviating["deviation"]["changed"] == [{"path": "top_box", "unit": 2, "used": 1}]

    # The fingerprint moves with the method, and only with it.
    args: dict[str, Any] = {
        "dataset_sha256": "d" * 64,
        "origin": dataset.origin,
        "support": REFERENCE_THRESHOLDS,
    }
    assert (
        native_evidence(spec, deviating, **args).system_fingerprint
        != native_evidence(spec, unit, **args).system_fingerprint
    )
    with pytest.raises(NativeEvidenceRefused, match="deviation"):
        native_evidence(spec, {**unit, "deviation": "garbled"}, **args)

    run_id = world.start()
    world.upstream(payloads={"aggregate": {"kind": AGGREGATE_ARTIFACT, "aggregate": deviating}})
    world.store_outcomes(run_id, completed, count=8)
    run = reconstruct_run(world.session, world.scope, world.store, run_id=run_id)
    assert run.complete and run.aggregation_deviation == deviating["deviation"]

    first = run.modules[AnalysisModuleId.EXECUTIVE].result
    assert first is not None
    doc = compose_internal_report(run, report_meta(first.method_status))
    sections = {s.id: s for s in doc.sections}
    intro = sections["intro"].blocks
    assert any(isinstance(b, Callout) and b.title == "Odchylka od 18.6.6" for b in intro)
    methodology = _text(sections["methodology"].blocks)
    assert "aia-aggregate-1+e1" in methodology and "top_box (18.6.6: 2, zde 1)" in methodology
    ordinal = next(
        m.ordinal for m in ANALYSIS_MODULES if m.module_id is AnalysisModuleId.LIMITATIONS
    )
    limitations = sections[f"ch-{ordinal}"]
    assert "odchyluje od přenosu 18.6.6" in _text(limitations.blocks)
    audit = next(b for b in sections["app-audit"].blocks if isinstance(b, AuditBlock))
    assert ("Metodika agregace", "aia-aggregate-1+e1") in audit.entries
    assert not lint_docx(DocxRenderer().render(doc))


def test_a_modelled_dataset_names_its_respondent_system_and_a_bad_record_is_refused() -> None:
    """The dataset's recorded respondent system (ADR 0024 §4) is read for a modelled origin only,
    fingerprinted, and refused when it does not fingerprint -- never read as no system."""
    from aia_core.application.analysis_results import SourcesRefused, _respondent_system
    from aia_core.domain.evidence import respondent_system_fingerprint
    from aia_core.domain.fieldwork import RESPONDENT_SYSTEM_METADATA

    system = {
        "respondent_prompt_sha256": "a" * 64,
        "persona_builder": "aia-panel-persona-source-1",
        "persona_mode": "calibrated",
        "sampler_version": "aia-panel-sample-1",
        "population_version": "v17_4_0",
        "model_binding": "bedrock/bedrock-eu-primary",
        "response_process_version": "aia-response-process-1",
    }
    meta = {RESPONDENT_SYSTEM_METADATA: system}
    modelled = DataOrigin.MODELLED_AI_PANEL
    assert _respondent_system(modelled, meta) == respondent_system_fingerprint(system)
    assert _respondent_system(modelled, {}) is None
    # A simulated dataset is never validated: whatever it recorded, it names no system.
    assert _respondent_system(DataOrigin.SYNTHETIC_AI_FICTIONAL, meta) is None
    for bad in ({**system, "persona_mode": ""}, {**system, "seed": "7"}, ["x"], {"a": 1}):
        with pytest.raises(SourcesRefused, match="respondent"):
            _respondent_system(modelled, {RESPONDENT_SYSTEM_METADATA: bad})


def _question_tables_run(world: World) -> Any:
    run_id = world.start()
    world.upstream()
    world.store_outcomes(run_id, completed)
    return reconstruct_run(world.session, world.scope, world.store, run_id=run_id)


def test_every_question_prints_its_numbers_through_admission_after_the_methodology(
    world: World, tmp_path: Path
) -> None:
    """complete-study-report B1a: a table per question, each cell an admitted ref."""
    run = _question_tables_run(world)
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    items = native_items(spec)
    tables = compose_question_tables(run, items, source="Zmrazený běh")
    table = run.modules[AnalysisModuleId.EXECUTIVE].inputs.table
    assert tables.refused == ()
    # Every kept row of the run's evidence is admitted once, and nothing else is.
    assert sorted(c.row.evidence_ref for c in tables.claims) == sorted(table.rows)
    assert all(c.surface is ClaimSurface.INTERNAL for c in tables.claims)
    (chapter,) = tables.sections
    printed = [b for b in chapter.blocks if isinstance(b, Table)]
    assert [t.title for t in printed] == [
        i.text
        for i in items
        if any(r.startswith(f"{i.question_id}.") for r in (*table.rows, *table.suppressed))
    ]
    # Estimates first, then the counts behind them, the same in every table.
    for t in printed:
        labels = [r.cells[0].text for r in t.rows if isinstance(r.cells[0], TextCell)]
        assert labels[-2:] == ["platné odpovědi", "efektivní n"]
    for t in printed:
        for row in t.rows:
            (label, value) = row.cells
            assert isinstance(label, TextCell) and label.text
            # A number is a ref, never text: suppression and intervals stay the ledger's.
            assert isinstance(value, NumberCell) and value.with_interval

    # Without scale notes no table carries one; with them a scale item's table names its
    # labelled points beside its values (input-interactions 3b).
    assert all(t.notes == () for t in printed)
    labelled = copy.deepcopy(DESIGN)
    labelled["sections"][0]["questions"][0]["popisky_skaly"] = ["nikdy", "denně"]
    labelled_spec, _ = compile_design(labelled)
    assert labelled_spec is not None
    notes = scale_notes(labelled_spec)
    assert notes == {"q1": "Škála: 1 = nikdy, 5 = denně."}
    tables = compose_question_tables(run, items, source="Zmrazený běh", scales=notes)
    (chapter,) = tables.sections
    by_title = {t.title: t for t in chapter.blocks if isinstance(t, Table)}
    noted = {i.text: notes[i.question_id] for i in items if i.question_id in notes}
    assert noted and all(
        by_title[title].notes == (note,) for title, note in noted.items() if title in by_title
    )

    first = run.modules[AnalysisModuleId.EXECUTIVE].result
    assert first is not None
    doc = compose_internal_report(run, report_meta(first.method_status), question_tables=tables)
    ids = [s.id for s in doc.sections]
    assert ids.index("methodology") + 1 == ids.index("ch-questions")
    assert set(table.rows) <= set(doc.ledger.rows)
    rendered = DocxRenderer().render(doc)
    assert not lint_docx(rendered)
    (tmp_path / "internal-report-with-questions.docx").write_bytes(rendered)


def test_a_question_the_gate_refuses_is_named_and_the_others_keep_their_tables(
    world: World,
) -> None:
    run = _question_tables_run(world)
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    items = native_items(spec)
    executive = run.modules[AnalysisModuleId.EXECUTIVE]
    # A policy book that does not know the first question: its claims cannot be admitted.
    origin = executive.record.labels.data_origin
    narrower = instrument_policy_book(items[1:], origin=origin, source="test: without the first")
    modules = dict(run.modules)
    modules[AnalysisModuleId.EXECUTIVE] = dataclasses.replace(
        executive, inputs=dataclasses.replace(executive.inputs, book=narrower)
    )
    tables = compose_question_tables(
        dataclasses.replace(run, modules=modules), items, source="Zmrazený běh"
    )
    assert [qid for qid, _ in tables.refused] == [items[0].question_id]
    (chapter,) = tables.sections
    assert any(
        isinstance(b, Callout)
        and items[0].text in "".join(i.text for i in b.content if isinstance(i, Text))
        for b in chapter.blocks
    )
    assert not any(c.row.question_id == items[0].question_id for c in tables.claims)
    assert {t.title for t in chapter.blocks if isinstance(t, Table)} >= {items[1].text}


def _all_text(blocks: Any) -> str:
    """Paragraphs, callouts and every list item's words."""
    items = [
        "".join(i.text for i in item.content if isinstance(i, Text))
        for b in blocks
        if isinstance(b, BulletList)
        for item in b.items
    ]
    return "\n".join([_text(blocks), *items])


def test_the_report_states_the_design_it_ran_and_appends_its_questionnaire(
    world: World, tmp_path: Path
) -> None:
    """complete-study-report B1b: the design and questionnaire, from the run's specification."""
    run = _question_tables_run(world)
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    first = run.modules[AnalysisModuleId.EXECUTIVE]
    assert first.result is not None
    design = compose_design_sections(spec, first.inputs.research_questions)
    chapter = _all_text(design.chapter.blocks)
    for q in first.inputs.research_questions:
        assert q in chapter
    for battery in spec.batteries:
        assert battery.title in chapter
        assert all(o.label in chapter for o in battery.objects)
    appendix = _all_text(design.appendix.blocks)
    assert design.appendix.appendix
    # Every question as it was asked, with its options or its scale.
    for q in spec.questions:
        assert q.text in appendix
        assert all(option in appendix for option in q.options)

    doc = compose_internal_report(run, report_meta(first.result.method_status), design=design)
    ids = [s.id for s in doc.sections]
    assert ids[:2] == ["intro", "ch-design"]
    assert ids.index("app-questionnaire") + 1 == ids.index("app-evidence")
    rendered = DocxRenderer().render(doc)
    assert not lint_docx(rendered)
    (tmp_path / "internal-report-with-design.docx").write_bytes(rendered)


def test_who_answered_comes_after_the_methodology_and_before_the_numbers(world: World) -> None:
    """complete-study-report B1c."""
    run = _question_tables_run(world)
    spec, _ = compile_design(DESIGN)
    assert spec is not None
    first = run.modules[AnalysisModuleId.EXECUTIVE]
    assert first.result is not None
    method = compose_method_section(
        {"persona_source": "fictional_roster"}, first.record.labels.data_origin
    )
    doc = compose_internal_report(
        run,
        report_meta(first.result.method_status),
        method=method,
        question_tables=compose_question_tables(run, native_items(spec), source="Zmrazený běh"),
    )
    ids = [s.id for s in doc.sections]
    assert ids.index("methodology") + 1 == ids.index("ch-method")
    assert ids.index("ch-method") + 1 == ids.index("ch-questions")
    assert not lint_docx(DocxRenderer().render(doc))


def test_an_answer_to_a_research_question_the_run_could_not_answer_says_so_where_it_is_read(
    world: World,
) -> None:
    """research-integrity-report review 2: the run recorded the gap at start, and the report said
    so only in "Respondenti a výpočet", chapters after an answer that read as measured."""
    run = _question_tables_run(world)
    first = run.modules[AnalysisModuleId.EXECUTIVE]
    assert first.result is not None
    (question,) = first.inputs.research_questions
    method = compose_method_section({}, first.record.labels.data_origin)
    words = "běh na ni odpovědět nemohl (měří ji jen otázky, na které běh neodpoví)"

    doc = compose_internal_report(
        run,
        report_meta(first.result.method_status),
        method=method,
        research_question_gaps={f" {question}\n": words},
    )
    intro = _all_text(doc.sections[0].blocks)
    assert f"{question} (bez doložené odpovědi, viz kapitola Respondenti a výpočet)" in intro
    # Every answer to it is qualified right under the question, before it is read: why, once,
    # at the first answer; a short line at each later one (review 3: the full callout under
    # every answering module repeated one reason 16 times in the fictional render).
    qualified: list[str] = []
    answers = 0
    for section in doc.sections:
        blocks = list(section.blocks)
        for i, block in enumerate(blocks):
            if (
                isinstance(block, Paragraph)
                and "".join(t.text for t in block.content if isinstance(t, Text)) == question
                and i + 1 < len(blocks)
            ):
                answers += 1
                # The question titles its answer, so it never ends a page alone above it.
                assert block.role is ParagraphRole.LEAD_IN, section.id
                after = blocks[i + 1]
                assert isinstance(after, Callout), section.id
                qualified.append(_callout_texts([after])[0])
    assert answers > 1 and len(qualified) == answers
    assert qualified[0].startswith(f"Při spuštění běh zaznamenal: {words}.")
    assert all(q.startswith("Ani tuto odpověď nečtěte jako doloženou") for q in qualified[1:])
    assert sum(f"{words}." in q for q in qualified) == 1
    assert not lint_docx(DocxRenderer().render(doc))

    # A question the run did not record as a gap is not qualified.
    plain = compose_internal_report(
        run, report_meta(first.result.method_status), research_question_gaps={"Jiná?": words}
    )
    assert "bez doložené odpovědi" not in _all_text(plain.sections[0].blocks)
    assert not any(
        isinstance(b, Callout) and b.title == "Bez doložené odpovědi"
        for s in plain.sections
        for b in s.blocks
    )
