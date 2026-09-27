"""The native agent boundary enqueues only: no model work in HTTP."""

from typing import Any

from fastapi.testclient import TestClient


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
