from pathlib import Path
from evidence_validator import validate_analysis
from client_report_v2 import numeric_text_gate, export_docx
from output_pack import export_management_deck_pptx, export_verbatims
from job_store import JobStore

def summary():return {'vysledky':{'Q1':{'celkem_pct':{'Ano':63.0,'Ne':37.0},'n':400,'effective_n':350,'verbatimy':['Celá odpověď bez zkrácení.']}}}
def analysis(v=63.0):
 c={'evidence_ref':'Q1','metric':'pct:Ano','value':v,'unit':'pct','label':'Ano'}
 return {'key_findings':[{'headline':'Zájem je většinový','finding':'63 % Ano.','evidence_refs':['Q1'],'numeric_claims':[c]}],'research_question_answers':[{'question':'Je zájem?','answer':'Ano, 63 %.','evidence_refs':['Q1'],'numeric_claims':[c]}],'implications':[]}
def report():
 c={'evidence_ref':'Q1','metric':'pct:Ano','value':63.0,'unit':'pct','label':'Ano'}
 return {'title':'Test','subtitle':'Client','executive_summary':'Výsledek ukazuje většinový zájem a jasný důvod pokračovat v ověřování nabídky.','decision_answer':'Pokračovat v ověřování; 63 % odpovědělo Ano.','research_question_answers':[{'question':'Je zájem?','answer':'Ano, 63 %.','evidence_strength':'high','why':'Q1','evidence_refs':['Q1'],'numeric_claims':[c]}],'key_findings':[{'headline':'Zájem je většinový','finding':'63 % Ano.','evidence':'Q1','meaning':'Pokračovat.','confidence':'high','evidence_refs':['Q1'],'numeric_claims':[c]}],'implications':[{'action':'Pokračovat','why':'Většina je pozitivní.','priority':'high','evidence_refs':['Q1'],'numeric_claims':[c]}],'validation_summary':'External validation pending.','confidence_summary':'Modelový výsledek.','method_summary':'Syntetický panel.','limitations':['External validation pending.'],'closing':'Další krok je externí holdout.'}
def test_evidence_rejects_forgery():
 assert validate_analysis(analysis(63),summary())['passed'] is True
 assert validate_analysis(analysis(75),summary())['passed'] is False
def test_numeric_gate():
 r=report();assert numeric_text_gate(r)['passed'];r['closing']='Nepodložených 99 %.';assert not numeric_text_gate(r)['passed']
def test_commander_override(tmp_path):
 s=JobStore(tmp_path/'j.sqlite');w=s.create_workflow(project_id='P',project_revision=1,cost_mode='REFERENCE');j=s.add_job(w,'analysis','analysis',input_data={'project':{'run_policy':{}}});x=s.configure_job(j,provider='openai',model='gpt-5',estimated_cost_usd=2.5,phase_policy={'fallback_budget_usd':4});assert x['provider_policy']=='openai' and x['model']=='gpt-5'
def test_client_exports_hide_internal(tmp_path):
 p=Path(export_docx(tmp_path/'c.docx',report(),project={'title':'Test'}));from docx import Document;text='\n'.join(x.text for x in Document(p).paragraphs).lower();assert 'quality gate' not in text and 'provider' not in text;d=Path(export_management_deck_pptx(tmp_path/'d.pptx',{'title':'Test'},report()));assert d.stat().st_size>1000
def test_verbatim_full(tmp_path):
 t='Dlouhá odpověď. '+('Celá věta. '*100);s=summary();s['vysledky']['Q1']['verbatimy']=[t];o=export_verbatims(tmp_path/'v.csv',tmp_path/'v.html',{'title':'X'},s);assert o['count']==1 and t in (tmp_path/'v.csv').read_text(encoding='utf-8-sig')
