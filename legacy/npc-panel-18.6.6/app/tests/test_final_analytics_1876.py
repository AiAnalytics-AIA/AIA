from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'ui_app.html').read_text(encoding='utf-8')


def test_portable_population_registry_and_live_panel():
    import population_context as pc
    p=pc.panel_path_for('LIVE')
    assert p.name=='FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz'
    assert p.is_file()
    current=pc.get_population('LIVE')['current_version']
    assert not Path(current['panel_path']).is_absolute()


def test_society_brief_and_grounded_price_query():
    from society_insights import generate_brief,ask_society
    b=generate_brief('LIVE',True)
    assert b['schema']=='npc.society_brief.v2'
    assert b['population']['rows']==18766
    assert len(b['strong_correlations'])>=10
    assert len(b['domain_summaries'])>=4
    assert all(x.get('causality')=='NOT_INFERRED' for x in b['strong_correlations'])
    q=ask_society('Co souvisí s citlivostí na cenu?','LIVE',False)
    assert q['epistemic_status']=='GROUNDED_AGGREGATE'
    assert 'Vyhledávání slev' in q['answer']
    assert 'nikoli o kauzální' in q['answer']


def test_society_segmentation_has_rich_grounded_description():
    from society_insights import run_segmentation,ask_segment
    r=run_segmentation(3,'LIVE')
    assert len(r['segments'])==3
    s=r['segments'][0]
    for key in ['description','why_identified','high_differences','low_differences','demographic_differences','weighted_share','epistemic_status','naming_status']:
        assert key in s
    a=ask_segment(s['segment_id'],'Čím se liší?',False)
    assert a['epistemic_status']=='GROUNDED_AGGREGATE'


def test_project_trash_roundtrip_preserves_revision_and_content(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'p.sqlite')
    try:
        x=ps.create_project(title='X',project={'title':'X','goal':'A'})
        pid=x['project_id']
        ps.save({'title':'X','goal':'B'},project_id=pid,force_new_revision=True)
        rev=ps.get(pid)['revision']
        ps.move_to_trash(pid)
        assert not any(r['project_id']==pid for r in ps.list(100,include_archived=True))
        assert any(r['project_id']==pid for r in ps.trash())
        y=ps.restore_from_trash(pid)
        assert y['revision']==rev
        assert y['project']['goal']=='B'
    finally: ps.close()


def test_sociomap_is_grouped_not_toolbar_spam():
    assert 'Výběr a skupiny | Porovnání | Analýza | Simulace | Zobrazení | Uložit/Export' in UI
    for token in ['Vysvětli tuto oblast','Difference Map','Confidence layer','Jen robustní','Relationship overlay','Co když objekt odeberu?','Polarizace','Opportunity','Diagnostika mapy','Přidat do reportu / klientského pohledu']:
        assert token in UI
    assert '← Zpět z čistého slidu' in UI


def test_two_map_modes_and_family_safe_object_manager_contract():
    assert 'Mapa respondentů' in UI and 'Objektová mapa' in UI
    assert 'family:' in UI
    assert 'výška = hustota / shluky lidí' in UI
    assert 'výška = metrika PRIMARY objektů' in UI
    assert 'PRIMARY' in UI and 'SECONDARY' in UI and 'HIDDEN' in UI
    assert 'Solo family' in UI or 'Solo' in UI
    assert 'Objekty / vrstvy' in UI


def test_kolo4_and_report_contracts_are_present():
    for token in ['📎 <span>Přidat soubory</span>','🔗 <span>Přidat odkaz</span>','Zpracovat komentáře','Pohled analytika','Pohled pro klienta','Přílohy','Koš']:
        assert token in UI
    assert 'Shrnutí' in UI and 'Zjištění' in UI and 'Doporučení' in UI and 'Zadání a kontext' in UI and 'Metodologie' in UI


def test_homepage_has_two_primary_start_paths():
    assert 'Začít výzkum' in UI
    assert 'Začít simulaci' in UI
