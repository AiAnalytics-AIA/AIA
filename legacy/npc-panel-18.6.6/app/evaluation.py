"""B0–B4 evaluation utilities for smoke/holdout benchmarks."""
from __future__ import annotations
from typing import Any
import numpy as np


def normalize_dist(d:dict[str,float],cats:list[str]|None=None)->dict[str,float]:
    cats=cats or list(d)
    vals=np.array([max(0.0,float(d.get(c,0))) for c in cats],float)
    s=vals.sum(); vals=vals/s if s else np.ones(len(vals))/len(vals)
    return {c:float(v) for c,v in zip(cats,vals)}

def tvd(a:dict[str,float],b:dict[str,float],cats:list[str]|None=None)->float:
    cats=cats or sorted(set(a)|set(b)); A=normalize_dist(a,cats); B=normalize_dist(b,cats)
    return float(.5*sum(abs(A[c]-B[c]) for c in cats))

def bootstrap_tvd(samples:list[dict[str,float]],truth:dict[str,float],*,seed=20260814,n_boot=1000)->dict[str,float]:
    if not samples:return {"median":float("nan"),"lo":float("nan"),"hi":float("nan")}
    rng=np.random.default_rng(seed); cats=sorted(set(truth)|set().union(*(x.keys() for x in samples)))
    vals=[]
    for _ in range(n_boot):
        ix=rng.integers(0,len(samples),len(samples)); m={c:np.mean([normalize_dist(samples[i],cats)[c] for i in ix]) for c in cats}
        vals.append(tvd(m,truth,cats))
    return {"median":float(np.median(vals)),"lo":float(np.quantile(vals,.025)),"hi":float(np.quantile(vals,.975))}

def kendall_tau(a:list[float],b:list[float])->float|None:
    if len(a)!=len(b) or len(a)<2:return None
    concord=discord=0
    for i in range(len(a)):
        for j in range(i+1,len(a)):
            x=(a[i]-a[j])*(b[i]-b[j])
            concord+=x>0; discord+=x<0
    den=concord+discord
    return float((concord-discord)/den) if den else 0.0

def compare_variants(truth:dict[str,dict[str,float]],predictions:dict[str,dict[str,dict[str,float]]])->dict[str,Any]:
    """truth[benchmark][cat], predictions[variant][benchmark][cat]."""
    out={}
    for variant,bench in predictions.items():
        rows=[]
        for bid,t in truth.items():
            if bid not in bench:continue
            rows.append({"benchmark":bid,"tvd":tvd(bench[bid],t)})
        out[variant]={"mean_tvd":float(np.mean([r["tvd"] for r in rows])) if rows else None,"rows":rows}
    if "B2" in out and "B3" in out and out["B2"]["mean_tvd"] is not None:
        b2=out["B2"]["mean_tvd"]; b3=out["B3"]["mean_tvd"]
        imp=(b2-b3)/b2 if b2 else 0
        out["anchor_decision"]="FULL" if imp>=.30 else "SELECTIVE" if imp>=.10 else "DO_NOT_BUILD_OR_USE"
        out["anchor_improvement_pct"]=round(100*imp,2)
    return out
