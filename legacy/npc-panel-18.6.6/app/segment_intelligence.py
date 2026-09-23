"""NPC Panel 18.4 — Segment Intelligence for Visualization Lab.

The discovery layer is deterministic and evidence-derived.  The optional AI layer
receives aggregates only (never raw respondent rows) and may explain, prioritize
and name the discovered groups.  It is not allowed to invent causal claims.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from visualization_lab import detect_profile_columns, detect_rating_columns, _label


def _safe(v: Any):
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 6)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v.item() if hasattr(v, "item") else v


def _fingerprint_frame(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    h = hashlib.sha256((str(len(df)) + "|" + "|".join(cols)).encode("utf-8"))
    if len(df):
        sample = pd.concat([df.head(8), df.tail(8)]).astype(str)
        h.update(sample.to_csv(index=False).encode("utf-8"))
    return h.hexdigest()


def _stable_id(kind: str, spec: dict[str, Any]) -> str:
    raw = json.dumps({"kind": kind, "filter": spec}, ensure_ascii=False, sort_keys=True, default=str)
    return "SG-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()


def _numeric_columns(df: pd.DataFrame, profile_cols: list[str], rating_cols: list[str]) -> list[str]:
    out = []
    for c in list(dict.fromkeys(profile_cols + rating_cols)):
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().mean() >= .65 and s.nunique(dropna=True) >= 3:
            out.append(c)
    return out


def _effect_rows(df: pd.DataFrame, mask: pd.Series, columns: list[str], *, limit: int = 12) -> list[dict[str, Any]]:
    mask = mask.fillna(False).astype(bool)
    rest = ~mask
    rows = []
    for c in columns:
        s = pd.to_numeric(df[c], errors="coerce")
        a = s[mask].dropna(); b = s[rest].dropna()
        if len(a) < 4 or len(b) < 4:
            continue
        ma, mb = float(a.mean()), float(b.mean())
        pooled = float(pd.concat([a, b]).std(ddof=1) or 0.0)
        z = (ma - mb) / pooled if pooled > 1e-9 else 0.0
        rows.append({
            "column": c,
            "label": _label(c),
            "group_mean": round(ma, 3),
            "rest_mean": round(mb, 3),
            "delta": round(ma - mb, 3),
            "standardized_difference": round(z, 3),
            "direction": "higher" if z > 0 else "lower" if z < 0 else "same",
        })
    rows.sort(key=lambda x: abs(float(x["standardized_difference"])), reverse=True)
    return rows[:limit]


def _categorical_rows(df: pd.DataFrame, mask: pd.Series, columns: list[str], *, limit: int = 8) -> list[dict[str, Any]]:
    mask = mask.fillna(False).astype(bool); rest = ~mask
    rows=[]
    for c in columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        s=df[c].astype(str)
        if s.nunique(dropna=True) < 2 or s.nunique(dropna=True) > 25:
            continue
        ga=s[mask].value_counts(normalize=True); rb=s[rest].value_counts(normalize=True)
        vals=set(ga.index)|set(rb.index)
        if not vals: continue
        value=max(vals,key=lambda v:abs(float(ga.get(v,0))-float(rb.get(v,0))))
        delta=float(ga.get(value,0))-float(rb.get(value,0))
        rows.append({"column":c,"label":_label(c),"value":str(value),"group_share":round(float(ga.get(value,0)),4),"rest_share":round(float(rb.get(value,0)),4),"delta_pp":round(100*delta,1)})
    rows.sort(key=lambda x:abs(float(x["delta_pp"])),reverse=True)
    return rows[:limit]


def _candidate_record(df: pd.DataFrame, mask: pd.Series, *, title: str, kind: str, filter_spec: dict[str, Any],
                      numeric_cols: list[str], profile_cols: list[str], rating_cols: list[str], origin: str) -> dict[str, Any] | None:
    mask=mask.fillna(False).astype(bool); n=int(mask.sum()); N=len(df); share=n/max(1,N)
    if n < max(12, int(.025*N)) or n > int(.68*N):
        return None
    effects=_effect_rows(df,mask,numeric_cols,limit=14)
    cat=_categorical_rows(df,mask,profile_cols,limit=8)
    obj=[x for x in effects if x["column"] in rating_cols][:6]
    traits=[x for x in effects if x["column"] not in rating_cols][:8]
    absz=[abs(float(x["standardized_difference"])) for x in effects[:8]]
    distinct=float(np.mean(absz[:5])) if absz else 0.0
    # Favor useful minority groups but do not artificially prefer tiny slivers.
    size_factor=min(1.0, math.sqrt(max(share,1e-6)/.18)) * min(1.0, math.sqrt(max(1-share,1e-6)/.35))
    evidence_factor=min(1.0, math.sqrt(n/80))
    rank=100*min(1.0,(0.58*min(distinct/1.25,1.0)+0.24*size_factor+0.18*evidence_factor))
    ids=[]
    idcol=next((c for c in ("respondent_id","panel_row_id","id","ID") if c in df.columns),None)
    for i in df.index[mask]: ids.append(str(df.at[i,idcol]) if idcol else f"R{int(i)+1:05d}")
    return {
        "id":_stable_id(kind,filter_spec),"title":title,"kind":kind,"origin":origin,
        "count":n,"share":round(share,4),"rank_score":round(rank,1),"distinctiveness":round(distinct,3),
        "filter":filter_spec,"respondent_ids":ids,"top_differences":effects[:8],"trait_differences":traits,
        "object_differences":obj,"categorical_differences":cat,
        "evidence_note":f"Skupina obsahuje {n} z {N} respondentů ({share*100:.1f} %). Porovnání je asociativní, nikoli kauzální."
    }


def discover_segments(df: pd.DataFrame, *, profile_columns: list[str] | None=None, rating_columns: list[str] | None=None,
                      max_candidates: int=12) -> dict[str, Any]:
    if df is None or df.empty: raise ValueError("Dataset neobsahuje respondenty.")
    profile_cols=[c for c in (profile_columns or detect_profile_columns(df,40)) if c in df.columns]
    rating_cols=[c for c in (rating_columns or detect_rating_columns(df,24)) if c in df.columns]
    numeric_cols=_numeric_columns(df,profile_cols,rating_cols)
    raw=[]
    # 1) Explicit segment/persona is the strongest explainable seed if available.
    segcol=next((c for c in profile_cols if any(x in c.lower() for x in ("segment","persona","cluster"))),None)
    if segcol:
        vc=df[segcol].astype(str).value_counts()
        for value,n in vc.head(12).items():
            spec={"logic":"AND","conditions":[{"column":segcol,"label":_label(segcol),"op":"=","value":str(value)}]}
            r=_candidate_record(df,df[segcol].astype(str).eq(str(value)),title=str(value),kind="declared_segment",filter_spec=spec,
                                numeric_cols=numeric_cols,profile_cols=profile_cols,rating_cols=rating_cols,origin="DATASET_SEGMENT")
            if r: raw.append(r)
    # 2) Demographic / categorical slices.
    for c in profile_cols:
        if c==segcol or pd.api.types.is_numeric_dtype(df[c]): continue
        nun=int(df[c].nunique(dropna=True))
        if not 2<=nun<=10: continue
        for value,n in df[c].astype(str).value_counts().head(4).items():
            share=n/max(1,len(df))
            if share<.06 or share>.55: continue
            spec={"logic":"AND","conditions":[{"column":c,"label":_label(c),"op":"=","value":str(value)}]}
            r=_candidate_record(df,df[c].astype(str).eq(str(value)),title=f"{_label(c)} · {value}",kind="categorical_slice",filter_spec=spec,
                                numeric_cols=numeric_cols,profile_cols=profile_cols,rating_cols=rating_cols,origin="AUTOMATIC_DISCOVERY")
            if r: raw.append(r)
    # 3) Tails of attitudes / behavior, then meaningful two-condition intersections.
    tail_masks=[]
    tail_cols=[c for c in numeric_cols if c not in rating_cols][:14]
    for c in tail_cols:
        s=pd.to_numeric(df[c],errors="coerce"); lo=float(s.quantile(.22)); hi=float(s.quantile(.78))
        for direction,op,val,mask in (("vysoké",">=",round(hi,3),s>=hi),("nízké","<=",round(lo,3),s<=lo)):
            spec={"logic":"AND","conditions":[{"column":c,"label":_label(c),"op":op,"value":val}]}
            title=f"{direction.capitalize()} · {_label(c)}"
            r=_candidate_record(df,mask,title=title,kind="numeric_tail",filter_spec=spec,numeric_cols=numeric_cols,profile_cols=profile_cols,rating_cols=rating_cols,origin="AUTOMATIC_DISCOVERY")
            if r: raw.append(r); tail_masks.append((c,direction,op,val,mask))
    # Intersections among strongest behavioral tails. This is where combinations such as sport + sugar avoidance emerge.
    for i in range(min(12,len(tail_masks))):
        c1,d1,o1,v1,m1=tail_masks[i]
        for j in range(i+1,min(12,len(tail_masks))):
            c2,d2,o2,v2,m2=tail_masks[j]
            if c1==c2: continue
            mask=m1&m2; share=float(mask.mean())
            if not .045<=share<=.38: continue
            spec={"logic":"AND","conditions":[{"column":c1,"label":_label(c1),"op":o1,"value":v1},{"column":c2,"label":_label(c2),"op":o2,"value":v2}]}
            title=f"{d1.capitalize()} {_label(c1)} + {d2} {_label(c2)}"
            r=_candidate_record(df,mask,title=title,kind="intersection",filter_spec=spec,numeric_cols=numeric_cols,profile_cols=profile_cols,rating_cols=rating_cols,origin="AUTOMATIC_DISCOVERY")
            if r: raw.append(r)
    # Deduplicate identical membership; prefer declared segment, then higher rank.
    best={}
    priority={"declared_segment":3,"intersection":2,"numeric_tail":1,"categorical_slice":0}
    for r in raw:
        key=hashlib.sha256("|".join(sorted(r["respondent_ids"])).encode()).hexdigest()
        cur=best.get(key)
        if cur is None or (priority.get(r["kind"],0),r["rank_score"])>(priority.get(cur["kind"],0),cur["rank_score"]):best[key]=r
    candidates=list(best.values());candidates.sort(key=lambda x:(-x["rank_score"],-x["count"],x["title"]))
    # Preserve all declared dataset segments in the visible intelligence set; discovery candidates fill the remaining slots.
    declared=[x for x in candidates if x.get("kind")=="declared_segment"]
    others=[x for x in candidates if x.get("kind")!="declared_segment"]
    selected=(declared+others)[:max_candidates]
    return {"schema":"npc.segment_intelligence.v1","dataset_fingerprint":_fingerprint_frame(df),"respondent_count":len(df),
            "rating_columns":[{"key":c,"label":_label(c)} for c in rating_cols],"profile_columns":[{"key":c,"label":_label(c)} for c in profile_cols],
            "candidates":selected,"method":"deterministic contrast discovery over declared segments, profile slices and behavioral tail intersections",
            "truth_contract":"Skupiny jsou odvozené pouze z respondentních dat. Skóre vyjadřuje datovou odlišnost a velikost, ne kauzalitu ani obchodní hodnotu."}


def public_ai_input(payload: dict[str, Any], *, max_candidates: int=8) -> dict[str, Any]:
    """Strip respondent IDs before any provider call."""
    out={"schema":payload.get("schema"),"respondent_count":payload.get("respondent_count"),"method":payload.get("method"),"candidates":[]}
    for c in (payload.get("candidates") or [])[:max_candidates]:
        out["candidates"].append({k:v for k,v in c.items() if k not in {"respondent_ids"}})
    return out


def ai_schema() -> dict[str, Any]:
    item={"type":"object","properties":{
        "candidate_id":{"type":"string"},"title":{"type":"string"},"why_interesting":{"type":"string"},
        "characterization":{"type":"string"},"business_meaning":{"type":"string"},"map_cta":{"type":"string"},
        "confidence_note":{"type":"string"},"caution":{"type":"string"}},
        "required":["candidate_id","title","why_interesting","characterization","business_meaning","map_cta","confidence_note","caution"]}
    return {"type":"object","properties":{"summary":{"type":"string"},"insights":{"type":"array","items":item}},"required":["summary","insights"]}


def interpret_with_ai(payload: dict[str, Any], *, provider: str, model: str|None=None) -> dict[str, Any]:
    """Explain aggregate evidence through exactly the selected provider; no fallback."""
    from ai_router import call_structured
    from runtime_config import resolve_provider_model
    provider=str(provider or "claude_code_subscription")
    selected_model=resolve_provider_model(provider,model)
    clean=public_ai_input(payload)
    system=("Jsi seniorní výzkumný analytik. Dostáváš pouze AGREGOVANÉ profily již datově nalezených skupin. "
            "Veškerý klientský text piš česky. Vyber maximálně 6 opravdu zajímavých kandidátů. "
            "Popiš konkrétně, čím se liší od zbytku vzorku a co to může znamenat pro rozhodnutí. "
            "Nevymýšlej žádná čísla, vlastnosti ani kauzalitu. Slova jako proto/protože používej jen pokud je kauzální vztah skutečně doložen; jinak používej asociativní formulaci 'souvisí', 'v této skupině se současně objevuje'. "
            "map_cta má být krátké tlačítkové sdělení ve stylu 'Zobrazit skupinu A na mapě'. confidence_note musí reflektovat velikost skupiny a sílu odlišností.")
    rr=call_structured(system=system,messages=[{"role":"user","content":json.dumps(clean,ensure_ascii=False)}],schema=ai_schema(),schema_name="npc_segment_intelligence",
                       anthropic_model=selected_model,openai_model=selected_model if provider=="openai" else None,max_tokens=4200,prefer=provider,allow_fallback=False,
                       claude_max_turns=4,claude_interactive=False)
    data=dict(rr.get("data") or {})
    valid={c["id"] for c in payload.get("candidates") or []}
    data["insights"]=[x for x in data.get("insights") or [] if str(x.get("candidate_id") or "") in valid][:6]
    return {"status":"AI_READY","provider":rr.get("provider") or provider,"model":rr.get("model") or selected_model,
            "fallback_used":bool(rr.get("fallback_used")),"summary":str(data.get("summary") or ""),"insights":data.get("insights") or [],
            "privacy_contract":"AI obdržela pouze agregované profily skupin; respondentní ID a individuální řádky nebyly odeslány."}


def merge_ai(payload:dict[str,Any], ai:dict[str,Any]|None)->dict[str,Any]:
    if not ai:return payload
    insight_rows=list(ai.get("insights") or [])
    by={str(x.get("candidate_id")):x for x in insight_rows}
    rank={str(x.get("candidate_id")):i for i,x in enumerate(insight_rows)}
    out=dict(payload);rows=[]
    for c in payload.get("candidates") or []:
        cc=dict(c);cc["ai_interpretation"]=by.get(str(c.get("id")));cc["ai_rank"]=rank.get(str(c.get("id")))
        rows.append(cc)
    out["candidates"]=rows;out["ai"]={k:v for k,v in ai.items() if k!="insights"}
    return out
