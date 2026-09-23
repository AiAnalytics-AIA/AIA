from pathlib import Path
import json, zipfile


def test_ui_support_bundle_function_and_always_visible_button_exist():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'async function createSupportBundle' in s
    assert 'onclick="createSupportBundle(window.LAST_FAILED_JOB_ID' in s
    assert '>Diagnostika</button>' in s


def test_backend_support_bundle_routes_exist():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    assert 'path=="/api/support/bundle"' in s
    assert 'path=="/api/support/download"' in s
    assert 'from support_bundle import create_bundle' in s


def test_support_bundle_contains_debug_state_without_user_content(tmp_path, monkeypatch):
    import support_bundle as sb
    monkeypatch.setattr(sb,'DIAG',tmp_path)
    monkeypatch.setattr(sb,'_jobs',lambda _jid=None:([{'job_id':'JOB-x','input_keys':['briefing'],'input_sizes':{'briefing':999},'error':{'error':'boom'}}],[{'job_id':'JOB-x','payload':{'phase':'generating'}}]))
    monkeypatch.setattr(sb,'_claude',lambda:{'version':'2.1.229','health':{'ok':True}})
    out=sb.create_bundle('JOB-x')
    assert out.is_file()
    with zipfile.ZipFile(out) as z:
        names=set(z.namelist())
        assert {'SUMMARY.json','JOBS.json','JOB_EVENTS.json','FINGERPRINT.json','CO_POSLAT.txt'} <= names
        raw='\n'.join(z.read(n).decode('utf-8','ignore') for n in names if n.endswith('.json') or n.endswith('.txt'))
        assert '999' in raw
        assert 'No prompts' in raw


def test_fast_analysis_same_claude_plain_json_recovery(monkeypatch):
    import research_designer as rd
    import claude_code_provider as cp
    monkeypatch.setattr(rd,'_structured_with_fallback',lambda **kw: (_ for _ in ()).throw(RuntimeError('schema broke')))
    payload={
      'title':'Cena produktu','problem_summary':'Zjistit reakci na zvýšení ceny','decision_use':'Rozhodnout o ceně',
      'objectives':['Změřit reakci'],'research_questions':['Jak se změní zájem?'],'hypotheses':[],
      'tracked_sets':[],'non_object_measures':[],'questions_for_user':[],'complexity':'short',
      'method_reason':'rychlý návrh','ready_for_questionnaire':True,
    }
    monkeypatch.setattr(cp,'text_call',lambda **kw:{'text':json.dumps(payload,ensure_ascii=False),'model':'haiku'})
    out=rd.analyze_research({'goal':'Zjistit reakci na zvýšení ceny'},model='haiku',provider='claude_code_subscription',fast=True)
    assert out['title']=='Cena produktu'
    assert out['research_questions']==['Jak se změní zájem?']
    assert out['_ai']['mode']=='prompt_json_recovery'
    assert out['_ai']['provider']=='claude_code_subscription'
    assert out['_ai']['fallback_used'] is False
