from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]

def sample_df(n=80):
    rng=np.random.default_rng(42)
    return pd.DataFrame({
        'respondent_id':[f'R{i:03d}' for i in range(n)],
        'dem_age':rng.integers(18,78,n),
        'dem_gender':np.where(rng.random(n)<.53,'žena','muž'),
        'dem_region':rng.choice(['Praha','Jihomoravský','Moravskoslezský'],n),
        'obj_British_Airways':rng.integers(1,11,n),
        'obj_Qatar_Airways':rng.integers(1,11,n),
        'obj_Ryanair':rng.integers(1,11,n),
        'beh_sport':rng.integers(1,11,n),
    })

def test_respondent_payload_is_row_truthful_and_has_filter_suggestions():
    from visualization_lab import respondent_map_payload
    df=sample_df()
    p=respondent_map_payload(df)
    assert p['schema']=='npc.visualization.respondents.v1'
    assert p['respondent_count']==len(df)
    assert len(p['points'])==len(df)
    assert {x['id'] for x in p['points']}==set(df['respondent_id'])
    assert p['object_count']>=3
    assert 'nevytváří syntetické respondenty' in p['truth_contract']
    assert any('Důchodci' in x['title'] or 'Ženy' in x['title'] for x in p['suggestions'])

def test_area_comparison_uses_selected_real_ids():
    from visualization_lab import respondent_map_payload,compare_area
    p=respondent_map_payload(sample_df())
    ids=[x['id'] for x in p['points']]
    c=compare_area(p['points'],ids[:20],ids[20:40])
    assert c['area_a']['n']==20 and c['area_b']['n']==20
    assert isinstance(c['differences'],list)

def test_saved_visualization_segment_does_not_create_revision(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'projects.sqlite')
    try:
        x=ps.create_project(project_type='research',title='Test',project={'title':'Test','goal':'G'})
        before=ps.get(x['project_id'])['revision']
        s=ps.save_visualization_segment(x['project_id'],'Senioři',filter_spec={'query':'důchodci'},respondent_ids=['R1','R2'])
        after=ps.get(x['project_id'])['revision']
        assert before==after
        assert ps.visualization_segments(x['project_id'])[0]['segment_id']==s['segment_id']
        assert ps.delete_visualization_segment(x['project_id'],s['segment_id'])['ok'] is True
    finally:ps.close()

def test_3d_object_export_has_normative_score_and_collapsed_matrix(tmp_path):
    from sociomap import fit_relational_landscape,export_relational_html
    M=np.array([[0,8,3],[7,0,9],[4,6,0]],float)
    r=fit_relational_landscape(M,['British Airways','Qatar Airways','Ryanair'],[7,9,6],max_iter=30)
    text=export_relational_html(tmp_path/'map.html',r).read_text(encoding='utf-8')
    for token in ['Vizualizace vztahů','Klasické skóre','Normativní skóre','Rozbalit vztahovou matici','s výškou / bez výšky','14+46','800']:
        assert token in text
    assert 'unpkg.com' not in text and 'three.min.js' not in text.lower()

def test_ui_visualization_lab_contract():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    for token in ['NPC Panel 18.2 — Block C: Visualization Lab','renderVisualizationLab1820','Zvýraznit v kontextu','Jen shoda','Blikání zapnuto','Označit oblast A/B','Uložit aktuální skupinu','Mapa respondentů','3D krajina vztahů']:
        assert token in s
    assert "if(v==='visualization')" in s
    assert 'Otevřít Visualization Lab' in s

def test_server_exposes_visualization_endpoints():
    s=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    assert '/api/visualization/respondents' in s
    assert '/api/visualization/segment' in s
    assert '/api/visualization/compare' in s
    assert '/api/visualization/segments/' in s


def test_server_reads_real_project_artifact_without_synthesizing(tmp_path, monkeypatch):
    import ui_server
    from project_store import ProjectStore
    root=tmp_path
    (root/'data').mkdir()
    df=sample_df(40); data_path=root/'respondent_dataset.csv'; df.to_csv(data_path,index=False)
    ps=ProjectStore(root/'data'/'project_store.sqlite')
    try:
        x=ps.create_project(project_type='research',title='Test',project={'title':'Test','goal':'G'})
        ps.register_artifact(project_id=x['project_id'],revision=x['revision'],stage_type='FIELDWORK',artifact_type='respondent_dataset',path=str(data_path),sha256='abc',size_bytes=data_path.stat().st_size)
    finally:ps.close()
    monkeypatch.setattr(ui_server,'ROOT',root)
    r=ui_server.visualization_respondents({'project_id':x['project_id']})
    assert r['available'] is True
    assert r['payload']['respondent_count']==40
    assert r['source']=='PROJECT_ARTIFACT'
