from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def test_unified_workspace_contract_present():
    html=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'one interactive Sociomapa Workspace, two modes over one canvas' in html
    assert 'Respondenti${hasR?' in html
    assert 'Objekty${hasO?' in html
    assert "window.openSociomap1863=function(source){return renderSociomapWorkspace1865" in html
    assert 'Přesouvat prvky' in html
    assert 'Přeměřit vztah A/B' in html
    assert 'Označit A/B' in html
    assert 'Ruční posun mění jen vizuální layout' in html
    assert "maso:['maso','meat']" in html
    assert "q.match(/^(.+?)\\s+(-?\\d+" in html


def test_visualization_routes_for_workspace():
    txt=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    assert 'def visualization_object_map' in txt
    assert 'def visualization_layout_action' in txt
    assert '"/api/visualization/object-map"' in txt
    assert '"/api/visualization/layout"' in txt


def test_new_and_old_demo_data_contracts():
    import sys
    sys.path.insert(0,str(ROOT))
    import ui_server
    new='PRJ-DEMO-VIS-NAPOJE-360'
    old='PRJ-DEMO-NEXORA-EMPLOYEE'
    rr=ui_server.visualization_respondents({'project_id':new})
    oo=ui_server.visualization_object_map({'project_id':new})
    assert rr['available'] is True
    assert rr['payload']['respondent_count']==600
    assert len(rr['payload']['points'])==600
    assert oo['available'] is True
    assert len(oo['object_map']['names'])==8
    assert len(oo['object_map']['matrix'])==8
    rr_old=ui_server.visualization_respondents({'project_id':old})
    oo_old=ui_server.visualization_object_map({'project_id':old})
    assert rr_old['available'] is False
    assert oo_old['available'] is True
    assert len(oo_old['object_map']['names'])==8


def test_layout_persistence_is_visual_only():
    import sys
    sys.path.insert(0,str(ROOT))
    from project_store import ProjectStore
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/'p.sqlite'
        ps=ProjectStore(db)
        try:
            p=ps.create_project(project_type='research',title='Sociomap layout test',project={'title':'Sociomap layout test'})
            pid=p['project_id']
            before=ps.get(pid)
            rev_before=before['revision']
            saved=ps.save_visualization_layout(pid,'objects',positions={'0':{'x':12.5,'y':-7.25}},view={'yaw':1.1},metadata={'manual_visual_override':True})
            assert saved['positions']['0']=={'x':12.5,'y':-7.25}
            after=ps.get(pid)
            assert after['revision']==rev_before
            reset=ps.reset_visualization_layout(pid,'objects')
            assert reset['ok'] is True
            assert ps.visualization_layout(pid,'objects')['positions']=={}
        finally:
            ps.close()
