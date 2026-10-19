"""Design Revisions (ADR 0016 decision 1): what a research run executes.

The browser submits the design it holds; AIA stores it as an immutable revision
of the Study's own design project. These tests pin what makes that safe: content
never carries authority, a revision never changes, and a revision is reachable
only through its own Study.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.workflows import start_workflow
from aia_core.domain.design import DESIGN_MAX_BYTES, DesignRejected, validate_design
from aia_core.domain.scope import ScopeDenied, StudyKind, StudyStatus
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.study_design_repository import (
    DesignRevisionNotFound,
    StudyDesignRepository,
)
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import ProjectRevisionRow

DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "sections": [{"type": "questions", "questions": [{"id": "q1", "typ": "skala"}]}],
    "n": 450,
}


@pytest.fixture
def designs(session: Any, scoped: Any) -> Any:
    """A repository for a user's scope on a study: ``designs(user=…, study=…)``."""
    return lambda **kw: StudyDesignRepository(session, scoped.scope(**kw))


def test_the_first_design_creates_the_studys_design_and_its_first_revision(
    scoped: Any, designs: Any
) -> None:
    repo = designs()
    assert repo.project_id() is None and repo.revisions() == [] and repo.latest() is None
    revision, created = repo.submit_as_working_copy(content=DESIGN, source_stage="run")
    assert created and revision.revision == 1 and revision.parent_revision is None
    assert revision.revision_id.startswith("REV-")
    assert revision.study_id == scoped.studies["primary"].study_id
    assert revision.source_stage == "run" and revision.created_by == scoped.users["lead"]
    assert repo.content(revision.revision_id) == DESIGN
    assert repo.project_id() is not None


def test_identical_content_is_the_same_revision_and_an_edit_is_a_new_one(
    scoped: Any, designs: Any
) -> None:
    repo = designs()
    first, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="persona")
    again, created = repo.submit_as_working_copy(content=dict(DESIGN), source_stage="run")
    assert not created and again.revision_id == first.revision_id
    edited, created = repo.submit_as_working_copy(
        content={**DESIGN, "n": 500}, source_stage="persona"
    )
    assert created and edited.revision == 2 and edited.parent_revision == 1
    # The revision under an existing run never changes.
    assert repo.content(first.revision_id)["n"] == 450
    assert [r.revision for r in repo.revisions()] == [2, 1]
    assert repo.latest() == edited


def test_content_never_carries_authority(scoped: Any, designs: Any) -> None:
    repo = designs()
    for key in ("client_id", "study_id", "organization_id", "Actor_ID"):
        with pytest.raises(DesignRejected) as refused:
            repo.submit(
                content={**DESIGN, key: "CLI-other"}, source_stage="run", workspace_revision=1
            )
        assert refused.value.reason == "design_carries_scope"
    # The unit store's own ids are data, not identity: stored as submitted, trusted for nothing.
    revision, _ = repo.submit_as_working_copy(
        content={**DESIGN, "project_id": "PRJ-unit"}, source_stage="run"
    )
    assert revision.study_id == scoped.studies["primary"].study_id


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ([1, 2], "design_not_object"),
        ({}, "design_empty"),
        ({"x": float("nan")}, "design_not_json"),
        ({"blob": "x" * (DESIGN_MAX_BYTES + 1)}, "design_too_large"),
    ],
)
def test_a_design_is_a_bounded_json_object(content: Any, reason: str) -> None:
    with pytest.raises(DesignRejected) as refused:
        validate_design(content)
    assert refused.value.reason == reason


def test_everyone_with_the_study_submits_a_design_while_it_is_open(
    scoped: Any, designs: Any
) -> None:
    """ADR 0019: one role holds EDIT_STUDY, so the former viewer and reviewer submit a design.

    A design identical to the newest is no new revision; what still bounds a submit is a
    missing grant, a rejected source stage and a closed study.
    """
    for i, user in enumerate(("viewer", "reviewer", "researcher")):
        _, created = designs(user=user).submit_as_working_copy(
            content={**DESIGN, "n": i + 1}, source_stage="run"
        )
        assert created, user
    # A member who was never granted the study submits like the others (ADR 0019).
    _, created = designs(user="outsider").submit_as_working_copy(
        content={**DESIGN, "n": 4}, source_stage="run"
    )
    assert created
    with pytest.raises(DesignRejected):
        designs().submit_as_working_copy(content=DESIGN, source_stage="results")
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        designs().submit_as_working_copy(content={**DESIGN, "n": 99}, source_stage="run")
    assert closed.value.reason == "study_closed"


def test_a_simulation_has_no_research_design(scoped: Any, designs: Any) -> None:
    sim = scoped.scope_repo.create_study(
        scoped.admin_context,
        client_id=scoped.clients["primary"].client_id,
        slug="scenarios",
        name="Acme scenarios",
        kind=StudyKind.SIMULATION,
    )
    scoped.studies["simulation"] = sim
    with pytest.raises(DesignRejected) as refused:
        designs(study="simulation").submit(content=DESIGN, source_stage="run", workspace_revision=1)
    assert refused.value.reason == "not_research"


def test_a_revision_is_reachable_only_through_its_own_study(scoped: Any, designs: Any) -> None:
    acme, _ = designs().submit_as_working_copy(content=DESIGN, source_stage="run")
    # Each study has a design of its own, so only the Study filter can refuse Acme's id.
    designs(study="sibling").submit_as_working_copy(content={**DESIGN, "n": 1}, source_stage="run")
    designs(user="other_lead", study="other_client").submit_as_working_copy(
        content=DESIGN, source_stage="run"
    )
    # The sibling study of the same client does not see it.
    with pytest.raises(DesignRevisionNotFound):
        designs(study="sibling").get(acme.revision_id)
    # Another client's lead, in their own study, cannot reach it by id either.
    globex = designs(user="other_lead", study="other_client")
    with pytest.raises(DesignRevisionNotFound):
        globex.get(acme.revision_id)
    with pytest.raises(DesignRevisionNotFound):
        globex.content(acme.revision_id)
    # Every read viewers may do is keyed by the Study; nothing looks a Study up by a project id.
    assert designs(user="viewer").get(acme.revision_id) == acme
    for name, method in inspect.getmembers(StudyDesignRepository, inspect.isfunction):
        if not name.startswith("_"):
            params = inspect.signature(method).parameters
            assert "project_id" not in params and "study_id" not in params, name


def test_the_repository_refuses_anything_but_an_issued_scope(session: Any) -> None:
    with pytest.raises(TypeError):
        StudyDesignRepository(session, {"study_id": "STU-x"})  # type: ignore[arg-type]


def test_only_the_design_repository_can_see_or_write_the_design(
    session: Any, scoped: Any, designs: Any
) -> None:
    """Every revision of a design passed validate_design: nothing else can write one."""
    repo = designs()
    first, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="run")
    project_id = repo.project_id()
    assert project_id is not None
    ordinary = ProjectRepository(session, scoped.scope())
    assert project_id not in [p.project_id for p in ordinary.list_projects().items]
    with pytest.raises(ProjectNotFound):
        ordinary.get(project_id)
    with pytest.raises(ProjectNotFound):
        ordinary.save(project_id, content={**DESIGN, "client_id": "CLI-other"})
    with pytest.raises(ProjectNotFound):
        ordinary.update_settings(project_id, title="renamed")
    with pytest.raises(ProjectNotFound):
        ordinary.move_to_trash(project_id)
    with pytest.raises(ProjectNotFound):
        start_workflow(session, scoped.scope(), project_id=project_id, workflow_type="research")
    # An ordinary project of the same Study is untouched by any of this.
    plain, _ = ordinary.create(title="Plain", content={"goal": "g"})
    assert plain.project_id in [p.project_id for p in ordinary.list_projects().items]
    assert [r.revision_id for r in repo.revisions()] == [first.revision_id]


def test_a_revision_row_is_never_updated(session: Any, designs: Any) -> None:
    revision, _ = designs().submit_as_working_copy(content=DESIGN, source_stage="run")
    row = session.scalars(
        select(ProjectRevisionRow).where(ProjectRevisionRow.revision_id == revision.revision_id)
    ).one()
    row.content = {**DESIGN, "n": 1}
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()


# -- a reused design's citation (project memory M3b) ---------------------------


def _labels() -> Any:
    from aia_core.domain.design_reuse import SourceRun, derive_source_labels

    return derive_source_labels([SourceRun(run_id="RUN-1", fieldwork_source="synthetic_fixture")])


def test_a_studys_design_source_is_recorded_once_and_read_through_the_study(
    scoped: Any, designs: Any
) -> None:
    repo = designs(study="sibling")
    assert repo.source() is None
    revision, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="memory")
    source_study = scoped.studies["primary"].study_id
    cited = repo.record_source(
        revision_id=revision.revision_id,
        source_study_id=source_study,
        source_revision_id="REV-source",
        source_revision=3,
        source_content_sha256="a" * 64,
        labels=_labels(),
    )
    assert repo.source() == cited
    assert (cited.source_study_id, cited.source_revision, cited.labels.synthetic) == (
        source_study,
        3,
        True,
    )
    assert cited.labels.run_ids == ("RUN-1",) and cited.created_by == scoped.users["lead"]
    with pytest.raises(DesignRejected) as again:
        repo.record_source(
            revision_id=revision.revision_id,
            source_study_id=source_study,
            source_revision_id="REV-other",
            source_revision=4,
            source_content_sha256="b" * 64,
            labels=_labels(),
        )
    assert again.value.reason == "source_already_recorded"
    # Another Study sees nothing of it.
    assert designs().source() is None


def test_a_source_cites_only_a_revision_of_the_study_itself(scoped: Any, designs: Any) -> None:
    mine, _ = designs().submit_as_working_copy(content=DESIGN, source_stage="run")
    theirs = designs(study="sibling")
    with pytest.raises(DesignRevisionNotFound):
        theirs.record_source(
            revision_id=mine.revision_id,
            source_study_id=scoped.studies["primary"].study_id,
            source_revision_id=mine.revision_id,
            source_revision=1,
            source_content_sha256=mine.content_sha256,
            labels=_labels(),
        )


# -- the working revision a Design Revision came from (ADR 0026 decision 5) ---------------------


def test_a_design_names_the_working_revision_it_is_and_is_checked_by_hash(
    session: Any, scoped: Any, designs: Any
) -> None:
    scope = scoped.scope()
    workspaces = StudyWorkspaceRepository(session)
    saved = workspaces.save(scope, content=DESIGN, base_revision=None)
    repo = designs()
    revision, created = repo.submit(
        content=dict(DESIGN), source_stage="questionnaire", workspace_revision=saved.revision
    )
    assert created and revision.workspace_revision == saved.revision
    assert revision.source_stage == "questionnaire"
    assert repo.get(revision.revision_id).workspace_revision == saved.revision
    # Content that is not that revision's, or a revision the working copy never wrote.
    for content, number in (({**DESIGN, "n": 1}, saved.revision), (DESIGN, saved.revision + 7)):
        with pytest.raises(DesignRejected) as refused:
            repo.submit(content=content, source_stage="run", workspace_revision=number)
        assert refused.value.reason == "design_not_from_workspace"
    # The same design from a later working revision is the same Design Revision, which keeps
    # the working revision it was first written from.
    later = workspaces.save(scope, content=DESIGN, analysis={"x": 1}, base_revision=saved.revision)
    assert later.revision == saved.revision + 1
    again, created = repo.submit(
        content=DESIGN, source_stage="run", workspace_revision=later.revision
    )
    assert not created and again.workspace_revision == saved.revision


def test_a_revision_without_a_working_revision_is_never_reused_for_one_that_has_it(
    session: Any, scoped: Any, designs: Any
) -> None:
    """A revision written before the rule names none; the same content submitted now is a new
    revision naming its working revision, so no proposal is made on an unknown baseline."""
    repo = designs()
    first, _ = repo.submit_as_working_copy(content=DESIGN, source_stage="run")
    project_id = repo.project_id()
    assert project_id is not None
    legacy = ProjectRepository(session, scoped.scope(), owner="study_design").save(
        project_id, content={**DESIGN, "n": 1}, reason="design:run"
    )
    assert repo.latest() is not None and repo.latest().workspace_revision is None  # type: ignore[union-attr]
    assert repo.latest().revision == legacy.revision  # type: ignore[union-attr]
    current, created = repo.submit_as_working_copy(content={**DESIGN, "n": 1}, source_stage="run")
    assert created and current.revision == legacy.revision + 1
    assert current.workspace_revision is not None
    assert first.workspace_revision is not None
