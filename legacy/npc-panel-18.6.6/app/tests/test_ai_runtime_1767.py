from pathlib import Path
from unittest.mock import patch
import json


def test_fullsim_resolves_builtin_special_panel_without_upload_registry():
    import ui_server
    project={"audience":{"source_mode":"special_audience","dataset_id":"builtin_special:construction_ecosystem","special_panel_key":"construction_ecosystem"}}
    path=Path(ui_server._panel_path_for_project(project))
    assert path.is_file()
    assert path.name=="construction_ecosystem.csv.gz"


def test_fast_brief_does_not_auto_select_special_audience(monkeypatch):
    import research_designer as rd
    data={
        "title":"Test","problem_summary":"Test trhu","decision_use":"go/no-go",
        "objectives":["Zjistit reakci"],"research_questions":["Jaká je reakce?"],"hypotheses":[],
        "recommended_topics":[],"tracked_sets":[],"non_object_measures":[],
        "audience_recommendation":{"strategy":"population","description":"stavební firmy","reason":"AI guess","builtin_subpanel":"","source_mode":"special_audience","dataset_id":"builtin_special:construction_ecosystem"},
        "complexity":"short","estimated_minutes":3,"method_reason":"","questions_for_user":[],"ready_for_questionnaire":True,
    }
    monkeypatch.setattr(rd,'_structured_with_fallback',lambda **kw:(data,{"provider":"claude_code_subscription","model":"sonnet"}))
    out=rd.analyze_research({"goal":"Otestovat nabídku pro stavební firmy"},model='sonnet',provider='claude_code_subscription')
    a=out['audience_recommendation']
    assert a['action']=='advisory_only'
    assert a['source_mode']=='population'
    assert a['dataset_id']==''
    p=rd.analysis_to_project_skeleton(out,{"goal":"Otestovat nabídku"})
    assert p['audience']['source_mode']=='population'
    assert p['audience']['dataset_id']==''


def test_research_partner_preserves_runtime_and_audience_source(monkeypatch):
    import research_copilot as rc
    from research_project import empty_project
    p=empty_project(title='X',goal='Goal',n=300)
    p['run_policy']={'provider':'claude_code_subscription','allow_provider_fallback':False,'phase_overrides':{'x':{'model':'opus'}}}
    p['budget']={'max_usd':12.5,'warning_pct':80}
    p['pre_research']={'accepted':[{'claim':'A','source_title':'S','source_url':'https://example.com'}]}
    p['audience'].update({'source_mode':'special_audience','dataset_id':'builtin_special:construction_ecosystem','dataset_name':'Stavebnictví','special_panel_key':'construction_ecosystem'})
    proposal={'message':'Upraveno','changes_summary':['cíl'],'questions_for_user':[], 'project':{
        'title':'Y','goal':'Nový goal','n':300,'audience':{'strategy':'population','description':'ČR 18+','filters':{},'segment':{},'product_description':'','success_definition':'','discovery_note':''},'sections':[]
    }}
    monkeypatch.setattr('ai_router.call_structured',lambda **kw:{'data':proposal,'provider':'claude_code_subscription','model':'sonnet','fallback_used':False})
    out=rc.chat('Uprav cíl',project=p,model='sonnet',provider='claude_code_subscription')
    q=out['proposed_project']
    assert q['goal']=='Nový goal'
    assert q['run_policy']['provider']=='claude_code_subscription'
    assert q['budget']['max_usd']==12.5
    assert q['pre_research']['accepted'][0]['claim']=='A'
    assert q['audience']['source_mode']=='special_audience'
    assert q['audience']['dataset_id']=='builtin_special:construction_ecosystem'


def test_research_partner_context_is_compact():
    import research_copilot as rc
    from research_project import empty_project
    p=empty_project(title='X',goal='Goal',n=300)
    p['pre_research']={'accepted':[{'claim':'C'*5000,'source_title':'S','source_url':'https://e'} for _ in range(50)],'quarantined':[{'claim':'Q'*5000} for _ in range(50)]}
    c=rc._compact_project_for_ai(p)
    raw=json.dumps(c,ensure_ascii=False)
    assert len(c['research_evidence_digest'])<=8
    assert 'quarantined' not in raw
    assert len(raw)<60000


def test_ui_ai_progress_has_elapsed_eta_heartbeat_and_cancel():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    for token in ['progressMeta','heartbeat','usualRange','cancelActiveJob','ACTIVE_JOB_ID']:
        assert token in s
    assert 'fastInteractiveModel()' in s


def test_ai_action_catalog_covers_user_facing_durable_ai():
    import ai_runtime
    required={'research_analysis','copilot','questionnaire_build','persona_suggest','deep_research','questionnaire_optimize','result_verify','fullsim_prepare','fullsim_run','audience_strategy','audience_propose','scenario_compile','ai_diagnose'}
    assert required.issubset(ai_runtime.AI_ACTIONS)
    for k in required:
        p=ai_runtime.action_profile(k)
        assert p['usual_seconds'][0]>0 and p['usual_seconds'][1]>=p['usual_seconds'][0]
        assert p['hard_seconds']>=p['usual_seconds'][1]


def test_scenario_and_audience_ai_are_durable_jobs():
    server=Path('ui_server.py').read_text(encoding='utf-8')
    ui=Path('ui_app.html').read_text(encoding='utf-8')
    assert '_start_job(self._body(),"scenario_compile")' in server
    assert '_start_job(self._body(),"audience_propose")' in server
    assert "job('/api/scenario/compile'" in ui
    assert "job('/api/audience/propose'" in ui

def test_research_context_exposes_agent_progress():
    s=Path('research_context.py').read_text(encoding='utf-8')
    for token in ['agent 1/2','agent 2/2','syntéza, deduplikace']:
        assert token in s

def test_ai_jobs_have_infrastructure_retry_budget():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    assert 'attempts=3' in s


def test_no_user_ai_module_hardcodes_global_provider_at_callsite():
    for name in ['audience.py','navrh.py','import_dotaznik.py','pdf_targets.py']:
        s=Path(name).read_text(encoding='utf-8')
        assert 'prefer=get_ai_provider()' not in s


def test_builtin_special_panel_can_prepare_world_model_end_to_end():
    import ui_server
    from full_simulation import prepare_full_simulation
    project={'title':'Construction','goal':'test','n':40,'model':'sonnet','run_policy':{'provider':'claude_code_subscription'},
             'audience':{'source_mode':'special_audience','dataset_id':'builtin_special:construction_ecosystem','special_panel_key':'construction_ecosystem','dataset_name':'Construction ecosystem'},'sections':[]}
    panel=ui_server._panel_path_for_project(project)
    spec={'topic':'Co když cena roste?','questions':[{'id':'Q','text':'Jaká bude reakce?','kategorie':['Negativní','Stejná','Pozitivní']}],
          'objective':'scenario_nowcast','domain':'general','n':40,'worlds':2,'mode':'dry','research_enabled':False,'world_model_provider':'heuristic',
          'scenario_contract':{'status':'APPROVED','shifts':[{'factor':'price','direction':'increase','magnitude_sd':.3,'scope':'whole audience','mechanism':'price friction','confidence':.3,'evidence_basis':'hypothesis'}]}}
    phases=[]
    out=prepare_full_simulation(spec,panel_path=panel,progress=phases.append)
    assert out['world_model']['sha256']
    assert any('načítám audience' in x for x in phases)
