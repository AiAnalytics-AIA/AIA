"""Canonical validation state machine bound to the current system fingerprint."""
from __future__ import annotations
import json
from pathlib import Path
LEVELS=("UNVALIDATED","SMOKE_VALIDATED","HOLDOUT_VALIDATED")

def combine(*statuses:str)->str:
    s=set(statuses)
    if "HOLDOUT_VALIDATED" in s:return "HOLDOUT_VALIDATED"
    if "SMOKE_VALIDATED" in s:return "SMOKE_VALIDATED"
    return "UNVALIDATED"

def validation_tier(root:str|Path|None=None)->str:
    root=Path(root or Path(__file__).resolve().parent);tiers=[]
    from system_fingerprint import current_system_sha256
    current=current_system_sha256()
    smoke=root/"SMOKE_VALIDATION.json"
    if smoke.exists():
        try:
            obj=json.loads(smoke.read_text(encoding="utf-8"))
            if obj.get("status")=="SMOKE_VALIDATED" and obj.get("system_sha256")==current:
                tiers.append("SMOKE_VALIDATED")
        except Exception:pass
    try:
        from validation_gate import load_validation_evidence
        ev=load_validation_evidence()
        if ev.get("status")=="VALIDATED" and ev.get("current_system_sha256",current)==current:
            tiers.append("HOLDOUT_VALIDATED")
    except Exception:pass
    return combine(*tiers)
