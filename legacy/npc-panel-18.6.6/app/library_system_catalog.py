from __future__ import annotations

"""Unified system-source catalog for NPC Panel 18.5.

The old UI exposed only rows manually uploaded to knowledge_library.sqlite even
though the release already carried several provenance/evidence registries.  This
module provides one read-only view across those registries.  It deliberately
never claims that a catalogued payload exists on disk when the retained release
contains only metadata/provenance.
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE_CATALOG = ROOT / "FINAL_SOURCE_CATALOG_v17.csv"
DOMAIN_COVERAGE = ROOT / "DOMAIN_EVIDENCE_COVERAGE.csv"


def _sid(kind: str, name: str) -> str:
    return "SYS-" + kind.upper() + "-" + hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:12]


def _json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value or "{}"))
    except Exception:
        return {}


def _existing(path: str | None) -> bool:
    if not path:
        return False
    try:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        return p.is_file()
    except Exception:
        return False


def _source_status(name: str, paths: list[str], expected_files: int, available_files: int) -> str:
    low = str(name or "").lower()
    if any(x in low for x in ["procurement", "mml_tgi", "mml-tgi"]):
        return "PROCUREMENT_REQUIRED" if available_files == 0 else "PARTIAL_LOCAL"
    if expected_files and available_files == expected_files:
        return "LOCAL"
    if available_files:
        return "PARTIAL_LOCAL"
    if expected_files:
        return "CATALOG_ONLY"
    return "REGISTERED_METADATA"


def _source_label_status(status: str) -> str:
    return {
        "LOCAL": "Lokálně dostupné",
        "PARTIAL_LOCAL": "Částečně dostupné",
        "CATALOG_ONLY": "Evidované v katalogu – payload není v tomto balíku",
        "REGISTERED_METADATA": "Evidovaný externí zdroj",
        "PROCUREMENT_REQUIRED": "Vyžaduje komerční přístup / pořízení",
        "INTERNAL_DERIVED": "Interně odvozené – není samostatný externí zdroj",
        "UNGROUNDED": "Bez externí kotvy",
    }.get(status, status)


def _merge_source(rows: dict[str, dict[str, Any]], key: str, incoming: dict[str, Any]) -> None:
    cur = rows.get(key)
    if not cur:
        rows[key] = incoming
        return
    for fld in ["domains", "topics", "dimensions", "paths", "roles", "years", "registry_files", "urls"]:
        vals = list(cur.get(fld) or []) + list(incoming.get(fld) or [])
        cur[fld] = sorted({str(v) for v in vals if str(v or "").strip()})
    cur["expected_files"] = max(int(cur.get("expected_files") or 0), int(incoming.get("expected_files") or 0))
    cur["available_files"] = max(int(cur.get("available_files") or 0), int(incoming.get("available_files") or 0))
    cur["size_bytes"] = max(int(cur.get("size_bytes") or 0), int(incoming.get("size_bytes") or 0))
    cur["confidence"] = max(float(cur.get("confidence") or 0), float(incoming.get("confidence") or 0))
    # Prefer a real external classification over internal/ungrounded labels.
    rank = {"UNGROUNDED": 0, "INTERNAL_DERIVED": 1, "REGISTERED_METADATA": 2, "CATALOG_ONLY": 3,
            "PROCUREMENT_REQUIRED": 4, "PARTIAL_LOCAL": 5, "LOCAL": 6}
    if rank.get(str(incoming.get("status")), 0) > rank.get(str(cur.get("status")), 0):
        cur["status"] = incoming.get("status")
    cur["status_label"] = _source_label_status(str(cur.get("status") or ""))


@lru_cache(maxsize=2)
def catalog() -> dict[str, Any]:
    if not SOURCE_CATALOG.is_file():
        return {"sources": [], "summary": {"source_groups": 0}, "domain_coverage": []}
    df = pd.read_csv(SOURCE_CATALOG, low_memory=False).fillna("")
    grouped: dict[str, dict[str, Any]] = {}

    # 1) Retained/acquisition inventory. One source_group may represent many files.
    micro = df[df["registry_file"].eq("MICRODATA_SOURCE_INVENTORY.csv")]
    for name, g in micro.groupby("source_or_dimension", dropna=False):
        details = [_json(x) for x in g["detail"].tolist()]
        paths = [str(x.get("path") or "") for x in details if x.get("path")]
        available = sum(1 for p in paths if _existing(p))
        extensions = sorted({str(x.get("extension") or "") for x in details if x.get("extension")})
        size = sum(int(float(x.get("size_bytes") or 0)) for x in details)
        status = _source_status(str(name), paths, len(paths), available)
        item = {
            "source_id": _sid("microdata", str(name)), "name": str(name), "kind": "MICRODATA_OR_MATERIALS",
            "status": status, "status_label": _source_label_status(status), "registry_files": ["MICRODATA_SOURCE_INVENTORY.csv"],
            "paths": paths, "expected_files": len(paths), "available_files": available, "size_bytes": size,
            "extensions": extensions, "domains": [], "topics": [], "dimensions": [], "roles": [], "years": [], "urls": [],
            "confidence": 1.0, "detail": "Seskupený zdroj z retenčního inventáře mikrodat / veřejných materiálů.",
        }
        _merge_source(grouped, "micro:" + str(name).lower(), item)

    # 2) Explicit research/source registries.
    for registry, kind in [("RESEARCH_SOURCE_REGISTRY_v16_0.csv", "RESEARCH_BENCHMARK"),
                           ("SOURCE_REGISTRY_v16_1.csv", "SOURCE_REGISTRY")]:
        part = df[df["registry_file"].eq(registry)]
        for _, row in part.iterrows():
            d = _json(row["detail"]); name = str(d.get("source") or row["source_or_dimension"] or "neuvedený zdroj")
            item = {
                "source_id": _sid(kind, name), "name": name, "kind": kind, "status": "REGISTERED_METADATA",
                "status_label": _source_label_status("REGISTERED_METADATA"), "registry_files": [registry], "paths": [],
                "expected_files": 0, "available_files": 0, "size_bytes": 0, "extensions": [],
                "domains": [str(d.get("domain") or "")], "topics": [], "dimensions": [],
                "roles": [str(d.get("role") or d.get("status") or "")], "years": [str(d.get("year") or "")],
                "urls": [str(d.get("source_url") or "")], "confidence": float(d.get("confidence") or 0),
                "detail": str(d.get("implementation_note") or d.get("note") or ""),
            }
            _merge_source(grouped, "src:" + name.lower(), item)

    # 3) Dimension evidence registry – aggregate all dimensions per named evidence source.
    part = df[df["registry_file"].eq("DIMENSION_EVIDENCE_REGISTRY_v3.csv")]
    for _, row in part.iterrows():
        d = _json(row["detail"]); name = str(d.get("source") or "bez kotvy")
        low = name.lower()
        if low in {"bez kotvy", "", "nan"}:
            status = "UNGROUNDED"
        elif "odvozeno" in low or str(d.get("source_role") or "").upper() == "OWN_ESTIMATE":
            status = "INTERNAL_DERIVED"
        else:
            status = "REGISTERED_METADATA"
        item = {
            "source_id": _sid("evidence", name), "name": name, "kind": "DIMENSION_EVIDENCE", "status": status,
            "status_label": _source_label_status(status), "registry_files": ["DIMENSION_EVIDENCE_REGISTRY_v3.csv"],
            "paths": [], "expected_files": 0, "available_files": 0, "size_bytes": 0, "extensions": [],
            "domains": [str(d.get("block") or "")], "topics": str(d.get("topics") or "").split("|"),
            "dimensions": [str(d.get("dimension") or row["source_or_dimension"] or "")],
            "roles": [str(d.get("evidence_role_v3") or d.get("source_role") or "")],
            "years": [str(d.get("source_year") or "")], "urls": [str(d.get("source_url") or "")],
            "confidence": float(d.get("confidence") or 0), "detail": str(d.get("marker") or ""),
        }
        _merge_source(grouped, "evidence:" + name.lower(), item)

    # 4) Calibration registry can add sources missing from the evidence registry.
    part = df[df["registry_file"].eq("CALIBRATION_REGISTRY.csv")]
    for _, row in part.iterrows():
        d = _json(row["detail"]); name = str(d.get("source") or "bez kotvy")
        low = name.lower(); status = "UNGROUNDED" if low in {"bez kotvy", "", "nan"} else "REGISTERED_METADATA"
        item = {
            "source_id": _sid("calibration", name), "name": name, "kind": "CALIBRATION_SOURCE", "status": status,
            "status_label": _source_label_status(status), "registry_files": ["CALIBRATION_REGISTRY.csv"],
            "paths": [], "expected_files": 0, "available_files": 0, "size_bytes": 0, "extensions": [],
            "domains": [str(d.get("block") or "")], "topics": [],
            "dimensions": [str(d.get("dimension") or row["source_or_dimension"] or "")],
            "roles": [str(d.get("evidence_role") or "")], "years": [], "urls": [str(d.get("source_url") or "")],
            "confidence": float(d.get("confidence") or 0), "detail": str(d.get("notes") or ""),
        }
        # Merge with same named external evidence source if it already exists.
        evidence_key = "evidence:" + name.lower()
        _merge_source(grouped, evidence_key if evidence_key in grouped else "cal:" + name.lower(), item)

    sources = sorted(grouped.values(), key=lambda x: (x.get("status") in {"UNGROUNDED", "INTERNAL_DERIVED"}, str(x.get("name")).lower()))
    status_counts: dict[str, int] = {}
    for x in sources:
        status_counts[x["status"]] = status_counts.get(x["status"], 0) + 1

    domain_coverage: list[dict[str, Any]] = []
    if DOMAIN_COVERAGE.is_file():
        dc = pd.read_csv(DOMAIN_COVERAGE).fillna("")
        domain_coverage = dc.to_dict(orient="records")

    return {
        "sources": sources,
        "summary": {
            "catalog_rows": int(len(df)), "source_groups": len(sources),
            "microdata_groups": int(micro["source_or_dimension"].nunique()),
            "expected_payload_files": sum(int(x.get("expected_files") or 0) for x in sources),
            "available_payload_files": sum(int(x.get("available_files") or 0) for x in sources),
            "status_counts": status_counts,
            "dimension_evidence_rows": int((df["registry_file"] == "DIMENSION_EVIDENCE_REGISTRY_v3.csv").sum()),
            "calibration_rows": int((df["registry_file"] == "CALIBRATION_REGISTRY.csv").sum()),
        },
        "domain_coverage": domain_coverage,
        "contract": {
            "catalog_is_provenance_not_payload": True,
            "missing_payload_is_never_reported_as_local": True,
            "system_catalog_is_read_only": True,
        },
    }


def source_by_id(source_id: str) -> dict[str, Any] | None:
    return next((x for x in catalog().get("sources", []) if x.get("source_id") == source_id), None)


def relevant_sources(text: str, *, limit: int = 12) -> list[dict[str, Any]]:
    q = str(text or "").lower()
    toks = {t for t in __import__("re").findall(r"[a-zá-ž0-9_]{4,}", q)}
    scored = []
    for s in catalog().get("sources", []):
        hay = " ".join([str(s.get("name") or ""), *(s.get("domains") or []), *(s.get("topics") or []), *(s.get("dimensions") or []), str(s.get("detail") or "")]).lower()
        score = sum(1 for t in toks if t in hay)
        if score:
            scored.append((score, float(s.get("confidence") or 0), s))
    return [x[2] for x in sorted(scored, key=lambda z: (-z[0], -z[1], str(z[2].get("name"))))[:max(1, int(limit))]]


def clear_cache() -> None:
    catalog.cache_clear()
