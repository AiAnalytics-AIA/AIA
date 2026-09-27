from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd

SENTINELS={99,999,-8,-9,-99,-999}

def domain_checks(df:pd.DataFrame, reference:pd.DataFrame|None=None)->list[dict[str,Any]]:
    f=[]
    if "vek" in df:
        v=pd.to_numeric(df["vek"],errors="coerce")
        n=int(((v<15)|(v>105)).sum());
        if n:f.append({"type":"age_range","n":n})
    if "vek" in df and "vzdelani" in df:
        v=pd.to_numeric(df["vek"],errors="coerce")
        bad=(v<19)&df["vzdelani"].astype(str).str.contains("VŠ|VOŠ|vysok",case=False,regex=True,na=False)
        if bad.any(): f.append({"type":"education_age_contradiction","n":int(bad.sum())})
    for c in df.select_dtypes(include=[np.number]).columns:
        s=pd.to_numeric(df[c],errors="coerce")
        n=int(s.isin(SENTINELS).sum())
        if n:f.append({"type":"sentinel","column":c,"n":n})
    dup=int(df.duplicated().sum())
    if dup:f.append({"type":"duplicate_rows","n":dup})
    # Cross-source duplicates are reported, never silently removed. IDs/free text are
    # excluded so we compare substantive shared cells only.
    if reference is not None and len(reference) and len(df):
        common=[c for c in df.columns if c in reference.columns and "id" not in c.lower()]
        common=[c for c in common if max(df[c].nunique(dropna=True),reference[c].nunique(dropna=True))<=200]
        if common:
            ref_keys=set(pd.util.hash_pandas_object(reference[common].astype(str).fillna("<NA>"),index=False).astype(str))
            new_hash=pd.util.hash_pandas_object(df[common].astype(str).fillna("<NA>"),index=False).astype(str)
            n_cross=int(new_hash.isin(ref_keys).sum())
            if n_cross:f.append({"type":"cross_source_exact_duplicates","n":n_cross,"columns":common})
    return f


def _matrix(ref:pd.DataFrame,new:pd.DataFrame):
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    common=[c for c in ref.columns if c in new.columns and not c.startswith("_")]
    # Exclude IDs/free text/high-cardinality columns.
    keep=[]
    for c in common:
        nun=max(ref[c].nunique(dropna=True),new[c].nunique(dropna=True))
        if "id" in c.lower() or nun>100: continue
        keep.append(c)
    if not keep: raise ValueError("Žádné společné modelovatelné sloupce pro realism gate.")
    num=[c for c in keep if pd.api.types.is_numeric_dtype(ref[c]) and pd.api.types.is_numeric_dtype(new[c])]
    cat=[c for c in keep if c not in num]
    tr=ColumnTransformer([
      ("num",Pipeline([("imp",SimpleImputer(strategy="median")),("sc",StandardScaler())]),num),
      ("cat",Pipeline([("imp",SimpleImputer(strategy="most_frequent")),("oh",OneHotEncoder(handle_unknown="ignore"))]),cat)
    ])
    both=pd.concat([ref[keep],new[keep]],ignore_index=True)
    X=tr.fit_transform(both)
    y=np.r_[np.zeros(len(ref),int),np.ones(len(new),int)]
    return X,y,keep


def propensity_mse(ref:pd.DataFrame,new:pd.DataFrame,*,seed=20260814,permutations=20)->dict[str,Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold,cross_val_predict
    if min(len(ref),len(new))<300:
        return energy_distance_test(ref,new,seed=seed,permutations=max(50,permutations))
    X,y,cols=_matrix(ref,new); pbar=float(y.mean())
    model=HistGradientBoostingClassifier(max_depth=5,learning_rate=.08,max_iter=120,random_state=seed)
    cv=StratifiedKFold(5,shuffle=True,random_state=seed)
    # HGB requires dense.
    if hasattr(X,"toarray"): X=X.toarray()
    pr=cross_val_predict(model,X,y,cv=cv,method="predict_proba")[:,1]
    pmse=float(np.mean((pr-pbar)**2))
    rng=np.random.default_rng(seed); null=[]
    for i in range(permutations):
        yp=rng.permutation(y)
        pp=cross_val_predict(model,X,yp,cv=3,method="predict_proba")[:,1]
        null.append(float(np.mean((pp-pbar)**2)))
    mu=float(np.mean(null)); sd=float(np.std(null,ddof=1) or 1e-9)
    z=(pmse-mu)/sd
    return {"metric":"pMSE","pmse":pmse,"null_mean":mu,"null_sd":sd,"z":float(z),
            "columns":cols,"n_ref":len(ref),"n_new":len(new)}


def energy_distance_test(ref:pd.DataFrame,new:pd.DataFrame,*,seed=20260814,permutations=100)->dict[str,Any]:
    # Robust small-N fallback on common numeric low-cardinality features.
    common=[c for c in ref.columns if c in new.columns and pd.api.types.is_numeric_dtype(ref[c]) and pd.api.types.is_numeric_dtype(new[c])]
    common=[c for c in common if "id" not in c.lower()][:20]
    if not common:return {"metric":"none","status":"REVIEW","reason":"no common numeric features"}
    A=ref[common].apply(pd.to_numeric,errors="coerce"); B=new[common].apply(pd.to_numeric,errors="coerce")
    med=pd.concat([A,B]).median(); sd=pd.concat([A,B]).std().replace(0,1)
    A=((A.fillna(med)-med)/sd).to_numpy(float); B=((B.fillna(med)-med)/sd).to_numpy(float)
    # cap samples for quadratic metric
    rng=np.random.default_rng(seed)
    if len(A)>400:A=A[rng.choice(len(A),400,replace=False)]
    if len(B)>400:B=B[rng.choice(len(B),400,replace=False)]
    def md(X,Y): return np.sqrt(((X[:,None,:]-Y[None,:,:])**2).sum(2)).mean()
    def stat(X,Y): return 2*md(X,Y)-md(X,X)-md(Y,Y)
    obs=float(stat(A,B)); Z=np.vstack([A,B]); na=len(A); null=[]
    for _ in range(permutations):
        ix=rng.permutation(len(Z)); null.append(float(stat(Z[ix[:na]],Z[ix[na:]])))
    p=(1+sum(v>=obs for v in null))/(1+len(null))
    return {"metric":"energy_distance","distance":obs,"permutation_p":float(p),"columns":common,"n_ref":len(A),"n_new":len(B)}


def assess(ref:pd.DataFrame,new:pd.DataFrame,*,threshold:dict[str,float]|None=None,seed=20260814)->dict[str,Any]:
    stats=propensity_mse(ref,new,seed=seed); findings=domain_checks(new,reference=ref)
    th=threshold or {}
    if stats["metric"]=="pMSE" and "pmse_z_max" in th:
        ok=stats["z"]<=th["pmse_z_max"]
    elif stats["metric"]=="energy_distance" and "energy_p_min" in th:
        ok=stats["permutation_p"]>=th["energy_p_min"]
    else:
        ok=None
    hard=any(x["type"] in {"age_range","sentinel"} for x in findings)
    decision="REJECT" if hard or ok is False else "ACCEPT" if ok is True else "REVIEW"
    return {"decision":decision,"statistic":stats,"findings":findings,"threshold_calibrated":bool(th)}


def calibrate_threshold(real_scores:list[float], synthetic_scores:list[float], *, metric:str="pMSE", max_real_reject_rate:float=.05)->dict[str,float]:
    """Calibrate a realism threshold from labelled historical examples.

    ``real_scores`` are scores observed when comparing genuine held-in sources to the
    reference population. The threshold is chosen so that at most approximately
    ``max_real_reject_rate`` of those known-real examples would be rejected.
    Synthetic scores are accepted only as diagnostics; they are returned as separation
    metadata by :func:`threshold_diagnostics` and never used to loosen the real-data
    false-positive constraint.
    """
    if not real_scores:
        raise ValueError("real_scores must contain at least one calibrated real-source score")
    if not 0 < max_real_reject_rate < .5:
        raise ValueError("max_real_reject_rate must be between 0 and .5")
    r=np.asarray(real_scores,float); r=r[np.isfinite(r)]
    if len(r)<3: raise ValueError("At least three real calibration scores are required")
    if metric=="pMSE":
        # Larger z = easier to distinguish from the real panel = worse.
        q=float(np.quantile(r,1-max_real_reject_rate,method="higher"))
        return {"pmse_z_max":q}
    if metric=="energy_distance":
        # Here the supplied score is the permutation p-value; lower = worse.
        q=float(np.quantile(r,max_real_reject_rate,method="lower"))
        return {"energy_p_min":q}
    raise ValueError(f"Unsupported realism metric: {metric}")

def threshold_diagnostics(real_scores:list[float], synthetic_scores:list[float], threshold:dict[str,float])->dict[str,Any]:
    r=np.asarray(real_scores,float); s=np.asarray(synthetic_scores,float)
    if "pmse_z_max" in threshold:
        t=float(threshold["pmse_z_max"]); return {
            "metric":"pMSE","threshold":t,
            "real_reject_rate":float(np.mean(r>t)) if len(r) else None,
            "synthetic_reject_rate":float(np.mean(s>t)) if len(s) else None,
        }
    if "energy_p_min" in threshold:
        t=float(threshold["energy_p_min"]); return {
            "metric":"energy_distance","threshold":t,
            "real_reject_rate":float(np.mean(r<t)) if len(r) else None,
            "synthetic_reject_rate":float(np.mean(s<t)) if len(s) else None,
        }
    raise ValueError("Unknown threshold shape")


def make_margin_only_twin(df: pd.DataFrame, *, n: int|None=None, seed: int=20260814) -> pd.DataFrame:
    """Create a deliberately structure-poor negative-control twin.

    Each column is independently permuted/resampled, preserving its observed marginal
    distribution while destroying cross-variable respondent-level relationships. This
    is a diagnostic negative control for realism-threshold calibration; it must never
    be ingested as population data.
    """
    if df.empty:
        return df.copy()
    rng=np.random.default_rng(seed); n=int(n or len(df))
    out={}
    for c in df.columns:
        vals=df[c].to_numpy(copy=True)
        if n==len(vals):
            out[c]=vals[rng.permutation(len(vals))]
        else:
            out[c]=vals[rng.integers(0,len(vals),size=n)]
    return pd.DataFrame(out,columns=df.columns)
