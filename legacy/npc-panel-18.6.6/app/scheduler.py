from __future__ import annotations
import json,time,uuid,datetime as dt,calendar
from typing import Any
from job_store import JobStore,now
MISFIRE_GRACE_SECONDS=60
from workflow_engine import create_standard
from project_store import ProjectStore

def _parse_iso(s:str)->dt.datetime:return dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None)
def _fmt(x:dt.datetime)->str:return x.strftime('%Y-%m-%dT%H:%M:%S')
def _add_months(base:dt.datetime,months:int)->dt.datetime:
 total=(base.year*12+(base.month-1))+max(1,int(months));year,mi=divmod(total,12);month=mi+1
 day=min(base.day,calendar.monthrange(year,month)[1]);return base.replace(year=year,month=month,day=day)
def _next_simple(expr:str,base:dt.datetime)->dt.datetime:
 # Local deterministic recurring contract: friendly aliases + a safe RRULE subset.
 raw=str(expr).strip();e=raw.lower()
 if e=='@hourly':return base+dt.timedelta(hours=1)
 if e=='@daily':return base+dt.timedelta(days=1)
 if e=='@weekly':return base+dt.timedelta(weeks=1)
 if e=='@monthly':return _add_months(base,1)
 if e.startswith('every:'):return base+dt.timedelta(minutes=max(1,int(e.split(':',1)[1])))
 rr=raw[6:] if raw.upper().startswith('RRULE:') else raw
 if 'FREQ=' in rr.upper():
  parts={}
  for item in rr.split(';'):
   if '=' in item:
    k,v=item.split('=',1);parts[k.strip().upper()]=v.strip().upper()
  freq=parts.get('FREQ');interval=max(1,int(parts.get('INTERVAL','1')))
  if freq=='HOURLY':out=base+dt.timedelta(hours=interval)
  elif freq=='DAILY':out=base+dt.timedelta(days=interval)
  elif freq=='WEEKLY':out=base+dt.timedelta(weeks=interval)
  elif freq=='MONTHLY':out=_add_months(base,interval)
  else:raise ValueError('RRULE supports FREQ=HOURLY|DAILY|WEEKLY|MONTHLY in 17.2.0')
  # Optional local clock pinning; intentionally no arbitrary eval/cron parser.
  if 'BYHOUR' in parts:out=out.replace(hour=max(0,min(23,int(parts['BYHOUR'].split(',')[0]))))
  if 'BYMINUTE' in parts:out=out.replace(minute=max(0,min(59,int(parts['BYMINUTE'].split(',')[0]))),second=0,microsecond=0)
  return out
 raise ValueError('recurring schedule_expr supports @hourly, @daily, @weekly, @monthly, every:<minutes>, or safe RRULE FREQ/INTERVAL/BYHOUR/BYMINUTE')
class Scheduler:
 def __init__(self,store:JobStore,project_store_path='data/project_store.sqlite'):self.s=store;self.project_store_path=project_store_path
 def create(self,spec:dict[str,Any]):
  sid='SCH-'+uuid.uuid4().hex[:15];t=now();typ=str(spec.get('schedule_type') or 'one_time');expr=str(spec.get('schedule_expr') or '')
  
  if typ=='one_time': next_at=expr
  elif typ=='recurring': next_at=str(spec.get('next_run_at') or (expr if 'T' in expr else now()))
  elif typ in {'after_workflow','conditional'}: next_at=str(spec.get('next_run_at') or now())
  else: raise ValueError('schedule_type must be one_time, recurring, after_workflow, conditional')
  with self.s.cx() as c:c.execute('INSERT INTO schedules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,spec['project_id'],spec.get('project_revision'),1 if spec.get('use_latest_revision') else 0,typ,expr,spec.get('timezone','Europe/Prague'),1,spec.get('misfire_policy','run_once'),json.dumps(spec.get('workflow_template') or {},ensure_ascii=False),next_at,None,t,t))
  return self.get(sid)
 def get(self,sid):
  with self.s.cx() as c:r=c.execute('SELECT * FROM schedules WHERE schedule_id=?',(sid,)).fetchone();return dict(r) if r else None
 def list(self):
  with self.s.cx() as c:return [dict(r) for r in c.execute('SELECT * FROM schedules ORDER BY next_run_at').fetchall()]
 def delete(self,sid):
  with self.s.cx() as c:c.execute('DELETE FROM schedules WHERE schedule_id=?',(sid,));return True
 def patch(self,sid,changes):
  allowed={'enabled','misfire_policy','schedule_expr','next_run_at','use_latest_revision'};sets=[];vals=[]
  for k,v in changes.items():
   if k in allowed:sets.append(k+'=?');vals.append(int(v) if k in {'enabled','use_latest_revision'} else v)
  if sets:
   vals += [now(),sid]
   with self.s.cx() as c:c.execute('UPDATE schedules SET '+','.join(sets)+',updated_at=? WHERE schedule_id=?',vals)
  return self.get(sid)
 def tick(self,now_dt:dt.datetime|None=None):
  now_dt=now_dt or dt.datetime.now();made=[]
  with self.s.cx() as c:due=c.execute('SELECT * FROM schedules WHERE enabled=1 AND next_run_at IS NOT NULL AND next_run_at<=? ORDER BY next_run_at',(_fmt(now_dt),)).fetchall()
  ps=ProjectStore(self.project_store_path)
  try:
   for r in due:
    d=dict(r);due_at=d['next_run_at'];idem=f"{d['schedule_id']}:{due_at}"
    with self.s.cx() as c:
     if c.execute('SELECT 1 FROM schedule_occurrences WHERE idempotency_key=?',(idem,)).fetchone():continue
    tpl=json.loads(d['workflow_template_json'] or '{}')
    resume_wid=str(tpl.get('resume_workflow_id') or '').strip()
    if resume_wid:
     wf=self.s.get_workflow(resume_wid)
     if not wf:
      with self.s.cx() as c:c.execute('UPDATE schedules SET enabled=0,last_run_at=?,next_run_at=NULL,updated_at=? WHERE schedule_id=?',(due_at,now(),d['schedule_id']))
      continue
     # WAITING_USER is intentionally excluded: an explicit approval must be resolved by a human.
     resumable={'PAUSED','WAITING_CAPACITY','WAITING_CREDITS','RECOVERY_REQUIRED'}
     changed=0
     with self.s.cx() as c:
      for j in wf.get('jobs') or []:
       if j.get('status') in resumable:
        c.execute("UPDATE jobs SET status='QUEUED',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=?",(now(),j['job_id']));changed+=1
      if changed:
       c.execute("UPDATE workflows SET status='QUEUED',updated_at=? WHERE workflow_id=?",(now(),resume_wid))
     if changed:
      for j in wf.get('jobs') or []:
       if j.get('status') in resumable:self.s.event(j['job_id'],'SCHEDULED_RESUME','Scheduled workflow continuation triggered',{'schedule_id':d['schedule_id'],'due_at':due_at})
      self.s.queue_ready_jobs(resume_wid)
     oid='OCC-'+uuid.uuid4().hex[:15]
     with self.s.cx() as c:
      c.execute('INSERT INTO schedule_occurrences VALUES(?,?,?,?,?,?,?)',(oid,d['schedule_id'],due_at,resume_wid,'RESUMED' if changed else 'NOOP',idem,now()))
      c.execute('UPDATE schedules SET enabled=0,last_run_at=?,next_run_at=NULL,updated_at=? WHERE schedule_id=?',(due_at,now(),d['schedule_id']))
     made.append(resume_wid) if changed else None
     continue
    # A schedule is a misfire only when it is meaningfully late; normal polling jitter is not a miss.
    lag=max(0.0,(now_dt-_parse_iso(due_at)).total_seconds())
    if d.get('misfire_policy')=='skip' and lag>MISFIRE_GRACE_SECONDS:
     if d['schedule_type']=='recurring': nxt=_fmt(_next_simple(d['schedule_expr'],now_dt))
     else: nxt=None
     with self.s.cx() as c:c.execute('UPDATE schedules SET last_run_at=?,next_run_at=?,updated_at=? WHERE schedule_id=?',(due_at,nxt,now(),d['schedule_id']))
     continue
    if d['schedule_type']=='after_workflow':
     dep=str(d['schedule_expr'] or tpl.get('after_workflow') or '')
     with self.s.cx() as c: wr=c.execute('SELECT status FROM workflows WHERE workflow_id=?',(dep,)).fetchone()
     if not wr or wr['status']!='COMPLETED': continue
    if d['schedule_type']=='conditional':
     from task_conditions import evaluate
     cond=tpl.get('condition')
     if not cond or not evaluate(cond,tpl.get('metrics') or {}): continue
    rev=None if d['use_latest_revision'] else d['project_revision'];snap=ps.get(d['project_id'],rev)
    if not snap:continue
    wf=create_standard(self.s,project_id=snap['project_id'],project_revision=snap['revision'],project=snap['project'],mode=tpl.get('mode','dry'),confirm_live=bool(tpl.get('confirm_live')),cost_mode=tpl.get('cost_mode'),budget_usd=tpl.get('budget_usd'),verification=bool(tpl.get('verification')),idempotency_key=idem,workflow_metadata={'schedule_id':d['schedule_id'],'schedule_due_at':due_at,'schedule_type':d['schedule_type'],'use_latest_revision':bool(d['use_latest_revision']),'scheduled_project_revision':snap['revision'],'misfire_policy':d['misfire_policy']})
    oid='OCC-'+uuid.uuid4().hex[:15]
    with self.s.cx() as c:
     c.execute('INSERT INTO schedule_occurrences VALUES(?,?,?,?,?,?,?)',(oid,d['schedule_id'],due_at,wf['workflow_id'],'CREATED',idem,now()))
     if d['schedule_type'] in {'one_time','after_workflow','conditional'}:nxt=None
     else:
      # run_once collapses missed occurrences by advancing from now; catch_up advances from due time.
      base=now_dt if d['misfire_policy']=='run_once' else _parse_iso(due_at);nxt=_fmt(_next_simple(d['schedule_expr'],base))
     c.execute('UPDATE schedules SET last_run_at=?,next_run_at=?,updated_at=? WHERE schedule_id=?',(due_at,nxt,now(),d['schedule_id']))
    made.append(wf['workflow_id'])
  finally:ps.close()
  return made
