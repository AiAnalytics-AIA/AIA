from pathlib import Path
import json, os
import claude_code_provider as cp


def _setup(monkeypatch, exe):
    monkeypatch.setattr(cp,'auth_status',lambda:{'subscription_verified':True,'verification_basis':'test'})
    monkeypatch.setattr(cp,'supports_required_cli',lambda:True)
    monkeypatch.setattr(cp,'executable',lambda:str(exe))
    monkeypatch.setattr(cp,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(cp,'_lock_release',lambda _slot:None)
    monkeypatch.setattr(cp,'subscription_env',lambda:{'PATH':os.environ.get('PATH','')})


def test_every_structured_step_recovers_malformed_json_with_same_claude(monkeypatch,tmp_path):
    fake=tmp_path/'claude'
    fake.write_text('''#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]; text=sys.stdin.read()
print(json.dumps({'type':'system','subtype':'init','model':'sonnet'}),flush=True)
if '--json-schema' in args:
    print(json.dumps({'type':'result','subtype':'success','result':'not valid json','session_id':'bad'}),flush=True)
else:
    print(json.dumps({'type':'result','subtype':'success','result':'{"ok":true,"label":"recovered"}','session_id':'good'}),flush=True)
''',encoding='utf-8');fake.chmod(0o755);_setup(monkeypatch,fake)
    schema={'type':'object','properties':{'ok':{'type':'boolean'},'label':{'type':'string'}},'required':['ok','label'],'additionalProperties':False}
    out=cp.structured_call(system='system',messages=[{'role':'user','content':'do it'}],schema=schema,schema_name='any_product_stage',model='sonnet',max_tokens=200)
    assert out['data']=={'ok':True,'label':'recovered'}
    assert out['provider']=='claude_code_subscription'
    assert out['fallback_used'] is False
    assert out['mode']=='same_claude_prompt_json_recovery'


def test_windows_unknown_safe_mode_retries_minimal_same_claude(monkeypatch,tmp_path):
    fake=tmp_path/'claude'
    fake.write_text('''#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]; text=sys.stdin.read()
if '--safe-mode' in args:
    print('error: unknown option --safe-mode',file=sys.stderr,flush=True);sys.exit(2)
print(json.dumps({'type':'system','subtype':'init','model':'haiku'}),flush=True)
print(json.dumps({'type':'result','subtype':'success','result':'{"ok":true}','session_id':'compat'}),flush=True)
''',encoding='utf-8');fake.chmod(0o755);_setup(monkeypatch,fake)
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
    out=cp.structured_call(system='sys',messages=[{'role':'user','content':'test'}],schema=schema,schema_name='windows_compat',model='haiku',max_tokens=100)
    assert out['data']=={'ok':True}
    assert out['provider']=='claude_code_subscription'
    assert out.get('fallback_used') is False


def test_ux_has_permanent_product_switch_library_and_dimension_guide():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'productSwitch' in s
    assert "switchProduct1776('research')" in s
    assert "switchProduct1776('simulation')" in s
    assert "switchProduct1776('library')" in s
    assert 'Data Library' in s
    assert 'audienceDimensionGuide1776' in s
    assert 'function options(values,current)' in s
    assert 'ensureAnalysis1776' in s
    assert "provider:'claude_code_subscription'" in s


def test_ui_ai_chain_self_heals_missing_analysis_before_questionnaire():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    start=s.index('buildQuestionnaire=async function')
    block=s[start:start+1500]
    assert 'await ensureAnalysis1776()' in block
    assert 'await ensureClaudeReady1776()' in block
    assert '/api/research/build_questionnaire' in block


def test_ai_diagnostics_are_claude_only(monkeypatch):
    import provider_diagnostics as pd
    import claude_code_setup as setup
    import claude_code_provider as provider
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'version',lambda:'2.1.229')
    monkeypatch.setattr(setup,'auth_status',lambda **kw:{'subscription_verified':True,'verification_basis':'test'})
    monkeypatch.setattr(provider,'health',lambda:{'ok':True,'provider':'claude_code_subscription'})
    import ai_router
    monkeypatch.setattr(ai_router,'roundtrip_test',lambda prefer=None:{'ok':True,'provider':'claude_code_subscription','model':'haiku','message':'ok'})
    r=pd.full_report(live=True)
    assert r['ok'] is True
    assert r['provider']=='claude_code_subscription'
    assert 'anthropic' not in r and 'openai' not in r


def test_settings_show_real_end_to_end_ai_test_result():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'Otestovat AI end-to-end' in s
    assert 'aiDiagSimple1777' in s
    assert 'Claude Code funguje end-to-end' in Path('provider_diagnostics.py').read_text(encoding='utf-8')


def test_real_product_ai_handlers_share_one_claude_runtime(monkeypatch,tmp_path):
    """Smoke the actual handler chain, not only the provider helper."""
    fake=tmp_path/'claude_flow'
    fake.write_text(r'''#!/usr/bin/env python3
import sys,json
args=sys.argv[1:]; _=sys.stdin.read()
def gen(s):
    if not isinstance(s,dict):return None
    if s.get('enum'):return s['enum'][0]
    t=s.get('type')
    if isinstance(t,list):t=next((x for x in t if x!='null'),'string')
    if t=='object':
        props=s.get('properties') or {}
        return {k:gen(props.get(k,{})) for k in (s.get('required') or [])}
    if t=='array':return [gen(s.get('items') or {}) for _ in range(int(s.get('minItems') or 0))]
    if t=='boolean':return True
    if t=='integer':return int(s.get('minimum') or 1)
    if t=='number':return float(s.get('minimum') or 1)
    return 'test'
schema=None
if '--json-schema' in args:
    i=args.index('--json-schema');schema=json.loads(args[i+1])
obj=gen(schema) if schema else {'ok':True}
print(json.dumps({'type':'system','subtype':'init','model':'sonnet'}),flush=True)
print(json.dumps({'type':'result','subtype':'success','result':json.dumps(obj,ensure_ascii=False),'structured_output':obj,'session_id':'flow'},ensure_ascii=False),flush=True)
''',encoding='utf-8');fake.chmod(0o755);_setup(monkeypatch,fake)
    import ui_server, audience
    analysis=ui_server.analyze_research_brief({'briefing':{'goal':'Zjistit reakci na cenu'},'n':100,'provider':'claude_code_subscription','model':'haiku'})
    questionnaire=ui_server.build_research_questionnaire({'analysis':analysis['analysis'],'briefing':{'goal':'Zjistit reakci na cenu'},'project':analysis['project'],'n':100,'provider':'claude_code_subscription','model':'sonnet'})
    aud=audience.propose_filters(ui_server.core.load_panel_cached(),'lidé 25 až 44 let',model='haiku',provider='claude_code_subscription')
    persona=ui_server.suggest_persona_dimensions({'project':analysis['project'],'provider':'claude_code_subscription','model':'sonnet','dimension_labels':{'price_sensitivity':'Cenová citlivost'}})
    review=ui_server.final_ai_review({'project':analysis['project'],'provider':'claude_code_subscription','model':'sonnet'})
    assert analysis['fast_brief_analysis'] is True
    assert isinstance(questionnaire,dict) and isinstance(aud,dict) and isinstance(persona,dict) and isinstance(review,dict)
