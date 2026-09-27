#!/usr/bin/env python3
from __future__ import annotations
import os, stat, tempfile
from pathlib import Path

def make_fake(path:Path, mode:str):
    status_text='Login method: Claude Max account' if mode=='sub' else 'Login method: Anthropic Console · API Usage Billing'
    sub='max' if mode=='sub' else None
    path.write_text(f'''#!/usr/bin/env python3\nimport json,sys\na=sys.argv[1:]\nif '--version' in a: print('2.1.999 (Claude Code)');sys.exit(0)\nif len(a)>=2 and a[0]=='auth' and a[1]=='status':\n    if '--text' in a:\n        print({status_text!r})\n    else:\n        print(json.dumps({{'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty','subscriptionType':{sub!r}}}))\n    sys.exit(0)\nif len(a)>=2 and a[0]=='auth' and a[1]=='login': sys.exit(0)\nif '-p' in a: print(json.dumps({{'result':'{{"ok":true}}','session_id':'fake'}}));sys.exit(0)\nsys.exit(0)\n''',encoding='utf-8')
    path.chmod(path.stat().st_mode|stat.S_IEXEC)

def main():
    with tempfile.TemporaryDirectory() as td:
        fake=Path(td)/'claude'
        make_fake(fake,'sub');os.environ['NPC_CLAUDE_CODE_EXE']=str(fake)
        os.environ['ANTHROPIC_API_KEY']='SHOULD_BE_SCRUBBED'
        import claude_code_setup as s
        st=s.auth_status();assert st['subscription_verified'],st
        env=s.subscription_env();assert 'ANTHROPIC_API_KEY' not in env
        import claude_code_provider as p
        h=p.health();assert h['ok'] and h['subscription_verified'],h
        r=p.structured_call(system='x',messages=[{'role':'user','content':'x'}],schema={'type':'object'},timeout=10)
        assert r['data']['ok'] is True and r['cost_usd']==0.0
        make_fake(fake,'api')
        s.invalidate_auth_cache()
        st=s.auth_status(force=True);assert not st['subscription_verified'] and st['kind']=='AUTH_UNVERIFIED',st
        try:p.text_call(system='x',messages=[{'role':'user','content':'x'}],timeout=10)
        except p.ClaudeCodeUnavailable:pass
        else:raise AssertionError('API-billed auth was not blocked')
    print('CLAUDE_CODE_ONE_CLICK_SETUP_SMOKE_PASS')
    return 0
if __name__=='__main__':raise SystemExit(main())
