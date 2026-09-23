from unittest.mock import patch
from pathlib import Path
import types, json

import pytest


def test_scenario_ai_failure_is_fail_visible_not_local_fallback():
    import scenario_compiler
    project={"goal":"Otestovat změnu ceny","run_policy":{"provider":"openai"},"audience":{"source_mode":"population"}}
    with patch('scenario_compiler.call_structured',side_effect=RuntimeError('[TRANSPORT] network down')):
        with pytest.raises(RuntimeError) as ei:
            scenario_compiler.compile_scenario('Cena se zvýší o 10 %',project=project,provider='openai',model='gpt-5.6')
    text=str(ei.value)
    assert 'SCENARIO_AI_FAILED' in text
    assert 'local_fallback' not in text


def test_fullsim_wrapper_survives_partially_malformed_ai_project():
    import ui_server
    # AI-shaped project with an invalid single-category question. Normal survey compile
    # is allowed to reject it; scenario wrapper must derive its own transparent outcome.
    project={
      'title':'AI doplněný projekt','goal':'Zjistit reakci na zdražení produktu','n':320,'model':'sonnet',
      'run_policy':{'provider':'claude_code_subscription'},
      'audience':{'source_mode':'population','strategy':'population','description':'ČR 18+','filters':{},'segment':{'mode':'none'}},
      'sections':[{'id':'broken','type':'questions','title':'AI blok','questions':[{'id':'Q_BAD','text':'Nedokončená otázka','typ':'vyber','kategorie':['Ano']}]}],
    }
    spec=ui_server._fullsim_spec_from_payload({'project':project,'spec':{'objective':'scenario_nowcast'}})
    assert spec['questions'][0]['id']=='SCENARIO_OUTCOME'
    assert spec['auto_outcome_question'] is True
    assert 'project_compile_warning' in spec
    assert spec['n']==320


def test_openai_research_repairs_stale_model_before_web_search(monkeypatch):
    import research_context as rc
    captured={}
    class Resp:
        model='gpt-5.6'
        output_text=json.dumps({'findings':[]})
    class Responses:
        def create(self,**kw): captured.update(kw); return Resp()
    class Client:
        responses=Responses()
    monkeypatch.setattr('provider_auth.create_openai_client',lambda **_:Client())
    monkeypatch.setattr('ai_router._openai_repair_model',lambda client,wanted:'gpt-5.6')
    cfg=rc.ResearchConfig(enabled=True,topic='test',openai_model='stale-model-id')
    out=rc._openai_research('test',[{'id':'Q1','text':'Co si myslíte?'}],cfg)
    assert out.error is None
    assert captured['model']=='gpt-5.6'
    assert captured['tools'][0]['type']=='web_search'


def test_claude_dual_research_gets_same_provider_recovery(monkeypatch):
    import research_context as rc
    calls=[]
    def fake(topic,questions,cfg,name):
        calls.append(name)
        if name in {'claude_code_A','claude_code_B'}:
            return rc.AgentResearch(name,'sonnet',topic,'now',[], 'transient')
        return rc.AgentResearch(name,'sonnet',topic,'now',[], None)
    monkeypatch.setattr(rc,'_claude_code_research',fake)
    monkeypatch.setattr('provider_auth.provider_key_ready',lambda p: True)
    monkeypatch.setattr('provider_auth.get_ai_provider',lambda:'claude_code_subscription')
    b=rc.run_dual_research(rc.ResearchConfig(enabled=True,topic='x'),[{'id':'Q1','text':'x'}],provider_override='claude_code_subscription')
    assert calls==['claude_code_A','claude_code_B','claude_code_recovery']
    assert b.quality_status=='SINGLE_PROVIDER_SELECTED'


def test_production_ai_paths_do_not_contain_automatic_local_fallback_label():
    # Debug fallbacks may remain behind explicit env flags, but default production
    # execution paths must never emit provider=local_fallback on failure.
    s=Path('scenario_compiler.py').read_text(encoding='utf-8')
    assert 'provider":"local_fallback"' not in s
    d=Path('research_designer.py').read_text(encoding='utf-8')
    assert 'NPC_ALLOW_LOCAL_DESIGN_FALLBACK' in d

def test_ai_scenario_contract_then_fullsim_dry_end_to_end(monkeypatch):
    import scenario_compiler
    import ui_server
    from full_simulation import run_full_simulation
    ai_data={
      'title':'Cena +10 %','objective':'baseline_delta','baseline':'Současná cena','event':'Cena se zvýší o 10 %',
      'time_horizon':'okamžitě','target_outcomes':['reakce na produkt'],
      'shifts':[{'factor':'economic_friction','direction':'increase','magnitude_sd':0.35,'scope':'whole audience','mechanism':'vyšší cena zvyšuje ekonomickou bariéru','confidence':0.5,'evidence_basis':'hypothesis_to_review'}],
      'assumptions':[],'unknowns':[],'review_note':'review'
    }
    monkeypatch.setattr(scenario_compiler,'call_structured',lambda **kw:{'data':ai_data,'provider':'openai','model':'gpt-5.6','fallback_used':False,'mode':'json_schema_strict'})
    project={'title':'AI projekt','goal':'Zjistit reakci na cenu','n':60,'model':'gpt-5.6','run_policy':{'provider':'openai'},'audience':{'source_mode':'population','strategy':'population','description':'ČR 18+','filters':{},'segment':{'mode':'none'}},'sections':[]}
    contract=scenario_compiler.approve_scenario(scenario_compiler.compile_scenario('Cena +10 %',project=project,provider='openai',model='gpt-5.6'))
    spec=ui_server._fullsim_spec_from_payload({'project':project,'spec':{'objective':'scenario_nowcast','mode':'dry','worlds':2,'min_worlds':2,'adaptive_worlds':False,'research_enabled':False,'world_model_provider':'heuristic','include_core_baseline':False,'include_demographics_baseline':False,'diagnostic_mode':'off','save_world_overlays':False,'use_learning_profile':False,'auto_wording_stress':False,'seed':17631}})
    spec['scenario_contract']=contract
    out=run_full_simulation(spec)
    assert out['manifest']['run_status']=='INVALID_DRY_RUN'
    assert out['manifest']['worlds_executed']==2
    assert 'SCENARIO_OUTCOME' in out['prediction']['methods']['FULL_SIMULATION']['questions']
