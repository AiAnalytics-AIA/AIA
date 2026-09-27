from pathlib import Path
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]


def _case(i):
    return {
        'system':'You are respondent engine',
        'messages':[{'role':'user','content':f'persona case {i}'}],
        'tools':[{'name':'answer','input_schema':{
            'type':'object','properties':{'answer':{'type':'string'}},
            'required':['answer'],'additionalProperties':False
        }}],
        'tool_choice':{'type':'tool','name':'answer'},
    }


def test_grouped_subscription_batches_cases_in_one_structured_call(monkeypatch):
    import pipeline, ai_router
    calls=[]
    def fake(**kw):
        calls.append(kw)
        payload=json.loads(kw['messages'][0]['content'])
        return {'data':{'responses':[{'case_id':x['case_id'],'response':{'answer':'A'+x['case_id']}} for x in payload['cases']]},
                'tok_in':101,'tok_out':17,'model':'sonnet'}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    monkeypatch.setenv('NPC_RESPONDENT_BATCH_CASES','96')
    monkeypatch.setenv('NPC_RESPONDENT_BATCH_CHARS','220000')
    journal=[]; progress=[]; events=[]
    out=pipeline._claude_subscription_grouped_responses([_case(i) for i in range(8)],'sonnet',max_tokens=60,
        progress=lambda a,b:progress.append((a,b)),on_result=lambda i,r:journal.append((i,r)),event_callback=events.append)
    assert len(calls)==1
    assert [json.loads(x['text'])['answer'] for x in out]==[f'A{i}' for i in range(8)]
    assert len(journal)==8 and progress[-1]==(8,8)
    assert any(x.get('phase')=='respondent_batch_start' for x in events)
    assert any(x.get('phase')=='respondent_batch_complete' for x in events)
    assert all(x.get('execution_mode')=='grouped_question_batch' for x in out)


def test_grouped_subscription_splits_failed_large_batch_and_keeps_results(monkeypatch):
    import pipeline, ai_router
    calls=[]
    def fake(**kw):
        payload=json.loads(kw['messages'][0]['content']); calls.append(len(payload['cases']))
        if len(payload['cases'])>2: raise TimeoutError('forced oversized batch timeout')
        return {'data':{'responses':[{'case_id':x['case_id'],'response':{'answer':'ok'}} for x in payload['cases']]},'model':'sonnet'}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    events=[]; journal=[]
    out=pipeline._claude_subscription_grouped_responses([_case(i) for i in range(4)],'sonnet',max_tokens=40,
        on_result=lambda i,r:journal.append(i),event_callback=events.append)
    assert calls[0]==4 and sorted(calls[1:])==[2,2]
    assert len(out)==4 and sorted(journal)==[0,1,2,3]
    assert any(x.get('phase')=='respondent_batch_split' for x in events)


def test_first_question_has_checkpoint_before_paid_calls():
    s=(ROOT/'dotaznik.py').read_text(encoding='utf-8')
    cp=s.index('checkpoint_stage": "before_first_respondent_call"')
    llm=s.index('fresh = _call_llm(',cp)
    assert cp < llm
    assert 'raw_journal_' in s
    assert 'journal_rows' in s and 'missing=[j for j in range(len(kw_list)) if j not in journal_rows]' in s


def test_respondent_watchdog_and_auto_retry_are_durable():
    p=(ROOT/'pipeline.py').read_text(encoding='utf-8')
    w=(ROOT/'worker_job.py').read_text(encoding='utf-8')
    assert 'NPC_RESPONDENT_QUESTION_TIMEOUT_S' in p
    assert 'RESPONDENT_QUESTION_WATCHDOG_TIMEOUT' in p
    assert "'respondent_batch_heartbeat'" in p
    assert 'RESPONDENT_AUTO_RETRY' in w
    assert "s.transition(job_id,'RETRYING'" in w
    assert "resume_available':(run_dir/'checkpoint.pkl').is_file()" in w


def test_launcher_restarts_unresponsive_server_and_stale_worker():
    s=(ROOT/'launcher_bootstrap.py').read_text(encoding='utf-8')
    assert 'HTTP backend proces žije, ale /health 3× po sobě neodpověděl' in s
    assert 'server_health_misses' in s
    assert '_worker_heartbeat_fresh' in s
    assert '_worker_has_fresh_running_job' in s
    assert 'RUNNING job má čerstvý heartbeat; restart odkládám' in s
    assert 'bez čerstvého scheduler ani job heartbeat' in s

def test_first_question_partial_journal_resumes_only_missing_cases(monkeypatch,tmp_path):
    import ai_router, claude_code_provider
    from dotaznik import run_dotaznik
    monkeypatch.setattr(claude_code_provider,'health',lambda:{'ok':True})
    first=[]; resumed=[]
    def answer(payload):
        return {'data':{'responses':[{'case_id':x['case_id'],'response':{'probabilities':[0.6,0.4]}} for x in payload['cases']]},'provider':'claude_code_subscription','model':'sonnet'}
    def fail_partial(**kw):
        payload=json.loads(kw['messages'][0]['content']); ids=[x['case_id'] for x in payload['cases']];first.append(ids)
        if len(ids)>2: raise TimeoutError('force split')
        if '2' in ids: raise TimeoutError('transport dies after first durable half')
        return answer(payload)
    def success(**kw):
        payload=json.loads(kw['messages'][0]['content']);resumed.append([x['case_id'] for x in payload['cases']]);return answer(payload)
    args=dict(otazky=[{'id':'Q1','text':'Koupili byste produkt?','typ':'vyber','kategorie':['Ano','Ne'],'povolit_nevim':False}],
              n=4,mode='sync',workers=1,ulozit=False,tichy=True,seed=1785,response_mode='probability',
              provider_policy='strict_claude_code_subscription',model='sonnet',checkpoint=True)
    run_dir=tmp_path/'run'
    monkeypatch.setattr(ai_router,'call_structured',fail_partial)
    with pytest.raises(RuntimeError,match='RESPONDENT_BATCH_FAILED'):
        run_dotaznik(run_dir=run_dir,**args)
    journal=run_dir/'raw_journal_Q1.jsonl'
    assert (run_dir/'checkpoint.pkl').is_file()
    assert len(journal.read_text(encoding='utf-8').splitlines())==2
    monkeypatch.setattr(ai_router,'call_structured',success)
    out=run_dotaznik(resume_dir=run_dir,**args)
    assert sum(map(len,resumed))==2
    assert out['n_chyb']==0 and out['run_status']=='COMPLETE'


def test_n120_uses_small_number_of_subscription_batches(monkeypatch):
    import pipeline, ai_router
    calls=[]
    def fake(**kw):
        payload=json.loads(kw['messages'][0]['content']); calls.append(len(payload['cases']))
        return {'data':{'responses':[{'case_id':x['case_id'],'response':{'answer':'ok'}} for x in payload['cases']]},'model':'sonnet'}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    monkeypatch.setenv('NPC_RESPONDENT_BATCH_CASES','48')
    monkeypatch.setenv('NPC_RESPONDENT_BATCH_CHARS','10000000')
    out=pipeline._claude_subscription_grouped_responses([_case(i) for i in range(120)],'sonnet',max_tokens=40)
    assert len(out)==120
    assert calls==[48,48,24]
    assert len(calls) <= 3
