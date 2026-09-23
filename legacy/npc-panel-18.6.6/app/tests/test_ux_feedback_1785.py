from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def ui(): return (ROOT/'ui_app.html').read_text(encoding='utf-8')

def test_start_is_compact_and_has_three_clear_product_choices():
    s=ui(); block=s[s.index('renderHome=function(){',s.index('// 17.8.5 — Respondent resilience + UX clarity')):]
    for x in ('Zjistit, co si lidé myslí','Otestovat konkrétní změnu','Doplnit evidence a model'):
        assert x in block
    assert 'Vyberte jednu cestu' in block


def test_brief_has_clickable_problem_types_and_attachments():
    s=ui()
    for x in ('Testuji cenu','Nový produkt / koncept','Hledám cílovou skupinu','Testuji komunikaci','Značka / positioning','Jiné'):
        assert x in s
    assert 'briefAttachFiles1785' in s and '/api/project/attachment' in s
    assert 'briefUrl1785' in s and 'attachments_context' in s


def test_projects_navigation_and_loader_exist():
    s=ui()
    assert "onclick=\"go('projects')\"" in s
    assert 'async function renderProjects1785()' in s
    assert "jget('/api/projects')" in s
    assert "jpost('/api/projects/load'" in s


def test_audience_dimensions_sample_and_worlds_are_explained():
    s=ui()
    assert "['audience','4','Audience / Cílová skupina'" in s
    assert "['persona','5','Dimenze'" in s
    assert 'ČR 18+</b> = výsledky reprezentují celou dospělou populaci' in s
    assert 'function sampleRecommendation1785()' in s and 'Použít doporučené N=' in s
    assert 'Jeden svět je nezávislá realizace' in s
    assert 'jsou tři samostatné scénáře, ne tři světy' in s


def test_generated_design_and_scenario_can_be_reviewed_with_ai():
    s=ui()
    assert 'PŘIPOMÍNKY K AI NÁVRHU' in s
    assert 'applyPlanReview1785' in s
    assert 'applyScenarioReview1785' in s
    assert 'review_comments' in s


def test_workflow_reconnects_and_shows_respondent_batch_progress():
    s=ui()
    assert 'reconnectBackend=async function(maxMs=90000)' in s
    assert 'Backend se znovu připojuje' in s
    for x in ('respondent_batch_start','respondent_batch_heartbeat','respondent_progress','respondent_batch_split'):
        assert x in s


def test_logo_is_local_absolute_route_with_visual_fallback():
    s=ui(); server=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    assert 'src="/brand/mark.png"' in s
    assert 'brandFallback1785' in s
    assert 'if path.startswith("/brand/")' in server
    assert (ROOT/'brand'/'mark.png').is_file()
