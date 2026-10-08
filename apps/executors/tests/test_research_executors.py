"""The research steps under the real worker loop (ADR 0016, PR C chunk 4).

Two compositions are driven here. The production one
(``aia_executors.registry``) must compile, check readiness, and then **park** at
fieldwork: no AI runtime is deployed, so nothing may be produced. The workbench
one (``aia_executors.workbench``) adds the fictional synthetic source, and its
dataset must say so. Whatever a step stores lives on the Study's owned design
project, where no ordinary artifact reader can see it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource
from aia_core.domain.workflow import (
    RUNTIME_UNAVAILABLE_REASON,
    FailureClass,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.artifact_repository import ArtifactNotFound, ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors import workbench
from aia_executors.registry import registry_for
from aia_executors.research import (
    AGGREGATE,
    FIELDWORK_DATASET,
    READINESS,
    SOCIOMAP,
    SPECIFICATION,
)
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

DESIGN = {
    "title": "Ranní nápoj",
    "n": 60,
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
                    "povolit_nevim": True,
                },
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


@pytest.fixture
def worker_with(
    sessions: sessionmaker[Session], database_url: str
) -> Callable[[dict[str, StepExecutor]], Worker]:
    def build(executors: dict[str, StepExecutor]) -> Worker:
        return Worker(
            session_factory=sessions,
            executors=executors,
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="research-worker",
                lease_seconds=30,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return build


def _start(world: Any, source: FieldworkSource) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, fieldwork_source=source
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


def test_production_compiles_checks_and_parks_at_fieldwork(
    world: Any,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    """D1: a real run progresses honestly to fieldwork, then waits for the AI runtime."""
    run_id = _start(world, FieldworkSource.AI_RUNTIME)
    endings = _drain(worker_with(registry_for(store=store, build=build)))
    assert endings == ["completed", "completed", "failed"]

    run = _run(world, run_id)
    steps = _steps(run)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert steps["run"]["status"] is StepRunStatus.WAITING_PROVIDER
    assert steps["run"]["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    last = steps["run"]["attempts"][-1]
    assert last["failure_class"] is FailureClass.RUNTIME_UNAVAILABLE
    assert "nic nebylo vymyšleno" in last["error"]["message"]
    assert steps["aggregate"]["status"] is StepRunStatus.BLOCKED
    assert steps["sociomap"]["status"] is StepRunStatus.BLOCKED

    spec_id = steps["compile"]["output"]["artifact_id"]
    readiness_id = steps["preflight"]["output"]["artifact_id"]
    with world.sessions() as session:
        scope = world.lead_scope(session)
        research = research_artifacts(session, scope, store)
        spec = research.read_json(spec_id)
        readiness = research.read_json(readiness_id)
        assert research.get(spec_id).artifact_type == SPECIFICATION
        assert research.get(readiness_id).artifact_type == READINESS
        assert [a.artifact_id for a in research.dependencies(readiness_id)] == [spec_id]
        # The generic reader -- what /projects/{p}/artifacts/{a} uses -- cannot see them.
        for artifact_id in (spec_id, readiness_id):
            with pytest.raises(ArtifactNotFound):
                ArtifactRepository(session, scope, store).get(artifact_id)
    assert spec["specification"]["n"] == 60
    assert [q["id"] for q in spec["specification"]["questions"]] == ["q1", "q2"]
    assert spec["specification"]["questions"][1]["options"][-1] == "Nevím / neodpovím"
    assert len(spec["specification"]["batteries"][0]["objects"]) == 5
    assert readiness["readiness"]["ready"] is True
    assert spec["produced_by"]["run_id"] == run_id
    assert spec["runtime_version"] == build.sha


def test_the_workbench_produces_a_fictional_dataset_that_says_so(
    world: Any,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    run_id = _start(world, FieldworkSource.SYNTHETIC_FIXTURE)
    worker = worker_with(workbench.workbench_registry_for(store=store, build=build))
    assert _drain(worker) == ["completed"] * 5
    assert _run(world, run_id)["status"] is WorkflowRunStatus.COMPLETED

    steps = _steps(_run(world, run_id))
    output = steps["run"]["output"]
    assert steps["run"]["status"] is StepRunStatus.SUCCEEDED
    assert output["artifact_type"] == FIELDWORK_DATASET
    assert output["data_origin"] == DataOrigin.SYNTHETIC_FIXTURE.value
    assert output["respondents"] == 60
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        artifact = research.get(output["artifact_id"])
        dataset = research.read_json(output["artifact_id"])["dataset"]
    assert artifact.metadata["data_origin"] == "SYNTHETIC_FIXTURE"
    assert dataset["origin"] == "SYNTHETIC_FIXTURE" and dataset["source"] == "synthetic_fixture"
    assert dataset["seed"] == workbench.SYNTHETIC_SEED
    assert len(dataset["respondents"]) == 60
    assert all(r["respondent_id"].startswith("SYN-") for r in dataset["respondents"])

    # Aggregate ran over that dataset, and says where its numbers came from.
    aggregate_out = steps["aggregate"]["output"]
    assert steps["aggregate"]["status"] is StepRunStatus.SUCCEEDED
    assert aggregate_out["artifact_type"] == AGGREGATE
    assert aggregate_out["data_origin"] == "SYNTHETIC_FIXTURE"
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        aggregate = research.read_json(aggregate_out["artifact_id"])["aggregate"]
        deps = {a.artifact_id for a in research.dependencies(aggregate_out["artifact_id"])}
    assert deps == {steps["compile"]["output"]["artifact_id"], output["artifact_id"]}
    assert aggregate["bootstrap_generator"].startswith("python-random")
    assert aggregate["questions"]["q1"]["n_platnych"] == 60
    assert set(aggregate["batteries"]["napoje"]["objects"]) == {
        "kava",
        "caj",
        "kakao",
        "dzus",
        "voda",
    }

    # The Sociomap was computed, and is internal only while D6 is open.
    sociomap_out = steps["sociomap"]["output"]
    assert sociomap_out["artifact_type"] == SOCIOMAP
    assert sociomap_out["methodology_status"] == "INTERNAL_ONLY"
    assert sociomap_out["data_origin"] == "SYNTHETIC_FIXTURE"
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        sociomap = research.read_json(sociomap_out["artifact_id"])["sociomap"]
    (battery,) = sociomap["batteries"]
    assert battery["methodology_status"] == "INTERNAL_ONLY"
    assert battery["sociomap"]["kind"] == "sociomap"


def test_a_worker_never_substitutes_a_source_it_does_not_provide(
    world: Any,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    """A run recorded for the fictional source, on the production composition, fails.

    It is not parked and not given another source's data: this composition was
    never meant to run it, so the run stops and says why.
    """
    run_id = _start(world, FieldworkSource.SYNTHETIC_FIXTURE)
    assert _drain(worker_with(registry_for(store=store, build=build))) == [
        "completed",
        "completed",
        "failed",
    ]
    run = _run(world, run_id)
    fieldwork = _steps(run)["run"]
    assert run["status"] is WorkflowRunStatus.FAILED
    assert fieldwork["attempts"][-1]["failure_class"] is FailureClass.MISSING_CONFIGURATION
    assert "does not provide" in fieldwork["attempts"][-1]["error"]["message"]
    assert "artifact_id" not in (fieldwork.get("output") or {})


@pytest.mark.parametrize("env", ["", "staging", "production", "develop"])
def test_the_workbench_composition_refuses_every_deployed_environment(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("AIA_ENV", env)
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    with pytest.raises(RuntimeError, match="fictional fieldwork"):
        workbench.build_registry()


@pytest.mark.parametrize("env", ["local", "test"])
def test_the_workbench_composition_builds_locally(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("AIA_ENV", env)
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    assert "research_fieldwork" in workbench.build_registry()


def test_no_composition_can_hand_the_ai_runtime_a_producer(
    store: InMemoryArtifactStore, build: BuildIdentity
) -> None:
    from aia_executors.research import FieldworkExecutor

    with pytest.raises(ValueError, match="not a dataset producer"):
        FieldworkExecutor(
            store=store,
            build=build,
            producers={FieldworkSource.AI_RUNTIME: lambda spec: None},  # type: ignore[arg-type,return-value]
        )


def test_a_changed_engine_is_not_handed_the_previous_engines_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reuse is by input fingerprint; the engine's version is part of it.

    Engine 1.2.0 stopped placing straight-liners (plan sociomap-formula-corrections,
    chunk 1c). Without the version in the fingerprint, a newer build would get the
    map the previous engine drew for the same dataset and spec back from storage.
    """
    from aia_core.domain.research_design import compile_design
    from aia_core.domain.research_sociomap import LEGACY_METHODS
    from aia_executors import research as research_module

    spec, problems = compile_design(
        {
            "n": 40,
            "sections": [
                {
                    "type": "object_battery",
                    "object_family": "značky",
                    "objects": ["A", "B", "C"],
                    "scale": [1, 10],
                }
            ],
        }
    )
    assert spec is not None, problems

    def fingerprint(*, interval: bool = False) -> str:
        return research_module._sociomap_fingerprint(
            "dataset-sha", spec, methods=LEGACY_METHODS, connectedness_interval=interval
        )

    before = fingerprint()
    assert fingerprint() == before
    # A map stored without F9's interval is never handed back once the switch is on.
    assert fingerprint(interval=True) != before
    monkeypatch.setattr(research_module, "ENGINE_IMPLEMENTATION_VERSION", "9.9.9")
    assert fingerprint() != before


def test_the_connectedness_interval_switch_is_off_unless_set_and_refuses_a_guess() -> None:
    """Audit F9's bootstrap (~90 s per 1,500 x 22 battery) runs only behind
    AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED (CLAUDE.md § 8)."""
    from aia_executors import research as research_module
    from aia_executors.registry import (
        SOCIOMAP_CONNECTEDNESS_INTERVAL_KEY as KEY,
    )
    from aia_executors.registry import (
        sociomap_connectedness_interval as switch,
    )

    assert switch({}) is False
    assert switch({KEY: ""}) is False and switch({KEY: "false"}) is False
    assert switch({KEY: "true"}) is True and switch({KEY: " ON "}) is True
    with pytest.raises(ValueError, match=KEY):
        switch({KEY: "maybe"})
    store, build = InMemoryArtifactStore(), BuildIdentity(sha=None)
    for on in (False, True):
        step = registry_for(store=store, build=build, sociomap_connectedness_interval=on)[
            "research_sociomap"
        ]
        assert isinstance(step, research_module.SociomapExecutor)
        assert step._connectedness_interval is on
    default = registry_for(store=store, build=build)["research_sociomap"]
    assert isinstance(default, research_module.SociomapExecutor)
    assert default._connectedness_interval is False
