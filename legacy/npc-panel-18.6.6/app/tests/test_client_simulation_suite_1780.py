from pathlib import Path
from types import SimpleNamespace
import json, shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_standalone_simulation_ui_has_ai_context_and_batch_actions():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    for x in ['/api/simulation/context/enrich','/api/simulation/context/resolve','/api/scenario/compile-batch','/api/fullsim/batch-pipeline','AI doplní kontext + dohledá trh','Dohledat a doplnit','Porovnat více variant']:
        assert x in s
    assert "quick:{label:'Rychlá',n:50" in s
    assert "standard:{label:'Standard',n:80" in s
    assert "deep:{label:'Důkladná',n:120" in s
    block=s[s.index('function simPreset1773'):s.index('function researchHasContext1773')]
    assert "model:'haiku'" not in block


def test_scenario_batch_contracts_are_independent(monkeypatch):
    import scenario_compiler as sc
    calls=[]
    def fake(text,**kwargs):
        calls.append(text)
        i=len(calls)
        return {'status':'REVIEW_REQUIRED','event':text,'shifts':[{'factor':f'f{i}','direction':'mixed','magnitude_sd':0.1*i,'scope':'all','mechanism':f'm{i}','confidence':.4,'evidence_basis':'test'}], 'assumptions':[], 'unknowns':[], 'claim_policy':{}}
    monkeypatch.setattr(sc,'compile_scenario',fake)
    out=sc.compile_scenario_variants('Zlevníme produkt',[{'label':'-10 %','variable':'Cena','value':-10,'unit':'%'},{'label':'-30 %','variable':'Cena','value':-30,'unit':'%'}],project={'simulation_context':{'sha256':'ctx'}})
    assert len(calls)==2 and calls[0]!=calls[1]
    assert out['variants'][0]['shifts'][0]['magnitude_sd'] != out['variants'][1]['shifts'][0]['magnitude_sd']
    assert out['nonlinearity_policy'].lower().startswith('each variant')
    assert out['context_sha256']=='ctx'


def test_context_enrichment_combines_research_and_library(monkeypatch):
    import simulation_context as sc
    import research_context
    import data_library
    draft={k:'' for k in ['title','subject','client','product_service','category','market','geography','current_state','current_price','price_unit','price_architecture','brand_positioning','decision','summary']}
    draft.update({'title':'T','subject':'Káva','product_service':'Produkt X','category':'káva','market':'ČR','geography':'ČR','decision':'Cena','summary':'ctx','competitors':[],'customer_segments':[],'purchase_drivers':['reference price'],'category_dynamics':[],'constraints':[],'outcomes':['nákup'],'known_facts':[],'assumptions':[],'uncertainties':[{'id':'U1','question':'Aktuální cena?','why_it_matters':'price','status':'UNRESOLVED','answer':'','confidence':0,'source_urls':[],'recommended_action':'research'}],'research_questions':['Jaká je aktuální cena produktu X?']})
    synth=json.loads(json.dumps(draft));synth['current_price']='499 Kč';synth['known_facts']=['Aktuální cena 499 Kč'];synth['uncertainties'][0].update({'status':'RESOLVED','answer':'499 Kč','confidence':.9,'source_urls':['https://example.com'],'recommended_action':'use_evidence'})
    seq=[draft,synth]
    monkeypatch.setattr(sc,'call_structured',lambda **kw:{'data':seq.pop(0),'provider':'claude_code_subscription','model':'sonnet'})
    bundle=research_context.ResearchBundle(True,'káva','now',[],[{'claim':'Cena 499 Kč','source_title':'Shop','source_url':'https://example.com','topics':['price']}],[],{},'DUAL_VERIFIED','sha')
    monkeypatch.setattr(research_context,'run_dual_research',lambda *a,**k:bundle)
    monkeypatch.setattr(data_library,'knowledge_context_for_project',lambda *a,**k:{'dimensions':[{'dimension_id':'D_PRICE'}],'count':1})
    out=sc.enrich_simulation_context('Simuluj cenu produktu X',provider='claude_code_subscription')
    assert out['current_price']=='499 Kč'
    assert out['uncertainties'][0]['status']=='RESOLVED'
    assert out['evidence']['accepted'][0]['source_url']=='https://example.com'
    assert out['data_library']['count']==1
    assert out['sha256']


def _fake_run(tmp_path,label='V1'):
    d=tmp_path/label; d.mkdir(parents=True,exist_ok=True)
    for name in ('prediction.json','prediction_manifest.json','FROZEN.lock','FULL_SIMULATION_REPORT.html'):(d/name).write_text('{}',encoding='utf-8')
    pred={'run_status':'COMPLETE','primary_method':'FULL_SIMULATION','methods':{
        'FULL_SIMULATION':{'questions':{'Q1':{'text':'Nákup','estimate_pct':{'Ano':60,'Ne':40},'interval_95':{'Ano':{'low':55,'high':65},'Ne':{'low':35,'high':45}}}}},
        'NPC_CORE':{'questions':{'Q1':{'text':'Nákup','estimate_pct':{'Ano':50,'Ne':50},'interval_95':{}}}}
    }}
    return {'run_id':label,'run_dir':str(d),'report_html':str(d/'FULL_SIMULATION_REPORT.html'),'prediction':pred,'manifest':{'manifest_sha256':'x'}}


def test_batch_pipeline_reuses_evidence_but_builds_each_variant(monkeypatch,tmp_path):
    import simulation_batch as sb
    import full_simulation as fs
    preps=[];runs=[]
    def prep(spec,**kw): preps.append((dict(spec),kw.get('existing_research'))); return {'world_model':{'sha256':spec['scenario_contract']['variant']['id']},'research':{},'research_summary':{}}
    def run(spec,**kw): runs.append((dict(spec),kw.get('prepared'))); return _fake_run(tmp_path,spec['scenario_contract']['variant']['id'])
    monkeypatch.setattr(fs,'prepare_full_simulation',prep);monkeypatch.setattr(fs,'run_full_simulation',run)
    monkeypatch.setattr(fs,'validate_full_simulation_result',lambda r,**kw:r|{'artifact_gate':{'status':'PASS'}})
    monkeypatch.setattr(sb,'_ai_interpret',lambda *a,**k:{'executive_summary':'E','decision_answer':'D','best_option':'V2','tradeoffs':[],'nonlinear_effects':['threshold'],'brand_risks':['premium signal'],'segment_implications':[],'uncertainties':[],'recommendations':['R'],'do_not_overclaim':[]})
    ctx={'sha256':'ctx','evidence':{'accepted':[{'claim':'x'}],'quarantined':[]}}
    contracts=[]
    for i,val in enumerate((-10,-30),1):contracts.append({'status':'APPROVED','variant':{'id':f'V{i}','label':f'{val}%','variable':'Cena','value':val,'unit':'%','change':'price'},'shifts':[]})
    old=sb.BATCH_ROOT;sb.BATCH_ROOT=tmp_path/'batches';sb.BATCH_ROOT.mkdir()
    try: out=sb.run_simulation_batch({'mode':'sync','provider':'claude_code_subscription','model':'sonnet','include_core_baseline':True,'seed':1},contracts,project={},panel_path='panel.csv',context=ctx,confirm_live=True)
    finally: sb.BATCH_ROOT=old
    assert len(preps)==2 and len(runs)==2
    assert preps[0][1] is ctx['evidence'] and preps[1][1] is ctx['evidence']
    assert runs[0][1]['world_model']['sha256'] != runs[1][1]['world_model']['sha256']
    assert out['artifact_gate']['status']=='PASS'
    assert Path(out['artifacts']['csv']).is_file() and Path(out['artifacts']['xlsx']).is_file() and Path(out['artifacts']['report_html']).is_file()
    assert out['interpretation']['best_option']=='V2'


def test_fullsim_artifact_gate_fails_closed(tmp_path):
    import full_simulation as fs
    d=tmp_path/'run';d.mkdir();(d/'prediction.json').write_text('{}');(d/'prediction_manifest.json').write_text('{}');(d/'FROZEN.lock').write_text('x')
    r={'run_dir':str(d),'prediction':{'run_status':'COMPLETE','methods':{'FULL_SIMULATION':{},'NPC_CORE':{}}},'manifest':{'manifest_sha256':'x'}}
    with pytest.raises(RuntimeError,match='FULLSIM_ARTIFACT_GATE_FAILED'):fs.validate_full_simulation_result(r)


def test_legacy_job_result_paths_are_browser_accessible():
    s=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    assert 'full_simulation_batches' in s and '"/artifacts/"' in s
    html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert "v.startsWith('/artifacts/')" in html


def test_scenario_unknowns_can_be_researched_or_filled_manually():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'Dohledat tyto nejistoty' in s
    assert 'Doplnit ručně' in s
    assert 'function editScenarioUnknowns1780()' in s

def test_batch_client_delivery_contains_audit_and_zip_contract():
    s=(ROOT/'simulation_batch.py').read_text(encoding='utf-8')
    assert 'SIMULATION_BATCH_CLIENT_DELIVERY.zip' in s
    assert 'simulation_batch.json' in s and 'batch_manifest.json' in s
    assert 'DELIVERY_SHA256SUMS.txt' in s
    ui=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'CLIENT DELIVERY · ZIP' in ui
