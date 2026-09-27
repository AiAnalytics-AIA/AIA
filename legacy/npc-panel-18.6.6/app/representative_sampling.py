from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd

DEFAULT_FIELDS=("pohlavi","vek_skupina","kraj","vzdelani","zamestnani_status")


def _clean_weights(df: pd.DataFrame, weights: np.ndarray | pd.Series | None = None) -> np.ndarray:
    if weights is None:
        if "_analysis_weight" in df.columns:
            w=pd.to_numeric(df["_analysis_weight"],errors="coerce").to_numpy(float)
        elif "vaha_kalibrovana" in df.columns:
            w=pd.to_numeric(df["vaha_kalibrovana"],errors="coerce").to_numpy(float)
        else:w=np.ones(len(df),float)
    else:w=np.asarray(weights,dtype=float)
    w=np.where(np.isfinite(w)&(w>0),w,0.0)
    if w.sum()<=0:w=np.ones(len(df),float)
    return w


def _targets(df:pd.DataFrame,w:np.ndarray,fields:list[str])->dict[str,dict[str,float]]:
    out={}
    for f in fields:
        if f not in df.columns:continue
        x=df[f].astype("string").fillna("<missing>")
        tmp=pd.DataFrame({"x":x,"w":w}).groupby("x",dropna=False)["w"].sum()
        if tmp.sum()>0:out[f]={str(k):float(v/tmp.sum()) for k,v in tmp.items()}
    return out


def _audit(sample:pd.DataFrame,targets:dict[str,dict[str,float]],weight_col:str|None=None)->dict[str,Any]:
    diffs={};counts={};max_pp=0.0;mean_parts=[]
    sw=None
    if weight_col and weight_col in sample.columns:
        sw=pd.to_numeric(sample[weight_col],errors="coerce").fillna(0).to_numpy(float)
    for f,t in targets.items():
        if f not in sample.columns:continue
        x=sample[f].astype("string").fillna("<missing>")
        if sw is None:
            vc=x.value_counts(normalize=True); raw_counts=x.value_counts()
            got={str(k):float(v) for k,v in vc.items()}; cts={str(k):int(v) for k,v in raw_counts.items()}
        else:
            tmp=pd.DataFrame({"x":x,"w":sw}).groupby("x")["w"].sum();den=float(tmp.sum()) or 1.0
            got={str(k):float(v/den) for k,v in tmp.items()};cts={str(k):round(float(v),3) for k,v in tmp.items()}
        fd={}
        for k,p in t.items():
            d=100.0*(got.get(k,0.0)-p);fd[k]=round(d,3);max_pp=max(max_pp,abs(d));mean_parts.append(abs(d))
        diffs[f]=fd;counts[f]=cts
    return {"max_abs_pp":round(max_pp,3),"mean_abs_pp":round(float(np.mean(mean_parts)) if mean_parts else 0.0,3),"diff_pp":diffs,"counts":counts}


def _rake(sample:pd.DataFrame,targets:dict[str,dict[str,float]],base_col:str="_base_sample_weight",iterations:int=60)->np.ndarray:
    w=pd.to_numeric(sample[base_col],errors="coerce").fillna(1.0).clip(lower=1e-9).to_numpy(float)
    for _ in range(iterations):
        old=w.copy()
        for f,t in targets.items():
            if f not in sample.columns:continue
            vals=sample[f].astype("string").fillna("<missing>").to_numpy();total=float(w.sum()) or 1.0
            for cat,p in t.items():
                mask=vals==cat;cur=float(w[mask].sum())/total
                if mask.any() and cur>0:w[mask]*=p/cur
        cap=(np.quantile(w,0.99)*8 if len(w)>20 else np.max(w)*8)
        w=np.clip(w,1e-6,max(cap,1e-6));w/=float(np.mean(w)) or 1.0
        if np.max(np.abs(w-old))<1e-8:break
    return w


def _milp_cell_quotas(df:pd.DataFrame,w:np.ndarray,fields:list[str],targets:dict[str,dict[str,float]],n:int)->tuple[pd.Series,dict[str,Any]]:
    """Integer-calibrate joint cell counts to all core margins at once.

    Variables are cell counts, not respondents, so the optimization stays small even
    for a ~20k-person synthetic panel. Marginal deviations have the dominant penalty;
    a small secondary penalty keeps the full joint-cell distribution close to the
    weighted target population.
    """
    from scipy.optimize import milp, Bounds, LinearConstraint
    from scipy.sparse import lil_matrix

    key_df=df[fields].astype("string").fillna("<missing>")
    keys=key_df.agg("¦".join,axis=1)
    tmp=pd.DataFrame({"key":keys,"w":w})
    grp=tmp.groupby("key",sort=True).agg(capacity=("w","size"),weight=("w","sum"))
    cell_keys=list(grp.index);J=len(cell_keys);caps=grp["capacity"].to_numpy(float)
    exp=n*grp["weight"].to_numpy(float)/float(grp["weight"].sum())
    # Decode categories by cell once.
    parts=[k.split("¦") for k in cell_keys]
    categories=[]
    for fi,f in enumerate(fields):
        for cat,p in targets.get(f,{}).items():categories.append((fi,f,str(cat),float(p)))
    K=len(categories)
    # q[J] + margin positive/negative [2K] + cell positive/negative [2J]
    nv=J+2*K+2*J
    c=np.zeros(nv,float)
    c[J:J+2*K]=1.0
    c[J+2*K:]=0.01
    integrality=np.zeros(nv,int);integrality[:J]=1
    lb=np.zeros(nv,float);ub=np.full(nv,np.inf,float);ub[:J]=caps
    # 1 total + K margins + J expected-cell soft equalities
    A=lil_matrix((1+K+J,nv),dtype=float);b=np.zeros(1+K+J,float)
    A[0,:J]=1.0;b[0]=n
    for k,(fi,f,cat,p) in enumerate(categories):
        for j,vals in enumerate(parts):
            if vals[fi]==cat:A[1+k,j]=1.0
        A[1+k,J+2*k]=-1.0;A[1+k,J+2*k+1]=1.0;b[1+k]=n*p
    off=1+K;slack0=J+2*K
    for j in range(J):
        A[off+j,j]=1.0;A[off+j,slack0+2*j]=-1.0;A[off+j,slack0+2*j+1]=1.0;b[off+j]=exp[j]
    cons=LinearConstraint(A.tocsr(),b,b)
    res=milp(c=c,integrality=integrality,bounds=Bounds(lb,ub),constraints=cons,options={"time_limit":20.0,"mip_rel_gap":0.0})
    if not res.success or res.x is None:raise RuntimeError(f"representative MILP failed: {res.message}")
    q=np.rint(res.x[:J]).astype(int)
    if int(q.sum())!=n or np.any(q<0) or np.any(q>caps+1e-8):raise RuntimeError("representative MILP returned invalid quotas")
    return pd.Series(q,index=cell_keys),{"solver":"scipy_milp","cells":J,"objective":float(res.fun),"message":str(res.message),"keys":keys}


def _quota_vector_fallback(df:pd.DataFrame,w:np.ndarray,fields:list[str],n:int,rng:np.random.Generator)->tuple[pd.Series,dict]:
    keys=df[fields].astype("string").fillna("<missing>").agg("¦".join,axis=1)
    work=pd.DataFrame({"key":keys,"w":w});cell=work.groupby("key").agg(weight=("w","sum"),capacity=("w","size"))
    exp=n*cell["weight"]/float(cell["weight"].sum());q=np.floor(exp).astype(int).clip(upper=cell["capacity"]);left=int(n-q.sum());frac=(exp-q).clip(lower=0)
    while left>0:
        avail=(q<cell["capacity"])
        if not avail.any():break
        scores=frac.where(avail,0).to_numpy(float)+rng.random(len(cell))*1e-9
        if scores.sum()<=0:scores=avail.to_numpy(float)
        j=int(np.argmax(scores));q.iloc[j]+=1;frac.iloc[j]=max(0.0,float(frac.iloc[j])-1.0);left-=1
    if int(q.sum())!=n:raise ValueError(f"Nelze sestavit unikátní reprezentativní vzorek N={n} z dostupné populace.")
    return q,{"keys":keys,"solver":"largest_remainder_fallback"}


def draw_representative(df:pd.DataFrame,n:int,*,seed:int|None=None,weights:np.ndarray|pd.Series|None=None,
                        attempts:int=32,fields:list[str]|None=None)->tuple[pd.DataFrame,dict[str,Any]]:
    if n<=0 or n>len(df):raise ValueError(f"Požadované N={n} není dostupné v populaci N={len(df)}.")
    base=_clean_weights(df,weights);all_fields=[f for f in (fields or list(DEFAULT_FIELDS)) if f in df.columns and df[f].nunique(dropna=True)>1]
    rng=np.random.default_rng(seed)
    if not all_fields:
        idx=rng.choice(np.arange(len(df)),size=n,replace=False,p=base/base.sum());out=df.iloc[idx].copy();out["_zdroj_index"]=out.index.to_numpy();out["_sample_poradi"]=range(n);out["_base_sample_weight"]=base[idx];out["_analysis_weight"]=out["_base_sample_weight"]/out["_base_sample_weight"].mean();audit={"status":"PASS","fields":[],"raw":{"max_abs_pp":0.0},"weighted":{"max_abs_pp":0.0},"statement":"Vzorek je reprezentativní v rámci zvolené populace."};out.attrs["representativeness"]=audit;return out.reset_index(drop=True),audit
    targets=_targets(df,base,all_fields)
    try:q,meta=_milp_cell_quotas(df,base,all_fields,targets,n)
    except Exception as exc:
        # Safe fallback keeps release usable on environments where scipy MILP is unavailable.
        joint=[f for f in ("pohlavi","vek_skupina","kraj") if f in all_fields]
        if n>=700 and "vzdelani" in all_fields:joint.append("vzdelani")
        if not joint:joint=all_fields[:2]
        q,meta=_quota_vector_fallback(df,base,joint,n,rng);meta["fallback_reason"]=str(exc);keys=meta["keys"]
    else:keys=meta.pop("keys")
    picks=[]
    key_arr=keys.to_numpy()
    for cell_key,count in q.items():
        count=int(count)
        if count<=0:continue
        pos=np.flatnonzero(key_arr==cell_key)
        if count>len(pos):raise RuntimeError(f"Buňka {cell_key} nemá dost respondentů pro reprezentativní výběr.")
        cw=base[pos];cw=np.where(np.isfinite(cw)&(cw>0),cw,0.0)
        prob=(cw/cw.sum()) if cw.sum()>0 else None
        chosen=rng.choice(pos,size=count,replace=False,p=prob);picks.extend(chosen.tolist())
    if len(picks)!=n:raise RuntimeError(f"Reprezentativní výběr vytvořil {len(picks)} místo N={n}.")
    rng.shuffle(picks);out=df.iloc[picks].copy();out["_zdroj_index"]=out.index.to_numpy();out["_sample_poradi"]=range(n);out["_base_sample_weight"]=base[picks]
    raw=_audit(out,targets);out["_analysis_weight"]=_rake(out,targets);weighted=_audit(out,targets,"_analysis_weight")
    # Integer granularity is the natural lower bound for small samples.  For a
    # category represented by one person, 100/N percentage points is already the
    # finest possible count resolution.  Do not apply a fixed 0.5 pp weighting gate
    # to N=32 (it is mathematically impossible); tighten automatically as N grows.
    raw_tol=max(0.50,100.0/max(n,1));weighted_tol=max(0.25,100.0/max(n,1))
    if weighted["max_abs_pp"]>weighted_tol+1e-9:
        raise RuntimeError(f"Vzorek N={n} nelze po kalibraci sestavit dostatečně reprezentativně (výběr max. {raw['max_abs_pp']} p. b.; po kalibraci max. {weighted['max_abs_pp']} p. b. / limit {round(weighted_tol,3)}). Zvětšete N nebo rozšiřte cílovou populaci.")
    aw=np.asarray(out["_analysis_weight"],dtype=float);ess=float((aw.sum()**2)/(np.square(aw).sum() or 1.0));raw_warn=bool(raw["max_abs_pp"]>raw_tol+1e-9)
    audit={"status":"PASS_WEIGHTED" if raw_warn else "PASS","population_n":int(len(df)),"sample_n":int(n),"fields":all_fields,"selection_method":meta.get("solver"),
           "raw":raw,"weighted":weighted,"raw_tolerance_pp":round(raw_tol,3),"weighted_tolerance_pp":weighted_tol,"raw_selection_warning":raw_warn,
           "effective_n":round(ess,3),"effective_n_ratio":round(ess/max(float(n),1.0),4),"weight_min":round(float(np.min(aw)),4),"weight_max":round(float(np.max(aw)),4),
           "statement":"Vzorek je reprezentativní po kalibraci na cílové marginály; výsledky používají analytické váhy." if raw_warn else "Vzorek je reprezentativně vybrán a kalibrován v rámci zvolené populace."}
    out.attrs["representativeness"]=audit
    return out.reset_index(drop=True),audit
