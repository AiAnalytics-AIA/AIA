from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def test_demo_project_catalog_has_20_research_and_5_simulation_demos():
    import demo_showcase
    research=demo_showcase.catalog()
    pc=demo_showcase.project_catalog()
    sims=[x for x in pc if x.get('project_type')=='simulation']
    assert len(research)==28
    assert len(pc)==34 and len(sims)==6
    assert all(x.get('source_research_project_id') for x in sims)


def test_research_demo_links_to_separate_simulation():
    import demo_showcase
    d=demo_showcase.load('PRJ-DEMO-COMPLETE-01-NOVA-SPARK-DEMO')
    assert d['project_type']=='research'
    assert d['companion_simulation_project_id'].startswith('SIM-DEMO-')
    s=demo_showcase.load(d['companion_simulation_project_id'])
    assert s['project_type']=='simulation'
    assert s['source_research_project_id']==d['project_id']
    assert len(s.get('worlds') or [])==8


def test_project_history_is_human_readable_and_contains_simulations():
    import ui_server
    rows=ui_server.project_history()
    assert any(x.get('project_type')=='simulation' for x in rows)
    demos=[x for x in rows if x.get('is_demo')]
    assert demos
    for x in demos:
        assert x.get('research_question')
        assert x.get('study_result')
        assert x.get('population')


def test_final_navigation_has_compact_top_and_full_side_menu():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    a=s.index('function applyFinalNav1798()')
    b=s.index('setTimeout(applyFinalNav1798',a)
    block=s[a:b]
    top=block.split('let side=',1)[0]
    for label in ['Úvod','Simulace','Výzkum','Správa projektů']:
        assert label in top
    for label in ['AI asistent','Data Library','Nastavení','Diagnostika','Dema']:
        assert label not in top
    side=block.split('let side=',1)[1]
    for label in ['Úvod','Simulace','Výzkum','AI asistent','Data Library','Nastavení','Správa projektů','Diagnostika']:
        assert label in side


def test_home_title_layout_is_not_squeezed_by_menu():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'npc1798-final-layout' in s
    assert 'grid-template-columns:minmax(0,1fr) auto!important' in s
    assert 'overflow-wrap:normal!important' in s
    assert '.topbar .actions{width:auto!important' in s


def test_demo_sociomap_is_unified_interactive_workspace_with_full_matrix_contract():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    a=s.index('// 18.6.5 — one interactive Sociomapa Workspace')
    block=s[a:]
    assert 'renderSociomapWorkspace1865' in block
    assert 'Respondenti${hasR?' in block and 'Objekty${hasO?' in block
    assert 'Vztahová matice objektů' in block
    assert 'Přeměřit vztah A/B' in block
    assert 'Přesouvat prvky' in block
    assert 'cv.onwheel=wheel1865' in block
    assert "window.openSociomap1863=function(source){return renderSociomapWorkspace1865" in block


def test_relation_matrix_preserves_direction_and_zero_diagonal_in_engine():
    from sociomap import fit_relational_landscape
    R=np.array([[0,9,2,4],[4,0,8,3],[7,5,0,9],[4,3,2,0]],float)
    res=fit_relational_landscape(R,['A','B','C','D'],[1,4,7,10],max_iter=25)
    assert res.relation_matrix.shape==(4,4)
    assert res.relation_matrix[0,1]==9 and res.relation_matrix[1,0]==4
    assert np.allclose(np.diag(res.relation_matrix),0)
    assert res.metadata['relation_scale']=='1-10'


def test_production_sociomap_exposes_interactive_3d_normative_and_collapsed_matrix(tmp_path):
    from sociomap import fit_relational_landscape, export_relational_html
    R=np.array([[0,9,2],[4,0,8],[7,3,0]],float)
    res=fit_relational_landscape(R,['A','B','C'],[2,6,9],max_iter=20)
    text=export_relational_html(tmp_path/'map.html',res).read_text(encoding='utf-8')
    assert 'Vizualizace vztahů' in text
    assert 'Klasické skóre' in text and 'Normativní skóre' in text
    assert 'Rozbalit vztahovou matici' in text
    assert 's výškou / bez výšky' in text
    assert '14+46' in text and '800' in text
    assert 'cv.onwheel' in text


def test_research_worlds_are_not_presented_as_field_research_output():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'Toto není další část field research.' in s
    assert 'Otevřít navazující simulaci' in s
    assert 'Světy / scénáře simulace' in s
