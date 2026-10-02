"""Executor test fixtures: a real database, a provisioned study, a worker.

The same shape as ``apps/worker/tests/conftest.py`` -- PostgreSQL when
``DATABASE_URL`` names one, otherwise a file-backed SQLite database per test --
and provisioned through the authorization path, never by inserting rows.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import OrganizationContext, ScopeRole, StudyContext, StudyStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import Base
from aia_executors.registry import registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

BUILD = BuildIdentity(sha="a15be650937aacaa", built_at="2026-09-23T01:00:00Z")


def postgres_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith("postgresql") else None


def _truncate(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    url = postgres_url()
    if url is None and os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
        # CI sets the flag so a missing database is a failure, not a quiet
        # fall-back to SQLite that reports the executor suite green.
        pytest.fail(
            "executor tests require PostgreSQL here; DATABASE_URL is not a postgresql:// URL"
        )
    return url or f"sqlite+pysqlite:///{tmp_path / 'executors.db'}"


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    eng = create_app_engine(database_url, pool_size=10, max_overflow=10)
    Base.metadata.create_all(eng)
    factory = create_session_factory(eng)
    _truncate(factory)
    try:
        yield eng
    finally:
        _truncate(factory)
        eng.dispose()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture
def build() -> BuildIdentity:
    """The build the test worker claims to be. Tests import nothing from here."""
    return BUILD


@dataclass(frozen=True)
class World:
    """An organization, a client, an ACTIVE study, a LEAD and a project."""

    organization_id: str
    client_id: str
    study_id: str
    lead_id: str
    project_id: str
    sessions: sessionmaker[Session]
    owner_id: str = ""

    def admin_context(self, session: Session) -> OrganizationContext:
        """The organization's owner, for tests that edit what the organization runs."""
        return ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=self.owner_id, organization_id=self.organization_id)
        )

    def lead_scope(self, session: Session) -> StudyContext:
        return ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=self.lead_id, organization_id=self.organization_id),
            study_id=self.study_id,
        )


@pytest.fixture
def world(sessions: sessionmaker[Session]) -> World:
    with sessions() as session:
        scope_repo = ScopeRepository(session)
        resolver = ScopeResolver(session)
        org, owner = scope_repo.create_organization(
            slug="aia", name="AIA", owner_email="owner@art-chain.io"
        )
        admin = resolver.organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )
        client = scope_repo.create_client(admin, slug="acme", name="Acme")
        study = scope_repo.create_study(
            admin, client_id=client.client_id, slug="s", name="S", budget_usd=25.0
        )
        lead = scope_repo.add_member(admin, email="lead@art-chain.io")
        resolver.grant_client_access(
            admin, client_id=client.client_id, user_id=lead.user_id, role=ScopeRole.RESEARCHER
        )
        session.flush()
        scope = resolver.study_context(
            AuthenticatedPrincipal(user_id=lead.user_id, organization_id=org.organization_id),
            study_id=study.study_id,
        )
        scope_repo.set_study_status(scope, StudyStatus.ACTIVE)
        project, _ = ProjectRepository(session, scope).create(
            title="Snapshot host", content={"goal": "g", "audience": {"age_min": 18}}
        )
        session.commit()
        return World(
            organization_id=org.organization_id,
            client_id=client.client_id,
            study_id=study.study_id,
            lead_id=lead.user_id,
            project_id=project.project_id,
            sessions=sessions,
            owner_id=owner.user_id,
        )


@pytest.fixture
def make_worker(
    sessions: sessionmaker[Session], database_url: str, store: InMemoryArtifactStore
) -> Callable[..., Worker]:
    """A worker running the real executor registry over the in-memory store."""

    def build(worker_id: str = "worker-a", **overrides: Any) -> Worker:
        settings = WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id=worker_id,
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
            **overrides,
        )
        return Worker(
            session_factory=sessions,
            executors=registry_for(store=store, build=BUILD),
            settings=settings,
        )

    return build
