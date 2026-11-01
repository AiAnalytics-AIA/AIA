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
    assert [(r.reason, r.role, r.payload) for r in rows] == [("owner_only", "MEMBER", {})]
    # The person is the row's subject; an address is never kept (as record_subject_mismatch).
    assert rows[0].subject_user_id is not None
    assert stray is None

    # A refused grant to a new address writes the audit row and no user for that address.
    admin.post(f"{API}/members", json={"email": "nobody@art-chain.io", "role": "OWNER"})
    with factory() as session:
        stray = session.scalar(select(UserRow).where(UserRow.email == "nobody@art-chain.io"))
        rows = session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.action == "MEMBER_ROLE_DENIED")
            .order_by(AccessAuditRow.event_id)
        ).all()
    assert stray is None
    assert len(rows) == 2
    assert rows[1].subject_user_id is None and rows[1].payload == {}


def test_an_address_that_is_no_address_is_refused_and_makes_no_user(
    app: Any, owner: TestClient
) -> None:
    """Sign-in binds a member by their e-mail: "alice" made a member who could never sign in
    (the Codex finding on #828)."""
    for bad in ("alice", "alice@", "@example.org", "a b@example.org", "alice@example", ""):
        refused = owner.post(f"{API}/members", json={"email": bad, "role": "MEMBER"})
        assert refused.status_code == 422, (bad, refused.text)
    with create_session_factory(app.state.engine)() as session:
        assert session.scalar(select(UserRow).where(UserRow.email == "alice")) is None
    added = owner.post(f"{API}/members", json={"email": "  Alice@Example.org ", "role": "MEMBER"})
    assert added.status_code == 201, added.text
    assert added.json()["email"] == "alice@example.org"
