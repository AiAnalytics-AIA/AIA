from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest


def _small_df(n=200):
    rng=np.random.default_rng(42)
    return pd.DataFrame({
      'panel_row_id':[f'R{i}' for i in range(n)],
      'vek':rng.integers(18,80,n),'is_parent':rng.integers(0,2,n),'is_student':rng.integers(0,2,n),'is_employed':rng.integers(0,2,n),'has_partner':rng.integers(0,2,n),
      'social_media_intensity_1_10':rng.uniform(1,10,n),'online_information_intensity_1_10':rng.uniform(1,10,n),'online_entertainment_intensity_1_10':rng.uniform(1,10,n),'online_transactions_intensity_1_10':rng.uniform(1,10,n),
      'news_online_weekly':rng.uniform(0,1,n),'tv_intensity_1_10':rng.uniform(1,10,n),'radio_intensity_1_10':rng.uniform(1,10,n),'print_intensity_1_10':rng.uniform(1,10,n),'online_video_user_2025':rng.integers(0,2,n),
      'gaming_intensity_1_10':rng.uniform(1,10,n),'travel_intensity_1_10':rng.uniform(1,10,n),'sport_activity_1_10':rng.uniform(1,10,n),'outdoor_activity_1_10':rng.uniform(1,10,n),'socializing_offline_1_10':rng.uniform(1,10,n),'dining_out_1_10':rng.uniform(1,10,n),'culture_activity_1_10':rng.uniform(1,10,n),'nightlife_1_10':rng.uniform(1,10,n),'diy_home_activity_1_10':rng.uniform(1,10,n),'cooking_activity_1_10':rng.uniform(1,10,n),
      'price_sensitivity_1_10':rng.uniform(1,10,n),'deal_proneness_1_10':rng.uniform(1,10,n),'premium_willingness_1_10':rng.uniform(1,10,n),'status_consumption_1_10':rng.uniform(1,10,n),'convenience_orientation_1_10':rng.uniform(1,10,n),'research_orientation_1_10':rng.uniform(1,10,n),'review_reliance_1_10':rng.uniform(1,10,n),
      'influencer_receptivity_1_10':rng.uniform(1,10,n),'social_proof_susceptibility_1_10':rng.uniform(1,10,n),'authority_receptivity_1_10':rng.uniform(1,10,n),'ad_avoidance_1_10':rng.uniform(1,10,n),'advertising_skepticism_1_10':rng.uniform(1,10,n),'reactance_1_10':rng.uniform(1,10,n),
      'financial_capability_1_10':rng.uniform(1,10,n),'vaha_strukturalni_2025':rng.uniform(.5,2,n),
      'kraj':rng.choice(['Hlavní město Praha','Středočeský kraj','Jihomoravský kraj'],n),
      'pohlavi':rng.choice(['Muž','Žena'],n)
    })


def test_catalog_exposes_broad_society_factor_categories():
    from prototype_server import load_panel_cached
    from audience_dimensions import catalog
    c=catalog(load_panel_cached())
    cats={x['id'] for x in c['categories']}
    assert c['filterable_count'] >= 100
    assert {'demography','digital','social','media','hobby','shopping','advertising','values','finance','work','derived'}.issubset(cats)


def test_hobby_catalog_contains_requested_lifestyle_signals():
    from prototype_server import load_panel_cached
    from audience_dimensions import catalog
    ids={x['id'] for x in catalog(load_panel_cached())['factors'] if x['category']=='hobby'}
    assert {'gaming_intensity_1_10','travel_intensity_1_10','sport_activity_1_10','outdoor_activity_1_10','culture_activity_1_10','cooking_activity_1_10'}.issubset(ids)


def test_sensitive_fields_are_research_only_not_targeting():
    from prototype_server import load_panel_cached
    from audience_dimensions import catalog
    rows={x['id']:x for x in catalog(load_panel_cached())['factors']}
    for k in ('core_religion_group','BFI_EXTR','volba_2021_strana'):
        if k in rows:
            assert rows[k]['sensitive'] is True and rows[k]['filterable'] is False and rows[k]['category']=='research_only'


def test_filter_logic_is_or_inside_factor_and_and_across_factors():
    from audience import _mask
    df=_small_df(300)
    m=_mask(df,{'kraj':['Hlavní město Praha','Středočeský kraj'],'sport_activity_1_10':{'min':7,'max':10}})
    expected=df.kraj.isin(['Hlavní město Praha','Středočeský kraj']) & df.sport_activity_1_10.between(7,10)
    assert m.equals(expected)


def test_real_sampling_honors_derived_factor_filter():
    from prototype_server import load_panel_cached
    from pipeline import Panel,sample_representative
    df=load_panel_cached().copy(); target='Vysoká'
    support=int((df['digital_engagement_tier_derived']==target).sum())
    assert support>100
    out=sample_representative(Panel(df),80,{'digital_engagement_tier_derived':[target]},seed=7)
    assert len(out)==80 and set(out['digital_engagement_tier_derived'].astype(str))=={target}


def test_derived_dimensions_are_deterministic():
    from audience_dimensions import attach_derived,DERIVED_COLUMNS
    df=_small_df(120);a=attach_derived(df);b=attach_derived(df.copy())
    for col in DERIVED_COLUMNS: pd.testing.assert_series_equal(a[col],b[col],check_names=True)


def test_evidence_dimension_requires_quantitative_anchor_and_predictor(tmp_path):
    from audience_dimensions import materialize_evidence_dimension
    df=_small_df(150)
    with pytest.raises(ValueError,match='target_prevalence'):
        materialize_evidence_dimension(df,dimension_id='new_interest',spec={'kind':'binary','predictors':[{'column':'sport_activity_1_10'}]},output_dir=tmp_path)
    with pytest.raises(ValueError,match='predictor'):
        materialize_evidence_dimension(df,dimension_id='new_interest',spec={'kind':'binary','target_prevalence':.3,'predictors':[]},output_dir=tmp_path)


def test_evidence_binary_materialization_hits_population_anchor(tmp_path):
    from audience_dimensions import materialize_evidence_dimension
    df=_small_df(500)
    r=materialize_evidence_dimension(df,dimension_id='new_interest',spec={'kind':'binary','target_prevalence':.31,'predictors':[{'column':'sport_activity_1_10','direction':'positive','strength':1}]},output_dir=tmp_path)
    assert Path(r['path']).is_file()
    assert abs(r['target_anchor']['achieved']-.31)<.015


def test_project_intake_provides_three_editable_design_variants():
    from ui_server import build_project_variants
    from research_project import empty_project
    a={'research_questions':['Q1','Q2','Q3','Q4'],'objectives':['O1','O2'],'hypotheses':['H1']}
    v=build_project_variants(a,empty_project(),300)
    assert [x['id'] for x in v]==['lean','recommended','deep']
    assert v[0]['n']<v[1]['n']<v[2]['n'] and v[2]['deep_research'] is True


def test_dimension_request_is_fail_closed_without_evidence_anchor(tmp_path,monkeypatch):
    import data_library
    monkeypatch.setattr(data_library,'DB_PATH',tmp_path/'lib.sqlite')
    monkeypatch.setattr(data_library,'OVERLAY_PATH',tmp_path/'overlays.json')
    r=data_library.create_dimension_request(label='Vztah k autonomní AI')
    data_library.decide_proposal(r['proposal_id'],'APPROVE')
    ready=data_library.dimension_materialization_readiness(r['proposal_id'])
    assert ready['ready'] is False
    assert any('target_' in x or 'knowledge_only' in x for x in ready['reasons'])


def test_approved_evidence_dimension_lifecycle_becomes_runtime_factor(tmp_path,monkeypatch):
    import data_library,audience_dimensions
    monkeypatch.setattr(data_library,'DB_PATH',tmp_path/'lib.sqlite');monkeypatch.setattr(data_library,'OVERLAY_PATH',tmp_path/'dimension_library_overlays.json')
    monkeypatch.setattr(audience_dimensions,'OVERLAY_META',tmp_path/'dimension_library_overlays.json');monkeypatch.setattr(audience_dimensions,'OVERLAY_DIR',tmp_path/'dims')
    r=data_library.create_dimension_request(label='Sportovní self-identita',dimension_id='sport_self_identity',spec={'kind':'binary','target_prevalence':.34,'quantitative_anchor_note':'Test evidence 34 %','predictors':[{'column':'sport_activity_1_10','direction':'positive','strength':1}]},origin='test')
    data_library.decide_proposal(r['proposal_id'],'APPROVE')
    df=_small_df(400)
    mat=audience_dimensions.materialize_evidence_dimension(df,dimension_id='sport_self_identity',spec=data_library.dimension_materialization_readiness(r['proposal_id'])['spec'],output_dir=tmp_path/'dims')
    meta={'version':'1','dimensions':{'sport_self_identity':{'runtime_status':'SIMULATED_FROM_EVIDENCE','evidence_summary':'Test evidence 34 %','overlay_path':mat['path'],'proposal_id':r['proposal_id'],'target_anchor':mat['target_anchor'],'predictors':mat['predictors']}}}
    (tmp_path/'dimension_library_overlays.json').write_text(json.dumps(meta),encoding='utf-8')
    enriched=audience_dimensions.enrich_panel(df);c=audience_dimensions.catalog(enriched)
    row=next(x for x in c['factors'] if x['id']=='sport_self_identity')
    assert row['status']=='SIMULATED_FROM_EVIDENCE' and row['category']=='custom' and row['filterable'] is True


def test_ui_and_server_expose_new_audience_dimension_workflow():
    root=Path(__file__).resolve().parents[1]
    ui=(root/'ui_app.html').read_text(encoding='utf-8');server=(root/'ui_server.py').read_text(encoding='utf-8')
    for text in ('3 MOŽNOSTI DESIGNU','FAKTORY SPOLEČNOSTI','Deep Research','Dosimulovat do respondentního datasetu','/api/audience/dimensions','/api/library/dimension/materialize'):
        assert text in ui or text in server
