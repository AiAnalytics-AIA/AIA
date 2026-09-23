import datetime as dt
import json
import pathlib
import sqlite3

import pytest


def _kw():
    schema={'type':'object','properties':{'choice':{'type':'string'}},'required':['choice'],'additionalProperties':False}
    return {'system':'sys','messages':[{'role':'user','content':'case'}],'tools':[{'name':'answer','input_schema':schema}]}


def test_1788_quota_does_not_split_batch(monkeypatch):
    import ai_router, pipeline
    calls=[];events=[]
    def boom(**kw):
        calls.append(kw)
        raise RuntimeError("[QUOTA] You've hit your session limit rate_limit_event resetsAt:1787590800 out_of_credits")
    monkeypatch.setattr(ai_router,'call_structured',boom)
    with pytest.raises(RuntimeError,match='RESPONDENT_WAITING_CREDITS'):
        pipeline._claude_subscription_grouped_responses([_kw()]*8,'sonnet',max_tokens=40,event_callback=events.append)
    assert len(calls)==1
    assert any(e.get('phase')=='respondent_waiting_credits' for e in events)
    assert not any(e.get('phase')=='respondent_batch_split' for e in events)


def test_1788_windows_temp_lock_cannot_mask_quota(monkeypatch):
    import claude_code_provider as c
    monkeypatch.setattr(c,'executable',lambda:'claude')
    monkeypatch.setattr(c,'auth_status',lambda:{'subscription_verified':True,'verification_basis':'auth_json_subscription'})
    monkeypatch.setattr(c,'supports_required_cli',lambda:True)
    monkeypatch.setattr(c,'_acquire_slot',lambda timeout:object())
    monkeypatch.setattr(c,'_lock_release',lambda x:None)
    monkeypatch.setattr(c,'_base_cli_command',lambda *a,**k:['claude'])
    monkeypatch.setattr(c,'subscription_env',lambda:{})
    monkeypatch.setattr(c,'_run_stream',lambda *a,**k:{'returncode':1,'outer':{'subtype':'success','is_error':True,'result':"You've hit your session limit resetsAt:1787590800"},'stderr':'','raw_lines':['{"type":"rate_limit_event","rate_limit_info":{"resetsAt":1787590800,"overageDisabledReason":"out_of_credits"}}']})
    monkeypatch.setattr(c.shutil,'rmtree',lambda *a,**k: (_ for _ in ()).throw(PermissionError(32,'in use')))
    with pytest.raises(c.ClaudeCodeLimit,match='session limit'):
        c._invoke(system='x',messages=[{'role':'user','content':'y'}],timeout=5)


def test_1788_quota_parks_and_auto_resumes(tmp_path):
    from job_store import JobStore
    from worker_job import _park_for_subscription_quota,_quota_reset_at
    from scheduler import Scheduler
    st=JobStore(tmp_path/'jobs.sqlite')
    wid=st.create_workflow(project_id='P1',project_revision=1)
    jid=st.add_job(wid,'run','respondent_run',status='READY',input_data={'project':{'run_policy':{'provider':'claude_code_subscription'}}})
    st.transition(jid,'QUEUED'); st.transition(jid,'RUNNING')
    with st.cx() as c:c.execute('UPDATE jobs SET attempt=3 WHERE job_id=?',(jid,))
    run_dir=tmp_path/'run';run_dir.mkdir();(run_dir/'checkpoint.pkl').write_bytes(b'x')
    exc=RuntimeError("[QUOTA] You've hit your session limit rate_limit_event resetsAt:1787590800 out_of_credits")
    reset,_=_quota_reset_at(exc)
    assert _park_for_subscription_quota(st,wid,jid,exc,run_dir=run_dir)==0
    j=st.get_job(jid);w=st.get_workflow(wid)
    assert j['status']=='WAITING_CREDITS' and j['attempt']==0
    assert w['status']=='WAITING_CREDITS'
    assert j['error']['auto_resume_at']==reset
    with st.cx() as c: rows=c.execute('SELECT * FROM schedules WHERE enabled=1').fetchall()
    assert len(rows)==1 and rows[0]['next_run_at']==reset
    Scheduler(st,project_store_path=tmp_path/'projects.sqlite').tick(dt.datetime.fromisoformat(reset)+dt.timedelta(seconds=5))
    assert st.get_job(jid)['status']=='QUEUED'


def test_1788_launcher_heartbeat_is_not_pid_fragile(tmp_path,monkeypatch):
    import launcher_bootstrap as lb
    root=tmp_path; (root/'data').mkdir()
    db=root/'data'/'research_os.sqlite'
    cx=sqlite3.connect(db)
    cx.execute('CREATE TABLE worker_state(worker_id TEXT,pid INTEGER,heartbeat_at TEXT,status TEXT,current_job_id TEXT,metadata_json TEXT)')
    cx.execute('CREATE TABLE jobs(job_id TEXT,status TEXT,heartbeat_at TEXT)')
    now=dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    cx.execute('INSERT INTO worker_state VALUES(?,?,?,?,?,?)',('WKR-real',99999,now,'BUSY','JOB-1','{}'))
    cx.execute('INSERT INTO jobs VALUES(?,?,?)',('JOB-1','RUNNING',now));cx.commit();cx.close()
    monkeypatch.setattr(lb,'ROOT',root)
    # Deliberately pass a different supervisor PID: durable heartbeat remains authoritative.
    assert lb._worker_heartbeat_fresh(12345,max_age_s=45)
    assert lb._worker_has_fresh_running_job(12345,max_age_s=45)


def test_1788_ui_maps_waiting_credits_as_paused():
    root=pathlib.Path(__file__).resolve().parents[1]
    server=(root/'ui_server.py').read_text(encoding='utf-8')
    ui=(root/'ui_app.html').read_text(encoding='utf-8')
    assert '"WAITING_CREDITS":"paused"' in server
    assert "j.state==='paused'" in ui
    assert 'checkpoint zůstává uložený' in ui
