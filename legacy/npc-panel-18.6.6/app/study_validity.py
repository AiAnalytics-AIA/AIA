"""Pre-run claim/readiness scorecard.

Axes intentionally use different vocabularies. Evidence coverage, sampling precision,
design quality and external predictive validation are not the same thing and must never
collapse into a self-awarded numeric score.
"""
from __future__ import annotations
from runtime_config import RUN_DEFAULTS
from typing import Any
import pandas as pd
from audience import feasibility, sampling_precision_pp
from core_joint import load_joint_status
from validation_status import validation_tier


def _evidence_axis(per_question:list[dict])->dict[str,Any]:
    scored=[q for q in per_question if q.get("score") is not None]
    if not scored:
        return {"status":"unsupported","score":None,"note":"Otázky se nepodařilo navázat na evidenční domény."}
    avg=sum(float(q["score"]) for q in scored)/len(scored)
    red=[q for q in scored if q.get("grade")=="RED"]
    guess=[q for q in scored if float(q.get("own_estimate_share") or 0)>=.5]
    if len(guess)>=len(scored)/2: status="unsupported"
    elif len(red)>=len(scored)/2: status="weak"
    elif red: status="moderate"
    else: status="strong"
    return {"status":status,"score":round(avg,1),"red_questions":[q.get("id") for q in red],
            "own_estimate_questions":[q.get("id") for q in guess],
            "note":"Grounding popisuje původ/evidenci dimenzí; není to prediktivní validita."}


def _stat_axis(questions:list[dict], feas:dict)->dict[str,Any]:
    n=float(feas.get("dosazitelne_n") or 0); ess=float(feas.get("ess") or n); base=min(n,ess) if ess else n
    rows=[]; worst="high"
    rank={"high":3,"medium":2,"low":1,"insufficient":0}
    def worsen(cur,new): return new if rank[new]<rank[cur] else cur
    for q in questions:
        filtered=bool(str(q.get("filtr") or "").strip()); eff=base*.5 if filtered else base
        st="high" if eff>=400 else "medium" if eff>=250 else "low" if eff>=100 else "insufficient"
        worst=worsen(worst,st)
        rows.append({"id":q.get("id"),"estimated_effective_n":int(eff),"filtered":filtered,
                     "sampling_precision_pp":sampling_precision_pp(eff),"status":st})
    return {"status":worst,"base_effective_n":round(base,1),"per_question":rows,
            "note":"Sampling-only precision; nezahrnuje chybu NPC modelu ani rozdíl proti reálné populaci."}


def _design_axis(lint:dict,questions:list[dict])->dict[str,Any]:
    errors=list(lint.get("errors") or []); warns=list(lint.get("warnings") or [])
    intent=[q.get("id") for q in questions if q.get("hypoteticka") or any(w in str(q.get("text","")).lower() for w in ("koupil byste","zvažoval","byste si","uvažoval"))]
    if errors: status="invalid"
    elif warns and intent: status="problematic"
    elif warns or intent: status="caution"
    else: status="clean"
    notes=[]
    if errors: notes.append(f"{len(errors)} lint chyb.")
    if warns: notes.append(f"{len(warns)} lint varování.")
    if intent: notes.append("Purchase/stated-intent otázky měří deklarovaný záměr; jako konverzi je lze interpretovat jen s empiricky validovanou behavioral calibration pro danou doménu.")
    return {"status":status,"hypothetical_questions":list(filter(None,intent)),"note":" ".join(notes) or "Bez zjevné designové vady."}


def _segment_axis(feas:dict)->dict[str,Any]:
    if not feas.get("ok",True): status="impossible"
    else:
        support=float(feas.get("support") or 0); n=float(feas.get("pozadovane_n") or 0); ess=float(feas.get("ess") or 0)
        if not support or n>support: status="impossible"
        elif ess<max(150,n*.5): status="weak"
        elif n>support*.5: status="adequate"
        else: status="strong"
    return {"status":status,"support":feas.get("support"),"ess":feas.get("ess"),
            "population_share_pct":feas.get("podil_populace_pct"),
            "note":"Podíl a support vycházejí z Census-kalibrované páteře; profilové signály jsou same-person measured nebo explicitně MATCHED_DONOR_BLOCK a nejsou kauzální claim."}


def _external_axis()->dict[str,Any]:
    tier=validation_tier()
    return {"status":tier.lower(),"tier":tier,
            "note":"SMOKE je vývojová evidence; pouze HOLDOUT_VALIDATED je finální blind externí evidence."}


def _joint_axis(persona_mode:str=RUN_DEFAULTS["persona_mode"])->dict[str,Any]:
    if str(persona_mode).lower()=="calibrated":
        from persona_calibration import calibration_status
        cs=calibration_status(); mode=str(cs.get("global_mode") or "core") if cs.get("active") else "core"
        base=_joint_axis(mode); base=dict(base); base["note"]=(base.get("note") or "")+" Persona recipe je vybrán human benchmark kalibrací."; return base
    if str(persona_mode).lower() in {"none","demographics"}:
        return {"status":"not_applicable","ablation_status":"BASELINE_MODE","client_joint_outputs_allowed":True,"diagnostics":{},"note":"Tento persona mode nepoužívá tematické donor bloky."}
    st=load_joint_status(); d=st.get("diagnostics") or {}
    return {"status":str(st.get("status","JOINT_UNVALIDATED")).lower(),
            "structure_status":st.get("structure_status"),
            "prediction_validation_status":st.get("prediction_validation_status","UNVALIDATED"),
            "core_same_person_joint":bool(st.get("core_same_person_joint")),
            "specialist_block_internal_joint":bool(st.get("specialist_block_internal_joint")),
            "cross_block_same_person_joint":bool(st.get("cross_block_same_person_joint")),
            "descriptive_core_outputs_allowed":bool(st.get("descriptive_core_outputs_allowed")),
            "matched_block_outputs_allowed":bool(st.get("matched_block_outputs_allowed")),
            "client_joint_outputs_allowed":bool(st.get("client_joint_outputs_allowed")),
            "diagnostics":d,
            "note":"v15.2 odděluje strukturální koherenci dat od prediktivní validity: core je same-person, jednotlivé tematické bloky jsou whole-donor; vazby mezi průzkumy jsou matching a nové NPC odpovědi vyžadují externí validaci."}


def _claim_level(axes:dict[str,dict])->tuple[str,list[str]]:
    blockers=[]
    if axes["design"]["status"]=="invalid": blockers.append("design")
    if axes["segment"]["status"]=="impossible": blockers.append("segment")
    if axes["statistical"]["status"]=="insufficient": blockers.append("statistical")
    if blockers:return "BLOCKED",blockers
    if axes["external"]["tier"]=="HOLDOUT_VALIDATED" and axes["joint"].get("client_joint_outputs_allowed") and axes["evidence"]["status"] in {"strong","moderate"}:
        return "PREDICTIVE",[]
    if axes["external"]["tier"]=="SMOKE_VALIDATED" and axes["joint"].get("client_joint_outputs_allowed"):
        return "DIRECTIONAL",[]
    return "EXPERIMENTAL",[]


def scorecard(*,otazky:list[dict],lint:dict,per_question:list[dict],panel:pd.DataFrame,filtry:dict|None,n:int,validation_status:str|None=None,persona_mode:str=RUN_DEFAULTS["persona_mode"])->dict[str,Any]:
    feas=feasibility(panel,filtry,int(n or 0))
    evidence=_evidence_axis(per_question)
    if str(persona_mode).lower()=="none": evidence={"status":"not_applicable","score":None,"note":"Generic baseline nepoužívá panelové evidence dimenze."}
    elif str(persona_mode).lower()=="demographics": evidence={"status":"strong","score":None,"note":"Demographics-only baseline používá Census-kalibrovanou populační páteř; tematické donor bloky se nepoužívají."}
    axes={"statistical":_stat_axis(otazky,feas),"evidence":evidence,
          "design":_design_axis(lint,otazky),"segment":_segment_axis(feas),
          "joint":_joint_axis(persona_mode),"external":_external_axis()}
    claim,blockers=_claim_level(axes)
    return {"claim_level":claim,"blocking_axes":blockers,"axes":axes,
            "target_group":{k:feas.get(k) for k in ("filtry","support","podil_populace_pct","ess","dosazitelne_n","sampling_precision_pp_pri_n")},
            "interpretation":{
                "BLOCKED":"Běh/výstup nemá splněný základní kontrakt.",
                "EXPERIMENTAL":"Použitelné pro interní hypotézy a testování; ne jako populační predikce.",
                "DIRECTIONAL":"Existuje vývojová evidence pro směr/kontrast, ne finální blind certifikace.",
                "PREDICTIVE":"Prediktivní claim je vázán na aktuální fingerprint a validovaný holdout."
            }[claim]}


def achieved_precision(summary:dict)->list[dict]:
    out=[]
    for qid,r in (summary.get("vysledky") or {}).items():
        n=int(r.get("n_platnych") or 0)
        out.append({"id":qid,"n_platnych":n,"n_eligible":r.get("n_eligible"),
                    "sampling_precision_pp":sampling_precision_pp(n),
                    "note":"sampling-only; not model/population error"})
    return out
