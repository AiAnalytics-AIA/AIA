"""A native run's analysis in the application layer: sources, preparation, reconstruction.

The upstream steps are driven through the real workflow repository, and outcomes are
stored with the one builder the executor uses; nothing here trusts a stored number.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
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
)
from aia_core.application.research import research_artifacts
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.analysis.artifact import (
    ANALYSIS_MODULE_ARTIFACT,
    CallRecord,
    ProducedBy,
    parse_module_artifact,
)
from aia_core.domain.analysis.native import NativeEvidenceRefused
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
                    {"kind": AGGREGATE_ARTIFACT, "aggregate": aggregate_dataset(spec, dataset)},
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
    first, _ = designs.submit(content=DESIGN, source_stage="run")
    designs.submit(content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run")
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
    other, _ = designs.submit(content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run")
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


@pytest.mark.parametrize("names_the_run", [True, False], ids=["the-run", "another"])
def test_another_compilers_specification_is_held_to_the_revision_it_records(
    world: World, names_the_run: bool
) -> None:
    """This system cannot recompile what another compiler produced, and a run parked
    across a deploy must still be analysed: such a specification is held to the revision
    it records, which must be the run's (or an identical one's) as for any other."""
    designs = StudyDesignRepository(world.session, world.scope)
    other, _ = designs.submit(content={**DESIGN, "title": "Jiný nápoj"}, source_stage="run")
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
