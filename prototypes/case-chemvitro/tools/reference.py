"""ChemVitro case · the reference ("true") model behind ANSWER-KEY.md. Not part of the client's pack.

It costs every site and the buy baseline with the TRUE parameters, including the hidden trap costs, over 20 000 seeded
futures, and applies the CFO's rule. Writes answer_key_reference.json (in tools/).
Run:  ~/.venvs/aia-panel/bin/python ChemVitro/tools/reference.py
"""
import json
from pathlib import Path
import numpy as np
from params import SITES, SITE_ORDER, TRAPS, COMPANY, BUY, PROCESS, DECISION, TIMING, OUTBOUND, COUNTRIES, STAFFING

ROOT = Path(__file__).resolve().parents[1]
N = 20_000; SEED = 20270201
YEARS = np.arange(2027, 2045)
P = PROCESS


def tri(rng, a, m, b, n): return rng.triangular(a, m, b, n)


def simulate(rate=DECISION['discount'], n=N, seed=SEED, traps=True):
    rng = np.random.default_rng(seed)
    disc = (1 + rate) ** -(YEARS - 2026 + 0.5)                      # mid-year, base 2026
    vol = np.minimum(COMPANY['use_t_2026'] * (1 + rng.uniform(0.01, 0.03, n))[:, None] ** (YEARS - 2026), COMPANY['capacity_t'])
    # shared futures: buy price, energy, carbon, wages, overrun
    buy_idx = np.exp(np.cumsum(rng.normal(0.01, BUY['price_vol_yearly'] * 0.6, (n, len(YEARS))), 1))
    buy_price = BUY['price_2026_eur_t'] * buy_idx
    renewal = 1 + tri(rng, *BUY['renewal_rise'][:1], BUY['renewal_likely'], BUY['renewal_rise'][1], n)
    after = YEARS >= 2031
    buy_price = np.where(after, buy_price * renewal[:, None], buy_price)
    buy_price = np.where(YEARS == 2030, buy_price * (1 + (renewal[:, None] - 1) / 2), buy_price)   # half the year renewed
    spot = buy_price * 1.45                                         # months bought spot after the contract (purchase file 2026-02)
    buy_unit = buy_price + BUY['freight_2026_eur_t'] * 1.02 ** (YEARS - 2026)
    energy_idx = np.exp(np.cumsum(rng.normal(0.0, 0.07, (n, len(YEARS))), 1))
    eua = 80 * np.exp(np.cumsum(rng.normal(0.03, 0.06, (n, len(YEARS))), 1))
    wage_shock = rng.normal(0, 0.01, n)
    overrun = np.exp(rng.normal(np.log(1.16), 0.15, n)) - 1         # comparable plants: median ~ +16-18 %
    buy_npv = (vol * buy_unit * disc).sum(1)

    out = {}
    for k in SITE_ORDER:
        s = SITES[k]; t = TRAPS.get(k, {}) if traps else {}; c = COUNTRIES[s['country']]
        extra_capex = np.zeros(n); extra_opex = np.zeros(n); delay = np.zeros(n); truck_years = np.zeros(n)
        if t.get('kind') == 'wastewater':
            extra_capex += t['pretreat_capex_m'] * 1e6 * rng.uniform(0.9, 1.3, n); extra_opex += t['pretreat_opex_m'] * 1e6
            delay += rng.uniform(*t['delay_months'], n)
        if t.get('kind') == 'air':
            extra_capex += (rng.uniform(*t['offset_m'], n) + t['abatement_capex_m']) * 1e6; extra_opex += t['abatement_opex_m'] * 1e6
            delay += rng.uniform(*t['delay_months'], n)
        if k == 'PL1' and traps:
            extra_capex += (t['spur_km'] * rng.uniform(*t['spur_eur_m_per_km'], n) + t['land_m']) * 1e6
            truck_years = (14 + rng.uniform(0, 10, n) + rng.uniform(*t['delay_months'], n)) / 12   # trucking until the spur runs
        if k == 'DE3' and traps:
            extra_capex += rng.uniform(*t['reinforcement_m'], n) * 1e6; delay += rng.uniform(*t['delay_months'], n)
        permit = tri(rng, *TIMING['permit_months'], n) * (0.8 if k == 'DE1' else 1.0)   # the park's permitting service
        build = tri(rng, *TIMING['build_months'], n)
        start_month = 1 + permit + delay + build                         # months after 1 Feb 2027
        start_year = 2027 + (1 + start_month) / 12                       # decimal year
        land = 18e4 * s['land_eur_m2']
        capex = s['epc_m'] * 1e6 * (1 + overrun) + land + extra_capex
        grant = 0.0
        if s['country'] == 'DE' and 'bis' in s['incentive']:             # GRW = a cash grant (pre-tax relevant); CZ/PL incentives are tax reliefs
            share = float(s['incentive'].split('bis ')[1].split(' %')[0]) / 100
            grant = capex * share * (rng.random(n) < 0.6) * rng.uniform(0.4, 1.0, n)
        # operating share of each year
        op = np.clip(YEARS[None, :] + 1 - start_year[:, None], 0, 1)
        st = STAFFING.get(k, STAFFING['default'])
        premium = rng.uniform(0, st['premium'], n) if st['premium'] else np.zeros(n)
        wages = P['fte'] * s['wage_eur'] * 12 * (1 + premium[:, None]) * (1 + c['wage_growth'] + wage_shock[:, None]) ** (YEARS - 2026)
        # first operating year: output share while the plant is still hiring; the rest is bought at spot
        ramp = rng.uniform(*st['ramp'], n)
        first = (YEARS[None, :] == np.floor(start_year)[:, None] + 1)
        unit = (P['raw_t_per_t'] * P['raw_material_eur_t'] * 1.02 ** (YEARS - 2026)
                + (P['el_mwh_per_t'] * s['el'] + P['gas_mwh_per_t'] * s['gas']) * energy_idx
                + P['gas_mwh_per_t'] * P['co2_t_per_mwh_gas'] * eua
                + P['hazwaste_t_per_t'] * s['haz_eur_t'] * 1.03 ** (YEARS - 2026)
                + P['ww_m3_per_t'] * s['sewer_eur_m3'] * 1.03 ** (YEARS - 2026)
                + P['raw_t_per_t'] * s['inbound_eur_t'] + OUTBOUND[k])
        truck = np.clip(np.minimum(YEARS[None, :] + 1 - start_year[:, None], truck_years[:, None]), 0, 1) * vol * P['raw_t_per_t'] * TRAPS.get('PL1', {}).get('truck_extra_eur_t', 0) * (k == 'PL1')
        fixed = wages + 0.025 * capex[:, None] + extra_opex[:, None] + s.get('park_fee_m', 0) * 1e6
        operate = op * (vol * unit + fixed) + truck
        short = first * op * vol * (1 - ramp[:, None])                  # tonnes not produced while hiring
        operate = operate - short * unit + short * (spot + BUY['freight_2026_eur_t'])
        # until start: buy; after 30.6.2030 without a plant: spot
        not_op = 1 - op
        contract = np.clip(2030.5 - YEARS, 0, 1)[None, :]
        buy_part = not_op * vol * np.where(contract >= not_op, buy_unit, contract / np.maximum(not_op, 1e-9) * buy_unit + (1 - contract / np.maximum(not_op, 1e-9)) * (spot + BUY['freight_2026_eur_t']))
        # capex spread over the build: 40 % in the year after permits, 60 % in the start year (simple)
        cap_year = np.clip(np.floor(start_year) - 2027, 0, len(YEARS) - 1).astype(int)
        cap_flow = np.zeros((n, len(YEARS))); rows = np.arange(n)
        cap_flow[rows, np.maximum(cap_year - 1, 0)] += 0.4 * (capex - grant); cap_flow[rows, cap_year] += 0.6 * (capex - grant)
        resid = DECISION['residual_share'] * capex * disc[-1]
        site_npv = ((operate + buy_part + cap_flow) * disc).sum(1) - resid
        saving = (buy_npv - site_npv) / 1e6
        start_ok = start_year <= 2030.5
        out[k] = dict(median_saving=float(np.median(saving)), p05=float(np.quantile(saving, 0.05)), p95=float(np.quantile(saving, 0.95)),
                      p_beat=float((saving > 0).mean()), p_loss=float((saving < -DECISION['loss_limit_m']).mean()),
                      p_start=float(start_ok.mean()), start_median=float(np.median(start_year)), capex_median_m=float(np.median(capex) / 1e6),
                      capex_p90_m=float(np.quantile(capex, 0.9) / 1e6), trap_capex_median_m=float(np.median(extra_capex) / 1e6),
                      brochure_capex_m=float(s['epc_m'] + land / 1e6))
        r = out[k]; r['passes'] = bool(r['p_beat'] >= DECISION['beat_prob'] and r['p_loss'] <= DECISION['loss_prob']
                                        and r['p_start'] >= DECISION['start_prob'] and r['capex_median_m'] <= DECISION['capex_ceiling_m'])
    passing = [k for k in SITE_ORDER if out[k]['passes']]
    winner = max(passing, key=lambda k: out[k]['median_saving']) if passing else None
    return dict(rate=rate, sites=out, passing=passing, winner=winner, buy_npv_median_m=float(np.median(buy_npv) / 1e6))


if __name__ == '__main__':
    res = {f'{r:.2f}': simulate(r) for r in (0.06, 0.08, 0.10)}
    res['naive_0.08'] = simulate(0.08, traps=False)     # what a study that misses the three traps would find
    (ROOT / 'tools' / 'answer_key_reference.json').write_text(json.dumps(res, indent=2, ensure_ascii=False))
    base = res['0.08']
    print('buy NPV median (mil. EUR)', round(base['buy_npv_median_m'], 1), '| winner', base['winner'], '| passing', base['passing'])
    for k in SITE_ORDER:
        r = base['sites'][k]
        print(f"{k} saving med {r['median_saving']:7.1f} [{r['p05']:6.1f},{r['p95']:6.1f}] Pbeat {r['p_beat']:.2f} Ploss {r['p_loss']:.2f} "
              f"Pstart {r['p_start']:.2f} start {r['start_median']:.2f} capex {r['capex_median_m']:.0f} (brochure {r['brochure_capex_m']:.0f}, trap {r['trap_capex_median_m']:.1f}) {'PASS' if r['passes'] else ''}")
    for rate in ('0.06', '0.10'): print(rate, res[rate]['winner'], res[rate]['passing'])
    nv = res['naive_0.08']; print('NAIVE (no traps) winner', nv['winner'], nv['passing'])
    for k in SITE_ORDER:
        r = nv['sites'][k]; print(f"  naive {k} med {r['median_saving']:6.1f} Pbeat {r['p_beat']:.2f} Ploss {r['p_loss']:.2f} Pstart {r['p_start']:.2f}")
