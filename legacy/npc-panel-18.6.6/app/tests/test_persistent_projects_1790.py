from __future__ import annotations
import json, sqlite3, zipfile
from pathlib import Path

from project_store import ProjectStore
from artifact_store import ArtifactStore
from project_pipeline import RESEARCH_STAGES, SIMULATION_STAGES, stage_fingerprint
from provider_runtime import CLAUDE_CODE, CLAUDE_API, provider_for_stage, api_budget_check
from research_project import empty_project
from job_store import JobStore
from workflow_engine import create_standard
from worker_job import _park_for_subscription_quota, _reserve_stage_if_paid
from project_artifact_sync import sync_simulation


def make_project(title='Test'):
    p=empty_project(title=title)
    p['goal']='Zjistit reakci veřejnosti na testovanou změnu.'
    p['decision_use']='Rozhodnutí o dalším postupu.'
    return p


def test_project_created_immediately_and_survives_restart(tmp_path):
    db=tmp_path/'project.sqlite'
    ps=ProjectStore(db)
    r=ps.create_project(project_type='research',title='Persist',project=make_project('Persist'),runtime_version='17.9.0')
    pid,rev=r['project_id'],r['revision']
    assert len(ps.stages(pid,rev))==len(RESEARCH_STAGES)==13
    assert ps.get(pid)['status']=='DRAFT'
    ps.close()
    ps2=ProjectStore(db)
    got=ps2.get(pid)
    assert got and got['revision']==rev and got['project']['title']=='Persist'
    assert len(ps2.stages(pid,rev))==13
    ps2.close()


def test_atomic_artifact_idempotence_and_cross_revision_visibility(tmp_path):
    db=tmp_path/'project.sqlite'; root=tmp_path/'artifacts'
    ps=ProjectStore(db); p=make_project('A')
    r=ps.create_project(project_type='research',title='A',project=p,runtime_version='17.9.0'); pid,rev=r['project_id'],r['revision']
    astore=ArtifactStore(ps,root); fp=stage_fingerprint(p,'DEEP_RESEARCH','research')
    a1=astore.put_json(project_id=pid,revision=rev,stage_type='DEEP_RESEARCH',artifact_type='DEEP_RESEARCH',obj={'evidence':[1]},input_fingerprint=fp,provider=CLAUDE_CODE,model='sonnet')
    a2=astore.put_json(project_id=pid,revision=rev,stage_type='DEEP_RESEARCH',artifact_type='DEEP_RESEARCH',obj={'evidence':[1]},input_fingerprint=fp,provider=CLAUDE_CODE,model='sonnet')
    assert a1['artifact_id']==a2['artifact_id'] and astore.verify(a1['artifact_id'])
    ps.set_stage(pid,rev,'BRIEF','DONE')
    ps.set_stage(pid,rev,'DEEP_RESEARCH','DONE',input_fingerprint=fp,artifacts=[a1['artifact_id']])
    p2=json.loads(json.dumps(p)); p2['report_style']='board'
    r2=ps.save(p2,project_id=pid,reason='report_style_changed',force_new_revision=True)
    arts=ps.artifacts(pid,r2['revision'])
    reused=[a for a in arts if a['artifact_id']==a1['artifact_id']]
    assert reused and reused[0]['reused_from_revision']==rev
    assert ps.stage(pid,r2['revision'],'DEEP_RESEARCH')['status']=='DONE'
    ps.close()


def test_questionnaire_change_preserves_upstream_and_invalidates_fieldwork(tmp_path):
    ps=ProjectStore(tmp_path/'p.sqlite'); p=make_project('Q')
    r=ps.create_project(project_type='research',title='Q',project=p);pid,rev=r['project_id'],r['revision']
    for sid in ('BRIEF','DEEP_RESEARCH','RESEARCH_DESIGN','QUESTIONNAIRE','AUDIENCE','DIMENSIONS','SAMPLE_PLAN','FIELDWORK'):
        ps.set_stage(pid,rev,sid,'DONE')
    p2=json.loads(json.dumps(p)); p2['sections']=[{'type':'questions','title':'T','questions':[{'id':'Q1','text':'Nová otázka','typ':'vyber','kategorie':['A','B']}]}]
    r2=ps.save(p2,project_id=pid,reason='questionnaire_changed',force_new_revision=True)
    st={x['stage_type']:x['status'] for x in ps.stages(pid,r2['revision'])}
    assert st['BRIEF']=='DONE' and st['DEEP_RESEARCH']=='DONE' and st['RESEARCH_DESIGN']=='DONE'
    assert st['QUESTIONNAIRE']=='READY'
    assert st['FIELDWORK']=='NOT_STARTED'
    ps.close()


def test_report_style_change_only_impacts_report_delivery(tmp_path):
    ps=ProjectStore(tmp_path/'p.sqlite'); r=ps.create_project(project_type='research',title='R',project=make_project('R'));pid=r['project_id']
    impact=ps.impact_preview(pid,['report_style'])
    assert impact['root_stage']=='REPORT'
    assert impact['invalidate']==['REPORT','DELIVERY']
    assert 'FIELDWORK' in impact['preserve'] and 'ANALYSIS' in impact['preserve']
    ps.close()


def test_branch_restore_keep_original_revision(tmp_path):
    ps=ProjectStore(tmp_path/'p.sqlite'); r=ps.create_project(project_type='research',title='B',project=make_project('B'));pid,rev1=r['project_id'],r['revision']
    original=ps.get(pid,rev1)['sha256']
    br=ps.branch(pid,rev1,'Alternative')
    assert br['revision']>rev1 and br.get('branch_id')
    assert ps.get(pid,rev1)['sha256']==original
    restored=ps.restore_as_new_revision(pid,rev1)
    assert restored['revision']>br['revision'] and ps.get(pid,rev1)['sha256']==original
    ps.close()


def test_dual_runtime_never_silently_switches_to_paid_api():
    assert provider_for_stage(preferred_provider=CLAUDE_CODE,policy='CLAUDE_CODE_ONLY')==CLAUDE_CODE
    assert provider_for_stage(preferred_provider=CLAUDE_CODE,policy='CLAUDE_CODE_THEN_API',explicit_api_continue=False)==CLAUDE_CODE
    assert provider_for_stage(preferred_provider=CLAUDE_CODE,policy='CLAUDE_CODE_THEN_API',explicit_api_continue=True)==CLAUDE_API
    assert provider_for_stage(preferred_provider=CLAUDE_CODE,policy='CLAUDE_API_ONLY')==CLAUDE_API
    # Unsupported LIVE provider values normalize to Claude Code, not a third vendor.
    assert provider_for_stage(preferred_provider='openai',policy='CLAUDE_CODE_ONLY')==CLAUDE_CODE
    assert provider_for_stage(preferred_provider='openai',policy='OPENAI_ONLY')=='openai'


def test_project_api_budget_blocks_before_request_and_job_waits_for_user(tmp_path, monkeypatch):
    import worker_job
    monkeypatch.setattr(worker_job,'ROOT',tmp_path)
    ps=ProjectStore(tmp_path/'data'/'project_store.sqlite')
    r=ps.create_project(project_type='research',title='Budget',project=make_project('Budget'),preferred_provider=CLAUDE_API,provider_policy='CLAUDE_API_ONLY',max_api_cost_usd=0.1)
    pid,rev=r['project_id'],r['revision']; ps.close()
    js=JobStore(tmp_path/'jobs.sqlite')
    wid=js.create_workflow(project_id=pid,project_revision=rev,budget_usd=100)
    jid=js.add_job(wid,'research','background_research',status='READY',provider_policy=CLAUDE_API,project_id=pid,project_revision=rev,stage_id='DEEP_RESEARCH',artifact_target='DEEP_RESEARCH',input_fingerprint='x')
    js.transition(jid,'QUEUED'); js.transition(jid,'RUNNING')
    cc,res,amount=_reserve_stage_if_paid(js,wid,jid,'background_research',CLAUDE_API)
    assert res=='__WAITING__' and amount>0.1
    assert js.get_job(jid)['status']=='WAITING_USER'
    assert js.pending_approvals()[0]['context']['reason']=='PROJECT_API_BUDGET_LIMIT'
    ps=ProjectStore(tmp_path/'data'/'project_store.sqlite')
    assert ps.get(pid)['status']=='WAITING_USER'; ps.close()


def test_quota_parks_without_retry_burn_and_creates_resume_schedule(tmp_path):
    js=JobStore(tmp_path/'jobs.sqlite');wid=js.create_workflow(project_id='PRJ-X',project_revision=1)
    jid=js.add_job(wid,'run','respondent_run',status='READY',provider_policy=CLAUDE_CODE,project_id='PRJ-X',project_revision=1,stage_id='FIELDWORK',artifact_target='FIELDWORK_RESULTS')
    js.transition(jid,'QUEUED');js.transition(jid,'RUNNING')
    with js.cx() as c:c.execute('UPDATE jobs SET attempt=2,lease_owner="w",lease_until="2099-01-01T00:00:00" WHERE job_id=?',(jid,))
    cp=tmp_path/'run';cp.mkdir();(cp/'checkpoint.pkl').write_bytes(b'checkpoint')
    _park_for_subscription_quota(js,wid,jid,RuntimeError('session limit resetsAt=1893456000'),run_dir=cp)
    j=js.get_job(jid)
    assert j['status']=='WAITING_CREDITS' and j['attempt']==0 and j['lease_owner'] is None
    with js.cx() as c:
        schedules=c.execute('SELECT * FROM schedules').fetchall()
    assert len(schedules)==1


def test_standard_pipeline_has_eight_resumable_analysis_modules(tmp_path):
    js=JobStore(tmp_path/'jobs.sqlite'); p=make_project('Analysis')
    out=create_standard(js,project_id='PRJ-A',project_revision=1,project=p,mode='dry',confirm_live=False,idempotency_key='accept')
    wf=js.get_workflow(out['workflow_id']);mods=[j for j in wf['jobs'] if j['kind']=='analysis_module']
    assert len(mods)==8
    assert [j['input']['analysis_module'] for j in mods]==['audience','executive','hypotheses','implications','limitations','objects','research_questions','segments'] or sorted(j['input']['analysis_module'] for j in mods)==sorted(['executive','research_questions','objects','audience','segments','hypotheses','implications','limitations'])
    assert all(j['stage_id']=='ANALYSIS' for j in mods)
    assert any(j['kind']=='analysis_assemble' for j in wf['jobs'])


def test_simulation_project_has_13_stages_and_worlds_are_durable(tmp_path):
    ps=ProjectStore(tmp_path/'p.sqlite');r=ps.create_project(project_type='simulation',title='S',project={'title':'S','simulation':{}});pid,rev=r['project_id'],r['revision']
    assert len(ps.stages(pid,rev))==len(SIMULATION_STAGES)==13
    astore=ArtifactStore(ps,tmp_path/'arts');run=tmp_path/'simrun';(run/'worlds').mkdir(parents=True)
    (run/'world_model.json').write_text('{}',encoding='utf-8');(run/'prediction.json').write_text('{"ok":true}',encoding='utf-8');(run/'prediction_manifest.json').write_text('{}',encoding='utf-8');(run/'FROZEN.lock').write_text('frozen',encoding='utf-8')
    (run/'worlds'/'world_001_result.json').write_text('{"world":1}',encoding='utf-8');(run/'worlds'/'world_002_result.json').write_text('{"world":2}',encoding='utf-8')
    created=sync_simulation(astore,project_id=pid,revision=rev,input_fingerprint='simfp',provider=CLAUDE_CODE,model='sonnet',result={'run_dir':str(run)})
    types=[a['artifact_type'] for a in created]
    assert types.count('SIMULATION_WORLD_RESULT')==2
    assert {'FROZEN_PREDICTION','FROZEN_MANIFEST','FROZEN_LOCK'}.issubset(set(types))
    ps.close()


def test_project_export_contains_history_artifacts_and_sha_manifest(tmp_path):
    ps=ProjectStore(tmp_path/'p.sqlite');p=make_project('Export');r=ps.create_project(project_type='research',title='Export',project=p);pid,rev=r['project_id'],r['revision']
    astore=ArtifactStore(ps,tmp_path/'arts');a=astore.put_text(project_id=pid,revision=rev,stage_type='BRIEF',artifact_type='BRIEF_COMPILED',text='hello',input_fingerprint='fp')
    ps.set_stage(pid,rev,'BRIEF','DONE',artifacts=[a['artifact_id']])
    z=ps.export_zip(pid,tmp_path/'export.zip')
    with zipfile.ZipFile(z) as zz:
        names=set(zz.namelist())
        assert {'project.json','revisions.json','events.json','artifact_manifest.json','provider_events.json','SHA256SUMS.txt'}.issubset(names)
        assert any(n.startswith('artifacts/') for n in names)
    ps.close()


def test_additive_migration_preserves_old_project_row(tmp_path):
    data=tmp_path/'data';data.mkdir();db=data/'project_store.sqlite'
    c=sqlite3.connect(db)
    c.execute('CREATE TABLE projects(project_id TEXT PRIMARY KEY,title TEXT,parent_project_id TEXT,created_at TEXT,modified_at TEXT,current_revision INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE project_revisions(project_id TEXT,revision INTEGER,created_at TEXT,content_sha256 TEXT,project_json TEXT,analysis_json TEXT,questionnaire_version TEXT,panel_version TEXT,model TEXT,reason TEXT,PRIMARY KEY(project_id,revision))')
    c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?)',('OLD-1','Old',None,'2026','2026',1))
    c.execute('INSERT INTO project_revisions VALUES(?,?,?,?,?,?,?,?,?,?)',('OLD-1',1,'2026','sha',json.dumps(make_project('Old')),'{}','2','v17.8.9','sonnet','old'))
    c.commit();c.close()
    ps=ProjectStore(db)
    got=ps.get('OLD-1')
    assert got and got['project']['title']=='Old'
    cols={r[1] for r in ps.cx.execute('PRAGMA table_info(projects)').fetchall()}
    assert {'project_type','status','provider_policy','max_api_cost_usd'}.issubset(cols)
    ps.close()
