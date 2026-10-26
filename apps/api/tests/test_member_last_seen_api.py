"""GET /members carries each member's last activity for an administrator (settings-redesign F19).

Settings -> Přístup draws it as the Naposledy column (F9). It is the member's own last
authenticated request: never an administrator's change to them, never a guess, and null for a
member who has made none, which the page reads as never.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import UserRow
from fastapi.testclient import TestClient

API = "/api/v1"


def _seen(owner: TestClient) -> dict[str, str | None]:
    response = owner.get(f"{API}/members")
    assert response.status_code == 200
    return {m["email"]: m["last_seen_at"] for m in response.json()}


def _parse(value: str | None) -> datetime:
    assert value is not None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_a_member_who_made_a_request_has_a_time_and_one_who_never_did_has_none(
    as_user: Any, owner: TestClient
) -> None:
    before = datetime.now(UTC) - timedelta(seconds=5)
    assert as_user("lead").get(f"{API}/workspace/me").status_code == 200
    seen = _seen(owner)
    # The owner's own read is a request too; the lead's was made just now.
    assert _parse(seen["lead@art-chain.io"]) >= before
    assert _parse(seen["owner@art-chain.io"]) >= before
    # Provisioned, never signed in: null, never a date.
    assert seen["viewer@art-chain.io"] is None
    # Every time is UTC, whichever database stored it.
    assert _parse(seen["lead@art-chain.io"]).tzinfo is not None


def test_an_administrators_change_to_a_member_is_not_the_member_being_seen(
    owner: TestClient,
) -> None:
    """Adding a member and changing their role upsert the same user row; neither stamps it."""
    assert _seen(owner)["researcher@art-chain.io"] is None
    changed = owner.post(
        f"{API}/members", json={"email": "researcher@art-chain.io", "role": "ADMIN"}
    )
    assert changed.status_code in (200, 201)
    assert changed.json()["last_seen_at"] is None
    assert _seen(owner)["researcher@art-chain.io"] is None
    added = owner.post(f"{API}/members", json={"email": "new-one@art-chain.io", "role": "MEMBER"})
    assert added.status_code in (200, 201)
    assert _seen(owner)["new-one@art-chain.io"] is None


def test_a_member_who_may_not_administer_reads_no_ones_activity(
    as_user: Any, owner: TestClient
) -> None:
    assert as_user("lead").get(f"{API}/workspace/me").status_code == 200
    assert _seen(owner)["lead@art-chain.io"] is not None
    listed = as_user("researcher").get(f"{API}/members")
    assert listed.status_code == 200
    assert {m["last_seen_at"] for m in listed.json()} == {None}


def test_the_repository_stamps_only_the_persons_own_request(app: Any, world: Any) -> None:
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        repo = ScopeRepository(session)
        repo.upsert_user(email="viewer@art-chain.io", display_name="Viewer")
        repo.upsert_user(email="brand-new@art-chain.io")
        session.flush()
        stamps = {
            row.email: row.last_seen_at
            for row in session.query(UserRow).filter(
                UserRow.email.in_(["viewer@art-chain.io", "brand-new@art-chain.io"])
            )
        }
        assert stamps == {"viewer@art-chain.io": None, "brand-new@art-chain.io": None}
        repo.upsert_user(email="viewer@art-chain.io", seen=True)
        repo.upsert_user(email="seen-first@art-chain.io", seen=True)
        session.flush()
        for email in ("viewer@art-chain.io", "seen-first@art-chain.io"):
            row = session.query(UserRow).filter(UserRow.email == email).one()
            assert row.last_seen_at is not None
        session.rollback()
