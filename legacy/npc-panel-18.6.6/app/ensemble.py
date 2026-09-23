"""Ensemble uncertainty for client-facing NPC outputs.

The interval is across controlled simulation/model runs (seed + optional calibrated
probability temperature). It is deliberately NOT labelled a population confidence
interval.  The result keeps every component run auditable.
"""
from __future__ import annotations
from typing import Any, Callable
import numpy as np


def _scalar_from_question(q:dict[str,Any])->dict[str,float]:
    if isinstance(q.get("expected_pct"),dict): return {str(k):float(v) for k,v in q["expected_pct"].items()}
    if isinstance(q.get("celkem_pct"),dict): return {str(k):float(v) for k,v in q["celkem_pct"].items()}
    out={}
    for k in ("prumer","expected_mean","top2box_pct"):
        if q.get(k) is not None: out[k]=float(q[k])
    return out


def summarize_runs(runs:list[dict[str,Any]], *, qlo=.10, qhi=.90)->dict[str,Any]:
    if len(runs)<2: raise ValueError("Ensemble requires at least two runs")
    qids=sorted(set.intersection(*(set(r.get("vysledky",{})) for r in runs)))
    questions={}
    for qid in qids:
        vals={}
        for r in runs:
            for k,v in _scalar_from_question(r["vysledky"][qid]).items(): vals.setdefault(k,[]).append(v)
        questions[qid]={k:{"median":float(np.median(v)),"lo":float(np.quantile(v,qlo)),"hi":float(np.quantile(v,qhi)),"runs":len(v)} for k,v in vals.items() if len(v)==len(runs)}
    return {
        "kind":"simulation_ensemble_interval",
        "population_ci":False,
        "interval_quantiles":[qlo,qhi],
        "n_runs":len(runs),
        "seeds":[r.get("seed") for r in runs],
        "models":sorted(set(str(r.get("model")) for r in runs)),
        "temperatures":[(r.get("dispersion_config") or {}).get("temperature",1.0) for r in runs],
        "total_cost_usd":round(sum(float(r.get("naklady_usd") or 0) for r in runs),4),
        "total_duration_s":round(sum(float(r.get("trvani_s") or 0) for r in runs),1),
        "questions":questions,
        "note":"Interval captures controlled run-to-run simulation/model sensitivity, not uncertainty to the real population.",
    }


def run_ensemble(runner:Callable[...,dict[str,Any]], *, base_kwargs:dict[str,Any], runs:int=5,
                 seed:int=20260814, temperatures:list[float]|None=None, qlo=.10, qhi=.90)->tuple[dict[str,Any],list[dict[str,Any]]]:
    if runs<2: raise ValueError("runs must be >=2")
    temperatures=temperatures or [0.9,1.0,1.1,1.0,0.95]
    out=[]
    for i in range(runs):
        kw=dict(base_kwargs); kw["seed"]=seed+i*1009; kw["ulozit"]=False
        dc=dict(kw.get("dispersion_config") or {}); dc["temperature"]=float(temperatures[i%len(temperatures)]); kw["dispersion_config"]=dc
        out.append(runner(**kw))
    return summarize_runs(out,qlo=qlo,qhi=qhi),out
