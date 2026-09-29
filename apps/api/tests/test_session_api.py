"""AIA's own session and the gate in front of its pages (ADR 0018 decision 3, OI-59).

Caddy asks ``GET /api/v1/session/gate`` before serving any request to ``/app``, so
these tests drive the gate exactly as ``forward_auth`` does: the original method
and URI in ``X-Forwarded-Method`` / ``X-Forwarded-Uri``, the browser's cookies and
``Accept`` copied through. Admission is membership, not role, and nothing about
the 18.6.6 unit decides it.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import AccessAuditRow, UserRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from aia_api.config import Environment, Settings

API = "/api/v1"
SESSION = f"{API}/session"
GATE = f"{API}/session/gate"
HTML = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


@pytest.fixture
def anonymous(app: FastAPI) -> TestClient:
    # follow_redirects off: the gate's 302 is the answer under test.
    return TestClient(app, follow_redirects=False)


def _gate(
    client: TestClient,
    *,
    cookie: str | None = None,
    method: str = "GET",
    uri: str = "/app/clients",
    accept: str = "*/*",
) -> Any:
    headers = {"X-Forwarded-Method": method, "X-Forwarded-Uri": uri, "Accept": accept}
    if cookie is not None:
        headers["Cookie"] = f"aia_session={cookie}"
    return client.get(GATE, headers=headers)


def _audit(app: FastAPI, prefix: str) -> list[str]:
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        return sorted(
            session.scalars(
                select(AccessAuditRow.action).where(AccessAuditRow.action.like(f"{prefix}%"))
            )
        )


# --------------------------------------------------------------------------- #
# Opening and closing a session
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("label", ["owner", "lead", "viewer", "outsider"])
def test_every_active_member_gets_an_httponly_lax_session_cookie(
    anonymous: TestClient, world: Any, label: str
) -> None:
    # A member with no client grant too: what they may see inside is the API's
    # answer, client by client and study by study.
    response = anonymous.post(SESSION, headers={"Authorization": f"Bearer {world.tokens[label]}"})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"aia_session={world.tokens[label]};")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age" not in cookie  # a browser-session cookie
    assert "Secure" not in cookie  # not under test; wherever is_production


def test_someone_who_is_no_member_gets_no_session(app: FastAPI, anonymous: TestClient) -> None:
    app.state.identity_provider.register(
        "token-stranger", subject="stranger@example.test", email="stranger@example.test"
    )
    response = anonymous.post(SESSION, headers={"Authorization": "Bearer token-stranger"})
    assert response.status_code == 403
    assert response.json()["code"] == "not_provisioned"
    assert "set-cookie" not in response.headers


def test_a_deactivated_account_gets_no_session_and_loses_the_one_it_had(
    app: FastAPI, anonymous: TestClient, world: Any
) -> None:
    token = world.tokens["lead"]
    assert anonymous.post(SESSION, headers={"Authorization": f"Bearer {token}"}).status_code == 204
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        user = session.get(UserRow, world.users["lead"])
        assert user is not None
        user.is_active = False
        session.commit()
    refused = anonymous.post(SESSION, headers={"Authorization": f"Bearer {token}"})
    assert refused.status_code == 401
    assert "set-cookie" not in refused.headers
    # Deactivation takes effect on the next page, not at the token's expiry.
    assert _gate(anonymous, cookie=token).status_code == 401
    assert _gate(anonymous, cookie=token, accept=HTML).status_code == 302


def test_a_session_needs_a_verified_credential(anonymous: TestClient, world: Any) -> None:
    assert anonymous.post(SESSION).status_code == 401
    bad = anonymous.post(SESSION, headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert "set-cookie" not in bad.headers


def test_closing_the_session_clears_the_cookie(anonymous: TestClient) -> None:
    response = anonymous.delete(SESSION)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith('aia_session="";') or cookie.startswith("aia_session=;")
    assert "Max-Age=0" in cookie


def test_opening_a_session_is_audited_and_the_gate_is_not(
    app: FastAPI, anonymous: TestClient, world: Any
) -> None:
    anonymous.post(SESSION, headers={"Authorization": f"Bearer {world.tokens['viewer']}"})
    anonymous.post(SESSION, headers={"Authorization": f"Bearer {world.tokens['outsider']}"})
    assert _audit(app, "AIA_SESSION") == ["AIA_SESSION", "AIA_SESSION"]
    for _ in range(3):
        assert _gate(anonymous, cookie=world.tokens["viewer"]).status_code == 204
    assert _audit(app, "AIA_SESSION") == ["AIA_SESSION", "AIA_SESSION"]


# --------------------------------------------------------------------------- #
# The per-request gate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("label", ["owner", "researcher", "viewer", "outsider"])
def test_a_members_session_passes_the_gate(anonymous: TestClient, world: Any, label: str) -> None:
    token = world.tokens[label]
    assert _gate(anonymous, cookie=token, accept=HTML).status_code == 204
    # Next.js's own requests for a page's data are GETs too.
    assert _gate(anonymous, cookie=token, uri="/app/clients?_rsc=1").status_code == 204
    assert _gate(anonymous, cookie=token, method="HEAD").status_code == 204


def test_a_navigation_without_a_session_goes_to_login(anonymous: TestClient, world: Any) -> None:
    response = _gate(anonymous, uri="/app/clients/CLI-1/research?tab=all", accept=HTML)
    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "/login?next=%2Fapp%2Fclients%2FCLI-1%2Fresearch%3Ftab%3Dall"
    )


def test_a_fetch_without_a_session_is_refused_not_redirected(
    anonymous: TestClient, world: Any
) -> None:
    # A fetch() following a redirect to an HTML page would parse it as data.
    assert _gate(anonymous).status_code == 401


def test_an_expired_session_goes_back_through_login(
    app: FastAPI, anonymous: TestClient, world: Any
) -> None:
    app.state.identity_provider.expire(world.tokens["lead"])
    assert _gate(anonymous, cookie=world.tokens["lead"], accept=HTML).status_code == 302
    assert _gate(anonymous, cookie=world.tokens["lead"]).status_code == 401


def test_a_forged_cookie_is_refused(anonymous: TestClient, world: Any) -> None:
    assert _gate(anonymous, cookie="forged").status_code == 401
    # The 18.6.6 panel's cookie is not an AIA session.
    response = anonymous.get(
        GATE,
        headers={"X-Forwarded-Method": "GET", "Cookie": f"aia_panel={world.tokens['owner']}"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("uri", ["//evil.example/", "https://evil.example/", "/\\evil", ""])
def test_the_login_redirect_never_leaves_the_origin(
    anonymous: TestClient, world: Any, uri: str
) -> None:
    response = _gate(anonymous, uri=uri, accept=HTML)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_a_page_takes_no_writes_whoever_asks(
    anonymous: TestClient, world: Any, method: str
) -> None:
    response = _gate(anonymous, cookie=world.tokens["owner"], method=method)
    assert response.status_code == 403
    assert response.json()["code"] == "method_not_allowed"


# --------------------------------------------------------------------------- #
# Nothing of 18.6.6 decides it
# --------------------------------------------------------------------------- #


def test_the_session_and_its_gate_need_nothing_of_18_6_6(settings: Settings) -> None:
    """ADR 0018: no legacy setting decides it, and the 18.6.6 panel's routes are gone."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.infrastructure.scope_repository import ScopeRepository
    from aia_core.infrastructure.tables import Base

    from aia_api.main import create_app

    assert not [name for name in Settings.model_fields if "legacy" in name or "panel" in name]
    application = create_app(settings)
    with TestClient(application, follow_redirects=False) as client:
        Base.metadata.create_all(application.state.engine)
        factory = create_session_factory(application.state.engine)
        with factory() as session:
            org, owner = ScopeRepository(session).create_organization(
                slug="aia", name="AIA", owner_email="owner@example.test", owner_name="Owner"
            )
            admin = ScopeResolver(session).organization_context(
                AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
            )
            ScopeRepository(session).add_member(admin, email="member@example.test")
            session.commit()
        application.state.identity_provider.register(
            "token-member", subject="member@example.test", email="member@example.test"
        )
        opened = client.post(SESSION, headers={"Authorization": "Bearer token-member"})
        assert opened.status_code == 204
        assert _gate(client, cookie="token-member", accept=HTML).status_code == 204
        # The panel's session and gate, for an owner too: not there at all.
        application.state.identity_provider.register(
            "token-owner", subject="owner@example.test", email="owner@example.test"
        )
        for method, path in (
            ("POST", f"{API}/panel/session"),
            ("DELETE", f"{API}/panel/session"),
            ("GET", f"{API}/panel/gate"),
        ):
            response = client.request(
                method,
                path,
                headers={
                    "Authorization": "Bearer token-owner",
                    "X-Forwarded-Method": "GET",
                    "Cookie": "aia_panel=token-owner",
                },
            )
            assert response.status_code == 404, (method, path)
        Base.metadata.drop_all(application.state.engine)


def test_local_development_identity_opens_a_session_too(settings: Settings) -> None:
    """``make dev`` signs in with X-AIA-Subject; the session carries that identity."""
    from aia_core.infrastructure.scope_repository import ScopeRepository
    from aia_core.infrastructure.tables import Base

    from aia_api.main import create_app

    local = settings.model_copy(
        update={"env": Environment.LOCAL, "identity_provider": "development"}
    )
    application = create_app(local)
    with TestClient(application, follow_redirects=False) as client:
        Base.metadata.create_all(application.state.engine)
        factory = create_session_factory(application.state.engine)
        with factory() as session:
            ScopeRepository(session).create_organization(
                slug="aia", name="AIA", owner_email="owner@example.test", owner_name="Owner"
            )
            session.commit()
        opened = client.post(SESSION, headers={"X-AIA-Subject": "owner@example.test"})
        assert opened.status_code == 204
        # Quoted, because of the "@"; the client's jar sends it back as a browser would.
        assert opened.headers["set-cookie"].startswith('aia_session="owner@example.test";')
        assert client.get(GATE, headers={"X-Forwarded-Method": "GET"}).status_code == 204
        assert client.delete(SESSION).status_code == 204
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(AccessAuditRow)) >= 1
        Base.metadata.drop_all(application.state.engine)
