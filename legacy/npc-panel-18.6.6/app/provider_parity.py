from __future__ import annotations
import json,time,math
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parent
STATUS=ROOT/'data'/'provider_parity.json'
DEFAULT_TOLERANCES={'aggregate_mean_abs_pp':3.0,'ranking_agreement':0.90,'variance_ratio_low':0.80,'variance_ratio_high':1.25,'schema_failure_rate':0.02}
def load_status()->dict[str,Any]:
 if STATUS.is_file():
  try:return json.loads(STATUS.read_text(encoding='utf-8'))
  except Exception:pass
 return {'status':'NOT_RUN','economy_respondent_default_allowed':False,'tolerances':DEFAULT_TOLERANCES}
def record_result(metrics:dict[str,Any],*,reference_provider:str,candidate_provider:str,candidate_model:str,batch_size:int=1,tolerances=None)->dict[str,Any]:
 t={**DEFAULT_TOLERANCES,**(tolerances or {})}
 checks={
  'aggregate':float(metrics.get('aggregate_mean_abs_pp',999))<=t['aggregate_mean_abs_pp'],
  'ranking':float(metrics.get('ranking_agreement',0))>=t['ranking_agreement'],
  'variance':t['variance_ratio_low']<=float(metrics.get('variance_ratio',0))<=t['variance_ratio_high'],
  'schema':float(metrics.get('schema_failure_rate',1))<=t['schema_failure_rate'],
 }
 passed=all(checks.values())
 out={'status':'PASS' if passed else 'FAIL','economy_respondent_default_allowed':passed,'reference_provider':reference_provider,'candidate_provider':candidate_provider,'candidate_model':candidate_model,'batch_size':int(batch_size),'metrics':metrics,'checks':checks,'tolerances':t,'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S')}
 STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return out
