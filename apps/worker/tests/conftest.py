"""Worker test fixtures: a real database, a provisioned study, and a worker builder.

The database is PostgreSQL when ``DATABASE_URL`` points at one -- which is how CI
runs this suite, and the only engine that can say anything about contention --
and otherwise a **file-backed** SQLite database per test. Not in-memory: the
worker runs its heartbeat on a second thread with its own connection, and the
in-memory engine's single shared connection cannot serve two threads.

Scope is provisioned through the same authorisation path production uses; there
is no back door.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import ScopeRole, StudyContext
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import Base, StudyRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.settings import WorkerSettings
from aia_worker.testing import KIND, build_registry
from aia_worker.worker import Worker
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


def postgres_url() -> str | None:
    """The PostgreSQL URL under test, or None."""
    url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith("postgresql") else None


def _truncate(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return postgres_url() or f"sqlite+pysqlite:///{tmp_path / 'worker.db'}"


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    """An engine with the schema in place and every table empty, before and after.

    On PostgreSQL the schema is created but never dropped, and tables are emptied
    on the way in as well as out -- a test killed mid-run must not leave rows that
    fail the next one (the same rule as the core concurrency suite).
    """
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


@dataclass(frozen=True)
class Study:
    """A provisioned study, a LEAD on it, and a project to hang runs off."""

    organization_id: str
    client_id: str
    study_id: str
    lead_id: str
    reviewer_id: str
    project_id: str
    sessions: sessionmaker[Session]

    def scope_for(self, session: Session, user_id: str) -> StudyContext:
        return ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=user_id, organization_id=self.organization_id),
            study_id=self.study_id,
        )

    def lead_scope(self, session: Session) -> StudyContext:
        return self.scope_for(session, self.lead_id)

    def create_run(self, *payloads: dict[str, Any], key: str = "run") -> str:
        """A run of independent ``scripted`` steps, one per payload. Committed."""
        with self.sessions() as session:
            run_id = WorkflowRepository(session, self.lead_scope(session)).create_run(
                project_id=self.project_id,
                project_revision=1,
                workflow_type="worker-test",
                steps=[StepDefinition(node_key=f"s{i}", kind=KIND) for i in range(len(payloads))],
                idempotency_key=key,
                step_inputs={f"s{i}": dict(p) for i, p in enumerate(payloads)},
            )
            session.commit()
        return run_id

    def run(self, run_id: str) -> dict[str, Any]:
        with self.sessions() as session:
            result: dict[str, Any] = WorkflowRepository(session, self.lead_scope(session)).get_run(
                run_id
            )
            return result

    def budget(self) -> dict[str, float]:
        with self.sessions() as session:
            position: dict[str, float] = WorkflowRepository(
                session, self.lead_scope(session)
            ).budget_position()
            return position

    def cancel(self, run_id: str) -> None:
        with self.sessions() as session:
            WorkflowRepository(session, self.lead_scope(session)).request_cancel(run_id)
            session.commit()


@pytest.fixture
def study(sessions: sessionmaker[Session]) -> Study:
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
        created = scope_repo.create_study(
            admin, client_id=client.client_id, slug="s", name="S", budget_usd=100.0
        )
        lead = scope_repo.add_member(admin, email="lead@art-chain.io")
        resolver.grant_client_access(
            admin, client_id=client.client_id, user_id=lead.user_id, role=ScopeRole.RESEARCHER
        )
        reviewer = scope_repo.add_member(admin, email="reviewer@art-chain.io")
        resolver.grant_client_access(
            admin, client_id=client.client_id, user_id=reviewer.user_id, role=ScopeRole.RESEARCHER
        )
        session.flush()
        scope = resolver.study_context(
            AuthenticatedPrincipal(user_id=lead.user_id, organization_id=org.organization_id),
            study_id=created.study_id,
        )
        project, _ = ProjectRepository(session, scope).create(title="Worker host")
        row = session.get(StudyRow, created.study_id)
        assert row is not None
        row.budget_usd, row.spent_usd = 100.0, 0.0
        session.commit()
        return Study(
            organization_id=org.organization_id,
            client_id=client.client_id,
            study_id=created.study_id,
            lead_id=lead.user_id,
            reviewer_id=reviewer.user_id,
            project_id=project.project_id,
            sessions=sessions,
        )


@pytest.fixture
def make_worker(sessions: sessionmaker[Session], database_url: str) -> Callable[..., Worker]:
    """Build a worker over the test database with short, test-sized timings."""

    def build(worker_id: str = "worker-a", **overrides: Any) -> Worker:
        options: dict[str, Any] = {
            "lease_seconds": 30,
            "heartbeat_seconds": 0.1,
            "poll_seconds": 0.05,
            "maintenance_seconds": 0.2,
            "capacity_backoff_seconds": 0,
            **overrides,
        }
        settings = WorkerSettings(
            database_url=database_url,
            executors="aia_worker.testing:build_registry",
            worker_id=worker_id,
            **options,
        )
        return Worker(session_factory=sessions, executors=build_registry(), settings=settings)

    return build
