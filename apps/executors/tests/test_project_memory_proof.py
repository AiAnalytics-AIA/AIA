"""Project memory's proof: reuse from a fictional source, end to end (project-memory-reuse.md M4).

One connected story through the real worker. A study of one client runs its design on the
fictional fixture until every step has produced its artifact. A new study of the same client is
then started from that design. Afterwards:

- the source is byte-identical: its revisions, their content, its run, and every artifact's bytes;
- the new study's working content and first Design Revision are the design, and its citation says
  the source was fictional (``synthetic``), naming the very run it was derived from;
- a sibling client of the same organization is refused, and another organization is refused, each
  asserted on its own -- an organization predicate alone would pass the second and still expose a
  sibling client -- and neither refusal writes anything.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.application.design_reuse import reuse_design
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.scope import ScopeDenied, StudyKind
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_executors import workbench
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 40,
    "sections": [
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        }
    ],
}


@pytest.fixture
def worker(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Worker:
    executors: dict[str, StepExecutor] = workbench.workbench_registry_for(store=store, build=build)
    return Worker(
        session_factory=sessions,
        executors=executors,
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="project-memory-proof",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _lead(world: Any) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id)


def _source_snapshot(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    """Everything of the source a reuse could touch, as bytes and ids."""
    with world.sessions() as session:
        scope = world.lead_scope(session)
        designs = StudyDesignRepository(session, scope)
        revisions = designs.revisions()
        runs = ResearchRuns(session, scope)
        run = runs.get(run_id)
        artifacts = research_artifacts(session, scope, store)
        ids = runs.artifact_ids(run_id)
        return {
            "revisions": [(r.revision_id, r.content_sha256) for r in revisions],
            "contents": [designs.content(r.revision_id) for r in revisions],
            "source": designs.source(),
            "working": StudyWorkspaceRepository(session).content(scope).content,
            "run": (run["status"], [(s["node_key"], s["status"]) for s in run["steps"]]),
            "artifacts": {a: (artifacts.get(a).sha256, artifacts.read(a)) for a in ids},
        }


def _studies(
    sessions: sessionmaker[Session], principal: AuthenticatedPrincipal, client_id: str
) -> int:
    with sessions() as session:
        client = ScopeResolver(session).client_context(principal, client_id=client_id)
        return len(ScopeRepository(session).studies_in_client(client))


def test_a_fictional_source_reused_stays_untouched_cites_its_labels_and_never_crosses_a_boundary(
    world: Any, worker: Worker, store: InMemoryArtifactStore, sessions: sessionmaker[Session]
) -> None:
    # -- the source: one design, one run on the fictional fixture, every step done ------------
    with sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit(
            content=DESIGN, source_stage="run"
        )
        run_id = (
            ResearchRuns(session, scope)
            .start(
                design_revision_id=revision.revision_id,
                fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            )
            .run_id
        )
        session.commit()
    while worker.run_once() is not None:
        pass
    before = _source_snapshot(world, store, run_id)
    assert before["run"][0] is WorkflowRunStatus.COMPLETED
    assert before["artifacts"], "the fictional run produced its artifacts"

    # -- a sibling client in the organization, and another organization ----------------------
    with sessions() as session:
        repo = ScopeRepository(session)
        admin = world.admin_context(session)
        sibling = repo.create_client(admin, slug="globex", name="Globex")
        other_org, other_owner = repo.create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="owner@elsewhere.test"
        )
        other_admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(
                user_id=other_owner.user_id, organization_id=other_org.organization_id
            )
        )
        theirs = repo.create_client(other_admin, slug="theirs", name="Theirs")
        session.commit()
    outsider = AuthenticatedPrincipal(
        user_id=other_owner.user_id, organization_id=other_org.organization_id
    )
    counts = {
        "acme": _studies(sessions, _lead(world), world.client_id),
        "globex": _studies(sessions, _lead(world), sibling.client_id),
        "theirs": _studies(sessions, outsider, theirs.client_id),
    }

    # -- the reuse --------------------------------------------------------------------------
    with sessions() as session:
        reused = reuse_design(
            session,
            ScopeResolver(session),
            _lead(world),
            store,
            client_id=world.client_id,
            source_study_id=world.study_id,
            source_revision_id=revision.revision_id,
            new_study=("ranni-napoj-znovu", "Ranní nápoj znovu"),
        )
        session.commit()
    assert reused.created_study
    with sessions() as session:
        target = ScopeResolver(session).study_context(_lead(world), study_id=reused.study_id)
        assert target.client_id == world.client_id
        assert ScopeRepository(session).get_study(target).kind is StudyKind.RESEARCH
        assert StudyWorkspaceRepository(session).content(target).content == DESIGN
        designs = StudyDesignRepository(session, target)
        [first] = designs.revisions()
        assert first.source_stage == "memory"
        assert designs.content(first.revision_id) == DESIGN
        cited = designs.source()
    assert cited is not None
    assert (cited.source_study_id, cited.source_revision_id, cited.source_content_sha256) == (
        world.study_id,
        revision.revision_id,
        revision.content_sha256,
    )
    labels = cited.labels
    assert labels.synthetic and not labels.never_run and not labels.unlabelled_data
    assert labels.run_ids == (run_id,)

    # -- the source, byte for byte ------------------------------------------------------------
    assert _source_snapshot(world, store, run_id) == before

    # -- the sibling client of the same organization, on its own -------------------------------
    with sessions() as session, pytest.raises(ScopeDenied):
        reuse_design(
            session,
            ScopeResolver(session),
            _lead(world),
            store,
            client_id=sibling.client_id,
            source_study_id=world.study_id,
            source_revision_id=revision.revision_id,
            new_study=("globex-kopie", "Globex kopie"),
        )

    # -- another organization, on its own ----------------------------------------------------
    for client_id in (world.client_id, theirs.client_id):
        with sessions() as session, pytest.raises(ScopeDenied):
            reuse_design(
                session,
                ScopeResolver(session),
                outsider,
                store,
                client_id=client_id,
                source_study_id=world.study_id,
                source_revision_id=revision.revision_id,
                new_study=("cizi", "Cizí"),
            )

    # Neither refusal wrote anything: the one new study is the reuse's, in its own client.
    assert _studies(sessions, _lead(world), world.client_id) == counts["acme"] + 1
    assert _studies(sessions, _lead(world), sibling.client_id) == counts["globex"]
    assert _studies(sessions, outsider, theirs.client_id) == counts["theirs"]
    assert _source_snapshot(world, store, run_id) == before
