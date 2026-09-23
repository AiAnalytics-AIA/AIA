from __future__ import annotations
import argparse,os,subprocess,sys,time,uuid,signal
from pathlib import Path
from job_store import JobStore, now
from research_os_config import WORKER_POLL_S
from edition_config import build_version
from spawn_env import safe_spawn_env

ROOT=Path(__file__).resolve().parent
CANCEL_GRACE_S=float(os.environ.get('NPC_CANCEL_GRACE_S','15'))
KILL_GRACE_S=float(os.environ.get('NPC_CANCEL_KILL_GRACE_S','5'))


def _spawn_worker(job_id:str, worker_id:str):
    kwargs={'cwd':ROOT,'env':safe_spawn_env()}
    if os.name=='nt':
        kwargs['creationflags']=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)|getattr(subprocess,'CREATE_NO_WINDOW',0)
    else:
        kwargs['start_new_session']=True
    return subprocess.Popen([sys.executable,'worker_job.py','--job-id',job_id,'--worker-id',worker_id],**kwargs)

def _terminate_worker_tree(p, force=False):
    if not p or p.poll() is not None:return
    try:
        if os.name=='nt':
            args=['taskkill','/PID',str(p.pid),'/T']+(['/F'] if force else [])
            subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8)
        else:
            os.killpg(p.pid, signal.SIGKILL if force else signal.SIGTERM)
    except Exception:
        try:p.kill() if force else p.terminate()
        except Exception:pass


def _force_recover_after_child_exit(store:JobStore, job_id:str):
    """Resolve a child that exited without committing a terminal state.

    For cancelled work we can safely finalize CANCELLED. For every other RUNNING
    job expire its lease immediately and reuse the normal recovery logic, which
    already handles uncertain paid external calls conservatively.
    """
    j=store.get_job(job_id)
    if not j or j.get('status')!='RUNNING': return
    if j.get('cancel_requested'):
        store.transition(job_id,'CANCELLED',message='child exited after cancel request',force=True)
        return
    with store.cx() as c:
        c.execute("UPDATE jobs SET lease_until='1970-01-01T00:00:00',heartbeat_at=?,updated_at=? WHERE job_id=? AND status='RUNNING'",(now(),now(),job_id))
    store.event(job_id,'CHILD_EXIT','worker child exited before terminal state; starting immediate recovery',{'return_code':'unexpected'},'WARN')
    store.recover_expired()


def _enforce_cancellation(store:JobStore, children:dict):
    now_t=time.time()
    for jid,meta in list(children.items()):
        p=meta['process']
        if p.poll() is not None: continue
        if not store.cancel_requested(jid):
            meta.pop('cancel_seen_at',None);meta.pop('terminate_at',None);continue
        seen=meta.setdefault('cancel_seen_at',now_t)
        if now_t-seen>=CANCEL_GRACE_S and 'terminate_at' not in meta:
            try:_terminate_worker_tree(p);meta['terminate_at']=now_t;store.event(jid,'CANCEL_TERMINATE','cooperative cancel timeout; terminating worker process tree',{'grace_s':CANCEL_GRACE_S},'WARN')
            except Exception as e:store.event(jid,'CANCEL_TERMINATE_ERROR',str(e),{},'WARN')
        term=meta.get('terminate_at')
        if term is not None and p.poll() is None and now_t-term>=KILL_GRACE_S:
            try:_terminate_worker_tree(p,force=True);meta['kill_at']=now_t;store.event(jid,'CANCEL_KILL','terminate timeout; killing worker process tree',{'kill_grace_s':KILL_GRACE_S},'WARN')
            except Exception as e:store.event(jid,'CANCEL_KILL_ERROR',str(e),{},'WARN')


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--once',action='store_true');ap.add_argument('--idle-exit',type=float,default=0);ap.add_argument('--concurrency',type=int,default=int(os.environ.get('NPC_WORKER_CONCURRENCY','2')));a=ap.parse_args()
    concurrency=max(1,min(8,int(a.concurrency)));wid='WKR-'+uuid.uuid4().hex[:10];s=JobStore();idle=time.time();children={}
    # Publish liveness immediately, before importing/initializing the scheduler.
    # Cold Windows/Python starts can be slower because of antivirus and first imports.
    s.worker_heartbeat(wid,os.getpid(),'STARTING',None,{'version':build_version(),'concurrency':concurrency,'phase':'scheduler_init'})
    try:
        from scheduler import Scheduler
        sched=Scheduler(s)
        s.recover_expired()
        s.worker_heartbeat(wid,os.getpid(),'READY',None,{'version':build_version(),'concurrency':concurrency,'phase':'ready'})
        while True:
            _enforce_cancellation(s,children)
            # Reap finished children and immediately reconcile any incomplete DB state.
            for jid,meta in list(children.items()):
                p=meta['process']
                if p.poll() is not None:
                    _force_recover_after_child_exit(s,jid)
                    s.queue_ready_jobs(meta['workflow_id']);children.pop(jid,None);idle=time.time()
            active=','.join(children.keys()) or None
            s.worker_heartbeat(wid,os.getpid(),'BUSY' if children else 'READY',active,{'version':build_version(),'concurrency':concurrency,'active_jobs':list(children)})
            sched.tick();s.recover_expired();s.requeue_capacity_waiters();s.queue_ready_jobs()
            claimed=0
            while len(children)<concurrency:
                job=s.claim(wid)
                if not job:break
                try:
                    p=_spawn_worker(job['job_id'],wid)
                except OSError as exc:
                    s.event(job['job_id'],'SPAWN_FAILED','worker subprocess spawn failed',{'errno':getattr(exc,'errno',None),'winerror':getattr(exc,'winerror',None),'error':str(exc)[:700]},'ERROR')
                    with s.cx() as c:
                        c.execute("UPDATE jobs SET status='QUEUED',lease_owner=NULL,lease_until=NULL,attempt=CASE WHEN attempt>0 THEN attempt-1 ELSE 0 END,updated_at=? WHERE job_id=?",(now(),job['job_id']))
                    time.sleep(2);break
                children[job['job_id']]={'process':p,'workflow_id':job['workflow_id']};claimed+=1;idle=time.time()
            if a.once and not children and claimed==0:return 0
            if a.idle_exit and not children and time.time()-idle>a.idle_exit:return 0
            time.sleep(WORKER_POLL_S)
    except KeyboardInterrupt:return 0
    finally:
        for meta in children.values():
            p=meta['process']
            if p.poll() is None:
                try:_terminate_worker_tree(p);p.wait(timeout=3)
                except Exception:
                    try:_terminate_worker_tree(p,force=True)
                    except Exception:pass
        s.worker_heartbeat(wid,os.getpid(),'STOPPED',None,{'version':build_version(),'concurrency':concurrency})
if __name__=='__main__':raise SystemExit(main())
