from __future__ import annotations

import json, os, queue, signal, subprocess, tempfile, threading, time, shutil
from pathlib import Path
from typing import Any

from claude_code_setup import executable, auth_status, subscription_env, supports_required_cli
from ai_execution_context import report as runtime_report, cancel_requested

ROOT = Path(__file__).resolve().parent
LOCK_PATH = ROOT/'data'/'claude_code_subscription.lock'
PROVIDER_ID = 'claude_code_subscription'

class ClaudeCodeUnavailable(RuntimeError): pass
class ClaudeCodeLimit(RuntimeError): pass
class ClaudeCodeCancelled(RuntimeError): pass


def _cleanup_temp_dir(path:str|Path)->None:
    """Best-effort Windows-safe cleanup that never masks provider status.

    Claude Code can briefly keep its cwd open after the top-level process exits.
    ``TemporaryDirectory.__exit__`` used to raise WinError 32 and overwrite the
    real QUOTA/rate-limit result. Cleanup is retried and then deferred silently.
    """
    p=Path(path); last=None
    for delay in (0.0,0.15,0.5,1.0):
        if delay: time.sleep(delay)
        try:
            shutil.rmtree(p)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last=exc
    try:
        runtime_report({'phase':'Claude Code · temp cleanup odložen; provider výsledek zachován',
                        'provider_stage':'temp_cleanup_deferred','temp_path':str(p),
                        'cleanup_error':str(last)[:500]})
    except Exception:
        pass


def _lock_try(fh) -> bool:
    """Acquire a real OS lock. The OS releases it automatically if a worker dies."""
    fh.seek(0)
    if os.name == 'nt':
        import msvcrt
        try:
            # Ensure a byte exists because msvcrt locks a byte range.
            if fh.read(1) == '':
                fh.seek(0); fh.write('0'); fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _lock_release(fh) -> None:
    if not fh: return
    try:
        fh.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try: fh.close()
    except Exception: pass


def _slot_count() -> int:
    """Kolik soubeznych Claude Code volani smi bezet (NPC AI RUNTIME FIX).

    Jeden globalni zamek delal z kazdeho paralelniho behu frontu, ktera se po
    60 s rozpadla na SUBSCRIPTION_PROVIDER_BUSY. Pocet slotu je konzervativni
    default 1 pro Pro; 3 sloty dávejte až na Max/Team s ověřenou kapacitou.
    """
    try:
        n = int(os.environ.get('NPC_CLAUDE_CODE_SLOTS', '1'))
    except Exception:
        n = 1
    return max(1, min(8, n))


def _start_timeout() -> float:
    """Kolik sekund cekat na prvni event z CLI (NPC AI RUNTIME FIX)."""
    try:
        return max(30.0, float(os.environ.get('NPC_CLAUDE_CODE_START_TIMEOUT_S', '120')))
    except Exception:
        return 120.0


def _auto_timeout(max_tokens, base, *, research: bool = False, interactive: bool = False) -> int:
    """Hard timeout podle ocekavane delky vystupu (NPC AI RUNTIME FIX).

    Claude Code nema prepinac max_tokens, takze dlouhy strukturovany vystup
    (report 9000 tokenu) potrebuje vic nez pausalnich 180 s, jinak NPC zabije
    proces uprostred platne odpovedi.
    """
    try:
        mt = int(max_tokens or 0)
    except Exception:
        mt = 0
    # Interactive UX steps (brief understanding / quick simulation context) must not
    # inherit report/research-sized time budgets. They use small schemas, no tools and
    # a low max-turn cap; if they cannot finish promptly, fail visibly instead of
    # making the form look frozen for minutes. Deep research keeps the old budget.
    need = (35.0 + mt / 30.0) if interactive and not research else (90.0 + mt / 18.0 + (240.0 if research else 0.0))
    try:
        base_f = float(base or 0)
    except Exception:
        base_f = 0.0
    return int(max(base_f, need))


_RETRYABLE = ('SUBSCRIPTION_PROVIDER_BUSY', 'SUBSCRIPTION_PROVIDER_START_TIMEOUT',
              'SUBSCRIPTION_PROVIDER_TIMEOUT', 'error_max_turns', 'MAX_TURNS')


def _with_retry(fn, *, attempts: int = 3):
    """Zopakuj volani pri docasne kolizi na sdilenem provideru (NPC AI RUNTIME FIX)."""
    last = None
    for i in range(max(1, int(attempts))):
        try:
            return fn()
        except ClaudeCodeCancelled:
            raise
        except ClaudeCodeLimit:
            raise
        except Exception as exc:
            last = exc
            msg = str(exc)
            kind = next((x for x in _RETRYABLE if x in msg), '')
            if not kind or i + 1 >= attempts:
                raise
            if 'TIMEOUT' in kind and i >= 1:
                raise
            wait = 2.0 + 4.0 * i
            runtime_report({'phase': f'Claude Code · docasna kolize ({kind}), pokus {i + 2}/{attempts}',
                            'provider_stage': 'retry', 'provider_retry_wait_seconds': wait})
            if cancel_requested():
                raise ClaudeCodeCancelled('JOB_CANCELLED')
            time.sleep(wait)
    if last is not None:
        raise last
    raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_UNAVAILABLE: neznama chyba retry smycky.')


def _acquire_slot(timeout: float = 190.0):
    """Pocitajici semafor nad N OS zamky (NPC AI RUNTIME FIX).

    OS zamek si drzi zivotnost procesu, takze spadly worker slot uvolni sam.
    Puvodni verze mela jen jeden zamek, cimz serializovala uplne vsechny AI
    plochy — vcetne copilota, ktery cekal na respondentni beh.
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    slots = _slot_count()
    paths = [LOCK_PATH] + [LOCK_PATH.with_name(f'claude_code_subscription_{i}.lock')
                           for i in range(1, slots)]
    handles = []
    for p in paths:
        try:
            handles.append(open(p, 'a+', encoding='utf-8'))
        except Exception:
            pass
    if not handles:
        handles = [open(LOCK_PATH, 'a+', encoding='utf-8')]
    start = time.monotonic()
    last_notice = -999.0
    while True:
        for fh in handles:
            if _lock_try(fh):
                try:
                    fh.seek(0); fh.truncate(); fh.write(f'{os.getpid()} {time.time()}\n')
                    fh.flush(); fh.seek(0)
                except Exception:
                    pass
                for other in handles:
                    if other is not fh:
                        try: other.close()
                        except Exception: pass
                runtime_report({'phase': 'Claude Code · subscription slot ziskan',
                                'provider_stage': 'slot_acquired', 'provider_slots': len(handles)})
                return fh
        elapsed = time.monotonic() - start
        if elapsed - last_notice >= 2.0:
            runtime_report({'phase': 'Claude Code · vsechny sloty obsazene, cekam',
                            'provider_stage': 'waiting_for_slot',
                            'provider_wait_seconds': round(elapsed, 1),
                            'provider_slots': len(handles)})
            last_notice = elapsed
        if cancel_requested():
            for fh in handles:
                try: fh.close()
                except Exception: pass
            raise ClaudeCodeCancelled('JOB_CANCELLED')
        if elapsed >= timeout:
            for fh in handles:
                try: fh.close()
                except Exception: pass
            raise ClaudeCodeUnavailable(
                f'SUBSCRIPTION_PROVIDER_BUSY: vsech {len(handles)} subscription slotu je obsazeno '
                f'dele nez {int(timeout)} s.')
        time.sleep(.2)



def _release_slot(slot=None):
    """Compatibility alias; real locking is OS-backed and handle-scoped."""
    _lock_release(slot)

def health(timeout=12)->dict[str,Any]:
    st=auth_status(); exe=executable()
    if not exe:
        return {'ok':False,'provider':PROVIDER_ID,'kind':'MISSING','message':'Claude Code CLI není nainstalovaný. Spusťte automatické nastavení v NPC.','incremental_api_cost_usd':0.0}
    if not supports_required_cli():
        return {'ok':False,'provider':PROVIDER_ID,'kind':'UPDATE_REQUIRED','message':'Claude Code CLI je starší než podporovaná řada 2.1.x. Aktualizujte stable build v Nastavení.','executable':exe,'incremental_api_cost_usd':0.0}
    if not st.get('subscription_verified'):
        return {'ok':False,'provider':PROVIDER_ID,'kind':st.get('kind','AUTH_UNVERIFIED'),'message':st.get('message','Claude subscription není ověřena.'),'executable':exe,'incremental_api_cost_usd':0.0,'subscription_verified':False,'auth_method':st.get('auth_method'),'api_provider':st.get('api_provider'),'subscription_type':st.get('subscription_type'),'verification_basis':st.get('verification_basis')}
    return {'ok':True,'provider':PROVIDER_ID,'kind':'SUBSCRIPTION_READY','message':st.get('message'),'executable':exe,'version':st.get('version'),'incremental_api_cost_usd':0.0,'subscription_verified':True,'auth_method':st.get('auth_method'),'api_provider':st.get('api_provider'),'subscription_type':st.get('subscription_type'),'verification_basis':st.get('verification_basis')}


def _prompt(messages:list[dict[str,Any]])->str:
    return '\n\n'.join(f"{str(m.get('role') or 'user').upper()}: {m.get('content','')}" for m in messages)


def _usage_from_outer(outer: dict[str,Any]) -> tuple[int,int]:
    u=outer.get('usage') or {}
    if not isinstance(u,dict): return 0,0
    def n(*keys):
        for k in keys:
            try:
                if u.get(k) is not None: return int(u.get(k) or 0)
            except Exception: pass
        return 0
    return n('input_tokens','inputTokens'), n('output_tokens','outputTokens')


def _schema_cli_payload(schema:dict|None)->tuple[dict|None,str]:
    if schema is None: return None,''
    raw=json.dumps(schema,ensure_ascii=False,separators=(',',':'))
    # Keep Windows command lines far below CreateProcess limits.
    if len(raw) <= 10000: return schema,''
    return None,"\n\nOUTPUT JSON SCHEMA (return one JSON object matching it exactly):\n"+raw


def _schema_prompt_tail(schema:dict|None)->str:
    if schema is None:return ''
    return "\n\nOUTPUT JSON SCHEMA. Return exactly one JSON object matching this schema; no markdown or commentary:\n"+json.dumps(schema,ensure_ascii=False,separators=(',',':'))


def _cli_unknown_option_text(run:dict[str,Any])->str:
    if int(run.get('returncode') or 0)==0:return ''
    outer=run.get('outer') or {}
    return '\n'.join([str(outer.get('result') or ''),str(outer.get('error') or ''),str(run.get('stderr') or ''),'\n'.join(run.get('raw_lines') or [])]).lower()


def _needs_minimal_cli_compat(run:dict[str,Any])->bool:
    """Detect option incompatibility on otherwise usable Claude Code 2.1.x builds."""
    text=_cli_unknown_option_text(run)
    if not text:return False
    if not any(x in text for x in ('unknown option','unknown argument','unrecognized','unexpected argument','invalid option','found argument')):
        return False
    # --json-schema has a narrower compatibility path; everything else uses the
    # minimal print-mode command below. This remains the same Claude executable,
    # account and model.
    return any(flag in text for flag in ('--safe-mode','--include-partial-messages','--system-prompt-file',
        '--disable-slash-commands','--no-session-persistence','--no-chrome','--permission-mode',
        '--input-format','--disallowedtools','--tools','--allowedtools','--max-turns'))


def _minimal_cli_command(exe:str, *, model:str)->list[str]:
    # Deliberately use the oldest stable print-mode surface. System instructions
    # are moved to stdin by the caller. This path is only used after the richer
    # command explicitly fails on an unsupported option.
    return [exe,'-p','--output-format','stream-json','--verbose','--model',str(model or 'sonnet'),
            'Process the request supplied on stdin. Return only the requested response.']


def _json_schema_cli_unsupported(run:dict[str,Any])->bool:
    if int(run.get('returncode') or 0)==0:return False
    outer=run.get('outer') or {}
    text='\n'.join([
        str(outer.get('result') or ''),str(outer.get('error') or ''),str(run.get('stderr') or ''),
        '\n'.join(run.get('raw_lines') or [])
    ]).lower()
    if 'json-schema' not in text and '--json-schema' not in text:return False
    return any(x in text for x in ('unknown option','unknown argument','unrecognized','not supported','unsupported','unexpected argument','invalid option','found argument'))


def _base_cli_command(exe:str, *, system_file:str, model:str, schema:dict|None, research:bool=False, max_turns:int=8)->list[str]:
    """Build a subscription-safe, non-interactive command.

    Current Claude Code documents --safe-mode specifically for troubleshooting broken
    user/project customizations while keeping authentication/model selection intact.
    We deliberately do NOT pass --mcp-config: even an empty MCP config can add startup
    waiting, and this product needs no MCP for normal model calls.
    """
    cmd=[
        exe,'-p','--safe-mode','--output-format','stream-json','--verbose',
        '--max-turns',str(max(1,int(max_turns))), '--model',str(model or 'sonnet'),
        '--system-prompt-file',system_file,'--disable-slash-commands','--no-session-persistence','--no-chrome',
        '--permission-mode','dontAsk','--input-format','text','--disallowedTools','mcp__*',
    ]
    if research:
        cmd += ['--tools','WebSearch,WebFetch','--allowedTools','WebSearch,WebFetch']
    else:
        cmd += ['--tools','']
    if schema is not None:
        cmd += ['--json-schema',json.dumps(schema,ensure_ascii=False,separators=(',',':'))]
    prompt=('Research the request supplied on stdin. Use web search/fetch only when needed and return the requested structured result.'
            if research else
            'Process the request supplied on stdin and return only the requested response.')
    cmd += [prompt]
    return cmd


def _terminate_tree(p:subprocess.Popen, *, force:bool=False)->None:
    if not p or p.poll() is not None: return
    try:
        if os.name=='nt':
            # /T is essential: worker termination alone can otherwise orphan claude.exe.
            flags=['/F'] if force else []
            subprocess.run(['taskkill','/PID',str(p.pid),'/T',*flags],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        else:
            os.killpg(p.pid, signal.SIGKILL if force else signal.SIGTERM)
    except Exception:
        try: p.kill() if force else p.terminate()
        except Exception: pass


def _stream_event_phase(obj:dict[str,Any])->dict[str,Any]|None:
    typ=str(obj.get('type') or '')
    sub=str(obj.get('subtype') or '')
    if typ=='system' and sub=='init':
        return {'phase':'Claude Code · připojeno, model začíná zpracovávat požadavek','provider_stage':'connected','provider_model':obj.get('model')}
    if typ=='system' and sub=='api_retry':
        return {'phase':f"Claude Code · API retry {obj.get('attempt','?')}/{obj.get('max_retries','?')}", 'provider_stage':'api_retry','retry_delay_ms':obj.get('retry_delay_ms'),'provider_error':obj.get('error')}
    if typ=='assistant':
        return {'phase':'Claude Code · skládám odpověď','provider_stage':'assistant'}
    if typ=='result':
        return {'phase':'Claude Code · odpověď dokončena','provider_stage':'result'}
    return None


def _run_stream(cmd:list[str], *, stdin_text:str, timeout:int, cwd:str|Path, env:dict[str,str])->dict[str,Any]:
    """Run Claude with real provider telemetry and hard process-tree cleanup."""
    kwargs=dict(cwd=str(cwd),env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',errors='replace',bufsize=1)
    if os.name=='nt':
        kwargs['creationflags']=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
    else:
        kwargs['start_new_session']=True
    runtime_report({'phase':'Claude Code · spouštím izolovaný provider proces','provider_stage':'starting'})
    p=subprocess.Popen(cmd,**kwargs)
    try:
        assert p.stdin is not None
        p.stdin.write(stdin_text); p.stdin.close()  # explicit EOF: non-interactive print mode must never wait for more input
    except Exception:
        _terminate_tree(p,force=True); raise

    q:queue.Queue=queue.Queue(); err_lines=[]; raw_lines=[]
    def pump(stream,name):
        try:
            for line in iter(stream.readline,''):
                q.put((name,line))
        finally:q.put((name,None))
    threading.Thread(target=pump,args=(p.stdout,'out'),daemon=True).start()
    threading.Thread(target=pump,args=(p.stderr,'err'),daemon=True).start()

    start=time.monotonic(); last_event=start; last_progress=-999.0; outer=None; ended=set()
    while True:
        if cancel_requested():
            runtime_report({'phase':'Claude Code · ruším provider proces','provider_stage':'cancelling'})
            _terminate_tree(p); 
            try:p.wait(timeout=4)
            except Exception:_terminate_tree(p,force=True)
            raise ClaudeCodeCancelled('JOB_CANCELLED')
        elapsed=time.monotonic()-start
        if elapsed >= timeout:
            runtime_report({'phase':'Claude Code · provider překročil hard timeout, ukončuji proces','provider_stage':'timeout','provider_elapsed_seconds':round(elapsed,1)})
            _terminate_tree(p)
            try:p.wait(timeout=4)
            except Exception:_terminate_tree(p,force=True)
            raise ClaudeCodeUnavailable(f'SUBSCRIPTION_PROVIDER_TIMEOUT: Claude Code neukončil požadavek do {timeout} s.')
        try:name,line=q.get(timeout=.25)
        except queue.Empty:
            line='__NOEVENT__';name=''
        if line is None:
            ended.add(name)
        elif line!='__NOEVENT__':
            last_event=time.monotonic()
            if name=='err': err_lines.append(line.rstrip())
            else:
                raw_lines.append(line.rstrip())
                try:obj=json.loads(line)
                except Exception:obj=None
                if isinstance(obj,dict):
                    if obj.get('type')=='result': outer=obj
                    phase=_stream_event_phase(obj)
                    if phase and time.monotonic()-last_progress>=.8:
                        phase['provider_elapsed_seconds']=round(elapsed,1); runtime_report(phase); last_progress=time.monotonic()
        if not raw_lines and elapsed >= _start_timeout():  # NPC AI RUNTIME FIX
            runtime_report({'phase':'Claude Code · žádný provider event do 45 s, ukončuji zaseklý start','provider_stage':'startup_timeout','provider_elapsed_seconds':round(elapsed,1)})
            _terminate_tree(p)
            try:p.wait(timeout=4)
            except Exception:_terminate_tree(p,force=True)
            raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_START_TIMEOUT: Claude Code neposlal ani inicializační event do %d s.' % int(_start_timeout()))
        silence=time.monotonic()-last_event
        if silence>=10 and time.monotonic()-last_progress>=5:
            runtime_report({'phase':'Claude Code · proces běží, čekám na další provider event','provider_stage':'waiting_provider_event','provider_silence_seconds':round(silence,1),'provider_elapsed_seconds':round(elapsed,1)})
            last_progress=time.monotonic()
        if p.poll() is not None and {'out','err'} <= ended:
            break

    rc=int(p.returncode or 0); err='\n'.join(err_lines).strip()
    if outer is None:
        # A few transitional CLI builds can still emit a single JSON object rather than
        # NDJSON despite stream-json. Preserve compatibility without masking errors.
        for line in reversed(raw_lines):
            try:
                obj=json.loads(line)
                if isinstance(obj,dict): outer=obj; break
            except Exception: pass
    if outer is None: outer={}
    return {'returncode':rc,'outer':outer,'stderr':err,'raw_lines':raw_lines}


def _invoke(*,system:str,messages:list[dict[str,Any]],model:str='sonnet',schema:dict|None=None,timeout:int=180,research:bool=False,max_turns:int=8)->dict[str,Any]:
    exe=executable()
    if not exe: raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_UNAVAILABLE: Claude Code CLI není nainstalovaný.')
    runtime_report({'phase':'Claude Code · ověřuji subscription přihlášení','provider_stage':'auth_check'})
    st=auth_status()
    if not st.get('subscription_verified'):
        raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_AUTH_UNVERIFIED: '+str(st.get('message') or 'Subscription billing nelze bezpečně potvrdit.'))
    basis=str(st.get('verification_basis') or '')
    phase='Claude Code · přihlášení ověřeno, kontroluji CLI runtime'
    if basis=='first_party_oauth_without_subscriptionType':
        phase='Claude Code · first-party OAuth ověřen; subscriptionType chybí, pokračuji skutečným CLI voláním'
    runtime_report({'phase':phase,'provider_stage':'runtime_check','auth_verification_basis':basis})
    if not supports_required_cli():
        raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_UPDATE_REQUIRED: Claude Code CLI je starší než podporovaná řada 2.1.x; aktualizujte stable build v Nastavení.')
    # NPC AI RUNTIME FIX: strop 60 s byl kratsi nez jedno bezne CLI volani.
    slot=_acquire_slot(timeout=max(180.0,float(timeout)))
    td=tempfile.mkdtemp(prefix='npc_claude_code_')
    try:
        td_path=Path(td); system_file=td_path/'system_prompt.txt'; system_file.write_text(str(system or ''),encoding='utf-8')
        cli_schema,schema_stdin=_schema_cli_payload(schema)
        cmd=_base_cli_command(exe,system_file=str(system_file),model=model,schema=cli_schema,research=research,max_turns=max_turns)
        env=subscription_env(); env['MCP_TIMEOUT']='3'; env['CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS']='15000'
        stdin_text=_prompt(messages)+schema_stdin
        if len(stdin_text.encode('utf-8')) > 9_500_000:
            raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_INPUT_TOO_LARGE: Claude Code stdin překročil bezpečný limit 9.5 MB.')
        run=_run_stream(cmd,stdin_text=stdin_text,timeout=timeout,cwd=td,env=env)
        # Some otherwise supported Claude Code 2.1.x builds do not expose the
        # --json-schema CLI switch. Keep the SAME Claude subscription/provider
        # and retry once with the schema embedded in stdin; structured_call
        # still parses/validates the resulting JSON contract. This is CLI
        # compatibility, never a provider/model fallback.
        if cli_schema is not None and _json_schema_cli_unsupported(run):
            runtime_report({'phase':'Claude Code · tato verze CLI nepodporuje --json-schema; opakuji stejný Claude call s JSON kontraktem v promptu','provider_stage':'schema_prompt_compat'})
            compat_stdin=_prompt(messages)+_schema_prompt_tail(schema)
            if len(compat_stdin.encode('utf-8')) > 9_500_000:
                raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_INPUT_TOO_LARGE: Claude Code stdin překročil bezpečný limit 9.5 MB.')
            compat_cmd=_base_cli_command(exe,system_file=str(system_file),model=model,schema=None,research=research,max_turns=max_turns)
            run=_run_stream(compat_cmd,stdin_text=compat_stdin,timeout=timeout,cwd=td,env=env)
        # A few Windows Claude Code builds expose print mode but reject one
        # of the newer isolation flags. For ordinary product AI calls, retry the
        # SAME executable/account/model once using the minimal stable print-mode
        # surface. Never switch provider and never fabricate a local answer.
        if not research and _needs_minimal_cli_compat(run):
            runtime_report({'phase':'Claude Code · kompatibilní print-mode retry na stejné instalaci','provider_stage':'minimal_cli_compat'})
            minimal_cmd=_minimal_cli_command(exe,model=model)
            minimal_stdin=('SYSTEM INSTRUCTIONS:\n'+str(system or '')+'\n\nREQUEST:\n'+_prompt(messages)+_schema_prompt_tail(schema))
            if len(minimal_stdin.encode('utf-8')) > 9_500_000:
                raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_INPUT_TOO_LARGE: Claude Code stdin překročil bezpečný limit 9.5 MB.')
            run=_run_stream(minimal_cmd,stdin_text=minimal_stdin,timeout=timeout,cwd=td,env=env)
    finally:
        _cleanup_temp_dir(td)
        _lock_release(slot)
    outer=run['outer']; raw='\n'.join(run['raw_lines']).strip(); err=run['stderr']; joined=(raw+'\n'+err).lower()
    if run['returncode']!=0 or str(outer.get('subtype') or '').lower() in {'error','failure'} or outer.get('is_error'):
        _detail=str(outer.get('result') or outer.get('error') or '').strip()
        _tail_lines=[x for x in (run.get('raw_lines') or []) if str(x).strip()][-3:]
        msg=' | '.join(x for x in [
            f"exit={run['returncode']}",
            f"subtype={outer.get('subtype')}" if outer.get('subtype') else '',
            f"is_error={outer.get('is_error')}" if outer.get('is_error') is not None else '',
            f"detail={_detail[:400]}" if _detail else '',
            f"stderr={err[-500:]}" if err else '',
            f"last_lines={' ¶ '.join(str(x)[:200] for x in _tail_lines)}" if _tail_lines else '',
        ] if x) or f"exit={run['returncode']}"
        if any(x in joined for x in ('usage limit','session limit','rate limit','rate_limit','limit reached','quota','too many requests','usage cap','out_of_credits')):
            raise ClaudeCodeLimit('SUBSCRIPTION_PROVIDER_LIMIT: '+msg[:1500])
        raise ClaudeCodeUnavailable('SUBSCRIPTION_PROVIDER_UNAVAILABLE: '+msg[:1800])
    text=outer.get('result')
    if text is None: text=outer.get('text','')
    structured=outer.get('structured_output') if schema is not None else None
    if structured is not None and not text: text=json.dumps(structured,ensure_ascii=False)
    tok_in,tok_out=_usage_from_outer(outer)
    runtime_report({'phase':'Claude Code · hotovo','provider_stage':'completed','tok_in':tok_in,'tok_out':tok_out})
    return {'text':str(text or ''),'raw':outer,'structured_output':structured,'provider':PROVIDER_ID,'model':model,
            'tok_in':tok_in,'tok_out':tok_out,'cost_usd':0.0,'subscription_usage':True,'subscription_verified':True,
            'session_id':outer.get('session_id')}


def _structured_prompt_recovery(*, system:str, messages:list[dict[str,Any]], schema:dict[str,Any], schema_name:str,
                                model:str, timeout:int, research:bool=False, max_turns:int=8,
                                first_error:Exception|None=None)->dict[str,Any]:
    """Recover malformed structured output through the SAME Claude Code subscription.

    This is deliberately provider-stable: no OpenAI/Anthropic API/local fallback.  It
    removes the CLI JSON-schema switch, embeds the contract in stdin, asks for exactly
    one JSON object, then parses it locally.  This protects every structured AI step
    (brief, questionnaire, audience, persona, final review, reports, Data Library), not
    just the first brief analysis.
    """
    from ai_router import extract_json
    recovery_messages=list(messages or [])
    tail=("\n\nTECHNICKÁ OPRAVA FORMÁTU: Předchozí strukturovaný pokus nevrátil čitelný JSON. "
          "Zpracuj znovu STEJNÝ věcný požadavek. Vrať POUZE jeden validní JSON objekt, "
          "bez markdownu, bez komentáře a bez textu před/za JSON. Dodrž přesně toto JSON schema:\n"+
          json.dumps(schema,ensure_ascii=False,separators=(',',':')))
    if recovery_messages and str(recovery_messages[-1].get('role') or '')=='user':
        recovery_messages[-1]=dict(recovery_messages[-1])
        recovery_messages[-1]['content']=str(recovery_messages[-1].get('content') or '')+tail
    else:
        recovery_messages.append({'role':'user','content':tail})
    runtime_report({'phase':f'Claude Code · opravuji JSON formát kroku {schema_name} stejným Claude runtime',
                    'provider_stage':'same_claude_json_recovery','schema_name':schema_name})
    rr=_with_retry(lambda:_invoke(system=system,messages=recovery_messages,model=model,schema=None,
                                  timeout=timeout,research=research,max_turns=max_turns))
    try:
        data=extract_json(str(rr.get('text') or ''))
    except Exception as exc:
        first=(f'; first={first_error}' if first_error else '')
        raise RuntimeError(f'CLAUDE_CODE_SCHEMA_ERROR[{schema_name}]: recovery JSON parse failed: {exc}{first}') from exc
    if str((schema or {}).get('type') or '')=='object' and not isinstance(data,dict):
        raise RuntimeError(f'CLAUDE_CODE_SCHEMA_ERROR[{schema_name}]: recovery returned {type(data).__name__}, expected object')
    rr['data']=data
    rr['structured_output']=None
    rr['mode']='same_claude_prompt_json_recovery'
    rr['attempts']=['structured', 'same_claude_prompt_json_recovery']
    rr['fallback_used']=False
    if first_error is not None: rr['first_schema_error']=str(first_error)[:900]
    return rr


def research_structured_call(*,system:str,messages:list[dict[str,Any]],schema:dict[str,Any],schema_name='npc_research',model='sonnet',max_tokens=6000,timeout=420,max_turns=8)->dict[str,Any]:
    from ai_router import extract_json
    eff=_auto_timeout(max_tokens,timeout,research=True)
    r=_with_retry(lambda:_invoke(system=system,messages=messages,model=model,schema=schema,timeout=eff,research=True,max_turns=max_turns))
    try:
        structured=r.get('structured_output')
        if structured is None: structured=extract_json(str(r.get('text') or ''))
        if str((schema or {}).get('type') or '')=='object' and not isinstance(structured,dict):
            raise ValueError(f'expected object, got {type(structured).__name__}')
        r['data']=structured
        r.setdefault('mode','structured')
        r.setdefault('attempts',['structured'])
        r.setdefault('fallback_used',False)
    except Exception as exc:
        r=_structured_prompt_recovery(system=system,messages=messages,schema=schema,schema_name=schema_name,
                                      model=model,timeout=eff,research=True,max_turns=max_turns,first_error=exc)
    return {'data':r.get('data'),'text':r.get('text',''),'raw':r.get('raw') or {},'provider':PROVIDER_ID,'model':model,
            'tok_in':r.get('tok_in',0),'tok_out':r.get('tok_out',0),'cost_usd':0.0,'subscription_usage':True,'subscription_verified':True,
            'tools':['WebSearch','WebFetch'],'session_id':r.get('session_id'),'schema_name':schema_name,
            'mode':r.get('mode'),'attempts':r.get('attempts'),'fallback_used':False}


def text_call(*,system:str,messages:list[dict[str,Any]],model='sonnet',max_tokens=1200,timeout=180,interactive:bool=False,max_turns:int=8)->dict[str,Any]:
    # Fast UI calls use a small turn/time envelope; long-form calls retain legacy behaviour.
    eff=_auto_timeout(max_tokens,timeout,interactive=interactive)
    return _with_retry(lambda:_invoke(system=system,messages=messages,model=model,timeout=eff,max_turns=max_turns))


def structured_call(*,system:str,messages:list[dict[str,Any]],schema:dict[str,Any],schema_name='npc',model='sonnet',max_tokens=1800,timeout=180,max_turns:int=8,interactive:bool=False)->dict[str,Any]:
    from ai_router import extract_json
    eff=_auto_timeout(max_tokens,timeout,interactive=interactive)
    try:
        r=_with_retry(lambda:_invoke(system=system,messages=messages,model=model,schema=schema,timeout=eff,max_turns=max_turns))
        data=r.get('structured_output')
        if data is None: data=extract_json(str(r.get('text') or ''))
        if str((schema or {}).get('type') or '')=='object' and not isinstance(data,dict):
            raise ValueError(f'expected object, got {type(data).__name__}')
        r['data']=data
        r.setdefault('mode','structured')
        r.setdefault('attempts',['structured'])
        r.setdefault('fallback_used',False)
        return r
    except ClaudeCodeCancelled:
        raise
    except ClaudeCodeLimit:
        raise
    except Exception as exc:
        # Respondent fieldwork can carry dozens of already valuable answers in one
        # request. Re-running the whole prompt merely to repair formatting doubles
        # subscription usage and was a primary cause of exhausted limits. The caller
        # keeps completed batches in its durable journal and resumes from there, so a
        # second paid Claude process must never be launched for respondent JSON repair.
        if str(schema_name or '').startswith('npc_respondent_'):
            raise RuntimeError(
                f'CLAUDE_CODE_SCHEMA_ERROR[{schema_name}]: invalid structured output; '
                f'no paid repair call was made: {exc}'
            ) from exc
        return _structured_prompt_recovery(system=system,messages=messages,schema=schema,schema_name=schema_name,
                                           model=model,timeout=eff,research=False,max_turns=max_turns,first_error=exc)
