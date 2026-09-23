"""AI-enriched context layer for standalone client-facing simulations.

A user may start with a short brief.  The system first structures what it knows,
then performs topic research on the same Claude Code subscription, then synthesizes
a context pack with explicit provenance and an actionable uncertainty register.
No unsupported market fact is silently promoted to a fact.
"""
from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
from typing import Any
import hashlib, json, time

from ai_router import call_structured
from provider_auth import get_ai_provider
from provider_runtime import normalize_live_provider


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()


def _uncertainty_schema() -> dict[str,Any]:
    return {"type":"object","properties":{
        "id":{"type":"string"},"question":{"type":"string"},"why_it_matters":{"type":"string"},
        "status":{"type":"string","enum":["RESOLVED","UNRESOLVED","ASSUMPTION"]},
        "answer":{"type":"string"},"confidence":{"type":"number"},
        "source_urls":{"type":"array","items":{"type":"string"}},
        "recommended_action":{"type":"string","enum":["use_evidence","research","ask_user","keep_assumption"]},
    },"required":["id","question","why_it_matters","status","answer","confidence","source_urls","recommended_action"],"additionalProperties":False}


def _context_schema() -> dict[str,Any]:
    return {"type":"object","properties":{
        "title":{"type":"string"},"subject":{"type":"string"},"client":{"type":"string"},
        "product_service":{"type":"string"},"category":{"type":"string"},"market":{"type":"string"},
        "geography":{"type":"string"},"current_state":{"type":"string"},"current_price":{"type":"string"},
        "price_unit":{"type":"string"},"price_architecture":{"type":"string"},
        "competitors":{"type":"array","items":{"type":"string"}},
        "brand_positioning":{"type":"string"},"customer_segments":{"type":"array","items":{"type":"string"}},
        "purchase_drivers":{"type":"array","items":{"type":"string"}},
        "category_dynamics":{"type":"array","items":{"type":"string"}},
        "constraints":{"type":"array","items":{"type":"string"}},
        "decision":{"type":"string"},"outcomes":{"type":"array","items":{"type":"string"}},
        "known_facts":{"type":"array","items":{"type":"string"}},
        "assumptions":{"type":"array","items":{"type":"string"}},
        "uncertainties":{"type":"array","items":_uncertainty_schema()},
        "research_questions":{"type":"array","items":{"type":"string"}},
        "summary":{"type":"string"},
    },"required":["title","subject","client","product_service","category","market","geography","current_state","current_price","price_unit","price_architecture","competitors","brand_positioning","customer_segments","purchase_drivers","category_dynamics","constraints","decision","outcomes","known_facts","assumptions","uncertainties","research_questions","summary"],"additionalProperties":False}


_DISCOVERY_SYSTEM="""Jsi seniorní strategy researcher. Z krátkého zadání simulace vytvoř strukturovaný briefing pro následný evidence research.
Nevymýšlej fakta, ceny, konkurenty ani podíly. Co z briefu nevíš, nech prázdné nebo jako explicitní nejistotu.
Navrhni výzkumné otázky, které mají dohledat klienta/produkt, kategorii a trh, aktuální ceny a cenovou architekturu, relevantní konkurenty, positioning značky, distribuční prostředí, nákupní faktory a mechanismy důležité pro scénář.
U cenových scénářů vždy mysli na reference price, kvalitu/premium signal, brand equity, promotion/deal-proneness, competitor response, channel economics a segmentovou heterogenitu. Neodvozuj výsledek simulace."""

_SYNTHESIS_SYSTEM="""Jsi seniorní strategy researcher a evidence synthesizer pro klientskou simulaci.
Syntetizuj briefing, webový evidence pack a Data Library do jednoho auditovatelného context packu.
Pravidla:
- Fakt můžeš uvést jako known_fact jen pokud je z původního briefu nebo je opřený o přiložený evidence source_url.
- Nevymýšlej cenu, konkurenta, klienta, tržní podíl ani chování trhu.
- Každou významnou mezeru dej do uncertainties. RESOLVED pouze když ji evidence skutečně řeší; jinak UNRESOLVED nebo ASSUMPTION.
- U nejistoty dej doporučenou akci: research / ask_user / keep_assumption / use_evidence.
- Price response nikdy nepředpokládej lineární. Uveď relevantní nelineární mechanismy a segmentovou heterogenitu v purchase_drivers/category_dynamics.
- Výstup je kontext pro model scénáře, ne predikce výsledku."""


def _coerce_context(x: dict[str,Any]) -> dict[str,Any]:
    out=deepcopy(x or {})
    for k in ("competitors","customer_segments","purchase_drivers","category_dynamics","constraints","outcomes","known_facts","assumptions","research_questions"):
        out[k]=[str(v).strip() for v in (out.get(k) or []) if str(v).strip()][:30]
    unc=[]
    for i,u in enumerate(out.get('uncertainties') or []):
        if not isinstance(u,dict): continue
        try: conf=max(0.0,min(1.0,float(u.get('confidence') or 0)))
        except Exception: conf=0.0
        unc.append({
            'id':str(u.get('id') or f'U{i+1}').strip()[:80],
            'question':str(u.get('question') or '').strip()[:700],
            'why_it_matters':str(u.get('why_it_matters') or '').strip()[:700],
            'status':str(u.get('status') or 'UNRESOLVED') if str(u.get('status') or '') in {'RESOLVED','UNRESOLVED','ASSUMPTION'} else 'UNRESOLVED',
            'answer':str(u.get('answer') or '').strip()[:1200],
            'confidence':round(conf,3),
            'source_urls':[str(v).strip() for v in (u.get('source_urls') or []) if str(v).strip()][:8],
            'recommended_action':str(u.get('recommended_action') or 'research') if str(u.get('recommended_action') or '') in {'use_evidence','research','ask_user','keep_assumption'} else 'research',
        })
    out['uncertainties']=unc[:30]
    for k in ("title","subject","client","product_service","category","market","geography","current_state","current_price","price_unit","price_architecture","brand_positioning","decision","summary"):
        out[k]=str(out.get(k) or '').strip()[:4000]
    return out


def _evidence_public(bundle) -> dict[str,Any]:
    return {
        'enabled':bool(bundle.enabled),'topic':bundle.topic,'created_at':bundle.created_at,
        'quality_status':bundle.quality_status,'sha256':bundle.sha256,
        'accepted':list(bundle.accepted or []),'quarantined':list(bundle.quarantined or []),
        'agents':[{'agent':a.agent,'model':a.model,'searched_at':a.searched_at,'error':a.error,'findings':len(a.findings)} for a in bundle.agents],
    }


def enrich_simulation_context(raw_brief: str, *, project: dict[str,Any]|None=None,
                              existing_context: dict[str,Any]|None=None,
                              unresolved_only: bool=False, model: str='sonnet',
                              provider: str|None=None, max_sources: int=8, progress=None, deep_research: bool=True) -> dict[str,Any]:
    brief=str(raw_brief or '').strip()
    if not brief and not existing_context:
        raise ValueError('Popište alespoň stručně, co chcete simulovat.')
    provider=normalize_live_provider(provider or ((project or {}).get('run_policy') or {}).get('provider') or get_ai_provider())
    _progress=progress if callable(progress) else (lambda _x:None)
    effective_model=('haiku' if provider=='claude_code_subscription' and not deep_research and str(model or '').lower() in {'sonnet','claude-sonnet',''} else model)
    _progress('Simulace · rychle strukturuji zadání a mapuji nejistoty' if not deep_research else 'Simulace · AI strukturuje zadání a mapuje informační mezery')
    discovery_payload={'raw_brief':brief,'project_context':project or {},'existing_context':existing_context or {},'mode':'resolve_uncertainties' if unresolved_only else 'new_simulation'}
    rr=call_structured(system=_DISCOVERY_SYSTEM,messages=[{'role':'user','content':json.dumps(discovery_payload,ensure_ascii=False,default=str)}],
                       schema=_context_schema(),schema_name='npc_simulation_context_discovery',anthropic_model=effective_model,max_tokens=(2200 if not deep_research else 5000),
                       prefer=provider,allow_fallback=False,timeout=(85 if not deep_research else 360),
                       claude_max_turns=(2 if not deep_research else 8),claude_interactive=(not deep_research))
    draft=_coerce_context(rr.get('data') or {})

    # Fast path: do NOT gate the simulation behind web research. Data Library is local
    # and cheap, so include it immediately; deep evidence remains an explicit option.
    if not deep_research:
        try:
            from data_library import knowledge_context_for_project
            library=knowledge_context_for_project(project or {'goal':brief,'briefing':{'product_description':brief}},limit=12)
        except Exception as exc:
            library={'dimensions':[],'count':0,'warning':str(exc)[:500]}
        evidence={'enabled':False,'topic':'','created_at':_now(),'quality_status':'NOT_RUN_FAST_CONTEXT','sha256':None,'accepted':[],'quarantined':[],'agents':[],
                  'note':'Web Deep Research nebyl pro rychlý start spuštěn. Lze jej spustit explicitně bez ztráty tohoto kontextu.'}
        draft['_meta']={'created_at':_now(),'provider':rr.get('provider') or provider,'model':rr.get('model') or effective_model,
                        'raw_brief':brief,'mode':'quick_context','deep_research':False,'evidence_sha256':None,'data_library_count':library.get('count',0)}
        draft['evidence']=evidence; draft['data_library']=library
        draft['sha256']=_sha({k:v for k,v in draft.items() if k!='sha256'})
        return draft

    questions=[{'id':f'CTX{i+1}','text':q,'kategorie':[]} for i,q in enumerate(draft.get('research_questions') or [])]
    if unresolved_only:
        questions=[{'id':str(u.get('id') or f'U{i+1}'),'text':str(u.get('question') or ''),'kategorie':[]} for i,u in enumerate((existing_context or draft).get('uncertainties') or []) if str(u.get('status') or '')!='RESOLVED'] or questions
    if not questions:
        questions=[{'id':'CTX1','text':f'Dohledej relevantní tržní, konkurenční, cenový a značkový kontext pro: {draft.get("subject") or brief}','kategorie':[]}]
    topic=' | '.join(x for x in [draft.get('client'),draft.get('product_service'),draft.get('category'),draft.get('market'),draft.get('geography'),brief] if x)[:1800]
    from research_context import run_dual_research
    _progress('Simulace · dohledávám klienta, trh, ceny, konkurenci a mechanismy')
    bundle=run_dual_research({'enabled':True,'topic':topic,'anthropic_model':model,'max_sources_per_agent':max(3,min(12,int(max_sources))),
                              'strict_consensus':False,'allow_degraded_single_agent':True,'max_context_blocks':12},questions,
                             provider_override=provider,progress=_progress)
    evidence=_evidence_public(bundle)
    try:
        from data_library import knowledge_context_for_project
        library=knowledge_context_for_project(project or {'goal':brief,'briefing':{'product_description':brief}},limit=12)
    except Exception as exc:
        library={'dimensions':[],'count':0,'warning':str(exc)[:500]}
    _progress('Simulace · syntetizuji evidence a vytvářím akční registr nejistot')
    synth_payload={'raw_brief':brief,'draft':draft,'previous_context':existing_context or {},'web_evidence':evidence,'data_library':library,'unresolved_only':bool(unresolved_only)}
    sr=call_structured(system=_SYNTHESIS_SYSTEM,messages=[{'role':'user','content':json.dumps(synth_payload,ensure_ascii=False,default=str)}],
                       schema=_context_schema(),schema_name='npc_simulation_context_synthesis',anthropic_model=effective_model,max_tokens=6500,
                       prefer=provider,allow_fallback=False,timeout=420)
    context=_coerce_context(sr.get('data') or {})
    # Manual user assumptions are authoritative inputs, not disposable model prose.
    # A later research pass may replace them only when it actually RESOLVES the same
    # uncertainty with evidence. Otherwise keep the user's explicit answer intact.
    if unresolved_only and existing_context:
        new_unc=list(context.get('uncertainties') or [])
        def _ukey(u):
            return (str((u or {}).get('id') or '').strip().lower(), str((u or {}).get('question') or '').strip().lower())
        pos={_ukey(u):i for i,u in enumerate(new_unc)}
        for old_u in (existing_context.get('uncertainties') or []):
            if not isinstance(old_u,dict) or str(old_u.get('status') or '')!='ASSUMPTION' or not str(old_u.get('answer') or '').strip():
                continue
            key=_ukey(old_u); i=pos.get(key)
            if i is not None and str((new_unc[i] or {}).get('status') or '')=='RESOLVED':
                continue
            kept=deepcopy(old_u); kept['recommended_action']='keep_assumption'
            if i is None:
                new_unc.append(kept); pos[key]=len(new_unc)-1
            else:
                new_unc[i]=kept
        context['uncertainties']=new_unc[:30]
    # Preserve original brief as an audit fact, never overwrite it with research prose.
    context['_meta']={'created_at':_now(),'provider':sr.get('provider') or provider,'model':sr.get('model') or effective_model,
                      'raw_brief':brief,'mode':'uncertainty_resolution' if unresolved_only else 'standalone_enrichment',
                      'evidence_sha256':evidence.get('sha256'),'data_library_count':library.get('count',0)}
    context['evidence']=evidence
    context['data_library']=library
    context['sha256']=_sha({k:v for k,v in context.items() if k!='sha256'})
    return context


def resolve_simulation_uncertainties(context: dict[str,Any], *, raw_brief: str='', project:dict[str,Any]|None=None,
                                     model:str='sonnet',provider:str|None=None,max_sources:int=8,progress=None)->dict[str,Any]:
    return enrich_simulation_context(raw_brief or str((context or {}).get('_meta',{}).get('raw_brief') or (context or {}).get('summary') or ''),
                                     project=project,existing_context=context,unresolved_only=True,model=model,provider=provider,max_sources=max_sources,progress=progress,deep_research=True)
