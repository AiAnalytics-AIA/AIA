"""NPC Panel 18.2 — Visualization Lab.

Read-only visualization preparation over real respondent rows.  The module never
synthesizes respondents: a row in the map always comes from the provided dataset.
"""
from __future__ import annotations
import hashlib, json, math, re
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

PROFILE_HINTS = (
    'respondent_id','panel_row_id','dem_','att_','beh_','bin_','gender','sex','pohlavi','pohlaví',
    'age','vek','věk','region','education','vzdel','vzděl','income','prijem','příjem','segment','persona'
)

LABELS = {
    'dem_gender':'Pohlaví','gender':'Pohlaví','sex':'Pohlaví','dem_age':'Věk','age':'Věk','vek':'Věk','věk':'Věk',
    'dem_region':'Region','region':'Region','dem_education':'Vzdělání','education':'Vzdělání','dem_income':'Příjem',
    'income':'Příjem','respondent_id':'Respondent','panel_row_id':'Řádek panelu'
}

def _label(col:str)->str:
    if col in LABELS:return LABELS[col]
    x=col
    for p in ('obj_','q_','dem_','att_','beh_','bin_'): x=x[len(p):] if x.startswith(p) else x
    return x.replace('_',' ').strip().capitalize()

def _safe(v:Any):
    if v is None:return None
    try:
        if pd.isna(v):return None
    except Exception:pass
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return float(v)
    if isinstance(v,(np.bool_,)):return bool(v)
    return v.item() if hasattr(v,'item') else v

def _is_profile_col(c:str)->bool:
    low=c.lower()
    return any(low==x or low.startswith(x) for x in PROFILE_HINTS)

def detect_rating_columns(df:pd.DataFrame, max_objects:int=24)->list[str]:
    direct=[c for c in df.columns if str(c).startswith('obj_')]
    if len(direct)>=2:return direct[:max_objects]
    out=[]
    for c in df.columns:
        c=str(c)
        if _is_profile_col(c):continue
        s=pd.to_numeric(df[c],errors='coerce')
        valid=s.dropna()
        if len(valid)<max(10,int(len(df)*.15)):continue
        # Visualization relation questions are expected on an approximately 1–10 scale.
        q01,q99=valid.quantile([.01,.99])
        if q01>=0 and q99<=10.5 and valid.nunique()>=3:out.append(c)
    return out[:max_objects]

def detect_profile_columns(df:pd.DataFrame,max_cols:int=28)->list[str]:
    cols=[str(c) for c in df.columns if _is_profile_col(str(c))]
    # Useful categorical columns that are not high-cardinality IDs.
    for c in df.columns:
        c=str(c)
        if c in cols or c.startswith('obj_'):continue
        s=df[c]
        nun=int(s.nunique(dropna=True))
        if 2<=nun<=20 and not pd.api.types.is_numeric_dtype(s):cols.append(c)
        if len(cols)>=max_cols:break
    return cols[:max_cols]

def _id_value(row:pd.Series,i:int)->str:
    for c in ('respondent_id','panel_row_id','id','ID'):
        if c in row.index and pd.notna(row[c]):return str(row[c])
    return f'R{i+1:05d}'

def _jitter(key:str)->tuple[float,float]:
    h=hashlib.sha256(key.encode('utf-8')).digest()
    a=int.from_bytes(h[:4],'big')/2**32*2*math.pi
    r=(int.from_bytes(h[4:8],'big')/2**32)**.5*1.55
    return math.cos(a)*r,math.sin(a)*r



def object_relationship_payload(df:pd.DataFrame,rating_columns:list[str])->dict[str,Any]:
    """Prepare object-mode Sociomapa from respondent rows.

    Position uses mutual relationship strength only. Height/color metrics are
    independent display layers. Pairwise p-values/N are included when the
    relation was estimated from respondent ratings.
    """
    cols=[c for c in rating_columns if c in df.columns]
    n=len(cols)
    if n<2:return {'names':[],'matrix':[],'positions':[],'scores_classic':[],'scores_normative':[]}
    X=df[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    R=np.zeros((n,n),float);RC=np.zeros((n,n),float);PN=np.zeros((n,n),int);PP=np.full((n,n),np.nan,float)
    try:
        from scipy.stats import pearsonr
    except Exception:
        pearsonr=None
    for i in range(n):
        for j in range(n):
            if i==j:continue
            a,b=X[:,i],X[:,j];ok=np.isfinite(a)&np.isfinite(b);nn=int(ok.sum());PN[i,j]=nn
            if nn<5:corr=0.0;pval=np.nan
            else:
                aa,bb=a[ok],b[ok];sa,sb=float(np.std(aa)),float(np.std(bb))
                if sa>1e-12 and sb>1e-12:
                    if pearsonr is not None:
                        try:
                            pr=pearsonr(aa,bb);corr=float(pr.statistic);pval=float(pr.pvalue)
                        except Exception:corr=float(np.corrcoef(aa,bb)[0,1]);pval=np.nan
                    else:corr=float(np.corrcoef(aa,bb)[0,1]);pval=np.nan
                else:corr=0.0;pval=np.nan
                if not np.isfinite(corr):corr=0.0
            RC[i,j]=corr;PP[i,j]=pval
            R[i,j]=float(np.clip(1.0+9.0*((corr+1.0)/2.0),1.0,10.0))
    score=R.sum(axis=0)+R.sum(axis=1)
    mu=float(np.mean(score));sd=float(np.std(score));norm=np.full(n,50.0) if sd<1e-12 else 50.0+10.0*(score-mu)/sd
    ang=np.linspace(0,2*np.pi,n,endpoint=False)-np.pi/2;P=np.c_[28*np.cos(ang),28*np.sin(ang)]
    max_strength=max(1.0,float(np.max([(R[i,j]+R[j,i])/2.0 for i in range(n) for j in range(i+1,n)] or [1.0])))
    for it in range(800):
        step=.1*(1-it/1000.0);delta=np.zeros_like(P)
        for i in range(n):
            for j in range(i+1,n):
                m=(R[i,j]+R[j,i])/2.0;target=14.0+46.0*(1.0-m/max_strength);d=P[j]-P[i];dist=float(np.hypot(d[0],d[1])) or 1e-6
                f=(dist-target)*step*.02;v=f*d/dist;delta[i]+=v;delta[j]-=v
        P+=delta
    P-=P.mean(axis=0,keepdims=True);rr=max(1.0,float(np.max(np.linalg.norm(P,axis=1))));P=P*(38.0/rr)
    means=[];supports=[]
    for c in cols:
        ss=pd.to_numeric(df[c],errors='coerce');means.append(round(float(ss.mean()),4) if ss.notna().any() else None);supports.append(int(ss.notna().sum()))
    return {'names':[_label(c) for c in cols],'source_columns':cols,
        'matrix':[[round(float(x),4) for x in row] for row in R],
        'pair_r':[[None if i==j else round(float(RC[i,j]),6) for j in range(n)] for i in range(n)],
        'pair_p':[[None if i==j or not np.isfinite(PP[i,j]) else round(float(PP[i,j]),8) for j in range(n)] for i in range(n)],
        'pair_n':[[int(PN[i,j]) for j in range(n)] for i in range(n)],
        'positions':[{'x':round(float(x),5),'y':round(float(y),5)} for x,y in P],
        'scores_classic':[round(float(x),4) for x in score],'scores_normative':[round(float(x),4) for x in norm],
        'mean_rating':means,'support_n':supports,
        'relation_source':'PAIRWISE_SIGNED_CORRELATION_FROM_RESPONDENT_RATINGS',
        'position_method':'mutual_strength_target_distance; 800_step_relaxation; normalized_radius_38',
        'height_contract':'position is relationship-only; display height/color are independent metrics',
        'matrix_contract':'row sends; column receives; diagonal=0; 1..10 relation strength',
        'statistics_contract':'pair_p is two-sided Pearson correlation p-value; pair_n is pairwise complete N. Strength and significance are separate.'}

def respondent_map_payload(df:pd.DataFrame,*,rating_columns:list[str]|None=None,profile_columns:list[str]|None=None,
                           max_rows:int|None=None)->dict[str,Any]:
    if df is None or df.empty:raise ValueError('Dataset neobsahuje žádné respondenty.')
    work=df.copy()
    if max_rows and len(work)>max_rows: work=work.iloc[:int(max_rows)].copy()
    rating_columns=[c for c in (rating_columns or detect_rating_columns(work)) if c in work.columns]
    if len(rating_columns)<2:raise ValueError('Pro mapu respondentů jsou potřeba alespoň dvě společně hodnocené položky / objekty.')
    profile_columns=[c for c in (profile_columns or detect_profile_columns(work)) if c in work.columns and c not in rating_columns]
    nobj=len(rating_columns); angles=np.linspace(0,2*np.pi,nobj,endpoint=False)-np.pi/2
    obj_xy=np.c_[42*np.cos(angles),42*np.sin(angles)]
    ratings=work[rating_columns].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    weights=np.maximum(0,ratings-5.0); weights[~np.isfinite(weights)]=0
    points=[]; unknown=0
    profile_values={c:work[c].tolist() for c in profile_columns}
    for i,row in work.iterrows():
        local_i=work.index.get_loc(i); rid=_id_value(row,local_i); w=weights[local_i]
        if float(w.sum())>1e-9:
            xy=(w[:,None]*obj_xy).sum(axis=0)/w.sum(); dx,dy=_jitter(rid); xy=xy+np.array([dx,dy])
            position_status='POSITIONED'
        else:
            unknown+=1; dx,dy=_jitter(rid); ang=(hashlib.md5(rid.encode()).digest()[0]/255)*2*np.pi; rr=54+3*((local_i%11)/10)
            xy=np.array([rr*np.cos(ang)+dx,rr*np.sin(ang)+dy]);position_status='UNDETERMINED'
        profile={_label(c):_safe(row[c]) for c in profile_columns if c in row.index}
        answer={_label(c):_safe(row[c]) for c in rating_columns if c in row.index}
        # Search text is explicitly prepared for the client filter; it is not a model input.
        search=' '.join([rid]+[str(v) for v in profile.values() if v is not None]+[f'{k} {v}' for k,v in answer.items() if v is not None]).lower()
        points.append({'id':rid,'x':round(float(xy[0]),5),'y':round(float(xy[1]),5),'position_status':position_status,
                       'profile':profile,'answers':answer,'search_text':search})
    objects=[]
    for j,c in enumerate(rating_columns):
        s=pd.to_numeric(work[c],errors='coerce')
        objects.append({'key':c,'name':_label(c),'x':round(float(obj_xy[j,0]),5),'y':round(float(obj_xy[j,1]),5),
                        'mean':round(float(s.mean()),4) if s.notna().any() else None,'n':int(s.notna().sum())})
    suggestions=interesting_groups(work,profile_columns,rating_columns)
    object_map=object_relationship_payload(work,rating_columns)
    return {'schema':'npc.visualization.respondents.v1','respondent_count':len(points),'object_count':len(objects),
            'points':points,'objects':objects,'profile_columns':[{'key':c,'label':_label(c)} for c in profile_columns],
            'rating_columns':[{'key':c,'label':_label(c)} for c in rating_columns], 'suggestions':suggestions,
            'object_map':object_map,'undetermined_count':unknown,
            'position_method':'weighted_brand_object_barycenter; weight=max(0,rating-5); deterministic overlap jitter',
            'truth_contract':'Každý bod odpovídá jednomu skutečnému řádku vstupního datasetu. Systém nevytváří syntetické respondenty jako náhradní data. Ruční layout v UI mění pouze zobrazení, nikdy data ani odpovědi.'}

def _find_col(cols:list[str],patterns:list[str])->str|None:
    for c in cols:
        norm=str(c).lower()
        if any(p in norm for p in patterns):return c
    return None

def interesting_groups(df:pd.DataFrame,profile_cols:list[str]|None=None,rating_cols:list[str]|None=None)->list[dict[str,Any]]:
    """Deterministic discovery hints. Block E may later append AI interpretation."""
    profile_cols=profile_cols or detect_profile_columns(df);rating_cols=rating_cols or detect_rating_columns(df)
    groups=[]
    def add(title,description,column,op,value,mask):
        n=int(mask.fillna(False).sum());share=n/max(1,len(df))
        if n>=max(5,int(len(df)*.03)):
            groups.append({'id':f'G{len(groups)+1}','title':title,'description':description,'count':n,'share':round(share,4),
                           'filter':{'column':_label(column),'source_column':column,'op':op,'value':value},'origin':'DETERMINISTIC_DISCOVERY'})
    age=_find_col(profile_cols,['age','vek','věk'])
    if age:
        s=pd.to_numeric(df[age],errors='coerce');add('Důchodci a senioři','Respondenti ve věku 60 a více let.',age,'>=',60,s>=60);add('Mladší lidé','Respondenti mladší 35 let.',age,'<',35,s<35)
    gender=_find_col(profile_cols,['gender','sex','pohl'])
    if gender:
        s=df[gender].astype(str).str.lower();mask=s.str.contains('ž|female|woman',regex=True);add('Ženy','Ženy ve vzorku.',gender,'contains','žena',mask)
    segment=_find_col(profile_cols,['segment','persona'])
    if segment:
        vc=df[segment].astype(str).value_counts()
        for value,n in vc.head(5).items():
            mask=df[segment].astype(str).eq(str(value)); add(str(value),f'Předdefinovaný segment v respondentním datasetu: {value}.',segment,'contains',str(value),mask)
    # Low/high tails of rating questions are often useful map filters.
    for c in rating_cols[:8]:
        s=pd.to_numeric(df[c],errors='coerce'); lab=_label(c)
        add(f'Výrazně nízké hodnocení · {lab}',f'Respondenti s hodnocením {lab} nejvýše 2 z 10.',c,'<=',2,s<=2)
        add(f'Výrazně vysoké hodnocení · {lab}',f'Respondenti s hodnocením {lab} alespoň 9 z 10.',c,'>=',9,s>=9)
    groups.sort(key=lambda x:(-x['count'],x['title']))
    return groups[:8]

def load_respondent_file(path:str|Path)->pd.DataFrame:
    p=Path(path)
    if not p.is_file():raise FileNotFoundError(str(p))
    if p.suffix.lower()=='.csv':return pd.read_csv(p,low_memory=False)
    if p.suffix.lower() in {'.xlsx','.xls'}:return pd.read_excel(p)
    if p.suffix.lower()=='.json':
        data=json.loads(p.read_text(encoding='utf-8'));return pd.DataFrame(data if isinstance(data,list) else data.get('rows') or data.get('respondents') or [])
    raise ValueError('Visualization Lab podporuje respondentní CSV, XLSX nebo JSON.')

def compare_area(points:list[dict[str,Any]],ids_a:list[str],ids_b:list[str]|None=None)->dict[str,Any]:
    """Compare two respondent areas with Welch t-test, Cohen d and 95% CI."""
    by={str(p['id']):p for p in points};A=[by[x] for x in map(str,ids_a or []) if str(x) in by];B=[by[x] for x in map(str,ids_b or []) if str(x) in by]
    def profile(rows):
        keys=sorted({k for p in rows for k in p.get('profile',{})});out=[]
        for k in keys:
            vals=[p['profile'].get(k) for p in rows if p['profile'].get(k) is not None]
            if not vals:continue
            nums=pd.to_numeric(pd.Series(vals),errors='coerce')
            if nums.notna().mean()>.8:out.append({'label':k,'kind':'numeric','value':round(float(nums.mean()),3),'n':int(nums.notna().sum())})
            else:
                vc=pd.Series([str(v) for v in vals]).value_counts();out.append({'label':k,'kind':'categorical','value':vc.index[0],'share':round(float(vc.iloc[0]/len(vals)),4),'n':len(vals)})
        return out
    pa,pb=profile(A),profile(B);bm={x['label']:x for x in pb};diff=[]
    for a in pa:
        b=bm.get(a['label'])
        if not b or a['kind']!=b['kind']:continue
        if a['kind']=='numeric':score=abs(float(a['value'])-float(b['value']));text=f"{a['label']}: {a['value']} vs {b['value']}"
        else:score=abs(float(a.get('share',0))-float(b.get('share',0)))+(0.3 if a['value']!=b['value'] else 0);text=f"{a['label']}: {a['value']} vs {b['value']}"
        diff.append({'label':a['label'],'score':round(score,4),'text':text})
    diff.sort(key=lambda x:-x['score'])
    keys=sorted({k for p in A+B for bag in (p.get('profile',{}),p.get('answers',{})) for k,v in bag.items() if v is not None});stats=[]
    try:
        from scipy.stats import ttest_ind, t as student_t
    except Exception:
        ttest_ind=None;student_t=None
    for k in keys:
        va=[];vb=[]
        for p in A:
            v=(p.get('answers') or {}).get(k,(p.get('profile') or {}).get(k))
            try:
                x=float(v)
                if math.isfinite(x):va.append(x)
            except Exception:pass
        for p in B:
            v=(p.get('answers') or {}).get(k,(p.get('profile') or {}).get(k))
            try:
                x=float(v)
                if math.isfinite(x):vb.append(x)
            except Exception:pass
        if len(va)<3 or len(vb)<3:continue
        aa=np.asarray(va,float);bb=np.asarray(vb,float);ma=float(aa.mean());mb=float(bb.mean());delta=ma-mb;n1=len(aa);n2=len(bb);s1=float(aa.std(ddof=1));s2=float(bb.std(ddof=1))
        se=math.sqrt((s1*s1/n1)+(s2*s2/n2));den=((s1*s1/n1)**2/max(1,n1-1))+((s2*s2/n2)**2/max(1,n2-1));dfv=((s1*s1/n1+s2*s2/n2)**2/den) if den>1e-15 else float(n1+n2-2)
        try:pval=float(ttest_ind(aa,bb,equal_var=False,nan_policy='omit').pvalue) if ttest_ind is not None else None
        except Exception:pval=None
        sp=math.sqrt(max(0,((n1-1)*s1*s1+(n2-1)*s2*s2)/max(1,n1+n2-2)));d=delta/sp if sp>1e-12 else 0.0
        try:crit=float(student_t.ppf(.975,dfv)) if student_t is not None and se>0 else 1.96
        except Exception:crit=1.96
        ci=[delta-crit*se,delta+crit*se]
        stats.append({'label':k,'mean_a':round(ma,4),'mean_b':round(mb,4),'delta':round(delta,4),'n_a':n1,'n_b':n2,
            'p':None if pval is None or not math.isfinite(pval) else round(pval,8),'cohen_d':round(d,4),'ci95':[round(float(ci[0]),4),round(float(ci[1]),4)],
            'significant_05':bool(pval is not None and pval<.05),'verdict':'statisticky průkazný rozdíl' if pval is not None and pval<.05 else 'bez průkazného rozdílu'})
    stats.sort(key=lambda x:(0 if x['significant_05'] else 1,-abs(float(x['cohen_d'])),-abs(float(x['delta']))))
    return {'area_a':{'n':len(A),'profile':pa},'area_b':{'n':len(B),'profile':pb},'differences':diff[:10],'statistics':stats[:24],
        'method':'Welchův dvouvýběrový t-test, Cohenovo d, 95% interval rozdílu průměrů; výpočty v původních jednotkách.'}

