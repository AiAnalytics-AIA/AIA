from pathlib import Path


def ui(): return Path('ui_app.html').read_text(encoding='utf-8')


def test_first_research_analysis_uses_sonnet_claude_only():
    s=ui()
    # analyzeBrief delegates to the current fingerprint-aware implementation.
    assert "await ensureAnalysis1776(false)" in s
    start=s.index('async function ensureAnalysis1776')
    block=s[start:s.index('analyzeBrief=async function',start)]
    assert "model:'sonnet'" in block
    assert "provider:'claude_code_subscription'" in block
    analyze=s[s.index('analyzeBrief=async function'):s.index('async function forceReanalyze',s.index('analyzeBrief=async function'))]
    assert 'BRIEF_AI_ERROR_1773' in analyze
    assert 'renderBrief()' in analyze
    rd=Path('research_designer.py').read_text(encoding='utf-8')
    fast=rd[rd.index('def _fast_analysis_tool'):rd.index('def _question_schema')]
    assert 'audience_recommendation' not in fast
    fn=rd[rd.index('def analyze_research('):rd.index('def analysis_to_project_skeleton')]
    assert 'max_out = 1800 if fast else 3200' in fn


def test_durable_job_surfaces_real_failure_and_remembers_job_id():
    s=ui(); block=s[s.index('async function job('):s.index('function renderSteps()',s.index('async function job('))]
    assert 'window.LAST_FAILED_JOB_ID=id' in block
    assert 'j.result?.error' in block
    assert 'j.error?.error' in block
    assert 'provider_error' in block


def test_worker_has_no_paid_provider_fallback_branch():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    assert '_request_paid_fallback' not in s
    assert 'CLAUDE_CODE_STAGE_FAILED' in s


def test_simulation_is_a_visible_standalone_product():
    s=ui(); a=s.index('// 17.7.3 — STANDALONE SIMULATION PRODUCT'); b=s.index('async function boot()',a); block=s[a:b]
    assert 'SIM_STEPS_1773' in block
    for step in ['sim_context','sim_change','sim_people','sim_run','sim_results']:
        assert step in block
    assert 'startSimulationProduct1773()' in block
    assert 'SCENARIO' in block
    assert "PRODUCT_PATH='simulation'" in block
    research=s[s.index('RESEARCH_STEPS.splice'):s.index('const _saveStep1')]
    assert 'fullsim' not in research


def test_simulation_normal_ui_hides_old_fullsim_knobs():
    s=ui(); a=s.index('function renderSimContext1773'); b=s.index('// Product navigation overrides',a); block=s[a:b]
    forbidden=['fsWorlds','fsSources','fsBudget','fsMode','n / svět','počet světů','Hard budget','HYBRID','INVALID_DRY_RUN']
    for token in forbidden: assert token not in block
    assert 'Rychlá' in block and 'Standard' in block and 'Důkladná' in block


def test_simulation_can_import_current_research_without_requiring_server_load():
    s=ui(); block=s[s.index('async function importResearchToSimulation1773'):s.index('function saveSimContext1773')]
    assert 'let src=PROJECT' in block
    assert "PROJECT_ID" in block and "/api/projects/load" in block
    # Server load is fallback only when local project has no useful context.
    assert "if(!researchHasContext1773(src)&&PROJECT_ID)" in block


def test_simulation_run_is_one_user_action_and_strict_claude_live():
    s=ui(); block=s[s.index('async function runSimulation1773'):s.index('function simFriendlyPrediction1773')]
    assert "/api/fullsim/pipeline" in block
    assert "/api/fullsim/batch-pipeline" in block
    assert "/api/fullsim/prepare" not in block and "/api/fullsim/run" not in block
    assert 'confirm_live:true' in block
    assert "go('sim_results')" in block
    dispatch=Path('legacy_job_dispatch.py').read_text(encoding='utf-8')
    start=dispatch.index('elif kind=="fullsim_pipeline"'); tail=dispatch[start:]; end=tail.find('\n    elif ',10); fs=tail if end<0 else tail[:end]
    assert 'requested=normalize_ai_provider' in fs and 'req["provider"]=requested' in fs
    assert 'has_anthropic_key()' in fs
    assert 'validate_full_simulation_result' in fs

def test_simulation_results_are_business_friendly_not_world_count_led():
    s=ui(); block=s[s.index('function simFriendlyPrediction1773'):s.index('// Product navigation overrides')]
    assert 'Dnes' in block and 'Po změně' in block and 'Rozdíl' in block
    assert 'světů' not in block.lower()
    assert 'Náklady' not in block


def test_dry_fullsim_audit_is_explicitly_local_only():
    s=Path('full_simulation.py').read_text(encoding='utf-8')
    assert 'else "dry_local_only"' in s


def test_demo_is_not_part_of_final_product_or_server():
    ui=Path('ui_app.html').read_text(encoding='utf-8')
    server=Path('ui_server.py').read_text(encoding='utf-8')
    assert 'async function loadIllustrativeDemo' not in ui
    assert 'function renderDemoMode' not in ui
    assert 'def illustrative_demo' not in server
    assert not Path('demo_prototype.json').exists()
    assert Path('selftest_questionnaire.json').is_file()
    assert not Path('prototype_outputs/demo_showcase').exists()


def test_fast_research_analysis_survives_claude_cli_without_json_schema(monkeypatch,tmp_path):
    import json, os
    import claude_code_provider as provider
    import research_designer as rd
    fake=tmp_path/'claude_compat'
    payload={
      'title':'Test ceny','problem_summary':'Zjistit reakci na změnu ceny','decision_use':'Rozhodnout o ceně',
      'objectives':['Změřit reakci'],'research_questions':['Jak se změní zájem?'],
      'hypotheses':['Vyšší cena sníží zájem'],'tracked_sets':[],
      'non_object_measures':[{'name':'purchase intent','reason':'hlavní outcome','question_type':'scale'}],
      'questions_for_user':[],'complexity':'short','method_reason':'Krátký rozhodovací výzkum','ready_for_questionnaire':True
    }
    script='''#!/usr/bin/env python3\nimport json,sys\nargs=sys.argv[1:]\n_ = sys.stdin.read()\nif '--json-schema' in args:\n print('error: unknown option --json-schema',file=sys.stderr,flush=True);sys.exit(2)\nprint(json.dumps({'type':'system','subtype':'init','model':'haiku'}),flush=True)\nprint(json.dumps({'type':'result','subtype':'success','result':json.dumps(PAYLOAD,ensure_ascii=False),'session_id':'research','usage':{'input_tokens':33,'output_tokens':55}}),flush=True)\n'''.replace('PAYLOAD',repr(payload))
    fake.write_text(script,encoding='utf-8');fake.chmod(0o755)
    monkeypatch.setattr(provider,'auth_status',lambda:{'subscription_verified':True})
    monkeypatch.setattr(provider,'supports_required_cli',lambda:True)
    monkeypatch.setattr(provider,'executable',lambda:str(fake))
    monkeypatch.setattr(provider,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(provider,'_lock_release',lambda _slot:None)
    monkeypatch.setattr(provider,'subscription_env',lambda:{'PATH':os.environ.get('PATH','')})
    out=rd.analyze_research({'goal':'Chci zjistit, jak lidé zareagují na vyšší cenu.'},model='haiku',provider='claude_code_subscription',fast=True)
    assert out['title']=='Test ceny'
    assert out['research_questions']==['Jak se změní zájem?']
    assert out['_ai']['provider']=='claude_code_subscription'
    assert out['audience_recommendation']['source_mode']=='population'
