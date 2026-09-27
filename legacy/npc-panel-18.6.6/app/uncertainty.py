"""Donor-aware weighted uncertainty helpers for NPC Panel 17.1.2.

17.1 rules:
- report Kish weight effective N *and* real donor support;
- bootstrap client-facing intervals over donor clusters, not synthetic rows;
- n_unique_layer_donors < 25 => suppress;
- 25..49 => INDIKATIVNI;
- >= 50 => REPORTABLE (subject to evidence/other gates).

Intervals describe synthetic-panel uncertainty conditional on the current fused panel.
They are not external predictive validation.
"""
from __future__ import annotations
from typing import Any, Iterable
import math
import numpy as np
import pandas as pd

CORE_DONOR_COL = "core_donor_id"
LAYER_DONOR_COLS = {
    "core": CORE_DONOR_COL,
    "mental_health": "_donor_mental_health_id",
    "social_network": "_donor_social_network_id",
    "institutions": "_donor_institutions_id",
    "rule_of_law": "_donor_rule_of_law_id",
    "politics": "_donor_politics_id",
    "family_health": "_donor_family_health_id",
}
TOPIC_LAYER_CANDIDATES = {
    "mentalni_zdravi": ("mental_health",),
    "vztahy": ("social_network",), "komunita": ("social_network",),
    "instituce": ("institutions", "rule_of_law"),
    "politika": ("politics",), "migrace": ("politics",), "ekonomika": ("politics",),
    "rodina": ("family_health",), "vira": ("family_health",), "nabozenstvi": ("family_health",),
    "zdravi": ("family_health",),
}


def clean_weights(df: pd.DataFrame, preferred: tuple[str, ...] = ("_analysis_weight", "vaha_strukturalni_2025", "vaha_kalibrovana")) -> np.ndarray:
    for c in preferred:
        if c in df.columns:
            w = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
            ok = np.isfinite(w) & (w > 0)
            if ok.any():
                med = float(np.nanmedian(w[ok]))
                return np.where(ok, w, med if np.isfinite(med) and med > 0 else 1.0)
    return np.ones(len(df), dtype=float)


def kish_effective_n(weights: Iterable[float]) -> float:
    w = np.asarray(list(weights), dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if not len(w): return 0.0
    den = float(np.square(w).sum())
    return float((w.sum() ** 2) / den) if den > 0 else 0.0


def weighted_mean(values: Iterable[float], weights: Iterable[float]) -> float | None:
    x=np.asarray(list(values),float); w=np.asarray(list(weights),float)
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    return float(np.average(x[ok],weights=w[ok])) if ok.any() else None


def weighted_distribution(values: pd.Series, categories: list[str], weights: Iterable[float]) -> dict[str,float]:
    w=np.asarray(list(weights),float); s=values.astype(object).to_numpy(); ok=pd.notna(s)&np.isfinite(w)&(w>0)
    if not ok.any(): return {str(c):0.0 for c in categories}
    denom=float(w[ok].sum()); ss=s.astype(str)
    return {str(c):round(100.0*float(w[ok&(ss==str(c))].sum())/denom,1) for c in categories}


def weighted_quantile(values: Iterable[float], weights: Iterable[float], q: float=.5) -> float|None:
    x=np.asarray(list(values),float); w=np.asarray(list(weights),float); ok=np.isfinite(x)&np.isfinite(w)&(w>0); x,w=x[ok],w[ok]
    if not len(x): return None
    o=np.argsort(x); x,w=x[o],w[o]; cum=np.cumsum(w)/w.sum(); return float(np.interp(float(q),cum,x))


def weighted_variance(values: Iterable[float], weights: Iterable[float]) -> float|None:
    x=np.asarray(list(values),float); w=np.asarray(list(weights),float); ok=np.isfinite(x)&np.isfinite(w)&(w>0); x,w=x[ok],w[ok]
    if len(x)<2:return None
    mu=float(np.average(x,weights=w)); return float(np.average((x-mu)**2,weights=w))


def _valid_donor_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([f"row_{i}" for i in range(len(df))], index=df.index, dtype=object)
    s=df[col].astype(object).copy()
    miss=s.isna() | (s.astype(str).str.strip().isin(["", "nan", "None", "<NA>"]))
    if miss.any():
        s.loc[miss]=[f"missing_row_{i}" for i in np.flatnonzero(miss.to_numpy())]
    return s.astype(str)


def donor_ids(df: pd.DataFrame, donor_col: str) -> pd.Series:
    """Public stable donor-id accessor; missing IDs are row-unique, never one fake cluster."""
    return _valid_donor_series(df, donor_col)


def choose_donor_layer(df: pd.DataFrame, topics: Iterable[str]|None=None) -> tuple[str,str]:
    candidates=[]
    for t in topics or []:
        candidates.extend(TOPIC_LAYER_CANDIDATES.get(str(t),()))
    candidates=list(dict.fromkeys(candidates))
    if not candidates: return "core", CORE_DONOR_COL
    viable=[]
    for layer in candidates:
        col=LAYER_DONOR_COLS[layer]
        if col in df.columns:
            viable.append((int(_valid_donor_series(df,col).nunique()),layer,col))
    if not viable:return "core",CORE_DONOR_COL
    _,layer,col=min(viable,key=lambda x:x[0])  # conservative: thinnest relevant measured layer
    return layer,col


def donor_support(df: pd.DataFrame, topics: Iterable[str]|None=None, *, layer: str|None=None) -> dict[str,Any]:
    n=int(len(df)); w=clean_weights(df); kish=kish_effective_n(w)
    core=_valid_donor_series(df, CORE_DONOR_COL)
    if layer and layer in LAYER_DONOR_COLS:
        lname, lcol=layer,LAYER_DONOR_COLS[layer]
    else:
        lname,lcol=choose_donor_layer(df,topics)
    ld=_valid_donor_series(df,lcol)
    counts=ld.value_counts(dropna=False)
    nlayer=int(len(counts)); ncore=int(core.nunique())
    maxshare=float(counts.iloc[0]/n) if n and len(counts) else 0.0
    # Conservative combination of unequal weighting and donor clustering.
    combined=float(kish*(nlayer/max(n,1)))
    combined=min(combined,kish,float(nlayer),float(ncore) if lname=="core" else combined)
    if nlayer < 25: status="SUPPRESS"
    elif nlayer < 50: status="INDICATIVE"
    else: status="REPORTABLE"
    return {
        "n":n,"effective_n_kish":round(kish,1),"n_unique_core_donors":ncore,
        "donor_layer":lname,"donor_column":lcol,"n_unique_layer_donors":nlayer,
        "max_donor_share":round(maxshare,4),"effective_n_combined":round(combined,1),
        "support_status":status,
    }


def _cluster_setup(df: pd.DataFrame, donor_col: str, weights: Iterable[float]) -> tuple[np.ndarray,np.ndarray,np.ndarray]:
    d=_valid_donor_series(df,donor_col).to_numpy(); w=np.asarray(list(weights),float)
    codes,uniques=pd.factorize(d,sort=False); return codes,uniques,w


def _cluster_multipliers(codes: np.ndarray, nclusters: int, reps:int, seed:int) -> np.ndarray:
    rng=np.random.default_rng(seed)
    sampled=rng.integers(0,nclusters,size=(reps,nclusters),endpoint=False)
    mult=np.zeros((reps,nclusters),dtype=np.int16)
    rows=np.arange(reps)[:,None]
    np.add.at(mult,(np.broadcast_to(rows,sampled.shape),sampled),1)
    return mult[:,codes]


def bootstrap_weighted_mean(values: Iterable[float], weights: Iterable[float], *, reps:int=400, seed:int=20260816, donors:Iterable[Any]|None=None) -> dict[str,float]|None:
    x=np.asarray(list(values),float); w=np.asarray(list(weights),float)
    if donors is None:
        d=np.arange(len(x)).astype(str)
    else:d=np.asarray(list(donors),dtype=object).astype(str)
    ok=np.isfinite(x)&np.isfinite(w)&(w>0)&pd.notna(d); x,w,d=x[ok],w[ok],d[ok]
    if len(x)<2:return None
    point=float(np.average(x,weights=w)); codes,uniques=pd.factorize(d,sort=False); m=len(uniques)
    if m<2:return {"estimate":point,"low":point,"high":point,"reps":0}
    mult=_cluster_multipliers(codes,m,reps,seed); wb=mult*w[None,:]; den=wb.sum(axis=1)
    vals=np.divide((wb*x[None,:]).sum(axis=1),den,out=np.full(reps,np.nan),where=den>0); vals=vals[np.isfinite(vals)]
    lo,hi=np.quantile(vals,[.025,.975]); return {"estimate":point,"low":float(lo),"high":float(hi),"reps":int(len(vals))}


def bootstrap_weighted_distribution(values: pd.Series, categories:list[str], weights:Iterable[float], *, reps:int=400, seed:int=20260816, donors:Iterable[Any]|None=None) -> dict[str,dict[str,float]]:
    s=values.astype(object).to_numpy(); w=np.asarray(list(weights),float)
    d=np.arange(len(s)).astype(str) if donors is None else np.asarray(list(donors),dtype=object).astype(str)
    ok=pd.notna(s)&np.isfinite(w)&(w>0)&pd.notna(d); s,w,d=s[ok],w[ok],d[ok]
    if not len(s):return {str(c):{"estimate":0.,"low":0.,"high":0.,"reps":0} for c in categories}
    codes,uniques=pd.factorize(d,sort=False); m=len(uniques); ss=s.astype(str); denom0=float(w.sum())
    if m>=2: mult=_cluster_multipliers(codes,m,reps,seed); wb=mult*w[None,:]; den=wb.sum(axis=1)
    out={}
    for c0 in categories:
        c=str(c0); point=100.*float(w[ss==c].sum())/denom0 if denom0 else 0.
        if m<2: lo=hi=point; rr=0
        else:
            num=(wb*(ss[None,:]==c)).sum(axis=1); vals=np.divide(num,den,out=np.zeros(reps),where=den>0)*100.; lo,hi=np.quantile(vals,[.025,.975]); rr=reps
        out[c]={"estimate":round(point,1),"low":round(float(lo),1),"high":round(float(hi),1),"reps":int(rr)}
    return out


def cluster_bootstrap_binary(hit: Iterable[float], weights: Iterable[float], donors: Iterable[Any], *, reps:int=350, seed:int=20260816) -> dict[str,float]|None:
    return bootstrap_weighted_mean(hit,weights,reps=reps,seed=seed,donors=donors)


def combine_interval_components(*,sampling:dict[str,float]|None,model_sd:float|None=None,sensitivity_sd:float|None=None)->dict[str,Any]|None:
    if not sampling:return None
    est=float(sampling["estimate"]); se=max(0.,(float(sampling["high"])-float(sampling["low"]))/(2*1.96)); ms=float(model_sd or 0); ps=float(sensitivity_sd or 0); total=math.sqrt(se*se+ms*ms+ps*ps)
    return {"estimate":est,"low":est-1.96*total,"high":est+1.96*total,"components":{"sampling_se":se,"model_sd":ms if model_sd is not None else None,"panel_sensitivity_sd":ps if sensitivity_sd is not None else None},"note":"Interval zahrnuje dostupné složky; donor bootstrap je cluster-aware."}


def n_guard(df:pd.DataFrame, threshold:float=50.0, topics:Iterable[str]|None=None, *, layer:str|None=None)->dict[str,Any]:
    s=donor_support(df,topics,layer=layer)
    # WP3: hard suppression is donor count <25; 25-49 is reportable only as indicative.
    s.update({"allowed":bool(s["n_unique_layer_donors"]>=25),"threshold":25.0,"indicative_threshold":50.0})
    s["effective_n"]=s["effective_n_combined"]
    return s
