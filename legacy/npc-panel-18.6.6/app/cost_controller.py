from __future__ import annotations
import json,uuid
from job_store import JobStore,now
class WorkflowBudgetExceeded(RuntimeError):pass
class CostController:
 def __init__(self,store:JobStore,workflow_id:str):self.s=store;self.wid=workflow_id
 def snapshot(self):
  with self.s.cx() as c:
   w=c.execute('SELECT budget_usd,cost_mode FROM workflows WHERE workflow_id=?',(self.wid,)).fetchone()
   actual=float(c.execute('SELECT COALESCE(SUM(actual_cost_usd),0) FROM jobs WHERE workflow_id=?',(self.wid,)).fetchone()[0] or 0)
   reserved=float(c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM cost_reservations WHERE workflow_id=? AND status='RESERVED'",(self.wid,)).fetchone()[0] or 0)
  return {'budget_usd':None if not w else w['budget_usd'],'cost_mode':None if not w else w['cost_mode'],'actual_spend_usd':actual,'reserved_spend_usd':reserved,'remaining_usd':None if not w or w['budget_usd'] is None else max(0,float(w['budget_usd'])-actual-reserved)}
 def reserve(self,job_id:str,amount:float):
  amount=max(0,float(amount));rid='COST-'+uuid.uuid4().hex[:14]
  # One IMMEDIATE transaction protects the workflow cap from concurrent reservations.
  with self.s.cx() as c:
   c.execute('BEGIN IMMEDIATE')
   w=c.execute('SELECT budget_usd,cost_mode FROM workflows WHERE workflow_id=?',(self.wid,)).fetchone()
   if not w: c.rollback(); raise KeyError(self.wid)
   actual=float(c.execute('SELECT COALESCE(SUM(actual_cost_usd),0) FROM jobs WHERE workflow_id=?',(self.wid,)).fetchone()[0] or 0)
   reserved=float(c.execute("SELECT COALESCE(SUM(amount_usd),0) FROM cost_reservations WHERE workflow_id=? AND status='RESERVED'",(self.wid,)).fetchone()[0] or 0)
   cap=w['budget_usd'];remaining=None if cap is None else max(0,float(cap)-actual-reserved)
   if cap is not None and actual+reserved+amount>float(cap)+1e-12:
    c.rollback();raise WorkflowBudgetExceeded(f'WORKFLOW_BUDGET_CAP: requested ${amount:.4f}; remaining ${remaining:.4f}')
   c.execute('INSERT INTO cost_reservations VALUES(?,?,?,?,?,?,?)',(rid,self.wid,job_id,amount,'RESERVED',now(),None));c.commit()
  return rid
 def settle(self,reservation_id:str,actual:float):
  actual=max(0,float(actual))
  with self.s.cx() as c:
   r=c.execute('SELECT job_id,amount_usd,status FROM cost_reservations WHERE reservation_id=?',(reservation_id,)).fetchone()
   if not r:raise KeyError(reservation_id)
   if r['status']!='RESERVED':return
   c.execute("UPDATE cost_reservations SET status='SETTLED',settled_at=? WHERE reservation_id=?",(now(),reservation_id));c.execute('UPDATE jobs SET actual_cost_usd=actual_cost_usd+?,updated_at=? WHERE job_id=?',(actual,now(),r['job_id']))
 def cancel(self,reservation_id:str):
  with self.s.cx() as c:c.execute("UPDATE cost_reservations SET status='CANCELLED',settled_at=? WHERE reservation_id=? AND status='RESERVED'",(now(),reservation_id))
