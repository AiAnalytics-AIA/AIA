"""End-to-end tests for the projects API.

These exercise the real HTTP surface against a real database. They cover the
contract a client depends on, the tenant boundary, and the error shape.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

BASE = "/api/v1/projects"


def _create(client: TestClient, **body: object) -> dict:
    """Create a project and return the response body."""
    payload = {"title": "Test výzkum", "content": {"goal": "g"}, **body}
    response = client.post(BASE, json=payload)
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


def test_readiness_reports_database(client: TestClient) -> None:
    """Readiness reflects dependency state, unlike liveness."""
    body = client.get("/api/v1/ready").json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    """Support needs a correlation id on every response, including errors."""
    ok = client.get("/api/v1/health")
    assert ok.headers["X-Request-ID"]

    err = client.get(f"{BASE}/PRJ-doesnotexist")
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
# Authentication and tenant isolation
# --------------------------------------------------------------------------- #


def test_project_endpoints_require_authentication(client: TestClient) -> None:
    """Every project route is behind auth."""
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json={"title": "x"}).status_code == 401
    assert client.get(f"{BASE}/PRJ-abc").status_code == 401


def test_cross_tenant_read_is_not_found(auth: TestClient, other_auth: TestClient) -> None:
    """Another tenant's project is indistinguishable from a missing one.

    A 403 would confirm the project exists, which leaks the existence of other
    tenants' data.
    """
    project = _create(auth)
    pid = project["project_id"]

    for response in (
        other_auth.get(f"{BASE}/{pid}"),
        other_auth.get(f"{BASE}/{pid}/revisions"),
        other_auth.get(f"{BASE}/{pid}/events"),
        other_auth.get(f"{BASE}/{pid}/impact"),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "project_not_found"


def test_cross_tenant_write_is_not_found(auth: TestClient, other_auth: TestClient) -> None:
    """Mutating routes are tenant-scoped too."""
    pid = _create(auth)["project_id"]

    assert other_auth.put(f"{BASE}/{pid}/content", json={"content": {}}).status_code == 404
    assert other_auth.patch(f"{BASE}/{pid}", json={"title": "hijacked"}).status_code == 404
    assert other_auth.post(f"{BASE}/{pid}/trash").status_code == 404

    assert auth.get(f"{BASE}/{pid}").json()["title"] == "Test výzkum"


def test_listing_never_crosses_tenants(auth: TestClient, other_auth: TestClient) -> None:
    """A portfolio listing shows only the caller's projects."""
    _create(auth, title="Mine")
    _create(other_auth, title="Theirs")

    assert [p["title"] for p in auth.get(BASE).json()["items"]] == ["Mine"]
    assert [p["title"] for p in other_auth.get(BASE).json()["items"]] == ["Theirs"]


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #


def test_create_returns_full_pipeline_and_location(auth: TestClient) -> None:
    """A new project comes back with revision 1 and all 13 stages."""
    response = auth.post(BASE, json={"title": "Nový", "content": {"goal": "g"}})
    body = response.json()

    assert response.status_code == 201
    assert response.headers["Location"].endswith(body["project_id"])
    assert body["current_revision"] == 1
    assert body["current_stage"] == "BRIEF"
    assert body["status"] == "DRAFT"
    assert len(body["stages"]) == 13
    assert body["stages"][0]["label"] == "Zadání"
    assert all(s["status"] == "NOT_STARTED" for s in body["stages"])


def test_create_simulation_returns_simulation_stages(auth: TestClient) -> None:
    """Project type selects the pipeline."""
    body = _create(auth, project_type="simulation", title="Sim")
    stage_types = [s["stage_type"] for s in body["stages"]]

    assert body["project_type"] == "simulation"
    assert "SCENARIO_CONTRACT" in stage_types
    assert "QUESTIONNAIRE" not in stage_types


def test_create_exposes_provider_label_not_just_id(auth: TestClient) -> None:
    """The UI shows 'Claude API', never the internal id 'anthropic'."""
    body = _create(auth, preferred_provider="anthropic")
    assert body["preferred_provider"] == "anthropic"
    assert body["provider_label"] == "Claude API"
    assert body["provider_policy"] == "CLAUDE_API_ONLY"


def test_create_rejects_unknown_fields(auth: TestClient) -> None:
    """Strict schemas stop a typo from being silently ignored."""
    response = auth.post(BASE, json={"title": "x", "projectType": "simulation"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_create_rejects_invalid_provider(auth: TestClient) -> None:
    """Only the three supported runtimes are accepted."""
    response = auth.post(BASE, json={"title": "x", "preferred_provider": "llama"})
    assert response.status_code == 422


def test_create_rejects_negative_budget(auth: TestClient) -> None:
    """A negative ceiling would disable budget enforcement."""
    assert auth.post(BASE, json={"title": "x", "max_api_cost_usd": -1}).status_code == 422


def test_create_normalises_title_into_content(auth: TestClient) -> None:
    """The stored content is self-describing, matching the legacy contract.

    A client that round-trips the returned content therefore deduplicates cleanly;
    this test pins the behaviour so it is not a surprise.
    """
    body = _create(auth, title="Titulek", content={"goal": "g"})
    assert body["content"]["title"] == "Titulek"

    echo = auth.put(
        f"{BASE}/{body['project_id']}/content", json={"content": body["content"]}
    ).json()
    assert echo["deduplicated"] is True
    assert echo["revision"] == 1


# --------------------------------------------------------------------------- #
# Save, revisions and the reuse rule
# --------------------------------------------------------------------------- #


def test_unchanged_save_deduplicates(auth: TestClient) -> None:
    """An idle autosave must not create a revision."""
    body = _create(auth)
    pid, content = body["project_id"], body["content"]

    for _ in range(3):
        response = auth.put(f"{BASE}/{pid}/content", json={"content": content})
        assert response.status_code == 200
        assert response.json()["deduplicated"] is True
        assert response.json()["revision"] == 1

    assert len(auth.get(f"{BASE}/{pid}/revisions").json()) == 1


def test_material_edit_creates_revision_and_reports_impact(auth: TestClient) -> None:
    """A real edit creates a revision and tells the client what it invalidated."""
    body = _create(auth)
    pid = body["project_id"]
    content = {**body["content"], "audience": {"mode": "population"}}
    auth.put(f"{BASE}/{pid}/content", json={"content": content})

    changed = {**content, "audience": {"mode": "customer"}}
    result = auth.put(f"{BASE}/{pid}/content", json={"content": changed}).json()

    assert result["deduplicated"] is False
    assert result["revision"] == 3
    assert result["changed_fields"] == ["audience"]
    assert result["impact"]["root_stage"] == "AUDIENCE"
    assert result["current_stage"] == "AUDIENCE"
    assert result["status"] == "READY_TO_CONTINUE"
    assert "BRIEF" in result["impact"]["preserve"]
    assert "FIELDWORK" in result["impact"]["invalidate"]


def test_provider_change_invalidates_nothing(auth: TestClient) -> None:
    """Switching provider must never discard completed work."""
    body = _create(auth)
    pid = body["project_id"]

    changed = {**body["content"], "provider": "anthropic"}
    result = auth.put(f"{BASE}/{pid}/content", json={"content": changed}).json()

    assert result["changed_fields"] == ["provider"]
    assert result["impact"]["root_stage"] is None
    assert result["impact"]["invalidate"] == []
    assert len(result["impact"]["preserve"]) == 13


def test_earlier_revisions_remain_readable(auth: TestClient) -> None:
    """History is immutable and inspectable per revision."""
    body = _create(auth)
    pid = body["project_id"]

    auth.put(f"{BASE}/{pid}/content", json={"content": {**body["content"], "n": 300}})
    auth.put(f"{BASE}/{pid}/content", json={"content": {**body["content"], "n": 900}})

    assert auth.get(f"{BASE}/{pid}", params={"revision": 2}).json()["content"]["n"] == 300
    assert auth.get(f"{BASE}/{pid}", params={"revision": 3}).json()["content"]["n"] == 900
    assert auth.get(f"{BASE}/{pid}").json()["content"]["n"] == 900


def test_revision_history_is_newest_first_with_provenance(auth: TestClient) -> None:
    """Revision history carries the hash, reason and impact for each entry."""
    body = _create(auth)
    pid = body["project_id"]
    auth.put(f"{BASE}/{pid}/content", json={"content": {**body["content"], "n": 1}})

    history = auth.get(f"{BASE}/{pid}/revisions").json()
    assert [r["revision"] for r in history] == [2, 1]
    assert len(history[0]["content_sha256"]) == 64
    assert history[0]["parent_revision"] == 1
    assert history[-1]["reason"] == "project_created"


def test_forced_revision_is_created_without_content_change(auth: TestClient) -> None:
    """Branch and restore need a revision even when content is identical."""
    body = _create(auth)
    pid = body["project_id"]

    result = auth.put(
        f"{BASE}/{pid}/content",
        json={"content": body["content"], "reason": "branch", "force_new_revision": True},
    ).json()

    assert result["deduplicated"] is False
    assert result["revision"] == 2


def test_explicit_stage_forces_rerun(auth: TestClient) -> None:
    """A user can rerun from a chosen stage without editing anything."""
    body = _create(auth)
    pid = body["project_id"]

    result = auth.put(
        f"{BASE}/{pid}/content",
        json={"content": body["content"], "explicit_stage": "FIELDWORK"},
    ).json()

    assert result["impact"]["root_stage"] == "FIELDWORK"
    assert "ANALYSIS" in result["impact"]["invalidate"]


def test_save_on_missing_project_is_404(auth: TestClient) -> None:
    """A save against a nonexistent project must not create one."""
    response = auth.put(f"{BASE}/PRJ-0000000000abcd/content", json={"content": {}})
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Impact preview
# --------------------------------------------------------------------------- #


def test_impact_preview_warns_before_an_expensive_edit(auth: TestClient) -> None:
    """The client can ask what an edit would cost before committing to it."""
    pid = _create(auth)["project_id"]

    result = auth.get(f"{BASE}/{pid}/impact", params={"field": ["audience"]}).json()
    assert result["root_stage"] == "AUDIENCE"
    assert "FIELDWORK" in result["invalidate"]

    safe = auth.get(f"{BASE}/{pid}/impact", params={"field": ["provider", "model"]}).json()
    assert safe["root_stage"] is None
    assert safe["invalidate"] == []


def test_impact_preview_flags_presentation_only_change(auth: TestClient) -> None:
    """A styling change is reported as presentation-only so no scary warning shows."""
    pid = _create(auth)["project_id"]
    result = auth.get(f"{BASE}/{pid}/impact", params={"field": ["report_style"]}).json()

    assert result["root_stage"] == "REPORT"
    assert result["presentation_only"] is True
    assert "FIELDWORK" in result["preserve"]


def test_impact_preview_rejects_stage_from_other_pipeline(auth: TestClient) -> None:
    """Asking a research project to rerun from WORLDS is a client error."""
    pid = _create(auth)["project_id"]
    response = auth.get(f"{BASE}/{pid}/impact", params={"explicit_stage": "WORLDS"})

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_stage"
    assert "BRIEF" in response.json()["details"]["allowed"]


# --------------------------------------------------------------------------- #
# Settings, audit, trash
# --------------------------------------------------------------------------- #


def test_settings_update_and_audit(auth: TestClient) -> None:
    """Provider and budget changes are recorded in project history."""
    pid = _create(auth)["project_id"]

    updated = auth.patch(
        f"{BASE}/{pid}",
        json={"preferred_provider": "openai", "max_api_cost_usd": 25, "pinned": True},
    ).json()

    assert updated["preferred_provider"] == "openai"
    assert updated["provider_label"] == "OpenAI API"
    assert updated["provider_policy"] == "OPENAI_ONLY"
    assert updated["max_api_cost_usd"] == 25
    assert updated["pinned"] is True

    events = auth.get(f"{BASE}/{pid}/events").json()
    settings_event = next(e for e in events if e["event_type"] == "SETTINGS_UPDATED")
    assert settings_event["payload"]["provider"]["to"] == "openai"


def test_project_history_records_creation_and_revisions(auth: TestClient) -> None:
    """History answers 'what happened to this project' without reading files."""
    body = _create(auth)
    pid = body["project_id"]
    auth.put(f"{BASE}/{pid}/content", json={"content": {**body["content"], "n": 5}})

    types = [e["event_type"] for e in auth.get(f"{BASE}/{pid}/events").json()]
    assert "PROJECT_CREATED" in types
    assert types.count("REVISION_SAVED") == 2


def test_trash_and_restore_round_trip(auth: TestClient) -> None:
    """Trashing hides a project from the portfolio but loses nothing."""
    body = _create(auth)
    pid = body["project_id"]

    assert auth.post(f"{BASE}/{pid}/trash").json()["status"] == "TRASHED"
    assert auth.get(BASE).json()["page"]["total"] == 0
    assert auth.get(BASE, params={"include_trashed": True}).json()["page"]["total"] == 1
    assert auth.get(f"{BASE}/{pid}").json()["content"] == body["content"]

    assert auth.post(f"{BASE}/{pid}/restore").json()["status"] == "READY_TO_CONTINUE"
    assert auth.get(BASE).json()["page"]["total"] == 1


# --------------------------------------------------------------------------- #
# Listing contract
# --------------------------------------------------------------------------- #


def test_listing_paginates_with_stable_metadata(auth: TestClient) -> None:
    """Pagination metadata is identical in shape on every list endpoint."""
    for i in range(5):
        _create(auth, title=f"P{i}")

    page = auth.get(BASE, params={"limit": 2}).json()
    assert page["page"] == {"total": 5, "limit": 2, "offset": 0, "has_more": True}
    assert len(page["items"]) == 2

    last = auth.get(BASE, params={"limit": 2, "offset": 4}).json()
    assert last["page"]["has_more"] is False


def test_listing_rejects_out_of_range_limit(auth: TestClient) -> None:
    """The API rejects an absurd page size rather than silently clamping it."""
    assert auth.get(BASE, params={"limit": 10_000}).status_code == 422
    assert auth.get(BASE, params={"limit": 0}).status_code == 422
    assert auth.get(BASE, params={"offset": -1}).status_code == 422


def test_listing_filters(auth: TestClient) -> None:
    """Type and search filters narrow the portfolio."""
    _create(auth, title="Brand study")
    _create(auth, title="Price simulation", project_type="simulation")

    assert auth.get(BASE, params={"project_type": "simulation"}).json()["page"]["total"] == 1
    assert auth.get(BASE, params={"search": "brand"}).json()["page"]["total"] == 1
    assert auth.get(BASE, params={"status": "DRAFT"}).json()["page"]["total"] == 2


def test_listing_rejects_unknown_status(auth: TestClient) -> None:
    """An unknown status is a client error with the allowed values attached."""
    response = auth.get(BASE, params={"status": "BANANA"})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_status"
    assert "DRAFT" in response.json()["details"]["allowed"]


# --------------------------------------------------------------------------- #
# Error contract and information disclosure
# --------------------------------------------------------------------------- #


def test_malformed_project_id_is_rejected_by_the_route(auth: TestClient) -> None:
    """Path validation blocks traversal and injection attempts at the edge."""
    for bad in ("../../etc/passwd", "PRJ-'; DROP TABLE projects; --", "not-a-project"):
        assert auth.get(f"{BASE}/{bad}").status_code in (404, 422)


def test_errors_share_one_shape(auth: TestClient) -> None:
    """Every error carries code, message, details and request_id."""
    response = auth.get(f"{BASE}/PRJ-0000000000abcd")
    body = response.json()

    assert response.status_code == 404
    assert set(body) == {"code", "message", "details", "request_id"}
    assert body["code"] == "project_not_found"


def test_stage_fingerprint_is_not_fully_exposed(auth: TestClient) -> None:
    """Only a short fingerprint prefix reaches the client.

    The full value is an internal artifact-reuse key; publishing it invites
    clients to depend on cache behaviour we may change.
    """
    body = _create(auth)
    for stage in body["stages"]:
        assert len(stage["fingerprint_prefix"]) <= 12


def test_responses_never_expose_internal_fields(auth: TestClient) -> None:
    """Tenant ids and storage locations must not leak into a response body."""
    body = _create(auth)
    serialised = str(body)

    assert "organization_id" not in serialised
    assert "ORG-primary" not in serialised
    assert "storage_key" not in serialised
