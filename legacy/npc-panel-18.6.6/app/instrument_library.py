"""Versioned, deterministic questionnaire instrument library for NPC Panel 15."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any
import json
import re

ROOT=Path(__file__).resolve().parent
LIBRARY_PATH=ROOT/"INSTRUMENT_LIBRARY_v1.json"

@lru_cache(maxsize=1)
def load_library() -> dict[str,Any]:
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def library_version() -> str:
    return str(load_library().get("library_version") or "unknown")


def study_types() -> dict[str,Any]:
    return deepcopy(load_library().get("study_types") or {})


def required_slots(study_type: str) -> list[str]:
    return list((study_types().get(study_type) or {}).get("required_slots") or [])


def _format_text(s: str, slots: dict[str,Any]) -> str:
    class Safe(dict):
        def __missing__(self,key): return "{"+key+"}"
    try: return str(s).format_map(Safe({k:str(v) for k,v in slots.items() if not isinstance(v,(list,dict))}))
    except Exception: return str(s)


def missing_slots(study_type: str, slots: dict[str,Any]) -> list[str]:
    miss=[]
    for k in required_slots(study_type):
        v=slots.get(k)
        if isinstance(v,list): ok=bool([x for x in v if str(x).strip()])
        else: ok=bool(str(v or "").strip())
        if not ok: miss.append(k)
    return miss


def _instrument_available(inst: dict[str,Any], slots: dict[str,Any]) -> bool:
    for k in inst.get("requires_slots") or []:
        v=slots.get(k)
        if isinstance(v,list):
            if not [x for x in v if str(x).strip()]: return False
        elif not str(v or "").strip(): return False
    return True


def instantiate(instrument_id: str, slots: dict[str,Any]) -> dict[str,Any] | None:
    lib=load_library(); inst=deepcopy((lib.get("instruments") or {}).get(instrument_id))
    if not inst: raise KeyError(f"Neznámý instrument: {instrument_id}")
    if not _instrument_available(inst,slots): return None
    kind=inst.get("kind")
    md={"instrument_id":instrument_id,"instrument_library_version":library_version(),"standard_instrument":True,
        "anchor_eligible":bool(inst.get("anchor_eligible",False)),
        "source_status":str(inst.get("source_status") or "PENDING_SOURCE_BINDING"),
        "source_name":str(inst.get("source_name") or ""),"source_year":str(inst.get("source_year") or "")}
    if kind=="questions":
        qs=[]
        for q in inst.get("questions") or []:
            qq={k:deepcopy(v) for k,v in q.items() if k not in {"construct","measurement_level","anchor_eligible","claim_mode","categories_from","append_categories"}}
            qq["text"]=_format_text(qq.get("text",""),slots)
            if q.get("categories_from"):
                qq["kategorie"]=[str(x).strip() for x in slots.get(q["categories_from"],[]) if str(x).strip()]
                qq["kategorie"]+=list(q.get("append_categories") or [])
            qqmd=dict(qq.get("metadata") or {})
            qqmd.update(md); qqmd.update({"construct":q.get("construct",""),"measurement_level":q.get("measurement_level",""),
                                          "anchor_eligible":bool(q.get("anchor_eligible",False)),"claim_mode":q.get("claim_mode","standard")})
            qq["metadata"]=qqmd; qs.append(qq)
        return {"id":"inst_"+re.sub(r"[^a-z0-9]+","_",instrument_id.lower()).strip("_"),"type":"questions",
                "title":inst.get("title",instrument_id),"purpose":"Standardní instrument z knihovny.","questions":qs,
                "metadata":md}
    if kind=="object_battery":
        objects=list(inst.get("objects") or [])
        if inst.get("objects_from"):
            objects=[str(x).strip() for x in slots.get(inst["objects_from"],[]) if str(x).strip()]
        return {"id":"inst_"+re.sub(r"[^a-z0-9]+","_",instrument_id.lower()).strip("_"),"type":"object_battery",
                "title":inst.get("title",instrument_id),"purpose":"Standardní srovnávací baterie z knihovny.",
                "object_family":inst.get("object_family","položky"),"object_type":inst.get("object_family","položky"),
                "objects":objects,"object_question":_format_text(inst.get("object_question","Jak hodnotíte {object}?"),slots),
                "scale_labels":list(inst.get("scale_labels") or ["vůbec","velmi"]),
                "familiarity_required":bool(inst.get("familiarity_required",False)),"output_type":inst.get("output_type","pozicni_mapa"),
                "visualize":True,"metadata":{**md,"construct":inst.get("construct","")}}
    raise ValueError(f"{instrument_id}: neznámý kind {kind}")


def recommended_instrument_ids(study_type: str, *, include_optional: bool=False) -> list[str]:
    st=study_types().get(study_type) or study_types().get("custom",{})
    ids=list(st.get("recommended_instruments") or [])
    if include_optional: ids+=list(st.get("optional_instruments") or [])
    return ids


def compile_standard_sections(study_type: str, slots: dict[str,Any], *, include_optional: bool=False) -> dict[str,Any]:
    sections=[]; skipped=[]
    for iid in recommended_instrument_ids(study_type,include_optional=include_optional):
        sec=instantiate(iid,slots)
        if sec is None: skipped.append(iid)
        else: sections.append(sec)
    return {"sections":sections,"skipped":skipped,"missing_slots":missing_slots(study_type,slots),"library_version":library_version()}


def merge_standard_sections(project: dict[str,Any], *, replace_existing_standard: bool=False) -> dict[str,Any]:
    p=deepcopy(project)
    study_type=str(p.get("study_type") or "custom")
    slots=dict(p.get("study_config") or {})
    compiled=compile_standard_sections(study_type,slots,include_optional=bool(slots.get("include_optional_instruments",False)))
    existing=[] if replace_existing_standard else list(p.get("sections") or [])
    if not replace_existing_standard:
        standard_ids={str((s.get("metadata") or {}).get("instrument_id") or "") for s in existing}
        new=[s for s in compiled["sections"] if str((s.get("metadata") or {}).get("instrument_id") or "") not in standard_ids]
        p["sections"]=new+existing
    else:
        custom=[s for s in list(p.get("sections") or []) if not (s.get("metadata") or {}).get("standard_instrument")]
        p["sections"]=compiled["sections"]+custom
    p["instrument_library"]={"version":compiled["library_version"],"missing_slots":compiled["missing_slots"],"skipped_instruments":compiled["skipped"]}
    return p
