#!/usr/bin/env python3
from __future__ import annotations
import compileall,json,subprocess,sys,re
from pathlib import Path
import pandas as pd,numpy as np
from data_contract import contract,panel_path
from edition_config import build_version
ROOT=Path(__file__).resolve().parent

def _chk(name,cond,detail,rows):rows.append({'check':name,'status':'PASS' if cond else 'FAIL','detail':str(detail)});return bool(cond)
def main()->int:
 c=contract();rows=[];allok=True
 # Compile production runtime only; legacy/source evidence is non-executable.
 for py in ROOT.glob('*.py'): allok &= _chk('compile:'+py.name,compileall.compile_file(str(py),quiet=1),py.name,rows)
 d=pd.read_csv(panel_path(),low_memory=False,dtype={'occupation_isco08':'string'})
 allok &= _chk('panel_rows',len(d)==int(c['rows']),len(d),rows)
 allok &= _chk('panel_columns',len(d.columns)==int(c['columns']),len(d.columns),rows)
 allok &= _chk('unique_ids',d.panel_row_id.nunique()==len(d),d.panel_row_id.nunique(),rows)
 allok &= _chk('no_legacy_D_P',not any(x.startswith(('D_','P_')) for x in d.columns),[x for x in d.columns if x.startswith(('D_','P_'))][:10],rows)
 score=pd.read_csv(ROOT/c['dimension_scorecard']);allok &= _chk('scorecard_complete',set(score['index'].astype(str))==set(d.columns),len(score),rows)
 fd=pd.read_csv(ROOT/c['field_dictionary']);allok &= _chk('field_dictionary_complete',set(fd.field.astype(str))==set(d.columns),len(fd),rows)
 cat=pd.read_csv(ROOT/c['persona_catalog']);missing=[x for x in cat.column.astype(str) if x not in d];allok &= _chk('persona_catalog_fields',not missing,missing[:20],rows)
 ra=pd.read_csv(ROOT/c['respondent_audit']);allok &= _chk('respondent_audit_no_hard_fail',not ra.audit_status.astype(str).str.contains('FAIL').any(),ra.audit_status.value_counts().to_dict(),rows)
 from population_subpanels import list_subpanels,apply,list_special_panels,load_special_panel_frame
 mism=[]
 for sp in list_subpanels():
  try:n=len(apply(d,sp['key']));
  except Exception:n=-1
  if n!=int(sp.get('rows') or -2):mism.append((sp['key'],n,sp.get('rows')))
 allok &= _chk('builtin_subpanels_match',not mism,mism,rows)
 sm=[]
 for sp in list_special_panels():
  try:x,m=load_special_panel_frame(sp['key']);n=len(x)
  except Exception as e:n=-1;sm.append((sp['key'],str(e)));continue
  if n!=int(sp.get('rows') or -2):sm.append((sp['key'],n,sp.get('rows')))
 allok &= _chk('special_panels_match',not sm,sm,rows)
 # Sensitive group protection.
 sens=[]
 for sp in list_special_panels():
  if str(sp.get('support') or '').startswith('STRUCTURAL_ONLY'):
   x,_=load_special_panel_frame(sp['key'])
   for col in ['religious_affiliation_group','religious_practice_1_10','value_security_1_10','politicky_zajem_2021']:
    if col in x and x[col].notna().any():sens.append((sp['key'],col))
 allok &= _chk('special_sensitive_fail_closed',not sens,sens[:20],rows)
 # campaign brand gate
 from campaign_background import validate_brand_state
 allok &= _chk('brand_specific_gate',validate_brand_state(None,brand='Test')['ready'] is False,validate_brand_state(None,brand='Test'),rows)
 # provider production calls must be fail-closed / no explicit silent fallback.
 air=(ROOT/'ai_router.py').read_text(encoding='utf-8',errors='ignore')
 allok &= _chk('provider_fail_closed','allow_fallback=False' in air or 'allow_fallback = False' in air,'static contract',rows)
 # external validation must remain pending.
 joint=json.loads((ROOT/c['core_joint_status']).read_text(encoding='utf-8'))
 allok &= _chk('external_holdout_pending',joint.get('prediction_validation_status')=='EXTERNAL_HOLDOUT_PENDING',joint.get('prediction_validation_status'),rows)
 allok &= _chk('cross_block_fail_closed',not bool(joint.get('cross_block_joint_claims_allowed')),joint.get('cross_block_joint_claims_allowed'),rows)
 # weights valid
 for role,wc in c['weights'].items():
  ok=wc in d and pd.to_numeric(d[wc],errors='coerce').fillna(0).ge(0).all() and pd.to_numeric(d[wc],errors='coerce').fillna(0).sum()>0
  allok &= _chk('weight:'+role,ok,wc,rows)
 # import smoke
 mods=['pipeline','persona_grounded','population_subpanels','audience_selector','ui_server','research_designer','full_simulation','provider_auth']
 errs=[]
 for m in mods:
  try:__import__(m)
  except Exception as e:errs.append((m,type(e).__name__,str(e)))
 allok &= _chk('import_smoke',not errs,errs,rows)
 pd.DataFrame(rows).to_csv(ROOT/'RELEASE_GATE_v17.csv',index=False,encoding='utf-8-sig')
 out={'version':build_version(),'methodology_base':'17.1.2','status':'ENGINEERING_RELEASE_EXTERNAL_HOLDOUT_PENDING' if allok else 'BLOCKED','passed':sum(x['status']=='PASS' for x in rows),'failed':sum(x['status']=='FAIL' for x in rows),'checks':rows}
 (ROOT/'RELEASE_GATE_v17.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:out[k] for k in ('version','status','passed','failed')},ensure_ascii=False))
 return 0 if allok else 1
if __name__=='__main__':raise SystemExit(main())
