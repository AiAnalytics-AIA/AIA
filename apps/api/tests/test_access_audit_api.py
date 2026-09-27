"""The access audit trail's bounds. Its shape and guard are in test_scope_api.py."""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"


def test_the_limit_is_bounded(owner: TestClient) -> None:
    assert owner.get(f"{API}/access-audit", params={"limit": 0}).status_code == 422
    assert owner.get(f"{API}/access-audit", params={"limit": 1001}).status_code == 422
    assert len(owner.get(f"{API}/access-audit", params={"limit": 1}).json()) == 1
