"""The workbench's Deep Research (research-lead-workbench 12a, F-DRL-6): recorded web, scripted
agents, the real worker, gateway, adapter, retrieval gate and steps -- and nothing paid.

The fixtures are the ones the UI workbench runs on (``tools/ui_workbench/fixtures/
deep_research/``): a fictional recorded web and the scripted agents' answers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.deep_research.contracts import Channel, EvidenceOrigin, RetrievalMode
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH_KINDS, INVESTIGATE_TRACK_KIND
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import AIUsageEventRow
from aia_executors.deep_research import PlanExecutor
from aia_executors.registry import registry_for
from aia_executors.workbench import (
    ScriptedDeepResearchModel,
    WorkbenchDesignClassifier,
    scripted_deep_research_runtime,
    workbench_registry_for,
)
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tools" / "ui_workbench" / "fixtures" / "deep_research"

Q1 = "Jak velký je trh ranních nápojů pro dojíždějící v Česku?"
Q2 = "Proč lidé na cestě do práce kupují nápoje s kofeinem?"
DESIGN: dict[str, Any] = {
    "title": "Workbench · rešerše k návrhu",
    "goal": "Zjistit, zda nový ranní nápoj dává smysl lidem, kteří dojíždějí.",
    "research_plan": {"research_questions": [Q1, Q2]},
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Jak často dojíždíte?", "kategorie": ["Denně"]}],
        }
    ],
}

KINDS = {*DEEP_RESEARCH_KINDS.values(), INVESTIGATE_TRACK_KIND}


@pytest.fixture(autouse=True)
def _test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The composition reads AIA_ENV as the workbench's worker does; here it is a test."""
    monkeypatch.setenv("AIA_ENV", "test")


def _worker(world: Any, database_url: str, store: Any, build: Any) -> Worker:
    return Worker(
        session_factory=world.sessions,
        executors=workbench_registry_for(store=store, build=build, deep_research=FIXTURES),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="workbench-deep-research",
            executors="aia_executors.workbench:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _start(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="questionnaire"
        )
        # As the panel starts it: QUICK, the web channel (apps/web/src/lib/api.ts).
        run = DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name="QUICK", channels=[Channel.WEB]
        )
        session.commit()
        return run.run_id


def test_the_registry_holds_the_six_steps_and_the_track_kind(store: Any, build: Any) -> None:
    registry = workbench_registry_for(store=store, build=build, deep_research=FIXTURES)
    assert set(registry) >= KINDS
    assert isinstance(registry[DEEP_RESEARCH_KINDS["plan"]], WorkbenchDesignClassifier)
    # Without fixtures the workbench is production's: the steps park over no runtime.
    plain = workbench_registry_for(store=store, build=build)
    assert type(plain[DEEP_RESEARCH_KINDS["plan"]]) is PlanExecutor
    assert plain[DEEP_RESEARCH_KINDS["plan"]]._runtime is None
    # And production never classifies a design for itself.
    production = registry_for(store=store, build=build)
    assert type(production[DEEP_RESEARCH_KINDS["plan"]]) is PlanExecutor


def test_the_runtime_is_recorded_and_free(store: Any, build: Any) -> None:
    runtime, model = scripted_deep_research_runtime(FIXTURES, env={"AIA_ENV": "local"})
    assert isinstance(model, ScriptedDeepResearchModel)
    retrieval = runtime.retrieval
    assert retrieval is not None
    for route in (retrieval.search_route, retrieval.fetch_route):
        assert route.retrieval_mode is RetrievalMode.RECORDED
        assert route.price_usd_per_call == 0.0
    assert runtime.sign_off_routes() == ()
    # Holds are nominal (a metered request needs a positive one), never a real model's price.
    assert runtime.config.largest_reservation_usd < 0.01


@pytest.mark.parametrize("env", ["develop", "staging", "production", ""])
def test_it_refuses_outside_local_and_test(env: str) -> None:
    with pytest.raises(RuntimeError, match="refuses AIA_ENV"):
        scripted_deep_research_runtime(FIXTURES, env={"AIA_ENV": env})


def test_a_run_on_the_fixture_completes_sealed_recorded_and_unpaid(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    run_id = _start(world)
    worker = _worker(world, database_url, store, build)
    for _ in range(40):
        if worker.run_once() is None:
            break
    with world.sessions() as session:
        runs = DeepResearchRuns(session, world.lead_scope(session))
        run, bundle = runs.get(run_id), runs.bundle(run_id, store=store)
        usage = session.scalars(
            select(AIUsageEventRow).where(AIUsageEventRow.run_id == run_id)
        ).all()

    assert run["status"] is WorkflowRunStatus.COMPLETED, run["steps"]
    assert {s["status"] for s in run["steps"]} == {StepRunStatus.SUCCEEDED}
    assert bundle.verify()
    assert bundle.origins == (EvidenceOrigin.RECORDED_FIXTURE,)
    assert bundle.client_facing is False
    assert bundle.snapshots and {s.retrieval_mode for s in bundle.snapshots} == {
        RetrievalMode.RECORDED
    }
    claims = {a.evidence.claim for a in bundle.accepted}
    assert "Prodej nápojů s kofeinem v plechovce vzrostl v Česku v roce 2025 o 9 %." in claims
    assert "Dojíždějící uvádějí jako hlavní důvod nákupu potřebu se probrat před prací." in claims

    # Every model request went through the gateway's ledger, answered by the script, at zero.
    assert usage, "no model request reached the ledger"
    assert {u.cost_usd for u in usage} == {0.0}
    assert all(
        (u.provider_request_id or "").startswith("workbench-scripted-")
        for u in usage
        if u.provider_request_id
    )
    assert {u.route_id for u in usage} == {"workbench-scripted"}
