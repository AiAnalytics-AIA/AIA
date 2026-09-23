"""AI-assisted reverse audience discovery.

AI chooses a defensible success outcome from the *actual questionnaire/results*.
Code validates that choice, learns propensity on the existing panel, and constructs
three deterministic targeting strategies with explicit size/lift/ESS trade-offs.
"""
from __future__ import annotations

import json, math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from ai_router import call_structured
from segment import discover_audience_on_panel, effective_sample_size, profile_segment
from product_policy import policy_value


def _weights(df: pd.DataFrame) -> np.ndarray:
    if "vaha_kalibrovana" in df:
        w=pd.to_numeric(df["vaha_kalibrovana"],errors="coerce").fillna(0).to_numpy(float)
    else: w=np.ones(len(df),dtype=float)
    return np.where(np.isfinite(w)&(w>0),w,0.0)


def _weighted_mean(x,w):
    x=np.asarray(x,float); w=np.asarray(w,float); ok=np.isfinite(x)&np.isfinite(w)&(w>0)
    return float(np.dot(x[ok],w[ok])/w[ok].sum()) if ok.any() and w[ok].sum()>0 else float("nan")


def _question_catalog(project: dict, detail: pd.DataFrame) -> list[dict[str,Any]]:
    meta={}
    for s in project.get("sections") or []:
        if s.get("type")!="questions": continue
        for q in s.get("questions") or []: meta[str(q.get("id"))]=q
    out=[]
    for qid,q in meta.items():
        if qid not in detail.columns or str(q.get("typ")) in {"text","otevrena"}: continue
        s=detail[qid].dropna().astype(str)
        if len(s)<20: continue
        vc=s.value_counts(); n=float(vc.sum())
        vals=[{"value":str(k),"pct":round(100*float(v)/n,1)} for k,v in vc.head(15).items()]
        if len(vals)<2 or len(vc)>30: continue
        out.append({"id":qid,"text":str(q.get("text") or qid),"type":q.get("typ"),"answers":vals})
    return out


def choose_outcome(project: dict, detail: pd.DataFrame, *, model: str="sonnet") -> dict[str,Any]:
    cat=_question_catalog(project,detail)
    if not cat: raise ValueError("Ve výsledcích není vhodná uzavřená outcome otázka pro hledání cílovky.")
    briefing=project.get("briefing") or {}; aud=project.get("audience") or {}
    context={"product":aud.get("product_description") or briefing.get("product_description") or "",
             "success_definition":aud.get("success_definition") or "",
             "decision_use":project.get("decision_use") or "",
             "research_goal":project.get("research_goal") or "",
             "available_outcomes":cat}
    schema={"type":"object","properties":{
        "question_id":{"type":"string"},"positive_answers":{"type":"array","items":{"type":"string"}},
        "success_interpretation":{"type":"string"},"reason":{"type":"string"},
        "confidence":{"type":"number"},
        "business_priority":{"type":"string","enum":["precision","balanced","scale"]},
        "warning":{"type":"string"}},
        "required":["question_id","positive_answers","success_interpretation","reason","confidence","business_priority","warning"]}
    system=("Jsi senior research strategist. Máš najít nejlepší cílovou skupinu pro navazující výzkum. "
            "Neinventuj nový outcome ani odpovědi. Vyber VÝHRADNĚ jednu otázku a odpovědi z available_outcomes. "
            "Outcome musí co nejlépe operacionalizovat obchodní/výzkumný úspěch, ne demografický stereotyp. "
            "business_priority=precision když je důležitější vysoká koncentrace úspěchu; scale když zásah; balanced jinak. "
            "Pokud je definice úspěchu nejasná, vyber nejbližší měřený outcome a napiš warning.")
    from provider_auth import get_ai_provider, normalize_ai_provider
    provider=normalize_ai_provider(((project.get("run_policy") or {}).get("provider") if isinstance(project,dict) else None) or get_ai_provider())
    rr=call_structured(system=system,messages=[{"role":"user","content":json.dumps(context,ensure_ascii=False)}],
                       schema=schema,schema_name="audience_outcome_strategy",anthropic_model=model,max_tokens=1300,prefer=provider,allow_fallback=False)
    x=dict(rr["data"]); by={q["id"]:q for q in cat}; q=by.get(str(x.get("question_id")))
    if not q: raise ValueError("AI vybrala outcome, který není ve skutečných výsledcích.")
    allowed={a["value"] for a in q["answers"]}; pos=[str(v) for v in x.get("positive_answers") or [] if str(v) in allowed]
    if not pos: raise ValueError("AI nevybrala žádnou platnou pozitivní odpověď.")
    x["positive_answers"]=pos; x["question_text"]=q["text"]
    x["_ai"]={"provider":rr.get("provider"),"model":rr.get("model"),"fallback_used":rr.get("fallback_used",False)}
    return x


def _opportunity_threshold(score: np.ndarray, w: np.ndarray, capture: float) -> float:
    """Smallest top-propensity audience that captures a target share of predicted successes.

    This adapts the audience size to how concentrated the opportunity actually is instead
    of hard-coding a population percentage.
    """
    order=np.argsort(-score); sw=w[order]; ss=score[order]
    mass=np.maximum(ss,0.0)*np.maximum(sw,0.0); total=mass.sum()
    if total<=0: return float(np.nanmedian(score))
    cum=np.cumsum(mass)/total; i=int(np.searchsorted(cum,capture,side="left")); i=min(max(i,0),len(ss)-1)
    return float(ss[i])


def _candidate(panel: pd.DataFrame, prop: pd.Series, capture: float, key: str, name: str) -> dict[str,Any]:
    p=pd.to_numeric(prop.reindex(panel.index),errors="coerce").fillna(0).clip(0,1).to_numpy(float); w=_weights(panel)
    thr=_opportunity_threshold(p,w,capture); mask=(p>=thr).astype(float); sw=w*mask
    actual=float(sw.sum()/w.sum()) if w.sum()>0 else 0.0
    rate=_weighted_mean(p,sw); base=_weighted_mean(p,w); lift=rate/base if base>0 else float("nan")
    total_opp=float(np.dot(p,w)); captured=float(np.dot(p,sw)); actual_capture=captured/total_opp if total_opp>0 else 0.0
    ess=effective_sample_size(sw)
    profile=profile_segment(panel,pd.Series(mask,index=panel.index),top_n=10)
    return {"key":key,"name":name,"target_opportunity_capture_pct":round(100*capture,1),
            "opportunity_capture_pct":round(100*actual_capture,1),"population_share_pct":round(100*actual,1),
            "propensity_threshold":round(thr,5),"expected_success_pct":round(100*rate,1) if np.isfinite(rate) else None,
            "population_success_pct":round(100*base,1) if np.isfinite(base) else None,
            "lift":round(float(lift),2) if np.isfinite(lift) else None,"ess_population":round(float(ess),1),
            "profile":profile,"membership":mask}


def discover_smart_audience(panel: pd.DataFrame, detail: pd.DataFrame, project: dict, *, model: str="sonnet",
                            seed: int=42, min_positive: int=20) -> dict[str,Any]:
    choice=choose_outcome(project,detail,model=model)
    prop,meta=discover_audience_on_panel(panel,detail,choice["question_id"],choice["positive_answers"],
                                         min_positive=min_positive,seed=seed)
    candidates=[_candidate(panel,prop,.25,"core","Jádro s nejvyšším sklonem k úspěchu"),
                _candidate(panel,prop,.55,"balanced","Nejlepší poměr potenciál / velikost"),
                _candidate(panel,prop,.80,"scale","Širší růstová skupina")]
    pref={"precision":"core","balanced":"balanced","scale":"scale"}.get(choice.get("business_priority"),"balanced")
    # Guard against tiny effective populations; move recommendation outward if necessary.
    ess_recommended=float(policy_value("audience", "ess_recommended_min", default=150) or 150)
    valid=[c for c in candidates if float(c.get("ess_population") or 0)>=ess_recommended]
    recommended=next((c["key"] for c in valid if c["key"]==pref),None) or (valid[0]["key"] if valid else "scale")
    for c in candidates:
        c["recommended"]=c["key"]==recommended
        c.pop("membership",None)
    return {"outcome":choice,"model":meta,"candidates":candidates,"recommended_key":recommended,
            "confidence_class":meta.get("confidence_class") or "C",
            "epistemic_status":meta.get("epistemic_status","synthetic_outcome_discovery"),
            "note":"AI volí měřený outcome; členství cílovky pak počítá deterministický propensity model. Bez human outcome kotvy jde o explorativní Class C."}


def persist_candidates(panel: pd.DataFrame, detail: pd.DataFrame, project: dict, out_dir: str|Path, *, model: str="sonnet",
                       seed: int=42,min_positive:int=20) -> dict[str,Any]:
    out=discover_smart_audience(panel,detail,project,model=model,seed=seed,min_positive=min_positive)
    # Refit once to materialize membership scores; exact same deterministic seed/outcome.
    prop,meta=discover_audience_on_panel(panel,detail,out["outcome"]["question_id"],out["outcome"]["positive_answers"],
                                         min_positive=min_positive,seed=seed)
    d=Path(out_dir); d.mkdir(parents=True,exist_ok=True); w=_weights(panel); p=prop.to_numpy(float)
    for c in out["candidates"]:
        thr=float(c["propensity_threshold"]); membership=(p>=thr).astype(float)
        fp=d/f"audience_{c['key']}.csv"; df=pd.DataFrame({"propensity":membership})
        if "panel_row_id" in panel.columns: df.insert(0,"panel_row_id",panel["panel_row_id"].astype(str).to_numpy())
        else: df.insert(0,"panel_index",panel.index.to_numpy())
        df.to_csv(fp,index=False); c["propensity_file"]=str(fp)
        c["segment_config"]={"mode":"propensity_file","name":c["name"],"propensity_file":str(fp),
                             "metadata_file":str(d/"strategy.json")}
    (d/"strategy.json").write_text(json.dumps({k:v for k,v in out.items() if k!="model"},ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    return out
