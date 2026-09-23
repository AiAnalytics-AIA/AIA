"""Controlled persona ablation for NPC Panel.

This experiment measures WHETHER persona conditioning changes model responses. It
explicitly does not claim that the changed answers are more accurate; that requires
the later external holdout benchmark.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import math
import numpy as np

from research_project import compile_project
from runtime_config import resolve_model, resolve_provider_model

ARMS=("none","demographics","full")


def _dist(v: dict, qid: str) -> dict[str,float]:
    a=(v.get("vysledky") or {}).get(qid) or {}
    d=a.get("celkem_pct") or {}
    return {str(k):float(x) for k,x in d.items() if isinstance(x,(int,float))}


def _tvd(a:dict[str,float],b:dict[str,float])->float|None:
    keys=set(a)|set(b)
    if not keys:return None
    return round(.5*sum(abs(a.get(k,0)-b.get(k,0)) for k in keys),3)  # percentage points mass / 2


def _switch_rate(va:dict,vb:dict,qid:str)->float|None:
    da=va.get("detail"); db=vb.get("detail")
    if da is None or db is None or qid not in da or qid not in db:return None
    aa=da[["_zdroj_index",qid]].copy(); bb=db[["_zdroj_index",qid]].copy()
    m=aa.merge(bb,on="_zdroj_index",suffixes=("_a","_b"))
    m=m[m[f"{qid}_a"].notna() & m[f"{qid}_b"].notna()]
    if not len(m):return None
    return round(100*float((m[f"{qid}_a"].astype(str)!=m[f"{qid}_b"].astype(str)).mean()),2)


def _comparison(va:dict,vb:dict,label_a:str,label_b:str)->dict[str,Any]:
    out=[]
    qs={q["id"]:q for q in va.get("otazky") or []}
    for qid,q in qs.items():
        aa=(va.get("vysledky") or {}).get(qid) or {}; bb=(vb.get("vysledky") or {}).get(qid) or {}
        if aa.get("typ") in {"vyber","multi"}:
            effect=_tvd(_dist(va,qid),_dist(vb,qid)); metric="TVD_pp"
        elif aa.get("typ")=="skala" and aa.get("prumer") is not None and bb.get("prumer") is not None:
            effect=round(abs(float(aa["prumer"])-float(bb["prumer"])),3); metric="mean_abs_diff"
        else:
            effect=None; metric="not_scored"
        out.append({"question_id":qid,"text":q.get("text",""),"metric":metric,"effect":effect,
                    "individual_switch_pct":_switch_rate(va,vb,qid),
                    "factual": any((va.get("detail") is not None and f"_provider_{qid}" in va["detail"] and
                                    str(x)=="deterministic_fact") for x in (va["detail"][f"_provider_{qid}"].dropna().unique() if va.get("detail") is not None and f"_provider_{qid}" in va["detail"] else []))})
    scored=[x["effect"] for x in out if x["effect"] is not None and not x["factual"]]
    return {"a":label_a,"b":label_b,"questions":out,
            "median_effect":round(float(np.median(scored)),3) if scored else None,
            "max_effect":round(float(max(scored)),3) if scored else None}


def run_persona_ablation(project:dict[str,Any], *, mode:str="sync", confirm_live:bool=False,
                          arms:list[str]|None=None, root:Path|None=None)->dict[str,Any]:
    c=compile_project(project); p=c["project"]; base=c["brief"]
    from provider_auth import normalize_ai_provider, probe_anthropic, probe_openai, provider_key_ready
    provider=normalize_ai_provider((p.get("run_policy") or {}).get("provider"))
    base["model"]=resolve_provider_model(provider,base.get("model"))
    if mode=="dry":
        status="INVALID_DRY_ABLATION"
    else:
        status="EFFECT_TEST_ONLY_NOT_ACCURACY"
        if not confirm_live: raise ValueError("Live ablation requires confirm_live=true")
        if provider=="claude_code_subscription":
            from claude_code_provider import health
            probe=health()
        else:
            probe=probe_openai(base.get("model")) if provider=="openai" else probe_anthropic(base.get("model"))
        if not provider_key_ready(provider) or not probe.get("ok"):
            raise RuntimeError("STRICT_LIVE_PROVIDER_FAILED: "+str(probe.get("message") or probe))
    selected=[x for x in (arms or list(ARMS)) if x in ARMS]
    if len(selected)<2: raise ValueError("Ablation needs at least two persona arms")
    total_cap=(p.get("budget") or {}).get("max_usd")
    remaining=float(total_cap) if total_cap is not None else None
    from prototype_server import load_panel_cached, PANEL_PATH
    from pipeline import Panel
    from dotaznik import run_dotaznik
    panel=Panel(load_panel_cached().copy())
    runs={}; total_spent=0.0
    for arm in selected:
        if remaining is not None and remaining<=0: raise RuntimeError("ABLATION_BUDGET_EXHAUSTED before all arms completed")
        v=run_dotaznik(base["otazky"],n=int(base.get("n",120)),filtry=base.get("filtry") or None,
            nazev=f"{base.get('nazev','study')}__ablation_{arm}",panel=panel,panel_path=PANEL_PATH,
            model=base.get("model"),mode=mode,seed=base.get("seed",42),workers=int(base.get("workers",8)),
            persona_mode=arm,response_mode=base.get("response_mode","probability"),allow_own_estimates=False,
            selection_weights=None,segment_meta=base.get("segment") or {},tichy=True,
            provider_policy=("strict_"+provider) if mode!="dry" else "fallback",budget_max_usd=remaining)
        if v.get("run_status")=="PARTIAL_BUDGET_CAP":
            raise RuntimeError(f"ABLATION_BUDGET_EXHAUSTED in arm {arm}; comparison would be unbalanced")
        spent=float(v.get("naklady_usd") or 0); total_spent+=spent
        if remaining is not None: remaining=max(0.0,remaining-spent)
        runs[arm]=v
    comps=[]
    for a,b in (("none","demographics"),("demographics","full"),("none","full")):
        if a in runs and b in runs: comps.append(_comparison(runs[a],runs[b],a,b))
    public_runs={k:{x:v.get(x) for x in ("run_id","run_status","n_dotazano","naklady_usd","prompt_template_sha256","sample_id_sha256","persona_mode","factual_layer")} for k,v in runs.items()}
    same_sample=len({v.get("sample_id_sha256") for v in runs.values()})==1
    same_prompt=len({v.get("prompt_template_sha256") for v in runs.values()})==1
    return {"status":status,"interpretation":"Ablace měří kauzální citlivost odpovědí na persona conditioning, nikoli shodu s realitou.",
            "arms":selected,"runs":public_runs,"comparisons":comps,"same_sample":same_sample,"same_prompt_template":same_prompt,
            "total_spent_usd":round(total_spent,4),"budget_max_usd":total_cap,"provider":provider,
            "valid_design":bool(same_sample and same_prompt)}
