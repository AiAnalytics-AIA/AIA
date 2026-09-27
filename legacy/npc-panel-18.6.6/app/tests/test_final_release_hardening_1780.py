from pathlib import Path
import json


def test_filter_references_follow_canonical_question_id_case():
    from filter_syntax import repair_filter
    fixed,note=repair_filter("O1 != 'ne'",{'o1'})
    assert fixed=="o1 != 'ne'"
    assert note


def test_compiled_project_keeps_filter_valid_after_id_slugification():
    from research_project import empty_project,compile_project
    from survey_lint import lint_questions
    p=empty_project(title='T',goal='G',n=50)
    p['decision_use']='D'
    p['sections']=[{'id':'main','title':'Main','type':'questions','questions':[
        {'id':'O1','text':'První?','typ':'vyber','kategorie':['ano','ne']},
        {'id':'O2','text':'Druhá?','typ':'vyber','kategorie':['a','b'],'filtr':"O1 != 'ne'"},
    ]}]
    q=compile_project(p)['brief']['otazky']
    assert q[0]['id']=='o1' and q[1]['filtr']=="o1 != 'ne'"
    assert lint_questions(q)['ok'] is True


def test_public_artifact_whitelist_includes_client_delivery_zip():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    start=s.index('def _publicize_workflow_paths')
    block=s[start:start+1800]
    assert '".zip"' in block
    assert 'application/zip' in s


def test_release_identity_is_consistent_1780():
    from edition_config import build_version
    assert Path('VERSION').read_text(encoding='utf-8').strip()=='18.6.6'
    assert json.loads(Path('BUILD_EDITION.json').read_text(encoding='utf-8'))['version']=='18.6.6'
    assert build_version()=='18.6.6'


def test_production_env_explicitly_disables_content_fallbacks():
    s=Path('.env.example').read_text(encoding='utf-8')
    assert 'NPC_ALLOW_LOCAL_DESIGN_FALLBACK=0' in s
    assert 'NPC_ALLOW_LOCAL_SCENARIO_FALLBACK=0' in s


def test_client_delivery_contract_exists_for_research_and_simulation():
    research=Path('worker_job.py').read_text(encoding='utf-8')
    sim=Path('full_simulation.py').read_text(encoding='utf-8')
    batch=Path('simulation_batch.py').read_text(encoding='utf-8')
    assert 'CLIENT_DELIVERY.zip' in research
    assert 'SIMULATION_CLIENT_DELIVERY.zip' in sim
    assert 'SIMULATION_BATCH_CLIENT_DELIVERY.zip' in batch
    assert 'FULLSIM_BATCH_ARTIFACT_GATE_FAILED' in batch


def test_research_client_delivery_is_fail_closed_on_missing_core_artifact():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    assert 'CLIENT_DELIVERY_ARTIFACT_GATE_FAILED' in s
    for key in ('client_report_docx','client_report_html','management_deck_pptx','questionnaire_html','respondent_dataset_csv','respondent_results_xlsx','output_manifest','client_delivery_zip'):
        assert f"'{key}'" in s
    assert "report_stage':'artifact_gate_pass'" in s


def test_supported_special_audience_presets_are_not_all_coming_soon():
    ui=Path('ui_app.html').read_text(encoding='utf-8')
    block=ui[ui.index('const SPECIAL_AUDIENCE_PRESETS='):ui.index('function chooseCustomerKind')]
    assert "kind:'population',source:'young_18_29'" in block
    assert "kind:'special',source:'healthcare_clinical_professionals'" in block
    assert "kind:'special',source:'healthcare_material_ecosystem'" in block
    assert 'PŘIPRAVENO' in ui[ui.index('function specialPresetHtml'):ui.index('function renderAudience')]
