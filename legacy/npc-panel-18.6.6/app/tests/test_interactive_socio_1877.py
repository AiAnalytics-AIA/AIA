from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui_app.html').read_text(encoding='utf-8')


def test_home_has_immediate_demo_entry():
    for token in ['data-demohome1878','renderDemoLibrary1794','Správa projektů','>DEMO<']:
        assert token in UI
    assert 'Rovnou MMC' not in UI


def test_persistent_map_dock_has_modes_roles_and_tools():
    for token in ['npcMapDock1877','Respondenti','Objekty','Analytik','Klient','Nastavení mapy','Nástroje','Analýza','Čistý slide']:
        assert token in UI
    assert 'z-index:300' in UI
    assert 'pointer-events:auto' in UI


def test_canvas_selection_opens_visible_detail_modal():
    assert 'npcDetailClose1877' in UI
    assert "st.modalSide27='right'" in UI
    assert 'modalRight27 .socio66Side.right{display:flex!important;z-index:520!important}' in UI
    assert "cv.addEventListener('click'" in UI


def test_demo_sociomap_is_forced_to_shared_interactive_workspace():
    assert 'Otevřít interaktivní Sociomapu' in UI
    assert "b.onclick=()=>window.openSociomap1863('demo')" in UI
    assert "window.openSociomap1863=function(source){return window.renderSociomapWorkspace1866" in UI


def test_final_css_is_in_head_not_runtime_body():
    style=UI.index('npc-interactive-socio-1877-style')
    head=UI.index('</head>')
    assert style < head
