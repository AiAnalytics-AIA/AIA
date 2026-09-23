from pathlib import Path
import pandas as pd
import pytest

import respondent_dialogue as rd


def _df():
    return pd.DataFrame([
        {'respondent_id':'R1','segment':'Energy','dem_age':24,'att_energy':9,'att_novelty':8,'obj_Monster':10,'obj_Red Bull':9,'obj_Cola':3},
        {'respondent_id':'R2','segment':'Energy','dem_age':28,'att_energy':8,'att_novelty':9,'obj_Monster':9,'obj_Red Bull':8,'obj_Cola':4},
        {'respondent_id':'R3','segment':'Other','dem_age':44,'att_energy':3,'att_novelty':2,'obj_Monster':3,'obj_Red Bull':4,'obj_Cola':8},
        {'respondent_id':'R4','segment':'Other','dem_age':52,'att_energy':2,'att_novelty':3,'obj_Monster':2,'obj_Red Bull':3,'obj_Cola':9},
        {'respondent_id':'R5','segment':'Other','dem_age':39,'att_energy':4,'att_novelty':4,'obj_Monster':4,'obj_Red Bull':5,'obj_Cola':7},
        {'respondent_id':'R6','segment':'Energy','dem_age':31,'att_energy':9,'att_novelty':7,'obj_Monster':8,'obj_Red Bull':9,'obj_Cola':4},
        {'respondent_id':'R7','segment':'Other','dem_age':61,'att_energy':1,'att_novelty':2,'obj_Monster':1,'obj_Red Bull':2,'obj_Cola':8},
        {'respondent_id':'R8','segment':'Energy','dem_age':26,'att_energy':8,'att_novelty':8,'obj_Monster':9,'obj_Red Bull':8,'obj_Cola':3},
    ])


def test_grounded_respondent_uses_measured_answer_and_refuses_fake_reason():
    d=_df().copy();d.insert(0,'__npc_dialogue_id',d['respondent_id'])
    out=rd.grounded_respondent(d.iloc[0],'Proč jsi hodnotil Monster tak vysoko?',sample_df=d)
    assert out['epistemic_status']=='MEASURED_ONLY'
    assert 'Monster = 10' in out['answer']
    assert 'Skutečný důvod' in out['answer']
    assert any(x.get('label')=='Monster' and x.get('value')==10 for x in out['evidence'])
    assert any(x.get('type')=='sample_association_not_causation' for x in out['evidence'])


def test_grounded_segment_aggregates_exact_rows_and_marks_association_not_causation():
    d=_df().copy();d.insert(0,'__npc_dialogue_id',d['respondent_id'])
    seg=d[d['segment']=='Energy'].copy()
    out=rd.grounded_segment(seg,'Proč má tento segment Monster tak vysoko?',all_df=d,label='Energy')
    assert out['epistemic_status']=='MEASURED_SEGMENT_ONLY'
    assert out['target']['n']==4
    assert 'Monster: průměr' in out['answer']
    assert 'nejsou důvod ani kauzalita' in out['answer']
    assert any(x.get('type')=='segment_statistic' and x.get('label')=='Monster' for x in out['evidence'])


def test_simulation_is_explicit_and_fail_closed_no_silent_fallback(monkeypatch):
    d=_df().copy();d.insert(0,'__npc_dialogue_id',d['respondent_id'])
    base=rd.grounded_respondent(d.iloc[0],'Proč Monster?',sample_df=d)
    captured={}
    def fake_call_structured(**kw):
        captured.update(kw)
        return {'data':{'answer':'Hypoteticky mi sedí energie a novost.','assumptions':['Motiv nebyl přímo měřen.'],'evidence_used':['Monster=10']},'provider':'openai','model':'test-model','fallback_used':False}
    import ai_router
    monkeypatch.setattr(ai_router,'call_structured',fake_call_structured)
    out=rd.simulate_extension('Proč Monster?',base,provider='openai',model='test-model')
    assert out['epistemic_status']=='SIMULATED_EXTENSION'
    assert 'SIMULACE NAD RÁMEC' in out['warning']
    assert out['fallback_used'] is False
    assert captured['allow_fallback'] is False
    assert 'raw' not in str(captured['messages']).lower()


def test_dialogue_loads_exact_ids_from_physical_csv(tmp_path):
    p=tmp_path/'RESPONDENTS.csv';_df().to_csv(p,index=False)
    out=rd.dialogue(candidate_paths=[(p,'TEST_DATA')],question='Jak jsi hodnotil Monster?',target_type='respondent',respondent_id='R2',mode='grounded')
    assert 'Monster = 9' in out['answer']
    assert out['source_file']=='RESPONDENTS.csv'
    seg=rd.dialogue(candidate_paths=[(p,'TEST_DATA')],question='Jak hodnotíte Monster?',target_type='segment',respondent_ids=['R1','R2','R6','R8'],segment_label='Energy',mode='grounded')
    assert seg['target']['n']==4


def test_ui_and_server_expose_respondent_segment_dialogue():
    root=Path(__file__).resolve().parents[1]
    ui=(root/'ui_app.html').read_text(encoding='utf-8')
    server=(root/'ui_server.py').read_text(encoding='utf-8')
    assert 'npc-respondent-dialogue-1866' in ui
    assert 'Jen z odpovědí' in ui and 'Simulovat nad rámec' in ui
    assert 'Doptat se této skupiny' in ui and 'Doptat se A' in ui
    assert '/api/visualization/dialogue' in server


def test_contract_guardrails():
    assert rd.CONTRACT_VERSION=='18.6.6-respondent-dialogue-v1'
    assert rd.MODES=={'grounded','simulated'}
    assert 'SIMULACE NAD RÁMEC' in rd._SIM_WARNING
