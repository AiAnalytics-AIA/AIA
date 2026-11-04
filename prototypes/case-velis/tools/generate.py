"""Generate the Velis case pack's data files (fictional, seeded, reproducible).

Run from the repo root:  python prototypes/case-velis/tools/generate.py
Writes prototypes/case-velis/data/*.xlsx and *.csv. Same seed, same bytes.

Every number here is fictional. The totals reconcile with the business-model canvas
(prototypes/obchodni-model/, boards KM1 and KM2): 410 000 orders in 2025, 300 Kč contribution per
order before logistics, 23,7 mil. Kč of 3PL invoices, EBITDA 27,3 mil. Kč, net debt −4 mil. Kč.
The behavioural files (delays, shipping price, survey, experts) have effects planted on purpose;
CASE.md says which, so a study can be checked against what was planted.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
import re
import zipfile
from pathlib import Path

import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

SEED = 20261104
OUT = Path(__file__).resolve().parents[1] / "data"
FIXED_TIME = dt.datetime(2026, 11, 4, 9, 0, 0)

rng = np.random.default_rng(SEED)

KRAJE = [  # (kraj, share of customers, big-city share inside the kraj)
    ("Hlavní město Praha", 0.205, 1.0),
    ("Jihomoravský", 0.118, 0.52),
    ("Středočeský", 0.122, 0.0),
    ("Moravskoslezský", 0.105, 0.38),
    ("Ústecký", 0.067, 0.0),
    ("Plzeňský", 0.055, 0.45),
    ("Olomoucký", 0.054, 0.0),
    ("Jihočeský", 0.055, 0.0),
    ("Zlínský", 0.050, 0.0),
    ("Královéhradecký", 0.047, 0.0),
    ("Liberecký", 0.040, 0.0),
    ("Pardubický", 0.045, 0.0),
    ("Vysočina", 0.044, 0.0),
    ("Karlovarský", 0.023, 0.0),
]
_W = np.array([k[1] for k in KRAJE])
KRAJ_P = _W / _W.sum()


def save_xlsx(
    name: str, sheets: dict[str, list[list]], notes: dict[str, str] | None = None
) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for r in rows:
            ws.append(r)
        for c in ws[1]:
            c.font = Font(bold=True)
        for i, col in enumerate(ws.columns, 1):
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
        if notes and title in notes:
            ws.cell(row=ws.max_row + 2, column=1, value=notes[title])
    wb.properties.creator = "Velis Commerce s.r.o. (fiktivní)"
    wb.properties.created = FIXED_TIME
    wb.properties.modified = FIXED_TIME
    path = OUT / name
    wb.save(path)
    _fix_zip_times(path)


def _fix_zip_times(path: Path) -> None:
    """Rewrite the XLSX zip with fixed timestamps so the bytes are reproducible."""
    data = []
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            data.append((info.filename, z.read(info.filename)))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in sorted(data):
            if name == "docProps/core.xml":  # openpyxl stamps the save time; pin it
                blob = re.sub(
                    rb"<dcterms:(created|modified)([^>]*)>[^<]*</dcterms:\1>",
                    rb"<dcterms:\1\2>2026-11-04T09:00:00Z</dcterms:\1>",
                    blob,
                )
            zi = zipfile.ZipInfo(name, date_time=(2026, 11, 4, 9, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, blob)


def save_csv(name: str, header: list[str], rows: list[list]) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- orders, monthly 2023-2025
SEASON = np.array([0.86, 0.74, 0.90, 0.95, 1.00, 0.92, 0.84, 0.88, 1.00, 1.06, 1.42, 1.23])
YEAR_TOTAL = {2023: 345_000, 2024: 376_100, 2025: 410_000}
AOV = {2023: 1390, 2024: 1420, 2025: 1450}  # average order value, Kč without VAT
RETURNS = {2023: 0.214, 2024: 0.219, 2025: 0.222}


def monthly(year: int) -> list[int]:
    s = SEASON.copy()
    if year == 2025:
        s[10] = 1.58  # Black Friday 2025: the planted outlier (KM1 data check)
    noise = rng.normal(1.0, 0.025, 12)
    w = s * noise
    vals = w / w.sum() * YEAR_TOTAL[year]
    vals = np.round(vals).astype(int)
    vals[-1] += YEAR_TOTAL[year] - vals.sum()
    return vals.tolist()


orders = {y: monthly(y) for y in YEAR_TOTAL}
REVENUE = {2023: 479.6e6, 2024: 534.1e6, 2025: 594.5e6}  # equals the P&L
rows = [
    [
        "Měsíc",
        "Objednávky",
        "Tržby bez DPH (Kč)",
        "Průměrná objednávka (Kč)",
        "Vrácené objednávky",
        "Podíl vratek",
    ]
]
for y in YEAR_TOTAL:
    aovs = [
        AOV[y] * float(rng.normal(1.0, 0.012)) * (1.06 if m in (10, 11) else 1.0) for m in range(12)
    ]
    rev = [orders[y][m] * aovs[m] for m in range(12)]
    k = REVENUE[y] / sum(rev)
    rev = [int(round(r * k)) for r in rev]
    rev[-1] += int(REVENUE[y]) - sum(rev)
    for m in range(12):
        n = orders[y][m]
        ret = int(round(n * RETURNS[y] * float(rng.normal(1.0, 0.04))))
        rows.append([f"{y}-{m + 1:02d}", n, rev[m], int(round(rev[m] / n)), ret, round(ret / n, 3)])
regions = [["Kraj", "Velké město v kraji", "Objednávky 2025", "Podíl"]]
reg_counts = rng.multinomial(YEAR_TOTAL[2025], KRAJ_P)
for (k, _, city), c in zip(KRAJE, reg_counts):
    regions.append([k, "ano" if city > 0 else "ne", int(c), round(int(c) / YEAR_TOTAL[2025], 3)])
save_xlsx(
    "objednavky_2023-2025.xlsx",
    {"Měsíce": rows, "Kraje 2025": regions},
    {
        "Měsíce": "Zdroj: e-shop Velis, export z objednávkového systému. Tržby bez DPH, po slevách, před vratkami."
    },
)

# ---------------------------------------------------------------- P&L, balance sheet, plan
pl = [
    ["Položka (mil. Kč, není-li uvedeno jinak)", "2023", "2024", "2025", "Plán 2025"],
    ["Objednávky (tis.)", 345.0, 376.1, 410.0, 400.0],
    ["Tržby bez DPH", 479.6, 534.1, 594.5, 580.0],
    ["Náklady na prodané zboží", -276.1, -309.0, -344.8, -336.4],
    ["Vratky, platby a poplatky tržišť", -103.45, -114.15, -126.7, -123.6],
    ["Příspěvek před logistikou", 100.05, 110.95, 123.0, 120.0],
    ["Logistika (faktury 3PL CZ)", -18.8, -21.1, -23.6, -23.0],
    ["Marketing", -28.5, -31.0, -34.0, -33.0],
    ["Osobní náklady", -22.0, -24.0, -26.5, -26.5],
    ["Ostatní režie", -9.9, -10.6, -11.6, -11.5],
    ["EBITDA", 20.85, 24.25, 27.3, 26.0],
    ["Odpisy", -2.6, -2.9, -3.1, -3.1],
    ["EBIT", 18.25, 21.35, 24.2, 22.9],
    ["Příspěvek na objednávku před logistikou (Kč)", 290, 295, 300, 300],
    ["Nákladové úroky", -0.6, -0.5, -0.4, -0.4],
    ["Zisk před zdaněním", 17.65, 20.85, 23.8, 22.5],
    ["Daň z příjmů", -3.71, -4.38, -5.0, -4.7],
    ["Čistý zisk", 13.94, 16.47, 18.8, 17.8],
]
bs = [
    ["Rozvaha k 31. 12. (mil. Kč)", "2023", "2024", "2025"],
    ["Dlouhodobý majetek", 13.5, 12.8, 12.0],
    ["Zásoby", 55.0, 61.0, 68.0],
    ["Pohledávky", 7.8, 8.6, 9.5],
    ["Peníze", 18.4, 24.1, 31.0],
    ["Aktiva celkem", 94.7, 106.5, 120.5],
    ["Vlastní kapitál", 47.9, 59.7, 72.5],
    ["Bankovní úvěry", 31.0, 29.0, 27.0],
    ["Krátkodobé závazky", 15.8, 17.8, 21.0],
    ["Pasiva celkem", 94.7, 106.5, 120.5],
]
save_xlsx(
    "vysledovka_rozvaha_2023-2025.xlsx",
    {"Výsledovka": pl, "Rozvaha": bs},
    {
        "Výsledovka": "Řádek 14: příspěvek na objednávku před logistikou = příspěvek před logistikou / objednávky. "
        "Logistika = faktury 3PL CZ (poplatek za objednávku + skladné). Plán 2025 schválen v prosinci 2024."
    },
)

# ---------------------------------------------------------------- 3PL CZ invoices 2025
inv = []
fee = 46.0
for m in range(12):
    invoiced = int(
        round(orders[2025][m] * 0.996)
    )  # cancellations before dispatch: the planted 0,4 %
    inv.append(
        [
            f"2025-{m + 1:02d}",
            f"FV-3PLCZ-2025-{m + 1:03d}",
            invoiced,
            f"{fee:.2f}".replace(".", ","),
            int(round(invoiced * fee)),
            400_000,
            int(round(invoiced * fee)) + 400_000,
        ]
    )
save_csv(
    "faktury_3PL_CZ_2025.csv",
    [
        "mesic",
        "cislo_faktury",
        "expedovane_objednavky",
        "poplatek_za_objednavku_kc",
        "poplatky_kc",
        "skladne_kc",
        "celkem_bez_dph_kc",
    ],
    inv,
)

# ---------------------------------------------------------------- customers summary 2025 (no personal data)
CUST = 128_000
age = [["Věková skupina", "Zákazníci", "Podíl"]]
for band, p in [("18–24", 0.17), ("25–34", 0.29), ("35–44", 0.24), ("45–54", 0.17), ("55+", 0.13)]:
    age.append([band, int(round(CUST * p)), p])
city = [["Bydliště", "Zákazníci", "Podíl", "Objednávky 2025", "Podíl objednávek"]]
city.append(["Velká města (Praha, Brno, Ostrava, Plzeň)", 48_640, 0.38, 164_000, 0.40])
city.append(["Ostatní", 79_360, 0.62, 246_000, 0.60])
freq = [["Četnost nákupů 2025", "Zákazníci", "Podíl", "Průměr objednávek na zákazníka"]]
for band, p, mean in [
    ("1 objednávka", 0.46, 1.0),
    ("2–3 objednávky", 0.33, 2.4),
    ("4 a více", 0.21, 9.3),
]:
    freq.append([band, int(round(CUST * p)), p, mean])
save_xlsx(
    "zakaznici_souhrn_2025.xlsx",
    {"Věk": age, "Bydliště": city, "Četnost": freq},
    {"Věk": "Souhrn z CRM k 31. 12. 2025. Bez osobních údajů."},
)

# ---------------------------------------------------------------- delays December 2024 (matched groups, 90 days)
# Planted: delayed customers place 3,9 % fewer orders in 90 days; 55 % of the loss is in big cities.
N = 6200
LOSS_CITY, LOSS_OTHER = 0.0564, 0.0283
LAMBDA = {"1": 0.62, "2–3": 1.55, "4+": 3.40}
FREQ_P = [0.46, 0.33, 0.21]


def delay_block(r: np.random.Generator) -> list[list]:
    out = []
    cid = 1
    for group in ("zpozdeno", "kontrola"):
        for _ in range(N):
            kraj_i = int(r.choice(len(KRAJE), p=KRAJ_P))
            kraj, _, city_share = KRAJE[kraj_i]
            big = bool(r.random() < city_share)
            band = ["1", "2–3", "4+"][int(r.choice(3, p=FREQ_P))]
            lam = LAMBDA[band]
            days = 0
            if group == "zpozdeno":
                days = 1 if r.random() < 0.82 else 2
                lam *= 1 - (LOSS_CITY if big else LOSS_OTHER)
            n90 = int(r.poisson(lam))
            rev = int(round(sum(r.normal(1450, 380) for _ in range(n90)))) if n90 else 0
            d = dt.date(2024, 12, 1) + dt.timedelta(days=int(r.integers(0, 20)))
            out.append(
                [
                    f"Z{cid:06d}",
                    f"zakaznik{cid:05d}@example.com",
                    group,
                    d.isoformat(),
                    kraj,
                    "ano" if big else "ne",
                    band,
                    days,
                    n90,
                    rev,
                ]
            )
            cid += 1
    return out


def realised(rows: list[list]) -> tuple[float, float]:
    """Overall relative loss and the big-city share of the lost orders, as a study would measure them."""

    def mean(g: str, c: str | None = None) -> tuple[float, int]:
        xs = [x[8] for x in rows if x[2] == g and (c is None or x[5] == c)]
        return sum(xs) / len(xs), len(xs)

    md, _ = mean("zpozdeno")
    mc, _ = mean("kontrola")
    lost = {}
    for c in ("ano", "ne"):
        a, na = mean("zpozdeno", c)
        b, _ = mean("kontrola", c)
        lost[c] = (b - a) * na
    total = lost["ano"] + lost["ne"]
    return 1 - md / mc, (lost["ano"] / total if total > 0 else float("nan"))


# Poisson noise at n = 6 200 per group is about ±1,5 pp, so the block takes the first sub-seed whose
# realised effect sits on the planted one: loss within 0,3 pp of 3,9 %, city share 48-62 %.
for k in range(2000):
    delay_rows = delay_block(np.random.default_rng([SEED, 1, k]))
    loss, share = realised(delay_rows)
    if abs(loss - 0.039) < 0.003 and 0.48 < share < 0.62:
        DELAY_SUBSEED = k
        break
else:
    raise SystemExit("no sub-seed reproduces the planted delay effect")
# planted quality issues: 1 % duplicated rows, 0,5 % missing kraj
dups = [
    delay_rows[int(i)]
    for i in rng.choice(len(delay_rows), size=int(0.01 * len(delay_rows)), replace=False)
]
for r in delay_rows:
    if rng.random() < 0.005:
        r[4] = ""
delay_rows += [list(r) for r in dups]
order = rng.permutation(len(delay_rows))
delay_rows = [delay_rows[int(i)] for i in order]
save_xlsx(
    "zpozdeni_2024.xlsx",
    {
        "Zásilky": [
            [
                "id_zakaznika",
                "email",
                "skupina",
                "datum_objednavky",
                "kraj",
                "velke_mesto",
                "cetnost_nakupu_2024",
                "zpozdeni_dni",
                "objednavky_90_dni",
                "trzby_90_dni_kc",
            ]
        ]
        + delay_rows
    },
    {
        "Zásilky": "Zpožděné zásilky z prosince 2024 (výpadek dopravce) a stejně velká kontrolní skupina vybraná podle měsíce, kraje a četnosti nákupů. Sledováno 90 dní."
    },
)

# ---------------------------------------------------------------- shipping price change 2024 (weekly)
ship = [["Týden od", "Cena dopravy (Kč)", "Objednávky", "Předpověď bez změny ceny"]]
start = dt.date(2024, 3, 4)
for w in range(26):
    d = start + dt.timedelta(weeks=w)
    base = 6900 * (1 + 0.0017 * w) * (1 + 0.06 * math.sin(2 * math.pi * (w + 2) / 26))
    price = 79 if d >= dt.date(2024, 6, 3) else 69
    actual = base * (1 - 0.051 if price == 79 else 1.0) * float(rng.normal(1.0, 0.018))
    ship.append([d.isoformat(), price, int(round(actual)), int(round(base))])
save_xlsx(
    "objednavky_doprava_2024.xlsx",
    {"Týdny": ship},
    {
        "Týdny": "Cena dopravy zvýšena z 69 na 79 Kč od 3. 6. 2024. Předpověď: model marketingu z března 2024."
    },
)

# ---------------------------------------------------------------- transition plan
plan = [
    [
        "Položka přechodu k jinému 3PL",
        "Min (mil. Kč)",
        "Nejspíš (mil. Kč)",
        "Max (mil. Kč)",
        "Poznámka",
    ],
    ["Souběh dvou skladů (2 měsíce)", 1.4, 2.1, 3.2, "nájem a personál u obou"],
    ["Převoz zásob", 0.9, 1.4, 2.0, "kamionová doprava, pojištění"],
    ["Napojení systémů (WMS, e-shop)", 0.6, 0.9, 1.4, "integrace API, testy"],
    ["Zaškolení a řízení přechodu", 0.4, 0.6, 0.9, "vlastní lidé, 3 měsíce"],
    ["Rezerva", 0.7, 1.0, 1.5, "ztráty a poškození"],
    ["Celkem", 4.0, 6.0, 9.0, "součet se zaokrouhlením"],
]
save_xlsx(
    "plan_prechodu.xlsx", {"Souhrn": plan}, {"Souhrn": "Odhad vedoucího logistiky, říjen 2026."}
)

# ---------------------------------------------------------------- expert ratings (expert map)
EXPERTS = [
    ("FR", "finanční ředitel"),
    ("OR", "obchodní ředitelka"),
    ("VL", "vedoucí logistiky"),
    ("VN", "vedoucí nákupu"),
    ("MK", "vedoucí marketingu"),
]
OPTIONS = ["A", "A2", "B", "B2", "C", "C2", "H"]
CRITERIA = [
    "Náklady",
    "Riziko dodavatele",
    "Služba zákazníkům",
    "Kapacita a růst",
    "Kapitálová náročnost",
]
BASE = {  # 10 = best for the company on that criterion
    "A": [6, 8, 8, 8, 2],
    "A2": [6, 8, 8, 7, 4],
    "B": [4, 6, 8, 5, 9],
    "B2": [5, 7, 8, 5, 9],
    "C": [8, 5, 3, 7, 9],
    "C2": [7, 5, 7, 7, 8],
    "H": [6, 5, 7, 6, 8],
}
BIAS = {  # planted disagreement: the head of logistics distrusts the Polish supplier; marketing weighs service
    "VL": {("C", 1): -3, ("C2", 1): -3, ("H", 1): -2},
    "FR": {("C", 1): +1, ("C2", 1): +1},
    "MK": {("C", 2): -1, ("C2", 2): +1},
}
exp_rows = []
for code, role in EXPERTS:
    for o in OPTIONS:
        for ci, c in enumerate(CRITERIA):
            v = BASE[o][ci] + BIAS.get(code, {}).get((o, ci), 0) + int(rng.integers(-1, 2))
            v = int(min(10, max(1, v)))
            exp_rows.append([code, role, o, c, v])
# one missing score, on purpose (a missing score stays missing)
exp_rows[37][4] = ""
save_csv(
    "hodnoceni_expertu.csv", ["hodnotitel", "role", "moznost", "kriterium", "skore_1_10"], exp_rows
)

# ---------------------------------------------------------------- customer survey (study type 3)
OBJECTS = [
    ("O1", "Doručení druhý den"),
    ("O2", "Doručení do 2 pracovních dnů"),
    ("O3", "Doručení do 3 pracovních dnů"),
    ("O4", "Expresní doručení ve velkých městech"),
    ("O5", "Doprava za 79 Kč"),
    ("O6", "Doprava za 59 Kč, o den delší"),
    ("O7", "Výdejní box nebo výdejní místo"),
    ("O8", "Doprava zdarma nad 1 500 Kč"),
]
SEGMENTS = {  # latent, not in the file: mean attractiveness 1-10 per object
    "rychli": (0.30, [9.2, 6.8, 3.4, 8.8, 5.2, 3.0, 5.0, 6.5], 0.42),
    "cenovi": (0.35, [6.2, 6.8, 5.6, 3.8, 3.2, 8.4, 7.4, 8.6], 0.12),
    "pohodlni": (0.20, [7.0, 6.9, 4.6, 5.0, 4.6, 5.8, 9.0, 7.0], 0.25),
    "lhostejni": (0.15, [6.0, 6.4, 5.4, 5.0, 5.4, 5.9, 6.0, 6.6], 0.30),
}
seg_names = list(SEGMENTS)
seg_p = np.array([SEGMENTS[s][0] for s in seg_names])
sv = []
for i in range(800):
    seg = seg_names[int(rng.choice(4, p=seg_p))]
    _, means, city_bias = SEGMENTS[seg]
    big = bool(rng.random() < min(0.95, 0.30 + city_bias))
    kraj = (
        "Hlavní město Praha"
        if big and rng.random() < 0.55
        else KRAJE[int(rng.choice(len(KRAJE), p=KRAJ_P))][0]
    )
    agep = [0.30, 0.38, 0.18, 0.09, 0.05] if seg == "rychli" else [0.13, 0.26, 0.26, 0.20, 0.15]
    ageb = ["18–24", "25–34", "35–44", "45–54", "55+"][int(rng.choice(5, p=agep))]
    band = ["1", "2–3", "4+"][int(rng.choice(3, p=[0.40, 0.36, 0.24]))]
    ratings = [int(min(10, max(1, round(rng.normal(m, 1.3))))) for m in means]
    if rng.random() < 0.02:
        ratings[int(rng.integers(0, 8))] = ""  # item non-response
    reorder = int(
        min(
            5,
            max(
                1,
                round(
                    rng.normal(
                        {"rychli": 3.1, "cenovi": 4.3, "pohodlni": 3.9, "lhostejni": 4.4}[seg], 0.8
                    )
                ),
            ),
        )
    )
    wtp = int(
        max(
            0,
            round(rng.normal({"rychli": 39, "cenovi": 6, "pohodlni": 14, "lhostejni": 10}[seg], 9)),
        )
    )
    sv.append([f"R{i + 1:04d}", ageb, kraj, "ano" if big else "ne", band, *ratings, reorder, wtp])
save_csv(
    "pruzkum_zakazniku_2026.csv",
    [
        "id_respondenta",
        "vek",
        "kraj",
        "velke_mesto",
        "cetnost_nakupu",
        *[f"{o}_atraktivita" for o, _ in OBJECTS],
        "q_zpozdeni_objednal_znovu_1_5",
        "q_priplatek_za_druhy_den_kc",
    ],
    sv,
)

print(
    "written to",
    OUT,
    "· delay sub-seed",
    DELAY_SUBSEED,
    "· realised loss %.4f, big-city share %.3f" % realised([r for r in delay_rows if r[0]]),
)
for p in sorted(OUT.iterdir()):
    print(f"  {p.name:38s} {p.stat().st_size:>9,d} B")
