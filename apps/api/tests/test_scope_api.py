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
