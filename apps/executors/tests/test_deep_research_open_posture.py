"""Deep Research under a client's OPEN posture (deep-research-web-search chunk 53, ADR 0032).

OPEN is the organization's recorded statement that a client's material may be used in public
search queries. Pinned on the run at enqueue, it lowers the class of that run's web egress, and
only that: the queries leave as Class C with the reason ``posture:OPEN``, the model requests keep
the design's rule class, and an edited design no operator classified runs its web tracks. A
CLASSIFIED (or never set) client changes nothing: its unclassified design still parks the run
and nothing is sent. Nothing a query says lowers its class; only the pinned posture does.

Shared helpers come from conftest fixtures (``world``, ``deep_research_fixture``), never from
another test module (AGENTS.md § pytest).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.web_retrieval import RetrievalGate, WebRetrieval
from aia_core.domain.deep_research.classification import OPEN_POSTURE_REASON
from aia_core.domain.deep_research.contracts import (
    ClientTerm,
    QueryDecision,
    RetrievalMode,
    StopReason,
)
from aia_core.domain.deep_research.tooling import TOOL_EVENT_KINDS, InMemoryToolLedger, ToolOutcome
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.model_adapters.transport import EnvironmentCredentials
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import AIUsageEventRow
from aia_core.infrastructure.web_retrieval import FetchedResponse
from aia_core.infrastructure.web_retrieval_brave import BraveSearch
from aia_executors.deep_research import DeepResearchRuntime, deep_research_registry
from aia_executors.deep_research_runtime import deep_research_runtime
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select

BRAVE = {
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "fictional-brave-key-0000",
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-09",
}
NOW = datetime(2026, 10, 28, 22, 0, tzinfo=UTC)


class _RecordedBrave:
    """Brave's transport, recorded: every search answered with an empty result list. Nothing
    leaves the process; each request is kept, so a test can say what would have been sent."""

    retrieval_mode = RetrievalMode.LIVE

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(
        self, url: str, *, address: str, max_bytes: int, headers: Mapping[str, str]
    ) -> FetchedResponse:
        self.urls.append(url)
        body = {"type": "search", "query": {}, "web": {"type": "search", "results": []}}
        return FetchedResponse(
            status=200,
            headers={"content-type": "application/json; charset=utf-8"},
            body=json.dumps(body).encode(),
            truncated=False,
            provider_request_id=None,
        )


class _Resolver:
    def resolve(self, host: str) -> tuple[str, ...]:
        return ("93.184.215.14",)  # public, as the gate requires; never dialled


class _StudyMeter(InMemoryToolLedger):
    def __init__(self) -> None:
        super().__init__(budget_usd=None)

    @property
    def charges_study_budget(self) -> bool:
        return True


def _set_posture(world: Any, posture: str | None) -> None:
    with world.sessions() as session:
        ScopeRepository(session).set_client_rules(
            world.admin_context(session),
            world.client_id,
            changes={"data_posture": posture},
            now=NOW,
        )
        session.commit()


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


def _brave_runtime(
    world: Any, fx: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[DeepResearchRuntime, _RecordedBrave, Any]:
    """Brave on a route approved for B and C, under enforce, with no operator record of the
    design: the shape develop's Deep Research meets once a design is edited."""
    # The sign-off (ADR 0022) is its own test; this one is about the posture alone.
    monkeypatch.setattr(DeepResearchRuntime, "sign_off_routes", lambda self: ())
    settings = dataclasses.replace(
        fx.ai_settings(world.client_id, approved_for=fx.TEST_ROUTE),
        material_approvals=(),
        data_class_gates=DataClassGates.ENFORCE,
    )
    agents = fx.RecordedAgents(fx.ANSWERS)
    composed = deep_research_runtime(settings, env=BRAVE, transport=agents, signer=fx.Signer())
    assert composed is not None and composed.retrieval is not None
    brave = _RecordedBrave()
    retrieval: WebRetrieval = dataclasses.replace(
        composed.retrieval,
        search=BraveSearch(
            credentials=EnvironmentCredentials(environ=BRAVE),
            resolver=_Resolver(),
            transport=brave,
        ),
    )
    return dataclasses.replace(composed, retrieval=retrieval), brave, agents


def _drain(
    world: Any, database_url: str, store: InMemoryArtifactStore, build: Any, runtime: Any
) -> None:
    worker = Worker(
        session_factory=world.sessions,
        executors=deep_research_registry(store=store, build=build, runtime=runtime),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="deep-research-open-posture-test",
            executors="aia_executors.registry:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )
    for _ in range(20):
        if worker.run_once() is None:
            return
    raise AssertionError("the worker kept finding work")


def _brave_dispatches(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        e
        for e in events
        if e["message"] == TOOL_EVENT_KINDS[ToolOutcome.DISPATCHED]
        and e["payload"].get("route_id") == "brave-web-search"
    ]


def test_an_open_clients_unclassified_design_runs_its_web_tracks_on_the_posture(
    world: Any,
    deep_research_fixture: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fx = deep_research_fixture
    runtime, brave, agents = _brave_runtime(world, fx, monkeypatch)
    _set_posture(world, "OPEN")
    run_id = _start(world, fx.DESIGN)
    _drain(world, database_url, store, build, runtime)
    run, events = _run(world, run_id)
    assert run["metadata"]["client_posture"] == "OPEN"
    assert run["status"] is WorkflowRunStatus.COMPLETED  # never parked for want of a record
    refused = [
        e
        for e in events
        if e["payload"].get("stop_reason") == StopReason.SEARCH_ROUTE_REFUSED.value
    ]
    dispatched = _brave_dispatches(events)
    assert refused == [] and dispatched and len(brave.urls) == len(dispatched)
    # The model requests keep the design's rule class: Class B, never lowered to C.
    assert agents.requests
    with world.sessions() as session:
        sent_as = set(
            session.scalars(
                select(AIUsageEventRow.data_class).where(AIUsageEventRow.run_id == run_id)
            )
        )
    assert sent_as == {DataClass.CLASS_B_DERIVED_CLIENT.value}


@pytest.mark.parametrize("posture", ["CLASSIFIED", None])
def test_a_classified_or_unset_clients_unclassified_design_still_parks_and_sends_nothing(
    world: Any,
    deep_research_fixture: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
    posture: str | None,
) -> None:
    fx = deep_research_fixture
    runtime, brave, agents = _brave_runtime(world, fx, monkeypatch)
    _set_posture(world, posture)
    run_id = _start(world, fx.DESIGN)
    _drain(world, database_url, store, build, runtime)
    run, events = _run(world, run_id)
    assert run["metadata"]["client_posture"] == "CLASSIFIED"
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert run["steps"][0]["attempts"][-1]["error"]["reason"] == "egress_unclassified_material"
    assert brave.urls == [] and agents.requests == [] and _brave_dispatches(events) == []


def test_a_run_keeps_the_posture_it_was_enqueued_under(
    world: Any,
    deep_research_fixture: Any,
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Switched to OPEN after enqueue, a CLASSIFIED run still parks: its request is what runs."""
    fx = deep_research_fixture
    runtime, brave, _agents = _brave_runtime(world, fx, monkeypatch)
    run_id = _start(world, fx.DESIGN)
    _set_posture(world, "OPEN")
    _drain(world, database_url, store, build, runtime)
    run, _events = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.WAITING_PROVIDER
    assert brave.urls == []


def _gate(world: Any, session: Any, runtime: DeepResearchRuntime, *, open_posture: bool) -> Any:
    assert runtime.retrieval is not None
    return RetrievalGate(
        retrieval=runtime.retrieval,
        scope=world.lead_scope(session),
        meter=_StudyMeter(),
        client_terms=(ClientTerm(term="Acme Pivovar", source="client.name"),),
        class_a_texts=("jedna dvě tři čtyři pět šest sedm",),
        class_gates=DataClassGates.ENFORCE,
        open_posture=open_posture,
    )


def test_only_the_pinned_posture_lowers_a_query_never_its_words(
    world: Any, deep_research_fixture: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fx = deep_research_fixture
    runtime, brave, _agents = _brave_runtime(world, fx, monkeypatch)
    query = "Acme Pivovar jedna dvě tři čtyři pět"
    with world.sessions() as session:
        classified = _gate(world, session, runtime, open_posture=False).search(
            query,
            context_class=DataClass.CLASS_C_INTERNAL,
            track_id="t1",
            max_results=3,
        )
        # The client's name and a run of Class A text: Class A, refused before anything left.
        assert classified.record.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
        assert classified.record.decision is QueryDecision.REFUSED
        assert brave.urls == []
        opened = _gate(world, session, runtime, open_posture=True).search(
            query,
            context_class=DataClass.CLASS_B_DERIVED_CLIENT,
            track_id="t1",
            max_results=3,
        )
    assert opened.record.data_class is DataClass.CLASS_C_INTERNAL
    assert opened.record.class_reasons == (OPEN_POSTURE_REASON,)
    assert opened.record.decision is QueryDecision.SENT and len(brave.urls) == 1
