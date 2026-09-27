from pathlib import Path
import zipfile


def _report():
    return {
        'title':'T','subtitle':'','executive_summary':'Shrnutí','decision_answer':'Odpověď',
        'research_question_answers':[],
        'key_findings':[{'headline':'Zjištění','finding':'Výsledek','meaning':'Význam','evidence':'Q1'}],
        'implications':[{'action':'Akce','why':'Proto'}],
        'validation_summary':'','confidence_summary':'','method_summary':'','limitations':['Limit'],'closing':'',
        '_meta':{'quality_gate':{'passed':True},'report_generation_mode':'AI'}
    }


def test_research_final_report_survives_optional_export_failure(monkeypatch,tmp_path):
    import worker_job, client_report_v2, output_pack
    from job_store import JobStore
    store=JobStore(tmp_path/'jobs.sqlite')
    monkeypatch.setattr(worker_job,'JobStore',lambda *a,**k:store)
    monkeypatch.setattr(worker_job,'ROOT',tmp_path)
    monkeypatch.setattr(client_report_v2,'compose_report',lambda *a,**k:_report())
    monkeypatch.setattr(output_pack,'export_management_deck_pptx',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('synthetic pptx failure')))
    data=tmp_path/'respondents.csv';data.write_text('id,Q1\n1,Ano\n',encoding='utf-8')
    xlsx=tmp_path/'results.xlsx';xlsx.write_bytes(b'xlsx-test')
    rh=tmp_path/'run.html';rh.write_text('<h1>run</h1>',encoding='utf-8')
    project={'title':'T','goal':'G','model':'sonnet','run_policy':{'provider':'claude_code_subscription'},'sections':[{'type':'questions','questions':[{'id':'Q1','text':'Q','typ':'vyber','kategorie':['Ano','Ne']}]}]}
    wid=store.create_workflow(project_id='P',project_revision=1,workflow_type='standard_study')
    outputs={
      'research':{'bundle':{}},'aggregate':{'summary':{'vysledky':{'Q1':{'celkem_pct':{'Ano':60,'Ne':40}}}},'batteries':[]},
      'interpret':{'analysis':{'executive_answer':'A','key_findings':[],'implications':[],'_meta':{'evidence_validation':{'passed':True}}}},
      'verify':{'verification':{},'verification_status':'PASS'},'alignment':{'alignment':{}},'donor_qc':{'donor_support':{}},
      'run':{'result':{'main':{'dataset_csv':str(data),'xlsx':str(xlsx),'html':str(rh),'summary':{}}}},
    }
    jobs={}
    kindmap={'research':'background_research','aggregate':'aggregate_results','interpret':'interpret_results','verify':'external_verification','alignment':'reality_alignment','donor_qc':'donor_qc','run':'respondent_run'}
    for key,out in outputs.items():
        jid=store.add_job(wid,key,kindmap[key],status='READY',input_data={'project':project,'mode':'sync'})
        store.transition(jid,'COMPLETED',output=out,force=True);jobs[key]=jid
    report=store.add_job(wid,'report','final_report',status='READY',input_data={'project':project,'mode':'sync'})
    for jid in jobs.values():store.add_dependency(report,jid)
    store.transition(report,'RUNNING',force=True)
    rc=worker_job.execute(report,'test-worker')
    assert rc==0
    j=store.get_job(report);assert j['status']=='COMPLETED'
    out=j['output'];assert out['report_status']=='COMPLETED_DEGRADED_EXPORT'
    for k in ('report_docx','report_html','report_json','output_manifest','client_delivery_zip','respondent_dataset_csv','respondent_results_xlsx'):
        assert out.get(k) and Path(out[k]).is_file(),k
    assert any(x.get('artifact')=='management_deck_pptx' for x in out['artifact_warnings'])
    with zipfile.ZipFile(out['client_delivery_zip']) as z:
        assert any(n.endswith('.docx') for n in z.namelist()) and any(n.endswith('.csv') for n in z.namelist())


def test_fullsim_report_renderer_failure_still_produces_results(monkeypatch,tmp_path):
    import full_simulation as fs
    from legacy_job_dispatch import execute_legacy
    monkeypatch.setattr(fs,'RUN_ROOT',tmp_path/'runs'); monkeypatch.setattr(fs,'BENCH_ROOT',tmp_path/'bench')
    fs.RUN_ROOT.mkdir();fs.BENCH_ROOT.mkdir()
    monkeypatch.setattr(fs,'write_run_html',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('synthetic html renderer failure')))
    spec={'topic':'Results guarantee','questions':[{'id':'Q1','text':'Dopad?','kategorie':['Ano','Ne']}],'objective':'scenario_nowcast','domain':'general','n':50,'worlds':2,'min_worlds':2,'adaptive_worlds':False,'mode':'dry','research_enabled':False,'world_model_provider':'heuristic','include_core_baseline':True,'include_demographics_baseline':False,'diagnostic_mode':'off','save_world_overlays':False,'use_learning_profile':False,'auto_wording_stress':False,'scenario_contract':{'status':'APPROVED','shifts':[{'factor':'price','direction':'decrease','magnitude_sd':0.2,'scope':'all','mechanism':'test','confidence':0.4,'evidence_basis':'hypothesis'}]},'seed':1787001}
    project={'title':'T','goal':'G','run_policy':{'provider':'claude_code_subscription'},'audience':{'source_mode':'population'}}
    out=execute_legacy('fullsim_pipeline',{'project':project,'spec':spec,'confirm_live':False},'RES-GUARANTEE')
    assert out['artifact_gate']['status']=='PASS'
    assert out['results_status']=='RESULTS_READY_DEGRADED_EXPORT'
    assert any(x.get('artifact')=='simulation_report_html' for x in out['artifact_warnings'])
    for k in ('report_html','results_csv','results_xlsx','client_delivery_zip'):assert Path(out[k]).is_file(),k


def test_batch_ai_interpretation_failure_falls_back(monkeypatch,tmp_path):
    import simulation_batch as sb, full_simulation as fs
    sb.BATCH_ROOT=tmp_path/'batches';sb.BATCH_ROOT.mkdir()
    def fakeprep(spec,**kw):return {'world_model':{},'research_summary':{}}
    def fakerun(spec,**kw):
        d=tmp_path/spec['scenario_contract']['variant']['id'];d.mkdir(exist_ok=True)
        for n in ('prediction.json','prediction_manifest.json','FROZEN.lock','FULL_SIMULATION_REPORT.html','SIMULATION_RESULTS.csv','SIMULATION_RESULTS.xlsx','SIMULATION_CLIENT_DELIVERY.zip'):(d/n).write_bytes(b'x')
        pred={'run_status':'COMPLETE','primary_method':'FULL_SIMULATION','methods':{'FULL_SIMULATION':{'questions':{'Q1':{'text':'Q','estimate_pct':{'Ano':60}}}},'NPC_CORE':{'questions':{'Q1':{'text':'Q','estimate_pct':{'Ano':50}}}}}}
        return {'run_id':spec['scenario_contract']['variant']['id'],'run_dir':str(d),'report_html':str(d/'FULL_SIMULATION_REPORT.html'),'prediction':pred,'manifest':{'manifest_sha256':'x'},'artifact_gate':{'status':'PASS'}}
    monkeypatch.setattr(fs,'prepare_full_simulation',fakeprep);monkeypatch.setattr(fs,'run_full_simulation',fakerun);monkeypatch.setattr(fs,'validate_full_simulation_result',lambda r,**kw:r)
    monkeypatch.setattr(sb,'_ai_interpret',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('comparison AI down')))
    cs=[]
    for i,v in enumerate((-10,-30),1):cs.append({'status':'APPROVED','variant':{'id':f'V{i}','label':str(v),'variable':'Cena','value':v,'unit':'%','change':'x'},'shifts':[]})
    out=sb.run_simulation_batch({'mode':'sync','provider':'claude_code_subscription','comparison_ai':True,'include_core_baseline':True,'seed':1},cs,project={},context={},confirm_live=True)
    assert out['artifact_gate']['status']=='PASS'
    assert out['results_status']=='RESULTS_READY_DEGRADED_EXPORT'
    assert any(x.get('artifact')=='comparison_ai_interpretation' for x in out['artifact_warnings'])
    for k in ('csv','xlsx','report_html','client_delivery_zip'):assert Path(out['artifacts'][k]).is_file(),k


def test_respondent_export_is_results_first_contract():
    s=Path('prototype_server.py').read_text(encoding='utf-8')
    assert "'status':'RESULTS_READY'" in s or '"status":"RESULTS_READY"' in s
    assert 'RESULTS_CORE.json' in s
    assert 'result_warnings' in s
