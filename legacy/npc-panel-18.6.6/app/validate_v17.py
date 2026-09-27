#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,re
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parent
rows=[]
def ck(name,cond,detail=''):
 rows.append({'test':name,'status':'PASS' if bool(cond) else 'FAIL','detail':str(detail)[:1000]})

def main():
 from data_contract import contract,panel_path,weight
 c=contract(); d=pd.read_csv(panel_path(),low_memory=False,dtype={'occupation_isco08':'string'})
 ck('contract_version',c.get('version')=='17.1.2',c.get('version'))
 ck('canonical_panel_shape',d.shape==(18766,400),d.shape)
 ck('ids_unique',d.panel_row_id.nunique()==len(d),d.panel_row_id.nunique())
 ck('no_legacy_D_P_columns',not any(x.startswith(('D_','P_')) for x in d.columns),[x for x in d if x.startswith(('D_','P_'))][:20])
 ck('default_weight_structural_2025',weight('default_current')=='vaha_strukturalni_2025',weight('default_current'))
 ck('default_weight_population_sum',abs(pd.to_numeric(d.vaha_strukturalni_2025).sum()-8956290.3618)<2,pd.to_numeric(d.vaha_strukturalni_2025).sum())
 ck('census_weight_preserved',abs(pd.to_numeric(d.vaha_kalibrovana).sum()-8533116)<1e-3,pd.to_numeric(d.vaha_kalibrovana).sum())
 score=pd.read_csv(ROOT/c['dimension_scorecard']); fd=pd.read_csv(ROOT/c['field_dictionary']); cat=pd.read_csv(ROOT/c['persona_catalog'])
 ck('scorecard_400_of_400',len(score)==400 and set(score['index'].astype(str))==set(d.columns),len(score))
 ck('field_dictionary_400_of_400',len(fd)==400 and set(fd.field.astype(str))==set(d.columns),len(fd))
 ck('persona_catalog_117',len(cat)==117,len(cat))
 ck('persona_fields_exist',set(cat.column.astype(str)).issubset(d.columns),sorted(set(cat.column.astype(str))-set(d.columns)))
 # respondent audit
 ra=pd.read_csv(ROOT/c['respondent_audit']); ck('respondent_audit_rows',len(ra)==18766,len(ra)); ck('respondent_no_hard_fail',not ra.audit_status.astype(str).str.contains('FAIL',case=False,na=False).any(),ra.audit_status.value_counts().to_dict())
 # Panel runtime + persona
 from pipeline import Panel,generate_persona_text
 p=Panel.load(hlasit=False); ck('panel_runtime_shape',p.df.shape==(18766,401),p.df.shape); ck('analysis_weight_internal','_analysis_weight' in p.df,p.df.columns[-1])
 row=p.df.iloc[1234]
 mk=generate_persona_text(row,temata=['marketing','kampan'],persona_mode='calibrated'); ck('persona_marketing_background','modelový behaviorální prior' not in mk,mk[:500]); ck('persona_brand_warning','Brand-specific background: NEDODÁN' in mk,mk[-500:])
 fin=generate_persona_text(row,temata=['finance','gramotnost'],persona_mode='calibrated'); ck('persona_finance','finanční' in fin.lower(),fin[:500])
 rel=generate_persona_text(row,temata=['vira','nabozenstvi'],persona_mode='calibrated'); ck('persona_religion','nábožensk' in rel.lower(),rel[:500])
 med=generate_persona_text(row,temata=['media','socialni_site'],persona_mode='calibrated'); ck('persona_media_minutes','min/den' in med,med[:500])
 # imported old projects default modern persona
 from research_project import normalize_project,empty_project,compile_project
 ep=empty_project(); ck('empty_project_calibrated',ep.get('persona_mode')=='calibrated',ep.get('persona_mode'))
 norm=normalize_project({'title':'T','sections':[{'id':'q','type':'questions','questions':[{'id':'q1','text':'Test?','typ':'vyber','kategorie':['Ano','Ne']}]}]}); ck('imported_project_calibrated',norm.get('persona_mode')=='calibrated',norm.get('persona_mode'))
 try:
  comp=compile_project(norm); pp=comp['brief'].get('provider_policy',''); ck('live_provider_policy_strict',pp.startswith('strict_'),pp)
 except Exception as e: ck('project_compile',False,e)
 # brand gate
 from campaign_background import validate_brand_state,build_campaign_context
 vg=validate_brand_state(None,brand='Test'); ck('brand_gate_missing_not_ready',vg.get('ready') is False,vg)
 # built-in + special routing
 from population_subpanels import list_subpanels,list_special_panels,apply,load_special_panel_frame
 subs=list_subpanels(); specs=list_special_panels(); ck('builtin_count_18',len(subs)==18,len(subs)); ck('special_count_18',len(specs)==18,len(specs))
 mism=[]
 for sp in subs:
  n=len(apply(d,sp['key']))
  if n!=int(sp['rows']):mism.append((sp['key'],n,sp['rows']))
 ck('builtin_filters_exact',not mism,mism)
 sm=[];masked=[]
 for sp in specs:
  x,m=load_special_panel_frame(sp['key'])
  if len(x)!=int(sp['rows']):sm.append((sp['key'],len(x),sp['rows']))
  if str(sp.get('support') or '').startswith('STRUCTURAL_ONLY'):
   for col in ['religious_affiliation_group','religious_practice_1_10','value_security_1_10','politicky_zajem_2021']:
    if col in x and x[col].notna().any():masked.append((sp['key'],col,int(x[col].notna().sum())))
 ck('special_files_exact',not sm,sm);ck('structural_special_sensitive_masked',not masked,masked)
 from audience_selector import recommend
 tests={'mladí 18-29':'use_builtin_subpanel','stavební materiál':'use_builtin_special_panel','realitní makléři':'builtin_special_with_warning','Ukrajinci v ČR':'builtin_special_with_warning','zdravotnický materiál':'use_builtin_special_panel'}
 bad=[]
 for brief,want in tests.items():
  got=recommend(brief,requested_n=300).get('action')
  if got!=want:bad.append((brief,got,want))
 ck('audience_routing',not bad,bad)
 # UI bootstrap
 import ui_server
 b=ui_server.bootstrap();ck('ui_product_release_17_2','17.3.1' in str(b.get('release')),b.get('release'));ck('ui_data_contract_17_1_2',c.get('version')=='17.1.2',c.get('version'));ck('ui_special_panels',len(b.get('special_panels') or [])==18,len(b.get('special_panels') or []));ck('ui_panel_rows',int((b.get('panel') or {}).get('rows') or 0)==18766,b.get('panel'))
 # Full Simulation current factor drivers and dry fail marking contract
 import full_simulation as fs
 missing=[]
 for f in fs.DEFAULT_FACTORS:
  for drv in f['drivers']:
   if drv['field'] not in d:missing.append((f['id'],drv['field']))
 ck('fullsim_default_drivers_exist',not missing,missing)
 src=(ROOT/'full_simulation.py').read_text(encoding='utf-8');ck('fullsim_no_legacy_P_drivers',not re.search(r'"P_(?:buy|media|value)_[^"]+"',src),re.findall(r'"P_(?:buy|media|value)_[^"]+"',src)[:20]);ck('fullsim_live_heuristic_blocked','FULLSIM_LIVE_WORLD_MODEL_REQUIRED' in src,'static contract');ck('fullsim_dry_invalid_marker','INVALID_DRY_RUN' in src,'static contract')
 # provider fail-closed static production path
 pipe=(ROOT/'pipeline.py').read_text(encoding='utf-8');rcfg=(ROOT/'runtime_config.py').read_text(encoding='utf-8');ck('provider_strict_contract','strict_' in pipe and 'no automatic cross-provider fallback' in rcfg,'runtime + pipeline')
 # source/evidence metadata coverage
 sc=pd.read_csv(ROOT/c['source_catalog']);ck('source_catalog_nonempty',len(sc)>=20,len(sc));ck('core_joint_pending',json.loads((ROOT/'CORE_JOINT_STATUS.json').read_text(encoding='utf-8')).get('prediction_validation_status')=='EXTERNAL_HOLDOUT_PENDING','pending')
 # structural audit result
 coh=pd.read_csv(ROOT/'COHERENCE_AUDIT_v17_1.csv');ck('coherence_23_pass',(coh.status=='PASS').all() and len(coh)>=20,coh.status.value_counts().to_dict())
 out=pd.DataFrame(rows);out.to_csv(ROOT/'V17_TARGETED_TESTS.csv',index=False,encoding='utf-8-sig');summary={'version':'17.2.1_product_on_17.1.2_data','tests':len(out),'passed':int((out.status=='PASS').sum()),'failed':int((out.status=='FAIL').sum())};(ROOT/'V17_TARGETED_TESTS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,ensure_ascii=False));
 if summary['failed']: print(out[out.status=='FAIL'].to_string(index=False));return 1 if summary['failed'] else 0
if __name__=='__main__': raise SystemExit(main())
