"""Self-approval over HTTP: an administrative act, audited, with inheritance."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_nothing_configured_reads_as_null_not_false(owner: TestClient) -> None:
    response = owner.get(f"{API}/self-approval")
    assert response.status_code == 200
    assert response.json() == {"organization": None, "clients": [], "studies": []}


def test_an_owner_configures_each_level(owner: TestClient, world: Any) -> None:
    organization = owner.put(f"{API}/self-approval", json={"allowed": True})
    assert organization.status_code == 200
    assert organization.json() == {"allowed": True, "source": "organization"}

    client_id = world.client_id("primary")
    client = owner.put(f"{API}/self-approval", json={"allowed": False, "client_id": client_id})
    assert client.json() == {"allowed": False, "source": "client"}

    study_id = world.study_id("primary")
    study = owner.put(f"{API}/self-approval", json={"allowed": True, "study_id": study_id})
    assert study.json() == {"allowed": True, "source": "study"}

    levels = owner.get(f"{API}/self-approval").json()
    assert levels["organization"] is True
    assert levels["clients"] == [{"client_id": client_id, "allowed": False}]
    assert levels["studies"] == [{"study_id": study_id, "client_id": client_id, "allowed": True}]


def test_null_restores_inheritance(owner: TestClient, world: Any) -> None:
    client_id = world.client_id("primary")
    owner.put(f"{API}/self-approval", json={"allowed": True})
    owner.put(f"{API}/self-approval", json={"allowed": False, "client_id": client_id})

    cleared = owner.put(f"{API}/self-approval", json={"allowed": None, "client_id": client_id})
    assert cleared.json() == {"allowed": True, "source": "organization"}
    assert owner.get(f"{API}/self-approval").json()["clients"] == []


def test_a_study_lead_cannot_configure_or_read_it(lead: TestClient, world: Any) -> None:
    """A LEAD must not be able to arrange self-approval for their own study."""
    study_id = world.study_id("primary")
    response = lead.put(f"{API}/self-approval", json={"allowed": True, "study_id": study_id})
    assert response.status_code == 403
    assert lead.get(f"{API}/self-approval").status_code == 403


def test_configuring_it_is_audited(owner: TestClient, world: Any) -> None:
    client_id = world.client_id("primary")
    owner.put(f"{API}/self-approval", json={"allowed": True, "client_id": client_id})
    audit = owner.get(f"{API}/access-audit").json()
    entry = next(e for e in audit if e["action"] == "SELF_APPROVAL_CONFIGURED")
    assert entry["client_id"] == client_id
    assert entry["reason"] == "client=true"


def test_an_unknown_level_is_not_found(owner: TestClient) -> None:
    response = owner.put(f"{API}/self-approval", json={"allowed": True, "client_id": "CLI-0"})
    assert response.status_code == 404


def test_a_client_and_a_study_together_are_refused(owner: TestClient, world: Any) -> None:
    response = owner.put(
        f"{API}/self-approval",
        json={
            "allowed": True,
            "client_id": world.client_id("primary"),
            "study_id": world.study_id("primary"),
        },
    )
    assert response.status_code == 422


def test_the_body_is_closed(owner: TestClient) -> None:
    response = owner.put(f"{API}/self-approval", json={"allowed": True, "scope": "everything"})
    assert response.status_code == 422


def test_the_request_requires_an_explicit_value(owner: TestClient) -> None:
    """``allowed`` has no default: forgetting it must not mean inherit or false."""
    assert owner.put(f"{API}/self-approval", json={}).status_code == 422
