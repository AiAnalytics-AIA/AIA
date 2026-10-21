"""Deep Research under advisory class gates (plan ``develop-class-advisory`` chunks 4-5).

OI-129: a design no operator classified parks the run (``egress_unclassified_material``)
under enforce; under ``AIA_DATA_CLASS_GATES=advisory`` -- develop only -- it takes the owner's
design rule (Class B) and the plan step's event says so. Brave, composed, declares the one
stated exception to EU residency, and the composition hands the gates to every gate.

Shared helpers come from conftest fixtures (``world``, ``deep_research_fixture``), never from
another test module (AGENTS.md § pytest).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.web_retrieval import RetrievalGate
from aia_core.domain.deep_research.tooling import InMemoryToolLedger
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors.ai_runtime import AIRuntimeSettings
from aia_executors.deep_research import DeepResearchRuntime, deep_research_registry
from aia_executors.deep_research_runtime import deep_research_runtime
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker

#: Brave on, with a fictional key (as ``test_deep_research_brave_route.py`` composes it).
BRAVE = {
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "fictional-brave-key-0000",
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-09",
}


def _settings(world: Any, fx: Any, gates: DataClassGates, *, classified: bool) -> AIRuntimeSettings:
    settings = fx.ai_settings(world.client_id, approved_for=fx.DEVELOP_ROUTE)
    approvals = settings.material_approvals if classified else ()
    return dataclasses.replace(settings, material_approvals=approvals, data_class_gates=gates)


def _worker(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: Any, runtime: Any
) -> Worker:
    assert isinstance(runtime, DeepResearchRuntime)
    return Worker(
        session_factory=world.sessions,
        executors=deep_research_registry(store=store, build=build, runtime=runtime),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="deep-research-advisory-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _drain(w: Worker, *, limit: int = 20) -> None:
    for _ in range(limit):
        if w.run_once() is None:
            return
    raise AssertionError("the worker kept finding work")


def _start(world: Any, design: dict[str, Any]) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=design, source_stage="brief"
        )
        run = DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name="QUICK"
        )
        session.commit()
        return run.run_id


def _run(world: Any, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with world.sessions() as session:
        runs = DeepResearchRuns(session, world.lead_scope(session))
        return runs.get(run_id), runs.events(run_id, limit=2000)


def test_under_enforce_an_unclassified_design_parks_the_run_and_sends_nothing(
    world: Any,
    deep_research_fixture: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    fx = deep_research_fixture
    agents = fx.RecordedAgents(fx.ANSWERS)
    runtime = deep_research_runtime(
        _settings(world, fx, DataClassGates.ENFORCE, classified=False),
        env={"AIA_DEEP_RESEARCH_ENABLED": "true"},
        transport=agents,
        signer=fx.Signer(),
    )
    assert runtime is not None and runtime.config.class_gates is DataClassGates.ENFORCE
    run_id = _start(world, fx.DESIGN)
    _drain(_worker(world, database_url, store, build, runtime))
    run, events = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert run["steps"][0]["attempts"][-1]["error"]["reason"] == "egress_unclassified_material"
    assert agents.requests == []
    assert not any("class_advisory" in e["payload"] for e in events)


def test_under_advisory_an_unclassified_design_takes_the_design_rule_and_says_so(
    world: Any,
    deep_research_fixture: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    fx = deep_research_fixture
    runtime = deep_research_runtime(
        _settings(world, fx, DataClassGates.ADVISORY, classified=False),
        env={"AIA_DEEP_RESEARCH_ENABLED": "true"},
        transport=fx.RecordedAgents(fx.ANSWERS),
        signer=fx.Signer(),
    )
    assert runtime is not None and runtime.config.class_gates is DataClassGates.ADVISORY
    run_id = _start(world, fx.DESIGN)
    _drain(_worker(world, database_url, store, build, runtime))
    run, events = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED  # never parked on the class
    recorded = [e["payload"]["class_advisory"] for e in events if "class_advisory" in e["payload"]]
    assert recorded == [
        {
            "gate": "deep_research_design",
            "rule": "egress_unclassified_material",
            "data_class": DataClass.CLASS_B_DERIVED_CLIENT.value,
            "advisory": True,
        }
    ]


class _StudyMeter(InMemoryToolLedger):
    """A meter that holds tool spend against the study, as ``StepToolMeter`` does."""

    def __init__(self) -> None:
        super().__init__(budget_usd=None)

    @property
    def charges_study_budget(self) -> bool:
        return True


def test_brave_composed_declares_the_exception_and_takes_any_class_only_under_advisory(
    world: Any, deep_research_fixture: Any
) -> None:
    fx = deep_research_fixture
    for gates, refused in ((DataClassGates.ENFORCE, True), (DataClassGates.ADVISORY, False)):
        runtime = deep_research_runtime(
            _settings(world, fx, gates, classified=True),
            env=BRAVE,
            transport=fx.RecordedAgents(fx.ANSWERS),
            signer=fx.Signer(),
        )
        assert runtime is not None and runtime.retrieval is not None
        search = runtime.retrieval.search_route
        assert search.route_id == "brave-web-search" and search.any_class_when_advisory
        # The fetch route declares nothing: pages stay Class C only in both modes.
        assert not runtime.retrieval.fetch_route.any_class_when_advisory
        # Advisory lifts the class, never the price or the sign-off.
        assert search.needs_sign_off and runtime.sign_off_routes() == ("brave-web-search",)
        with world.sessions() as session:
            gate = RetrievalGate(
                retrieval=runtime.retrieval,
                scope=world.lead_scope(session),
                meter=_StudyMeter(),
                client_terms=(),
                class_a_texts=(),
                class_gates=runtime.config.class_gates,
            )
            for cls in (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, DataClass.CLASS_B_DERIVED_CLIENT):
                assert (gate.refusal_for_class(cls) is not None) is refused
