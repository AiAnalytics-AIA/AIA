from __future__ import annotations
import os

WINDOWS_ENV_WARN=28000

def _norm(p:str)->str:
    try:return os.path.normcase(os.path.normpath(p))
    except Exception:return p.lower()

def safe_spawn_env(base:dict[str,str]|None=None)->dict[str,str]:
    """Return a deduplicated Windows-safe environment for subprocesses.

    Keeps normal variables, but prevents a duplicated PATH from making CreateProcess
    fail with WinError 8 because the environment block exceeded Windows limits.
    """
    env=dict(base or os.environ)
    if os.name!='nt':return env
    path=str(env.get('PATH') or '')
    parts=[x for x in path.split(os.pathsep) if x]
    seen=set();dedup=[]
    for x in parts:
        k=_norm(x)
        if k in seen:continue
        seen.add(k);dedup.append(x)
    env['PATH']=os.pathsep.join(dedup)
    def block_size(d):return sum(len(str(k))+len(str(v))+2 for k,v in d.items())+1
    if block_size(env)>WINDOWS_ENV_WARN:
        # Keep all normal variables; trim only PATH first. This is a last-resort guard.
        cur=[]
        for x in dedup:
            trial=os.pathsep.join(cur+[x])
            env['PATH']=trial
            if block_size(env)>WINDOWS_ENV_WARN:break
            cur.append(x)
        env['PATH']=os.pathsep.join(cur)
    return env
