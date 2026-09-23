from __future__ import annotations
from dataclasses import dataclass
import pandas as pd

@dataclass
class Route:
    track:str; confidence:float; reasons:list[str]

def classify(df:pd.DataFrame,name:str="",explicit:str|None=None)->Route:
    if explicit:
        t=explicit.upper()
        if t not in {"A","B","C"}: raise ValueError("trat musí být A/B/C")
        return Route(t,1.0,["explicitně zadáno"])
    cols={str(c).lower() for c in df.columns}
    # Track C can never be inferred: validation truth must be deliberately marked.
    if {"variable","category","target_share"} <= cols or {"promenna","kategorie","cil"} <= cols:
        return Route("B",.95,["long-form kalibrační cíle"])
    if any(x in cols for x in {"respondent_id","id_respondent","case_id"}) and len(df)>=2:
        return Route("A",.80,["řádek vypadá jako respondent-level mikrodata"])
    if len(df)<=50 and len(cols)<=8:
        return Route("B",.60,["malá agregační tabulka; potvrď mapping"])
    return Route("A",.55,["výchozí respondent-level interpretace; doporučeno explicitně potvrdit"])
