from __future__ import annotations
from typing import Any
from job_store import JobStore
from research_os_config import COST_MODES,DEFAULT_COST_MODE
from edition_config import build_version
from project_pipeline import stage_fingerprint
from provider_runtime import normalize_live_provider

# The persistent project pipeline is more granular than the old 10-node runtime.
# Snapshot nodes are cheap/local and establish durable approved inputs before the
# expensive stages. Existing runtime jobs are deliberately reused underneath.
STANDARD=[
 ('compile','project_compile','auto',[],'BRIEF','BRIEF_COMPILED'),
 ('research','background_research','auto',['compile'],'DEEP_RESEARCH','DEEP_RESEARCH'),
 ('design','project_stage_snapshot','auto',['research'],'RESEARCH_DESIGN','RESEARCH_DESIGN'),
 ('questionnaire','project_stage_snapshot','auto',['design'],'QUESTIONNAIRE','QUESTIONNAIRE_APPROVED'),
 ('audience','project_stage_snapshot','auto',['questionnaire'],'AUDIENCE','AUDIENCE_SNAPSHOT'),
 ('dimensions','project_stage_snapshot','auto',['audience'],'DIMENSIONS','DIMENSIONS_SNAPSHOT'),
 ('sample','project_stage_snapshot','auto',['dimensions'],'SAMPLE_PLAN','SAMPLE_PLAN'),
 ('preflight','project_preflight','review_if_warning',['sample','research'],'RESEARCH_DESIGN','PREFLIGHT'),
 ('run','respondent_run','auto',['preflight','research'],'FIELDWORK','FIELDWORK_RESULTS'),
 ('aggregate','aggregate_results','auto',['run'],'AGGREGATION','AGGREGATED_RESULTS'),
 ('donor_qc','donor_qc','review_if_warning',['aggregate'],'VALIDATION','DONOR_QC'),
 ('analysis_executive','analysis_module','auto',['donor_qc','research'],'ANALYSIS','ANALYSIS_EXECUTIVE'),
 ('analysis_research_questions','analysis_module','auto',['analysis_executive'],'ANALYSIS','ANALYSIS_RESEARCH_QUESTIONS'),
 ('analysis_objects','analysis_module','auto',['analysis_research_questions'],'ANALYSIS','ANALYSIS_OBJECTS'),
 ('analysis_audience','analysis_module','auto',['analysis_objects'],'ANALYSIS','ANALYSIS_AUDIENCE'),
 ('analysis_segments','analysis_module','auto',['analysis_audience'],'ANALYSIS','ANALYSIS_SEGMENTS'),
 ('analysis_hypotheses','analysis_module','auto',['analysis_segments'],'ANALYSIS','ANALYSIS_HYPOTHESES'),
 ('analysis_implications','analysis_module','auto',['analysis_hypotheses'],'ANALYSIS','ANALYSIS_IMPLICATIONS'),
 ('analysis_limitations','analysis_module','auto',['analysis_implications'],'ANALYSIS','ANALYSIS_LIMITATIONS'),
 ('interpret','analysis_assemble','auto',['analysis_limitations'],'ANALYSIS','ANALYSIS'),
 ('verify','external_verification','auto',['interpret'],'VALIDATION','EXTERNAL_VERIFICATION'),
 ('alignment','reality_alignment','auto',['interpret','verify','research','aggregate'],'VALIDATION','REALITY_ALIGNMENT'),
 ('report','final_report','auto',['interpret','verify','research','alignment'],'REPORT','CLIENT_REPORT'),
 ('delivery','project_delivery_finalize','auto',['report'],'DELIVERY','DELIVERY_MANIFEST'),
]

def create_standard(store:JobStore,*,project_id:str,project_revision:int,project:dict[str,Any],mode='dry',confirm_live=False,cost_mode=None,budget_usd=None,priority=50,verification=False,after_workflow=None,idempotency_key=None,workflow_metadata=None)->dict[str,Any]:
 cm=str(cost_mode or DEFAULT_COST_MODE).upper();cm=cm if cm in COST_MODES else DEFAULT_COST_MODE
 verification=bool(verification or (str(mode)!='dry' and bool(confirm_live)))
 if idempotency_key:
  with store.cx() as c:
   old=c.execute('SELECT workflow_id FROM jobs WHERE idempotency_key=?',(f'{idempotency_key}:compile',)).fetchone()
  if old:
   existing=store.get_workflow(old['workflow_id'])
   return {'workflow_id':old['workflow_id'],'status':existing['status'],'jobs':{j['node_key']:j['job_id'] for j in existing['jobs']},'deduplicated':True}
 if budget_usd is None:budget_usd=float(COST_MODES[cm]['default_budget_usd'])
 meta={'mode':mode,'confirm_live':bool(confirm_live),'verification_requested':bool(verification),'research_os':build_version(),'project_source_of_truth':True,**(workflow_metadata or {})}
 wid=store.create_workflow(project_id=project_id,project_revision=project_revision,workflow_type='persistent_research_project',priority=priority,budget_usd=budget_usd,cost_mode=cm,metadata=meta,workflow_id=None)
 ids={}; phase_overrides=dict(((project.get('run_policy') or {}).get('phase_overrides') or {}))
 default_provider=normalize_live_provider(((project.get('run_policy') or {}).get('provider')) or 'claude_code_subscription')
 for key,kind,imode,deps,stage_id,artifact_target in STANDARD:
  preset_model=(COST_MODES.get(cm) or {}).get('phase_models',{}).get(key) or (COST_MODES.get(cm) or {}).get('phase_models',{}).get(kind)
  phase={'model':preset_model} if preset_model else {}
  override=dict(phase_overrides.get(key) or phase_overrides.get(kind) or phase_overrides.get(stage_id) or {})
  phase.update(override)
  requested_provider=phase.get('provider') or default_provider
  phase['provider']=normalize_live_provider(requested_provider)
  fp=stage_fingerprint(project,stage_id,'research')
  inp={'project':project,'project_id':project_id,'project_revision':int(project_revision),'stage_id':stage_id,'artifact_target':artifact_target,
       'input_fingerprint':fp,'analysis_module':(key[len('analysis_'):] if key.startswith('analysis_') else None),'mode':mode,'confirm_live':bool(confirm_live),'verification_requested':bool(verification),'cost_mode':cm,'budget_usd':budget_usd,'phase_policy':phase}
  jid=store.add_job(wid,key,kind,status='DRAFT',priority=priority,interaction_mode=imode,provider_policy=phase.get('provider'),model=phase.get('model'),estimated_cost_usd=phase.get('estimated_cost_usd'),input_data=inp,
                    idempotency_key=(f'{idempotency_key}:{key}' if idempotency_key else None),project_id=project_id,project_revision=project_revision,stage_id=stage_id,artifact_target=artifact_target,input_fingerprint=fp);ids[key]=jid
  if str(requested_provider or '').strip().lower() not in {'claude_code_subscription','claude_code','subscription','anthropic','claude_api','anthropic_api','api','openai','openai_api'}:
   store.event(jid,'CONFIG_NORMALIZED','Unsupported LIVE provider override was normalized to the selected supported runtime.',{'requested_provider':requested_provider,'effective_provider':phase.get('provider'),'stage_id':stage_id},'WARN')
  for d in deps:store.add_dependency(jid,ids[d])
 if after_workflow:store.add_workflow_dependency(wid,after_workflow)
 store.activate_workflow_graph(wid);return {'workflow_id':wid,'status':store.get_workflow(wid)['status'],'jobs':ids,'project_id':project_id,'project_revision':project_revision}

def command_center(store:JobStore)->dict[str,Any]:
 wfs=store.list_workflows(300);apps=store.pending_approvals();workers=store.workers();out={'needs_attention':[],'running':[],'scheduled':[],'finished':[],'failed':[],'workers':workers}
 approval_jobs={a['job_id'] for a in apps}
 for w in wfs:
  full=store.get_workflow(w['workflow_id']);jobs=full['jobs'];done=sum(j['status']=='COMPLETED' for j in jobs)
  _rank={'RUNNING':0,'WAITING_USER':1,'WAITING_CAPACITY':2,'WAITING_CREDITS':3,'RECOVERY_REQUIRED':4,'RETRYING':5,'QUEUED':6,'READY':7,'WAITING_DEPENDENCY':8,'PAUSED':9}
  _active=sorted((j for j in jobs if j.get('status') in _rank),key=lambda j:(_rank.get(j.get('status'),99),str(j.get('started_at') or '9999'),str(j.get('created_at') or '')))
  cur=_active[0] if _active else None
  rp=((cur or {}).get('input') or {}).get('project',{}).get('run_policy',{}) if cur else {}
  provider=(cur or {}).get('provider_policy') or rp.get('provider') or None
  model=(cur or {}).get('model') or (((cur or {}).get('input') or {}).get('project',{}).get('model') if cur else None)
  progress=None
  if cur:
   with store.cx() as c:ev=c.execute("SELECT payload_json FROM job_events WHERE job_id=? AND event_type='PROGRESS' ORDER BY event_id DESC LIMIT 1",(cur['job_id'],)).fetchone()
   if ev:
    import json
    try:progress=json.loads(ev['payload_json'] or '{}')
    except Exception:progress=None
  phases=[]
  for j in jobs:
   jp=(j.get('input') or {}).get('phase_policy') or {}
   phases.append({'node_key':j['node_key'],'kind':j['kind'],'status':j['status'],'stage_id':j.get('stage_id'),'artifact_target':j.get('artifact_target'),'provider':j.get('provider_policy') or jp.get('provider'),'model':j.get('model') or jp.get('model'),'estimated_cost_usd':j.get('estimated_cost_usd'),'actual_cost_usd':j.get('actual_cost_usd')})
  card={**w,'workflow':full,'done':done,'total':len(jobs),'current_job':cur,'provider':provider,'model':model,'progress':progress,'phases':phases,'approval_required':bool(cur and cur['job_id'] in approval_jobs)}
  if full['status'] in {'WAITING_USER','WAITING_CAPACITY','WAITING_CREDITS','RECOVERY_REQUIRED','PAUSED'}:out['needs_attention'].append(card)
  elif full['status'] in {'RUNNING','READY','QUEUED','WAITING_DEPENDENCY','RETRYING'}:out['running'].append(card)
  elif full['status']=='COMPLETED':out['finished'].append(card)
  elif full['status'] in {'FAILED','CANCELLED'}:out['failed'].append(card)
  else:out['scheduled'].append(card)
 out['approvals']=apps;return out
