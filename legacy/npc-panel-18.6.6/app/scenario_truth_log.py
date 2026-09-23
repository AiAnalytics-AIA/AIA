"""Append-only scenario resolution log; separate from blind forecast track record."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import hashlib,json,os
ROOT=Path(__file__).resolve().parent
LOG=ROOT/"data"/"scenario_truth_log.jsonl"

def record(entry: dict[str,Any]) -> dict[str,Any]:
    LOG.parent.mkdir(parents=True,exist_ok=True)
    e=dict(entry); e["recorded_at_utc"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    base=json.dumps(e,sort_keys=True,ensure_ascii=False,default=str)
    e["record_sha256"]=hashlib.sha256(base.encode()).hexdigest()
    with LOG.open("a",encoding="utf-8") as f: f.write(json.dumps(e,ensure_ascii=False,default=str)+"\n")
    return e

def list_entries(limit:int=100)->list[dict[str,Any]]:
    if not LOG.is_file(): return []
    rows=[]
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try: rows.append(json.loads(line))
        except Exception: pass
    return rows[-max(1,int(limit)):][::-1]
