"""Cross-validated B4 calibration layer over raw category distributions.

Calibration is intentionally separate from respondent microdata.  It may be fitted
only on SMOKE/CALIBRATION benchmarks, never on a final holdout.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

@dataclass
class CategoryCalibrator:
    categories:list[str]
    bias:dict[str,float]
    domain:str="default"
    n_benchmarks:int=0
    cv_improvement:float|None=None

    def apply(self,pred:dict[str,float])->dict[str,float]:
        x=np.array([max(1e-9,float(pred.get(c,0))) for c in self.categories],float); x=x/x.sum()
        logits=np.log(x)+np.array([self.bias.get(c,0.0) for c in self.categories])
        logits-=logits.max(); p=np.exp(logits); p/=p.sum()
        return {c:float(v) for c,v in zip(self.categories,p)}

def _tvd(a,b,cats): return .5*sum(abs(float(a.get(c,0))-float(b.get(c,0))) for c in cats)

def fit_calibrator(rows:list[dict[str,Any]], *, dataset_role:str, min_benchmarks=8, domain="default")->CategoryCalibrator:
    if dataset_role.lower() in {"holdout","final_holdout","blind_holdout"}: raise ValueError("Calibration on final holdout is forbidden")
    if len(rows)<min_benchmarks: raise ValueError(f"Need at least {min_benchmarks} calibration benchmarks")
    cats=sorted(set().union(*(set(r["prediction"])|set(r["truth"]) for r in rows)))
    def learn(train):
        # Mean log-ratio residual with shrinkage; robust to zero cells.
        res=[]
        for r in train:
            p=np.array([max(1e-5,float(r["prediction"].get(c,0))) for c in cats]); t=np.array([max(1e-5,float(r["truth"].get(c,0))) for c in cats]); p/=p.sum();t/=t.sum(); res.append(np.log(t)-np.log(p))
        b=np.mean(res,axis=0); b-=b.mean(); b*=len(train)/(len(train)+5)
        return b
    raw=[];cal=[]
    for i in range(len(rows)):
        train=rows[:i]+rows[i+1:]; b=learn(train); r=rows[i]
        obj=CategoryCalibrator(cats,{c:float(v) for c,v in zip(cats,b)},domain,len(train))
        pp=obj.apply(r["prediction"]); raw.append(_tvd(r["prediction"],r["truth"],cats));cal.append(_tvd(pp,r["truth"],cats))
    imp=(np.mean(raw)-np.mean(cal))/np.mean(raw) if np.mean(raw)>0 else 0
    b=learn(rows)
    return CategoryCalibrator(cats,{c:float(v) for c,v in zip(cats,b)},domain,len(rows),float(imp))

def deployable(cal:CategoryCalibrator,min_cv_improvement=.03)->bool:
    return cal.cv_improvement is not None and cal.cv_improvement>=min_cv_improvement
