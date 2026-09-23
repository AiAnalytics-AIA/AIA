"""End-to-end tests for the projects API.

These exercise the real HTTP surface against a real database. They cover the
contract a client depends on, the client/study isolation boundary, and the
error shape.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from aia_api.config import Settings
from aia_api.main import create_app

API = "/api/v1"


def base(world: Any, study: str = "primary") -> str:
    """Projects live under a study: the study is the access boundary."""
    return f"{API}/studies/{world.study_id(study)}/projects"


def _create(client: TestClient, world: Any, **body: object) -> dict:
    """Create a project in the primary study and return the response body."""
    payload = {"title": "Test výzkum", "content": {"goal": "g"}, **body}
    response = client.post(base(world), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #


def test_health_does_not_require_auth(client: TestClient) -> None:
    """Liveness must answer without credentials or the orchestrator cannot probe it."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_the_build_it_was_told_and_null_otherwise(
    settings: Settings, client: TestClient
) -> None:
    """The deployed revision must be visible from the URL; an untold process says None."""
    assert client.get("/api/v1/health").json()["build"] == {"sha": None, "built_at": None}

    told = create_app(
        settings.model_copy(
            update={"build_sha": "a15be650937aacaa", "build_time": "2026-09-23T01:00:00Z"}
        )
    )
    with TestClient(told) as c:
        body = c.get("/api/v1/health").json()
    assert body["build"] == {"sha": "a15be650937aacaa", "built_at": "2026-09-23T01:00:00Z"}
    assert body["env"] == "test"


def test_readiness_reports_database(client: TestClient) -> None:
    """Readiness reflects dependency state, unlike liveness."""
    body = client.get("/api/v1/ready").json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    """Support needs a correlation id on every response, including errors."""
    ok = client.get("/api/v1/health")
    assert ok.headers["X-Request-ID"]

    err = client.get(f"{API}/studies/STU-0000000000abcd/projects")
    assert err.headers["X-Request-ID"]


def test_client_supplied_request_id_is_sanitised(client: TestClient) -> None:
    """An inbound id is honoured but stripped, so it cannot inject into logs."""
    response = client.get(
        "/api/v1/health", headers={"X-Request-ID": "abc\n INJECTED line=1 " + "x" * 200}
    )
    rid = response.headers["X-Request-ID"]
    assert "\n" not in rid and " " not in rid
    assert len(rid) <= 64


# --------------------------------------------------------------------------- #
# Authentication and client isolation
# --------------------------------------------------------------------------- #


def test_project_endpoints_require_authentication(client: TestClient, world: Any) -> None:
    """Every project route is behind auth, and the challenge names bearer."""
    response = client.get(base(world))
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"

    assert client.post(base(world), json={"title": "x"}).status_code == 401
    assert client.get(f"{base(world)}/PRJ-abc").status_code == 401


def test_cross_client_read_is_not_found(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Another client's project is indistinguishable from a missing one.

    A 403 would confirm the project exists, which would disclose another client's
    engagement. Note the code is ``not_found`` rather than ``project_not_found``:
    the request is refused at scope resolution, before the project repository is
    reached at all, so the caller learns nothing about the study either.
    """
    project = _create(researcher, world)
    pid = project["project_id"]

    for response in (
        other_client_lead.get(f"{base(world)}/{pid}"),
        other_client_lead.get(f"{base(world)}/{pid}/revisions"),
        other_client_lead.get(f"{base(world)}/{pid}/events"),
        other_client_lead.get(f"{base(world)}/{pid}/impact"),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


def test_cross_client_write_is_not_found(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """Mutating routes are scope-checked too, not just the reads."""
    pid = _create(researcher, world)["project_id"]

    assert (
        other_client_lead.put(f"{base(world)}/{pid}/content", json={"content": {}}).status_code
        == 404
    )
    assert (
        other_client_lead.patch(f"{base(world)}/{pid}", json={"title": "hijacked"}).status_code
        == 404
    )
    assert other_client_lead.post(f"{base(world)}/{pid}/trash").status_code == 404

    assert researcher.get(f"{base(world)}/{pid}").json()["title"] == "Test výzkum"


def test_listing_never_crosses_clients(
    researcher: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    """A project listing shows only the projects of the study in scope."""
    mine = base(world, "primary")
    theirs = base(world, "other_client")

    researcher.post(mine, json={"title": "Mine", "content": {}})
    other_client_lead.post(theirs, json={"title": "Theirs", "content": {}})

    assert [p["title"] for p in researcher.get(mine).json()["items"]] == ["Mine"]
    assert [p["title"] for p in other_client_lead.get(theirs).json()["items"]] == ["Theirs"]

    # And neither can see into the other's study at all.
    assert researcher.get(theirs).status_code == 404
    assert other_client_lead.get(mine).status_code == 404


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #


def test_create_returns_full_pipeline_and_location(researcher: TestClient, world: Any) -> None:
    """A new project comes back with revision 1 and all 13 stages."""
    response = researcher.post(base(world), json={"title": "Nový", "content": {"goal": "g"}})
    body = response.json()

    assert response.status_code == 201
    assert response.headers["Location"].endswith(body["project_id"])
    assert body["current_revision"] == 1
    assert body["current_stage"] == "BRIEF"
    assert body["status"] == "DRAFT"
    assert len(body["stages"]) == 13
    assert body["stages"][0]["label"] == "Zadání"
    assert all(s["status"] == "NOT_STARTED" for s in body["stages"])


def test_create_simulation_returns_simulation_stages(researcher: TestClient, world: Any) -> None:
    """Project type selects the pipeline."""
    body = _create(researcher, world, project_type="simulation", title="Sim")
    stage_types = [s["stage_type"] for s in body["stages"]]

    assert body["project_type"] == "simulation"
    assert "SCENARIO_CONTRACT" in stage_types
    assert "QUESTIONNAIRE" not in stage_types


def test_create_exposes_provider_label_not_just_id(researcher: TestClient, world: Any) -> None:
    """The UI shows 'Claude API', never the internal id 'anthropic'."""
    body = _create(researcher, world, preferred_provider="anthropic")
    assert body["preferred_provider"] == "anthropic"
    assert body["provider_label"] == "Claude API"
    assert body["provider_policy"] == "CLAUDE_API_ONLY"


def test_create_rejects_unknown_fields(researcher: TestClient, world: Any) -> None:
    """Strict schemas stop a typo from being silently ignored."""
    response = researcher.post(base(world), json={"title": "x", "projectType": "simulation"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_create_rejects_invalid_provider(researcher: TestClient, world: Any) -> None:
    """Only the three supported runtimes are accepted."""
    response = researcher.post(base(world), json={"title": "x", "preferred_provider": "llama"})
    assert response.status_code == 422


def test_create_rejects_negative_budget(researcher: TestClient, world: Any) -> None:
    """A negative ceiling would disable budget enforcement."""
    assert (
        researcher.post(base(world), json={"title": "x", "max_api_cost_usd": -1}).status_code == 422
    )


def test_create_normalises_title_into_content(researcher: TestClient, world: Any) -> None:
    """The stored content is self-describing, matching the legacy contract.

    A client that round-trips the returned content therefore deduplicates cleanly;
    this test pins the behaviour so it is not a surprise.
    """
    body = _create(researcher, world, title="Titulek", content={"goal": "g"})
    assert body["content"]["title"] == "Titulek"

    echo = researcher.put(
        f"{base(world)}/{body['project_id']}/content", json={"content": body["content"]}
    ).json()
    assert echo["deduplicated"] is True
    assert echo["revision"] == 1


# --------------------------------------------------------------------------- #
# Save, revisions and the reuse rule
# --------------------------------------------------------------------------- #


def test_unchanged_save_deduplicates(researcher: TestClient, world: Any) -> None:
    """An idle autosave must not create a revision."""
    body = _create(researcher, world)
    pid, content = body["project_id"], body["content"]

    for _ in range(3):
        response = researcher.put(f"{base(world)}/{pid}/content", json={"content": content})
        assert response.status_code == 200
        assert response.json()["deduplicated"] is True
        assert response.json()["revision"] == 1

    assert len(researcher.get(f"{base(world)}/{pid}/revisions").json()) == 1


def test_material_edit_creates_revision_and_reports_impact(
    researcher: TestClient, world: Any
) -> None:
    """A real edit creates a revision and tells the client what it invalidated."""
    body = _create(researcher, world)
    pid = body["project_id"]
    content = {**body["content"], "audience": {"mode": "population"}}
    researcher.put(f"{base(world)}/{pid}/content", json={"content": content})

    changed = {**content, "audience": {"mode": "customer"}}
    result = researcher.put(f"{base(world)}/{pid}/content", json={"content": changed}).json()

    assert result["deduplicated"] is False
    assert result["revision"] == 3
    assert result["changed_fields"] == ["audience"]
    assert result["impact"]["root_stage"] == "AUDIENCE"
    assert result["current_stage"] == "AUDIENCE"
    assert result["status"] == "READY_TO_CONTINUE"
    assert "BRIEF" in result["impact"]["preserve"]
    assert "FIELDWORK" in result["impact"]["invalidate"]


def test_provider_change_invalidates_nothing(researcher: TestClient, world: Any) -> None:
    """Switching provider must never discard completed work."""
    body = _create(researcher, world)
    pid = body["project_id"]

    changed = {**body["content"], "provider": "anthropic"}
    result = researcher.put(f"{base(world)}/{pid}/content", json={"content": changed}).json()

    assert result["changed_fields"] == ["provider"]
    assert result["impact"]["root_stage"] is None
    assert result["impact"]["invalidate"] == []
    assert len(result["impact"]["preserve"]) == 13


def test_earlier_revisions_remain_readable(researcher: TestClient, world: Any) -> None:
    """History is immutable and inspectable per revision."""
    body = _create(researcher, world)
    pid = body["project_id"]

    researcher.put(f"{base(world)}/{pid}/content", json={"content": {**body["content"], "n": 300}})
    researcher.put(f"{base(world)}/{pid}/content", json={"content": {**body["content"], "n": 900}})

    assert (
        researcher.get(f"{base(world)}/{pid}", params={"revision": 2}).json()["content"]["n"] == 300
    )
    assert (
        researcher.get(f"{base(world)}/{pid}", params={"revision": 3}).json()["content"]["n"] == 900
    )
    assert researcher.get(f"{base(world)}/{pid}").json()["content"]["n"] == 900


def test_revision_history_is_newest_first_with_provenance(
    researcher: TestClient, world: Any
) -> None:
    """Revision history carries the hash, reason and impact for each entry."""
    body = _create(researcher, world)
    pid = body["project_id"]
    researcher.put(f"{base(world)}/{pid}/content", json={"content": {**body["content"], "n": 1}})

    history = researcher.get(f"{base(world)}/{pid}/revisions").json()
    assert [r["revision"] for r in history] == [2, 1]
    assert len(history[0]["content_sha256"]) == 64
    assert history[0]["parent_revision"] == 1
    assert history[-1]["reason"] == "project_created"


def test_forced_revision_is_created_without_content_change(
    researcher: TestClient, world: Any
) -> None:
    """Branch and restore need a revision even when content is identical."""
    body = _create(researcher, world)
    pid = body["project_id"]

    result = researcher.put(
        f"{base(world)}/{pid}/content",
        json={"content": body["content"], "reason": "branch", "force_new_revision": True},
    ).json()

    assert result["deduplicated"] is False
    assert result["revision"] == 2


def test_explicit_stage_forces_rerun(researcher: TestClient, world: Any) -> None:
    """A user can rerun from a chosen stage without editing anything."""
    body = _create(researcher, world)
    pid = body["project_id"]

    result = researcher.put(
        f"{base(world)}/{pid}/content",
        json={"content": body["content"], "explicit_stage": "FIELDWORK"},
    ).json()

    assert result["impact"]["root_stage"] == "FIELDWORK"
    assert "ANALYSIS" in result["impact"]["invalidate"]


def test_save_on_missing_project_is_404(researcher: TestClient, world: Any) -> None:
    """A save against a nonexistent project must not create one."""
    response = researcher.put(f"{base(world)}/PRJ-0000000000abcd/content", json={"content": {}})
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Impact preview
# --------------------------------------------------------------------------- #


def test_impact_preview_warns_before_an_expensive_edit(researcher: TestClient, world: Any) -> None:
    """The client can ask what an edit would cost before committing to it."""
    pid = _create(researcher, world)["project_id"]

    result = researcher.get(f"{base(world)}/{pid}/impact", params={"field": ["audience"]}).json()
    assert result["root_stage"] == "AUDIENCE"
    assert "FIELDWORK" in result["invalidate"]

    safe = researcher.get(
        f"{base(world)}/{pid}/impact", params={"field": ["provider", "model"]}
    ).json()
    assert safe["root_stage"] is None
    assert safe["invalidate"] == []


def test_impact_preview_flags_presentation_only_change(researcher: TestClient, world: Any) -> None:
    """A styling change is reported as presentation-only so no scary warning shows."""
    pid = _create(researcher, world)["project_id"]
    result = researcher.get(
        f"{base(world)}/{pid}/impact", params={"field": ["report_style"]}
    ).json()

    assert result["root_stage"] == "REPORT"
    assert result["presentation_only"] is True
    assert "FIELDWORK" in result["preserve"]


def test_impact_preview_rejects_stage_from_other_pipeline(
    researcher: TestClient, world: Any
) -> None:
    """Asking a research project to rerun from WORLDS is a client error."""
    pid = _create(researcher, world)["project_id"]
    response = researcher.get(f"{base(world)}/{pid}/impact", params={"explicit_stage": "WORLDS"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_stage"
    assert "BRIEF" in response.json()["details"]["allowed"]


# --------------------------------------------------------------------------- #
# Settings, audit, trash
# --------------------------------------------------------------------------- #


def test_settings_update_and_audit(researcher: TestClient, world: Any) -> None:
    """Provider and budget changes are recorded in project history."""
    pid = _create(researcher, world)["project_id"]

    updated = researcher.patch(
        f"{base(world)}/{pid}",
        json={"preferred_provider": "openai", "max_api_cost_usd": 25, "pinned": True},
    ).json()

    assert updated["preferred_provider"] == "openai"
    assert updated["provider_label"] == "OpenAI API"
    assert updated["provider_policy"] == "OPENAI_ONLY"
    assert updated["max_api_cost_usd"] == 25
    assert updated["pinned"] is True

    events = researcher.get(f"{base(world)}/{pid}/events").json()
    settings_event = next(e for e in events if e["event_type"] == "SETTINGS_UPDATED")
    assert settings_event["payload"]["provider"]["to"] == "openai"


def test_project_history_records_creation_and_revisions(researcher: TestClient, world: Any) -> None:
    """History answers 'what happened to this project' without reading files."""
    body = _create(researcher, world)
    pid = body["project_id"]
    researcher.put(f"{base(world)}/{pid}/content", json={"content": {**body["content"], "n": 5}})

    types = [e["event_type"] for e in researcher.get(f"{base(world)}/{pid}/events").json()]
    assert "PROJECT_CREATED" in types
    assert types.count("REVISION_SAVED") == 2


def test_trash_and_restore_round_trip(researcher: TestClient, world: Any) -> None:
    """Trashing hides a project from the portfolio but loses nothing."""
    body = _create(researcher, world)
    pid = body["project_id"]

    assert researcher.post(f"{base(world)}/{pid}/trash").json()["status"] == "TRASHED"
    assert researcher.get(base(world)).json()["page"]["total"] == 0
    assert (
        researcher.get(base(world), params={"include_trashed": True}).json()["page"]["total"] == 1
    )
    assert researcher.get(f"{base(world)}/{pid}").json()["content"] == body["content"]

    assert researcher.post(f"{base(world)}/{pid}/restore").json()["status"] == "READY_TO_CONTINUE"
    assert researcher.get(base(world)).json()["page"]["total"] == 1


# --------------------------------------------------------------------------- #
# Listing contract
# --------------------------------------------------------------------------- #


def test_listing_paginates_with_stable_metadata(researcher: TestClient, world: Any) -> None:
    """Pagination metadata is identical in shape on every list endpoint."""
    for i in range(5):
        _create(researcher, world, title=f"P{i}")

    page = researcher.get(base(world), params={"limit": 2}).json()
    assert page["page"] == {"total": 5, "limit": 2, "offset": 0, "has_more": True}
    assert len(page["items"]) == 2

    last = researcher.get(base(world), params={"limit": 2, "offset": 4}).json()
    assert last["page"]["has_more"] is False


def test_listing_rejects_out_of_range_limit(researcher: TestClient, world: Any) -> None:
    """The API rejects an absurd page size rather than silently clamping it."""
    assert researcher.get(base(world), params={"limit": 10_000}).status_code == 422
    assert researcher.get(base(world), params={"limit": 0}).status_code == 422
    assert researcher.get(base(world), params={"offset": -1}).status_code == 422


def test_listing_filters(researcher: TestClient, world: Any) -> None:
    """Type and search filters narrow the portfolio."""
    _create(researcher, world, title="Brand study")
    _create(researcher, world, title="Price simulation", project_type="simulation")

    assert (
        researcher.get(base(world), params={"project_type": "simulation"}).json()["page"]["total"]
        == 1
    )
    assert researcher.get(base(world), params={"search": "brand"}).json()["page"]["total"] == 1
    assert researcher.get(base(world), params={"status": "DRAFT"}).json()["page"]["total"] == 2


def test_listing_rejects_unknown_status(researcher: TestClient, world: Any) -> None:
    """An unknown status is a client error with the allowed values attached."""
    response = researcher.get(base(world), params={"status": "BANANA"})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_status"
    assert "DRAFT" in response.json()["details"]["allowed"]


# --------------------------------------------------------------------------- #
# Error contract and information disclosure
# --------------------------------------------------------------------------- #


def test_malformed_project_id_is_rejected_by_the_route(researcher: TestClient, world: Any) -> None:
    """Path validation blocks traversal and injection attempts at the edge."""
    for bad in ("../../etc/passwd", "PRJ-'; DROP TABLE projects; --", "not-a-project"):
        assert researcher.get(f"{base(world)}/{bad}").status_code in (404, 422)


def test_errors_share_one_shape(researcher: TestClient, world: Any) -> None:
    """Every error carries code, message, details and request_id."""
    response = researcher.get(f"{base(world)}/PRJ-0000000000abcd")
    body = response.json()

    assert response.status_code == 404
    assert set(body) == {"code", "message", "details", "request_id"}
    assert body["code"] == "project_not_found"


def test_stage_fingerprint_is_not_fully_exposed(researcher: TestClient, world: Any) -> None:
    """Only a short fingerprint prefix reaches the client.

    The full value is an internal artifact-reuse key; publishing it invites
    clients to depend on cache behaviour we may change.
    """
    body = _create(researcher, world)
    for stage in body["stages"]:
        assert len(stage["fingerprint_prefix"]) <= 12


def test_responses_never_expose_internal_fields(researcher: TestClient, world: Any) -> None:
    """Organization, client and storage internals must not leak into a response."""
    body = _create(researcher, world)
    serialised = str(body)

    assert "organization_id" not in serialised
    assert "ORG-primary" not in serialised
    assert "storage_key" not in serialised
