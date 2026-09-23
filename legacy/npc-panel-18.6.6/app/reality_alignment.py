from __future__ import annotations
import csv, hashlib, html, json, time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 'npc_ai_panel_calibration/v1'

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def _schema()->dict[str,Any]:
    evidence={'type':'object','properties':{
        'topic':{'type':'string'},'npc_result':{'type':'string'},'external_context':{'type':'string'},
        'assessment':{'type':'string'},'confidence':{'type':'string','enum':['high','medium','low']},
        'evidence_refs':{'type':'array','items':{'type':'string'}}},
        'required':['topic','npc_result','external_context','assessment','confidence','evidence_refs'],'additionalProperties':False}
    tension={'type':'object','properties':{
        'topic':{'type':'string'},'npc_result':{'type':'string'},'external_context':{'type':'string'},'gap':{'type':'string'},
        'likely_causes':{'type':'array','items':{'type':'string'}},'what_to_change':{'type':'string'},
        'priority':{'type':'string','enum':['high','medium','low']},'evidence_refs':{'type':'array','items':{'type':'string'}}},
        'required':['topic','npc_result','external_context','gap','likely_causes','what_to_change','priority','evidence_refs'],'additionalProperties':False}
    plan={'type':'object','properties':{
        'priority':{'type':'integer','minimum':1,'maximum':20},'action':{'type':'string'},'why':{'type':'string'},
        'expected_effect':{'type':'string'},'evidence_basis':{'type':'array','items':{'type':'string'}}},
        'required':['priority','action','why','expected_effect','evidence_basis'],'additionalProperties':False}
    rule={'type':'object','properties':{
        'rule_id':{'type':'string'},'title':{'type':'string'},'question_ids':{'type':'array','items':{'type':'string'}},
        'topics':{'type':'array','items':{'type':'string'}},'segments':{'type':'array','items':{'type':'string'}},
        'anchor_type':{'type':'string','enum':['directional','distribution','mean','ranking','context_prior']},
        'target_anchor':{'type':'string'},'strength':{'type':'number','minimum':0,'maximum':0.35},
        'evidence_strength':{'type':'string','enum':['strong','moderate','weak']},'rationale':{'type':'string'},
        'expected_effect':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}}},
        'required':['rule_id','title','question_ids','topics','segments','anchor_type','target_anchor','strength','evidence_strength','rationale','expected_effect','evidence_refs'],'additionalProperties':False}
    return {'type':'object','properties':{
        'overall_alignment_score':{'type':'integer','minimum':0,'maximum':100},'verdict':{'type':'string'},
        'what_matches':{'type':'array','items':evidence},'what_does_not_match':{'type':'array','items':tension},
        'missing_evidence':{'type':'array','items':{'type':'string'}},'ten_out_of_ten_plan':{'type':'array','items':plan},
        'calibration_candidates':{'type':'array','items':rule},'closing_conclusion':{'type':'string'}},
        'required':['overall_alignment_score','verdict','what_matches','what_does_not_match','missing_evidence','ten_out_of_ten_plan','calibration_candidates','closing_conclusion'],'additionalProperties':False}

def compare(project:dict[str,Any], summary:dict[str,Any], analysis:dict[str,Any], research:dict[str,Any], verification:dict[str,Any], *, provider_override:str|None=None)->dict[str,Any]:
    from provider_auth import get_ai_provider, normalize_ai_provider
    from ai_router import call_structured
    provider=normalize_ai_provider(provider_override or (project.get('run_policy') or {}).get('provider') or get_ai_provider())
    background=[{'claim':x.get('claim'),'title':x.get('source_title'),'url':x.get('source_url'),'confidence':x.get('merge_confidence')} for x in (research or {}).get('accepted') or []][:20]
    validation=[{'target_id':x.get('target_id'),'claim':x.get('claim_summary'),'direction':x.get('direction'),'directness':x.get('directness'),'title':x.get('source_title'),'url':x.get('source_url')} for x in (verification or {}).get('findings') or []][:40]
    payload={
      'project':{'title':project.get('title'),'goal':project.get('goal'),'research_questions':(project.get('research_plan') or {}).get('research_questions') or (project.get('research_plan') or {}).get('objectives') or [project.get('goal')], 'audience':project.get('audience')},
      'initial_research':background,'analysis':analysis,'post_result_validation':validation,
      'result_summary':{'n':summary.get('n'),'run_status':summary.get('run_status'),'donor_support':summary.get('donor_support'),'results':summary.get('vysledky')},
      'calibration_contract':{
        'standard_panel_must_remain_unchanged':True,
        'rules_are_for_separate_ai_panel_mode_only':True,
        'do_not_change_demographic_facts':True,
        'do_not_invent_exact_targets_without_external_evidence':True,
        'max_rule_strength':0.35,
        'weak_evidence_rules_should_not_be_enabled':True,
      }
    }
    system=("Jsi senior metodolog, research director a calibration reviewer. Porovnej počáteční externí research, skutečné výsledky NPC, analytické závěry a post-result validaci. "
            "Neobhajuj model. Jasně napiš co sedí, co nesedí, jak velký je problém a co bys upravil, aby další běh lépe odpovídal dostupné realitě. "
            "Navrhni praktický plán '10/10'. Kalibrační kandidáty navrhuj pouze tam, kde existuje evidence; nikdy neměň demografická/faktická pole. "
            "Kalibrace je měkký prior pro samostatný AI Panel, ne přepis původního výsledku. Sílu drž konzervativně <=0.35. Piš česky, konkrétně, klientsky a bez zbytečných disclaimerů.")
    rr=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],schema=_schema(),schema_name='npc_reality_alignment',anthropic_model='sonnet',max_tokens=7500,prefer=provider,allow_fallback=False)
    data=rr.get('data') or {}
    data['_meta']={'created_at':_now(),'provider':rr.get('provider') or provider,'model':rr.get('model'),'api_cost_usd':0.0 if provider=='claude_code_subscription' else None}
    return data

def build_calibration_profile(alignment:dict[str,Any], *, project:dict[str,Any], workflow_id:str)->dict[str,Any]:
    rules=[]
    for i,r in enumerate(alignment.get('calibration_candidates') or [],1):
        strength=max(0.0,min(0.35,float(r.get('strength') or 0)))
        ev=str(r.get('evidence_strength') or 'weak').lower()
        enabled=ev in {'strong','moderate'} and strength>0
        rid=str(r.get('rule_id') or f'R{i}')
        rules.append({
          'rule_id':rid,'enabled':enabled,'title':r.get('title') or rid,
          'scope':{'question_ids':list(r.get('question_ids') or [])[:30],'topics':list(r.get('topics') or [])[:20],'segments':list(r.get('segments') or [])[:20]},
          'anchor':{'type':r.get('anchor_type') or 'context_prior','target':r.get('target_anchor') or ''},
          'strength':strength,'evidence_strength':ev,'rationale':r.get('rationale') or '',
          'expected_effect':r.get('expected_effect') or '','evidence_refs':list(r.get('evidence_refs') or [])[:30],
        })
    base={'schema':SCHEMA_VERSION,'profile_id':'','created_at':_now(),'source_workflow_id':workflow_id,
          'source_project_title':project.get('title'),'alignment_score':alignment.get('overall_alignment_score'),
          'rules':rules,'application':{'mode':'soft_prior','preserve_measured_facts':True,'preserve_demographics':True,'max_strength':0.35}}
    raw=json.dumps({k:v for k,v in base.items() if k!='profile_id'},ensure_ascii=False,sort_keys=True,default=str).encode('utf-8')
    base['profile_id']='AIP-'+hashlib.sha256(raw).hexdigest()[:12]
    return base

def export_profile(profile:dict[str,Any], json_path:str|Path, csv_path:str|Path)->tuple[str,str]:
    jp=Path(json_path);cp=Path(csv_path);jp.parent.mkdir(parents=True,exist_ok=True)
    jp.write_text(json.dumps(profile,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    with cp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['rule_id','enabled','title','question_ids','topics','segments','anchor_type','target_anchor','strength','evidence_strength','rationale','expected_effect','evidence_refs'])
        w.writeheader()
        for r in profile.get('rules') or []:
            s=r.get('scope') or {};a=r.get('anchor') or {}
            w.writerow({'rule_id':r.get('rule_id'),'enabled':r.get('enabled'),'title':r.get('title'),'question_ids':'|'.join(s.get('question_ids') or []),'topics':'|'.join(s.get('topics') or []),'segments':'|'.join(s.get('segments') or []),'anchor_type':a.get('type'),'target_anchor':a.get('target'),'strength':r.get('strength'),'evidence_strength':r.get('evidence_strength'),'rationale':r.get('rationale'),'expected_effect':r.get('expected_effect'),'evidence_refs':'|'.join(r.get('evidence_refs') or [])})
    return str(jp),str(cp)

def calibration_text(profile:dict[str,Any]|None, *, question_id:str, topics:list[str]|None=None)->str:
    if not profile or profile.get('schema')!=SCHEMA_VERSION:return ''
    tset={str(x).strip().lower() for x in (topics or []) if str(x).strip()}
    rows=[]
    for r in profile.get('rules') or []:
        if not r.get('enabled'): continue
        scope=r.get('scope') or {};qids={str(x) for x in scope.get('question_ids') or []};rt={str(x).strip().lower() for x in scope.get('topics') or []}
        if qids and question_id not in qids: continue
        if rt and tset and not (rt&tset): continue
        strength=max(0.0,min(.35,float(r.get('strength') or 0)))
        if strength<=0: continue
        rows.append(f"- {r.get('title')}: {((r.get('anchor') or {}).get('target') or '')} (soft prior strength={strength:.2f}; evidence={r.get('evidence_strength')})")
    if not rows:return ''
    return "AI PANEL KALIBRAČNÍ PRIOR — pouze měkký skupinový prior, nikoli fakt o jednotlivci. Zachovej pevná fakta persony a nepřepisuj je.\n"+'\n'.join(rows[:6])

def export_alignment_html(path:str|Path, project:dict[str,Any], alignment:dict[str,Any], profile:dict[str,Any])->str:
    e=lambda x:html.escape(str(x or ''));p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    yes=''.join(f"<div class='card good'><h3>{e(x.get('topic'))}</h3><p><b>NPC:</b> {e(x.get('npc_result'))}</p><p><b>Externí kontext:</b> {e(x.get('external_context'))}</p><p>{e(x.get('assessment'))}</p></div>" for x in alignment.get('what_matches') or [])
    no=''.join(f"<div class='card warn'><h3>{e(x.get('topic'))}</h3><p><b>Rozdíl:</b> {e(x.get('gap'))}</p><p><b>Co změnit:</b> {e(x.get('what_to_change'))}</p><p class='mut'>{e(' · '.join(x.get('likely_causes') or []))}</p></div>" for x in alignment.get('what_does_not_match') or [])
    plan=''.join(f"<li><b>{e(x.get('action'))}</b> — {e(x.get('why'))}<br><span class='mut'>Očekávaný efekt: {e(x.get('expected_effect'))}</span></li>" for x in sorted(alignment.get('ten_out_of_ten_plan') or [],key=lambda x:x.get('priority') or 99))
    rules=''.join(f"<tr><td>{e(r.get('title'))}</td><td>{e((r.get('anchor') or {}).get('target'))}</td><td>{e(r.get('strength'))}</td><td>{e(r.get('evidence_strength'))}</td><td>{'ANO' if r.get('enabled') else 'NE'}</td></tr>" for r in profile.get('rules') or [])
    body=f'''<!doctype html><meta charset="utf-8"><title>Reality Alignment</title><style>body{{font:15px/1.55 Inter,Segoe UI,Arial,sans-serif;background:#f4f6f8;color:#17202a;margin:0}}main{{max-width:1080px;margin:auto;background:white;min-height:100vh;padding:48px 60px}}h1{{font-size:36px}}h2{{margin-top:34px;border-top:1px solid #e4e7eb;padding-top:22px}}.score{{font-size:52px;font-weight:800}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.card{{border:1px solid #e0e4e8;border-radius:14px;padding:16px}}.good{{background:#f0f8f3}}.warn{{background:#fff6e5}}.mut{{color:#667085}}table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}</style><main><div class="mut">NPC Panel · Reality Alignment</div><h1>{e(project.get('title'))}</h1><div class="score">{e(alignment.get('overall_alignment_score'))}/100</div><p style="font-size:20px"><b>{e(alignment.get('verdict'))}</b></p><h2>Co sedí</h2><div class="grid">{yes or '<div class="card">Bez potvrzených shod.</div>'}</div><h2>Co nesedí a co bych upravil</h2><div class="grid">{no or '<div class="card">Bez identifikovaných zásadních rozporů.</div>'}</div><h2>Jak to posunout na 10/10</h2><ol>{plan}</ol><h2>AI Panel · navržená kalibrace</h2><p>Kalibrace se aplikuje pouze v samostatném režimu AI Panel a nemění původní Standard Panel.</p><table><tr><th>Pravidlo</th><th>Prior / cíl</th><th>Síla</th><th>Evidence</th><th>Aktivní</th></tr>{rules}</table><h2>Závěr</h2><p style="font-size:20px">{e(alignment.get('closing_conclusion'))}</p></main>'''
    p.write_text(body,encoding='utf-8');return str(p)
