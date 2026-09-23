#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from data_contract import contract,panel_path
ROOT=Path(__file__).resolve().parent

def main(argv=None):
 ap=argparse.ArgumentParser(); ap.add_argument('--panel',default=str(panel_path())); ap.add_argument('--out',default=str(ROOT/'COHERENCE_AUDIT_v17_1.csv')); a=ap.parse_args(argv)
 c=contract(); d=pd.read_csv(a.panel,low_memory=False,dtype={'occupation_isco08':'string'}); rows=[]
 def ck(name,cond,value,expected,kind='STRUCTURAL'):
  rows.append({'check':name,'status':'PASS' if bool(cond) else 'FAIL','value':value,'expected':expected,'kind':kind})
 ck('rows',len(d)==int(c['rows']),len(d),c['rows'])
 ck('columns',len(d.columns)==int(c['columns']),len(d.columns),c['columns'])
 ck('unique_panel_row_id',d.panel_row_id.nunique()==len(d),d.panel_row_id.nunique(),len(d))
 ck('no_legacy_D_P',not any(x.startswith(('D_','P_')) for x in d.columns),sum(x.startswith(('D_','P_')) for x in d.columns),0)
 # hard same-person/coherence rules
 age=pd.to_numeric(d.vek,errors='coerce')
 src=d.core_source.astype(str)
 bad=((age<=65)&~src.str.startswith('PIAAC'))|((age>=66)&~src.str.startswith('ISSP'))
 ck('core_age_source_contract',bad.sum()==0,int(bad.sum()),0)
 st=d.zamestnani_status.astype(str)
 ck('current_occupation_only_employed',(~(d.occupation_reference.eq('current') & ~st.eq('employed'))).all(),int((d.occupation_reference.eq('current') & ~st.eq('employed')).sum()),0)
 hh=pd.to_numeric(d.velikost_domacnosti,errors='coerce'); co=pd.to_numeric(d.get('partner_cohabiting'),errors='coerce')
 ck('cohabiting_partner_household_ge2',(~(co.eq(1)&hh.lt(2))).all(),int((co.eq(1)&hh.lt(2)).sum()),0)
 kids=pd.to_numeric(d.pocet_deti_celkem,errors='coerce')
 badkids=kids.isin([97,98,99,997,998,999])
 ck('children_missing_codes_not_substantive',badkids.sum()==0,int(badkids.sum()),0)
 # income semantic check only where absolute definitions are comparable in same ISSP core
 pi=pd.to_numeric(d.prijem_osobni_mesicni,errors='coerce'); hi=pd.to_numeric(d.prijem_domacnosti_mesicni,errors='coerce')
 comp=pi.notna()&hi.notna(); over=comp&(pi>hi+1e-9)
 ck('personal_income_not_above_household_when_comparable',over.sum()==0,int(over.sum()),0)
 # isco hierarchy including leading zero
 occ=d.occupation_isco08.fillna('').astype(str).str.replace(r'\.0$','',regex=True); maj=pd.to_numeric(d.occupation_major,errors='coerce'); two=pd.to_numeric(d.occupation_2digit,errors='coerce')
 valid=occ.str.match(r'^\d{2,4}$')
 expmaj=pd.to_numeric(occ.where(valid).str[0],errors='coerce'); exptwo=pd.to_numeric(occ.where(valid).str[:2],errors='coerce')
 badisco=valid & ((maj!=expmaj)|((occ.str.len()>=2)&two.notna()&(two!=exptwo)))
 ck('isco_hierarchy',badisco.sum()==0,int(badisco.sum()),0)
 zero=occ.str.match(r'^0[13]',na=False)
 ck('isco_leading_zero_preserved',((maj[zero]==0)|maj[zero].isna()).all(),int(zero.sum()),'all 01/03 codes major 0')
 # profile technical
 pc=pd.to_numeric(d.profile_confidence_0_1,errors='coerce')
 ck('profile_confidence_range',pc.dropna().between(0,1).all(),f'{pc.min():.4f}..{pc.max():.4f}','0..1')
 ck('brand_specific_background_fail_closed',pd.to_numeric(d.brand_specific_background_ready,errors='coerce').fillna(0).eq(0).all(),int(pd.to_numeric(d.brand_specific_background_ready,errors='coerce').fillna(0).sum()),0)
 # weights
 for role,wc in c['weights'].items():
  x=pd.to_numeric(d[wc],errors='coerce'); valid=x.dropna(); ok=valid.ge(0).all() and valid.sum()>0 and (role=='party_2021_aggregate' or x.notna().all()); ck('weight_'+role,ok,round(float(valid.sum()),3),'>0 nonnegative; party aggregate may be NA outside eligible historical voter universe','WEIGHT')
 # Census broad structural target remains preserved by original 2021 weight.
 if (ROOT/'BACKBONE_CENSUS_2021_TARGETS.csv').exists():
  t=pd.read_csv(ROOT/'BACKBONE_CENSUS_2021_TARGETS.csv')
  x=d.groupby(['vek_skupina','pohlavi','kraj'],dropna=False).vaha_kalibrovana.sum().reset_index(name='observed').rename(columns={'vek_skupina':'ageband'})
  m=t.merge(x,on=['ageband','pohlavi','kraj'],how='left'); err=(m.population_2021-m.observed.fillna(0)).abs().max()
  ck('census2021_ageband_sex_kraj',err<1e-3,float(err),'<0.001','CALIBRATION')
 if (ROOT/'CENSUS_LABOUR_FORCE_TARGETS_v17.csv').exists():
  t=pd.read_csv(ROOT/'CENSUS_LABOUR_FORCE_TARGETS_v17.csv'); x=d.groupby(['vek_skupina','pohlavi','pracovni_sila']).vaha_kalibrovana.sum().reset_index(name='observed'); m=t.merge(x,on=['vek_skupina','pohlavi','pracovni_sila'],how='left'); err=(m.target_population-m.observed.fillna(0)).abs().max()
  ck('census2021_labour_force',err<2.0,float(err),'<2 persons absolute (rounding legacy)','CALIBRATION')
 # respondent audit and cross-block contract
 ra=pd.read_csv(ROOT/c['respondent_audit']); hard=ra.audit_status.astype(str).str.contains('FAIL',case=False,na=False).sum(); ck('respondent_audit_no_hard_fail',hard==0,int(hard),0)
 joint=json.loads((ROOT/c['core_joint_status']).read_text(encoding='utf-8')); ck('core_joint_structural_status',joint.get('status')=='COHERENT_CORE_MATCHED_BLOCKS',joint.get('status'),'COHERENT_CORE_MATCHED_BLOCKS')
 ck('cross_block_same_person_false',not bool(joint.get('cross_block_same_person_joint')),joint.get('cross_block_same_person_joint'),False)
 ck('external_holdout_pending',joint.get('prediction_validation_status')=='EXTERNAL_HOLDOUT_PENDING',joint.get('prediction_validation_status'),'EXTERNAL_HOLDOUT_PENDING')
 out=pd.DataFrame(rows); out.to_csv(a.out,index=False,encoding='utf-8-sig'); fail=int((out.status=='FAIL').sum()); print(json.dumps({'version':'17.1.2','passed':int((out.status=='PASS').sum()),'failed':fail,'out':a.out},ensure_ascii=False)); return 1 if fail else 0
if __name__=='__main__': raise SystemExit(main())
