"""The two indicator maps of the Velis case, method v2 (the external review of 5 Nov 2026).

What changed from v1, and why:
- Four evidence states per cell, no universal scoring of missing data: known (a value with its
  source), unknown (no evidence: the cell keeps the range of scores it could take), not applicable
  (the indicator does not apply to the object; its weight goes to the object's other criteria),
  and, for checklists, each item met, evidenced absent or unknown. v1's rules 3-6 (median for a
  missing number, an undocumented service as not offered, an undisclosed price rise as the median,
  no reported outage = 8) are gone.
- Non-compensable requirements are gates, not scores: an option that fails one is out, and one
  whose gate is unknown cannot be recommended until the evidence is in, whatever it scores.
- No double counting: an indicator whose mechanism the model's NPV already contains is dropped
  (counted once, in E1); the expert ratings cover criteria scored elsewhere and are a cross-check.
- Weights by swing weighting (each stakeholder rates the swing from the worst to the best option
  on each criterion, the largest swing = 100), approved by the decision owner; each value scale
  approved with it.
- Every number the map reads from the model is the model's own (KM4 Výsledky): v1 read other
  medians and loss probabilities than the results board showed.
"""
import csv
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
INF = 1e9
V, S, N = "Vysoká", "Střední", "Nízká"


def K(v, cert, src):
    return {"state": "known", "v": v, "cert": cert, "src": src}


def U(why):
    return {"state": "unknown", "src": why}


def NA(why):
    return {"state": "na", "src": why}


def CL(items, cert, src):
    """A checklist cell: one letter per item, y met, n evidenced absent, ? unknown."""
    return {"state": "checklist", "v": items, "cert": cert, "src": src}


# ---------------- Map 1: the seven options ----------------
objs = ["A", "A2", "B", "B2", "C", "C2", "H"]
names = {"A": "A · Hala", "A2": "A2 · Hala po etapách", "B": "B · 3PL CZ", "B2": "B2 · 3PL CZ pevná cena",
         "C": "C · 3PL PL", "C2": "C2 · 3PL PL + expres", "H": "H · Hybrid"}


def row(vals, cert, src):
    out = {}
    for o, v in zip(objs, vals):
        c = cert.get(o) if isinstance(cert, dict) else cert
        s = src.get(o) if isinstance(src, dict) else src
        out[o] = v if isinstance(v, dict) else K(v, c, s)
    return out


# The experts' table, read as it is: one empty cell stays empty (no median).
EXPERTS = {}
with open(os.path.join(HERE, "..", "..", "case-velis", "data", "hodnoceni_expertu.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if r["skore_1_10"]:
            EXPERTS.setdefault(r["moznost"], {}).setdefault(r["kriterium"], []).append(int(r["skore_1_10"]))

options = {
    "objects": [{"id": o, "name": names[o]} for o in objs],
    "crossings": [["E", "C2", "B2"]],
    "flip": [1, 1],
    "owner": "FR",
    "stakeholders": {"FR": "finanční ředitel (vlastník rozhodnutí)", "OR": "obchodní ředitelka", "VL": "vedoucí logistiky"},
    "gates": [
        {"code": "G1", "name": "Slib ve velkých městech: doručení do 1 pracovního dne", "from": "Zadání · podmínka OR",
         "values": {"A": ["pass", "úsudek: vlastní expedice z Jihlavy (ověří MV8)"], "A2": ["pass", "úsudek, jako A"],
                    "B": ["pass", "smlouva s. 3"], "B2": ["pass", "smlouva s. 3"], "C": ["fail", "nabidka_3PL_PL s. 3: 2 dny"],
                    "C2": ["pass", "nabidka_kuryr_expres s. 1"], "H": ["pass", "města z CZ, smlouva s. 3"]}},
        {"code": "G2", "name": "Investice nejvýš 90 mil. Kč", "from": "Zadání · strop FR",
         "values": {"A": ["pass", "70 mil., nabidka_hala s. 1"], "A2": ["pass", "77 mil., s. 2"], "B": ["pass", "0"], "B2": ["pass", "0"],
                    "C": ["pass", "0"], "C2": ["pass", "0"], "H": ["pass", "0"]}},
    ],
    "swing": {  # points for the swing from the worst to the best option on each criterion
        "FR": {"E": 100, "R": 50, "V": 35, "D": 30, "K": 25, "P": 15, "T": 10},
        "OR": {"E": 70, "R": 30, "V": 30, "D": 40, "K": 60, "P": 10, "T": 20},
        "VL": {"E": 60, "R": 25, "V": 40, "D": 60, "K": 50, "P": 15, "T": 30},
    },
    "categories": [
        {"code": "E", "name": "Ekonomika", "why": "cíl FR: nejvyšší příspěvek za 7 let", "indicators": [
            {"code": "E1", "name": "Medián NPV proti B (mil. Kč, 8 %)", "kind": "pásmo", "from": "Výsledky (M4)",
             "rule": "< 0 → 2 · < 1 → 4 · < 3 → 5 · < 5 → 6 · < 7 → 8 · ≥ 7 → 10",
             "cuts": [(-0.001, 2), (0.999, 4), (2.999, 5), (4.999, 6), (6.999, 8), (INF, 10)],
             "contains": "investici, přechod, ztrátu objednávek ze zpoždění, indexaci cen, mzdy a daň",
             "values": row([2.6, 3.7, 0.0, 5.6, 3.4, 7.3, 0.3], V, "M4 Výsledky · medián z 20 000 budoucností")},
        ]},
        {"code": "R", "name": "Riziko ztráty", "why": "limit FR: ztráta > 10 mil. nejvýš v 1 z 10", "indicators": [
            {"code": "R1", "name": "P(ztráta > 10 mil. Kč proti B) (% budoucností)", "kind": "pásmo", "from": "Výsledky (M4)",
             "rule": "≤ 1 → 10 · ≤ 3 → 8 · ≤ 5 → 6 · ≤ 10 → 3 · > 10 → 1",
             "cuts": [(1, 10), (3, 8), (5, 6), (10, 3), (INF, 1)],
             "contains": "stejný model jako E1, jiná vlastnost: chvost, ne medián",
             "values": row([4, 3, 0, 0, 4, 0, 1], V, "M4 Výsledky")},
        ]},
        {"code": "D", "name": "Závislost na dodavateli (Porter)", "why": "síla dodavatele: jediný 3PL", "indicators": [
            {"code": "D1", "name": "Závislost na jednom dodavateli", "kind": "slovní", "from": "Rešerše · Porter",
             "rule": "vlastní + záloha 8 · dva dodavatelé 7 · jeden s pevnou cenou 5 · jeden 4 · dva noví 3",
             "contains": "mimo model: vyjednávací síla, ne cena",
             "values": row([8, 8, 4, 5, 4, 3, 7], S, "Porter: síla dodavatelů (úsudek)")},
        ]},
        {"code": "P", "name": "Kurzové riziko (PESTEL E)", "why": "fakturace v EUR, model počítá v Kč", "indicators": [
            {"code": "P2", "name": "Měna nákladu", "kind": "slovní", "from": "Rešerše · PESTEL E",
             "rule": "vše v Kč 9 · část v EUR 7 · fakturace v EUR 5",
             "contains": "mimo model: kurz v Modelu není",
             "values": row([9, 9, 9, 9, 5, 5, 7], V, {"A": "Kč", "A2": "Kč", "B": "smlouva: Kč", "B2": "Kč", "C": "nabidka_3PL_PL s. 1: EUR", "C2": "EUR", "H": "polovina v EUR"})},
        ]},
        {"code": "V", "name": "Vratnost rozhodnutí", "why": "růst 4–14 % ročně je nejistý", "indicators": [
            {"code": "F1", "name": "Jak rychle se dá rozhodnutí změnit", "kind": "slovní", "from": "Rešerše · PESTEL L",
             "rule": "výpověď 6 měs. 9 · výpověď 12 měs. 6 · část smlouvy na 7 let 4 · 7 let, výstup po 3. roce 3 · vlastní hala 2",
             "contains": "mimo model: Model počítá jeden průběh na 7 let",
             "values": row([2, 3, 9, 6, 3, 3, 4], V, {"A": "nabidka_hala s. 6", "A2": "druhá etapa se dá odložit", "B": "smlouva s. 8", "B2": "dodatek: 12 měsíců", "C": "nabidka_3PL_PL s. 7", "C2": "s. 7", "H": "PL část s. 7"})},
        ]},
        {"code": "K", "name": "Kapacitní rezerva 2032", "why": "potřeba 750 tis. objednávek při 9 % ročně", "indicators": [
            {"code": "F2", "name": "Kapacita na rok 2032 (podíl potřeby)", "kind": "pásmo", "from": "Data · Předpoklady",
             "rule": "≥ 1,2 → 10 · ≥ 1,0 → 8 · ≥ 0,9 → 6 · ≥ 0,8 → 4 · < 0,8 → 2",
             "cuts": [(0.7999, 2), (0.8999, 4), (0.9999, 6), (1.1999, 8), (INF, 10)],
             "contains": "částečně v E1 (přetečení k 3PL); zde rezerva pro růst nad 9 %",
             "values": row([0.83, 0.83, U("3PL CZ limit nehlásí · dotaz odeslán 4. 11."), U("jako B"), 1.12, 1.12, 1.3],
                           {"A": V, "A2": V, "C": V, "C2": V, "H": S},
                           {"A": "nabidka_hala s. 3: 620 tis.", "A2": "s. 3", "C": "s. 4: 70 tis. měsíčně", "C2": "s. 4", "H": "dva sklady"})},
        ]},
        {"code": "T", "name": "Realizace", "why": "rozhoduje se do 15. 12. 2026", "indicators": [
            {"code": "T1", "name": "Začátek nového stavu", "kind": "slovní", "from": "Zadání · dokumenty",
             "rule": "hned 10 · 1. 1. 2027 9 · 1. 7. 2027 7 · 1. 1. 2028 5",
             "contains": "mimo model jako termín; náklad čekání je v E1",
             "values": row([5, 5, 10, 9, 7, 7, 7], V, "CASE §8: kdy která možnost začne")},
        ]},
    ],
    # v1's indicators that are not scored any more, and why: the overlap check
    "removed": [
        {"code": "E2", "name": "Podíl budoucností, kde je nejlepší", "to": "vypuštěno", "why": "stejný model a stejné budoucnosti jako E1 a R1"},
        {"code": "K1", "name": "Investice", "to": "brána G2", "why": "strop FR je podmínka, ne preference; náklad je v E1"},
        {"code": "K2", "name": "Náklad přechodu", "to": "v E1", "why": "Model ho odečítá v roce přechodu"},
        {"code": "S1", "name": "Doručení ve velkých městech", "to": "brána G1", "why": "podmínka OR se nekompenzuje"},
        {"code": "S2", "name": "Ztráta objednávek ze zpoždění", "to": "v E1", "why": "Model ji počítá z dat o zpožděních"},
        {"code": "D2", "name": "Roční indexace ceny", "to": "v E1", "why": "indexace je předpoklad Modelu"},
        {"code": "P1", "name": "Citlivost na mzdy", "to": "v E1", "why": "růst mezd je předpoklad Modelu"},
        {"code": "X1", "name": "Průměr hodnocení manažerů", "to": "kontrola", "why": "pět kritérií manažerů už hodnotí E1, D1, F2 a G1"},
    ],
    "experts": {o: round(st.mean([s for c in EXPERTS[o].values() for s in c]), 2) for o in objs},
    "expert_cells": {o: sum(len(c) for c in EXPERTS[o].values()) for o in objs},
}

# ---------------- Map 2: fulfilment suppliers ----------------
sup = ["DE", "WI", "VL", "MO", "PO", "DU"]
snames = {"DE": "Delta Fulfillment CZ", "WI": "Wisła Fulfilment", "VL": "Vlastní provoz Velis",
          "MO": "Morava Fulfil*", "PO": "Polaris Logistyka*", "DU": "Dunaj 3PL*"}


def srow(vals, cert, src):
    out = {}
    for o, v in zip(sup, vals):
        c = cert.get(o) if isinstance(cert, dict) else cert
        s = src.get(o) if isinstance(src, dict) else src
        out[o] = v if isinstance(v, dict) else K(v, c, s)
    return out


suppliers = {
    "objects": [{"id": o, "name": snames[o]} for o in sup],
    "flip": [1, 1],
    "owner": "VN",
    "stakeholders": {"VN": "vedoucí nákupu (vlastník výběru)", "FR": "finanční ředitel", "OR": "obchodní ředitelka"},
    "gates": [
        {"code": "G1", "name": "Slib ve velkých městech: do 1 dne, sám nebo s expresním partnerem", "from": "Zadání · podmínka OR",
         "values": {"DE": ["pass", "smlouva s. 3"], "WI": ["pass", "s expresem: nabidka_kuryr_expres"], "VL": ["pass", "úsudek: Jihlava"],
                    "MO": ["pass", "web*"], "PO": ["unknown", "2 dny, expresní partner nedoložen"], "DU": ["unknown", "2 dny (úsudek), partner nedoložen"]}},
    ],
    "swing": {
        "VN": {"C": 100, "S": 80, "R": 60, "P": 50, "K": 40, "V": 30, "M": 20},
        "FR": {"C": 100, "S": 50, "R": 50, "P": 60, "K": 30, "V": 15, "M": 30},
        "OR": {"C": 60, "S": 100, "R": 70, "P": 30, "K": 50, "V": 50, "M": 10},
    },
    "categories": [
        {"code": "C", "name": "Cena", "why": "náklad na objednávku je hlavní páka", "indicators": [
            {"code": "C1", "name": "Provozní náklad na objednávku vč. skladného (Kč)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≤ 45 → 10 · ≤ 50 → 8 · ≤ 55 → 6 · ≤ 60 → 4 · > 60 → 2 (při 410 tis. objednávek, 2,3 položky)",
             "cuts": [(45, 10), (50, 8), (55, 6), (60, 4), (INF, 2)],
             "values": srow([57.7, 47.6, 47.1, 52.0, 44.0, U("ceník nezveřejněn")], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S},
                            {"DE": "smlouva s. 3–4: 46 + 4,8 mil./rok", "WI": "s. 1–3: 34 + 6 svoz + 3,1 mil.", "VL": "nabidka_hala s. 5: 32 Kč + 6,2 mil.", "MO": "veřejný ceník*", "PO": "veřejný ceník*"})},
            {"code": "C2", "name": "Roční indexace (%)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≤ 2 → 10 · ≤ 3 → 8 · ≤ 4 → 6 · ≤ 5 → 4 · > 5 → 2",
             "cuts": [(2, 10), (3, 8), (4, 6), (5, 4), (INF, 2)],
             "values": srow([5, 3, 4.5, U("indexace nezveřejněna"), 3.5, U("nezveřejněno")], {"DE": V, "WI": V, "VL": N, "PO": S},
                            {"DE": "smlouva s. 6", "WI": "s. 5", "VL": "úsudek: mzdy CZ", "PO": "obchodní podmínky*"})},
        ]},
        {"code": "S", "name": "Rychlost doručení", "why": "slib ve velkých městech",
         "overlap": "S2 (uzávěrka) z části určuje S1: obě v jedné kategorii, váha jednou", "indicators": [
            {"code": "S1", "name": "Doručení do velkých měst (dny)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "1 → 9 · 2 → 5 · 3 → 2",
             "cuts": [(1, 9), (2, 5), (INF, 2)],
             "values": srow([1, 2, 1, 1, 2, 2], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S, "DU": N},
                            {"DE": "smlouva s. 3", "WI": "s. 3", "VL": "úsudek: Jihlava", "MO": "web*", "PO": "web*", "DU": "úsudek: vzdálenost"})},
            {"code": "S2", "name": "Uzávěrka expedice (hodina)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≥ 15 → 10 · 14 → 8 · 13 → 6 · ≤ 12 → 4",
             "cuts": [(12, 4), (13, 6), (14, 8), (INF, 10)],
             "values": srow([14, 13, 15, 15, 12, U("uzávěrka nezveřejněna")], {"DE": V, "WI": V, "VL": N, "MO": S, "PO": S},
                            {"DE": "smlouva s. 3", "WI": "s. 6", "VL": "úsudek", "MO": "web*", "PO": "web*"})},
        ]},
        {"code": "K", "name": "Kapacita", "why": "potřeba 750 tis. objednávek v roce 2032", "indicators": [
            {"code": "K1", "name": "Kapacita / potřeba 2032", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≥ 1,2 → 10 · ≥ 1,0 → 8 · ≥ 0,9 → 6 · ≥ 0,8 → 4 · < 0,8 → 2",
             "cuts": [(0.7999, 2), (0.8999, 4), (0.9999, 6), (1.1999, 8), (INF, 10)],
             "values": srow([U("limit nehlášen · dotaz odeslán 4. 11."), 1.12, 0.83, 0.9, 1.4, U("nezveřejněno")], {"WI": V, "VL": V, "MO": S, "PO": S},
                            {"WI": "s. 4", "VL": "nabidka_hala s. 3", "MO": "výroční zpráva*", "PO": "web*"})},
        ]},
        {"code": "P", "name": "Smluvní podmínky", "why": "ochrana proti zdražení a uzamčení", "indicators": [
            {"code": "P1", "name": "Checklist podmínek (z 5)", "kind": "checklist",
             "items": ["strop indexace", "výpověď ≤ 6 měsíců", "sleva za zpoždění", "odpovědnost ≥ 2 mil. Kč", "bez poplatku za ukončení"],
             "from": "Data · Rešerše",
             "rule": "skóre = 1 + 9 × podíl splněných; nedoložená položka je neznámá, ne nesplněná",
             "values": {"DE": CL("yyyyy", V, "smlouva s. 3–8"), "WI": CL("nnyyn", V, "nabidka_3PL_PL s. 5–7"),
                        "VL": NA("vlastní provoz nemá smlouvu s 3PL"), "MO": CL("yy?y?", S, "obchodní podmínky*"),
                        "PO": CL("?y?y?", S, "obchodní podmínky*"), "DU": CL("?y???", N, "zveřejněna jen výpověď")}},
        ]},
        {"code": "R", "name": "Spolehlivost", "why": "zpoždění stojí 3,6 % objednávek", "indicators": [
            {"code": "R1", "name": "Výpadky za 3 roky", "kind": "slovní", "from": "Data · Rešerše",
             "rule": "doložená bezchybná historie 9 · hlášený výpadek 5 · nový provoz 5 · bez záznamu = neznámo",
             "range": [5, 9],
             "values": srow([9, U("nic nehlášeno, nic doloženo"), 5, 5, U("nic nehlášeno"), U("nic nehlášeno")],
                            {"DE": V, "VL": N, "MO": S},
                            {"DE": "faktury_3PL_CZ_2025: žádná sleva za zpoždění", "VL": "rozjezd provozu (úsudek)", "MO": "zpráva o výpadku WMS 2025*"})},
            {"code": "R2", "name": "Riziko dodavatele podle manažerů", "kind": "přímo", "from": "Data",
             "rule": "průměr kritéria Riziko dodavatele z hodnoceni_expertu.csv; kdo nebyl hodnocen, je neznámý",
             "values": srow([6.4, 5.0, 8.4, U("manažeři nehodnotili"), U("nehodnotili"), U("nehodnotili")], V,
                            {"DE": "možnost B", "WI": "možnost C", "VL": "možnost A"})},
        ]},
        {"code": "V", "name": "Služby navíc", "why": "vratky tvoří velkou část práce", "indicators": [
            {"code": "V1", "name": "Checklist služeb (z 4)", "kind": "checklist",
             "items": ["vratky do 48 h", "dárkové balení", "napojení na e-shop přes API", "sklad v ČR pro výprodeje"],
             "from": "Data · Rešerše", "rule": "skóre = 1 + 9 × podíl splněných; nedoložená položka je neznámá",
             "values": {"DE": CL("yyny", V, "smlouva s. 2"), "WI": CL("??yn", V, "s. 7: napojení systémů; sklad v PL"),
                        "VL": CL("yyyy", S, "vlastní provoz"), "MO": CL("yyy?", S, "web*"),
                        "PO": CL("y?yn", S, "web*"), "DU": CL("?y??", N, "web*")}},
        ]},
        {"code": "M", "name": "Měna (PESTEL E)", "why": "kurzové riziko", "indicators": [
            {"code": "L2", "name": "Měna fakturace", "kind": "slovní", "from": "Rešerše · PESTEL E",
             "rule": "Kč 9 · EUR 5 · PLN 4",
             "values": srow([9, 5, 9, 9, 4, 5], V, {"DE": "smlouva", "WI": "nabídka s. 1", "VL": "Kč", "MO": "ceník*", "PO": "ceník*", "DU": "ceník*"})},
        ]},
    ],
    "removed": [
        {"code": "L1", "name": "Vzdálenost od Prahy", "to": "vypuštěno", "why": "vzdálenost už je v S1 (dny doručení) a v C1 (svoz)"},
        {"code": "R1 · pravidlo 6", "name": "Nic nehlášeno = 8", "to": "neznámo", "why": "chybějící záznam není bezchybná historie"},
        {"code": "C2 · pravidlo 5", "name": "Nezveřejněná indexace = medián", "to": "neznámo", "why": "mlčení dodavatele není průměr trhu"},
    ],
}

json.dump(options, open(os.path.join(HERE, "spec_options.json"), "w"), ensure_ascii=False, indent=1)
json.dump(suppliers, open(os.path.join(HERE, "spec_suppliers.json"), "w"), ensure_ascii=False, indent=1)

# ---------------- How each scale reads on the boards ----------------
# A band's label names its input range; a value exactly on a boundary takes the better score.
# A level names a situation and the objects that are in it; its score must equal theirs.
LOOK = {
    "options": {
        "E1": {"bands": ["pod 0", "0–1", "1–3", "3–5", "5–7", "7 a víc"], "unit": "mil. Kč"},
        "R1": {"bands": ["do 1", "1–3", "3–5", "5–10", "nad 10"], "unit": "% budoucností"},
        "F2": {"bands": ["pod 0,8", "0,8–0,9", "0,9–1,0", "1,0–1,2", "1,2 a víc"], "unit": "× potřeby"},
        "D1": {"levels": [["vlastní provoz, záloha u 3PL", 8, ["A", "A2"]], ["dva dodavatelé", 7, ["H"]],
                          ["jeden dodavatel s pevnou cenou", 5, ["B2"]], ["jeden dodavatel", 4, ["B", "C"]],
                          ["dva noví dodavatelé", 3, ["C2"]]]},
        "P2": {"levels": [["vše v Kč", 9, ["A", "A2", "B", "B2"]], ["část v EUR", 7, ["H"]], ["fakturace v EUR", 5, ["C", "C2"]]]},
        "F1": {"levels": [["výpověď 6 měsíců", 9, ["B"]], ["výpověď 12 měsíců", 6, ["B2"]], ["část smlouvy na 7 let", 4, ["H"]],
                          ["7 let, výstup po 3. roce s poplatkem", 3, ["C", "C2"]], ["2. etapa haly se dá odložit", 3, ["A2"]],
                          ["vlastní hala", 2, ["A"]]]},
        "T1": {"levels": [["hned", 10, ["B"]], ["1. 1. 2027", 9, ["B2"]], ["1. 7. 2027", 7, ["C", "C2", "H"]], ["1. 1. 2028", 5, ["A", "A2"]]]},
    },
    "suppliers": {
        "C1": {"bands": ["do 45", "45–50", "50–55", "55–60", "nad 60"], "unit": "Kč"},
        "C2": {"bands": ["do 2", "2–3", "3–4", "4–5", "nad 5"], "unit": "% ročně"},
        "S1": {"bands": ["1 den", "2 dny", "3 dny"], "unit": ""},
        "S2": {"bands": ["do 12:00", "13:00", "14:00", "15:00 a později"], "unit": ""},
        "K1": {"bands": ["pod 0,8", "0,8–0,9", "0,9–1,0", "1,0–1,2", "1,2 a víc"], "unit": "× potřeby"},
        "R1": {"levels": [["doložená bezchybná historie", 9, ["DE"]], ["hlášený výpadek", 5, ["MO"]], ["nový provoz", 5, ["VL"]]]},
        "L2": {"levels": [["Kč", 9, ["DE", "VL", "MO"]], ["EUR", 5, ["WI", "DU"]], ["PLN", 4, ["PO"]]]},
    },
}
json.dump(LOOK, open(os.path.join(HERE, "look.json"), "w"), ensure_ascii=False, indent=1)
