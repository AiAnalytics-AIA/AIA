"""A research run's spend over HTTP (artifact-fieldwork FLD4): what the run has spent, holds
open and could not settle, read by the rules a person's spend is (Q40), whoever it is booked to.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import AIUsageEventRow, BudgetReservationRow, StudyRow
from fastapi import FastAPI
from fastapi.testclient import TestClient

API = "/api/v1"

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
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


def _run(c: TestClient, world: Any) -> str:
    made = world.design(c, DESIGN)
    assert made.status_code in (200, 201), made.text
    started = c.post(
        f"{API}/studies/{world.study_id()}/research/runs",
        json={"design_revision_id": made.json()["revision_id"]},
    )
    assert started.status_code == 201, started.text
    return str(started.json()["run_id"])


def _hold(app: FastAPI, world: Any, run_id: str, rid: str, status: str, amount: float) -> None:
    with create_session_factory(app.state.engine)() as session:
        study = session.get(StudyRow, world.study_id())
        assert study is not None
        settled = status != "RESERVED"
        session.add(
            BudgetReservationRow(
                reservation_id=rid,
                client_id=study.client_id,
                study_id=study.study_id,
                run_id=run_id,
                amount_usd=amount,
                settled_amount_usd=amount if settled else 0.0,
                status=status,
                settled_at=datetime.now(UTC) if settled else None,
                charged_to_user_id="someone-else",
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
                charged_to_user_id="someone-else",
                agent_id="aia.research.respondent",
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


def test_a_run_with_nothing_charged_has_spent_a_known_zero(
    researcher: TestClient, world: Any
) -> None:
    run_id = _run(researcher, world)
    body = researcher.get(f"{API}/studies/{world.study_id()}/research/runs/{run_id}").json()
    assert body["spend"] == {"spent_usd": 0.0, "reserved_usd": 0.0, "uncertain_calls": 0}


def test_a_run_reads_its_own_holds_whoever_they_are_booked_to(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    run_id = _run(researcher, world)
    _hold(app, world, run_id, "r-open", "RESERVED", 2.0)
    _hold(app, world, run_id, "r-tool", "SETTLED", 0.25)
    _hold(app, world, run_id, "r-unknown", "SETTLED_UNCERTAIN", 0.10)
    _hold(app, world, "RUN-another", "r-other", "SETTLED", 9.0)  # another run's: not this one's
    body = researcher.get(f"{API}/studies/{world.study_id()}/research/runs/{run_id}").json()
    assert body["spend"]["spent_usd"] == pytest.approx(0.35)
    assert body["spend"]["reserved_usd"] == pytest.approx(2.0)
    assert body["spend"]["uncertain_calls"] == 1


def test_a_listed_run_carries_no_spend(researcher: TestClient, world: Any) -> None:
    _run(researcher, world)
    [listed] = researcher.get(f"{API}/studies/{world.study_id()}/research/runs").json()["items"]
    assert listed["spend"] is None


def test_a_runs_model_calls_are_spent_and_one_in_flight_is_uncertain(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    run_id = _run(researcher, world)
    _usage(app, world, run_id, "c1", "DISPATCHED", 0.0)
    _usage(app, world, run_id, "c1", "SUCCEEDED", 0.40)
    _usage(app, world, run_id, "c2", "DISPATCHED", 0.0)  # no outcome: uncertain, never zero
    _usage(app, world, "RUN-another", "c3", "SUCCEEDED", 7.0)
    spend = researcher.get(f"{API}/studies/{world.study_id()}/research/runs/{run_id}").json()[
        "spend"
    ]
    assert spend["spent_usd"] == pytest.approx(0.40)
    assert spend["uncertain_calls"] == 1


def test_a_run_records_why_its_ceiling_was_unknown(researcher: TestClient, world: Any) -> None:
    """FLD4d: a deployment that names no fieldwork reservation gives no ceiling; the run says why,
    never a zero."""
    run_id = _run(researcher, world)
    body = researcher.get(f"{API}/studies/{world.study_id()}/research/runs/{run_id}").json()
    assert body["cost_ceiling"] == {"usd": None, "unknown": "fieldwork_reservation_missing"}
    # A listed run carries what it recorded too.
    [listed] = researcher.get(f"{API}/studies/{world.study_id()}/research/runs").json()["items"]
    assert listed["cost_ceiling"] == body["cost_ceiling"]
