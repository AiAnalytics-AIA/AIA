from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "results_registry.sqlite"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH); cx.row_factory = sqlite3.Row
    cx.executescript('''
      CREATE TABLE IF NOT EXISTS results(
        result_id TEXT PRIMARY KEY, project_id TEXT, project_type TEXT, title TEXT NOT NULL,
        created_at TEXT NOT NULL, origin TEXT NOT NULL, status TEXT NOT NULL,
        eligible_for_learning INTEGER NOT NULL DEFAULT 0,
        artifact_refs_json TEXT NOT NULL DEFAULT '[]', metadata_json TEXT NOT NULL DEFAULT '{}', note TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_results_project ON results(project_id);
    '''); cx.commit(); return cx


def register_result(*, project_id: str, project_type: str, title: str, origin: str,
                    status: str = "COMPLETED", eligible_for_learning: bool = False,
                    artifact_refs: list[Any] | None = None, metadata: dict[str, Any] | None = None,
                    note: str = "") -> dict[str, Any]:
    rid = "RES-" + hashlib.sha256((project_id + origin + title).encode()).hexdigest()[:14]
    cx = _connect()
    try:
        cx.execute('''INSERT OR REPLACE INTO results(result_id,project_id,project_type,title,created_at,origin,status,
                    eligible_for_learning,artifact_refs_json,metadata_json,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                   (rid, project_id, project_type, title, _now(), origin, status, int(bool(eligible_for_learning)),
                    json.dumps(artifact_refs or [], ensure_ascii=False, default=str), json.dumps(metadata or {}, ensure_ascii=False, default=str), note))
        cx.commit()
    finally: cx.close()
    return get_result(rid)


def get_result(result_id: str) -> dict[str, Any]:
    cx = _connect()
    try: r = cx.execute("SELECT * FROM results WHERE result_id=?", (result_id,)).fetchone()
    finally: cx.close()
    if not r: raise KeyError(result_id)
    d = dict(r); d["eligible_for_learning"] = bool(d["eligible_for_learning"])
    for old, new, default in [("artifact_refs_json", "artifact_refs", []), ("metadata_json", "metadata", {})]:
        try: d[new] = json.loads(d.pop(old) or json.dumps(default))
        except Exception: d[new] = default
    return d


def list_results(limit: int = 300) -> list[dict[str, Any]]:
    cx = _connect()
    try: rows = cx.execute("SELECT result_id FROM results ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
    finally: cx.close()
    return [get_result(r["result_id"]) for r in rows]


def sync_project_store() -> dict[str, int]:
    """Read completed project metadata into registry. No learning/calibration side effect."""
    from project_store import ProjectStore
    ps = ProjectStore(ROOT / "data" / "project_store.sqlite")
    added = 0
    try:
        for row in ps.list(500, include_archived=True):
            if str(row.get("status") or "").upper() != "COMPLETED":
                continue
            pid = str(row.get("project_id") or "")
            snap = ps.get(pid) or {}; project = snap.get("project") or {}; analysis = snap.get("analysis") or {}
            ptype = str(row.get("project_type") or "research")
            register_result(project_id=pid, project_type=ptype, title=str(row.get("title") or project.get("title") or pid),
                            origin="PROJECT_STORE", eligible_for_learning=False,
                            metadata={"revision": row.get("revision"), "synthetic": True,
                                      "executive_answer": analysis.get("executive_answer") if isinstance(analysis, dict) else None},
                            note="Syntetický projektový výsledek není validační pravda a sám nekalibruje populaci.")
            added += 1
    finally: ps.close()
    return {"synced": added}


def sync_showcase_demos() -> dict[str, int]:
    try:
        from demo_showcase import project_catalog
        rows = project_catalog()
    except Exception:
        rows = []
    added = 0
    for x in rows:
        pid = str(x.get("project_id") or "")
        if not pid: continue
        register_result(project_id=pid, project_type=str(x.get("project_type") or "research"),
                        title=str(x.get("title") or pid), origin="DEMO", eligible_for_learning=False,
                        metadata={"demo": True, "sample": x.get("sample"), "domain": x.get("domain")},
                        note="Ilustrační DEMO – nikdy se nepoužívá ke kalibraci LIVE populace.")
        added += 1
    return {"synced": added}


def summary(sync: bool = False) -> dict[str, Any]:
    if sync:
        try: sync_project_store()
        except Exception: pass
        try: sync_showcase_demos()
        except Exception: pass
    rows = list_results(1000)
    return {"results": len(rows), "eligible_for_learning": sum(1 for x in rows if x["eligible_for_learning"]),
            "demo": sum(1 for x in rows if x["origin"] == "DEMO"),
            "project_store": sum(1 for x in rows if x["origin"] == "PROJECT_STORE"),
            "contract": "Synthetic/project/demo results never auto-calibrate LIVE."}
