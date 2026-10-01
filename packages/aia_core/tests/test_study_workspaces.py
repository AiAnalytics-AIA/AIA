"""A research Study's working content, stored in AIA (ADR 0018, OI-58).

The stages save one document per Study every few seconds. These tests pin the
rules that keep that store the Study's own: read and written only through an issued
scope, never found by a project id or an 18.6.6 unit id, refused from a stale copy
instead of silently overwriting a newer save, and never editable while the Study's
content still waits to be migrated from 18.6.6. The brief's attachments follow the
same rules: kept in AIA's storage on the working project, served only through the
Study.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.attachments import (
    ATTACHMENT_ARTIFACT_TYPE,
    ATTACHMENT_MAX_BYTES,
    ATTACHMENT_STAGE,
    CONTEXT_EXCERPT_CHARS,
    AttachmentRejected,
    attachment_record,
    content_type_of,
    safe_filename,
    validate_attachment,
)
from aia_core.domain.scope import ScopeDenied, StudyStatus
from aia_core.domain.workspace import (
    WORKING_CONTENT_MAX_BYTES,
    WORKSPACE_PROJECT_OWNER,
    ContentState,
    WorkspaceRejected,
    validate_working_content,
)
from aia_core.infrastructure.artifact_repository import ArtifactNotFound, ArtifactRepository
from aia_core.infrastructure.repositories import ProjectNotFound, ProjectRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
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


def test_everyone_with_the_study_saves_while_it_is_open_and_nobody_once_it_is_closed(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    """ADR 0019: one role, so every person who opens the study edits it.

    The viewer and the reviewer were refused a save before it. What still bounds a save:
    a person with no grant cannot open the study, and a closed study is not editable.
    """
    revision: int | None = None
    for user in ("viewer", "reviewer", "researcher", "lead"):
        saved = workspaces.save(
            scoped.scope(user=user), content={**BRIEF, "title": user}, base_revision=revision
        )
        revision = saved.revision
    assert workspaces.content(scoped.scope(user="viewer")).content["title"] == "lead"
    with pytest.raises(ScopeDenied):
        scoped.scope(user="outsider")
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as closed:
        workspaces.save(scoped.scope(), content=BRIEF, base_revision=revision)
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


def test_the_last_stage_is_remembered_for_whoever_opens_the_study(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    assert workspaces.record_stage(lead, stage="brief") is None  # nothing saved yet
    workspaces.save(lead, content=BRIEF, base_revision=None)
    assert workspaces.record_stage(lead, stage="plan").last_stage == "plan"
    # ADR 0019: the former viewer edits like anyone else, so the stage they open is remembered.
    viewer = scoped.scope(user="viewer")
    assert workspaces.record_stage(viewer, stage="audience").last_stage == "audience"
    with pytest.raises(ScopeDenied):
        scoped.scope(user="outsider")
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


# -- attachments ---------------------------------------------------------------

DOCX = (
    Path(__file__).parent / "fixtures" / "attachment_text" / "inputs" / "zadani.docx"
).read_bytes()


def test_an_attachment_is_kept_in_aia_storage_on_the_working_project(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    lead = scoped.scope()
    store = InMemoryArtifactStore()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    record = workspaces.attach(lead, store, filename="Zadání klienta.docx", data=DOCX)
    # The unit's record, with the unit's name reduction and the unit's excerpt.
    assert record.kind == "file"
    assert record.filename == "Zad_n_ klienta.docx"
    assert (record.extension, record.size_bytes) == (".docx", len(DOCX))
    assert record.sha256 == hashlib.sha256(DOCX).hexdigest()
    assert record.text_extracted is True
    assert record.context_excerpt.startswith("Zadání výzkumu: fiktivní ranní nápoj")
    assert record.attachment_id.startswith("ART-")

    artifact, data = workspaces.attachment(scoped.scope(user="viewer"), store, record.attachment_id)
    assert data == DOCX
    assert (artifact.stage_type, artifact.artifact_type) == (
        ATTACHMENT_STAGE,
        ATTACHMENT_ARTIFACT_TYPE,
    )
    assert artifact.metadata["filename"] == record.filename
    ws = workspaces.get(lead)
    assert ws is not None and artifact.project_id == ws.project_id
    assert artifact.produced_by_user_id == lead.actor_id
    # Nothing in the brief changed: the stage adds the record and saves.
    assert workspaces.content(lead).revision == 1
    # The bytes sit under the Study's own storage prefix.
    assert f"/{lead.study_id}/" in artifact.storage_key


def test_a_file_that_cannot_be_read_is_kept_and_says_so(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    lead = scoped.scope()
    store = InMemoryArtifactStore()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    record = workspaces.attach(lead, store, filename="foto.png", data=b"\x89PNG not really")
    assert (record.text_extracted, record.context_excerpt) == (False, "")
    assert workspaces.attachment(lead, store, record.attachment_id)[1] == b"\x89PNG not really"


def test_nothing_is_attached_to_a_study_without_saved_content_or_awaiting_migration(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    store = InMemoryArtifactStore()
    with pytest.raises(WorkspaceConflict) as unsaved:
        workspaces.attach(scoped.scope(), store, filename="a.txt", data=b"text")
    assert unsaved.value.reason == "not_saved"
    _awaiting(session, scoped, study="sibling")
    with pytest.raises(WorkspaceConflict) as waiting:
        workspaces.attach(scoped.scope(study="sibling"), store, filename="a.txt", data=b"text")
    assert waiting.value.reason == "awaiting_migration"
    assert store._objects == {}


def test_everyone_with_an_open_study_attaches_and_the_file_is_checked_first(
    scoped: Any, workspaces: StudyWorkspaceRepository
) -> None:
    store = InMemoryArtifactStore()
    workspaces.save(scoped.scope(), content=BRIEF, base_revision=None)
    # ADR 0019: the former viewer and reviewer attach like anyone else.
    for user in ("viewer", "reviewer"):
        record = workspaces.attach(scoped.scope(user=user), store, filename="a.txt", data=b"x")
        _, data = workspaces.attachment(scoped.scope(), store, record.attachment_id)
        assert data == b"x"
    store = InMemoryArtifactStore()  # the checks below must leave nothing in a store
    with pytest.raises(ScopeDenied):
        scoped.scope(user="outsider")
    for data, reason in ((b"", "empty"), (b"x" * (ATTACHMENT_MAX_BYTES + 1), "too_large")):
        with pytest.raises(AttachmentRejected) as rejected:
            workspaces.attach(scoped.scope(), store, filename="a.txt", data=data)
        assert rejected.value.reason == reason
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied):
        workspaces.attach(scoped.scope(), store, filename="a.txt", data=b"x")
    assert store._objects == {}


def test_an_attachment_is_served_only_through_its_own_study(
    scoped: Any, workspaces: StudyWorkspaceRepository, session: Any
) -> None:
    store = InMemoryArtifactStore()
    lead = scoped.scope()
    workspaces.save(lead, content=BRIEF, base_revision=None)
    record = workspaces.attach(lead, store, filename="a.txt", data=b"primary")
    workspaces.save(scoped.scope(study="sibling"), content=BRIEF, base_revision=None)
    for other in (
        scoped.scope(study="sibling"),
        scoped.scope(user="other_lead", study="other_client"),
    ):
        with pytest.raises(ArtifactNotFound):
            workspaces.attachment(other, store, record.attachment_id)
    # Neither the generic project routes nor a run's artifact reader can see it.
    with pytest.raises(ArtifactNotFound):
        ArtifactRepository(session, lead, store).get(record.attachment_id)
    with pytest.raises(ArtifactNotFound):
        ArtifactRepository(session, lead, store, owner="study_design").get(record.attachment_id)
    # And an artifact of the working project that is not an attachment is not served as one.
    ws = workspaces.get(lead)
    assert ws is not None and ws.project_id is not None
    other_kind, _ = ArtifactRepository(session, lead, store, owner=WORKSPACE_PROJECT_OWNER).put(
        project_id=ws.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="SOMETHING_ELSE",
        data=b"{}",
    )
    with pytest.raises(ArtifactNotFound):
        workspaces.attachment(lead, store, other_kind.artifact_id)


def test_an_attachments_name_is_reduced_exactly_as_the_unit_reduced_it() -> None:
    """``ui_server.py:1024-1026``: Path(name).name, then the unsafe characters, then 160."""
    cases = {
        "zadani.pdf": "zadani.pdf",
        "Zadání klienta (v2).docx": "Zad_n_ klienta _v2_.docx",
        "../../etc/passwd": "passwd",
        "C:\\fakepath\\brief.txt": "C_fakepath_brief.txt",
        "": "attachment",
        "ěščř": "_",
        "a" * 200 + ".txt": "a" * 160,
        " mezera.txt": " mezera.txt",
    }
    for raw, expected in cases.items():
        assert safe_filename(raw) == expected, raw
    assert validate_attachment("x.csv", b"a;b") == "x.csv"
    record = attachment_record(
        attachment_id="ART-1", filename="x.pdf", size_bytes=3, sha256="s", text="t" * 7000
    )
    assert (record.content_type, record.text_extracted) == ("application/pdf", True)
    assert len(record.context_excerpt) == CONTEXT_EXCERPT_CHARS
    assert content_type_of("x.unknown") == "application/octet-stream"
