"""The weighting-scenario map (MV9): two specs, ChemVitro and Velis.

A perspective is a set of components of the decision; a component is one measure per option with
a source, a direction and a declared value scale (the worst and the best anchor, 0 and 10, linear
between them, clipped outside). A component the documents do not give per option keeps a range
of values, never a single number. A perspective with no component for the case stays empty and
says why. A scenario is a named weight vector over the perspectives; the components of one
perspective share its weight equally, so a perspective counts once however many components it
has (the overlap check: components that read the same model result are named, not weighted
twice).

ChemVitro's numbers come from report 2's tables (T1, T4, T5, T6), chapter 4 (the compensation
chance), chapter 6 (hiring) and chapter 9 (incentives), and the named site ratings in the case
pack (hodnoceni_lokalit.csv, read from git). Velis reuses the indicator spec (spec_options.json)
and its scored cells. The scenario weights are illustrative: in a study the decision owner and
the client's people compose them.
"""
import json
import os
import statistics as st
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compute import score_cell  # noqa: E402

# ---------------- ChemVitro: eight sites ----------------
SITES = ["VR", "LI", "KA", "WE", "LN", "ES", "OD", "BO"]
SITE_NAMES = {"VR": "Vrbice", "LI": "Lipová", "KA": "Kamenec", "WE": "Wendelstedt", "LN": "Lindenau",
              "ES": "Eschfeld", "OD": "Odrzyca", "BO": "Bory"}
CASE_CODES = {"CZ1": "VR", "CZ2": "LI", "CZ3": "KA", "DE1": "WE", "DE2": "LN", "DE3": "ES", "PL1": "OD", "PL2": "BO"}


def vals(xs):
    return dict(zip(SITES, xs))


def site_ratings(criterion):
    """The named raters' mean score per site for one criterion of hodnoceni_lokalit.csv (1–10, 10 best)."""
    text = subprocess.run(["git", "show", "origin/chore/case-chemvitro:prototypes/case-chemvitro/data/hodnoceni_lokalit.csv"],
                          cwd=HERE, capture_output=True, text=True, check=True).stdout
    rows = [r.split(";") for r in text.strip().splitlines()[1:]]
    out, raters = {}, set()
    for hodnotitel, _role, code, krit, score, *_ in rows:
        if krit == criterion and score:
            out.setdefault(CASE_CODES[code], []).append(int(score))
            raters.add(hodnotitel)
    return {k: round(st.mean(v), 2) for k, v in out.items()}, len(raters)


risk_rating, n_raters = site_ratings("Rizika lokality")
labour_rating, _ = site_ratings("Pracovní síla")

chemvitro = {
    "case": "ChemVitro",
    "decision": "Vlastní závod na VTX-40: která z osmi lokalit",
    "objects": [{"id": s, "name": SITE_NAMES[s]} for s in SITES],
    "owner_scenario": "FR",
    "perspectives": [
        {"code": "F", "name": "Finanční", "components": [
            {"code": "F1", "name": "Medián úspory proti nákupu", "unit": "mil. EUR, NPV 8 %", "source": "T1", "grade": "odhad",
             "anchors": [60, 140], "values": vals([110.8, 126.0, 132.4, 82.3, 86.5, 61.2, 134.7, 123.2])},
            {"code": "F2", "name": "Investice v základním případě", "unit": "mil. EUR", "source": "T5", "grade": "výpočet",
             "anchors": [180, 140], "values": vals([160.6, 158.6, 152.3, 171.8, 170.8, 175.5, 148.9, 143.9])},
            {"code": "F3", "name": "IRR", "unit": "%", "source": "T4", "grade": "výpočet",
             "anchors": [12, 22], "values": vals([18.2, 19.2, 19.9, 14.8, 15.5, 14.4, 20.5, 20.1]),
             "overlap": "týž výpočet jako F1 (NPV nákladů na zásobování)"},
            {"code": "F4", "name": "Návratnost", "unit": "rok", "source": "T4", "grade": "výpočet",
             "anchors": [2037, 2033], "values": vals([2035, 2034, 2034, 2035, 2035, 2036, 2034, 2035]),
             "overlap": "týž výpočet jako F1"},
            {"code": "F5", "name": "Medián úspory po zdanění", "unit": "mil. EUR, 8 %", "source": "T4", "grade": "odhad",
             "state": "prozatímní: daňové sazby čekají na ověření",
             "anchors": [40, 110], "values": vals([87.5, 99.9, 107.3, 72.1, 80.0, 45.9, 107.2, 96.0])},
            {"code": "F6", "name": "P(ztráta > 20 mil. EUR)", "unit": "podíl budoucností", "source": "T1", "grade": "odhad",
             "anchors": [0.25, 0.0], "values": vals([0.08, 0.06, 0.05, 0.15, 0.14, 0.21, 0.05, 0.06])},
        ]},
        {"code": "S", "name": "Strategická",
         "note": "Závislost na dodavateli, vratnost a podmínky po roce 2035 jsou pro všech osm lokalit stejné: nerozlišují, nevstupují.",
         "components": [
            {"code": "S1", "name": "Pobídky: nejvyšší uváděná podpora", "unit": "% investice", "source": "Nabídky lokalit s. 1–8; kap. 9",
             "grade": "z dat klienta", "state": "prozatímní: schvaluje úřad; v základním případě nezapočteno; české nabídky uvádějí 20–25 % bez rozlišení lokalit",
             "anchors": [0, 50], "values": {"VR": [20, 25], "LI": [20, 25], "KA": [20, 25], "WE": 15, "LN": 20, "ES": 0, "OD": 35, "BO": 50}},
            {"code": "S2", "name": "Rizika lokality podle vedení", "unit": f"průměr 1–10, {n_raters} hodnotitelů", "source": "hodnoceni_lokalit.csv",
             "grade": "jmenovaní hodnotitelé", "state": "úsudek lidí klienta, ne doklad",
             "anchors": [1, 10], "values": risk_rating},
        ]},
        {"code": "P", "name": "Provozní", "components": [
            {"code": "P1", "name": "Provozní náklad na tunu v roce 2032", "unit": "EUR/t", "source": "T6", "grade": "výpočet",
             "anchors": [1500, 1250], "values": vals([1311, 1300, 1295, 1455, 1434, 1463, 1292, 1290]),
             "overlap": "provoz je uvnitř F1; zde jako samostatný pohled provozu"},
            {"code": "P2", "name": "Doba obsazení místa operátora", "unit": "dny", "source": "Trh práce v regionech; kap. 6.2", "grade": "z dat klienta",
             "state": "zpráva uvádí jen Eschfeld a rozpětí ostatních regionů: rozsah",
             "anchors": [120, 40], "values": {s: ([49, 71] if s != "ES" else 118) for s in SITES}},
        ]},
        {"code": "M", "name": "Marketingová a obchodní",
         "note": "Pro ChemVitro prázdná: závod zásobuje jen vlastní závody v Brně a Pardubicích, poptávka není otázkou.",
         "components": []},
        {"code": "L", "name": "Logistická", "components": [
            {"code": "L1", "name": "Doprava produktu do Brna a Pardubic", "unit": "EUR/t", "source": "T6", "grade": "výpočet",
             "anchors": [60, 15], "values": vals([38, 20, 24, 58, 53, 55, 37, 33])},
            {"code": "L2", "name": "Infrastruktura mimo areál, kterou lokalita vyžaduje", "unit": "mil. EUR", "source": "T5 (most, vlečka)", "grade": "výpočet",
             "anchors": [8, 0], "values": vals([0, 0, 0, 0, 0, 4.1, 6.8, 0])},
        ]},
        {"code": "E", "name": "Prostředí a povolování",
         "note": "Emise a odpady jsou dány návrhem procesu, na všech lokalitách stejné: nevstupují.",
         "components": [
            {"code": "E1", "name": "P(výroba k 1. 7. 2030)", "unit": "podíl budoucností", "source": "T1", "grade": "odhad",
             "anchors": [0, 1], "values": vals([0.21, 0.76, 0.76, 0.94, 0.77, 0.67, 0.75, 0.19])},
            {"code": "E2", "name": "Šance na kompenzační opatření", "unit": "podíl", "source": "kap. 4", "grade": "úsudek",
             "state": "bez dokladu o konkrétní lokalitě; rozhoduje o bráně termínu",
             "anchors": [1, 0], "values": vals([0.8, 0.2, 0.2, 0, 0, 0, 0.2, 0.8])},
            {"code": "E3", "name": "Předčištění odpadních vod", "unit": "mil. EUR", "source": "T5", "grade": "výpočet",
             "anchors": [15, 0], "values": vals([0, 10.0, 0, 0, 10.0, 0, 0, 0])},
        ]},
        {"code": "H", "name": "Lidé", "components": [
            {"code": "H1", "name": "Náklady na zaměstnance", "unit": "EUR/t", "source": "T6", "grade": "výpočet",
             "anchors": [250, 90], "values": vals([121, 116, 124, 203, 195, 232, 102, 109]),
             "overlap": "položka P1"},
            {"code": "H2", "name": "Pracovní síla podle vedení", "unit": f"průměr 1–10, {n_raters} hodnotitelů", "source": "hodnoceni_lokalit.csv",
             "grade": "jmenovaní hodnotitelé", "state": "úsudek lidí klienta, ne doklad",
             "anchors": [1, 10], "values": labour_rating},
        ]},
    ],
    # The CFO's rule as written on 2. 11. 2026: four conditions, every one a gate. T1 at 8 %.
    "gates": [
        {"code": "G1", "name": "Porazí nákup s pravděpodobností ≥ 0,75", "source": "T1",
         "values": vals([["pass", "0,88"], ["pass", "0,91"], ["pass", "0,92"], ["pass", "0,80"], ["pass", "0,81"], ["fail", "0,73"], ["pass", "0,92"], ["pass", "0,91"]])},
        {"code": "G2", "name": "Ztráta > 20 mil. EUR nejvýš v 10 % budoucností", "source": "T1",
         "values": vals([["pass", "0,08"], ["pass", "0,06"], ["pass", "0,05"], ["fail", "0,15"], ["fail", "0,14"], ["fail", "0,21"], ["pass", "0,05"], ["pass", "0,06"]])},
        {"code": "G3", "name": "Výroba k 1. 7. 2030 s pravděpodobností ≥ 0,80", "source": "T1",
         "values": vals([["fail", "0,21"], ["fail", "0,76"], ["fail", "0,76"], ["pass", "0,94"], ["fail", "0,77"], ["fail", "0,67"], ["fail", "0,75"], ["fail", "0,19"]])},
        {"code": "G4", "name": "Investice nejvýš 175 mil. EUR (základní případ)", "source": "T5",
         "values": vals([["pass", "160,6"], ["pass", "158,6"], ["pass", "152,3"], ["pass", "171,8"], ["pass", "170,8"], ["fail", "175,5"], ["pass", "148,9"], ["pass", "143,9"]])},
    ],
    "gate_settings": [
        {"code": "dnes", "name": "Pravidlo dnes (šance na kompenzaci 20 %)", "override": {}},
        {"code": "urady", "name": "Po písemném stanovisku úřadů: bez kompenzace (0 %)", "source": "kap. 5.3 a 6.1",
         "override": {"G3": {"LI": ["pass", "0,942"], "KA": ["pass", "0,942"], "OD": ["pass", "0,942"]}}},
    ],
    "scenarios": [
        {"code": "FR", "name": "FŘ", "who": "finanční ředitelka (vlastník pravidla)", "weights": {"F": 0.5, "E": 0.3, "P": 0.1, "L": 0.1}},
        {"code": "VR", "name": "VŘ", "who": "výrobní ředitel", "weights": {"P": 0.4, "H": 0.2, "L": 0.2, "F": 0.2}},
        {"code": "LOG", "name": "LOG", "who": "vedoucí logistiky (zadání: logistika 0,3 · provoz 0,5 · finance 0,2)", "weights": {"L": 0.3, "P": 0.5, "F": 0.2}},
        {"code": "EHS", "name": "EHS", "who": "vedoucí EHS", "weights": {"E": 0.5, "F": 0.3, "S": 0.2}},
        {"code": "EQ", "name": "Rovné váhy", "who": "každá neprázdná perspektiva stejně", "weights": {"F": 1, "S": 1, "P": 1, "L": 1, "E": 1, "H": 1}},
    ],
    "fan": {"concentration": 60, "draws": 300, "seed": 20261108},
}

# ---------------- Velis: the seven options, from the indicator spec ----------------
so = json.load(open(os.path.join(HERE, "spec_options.json")))
IND = {i["code"]: (c, i) for c in so["categories"] for i in c["indicators"]}
PERSP = {  # which indicator serves which perspective
    "F": ("Finanční", ["E1", "R1", "P2"], None),
    "S": ("Strategická", ["D1", "F1"], None),
    "P": ("Provozní", ["T1"], None),
    "M": ("Marketingová a obchodní", [], "Slib doručení do 1 dne ve velkých městech je brána G1 a nekompenzuje se; skórovaná součást není."),
    "L": ("Logistická", ["F2"], None),
    "E": ("Prostředí a povolování", [], "Pro Velis prázdná: sklad ani 3PL povolení nepotřebují."),
    "H": ("Lidé", [], "Růst mezd je předpoklad Modelu, uvnitř E1 (překryv P1 vypuštěn v SI1)."),
}
GRADE = {"pásmo": "výpočet", "slovní": "úsudek", "přímo": "jmenovaní hodnotitelé", "checklist": "doklad"}


def velis_component(code):
    cat, ind = IND[code]
    cells = {o: score_cell(ind, ind["values"][o]) for o in ind["values"]}
    values = {}
    for o, x in cells.items():
        values[o] = x["lo"] if x["lo"] == x["hi"] else [x["lo"], x["hi"]]
    unknown = [o for o, x in cells.items() if x["state"] == "unknown"]
    return {"code": code, "name": ind["name"], "unit": "skóre 1–10 podle pravidla SI1", "source": ind["from"],
            "grade": GRADE[ind["kind"]], "anchors": [1, 10], "values": values,
            **({"overlap": ind["contains"]} if ind.get("contains") else {}),
            **({"state": "neznámo u " + ", ".join(unknown) + ": rozsah skóre"} if unknown else {})}


def velis_weights(points):
    w = {}
    for cat in so["categories"]:
        for p, (_, codes, _) in PERSP.items():
            if any(i["code"] in codes for i in cat["indicators"]):
                w[p] = w.get(p, 0) + points[cat["code"]]
    return w


velis = {
    "case": "Velis Commerce",
    "decision": "Strategie skladu a logistiky 2026–2032: sedm možností",
    "objects": [{"id": o["id"], "name": o["name"]} for o in so["objects"]],
    "owner_scenario": "FR",
    "perspectives": [
        {"code": p, "name": name, **({"note": note} if note else {}), "components": [velis_component(c) for c in codes]}
        for p, (name, codes, note) in PERSP.items()
    ],
    "gates": [{"code": g["code"], "name": g["name"], "source": g["from"], "values": g["values"]} for g in so["gates"]],
    "gate_settings": [{"code": "dnes", "name": "Brány podle dokladů", "override": {}}],
    "scenarios": [
        {"code": k, "name": k, "who": so["stakeholders"][k] + " (swing weighting, SI1)", "weights": velis_weights(pts)}
        for k, pts in so["swing"].items()
    ] + [{"code": "EQ", "name": "Rovné váhy", "who": "každá neprázdná perspektiva stejně", "weights": {"F": 1, "S": 1, "P": 1, "L": 1}}],
    "fan": {"concentration": 60, "draws": 300, "seed": 20261108},
}

json.dump(chemvitro, open(os.path.join(HERE, "spec_weights_chemvitro.json"), "w"), ensure_ascii=False, indent=1)
json.dump(velis, open(os.path.join(HERE, "spec_weights_velis.json"), "w"), ensure_ascii=False, indent=1)
print("site ratings", risk_rating, labour_rating, n_raters)
