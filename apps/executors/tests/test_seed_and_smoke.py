"""The develop seed is idempotent and reversible; the smoke module tells the truth."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aia_core.application.develop_seed import (
    SEED_ORGANIZATION_SLUG,
    SEED_PROJECT_TITLE,
    reset_develop_seed,
    seed_develop,
    seeded_study_scope,
)
from aia_core.application.workflows import start_workflow
from aia_core.domain.scope import ScopeRole, StudyStatus
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import OrganizationRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors import smoke
from aia_worker.worker import Worker
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

OWNER = "operator@example.com"


def test_seed_provisions_a_complete_world_once(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        first = seed_develop(session, owner_email=OWNER)
        session.commit()
    assert first.created == {
        "organization": True,
        "client": True,
        "study": True,
        "project": True,
        "run": True,
    }

    with sessions() as session:
        second = seed_develop(session, owner_email=OWNER)
        session.commit()
    assert (second.organization_id, second.client_id, second.study_id, second.project_id) == (
        first.organization_id,
        first.client_id,
        first.study_id,
        first.project_id,
    )
    assert second.run_id == first.run_id
    assert not any(second.created.values())

    with sessions() as session:
        scope = seeded_study_scope(session, owner_email=OWNER)
        assert scope.role is ScopeRole.LEAD
        assert scope.study_status is StudyStatus.ACTIVE
        projects = ProjectRepository(session, scope).list_projects()
        assert [p.title for p in projects.items] == [SEED_PROJECT_TITLE]
        run = WorkflowRepository(session, scope).get_run(first.run_id)
        # A run whose only step is RUNNABLE derives as RUNNING: nothing waits on a person.
        assert run["status"] is WorkflowRunStatus.RUNNING
        assert not run["status"].is_terminal
        assert run["workflow_type"] == DEVELOP_SNAPSHOT
        assert ScopeRepository(session).study_spend(scope)["budget_usd"] == 25.0


def test_seed_refuses_a_blank_operator(sessions: sessionmaker[Session]) -> None:
    with sessions() as session, pytest.raises(ValueError, match="AIA_SEED_OWNER_EMAIL"):
        seed_develop(session, owner_email="")


def test_reset_removes_only_the_seeded_organization(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        ScopeRepository(session).create_organization(
            slug="other", name="Other", owner_email="other@example.com"
        )
        seed_develop(session, owner_email=OWNER)
        session.commit()

    with sessions() as session:
        assert reset_develop_seed(session) is True
        session.commit()
    with sessions() as session:
        slugs = session.scalars(select(OrganizationRow.slug)).all()
        assert slugs == ["other"]
        assert session.scalar(select(func.count()).select_from(OrganizationRow)) == 1
        assert reset_develop_seed(session) is False
        with pytest.raises(LookupError):
            seeded_study_scope(session, owner_email=OWNER)


def test_storage_round_trip_reports_ok_and_leaves_nothing(store: InMemoryArtifactStore) -> None:
    lines: list[str] = []
    report = smoke.Report(lines.append)
    smoke.storage_round_trip(store, report)
    assert report.failed is False
    assert lines == ["ok    storage: put, hash-verified get and delete round-trip"]
    assert store.keys == []


class _BrokenStore(InMemoryArtifactStore):
    def get(self, key: str, *, expected_sha256: str | None = None) -> bytes:
        return b"not what was written"


def test_storage_round_trip_reports_a_failure_honestly() -> None:
    lines: list[str] = []
    report = smoke.Report(lines.append)
    smoke.storage_round_trip(_BrokenStore(), report)
    assert report.failed is True
    assert lines[0].startswith("FAIL  storage")


def test_slice_check_passes_when_a_worker_executes_the_run(
    sessions: sessionmaker[Session],
    store: InMemoryArtifactStore,
    make_worker: Callable[..., Worker],
) -> None:
    """The smoke module's slice check, with a worker driven in-process between polls."""
    worker = make_worker()
    lines: list[str] = []
    report = smoke.Report(lines.append)

    def poll_then_work(_: float) -> None:
        worker.run_once()

    original_wait = smoke.wait_for_snapshot

    def wait(sess: sessionmaker[Session], **kwargs: Any) -> dict[str, Any]:
        return original_wait(sess, **{**kwargs, "sleep": poll_then_work, "poll_s": 0.0})

    smoke.wait_for_snapshot = wait  # type: ignore[assignment]
    try:
        smoke.slice_check(
            sessions,
            store=store,
            owner_email=OWNER,
            expect_build="a15be650937aacaa",
            timeout_s=5.0,
            report=report,
        )
    finally:
        smoke.wait_for_snapshot = original_wait  # type: ignore[assignment]

    assert report.failed is False, lines
    assert any(line.startswith("ok    slice: the running worker claimed") for line in lines)
    assert any("artifact provenance names build a15be650937aacaa" in line for line in lines)
    # The seeded run and the smoke's own run both exist; only the smoke's executed here.
    with sessions() as session:
        scope = seeded_study_scope(session, owner_email=OWNER)
        runs = WorkflowRepository(session, scope).list_runs(project_id=scope_project(session))
    assert len(runs) == 2


def scope_project(session: Session) -> str:
    scope = seeded_study_scope(session, owner_email=OWNER)
    return ProjectRepository(session, scope).list_projects().items[0].project_id


def test_slice_check_fails_when_no_worker_runs(
    sessions: sessionmaker[Session], store: InMemoryArtifactStore
) -> None:
    lines: list[str] = []
    report = smoke.Report(lines.append)
    smoke.slice_check(
        sessions, store=store, owner_email=OWNER, expect_build=None, timeout_s=0.0, report=report
    )
    assert report.failed is True
    assert any(line.startswith("FAIL  slice: the running worker completed") for line in lines)


def test_slice_check_fails_when_the_artifact_names_another_build(
    sessions: sessionmaker[Session],
    store: InMemoryArtifactStore,
    make_worker: Callable[..., Worker],
) -> None:
    worker = make_worker()  # BUILD is a15be650937aacaa
    lines: list[str] = []
    report = smoke.Report(lines.append)
    original_wait = smoke.wait_for_snapshot

    def wait(sess: sessionmaker[Session], **kwargs: Any) -> dict[str, Any]:
        # Drain the queue: the seed's own run is claimable too, and one claim
        # may pick it before the smoke's run.
        while worker.run_once() is not None:
            pass
        return original_wait(sess, **{**kwargs, "poll_s": 0.0})

    smoke.wait_for_snapshot = wait  # type: ignore[assignment]
    try:
        smoke.slice_check(
            sessions,
            store=store,
            owner_email=OWNER,
            expect_build="deadbeefdeadbeef",
            timeout_s=5.0,
            report=report,
        )
    finally:
        smoke.wait_for_snapshot = original_wait  # type: ignore[assignment]
    assert report.failed is True
    assert any("produced by the deployed build" in line for line in lines)


def test_start_workflow_for_the_seed_is_visible_to_the_seeded_scope(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        seed = seed_develop(session, owner_email=OWNER)
        scope = seeded_study_scope(session, owner_email=OWNER)
        again = start_workflow(
            session, scope, project_id=seed.project_id, workflow_type=DEVELOP_SNAPSHOT
        )
        assert again.run_id == seed.run_id
        assert SEED_ORGANIZATION_SLUG == "aia-develop"
