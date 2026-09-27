"""Atomic filesystem artifact storage backed by ProjectStore registry."""
from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from pathlib import Path
from typing import Any

class ArtifactStore:
    def __init__(self, project_store, root: str|Path='data/project_artifacts'):
        self.project_store=project_store
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)

    def _dir(self,project_id:str,revision:int,stage_type:str)->Path:
        p=self.root/project_id/f'r{int(revision):04d}'/stage_type
        p.mkdir(parents=True,exist_ok=True); return p

    @staticmethod
    def _safe(name:str)->str:
        import re
        return re.sub(r'[^A-Za-z0-9._-]+','_',str(name or 'artifact'))[:160] or 'artifact'

    def put_bytes(self,*,project_id:str,revision:int,stage_type:str,artifact_type:str,data:bytes,
                  filename:str|None=None,input_fingerprint:str='',provider:str='',model:str='',
                  metadata:dict[str,Any]|None=None,dependencies:list[str]|None=None,status:str='VALID')->dict[str,Any]:
        d=self._dir(project_id,revision,stage_type)
        digest=hashlib.sha256(data).hexdigest()
        fname=self._safe(filename or f'{artifact_type}_{digest[:12]}.bin')
        target=d/fname
        fd,tmp=tempfile.mkstemp(prefix='.tmp_',dir=str(d))
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,target)
            # verify bytes after atomic rename before registry commit
            got=hashlib.sha256(target.read_bytes()).hexdigest()
            if got!=digest: raise IOError('ARTIFACT_SHA256_MISMATCH')
        finally:
            try:
                if os.path.exists(tmp): os.unlink(tmp)
            except Exception: pass
        return self.project_store.register_artifact(
            project_id=project_id,revision=revision,stage_type=stage_type,artifact_type=artifact_type,
            path=str(target),sha256=digest,size_bytes=len(data),status=status,input_fingerprint=input_fingerprint,
            provider=provider,model=model,metadata=metadata or {},dependencies=dependencies or [])

    def put_json(self,**kw):
        obj=kw.pop('obj'); filename=kw.pop('filename',None) or f"{kw.get('artifact_type','artifact')}.json"
        return self.put_bytes(data=json.dumps(obj,ensure_ascii=False,indent=2,default=str).encode('utf-8'),filename=filename,**kw)

    def put_text(self,**kw):
        text=kw.pop('text'); filename=kw.pop('filename',None) or f"{kw.get('artifact_type','artifact')}.txt"
        return self.put_bytes(data=str(text).encode('utf-8'),filename=filename,**kw)

    def put_file(self,*,source:str|Path,**kw):
        src=Path(source)
        if not src.is_file(): raise FileNotFoundError(src)
        return self.put_bytes(data=src.read_bytes(),filename=kw.pop('filename',src.name),**kw)

    def get(self,artifact_id:str): return self.project_store.get_artifact(artifact_id)
    def exists(self,artifact_id:str)->bool:
        a=self.get(artifact_id); return bool(a and Path(a['path']).is_file())
    def verify(self,artifact_id:str)->bool:
        a=self.get(artifact_id)
        if not a: return False
        p=Path(a['path'])
        return p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==a.get('sha256')
