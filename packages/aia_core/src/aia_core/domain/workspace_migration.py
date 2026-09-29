"""Bringing a Study's working content over from the 18.6.6 project store (ADR 0018, decision 2).

Until ADR 0018 a research Study's working content was an 18.6.6 unit project, bound
to the Study by ``study_workspaces.unit_project_id``; every such binding is now
``AWAITING_MIGRATION``. The migration brings each over once, explicitly, and says
what it did:

* **MIGRATED** -- the bound unit project exists. Every one of its revisions becomes a
  revision of the Study's working project, in order, one for one: AIA revision *k*
  is unit revision *k*. Their content is the unit's, byte for byte, except the
  brief's file records, which name the AIA artifact now holding each file
  (:func:`rewrite_attachments`). The unit's revision ids, timestamps and reasons are
  kept in lineage.
* **RECOVERED** -- the bound project is not in the store and the Study submitted a
  Design Revision: its newest becomes the working content, with lineage (OI-66).
* **UNRECOVERABLE** -- the bound project is not in the store and nothing was
  submitted: the Study says so, and a person who may edit starts again explicitly.
  Both of these are decided only when the operator says the copy is complete
  (``recover_missing``): a project missing from an incomplete copy is not lost.
* **NOT_MIGRATED** -- anything the migration could not do safely (the actor has no
  edit grant, the Study is closed, the project is a simulation, the copy does not
  hash to what the unit recorded, a revision fails validation). The Study stays
  ``AWAITING_MIGRATION``, and the report says why.

The unit never recorded who saved a revision, so a migrated revision's author is
unknown (``created_by`` null), never the operator's. Nothing here reads or writes
the unit's files: this module is the rules; the reader and the writes are
infrastructure, the orchestration application.

Pure: no I/O.
"""

from __future__ import annotations

import copy
import re
from enum import StrEnum
from typing import Any, Final
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field

from .pipeline import fingerprint
from .workspace import LEGACY_SOURCE, SAVE_REASON, WorkspaceRejected, validate_working_content

__all__ = [
    "LEGACY_ATTACHMENT_ID",
    "MIGRATION_VERSION",
    "DoneBefore",
    "FileRef",
    "MigratedFile",
    "MigrationOutcome",
    "MigrationReport",
    "StudyMigration",
    "UnitAttachment",
    "UnitProject",
    "UnitProjectSummary",
    "UnitRevision",
    "file_refs",
    "migrated_reason",
    "rewrite_attachments",
    "source_problems",
    "validate_migration",
]

#: The migration's own version: recorded in every Study's lineage it writes.
MIGRATION_VERSION: Final = "aia-unit-workspace-migration-1"

#: The unit's attachment ids (``ui_server.save_project_attachment``: ``ATT-`` and 14
#: hex characters). A brief record with any other id is not a unit file.
LEGACY_ATTACHMENT_ID: Final = re.compile(r"^ATT-[0-9a-f]{6,64}$")

# Keys of a unit file record that name the unit's own storage: dropped once the file
# is in AIA, where only the artifact id finds it (ADR 0018: a record carries no URL).
_UNIT_STORAGE_KEYS: Final = ("download_url", "stored_name", "project_id")
_REASON_UNSAFE: Final = re.compile(r"[^a-z0-9_.-]+")


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UnitRevision(_Frozen):
    """One immutable revision of a unit project (``project_revisions``)."""

    revision: int
    revision_id: str | None
    created_at: str | None
    reason: str
    content_sha256: str | None
    content: dict[str, Any]
    analysis: dict[str, Any]


class UnitAttachment(_Frozen):
    """A file the unit bound to a project (``project_attachments``)."""

    attachment_id: str
    filename: str
    stored_name: str
    sha256: str
    size_bytes: int
    revision: int | None
    created_at: str | None


class UnitProject(_Frozen):
    """A unit project as its store holds it: the whole history, never a single copy."""

    project_id: str
    title: str
    project_type: str
    status: str
    current_revision: int
    deleted_at: str | None
    revisions: tuple[UnitRevision, ...]
    attachments: tuple[UnitAttachment, ...]


class UnitProjectSummary(_Frozen):
    """A unit project in the report's list of what no Study refers to."""

    project_id: str
    title: str
    project_type: str
    status: str
    current_revision: int
    modified_at: str | None


class FileRef(_Frozen):
    """A unit file of a project: its id, the name the unit stored it by, where it appears.

    ``first_revision`` is the unit revision whose brief first named it, or -- for a
    file the unit bound to the project that no brief names -- the revision it was
    bound at (the last one when the unit recorded none).
    """

    attachment_id: str
    stored_name: str
    filename: str
    sha256: str
    size_bytes: int
    first_revision: int
    named_in_brief: bool


class MigratedFile(_Frozen):
    """A unit file now held in AIA: the artifact that has its bytes."""

    attachment_id: str
    artifact_id: str
    filename: str
    sha256: str
    size_bytes: int
    named_in_brief: bool


class MigrationOutcome(StrEnum):
    MIGRATED = "MIGRATED"
    RECOVERED = "RECOVERED"
    UNRECOVERABLE = "UNRECOVERABLE"
    NOT_MIGRATED = "NOT_MIGRATED"


class StudyMigration(BaseModel):
    """What the migration did, or would do, for one Study."""

    model_config = ConfigDict(extra="forbid")

    study_id: str
    organization_id: str
    unit_project_id: str | None
    outcome: MigrationOutcome
    reason: str = ""
    applied: bool = False
    source_revisions: int = 0
    migrated_revisions: int = 0
    unit_trashed: bool = False
    files_migrated: list[MigratedFile] = Field(default_factory=list)
    files_missing: list[str] = Field(default_factory=list)
    files_mismatched: list[str] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)


class DoneBefore(_Frozen):
    """A Study once bound to 18.6.6 that no longer waits: migrated, recovered or restarted."""

    study_id: str
    unit_project_id: str | None
    state: str


class MigrationReport(BaseModel):
    """The whole run: every Study that waited, and every unit project no Study refers to."""

    model_config = ConfigDict(extra="forbid")

    migration_version: str = MIGRATION_VERSION
    source: str = LEGACY_SOURCE
    applied: bool
    recover_missing: bool
    store: str
    attachments_dir: str | None
    actor: str
    studies_awaiting: int
    studies: list[StudyMigration]
    done_before: list[DoneBefore]
    unit_projects_not_bound: list[UnitProjectSummary]

    def count(self, outcome: MigrationOutcome) -> int:
        return sum(1 for s in self.studies if s.outcome is outcome)


# --------------------------------------------------------------------------- #
# The brief's file records
# --------------------------------------------------------------------------- #


def _records(content: dict[str, Any]) -> list[Any]:
    briefing = content.get("briefing")
    if not isinstance(briefing, dict):
        return []
    records = briefing.get("attachments")
    return records if isinstance(records, list) else []


def _stored_name(record: dict[str, Any]) -> str:
    """The name the unit stored a file by: its ``stored_name``, else its URL's last part."""
    stored = record.get("stored_name")
    if isinstance(stored, str) and stored:
        return stored.rsplit("/", 1)[-1]
    url = record.get("download_url")
    if isinstance(url, str) and url.startswith("/project-attachments/"):
        return unquote(url.rsplit("/", 1)[-1])
    return ""


def _is_unit_file(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("kind", "file") != "url"
        and isinstance(record.get("attachment_id"), str)
        and bool(LEGACY_ATTACHMENT_ID.fullmatch(record["attachment_id"]))
    )


def _size(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def file_refs(project: UnitProject) -> list[FileRef]:
    """Every unit file of the project, once each.

    First the files a brief named in any revision, in order of first mention; then
    the files the unit bound to the project (``project_attachments``) that no brief
    names -- still the project's, so they are brought too. What a brief record
    leaves out (its stored name, its SHA256) is taken from the unit's binding of
    the same id, when there is one.
    """
    bound = {a.attachment_id: a for a in project.attachments}
    last = project.revisions[-1].revision if project.revisions else 1
    seen: dict[str, FileRef] = {}
    for rev in project.revisions:
        for record in _records(rev.content):
            if not _is_unit_file(record) or record["attachment_id"] in seen:
                continue
            binding = bound.get(record["attachment_id"])
            seen[record["attachment_id"]] = FileRef(
                attachment_id=record["attachment_id"],
                stored_name=_stored_name(record) or (binding.stored_name if binding else ""),
                filename=str(record.get("filename") or (binding.filename if binding else "")),
                sha256=str(record.get("sha256") or (binding.sha256 if binding else "")),
                size_bytes=_size(record.get("size_bytes"))
                or (binding.size_bytes if binding else 0),
                first_revision=rev.revision,
                named_in_brief=True,
            )
    for a in project.attachments:
        if a.attachment_id in seen:
            continue
        seen[a.attachment_id] = FileRef(
            attachment_id=a.attachment_id,
            stored_name=a.stored_name,
            filename=a.filename,
            sha256=a.sha256,
            size_bytes=a.size_bytes,
            first_revision=a.revision if a.revision else last,
            named_in_brief=False,
        )
    return list(seen.values())


def rewrite_attachments(
    content: dict[str, Any], migrated: dict[str, MigratedFile]
) -> dict[str, Any]:
    """The content with each migrated unit file's record naming its AIA artifact.

    A record of a migrated file keeps every key it had but the unit's storage ones
    (``download_url``, ``stored_name``, ``project_id``): ``attachment_id`` becomes the
    artifact's, and ``legacy_attachment_id`` keeps the unit's. A record whose file did
    not come over is left exactly as it was, so the brief still says what was attached
    and the stage says the file is not in AIA. Deterministic: validation applies it to
    the source and compares.
    """
    out = copy.deepcopy(content)
    for i, record in enumerate(_records(out)):
        if not _is_unit_file(record) or record["attachment_id"] not in migrated:
            continue
        file = migrated[record["attachment_id"]]
        kept = {k: v for k, v in record.items() if k not in _UNIT_STORAGE_KEYS}
        kept["attachment_id"] = file.artifact_id
        kept["legacy_attachment_id"] = file.attachment_id
        _records(out)[i] = kept
    return out


def migrated_reason(unit_reason: str) -> str:
    """A migrated revision's reason: the unit's, marked as migrated, within ``SAVE_REASON``."""
    reason = _REASON_UNSAFE.sub("_", str(unit_reason or "").lower()).strip("_")[:54]
    candidate = f"unit:{reason or 'saved'}"
    return candidate if SAVE_REASON.fullmatch(candidate) else "unit:saved"


def source_problems(project: UnitProject) -> list[str]:
    """Why a unit project cannot be migrated as it is in the copy; none when it can.

    Each revision's content must hash to the SHA256 the unit recorded when it wrote
    it -- the unit's ``_sha`` and AIA's :func:`~aia_core.domain.pipeline.fingerprint`
    are the same function -- so a copy that is not what the unit wrote is refused
    rather than migrated. And each must be content AIA can hold
    (:func:`~aia_core.domain.workspace.validate_working_content`), so the Study can
    be saved again once it is migrated.
    """
    problems: list[str] = []
    for rev in project.revisions:
        if rev.content_sha256 and fingerprint(rev.content) != rev.content_sha256:
            problems.append(
                f"unit revision {rev.revision}: the copy's content does not hash to the "
                "SHA256 the unit recorded"
            )
        try:
            validate_working_content(rev.content, rev.analysis)
        except WorkspaceRejected as exc:
            problems.append(f"unit revision {rev.revision}: {exc} ({exc.reason})")
    return problems


def validate_migration(
    source: tuple[UnitRevision, ...] | list[UnitRevision],
    written: list[tuple[int, str, dict[str, Any]]],
    migrated: dict[str, MigratedFile],
) -> list[str]:
    """Problems with a migration, none when it holds. ``written`` is (revision, sha, analysis).

    Every source revision must be there, in order and one for one -- AIA revision
    *k* is the *k*-th of the unit's -- each one's content hash must be that of the
    source's content with its file records rewritten, and its analysis the source's.
    """
    problems: list[str] = []
    if len(written) != len(source):
        problems.append(f"{len(source)} revisions in the unit, {len(written)} written")
    for position, ((aia_revision, sha, analysis), unit) in enumerate(
        zip(written, source, strict=False), start=1
    ):
        if aia_revision != position:
            problems.append(
                f"unit revision {unit.revision} was written as AIA revision {aia_revision}, "
                f"not {position}"
            )
        expected = fingerprint(rewrite_attachments(unit.content, migrated))
        if sha != expected:
            problems.append(
                f"unit revision {unit.revision}: content differs from the unit's "
                f"(AIA revision {aia_revision})"
            )
        if analysis != unit.analysis:
            problems.append(f"unit revision {unit.revision}: analysis differs from the unit's")
    return problems
