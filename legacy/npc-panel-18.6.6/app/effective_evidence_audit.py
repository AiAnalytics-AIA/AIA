"""Audit effective evidence content of D_* dimensions beyond basic demographics."""
from __future__ import annotations
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold,cross_val_score
from dimension_catalog import DIMENZE

DEMO=["pohlavi","vek","vzdelani","kraj","trida_spolecenska","employment_status"]

def audit(panel:pd.DataFrame, *, folds=5, seed=20260814)->pd.DataFrame:
    xcols=[c for c in DEMO if c in panel]
    num=[c for c in xcols if pd.api.types.is_numeric_dtype(panel[c])]; cat=[c for c in xcols if c not in num]
    tr=ColumnTransformer([("n",Pipeline([("i",SimpleImputer(strategy="median")),("s",StandardScaler())]),num),("c",Pipeline([("i",SimpleImputer(strategy="most_frequent")),("o",OneHotEncoder(handle_unknown="ignore"))]),cat)])
    cv=KFold(folds,shuffle=True,random_state=seed); rows=[]
    for name,d in DIMENZE.items():
        col="D_"+name
        if col not in panel: continue
        y=pd.to_numeric(panel[col],errors="coerce"); mask=y.notna()
        if mask.sum()<100: continue
        pipe=Pipeline([("x",tr),("m",Ridge(alpha=5.0))])
        r2=float(np.mean(cross_val_score(pipe,panel.loc[mask,xcols],y[mask],cv=cv,scoring="r2")))
        prov=d.get("prov") or {}; role=prov.get("zdroj_role") or d.get("role") or d.get("source_role") or "UNKNOWN"; conf=float(prov.get("jistota",d.get("jistota",d.get("confidence",.5))))
        grade="A" if role=="BRIDGE" else "B" if role=="SPECIALIST" else "C"
        rows.append({"dimension":name,"column":col,"evidence_grade":grade,"source_role":role,"confidence":conf,"demographic_oos_r2":r2,"residual_share_vs_demography":max(0.0,1-r2),"production_default":role!="OWN_ESTIMATE"})
    return pd.DataFrame(rows).sort_values(["evidence_grade","demographic_oos_r2"])
