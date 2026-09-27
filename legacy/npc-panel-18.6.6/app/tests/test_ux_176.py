from __future__ import annotations

import base64
import datetime as dt
from pathlib import Path

from job_store import JobStore
from scheduler import Scheduler
from research_project import empty_project, _clean_text
from ui_server import import_questionnaire_payload, _fullsim_spec_from_payload

ROOT=Path(__file__).resolve().parents[1]


def test_launcher_is_easy_to_find_and_unique_primary():
    assert (ROOT/'A0_NPC_PANEL_START.bat').is_file()
    assert not (ROOT/'A_NPC_PANEL_START.bat').exists()
    # Legacy AAA launcher is deliberately outside the root so A0 stays first among launchers.
    assert not (ROOT/'AAA_START_NPC_PANEL.bat').exists()
    bats=sorted(p.name for p in ROOT.glob('*.bat'))
    assert bats[0]=='A0_NPC_PANEL_START.bat'


def test_production_ux_has_requested_branching_and_no_bad_copy():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    # Questionnaire starts with exactly the three user-facing creation concepts.
    for text in ('Nahrát Excel','Sestavit ručně','Sestavit s AI','OPTIMALIZOVAT DOTAZNÍK S AI'):
        assert text in s
    # Audience first branches only to own vs AI analytics; the actual renderer returns immediately.
    audience=s[s.index('function renderAudience()'):s.index('function renderPersona()',s.index('function renderAudience()'))]
    first=audience[:audience.index("if(entry==='own')")]
    assert 'Vlastní audience' in first and 'Audience AI Analytics' in first
    assert 'Special Audience' not in first and 'Česká populace (+18)' not in first
    # 18+ branch explicitly hides Special Audience until the user navigates back.
    assert "if(choice==='special')" in audience
    assert 'Česká populace (+18)' in audience
    assert 'Special Audience už se zde nenabízí' in audience
    assert 'COMING SOON' in audience
    assert 'DOPLNIT DATA' not in s.upper()
    # Persona first branch is deliberately binary.
    persona=s[s.index('function renderPersona()'):s.index('function renderRun()',s.index('function renderPersona()'))]
    assert 'Nastavit persony sám' in persona and 'Nastavit persony pomocí AI' in persona
    assert 'Pokročilé metodické nastavení persony' not in persona


def test_production_designer_no_deterministic_router_or_ecowall_prompt():
    s=(ROOT/'research_designer.py').read_text(encoding='utf-8').lower()
    assert 'deterministický study router' not in s
    assert 'ecowall' not in s
    assert 'elections' not in s


def test_malformed_item_markup_is_cleaned():
    assert _clean_text('<\ni\nt\ne\nm\n>\nZ\nj\ni\ns\nt\ni') == 'Zjisti'
    assert _clean_text('&lt;item&gt;Zjisti&lt;/item&gt;') == 'Zjisti'


def test_questionnaire_template_round_trip():
    raw=(ROOT/'NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx').read_bytes()
    out=import_questionnaire_payload({'filename':'NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx','data_b64':base64.b64encode(raw).decode(),'project':empty_project()})
    assert out['summary']['question_count']==2
    assert out['summary']['tracked_sets']==1
    tracked=[x for x in out['project']['sections'] if x.get('type')=='object_battery'][0]
    assert 4<=len(tracked['objects'])<=15


def test_empty_project_scenario_gets_transparent_outcome_instrument():
    p=empty_project(title='',goal='Zjistit dopad zvýšení ceny o 10 % na zájem o produkt')
    spec=_fullsim_spec_from_payload({'project':p,'spec':{'topic':p['goal'],'mode':'dry','n':50,'worlds':2,'research_enabled':False}})
    assert len(spec['questions'])==1
    assert spec['questions'][0]['id']=='SCENARIO_OUTCOME'
    assert spec.get('auto_outcome_question') is True
    assert len(spec['questions'][0]['kategorie'])==5


def test_waiting_states_and_scheduled_resume_are_real(tmp_path):
    store=JobStore(tmp_path/'jobs.sqlite')
    wid=store.create_workflow(project_id='P',project_revision=1,cost_mode='REFERENCE')
    jid=store.add_job(wid,'analysis','analysis',input_data={'project':{'run_policy':{}}})
    store.transition(jid,'QUEUED'); store.transition(jid,'RUNNING'); store.transition(jid,'WAITING_CAPACITY')
    assert store.get_workflow(wid)['status']=='WAITING_CAPACITY'
    due=(dt.datetime.now()-dt.timedelta(seconds=2)).strftime('%Y-%m-%dT%H:%M:%S')
    sch=Scheduler(store,project_store_path=tmp_path/'projects.sqlite')
    sch.create({'project_id':'P','project_revision':1,'schedule_type':'one_time','schedule_expr':due,'workflow_template':{'resume_workflow_id':wid}})
    made=sch.tick(dt.datetime.now())
    assert wid in made
    assert store.get_job(jid)['status']=='QUEUED'


def test_cost_mode_has_phase_model_presets_and_override():
    from research_os_config import COST_MODES
    from workflow_engine import create_standard
    assert COST_MODES['REFERENCE']['phase_models']['research']=='sonnet'
    assert COST_MODES['REFERENCE']['phase_models']['report']=='sonnet'
    import tempfile
    store=JobStore(Path(tempfile.mkdtemp())/'jobs.sqlite')
    project=empty_project(); project['run_policy']['cost_mode']='REFERENCE'; project['run_policy']['phase_overrides']={'report':{'provider':'openai','model':'gpt-5'}}
    wf=create_standard(store,project_id='P',project_revision=1,project=project,mode='dry',confirm_live=False,cost_mode='REFERENCE')
    jobs={j['node_key']:j for j in store.get_workflow(wf['workflow_id'])['jobs']}
    assert jobs['report']['provider_policy']=='openai' and jobs['report']['model']=='gpt-5'
    ev=store.updates(0,5000); assert not any(x.get('event_type')=='CONFIG_NORMALIZED' and x.get('job_id')==jobs['report']['job_id'] for x in ev)
    assert jobs['research']['model']=='sonnet'


def test_special_audience_catalogue_exposes_supported_presets_and_upload_only_gaps():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    fn=s[s.index('function specialPresetHtml()'):s.index('function renderAudience()',s.index('function specialPresetHtml()'))]
    presets=s[s.index('const SPECIAL_AUDIENCE_PRESETS='):s.index('function chooseCustomerKind')]
    assert 'PŘIPRAVENO' in fn
    assert 'VLASTNÍ DATA' in fn
    assert "kind:'population'" in presets or "kind:'special'" in presets
    assert "kind:'coming_soon'" in presets

def test_settings_are_user_facing_and_dual_claude_runtime():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    start=s.rindex('renderSettings=async function')
    settings=s[start:s.index('async function saveClaudeApi1790',start)]
    for text in ('AI nastavení','Claude Code','Claude API','Bezpečnostní pravidlo','Žádný silent fallback'):
        assert text in settings
    assert 'explicitním potvrzení' in settings
    assert 'OpenAI' not in settings
    assert "model:'sonnet'" in s

def test_run_screen_hides_detailed_check_and_uses_business_labels():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    run=s[s.index('function renderRun()'):s.index('async function startProject',s.index('function renderRun()'))]
    assert 'Podrobná kontrola projektu' in run and '<details' in run
    for text in ('Rychle a levně','Střední cesta','Excelent','Research před spuštěním'):
        assert text in run
    assert '<h3>ECONOMY</h3>' not in run and '<h3>REFERENCE</h3>' not in run

def test_every_major_ai_builder_exposes_selected_provider_and_model():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'function aiActionBar' in s
    q=s[s.index('function renderQuestionnaire()'):s.index('function renderAudience()',s.index('function renderQuestionnaire()'))]
    persona=s[s.index('function renderPersona()'):s.index('function renderRun()',s.index('function renderPersona()'))]
    full=s[s.index('function renderFullSim()'):s.index('function wfStatusChip',s.index('function renderFullSim()'))]
    assert 'aiActionBar' in q
    assert 'aiActionBar' in persona
    assert 'providerOptions()' in full and 'aiModelOptions()' in full
