"""The run QC step under the real worker loop (run-qc-and-checkpoint RQC2).

A run started with the switch gains a ``qc`` step after fieldwork; one started without it is the
research graph as before. On the workbench's fictional fieldwork the run completes and stores the
QC the domain computes (evidence-integrity 2a); a QC it cannot read is stored as not computed and
the run still completes: nothing QC finds fails a run (MVP-24).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import DataOrigin, FieldworkSource
from aia_core.domain.qc_flags import dataset_flags, flags_payload
from aia_core.domain.run_qc import QcNotReadable, dataset_qc
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors import research as research_executors
from aia_executors import workbench
from aia_executors.research import RUN_QC, unit_dry
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

DESIGN = {
    "title": "Ranní nápoj",
    "n": 40,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"text": f"Jak moc souhlasíte {k}?", "typ": "skala", "skala": [1, 5]}
                for k in range(3)
            ]
            + [{"text": "Co pijete?", "typ": "vyber", "kategorie": ["Kávu", "Čaj"]}],
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
                worker_id="qc-worker",
                lease_seconds=60,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return build


def _start(world: Any, *, qc: bool) -> tuple[str, str]:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            qc_enabled=qc,
        )
        session.commit()
        return started.run_id, revision.revision_id


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def test_without_the_switch_the_graph_is_unchanged(world: Any) -> None:
    run = _run(world, _start(world, qc=False)[0])
    assert [s["node_key"] for s in run["steps"]] == [
        "compile",
        "preflight",
        "run",
        "aggregate",
        "sociomap",
    ]
    assert "qc_enabled" not in run["metadata"]


def test_the_switch_is_part_of_the_runs_identity_and_a_retry_keeps_it(world: Any) -> None:
    without, revision_id = _start(world, qc=False)
    with world.sessions() as session:
        scope = world.lead_scope(session)
        with_qc = ResearchRuns(session, scope).start(
            design_revision_id=revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            qc_enabled=True,
        )
        session.commit()
    assert with_qc.created and with_qc.run_id != without
    run = _run(world, with_qc.run_id)
    assert run["metadata"]["qc_enabled"] is True
    assert [s["node_key"] for s in run["steps"]][-1] == "qc"

    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(with_qc.run_id)
        retried = runs.retry(with_qc.run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    assert _run(world, retried.run_id)["metadata"]["qc_enabled"] is True


def test_the_fictional_run_completes_and_stores_the_domains_qc(
    world: Any,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    run_id = _start(world, qc=True)[0]
    worker = worker_with(workbench.workbench_registry_for(store=store, build=build))
    assert _drain(worker) == ["completed"] * 6
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    steps = {s["node_key"]: s for s in run["steps"]}
    out = steps["qc"]["output"]
    assert steps["qc"]["status"] is StepRunStatus.SUCCEEDED
    assert out["artifact_type"] == RUN_QC
    assert out["status"] == "computed"

    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        stored = research.read_json(out["artifact_id"])["qc"]
        spec_id = steps["compile"]["output"]["artifact_id"]
        dataset_id = steps["run"]["output"]["artifact_id"]
        deps = {a.artifact_id for a in research.dependencies(out["artifact_id"])}
        expected = dataset_qc(
            research_executors._read_spec(research, spec_id),
            research_executors._read_dataset(research, dataset_id),
            dry=True,
        )
        dataset = research_executors._read_dataset(research, dataset_id)
        spec = research_executors._read_spec(research, spec_id)
        flags = flags_payload(dataset_flags(spec, dataset))
        respondents = len(dataset.respondents)
    assert deps == {spec_id, dataset_id}
    assert stored["inputs"]["dataset_artifact_id"] == dataset_id
    assert stored["level"] == expected.level.value == out["level"]
    assert [(f["check"], f["where"], f["value"]) for f in stored["findings"]] == [
        (f.check.value, f.where, f.value) for f in expected.findings
    ]
    assert stored["metrics"] == expected.metrics
    # A fictional run is the unit's dry run: no ablation flag.
    assert "persona_effect_unverified" not in {f["check"] for f in stored["findings"]}
    # RQC4a: the straight-liners the rule names, one flag each, the record a decision lands in.
    assert stored["flags"] == flags
    assert round(len(flags["flags"]) / respondents, 3) == stored["metrics"]["straightlining"]
    assert set(stored["not_applicable"]) == {k.value for k in expected.not_applicable}


def test_a_qc_it_cannot_read_is_stored_as_not_computed_and_the_run_completes(
    world: Any,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A routed dataset (RQC11) is the case: fieldwork refuses a routed run today, so the domain's
    refusal is what this run meets."""

    def refuse(*_: Any, **__: Any) -> Any:
        raise QcNotReadable("q2: a conditional question's base is the respondents asked")

    monkeypatch.setattr(research_executors, "dataset_qc", refuse)
    run_id = _start(world, qc=True)[0]
    worker = worker_with(workbench.workbench_registry_for(store=store, build=build))
    assert _drain(worker) == ["completed"] * 6
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    out = next(s for s in run["steps"] if s["node_key"] == "qc")["output"]
    assert out["status"] == "not_computed"
    with world.sessions() as session:
        stored = research_artifacts(session, world.lead_scope(session), store).read_json(
            out["artifact_id"]
        )["qc"]
    assert stored["reason"].startswith("q2: a conditional question's base")
    assert "findings" not in stored and "level" not in stored and "flags" not in stored


@pytest.mark.parametrize(
    ("origin", "dry"),
    [
        (DataOrigin.SYNTHETIC_FIXTURE, True),
        (DataOrigin.SYNTHETIC_AI_FICTIONAL, False),
        (DataOrigin.MODELLED_AI_PANEL, False),
        (None, False),
    ],
)
def test_only_the_fixtures_invented_answers_are_the_units_dry_run(
    origin: DataOrigin | None, dry: bool
) -> None:
    """The unit's dry run made no model call; fictional AI respondents were a model's answers."""
    assert unit_dry(origin) is dry
