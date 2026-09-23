from __future__ import annotations
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, os
from itertools import product
ROOT=Path(__file__).resolve().parent
policy=json.loads((ROOT/'PROJECT_POLICY.json').read_text(encoding='utf-8'))
PANEL=ROOT/str(policy.get('production',{}).get('panel') or policy.get('production_panel') or 'FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz')
df=pd.read_csv(PANEL,low_memory=False)
W=pd.to_numeric(df['vaha_strukturalni_2025'],errors='coerce').fillna(0).astype(float)
FIELDS=[x.strip()+'_1_10' for x in '''linkedin_affinity, social_passive_consumption, social_public_interaction, social_private_sharing, social_algorithm_discovery, social_relaxation_use, travel_intensity, sport_activity, outdoor_activity, socializing_offline, dining_out, culture_activity, nightlife, diy_home_activity, cooking_activity, physical_retail_activity, commute_intensity, caregiving_intensity, price_sensitivity, deal_proneness, premium_willingness, purchase_planning, impulse_buying, research_orientation, review_reliance, novelty_orientation, risk_aversion, brand_consciousness, brand_loyalty_general, convenience_orientation, local_brand_preference, sustainability_orientation, status_consumption, privacy_concern, persuasion_knowledge, advertising_skepticism, reactance, need_for_cognition, need_for_affect, social_proof_susceptibility, influencer_receptivity, authority_receptivity, scarcity_response, ad_avoidance, social_ad_attention, search_ad_attention, audio_ad_attention, ooh_ad_attention, category_knowledge_general, market_knowledge_general, advertising_literacy'''.split(',')]

# ---------- WP1 rules / correlation QC ----------
rules=[
("R01","advertising_skepticism_1_10","ad_avoidance_1_10",.50,.35,.65,"LITERATURE_ANCHOR","Ad skepticism/irritation and avoidance/ad-blocking empirical literature; target is conservative structural design prior, not a universal population parameter.","2021 empirical ad-avoidance study"),
("R02","advertising_skepticism_1_10","reactance_1_10",.40,.25,.55,"LITERATURE_ANCHOR","Reactance is a documented correlate/antecedent of commercial advertising skepticism; target is a structural prior.","2009 advertising skepticism scale study"),
("R03","persuasion_knowledge_1_10","advertising_skepticism_1_10",.35,.20,.50,"MIXED_EVIDENCE","Persuasion knowledge and skepticism are related in some contexts but not invariant; use positive moderate prior, not a claimed universal law.","Persuasion-knowledge studies 2020/2021; mixed evidence"),
("R04","price_sensitivity_1_10","deal_proneness_1_10",.50,.35,.65,"STRUCTURAL_PRIOR_INFORMED_BY_CONSTRUCT_LITERATURE","Price-related consumer constructs share variance but remain distinct.","Lichtenstein, Ridgway & Netemeyer 1993, Journal of Marketing Research"),
("R05","novelty_orientation_1_10","brand_loyalty_general_1_10",-.30,-.48,-.12,"MIXED_EVIDENCE","Variety/novelty seeking can weaken loyalty, but direction is domain-dependent; retained only as conservative structural prior.","Variety-seeking/loyalty literature; domain-dependent"),
("R06","purchase_planning_1_10","impulse_buying_1_10",-.45,-.62,-.28,"ASSUMED_STRUCTURAL_PRIOR","Opposing decision-style constructs; no single Czech population r claimed.","ASSUMED"),
("R07","research_orientation_1_10","review_reliance_1_10",.50,.35,.65,"ASSUMED_STRUCTURAL_PRIOR","Related information-search behaviors, deliberately not identical.","ASSUMED"),
("R08","social_relaxation_use_1_10","social_private_sharing_1_10",.70,.55,.82,"PRESERVED_MEASURED_MODEL_BLOCK","Existing coherent social-use joint block preserved from v16.","v16 source-preservation design"),
("R09","social_relaxation_use_1_10","social_algorithm_discovery_1_10",.70,.55,.82,"PRESERVED_MEASURED_MODEL_BLOCK","Existing coherent social-use joint block preserved from v16.","v16 source-preservation design"),
("R10","social_public_interaction_1_10","social_relaxation_use_1_10",.65,.50,.80,"PRESERVED_MEASURED_MODEL_BLOCK","Existing coherent social-use joint block preserved from v16.","v16 source-preservation design"),
("R11","social_media_minutes_day","BFI_EMOS",.08,.001,.23,"LITERATURE_WEAK_EFFECT","Preregistered positive weak-effect direction; exact magnitude is not treated as universal.","audit literature anchor"),
("R12","social_media_minutes_day","BFI_CONS",-.04,-.19,-.001,"LITERATURE_WEAK_EFFECT","Preregistered negative weak-effect direction; exact magnitude is not treated as universal.","audit literature anchor"),
]
rule_df=pd.DataFrame(rules,columns=['rule_id','field_a','field_b','target_r','tolerance_low','tolerance_high','evidence_class','interpretation','source'])
obs=[]
for _,r in rule_df.iterrows():
    x=pd.to_numeric(df[r.field_a],errors='coerce'); y=pd.to_numeric(df[r.field_b],errors='coerce'); rr=float(x.corr(y));
    status='PASS' if r.tolerance_low <= rr <= r.tolerance_high else 'FAIL'
    obs.append(rr)
rule_df['observed_r']=obs; rule_df['abs_deviation_from_target']=(rule_df.observed_r-rule_df.target_r).abs(); rule_df['status']=['PASS' if lo<=o<=hi else 'FAIL' for o,lo,hi in zip(rule_df.observed_r,rule_df.tolerance_low,rule_df.tolerance_high)]
rule_df.to_csv(ROOT/'PSYCH_BEHAVIOR_RULES_v17_1.csv',index=False)

corr=df[FIELDS].corr()
tri=np.abs(corr.to_numpy()[np.triu_indices(len(FIELDS),1)])
summary={
 'n_fields':len(FIELDS),'median_abs_r':float(np.median(tri)),'mean_abs_r':float(np.mean(tri)),
 'share_abs_r_gt_0_2':float((tri>.2).mean()),'share_abs_r_gt_0_4':float((tri>.4).mean()),'max_abs_r':float(tri.max()),
 'target_median_abs_r_low':.12,'target_median_abs_r_high':.25,
}
qc_rows=[]
for i,a in enumerate(FIELDS):
    for b in FIELDS[i+1:]: qc_rows.append({'pair_type':'ALL_MODELED','field_a':a,'field_b':b,'target_r':np.nan,'observed_r':corr.loc[a,b],'tolerance_low':np.nan,'tolerance_high':np.nan,'status':'INFO'})
for _,r in rule_df.iterrows(): qc_rows.append({'pair_type':'ANCHORED','field_a':r.field_a,'field_b':r.field_b,'target_r':r.target_r,'observed_r':r.observed_r,'tolerance_low':r.tolerance_low,'tolerance_high':r.tolerance_high,'status':r.status})
qc=pd.DataFrame(qc_rows)
# Frobenius norm on anchored target matrix against observed for only anchored pair entries
fro=float(np.sqrt(np.sum((rule_df.observed_r-rule_df.target_r)**2)))
qc['global_median_abs_r']=summary['median_abs_r']; qc['anchor_frobenius_norm']=fro
qc.to_csv(ROOT/'CORRELATION_MATRIX_QC_v17_1.csv',index=False)
(ROOT/'CORRELATION_MATRIX_SUMMARY_v17_1.json').write_text(json.dumps({**summary,'anchored_pairs':len(rule_df),'anchor_failures':int((rule_df.status=='FAIL').sum()),'anchor_frobenius_norm':fro},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Exact marginal preservation vs v17_0 where available.
base=ROOT/'audit_reference'/'FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz'
if base.exists():
    d0=pd.read_csv(base,usecols=FIELDS,low_memory=False)
    marg=[]
    for c in FIELDS:
        a=pd.to_numeric(d0[c],errors='coerce'); b=pd.to_numeric(df[c],errors='coerce'); sd=float(a.std()) or 1.; shift=float((b.mean()-a.mean())/sd)
        same=bool(np.allclose(np.sort(a.to_numpy()),np.sort(b.to_numpy()),equal_nan=True,rtol=0,atol=0))
        marg.append({'field':c,'mean_v17_0':a.mean(),'mean_v17_1':b.mean(),'sd_v17_0':sd,'mean_shift_sd':shift,'exact_sorted_marginal_preserved':same,'status':'PASS' if abs(shift)<=.05 and same else 'FAIL'})
    pd.DataFrame(marg).to_csv(ROOT/'MARGINAL_PRESERVATION_QC_v17_1.csv',index=False)

# Joint tails comparison from old to new: same-factor coextremes and selected contradictions.
def extreme_count(frame, cols, high=True):
    A=np.column_stack([pd.to_numeric(frame[c],errors='coerce').to_numpy(float)>=8 if high else pd.to_numeric(frame[c],errors='coerce').to_numpy(float)<=3 for c in cols])
    return (A.sum(axis=1)>=3).mean()
if base.exists():
    d0=pd.read_csv(base,low_memory=False)
    factor_groups={
      'F1_DEAL':['price_sensitivity_1_10','deal_proneness_1_10','local_brand_preference_1_10'],
      'F2_DELIB':['purchase_planning_1_10','research_orientation_1_10','review_reliance_1_10','need_for_cognition_1_10'],
      'F3_RESIST':['persuasion_knowledge_1_10','advertising_skepticism_1_10','reactance_1_10','ad_avoidance_1_10','privacy_concern_1_10'],
      'F6_ACTIVITY':['travel_intensity_1_10','sport_activity_1_10','outdoor_activity_1_10','socializing_offline_1_10','dining_out_1_10','culture_activity_1_10','nightlife_1_10']}
    tails=[]
    for fac,cols in factor_groups.items():
        old=extreme_count(d0,cols); new=extreme_count(df,cols); tails.append({'check':fac+'_3plus_high','v17_0':old,'v17_1':new,'desired':'increase','status':'PASS' if new>old else 'FAIL'})
    contradictions=[('price_and_premium',['price_sensitivity_1_10','deal_proneness_1_10','premium_willingness_1_10']),('novel_and_loyal',['novelty_orientation_1_10','brand_loyalty_general_1_10','risk_aversion_1_10'])]
    for name,cols in contradictions:
        old=extreme_count(d0,cols); new=extreme_count(df,cols); tails.append({'check':name+'_contradictory_3plus_high','v17_0':old,'v17_1':new,'desired':'decrease','status':'PASS' if new<old else 'WARN'})
    pd.DataFrame(tails).to_csv(ROOT/'JOINT_TAIL_QC_v17_1.csv',index=False)

# ---------- WP2: calibration reproduction ----------
oldcal=ROOT/'audit_reference'/'legacy_17_0_1'/'MARKETING_BENCHMARK_VALIDATION_v17.csv'
if oldcal.exists():
    cal=pd.read_csv(oldcal)
    cal.insert(0,'check_class','CALIBRATION_REPRODUCTION_NOT_VALIDATION')
    cal['interpretation']='Kontrola, že build reprodukuje cíle použité při kalibraci. Není to out-of-sample validace.'
    cal.to_csv(ROOT/'CALIBRATION_REPRODUCTION_CHECK_v17_1.csv',index=False)

# preregistered OOS checks from ČSÚ Information Society in Figures 2026, 2025 conditional cells not used as generator targets.
def wpct(mask,col):
    m=pd.Series(mask,index=df.index).fillna(False).astype(bool) & df[col].notna(); ww=W[m]; x=pd.to_numeric(df.loc[m,col],errors='coerce')
    return 100.*float(np.average(x,weights=ww)) if len(x) and ww.sum()>0 else np.nan
checks=[]
def add(cid,desc,target,tol,mask,col,source,universe,direction='two_sided',generator_input=False,check_class='OUT_OF_SAMPLE'):
    obs=wpct(mask,col); low=target-tol; high=target+tol
    status='PASS' if low<=obs<=high else 'FAIL'
    checks.append({'check_id':cid,'check_class':check_class,'description':desc,'target':target,'tolerance_low':low,'tolerance_high':high,'direction_required':direction,'observed':obs,'abs_error_pp':abs(obs-target),'source':source,'universe':universe,'generator_input':bool(generator_input),'status':status})
allmask=pd.Series(True,index=df.index)
source='ČSÚ, Informační společnost v číslech 2026, Tab. C9/F5; reference year 2025'
add('OOS01','Social-network use: men',59.6,3.0,df.pohlavi.eq('muž'),'social_network_user_2025',source,'panel 18+ vs source 16+',generator_input=True,check_class='CALIBRATION_REGRESSION')
add('OOS02','Social-network use: women',66.6,3.0,df.pohlavi.eq('žena'),'social_network_user_2025',source,'panel 18+ vs source 16+',generator_input=True,check_class='CALIBRATION_REGRESSION')
# Explicit directional gender gap check
men=wpct(df.pohlavi.eq('muž'),'social_network_user_2025'); women=wpct(df.pohlavi.eq('žena'),'social_network_user_2025'); target_gap=7.0; obs_gap=women-men
checks.append({'check_id':'OOS03','check_class':'CALIBRATION_REGRESSION','description':'Social-network gender gap women-minus-men','target':target_gap,'tolerance_low':2.0,'tolerance_high':12.0,'direction_required':'positive','observed':obs_gap,'abs_error_pp':abs(obs_gap-target_gap),'source':source,'universe':'panel 18+ vs source 16+','generator_input':True,'status':'PASS' if 2<=obs_gap<=12 else 'FAIL'})
st=df['is_student'].fillna(False).astype(bool)
student_specs=[
 ('OOS04','Students: internet',100.0,'internet_user_2025'),('OOS05','Students: mobile internet',100.0,'mobile_internet_user_2025'),
 ('OOS06','Students: social networks',98.6,'social_network_user_2025'),('OOS07','Students: online video',98.3,'online_video_user_2025'),
 ('OOS08','Students: online music',99.1,'online_music_user_2025'),('OOS09','Students: online shopping',92.8,'online_shopper_2025'),
 ('OOS10','Students: online news',84.6,'online_news_user_2025'),('OOS11','Students: internet banking',86.3,'internet_banking_user_2025')]
for cid,desc,target,col in student_specs:add(cid,desc,target,5.0,st,col,source,'panel students 18+ vs source students 16+')
add('OOS12','Male students: social networks',98.1,4.0,st&df.pohlavi.eq('muž'),'social_network_user_2025',source,'student 18+ proxy')
add('OOS13','Female students: social networks',99.0,4.0,st&df.pohlavi.eq('žena'),'social_network_user_2025',source,'student 18+ proxy')
add('OOS14','Male students: online video',97.4,4.0,st&df.pohlavi.eq('muž'),'online_video_user_2025',source,'student 18+ proxy')
add('OOS15','Female students: online video',99.0,4.0,st&df.pohlavi.eq('žena'),'online_video_user_2025',source,'student 18+ proxy')
oos=pd.DataFrame(checks); oos.to_csv(ROOT/'OUT_OF_SAMPLE_VALIDATION_v17_1.csv',index=False)

# ---------- WP3 donor coverage matrix ----------
layers={
'core':'core_donor_id','mental_health':'_donor_mental_health_id','social_network':'_donor_social_network_id','institutions':'_donor_institutions_id','rule_of_law':'_donor_rule_of_law_id','politics':'_donor_politics_id','family_health':'_donor_family_health_id'}
agebins=pd.cut(pd.to_numeric(df['vek'],errors='coerce'),[17,29,44,64,79,200],labels=['18-29','30-44','45-64','65-79','80+'])
mat=[]
for (kraj,sex,ag),idx in df.groupby([df['kraj'],df['pohlavi'],agebins],observed=True).groups.items():
    sub=df.loc[idx]; ww=W.loc[idx]
    for layer,col in layers.items():
        donor=sub[col].astype(str).where(sub[col].notna(), pd.Series([f'missing_{i}' for i in sub.index],index=sub.index))
        counts=donor.value_counts(); nu=int(donor.nunique()); maxshare=float(counts.iloc[0]/len(sub)) if len(counts) else 0
        status='SUPPRESS' if nu<25 else ('INDICATIVE' if nu<50 else 'REPORTABLE')
        mat.append({'kraj':kraj,'pohlavi':sex,'vek_skupina':str(ag),'layer':layer,'n_rows':len(sub),'weighted_population':float(ww.sum()),'n_unique_donors':nu,'max_donor_share':maxshare,'support_status':status})
pd.DataFrame(mat).to_csv(ROOT/'DONOR_COVERAGE_MATRIX_v17_1.csv',index=False)

# overall donor registry summary
reg=[]
for layer,col in layers.items():
    vc=df[col].value_counts(dropna=True); reg.append({'layer':layer,'donor_column':col,'n_unique_donors':int(df[col].nunique(dropna=True)),'max_reuse':int(vc.max()) if len(vc) else 0,'median_reuse':float(vc.median()) if len(vc) else 0})
pd.DataFrame(reg).to_csv(ROOT/'DONOR_SUPPORT_SUMMARY_v17_1.csv',index=False)

# LLM ablation status/protocol (WP4 cannot be faked without credentials)
abstat={'version':'17.1.2','llm_ablation_run':False,'reason':'NO_LIVE_PROVIDER_CREDENTIALS_IN_BUILD_ENVIRONMENT','required_arms':['A_question_only','B_demographics','C_demographics_plus_measured','D_full_persona'],'required_metrics':['TVD','entropy_gap','modal_response_share','age_x_sex_subgroup_error','seed_variance'],'required_seeds':3,'decision_rule':'Keep marketing persona signals in LLM prompt only if D beats C and C beats B by more than between-seed noise on preregistered external truth.','release_effect':'EXTERNAL_PREDICTIVE_CERTIFICATION_PENDING'}
(ROOT/'LLM_ABLATION_STATUS_v17_1.json').write_text(json.dumps(abstat,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'LLM_ABLATION_RESULTS_v17_1.csv').write_text('arm,seed,target_id,tvd,entropy_gap,modal_share,subgroup_error,status\n',encoding='utf-8')
(ROOT/'LLM_ABLATION_PROTOCOL_v17_1.md').write_text('''# LLM ablation protocol — NPC Panel 17.1.2\n\nStatus: **NOT RUN — no live provider credentials in build environment.** This is not a PASS.\n\n## Arms\nA: question only. B: demographics only. C: demographics + measured/matched evidence. D: full persona including modeled marketing layer.\n\n## Required truth\nUse a Czech human-response holdout that was not used to calibrate or build the panel, ideally post-model-cutoff. Lock the truth file hash before API runs.\n\n## Metrics\nTVD, entropy gap, modal-response collapse, age×sex subgroup error, and between-seed variance. Run at least 3 seeds per arm.\n\n## Decision rule\nMarketing signals remain in LLM prompts only if D improves over C, and C over B, by more than between-seed noise. Otherwise modeled marketing remains available for segmentation/planning but is excluded from respondent prompts by default.\n''',encoding='utf-8')

# WP6 placeholder under explicit project governance; no invented license facts.
sources=pd.read_csv(ROOT/'FINAL_SOURCE_CATALOG_v17.csv') if (ROOT/'FINAL_SOURCE_CATALOG_v17.csv').exists() else pd.DataFrame()
namecol=next((c for c in ['source','name','source_name','dataset'] if c in sources.columns),None)
unique=[]
if namecol:
    unique=[str(x) for x in sources[namecol].dropna().unique()[:1000]]
else: unique=['PIAAC 2023 CZ','ISSP 2022 CZ','ČSÚ ICT 2025','AMI Digital Index 2026','Reuters Institute DNR','ATO PCEM','RADIOPROJEKT','MEDIA PROJEKT','JRC/EU-SILC','QoG']
lic=pd.DataFrame({'source':unique})
for c in ['provider','acquisition_route','license_type','commercial_use','derivative_product','third_party_transfer','evidence_document']:
    lic[c]='EXTERNALLY_MANAGED_NOT_REASSESSED'
lic['risk_grade']='EXTERNAL_COMPLIANCE_REGISTER_REQUIRED'
lic.to_csv(ROOT/'DATA_LICENSE_REGISTER.csv',index=False)

print(json.dumps({'correlation':summary,'anchor_failures':int((rule_df.status=='FAIL').sum()),'oos_checks':len(oos),'oos_failed':int((oos.status=='FAIL').sum()),'donor_matrix_rows':len(mat)},ensure_ascii=False,indent=2))
