"""``python -m aia_executors.legacy_workspace``: migrate Studies' content out of 18.6.6.

The explicit, one-off migration of ADR 0018 (decision 2). Every Study still
``AWAITING_MIGRATION`` gets its bound 18.6.6 project -- every revision, every file
its brief names or the unit bound to it -- as its AIA working content, from a
**copy** of the unit's state:

    --store        the unit's project store: the ZIP that
                   ``deploy/reference/bin/backup-legacy-state.py`` streams, or one
                   ``project_store.sqlite`` copied from it
    --attachments  a copy of ``/app/data/ui_uploads/project_attachments``
    --as           the AIA person the migration acts as; each Study is opened through
                   the scope that person holds on it, so a Study they may not edit is
                   reported and left waiting

Without ``--apply`` it is a dry run: nothing is written and the report says what
would happen. ``--recover-missing`` says the copy is complete, so a Study whose
unit project is not in it becomes RECOVERED (from its newest Design Revision) or
UNRECOVERABLE; without it such a Study stays waiting. ``--study`` limits the run.

Reads ``DATABASE_URL`` (PostgreSQL) and ``AIA_STORAGE_*``. The full report is JSON,
to ``--report`` or standard output; a summary goes to standard error. Exits 0 when
every Study it looked at is (or, in a dry run, would be) migrated, recovered or
marked unrecoverable; 3 when some stay waiting (``NOT_MIGRATED``, each with its
reason); 2 when it could not start. Nothing it does reads the running unit or
writes its files. The runbook is ``deploy/develop/README.md`` § Migrating 18.6.6
content.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aia_core.application.workspace_migration import MigrationRefused, migrate_unit_workspaces
from aia_core.domain.workspace_migration import MigrationOutcome, MigrationReport
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store
from aia_core.infrastructure.unit_project_store import UnitAttachmentFiles, UnitProjectStore

from ._db import engine_from_env

__all__ = ["main", "summary"]


def summary(report: MigrationReport) -> list[str]:
    """The report in a few lines, for the operator's terminal."""
    mode = "applied" if report.applied else "dry run: nothing written"
    lines = [
        f"18.6.6 workspace migration ({mode}), as {report.actor}",
        f"  {report.studies_awaiting} awaiting, {len(report.studies)} looked at, "
        f"{len(report.done_before)} done before",
    ]
    for outcome in MigrationOutcome:
        n = report.count(outcome)
        if n:
            lines.append(f"  {outcome.value}: {n}")
    for study in report.studies:
        files = len(study.files_migrated)
        left = len(study.files_missing) + len(study.files_mismatched)
        state = "applied" if study.applied else "not applied"
        lines.append(
            f"  - {study.study_id} <- {study.unit_project_id or '(none)'}: {study.outcome.value}, "
            f"{state}; {study.source_revisions} revisions, {files} files"
            + (f", {left} files not brought" if left else "")
            + (f"; {study.reason}" if study.reason else "")
        )
        lines.extend(f"      ! {p}" for p in study.problems)
    if report.unit_projects_not_bound:
        lines.append(
            f"  {len(report.unit_projects_not_bound)} unit projects no Study refers to "
            "(kept in the unit's volume; listed in the report)"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--store", type=Path, required=True, help="copy of the unit's project store"
    )
    parser.add_argument("--attachments", type=Path, help="copy of the unit's project_attachments")
    parser.add_argument("--as", dest="actor", required=True, help="the AIA person's email")
    parser.add_argument("--apply", action="store_true", help="write; without it, a dry run")
    parser.add_argument(
        "--recover-missing",
        action="store_true",
        help="the copy is complete: a project missing from it is gone",
    )
    parser.add_argument(
        "--study", action="append", default=None, help="only this Study (repeatable)"
    )
    parser.add_argument("--report", default="-", help="where the JSON report goes; - is stdout")
    args = parser.parse_args(argv)

    try:
        files = UnitAttachmentFiles(args.attachments) if args.attachments else None
        unit = UnitProjectStore(args.store)
    except (OSError, ValueError) as exc:
        print(f"cannot read the copy: {exc}", file=sys.stderr)
        return 2
    engine, sessions = engine_from_env()
    try:
        with unit:
            report = migrate_unit_workspaces(
                sessions,
                store=build_artifact_store(StorageSettings.from_env()),
                unit=unit,
                files=files,
                actor_email=args.actor,
                apply=args.apply,
                recover_missing=args.recover_missing,
                only=set(args.study) if args.study else None,
            )
    except MigrationRefused as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        engine.dispose()

    body = report.model_dump_json(indent=2)
    if args.report == "-":
        print(body)
    else:
        Path(args.report).write_text(body + "\n", encoding="utf-8")
    for line in summary(report):
        print(line, file=sys.stderr)
    return 3 if report.count(MigrationOutcome.NOT_MIGRATED) else 0


if __name__ == "__main__":
    raise SystemExit(main())
