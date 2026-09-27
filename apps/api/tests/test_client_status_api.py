"""Client lifecycle status over HTTP."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_an_owner_archives_a_client_and_it_leaves_the_default_list(
    owner: TestClient, world: Any
) -> None:
    client_id = world.client_id("other")
    response = owner.put(f"{API}/clients/{client_id}/status", json={"status": "ARCHIVED"})
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
    assert response.json()["study_count"] == 1

    listed = {c["client_id"] for c in owner.get(f"{API}/clients").json()}
    assert client_id not in listed
    everything = owner.get(f"{API}/clients", params={"include_archived": True}).json()
    assert client_id in {c["client_id"] for c in everything}


def test_the_change_is_audited(owner: TestClient, world: Any) -> None:
    client_id = world.client_id("primary")
    owner.put(f"{API}/clients/{client_id}/status", json={"status": "DORMANT"})
    audit = owner.get(f"{API}/access-audit").json()
    entry = next(e for e in audit if e["action"] == "CLIENT_STATUS_CHANGED")
    assert (entry["client_id"], entry["reason"]) == (client_id, "DORMANT")


def test_a_study_lead_cannot_change_it(lead: TestClient, world: Any) -> None:
    response = lead.put(
        f"{API}/clients/{world.client_id('primary')}/status", json={"status": "ARCHIVED"}
    )
    assert response.status_code == 403


def test_an_unknown_client_is_not_found(owner: TestClient) -> None:
    response = owner.put(f"{API}/clients/CLI-0/status", json={"status": "ACTIVE"})
    assert response.status_code == 404


def test_only_client_statuses_are_accepted(owner: TestClient, world: Any) -> None:
    url = f"{API}/clients/{world.client_id('primary')}/status"
    assert owner.put(url, json={"status": "DELIVERED"}).status_code == 422
    assert owner.put(url, json={"status": "ACTIVE", "force": True}).status_code == 422
