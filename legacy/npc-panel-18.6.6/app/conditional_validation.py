"""Validation diagnostics for 10.13 conditional calibration.

Two diagnostics are intentionally separated:
1) category LOO: required as a regression/sensitivity check, but NOT treated as
   an independent holdout because one missing category can be partly implied by
   the national total and the remaining categories;
2) axis holdout: removes an entire published axis (age/sex/education/region)
   from fitting and asks whether the other axes recover it. This is materially
   stronger, though still not a new-year or independent-source human holdout.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
from scipy.stats import norm
from conditional_engine import TRUTH, fit_probs, _bands, _sex, _edu
from pipeline import PANEL_PATH

ROOT=Path(__file__).resolve().parent


def _weights(p): return pd.to_numeric(p['vaha_kalibrovana'],errors='coerce').fillna(1.0).to_numpy(float)

def _axis_values(p,axis):
    if axis=='vek': return _bands(p)
    if axis=='pohlavi': return _sex(p)
    if axis=='vzdelani': return _edu(p)
    if axis=='kraj': return p['kraj'].astype(str).to_numpy()
    raise KeyError(axis)

def _predict_category(p,eta,axis,cat):
    vals=_axis_values(p,axis); m=vals==cat
    if not m.any(): return None
    w=_weights(p); return 100*float(np.average(norm.cdf(eta[m]),weights=w[m]))

def category_loo(panel: pd.DataFrame, n_categories: int=30, seed: int=20260816) -> pd.DataFrame:
    candidates=[]
    for dim,spec in TRUTH.items():
        for axis in ('vek','pohlavi','vzdelani','kraj'):
            for cat,target in (spec.get(axis) or {}).items(): candidates.append((dim,axis,str(cat),float(target)))
    rng=np.random.default_rng(seed); choose=rng.choice(len(candidates),size=min(n_categories,len(candidates)),replace=False)
    rows=[]
    for ix in choose:
        dim,axis,cat,target=candidates[int(ix)]; eta=fit_probs(panel,TRUTH[dim],holdout=(axis,cat),iters=10,solve_iters=18); pred=_predict_category(panel,eta,axis,cat)
        rows.append({'dimension':dim,'axis':axis,'category':cat,'target_pct':target,'pred_pct':None if pred is None else round(pred,3),'abs_error_pp':None if pred is None else round(abs(pred-target),3)})
    return pd.DataFrame(rows)

def axis_holdout(panel: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for dim,spec in TRUTH.items():
        for axis in ('vek','pohlavi','vzdelani','kraj'):
            targets=spec.get(axis) or {}
            if len(targets)<2: continue
            eta=fit_probs(panel,spec,holdout_axis=axis,iters=10,solve_iters=18)
            errs=[]
            for cat,target in targets.items():
                pred=_predict_category(panel,eta,axis,str(cat))
                if pred is None: continue
                err=abs(pred-float(target)); errs.append(err)
                rows.append({'dimension':dim,'axis':axis,'category':str(cat),'target_pct':float(target),'pred_pct':round(pred,3),'abs_error_pp':round(err,3)})
    return pd.DataFrame(rows)


def fitted_targets(panel: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for dim,spec in TRUTH.items():
        eta=fit_probs(panel,spec,iters=14,solve_iters=22)
        # total
        w=_weights(panel); pred=100*float(np.average(norm.cdf(eta),weights=w)); target=float(spec['celkem'])
        rows.append({'dimension':dim,'axis':'celkem','category':'celkem','target_pct':target,'pred_pct':round(pred,3),'abs_error_pp':round(abs(pred-target),3)})
        for axis in ('vek','pohlavi','vzdelani','kraj'):
            for cat,target in (spec.get(axis) or {}).items():
                pred=_predict_category(panel,eta,axis,str(cat))
                if pred is not None: rows.append({'dimension':dim,'axis':axis,'category':str(cat),'target_pct':float(target),'pred_pct':round(pred,3),'abs_error_pp':round(abs(pred-float(target)),3)})
    return pd.DataFrame(rows)

def run(panel_path: str|Path=PANEL_PATH, out_dir: str|Path=ROOT) -> dict:
    p=pd.read_csv(panel_path,low_memory=False); p['w']=pd.to_numeric(p['vaha_kalibrovana'],errors='coerce').fillna(1.0)
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    loo=category_loo(p); axis=axis_holdout(p); fitted=fitted_targets(p)
    loo.to_csv(out/'CONDITIONAL_LOO_30.csv',index=False); axis.to_csv(out/'CONDITIONAL_AXIS_HOLDOUT.csv',index=False); fitted.to_csv(out/'CONDITIONAL_FITTED_TARGETS.csv',index=False)
    summary={
      'release':'10.13.0','n_truth_dimensions':len(TRUTH),
      'category_loo_n':int(len(loo)),'category_loo_mae_pp':round(float(loo.abs_error_pp.mean()),3) if len(loo) else None,
      'axis_holdout_n_cells':int(len(axis)),'axis_holdout_mae_pp':round(float(axis.abs_error_pp.mean()),3) if len(axis) else None,
      'fitted_n_cells':int(len(fitted)),'fitted_mae_pp':round(float(fitted.abs_error_pp.mean()),3) if len(fitted) else None,
      'category_loo_interpretation':'Regression/sensitivity diagnostic only; not an independent holdout because omitted categories can be partly constrained by totals and sibling categories.',
      'axis_holdout_interpretation':'Stronger conditional test: the whole demographic axis is absent from fit. Still not a new-year or independent-source human holdout.',
      'joint_status':'JOINT_UNVALIDATED'
    }
    (out/'CONDITIONAL_VALIDATION_10_13.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--panel',default=str(PANEL_PATH)); ap.add_argument('--out-dir',default=str(ROOT)); a=ap.parse_args(); print(json.dumps(run(a.panel,a.out_dir),ensure_ascii=False,indent=2))
