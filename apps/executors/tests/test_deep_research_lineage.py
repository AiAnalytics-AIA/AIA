"""Interpretation Research over real results: lineage, scope and the frozen engine (ADR 0021).

One world holds both kinds of run. A research run on fictional fieldwork
(``aia_executors.workbench``) produces a specification, a dataset, an aggregate and a
Sociomap; Deep Research runs over the same Design Revision with recorded retrieval. What is
pinned:

* an interpretation spec pins the exact artifacts of the result it names, by id and SHA256,
  and the Design Revision that run executed;
* a newer result is another lineage, never a silent retarget; the same target always
  freezes to the same lineage;
* a target of another Study or client, an artifact the run did not produce, an entity the
  artifact does not hold and a corrupt artifact are all refused;
* **Interpretation Research is frozen, never enqueued, until chunk 30**: the enqueue
  boundary refuses its spec, and a persisted interpretation row is never retried -- no run,
  no model or retrieval call;
* a design run and an interpretation spec share one engine identity and differ in run
  identity; provenance round-trips and resolves to the original immutable inputs; nothing
  wrote a design or a deterministic research artifact.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from aia_core.application.deep_research import (
    DeepResearchRuns,
    InterpretationNotReady,
    LineageChanged,
    ResearchTargetInvalid,
    ResearchTargetNotFound,
    governed_record,
    run_spec_metadata,
)
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.deep_research.integration import (
    DETERMINISTIC_ARTIFACT_TYPES,
    DeepResearchRunSpec,
    DesignLineage,
    InterpretationLineage,
    PurposeSource,
    ResultBatteryObjectTarget,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    SociomapTarget,
)
from aia_core.domain.deep_research.workflow import (
    ARTIFACT_TYPES,
    DEEP_RESEARCH,
    deep_research_steps,
)
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.scope import StudyStatus
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore, IntegrityError
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ProjectArtifactRow, UserRow
from aia_core.infrastructure.web_retrieval import RecordedSearch
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors import workbench
from aia_executors.deep_research import deep_research_registry
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ANSWERS,
    DESIGN_2,
    RecordedAgents,
    ResearchWorld,
    approve_knowledge,
    recorded,
    research,  # noqa: F401  (the fixture)
)

#: The journey's second-pass design, made runnable: a sample size, and the tracked set
#: (its three drinks) named and scaled.
RESULTS_DESIGN: dict[str, Any] = {
    **DESIGN_2,
    "n": 60,
    "sections": [
        DESIGN_2["sections"][0],
        {**DESIGN_2["sections"][1], "object_family": "nápoje", "scale": [1, 10]},
    ],
}
#: The same study later: a larger sample, so a newer, different result.
NEWER_DESIGN: dict[str, Any] = {**RESULTS_DESIGN, "n": 80}


@dataclass
class World:
    research: ResearchWorld
    store: InMemoryArtifactStore
    worker: Worker
    agents: RecordedAgents
    revision_id: str
    research_run_id: str
    runtime: Any

    def search_calls(self) -> list[str]:
        """Every query that reached the recorded search (a retrieval call)."""
        retrieval = self.runtime.retrieval
        assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
        return list(retrieval.search.calls)

    def runs(self, scope: Any | None = None) -> Iterator[DeepResearchRuns]:
        with self.research.sessions() as session:
            yield DeepResearchRuns(
                session, scope(session) if scope else self.research.lead_scope(session)
            )
            session.commit()

    def steps(self, run_id: str | None = None) -> dict[str, dict[str, Any]]:
        with self.research.sessions() as session:
            run = ResearchRuns(session, self.research.lead_scope(session)).get(
                run_id or self.research_run_id
            )
        return {s["node_key"]: s for s in run["steps"]}

    def artifact(self, run_id: str | None, node: str) -> str:
        return str(self.steps(run_id)[node]["output"]["artifact_id"])

    def drain(self) -> int:
        n = 0
        while self.worker.run_once() is not None:
            n += 1
        return n


def _research_run(world: ResearchWorld, content: dict[str, Any]) -> tuple[str, str]:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=content, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
        return revision.revision_id, started.run_id


@pytest.fixture
def results(research: ResearchWorld, database_url: str, build: Any) -> World:  # noqa: F811
    approve_knowledge(research)
    store = InMemoryArtifactStore()
    agents = RecordedAgents(ANSWERS)
    runtime = recorded(research, agents, contents=(RESULTS_DESIGN, NEWER_DESIGN))
    worker = Worker(
        session_factory=research.sessions,
        executors={
            **workbench.workbench_registry_for(store=store, build=build),
            **deep_research_registry(store=store, build=build, runtime=runtime),
        },
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="lineage-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )
    revision_id, run_id = _research_run(research, RESULTS_DESIGN)
    world = World(research, store, worker, agents, revision_id, run_id, runtime)
    world.drain()
    with research.sessions() as session:
        run = ResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED, run["status"]
    return world


def _sociomap_object(
    world: World, run_id: str | None = None, object_id: str | None = None
) -> SociomapObjectTarget:
    sociomap_id = world.artifact(run_id, "sociomap")
    with world.research.sessions() as session:
        payload = research_artifacts(
            session, world.research.lead_scope(session), world.store
        ).read_json(sociomap_id)
    (battery,) = payload["sociomap"]["batteries"]
    return SociomapObjectTarget(
        kind="SOCIOMAP_OBJECT",
        research_run_id=run_id or world.research_run_id,
        sociomap_artifact_id=sociomap_id,
        battery_id=battery["battery_id"],
        object_id=object_id or battery["objects"][0]["id"],
    )


def _freeze(world: World, target: Any, scope: Any | None = None) -> Any:
    for runs in world.runs(scope):
        return runs.freeze_interpretation(target=target, preset_name="QUICK", store=world.store)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- lineage


def test_interpretation_pins_the_exact_result_and_the_design_it_executed(results: World) -> None:
    target = _sociomap_object(results)
    spec = _freeze(results, target)
    lineage = spec.lineage
    assert isinstance(lineage, InterpretationLineage)
    assert lineage.research_run_id == results.research_run_id
    steps = results.steps()
    with results.research.sessions() as session:
        repo = research_artifacts(session, results.research.lead_scope(session), results.store)
        expected = {
            node: (
                steps[node]["output"]["artifact_id"],
                repo.get(steps[node]["output"]["artifact_id"]).sha256,
            )
            for node in ("aggregate", "compile", "run", "sociomap")
        }
        revision = StudyDesignRepository(session, results.research.lead_scope(session)).get(
            results.revision_id
        )
    assert {p.node_key: (p.artifact_id, p.sha256) for p in lineage.artifacts} == expected
    assert lineage.design == DesignLineage(
        kind="DESIGN",
        design_revision_id=results.revision_id,
        design_revision=revision.revision,
        design_content_sha256=revision.content_sha256,
    )
    # The engine request is the one the design side freezes over that revision: unchanged.
    for runs in results.runs():
        design = runs.freeze_design(design_revision_id=results.revision_id, preset_name="QUICK")
    assert spec.engine_request == design.engine_request
    assert spec.fingerprint() != design.fingerprint()


def test_every_result_target_resolves_to_an_entity_its_artifact_holds(results: World) -> None:
    aggregate = results.artifact(None, "aggregate")
    sociomap = _sociomap_object(results)
    with results.research.sessions() as session:
        payload = research_artifacts(
            session, results.research.lead_scope(session), results.store
        ).read_json(sociomap.sociomap_artifact_id)
    objects = [o["id"] for o in payload["sociomap"]["batteries"][0]["objects"]]
    run = results.research_run_id
    valid = [
        ResultQuestionTarget(
            kind="RESULT_QUESTION",
            research_run_id=run,
            aggregate_artifact_id=aggregate,
            question_id="q1",
        ),
        ResultBatteryObjectTarget(
            kind="RESULT_BATTERY_OBJECT",
            research_run_id=run,
            aggregate_artifact_id=aggregate,
            battery_id=sociomap.battery_id,
            object_id=objects[0],
        ),
        SociomapTarget(
            kind="SOCIOMAP",
            research_run_id=run,
            sociomap_artifact_id=sociomap.sociomap_artifact_id,
            battery_id=sociomap.battery_id,
        ),
        SociomapRelationshipTarget(
            kind="SOCIOMAP_RELATIONSHIP",
            research_run_id=run,
            sociomap_artifact_id=sociomap.sociomap_artifact_id,
            battery_id=sociomap.battery_id,
            source_object_id=objects[0],
            target_object_id=objects[1],
        ),
    ]
    fingerprints = {_freeze(results, t).fingerprint() for t in valid}
    assert len(fingerprints) == len(valid)

    missing = [
        ResultQuestionTarget(
            kind="RESULT_QUESTION",
            research_run_id=run,
            aggregate_artifact_id=aggregate,
            question_id="q99",
        ),
        sociomap.model_copy(update={"object_id": "neexistuje"}),
        sociomap.model_copy(update={"battery_id": "neexistuje"}),
    ]
    for target in missing:
        with pytest.raises(ResearchTargetInvalid):
            _freeze(results, target)


def test_an_artifact_the_run_did_not_produce_for_that_node_is_refused(results: World) -> None:
    target = _sociomap_object(results)
    # The aggregate's id named as the Sociomap: a real artifact of this run, not this node's.
    wrong = target.model_copy(update={"sociomap_artifact_id": results.artifact(None, "aggregate")})
    with pytest.raises(ResearchTargetNotFound):
        _freeze(results, wrong)
    with pytest.raises(ResearchTargetNotFound):
        _freeze(results, target.model_copy(update={"research_run_id": "RUN-0000000000000000"}))


def test_a_newer_result_is_another_lineage_never_a_silent_retarget(results: World) -> None:
    old_target = _sociomap_object(results)
    first = _freeze(results, old_target)
    # The same study produces a newer result.
    _revision, newer_run = _research_run(results.research, NEWER_DESIGN)
    results.drain()
    new_target = _sociomap_object(results, newer_run)
    assert new_target.sociomap_artifact_id != old_target.sociomap_artifact_id
    again = _freeze(results, old_target)
    newer = _freeze(results, new_target)
    # The old target still freezes to the old result, exactly: never the newest one.
    assert again.fingerprint() == first.fingerprint() and again.lineage == first.lineage
    assert newer.fingerprint() != first.fingerprint()
    assert isinstance(first.lineage, InterpretationLineage)
    assert isinstance(newer.lineage, InterpretationLineage)
    assert first.lineage.research_run_id == results.research_run_id
    assert newer.lineage.research_run_id == newer_run
    pin = first.lineage.pin("sociomap")
    assert pin is not None and pin.artifact_id == old_target.sociomap_artifact_id


def test_the_same_target_always_freezes_to_the_same_lineage(results: World) -> None:
    """What a retry will re-freeze from chunk 30: the stored target, to the same lineage."""
    target = _sociomap_object(results)
    first = _freeze(results, target)
    _revision, _newer = _research_run(results.research, NEWER_DESIGN)  # a newer result exists
    results.drain()
    again = _freeze(results, target)
    assert again.target == first.target == target
    assert again.lineage == first.lineage


# --------------------------------------------------------------------------- fails closed


def _deep_research_runs(world: World) -> list[str]:
    for runs in world.runs():
        return [r["run_id"] for r in runs.runs(limit=100)]
    raise AssertionError("unreachable")


def _store_interpretation_row(world: World, spec: Any) -> str:
    """A persisted ``INTERPRETATION_RESEARCH`` row, written at the repository level.

    No current code path creates one (the enqueue boundary refuses the spec): this stands
    for a historical or future row, so the test asks what happens *if such a row exists*
    without proving that the application can make it.
    """
    with world.research.sessions() as session:
        scope = world.research.lead_scope(session)
        project_id = StudyDesignRepository(session, scope).project_id()
        assert project_id is not None
        request = spec.engine_request
        steps = deep_research_steps()
        workflows = WorkflowRepository(session, scope)
        run_id = workflows.create_run(
            project_id=project_id,
            project_revision=request.design_revision,
            workflow_type=DEEP_RESEARCH,
            steps=steps,
            idempotency_key=f"{DEEP_RESEARCH}:spec:{spec.fingerprint()}:simulated",
            metadata={
                "design_revision_id": request.design_revision_id,
                "design_revision": request.design_revision,
                "request_fingerprint": request.fingerprint(),
                "preset": request.preset,
                "channels": [c.value for c in request.channels],
                **run_spec_metadata(spec, purpose_source=PurposeSource.EXPLICIT),
            },
            fingerprints={s.node_key: request.fingerprint() for s in steps},
        )
        workflows.request_cancel(run_id, reason="simulated")
        session.commit()
        return run_id


def test_interpretation_execution_fails_closed_until_target_subjects_exist(
    results: World,
) -> None:
    """ADR 0021 Step 1: the target and its lineage resolve; nothing is enqueued (OI-88)."""
    target = _sociomap_object(results)
    for runs in results.runs():
        with pytest.raises(InterpretationNotReady):
            runs.start_interpretation(target=target, preset_name="QUICK", store=results.store)
    assert _deep_research_runs(results) == []
    # Scope, lineage and target are checked first: a foreign target is not "not ready".
    for runs in results.runs(_sibling_scope(results.research)):
        with pytest.raises(ResearchTargetNotFound):
            runs.start_interpretation(target=target, preset_name="QUICK", store=results.store)


def test_the_enqueue_boundary_refuses_any_interpretation_spec(results: World) -> None:
    """The invariant lives where every run is created, not only in the public start."""
    spec = _freeze(results, _sociomap_object(results))
    for runs in results.runs():
        with pytest.raises(InterpretationNotReady):
            runs._enqueue(
                spec,
                purpose_source=PurposeSource.EXPLICIT,
                retry_of=None,
                prices=None,
                modes=(),
                confirm_cost_usd=None,
            )
    assert _deep_research_runs(results) == []


def test_an_interpretation_row_is_never_retried_until_chunk_30(results: World) -> None:
    spec = _freeze(results, _sociomap_object(results))
    row = _store_interpretation_row(results, spec)
    asked, searched = len(results.agents.requests), len(results.search_calls())
    for runs in results.runs():
        with pytest.raises(InterpretationNotReady):
            runs.retry(row, store=results.store)
    assert _deep_research_runs(results) == [row]  # no new workflow run
    assert results.drain() == 0  # nothing to claim
    assert (len(results.agents.requests), len(results.search_calls())) == (asked, searched)


def test_a_result_that_no_longer_reads_as_pinned_is_refused(results: World) -> None:
    target = _sociomap_object(results)
    row = _store_interpretation_row(results, _freeze(results, target))
    for runs in results.runs():
        assert runs.resolve_lineage(row, store=results.store) == _freeze(results, target).lineage
    with results.research.sessions() as session:  # the pinned row no longer says what it did
        artifact = session.get(ProjectArtifactRow, target.sociomap_artifact_id)
        assert artifact is not None
        artifact.status = "SUPERSEDED"
        session.commit()
    with pytest.raises(ResearchTargetInvalid):
        _freeze(results, target)
    for runs in results.runs():
        with pytest.raises(LineageChanged):
            runs.resolve_lineage(row, store=results.store)


# --------------------------------------------------------------------------- scope


def _sibling_scope(world: ResearchWorld) -> Any:
    """A second study of the same client, opened by the same lead (ADR 0019: a member)."""
    with world.sessions() as session:
        principal = AuthenticatedPrincipal(
            user_id=world.lead_id, organization_id=world.organization_id
        )
        # A study is created by the organization's owner (the fixture's ``owner@``).
        owner_id = session.scalar(
            select(UserRow.user_id).where(UserRow.email == "owner@art-chain.io")
        )
        assert owner_id is not None
        owner = AuthenticatedPrincipal(user_id=owner_id, organization_id=world.organization_id)
        resolver = ScopeResolver(session)
        repo = ScopeRepository(session)
        study = repo.create_study(
            resolver.organization_context(owner),
            client_id=world.client_id,
            slug="sourozenec",
            name="Sourozenec",
            budget_usd=5.0,
        )
        session.flush()
        repo.set_study_status(
            resolver.study_context(principal, study_id=study.study_id), StudyStatus.ACTIVE
        )
        session.commit()
        study_id = study.study_id

    def scope(session: Any) -> Any:
        return ScopeResolver(session).study_context(principal, study_id=study_id)

    return scope


def test_a_result_of_another_study_or_client_is_not_this_studys_to_interpret(
    results: World,
) -> None:
    target = _sociomap_object(results)
    with pytest.raises(ResearchTargetNotFound):
        _freeze(results, target, scope=_sibling_scope(results.research))
    with pytest.raises(ResearchTargetNotFound):
        _freeze(results, target, scope=results.research.other_scope)


def test_a_corrupt_pinned_artifact_fails_closed(results: World) -> None:
    target = _sociomap_object(results)
    with results.research.sessions() as session:
        key = session.get(ProjectArtifactRow, results.artifact(None, "aggregate")).storage_key
    results.store._objects[key] = (b'{"tampered": true}', *results.store._objects[key][1:])
    with pytest.raises(IntegrityError):
        _freeze(results, target)


# --------------------------------------------------------------------------- the frozen engine


def test_design_and_interpretation_share_one_engine_identity(results: World) -> None:
    """Orchestration identity is not engine-work identity. A design run and an interpretation
    spec over one revision have one engine request -- and so the step fingerprints the
    engine reuses by -- and two run identities. Reuse across runs itself is the journey's
    (``test_a_second_pass_reuses_unchanged_tracks_and_measures_what_it_bought``, unchanged)."""
    for runs in results.runs():
        design = runs.start(design_revision_id=results.revision_id, preset_name="QUICK")
    interpretation = _freeze(results, _sociomap_object(results))
    for runs in results.runs():
        d_meta = runs.get(design.run_id)["metadata"]
    assert d_meta["request_fingerprint"] == interpretation.engine_request_fingerprint()
    assert d_meta["run_spec_fingerprint"] != interpretation.fingerprint()


def test_provenance_round_trips_and_resolves_to_the_original_inputs(results: World) -> None:
    for runs in results.runs():
        design = runs.start(
            design_revision_id=results.revision_id, preset_name="QUICK", title="Kontext"
        )
    results.drain()
    for runs in results.runs():
        provenance = runs.provenance(design.run_id, store=results.store)
        meta = runs.get(design.run_id)["metadata"]
        bundle = runs.bundle(design.run_id, store=results.store)
        assert provenance.purpose.value == "DESIGN_RESEARCH"
        assert provenance.target.model_dump(mode="json") == meta["target"]
        assert provenance.lineage.model_dump(mode="json") == meta["lineage"]
        assert provenance.run_spec_fingerprint == meta["run_spec_fingerprint"]
        assert provenance.engine_request_fingerprint == meta["request_fingerprint"]
        assert provenance.evidence_bundle_seal == bundle.sha256 and bundle.verify()
        publish = next(s for s in runs.get(design.run_id)["steps"] if s["node_key"] == "publish")
        assert provenance.evidence_bundle_artifact_id == publish["output"]["artifact_id"]
        # The provenance survives its own serialisation exactly.
        assert type(provenance).model_validate_json(provenance.model_dump_json()) == provenance
        # And its lineage still resolves to the inputs it was frozen on.
        assert runs.resolve_lineage(design.run_id, store=results.store) == provenance.lineage

    # Interpretation: frozen, never enqueued -- its spec and what a run would store of it
    # round-trip exactly, and resolve to the same pinned inputs.
    spec = _freeze(results, _sociomap_object(results))
    assert DeepResearchRunSpec.model_validate_json(spec.model_dump_json()) == spec
    stored = {
        **run_spec_metadata(spec, purpose_source=PurposeSource.EXPLICIT),
        "request_fingerprint": spec.engine_request_fingerprint(),
    }
    record = governed_record(stored)
    assert record is not None
    assert (record.purpose, record.target, record.lineage) == (
        spec.purpose,
        spec.target,
        spec.lineage,
    )
    assert record.run_spec_fingerprint == spec.fingerprint()


def test_neither_purpose_wrote_a_design_or_any_deterministic_artifact(results: World) -> None:
    def research_state() -> tuple[list[tuple[str, str, str]], list[str]]:
        with results.research.sessions() as session:
            rows = session.scalars(
                select(ProjectArtifactRow).where(
                    ProjectArtifactRow.artifact_type.in_(DETERMINISTIC_ARTIFACT_TYPES)
                )
            ).all()
            revisions = StudyDesignRepository(
                session, results.research.lead_scope(session)
            ).revisions(limit=50)
            return (
                sorted((r.artifact_id, r.sha256, r.status) for r in rows),
                [r.revision_id for r in revisions],
            )

    before = research_state()
    target = _sociomap_object(results)
    for runs in results.runs():
        design = runs.start(design_revision_id=results.revision_id, preset_name="QUICK")
        with pytest.raises(InterpretationNotReady):
            runs.start_interpretation(target=target, preset_name="QUICK", store=results.store)
    _freeze(results, target)
    results.drain()
    assert research_state() == before
    with results.research.sessions() as session:
        written = {
            r.artifact_type
            for r in session.scalars(select(ProjectArtifactRow)).all()
            if r.artifact_metadata.get("run_id") == design.run_id
        }
    assert written and written <= set(ARTIFACT_TYPES.values())
