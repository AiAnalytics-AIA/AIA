"""A research Study's working content, stored in AIA (ADR 0018, OI-58).

The stages save one document per Study every few seconds. These tests pin the
rules that keep that store the Study's own: read and written only through an issued
scope, never found by a project id or an 18.6.6 unit id, refused from a stale copy
instead of silently overwriting a newer save, and never editable while the Study's
content still waits to be migrated from 18.6.6.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from aia_core.domain.scope import ScopeDenied, StudyStatus
from aia_core.domain.workspace import (
    WORKING_CONTENT_MAX_BYTES,
    WORKSPACE_PROJECT_OWNER,
    ContentState,
    WorkspaceRejected,
    validate_working_content,
)
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from aia_core.infrastructure.tables import ProjectRow, StudyWorkspaceRow

BRIEF = {"title": "Vnímání značky", "goal": "Zjistit, co lidé o značce vědí", "sections": []}


@pytest.fixture
def workspaces(session: Any) -> StudyWorkspaceRepository:
    return StudyWorkspaceRepository(session)


def _awaiting(session: Any, scoped: Any, *, study: str = "primary", unit: str = "PRJ-old") -> None:
    """A Study bound to an 18.6.6 project before ADR 0018, as the migration leaves it."""
    s = scoped.studies[study]
    session.add(
        StudyWorkspaceRow(
            study_id=s.study_id,
            organization_id=scoped.organization_id,
            client_id=s.client_id,
            content_state=ContentState.AWAITING_MIGRATION.value,
            unit_project_id=unit,
            lineage={},
            bound_by=scoped.users["lead"],
        )
    )
    session.flush()


def test_a_new_study_is_empty_and_its_first_save_creates_its_working_project(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    lead = scoped.scope()
    empty = workspaces.content(lead)
    assert empty.state is ContentState.EMPTY
    assert (empty.revision, empty.content, empty.analysis) == (None, None, None)

    saved = workspaces.save(lead, content=BRIEF, base_revision=None, reason="autosave")
    assert (saved.state, saved.revision, saved.deduplicated) == (ContentState.NATIVE, 1, False)
    assert saved.revision_id.startswith("REV-")

    loaded = workspaces.content(lead)
    assert loaded.state is ContentState.NATIVE
    assert loaded.revision == 1
    assert loaded.content == BRIEF
    assert loaded.saved_by == lead.actor_id
    ws = workspaces.get(lead)
    assert ws is not None and ws.project_id is not None and ws.unit_project_id is None
    project = session.get(ProjectRow, ws.project_id)
    assert project.owner == WORKSPACE_PROJECT_OWNER
    assert project.study_id == lead.study_id and project.client_id == lead.client_id


def test_each_change_is_a_revision_and_an_unchanged_save_writes_nothing(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    second = workspaces.save(lead, content={**BRIEF, "goal": "Jinak"}, base_revision=1)
    assert (second.revision, second.deduplicated) == (2, False)
    same = workspaces.save(lead, content={**BRIEF, "goal": "Jinak"}, base_revision=2)
    assert (same.revision, same.deduplicated, same.revision_id) == (2, True, second.revision_id)
    history = workspaces.revisions(lead)
    assert [r.revision for r in history] == [2, 1]
    assert history[0].parent_revision == 1
    assert history[0].reason == "autosave"


def test_an_analysis_that_changed_is_saved_even_when_the_document_did_not(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    saved = workspaces.save(
        lead, content=BRIEF, analysis={"summary": "rozbor"}, base_revision=1, reason="ai_analysis"
    )
    assert (saved.revision, saved.deduplicated) == (2, False)
    loaded = workspaces.content(lead)
    assert loaded.analysis == {"summary": "rozbor"}
    assert loaded.content == BRIEF


def test_a_save_from_a_stale_copy_is_refused_and_says_what_is_current(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    researcher = scoped.scope(user="researcher")
    workspaces.save(lead, content=BRIEF, base_revision=None)
    workspaces.save(researcher, content={**BRIEF, "goal": "Druhý editor"}, base_revision=1)
    with pytest.raises(WorkspaceConflict) as stale:
        workspaces.save(lead, content={**BRIEF, "goal": "První editor"}, base_revision=1)
    assert stale.value.reason == "stale_revision"
    assert stale.value.current_revision == 2
    # A blind save over existing content is a stale save too.
    with pytest.raises(WorkspaceConflict):
        workspaces.save(lead, content=BRIEF, base_revision=None)
    assert workspaces.content(lead).content == {**BRIEF, "goal": "Druhý editor"}


def test_content_awaiting_migration_is_named_and_not_editable(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    _awaiting(session, scoped)
    lead = scoped.scope()
    waiting = workspaces.content(lead)
    assert waiting.state is ContentState.AWAITING_MIGRATION
    assert waiting.content is None
    with pytest.raises(WorkspaceConflict) as refused:
        workspaces.save(lead, content=BRIEF, base_revision=None)
    assert refused.value.reason == "awaiting_migration"
    ws = workspaces.get(lead)
    assert ws is not None and ws.unit_project_id == "PRJ-old" and ws.project_id is None


def test_an_unrecoverable_study_starts_again_only_by_a_save_and_keeps_the_record(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    s = scoped.studies["primary"]
    session.add(
        StudyWorkspaceRow(
            study_id=s.study_id,
            organization_id=scoped.organization_id,
            client_id=s.client_id,
            content_state=ContentState.UNRECOVERABLE.value,
            unit_project_id="PRJ-gone",
            lineage={"source": "npc-panel-18.6.6", "outcome": "unit project missing"},
            bound_by=scoped.users["lead"],
        )
    )
    session.flush()
    lead = scoped.scope()
    assert workspaces.content(lead).state is ContentState.UNRECOVERABLE
    saved = workspaces.save(lead, content=BRIEF, base_revision=None)
    assert saved.state is ContentState.NATIVE
    lineage = workspaces.content(lead).lineage
    assert lineage["outcome"] == "unit project missing"
    assert lineage["restarted_after_unrecoverable"]["by"] == lead.actor_id


def test_only_editors_of_an_open_research_study_save(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    for user in ("viewer", "reviewer"):
        with pytest.raises(ScopeDenied):
            workspaces.save(scoped.scope(user=user), content=BRIEF, base_revision=None)
    workspaces.save(scoped.scope(), content=BRIEF, base_revision=None)
    # A reader reads what the editors saved.
    assert workspaces.content(scoped.scope(user="viewer")).content == BRIEF
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        workspaces.save(scoped.scope(), content=BRIEF, base_revision=1)
    assert closed.value.reason == "study_closed"


def test_a_study_never_reads_another_studys_content(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    workspaces.save(scoped.scope(), content=BRIEF, base_revision=None)
    assert workspaces.content(scoped.scope(study="sibling")).state is ContentState.EMPTY
    assert (
        workspaces.content(scoped.scope(user="other_lead", study="other_client")).state
        is ContentState.EMPTY
    )
    with pytest.raises(ScopeDenied):
        scoped.scope(user="other_lead", study="primary")
    # No method takes a project or unit project id to find a study.
    for name, method in inspect.getmembers(StudyWorkspaceRepository, inspect.isfunction):
        if name.startswith("_"):
            continue
        params = inspect.signature(method).parameters
        assert "unit_project_id" not in params and "project_id" not in params, name


def test_the_working_project_is_invisible_to_the_generic_project_routes(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    ws = workspaces.get(lead)
    assert ws is not None and ws.project_id is not None
    ordinary = ProjectRepository(workspaces._session, lead)
    assert ordinary.list_projects().total == 0
    with pytest.raises(ProjectNotFound):
        ordinary.get(ws.project_id)


def test_content_is_checked_before_it_is_stored(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    for bad, reason in (
        ([], "content_not_object"),
        ({}, "content_empty"),
        ({"title": "x", "client_id": "CLI-other"}, "content_carries_scope"),
    ):
        with pytest.raises(WorkspaceRejected) as rejected:
            workspaces.save(lead, content=bad, base_revision=None)
        assert rejected.value.reason == reason
    with pytest.raises(WorkspaceRejected) as not_object:
        workspaces.save(lead, content=BRIEF, analysis=["x"], base_revision=None)
    assert not_object.value.reason == "analysis_not_object"
    with pytest.raises(WorkspaceRejected) as reason_bad:
        workspaces.save(lead, content=BRIEF, base_revision=None, reason="Not A Reason!")
    assert reason_bad.value.reason == "bad_reason"
    assert workspaces.content(lead).state is ContentState.EMPTY


def test_the_size_limit_counts_content_and_analysis_together() -> None:
    half = "x" * (WORKING_CONTENT_MAX_BYTES // 2)
    validate_working_content({"a": half[:-100]})
    with pytest.raises(WorkspaceRejected) as big:
        validate_working_content({"a": half}, {"b": half})
    assert big.value.reason == "content_too_large"
    with pytest.raises(WorkspaceRejected) as nan:
        validate_working_content({"a": float("nan")})
    assert nan.value.reason == "content_not_json"


def test_the_last_stage_is_remembered_by_editors_only(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    assert workspaces.record_stage(lead, stage="brief") is None  # nothing saved yet
    workspaces.save(lead, content=BRIEF, base_revision=None)
    assert workspaces.record_stage(lead, stage="plan").last_stage == "plan"
    viewer = scoped.scope(user="viewer")
    assert workspaces.record_stage(viewer, stage="audience").last_stage == "plan"
    with pytest.raises(ValueError):
        workspaces.record_stage(lead, stage="nonsense")


def test_a_clients_workspaces_are_only_the_studies_its_scope_opens(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    workspaces.save(scoped.scope(), content=BRIEF, base_revision=None)
    workspaces.save(scoped.scope(study="sibling"), content=BRIEF, base_revision=None)
    workspaces.save(
        scoped.scope(user="other_lead", study="other_client"), content=BRIEF, base_revision=None
    )
    lead = scoped.resolver.client_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients["primary"].client_id
    )
    seen = workspaces.in_client(lead)
    assert set(seen) == {scoped.studies["primary"].study_id, scoped.studies["sibling"].study_id}
    assert all(w.state is ContentState.NATIVE for w in seen.values())
