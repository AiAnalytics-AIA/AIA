"""Canonical v17 built-in and special-audience panel registry."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd
from data_contract import contract
ROOT=Path(__file__).resolve().parent

def _load_json(name,default):
    p=ROOT/name
    try:return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:return default

def list_subpanels()->list[dict[str,Any]]:
    return list(_load_json(contract()["builtin_subpanels"],{}).get("subpanels") or [])
def get_subpanel(key:str):
    return next((x for x in list_subpanels() if x.get("key")==str(key or "").strip()),None)
def list_special_panels()->list[dict[str,Any]]:
    obj=_load_json(contract()["special_panels"],[])
    return list(obj if isinstance(obj,list) else obj.get("panels") or [])
def get_special_panel(key:str):
    key=str(key or "").strip().replace("builtin_special:","")
    return next((x for x in list_special_panels() if x.get("key")==key),None)
def runtime_filters(spec):
    f=dict((spec or {}).get("filter") or {});out={}
    for k,v in f.items():out[k]=tuple(v) if k=="vek" and isinstance(v,list) and len(v)==2 else v
    return out
def apply(df:pd.DataFrame,key:str)->pd.DataFrame:
    spec=get_subpanel(key)
    if not spec:raise KeyError(f"Neznámý vestavěný panel: {key}")
    from audience import _mask
    return df[_mask(df,runtime_filters(spec))].copy()
def load_special_panel_frame(key:str):
    spec=get_special_panel(key)
    if not spec:raise KeyError(f"Neznámý vestavěný special panel: {key}")
    p=ROOT/str(spec.get("file") or "")
    if not p.is_file():raise FileNotFoundError(f"Chybí soubor special panelu: {p}")
    d=pd.read_csv(p,low_memory=False,dtype={"occupation_isco08":"string"})
    # Structural-only foreign/minority panels must never resurrect group-sensitive fields.
    if str(spec.get("support") or "").startswith("STRUCTURAL_ONLY"):
        for c in d.columns:
            if c.startswith(("value_","CSES_","QOG_","ROL_")) or c in {"religious_affiliation_group","religious_practice_1_10","politicky_zajem_2021","volba_2021_strana"}:
                d[c]=pd.NA
    return d,spec
def project_patch(key:str):
    spec=get_subpanel(key)
    if not spec:raise KeyError(key)
    return {"source_mode":"population","dataset_id":"","dataset_name":spec["name"],"strategy":"filters","description":spec.get("description") or spec["name"],"builtin_subpanel":key,"filters":runtime_filters(spec),"subpanel_status":spec.get("status","ready"),"support_tier":spec.get("support_tier",""),"support_summary":{k:spec.get(k) for k in ("rows","weighted_population","unique_core_donors","effective_core_donors","max_core_reuse")}}
def special_project_patch(key:str):
    spec=get_special_panel(key)
    if not spec:raise KeyError(key)
    return {"source_mode":"special_audience","dataset_id":"builtin_special:"+key,"dataset_name":spec.get("name") or key,"builtin_subpanel":"","strategy":"special_panel","description":spec.get("note") or spec.get("name") or key,"filters":{},"special_panel_key":key,"special_panel_status":spec.get("status"),"support_tier":spec.get("support"),"support_summary":{"rows":spec.get("rows"),"population_anchor":spec.get("current_population_anchor")}}
