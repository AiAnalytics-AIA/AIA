"""A copy of the 18.6.6 unit's project store, read and never written (ADR 0018, decision 2).

The migration reads a **copy** of ``/app/data/project_store.sqlite`` -- the WAL-safe
one ``deploy/reference/bin/backup-legacy-state.py`` writes, either the database itself
or the ZIP it streams -- and a copy of ``/app/data/ui_uploads/project_attachments``.
Nothing here can change either:

* the database is opened ``mode=ro&immutable=1``: read-only, and without the WAL or
  lock files a live database would need, which is right for a copy nobody writes and
  refuses anything else;
* a ZIP is unpacked into a temporary directory that is removed on close;
* a file is read by its base name only, inside the directory it was given.

The unit's own ``ProjectStore`` is deliberately not used: opening it runs the unit's
schema script and migrations, which write.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import TracebackType
from typing import Any

from ..domain.workspace_migration import (
    UnitAttachment,
    UnitProject,
    UnitProjectSummary,
    UnitRevision,
)

__all__ = ["UnitAttachmentFiles", "UnitProjectStore"]

_DATABASE: str = "project_store.sqlite"


def _loads(raw: Any, default: Any) -> Any:
    try:
        value = json.loads(raw or "")
    except (TypeError, ValueError):
        return default
    return value if isinstance(value, type(default)) else default


class UnitProjectStore:
    """Read access to a copy of the unit's project store. Use as a context manager."""

    def __init__(self, path: Path) -> None:
        self.source = path
        self._scratch: Path | None = None
        database = path
        if zipfile.is_zipfile(path):
            self._scratch = Path(tempfile.mkdtemp(prefix="aia-unit-store-"))
            with zipfile.ZipFile(path) as bundle:
                if _DATABASE not in bundle.namelist():
                    self._drop_scratch()
                    raise FileNotFoundError(f"{path} holds no {_DATABASE}")
                bundle.extract(_DATABASE, self._scratch)
            database = self._scratch / _DATABASE
        if not database.is_file():
            self._drop_scratch()
            raise FileNotFoundError(database)
        wal = database.with_name(database.name + "-wal")
        shm = database.with_name(database.name + "-shm")
        if (wal.is_file() and wal.stat().st_size > 0) or shm.exists():
            # immutable=1 ignores a WAL and takes no lock, so a database the unit
            # still has open would read stale or torn: only a copy is read.
            self._drop_scratch()
            raise ValueError(
                f"{database} has a write-ahead log or shared-memory file beside it: it "
                "is a live database. Read a copy made with "
                "deploy/reference/bin/backup-legacy-state.py."
            )
        uri = database.resolve().as_uri() + "?mode=ro&immutable=1"
        self._cx = sqlite3.connect(uri, uri=True)
        self._cx.row_factory = sqlite3.Row
        tables = {
            r[0] for r in self._cx.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = {"projects", "project_revisions", "project_attachments"} - tables
        if missing:
            self.close()
            raise ValueError(f"not a unit project store: no {', '.join(sorted(missing))}")
        self._columns = {r[1] for r in self._cx.execute("PRAGMA table_info(projects)")}

    def __enter__(self) -> UnitProjectStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _drop_scratch(self) -> None:
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None

    def close(self) -> None:
        self._cx.close()
        self._drop_scratch()

    def _column(self, row: sqlite3.Row, name: str) -> Any:
        return row[name] if name in self._columns else None

    def project(self, project_id: str) -> UnitProject | None:
        """The unit project with its every revision, oldest first, and its bound files."""
        row = self._cx.execute(
            "SELECT * FROM projects WHERE project_id=?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        revisions = tuple(
            UnitRevision(
                revision=int(r["revision"]),
                revision_id=r["revision_id"],
                created_at=r["created_at"],
                reason=str(r["reason"] or ""),
                content_sha256=r["content_sha256"],
                content=_loads(r["project_json"], {}),
                analysis=_loads(r["analysis_json"], {}),
            )
            for r in self._cx.execute(
                "SELECT * FROM project_revisions WHERE project_id=? ORDER BY revision",
                (project_id,),
            )
        )
        attachments = tuple(
            UnitAttachment(
                attachment_id=str(a["attachment_id"]),
                filename=str(a["filename"]),
                stored_name=PurePosixPath(str(a["stored_path"]).replace("\\", "/")).name,
                sha256=str(a["sha256"]),
                size_bytes=int(a["size_bytes"] or 0),
                revision=a["revision"],
                created_at=a["created_at"],
            )
            for a in self._cx.execute(
                "SELECT * FROM project_attachments WHERE project_id=? ORDER BY created_at",
                (project_id,),
            )
        )
        return UnitProject(
            project_id=project_id,
            title=str(row["title"] or ""),
            project_type=str(self._column(row, "project_type") or "research"),
            status=str(self._column(row, "status") or ""),
            current_revision=int(row["current_revision"] or 0),
            deleted_at=self._column(row, "deleted_at"),
            revisions=revisions,
            attachments=attachments,
        )

    def summaries(self) -> list[UnitProjectSummary]:
        """Every project in the store, newest first: the report's list of what is left."""
        return [
            UnitProjectSummary(
                project_id=str(r["project_id"]),
                title=str(r["title"] or ""),
                project_type=str(self._column(r, "project_type") or "research"),
                status=str(self._column(r, "status") or ""),
                current_revision=int(r["current_revision"] or 0),
                modified_at=r["modified_at"],
            )
            for r in self._cx.execute("SELECT * FROM projects ORDER BY modified_at DESC")
        ]


class UnitAttachmentFiles:
    """A copy of the unit's ``project_attachments`` directory, read by base name only."""

    def __init__(self, directory: Path) -> None:
        if not directory.is_dir():
            raise NotADirectoryError(directory)
        self.directory = directory.resolve()

    def read(self, stored_name: str) -> bytes | None:
        """The file's bytes, or ``None`` when it is not there. Never outside the directory."""
        name = PurePosixPath(str(stored_name).replace("\\", "/")).name
        if not name or name in {".", ".."}:
            return None
        path = (self.directory / name).resolve()
        if path.parent != self.directory or not path.is_file():
            return None
        return path.read_bytes()

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
