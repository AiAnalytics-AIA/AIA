"""Authoritative structural-joint and predictive-validation gates for NPC Panel.

v15.2 separates two questions that older releases conflated:
1) Is the stored respondent internally coherent?  Yes for the same-person core and
   within each whole donor block; cross-survey links are statistical matches.
2) Are new NPC answers externally prediction-validated?  Not automatically.

Therefore a structurally coherent panel does not self-upgrade predictive claims.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent
STATUS_PATH=ROOT/"CORE_JOINT_STATUS.json"
LEVELS=("COHERENT_CORE_MATCHED_BLOCKS","JOINT_SMOKE_VALIDATED","JOINT_VALIDATED","JOINT_UNVALIDATED")


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()


def _fallback(reason: str) -> dict[str,Any]:
    return {
        "status":"JOINT_UNVALIDATED",
        "structure_status":"UNKNOWN",
        "prediction_validation_status":"UNVALIDATED",
        "client_joint_outputs_allowed":False,
        "descriptive_core_outputs_allowed":False,
        "matched_block_outputs_allowed":False,
        "cross_block_joint_claims_allowed":False,
        "reasons":[reason],
    }


def load_joint_status(path:str|Path=STATUS_PATH)->dict[str,Any]:
    p=Path(path)
    if not p.exists(): return _fallback("CORE_JOINT_STATUS.json is missing")
    try: obj=json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc: return _fallback(f"invalid CORE_JOINT_STATUS.json: {exc}")
    if obj.get("status") not in LEVELS:
        return _fallback("unknown joint validation status")

    # Structural v15.2 certificate is tied to the exact production panel bytes.
    if obj.get("status")=="COHERENT_CORE_MATCHED_BLOCKS":
        panel_name=str(obj.get("production_panel") or "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz")
        panel=ROOT/panel_name
        expected=str(obj.get("panel_sha256") or "")
        if not panel.exists():
            return _fallback(f"production panel missing: {panel_name}")
        if expected and _sha256(panel)!=expected:
            return _fallback("production panel fingerprint changed since structural QC")
        obj["client_joint_outputs_allowed"]=False
        obj["descriptive_core_outputs_allowed"]=True
        obj["matched_block_outputs_allowed"]=True
        obj["cross_block_joint_claims_allowed"]=False
        return obj

    # External joint-validation certificates remain tied to the behavior-changing system.
    if obj.get("status") in {"JOINT_SMOKE_VALIDATED","JOINT_VALIDATED"}:
        try:
            from system_fingerprint import current_system_sha256
            cur=current_system_sha256(); obj["current_system_sha256"]=cur
            if obj.get("system_sha256")!=cur:
                return _fallback("system fingerprint changed since joint validation")
        except Exception as exc:
            return _fallback(f"cannot verify joint fingerprint: {exc}")
        obj["client_joint_outputs_allowed"]=True
        obj.setdefault("descriptive_core_outputs_allowed",True)
        obj.setdefault("matched_block_outputs_allowed",True)
        obj.setdefault("cross_block_joint_claims_allowed",True)
        return obj

    obj["client_joint_outputs_allowed"]=False
    obj.setdefault("descriptive_core_outputs_allowed",False)
    obj.setdefault("matched_block_outputs_allowed",False)
    obj.setdefault("cross_block_joint_claims_allowed",False)
    return obj


def joint_output_gate(*,output:str,allow_experimental:bool=False)->dict[str,Any]:
    """Gate client claims that require cross-block latent joint validity.

    Ordinary demographic/core profiles and labelled donor-block summaries are not
    sent through this gate; natural clustering/sociomaps/cross-block latent claims are.
    """
    st=load_joint_status(); allowed=bool(st.get("client_joint_outputs_allowed"))
    if allowed:
        return {"allowed":True,"experimental":False,"status":st["status"],"output":output}
    warning=(
        "v15.2 má koherentní same-person core a celé matchované donor bloky, ale vazba mezi různými "
        "průzkumy je statistický matching. Přirozené clustery a jiné cross-block joint claimy proto "
        "zůstávají experimentální do externí validace."
    )
    if allow_experimental:
        return {"allowed":True,"experimental":True,"status":st["status"],"output":output,"warning":warning}
    return {"allowed":False,"experimental":False,"status":st["status"],"output":output,"warning":warning}


def natural_clustering_allowed(*,allow_experimental:bool=False)->dict[str,Any]:
    return joint_output_gate(output="natural_latent_clustering",allow_experimental=allow_experimental)
