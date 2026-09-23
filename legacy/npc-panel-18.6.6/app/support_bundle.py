from __future__ import annotations
import hashlib, json, os, platform, shutil, sqlite3, sys, time, zipfile
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent
DIAG=ROOT/'diagnostics'
LOGS=ROOT/'logs'
DB=ROOT/'data'/'research_os.sqlite'
SENSITIVE=('api_key','apikey','token','password','secret','authorization','oauth','cookie','credential')
CONTENT_KEYS={'messages','prompt','system','briefing','project','input','payload','questionnaire','history','text','content'}

def _safe(v:Any, depth:int=0):
    if depth>5:return '<trimmed>'
    if isinstance(v,dict):
        out={}
        for k,x in v.items():
            lk=str(k).lower()
            if any(s in lk for s in SENSITIVE): out[k]='<redacted>'
            elif lk in CONTENT_KEYS: out[k]='<omitted user content>'
            else: out[k]=_safe(x,depth+1)
        return out
    if isinstance(v,list):return [_safe(x,depth+1) for x in v[:80]]
    if isinstance(v,str):return v[:5000]
    return v

def _loads(x,default):
    try:return json.loads(x or '')
    except Exception:return default

def _jobs(last_job_id:str|None=None):
    if not DB.is_file():return [],[]
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
    try:
        if last_job_id:
            rows=c.execute('SELECT * FROM jobs WHERE job_id=?',(last_job_id,)).fetchall()
        else:
            rows=c.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 15').fetchall()
        jobs=[]; ids=[]
        for r in rows:
            d=dict(r);ids.append(d['job_id'])
            inp=_loads(d.get('input_json'),{}) or {}
            jobs.append({
                'job_id':d.get('job_id'),'workflow_id':d.get('workflow_id'),'node_key':d.get('node_key'),'kind':d.get('kind'),
                'status':d.get('status'),'created_at':d.get('created_at'),'started_at':d.get('started_at'),'heartbeat_at':d.get('heartbeat_at'),
                'finished_at':d.get('finished_at'),'attempt':d.get('attempt'),'max_attempts':d.get('max_attempts'),'provider_policy':d.get('provider_policy'),
                'model':d.get('model'),'project_id':d.get('project_id'),'project_revision':d.get('project_revision'),'stage_id':d.get('stage_id'),'artifact_target':d.get('artifact_target'),'input_fingerprint':d.get('input_fingerprint'),'cancel_requested':d.get('cancel_requested'),'error':_safe(_loads(d.get('error_json'),{})),
                'input_keys':sorted(map(str,inp.keys())),'input_sizes':{str(k):len(str(v)) for k,v in inp.items() if k in {'briefing','project','analysis','scenario','spec'}},
            })
        events=[]
        for jid in ids:
            for e in c.execute('SELECT event_id,job_id,ts,level,event_type,message,payload_json FROM job_events WHERE job_id=? ORDER BY event_id DESC LIMIT 160',(jid,)).fetchall()[::-1]:
                q=dict(e);q['payload']=_safe(_loads(q.pop('payload_json',None),{}));events.append(q)
        return jobs,events[-800:]
    finally:c.close()

def _project_snapshot(jobs):
    pids=[str(j.get('project_id') or '') for j in jobs if str(j.get('project_id') or '')]
    if not pids:return None
    try:
        from project_store import ProjectStore
        ps=ProjectStore(ROOT/'data'/'project_store.sqlite')
        try:
            pid=pids[0]; ov=ps.overview(pid)
            if not ov:return None
            return _safe({'project_id':pid,'revision':ov.get('revision'),'project_type':ov.get('project_type'),'status':ov.get('status'),'current_stage':ov.get('current_stage'),'last_completed_stage':ov.get('last_completed_stage'),'last_completed_artifact':ov.get('last_completed_artifact'),'last_checkpoint':ov.get('last_checkpoint'),'preferred_provider':ov.get('preferred_provider'),'provider_policy':ov.get('provider_policy'),'max_api_cost_usd':ov.get('max_api_cost_usd'),'api_spent_usd':ov.get('api_spent_usd'),'stages':[{'stage_type':x.get('stage_type'),'status':x.get('status'),'current_job_id':x.get('current_job_id'),'last_checkpoint':x.get('last_checkpoint'),'waiting_reason':x.get('waiting_reason'),'quota_reset_at':x.get('quota_reset_at'),'artifact_count':len(x.get('artifact_ids') or [])} for x in ov.get('stages') or []],'artifact_count':len(ov.get('artifacts') or []),'ai_usage':{k:v for k,v in (ov.get('ai_usage') or {}).items() if k!='events'}})
        finally: ps.close()
    except Exception as exc:return {'error':str(exc)[:500]}

def _claude():
    try:
        from claude_code_setup import auth_status, executable, version
        from claude_code_provider import health
        st=dict(auth_status() or {}); h=dict(health() or {})
        for d in (st,h):
            for k in list(d):
                if any(x in str(k).lower() for x in ('email','token','raw_status','status_text','account')): d.pop(k,None)
        return {'executable_found':bool(executable()),'version':version(),'auth':_safe(st),'health':_safe(h)}
    except Exception as e:return {'error':repr(e)}

def create_bundle(last_job_id:str|None=None)->Path:
    DIAG.mkdir(parents=True,exist_ok=True)
    ts=time.strftime('%Y%m%d_%H%M%S')
    safe_jid=(last_job_id or '').strip() if str(last_job_id or '').startswith('JOB-') else ''
    stem=f'NPC_DIAGNOSTIKA_{ts}'+(f'_{safe_jid}' if safe_jid else '')
    work=DIAG/stem
    if work.exists():shutil.rmtree(work,ignore_errors=True)
    work.mkdir(parents=True)
    jobs,events=_jobs(safe_jid or None)
    version=(ROOT/'VERSION').read_text(encoding='utf-8').strip() if (ROOT/'VERSION').is_file() else ''
    summary={
        'npc_version':version,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'platform':platform.platform(),
        'python':sys.version,'python_executable':sys.executable,'requested_job_id':safe_jid or None,
        'jobs_included':len(jobs),'events_included':len(events),'claude':_claude(),
        'environment_flags':{k:bool(os.environ.get(k)) for k in ['HTTP_PROXY','HTTPS_PROXY','NO_PROXY','NPC_CLAUDE_CODE_SLOTS','NPC_CLAUDE_CODE_START_TIMEOUT_S']},
        'privacy':'No prompts, questionnaire/project content, API keys, OAuth tokens or passwords are intentionally included.'
    }
    (work/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    (work/'JOBS.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf-8')
    (work/'JOB_EVENTS.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    project_snapshot=_project_snapshot(jobs)
    if project_snapshot is not None:(work/'PROJECT_RUNTIME.json').write_text(json.dumps(project_snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    (work/'CO_POSLAT.txt').write_text('Pošlete celý tento ZIP do chatu a jednou větou napište, co jste stiskl těsně před chybou.\nBalík záměrně neobsahuje prompty, obsah projektu ani přihlašovací údaje.\n',encoding='utf-8')
    for name in ['startup.log','worker.log','backend_errors.log','ai_diagnostika.txt','claude_code_setup.log','server.log']:
        src=LOGS/name
        if src.is_file(): (work/name).write_bytes(src.read_bytes()[-500_000:])
    fp=[]
    for name in ['VERSION','BUILD_EDITION.json','ai_router.py','claude_code_provider.py','research_designer.py','worker_job.py','ui_server.py','ui_app.html']:
        p=ROOT/name
        if p.is_file(): fp.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size})
    (work/'FINGERPRINT.json').write_text(json.dumps(fp,ensure_ascii=False,indent=2),encoding='utf-8')
    out=DIAG/(stem+'.zip')
    if out.exists():out.unlink()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in work.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(work))
    shutil.rmtree(work,ignore_errors=True)
    return out

if __name__=='__main__':
    jid=sys.argv[1] if len(sys.argv)>1 else None
    print(create_bundle(jid))
