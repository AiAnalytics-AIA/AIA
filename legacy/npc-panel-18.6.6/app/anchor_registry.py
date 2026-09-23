"""Known-truth anchor registry for v15 projects.

Global anchors must be explicitly documented in VALIDATION_ANCHORS.json. Customer /
Special Audience datasets may carry an optional Benchmarks sheet; those targets stay
scoped to that audience and are never generalized to the Czech population.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import pandas as pd
from audience_registry import AUDIENCE_ROOT

ROOT=Path(__file__).resolve().parent
GLOBAL=ROOT/"VALIDATION_ANCHORS.json"


def load_global_anchors() -> dict[str,Any]:
    return json.loads(GLOBAL.read_text(encoding="utf-8")) if GLOBAL.is_file() else {"schema_version":1,"anchors":[]}


def audience_benchmarks(audience_id: str) -> list[dict[str,Any]]:
    p=AUDIENCE_ROOT/str(audience_id)/"benchmarks.csv"
    if not p.is_file(): return []
    df=pd.read_csv(p,low_memory=False).dropna(how="all")
    return df.fillna("").to_dict("records")


def available_anchors(project: dict[str,Any]) -> dict[str,Any]:
    aud=(project or {}).get("audience") or {}
    mode=str(aud.get("source_mode") or "population")
    global_items=list(load_global_anchors().get("anchors") or [])
    scoped=[]
    if mode in {"customer","special_audience"} and aud.get("dataset_id"):
        scoped=audience_benchmarks(str(aud["dataset_id"]))
    return {"global":global_items,"audience_scoped":scoped,"count":len(global_items)+len(scoped),
            "status":"AVAILABLE" if global_items or scoped else "NO_VERIFIED_ANCHORS",
            "note":"Only documented truth is returned; zero anchors is safer than invented validation."}
