"""The study workspace bridge (ADR 0015 decision 5, OI-58): temporary migration debt.

A study's working content may live in the unit's store only behind an AIA-owned
binding that is reached through the study's scope. These tests pin the rules
that keep the bridge from becoming the data model or a way around scope.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from aia_core.domain.scope import ScopeDenied, StudyStatus
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)


@pytest.fixture
def workspaces(session: Any) -> StudyWorkspaceRepository:
    return StudyWorkspaceRepository(session)


def test_a_study_is_bound_once_and_read_through_its_scope(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    assert workspaces.get(lead) is None
    bound = workspaces.bind(lead, unit_project_id="PRJ-abc123")
    assert bound.unit_project_id == "PRJ-abc123"
    assert workspaces.bind(lead, unit_project_id="PRJ-abc123") == bound
    with pytest.raises(WorkspaceConflict) as conflict:
        workspaces.bind(lead, unit_project_id="PRJ-other")
    assert conflict.value.reason == "study_already_bound"
    assert workspaces.get(scoped.scope(user="viewer")) == bound


def test_a_unit_project_bound_to_one_study_cannot_be_bound_to_another(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    workspaces.bind(scoped.scope(), unit_project_id="PRJ-shared")
    # Not even the same client's sibling study, and certainly not another client's.
    with pytest.raises(WorkspaceConflict) as sibling:
        workspaces.bind(scoped.scope(study="sibling"), unit_project_id="PRJ-shared")
    assert sibling.value.reason == "unit_project_taken"
    with pytest.raises(WorkspaceConflict):
        workspaces.bind(
            scoped.scope(user="other_lead", study="other_client"), unit_project_id="PRJ-shared"
        )


def test_a_unit_project_id_is_never_a_way_into_a_study(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    workspaces.bind(scoped.scope(), unit_project_id="PRJ-acme")
    # Another client's lead, in their own study's scope, reads nothing of Acme's binding.
    assert workspaces.get(scoped.scope(user="other_lead", study="other_client")) is None
    # And cannot even resolve Acme's study to ask.
    with pytest.raises(ScopeDenied):
        scoped.scope(user="other_lead", study="primary")
    # No method takes a unit project id to find a study: every read is keyed by an issued scope.
    for name, method in inspect.getmembers(StudyWorkspaceRepository, inspect.isfunction):
        if name.startswith("_") or name == "bind":
            continue
        assert "unit_project_id" not in inspect.signature(method).parameters, name


def test_binding_needs_edit_rights_on_an_open_study(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    for user in ("viewer", "reviewer"):
        with pytest.raises(ScopeDenied):
            workspaces.bind(scoped.scope(user=user), unit_project_id=f"PRJ-{user}")
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        workspaces.bind(scoped.scope(), unit_project_id="PRJ-late")
    assert closed.value.reason == "study_closed"


def test_a_unit_project_id_must_look_like_one(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    for bad in ("", "PRJ/../x", "a b", "x" * 161):
        with pytest.raises(ValueError):
            workspaces.bind(scoped.scope(), unit_project_id=bad)


def test_the_last_stage_is_remembered_by_editors_only(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    assert workspaces.record_stage(lead, stage="plan") is None  # nothing bound yet
    workspaces.bind(lead, unit_project_id="PRJ-stage")
    assert workspaces.record_stage(lead, stage="questionnaire").last_stage == "questionnaire"  # type: ignore[union-attr]
    assert (
        workspaces.record_stage(scoped.scope(user="viewer"), stage="brief").last_stage
        == "questionnaire"
    )  # type: ignore[union-attr]
    with pytest.raises(ValueError):
        workspaces.record_stage(lead, stage="../etc")


def test_a_clients_workspaces_are_only_the_studies_its_scope_opens(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    workspaces.bind(scoped.scope(), unit_project_id="PRJ-a")
    workspaces.bind(scoped.scope(study="sibling"), unit_project_id="PRJ-b")
    workspaces.bind(scoped.scope(user="other_lead", study="other_client"), unit_project_id="PRJ-c")
    acme = scoped.resolver.client_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients["primary"].client_id
    )
    assert {w.unit_project_id for w in workspaces.in_client(acme).values()} == {"PRJ-a", "PRJ-b"}
