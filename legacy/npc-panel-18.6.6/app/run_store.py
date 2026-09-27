"""Persistent study/run history and reusable question bank."""
from __future__ import annotations
import sqlite3,json,time,hashlib
from pathlib import Path
from typing import Any

SCHEMA='''
CREATE TABLE IF NOT EXISTS studies(id TEXT PRIMARY KEY,name TEXT,client TEXT,research_question TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,text TEXT,type TEXT,schema_json TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,study_id TEXT,created_at TEXT,system_fingerprint TEXT,panel_version TEXT,model TEXT,mode TEXT,seed INTEGER,n INTEGER,cost_usd REAL,run_dir TEXT,metadata_json TEXT);
CREATE TABLE IF NOT EXISTS run_questions(run_id TEXT,question_id TEXT,result_json TEXT,PRIMARY KEY(run_id,question_id));
'''

def stable_question_id(text:str,typ:str="")->str:return "Q_"+hashlib.sha256((typ+"|"+" ".join(text.lower().split())).encode()).hexdigest()[:16]
class RunStore:
    def __init__(self,path="data/run_store.sqlite"):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.cx=sqlite3.connect(self.path);self.cx.executescript(SCHEMA)
        cols={r[1] for r in self.cx.execute("PRAGMA table_info(runs)").fetchall()}
        for name,typ in [("workflow_id","TEXT"),("job_id","TEXT"),("provider","TEXT"),("provider_policy","TEXT"),("response_mode","TEXT"),("persona_mode","TEXT"),("prompt_hash","TEXT"),("system_hash","TEXT")]:
            if name not in cols:self.cx.execute(f"ALTER TABLE runs ADD COLUMN {name} {typ}")
        self.cx.commit()
    def close(self):self.cx.close()
    def record(self,result:dict[str,Any],*,study_id:str|None=None,client=""):
        rid=result.get("run_id") or hashlib.sha256(f"{time.time()}".encode()).hexdigest()[:16]
        sid=study_id or "STUDY_"+hashlib.sha256(str(result.get("nazev","study")).encode()).hexdigest()[:12]
        self.cx.execute("INSERT OR IGNORE INTO studies VALUES(?,?,?,?,?)",(sid,result.get("nazev",sid),client,"",time.strftime("%Y-%m-%dT%H:%M:%S")))
        fp=""
        try:
            from system_fingerprint import current_system_sha256
            fp=current_system_sha256(result.get("panel_path") or None)
        except Exception:
            fp=""
        meta={k:v for k,v in result.items() if k not in {"detail","vysledky"}}
        self.cx.execute("""INSERT OR REPLACE INTO runs(id,study_id,created_at,system_fingerprint,panel_version,model,mode,seed,n,cost_usd,run_dir,metadata_json,workflow_id,job_id,provider,provider_policy,response_mode,persona_mode,prompt_hash,system_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
            rid,sid,time.strftime("%Y-%m-%dT%H:%M:%S"),fp,
            result.get("panel_version",result.get("release","")),result.get("model",""),result.get("mode",""),
            result.get("seed"),result.get("n_dotazano"),result.get("naklady_usd"),result.get("run_dir",""),
            json.dumps(meta,ensure_ascii=False,default=str),result.get("workflow_id"),result.get("job_id"),result.get("provider") or meta.get("provider"),result.get("provider_policy") or meta.get("provider_policy"),result.get("response_mode") or meta.get("response_mode"),result.get("persona_mode") or meta.get("persona_mode"),result.get("prompt_hash") or meta.get("prompt_template_sha256"),result.get("system_hash") or meta.get("system_hash")))
        for q in result.get("otazky",[]):
            qid=stable_question_id(q.get("text",""),q.get("typ",""));self.cx.execute("INSERT OR IGNORE INTO questions VALUES(?,?,?,?,?)",(qid,q.get("text",""),q.get("typ",""),json.dumps(q,ensure_ascii=False),time.strftime("%Y-%m-%dT%H:%M:%S")))
            self.cx.execute("INSERT OR REPLACE INTO run_questions VALUES(?,?,?)",(rid,qid,json.dumps(result.get("vysledky",{}).get(q.get("id"),{}),ensure_ascii=False,default=str)))
        self.cx.commit();return rid


    def list_runs(self, limit:int=100) -> list[dict[str,Any]]:
        rows=self.cx.execute("""SELECT r.id,r.study_id,s.name,r.created_at,r.system_fingerprint,r.panel_version,r.model,r.mode,r.seed,r.n,r.cost_usd,r.run_dir,r.metadata_json,
                                      (SELECT COUNT(*) FROM run_questions rq WHERE rq.run_id=r.id) AS question_count
                               FROM runs r LEFT JOIN studies s ON s.id=r.study_id
                               ORDER BY r.created_at DESC LIMIT ?""",(int(limit),)).fetchall()
        cols=["run_id","study_id","study_name","created_at","system_fingerprint","panel_version","model","mode","seed","n","cost_usd","run_dir","metadata_json","question_count"]
        out=[]
        for row in rows:
            d=dict(zip(cols,row))
            try:d["metadata"]=json.loads(d.pop("metadata_json") or "{}")
            except Exception:d["metadata"]={};d.pop("metadata_json",None)
            out.append(d)
        return out

    def latest_fingerprint(self) -> str:
        row=self.cx.execute("SELECT system_fingerprint FROM runs WHERE system_fingerprint<>'' ORDER BY created_at DESC LIMIT 1").fetchone()
        return row[0] if row else ""

    def question_history(self, question_id: str, limit: int=200) -> list[dict[str,Any]]:
        """Return comparable historical results for one stable question id."""
        rows=self.cx.execute("""SELECT rq.run_id,r.created_at,r.system_fingerprint,r.panel_version,r.model,r.mode,r.seed,r.n,r.cost_usd,rq.result_json
                               FROM run_questions rq JOIN runs r ON r.id=rq.run_id
                               WHERE rq.question_id=? ORDER BY r.created_at DESC LIMIT ?""",
                             (question_id,int(limit))).fetchall()
        cols=["run_id","created_at","system_fingerprint","panel_version","model","mode","seed","n","cost_usd","result"]
        out=[]
        for row in rows:
            d=dict(zip(cols,row));
            try:d["result"]=json.loads(d["result"])
            except Exception:pass
            out.append(d)
        return out

    def list_questions(self, limit:int=500) -> list[dict[str,Any]]:
        rows=self.cx.execute("SELECT id,text,type,created_at FROM questions ORDER BY created_at DESC LIMIT ?",(int(limit),)).fetchall()
        return [{"id":r[0],"text":r[1],"type":r[2],"created_at":r[3]} for r in rows]
