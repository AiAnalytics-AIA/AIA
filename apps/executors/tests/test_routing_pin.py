"""A run pins whether its display conditions are routed (working-copy-edit-ops WCE13 (d)).

``AIA_ROUTING_ENABLED`` (``ResearchRuns.routing_enabled``) is off until fieldwork routes by a
condition (run-qc-and-checkpoint RQC11). Off, a conditional question fails readiness and no run
starts, as it always has. On, a valid condition passes, and a new run pins it: its preflight step
reads the pin, never a switch, and a retry keeps the original's. A design with no condition pins
nothing, so its run is the one it always was.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.application.research import DesignNotReady, ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.workflow import StepRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors import workbench
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

PLAIN = {
    "title": "Ranní nápoj",
    "n": 40,
    "sections": [
        {
            "id": "uvod",
            "type": "questions",
            "questions": [
                {"id": "Q1", "text": "Pijete kávu?", "typ": "vyber", "kategorie": ["Ano", "Ne"]},
                {"id": "Q2", "text": "Proč ne?", "typ": "otevrena"},
            ],
        }
    ],
}
CONDITIONAL: dict[str, Any] = {
    **PLAIN,
    "sections": [
        {
            **PLAIN["sections"][0],
            "questions": [
                PLAIN["sections"][0]["questions"][0],
                {
                    **PLAIN["sections"][0]["questions"][1],
                    "filtr": {"question_id": "Q1", "options": ["Ne"]},
                },
            ],
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
            worker_id="routing-pin-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _start(world: Any, content: dict[str, Any], *, routing: bool) -> dict[str, Any]:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=content, source_stage="run"
        )
        runs = ResearchRuns(session, scope, routing_enabled=routing)
        started = runs.start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
        return runs.get(started.run_id)


def _checks(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, dict[str, Any]]:
    with world.sessions() as session:
        run = ResearchRuns(session, world.lead_scope(session)).get(run_id)
        step = next(s for s in run["steps"] if s["node_key"] == "preflight")
        assert step["status"] is StepRunStatus.SUCCEEDED, step
        research = research_artifacts(session, world.lead_scope(session), store)
        readiness = research.read_json(step["output"]["artifact_id"])["readiness"]
    assert readiness["ready"] is True
    return {c["id"]: c for c in readiness["checks"]}


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _drain(worker: Worker) -> None:
    while worker.run_once() is not None:
        pass


def test_off_a_conditional_question_stops_the_start_as_it_always_has(world: Any) -> None:
    with pytest.raises(DesignNotReady) as refused:
        _start(world, CONDITIONAL, routing=False)
    checks = {c.id: c for c in refused.value.readiness.checks}
    assert checks["conditional_questions"].status == "FAIL"


def test_on_a_valid_condition_starts_and_the_preflight_reads_the_runs_pin(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    run = _start(world, CONDITIONAL, routing=True)
    assert run["metadata"]["routing"] is True
    _drain(worker)
    checks = _checks(world, store, run["run_id"])
    assert checks["conditional_questions"]["status"] == "PASS"
    assert "q2" in checks["conditional_questions"]["message"]
    # No source routes yet (RQC11): fieldwork fails by name, never asking everyone.
    run = _run(world, run["run_id"])
    fieldwork = next(s for s in run["steps"] if s["node_key"] == "run")
    assert fieldwork["status"] is StepRunStatus.FAILED, fieldwork
    assert fieldwork["attempts"][-1]["error"]["code"] == "routing_unavailable"


def test_a_retry_keeps_the_originals_pin_whatever_its_composition_says_now(
    world: Any, worker: Worker
) -> None:
    run = _start(world, CONDITIONAL, routing=True)
    with world.sessions() as session:
        ResearchRuns(session, world.lead_scope(session)).cancel(run["run_id"])
        session.commit()
    _drain(worker)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session), routing_enabled=False)
        retried = runs.retry(run["run_id"], fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
        assert runs.get(retried.run_id)["metadata"]["routing"] is True


def test_a_start_after_the_switch_is_off_finds_the_routed_run(world: Any) -> None:
    routed = _start(world, CONDITIONAL, routing=True)
    assert _start(world, CONDITIONAL, routing=False)["run_id"] == routed["run_id"]


def test_a_design_without_a_condition_pins_nothing_and_keeps_its_run(world: Any) -> None:
    unrouted = _start(world, PLAIN, routing=False)
    routed = _start(world, PLAIN, routing=True)
    assert "routing" not in routed["metadata"]
    assert routed["run_id"] == unrouted["run_id"]
