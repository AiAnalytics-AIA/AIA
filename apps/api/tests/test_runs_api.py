"""Runs and artifacts over HTTP: the browser's half of the develop vertical slice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.db import create_session_factory
from aia_executors.registry import registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Settings

API = "/api/v1"
BUILD = BuildIdentity(sha="a15be650937aacaa")


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed SQLite database: these tests start a worker (AGENTS.md § SQLite).

    Its heartbeat thread would otherwise share in-memory SQLite's one connection
    and roll back a step's uncommitted artifact row mid-transaction.
    """
    if settings.database_url and ":memory:" not in settings.database_url:
        return settings
    return settings.model_copy(update={"database_url": f"sqlite+pysqlite:///{tmp_path / 'api.db'}"})


def _project(client: TestClient, study_id: str) -> str:
    response = client.post(
        f"{API}/studies/{study_id}/projects",
        json={"title": "Slice", "content": {"goal": "g"}},
    )
    assert response.status_code == 201, response.text
    project_id: str = response.json()["project_id"]
    return project_id


def _worker(app: FastAPI) -> Worker:
    """A worker over the app's database and the app's own artifact store."""
    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors=registry_for(store=app.state.artifact_store, build=BUILD),
        settings=WorkerSettings(
            database_url=settings.database_url or "sqlite+pysqlite:///:memory:",
            executors="aia_executors.registry:build_registry",
            worker_id="api-test-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


def test_run_endpoints_require_authentication(client: TestClient, world: Any) -> None:
    base = f"{API}/studies/{world.study_id()}/projects/PRJ-0000000000abcd"
    assert (
        client.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"}).status_code == 401
    )
    assert client.get(f"{base}/runs").status_code == 401
    assert client.get(f"{base}/runs/RUN-0000000000abcd").status_code == 401
    assert client.get(f"{base}/artifacts/ART-0000000000abcd").status_code == 401


def test_start_run_creates_a_pending_single_step_run(researcher: TestClient, world: Any) -> None:
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    base = f"{API}/studies/{study_id}/projects/{project_id}"

    created = researcher.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"})
    assert created.status_code == 201, created.text
    body = created.json()
    # Derived from its steps: one RUNNABLE step, nothing waiting on a person.
    assert body["status"] == "RUNNING"
    assert body["is_terminal"] is False
    assert body["created"] is True
    assert body["project_revision"] == 1
    assert [s["kind"] for s in body["steps"]] == ["develop_snapshot"]
    assert body["steps"][0]["status"] == "RUNNABLE"
    assert created.headers["Location"].endswith(f"/runs/{body['run_id']}")

    again = researcher.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"})
    assert again.status_code == 200
    assert again.json()["run_id"] == body["run_id"]
    assert again.json()["created"] is False

    listed = researcher.get(f"{base}/runs").json()["items"]
    assert [r["run_id"] for r in listed] == [body["run_id"]]
    assert listed[0]["is_terminal"] is False and listed[0]["needs_attention"] is False

    events = researcher.get(f"{base}/runs/{body['run_id']}/events").json()
    assert events[0]["event_type"] == "RUN_CREATED"


def test_unknown_workflow_type_is_a_validation_error(researcher: TestClient, world: Any) -> None:
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    response = researcher.post(
        f"{API}/studies/{study_id}/projects/{project_id}/runs",
        json={"workflow_type": "research_pipeline"},
    )
    assert response.status_code == 422


def test_a_viewer_labelled_member_and_one_with_no_grant_may_read_and_start_runs(
    researcher: TestClient, viewer: TestClient, outsider: TestClient, world: Any
) -> None:
    """ADR 0019: the "viewer" label holds the Researcher role, so it may start a run.

    A member who was never granted the study is a member: they read and start runs too.
    """
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    base = f"{API}/studies/{study_id}/projects/{project_id}"
    first = viewer.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"})
    assert first.status_code == 201, first.text
    # A run is idempotent per revision, so the second member is handed the same run: 200, not 201.
    again = outsider.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"})
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == first.json()["run_id"]
    for member in (viewer, outsider):
        assert member.get(f"{base}/runs").status_code == 200


def test_a_run_is_found_only_through_its_own_study(
    researcher: TestClient, as_user: Any, world: Any
) -> None:
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    run_id = researcher.post(
        f"{API}/studies/{study_id}/projects/{project_id}/runs",
        json={"workflow_type": "develop_snapshot"},
    ).json()["run_id"]

    other = as_user("other_lead")
    other_study = world.study_id("other_client")
    # Another client's lead may open this study (ADR 0019), and reads its run there.
    assert (
        other.get(f"{API}/studies/{study_id}/projects/{project_id}/runs/{run_id}").status_code
        == 200
    )
    # A real run addressed under the wrong study is not found, whoever asks.
    assert (
        other.get(f"{API}/studies/{other_study}/projects/{project_id}/runs/{run_id}").status_code
        == 404
    )


def test_missing_run_and_artifact_are_404(researcher: TestClient, world: Any) -> None:
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    base = f"{API}/studies/{study_id}/projects/{project_id}"
    assert researcher.get(f"{base}/runs/RUN-0000000000abcd").status_code == 404
    assert researcher.get(f"{base}/artifacts/ART-0000000000abcd").status_code == 404
    assert researcher.get(f"{base}/runs/not-a-run-id").status_code == 422


def test_the_full_slice_over_http(app: FastAPI, researcher: TestClient, world: Any) -> None:
    """Browser -> API -> PostgreSQL -> worker -> ArtifactStore -> API -> browser.

    The worker is driven in-process here; in develop it is the worker container,
    and `aia_executors.smoke` proves the same sequence against the deployment.
    """
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    base = f"{API}/studies/{study_id}/projects/{project_id}"
    run_id = researcher.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"}).json()[
        "run_id"
    ]

    result = _worker(app).run_once()
    assert result is not None and result.ending == "completed"

    run = researcher.get(f"{base}/runs/{run_id}").json()
    assert run["status"] == "COMPLETED"
    assert run["is_terminal"] is True
    step = run["steps"][0]
    assert step["status"] == "SUCCEEDED"
    assert step["attempts"][0]["status"] == "SUCCEEDED"
    assert step["attempts"][0]["worker_id"] == "api-test-worker"
    artifact_id = step["output"]["artifact_id"]

    artifact = researcher.get(f"{base}/artifacts/{artifact_id}")
    assert artifact.status_code == 200, artifact.text
    body = artifact.json()
    assert body["artifact_type"] == "develop_snapshot"
    assert body["runtime_version"] == BUILD.sha
    assert body["status"] == "VALID"
    assert "storage_key" not in body
    assert body["payload"]["project_id"] == project_id
    assert body["payload"]["produced_by"]["run_id"] == run_id

    events = researcher.get(f"{base}/runs/{run_id}/events").json()
    kinds = [e["event_type"] for e in events]
    assert kinds[0] == "RUN_CREATED"
    assert "STEP_SUCCEEDED" in kinds
    assert kinds[-1] == "RUN_STATUS"  # the run's terminal transition is the last word

    # Another client's lead cannot read the artifact, and is not told it exists.
    other_base = f"{API}/studies/{world.study_id('other_client')}/projects/{project_id}"
    assert researcher.get(f"{other_base}/artifacts/{artifact_id}").status_code == 404


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_a_corrupt_artifact_stays_marked_corrupt_after_the_409(
    app: FastAPI,
    researcher: TestClient,
    world: Any,
    damage_artifact: Any,
    artifact_status: Any,
    damage: str,
) -> None:
    """Regression: the CORRUPT mark was rolled back with the 409 that reported it.

    ``ArtifactRepository.read`` flushes the mark into the request's session and
    raises; the route answered 409, and ``get_session`` rolled the mark back with
    it, so the artifact read VALID in every listing afterwards.
    """
    study_id = world.study_id()
    project_id = _project(researcher, study_id)
    base = f"{API}/studies/{study_id}/projects/{project_id}"
    run_id = researcher.post(f"{base}/runs", json={"workflow_type": "develop_snapshot"}).json()[
        "run_id"
    ]
    result = _worker(app).run_once()
    assert result is not None and result.ending == "completed"
    artifact_id = researcher.get(f"{base}/runs/{run_id}").json()["steps"][0]["output"][
        "artifact_id"
    ]
    damage_artifact(artifact_id, damage)

    refused = researcher.get(f"{base}/artifacts/{artifact_id}")
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "artifact_corrupt"
    assert artifact_status(artifact_id) == "CORRUPT"

    # The next read refuses again, and the study's listing now says what happened.
    assert researcher.get(f"{base}/artifacts/{artifact_id}").status_code == 409
    outputs = researcher.get(f"{API}/clients/{world.client_id()}/overview").json()
    listed = {o["artifact_id"]: o["status"] for o in outputs["recent_outputs"]}
    assert listed[artifact_id] == "CORRUPT"
