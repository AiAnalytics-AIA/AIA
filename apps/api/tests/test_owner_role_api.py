"""Only an OWNER grants or removes OWNER, over the API (security-audit-2026-10 S14).

The rule lives in ``ScopeRepository.add_member``; this holds the route to it: an ADMIN's
request is a 403 naming the reason, and an OWNER's goes through.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_an_admin_is_refused_owner_and_an_owner_grants_it(owner: TestClient, as_user: Any) -> None:
    promoted = owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    assert promoted.status_code == 201, promoted.text
    admin = as_user("lead")

    refused = admin.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "OWNER"})
    assert refused.status_code == 403
    assert refused.json()["details"]["reason"] == "owner_only"
    demoted = admin.post(f"{API}/members", json={"email": "owner@art-chain.io", "role": "MEMBER"})
    assert demoted.status_code == 403
    assert demoted.json()["details"]["reason"] == "owner_only"

    granted = owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "OWNER"})
    assert granted.status_code == 201, granted.text
    assert granted.json()["organization_role"] == "OWNER"
