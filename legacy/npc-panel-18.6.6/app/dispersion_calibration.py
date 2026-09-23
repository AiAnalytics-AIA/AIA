"""Calibration of probability sharpness on SMOKE/calibration data only."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np


def temperature_scale(probs,temperature:float):
    p=np.asarray(probs,float); p=np.clip(p,1e-12,None); p/=p.sum(); t=max(float(temperature),.05)
    z=np.log(p)/t; z-=z.max(); q=np.exp(z); return q/q.sum()

def _loss(rows:list[dict[str,Any]],T:float)->float:
    losses=[]
    for r in rows:
        P=np.asarray(r["persona_probabilities"],float)
        if P.ndim==1:P=P[None,:]
        pred=np.mean(np.vstack([temperature_scale(x,T) for x in P]),axis=0)
        truth=np.asarray(r["truth"],float); truth=truth/truth.sum()
        losses.append(.5*np.abs(pred-truth).sum())
    return float(np.mean(losses)) if losses else float("inf")

def fit_temperature(rows:list[dict[str,Any]],*,dataset_role:str="smoke",grid=None)->dict[str,Any]:
    if dataset_role.lower() in {"holdout","blind_holdout","final_holdout"}:
        raise RuntimeError("Dispersion calibration se nesmí fitovat na finálním holdoutu.")
    grid=grid or np.linspace(.45,2.2,36)
    scored=[(float(_loss(rows,float(t))),float(t)) for t in grid]
    loss,T=min(scored)
    return {"temperature":T,"mean_tvd":loss,"dataset_role":dataset_role,"grid":scored}

def save_calibration(obj:dict,path:str|Path):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8");return p
