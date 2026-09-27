from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_ui_cancel_is_guarded_confirmed_and_audited():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'id="progressCancel"' in s and 'disabled>Zrušit běh</button>' in s
    assert 'PROGRESS_CANCEL_ARM_AT=Date.now()+5000' in s
    assert "confirm('Opravdu chcete tento běh zrušit?" in s
    assert "source:'ui_progress_button'" in s
    assert "reason:'explicit_user_confirmation'" in s
    assert 'FOREGROUND_JOB_STARTING||ACTIVE_JOB_ID' in s
    assert 'FOREGROUND_JOB_ALREADY_ACTIVE' in s


def test_cancelled_scenario_is_not_rendered_as_failure():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    i=s.rfind('compileSimChange1773=async function(){')
    line=s[i:s.find('\n',i)]
    assert 'isCancelledError1786(e)' in line
    assert 'SIM_ERROR_1773=null' in line
    assert 'Příprava scénáře byla zrušena' in line


def test_cancel_provenance_is_stored(tmp_path):
    from job_store import JobStore
    store=JobStore(tmp_path/'research_os.sqlite')
    wid=store.create_workflow(project_id='P1',project_revision=1,workflow_type='t')
    jid=store.add_job(wid,'x','legacy_task',status='READY')
    assert store.request_cancel(jid,source='ui_progress_button',reason='explicit_user_confirmation') is True
    ev=[x for x in store.updates(0,100) if x['job_id']==jid and x['event_type']=='CANCEL_REQUESTED'][-1]
    assert ev['payload']['source']=='ui_progress_button'
    assert ev['payload']['reason']=='explicit_user_confirmation'


def test_scenario_compiler_preserves_job_cancel(monkeypatch):
    import scenario_compiler as sc
    from claude_code_provider import ClaudeCodeCancelled
    def boom(**kwargs):
        raise ClaudeCodeCancelled('JOB_CANCELLED')
    monkeypatch.setattr(sc,'call_structured',boom)
    with pytest.raises(ClaudeCodeCancelled):
        sc.compile_scenario('Zlevníme produkt o 10 %',project={},provider='claude_code_subscription')


def test_worker_watchdog_accepts_fresh_running_child_heartbeat(tmp_path,monkeypatch):
    import launcher_bootstrap as lb
    from job_store import JobStore
    monkeypatch.setattr(lb,'ROOT',tmp_path)
    db=tmp_path/'data'/'research_os.sqlite'
    st=JobStore(db)
    wid=st.create_workflow(project_id='P',project_revision=1,workflow_type='t')
    jid=st.add_job(wid,'run','legacy_task',status='READY',priority=50)
    st.queue_ready_jobs(wid)
    st.worker_heartbeat('WKR-test',43210,'READY',None,{})
    j=st.claim('WKR-test')
    assert j and j['job_id']==jid
    st.worker_heartbeat('WKR-test',43210,'BUSY',jid,{})
    st.heartbeat(jid,'WKR-test')
    assert lb._worker_has_fresh_running_job(43210,max_age_s=60) is True


def test_launcher_has_independent_server_and_worker_watchdog_clocks():
    s=(ROOT/'launcher_bootstrap.py').read_text(encoding='utf-8')
    assert 'last_server_health_check=0.0' in s
    assert 'last_worker_health_check=0.0' in s
    assert "elif _worker_has_fresh_running_job(worker.pid):" in s
    assert 'restart odkládám' in s


def test_worker_honors_cancel_before_provider_dispatch():
    s=(ROOT/'worker_job.py').read_text(encoding='utf-8')
    assert "if s.cancel_requested(job_id):" in s
    assert "message='cancelled before task dispatch'" in s
