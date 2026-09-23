"""Repeatable published-margin validation tier.

SMOKE_VALIDATED is a development/iteration status only. It never unlocks or
replaces the one-shot human HOLDOUT_VALIDATED certificate.
"""
from __future__ import annotations
from typing import Any
import numpy as np

def evaluate_smoke(comparison:dict[str,Any], *, min_benchmarks=12, min_full_win_rate=.60,
                   min_improvement_vs_demo=.10, min_improvement_vs_generic=.10)->dict[str,Any]:
    req=["B1","B2","B3"]
    if any(v not in comparison for v in req): return {"status":"SMOKE_FAIL","reason":"missing required variants B1/B2/B3"}
    rows={v:{x["benchmark"]:x["tvd"] for x in comparison[v].get("rows",[])} for v in req}
    ids=sorted(set.intersection(*(set(rows[v]) for v in req)))
    if len(ids)<min_benchmarks: return {"status":"SMOKE_FAIL","reason":f"need >= {min_benchmarks} common benchmarks","n":len(ids)}
    m={v:float(np.mean([rows[v][i] for i in ids])) for v in req}; full=m["B3"]
    imp_demo=(m["B2"]-full)/m["B2"] if m["B2"] else 0
    imp_gen=(m["B1"]-full)/m["B1"] if m["B1"] else 0
    wins=float(np.mean([rows["B3"][i]<rows["B2"][i] for i in ids]))
    ok=imp_demo>=min_improvement_vs_demo and imp_gen>=min_improvement_vs_generic and wins>=min_full_win_rate
    return {"status":"SMOKE_VALIDATED" if ok else "SMOKE_FAIL","n":len(ids),"mean_tvd":m,"improvement_vs_B2":imp_demo,"improvement_vs_B1":imp_gen,"win_rate_vs_B2":wins,
            "note":"Repeatable published-margin development validation; does not replace final blind human holdout."}
