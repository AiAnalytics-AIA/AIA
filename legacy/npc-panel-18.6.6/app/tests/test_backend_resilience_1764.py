from pathlib import Path
import inspect

ROOT=Path(__file__).resolve().parents[1]


def test_first_brief_analysis_does_not_run_deep_research(monkeypatch):
    import ui_server, research_designer, research_context
    called={'deep':0,'analyze':0}
    def forbidden(*a,**k):
        called['deep']+=1
        raise AssertionError('Deep Research must not run in first brief analysis')
    def fake_analyze(brief,model='sonnet',provider=None):
        called['analyze']+=1
        return {'study_type':'custom','study_config':{},'object_type':'none','tracked_sets':[],
                'questions_for_user':[],'what_to_learn':['Zjistit hlavní reakci'],'standard_section_structure':[],
                'ready_for_questionnaire':True,'recommended_audience':{'description':'ČR 18+'}}
    def fake_skeleton(analysis,briefing,n=300):
        return {'title':'Test','goal':briefing.get('goal',''),'n':n,'sections':[],
                'run_policy':{'provider':'claude_code_subscription'}}
    monkeypatch.setattr(research_context,'run_dual_research',forbidden)
    monkeypatch.setattr(research_designer,'analyze_research',fake_analyze)
    monkeypatch.setattr(research_designer,'analysis_to_project_skeleton',fake_skeleton)
    out=ui_server.analyze_research_brief({'briefing':{'goal':'Zjistit reakci trhu'},'provider':'claude_code_subscription','model':'sonnet'})
    assert called=={'deep':0,'analyze':1}
    assert out['fast_brief_analysis'] is True
    assert out['research']['quality_status']=='NOT_RUN'
    assert out['project']['research_context'] is False


def test_frontend_reconnects_and_server_owns_ai_deadline():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'async function reconnectBackend(maxMs=30000)' in s or 'reconnectBackend=async function(maxMs=90000)' in s
    assert "await reconnectBackend(90000)" in s
    start=s.index('async function job(endpoint')
    block=s[start:s.index('function renderSteps()',start)]
    assert "server hard stop" in block
    assert "job neruším" in block
    assert "/cancel" not in block
    assert "Backend se restartuje" in s
    assert "zavřete starou kartu" not in s


def test_launcher_has_http_backend_watchdog():
    s=(ROOT/'launcher_bootstrap.py').read_text(encoding='utf-8')
    assert 'def start_server()' in s
    assert "HTTP backend skončil kódem" in s
    assert "automaticky jej obnovuji" in s
    assert "HTTP backend znovu READY" in s
    assert "server_restarts" in s
    assert "logs/server.log" in s or "SERVER_LOG" in s


def test_retried_http_job_creation_is_idempotent(monkeypatch,tmp_path):
    import ui_server
    from job_store import JobStore
    store=JobStore(tmp_path/'jobs.sqlite')
    monkeypatch.setattr(ui_server,'_ros_store',lambda:store)
    payload={'client_request_id':'same-request','provider':'anthropic','project':{'run_policy':{'provider':'anthropic'}}}
    j1=ui_server._start_job(dict(payload),'research_analysis')
    j2=ui_server._start_job(dict(payload),'research_analysis')
    assert j1==j2
    with store.cx() as c:
        assert c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==1
