#!/usr/bin/env python3
from __future__ import annotations
import json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
LOG=ROOT/'logs'/'ai_diagnostika.txt'

def say(s=''):
    print(s,flush=True)
    try:
        LOG.parent.mkdir(parents=True,exist_ok=True)
        with LOG.open('a',encoding='utf-8') as f:f.write(s+'\n')
    except Exception: pass

def main()->int:
    try: LOG.unlink(missing_ok=True)
    except Exception: pass
    say('NPC Panel — AI diagnostika (bez úprav zdrojového kódu)')
    say('Složka: '+str(ROOT))
    say('='*68)
    from claude_code_setup import executable, version, auth_status, supports_required_cli, subscription_env
    exe=executable(); say('1/5 Claude CLI: '+(exe or 'NENALEZEN'))
    if not exe:
        say('[FAIL] Claude Code není nainstalovaný / nalezitelný.'); return 2
    say('    verze: '+(version(force=True) or '(neznámá)'))
    say('    compatibility gate: '+('PASS' if supports_required_cli() else 'FAIL'))
    env=subscription_env()
    risky=[k for k in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_BASE_URL') if k in env]
    say('2/5 Subscription environment: '+('PASS' if not risky else 'FAIL '+','.join(risky)))
    st=auth_status(force=True,cache_seconds=1)
    safe={k:v for k,v in st.items() if k not in {'raw_status','status_text','email'}}
    say('3/5 Auth/billing guard:')
    say(json.dumps(safe,ensure_ascii=False,indent=2))
    from claude_code_provider import health
    h=health(); say('4/5 NPC provider health:')
    say(json.dumps(h,ensure_ascii=False,indent=2))
    if not h.get('ok'):
        say('[FAIL] Provider není READY. Viz detail výše.'); return 3
    say('5/5 Skutečný one-word roundtrip přes Claude Code subscription...')
    t=time.time()
    try:
        from claude_code_provider import text_call
        r=text_call(system='Jsi diagnostický test. Odpověz pouze slovem OK.',messages=[{'role':'user','content':'Odpověz pouze: OK'}],model='sonnet',timeout=90)
        text=str(r.get('text') or '').strip()
        say(f'    čas: {time.time()-t:.1f} s')
        say('    odpověď: '+text[:300].replace('\n',' | '))
        say('    tokeny: in=%s out=%s'%(r.get('tok_in',0),r.get('tok_out',0)))
        if 'OK' not in text.upper():
            say('[FAIL] CLI doběhlo, ale nevrátilo očekávanou odpověď.'); return 4
    except Exception as exc:
        say(f'[FAIL] Roundtrip: {type(exc).__name__}: {exc}'); return 5
    say('[OK] Claude Code subscription runtime funguje end-to-end.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
