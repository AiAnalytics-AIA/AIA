"""Interpretation Research over HTTP (ADR 0021, plan ``deep-research-web-search.md`` chunk 30).

A research run on fictional fieldwork produces a specification, a dataset, an aggregate and
a Sociomap through the real executors; ``POST …/deep-research/runs/interpretation`` then
starts Interpretation Research over one of its results. What is pinned:

* the route answers 201 with the run (its purpose, target and pinned lineage), 200 for the
  same spec again, and the run researches the target's mission, not the design's subjects;
* a result of another Study is 404; an entity the artifact does not hold, a design target
  and a malformed body are 422; nothing is enqueued for any of them;
* the study's spend limit asks first, as for a design run, and the yes is recorded once;
* the retry route re-freezes the stored target with the artifact store;
* the design-proposal route still refuses an interpretation run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ApprovalDecisionRow, WorkflowRunRow
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"
DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "research_plan": {"research_questions": ["Co dojíždějící ráno pijí?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}
#: The route's prices and limits, as ``test_deep_research_spend_api.py`` states them.
ROUTE = {
    "bedrock_input_usd_per_mtok": 3.0,
    "bedrock_output_usd_per_mtok": 15.0,
    "bedrock_context_window_tokens": 200_000,
    "ai_research_max_output_tokens": 8_192,
}


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed SQLite database (these tests start a worker, AGENTS.md § SQLite), the
    fictional fieldwork source, and the route's prices for the spend limit."""
    update: dict[str, Any] = {
        **ROUTE,
        "research_fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE,
    }
    if not settings.database_url or ":memory:" in settings.database_url:
        update["database_url"] = f"sqlite+pysqlite:///{tmp_path / 'api.db'}"
    return settings.model_copy(update=update)


def _study(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}"


def _url(world: Any, study: str = "primary") -> str:
    return f"{_study(world, study)}/deep-research/runs"


def _worker(app: FastAPI) -> Worker:
    """The real research executors with fictional fieldwork; no Deep Research runtime."""
    from aia_core.infrastructure.build_identity import BuildIdentity
    from aia_executors import workbench

    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors=workbench.workbench_registry_for(
            store=app.state.artifact_store, build=BuildIdentity(sha="a15be650937aacaa")
        ),
        settings=WorkerSettings(
            database_url=settings.database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="interpretation-api-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


def _results(app: FastAPI, c: TestClient, world: Any) -> dict[str, Any]:
    """A completed research run of the primary study: its id and its steps' artifacts."""
    revision = c.post(
        f"{_study(world)}/design/revisions", json={"content": DESIGN, "source_stage": "run"}
    )
    assert revision.status_code == 201, revision.text
    started = c.post(
        f"{_study(world)}/research/runs",
        json={"design_revision_id": revision.json()["revision_id"]},
    )
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]
    worker = _worker(app)
    while worker.run_once() is not None:
        pass
    run = c.get(f"{_study(world)}/research/runs/{run_id}").json()
    assert run["status"] == "COMPLETED", run
    steps = {s["node_key"]: s["artifact_id"] for s in run["steps"]}
    sociomap = c.get(f"{_study(world)}/research/runs/{run_id}/artifacts/{steps['sociomap']}")
    (battery,) = sociomap.json()["payload"]["sociomap"]["batteries"]
    return {
        "run_id": run_id,
        "revision_id": revision.json()["revision_id"],
        "aggregate": steps["aggregate"],
        "sociomap": steps["sociomap"],
        "battery_id": battery["battery_id"],
        "objects": [o["id"] for o in battery["objects"]],
    }


def _object_target(results: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {
        "kind": "SOCIOMAP_OBJECT",
        "research_run_id": results["run_id"],
        "sociomap_artifact_id": results["sociomap"],
        "battery_id": results["battery_id"],
        "object_id": results["objects"][0],
        **over,
    }


def _body(target: dict[str, Any], **over: Any) -> dict[str, Any]:
    return {"target": target, "preset_name": "QUICK", "channels": ["WEB"], **over}


def test_context_report_requires_explicit_completed_owned_research(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    results = _results(app, researcher, world)
    review = researcher.post(f"{_url(world)}/interpretation", json=_body(_object_target(results)))
    assert review.status_code == 201, review.text
    url = f"{_study(world)}/research/runs/{results['run_id']}/report/context/download"
    assert researcher.get(url).status_code == 422
    params = {"deep_research_run_id": review.json()["run_id"]}
    pending = researcher.get(url, params=params)
    assert pending.status_code == 409 and pending.json()["code"] == "context_report_refused"
    foreign = (
        f"{_study(world, 'other_client')}/research/runs/{results['run_id']}/report/context/download"
    )
    assert researcher.get(foreign, params=params).status_code == 404
    assert researcher.get(url, params={"deep_research_run_id": "RUN-000000"}).status_code == 404
    assert (
        researcher.get(url, params={"deep_research_run_id": "untrusted-value"}).status_code == 422
    )


def test_the_route_starts_interpretation_over_a_result_once_per_spec(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    results = _results(app, researcher, world)
    target = _object_target(results)
    started = researcher.post(f"{_url(world)}/interpretation", json=_body(target, title="Výklad"))
    assert started.status_code == 201, started.text
    job = started.json()
    assert started.headers["Location"].endswith(f"/deep-research/runs/{job['run_id']}")
    assert job["integration_contract"] == "aia-deep-research-run-spec-1"
    assert job["purpose"] == "INTERPRETATION_RESEARCH" and job["purpose_source"] == "EXPLICIT"
    assert job["target"] == target and job["title"] == "Výklad"
    assert job["lineage"]["kind"] == "INTERPRETATION"
    assert job["lineage"]["research_run_id"] == results["run_id"]
    assert job["lineage"]["design"]["design_revision_id"] == results["revision_id"]
    assert {p["node_key"] for p in job["lineage"]["artifacts"]} == {
        "aggregate",
        "compile",
        "run",
        "sociomap",
    }
    assert job["design_revision_id"] == results["revision_id"]
    assert job["steps"][0]["node_key"] == "plan"
    # The same spec again: the run that exists. The title is not identity.
    again = researcher.post(f"{_url(world)}/interpretation", json=_body(target))
    assert again.status_code == 200 and again.json()["run_id"] == job["run_id"]
    # A design run over the same revision is another run.
    design = researcher.post(
        _url(world),
        json={"design_revision_id": results["revision_id"], "preset_name": "QUICK"},
    )
    assert design.status_code == 201 and design.json()["run_id"] != job["run_id"]
    with create_session_factory(app.state.engine)() as session:
        meta = {
            r.run_id: r.metadata_json
            for r in session.scalars(select(WorkflowRunRow)).all()
            if r.workflow_type == "deep_research"
        }
    assert (
        meta[job["run_id"]]["request_fingerprint"]
        != meta[design.json()["run_id"]]["request_fingerprint"]
    )
    assert meta[job["run_id"]]["subjects"] == 1  # the object: the target's mission


def test_a_result_of_another_study_is_404_and_an_entity_it_does_not_hold_422(
    app: FastAPI, researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    results = _results(app, researcher, world)
    target = _object_target(results)
    # Through another Study's path the result does not exist, whoever asks.
    for member in (researcher, other_client_lead):
        refused = member.post(f"{_url(world, 'other_client')}/interpretation", json=_body(target))
        assert refused.status_code == 404, refused.text
    unknown_run = _object_target(results, research_run_id="RUN-0000000000000000")
    assert (
        researcher.post(f"{_url(world)}/interpretation", json=_body(unknown_run)).status_code == 404
    )
    # An entity the artifact does not hold, and a design target: 422, named.
    for bad in (
        _object_target(results, object_id="neexistuje"),
        _object_target(results, battery_id="neexistuje"),
        {
            "kind": "RESULT_QUESTION",
            "research_run_id": results["run_id"],
            "aggregate_artifact_id": results["aggregate"],
            "question_id": "q99",
        },
        {"kind": "DESIGN_REVISION", "design_revision_id": results["revision_id"]},
    ):
        refused = researcher.post(f"{_url(world)}/interpretation", json=_body(bad))
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "research_input"
    # A malformed body is the framework's 422.
    for body in (
        _body(target, preset_name="UNKNOWN"),
        _body(target, channels=["WEB", "WEB"]),
        _body({**target, "kind": "SEGMENT"}),
        {**_body(target), "purpose": "DESIGN_RESEARCH"},
    ):
        assert researcher.post(f"{_url(world)}/interpretation", json=body).status_code == 422
    assert researcher.get(_url(world)).json() == []  # nothing was enqueued


def test_the_spend_limit_asks_first_and_the_yes_is_recorded_once(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    results = _results(app, researcher, world)
    target = _object_target(results)
    assert (
        researcher.put(f"{_study(world)}/spend-confirm", json={"limit_usd": 0.01}).status_code
        == 200
    )
    asked = researcher.post(f"{_url(world)}/interpretation", json=_body(target))
    assert asked.status_code == 409, asked.text
    assert asked.json()["code"] == "cost_confirmation_required"
    ceiling = asked.json()["details"]["ceiling_usd"]
    assert ceiling > 0.01 and researcher.get(_url(world)).json() == []
    low = researcher.post(
        f"{_url(world)}/interpretation", json=_body(target, confirm_cost_usd=ceiling / 2)
    )
    assert low.status_code == 409
    started = researcher.post(
        f"{_url(world)}/interpretation", json=_body(target, confirm_cost_usd=ceiling)
    )
    assert started.status_code == 201, started.text
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
        ).all()
        assert [(r.run_id, r.decision) for r in rows] == [(started.json()["run_id"], "confirm")]
    again = researcher.post(f"{_url(world)}/interpretation", json=_body(target))
    assert again.status_code == 200 and again.json()["run_id"] == started.json()["run_id"]


def test_the_retry_route_refreezes_the_stored_target(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    results = _results(app, researcher, world)
    target = _object_target(results)
    job = researcher.post(f"{_url(world)}/interpretation", json=_body(target)).json()
    run_url = f"{_url(world)}/{job['run_id']}"
    assert researcher.post(f"{run_url}/cancel").status_code == 200
    retried = researcher.post(f"{run_url}/retry")
    assert retried.status_code == 201, retried.text
    body = retried.json()
    assert body["run_id"] != job["run_id"] and body["purpose"] == "INTERPRETATION_RESEARCH"
    assert (body["target"], body["lineage"]) == (job["target"], job["lineage"])


def test_the_design_proposal_route_refuses_an_interpretation_run(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Chunk 29's route proposes only from Design Research. The run is marked completed in the
    database: the API's worker composes no Deep Research runtime, and the refusal is the
    purpose's, read before any bundle."""
    results = _results(app, researcher, world)
    job = researcher.post(
        f"{_url(world)}/interpretation", json=_body(_object_target(results))
    ).json()
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, job["run_id"])
        assert row is not None
        row.status = "COMPLETED"
        session.commit()
    run_url = f"{_url(world)}/{job['run_id']}"
    proposal = researcher.get(f"{run_url}/design-proposal")
    assert proposal.status_code == 409 and proposal.json()["code"] == "not_design_research"
    accept = {"item_ids": ["DRP-" + "0" * 24], "expected_revision_id": results["revision_id"]}
    refused = researcher.post(f"{run_url}/design-proposal/accept", json=accept)
    assert refused.status_code == 409 and refused.json()["code"] == "not_design_research"
