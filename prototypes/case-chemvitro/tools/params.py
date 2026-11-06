"""ChemVitro case · the single source of truth for the generated data, the documents and the answer key.

Everything here is FICTIONAL: ChemVitro a.s., its sites, suppliers, people and numbers are invented.
generate.py (data), documents.py (documents) and reference.py (answer-key numbers) all read this file.
"""
SEED = 20261104

COMPANY = dict(name='ChemVitro a.s.', seat='Brno', product='VTX-40', product_long='VTX-40 (vitrolanový ester, fiktivní meziprodukt)',
               use_t_2026=34_000, use_growth=0.02, capacity_t=40_000, users={'Brno': 0.62, 'Pardubice': 0.38})

# the current supply contract (buy baseline)
BUY = dict(supplier='Hanshin Fine Chemicals Co. (fiktivní)', contract_end='2030-06-30', price_2026_eur_t=1_470,
           freight_2026_eur_t=96, renewal_rise=(0.12, 0.22), renewal_likely=0.17, price_vol_yearly=0.05)

# decision, constraints and rule (CASE §3-6)
DECISION = dict(decided_by='finanční ředitelka (FŘ) s představenstvem', deadline='2027-01-29', study_due='2027-01-15',
                start_by='2030-07-01', capex_ceiling_m=175, decision_date='2027-02-01',
                discount=0.08, discount_alt=(0.06, 0.10), horizon=(2027, 2044), residual_share=0.30,
                beat_prob=0.75, loss_limit_m=20, loss_prob=0.10, start_prob=0.80)

# process design (one design for every site): per tonne of VTX-40
PROCESS = dict(raw_t_per_t=1.25, el_mwh_per_t=0.35, gas_mwh_per_t=3.1, co2_t_per_mwh_gas=0.2, boiler_mw=24,
               ww_m3_per_t=4.2, ww_cod_mg_l=2_400, ww_sulfate_mg_l=1_800, ww_ph=(2.0, 3.0), voc_kg_per_t=0.9,
               nox_kg_per_t=0.55, hazwaste_t_per_t=0.045, raw_material_eur_t=540, fte=95, operating_days=330)

COUNTRIES = {'CZ': dict(name='Česko', cur='CZK', fx_eur=24.3, wage_growth=0.060),
             'DE': dict(name='Německo', cur='EUR', fx_eur=1.0, wage_growth=0.035),
             'PL': dict(name='Polsko', cur='PLN', fx_eur=4.27, wage_growth=0.070)}

# eight sites. 'trap' marks the hidden problems (ANSWER-KEY only); everything else is what the files show.
SITES = {
 'CZ1': dict(name='Vrbice', park='Průmyslová zóna Labe-jih', country='CZ', region='Ústecký kraj', plot_ha=22, land_eur_m2=24,
             epc_m=128, wage_eur=2_350, el=118, gas=41, sewer_eur_m3=3.1, haz_eur_t=310, inbound_eur_t=29, rail='vlečka v zóně',
             road='silnice I. třídy, 2 km', ww_body='průmyslová ČOV zóny (Labe-jih Servis)', incentive='investiční pobídka až 20 % (zákon 72/2000 Sb.)',
             trap='air', air=dict(pm10=31, pm25=21, no2=27, bap=1.8)),
 'CZ2': dict(name='Lipová', park='Park Lipová', country='CZ', region='Olomoucký kraj', plot_ha=19, land_eur_m2=19,
             epc_m=124, wage_eur=2_250, el=118, gas=41, sewer_eur_m3=2.8, haz_eur_t=355, inbound_eur_t=34, rail='železniční stanice 1,1 km',
             road='silnice II. třídy', ww_body='městská ČOV Lipová (Vodovody Lipovsko)', incentive='investiční pobídka až 20 % (zákon 72/2000 Sb.)',
             trap='wastewater', air=dict(pm10=22, pm25=14, no2=17, bap=0.7)),
 'CZ3': dict(name='Kamenec', park='Průmyslová zóna Kamenec', country='CZ', region='Moravskoslezský kraj', plot_ha=21, land_eur_m2=27,
             epc_m=126, wage_eur=2_400, el=118, gas=41, sewer_eur_m3=3.0, haz_eur_t=290, inbound_eur_t=31, rail='vlečka v zóně (provozovaná)',
             road='dálnice D1, 4 km', ww_body='průmyslová ČOV zóny Kamenec', incentive='investiční pobídka až 25 % (zákon 72/2000 Sb.)',
             trap=None, air=dict(pm10=27, pm25=17, no2=24, bap=0.9), air_2021_bap=1.3, competitor_hiring=380),
 'DE1': dict(name='Wendelstedt', park='Chemiepark Wendelstedt', country='DE', region='Sachsen-Anhalt', plot_ha=18, land_eur_m2=38,
             epc_m=141, wage_eur=4_900, el=109, gas=43, sewer_eur_m3=4.6, haz_eur_t=240, inbound_eur_t=22, rail='Werksbahn im Park',
             road='A9, 6 km', ww_body='Industriekläranlage des Chemieparks', incentive='GRW-Förderung bis 15 %', trap=None,
             air=dict(pm10=19, pm25=12, no2=19, bap=0.4), park_fee_m=1.1),
 'DE2': dict(name='Lindenau', park='Industriegebiet Lindenau-Ost', country='DE', region='Sachsen', plot_ha=20, land_eur_m2=29,
             epc_m=133, wage_eur=4_700, el=132, gas=43, sewer_eur_m3=3.9, haz_eur_t=265, inbound_eur_t=27, rail='Bahnhof Lindenau 2,5 km',
             road='B6, 3 km', ww_body='kommunale Kläranlage Lindenau (Zweckverband)', incentive='GRW-Förderung bis 20 %',
             trap='wastewater', air=dict(pm10=18, pm25=11, no2=16, bap=0.3)),
 'DE3': dict(name='Eschfeld', park='Gewerbepark Eschfeld', country='DE', region='Bayern', plot_ha=19, land_eur_m2=55,
             epc_m=138, wage_eur=5_600, el=132, gas=43, sewer_eur_m3=4.2, haz_eur_t=250, inbound_eur_t=33, rail='Bahnstrecke 0,8 km',
             road='Kreisstraße, A93 7 km', ww_body='kommunale Kläranlage Eschfeld', incentive='keine Regionalförderung',
             trap='logistics', air=dict(pm10=17, pm25=11, no2=15, bap=0.3)),
 'PL1': dict(name='Odrzyca', park='Park Przemysłowy Odrzyca', country='PL', region='Opolskie', plot_ha=24, land_eur_m2=16,
             epc_m=119, wage_eur=2_150, el=128, gas=44, sewer_eur_m3=2.6, haz_eur_t=330, inbound_eur_t=28, rail='bocznica kolejowa 3,4 km',
             road='A4, 5 km', ww_body='oczyszczalnia przemysłowa parku', incentive='zwolnienie z CIT (Polska Strefa Inwestycji) do 35 %',
             trap='logistics', air=dict(pm10=24, pm25=16, no2=19, bap=0.8)),
 'PL2': dict(name='Bory', park='Strefa Aktywności Gospodarczej Bory', country='PL', region='Śląskie', plot_ha=25, land_eur_m2=14,
             epc_m=117, wage_eur=2_300, el=128, gas=44, sewer_eur_m3=2.4, haz_eur_t=300, inbound_eur_t=26, rail='bocznica w strefie',
             road='A1, 3 km', ww_body='miejska oczyszczalnia Bory (PWiK Bory)', incentive='zwolnienie z CIT (Polska Strefa Inwestycji) do 50 %',
             trap='air', air=dict(pm10=36, pm25=27, no2=31, bap=3.9)),
}
SITE_ORDER = ['CZ1', 'CZ2', 'CZ3', 'DE1', 'DE2', 'DE3', 'PL1', 'PL2']
# outbound freight to the users (Brno 62 %, Pardubice 38 %), EUR per tonne
OUTBOUND = {'CZ1': 34, 'CZ2': 18, 'CZ3': 21, 'DE1': 52, 'DE2': 47, 'DE3': 49, 'PL1': 33, 'PL2': 29}

# the hidden costs (true values; visible only by combining files and documents)
TRAPS = {
 'CZ2': dict(kind='wastewater', where='vyjadreni_cov.pdf s. 2 + proces_emise_odpady.xlsx',
             limits=dict(sulfate=300, cod=800), spare_m3_day=600, surcharge_eur_m3=14.0, pretreat_capex_m=11.0, pretreat_opex_m=0.7,
             delay_months=(2, 5), note='kanalizační řád: síranů nejvýše 300 mg/l, CHSK 800 mg/l; nad limit příplatek, nebo předčištění'),
 'DE2': dict(kind='wastewater', where='vyjadreni_cov.pdf s. 5 + proces_emise_odpady.xlsx',
             limits=dict(sulfate=600, cod=1000), spare_m3_day=250, surcharge_eur_m3=None, pretreat_capex_m=13.0, pretreat_opex_m=0.8,
             delay_months=(4, 8), note='freie Kapazität 250 m³/Tag < Bedarf ~433 m³/Tag: eigene Vorbehandlung und Teil-Direkteinleitung nötig'),
 'CZ1': dict(kind='air', where='ovzdusi_stanice.csv + memo_povolovani_ovzdusi.pdf s. 2',
             offset_m=(5.0, 9.0), abatement_capex_m=4.5, abatement_opex_m=0.4, delay_months=(9, 15)),
 'PL2': dict(kind='air', where='ovzdusi_stanice.csv + memo_povolovani_ovzdusi.pdf s. 3',
             offset_m=(7.0, 13.0), abatement_capex_m=5.0, abatement_opex_m=0.45, delay_months=(12, 18)),
 'PL1': dict(kind='logistics', where='vyjadreni_doprava.pdf s. 7 + nabidky_lokalit.pdf s. 7',
             spur_km=3.4, spur_eur_m_per_km=(1.9, 2.8), land_m=1.2, truck_extra_eur_t=16, delay_months=(0, 10)),
 'DE3': dict(kind='logistics', where='vyjadreni_doprava.pdf s. 6',
             bridge_limit_t=16, tanker_t=40, reinforcement_m=(3.2, 5.0), delay_months=(6, 10)),
}

TIMING = dict(permit_months=(8, 9, 11), build_months=(20, 22, 26))   # min, likely, max (base, every site)
EPC_ACCURACY = 0.25          # the EPC estimate's stated band (±25 %)
OVERRUN = dict(median=0.13, p90=0.38)   # what the comparable plants show (greenfield worse)

EXPERT_CRITERIA = ['Náklady', 'Povolování a životní prostředí', 'Pracovní síla', 'Logistika', 'Rizika lokality', 'Pobídky a podpora']
EXPERTS = [('GR', 'generální ředitel'), ('FR', 'finanční ředitelka'), ('VR', 'výrobní ředitel'), ('EHS', 'vedoucí EHS'),
           ('HR', 'personální ředitelka'), ('LOG', 'vedoucí logistiky'), ('NAK', 'vedoucí nákupu'), ('TI1', 'technolog 1'),
           ('TI2', 'technolog 2'), ('PRA', 'právník'), ('ZAM', 'zástupce zaměstnanců'), ('KON', 'externí konzultant LokaPartner')]

# competition for staff: first-year output share while hiring (min, max) and a wage premium (max) where big employers hire
STAFFING = {'CZ3': dict(ramp=(0.55, 0.90), premium=0.10), 'DE3': dict(ramp=(0.50, 0.85), premium=0.06), 'PL2': dict(ramp=(0.65, 0.90), premium=0.04),
            'default': dict(ramp=(0.70, 0.95), premium=0.0)}

SURVEY = dict(n=300, by_country={'CZ': 174, 'DE': 66, 'PL': 60}, straightliners=9, duplicates=6, home_bias=2.0)
# chemical-industry workers per country (labour pool, for weighting the survey)
LABOUR_POOL = {'CZ': 31_000, 'DE': 46_000, 'PL': 24_000}
