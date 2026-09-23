"""Validation gates for tracked-object studies — NPC Panel 10.12.

10.12 removes two invalid universal assumptions from the old V4/V5 gates:
* a good object battery does NOT need to contain a negative correlation;
* categorical demographics do NOT have a meaningful Pearson correlation after arbitrary
  factorisation, and demographic differentiation is not required for a useful map.

Blocking now focuses on whether the map is mathematically identifiable and supported by
actual variation/coverage. Demographic differentiation remains an informative diagnostic.
"""
from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd


def object_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("obj_")]


def characteristic_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith(("dem_", "att_", "beh_", "bin_"))]


def ipsatize(df: pd.DataFrame, cols: list[str] | None = None) -> pd.DataFrame:
    cols = cols or object_columns(df)
    x = df[cols].apply(pd.to_numeric, errors="coerce")
    return x.sub(x.mean(axis=1, skipna=True), axis=0)


def _pc1_share(x: pd.DataFrame) -> float | None:
    a=x.to_numpy(float); a=np.where(np.isfinite(a),a,0.0)
    if min(a.shape)<2 or np.allclose(a.std(axis=0),0): return None
    _,s,_=np.linalg.svd(a-a.mean(axis=0),full_matrices=False); v=s*s
    return float(v[0]/v.sum()) if v.sum() else None


def _corr_vector(x: pd.DataFrame) -> np.ndarray:
    c=x.corr(min_periods=max(10,int(len(x)*.1))).to_numpy(float)
    if len(c)<2:return np.array([],dtype=float)
    v=c[np.triu_indices(len(c),1)]
    return v[np.isfinite(v)]


def _object_quality(df: pd.DataFrame, objs: list[str]) -> dict[str,Any]:
    per={}; ok=True
    for c in objs:
        s=pd.to_numeric(df[c],errors="coerce")
        n=int(s.notna().sum()); sd=float(s.std()) if n>1 else 0.0; unique=int(s.nunique(dropna=True))
        cov=float(n/len(df)) if len(df) else 0.0
        good=n>=max(30,int(.20*len(df))) and unique>=3 and np.isfinite(sd) and sd>=.35
        ok &= good
        per[c]={"n":n,"coverage":cov,"sd":sd,"unique":unique,"pass":bool(good)}
    return {"pass":bool(ok and len(objs)>=4),"objects":per}


def _redundancy(df: pd.DataFrame, objs: list[str]) -> dict[str,Any]:
    c=df[objs].apply(pd.to_numeric,errors="coerce").corr(min_periods=max(20,int(len(df)*.1)))
    pairs=[]
    for i,a in enumerate(objs):
        for j in range(i+1,len(objs)):
            r=c.iloc[i,j]
            if np.isfinite(r): pairs.append({"a":a,"b":objs[j],"r":float(r)})
    pairs=sorted(pairs,key=lambda x:-abs(x["r"]))
    maxabs=abs(pairs[0]["r"]) if pairs else None
    # Near-duplicates collapse map geometry; ordinary positive correlation is fine.
    return {"pass":bool(maxabs is not None and maxabs < .97),"max_abs_correlation":maxabs,
            "most_redundant_pairs":pairs[:10]}


def _eta_squared(cat: pd.Series, x: pd.Series) -> float | None:
    ok=cat.notna() & x.notna(); cat=cat[ok].astype(str); x=pd.to_numeric(x[ok],errors="coerce")
    ok=x.notna();cat=cat[ok];x=x[ok]
    if len(x)<30 or cat.nunique()<2 or x.nunique()<2:return None
    mu=float(x.mean()); den=float(((x-mu)**2).sum())
    if den<=0:return None
    num=0.0
    for _,g in x.groupby(cat): num += len(g)*(float(g.mean())-mu)**2
    return float(max(0.0,min(1.0,num/den)))


def _demo_object_associations(df: pd.DataFrame, objs: list[str]) -> list[dict[str,Any]]:
    found=[]
    for d in [c for c in df if c.startswith("dem_")]:
        raw=df[d]
        numeric=pd.to_numeric(raw,errors="coerce")
        numeric_ok=numeric.notna().sum()>=max(30,int(.8*raw.notna().sum())) and numeric.nunique()>3
        for o in objs:
            x=pd.to_numeric(df[o],errors="coerce")
            if numeric_ok:
                ok=numeric.notna()&x.notna()
                if ok.sum()<30 or x[ok].nunique()<2:continue
                r=float(pd.Series(numeric[ok]).corr(pd.Series(x[ok]),method="spearman"))
                if np.isfinite(r):found.append({"demo":d,"object":o,"metric":"spearman_r","value":r})
            else:
                eta=_eta_squared(raw,x)
                if eta is not None:found.append({"demo":d,"object":o,"metric":"eta_squared","value":eta})
    return sorted(found,key=lambda z:-abs(z["value"]))


def _relation_stability(df: pd.DataFrame, objs: list[str], *, seed:int=12012, boot:int=12) -> dict[str,Any]:
    x=df[objs].apply(pd.to_numeric,errors="coerce")
    base=_corr_vector(x)
    if len(base)<3 or len(x)<60:return {"pass":None,"status":"NOT_ENOUGH_DATA"}
    rng=np.random.default_rng(seed); vals=[]
    # Pair ordering is stable because each bootstrap uses the same columns; NaN pair
    # differences are handled by recomputing full vectors from filled pairwise corr.
    bc=x.corr(min_periods=max(10,int(len(x)*.1)))
    tri=np.triu_indices(len(objs),1); bvec=bc.to_numpy()[tri]
    for _ in range(boot):
        ix=rng.integers(0,len(x),len(x)); cc=x.iloc[ix].corr(min_periods=max(10,int(len(x)*.1))).to_numpy()[tri]
        ok=np.isfinite(bvec)&np.isfinite(cc)
        if ok.sum()>=3 and np.std(bvec[ok])>0 and np.std(cc[ok])>0:
            r=np.corrcoef(bvec[ok],cc[ok])[0,1]
            if np.isfinite(r):vals.append(float(r))
    if not vals:return {"pass":None,"status":"NOT_COMPUTABLE"}
    med=float(np.median(vals)); return {"pass":med>=.70,"median_relation_correlation":med,"bootstrap":vals}


def _transformation_sensitivity(df: pd.DataFrame, objs:list[str]) -> dict[str,Any]:
    raw=df[objs].apply(pd.to_numeric,errors="coerce")
    ip=ipsatize(df,objs)
    a=raw.corr(min_periods=max(10,int(len(df)*.1))).to_numpy(); b=ip.corr(min_periods=max(10,int(len(df)*.1))).to_numpy()
    tri=np.triu_indices(len(objs),1); av=a[tri];bv=b[tri];ok=np.isfinite(av)&np.isfinite(bv)
    if ok.sum()<3 or np.std(av[ok])==0 or np.std(bv[ok])==0:return {"pass":None,"status":"NOT_COMPUTABLE"}
    r=float(np.corrcoef(av[ok],bv[ok])[0,1])
    return {"pass":r>=.55,"raw_vs_ipsatized_relation_correlation":r}


def validate_study_dataset(df: pd.DataFrame, *, real_seed: pd.DataFrame | None=None,
                           segment_metrics: dict[str,Any] | None=None,
                           stress_1: float | None=None,
                           scale_domains: dict[str,tuple[int,int]] | None=None) -> dict[str,Any]:
    objs=object_columns(df);chars=characteristic_columns(df);gates={}
    violations=[];domains=scale_domains or {}
    for c in df.columns:
        s=pd.to_numeric(df[c],errors="coerce").dropna()
        if c in domains: lo,hi=domains[c];bad=s[(s<lo)|(s>hi)]
        elif c.startswith(("obj_","att_")):bad=s[(s<1)|(s>10)]
        elif c.startswith(("fam_","bin_")):bad=s[~s.isin([0,1])]
        elif c.startswith("beh_"):bad=s[(s<1)|(s>5)]
        else:continue
        if len(bad):violations.append({"var":c,"n":int(len(bad)),"examples":bad.head(5).tolist()})
    gates["V1"]={"pass":not violations,"violations":violations,"blocking":True}

    coverage={};v2=True
    for c in objs+[c for c in df if c.startswith("att_")]:
        s=pd.to_numeric(df[c],errors="coerce").dropna();used=sorted(set(int(x) for x in s if float(x).is_integer()));coverage[c]=used
        if len(s)>=40 and len(set(used)&set(range(1,11)))<6:v2=False
    gates["V2"]={"pass":v2,"coverage":coverage,"blocking":False}

    pc1=_pc1_share(ipsatize(df,objs));gates["V3"]={"pass":pc1 is not None and pc1<=.55,"pc1_share":pc1,"blocking":True}
    gates["V4"]={**_redundancy(df,objs),"meaning":"near-duplicate object check; negative correlation is NOT required","blocking":True}
    gates["V5"]={**_object_quality(df,objs),"meaning":"coverage/variance/unique-value support","blocking":True}

    assocs=_demo_object_associations(df,objs)
    gates["DEMO_DIFFERENTIATION"]={"pass":None,"status":"DIAGNOSTIC_ONLY","top_associations":assocs[:30],
        "note":"Categorical demographics use eta-squared; numeric/ordinal demographics use Spearman. No arbitrary category coding and no minimum differentiation is required."}
    gates["MAP_RELATION_STABILITY"]={**_relation_stability(df,objs),"blocking":False}
    gates["TRANSFORMATION_SENSITIVITY"]={**_transformation_sensitivity(df,objs),"blocking":False}

    dead=[]
    for c in chars:
        raw=df[c]
        if raw.notna().sum()<20 or raw.nunique(dropna=True)<=1:dead.append(c)
    gates["V6"]={"pass":not dead,"dead_variables":dead,"blocking":False}

    if real_seed is None:gates["V7"]={"pass":None,"status":"NOT_RUN_NO_REAL_SEED","variance_ratios":{}}
    else:
        ratios={}
        for c in [x for x in objs+chars if x in real_seed.columns]:
            a=pd.to_numeric(df[c],errors="coerce").var();b=pd.to_numeric(real_seed[c],errors="coerce").var()
            if pd.notna(a) and pd.notna(b) and b>0:ratios[c]=float(a/b)
        key={k:v for k,v in ratios.items() if np.isfinite(v)};gates["V7"]={"pass":bool(key) and all(.7<=v<=1.3 for v in key.values()),"variance_ratios":key,"blocking":False}
    sm=segment_metrics or {}
    gates["V8"]={"pass":None,"status":"NOT_RUN_NO_SEGMENTATION"} if not sm else {"pass":sm.get("bootstrap_ari") is not None and sm.get("entropy") is not None and sm.get("bootstrap_ari")>.6 and sm.get("entropy")>.8,"bootstrap_ari":sm.get("bootstrap_ari"),"entropy":sm.get("entropy"),"blocking":False}
    if stress_1 is not None:gates["MAP_STRESS"]={"pass":stress_1<=.18,"stress_1":stress_1,"blocking":True}

    blocking=[k for k,v in gates.items() if v.get("blocking")]
    fail=[k for k in blocking if gates[k].get("pass") is not True]
    return {"status":"BLOCK" if fail else "PASS","blocking_failures":fail,"gates":gates,
            "object_columns":objs,"characteristic_columns":chars}
