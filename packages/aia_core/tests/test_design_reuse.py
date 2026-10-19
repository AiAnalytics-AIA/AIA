"""Reusing a past study's design, scoped to one client (plans/project-memory-reuse.md M3c).

Over the two-client world in ``conftest.py``: the primary client's study has a design and a
run on the fictional fixture. Its design starts a new study, or an empty one, of the same
client: the target's working content and first Design Revision are the source's content, the
citation carries the source's labels, and the source is unchanged. A target with content, a
simulation, a study of another client and a revision of another study are each refused.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.application.design_reuse import ReuseRefused, reuse_design
from aia_core.application.research import ResearchRuns
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.scope import ScopeDenied, StudyKind
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Jak často?", "typ": "skala", "skala": [1, 5]}],
        }
    ],
}


class _World:
    """The scope fixture, with the source revision and its run beside it."""

    def __init__(self, scoped: Any, source_revision: Any, source_run_id: str) -> None:
        self._scoped = scoped
        self.source_revision = source_revision
        self.source_run_id = source_run_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._scoped, name)


@pytest.fixture
def world(session: Any, scoped: Any) -> Any:
    """The primary study's design, run once on the fictional fixture."""
    source = StudyDesignRepository(session, scoped.scope(study="primary"))
    revision, _ = source.submit_as_working_copy(content=DESIGN, source_stage="run")
    run = ResearchRuns(session, scoped.scope(study="primary")).start(
        design_revision_id=revision.revision_id,
        fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
    )
    session.flush()
    return _World(scoped, revision, run.run_id)


def _reuse(world: Any, session: Any, **kw: Any) -> Any:
    args: dict[str, Any] = {
        "client_id": world.clients["primary"].client_id,
        "source_study_id": world.studies["primary"].study_id,
        "source_revision_id": world.source_revision.revision_id,
    }
    args.update(kw)
    return reuse_design(
        session,
        world.resolver,
        world.principal(world.users["lead"]),
        InMemoryArtifactStore(),
        **args,
    )


def test_a_new_study_starts_from_the_design_with_its_citation_and_labels(
    world: Any, session: Any
) -> None:
    reused = _reuse(world, session, new_study=("ranni-napoj-2", "Ranní nápoj 2"))
    assert reused.created_study
    target = world.resolver.study_context(
        world.principal(world.users["lead"]), study_id=reused.study_id
    )
    assert target.client_id == world.clients["primary"].client_id
    assert StudyWorkspaceRepository(session).content(target).content == DESIGN
    designs = StudyDesignRepository(session, target)
    assert [r.revision_id for r in designs.revisions()] == [reused.revision.revision_id]
    assert reused.revision.source_stage == "memory"
    assert designs.content(reused.revision.revision_id) == DESIGN
    # The reused design names the working revision the reuse wrote (ADR 0026 decision 5).
    working = StudyWorkspaceRepository(session).content(target)
    assert reused.revision.workspace_revision is not None
    assert reused.revision.workspace_revision == working.revision
    cited = designs.source()
    assert cited == reused.source
    assert (cited.source_study_id, cited.source_revision_id) == (
        world.studies["primary"].study_id,
        world.source_revision.revision_id,
    )
    assert cited.source_content_sha256 == world.source_revision.content_sha256
    assert cited.labels.synthetic and not cited.labels.never_run
    assert cited.labels.run_ids == (world.source_run_id,)
    # The source is unchanged: still one revision, no citation of its own.
    source = StudyDesignRepository(session, world.scope(study="primary"))
    assert [r.revision_id for r in source.revisions()] == [world.source_revision.revision_id]
    assert source.source() is None


def test_an_empty_study_of_the_client_takes_the_design_and_one_with_content_is_refused(
    world: Any, session: Any
) -> None:
    sibling = world.studies["sibling"].study_id
    reused = _reuse(world, session, target_study_id=sibling)
    assert (reused.study_id, reused.created_study) == (sibling, False)
    with pytest.raises(ReuseRefused) as again:
        _reuse(world, session, target_study_id=sibling)
    assert again.value.reason == "target_not_empty"


def test_a_target_with_working_content_alone_is_not_empty(world: Any, session: Any) -> None:
    sibling = world.scope(study="sibling")
    StudyWorkspaceRepository(session).save(
        sibling, content={"title": "Rozepsáno"}, base_revision=None
    )
    with pytest.raises(ReuseRefused) as refused:
        _reuse(world, session, target_study_id=sibling.study_id)
    assert refused.value.reason == "target_not_empty"
    assert StudyDesignRepository(session, sibling).latest() is None


def test_a_simulation_is_not_a_target(world: Any, session: Any) -> None:
    client = world.resolver.client_context(
        world.principal(world.users["lead"]), client_id=world.clients["primary"].client_id
    )
    simulation = ScopeRepository(session).create_study_in_client(
        client, slug="sim", name="Scénář", kind=StudyKind.SIMULATION
    )
    session.flush()
    with pytest.raises(ReuseRefused) as refused:
        _reuse(world, session, target_study_id=simulation.study_id)
    assert refused.value.reason == "not_research"


def test_nothing_crosses_the_client(world: Any, session: Any) -> None:
    other = world.studies["other_client"].study_id
    # A target of another client.
    with pytest.raises(ScopeDenied):
        _reuse(world, session, target_study_id=other)
    # A source of another client, named under this one.
    theirs = StudyDesignRepository(session, world.scope(user="other_lead", study="other_client"))
    revision, _ = theirs.submit_as_working_copy(content=DESIGN, source_stage="run")
    with pytest.raises(ScopeDenied):
        _reuse(
            world,
            session,
            source_study_id=other,
            source_revision_id=revision.revision_id,
            new_study=("x", "X"),
        )
    # A revision of another study, named as the source's.
    with pytest.raises(DesignRevisionNotFound):
        _reuse(world, session, source_revision_id=revision.revision_id, new_study=("y", "Y"))


def test_a_source_never_run_is_cited_as_never_run(world: Any, session: Any) -> None:
    edited = StudyDesignRepository(session, world.scope(study="primary"))
    second, _ = edited.submit_as_working_copy(content={**DESIGN, "n": 300}, source_stage="run")
    reused = _reuse(world, session, source_revision_id=second.revision_id, new_study=("z", "Z"))
    labels = reused.source.labels
    assert (labels.never_run, labels.synthetic, labels.run_ids) == (True, False, ())
