from __future__ import annotations

"""STATIC/LIVE population registry for NPC Panel 18.5.

STATIC is an immutable reference snapshot. LIVE is the runtime population used by
research and simulation unless a project explicitly pins STATIC.  Library imports
never mutate LIVE automatically; a new LIVE version must be explicitly promoted or
an approved evidence overlay must be explicitly registered.
"""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "population_registry.sqlite"
STATIC_PATH = ROOT / "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz"
LIVE_BASE_PATH = ROOT / "FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _shape(path: Path) -> tuple[int, int]:
    try:
        import pandas as pd
        df = pd.read_csv(path, nrows=5, low_memory=False)
        cols = len(df.columns)
        # gzip line counting is inexpensive at this size and avoids holding the panel.
        import gzip
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
            rows = max(0, sum(1 for _ in f) - 1)
        return rows, cols
    except Exception:
        return 0, 0


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH)
    cx.row_factory = sqlite3.Row
    cx.executescript('''
      CREATE TABLE IF NOT EXISTS populations(
        population_id TEXT PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
        immutable INTEGER NOT NULL DEFAULT 0, current_version_id TEXT,
        created_at TEXT NOT NULL, description TEXT
      );
      CREATE TABLE IF NOT EXISTS population_versions(
        version_id TEXT PRIMARY KEY, population_id TEXT NOT NULL, created_at TEXT NOT NULL,
        panel_path TEXT NOT NULL, sha256 TEXT NOT NULL, rows INTEGER, columns INTEGER,
        parent_version_id TEXT, status TEXT NOT NULL, evidence_refs_json TEXT NOT NULL DEFAULT '[]',
        calibration_ids_json TEXT NOT NULL DEFAULT '[]', notes TEXT,
        FOREIGN KEY(population_id) REFERENCES populations(population_id)
      );
      CREATE TABLE IF NOT EXISTS calibration_events(
        event_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, source_ref TEXT,
        proposal_id TEXT, dimension_id TEXT, change_type TEXT NOT NULL,
        status TEXT NOT NULL, spec_json TEXT NOT NULL DEFAULT '{}', applied_version_id TEXT,
        note TEXT
      );
    ''')
    cx.commit()
    _bootstrap(cx)
    return cx


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except Exception:
        return str(path.resolve())


def _resolve_registered_path(stored: str, expected_sha256: str = "") -> Path:
    raw=Path(str(stored or ""))
    candidates=[]
    if raw.is_absolute(): candidates.append(raw)
    else: candidates.append(ROOT/raw)
    if raw.name: candidates.append(ROOT/raw.name)
    seen=set()
    for candidate in candidates:
        key=str(candidate)
        if key in seen: continue
        seen.add(key)
        if not candidate.is_file(): continue
        if expected_sha256:
            try:
                if _sha(candidate)!=expected_sha256: continue
            except Exception:
                continue
        return candidate.resolve()
    raise FileNotFoundError(str(stored))


def _repair_registered_paths(cx: sqlite3.Connection) -> None:
    rows=cx.execute("SELECT version_id,panel_path,sha256 FROM population_versions").fetchall()
    changed=False
    for row in rows:
        stored=str(row["panel_path"] or "")
        try: resolved=_resolve_registered_path(stored,str(row["sha256"] or ""))
        except FileNotFoundError: continue
        portable=_portable_path(resolved)
        if portable!=stored:
            cx.execute("UPDATE population_versions SET panel_path=? WHERE version_id=?",(portable,row["version_id"]))
            changed=True
    if changed: cx.commit()


def _bootstrap(cx: sqlite3.Connection) -> None:
    for pid, kind, label, immutable, path, desc in [
        ("CZ_STATIC_REFERENCE", "STATIC", "Česká populace · statická reference", 1, STATIC_PATH,
         "Neměnný referenční snapshot pro srovnání, audit a reprodukci."),
        ("CZ_LIVE", "LIVE", "Česká populace · LIVE", 0, LIVE_BASE_PATH,
         "Dynamická runtime populace. Mění se pouze explicitním schváleným povýšením/verzí; upload do Library ji sám nemění."),
    ]:
        exists = cx.execute("SELECT 1 FROM populations WHERE population_id=?", (pid,)).fetchone()
        if exists:
            continue
        if not path.is_file():
            continue
        digest = _sha(path); rows, cols = _shape(path)
        vid = f"{pid}-BASE-{digest[:12]}"
        cx.execute("INSERT INTO populations VALUES(?,?,?,?,?,?,?)", (pid, kind, label, immutable, vid, _now(), desc))
        cx.execute("INSERT INTO population_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (vid, pid, _now(), _portable_path(path), digest, rows, cols, None, "ACTIVE", "[]", "[]", "bootstrap"))
    cx.commit()
    _repair_registered_paths(cx)


def _loads(x: str, default: Any) -> Any:
    try:
        return json.loads(x or ("{}" if isinstance(default, dict) else "[]"))
    except Exception:
        return default


def _version_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    d = dict(row)
    d["evidence_refs"] = _loads(d.pop("evidence_refs_json", "[]"), [])
    d["calibration_ids"] = _loads(d.pop("calibration_ids_json", "[]"), [])
    return d


def get_population(kind: str = "LIVE") -> dict[str, Any]:
    want = str(kind or "LIVE").upper()
    pid = "CZ_STATIC_REFERENCE" if want.startswith("STATIC") else "CZ_LIVE"
    cx = _connect()
    try:
        p = cx.execute("SELECT * FROM populations WHERE population_id=?", (pid,)).fetchone()
        if not p:
            raise FileNotFoundError(f"Population {pid} není inicializována.")
        v = cx.execute("SELECT * FROM population_versions WHERE version_id=?", (p["current_version_id"],)).fetchone()
        out = dict(p); out["immutable"] = bool(out["immutable"]); out["current_version"] = _version_row(v)
        return out
    finally:
        cx.close()


def list_populations() -> list[dict[str, Any]]:
    return [get_population("STATIC"), get_population("LIVE")]


def panel_path_for(kind: str = "LIVE") -> Path:
    v = get_population(kind)["current_version"]
    if not v:
        raise FileNotFoundError(f"Population {kind} nemá aktivní verzi.")
    return _resolve_registered_path(str(v.get("panel_path") or ""), str(v.get("sha256") or ""))


def project_population_mode(project: dict[str, Any] | None) -> str:
    p = project or {}
    candidates = [p.get("population_mode"), (p.get("population") or {}).get("mode"),
                  (p.get("run_policy") or {}).get("population_mode")]
    for x in candidates:
        if str(x or "").upper().startswith("STATIC"):
            return "STATIC"
        if str(x or "").upper().startswith("LIVE"):
            return "LIVE"
    return "LIVE"


def project_population_context(project: dict[str, Any] | None) -> dict[str, Any]:
    mode = project_population_mode(project)
    pop = get_population(mode)
    return {"mode": mode, "population_id": pop["population_id"], "label": pop["label"],
            "immutable": pop["immutable"], "version": pop["current_version"]}


def propose_calibration(*, source_ref: str = "", proposal_id: str = "", dimension_id: str = "",
                        change_type: str = "overlay", spec: dict[str, Any] | None = None, note: str = "") -> dict[str, Any]:
    payload = json.dumps(spec or {}, ensure_ascii=False, sort_keys=True, default=str)
    eid = "CAL-" + hashlib.sha256((source_ref + proposal_id + dimension_id + payload + str(time.time_ns())).encode()).hexdigest()[:14]
    cx = _connect()
    try:
        cx.execute("INSERT INTO calibration_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (eid, _now(), source_ref, proposal_id, dimension_id, change_type, "PROPOSED", payload, None, note))
        cx.commit()
    finally:
        cx.close()
    return get_calibration(eid)


def get_calibration(event_id: str) -> dict[str, Any]:
    cx = _connect()
    try:
        r = cx.execute("SELECT * FROM calibration_events WHERE event_id=?", (event_id,)).fetchone()
    finally:
        cx.close()
    if not r:
        raise KeyError(event_id)
    d = dict(r); d["spec"] = _loads(d.pop("spec_json", "{}"), {})
    return d


def decide_calibration(event_id: str, decision: str) -> dict[str, Any]:
    decision = str(decision or "").upper()
    if decision not in {"APPROVE", "REJECT"}:
        raise ValueError("decision musí být APPROVE nebo REJECT")
    cur = get_calibration(event_id)
    if cur["status"] not in {"PROPOSED", "APPROVED"}:
        return cur
    status = "APPROVED" if decision == "APPROVE" else "REJECTED"
    cx = _connect()
    try:
        cx.execute("UPDATE calibration_events SET status=? WHERE event_id=?", (status, event_id)); cx.commit()
    finally:
        cx.close()
    return get_calibration(event_id)


def register_applied_overlay(*, event_id: str, live_version_id: str | None = None) -> dict[str, Any]:
    """Mark an approved evidence overlay as active for LIVE runtime metadata.

    This does not rewrite the panel file.  The overlay itself remains versioned in
    Data Library/audience_dimensions.  STATIC is never touched.
    """
    ev = get_calibration(event_id)
    if ev["status"] != "APPROVED":
        raise ValueError("Kalibrační událost musí být nejdřív schválena.")
    live = get_population("LIVE"); vid = live_version_id or live["current_version_id"]
    cx = _connect()
    try:
        v = cx.execute("SELECT * FROM population_versions WHERE version_id=? AND population_id='CZ_LIVE'", (vid,)).fetchone()
        if not v:
            raise KeyError(vid)
        ids = _loads(v["calibration_ids_json"], [])
        if event_id not in ids:
            ids.append(event_id)
        cx.execute("UPDATE population_versions SET calibration_ids_json=? WHERE version_id=?", (json.dumps(ids), vid))
        cx.execute("UPDATE calibration_events SET status='APPLIED',applied_version_id=? WHERE event_id=?", (vid, event_id))
        cx.commit()
    finally:
        cx.close()
    return get_calibration(event_id)


def promote_live_version(panel_path: str | Path, *, evidence_refs: list[str] | None = None,
                         calibration_ids: list[str] | None = None, notes: str = "") -> dict[str, Any]:
    """Explicitly promote an already-built panel snapshot to LIVE.

    No code path calls this automatically from source import.  It is intentionally a
    separate explicit operation so Library ingestion cannot silently change runtime.
    """
    p = Path(panel_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(str(p))
    if p.resolve() == STATIC_PATH.resolve():
        raise ValueError("Statický referenční snapshot nelze povýšit ani přepsat jako LIVE změnu.")
    digest = _sha(p); rows, cols = _shape(p); live = get_population("LIVE"); parent = live["current_version_id"]
    vid = "CZ_LIVE-" + digest[:12]
    cx = _connect()
    try:
        cx.execute("INSERT OR IGNORE INTO population_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (vid, "CZ_LIVE", _now(), str(p), digest, rows, cols, parent, "ACTIVE",
                    json.dumps(evidence_refs or [], ensure_ascii=False), json.dumps(calibration_ids or [], ensure_ascii=False), notes))
        cx.execute("UPDATE population_versions SET status='SUPERSEDED' WHERE population_id='CZ_LIVE' AND version_id<>? AND status='ACTIVE'", (vid,))
        cx.execute("UPDATE populations SET current_version_id=? WHERE population_id='CZ_LIVE'", (vid,)); cx.commit()
    finally:
        cx.close()
    return get_population("LIVE")


def population_quality() -> dict[str, Any]:
    import pandas as pd
    cal_path = ROOT / "CALIBRATION_REGISTRY.csv"
    cov_path = ROOT / "DOMAIN_EVIDENCE_COVERAGE.csv"
    oos_path = ROOT / "OUT_OF_SAMPLE_VALIDATION_v17_1.csv"
    corr_path = ROOT / "CORRELATION_MATRIX_QC_v17_1.csv"
    out: dict[str, Any] = {"calibration": {}, "coverage_gaps": [], "oos": {}, "relationships": []}
    if cal_path.is_file():
        c = pd.read_csv(cal_path).fillna("")
        out["calibration"] = {
            "dimensions": int(len(c)),
            "production_default": int((c["production_default"].astype(str).str.lower() == "true").sum()),
            "truth_available": int((c["truth_available"].astype(str).str.lower() == "true").sum()),
            "pending_anchor_only": int(c["calibration_status"].astype(str).str.contains("ANCHOR_ONLY_PENDING").sum()),
            "no_source_disabled": int(c["calibration_status"].astype(str).str.contains("NO_SOURCE_DISABLED").sum()),
            "unvalidated_joint": int((c["joint_validated"].astype(str).str.lower() != "true").sum()),
        }
    if cov_path.is_file():
        c = pd.read_csv(cov_path).fillna("")
        c = c.sort_values(["score", "topic"], ascending=[True, True])
        out["coverage_gaps"] = c.head(10).to_dict(orient="records")
    if oos_path.is_file():
        o = pd.read_csv(oos_path).fillna("")
        out["oos"] = {"checks": int(len(o)), "pass": int((o["status"] == "PASS").sum()), "fail": int((o["status"] == "FAIL").sum()),
                      "failed_checks": o[o["status"] == "FAIL"][["check_id", "description", "target", "observed", "abs_error_pp"]].to_dict(orient="records")}
    if corr_path.is_file():
        r = pd.read_csv(corr_path).fillna("")
        r["abs_r"] = pd.to_numeric(r["observed_r"], errors="coerce").abs()
        top = r.dropna(subset=["abs_r"]).sort_values("abs_r", ascending=False).head(12)
        out["relationships"] = top[["field_a", "field_b", "observed_r", "pair_type", "status"]].to_dict(orient="records")
    return out


def summary() -> dict[str, Any]:
    cx = _connect()
    try:
        events = cx.execute("SELECT status,COUNT(*) n FROM calibration_events GROUP BY status").fetchall()
        versions = cx.execute("SELECT population_id,COUNT(*) n FROM population_versions GROUP BY population_id").fetchall()
    finally:
        cx.close()
    return {"populations": list_populations(), "quality": population_quality(),
            "calibration_events": {r["status"]: r["n"] for r in events},
            "version_counts": {r["population_id"]: r["n"] for r in versions},
            "default_runtime": "LIVE", "import_mutates_live": False,
            "static_immutable": True}
