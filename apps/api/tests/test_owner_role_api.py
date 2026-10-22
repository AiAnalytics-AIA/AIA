"""Only an OWNER grants or removes OWNER, over the API (security-audit-2026-10 S14).

The rule lives in ``ScopeRepository.add_member``; this holds the route to it: an ADMIN's
request is a 403 naming the reason, and an OWNER's goes through.
"""

from __future__ import annotations

from typing import Any

from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import AccessAuditRow, UserRow
from fastapi.testclient import TestClient
from sqlalchemy import select

API = "/api/v1"


def test_an_admin_is_refused_owner_and_an_owner_grants_it(owner: TestClient, as_user: Any) -> None:
    promoted = owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    assert promoted.status_code == 201, promoted.text
    admin = as_user("lead")

    refused = admin.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "OWNER"})
    assert refused.status_code == 403
    assert refused.json()["details"]["reason"] == "owner_only"
    assert refused.json()["message"] == "Only an OWNER grants or removes the OWNER role."
    demoted = admin.post(f"{API}/members", json={"email": "owner@art-chain.io", "role": "MEMBER"})
    assert demoted.status_code == 403
    assert demoted.json()["details"]["reason"] == "owner_only"

    granted = owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "OWNER"})
    assert granted.status_code == 201, granted.text
    assert granted.json()["organization_role"] == "OWNER"


def test_a_refused_owner_change_is_in_the_access_audit(
    app: Any, owner: TestClient, as_user: Any
) -> None:
    # The refusal is the security-relevant event: it survives the 403's rollback.
    owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    admin = as_user("lead")
    refused = admin.post(f"{API}/members", json={"email": "owner@art-chain.io", "role": "MEMBER"})
    assert refused.status_code == 403

    factory = create_session_factory(app.state.engine)
    with factory() as session:
        rows = session.scalars(
            select(AccessAuditRow).where(AccessAuditRow.action == "MEMBER_ROLE_DENIED")
        ).all()
        stray = session.scalar(select(UserRow).where(UserRow.email == "nobody@art-chain.io"))
    assert [(r.reason, r.role, r.payload) for r in rows] == [
        ("owner_only", "MEMBER", {"email": "owner@art-chain.io"})
    ]
    assert stray is None

    # A refused grant to a new address writes the audit row and no user for that address.
    admin.post(f"{API}/members", json={"email": "nobody@art-chain.io", "role": "OWNER"})
    with factory() as session:
        stray = session.scalar(select(UserRow).where(UserRow.email == "nobody@art-chain.io"))
        count = len(
            session.scalars(
                select(AccessAuditRow).where(AccessAuditRow.action == "MEMBER_ROLE_DENIED")
            ).all()
        )
    assert stray is None
    assert count == 2
