"""The explicit migration of Studies' working content out of 18.6.6 (ADR 0018, decision 2).

The copies these tests read are written the way the unit writes its store
(``tests/unit_store.py``: the unit's own schema and migrations, read from its source
as text; its hashing; its file names and records). They pin what the migration
promises: every revision one for one, every file in AIA storage or reported, the
Study's identity and ownership kept, nothing done around the operator's own grants,
nothing written by a dry run or by a Study that does not validate, a project missing
from a copy never declared lost until the operator says the copy is complete, and a
second run that changes nothing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from aia_core.application.workspace_migration import (
    RECOVERED_REASON,
    MigrationRefused,
    migrate_unit_workspaces,
)
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.scope import StudyStatus
from aia_core.domain.workspace import LEGACY_SOURCE, SAVE_REASON, ContentState
from aia_core.domain.workspace_migration import (
    MIGRATION_VERSION,
    MigratedFile,
    MigrationOutcome,
    MigrationReport,
    UnitAttachment,
    UnitProject,
    UnitRevision,
    file_refs,
    migrated_reason,
    rewrite_attachments,
    source_problems,
    validate_migration,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    ProjectArtifactRow,
    ProjectEventRow,
    ProjectRevisionRow,
    ProjectRow,
    StudyWorkspaceRow,
    UserRow,
)
from aia_core.infrastructure.unit_project_store import UnitAttachmentFiles, UnitProjectStore

REPO = Path(__file__).resolve().parents[3]
PRJ = "PRJ-0a1b2c3d4e5f60"
LEAD = "lead@art-chain.io"


# --------------------------------------------------------------------------- #
# The rules (pure)
# --------------------------------------------------------------------------- #


def _record(n: int, **extra: Any) -> dict[str, Any]:
    aid = f"ATT-{n:014x}"
    return {
        "attachment_id": aid,
        "filename": f"soubor-{n}.txt",
        "stored_name": f"{aid}_soubor-{n}.txt",
        "size_bytes": 10 + n,
        "sha256": f"{n:064x}",
        "kind": "file",
        "extension": ".txt",
        "text_extracted": True,
        "context_excerpt": f"text {n}",
        "project_id": PRJ,
        "download_url": f"/project-attachments/{aid}_soubor-{n}.txt",
        **extra,
    }


def _rev(revision: int, attachments: list[Any], **content: Any) -> UnitRevision:
    body = {"title": "Fiktivní", "briefing": {"attachments": attachments}, **content}
    return UnitRevision(
        revision=revision,
        revision_id=f"REV-{revision:016x}",
        created_at="2026-09-20T10:00:00",
        reason="autosave",
        content_sha256=fingerprint(body),
        content=body,
        analysis={},
    )


def _project(revisions: list[UnitRevision], attachments: list[UnitAttachment] = ()) -> UnitProject:  # type: ignore[assignment]
    return UnitProject(
        project_id=PRJ,
        title="Fiktivní",
        project_type="research",
        status="DRAFT",
        current_revision=len(revisions),
        deleted_at=None,
        revisions=tuple(revisions),
        attachments=tuple(attachments),
    )


def test_each_unit_file_is_brought_once_first_those_a_brief_named() -> None:
    one, two = _record(1), _record(2, stored_name="", sha256="")
    url = {"kind": "url", "url": "https://example.invalid/", "attachment_id": "ATT-00000000000009"}
    native = {**_record(3), "attachment_id": "ART-0123456789abcdef"}
    bound_two = UnitAttachment(
        attachment_id=two["attachment_id"],
        filename="soubor-2.txt",
        stored_name="ATT-00000000000002_soubor-2.txt",
        sha256="b" * 64,
        size_bytes=12,
        revision=2,
        created_at=None,
    )
    bound_only = UnitAttachment(
        attachment_id="ATT-00000000000004",
        filename="jen-navazany.pdf",
        stored_name="ATT-00000000000004_jen-navazany.pdf",
        sha256="c" * 64,
        size_bytes=40,
        revision=None,
        created_at=None,
    )
    project = _project(
        [_rev(1, [url, native]), _rev(2, [one]), _rev(3, [two, one])],
        [bound_only, bound_two],
    )
    refs = file_refs(project)
    assert [r.attachment_id for r in refs] == [
        one["attachment_id"],
        two["attachment_id"],
        "ATT-00000000000004",
    ]
    assert [(r.first_revision, r.named_in_brief) for r in refs] == [
        (2, True),
        (3, True),
        (3, False),
    ]
    # A brief record without its stored name or hash takes them from the unit's binding.
    assert (refs[1].stored_name, refs[1].sha256) == (bound_two.stored_name, "b" * 64)
    # Only a download URL: the stored name is the URL's last part, unquoted.
    by_url = file_refs(_project([_rev(1, [_record(5, stored_name="")])]))
    assert by_url[0].stored_name == "ATT-00000000000005_soubor-5.txt"


def test_a_migrated_record_names_its_artifact_and_forgets_the_units_storage() -> None:
    kept, gone = _record(1), _record(2)
    url = {"kind": "url", "url": "https://example.invalid/"}
    content = {"title": "T", "briefing": {"attachments": [kept, gone, url], "situation": "s"}}
    migrated = {
        kept["attachment_id"]: MigratedFile(
            attachment_id=kept["attachment_id"],
            artifact_id="ART-00000000000000aa",
            filename="soubor-1.txt",
            sha256=kept["sha256"],
            size_bytes=11,
            named_in_brief=True,
        )
    }
    out = rewrite_attachments(content, migrated)
    first, second, third = out["briefing"]["attachments"]
    assert first == {
        **{k: v for k, v in kept.items() if k not in ("download_url", "stored_name", "project_id")},
        "attachment_id": "ART-00000000000000aa",
        "legacy_attachment_id": kept["attachment_id"],
    }
    # A file that did not come over keeps its record exactly: the brief still says it
    # was attached, and the stage says it is not in AIA.
    assert second == gone and third == url
    assert out["briefing"]["situation"] == "s"
    assert content["briefing"]["attachments"][0] == kept  # the source is not changed
    assert rewrite_attachments({"title": "T"}, migrated) == {"title": "T"}


def test_a_migrated_revision_keeps_the_units_reason_within_the_save_rule() -> None:
    for unit, expected in (
        ("autosave", "unit:autosave"),
        ("project_created", "unit:project_created"),
        ("AI analýza!", "unit:ai_anal_za"),
        ("", "unit:saved"),
        ("x" * 200, "unit:" + "x" * 54),
    ):
        assert migrated_reason(unit) == expected
        assert SAVE_REASON.fullmatch(migrated_reason(unit))


def test_a_copy_that_is_not_what_the_unit_wrote_is_refused_before_anything_is_written() -> None:
    good = _rev(1, [])
    assert source_problems(_project([good])) == []
    forged = good.model_copy(update={"content_sha256": "0" * 64})
    assert "does not hash" in source_problems(_project([forged]))[0]
    scoped = _rev(2, [], study_id="STU-elsewhere")
    assert "content_carries_scope" in source_problems(_project([good, scoped]))[0]
    big = _rev(3, [], blob="x" * (2 * 1024 * 1024))
    assert "content_too_large" in source_problems(_project([big]))[0]


def test_a_migration_holds_only_when_every_revision_is_there_in_order() -> None:
    revisions = [_rev(1, []), _rev(2, [_record(1)])]
    written = [(i, fingerprint(r.content), {}) for i, r in enumerate(revisions, start=1)]
    assert validate_migration(revisions, written, {}) == []
    assert "1 written" in validate_migration(revisions, written[:1], {})[0]
    swapped = [written[1], written[0]]
    problems = validate_migration(revisions, swapped, {})
    assert any("written as AIA revision 2, not 1" in p for p in problems)
    assert any("content differs" in p for p in problems)
    bad_analysis = [written[0], (2, written[1][1], {"x": 1})]
    assert validate_migration(revisions, bad_analysis, {}) == [
        "unit revision 2: analysis differs from the unit's"
    ]


# --------------------------------------------------------------------------- #
# Reading the copy
# --------------------------------------------------------------------------- #


@pytest.fixture
def unit(tmp_path: Path, unit_store: Any) -> Iterator[Any]:
    store = unit_store.UnitStore(tmp_path / "unit")
    yield store
    store.close()


def _backup_script() -> Any:
    path = REPO / "deploy/reference/bin/backup-legacy-state.py"
    spec = importlib.util.spec_from_file_location("backup_legacy_state", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["backup_legacy_state"] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_backup_zip_is_read_as_the_unit_wrote_it_and_left_as_it_was(
    tmp_path: Path, unit: Any, unit_store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = unit_store.brief("Ranní nápoj", "Zjistit zájem")
    unit.save(PRJ, content, reason="project_created")
    unit.save(PRJ, {**content, "goal": "Jinak"}, analysis={"summary": "rozbor"})
    record = unit.attach("zadání.pdf", b"%PDF-1.4 fiktivni", project_id=PRJ, revision=2)
    unit.close()

    bundle = tmp_path / "legacy-state.zip"
    with bundle.open("wb") as out:
        assert _backup_script().write_backup(unit.root, out) == ["project_store.sqlite"]
    before = (_sha(bundle), bundle.stat().st_mtime_ns)
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    with UnitProjectStore(bundle) as copy:
        project = copy.project(PRJ)
        assert project is not None
        assert [r.revision for r in project.revisions] == [1, 2]
        assert project.revisions[0].content == content
        assert project.revisions[0].reason == "project_created"
        assert project.revisions[1].analysis == {"summary": "rozbor"}
        assert all(r.content_sha256 == fingerprint(r.content) for r in project.revisions)
        assert [(a.attachment_id, a.stored_name, a.revision) for a in project.attachments] == [
            (record["attachment_id"], record["stored_name"], 2)
        ]
        assert (project.project_type, project.status, project.deleted_at) == (
            "research",
            "DRAFT",
            None,
        )
        assert copy.project("PRJ-not-there") is None
        assert [s.project_id for s in copy.summaries()] == [PRJ]
        assert list(scratch.iterdir())  # unpacked while open ...
    assert list(scratch.iterdir()) == []  # ... and removed on close
    assert (_sha(bundle), bundle.stat().st_mtime_ns) == before


def test_the_database_itself_is_read_without_being_changed(unit: Any, unit_store: Any) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"))
    unit.trash(PRJ)
    unit.close()
    before = (_sha(unit.database), unit.database.stat().st_mtime_ns)
    with UnitProjectStore(unit.database) as copy:
        project = copy.project(PRJ)
        assert project is not None and project.status == "TRASHED" and project.deleted_at
    assert (_sha(unit.database), unit.database.stat().st_mtime_ns) == before
    assert not unit.database.with_name("project_store.sqlite-wal").exists()


def test_a_database_the_unit_still_has_open_is_refused(unit: Any, unit_store: Any) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"))
    # The unit's own connection is still open in WAL mode: its log and shared memory
    # are beside the file, and immutable reading would miss what they hold.
    assert unit.database.with_name("project_store.sqlite-shm").exists()
    with pytest.raises(ValueError, match="live database"):
        UnitProjectStore(unit.database)


def test_what_is_not_a_unit_store_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "other.sqlite"
    cx = sqlite3.connect(other)
    cx.execute("CREATE TABLE projects(project_id TEXT)")
    cx.commit()
    cx.close()
    with pytest.raises(ValueError, match="project_attachments, project_revisions"):
        UnitProjectStore(other)
    empty_zip = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty_zip, "w") as z:
        z.writestr("readme.txt", "nic")
    with pytest.raises(FileNotFoundError, match=r"holds no project_store\.sqlite"):
        UnitProjectStore(empty_zip)
    with pytest.raises(FileNotFoundError):
        UnitProjectStore(tmp_path / "missing.sqlite")


def test_a_file_is_read_by_its_base_name_inside_the_copy_only(tmp_path: Path) -> None:
    folder = tmp_path / "project_attachments"
    folder.mkdir()
    (folder / "ATT-00000000000001_a.txt").write_bytes(b"a")
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"secret")
    (folder / "ATT-00000000000002_link.txt").symlink_to(outside)
    files = UnitAttachmentFiles(folder)
    assert files.read("ATT-00000000000001_a.txt") == b"a"
    assert files.read("/app/data/ui_uploads/project_attachments/ATT-00000000000001_a.txt") == b"a"
    assert files.read("..\\..\\ATT-00000000000001_a.txt") == b"a"
    assert files.read("../secret.txt") is None
    assert files.read("ATT-00000000000002_link.txt") is None  # points outside
    assert files.read("") is None and files.read("..") is None
    assert files.read("ATT-missing") is None
    with pytest.raises(NotADirectoryError):
        UnitAttachmentFiles(outside)


# --------------------------------------------------------------------------- #
# The migration, end to end
# --------------------------------------------------------------------------- #


@pytest.fixture
def sessions(engine: Any) -> Any:
    return create_session_factory(engine)


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _bind(session: Any, scoped: Any, *, study: str = "primary", unit_project: str = PRJ) -> str:
    """A Study bound to an 18.6.6 project before ADR 0018: as migration 5b1d0f3e9a21 left it."""
    s = scoped.studies[study]
    session.add(
        StudyWorkspaceRow(
            study_id=s.study_id,
            organization_id=scoped.organization_id,
            client_id=s.client_id,
            content_state=ContentState.AWAITING_MIGRATION.value,
            unit_project_id=unit_project,
            lineage={},
            bound_by=scoped.users["lead"],
        )
    )
    session.commit()
    return str(s.study_id)


def _migrate(
    sessions: Any, store: Any, unit: Any, *, actor: str = LEAD, **options: Any
) -> MigrationReport:
    unit.close()  # the unit wrote its copy; a closed database leaves no log beside it
    with UnitProjectStore(unit.database) as copy:
        return migrate_unit_workspaces(
            sessions,
            store=store,
            unit=copy,
            files=UnitAttachmentFiles(unit.uploads),
            actor_email=actor,
            **options,
        )


def _row(session: Any, study_id: str) -> StudyWorkspaceRow:
    session.expire_all()
    row = session.get(StudyWorkspaceRow, study_id)
    assert row is not None
    return row


def _history(unit: Any, unit_store: Any) -> dict[str, Any]:
    """Four revisions of one project, the way a person worked in 18.6.6."""
    first = unit_store.brief("Ranní nápoj", "Zjistit zájem")
    unit.save(PRJ, first, reason="project_created")
    brief_file = unit.attach(
        "zadání.txt", "Fiktivní zadání".encode(), project_id=PRJ, revision=1, text="Fiktivní zadání"
    )
    second = unit_store.brief("Ranní nápoj", "Zjistit zájem", [brief_file])
    unit.save(PRJ, second)
    # The same document with a new analysis: a revision of its own in the unit.
    unit.save(PRJ, second, analysis={"summary": "rozbor"}, reason="ai_analysis")
    # The rebuilt interface uploaded without a project: a record, a file, no binding.
    unbound = unit.attach("otázky.xlsx", b"PK\x03\x04 fiktivni")
    fourth = unit_store.brief("Ranní nápoj 2", "Zjistit zájem dospělých", [brief_file, unbound])
    unit.save(PRJ, fourth, analysis={"summary": "rozbor"})
    # Bound to the project, never named by a brief.
    extra = unit.attach("podklad.pdf", b"%PDF-1.4 fiktivni", project_id=PRJ, revision=4)
    return {"contents": [first, second, second, fourth], "files": [brief_file, unbound, extra]}


def test_a_dry_run_says_what_it_would_do_and_writes_nothing(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    _history(unit, unit_store)
    study_id = _bind(session, scoped)
    report = _migrate(sessions, store, unit)
    assert report.applied is False
    (study,) = report.studies
    assert (study.outcome, study.applied) == (MigrationOutcome.MIGRATED, False)
    assert (study.source_revisions, study.migrated_revisions, len(study.files_migrated)) == (
        4,
        0,
        3,
    )
    row = _row(session, study_id)
    assert (row.content_state, row.project_id) == (ContentState.AWAITING_MIGRATION.value, None)
    assert session.scalar(select(func.count()).select_from(ProjectRow)) == 0
    assert store.keys == []


def test_a_study_gets_every_revision_and_file_and_keeps_who_it_belongs_to(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    world = _history(unit, unit_store)
    study_id = _bind(session, scoped)
    report = _migrate(sessions, store, unit, apply=True)
    (study,) = report.studies
    assert (study.outcome, study.applied, study.migrated_revisions) == (
        MigrationOutcome.MIGRATED,
        True,
        4,
    )
    assert (study.files_missing, study.files_mismatched, study.problems) == ([], [], [])
    ids = {f.attachment_id: f for f in study.files_migrated}
    brief_file, unbound, extra = world["files"]
    assert set(ids) == {f["attachment_id"] for f in world["files"]}
    assert not ids[extra["attachment_id"]].named_in_brief

    lead = scoped.scope()
    workspaces = StudyWorkspaceRepository(session)
    session.expire_all()
    loaded = workspaces.content(lead)
    assert (loaded.state, loaded.revision) == (ContentState.MIGRATED, 4)
    assert loaded.analysis == {"summary": "rozbor"}
    records = loaded.content["briefing"]["attachments"]
    assert [r["attachment_id"] for r in records] == [
        ids[brief_file["attachment_id"]].artifact_id,
        ids[unbound["attachment_id"]].artifact_id,
    ]
    assert [r["legacy_attachment_id"] for r in records] == [
        brief_file["attachment_id"],
        unbound["attachment_id"],
    ]
    assert not any(k in r for r in records for k in ("download_url", "stored_name", "project_id"))
    assert records[0]["context_excerpt"] == "Fiktivní zadání"

    # One for one, oldest first, reasons marked, the author unknown -- never the operator.
    history = workspaces.revisions(lead)
    assert [r.revision for r in history] == [4, 3, 2, 1]
    assert [r.reason for r in history] == [
        "unit:autosave",
        "unit:ai_analysis",
        "unit:autosave",
        "unit:project_created",
    ]
    assert {r.created_by for r in history} == {None}
    ws = workspaces.get(lead)
    assert ws is not None and ws.project_id is not None
    rows = {
        r.revision: r
        for r in session.scalars(
            select(ProjectRevisionRow).where(ProjectRevisionRow.project_id == ws.project_id)
        )
    }
    # A revision that names no file is the unit's byte for byte, hash included.
    assert rows[1].content == world["contents"][0]
    assert rows[1].content_sha256 == unit_store.unit_sha(world["contents"][0])
    assert rows[2].content_sha256 == rows[3].content_sha256 != rows[4].content_sha256

    # The files are in AIA storage, served through the Study only, byte for byte.
    for legacy, data in (
        (brief_file, "Fiktivní zadání".encode()),
        (unbound, b"PK\x03\x04 fiktivni"),
        (extra, b"%PDF-1.4 fiktivni"),
    ):
        artifact, body = workspaces.attachment(
            lead, store, ids[legacy["attachment_id"]].artifact_id
        )
        assert body == data
        assert artifact.metadata["legacy_attachment_id"] == legacy["attachment_id"]
        assert artifact.metadata["migrated_from"] == LEGACY_SOURCE
    placed = {r.artifact_id: r.revision for r in session.scalars(select(ProjectArtifactRow))}
    assert placed[ids[brief_file["attachment_id"]].artifact_id] == 2  # first named in revision 2
    assert placed[ids[unbound["attachment_id"]].artifact_id] == 4
    assert placed[ids[extra["attachment_id"]].artifact_id] == 4  # bound at revision 4

    # The Study's own project, in its own client, and a record of who migrated it.
    project = session.get(ProjectRow, ws.project_id)
    assert (project.study_id, project.client_id, project.organization_id) == (
        lead.study_id,
        lead.client_id,
        lead.organization_id,
    )
    events = list(
        session.scalars(select(ProjectEventRow).where(ProjectEventRow.project_id == ws.project_id))
    )
    migrated = [e for e in events if e.event_type == "WORKSPACE_MIGRATED"]
    assert [(e.actor_id, e.payload["revisions"], e.payload["files"]) for e in migrated] == [
        (lead.actor_id, 4, 3)
    ]
    assert {e.actor_id for e in events if e.event_type == "REVISION_SAVED"} == {None}

    lineage = _row(session, study_id).lineage
    assert lineage["source"] == LEGACY_SOURCE and lineage["unit_project_id"] == PRJ
    assert (lineage["outcome"], lineage["migration_version"], lineage["migrated_by"]) == (
        "migrated",
        MIGRATION_VERSION,
        lead.actor_id,
    )
    assert [(r["aia_revision"], r["unit_revision"]) for r in lineage["revisions"]] == [
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
    ]
    assert all(
        r["unit_revision_id"].startswith("REV-") and r["unit_created_at"]
        for r in lineage["revisions"]
    )
    assert lineage["files"] == {k: v.artifact_id for k, v in ids.items()}

    # And it is AIA's content now: the next save is an ordinary one.
    saved = workspaces.save(lead, content={**loaded.content, "goal": "Po migraci"}, base_revision=4)
    assert (saved.revision, saved.state) == (5, ContentState.MIGRATED)


def test_a_file_not_in_the_copy_or_changed_since_is_reported_and_its_record_kept(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    kept = unit.attach("a.txt", b"a", project_id=PRJ)
    lost = unit.attach("b.txt", b"b", project_id=PRJ)
    changed = unit.attach("c.txt", b"c", project_id=PRJ)
    unit.save(PRJ, unit_store.brief("T", "G", [kept, lost, changed]))
    (unit.uploads / lost["stored_name"]).unlink()
    (unit.uploads / changed["stored_name"]).write_bytes(b"not c")
    study_id = _bind(session, scoped)
    (study,) = _migrate(sessions, store, unit, apply=True).studies
    assert (study.outcome, study.applied) == (MigrationOutcome.MIGRATED, True)
    assert study.files_missing == [lost["attachment_id"]]
    assert study.files_mismatched == [changed["attachment_id"]]
    assert [f.attachment_id for f in study.files_migrated] == [kept["attachment_id"]]
    session.expire_all()
    records = (
        StudyWorkspaceRepository(session).content(scoped.scope()).content["briefing"]["attachments"]
    )
    assert records[0]["attachment_id"].startswith("ART-")
    assert records[1:] == [lost, changed]  # exactly as the unit had them
    assert len(store.keys) == 1
    lineage = _row(session, study_id).lineage
    assert (lineage["files_missing"], lineage["files_mismatched"]) == (
        [lost["attachment_id"]],
        [changed["attachment_id"]],
    )


def test_a_project_missing_from_the_copy_waits_until_the_copy_is_said_complete(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    unit.save("PRJ-somethingelse", unit_store.brief("Jiný", "G"))
    designed = _bind(session, scoped, unit_project="PRJ-gone0000000001")
    nothing = _bind(session, scoped, study="sibling", unit_project="PRJ-gone0000000002")
    design = {"title": "Ranní nápoj", "goal": "Zjistit zájem", "sections": []}
    revision, _ = StudyDesignRepository(session, scoped.scope()).submit(
        content=design, source_stage="run"
    )
    session.commit()

    waiting = _migrate(sessions, store, unit, apply=True)
    assert [(s.outcome, s.applied) for s in waiting.studies] == [
        (MigrationOutcome.NOT_MIGRATED, False)
    ] * 2
    assert all("not in this copy" in s.reason for s in waiting.studies)
    assert {_row(session, s).content_state for s in (designed, nothing)} == {
        ContentState.AWAITING_MIGRATION.value
    }

    unit_again = unit_store.UnitStore(unit.root)  # the same copy, now said to be complete
    report = _migrate(sessions, store, unit_again, apply=True, recover_missing=True)
    outcomes = {s.study_id: (s.outcome, s.applied) for s in report.studies}
    assert outcomes == {
        designed: (MigrationOutcome.RECOVERED, True),
        nothing: (MigrationOutcome.UNRECOVERABLE, True),
    }
    session.expire_all()
    recovered = StudyWorkspaceRepository(session).content(scoped.scope())
    assert (recovered.state, recovered.revision, recovered.content) == (
        ContentState.RECOVERED,
        1,
        design,
    )
    assert StudyWorkspaceRepository(session).revisions(scoped.scope())[0].reason == RECOVERED_REASON
    assert _row(session, designed).lineage["design_revision_id"] == revision.revision_id
    lost = StudyWorkspaceRepository(session).content(scoped.scope(study="sibling"))
    assert (lost.state, lost.revision, lost.content) == (ContentState.UNRECOVERABLE, None, None)
    assert _row(session, nothing).lineage["outcome"] == "unrecoverable"


def test_any_member_with_the_client_can_be_the_operator_whatever_their_former_role(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    """ADR 0019: the former viewer holds the Researcher grant, so their migration is applied.

    Before it, the same operator was refused with ``insufficient_role`` and a PERMISSION_DENIED
    audit entry. The study is migrated as that person, through their own grants.
    """
    unit.save(PRJ, unit_store.brief("T", "G"))
    unit.close()
    study_id = _bind(session, scoped)
    (study,) = _migrate(
        sessions, store, unit_store.UnitStore(unit.root), actor="viewer@art-chain.io", apply=True
    ).studies
    assert (study.outcome, study.applied) == (MigrationOutcome.MIGRATED, True)
    assert _row(session, study_id).content_state == ContentState.MIGRATED.value
    session.expire_all()
    user = session.scalar(select(UserRow).where(UserRow.email == "viewer@art-chain.io"))
    denied = session.scalars(
        select(AccessAuditRow).where(
            AccessAuditRow.actor_id == user.user_id,
            AccessAuditRow.action.in_(("ACCESS_DENIED", "PERMISSION_DENIED")),
        )
    ).all()
    assert denied == []


def test_the_operator_migrates_only_what_their_own_grants_let_them_edit(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"))
    unit.close()
    study_id = _bind(session, scoped)
    for actor, reason, action in (
        ("outsider@art-chain.io", "no_grant", "ACCESS_DENIED"),
        # An organization owner has no implicit access to a client's studies.
        ("owner@art-chain.io", "no_grant", "ACCESS_DENIED"),
    ):
        again = unit_store.UnitStore(unit.root)
        (study,) = _migrate(sessions, store, again, actor=actor, apply=True).studies
        assert (study.outcome, study.applied) == (MigrationOutcome.NOT_MIGRATED, False)
        assert reason in study.reason
        session.expire_all()
        user = session.scalar(select(UserRow).where(UserRow.email == actor))
        audit = session.scalars(
            select(AccessAuditRow).where(
                AccessAuditRow.actor_id == user.user_id,
                AccessAuditRow.study_id == study_id,
                AccessAuditRow.action.in_(("ACCESS_DENIED", "PERMISSION_DENIED")),
            )
        ).all()
        assert [a.action for a in audit] == [action]
    assert _row(session, study_id).content_state == ContentState.AWAITING_MIGRATION.value
    assert store.keys == []

    with pytest.raises(MigrationRefused):
        _migrate(sessions, store, unit_store.UnitStore(unit.root), actor="nobody@example.invalid")
    session.expire_all()
    session.scalar(select(UserRow).where(UserRow.email == LEAD)).is_active = False
    session.commit()
    with pytest.raises(MigrationRefused):
        _migrate(sessions, store, unit_store.UnitStore(unit.root))


def test_a_closed_study_or_a_simulation_project_is_left_waiting_and_says_why(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"))
    unit.save(
        "PRJ-simulation0001",
        {"schema_version": "simulation-project-v1", "title": "S", "simulation": {}},
        project_type="simulation",
    )
    closed = _bind(session, scoped)
    simulation = _bind(session, scoped, study="sibling", unit_project="PRJ-simulation0001")
    scoped.scope_repo.set_study_status(scoped.scope(), status=StudyStatus.DELIVERED)
    session.commit()
    report = _migrate(sessions, store, unit, apply=True)
    reasons = {s.study_id: (s.outcome, s.reason) for s in report.studies}
    assert reasons[closed] == (
        MigrationOutcome.NOT_MIGRATED,
        "the Study is DELIVERED: reopen it to migrate",
    )
    assert reasons[simulation] == (
        MigrationOutcome.NOT_MIGRATED,
        "the unit project is a simulation project, not research",
    )
    assert {_row(session, s).content_state for s in (closed, simulation)} == {
        ContentState.AWAITING_MIGRATION.value
    }


def test_what_does_not_validate_is_rolled_back_and_left_waiting(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    # A revision without a title: AIA's first write gives one, so what is written is
    # not the unit's, and the Study is rolled back rather than migrated differently.
    untitled = unit_store.brief("T", "G")
    del untitled["title"]
    unit.save(PRJ, untitled)
    study_id = _bind(session, scoped)
    (study,) = _migrate(sessions, store, unit, apply=True).studies
    assert (study.outcome, study.applied) == (MigrationOutcome.NOT_MIGRATED, False)
    assert study.reason == "what was written did not match the source; rolled back"
    assert any("content differs" in p for p in study.problems)
    row = _row(session, study_id)
    assert (row.content_state, row.project_id, row.lineage) == (
        ContentState.AWAITING_MIGRATION.value,
        None,
        {},
    )
    assert session.scalar(select(func.count()).select_from(ProjectRow)) == 0


def test_a_copy_that_does_not_hash_to_what_the_unit_recorded_is_not_migrated(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"), sha="0" * 64)
    study_id = _bind(session, scoped)
    (study,) = _migrate(sessions, store, unit, apply=True).studies
    assert (study.outcome, study.applied) == (MigrationOutcome.NOT_MIGRATED, False)
    assert "does not hash" in study.problems[0]
    assert _row(session, study_id).content_state == ContentState.AWAITING_MIGRATION.value


def test_a_second_run_changes_nothing_and_says_what_was_done_before(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    world = _history(unit, unit_store)
    unit.save("PRJ-nobodys0000001", unit_store.brief("Nikoho", "G"))
    study_id = _bind(session, scoped)
    first = _migrate(sessions, store, unit, apply=True)
    assert [p.project_id for p in first.unit_projects_not_bound] == ["PRJ-nobodys0000001"]
    revisions = session.scalar(select(func.count()).select_from(ProjectRevisionRow))
    objects = store.keys

    second = _migrate(sessions, store, unit_store.UnitStore(unit.root), apply=True)
    assert (second.studies_awaiting, second.studies) == (0, [])
    assert [(d.study_id, d.unit_project_id, d.state) for d in second.done_before] == [
        (study_id, PRJ, ContentState.MIGRATED.value)
    ]
    # The migrated project is still one a Study refers to.
    assert [p.project_id for p in second.unit_projects_not_bound] == ["PRJ-nobodys0000001"]
    assert (
        session.scalar(select(func.count()).select_from(ProjectRevisionRow))
        == revisions
        == len(world["contents"])
    )
    assert store.keys == objects


def test_a_run_can_be_limited_to_named_studies_and_keeps_a_trashed_projects_mark(
    session: Any,
    scoped: Any,
    sessions: Any,
    store: InMemoryArtifactStore,
    unit: Any,
    unit_store: Any,
) -> None:
    unit.save(PRJ, unit_store.brief("T", "G"))
    unit.trash(PRJ)
    unit.save("PRJ-other00000001", unit_store.brief("O", "G"))
    primary = _bind(session, scoped)
    sibling = _bind(session, scoped, study="sibling", unit_project="PRJ-other00000001")
    report = _migrate(sessions, store, unit, apply=True, only={primary})
    assert [s.study_id for s in report.studies] == [primary] and report.studies_awaiting == 2
    assert report.studies[0].unit_trashed is True
    assert _row(session, primary).lineage["unit_trashed"] is True
    assert _row(session, sibling).content_state == ContentState.AWAITING_MIGRATION.value
