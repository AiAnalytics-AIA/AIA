"""The native Deep Research route uses the Study's scope and a durable six-step run."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"
DESIGN = {
    "title": "Fiktivní káva",
    "goal": "Zjistit veřejný kontext přípravy kávy.",
    "research_plan": {"research_questions": ["Jak lidé připravují kávu?"]},
    "sections": [],
}


def _url(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}/deep-research/runs"


def _revision(client: TestClient, world: Any) -> str:
    response = client.post(
        f"{API}/studies/{world.study_id()}/design/revisions",
        json={"content": DESIGN, "source_stage": "brief"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["revision_id"])


def test_start_is_scoped_idempotent_and_does_not_publish_before_worker(
    researcher: TestClient, viewer: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    payload = {"design_revision_id": revision, "preset_name": "QUICK", "channels": ["WEB"]}
    started = researcher.post(_url(world), json=payload)
    assert started.status_code == 201, started.text
    job = started.json()
    assert [step["node_key"] for step in job["steps"]] == [
        "plan",
        "investigate",
        "merge",
        "verify",
        "synthesize",
        "publish",
    ]
    assert job["channels"] == ["WEB"] and job["preset"] == "QUICK"
    assert researcher.post(_url(world), json=payload).status_code == 200
    assert len(researcher.get(_url(world)).json()) == 1
    run_url = f"{_url(world)}/{job['run_id']}"
    assert viewer.get(run_url).status_code == 200
    assert researcher.get(f"{run_url}/bundle").status_code == 409
    assert viewer.get(f"{run_url}/bundle").status_code == 403
    assert viewer.get(f"{run_url}/events").status_code == 403
    events = researcher.get(f"{run_url}/events")
    assert events.status_code == 200, events.text
    assert other_client_lead.get(run_url).status_code == 404


def test_invalid_or_unauthorised_job_is_refused_before_enqueue(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    revision = _revision(researcher, world)
    base = {"design_revision_id": revision, "preset_name": "QUICK"}
    assert viewer.post(_url(world), json=base).status_code == 403
    for channels in ([], ["WEB", "WEB"], ["OTHER"]):
        assert researcher.post(_url(world), json={**base, "channels": channels}).status_code == 422
    assert researcher.post(_url(world), json={**base, "preset_name": "UNKNOWN"}).status_code == 422
    assert (
        researcher.post(_url(world), json={**base, "design_revision_id": "REV-0"}).status_code
        == 404
    )
    assert researcher.get(f"{_url(world)}/RUN-0").status_code == 404
