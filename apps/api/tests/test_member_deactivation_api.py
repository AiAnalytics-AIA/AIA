"""POST /members/{id}/deactivate and /reactivate (D-27, ADR 0030, settings-backends SB2)."""

from __future__ import annotations

from typing import Any

from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import AccessAuditRow
from fastapi.testclient import TestClient
from sqlalchemy import select

API = "/api/v1"


def test_an_owner_deactivates_and_reactivates_a_member(
    as_user: Any, world: Any, owner: TestClient
) -> None:
    lead_id = world.users["lead"]
    lead: TestClient = as_user("lead")
    assert lead.post(f"{API}/lead").status_code == 201

    off = owner.post(f"{API}/members/{lead_id}/deactivate")
    assert off.status_code == 200
    body = off.json()
    assert body["is_active"] is False and body["deactivated_at"] is not None
    assert body["lead_sealed_at"] is not None and body["lead_erase_after"] is not None
    # From the next request the member resolves nothing here, whatever token they hold.
    me = lead.get(f"{API}/workspace/me")
    assert me.status_code == 403 and me.json()["code"] == "member_deactivated"
    assert lead.get(f"{API}/lead").status_code == 403

    on = owner.post(f"{API}/members/{lead_id}/reactivate")
    assert on.status_code == 200 and on.json()["is_active"] is True
    assert on.json()["lead_sealed_at"] is None
    back = lead.get(f"{API}/lead")
    assert back.status_code == 200 and back.json()["hatched"] is True


def test_a_member_cannot_deactivate_anyone(as_user: Any, world: Any) -> None:
    researcher: TestClient = as_user("researcher")
    refused = researcher.post(f"{API}/members/{world.users['lead']}/deactivate")
    assert refused.status_code == 403


def test_someone_outside_the_organization_is_not_found(owner: TestClient) -> None:
    missing = owner.post(f"{API}/members/USR-nobody/deactivate")
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"


def test_the_last_owner_is_refused_by_name(owner: TestClient) -> None:
    me = owner.get(f"{API}/workspace/me").json()["user_id"]
    refused = owner.post(f"{API}/members/{me}/deactivate")
    assert refused.status_code == 403
    assert refused.json()["details"]["reason"] == "last_owner"


def test_a_refused_deactivation_is_in_the_access_audit(
    app: Any, owner: TestClient, as_user: Any
) -> None:
    """The refusal of the OWNER rule is the security-relevant event: it survives the 403's
    rollback, as a refused role change does, naming the person and the change."""
    me = owner.get(f"{API}/workspace/me").json()["user_id"]
    assert owner.post(f"{API}/members/{me}/deactivate").status_code == 403  # last_owner
    owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    admin = as_user("lead")
    assert admin.post(f"{API}/members/{me}/deactivate").status_code == 403  # owner_only
    assert admin.post(f"{API}/members/{me}/reactivate").status_code == 200  # not deactivated

    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.action == "MEMBER_ROLE_DENIED")
            .order_by(AccessAuditRow.event_id)
        ).all()
        deactivated = session.scalars(
            select(AccessAuditRow).where(AccessAuditRow.action == "MEMBER_DEACTIVATED")
        ).all()
    assert [(r.reason, r.role, r.payload, r.subject_user_id) for r in rows] == [
        ("last_owner", "OWNER", {"change": "deactivate"}, me),
        ("owner_only", "OWNER", {"change": "deactivate"}, me),
    ]
    assert deactivated == []
