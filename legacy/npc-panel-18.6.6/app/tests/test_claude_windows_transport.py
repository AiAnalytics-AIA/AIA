from pathlib import Path
import json, os
import claude_code_setup as setup
import claude_code_provider as provider


def _fake_claude(tmp_path:Path, structured=True):
    p=tmp_path/'fake_claude'
    payload={'type':'result','subtype':'success','result':'OK','session_id':'s1','usage':{'input_tokens':123,'output_tokens':17}}
    if structured: payload['structured_output']={'findings':[]}
    script='''#!/usr/bin/env python3\nimport json,sys,time\n_ = sys.stdin.read()\nprint(json.dumps({"type":"system","subtype":"init","model":"haiku"}),flush=True)\nprint(json.dumps({"type":"stream_event","event":{"delta":{"type":"text_delta","text":"O"}}}),flush=True)\nprint(json.dumps(PAYLOAD),flush=True)\n'''.replace('PAYLOAD',repr(payload))
    p.write_text(script,encoding='utf-8');p.chmod(0o755);return str(p)


def test_subscription_env_drops_huge_inherited_variable(monkeypatch):
    monkeypatch.setenv('NPC_ACCIDENTAL_HUGE_CONTEXT','X'*100_000)
    monkeypatch.setenv('PATH','C:/Windows;C:/Tools')
    env=setup.subscription_env()
    assert 'NPC_ACCIDENTAL_HUGE_CONTEXT' not in env
    assert all(len(str(v))<=16000 for v in env.values())
    assert 'ANTHROPIC_API_KEY' not in env


def test_research_long_payload_goes_to_stdin_and_streams(monkeypatch,tmp_path):
    exe=_fake_claude(tmp_path,structured=True)
    monkeypatch.setattr(provider,'auth_status',lambda:{'subscription_verified':True})
    monkeypatch.setattr(provider,'supports_required_cli',lambda:True)
    monkeypatch.setattr(provider,'executable',lambda:exe)
    monkeypatch.setattr(provider,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(provider,'_lock_release',lambda _slot:None)
    monkeypatch.setattr(provider,'subscription_env',lambda:{'PATH':os.environ.get('PATH','')})
    huge='ČESKÝ KONTEXT '+('data '*30_000)
    system='SYS '+('pravidlo '*8_000)
    schema={'type':'object','properties':{'findings':{'type':'array'}},'required':['findings']}
    out=provider.research_structured_call(system=system,messages=[{'role':'user','content':huge}],schema=schema)
    assert out['data']=={'findings':[]}
    assert out['tok_in']==123 and out['tok_out']==17


def test_text_stream_result(monkeypatch,tmp_path):
    exe=_fake_claude(tmp_path,structured=False)
    monkeypatch.setattr(provider,'auth_status',lambda:{'subscription_verified':True})
    monkeypatch.setattr(provider,'supports_required_cli',lambda:True)
    monkeypatch.setattr(provider,'executable',lambda:exe)
    monkeypatch.setattr(provider,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(provider,'_lock_release',lambda _slot:None)
    monkeypatch.setattr(provider,'subscription_env',lambda:{'PATH':os.environ.get('PATH','')})
    out=provider.text_call(system='sys',messages=[{'role':'user','content':'ping'}],model='haiku')
    assert out['text']=='OK'
    assert out['tok_in']==123


def test_large_schema_moves_off_command_line():
    schema={'type':'object','description':'Z'*15_000,'properties':{}}
    cli_schema,stdin_tail=provider._schema_cli_payload(schema)
    assert cli_schema is None
    assert len(stdin_tail)>10_000


def test_auth_status_skips_text_probe_when_json_proves_subscription(monkeypatch):
    calls=[]
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    def cap(cmd,timeout=30):
        calls.append(list(cmd))
        if cmd[-1]=='--version':
            return type('P',(),{'returncode':0,'stdout':'2.1.250','stderr':''})()
        return type('P',(),{'returncode':0,'stdout':json.dumps({'loggedIn':True,'authMethod':'oauth','subscriptionType':'max'}),'stderr':''})()
    monkeypatch.setattr(setup,'run_capture',cap)
    setup.invalidate_auth_cache();setup._VERSION_CACHE='';setup._VERSION_CACHE_AT=0
    st=setup.auth_status(force=True)
    assert st['subscription_verified'] is True
    assert not any('--text' in c for c in calls)
    before=len(calls); setup.auth_status(); assert len(calls)==before


def test_structured_call_retries_same_claude_when_json_schema_flag_is_unsupported(monkeypatch,tmp_path):
    p=tmp_path/'fake_claude_no_schema'
    script='''#!/usr/bin/env python3
import json,sys
args=sys.argv[1:]
text=sys.stdin.read()
if '--json-schema' in args:
    print('error: unknown option --json-schema',file=sys.stderr,flush=True)
    sys.exit(2)
print(json.dumps({'type':'system','subtype':'init','model':'haiku'}),flush=True)
print(json.dumps({'type':'result','subtype':'success','result':'{"ok":true,"note":"compat"}','session_id':'s2','usage':{'input_tokens':9,'output_tokens':5}}),flush=True)
'''
    p.write_text(script,encoding='utf-8');p.chmod(0o755)
    monkeypatch.setattr(provider,'auth_status',lambda:{'subscription_verified':True})
    monkeypatch.setattr(provider,'supports_required_cli',lambda:True)
    monkeypatch.setattr(provider,'executable',lambda:str(p))
    monkeypatch.setattr(provider,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(provider,'_lock_release',lambda _slot:None)
    monkeypatch.setattr(provider,'subscription_env',lambda:{'PATH':os.environ.get('PATH','')})
    schema={'type':'object','properties':{'ok':{'type':'boolean'},'note':{'type':'string'}},'required':['ok','note'],'additionalProperties':False}
    out=provider.structured_call(system='sys',messages=[{'role':'user','content':'test'}],schema=schema,schema_name='compat',model='haiku',max_tokens=200)
    assert out['data']=={'ok':True,'note':'compat'}
    assert out['provider']=='claude_code_subscription'
