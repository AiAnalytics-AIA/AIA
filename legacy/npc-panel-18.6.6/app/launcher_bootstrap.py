#!/usr/bin/env python3
"""NPC Panel Research OS bootstrap/supervisor.

- creates/reuses a validated local Python runtime in .npc_runtime;
- optionally bootstraps Claude Code in the Claude edition;
- starts a persistent Research OS worker separately from the HTTP UI server;
- browser lifetime is independent of worker lifetime;
- stale .venv from old releases is ignored.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time, traceback, webbrowser, urllib.request
from pathlib import Path
from spawn_env import safe_spawn_env
from edition_config import build_version
ROOT=Path(__file__).resolve().parent
LOG_DIR=ROOT/'logs';LOG_DIR.mkdir(exist_ok=True)
LOG=LOG_DIR/'startup.log';WORKER_LOG=LOG_DIR/'worker.log';SERVER_LOG=LOG_DIR/'server.log';REQ=ROOT/'requirements.txt';RUNTIME_ENV=ROOT/'.npc_runtime';RUNTIME_PY=Path(sys.executable)
LAUNCHER_LOCK=ROOT/'data'/'launcher.lock'; SERVER_STATE=ROOT/'data'/'server_state.json'
CORE=('pandas','numpy','openpyxl','scipy','sklearn','docx','pypdf')

def log(msg):
 line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}";print(line,flush=True)
 with LOG.open('a',encoding='utf-8') as f:f.write(line+'\n')
def run(cmd,check=False,stream=False,timeout=None):
 log('$ '+' '.join(map(str,cmd)));env=safe_spawn_env();env.setdefault('PYTHONUTF8','1');env.setdefault('PYTHONIOENCODING','utf-8')
 if stream:
  with LOG.open('a',encoding='utf-8') as f:
   p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env)
   try:
    for line in p.stdout or []: print(line,end='');f.write(line);f.flush()
    rc=p.wait(timeout=timeout)
   except Exception:
    p.kill();raise
 else:
  with LOG.open('a',encoding='utf-8') as f:rc=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,timeout=timeout).returncode
 log(f'return_code={rc}')
 if check and rc:raise RuntimeError(f"Příkaz selhal ({rc}): {' '.join(map(str,cmd))}")
 return rc
def _pid_alive(pid:int)->bool:
 try:
  pid=int(pid)
  if pid<=0:return False
  if os.name=='nt':
   import ctypes
   PROCESS_QUERY_LIMITED_INFORMATION=0x1000
   h=ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
   if h:
    ctypes.windll.kernel32.CloseHandle(h);return True
   return False
  os.kill(pid,0);return True
 except Exception:return False

def _port_8766_health()->dict|None:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8766/health',timeout=1.2) as r:
   if 200<=int(r.status)<300:
    data=json.loads(r.read().decode('utf-8','replace') or '{}')
    return data if isinstance(data,dict) else {'status':'ok'}
 except Exception:pass
 return None

def _live_server_url()->str|None:
 try:
  d=json.loads(SERVER_STATE.read_text(encoding='utf-8'));url=str(d.get('url') or '')
  if not url.startswith(('http://127.0.0.1:','http://localhost:')):return None
  with urllib.request.urlopen(url+'/health',timeout=1.5) as r:
   if 200<=int(r.status)<300:return url
 except Exception:pass
 return None

def _worker_heartbeat_fresh(pid:int,max_age_s:float=45.0)->bool:
 """Use the durable worker heartbeat, not a fragile Windows PID equality.

 The venv/launcher process PID can differ from the Python PID persisted by the daemon
 on some Windows installations. 17.8.7 therefore restarted a healthy worker every
 ~110 s. A single-instance launcher owns this DB, so the freshest non-STOPPED worker
 row is the correct liveness signal.
 """
 try:
  import sqlite3
  db=ROOT/'data'/'research_os.sqlite'
  if not db.is_file():return False
  c=sqlite3.connect(db,timeout=1.5)
  r=c.execute("SELECT heartbeat_at FROM worker_state WHERE status!='STOPPED' ORDER BY heartbeat_at DESC LIMIT 1").fetchone();c.close()
  if not r:return False
  ts=time.mktime(time.strptime(str(r[0])[:19],'%Y-%m-%dT%H:%M:%S'))
  return time.time()-ts<float(max_age_s)
 except Exception:return False

def _worker_has_fresh_running_job(pid:int,max_age_s:float=45.0)->bool:
 """Any fresh RUNNING-job heartbeat proves useful work is alive."""
 try:
  import sqlite3
  db=ROOT/'data'/'research_os.sqlite'
  if not db.is_file():return False
  c=sqlite3.connect(db,timeout=1.5)
  r=c.execute("SELECT heartbeat_at FROM jobs WHERE status='RUNNING' AND heartbeat_at IS NOT NULL ORDER BY heartbeat_at DESC LIMIT 1").fetchone();c.close()
  if not r:return False
  ts=time.mktime(time.strptime(str(r[0])[:19],'%Y-%m-%dT%H:%M:%S'))
  return time.time()-ts<float(max_age_s)
 except Exception:return False

def _acquire_launcher_lock()->bool:
 LAUNCHER_LOCK.parent.mkdir(parents=True,exist_ok=True)
 for _ in range(2):
  try:
   fd=os.open(LAUNCHER_LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
   os.write(fd,json.dumps({'pid':os.getpid(),'started_at':time.time()}).encode());os.close(fd);return True
  except FileExistsError:
   try:d=json.loads(LAUNCHER_LOCK.read_text(encoding='utf-8'));pid=int(d.get('pid') or 0)
   except Exception:pid=0
   if not _pid_alive(pid):
    try:LAUNCHER_LOCK.unlink()
    except Exception:return False
    continue
   return False
 return False

def _existing_instance():
 # A second double-click should open/reuse the same server, never spawn another worker.
 url=_live_server_url()
 if url:return url
 for _ in range(40):
  time.sleep(.5);url=_live_server_url()
  if url:return url
 return None

def runtime_python():return RUNTIME_ENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def py_ok(py):return py.is_file() and (RUNTIME_ENV/'pyvenv.cfg').is_file() and run([str(py),'-c','import sys;print(sys.executable)'])==0
def imports_ok(py):return run([str(py),'-c','; '.join(f'import {x}' for x in CORE)+"; print('core-deps-ok')"])==0
def ensure_runtime(force=False):
 global RUNTIME_PY
 if sys.version_info<(3,11):raise RuntimeError('NPC Panel vyžaduje Python 3.11+.')
 log(f'bootstrap_python={sys.executable} version={sys.version.split()[0]}')
 # use complete base Python directly; otherwise isolated runtime
 if not force and imports_ok(Path(sys.executable)):
  RUNTIME_PY=Path(sys.executable);log('Používám základní Python — CORE dependencies jsou dostupné.');return
 if force or (RUNTIME_ENV.exists() and not py_ok(runtime_python())):
  log('Mažu neplatný .npc_runtime.');shutil.rmtree(RUNTIME_ENV,ignore_errors=True)
 if not py_ok(runtime_python()):
  run([sys.executable,'-m','venv','--system-site-packages',str(RUNTIME_ENV)],check=True)
 RUNTIME_PY=runtime_python()
 if not imports_ok(RUNTIME_PY):
  log('První start: instaluji Python závislosti. Průběh je vidět zde i v logs/startup.log.')
  run([str(RUNTIME_PY),'-m','pip','install','--disable-pip-version-check','--prefer-binary','--timeout','30','--retries','3','-r',str(REQ)],check=True,stream=True)
 if not imports_ok(RUNTIME_PY):raise RuntimeError('Po instalaci chybí CORE Python závislosti.')
def edition():
 try:return json.loads((ROOT/'BUILD_EDITION.json').read_text(encoding='utf-8'))
 except Exception:return {'edition':'API_ONLY','claude_code_enabled':False}
def claude_status_note():
    """Never make Claude installation/login a prerequisite for opening NPC."""
    if not edition().get('claude_code_enabled'):
        return
    try:
        from claude_code_setup import auth_status
        st=auth_status()
        if st.get('subscription_verified'):
            log('Claude Code subscription READY.')
        else:
            log('Claude Code subscription zatím není READY. NPC se přesto spustí; setup poběží odděleně a provider zůstane fail-closed.')
    except Exception as e:
        log('Claude Code status check nebyl dostupný: '+repr(e)+'. NPC se přesto spustí.')

def spawn_claude_setup(interactive=True):
    """Run optional Claude installation/login outside the supervisor console/process.

    A failure here must never terminate the UI server or Research OS worker.
    """
    if not edition().get('claude_code_enabled') or not interactive:
        return None
    try:
        env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
        kwargs={'cwd':ROOT,'env':env}
        if os.name=='nt':
            # Use the persistent wrapper, not a raw Python child. The dedicated cmd /k
            # window remains visible after SUCCESS or ERROR so the user always sees
            # auth status and the claude setup log path. It is fully independent from
            # the NPC supervisor/worker processes.
            wrapper=ROOT/'INSTALOVAT_CLAUDE_CODE.bat'
            comspec=os.environ.get('COMSPEC') or 'cmd.exe'
            cmd=[comspec,'/d','/k',str(wrapper)]
            kwargs['creationflags']=getattr(subprocess,'CREATE_NEW_CONSOLE',0)
        else:
            # Non-Windows validation environments do not have a real Claude OAuth flow.
            return None
        p=subprocess.Popen(cmd,**kwargs)
        log(f'Claude Code setup spuštěn odděleně pid={p.pid}; jeho pád neukončí NPC.')
        return p
    except Exception as e:
        log('Claude Code setup se nepodařilo otevřít: '+repr(e)+'. NPC pokračuje bez něj.')
        return None

def preflight():
 if run([str(RUNTIME_PY),'runtime_diagnostic.py','--import-smoke'])!=0:return False
 if run([str(RUNTIME_PY),'backend_smoketest.py'])!=0:return False
 return True
def wait_worker(timeout=None,pid=None,process=None):
 # A cold Windows start (especially immediately after pip install or with AV scanning)
 # can take tens of seconds. Liveness is enough to open the UI; READY can follow.
 if timeout is None: timeout=float(os.environ.get('NPC_WORKER_START_TIMEOUT_S','90'))
 end=time.time()+max(5.0,float(timeout));last_status=None
 while time.time()<end:
  if process is not None and process.poll() is not None:
   return False,last_status,'exited'
  try:
   import sqlite3
   db=ROOT/'data'/'research_os.sqlite'
   if db.is_file():
    c=sqlite3.connect(db,timeout=2)
    # Windows venv/python redirectors can expose a supervisor PID different from
    # os.getpid() stored by worker_daemon. Single-instance launcher => newest active
    # durable heartbeat is authoritative; do not wait 90 s on brittle PID equality.
    r=c.execute("SELECT heartbeat_at,status FROM worker_state WHERE status!='STOPPED' ORDER BY heartbeat_at DESC LIMIT 1").fetchone();c.close()
    if r:
     last_status=str(r[1] or '')
     ts=time.mktime(time.strptime(str(r[0])[:19],'%Y-%m-%dT%H:%M:%S'))
     if time.time()-ts<20:
      return True,last_status,'heartbeat'
  except Exception:pass
  time.sleep(.35)
 if process is not None and process.poll() is None:
  # Do not kill the entire desktop app just because first worker initialization is slow.
  return True,last_status or 'STARTING','alive_without_heartbeat'
 return False,last_status,'timeout'

def _tail(path:Path,lines=30)->str:
 try:return '\n'.join(path.read_text(encoding='utf-8',errors='replace').splitlines()[-int(lines):])
 except Exception:return ''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repair',action='store_true');ap.add_argument('--setup-only',action='store_true');ap.add_argument('--noninteractive-claude',action='store_true');a=ap.parse_args()
 LOG.write_text(f"NPC PANEL {build_version()} RESEARCH OS STARTUP — {time.strftime('%Y-%m-%d %H:%M:%S')}\n",encoding='utf-8');worker=None;server=None;wf=None;sf=None;own_lock=False
 if not _acquire_launcher_lock():
  url=_existing_instance()
  if url:
   log('NPC Panel už běží: '+url);webbrowser.open(url);return 0
  log('NPC Panel už startuje v jiném procesu. Druhou instanci nespouštím.');return 0
 own_lock=True
 def start_worker():
  nonlocal wf
  if wf is None:wf=WORKER_LOG.open('a',encoding='utf-8')
  p=subprocess.Popen([str(RUNTIME_PY),'-u','worker_daemon.py','--concurrency','2'],cwd=ROOT,stdout=wf,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
  ok,status,reason=wait_worker(pid=p.pid,process=p)
  if not ok:
   tail=_tail(WORKER_LOG,40)
   if tail: log('Poslední řádky worker.log:\n'+tail)
   raise RuntimeError(f'Research OS worker skončil během startu (status={status or "unknown"}, reason={reason}, code={p.poll()}). Viz logs/worker.log.')
  if reason=='alive_without_heartbeat':
   log(f'Research OS worker stále startuje pid={p.pid}; UI spouštím bez blokování. Command Center ukáže stav workeru, jakmile pošle heartbeat.')
  else:
   log(f'Research OS worker {status or "READY"} pid={p.pid}')
  return p
 def start_server():
  existing=_port_8766_health()
  if existing:
   rel=str(existing.get('release') or 'jiná/neznámá verze')
   raise RuntimeError('Port 8766 už používá běžící NPC Panel ('+rel+'). Zavřete staré černé runtime okno NPC Panelu a spusťte tuto verzi znovu.')
  sf=SERVER_LOG.open('a',encoding='utf-8')
  p=subprocess.Popen([str(RUNTIME_PY),'-u','ui_server.py','--host','127.0.0.1','--port','8766','--no-open'],cwd=ROOT,stdout=sf,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'})
  deadline=time.time()+60; url=None
  while time.time()<deadline:
   if p.poll() is not None:
    sf.flush(); tail=_tail(SERVER_LOG,50); sf.close()
    if tail: log('Poslední řádky server.log:\n'+tail)
    raise RuntimeError(f'HTTP UI server skončil během startu (code={p.returncode}).')
   url=_live_server_url()
   if url: return p,sf,url
   time.sleep(.25)
  try:p.terminate()
  except Exception:pass
  sf.close(); raise RuntimeError('HTTP UI server se do 60 s nestal READY. Viz logs/server.log.')
 try:
  ensure_runtime(a.repair)
  envfile=ROOT/'.env'
  if not envfile.exists() and (ROOT/'.env.example').exists():shutil.copy2(ROOT/'.env.example',envfile);log('Vytvořen .env z .env.example')
  claude_status_note()
  if not preflight():raise RuntimeError('Produktový preflight selhal; viz konkrétní chyba v logs/startup.log.')
  worker=start_worker()
  if a.setup_only:
   log('Setup + backend + worker preflight: OK');return 0
  log('Spouštím HTTP UI server…')
  server,sf,url=start_server()
  # The supervisor owns browser opening and keeps a watchdog around the server.
  log('NPC Panel READY: '+url)
  opened=False
  try: opened=bool(webbrowser.open(url,new=2))
  except Exception as e: log('Výchozí prohlížeč se nepodařilo otevřít: '+repr(e))
  if opened: log('Otevírám panel ve výchozím prohlížeči.')
  else: log('Prohlížeč se neotevřel automaticky. Otevřete ručně: '+url)
  # Claude Code installation/login is an explicit Settings action. Normal NPC start
  # must never surprise the user with a second console window.
  if os.environ.get('NPC_AUTO_CLAUDE_SETUP')=='1' and not a.noninteractive_claude:
   spawn_claude_setup(interactive=True)
  worker_restarts=[];server_restarts=[];server_health_misses=0;worker_health_misses=0;last_server_health_check=0.0;last_worker_health_check=0.0;last_worker_defer_log=0.0
  while True:
   now_t=time.time()
   if server.poll() is None and now_t-last_server_health_check>=3.0:
    last_server_health_check=now_t
    if _port_8766_health():
     server_health_misses=0
    else:
     server_health_misses+=1
     if server_health_misses>=3:
      log('HTTP backend proces žije, ale /health 3× po sobě neodpověděl; restartuji UI backend. Durable workflow a worker pokračují.')
      try:server.terminate();server.wait(timeout=5)
      except Exception:
       try:server.kill();server.wait(timeout=3)
       except Exception:pass
      if sf:
       try:sf.flush();sf.close()
       except Exception:pass
       sf=None
      t=time.time();server_restarts=[x for x in server_restarts if t-x<300];server_restarts.append(t)
      if len(server_restarts)>5:raise RuntimeError('HTTP backend byl nereagující více než 5× během 5 minut. Viz logs/server.log.')
      server,sf,url=start_server();server_health_misses=0;log('HTTP backend watchdog: znovu READY '+url)
   if worker.poll() is None and now_t-last_worker_health_check>=5.0:
    last_worker_health_check=now_t
    if _worker_heartbeat_fresh(worker.pid):
     worker_health_misses=0
    elif _worker_has_fresh_running_job(worker.pid):
     worker_health_misses=0
     if now_t-last_worker_defer_log>=60:
      last_worker_defer_log=now_t
      log('Worker scheduler heartbeat je opožděný, ale RUNNING job má čerstvý heartbeat; restart odkládám, aby se živý běh nepřerušil.')
    else:
     worker_health_misses+=1
     if worker_health_misses>=4:
      log('Worker proces žije bez čerstvého scheduler ani job heartbeat; restartuji durable worker. Rozpracovaný job obnoví lease/checkpoint recovery.')
      try:worker.terminate();worker.wait(timeout=6)
      except Exception:
       try:worker.kill();worker.wait(timeout=3)
       except Exception:pass
      worker=start_worker();worker_health_misses=0;last_worker_health_check=time.time()
   if server.poll() is not None:
    if sf:
     try: sf.flush(); sf.close()
     except Exception: pass
     sf=None
    t=time.time(); server_restarts=[x for x in server_restarts if t-x<300]; server_restarts.append(t)
    if len(server_restarts)>5:
     raise RuntimeError('HTTP backend spadl více než 5× během 5 minut. Viz logs/server.log.')
    log(f'HTTP backend skončil kódem {server.returncode}; automaticky jej obnovuji. Rozpracované joby zůstávají v durable store.')
    time.sleep(1); server,sf,url=start_server(); log('HTTP backend znovu READY: '+url)
   if worker.poll() is not None:
    t=time.time();worker_restarts=[x for x in worker_restarts if t-x<120];worker_restarts.append(t)
    if len(worker_restarts)>5:
     log('VAROVÁNÍ: worker padá opakovaně; další automatický restart na 120 s pozastaven. UI zůstává dostupné.')
     time.sleep(10);worker_restarts=[]
    else:
     log(f'Worker skončil kódem {worker.returncode}; obnovuji durable worker.');time.sleep(1);worker=start_worker()
   time.sleep(1)
 except Exception as e:
  log('STARTUP ERROR: '+repr(e))
  with LOG.open('a',encoding='utf-8') as f:traceback.print_exc(file=f)
  print('\nNPC Panel se nespustil. Log: '+str(LOG));return 1
 finally:
  if server and server.poll() is None:
   try:server.terminate();server.wait(timeout=5)
   except Exception:
    try:server.kill()
    except Exception:pass
  if worker and worker.poll() is None:
   try:worker.terminate();worker.wait(timeout=5)
   except Exception:
    try:worker.kill()
    except Exception:pass
  if wf:wf.close()
  if sf:
   try:sf.close()
   except Exception:pass
  # ui_server may be terminated by the supervisor (Windows TerminateProcess does not run Python finally).
  # Remove only this installation's state file after its child server is gone; stale files are never authoritative.
  if server is not None and server.poll() is not None:
   try:SERVER_STATE.unlink(missing_ok=True)
   except Exception:pass
  if own_lock:
   try:LAUNCHER_LOCK.unlink(missing_ok=True)
   except Exception:pass
if __name__=='__main__':raise SystemExit(main())
