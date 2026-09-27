"""Why a worker refuses an engine that has one connection for every thread.

``create_app_engine`` gives in-memory SQLite a single shared connection
(``StaticPool``), so that separate sessions see one database. A worker's heartbeat
thread opens and closes its own session every ``heartbeat_seconds`` while the step
it guards holds an open transaction. On a shared connection that close returns
*the step's* connection to the pool, which rolls it back: the step's flushed
artifact row is discarded, and its dependency edge -- inserted next, by the
autoflush of the next scope query -- fails its foreign key.

That was ``test_research_artifacts_are_read_only_through_the_run_that_produced_them``
failing about one run in fourteen with an ``IntegrityError`` on
``project_artifact_dependencies``. The artifact repository was not at fault: its
transaction is correct and was rolled back from underneath it. These tests replay
the heartbeat's close at the one point it has to land, so the race is a
deterministic result rather than a timing accident, and pin the guard that makes
the worker refuse such an engine at construction.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.db import shares_one_connection
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import ProjectArtifactRow
from aia_worker.settings import WorkerSettings
from aia_worker.testing import build_registry
from aia_worker.worker import Worker
from sqlalchemy import Engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

MEMORY = "sqlite+pysqlite:///:memory:"


@pytest.fixture(params=["memory", "own-connections"])
def database_url(request: pytest.FixtureRequest, tmp_path: Path) -> str:
    """Overrides conftest: the shared-connection engine, and one that is not."""
    if request.param == "memory":
        return MEMORY
    postgres = os.environ.get("DATABASE_URL", "")
    if postgres.startswith("postgresql"):
        return postgres
    return f"sqlite+pysqlite:///{tmp_path / 'worker.db'}"


def _close_a_heartbeat_session_after_the_artifact_row_flushes(
    step_session: Session, sessions: sessionmaker[Session]
) -> None:
    """Do what the heartbeat thread does, once, right after the artifact INSERT.

    The heartbeat opens a session, runs its lease extension and closes it. The
    statement does not matter; the close does.
    """
    fired = False

    def heartbeat(session: Session, _context: Any) -> None:
        nonlocal fired
        if fired or not any(isinstance(obj, ProjectArtifactRow) for obj in session.new):
            return
        fired = True
        with sessions() as other:
            other.execute(select(1))

    event.listen(step_session, "after_flush", heartbeat)


def _put_with_two_dependencies(study: Any) -> None:
    """The Sociomap step's write: one artifact depending on the spec and the dataset."""
    store = InMemoryArtifactStore()
    with study.sessions() as session:
        repo = ArtifactRepository(session, study.lead_scope(session), store)
        parents = [
            repo.put_json(
                project_id=study.project_id,
                revision=1,
                stage_type="REPORT",
                artifact_type=kind,
                payload={"kind": kind},
            )[0].artifact_id
            for kind in ("SPECIFICATION", "FIELDWORK_DATASET")
        ]
        session.commit()

        _close_a_heartbeat_session_after_the_artifact_row_flushes(session, study.sessions)
        child, _ = repo.put_json(
            project_id=study.project_id,
            revision=1,
            stage_type="REPORT",
            artifact_type="SOCIOMAP",
            payload={"kind": "SOCIOMAP"},
            depends_on=parents,
        )
        session.commit()
    with study.sessions() as session:
        traced = ArtifactRepository(session, study.lead_scope(session), store).dependencies(
            child.artifact_id
        )
    assert sorted(a.artifact_id for a in traced) == sorted(parents)


def test_a_heartbeat_session_closing_mid_step_breaks_only_a_shared_connection(
    study: Any, database_url: str
) -> None:
    """The reproduction: the exact failure on ``:memory:``, none with a connection each."""
    if database_url != MEMORY:
        _put_with_two_dependencies(study)
        return
    with pytest.raises(IntegrityError) as raised:
        _put_with_two_dependencies(study)
    message = str(raised.value)
    assert "FOREIGN KEY constraint failed" in message
    assert "autoflush" in message
    assert "project_artifact_dependencies" in message


def test_shares_one_connection_names_only_the_in_memory_engine(
    engine: Engine, database_url: str
) -> None:
    assert shares_one_connection(engine) is (database_url == MEMORY)


def test_a_worker_refuses_an_engine_whose_threads_would_share_one_connection(
    sessions: sessionmaker[Session], database_url: str
) -> None:
    """Fail at construction, every time -- not one step in fourteen, mid-run."""
    settings = WorkerSettings(
        database_url=database_url,
        executors="aia_worker.testing:build_registry",
        worker_id="worker-a",
    )
    if database_url != MEMORY:
        Worker(session_factory=sessions, executors=build_registry(), settings=settings)
        return
    with pytest.raises(ValueError, match="one connection"):
        Worker(session_factory=sessions, executors=build_registry(), settings=settings)


def test_a_worker_refuses_a_session_factory_bound_to_no_engine() -> None:
    """It could not tell whether its heartbeat would share the step's connection."""
    settings = WorkerSettings(
        database_url=MEMORY,
        executors="aia_worker.testing:build_registry",
        worker_id="worker-a",
    )
    with pytest.raises(ValueError, match="bound to an engine"):
        Worker(session_factory=sessionmaker(), executors=build_registry(), settings=settings)
