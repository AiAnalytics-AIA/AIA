"""ChemVitro case · writes the client's data files into ../data/ from params.py with a fixed seed.

Run from anywhere:  ~/.venvs/aia-panel/bin/python ChemVitro/tools/generate.py
The files are byte-identical on every run (fixed seed, fixed workbook dates). The files are deliberately NOT clean:
checking them is part of every study. What was planted is in ANSWER-KEY.md.
"""
import csv, datetime as dt
from pathlib import Path
import numpy as np
import openpyxl
from openpyxl.styles import Font
from params import (SEED, COMPANY, BUY, PROCESS, COUNTRIES, SITES, SITE_ORDER, OUTBOUND, TRAPS, EXPERT_CRITERIA, EXPERTS,
                    SURVEY, LABOUR_POOL)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'; DATA.mkdir(exist_ok=True)
rng = np.random.default_rng(SEED)
FIXED = dt.datetime(2026, 11, 2, 9, 0, 0)


def book():
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    wb.properties.creator = 'ChemVitro a.s. (fiktivní)'; wb.properties.created = FIXED; wb.properties.modified = FIXED
    return wb


def sheet(wb, title, header, rows, note=None):
    ws = wb.create_sheet(title); ws.append(header)
    for c in ws[1]: c.font = Font(bold=True)
    for r in rows: ws.append(list(r))
    if note: ws.append([]); ws.append([note])
    return ws


def save(wb, name):
    path = DATA / name; wb.save(path)
    # openpyxl stamps the save time into docProps/core.xml: rewrite it so the file is byte-identical on every run
    import zipfile, shutil, tempfile
    tmp = Path(tempfile.mkstemp(suffix='.xlsx')[1])
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'docProps/core.xml':
                import re
                data = re.sub(rb'(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)', rb'\g<1>2026-11-02T09:00:00Z\g<2>', data)
            info = zipfile.ZipInfo(item.filename, date_time=(2026, 11, 2, 9, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)
    shutil.move(tmp, path)


def write_csv(name, header, rows):
    with open(DATA / name, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';', lineterminator='\n'); w.writerow(header); w.writerows(rows)


def czdec(x, d=2):
    return f'{x:.{d}f}'.replace('.', ',')


# ---------------------------------------------------------------- 1. comparable plants
def comparable_plants():
    rows = []
    countries = ['CZ'] * 9 + ['DE'] * 14 + ['PL'] * 9 + ['SK'] * 2 + ['AT'] * 2
    kinds = rng.choice(['chemický park', 'greenfield', 'brownfield'], size=36, p=[0.4, 0.4, 0.2])
    for i in range(36):
        c = countries[i]; kind = kinds[i]
        cap = float(rng.choice([18, 22, 25, 30, 35, 40, 45, 50, 60]))
        year = int(rng.integers(2012, 2026))
        base = 3.2 * cap ** 0.72 * (1.0 if c in ('CZ', 'PL', 'SK') else 1.12) * (1.02 ** (year - 2012))   # mil. EUR of that year
        overrun = float(np.exp(rng.normal(np.log(1.11 if kind == 'chemický park' else 1.17), 0.14))) - 1
        planned = int(rng.integers(18, 27)); actual = int(round(planned * (1 + max(-0.05, overrun * 0.9 + rng.normal(0, 0.06)))))
        pretreat = (kind != 'chemický park') and rng.random() < 0.38
        pre_cost = round(float(rng.uniform(6, 15)), 1) if pretreat else None
        spur = (kind == 'greenfield') and rng.random() < 0.45
        spur_km = round(float(rng.uniform(0.6, 4.5)), 1) if spur else None
        spur_cost = round(spur_km * float(rng.uniform(1.6, 2.8)), 1) if spur else None
        comp = (c in ('CZ', 'PL')) and rng.random() < 0.40
        comp_cost = round(float(rng.uniform(3, 11)), 1) if comp else None
        capex = base * (1 + overrun) + (pre_cost or 0) + (spur_cost or 0) + (comp_cost or 0)
        cur = 'EUR'
        if c == 'CZ' and rng.random() < 0.6: cur = 'CZK'; capex *= 24.5
        if c == 'PL' and rng.random() < 0.6: cur = 'PLN'; capex *= 4.3
        rows.append([f'P-{i + 1:02d}', c, kind, year, cap, round(capex, 1), cur, year, planned, actual, round(100 * overrun, 1),
                     'ano' if pretreat else 'ne', pre_cost, 'ano' if spur else 'ne', spur_km, spur_cost, 'ano' if comp else 'ne', comp_cost])
    # planted: P-23 capacity written in t/day, P-17 entered twice (second time with a rounded capex), P-31 price year missing
    rows[22][4] = round(rows[22][4] * 1000 / 330, 0); rows[22].append('kapacita převzata z výroční zprávy')
    dup = list(rows[16]); dup[5] = round(dup[5], 0); rows.insert(30, dup)
    rows[31][7] = None
    for r in rows:
        if len(r) < 19: r.append('')
    wb = book()
    sheet(wb, 'Závody', ['ID', 'Země', 'Typ lokality', 'Rok uvedení do provozu', 'Kapacita (kt/rok)', 'Investice celkem (mil.)', 'Měna',
                         'Cenová hladina (rok)', 'Plán výstavby (měsíce)', 'Skutečnost (měsíce)', 'Překročení rozpočtu EPC (%)',
                         'Předčištění odpadních vod', 'Předčištění (mil. EUR)', 'Vlečka postavena', 'Vlečka (km)', 'Vlečka (mil. EUR)',
                         'Kompenzační opatření (ovzduší)', 'Kompenzace (mil. EUR)', 'Poznámka'], rows,
          'Zdroj: databáze oborového sdružení (fiktivní), výběr závodů na estery a podobné meziprodukty 18–60 kt/rok. '
          'Investice celkem = skutečné náklady včetně infrastruktury mimo areál. Překročení = proti odhadu EPC při rozhodnutí.')
    save(wb, 'srovnatelne_zavody.xlsx')


# ---------------------------------------------------------------- 2. site sheet (from the site agencies' brochures)
def site_sheet():
    rows = []
    for k in SITE_ORDER:
        s = SITES[k]
        rows.append([k, s['name'], s['park'], COUNTRIES[s['country']]['name'], s['region'], s['plot_ha'], s['land_eur_m2'],
                     s['rail'], s['road'], 'ano', s['ww_body'], s['incentive'],
                     {'CZ1': 'ÚP: plochy výroby, schváleno', 'CZ2': 'ÚP: plochy výroby', 'CZ3': 'ÚP: plochy těžké výroby',
                      'DE1': 'B-Plan Industriegebiet (GI)', 'DE2': 'B-Plan GI', 'DE3': 'B-Plan GE/GI (Änderung läuft)',
                      'PL1': 'MPZP: tereny przemysłowe', 'PL2': 'MPZP: tereny przemysłowe P/U'}[k]])
    wb = book()
    sheet(wb, 'Lokality', ['Kód', 'Obec', 'Areál', 'Země', 'Region', 'Plocha k dispozici (ha)', 'Cena pozemku (EUR/m²)',
                          'Železnice', 'Silnice', 'Napojení na kanalizaci', 'Odpadní vody převezme', 'Pobídky (podle agentury)',
                          'Územní plán'], rows,
          'Souhrn ChemVitro z nabídek lokalitních agentur (nabidky_lokalit.pdf), říjen 2026. Potřeba: 18 ha.')
    save(wb, 'lokality_parametry.xlsx')


# ---------------------------------------------------------------- 3. labour market
def labour():
    rows = []
    pool_share = {k: None for k in SITE_ORDER}
    info = {'CZ1': (5.9, 6_200, 58), 'CZ2': (3.8, 2_100, 64), 'CZ3': (5.1, 8_900, 71), 'DE1': (6.8, 14_500, 49),
            'DE2': (6.1, 3_300, 66), 'DE3': (2.4, 2_600, 118), 'PL1': (4.6, 4_800, 61), 'PL2': (3.9, 9_700, 55)}
    for k in SITE_ORDER:
        s = SITES[k]; c = COUNTRIES[s['country']]
        unemp, chem, fill = info[k]
        gross_local = s['wage_eur'] / 1.34 * c['fx_eur']         # employer cost -> gross wage in local currency
        rows.append([k, s['region'], c['cur'], round(gross_local, -1 if c['cur'] != 'EUR' else 0), czdec(100 * c['wage_growth'], 1),
                     unemp, chem, fill, 380 if k == 'CZ3' else (120 if k == 'PL2' else 0),
                     'Kamenec Steel (fiktivní) nabírá 380 lidí do 2028' if k == 'CZ3' else ('Bory Automotive (fiktivní) 120 lidí' if k == 'PL2' else '')])
    wb = book()
    sheet(wb, 'Regiony', ['Kód lokality', 'Region', 'Měna', 'Hrubá měsíční mzda operátora chemické výroby (medián, místní měna)',
                         'Růst mezd ročně (%, průměr 3 let)', 'Nezaměstnanost (%)', 'Zaměstnanci chemie v regionu',
                         'Doba obsazení pozice operátora (dny)', 'Velké nábory v okolí (lidé)', 'Poznámka'], rows,
          'Zdroj: personální agentura (fiktivní) z veřejných statistik a vlastních dat, září 2026. Mzda je hrubá, bez odvodů zaměstnavatele.')
    sheet(wb, 'Země', ['Země', 'Zaměstnanci chemického průmyslu (relevantní regiony)'],
          [[COUNTRIES[c]['name'], n] for c, n in LABOUR_POOL.items()])
    save(wb, 'trh_prace_regiony.xlsx')


# ---------------------------------------------------------------- 4. energy, water and fees (offers)
def energy():
    rows = []
    for k in SITE_ORDER:
        s = SITES[k]
        rows.append([k, czdec(s['el'], 0), czdec(s['gas'], 0), czdec(s['sewer_eur_m3']), czdec({'CZ': 2.4, 'DE': 2.9, 'PL': 1.9}[s['country']]),
                     'fix 3 roky, pak trh' if s['country'] != 'DE' or k == 'DE1' else 'fix 2 roky, pak trh',
                     'park' if k == 'DE1' else 'dodavatel'])
    write_csv('energie_a_poplatky.csv', ['kod_lokality', 'elektrina_eur_mwh', 'plyn_eur_mwh', 'stocne_eur_m3', 'voda_eur_m3',
                                         'cenova_fixace', 'nabidku_dal'], rows)


# ---------------------------------------------------------------- 5. hazardous waste quotes
def waste():
    rows = []
    for k in SITE_ORDER:
        s = SITES[k]
        dist = {'CZ1': 85, 'CZ2': 140, 'CZ3': 60, 'DE1': 25, 'DE2': 70, 'DE3': 110, 'PL1': 95, 'PL2': 40}[k]
        rows.append([k, 'kal z neutralizace + destilační zbytek', czdec(s['haz_eur_t'], 0), dist, 'spalovna',
                     'cena platí do 2028, pak podle ceníku' if k != 'DE1' else 'Rahmenvertrag Chemiepark 5 Jahre'])
    # planted: a second, cheaper quote for PL2 that covers only the non-hazardous fraction
    rows.append(['PL2', 'kal z neutralizace (ostatní odpad)', '95', 40, 'skládka', 'jen ostatní odpad, ne nebezpečný'])
    write_csv('odpady_nabidky.csv', ['kod_lokality', 'odpad', 'cena_eur_t', 'vzdalenost_km', 'zarizeni', 'poznamka'], rows)


# ---------------------------------------------------------------- 5b. freight quotes
def freight():
    # outbound split Brno / Pardubice, so that 0,62 Brno + 0,38 Pardubice = OUTBOUND
    ratio = {'CZ1': 0.75, 'CZ2': 1.25, 'CZ3': 1.30, 'DE1': 0.93, 'DE2': 0.90, 'DE3': 0.95, 'PL1': 1.15, 'PL2': 1.10}   # Pardubice / Brno
    mode = {'CZ1': 'vlečka v zóně', 'CZ2': 'železnice na překladiště Lipová, dál cisterny', 'CZ3': 'vlečka v zóně',
            'DE1': 'Werksbahn', 'DE2': 'železnice do GVZ Lindenau, dál cisterny', 'DE3': 'cisterny (trať bez vlečky)',
            'PL1': 'železnice; předpoklad dopravce: vlečka k areálu', 'PL2': 'vlečka v zóně'}
    rows = []
    for k in SITE_ORDER:
        o = OUTBOUND[k]; r = ratio[k]; brno = o / (0.62 + 0.38 * r)
        rows.append([k, czdec(SITES[k]['inbound_eur_t'], 0), mode[k], czdec(brno, 0), czdec(brno * r, 0), 'cisterny', 'Speditrans (fiktivní), 10/2026'])
    write_csv('doprava_nabidky.csv', ['kod_lokality', 'suroviny_dovoz_eur_t', 'suroviny_zpusob', 'produkt_do_brna_eur_t',
                                      'produkt_do_pardubic_eur_t', 'produkt_zpusob', 'nabidku_dal'], rows)


# ---------------------------------------------------------------- 6. air-quality stations
def air():
    rows = []
    for k in SITE_ORDER:
        a = SITES[k]['air']
        for y in range(2021, 2026):
            drift = 1 + 0.03 * (2023 - y)             # slow improvement
            noise = lambda v: max(0.1, v * drift * float(rng.normal(1, 0.05)))
            bap = SITES[k].get('air_2021_bap') if (k == 'CZ3' and y == 2021) else noise(a['bap'])
            rows.append([k, f'stanice {SITES[k]["name"]}', y, czdec(noise(a['pm10']), 1), czdec(noise(a['pm25']), 1),
                         czdec(noise(a['no2']), 1), czdec(bap, 2)])
    write_csv('ovzdusi_stanice.csv', ['kod_lokality', 'stanice', 'rok', 'pm10_ug_m3', 'pm25_ug_m3', 'no2_ug_m3', 'bap_ng_m3'], rows)


# ---------------------------------------------------------------- 7. process design
def process():
    p = PROCESS; wb = book()
    sheet(wb, 'Návrh procesu', ['Veličina', 'Hodnota', 'Jednotka', 'Poznámka'], [
        ['Kapacita', COMPANY['capacity_t'], 't VTX-40 ročně', 'návrh na 40 000 t; spotřeba ChemVitro 2026: 34 000 t'],
        ['Suroviny', p['raw_t_per_t'], 't na t produktu', 'železnice nebo cisterny'],
        ['Cena surovin', p['raw_material_eur_t'], 'EUR na t surovin', 'stejná pro všechny lokality, franko závod'],
        ['Elektřina', p['el_mwh_per_t'], 'MWh na t', ''],
        ['Zemní plyn (pára)', p['gas_mwh_per_t'], 'MWh na t', 'parní kotel 24 MW příkonu'],
        ['Emisní faktor plynu', p['co2_t_per_mwh_gas'], 't CO2 na MWh', ''],
        ['Odpadní voda', p['ww_m3_per_t'], 'm³ na t', 'po neutralizaci v areálu'],
        ['CHSK v odpadní vodě', p['ww_cod_mg_l'], 'mg/l', 'po neutralizaci'],
        ['Sírany v odpadní vodě', p['ww_sulfate_mg_l'], 'mg/l', 'po neutralizaci'],
        ['pH před neutralizací', '2–3', '', 'neutralizace je v rozsahu EPC'],
        ['VOC', p['voc_kg_per_t'], 'kg na t', 'po oxidaci odpadních plynů'],
        ['NOx', p['nox_kg_per_t'], 'kg na t', ''],
        ['Nebezpečný odpad', p['hazwaste_t_per_t'], 't na t', 'kal z neutralizace a destilační zbytek, kat. N'],
        ['Zaměstnanci', p['fte'], 'FTE', 'z toho 70 ve směnách'],
        ['Provozní dny', p['operating_days'], 'dny ročně', ''],
    ], 'Zdroj: koncepční návrh procesu, oddělení technologie ChemVitro, září 2026.')
    save(wb, 'proces_emise_odpady.xlsx')


# ---------------------------------------------------------------- 8. purchase history (buy baseline)
def purchases():
    rows = []; price = 1_390.0
    for y in range(2023, 2027):
        for m in range(1, 13):
            if (y, m) > (2026, 9): break
            price *= float(np.exp(rng.normal(0.003, 0.025)))
            vol = COMPANY['use_t_2026'] / 12 * (1.02 ** (y - 2026)) * float(rng.normal(1, 0.07))
            rows.append([f'{y}-{m:02d}', round(vol), round(price), BUY['freight_2026_eur_t'] + int(rng.integers(-6, 7)), 'EUR', 'Hanshin Fine Chemicals'])
    # planted: 2025-07 volume in kg, 2024-03 price in USD (labelled), 2026-02 an emergency spot purchase from another supplier
    i = [r[0] for r in rows].index('2025-07'); rows[i][1] = rows[i][1] * 1000
    i = [r[0] for r in rows].index('2024-03'); rows[i][2] = round(rows[i][2] * 1.08); rows[i][4] = 'USD'
    i = [r[0] for r in rows].index('2026-02'); rows.insert(i + 1, ['2026-02', 640, 2_180, 140, 'EUR', 'spot: EuroChem Trade (fiktivní)'])
    wb = book()
    sheet(wb, 'Nákup', ['Měsíc', 'Množství (t)', 'Cena (za t)', 'Doprava (EUR/t)', 'Měna ceny', 'Dodavatel'], rows,
          'Zdroj: nákupní systém ChemVitro. Ceny bez DPH, franko sklad Brno/Pardubice.')
    save(wb, 'nakup_vtx40_2023-2026.xlsx')


# ---------------------------------------------------------------- 9. expert ratings
def experts():
    # true site profile per criterion (1-10, 10 = best for ChemVitro)
    true = {'CZ1': [7, 4, 7, 8, 5, 7], 'CZ2': [8, 6, 5, 6, 6, 7], 'CZ3': [7, 7, 6, 8, 7, 8], 'DE1': [5, 9, 7, 9, 8, 6],
            'DE2': [6, 6, 6, 6, 6, 7], 'DE3': [4, 7, 3, 5, 6, 3], 'PL1': [8, 7, 7, 6, 6, 8], 'PL2': [9, 5, 7, 8, 5, 9]}
    rows = []
    for code, role in EXPERTS:
        lean = float(rng.normal(0, 0.6))
        for k in SITE_ORDER:
            for j, crit in enumerate(EXPERT_CRITERIA):
                v = true[k][j] + lean + float(rng.normal(0, 1.0))
                if code == 'KON' and k in ('PL2', 'CZ2'): v += 2.5            # the agency brokered these two offers
                if code == 'EHS' and j == 1: v = true[k][j] + float(rng.normal(0, 0.5)) - (2 if k in ('CZ1', 'PL2') else 0)
                v = int(np.clip(round(v), 1, 10))
                if code == 'TI2': v = 11 - v                                    # rated with the scale reversed
                rows.append([code, role, k, crit, v, 'hodnoceno 1 = nejlepší' if (code == 'TI2' and k == 'CZ1' and j == 0) else ''])
    # planted: two cells missing
    for idx in (5 * 48 + 2 * 6 + 3, 9 * 48 + 7 * 6 + 5): rows[idx][4] = ''
    write_csv('hodnoceni_lokalit.csv', ['hodnotitel', 'role', 'lokalita', 'kriterium', 'skore_1_10', 'poznamka'], rows)


# ---------------------------------------------------------------- 10. worker survey
def survey():
    base = {'CZ1': 5.2, 'CZ2': 5.6, 'CZ3': 5.8, 'DE1': 6.4, 'DE2': 4.6, 'DE3': 6.0, 'PL1': 5.4, 'PL2': 5.0}
    kraje = {'CZ': ['Ústecký', 'Olomoucký', 'Moravskoslezský', 'Jihomoravský', 'Pardubický', 'Středočeský'],
             'DE': ['Sachsen-Anhalt', 'Sachsen', 'Bayern', 'Thüringen'], 'PL': ['Opolskie', 'Śląskie', 'Dolnośląskie', 'Małopolskie']}
    rows = []; rid = 0
    for c, n in SURVEY['by_country'].items():
        for _ in range(n):
            rid += 1
            age = int(rng.choice([22, 28, 35, 44, 55])) + int(rng.integers(-3, 4))
            prof = str(rng.choice(['operátor', 'technik', 'laborant', 'údržba'], p=[0.5, 0.2, 0.15, 0.15]))
            mobile = (age < 33 and prof in ('technik', 'údržba') and rng.random() < 0.7) or rng.random() < 0.12
            reloc = int(np.clip(round(rng.normal(4.2 if mobile else 2.1, 0.7)), 1, 5))
            scores = []
            for k in SITE_ORDER:
                v = base[k] + float(rng.normal(0, 1.4))
                if SITES[k]['country'] == c: v += SURVEY['home_bias']
                if mobile and k in ('DE1', 'DE3'): v += 1.8                          # mobile segment follows the wages
                if mobile and SITES[k]['country'] == c: v -= 1.0
                scores.append(int(np.clip(round(v), 1, 10)))
            wage_eur = {'CZ': 1_750, 'DE': 3_600, 'PL': 1_600}[c] * float(rng.normal(1, 0.12)) * (1.15 if mobile else 1)
            wage_local = round(wage_eur * COUNTRIES[c]['fx_eur'], -2 if c != 'DE' else -1)
            km = int(np.clip(rng.normal(55 if mobile else 30, 15), 5, 150))
            rows.append([f'W{rid:03d}', COUNTRIES[c]['name'], str(rng.choice(kraje[c])), age, prof, int(rng.integers(1, 30)), reloc, km,
                         int(wage_local), COUNTRIES[c]['cur']] + scores)
    # planted: straight-liners, duplicated respondents
    for i in rng.choice(len(rows), SURVEY['straightliners'], replace=False):
        rows[i][10:18] = [int(rng.choice([1, 5, 10]))] * 8
    dups = [list(rows[i]) for i in rng.choice(len(rows), SURVEY['duplicates'], replace=False)]
    for d in dups: rows.insert(int(rng.integers(0, len(rows))), d)
    write_csv('pruzkum_pracovniku_2026.csv',
              ['id_respondenta', 'zeme', 'region', 'vek', 'profese', 'praxe_let', 'ochota_prestehovat_1_5', 'dojizdka_max_km',
               'ocekavana_hruba_mzda', 'mena'] + [f'{k}_atraktivita' for k in SITE_ORDER], rows)
    (DATA / 'pruzkum_pracovniku_2026_dotaznik.md').write_text(QUESTIONNAIRE, encoding='utf-8')


QUESTIONNAIRE = """# Průzkum pracovníků chemického průmyslu, říjen 2026: dotazník a kódy

Fiktivní průzkum pro případovou studii AIA. 300 pracovníků chemického průmyslu v Česku, Německu a Polsku, online panel personální agentury ChemStaff (fiktivní, Brno), 5.–23. 10. 2026. Odpovídali v češtině, němčině nebo polštině.
Soubor: `pruzkum_pracovniku_2026.csv` (oddělovač `;`, UTF-8). Prázdná buňka = otázka bez odpovědi, nikdy ne 0.

## Profil

| Sloupec | Význam | Hodnoty |
|---|---|---|
| `id_respondenta` | pseudonymní kód | W001–W300 |
| `zeme` | země bydliště | Česko, Německo, Polsko |
| `region` | kraj / Land / województwo | |
| `vek` | věk v letech | |
| `profese` | současná práce | operátor, technik, laborant, údržba |
| `praxe_let` | roky praxe v chemii | |

## Otázka 1: lákavost práce v novém závodě

> Firma staví nový chemický závod. Jak lákavé by pro vás bylo v něm pracovat, kdyby stál v této lokalitě?
> Ohodnoťte na škále 1–10, kde **1 = vůbec nelákavé** a **10 = velmi lákavé**.

Respondent viděl název obce, region a vzdálenost od svého bydliště. Pořadí lokalit se střídalo náhodně.

| Sloupec | Lokalita |
|---|---|
| `CZ1_atraktivita` | Vrbice (Ústecký kraj) |
| `CZ2_atraktivita` | Lipová (Olomoucký kraj) |
| `CZ3_atraktivita` | Kamenec (Moravskoslezský kraj) |
| `DE1_atraktivita` | Wendelstedt (Sachsen-Anhalt) |
| `DE2_atraktivita` | Lindenau (Sachsen) |
| `DE3_atraktivita` | Eschfeld (Bayern) |
| `PL1_atraktivita` | Odrzyca (Opolskie) |
| `PL2_atraktivita` | Bory (Śląskie) |

## Otázka 2: přestěhování

> Přestěhoval(a) byste se kvůli takové práci?

`ochota_prestehovat_1_5`: **1 = určitě ne**, 2 = spíše ne, 3 = nevím, 4 = spíše ano, **5 = určitě ano**.

## Otázka 3: dojíždění

> Kolik kilometrů jste ochoten/ochotna denně dojíždět do práce (jedním směrem)?

`dojizdka_max_km`: celé km.

## Otázka 4: mzda

> Jakou hrubou měsíční mzdu byste za takovou práci očekával(a)?

`ocekavana_hruba_mzda` v měně ze sloupce `mena` (CZK, EUR, PLN).
"""

if __name__ == '__main__':
    comparable_plants(); site_sheet(); labour(); energy(); waste(); freight(); air(); process(); purchases(); experts(); survey()
    for f in sorted(DATA.iterdir()): print(f.name, f.stat().st_size)
