"""The report editor's gate (plan report-editor-hosting, chunk 3).

ONLYOFFICE Docs is served at docs.<hostname>; AIA's session cookie never reaches it. These
tests drive the three routes as the pane and Caddy do: a ticket asked for with the person's
own token, spent once at the editor's origin for the docs cookie, and the docs gate asked by
``forward_auth`` before every request there, with the original method in
``X-Forwarded-Method``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from aia_core.domain.scope import OrganizationContext, OrganizationRole, ScopeGrant
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.docs_ticket_repository import DocsTicketRepository
from aia_core.infrastructure.tables import AccessAuditRow, DocsTicketSpendRow, UserRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Environment, Settings
from aia_api.docs_pass import COOKIE_LIFETIME, DocsPasses

API = "/api/v1/session"
EDITOR = "https://docs.aia.example.test"
EDITOR_HOST = "docs.aia.example.test"
SECRET = "k" * 48
API_JS = "/web-apps/apps/api/documents/api.js"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
        onlyoffice_url=EDITOR,
        onlyoffice_jwt_secret=SECRET,
    )


@pytest.fixture
def anonymous(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as c:
        yield c


def _ticket(client: TestClient, world: Any, label: str = "researcher") -> str:
    response = client.post(
        f"{API}/docs-ticket", headers={"Authorization": f"Bearer {world.tokens[label]}"}
    )
    assert response.status_code == 200, response.text
    url = urlparse(response.json()["session_url"])
    assert f"{url.scheme}://{url.netloc}" == EDITOR and url.path == "/__aia/session"
    return parse_qs(url.query)["ticket"][0]


def _spend(client: TestClient, ticket: str, *, next: str = API_JS, host: str = EDITOR_HOST) -> Any:  # noqa: A002
    return client.get(
        f"{API}/docs", params={"ticket": ticket, "next": next}, headers={"Host": host}
    )


def _gate(client: TestClient, cookie: str | None, *, method: str = "GET") -> Any:
    headers = {"X-Forwarded-Method": method, "X-Forwarded-Uri": API_JS}
    if cookie is not None:
        headers["Cookie"] = f"aia_docs={cookie}"
    return client.get(f"{API}/docs-gate", headers=headers)


def _docs_cookie(response: Any) -> str:
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("aia_docs=")
    return cookie.split(";", 1)[0].split("=", 1)[1]


def _audit(app: FastAPI, action: str) -> int:
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        return len(
            session.scalars(select(AccessAuditRow).where(AccessAuditRow.action == action)).all()
        )


def _deactivate(app: FastAPI, user_id: str) -> None:
    factory = create_session_factory(app.state.engine)
    with factory() as session:
        user = session.get(UserRow, user_id)
        assert user is not None
        user.is_active = False
        session.commit()


# --------------------------------------------------------------------------- #
# The way in: a ticket, spent once, for the docs cookie
# --------------------------------------------------------------------------- #


def test_a_member_s_ticket_buys_the_docs_cookie_and_a_redirect_to_next(
    anonymous: TestClient, world: Any, app: FastAPI
) -> None:
    before = _audit(app, "AIA_SESSION")
    response = _spend(anonymous, _ticket(anonymous, world))
    assert response.status_code == 302
    assert response.headers["location"] == API_JS
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert "Max-Age=28800" in cookie  # a working day; the gate re-checks membership
    assert "Domain" not in cookie  # host-only: the editor's origin, never AIA's
    assert _audit(app, "AIA_SESSION") == before + 1  # opening it is in the access audit


def test_the_docs_cookie_is_never_the_id_token(anonymous: TestClient, world: Any) -> None:
    cookie = _docs_cookie(_spend(anonymous, _ticket(anonymous, world)))
    assert world.tokens["researcher"] not in cookie
    claims = DocsPasses(SECRET).read(cookie, kind="cookie", now=datetime.now(UTC))
    assert claims is not None and claims.user_id == world.users["researcher"]


def test_a_ticket_is_spent_once(anonymous: TestClient, world: Any) -> None:
    ticket = _ticket(anonymous, world)
    assert _spend(anonymous, ticket).status_code == 302
    again = _spend(anonymous, ticket)
    assert again.status_code == 401
    assert again.json()["code"] == "docs_unauthenticated"
    assert "set-cookie" not in again.headers


def test_a_ticket_at_aia_s_own_hostname_is_not_found_and_not_spent(
    anonymous: TestClient, world: Any
) -> None:
    ticket = _ticket(anonymous, world)
    assert _spend(anonymous, ticket, host="aia.example.test").status_code == 404
    assert _spend(anonymous, ticket).status_code == 302


@pytest.mark.parametrize("bad", ["", "nonsense", "a.b"])
def test_no_valid_ticket_is_refused(anonymous: TestClient, world: Any, bad: str) -> None:
    assert _spend(anonymous, bad).status_code == 401


def test_a_ticket_signed_under_another_secret_is_refused(anonymous: TestClient, world: Any) -> None:
    forged, _ = DocsPasses("z" * 48).ticket(
        user_id=world.users["researcher"],
        organization_id=world.organization_id,
        now=datetime.now(UTC),
    )
    assert _spend(anonymous, forged).status_code == 401


def test_a_cookie_is_not_a_ticket(anonymous: TestClient, world: Any) -> None:
    cookie = _docs_cookie(_spend(anonymous, _ticket(anonymous, world)))
    assert _spend(anonymous, cookie).status_code == 401


def test_an_expired_ticket_is_refused(anonymous: TestClient, world: Any) -> None:
    old, _ = DocsPasses(SECRET).ticket(
        user_id=world.users["researcher"],
        organization_id=world.organization_id,
        now=datetime.now(UTC) - timedelta(minutes=5),
    )
    assert _spend(anonymous, old).status_code == 401


def test_a_ticket_for_someone_deactivated_since_is_refused_and_audited(
    anonymous: TestClient, world: Any, app: FastAPI
) -> None:
    ticket = _ticket(anonymous, world)
    _deactivate(app, world.users["researcher"])
    before = _audit(app, "AIA_SESSION_DENIED")
    response = _spend(anonymous, ticket)
    assert response.status_code == 403
    assert response.json()["code"] == "not_a_member"
    assert _audit(app, "AIA_SESSION_DENIED") == before + 1


@pytest.mark.parametrize(
    "next_path", ["https://evil.example.test/", "//evil.example.test/x", "/\t/evil.example.test"]
)
def test_next_never_leaves_the_editor_s_origin(
    anonymous: TestClient, world: Any, next_path: str
) -> None:
    response = _spend(anonymous, _ticket(anonymous, world), next=next_path)
    assert response.status_code == 302 and response.headers["location"] == "/"


def test_a_ticket_needs_the_person_s_own_token(anonymous: TestClient) -> None:
    assert anonymous.post(f"{API}/docs-ticket").status_code == 401


def test_a_deactivated_person_gets_no_ticket(
    anonymous: TestClient, world: Any, app: FastAPI
) -> None:
    _deactivate(app, world.users["viewer"])
    response = anonymous.post(
        f"{API}/docs-ticket", headers={"Authorization": f"Bearer {world.tokens['viewer']}"}
    )
    assert response.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# The docs gate, before every request to the editor's origin
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("method", ["GET", "HEAD", "POST", "post"])
def test_a_valid_docs_cookie_passes_the_gate(
    anonymous: TestClient, world: Any, method: str
) -> None:
    cookie = _docs_cookie(_spend(anonymous, _ticket(anonymous, world)))
    assert _gate(anonymous, cookie, method=method).status_code == 204


@pytest.mark.parametrize("method", ["PUT", "DELETE", "PATCH", "OPTIONS"])
def test_a_method_the_editor_never_takes_is_refused_first(
    anonymous: TestClient, world: Any, method: str
) -> None:
    cookie = _docs_cookie(_spend(anonymous, _ticket(anonymous, world)))
    response = _gate(anonymous, cookie, method=method)
    assert response.status_code == 403
    assert response.json()["code"] == "method_not_allowed"


def test_no_cookie_is_401_and_never_a_redirect(anonymous: TestClient, world: Any) -> None:
    response = anonymous.get(
        f"{API}/docs-gate", headers={"X-Forwarded-Method": "GET", "Accept": "text/html"}
    )
    assert response.status_code == 401
    assert "location" not in response.headers


def test_aia_s_own_session_cookie_does_not_open_the_editor(
    anonymous: TestClient, world: Any
) -> None:
    response = anonymous.get(
        f"{API}/docs-gate",
        headers={"X-Forwarded-Method": "GET", "Cookie": f"aia_session={world.tokens['owner']}"},
    )
    assert response.status_code == 401


def test_a_ticket_is_not_a_docs_cookie(anonymous: TestClient, world: Any) -> None:
    assert _gate(anonymous, _ticket(anonymous, world)).status_code == 401


def test_an_expired_docs_cookie_is_refused(anonymous: TestClient, world: Any) -> None:
    old, _ = DocsPasses(SECRET).cookie(
        user_id=world.users["researcher"],
        organization_id=world.organization_id,
        now=datetime.now(UTC) - COOKIE_LIFETIME - timedelta(seconds=1),
    )
    assert _gate(anonymous, old).status_code == 401


def test_a_person_deactivated_after_opening_the_editor_is_shut_out(
    anonymous: TestClient, world: Any, app: FastAPI
) -> None:
    cookie = _docs_cookie(_spend(anonymous, _ticket(anonymous, world)))
    _deactivate(app, world.users["researcher"])
    assert _gate(anonymous, cookie).status_code == 403


def test_a_cookie_naming_another_organization_is_refused(anonymous: TestClient, world: Any) -> None:
    forged, _ = DocsPasses(SECRET).cookie(
        user_id=world.users["researcher"], organization_id="ORG-elsewhere", now=datetime.now(UTC)
    )
    assert _gate(anonymous, forged).status_code == 403


# --------------------------------------------------------------------------- #
# Off until configured
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "configured",
    [{}, {"onlyoffice_url": EDITOR}, {"onlyoffice_jwt_secret": SECRET}],
)
def test_every_docs_route_is_404_until_the_editor_is_configured(
    configured: dict[str, str], world: Any
) -> None:
    from aia_api.main import create_app

    settings = Settings(
        env=Environment.TEST,
        database_url="sqlite+pysqlite:///:memory:",
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
        **configured,
    )
    with TestClient(create_app(settings), follow_redirects=False) as client:
        assert client.post(f"{API}/docs-ticket").status_code in (401, 404)
        assert client.get(f"{API}/docs", headers={"Host": EDITOR_HOST}).status_code == 404
        assert client.get(f"{API}/docs-gate").status_code == 404


# --------------------------------------------------------------------------- #
# The spent tickets themselves
# --------------------------------------------------------------------------- #


def _context(world: Any) -> OrganizationContext:
    return OrganizationContext(
        organization_id=world.organization_id,
        actor_id=world.users["researcher"],
        organization_role=OrganizationRole.MEMBER,
        grant=ScopeGrant._issue(),
    )


def test_a_person_s_long_expired_spends_go_on_their_next_spend(app: FastAPI, world: Any) -> None:
    factory = create_session_factory(app.state.engine)
    now = datetime.now(UTC)
    with factory() as session:
        tickets = DocsTicketRepository(session, _context(world))
        assert tickets.spend("old", expires_at=now - timedelta(days=2), now=now - timedelta(days=2))
        assert tickets.spend("recent", expires_at=now - timedelta(hours=1), now=now)
        assert tickets.spend("new", expires_at=now + timedelta(minutes=1), now=now)
        session.commit()
        kept = set(session.scalars(select(DocsTicketSpendRow.ticket_id)))
    assert kept == {"recent", "new"}


def test_a_spend_needs_an_issued_scope(app: FastAPI) -> None:
    from aia_core.domain.scope import ScopeDenied

    factory = create_session_factory(app.state.engine)
    with factory() as session, pytest.raises(ScopeDenied):
        DocsTicketRepository(session, object())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# The editor's origin, as configured
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value",
    [
        "http://docs.example.test",
        "https://docs.example.test:443",
        "https://docs.example.test:8443",
        "https://docs.example.test/path",
        "https://docs.example.test#x",
        "https://docs.example.test?x=1",
        "https://user@docs.example.test",
        "https://:pw@docs.example.test",
        "docs.example.test",
    ],
)
def test_anything_but_an_https_origin_is_refused_at_start(value: str) -> None:
    # The ticket's URL is built on it, and the exchange compares a browser's Host with it.
    with pytest.raises(ValueError):
        Settings(onlyoffice_url=value)


def test_an_https_origin_is_kept_without_its_trailing_slash() -> None:
    assert Settings(onlyoffice_url="https://docs.example.test/").onlyoffice_url == (
        "https://docs.example.test"
    )


def test_a_short_editor_secret_is_refused_at_start() -> None:
    with pytest.raises(ValueError):
        Settings(onlyoffice_jwt_secret="too-short")
