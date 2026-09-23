from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui_app.html').read_text(encoding='utf-8')

def test_respondent_and_object_maps_have_different_height_semantics():
    assert 'RESPONDENT_DENSITY_TERRAIN' in UI
    assert 'OBJECT_METRIC_TERRAIN' in UI
    assert "terrain_mode:isResp?'respondent_density':'object_metric'" in UI
    assert "if(st.mapType==='respondents')return[{id:'density'" in UI
    assert "preferred=type==='respondents'?'density'" in UI

def test_respondent_density_uses_people_not_object_hills():
    assert "for(const p of (st.respondents?.points||[]))" in UI
    assert "let q=personPos66(p);src.push({x:q.x,y:q.y,h:1,c:1})" in UI
    assert "let hr=isResp?(den||0)" in UI
    assert "Hustota / shluky respondentů" in UI

def test_object_map_still_uses_primary_object_metrics():
    assert "let o=st.objects||{},hv=objectMetricArray66(st.heightMetric)" in UI
    assert "if((o.types||[])[i]==='dot')continue" in UI
    assert "object_metric_terrain:!isResp" in UI

def test_settings_explain_correct_semantics():
    assert 'Respondenti = hustota lidí, Objekty = metrika objektů.' in UI
    assert 'family přepočítá polohy lidí a terén pak tvoří jejich hustota' in UI
    assert "výška = hustota / shluky lidí" in UI
    assert "výška = metrika PRIMARY objektů" in UI
