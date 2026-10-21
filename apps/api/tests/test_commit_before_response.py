"""A request's transaction is committed before its response leaves, on a real server.

``get_session`` commits after the handler returns. Under FastAPI's default scope for a
``yield`` dependency (``"request"``, since 0.118.0) that exit runs after the response has been
sent, so a client could hold a 201 for a row no other connection could see yet, and a commit
that failed was rolled back after the client had been told it succeeded. The dependency now
runs in ``scope="function"`` (FastAPI 0.121.0): it exits when the endpoint returns, before the
response is sent.

``TestClient`` cannot show either: it returns only once the whole ASGI cycle, the dependency's
exit included, has finished. These tests run the application under uvicorn on a socket and
talk to it over separate HTTP connections, as a browser and the acceptance harness do. The
commit is slowed on purpose, so the order the tests check does not depend on the machine.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import Base, UserRow
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_api.config import Environment, Settings
from aia_api.dependencies import get_session
from aia_api.main import create_app

API = "/api/v1"
NEW_EMAIL = "late-commit@art-chain.io"
# Long enough that a response sent before the commit is seen first on any machine.
COMMIT_DELAY_S = 0.4


@dataclass
class Served:
    app: FastAPI
    base_url: str
    owner_token: str
    member_token: str


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Served]:
    """The application under uvicorn on a free port, with a database every connection shares."""
    url = os.environ.get("DATABASE_URL") or f"sqlite+pysqlite:///{tmp_path / 'aia.sqlite'}"
    settings = Settings(
        env=Environment.TEST,
        database_url=url,
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
    )
    app = create_app(settings)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.01)

    Base.metadata.create_all(app.state.engine)
    try:
        with create_session_factory(app.state.engine)() as session:
            org, owner = ScopeRepository(session).create_organization(
                slug="aia", name="AI Analytics", owner_email="owner@art-chain.io", owner_name="O"
            )
            ScopeResolver(session).organization_context(
                AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
            )
            session.commit()
        provider = app.state.identity_provider
        provider.register("token-owner", subject="owner@art-chain.io", email="owner@art-chain.io")
        provider.register("token-new", subject=NEW_EMAIL, email=NEW_EMAIL)
        yield Served(app, f"http://127.0.0.1:{port}", "token-owner", "token-new")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        cleanup = create_app_engine(url)
        Base.metadata.drop_all(cleanup)
        cleanup.dispose()


def _watch_new_member(factory: Any) -> None:
    """Mark a session that writes the new member's row (the repository flushes it early)."""

    def before_flush(session: Session, *_: Any) -> None:
        if any(isinstance(o, UserRow) and o.email == NEW_EMAIL for o in session.new):
            session.info["adds_new_member"] = True

    event.listen(factory, "before_flush", before_flush)


def _adds_new_member(session: Session) -> bool:
    return bool(session.info.get("adds_new_member"))


def _client(served: Served, token: str) -> httpx.Client:
    # A client of its own is a connection of its own: what one request committed is what
    # the next one, from anywhere, reads.
    return httpx.Client(
        base_url=served.base_url, headers={"Authorization": f"Bearer {token}"}, timeout=10
    )


def test_a_write_is_committed_before_its_response_is_sent(served: Served) -> None:
    committed_at: list[float] = []

    def slow_commit(session: Session) -> None:
        if _adds_new_member(session):
            session.info["late_commit"] = True
            time.sleep(COMMIT_DELAY_S)

    def after_commit(session: Session) -> None:
        if session.info.pop("late_commit", False):
            session.info.pop("adds_new_member", None)
            committed_at.append(time.monotonic())

    factory: Any = served.app.state.session_factory
    _watch_new_member(factory)
    event.listen(factory, "before_commit", slow_commit)
    event.listen(factory, "after_commit", after_commit)

    with _client(served, served.owner_token) as owner:
        sent = time.monotonic()
        added = owner.post(f"{API}/members", json={"email": NEW_EMAIL})
        answered = time.monotonic()
    assert added.status_code == 201, added.text

    # The commit finished before the client had its answer, not after it.
    assert committed_at, "the member's transaction was never committed"
    assert committed_at[0] <= answered, (
        f"the 201 arrived {answered - sent:.3f}s after the request and the commit "
        f"{committed_at[0] - sent:.3f}s after it"
    )
    assert answered - sent >= COMMIT_DELAY_S

    # Read at once, on other connections: the member is there, and their first sign-in finds
    # the row the 201 promised instead of inserting a second one (UniqueViolation, 500).
    with _client(served, served.owner_token) as reader:
        listed = reader.get(f"{API}/members")
    assert NEW_EMAIL in [m["email"] for m in listed.json()]
    with _client(served, served.member_token) as member:
        signed_in = member.post(f"{API}/session")
    assert signed_in.status_code != 500, signed_in.text


def test_a_commit_that_fails_is_the_response(served: Served) -> None:
    """A transaction refused at commit is the error the client gets, in the one envelope."""

    def refuse(session: Session) -> None:
        if _adds_new_member(session):
            raise IntegrityError("INSERT INTO users", {}, Exception("uq_users_email"))

    _watch_new_member(served.app.state.session_factory)
    event.listen(served.app.state.session_factory, "before_commit", refuse)

    with _client(served, served.owner_token) as owner:
        refused = owner.post(f"{API}/members", json={"email": NEW_EMAIL})
    assert refused.status_code == 500, refused.text
    body = refused.json()
    assert body["code"] == "internal_error"
    assert set(body) == {"code", "message", "details", "request_id"}
    assert "uq_users_email" not in refused.text

    with _client(served, served.owner_token) as reader:
        listed = reader.get(f"{API}/members")
    assert NEW_EMAIL not in [m["email"] for m in listed.json()]


def _session_scopes(dependant: Any) -> Iterator[str | None]:
    for sub in dependant.dependencies:
        if sub.call is get_session:
            yield sub.scope
        yield from _session_scopes(sub)


def test_every_route_takes_its_session_in_function_scope() -> None:
    """One ``Depends(get_session)`` without the scope would commit after the response again.

    It would also be a second session in the same request, since the dependency cache is keyed
    by scope as well as by the callable.
    """
    app = create_app(
        Settings(
            env=Environment.TEST,
            database_url="sqlite+pysqlite:///:memory:",
            identity_provider="test",
            log_level="WARNING",
            log_format="console",
        )
    )
    found: dict[str, set[str | None]] = {}
    for context in iter_route_contexts(app.routes):
        route = context.route
        if isinstance(route, APIRoute):
            scopes = set(_session_scopes(route.dependant))
            if scopes:
                found[f"{sorted(route.methods)} {context.path}"] = scopes
    assert len(found) > 50, "the walk found too few routes to be the application's"
    wrong = {path: scopes for path, scopes in found.items() if scopes != {"function"}}
    assert wrong == {}
