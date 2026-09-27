from pathlib import Path
import json, sqlite3
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def _demo_df(name='01_NAPOJE_360_DEMO'):
    return pd.read_csv(ROOT/'demo_library'/'visualization_showcase'/name/'RESPONDENTS.csv')


def test_discovery_keeps_declared_segments_and_exact_member_ids():
    from segment_intelligence import discover_segments
    df=_demo_df(); out=discover_segments(df,max_candidates=12)
    titles={x['title'] for x in out['candidates'] if x['kind']=='declared_segment'}
    assert {'Aktivní bez cukru','Tradiční sladká chuť','Energetičtí mladí','Cenově citliví','Minerálka a zdraví'} <= titles
    c=next(x for x in out['candidates'] if x['title']=='Aktivní bez cukru')
    truth=set(df.loc[df['segment']=='Aktivní bez cukru','respondent_id'].astype(str))
    assert set(c['respondent_ids'])==truth and c['count']==len(truth)


def test_discovery_finds_compound_behavioral_groups():
    from segment_intelligence import discover_segments
    out=discover_segments(_demo_df(),max_candidates=30)
    assert any(x['kind']=='intersection' and len((x['filter'] or {}).get('conditions') or [])==2 for x in out['candidates'])


def test_provider_input_contains_aggregates_not_respondent_ids():
    from segment_intelligence import discover_segments, public_ai_input
    out=discover_segments(_demo_df(),max_candidates=12); clean=public_ai_input(out)
    blob=json.dumps(clean,ensure_ascii=False)
    assert 'respondent_ids' not in blob
    assert '01R0001' not in blob
    assert 'top_differences' in blob


def test_ai_call_is_exact_provider_no_fallback(monkeypatch):
    import ai_router
    from segment_intelligence import discover_segments, interpret_with_ai
    seen={}
    def fake(**kw):
        seen.update(kw)
        ids=[x['id'] for x in json.loads(kw['messages'][0]['content'])['candidates'][:2]]
        return {'provider':'openai','model':'gpt-test','fallback_used':False,'data':{'summary':'Souhrn','insights':[{'candidate_id':i,'title':'T','why_interesting':'W','characterization':'C','business_meaning':'B','map_cta':'Zobrazit','confidence_note':'J','caution':'Pozor'} for i in ids]}}
    monkeypatch.setattr(ai_router,'call_structured',fake)
    out=discover_segments(_demo_df(),max_candidates=6)
    ai=interpret_with_ai(out,provider='openai',model='gpt-test')
    assert seen['prefer']=='openai' and seen['allow_fallback'] is False
    assert '01R0001' not in seen['messages'][0]['content']
    assert ai['provider']=='openai' and ai['fallback_used'] is False


def test_demo_intelligence_is_precomputed_and_clickable():
    from ui_server import visualization_intelligence
    for pid in ['PRJ-DEMO-VIS-NAPOJE-360','PRJ-DEMO-VIS-AEROLINKY-360','PRJ-DEMO-VIS-SOCIAL-360','PRJ-DEMO-VIS-HRY-360','PRJ-DEMO-VIS-MODA-360']:
        r=visualization_intelligence({'project_id':pid})
        assert r['available'] and r['ai_state']=='DEMO_PRECOMPUTED'
        rows=[x for x in r['intelligence']['candidates'] if x.get('ai_interpretation')]
        assert len(rows)==5
        assert all(x['respondent_ids'] for x in rows)
        assert all('Zobrazit skupinu' in x['ai_interpretation']['map_cta'] for x in rows)


def test_cache_does_not_create_project_revision(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'p.sqlite')
    try:
        x=ps.create_project(title='Test',project_type='research'); pid=x['project_id']; rev=ps.get(pid)['revision']
        ps.save_segment_intelligence(pid,'abc',{'status':'AI_READY','summary':'x'},provider='anthropic',model='test')
        assert ps.get(pid)['revision']==rev
        c=ps.segment_intelligence(pid)
        assert c['dataset_fingerprint']=='abc' and c['payload']['summary']=='x'
    finally: ps.close()


def test_ui_contract_has_ai_cards_exact_ids_and_no_hidden_paid_call():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    assert 'AI Segment Intelligence' in s
    assert 'vActivateInsight1840' in s
    assert 'activeIds1840' in s
    assert "use_ai:false" in s
    assert 'AI vysvětlit zajímavé skupiny' in s
    assert "use_ai:true" in s  # only explicit button action
    load=s[s.index('async function vLoadIntelligence1840'):s.index('async function vRunAiIntelligence1840')]
    assert 'use_ai:true' not in load


def test_all_demo_files_declare_build_time_ai_and_demo_truth():
    base=ROOT/'demo_library'/'visualization_showcase'
    files=sorted(base.glob('*_DEMO/SEGMENT_INTELLIGENCE_DEMO.json'))
    assert len(files)==5
    for p in files:
        x=json.loads(p.read_text(encoding='utf-8'))
        assert x['provenance']=='BUILD_TIME_AI_DEMO'
        assert 'ILUSTRAČNÍ DEMO' in x['demo_truth']
        assert len(x['insights'])==5
