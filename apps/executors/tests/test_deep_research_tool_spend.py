"""A priced tool call is charged to the study (plan ``deep-research-web-search.md`` 23c).

Through the real worker loop and its step context: a step that searches through the
retrieval gate over :class:`StepToolMeter` holds each priced call against the study's budget
before it leaves, marks the hold dispatched before the call does, and settles it once at what
the gate charged -- the route's price for an answered call, the ceiling for a lost one,
nothing for one that never left. A call the study's budget cannot hold is never sent, and
the step waits for a person. The routes are doubles that say LIVE; nothing reaches a network.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from aia_core.application.web_retrieval import RetrievalGate, WebRetrieval
from aia_core.domain.ai_contracts import Delivery
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.tooling import ToolKind, ToolOutcome, ToolRoute
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.domain.workflow import StepDefinition, StepRunStatus
from aia_core.infrastructure.tables import BudgetReservationRow, StepAttemptRow, StudyRow
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    RecordedResolver,
    SearchResponse,
    ToolCallFailed,
    WebFetcher,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.deep_research import StepToolMeter
from aia_worker.executor import StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

KIND = "priced_search_test"
PRICE = 0.01
NOW = datetime(2026, 10, 9, tzinfo=UTC)


def _route(tool: ToolKind) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id=f"{tool.value}-live",
            provider="live",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=tool,
        adapter_id=f"live-{tool.value.split('_')[1]}-v1",
        retrieval_mode=RetrievalMode.LIVE,
        price_usd_per_call=PRICE,
    )


@dataclass(slots=True)
class _Search:
    """Answers, or fails as scripted; records what the study's hold looked like when called."""

    script: list[Any]
    sessions: sessionmaker[Session]
    adapter_id: str = "live-search-v1"
    calls: list[str] = field(default_factory=list)
    dispatched_holds: list[int] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        self.calls.append(query)
        with self.sessions() as session:
            # The hold is marked dispatched, and committed, before the call leaves.
            self.dispatched_holds.append(
                len(
                    session.scalars(
                        select(StepAttemptRow).where(StepAttemptRow.paid_call_dispatched)
                    ).all()
                )
            )
        failure = self.script.pop(0)
        if failure is not None:
            raise failure
        return SearchResponse(hits=(), provider_request_id=f"p-{len(self.calls)}", credits=1)


@dataclass(slots=True)
class _NoPages:
    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        raise AssertionError("no page is fetched here")


@dataclass(slots=True)
class _PricedSearchExecutor:
    """Searches each query of its payload through a gate over the step's own meter."""

    search: _Search
    outcomes: list[ToolOutcome] = field(default_factory=list)

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        meter = StepToolMeter.resuming(context, clock=lambda: NOW)
        gate = RetrievalGate(
            retrieval=WebRetrieval(
                search_route=_route(ToolKind.WEB_SEARCH),
                fetch_route=_route(ToolKind.WEB_FETCH),
                search=self.search,
                fetcher=WebFetcher(
                    transport=_NoPages(),
                    resolver=RecordedResolver(hosts={}),
                    adapter_id="live-fetch-v1",
                    clock=lambda: NOW,
                ),
            ),
            scope=context.scope,
            meter=meter,
            client_terms=(),
            class_a_texts=(),
            clock=lambda: NOW,
        )
        for query in step.payload["queries"]:
            gate.search(
                query, context_class=DataClass.CLASS_C_INTERNAL, track_id="T", max_results=3
            )
        self.outcomes = [e.outcome for e in meter.events()]
        return Succeeded(output={"spent": meter.committed_usd()})


def _worker(
    sessions: sessionmaker[Session], database_url: str, executor: _PricedSearchExecutor
) -> Worker:
    return Worker(
        session_factory=sessions,
        executors={KIND: executor},
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="tool-spend-test",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _run(world: Any, queries: list[str], *, budget: float) -> str:
    with world.sessions() as session:
        study = session.get(StudyRow, world.study_id)
        assert study is not None
        study.budget_usd, study.spent_usd = budget, 0.0
        run_id = WorkflowRepository(session, world.lead_scope(session)).create_run(
            project_id=world.project_id,
            project_revision=1,
            workflow_type="tool-spend-test",
            steps=[StepDefinition(node_key="search", kind=KIND)],
            idempotency_key=f"tool-spend:{budget}:{len(queries)}",
            step_inputs={"search": {"queries": queries}},
        )
        session.commit()
    return run_id


def _spent(world: Any) -> float:
    with world.sessions() as session:
        study = session.get(StudyRow, world.study_id)
        assert study is not None
        return float(study.spent_usd)


def _holds(world: Any) -> list[tuple[str, float | None]]:
    with world.sessions() as session:
        rows = session.scalars(select(BudgetReservationRow)).all()
        return sorted((r.status, r.settled_amount_usd) for r in rows)


Build = Callable[[list[Any]], tuple[Worker, _PricedSearchExecutor]]


@pytest.fixture
def priced(sessions: sessionmaker[Session], database_url: str) -> Build:
    def go(script: list[Any]) -> tuple[Worker, _PricedSearchExecutor]:
        executor = _PricedSearchExecutor(_Search(script=script, sessions=sessions))
        return _worker(sessions, database_url, executor), executor

    return go


def test_each_answered_call_is_held_before_it_leaves_and_charged_its_price(
    world: Any, priced: Build
) -> None:
    w, executor = priced([None, None])
    run_id = _run(world, ["první", "druhý"], budget=1.0)
    result = w.run_once()
    assert result is not None and result.ending == "completed", result
    assert executor.search.calls == ["první", "druhý"]
    assert executor.search.dispatched_holds == [1, 1]
    assert _spent(world) == pytest.approx(2 * PRICE)
    assert _holds(world) == [("SETTLED", pytest.approx(PRICE))] * 2
    assert executor.outcomes == [
        ToolOutcome.DISPATCHED,
        ToolOutcome.SUCCEEDED,
        ToolOutcome.DISPATCHED,
        ToolOutcome.SUCCEEDED,
    ]
    assert run_id


def test_a_lost_answer_is_charged_its_ceiling_and_one_never_sent_nothing(
    world: Any, priced: Build
) -> None:
    lost = ToolCallFailed("lost", reason="lost", delivery=Delivery.UNKNOWN)
    refused = ToolCallFailed("not sent", reason="no_route", delivery=Delivery.NOT_SENT)
    w, _executor = priced([lost, refused])
    _run(world, ["ztracený", "neodeslaný"], budget=1.0)
    result = w.run_once()
    assert result is not None and result.ending == "completed", result
    assert _spent(world) == pytest.approx(PRICE)  # the lost one at its ceiling; the other 0
    assert _holds(world) == [("SETTLED", 0.0), ("SETTLED", pytest.approx(PRICE))]


def test_a_call_the_study_cannot_hold_is_never_sent_and_the_step_waits(
    world: Any, priced: Build
) -> None:
    w, executor = priced([None, None])
    run_id = _run(world, ["první", "druhý"], budget=0.015)
    w.run_once()
    assert executor.search.calls == ["první"], "the second call was never sent"
    assert _spent(world) == pytest.approx(PRICE)
    with world.sessions() as session:
        run = WorkflowRepository(session, world.lead_scope(session)).get_run(run_id)
    [step] = run["steps"]
    assert step["status"] is StepRunStatus.AWAITING_BUDGET
