"""PUT /members/{user_id}/methodologist over HTTP (D-14, settings-backends SB1).

Only an OWNER grants or revokes the Metodik mark, refused by name (``owner_only``) and leaving
no mark change in the audit; a user of another organization is not found, whoever they are.
"""

from __future__ import annotations

from typing import Any

from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import AccessAuditRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

API = "/api/v1"


def _mark_rows(app: FastAPI) -> list[str]:
    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(AccessAuditRow.action).where(
                    AccessAuditRow.action.in_(("METHODOLOGIST_GRANTED", "METHODOLOGIST_REVOKED"))
                )
            )
        )


def test_an_admin_is_refused_owner_only_and_no_mark_changes(
    app: FastAPI, owner: TestClient, as_user: Any, world: Any
) -> None:
    promoted = owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    assert promoted.status_code == 201, promoted.text
    admin: TestClient = as_user("lead")
    refused = admin.put(
        f"{API}/members/{world.users['researcher']}/methodologist", json={"methodologist": True}
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "owner_only"
    assert _mark_rows(app) == []
    listed = {m["user_id"]: m for m in owner.get(f"{API}/members").json()}
    assert listed[world.users["researcher"]]["methodologist"] is False


def test_an_owner_cannot_mark_a_user_of_another_organization(
    app: FastAPI, owner: TestClient
) -> None:
    with create_session_factory(app.state.engine)() as session:
        _, theirs = ScopeRepository(session).create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="o@example.org", owner_name="O"
        )
        session.commit()
    missing = owner.put(
        f"{API}/members/{theirs.user_id}/methodologist", json={"methodologist": True}
    )
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    assert _mark_rows(app) == []
