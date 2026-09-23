from __future__ import annotations
from pathlib import Path
import json, zipfile

from demo_showcase import catalog, load, editable_project
from project_memory import search


def test_demo_catalog_contains_twenty_five_research_demos_in_three_collections():
    rows=catalog()
    assert len(rows)==28
    assert sum(x['collection']=='complete' for x in rows)==10
    assert sum(x['collection']=='showcase' for x in rows)==10
    assert sum(x['collection']=='visualization_showcase' for x in rows)==5
    assert len({x['project_id'] for x in rows})==28
    assert all(x['is_demo'] and x['read_only'] and x['status']=='COMPLETED' for x in rows)


def test_every_demo_opens_without_runtime_and_has_downloadable_outputs():
    for x in catalog():
        d=load(x['project_id'])
        assert d['is_demo'] and d['read_only'] and d['artifact_count']>0
        assert d['files'] and all(Path(f['path']).is_file() for f in d['files'])
        assert d['notice'].startswith('DEMO')
        assert d['primary_files'].get('report')
        assert d['primary_files'].get('workbook')
        if x['collection']=='visualization_showcase':
            assert d['primary_files'].get('respondents')
            assert d['world_count']==0
        elif x['collection']=='canonical':
            assert d['primary_files'].get('respondents')
            assert d['world_count']==0
        else:
            assert d['world_count']>=1


def test_complete_decision_demos_have_self_contained_project_export_zip():
    for x in catalog():
        if x['collection']!='complete': continue
        d=load(x['project_id']); z=d['primary_files'].get('project_export')
        assert z and Path(z['path']).is_file()
        with zipfile.ZipFile(z['path']) as zz:
            assert zz.testzip() is None
            assert any(n.endswith('_NPC_PROJECT_IMPORT.json') for n in zz.namelist())
            assert any(n.endswith('_REPORT.docx') for n in zz.namelist())
            assert any(n.endswith('_RESULTS.xlsx') for n in zz.namelist())


def test_showcase_demos_have_worlds_analysis_and_project_exports():
    for x in catalog():
        if x['collection']!='showcase': continue
        d=load(x['project_id'])
        assert d['world_count']==8
        assert d['analysis_module_count']==8
        assert d['primary_files'].get('project_export')
        assert d['primary_files'].get('sociomap')


def test_copy_is_editable_inspiration_not_result_reuse():
    x=catalog()[0]; before=Path(x['relative_path']) if False else None
    p=editable_project(x['project_id'])
    assert p['title'].endswith('— kopie')
    assert p['demo_source']['project_id']==x['project_id']
    assert any('DEMO výsledky nejsou automaticky přeneseny jako důkaz' in str(n) for n in p.get('notes') or [])
    assert '_results' not in json.dumps(p,ensure_ascii=False).lower()


def test_demo_memory_is_safe_and_raw_respondent_files_are_not_indexed(tmp_path):
    # Search works even with no project database and can return bundled DEMO high-level memory.
    out=search('NOVA Spark',db_path=tmp_path/'missing.sqlite',limit=30)
    assert out['count']>0 and any(h.get('project_id','').startswith('PRJ-DEMO') for h in out['hits'])
    # Memory implementation must never read bundled respondent/db filenames into entries.
    src=Path('project_memory.py').read_text(encoding='utf-8')
    assert 'RESPONDENT_DATABASE' not in src and 'RESPONDENTS.csv' not in src and '_DATABASE.sqlite' not in src


def test_ui_exposes_global_assistant_demo_library_and_read_only_copy_flow():
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'id="assistantDrawer1791"' in s
    assert "go('demos')" in s and '/api/demos' in s
    assert 'Vytvořit kopii jako nový projekt' in s
    assert 'DEMO · READ ONLY' in s
    assert '/api/demos/copy' in s
    assert "if(r.is_demo)" in s


def test_server_routes_demo_files_through_normal_artifact_download_path():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    assert 'demo_library' in s
    assert 'if path=="/api/demos"' in s
    assert 'if path=="/api/demos/copy"' in s
    assert 'project_assistant' in s


def test_project_assistant_is_utility_job_not_fake_project_stage():
    s=Path('ui_server.py').read_text(encoding='utf-8')
    assert "utility_kind=kind in {'copilot','project_assistant','ai_diagnose'}" in s
    assert "stage_id='' if utility_kind" in s or "stage_id=(None if utility_kind" in s or "stage_id=(\"\" if utility_kind" in s
