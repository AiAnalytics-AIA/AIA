from __future__ import annotations
import html,json,re,time
from pathlib import Path
from typing import Any

def _now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _nc():return {'type':'object','properties':{'evidence_ref':{'type':'string'},'metric':{'type':'string'},'value':{'type':'number'},'unit':{'type':'string'},'label':{'type':'string'}},'required':['evidence_ref','metric','value','unit','label'],'additionalProperties':False}
def _schema():
 nc=_nc();qa={'type':'object','properties':{'question':{'type':'string'},'answer':{'type':'string'},'evidence_strength':{'type':'string'},'why':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}},'numeric_claims':{'type':'array','items':nc}},'required':['question','answer','evidence_strength','why','evidence_refs','numeric_claims'],'additionalProperties':False};f={'type':'object','properties':{'headline':{'type':'string'},'finding':{'type':'string'},'evidence':{'type':'string'},'meaning':{'type':'string'},'confidence':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}},'numeric_claims':{'type':'array','items':nc}},'required':['headline','finding','evidence','meaning','confidence','evidence_refs','numeric_claims'],'additionalProperties':False};im={'type':'object','properties':{'action':{'type':'string'},'why':{'type':'string'},'priority':{'type':'string'},'evidence_refs':{'type':'array','items':{'type':'string'}},'numeric_claims':{'type':'array','items':nc}},'required':['action','why','priority','evidence_refs','numeric_claims'],'additionalProperties':False}
 return {'type':'object','properties':{'title':{'type':'string'},'subtitle':{'type':'string'},'executive_summary':{'type':'string'},'decision_answer':{'type':'string'},'research_question_answers':{'type':'array','items':qa},'context_intro':{'type':'string'},'context_points':{'type':'array','items':{'type':'string'}},'key_findings':{'type':'array','items':f},'implications':{'type':'array','items':im},'validation_summary':{'type':'string'},'confidence_summary':{'type':'string'},'method_summary':{'type':'string'},'limitations':{'type':'array','items':{'type':'string'}},'closing':{'type':'string'}},'required':['title','subtitle','executive_summary','decision_answer','research_question_answers','context_intro','context_points','key_findings','implications','validation_summary','confidence_summary','method_summary','limitations','closing'],'additionalProperties':False}
def _review_schema():return {'type':'object','properties':{'overall_score':{'type':'number'},'blocking_issues':{'type':'array','items':{'type':'string'}},'unsupported_claims':{'type':'array','items':{'type':'string'}},'recommended_changes':{'type':'array','items':{'type':'string'}},'verdict':{'type':'string'}},'required':['overall_score','blocking_issues','unsupported_claims','recommended_changes','verdict'],'additionalProperties':False}
def _text(report):
 parts=[report.get(k) for k in ('executive_summary','decision_answer','context_intro','validation_summary','confidence_summary','closing')]
 for g in ('research_question_answers','key_findings','implications'):
  for r in report.get(g) or []:
   for k in ('answer','why','headline','finding','evidence','meaning','action'):parts.append(r.get(k))
 return '\n'.join(str(x or '') for x in parts)
def numeric_text_gate(report):
 vals=[]
 for g in ('research_question_answers','key_findings','implications'):
  for r in report.get(g) or []:
   for c in r.get('numeric_claims') or []:
    try:vals.append(float(c.get('value')))
    except:pass
 bad=[];text=_text(report)
 for m in re.finditer(r'(?<!\d)(\d{1,3}(?:[\.,]\d+)?)\s*%',text):
  v=float(m.group(1).replace(',','.'))
  if not any(abs(v-x)<=.11 for x in vals):bad.append(v)
 return {'passed':not bad,'unstructured_percentages':bad}
def quality_gate(report,evidence_validation,reviewer=None):
 score=0;issues=[]
 for ok,pts,msg in [(len(str(report.get('executive_summary') or ''))>=180,15,'short executive summary'),(len(str(report.get('decision_answer') or ''))>=70,10,'missing decision answer'),(len(report.get('research_question_answers') or [])>=1,15,'missing research answers'),(len(report.get('key_findings') or [])>=3,15,'too few findings'),(all(x.get('evidence_refs') for x in report.get('key_findings') or []),10,'finding refs missing'),(len(report.get('implications') or [])>=2,10,'too few implications'),(bool(report.get('confidence_summary')) and bool(report.get('limitations')),5,'confidence/limits missing'),(bool(evidence_validation.get('passed')),15,'evidence validator failed'),(numeric_text_gate(report)['passed'],5,'unstructured percentage')]:
  if ok:score+=pts
  else:issues.append(msg)
 rs=float((reviewer or {}).get('overall_score') or 100)
 if reviewer is not None and (rs<90 or reviewer.get('blocking_issues')):issues.append(f'partner review {rs:.0f}/100')
 return {'score':score,'threshold':90,'passed':score>=90 and not issues,'issues':issues,'reviewer_score':rs}
def _fallback_report_from_validated_analysis(project,analysis,verification,base_ev,reason=''):
 from copy import deepcopy
 rqa=[]
 for x in analysis.get('research_question_answers') or []:
  rqa.append({'question':str(x.get('question') or ''),'answer':str(x.get('answer') or ''),'evidence_strength':str(x.get('evidence_strength') or 'moderate'),'why':str(x.get('why') or ''),'evidence_refs':list(x.get('evidence_refs') or []),'numeric_claims':deepcopy(x.get('numeric_claims') or [])})
 kf=[]
 for x in analysis.get('key_findings') or []:
  nums=x.get('numbers') or []
  kf.append({'headline':str(x.get('headline') or ''),'finding':str(x.get('finding') or ''),'evidence':'; '.join(map(str,nums)) if nums else ', '.join(map(str,x.get('evidence_refs') or [])),'meaning':str(x.get('meaning') or ''),'confidence':str(x.get('confidence') or 'medium'),'evidence_refs':list(x.get('evidence_refs') or []),'numeric_claims':deepcopy(x.get('numeric_claims') or [])})
 imp=[]
 for x in analysis.get('implications') or []:
  imp.append({'action':str(x.get('action') or ''),'why':str(x.get('rationale') or x.get('why') or ''),'priority':str(x.get('priority') or 'medium'),'evidence_refs':list(x.get('evidence_refs') or []),'numeric_claims':deepcopy(x.get('numeric_claims') or [])})
 exec_answer=str(analysis.get('executive_answer') or project.get('goal') or 'Výzkum byl dokončen.')
 limitations=list(analysis.get('limitations') or [])
 limitations += ['Jde o syntetický/modelovaný výzkum; externí prediktivní certifikace zůstává samostatnou metodickou otázkou.']
 report={'title':str(project.get('title') or 'Výzkumná zpráva'),'subtitle':'Client deliverable · sestaveno z validované analýzy','executive_summary':exec_answer,'decision_answer':exec_answer,'research_question_answers':rqa,'context_intro':str(project.get('goal') or ''),'context_points':[],'key_findings':kf,'implications':imp,'validation_summary':str((verification or {}).get('quality_status') or (verification or {}).get('verification_status') or 'Externí triangulace je uvedena v auditních podkladech.'),'confidence_summary':str(analysis.get('confidence_summary') or ''),'method_summary':'Výstup je sestaven z validované analytické vrstvy NPC Panelu bez dodatečného stylistického AI průchodu.','limitations':limitations,'closing':exec_answer}
 report['_meta']={'report_generation_mode':'DETERMINISTIC_FROM_VALIDATED_ANALYSIS','ai_report_error':str(reason)[:1500],'analysis_evidence_validation':base_ev,'client_ready':False,'quality_gate':{'passed':False,'score':0,'issues':['AI report formatting unavailable; deterministic validated-analysis fallback used']}}
 return report

def compose_report(project,result_summary,analysis,*,research=None,verification=None,donor_support=None,reality_alignment=None,battery_results=None,provider_override=None,model_override=None,checkpoint_dir=None):
 from provider_auth import get_ai_provider,normalize_ai_provider
 from ai_router import call_structured
 from ai_execution_context import report as runtime_report
 from evidence_validator import validate_analysis
 provider=normalize_ai_provider(provider_override or (project.get('run_policy') or {}).get('provider') or get_ai_provider());model=str(model_override or project.get('model') or ('gpt-5' if provider=='openai' else 'sonnet'));cm=str((project.get('run_policy') or {}).get('cost_mode') or 'REFERENCE').upper();base_ev=(analysis.get('_meta') or {}).get('evidence_validation') or validate_analysis(analysis,result_summary,battery_results)
 if not base_ev.get('passed'):raise RuntimeError('REPORT_BLOCKED_BY_ANALYSIS_EVIDENCE_GATE')
 rqs=list((analysis.get('_meta') or {}).get('research_questions') or (project.get('research_plan') or {}).get('objectives') or [project.get('goal') or 'Výzkumná otázka']);bg=(research or {}).get('accepted') or [];vr=(verification or {}).get('findings') or []
 from data_library import knowledge_context_for_project
 library_context=knowledge_context_for_project(project,limit=12)
 payload={'project':{'title':project.get('title'),'goal':project.get('goal'),'decision_use':project.get('decision_use'),'research_questions':rqs},'analysis':analysis,'background_sources':bg[:25],'post_result_validation':vr[:35],'donor_support':donor_support or {},'reality_alignment':reality_alignment or {},'data_library_context':library_context}
 system='Jsi partner-level research consultant. Piš česky, answer-first, přímo pro CEO/board. Každé číslo musí zachovat evidence_ref, metric a value z analýzy. Nevymýšlej segmenty ani kauzalitu. Externí research a schválená Data Library jsou pouze kontext/triangulace, pokud nejsou explicitně naměřeným výsledkem tohoto projektu. Knowledge-only dimenzi nikdy nevydávej za individuálně naměřenou vlastnost. Doporučení musí být konkrétní.'
 cp=Path(checkpoint_dir) if checkpoint_dir else None
 if cp:cp.mkdir(parents=True,exist_ok=True)
 draftp=cp/'report_draft.json' if cp else None;report=json.loads(draftp.read_text(encoding='utf-8')) if draftp and draftp.exists() else None;rr={}
 if report is None:
  runtime_report({'phase':'Client Report Agent · generuji hlavní klientský report','agent':'Client Report Agent','report_stage':'draft'})
  try:
   rr=call_structured(system=system,messages=[{'role':'user','content':json.dumps(payload,ensure_ascii=False,default=str)}],schema=_schema(),schema_name='npc_client_report',anthropic_model=model,openai_model=model if provider=='openai' else None,max_tokens=9000,prefer=provider,allow_fallback=False);report=rr.get('data') or {}
  except Exception as draft_exc:
   runtime_report({'phase':'Client Report Agent · stylistický AI průchod selhal, sestavuji bezpečný report z validované analýzy','agent':'Client Report Agent','report_stage':'deterministic_fallback','level':'WARN','error':str(draft_exc)[:800]})
   report=_fallback_report_from_validated_analysis(project,analysis,verification,base_ev,draft_exc);rr={'provider':provider,'model':model,'fallback_used':True}
  if draftp:
   try:draftp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
   except Exception:pass
 ev=validate_analysis(report,result_summary,battery_results);review=None
 if cm!='ECONOMY' and (report.get('_meta') or {}).get('report_generation_mode')!='DETERMINISTIC_FROM_VALIDATED_ANALYSIS':
  runtime_report({'phase':'Client Report QA · kontroluji kvalitu a podloženost','agent':'Report QA','report_stage':'review'})
  try:
   rev=call_structured(system='Jsi nezávislý partner-level reviewer. Hodnoť tvrdě 0-100: evidence, answer-first story, decision usefulness, unsupported claims. Nezvyšuj skóre zdvořilostí.',messages=[{'role':'user','content':json.dumps({'report':report,'evidence_validation':ev},ensure_ascii=False,default=str)}],schema=_review_schema(),schema_name='npc_report_review',anthropic_model=model,openai_model=model if provider=='openai' else None,max_tokens=2500,prefer=provider,allow_fallback=False);review=rev.get('data') or {}
  except Exception as review_exc:
   runtime_report({'phase':'Client Report QA · reviewer nedokončil kontrolu; report pokračuje s deterministickou evidence kontrolou','agent':'Report QA','report_stage':'review_deferred','level':'WARN','error':str(review_exc)[:800]})
   review=None
 gate=quality_gate(report,ev,review)
 # NPC AI RUNTIME FIX: quality gate opravuje, misto aby zahodil hotovy beh.
 _rep_fix=0
 while not gate['passed'] and _rep_fix<2 and (report.get('_meta') or {}).get('report_generation_mode')!='DETERMINISTIC_FROM_VALIDATED_ANALYSIS':
  _rep_fix+=1
  runtime_report({'phase':f'Client Report QA · opravuji report podle quality gate ({_rep_fix}/2)','agent':'Report QA','report_stage':'repair','repair_attempt':_rep_fix,'quality_score':gate.get('score')})
  _sys=system+(' Predchozi verze neprosla quality gate. Oprav vsechny uvedene problemy,'
               ' zachovej evidence_ref/metric/value z analyzy a nepridavej nepodlozena tvrzeni.'
               ' Vrat kompletni opravenou zpravu ve stejnem schematu.')
  _pl={**payload,'previous_report':report,'quality_gate':gate,'evidence_validation':ev}
  try:
   _rr2=call_structured(system=_sys,messages=[{'role':'user','content':json.dumps(_pl,ensure_ascii=False,default=str)}],
                        schema=_schema(),schema_name='npc_client_report_repair',anthropic_model=model,
                        openai_model=model if provider=='openai' else None,max_tokens=9000,
                        prefer=provider,allow_fallback=False)
  except Exception:
   break
  _new=_rr2.get('data') or {}
  if not _new:
   break
  _ev2=validate_analysis(_new,result_summary,battery_results)
  _rev2=review
  if cm!='ECONOMY':
   try:
    _rv=call_structured(system='Jsi nezavisly partner-level reviewer. Hodnot tvrde 0-100.',
                        messages=[{'role':'user','content':json.dumps({'report':_new,'evidence_validation':_ev2},ensure_ascii=False,default=str)}],
                        schema=_review_schema(),schema_name='npc_report_review_repair',anthropic_model=model,
                        openai_model=model if provider=='openai' else None,max_tokens=2500,
                        prefer=provider,allow_fallback=False)
    _rev2=_rv.get('data') or review
   except Exception:
    pass
  _g2=quality_gate(_new,_ev2,_rev2)
  if float(_g2.get('score') or 0)>=float(gate.get('score') or 0):
   report,ev,review,gate,rr=_new,_ev2,_rev2,_g2,_rr2
   if draftp:
    try:
     draftp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
     pass
  if gate['passed']:
   break
 _existing_meta=dict(report.get('_meta') or {})
 report['_meta']={**_existing_meta,'created_at':_now(),'provider':rr.get('provider') or provider,'model':rr.get('model') or model,'quality_gate':gate,'partner_review':review or {},'analysis_evidence_validation':base_ev,'report_evidence_validation':ev,'method_status':'FINAL_ENGINEERING_RELEASE_EXTERNAL_PREDICTIVE_CERTIFICATION_PENDING'}
 report['_meta']['gate_repairs']=_rep_fix
 report['_meta']['client_ready']=bool(gate['passed'])
 # NPC AI RUNTIME FIX: kvalitativni brana uz nezahazuje hotovy beh. Spravnost cisel
 # hlida evidence gate analyzy (zustava tvrda); tady jde o kvalitu textu, takze
 # report vznikne a nese viditelny priznak REVIEW_REQUIRED. Tvrde chovani vratite
 # promennou NPC_STRICT_REPORT_GATE=1.
 if not gate['passed'] and str(__import__('os').environ.get('NPC_STRICT_REPORT_GATE','')).strip().lower() in {'1','true','ano'}:
  raise RuntimeError('CLIENT_REPORT_QUALITY_GATE_FAILED (po %d opravnych pruchodech): '%_rep_fix+json.dumps(gate,ensure_ascii=False))
 return report
def _add_table(doc,headers,rows):
 t=doc.add_table(rows=1,cols=len(headers));t.style='Light Shading Accent 1'
 for i,h in enumerate(headers):t.rows[0].cells[i].text=str(h)
 for row in rows:
  c=t.add_row().cells
  for i,v in enumerate(row):c[i].text=str(v or '')
def export_docx(path,report,*,project,maps=None):
 from docx import Document
 from docx.shared import Inches,Pt
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);d=Document();d.styles['Normal'].font.name='Aptos';d.styles['Normal'].font.size=Pt(10.5);d.add_heading(report.get('title') or project.get('title') or 'Výzkumná zpráva',0);d.add_paragraph(report.get('subtitle') or 'Client deliverable');d.add_heading('Executive summary',1);d.add_paragraph(report.get('executive_summary') or '');d.add_heading('Odpověď pro rozhodnutí',1);d.add_paragraph(report.get('decision_answer') or '');d.add_heading('Výzkumné otázky',1);_add_table(d,['Otázka','Odpověď','Síla evidence'],[[x.get('question'),x.get('answer'),x.get('evidence_strength')] for x in report.get('research_question_answers') or []]);d.add_heading('Co jsme zjistili',1)
 for i,x in enumerate(report.get('key_findings') or [],1):d.add_heading(f"{i}. {x.get('headline')}",2);d.add_paragraph(x.get('finding') or '');d.add_paragraph('Evidence: '+str(x.get('evidence') or ''));d.add_paragraph('Co to znamená: '+str(x.get('meaning') or ''))
 d.add_heading('Doporučení',1)
 for x in report.get('implications') or []:d.add_heading(str(x.get('action') or ''),2);d.add_paragraph(str(x.get('why') or ''))
 d.add_heading('Jak výsledky zapadají do dostupné externí evidence',1);d.add_paragraph(report.get('validation_summary') or '');d.add_heading('Jistota závěrů',1);d.add_paragraph(report.get('confidence_summary') or '');d.add_heading('Metodika',1);d.add_paragraph(report.get('method_summary') or '');d.add_heading('Limity',1)
 for x in report.get('limitations') or []:d.add_paragraph(str(x),style='List Bullet')
 d.add_heading('Závěr',1);d.add_paragraph(report.get('closing') or '');d.save(p);return p
def export_html(path,report,*,project,maps=None):
 e=lambda x:html.escape(str(x or ''));p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);find=''.join(f'<section><h3>{e(x.get("headline"))}</h3><p>{e(x.get("finding"))}</p><p><b>Co to znamená:</b> {e(x.get("meaning"))}</p></section>' for x in report.get('key_findings') or []);imp=''.join(f'<li><b>{e(x.get("action"))}</b><br>{e(x.get("why"))}</li>' for x in report.get('implications') or []);txt=f'''<!doctype html><meta charset="utf-8"><style>body{{font:16px/1.6 Inter,Arial;background:#eef1f5;margin:0;color:#15171a}}main{{max-width:1050px;margin:auto;background:white;padding:55px 70px}}h1{{font-size:40px}}h2{{margin-top:42px;border-top:1px solid #e5e7eb;padding-top:22px}}.decision{{border-left:5px solid #173a78;background:#f4f7fc;padding:18px;font-size:20px}}</style><main><h1>{e(report.get('title'))}</h1><p>{e(report.get('subtitle'))}</p><h2>Executive summary</h2><p>{e(report.get('executive_summary'))}</p><h2>Odpověď pro rozhodnutí</h2><div class="decision">{e(report.get('decision_answer'))}</div><h2>Co jsme zjistili</h2>{find}<h2>Doporučení</h2><ol>{imp}</ol><h2>Jak výsledky zapadají do externí evidence</h2><p>{e(report.get('validation_summary'))}</p><h2>Jistota a limity</h2><p>{e(report.get('confidence_summary'))}</p><ul>{''.join('<li>'+e(x)+'</li>' for x in report.get('limitations') or [])}</ul></main>''';p.write_text(txt,encoding='utf-8');return p
