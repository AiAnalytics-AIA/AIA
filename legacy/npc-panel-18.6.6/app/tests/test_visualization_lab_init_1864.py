from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'ui_app.html').read_text(encoding='utf-8')


def test_vlab_state_is_initialized_before_legacy_code_can_run():
    first_script = UI.index('<script>')
    init = UI.index('var VLAB1820 = window.VLAB1820 ||', first_script)
    block_c = UI.index('// NPC Panel 18.2 — Block C: Visualization Lab')
    assert init < block_c
    assert 'let VLAB1820=' not in UI
    assert 'window.VLAB1820 = VLAB1820;' in UI


def test_sociomap_entry_uses_shared_visualization_lab():
    assert "window.openSociomap1863=async function(source)" in UI
    assert "await renderVisualizationLab1820()" in UI
    assert "if(v==='sociomap'||v==='visualization')" in UI


def test_visualization_lab_reinitialization_is_idempotent_not_lexical():
    assert "VLAB1820={...VLAB1820,payload:null" in UI
    assert "window.VLAB1820=VLAB1820" in UI
