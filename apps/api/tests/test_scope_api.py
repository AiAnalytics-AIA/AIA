"""The scope router's administrative reads, which no API test exercised before."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_the_access_audit_lists_entries_with_their_payload(
    owner: TestClient, lead: TestClient, world: Any
) -> None:
    # A grant writes a before/after payload; the audit exists to show it later.
    granted = lead.post(
        f"{API}/studies/{world.study_id()}/grants",
        json={"user_id": world.users["outsider"], "role": "VIEWER"},
    )
    assert granted.status_code == 204
    response = owner.get(f"{API}/access-audit")
    assert response.status_code == 200, response.text
    entries = response.json()
    assert entries and all("payload" in e for e in entries)
    assert any(e["payload"] for e in entries)


def test_the_access_audit_is_for_administrators(lead: TestClient) -> None:
    assert lead.get(f"{API}/access-audit").status_code == 403


def test_a_study_created_by_an_administrator_reports_the_one_role(
    owner: TestClient, world: Any
) -> None:
    """ADR 0019: the creation response named a role that no longer exists (LEAD)."""
    response = owner.post(
        f"{API}/studies",
        json={
            "client_id": world.client_id(),
            "slug": "fresh-2026",
            "name": "Fresh study",
            "budget_usd": 50.0,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["your_role"] == "RESEARCHER"


def test_an_archived_clients_studies_are_not_in_the_portfolio_listing(
    owner: TestClient, lead: TestClient, world: Any
) -> None:
    """Archived clients stay invisible in `GET /studies` as on a direct read (ADR 0019).

    Every member lists every study now, so an archived client's study names and metadata
    would otherwise reach everyone, though opening the study itself is refused.
    """
    primary = world.study_id("primary")
    listed = {s["study_id"] for s in lead.get(f"{API}/studies").json()}
    assert primary in listed and world.study_id("other_client") in listed

    archived = owner.put(f"{API}/clients/{world.client_id()}/status", json={"status": "ARCHIVED"})
    assert archived.status_code == 200, archived.text

    after = {s["study_id"] for s in lead.get(f"{API}/studies").json()}
    assert primary not in after and world.study_id("other_client") in after
    by_client = lead.get(f"{API}/studies", params={"client_id": world.client_id()})
    assert by_client.status_code == 200 and by_client.json() == []
    assert lead.get(f"{API}/studies/{primary}").status_code == 404
