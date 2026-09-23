from __future__ import annotations
import json, os, time, shutil, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.neighbors import NearestNeighbors
from .registry import Registry

CORE=["pohlavi","vek","vzdelani","kraj","trida_spolecenska","employment_status"]

def complete_from_donors(new:pd.DataFrame,reference:pd.DataFrame,*,seed=20260814,k=5)->tuple[pd.DataFrame,pd.DataFrame]:
    """Complete Track-A rows to the active panel schema without mutating donors.

    Measured incoming cells are preserved. Missing derived layers are copied from
    one of k nearest donor rows based ONLY on shared core sociodemography. This is
    explicitly provenance='imputovano', never 'mereno'.
    """
    incoming=new.copy(); shared=[c for c in CORE if c in incoming.columns and c in reference.columns]
    if not shared:raise ValueError("Track A needs at least one shared core demographic column.")
    num=[c for c in shared if c=="vek" or (pd.api.types.is_numeric_dtype(reference[c]) and pd.api.types.is_numeric_dtype(incoming[c]))]
    cat=[c for c in shared if c not in num]
    tr=ColumnTransformer([
      ("n",Pipeline([("i",SimpleImputer(strategy="median")),("s",StandardScaler())]),num),
      ("c",Pipeline([("i",SimpleImputer(strategy="most_frequent")),("o",OneHotEncoder(handle_unknown="ignore"))]),cat)
    ])
    allx=pd.concat([reference[shared],incoming[shared]],ignore_index=True); X=tr.fit_transform(allx)
    R=X[:len(reference)]; N=X[len(reference):]
    nn=NearestNeighbors(n_neighbors=min(k,len(reference))).fit(R); dist,idx=nn.kneighbors(N)
    rng=np.random.default_rng(seed); chosen=[]
    for ds,ids in zip(dist,idx):
        w=1/(ds+0.05); w=w/w.sum(); chosen.append(int(rng.choice(ids,p=w)))
    donors=reference.iloc[chosen].reset_index(drop=True)
    # One reindex instead of ~200 column inserts: faster and avoids fragmented frames.
    out=incoming.reindex(columns=reference.columns).copy()
    prov=[]
    for c in reference.columns:
        measured=(incoming[c].notna() if c in incoming.columns else pd.Series(False,index=incoming.index))
        miss=~measured
        if miss.any():
            # Preserve object/string compatibility before assigning donor values.
            if reference[c].dtype == object or pd.api.types.is_string_dtype(reference[c]):
                out[c]=out[c].astype(object)
            out.loc[miss,c]=donors.loc[miss,c].to_numpy()
        layer=("sociodemo" if c in CORE else "dispozice" if c.startswith(("D_","M_","F_")) else
               "osobnost" if c.startswith(("H_","E_","X_","A_","C_","O_","TCI_","Air_","Earth_","Fire_","Water_")) else "ostatni")
        prov.append({"column":c,"layer":layer,"measured_cells":int(measured.sum()),"imputed_cells":int(miss.sum())})
    return out,pd.DataFrame(prov)


def _next_version(reg:Registry,prefix="v14.ingest"):
    rows=reg.cx.execute("SELECT verze FROM verze WHERE verze LIKE ?",(prefix+".%",)).fetchall()
    nums=[]
    for r in rows:
        try:nums.append(int(str(r[0]).rsplit(".",1)[1]))
        except:pass
    return f"{prefix}.{max(nums,default=0)+1}"


def merge_track_a(new:pd.DataFrame,active_path:str|Path,reg:Registry,*,upload_id:int|None=None,seed=20260814,
                  versions_dir:str|Path="data/panel_versions")->dict:
    ref=pd.read_csv(active_path,low_memory=False); completed,prov=complete_from_donors(new,ref,seed=seed)
    merged=pd.concat([ref,completed],ignore_index=True)
    if "panel_row_id" in merged:
        merged["panel_row_id"]=[f"P{n:07d}" for n in range(1,len(merged)+1)]
    # Track A must not move the population backbone merely because new donor rows
    # were appended. Re-rake to the active version's existing joint backbone
    # distribution (prefer explicit Census anchor, otherwise age×sex×region).
    wcol="vaha_kalibrovana"
    if "backbone_anchor" in ref.columns and ref["backbone_anchor"].notna().any():
        rw=pd.to_numeric(ref[wcol],errors="coerce").fillna(1.0)
        sh=ref.assign(_w=rw).groupby("backbone_anchor",dropna=False)["_w"].sum(); sh=sh/sh.sum()
        targets=pd.DataFrame({"variable":"backbone_anchor","category":sh.index.astype(str),"target_share":sh.values})
        merged,_backbone_qc=rake_targets(merged,targets,weight_col=wcol)
    else:
        merged["_ingest_ageband"]=pd.cut(pd.to_numeric(merged["vek"],errors="coerce"),[17,24,34,44,54,64,74,200],labels=["18-24","25-34","35-44","45-54","55-64","65-74","75+"]).astype(str)
        ref2=ref.copy(); ref2["_ingest_ageband"]=pd.cut(pd.to_numeric(ref2["vek"],errors="coerce"),[17,24,34,44,54,64,74,200],labels=["18-24","25-34","35-44","45-54","55-64","65-74","75+"]).astype(str)
        rw=pd.to_numeric(ref2[wcol],errors="coerce").fillna(1.0); key=ref2[["_ingest_ageband","pohlavi","kraj"]].astype(str).agg("|".join,axis=1); sh=pd.Series(rw.to_numpy(),index=key).groupby(level=0).sum();sh=sh/sh.sum()
        targets=pd.DataFrame({"variable":"_ingest_ageband&pohlavi&kraj","category":sh.index,"target_share":sh.values})
        merged,_backbone_qc=rake_targets(merged,targets,weight_col=wcol); merged=merged.drop(columns=["_ingest_ageband"])
    ver=_next_version(reg); vd=Path(versions_dir); vd.mkdir(parents=True,exist_ok=True)
    target=vd/f"panel_{ver}.csv"; tmp=target.with_suffix(".tmp.csv")
    merged.to_csv(tmp,index=False); os.replace(tmp,target)
    prov_path=vd/f"panel_{ver}_provenance.csv"; prov.to_csv(prov_path,index=False)
    parquet_path=None
    try:
        parquet_path=vd/f"panel_{ver}.parquet"; merged.to_parquet(parquet_path,index=False)
    except Exception:
        parquet_path=None
    parent=reg.active_version(); reg.register_version(ver,target,rodic=parent["verze"] if parent else None,
        upload_id=upload_id,n_radku=len(merged),changelog=f"Track A +{len(new)} rows; donor completion for missing layers",activate=True)
    return {"version":ver,"path":str(target.resolve()),"parquet":str(parquet_path.resolve()) if parquet_path else None,"provenance":str(prov_path.resolve()),"n":len(merged),"added":len(new),"backbone_qc":_backbone_qc}


def rake_targets(panel:pd.DataFrame,targets:pd.DataFrame,*,weight_col="vaha_kalibrovana",max_iter=80,tol=1e-7,trim=5.0)->tuple[pd.DataFrame,dict]:
    req={"variable","category","target_share"}
    t=targets.rename(columns={"promenna":"variable","kategorie":"category","cil":"target_share"})
    if not req<=set(t.columns):raise ValueError("Track B targets need variable, category, target_share")
    out=panel.copy(); w=pd.to_numeric(out.get(weight_col,1.0),errors="coerce").fillna(1.0).to_numpy(float)
    w=np.clip(w,1e-9,None); w/=w.mean()
    for it in range(max_iter):
        old=w.copy()
        for var,g in t.groupby("variable"):
            vars_=str(var).split("&")
            if any(v not in out for v in vars_):raise KeyError(f"Target variable missing: {var}")
            key=out[vars_].astype(str).agg("|".join,axis=1) if len(vars_)>1 else out[vars_[0]].astype(str)
            for _,r in g.iterrows():
                mask=(key==str(r["category"])).to_numpy(); cur=w[mask].sum()/w.sum() if mask.any() else 0
                target=float(r["target_share"])
                if target<0 or target>1:raise ValueError("target_share must be 0..1")
                if target>0 and not mask.any():raise ValueError(f"No support for target {var}={r['category']}")
                if cur>0:w[mask]*=target/cur
        w/=w.mean()
        med=np.median(w); cap=trim*med
        excess=np.maximum(w-cap,0).sum(); w=np.minimum(w,cap)
        if excess>0:w+=excess/len(w)
        if np.max(np.abs(w-old))<tol:break
    out[weight_col]=w
    checks=[]
    for var,g in t.groupby("variable"):
        vars_=str(var).split("&"); key=out[vars_].astype(str).agg("|".join,axis=1) if len(vars_)>1 else out[vars_[0]].astype(str)
        for _,r in g.iterrows():
            mask=(key==str(r["category"])).to_numpy(); actual=w[mask].sum()/w.sum()
            checks.append({"variable":var,"category":r["category"],"target":float(r["target_share"]),"actual":float(actual),"error":float(actual-r["target_share"])})
    return out,{"iterations":it+1,"max_abs_error":max(abs(x["error"]) for x in checks) if checks else 0,"checks":checks}


def merge_track_b(targets:pd.DataFrame,active_path:str|Path,reg:Registry,*,upload_id=None,versions_dir="data/panel_versions"):
    ref=pd.read_csv(active_path,low_memory=False); out,qc=rake_targets(ref,targets)
    ver=_next_version(reg); vd=Path(versions_dir); vd.mkdir(parents=True,exist_ok=True); target=vd/f"panel_{ver}.csv"; tmp=target.with_suffix(".tmp.csv")
    out.to_csv(tmp,index=False); os.replace(tmp,target); parent=reg.active_version()
    parquet_path=None
    try:
        parquet_path=vd/f"panel_{ver}.parquet"; out.to_parquet(parquet_path,index=False)
    except Exception:
        parquet_path=None
    target_payload=targets[[c for c in targets.columns if c in {"variable","category","target_share","promenna","kategorie","cil"}]].to_dict("records")
    hash_cilu=hashlib.sha256(json.dumps(target_payload,sort_keys=True,ensure_ascii=False,default=str).encode("utf-8")).hexdigest()
    reg.register_version(ver,target,rodic=parent["verze"] if parent else None,upload_id=upload_id,n_radku=len(out),hash_cilu=hash_cilu,changelog="Track B recalibration",activate=True)
    return {"version":ver,"path":str(target.resolve()),"parquet":str(parquet_path.resolve()) if parquet_path else None,"n":len(out),"qc":qc,"hash_cilu":hash_cilu}
