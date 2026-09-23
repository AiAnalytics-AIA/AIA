"""Experimental survey-design diagnostics: order and framing sensitivity."""
from __future__ import annotations

from copy import deepcopy
from typing import Any
import numpy as np


def _dist(result: dict, qid: str) -> dict[str, float]:
    a = result["vysledky"][qid]
    return a.get("expected_pct") or a.get("celkem_pct") or {}


def _l1_pp(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return float(sum(abs(float(a.get(k,0))-float(b.get(k,0))) for k in keys))


def order_sensitivity(questions: list[dict[str, Any]], *, panel, n: int = 300,
                      model: str, mode: str = "dry", seed: int = 0,
                      workers: int = 8) -> dict[str, Any]:
    """Run same synthetic cases under original vs reversed independent-question order.

    Questions with routing filters are rejected because reversing them would change
    eligibility rather than isolate a pure order effect.
    """
    if any(q.get("filtr") for q in questions):
        raise ValueError("order_sensitivity requires questions without routing filters")
    from dotaznik import run_dotaznik
    q1 = deepcopy(questions); q2 = list(reversed(deepcopy(questions)))
    common = dict(n=n, panel=panel, model=model, mode=mode, seed=seed,
                  workers=workers, ulozit=False, tichy=True, response_mode="probability")
    a = run_dotaznik(q1, nazev="order_original", **common)
    b = run_dotaznik(q2, nazev="order_reversed", **common)
    rows=[]
    for q in questions:
        qid=q["id"]; da=_dist(a,qid); db=_dist(b,qid)
        rows.append({"question_id":qid,"l1_difference_pp":round(_l1_pp(da,db),3),
                     "original":da,"reversed":db})
    return {"n":n,"seed":seed,"mode":mode,"questions":rows,
            "max_l1_difference_pp":max((r["l1_difference_pp"] for r in rows),default=0),
            "note":"Order sensitivity experiment; not a human-ground-truth validation."}


def framing_sensitivity(result: dict, question_id: str) -> dict[str, Any]:
    tab = result.get("vysledky",{}).get(question_id,{}).get("podle_varianty",{})
    if len(tab) < 2:
        return {"question_id":question_id,"variants":tab,"max_pairwise_l1_pp":None}
    variants=list(tab)
    best=0.0
    for i in range(len(variants)):
        for j in range(i+1,len(variants)):
            ra, rb = tab[variants[i]], tab[variants[j]]
            # n-guarded variant cells remain hidden from client output, but the
            # randomized experiment may use internal-only distributions for a
            # model-sensitivity diagnostic.
            a = ra.get("_internal_pct") if ra.get("suppressed") else {k:v for k,v in ra.items() if k not in {"n","effective_n","intervaly_95","interval_95"} and not str(k).startswith("_")}
            b = rb.get("_internal_pct") if rb.get("suppressed") else {k:v for k,v in rb.items() if k not in {"n","effective_n","intervaly_95","interval_95"} and not str(k).startswith("_")}
            if isinstance(a, dict) and isinstance(b, dict):
                best=max(best,_l1_pp(a,b))
    return {"question_id":question_id,"variants":tab,"max_pairwise_l1_pp":round(best,3),
            "note":"Randomized synthetic framing split; interpret as model sensitivity until human-calibrated."}
