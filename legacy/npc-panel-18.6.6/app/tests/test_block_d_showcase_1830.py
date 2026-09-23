import demo_showcase, ui_server

def test_five_visual_showcases_exist():
    rows=[x for x in demo_showcase.project_catalog() if x.get('collection')=='visualization_showcase']
    assert len(rows)==5
    assert {x['domain'] for x in rows} >= {'FMCG / nápoje','Cestování / aerolinky','Média / sociální sítě','Gaming','Móda / retail'}

def test_each_demo_has_full_real_rows_for_renderer():
    for x in [x for x in demo_showcase.project_catalog() if x.get('collection')=='visualization_showcase']:
        r=ui_server.visualization_respondents({'project_id':x['project_id']})
        assert r['available'] is True
        assert r['source']=='DEMO_DATASET'
        assert r['payload']['respondent_count']==600
        assert r['payload']['object_count']==8
        assert len(r['payload']['suggestions'])>=5

def test_each_demo_has_3d_map_and_truth_label():
    for x in [x for x in demo_showcase.project_catalog() if x.get('collection')=='visualization_showcase']:
        d=demo_showcase.load(x['project_id'])
        assert any(f['name']=='OBJECT_MAP_3D.html' for f in d['files'])
        assert 'ILUSTRAČNÍ DEMO' in (d['project'].get('demo_truth') or '')
