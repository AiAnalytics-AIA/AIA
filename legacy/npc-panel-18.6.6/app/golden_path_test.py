#!/usr/bin/env python3
from __future__ import annotations
import json,shutil,time
from pathlib import Path
from edition_config import build_version
VERSION=build_version()
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'remediation'/f"GOLDEN_PATH_{VERSION.replace('.', '_')}.json"
def main():
 checks=[]
 def ck(n,ok,d=''):checks.append({'check':n,'status':'PASS' if ok else 'FAIL','detail':d})
 import ui_server
 ep=(ui_server.bootstrap().get('empty_project') or {});blob=json.dumps(ep,ensure_ascii=False).lower();ck('empty_project_no_demo_hardcode',all(x not in blob for x in ('ecowall','matcha','elections')))
 from full_simulation import run_full_simulation
 spec={'topic':'Golden path','questions':[{'id':'SCENARIO_OUTCOME','text':'Jaký dopad?','kategorie':['Negativní','Beze změny','Pozitivní']}],'objective':'scenario_nowcast','domain':'general','n':50,'worlds':2,'min_worlds':2,'adaptive_worlds':False,'seed':17502,'model':'sonnet','provider':'anthropic','mode':'dry','persona_mode':'calibrated','research_enabled':False,'world_model_provider':'heuristic','include_core_baseline':False,'include_demographics_baseline':False,'diagnostic_mode':'off','save_world_overlays':False,'use_learning_profile':False,'auto_wording_stress':False}
 r=run_full_simulation(spec);d=Path(r['run_dir']);rid=r['run_id'];ck('fullsim_dry_executes',r['manifest']['worlds_executed']==2 and r['manifest']['run_status']=='INVALID_DRY_RUN',rid)
 for f in [d/'worlds/world_002_result.json',d/'worlds/world_002.json',d/'FROZEN.lock']:
  if f.exists():f.unlink()
 st=json.loads((d/'resume_state.json').read_text(encoding='utf-8'));st.update({'completed_worlds':1,'status':'WAITING_CREDITS'});(d/'resume_state.json').write_text(json.dumps(st),encoding='utf-8');spec['resume_run_id']=rid;r2=run_full_simulation(spec);ck('fullsim_resume_same_run',r2['run_id']==rid and r2['manifest'].get('resumed') is True and r2['manifest']['worlds_executed']==2);ck('fullsim_freezes_after_complete',(d/'FROZEN.lock').exists())
 from evidence_validator import validate_analysis
 sm={'vysledky':{'Q1':{'celkem_pct':{'Ano':63,'Ne':37},'n':400}}};a={'key_findings':[{'headline':'x','evidence_refs':['Q1'],'numeric_claims':[{'evidence_ref':'Q1','metric':'pct:Ano','value':63,'unit':'pct','label':'Ano'}]}],'research_question_answers':[],'implications':[]};ck('evidence_accepts_truth',validate_analysis(a,sm)['passed']);a['key_findings'][0]['numeric_claims'][0]['value']=77;ck('evidence_rejects_forgery',not validate_analysis(a,sm)['passed'])
 from validation_status import validation_tier
 vt=str(validation_tier()).upper();ck('external_validation_stays_pending','PENDING' in vt or 'UNVALID' in vt or 'NOT_VALIDATED' in vt,vt)
 from legal_gate import audit_legal
 lg=audit_legal(use_case='internal');ck('licensing_not_fake_pass',lg.get('status')!='PASS' or bool(lg.get('licensing_evidence_present')),str(lg.get('status')))
 try:shutil.rmtree(d)
 except:pass
 ok=all(c['status']=='PASS' for c in checks);obj={'kind':'npc_golden_path_v1','version':VERSION,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'status':'PASS' if ok else 'FAIL','checks':checks,'note':'Engineering/dry regression only; not predictive validation.'};OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(obj,ensure_ascii=False,indent=2));return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
