from __future__ import annotations
import pandas as pd

CORE_ALIASES={
 "sex":"pohlavi","gender":"pohlavi","pohlaví":"pohlavi",
 "age":"vek","věk":"vek","education":"vzdelani","vzdělání":"vzdelani",
 "region":"kraj","region_cz":"kraj","weight":"vaha_kalibrovana","vaha":"vaha_kalibrovana",
}

def harmonize_columns(df:pd.DataFrame,mapping:dict[str,str]|None=None)->pd.DataFrame:
    mp={**CORE_ALIASES,**(mapping or {})}
    ren={c:mp.get(str(c).strip().lower(),c) for c in df.columns}
    return df.rename(columns=ren).copy()


def apply_value_dictionary(df:pd.DataFrame,dictionary:dict[str,dict[str,str]]|None=None)->tuple[pd.DataFrame,dict[str,list[str]]]:
    out=df.copy(); unknown={}
    for c,mp in (dictionary or {}).items():
        if c not in out: continue
        known=set(mp); vals=set(out[c].dropna().astype(str))
        u=sorted(vals-known)
        if u: unknown[c]=u
        out[c]=out[c].map(lambda x: mp.get(str(x),x) if pd.notna(x) else x)
    return out,unknown
