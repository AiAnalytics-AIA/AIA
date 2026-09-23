#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent
STATE_PATH=ROOT/'data'/'claude_code_setup.json'
LOG_DIR=ROOT/'logs';LOG_DIR.mkdir(exist_ok=True)
LOG=LOG_DIR/'claude_code_setup.log'
_AUTH_CACHE:dict[str,Any]|None=None
_AUTH_CACHE_AT=0.0
_AUTH_CACHE_SECONDS=120.0
_VERSION_CACHE=''
_VERSION_CACHE_AT=0.0
_PATH_PRIMED=False

# Variables that can make Claude Code use separately billed API/cloud credentials.
PAYG_ENV_KEYS={
    'ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL',
    'ANTHROPIC_BEDROCK_BASE_URL','ANTHROPIC_VERTEX_BASE_URL',
    'CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY',
    'AWS_BEARER_TOKEN_BEDROCK','AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN',
    'GOOGLE_APPLICATION_CREDENTIALS','ANTHROPIC_VERTEX_PROJECT_ID',
    # Never let an externally injected OAuth/API token or model override shadow the
    # locally authenticated Claude subscription used by this provider.
    'CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_CUSTOM_HEADERS','ANTHROPIC_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_SMALL_FAST_MODEL','ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION',
}

def log(msg:str):
    line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line,flush=True)
    with LOG.open('a',encoding='utf-8') as f:f.write(line+'\n')

def subscription_env()->dict[str,str]:
    """Return a small, Windows-safe environment for Claude Code subscription calls.

    Do NOT inherit the entire parent process environment.  On Windows a single
    oversized inherited variable can make CreateProcess fail before Claude starts
    ("the environment variable is longer than 32767 characters").  Research/project
    payloads belong on stdin/files, never in environment variables.
    """
    # OS/runtime variables required for process startup, profile/keychain discovery,
    # networking and enterprise proxy/certificate setups. Everything else is dropped.
    keep = {
        'PATH','PATHEXT','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC',
        'USERPROFILE','HOME','HOMEDRIVE','HOMEPATH','APPDATA','LOCALAPPDATA',
        'TEMP','TMP','PROGRAMDATA','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432',
        'USERNAME','USERDOMAIN','COMPUTERNAME','LANG','LC_ALL','TZ',
        'HTTP_PROXY','HTTPS_PROXY','NO_PROXY','ALL_PROXY','SSL_CERT_FILE','SSL_CERT_DIR',
        'REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS',
        'CLAUDE_CONFIG_DIR','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME',
    }
    env:dict[str,str] = {}
    dropped_oversize=[]
    for k,v in os.environ.items():
        ku=k.upper()
        if ku not in keep:
            continue
        sv=str(v)
        # Be comfortably below the documented Windows per-variable ceiling.
        if len(sv) > 16000:
            dropped_oversize.append(k)
            continue
        env[k]=sv
    for k in PAYG_ENV_KEYS:
        env.pop(k,None)
    # Stable subscription runtime. Updates are handled explicitly.
    env['DISABLE_AUTOUPDATER']='1'
    env['DISABLE_UPDATES']='1'
    env['CLAUDE_CODE_DISABLE_AUTO_MEMORY']='1'
    env['CLAUDE_CODE_SKIP_PROMPT_HISTORY']='1'
    # NPC uses Claude Code only as an isolated model transport. Disable user/claude.ai
    # MCP customizations for these subprocesses. Newer Claude Code honors safe mode;
    # ENABLE_CLAUDEAI_MCP_SERVERS=false additionally blocks managed claude.ai MCPs.
    # Older builds simply ignore unknown environment flags and are still isolated by
    # --strict-mcp-config with a valid empty {mcpServers:{}} file.
    env['CLAUDE_CODE_SAFE_MODE']='1'
    env['ENABLE_CLAUDEAI_MCP_SERVERS']='false'
    env['PYTHONUTF8']='1';env['PYTHONIOENCODING']='utf-8'
    if os.name=='nt':
        localbin=Path.home()/'.local'/'bin'
        npm=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'npm'
        localapp=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))
        extras=[localbin,localapp/'Microsoft'/'WinGet'/'Links',localapp/'Microsoft'/'WindowsApps',npm,Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs']
        base=env.get('PATH') or os.environ.get('PATH','')
        # PATH itself can be polluted/duplicated on long-lived desktop sessions.
        if len(base)>12000:
            base=os.pathsep.join(x for x in base.split(os.pathsep) if x)[:12000]
        env['PATH']=os.pathsep.join([str(x) for x in extras if x.exists()]+([base] if base else []))
    if dropped_oversize:
        env['NPC_ENV_OVERSIZE_DROPPED']=','.join(dropped_oversize)[:1000]
    return env

def refresh_process_path(*, force:bool=False):
    """Prime the Windows PATH exactly once without duplicating entries."""
    global _PATH_PRIMED
    if os.name!='nt':return
    if _PATH_PRIMED and not force:return
    localapp=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))
    extras=[Path.home()/'.local'/'bin',localapp/'Microsoft'/'WinGet'/'Links',localapp/'Microsoft'/'WindowsApps',Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'npm',Path(os.environ.get('ProgramFiles','C:/Program Files'))/'nodejs']
    existing=[x for x in str(os.environ.get('PATH','')).split(os.pathsep) if x]
    seen={os.path.normcase(os.path.normpath(x)) for x in existing}
    prefix=[]
    for x in extras:
        sx=str(x)
        nx=os.path.normcase(os.path.normpath(sx))
        if x.exists() and nx not in seen:
            prefix.append(sx);seen.add(nx)
    os.environ['PATH']=os.pathsep.join(prefix+existing)
    _PATH_PRIMED=True

def executable()->str|None:
    override=os.environ.get('NPC_CLAUDE_CODE_EXE','').strip()
    if override and Path(override).is_file():return override
    refresh_process_path()
    if os.name=='nt':
        # Prefer the native installer path to avoid an old Claude Desktop WindowsApps shim shadowing the CLI.
        p=Path.home()/'.local'/'bin'/'claude.exe'
        if p.is_file():return str(p)
    for name in ('claude','claude.exe','claude.cmd'):
        p=shutil.which(name)
        if p:return p
    return None

def run_capture(cmd:list[str],timeout=30)->subprocess.CompletedProcess[str]:
    return subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,env=subscription_env())

def version(*,force:bool=False)->str:
    global _VERSION_CACHE,_VERSION_CACHE_AT
    if not force and _VERSION_CACHE and time.monotonic()-_VERSION_CACHE_AT<300:
        return _VERSION_CACHE
    exe=executable()
    if not exe:return ''
    try:
        p=run_capture([exe,'--version'],5)
        _VERSION_CACHE=((p.stdout or '')+' '+(p.stderr or '')).strip()[:300]
        _VERSION_CACHE_AT=time.monotonic();return _VERSION_CACHE
    except Exception:return ''


def supports_required_cli()->bool:
    """Compatibility gate for Claude Code print mode.

    Do not pin an arbitrary patch release.  Claude Code can change the textual
    version/status shape independently of the print-mode contract and valid
    installations have been observed with missing subscription metadata.  NPC
    therefore uses a very low major/minor sanity floor and lets the *real*
    non-interactive invocation be the authoritative capability check.  An
    unparseable version is not itself a reason to block a working CLI.
    """
    exe=executable()
    if not exe:return False
    try:
        import re
        raw=version()
        m=re.search(r'(\d+)\.(\d+)\.(\d+)', raw or '')
        if not m:
            return True
        ver=tuple(int(x) for x in m.groups())
        return ver >= (2,1,0)
    except Exception:
        return True

def _credential_subscription_hint()->dict[str,str]:
    """Read only non-secret billing metadata from Claude's local credential file.

    Some Claude Code builds omit ``subscriptionType`` from ``auth status`` even
    when the locally stored OAuth credential knows the plan.  Never return token
    material from this helper.
    """
    candidates=[Path.home()/'.claude'/'.credentials.json']
    for cp in candidates:
        try:
            if not cp.is_file():
                continue
            obj=json.loads(cp.read_text(encoding='utf-8'))
            if not isinstance(obj,dict):
                continue
            found={'subscription_type':'','billing_type':''}
            def walk(node):
                if isinstance(node,dict):
                    for k,v in node.items():
                        kl=str(k).lower()
                        if kl=='subscriptiontype' and not found['subscription_type'] and isinstance(v,(str,int,float)):
                            found['subscription_type']=str(v).lower().strip()
                        elif kl=='billingtype' and not found['billing_type'] and isinstance(v,(str,int,float)):
                            found['billing_type']=str(v).lower().strip()
                        elif isinstance(v,(dict,list)):
                            walk(v)
                elif isinstance(node,list):
                    for v in node:
                        if isinstance(v,(dict,list)): walk(v)
            walk(obj)
            return {'subscription_type':found['subscription_type'],'billing_type':found['billing_type'],'source':'credential_metadata'}
        except Exception:
            continue
    return {'subscription_type':'','billing_type':'','source':''}


def auth_status(*,force:bool=False,cache_seconds:float=_AUTH_CACHE_SECONDS)->dict[str,Any]:
    """Subscription-safe readiness check with tolerant metadata handling.

    ``subscriptionType`` is useful evidence but is not a reliable required field:
    valid Claude Pro/Max OAuth sessions can omit it.  NPC therefore accepts a
    logged-in first-party Claude OAuth session when there is no API/Console billing
    signal and all API credential environment variables are scrubbed before the
    provider starts.  The real ``claude -p`` invocation remains the authoritative
    capability check.
    """
    global _AUTH_CACHE,_AUTH_CACHE_AT
    if not force and _AUTH_CACHE and (time.monotonic()-_AUTH_CACHE_AT)<max(1.0,float(cache_seconds)):
        return dict(_AUTH_CACHE)
    exe=executable()
    if not exe:
        out={'installed':False,'logged_in':False,'subscription_verified':False,'subscription_candidate':False,'kind':'MISSING','message':'Claude Code není nainstalovaný.'}
        _AUTH_CACHE=out;_AUTH_CACHE_AT=time.monotonic();return dict(out)
    js:dict[str,Any]={};txt='';rc_json=1
    try:
        p=run_capture([exe,'auth','status'],8);rc_json=p.returncode
        raw=(p.stdout or '').strip()
        try:js=json.loads(raw) if raw else {}
        except Exception:js={}
    except Exception as e:js={'error':str(e)}

    auth_method=str(js.get('authMethod') or '').lower().strip()
    api_provider=str(js.get('apiProvider') or '').lower().strip()
    sub=str(js.get('subscriptionType') or '').lower().strip()
    logged=bool(js.get('loggedIn')) or rc_json==0
    explicit_sub=any(sub.startswith(x) for x in ('pro','max','team','enterprise'))

    # Read text only when JSON did not already prove a subscription.
    sub_text=False;bad_text=False
    if not (logged and explicit_sub):
        try:
            p2=run_capture([exe,'auth','status','--text'],8)
            txt=((p2.stdout or '')+'\n'+(p2.stderr or '')).strip()
        except Exception as e:txt=str(e)
        lower=txt.lower()
        sub_text=(('login method:' in lower and any(x in lower for x in ('claude max account','claude pro account','claude team account','claude enterprise account')))
                  or ('claude account with subscription' in lower)
                  or any(('subscription type: '+x) in lower for x in ('pro','max','team','enterprise')))
        bad_text=any(x in lower for x in ('api usage billing','anthropic console','credentials-file','login method: api key','api key billing'))
        logged=logged or sub_text

    hint=_credential_subscription_hint() if logged and not explicit_sub and not sub_text else {'subscription_type':'','billing_type':'','source':''}
    hinted_sub=any(str(hint.get('subscription_type') or '').startswith(x) for x in ('pro','max','team','enterprise'))
    hinted_billing=str(hint.get('billing_type') or '').lower()

    # Hard fail on explicit pay-as-you-go / enterprise cloud routes.
    bad_auth=auth_method in {'api_key','console','none'}
    bad_provider=api_provider in {'bedrock','vertex','foundry','aws','gcp'}
    bad_hint=any(x in hinted_billing for x in ('api','console','usage')) and 'subscription' not in hinted_billing

    oauth_like=auth_method in {'claude.ai','oauth','oauth_token','oauth-token','oauth2'} or 'oauth' in auth_method
    # Some valid Claude subscription sessions omit BOTH subscriptionType and
    # authMethod.  A successful logged-in first-party status with no API/Console
    # billing signal is therefore a candidate, not a failure.  The real `claude
    # -p` call remains the authoritative capability check.
    first_party=(not api_provider) or api_provider in {'firstparty','first_party','anthropic'}
    auth_metadata_missing=(not auth_method)
    metadata_missing_candidate=bool(logged and (oauth_like or auth_metadata_missing) and first_party and not (bad_auth or bad_provider or bad_text or bad_hint))

    verified=bool(logged and not (bad_auth or bad_provider or bad_text or bad_hint) and (explicit_sub or sub_text or hinted_sub or metadata_missing_candidate))
    if explicit_sub: basis='auth_json_subscription'
    elif sub_text: basis='auth_text_subscription'
    elif hinted_sub: basis='credential_subscription_metadata'
    elif metadata_missing_candidate: basis='first_party_oauth_without_subscriptionType'
    else: basis=''

    if verified:
        kind='SUBSCRIPTION_READY'
        if basis=='first_party_oauth_without_subscriptionType':
            message='Claude Code je přihlášen přes first-party OAuth; subscriptionType chybí, proto NPC ověří použitelnost skutečným Claude print-mode voláním.'
        else:
            message='Claude Code je přihlášen přes Claude předplatné.'
    elif logged:
        kind='AUTH_UNVERIFIED';message='Claude Code je přihlášen, ale přihlášení vypadá jako API/Console nebo jiný neověřený billing. NPC ho pro subscription LIVE nepoužije.'
    else:
        kind='LOGIN_REQUIRED';message='Claude Code není přihlášen přes Claude účet.'

    out={
        'installed':True,'logged_in':logged,'subscription_verified':verified,'subscription_candidate':metadata_missing_candidate,
        'verification_basis':basis,'kind':kind,'message':message,'version':version(),
        'auth_method':js.get('authMethod'),'api_provider':js.get('apiProvider'),'subscription_type':js.get('subscriptionType') or hint.get('subscription_type') or None,
        'billing_type_hint':hint.get('billing_type') or None,'email':js.get('email'),'status_text':txt[:1200],'executable':exe,'api_env_scrubbed':True,
        'raw_status':{k:v for k,v in js.items() if k not in {'token','accessToken','refreshToken','apiKey'}},
    }
    _AUTH_CACHE=out;_AUTH_CACHE_AT=time.monotonic();return dict(out)

def invalidate_auth_cache()->None:
    global _AUTH_CACHE,_AUTH_CACHE_AT
    _AUTH_CACHE=None;_AUTH_CACHE_AT=0.0

def _run_stream(cmd:list[str],timeout=600)->int:
    log('$ '+' '.join(cmd))
    try:
        p=subprocess.run(cmd,cwd=ROOT,env=subscription_env(),timeout=timeout)
        log(f'return_code={p.returncode}');return int(p.returncode)
    except Exception as e:log(f'ERROR: {e}');return 1

def install_windows(force:bool=False)->bool:
    refresh_process_path()
    if executable() and not force:return True
    # Anthropic currently recommends the native installer. Pin the stable channel
    # for a predictable scripted runtime, then use WinGet only as a fallback.
    powershell=shutil.which('powershell.exe') or shutil.which('powershell') or shutil.which('pwsh')
    if powershell:
        log('Instaluji Claude Code přes oficiální Anthropic native installer (stable)…')
        script="[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; & ([scriptblock]::Create((irm https://claude.ai/install.ps1))) stable"
        rc=_run_stream([powershell,'-NoProfile','-ExecutionPolicy','Bypass','-Command',script],600)
        refresh_process_path()
        if rc==0 and executable():return True
    winget=shutil.which('winget')
    if winget:
        log('Native instalace nebyla dostupná/úspěšná. Zkouším Windows Package Manager…')
        rc=_run_stream([winget,'install','-e','--id','Anthropic.ClaudeCode','--accept-source-agreements','--accept-package-agreements','--silent'],600)
        refresh_process_path()
        if rc==0 and executable():return True
    return False

def install()->bool:
    exe=executable()
    if exe and supports_required_cli():return True
    if exe:log('Nalezený Claude Code je starší/nekompatibilní s bezpečným NPC runtime. Aktualizuji stabilní nativní build…')
    if os.name=='nt':return install_windows(force=bool(exe)) and supports_required_cli()
    if exe:return supports_required_cli()
    log('Automatická instalace Claude Code je v tomto balíku určena pro Windows.');return False

def save_state(st:dict[str,Any]):
    STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    safe={k:v for k,v in st.items() if k not in {'raw_status','status_text','email'}}
    safe['checked_at']=time.strftime('%Y-%m-%dT%H:%M:%S')
    STATE_PATH.write_text(json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf-8')

def login_subscription(email:str='')->bool:
    exe=executable()
    if not exe:return False
    cmd=[exe,'auth','login']
    if email.strip():cmd += ['--email',email.strip()]
    log('Otevírám oficiální Claude přihlášení. Přihlašovací údaje zadáváte pouze Anthropic/Claude, NPC je nevidí ani neukládá.')
    log('$ claude auth login'+(' --email [prefilled]' if email.strip() else ''))
    try:
        p=subprocess.run(cmd,cwd=ROOT,env=subscription_env(),timeout=900)
        log(f'return_code={p.returncode}');invalidate_auth_cache();return p.returncode==0
    except Exception as e:
        log(f'LOGIN ERROR: {e}');return False

def ensure_ready(interactive:bool=True,force_login:bool=False)->dict[str,Any]:
    LOG.write_text(f"NPC CLAUDE CODE SETUP — {time.strftime('%Y-%m-%d %H:%M:%S')}\n",encoding='utf-8')
    if not install():
        st=auth_status();st['message']='Automatická instalace Claude Code se nezdařila. NPC lze spustit přes API; Claude Code zůstává fail-closed.';save_state(st);return st
    st=auth_status()
    if st.get('subscription_verified') and not force_login:save_state(st);return st
    if interactive:
        log('Claude subscription zatím není bezpečně ověřena.')
        try:email=input('E-mail k Claude Pro/Max účtu (Enter = doplníte v prohlížeči): ').strip()
        except EOFError:email=''
        login_subscription(email)
        st=auth_status()
    save_state(st)
    return st

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--status',action='store_true');ap.add_argument('--interactive',action='store_true');ap.add_argument('--force-login',action='store_true');a=ap.parse_args()
    if a.status:
        st=auth_status();print(json.dumps(st,ensure_ascii=False,indent=2));return 0 if st.get('subscription_verified') else 2
    st=ensure_ready(interactive=a.interactive or not a.status,force_login=a.force_login)
    print('\n'+st.get('message',''))
    if st.get('subscription_verified'):
        print('Claude Code subscription: READY')
        return 0
    print('Claude Code subscription: NOT READY (NPC z bezpečnostních důvodů nepoužije placené API automaticky).')
    return 2

if __name__=='__main__':raise SystemExit(main())
