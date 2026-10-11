"""A run computes the methodology in force when it started (ADR 0023 decision 6, plan A4).

The methodologist puts an edited object map in force on the Metodika tab; a run started
afterwards pins it under its own name and computes it through the real worker; a run started
before keeps what it pinned; a retry keeps the original's pin; going back to the preset gives
the code's pins again. With nothing stored, a run pins exactly what it pinned before the store
existed.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.research_sociomap import default_methods
from aia_core.domain.sociomap import AIA_SOCIOMAP_V3
from aia_core.domain.sociomap.models_v3 import SociomapArtifactV3, read_artifact
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.methodology_repository import MethodologyRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors import workbench
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
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
            worker_id="methodology-pin-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _edit(world: Any, *, sigma: float, n_min: int) -> int:
    """Propose and put in force an edited object map, as the Metodika tab will."""
    spec = AIA_SOCIOMAP_V3.model_dump(mode="json")
    spec["terrain"]["sigma"] = sigma
    spec["relation"]["n_min"] = n_min
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose(
            "sociomap", base_preset="aia-sociomap-3", spec=spec, formulas={}, note="test"
        )
        repo.activate("sociomap", version.version_number, reason="test")
        session.commit()
        return version.version_number


def _reset(world: Any) -> None:
    with world.sessions() as session:
        MethodologyRepository(session, world.admin_context(session)).activate("sociomap", None)
        session.commit()


def _start(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
        return started.run_id


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _drain(worker: Worker) -> None:
    while worker.run_once() is not None:
        pass


def _maps(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    step = next(s for s in run["steps"] if s["node_key"] == "sociomap")
    assert step["status"] is StepRunStatus.SUCCEEDED, step
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        body = research.read_json(step["output"]["artifact_id"])["sociomap"]
    (battery,) = body["batteries"]
    maps: dict[str, Any] = battery["maps"]
    return maps


def test_with_nothing_stored_a_run_pins_the_codes_methods(world: Any) -> None:
    run = _run(world, _start(world))
    assert run["metadata"]["sociomap_methods"] == [
        m.model_dump(mode="json") for m in default_methods()
    ]
    assert "methodology" not in run["metadata"]


def test_a_run_computes_the_edited_methodology_in_force_when_it_started(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    before = _start(world)
    number = _edit(world, sigma=0.3, n_min=12)
    after = _start(world)
    assert after != before  # the same revision under an edited methodology is another run
    metadata = _run(world, after)["metadata"]
    assert [m["method_id"] for m in metadata["sociomap_methods"]] == [
        "aia-sociomap-1",
        f"aia-sociomap-3+e{number}",
    ]
    assert metadata["methodology"]["name"] == f"aia-sociomap-3+e{number}"
    assert _start(world) == after  # and that run is idempotent
    _drain(worker)
    edited = read_artifact(_maps(world, store, after)[f"aia-sociomap-3+e{number}"])
    assert isinstance(edited, SociomapArtifactV3)
    assert edited.spec.methodology_version == f"aia-sociomap-3+e{number}"
    assert (edited.spec.terrain is not None and edited.spec.terrain.sigma) == 0.3
    assert edited.spec.relation.n_min == 12
    original = read_artifact(_maps(world, store, before)["aia-sociomap-3"])
    assert isinstance(original, SociomapArtifactV3)
    assert original.spec.terrain is not None
    assert original.spec.terrain.sigma == 0.25  # the earlier run kept its pin


def test_a_retry_keeps_the_methodology_its_run_pinned(world: Any) -> None:
    number = _edit(world, sigma=0.3, n_min=12)
    run_id = _start(world)
    _reset(world)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    pinned = _run(world, retried.run_id)["metadata"]["sociomap_methods"]
    assert pinned[1]["method_id"] == f"aia-sociomap-3+e{number}"


def test_back_to_the_preset_a_new_run_pins_the_codes_methods_again(world: Any) -> None:
    _edit(world, sigma=0.3, n_min=12)
    _reset(world)
    run = _run(world, _start(world))
    assert run["metadata"]["sociomap_methods"] == [
        m.model_dump(mode="json") for m in default_methods()
    ]
