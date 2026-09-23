"""Fail-closed evidence tier gate for NPC Panel 10.13.

Tier A: conditional + independently validated joint evidence (currently none).
Tier B: documented marginal/conditional evidence; aggregate and demographic
        breakdowns may be shown with wide uncertainty, but must not be promoted
        to an individual-trait or segment-ground-truth claim.
Tier C: insufficient evidence for a client quantitative claim; internal
        experimental persona use is allowed only with explicit synthetic labels.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
import pandas as pd

ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/'CALIBRATION_REGISTRY.csv'


def load_registry(path: str|Path=REGISTRY) -> pd.DataFrame:
    df=pd.read_csv(path)
    required={'dimension','column','tier','production_default','joint_validated'}
    missing=required-set(df.columns)
    if missing: raise ValueError(f'Calibration registry missing columns: {sorted(missing)}')
    if df['dimension'].duplicated().any(): raise ValueError('Duplicate dimension in calibration registry')
    return df


def _normalize(name: str) -> str:
    x=str(name)
    if x.startswith('D_') or x.startswith('M_'): x=x[2:]
    return x


def dimension_record(name: str, registry: pd.DataFrame|None=None) -> dict:
    df=registry if registry is not None else load_registry()
    dim=_normalize(name); hit=df[df.dimension.astype(str)==dim]
    if hit.empty:
        return {'dimension':dim,'tier':'C','production_default':False,'joint_validated':False,
                'client_claim_mode':'REFUSE','reason':'dimension_missing_from_registry'}
    return hit.iloc[0].to_dict()


def dimension_tier(name: str, registry: pd.DataFrame|None=None) -> str:
    return str(dimension_record(name,registry).get('tier','C')).upper()


def check_claim(dimensions: Iterable[str], use_case: str='aggregate', registry: pd.DataFrame|None=None) -> dict:
    """Evaluate whether dimensions may support the requested client-facing claim.

    use_case values: aggregate, demographic_breakdown, segmentation, persona,
    individual, internal_experimental.
    """
    df=registry if registry is not None else load_registry(); recs=[dimension_record(d,df) for d in dimensions]
    tiers=[str(r.get('tier','C')).upper() for r in recs]
    use=str(use_case).lower()
    if use=='internal_experimental':
        return {'allowed':True,'mode':'EXPERIMENTAL','tiers':tiers,'records':recs,
                'warning':'Synthetic/derived traits; not a client ground-truth claim.'}
    if any(t=='C' for t in tiers):
        return {'allowed':False,'mode':'REFUSE','tiers':tiers,'records':recs,
                'reason':'At least one dimension is Tier C or absent from the registry.'}
    if use in {'segmentation','persona','individual'}:
        ok=all(t=='A' and bool(r.get('joint_validated')) for t,r in zip(tiers,recs))
        return {'allowed':ok,'mode':'RECOMMEND' if ok else 'REFUSE','tiers':tiers,'records':recs,
                'reason':None if ok else 'Legacy dimension-level individual claims require independently validated Tier A; the v15.2 population persona no longer uses D_* as its production core.'}
    # aggregate and demographic breakdown: Tier B is display-only.
    return {'allowed':True,'mode':'JUST_SHOW' if any(t=='B' for t in tiers) else 'RECOMMEND','tiers':tiers,'records':recs,
            'warning':'Tier B: show with interval/evidence rating; do not turn it into an individual or targeting claim.' if any(t=='B' for t in tiers) else None}


def registry_summary(registry: pd.DataFrame|None=None) -> dict:
    df=registry if registry is not None else load_registry()
    return {'n_dimensions':int(len(df)),'tiers':{str(k):int(v) for k,v in df.tier.value_counts().to_dict().items()},
            'conditional_calibrated':int((df.calibration_status=='1_CONDITIONAL_CALIBRATED').sum()),
            'tier_a':int((df.tier=='A').sum()),'joint_validated':bool(df.joint_validated.fillna(False).astype(bool).any())}
