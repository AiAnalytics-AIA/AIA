from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def ui_text():
    return (ROOT/'ui_app.html').read_text(encoding='utf-8')


def step1_block():
    s=ui_text(); a=s.index('// 17.7.0 STEP 1 — USER-FRIENDLY PROJECT FLOW'); b=s.index('async function boot(){',a)
    return s[a:b]


def test_questionnaire_edit_can_always_continue_to_audience():
    s=ui_text()
    assert 'onclick="continueQuestionnaireToAudience()"' in s
    block=s[s.index('function continueQuestionnaireToAudience()'):s.index('renderHome=function',s.index('function continueQuestionnaireToAudience()'))]
    assert "LAST_CHECK=null" in block
    assert "go('audience')" in block
    assert "save('questionnaire_done',false)" in block


def test_normal_step1_ui_hides_internal_methodology_and_provider_controls():
    s=ui_text(); b=step1_block()
    # Core user-facing helpers remain present, while Data Library now lives in its
    # own active product layer outside the historical STEP-1 override block.
    for f in ['projectIssuesHtml=function','checkStatusHtml=function','audPreviewHtml=function','personaSampleCard=function','renderSettings=async function']:
        assert f in b
    assert 'function renderData(){' in s
    # Data Library is a live module; historical future-facing placeholders must not survive.
    data=s[s.index("function renderData(){CURRENT='data';renderSteps();title('Data Library'"):s.index('async function uploadLibrarySource')]
    assert 'Knihovna reálných zdrojů' in data
    assert 'Deep Research robot' in data
    assert 'Knihovna zdrojů a poznatků bude doplněna' not in s
    assert 'V Kroku 2 sem přidám' not in s
    # The effective AI action shown after overrides is a simple button without provider/model selectors.
    assert "aiActionBar=function(label,action,help='')" in b
    simple=b[b.index("aiActionBar=function(label,action,help='')"):b.index('renderPromptChips=function',b.index("aiActionBar=function(label,action,help='')"))]
    assert 'providerOptions' not in simple and 'aiModelOptions' not in simple


def test_persona_prompt_chips_are_user_language_not_benchmark_diagnostics():
    s=ui_text(); a=s.rindex('renderPromptChips=function'); b=s.index('sendClaude=async function',a); block=s[a:b]
    assert 'Jaké dimenze jsou pro tento projekt důležité?' in block
    assert 'Doporuč mi personu' in block
    assert 'human benchmark' not in block.lower()
    assert 'ablac' not in block.lower()


def test_representative_sampler_matches_all_core_margins_for_full_population():
    from representative_sampling import draw_representative, DEFAULT_FIELDS
    df=pd.read_csv(ROOT/'FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz',low_memory=False)
    sample,audit=draw_representative(df,300,seed=1770)
    assert len(sample)==300 and sample['_zdroj_index'].nunique()==300
    assert audit['status']=='PASS'
    assert set(audit['fields'])==set(DEFAULT_FIELDS)
    assert audit['raw']['max_abs_pp'] <= 1.0
    assert audit['weighted']['max_abs_pp'] <= 0.5
    assert audit['selection_method'] in {'scipy_milp','largest_remainder_fallback'}


def test_representative_sampler_uses_chosen_filtered_population_as_truth():
    from representative_sampling import draw_representative
    df=pd.read_csv(ROOT/'FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz',low_memory=False)
    sub=df[pd.to_numeric(df['vek'],errors='coerce').between(25,44)].copy()
    sample,audit=draw_representative(sub,150,seed=1771)
    assert len(sample)==150
    assert pd.to_numeric(sample['vek'],errors='coerce').between(25,44).all()
    assert audit['raw']['max_abs_pp'] <= 1.0
    assert audit['weighted']['max_abs_pp'] <= 0.5


def test_project_preflight_keeps_methodology_internal_and_proves_sample(monkeypatch):
    from research_project import empty_project
    import ui_server
    monkeypatch.setattr(ui_server,"provider_key_ready",lambda _p: True)
    from ui_server import import_questionnaire_payload, project_preflight
    raw=(ROOT/'NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx').read_bytes()
    project=import_questionnaire_payload({'filename':'NPC_QUESTIONNAIRE_TEMPLATE_v17_6_0.xlsx','data_b64':base64.b64encode(raw).decode(),'project':empty_project()})['project']
    project['n']=300
    out=project_preflight(project)
    assert out['representativeness']['status']=='READY'
    assert out['representativeness']['raw_max_abs_pp'] <= 1.0
    internal_codes={x['code'] for x in out['issues']}
    assert {'JOINT_STATUS','EXTERNAL_VALIDATION'} <= internal_codes
    public_codes={x['code'] for x in out['user_issues']}
    assert 'JOINT_STATUS' not in public_codes and 'EXTERNAL_VALIDATION' not in public_codes
    for x in out['user_issues']:
        assert x.get('user_message')


def test_run_result_persists_representativeness_audit():
    s=(ROOT/'dotaznik.py').read_text(encoding='utf-8')
    assert '"representativeness": sampling_audit' in s
    assert 'sampling_audit = dict(vzorek.attrs.get("representativeness") or {})' in s


def test_final_review_is_durable_claude_only_and_defensively_sanitized():
    server=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    runtime=(ROOT/'ai_runtime.py').read_text(encoding='utf-8')
    dispatch=(ROOT/'legacy_job_dispatch.py').read_text(encoding='utf-8')
    assert '"final_review"' in runtime
    assert '_start_job(self._body(),"final_review")' in server
    assert 'elif kind=="final_review"' in dispatch
    fn=server[server.index('def final_ai_review'):server.index('def design_questionnaire')]
    assert 'prefer="claude_code_subscription"' in fn
    assert 'allow_fallback=False' in fn
    assert 'forbidden=re.compile' in fn


def test_static_navigation_keeps_commander_advanced_not_primary():
    s=ui_text(); start=s.index('<aside class="sidebar">'); end=s.index('<main class="workspace">',start); side=s[start:end]
    assert '<summary class="toolbtn"' in side and 'Pokročilé' in side
    assert '<aside class="copilot' not in s
    # Command Center belongs to the advanced navigation, not as a permanent workspace button.
    main=s[end:s.index('<script>',end)]
    assert 'Command Center' not in main
