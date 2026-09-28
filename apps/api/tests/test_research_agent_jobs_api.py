"""The native agent boundary enqueues only: no model work in HTTP."""

from pathlib import Path
from typing import Any

import pytest
from aia_core.application.research import research_artifacts
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.storage import ArtifactStore
from aia_worker.executor import StepContext, StepInput, StepOutcome, Succeeded
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Settings


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed SQLite database: one test here starts a worker (AGENTS.md § SQLite)."""
    if settings.database_url and ":memory:" not in settings.database_url:
        return settings
    return settings.model_copy(update={"database_url": f"sqlite+pysqlite:///{tmp_path / 'api.db'}"})


def base(world: Any, study: str = "primary") -> str:
    return f"/api/v1/studies/{world.study_id(study)}/research/agent-jobs"


def revision(client: TestClient, world: Any) -> str:
    response = client.post(
        f"/api/v1/studies/{world.study_id()}/design/revisions",
        json={"content": {"title": "Fictional", "goal": "Test concept"}, "source_stage": "brief"},
    )
    assert response.status_code == 201
    return str(response.json()["revision_id"])


def test_native_job_start_is_idempotent_and_returns_only_public_state(
    researcher: TestClient,
    viewer: TestClient,
    world: Any,
) -> None:
    rid = revision(researcher, world)
    body = {"design_revision_id": rid, "action": "analyze_brief"}
    started = researcher.post(base(world), json=body)
    assert started.status_code == 201, started.text
    job = started.json()
    assert job["status"] == "RUNNING" and job["context_sha256"]
    assert "snapshot" not in job and "metadata" not in job
    repeated = researcher.post(base(world), json=body)
    assert repeated.status_code == 200 and repeated.json()["run_id"] == job["run_id"]
    assert viewer.post(base(world), json=body).status_code == 403
    read = viewer.get(f"{base(world)}/{job['run_id']}")
    assert read.status_code == 200 and read.json()["actual_cost_usd"] is None
    assert researcher.get(base(world)).json()[0]["run_id"] == job["run_id"]
    assert researcher.get(f"{base(world, 'sibling')}/{job['run_id']}").status_code == 404
    assert researcher.get(f"{base(world)}/{job['run_id']}/result").status_code == 409


def test_agent_api_rejects_authority_and_unimplemented_actions(
    researcher: TestClient,
    world: Any,
) -> None:
    rid = revision(researcher, world)
    for extra in ({"provider": "anthropic"}, {"client_id": "different"}, {"model": "unreviewed"}):
        r = researcher.post(
            base(world), json={"design_revision_id": rid, "action": "analyze_brief", **extra}
        )
        assert r.status_code == 422
    assert (
        researcher.post(
            base(world), json={"design_revision_id": rid, "action": "web_research"}
        ).status_code
        == 422
    )


def test_cancel_is_scoped_and_requires_cancel_permission(
    researcher: TestClient,
    viewer: TestClient,
    world: Any,
) -> None:
    rid = revision(researcher, world)
    job = researcher.post(
        base(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()
    url = f"{base(world)}/{job['run_id']}/cancel"
    assert viewer.post(url).status_code == 403
    cancelled = researcher.post(url)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"


class _Proposes:
    """Stands in for the model: stores the proposal artifact the real executor would."""

    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        with context.transaction() as (session, _):
            artifact, _created = research_artifacts(session, context.scope, self._store).put_json(
                payload={"result": {"project": {"title": "Proposed"}}, "provenance": {}},
                project_id=step.project_id,
                revision=step.project_revision,
                stage_type=step.stage_type,
                artifact_type="research_agent_proposal",
            )
        return Succeeded(output={"artifact_id": artifact.artifact_id})


def _worker(app: FastAPI) -> Worker:
    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors={"research_agent": _Proposes(app.state.artifact_store)},
        settings=WorkerSettings(
            database_url=settings.database_url or "sqlite+pysqlite:///:memory:",
            executors="aia_executors.registry:build_registry",
            worker_id="agent-jobs-test-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_a_corrupt_proposal_is_a_409_and_stays_marked_corrupt(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
    damage: str,
) -> None:
    """Regression: a proposal whose bytes failed verification answered 500.

    The storage error escaped the route's error mapping, so the caller got
    ``internal_error`` and ``get_session`` rolled the CORRUPT mark back with it.
    """
    rid = revision(researcher, world)
    job = researcher.post(
        base(world), json={"design_revision_id": rid, "action": "analyze_brief"}
    ).json()
    done = _worker(app).run_once()
    assert done is not None and done.ending == "completed"
    url = f"{base(world)}/{job['run_id']}"
    assert researcher.get(f"{url}/result").status_code == 200
    (step,) = researcher.get(url).json()["steps"]
    damage_artifact(step["artifact_id"], damage)

    refused = researcher.get(f"{url}/result")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(step["artifact_id"]) == "CORRUPT"
    accepted = researcher.post(f"{url}/accept", json={"expected_revision_id": rid})
    assert accepted.status_code == 409 and accepted.json()["code"] == "artifact_corrupt"
