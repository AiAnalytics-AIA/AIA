"""The session and gate in front of the vendored 18.6.6 interface (ADR 0012).

Caddy asks ``GET /api/v1/panel/gate`` before forwarding any request to the unit,
so these tests drive the gate exactly as ``forward_auth`` does: the original
method and URI in ``X-Forwarded-Method`` / ``X-Forwarded-Uri``, the browser's
cookies, ``Origin`` and ``Accept`` copied through.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import OrganizationRole
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aia_api.config import Environment, Settings

API = "/api/v1"
ORIGIN = "https://aia-develop.example.test"
SESSION = f"{API}/panel/session"
GATE = f"{API}/panel/gate"
HTML = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
        legacy_panel_enabled=True,
        legacy_panel_origin=ORIGIN,
    )


@pytest.fixture
def tokens(app: FastAPI, world: Any) -> dict[str, str]:
    """The world's tokens plus an organization admin's."""
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        owner = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=world.users["owner"], organization_id=world.organization_id
            )
        )
        ScopeRepository(session).add_member(
            owner, email="admin@art-chain.io", role=OrganizationRole.ADMIN
        )
        session.commit()
    app.state.identity_provider.register(
        "token-admin", subject="admin@art-chain.io", email="admin@art-chain.io"
    )
    return {**world.tokens, "admin": "token-admin"}


@pytest.fixture
def anonymous(app: FastAPI) -> TestClient:
    # follow_redirects off: the gate's 302 is the answer under test.
    return TestClient(app, follow_redirects=False)


def _gate(
    client: TestClient,
    *,
    cookie: str | None = None,
    method: str = "GET",
    uri: str = "/",
    accept: str = "application/json",
    origin: str | None = None,
) -> Any:
    headers = {"X-Forwarded-Method": method, "X-Forwarded-Uri": uri, "Accept": accept}
    if origin is not None:
        headers["Origin"] = origin
    if cookie is not None:
        headers["Cookie"] = f"aia_panel={cookie}"
    return client.get(GATE, headers=headers)


# --------------------------------------------------------------------------- #
# Opening and closing a session
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("label", ["owner", "admin"])
def test_an_administrator_gets_an_httponly_lax_session_cookie(
    anonymous: TestClient, tokens: dict[str, str], label: str
) -> None:
    response = anonymous.post(SESSION, headers={"Authorization": f"Bearer {tokens[label]}"})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"aia_panel={tokens[label]};")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    # Not Secure under test; Secure wherever is_production (staging included).
    assert "Secure" not in cookie


def test_a_plain_member_is_refused_a_session(anonymous: TestClient, tokens: dict[str, str]) -> None:
    response = anonymous.post(SESSION, headers={"Authorization": f"Bearer {tokens['lead']}"})
    assert response.status_code == 403
    assert response.json()["code"] == "legacy_panel_denied"
    assert "set-cookie" not in response.headers


def test_a_session_needs_a_verified_credential(anonymous: TestClient, world: Any) -> None:
    assert anonymous.post(SESSION).status_code == 401
    bad = anonymous.post(SESSION, headers={"Authorization": "Bearer not-a-token"})
    assert bad.status_code == 401
    assert "set-cookie" not in bad.headers


def test_closing_the_session_clears_the_cookie(anonymous: TestClient) -> None:
    response = anonymous.delete(SESSION)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert cookie.startswith('aia_panel="";') or cookie.startswith("aia_panel=;")
    assert "Max-Age=0" in cookie


# --------------------------------------------------------------------------- #
# The per-request gate
# --------------------------------------------------------------------------- #


def test_an_administrators_session_passes_the_gate(
    anonymous: TestClient, tokens: dict[str, str]
) -> None:
    assert _gate(anonymous, cookie=tokens["owner"], uri="/api/bootstrap").status_code == 204
    assert _gate(anonymous, cookie=tokens["admin"], accept=HTML).status_code == 204


def test_a_members_session_is_refused_by_the_gate(
    anonymous: TestClient, tokens: dict[str, str]
) -> None:
    response = _gate(anonymous, cookie=tokens["researcher"], accept=HTML)
    assert response.status_code == 403
    assert response.json()["code"] == "legacy_panel_denied"


def test_a_navigation_without_a_session_goes_to_login(anonymous: TestClient, world: Any) -> None:
    response = _gate(anonymous, uri="/?tab=projects", accept=HTML)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F%3Ftab%3Dprojects"


def test_an_api_call_without_a_session_is_refused_not_redirected(
    anonymous: TestClient, world: Any
) -> None:
    # A fetch() following a redirect to an HTML page would parse it as data.
    response = _gate(anonymous, uri="/api/bootstrap")
    assert response.status_code == 401


def test_an_expired_session_goes_back_through_login(
    app: FastAPI, anonymous: TestClient, tokens: dict[str, str]
) -> None:
    app.state.identity_provider.expire(tokens["owner"])
    assert _gate(anonymous, cookie=tokens["owner"], accept=HTML).status_code == 302
    assert _gate(anonymous, cookie=tokens["owner"]).status_code == 401


def test_a_forged_cookie_is_refused(anonymous: TestClient, world: Any) -> None:
    assert _gate(anonymous, cookie="forged").status_code == 401


@pytest.mark.parametrize("uri", ["//evil.example/", "https://evil.example/", "/\\evil", ""])
def test_the_login_redirect_never_leaves_the_origin(
    anonymous: TestClient, world: Any, uri: str
) -> None:
    response = _gate(anonymous, uri=uri, accept=HTML)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=%2F"


@pytest.mark.parametrize("origin", [None, "https://evil.example", "null"])
def test_a_write_from_another_origin_is_refused_before_the_session_is_read(
    anonymous: TestClient, tokens: dict[str, str], origin: str | None
) -> None:
    response = _gate(
        anonymous, cookie=tokens["owner"], method="POST", uri="/api/projects", origin=origin
    )
    assert response.status_code == 403
    assert response.json()["code"] == "cross_origin"


def test_a_write_from_the_product_origin_passes(
    anonymous: TestClient, tokens: dict[str, str]
) -> None:
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = _gate(
            anonymous, cookie=tokens["owner"], method=method, uri="/api/x", origin=ORIGIN
        )
        assert response.status_code == 204, method


def test_the_gate_writes_no_audit_row_per_request(
    app: FastAPI, anonymous: TestClient, tokens: dict[str, str]
) -> None:
    from aia_core.infrastructure.tables import AccessAuditRow
    from sqlalchemy import func, select

    factory = create_session_factory(app.state.engine)
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(AccessAuditRow))
    for _ in range(3):
        _gate(anonymous, cookie=tokens["owner"])
    with factory() as session:
        after = session.scalar(select(func.count()).select_from(AccessAuditRow))
    assert after == before


def test_opening_a_session_is_audited(
    app: FastAPI, anonymous: TestClient, tokens: dict[str, str]
) -> None:
    from aia_core.infrastructure.tables import AccessAuditRow
    from sqlalchemy import select

    anonymous.post(SESSION, headers={"Authorization": f"Bearer {tokens['admin']}"})
    anonymous.post(SESSION, headers={"Authorization": f"Bearer {tokens['viewer']}"})
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        actions = sorted(
            session.scalars(
                select(AccessAuditRow.action).where(AccessAuditRow.action.like("LEGACY_PANEL_%"))
            )
        )
    assert actions == ["LEGACY_PANEL_DENIED", "LEGACY_PANEL_SESSION"]


# --------------------------------------------------------------------------- #
# The kill switch and the production guard
# --------------------------------------------------------------------------- #


def test_everything_is_404_when_the_panel_is_off(settings: Settings) -> None:
    from aia_api.main import create_app

    off = settings.model_copy(update={"legacy_panel_enabled": False})
    with TestClient(create_app(off), follow_redirects=False) as client:
        assert client.post(SESSION).status_code == 404
        assert client.delete(SESSION).status_code == 404
        assert _gate(client, accept=HTML).status_code == 404


def test_production_refuses_the_panel() -> None:
    settings = Settings(
        env=Environment.PRODUCTION,
        database_url="postgresql+psycopg://u:p@db/aia",
        legacy_panel_enabled=True,
        legacy_panel_origin=ORIGIN,
    )
    with pytest.raises(RuntimeError, match="AIA_LEGACY_PANEL_ENABLED is refused in production"):
        settings.validate_for_production()


def test_a_deployed_panel_must_name_its_origin() -> None:
    settings = Settings(
        env=Environment.STAGING,
        database_url="postgresql+psycopg://u:p@db/aia",
        legacy_panel_enabled=True,
    )
    with pytest.raises(RuntimeError, match="AIA_LEGACY_PANEL_ORIGIN is required"):
        settings.validate_for_production()


def test_local_development_identity_opens_a_session_too(settings: Settings) -> None:
    """``make dev`` signs in with X-AIA-Subject; the panel session carries that identity."""
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
        # Quoted, because of the "@"; a JWT needs no quoting. The client's jar
        # sends it back as a browser would.
        assert opened.headers["set-cookie"].startswith('aia_panel="owner@example.test";')
        assert client.get(GATE, headers={"X-Forwarded-Method": "GET"}).status_code == 204
