from __future__ import annotations
import sqlite3,json,time,uuid,threading
from pathlib import Path
from typing import Any
from research_os_config import DB_PATH,LEASE_SECONDS

STATUSES={'DRAFT','READY','QUEUED','RUNNING','WAITING_DEPENDENCY','WAITING_USER','WAITING_CAPACITY','WAITING_CREDITS','PAUSED','RETRYING','RECOVERY_REQUIRED','COMPLETED','FAILED','CANCELLED'}
ALLOWED={
 'DRAFT':{'READY','CANCELLED'},'READY':{'QUEUED','CANCELLED'},'QUEUED':{'RUNNING','PAUSED','CANCELLED'},
 'RUNNING':{'COMPLETED','FAILED','WAITING_USER','WAITING_CAPACITY','WAITING_CREDITS','RETRYING','PAUSED','CANCELLED','RECOVERY_REQUIRED'},
 'WAITING_DEPENDENCY':{'QUEUED','CANCELLED'},'WAITING_USER':{'QUEUED','CANCELLED'},'WAITING_CAPACITY':{'QUEUED','PAUSED','CANCELLED'},'WAITING_CREDITS':{'QUEUED','PAUSED','CANCELLED'},'PAUSED':{'QUEUED','CANCELLED'},
 'RETRYING':{'QUEUED','RUNNING','FAILED','CANCELLED'},'RECOVERY_REQUIRED':{'QUEUED','CANCELLED','FAILED'},
 'FAILED':{'RETRYING','QUEUED','CANCELLED'},'COMPLETED':set(),'CANCELLED':set()
}
SCHEMA='''
PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS workflows(workflow_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,project_revision INTEGER NOT NULL,workflow_type TEXT NOT NULL,status TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 50,budget_usd REAL,cost_mode TEXT NOT NULL DEFAULT 'ECONOMY',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,node_key TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,priority INTEGER NOT NULL DEFAULT 50,run_after TEXT,scheduled_for TEXT,started_at TEXT,heartbeat_at TEXT,finished_at TEXT,attempt INTEGER NOT NULL DEFAULT 0,max_attempts INTEGER NOT NULL DEFAULT 3,lease_owner TEXT,lease_until TEXT,interaction_mode TEXT NOT NULL DEFAULT 'auto',provider_policy TEXT,model TEXT,estimated_cost_usd REAL,actual_cost_usd REAL NOT NULL DEFAULT 0,project_id TEXT,project_revision INTEGER,stage_id TEXT,artifact_target TEXT,input_fingerprint TEXT,input_json TEXT NOT NULL DEFAULT '{}',output_json TEXT NOT NULL DEFAULT '{}',error_json TEXT NOT NULL DEFAULT '{}',idempotency_key TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,cancel_requested INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(workflow_id) REFERENCES workflows(workflow_id),UNIQUE(workflow_id,node_key),UNIQUE(idempotency_key));
CREATE TABLE IF NOT EXISTS job_dependencies(job_id TEXT NOT NULL,depends_on_job_id TEXT NOT NULL,dependency_type TEXT NOT NULL DEFAULT 'success',PRIMARY KEY(job_id,depends_on_job_id),FOREIGN KEY(job_id) REFERENCES jobs(job_id),FOREIGN KEY(depends_on_job_id) REFERENCES jobs(job_id));
CREATE TABLE IF NOT EXISTS workflow_dependencies(workflow_id TEXT NOT NULL,depends_on_workflow_id TEXT NOT NULL,PRIMARY KEY(workflow_id,depends_on_workflow_id));
CREATE TABLE IF NOT EXISTS schedules(schedule_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,project_revision INTEGER,use_latest_revision INTEGER NOT NULL DEFAULT 0,schedule_type TEXT NOT NULL,schedule_expr TEXT NOT NULL,timezone TEXT NOT NULL DEFAULT 'Europe/Prague',enabled INTEGER NOT NULL DEFAULT 1,misfire_policy TEXT NOT NULL DEFAULT 'run_once',workflow_template_json TEXT NOT NULL,next_run_at TEXT,last_run_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schedule_occurrences(occurrence_id TEXT PRIMARY KEY,schedule_id TEXT NOT NULL,due_at TEXT NOT NULL,workflow_id TEXT,status TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,FOREIGN KEY(schedule_id) REFERENCES schedules(schedule_id));
CREATE TABLE IF NOT EXISTS approvals(approval_id TEXT PRIMARY KEY,job_id TEXT NOT NULL,status TEXT NOT NULL,question TEXT NOT NULL,options_json TEXT NOT NULL,context_json TEXT NOT NULL DEFAULT '{}',decision_json TEXT,created_at TEXT NOT NULL,decided_at TEXT,FOREIGN KEY(job_id) REFERENCES jobs(job_id));
CREATE TABLE IF NOT EXISTS job_events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT NOT NULL,ts TEXT NOT NULL,level TEXT NOT NULL,event_type TEXT NOT NULL,message TEXT NOT NULL,payload_json TEXT NOT NULL DEFAULT '{}',FOREIGN KEY(job_id) REFERENCES jobs(job_id));
CREATE TABLE IF NOT EXISTS cost_reservations(reservation_id TEXT PRIMARY KEY,workflow_id TEXT NOT NULL,job_id TEXT,amount_usd REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,settled_at TEXT);
CREATE TABLE IF NOT EXISTS worker_state(worker_id TEXT PRIMARY KEY,pid INTEGER,heartbeat_at TEXT,status TEXT,current_job_id TEXT,metadata_json TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_jobs_runnable ON jobs(status,run_after,priority); CREATE INDEX IF NOT EXISTS idx_jobs_workflow ON jobs(workflow_id); CREATE INDEX IF NOT EXISTS idx_schedules_next ON schedules(enabled,next_run_at); CREATE INDEX IF NOT EXISTS idx_events_job ON job_events(job_id,event_id);
'''
def now()->str:return time.strftime('%Y-%m-%dT%H:%M:%S')
def _loads(x,default):
 try:return json.loads(x or '')
 except Exception:return default
def _iso_epoch(s:str|None)->float:
 if not s:return 0
 try:return time.mktime(time.strptime(s[:19],'%Y-%m-%dT%H:%M:%S'))
 except Exception:return 0
class JobStore:
 def __init__(self,path: str|Path=DB_PATH): self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self._init()
 def cx(self):
  c=sqlite3.connect(self.path,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA journal_mode=WAL');return c
 def _init(self):
  with self.cx() as c:
   c.executescript(SCHEMA)
   cols={r[1] for r in c.execute('PRAGMA table_info(jobs)').fetchall()}
   for spec in ('project_id TEXT','project_revision INTEGER','stage_id TEXT','artifact_target TEXT','input_fingerprint TEXT'):
    if spec.split()[0] not in cols:c.execute('ALTER TABLE jobs ADD COLUMN '+spec)
   # Backfill project linkage from the owning workflow for 17.8.x rows.
   c.execute('''UPDATE jobs SET project_id=COALESCE(project_id,(SELECT project_id FROM workflows w WHERE w.workflow_id=jobs.workflow_id)),
              project_revision=COALESCE(project_revision,(SELECT project_revision FROM workflows w WHERE w.workflow_id=jobs.workflow_id))''')
 def event(self,job_id,typ,msg,payload=None,level='INFO'):
  with self.cx() as c:c.execute('INSERT INTO job_events(job_id,ts,level,event_type,message,payload_json) VALUES(?,?,?,?,?,?)',(job_id,now(),level,typ,msg,json.dumps(payload or {},ensure_ascii=False,default=str)))
 def create_workflow(self,*,project_id,project_revision,workflow_type='standard_study',priority=50,budget_usd=None,cost_mode='ECONOMY',metadata=None,workflow_id=None):
  wid=workflow_id or 'WF-'+uuid.uuid4().hex[:16];t=now()
  with self.cx() as c:c.execute('INSERT INTO workflows VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(wid,project_id,int(project_revision),workflow_type,'READY',int(priority),budget_usd,cost_mode,t,t,None,None,json.dumps(metadata or {},ensure_ascii=False,default=str)))
  return wid
 def add_job(self,workflow_id,node_key,kind,*,status='READY',priority=50,run_after=None,scheduled_for=None,max_attempts=3,interaction_mode='auto',provider_policy=None,model=None,estimated_cost_usd=None,input_data=None,idempotency_key=None,project_id=None,project_revision=None,stage_id=None,artifact_target=None,input_fingerprint=None):
  jid='JOB-'+uuid.uuid4().hex[:16]; idem=idempotency_key or f'{workflow_id}:{node_key}';t=now()
  with self.cx() as c:
   old=c.execute('SELECT job_id FROM jobs WHERE idempotency_key=?',(idem,)).fetchone()
   if old:return old['job_id']
   wf=c.execute('SELECT project_id,project_revision FROM workflows WHERE workflow_id=?',(workflow_id,)).fetchone()
   pid=project_id or (wf['project_id'] if wf else None); prev=int(project_revision if project_revision is not None else (wf['project_revision'] if wf else 0))
   c.execute('''INSERT INTO jobs(job_id,workflow_id,node_key,kind,status,priority,run_after,scheduled_for,started_at,heartbeat_at,finished_at,attempt,max_attempts,lease_owner,lease_until,interaction_mode,provider_policy,model,estimated_cost_usd,actual_cost_usd,project_id,project_revision,stage_id,artifact_target,input_fingerprint,input_json,output_json,error_json,idempotency_key,created_at,updated_at,cancel_requested) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(jid,workflow_id,node_key,kind,status,int(priority),run_after,scheduled_for,None,None,None,0,int(max_attempts),None,None,interaction_mode,provider_policy,model,estimated_cost_usd,0.0,pid,prev,stage_id,artifact_target,input_fingerprint,json.dumps(input_data or {},ensure_ascii=False,default=str),'{}','{}',idem,t,t,0))
  self.event(jid,'CREATED',f'{kind} created',{'status':status,'project_id':pid,'project_revision':prev,'stage_id':stage_id,'artifact_target':artifact_target});return jid
 def add_dependency(self,job_id,depends_on_job_id,dependency_type='success'):
  with self.cx() as c:c.execute('INSERT OR IGNORE INTO job_dependencies VALUES(?,?,?)',(job_id,depends_on_job_id,dependency_type))
 def activate_workflow_graph(self,wid):
  with self.cx() as c:
   rows=c.execute("SELECT job_id FROM jobs WHERE workflow_id=? AND status='DRAFT'",(wid,)).fetchall()
   c.execute("UPDATE jobs SET status='READY',updated_at=? WHERE workflow_id=? AND status='DRAFT'",(now(),wid))
   blocked=bool(c.execute("SELECT 1 FROM workflow_dependencies wd JOIN workflows dw ON dw.workflow_id=wd.depends_on_workflow_id WHERE wd.workflow_id=? AND dw.status!='COMPLETED' LIMIT 1",(wid,)).fetchone())
   c.execute("UPDATE workflows SET status=?,updated_at=? WHERE workflow_id=?",('WAITING_DEPENDENCY' if blocked else 'READY',now(),wid))
  for r in rows:self.event(r['job_id'],'GRAPH_READY','workflow dependency graph published',{'workflow_id':wid})
  self.queue_ready_jobs(wid);self.refresh_workflow(wid);return len(rows)
 def add_workflow_dependency(self,wid,depends_wid):
  with self.cx() as c:c.execute('INSERT OR IGNORE INTO workflow_dependencies VALUES(?,?)',(wid,depends_wid));c.execute("UPDATE workflows SET status='WAITING_DEPENDENCY',updated_at=? WHERE workflow_id=?",(now(),wid))
 def transition(self,job_id,new_status,*,output=None,error=None,message=None,force=False):
  if new_status not in STATUSES:raise ValueError(new_status)
  with self.cx() as c:
   r=c.execute('SELECT status,workflow_id FROM jobs WHERE job_id=?',(job_id,)).fetchone()
   if not r:raise KeyError(job_id)
   old=r['status']
   if not force and new_status!=old and new_status not in ALLOWED.get(old,set()):raise ValueError(f'Illegal job transition {old}->{new_status}')
   fields=['status=?','updated_at=?'];vals=[new_status,now()]
   if new_status=='RUNNING':fields+=['started_at=COALESCE(started_at,?)'];vals+=[now()]
   if new_status in {'COMPLETED','FAILED','CANCELLED'}:fields+=['finished_at=?','lease_owner=NULL','lease_until=NULL'];vals+=[now()]
   if output is not None:fields+=['output_json=?'];vals+=[json.dumps(output,ensure_ascii=False,default=str)]
   if error is not None:fields+=['error_json=?'];vals+=[json.dumps(error,ensure_ascii=False,default=str)]
   vals.append(job_id);c.execute('UPDATE jobs SET '+','.join(fields)+' WHERE job_id=?',vals)
  self.event(job_id,'STATUS',message or f'{old}->{new_status}',{'from':old,'to':new_status},'ERROR' if new_status=='FAILED' else 'INFO');self.refresh_workflow(r['workflow_id'])
  if new_status=='COMPLETED': self.queue_ready_jobs(r['workflow_id'])
 def refresh_workflow(self,wid):
  with self.cx() as c:
   wr=c.execute('SELECT status FROM workflows WHERE workflow_id=?',(wid,)).fetchone();current=wr['status'] if wr else None
   rows=c.execute('SELECT status FROM jobs WHERE workflow_id=?',(wid,)).fetchall();sts=[r['status'] for r in rows]
   if not sts:return
   if all(s=='COMPLETED' for s in sts):ws='COMPLETED'
   elif all(s in {'COMPLETED','CANCELLED'} for s in sts) and any(s=='CANCELLED' for s in sts):ws='CANCELLED'
   elif any(s=='FAILED' for s in sts):ws='FAILED'
   elif current=='PAUSED':ws='PAUSED'
   elif any(s=='WAITING_USER' for s in sts):ws='WAITING_USER'
   elif any(s=='WAITING_CAPACITY' for s in sts):ws='WAITING_CAPACITY'
   elif any(s=='WAITING_CREDITS' for s in sts):ws='WAITING_CREDITS'
   elif any(s=='RUNNING' for s in sts):ws='RUNNING'
   elif any(s in {'QUEUED','RETRYING'} for s in sts):ws='QUEUED'
   elif any(s=='PAUSED' for s in sts):ws='PAUSED'
   else:ws='READY'
   t=now();c.execute('UPDATE workflows SET status=?,updated_at=?,started_at=CASE WHEN ?=\'RUNNING\' THEN COALESCE(started_at,?) ELSE started_at END,finished_at=CASE WHEN ? IN (\'COMPLETED\',\'FAILED\',\'CANCELLED\') THEN ? ELSE finished_at END WHERE workflow_id=?',(ws,t,ws,t,ws,t,wid))
 def queue_ready_jobs(self,wid=None):
  with self.cx() as c:
   if wid:
    wr=c.execute('SELECT status FROM workflows WHERE workflow_id=?',(wid,)).fetchone()
    if wr and wr['status'] in {'PAUSED','CANCELLED'}:return 0
   q="SELECT j.job_id,j.workflow_id FROM jobs j JOIN workflows w ON w.workflow_id=j.workflow_id WHERE j.status IN ('READY','WAITING_DEPENDENCY','RETRYING') AND w.status NOT IN ('PAUSED','CANCELLED')";args=[]
   if wid:q+=' AND j.workflow_id=?';args=[wid]
   for r in c.execute(q,args).fetchall():
    deps=c.execute('SELECT d.depends_on_job_id,j2.status FROM job_dependencies d JOIN jobs j2 ON j2.job_id=d.depends_on_job_id WHERE d.job_id=?',(r['job_id'],)).fetchall()
    wfdeps=c.execute('SELECT wd.depends_on_workflow_id,w.status FROM workflow_dependencies wd JOIN workflows w ON w.workflow_id=wd.depends_on_workflow_id WHERE wd.workflow_id=?',(r['workflow_id'],)).fetchall()
    if all(x['status']=='COMPLETED' for x in deps) and all(x['status']=='COMPLETED' for x in wfdeps):
     c.execute("UPDATE jobs SET status='QUEUED',updated_at=? WHERE job_id=?",(now(),r['job_id']))
   if wid:c.execute("UPDATE workflows SET status=CASE WHEN EXISTS(SELECT 1 FROM jobs WHERE workflow_id=? AND status='QUEUED') THEN 'QUEUED' ELSE status END,updated_at=? WHERE workflow_id=?",(wid,now(),wid))
 def claim(self,worker_id):
  self.queue_ready_jobs()
  with self.cx() as c:
   c.execute('BEGIN IMMEDIATE')
   r=c.execute("""SELECT j.* FROM jobs j JOIN workflows w ON w.workflow_id=j.workflow_id
      WHERE j.status='QUEUED' AND (j.run_after IS NULL OR j.run_after<=?) AND w.status NOT IN ('PAUSED','CANCELLED')
        AND NOT EXISTS (SELECT 1 FROM job_dependencies d JOIN jobs dj ON dj.job_id=d.depends_on_job_id WHERE d.job_id=j.job_id AND dj.status!='COMPLETED')
        AND NOT EXISTS (SELECT 1 FROM workflow_dependencies wd JOIN workflows dw ON dw.workflow_id=wd.depends_on_workflow_id WHERE wd.workflow_id=j.workflow_id AND dw.status!='COMPLETED')
      ORDER BY j.priority DESC,j.created_at LIMIT 1""",(now(),)).fetchone()
   if not r:c.commit();return None
   until=time.strftime('%Y-%m-%dT%H:%M:%S',time.localtime(time.time()+LEASE_SECONDS))
   c.execute("UPDATE jobs SET status='RUNNING',lease_owner=?,lease_until=?,heartbeat_at=?,started_at=COALESCE(started_at,?),attempt=attempt+1,updated_at=? WHERE job_id=? AND status='QUEUED'",(worker_id,until,now(),now(),now(),r['job_id']))
   if c.total_changes!=1:c.rollback();return None
   c.commit()
  self.event(r['job_id'],'CLAIMED',f'claimed by {worker_id}',{'lease_until':until});self.refresh_workflow(r['workflow_id']);return self.get_job(r['job_id'])
 def heartbeat(self,job_id,worker_id):
  until=time.strftime('%Y-%m-%dT%H:%M:%S',time.localtime(time.time()+LEASE_SECONDS))
  with self.cx() as c:c.execute("UPDATE jobs SET heartbeat_at=?,lease_until=?,updated_at=? WHERE job_id=? AND lease_owner=? AND status='RUNNING'",(now(),until,now(),job_id,worker_id))
 def recover_expired(self):
  n=0;events=[]
  with self.cx() as c:
   rows=c.execute("SELECT job_id,workflow_id,kind,input_json,attempt,max_attempts FROM jobs WHERE status='RUNNING' AND lease_until IS NOT NULL AND lease_until<?",(now(),)).fetchall()
   for r in rows:
    inp=_loads(r['input_json'],{});project=inp.get('project') or {};rp=project.get('run_policy') or {};provider=str(rp.get('provider') or 'anthropic')
    if r['kind']=='legacy_task':
     lp=inp.get('payload') or {};project=lp.get('project') or project;rp=project.get('run_policy') or {};provider=str(lp.get('provider') or rp.get('provider') or ((lp.get('spec') or {}).get('provider')) or provider)
    for d in reversed(inp.get('approval_decisions') or []):
     if d.get('provider')=='anthropic':provider='anthropic';break
    paid_uncertain=(r['kind']=='respondent_run' and str(inp.get('mode') or 'dry')!='dry' and provider == 'anthropic')
    if r['kind']=='legacy_task':
     lp=inp.get('payload') or {};legacy_mode=str(lp.get('mode') or ((lp.get('spec') or {}).get('mode')) or 'dry');paid_uncertain=bool(lp.get('confirm_live')) and legacy_mode!='dry' and provider == 'anthropic'
    if paid_uncertain:
     st='RECOVERY_REQUIRED'
     # We cannot know whether an in-flight provider request was already billed. Convert
     # any outstanding reservation into conservative estimated exposure before retry.
     rr=c.execute("SELECT reservation_id,amount_usd FROM cost_reservations WHERE job_id=? AND status='RESERVED'",(r['job_id'],)).fetchall()
     uncertain=sum(float(x['amount_usd'] or 0) for x in rr)
     if rr:
      c.execute("UPDATE cost_reservations SET status='SETTLED_UNCERTAIN',settled_at=? WHERE job_id=? AND status='RESERVED'",(now(),r['job_id']))
      c.execute('UPDATE jobs SET actual_cost_usd=actual_cost_usd+? WHERE job_id=?',(uncertain,r['job_id']))
     payload={'status':st,'reason':'paid_external_call_side_effect_uncertain','conservative_cost_exposure_usd':uncertain}
    else:
     st='RETRYING' if r['attempt']<r['max_attempts'] else 'RECOVERY_REQUIRED';payload={'status':st,'reason':'expired_lease_idempotent_or_subscription'}
    c.execute('UPDATE jobs SET status=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=?',(st,now(),r['job_id']));n+=1;events.append((r['job_id'],r['workflow_id'],payload))
  for jid,wid,payload in events:self.event(jid,'RECOVERY','expired lease recovered',payload,'WARN');self.refresh_workflow(wid)
  self.queue_ready_jobs();return n
 def request_cancel(self,job_id,source='unknown',reason=''):
  with self.cx() as c:
   r=c.execute('SELECT status FROM jobs WHERE job_id=?',(job_id,)).fetchone()
   if not r:return False
   if r['status']=='RUNNING':
    c.execute('UPDATE jobs SET cancel_requested=1,updated_at=? WHERE job_id=?',(now(),job_id))
   elif r['status'] not in {'COMPLETED','FAILED','CANCELLED'}:
    c.execute("UPDATE jobs SET status='CANCELLED',cancel_requested=1,finished_at=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",(now(),now(),job_id))
    c.execute("UPDATE approvals SET status='CANCELLED',decided_at=? WHERE job_id=? AND status='PENDING'",(now(),job_id))
  self.event(job_id,'CANCEL_REQUESTED','cancel requested',{'job_id':job_id,'source':str(source or 'unknown')[:120],'reason':str(reason or '')[:500]},'WARN')
  return True
 def cancel_requested(self,job_id):
  with self.cx() as c:r=c.execute('SELECT cancel_requested FROM jobs WHERE job_id=?',(job_id,)).fetchone();return bool(r and r[0])
 def get_job(self,jid):
  with self.cx() as c:r=c.execute('SELECT * FROM jobs WHERE job_id=?',(jid,)).fetchone();return self._job(r) if r else None
 def _job(self,r):
  d=dict(r);d['input']=_loads(d.pop('input_json',None),{});d['output']=_loads(d.pop('output_json',None),{});d['error']=_loads(d.pop('error_json',None),{});return d
 def get_workflow(self,wid):
  with self.cx() as c:
   r=c.execute('SELECT * FROM workflows WHERE workflow_id=?',(wid,)).fetchone()
   if not r:return None
   d=dict(r);d['metadata']=_loads(d.pop('metadata_json',None),{});d['jobs']=[self._job(x) for x in c.execute('SELECT * FROM jobs WHERE workflow_id=? ORDER BY created_at,node_key',(wid,)).fetchall()];return d
 def list_jobs(self,statuses=None,limit=200):
  with self.cx() as c:
   if statuses:
    ss=[x for x in statuses if x in STATUSES];q='SELECT * FROM jobs WHERE status IN (%s) ORDER BY priority DESC,created_at DESC LIMIT ?'%(','.join('?'*len(ss)));rows=c.execute(q,(*ss,int(limit))).fetchall()
   else:rows=c.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?',(int(limit),)).fetchall()
  return [self._job(r) for r in rows]
 def list_workflows(self,limit=200):
  with self.cx() as c:rows=c.execute('SELECT * FROM workflows ORDER BY created_at DESC LIMIT ?',(int(limit),)).fetchall()
  out=[]
  for r in rows:
   d=dict(r);d['metadata']=_loads(d.pop('metadata_json',None),{});out.append(d)
  return out
 def pending_approvals(self):
  with self.cx() as c:rows=c.execute("SELECT * FROM approvals WHERE status='PENDING' ORDER BY created_at").fetchall()
  return [{**dict(r),'options':_loads(r['options_json'],[]),'context':_loads(r['context_json'],{})} for r in rows]
 def create_approval(self,job_id,question,options,context=None):
  aid='APR-'+uuid.uuid4().hex[:16]
  with self.cx() as c:c.execute('INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?)',(aid,job_id,'PENDING',question,json.dumps(options,ensure_ascii=False),json.dumps(context or {},ensure_ascii=False),None,now(),None))
  self.transition(job_id,'WAITING_USER',message='approval required');return aid
 def decide_approval(self,approval_id,decision):
  decision=dict(decision or {});opt=str(decision.get('option') or '').strip()
  with self.cx() as c:
   r=c.execute('SELECT job_id,status,options_json,context_json FROM approvals WHERE approval_id=?',(approval_id,)).fetchone()
   if not r:raise KeyError(approval_id)
   if r['status']!='PENDING':raise ValueError('Approval already decided')
   options=_loads(r['options_json'],[])
   allowed=set()
   for x in options:
    if isinstance(x,dict) and str(x.get('option') or '').strip():allowed.add(str(x['option']).strip())
    elif isinstance(x,str) and x.strip():allowed.add(x.strip())
   if not opt or opt not in allowed:
    raise ValueError('Neplatná approval volba. Povolené možnosti: '+', '.join(sorted(allowed)))
   ctx=_loads(r['context_json'],{})
   # Persist the cost estimate shown at approval time together with the chosen provider.
   if opt in {'use_anthropic_api','use_openai_api'}:
    estimates=ctx.get('provider_estimates_usd') or {}
    provider='anthropic' if opt=='use_anthropic_api' else 'openai'
    if provider not in estimates:
     raise ValueError(f'Approval neobsahuje platný cost estimate pro provider {provider}.')
    decision['provider']=provider
    decision['estimated_cost_usd']=float(estimates[provider])
   j=c.execute('SELECT input_json,workflow_id FROM jobs WHERE job_id=?',(r['job_id'],)).fetchone()
   if not j:raise KeyError(r['job_id'])
   inp=_loads(j['input_json'],{})
   if opt=='increase_budget':
    new_cap=float(decision.get('budget_usd') if decision.get('budget_usd') is not None else (decision.get('value') or 0))
    if new_cap<=0:raise ValueError('increase_budget vyžaduje budget_usd/value > 0')
    decision['budget_usd']=new_cap
    c.execute('UPDATE workflows SET budget_usd=?,updated_at=? WHERE workflow_id=?',(new_cap,now(),j['workflow_id']))
   if opt=='reduce_n':
    new_n=int(decision.get('n') if decision.get('n') is not None else (decision.get('value') or 0))
    if new_n<=0:raise ValueError('reduce_n vyžaduje n/value > 0')
    decision['n']=new_n
    pr=dict(inp.get('project') or {});pr['n']=new_n;inp['project']=pr
   inp.setdefault('approval_decisions',[]).append(decision)
   target='CANCELLED' if opt=='cancel' else ('PAUSED' if opt=='continue_later' else 'QUEUED')
   c.execute("UPDATE approvals SET status='DECIDED',decision_json=?,decided_at=? WHERE approval_id=?",(json.dumps(decision,ensure_ascii=False),now(),approval_id))
   c.execute('UPDATE jobs SET input_json=?,status=?,cancel_requested=?,updated_at=? WHERE job_id=?',(json.dumps(inp,ensure_ascii=False),target,1 if target=='CANCELLED' else 0,now(),r['job_id']))
  self.event(r['job_id'],'APPROVED','user decision',decision);self.refresh_workflow(self.get_job(r['job_id'])['workflow_id']);return self.get_job(r['job_id'])

 def configure_job(self,job_id,*,provider=None,model=None,estimated_cost_usd=None,phase_policy=None):
  with self.cx() as c:
   r=c.execute('SELECT status,input_json,workflow_id FROM jobs WHERE job_id=?',(job_id,)).fetchone()
   if not r:raise KeyError(job_id)
   if r['status'] in {'RUNNING','COMPLETED','CANCELLED'}:raise ValueError('Běžící nebo dokončenou fázi nelze přepsat.')
   inp=_loads(r['input_json'],{});pp=dict(inp.get('phase_policy') or {})
   if phase_policy:pp.update(dict(phase_policy))
   if provider is not None:pp['provider']=str(provider)
   if model is not None:pp['model']=str(model)
   inp['phase_policy']=pp;fields=['input_json=?','updated_at=?'];vals=[json.dumps(inp,ensure_ascii=False,default=str),now()]
   if provider is not None:fields.append('provider_policy=?');vals.append(str(provider))
   if model is not None:fields.append('model=?');vals.append(str(model))
   if estimated_cost_usd is not None:fields.append('estimated_cost_usd=?');vals.append(float(estimated_cost_usd))
   vals.append(job_id);c.execute('UPDATE jobs SET '+','.join(fields)+' WHERE job_id=?',vals)
  self.event(job_id,'CONFIG_UPDATED','Commander phase policy updated',{'provider':provider,'model':model,'estimated_cost_usd':estimated_cost_usd});self.refresh_workflow(r['workflow_id']);return self.get_job(job_id)

 def requeue_capacity_waiters(self):
  with self.cx() as c:
   rows=c.execute("SELECT job_id,input_json,workflow_id FROM jobs WHERE status='WAITING_CAPACITY'").fetchall()
  if not rows:return 0
  global _CAPACITY_HEALTH_CACHE
  try:
   cache=globals().get('_CAPACITY_HEALTH_CACHE') or {'ts':0.0,'ok':False}
   if time.monotonic()-float(cache.get('ts') or 0)>45:
    from claude_code_provider import health
    cache={'ts':time.monotonic(),'ok':bool(health(timeout=5).get('ok'))};globals()['_CAPACITY_HEALTH_CACHE']=cache
   if not cache.get('ok'):return 0
  except Exception as exc:
   for r in rows:self.event(r['job_id'],'WARN','capacity health check failed',{'error':str(exc)[:500]},'WARN')
   return 0
  changed=[]
  with self.cx() as c:
   for r in rows:
    inp=_loads(r['input_json'],{});rp=((inp.get('project') or {}).get('run_policy') or {})
    if not bool(rp.get('auto_resume_capacity')):continue
    c.execute("UPDATE jobs SET status='QUEUED',updated_at=?,error_json='{}' WHERE job_id=?",(now(),r['job_id']));changed.append((r['job_id'],r['workflow_id']))
  for jid,wid in changed:self.event(jid,'AUTO_RESUME','Claude Code capacity available; job requeued',{});self.refresh_workflow(wid)
  return len(changed)

 def updates(self,since=0,limit=500):
  with self.cx() as c:rows=c.execute('SELECT * FROM job_events WHERE event_id>? ORDER BY event_id LIMIT ?',(int(since),int(limit))).fetchall()
  return [{**dict(r),'payload':_loads(r['payload_json'],{})} for r in rows]
 def worker_heartbeat(self,worker_id,pid,status='READY',current_job_id=None,metadata=None):
  with self.cx() as c:c.execute('INSERT INTO worker_state VALUES(?,?,?,?,?,?) ON CONFLICT(worker_id) DO UPDATE SET pid=excluded.pid,heartbeat_at=excluded.heartbeat_at,status=excluded.status,current_job_id=excluded.current_job_id,metadata_json=excluded.metadata_json',(worker_id,int(pid),now(),status,current_job_id,json.dumps(metadata or {},ensure_ascii=False)))
 def workers(self):
  with self.cx() as c:return [dict(r) for r in c.execute('SELECT * FROM worker_state ORDER BY heartbeat_at DESC').fetchall()]
