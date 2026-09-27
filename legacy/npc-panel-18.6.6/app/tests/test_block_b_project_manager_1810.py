from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_project_store_adds_only_manager_metadata_and_preserves_revision_model(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'projects.sqlite')
    try:
        r=ps.create_project(project_type='research',title='Test',project={'title':'Test','goal':'Zjistit preference'});pid=r['project_id'];got=ps.get(pid)
        assert got['pinned'] is False and got['tags']==[]
        ps.set_pinned(pid,True);ps.set_tags(pid,['Priorita','Retail','Priorita'])
        row=next(x for x in ps.list(include_archived=True) if x['project_id']==pid)
        assert row['pinned'] is True and row['tags']==['Priorita','Retail'] and ps.get(pid)['revision']==got['revision']
    finally:ps.close()

def test_project_duplicate_is_new_project_with_source_parent(tmp_path):
    from project_store import ProjectStore
    ps=ProjectStore(tmp_path/'projects.sqlite')
    try:
        a=ps.create_project(project_type='simulation',title='Cena -10 %',project={'schema_version':'simulation-project-v1','title':'Cena -10 %','simulation':{'brief':'Cena -10 %'}})
        b=ps.duplicate(a['project_id'],'Cena -20 %');x=ps.get(b['project_id'])
        assert b['project_id']!=a['project_id'] and x['project_type']=='simulation' and x['parent_project_id']==a['project_id'] and x['project']['title']=='Cena -20 %'
    finally:ps.close()

def test_dashboard_read_model_handles_research_and_simulation_without_mutation():
    import ui_server
    base={'status':'READY_TO_CONTINUE','current_stage':'REPORT','last_completed_stage':'ANALYSIS','last_checkpoint':'cp-1','stages':[{'status':'DONE'},{'status':'READY'}],'artifacts':[1,2]}
    r=ui_server._project_dashboard_read_model({**base,'project_type':'research','project':{'goal':'Co lidé chtějí?','audience':{'description':'ČR 18+'},'research_plan':{'research_questions':['Která varianta vyhraje?']}},'analysis':{'executive_answer':'Varianta B','key_findings':[1,2]}})
    assert r['research_question']=='Která varianta vyhraje?' and r['executive_answer']=='Varianta B' and r['progress_done']==1 and r['artifact_count']==2
    s=ui_server._project_dashboard_read_model({**base,'project_type':'simulation','project':{'simulation':{'brief':'Cena -10 %','decision':'Co se změní?','baseline':'Cena 100'},'scenario_contract':{'variants':[{'name':'-10 %'},{'name':'-20 %'}]},'fullsim_run':{'worlds_executed':7,'worlds_planned':12,'winner':'-10 %','recommendation':'Testovat -10 %','risks':['ztráta marže'],'opportunities':['objem']}}})
    assert s['variant_count']==2 and s['worlds_executed']==7 and s['worlds_planned']==12 and s['winner']=='-10 %'

def test_project_routes_and_actions_exist():
    s=(ROOT/'ui_server.py').read_text(encoding='utf-8');assert '/api/projects/dashboard' in s
    for a in ("action=='pin'","action=='unpin'","action=='tags'","action=='duplicate'"):assert a in s

def test_project_manager_ui_has_required_filters_saved_views_and_quick_actions():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8')
    for token in ['NPC Panel 18.1 — Block B','Hledat napříč projekty','Čeká na mě','Čeká na AI','Vyžaduje zásah','Uložit tento pohled','AI cesta','Aktualizace','Naposledy upravené','★ Připnout','Duplikovat','Archivovat']:assert token in s

def test_home_is_portfolio_dashboard_and_simulation_has_decision_dashboard():
    s=(ROOT/'ui_app.html').read_text(encoding='utf-8');assert "title('Portfolio dashboard'" in s
    for token in ['Co je potřeba řešit','Právě běží','SIMULAČNÍ DASHBOARD','Rozhodovací přehled','Segmenty s odlišnou reakcí','Rizika a breakpointy','Příležitosti','Filtrovat segment, riziko, příležitost','Všechny varianty']:assert token in s
