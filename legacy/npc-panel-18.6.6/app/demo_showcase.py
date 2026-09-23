"""Read-only DEMO project library for NPC Panel 17.9.4.

Two bundled collections are exposed through the ordinary Projects workspace:
- Complete Decision Demos (10): decision/scenario-oriented full output packages.
- Deep Showcase Demos (10): research/showcase packages with questionnaire,
  sociomap, analysis modules and eight explorable worlds.

Opening a DEMO never creates a job and never calls Claude/API/web.  Copying a
DEMO creates a normal editable project; the immutable seed stays unchanged.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json, re, datetime as dt

ROOT=Path(__file__).resolve().parent
DEMO_ROOT=ROOT/'demo_library'
COMPLETE=DEMO_ROOT/'complete'
SHOWCASE=DEMO_ROOT/'showcase'
SIMULATIONS=DEMO_ROOT/'simulations'
VISUAL=DEMO_ROOT/'visualization_showcase'
CANONICAL=DEMO_ROOT/'canonical'


def _read(path:Path, default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default

def _safe_id(x:str)->str:
    return re.sub(r'[^A-Z0-9]+','-',str(x or '').upper()).strip('-')


def _read_csv_preview(path:Path, limit:int=12):
    try:
        import csv
        with path.open('r',encoding='utf-8-sig',newline='') as f:
            r=csv.DictReader(f)
            out=[]
            for i,row in enumerate(r):
                out.append(dict(row))
                if i+1>=limit:break
            return out
    except Exception:
        return []

def _files(base:Path)->list[dict[str,Any]]:
    out=[]
    if not base.is_dir():return out
    wanted={'.docx','.xlsx','.csv','.json','.html','.svg','.png','.zip','.sqlite','.md','.txt'}
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in wanted:continue
        # Per-demo SHA manifests and integration notes remain downloadable too.
        rel=p.relative_to(ROOT).as_posix()
        kind={'.docx':'Word report','.xlsx':'Excel','.csv':'CSV','.json':'JSON','.html':'HTML','.svg':'SVG','.png':'PNG','.zip':'Project ZIP','.sqlite':'SQLite','.md':'Dokumentace','.txt':'Text'}.get(p.suffix.lower(),'Soubor')
        out.append({'name':p.name,'kind':kind,'path':str(p),'relative_path':rel,'size_bytes':p.stat().st_size})
    return out

def _complete_catalog()->list[dict[str,Any]]:
    manifest=_read(COMPLETE/'DEMO_LIBRARY_MANIFEST.json',[]) or []
    out=[]
    for i,x in enumerate(manifest,1):
        slug=str(x.get('slug') or f'{i:02d}_DEMO')
        base=COMPLETE/slug
        imp=next(base.glob('*_NPC_PROJECT_IMPORT.json'),None)
        obj=_read(imp,{}) if imp else {}
        rev=int(((obj or {}).get('project') or {}).get('current_revision') or 6)
        assignment=(obj or {}).get('assignment_summary') or {}; qs=assignment.get('questions') or []
        out.append({'project_id':'PRJ-DEMO-COMPLETE-'+_safe_id(slug),'demo_seed_key':slug,'title':x.get('title') or slug,'project_type':'research','study_type':x.get('type') or '',
                    'domain':x.get('industry') or '','sample':int(x.get('sample') or 0),'winner':x.get('winner'),'takeaway':x.get('takeaway') or '',
                    'research_question':str((qs[0] if qs else None) or assignment.get('primary_decision') or ''),
                    'goal':str(assignment.get('client_need') or ''),'population':'ČR 18+','client':str(assignment.get('client_need') or ''),'study_result':str(x.get('takeaway') or ''),
                    'status':'COMPLETED','current_stage':'DELIVERY','progress_pct':100,'revision':rev,'current_revision':rev,'modified_at':'2026-08-24T20:20:00',
                    'read_only':True,'is_demo':True,'demo':True,'collection':'complete','collection_label':'Complete Decision Demos','relative_path':f'demo_library/complete/{slug}'})
    return out

def _showcase_catalog()->list[dict[str,Any]]:
    reg=_read(SHOWCASE/'DEMO_REGISTRY.json',[]) or []
    out=[]
    for x in reg:
        base=SHOWCASE/str(x.get('relative_path') or '')
        seed=_read(base/'DEMO_PROJECT_SEED.json',{}) or {}
        rev=int(seed.get('current_revision') or 7)
        brief=seed.get('brief') or {}; aud=seed.get('audience') or {}; qs=seed.get('research_questions') or []; ds=seed.get('demo_summary') or {}
        out.append({'project_id':x.get('project_id'),'demo_seed_key':x.get('demo_seed_key'),'title':x.get('title'),'project_type':seed.get('project_type') or 'research',
                    'study_type':x.get('study_type') or seed.get('study_type') or '','domain':x.get('domain') or seed.get('domain') or '',
                    'sample':int((aud.get('n')) or 0),'takeaway':ds.get('main_answer') or seed.get('executive_answer') or '',
                    'research_question':str(ds.get('main_question') or (qs[0] if qs else None) or brief.get('decision') or seed.get('executive_answer') or ''),
                    'goal':str(brief.get('client_input') or ''),'population':str(aud.get('population') or aud.get('description') or 'ČR 18+'),
                    'client':str(ds.get('client') or brief.get('client_input') or ''),'study_result':str(ds.get('main_answer') or seed.get('executive_answer') or seed.get('recommendation') or ''),
                    'status':'COMPLETED','current_stage':'DELIVERY','progress_pct':100,'revision':rev,'current_revision':rev,'modified_at':'2026-08-24T20:16:00',
                    'read_only':True,'is_demo':True,'demo':True,'collection':'showcase','collection_label':'Deep Showcase Demos','relative_path':f'demo_library/showcase/{x.get("relative_path")}'})
    return out

SIMULATION_COMPANION_KEYS={
    '01_NOVA_SPARK_DEMO':'Produkt / launch scénáře',
    '02_VOLTIO_FLEX_DEMO':'Pricing scénáře',
    '04_MESTO_2035_DEMO':'Policy scénáře',
    '07_METROMARKET_LOCAL_DEMO':'Retail koncept scénáře',
    '09_STREAMIO_ONE_DEMO':'Subscription / pricing scénáře',
}


def _visualization_catalog()->list[dict[str,Any]]:
    reg=_read(VISUAL/'DEMO_VISUALIZATION_REGISTRY.json',[]) or []
    out=[]
    for x in reg:
        base=VISUAL/str(x.get('relative_path') or '')
        seed=_read(base/'DEMO_PROJECT_SEED.json',{}) or {}
        aud=seed.get('audience') or {}; qs=seed.get('research_questions') or []; brief=seed.get('brief') or {}; ds=seed.get('demo_summary') or {}
        out.append({'project_id':x.get('project_id'),'demo_seed_key':x.get('demo_seed_key'),'title':x.get('title'),'project_type':'research',
            'study_type':x.get('study_type') or seed.get('study_type') or 'Visualization showcase','domain':x.get('domain') or seed.get('domain') or '',
            'sample':int(aud.get('n') or x.get('sample') or 0),'takeaway':ds.get('main_answer') or x.get('takeaway') or seed.get('executive_answer') or '',
            'research_question':str(ds.get('main_question') or (qs[0] if qs else None) or brief.get('decision') or ''),'goal':str(brief.get('client_input') or ''),
            'population':str(aud.get('population') or 'Ilustrační populace 18+'),'client':str(ds.get('client') or 'DEMO Visualization Lab'),'study_result':str(ds.get('main_answer') or seed.get('executive_answer') or ''),
            'status':'COMPLETED','current_stage':'DELIVERY','progress_pct':100,'revision':1,'current_revision':1,'modified_at':'2026-08-26T00:50:00',
            'read_only':True,'is_demo':True,'demo':True,'collection':'visualization_showcase','collection_label':'Visualization Showcase 360','relative_path':f'demo_library/visualization_showcase/{x.get("relative_path")}'})
    return out

def _canonical_catalog()->list[dict[str,Any]]:
    """Canonical read-only product tests (MMC/GEMO/etc.) wired into the normal DEMO loader."""
    reg=_read(CANONICAL/'CANONICAL_DEMO_REGISTRY.json',{}) or {}
    out=[]
    for x in reg.get('research') or []:
        base=CANONICAL/str(x.get('relative_path') or '')
        seed=_read(base/'DEMO_PROJECT_SEED.json',{}) or {}
        aud=seed.get('audience') or {}; brief=seed.get('brief') or {}; qs=seed.get('research_questions') or []; ds=seed.get('demo_summary') or {}
        out.append({'project_id':x.get('project_id') or seed.get('project_id'),'demo_seed_key':x.get('demo_seed_key'),'title':x.get('title') or seed.get('title'),'project_type':'research',
            'study_type':x.get('study_type') or seed.get('study_type') or 'Canonical reference research','domain':x.get('domain') or seed.get('domain') or '',
            'sample':int(x.get('sample') or aud.get('n') or 0),'takeaway':ds.get('main_answer') or seed.get('executive_answer') or '',
            'research_question':str(ds.get('main_question') or (qs[0] if qs else None) or brief.get('decision') or ''),'goal':str(brief.get('client_input') or ''),
            'population':str(aud.get('population') or 'Syntetický reference sample'),'client':str(ds.get('client') or 'Canonical DEMO / reference case'),'study_result':str(ds.get('main_answer') or seed.get('executive_answer') or seed.get('recommendation') or ''),
            'status':'COMPLETED','current_stage':'DELIVERY','progress_pct':100,'revision':int(seed.get('current_revision') or 1),'current_revision':int(seed.get('current_revision') or 1),'modified_at':'2026-08-31T15:25:00',
            'read_only':True,'is_demo':True,'demo':True,'synthetic':True,'no_learning':True,'population_calibration_allowed':False,
            'collection':'canonical','collection_label':'Canonical DEMO / Golden Product Tests','relative_path':f'demo_library/canonical/{x.get("relative_path")}'} )
    return out

def _canonical_simulations()->list[dict[str,Any]]:
    reg=_read(CANONICAL/'CANONICAL_DEMO_REGISTRY.json',{}) or {}
    out=[]
    for x in reg.get('simulations') or []:
        base=CANONICAL/str(x.get('relative_path') or '')
        seed=_read(base/'DEMO_SIMULATION_SEED.json',{}) or {}; aud=seed.get('audience') or {}; brief=seed.get('brief') or {}
        out.append({'project_id':x.get('project_id') or seed.get('project_id'),'demo_seed_key':x.get('demo_seed_key'),'title':x.get('title') or seed.get('title'),'project_type':'simulation',
            'study_type':x.get('study_type') or 'Canonical scenario simulation','domain':x.get('domain') or '', 'sample':int(x.get('sample') or aud.get('n') or 0),
            'takeaway':seed.get('executive_answer') or '', 'research_question':str(brief.get('decision') or ''),'goal':str(brief.get('client_input') or ''),
            'population':str(aud.get('population') or 'Synthetic reference sample'),'client':'Canonical DEMO / reference case','study_result':str(seed.get('recommendation') or seed.get('executive_answer') or ''),
            'status':'COMPLETED','current_stage':'DELIVERY','progress_pct':100,'revision':1,'current_revision':1,'modified_at':'2026-08-31T15:25:00',
            'read_only':True,'is_demo':True,'demo':True,'synthetic':True,'no_learning':True,'population_calibration_allowed':False,
            'source_research_project_id':x.get('source_research_project_id') or seed.get('source_research_project_id'),'companion_simulation':True,
            'collection':'simulation','collection_label':'Canonical DEMO simulace','relative_path':f'demo_library/canonical/{x.get("relative_path")}'})
    return out

def catalog()->list[dict[str,Any]]:
    """Public research DEMO library including canonical MMC/GEMO golden cases."""
    return _complete_catalog()+_showcase_catalog()+_visualization_catalog()+_canonical_catalog()

def simulation_companions()->list[dict[str,Any]]:
    """Read-only scenario simulations linked to selected research demos.

    They are exposed in Project Management so Research and Simulation are clearly
    separated. They intentionally do not increase the public 20-demo library count.
    """
    out=[]
    for src in _complete_catalog():
        key=str(src.get('demo_seed_key') or '')
        if key not in SIMULATION_COMPANION_KEYS: continue
        sim_base=SIMULATIONS/key
        seed=_read(sim_base/'DEMO_SIMULATION_SEED.json',{}) or {}
        out.append({**src,
            'project_id':'SIM-DEMO-'+_safe_id(key),
            'title':seed.get('title') or (str(src.get('title') or '').replace(' — DEMO','')+' — DEMO simulace'),
            'project_type':'simulation','study_type':SIMULATION_COMPANION_KEYS[key],
            'takeaway':seed.get('executive_answer') or ('Navazující scénářový stress-test nad závěry zdrojového výzkumu. '+str(src.get('takeaway') or '')),
            'source_research_project_id':src.get('project_id'),'companion_simulation':True,
            'goal':str((seed.get('brief') or {}).get('decision') or 'Otestovat robustnost doporučení ze zdrojového výzkumu v různých scénářích.'),
            'study_result':seed.get('recommendation') or seed.get('executive_answer') or str(src.get('takeaway') or ''),
            'collection':'simulation','collection_label':'DEMO simulace','relative_path':f'demo_library/simulations/{key}',
            'sample':int(((seed.get('audience') or {}).get('n')) or src.get('sample') or 0)})
    return out+_canonical_simulations()

def project_catalog()->list[dict[str,Any]]:
    return catalog()+simulation_companions()

def find(project_id:str)->dict[str,Any]|None:
    pid=str(project_id or '')
    return next((x for x in project_catalog() if x.get('project_id')==pid),None)

def _complete_sociomap_matrix_1_10(sociomap:dict[str,Any]|None)->dict[str,Any]|None:
    """Make DEMO sociomap obey the same all-pairs display contract as production.

    DEMO seeds do not always carry respondent-level ratings for every mapped item.
    Explicit seed edges are therefore used first. Missing demo-only pairs are filled
    from the seed geometry so the showcase can render a complete matrix. Real LIVE
    projects use correlations from common respondent ratings or an explicit measured
    directional matrix in sociomap.py.
    """
    if not isinstance(sociomap,dict): return sociomap
    out=dict(sociomap); nodes=list(out.get('nodes') or []); edges=list(out.get('edges') or [])
    n=len(nodes)
    if not n:return out
    existing=out.get('relation_matrix_1_10')
    if isinstance(existing,list) and len(existing)==n and all(isinstance(row,list) and len(row)==n for row in existing):
        ok=True
        for i,row in enumerate(existing):
            for j,v in enumerate(row):
                try:fv=float(v)
                except Exception:ok=False;break
                if (i==j and abs(fv)>1e-9) or (i!=j and not (1.0<=fv<=10.0)):ok=False;break
            if not ok:break
        if ok:
            out.setdefault('matrix_contract',{'scale':'1-10','diagonal':0,'all_pairs':True,'asymmetry_allowed':True})
            return out
    import math
    M=[[0.0 for _ in range(n)] for __ in range(n)]; seen=set()
    for e in edges:
        try:i=int(e.get('from'));j=int(e.get('to'))
        except Exception:continue
        if not (0<=i<n and 0<=j<n) or i==j:continue
        v=float(e.get('relation_1_10',e.get('weight',e.get('value',0.5))))
        if v<=1.000001:v=1.0+9.0*max(0.0,min(1.0,v))
        v=max(1.0,min(10.0,v));M[i][j]=v;seen.add((i,j))
        if not bool(e.get('directed',False)):
            M[j][i]=v;seen.add((j,i))
    coords=[(float(x.get('x') or 0),float(x.get('y') or 0)) for x in nodes]
    dmax=max([math.hypot(coords[i][0]-coords[j][0],coords[i][1]-coords[j][1]) for i in range(n) for j in range(i+1,n)] or [1.0]) or 1.0
    for i in range(n):
        for j in range(n):
            if i==j:M[i][j]=0.0;continue
            if (i,j) in seen:continue
            d=math.hypot(coords[i][0]-coords[j][0],coords[i][1]-coords[j][1])
            M[i][j]=round(1.0+9.0*max(0.0,min(1.0,1.0-d/dmax)),2)
    out['relation_matrix_1_10']=M
    out['matrix_source']='DEMO_SEED_RELATIONS_WITH_GEOMETRY_FILL; LIVE uses respondent correlations or explicit directional relations'
    out['matrix_contract']={'scale':'1-10','diagonal':0,'all_pairs':True,'asymmetry_allowed':True}
    return out

def _primary_files(files:list[dict[str,Any]])->dict[str,dict[str,Any]]:
    def first(pred):return next((x for x in files if pred(x)),None)
    return {
      'report':first(lambda x:x['name'].lower().endswith('.docx') or ('report' in x['name'].lower() and x['name'].lower().endswith('.html'))),
      'workbook':first(lambda x:x['name'].lower().endswith('.xlsx') and 'preview' not in x['name'].lower()),
      'respondents':first(lambda x:x['name'].lower().endswith('.csv') and any(k in x['name'].lower() for k in ('respondent','evaluation'))),
      'database':first(lambda x:x['name'].lower().endswith('.sqlite')),
      'project_export':first(lambda x:x['name'].lower().endswith('.zip') and 'project_export' in x['name'].lower()),
      'dashboard':first(lambda x:x['name'].lower().endswith('.html') and ('dashboard' in x['name'].lower() or 'preview' in x['name'].lower())),
      'sociomap':first(lambda x:'sociomap' in x['name'].lower() and x['name'].lower().endswith('.png')),
    }

def load(project_id:str)->dict[str,Any]:
    meta=find(project_id)
    if not meta:raise KeyError(project_id)
    if meta['collection']=='simulation':
        base=ROOT/meta['relative_path']; seed=_read(base/'DEMO_SIMULATION_SEED.json',{}) or {}; history=[]
        project_data=seed; import_data={}; ds=seed.get('demo_summary') or {}; assignment={'client_need':((seed.get('brief') or {}).get('client_input') or ''),'primary_decision':(ds.get('main_question') or (seed.get('brief') or {}).get('decision') or ''),'questions':([ds.get('main_question')] if ds.get('main_question') else ['Jak robustní je doporučení napříč scénáři?','Ve kterých světech se doporučení mění?']),'deliverables':['scenario comparison','world results','recommendation']}
        worlds_data=seed.get('worlds') or _read(base/'SIMULATION_WORLDS.json',[]) or []; variants=[]; audience=seed.get('audience') or {}; questionnaire=[]; segments=[]
        executive={'answer':seed.get('executive_answer') or '', 'recommendation':seed.get('recommendation') or '', 'winner':seed.get('winner')}
        analysis={}; sociomap=None
    elif meta['collection']=='visualization_showcase':
        base=ROOT/meta['relative_path']; seed=_read(base/'DEMO_PROJECT_SEED.json',{}) or {}; history=[]
        project_data=seed; import_data={}; brief=seed.get('brief') or {}; assignment={'client_need':brief.get('client_input') or '', 'primary_decision':brief.get('decision') or '', 'questions':seed.get('research_questions') or [], 'deliverables':['Visualization Lab','respondent dataset','3D object map']}
        worlds_data=[]; variants=seed.get('objects') or []; audience=seed.get('audience') or {}; questionnaire=seed.get('questionnaire') or _read(base/'QUESTIONNAIRE.json',[]) or []; segments=seed.get('segments') or []
        ds=seed.get('demo_summary') or {}; executive={'answer':seed.get('executive_answer') or '', 'main_answer':ds.get('main_answer') or '', 'why':ds.get('why') or seed.get('executive_answer') or '', 'recommendation':seed.get('recommendation') or '', 'winner':None}; analysis=_read(base/'ANALYSIS.json',{}) or {}
        sociomap=_read(base/'OBJECTS_SOCIOMAP_DEMO.json',{}) or {}
    elif meta['collection']=='complete':
        base=ROOT/meta['relative_path']; pj=next(base.glob('*_PROJECT.json'),None); imp=next(base.glob('*_NPC_PROJECT_IMPORT.json'),None); hist=next(base.glob('*_HISTORY.json'),None); worlds=next(base.glob('*_WORLDS.json'),None)
        project_data=_read(pj,{}) if pj else {}; import_data=_read(imp,{}) if imp else {}; history=_read(hist,[]) if hist else (import_data.get('history') or [])
        worlds_data=_read(worlds,[]) if worlds else (project_data.get('worlds') or import_data.get('worlds') or [])
        assignment=project_data.get('assignment_summary') or import_data.get('assignment_summary') or {}
        variants=project_data.get('variant_results') or []
        executive={'answer':meta.get('takeaway') or assignment.get('primary_decision') or '', 'recommendation':meta.get('takeaway') or '', 'winner':meta.get('winner')}
        audience=(import_data.get('audience') or {'population':'ČR 18+','n':meta.get('sample')})
        questionnaire=import_data.get('questionnaire') or []
        segments=project_data.get('segment_results') or import_data.get('segments') or []
        analysis=import_data.get('analysis') or {}
        sociomap=None
        if not variants:
            vr=next(base.glob('*_VARIANT_RESULTS.csv'),None)
            variants=_read_csv_preview(vr,20) if vr else []
        if not segments:
            sr=next(base.glob('*_SEGMENT_RESULTS.csv'),None)
            segments=_read_csv_preview(sr,20) if sr else []
        sm=next(base.glob('*SOCIOMAP*.json'),None)
        if sm: sociomap=_read(sm,{})
    else:
        base=ROOT/meta['relative_path']; seed=_read(base/'DEMO_PROJECT_SEED.json',{}) or {}; history=_read(base/'PROJECT_HISTORY_DEMO.json',[]) or seed.get('history') or []
        project_data=seed; import_data={}; assignment={'client_need':((seed.get('brief') or {}).get('client_input') or ''),'primary_decision':((seed.get('brief') or {}).get('decision') or ''),'questions':[],'deliverables':[]}
        worlds_data=seed.get('worlds') or [] ; variants=seed.get('objects') or []; audience=seed.get('audience') or {}; questionnaire=seed.get('questionnaire') or []; segments=seed.get('segments') or []
        ds=seed.get('demo_summary') or {}; executive={'answer':seed.get('executive_answer') or '', 'main_answer':ds.get('main_answer') or '', 'why':ds.get('why') or seed.get('executive_answer') or '', 'recommendation':seed.get('recommendation') or '', 'primary_metric':seed.get('primary_metric'),'primary_value':seed.get('primary_value'),'world_range':seed.get('world_range'),'winner_stability':seed.get('winner_stability'),'overall':seed.get('overall')}
        analysis={}
        adir=base/'analysis'
        if adir.is_dir():
            for p in sorted(adir.glob('*.json')):analysis[p.stem]=_read(p,{})
        sociomap=_read(base/'OBJECTS_SOCIOMAP_DEMO.json',{}) or seed.get('sociomap')
    sociomap=_complete_sociomap_matrix_1_10(sociomap)
    files=_files(base); primary=_primary_files(files)
    companion_id=None
    if str(meta.get('project_type') or 'research')=='research' and str(meta.get('demo_seed_key') or '') in SIMULATION_COMPANION_KEYS:
        companion_id='SIM-DEMO-'+_safe_id(str(meta.get('demo_seed_key') or ''))
    demo_summary=(project_data.get('demo_summary') or {}) if isinstance(project_data,dict) else {}
    return {**meta,'is_demo':True,'read_only':True,'analysis':analysis,'assignment':assignment,'audience':audience,'questionnaire':questionnaire,'variants':variants,'segments':segments,'worlds':worlds_data,'history':history,'executive':executive,'demo_summary':demo_summary,'sociomap':sociomap,
            'companion_simulation_project_id':companion_id,
            'files':files,'primary_files':primary,'project':project_data,'artifact_count':len(files),'world_count':len(worlds_data),'analysis_module_count':len(analysis) if isinstance(analysis,dict) else 0,
            'notice':'DEMO — deterministický showcase. Otevření nic nedopočítává, nevolá AI/API a nemění learning/dynamickou populaci.'}

def editable_project(project_id:str)->dict[str,Any]:
    d=load(project_id)
    from research_project import empty_project
    p=empty_project(title=str(d.get('title') or 'DEMO').replace(' — DEMO','').replace(' DEMO','')+' — kopie')
    a=d.get('assignment') or {}; ex=d.get('executive') or {}; aud=d.get('audience') or {}
    p['goal']=str(a.get('client_need') or ((d.get('project') or {}).get('brief') or {}).get('client_input') or d.get('title') or '')
    p['decision_use']=str(a.get('primary_decision') or ((d.get('project') or {}).get('brief') or {}).get('decision') or '')
    p['n']=int(aud.get('n') or d.get('sample') or 300)
    p['audience']['description']=str(aud.get('population') or aud.get('description') or 'ČR 18+')
    p['research_plan']['research_questions']=[str(x) for x in (a.get('questions') or []) if str(x).strip()]
    p['notes']=(p.get('notes') or [])+[f"Vytvořeno jako editovatelná kopie z {d.get('title')} ({d.get('project_id')}). DEMO výsledky nejsou automaticky přeneseny jako důkaz."]
    p['demo_source']={'project_id':d.get('project_id'),'title':d.get('title'),'collection':d.get('collection'),'copied_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    # Preserve questionnaire text as editable inspiration, never as immutable result.
    qs=[]
    for i,q in enumerate(d.get('questionnaire') or []):
        if not isinstance(q,dict):continue
        text=str(q.get('text') or '').strip()
        if text:qs.append({'id':f'QDEMO{i+1}','text':text,'typ':'text','povolit_nevim':True,'metadata':{'demo_source_question_id':q.get('id')}})
    if qs:p['sections']=[{'id':'S-DEMO','type':'questions','title':'Otázky převzaté z DEMO k úpravě','purpose':'inspirace','questions':qs}]
    return p
