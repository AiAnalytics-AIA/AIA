from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui_app.html').read_text(encoding='utf-8')

def test_object_manager_has_explicit_apply_and_matrix_contract():
    for token in ['Aplikovat změny','Po aplikaci:','npcApplyObjectChanges28','draftRoles','Správa vztahů / matice']:
        assert token in UI
    assert "o.matrix=subsetMatrix27(u.matrix,vis)" in UI
    assert "vis=m.roles.map((r,i)=>r!=='HIDDEN'?i:-1)" in UI

def test_settings_contains_map_mode_matrix_and_relationship_management():
    for token in ['<h4>Mapa</h4>','Mapa respondentů','Objektová mapa','Aktivní matice:','Správa vztahů','Zobrazit matici']:
        assert token in UI

def test_object_click_detail_is_family_aware_relationship_field():
    assert 'npc-object-relationship-field-1882' in UI
    assert 'family-aware relationship field' in UI
    for token in ['Unikátní silný vztah','Sdílený silný vztah','Střední / nevyhraněný vztah','Slabý / žádný vztah','Překryv s dalšími objekty stejné family','Stejné vnímání']:
        assert token in UI
    assert 'commercial_copy_only_when_relevant:true' in UI
    assert "same_family_only:true" in UI
    assert "st.selectedPerson=null" in UI

def test_scenarios_and_relationship_matrix_are_first_class_tools():
    for token in ['Scénáře / Co když…','Co se stane, když…','Upravit vztahy v matici','relationshipManagerHtml28','Scénář / upravit vztahy']:
        assert token in UI
    assert 'Raw source data se nemění' in UI

def test_ai_discovery_and_quick_filters_are_visibly_distinct_and_deduped():
    assert 'AI / discovery ·' in UI
    assert 'Rychlý filtr ·' in UI
    assert 'inter/union>.82' in UI
