"""Campaign background contract for v17. Specific brand knowledge is fail-closed."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
def validate_brand_state(brand_state:pd.DataFrame|None, *, brand:str="")->dict:
    if brand_state is None or brand_state.empty:return {"ready":False,"reason":"BRAND_SPECIFIC_BACKGROUND_MISSING"}
    required={"panel_row_id","brand"};missing=required-set(brand_state.columns)
    if missing:return {"ready":False,"reason":"BRAND_STATE_SCHEMA_MISSING:"+",".join(sorted(missing))}
    if brand and not brand_state["brand"].astype(str).str.casefold().eq(str(brand).casefold()).any():return {"ready":False,"reason":"REQUESTED_BRAND_NOT_IN_STATE"}
    return {"ready":True,"rows":int(len(brand_state))}
def build_campaign_context(row:pd.Series,*,brand:str,category:str,brand_state:pd.DataFrame|None=None,category_state:pd.DataFrame|None=None,current_state:dict|None=None)->dict:
    gate=validate_brand_state(brand_state,brand=brand)
    if not gate["ready"]:raise ValueError("Brand-specific simulation blocked: "+gate["reason"]+". Doplňte brand/category/customer research; NPC nesmí znalost značky vymyslet.")
    rid=str(row.get("panel_row_id"));bs=brand_state[(brand_state.panel_row_id.astype(str)==rid)&(brand_state.brand.astype(str).str.casefold()==str(brand).casefold())]
    if bs.empty:raise ValueError("Brand-specific simulation blocked: respondent nemá brand state.")
    return {"respondent_id":rid,"brand":brand,"category":category,"generic_background":{"media_orientation":row.get("old_new_media_orientation_1_10"),"price_sensitivity":row.get("price_sensitivity_1_10"),"research_orientation":row.get("research_orientation_1_10"),"advertising_skepticism":row.get("advertising_skepticism_1_10"),"reactance":row.get("reactance_1_10"),"profile_confidence":row.get("profile_confidence_0_1")},"brand_state":bs.iloc[0].to_dict(),"current_state":current_state or {},"contract":"BACKGROUND→EXPOSURE→ATTENTION→PROCESSING→RESPONSE→UPDATED_STATE"}
