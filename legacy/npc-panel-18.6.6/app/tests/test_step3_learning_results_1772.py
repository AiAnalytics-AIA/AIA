from pathlib import Path
import json


def _temp_library(monkeypatch,tmp_path):
    import data_library as dl
    monkeypatch.setattr(dl,'DB_PATH',tmp_path/'library.sqlite')
    monkeypatch.setattr(dl,'FILES_DIR',tmp_path/'files')
    monkeypatch.setattr(dl,'OVERLAY_PATH',tmp_path/'overlays.json')
    return dl


def test_final_review_uses_library_context_and_friendly_knowledge_statement():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    block=s[s.index('def final_ai_review'):s.index('\ndef ',s.index('def final_ai_review')+5)]
    assert 'knowledge_context_for_project' in block
    assert 'knowledge_statement' in block
    assert 'data_library_context' in block


def test_client_report_uses_approved_library_context_as_context_not_truth():
    s=Path('client_report_v2.py').read_text(encoding='utf-8')
    assert 'knowledge_context_for_project' in s
    assert 'data_library_context' in s
    assert 'knowledge-only' in s.lower() or 'knowledge_only' in s.lower() or 'individually measured' in s.lower()


def test_learning_cycle_without_external_evidence_creates_no_dimension_proposals(monkeypatch,tmp_path):
    dl=_temp_library(monkeypatch,tmp_path)
    import ai_router
    def fake(**kwargs):
        return {'data':{
            'summary':'Chybí externí potvrzení.',
            'gaps':[{'topic':'cenová citlivost','why':'doplnit real data','priority':'high'}],
            'research_topics':['ČR price sensitivity 2026'],
            # Even if an LLM violates the prompt, code must suppress dimension proposals without external evidence.
            'dimension_impacts':[{'dimension_id':'cena_x','dimension_label':'Cena X','action':'new_dimension','rationale':'x','evidence_summary':'synthetic only','confidence':0.9}],
        }}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    out=dl.learn_from_completed_workflow(workflow_id='WF-NO-EVIDENCE',project={'title':'P','goal':'G'},research={'accepted':[]},verification={})
    assert out['status']=='GAPS_IDENTIFIED'
    assert out['proposal_ids']==[]
    assert dl.list_proposals()==[]


def test_learning_cycle_with_external_evidence_creates_approval_gated_proposal(monkeypatch,tmp_path):
    dl=_temp_library(monkeypatch,tmp_path)
    import ai_router
    def fake(**kwargs):
        return {'data':{
            'summary':'Externí evidence navrhuje zpřesnit cenovou dimenzi.',
            'gaps':[], 'research_topics':[],
            'dimension_impacts':[{'dimension_id':'price_sensitivity_v2','dimension_label':'Cenová citlivost','action':'refine_dimension','rationale':'novější česká evidence','evidence_summary':'Český zdroj 2026','confidence':0.82}],
        }}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    research={'accepted':[{'claim':'Cena je silnější driver','why_relevant':'ČR spotřebitelé','source_title':'Study','source_url':'https://example.test','source_date':'2026','source_quality':'high'}]}
    out=dl.learn_from_completed_workflow(workflow_id='WF-EVIDENCE',project={'title':'P','goal':'G'},research=research,verification={})
    assert out['status']=='PROPOSALS_READY'
    assert len(out['proposal_ids'])==1
    p=dl.list_proposals()[0]
    assert p['status']=='PROPOSED'
    assert p['runtime_status']=='KNOWLEDGE_CONTEXT'
    assert dl.active_dimensions()=={}


def test_approved_learning_proposal_enters_knowledge_layer_and_history(monkeypatch,tmp_path):
    dl=_temp_library(monkeypatch,tmp_path)
    cx=dl._connect()
    try:
        cx.execute('INSERT INTO dimension_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?)',('P1',None,dl._now(),'dim_x','Dim X','calibration_update','reason','external evidence',0.8,'PROPOSED',None));cx.commit()
    finally:cx.close()
    dl._save_proposal_spec('P1',origin='workflow_external_evidence',action='calibration_update',spec={'population_scope':'CZ18+'})
    out=dl.decide_proposal('P1','APPROVE')
    d=out['active_dimensions']['dim_x']
    assert d['runtime_status']=='CALIBRATION_CANDIDATE'
    assert d['origin']=='workflow_external_evidence'
    cx=dl._connect()
    try:n=cx.execute('SELECT COUNT(*) FROM calibration_history WHERE proposal_id=?',('P1',)).fetchone()[0]
    finally:cx.close()
    assert n==1


def test_worker_learning_cycle_is_nonblocking_and_exported():
    s=Path('worker_job.py').read_text(encoding='utf-8')
    block=s[s.index("elif kind == 'final_report'"):s.index("elif kind == 'condition_gate'")]
    assert 'learn_from_completed_workflow' in block
    assert "'status':'DEFERRED'" in block
    assert 'model_learning_json' in block
    assert 'learning_cycle' in block


def test_step3_ui_has_learning_tab_final_review_knowledge_and_simplified_results():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    a=s.index('// 17.7.2 STEP 3')
    b=s.index('async function boot()',a)
    block=s[a:b]
    assert 'Učení modelu' in block
    assert 'knowledge_statement' in block
    assert 'Syntetické odpovědi nejsou validační pravda' in block
    assert 'Výstupy ke stažení' in block
    assert 'Co jsme zjistili' in block
    assert 'Co doporučujeme' in block
    assert 'Metodika a audit' in block
    # Normal results must not lead with internal validation codes.
    for forbidden in ['joint_unvalidated','UNVALIDATED','donor support','population anchors','validation truth']:
        assert forbidden not in block


def test_learning_ui_explains_no_self_calibration_from_synthetic_answers():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    a=s.index('// 17.7.2 STEP 3');b=s.index('async function boot()',a);block=s[a:b]
    assert 'Panel se nesmí kalibrovat sám' in block
    assert 'externí evidenci' in block or 'externí evidence' in block
    assert 'schválení' in block.lower()
