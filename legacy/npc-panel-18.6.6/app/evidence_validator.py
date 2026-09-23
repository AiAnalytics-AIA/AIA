from __future__ import annotations
import math,re
from typing import Any
def _norm(s):return re.sub(r'\s+',' ',str(s or '').strip()).casefold()
def _num(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except Exception:return None
def build_evidence_index(result_summary,battery_results=None):
 idx={}
 for qid,r in (result_summary.get('vysledky') or {}).items():
  if not isinstance(r,dict):continue
  m={}
  for ans,v in (r.get('celkem_pct') or {}).items():
   x=_num(v)
   if x is not None:m[f'pct:{_norm(ans)}']=x
  for src,key in [('prumer','mean'),('top2box_pct','top2box_pct'),('n','n'),('effective_n','effective_n')]:
   x=_num(r.get(src))
   if x is not None:m[key]=x
  idx[str(qid)]={'kind':'question','metrics':m,'raw':r}
 for b in battery_results or []:
  if not isinstance(b,dict) or b.get('error'):continue
  metrics={}
  for k,v in (b.get('map_metrics') or {}).items():
   x=_num(v)
   if x is not None:metrics['map:'+_norm(k)]=x
  idx['battery:'+str(b.get('id') or '')]={'kind':'battery','metrics':metrics,'raw':b}
 return idx
def resolve_metric(index,ref,metric):
 row=index.get(str(ref));m=_norm(metric)
 if not row:return None
 metrics=row.get('metrics') or {}
 if m in metrics:return _num(metrics[m])
 if m.startswith('pct|'):return _num(metrics.get('pct:'+_norm(m.split('|',1)[1])))
 if m.startswith('pct:'):return _num(metrics.get('pct:'+_norm(m.split(':',1)[1])))
 return None
def validate_claim(claim,index,tolerance=.051):
 ref=str(claim.get('evidence_ref') or '').strip();metric=str(claim.get('metric') or '').strip();stated=_num(claim.get('value'));source=resolve_metric(index,ref,metric);issues=[]
 if ref not in index:issues.append('UNKNOWN_EVIDENCE_REF')
 if source is None:issues.append('UNKNOWN_METRIC')
 if stated is None:issues.append('INVALID_VALUE')
 delta=None
 if source is not None and stated is not None:
  delta=abs(source-stated)
  if delta>tolerance:issues.append('VALUE_MISMATCH')
 return {'ok':not issues,'evidence_ref':ref,'metric':metric,'stated_value':stated,'source_value':source,'delta':delta,'issues':issues}
def validate_analysis(analysis,result_summary,battery_results=None):
 idx=build_evidence_index(result_summary,battery_results);findings=analysis.get('key_findings') or [];issues=[];checks=[];ref_total=ref_ok=0
 for group in ('research_question_answers','key_findings','implications'):
  for i,row in enumerate(analysis.get(group) or []):
   for ref in row.get('evidence_refs') or []:
    ref_total+=1
    if str(ref) in idx:ref_ok+=1
    else:issues.append({'type':'UNKNOWN_EVIDENCE_REF','owner':group,'index':i,'ref':ref})
   for c in row.get('numeric_claims') or []:
    cc=validate_claim(c,idx);cc.update({'owner':group,'index':i});checks.append(cc)
    if not cc['ok']:issues.append({'type':'NUMERIC_CLAIM_FAILED','owner':group,'index':i,'check':cc})
 num_total=len(checks);num_ok=sum(x['ok'] for x in checks);coverage=sum(bool(x.get('evidence_refs')) for x in findings)/len(findings) if findings else 0.;rr=ref_ok/ref_total if ref_total else (1. if not findings else 0.);nr=num_ok/num_total if num_total else 1.
 score=round(100*(.35*rr+.45*nr+.20*coverage),1);passed=bool(findings) and ref_ok==ref_total and num_ok==num_total and coverage>=.95 and score>=90
 return {'score':score,'passed':passed,'threshold':90,'reference_checks':ref_total,'reference_ok':ref_ok,'numeric_claims':num_total,'numeric_claims_ok':num_ok,'finding_reference_coverage':coverage,'issues':issues,'checks':checks}
