from pathlib import Path
import json


def test_progress_ui_prefers_running_job_and_shows_real_phase():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'function workflowActiveJob1784' in s
    assert "RUNNING:0" in s and "READY:7" in s
    block=s[s.index('function workflowActiveJob1784'):s.index('async function retryResearch1770')]
    assert 'latest_progress' in block
    assert 'Skutečně aktivní krok' in block
    assert 'procento znamená dokončené hlavní kroky' in block


def test_workflow_api_exposes_current_job_and_latest_progress():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    block=s[s.index('def _workflow_public'):s.index('PAGE=',s.index('def _workflow_public'))]
    assert "event_type='PROGRESS'" in block
    assert "rank={'RUNNING':0" in block
    assert "w['current_job']=current" in block
    assert "w['progress_pct']" in block


def test_background_research_forwards_internal_progress():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    block=s[s.index("elif kind == 'background_research'"):s.index("elif kind == 'project_preflight'")]
    assert 'def _research_progress(text)' in block
    assert 'run_dual_research(cfg, _compiled_questions(project), provider_override=provider, progress=_research_progress)' in block


def test_client_report_has_validated_analysis_fallback_and_nonblocking_reviewer():
    s=Path('client_report_v2.py').read_text(encoding='utf-8')
    assert 'def _fallback_report_from_validated_analysis' in s
    assert 'DETERMINISTIC_FROM_VALIDATED_ANALYSIS' in s
    assert 'stylistický AI průchod selhal' in s
    assert 'reviewer nedokončil kontrolu; report pokračuje' in s


def test_report_artifact_gate_keeps_core_outputs_hard_and_deck_optional():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    block=s[s.index("elif kind == 'final_report'"):s.index("elif kind == 'condition_gate'")]
    req=block[block.index('_required_client_artifacts='):block.index('_optional_client_artifacts=')]
    opt=block[block.index('_optional_client_artifacts='):block.index('_missing_client=[]')]
    assert 'client_report_docx' in req and 'client_report_html' in req
    assert 'respondent_dataset_csv' in req and 'respondent_results_xlsx' in req
    assert 'client_delivery_zip' in req
    assert 'management_deck_pptx' not in req
    assert 'management_deck_pptx' in opt
    assert 'COMPLETED_DEGRADED_FORMATTING' in block


def test_version_1784():
    assert Path('VERSION').read_text(encoding='utf-8').strip()=='18.6.6'
    assert json.loads(Path('BUILD_EDITION.json').read_text(encoding='utf-8'))['version']=='18.6.6'

def test_report_ai_failure_still_returns_report_from_validated_analysis(monkeypatch,tmp_path):
    import ai_router, data_library
    from client_report_v2 import compose_report
    monkeypatch.setattr(ai_router,'call_structured',lambda **kw: (_ for _ in ()).throw(RuntimeError('synthetic report AI outage')))
    monkeypatch.setattr(data_library,'knowledge_context_for_project',lambda *a,**k:{'count':0,'dimensions':[]})
    summary={'vysledky':{'Q1':{'celkem_pct':{'Ano':60.0,'Ne':40.0}}}}
    ev={'score':100.0,'passed':True,'threshold':90,'reference_checks':1,'reference_ok':1,'numeric_claims':1,'numeric_claims_ok':1,'finding_reference_coverage':1.0,'issues':[],'checks':[]}
    claim={'evidence_ref':'Q1','metric':'pct:Ano','value':60.0,'unit':'%','label':'Ano'}
    analysis={
      'executive_answer':'Šedesát procent modelovaných respondentů volí odpověď Ano; závěr vychází z výsledku Q1.',
      'research_question_answers':[{'question':'Koupili by produkt?','answer':'V modelu převažuje Ano.','evidence_strength':'strong','evidence_refs':['Q1'],'numeric_claims':[claim],'why':'Q1'}],
      'key_findings':[{'headline':'Převažuje Ano','finding':'V Q1 je Ano nejsilnější odpověď.','evidence_refs':['Q1'],'numeric_claims':[claim],'numbers':['Ano 60 %'],'who_differs':'','meaning':'Převažující modelovaný směr.','confidence':'high'}],
      'implications':[{'action':'Pracovat s tímto směrem opatrně.','rationale':'Jde o syntetický výsledek.','priority':'medium','evidence_refs':['Q1']}],
      'confidence_summary':'Evidence v rámci modelového běhu je konzistentní.','limitations':['Syntetický výzkum.'],
      '_meta':{'evidence_validation':ev,'research_questions':['Koupili by produkt?']}
    }
    report=compose_report({'title':'Test','goal':'Test','run_policy':{'cost_mode':'REFERENCE','provider':'claude_code_subscription'}},summary,analysis,verification={'quality_status':'TEST'},checkpoint_dir=tmp_path)
    assert report['_meta']['report_generation_mode']=='DETERMINISTIC_FROM_VALIDATED_ANALYSIS'
    assert 'synthetic report AI outage' in report['_meta']['ai_report_error']
    assert report['key_findings'][0]['evidence_refs']==['Q1']


def test_deterministic_fallback_skips_additional_ai_repairs():
    s=Path('client_report_v2.py').read_text(encoding='utf-8')
    assert "while not gate['passed'] and _rep_fix<2 and (report.get('_meta') or {}).get('report_generation_mode')!='DETERMINISTIC_FROM_VALIDATED_ANALYSIS'" in s
