import json
import claude_code_setup as setup


def _cp(rc=0,out='',err=''):
    return type('P',(),{'returncode':rc,'stdout':out,'stderr':err})()


def test_missing_subscription_type_first_party_oauth_is_not_false_block(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'_credential_subscription_hint',lambda:{'subscription_type':'','billing_type':'','source':''})
    def cap(cmd,timeout=30):
        if '--version' in cmd:
            return _cp(out='2.1.100 (Claude Code)')
        if '--text' in cmd:
            return _cp(out='Logged in with Claude account')
        return _cp(out=json.dumps({'loggedIn':True,'authMethod':'oauth_token','apiProvider':'firstParty'}))
    monkeypatch.setattr(setup,'run_capture',cap)
    setup.invalidate_auth_cache(); setup._VERSION_CACHE=''; setup._VERSION_CACHE_AT=0
    st=setup.auth_status(force=True)
    assert st['subscription_verified'] is True
    assert st['verification_basis']=='first_party_oauth_without_subscriptionType'


def test_console_api_billing_stays_blocked_without_subscription_type(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'_credential_subscription_hint',lambda:{'subscription_type':'','billing_type':'','source':''})
    def cap(cmd,timeout=30):
        if '--version' in cmd:
            return _cp(out='2.1.100 (Claude Code)')
        if '--text' in cmd:
            return _cp(out='Login method: Anthropic Console · API Usage Billing')
        return _cp(out=json.dumps({'loggedIn':True,'authMethod':'oauth_token','apiProvider':'firstParty'}))
    monkeypatch.setattr(setup,'run_capture',cap)
    setup.invalidate_auth_cache(); setup._VERSION_CACHE=''; setup._VERSION_CACHE_AT=0
    st=setup.auth_status(force=True)
    assert st['subscription_verified'] is False
    assert st['kind']=='AUTH_UNVERIFIED'


def test_hard_patch_version_pin_removed(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'version',lambda **kwargs:'2.1.100 (Claude Code)')
    assert setup.supports_required_cli() is True


def test_unparseable_version_does_not_false_block_working_executable(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'version',lambda **kwargs:'Claude Code stable')
    assert setup.supports_required_cli() is True


def test_missing_subscription_type_can_reach_real_provider_call(monkeypatch,tmp_path):
    import os
    import claude_code_provider as provider
    fake=tmp_path/'claude'
    fake.write_text('''#!/usr/bin/env python3\nimport json,sys\na=sys.argv[1:]\nif '--version' in a: print('2.1.100 (Claude Code)');sys.exit(0)\nif len(a)>=2 and a[0]=='auth' and a[1]=='status':\n    if '--text' in a: print('Logged in with Claude account');sys.exit(0)\n    print(json.dumps({'loggedIn':True,'authMethod':'oauth_token','apiProvider':'firstParty'}));sys.exit(0)\n_ = sys.stdin.read()\nprint(json.dumps({'type':'system','subtype':'init','model':'haiku'}),flush=True)\nprint(json.dumps({'type':'result','subtype':'success','result':'OK','session_id':'s','usage':{'input_tokens':4,'output_tokens':1}}),flush=True)\n''',encoding='utf-8')
    fake.chmod(0o755)
    monkeypatch.setenv('NPC_CLAUDE_CODE_EXE',str(fake))
    monkeypatch.setattr(setup,'_credential_subscription_hint',lambda:{'subscription_type':'','billing_type':'','source':''})
    setup.invalidate_auth_cache(); setup._VERSION_CACHE=''; setup._VERSION_CACHE_AT=0
    monkeypatch.setattr(provider,'_acquire_slot',lambda **kwargs:None)
    monkeypatch.setattr(provider,'_lock_release',lambda _slot:None)
    out=provider.text_call(system='x',messages=[{'role':'user','content':'ping'}],model='haiku',timeout=10)
    assert out['text']=='OK'
    assert out['subscription_verified'] is True


def test_missing_auth_method_and_subscription_type_logged_in_first_party_not_false_block(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'_credential_subscription_hint',lambda:{'subscription_type':'','billing_type':'','source':''})
    def cap(cmd,timeout=30):
        if '--version' in cmd:
            return _cp(out='Claude Code stable')
        if '--text' in cmd:
            return _cp(out='Logged in with Claude account')
        return _cp(out=json.dumps({'loggedIn':True,'apiProvider':'firstParty'}))
    monkeypatch.setattr(setup,'run_capture',cap)
    setup.invalidate_auth_cache(); setup._VERSION_CACHE=''; setup._VERSION_CACHE_AT=0
    st=setup.auth_status(force=True)
    assert st['subscription_verified'] is True
    assert st['subscription_candidate'] is True


def test_missing_auth_method_still_blocks_explicit_console_billing(monkeypatch):
    monkeypatch.setattr(setup,'executable',lambda:'claude')
    monkeypatch.setattr(setup,'_credential_subscription_hint',lambda:{'subscription_type':'','billing_type':'','source':''})
    def cap(cmd,timeout=30):
        if '--version' in cmd:
            return _cp(out='Claude Code stable')
        if '--text' in cmd:
            return _cp(out='Anthropic Console · API Usage Billing')
        return _cp(out=json.dumps({'loggedIn':True,'apiProvider':'firstParty'}))
    monkeypatch.setattr(setup,'run_capture',cap)
    setup.invalidate_auth_cache(); setup._VERSION_CACHE=''; setup._VERSION_CACHE_AT=0
    st=setup.auth_status(force=True)
    assert st['subscription_verified'] is False
    assert st['kind']=='AUTH_UNVERIFIED'
