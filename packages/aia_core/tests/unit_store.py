"""A copy of an 18.6.6 project store, written as the unit writes one: for tests only.

The layout is the unit's own -- its ``SCHEMA`` and the columns its migrations add --
read out of ``legacy/npc-panel-18.6.6/app/project_store.py`` as text, through the
AST: no unit code is imported or run. Rows are written as the unit's
``ProjectStore`` writes them: content hashed by its ``_sha``, stored by
``json.dumps(ensure_ascii=False, default=str)``, revisions numbered 1, 2, 3 with
``REV-`` ids and local timestamps, trash as ``move_to_trash`` leaves it, and each
file as ``ui_server.save_project_attachment`` stores and describes it
(``ATT-<14 hex>_<safe name>``). Every value is fictional.

Loaded by path (the ``unit_store`` fixture), never imported by module name: both
test directories load it.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[3]
UNIT_STORE_SOURCE = REPO / "legacy/npc-panel-18.6.6/app/project_store.py"


def unit_schema() -> tuple[str, dict[str, list[str]]]:
    """The unit's ``SCHEMA`` script and, per table, the columns ``_migrate_178x`` adds."""
    tree = ast.parse(UNIT_STORE_SOURCE.read_text(encoding="utf-8"))
    schema = next(
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SCHEMA" for t in node.targets)
        and isinstance(node.value, ast.Constant)
    )
    columns: dict[str, list[str]] = {}
    migrate = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_migrate_178x"
    )
    for loop in (n for n in migrate.body if isinstance(n, ast.For)):
        call = loop.body[0].value  # _add_col(self.cx, '<table>', spec)
        assert isinstance(call, ast.Call)
        table = call.args[1]
        assert isinstance(table, ast.Constant)
        columns[str(table.value)] = list(ast.literal_eval(loop.iter))
    return schema, columns


def unit_sha(obj: Any) -> str:
    """The unit's ``_sha``, as ``project_store.py`` writes it."""
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class UnitStore:
    """Writes ``project_store.sqlite`` and ``project_attachments/`` under ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.database = root / "project_store.sqlite"
        self.uploads = root / "ui_uploads" / "project_attachments"
        self.uploads.mkdir(parents=True, exist_ok=True)
        schema, columns = unit_schema()
        self.cx = sqlite3.connect(self.database)
        self.cx.row_factory = sqlite3.Row
        self.cx.executescript(schema)
        for table, specs in columns.items():
            have = {r[1] for r in self.cx.execute(f"PRAGMA table_info({table})")}
            for spec in specs:
                if spec.split()[0] not in have:
                    self.cx.execute(f"ALTER TABLE {table} ADD COLUMN {spec}")
        self.cx.commit()

    def close(self) -> None:
        self.cx.close()

    def save(
        self,
        project_id: str,
        content: dict[str, Any],
        *,
        analysis: dict[str, Any] | None = None,
        reason: str = "autosave",
        project_type: str = "research",
        sha: str | None = None,
    ) -> int:
        """One more revision, as ``_save_normalized`` writes it; ``sha`` forges the hash."""
        now = _now()
        row = self.cx.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            revision, parent = 1, None
            self.cx.execute(
                "INSERT INTO projects(project_id,title,parent_project_id,created_at,modified_at,"
                "current_revision,project_type,status,current_stage,preferred_provider,"
                "provider_policy,max_api_cost_usd,runtime_version,archived) "
                "VALUES(?,?,?,?,?,?,?,'DRAFT',?,?,'CLAUDE_CODE_ONLY',10.0,?,0)",
                (
                    project_id,
                    content.get("title", ""),
                    None,
                    now,
                    now,
                    1,
                    project_type,
                    "brief",
                    "claude_code_subscription",
                    "18.6.6",
                ),
            )
        else:
            parent = int(row["current_revision"])
            revision = parent + 1
        self.cx.execute(
            "INSERT INTO project_revisions(project_id,revision,created_at,content_sha256,"
            "project_json,analysis_json,questionnaire_version,panel_version,model,reason,"
            "revision_id,parent_revision,branch_id,metadata_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                project_id,
                revision,
                now,
                sha or unit_sha(content),
                json.dumps(content, ensure_ascii=False, default=str),
                json.dumps(analysis or {}, ensure_ascii=False, default=str),
                str(content.get("schema_version", 2)),
                "",
                str(content.get("model", "")),
                reason,
                "REV-" + uuid.uuid4().hex[:16],
                parent,
                None,
                "{}",
            ),
        )
        self.cx.execute(
            "UPDATE projects SET title=?,modified_at=?,current_revision=?,project_type=? "
            "WHERE project_id=?",
            (content.get("title", ""), now, revision, project_type, project_id),
        )
        self.cx.commit()
        return revision

    def attach(
        self,
        filename: str,
        data: bytes,
        *,
        project_id: str | None = None,
        revision: int | None = None,
        text: str = "",
    ) -> dict[str, Any]:
        """Store a file as ``save_project_attachment`` does; bound when given a project."""
        name = Path(filename).name
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)[:160] or "attachment"
        aid = "ATT-" + hashlib.sha256(data + str(time.time_ns()).encode()).hexdigest()[:14]
        stored = f"{aid}_{safe}"
        path = self.uploads / stored
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        ext = Path(safe).suffix.lower()
        if project_id:
            self.cx.execute(
                "INSERT OR REPLACE INTO project_attachments VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    aid,
                    project_id,
                    revision,
                    safe,
                    f"/app/data/ui_uploads/project_attachments/{stored}",
                    digest,
                    len(data),
                    _now(),
                    json.dumps({"extension": ext, "text_extracted": bool(text)}),
                ),
            )
            self.cx.commit()
        return {
            "attachment_id": aid,
            "filename": safe,
            "stored_name": stored,
            "size_bytes": len(data),
            "sha256": digest,
            "kind": "file",
            "extension": ext,
            "text_extracted": bool(text),
            "context_excerpt": text[:6000],
            "project_id": project_id or None,
            "download_url": "/project-attachments/" + quote(stored),
        }

    def trash(self, project_id: str) -> None:
        """As ``move_to_trash`` leaves a project."""
        now = _now()
        self.cx.execute(
            "UPDATE projects SET pre_trash_status=status,status='TRASHED',archived=1,"
            "deleted_at=?,modified_at=? WHERE project_id=?",
            (now, now, project_id),
        )
        self.cx.commit()


def brief(title: str, goal: str, attachments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A research project as the unit's ``normalize_project`` leaves one, cut to what matters."""
    return {
        "schema_version": 2,
        "title": title,
        "goal": goal,
        "study_type": "custom",
        "briefing": {
            "product_description": "Fiktivní ranní nápoj",
            "situation": "",
            "attachments": list(attachments or []),
            "attachments_context": "",
        },
        "sections": [],
        "model": "sonnet",
    }
