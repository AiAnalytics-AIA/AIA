"""A run's or job's ``actual_cost_usd`` is its spend's total, unknown while a call's outcome is.

The attempts' recorded cost was no such figure (F-R10, artifact-results.md): an attempt that ends
with a paid call never answered is charged its whole hold as exposure, an upper bound, and keeps it
even when the step completes (the flag is set known afterwards); a call still out is left out; an
operator's later resolution reaches the usage ledger alone. The figure is now read from the same
ledger fold as ``spend`` (spend_attribution.run_spend), so it agrees with it on every read: a
research run, an agent job and a Deep Research run alike.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import (
    AIUsageEventRow,
    BudgetReservationRow,
    StepAttemptRow,
    StepRunRow,
    StudyRow,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

API = "/api/v1"
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit, jak lidé připravují kávu.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "n": 60,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


def _attempt(app: FastAPI, run_id: str, *, known: bool, cost: float) -> None:
    """The run's first step's attempt with a paid call sent, as the engine leaves it: ``cost`` is
    what the attempt records, the whole hold for a call never answered."""
    with create_session_factory(app.state.engine)() as session:
        step = session.scalars(select(StepRunRow).where(StepRunRow.run_id == run_id)).first()
        assert step is not None
        session.add(
            StepAttemptRow(
                attempt_id=f"ATT-{run_id[-12:]}",
                step_id=step.step_id,
                attempt_number=1,
                status="SUCCEEDED" if known else "FAILED",
                paid_call_dispatched=True,
                paid_call_outcome_known=known,
                actual_cost_usd=cost,
            )
        )
        session.commit()


def _usage(app: FastAPI, world: Any, run_id: str, call: str, outcome: str, cost: float) -> None:
    """A usage-ledger row of ``run_id``: only what the fold reads is meaningful."""
    with create_session_factory(app.state.engine)() as session:
        study = session.get(StudyRow, world.study_id())
        assert study is not None
        session.add(
            AIUsageEventRow(
                event_id=f"{call}-{outcome}",
                call_id=call,
                outcome=outcome,
                purpose="fieldwork",
                organization_id=study.organization_id,
                client_id=study.client_id,
                study_id=study.study_id,
                actor_id="worker:test",
                run_id=run_id,
                agent_id="aia.test",
                agent_version="1",
                prompt_id="p",
                prompt_version="1",
                capability="c",
                policy_version="1",
                runtime_version="1",
                provider="aws_bedrock",
                model="m",
                route_id="r",
                data_class="B",
                residency_zone="EU",
                cost_usd=cost,
                cost_basis="METERED",
                occurred_at=datetime.now(UTC),
            )
        )
        session.commit()


def _tool_hold(app: FastAPI, world: Any, run_id: str, amount: float) -> None:
    """A settled hold no ledger row names (a priced tool call)."""
    with create_session_factory(app.state.engine)() as session:
        study = session.get(StudyRow, world.study_id())
        assert study is not None
        session.add(
            BudgetReservationRow(
                reservation_id=f"R-{run_id[-12:]}",
                client_id=study.client_id,
                study_id=study.study_id,
                run_id=run_id,
                amount_usd=amount,
                settled_amount_usd=amount,
                status="SETTLED",
                settled_at=datetime.now(UTC),
            )
        )
        session.commit()


def _revision(c: TestClient, world: Any) -> str:
    made = world.design(c, DESIGN, source_stage="brief")
    assert made.status_code in (200, 201), made.text
    return str(made.json()["revision_id"])


def _research_run(c: TestClient, world: Any) -> str:
    started = c.post(
        f"{API}/studies/{world.study_id()}/research/runs",
        json={"design_revision_id": _revision(c, world)},
    )
    assert started.status_code == 201, started.text
    return f"{API}/studies/{world.study_id()}/research/runs/{started.json()['run_id']}"


def _agent_job(c: TestClient, world: Any) -> str:
    base = f"{API}/studies/{world.study_id()}/research/agent-jobs"
    started = c.post(
        base, json={"design_revision_id": _revision(c, world), "action": "analyze_brief"}
    )
    assert started.status_code == 201, started.text
    return f"{base}/{started.json()['run_id']}"


def _deep_research_run(c: TestClient, world: Any) -> str:
    base = f"{API}/studies/{world.study_id()}/deep-research/runs"
    started = c.post(
        base,
        json={
            "design_revision_id": _revision(c, world),
            "preset_name": "QUICK",
            "channels": ["WEB"],
        },
    )
    assert started.status_code == 201, started.text
    return f"{base}/{started.json()['run_id']}"


STARTS = pytest.mark.parametrize("start", [_research_run, _agent_job, _deep_research_run])


def _cost(c: TestClient, url: str) -> Any:
    body = c.get(url)
    assert body.status_code == 200, body.text
    return body.json()["actual_cost_usd"]


@STARTS
def test_a_call_never_answered_leaves_the_cost_unknown_though_its_step_completed(
    researcher: TestClient, world: Any, app: FastAPI, start: Any
) -> None:
    url = start(researcher, world)
    run_id = url.rsplit("/", 1)[1]
    # complete_attempt charged the hold as exposure, then set the outcome known.
    _attempt(app, run_id, known=True, cost=0.10)
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    _usage(app, world, run_id, "c1", "UNCERTAIN", 0.0)
    assert _cost(researcher, url) is None


@STARTS
def test_a_call_resolved_later_reads_its_resolved_cost(
    researcher: TestClient, world: Any, app: FastAPI, start: Any
) -> None:
    url = start(researcher, world)
    run_id = url.rsplit("/", 1)[1]
    _attempt(app, run_id, known=False, cost=0.10)  # the exposure, on the attempt for good
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    _usage(app, world, run_id, "c1", "UNCERTAIN", 0.0)
    _usage(app, world, run_id, "c1", "RESOLVED_BILLED", 0.03)  # an operator's answer
    assert _cost(researcher, url) == pytest.approx(0.03)


@STARTS
def test_the_cost_is_what_the_ledger_and_the_holds_say_was_spent(
    researcher: TestClient, world: Any, app: FastAPI, start: Any
) -> None:
    url = start(researcher, world)
    run_id = url.rsplit("/", 1)[1]
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    _usage(app, world, run_id, "c1", "SUCCEEDED", 0.40)
    _tool_hold(app, world, run_id, 0.25)
    assert _cost(researcher, url) == pytest.approx(0.65)


def test_a_research_runs_cost_agrees_with_its_spend_beside_it(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    url = _research_run(researcher, world)
    run_id = url.rsplit("/", 1)[1]
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    _usage(app, world, run_id, "c1", "SUCCEEDED", 0.40)
    body = researcher.get(url).json()
    assert body["actual_cost_usd"] == pytest.approx(body["spend"]["spent_usd"])
    _usage(app, world, run_id, "c2", "DISPATCHED", 0.0)
    body = researcher.get(url).json()
    assert body["spend"]["uncertain_calls"] == 1 and body["actual_cost_usd"] is None


@STARTS
def test_a_call_still_out_reads_unknown_until_it_is_answered(
    researcher: TestClient, world: Any, app: FastAPI, start: Any
) -> None:
    """While a call is out the figure is unknown, by the rule spend reads (never the sum so far
    as if it were the cost); once it is answered, its cost."""
    url = start(researcher, world)
    run_id = url.rsplit("/", 1)[1]
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    assert _cost(researcher, url) is None
    _usage(app, world, run_id, "c1", "SUCCEEDED", 0.02)
    assert _cost(researcher, url) == pytest.approx(0.02)
