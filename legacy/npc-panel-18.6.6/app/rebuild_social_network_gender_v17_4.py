from __future__ import annotations
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parent
IN=ROOT/'FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz'
OUT=ROOT/'FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz'
AUDIT=ROOT/'remediation'/'T2_social_network_rebuild.json'
SEED=20260820
AGES=['18-24','25-34','35-44','45-54','55-64','65-74','75+']
TARGET_GENDER_GAP=.07
GATED_SOCIAL_FIELDS=['social_media_minutes_day','social_media_intensity_1_10','facebook_minutes_day','instagram_minutes_day','tiktok_minutes_day','youtube_minutes_day','whatsapp_minutes_day','messenger_minutes_day','x_minutes_day','news_social_weekly']
def sha256_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def wpct(df,mask):
 g=df[mask & df.social_network_user_2025.notna()];w=pd.to_numeric(g.vaha_strukturalni_2025,errors='coerce').fillna(0).to_numpy(float);x=pd.to_numeric(g.social_network_user_2025,errors='coerce').fillna(0).to_numpy(float)
 return float(np.average(x,weights=w)) if len(g) and w.sum()>0 else float('nan')
def _stable_rank(ids,salt):return np.array([int(hashlib.sha256(f'{SEED}|{salt}|{x}'.encode()).hexdigest()[:16],16) for x in ids.astype(str)],dtype=np.uint64)
def choose_near_weight(df,candidates,target,salt):
 if target<=0 or len(candidates)==0:return [],0.0
 c=df.loc[candidates,['panel_row_id','vaha_strukturalni_2025']].copy();c['_rank']=_stable_rank(c.panel_row_id,salt);c=c.sort_values('_rank');weights=pd.to_numeric(c.vaha_strukturalni_2025,errors='coerce').fillna(0).clip(lower=0)
 sel=[];total=0.;remain=[]
 for idx,w in zip(c.index,weights):
  w=float(w)
  if total+w<=target:sel.append(int(idx));total+=w
  else:remain.append((int(idx),w))
 best=(abs(target-total),None,total)
 for idx,w in remain:
  err=abs(target-(total+w))
  if err<best[0]:best=(err,idx,total+w)
 if best[1] is not None:sel.append(int(best[1]));total=float(best[2])
 return sel,total
def allocate(df):
 w=pd.to_numeric(df.vaha_strukturalni_2025,errors='coerce').fillna(0);sexw=df.groupby('pohlavi').vaha_strukturalni_2025.sum();tw=float(w.sum());overall=float(np.average(df.social_network_user_2025,weights=w));cm=wpct(df,df.pohlavi.eq('muž'));cf=wpct(df,df.pohlavi.eq('žena'));fs=float(sexw['žena']/tw);tm=overall-fs*TARGET_GENDER_GAP;tf=tm+TARGET_GENDER_GAP;total=(cm-tm)*float(sexw['muž'])
 cellw=df.groupby(['vek_skupina','pohlavi']).vaha_strukturalni_2025.sum();cur={(a,s):wpct(df,df.vek_skupina.eq(a)&df.pohlavi.eq(s)) for a in AGES for s in ['muž','žena']};mins=[];caps=[]
 for a in AGES:
  wm,wf=float(cellw[a,'muž']),float(cellw[a,'žena']);pm,pf=cur[a,'muž'],cur[a,'žena'];dmin=max(0.,(pm-pf)/(1/wm+1/wf));mp=float(df.loc[df.vek_skupina.eq(a)&df.pohlavi.eq('muž')&~df.is_student.fillna(False).astype(bool)&df.social_network_user_2025.eq(1),'vaha_strukturalni_2025'].sum());fp=float(df.loc[df.vek_skupina.eq(a)&df.pohlavi.eq('žena')&~df.is_student.fillna(False).astype(bool)&df.social_network_user_2025.eq(0),'vaha_strukturalni_2025'].sum());mins.append(dmin);caps.append(min(mp,fp))
 if sum(caps)+1e-6<total:raise RuntimeError('Insufficient support')
 cmw=np.array([float(cellw[a,'muž']) for a in AGES]);cfw=np.array([float(cellw[a,'žena']) for a in AGES]);obj=lambda d:float(np.sum((d/cmw)**2+(d/cfw)**2));x0=np.array(mins,float);rem=total-x0.sum();avail=np.maximum(np.array(caps)-x0,0)
 if rem>0:x0+=rem*avail/avail.sum();x0=np.minimum(x0,np.array(caps));rem=total-x0.sum()
 if rem>1e-8:
  for i in np.argsort(-(np.array(caps)-x0)):
   add=min(rem,caps[i]-x0[i]);x0[i]+=add;rem-=add
   if rem<=1e-8:break
 res=minimize(obj,x0,method='SLSQP',bounds=list(zip(mins,caps)),constraints=[{'type':'eq','fun':lambda d:float(d.sum()-total)}],options={'ftol':1e-12,'maxiter':10000})
 if not res.success:raise RuntimeError(res.message)
 return {a:float(res.x[i]) for i,a in enumerate(AGES)},{'overall_prevalence_preserved':overall,'current_male':cm,'current_female':cf,'target_male':tm,'target_female':tf,'target_gap':TARGET_GENDER_GAP,'transfer_weight_total':total}
def main():
 df=pd.read_csv(IN,low_memory=False,dtype={'occupation_isco08':'string'});before=df.copy();transfer,meta=allocate(df);changes=[]
 for age in AGES:
  target=transfer[age];mi=df.index[df.vek_skupina.eq(age)&df.pohlavi.eq('muž')&~df.is_student.fillna(False).astype(bool)&df.social_network_user_2025.eq(1)];fi=df.index[df.vek_skupina.eq(age)&df.pohlavi.eq('žena')&~df.is_student.fillna(False).astype(bool)&df.social_network_user_2025.eq(0)];ms,wm=choose_near_weight(df,mi,target,f'{age}|M10');fs,wf=choose_near_weight(df,fi,target,f'{age}|F01')
  if ms:
   df.loc[ms,'social_network_user_2025']=0
   for c in GATED_SOCIAL_FIELDS:
    if c in df.columns:df.loc[ms,c]=1 if c.endswith('_1_10') else 0
  if fs:
   pool=df.index[df.vek_skupina.eq(age)&df.pohlavi.eq('žena')&~df.is_student.fillna(False).astype(bool)&df.social_network_user_2025.eq(1)&~df.index.isin(fs)]
   pdx=df.loc[pool,['panel_row_id']].copy();pdx['_rank']=_stable_rank(pdx.panel_row_id,f'{age}|PROFILE');order=list(pdx.sort_values('_rank').index)
   for j,idx in enumerate(fs):
    src=order[j%len(order)];df.at[idx,'social_network_user_2025']=1
    for c in GATED_SOCIAL_FIELDS:
     if c in df.columns:df.at[idx,c]=df.at[src,c]
  changes.append({'age':age,'target_transfer_weight':target,'male_flipped_n':len(ms),'female_flipped_n':len(fs)})
 st=before.is_student.fillna(False).astype(bool);assert np.array_equal(before.loc[st,'social_network_user_2025'].to_numpy(),df.loc[st,'social_network_user_2025'].to_numpy())
 df.to_csv(OUT,index=False,compression='gzip')
 audit={'status':'PASS_GENERATOR_PATCH','base_panel':IN.name,'output_panel':OUT.name,'base_sha256':sha256_file(IN),'output_sha256':sha256_file(OUT),**meta,'after_male':wpct(df,df.pohlavi.eq('muž')),'after_female':wpct(df,df.pohlavi.eq('žena')),'after_gap':wpct(df,df.pohlavi.eq('žena'))-wpct(df,df.pohlavi.eq('muž')),'students_unchanged':True,'changes':changes,'method_note':'Constrained modeled assignment; not external predictive validation.'}
 AUDIT.parent.mkdir(exist_ok=True);AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(audit,ensure_ascii=False,indent=2)[:2000])
if __name__=='__main__':main()
