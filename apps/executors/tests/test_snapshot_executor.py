"""The develop_snapshot step, driven by the real worker loop over a real store."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aia_core.application.workflows import start_workflow
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.domain.workflow_templates import (
    DEVELOP_SNAPSHOT,
    RESEARCH_KINDS,
    UnknownWorkflowType,
    steps_for_workflow,
)
from aia_core.infrastructure.artifact_repository import ArtifactRepository
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.registry import build_registry, registry_for
from aia_executors.snapshot import ARTIFACT_TYPE, KIND, SnapshotExecutor
from aia_worker.registry import load_executors
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

# The research steps with an executor so far (ADR 0016; PR C adds the rest by chunk).
PRODUCTION_RESEARCH_KINDS = [
    RESEARCH_KINDS[n] for n in ("compile", "preflight", "run", "aggregate")
]


def _start(world: Any, **kwargs: Any) -> str:
    with world.sessions() as session:
        started = start_workflow(
            session,
            world.lead_scope(session),
            project_id=world.project_id,
            workflow_type=DEVELOP_SNAPSHOT,
            **kwargs,
        )
        session.commit()
        return started.run_id


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        result: dict[str, Any] = WorkflowRepository(session, world.lead_scope(session)).get_run(
            run_id
        )
        return result


def test_the_template_is_one_step_under_the_first_stage() -> None:
    from aia_core.domain.pipeline import ProjectType

    steps = steps_for_workflow(DEVELOP_SNAPSHOT, project_type=ProjectType.RESEARCH)
    assert [(s.node_key, s.kind, s.stage_type) for s in steps] == [("snapshot", KIND, "BRIEF")]
    assert not steps[0].consumes_population
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow("research_pipeline", project_type=ProjectType.RESEARCH)


def test_the_registry_offers_the_snapshot_kind_and_loads_through_the_worker(
    monkeypatch: pytest.MonkeyPatch, build: BuildIdentity
) -> None:
    monkeypatch.setenv("AIA_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("AIA_BUILD_SHA", build.sha or "")
    loaded = load_executors("aia_executors.registry:build_registry")
    # The production registry: the snapshot and the research steps (ADR 0016).
    assert set(loaded) == {KIND, *PRODUCTION_RESEARCH_KINDS}
    assert isinstance(build_registry()[KIND], SnapshotExecutor)


def test_the_worker_executes_a_snapshot_and_the_artifact_is_readable(
    world: Any,
    store: InMemoryArtifactStore,
    make_worker: Callable[..., Worker],
    build: BuildIdentity,
) -> None:
    run_id = _start(world)
    worker = make_worker()
    result = worker.run_once()
    assert result is not None and result.ending == "completed"

    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    step = run["steps"][0]
    assert step["status"] is StepRunStatus.SUCCEEDED
    output = step["output"]
    assert output["artifact_type"] == ARTIFACT_TYPE
    assert output["reused"] is False
    assert output["runtime_version"] == build.sha

    with world.sessions() as session:
        scope = world.lead_scope(session)
        artifacts = ArtifactRepository(session, scope, store)
        artifact = artifacts.get(output["artifact_id"])
        payload = artifacts.read_json(output["artifact_id"])
        content = ProjectRepository(session, scope).content(world.project_id)

    assert artifact.stage_type == "BRIEF"
    assert artifact.runtime_version == build.sha
    assert artifact.produced_by_job_id == step["attempts"][0]["attempt_id"]
    assert artifact.produced_by_user_id == world.lead_id, "the run's trigger is the producer"
    assert artifact.input_fingerprint == fingerprint(content) == payload["content_fingerprint"]
    assert payload["project_id"] == world.project_id
    assert payload["project_revision"] == 1
    assert payload["produced_by"]["run_id"] == run_id
    assert [s["stage_type"] for s in payload["stages"]][:2] == ["BRIEF", "DEEP_RESEARCH"]
    assert store.keys == [artifact.storage_key]


def test_starting_the_same_revision_twice_returns_the_same_run(world: Any) -> None:
    first = _start(world)
    with world.sessions() as session:
        again = start_workflow(
            session,
            world.lead_scope(session),
            project_id=world.project_id,
            workflow_type=DEVELOP_SNAPSHOT,
        )
    assert again.run_id == first
    assert again.created is False


def test_a_second_run_over_unchanged_content_reuses_the_artifact(
    world: Any, store: InMemoryArtifactStore, make_worker: Callable[..., Worker]
) -> None:
    """At-least-once execution must not upload twice; the fingerprint is the key."""
    worker = make_worker()
    first = _start(world, idempotency_key="one")
    assert worker.run_once() is not None
    second = _start(world, idempotency_key="two")
    assert worker.run_once() is not None

    a, b = _run(world, first)["steps"][0]["output"], _run(world, second)["steps"][0]["output"]
    assert a["artifact_id"] == b["artifact_id"]
    assert b["reused"] is True
    assert len(store.keys) == 1


def test_an_edit_produces_a_new_artifact_for_the_new_revision(
    world: Any, store: InMemoryArtifactStore, make_worker: Callable[..., Worker]
) -> None:
    worker = make_worker()
    first = _start(world)
    assert worker.run_once() is not None

    with world.sessions() as session:
        ProjectRepository(session, world.lead_scope(session)).save(
            world.project_id, content={"goal": "changed", "audience": {"age_min": 30}}
        )
        session.commit()
    second = _start(world)
    assert second != first
    assert worker.run_once() is not None

    assert _run(world, second)["project_revision"] == 2
    assert _run(world, second)["steps"][0]["output"]["reused"] is False
    assert len(store.keys) == 2


def test_a_viewer_cannot_start_a_run(world: Any, sessions: sessionmaker[Session]) -> None:
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.scope import ScopeDenied, ScopeRole
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with sessions() as session:
        resolver = ScopeResolver(session)
        admin_principal = AuthenticatedPrincipal(
            user_id=world.lead_id, organization_id=world.organization_id
        )
        # The lead is not an administrator; use the organization owner to grant.
        owner_id = ScopeRepository(session).upsert_user(email="owner@art-chain.io")["user_id"]
        admin = resolver.organization_context(
            AuthenticatedPrincipal(user_id=owner_id, organization_id=world.organization_id)
        )
        viewer = ScopeRepository(session).add_member(admin, email="viewer@art-chain.io")
        resolver.grant_client_access(
            admin, client_id=world.client_id, user_id=viewer.user_id, role=ScopeRole.VIEWER
        )
        session.flush()
        scope = resolver.study_context(
            AuthenticatedPrincipal(user_id=viewer.user_id, organization_id=world.organization_id),
            study_id=world.study_id,
        )
        with pytest.raises(ScopeDenied, match="RUN_WORKFLOW"):
            start_workflow(
                session, scope, project_id=world.project_id, workflow_type=DEVELOP_SNAPSHOT
            )
        del admin_principal


def test_registry_for_is_keyed_by_kind(store: InMemoryArtifactStore, build: BuildIdentity) -> None:
    registry = registry_for(store=store, build=build)
    assert list(registry) == [KIND, *PRODUCTION_RESEARCH_KINDS]
