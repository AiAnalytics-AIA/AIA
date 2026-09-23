"""Block-level statistical donor fusion framework for NPC Panel v15.

This module intentionally does NOT fabricate donor microdata. It operates only on
real respondent-level donor files explicitly registered in DONOR_BLOCK_REGISTRY.json.
Each thematic block is copied as a coherent block from one real donor respondent;
matching across blocks uses shared variables and leaves provenance columns behind.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/"DONOR_BLOCK_REGISTRY.json"

@dataclass
class DonorBlock:
    block_id: str
    path: str
    id_column: str
    matching: list[str]
    payload: list[str]
    weight_column: str | None = None
    source: str = ""
    reference_period: str = ""


def load_registry(path: str|Path=REGISTRY) -> dict[str,Any]:
    p=Path(path)
    if not p.is_file():
        return {"schema_version":1,"blocks":[]}
    return json.loads(p.read_text(encoding="utf-8"))


def _encode_joint(base: pd.DataFrame, donor: pd.DataFrame, cols: list[str]) -> tuple[np.ndarray,np.ndarray,list[str]]:
    """Create a shared numeric matching matrix without learning from payload columns."""
    bparts=[]; dparts=[]; used=[]
    for c in cols:
        if c not in base.columns or c not in donor.columns:
            continue
        bs=base[c]; ds=donor[c]
        if pd.api.types.is_numeric_dtype(bs) and pd.api.types.is_numeric_dtype(ds):
            combo=pd.concat([pd.to_numeric(bs,errors="coerce"),pd.to_numeric(ds,errors="coerce")])
            med=float(combo.median()) if combo.notna().any() else 0.0
            sd=float(combo.std(ddof=0)) or 1.0
            bparts.append(((pd.to_numeric(bs,errors="coerce").fillna(med)-med)/sd).to_numpy()[:,None])
            dparts.append(((pd.to_numeric(ds,errors="coerce").fillna(med)-med)/sd).to_numpy()[:,None])
        else:
            cats=sorted(set(bs.dropna().astype(str))|set(ds.dropna().astype(str)))
            if len(cats)>50: continue
            bm=np.column_stack([(bs.astype(str)==x).to_numpy(float) for x in cats])
            dm=np.column_stack([(ds.astype(str)==x).to_numpy(float) for x in cats])
            bparts.append(bm); dparts.append(dm)
        used.append(c)
    if not bparts:
        raise ValueError("Donor block nemá žádné společné matching proměnné s backbone.")
    return np.concatenate(bparts,axis=1),np.concatenate(dparts,axis=1),used


def fuse_block(base: pd.DataFrame, donor: pd.DataFrame, block: DonorBlock, *, seed:int=15001,
               k_nearest:int=5) -> tuple[pd.DataFrame,dict[str,Any]]:
    """Hot-deck nearest-neighbour donor match; entire payload comes from one donor row."""
    from sklearn.neighbors import NearestNeighbors
    missing=[c for c in block.payload if c not in donor.columns]
    if missing: raise ValueError(f"{block.block_id}: donor chybí payload sloupce: {missing[:8]}")
    Xb,Xd,used=_encode_joint(base,donor,block.matching)
    k=max(1,min(int(k_nearest),len(donor)))
    nn=NearestNeighbors(n_neighbors=k,metric="euclidean").fit(Xd)
    dist,idx=nn.kneighbors(Xb)
    rng=np.random.default_rng(seed)
    chosen=[]
    dw=pd.to_numeric(donor.get(block.weight_column,pd.Series(1.0,index=donor.index)),errors="coerce").fillna(0).clip(lower=0).to_numpy(float) if block.weight_column else np.ones(len(donor))
    for i in range(len(base)):
        cand=idx[i]
        # distance kernel x donor survey weight; no payload variable enters selection.
        scale=float(np.median(dist[i])) if np.median(dist[i])>0 else 1.0
        p=np.exp(-dist[i]/scale)*dw[cand]
        p=p/p.sum() if p.sum()>0 else np.ones(len(cand))/len(cand)
        chosen.append(int(rng.choice(cand,p=p)))
    out=base.copy()
    for c in block.payload:
        out[c]=donor.iloc[chosen][c].to_numpy()
    out[f"_donor_{block.block_id}_id"]=donor.iloc[chosen][block.id_column].astype(str).to_numpy()
    out[f"_donor_{block.block_id}_distance"]=[round(float(dist[i,list(idx[i]).index(chosen[i])]),6) if chosen[i] in idx[i] else None for i in range(len(base))]
    audit={"block_id":block.block_id,"n_base":len(base),"n_donor":len(donor),"matching_used":used,"payload":block.payload,
           "median_match_distance":round(float(np.median([dist[i,list(idx[i]).index(chosen[i])] for i in range(len(base))])),4),
           "unique_donors_used":len(set(chosen)),"source":block.source,"reference_period":block.reference_period}
    return out,audit


def build_fused_panel(backbone: pd.DataFrame, *, registry_path: str|Path=REGISTRY, seed:int=15001) -> tuple[pd.DataFrame,dict[str,Any]]:
    reg=load_registry(registry_path)
    out=backbone.copy(); audits=[]
    for i,b in enumerate(reg.get("blocks") or []):
        if not b.get("enabled",True): continue
        p=(ROOT/str(b["path"])).resolve() if not Path(str(b["path"])).is_absolute() else Path(str(b["path"])).resolve()
        if not p.is_file(): raise FileNotFoundError(f"Donor block {b.get('block_id')}: {p}")
        donor=pd.read_csv(p,low_memory=False) if p.suffix.lower()==".csv" else pd.read_parquet(p)
        block=DonorBlock(block_id=str(b["block_id"]),path=str(p),id_column=str(b.get("id_column") or "respondent_id"),
                         matching=list(b.get("matching") or []),payload=list(b.get("payload") or []),weight_column=b.get("weight_column"),
                         source=str(b.get("source") or ""),reference_period=str(b.get("reference_period") or ""))
        out,a=fuse_block(out,donor,block,seed=seed+1009*i,k_nearest=int(b.get("k_nearest") or 5)); audits.append(a)
    payload={"schema_version":1,"method":"block_hot_deck_knn","seed":seed,"blocks":audits}
    payload["sha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return out,payload


def donor_qc(fused: pd.DataFrame, registry_path: str|Path=REGISTRY) -> dict[str,Any]:
    reg=load_registry(registry_path); checks=[]
    for b in reg.get("blocks") or []:
        if not b.get("enabled",True): continue
        bid=str(b["block_id"]); idc=f"_donor_{bid}_id"; dc=f"_donor_{bid}_distance"
        if idc not in fused:
            checks.append({"block_id":bid,"status":"FAIL","reason":"missing donor provenance"}); continue
        reuse=fused[idc].value_counts(normalize=True).max() if len(fused) else 1.0
        md=float(pd.to_numeric(fused.get(dc),errors="coerce").median()) if dc in fused else None
        status="PASS" if reuse<=0.10 else "WARN"
        checks.append({"block_id":bid,"status":status,"max_single_donor_share":round(float(reuse),4),"median_distance":round(md,4) if md is not None else None})
    return {"ok":all(x["status"]!="FAIL" for x in checks),"checks":checks}
