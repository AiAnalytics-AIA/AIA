"""Every whole-copy write of the working copy is logged and cannot change a locked item
(working-copy-edit-ops WCE2c; ADR 0029 decisions 3 and 8).

The PUT's save (a person, ``ui``), a server-authored copy (``submit_as_working_copy``,
``authored``) and a reuse (``reuse``) each leave one ``workspace_edit_ops`` row per field they
changed, in the transaction that writes the revision, under the person's own id. A write that
changes a declared Sociomap input of the current copy is refused whole, after the stale check.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.research_template import research_template
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from aia_core.infrastructure.workspace_edit_repository import WorkspaceEditRepository


def _design(*, declared: bool = False) -> dict[str, Any]:
    content = research_template()
    content["sections"] = [
        {
            "id": "sec_a",
            "type": "questions",
            "questions": [
                {"id": "Q1", "text": "Jak často?", "typ": "skala", "skala": [1, 5]},
                {"id": "Q2", "text": "Kde nakupujete?", "typ": "vyber", "kategorie": ["A", "B"]},
            ],
        }
    ]
    if declared:
        content["sections"][0]["questions"][0]["sociomap_rating"] = True
    return content


def _person(scope: Any) -> WriteBy:
    return WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI)


def test_a_persons_save_is_logged_field_by_field_under_their_id(scoped: Any, session: Any) -> None:
    scope = scoped.scope(user="lead")
    workspaces = StudyWorkspaceRepository(session)
    first = workspaces.save(scope, content=_design(), base_revision=None, by=_person(scope))
    edited = _design()
    edited["sections"][0]["questions"][1]["text"] = "Kde kupujete?"
    second = workspaces.save(scope, content=edited, base_revision=first.revision, by=_person(scope))
    log = WorkspaceEditRepository(session, scope)
    rows = log.rows(after_revision=first.revision)
    assert [(r.item_key, r.field) for r in rows] == [("content:question:Q2", "text")]
    (row,) = rows
    assert (row.base_revision, row.result_revision) == (first.revision, second.revision)
    assert row.by == WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI)
    assert row.op == {"op": "whole_copy", "reason": "autosave"}
    # The first save wrote every item it created, from no copy.
    assert {r.base_revision for r in log.rows() if r.result_revision == first.revision} == {None}


def test_a_save_that_changes_nothing_writes_no_revision_and_no_row(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope(user="lead")
    workspaces = StudyWorkspaceRepository(session)
    first = workspaces.save(scope, content=_design(), base_revision=None, by=_person(scope))
    again = workspaces.save(
        scope, content=_design(), base_revision=first.revision, by=_person(scope)
    )
    assert again.deduplicated
    assert WorkspaceEditRepository(session, scope).rows(after_revision=first.revision) == []


def test_a_save_cannot_change_a_declared_sociomap_input(scoped: Any, session: Any) -> None:
    scope = scoped.scope(user="lead")
    workspaces = StudyWorkspaceRepository(session)
    first = workspaces.save(
        scope, content=_design(declared=True), base_revision=None, by=_person(scope)
    )
    session.commit()  # the request that declared the input has ended
    locked = _design(declared=True)
    locked["sections"][0]["questions"][0]["text"] = "Jak moc často?"
    with pytest.raises(WorkspaceConflict) as refused:
        workspaces.save(scope, content=locked, base_revision=first.revision, by=_person(scope))
    assert refused.value.reason == "sociomap_input_locked"
    assert refused.value.current_revision == first.revision
    session.rollback()
    # Nothing was written: the copy and the log are as they were.
    assert workspaces.content(scope).revision == first.revision
    assert WorkspaceEditRepository(session, scope).rows(after_revision=first.revision) == []
    # A change to anything the map does not read is saved.
    free = _design(declared=True)
    free["sections"][0]["questions"][1]["text"] = "Kde kupujete?"
    saved = workspaces.save(scope, content=free, base_revision=first.revision, by=_person(scope))
    assert saved.revision == first.revision + 1


def test_a_stale_save_is_refused_as_stale_before_the_lock(scoped: Any, session: Any) -> None:
    scope = scoped.scope(user="lead")
    workspaces = StudyWorkspaceRepository(session)
    first = workspaces.save(
        scope, content=_design(declared=True), base_revision=None, by=_person(scope)
    )
    other = copy.deepcopy(_design(declared=True))
    other["title"] = "Jiný název"
    workspaces.save(scope, content=other, base_revision=first.revision, by=_person(scope))
    locked = _design(declared=True)
    locked["sections"][0]["questions"][0]["text"] = "Jak moc často?"
    with pytest.raises(WorkspaceConflict) as refused:
        workspaces.save(scope, content=locked, base_revision=first.revision, by=_person(scope))
    assert refused.value.reason == "stale_revision"


def test_a_server_authored_copy_is_logged_as_authored(scoped: Any, session: Any) -> None:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=_design(), source_stage="run"
    )
    rows = WorkspaceEditRepository(session, scope).rows()
    assert rows and {r.result_revision for r in rows} == {revision.workspace_revision}
    assert {r.by for r in rows} == {WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.AUTHORED)}


def test_the_bare_template_a_server_saved_is_still_overwritten_from_no_revision(
    scoped: Any, session: Any
) -> None:
    """OI-173 holds with the log: a browser that loaded the study EMPTY saves over the template
    a server writer saved, and its rows name no base revision."""
    scope = scoped.scope(user="lead")
    StudyDesignRepository(session, scope).submit_as_working_copy(
        content=research_template(), source_stage="brief"
    )
    workspaces = StudyWorkspaceRepository(session)
    template = workspaces.content(scope).revision
    saved = workspaces.save(scope, content=_design(), base_revision=None, by=_person(scope))
    rows = WorkspaceEditRepository(session, scope).rows(after_revision=template)
    assert rows and {(r.base_revision, r.result_revision) for r in rows} == {(None, saved.revision)}
