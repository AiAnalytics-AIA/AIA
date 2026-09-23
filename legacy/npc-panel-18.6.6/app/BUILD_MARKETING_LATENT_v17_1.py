from __future__ import annotations

import json, math, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT=Path(__file__).resolve().parent
IN=ROOT/'audit_reference'/'FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz'
OUT=ROOT/'FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz'
SEED=20260819
RESIDUAL_LOADING=0.54

FIELDS=[x.strip()+'_1_10' for x in '''linkedin_affinity, social_passive_consumption, social_public_interaction, social_private_sharing, social_algorithm_discovery, social_relaxation_use, travel_intensity, sport_activity, outdoor_activity, socializing_offline, dining_out, culture_activity, nightlife, diy_home_activity, cooking_activity, physical_retail_activity, commute_intensity, caregiving_intensity, price_sensitivity, deal_proneness, premium_willingness, purchase_planning, impulse_buying, research_orientation, review_reliance, novelty_orientation, risk_aversion, brand_consciousness, brand_loyalty_general, convenience_orientation, local_brand_preference, sustainability_orientation, status_consumption, privacy_concern, persuasion_knowledge, advertising_skepticism, reactance, need_for_cognition, need_for_affect, social_proof_susceptibility, influencer_receptivity, authority_receptivity, scarcity_response, ad_avoidance, social_ad_attention, search_ad_attention, audio_ad_attention, ooh_ad_attention, category_knowledge_general, market_knowledge_general, advertising_literacy'''.split(',')]
SOCIAL_PRESERVE=['social_passive_consumption_1_10','social_public_interaction_1_10','social_private_sharing_1_10','social_algorithm_discovery_1_10','social_relaxation_use_1_10']
FACTORS=['F1_DEAL','F2_DELIB','F3_RESIST','F4_SOCIAL','F5_NOVEL','F6_ACTIVITY','F7_HOME']

R=np.eye(7)
PAIRS={(0,1):.34,(0,2):.28,(0,3):.22,(0,4):-.30,(0,5):-.25,(0,6):.32,
       (1,2):.34,(1,3):-.28,(1,4):.32,(1,5):.28,(1,6):.20,
       (2,3):-.34,(2,4):.20,(2,5):-.22,(2,6):.25,
       (3,4):.30,(3,5):.35,(3,6):-.22,
       (4,5):.38,(4,6):-.25,(5,6):-.32}
for (i,j),v in PAIRS.items(): R[i,j]=R[j,i]=v

LOAD={}
def put(field,factor,loading): LOAD.setdefault(field,{})[factor]=loading
for f,l in [('price_sensitivity_1_10',.48),('deal_proneness_1_10',.44),('premium_willingness_1_10',-.48),('status_consumption_1_10',-.38),('brand_consciousness_1_10',-.32),('local_brand_preference_1_10',.20)]: put(f,'F1_DEAL',l)
for f,l in [('purchase_planning_1_10',.58),('research_orientation_1_10',.56),('review_reliance_1_10',.50),('need_for_cognition_1_10',.50),('impulse_buying_1_10',-.55),('convenience_orientation_1_10',-.32),('category_knowledge_general_1_10',.52),('market_knowledge_general_1_10',.52),('advertising_literacy_1_10',.42),('search_ad_attention_1_10',.26),('linkedin_affinity_1_10',.30)]: put(f,'F2_DELIB',l)
for f,l in [('persuasion_knowledge_1_10',.42),('advertising_skepticism_1_10',.58),('reactance_1_10',.52),('ad_avoidance_1_10',.56),('privacy_concern_1_10',.38),('advertising_literacy_1_10',.24),('social_ad_attention_1_10',-.22),('audio_ad_attention_1_10',-.14),('ooh_ad_attention_1_10',-.12)]: put(f,'F3_RESIST',l)
for f,l in [('social_passive_consumption_1_10',.58),('social_public_interaction_1_10',.72),('social_private_sharing_1_10',.74),('social_algorithm_discovery_1_10',.70),('social_relaxation_use_1_10',.74),('social_proof_susceptibility_1_10',.50),('influencer_receptivity_1_10',.54),('authority_receptivity_1_10',.34),('scarcity_response_1_10',.30),('need_for_affect_1_10',.32),('social_ad_attention_1_10',.32)]: put(f,'F4_SOCIAL',l)
for f,l in [('novelty_orientation_1_10',.42),('risk_aversion_1_10',-.42),('brand_loyalty_general_1_10',-.28),('sustainability_orientation_1_10',.32),('premium_willingness_1_10',.18),('culture_activity_1_10',.18),('travel_intensity_1_10',.22)]: put(f,'F5_NOVEL',l)
for f,l in [('travel_intensity_1_10',.50),('sport_activity_1_10',.46),('outdoor_activity_1_10',.44),('socializing_offline_1_10',.52),('dining_out_1_10',.50),('culture_activity_1_10',.46),('nightlife_1_10',.46),('physical_retail_activity_1_10',.30),('commute_intensity_1_10',.26),('ooh_ad_attention_1_10',.22),('audio_ad_attention_1_10',.18)]: put(f,'F6_ACTIVITY',l)
for f,l in [('diy_home_activity_1_10',.50),('cooking_activity_1_10',.54),('caregiving_intensity_1_10',.50),('physical_retail_activity_1_10',.24),('commute_intensity_1_10',.16),('convenience_orientation_1_10',.18),('local_brand_preference_1_10',.24)]: put(f,'F7_HOME',l)
assert set(LOAD)==set(FIELDS)


def znum(s:pd.Series)->pd.Series:
    x=pd.to_numeric(s,errors='coerce').astype(float); sd=x.std(skipna=True)
    z=(x-x.mean(skipna=True))/(sd if pd.notna(sd) and sd>0 else 1.0)
    return z.fillna(0.0).clip(-4,4)

def normal_score(s:pd.Series)->np.ndarray:
    x=pd.to_numeric(s,errors='coerce'); r=x.rank(method='average',pct=True)
    return norm.ppf(np.clip(r.to_numpy(float),1e-4,1-1e-4))

def reassign(orig:pd.Series,score:np.ndarray)->np.ndarray:
    vals=np.sort(pd.to_numeric(orig,errors='coerce').to_numpy(float)); order=np.argsort(score,kind='mergesort'); out=np.empty(len(vals),float); out[order]=vals; return out

def sha(path:Path)->str:
    h=hashlib.sha256();
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main():
    d=pd.read_csv(IN,low_memory=False); before=d.copy(); n=len(d); rng=np.random.default_rng(SEED)
    # Correlated latent factors + weak measured covariates. Missing BFI stays neutral, never imputed as a measured trait.
    F=pd.DataFrame(rng.multivariate_normal(np.zeros(7),R,size=n),columns=FACTORS,index=d.index)
    cv={k:znum(d[c]) for k,c in {'age':'vek','income':'prijem_pozice_0_1','edu':'vzdelani_isced','extr':'BFI_EXTR','cons':'BFI_CONS','open':'BFI_OPEM','agre':'BFI_AGRE'}.items()}
    parent=znum(pd.to_numeric(d['is_parent'],errors='coerce')) if 'is_parent' in d else pd.Series(0.0,index=d.index)
    F['F1_DEAL'] += -.20*cv['income']+.05*cv['age']
    F['F2_DELIB'] += .14*cv['cons']+.10*cv['open']+.10*cv['edu']+.08*cv['income']
    F['F3_RESIST'] += .08*cv['open']-.06*cv['agre']+.04*cv['cons']
    F['F4_SOCIAL'] += .14*cv['extr']-.10*cv['age']-.04*cv['cons']
    F['F5_NOVEL'] += .25*cv['open']+.10*cv['extr']-.14*cv['age']
    F['F6_ACTIVITY'] += .18*cv['extr']-.18*cv['age']+.08*cv['income']
    F['F7_HOME'] += .10*cv['cons']+.10*cv['age']+.10*parent
    F=(F-F.mean())/F.std()

    # Rank copula: exact current marginal is preserved for each field. Existing social-style joint block is already coherent and is not overwritten.
    for field in FIELDS:
        if field in SOCIAL_PRESERVE: continue
        score=np.zeros(n,float)
        for fac,loading in LOAD[field].items(): score += loading*F[fac].to_numpy(float)
        score += RESIDUAL_LOADING*normal_score(before[field])+.01*rng.standard_normal(n)
        d[field]=reassign(before[field],score)

    # Weak BFI relation for social-media time, while preserving the exact within-age distribution and all non-user zeros.
    for age,inds in d.groupby('vek').groups.items():
        idx=np.asarray(list(inds),dtype=int); idx=idx[pd.to_numeric(d.loc[idx,'social_network_user_2025'],errors='coerce').fillna(0).to_numpy()==1]
        if len(idx)<3: continue
        orig=normal_score(before.loc[idx,'social_media_minutes_day']); emos=znum(d.loc[idx,'BFI_EMOS']).to_numpy(); cons=znum(d.loc[idx,'BFI_CONS']).to_numpy()
        s=.15*emos+.08*cons+.70*orig+.01*rng.standard_normal(len(idx))
        for field in ['social_media_minutes_day','social_media_intensity_1_10']:
            d.loc[idx,field]=reassign(before.loc[idx,field],s)

    # Repair legacy CSV round-trip loss of leading zero for ISCO-08 armed-forces codes.
    # occupation_major=0 is the semantic anchor; runtime reads this field as string.
    occ=d['occupation_isco08'].fillna('').astype(str).str.replace(r'\.0$','',regex=True)
    maj=pd.to_numeric(d['occupation_major'],errors='coerce')
    zmask=maj.eq(0)&occ.str.match(r'^\d{3}$')
    d.loc[zmask,'occupation_isco08']=occ[zmask].str.zfill(4)

    # Hard non-user guard remains hard.
    non=pd.to_numeric(d['social_network_user_2025'],errors='coerce').fillna(0).eq(0)
    d.loc[non,'social_media_minutes_day']=0.0; d.loc[non,'social_media_intensity_1_10']=1.0

    # exact marginal and guard assertions
    for field in FIELDS:
        a=np.sort(pd.to_numeric(before[field],errors='coerce').to_numpy()); b=np.sort(pd.to_numeric(d[field],errors='coerce').to_numpy())
        if not np.allclose(a,b,equal_nan=True,atol=0,rtol=0): raise AssertionError(f'marginal changed: {field}')
    if not (d.loc[non,'social_media_minutes_day']==0).all(): raise AssertionError('non-user social minute guard failed')

    d.to_csv(OUT,index=False,compression='gzip')
    # factors are audit-only; never persona facts.
    F.insert(0,'panel_row_id',d['panel_row_id'].astype(str).to_numpy()); F.to_csv(ROOT/'LATENT_FACTOR_AUDIT_v17_1.csv.gz',index=False,compression='gzip')
    meta={'version':'17.1.2','base_version':'17.0.1','rows':len(d),'columns':len(d.columns),'seed':SEED,'fields_restructured':len(FIELDS)-len(SOCIAL_PRESERVE),'social_style_fields_preserved':SOCIAL_PRESERVE,'panel_sha256':sha(OUT)}
    (ROOT/'LATENT_BUILD_STATUS_v17_1.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False))
if __name__=='__main__': main()
