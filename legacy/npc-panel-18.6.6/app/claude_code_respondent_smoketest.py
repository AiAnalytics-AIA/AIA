#!/usr/bin/env python3
"""Offline end-to-end regression for Claude Code respondent transport.

Uses a fake local Claude executable. It exercises auth -> provider -> questionnaire
-> pipeline -> parsing -> zero incremental API cost without contacting Anthropic.
"""
from __future__ import annotations
import json, os, stat, tempfile
from pathlib import Path

def main()->int:
    old=os.environ.get('NPC_CLAUDE_CODE_EXE')
    keys=('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','OPENAI_API_KEY')
    oldkeys={k:os.environ.get(k) for k in keys}
    try:
        with tempfile.TemporaryDirectory() as td:
            fake=Path(td)/('claude.cmd' if os.name=='nt' else 'claude')
            if os.name=='nt':
                # Windows CI is not used for this package audit; keep a readable guard.
                raise RuntimeError('Fake executable smoke is intended for POSIX package validation; Windows uses real CLI health.')
            fake.write_text('''#!/usr/bin/env python3\nimport json,sys\na=sys.argv[1:]\nif '--version' in a: print('2.1.999 (Claude Code)');sys.exit(0)\nif len(a)>=2 and a[0]=='auth' and a[1]=='status':\n    if '--text' in a: print('Login method: Claude Max account\\nSubscription type: Max')\n    else: print(json.dumps({'loggedIn':True,'authMethod':'oauth','apiProvider':'firstParty','subscriptionType':'max'}))\n    sys.exit(0)\nif '-p' in a:\n    print(json.dumps({'result':json.dumps({'probabilities':[0.7,0.3]}),'session_id':'fake-live'}));sys.exit(0)\nsys.exit(0)\n''',encoding='utf-8')
            fake.chmod(fake.stat().st_mode|stat.S_IEXEC)
            os.environ['NPC_CLAUDE_CODE_EXE']=str(fake)
            for k in keys: os.environ.pop(k,None)
            from dotaznik import run_dotaznik
            r=run_dotaznik([
                {'id':'Q1','text':'Která varianta se vám líbí více?','typ':'vyber','kategorie':['A','B'],'povolit_nevim':False}
            ],n=3,mode='sync',workers=1,ulozit=False,tichy=True,seed=123,response_mode='probability',
              provider_policy='strict_claude_code_subscription',model='sonnet',budget_max_usd=1.0)
            assert r['provider']=='claude_code_subscription'
            assert float(r['naklady_usd'])==0.0
            assert r['budget']['provider']=='claude_code_subscription' and float(r['budget']['spent_usd'])==0.0
            assert int(r['n_chyb'])==0
            assert r['vysledky']['Q1']['expected_pct']['A']>r['vysledky']['Q1']['expected_pct']['B']
            print('CLAUDE_CODE_RESPONDENT_E2E_FAKE_PASS')
            return 0
    finally:
        if old is None: os.environ.pop('NPC_CLAUDE_CODE_EXE',None)
        else: os.environ['NPC_CLAUDE_CODE_EXE']=old
        for k,v in oldkeys.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v

if __name__=='__main__': raise SystemExit(main())
