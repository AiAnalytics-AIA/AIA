from pathlib import Path
import json


def ui():
    return Path('ui_app.html').read_text(encoding='utf-8')


def test_plan_renders_comparable_object_sets_visually():
    s=ui()
    block=s[s.index('// 17.7.1 STEP 2'):s.index('async function boot()',s.index('// 17.7.1 STEP 2'))]
    assert 'objectSetGrid' in s
    assert 'Porovnatelné sady' in block
    assert 'Porovnáváme mezi sebou' in block
    assert 'Značky' in block and 'Regiony' in block and 'Argumenty' in block
    assert '+ Přidat sadu' in block


def test_persona_is_dimension_menu_not_ablation_ui():
    s=ui(); a=s.index('renderPersona=function()',s.index('// 17.7.1 STEP 2')); b=s.index('function setLibraryTab',a)
    block=s[a:b]
    assert 'Sociodemografie a reprezentativní výběr' in block
    assert 'VOLITELNÁ HLOUBKA' in block
    assert 'AI doporučí' in block
    assert 'Chci doplnit novou dimenzi' in block
    assert 'Ablace none' not in block
    assert 'human benchmark' not in block.lower()
    assert 'AI provider' not in block


def test_data_library_is_user_friendly_source_library():
    s=ui(); a=s.index('function renderData()',s.index('// 17.7.1 STEP 2')); b=s.index('async function uploadLibrarySource',a)
    block=s[a:b]
    for word in ['Výzkum','Vědecký článek','Diplomová / disertační práce','Deep Research','Návrhy změn dimenzí']:
        assert word in block
    for forbidden in ['Track A','Track B','Track C','populační kotvy','validační pravda']:
        assert forbidden not in block


def test_library_backend_roundtrip_without_ai(tmp_path,monkeypatch):
    import data_library as dl
    monkeypatch.setattr(dl,'DB_PATH',tmp_path/'library.sqlite')
    monkeypatch.setattr(dl,'FILES_DIR',tmp_path/'files')
    monkeypatch.setattr(dl,'OVERLAY_PATH',tmp_path/'overlays.json')
    r=dl.add_source(raw='České domácnosti jsou citlivé na cenu a příjem.'.encode('utf-8'),filename='studie.txt',source_type='research',title='Studie cenové citlivosti',year='2026')
    assert r['source_type']=='research'
    assert r['analysis_status']=='NOT_ANALYZED'
    assert 'finance' in r['dimensions'] or 'cena' in r['dimensions']
    assert dl.summary()['sources']==1


def test_library_ai_analysis_creates_reviewable_proposal(tmp_path,monkeypatch):
    import data_library as dl
    monkeypatch.setattr(dl,'DB_PATH',tmp_path/'library.sqlite')
    monkeypatch.setattr(dl,'FILES_DIR',tmp_path/'files')
    monkeypatch.setattr(dl,'OVERLAY_PATH',tmp_path/'overlays.json')
    e=dl.add_source(raw=b'price sensitivity evidence',filename='paper.txt',source_type='scientific_article',title='Price study')
    monkeypatch.setattr(dl,'_proposal_from_ai',lambda entry,model='sonnet':{
        'summary':'Zdroj zpřesňuje cenovou citlivost.',
        'topics':['cena'],
        'dimension_impacts':[{'dimension_id':'price_anxiety','dimension_label':'Cenová úzkost','action':'new_dimension','rationale':'Může odlišovat reakce na zdražení.','evidence_summary':'Zdroj popisuje heterogenitu citlivosti.','confidence':0.72}]
    })
    out=dl.analyze_entry(e['entry_id'])
    p=out['proposals'][0]
    assert p['status']=='PROPOSED'
    decided=dl.decide_proposal(p['proposal_id'],'APPROVE')
    assert decided['active_dimensions']['price_anxiety']['label']=='Cenová úzkost'
    assert dl.summary()['approved_changes']==1


def test_bootstrap_exposes_library_summary():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    assert '"data_library":__import__("data_library").summary()' in s
    assert 'path=="/api/library"' in s
    assert 'path=="/api/library/upload"' in s
    assert 'path=="/api/library/deep-research"' in s


def test_library_deep_research_is_durable_claude_job():
    s=Path('legacy_job_dispatch.py').read_text(encoding='utf-8')
    assert 'elif kind=="library_deep_research"' in s
    assert 'from data_library import deep_research' in s
    runtime=Path('ai_runtime.py').read_text(encoding='utf-8')
    assert '"library_deep_research"' in runtime
