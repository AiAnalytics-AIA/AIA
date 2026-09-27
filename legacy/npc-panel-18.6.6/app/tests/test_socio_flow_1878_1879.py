from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui_app.html').read_text(encoding='utf-8')

def test_home_demo_is_generic_and_next_to_project_management():
    assert 'data-demohome1878' in UI
    assert '>Správa projektů</button><button class="btn secondary" data-demohome1878' in UI
    assert '>DEMO</button>' in UI
    assert 'Rovnou MMC' not in UI

def test_settings_contains_prepared_family_maps_and_object_manager():
    for token in ['Předpřipravené mapy / family','npcFamilyQuick1878','Detailní Object Manager','Barva = výška.']:
        assert token in UI

def test_large_map_has_analysis_below_it():
    for token in ['npcSocioBelow1878','SEGMENTACE A POROVNÁNÍ','Pokračujte pod mapou','AI · zajímavé skupiny','Rychlé segmenty','Výběr, doptání a porovnání']:
        assert token in UI

def test_gemo_demo_safe_opener_is_present():
    assert 'npcOpenDemoSociomap1878' in UI
    assert "return window.npcOpenDemoSociomap1878(cur?.project_id)" in UI
    assert 'GEMO-DEMO-REPUTATION' in (ROOT/'demo_library/canonical/CANONICAL_DEMO_REGISTRY.json').read_text(encoding='utf-8')

def test_clean_slide_return_is_above_canvas_and_clickable():
    assert '.socio66.clean27 .npcReturn27{display:block!important;position:fixed!important' in UI
    assert 'z-index:2147483646!important' in UI
    assert 'pointer-events:auto!important' in UI

def test_interaction_stability_wraps_map_settings_actions():
    for token in ["'socioMetric66','socioNorm66'","'npcFamily27','npcRole27'",'no_observer_render_loop:true']:
        assert token in UI
