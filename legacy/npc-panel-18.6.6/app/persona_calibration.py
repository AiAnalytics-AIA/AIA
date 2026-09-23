"""Benchmark-driven persona calibration.

Only rows explicitly marked CALIBRATION may tune the persona. BLIND_HOLDOUT rows are
measurement-only and are rejected for fitting. The active profile selects the persona
recipe (demographics/core/full) by question domain before the LLM prompt is built.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib, json, time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
CAL_DIR = ROOT / "data" / "persona_calibration"
ACTIVE_PROFILE = CAL_DIR / "active_profile.json"
_DISABLED: ContextVar[bool] = ContextVar("npc_persona_calibration_disabled", default=False)
CANDIDATES = ("demographics", "core", "full")
ORDER = {"demographics": 0, "core": 1, "full": 2}


def _sha(obj: object) -> str:
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_active_profile() -> dict[str, Any] | None:
    if not ACTIVE_PROFILE.is_file(): return None
    try:
        x=json.loads(ACTIVE_PROFILE.read_text(encoding="utf-8"))
        return x if isinstance(x,dict) and x.get("profile_hash") else None
    except Exception:
        return None


def calibration_status() -> dict[str, Any]:
    p=load_active_profile()
    if not p:
        return {"active":False,"fallback_mode":"core","note":"Není aktivní human benchmark kalibrace; režim calibrated používá core."}
    return {"active":True,"profile_hash":p.get("profile_hash"),"created_at":p.get("created_at"),
            "global_mode":p.get("global_mode"),"domains":p.get("domains",{}),
            "n_questions":p.get("n_questions"),"cv":p.get("cv",{}),"source":p.get("source",{})}


@contextmanager
def disable_active_calibration():
    tok=_DISABLED.set(True)
    try: yield
    finally: _DISABLED.reset(tok)


def _select_mode(g: pd.DataFrame) -> tuple[str, dict[str,float]]:
    means=(g[g["baseline"].isin(CANDIDATES)].groupby("baseline")["mae_pp"].mean().dropna().to_dict())
    if not means: return "core", {}
    # deterministic tie-break: prefer simpler recipe when errors are effectively tied
    best=min(means, key=lambda m:(round(float(means[m]),3), ORDER.get(m,99)))
    return best,{k:round(float(v),3) for k,v in means.items()}


def _cv_selection(g: pd.DataFrame) -> dict[str, Any]:
    qs=sorted(g["question_id"].astype(str).unique())
    chosen=[]; errs=[]; core=[]
    for q in qs:
        tr=g[g["question_id"].astype(str)!=q]
        te=g[g["question_id"].astype(str)==q]
        if tr["question_id"].nunique()<2: continue
        mode,_=_select_mode(tr)
        v=te[te["baseline"]==mode]["mae_pp"]
        c=te[te["baseline"]=="core"]["mae_pp"]
        if len(v) and len(c):
            chosen.append(mode); errs.append(float(v.mean())); core.append(float(c.mean()))
    if not errs:
        return {"n_folds":0,"selected_mae_pp":None,"core_mae_pp":None,"improvement_vs_core_pp":None,"stable":False}
    imp=float(np.mean(core)-np.mean(errs))
    return {"n_folds":len(errs),"selected_mae_pp":round(float(np.mean(errs)),3),
            "core_mae_pp":round(float(np.mean(core)),3),"improvement_vs_core_pp":round(imp,3),
            "selection_counts":{m:chosen.count(m) for m in CANDIDATES},"stable":len(errs)>=4 and imp>=-0.15}


def fit_calibration_profile(rows: pd.DataFrame | Iterable[dict[str,Any]], *, source: dict[str,Any] | None=None,
                            min_domain_questions: int=4, activate: bool=True) -> dict[str, Any]:
    df=rows.copy() if isinstance(rows,pd.DataFrame) else pd.DataFrame(list(rows))
    required={"question_id","baseline","mae_pp","benchmark_role"}
    miss=required-set(df.columns)
    if miss: raise ValueError("Benchmark calibration chybí sloupce: "+", ".join(sorted(miss)))
    role=df["benchmark_role"].astype(str).str.upper()
    if not (role=="CALIBRATION").any():
        raise ValueError("Kalibrace odmítnuta: nejsou přítomny žádné řádky benchmark_role=CALIBRATION. BLIND_HOLDOUT nesmí personu učit.")
    cal=df[role=="CALIBRATION"].copy()
    if "mode" in cal.columns and cal["mode"].astype(str).str.lower().eq("dry").all():
        raise ValueError("Kalibrace persony nesmí vzniknout pouze z dry benchmarku.")
    cal["mae_pp"]=pd.to_numeric(cal["mae_pp"],errors="coerce")
    cal=cal[cal["baseline"].isin(CANDIDATES)&cal["mae_pp"].notna()]
    n_q=int(cal["question_id"].nunique())
    if n_q<4: raise ValueError("Pro aktivní kalibraci persony jsou potřeba alespoň 4 CALIBRATION otázky.")
    global_mode,global_means=_select_mode(cal)
    cv=_cv_selection(cal)
    if not cv.get("stable"):
        global_mode="core"
    domains={}
    if "domain" in cal.columns:
        for dom,g in cal.groupby(cal["domain"].fillna("").astype(str)):
            dom=dom.strip()
            nq=int(g["question_id"].nunique())
            if not dom or nq<int(min_domain_questions): continue
            mode,means=_select_mode(g); dcv=_cv_selection(g)
            if not dcv.get("stable"): mode="core"
            domains[dom]={"mode":mode,"n_questions":nq,"mean_mae_pp":means,"cv":dcv}
    payload={"kind":"npc_persona_calibration_v1","created_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
             "global_mode":global_mode,"global_mean_mae_pp":global_means,"domains":domains,"n_questions":n_q,
             "cv":cv,"source":source or {},"policy":{"calibration_rows_only":True,"blind_holdout_forbidden":True,
             "fallback_without_profile":"core","candidate_recipes":list(CANDIDATES)}}
    payload["profile_hash"]=_sha(payload)
    if activate:
        CAL_DIR.mkdir(parents=True,exist_ok=True)
        ACTIVE_PROFILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    return payload


def fit_calibration_csv(path: str|Path, *, activate: bool=True) -> dict[str,Any]:
    p=Path(path)
    df=pd.read_csv(p,low_memory=False)
    src={"filename":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    return fit_calibration_profile(df,source=src,activate=activate)


def resolve_effective_mode(requested_mode: str, topics: Iterable[str] | None=None) -> tuple[str,dict[str,Any]]:
    req=str(requested_mode or "core")
    if req!="calibrated": return req,{"active":False,"requested_mode":req,"effective_mode":req}
    if _DISABLED.get(): return "core",{"active":False,"requested_mode":"calibrated","effective_mode":"core","disabled_for_benchmark":True}
    p=load_active_profile()
    if not p:
        return "core",{"active":False,"requested_mode":"calibrated","effective_mode":"core","reason":"no_active_profile"}
    hits=[]
    for t in topics or []:
        d=(p.get("domains") or {}).get(str(t))
        if d: hits.append((str(t),d))
    if hits:
        # If several calibrated domains apply, prefer the recipe with best cross-validated
        # selected MAE; tie-break towards the simpler recipe.
        def key(x):
            d=x[1]; cv=d.get("cv") or {}; err=cv.get("selected_mae_pp")
            return (999 if err is None else float(err), ORDER.get(d.get("mode"),99))
        dom,d=min(hits,key=key); mode=str(d.get("mode") or "core")
        return mode,{"active":True,"profile_hash":p.get("profile_hash"),"requested_mode":"calibrated",
                     "effective_mode":mode,"domain":dom,"n_questions":d.get("n_questions")}
    mode=str(p.get("global_mode") or "core")
    return mode,{"active":True,"profile_hash":p.get("profile_hash"),"requested_mode":"calibrated",
                 "effective_mode":mode,"domain":"__global__","n_questions":p.get("n_questions")}


def runtime_manifest(requested_mode: str) -> dict[str,Any]:
    if str(requested_mode)!="calibrated": return {"requested_mode":requested_mode,"active":False}
    s=calibration_status(); s["requested_mode"]="calibrated"; return s
