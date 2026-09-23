from __future__ import annotations
import hashlib, json
import pandas as pd
from .registry import Registry

DEFAULT_QUASI=["respondent_id","pohlavi","vek","vzdelani","kraj"]

def row_hashes(df:pd.DataFrame, columns:list[str]|None=None, *, source_id:str="") -> list[str]:
    cols=[c for c in (columns or DEFAULT_QUASI) if c in df.columns]
    if not cols: raise ValueError("Nelze vytvořit respondent-level holdout hash: žádný identifikátor/quasi sloupec.")
    out=[]
    for _,r in df[cols].iterrows():
        vals=[None if pd.isna(r[c]) else str(r[c]).strip().lower() for c in cols]
        payload=json.dumps([source_id,cols,vals],ensure_ascii=False,separators=(",",":"))
        out.append(hashlib.sha256(payload.encode()).hexdigest())
    return out


def assert_no_holdout(df:pd.DataFrame,registry:Registry,*,source_id:str="",columns:list[str]|None=None):
    known=registry.holdout_hashes(source_id or None)
    if not known: return {"ok":True,"matches":0}
    hs=row_hashes(df,columns,source_id=source_id)
    hits=[h for h in hs if h in known]
    if hits: raise RuntimeError(f"LEAKAGE BLOCK: ingest obsahuje {len(hits)} respondentů z holdoutu.")
    return {"ok":True,"matches":0}
