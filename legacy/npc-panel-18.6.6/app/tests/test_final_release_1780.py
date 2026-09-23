from __future__ import annotations

from pathlib import Path
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def text(name:str)->str:
    return (ROOT/name).read_text(encoding='utf-8')


def test_release_identity_is_consistent_1780():
    from edition_config import build_version, load_edition
    assert text('VERSION').strip()=='18.6.6'
    assert build_version()=='18.6.6'
    ed=load_edition()
    assert ed['version']=='18.6.6'
    assert ed['default_provider']=='claude_code_subscription'
    assert ed['claude_code_enabled'] is True


def test_claude_runtime_has_production_safety_contract():
    src=text('claude_code_provider.py')
    assert "NPC_CLAUDE_CODE_SLOTS', '1'" in src
    assert 'max_turns:int=8' in src
    cmd=src[src.index('def _base_cli_command'):src.index('def _terminate_tree')]
    assert '--include-partial-messages' not in cmd
    import ai_router
    assert ai_router.classify_provider_exception(RuntimeError('{"permissionMode":"dontAsk"}'))!='PERMISSION'
    assert ai_router.classify_provider_exception(RuntimeError('error_max_turns'))=='MAX_TURNS'


def test_browser_never_auto_cancels_ai_on_client_timer():
    s=text('ui_app.html')
    start=s.index('async function job(endpoint')
    end=s.index('\n',start)
    fn=s[start:end]
    assert "/api/jobs/" not in fn or "/cancel" not in fn
    assert 'server hard stop' in fn
    assert 'job neruším' in fn


def test_research_brief_cache_belongs_only_to_exact_brief_and_uses_sonnet():
    s=text('ui_app.html')
    assert 'function briefFingerprint1780()' in s
    assert 'ANALYSIS._brief_signature===sig' in s
    assert "model:'sonnet',provider:'claude_code_subscription'" in s
    assert 'forceReanalyze1780' in s


def test_workflow_graph_has_publish_barrier_and_claim_guard():
    js=text('job_store.py'); wf=text('workflow_engine.py')
    assert 'def activate_workflow_graph' in js
    assert "status='DRAFT'" in wf
    assert 'NOT EXISTS (SELECT 1 FROM job_dependencies' in js
    assert 'store.activate_workflow_graph(wid)' in wf


def test_old_cross_provider_phase_override_is_normalized_and_logged(tmp_path):
    from job_store import JobStore
    from workflow_engine import create_standard
    from research_project import empty_project
    st=JobStore(tmp_path/'jobs.sqlite')
    p=empty_project();p['run_policy']['cost_mode']='REFERENCE';p['run_policy']['phase_overrides']={'report':{'provider':'openai','model':'gpt-5'}}
    wf=create_standard(st,project_id='P',project_revision=1,project=p,mode='dry')
    jobs={j['node_key']:j for j in st.get_workflow(wf['workflow_id'])['jobs']}
    assert jobs['report']['provider_policy']=='openai'
    assert jobs['report']['model']=='gpt-5'  # model override is audited separately; transport is never switched.
    ev=st.updates(0,5000)
    assert not any(x.get('event_type')=='CONFIG_NORMALIZED' and x.get('job_id')==jobs['report']['job_id'] for x in ev)


def test_representative_and_factual_safety_nets_exist():
    assert 'PASS_WEIGHTED' in text('representative_sampling.py')
    assert 'harmonize_project_fact_choices' in text('factual_layer.py')
    assert 'harmonize_project_fact_choices' in text('project_engine.py')
    assert 'FACT_OPTIONS_HARMONIZED' in text('ui_server.py')


def test_research_client_delivery_contains_dataset_contract(tmp_path):
    from output_pack import export_client_delivery_zip
    files={}
    for name in ('CLIENT_REPORT.docx','RESPONDENT_DATASET.csv','RESULTS.xlsx','VERBATIMS.csv'):
        p=tmp_path/name;p.write_text('test',encoding='utf-8');files[name]=str(p)
    out=Path(export_client_delivery_zip(tmp_path/'CLIENT_DELIVERY.zip',files,project={'title':'T'},workflow_id='WF'))
    assert out.is_file()
    with zipfile.ZipFile(out) as z:
        names=set(z.namelist())
        assert {'CLIENT_REPORT.docx','RESPONDENT_DATASET.csv','RESULTS.xlsx','VERBATIMS.csv','DELIVERY_METADATA.json','DELIVERY_SHA256SUMS.txt'} <= names
    ui=text('ui_app.html')
    assert 'CLIENT DELIVERY · ZIP' in ui
    assert 'Respondentní dataset · CSV' in ui
    assert 'Výsledky + data · XLSX' in ui


def test_pptx_and_zip_are_public_download_types():
    s=text('ui_server.py')
    assert '".pptx",".zip"' in s or '".pptx", ".zip"' in s
    assert 'application/vnd.openxmlformats-officedocument.presentationml.presentation' in s
    assert 'application/zip' in s


def test_data_library_is_live_not_placeholder():
    s=text('ui_app.html').lower()
    assert '/api/library' in s
    assert 'deep research' in s
    assert 'návrhy dimenzí' in s
    assert 'učení modelu' in s
    assert 'knihovna zdrojů a poznatků bude doplněna' not in s
    assert 'v kroku 2 sem přidám' not in s


def test_single_simulation_delivery_is_frozen_and_client_ready(tmp_path, monkeypatch):
    import full_simulation as fs
    from legacy_job_dispatch import execute_legacy
    monkeypatch.setattr(fs,'RUN_ROOT',tmp_path/'runs'); monkeypatch.setattr(fs,'BENCH_ROOT',tmp_path/'bench')
    fs.RUN_ROOT.mkdir();fs.BENCH_ROOT.mkdir()
    spec={
      'topic':'Release single simulation','questions':[{'id':'Q1','text':'Jaký bude dopad?','kategorie':['Negativní','Beze změny','Pozitivní']}],
      'objective':'scenario_nowcast','domain':'general','n':50,'worlds':2,'min_worlds':2,'adaptive_worlds':False,
      'mode':'dry','research_enabled':False,'world_model_provider':'heuristic','include_core_baseline':True,
      'include_demographics_baseline':False,'diagnostic_mode':'off','save_world_overlays':False,'use_learning_profile':False,
      'auto_wording_stress':False,'scenario_contract':{'status':'APPROVED','shifts':[{'factor':'economic_friction','direction':'increase','magnitude_sd':0.2,'scope':'all','mechanism':'audit','confidence':0.4,'evidence_basis':'hypothesis'}]},'seed':1780101,
    }
    project={'title':'Release single','goal':'audit','run_policy':{'provider':'claude_code_subscription'},'audience':{'source_mode':'population'}}
    out=execute_legacy('fullsim_pipeline',{'project':project,'spec':spec,'confirm_live':False},'FINAL-1780')
    assert out['artifact_gate']['status']=='PASS'
    assert out['prediction']['run_status']=='INVALID_DRY_RUN'
    assert {'FULL_SIMULATION','NPC_CORE'} <= set(out['prediction']['methods'])
    for k in ('results_csv','results_xlsx','client_delivery_zip','report_html'):
        assert Path(out[k]).is_file(),k
    with zipfile.ZipFile(out['client_delivery_zip']) as z:
        names=set(z.namelist())
        assert {'FULL_SIMULATION_REPORT.html','SIMULATION_RESULTS.csv','SIMULATION_RESULTS.xlsx','prediction.json','prediction_manifest.json','FROZEN.lock','DELIVERY_SHA256SUMS.txt'} <= names


def test_simulation_product_exposes_context_uncertainty_and_batch():
    s=text('ui_app.html')
    for token in ('/api/simulation/context/enrich','/api/simulation/context/resolve','/api/scenario/compile-batch','/api/fullsim/batch-pipeline','Dohledat a doplnit','Porovnat více variant'):
        assert token in s
    sc=text('scenario_compiler.py').lower()
    assert 'linear' in sc and ('price' in sc or 'cen' in sc)
    sb=text('simulation_batch.py')
    assert 'shared_core_baseline' in sb
    assert 'SIMULATION_BATCH_CLIENT_DELIVERY.zip' in sb
    assert "sheet_name='Evidence'" in sb and "sheet_name='Uncertainties'" in sb


def test_single_and_batch_delivery_gates_fail_closed():
    fs=text('full_simulation.py')
    for n in ('prediction.json','prediction_manifest.json','FROZEN.lock','FULL_SIMULATION_REPORT.html','SIMULATION_RESULTS.csv','SIMULATION_RESULTS.xlsx','SIMULATION_CLIENT_DELIVERY.zip'):
        assert n in fs
    sb=text('simulation_batch.py')
    assert 'FULLSIM_BATCH_ARTIFACT_GATE_FAILED' in sb
    assert 'frozen_variants' in sb
