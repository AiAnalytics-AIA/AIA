"""The access audit trail over HTTP."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_an_owner_reads_the_trail(owner: TestClient, world: Any) -> None:
    """Every provisioned grant is in the trail, and the trail serialises.

    Regression: the resolver's entries carry an internal ``payload`` the closed
    response model forbids, so this route answered 500 for any organization that
    had granted anyone anything.
    """
    response = owner.get(f"{API}/access-audit")
    assert response.status_code == 200
    entries = response.json()
    assert entries
    assert all("payload" not in e for e in entries)
    granted = {e["subject_user_id"] for e in entries if e["action"] == "CLIENT_GRANT"}
    assert world.users["lead"] in granted


def test_a_member_may_not_read_the_trail(lead: TestClient) -> None:
    assert lead.get(f"{API}/access-audit").status_code == 403


def test_the_limit_is_bounded(owner: TestClient) -> None:
    assert owner.get(f"{API}/access-audit", params={"limit": 0}).status_code == 422
    assert owner.get(f"{API}/access-audit", params={"limit": 1001}).status_code == 422
    assert len(owner.get(f"{API}/access-audit", params={"limit": 1}).json()) == 1
