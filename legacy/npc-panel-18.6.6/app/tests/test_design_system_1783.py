from pathlib import Path
import json,re

UI=Path('ui_app.html')

def ui(): return UI.read_text(encoding='utf-8')

def test_release_identity_1783():
    assert Path('VERSION').read_text(encoding='utf-8').strip()=='18.6.6'
    assert json.loads(Path('BUILD_EDITION.json').read_text(encoding='utf-8'))['version']=='18.6.6'

def test_ai_analytics_design_tokens_and_shell():
    s=ui()
    for token in ['--rail:#F5F8FA','--ink:#15242E','--brand:#2180A5','--content:1080px','--rail-w:248px']:
        assert token in s
    assert 'class="brandWordmark"' in s and '<span>AI</span><span>ANALYTICS</span>' in s
    assert 'class="topbarInner"' in s and 'id="stepProgress1782"' in s

def test_home_is_single_analytics_product_hub():
    s=ui()
    assert 'class="productHub1783"' in s
    assert 'class="hubGrid1783"' in s
    assert '<span class="hubIndex1783">01</span>' in s
    assert '<span class="hubIndex1783">02</span>' in s
    assert '<span class="hubIndex1783">03</span>' in s
    assert 'AI ANALYTICS · RESEARCH OPERATING SYSTEM' in s

def test_route_aware_shell_and_new_project_button():
    s=ui()
    assert 'document.body.dataset.product=product' in s
    assert 'document.body.dataset.route=CURRENT' in s
    assert "nb.style.display=show?'inline-flex':'none'" in s
    assert "product==='simulation'?'+ Nová simulace':'+ Nový výzkum'" in s

def test_progress_uses_correct_step_set_for_simulation():
    s=ui()
    i=s.index('function updateTopbarProgress1782()')
    line=s[i:s.find('\n',i)]
    assert "PRODUCT_PATH==='simulation'?SIM_STEPS_1773" in line
    assert "PRODUCT_PATH==='research'?RESEARCH_STEPS" in line

def test_removed_copilot_dom_is_never_required():
    s=ui()
    assert "$('#promptchips').innerHTML=" not in s
    assert "let box=$('#promptchips');if(!box)return;" in s
    assert "if($('#promptchips'))renderPromptChips()" in s
    assert "if($('#chatInput'))$('#chatInput').addEventListener" in s
    assert "if(!$('#chatInput'))return;return _sendClaude1773()" in s
    assert 'BOOT_STAGE_1783' in s

def test_design_completion_covers_major_product_surfaces():
    s=ui()
    for selector in ['.dimensionGuide','.resultFile:hover','.scenarioShift','.libraryTabs','.knowledgeFlow','.productHub1783','.aiAction:before']:
        assert selector in s

def test_visual_release_is_not_a_methodology_change():
    d=Path('DESIGN_SYSTEM_17_8_3.md').read_text(encoding='utf-8')
    assert 'Research metodika' in d
    assert 'job/workflow engine' in d
    assert 'Full Simulation' in d
