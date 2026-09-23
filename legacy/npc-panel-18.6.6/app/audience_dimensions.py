from __future__ import annotations

"""Data-backed audience/dimension catalogue for NPC Panel 17.9.3.

The production CSV stays immutable.  This module attaches two runtime layers:
1) deterministic dimensions derived only from existing respondent signals,
2) human-approved evidence-based overlays materialized by Data Library.

Every factor returned by ``catalog`` therefore has explicit provenance and filter
semantics.  Unsupported/sensitive fields are never silently exposed as ad-like
filters.
"""

from pathlib import Path
from typing import Any
import hashlib, json, math, re
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OVERLAY_META=ROOT/'data'/'dimension_library_overlays.json'
OVERLAY_DIR=ROOT/'data'/'dimension_overlays'

CATEGORY_META={
 'demography':('Demografie a životní fáze','Kdo člověk je a v jaké životní situaci se nachází.'),
 'digital':('Digitální chování a zařízení','Používání internetu, zařízení a digitálních služeb.'),
 'social':('Sociální sítě a platformy','Používání konkrétních platforem a způsob sociálního používání.'),
 'media':('Média a zpravodajství','TV, rádio, tisk, online/news a celková mediální pozornost.'),
 'hobby':('Hobby, volný čas a lifestyle','Gaming, cestování, sport, outdoor, kultura, gastronomie, DIY a další aktivity.'),
 'shopping':('Nákupní a značkové chování','Cena, slevy, premium, plánování, recenze, loajalita, convenience a značky.'),
 'advertising':('Reakce na reklamu a komunikaci','Pozornost, skepse, influencer/social proof, reactance a reklamní kanály.'),
 'values':('Hodnoty a životní orientace','Hodnotové orientace, rodina/práce, lokalita a kosmopolitnost.'),
 'finance':('Finance a finanční capability','Rozpočtování, rezervy, investice, znalosti a finanční resilience.'),
 'work':('Práce, profese a role','Ekonomická aktivita, profesní skupiny a pracovní role.'),
 'derived':('Odvozené praktické profily','Deterministické souhrny vytvořené pouze z již existujících respondentních signálů.'),
 'custom':('Nové dimenze z Data Library','Schválené evidence-based dimenze materializované jako auditovaný overlay.'),
 'research_only':('Research-only / citlivé','Dostupné pro metodický research, ale ne jako běžný audience targeting filtr.'),
}

# Curated product-facing factors.  The file already contains ~400 columns; we expose
# only fields with a defensible targeting/segmentation interpretation.
CATEGORY_COLUMNS={
 'demography':[
  'vek','pohlavi','kraj','region_macro','vzdelani','vzdelani_isced','zamestnani_status','hlavni_status',
  'prijem_decile','prijem_osobni_mesicni','prijem_domacnosti_mesicni','velikost_domacnosti','pocet_deti_celkem',
  'has_partner','partner_cohabiting','is_parent','is_student','is_employed','is_unemployed','vek_skupina',
 ],
 'digital':[
  'internet_user_2025','mobile_internet_user_2025','online_shopper_2025','internet_banking_user_2025','online_video_user_2025',
  'online_music_user_2025','online_news_user_2025','ai_user_2025','smartphone_use_intensity_1_10','tablet_use_intensity_1_10',
  'computer_use_intensity_1_10','digital_communication_intensity_1_10','online_information_intensity_1_10',
  'online_entertainment_intensity_1_10','online_transactions_intensity_1_10','digital_personal_management_intensity_1_10',
 ],
 'social':[
  'social_network_user_2025','facebook_regular_user_2026','instagram_regular_user_2026','tiktok_regular_user_2026','youtube_regular_user_2026',
  'whatsapp_user_2026','messenger_user_2026','x_regular_user_2026','linkedin_affinity_1_10','social_media_minutes_day','social_media_intensity_1_10',
  'facebook_minutes_day','instagram_minutes_day','tiktok_minutes_day','youtube_minutes_day','whatsapp_minutes_day','messenger_minutes_day','x_minutes_day',
  'social_passive_consumption_1_10','social_public_interaction_1_10','social_private_sharing_1_10','social_algorithm_discovery_1_10','social_relaxation_use_1_10',
 ],
 'media':[
  'tv_weekly_reach','tv_daily_reach','tv_minutes_day','tv_intensity_1_10','radio_weekly_reach','radio_daily_reach','radio_minutes_day','radio_intensity_1_10',
  'print_period_reach','print_minutes_day','print_intensity_1_10','news_tv_weekly','news_print_weekly','news_online_weekly','news_social_weekly',
  'media_fragmentation_1_10','old_new_media_orientation_1_10','media_multitasking_1_10','media_gross_minutes_day','media_net_attention_minutes_day',
 ],
 'hobby':[
  'gaming_weekly','gaming_hours_week','gaming_intensity_1_10','private_travel_trips_year_model','travel_intensity_1_10','sport_activity_1_10','outdoor_activity_1_10',
  'socializing_offline_1_10','dining_out_1_10','culture_activity_1_10','nightlife_1_10','diy_home_activity_1_10','cooking_activity_1_10','physical_retail_activity_1_10',
  'commute_intensity_1_10','caregiving_intensity_1_10',
 ],
 'shopping':[
  'price_sensitivity_1_10','deal_proneness_1_10','premium_willingness_1_10','purchase_planning_1_10','impulse_buying_1_10','research_orientation_1_10',
  'review_reliance_1_10','novelty_orientation_1_10','risk_aversion_1_10','brand_consciousness_1_10','brand_loyalty_general_1_10','convenience_orientation_1_10',
  'local_brand_preference_1_10','sustainability_orientation_1_10','status_consumption_1_10','category_knowledge_general_1_10','market_knowledge_general_1_10',
 ],
 'advertising':[
  'privacy_concern_1_10','persuasion_knowledge_1_10','advertising_skepticism_1_10','reactance_1_10','need_for_cognition_1_10','need_for_affect_1_10',
  'social_proof_susceptibility_1_10','influencer_receptivity_1_10','authority_receptivity_1_10','scarcity_response_1_10','ad_avoidance_1_10',
  'tv_ad_attention_1_10','social_ad_attention_1_10','search_ad_attention_1_10','audio_ad_attention_1_10','print_ad_attention_1_10','ooh_ad_attention_1_10','advertising_literacy_1_10',
 ],
 'values':[
  'value_self_direction_1_10','value_stimulation_1_10','value_hedonism_1_10','value_achievement_1_10','value_power_1_10','value_security_1_10',
  'value_conformity_1_10','value_tradition_1_10','value_benevolence_1_10','value_universalism_1_10','value_openness_to_change_1_10','value_conservation_1_10',
  'value_self_enhancement_1_10','value_self_transcendence_1_10','family_centrality_1_10','work_centrality_1_10','local_attachment_1_10','cosmopolitan_orientation_1_10','authority_orientation_1_10',
 ],
 'finance':[
  'financial_daily_decision_role','financial_budgeting','financial_goal_set','financial_unexpected_14k_capable','financial_income_loss_without_loan','financial_regular_reserve',
  'financial_income_covers_costs','financial_saves_bank_product','financial_invests_stocks_funds','financial_crypto_saving','financial_mobile_payment',
  'financial_knowledge_1_10','financial_behavior_1_10','financial_resilience_1_10','financial_planning_1_10','financial_capability_1_10',
 ],
 'work':[
  'occupation_major','occupation_2digit','is_teacher','is_ict_specialist','is_science_engineering','is_business_admin_specialist','is_manager','is_service_sales',
  'is_health_professional','is_medical_doctor','is_health_associate_professional','is_healthcare_profession_current','is_construction_ecosystem_current','is_real_estate_professional_current','is_procurement_buyer_current',
 ],
}

# Explicit research-only fields.  They remain inspectable but never appear as ordinary
# targeting filters.  This avoids confusing a research platform with an ad network.
RESEARCH_ONLY=[
 'core_religion_group','core_religious_attendance','religious_affiliation_group','religious_practice_1_10',
 'PHQ9_2022','GAD7_2022','mentalni_zdravi_sebehodnoceni_2022','fyzicke_zdravi_sebehodnoceni_2022',
 'volba_2021_strana','politicky_zajem_2021','redistribuce_podpora_2021',
 'BFI_EXTR','BFI_AGRE','BFI_CONS','BFI_EMOS','BFI_OPEM',
]

LABELS={
 'vek':'Věk','pohlavi':'Pohlaví','kraj':'Kraj','region_macro':'Makroregion','vzdelani':'Vzdělání','vzdelani_isced':'Vzdělání (ISCED)',
 'zamestnani_status':'Ekonomická aktivita','hlavni_status':'Hlavní životní status','prijem_decile':'Příjmový decil','prijem_osobni_mesicni':'Osobní měsíční příjem',
 'prijem_domacnosti_mesicni':'Příjem domácnosti','velikost_domacnosti':'Velikost domácnosti','pocet_deti_celkem':'Počet dětí','has_partner':'Má partnera','is_parent':'Rodič',
 'life_stage_derived':'Životní fáze','digital_engagement_tier_derived':'Digitální angažovanost','dominant_media_derived':'Dominantní mediální kanál',
 'dominant_leisure_derived':'Dominantní volnočasová aktivita','shopping_orientation_derived':'Nákupní orientace','ad_receptivity_tier_derived':'Receptivita k reklamě',
 'financial_capability_tier_derived':'Finanční capability tier',
}

DERIVED_COLUMNS=[
 'life_stage_derived','digital_engagement_tier_derived','dominant_media_derived','dominant_leisure_derived',
 'shopping_orientation_derived','ad_receptivity_tier_derived','financial_capability_tier_derived',
]


def _label(col:str)->str:
    if col in LABELS:return LABELS[col]
    x=col
    x=re.sub(r'_(2025|2026|2022)$','',x)
    x=x.replace('_1_10','').replace('_0_1','').replace('_',' ')
    return x[:1].upper()+x[1:]


def _series_numeric(s:pd.Series)->pd.Series:
    return pd.to_numeric(s,errors='coerce')


def _tier(x:pd.Series, labels=('Nízká','Střední','Vysoká','Velmi vysoká'))->pd.Series:
    a=_series_numeric(x)
    return pd.cut(a,[-np.inf,3.0,5.5,7.5,np.inf],labels=list(labels)).astype('string')


def attach_derived(df:pd.DataFrame)->pd.DataFrame:
    """Attach deterministic, auditable aggregate dimensions without touching source CSV."""
    out=df.copy()
    age=_series_numeric(out.get('vek',pd.Series(np.nan,index=out.index)))
    parent=pd.to_numeric(out.get('is_parent',0),errors='coerce').fillna(0)>0
    student=pd.to_numeric(out.get('is_student',0),errors='coerce').fillna(0)>0
    employed=pd.to_numeric(out.get('is_employed',0),errors='coerce').fillna(0)>0
    partner=pd.to_numeric(out.get('has_partner',0),errors='coerce').fillna(0)>0
    life=np.full(len(out),'Dospělý / ostatní',dtype=object)
    life[age.ge(65).fillna(False).to_numpy()]='Senior 65+'
    life[(age.lt(30).fillna(False)&student).to_numpy()]='Student / mladý dospělý'
    life[(age.lt(35).fillna(False)&~student&~parent).to_numpy()]='Mladý bez dětí'
    life[parent.to_numpy()]='Rodič'
    life[(age.between(35,64).fillna(False)&~parent&partner).to_numpy()]='Střední věk · partner bez dětí v domácnosti'
    out['life_stage_derived']=pd.Series(life,index=out.index,dtype='string')

    def mean_existing(cols):
        vals=[_series_numeric(out[c]) for c in cols if c in out.columns]
        return pd.concat(vals,axis=1).mean(axis=1) if vals else pd.Series(np.nan,index=out.index)
    digital=mean_existing(['smartphone_use_intensity_1_10','computer_use_intensity_1_10','digital_communication_intensity_1_10','online_information_intensity_1_10','online_entertainment_intensity_1_10','online_transactions_intensity_1_10','digital_personal_management_intensity_1_10'])
    out['digital_engagement_tier_derived']=_tier(digital)

    media_map={
      'TV':'tv_intensity_1_10','Rádio':'radio_intensity_1_10','Tisk':'print_intensity_1_10',
      'Sociální sítě':'social_media_intensity_1_10','Online zprávy':'online_information_intensity_1_10','Online video':'online_entertainment_intensity_1_10'}
    mm=pd.DataFrame({k:_series_numeric(out[v]) for k,v in media_map.items() if v in out.columns})
    out['dominant_media_derived']=(mm.idxmax(axis=1).fillna('Bez dominantního kanálu') if not mm.empty else pd.Series('Bez dominantního kanálu',index=out.index,dtype='string')).astype('string')

    leisure_map={'Gaming':'gaming_intensity_1_10','Cestování':'travel_intensity_1_10','Sport':'sport_activity_1_10','Outdoor':'outdoor_activity_1_10','Socializace':'socializing_offline_1_10','Restaurace':'dining_out_1_10','Kultura':'culture_activity_1_10','Nightlife':'nightlife_1_10','DIY / domov':'diy_home_activity_1_10','Vaření':'cooking_activity_1_10'}
    lm=pd.DataFrame({k:_series_numeric(out[v]) for k,v in leisure_map.items() if v in out.columns})
    out['dominant_leisure_derived']=(lm.idxmax(axis=1).fillna('Bez dominantní aktivity') if not lm.empty else pd.Series('Bez dominantní aktivity',index=out.index,dtype='string')).astype('string')

    price=mean_existing(['price_sensitivity_1_10','deal_proneness_1_10']); premium=mean_existing(['premium_willingness_1_10','status_consumption_1_10']); research=mean_existing(['research_orientation_1_10','review_reliance_1_10']); convenience=mean_existing(['convenience_orientation_1_10'])
    shop=pd.DataFrame({'Value / slevy':price,'Premium / status':premium,'Research / recenze':research,'Convenience':convenience})
    shop_any=shop.notna().any(axis=1); shop_safe=shop.fillna(-np.inf)
    orient=shop_safe.idxmax(axis=1).astype('string');orient.loc[~shop_any]='Vyvážená'
    out['shopping_orientation_derived']=orient

    positive=mean_existing(['social_proof_susceptibility_1_10','influencer_receptivity_1_10','authority_receptivity_1_10','scarcity_response_1_10','tv_ad_attention_1_10','social_ad_attention_1_10','search_ad_attention_1_10'])
    resistance=mean_existing(['advertising_skepticism_1_10','reactance_1_10','ad_avoidance_1_10'])
    adscore=(positive-(resistance-5.5)*0.55).clip(1,10)
    out['ad_receptivity_tier_derived']=_tier(adscore)
    out['financial_capability_tier_derived']=_tier(_series_numeric(out.get('financial_capability_1_10',pd.Series(np.nan,index=out.index))))
    return out


def _overlay_meta()->dict[str,Any]:
    if not OVERLAY_META.is_file():return {'dimensions':{}}
    try:return json.loads(OVERLAY_META.read_text(encoding='utf-8'))
    except Exception:return {'dimensions':{}}


def attach_evidence_overlays(df:pd.DataFrame)->pd.DataFrame:
    out=df.copy(); meta=_overlay_meta(); dims=meta.get('dimensions') or {}
    if 'panel_row_id' not in out.columns:return out
    for did,spec in dims.items():
        if str(spec.get('runtime_status') or '')!='SIMULATED_FROM_EVIDENCE':continue
        # Idempotent: prototype_server already enriches the cached panel. Calling
        # catalog/enrich again must not create _x/_y columns or hide a custom factor.
        if did in out.columns:continue
        path=spec.get('overlay_path')
        if not path:continue
        p=Path(path); p=p if p.is_absolute() else ROOT/p
        if not p.is_file():continue
        try:
            ov=pd.read_csv(p,low_memory=False)
            if 'panel_row_id' not in ov.columns or did not in ov.columns:continue
            out=out.merge(ov[['panel_row_id',did]],on='panel_row_id',how='left',validate='one_to_one')
        except Exception:continue
    return out


def enrich_panel(df:pd.DataFrame)->pd.DataFrame:
    return attach_evidence_overlays(attach_derived(df))


def _kind(s:pd.Series)->str:
    vals=s.dropna()
    if vals.empty:return 'category'
    numeric=pd.api.types.is_numeric_dtype(vals)
    uniq=vals.nunique(dropna=True)
    if numeric:
        keys=set(str(float(x)).rstrip('0').rstrip('.') for x in vals.unique()[:50])
        if uniq<=2 and keys.issubset({'0','1'}):return 'binary'
        if uniq<=12 and not any(tok in str(s.name) for tok in ('minutes','prijem_osobni','prijem_domacnosti','hours','trips')):return 'numeric'
        return 'numeric'
    return 'category'


def _factor(df:pd.DataFrame,col:str,category:str,*,status='PANEL_EXISTING',filterable=True,sensitive=False,source='Panel v17') -> dict[str,Any] | None:
    if col not in df.columns:return None
    s=df[col]; kind=_kind(s); out={'id':col,'column':col,'label':_label(col),'category':category,'category_label':CATEGORY_META[category][0],'kind':kind,'status':status,'filterable':bool(filterable),'sensitive':bool(sensitive),'source':source,'non_null':int(s.notna().sum())}
    if kind=='numeric':
        x=_series_numeric(s).dropna()
        if len(x):out.update({'min':float(x.min()),'max':float(x.max()),'p10':float(x.quantile(.1)),'p90':float(x.quantile(.9))})
        if col.endswith('_1_10'):out.update({'min':1.0,'max':10.0,'scale_hint':'1–10'})
    else:
        vals=s.dropna().astype(str).value_counts().head(60)
        out['values']=[{'value':k,'count':int(v)} for k,v in vals.items()]
    return out


def catalog(df:pd.DataFrame, *, include_research_only:bool=True)->dict[str,Any]:
    enriched=enrich_panel(df)
    factors=[];seen=set()
    for cat,cols in CATEGORY_COLUMNS.items():
        for col in cols:
            x=_factor(enriched,col,cat)
            if x and col not in seen:factors.append(x);seen.add(col)
    for col in DERIVED_COLUMNS:
        x=_factor(enriched,col,'derived',status='DERIVED_EXISTING_SIGNALS',source='Deterministický overlay z existujících signálů')
        if x and col not in seen:factors.append(x);seen.add(col)
    meta=_overlay_meta().get('dimensions') or {}
    for did,spec in sorted(meta.items()):
        if str(spec.get('runtime_status') or '')!='SIMULATED_FROM_EVIDENCE' or did not in enriched.columns:continue
        x=_factor(enriched,did,'custom',status='SIMULATED_FROM_EVIDENCE',source=str(spec.get('evidence_summary') or 'Data Library evidence'))
        if x:
            x.update({'provenance':{'proposal_id':spec.get('proposal_id'),'source_entry_id':spec.get('source_entry_id'),'target_anchor':spec.get('target_anchor'),'predictors':spec.get('predictors'),'materialized_at':spec.get('materialized_at')}})
            factors.append(x);seen.add(did)
    if include_research_only:
        for col in RESEARCH_ONLY:
            x=_factor(enriched,col,'research_only',status='PANEL_EXISTING_RESEARCH_ONLY',filterable=False,sensitive=True,source='Research-only panel signal')
            if x:factors.append(x)
    cats=[]
    for cid,(label,desc) in CATEGORY_META.items():
        count=sum(1 for x in factors if x['category']==cid)
        if count:cats.append({'id':cid,'label':label,'description':desc,'count':count,'filterable_count':sum(1 for x in factors if x['category']==cid and x['filterable'])})
    return {'version':'17.9.4','categories':cats,'factors':factors,'filterable_count':sum(bool(x['filterable']) for x in factors),'factor_count':len(factors),'base_columns':len(df.columns),'runtime_columns':len(enriched.columns),'logic':'OR uvnitř jedné dimenze, AND mezi dimenzemi'}


def factor_map(df:pd.DataFrame)->dict[str,dict[str,Any]]:
    return {x['id']:x for x in catalog(df)['factors']}


def search_catalog(df:pd.DataFrame,text:str,limit:int=50)->list[dict[str,Any]]:
    words=[w for w in re.findall(r'[a-zá-ž0-9]{3,}',str(text or '').lower()) if w not in {'lidé','lidi','které','který','skupina'}]
    fac=[x for x in catalog(df,include_research_only=False)['factors'] if x.get('filterable')]
    base={'vek','pohlavi','kraj','vzdelani','zamestnani_status','prijem_decile'}
    scored=[]
    for x in fac:
        hay=(x['id']+' '+x['label']+' '+x['category_label']).lower();score=10 if x['id'] in base else 0
        score+=sum(4 if w in x['label'].lower() else 2 if w in hay else 0 for w in words)
        if score:scored.append((score,x))
    return [x for _,x in sorted(scored,key=lambda z:(-z[0],z[1]['label']))[:limit]]


def deterministic_noise(ids:pd.Series,salt:str)->np.ndarray:
    out=np.empty(len(ids),dtype=float)
    for i,v in enumerate(ids.astype(str)):
        h=hashlib.sha256((salt+'|'+v).encode()).digest();u=(int.from_bytes(h[:8],'big')+.5)/(2**64)
        out[i]=u
    return out


def _predictor_score(df:pd.DataFrame,predictors:list[dict[str,Any]],dimension_id:str)->np.ndarray:
    parts=[]
    for row in predictors or []:
        col=str(row.get('column') or row.get('id') or '')
        if col not in df.columns:continue
        x=_series_numeric(df[col]);sd=float(x.std(ddof=0) or 0)
        if not np.isfinite(sd) or sd<=1e-12:continue
        z=((x-x.mean())/sd).fillna(0).to_numpy(float)
        direction=-1.0 if str(row.get('direction') or 'positive').lower() in {'negative','-','inverse'} else 1.0
        strength=float(row.get('strength') or row.get('weight') or 1.0)
        parts.append(direction*strength*z)
    base=np.mean(parts,axis=0) if parts else np.zeros(len(df),dtype=float)
    # deterministic residual prevents ties while remaining fully reproducible
    noise=deterministic_noise(df['panel_row_id'],dimension_id)-.5
    return base+.35*noise


def materialize_evidence_dimension(df:pd.DataFrame, *, dimension_id:str, spec:dict[str,Any], output_dir:Path|None=None)->dict[str,Any]:
    """Materialize one approved evidence-based respondent overlay.

    Fail closed unless the evidence supplies a quantitative population anchor and at
    least one existing numeric/binary predictor.  Relationships alone never invent a
    population distribution.
    """
    did=re.sub(r'[^a-z0-9_]+','_',str(dimension_id or '').lower()).strip('_')
    if not did:raise ValueError('Chybí dimension_id.')
    if 'panel_row_id' not in df.columns:raise ValueError('Panel nemá panel_row_id; overlay nelze bezpečně navázat.')
    predictors=[dict(x) for x in (spec.get('predictors') or []) if isinstance(x,dict)]
    usable=[x for x in predictors if str(x.get('column') or x.get('id') or '') in df.columns and pd.api.types.is_numeric_dtype(df[str(x.get('column') or x.get('id'))])]
    if not usable:raise ValueError('Dosimulování vyžaduje alespoň jeden existující numerický/binary predictor z panelu.')
    kind=str(spec.get('kind') or spec.get('scale') or 'binary').lower()
    score=_predictor_score(df,usable,did)
    if kind in {'binary','boolean','prevalence'}:
        prev=spec.get('target_prevalence')
        try:prev=float(prev)
        except Exception:raise ValueError('Chybí evidence-based target_prevalence (0–1 nebo 0–100 %).')
        if prev>1:prev/=100.0
        if not (0<prev<1):raise ValueError('target_prevalence musí být mezi 0 a 1 (nebo 0–100 %).')
        w=pd.to_numeric(df.get('vaha_strukturalni_2025',df.get('vaha_kalibrovana',1.0)),errors='coerce').fillna(0).to_numpy(float)
        order=np.argsort(-score);target=prev*float(w.sum());cum=np.cumsum(w[order]);cut=int(np.searchsorted(cum,target,side='left'))
        vals=np.zeros(len(df),dtype='int8');vals[order[:min(len(order),cut+1)]]=1
        achieved=float((w*vals).sum()/w.sum()) if w.sum()>0 else float(vals.mean())
        anchor={'kind':'prevalence','target':prev,'achieved':achieved}
    elif kind in {'scale_1_10','1_10','continuous'}:
        mean=spec.get('target_mean')
        try:mean=float(mean)
        except Exception:raise ValueError('Chybí evidence-based target_mean pro škálovou dimenzi.')
        if not (1<=mean<=10):raise ValueError('target_mean pro scale_1_10 musí být 1–10.')
        ranks=pd.Series(score).rank(method='average',pct=True).to_numpy();vals=1+9*ranks
        vals=np.clip(vals+(mean-float(np.mean(vals))),1,10)
        vals=np.round(vals,2);anchor={'kind':'mean_1_10','target':mean,'achieved':float(np.mean(vals))}
    else:raise ValueError('Podporované kind: binary nebo scale_1_10.')
    od=output_dir or OVERLAY_DIR;od.mkdir(parents=True,exist_ok=True);path=od/f'{did}.csv.gz'
    pd.DataFrame({'panel_row_id':df['panel_row_id'].astype(str),did:vals}).to_csv(path,index=False,compression='gzip')
    raw=path.read_bytes();return {'dimension_id':did,'path':str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),'sha256':hashlib.sha256(raw).hexdigest(),'rows':len(df),'kind':kind,'target_anchor':anchor,'predictors':usable}
