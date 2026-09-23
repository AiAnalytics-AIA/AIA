from pathlib import Path
import demo_showcase
import ui_server

ROOT=Path(__file__).resolve().parents[1]

def test_ui_has_one_final_sociomap_entry_contract():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert "window.openSociomap1863=async function" in s
    assert "if(v==='sociomap'||v==='visualization')" in s
    assert "sociomapExplorer1795=retired" in s
    assert "sociomapTerrain1796=retired" in s
    assert "sociomapBubble1797=retired" in s
    assert "sociomapFlat1798=retired" in s
    assert "b.onclick=()=>openSociomap1863('demo')" in s
    assert "onclick=\"openSociomap1863('project')\"" in s


def test_all_demo_relational_maps_use_new_object_map_artifact():
    covered=0
    for meta in demo_showcase.project_catalog():
        d=demo_showcase.load(meta['project_id'])
        if not (d.get('sociomap') or {}).get('nodes'):
            continue
        covered += 1
        maps=[f for f in d.get('files') or [] if f.get('name')=='OBJECT_MAP_3D.html']
        assert maps, meta['project_id']
        p=Path(maps[0]['path'])
        text=p.read_text(encoding='utf-8')
        assert 'Klasické skóre' in text
        assert 'Normativní skóre' in text
        assert 'Rozbalit vztahovou matici' in text
        assert '800' in text
    assert covered == 18


def test_visualization_showcase_respondents_are_real_rows():
    pids=['PRJ-DEMO-VIS-NAPOJE-360','PRJ-DEMO-VIS-AEROLINKY-360','PRJ-DEMO-VIS-SOCIAL-360','PRJ-DEMO-VIS-HRY-360','PRJ-DEMO-VIS-MODA-360']
    for pid in pids:
        r=ui_server.visualization_respondents({'project_id':pid})
        assert r['available'] is True
        assert r['payload']['respondent_count']==600
        assert r['payload']['object_count']==8
        assert r['payload']['truth_contract'].startswith('Každý bod odpovídá jednomu skutečnému řádku')


def test_old_showcase_does_not_fake_respondents_but_has_new_object_map():
    pid='PRJ-DEMO-NOVA-SPARK'
    r=ui_server.visualization_respondents({'project_id':pid})
    assert r['available'] is False
    d=demo_showcase.load(pid)
    assert any(f.get('name')=='OBJECT_MAP_3D.html' for f in d.get('files') or [])
