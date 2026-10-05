"""API test fixtures.

Each test gets an app with its own database and a provisioned organization,
clients, studies and users at every role, so tests exercise the same
authentication and authorisation path production does.

Authentication uses ``TestIdentityProvider`` with opaque tokens: the Cognito JWT
contract is verified separately in ``test_identity.py`` against real signed
tokens, so tests that merely need *an* authenticated caller do not each pay for
crypto.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import Base, ProjectArtifactRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Environment, Settings
from aia_api.main import create_app

API = "/api/v1"


@pytest.fixture
def settings() -> Settings:
    """Test settings: an isolated database and the deterministic identity provider."""
    return Settings(
        env=Environment.TEST,
        database_url=os.environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        identity_provider="test",
        log_level="WARNING",
        log_format="console",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    """An application with a freshly created schema."""
    application = create_app(settings)
    with TestClient(application):
        Base.metadata.create_all(application.state.engine)
        try:
            yield application
        finally:
            Base.metadata.drop_all(application.state.engine)


@dataclass(frozen=True)
class World:
    """A provisioned organization, two clients, three studies and users at every role.

    Two clients exist deliberately: the isolation tests that matter are the ones
    crossing a client boundary, and a single-client fixture cannot express them.
    """

    organization_id: str
    clients: dict[str, Any]
    studies: dict[str, Any]
    users: dict[str, str]
    tokens: dict[str, str]

    def study_id(self, name: str = "primary") -> str:
        return self.studies[name].study_id

    def client_id(self, name: str = "primary") -> str:
        return self.clients[name].client_id


@pytest.fixture
def world(app: FastAPI) -> World:
    """Provision the scope graph and register a token per user."""
    factory = create_session_factory(app.state.engine)
    provider = app.state.identity_provider

    with factory() as session:
        scope_repo = ScopeRepository(session)
        resolver = ScopeResolver(session)

        org, owner = scope_repo.create_organization(
            slug="aia",
            name="AI Analytics",
            owner_email="owner@art-chain.io",
            owner_name="Owner",
        )
        admin = resolver.organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )

        primary = scope_repo.create_client(admin, slug="acme", name="Acme Corp")
        other = scope_repo.create_client(admin, slug="globex", name="Globex Inc")

        studies = {
            "primary": scope_repo.create_study(
                admin,
                client_id=primary.client_id,
                slug="brand-2026",
                name="Acme brand",
                budget_usd=500.0,
            ),
            "sibling": scope_repo.create_study(
                admin,
                client_id=primary.client_id,
                slug="pricing-2026",
                name="Acme pricing",
                budget_usd=200.0,
            ),
            "other_client": scope_repo.create_study(
                admin,
                client_id=other.client_id,
                slug="brand-2026",
                name="Globex brand",
                budget_usd=300.0,
            ),
        }

        # ADR 0019: one role. The labels are kept so the tests that name one still
        # read; every one holds the same Researcher grant. They collapse with the grants.
        users = {"owner": owner.user_id}
        for label in ("lead", "researcher", "reviewer", "viewer"):
            member = scope_repo.add_member(admin, email=f"{label}@art-chain.io")
            users[label] = member.user_id

        other_lead = scope_repo.add_member(admin, email="other-lead@art-chain.io")
        users["other_lead"] = other_lead.user_id

        # A member of the organization holding no client grant at all.
        outsider = scope_repo.add_member(admin, email="outsider@art-chain.io")
        users["outsider"] = outsider.user_id

        session.commit()

        # Bind a token per user. The subject matches the email, which is what the
        # provisioned user record was keyed on.
        tokens: dict[str, str] = {}
        for label in users:
            email = (
                "owner@art-chain.io"
                if label == "owner"
                else f"{label.replace('_', '-')}@art-chain.io"
            )
            token = f"token-{label}"
            provider.register(token, subject=email, email=email, display_name=label)
            tokens[label] = token

        return World(
            organization_id=org.organization_id,
            clients={"primary": primary, "other": other},
            studies=studies,
            users=users,
            tokens=tokens,
        )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """An unauthenticated client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def as_user(app: FastAPI, world: World):
    """Return a factory for clients authenticated as a provisioned user."""

    def build(label: str) -> TestClient:
        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {world.tokens[label]}"})
        return c

    return build


@pytest.fixture
def lead(as_user: Any) -> TestClient:
    """A client authenticated as a LEAD on the primary client."""
    return as_user("lead")


@pytest.fixture
def researcher(as_user: Any) -> TestClient:
    """A client authenticated as a RESEARCHER on the primary client."""
    return as_user("researcher")


@pytest.fixture
def reviewer(as_user: Any) -> TestClient:
    """The person once labelled REVIEWER; a Researcher like everyone else (ADR 0019)."""
    return as_user("reviewer")


@pytest.fixture
def viewer(as_user: Any) -> TestClient:
    """The person once labelled VIEWER; a Researcher like everyone else (ADR 0019)."""
    return as_user("viewer")


@pytest.fixture
def other_client_lead(as_user: Any) -> TestClient:
    """A LEAD on a *different* client, for cross-client isolation tests."""
    return as_user("other_lead")


@pytest.fixture
def outsider(as_user: Any) -> TestClient:
    """An organization member with no client grant."""
    return as_user("outsider")


@pytest.fixture
def owner(as_user: Any) -> TestClient:
    """The organization OWNER: may administer, but holds no client grant."""
    return as_user("owner")


@pytest.fixture
def damage_artifact(app: FastAPI) -> Callable[[str, str], None]:
    """Damage an artifact's stored object behind the database's back.

    ``"tampered"`` replaces the bytes, so they no longer match the recorded
    SHA-256; ``"missing"`` deletes the object. The key comes from the artifact's
    row, so this works on whichever store the app was built with.
    """

    def damage(artifact_id: str, how: str) -> None:
        with create_session_factory(app.state.engine)() as session:
            key = session.scalars(
                select(ProjectArtifactRow.storage_key).where(
                    ProjectArtifactRow.artifact_id == artifact_id
                )
            ).one()
        if how == "tampered":
            app.state.artifact_store.put(key, b'{"tampered": true}')
        elif how == "missing":
            app.state.artifact_store.delete(key)
        else:  # pragma: no cover - a typo in a test
            raise ValueError(f"unknown damage {how!r}")

    return damage


@pytest.fixture
def artifact_status(app: FastAPI) -> Callable[[str], str]:
    """The status the database holds for an artifact, read in a session of its own.

    Not through the API: a response can say CORRUPT while the row it came from is
    rolled back, which is exactly what the durable-mark tests are about.
    """

    def read(artifact_id: str) -> str:
        with create_session_factory(app.state.engine)() as session:
            status: str = session.scalars(
                select(ProjectArtifactRow.status).where(
                    ProjectArtifactRow.artifact_id == artifact_id
                )
            ).one()
        return status

    return read


@pytest.fixture
def api_prefix() -> str:
    """The versioned API prefix."""
    return API


@pytest.fixture
def projects_url(world: World):
    """Return a function building the projects URL for a named study.

    Exposed as a fixture rather than an importable helper because the two test
    packages in this repository are both called ``tests``, so relative imports
    between them collide under a single pytest invocation.
    """

    def build(study: str = "primary") -> str:
        return f"{API}/studies/{world.study_id(study)}/projects"

    return build
