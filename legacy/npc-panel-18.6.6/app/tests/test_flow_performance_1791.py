from pathlib import Path
from types import SimpleNamespace
import json


def _context():
    return {
        'title':'T','subject':'S','client':'','product_service':'Produkt','category':'Kategorie','market':'ČR',
        'geography':'ČR','current_state':'Dnes','current_price':'','price_unit':'','price_architecture':'',
        'competitors':[],'brand_positioning':'','customer_segments':[],'purchase_drivers':['relevance'],
        'category_dynamics':[],'constraints':[],'decision':'Rozhodnout','outcomes':['zájem'],'known_facts':['brief'],
        'assumptions':[],'uncertainties':[],'research_questions':['Co je důležité?'],'summary':'Shrnutí'
    }


def test_research_intake_routes_default_sonnet_to_fast_haiku(monkeypatch):
    import ui_server, research_designer
    seen={}
    def fake(briefing,*,model,provider,fast=False):
        seen.update(model=model,provider=provider,fast=fast)
        return {'title':'T','problem_summary':'P','decision_use':'D','objectives':['O'],'research_questions':['RQ'],
                'hypotheses':[],'tracked_sets':[],'non_object_measures':[],'questions_for_user':[],
                'complexity':'short','method_reason':'M','ready_for_questionnaire':True,'study_type':'custom','study_config':{},
                'audience_recommendation':{'source_mode':'population'},'_ai':{}}
    monkeypatch.setattr(research_designer,'analyze_research',fake)
    out=ui_server.analyze_research_brief({'briefing':{'goal':'Zjistit reakci'},'model':'sonnet','provider':'claude_code_subscription','n':120})
    assert seen == {'model':'haiku','provider':'claude_code_subscription','fast':True}
    assert out['fast_brief_analysis'] is True
    assert out['research']['quality_status']=='NOT_RUN'


def test_quick_simulation_context_never_calls_web_research(monkeypatch):
    import simulation_context, research_context, data_library
    calls=[]
    def fake_call(**kw):
        calls.append(kw)
        return {'data':_context(),'provider':'claude_code_subscription','model':kw['anthropic_model']}
    monkeypatch.setattr(simulation_context,'call_structured',fake_call)
    monkeypatch.setattr(research_context,'run_dual_research',lambda *a,**k: (_ for _ in ()).throw(AssertionError('web research must not run in quick context')))
    monkeypatch.setattr(data_library,'knowledge_context_for_project',lambda *a,**k:{'dimensions':[],'count':0})
    out=simulation_context.enrich_simulation_context('Test',provider='claude_code_subscription',model='sonnet',deep_research=False)
    assert len(calls)==1
    assert calls[0]['anthropic_model']=='haiku'
    assert calls[0]['claude_max_turns']==2 and calls[0]['claude_interactive'] is True
    assert out['evidence']['quality_status']=='NOT_RUN_FAST_CONTEXT'
    assert out['_meta']['mode']=='quick_context'


def test_deep_simulation_context_preserves_dual_research(monkeypatch):
    import simulation_context, research_context, data_library
    calls=[]
    def fake_call(**kw):
        calls.append(kw)
        return {'data':_context(),'provider':'claude_code_subscription','model':kw['anthropic_model']}
    monkeypatch.setattr(simulation_context,'call_structured',fake_call)
    agent=SimpleNamespace(agent='claude_code_A',model='sonnet',searched_at='now',error=None,findings=[])
    bundle=SimpleNamespace(enabled=True,topic='T',created_at='now',quality_status='DUAL_VERIFIED',sha256='abc',accepted=[],quarantined=[],agents=[agent,agent])
    seen={'research':0}
    def fake_research(*a,**k): seen['research']+=1; return bundle
    monkeypatch.setattr(research_context,'run_dual_research',fake_research)
    monkeypatch.setattr(data_library,'knowledge_context_for_project',lambda *a,**k:{'dimensions':[],'count':0})
    out=simulation_context.enrich_simulation_context('Test',provider='claude_code_subscription',model='sonnet',deep_research=True)
    assert seen['research']==1 and len(calls)==2
    assert out['evidence']['quality_status']=='DUAL_VERIFIED'
    assert out['_meta']['mode']=='standalone_enrichment'


def test_cancelled_stage_becomes_ready_and_clears_current_job(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'p.sqlite')
    try:
        created=ps.create_project(project_type='research',title='X',project={'title':'X','goal':'G'},runtime_version='17.9.1')
        pid,rev=created['project_id'],created['revision']
        ps.set_stage(pid,rev,'RESEARCH_DESIGN','RUNNING',current_job_id='JOB-old')
        ps.set_stage(pid,rev,'RESEARCH_DESIGN','READY',waiting_reason='cancelled_by_user',clear_current_job=True)
        st=ps.stage(pid,rev,'RESEARCH_DESIGN'); pr=ps.get(pid)
        assert st['status']=='READY' and st['current_job_id'] is None
        assert pr['status']=='READY_TO_CONTINUE' and pr['current_stage']=='RESEARCH_DESIGN'
    finally: ps.close()


def test_stage_mapping_separates_fast_and_deep_simulation_context():
    from project_pipeline import LEGACY_STAGE_MAP
    assert LEGACY_STAGE_MAP['simulation_context_enrich']=='BRIEF'
    assert LEGACY_STAGE_MAP['simulation_context_deep']=='DEEP_RESEARCH'
    assert LEGACY_STAGE_MAP['simulation_uncertainty_resolve']=='DEEP_RESEARCH'


def test_ui_exposes_fast_context_and_optional_deep_research():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert '/api/simulation/context/enrich' in s
    assert '/api/simulation/context/deep' in s
    assert 'Deep Research (volitelné)' in s
    assert 'deep_research:false' in s
    assert '},1800)}' in s


def test_autosave_server_uses_supplied_panel_version_fast_path():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    a=s.index('def save_project_state'); b=s.index('def project_history',a); block=s[a:b]
    assert "panel_version=str(req.get('panel_version') or '').strip()" in block
    assert "if not panel_version:" in block


def test_claude_interactive_runtime_plumbing_present():
    p=Path('claude_code_provider.py').read_text(encoding='utf-8')
    r=Path('ai_router.py').read_text(encoding='utf-8')
    assert 'interactive: bool = False' in p
    assert 'max_turns:int=8,interactive:bool=False' in p
    assert 'claude_max_turns: int = 8, claude_interactive: bool = False' in r
