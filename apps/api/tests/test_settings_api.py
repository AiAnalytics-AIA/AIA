"""The settings document: who may read what, and that values come from the code."""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.evidence import REFERENCE_THRESHOLDS
from aia_core.domain.providers import (
    DEFAULT_MAX_API_COST_USD,
    Provider,
    ProviderPolicy,
    is_paid,
)
from aia_core.domain.scope import ROLE_PERMISSIONS, OrganizationRole, StudyStatus
from aia_core.domain.workflow import DEFAULT_LEASE_SECONDS
from fastapi.testclient import TestClient

from aia_api.routers.settings import _database_backend

API = "/api/v1"


def _groups(body: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    return {g["key"]: {i["key"]: i for i in g["items"]} for g in body["groups"]}


def test_settings_require_authentication(client: TestClient, world: Any) -> None:
    assert client.get(f"{API}/settings").status_code == 401


def test_an_owner_sees_the_deployment_group(owner: TestClient) -> None:
    response = owner.get(f"{API}/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["your_role"] == "OWNER"
    assert body["may_administer"] is True
    deployment = _groups(body)["deployment"]
    assert deployment["env"]["value"] == "test"
    assert deployment["env"]["control"] == "DEPLOYMENT"
    assert deployment["env"]["source"] == "AIA_ENV"
    assert deployment["identity_provider"]["value"] == "test"


def test_a_member_does_not_see_the_deployment_group(researcher: TestClient) -> None:
    body = researcher.get(f"{API}/settings").json()
    assert body["your_role"] == "MEMBER"
    assert body["may_administer"] is False
    assert "deployment" not in _groups(body)
    # Everything else is the same document.
    assert "studies" in _groups(body)


def test_no_secret_reaches_the_document(owner: TestClient) -> None:
    raw = owner.get(f"{API}/settings").text
    # The test database URL is a path, not a secret, but a production URL carries a
    # password: only the backend name may appear.
    deployment = _groups(owner.get(f"{API}/settings").json())["deployment"]
    # CI's SQLite job runs with DATABASE_URL="" (not configured), the PostgreSQL job
    # with a URL: either way the document carries a backend name or null, never a URL.
    assert deployment["database_backend"]["value"] in {None, "sqlite", "postgresql"}
    assert "://" not in raw
    assert deployment["cognito_configured"]["value"] is False


@pytest.mark.parametrize(
    ("url", "backend"),
    [
        ("", None),
        ("   ", None),
        ("sqlite+pysqlite:///:memory:", "sqlite"),
        ("postgresql+psycopg://aia:s3cret@db.internal:5432/aia", "postgresql"),
        ("postgres://aia:s3cret@db.internal/aia", "postgresql"),
    ],
)
def test_a_database_url_is_reduced_to_its_backend(url: str, backend: str | None) -> None:
    """Unset is null, not a guessed default; a password never survives."""
    assert _database_backend(url) == backend


def test_values_are_the_domain_constants(owner: TestClient) -> None:
    groups = _groups(owner.get(f"{API}/settings").json())
    assert groups["studies"]["default_project_max_api_cost"]["value"] == DEFAULT_MAX_API_COST_USD
    assert groups["workflow"]["lease_seconds"]["value"] == DEFAULT_LEASE_SECONDS
    assert groups["evidence"]["min_cell"]["value"] == REFERENCE_THRESHOLDS.min_cell
    assert groups["evidence"]["tier_C_permits"]["value"] == ["internal_experimental"]


def test_every_item_states_its_control_and_source(owner: TestClient) -> None:
    body = owner.get(f"{API}/settings").json()
    for group in body["groups"]:
        assert group["items"], group["key"]
        for item in group["items"]:
            assert item["control"] in {"API", "DEPLOYMENT", "CODE", "INVARIANT"}
            assert item["source"].strip(), item["key"]


def test_invariants_are_in_force_and_not_editable(owner: TestClient) -> None:
    body = owner.get(f"{API}/settings").json()
    invariants = [i for g in body["groups"] for i in g["items"] if i["control"] == "INVARIANT"]
    assert {i["key"] for i in invariants} >= {
        "no_silent_provider_fallback",
        "no_spend_past_budget",
        "no_invented_certainty",
        "no_fake_progress",
        "no_visualisation_mutation",
        "eu_residency",
    }
    assert all(i["value"] is True for i in invariants)


def test_api_controls_name_a_route_that_exists(owner: TestClient, app: Any) -> None:
    routes = {
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    body = owner.get(f"{API}/settings").json()
    for group in body["groups"]:
        for item in group["items"]:
            if item["control"] == "API":
                assert item["source"] in routes, item


def test_vocabularies_are_the_domain_enums(researcher: TestClient) -> None:
    vocab = researcher.get(f"{API}/settings").json()["vocabularies"]
    assert vocab["organization_roles"] == [r.value for r in OrganizationRole]
    assert vocab["study_statuses"] == [s.value for s in StudyStatus]
    assert vocab["provider_policies"] == [p.value for p in ProviderPolicy]
    assert [p["id"] for p in vocab["providers"]] == [p.value for p in Provider]
    paid = {p["id"]: p["paid"] for p in vocab["providers"]}
    assert paid == {p.value: is_paid(p) for p in Provider}
    # The subscription runtime has no marginal cost; the per-token APIs do.
    assert paid["claude_code_subscription"] is False
    assert paid["anthropic"] is True
    by_role = {r["role"]: set(r["permissions"]) for r in vocab["scope_roles"]}
    assert by_role == {
        role.value: {p.value for p in granted} for role, granted in ROLE_PERMISSIONS.items()
    }
    assert len(vocab["research_stages"]) == 13
    assert len(vocab["simulation_stages"]) == 13
