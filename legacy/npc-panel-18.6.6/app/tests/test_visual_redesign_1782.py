from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def ui(): return (ROOT/'ui_app.html').read_text(encoding='utf-8')

def test_ai_analytics_design_tokens_are_applied():
    s=ui()
    for token in ('--rail:#F5F8FA','--line:#DEE7EB','--ink:#15242E','--mut:#54666F','--brand:#2180A5','--brand2:#EAF4F8','--r:4px'):
        assert token in s
    assert 'grid-template-columns:248px minmax(0,1fr)' in s
    assert 'max-width:1080px' in s

def test_brand_lockup_uses_handoff_mark():
    s=ui()
    assert 'src="/brand/mark.png"' in s
    assert '<span>AI</span><span>ANALYTICS</span>' in s
    assert (ROOT/'brand'/'mark.png').is_file()
    assert (ROOT/'brand'/'mark-light.png').is_file()

def test_topbar_has_context_eyebrow_and_progress():
    s=ui()
    assert 'id="stepEyebrow1782"' in s
    assert 'id="stepProgress1782"' in s
    assert 'function updateTopbarProgress1782()' in s
    assert "'KROK '+(idx+1)+' / '+xs.length" in s
    assert "PRODUCT_PATH==='simulation'?SIM_STEPS_1773" in s

def test_removed_ai_partner_is_not_restored():
    s=ui()
    assert '<aside class="copilot' not in s
    assert 'AI, výzkumný partner' not in s

def test_redesign_is_visual_not_workflow_rewrite():
    s=ui()
    for endpoint in ('/api/research/analyze','/api/fullsim/pipeline','/api/fullsim/batch-pipeline','/api/library/'):
        assert endpoint in s
    assert 'briefFingerprint1780' in s
    assert "provider:'claude_code_subscription'" in s

def test_reference_radius_focus_and_topbar_language():
    s=ui()
    assert 'border-radius:3px' in s
    assert 'box-shadow:0 0 0 3px rgba(33,128,165,.10)' in s
    assert 'backdrop-filter:saturate(180%) blur(8px)' in s
