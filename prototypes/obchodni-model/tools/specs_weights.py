"""The weighting-scenario map (MV9): two specs, ChemVitro and Velis, after MVP-SCOPE.md § 3 and § 4.

A perspective is a set of components of the decision; a component is one measure per option with a
source, a grade, a direction and a declared value scale (the worst and the best anchor, 0 and 10,
linear between them, clipped outside). Each component says whether the model's saving already holds
its mechanism (role "part": v modelu), whether it restates the saving itself (role "saving"), or
whether the model leaves it out (role "outside": mimo model). A component the documents do not give
per option keeps a range of values, never a single number; one that does not apply to an option is
null and takes no weight there. Gates are not components. A row that is the same for every site, or
informational, is listed and not scored.

Two scenario families keep one mechanism counted once (the overlap check, § 4 line 6):
  a  the saving against what the model leaves out: roles saving + outside;
  b  the parts of the saving against each other, without the saving itself: roles part + outside.
A scenario is a named weight vector over the perspectives with its family; the admitted components of
a perspective share its weight equally. A vector over every component that weights the saving and one
of its parts is refused by name and offered the two families.

ChemVitro's numbers come from report 2's tables (T1, T4, T5, T6, T8, T9) and chapters 4, 6 and 9.
Velis reuses the indicator spec (spec_options.json) and its scored cells. The scenario weights are
illustrative: in a study the decision owner and the client's people compose them, and the approval
ledger records who and when, before the results.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from compute import score_cell  # noqa: E402

# ---------------- ChemVitro: eight sites ----------------
SITES = ["VR", "LI", "KA", "WE", "LN", "ES", "OD", "BO"]
SITE_NAMES = {"VR": "Vrbice", "LI": "Lipová", "KA": "Kamenec", "WE": "Wendelstedt", "LN": "Lindenau",
              "ES": "Eschfeld", "OD": "Odrzyca", "BO": "Bory"}
CZ, DE, PL = ["VR", "LI", "KA"], ["WE", "LN", "ES"], ["OD", "BO"]


def vals(xs):
    return dict(zip(SITES, xs))


def comp(code, name, unit, source, grade, role, anchors, values, **more):
    return {"code": code, "name": name, "unit": unit, "source": source, "grade": grade, "role": role,
            "anchors": anchors, "values": values, **more}


def info(name, text, source=None, grade=None):
    """A row shown and not scored: the same for every site, informational, or not applicable."""
    return {"info": True, "name": name, "text": text, "source": source, "grade": grade}


chemvitro = {
    "case": "ChemVitro",
    "decision": "Vlastní závod na VTX-40: která z osmi lokalit",
    "objects": [{"id": s, "name": SITE_NAMES[s]} for s in SITES],
    "owner_scenario": "FR_A",
    "families": {
        "a": {"name": "Úspora proti tomu, co model nepočítá", "roles": ["saving", "outside"]},
        "b": {"name": "Části úspory proti sobě, bez úspory samé", "roles": ["part", "outside"]},
    },
    "perspectives": [
        {"code": "F", "name": "Finanční", "components": [
            comp("F1", "Medián úspory proti nákupu", "mil. EUR, NPV 2027–2044 při 8 %", "T1", "odhad", "saving",
                 [60, 140], vals([110.8, 126.0, 132.4, 82.3, 86.5, 61.2, 134.7, 123.2])),
            comp("F2", "Investice v základním případě", "mil. EUR", "T5", "výpočet", "part",
                 [180, 140], vals([160.6, 158.6, 152.3, 171.8, 170.8, 175.5, 148.9, 143.9]), gate="G4"),
            comp("F3", "P(investice ≤ 175 mil. EUR)", "podíl budoucností", "T5", "odhad", "part",
                 [0.4, 1.0], vals([0.79, 0.82, 0.90, 0.56, 0.57, 0.50, 0.92, 0.92])),
            comp("F4", "IRR", "%", "T4", "výpočet", "saving", [12, 22], vals([18.2, 19.2, 19.9, 14.8, 15.5, 14.4, 20.5, 20.1])),
            comp("F5", "Rok návratnosti", "rok", "T4", "výpočet", "saving", [2037, 2033], vals([2035, 2034, 2034, 2035, 2035, 2036, 2034, 2035])),
            comp("F6", "NPV po zdanění při 8 %", "mil. EUR, základní případ", "T4", "výpočet", "saving",
                 [60, 130], vals([96.6, 116.3, 121.3, 84.3, 92.4, 69.3, 118.6, 99.7]), state="daň je pevný parametr; sazby prozatímní"),
            info("Pobídky: daňová úleva (CZ, PL) nebo dotace (DE), podíl a P(schválení) 0,5",
                 "informační: CZ 20–25 %, Odrzyca 35 %, Bory 50 %, Wendelstedt 15 %, Lindenau 20 %, Eschfeld 0; v základním případě nezapočteno, ve výhledu po zdanění ano",
                 "R2-P10, T9", "z dat klienta · právní předpis · úsudek"),
        ]},
        {"code": "S", "name": "Strategická", "components": [
            comp("S1", "Společné selhání s vedoucí lokalitou (Odrzyca)", "podíl budoucností, v nichž je horší než nákup i tato lokalita", "T8, R2-P12", "odhad", "outside",
                 [1.0, 0.7], vals([0.90, 0.84, 0.79, 0.98, 0.97, 0.99, None, 0.91]), state="Odrzyca je vedoucí lokalita sama: neuplatní se"),
            info("Závislost na jednom dodavateli · přirážka při prodloužení 12–22 % · podmínky po roce 2035 · zůstatková hodnota 30 %",
                 "stejné pro všechny lokality: páky nákupu proti vlastní výrobě, ne rozdíly mezi lokalitami", "R2-P03 §2.4, R2-P08 §7.2, T9", "z dat klienta · úsudek"),
            info("Tržní pozice", "neuplatní se: závod zásobuje jen Brno (62 %) a Pardubice (38 %)"),
        ]},
        {"code": "P", "name": "Provozní", "components": [
            comp("P1", "Energie na tunu 2032", "EUR/t", "T6", "výpočet", "part", [200, 170], vals([179, 179, 179, 182, 190, 190, 192, 192])),
            comp("P2", "Údržba, pojištění a poplatek parku na tunu 2032", "EUR/t", "T6", "výpočet", "part", [160, 100], vals([113, 124, 111, 157, 132, 122, 105, 103])),
            comp("P3", "Odpad a voda na tunu 2032", "EUR/t", "T6", "výpočet", "part", [50, 35], vals([43, 45, 42, 38, 47, 48, 39, 37])),
            info("Provozní náklad na tunu 2032 celkem", "součet položek (P1–P3, L1, H1, suroviny 760 a CO₂ 56): 1 311 · 1 300 · 1 295 · 1 455 · 1 434 · 1 463 · 1 292 · 1 290 EUR/t; kreslí se po položkách, aby se mechanismus nepočítal dvakrát", "T6", "výpočet"),
            info("Najíždění 60–90 % v prvním půlroce", "stejné pro všechny lokality", "T9", "úsudek"),
        ]},
        {"code": "M", "name": "Marketingová a obchodní",
         "note": "Pro ChemVitro prázdná: vázaná poptávka, žádný slib zákazníkům. Pro Velis ústřední (slib doručení, doba doručení, růst poptávky).",
         "components": []},
        {"code": "L", "name": "Logistická", "components": [
            comp("L1", "Doprava produktu do Brna a Pardubic", "EUR/t", "T6", "výpočet", "part", [60, 15], vals([38, 20, 24, 58, 53, 55, 37, 33])),
            comp("L2", "Vlečka k postavení: 3,4 km × 1,9–2,8 mil. EUR/km", "mil. EUR", "T5, T9", "z dat klienta · odhad", "part",
                 [8, 0], vals([0, 0, 0, 0, 0, 0, [6.5, 9.5], 0]), state="Odrzyca: cena za km je rozpětí; získání pozemků 6–24 měsíců (úsudek)"),
            comp("L3", "Silniční přístup: zesílení mostu (nosnost 16 t proti 40 t)", "mil. EUR", "T5, T9", "z dat klienta", "part",
                 [6, 0], vals([0, 0, 0, 0, 0, [3.2, 5.0], 0, 0]), state="Eschfeld: 3,2–5,0 mil. EUR, základní případ 4,1"),
            comp("L4", "Doprava surovin přes překladiště do stavby vlečky", "EUR/t surovin navíc", "T9", "úsudek", "part",
                 [40, 0], vals([0, 0, 0, 0, 0, 0, [10, 40], 0]), state="Odrzyca: žádná nabídka, úsudek 10–40"),
        ]},
        {"code": "E", "name": "Prostředí a povolování", "components": [
            comp("E1", "Šance na kompenzační opatření (stanice nad limitem memoranda)", "podíl", "R2-P05, T9", "z dat klienta · úsudek", "part",
                 [1, 0], vals([0.8, 0.2, 0.2, 0, 0, 0, 0.2, 0.8]), state="rozhodující vstup modelu; bez dokladu o konkrétní lokalitě", gate="G3"),
            comp("E2", "Prodloužení povolování s kompenzací", "měsíce", "T9", "z dat klienta", "part",
                 [18, 0], {**{s: [9, 15] for s in CZ}, **{s: 0 for s in DE}, **{s: [12, 18] for s in PL}}, state="Česko 9–15, Polsko 12–18, Německo bez kompenzace"),
            comp("E3", "Předčištění odpadních vod", "mil. EUR", "T5, T9", "z dat klienta · odhad", "part",
                 [15, 0], vals([0, [6.7, 14.1], 0, 0, [6.7, 14.1], 0, 0, 0]), state="Lipová a Lindenau: 6,7–14,1 ze srovnatelných závodů, základní případ 10"),
            info("Poplatek chemického parku (Wendelstedt 1,1 mil. EUR ročně)", "uvnitř P2, údržba a park (T6): počítá se jednou, tady ne podruhé", "T9", "z dat klienta"),
            info("Emise CO₂ a EU ETS", "stejné pro všechny lokality: 56 EUR/t", "T6", "výpočet"),
        ]},
        {"code": "H", "name": "Lidé", "components": [
            comp("H1", "Náklady na zaměstnance na tunu 2032", "EUR/t", "T6, T9", "výpočet · právní předpis (prozatímní)", "part",
                 [250, 90], vals([121, 116, 124, 203, 195, 232, 102, 109])),
            comp("H2", "Doba obsazení místa operátora", "dny", "R2-P07 §6.2, Trh práce v regionech", "z dat klienta", "outside",
                 [120, 40], {s: ([49, 71] if s != "ES" else 118) for s in SITES}, state="jen zátěžová zkouška modelu; zpráva uvádí Eschfeld a rozpětí ostatních regionů"),
            comp("H3", "Velký nábor v okolí do roku 2028", "lidí", "Trh práce v regionech, kap. 13", "z dat klienta", "outside",
                 [400, 0], vals([0, 0, 380, 0, 0, 0, 0, [0, 380]]), state="Kamenec 380; u Borů zpráva nábor jmenuje bez čísla: rozsah"),
            info("Růst mezd po roce 2031", "stejné pro všechny lokality", "T9", "úsudek"),
        ]},
    ],
    # The CFO's rule as written on 2. 11. 2026: four conditions, every one a gate, none a component. T1 at 8 %.
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
    "composed": "ilustrační, 8. 11. 2026; ve studii zapsáno do schvalovací knihy před výsledky",
    "scenarios": [
        # the owner's vector over every component: the overlap check refuses it
        {"code": "FR_ALL", "name": "FŘ, jak zadáno", "who": "finanční ředitelka", "family": None, "weights": {"F": 0.5, "P": 0.3, "L": 0.2}},
        {"code": "FR_A", "name": "FŘ · a", "who": "finanční ředitelka (vlastník pravidla)", "family": "a", "weights": {"F": 0.6, "S": 0.2, "H": 0.2}},
        {"code": "EQ_A", "name": "Rovné váhy · a", "who": "každá perspektiva rodiny stejně", "family": "a", "weights": {"F": 1, "S": 1, "H": 1}},
        {"code": "VR_B", "name": "VŘ · b", "who": "výrobní ředitel", "family": "b", "weights": {"P": 0.4, "H": 0.2, "L": 0.2, "F": 0.2}},
        {"code": "LOG_B", "name": "LOG · b", "who": "vedoucí logistiky (zadání: logistika 0,3 · provoz 0,5 · finance 0,2)", "family": "b", "weights": {"L": 0.3, "P": 0.5, "F": 0.2}},
        {"code": "EHS_B", "name": "EHS · b", "who": "vedoucí EHS", "family": "b", "weights": {"E": 0.5, "L": 0.3, "F": 0.2}},
        {"code": "EQ_B", "name": "Rovné váhy · b", "who": "každá perspektiva rodiny stejně", "family": "b", "weights": {"F": 1, "P": 1, "L": 1, "E": 1, "H": 1}},
    ],
    "fan": {"concentration": 60, "draws": 300, "seed": 20261108},
}

# ---------------- Velis: the seven options, from the indicator spec ----------------
so = json.load(open(os.path.join(HERE, "spec_options.json")))
IND = {i["code"]: (c, i) for c in so["categories"] for i in c["indicators"]}
ROLE = {"E1": "saving", "R1": "saving", "P2": "outside", "D1": "outside", "F1": "outside", "T1": "outside", "F2": "outside"}
PERSP = {  # which indicator serves which perspective
    "F": ("Finanční", ["E1", "R1", "P2"], None),
    "S": ("Strategická", ["D1", "F1"], None),
    "P": ("Provozní", ["T1"], None),
    "M": ("Marketingová a obchodní", [], "Slib doručení do 1 dne ve velkých městech je brána G1 (doba doručení 1 den, C 2 dny) a nekompenzuje se; růst poptávky je pro všechny stejný: skórovaná součást není."),
    "L": ("Logistická", ["F2"], None),
    "E": ("Prostředí a povolování", [], "Pro Velis prázdná: sklad ani 3PL povolení nepotřebují."),
    "H": ("Lidé", [], "Růst mezd je předpoklad Modelu, uvnitř E1 (překryv P1 vypuštěn v SI1)."),
}
GRADE = {"pásmo": "výpočet", "slovní": "úsudek", "přímo": "jmenovaní hodnotitelé", "checklist": "doklad"}


def velis_component(code):
    cat, ind = IND[code]
    cells = {o: score_cell(ind, ind["values"][o]) for o in ind["values"]}
    values = {o: (x["lo"] if x["lo"] == x["hi"] else [x["lo"], x["hi"]]) for o, x in cells.items()}
    unknown = [o for o, x in cells.items() if x["state"] == "unknown"]
    return comp(code, ind["name"], "skóre 1–10 podle pravidla SI1", ind["from"], GRADE[ind["kind"]], ROLE[code], [1, 10], values,
                **({"overlap": ind["contains"]} if ind.get("contains") else {}),
                **({"state": "neznámo u " + ", ".join(unknown) + ": rozsah skóre"} if unknown else {}))


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
    "families": {"a": {"name": "Úspora proti tomu, co model nepočítá", "roles": ["saving", "outside"]}},
    "perspectives": [
        {"code": p, "name": name, **({"note": note} if note else {}), "components": [velis_component(c) for c in codes]}
        for p, (name, codes, note) in PERSP.items()
    ],
    "gates": [{"code": g["code"], "name": g["name"], "source": g["from"], "values": g["values"]} for g in so["gates"]],
    "gate_settings": [{"code": "dnes", "name": "Brány podle dokladů", "override": {}}],
    "composed": "swing weighting ze SI1, schváleno FR 4. 11. před prvním skóre; rovné váhy ilustrační",
    "scenarios": [
        {"code": k, "name": k, "who": so["stakeholders"][k], "family": "a", "weights": velis_weights(pts)}
        for k, pts in so["swing"].items()
    ] + [{"code": "EQ", "name": "Rovné váhy", "who": "každá neprázdná perspektiva stejně", "family": "a", "weights": {"F": 1, "S": 1, "P": 1, "L": 1}}],
    "fan": {"concentration": 60, "draws": 300, "seed": 20261108},
}

json.dump(chemvitro, open(os.path.join(HERE, "spec_scenarios_chemvitro.json"), "w"), ensure_ascii=False, indent=1)
json.dump(velis, open(os.path.join(HERE, "spec_scenarios_velis.json"), "w"), ensure_ascii=False, indent=1)
print("chemvitro scored components", sum(1 for p in chemvitro["perspectives"] for c in p["components"] if not c.get("info")))
