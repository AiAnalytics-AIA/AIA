from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def test_system_catalog_exposes_all_registered_provenance_truthfully():
    import library_system_catalog as c
    x=c.catalog(); s=x['summary']
    assert s['catalog_rows']==945
    assert s['source_groups']>=130
    assert s['microdata_groups']==43
    assert s['expected_payload_files']==775
    assert s['available_payload_files'] <= s['expected_payload_files']
    # Missing retained payloads must never be labeled LOCAL.
    for row in x['sources']:
        if row.get('expected_files') and not row.get('available_files'):
            assert row['status'] not in {'LOCAL','PARTIAL_LOCAL'}


def test_static_and_live_are_real_separate_snapshots_and_static_is_immutable():
    import population_context as p
    static=p.get_population('STATIC'); live=p.get_population('LIVE')
    assert static['immutable'] is True and live['immutable'] is False
    assert static['current_version']['panel_path'] != live['current_version']['panel_path']
    assert static['current_version']['sha256'] != live['current_version']['sha256']
    assert static['current_version']['rows']==18766
    assert live['current_version']['rows']==18766
    assert p.project_population_mode({})=='LIVE'
    assert p.project_population_mode({'population_mode':'STATIC'})=='STATIC'
    assert p.project_population_context({'population_mode':'STATIC'})['immutable'] is True


def test_batch_import_deduplicates_and_never_changes_live(tmp_path, monkeypatch):
    import data_library as d
    import library_batch_import as b
    import population_context as p
    db=tmp_path/'knowledge.sqlite'; files=tmp_path/'files'
    monkeypatch.setattr(d,'DB_PATH',db); monkeypatch.setattr(d,'FILES_DIR',files)
    before=p.get_population('LIVE')['current_version']['sha256']
    raw=b'block-f-source-content'
    r=b.batch_add_sources([
        {'raw':raw,'filename':'a.txt','source_type':'report'},
        {'raw':raw,'filename':'a-copy.txt','source_type':'report'},
    ],defaults={'author':'NPC test'})
    assert r['live_population_changed'] is False
    assert r['ok_count']==2
    assert r['results'][1]['entry'].get('deduplicated') is True
    assert p.get_population('LIVE')['current_version']['sha256']==before


def test_results_registry_marks_demo_and_project_results_non_learning(tmp_path, monkeypatch):
    import results_registry as r
    monkeypatch.setattr(r,'DB_PATH',tmp_path/'results.sqlite')
    x=r.register_result(project_id='D1',project_type='research',title='Demo',origin='DEMO',eligible_for_learning=False)
    assert x['eligible_for_learning'] is False
    sm=r.summary()
    assert sm['demo']==1 and sm['eligible_for_learning']==0


def test_runtime_paths_use_population_context_and_no_import_side_effect():
    u=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    p=(ROOT/'prototype_server.py').read_text(encoding='utf-8')
    d=(ROOT/'data_library.py').read_text(encoding='utf-8')
    assert 'population_context' in u and 'panel_path_for' in u
    assert 'project_population_mode' in p and 'population_context' in p
    assert 'allow_fallback=False' in d
    assert "provider:str='claude_code_subscription'" in d


def test_bootstrap_has_three_explicit_ai_providers():
    s=(ROOT/'ui_server.py').read_text(encoding='utf-8')
    assert '"id":"claude_code_subscription"' in s
    assert '"id":"anthropic"' in s
    assert '"id":"openai"' in s
    assert '"has_openai_key":has_openai_key()' in s


def test_library_ui_has_complete_hub_contract():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    for marker in ['NPC Panel 18.6 — Complete Final','Přehled','Všechny zdroje','Česká populace','Výsledky','Dávkový import zdrojů','STATIC + LIVE','Katalogová evidence není totéž jako lokální datový soubor','LIVE populaci automaticky nemění']:
        assert marker in s
    assert '/api/library/system-catalog' in s
    assert '/api/results-registry?sync=1' in s
    assert '/api/library/batch-upload' in s
    assert '/api/library/project-link' in s
    assert 'provider:p' in s and 'libProvider1850' in s


def test_library_project_link_is_metadata_not_project_revision(tmp_path, monkeypatch):
    import data_library as d
    monkeypatch.setattr(d,'DB_PATH',tmp_path/'knowledge.sqlite')
    row=d.link_source_to_project('P-1','SYS-1',source_kind='system_catalog',usage_role='context')
    assert row['project_id']=='P-1' and row['source_ref']=='SYS-1'
    assert d.project_sources('P-1')[0]['source_kind']=='system_catalog'


def test_population_quality_exposes_targets_and_oos_failures():
    import population_context as p
    q=p.population_quality()
    assert q['calibration']['dimensions']==75
    assert len(q['coverage_gaps'])>=5
    assert q['oos']['checks']==15
    assert q['oos']['fail']==2
    assert {x['check_id'] for x in q['oos']['failed_checks']}=={'OOS08','OOS10'}
