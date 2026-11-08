"""Build the result boards of the MVP r2 (session C): M3 Model, M4 Rozhodnutí, M4b Finance, M4d Provoz and the
new M4g Harmonogram.

Every ChemVitro number here is copied from the exemplar report (`../exemplar/ChemVitro_2_model-lokality_nigel.txt`,
5 Nov 2026): tables T1-T6 and chapters 3.3, 5-10 and appendix B. Velis sections are kept as the boards had them; the
script marks each section with the case it belongs to and never mixes the two.

Run from this folder: `python3 tools/results_build.py`. Idempotent: generated sections carry `data-gen="r2"` and are
rebuilt; sections without it are kept. `python3 tools/results_build.py check` compares the ChemVitro data against the
exemplar's text and exits non-zero on a number the text does not contain.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXEMPLAR = ROOT / "exemplar" / "ChemVitro_2_model-lokality_nigel.txt"

# ---------------------------------------------------------------- ChemVitro data (exemplar, 5 Nov 2026)

SITES = ["Vrbice", "Lipová", "Kamenec", "Wendelstedt", "Lindenau", "Eschfeld", "Odrzyca", "Bory"]
COUNTRY = ["CZ", "CZ", "CZ", "DE", "DE", "DE", "PL", "PL"]
LEAD = ["Lipová", "Kamenec", "Odrzyca"]

# T1-T3: median, p5, p95, P(beats buying), P(loss > 20), P(production by 1. 7. 2030), investment (base)
RULE = {
    8: [
        (110.8, -40.7, 331.5, 0.88, 0.08, 0.21, 160.6),
        (126.0, -30.2, 349.4, 0.91, 0.06, 0.76, 158.6),
        (132.4, -23.5, 356.9, 0.92, 0.05, 0.76, 152.3),
        (82.3, -74.7, 308.1, 0.80, 0.15, 0.94, 171.8),
        (86.5, -68.8, 311.7, 0.81, 0.14, 0.77, 170.8),
        (61.2, -94.4, 285.7, 0.73, 0.21, 0.67, 175.5),
        (134.7, -23.8, 359.1, 0.92, 0.05, 0.75, 148.9),
        (123.2, -30.9, 344.4, 0.91, 0.06, 0.19, 143.9),
    ],
    6: [
        (160.0, -24.4, 433.2, 0.92, 0.06, 0.21, 160.6),
        (177.9, -11.4, 455.9, 0.94, 0.04, 0.76, 158.6),
        (184.5, -4.3, 463.4, 0.94, 0.04, 0.76, 152.3),
        (126.2, -62.8, 404.9, 0.86, 0.105, 0.94, 171.8),  # printed 0,10, fails: 0,105 (ch. 5.2)
        (130.9, -57.9, 407.9, 0.87, 0.10, 0.77, 170.8),
        (102.2, -85.8, 378.9, 0.81, 0.15, 0.67, 175.5),
        (187.0, -4.8, 464.9, 0.95, 0.04, 0.75, 148.9),
        (172.3, -14.9, 445.7, 0.94, 0.05, 0.19, 143.9),
    ],
    10: [
        (73.3, -53.2, 253.2, 0.82, 0.12, 0.21, 160.6),
        (85.6, -44.8, 269.2, 0.86, 0.09, 0.76, 158.6),
        (91.6, -38.6, 275.7, 0.87, 0.08, 0.76, 152.3),
        (48.3, -83.2, 232.8, 0.71, 0.21, 0.94, 171.8),
        (52.6, -77.5, 237.1, 0.73, 0.19, 0.77, 170.8),
        (29.5, -100.1, 212.7, 0.63, 0.28, 0.67, 175.5),
        (93.9, -37.7, 277.9, 0.88, 0.08, 0.75, 148.9),
        (85.5, -42.1, 265.3, 0.86, 0.09, 0.19, 143.9),
    ],
}
TH = {"beat": 0.75, "loss": 0.10, "time": 0.80, "inv": 175.0}

# 5.3 decision boundary: compensation chance -> rule's pick, P(in time) and median of Lipová / Kamenec / Odrzyca
BOUNDARY = [
    ("0 %", "Odrzyca", (0.942, 0.942, 0.942), (130.7, 137.1, 141.3)),
    ("5 %", "Odrzyca", (0.896, 0.894, 0.893), (129.9, 135.9, 139.6)),
    ("10 %", "Odrzyca", (0.852, 0.851, 0.844), (128.7, 134.9, 137.8)),
    ("14 %", "Odrzyca", (0.817, 0.813, 0.808), (127.6, 133.7, 136.6)),
    ("15 %", "Kamenec", (0.807, 0.804, 0.797), (127.3, 133.6, 136.3)),
    ("16 %", "nic", (0.797, 0.795, 0.787), (127.1, 133.3, 136.0)),
    ("20 % (model)", "nic", (0.760, 0.759, 0.748), (126.0, 132.4, 134.7)),
    ("30 %", "nic", (0.669, 0.668, 0.653), (123.5, 129.5, 131.3)),
]

# 6.1 delay of the decision (months) -> P(production by 1. 7. 2030) per site, compensation chance 20 %
DELAY = [
    (0, (0.212, 0.760, 0.759, 0.942, 0.772, 0.667, 0.748, 0.190)),
    (2, (0.182, 0.726, 0.726, 0.908, 0.602, 0.480, 0.720, 0.183)),
    (4, (0.147, 0.583, 0.586, 0.731, 0.403, 0.298, 0.580, 0.146)),
    (6, (0.115, 0.453, 0.456, 0.568, 0.210, 0.141, 0.452, 0.114)),
]
# 6.1, second table: no compensation (Lipová, Kamenec, Odrzyca)
DELAY_NOCOMP = [(0, 0.942, "Odrzyca"), (2, 0.908, "Odrzyca"), (4, 0.731, "nic"), (6, 0.568, "nic")]
# 6.2 hiring delay (months) -> P(in time) Lipová / Kamenec / Odrzyca; 2 months equals the 2-month delay
HIRING = {0: (0.760, 0.759, 0.748), 1: (0.745, 0.744, 0.737), 2: (0.726, 0.726, 0.720), 3: (0.672, 0.671, 0.666)}
HIRING_WENDELSTEDT_3 = 0.840
# total months of delay the report computed (decision delay + hiring), P(in time) Lipová / Kamenec / Odrzyca
TOTAL_DELAY = {0: HIRING[0], 1: HIRING[1], 2: HIRING[2], 3: HIRING[3], 4: (0.583, 0.586, 0.580), 6: (0.453, 0.456, 0.452)}

# ch. 7 tornado, Odrzyca, base case 170,7
TORNADO_BASE = 170.7
TORNADO = [
    # lever, range tested, low result, high result (Odrzyca) or None, swing (Odrzyca or across sites), grade
    ("Cena Hanshinu v roce 2026", "1 470 – 1 868 EUR/t", 84.8, 237.5, (152.7, 152.7), "z dat klienta"),
    ("Přirážka při prodloužení", "12 – 22 %", None, None, (57.7, 57.7), "z dat klienta"),
    ("Překročení rozpočtu", "−6 až 31 % (36 závodů)", None, None, (34.2, 44.5), "z dat klienta"),
    ("Dlouhodobý vývoj cen energie", "podle cenových cest", None, None, (23.1, 25.8), "prozatímní"),
    ("Údržba a pojištění", "2 – 4 % investice ročně", None, None, (17.8, 24.4), "úsudek"),
    ("Přirážka spotové ceny", "20 – 60 %", None, None, (16.9, 31.2), "úsudek"),
    ("Skladba mezd", "podle regionu", None, None, (10.1, 23.5), "úsudek"),
]

# 7.1 break-even values, base case
BREAKEVEN = [
    ("Cena Hanshinu 2026, při které se vlastní výroba a nákup vyrovnají", "EUR/t", ["1 308", "1 277", "1 261", "1 434", "1 413", "1 450", "1 249", "1 263"]),
    ("Přirážka při prodloužení, při které se vyrovnají", "%", ["−6,3", "−10,7", "−11,7", "−0,3", "−1,3", "1,2", "−12,6", "−8,2"]),
    ("Překročení rozpočtu, při kterém investice dosáhne 175 mil. EUR", "%", ["28,2", "30,2", "35,0", "19,3", "20,1", "16,7", "38,9", "43,6"]),
]

# 7.2 terms after 2035: median saving per site, the rule's pick
POST2035 = [
    ("0 % (zpět na cenu vzorce)", (58.2, 73.2, 79.1, 29.2, 33.7, 8.7, 81.7, 70.7), "nic"),
    ("jako při prvním prodloužení (základ)", (110.8, 126.0, 132.4, 82.3, 86.5, 61.2, 134.7, 123.2), "nic"),
    ("30 %", (151.7, 166.7, 173.1, 122.7, 127.0, 102.2, 175.3, 163.8), "Wendelstedt"),
]

# 7.3 correlation settings: median range per leading site
CORR = [("Lipová", "124,6 – 126,3"), ("Kamenec", "131,3 – 132,7"), ("Odrzyca", "134,2 – 135,3"), ("Wendelstedt", "81,9 – 82,4")]

# 8.1 value for the rule
VOI_RULE = [
    ("Zda úřad uloží kompenzační opatření v Odrzyci", 122.5, "bez kompenzace (79,4 % budoucností) Odrzycu, průměrná úspora 154,2; s kompenzací nic"),
    ("… v Kamenci", 120.7, "bez kompenzace (79,9 %) Kamenec, 151,1; s kompenzací nic"),
    ("… v Lipové", 115.2, "bez kompenzace (80,0 %) Lipovou, 144,1; s kompenzací nic"),
    ("… ve všech třech", 152.1, "Odrzycu, není-li tam kompenzace; jinak Kamenec, pak Lipovou; nic jen v 0,8 % budoucností"),
]
# 8.2 EVPPI, mil. EUR
EVPPI = [("Kompenzace v Odrzyci", 4.9), ("Kompenzace v Borech", 3.1), ("Kompenzace v Kamenci", 2.2), ("Každý další vstup", 0.7)]
EVPPI_ALL = 14.2
MEAN_BEST = ("Odrzyca", 147.6)

# 8.3 + ch. 13 enquiry table
ENQUIRY = [
    ("Kompenzace v Odrzyci", "písemné stanovisko vojvodského úřadu v Opolí, zda novému zdroji uloží kompenzační opatření", "do dvou měsíců od 1. 2. 2027, nebo souběžně s podmíněným rozhodnutím", "v podkladech není", "vedoucí ochrany životního prostředí a bezpečnosti · dotaz do 20. 11. 2026"),
    ("Kompenzace v Kamenci", "písemné stanovisko Krajského úřadu Moravskoslezského kraje", "totéž", "v podkladech není", "táž osoba"),
    ("Kompenzace v Lipové", "písemné stanovisko Krajského úřadu Olomouckého kraje", "totéž", "v podkladech není", "táž osoba"),
    ("Cena Hanshinu v roce 2026", "vysvětlení, proč cena překročila smluvní strop ±10 % ročně a z jakého základu se počítá cena roku 2029", "do 15. 1. 2027", "v podkladech není", "vedoucí nákupu"),
]

# T4 finance (base case): pre-tax 6/8/10, post-tax 6/8/10, median post-tax 8 %, IRR, payback, investment, start (base)
T4 = [
    ("Vrbice", (189.2, 134.5, 92.7), (142.0, 96.6, 61.9), 87.5, "18,2 %", 2035, 160.6, "2030,92"),
    ("Lipová", (219.3, 159.9, 113.8), (165.8, 116.3, 78.0), 99.9, "19,2 %", 2034, 158.6, "2029,92"),
    ("Kamenec", (225.6, 165.9, 119.6), (170.8, 121.3, 82.9), 107.3, "19,9 %", 2034, 152.3, "2029,92"),
    ("Wendelstedt", (149.8, 99.8, 61.2), (129.4, 84.3, 49.5), 72.1, "14,8 %", 2035, 171.8, "2029,92"),
    ("Lindenau", (156.0, 105.7, 67.0), (138.7, 92.4, 56.7), 80.0, "15,5 %", 2035, 170.8, "2030,17"),
    ("Eschfeld", (139.4, 91.2, 54.2), (111.9, 69.3, 36.7), 45.9, "14,4 %", 2036, 175.5, "2030,25"),
    ("Odrzyca", (230.6, 170.7, 124.2), (166.5, 118.6, 81.4), 107.2, "20,5 %", 2034, 148.9, "2029,92"),
    ("Bory", (200.5, 145.8, 103.9), (143.4, 99.7, 66.4), 96.0, "20,1 %", 2035, 143.9, "2031,17"),
]
BUY_NPV = (1067.9, 911.6, 787.2)  # keep buying, NPV of cost 2027-2044 at 6 / 8 / 10 %

# T5 investment by item: EPC×1,17, land, compensation, pre-treatment, bridge, spur, one-off, total, P(≤175), p10/p50/p90
T5 = [
    ("Vrbice", (149.8, 4.3, 6.5, 0.0, 0.0, 0.0, 0.0), 160.6, 0.79, "128,0 / 159,9 / 181,1"),
    ("Lipová", (145.1, 3.4, 0.0, 10.0, 0.0, 0.0, 0.1), 158.6, 0.82, "129,6 / 160,3 / 181,9"),
    ("Kamenec", (147.4, 4.9, 0.0, 0.0, 0.0, 0.0, 0.0), 152.3, 0.90, "121,6 / 153,9 / 175,9"),
    ("Wendelstedt", (165.0, 6.8, 0.0, 0.0, 0.0, 0.0, 0.0), 171.8, 0.56, "136,6 / 171,0 / 193,2"),
    ("Lindenau", (155.6, 5.2, 0.0, 10.0, 0.0, 0.0, 0.0), 170.8, 0.57, "137,7 / 170,9 / 190,9"),
    ("Eschfeld", (161.5, 9.9, 0.0, 0.0, 4.1, 0.0, 0.0), 175.5, 0.50, "141,0 / 175,2 / 196,3"),
    ("Odrzyca", (139.2, 2.9, 0.0, 0.0, 0.0, 6.8, 0.0), 148.9, 0.92, "120,3 / 150,7 / 170,5"),
    ("Bory", (136.9, 2.5, 4.5, 0.0, 0.0, 0.0, 0.0), 143.9, 0.92, "114,8 / 144,2 / 163,4"),
]
T5_COLS = ["EPC × (1 + 17 %)", "Pozemek 18 ha", "Kompenzace", "Předčištění", "Most", "Vlečka", "Jednorázové"]

# ch. 9 incentives
INCENTIVES = [
    ("Česko (Vrbice, Lipová, Kamenec)", "investiční pobídka až 20–25 %", "daňová úleva", "jen při dostatečném zisku; mění NPV po zdanění, ne před ním"),
    ("Polsko: Odrzyca", "osvobození od daně z příjmu až 35 %", "daňová úleva", "totéž"),
    ("Polsko: Bory", "osvobození od daně z příjmu až 50 %", "daňová úleva", "totéž"),
    ("Německo: Wendelstedt", "regionální podpora GRW až 15 %", "hotovostní dotace", "snížila by investici; schvaluje úřad"),
    ("Německo: Lindenau", "GRW až 20 %", "hotovostní dotace", "totéž"),
    ("Německo: Eschfeld", "žádná", "—", "—"),
]

# T6 operating cost per tonne in 2032, EUR/t (base case): CO₂, doprava, energie, lidé, odpad, suroviny, voda, údržba a park, celkem
T6_COLS = ["CO₂", "doprava", "energie", "lidé", "odpad", "suroviny", "voda", "údržba a park"]
T6 = [
    ("Vrbice", (56, 38, 179, 121, 17, 760, 26, 113), 1311),
    ("Lipová", (56, 20, 179, 116, 20, 760, 25, 124), 1300),
    ("Kamenec", (56, 24, 179, 124, 16, 760, 26, 111), 1295),
    ("Wendelstedt", (56, 58, 182, 203, 13, 760, 25, 157), 1455),
    ("Lindenau", (56, 53, 190, 195, 15, 760, 32, 132), 1434),
    ("Eschfeld", (56, 55, 190, 232, 14, 760, 34, 122), 1463),
    ("Odrzyca", (56, 37, 192, 102, 18, 760, 21, 105), 1292),
    ("Bory", (56, 33, 192, 109, 17, 760, 20, 103), 1290),
]
BOUGHT_TONNE_2032 = 2340


# T6 doprava column: product transport to Brno (62 %) and Pardubice (38 %), EUR/t, 2032 base case
TRANSPORT = [(site, vals[1]) for site, vals, _ in T6]
TRANSPORT_ASIA = 96  # EUR/t, keep-buying baseline, T9 (45-month average 96,4)
# T9 logistics inputs: (input, unit, low, likely, high, source, grade, who, state)
LOGISTICS_INPUTS = [
    ("Odrzyca: délka vlečky", "km", "3,40", "3,40", "3,40", "Vyjádření k dopravě s. 7", "z dat klienta", "vedoucí logistiky", "ověřeno"),
    ("Odrzyca: vlečka, cena za km", "mil. EUR/km", "1,90", "2,00", "2,80", "Srovnatelné závody: 4 vlečky 1,94–2,76 mil. EUR/km", "odhad", "vedoucí logistiky", "ověřeno"),
    ("Odrzyca: získání pozemků pro vlečku", "měsíce", "6", "12", "24", "není v podkladech", "úsudek", "vedoucí logistiky", "úsudek"),
    ("Odrzyca: stavba vlečky od získání pozemků", "měsíce", "14", "19", "24", "Vyjádření k dopravě s. 7: 14–24 měsíců", "z dat klienta", "vedoucí logistiky", "ověřeno"),
    ("Odrzyca: silniční doprava surovin přes překladiště navíc", "EUR/t surovin", "10", "20", "40", "žádná nabídka", "úsudek", "vedoucí logistiky", "úsudek"),
    ("Eschfeld: zesílení mostu", "mil. EUR", "3,20", "4,10", "5,00", "Vyjádření k dopravě s. 6: 3,2–5,0 mil. EUR", "z dat klienta", "vedoucí logistiky", "ověřeno"),
    ("Eschfeld: zesílení mostu od rozhodnutí do povolení těžké dopravy", "měsíce", "12", "18", "30", "Vyjádření k dopravě s. 6: povolení až po dokončení; délka není uvedena", "úsudek", "vedoucí logistiky", "úsudek"),
    ("Doprava z Asie (další nákup)", "EUR/t", "96", "96", "96", "Nákupy VTX-40 2023–2026: průměr za 45 měsíců 96,4", "z dat klienta", "vedoucí logistiky", "ověřeno"),
    ("Připočíst dopravu surovin z nabídek", "–", "0", "0", "1", "cena surovin je franko závod; nabídky dopravy surovin by ji počítaly dvakrát; základ nepřičítat, citlivost přičíst", "úsudek", "autor", "úsudek"),
]

# ch. 6 start of production: median and 90th percentile where the report states them (decimal years), P(in time) from T1
# Base-case start from T4; medians from the text (leden 2030 = 2030,0; listopad 2030 = 2030,83; únor 2031 = 2031,08;
# konec 2029 = 2029,92; jaro 2030 = the base case, 2030,17 and 2030,25).
SCHEDULE = [
    # site, base (T4), median, p90 or None, driver of the tail
    ("Vrbice", 2030.92, 2030.83, None, "kompenzace s pravděpodobností 0,8: stanice překračuje limit benzo[a]pyrenu"),
    ("Lipová", 2029.92, 2030.0, 2030.92, "kompenzace s pravděpodobností 0,2 (+9 až 15 měsíců); předčištění vod"),
    ("Kamenec", 2029.92, 2030.0, 2030.92, "kompenzace s pravděpodobností 0,2 (+9 až 15 měsíců)"),
    ("Wendelstedt", 2029.92, 2029.92, None, "bez kompenzace; kratší povolování v parku se nezapočítává (pesimisticky)"),
    ("Lindenau", 2030.17, 2030.17, None, "povolení k přímému vypouštění předčištěných vod"),
    ("Eschfeld", 2030.25, 2030.25, None, "změna územního plánu; start až po zesílení mostu (nosnost 16 t, cisterny 40 t)"),
    ("Odrzyca", 2029.92, 2030.0, 2031.17, "kompenzace s pravděpodobností 0,2 (+12 až 18 měsíců); pozemky pro vlečku 3,4 km"),
    ("Bory", 2031.17, 2031.08, None, "kompenzace s pravděpodobností 0,8: stanice překračuje limity PM2,5 a benzo[a]pyrenu"),
]
DEADLINE = 2030.5
DECISION = 2027.08

# ---------------------------------------------------------------- formatting

def cz(x: float, d: int = 1) -> str:
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def p(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def p3(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def mark(ok: bool) -> str:
    return '<span class="ok">✔</span>' if ok else '<span class="no">✘</span>'


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


CASE_CV = '<span class="zcase cv">ChemVitro</span>'
CASE_VE = '<span class="zcase">Velis</span>'
G_EST = '<span class="zg est">odhad (interní)</span>'
G_CALC = '<span class="zg calc">výpočet</span>'
G_DATA = '<span class="zg data">z dat klienta</span>'
G_JUD = '<span class="zg mod">úsudek</span>'
G_PROV = '<span class="zg mod">prozatímní</span>'


def section(title: str, cap: str, body: str, case: str = CASE_CV, cls: str = "") -> str:
    return (
        f'<section class="sec{(" " + cls) if cls else ""}" data-gen="r2"><div class="sh"><span class="num">00</span>'
        f"<h2>{title}</h2><span class=\"grow\"></span>{case}<span class=\"cap\">{cap}</span></div>"
        f'<div class="sb">{body}</div></section>'
    )


def table(head: list[str], rows: list[list[str]], widths: dict[int, int] | None = None, cls: str = "zt") -> str:
    widths = widths or {}
    th = ""
    for i, h in enumerate(head):
        style = f' style="width: {widths[i]}px"' if i in widths else ""
        th += f"<th{style}>{h}</th>"
    body = "".join("<tr>" + "".join(rows_cell(c) for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def rows_cell(c: str) -> str:
    if c.startswith("#"):  # numeric cell
        return f'<td class="num">{c[1:]}</td>'
    return f"<td>{c}</td>"


def cap(text: str) -> str:
    return f'<p class="zcap">{text}</p>'


# ---------------------------------------------------------------- SVG helpers

def svg_open(w: int, h: int, label: str) -> str:
    return (
        f'<svg class="zfig" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">'
        "<style>.zfig .t{font:11px var(--sans);fill:var(--muted)}.zfig .b{font:500 12px var(--mono);fill:var(--ink)}"
        ".zfig .k{font:12px var(--sans);fill:var(--ink)}.zfig .gl{stroke:var(--border);stroke-width:1}</style>"
    )


def timeline_svg() -> str:
    """ChemVitro's shared timeline: phases from the decision to full production, with purchases below."""
    w, h = 900, 250
    x0, x1 = 150, 640
    y0, y1 = 2027.0, 2031.5

    def X(t: float) -> float:
        return x0 + (t - y0) / (y1 - y0) * (x1 - x0)

    s = svg_open(w, h, "Časová osa modelu ChemVitro: rozhodnutí, povolování, výstavba, najíždění, nákup")
    for yr in range(2027, 2032):
        s += f'<line class="gl" x1="{X(yr):.1f}" x2="{X(yr):.1f}" y1="18" y2="{h-28}"/><text class="t" x="{X(yr):.1f}" y="{h-12}" text-anchor="middle">{yr}</text>'
    rows = [
        ("Rozhodnutí a žádosti", DECISION, DECISION + 0.04, None, "1. 2. 2027", "var(--ink)"),
        ("Povolování", DECISION, DECISION + 8 / 12, DECISION + 11 / 12, "8–11 měsíců", "var(--v1)"),
        ("Kompenzační opatření", DECISION + 11 / 12, DECISION + 11 / 12 + 9 / 12, DECISION + 11 / 12 + 18 / 12, "+9–18 měsíců, jen kde je úřad uloží", "var(--you)"),
        ("Výstavba", DECISION + 11 / 12, DECISION + 11 / 12 + 22 / 12, DECISION + 11 / 12 + 37 / 12, "22 měsíců + zpoždění závodu (medián 3, max. 15)", "var(--v1)"),
        ("Najíždění", DECISION + 33 / 12, DECISION + 39 / 12, None, "půl roku na 60–90 % výkonu", "var(--c4)"),
    ]
    y = 30
    for name, a, b, c, note, col in rows:
        s += f'<text class="k" x="{x0-10}" y="{y+11}" text-anchor="end">{esc(name)}</text>'
        s += f'<rect x="{X(a):.1f}" y="{y}" width="{max(X(b)-X(a),3):.1f}" height="14" rx="2" style="fill:{col}"/>'
        if c:
            s += f'<rect x="{X(b):.1f}" y="{y}" width="{X(c)-X(b):.1f}" height="14" rx="2" style="fill:{col};opacity:.3"/>'
        nx = X(c if c else b) + 6
        if abs(nx - X(DEADLINE)) < 60:
            nx = X(DEADLINE) + 8
        s += f'<text class="t" x="{nx:.1f}" y="{y+11}">{esc(note)}</text>'
        y += 26
    # purchases
    y += 6
    s += f'<text class="k" x="{x0-10}" y="{y+11}" text-anchor="end">Nákup VTX-40</text>'
    s += f'<rect x="{X(2027.0):.1f}" y="{y}" width="{X(DEADLINE)-X(2027.0):.1f}" height="14" rx="2" style="fill:var(--sunken);stroke:var(--border)"/>'
    s += f'<text class="t" x="{(X(2027.0)+X(DEADLINE))/2:.1f}" y="{y+11}" text-anchor="middle">cena podle vzorce (±10 % ročně) + doprava</text>'
    s += f'<rect x="{X(DEADLINE):.1f}" y="{y}" width="{X(2031.5)-X(DEADLINE):.1f}" height="14" rx="2" style="fill:var(--youwash);stroke:var(--you)"/>'
    s += f'<text class="t" x="{X(DEADLINE)+6:.1f}" y="{y+11}">spot, dokud závod neběží</text>'
    # deadline
    s += f'<line x1="{X(DEADLINE):.1f}" x2="{X(DEADLINE):.1f}" y1="14" y2="{h-28}" style="stroke:var(--youink);stroke-width:1.5;stroke-dasharray:4 3"/>'
    s += f'<text class="t" x="{X(DEADLINE)+4:.1f}" y="12" style="fill:var(--youink)">1. 7. 2030 · konec smlouvy</text>'
    return s + "</svg>"


def tornado_svg() -> str:
    w = 900
    rowh = 30
    h = 24 + rowh * len(TORNADO) + 30
    x0, x1 = 300, 870
    scale = (x1 - x0) / 190.0  # 190 mil. EUR across the chart
    s = svg_open(w, h, "Tornádo: rozkmit úspory Odrzyce při posunu jednoho vstupu na dolní a horní mez")
    y = 20
    for name, rng, lo, hi, (sw_lo, sw_hi), grade in TORNADO:
        s += f'<text class="k" x="{x0-10}" y="{y+11}" text-anchor="end">{esc(name)}</text>'
        s += f'<text class="t" x="{x0-10}" y="{y+24}" text-anchor="end">{esc(rng)} · {esc(grade)}</text>'
        if lo is not None:
            # exact ends around the base: drawn as two parts
            l = (TORNADO_BASE - lo) * scale
            r = (hi - TORNADO_BASE) * scale
            s += f'<rect x="{x0:.1f}" y="{y}" width="{l:.1f}" height="14" style="fill:var(--v1)"/>'
            s += f'<rect x="{x0+l:.1f}" y="{y}" width="{r:.1f}" height="14" style="fill:var(--v2)"/>'
            s += f'<text class="b" x="{x0+l+r+6:.1f}" y="{y+11}">{cz(lo)} → {cz(hi)}</text>'
        else:
            s += f'<rect x="{x0:.1f}" y="{y}" width="{sw_lo*scale:.1f}" height="14" style="fill:var(--ink);opacity:.75"/>'
            if sw_hi > sw_lo:
                s += f'<rect x="{x0+sw_lo*scale:.1f}" y="{y}" width="{(sw_hi-sw_lo)*scale:.1f}" height="14" style="fill:var(--ink);opacity:.2"/>'
                txt = f"rozkmit {cz(sw_lo)} – {cz(sw_hi)} podle lokality"
            else:
                txt = f"rozkmit {cz(sw_lo)}"
            s += f'<text class="b" x="{x0+sw_hi*scale+6:.1f}" y="{y+11}">{txt}</text>'
        y += rowh
    s += f'<text class="t" x="{x0}" y="{h-6}">rozkmit úspory v základním případě, mil. EUR (Odrzyca: základ {cz(TORNADO_BASE)}); modře posun na dolní mez, oranžově na horní</text>'
    return s + "</svg>"


def t6_svg() -> str:
    """Stacked bar per site, cost per tonne 2032 by category."""
    w = 900
    rowh = 34
    h = 20 + rowh * len(T6) + 46
    x0, x1 = 120, 760
    maxv = 1500.0
    scale = (x1 - x0) / maxv
    cols = ["var(--c6)", "var(--c5)", "var(--v2)", "var(--c1)", "var(--c2)", "var(--sunken)", "var(--c4)", "var(--v1)"]
    s = svg_open(w, h, "Provozní náklad na tunu v roce 2032 podle položek, základní případ, osm lokalit")
    y = 16
    for site, vals, total in T6:
        s += f'<text class="k" x="{x0-10}" y="{y+13}" text-anchor="end">{esc(site)}</text>'
        x = x0
        for v, col in zip(vals, cols):
            wv = v * scale
            stroke = ';stroke:var(--border);stroke-width:.5' if col == "var(--sunken)" else ""
            s += f'<rect x="{x:.1f}" y="{y}" width="{wv:.1f}" height="18" style="fill:{col}{stroke}"/>'
            if v >= 90:
                s += f'<text class="b" x="{x+wv/2:.1f}" y="{y+13}" text-anchor="middle" style="fill:{"var(--ink)" if col=="var(--sunken)" else "#fff"};font-size:11px">{v}</text>'
            x += wv
        s += f'<text class="b" x="{x+6:.1f}" y="{y+13}">{cz(total,0)}</text>'
        y += rowh
    s += f'<text class="t" x="{x0}" y="{h-8}">EUR na tunu VTX-40, rok 2032, nominálně, bez investice; nakoupená tuna by v témž roce stála přibližně {cz(BOUGHT_TONNE_2032,0)} EUR včetně přirážky a dopravy</text>'
    return s + "</svg>"


def schedule_svg() -> str:
    w = 900
    rowh = 34
    h = 40 + rowh * len(SCHEDULE) + 40
    x0, x1 = 130, 660
    y0, y1 = 2029.5, 2031.5

    def X(t: float) -> float:
        return x0 + (t - y0) / (y1 - y0) * (x1 - x0)

    s = svg_open(w, h, "Zahájení výroby podle lokalit: medián a 90. percentil proti 1. 7. 2030")
    for yr in (2030, 2031):
        s += f'<line class="gl" x1="{X(yr):.1f}" x2="{X(yr):.1f}" y1="14" y2="{h-34}"/><text class="t" x="{X(yr):.1f}" y="{h-20}" text-anchor="middle">1. 1. {yr}</text>'
    s += f'<line x1="{X(DEADLINE):.1f}" x2="{X(DEADLINE):.1f}" y1="8" y2="{h-34}" style="stroke:var(--youink);stroke-width:1.5;stroke-dasharray:4 3"/>'
    s += f'<text class="t" x="{X(DEADLINE)+4:.1f}" y="12" style="fill:var(--youink)">1. 7. 2030</text>'
    y = 36
    for (site, base, med, p90, _), r8 in zip(SCHEDULE, RULE[8]):
        s += f'<text class="k" x="{x0-10}" y="{y+5}" text-anchor="end">{esc(site)}</text>'
        if p90:
            s += f'<line x1="{X(med):.1f}" x2="{X(p90):.1f}" y1="{y}" y2="{y}" style="stroke:var(--ink);stroke-width:2"/>'
            s += f'<line x1="{X(p90):.1f}" x2="{X(p90):.1f}" y1="{y-5}" y2="{y+5}" style="stroke:var(--ink);stroke-width:2"/>'
        else:
            s += f'<text class="t" x="{X(med)+10:.1f}" y="{y+4}">90. percentil neuveden</text>'
        s += f'<circle cx="{X(med):.1f}" cy="{y}" r="5" style="fill:{"var(--ink)" if med <= DEADLINE else "var(--youink)"}"/>'
        pt = r8[5]
        s += f'<text class="b" x="{x1+200}" y="{y+4}" text-anchor="end" style="fill:{"var(--done)" if pt >= TH["time"] else "var(--youink)"}">{p(pt)} {"✔" if pt >= TH["time"] else "✘"}</text>'
        y += rowh
    s += f'<text class="b" x="{x1+200}" y="12" text-anchor="end" style="font-size:11px;fill:var(--muted)">P(výroba včas) ≥ 0,80</text>'
    s += f'<text class="t" x="{x0}" y="{h-4}">tečka medián zahájení výroby, čára po 90. percentil tam, kde ho zpráva uvádí (Lipová a Kamenec konec roku 2030, Odrzyca březen 2031)</text>'
    return s + "</svg>"


# ---------------------------------------------------------------- M3 Model sections

def m3_timeline() -> str:
    body = timeline_svg()
    body += table(
        ["Případ", "Rozhodnutí", "Fáze před provozem", "Co se platí, dokud možnost neběží", "Termín"],
        [
            [CASE_VE, "výpověď 3PL CZ do 31. 12. 2026", "hala 12 měsíců; přechod k jinému 3PL nejdřív 1. 7. 2027 (2027 napůl)", "rok 2026 všichni u 3PL CZ podle smlouvy", "žádný pevný; slib doručení ve městech"],
            [CASE_CV, "1. 2. 2027, žádosti o povolení ihned", "povolování 8–11 měsíců (+ kompenzace, územní plán, povolení vypouštění) → výstavba 22 měsíců + zpoždění srovnatelného závodu → najíždění půl roku", "nákup za cenu podle vzorce; po 30. 6. 2030 spotová cena, dokud závod neběží", "1. 7. 2030, konec smlouvy s Hanshinem"],
        ],
        {0: 110, 4: 190},
    )
    body += cap("Jedna časová osa pro všechny možnosti: každý měsíc zpoždění se promítá přímo do nákladů, protože se mezitím nakupuje. Osa ChemVitro podle přílohy B zprávy; Velis podle Zadání (Z5).")
    return section("Časová osa", "sdílená všemi možnostmi", body, case=CASE_CV + CASE_VE)


def m3_items_cv() -> str:
    rows = [
        ["Investice", "KAPITÁL · rok 0", "odhad EPC × 1,17 (medián překročení 36 závodů) + pozemek 18 ha + položky mimo odhad (most, vlečka, předčištění, kompenzace, poplatek parku)", "každá lokalita"],
        ["Zůstatková hodnota", "KAPITÁL · rok 2044", "30 % investice", "každá lokalita"],
        ["Suroviny", "VARIABILNÍ", "1,25 t na tunu × 540 EUR/t franko závod, cena sleduje surovinový index", "každá lokalita"],
        ["Energie", "VARIABILNÍ", "elektřina 0,35 MWh/t + plyn 3,1 MWh/t za ceny z nabídek, dál podle cenových cest země", "každá lokalita"],
        ["CO₂", "VARIABILNÍ", "0,62 t na tunu × cena povolenky EU ETS − bezplatná alokace", "každá lokalita"],
        ["Voda, odpad, doprava produktu", "VARIABILNÍ", "podle nabídek lokality; doprava do Brna (62 %) a Pardubic (38 %)", "každá lokalita"],
        ["Lidé", "FIXNÍ", "95 zaměstnanců × mzda operátora × skladba mezd + odvody", "každá lokalita"],
        ["Údržba, pojištění, poplatek parku", "FIXNÍ", "2–4 % odhadu investice ročně; Wendelstedt + 1,1 mil. EUR ročně", "každá lokalita"],
        ["Nákup do zahájení výroby", "VARIABILNÍ", "cena podle vzorce (±10 % ročně) + doprava; po 30. 6. 2030 spotová cena s přirážkou 20–60 %", "každá lokalita; základ celé období"],
        ["Nákup nad 40 000 t", "VARIABILNÍ", "poptávka nad kapacitu závodu na spotovém trhu", "každá lokalita"],
        ["Daň z příjmů", "DAŇ · ROČNĚ", "sazba země (CZ 21 %, PL 19 %, DE 28–30 % → 23–25 % od 2032) × (zisk − odpisy); jen pro NPV po zdanění", "každá lokalita"],
    ]
    body = table(["Položka", "Druh", "Vzorec v základu", "Možnosti"], rows, {1: 150, 3: 180})
    body += cap("Náklady na zásobování = investice + provoz od zahájení výroby + nákup do zahájení výroby + nákup nad 40 000 t − zůstatková hodnota. Úspora lokality = náklady dalšího nákupu − náklady vlastní výroby, v NPV 2027–2044; peněžní toky diskontovány k polovině roku, nominálně, inflace 2 % (prozatímní). Základ pro srovnání: <b>0 · Další nákup</b>, počítaný ve stejných budoucnostech jako osm lokalit.")
    return section("Položky modelu: náklady na zásobování", "11 položek · druhy podle metodiky · příloha B zprávy", body)


def m3_base_vs_futures() -> str:
    rows = [
        [CASE_VE, "C2 proti B", "#+8,8 mil. Kč", "#+7,3 mil. Kč", "20 000 losů, seed 20261030", "ztráta objednávek a poplatky losované z rozpětí; v základu nejpravděpodobnější hodnoty"],
        [CASE_CV, "Odrzyca proti dalšímu nákupu", "#170,7 mil. EUR", "#134,7 mil. EUR", "20 000 budoucností, seed 20270201", "kompenzační opatření (20 % budoucností), zpoždění s nákupy na spotu a překročení rozpočtu nad medián nastanou jen v části budoucností"],
    ]
    body = table(["Případ", "Možnost", "Základní případ", "Medián budoucností", "Losování", "Proč se liší"], rows, {0: 100, 2: 130, 3: 150, 4: 180})
    body += cap("Základní případ je jediný výpočet, v němž má každý vstup nejpravděpodobnější hodnotu: slouží ke srovnání možností a k citlivosti (tornádo, body zvratu). Budoucnosti losují všechny vstupy najednou z rozdělení PERT (dolní, nejpravděpodobnější, horní hodnota) s deklarovanými korelacemi; pravidlo se čte z nich. Stejné semínko dává stejné bajty: opakovaný běh je kontrola, ne nový výsledek.")
    return section("Základní případ a budoucnosti", "jeden výpočet proti 20 000", body, case=CASE_CV + CASE_VE)


def m3_extra_runs() -> str:
    rows = [
        [CASE_CV, "Hranice rozhodnutí", "šance na kompenzaci tam, kde stanice limity nepřekračuje", "0 · 5 · 10 · 14 · 15 · 16 · 20 · 30 %", 'Rozhodnutí · <a href="KM4Results.dc.html">M4</a>'],
        [CASE_CV, "Korelace", "tři nastavení: nulové (překročení a zpoždění nezávisle), podle úsudku, silné", "0 / 0,8 · 0,6 · 0,4 / 0,95 · 0,85 · 0,4", "Rozhodnutí · M4"],
        [CASE_CV, "Odklad rozhodnutí", "datum rozhodnutí a podání žádostí", "+2 · +4 · +6 měsíců", 'Rozhodnutí · M4, Harmonogram · <a href="KM12Schedule.dc.html">M4g</a>'],
        [CASE_CV, "Zpoždění náboru", "start každé lokality", "+1 · +2 · +3 měsíce", "Harmonogram · M4g"],
        [CASE_CV, "Podmínky po roce 2035", "přirážka od roku 2036", "0 % · jako první prodloužení · 30 %", "Rozhodnutí · M4"],
        [CASE_CV, "Hodnota pro pravidlo", "budoucnosti rozděleny podle toho, zda úřad kompenzaci uloží; pravidlo uplatněno v každé skupině", "Odrzyca · Kamenec · Lipová · všechny tři", "Rozhodnutí · M4"],
        [CASE_VE, "Varianty struktury", "tvar vztahu (ztráta podle zpoždění, přenos mezd, zůstatková hodnota)", "tři varianty, každá počítána celá", "Model · 08 výše"],
        [CASE_VE, "Zátěžové testy", "hodnoty mimo rozdělení", "výpadek skladu, plný přenos mezd", "Předpoklady · M2 04"],
    ]
    body = table(["Případ", "Propočet", "Co se mění", "Hodnoty", "Kde se čte"], rows, {0: 100, 1: 160, 3: 220, 4: 190})
    body += cap("Pravidlo dodatečných propočtů: týž model, tytéž budoucnosti s týmž semínkem, pravidlo v zapsaném znění; mění se vždy jen jeden předpoklad a všechny budoucnosti se počítají znovu. Každý propočet je v tomto seznamu; co tu není, zpráva nepočítala.")
    return section("Dodatečné propočty", "jeden předpoklad najednou", body, case=CASE_CV + CASE_VE)


# ---------------------------------------------------------------- M4 Rozhodnutí sections

def rule_table_8() -> str:
    rows = []
    for site, r in zip(SITES, RULE[8]):
        med, lo, hi, beat, loss, tm, inv = r
        ok = beat >= TH["beat"] and loss <= TH["loss"] and tm >= TH["time"] and inv <= TH["inv"]
        rows.append([
            f"<b>{site}</b>",
            f"#{cz(med)}",
            f"#{cz(lo)} až {cz(hi)}",
            f"#{p(beat)} {mark(beat >= TH['beat'])}",
            f"#{p(loss)} {mark(loss <= TH['loss'])}",
            f"#{p(tm)} {mark(tm >= TH['time'])}",
            f"#{cz(inv)} {mark(inv <= TH['inv'])}",
            "<b>ano</b>" if ok else "ne",
        ])
    body = table(
        ["Lokalita", "Medián úspory", "90% interval", "P(porazí nákup) ≥ 0,75", "P(ztráta > 20) ≤ 0,10", "P(výroba k 1. 7. 2030) ≥ 0,80", "Investice ≤ 175 (základ)", "Splnila pravidlo"],
        rows, {7: 90},
    )
    body += cap(f"Pravidlo finanční ředitelky, zapsané 2. 11. 2026 před prvním výsledkem: lokalita s nejvyšším mediánem úspory proti dalšímu nákupu (NPV nákladů 2027–2044 při 8 %, před zdaněním), splní-li čtyři podmínky; jinak žádná, a říci, který předpoklad stojí za ověření. Investiční podmínku pravidlo neuvádí s pravděpodobností: posuzuje se na základním případu, výklad čeká na potvrzení. Verdikt: <b>nic</b>. Lipová, Kamenec a Odrzyca nesplní jen termín (0,75–0,76 proti 0,80), německé lokality hlavně riziko ztráty. Medián, interval a pravděpodobnosti {G_EST}, investice {G_CALC}. Další nákup v mediánu 897 mil. EUR.")
    return section("Pravidlo při 8 %", "tabulka T1 zprávy", body)


def rule_table_other() -> str:
    rows = []
    for i, site in enumerate(SITES):
        r6, r10 = RULE[6][i], RULE[10][i]
        def cells(r):
            med, lo, hi, beat, loss, tm, inv = r
            return [f"#{cz(med)} <span class=\"cap\" style=\"display:inline\">({cz(lo)} až {cz(hi)})</span>", f"#{p(beat)} {mark(beat >= TH['beat'])}", f"#{p(loss)} {mark(loss <= TH['loss'])}"]
        rows.append([f"<b>{site}</b>", *cells(r6), *cells(r10), "ne"])
    body = table(
        ["Lokalita", "6 %: medián (90% interval)", "P(porazí)", "P(ztráta > 20)", "10 %: medián (90% interval)", "P(porazí)", "P(ztráta > 20)", "Pravidlo"],
        rows, {7: 70},
    )
    body += cap("Tabulky T2 a T3 zprávy. P(výroba včas) a investice na sazbě nezávisí, takže verdikt je při 6 % i 10 % týž: nic. Při 6 % Wendelstedt podmínku ztráty téměř splní (0,105 proti 0,10) a Lindenau nesplní jen termín; při 10 % přibude Vrbici riziko ztráty (0,12) a Wendelstedtu a Lindenau i podmínka, že porazí nákup (0,71 a 0,73). " + G_EST)
    return section("Pravidlo při 6 % a 10 %", "tabulky T2 a T3", body)


def boundary() -> str:
    rows = []
    for ch, pick, pts, meds in BOUNDARY:
        rows.append([f"<b>{ch}</b>", f"<b>{pick}</b>" if pick != "nic" else pick, "#" + " / ".join(p3(x) for x in pts), "#" + " / ".join(cz(x) for x in meds)])
    body = table(["Šance na kompenzaci", "Pravidlo vybere", "Výroba včas: Lipová / Kamenec / Odrzyca", "Medián úspory: Lipová / Kamenec / Odrzyca, mil. EUR"], rows, {0: 150, 1: 130})
    body += cap("Verdikt stojí na jediném úsudku: šanci, že úřad uloží kompenzační opatření tam, kde stanice limity nepřekračuje (model 20 %, žádný dokument). Do 14 % vybere pravidlo Odrzycu, při 15 % Kamenec (Odrzyca klesne na 0,797), od 16 % nic. Medián se přitom mění jen málo: šance na kompenzaci rozhoduje, zda lze vybírat, ne kolik se ušetří. Zjistit, na které straně hranice ChemVitro je, lze jen u úřadů. " + G_EST)
    return section("Hranice rozhodnutí", "jeden úsudek, celé rozpětí, budoucnosti znovu", body)


def delays() -> str:
    rows = []
    for m, vals in DELAY:
        rows.append([f"<b>{m} měsíců</b>" if m != 2 else "<b>2 měsíce</b>", *[f"#{p3(v)}" for v in vals], "nic"])
    body = table(["Odklad rozhodnutí", *SITES, "Pravidlo vybere"], rows, {0: 120, 9: 90})
    body += cap("Pravděpodobnost zahájení výroby k 1. 7. 2030 při šanci na kompenzaci 20 %: v žádném řádku pravidlo nic nevybere, čekání jen snižuje jistotu termínu. " + G_EST)
    rows2 = [["Výroba včas: Lipová, Kamenec, Odrzyca", *[f"#{p3(v)}" for _, v, _ in DELAY_NOCOMP]], ["Pravidlo vybere", *[f"<b>{pick}</b>" if pick != "nic" else pick for _, _, pick in DELAY_NOCOMP]]]
    body += '<div style="max-width:760px;margin-top:12px">' + table(["Úřady potvrdí, že kompenzaci neuloží", "0 měsíců", "2 měsíce", "4 měsíce", "6 měsíců"], rows2) + "</div>"
    body += cap("S potvrzením vybere pravidlo Odrzycu i po dvou měsících čekání, po čtyřech už nic. Odpověď úřadů má cenu jen tehdy, přijde-li zhruba do dvou měsíců od 1. 2. 2027, nebo poběží-li zjišťování souběžně s rozhodnutím. " + G_EST)
    return section("Odklad rozhodnutí", "s posuzovanou událostí a bez ní", body)


def hiring() -> str:
    rows = []
    for m in (1, 2, 3):
        vals = HIRING[m]
        note = {1: "", 2: "tatáž čísla jako dvouměsíční odklad", 3: f"Wendelstedt {p3(HIRING_WENDELSTEDT_3)}, nad 0,80; riziko ztráty dál nesplňuje"}[m]
        rows.append([f"<b>+{m} měsíc{'e' if m > 1 else ''}</b>", *[f"#{p3(v)}" for v in vals], note])
    body = '<div style="max-width:820px">' + table(["Zpoždění náboru", "Lipová", "Kamenec", "Odrzyca", "Poznámka"], rows, {0: 130}) + "</div>"
    body += cap("Zátěžová zkouška, ne předpověď: podklady neuvádějí, jak dlouho potrvá najmout 95 lidí (obsazení místa operátora 49–71 dní, v Eschfeldu 118; u Kamence do roku 2028 nábor 380 lidí jinde). Zpoždění náboru posouvá start stejně jako odklad rozhodnutí a oba vlivy se sčítají: dva měsíce odkladu a dva měsíce náboru odpovídají čtyřměsíčnímu odkladu, po kterém pravidlo nevybere nic ani s příznivou odpovědí. " + G_EST)
    return section("Zpoždění náboru", "zátěžová zkouška, sčítá se s odkladem", body)


def tornado() -> str:
    body = tornado_svg()
    body += cap("Každý vstup zvlášť na dolní a horní mez, ostatní v základu. Cena Hanshinu posouvá úsporu více než dvakrát silněji než druhý vstup a u všech osmi lokalit jsou první tři páky tytéž; dvě z nich jsou obchodní, ne technické. Ověřovat má smysl hlavně cenu Hanshinu; přesnější údržba nebo mzdy by verdikt nezměnily. Rozkmit u Odrzyce přesně pro první dvě páky; u ostatních zpráva uvádí rozpětí přes lokality. " + G_CALC)
    return section("Tornádo v základním případě", "Odrzyca, základ 170,7 mil. EUR", body)


def breakeven() -> str:
    rows = [[f"{name}, {unit}", *[f"#{v}" for v in vals]] for name, unit, vals in BREAKEVEN]
    body = table(["Bod zvratu", *SITES], rows, {0: 260})
    body += cap("Základní případ. Při průměrné ceně roku 2025 (1 296 EUR/t) by vlastní výroba v základu porazila nákup jen v Lipové, Kamenci, Odrzyci a Borech; v mediánu budoucností, které zahrnují rizika, prohrává všude (−6,1 Odrzyca až −78,1 Eschfeld). České a polské lokality porazí nákup i bez přirážky, dokonce se slevou 6,3–12,6 %; německé jsou na hraně. Strop 175 překročí Bory, Odrzyca a Kamenec až při překročení rozpočtu 35–44 %, Eschfeld už při 16,7 %, pod mediánem srovnatelných závodů. " + G_CALC)
    return section("Body zvratu tří největších pák", "jedna hodnota, ostatní v základu", body)


def post2035() -> str:
    rows = [[f"<b>{name}</b>", *[f"#{cz(v)}" for v in vals], f"<b>{pick}</b>" if pick != "nic" else pick] for name, vals, pick in POST2035]
    body = table(["Přirážka od roku 2036", *SITES, "Pravidlo vybere"], rows, {0: 200, 9: 100})
    body += cap("Dopis dodavatele pokrývá jen prvních pět let prodloužení; model v základu předpokládá tytéž podmínky i po roce 2035. Při 30 % by pravidlo splnil Wendelstedt (porazí nákup 0,87, ztráta 9 %, termín 0,94). Při návratu k ceně podle vzorce bez přirážky klesne úspora každé lokality zhruba o 53 mil. EUR a riziko ztráty Lipové, Kamence a Odrzyce stoupne nad práh (0,14, 0,12, 0,12). Druhá páka verdiktu; na rozdíl od kompenzace ji dnes nelze zjistit, závazná nabídka přijde v polovině roku 2029. Mediány " + G_EST)
    return section("Podmínky po roce 2035", "druhá páka verdiktu", body)


def correlation() -> str:
    rows = [
        ["Nulové", "0 · 0 · 0; překročení rozpočtu a zpoždění losovány nezávisle", "nic"],
        ["Podle úsudku (základ)", "elektřina mezi zeměmi 0,8 · elektřina a plyn 0,6 · plyn a povolenka 0,4", "nic"],
        ["Silné", "0,95 · 0,85 · 0,4", "nic"],
    ]
    body = '<div class="zcols">' + table(["Nastavení korelací", "Hodnoty", "Pravidlo vybere"], rows, {0: 160, 2: 110})
    body += table(["Lokalita", "Medián úspory ve třech nastaveních, mil. EUR"], [[s, f"#{r}"] for s, r in CORR], {0: 120}) + "</div>"
    body += cap("Korelace jsou úsudek, a pravidlo hlídá chvosty, proto se jeho výsledek počítá ve třech nastaveních. Verdikt je ve všech třech týž; mediány se liší nejvýše o 1,4 mil. EUR a pravděpodobnosti nejvýše o 0,01. Na korelaci závisí jen jemný tvar mapy budoucností (Sociomapa). " + G_EST)
    return section("Kontrola korelací", "verdikt beze změny, mediány do 1,4 mil. EUR", body)


def voi() -> str:
    rows = [[what, f"#<b>{cz(v)}</b>", then] for what, v, then in VOI_RULE]
    body = "<h3 class=\"zh3\">1 · Hodnota pro pravidlo</h3>" + table(["Co se zjistí", "Hodnota pro pravidlo, mil. EUR", "Co pravidlo pak vybere"], rows, {0: 240, 1: 150})
    body += cap("Průměr přes obě možné odpovědi. Bez informace pravidlo nevybere nic a úspora je 0; s ní se pravidlo uplatní zvlášť v budoucnostech s každou odpovědí. Hodnota je vysoká, protože odpověď zhruba ve čtyřech pětinách budoucností změní výsledek pravidla z „nic“ na lokalitu. U Borů (stanice nad limity) se nepočítala. " + G_EST)
    rows2 = [[what, f"#{cz(v)}"] for what, v in EVPPI]
    body += "<h3 class=\"zh3\">2 · Očekávaná hodnota dokonalé dílčí informace (EVPPI)</h3><div style=\"max-width:620px\">" + table(["Vstup", "EVPPI, mil. EUR"], rows2, {1: 140}) + "</div>"
    body += cap(f"Podle průměrné úspory je nejlepší {MEAN_BEST[0]} ({cz(MEAN_BEST[1])} mil. EUR) a informace o kompenzaci tuto volbu sotva mění. Dokonalá informace o všech vstupech by měla hodnotu {cz(EVPPI_ALL)} mil. EUR; hodnoty se nesčítají. Cena Hanshinu tu hodnotu nemá, přestože je největší pákou: v celém rozpětí modelu (1 470–1 868 EUR/t) se v průměru vyplatí stavět, a to v Odrzyci; průměr roku 2025 (1 296) leží mimo ně, proto se cena prověřuje zvlášť. Strong a Oakley (2013). " + G_EST)
    body += '<div class="zflag" style="margin-top:12px"><b>Ani jedna hodnota není rozpočtem na zjištění.</b> Obě míry počítají s dokonalou informací a neutrálním postojem k riziku a nezapočítávají náklady ani čas na její získání; stanovisko úřadu dokonalou informací být nemusí. Čas je rozhodující: odpověď má hodnotu jen do dvou měsíců od 1. 2. 2027, nebo při zjišťování souběžném s rozhodnutím.</div>'
    return section("Hodnota informace ve dvou mírách", "pro pravidlo první, EVPPI druhá", body)


def enquiry() -> str:
    rows = [[f"<b>{a}</b>", b, c, d, e] for a, b, c, d, e in ENQUIRY]
    body = table(["Co se zjistí", "Výstup", "Doba", "Cena", "Kdo"], rows, {0: 150, 2: 190, 3: 100, 4: 190})
    body += cap("Doby jsou návrhem " + G_JUD + "; náklady na zjištění ani na souběžnou přípravu žádostí podklady neuvádějí. Ústní nebo neurčitou odpověď zpráva neumí převést na pravděpodobnost: co platí za potvrzení, rozhodne představenstvo. Výsledek pravidla změní jen písemné stanovisko, že kompenzace požadována nebude: pak vybere Odrzycu, jinak Kamenec, jinak Lipovou.")
    return section("Zjištění před rozhodnutím", "výstup, doba, cena, kdo", body)


# ---------------------------------------------------------------- M4b Finance sections

def t4() -> str:
    rows = []
    for site, pre, post, medpost, irr, pay, inv, start in T4:
        rows.append([f"<b>{site}</b>", *[f"#{cz(v)}" for v in pre], *[f"#{cz(v)}" for v in post], f"#{cz(medpost)}", f"#{irr}", f"#{pay}", f"#{cz(inv)}", f"#{start}"])
    body = table(["Lokalita", "Před zdaněním 6 %", "8 %", "10 %", "Po zdanění 6 %", "8 %", "10 %", "Medián po zdanění 8 %", "IRR", "Návratnost", "Investice (ceny 2026)", "Zahájení výroby (základ)"], rows, cls="zt small")
    body += cap(f"Základní případ, mil. EUR; úspora = nákup minus vlastní výroba. Další nákup (NPV nákladů 2027–2044) {cz(BUY_NPV[0])} / {cz(BUY_NPV[1])} / {cz(BUY_NPV[2])} mil. EUR při 6 / 8 / 10 %. Před zdaněním vedou při každé sazbě Odrzyca, Kamenec a Lipová; sazba mění výši, ne pořadí. IRR 18,2–20,5 % v Česku a Polsku, 14,4–15,5 % v Německu; investice se vrátí 2034 až 2036. Po zdanění jsou Kamenec a Odrzyca rovnocenné (121,3 a 118,6; medián 107,3 a 107,2), německé lokality ztrácejí zdaněním méně (vyšší sazba zvyšuje daňovou hodnotu nákladů a odpisů); pravidlo pracuje jen s NPV před zdaněním. Základ {G_CALC}, medián po zdanění {G_EST}, daňové sazby {G_PROV}.")
    return section("NPV před zdaněním a po zdanění při třech sazbách, IRR, návratnost", "tabulka T4", body)


def t5() -> str:
    rows = []
    for site, items, total, pr, pct in T5:
        rows.append([f"<b>{site}</b>", *[f"#{cz(v)}" if v else '#<span class="muted">–</span>' for v in items], f"#<b>{cz(total)}</b>"])
    body = table(["Lokalita", *T5_COLS, "Celkem"], rows, cls="zt small")
    rows2 = [[f"<b>{site}</b>", f"#{p(pr)} {mark(pr >= 0.5)}", *[f"#{x}" for x in pct.split(" / ")]] for site, items, total, pr, pct in T5]
    body += '<div style="max-width:620px;margin-top:12px">' + table(["Lokalita", "P(investice ≤ 175)", "p10", "p50", "p90"], rows2, {1: 150}) + "</div>"
    body += cap("Základní případ, mil. EUR, ceny 2026. Odhad EPC (třída 4, ±25 %) je navýšen o medián překročení 36 srovnatelných závodů (17 %, 90. percentil 30,2 %, maximum 61 %); překročení a zpoždění se losují z téhož závodu najednou. Položky a součet " + G_CALC + "; druhá tabulka: P(investice ≤ 175) a percentily investice z budoucností " + G_EST + ", značka od 0,5 výše.")
    body += '<div class="zcols" style="margin-top:12px"><div class="zcard"><h3>Co odhad EPC výslovně nezahrnuje</h3><p>pozemek · infrastruktura mimo areál (vlečky, přípojky, úpravy komunikací a mostů) · předčištění odpadních vod nad rámec neutralizace · kompenzační opatření · poplatky chemického parku · pobídky</p><p class="muted">Doplněno podle dokumentů lokalit: pozemek 18 ha všude; most u Eschfeldu 3,2–5,0 mil. EUR (nosnost 16 t, cisterny 40 t); vlečka v Odrzyci 3,4 km za 1,9–2,8 mil. EUR/km; předčištění v Lipové a Lindenau 6,7–14,1 mil. EUR; kompenzace 3–15 mil. EUR tam, kde ji úřad uloží; poplatek parku ve Wendelstedtu 1,1 mil. EUR ročně (v provozu, ne v investici).</p></div><div class="zcard"><h3>Výklad investiční podmínky</h3><p>Pravidlo neuvádí pravděpodobnost, investice se proto posuzuje na základním případu; vedle toho P(investice ≤ 175). Přísnější výklad „v každé budoucnosti“ by vyřadil všech osm lokalit a verdikt „nic“ by nezměnil. Strop ohrožuje hlavně německé lokality (0,50–0,57). Výklad čeká na potvrzení finanční ředitelkou.</p></div></div>'
    return section("Investice podle položek", "tabulka T5 · co odhad EPC nezahrnuje", body)


def incentives() -> str:
    rows = [[f"<b>{a}</b>", b, c, d] for a, b, c, d in INCENTIVES]
    body = table(["Kde", "Pobídka podle agentur", "Forma", "Dopad na výpočet"], rows, {0: 220, 2: 150})
    body += cap("Základní případ pobídky nezapočítává: musí je schválit úřad a klient neví, zda je dostane; v budoucnostech je model přiznává s pravděpodobností 0,5 " + G_JUD + ". Proč je pravidlo před zdaněním nevidí: daňová úleva snižuje daň, tedy jen NPV po zdanění, a má hodnotu jen při dostatečném zisku, který model neověřuje; hotovostní dotace by snížila investici, ale ta je v základu bez ní. Forma pobídek " + G_PROV + ", čeká na ověření u pramene.")
    return section("Pobídky: daňové úlevy proti hotovostním dotacím", "proč je pravidlo před zdaněním nevidí", body)


# ---------------------------------------------------------------- M4d Provoz sections

def t6_section() -> str:
    body = t6_svg()
    body += '<div class="zleg">' + "".join(
        f'<span><i style="background:{c}{";border:1px solid var(--border)" if c=="var(--sunken)" else ""}"></i>{n}</span>'
        for n, c in zip(T6_COLS, ["var(--c6)", "var(--c5)", "var(--v2)", "var(--c1)", "var(--c2)", "var(--sunken)", "var(--c4)", "var(--v1)"])
    ) + "</div>"
    rows = [[f"<b>{site}</b>", *[f"#{v}" for v in vals], f"#<b>{cz(total,0)}</b>"] for site, vals, total in T6]
    body += table(["Lokalita", *T6_COLS, "Celkem"], rows)
    body += cap("Rok 2032, kdy závod v základním případě všude běží naplno; nominálně, bez investice; z návrhu procesu, nabídek lokalit a cenových cest modelu. " + G_CALC)
    body += '<div class="zcols" style="margin-top:12px"><div class="zcard"><h3>Co se mezi lokalitami liší</h3><p><b>Lidé</b> 102–124 EUR/t v Česku a Polsku, 195–232 v Německu (vyšší mzdy). <b>Údržba, pojištění a poplatek parku</b> 103–124 proti 122–157: údržba se počítá z odhadu investice, nejvyššího v Německu; Wendelstedt platí poplatek parku 1,1 mil. EUR ročně. <b>Doprava</b> produktu do Brna a Pardubic 20–38 proti 53–58, protože německé lokality jsou dál.</p></div><div class="zcard"><h3>Co se neliší</h3><p><b>Suroviny</b> 760 EUR/t všude, protože je klient oceňuje stejnou cenou franko závod; největší položka. <b>CO₂</b> 56 EUR/t všude; <b>energie</b> 179–192; voda a odpad v jednotkách EUR. I nejdražší německý provoz (1 463) je výrazně levnější než nakoupená tuna (asi 2 340 včetně přirážky a dopravy); z rozdílu se splácí investice, a ztrácí se čekáním, dokud závod neběží.</p></div></div>'
    return section("Provozní náklad na tunu podle položek, rok 2032", "tabulka T6 · základní případ", body)


# ---------------------------------------------------------------- M4g Harmonogram sections

def schedule_section() -> str:
    body = schedule_svg()
    body += cap("Lipová, Kamenec a Odrzyca v mediánu zahájí výrobu v lednu 2030, s půlroční rezervou; 90. percentil Lipové a Kamence připadá na konec roku 2030, Odrzyce na březen 2031, protože v Polsku se povolování prodlužuje více. Vrbice a Bory mají medián až v listopadu 2030 a v únoru 2031: termín nestihnou ani v typické budoucnosti. Wendelstedt je nejrychlejší (konec 2029, 0,94); Lindenau a Eschfeld jaro 2030. Pro pravidlo rozhoduje délka čáry vpravo od 1. 7. 2030, ne poloha tečky: <b>rozhoduje chvost, ne medián.</b> " + G_EST)
    return section("Zahájení výroby proti termínu", "medián, 90. percentil, P(včas)", body)


def tail_drivers() -> str:
    rows = [[f"<b>{site}</b>", COUNTRY[i], drv, f"#{p(RULE[8][i][5])}"] for i, (site, _, _, _, drv) in enumerate(SCHEDULE)]
    body = table(["Lokalita", "Země", "Co prodlužuje chvost", "P(výroba včas)"], rows, {1: 60, 3: 120})
    body += cap("Všem lokalitám je společné povolování 8–11 měsíců, výstavba 22 měsíců se zpožděním vylosovaného srovnatelného závodu (medián 3, nejvýše 15 měsíců) a najíždění půl roku. Kompenzační opatření prodlouží povolování o 9–15 měsíců v Česku a 12–18 v Polsku; u srovnatelných závodů byla uložena u 5 z 9 českých, 4 z 9 polských a u žádného ze 14 německých. Z dat klienta: memorandum k povolování, srovnatelné závody, měření ovzduší, vyjádření k dopravě a čistíren. Šance 0,2 tam, kde stanice limity nepřekračuje, je " + G_JUD + ".")
    return section("Co prodlužuje chvost", "povolování, kompenzace, most, vlečka", body)


def delay_hiring_table() -> str:
    cols = [0, 1, 2, 3]
    rows = []
    for dm, _ in DELAY:
        cells = []
        for hm in cols:
            tot = dm + hm
            if tot in TOTAL_DELAY:
                v = TOTAL_DELAY[tot]
                cells.append("#" + " / ".join(p3(x) for x in v))
            else:
                cells.append('#<span class="muted">—</span>')
        pick = "Odrzyca" if dm + 0 <= 2 else "nic"
        rows.append([f"<b>{dm} měs.</b>", *cells, pick])
    body = table(["Odklad rozhodnutí ↓ · zpoždění náboru →", "0 měsíců", "+1 měsíc", "+2 měsíce", "+3 měsíce", "Pravidlo bez kompenzace, bez náboru"], rows, {0: 200, 5: 170})
    body += cap("P(výroba k 1. 7. 2030) Lipová / Kamenec / Odrzyca při šanci na kompenzaci 20 %; s ní pravidlo nevybere nic v žádném poli. Zpoždění náboru posouvá start stejně jako odklad rozhodnutí, takže platí součet měsíců: pole bez hodnoty je součet, který zpráva nepočítala. Poslední sloupec: potvrdí-li úřady, že kompenzaci neuloží, vybere pravidlo Odrzycu do dvou měsíců celkového posunu, potom nic. Lokality blízko hranice ztrácejí zpočátku asi 0,015 za měsíc, po dvou měsících více. " + G_EST)
    return section("Odklad a nábor: každý měsíc", "součet měsíců, pravidlo znovu", body)


def velis_schedule_note() -> str:
    body = table(["Harmonogram", "Rozdělení"], [["pevné termíny ze Zadání: výpověď 3PL CZ do 31. 12. 2026, hala za 12 měsíců, přechod 1. 7. 2027", "žádné; zpoždění přechodu je zátěžový test v Předpokladech (M2 04)"]])
    return section("Pevné termíny", "bez rozdělení", body, case=CASE_VE)



# ---------------------------------------------------------------- M4f Logistika sections

def transport_svg() -> str:
    w = 900
    rowh = 26
    h = 16 + rowh * len(TRANSPORT) + 40
    x0 = 130
    scale = 7.0
    s = svg_open(w, h, "Doprava produktu do Brna a Pardubic podle lokalit, EUR na tunu, rok 2032")
    y = 12
    for site, v in TRANSPORT:
        col = "var(--v1)" if v < 45 else "var(--v2)"
        s += f'<text class="k" x="{x0-10}" y="{y+12}" text-anchor="end">{esc(site)}</text>'
        s += f'<rect x="{x0}" y="{y}" width="{v*scale:.1f}" height="16" rx="2" style="fill:{col}"/>'
        s += f'<text class="b" x="{x0+v*scale+6:.1f}" y="{y+12}">{v}</text>'
        y += rowh
    xa = x0 + TRANSPORT_ASIA * scale
    s += f'<line x1="{xa:.1f}" x2="{xa:.1f}" y1="6" y2="{y+4}" style="stroke:var(--ink);stroke-dasharray:4 3"/>'
    s += f'<text class="t" x="{xa-6:.1f}" y="{y}" text-anchor="end">doprava z Asie při dalším nákupu: {TRANSPORT_ASIA} EUR/t</text>'
    s += f'<text class="t" x="{x0}" y="{h-8}">EUR na tunu produktu, rok 2032, základní případ; z nabídek dopravy (Nabídky dopravy), 62 % do Brna, 38 % do Pardubic</text>'
    return s + "</svg>"


def m4f_transport() -> str:
    body = transport_svg()
    body += cap("Složka <i>Doprava produktu do Brna a Pardubic, EUR/t</i> (perspektiva logistická, v modelu): 20–38 EUR/t z českých a polských lokalit, 53–58 z německých, protože jsou vzdálenější; třetí z položek, kterými se země liší (vedle lidí a údržby, Provoz). Doprava surovin se nepřičítá: cena surovin je franko závod. " + G_CALC)
    return section("Doprava produktu do Brna a Pardubic", "T6, sloupec doprava", body)


def m4f_access() -> str:
    rows = [
        ["<b>Odrzyca</b>", "Vlečka k postavení: délka, cena za km, získání pozemků", "nabídka dopravy počítá s vlečkou, která neexistuje; 3,4 km, 1,9–2,8 mil. EUR/km, pozemky 6–24 měsíců, stavba 14–24 měsíců", "#6,8", "do postavení vlečky silniční doprava surovin přes překladiště s přirážkou 10–40 EUR/t surovin; start výroby na vlečce nezávisí"],
        ["<b>Eschfeld</b>", "Silniční přístup: nosnost mostu 16 t proti 40 t, zesílení", "cisterny váží 40 t, most unese 16 t; zesílení 3,2–5,0 mil. EUR, 12–30 měsíců do povolení těžké dopravy", "#4,1", "výroba začne nejdříve po zesílení mostu (Harmonogram); investice 175,5 proti stropu 175"],
        ["ostatních šest", "–", "příjezd a vlečka podle nabídek lokalit bez položky navíc", '#<span class="muted">–</span>', "–"],
    ]
    body = table(["Lokalita", "Složka", "Co dokumenty uvádějí", "V investici (základ, mil. EUR)", "Co to dělá v modelu"], rows, {0: 110, 3: 120})
    body += cap("Obě položky odhad EPC výslovně nezahrnuje (infrastruktura mimo areál); doplněny podle Vyjádření k dopravě s. 6 a 7 a Srovnatelných závodů, v investici podle tabulky T5 (Finance). Každá je v modelu: jako investice i jako čas před zahájením výroby. " + G_DATA + " " + G_JUD)
    return section("Vlečka a most: přístup, který odhad stavby nezahrnuje", "T5 · T9 · nález kontroly dat P1", body)


def m4f_inputs() -> str:
    rows = [[f"<b>{a}</b>", b, f"#{lo}", f"#{li}", f"#{hi}", src, f'<span class="zg {"data" if g == "z dat klienta" else ("est" if g == "odhad" else "mod")}">{g}</span>', who, st] for a, b, lo, li, hi, src, g, who, st in LOGISTICS_INPUTS]
    body = table(["Vstup", "Jednotka", "Dolní", "Nejspíš", "Horní", "Zdroj", "Stupeň", "Stojí za ním", "Stav"], rows, {2: 55, 3: 60, 4: 55}, cls="zt small")
    body += cap("Logistické řádky tabulky T9 zprávy. Cena surovin 540 EUR/t franko závod je stejná pro všechny lokality; přičtení dopravy surovin z nabídek by úspory snížilo o 9–14 mil. EUR a verdikt by nezměnilo (nález P1). Co chybí, jde za vedoucím logistiky: pozemky pro vlečku se Zarząd Infrastruktury Kolejowej Opole a cena silniční dopravy do jejího postavení, pro kterou nabídka není (Rozhodnutí, zjištění před rozhodnutím).")
    return section("Logistické vstupy modelu", "T9 · rozpětí, zdroj, stupeň, kdo za ním stojí", body)


def build_m4f() -> None:
    path = ROOT / "KM11Logistics.dc.html"
    html = rebuild(
        path,
        ["Cost-to-serve podle zón", m4f_transport, "Vlastní sklad, nebo 3PL", m4f_access, m4f_inputs, ("grid", "Dimenzování skladu (hala A)", "Úroveň služby a OTIF"), "Síť a umístění skladu (těžiště)"],
        extra={
            TABS_OLD: TABS_NEW,
            '<a href="KM9Operations.dc.html"><i class="ph ph-caret-left s"></i>Provoz</a>': '<a href="KM12Schedule.dc.html"><i class="ph ph-caret-left s"></i>Harmonogram</a>',
        },
    )
    path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- splicing

EXTRA_CSS = """
/*r2*/
.zcase{display:inline-flex;align-items:center;height:20px;padding:0 7px;border-radius:4px;font:500 11px var(--sans);background:var(--sunken);color:var(--ink);border:1px solid var(--border);white-space:nowrap}
.zcase.cv{background:var(--swash);border-color:var(--sedge);color:var(--signal)}
.zcase+.zcase{margin-left:-4px}
.zt .ok{color:var(--done);font-weight:600}.zt .no{color:var(--youink);font-weight:600}
.zh3{margin:4px 0 8px;font-size:13px;font-weight:600}
.zt.small{font-size:12px}.zt.small th,.zt.small td{padding:6px 7px}.zt.small td.num{font-size:11.5px}
.zt td .cap{font-size:11px;color:var(--muted)}
.zpark{display:flex;align-items:center;gap:10px;padding:8px 24px;background:var(--sunken);border-bottom:1px solid var(--border);font-size:12.5px;color:var(--muted)}
"""

SEC_RE = re.compile(r'<section class="sec[^"]*"[^>]*>.*?</section>', re.S)


def split_body(html: str) -> tuple[str, str, str, str]:
    """Return (head, preamble, sections-joined, tail) where the body is `<div class="abody">` … `</div>` before </main>."""
    i = html.index('<div class="abody">')
    j = html.index("\n      </main>")
    inner = html[i + len('<div class="abody">'): j]
    assert inner.endswith("</div>"), "abody must end with </div>"
    inner = inner[: -len("</div>")]
    return html[:i], inner, "", html[j:]


def rebuild(path: Path, order: list, *, extra: dict | None = None, drop_kept: bool = False) -> str:
    html = path.read_text(encoding="utf-8")
    head, inner, _, tail = split_body(html)
    sections = SEC_RE.findall(inner)
    preamble = SEC_RE.sub("", inner).strip().replace('<div class="zgrid2"></div>', "")
    kept = {}
    for s in sections:
        if 'data-gen="r2"' in s:
            continue
        m = re.search(r"<h2>(.*?)</h2>", s, re.S)
        kept[m.group(1)] = s
    out = []
    def kept_section(title: str) -> str:
        s = kept.pop(title)
        if 'class="zcase"' not in s:
            s = s.replace('<span class="grow"></span><span class="cap">', f'<span class="grow"></span>{CASE_VE}<span class="cap">', 1)
        return s

    for item in order:
        if callable(item):
            out.append(item())
        elif isinstance(item, tuple):  # ("grid", title, title): two kept sections side by side
            out.append('<div class="zgrid2">' + "".join(kept_section(t) for t in item[1:]) + "</div>")
        else:
            out.append(kept_section(item))
    assert drop_kept or not kept, f"{path.name}: kept sections not placed: {list(kept)}"
    body = "".join(out)
    # renumber
    n = [0]

    def num(m):
        n[0] += 1
        return f'<span class="num">{n[0]:02d}</span>'

    body = re.sub(r'<span class="num">\d\d</span>', num, body)
    html = head + '<div class="abody">' + (preamble if preamble else "") + body + "</div>" + tail
    if "/*r2*/" not in html:
        html = html.replace("</style>", EXTRA_CSS + "</style>", 1)
    for k, v in (extra or {}).items():
        if v in html:  # applied by an earlier run
            continue
        assert k in html, f"{path.name}: not found: {k[:60]}"
        html = html.replace(k, v, 1)
    return html


TABS_OLD = '<a href="KM10Market.dc.html">Trh</a></nav>'
TABS_NEW = '<a href="KM10Market.dc.html">Trh</a><a href="KM12Schedule.dc.html">Harmonogram</a></nav>'
TABS_NEW_ON = '<a href="KM10Market.dc.html">Trh</a><a href="KM12Schedule.dc.html" class="on" aria-current="page">Harmonogram</a></nav>'


def build_m3() -> None:
    path = ROOT / "KM3Model.dc.html"
    html = rebuild(
        path,
        ["Varianty", m3_timeline, "Hybné veličiny a časování", "Položky modelu", m3_items_cv, "Výsledek v základním scénáři", m3_base_vs_futures, "Varianty struktury modelu", "Kdy výpočet stačí", m3_extra_runs],
        extra={
            # the baseline named as such on B's card
            '<b>B</b></span><h3>Zůstat u 3PL CZ</h3>': '<b>B</b><span class="grow"></span><span class="zg calc">základ pro srovnání</span></span><h3>Zůstat u 3PL CZ</h3>',
            # same seed, same bytes in the stopping rule
            'Víc losů zmenší jen numerický šum.': 'Stejné semínko (20261030), stejné bajty: opakovaný běh dává týž soubor výsledků. Víc losů zmenší jen numerický šum.',
            'na to jsou varianty struktury (05)': 'na to jsou varianty struktury (08)',
        },
    )
    path.write_text(html, encoding="utf-8")


def build_m4() -> None:
    path = ROOT / "KM4Results.dc.html"
    html = rebuild(
        path,
        [
            "Doporučení podle pravidla", rule_table_8, rule_table_other, boundary,
            ("grid", "Rozdíl C2 − B ve 20 000 budoucnostech", "Co výsledek otáčí"), delays, hiring,
            tornado, ("grid", "Bod zvratu", "Předpověď objednávek, ověřená zpětně"), breakeven, post2035, correlation,
            "Hodnota informace podle pravidla", voi, enquiry,
            "Přechod na B2: posouzení",
        ],
        extra={TABS_OLD: TABS_NEW},
    )
    # ✓/✗ on Velis's rule table: the three conditions against their thresholds
    html = velis_rule_marks(html)
    path.write_text(html, encoding="utf-8")


def velis_rule_marks(html: str) -> str:
    """Put ✔/✘ beside each condition's value in Velis's own rule table (P(lepší) ≥ 0,80, P(ztráta) ≤ 0,10, slib)."""
    m = re.search(r'(<section class="sec"><div class="sh"><span class="num">\d\d</span><h2>Doporučení podle pravidla</h2>.*?</section>)', html, re.S)
    sec = m.group(1)
    if "✔" in sec:
        return html
    new = sec

    def row(mm):
        r = mm.group(0)
        cells = re.findall(r"<td[^>]*>.*?</td>", r, re.S)
        if len(cells) < 7:
            return r
        vals = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        better = float(vals[3].replace(",", "."))
        loss = float(vals[4].replace(",", "."))
        promise = "drží" in vals[5]
        cells[3] = cells[3].replace("</td>", f" {mark(better >= 0.80)}</td>")
        cells[4] = cells[4].replace("</td>", f" {mark(loss <= 0.10)}</td>")
        cells[5] = cells[5].replace("</td>", f" {mark(promise)}</td>")
        return "<tr>" + "".join(cells) + "</tr>"

    new = re.sub(r"<tr>(?:<td.*?</td>)+</tr>", row, new, flags=re.S)
    return html.replace(sec, new, 1)


def build_m4b() -> None:
    path = ROOT / "KM7Finance.dc.html"
    html = rebuild(
        path,
        ["Business case: investice, NPV, IRR, návratnost", t4, t5, incentives, "Peněžní tok C2 proti dnešku po letech", "Ceny pro bod zvratu", "Cenová elasticita a cena dopravy"],
        extra={TABS_OLD: TABS_NEW},
    )
    path.write_text(html, encoding="utf-8")


def build_m4d() -> None:
    path = ROOT / "KM9Operations.dc.html"
    html = rebuild(
        path,
        ["Předpověď objednávek po měsících proti kapacitě", "Optimální plán za daných omezení", "Zásoby", t6_section],
        extra={
            TABS_OLD: TABS_NEW,
            '<a class="btn primary sm" href="KM10Market.dc.html">Trh<i class="ph ph-caret-right s"></i></a>': '<a class="btn primary sm" href="KM12Schedule.dc.html">Harmonogram<i class="ph ph-caret-right s"></i></a>',
            '<a href="KM11Logistics.dc.html">Logistika<i class="ph ph-caret-right s"></i></a></div>': '<a href="KM12Schedule.dc.html">Harmonogram<i class="ph ph-caret-right s"></i></a></div>',
        },
    )
    path.write_text(html, encoding="utf-8")


def build_m4g() -> None:
    """A new board from KM9's frame."""
    src = (ROOT / "KM9Operations.dc.html").read_text(encoding="utf-8")
    dst = ROOT / "KM12Schedule.dc.html"
    html = src
    if dst.exists():  # keep the board's own measured height
        m_h = re.search(r'"\$preview":\{"width":1440,"height":(\d+)', dst.read_text(encoding="utf-8"))
        html = re.sub(r'("\$preview":\{"width":1440,"height":)\d+', rf"\g<1>{m_h.group(1)}", html)
    rep = {
        "<title>Model – Výsledky: Provoz</title>": "<title>Model – Výsledky: Harmonogram</title>",
        '<main class="art" aria-label="Výsledky · Provoz">': '<main class="art" aria-label="Výsledky · Harmonogram">',
        "<h1>Výsledky · Provoz</h1>": "<h1>Výsledky · Harmonogram</h1>",
        '<span class="pill you"><span class="stg sm youq" aria-hidden="true"><i class="ph ph-exclamation-mark"></i></span>kapacita ve špičce</span>': '<span class="pill you"><span class="stg sm youq" aria-hidden="true"><i class="ph ph-exclamation-mark"></i></span>termín drží jen Wendelstedt</span>',
        '<a class="btn primary sm" href="KM12Schedule.dc.html">Harmonogram<i class="ph ph-caret-right s"></i></a>': '<a class="btn primary sm" href="KM11Logistics.dc.html">Logistika<i class="ph ph-caret-right s"></i></a>',
        '<a href="KM9Operations.dc.html" class="on" aria-current="page">Provoz</a>': '<a href="KM9Operations.dc.html">Provoz</a>',
        TABS_NEW: TABS_NEW_ON,
        "Vidí: Výsledky": "Vidí: Výsledky · Harmonogram",
        '<a href="KM8Accounting.dc.html"><i class="ph ph-caret-left s"></i>Účetnictví</a>': '<a href="KM9Operations.dc.html"><i class="ph ph-caret-left s"></i>Provoz</a>',
        "<b>M4d Provoz</b>": "<b>M4g Harmonogram</b>",
        '<a href="KM12Schedule.dc.html">Harmonogram<i class="ph ph-caret-right s"></i></a></div>': '<a href="KM11Logistics.dc.html">Logistika<i class="ph ph-caret-right s"></i></a></div>',
    }
    for k, v in rep.items():
        if v in html:
            continue
        assert k in html, f"KM12: frame text not found: {k[:70]}"
        html = html.replace(k, v, 1)
    # Ada's conversation
    m = re.search(r'(<div class="conv">)(.*?)(\n  </div>\n  <div class="cfdock">)', html, re.S)
    conv = (
        '\n<div class="day">8. 11.</div><div class="reply"><span class="lav" aria-hidden="true"><i class="ph ph-sparkle"></i></span><div class="body"><div class="who"><b>Ada</b>09:40</div>'
        "<p>Harmonogram čte totéž losování jako Rozhodnutí: start výroby každé lokality proti 1. 7. 2030. Tři nejlevnější lokality mají v mediánu půlroční rezervu, ale jejich chvost sahá za termín; nad prahem 0,80 je jen Wendelstedt.</p></div></div>"
        '<div class="me">Co ten chvost dělá?</div><div class="reply"><span class="lav" aria-hidden="true"><i class="ph ph-sparkle"></i></span><div class="body"><div class="who"><b>Ada</b>09:41</div>'
        "<p>Kompenzační opatření, kde je úřad uloží: 9–18 měsíců navíc ve 20 % budoucností. U Eschfeldu most, u Lindenau povolení vypouštění, u Odrzyce pozemky pro vlečku. Odklad a nábor se k tomu sčítají po měsících.</p></div></div>"
    )
    html = html[: m.start(2)] + conv + html[m.end(2):]
    dst.write_text(html, encoding="utf-8")
    html = rebuild(dst, [schedule_section, tail_drivers, delay_hiring_table, velis_schedule_note], drop_kept=True)
    dst.write_text(html, encoding="utf-8")


PARK_LINE = '<div class="zpark"><i class="ph ph-pause-circle"></i>Odloženo pro MVP r2 (8. 11. 2026): zpráva typu 2 tuto kartu nepotřebuje; návrh zůstává, nic se tu nestaví.</div>'


def park(name: str) -> None:
    path = ROOT / name
    html = path.read_text(encoding="utf-8")
    if 'class="zpark"' in html:
        return
    anchor = 'aria-current="page">' + {"KM8Accounting.dc.html": "Účetnictví", "KM10Market.dc.html": "Trh"}[name] + "</a>"
    i = html.index(anchor)
    j = html.index("</nav>", i) + len("</nav>")
    html = html[:j] + PARK_LINE + html[j:]
    html = html.replace("</style>", ".zpark{display:flex;align-items:center;gap:10px;padding:8px 24px;background:var(--sunken);border-bottom:1px solid var(--border);font-size:12.5px;color:var(--muted)}\n</style>", 1)
    path.write_text(html, encoding="utf-8")


def set_heights(heights: dict[str, int]) -> None:
    cj_path = ROOT / "canvas.json"
    cj = json.loads(cj_path.read_text(encoding="utf-8"))
    if "KM12Schedule.dc.html" not in cj["boards"]:
        cj["boards"]["KM12Schedule.dc.html"] = {"h": 1600, "is_interactive": True, "title": "M4g · Výsledky: Harmonogram", "w": 1440, "x": 10640, "y": 29600}
        order = cj["order"]
        order.insert(order.index("KM10Market.dc.html") + 1, "KM12Schedule.dc.html")
        cj["notes"]["t9"]["maxW"] = 12080
    for name, h in heights.items():
        cj["boards"][name]["h"] = h
        path = ROOT / name
        html = path.read_text(encoding="utf-8")
        html = re.sub(r'("\$preview":\{"width":1440,"height":)\d+', rf"\g<1>{h}", html)
        path.write_text(html, encoding="utf-8")
    cj_path.write_text(json.dumps(cj, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- check against the exemplar

def check() -> int:
    text = EXEMPLAR.read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", text)
    missing = []

    def need(s: str) -> None:
        if s not in flat:
            missing.append(s)

    for rate, rows in RULE.items():
        for (med, lo, hi, beat, loss, tm, inv) in rows:
            need(cz(med))
            need(cz(hi))
            need(cz(inv))
    for _, pick, pts, meds in BOUNDARY:
        need(" / ".join(p3(x) for x in pts))
        need(" / ".join(cz(x) for x in meds))
    for m, vals in DELAY:
        for v in vals:
            need(p3(v))
    for name, vals, _ in POST2035:
        for v in vals:
            need(cz(v))
    for _, _, vals in BREAKEVEN:
        for v in vals:
            need(v)
    for site, pre, post, medpost, irr, pay, inv, start in T4:
        for v in (*pre, *post, medpost):
            need(cz(v))
        need(irr)
        need(start)
    for site, items, total, pr, pct in T5:
        need(cz(total))
        for part in pct.split(" / "):  # the text wraps one row of T5 across lines
            need(part)
    for site, vals, total in T6:
        need(cz(total, 0))
    for what, v, _ in VOI_RULE:
        need(cz(v))
    for what, v in EVPPI:
        need(cz(v))
    for m, vals in HIRING.items():
        if m:
            for v in vals:
                need(p3(v))
    for a, b, lo, li, hi, *_ in LOGISTICS_INPUTS:
        for v in (lo, li, hi):
            need(v)
    for s in missing:
        print("not in the exemplar:", s)
    print(f"check: {len(missing)} missing")
    return 1 if missing else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:
        sys.exit(check())
    if sys.argv[1:2] == ["heights"]:
        set_heights(json.loads(sys.argv[2]))
        sys.exit(0)
    build_m3()
    build_m4()
    build_m4b()
    build_m4d()
    build_m4g()
    build_m4f()
    park("KM8Accounting.dc.html")
    park("KM10Market.dc.html")
    set_heights({})
    print("built")
