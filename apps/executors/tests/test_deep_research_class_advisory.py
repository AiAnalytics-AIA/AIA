"""Deep Research under advisory class gates (plan ``develop-class-advisory`` chunks 4-5).

OI-129: a design no operator classified parks the run (``egress_unclassified_material``)
under enforce; under ``AIA_DATA_CLASS_GATES=advisory`` -- develop only -- it takes the owner's
design rule (Class B) and the plan step's event says so. Brave, composed, declares the one
stated exception to EU residency, and the composition hands the gates to every gate.
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
from aia_executors.ai_runtime import AIRuntimeSettings
from aia_executors.deep_research_runtime import deep_research_runtime
from deep_research_fixtures import (  # type: ignore[import-not-found]
    ANSWERS,
    DEVELOP_ROUTE,
    RecordedAgents,
    Signer,
    ai_settings,
)
from test_deep_research_brave_route import BRAVE  # type: ignore[import-not-found]
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    drain,
    research,  # noqa: F401  (a fixture)
    start,
    worker,
)


def _unclassified(world: ResearchWorld, gates: DataClassGates) -> AIRuntimeSettings:
    """The fixture's settings with no operator classification of any design."""
    settings = ai_settings(world.client_id, approved_for=DEVELOP_ROUTE)
    return dataclasses.replace(settings, material_approvals=(), data_class_gates=gates)


def _events(world: ResearchWorld, run_id: str) -> list[dict[str, Any]]:
    with world.sessions() as session:
        return DeepResearchRuns(session, world.lead_scope(session)).events(run_id, limit=2000)


def test_under_enforce_an_unclassified_design_parks_the_run_and_sends_nothing(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    agents = RecordedAgents(ANSWERS)
    runtime = deep_research_runtime(
        _unclassified(research, DataClassGates.ENFORCE),
        env={"AIA_DEEP_RESEARCH_ENABLED": "true"},
        transport=agents,
        signer=Signer(),
    )
    assert runtime is not None and runtime.config.class_gates is DataClassGates.ENFORCE
    run_id = start(research)
    drain(worker(research, database_url, store, build, runtime))
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    attempt = run["steps"][0]["attempts"][-1]
    assert attempt["error"]["reason"] == "egress_unclassified_material"
    assert agents.requests == []
    assert not any("class_advisory" in e["payload"] for e in _events(research, run_id))


def test_under_advisory_an_unclassified_design_takes_the_design_rule_and_says_so(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    runtime = deep_research_runtime(
        _unclassified(research, DataClassGates.ADVISORY),
        env={"AIA_DEEP_RESEARCH_ENABLED": "true"},
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )
    assert runtime is not None and runtime.config.class_gates is DataClassGates.ADVISORY
    run_id = start(research)
    drain(worker(research, database_url, store, build, runtime))
    with research.sessions() as session:
        run = DeepResearchRuns(session, research.lead_scope(session)).get(run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED  # never parked on the class
    recorded = [
        e["payload"]["class_advisory"]
        for e in _events(research, run_id)
        if ("class_advisory" in e["payload"])
    ]
    assert recorded == [
        {
            "gate": "deep_research_design",
            "rule": "egress_unclassified_material",
            "data_class": DataClass.CLASS_B_DERIVED_CLIENT.value,
            "advisory": True,
        }
    ]


def test_brave_composed_declares_the_exception_and_takes_any_class_only_under_advisory(
    research: ResearchWorld,  # noqa: F811
) -> None:
    for gates, refused in ((DataClassGates.ENFORCE, True), (DataClassGates.ADVISORY, False)):
        settings = dataclasses.replace(
            ai_settings(research.client_id, approved_for=DEVELOP_ROUTE), data_class_gates=gates
        )
        runtime = deep_research_runtime(
            settings, env=BRAVE, transport=RecordedAgents(ANSWERS), signer=Signer()
        )
        assert runtime is not None and runtime.retrieval is not None
        search = runtime.retrieval.search_route
        assert search.route_id == "brave-web-search" and search.any_class_when_advisory
        # The fetch route declares nothing: pages stay Class C only in both modes.
        assert not runtime.retrieval.fetch_route.any_class_when_advisory
        # Advisory lifts the class, never the price or the sign-off.
        assert search.needs_sign_off and runtime.sign_off_routes() == ("brave-web-search",)
        with research.sessions() as session:
            gate = RetrievalGate(
                retrieval=runtime.retrieval,
                scope=research.lead_scope(session),
                meter=_StudyMeter(),
                client_terms=(),
                class_a_texts=(),
                class_gates=runtime.config.class_gates,
            )
            for cls in (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, DataClass.CLASS_B_DERIVED_CLIENT):
                assert (gate.refusal_for_class(cls) is not None) is refused


class _StudyMeter(InMemoryToolLedger):
    """A meter that holds tool spend against the study, as ``StepToolMeter`` does."""

    def __init__(self) -> None:
        super().__init__(budget_usd=None)

    @property
    def charges_study_budget(self) -> bool:
        return True
