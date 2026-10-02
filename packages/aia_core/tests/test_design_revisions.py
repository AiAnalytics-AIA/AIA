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
    revision, created = repo.submit(content=DESIGN, source_stage="run")
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
    first, _ = repo.submit(content=DESIGN, source_stage="persona")
    again, created = repo.submit(content=dict(DESIGN), source_stage="run")
    assert not created and again.revision_id == first.revision_id
    edited, created = repo.submit(content={**DESIGN, "n": 500}, source_stage="persona")
    assert created and edited.revision == 2 and edited.parent_revision == 1
    # The revision under an existing run never changes.
    assert repo.content(first.revision_id)["n"] == 450
    assert [r.revision for r in repo.revisions()] == [2, 1]
    assert repo.latest() == edited


def test_content_never_carries_authority(scoped: Any, designs: Any) -> None:
    repo = designs()
    for key in ("client_id", "study_id", "organization_id", "Actor_ID"):
        with pytest.raises(DesignRejected) as refused:
            repo.submit(content={**DESIGN, key: "CLI-other"}, source_stage="run")
        assert refused.value.reason == "design_carries_scope"
    # The unit store's own ids are data, not identity: stored as submitted, trusted for nothing.
    revision, _ = repo.submit(content={**DESIGN, "project_id": "PRJ-unit"}, source_stage="run")
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
        _, created = designs(user=user).submit(content={**DESIGN, "n": i + 1}, source_stage="run")
        assert created, user
    # A member who was never granted the study submits like the others (ADR 0019).
    _, created = designs(user="outsider").submit(content={**DESIGN, "n": 4}, source_stage="run")
    assert created
    with pytest.raises(DesignRejected):
        designs().submit(content=DESIGN, source_stage="results")
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        designs().submit(content={**DESIGN, "n": 99}, source_stage="run")
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
        designs(study="simulation").submit(content=DESIGN, source_stage="run")
    assert refused.value.reason == "not_research"


def test_a_revision_is_reachable_only_through_its_own_study(scoped: Any, designs: Any) -> None:
    acme, _ = designs().submit(content=DESIGN, source_stage="run")
    # Each study has a design of its own, so only the Study filter can refuse Acme's id.
    designs(study="sibling").submit(content={**DESIGN, "n": 1}, source_stage="run")
    designs(user="other_lead", study="other_client").submit(content=DESIGN, source_stage="run")
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
    first, _ = repo.submit(content=DESIGN, source_stage="run")
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
    revision, _ = designs().submit(content=DESIGN, source_stage="run")
    row = session.scalars(
        select(ProjectRevisionRow).where(ProjectRevisionRow.revision_id == revision.revision_id)
    ).one()
    row.content = {**DESIGN, "n": 1}
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()
