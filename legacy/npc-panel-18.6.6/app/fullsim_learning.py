"""Learning/validation layer for NPC Full Simulation 10.15.

Everything in this module is benchmark-driven.  It may *use* synthetic priors,
but it never upgrades them to evidence.  Human calibration samples are frozen
before the holdout truth, meta-error models train only on earlier blind runs,
and relationship provenance remains explicit.
"""
from __future__ import annotations

import hashlib, json, math, time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha_json(obj: Any) -> str:
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def _clip(x: float, lo: float, hi: float) -> float:
    return float(max(lo,min(hi,x)))


def _norm_pct(d: dict[str, Any], cats: list[str]) -> np.ndarray:
    x=np.array([max(0.0,float(d.get(c,0.0))) for c in cats],float)
    return x/x.sum() if x.sum()>0 else np.ones(len(cats))/max(1,len(cats))


# ------------------------------------------------------------------
# 1. Human mini-sample rectification


def calibration_counts(calibration: dict[str, Any], qid: str, cats: list[str], *, size: int|None=None, seed: int=0) -> tuple[np.ndarray,int]:
    """Return weighted human counts. Supports respondent rows or aggregate counts.

    Respondent rows are the preferred format because the same frozen sample can
    later support joint diagnostics.  If size is requested, a deterministic
    pre-truth subsample is drawn without replacement.
    """
    qs=(calibration.get("questions") or {}).get(qid, {})
    if isinstance(qs,dict) and qs.get("counts"):
        arr=np.array([max(0.0,float(qs["counts"].get(c,0.0))) for c in cats],float)
        n=int(round(arr.sum()))
        return arr,n
    rows=list(calibration.get("rows") or [])
    if not rows:
        return np.zeros(len(cats),float),0
    rng=np.random.default_rng(int(seed)+int(hashlib.sha256(qid.encode()).hexdigest()[:8],16))
    if size is not None and len(rows)>size:
        ix=rng.choice(len(rows),size=int(size),replace=False)
        rows=[rows[int(i)] for i in ix]
    weight_col=str(calibration.get("weight_column") or "weight")
    counts={c:0.0 for c in cats}; n=0
    for r in rows:
        val=r.get(qid)
        if val is None: continue
        sval=str(val)
        if sval not in counts: continue
        try: w=float(r.get(weight_col,1.0) or 1.0)
        except Exception: w=1.0
        if not np.isfinite(w) or w<=0: continue
        counts[sval]+=w; n+=1
    # rescale weights to respondent count so prior ESS remains interpretable.
    a=np.array([counts[c] for c in cats],float)
    if a.sum()>0 and n>0: a*=n/a.sum()
    return a,n


def _dirichlet_interval(alpha: np.ndarray, seed: int, draws: int=4000) -> tuple[np.ndarray,np.ndarray]:
    rng=np.random.default_rng(seed)
    sims=rng.dirichlet(np.clip(alpha,1e-5,None),size=draws)
    return np.quantile(sims,.025,axis=0),np.quantile(sims,.975,axis=0)


def rectify_prediction(base: dict[str,Any], calibration: dict[str,Any], *, human_n: int|None=None,
                       prior_ess: float=75.0, seed: int=0, label: str|None=None) -> dict[str,Any]:
    """Bayesian shrinkage: synthetic forecast is an explicit Dirichlet prior.

    This is deliberately not sold as a magically enlarged human sample.  The
    prior ESS is auditable and should eventually be learned from blind history.
    """
    out={"kind":"npc_rectified_prediction_v1","questions":{},"human_n_requested":human_n,
         "prior_ess":round(float(prior_ess),3),"calibration_sha256":sha_json(calibration)}
    used=[]
    for qid,q in (base.get("questions") or {}).items():
        cats=list(q.get("categories") or q.get("estimate_pct",{}).keys())
        if not cats: continue
        syn=_norm_pct(q.get("estimate_pct") or {},cats)
        cnt,n=calibration_counts(calibration,qid,cats,size=human_n,seed=seed)
        if n<=0: continue
        alpha=np.clip(syn*float(prior_ess)+cnt,1e-5,None)
        post=alpha/alpha.sum(); lo,hi=_dirichlet_interval(alpha,seed+len(used)*1009)
        out["questions"][qid]={"text":q.get("text"),"categories":cats,
            "estimate_pct":{c:round(float(post[i]*100),3) for i,c in enumerate(cats)},
            "interval_95":{c:{"low":round(float(lo[i]*100),3),"high":round(float(hi[i]*100),3)} for i,c in enumerate(cats)},
            "human_n":n,"synthetic_prior_ess":round(float(prior_ess),3)}
        used.append(n)
    out["human_n_realized"]=min(used) if used else 0
    out["label"]=label or (f"FULLSIM_PLUS_{human_n}" if human_n else "FULLSIM_RECTIFIED")
    out["epistemic_note"]="Human mini-sample updates an explicit synthetic prior; it is not counted as a larger human sample. Holdout truth must be separate."
    out["sha256"]=sha_json(out)
    return out


def rectification_curve(base: dict[str,Any], calibration: dict[str,Any], *, sizes: Iterable[int]=(25,50,100,250),
                        prior_ess: float=75.0, seed: int=0) -> dict[str,dict[str,Any]]:
    out={}
    available=len(calibration.get("rows") or [])
    for n in sizes:
        if available and available<int(n): continue
        pred=rectify_prediction(base,calibration,human_n=int(n),prior_ess=prior_ess,seed=seed,label=f"FULLSIM_PLUS_{int(n)}")
        if pred.get("questions"): out[pred["label"]]=pred
    return out


def register_human_calibration(run_id: str, calibration: dict[str,Any], *, run_root: Path, bench_root: Path,
                               sizes=(25,50,100,250), seed: int=0, prior_ess: float|None=None) -> dict[str,Any]:
    rd=run_root/run_id; bd=bench_root/run_id; bd.mkdir(parents=True,exist_ok=True)
    if (bd/"truth.json").exists(): raise RuntimeError("Human calibration must be frozen before holdout truth.")
    pred=json.loads((rd/"prediction.json").read_text(encoding="utf-8"))
    base=(pred.get("methods") or {}).get("FULL_SIMULATION")
    if not base: raise ValueError("FULL_SIMULATION prediction missing")
    # Prior ESS may only depend on pre-existing history. Caller can override.
    ess=float(prior_ess if prior_ess is not None else 75.0)
    curve=rectification_curve(base,calibration,sizes=sizes,prior_ess=ess,seed=seed)
    available_n=len(calibration.get("rows") or [])
    if not available_n:
        available_n=max([int(p.get("human_n_realized",0) or 0) for p in curve.values()] or [0])
    stability=calibration_stability(curve)
    obj={"kind":"npc_human_calibration_freeze_v2","run_id":run_id,"created_at":now(),
         "source":calibration.get("source",""),"sample_id":calibration.get("sample_id",""),
         "calibration_sha256":sha_json(calibration),"methods":list(curve),"prior_ess":ess,
         "available_human_n":available_n,"stability":stability}
    obj["sha256"]=sha_json(obj)
    (bd/"human_calibration_manifest.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    (bd/"human_calibration.json").write_text(json.dumps(calibration,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    (bd/"human_calibration_stability.json").write_text(json.dumps(stability,ensure_ascii=False,indent=2),encoding="utf-8")
    sd=bd/"submissions"; sd.mkdir(exist_ok=True)
    for method,p in curve.items():
        sub={"kind":"external_prediction_v1","run_id":run_id,"method":method,"submitted_at":now(),
             "status":"PRE_TRUTH_ELIGIBLE","prediction":p,"metadata":{"source":"human_rectification","calibration_manifest_sha256":obj["sha256"]}}
        sub["sha256"]=sha_json(sub)
        (sd/f"{method.lower()}.json").write_text(json.dumps(sub,ensure_ascii=False,indent=2),encoding="utf-8")

    # Respondent-level calibration can diagnose joint structure and demographic
    # inflation. These are diagnostics only; the holdout truth remains separate.
    joint=None; demo_inflation=None
    sp=rd/"synthetic_response_sample.csv.gz"
    rows=calibration.get("rows") or []
    if sp.exists() and rows:
        try:
            syn=pd.read_csv(sp); hum=pd.DataFrame(rows)
            qids=sorted(set((base.get("questions") or {})) & set(syn.columns) & set(hum.columns))
            if len(qids)>=2:
                joint=joint_structure_score(syn,hum,qids)
                (bd/"joint_calibration_diagnostic.json").write_text(json.dumps(joint,ensure_ascii=False,indent=2),encoding="utf-8")
            if qids:
                demo_inflation=demographic_inflation_score(syn,hum,qids)
                (bd/"demographic_inflation_diagnostic.json").write_text(json.dumps(demo_inflation,ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception:
            joint=None; demo_inflation=None

    meta_error={}; robustness={}; lp={}; wm={}
    for name,var in (("meta_error.json","meta_error"),("robustness.json","robustness"),("learning_profile.json","lp"),("world_model.json","wm")):
        fp=rd/name
        if fp.exists():
            try:
                val=json.loads(fp.read_text(encoding="utf-8"))
                if var=="meta_error": meta_error=val
                elif var=="robustness": robustness=val
                elif var=="lp": lp=val
                else: wm=val
            except Exception: pass
    router=decision_router(meta_error=meta_error,robustness=robustness,stereotype=stereotype_adversary(wm) if wm else None,
                           learning_profile=lp,benchmark_eligible=True,human_calibration_n=available_n)
    router["calibration_stability"]=stability
    if joint is not None: router["joint_calibration_diagnostic"]={k:v for k,v in joint.items() if k!="pairs"}
    if demo_inflation is not None: router["demographic_inflation"]={k:v for k,v in demo_inflation.items() if k!="pairs"}
    (bd/"decision_router_with_humans.json").write_text(json.dumps(router,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"manifest":obj,"predictions":curve,"stability":stability,"decision_router":router,
            "joint_diagnostic":joint,"demographic_inflation":demo_inflation}


# ------------------------------------------------------------------
# 2. Meta-error model: forecast the forecast error before truth

FEATURES=("world_sd","interval_width","method_disagreement","prompt_sensitivity","research_strength","world_confidence","n_categories","question_length")


def prediction_features(*, qid: str, q: dict[str,Any], prediction: dict[str,Any], diagnostics: dict[str,Any]|None=None,
                        research_summary: dict[str,Any]|None=None, world_model: dict[str,Any]|None=None) -> dict[str,float]:
    diagnostics=diagnostics or {}; fs=(prediction.get("methods") or {}).get("FULL_SIMULATION",{})
    fq=(fs.get("questions") or {}).get(qid,{})
    wsd=list((fq.get("between_world_sd_pp") or {}).values())
    widths=[float(v["high"])-float(v["low"]) for v in (fq.get("interval_95") or {}).values() if isinstance(v,dict) and "low" in v]
    conf=[float(f.get("confidence",0)) for f in (world_model or {}).get("factors",[])]
    return {
        "world_sd":float(np.mean(wsd)) if wsd else 0.0,
        "interval_width":float(np.mean(widths)) if widths else 0.0,
        "method_disagreement":float((diagnostics.get("model_disagreement_pp") or {}).get(qid,0.0)),
        "prompt_sensitivity":float((diagnostics.get("prompt_sensitivity_pp") or {}).get(qid,0.0)),
        "research_strength":float((research_summary or {}).get("accepted",0))/max(1,float((research_summary or {}).get("accepted",0)+(research_summary or {}).get("target_overlap_available",0))),
        "world_confidence":float(np.mean(conf)) if conf else 0.0,
        "n_categories":float(len(q.get("kategorie") or q.get("categories") or fq.get("categories") or [])),
        "question_length":float(len(str(q.get("text") or fq.get("text") or "")))/100.0,
    }


def _history_meta_rows(run_root: Path, bench_root: Path, domain: str) -> list[dict[str,Any]]:
    rows=[]
    if not bench_root.exists(): return rows
    for bd in bench_root.iterdir():
        if not bd.is_dir() or not (bd/"truth.json").exists() or not (bd/"scores.json").exists(): continue
        try:
            truth=json.loads((bd/"truth.json").read_text(encoding="utf-8")); scores=json.loads((bd/"scores.json").read_text(encoding="utf-8"))
            if truth.get("benchmark_eligibility")!="BLIND_ELIGIBLE": continue
            if str(truth.get("domain","general")) not in {str(domain),"general"}: continue
            fp=bd/"meta_features.json"
            if not fp.exists(): continue
            feats=json.loads(fp.read_text(encoding="utf-8"))
            sq=(scores.get("methods") or {}).get("FULL_SIMULATION",{}).get("questions",[])
            byq={x.get("question_id"):x for x in sq}
            for qid,f in (feats.get("questions") or {}).items():
                if qid in byq: rows.append({"run_id":bd.name,"qid":qid,"x":[float(f.get(k,0)) for k in FEATURES],"y":float(byq[qid]["mae_pp"])})
        except Exception: continue
    return rows


def meta_error_forecast(feature_map: dict[str,dict[str,float]], *, run_root: Path, bench_root: Path, domain: str="general") -> dict[str,Any]:
    hist=_history_meta_rows(run_root,bench_root,domain)
    X=np.array([r["x"] for r in hist],float) if hist else np.empty((0,len(FEATURES)))
    y=np.array([r["y"] for r in hist],float) if hist else np.empty(0)
    method="HEURISTIC_NO_HISTORY"; coef=None; resid_sd=4.0
    if len(hist)>=8:
        mu=X.mean(0); sd=X.std(0); sd[sd<1e-6]=1
        Z=(X-mu)/sd; lam=3.0
        beta=np.linalg.solve(Z.T@Z+lam*np.eye(Z.shape[1]),Z.T@(y-y.mean()))
        pred_hist=y.mean()+Z@beta; resid_sd=max(1.5,float(np.sqrt(np.mean((y-pred_hist)**2))))
        method="RIDGE_PRIOR_BLIND_HISTORY"; coef=(mu,sd,beta,float(y.mean()))
    base=float(np.mean(y)) if len(y) else 6.0
    out={"kind":"npc_meta_error_forecast_v1","domain":domain,"history_n":len(hist),"method":method,"questions":{}}
    for qid,f in feature_map.items():
        x=np.array([float(f.get(k,0)) for k in FEATURES],float)
        if coef:
            mu,sd,beta,ybar=coef; est=float(ybar+((x-mu)/sd)@beta)
        else:
            est=base + .35*x[0]+.05*max(0,x[1]-10)+.22*x[2]+.25*x[3]-.8*x[4]-.8*x[5]
        est=_clip(est,1.0,30.0)
        z=(10.0-est)/max(1.0,resid_sd); pgt=1/(1+math.exp(_clip(z,-20,20)))
        out["questions"][qid]={"expected_mae_pp":round(est,3),"p_error_gt_10pp":round(float(pgt),4),"features":{k:round(float(f.get(k,0)),4) for k in FEATURES}}
    out["residual_sd_pp"]=round(resid_sd,3); out["sha256"]=sha_json(out); return out


# ------------------------------------------------------------------
# 3-4. Robustness diagnostics and multi-model/prompt disagreement


def compare_prediction_methods(methods: dict[str,dict[str,Any]], *, primary_prefix: str="FULLSIM_DIAG") -> dict[str,Any]:
    selected={k:v for k,v in methods.items() if k.startswith(primary_prefix)}
    qids=sorted({q for m in selected.values() for q in (m.get("questions") or {})})
    model_dis={}; prompt_sens={}; noise_sens={}; rank_flips={}
    for qid in qids:
        rows=[]
        for name,m in selected.items():
            q=(m.get("questions") or {}).get(qid)
            if q: rows.append((name,q))
        cats=sorted({c for _,q in rows for c in (q.get("estimate_pct") or {})})
        if not rows or not cats: continue
        arr=np.array([[float(q.get("estimate_pct",{}).get(c,0)) for c in cats] for _,q in rows])
        model_dis[qid]=round(float(np.mean(np.ptp(arr,axis=0))),3)
        # Group spreads by prompt/noise components encoded in method name.
        psp=[]; nsp=[]; tops=[]
        byp={}; byn={}
        for (name,q),vec in zip(rows,arr):
            parts=name.split("__")
            model=parts[1] if len(parts)>1 else ""; prompt=parts[2] if len(parts)>2 else ""; noise=parts[3] if len(parts)>3 else ""
            byp.setdefault(prompt,[]).append(vec); byn.setdefault(noise,[]).append(vec); tops.append(cats[int(np.argmax(vec))])
        if len(byp)>1:
            means=np.array([np.mean(v,axis=0) for v in byp.values()]); psp=list(np.ptp(means,axis=0))
        if len(byn)>1:
            means=np.array([np.mean(v,axis=0) for v in byn.values()]); nsp=list(np.ptp(means,axis=0))
        prompt_sens[qid]=round(float(np.mean(psp)) if psp else 0.0,3)
        noise_sens[qid]=round(float(np.mean(nsp)) if nsp else 0.0,3)
        rank_flips[qid]=len(set(tops))>1
    return {"kind":"npc_fullsim_robustness_v1","model_disagreement_pp":model_dis,"prompt_sensitivity_pp":prompt_sens,
            "response_noise_sensitivity_pp":noise_sens,"top_category_rank_flip":rank_flips,
            "fragile_questions":[q for q in qids if prompt_sens.get(q,0)>8 or model_dis.get(q,0)>10 or rank_flips.get(q)],
            "sha256":sha_json({"model_disagreement_pp":model_dis,"prompt_sensitivity_pp":prompt_sens,"noise":noise_sens,"flips":rank_flips})}


# ------------------------------------------------------------------
# 5-6. Relationship provenance + posterior store

DEMO_FIELDS={"vek","pohlavi","vzdelani","kraj","velikost_obce","prijem_cisty_mesicni"}


def annotate_relationship_provenance(world_model: dict[str,Any], learned: dict[str,Any]|None=None) -> dict[str,Any]:
    learned=learned or {}; lm=learned.get("relationships") or {}
    counts={"OBSERVED_JOINT":0,"LEARNED_JOINT":0,"HYPOTHESIZED_JOINT":0,"CONTESTED_JOINT":0}
    for f in world_model.get("factors",[]):
        fconf=float(f.get("confidence",.3) or .3)
        for d in f.get("drivers",[]):
            key=f"{f.get('id')}::{d.get('field')}"
            explicit=str(d.get("provenance") or "").upper()
            if explicit=="OBSERVED_JOINT" and d.get("joint_source"):
                p="OBSERVED_JOINT"
            elif key in lm and int(lm[key].get("n_human_benchmarks",0))>=3:
                p="LEARNED_JOINT"; d["learned_effect"]=lm[key].get("effect")
            elif explicit=="CONTESTED_JOINT" or (fconf<.35 and abs(float(d.get("effect",0)))>=.18):
                p="CONTESTED_JOINT"
            else: p="HYPOTHESIZED_JOINT"
            d["provenance"]=p; counts[p]+=1
    for c in world_model.get("factor_correlations",[]):
        c.setdefault("provenance","CONTESTED_JOINT" if abs(float(c.get("rho",0)))<.12 else "HYPOTHESIZED_JOINT")
        counts[c["provenance"]]=counts.get(c["provenance"],0)+1
    world_model["relationship_provenance_counts"]=counts
    return world_model


def stereotype_adversary(world_model: dict[str,Any]) -> dict[str,Any]:
    flags=[]
    for f in world_model.get("factors",[]):
        conf=float(f.get("confidence",0))
        for d in f.get("drivers",[]):
            if d.get("field") in DEMO_FIELDS and abs(float(d.get("effect",0)))>=.25 and d.get("provenance")!="OBSERVED_JOINT":
                flags.append({"factor":f.get("id"),"field":d.get("field"),"effect":float(d.get("effect",0)),"confidence":conf,
                              "reason":"strong demographic relationship without observed joint evidence"})
    return {"kind":"anti_stereotype_adversary_v1","flags":flags,"risk":"HIGH" if len(flags)>=4 else "MEDIUM" if flags else "LOW",
            "recommended_stresses":["shrink_unobserved_demographic_effects","flip_weak_demographic_effects"] if flags else [],"sha256":sha_json(flags)}


def adversarial_world_model(world_model: dict[str,Any], mode: str) -> dict[str,Any]:
    x=json.loads(json.dumps(world_model,ensure_ascii=False))
    for f in x.get("factors",[]):
        for d in f.get("drivers",[]):
            if d.get("field") not in DEMO_FIELDS or d.get("provenance")=="OBSERVED_JOINT": continue
            e=float(d.get("effect",0))
            if mode=="shrink": d["effect"]=round(e*.35,5)
            elif mode=="flip_weak" and float(f.get("confidence",0))<.55: d["effect"]=round(-e*.5,5)
    x["adversarial_mode"]=mode; x["sha256"]=sha_json({k:v for k,v in x.items() if k!="sha256"}); return x


# ------------------------------------------------------------------
# 7. Joint-structure validation from respondent-level data


def _cramers_v(a: pd.Series,b: pd.Series) -> float:
    ct=pd.crosstab(a,b)
    if ct.empty: return float("nan")
    obs=ct.to_numpy(float); n=obs.sum()
    if n<=1: return float("nan")
    exp=obs.sum(1,keepdims=True)@obs.sum(0,keepdims=True)/n
    chi=float(np.sum(np.where(exp>0,(obs-exp)**2/exp,0)))
    den=max(1,min(obs.shape[0]-1,obs.shape[1]-1))
    return float(math.sqrt(max(0,chi/n/den)))


def _mutual_info(a: pd.Series,b: pd.Series) -> float:
    ct=pd.crosstab(a,b).to_numpy(float); n=ct.sum()
    if n<=0:return float("nan")
    p=ct/n; pa=p.sum(1,keepdims=True); pb=p.sum(0,keepdims=True); den=pa@pb
    ok=(p>0)&(den>0); return float(np.sum(p[ok]*np.log(p[ok]/den[ok])))


def joint_structure_score(pred: pd.DataFrame, truth: pd.DataFrame, question_ids: list[str]) -> dict[str,Any]:
    qs=[q for q in question_ids if q in pred.columns and q in truth.columns]
    pairs=[]
    for i,a in enumerate(qs):
        for b in qs[i+1:]:
            pv=_cramers_v(pred[a],pred[b]); tv=_cramers_v(truth[a],truth[b]); pm=_mutual_info(pred[a],pred[b]); tm=_mutual_info(truth[a],truth[b])
            if np.isfinite(pv) and np.isfinite(tv): pairs.append({"a":a,"b":b,"cramers_v_pred":pv,"cramers_v_truth":tv,"cramers_v_abs_error":abs(pv-tv),
                                                                    "mi_pred":pm,"mi_truth":tm,"mi_abs_error":abs(pm-tm) if np.isfinite(pm) and np.isfinite(tm) else None})
    return {"kind":"npc_joint_structure_score_v1","n_pairs":len(pairs),"mean_cramers_v_abs_error":round(float(np.mean([x["cramers_v_abs_error"] for x in pairs])),5) if pairs else None,
            "mean_mi_abs_error":round(float(np.mean([x["mi_abs_error"] for x in pairs if x["mi_abs_error"] is not None])),5) if any(x["mi_abs_error"] is not None for x in pairs) else None,
            "pairs":pairs,"note":"Joint score is diagnostic only; it never upgrades external predictive validation."}


# ------------------------------------------------------------------
# 9. Counter-intuitive truth checks


def counterintuitive_score(prediction: dict[str,Any], truth: dict[str,Any]) -> dict[str,Any]:
    checks=[]
    for qid,tq in (truth.get("questions") or {}).items():
        ci=tq.get("counterintuitive") if isinstance(tq,dict) else None
        if not isinstance(ci,dict): continue
        cat=str(ci.get("category") or ""); ref=float(ci.get("reference_pct",50)); direction=str(ci.get("direction") or "above")
        tv=float((tq.get("truth_pct") or {}).get(cat,np.nan)); pq=(prediction.get("questions") or {}).get(qid,{}); pv=float((pq.get("estimate_pct") or {}).get(cat,np.nan))
        if not np.isfinite(tv) or not np.isfinite(pv): continue
        truth_sign=(tv-ref)>0 if direction=="above" else (tv-ref)<0
        pred_sign=(pv-ref)>0 if direction=="above" else (pv-ref)<0
        checks.append({"question_id":qid,"category":cat,"truth_pct":tv,"prediction_pct":pv,"reference_pct":ref,"direction":direction,"truth_is_counterintuitive":truth_sign,"predicted_direction_correctly":pred_sign==truth_sign})
    return {"kind":"counterintuitive_truth_score_v1","n_checks":len(checks),"hit_rate":round(float(np.mean([x["predicted_direction_correctly"] for x in checks])),4) if checks else None,"checks":checks}


# ------------------------------------------------------------------
# 11. Response-noise policy learned only from prior blind leaderboard


def choose_noise_temperature(records: list[dict[str,Any]], default: float=1.0) -> dict[str,Any]:
    vals={}
    for r in records:
        m=str(r.get("method",""))
        if "__NOISE_" not in m: continue
        try: t=float(m.split("__NOISE_",1)[1].split("__",1)[0])
        except Exception: continue
        vals.setdefault(t,[]).append(float(r.get("mae_pp",np.nan)))
    eligible={t:[x for x in xs if np.isfinite(x)] for t,xs in vals.items()}
    eligible={t:xs for t,xs in eligible.items() if len(xs)>=3}
    if not eligible: return {"temperature":default,"status":"NO_BLIND_EVIDENCE_USE_NEUTRAL"}
    best=min(eligible,key=lambda t:np.mean(eligible[t]))
    return {"temperature":float(best),"status":"LEARNED_FROM_BLIND_ABLATION","n":len(eligible[best]),"mean_mae_pp":round(float(np.mean(eligible[best])),3)}

# ------------------------------------------------------------------
# 12. 10.15 optimization: convergence, residual learning, routing, demo guard


def question_signature(text: str, categories: Iterable[str]) -> str:
    import re
    s=re.sub(r"\s+"," ",re.sub(r"[^\w\s]"," ",str(text or "").casefold())).strip()
    payload={"text":s,"categories":[str(x).casefold().strip() for x in categories]}
    return sha_json(payload)[:20]


def residual_learning_profile(*, run_root: Path, bench_root: Path, domain: str="general", min_history: int=2) -> dict[str,Any]:
    """Learn conservative category residuals only from earlier blind truth.

    Exact question signatures are intentional: with a small history it is safer to
    learn a repeated-item correction than to hallucinate transfer across unrelated
    questions. Corrections are shrunk toward zero and capped at +/-10 p.p.
    """
    acc: dict[str,dict[str,list[float]]] = {}
    if bench_root.exists():
        for bd in bench_root.iterdir():
            if not bd.is_dir() or not (bd/"truth.json").exists(): continue
            try:
                truth=json.loads((bd/"truth.json").read_text(encoding="utf-8"))
                if truth.get("benchmark_eligibility")!="BLIND_ELIGIBLE": continue
                if str(truth.get("domain","general")) not in {str(domain),"general"}: continue
                rp=run_root/bd.name/"prediction.json"
                if not rp.exists(): continue
                pred=json.loads(rp.read_text(encoding="utf-8"))
                fs=(pred.get("methods") or {}).get("FULL_SIMULATION",{})
                for qid,tq in (truth.get("questions") or {}).items():
                    pq=(fs.get("questions") or {}).get(qid)
                    if not pq or not isinstance(tq,dict): continue
                    td=tq.get("truth_pct") or {}; pd=pq.get("estimate_pct") or {}
                    cats=list(td)
                    sig=question_signature(pq.get("text") or qid,cats)
                    for c in cats:
                        if c in pd:
                            acc.setdefault(sig,{}).setdefault(str(c),[]).append(float(td[c])-float(pd[c]))
            except Exception:
                continue
    items={}
    for sig,bycat in acc.items():
        good={}
        for c,xs in bycat.items():
            if len(xs)>=min_history:
                # empirical-Bayes-ish shrink: n/(n+3), then half-strength safety shrink
                n=len(xs); raw=float(np.mean(xs)); shrink=(n/(n+3))*0.5
                good[c]={"n":n,"raw_mean_residual_pp":round(raw,3),"correction_pp":round(_clip(raw*shrink,-10,10),3)}
        if good: items[sig]=good
    return {"kind":"npc_residual_learning_profile_v1","domain":domain,"items":items,"n_signatures":len(items),
            "policy":"exact repeated question only; blind history; conservative shrink and +/-10pp cap","sha256":sha_json(items)}


def apply_residual_correction(prediction: dict[str,Any], profile: dict[str,Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    out=json.loads(json.dumps(prediction,ensure_ascii=False)); hits=[]
    for qid,q in (out.get("questions") or {}).items():
        cats=list(q.get("categories") or (q.get("estimate_pct") or {}).keys())
        sig=question_signature(q.get("text") or qid,cats); corr=(profile.get("items") or {}).get(sig)
        if not corr: continue
        v=np.array([max(0,float((q.get("estimate_pct") or {}).get(c,0))+float((corr.get(c) or {}).get("correction_pp",0))) for c in cats],float)
        if v.sum()<=0: continue
        v*=100/v.sum()
        q["estimate_pct"]={c:round(float(v[i]),3) for i,c in enumerate(cats)}
        q["residual_learning"]={c:corr[c] for c in cats if c in corr}
        hits.append({"question_id":qid,"signature":sig,"categories":list(q["residual_learning"])})
    out["kind"]="npc_sim_learned_residual_v1"; out["residual_profile_sha256"]=profile.get("sha256"); out["sha256"]=sha_json(out)
    return out,{"hits":hits,"n_hits":len(hits)}


def world_convergence(world_results: list[dict[str,Any]], questions: list[dict[str,Any]], *, threshold_pp: float=1.25, window: int=3) -> dict[str,Any]:
    """Stop worlds when recent ensemble means stabilize; never earlier than window+1."""
    if len(world_results)<max(4,window+1):
        return {"converged":False,"worlds":len(world_results),"max_recent_shift_pp":None,"reason":"MIN_WORLDS"}
    qids=[str(q.get("id")) for q in questions]
    snapshots=[]
    start=max(1,len(world_results)-window)
    from full_simulation import ensemble_world_results  # local to avoid import cycle at module load
    for k in range(start,len(world_results)+1):
        e=ensemble_world_results(world_results[:k],questions); vec=[]
        for qid in qids:
            q=(e.get("questions") or {}).get(qid,{})
            for c in q.get("categories") or []: vec.append(float((q.get("estimate_pct") or {}).get(c,0)))
        snapshots.append(np.asarray(vec,float))
    shifts=[float(np.max(np.abs(b-a))) for a,b in zip(snapshots,snapshots[1:]) if len(a)==len(b) and len(a)]
    mx=max(shifts) if shifts else float("inf")
    return {"converged":bool(mx<=float(threshold_pp)),"worlds":len(world_results),"max_recent_shift_pp":round(mx,3) if np.isfinite(mx) else None,
            "threshold_pp":float(threshold_pp),"window":window,"reason":"STABLE" if mx<=float(threshold_pp) else "UNSTABLE"}


def _eta2_numeric_by_category(y: pd.Series, g: pd.Series) -> float:
    yy=pd.to_numeric(y,errors="coerce"); ok=yy.notna() & g.notna(); yy=yy[ok]; gg=g[ok].astype(str)
    if len(yy)<20 or yy.var(ddof=0)<=1e-12: return 0.0
    mu=float(yy.mean()); ss=float(((yy-mu)**2).sum())
    between=sum(len(v)*(float(v.mean())-mu)**2 for _,v in yy.groupby(gg))
    return float(between/ss) if ss>0 else 0.0


def demographic_overdetermination_guard(df: pd.DataFrame, *, factor_cols: list[str]|None=None, response_cols: list[str]|None=None,
                                         demographic_cols: Iterable[str]=("pohlavi","vek","vzdelani","kraj","velikost_obce"),
                                         warn_eta2: float=.18, red_eta2: float=.30) -> dict[str,Any]:
    """Detect when synthetic traits/responses are implausibly determined by demographics.

    Without human joint truth this is a *risk guard*, not a validation result. It
    blocks extreme caricature-like dependence and is later upgraded to an
    inflation ratio when a human calibration sample with matching fields arrives.
    """
    factor_cols=factor_cols or [c for c in df.columns if c.startswith("FS_") and c.endswith("_10")]
    response_cols=response_cols or []
    rows=[]
    for y in factor_cols:
        if y not in df: continue
        for d in demographic_cols:
            if d not in df: continue
            eta=_eta2_numeric_by_category(df[y],df[d])
            if eta>=warn_eta2: rows.append({"outcome":y,"demographic":d,"eta2":round(eta,4),"severity":"RED" if eta>=red_eta2 else "AMBER"})
    # categorical response association as Cramer's V
    for y in response_cols:
        if y not in df: continue
        for d in demographic_cols:
            if d not in df: continue
            v=_cramers_v(df[y].astype(str),df[d].astype(str))
            if np.isfinite(v) and v>=.35: rows.append({"outcome":y,"demographic":d,"cramers_v":round(v,4),"severity":"RED" if v>=.55 else "AMBER"})
    sev="RED" if any(x["severity"]=="RED" for x in rows) else "AMBER" if rows else "GREEN"
    return {"kind":"npc_demographic_overdetermination_guard_v1","status":sev,"flags":rows[:100],"n_flags":len(rows),
            "note":"Pre-truth risk guard only; it does not claim human demographic inflation without a human joint benchmark."}


def demographic_inflation_score(pred: pd.DataFrame, truth: pd.DataFrame, question_ids: list[str], demographic_cols: Iterable[str]=( "pohlavi","vek","vzdelani","kraj")) -> dict[str,Any]:
    rows=[]
    for q in question_ids:
        if q not in pred or q not in truth: continue
        for d in demographic_cols:
            if d not in pred or d not in truth: continue
            pv=_cramers_v(pred[q].astype(str),pred[d].astype(str)); tv=_cramers_v(truth[q].astype(str),truth[d].astype(str))
            if not(np.isfinite(pv) and np.isfinite(tv)): continue
            ratio=float(pv/max(tv,.03)); rows.append({"question_id":q,"demographic":d,"synthetic_v":round(pv,4),"human_v":round(tv,4),"inflation_ratio":round(ratio,3)})
    vals=[r["inflation_ratio"] for r in rows]
    return {"kind":"npc_demographic_inflation_score_v1","n_pairs":len(rows),"median_ratio":round(float(np.median(vals)),3) if vals else None,
            "mean_ratio":round(float(np.mean(vals)),3) if vals else None,"red":bool(vals and np.median(vals)>1.8),"pairs":rows}


def recommend_human_n(meta_error: dict[str,Any], robustness: dict[str,Any]|None=None, *, history_n: int=0) -> int:
    qs=list((meta_error.get("questions") or {}).values()); exp=max([float(x.get("expected_mae_pp",6)) for x in qs] or [6.0])
    fragile=len((robustness or {}).get("fragile_questions") or [])
    if exp<=3.5 and not fragile and history_n>=5: return 25
    if exp<=5.5 and fragile==0: return 50
    if exp<=8.0 and fragile<=1: return 100
    return 250


def decision_router(*, meta_error: dict[str,Any], robustness: dict[str,Any]|None, stereotype: dict[str,Any]|None,
                    learning_profile: dict[str,Any]|None, benchmark_eligible: bool, human_calibration_n: int=0,
                    joint_status: str="JOINT_UNVALIDATED") -> dict[str,Any]:
    qs=list((meta_error.get("questions") or {}).values()); maxerr=max([float(x.get("expected_mae_pp",6)) for x in qs] or [6.0]); maxp=max([float(x.get("p_error_gt_10pp",.2)) for x in qs] or [.2])
    frag=len((robustness or {}).get("fragile_questions") or []); srisk=(stereotype or {}).get("risk","LOW")
    hist=int((learning_profile or {}).get("n_benchmarks",0)); rec_n=recommend_human_n(meta_error,robustness,history_n=hist)
    reasons=[]; abstain=False
    if not benchmark_eligible: reasons.append("scenario/nowcast is contaminated for blind scoring")
    if frag: reasons.append(f"{frag} question(s) are wording/model fragile")
    if srisk=="HIGH": reasons.append("world model has strong unobserved demographic dependencies")
    if maxp>=.55 or maxerr>=12 or (frag>=2 and srisk=="HIGH"):
        mode="STANDARD_HUMAN_SURVEY"; abstain=True; reasons.append("predicted synthetic error is too high")
    elif human_calibration_n>=rec_n:
        mode=f"NPC_HYBRID_{human_calibration_n}"; reasons.append("human mini-sample is large enough for rectification")
    elif human_calibration_n>0:
        mode=f"NPC_HYBRID_{human_calibration_n}_EARLY"; reasons.append(f"collect up to about n={rec_n} if posterior is still moving")
    elif maxerr<=4.5 and frag==0 and srisk!="HIGH" and hist>=3:
        mode="NPC_SIM"; reasons.append("blind history + current diagnostics support synthetic-only use")
    else:
        mode=f"NPC_HYBRID_{rec_n}_RECOMMENDED"; reasons.append("use synthetic prior but rectify it with a small human sample")
    return {"kind":"npc_decision_router_v1","recommended_mode":mode,"recommended_human_n":rec_n,"abstain_from_synthetic_only":abstain,
            "max_expected_mae_pp":round(maxerr,3),"max_p_error_gt_10pp":round(maxp,4),"history_n":hist,"joint_status":joint_status,"reasons":reasons,
            "note":"Router is operational guidance. It does not upgrade evidence tier or external predictive validation."}


def calibration_stability(curve: dict[str,dict[str,Any]], *, tolerance_pp: float=2.0) -> dict[str,Any]:
    parsed=[]
    for name,p in curve.items():
        try: n=int(name.rsplit("_",1)[1])
        except Exception: continue
        parsed.append((n,p))
    parsed.sort(); steps=[]; recommended=None
    for (n0,p0),(n1,p1) in zip(parsed,parsed[1:]):
        diffs=[]
        for qid,q1 in (p1.get("questions") or {}).items():
            q0=(p0.get("questions") or {}).get(qid,{})
            for c,v in (q1.get("estimate_pct") or {}).items():
                if c in (q0.get("estimate_pct") or {}): diffs.append(abs(float(v)-float(q0["estimate_pct"][c])))
        mx=max(diffs) if diffs else None; steps.append({"from_n":n0,"to_n":n1,"max_shift_pp":round(mx,3) if mx is not None else None})
        if mx is not None and mx<=tolerance_pp and recommended is None: recommended=n1
    if recommended is None and parsed: recommended=parsed[-1][0]
    return {"kind":"npc_calibration_stability_v1","recommended_n":recommended,"tolerance_pp":tolerance_pp,"steps":steps,
            "status":"STABLE" if steps and any((x["max_shift_pp"] or 999)<=tolerance_pp for x in steps) else "MORE_HUMANS_MAY_HELP"}
