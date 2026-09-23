"""Project-centric durable pipelines for NPC Panel 17.9.0.

The workflow engine may enqueue work, but the project/stage/artifact graph is the
source of truth.  Stage definitions intentionally stay small and deterministic so
the current SQLite + filesystem architecture remains sufficient for the MVP.
"""
from __future__ import annotations
import hashlib, json
from typing import Any

PROJECT_STATUSES={
    'DRAFT','IN_PROGRESS','WAITING_USER','WAITING_CREDITS','WAITING_CAPACITY',
    'READY_TO_CONTINUE','COMPLETED','COMPLETED_WITH_WARNINGS','ARCHIVED'
}
STAGE_STATUSES={'NOT_STARTED','READY','RUNNING','WAITING_USER','WAITING_CREDITS','WAITING_CAPACITY','DONE','DONE_WITH_WARNINGS','INVALIDATED','FAILED'}

RESEARCH_STAGES=[
 ('BRIEF','Zadání'),('DEEP_RESEARCH','Deep Research'),('RESEARCH_DESIGN','Výzkumný design'),
 ('QUESTIONNAIRE','Dotazník'),('AUDIENCE','Cílová skupina'),('DIMENSIONS','Dimenze'),
 ('SAMPLE_PLAN','Výběrový plán'),('FIELDWORK','Respondenti'),('AGGREGATION','Agregace'),
 ('VALIDATION','Validace'),('ANALYSIS','Analýza'),('REPORT','Report'),('DELIVERY','Předání')]
SIMULATION_STAGES=[
 ('BRIEF','Kontext'),('DEEP_RESEARCH','Deep Research'),('BASELINE','Baseline'),
 ('SCENARIO_CONTRACT','Kontrakt scénáře'),('AUDIENCE','Cílová skupina'),('DIMENSIONS','Dimenze'),
 ('VARIANTS','Varianty'),('WORLDS','Simulované světy'),('FROZEN_RESULTS','Zmrazené výsledky'),
 ('COMPARISON','Srovnání'),('INTERPRETATION','Interpretace'),('REPORT','Report'),('DELIVERY','Předání')]

# The first changed stage invalidates itself and everything downstream.  A few
# presentation-only changes have deliberately narrower impact.
IMPACT_ROOTS={
 'brief':'BRIEF','briefing':'BRIEF','goal':'BRIEF','decision_use':'BRIEF','research_plan':'RESEARCH_DESIGN','questionnaire':'QUESTIONNAIRE',
 'sections':'QUESTIONNAIRE','tracked_objects':'QUESTIONNAIRE','audience':'AUDIENCE','persona_dimensions':'DIMENSIONS','n':'SAMPLE_PLAN',
 'sample':'SAMPLE_PLAN','panel_mode':'SAMPLE_PLAN','provider':None,'preferred_provider':None,'provider_policy':None,'model':None,
 'analysis_instructions':'ANALYSIS','analysis_style':'ANALYSIS','report_style':'REPORT','report_branding':'REPORT',
 'simulation_change':'SCENARIO_CONTRACT','scenario':'SCENARIO_CONTRACT','scenario_contract':'SCENARIO_CONTRACT','variants':'VARIANTS'
}

def stages_for(project_type:str)->list[tuple[str,str]]:
    return SIMULATION_STAGES if str(project_type).lower()=='simulation' else RESEARCH_STAGES


# A research-only stage id must never be written into a simulation project (or the
# reverse).  Before 17.9.9 a legacy action such as ``research_analysis`` started on a
# simulation project resolved to RESEARCH_DESIGN, which does not exist in
# SIMULATION_STAGES, and the job died inside project_store.set_stage with
# ``KeyError: 'RESEARCH_DESIGN'`` one second after being claimed.  The map below
# gives every stage its nearest counterpart in the other pipeline.
STAGE_EQUIVALENTS={
 'RESEARCH_DESIGN':'SCENARIO_CONTRACT','QUESTIONNAIRE':'SCENARIO_CONTRACT','SAMPLE_PLAN':'VARIANTS',
 'FIELDWORK':'WORLDS','AGGREGATION':'FROZEN_RESULTS','VALIDATION':'COMPARISON','ANALYSIS':'INTERPRETATION',
 'SCENARIO_CONTRACT':'RESEARCH_DESIGN','BASELINE':'RESEARCH_DESIGN','VARIANTS':'SAMPLE_PLAN',
 'WORLDS':'FIELDWORK','FROZEN_RESULTS':'AGGREGATION','COMPARISON':'VALIDATION','INTERPRETATION':'ANALYSIS',
}


def resolve_stage(project_type:str,stage_id:str|None,*,default:str|None=None)->str:
    """Return a stage id that provably exists in this project type's pipeline.

    Resolution order: the requested stage, its cross-pipeline equivalent, the caller's
    default, then the first stage.  It never raises, because a mis-mapped stage is a
    routing detail and must not destroy a queued job.
    """
    ids=[x[0] for x in stages_for(project_type)]
    sid=str(stage_id or '').strip().upper()
    if sid in ids: return sid
    alt=STAGE_EQUIVALENTS.get(sid)
    if alt in ids: return alt
    dfl=str(default or '').strip().upper()
    if dfl in ids: return dfl
    alt=STAGE_EQUIVALENTS.get(dfl)
    if alt in ids: return alt
    return ids[0]

def stage_ids(project_type:str)->list[str]: return [x[0] for x in stages_for(project_type)]

def fingerprint(value:Any)->str:
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()



def stage_input_payload(project:dict[str,Any], stage_id:str, project_type:str='research')->dict[str,Any]:
    """Return only inputs that materially affect a logical stage.

    Provider transport is intentionally excluded: mixed-provider continuation must
    preserve completed artifacts. Model choice is included only where it changes
    generated content. This payload is the durable fingerprint contract.
    """
    p=project or {}; sid=str(stage_id or '').upper(); sim=str(project_type).lower()=='simulation'
    if sim:
        simobj=p.get('simulation') or p
        mapping={
          'BRIEF':{'title':p.get('title'),'goal':p.get('goal'),'context':simobj.get('context') or simobj.get('brief')},
          'DEEP_RESEARCH':{'brief':simobj.get('context') or simobj.get('brief'),'attachments':p.get('attachment_refs'),'data_context':p.get('data_context')},
          'BASELINE':{'baseline':simobj.get('baseline'),'audience':simobj.get('audience'),'dimensions':simobj.get('dimensions'),'population':simobj.get('population_snapshot')},
          'SCENARIO_CONTRACT':{'scenario_contract':p.get('scenario_contract') or simobj.get('scenario_contract'),'change':simobj.get('change') or simobj.get('scenario')},
          'AUDIENCE':{'audience':simobj.get('audience') or p.get('audience')},
          'DIMENSIONS':{'dimensions':simobj.get('dimensions') or p.get('persona_dimensions')},
          'VARIANTS':{'variants':simobj.get('variants') or p.get('variants'),'scenario_contract':p.get('scenario_contract') or simobj.get('scenario_contract')},
          'WORLDS':{'variants':simobj.get('variants') or p.get('variants'),'worlds':simobj.get('worlds'),'n':simobj.get('n'),'model':simobj.get('model') or p.get('model'),'population':simobj.get('population_snapshot')},
          'FROZEN_RESULTS':{'variants':simobj.get('variants') or p.get('variants'),'worlds':simobj.get('worlds')},
          'COMPARISON':{'variants':simobj.get('variants') or p.get('variants'),'comparison_policy':simobj.get('comparison_policy')},
          'INTERPRETATION':{'analysis_instructions':p.get('analysis_instructions') or simobj.get('analysis_instructions'),'model':simobj.get('model') or p.get('model')},
          'REPORT':{'report_style':p.get('report_style') or simobj.get('report_style'),'report_branding':p.get('report_branding') or simobj.get('report_branding')},
          'DELIVERY':{'delivery':p.get('delivery') or simobj.get('delivery'),'report_style':p.get('report_style') or simobj.get('report_style')},
        }
        return {'stage':sid,'inputs':mapping.get(sid,simobj)}
    mapping={
      'BRIEF':{'title':p.get('title'),'goal':p.get('goal'),'decision_use':p.get('decision_use'),'briefing':p.get('briefing'),'study_type':p.get('study_type')},
      'DEEP_RESEARCH':{'goal':p.get('goal'),'decision_use':p.get('decision_use'),'briefing':p.get('briefing'),'research_questions':(p.get('research_plan') or {}).get('research_questions'),'attachment_refs':p.get('attachment_refs'),'data_context':p.get('data_context')},
      'RESEARCH_DESIGN':{'goal':p.get('goal'),'decision_use':p.get('decision_use'),'study_type':p.get('study_type'),'research_plan':p.get('research_plan'),'tracked_objects':p.get('tracked_objects')},
      'QUESTIONNAIRE':{'sections':p.get('sections'),'instrument_library':p.get('instrument_library'),'tracked_objects':p.get('tracked_objects'),'questionnaire_policy':p.get('questionnaire_policy')},
      'AUDIENCE':{'audience':p.get('audience')},
      'DIMENSIONS':{'persona_mode':p.get('persona_mode'),'persona_dimensions':p.get('persona_dimensions')},
      'SAMPLE_PLAN':{'n':p.get('n'),'panel_mode':p.get('panel_mode'),'audience':p.get('audience'),'persona_mode':p.get('persona_mode'),'persona_dimensions':p.get('persona_dimensions')},
      'FIELDWORK':{'sections':p.get('sections'),'audience':p.get('audience'),'persona_mode':p.get('persona_mode'),'persona_dimensions':p.get('persona_dimensions'),'n':p.get('n'),'model':p.get('model'),'population_snapshot':p.get('population_snapshot')},
      'AGGREGATION':{'aggregation_policy':p.get('aggregation_policy'),'weighting':p.get('weighting')},
      'VALIDATION':{'validation_policy':p.get('validation_policy'),'benchmarks':p.get('benchmarks')},
      'ANALYSIS':{'analysis_instructions':p.get('analysis_instructions'),'analysis_style':p.get('analysis_style'),'research_questions':(p.get('research_plan') or {}).get('research_questions'),'model':p.get('model')},
      'REPORT':{'report_style':p.get('report_style'),'report_branding':p.get('report_branding'),'language':p.get('report_language')},
      'DELIVERY':{'delivery':p.get('delivery'),'report_style':p.get('report_style'),'report_branding':p.get('report_branding')},
    }
    return {'stage':sid,'inputs':mapping.get(sid,p)}

def stage_fingerprint(project:dict[str,Any], stage_id:str, project_type:str='research')->str:
    return fingerprint(stage_input_payload(project,stage_id,project_type))

def impact_preview(project_type:str, changed_fields:list[str]|None=None, explicit_stage:str|None=None)->dict[str,Any]:
    ids=stage_ids(project_type)
    root=explicit_stage if explicit_stage in ids else None
    presentation_only=False
    if not root:
        roots=[]
        for f in changed_fields or []:
            r=IMPACT_ROOTS.get(str(f))
            if r: roots.append(r)
            if f in {'report_style','report_branding'}: presentation_only=True
        if roots: root=min(roots,key=lambda x:ids.index(x) if x in ids else 999)
    if not root:
        return {'root_stage':None,'invalidate':[],'preserve':ids,'presentation_only':False}
    pos=ids.index(root)
    inv=ids[pos:]
    return {'root_stage':root,'invalidate':inv,'preserve':ids[:pos],'presentation_only':presentation_only}

# Existing worker kinds -> durable project stages.  This lets 17.8.x jobs keep
# running while project persistence becomes authoritative.
JOB_STAGE_MAP={
 'project_compile':'BRIEF','background_research':'DEEP_RESEARCH','project_preflight':'RESEARCH_DESIGN',
 'respondent_run':'FIELDWORK','aggregate_results':'AGGREGATION','donor_qc':'VALIDATION',
 'interpret_results':'ANALYSIS','analysis_module':'ANALYSIS','analysis_assemble':'ANALYSIS','external_verification':'VALIDATION','reality_alignment':'VALIDATION',
 'final_report':'REPORT','project_stage_snapshot':'RESEARCH_DESIGN','project_delivery_finalize':'DELIVERY','legacy_task':'RESEARCH_DESIGN'
}
LEGACY_STAGE_MAP={
 'research_analysis':'RESEARCH_DESIGN','questionnaire_build':'QUESTIONNAIRE','questionnaire_repair':'QUESTIONNAIRE',
 'questionnaire_optimize':'QUESTIONNAIRE','audience_design':'AUDIENCE','persona_design':'DIMENSIONS',
 'scenario_compile':'SCENARIO_CONTRACT','simulation_context_enrich':'BRIEF','simulation_context_deep':'DEEP_RESEARCH','simulation_uncertainty_resolve':'DEEP_RESEARCH','fullsim':'WORLDS',
 'simulation_run':'WORLDS','final_review':'VALIDATION'
}
