from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def test_1860_release_identity():
    from edition_config import build_version, allowed_providers
    assert (ROOT/'VERSION').read_text(encoding='utf-8').strip()=='18.6.6'
    assert build_version()=='18.6.6'
    assert allowed_providers()=={'claude_code_subscription','anthropic','openai'}
    b=json.loads((ROOT/'BUILD_EDITION.json').read_text(encoding='utf-8'))
    assert b['version']=='18.6.6' and b['openai_api_enabled'] is True

def test_1860_three_providers_are_fail_closed_and_not_normalized_away():
    from provider_runtime import normalize_live_provider, policy_for_provider
    assert normalize_live_provider('openai')=='openai'
    assert policy_for_provider('openai')=='OPENAI_ONLY'
    src=(ROOT/'ai_router.py').read_text(encoding='utf-8')
    assert 'allow_fallback=False' in src

def test_1860_project_store_persists_openai_as_openai(tmp_path):
    from project_store import ProjectStore
    st=ProjectStore(tmp_path/'p.sqlite')
    x=st.create_project(title='OpenAI project',project={},preferred_provider='openai',runtime_version='18.6.6')
    row=st.get(x['project_id'])
    assert row['preferred_provider']=='openai'
    assert row['provider_policy']=='OPENAI_ONLY'

def test_1860_workflow_keeps_explicit_openai_stage(tmp_path):
    from job_store import JobStore
    from workflow_engine import create_standard
    from research_project import empty_project
    st=JobStore(tmp_path/'j.sqlite')
    p=empty_project(); p['run_policy']['provider']='openai'; p['run_policy']['phase_overrides']={'report':{'provider':'openai','model':'gpt-test'}}
    wf=create_standard(st,project_id='P',project_revision=1,project=p,mode='dry')
    jobs={j['node_key']:j for j in st.get_workflow(wf['workflow_id'])['jobs']}
    assert jobs['report']['provider_policy']=='openai'

def test_1860_showcase_and_visualization_contract():
    import demo_showcase
    assert len(demo_showcase.catalog())==28
    assert len(demo_showcase.project_catalog())==34
    ui=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    for token in ['Visualization Lab','Zvýraznit','Blikání']:
        assert token in ui
    sm=(ROOT/'sociomap.py').read_text(encoding='utf-8')
    for token in ['Rozbalit vztahovou matici','Normativní skóre']:
        assert token in sm

def test_1860_library_and_populations_contract():
    import library_system_catalog as c
    import population_context as p
    s=c.catalog()['summary']
    assert s['catalog_rows']==945 and s['source_groups']>=130
    a=p.get_population('STATIC')['current_version']; b=p.get_population('LIVE')['current_version']
    assert a['rows']==b['rows']==18766
    assert a['sha256']!=b['sha256']

def test_1860_release_metadata_has_no_current_claude_only_contradiction():
    r=json.loads((ROOT/'RELEASE_STATE.json').read_text(encoding='utf-8'))
    assert r['version']=='18.6.6'
    assert r['status']=='FINAL_ENGINEERING_RELEASE_EXTERNAL_VALIDATION_PENDING'
    assert r['provider_policy']['live_providers']==['claude_code_subscription','anthropic','openai']
    assert r['demos']['total']==34
    p=json.loads((ROOT/'PRODUCT_POLICY.json').read_text(encoding='utf-8'))
    assert p['ai_runtime']['openai_live_allowed'] is True
    assert p['demos']['count']==34
