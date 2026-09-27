"""Register durable sub-artifacts produced by existing NPC engines.

The engines keep their proven 17.8.x checkpoint formats.  This module projects
those checkpoints into the 17.9.0 project artifact graph without moving or
mutating the source files.  ArtifactStore always writes an atomic verified copy.
"""
from __future__ import annotations
import json, html, io
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent

ANALYSIS_MODULES=(
    ('ANALYSIS_EXECUTIVE','executive'),
    ('ANALYSIS_RESEARCH_QUESTIONS','research_questions'),
    ('ANALYSIS_OBJECTS','objects'),
    ('ANALYSIS_AUDIENCE','audience'),
    ('ANALYSIS_SEGMENTS','segments'),
    ('ANALYSIS_HYPOTHESES','hypotheses'),
    ('ANALYSIS_IMPLICATIONS','implications'),
    ('ANALYSIS_LIMITATIONS','limitations'),
)

def _common(project_id,revision,stage_type,input_fingerprint,provider,model,job_id,workflow_id):
    return dict(project_id=project_id,revision=revision,stage_type=stage_type,input_fingerprint=input_fingerprint or '',provider=provider or '',model=model or '',metadata={'job_id':job_id,'workflow_id':workflow_id,'supplementary':True})

def sync_research(astore,*,project_id,revision,input_fingerprint,provider='',model='',job_id='',workflow_id='',out=None):
    out=out or {}; bundle=out.get('bundle') or {}
    base=_common(project_id,revision,'DEEP_RESEARCH',input_fingerprint,provider,model,job_id,workflow_id)
    created=[]
    def put(t,obj,name):
        a=astore.put_json(**base,artifact_type=t,obj=obj,filename=name); created.append(a); return a
    put('DEEP_RESEARCH_EVIDENCE',{'accepted':bundle.get('accepted') or [],'quality_status':bundle.get('quality_status') or out.get('quality_status')},'EVIDENCE.json')
    sources=[]
    for x in (bundle.get('accepted') or [])+(bundle.get('quarantined') or []):
        if not isinstance(x,dict): continue
        sources.append({k:x.get(k) for k in ('url','source_url','title','publisher','date','tier','status','confidence') if x.get(k) is not None})
    put('DEEP_RESEARCH_SOURCES',{'sources':sources},'SOURCES.json')
    uncertainties=[]
    for x in bundle.get('quarantined') or []:
        if isinstance(x,dict): uncertainties.append({'claim':x.get('claim') or x.get('title'),'reason':x.get('reason') or x.get('quarantine_reason'),'source':x.get('url') or x.get('source_url')})
    put('DEEP_RESEARCH_UNCERTAINTIES',{'uncertainties':uncertainties},'UNCERTAINTIES.json')
    summary=(bundle.get('summary') or bundle.get('synthesis') or out.get('research_status') or '')
    text='<!doctype html><meta charset="utf-8"><h1>Deep Research</h1><p>'+html.escape(str(summary))+'</p><p>Accepted evidence: '+str(len(bundle.get('accepted') or []))+'</p><p>Quarantined: '+str(len(bundle.get('quarantined') or []))+'</p>'
    a=astore.put_text(**base,artifact_type='DEEP_RESEARCH_SUMMARY_HTML',text=text,filename='RESEARCH_SUMMARY.html');created.append(a)
    return created

def sync_fieldwork(astore,*,project_id,revision,input_fingerprint,provider='',model='',job_id='',workflow_id='',run_dir=None,result=None,batch_size=96):
    d=Path(run_dir) if run_dir else None
    if not d or not d.is_dir(): return []
    base=_common(project_id,revision,'FIELDWORK',input_fingerprint,provider,model,job_id,workflow_id)
    created=[]; batch_manifest=[]
    # A partial question journal is split into bounded immutable respondent batches.
    # Each result carries its own provider/model when available, which preserves
    # mixed Claude Code -> Claude API provenance across quota continuation.
    for p in sorted(d.glob('raw_journal_*.jsonl')):
        qid=p.stem.replace('raw_journal_',''); rows=[]
        for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
            try:
                x=json.loads(line)
                if isinstance(x,dict) and 'local_j' in x: rows.append(x)
            except Exception: pass
        rows.sort(key=lambda x:int(x.get('local_j') or 0))
        for bi in range(0,len(rows),int(batch_size)):
            chunk=rows[bi:bi+int(batch_size)]; batch_no=bi//int(batch_size)+1
            providers=sorted({str((x.get('result') or {}).get('provider') or provider or '') for x in chunk if str((x.get('result') or {}).get('provider') or provider or '')})
            models=sorted({str((x.get('result') or {}).get('model') or model or '') for x in chunk if str((x.get('result') or {}).get('model') or model or '')})
            bp='mixed' if len(providers)>1 else (providers[0] if providers else provider)
            bm='mixed' if len(models)>1 else (models[0] if models else model)
            t=f'FIELDWORK_{qid}_BATCH_{batch_no:03d}'
            a=astore.put_json(**{**base,'provider':bp,'model':bm,'metadata':{**base['metadata'],'question_id':qid,'batch_id':batch_no,'respondent_count':len(chunk),'respondent_min':min((int(x['local_j']) for x in chunk),default=None),'respondent_max':max((int(x['local_j']) for x in chunk),default=None),'providers':providers,'models':models,'checkpoint_kind':'respondent_batch'}},artifact_type=t,obj={'question_id':qid,'batch_id':batch_no,'rows':chunk,'providers':providers,'models':models},filename=f'{qid}_batch_{batch_no:03d}.json')
            created.append(a);batch_manifest.append({'artifact_id':a['artifact_id'],'artifact_type':t,'sha256':a['sha256'],'question_id':qid,'batch_id':batch_no,'respondent_count':len(chunk),'provider':bp,'model':bm})
        # Preserve the native append-only journal as an audit checkpoint too.
        a=astore.put_file(**{**base,'metadata':{**base['metadata'],'question_id':qid,'checkpoint_kind':'respondent_journal'}},artifact_type=f'FIELDWORK_JOURNAL_{qid}',source=p,filename=p.name);created.append(a)
    for name,t in [('checkpoint.pkl','FIELDWORK_CHECKPOINT'),('progress.json','FIELDWORK_PROGRESS'),('manifest.json','FIELDWORK_NATIVE_MANIFEST'),('souhrn.json','FIELDWORK_SUMMARY')]:
        fp=d/name
        if fp.is_file(): created.append(astore.put_file(**{**base,'metadata':{**base['metadata'],'checkpoint_kind':t.lower()}},artifact_type=t,source=fp,filename=name))
    # Completed raw datasets are copied from the canonical run directory. They
    # are never synthesized from partial checkpoints.
    r=result or {}; run_id=((((r.get('main') or {}).get('summary') or {}).get('run_id')) if isinstance(r,dict) else None)
    run_root=(ROOT/'runs'/str(run_id)) if run_id else d
    if run_root and run_root.is_dir():
        candidates=[('detail_public.csv','RAW_RESPONSES_CSV'),('detail_internal.csv','RAW_RESPONSES_INTERNAL_CSV'),('vysledky.xlsx','RAW_RESPONSES_XLSX'),('report.html','FIELDWORK_REPORT_HTML')]
        for name,t in candidates:
            fp=run_root/name
            if fp.is_file(): created.append(astore.put_file(**{**base,'metadata':{**base['metadata'],'run_id':run_id,'dataset_kind':t.lower()}},artifact_type=t,source=fp,filename=name))
        # Parquet is optional only when the existing runtime lacks an engine;
        # never fake a parquet file. If available, derive it deterministically
        # from the already persisted public CSV.
        csvp=run_root/'detail_public.csv'
        if csvp.is_file():
            try:
                import pandas as pd
                pq=d/'detail_public.parquet'; pd.read_csv(csvp,low_memory=False).to_parquet(pq,index=False)
                created.append(astore.put_file(**{**base,'metadata':{**base['metadata'],'run_id':run_id,'derived_from':'RAW_RESPONSES_CSV'}},artifact_type='RAW_RESPONSES_PARQUET',source=pq,filename='detail_public.parquet'))
            except Exception: pass
    manifest={'workflow_id':workflow_id,'job_id':job_id,'run_dir':str(d),'run_id':run_id,'input_fingerprint':input_fingerprint,'batches':batch_manifest,'artifact_ids':[a['artifact_id'] for a in created],'mixed_provider':len({x.get('provider') for x in batch_manifest if x.get('provider')})>1}
    ma=astore.put_json(**base,artifact_type='FIELDWORK_MANIFEST',obj=manifest,filename='FIELDWORK_MANIFEST.json');created.append(ma)
    return created

def sync_aggregation(astore,*,project_id,revision,input_fingerprint,provider='',model='',job_id='',workflow_id='',out=None):
    out=out or {}; base=_common(project_id,revision,'AGGREGATION',input_fingerprint,provider,model,job_id,workflow_id);created=[]
    try:
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active; ws.title='Summary'; ws.append(['Metric','Value'])
        for k,v in sorted((out.get('summary') or {}).items()):
            if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False,default=str)
            ws.append([str(k),v])
        for idx,b in enumerate(out.get('batteries') or [],1):
            sh=wb.create_sheet((str(b.get('id') or f'Battery{idx}'))[:31]); sh.append(['Field','Value'])
            for k,v in sorted(b.items()):
                if isinstance(v,(dict,list)): v=json.dumps(v,ensure_ascii=False,default=str)
                sh.append([str(k),v])
        bio=io.BytesIO();wb.save(bio)
        created.append(astore.put_bytes(**base,artifact_type='RESULTS_TABLES_XLSX',data=bio.getvalue(),filename='RESULTS_TABLES.xlsx'))
    except Exception: pass
    return created

def _analysis_payloads(a:dict[str,Any])->dict[str,Any]:
    return {
      'ANALYSIS_EXECUTIVE':{'executive_answer':a.get('executive_answer'),'confidence_summary':a.get('confidence_summary')},
      'ANALYSIS_RESEARCH_QUESTIONS':{'research_question_answers':a.get('research_question_answers') or []},
      'ANALYSIS_OBJECTS':{'key_findings':a.get('key_findings') or [],'object_analysis':a.get('object_analysis') or a.get('objects') or []},
      'ANALYSIS_AUDIENCE':{'audience_analysis':a.get('audience_analysis') or {},'confidence_summary':a.get('confidence_summary')},
      'ANALYSIS_SEGMENTS':{'segment_story':a.get('segment_story'),'segments':a.get('segments') or []},
      'ANALYSIS_HYPOTHESES':{'hypotheses':a.get('hypotheses') or [],'surprises':a.get('surprises') or [],'next_questions':a.get('next_questions') or []},
      'ANALYSIS_IMPLICATIONS':{'implications':a.get('implications') or []},
      'ANALYSIS_LIMITATIONS':{'limitations':a.get('limitations') or [],'confidence_summary':a.get('confidence_summary'),'meta':a.get('_meta') or {}},
    }

def sync_analysis_modules(astore,*,project_id,revision,input_fingerprint,provider='',model='',job_id='',workflow_id='',analysis=None):
    a=analysis or {}; base=_common(project_id,revision,'ANALYSIS',input_fingerprint,provider,model,job_id,workflow_id);created=[]
    payloads=_analysis_payloads(a)
    for idx,(t,label) in enumerate(ANALYSIS_MODULES,1):
        created.append(astore.put_json(**{**base,'metadata':{**base['metadata'],'analysis_module':label,'module_index':idx,'module_total':len(ANALYSIS_MODULES)}},artifact_type=t,obj={'module':label,'module_index':idx,'module_total':len(ANALYSIS_MODULES),'content':payloads[t],'source':'validated_analysis_checkpoint'},filename=f'{idx:02d}_{label}.json'))
    return created

def _sync_run_dir(astore,base,run_dir:Path):
    created=[]
    key=[('spec.json','SIMULATION_SPEC','WORLDS'),('prepare_snapshot.json','SIMULATION_PREPARE','WORLDS'),('world_model.json','WORLD_MODEL','WORLDS'),('research_snapshot.json','SIMULATION_RESEARCH','DEEP_RESEARCH'),('prediction.json','FROZEN_PREDICTION','FROZEN_RESULTS'),('prediction_manifest.json','FROZEN_MANIFEST','FROZEN_RESULTS'),('FROZEN.lock','FROZEN_LOCK','FROZEN_RESULTS'),('PARTIAL.lock','PARTIAL_LOCK','FROZEN_RESULTS'),('resume_state.json','SIMULATION_RESUME_STATE','WORLDS'),('world_summary.json','WORLD_SUMMARY','WORLDS'),('FULL_SIMULATION_REPORT.html','SIMULATION_REPORT','REPORT')]
    for name,t,stage in key:
        p=run_dir/name
        if p.is_file(): created.append(astore.put_file(**{**base,'stage_type':stage},artifact_type=t,source=p,filename=name))
    for p in sorted((run_dir/'worlds').glob('world_*_result.json')) if (run_dir/'worlds').is_dir() else []:
        created.append(astore.put_file(**{**base,'metadata':{**base['metadata'],'world_file':p.name}},artifact_type='SIMULATION_WORLD_RESULT',source=p,filename=p.name))
    return created

def sync_simulation(astore,*,project_id,revision,input_fingerprint,provider='',model='',job_id='',workflow_id='',result=None):
    result=result or {}; base=_common(project_id,revision,'WORLDS',input_fingerprint,provider,model,job_id,workflow_id);created=[]
    dirs=[]
    rd=result.get('run_dir') if isinstance(result,dict) else None
    if rd: dirs.append(Path(rd))
    for v in result.get('variants') or [] if isinstance(result,dict) else []:
        if isinstance(v,dict) and v.get('run_dir'): dirs.append(Path(v['run_dir']))
    # Batch wrappers may expose run directories only in a sibling "runs" list.
    for v in result.get('runs') or [] if isinstance(result,dict) else []:
        if isinstance(v,dict) and v.get('run_dir'): dirs.append(Path(v['run_dir']))
    seen=set()
    for d in dirs:
        try:key=str(d.resolve())
        except Exception:key=str(d)
        if key in seen or not d.is_dir(): continue
        seen.add(key);created.extend(_sync_run_dir(astore,base,d))
    return created

def sync_for_job(astore,*,kind,out,project_id,revision,stage_id,input_fingerprint='',provider='',model='',job_id='',workflow_id=''):
    try:
        if kind=='background_research': return sync_research(astore,project_id=project_id,revision=revision,input_fingerprint=input_fingerprint,provider=provider,model=model,job_id=job_id,workflow_id=workflow_id,out=out)
        if kind=='respondent_run':
            r=((out or {}).get('result') or {}); rd=(((r.get('main') or {}).get('run_dir')) or (r.get('run_dir')))
            return sync_fieldwork(astore,project_id=project_id,revision=revision,input_fingerprint=input_fingerprint,provider=provider,model=model,job_id=job_id,workflow_id=workflow_id,run_dir=rd,result=r)
        if kind=='aggregate_results': return sync_aggregation(astore,project_id=project_id,revision=revision,input_fingerprint=input_fingerprint,provider=provider,model=model,job_id=job_id,workflow_id=workflow_id,out=out)
        if kind=='interpret_results': return sync_analysis_modules(astore,project_id=project_id,revision=revision,input_fingerprint=input_fingerprint,provider=provider,model=model,job_id=job_id,workflow_id=workflow_id,analysis=(out or {}).get('analysis') or {})
        if kind=='legacy_task' and str((out or {}).get('legacy_kind') or '').startswith('fullsim'):
            return sync_simulation(astore,project_id=project_id,revision=revision,input_fingerprint=input_fingerprint,provider=provider,model=model,job_id=job_id,workflow_id=workflow_id,result=(out or {}).get('result') or {})
    except Exception as exc:
        try: astore.project_store.event(project_id,'SUPPLEMENTARY_ARTIFACT_WARNING','Doplňkové rozdělení artefaktů selhalo; hlavní výstup zůstává platný.',{'kind':kind,'error':str(exc)[:1000]},revision=revision,stage_type=stage_id,level='WARN')
        except Exception: pass
    return []
