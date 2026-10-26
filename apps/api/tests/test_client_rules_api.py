"""A client's rules over HTTP (settings-backends SB7)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"


def test_a_member_reads_and_an_owner_sets_the_rules(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}/rules"
    fresh = researcher.get(url)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["data_posture"] is None
    assert fresh.json()["effective_posture"] == "CLASSIFIED"
    set_ = owner.put(url, json={"data_posture": "OPEN", "wallet_ceiling_usd": 40})
    assert set_.status_code == 200, set_.text
    assert (set_.json()["effective_posture"], set_.json()["wallet_ceiling_usd"]) == ("OPEN", 40.0)
    assert set_.json()["set_by"] is not None and set_.json()["set_at"] is not None
    # Only what is sent changes; null clears.
    cleared = owner.put(url, json={"wallet_ceiling_usd": None}).json()
    assert (cleared["data_posture"], cleared["wallet_ceiling_usd"]) == ("OPEN", None)
    listed = {r["client_id"]: r for r in researcher.get(f"{API}/settings/client-rules").json()}
    assert listed[world.client_id()]["effective_posture"] == "OPEN"
    assert listed[world.client_id("other")]["effective_posture"] == "CLASSIFIED"


def test_a_researcher_cannot_set_them_and_a_wrong_value_is_refused(
    owner: TestClient, researcher: TestClient, world: Any
) -> None:
    url = f"{API}/clients/{world.client_id()}/rules"
    assert researcher.put(url, json={"data_posture": "OPEN"}).status_code == 403
    assert owner.put(url, json={"data_posture": "MAYBE"}).status_code == 422
    assert owner.put(url, json={"wallet_ceiling_usd": -1}).status_code == 422
    assert owner.get(f"{API}/clients/CLI-nobody/rules").status_code == 404


def _other_organization(app: Any, role: str) -> TestClient:
    """An OWNER (or that OWNER's ADMIN) of a second organization, signed in."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.scope import OrganizationRole
    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with create_session_factory(app.state.engine)() as session:
        repo = ScopeRepository(session)
        org, owner = repo.create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="o@elsewhere.example"
        )
        email = "o@elsewhere.example"
        if role == "ADMIN":
            admin = ScopeResolver(session).organization_context(
                AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
            )
            email = "a@elsewhere.example"
            repo.add_member(admin, email=email, role=OrganizationRole.ADMIN)
        session.commit()
    token = f"token-elsewhere-{role.lower()}"
    app.state.identity_provider.register(token, subject=email, email=email)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_an_owner_of_another_organization_neither_reads_nor_sets_them(
    app: Any, owner: TestClient, world: Any
) -> None:
    """The organization filter is the only guard: another organization's OWNER finds no such
    client, cannot set its rules, and does not see it listed."""
    url = f"{API}/clients/{world.client_id()}/rules"
    theirs = _other_organization(app, "OWNER")
    assert theirs.get(url).status_code == 404
    assert theirs.put(url, json={"data_posture": "OPEN"}).status_code == 404
    listed = [r["client_id"] for r in theirs.get(f"{API}/settings/client-rules").json()]
    assert world.client_id() not in listed and world.client_id("other") not in listed
    assert owner.get(url).json()["data_posture"] is None  # nothing changed


def test_an_admin_of_another_organization_is_refused_too(
    app: Any, owner: TestClient, world: Any
) -> None:
    theirs = _other_organization(app, "ADMIN")
    url = f"{API}/clients/{world.client_id()}/rules"
    assert theirs.get(url).status_code == 404
    assert theirs.put(url, json={"wallet_ceiling_usd": 1}).status_code == 404
    assert world.client_id() not in [
        r["client_id"] for r in theirs.get(f"{API}/settings/client-rules").json()
    ]
    assert owner.get(url).json()["wallet_ceiling_usd"] is None


def test_an_admin_who_is_not_the_owner_sets_them(
    owner: TestClient, as_user: Any, world: Any
) -> None:
    owner.post(f"{API}/members", json={"email": "lead@art-chain.io", "role": "ADMIN"})
    admin: TestClient = as_user("lead")
    url = f"{API}/clients/{world.client_id()}/rules"
    set_ = admin.put(url, json={"data_posture": "OPEN", "wallet_ceiling_usd": 9})
    assert set_.status_code == 200, set_.text
    assert set_.json()["set_by"] == world.users["lead"]
    assert owner.get(url).json()["effective_posture"] == "OPEN"
