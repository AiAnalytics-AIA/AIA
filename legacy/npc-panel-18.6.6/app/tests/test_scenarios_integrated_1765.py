from pathlib import Path
from unittest.mock import patch


def test_scenario_step_is_integrated_and_renderer_exists():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert "['fullsim','7','Scénáře'" in s
    assert "['results','8','Výstupy'" in s
    assert 'function fsPredHtml(p)' in s
    assert "function startProductionSimulation(){APP_MODE='production';PRODUCT_PATH='research'" in s
    assert 'Rovnou scénář / simulace' in s


def test_fullsim_run_persistence_reads_same_key_it_writes():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert "localStorage.setItem('npc_fullsim_run_1019'" in s
    load=s[s.index('function load()'):s.index('function toast',s.index('function load()'))]
    assert "localStorage.getItem('npc_fullsim_run_1019')" in load


def test_new_project_clears_old_scenario_state():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    reset=s[s.index('function resetProject()'):s.index('function renderBrief',s.index('function resetProject()'))]
    for key in ['npc_fullsim_run_1019','npc_fullsim_prep_1015','npc_scenario_contract_15']:
        assert key in reset
    assert 'SCENARIO_CONTRACT=null' in reset


def test_scenario_contract_is_editable_before_approval():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    for fn in ['updateScenarioShift','removeScenarioShift','addScenarioShift','unlockScenario']:
        assert f'function {fn}' in s
    assert 'Schválit scénář pro simulaci' in s


def test_fullsim_reuses_existing_safe_research(monkeypatch):
    import full_simulation as fs
    accepted=[{'claim':'Bezpečný kontext','source_title':'Zdroj','source_url':'https://example.com','topics':['general']}]
    existing={'accepted':accepted,'quarantined':[{'claim':'outcome benchmark'}],'quality_status':'PASS','config':{}}
    spec={
        'topic':'Co když cena stoupne o 10 %?','questions':[{'id':'Q','text':'Dopad?','kategorie':['Negativní','Stejný','Pozitivní']}],
        'objective':'scenario_nowcast','domain':'general','n':50,'worlds':2,'mode':'dry','research_enabled':True,
        'world_model_provider':'heuristic','scenario_contract':{'status':'APPROVED','shifts':[{'factor':'price','direction':'increase','magnitude_sd':.4,'scope':'whole audience','mechanism':'price friction','confidence':.3,'evidence_basis':'hypothesis'}]},
    }
    monkeypatch.setattr(fs,'run_dual_research',lambda *a,**k: (_ for _ in ()).throw(AssertionError('research should have been reused')))
    prep=fs.prepare_full_simulation(spec,existing_research=existing)
    assert prep['research_summary']['accepted']==1
    assert prep['research']['accepted'][0]['claim']=='Bezpečný kontext'


def test_scenario_compiler_receives_existing_safe_research(monkeypatch):
    import scenario_compiler as sc
    seen={}
    def fake(**kw):
        seen['messages']=kw['messages']
        return {'data':{'title':'X','objective':'baseline_delta','baseline':'B','event':'E','time_horizon':'T','target_outcomes':['Q'],
          'shifts':[{'factor':'price','direction':'increase','magnitude_sd':.4,'scope':'all','mechanism':'m','confidence':.3,'evidence_basis':'hypothesis'}],
          'assumptions':[],'unknowns':[],'review_note':''},'provider':'openai','model':'gpt'}
    monkeypatch.setattr(sc,'call_structured',fake)
    project={'decision_use':'go/no-go','audience':{'source_mode':'population'},'research_plan':{},'pre_research':{'accepted':[{'claim':'Known fact','source_title':'S','source_url':'https://e'}]}}
    sc.compile_scenario('cena +10%',project=project,provider='openai',model='gpt')
    assert 'Known fact' in seen['messages'][0]['content']
