from __future__ import annotations

"""Deterministic Society Intelligence for NPC Panel.

Numbers are computed from the explicitly selected bundled population panel.
No LLM is required for numeric results.  MODELLED population evidence is never
presented as observed fieldwork, and association is never relabelled causality.
"""

import hashlib, json, math, sqlite3, time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
DB_PATH=ROOT/'data'/'society_insights.sqlite'
_CACHE:dict[str,Any]={}


def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def _connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    cx=sqlite3.connect(DB_PATH,timeout=20);cx.row_factory=sqlite3.Row
    cx.executescript('''
    CREATE TABLE IF NOT EXISTS society_settings(key TEXT PRIMARY KEY,value_json TEXT NOT NULL,updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS society_briefs(brief_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,population_mode TEXT NOT NULL,panel_sha256 TEXT,payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS society_segment_runs(run_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,population_mode TEXT NOT NULL,payload_json TEXT NOT NULL);
    ''');cx.commit();return cx

def _sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def _panel(mode='LIVE')->tuple[pd.DataFrame,Path]:
    from population_context import panel_path_for
    p=panel_path_for(mode)
    key=f'{mode}:{p}:{p.stat().st_mtime_ns}'
    if key not in _CACHE:
        _CACHE.clear();_CACHE[key]=pd.read_csv(p,low_memory=False)
    return _CACHE[key],p

def _label(c:str)->str:
    repl={
      'price_sensitivity_1_10':'Citlivost na cenu','deal_proneness_1_10':'Vyhledávání slev','premium_willingness_1_10':'Ochota připlatit',
      'social_media_intensity_1_10':'Intenzita sociálních sítí','digital_communication_intensity_1_10':'Digitální komunikace',
      'online_information_intensity_1_10':'Online informace','online_entertainment_intensity_1_10':'Online zábava','travel_intensity_1_10':'Cestování',
      'sport_activity_1_10':'Sport','outdoor_activity_1_10':'Outdoor aktivity','dining_out_1_10':'Stravování venku','culture_activity_1_10':'Kultura',
      'socializing_offline_1_10':'Offline socializace','tv_intensity_1_10':'Televize','radio_intensity_1_10':'Rádio','gaming_intensity_1_10':'Gaming',
      'JRC_trust':'Obecná důvěra','politicky_zajem_2021':'Politický zájem','redistribuce_podpora_2021':'Podpora redistribuce',
      'zdravi_sebehodnoceni':'Sebehodnocení zdraví','PHQ9_2022':'PHQ-9','GAD7_2022':'GAD-7','prijem_pozice_0_1':'Příjmová pozice'
    }
    return repl.get(c,c.replace('_1_10','').replace('_2021','').replace('_2022','').replace('_',' ').strip().capitalize())

def _candidate_cols(df:pd.DataFrame,max_cols=72):
    preferred=[];fallback=[]
    for c in df.columns:
        if c.startswith('_') or any(x in c.lower() for x in ['donor','source','id','weight','vaha','quality','distance','code','kod','flag','rank']):continue
        s=pd.to_numeric(df[c],errors='coerce'); n=int(s.notna().sum())
        if n<max(100,len(df)//3) or s.nunique(dropna=True)<4:continue
        if c.endswith('_1_10') or c in {'PHQ9_2022','GAD7_2022','JRC_trust','politicky_zajem_2021','redistribuce_podpora_2021','hodnoceni_vlady_2021','stav_ekonomiky_2021','zdravi_sebehodnoceni','prijem_pozice_0_1'}:
            preferred.append(c)
        elif any(x in c for x in ['BFI_','JRC_','ISSP_','QOG_']):fallback.append(c)
    return (preferred+fallback)[:max_cols]

def _corr_rows(df,cols,limit=18):
    num=df[cols].apply(pd.to_numeric,errors='coerce')
    corr=num.corr(min_periods=max(80,len(df)//20))
    rows=[]
    for i,a in enumerate(cols):
        for b in cols[i+1:]:
            r=corr.at[a,b]
            if pd.isna(r):continue
            n=int(num[[a,b]].dropna().shape[0])
            rows.append({'a':a,'b':b,'a_label':_label(a),'b_label':_label(b),'r':round(float(r),4),'abs_r':round(abs(float(r)),4),'n':n,'epistemic_status':'MODELLED_PANEL_ASSOCIATION','causality':'NOT_INFERRED'})
    rows.sort(key=lambda x:(-x['abs_r'],-x['n'],x['a'],x['b']))
    return rows[:limit],rows

def _domain_summaries(df):
    groups={
      'Digitální chování':['smartphone_use_intensity_1_10','digital_communication_intensity_1_10','online_information_intensity_1_10','online_entertainment_intensity_1_10','online_transactions_intensity_1_10','social_media_intensity_1_10'],
      'Média':['tv_intensity_1_10','radio_intensity_1_10','print_intensity_1_10','gaming_intensity_1_10'],
      'Volný čas a životní styl':['travel_intensity_1_10','sport_activity_1_10','outdoor_activity_1_10','socializing_offline_1_10','dining_out_1_10','culture_activity_1_10'],
      'Spotřebitelské rozhodování':['price_sensitivity_1_10','deal_proneness_1_10','premium_willingness_1_10','physical_retail_activity_1_10'],
      'Společnost a postoje':['JRC_trust','politicky_zajem_2021','redistribuce_podpora_2021','hodnoceni_vlady_2021','stav_ekonomiky_2021']}
    out=[]
    for domain,cols in groups.items():
        vals=[]
        for c in cols:
            if c not in df:continue
            m=pd.to_numeric(df[c],errors='coerce').mean()
            if pd.notna(m):vals.append((c,float(m)))
        if not vals:continue
        top=sorted(vals,key=lambda x:x[1],reverse=True)[:3]
        out.append({'domain':domain,'summary':'Nejvýše v aktuálním modelled panelu: '+', '.join(f'{_label(c)} {v:.1f}' for c,v in top)+'.','metrics':[{'field':c,'label':_label(c),'mean':round(v,2)} for c,v in vals]})
    return out

def _hypotheses(df,all_corr):
    look={(x['a'],x['b']):x for x in all_corr};look.update({(x['b'],x['a']):x for x in all_corr})
    specs=[
      ('Citlivost na cenu × vyhledávání slev','price_sensitivity_1_10','deal_proneness_1_10'),
      ('Citlivost na cenu × ochota připlatit','price_sensitivity_1_10','premium_willingness_1_10'),
      ('Sociální sítě × online zábava','social_media_intensity_1_10','online_entertainment_intensity_1_10'),
      ('Online transakce × internetové bankovnictví','online_transactions_intensity_1_10','internet_banking_user_2025'),
      ('Politický zájem × politická média','politicky_zajem_2021','politika_media_2021'),
      ('PHQ-9 × GAD-7','PHQ9_2022','GAD7_2022'),
      ('Příjmová pozice × cenová citlivost','prijem_pozice_0_1','price_sensitivity_1_10'),
      ('Důvěra × občanské hodnocení vlády','JRC_trust','hodnoceni_vlady_2021')]
    out=[]
    for label,a,b in specs:
        if a not in df or b not in df:continue
        z=df[[a,b]].apply(pd.to_numeric,errors='coerce').dropna();r=float(z[a].corr(z[b])) if len(z)>=30 else math.nan
        status='STRONG' if pd.notna(r) and abs(r)>=.35 else 'MODERATE' if pd.notna(r) and abs(r)>=.2 else 'WEAK_OR_NOT_CONFIRMED'
        out.append({'label':label,'a':a,'b':b,'r':None if pd.isna(r) else round(r,4),'n':len(z),'status':status,'causality':'NOT_INFERRED'})
    return out

def _group_contrasts(df):
    out=[]
    metrics=[c for c in ['price_sensitivity_1_10','premium_willingness_1_10','social_media_intensity_1_10','travel_intensity_1_10','JRC_trust'] if c in df]
    for gcol in ['pohlavi','vek_skupina','vzdelani']:
        if gcol not in df:continue
        for m in metrics:
            t=df[[gcol,m]].copy();t[m]=pd.to_numeric(t[m],errors='coerce');t=t.dropna()
            means=t.groupby(gcol)[m].agg(['mean','count']).query('count>=100').sort_values('mean')
            if len(means)<2:continue
            lo,hi=means.iloc[0],means.iloc[-1]
            out.append({'metric':m,'metric_label':_label(m),'group_label':_label(gcol),'low_group':str(means.index[0]),'high_group':str(means.index[-1]),'low_mean':round(float(lo['mean']),2),'high_mean':round(float(hi['mean']),2),'difference':round(float(hi['mean']-lo['mean']),2)})
    return sorted(out,key=lambda x:abs(x['difference']),reverse=True)[:12]

def _schedule():
    default={'enabled':True,'cadence':'weekly','population_mode':'LIVE'}
    try:
        cx=_connect();r=cx.execute("SELECT value_json FROM society_settings WHERE key='brief_schedule'").fetchone();cx.close()
        return {**default,**(json.loads(r[0]) if r else {})}
    except Exception:return default

def set_schedule(enabled=True,cadence='weekly',population_mode='LIVE'):
    cadence=cadence if cadence in {'manual','weekly','monthly'} else 'weekly';d={'enabled':bool(enabled),'cadence':cadence,'population_mode':'STATIC' if str(population_mode).upper().startswith('STATIC') else 'LIVE'}
    cx=_connect();cx.execute("INSERT OR REPLACE INTO society_settings VALUES('brief_schedule',?,?)",(json.dumps(d,ensure_ascii=False),_now()));cx.commit();cx.close();return d

def _latest(mode):
    try:
        cx=_connect();r=cx.execute('SELECT payload_json FROM society_briefs WHERE population_mode=? ORDER BY created_at DESC LIMIT 1',(mode,)).fetchone();cx.close();return json.loads(r[0]) if r else None
    except Exception:return None

def _due(brief,schedule):
    if not brief:return True
    if not schedule.get('enabled') or schedule.get('cadence')=='manual':return False
    try:
        ts=time.mktime(time.strptime(brief['generated_at'][:19],'%Y-%m-%dT%H:%M:%S'));age=time.time()-ts
    except Exception:return True
    return age>(7*86400 if schedule.get('cadence')=='weekly' else 30*86400)

def generate_brief(population_mode='LIVE',force=False):
    mode='STATIC' if str(population_mode).upper().startswith('STATIC') else 'LIVE';schedule=_schedule();old=_latest(mode)
    if not force and old and not _due(old,schedule):return old
    df,p=_panel(mode);cols=_candidate_cols(df);strong,all_corr=_corr_rows(df,cols,18)
    hyp=_hypotheses(df,all_corr)
    weak=[]
    for h in hyp:
        if h['status']=='WEAK_OR_NOT_CONFIRMED':weak.append({'a':h['a'],'b':h['b'],'a_label':_label(h['a']),'b_label':_label(h['b']),'r':h['r'],'n':h['n'],'status':h['status'],'note':'Slabý lineární vztah v modelled panelu není důkaz absence vztahu v reálném světě.'})
    if len(weak)<6:
        for x in reversed(all_corr):
            if x['abs_r']<=.12:
                weak.append({**x,'status':'WEAK_OR_NOT_CONFIRMED','note':'Slabý lineární vztah v modelled panelu není důkaz absence vztahu v reálném světě.'})
                if len(weak)>=8:break
    payload={'schema':'npc.society_brief.v2','brief_id':'SOC-'+hashlib.sha256((mode+_now()+str(len(df))).encode()).hexdigest()[:12],'generated_at':_now(),'population':{'mode':mode,'rows':int(len(df)),'panel_file':p.name,'panel_sha256':_sha(p),'epistemic_status':'MODELLED_POPULATION'},'relationship_source':'CURRENT_PANEL_CORRELATION','truth_contract':'Výstup je deterministická agregovaná analýza aktuální modelled NPC populace. MODELLED/SYNTHETIC ≠ OBSERVED; association ≠ causality; nejde o externí prediktivní validaci.','domain_summaries':_domain_summaries(df),'strong_correlations':strong,'weak_or_not_confirmed':weak[:8],'hypothesis_checks':hyp,'group_contrasts':_group_contrasts(df),'schedule':schedule}
    try:
        cx=_connect();cx.execute('INSERT OR REPLACE INTO society_briefs VALUES(?,?,?,?,?)',(payload['brief_id'],payload['generated_at'],mode,payload['population']['panel_sha256'],json.dumps(payload,ensure_ascii=False,default=str)));cx.commit();cx.close()
    except Exception:payload['persistence_status']='TRANSIENT'
    return payload

def ask_society(question,population_mode='LIVE',use_ai=False):
    b=generate_brief(population_mode,False);q=str(question or '').strip();ql=q.lower();rels=b['strong_correlations']+b['weak_or_not_confirmed']
    terms=[x for x in ql.replace('?',' ').replace(',',' ').split() if len(x)>=4]
    scored=[]
    for r in rels:
        hay=(str(r.get('a_label',''))+' '+str(r.get('b_label',''))+' '+str(r.get('a',''))+' '+str(r.get('b',''))).lower();score=sum(1 for t in terms if t in hay)
        if score:scored.append((score,abs(float(r.get('r') or 0)),r))
    # For common domain questions, calculate a transparent current-panel correlation
    # slice even when the target relationship is not among the global top 18.
    targets=[]
    keyword_targets=[(('cen','citliv'),'price_sensitivity_1_10'),(('slev','deal'),'deal_proneness_1_10'),(('premium','připl','pripl'),'premium_willingness_1_10'),(('sociál','social'),'social_media_intensity_1_10'),(('cest','travel'),'travel_intensity_1_10'),(('důvěr','duver','trust'),'JRC_trust')]
    for keys,field in keyword_targets:
        if any(k in ql for k in keys):targets.append(field)
    if targets:
        df,_=_panel(population_mode);cols=_candidate_cols(df,72)
        for target in targets:
            if target not in df:continue
            x=pd.to_numeric(df[target],errors='coerce')
            for c in cols:
                if c==target:continue
                y=pd.to_numeric(df[c],errors='coerce');z=pd.DataFrame({'x':x,'y':y}).dropna()
                if len(z)<100:continue
                r=float(z['x'].corr(z['y']))
                if pd.isna(r):continue
                rr={'a':target,'b':c,'a_label':_label(target),'b_label':_label(c),'r':round(r,4),'abs_r':round(abs(r),4),'n':len(z),'epistemic_status':'MODELLED_PANEL_ASSOCIATION','causality':'NOT_INFERRED'}
                scored.append((5,abs(r),rr))
    scored.sort(key=lambda x:(-x[0],-x[1]));hits=[];seen=set()
    for _,__,r in scored:
        key=tuple(sorted((str(r.get('a')),str(r.get('b')))))
        if key in seen:continue
        seen.add(key);hits.append(r)
        if len(hits)>=5:break
    if not hits:hits=b['strong_correlations'][:5]
    if hits:
        answer='Z aktuálního modelled panelu jsou k dotazu nejrelevantnější tyto asociace: '+ '; '.join(f"{r.get('a_label')} × {r.get('b_label')}: r={float(r.get('r') or 0):+.2f}, N={r.get('n')}" for r in hits)+'. Jde o asociace v modelled populaci, nikoli o kauzální důvody.'
    else:answer='V aktuálním modelled panelu nemám dostatečný agregovaný vztah, který by tuto otázku přímo zodpověděl.'
    return {'answer':answer,'question':q,'epistemic_status':'GROUNDED_AGGREGATE','population_mode':b['population']['mode'],'evidence':hits,'ai_used':False,'truth_contract':b['truth_contract']}

def _segment_features(df,dimensions=None):
    if dimensions:
        cols=[c for c in dimensions if c in df]
    else:
        pref=['price_sensitivity_1_10','deal_proneness_1_10','premium_willingness_1_10','social_media_intensity_1_10','online_information_intensity_1_10','travel_intensity_1_10','sport_activity_1_10','dining_out_1_10','culture_activity_1_10','JRC_trust','politicky_zajem_2021','prijem_pozice_0_1']
        cols=[c for c in pref if c in df]
    return cols[:16]

def run_segmentation(k=4,population_mode='LIVE',dimensions=None,name='Segment Lab'):
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    mode='STATIC' if str(population_mode).upper().startswith('STATIC') else 'LIVE';df,p=_panel(mode);cols=_segment_features(df,dimensions)
    if len(cols)<2:raise ValueError('Pro segmentaci nejsou dostupné alespoň 2 numerické dimenze.')
    X=df[cols].apply(pd.to_numeric,errors='coerce');X=X.fillna(X.median(numeric_only=True)).fillna(0);Z=StandardScaler().fit_transform(X)
    k=max(2,min(8,int(k)));labels=KMeans(n_clusters=k,random_state=1866,n_init=10).fit_predict(Z)
    w=pd.to_numeric(df.get('vaha_kalibrovana',pd.Series(np.ones(len(df)))),errors='coerce').fillna(1).clip(lower=0);totalw=float(w.sum()) or float(len(df));ids=df.get('panel_row_id',pd.Series([f'R{i}' for i in range(len(df))])).astype(str)
    segs=[]
    for i in range(k):
        mask=labels==i;n=int(mask.sum());diffs=[]
        for c in cols:
            sm=float(pd.to_numeric(df.loc[mask,c],errors='coerce').mean());rm=float(pd.to_numeric(df.loc[~mask,c],errors='coerce').mean());delta=sm-rm
            diffs.append({'field':c,'label':_label(c),'segment_mean':round(sm,2),'rest_mean':round(rm,2),'difference':round(delta,2),'direction':'higher' if delta>=0 else 'lower'})
        diffs.sort(key=lambda x:abs(x['difference']),reverse=True)
        hi=[d for d in diffs if d['direction']=='higher'][:6];lo=[d for d in diffs if d['direction']=='lower'][:6]
        demo=[]
        for gc in ['pohlavi','vek_skupina','vzdelani']:
            if gc not in df:continue
            gv=df.loc[mask,gc].astype(str).value_counts(normalize=True);rv=df.loc[~mask,gc].astype(str).value_counts(normalize=True)
            for val,share in gv.head(5).items():demo.append({'label':_label(gc),'value':val,'segment_share':round(float(share),4),'rest_share':round(float(rv.get(val,0)),4),'difference_pp':round(100*(float(share)-float(rv.get(val,0))),1)})
        demo.sort(key=lambda x:abs(x['difference_pp']),reverse=True)
        desc='Segment se oproti zbytku modelled populace odlišuje zejména: '+ '; '.join(f"{d['label']} {'výše' if d['direction']=='higher' else 'níže'} ({d['segment_mean']} vs {d['rest_mean']})" for d in diffs[:4])+'.'
        title='Segment '+str(i+1)+((' · '+hi[0]['label']) if hi else (' · '+lo[0]['label'] if lo else ''))
        sid='SEG-'+hashlib.sha256((mode+str(i)+','.join(cols)+str(k)).encode()).hexdigest()[:12]
        segs.append({'segment_id':sid,'title':title,'cluster_index':i,'count':n,'weighted_share':round(float(w[mask].sum()/totalw),4),'description':desc,'why_identified':'K-means seskupil panelové řádky podle podobnosti na standardizovaných vybraných measured/modelled dimenzích. Název a popis shrnují největší agregované rozdíly proti zbytku.','top_differences':diffs[:10],'high_differences':hi,'low_differences':lo,'demographic_differences':demo[:10],'respondent_ids':ids[mask].tolist(),'epistemic_status':'MODELLED_POPULATION_SEGMENT','naming_status':'DETERMINISTIC_DESCRIPTION','truth_contract':'Segment je matematická skupina v modelled NPC populaci; measured/modelled agregované rysy určují rozdíly, slovní název není skutečný respondentní výrok.'})
    run={'schema':'npc.society_segment_run.v2','run_id':'SEGRUN-'+hashlib.sha256((_now()+mode+str(k)+','.join(cols)).encode()).hexdigest()[:12],'created_at':_now(),'name':name,'population_mode':mode,'dimensions':cols,'k':k,'segments':segs,'truth_contract':'MODELLED population segmentation; not observed fieldwork segmentation.'}
    _CACHE['segment:'+run['run_id']]=run
    try:
        cx=_connect();cx.execute('INSERT OR REPLACE INTO society_segment_runs VALUES(?,?,?,?)',(run['run_id'],run['created_at'],mode,json.dumps(run,ensure_ascii=False,default=str)));cx.commit();cx.close()
    except Exception:pass
    return run

def _find_segment(segment_id):
    for k,v in list(_CACHE.items()):
        if k.startswith('segment:'):
            for s in v.get('segments',[]):
                if s.get('segment_id')==segment_id:return s,v
    try:
        cx=_connect();rows=cx.execute('SELECT payload_json FROM society_segment_runs ORDER BY created_at DESC LIMIT 30').fetchall();cx.close()
        for r in rows:
            run=json.loads(r[0])
            for s in run.get('segments',[]):
                if s.get('segment_id')==segment_id:return s,run
    except Exception:pass
    return None,None

def ask_segment(segment_id,question,use_ai=False):
    s,run=_find_segment(str(segment_id));
    if not s:raise KeyError('Segment nebyl nalezen. Spusťte segmentaci znovu.')
    dif=s.get('top_differences',[])[:6];demo=s.get('demographic_differences',[])[:4]
    answer=f"{s['title']} tvoří {100*float(s.get('weighted_share') or 0):.1f}% modelled populace (N={s.get('count')}). Největší measured/modelled rozdíly proti zbytku: "+'; '.join(f"{d['label']} {d['difference']:+.2f}" for d in dif)+'.'
    if demo:answer+=' Demograficky nejvíc vyčnívá: '+'; '.join(f"{d['label']}={d['value']} {d['difference_pp']:+.1f} p.b." for d in demo)+'.'
    return {'answer':answer,'question':question,'segment_id':segment_id,'epistemic_status':'GROUNDED_AGGREGATE','ai_used':False,'truth_contract':s.get('truth_contract')}
