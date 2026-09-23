"""Source-use governance adapter.

Licensing/rights were reviewed outside this workstream according to the project
owner. The historic per-source ledger remains in the repository for traceability,
but this handoff release does not re-adjudicate it and does not block runtime on
that stale template. Set PROJECT_POLICY.json -> licensing.mode="ledger" if a future
team wants to reactivate repository-local fail-closed approval checks.

This module is not legal advice.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pandas as pd

ROOT = Path(__file__).resolve().parent
DICT_PATH = ROOT / "DIMENSION_DATA_DICTIONARY_v2.csv"
APPROVALS_PATH = ROOT / "LEGAL_APPROVALS.csv"
POLICY_PATH = ROOT / "PROJECT_POLICY.json"
BASE_SOURCE_KEY = "BASE_PANEL_BACKBONE"
CLEARED = "CLEARED_COMMERCIAL"
REVIEW = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED"


def _dictionary() -> pd.DataFrame:
    return pd.read_csv(DICT_PATH)


def _policy() -> dict[str, Any]:
    if not POLICY_PATH.exists():
        return {"licensing": {"mode": "ledger"}}
    try:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Invalid PROJECT_POLICY.json: {exc}") from exc


def load_approvals(path: str | Path = APPROVALS_PATH) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Chybí legal approval ledger: {p}")
    df = pd.read_csv(p).fillna("")
    required = {"source_key", "status", "approved_by", "approved_at", "scope", "evidence"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"LEGAL_APPROVALS.csv chybí sloupce: {sorted(missing)}")
    return df


def sources_for_topics(topics: list[str] | None, *, allow_own_estimates: bool = False) -> list[str]:
    df = _dictionary()
    if topics:
        wanted = set(topics)
        df = df[df["topics"].fillna("").map(lambda s: bool(set(str(s).split("|")) & wanted))]
    if not allow_own_estimates:
        df = df[df["source_role"] != "OWN_ESTIMATE"]
    return [BASE_SOURCE_KEY] + sorted({str(x).strip() for x in df["source"] if str(x).strip()})


def audit_legal(*, use_case: str = "internal", topics: list[str] | None = None,
                allow_own_estimates: bool = False,
                approvals_path: str | Path = APPROVALS_PATH,
                force_ledger: bool = False) -> dict[str, Any]:
    use_case = str(use_case).lower().strip()
    if use_case not in {"internal", "research", "commercial"}:
        raise ValueError("use_case musí být internal | research | commercial")
    policy = _policy()
    lic = policy.get("licensing") or {}
    mode = "ledger" if force_ledger else str(lic.get("mode", "ledger")).strip().lower()
    needed = sources_for_topics(topics, allow_own_estimates=allow_own_estimates)

    if mode == "external_owner_cleared":
        required_meta={k:str(lic.get(k,"")).strip() for k in ("cleared_by","cleared_at","evidence_ref")}
        evidence_present=all(required_meta.values())
        if use_case == "commercial":
            mode="ledger"
        elif evidence_present:
            return {"use_case":use_case,"mode":"external_owner_cleared","needed_sources":len(needed),"cleared_sources":None,"unresolved_sources":[],"fail":[],"warnings":[],"status":"PASS","external_clearance":True,"licensing_evidence_present":True,"clearance":required_meta,"note":str(lic.get("note","Rights/licensing handled outside this repository."))}
        else:
            unresolved=[{"source_key":src,"status":REVIEW,"cleared":False} for src in needed]
            return {"use_case":use_case,"mode":"external_owner_cleared","needed_sources":len(needed),"cleared_sources":0,"unresolved_sources":unresolved,"fail":[],"warnings":unresolved,"status":"REVIEW_REQUIRED","external_clearance":False,"licensing_evidence_present":False,"missing_clearance_fields":[k for k,v in required_meta.items() if not v],"note":"External-owner clearance is not evidenced; review required."}

    approvals = load_approvals(approvals_path)
    status = {str(r.source_key): str(r.status).strip().upper() for r in approvals.itertuples()}
    rows = []
    for src in needed:
        st = status.get(src, REVIEW)
        rows.append({"source_key": src, "status": st, "cleared": st == CLEARED})
    unresolved = [r for r in rows if not r["cleared"]]
    fail = unresolved if use_case == "commercial" else []
    warnings = unresolved if use_case != "commercial" else []
    return {
        "use_case": use_case,
        "mode": "ledger",
        "needed_sources": len(rows),
        "cleared_sources": sum(r["cleared"] for r in rows),
        "unresolved_sources": unresolved,
        "fail": fail,
        "warnings": warnings,
        "status": "PASS" if not fail else "BLOCKED",
        "external_clearance": False,
        "licensing_evidence_present": bool(rows) and not unresolved,
        "note": "Repository-local source approval ledger is active.",
    }


def assert_legal_ready(**kwargs) -> dict[str, Any]:
    out = audit_legal(**kwargs)
    if out["fail"]:
        names = ", ".join(x["source_key"] for x in out["fail"][:8])
        more = "…" if len(out["fail"]) > 8 else ""
        raise RuntimeError("Commercial run blocked: unresolved source rights: " + names + more)
    return out
