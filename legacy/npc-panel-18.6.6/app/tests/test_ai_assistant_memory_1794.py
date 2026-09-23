from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch

from project_store import ProjectStore
from artifact_store import ArtifactStore
from project_memory import search, answer
from research_project import empty_project
from ai_runtime import action_profile


def project_with_question(title, goal, text):
    p=empty_project(title=title);p['goal']=goal;p['decision_use']='Rozhodnutí'
    p['sections']=[{'id':'S1','type':'questions','title':'Hlavní blok','questions':[{'id':'Q1','text':text,'typ':'skala','skala':[1,10],'popisky_skaly':['určitě ne','určitě ano'],'povolit_nevim':False}]}]
    return p


def test_history_search_finds_previous_question_with_provenance(tmp_path):
    db=tmp_path/'project.sqlite';ps=ProjectStore(db)
    old=ps.create_project(project_type='research',title='Test ceny 2025',project=project_with_question('Test ceny 2025','Ochota zaplatit za nový produkt','Jaká je maximální cena, kterou byste byli ochotni zaplatit?'))
    cur=ps.create_project(project_type='research',title='Nový cenový test',project=project_with_question('Nový cenový test','Cena nového produktu','Jak atraktivní je produkt?'))
    ps.close()
    r=search('Jakou otázku jsme dřív použili na ochotu zaplatit?',db_path=db,current_project_id=cur['project_id'],current_revision=cur['revision'],current_project=project_with_question('Nový cenový test','Cena nového produktu','Jak atraktivní je produkt?'))
    assert r['count']>=1
    q=next(h for h in r['hits'] if h['kind']=='question' and h['project_id']==old['project_id'])
    assert q['project_title']=='Test ceny 2025' and q['revision']==old['revision']
    assert 'maximální cena' in q['text'] and str(q['payload']['question']['id']).lower()=='q1'


def test_current_revision_is_excluded_but_older_revision_can_be_memory(tmp_path):
    db=tmp_path/'project.sqlite';ps=ProjectStore(db);p=project_with_question('A','Cena','Kolik byste zaplatili?')
    r1=ps.create_project(project_type='research',title='A',project=p);pid=r1['project_id']
    p2=json.loads(json.dumps(p));p2['sections'][0]['questions'][0]['text']='Kolik byste zaplatili měsíčně?'
    r2=ps.save(p2,project_id=pid,force_new_revision=True,reason='edit');ps.close()
    r=search('otázka kolik zaplatili',db_path=db,current_project_id=pid,current_revision=r2['revision'],current_project=p2)
    assert any(h['same_project_history'] and h['revision']==r1['revision'] for h in r['hits'])
    assert not any(h['revision']==r2['revision'] and h['project_id']==pid for h in r['hits'])


def test_raw_fieldwork_artifact_is_never_indexed(tmp_path):
    db=tmp_path/'project.sqlite';ps=ProjectStore(db);p=project_with_question('Privacy','Test','Běžná otázka?')
    r=ps.create_project(project_type='research',title='Privacy',project=p);ast=ArtifactStore(ps,tmp_path/'arts')
    ast.put_text(project_id=r['project_id'],revision=r['revision'],stage_type='FIELDWORK',artifact_type='RAW_RESPONSES_CSV',text='SUPERSECRETRESPONDENTTOKEN',input_fingerprint='raw')
    ast.put_text(project_id=r['project_id'],revision=r['revision'],stage_type='ANALYSIS',artifact_type='ANALYSIS_EXECUTIVE',text='Užitečný závěr MARKETMEMORYTOKEN',input_fingerprint='ana')
    ps.close()
    assert search('SUPERSECRETRESPONDENTTOKEN',db_path=db)['count']==0
    assert any('MARKETMEMORYTOKEN' in h['text'] for h in search('MARKETMEMORYTOKEN',db_path=db)['hits'])


def test_ai_answer_can_only_cite_retrieved_memory_ids(tmp_path):
    db=tmp_path/'project.sqlite';ps=ProjectStore(db);p=project_with_question('Old','Cena','Jaká cena je ještě přijatelná?')
    ps.create_project(project_type='research',title='Old',project=p);ps.close()
    def fake(**kwargs):
        # Obtain the real first memory id from the prompt context and also add a fake id.
        import re
        ctx=kwargs['messages'][-1]['content'];mid=re.search(r'id=(MEM-[a-f0-9]+)',ctx).group(1)
        return {'data':{'answer':'V projektu Old byla použita cenová otázka [1].','source_ids':[mid,'MEM-FAKE'],'follow_up_suggestions':['Upravit rámování pro novou cílovku']},'provider':'claude_code_subscription','model':'sonnet','fallback_used':False}
    with patch('ai_router.call_structured',side_effect=fake):
        out=answer('Najdi starou otázku na cenu',db_path=db,current_project={})
    assert out['_ai']['used'] is True and len(out['sources'])>=1
    assert all(x['memory_id']!='MEM-FAKE' for x in out['sources'])


def test_assistant_runtime_has_three_minute_ceiling_and_ui_is_global():
    a=action_profile('project_assistant')
    assert a['hard_seconds']==180
    s=Path('ui_app.html').read_text(encoding='utf-8')
    assert 'id="assistantDrawer1791"' in s
    assert 'AI asistent' in s and '/api/assistant/search' in s and '/api/assistant/chat' in s
    assert 'Použít otázku' in s and 'inspired_from_project' in s
    # It is a drawer, not the old mandatory third-column copilot DOM.
    assert '<aside class="copilot' not in s
