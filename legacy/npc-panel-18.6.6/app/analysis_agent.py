from __future__ import annotations
import json, math, time
from pathlib import Path
from typing import Any
from research_project import compile_project


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _research_questions(project:dict[str,Any])->list[str]:
    rp=project.get('research_plan') or {}
    qs=[]
    explicit=rp.get('research_questions') or []
    for x in explicit:
        if str(x).strip(): qs.append(str(x).strip())
    if not qs:
        for x in rp.get('objectives') or []:
            if str(x).strip(): qs.append(str(x).strip())
    if not qs and str(project.get('goal') or '').strip(): qs=[str(project['goal']).strip()]
    return qs[:8]


def _evidence_table(project:dict[str,Any], summary:dict[str,Any])->list[dict[str,Any]]:
    compiled=compile_project(project)
    qby={q['id']:q for q in compiled['brief'].get('otazky') or []}
    out=[]
    for qid,r in (summary.get('vysledky') or {}).items():
        if not isinstance(r,dict): continue
        q=qby.get(qid) or {}
        row={'question_id':qid,'question_text':q.get('text') or qid,'type':q.get('typ')}
        if isinstance(r.get('celkem_pct'),dict):
            vals=[]
            for k,v in r['celkem_pct'].items():
                try: vals.append({'answer':str(k),'pct':round(float(v),3)})
                except Exception: pass
            row['distribution']=vals
        if r.get('prumer') is not None:
            try: row['mean']=round(float(r['prumer']),4)
            except Exception: pass
        if r.get('top2box_pct') is not None:
            try: row['top2box_pct']=round(float(r['top2box_pct']),3)
            except Exception: pass
        # Preserve any subgroup/crosstab payloads already computed by the engine, bounded.
        for key in ('segmenty','subgroups','by_segment','cross_tabs'):
            if key in r: row[key]=r[key]
        out.append(row)
    return out[:80]


def _schema()->dict[str,Any]:
    nc={'type':'object','properties':{'evidence_ref':{'type':'string'},'metric':{'type':'string'},'value':{'type':'number'},'unit':{'type':'string'},'label':{'type':'string'}},'required':['evidence_ref','metric','value','unit','label'],'additionalProperties':False}
    return {'type':'object','properties':{
      'executive_answer':{'type':'string'},
      'research_question_answers':{'type':'array','items':{'type':'object','properties':{'question':{'type':'string'},'answer':{'type':'string'},'evidence_strength':{'type':'string','enum':['strong','moderate','weak','insufficient']},'evidence_refs':{'type':'array','items':{'type':'string'}},'numeric_claims':{'type':'array','items':nc},'why':{'type':'string'}},'required':['question','answer','evidence_strength','evidence_refs','numeric_claims','why'],'additionalProperties':False}},
      'key_findings':{'type':'array','items':{'type':'object','properties':{'headline':{'type':'string'},'finding':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}},'numeric_claims':{'type':'array','items':nc},'numbers':{'type':'array','items':{'type':'string'}},'who_differs':{'type':'string'},'meaning':{'type':'string'},'confidence':{'type':'string','enum':['high','medium','low']}},'required':['headline','finding','evidence_refs','numeric_claims','numbers','who_differs','meaning','confidence'],'additionalProperties':False}},
      'segment_story':{'type':'array','items':{'type':'object','properties':{'segment':{'type':'string'},'description':{'type':'string'},'difference':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}}},'required':['segment','description','difference','evidence_refs'],'additionalProperties':False}},
      'implications':{'type':'array','items':{'type':'object','properties':{'action':{'type':'string'},'rationale':{'type':'string'},'priority':{'type':'string','enum':['high','medium','low']},'evidence_refs':{'type':'array','items':{'type':'string'}}},'required':['action','rationale','priority','evidence_refs'],'additionalProperties':False}},
      'surprises':{'type':'array','items':{'type':'string'}},'confidence_summary':{'type':'string'},'limitations':{'type':'array','items':{'type':'string'}},'next_questions':{'type':'array','items':{'type':'string'}}},
      'required':['executive_answer','research_question_answers','key_findings','segment_story','implications','surprises','confidence_summary','limitations','next_questions'],'additionalProperties':False}


def analyze_results(project:dict[str,Any], result_summary:dict[str,Any], *, research_bundle:dict[str,Any]|None=None, donor_support:dict[str,Any]|None=None, battery_results:list[dict[str,Any]]|None=None, provider_override:str|None=None, model_override:str|None=None, checkpoint_dir:str|Path|None=None, cost_mode:str|None=None)->dict[str,Any]:
    from provider_auth import get_ai_provider, normalize_ai_provider
    from ai_router import call_structured
    from evidence_validator import validate_analysis
    provider=normalize_ai_provider(provider_override or (project.get('run_policy') or {}).get('provider') or get_ai_provider());model=str(model_override or project.get('model') or 'sonnet');cm=str(cost_mode or (project.get('run_policy') or {}).get('cost_mode') or 'REFERENCE').upper();evidence=_evidence_table(project,result_summary);rqs=_research_questions(project);context=[{'claim':x.get('claim'),'source_title':x.get('source_title'),'source_url':x.get('source_url'),'topics':x.get('topics'),'confidence':x.get('merge_confidence')} for x in (research_bundle or {}).get('accepted') or []];batteries=[]
    for b in battery_results or []:
        if isinstance(b,dict) and not b.get('error'):batteries.append({'evidence_ref':'battery:'+str(b.get('id') or ''),'id':b.get('id'),'title':b.get('title'),'object_ranking':(b.get('object_ranking') or [])[:15],'nearest_pairs':(b.get('nearest_pairs') or [])[:12],'map_metrics':b.get('map_metrics') or {}})
    payload={'project':{'title':project.get('title'),'goal':project.get('goal'),'decision_use':project.get('decision_use'),'research_questions':rqs},'survey_evidence':evidence,'relational_batteries':batteries,'donor_support':donor_support or result_summary.get('donor_support') or {},'background_context':context[:20],'method_status':'synthetic/modelled research; external predictive certification pending'}
    system='Jsi senior research director. Odpověz na research questions, nepopisuj jen tabulky. Každé číslo v research_question_answers a key_findings musí být v numeric_claims s evidence_ref, metric (mean, top2box_pct, n, effective_n nebo pct:<přesná odpověď>), value a unit. Hodnoty přesně opisuj z evidence. Externí research je jen kontext. Nevymýšlej segmenty ani kauzalitu.'
    cp=Path(checkpoint_dir) if checkpoint_dir else None
    if cp:cp.mkdir(parents=True,exist_ok=True)
    draftp=cp/'analysis_draft.json' if cp else None;draft=json.loads(draftp.read_text(encoding='utf-8')) if draftp and draftp.exists() else None;rr={}
    if draft is None:
        rr=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],schema=_schema(),schema_name='npc_client_analysis',anthropic_model=model,openai_model=model if provider=='openai' else None,max_tokens=7000,prefer=provider,allow_fallback=False);draft=rr.get('data') or {}
        if draftp:draftp.write_text(json.dumps(draft,ensure_ascii=False,indent=2),encoding='utf-8')
    data=draft
    if cm!='ECONOMY':
        finalp=cp/'analysis_final.json' if cp else None
        if finalp and finalp.exists():data=json.loads(finalp.read_text(encoding='utf-8'))
        else:
            rr2=call_structured(system=system+' Jsi challenger a senior editor. Odstraň unsupported claims a vrať kompletní opravenou analýzu se stejným schématem.',messages=[{'role':'user','content':json.dumps({**payload,'draft_analysis':draft},ensure_ascii=False,default=str)}],schema=_schema(),schema_name='npc_client_analysis_challenged',anthropic_model=model,openai_model=model if provider=='openai' else None,max_tokens=7000,prefer=provider,allow_fallback=False);data=rr2.get('data') or draft;rr=rr2
            if finalp:finalp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    ev=validate_analysis(data,result_summary,battery_results)
    # NPC AI RUNTIME FIX: evidence gate ted opravuje, misto aby zabil cely beh.
    # Chyby validace jdou zpet modelu jako konkretni zadani na opravu.
    _repairs=0
    while not ev.get('passed') and _repairs<2:
        _repairs+=1
        _sys=system+(' Predchozi verze neprosla evidence gate. Oprav VSECHNY uvedene problemy:'
                     ' kazde cislo musi mit evidence_ref z evidence tabulky, metric z povolene sady'
                     ' (mean, top2box_pct, n, effective_n, pct:<presna odpoved>) a value presne'
                     ' opsanou z evidence. Vrat kompletni opravenou analyzu ve stejnem schematu.')
        _pl={**payload,'previous_analysis':data,
             'validation_issues':(ev.get('issues') or [])[:60],
             'failed_checks':[c for c in (ev.get('checks') or []) if not c.get('ok')][:60]}
        try:
            _rr=call_structured(system=_sys,messages=[{'role':'user','content':json.dumps(_pl,ensure_ascii=False,default=str)}],
                                schema=_schema(),schema_name='npc_client_analysis_repair',anthropic_model=model,
                                openai_model=model if provider=='openai' else None,max_tokens=7000,
                                prefer=provider,allow_fallback=False)
        except Exception:
            break
        _new=_rr.get('data') or {}
        if not _new:
            break
        _ev2=validate_analysis(_new,result_summary,battery_results)
        if float(_ev2.get('score') or 0)>=float(ev.get('score') or 0):
            data,ev,rr=_new,_ev2,_rr
            if cp:
                try:
                    (cp/'analysis_final.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
                except Exception:
                    pass
        if ev.get('passed'):
            break
    data['_meta']={'created_at':_now(),'provider':rr.get('provider') or provider,'model':rr.get('model') or model,'research_questions':rqs,'evidence_question_ids':[x['question_id'] for x in evidence],'battery_evidence_ids':[x['evidence_ref'] for x in batteries],'background_sources':len(context),'evidence_validation':ev,'analysis_passes':1 if cm=='ECONOMY' else 2}
    data['_meta']['gate_repairs']=_repairs
    if not ev.get('passed'):raise RuntimeError('ANALYSIS_EVIDENCE_GATE_FAILED (po %d opravnych pruchodech): '%_repairs+json.dumps(ev,ensure_ascii=False)[:5000])
    return data
# 17.9.0 persistent modular analysis -------------------------------------------------
MODULE_ORDER=('executive','research_questions','objects','audience','segments','hypotheses','implications','limitations')

def _module_schema(module:str)->dict[str,Any]:
    full=_schema(); props=full['properties']; module=str(module)
    fields={
      'executive':['executive_answer','confidence_summary'],
      'research_questions':['research_question_answers'],
      'objects':['key_findings'],
      'segments':['segment_story'],
      'hypotheses':['surprises','next_questions'],
      'implications':['implications'],
      'limitations':['limitations'],
    }
    if module=='audience':
        return {'type':'object','properties':{'audience_analysis':{'type':'string'}},'required':['audience_analysis'],'additionalProperties':False}
    fs=fields.get(module)
    if not fs: raise ValueError(f'Unknown analysis module: {module}')
    return {'type':'object','properties':{k:props[k] for k in fs},'required':fs,'additionalProperties':False}

def _module_payload(project:dict[str,Any], result_summary:dict[str,Any], *, research_bundle=None, donor_support=None, battery_results=None)->dict[str,Any]:
    evidence=_evidence_table(project,result_summary);rqs=_research_questions(project)
    context=[{'claim':x.get('claim'),'source_title':x.get('source_title'),'source_url':x.get('source_url'),'topics':x.get('topics'),'confidence':x.get('merge_confidence')} for x in (research_bundle or {}).get('accepted') or []]
    batteries=[]
    for b in battery_results or []:
        if isinstance(b,dict) and not b.get('error'):
            batteries.append({'evidence_ref':'battery:'+str(b.get('id') or ''),'id':b.get('id'),'title':b.get('title'),'object_ranking':(b.get('object_ranking') or [])[:15],'nearest_pairs':(b.get('nearest_pairs') or [])[:12],'map_metrics':b.get('map_metrics') or {}})
    return {'project':{'title':project.get('title'),'goal':project.get('goal'),'decision_use':project.get('decision_use'),'research_questions':rqs,'audience':project.get('audience')},
            'survey_evidence':evidence,'relational_batteries':batteries,'donor_support':donor_support or result_summary.get('donor_support') or {},
            'background_context':context[:20],'method_status':'synthetic/modelled research; external predictive certification pending'}

def analyze_module(module:str, project:dict[str,Any], result_summary:dict[str,Any], *, research_bundle=None, donor_support=None,
                   battery_results=None, provider_override=None, model_override=None)->dict[str,Any]:
    """Run exactly one durable analysis module.

    Each module is independently fingerprinted by the workflow and may be resumed or
    provider-switched without repeating already completed modules.
    """
    from provider_auth import get_ai_provider, normalize_ai_provider
    from ai_router import call_structured
    module=str(module); schema=_module_schema(module)
    provider=normalize_ai_provider(provider_override or (project.get('run_policy') or {}).get('provider') or get_ai_provider())
    model=str(model_override or project.get('model') or 'sonnet')
    payload=_module_payload(project,result_summary,research_bundle=research_bundle,donor_support=donor_support,battery_results=battery_results)
    instructions={
      'executive':'Napiš stručnou odpověď pro rozhodnutí a transparentní confidence summary. Nevymýšlej čísla.',
      'research_questions':'Odpověz jednotlivě na výzkumné otázky. Každé číslo musí mít numeric_claim s přesným evidence_ref a metric.',
      'objects':'Vyber klíčová zjištění o sledovaných objektech. Číselná tvrzení odkaž přes numeric_claims na survey evidence.',
      'audience':'Popiš pouze rozdíly a charakter cílové skupiny, které jsou opřené o dodané výsledky. Bez kauzálních tvrzení.',
      'segments':'Popiš validní segmentové rozdíly. Nevytvářej segmenty, které ve výsledcích nejsou.',
      'hypotheses':'Uveď překvapení a další ověřitelné otázky. Hypotézy jasně odděl od naměřených/modelovaných zjištění.',
      'implications':'Navrhni praktické implikace s prioritou a evidence refs; nepřekračuj sílu evidence.',
      'limitations':'Sepiš metodické limity, nejistoty a co nelze z výsledků tvrdit.',
    }
    system=('Jsi senior research director. Pracuješ jen na jednom modulu analýzy. '+instructions[module]+
            ' Externí research je pouze kontext. Nevymýšlej data, segmenty ani kauzalitu. Vrať pouze požadované strukturované pole/pole.')
    rr=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],
                       schema=schema,schema_name='npc_analysis_'+module,anthropic_model=model,
                       openai_model=None,max_tokens=2800,prefer=provider,allow_fallback=False)
    data=rr.get('data') or {}
    return {'module':module,'content':data,'provider':rr.get('provider') or provider,'model':rr.get('model') or model,
            'tok_in':int(rr.get('tok_in') or 0),'tok_out':int(rr.get('tok_out') or 0),'created_at':_now()}

def assemble_modules(modules:dict[str,dict[str,Any]], project:dict[str,Any], result_summary:dict[str,Any], *, battery_results=None)->dict[str,Any]:
    """Deterministically compose module artifacts into the legacy analysis contract."""
    def content(name):
        x=modules.get(name) or {}; return x.get('content') if isinstance(x.get('content'),dict) else x
    ex=content('executive');rq=content('research_questions');ob=content('objects');au=content('audience');se=content('segments');hy=content('hypotheses');im=content('implications');li=content('limitations')
    data={
      'executive_answer':ex.get('executive_answer') or '',
      'research_question_answers':rq.get('research_question_answers') or [],
      'key_findings':ob.get('key_findings') or [],
      'segment_story':se.get('segment_story') or [],
      'implications':im.get('implications') or [],
      'surprises':hy.get('surprises') or [],
      'confidence_summary':ex.get('confidence_summary') or '',
      'limitations':li.get('limitations') or [],
      'next_questions':hy.get('next_questions') or [],
    }
    from evidence_validator import validate_analysis
    ev=validate_analysis(data,result_summary,battery_results)
    providers=[];models=[]
    for m in MODULE_ORDER:
        x=modules.get(m) or {}
        if x.get('provider'):providers.append(x.get('provider'))
        if x.get('model'):models.append(x.get('model'))
    data['_modules']={'audience':au.get('audience_analysis') or '', 'completed':list(modules.keys())}
    data['_meta']={'created_at':_now(),'provider':'mixed' if len(set(providers))>1 else (providers[-1] if providers else None),
                   'model':'mixed' if len(set(models))>1 else (models[-1] if models else None),'evidence_validation':ev,
                   'analysis_mode':'PERSISTENT_MODULES_V1','module_count':len(modules),'module_order':list(MODULE_ORDER)}
    if not ev.get('passed'):
        raise RuntimeError('ANALYSIS_EVIDENCE_GATE_FAILED_MODULE_ASSEMBLY: '+json.dumps(ev,ensure_ascii=False)[:5000])
    return data

