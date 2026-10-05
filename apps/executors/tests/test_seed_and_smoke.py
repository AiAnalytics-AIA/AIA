"""The develop seed is idempotent and reversible; the smoke module tells the truth."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aia_core.application.develop_seed import (
    SEED_CLIENT_SLUG,
    SEED_ORGANIZATION_SLUG,
    SEED_PROJECT_TITLE,
    SEED_WORKSPACES,
    SMOKE_ORGANIZATION_SLUG,
    reset_develop_seed,
    seed_develop,
    seeded_study_scope,
)
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.application.workflows import start_workflow
from aia_core.domain.scope import ClientStatus, ScopeDenied, ScopeRole, StudyStatus
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
        "smoke_organization": True,
        "client": True,
        "study": True,
        "project": True,
        "run": True,
        "workspaces": True,
    }

    with sessions() as session:
        second = seed_develop(session, owner_email=OWNER)
        session.commit()
    assert (
        second.organization_id,
        second.smoke_organization_id,
        second.client_id,
        second.study_id,
        second.project_id,
    ) == (
        first.organization_id,
        first.smoke_organization_id,
        first.client_id,
        first.study_id,
        first.project_id,
    )
    assert first.smoke_organization_id != first.organization_id
    assert second.run_id == first.run_id
    assert not any(second.created.values())

    with sessions() as session:
        scope = seeded_study_scope(session)
        assert scope.role is ScopeRole.RESEARCHER
        assert scope.study_status is StudyStatus.ACTIVE
        projects = ProjectRepository(session, scope).list_projects()
        assert [p.title for p in projects.items] == [SEED_PROJECT_TITLE]
        run = WorkflowRepository(session, scope).get_run(first.run_id)
        # A run whose only step is RUNNABLE derives as RUNNING: nothing waits on a person.
        assert run["status"] is WorkflowRunStatus.RUNNING
        assert not run["status"].is_terminal
        assert run["workflow_type"] == DEVELOP_SNAPSHOT
        assert ScopeRepository(session).study_spend(scope)["budget_usd"] == 25.0


def test_seed_gives_two_fictional_clients_their_own_work_and_knowledge(
    sessions: sessionmaker[Session],
) -> None:
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.knowledge import ProposalStatus
    from aia_core.domain.scope import StudyKind
    from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository

    with sessions() as session:
        result = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        again = seed_develop(session, owner_email=OWNER)
        session.commit()
    assert again.workspaces == result.workspaces and again.created["workspaces"] is False
    assert set(result.workspaces) == set(SEED_WORKSPACES)

    with sessions() as session:
        resolver = ScopeResolver(session)
        repo = ScopeRepository(session)
        knowledge = ClientKnowledgeRepository(session)
        owner = AuthenticatedPrincipal(
            user_id=result.owner_user_id, organization_id=result.organization_id
        )
        seen: dict[str, set[str]] = {}
        for slug, client_id in result.workspaces.items():
            ctx = resolver.client_context(owner, client_id=client_id)
            studies = repo.studies_in_client(ctx)
            assert {s.kind for s in studies} == {StudyKind.RESEARCH, StudyKind.SIMULATION}
            assert len(studies) == len(SEED_WORKSPACES[slug]["studies"])
            items = knowledge.items(ctx)
            assert len(items) == len(SEED_WORKSPACES[slug]["knowledge"])
            assert all(
                knowledge.revisions(ctx, item_id=i.item_id)[0].approved_by != result.owner_user_id
                for i in items
            )
            pending = knowledge.proposals(ctx, status=ProposalStatus.PROPOSED)
            assert len(pending) == (1 if SEED_WORKSPACES[slug]["pending"] else 0)
            seen[slug] = {i.title for i in items}
        # Each client's knowledge is its own.
        a, b = seen.values()
        assert not a & b


def test_seed_admits_a_new_operator_to_an_existing_world(
    sessions: sessionmaker[Session],
) -> None:
    # A changed AIA_SEED_OWNER_EMAIL used to be denied as `not_a_member` before
    # the seed could add it, which failed every develop smoke with a bare
    # "ScopeDenied: not found" (deploy runs 36-38).
    with sessions() as session:
        first = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        second = seed_develop(session, owner_email="second-operator@example.test")
        session.commit()
    assert second.organization_id == first.organization_id
    assert second.study_id == first.study_id
    assert second.owner_user_id != first.owner_user_id
    with sessions() as session:
        again = seed_develop(session, owner_email=OWNER)
        session.commit()
    assert again.owner_user_id == first.owner_user_id


def test_seed_names_why_an_archived_seed_client_is_denied(
    sessions: sessionmaker[Session],
) -> None:
    # Archiving the smoke's own client is a decision the seed does not undo, and
    # the smoke line says which row stopped it. Nobody sees that client in their
    # workspace, so only someone acting in the smoke's organization can do it.
    with sessions() as session:
        seeded = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=seeded.smoke_owner_user_id,
                organization_id=seeded.smoke_organization_id,
            )
        )
        ScopeRepository(session).set_client_status(
            admin, client_id=seeded.client_id, status=ClientStatus.ARCHIVED
        )
        session.commit()
    with sessions() as session, pytest.raises(ScopeDenied) as denied:
        seed_develop(session, owner_email=OWNER)
    assert denied.value.reason == "client_archived"
    assert smoke.describe_failure(denied.value) == (
        "ScopeDenied: not found (reason: client_archived)"
    )
    assert smoke.describe_failure(RuntimeError("boom")) == "RuntimeError: boom"


def test_seed_leaves_an_archived_fictional_client_as_it_was(
    sessions: sessionmaker[Session],
) -> None:
    # A person archiving one of the showcase clients (Settings, PUT
    # /clients/{id}/status) must not fail every later deploy: the seed leaves
    # that client archived and seeds nothing into it. Deploy run 40 failed on
    # an archived client (OI-80).
    with sessions() as session:
        seeded = seed_develop(session, owner_email=OWNER)
        session.commit()
    archived = seeded.workspaces["lumen-pojistovna"]
    with sessions() as session:
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=seeded.owner_user_id, organization_id=seeded.organization_id
            )
        )
        ScopeRepository(session).set_client_status(
            admin, client_id=archived, status=ClientStatus.ARCHIVED
        )
        session.commit()

    with sessions() as session:
        again = seed_develop(session, owner_email=OWNER)
        session.commit()

    assert again.workspaces["lumen-pojistovna"] == archived
    assert again.study_id == seeded.study_id
    with sessions() as session:
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=seeded.owner_user_id, organization_id=seeded.organization_id
            )
        )
        statuses = {
            c.slug: c.status
            for c in ScopeRepository(session).list_clients(admin, include_archived=True)
        }
    assert statuses["lumen-pojistovna"] is ClientStatus.ARCHIVED
    assert statuses["horizont-mobility"] is ClientStatus.ACTIVE


def test_seed_refuses_a_blank_operator(sessions: sessionmaker[Session]) -> None:
    with sessions() as session, pytest.raises(ValueError, match="AIA_SEED_OWNER_EMAIL"):
        seed_develop(session, owner_email="")


def test_the_smoke_acts_in_an_organization_the_operator_never_sees(
    sessions: sessionmaker[Session],
) -> None:
    # The operator's client list (GET /workspace/clients) holds the showcase
    # clients only: the smoke's client is in an organization they are not in.
    with sessions() as session:
        seeded = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        resolver = ScopeResolver(session)
        repo = ScopeRepository(session)
        operator = AuthenticatedPrincipal(
            user_id=seeded.owner_user_id, organization_id=seeded.organization_id
        )
        assert set(resolver.accessible_clients(operator)) == set(seeded.workspaces.values())
        assert seeded.smoke_organization_id not in repo.memberships_for_user(seeded.owner_user_id)
        assert seeded.organization_id not in repo.memberships_for_user(seeded.smoke_owner_user_id)
        slugs = {
            c.slug
            for c in repo.list_clients(
                resolver.organization_context(operator), include_archived=True
            )
        }
        assert SEED_CLIENT_SLUG not in slugs
        scope = seeded_study_scope(session)
        assert (scope.organization_id, scope.client_id, scope.study_id) == (
            seeded.smoke_organization_id,
            seeded.client_id,
            seeded.study_id,
        )
        assert scope.actor_id == seeded.smoke_owner_user_id
        assert scope.role is ScopeRole.RESEARCHER


def test_an_archived_synthetic_client_in_the_operator_organization_does_not_stop_the_smoke(
    sessions: sessionmaker[Session],
) -> None:
    # The develop host's state after deploy runs 36-41: the operator's
    # organization holds the smoke client the seed used to make there, with the
    # operator LEAD on it, archived on purpose to keep it out of the client list.
    with sessions() as session:
        seeded = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        resolver = ScopeResolver(session)
        repo = ScopeRepository(session)
        admin = resolver.organization_context(
            AuthenticatedPrincipal(
                user_id=seeded.owner_user_id, organization_id=seeded.organization_id
            )
        )
        old = {c.slug: c for c in repo.list_clients(admin, include_archived=True)}.get(
            SEED_CLIENT_SLUG
        )
        if old is None:
            old = repo.create_client(
                admin, slug=SEED_CLIENT_SLUG, name="Synthetic client (develop)"
            )
        repo.set_client_status(admin, client_id=old.client_id, status=ClientStatus.ARCHIVED)
        session.commit()

    with sessions() as session:
        again = seed_develop(session, owner_email=OWNER)
        session.commit()
    with sessions() as session:
        scope = seeded_study_scope(session)
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=seeded.owner_user_id, organization_id=seeded.organization_id
            )
        )
        statuses = {
            c.slug: c.status
            for c in ScopeRepository(session).list_clients(admin, include_archived=True)
        }
    assert again.client_id == seeded.client_id != old.client_id
    assert scope.client_id == seeded.client_id
    assert statuses[SEED_CLIENT_SLUG] is ClientStatus.ARCHIVED


def test_reset_removes_only_the_seeded_organizations(sessions: sessionmaker[Session]) -> None:
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
        assert SMOKE_ORGANIZATION_SLUG not in slugs
        assert session.scalar(select(func.count()).select_from(OrganizationRow)) == 1
        assert reset_develop_seed(session) is False
        with pytest.raises(LookupError):
            seeded_study_scope(session)


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


def test_the_ai_check_is_not_runnable_and_says_why_without_claiming_a_live_route() -> None:
    lines: list[str] = []
    report = smoke.Report(lines.append)
    smoke.ai_check(report)
    assert report.failed is False
    assert lines == [
        "NOT_RUNNABLE  ai: governed model call through ModelGateway -> bedrock-eu-primary",
        "      the smoke makes no paid model call; the AI runtime is off by default "
        "and is checked by its own acceptance, not on each deploy (ADR 0010, "
        "docs/architecture/bedrock-develop-activation-2026-09-26.md)",
    ]


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
    # Whichever run the worker claimed first (the seed's own run is claimable too)
    # produced the artifact; the other reused it. Either way the executing build
    # is the one under test, and that is the fact the check reports.
    assert any(
        "artifact provenance names build a15be650937aacaa" in line
        or "executed by build a15be650937aacaa" in line
        for line in lines
    ), lines
    # The seeded run and the smoke's own run both exist.
    with sessions() as session:
        scope = seeded_study_scope(session)
        runs = WorkflowRepository(session, scope).list_runs(project_id=scope_project(session))
    assert len(runs) == 2


def scope_project(session: Session) -> str:
    scope = seeded_study_scope(session)
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
    assert any("executed by the deployed build" in line for line in lines)


def test_slice_check_accepts_an_artifact_reused_from_an_earlier_build(
    sessions: sessionmaker[Session],
    store: InMemoryArtifactStore,
    database_url: str,
    make_worker: Callable[..., Worker],
) -> None:
    """The second deploy over unchanged content reuses the first deploy's artifact.

    Reuse by content fingerprint is the design (``snapshot.py``), so the artifact
    keeps the provenance of the build that first produced it. What the smoke
    check must prove is that the *deployed* build executed the run; it must not
    fail because the bytes already existed. Deploy develop run 35869042785 failed
    exactly this way at ``848ec11`` after ``b5c331f`` had produced the artifact.
    """
    from aia_core.infrastructure.build_identity import BuildIdentity
    from aia_executors.registry import registry_for
    from aia_worker.settings import WorkerSettings

    previous_build = "b5c331fa4031f276"
    previous_worker = Worker(
        session_factory=sessions,
        executors=registry_for(
            store=store, build=BuildIdentity(sha=previous_build, built_at="2026-09-23T13:00:00Z")
        ),
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="worker-previous",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )
    current_worker = make_worker()  # BUILD is a15be650937aacaa
    original_wait = smoke.wait_for_snapshot

    def drain_with(worker: Worker) -> Callable[..., dict[str, Any]]:
        def wait(sess: sessionmaker[Session], **kwargs: Any) -> dict[str, Any]:
            while worker.run_once() is not None:
                pass
            return original_wait(sess, **{**kwargs, "poll_s": 0.0})

        return wait

    # First deploy: the previous build produces the artifact.
    first: list[str] = []
    smoke.wait_for_snapshot = drain_with(previous_worker)  # type: ignore[assignment]
    try:
        smoke.slice_check(
            sessions,
            store=store,
            owner_email=OWNER,
            expect_build=previous_build,
            timeout_s=5.0,
            report=smoke.Report(first.append),
        )
    finally:
        smoke.wait_for_snapshot = original_wait  # type: ignore[assignment]
    assert not any(line.startswith("FAIL") for line in first), first
    assert len(store.keys) == 1

    # Second deploy, same content: the current build executes, the artifact is reused.
    second: list[str] = []
    report = smoke.Report(second.append)
    smoke.wait_for_snapshot = drain_with(current_worker)  # type: ignore[assignment]
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
    assert report.failed is False, second
    assert any(
        f"reused from build {previous_build}" in line
        and "executed by build a15be650937aacaa" in line
        for line in second
    ), second
    assert len(store.keys) == 1, "reuse must not upload a second copy"


def test_start_workflow_for_the_seed_is_visible_to_the_seeded_scope(
    sessions: sessionmaker[Session],
) -> None:
    with sessions() as session:
        seed = seed_develop(session, owner_email=OWNER)
        scope = seeded_study_scope(session)
        again = start_workflow(
            session, scope, project_id=seed.project_id, workflow_type=DEVELOP_SNAPSHOT
        )
        assert again.run_id == seed.run_id
        assert SEED_ORGANIZATION_SLUG == "aia-develop"
