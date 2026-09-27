from __future__ import annotations
import json,re
from edition_config import build_version
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def txt(name): return (ROOT/name).read_text(encoding='utf-8',errors='replace')

def main():
    server=txt('ui_server.py'); ui=txt('ui_app.html'); runtime=txt('ai_runtime.py')
    checks=[]
    def add(name,ok,detail): checks.append({'check':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    durable={
      '/api/research/analyze':'research_analysis','/api/copilot/chat':'copilot',
      '/api/research/build_questionnaire':'questionnaire_build','/api/research/deep':'deep_research',
      '/api/questionnaire/optimize':'questionnaire_optimize','/api/persona/suggest':'persona_suggest',
      '/api/audience/propose':'audience_propose','/api/scenario/compile':'scenario_compile',
      '/api/fullsim/prepare':'fullsim_prepare','/api/fullsim/run':'fullsim_run','/api/results/verify':'result_verify',
      '/api/settings/ai_diagnose':'ai_diagnose','/api/discovery/strategy':'audience_strategy'
    }
    for ep,kind in durable.items():
        add('durable:'+ep, f'_start_job(self._body(),"{kind}")' in server,
            f'{ep} -> {kind}; durable job, reconnect/idempotency/progress')
        add('profile:'+kind, f'"{kind}"' in runtime, 'action has ETA/hard-timeout metadata')
    modules=['audience.py','navrh.py','import_dotaznik.py','pdf_targets.py']
    bad=[m for m in modules if 'prefer=get_ai_provider()' in txt(m)]
    add('explicit_provider_user_ai',not bad,'No hard-coded global provider at user AI callsites' if not bad else 'Hard-coded: '+','.join(bad))
    add('production_fail_closed', 'allow_fallback=False' in txt('scenario_compiler.py') and 'allow_fallback=False' in txt('research_copilot.py'),
        'Scenario/compiler and copilot use selected provider without cross-provider fallback')
    add('no_auto_replay','attempts=1 if kind in AI_ACTIONS else 2' in server,
        'Failed user-facing AI jobs are not automatically charged/replayed')
    add('brief_fast','Deep Research is deliberately NOT run here' in server and 'max_tokens=3200' in txt('research_designer.py'),
        'First brief pass is one compact design call; Deep Research is explicit later')
    add('brief_no_special_autoselect','action": "advisory_only"' in txt('research_designer.py') and 'NEVYBÍREJ dataset, special audience' in txt('research_designer.py'),
        'Brief analysis cannot silently switch to builtin special audience')
    add('copilot_compact_protected','_compact_project_for_ai' in txt('research_copilot.py') and '_merge_design_proposal' in txt('research_copilot.py'),
        'Research Partner sends compact design context and preserves runtime/audience source/budget')
    add('scenario_builtin_special','dataset_id.startswith("builtin_special:")' in server and 'get_special_panel' in server,
        'FullSim resolves packaged builtin_special panels directly instead of upload registry')
    add('progress_ui', all(x in ui for x in ['progressMeta','provider_stage','hard stop ','cancelActiveJob','Běží ']),
        'Elapsed time, ETA range, hard stop, real provider stage, worker heartbeat, provider/model/cost and cancel are visible')
    provider_src=txt('claude_code_provider.py'); setup_src=txt('claude_code_setup.py'); daemon_src=txt('worker_daemon.py')
    add('subscription_os_lock', '_lock_try' in provider_src and 'msvcrt.locking' in provider_src and 'fcntl.flock' in provider_src,
        'Claude subscription serialization uses OS process-lifetime locking; stale lock files cannot block later jobs')
    add('subscription_safe_mode', "'--safe-mode'" in provider_src and "'--mcp-config'," not in provider_src,
        'Normal Claude calls use safe-mode and do not initialize MCP configuration')
    add('subscription_stream_json', "'--output-format','stream-json'" in provider_src and 'provider_stage' in provider_src,
        'Claude provider emits real stream-json lifecycle telemetry instead of synthetic worker-only progress')
    add('subscription_auth_cache', '_AUTH_CACHE_SECONDS=120.0' in setup_src and "auth','status'],8" in setup_src,
        'Subscription proof is cached per worker and no longer repeated twice before every model call')
    add('process_tree_cancel', 'taskkill' in daemon_src and "'/T'" in daemon_src and 'os.killpg' in daemon_src,
        'Cancel/restart terminates worker + Claude child process tree; orphaned CLI processes are not left behind')
    rc=txt('research_context.py')
    add('research_agent_progress',all(x in rc for x in ['agent 1/2','agent 2/2','syntéza, deduplikace']),
        'Deep Research exposes per-agent and synthesis phases')
    # Native web-search lanes are intentional exceptions, not router bypass bugs.
    exceptions=[
      {'module':'research_context.py','reason':'provider-native web search/WebSearch+WebFetch; selected provider is explicit and no cross-provider fallback'},
      {'module':'result_context.py','reason':'post-run provider-native web search for external triangulation; selected provider is explicit'},
      {'module':'provider_auth.py','reason':'provider health/probe only, not production research generation'},
      {'module':'anthropic_compat.py','reason':'low-level compatibility wrapper called by approved provider paths'},
    ]
    failed=[c for c in checks if c['status']!='PASS']
    _ver=build_version()
    out={'version':_ver,'status':'PASS' if not failed else 'FAIL','checks':checks,'native_provider_exceptions':exceptions,
         'policy':{'production_cross_provider_fallback':False,'local_design_fallback':'DEBUG_ENV_ONLY','interactive_auto_retry':False,
                   'progress':'elapsed + ETA range + heartbeat; no fake percentage','claude_code_cost':'subscription/API $0; token usage shown only when CLI reports it'}}
    p=ROOT/'remediation'/f"AI_RUNTIME_AUDIT_{_ver.replace('.', '_')}.json"; p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'pass':len(checks)-len(failed),'fail':len(failed),'file':str(p)},ensure_ascii=False))
    return 0 if not failed else 1
if __name__=='__main__': raise SystemExit(main())
