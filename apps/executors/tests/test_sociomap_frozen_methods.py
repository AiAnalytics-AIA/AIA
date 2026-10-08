"""A research run computes the Sociomap methods it pinned when it was started.

Plan ``sociomap-formula-corrections`` § 8.2, slice S1 (I0, I4): ``ResearchRuns.start``
pins each method with its whole spec; the ``sociomap`` step computes exactly those,
whatever the module's preset becomes before it runs or is retried; a run stored before
methods were pinned is computed as ``aia-sociomap-1``, which computed every such run.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain import research_sociomap
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.research_sociomap import LEGACY_METHODS, SociomapMethod
from aia_core.domain.sociomap import AIA_SOCIOMAP_V1, SociomapSpec
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import StepRunRow, WorkflowRunRow
from aia_executors import workbench
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

DESIGN = {
    "title": "Ranní nápoj",
    "n": 40,
    "sections": [
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        }
    ],
}


def _variant(extent: float) -> SociomapSpec:
    """``aia-sociomap-1`` with another map frame: same method id, another spec."""
    return AIA_SOCIOMAP_V1.model_copy(
        update={
            "layout": AIA_SOCIOMAP_V1.layout.model_copy(
                update={
                    "map_frame": AIA_SOCIOMAP_V1.layout.map_frame.model_copy(
                        update={"extent": extent}
                    )
                }
            )
        }
    )


@pytest.fixture
def worker(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Worker:
    executors: dict[str, StepExecutor] = workbench.workbench_registry_for(store=store, build=build)
    return Worker(
        session_factory=sessions,
        executors=executors,
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="sociomap-pin-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _start(world: Any, *, methods: tuple[SociomapMethod, ...] | None = None) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            sociomap_methods=methods,
        )
        session.commit()
        return started.run_id


def _drain(worker: Worker) -> None:
    while worker.run_once() is not None:
        pass


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _sociomap(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    run = _run(world, run_id)
    step = next(s for s in run["steps"] if s["node_key"] == "sociomap")
    assert step["status"] is StepRunStatus.SUCCEEDED, step
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        body: dict[str, Any] = research.read_json(step["output"]["artifact_id"])["sociomap"]
    return body


def _extent(body: dict[str, Any]) -> float:
    (battery,) = body["batteries"]
    return float(battery["sociomap"]["spec"]["layout"]["map_frame"]["extent"])


def test_a_new_run_pins_the_default_and_records_it(world: Any) -> None:
    run_id = _start(world)
    run = _run(world, run_id)
    pinned = [m.model_dump(mode="json") for m in LEGACY_METHODS]
    assert run["metadata"]["sociomap_methods"] == pinned
    with world.sessions() as session:
        step = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == "sociomap")
        ).one()
        assert step.input_json == {"methods": pinned}


def test_the_run_computes_its_pin_after_the_module_preset_changes(
    world: Any,
    store: InMemoryArtifactStore,
    worker: Worker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = _start(world)
    # The preset changes between enqueue and execution (a new build, a new default):
    # the run still computes the spec it pinned.
    monkeypatch.setattr(research_sociomap, "AIA_SOCIOMAP_V1", _variant(30.0))
    monkeypatch.setattr(
        research_sociomap, "default_methods", lambda: (SociomapMethod.of(_variant(30.0)),)
    )
    _drain(worker)
    assert _run(world, run_id)["status"] is WorkflowRunStatus.COMPLETED
    body = _sociomap(world, store, run_id)
    assert _extent(body) == AIA_SOCIOMAP_V1.layout.map_frame.extent == 45.0
    assert body["methods"] == [
        {"method_id": "aia-sociomap-1", "spec_fingerprint": AIA_SOCIOMAP_V1.fingerprint()}
    ]


def test_a_run_pinned_to_another_spec_computes_that_spec_and_is_another_run(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    legacy = _start(world)
    variant = (SociomapMethod.of(_variant(30.0)),)
    pinned = _start(world, methods=variant)
    assert pinned != legacy  # the same revision under another set is another run
    assert _start(world, methods=variant) == pinned  # and that run is idempotent
    _drain(worker)
    assert _extent(_sociomap(world, store, legacy)) == 45.0
    body = _sociomap(world, store, pinned)
    assert _extent(body) == 30.0
    assert body["methods"][0]["spec_fingerprint"] == _variant(30.0).fingerprint()


def test_a_run_stored_before_pins_is_computed_as_aia_sociomap_1(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    run_id = _start(world, methods=(SociomapMethod.of(_variant(30.0)),))
    with world.sessions() as session:
        # What every run stored before this change looks like: no pin anywhere.
        step = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == "sociomap")
        ).one()
        step.input_json = {}
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        run.metadata_json = {k: v for k, v in run.metadata_json.items() if k != "sociomap_methods"}
        session.commit()
    _drain(worker)
    body = _sociomap(world, store, run_id)
    assert _extent(body) == 45.0
    assert body["methods"][0]["method_id"] == "aia-sociomap-1"


def test_a_retry_pins_what_the_run_it_retries_pinned(
    world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    variant = (SociomapMethod.of(_variant(30.0)),)
    run_id = _start(world, methods=variant)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        session.commit()
    # The default changes before the retry; the retry keeps the original's pin.
    monkeypatch.setattr(
        "aia_core.application.research.default_methods",
        lambda: (SociomapMethod.of(_variant(20.0)),),
    )
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    assert retried.run_id != run_id
    assert _run(world, retried.run_id)["metadata"]["sociomap_methods"] == [
        m.model_dump(mode="json") for m in variant
    ]


def test_a_pin_that_does_not_verify_fails_the_step_by_name(world: Any, worker: Worker) -> None:
    run_id = _start(world)
    with world.sessions() as session:
        step = session.scalars(
            select(StepRunRow).where(StepRunRow.run_id == run_id, StepRunRow.node_key == "sociomap")
        ).one()
        (method,) = step.input_json["methods"]
        edited = {**method, "spec": {**method["spec"]}}
        edited["spec"]["spec"] = {
            **method["spec"]["spec"],
            "terrain": {**method["spec"]["spec"]["terrain"], "normalization": "absolute"},
        }
        step.input_json = {"methods": [edited]}
        session.commit()
    _drain(worker)
    step_out = next(s for s in _run(world, run_id)["steps"] if s["node_key"] == "sociomap")
    assert step_out["status"] is StepRunStatus.FAILED
    error = step_out["attempts"][-1]["error"]
    assert error["code"] == "sociomap_method_invalid"
    assert "fingerprint" in error["message"]
