"""Compile free-text scenarios into explicit, reviewable measured-variable shifts.

The free-text story is never the final simulation object. The compiler produces a
structured delta contract that a user can review before Full Simulation. The output
policy is always change/difference first, not an absolute population level claim.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any
import json

from provider_auth import get_ai_provider
from ai_router import call_structured
from typology_reference import compact_typology_context

OBJECTIVES={"subgroup_delta","variant_delta","baseline_delta"}

SCHEMA={
    "type":"object",
    "properties":{
        "title":{"type":"string"},
        "objective":{"type":"string","enum":sorted(OBJECTIVES)},
        "baseline":{"type":"string"},
        "event":{"type":"string"},
        "time_horizon":{"type":"string"},
        "target_outcomes":{"type":"array","items":{"type":"string"}},
        "shifts":{"type":"array","items":{"type":"object","properties":{
            "factor":{"type":"string"},"direction":{"type":"string","enum":["increase","decrease","mixed"]},
            "magnitude_sd":{"type":"number"},"scope":{"type":"string"},"mechanism":{"type":"string"},
            "confidence":{"type":"number"},"evidence_basis":{"type":"string"}
        },"required":["factor","direction","magnitude_sd","scope","mechanism","confidence","evidence_basis"],"additionalProperties":False}},
        "assumptions":{"type":"array","items":{"type":"string"}},
        "unknowns":{"type":"array","items":{"type":"string"}},
        "review_note":{"type":"string"}
    },
    "required":["title","objective","baseline","event","time_horizon","target_outcomes","shifts","assumptions","unknowns","review_note"],
    "additionalProperties":False
}

SYSTEM="""Jsi výzkumný metodik a kompilátor scénářů. Nepředpovídáš výsledek.
Překládáš volný scénář na explicitní, auditovatelný delta kontrakt k lidskému schválení.

Pravidla:
- Výstupem je vždy rozdíl: mezi skupinami, variantami nebo proti baseline; nikdy netvrď absolutní poptávku ani volební procento.
- Každý shift musí být mechanismus/faktor, ne finální outcome. magnitude_sd je hypotéza o síle zásahu, ne naměřený fakt.
- Bez opory nepoužívej vysokou confidence. Nevymýšlej zdroje ani konkrétní statistiky.
- Odděl assumptions a unknowns. Když scénář vyžaduje klientskou populaci a projekt ji nemá, uveď to v unknowns/review_note.
- Nepiš přesvědčivý příběh; vytvoř objekt, který lze odmítnout nebo upravit před simulací.
- Pokud je přiložena TYPOLOGIE 2026, používej ji pouze jako hypotézový seznam mechanismů/kandidátních skupin. Není to změřená segmentace současného panelu; nikdy z ní nedělej absolutní podíly ani hard assignment.
- U cenových a promo scénářů NIKDY nepředpokládej lineární response. Zvaž reference price, cenové prahy, perceived quality/premium signal, brand equity a důvěru, promo/deal-proneness, channel economics/marži, konkurenční reakci, substituci a segmentovou heterogenitu.
- Různé varianty změny se kompilují samostatně. magnitude_sd varianty nesmí vzniknout prostým násobením jedné hodnoty podle procenta změny.
- Pokud SIMULATION_CONTEXT obsahuje evidence/nejistoty, používej evidence-backed fakta a nevyřešené položky ponech jako assumptions/unknowns; nevymýšlej jejich řešení."""


def _sanitize(x: dict[str,Any], *, project: dict[str,Any]|None=None) -> dict[str,Any]:
    out=deepcopy(x or {})
    if out.get("objective") not in OBJECTIVES: out["objective"]="baseline_delta"
    shifts=[]
    for s in out.get("shifts") or []:
        try: mag=float(s.get("magnitude_sd",0))
        except Exception: mag=0.0
        try: conf=float(s.get("confidence",0.3))
        except Exception: conf=0.3
        shifts.append({"factor":str(s.get("factor") or "").strip(),"direction":s.get("direction") if s.get("direction") in {"increase","decrease","mixed"} else "mixed",
                       "magnitude_sd":round(max(-2.0,min(2.0,mag)),3),"scope":str(s.get("scope") or "whole audience").strip(),
                       "mechanism":str(s.get("mechanism") or "").strip(),"confidence":round(max(0.0,min(1.0,conf)),3),
                       "evidence_basis":str(s.get("evidence_basis") or "hypothesis_to_review").strip()})
    out["shifts"]=shifts[:12]
    out["target_outcomes"]=[str(x).strip() for x in out.get("target_outcomes") or [] if str(x).strip()][:12]
    out["assumptions"]=[str(x).strip() for x in out.get("assumptions") or [] if str(x).strip()][:12]
    out["unknowns"]=[str(x).strip() for x in out.get("unknowns") or [] if str(x).strip()][:12]
    aud=(project or {}).get("audience") or {}
    src=str(aud.get("source_mode") or "population")
    if src in {"customer","special_audience"} and not aud.get("dataset_id"):
        out["unknowns"].append("Projekt nemá zvolený dataset pro deklarovanou speciální audience.")
    out["claim_policy"]={"primary_output":"delta","absolute_level_claims_allowed":False,
                         "subgroup_profile_requires_joint_support":True,"human_review_required":True}
    out["status"]="REVIEW_REQUIRED"
    return out


def compile_scenario(text: str, *, project: dict[str,Any]|None=None, baseline: str="", objective: str|None=None,
                     model: str="sonnet", provider: str|None=None) -> dict[str,Any]:
    text=str(text or "").strip()
    if not text: raise ValueError("Scénář je prázdný.")
    provider=str(provider or ((project or {}).get("run_policy") or {}).get("provider") or get_ai_provider())
    _aud=(project or {}).get("audience",{}) or {}
    _typo=compact_typology_context(text + " " + str((project or {}).get("decision_use",""))) if str(_aud.get("source_mode") or "population")=="population" else {}
    _research=(project or {}).get("pre_research") or {}
    _simctx=(project or {}).get("simulation_context") or {}
    _ctx_evidence=((_simctx.get("evidence") or {}).get("accepted") or []) if isinstance(_simctx,dict) else []
    _project_ev=[{"claim":x.get("claim"),"source_title":x.get("source_title"),"source_url":x.get("source_url"),"topics":x.get("topics")} for x in (_research.get("accepted") or [])[:12]]
    _sim_ev=[{"claim":x.get("claim"),"source_title":x.get("source_title"),"source_url":x.get("source_url"),"topics":x.get("topics")} for x in _ctx_evidence[:16]]
    context={"scenario":text,"baseline":baseline,"objective_hint":objective or "",
             "decision_use":(project or {}).get("decision_use",""),"audience":_aud,
             "research_plan":(project or {}).get("research_plan",{}),
             "simulation_context":{k:v for k,v in _simctx.items() if k not in {"evidence","data_library"}} if isinstance(_simctx,dict) else {},
             "existing_safe_research":_project_ev+_sim_ev}
    if _typo: context["typology_2026_hypothesis_reference"]=_typo
    try:
        r=call_structured(system=SYSTEM,messages=[{"role":"user","content":json.dumps(context,ensure_ascii=False,indent=2)}],
                          schema=SCHEMA,schema_name="npc_scenario_compiler",anthropic_model=model,max_tokens=2500,
                          prefer=provider,allow_fallback=False)
        out=_sanitize(r.get("data") or {},project=project)
        out["_ai"]={k:r.get(k) for k in ("provider","model","fallback_used","mode","tok_in","tok_out")}
        return out
    except Exception as exc:
        from ai_execution_context import is_cancel_exception
        if is_cancel_exception(exc):
            raise
        # Production is fail-visible. Never relabel a failed LIVE provider as a
        # "local_fallback" scenario, because that makes the user think the AI step
        # succeeded and then causes the simulation to fail later with empty shifts.
        import os
        if str(os.environ.get("NPC_ALLOW_LOCAL_SCENARIO_FALLBACK", "")).strip().lower() in {"1","true","yes","on"}:
            return _sanitize({"title":"Scénář k revizi","objective":objective or "baseline_delta","baseline":baseline or "Výchozí stav projektu",
                              "event":text,"time_horizon":"neuvedeno","target_outcomes":[],"shifts":[],
                              "assumptions":[],"unknowns":["DEBUG fallback: AI kompilátor nebyl dostupný; posuny nebyly odhadnuty."],
                              "review_note":"DEBUG pouze. Bez schválených shifts se scénář nesmí spustit."},project=project) | {"_ai":{"provider":"debug_local_fallback","fallback_used":True,"invalid_for_live":True,"error":str(exc)[:700]}}
        raise RuntimeError(f"SCENARIO_AI_FAILED: {provider}: {exc}") from exc


def approve_scenario(contract: dict[str,Any]) -> dict[str,Any]:
    c=_sanitize(contract)
    if not c.get("shifts"):
        raise ValueError("Scénář nemá žádné explicitní shifts; není co schválit pro simulaci.")
    c["status"]="APPROVED"
    c["claim_policy"]["human_review_required"]=False
    return c


def compile_scenario_variants(base_change: str, variants: list[dict[str,Any]], *, project:dict[str,Any]|None=None,
                              baseline:str="", objective:str|None=None, model:str="sonnet", provider:str|None=None) -> dict[str,Any]:
    """Compile several variants independently against the same evidence context."""
    base=str(base_change or '').strip()
    if not base: raise ValueError('Popište změnu, ze které mají varianty vycházet.')
    clean=[]
    for i,v in enumerate(variants or []):
        if not isinstance(v,dict): continue
        value=v.get('value'); label=str(v.get('label') or f'Varianta {i+1}').strip()
        variable=str(v.get('variable') or 'změna').strip(); unit=str(v.get('unit') or '').strip()
        desc=str(v.get('change') or '').strip() or f"{base} | {variable}: {value}{unit}"
        clean.append({'id':str(v.get('id') or f'V{i+1}'),'label':label,'variable':variable,'value':value,'unit':unit,'change':desc})
    if not clean: raise ValueError('Batch simulace neobsahuje žádné varianty.')
    if len(clean)>12: raise ValueError('V jednom porovnání lze spustit nejvýše 12 variant.')
    compiled=[]
    for v in clean:
        prompt=(f"VARIANTA {v['label']}\nZákladní změna: {base}\nKonkrétní parametr: {v['variable']} = {v['value']}{v['unit']}\n"
                f"Variantu kompiluj samostatně. Neškáluj mechanicky magnitude_sd z jiné varianty.\nDetail: {v['change']}")
        c=compile_scenario(prompt,project=project,baseline=baseline,objective=objective,model=model,provider=provider)
        c['variant']={k:v[k] for k in ('id','label','variable','value','unit','change')}
        c['comparison_family']='INDEPENDENT_VARIANTS_SHARED_CONTEXT'
        compiled.append(c)
    return {'kind':'npc_scenario_batch_v1','status':'REVIEW_REQUIRED','base_change':base,'variants':compiled,
            'nonlinearity_policy':'Each variant is independently compiled; no linear interpolation assumption.',
            'context_sha256':((project or {}).get('simulation_context') or {}).get('sha256')}


def approve_scenario_batch(batch: dict[str,Any]) -> dict[str,Any]:
    out=deepcopy(batch or {}); vals=[]
    for c in out.get('variants') or []:
        cc=approve_scenario(c); cc['variant']=deepcopy(c.get('variant') or {})
        cc['comparison_family']='INDEPENDENT_VARIANTS_SHARED_CONTEXT'; vals.append(cc)
    if not vals: raise ValueError('Batch neobsahuje schvalitelné varianty.')
    out['variants']=vals; out['status']='APPROVED'; return out
