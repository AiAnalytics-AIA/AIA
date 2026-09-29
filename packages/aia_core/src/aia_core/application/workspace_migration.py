"""The explicit, one-off migration of Studies' working content out of 18.6.6 (ADR 0018, decision 2).

Every Study bound to an 18.6.6 project before ADR 0018 is ``AWAITING_MIGRATION``:
readable, not editable. :func:`migrate_unit_workspaces` brings each over from a
**copy** of the unit's project store and attachment directory, as the operator named
by ``actor_email`` -- through a scope the resolver issues for that person on that
Study, exactly as the API would, so a Study they may not edit is reported and left
waiting, never written around its scope.

**Dry run by default.** Without ``apply`` no content, file or state is written and
the report says what would happen; the only record a dry run leaves is the access
audit's entry for a Study the operator was refused, as any refused request leaves.
With ``apply``, each Study is its own transaction: the files are uploaded, the
revisions written, the result compared with the source
(:func:`~aia_core.domain.workspace_migration.validate_migration`), and only a Study
that validates is committed; one that does not is rolled back, stays waiting, and is
reported with the difference. Re-running changes nothing already migrated: a Study
that no longer waits is listed as done before, never written again.

**A project missing from the copy is not lost** until the operator says the copy is
complete (``recover_missing``): only then does such a Study become ``RECOVERED``
from its newest Design Revision or ``UNRECOVERABLE``. Without it the Study stays
waiting, so a partial or wrong copy cannot decide its fate.

What stays behind is listed too: files the brief names that are not in the copy or
whose bytes do not match their recorded SHA256, and every unit project no Study
refers to. Nothing reads the unit afterwards, and nothing here writes it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..domain.attachments import extension_of, safe_filename
from ..domain.scope import Permission, ScopeDenied, StudyContext, StudyKind
from ..domain.workspace import LEGACY_SOURCE, ContentState
from ..domain.workspace_migration import (
    MIGRATION_VERSION,
    DoneBefore,
    FileRef,
    MigratedFile,
    MigrationOutcome,
    MigrationReport,
    StudyMigration,
    UnitProject,
    file_refs,
    migrated_reason,
    rewrite_attachments,
    source_problems,
    validate_migration,
)
from ..infrastructure.artifact_repository import new_artifact_id
from ..infrastructure.storage import ArtifactStore, StorageError
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_workspace_repository import StudyWorkspaceRepository, WorkspaceConflict
from ..infrastructure.tables import StudyRow, UserRow
from ..infrastructure.unit_project_store import UnitAttachmentFiles, UnitProjectStore
from .scope import AuthenticatedPrincipal, ScopeResolver

__all__ = ["MigrationRefused", "migrate_unit_workspaces"]

#: The reason every recovered revision is written with.
RECOVERED_REASON = "unit:recovered_from_design"


class MigrationRefused(Exception):
    """The migration cannot start: the operator named is not an active AIA user."""


class _Invalid(Exception):
    """What was written is not the source: the Study's transaction is rolled back."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def _actor(session: Session, email: str) -> str:
    row = session.scalar(select(UserRow).where(UserRow.email == email.strip().lower()))
    if row is None or not row.is_active:
        raise MigrationRefused(f"no active AIA user {email!r}; the migration acts as a person")
    return row.user_id


def _read_files(
    refs: list[FileRef], files: UnitAttachmentFiles | None
) -> tuple[list[tuple[FileRef, bytes]], list[str], list[str]]:
    """The unit files in the copy: (found, missing, mismatched), each by attachment id."""
    found: list[tuple[FileRef, bytes]] = []
    missing: list[str] = []
    mismatched: list[str] = []
    for ref in refs:
        data = files.read(ref.stored_name) if files is not None and ref.stored_name else None
        if data is None:
            missing.append(ref.attachment_id)
        elif ref.sha256 and UnitAttachmentFiles.sha256(data) != ref.sha256:
            mismatched.append(ref.attachment_id)
        else:
            found.append((ref, data))
    return found, missing, mismatched


def _lineage(report: StudyMigration, *, actor_id: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": LEGACY_SOURCE,
        "unit_project_id": report.unit_project_id,
        "outcome": report.outcome.value.lower(),
        "migration_version": MIGRATION_VERSION,
        "migrated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "migrated_by": actor_id,
        **extra,
    }


def _recover(
    session: Session,
    scope: StudyContext,
    report: StudyMigration,
    *,
    store: ArtifactStore,
    apply: bool,
) -> None:
    """The unit project is not in a copy the operator says is complete."""
    workspaces = StudyWorkspaceRepository(session)
    designs = StudyDesignRepository(session, scope)
    latest = designs.latest()
    if latest is None:
        report.outcome = MigrationOutcome.UNRECOVERABLE
        report.reason = "the unit project is not in the store and the Study submitted no design"
        if apply:
            workspaces.mark_unrecoverable(
                scope,
                lineage=_lineage(
                    report, actor_id=scope.actor_id, extra={"unit_project": "missing"}
                ),
            )
            report.applied = True
        return
    report.outcome = MigrationOutcome.RECOVERED
    report.reason = (
        "the unit project is not in the store; "
        f"recovered from Design Revision {latest.revision} ({latest.revision_id})"
    )
    report.source_revisions = 1
    if not apply:
        return
    written = workspaces.import_migrated(
        scope,
        store,
        revisions=[(designs.content(latest.revision_id), {}, RECOVERED_REASON)],
        files=[],
        state=ContentState.RECOVERED,
        lineage=_lineage(
            report,
            actor_id=scope.actor_id,
            extra={
                "unit_project": "missing",
                "design_revision_id": latest.revision_id,
                "design_revision": latest.revision,
            },
        ),
    )
    report.migrated_revisions = len(written)
    if written != [(1, latest.content_sha256, {})]:
        report.problems = ["the recovered content is not the Design Revision's"]
        raise _Invalid(report.problems)
    report.applied = True


def _migrate(
    session: Session,
    scope: StudyContext,
    report: StudyMigration,
    project: UnitProject,
    *,
    files: UnitAttachmentFiles | None,
    store: ArtifactStore,
    apply: bool,
) -> None:
    """The unit project is in the copy: bring its every revision and file."""
    report.source_revisions = len(project.revisions)
    report.unit_trashed = bool(project.deleted_at) or project.status == "TRASHED"
    if project.project_type != "research":
        report.reason = f"the unit project is a {project.project_type} project, not research"
        return
    if not project.revisions:
        report.reason = "the unit project has no revision to migrate"
        return
    problems = source_problems(project)
    if problems:
        report.problems = problems
        report.reason = "the copy of the unit project cannot be migrated as it is"
        return

    found, missing, mismatched = _read_files(file_refs(project), files)
    report.files_missing = missing
    report.files_mismatched = mismatched
    migrated = {
        ref.attachment_id: MigratedFile(
            attachment_id=ref.attachment_id,
            artifact_id=new_artifact_id(),
            filename=safe_filename(ref.filename or ref.stored_name),
            sha256=UnitAttachmentFiles.sha256(data),
            size_bytes=len(data),
            named_in_brief=ref.named_in_brief,
        )
        for ref, data in found
    }
    report.files_migrated = list(migrated.values())
    report.outcome = MigrationOutcome.MIGRATED
    if not apply:
        return

    # AIA revision k is the unit's k-th: a file sits at the AIA revision of the unit
    # revision that first named it (or the one it was bound at).
    position = {r.revision: i for i, r in enumerate(project.revisions, start=1)}
    stored = [
        (
            migrated[ref.attachment_id].artifact_id,
            migrated[ref.attachment_id].filename,
            data,
            {
                "filename": migrated[ref.attachment_id].filename,
                "extension": extension_of(migrated[ref.attachment_id].filename),
                "migrated_from": LEGACY_SOURCE,
                "legacy_attachment_id": ref.attachment_id,
                "legacy_stored_name": ref.stored_name,
                "named_in_brief": ref.named_in_brief,
            },
            position.get(ref.first_revision, len(project.revisions)),
        )
        for ref, data in found
    ]
    written = StudyWorkspaceRepository(session).import_migrated(
        scope,
        store,
        revisions=[
            (rewrite_attachments(r.content, migrated), r.analysis, migrated_reason(r.reason))
            for r in project.revisions
        ],
        files=stored,
        state=ContentState.MIGRATED,
        lineage=_lineage(
            report,
            actor_id=scope.actor_id,
            extra={
                "unit_title": project.title,
                "unit_status": project.status,
                "unit_trashed": report.unit_trashed,
                "revisions": [
                    {
                        "aia_revision": i,
                        "unit_revision": r.revision,
                        "unit_revision_id": r.revision_id,
                        "unit_created_at": r.created_at,
                        "unit_reason": r.reason,
                        "unit_content_sha256": r.content_sha256,
                    }
                    for i, r in enumerate(project.revisions, start=1)
                ],
                "files": {f.attachment_id: f.artifact_id for f in migrated.values()},
                "files_missing": missing,
                "files_mismatched": mismatched,
            },
        ),
    )
    report.migrated_revisions = len(written)
    problems = validate_migration(project.revisions, written, migrated)
    if problems:
        report.problems = problems
        raise _Invalid(problems)
    report.applied = True


def _one(
    sessions: sessionmaker[Session],
    report: StudyMigration,
    *,
    actor_id: str,
    unit: UnitProjectStore,
    files: UnitAttachmentFiles | None,
    store: ArtifactStore,
    apply: bool,
    recover_missing: bool,
) -> None:
    """One waiting Study, in its own session and transaction."""
    with sessions() as session:
        try:
            scope = ScopeResolver(session).study_context(
                AuthenticatedPrincipal(user_id=actor_id, organization_id=report.organization_id),
                study_id=report.study_id,
                require=Permission.EDIT_STUDY,
            )
        except ScopeDenied as exc:
            session.commit()  # the resolver's access-audit record of the refusal
            report.reason = f"the operator may not edit this Study ({exc.reason})"
            return
        study = session.get(StudyRow, report.study_id)
        if study is None or study.kind != StudyKind.RESEARCH.value:
            report.reason = "not a research Study"
            return
        if not scope.study_status.accepts_work:
            report.reason = f"the Study is {scope.study_status.value}: reopen it to migrate"
            return
        project = unit.project(report.unit_project_id) if report.unit_project_id else None
        try:
            if project is not None:
                _migrate(session, scope, report, project, files=files, store=store, apply=apply)
            elif recover_missing:
                _recover(session, scope, report, store=store, apply=apply)
            else:
                report.reason = (
                    "the unit project is not in this copy; once the copy is known to be "
                    "complete, recover_missing decides RECOVERED or UNRECOVERABLE"
                )
        except _Invalid:
            session.rollback()
            report.outcome = MigrationOutcome.NOT_MIGRATED
            report.reason = "what was written did not match the source; rolled back"
            report.applied = False
            return
        except (WorkspaceConflict, ScopeDenied, ValueError, StorageError) as exc:
            session.rollback()
            report.outcome = MigrationOutcome.NOT_MIGRATED
            report.reason = f"{type(exc).__name__}: {exc}"
            report.applied = False
            return
        if apply:
            session.commit()
        else:
            session.rollback()


def migrate_unit_workspaces(
    sessions: sessionmaker[Session],
    *,
    store: ArtifactStore,
    unit: UnitProjectStore,
    files: UnitAttachmentFiles | None,
    actor_email: str,
    apply: bool = False,
    recover_missing: bool = False,
    only: set[str] | None = None,
) -> MigrationReport:
    """Migrate (or, without ``apply``, plan) every Study waiting for its 18.6.6 content.

    ``only`` limits the run to those Study ids. Raises :class:`MigrationRefused`
    when ``actor_email`` is not an active AIA user.
    """
    with sessions() as session:
        actor_id = _actor(session, actor_email)
        bindings = StudyWorkspaceRepository(session).unit_bindings()
    waiting = [b for b in bindings if b[3] is ContentState.AWAITING_MIGRATION]
    studies: list[StudyMigration] = []
    for study_id, organization_id, unit_project_id, _ in waiting:
        if only is not None and study_id not in only:
            continue
        report = StudyMigration(
            study_id=study_id,
            organization_id=organization_id,
            unit_project_id=unit_project_id,
            outcome=MigrationOutcome.NOT_MIGRATED,
        )
        studies.append(report)
        _one(
            sessions,
            report,
            actor_id=actor_id,
            unit=unit,
            files=files,
            store=store,
            apply=apply,
            recover_missing=recover_missing,
        )
    bound = {b[2] for b in bindings if b[2]}
    return MigrationReport(
        applied=apply,
        recover_missing=recover_missing,
        store=str(unit.source),
        attachments_dir=str(files.directory) if files is not None else None,
        actor=actor_email.strip().lower(),
        studies_awaiting=len(waiting),
        studies=studies,
        done_before=[
            DoneBefore(study_id=b[0], unit_project_id=b[2], state=b[3].value)
            for b in bindings
            if b[3] is not ContentState.AWAITING_MIGRATION
        ],
        unit_projects_not_bound=[s for s in unit.summaries() if s.project_id not in bound],
    )
