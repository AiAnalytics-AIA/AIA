"""Domain-specific readiness diagnostics for the v17 integrated population core.

Readiness is based on fields that can actually reach the production persona:
same-person measured core signals, measured derived scores, and explicitly labelled
whole matched donor blocks. It is an evidence/coverage diagnostic, not predictive validity.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parent
CATALOG_PATH=ROOT/'PERSONA_SIGNAL_CATALOG_v17.csv'
from pipeline import PANEL_PATH as _RUNTIME_PANEL_PATH
PANEL_PATH=Path(_RUNTIME_PANEL_PATH)
ROLE_WEIGHT={'MEASURED_JOINT':1.0,'MEASURED_DERIVED':0.90,'MATCHED_DONOR_BLOCK':0.72,'MATCHED_WHOLE_BLOCK_CANONICAL':0.72,'CALIBRATED_BEHAVIOR_MODEL':0.70,'CALIBRATED_MODELED_COMPOSITE':0.62,'CALIBRATED_MODELED_BINARY':0.58,'MODELED_VALUE_PROXY':0.48,'MODELED_BEHAVIOR_PRIOR':0.46}


def _freshness(year: Any, now:int=2026)->float:
    try:y=int(float(year))
    except Exception:return .55
    return max(.45,1.0-.045*max(0,now-y))


def _catalog()->pd.DataFrame:
    d=pd.read_csv(CATALOG_PATH)
    for c in ('topics','evidence_role','column','block'): d[c]=d[c].fillna('').astype(str)
    return d


def _topic_match(cell:str, topic:str)->bool:
    t=str(topic).strip().lower(); vals={x.strip().lower() for x in str(cell).split('|') if x.strip()}
    return t in vals


def readiness_for_topic(topic:str,*,panel:pd.DataFrame|None=None)->dict[str,Any]:
    topic=str(topic).strip(); d=_catalog(); d=d[d['topics'].map(lambda x:_topic_match(x,topic))].copy()
    if d.empty:
        return {'topic':topic,'score':0,'grade':'RED','n_dimensions':0,'bridge_share':0.0,'own_estimate_share':0.0,
                'nonmissing_mean':None,'evidence_roles':{},'reason':'no production persona signals mapped to topic'}
    if panel is None: panel=pd.read_csv(PANEL_PATH,low_memory=False)
    vals=[]; covs=[]; usable=[]
    for r in d.itertuples(index=False):
        col=str(r.column); role=str(r.evidence_role); cov=float(panel[col].notna().mean()) if col in panel.columns else 0.0
        if cov<=0: continue
        covs.append(cov); usable.append(role)
        priority=float(r.priority) if pd.notna(r.priority) else 1.0
        vals.append(ROLE_WEIGHT.get(role,.45)*_freshness(r.wave)*(0.55+0.45*cov)*min(1.12,max(.75,priority)))
    if not vals:
        return {'topic':topic,'score':0,'grade':'RED','n_dimensions':int(len(d)),'usable_signals':0,'bridge_share':0.0,'own_estimate_share':0.0,
                'nonmissing_mean':0.0,'evidence_roles':{},'reason':'mapped signals are absent from current runtime panel'}
    # Multiple independent signals increase practical readiness, but cannot turn matching into measured same-person truth.
    base=float(np.mean(vals)); breadth=min(1.0,0.78+0.055*len(vals)); score=round(100*base*breadth,1)
    grade='GREEN' if score>=70 else 'YELLOW' if score>=50 else 'RED'
    roles=pd.Series(usable).value_counts().to_dict(); total=max(1,len(usable))
    return {'topic':topic,'score':score,'grade':grade,'n_dimensions':int(len(d)),'usable_signals':int(len(vals)),
            'bridge_share':round(float(roles.get('MATCHED_DONOR_BLOCK',0))/total,3),'own_estimate_share':0.0,
            'nonmissing_mean':round(float(np.mean(covs)),3),'evidence_roles':{str(k):int(v) for k,v in roles.items()},
            'reason':'v15.2 evidence/coverage score from production persona catalog; NOT predictive-validity score'}


def readiness_for_topics(topics:list[str],*,panel:pd.DataFrame|None=None)->dict[str,Any]:
    topics=list(dict.fromkeys(str(x).strip() for x in topics if str(x).strip()))
    if panel is None: panel=pd.read_csv(PANEL_PATH,low_memory=False)
    rows=[readiness_for_topic(t,panel=panel) for t in topics]; minimum=min((r['score'] for r in rows),default=0)
    return {'domains':rows,'minimum_score':minimum,'overall':'GREEN' if minimum>=70 else 'YELLOW' if minimum>=50 else 'RED'}
