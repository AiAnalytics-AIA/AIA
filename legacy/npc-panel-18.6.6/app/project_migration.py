"""Non-destructive PROJECT_PERSISTENCE_MIGRATION_V1 for NPC Panel 17.9.0.

Migration is additive and idempotent. Historical jobs/runs are linked only when
project + revision + stage identity can be established deterministically. Unknown
history is preserved as UNKNOWN instead of inventing a successful stage.
"""
from __future__ import annotations
import json,time
from pathlib import Path
from project_store import ProjectStore
from artifact_store import ArtifactStore
from job_store import JobStore
from project_pipeline import JOB_STAGE_MAP, LEGACY_STAGE_MAP

ROOT=Path(__file__).resolve().parent

def _loads(x,default):
    try:return json.loads(x or '')
    except Exception:return default

def migrate(root:Path=ROOT,*,write_report:bool=True)->dict:
    root=Path(root); ps=ProjectStore(root/'data'/'project_store.sqlite'); astore=ArtifactStore(ps,root/'data'/'project_artifacts'); js=JobStore(root/'data'/'research_os.sqlite')
    report={'kind':'PROJECT_PERSISTENCE_MIGRATION_V1','target_version':'17.9.0','started_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'status':'PASS','destructive_changes':False,
            'projects_seen':0,'revisions_seen':0,'stage_rows_created_or_verified':0,'legacy_workflows_seen':0,'linked_jobs':0,'unlinked_jobs':0,
            'completed_jobs_imported':0,'artifacts_registered':0,'unknown_history_preserved':0,'resumable_research_runs':0,'full_simulation_runs':0,'notes':[]}
    try:
        projects=ps.cx.execute('SELECT project_id,project_type,current_revision FROM projects').fetchall(); report['projects_seen']=len(projects)
        existing_projects={r['project_id'] for r in projects}
        for pr in projects:
            revs=ps.cx.execute('SELECT revision FROM project_revisions WHERE project_id=? ORDER BY revision',(pr['project_id'],)).fetchall();report['revisions_seen']+=len(revs)
            for rr in revs:
                ps._ensure_stages(pr['project_id'],int(rr['revision']),pr['project_type'] or 'research')
                report['stage_rows_created_or_verified']+=int(ps.cx.execute('SELECT COUNT(*) FROM project_stages WHERE project_id=? AND revision=?',(pr['project_id'],int(rr['revision']))).fetchone()[0])
            exists=ps.cx.execute("SELECT 1 FROM project_events WHERE project_id=? AND event_type='PROJECT_PERSISTENCE_MIGRATED' LIMIT 1",(pr['project_id'],)).fetchone()
            if not exists: ps.event(pr['project_id'],'PROJECT_PERSISTENCE_MIGRATED','Historický projekt byl bezpečně připojen k 17.9.0 stage/artifact architektuře.',{'source':'17.8.x','destructive':False},revision=int(pr['current_revision'] or 0))
        ps.cx.commit()

        with js.cx() as c:
            report['legacy_workflows_seen']=int(c.execute('SELECT COUNT(*) FROM workflows').fetchone()[0])
            rows=c.execute('SELECT * FROM jobs ORDER BY created_at,job_id').fetchall()
        for raw in rows:
            j=js._job(raw); pid=str(j.get('project_id') or '').strip(); rev=int(j.get('project_revision') or 0)
            if not pid or pid not in existing_projects or rev<=0:
                report['unlinked_jobs']+=1; report['unknown_history_preserved']+=1; continue
            report['linked_jobs']+=1
            kind=str(j.get('kind') or ''); inp=j.get('input') or {}; out=j.get('output') or {}
            stage=str(j.get('stage_id') or inp.get('stage_id') or JOB_STAGE_MAP.get(kind) or '')
            if kind=='legacy_task': stage=str(j.get('stage_id') or inp.get('stage_id') or LEGACY_STAGE_MAP.get(str(inp.get('kind') or inp.get('legacy_kind') or '')) or '')
            target=str(j.get('artifact_target') or inp.get('artifact_target') or (stage+'_LEGACY_OUTPUT' if stage else ''))
            fp=str(j.get('input_fingerprint') or inp.get('input_fingerprint') or '')
            if not stage or not target:
                report['unknown_history_preserved']+=1; continue
            if j.get('status')!='COMPLETED':
                # Waiting/failed/running legacy jobs remain resumable evidence; never
                # infer a completed stage from the mere presence of a file.
                continue
            art=astore.put_json(project_id=pid,revision=rev,stage_type=stage,artifact_type=target,obj=out,filename=f'{target}.json',input_fingerprint=fp,provider=str(j.get('provider_policy') or out.get('provider') or ''),model=str(j.get('model') or out.get('model') or ''),metadata={'migrated_from_job':j['job_id'],'workflow_id':j['workflow_id'],'migration':'PROJECT_PERSISTENCE_MIGRATION_V1'})
            report['completed_jobs_imported']+=1; report['artifacts_registered']+=1
            try:
                from project_artifact_sync import sync_for_job
                extras=sync_for_job(astore,kind=kind,out=out,project_id=pid,revision=rev,stage_id=stage,input_fingerprint=fp,provider=str(j.get('provider_policy') or out.get('provider') or ''),model=str(j.get('model') or out.get('model') or ''),job_id=j['job_id'],workflow_id=j['workflow_id']) or []
                report['artifacts_registered']+=len(extras)
            except Exception as exc:
                report['notes'].append('supplementary sync warning '+j['job_id']+': '+str(exc)[:300])
            ps.set_stage(pid,rev,stage,'DONE',input_fingerprint=fp,provider=str(j.get('provider_policy') or ''),model=str(j.get('model') or ''),current_job_id=j['job_id'],artifacts=[art['artifact_id']])

        runs=root/'runs'
        if runs.is_dir(): report['resumable_research_runs']=sum(1 for d in runs.glob('research_os_*') if d.is_dir() and ((d/'checkpoint.pkl').is_file() or any(d.glob('raw_journal_*.jsonl'))))
        fs=root/'full_simulation_runs'
        if fs.is_dir(): report['full_simulation_runs']=sum(1 for d in fs.iterdir() if d.is_dir() and ((d/'prediction_manifest.json').is_file() or (d/'resume_state.json').is_file()))
        if report['unlinked_jobs'] or report['unknown_history_preserved']:
            report['notes'].append('Historie bez spolehlivého project/revision/stage match zůstává zachovaná jako UNKNOWN; migrace ji nehádá.')
        report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as exc:
        report['status']='FAIL';report['error']=str(exc);report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%S')
    finally:
        ps.close()
    if write_report:
        (root/'MIGRATION_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    r=migrate();print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(0 if r.get('status')=='PASS' else 1)
