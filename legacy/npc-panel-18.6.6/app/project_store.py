"""Persistent project / revision / stage / artifact source of truth.

17.9.0 extends the original immutable revision store without breaking its public
save/get/list API.  Existing 17.8.x databases are migrated in place additively.
"""
from __future__ import annotations
import hashlib, json, sqlite3, time, uuid, zipfile
from pathlib import Path
from typing import Any
from research_project import normalize_project, empty_project
from project_pipeline import stages_for, resolve_stage, impact_preview as pipeline_impact_preview, PROJECT_STATUSES, STAGE_STATUSES
from provider_runtime import CLAUDE_CODE, normalize_live_provider, normalize_policy, ui_provider, policy_for_provider

SCHEMA='''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS projects(
  project_id TEXT PRIMARY KEY,title TEXT,parent_project_id TEXT,created_at TEXT,modified_at TEXT,
  current_revision INTEGER DEFAULT 0,
  project_type TEXT NOT NULL DEFAULT 'research',status TEXT NOT NULL DEFAULT 'DRAFT',current_stage TEXT,
  last_completed_stage TEXT,last_completed_artifact TEXT,last_checkpoint TEXT,preferred_provider TEXT NOT NULL DEFAULT 'claude_code_subscription',
  provider_policy TEXT NOT NULL DEFAULT 'CLAUDE_CODE_ONLY',max_api_cost_usd REAL NOT NULL DEFAULT 10.0,
  api_spent_usd REAL NOT NULL DEFAULT 0.0,runtime_version TEXT,archived INTEGER NOT NULL DEFAULT 0,
  pinned INTEGER NOT NULL DEFAULT 0,tags_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS project_revisions(
  project_id TEXT,revision INTEGER,created_at TEXT,content_sha256 TEXT,project_json TEXT,
  analysis_json TEXT,questionnaire_version TEXT,panel_version TEXT,model TEXT,reason TEXT,
  revision_id TEXT,parent_revision INTEGER,branch_id TEXT,metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(project_id,revision)
);
CREATE TABLE IF NOT EXISTS project_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,revision INTEGER,stage_type TEXT,
  ts TEXT NOT NULL,event_type TEXT NOT NULL,level TEXT NOT NULL DEFAULT 'INFO',message TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS project_stages(
  project_id TEXT NOT NULL,revision INTEGER NOT NULL,stage_type TEXT NOT NULL,ordinal INTEGER NOT NULL,
  label TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'NOT_STARTED',input_fingerprint TEXT,provider TEXT,model TEXT,
  current_job_id TEXT,artifact_ids_json TEXT NOT NULL DEFAULT '[]',last_checkpoint TEXT,waiting_reason TEXT,
  quota_reset_at TEXT,started_at TEXT,finished_at TEXT,updated_at TEXT NOT NULL,
  PRIMARY KEY(project_id,revision,stage_type)
);
CREATE TABLE IF NOT EXISTS project_artifacts(
  artifact_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,revision INTEGER NOT NULL,stage_type TEXT NOT NULL,
  artifact_type TEXT NOT NULL,path TEXT NOT NULL,sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'VALID',input_fingerprint TEXT,provider TEXT,model TEXT,created_at TEXT NOT NULL,
  superseded_by TEXT,metadata_json TEXT NOT NULL DEFAULT '{}',
  artifact_version INTEGER NOT NULL DEFAULT 1,storage_uri TEXT,prompt_version TEXT,runtime_version TEXT,
  is_current INTEGER NOT NULL DEFAULT 1,is_approved INTEGER NOT NULL DEFAULT 0,is_frozen INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project_artifact_dependencies(
  artifact_id TEXT NOT NULL,depends_on_artifact_id TEXT NOT NULL,PRIMARY KEY(artifact_id,depends_on_artifact_id)
);
CREATE TABLE IF NOT EXISTS project_attachments(
  attachment_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,revision INTEGER,filename TEXT NOT NULL,stored_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,created_at TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS project_branches(
  branch_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,source_revision INTEGER NOT NULL,name TEXT NOT NULL,
  created_at TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS project_visualization_segments(
  segment_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,name TEXT NOT NULL,created_at TEXT NOT NULL,modified_at TEXT NOT NULL,
  color TEXT,filter_json TEXT NOT NULL DEFAULT '{}',respondent_ids_json TEXT NOT NULL DEFAULT '[]',metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_visualization_segments_pid ON project_visualization_segments(project_id,modified_at DESC);
CREATE TABLE IF NOT EXISTS project_segment_intelligence(
  project_id TEXT PRIMARY KEY,dataset_fingerprint TEXT NOT NULL,created_at TEXT NOT NULL,modified_at TEXT NOT NULL,
  provider TEXT,model TEXT,status TEXT NOT NULL DEFAULT 'READY',payload_json TEXT NOT NULL DEFAULT '{}',metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS project_visualization_layouts(
  project_id TEXT NOT NULL,mode TEXT NOT NULL,created_at TEXT NOT NULL,modified_at TEXT NOT NULL,
  positions_json TEXT NOT NULL DEFAULT '{}',view_json TEXT NOT NULL DEFAULT '{}',metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(project_id,mode)
);
CREATE TABLE IF NOT EXISTS project_provider_events(
  provider_event_id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,revision INTEGER,stage_type TEXT,
  ts TEXT NOT NULL,from_provider TEXT,to_provider TEXT,reason TEXT,explicit_user_action INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,estimated_cost_usd REAL NOT NULL DEFAULT 0,
  actual_cost_usd REAL NOT NULL DEFAULT 0,metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_projects_modified ON projects(modified_at DESC);
CREATE INDEX IF NOT EXISTS idx_project_events_pid ON project_events(project_id,event_id);
CREATE INDEX IF NOT EXISTS idx_project_stages_pid ON project_stages(project_id,revision,ordinal);
CREATE INDEX IF NOT EXISTS idx_project_artifacts_pid ON project_artifacts(project_id,revision,stage_type,artifact_type);
'''

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%S')
def _sha(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def _loads(x,default):
    try:return json.loads(x or '')
    except Exception:return default

def _cols(cx,table): return {r[1] for r in cx.execute(f'PRAGMA table_info({table})').fetchall()}

def _add_col(cx,table,spec):
    name=spec.split()[0]
    if name not in _cols(cx,table): cx.execute(f'ALTER TABLE {table} ADD COLUMN {spec}')

class ProjectStore:
    def __init__(self,path: str|Path='data/project_store.sqlite'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path,timeout=30); self.cx.row_factory=sqlite3.Row
        self.cx.executescript(SCHEMA); self._migrate_178x(); self.cx.commit()
    def _migrate_178x(self):
        # SQLite CREATE TABLE IF NOT EXISTS keeps old table layouts.  Add only
        # missing columns, never destructively rewrite user data.
        for spec in [
            "project_type TEXT NOT NULL DEFAULT 'research'","status TEXT NOT NULL DEFAULT 'DRAFT'","current_stage TEXT",
            "last_completed_stage TEXT","last_completed_artifact TEXT","last_checkpoint TEXT","preferred_provider TEXT NOT NULL DEFAULT 'claude_code_subscription'",
            "provider_policy TEXT NOT NULL DEFAULT 'CLAUDE_CODE_ONLY'","max_api_cost_usd REAL NOT NULL DEFAULT 10.0",
            "api_spent_usd REAL NOT NULL DEFAULT 0.0","runtime_version TEXT","archived INTEGER NOT NULL DEFAULT 0","pinned INTEGER NOT NULL DEFAULT 0","tags_json TEXT NOT NULL DEFAULT '[]'",
            "deleted_at TEXT","pre_trash_status TEXT"]:
            _add_col(self.cx,'projects',spec)
        for spec in ["revision_id TEXT","parent_revision INTEGER","branch_id TEXT","metadata_json TEXT NOT NULL DEFAULT '{}'"]:
            _add_col(self.cx,'project_revisions',spec)
        for spec in ["artifact_version INTEGER NOT NULL DEFAULT 1","storage_uri TEXT","prompt_version TEXT","runtime_version TEXT","is_current INTEGER NOT NULL DEFAULT 1","is_approved INTEGER NOT NULL DEFAULT 0","is_frozen INTEGER NOT NULL DEFAULT 0"]:
            _add_col(self.cx,'project_artifacts',spec)
        self.cx.execute("UPDATE project_revisions SET revision_id=COALESCE(revision_id,'REV-'||project_id||'-'||revision)")
        self.cx.execute("UPDATE project_artifacts SET storage_uri=COALESCE(storage_uri,path), artifact_version=COALESCE(artifact_version,1), is_current=COALESCE(is_current,1), is_approved=COALESCE(is_approved,0), is_frozen=COALESCE(is_frozen,0)")
    def close(self): self.cx.close()

    def event(self,project_id,event_type,message,payload=None,*,revision=None,stage_type=None,level='INFO'):
        self.cx.execute('INSERT INTO project_events(project_id,revision,stage_type,ts,event_type,level,message,payload_json) VALUES(?,?,?,?,?,?,?,?)',
                        (project_id,revision,stage_type,_now(),event_type,level,message,json.dumps(payload or {},ensure_ascii=False,default=str)))
        self.cx.commit()

    def _ensure_stages(self,project_id:str,revision:int,project_type:str):
        now=_now()
        for i,(sid,label) in enumerate(stages_for(project_type),1):
            self.cx.execute('''INSERT OR IGNORE INTO project_stages(project_id,revision,stage_type,ordinal,label,status,updated_at)
                               VALUES(?,?,?,?,?,'NOT_STARTED',?)''',(project_id,int(revision),sid,i,label,now))
        # The first stage is immediately actionable for a new revision.
        self.cx.execute("UPDATE project_stages SET status='READY',updated_at=? WHERE project_id=? AND revision=? AND ordinal=1 AND status='NOT_STARTED'",(now,project_id,int(revision)))

    def create_project(self,*,project_type='research',title=None,project=None,parent_project_id=None,
                       preferred_provider=CLAUDE_CODE,provider_policy='CLAUDE_CODE_ONLY',max_api_cost_usd=10.0,
                       runtime_version='')->dict[str,Any]:
        ptype='simulation' if str(project_type).lower()=='simulation' else 'research'
        preferred_provider=normalize_live_provider(preferred_provider)
        if provider_policy in (None,'', 'CLAUDE_CODE_ONLY') and preferred_provider != CLAUDE_CODE:
            provider_policy=policy_for_provider(preferred_provider)
        pid='PRJ-'+uuid.uuid4().hex[:14]; now=_now(); title=str(title or ('Nová simulace' if ptype=='simulation' else 'Nový výzkum'))
        self.cx.execute('''INSERT INTO projects(project_id,title,parent_project_id,created_at,modified_at,current_revision,project_type,status,current_stage,
                           preferred_provider,provider_policy,max_api_cost_usd,runtime_version,archived)
                           VALUES(?,?,?,?,?,0,?,'DRAFT',?,?,?,?,?,0)''',
                        (pid,title,parent_project_id,now,now,ptype,stages_for(ptype)[0][0],normalize_live_provider(preferred_provider),normalize_policy(provider_policy),float(max_api_cost_usd),runtime_version))
        self.cx.commit()
        if ptype=='research':
            state=project if isinstance(project,dict) else empty_project(title=title)
            out=self.save(state,project_id=pid,parent_project_id=parent_project_id,reason='project_created',project_type=ptype,runtime_version=runtime_version)
        else:
            state=project if isinstance(project,dict) else {'schema_version':'simulation-project-v1','title':title,'simulation':{}}
            out=self.save_raw(state,project_id=pid,reason='project_created',project_type=ptype,runtime_version=runtime_version)
        self.event(pid,'PROJECT_CREATED','Projekt byl vytvořen okamžitě při zahájení práce.',{'project_type':ptype,'provider':normalize_live_provider(preferred_provider),'provider_policy':normalize_policy(provider_policy)},revision=out['revision'])
        return {**out,'project_type':ptype,'status':'DRAFT','preferred_provider':normalize_live_provider(preferred_provider),'provider_policy':normalize_policy(provider_policy),'max_api_cost_usd':float(max_api_cost_usd)}

    def _save_normalized(self,p:dict[str,Any],*,project_id,parent_project_id,analysis,panel_version,reason,project_type=None,runtime_version='',force_new_revision=False)->dict[str,Any]:
        pid=project_id or ('PRJ-'+uuid.uuid4().hex[:14]); now=_now(); h=_sha(p)
        row=self.cx.execute('SELECT * FROM projects WHERE project_id=?',(pid,)).fetchone()
        ptype=(project_type or (row['project_type'] if row and 'project_type' in row.keys() else 'research') or 'research').lower()
        ptype='simulation' if ptype=='simulation' else 'research'
        old_project=None
        if row:
            rev=int(row['current_revision'] or 0); parent=row['parent_project_id']
            _oldrow=self.cx.execute('SELECT content_sha256,project_json FROM project_revisions WHERE project_id=? AND revision=?',(pid,rev)).fetchone() if rev else None
            last=_oldrow
            old_project=_loads(_oldrow['project_json'],{}) if _oldrow else None
            if last and last['content_sha256']==h and not force_new_revision:
                self.cx.execute('UPDATE projects SET modified_at=?,title=?,runtime_version=COALESCE(NULLIF(?,""),runtime_version) WHERE project_id=?',(now,p.get('title',''),runtime_version,pid)); self.cx.commit()
                return {'project_id':pid,'revision':rev,'deduplicated':True,'parent_project_id':parent}
            parent_rev=rev if rev else None; rev+=1
        else:
            rev=1; parent=parent_project_id; parent_rev=None
            self.cx.execute('''INSERT INTO projects(project_id,title,parent_project_id,created_at,modified_at,current_revision,project_type,status,current_stage,preferred_provider,provider_policy,max_api_cost_usd,runtime_version,archived)
                               VALUES(?,?,?,?,?,?,?,'DRAFT',?,?,'CLAUDE_CODE_ONLY',10.0,?,0)''',
                            (pid,p.get('title',''),parent,now,now,rev,ptype,stages_for(ptype)[0][0],CLAUDE_CODE,runtime_version))
        rid='REV-'+uuid.uuid4().hex[:16]
        self.cx.execute('''INSERT INTO project_revisions(project_id,revision,created_at,content_sha256,project_json,analysis_json,questionnaire_version,panel_version,model,reason,revision_id,parent_revision,branch_id,metadata_json)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
            pid,rev,now,h,json.dumps(p,ensure_ascii=False,default=str),json.dumps(analysis or {},ensure_ascii=False,default=str),
            str(p.get('schema_version',2)),panel_version,str(p.get('model','')),reason,rid,parent_rev,None,'{}'))
        self.cx.execute('UPDATE projects SET title=?,modified_at=?,current_revision=?,project_type=?,runtime_version=COALESCE(NULLIF(?,""),runtime_version) WHERE project_id=?',(p.get('title',''),now,rev,ptype,runtime_version,pid))
        self._ensure_stages(pid,rev,ptype)
        changed_fields=[]; impact={'invalidate':[],'preserve':[x[0] for x in stages_for(ptype)],'root_stage':None}
        if parent_rev and isinstance(old_project,dict):
            keys=set(old_project)|set(p)
            changed_fields=[k for k in sorted(keys) if _sha(old_project.get(k))!=_sha(p.get(k))]
            impact=pipeline_impact_preview(ptype,changed_fields)
            # Reuse completed immutable artifacts/stages that are upstream of the
            # actual change. This is the core cross-revision no-recompute rule.
            for sid in impact.get('preserve') or []:
                prev=self.cx.execute('SELECT * FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?',(pid,int(parent_rev),sid)).fetchone()
                if prev and prev['status'] in {'DONE','DONE_WITH_WARNINGS'}:
                    self.cx.execute('''UPDATE project_stages SET status=?,input_fingerprint=?,provider=?,model=?,current_job_id=NULL,artifact_ids_json=?,last_checkpoint=?,waiting_reason=NULL,quota_reset_at=NULL,started_at=?,finished_at=?,updated_at=? WHERE project_id=? AND revision=? AND stage_type=?''',
                                    (prev['status'],prev['input_fingerprint'],prev['provider'],prev['model'],prev['artifact_ids_json'],prev['last_checkpoint'],prev['started_at'],prev['finished_at'],now,pid,rev,sid))
            root=impact.get('root_stage')
            if root:
                self.cx.execute("UPDATE project_stages SET status='READY',updated_at=? WHERE project_id=? AND revision=? AND stage_type=?",(now,pid,rev,root))
                self.cx.execute("UPDATE projects SET current_stage=?,status='READY_TO_CONTINUE' WHERE project_id=?",(root,pid))
            elif parent_rev:
                # A metadata/provider/report preference edit with no data impact
                # may safely keep every completed stage/artifact.
                done=self.cx.execute("SELECT stage_type FROM project_stages WHERE project_id=? AND revision=? AND status IN ('DONE','DONE_WITH_WARNINGS') ORDER BY ordinal DESC LIMIT 1",(pid,rev)).fetchone()
                if done:self.cx.execute("UPDATE projects SET current_stage=?,last_completed_stage=?,status='READY_TO_CONTINUE' WHERE project_id=?",(done[0],done[0],pid))
        self.cx.commit()
        self.event(pid,'REVISION_SAVED','Vznikla neměnná revize projektu.',{'reason':reason,'sha256':h,'revision_id':rid,'changed_fields':changed_fields,'impact':impact},revision=rev)
        return {'project_id':pid,'revision':rev,'revision_id':rid,'deduplicated':False,'parent_project_id':parent}

    def save(self,project:dict[str,Any],*,project_id:str|None=None,parent_project_id:str|None=None,
             analysis:dict[str,Any]|None=None,panel_version:str='',reason:str='autosave',project_type:str|None=None,runtime_version:str='',force_new_revision:bool=False)->dict[str,Any]:
        return self._save_normalized(normalize_project(project),project_id=project_id,parent_project_id=parent_project_id,analysis=analysis or {},panel_version=panel_version,reason=reason,project_type=project_type,runtime_version=runtime_version,force_new_revision=force_new_revision)
    def save_raw(self,project:dict[str,Any],*,project_id:str|None=None,parent_project_id:str|None=None,analysis=None,panel_version='',reason='autosave',project_type='simulation',runtime_version='',force_new_revision:bool=False):
        p=dict(project or {}); p.setdefault('title','Nová simulace')
        return self._save_normalized(p,project_id=project_id,parent_project_id=parent_project_id,analysis=analysis or {},panel_version=panel_version,reason=reason,project_type=project_type,runtime_version=runtime_version,force_new_revision=force_new_revision)

    def get(self,project_id:str,revision:int|None=None)->dict[str,Any]|None:
        p=self.cx.execute('SELECT * FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not p:return None
        revision=int(revision if revision is not None else p['current_revision'])
        x=self.cx.execute('SELECT * FROM project_revisions WHERE project_id=? AND revision=?',(project_id,revision)).fetchone()
        if not x:return None
        return {'project_id':project_id,'revision':revision,'revision_id':x['revision_id'],'parent_project_id':p['parent_project_id'],
                'project':_loads(x['project_json'],{}),'analysis':_loads(x['analysis_json'],{}),'created_at':x['created_at'],'sha256':x['content_sha256'],
                'project_type':p['project_type'],'status':p['status'],'current_stage':p['current_stage'],'preferred_provider':p['preferred_provider'],
                'provider_policy':p['provider_policy'],'max_api_cost_usd':float(p['max_api_cost_usd'] or 0),'api_spent_usd':float(p['api_spent_usd'] or 0),'last_completed_stage':p['last_completed_stage'],'last_completed_artifact':p['last_completed_artifact'],'last_checkpoint':p['last_checkpoint'],'runtime_version':p['runtime_version'],'archived':bool(p['archived']),'pinned':bool(p['pinned']),'tags':_loads(p['tags_json'],[])}

    def list(self,limit:int=100,*,include_archived=False,project_type=None,status=None)->list[dict[str,Any]]:
        wh=["status!='TRASHED'"]; vals=[]
        if not include_archived: wh.append('archived=0')
        if project_type: wh.append('project_type=?'); vals.append(str(project_type))
        if status: wh.append('status=?'); vals.append(str(status))
        q='SELECT * FROM projects'+((' WHERE '+' AND '.join(wh)) if wh else '')+' ORDER BY modified_at DESC LIMIT ?'; vals.append(int(limit))
        rows=self.cx.execute(q,vals).fetchall(); out=[]
        for r in rows:
            done,total=self.cx.execute("SELECT SUM(CASE WHEN status IN ('DONE','DONE_WITH_WARNINGS') THEN 1 ELSE 0 END),COUNT(*) FROM project_stages WHERE project_id=? AND revision=?",(r['project_id'],int(r['current_revision'] or 0))).fetchone()
            out.append({'project_id':r['project_id'],'title':r['title'],'parent_project_id':r['parent_project_id'],'created_at':r['created_at'],'modified_at':r['modified_at'],'revision':r['current_revision'],
                        'project_type':r['project_type'],'status':r['status'],'current_stage':r['current_stage'],'last_completed_stage':r['last_completed_stage'],'last_completed_artifact':r['last_completed_artifact'],'last_checkpoint':r['last_checkpoint'],
                        'preferred_provider':r['preferred_provider'],'provider_label':ui_provider(r['preferred_provider']),'provider_policy':r['provider_policy'],'max_api_cost_usd':float(r['max_api_cost_usd'] or 0),'api_spent_usd':float(r['api_spent_usd'] or 0),
                        'progress_done':int(done or 0),'progress_total':int(total or 0),'progress_pct':round(100*float(done or 0)/float(total or 1),1),'archived':bool(r['archived']),'pinned':bool(r['pinned']),'tags':_loads(r['tags_json'],[]),'deleted_at':r['deleted_at'],'pre_trash_status':r['pre_trash_status']})
        return out

    def move_to_trash(self,project_id:str)->dict[str,Any]:
        row=self.cx.execute("SELECT status,archived FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not row: raise KeyError(project_id)
        if str(row['status'])=='TRASHED': return self.get_trash_row(project_id)
        now=_now()
        self.cx.execute("UPDATE projects SET pre_trash_status=status,status='TRASHED',archived=1,deleted_at=?,modified_at=? WHERE project_id=?",(now,now,project_id))
        self.cx.commit(); self.event(project_id,'PROJECT_TRASHED','Projekt byl vratně přesunut do koše.',{'deleted_at':now})
        return self.get_trash_row(project_id)

    def restore_from_trash(self,project_id:str)->dict[str,Any]:
        row=self.cx.execute("SELECT pre_trash_status,status FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not row: raise KeyError(project_id)
        status=str(row['pre_trash_status'] or 'DRAFT') if str(row['status'])=='TRASHED' else str(row['status'] or 'DRAFT')
        now=_now()
        self.cx.execute("UPDATE projects SET status=?,archived=0,deleted_at=NULL,pre_trash_status=NULL,modified_at=? WHERE project_id=?",(status,now,project_id))
        self.cx.commit(); self.event(project_id,'PROJECT_RESTORED','Projekt byl obnoven z koše.',{'restored_status':status})
        return self.get(project_id) or {'project_id':project_id,'status':status}

    def get_trash_row(self,project_id:str)->dict[str,Any]:
        r=self.cx.execute("SELECT * FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not r: raise KeyError(project_id)
        return {'project_id':r['project_id'],'title':r['title'],'project_type':r['project_type'],'status':r['status'],'revision':r['current_revision'],'deleted_at':r['deleted_at'],'modified_at':r['modified_at'],'pre_trash_status':r['pre_trash_status']}

    def trash(self,limit:int=500)->list[dict[str,Any]]:
        rows=self.cx.execute("SELECT * FROM projects WHERE status='TRASHED' ORDER BY deleted_at DESC,modified_at DESC LIMIT ?",(int(limit),)).fetchall()
        return [{'project_id':r['project_id'],'title':r['title'],'project_type':r['project_type'],'status':r['status'],'revision':r['current_revision'],'deleted_at':r['deleted_at'],'modified_at':r['modified_at'],'pre_trash_status':r['pre_trash_status']} for r in rows]

    def revisions(self,project_id:str)->list[dict[str,Any]]:
        rows=self.cx.execute('SELECT revision,revision_id,parent_revision,branch_id,created_at,content_sha256,reason,metadata_json FROM project_revisions WHERE project_id=? ORDER BY revision DESC',(project_id,)).fetchall()
        return [{**dict(r),'metadata':_loads(r['metadata_json'],{})} for r in rows]
    def events(self,project_id:str,limit=300)->list[dict[str,Any]]:
        rows=self.cx.execute('SELECT * FROM project_events WHERE project_id=? ORDER BY event_id DESC LIMIT ?',(project_id,int(limit))).fetchall()
        return [{**dict(r),'payload':_loads(r['payload_json'],{})} for r in rows]
    def stages(self,project_id:str,revision:int|None=None)->list[dict[str,Any]]:
        p=self.cx.execute('SELECT current_revision,project_type FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not p:return []
        rev=int(revision if revision is not None else p['current_revision']); self._ensure_stages(project_id,rev,p['project_type']); self.cx.commit()
        rows=self.cx.execute('SELECT * FROM project_stages WHERE project_id=? AND revision=? ORDER BY ordinal',(project_id,rev)).fetchall()
        return [{**dict(r),'artifact_ids':_loads(r['artifact_ids_json'],[])} for r in rows]

    def set_stage(self,project_id:str,revision:int,stage_type:str,status:str,*,input_fingerprint=None,provider=None,model=None,current_job_id=None,last_checkpoint=None,waiting_reason=None,quota_reset_at=None,artifacts=None,clear_current_job:bool=False):
        status=str(status).upper()
        if status not in STAGE_STATUSES: raise ValueError(status)
        p=self.cx.execute('SELECT project_type FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not p: raise KeyError(project_id)
        self._ensure_stages(project_id,revision,p['project_type'])
        row=self.cx.execute('SELECT status,artifact_ids_json,started_at FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?',(project_id,int(revision),stage_type)).fetchone()
        if not row:
            # Defence in depth for the 17.9.8 crash: a caller that hands us a stage from
            # the other pipeline gets it resolved here rather than killing the job.
            resolved=resolve_stage(p['project_type'],stage_type)
            if resolved!=stage_type:
                stage_type=resolved
                row=self.cx.execute('SELECT status,artifact_ids_json,started_at FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?',(project_id,int(revision),stage_type)).fetchone()
        if not row: raise KeyError(stage_type)
        ids=_loads(row['artifact_ids_json'],[])
        for x in artifacts or []:
            if x and x not in ids: ids.append(x)
        started=row['started_at'] or (_now() if status=='RUNNING' else None)
        finished=_now() if status in {'DONE','DONE_WITH_WARNINGS'} else None
        self.cx.execute('''UPDATE project_stages SET status=?,input_fingerprint=COALESCE(?,input_fingerprint),provider=COALESCE(?,provider),model=COALESCE(?,model),
                           current_job_id=CASE WHEN ? THEN NULL ELSE COALESCE(?,current_job_id) END,artifact_ids_json=?,last_checkpoint=COALESCE(?,last_checkpoint),waiting_reason=?,quota_reset_at=?,started_at=COALESCE(started_at,?),finished_at=COALESCE(?,finished_at),updated_at=?
                           WHERE project_id=? AND revision=? AND stage_type=?''',
                        (status,input_fingerprint,provider,model,1 if clear_current_job else 0,current_job_id,json.dumps(ids),last_checkpoint,waiting_reason,quota_reset_at,started,finished,_now(),project_id,int(revision),stage_type))
        proj_status={'RUNNING':'IN_PROGRESS','READY':'READY_TO_CONTINUE','WAITING_USER':'WAITING_USER','WAITING_CREDITS':'WAITING_CREDITS','WAITING_CAPACITY':'WAITING_CAPACITY','FAILED':'READY_TO_CONTINUE'}.get(status)
        if status in {'DONE','DONE_WITH_WARNINGS'}:
            nxt=self.cx.execute("SELECT stage_type FROM project_stages WHERE project_id=? AND revision=? AND ordinal>(SELECT ordinal FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?) ORDER BY ordinal LIMIT 1",(project_id,int(revision),project_id,int(revision),stage_type)).fetchone()
            if nxt:
                self.cx.execute("UPDATE project_stages SET status='READY',updated_at=? WHERE project_id=? AND revision=? AND stage_type=? AND status IN ('NOT_STARTED','INVALIDATED')",(_now(),project_id,int(revision),nxt[0]))
                candidate=nxt[0]; proj_status='READY_TO_CONTINUE'
            else:
                candidate=stage_type; proj_status='COMPLETED_WITH_WARNINGS' if status=='DONE_WITH_WARNINGS' else 'COMPLETED'
            # Multiple durable jobs may contribute to the same logical stage (for
            # example donor QC + external verification).  A late completion must
            # never move the project dashboard backwards to an earlier stage.
            prow=self.cx.execute('SELECT current_stage,status,last_completed_stage FROM projects WHERE project_id=?',(project_id,)).fetchone()
            ords={r['stage_type']:int(r['ordinal']) for r in self.cx.execute('SELECT stage_type,ordinal FROM project_stages WHERE project_id=? AND revision=?',(project_id,int(revision))).fetchall()}
            current_existing=(prow['current_stage'] if prow else None)
            current=candidate if ords.get(candidate,0)>=ords.get(current_existing,0) else current_existing
            last_existing=(prow['last_completed_stage'] if prow else None)
            last_completed=stage_type if ords.get(stage_type,0)>=ords.get(last_existing,0) else last_existing
            # A completion of an earlier contributor must also not turn an already
            # later-running/completed project back into READY_TO_CONTINUE.
            existing_status=(prow['status'] if prow else None)
            if ords.get(candidate,0)<ords.get(current_existing,0) and existing_status in PROJECT_STATUSES:
                proj_status=existing_status
            self.cx.execute('UPDATE projects SET last_completed_stage=?,last_completed_artifact=COALESCE(?,last_completed_artifact),current_stage=?,status=?,last_checkpoint=COALESCE(?,last_checkpoint),modified_at=? WHERE project_id=?',(last_completed,(ids[-1] if ids else None),current,proj_status,last_checkpoint,_now(),project_id))
        elif proj_status:
            self.cx.execute('UPDATE projects SET current_stage=?,status=?,last_checkpoint=COALESCE(?,last_checkpoint),modified_at=? WHERE project_id=?',(stage_type,proj_status,last_checkpoint,_now(),project_id))
        self.cx.commit(); self.event(project_id,'STAGE_STATUS',f'{stage_type}: {row["status"]} → {status}',{'from':row['status'],'to':status,'waiting_reason':waiting_reason},revision=revision,stage_type=stage_type,level='WARN' if status.startswith('WAITING') or status=='FAILED' else 'INFO')
        return self.stage(project_id,revision,stage_type)
    def stage(self,project_id,revision,stage_type):
        r=self.cx.execute('SELECT * FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?',(project_id,int(revision),stage_type)).fetchone()
        return ({**dict(r),'artifact_ids':_loads(r['artifact_ids_json'],[])}) if r else None

    def register_artifact(self,*,project_id:str,revision:int,stage_type:str,artifact_type:str,path:str,sha256:str,size_bytes:int,status='VALID',input_fingerprint='',provider='',model='',metadata=None,dependencies=None,prompt_version='',runtime_version='',is_approved=None,is_frozen=None)->dict[str,Any]:
        metadata=dict(metadata or {})
        # Idempotent reuse by exact stage/type/fingerprint/SHA.
        old=self.cx.execute('''SELECT * FROM project_artifacts WHERE project_id=? AND revision=? AND stage_type=? AND artifact_type=? AND COALESCE(input_fingerprint,'')=? AND sha256=? AND superseded_by IS NULL ORDER BY created_at DESC LIMIT 1''',
                            (project_id,int(revision),stage_type,artifact_type,input_fingerprint or '',sha256)).fetchone()
        if old:return self._artifact(old)
        prev=self.cx.execute('''SELECT artifact_id,COALESCE(artifact_version,1) artifact_version FROM project_artifacts WHERE project_id=? AND revision=? AND stage_type=? AND artifact_type=? AND superseded_by IS NULL ORDER BY artifact_version DESC,created_at DESC LIMIT 1''',(project_id,int(revision),stage_type,artifact_type)).fetchone()
        ver=(int(prev['artifact_version'])+1) if prev else 1
        aid='ART-'+uuid.uuid4().hex[:18]
        approved=int(bool(('APPROVED' in artifact_type.upper()) if is_approved is None else is_approved))
        frozen=int(bool(('FROZEN' in artifact_type.upper()) if is_frozen is None else is_frozen))
        rvrow=self.cx.execute("SELECT COALESCE(runtime_version,'') FROM projects WHERE project_id=?",(project_id,)).fetchone()
        rv=str(runtime_version or (rvrow[0] if rvrow else '') or '')
        self.cx.execute('''INSERT INTO project_artifacts(artifact_id,project_id,revision,stage_type,artifact_type,path,sha256,size_bytes,status,input_fingerprint,provider,model,created_at,superseded_by,metadata_json,artifact_version,storage_uri,prompt_version,runtime_version,is_current,is_approved,is_frozen)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?,1,?,?)''',(aid,project_id,int(revision),stage_type,artifact_type,path,sha256,int(size_bytes),status,input_fingerprint,provider,model,_now(),json.dumps(metadata,ensure_ascii=False,default=str),ver,path,str(prompt_version or metadata.get('prompt_version') or ''),rv,approved,frozen))
        if prev:
            self.cx.execute('UPDATE project_artifacts SET is_current=0,superseded_by=? WHERE artifact_id=?',(aid,prev['artifact_id']))
        for dep in dependencies or []: self.cx.execute('INSERT OR IGNORE INTO project_artifact_dependencies VALUES(?,?)',(aid,dep))
        row=self.cx.execute('SELECT artifact_ids_json FROM project_stages WHERE project_id=? AND revision=? AND stage_type=?',(project_id,int(revision),stage_type)).fetchone()
        if row:
            ids=_loads(row[0],[])
            if aid not in ids: ids.append(aid)
            self.cx.execute('UPDATE project_stages SET artifact_ids_json=?,updated_at=? WHERE project_id=? AND revision=? AND stage_type=?',(json.dumps(ids),_now(),project_id,int(revision),stage_type))
        self.cx.commit(); self.event(project_id,'ARTIFACT_REGISTERED',f'{artifact_type} byl bezpečně uložen.',{'artifact_id':aid,'sha256':sha256,'path':path,'provider':provider,'model':model,'artifact_version':ver},revision=revision,stage_type=stage_type)
        return self.get_artifact(aid)
    def _artifact(self,r): return {**dict(r),'metadata':_loads(r['metadata_json'],{})}
    def get_artifact(self,artifact_id):
        r=self.cx.execute('SELECT * FROM project_artifacts WHERE artifact_id=?',(artifact_id,)).fetchone(); return self._artifact(r) if r else None
    def artifacts(self,project_id,revision=None,stage_type=None,artifact_type=None):
        p=self.cx.execute('SELECT current_revision FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not p:return []
        rev=int(revision if revision is not None else p[0])
        # Direct artifacts physically created in this revision.
        wh=['project_id=?','revision=?']; vals=[project_id,rev]
        if stage_type: wh.append('stage_type=?');vals.append(stage_type)
        if artifact_type: wh.append('artifact_type=?');vals.append(artifact_type)
        direct=list(self.cx.execute('SELECT * FROM project_artifacts WHERE '+' AND '.join(wh)+' ORDER BY created_at,artifact_id',vals).fetchall())
        out=[];seen=set()
        for r in direct:
            a=self._artifact(r);a['referenced_by_revision']=rev;out.append(a);seen.add(a['artifact_id'])
        # Preserved stages in a newer immutable revision intentionally reference
        # verified artifacts from an older revision. Surface those references in
        # overview/export/history so a revision never appears to have lost its
        # reused upstream work merely because the bytes were not duplicated.
        sw=['project_id=?','revision=?']; sv=[project_id,rev]
        if stage_type: sw.append('stage_type=?');sv.append(stage_type)
        for sr in self.cx.execute('SELECT stage_type,artifact_ids_json FROM project_stages WHERE '+' AND '.join(sw)+' ORDER BY ordinal',sv).fetchall():
            for aid in _loads(sr['artifact_ids_json'],[]):
                if not aid or aid in seen: continue
                ar=self.cx.execute('SELECT * FROM project_artifacts WHERE artifact_id=?',(aid,)).fetchone()
                if not ar: continue
                a=self._artifact(ar)
                if artifact_type and a.get('artifact_type')!=artifact_type: continue
                a['referenced_by_revision']=rev;a['reused_from_revision']=int(a.get('revision') or 0) if int(a.get('revision') or 0)!=rev else None
                out.append(a);seen.add(aid)
        out.sort(key=lambda a:(str(a.get('created_at') or ''),str(a.get('artifact_id') or '')))
        return out
    def reusable_artifact(self,project_id,revision,stage_type,artifact_type,input_fingerprint):
        r=self.cx.execute("SELECT * FROM project_artifacts WHERE project_id=? AND revision=? AND stage_type=? AND artifact_type=? AND input_fingerprint=? AND status='VALID' AND superseded_by IS NULL AND COALESCE(is_current,1)=1 ORDER BY created_at DESC LIMIT 1",(project_id,int(revision),stage_type,artifact_type,input_fingerprint)).fetchone()
        if not r:return None
        a=self._artifact(r); p=Path(a['path'])
        return a if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'] else None

    def reusable_artifact_any_revision(self,project_id,stage_type,artifact_type,input_fingerprint):
        r=self.cx.execute("SELECT * FROM project_artifacts WHERE project_id=? AND stage_type=? AND artifact_type=? AND input_fingerprint=? AND status='VALID' AND superseded_by IS NULL AND COALESCE(is_current,1)=1 ORDER BY revision DESC,created_at DESC LIMIT 1",(project_id,stage_type,artifact_type,input_fingerprint)).fetchone()
        if not r:return None
        a=self._artifact(r); p=Path(a['path'])
        return a if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a['sha256'] else None

    def bind_attachment(self,*,project_id,revision=None,attachment_id,filename,stored_path,sha256,size_bytes,metadata=None):
        self.cx.execute('INSERT OR REPLACE INTO project_attachments VALUES(?,?,?,?,?,?,?,?,?)',(attachment_id,project_id,revision,filename,stored_path,sha256,int(size_bytes),_now(),json.dumps(metadata or {},ensure_ascii=False,default=str)));self.cx.commit()
        self.event(project_id,'ATTACHMENT_ADDED',f'Příloha {filename} byla navázána na projekt.',{'attachment_id':attachment_id,'sha256':sha256},revision=revision)
    def attachments(self,project_id):
        return [{**dict(r),'metadata':_loads(r['metadata_json'],{})} for r in self.cx.execute('SELECT * FROM project_attachments WHERE project_id=? ORDER BY created_at',(project_id,)).fetchall()]

    def impact_preview(self,project_id,changed_fields=None,explicit_stage=None):
        p=self.cx.execute('SELECT project_type,current_revision FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not p:raise KeyError(project_id)
        out=pipeline_impact_preview(p['project_type'],changed_fields or [],explicit_stage)
        arts=self.artifacts(project_id,p['current_revision'])
        out['affected_artifacts']=[{'artifact_id':a['artifact_id'],'artifact_type':a['artifact_type'],'stage_type':a['stage_type']} for a in arts if a['stage_type'] in out['invalidate']]
        return out
    def invalidate(self,project_id,revision,stages:list[str],reason='input_changed'):
        for sid in stages:
            self.cx.execute("UPDATE project_stages SET status='INVALIDATED',waiting_reason=?,finished_at=NULL,updated_at=? WHERE project_id=? AND revision=? AND stage_type=?",(reason,_now(),project_id,int(revision),sid))
        self.cx.execute("UPDATE projects SET status='READY_TO_CONTINUE',current_stage=COALESCE(?,current_stage),modified_at=? WHERE project_id=?",((stages or [None])[0],_now(),project_id));self.cx.commit()
        self.event(project_id,'STAGES_INVALIDATED','Změna vstupu selektivně zneplatnila navazující kroky.',{'stages':stages,'reason':reason},revision=revision,level='WARN')

    def record_provider_event(self,project_id,*,revision=None,stage_type=None,from_provider=None,to_provider=None,reason='',explicit_user_action=False,input_tokens=0,output_tokens=0,estimated_cost_usd=0,actual_cost_usd=0,metadata=None):
        to=normalize_live_provider(to_provider or from_provider)
        self.cx.execute('''INSERT INTO project_provider_events(project_id,revision,stage_type,ts,from_provider,to_provider,reason,explicit_user_action,input_tokens,output_tokens,estimated_cost_usd,actual_cost_usd,metadata_json)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(project_id,revision,stage_type,_now(),from_provider,to,reason,1 if explicit_user_action else 0,int(input_tokens or 0),int(output_tokens or 0),float(estimated_cost_usd or 0),float(actual_cost_usd or 0),json.dumps(metadata or {},ensure_ascii=False,default=str)))
        if actual_cost_usd:
            self.cx.execute('UPDATE projects SET api_spent_usd=api_spent_usd+?,modified_at=? WHERE project_id=?',(float(actual_cost_usd),_now(),project_id))
        self.cx.commit(); self.event(project_id,'PROVIDER_CHANGED' if from_provider and from_provider!=to else 'PROVIDER_USAGE',f'AI runtime: {ui_provider(to)}',{'from':from_provider,'to':to,'reason':reason,'explicit_user_action':bool(explicit_user_action),'estimated_cost_usd':estimated_cost_usd,'actual_cost_usd':actual_cost_usd},revision=revision,stage_type=stage_type)
    def set_provider_policy(self,project_id,*,preferred_provider=None,provider_policy=None,max_api_cost_usd=None,explicit=False,reason='settings'):
        row=self.cx.execute('SELECT preferred_provider,provider_policy FROM projects WHERE project_id=?',(project_id,)).fetchone()
        if not row:raise KeyError(project_id)
        newp=normalize_live_provider(preferred_provider or row['preferred_provider']); pol=normalize_policy(provider_policy or (policy_for_provider(newp) if preferred_provider is not None else row['provider_policy']))
        cap=float(max_api_cost_usd if max_api_cost_usd is not None else self.cx.execute('SELECT max_api_cost_usd FROM projects WHERE project_id=?',(project_id,)).fetchone()[0])
        self.cx.execute('UPDATE projects SET preferred_provider=?,provider_policy=?,max_api_cost_usd=?,modified_at=? WHERE project_id=?',(newp,pol,cap,_now(),project_id));self.cx.commit()
        if row['preferred_provider']!=newp:self.record_provider_event(project_id,from_provider=row['preferred_provider'],to_provider=newp,reason=reason,explicit_user_action=explicit)
        self.event(project_id,'PROJECT_AI_POLICY_UPDATED','AI politika projektu byla změněna.',{'preferred_provider':newp,'provider_policy':pol,'max_api_cost_usd':cap,'explicit':explicit})
        return self.get(project_id)
    def provider_events(self,project_id,limit=1000):
        rows=self.cx.execute('SELECT * FROM project_provider_events WHERE project_id=? ORDER BY provider_event_id DESC LIMIT ?',(project_id,int(limit))).fetchall()
        return [{**dict(r),'metadata':_loads(r['metadata_json'],{})} for r in rows]

    def ai_usage(self,project_id):
        rows=self.cx.execute('SELECT * FROM project_provider_events WHERE project_id=? ORDER BY provider_event_id',(project_id,)).fetchall()
        ev=[{**dict(r),'metadata':_loads(r['metadata_json'],{})} for r in rows]
        return {'project_id':project_id,'input_tokens':sum(int(x['input_tokens'] or 0) for x in ev),'output_tokens':sum(int(x['output_tokens'] or 0) for x in ev),'estimated_cost_usd':round(sum(float(x['estimated_cost_usd'] or 0) for x in ev),6),'actual_cost_usd':round(sum(float(x['actual_cost_usd'] or 0) for x in ev),6),'events':ev}

    def overview(self,project_id):
        p=self.get(project_id)
        if not p:return None
        return {**p,'stages':self.stages(project_id,p['revision']),'artifacts':self.artifacts(project_id,p['revision']),
                'attachments':self.attachments(project_id),'recent_events':self.events(project_id,40),'revisions':self.revisions(project_id),'ai_usage':self.ai_usage(project_id),
                'visualization_segments':self.visualization_segments(project_id)}
    def set_pinned(self,project_id:str,pinned:bool=True):
        self.cx.execute('UPDATE projects SET pinned=?,modified_at=? WHERE project_id=?',(1 if pinned else 0,_now(),project_id));self.cx.commit()
        self.event(project_id,'PROJECT_PINNED' if pinned else 'PROJECT_UNPINNED','Projekt byl připnut.' if pinned else 'Projekt byl odepnut.',{})
        return {'project_id':project_id,'pinned':bool(pinned)}

    def set_tags(self,project_id:str,tags:list[str]):
        clean=[]
        for x in tags or []:
            t=str(x or '').strip()[:40]
            if t and t.lower() not in {y.lower() for y in clean}:clean.append(t)
        clean=clean[:12]
        self.cx.execute('UPDATE projects SET tags_json=?,modified_at=? WHERE project_id=?',(json.dumps(clean,ensure_ascii=False),_now(),project_id));self.cx.commit()
        self.event(project_id,'PROJECT_TAGS_UPDATED','Štítky projektu byly upraveny.',{'tags':clean})
        return {'project_id':project_id,'tags':clean}

    def duplicate(self,project_id:str,title:str|None=None):
        src=self.get(project_id)
        if not src:raise KeyError(project_id)
        state=json.loads(json.dumps(src['project'],ensure_ascii=False,default=str))
        row=self.cx.execute('SELECT title FROM projects WHERE project_id=?',(project_id,)).fetchone()
        new_title=str(title or ((state.get('title') or (row[0] if row else None) or 'Projekt')+' · kopie'))
        state['title']=new_title
        out=self.create_project(project_type=src['project_type'],title=new_title,project=state,parent_project_id=project_id,preferred_provider=src['preferred_provider'],provider_policy=src['provider_policy'],max_api_cost_usd=src['max_api_cost_usd'],runtime_version=src.get('runtime_version') or '')
        self.event(out['project_id'],'PROJECT_DUPLICATED','Vznikla editovatelná kopie projektu.',{'source_project_id':project_id})
        return {**out,'source_project_id':project_id}

    def archive(self,project_id,archived=True):
        self.cx.execute("UPDATE projects SET archived=?,status=?,modified_at=? WHERE project_id=?",(1 if archived else 0,'ARCHIVED' if archived else 'READY_TO_CONTINUE',_now(),project_id));self.cx.commit();self.event(project_id,'PROJECT_ARCHIVED' if archived else 'PROJECT_RESTORED','Projekt byl archivován.' if archived else 'Projekt byl obnoven.',{})
    def save_visualization_segment(self,project_id:str,name:str,*,filter_spec=None,respondent_ids=None,color:str='',metadata=None,segment_id:str|None=None):
        if not self.get(project_id):raise KeyError(project_id)
        sid=str(segment_id or ('VSEG-'+uuid.uuid4().hex[:14]))
        clean_ids=[str(x) for x in (respondent_ids or [])][:10000]
        now=_now()
        self.cx.execute('''INSERT INTO project_visualization_segments(segment_id,project_id,name,created_at,modified_at,color,filter_json,respondent_ids_json,metadata_json)
                           VALUES(?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(segment_id) DO UPDATE SET name=excluded.name,modified_at=excluded.modified_at,color=excluded.color,filter_json=excluded.filter_json,respondent_ids_json=excluded.respondent_ids_json,metadata_json=excluded.metadata_json''',
                        (sid,project_id,str(name or 'Uložený segment')[:120],now,now,str(color or '')[:32],json.dumps(filter_spec or {},ensure_ascii=False),json.dumps(clean_ids,ensure_ascii=False),json.dumps(metadata or {},ensure_ascii=False,default=str)))
        self.cx.commit();self.event(project_id,'VISUALIZATION_SEGMENT_SAVED','Vizualizační segment byl uložen.',{'segment_id':sid,'name':name,'respondent_count':len(clean_ids)})
        return {'segment_id':sid,'project_id':project_id,'name':str(name or 'Uložený segment'),'color':str(color or ''),'filter':filter_spec or {},'respondent_ids':clean_ids,'metadata':metadata or {}}

    def visualization_segments(self,project_id:str):
        rows=self.cx.execute('SELECT * FROM project_visualization_segments WHERE project_id=? ORDER BY modified_at DESC',(project_id,)).fetchall()
        return [{'segment_id':r['segment_id'],'project_id':r['project_id'],'name':r['name'],'created_at':r['created_at'],'modified_at':r['modified_at'],'color':r['color'],
                 'filter':_loads(r['filter_json'],{}),'respondent_ids':_loads(r['respondent_ids_json'],[]),'metadata':_loads(r['metadata_json'],{})} for r in rows]

    def visualization_layout(self,project_id:str,mode:str):
        mode=str(mode or 'respondents').strip().lower()
        r=self.cx.execute('SELECT * FROM project_visualization_layouts WHERE project_id=? AND mode=?',(project_id,mode)).fetchone()
        if not r:return {'project_id':project_id,'mode':mode,'positions':{},'view':{},'metadata':{}}
        return {'project_id':project_id,'mode':mode,'created_at':r['created_at'],'modified_at':r['modified_at'],
                'positions':_loads(r['positions_json'],{}),'view':_loads(r['view_json'],{}),'metadata':_loads(r['metadata_json'],{})}

    def save_visualization_layout(self,project_id:str,mode:str,*,positions=None,view=None,metadata=None):
        if not self.get(project_id):raise KeyError(project_id)
        mode=str(mode or 'respondents').strip().lower()
        if mode not in {'respondents','objects'}:raise ValueError('Neznámý režim vizualizačního layoutu.')
        clean={}
        for k,v in (positions or {}).items():
            try:
                x=float(v.get('x'));y=float(v.get('y'))
                if abs(x)<=200 and abs(y)<=200:clean[str(k)]={'x':round(x,5),'y':round(y,5)}
            except Exception:continue
        now=_now();old=self.cx.execute('SELECT created_at FROM project_visualization_layouts WHERE project_id=? AND mode=?',(project_id,mode)).fetchone()
        created=(old['created_at'] if old else now)
        sql=('INSERT INTO project_visualization_layouts(project_id,mode,created_at,modified_at,positions_json,view_json,metadata_json) '
             'VALUES(?,?,?,?,?,?,?) ON CONFLICT(project_id,mode) DO UPDATE SET modified_at=excluded.modified_at,positions_json=excluded.positions_json,view_json=excluded.view_json,metadata_json=excluded.metadata_json')
        self.cx.execute(sql,(project_id,mode,created,now,json.dumps(clean,ensure_ascii=False),json.dumps(view or {},ensure_ascii=False,default=str),json.dumps(metadata or {},ensure_ascii=False,default=str)))
        self.cx.commit();self.event(project_id,'VISUALIZATION_LAYOUT_SAVED','Ruční layout Sociomapy byl uložen bez změny dat projektu.',{'mode':mode,'moved_count':len(clean)})
        return self.visualization_layout(project_id,mode)

    def reset_visualization_layout(self,project_id:str,mode:str):
        mode=str(mode or 'respondents').strip().lower()
        cur=self.cx.execute('DELETE FROM project_visualization_layouts WHERE project_id=? AND mode=?',(project_id,mode));self.cx.commit()
        if cur.rowcount:self.event(project_id,'VISUALIZATION_LAYOUT_RESET','Ruční layout Sociomapy byl resetován na datově vypočtenou polohu.',{'mode':mode})
        return {'ok':True,'project_id':project_id,'mode':mode,'deleted':int(cur.rowcount or 0)}

    def save_segment_intelligence(self,project_id:str,dataset_fingerprint:str,payload:dict,*,provider:str='',model:str='',status:str='READY',metadata=None):
        now=_now(); self.cx.execute("""INSERT INTO project_segment_intelligence(project_id,dataset_fingerprint,created_at,modified_at,provider,model,status,payload_json,metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET dataset_fingerprint=excluded.dataset_fingerprint,modified_at=excluded.modified_at,provider=excluded.provider,model=excluded.model,status=excluded.status,payload_json=excluded.payload_json,metadata_json=excluded.metadata_json""",
            (project_id,dataset_fingerprint,now,now,provider,model,status,json.dumps(payload or {},ensure_ascii=False,default=str),json.dumps(metadata or {},ensure_ascii=False,default=str))); self.cx.commit()
        self.event(project_id,'SEGMENT_INTELLIGENCE_CACHED','Interpretace zajímavých segmentů byla uložena bez změny revize projektu.',{'dataset_fingerprint':dataset_fingerprint,'provider':provider,'model':model,'status':status})
        return self.segment_intelligence(project_id)

    def segment_intelligence(self,project_id:str):
        r=self.cx.execute('SELECT * FROM project_segment_intelligence WHERE project_id=?',(project_id,)).fetchone()
        if not r:return None
        return {**dict(r),'payload':_loads(r['payload_json'],{}),'metadata':_loads(r['metadata_json'],{})}

    def clear_segment_intelligence(self,project_id:str):
        cur=self.cx.execute('DELETE FROM project_segment_intelligence WHERE project_id=?',(project_id,)); self.cx.commit(); return {'ok':True,'deleted':int(cur.rowcount or 0),'project_id':project_id}

    def delete_visualization_segment(self,project_id:str,segment_id:str):
        cur=self.cx.execute('DELETE FROM project_visualization_segments WHERE project_id=? AND segment_id=?',(project_id,segment_id));self.cx.commit()
        if cur.rowcount:self.event(project_id,'VISUALIZATION_SEGMENT_DELETED','Vizualizační segment byl odstraněn.',{'segment_id':segment_id})
        return {'ok':bool(cur.rowcount),'project_id':project_id,'segment_id':segment_id}

    def branch(self,project_id,source_revision:int,name:str='Větev')->dict[str,Any]:
        src=self.get(project_id,source_revision)
        if not src:raise KeyError(source_revision)
        bid='BR-'+uuid.uuid4().hex[:14]
        self.cx.execute('INSERT INTO project_branches VALUES(?,?,?,?,?,?)',(bid,project_id,int(source_revision),str(name),_now(),'{}'));self.cx.commit()
        out=self.save_raw(src['project'],project_id=project_id,analysis=src['analysis'],reason='branch:'+name,project_type=src['project_type'],force_new_revision=True) if src['project_type']=='simulation' else self.save(src['project'],project_id=project_id,analysis=src['analysis'],reason='branch:'+name,project_type=src['project_type'],force_new_revision=True)
        self.cx.execute('UPDATE project_revisions SET branch_id=? WHERE project_id=? AND revision=?',(bid,project_id,out['revision']));self.cx.commit();self.event(project_id,'BRANCH_CREATED','Vznikla nová větev projektu.',{'branch_id':bid,'source_revision':source_revision,'new_revision':out['revision'],'name':name},revision=out['revision'])
        return {**out,'branch_id':bid}
    def restore_as_new_revision(self,project_id,source_revision:int):
        src=self.get(project_id,source_revision)
        if not src:raise KeyError(source_revision)
        out=self.save_raw(src['project'],project_id=project_id,analysis=src['analysis'],reason=f'restore_revision_{source_revision}',project_type=src['project_type'],force_new_revision=True) if src['project_type']=='simulation' else self.save(src['project'],project_id=project_id,analysis=src['analysis'],reason=f'restore_revision_{source_revision}',project_type=src['project_type'],force_new_revision=True)
        self.event(project_id,'REVISION_RESTORED','Historická revize byla obnovena jako nová revize.',{'source_revision':source_revision,'new_revision':out['revision']},revision=out['revision'])
        return out
    def export_zip(self,project_id,out_path:str|Path):
        ov=self.overview(project_id)
        if not ov:raise KeyError(project_id)
        out=Path(out_path);out.parent.mkdir(parents=True,exist_ok=True)
        hashes={}
        def add_bytes(z,name,data):
            z.writestr(name,data); hashes[name]=hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            payloads={
              'project.json':self.get(project_id),
              'revisions.json':self.revisions(project_id),
              'events.json':self.events(project_id,limit=100000),
              'artifact_manifest.json':ov['artifacts'],
              'attachments_manifest.json':ov['attachments'],
              'provider_events.json':self.provider_events(project_id,limit=100000),
              'project_overview.json':ov,
            }
            for name,obj in payloads.items(): add_bytes(z,name,json.dumps(obj,ensure_ascii=False,indent=2,default=str).encode('utf-8'))
            for a in ov['artifacts']:
                fp=Path(a['path'])
                if fp.is_file():
                    name='artifacts/'+a['artifact_id']+'_'+fp.name; data=fp.read_bytes(); add_bytes(z,name,data)
            for a in ov['attachments']:
                fp=Path(a['stored_path'])
                if fp.is_file():
                    name='attachments/'+a['attachment_id']+'_'+Path(a['filename']).name; data=fp.read_bytes(); add_bytes(z,name,data)
            checks=''.join(f'{digest}  {name}\n' for name,digest in sorted(hashes.items())).encode('utf-8')
            z.writestr('SHA256SUMS.txt',checks)
        self.event(project_id,'PROJECT_EXPORTED','Vznikl kompletní export projektu.',{'path':str(out),'files':len(hashes)})
        return out
