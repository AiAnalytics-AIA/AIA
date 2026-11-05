import json
INF = 1e9
V, S, N, O = "Vysoká", "Střední", "Nízká", "Odhad"

# ---------------- Map 1: the seven options ----------------
objs = ["A", "A2", "B", "B2", "C", "C2", "H"]
names = {"A": "A · Hala", "A2": "A2 · Hala po etapách", "B": "B · 3PL CZ", "B2": "B2 · 3PL CZ pevná cena",
         "C": "C · 3PL PL", "C2": "C2 · 3PL PL + expres", "H": "H · Hybrid"}


def row(vals, cert, src):
    return {o: (None if v is None else (v, cert if not isinstance(cert, dict) else cert[o], src if not isinstance(src, dict) else src[o]))
            for o, v in zip(objs, vals)}

ex = {"A": 6.6, "A2": 6.28, "B": 6.52, "B2": 6.76, "C": 6.08, "C2": 6.48, "H": 6.44}  # A with OR's missing cell at the median
options = {
    "objects": [{"id": o, "name": names[o]} for o in objs],
    "crossings": [["E", "C2", "B2"], ["E", "C2", "B"]],
    "flip": [1, 1],
    "categories": [
        {"code": "E", "name": "Ekonomika", "w": 0.22, "why": "cíl FR: nejvyšší příspěvek za 7 let", "indicators": [
            {"code": "E1", "name": "Medián NPV proti B (mil. Kč, 8 %)", "kind": "pásmo", "from": "Výsledky",
             "rule": "< 0 → 2 · < 1 → 4 · < 3 → 5 · < 5 → 6 · < 7 → 8 · ≥ 7 → 10",
             "cuts": [(-0.001, 2), (0.999, 4), (2.999, 5), (4.999, 6), (6.999, 8), (INF, 10)],
             "values": row([3.9, 4.7, 0.0, 5.9, 4.7, 8.8, 1.1], V, "Výsledky · model, 800 budoucností")},
            {"code": "E2", "name": "Podíl budoucností, kde je nejlepší (%)", "kind": "pásmo", "from": "Výsledky",
             "rule": "< 5 → 2 · < 10 → 4 · < 20 → 6 · < 30 → 8 · ≥ 30 → 10",
             "cuts": [(4.99, 2), (9.99, 4), (19.99, 6), (29.99, 8), (INF, 10)],
             "values": row([9, 15, 3, 24, 7, 42, 0], V, "Výsledky · model")},
        ]},
        {"code": "R", "name": "Riziko ztráty", "w": 0.12, "why": "limit FR: ztráta > 10 mil. nejvýš v 1 z 10", "indicators": [
            {"code": "R1", "name": "P(ztráta > 10 mil. Kč proti B) (%)", "kind": "pásmo", "from": "Výsledky",
             "rule": "≤ 2 → 10 · ≤ 5 → 8 · ≤ 10 → 6 · ≤ 15 → 3 · > 15 → 1",
             "cuts": [(2, 10), (5, 8), (10, 6), (15, 3), (INF, 1)],
             "values": row([12, 8, 0, 3, 9, 6, 14], V, "Výsledky · model")},
        ]},
        {"code": "K", "name": "Kapitál", "w": 0.08, "why": "strop investice 90 mil., hotovost 4 mil.", "indicators": [
            {"code": "K1", "name": "Investice (mil. Kč)", "kind": "pásmo", "from": "Data · dokumenty",
             "rule": "0 → 10 · ≤ 45 → 7 · ≤ 90 → 4 · > 90 vyřazeno",
             "cuts": [(0, 10), (45, 7), (90, 4)],
             "values": row([70, 77, 0, 0, 0, 0, 0], V, {"A": "nabidka_hala.pdf s. 1", "A2": "nabidka_hala.pdf s. 2", "B": "smlouva s. 4", "B2": "dodatek", "C": "nabidka_3PL_PL s. 1", "C2": "nabidka_3PL_PL s. 1", "H": "obě nabídky 3PL"})},
            {"code": "K2", "name": "Náklad přechodu (mil. Kč)", "kind": "pásmo", "from": "Data",
             "rule": "0 → 10 · ≤ 3 → 8 · ≤ 6 → 6 · ≤ 9 → 4 · > 9 → 2",
             "cuts": [(0, 10), (3, 8), (6, 6), (9, 4), (INF, 2)],
             "values": row([None, None, 0, 0, 6, 6, 6], V, {"B": "beze změny", "B2": "beze změny", "C": "plan_prechodu.xlsx, Celkem", "C2": "plan_prechodu.xlsx", "H": "plan_prechodu.xlsx", "A": "", "A2": ""})},
        ]},
        {"code": "S", "name": "Slib a zákazníci", "w": 0.16, "why": "podmínka OR: slib ve městech se nezhorší", "indicators": [
            {"code": "S1", "name": "Doručení ve velkých městech (pracovní dny)", "kind": "pásmo", "from": "Data · dokumenty",
             "rule": "1 den → 9 · 2 dny → 3 (porušuje podmínku)",
             "cuts": [(1, 9), (2, 3), (INF, 1)],
             "values": row([1, 1, 1, 1, 2, 1, 1], V, {"A": "úsudek: vlastní expedice", "A2": "úsudek", "B": "smlouva s. 3", "B2": "smlouva s. 3", "C": "nabidka_3PL_PL s. 3", "C2": "nabidka_kuryr_expres", "H": "smlouva s. 3"})},
            {"code": "S2", "name": "Ztráta objednávek ze zpoždění (%)", "kind": "pásmo", "from": "Data",
             "rule": "0 → 10 · ≤ 1 → 8 · ≤ 2 → 6 · ≤ 3 → 4 · > 3 → 2",
             "cuts": [(0, 10), (1, 8), (2, 6), (3, 4), (INF, 2)],
             "values": row([0, 0, 0, 0, 3.6, 1.7, 1.7], V, "zpozdeni_2024.xlsx: 3,6 % celkem, 48 % mimo města")},
        ]},
        {"code": "D", "name": "Dodavatelé (Porter)", "w": 0.10, "why": "síla dodavatele: jediný 3PL, indexace 3–7 %", "indicators": [
            {"code": "D1", "name": "Závislost na jednom dodavateli", "kind": "slovní", "from": "Rešerše · Porter",
             "rule": "slovní škála: vlastní + záloha 8 · dva dodavatelé 7 · jeden s pevnou cenou 5 · jeden 4 · dva noví 3",
             "values": row([8, 8, 4, 5, 4, 3, 7], S, "Porter: síla dodavatelů (úsudek)")},
            {"code": "D2", "name": "Roční indexace ceny (%)", "kind": "pásmo", "from": "Data · dokumenty",
             "rule": "≤ 1 → 10 · ≤ 2 → 8 · ≤ 3 → 7 · ≤ 4 → 5 · ≤ 5 → 4 · > 5 → 2",
             "cuts": [(1, 10), (2, 8), (3, 7), (4, 5), (5, 4), (INF, 2)],
             "values": row([None, None, 5, 1, 3, 3, 4], {"A": O, "A2": O, "B": V, "B2": V, "C": V, "C2": S, "H": S},
                           {"A": "", "A2": "", "B": "smlouva s. 6: 3–7 %, čekáno 5 %", "B2": "dodatek: poplatek pevně, skladné dál čl. 5", "C": "nabidka_3PL_PL s. 5: průměr 3 %", "C2": "s. 5; expres bez indexace v nabídce", "H": "průměr B a C"})},
        ]},
        {"code": "P", "name": "Prostředí (PESTEL)", "w": 0.08, "why": "mzdy a kurz jsou největší vnější tlaky na cenu", "indicators": [
            {"code": "P1", "name": "Citlivost nákladu na mzdy v logistice", "kind": "slovní", "from": "Rešerše · PESTEL E",
             "rule": "slovní škála: pevná cena 8 · PL minimální mzda 6 · CZ vzorec (½ růstu mezd) 5 · vlastní lidé 4",
             "values": row([4, 4, 5, 8, 6, 6, 5], S, "PESTEL: mzdy doprava a skladování (ČSÚ, GUS)")},
            {"code": "P2", "name": "Kurzové riziko", "kind": "slovní", "from": "Rešerše · PESTEL E",
             "rule": "slovní škála: vše v Kč 9 · část v EUR 7 · fakturace v EUR 5",
             "values": row([9, 9, 9, 9, 5, 5, 7], V, {"A": "Kč", "A2": "Kč", "B": "smlouva: Kč", "B2": "Kč", "C": "nabidka_3PL_PL s. 1: EUR", "C2": "EUR", "H": "polovina v EUR"})},
        ]},
        {"code": "F", "name": "Flexibilita", "w": 0.10, "why": "růst 4–14 % ročně je nejistý", "indicators": [
            {"code": "F1", "name": "Vratnost rozhodnutí", "kind": "slovní", "from": "Rešerše · PESTEL L",
             "rule": "slovní škála: výpověď 6 měs. 9 · výpověď 12 měs. 6 · výstup po 3. roce s poplatkem 3 · vlastní hala 2",
             "values": row([2, 3, 9, 6, 3, 3, 4], V, {"A": "nabidka_hala s. 6", "A2": "druhá etapa se dá odložit", "B": "smlouva s. 8", "B2": "dodatek: 12 měsíců", "C": "nabidka_3PL_PL s. 7", "C2": "s. 7", "H": "PL část s. 7"})},
            {"code": "F2", "name": "Kapacita na rok 2032 (podíl potřeby)", "kind": "pásmo", "from": "Data · Předpoklady",
             "rule": "potřeba 750 tis. objednávek (9 % ročně): ≥ 1,2 → 10 · ≥ 1,0 → 8 · ≥ 0,9 → 6 · ≥ 0,8 → 4 · < 0,8 → 2",
             "cuts": [(0.7999, 2), (0.8999, 4), (0.9999, 6), (1.1999, 8), (INF, 10)],
             "values": row([0.83, 0.83, 1.2, 1.2, 1.12, 1.12, 1.3], {"A": V, "A2": V, "B": N, "B2": N, "C": V, "C2": V, "H": S},
                           {"A": "nabidka_hala s. 3: 620 tis.", "A2": "s. 3", "B": "limit nehlášen, úsudek", "B2": "úsudek", "C": "s. 4: 70 tis. měsíčně", "C2": "s. 4", "H": "dva sklady"})},
        ]},
        {"code": "T", "name": "Realizace", "w": 0.06, "why": "rozhoduje se do 15. 12. 2026", "indicators": [
            {"code": "T1", "name": "Začátek nového stavu", "kind": "slovní", "from": "Zadání · dokumenty",
             "rule": "hned 10 · 1. 1. 2027 9 · 1. 7. 2027 7 · 1. 1. 2028 5",
             "values": row([5, 5, 10, 9, 7, 7, 7], V, "CASE §8: kdy která možnost začne")},
        ]},
        {"code": "X", "name": "Experti", "w": 0.08, "why": "pět manažerů klienta, pět kritérií", "indicators": [
            {"code": "X1", "name": "Průměr hodnocení manažerů (1–10)", "kind": "přímo", "from": "Data",
             "rule": "tvrdá data se použijí přímo (pravidlo 1); chybějící buňka OR·A·Služba = medián ostatních čtyř",
             "values": row([ex[o] for o in objs], V, "hodnoceni_expertu.csv, 25 buněk")},
        ]},
    ],
}

# ---------------- Map 2: fulfilment suppliers ----------------
sup = ["DE", "WI", "VL", "MO", "PO", "DU"]
snames = {"DE": "Delta Fulfillment CZ", "WI": "Wisła Fulfilment", "VL": "Vlastní provoz Velis",
          "MO": "Morava Fulfil*", "PO": "Polaris Logistyka*", "DU": "Dunaj 3PL*"}


def srow(vals, cert, src):
    return {o: (None if v is None else (v, cert if not isinstance(cert, dict) else cert[o], src if not isinstance(src, dict) else src[o]))
            for o, v in zip(sup, vals)}

suppliers = {
    "objects": [{"id": o, "name": snames[o]} for o in sup],
    "flip": [1, 1],
    "categories": [
        {"code": "C", "name": "Cena", "w": 0.22, "why": "náklad na objednávku je hlavní páka", "indicators": [
            {"code": "C1", "name": "Provozní náklad na objednávku vč. skladného (Kč)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≤ 45 → 10 · ≤ 50 → 8 · ≤ 55 → 6 · ≤ 60 → 4 · > 60 → 2 (při 410 tis. objednávek, 2,3 položky)",
             "cuts": [(45, 10), (50, 8), (55, 6), (60, 4), (INF, 2)],
             "values": srow([57.7, 47.6, 47.1, 52.0, 44.0, None], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S, "DU": O},
                            {"DE": "smlouva s. 3–4: 46 + 4,8 mil./rok", "WI": "s. 1–3: 34 + 6 svoz + 3,1 mil.", "VL": "nabidka_hala s. 5: 32 Kč + 6,2 mil.", "MO": "veřejný ceník*", "PO": "veřejný ceník*", "DU": ""})},
            {"code": "C2", "name": "Roční indexace (%)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≤ 2 → 10 · ≤ 3 → 8 · ≤ 4 → 6 · ≤ 5 → 4 · > 5 → 2 · nezveřejněno = medián (upravené pravidlo 5)",
             "cuts": [(2, 10), (3, 8), (4, 6), (5, 4), (INF, 2)],
             "values": srow([5, 3, 4.5, None, 3.5, None], {"DE": V, "WI": V, "VL": N, "MO": O, "PO": S, "DU": O},
                            {"DE": "smlouva s. 6", "WI": "s. 5", "VL": "úsudek: mzdy CZ", "MO": "", "PO": "obchodní podmínky*", "DU": ""})},
        ]},
        {"code": "S", "name": "Doručení", "w": 0.20, "why": "slib ve velkých městech", "indicators": [
            {"code": "S1", "name": "Doručení do velkých měst (dny)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "1 → 9 · 2 → 5 · 3 → 2",
             "cuts": [(1, 9), (2, 5), (INF, 2)],
             "values": srow([1, 2, 1, 1, 2, 2], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S, "DU": N},
                            {"DE": "smlouva s. 3", "WI": "s. 3", "VL": "úsudek: Jihlava", "MO": "web*", "PO": "web*", "DU": "úsudek: vzdálenost"})},
            {"code": "S2", "name": "Uzávěrka expedice (hodina)", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≥ 15 → 10 · 14 → 8 · 13 → 6 · ≤ 12 → 4",
             "cuts": [(12, 4), (13, 6), (14, 8), (INF, 10)],
             "values": srow([14, 13, 15, 15, 12, None], {"DE": V, "WI": V, "VL": N, "MO": S, "PO": S, "DU": O},
                            {"DE": "smlouva s. 3", "WI": "s. 6", "VL": "úsudek", "MO": "web*", "PO": "web*", "DU": ""})},
        ]},
        {"code": "K", "name": "Kapacita", "w": 0.12, "why": "potřeba 750 tis. objednávek v roce 2032", "indicators": [
            {"code": "K1", "name": "Kapacita / potřeba 2032", "kind": "pásmo", "from": "Data · Rešerše",
             "rule": "≥ 1,2 → 10 · ≥ 1,0 → 8 · ≥ 0,9 → 6 · ≥ 0,8 → 4 · < 0,8 → 2",
             "cuts": [(0.7999, 2), (0.8999, 4), (0.9999, 6), (1.1999, 8), (INF, 10)],
             "values": srow([1.2, 1.12, 0.83, 0.9, 1.4, None], {"DE": N, "WI": V, "VL": V, "MO": S, "PO": S, "DU": O},
                            {"DE": "limit nehlášen, úsudek", "WI": "s. 4", "VL": "nabidka_hala s. 3", "MO": "výroční zpráva*", "PO": "web*", "DU": ""})},
        ]},
        {"code": "P", "name": "Smluvní podmínky", "w": 0.12, "why": "ochrana proti zdražení a uzamčení", "indicators": [
            {"code": "P1", "name": "Checklist podmínek (z 5)", "kind": "checklist", "items": 5, "from": "Data · Rešerše",
             "rule": "strop indexace · výpověď ≤ 6 měs. · sleva za zpoždění · odpovědnost ≥ 2 mil. · bez poplatku za ukončení; skóre = 1 + 9 × podíl; nezdokumentované = nesplněno (pravidlo 4)",
             "values": srow([5, 2, 1, 3, 2, 1], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S, "DU": N},
                            {"DE": "smlouva s. 3–8", "WI": "s. 5–7", "VL": "jen cena pod kontrolou", "MO": "obchodní podmínky*", "PO": "obchodní podmínky*", "DU": "zveřejněna jen výpověď"})},
        ]},
        {"code": "R", "name": "Spolehlivost", "w": 0.14, "why": "zpoždění stojí 3,6 % objednávek", "indicators": [
            {"code": "R1", "name": "Hlášené výpadky za 3 roky", "kind": "slovní", "from": "Data · Rešerše",
             "rule": "doložená bezchybná historie 9 · nic nehlášeno 8 (pravidlo 6) · hlášený výpadek 5 · nový provoz 5",
             "values": srow([9, 8, 5, 5, 8, 8], {"DE": V, "WI": N, "VL": S, "MO": S, "PO": N, "DU": N},
                            {"DE": "faktury_3PL_CZ_2025: žádná sleva za zpoždění", "WI": "nic nehlášeno", "VL": "rozjezd provozu", "MO": "zpráva o výpadku WMS 2025*", "PO": "nic nehlášeno", "DU": "nic nehlášeno"})},
            {"code": "R2", "name": "Riziko dodavatele podle manažerů", "kind": "přímo", "from": "Data",
             "rule": "průměr kritéria Riziko dodavatele z hodnoceni_expertu.csv (B, C, A); ostatní nehodnotili = medián",
             "values": srow([6.4, 5.0, 8.4, None, None, None], {"DE": V, "WI": V, "VL": V, "MO": O, "PO": O, "DU": O},
                            {"DE": "možnost B", "WI": "možnost C", "VL": "možnost A", "MO": "", "PO": "", "DU": ""})},
        ]},
        {"code": "V", "name": "Služby navíc", "w": 0.08, "why": "vratky tvoří velkou část práce", "indicators": [
            {"code": "V1", "name": "Checklist služeb (z 4)", "kind": "checklist", "items": 4, "from": "Data · Rešerše",
             "rule": "vratky do 48 h · dárkové balení · napojení na e-shop přes API · sklad v ČR pro výprodeje; nezdokumentované = nesplněno",
             "values": srow([3, 1, 4, 3, 2, 1], {"DE": V, "WI": V, "VL": S, "MO": S, "PO": S, "DU": N},
                            {"DE": "smlouva s. 2", "WI": "s. 7: napojení systémů", "VL": "vlastní", "MO": "web*", "PO": "web*", "DU": "web*"})},
        ]},
        {"code": "L", "name": "Lokalita (PESTEL)", "w": 0.12, "why": "vzdálenost a měna", "indicators": [
            {"code": "L1", "name": "Vzdálenost od Prahy (km)", "kind": "pásmo", "from": "Rešerše",
             "rule": "≤ 150 → 10 · ≤ 250 → 8 · ≤ 350 → 5 · > 350 → 3",
             "cuts": [(150, 10), (250, 8), (350, 5), (INF, 3)],
             "values": srow([205, 400, 130, 370, 330, 330], V, "mapa: silniční vzdálenost")},
            {"code": "L2", "name": "Měna fakturace", "kind": "slovní", "from": "Rešerše · PESTEL E",
             "rule": "Kč 9 · EUR 5 · PLN 4",
             "values": srow([9, 5, 9, 9, 4, 5], V, {"DE": "smlouva", "WI": "nabídka s. 1", "VL": "Kč", "MO": "ceník*", "PO": "ceník*", "DU": "ceník*"})},
        ]},
    ],
}

json.dump(options, open("spec_options.json", "w"), ensure_ascii=False, indent=1)
json.dump(suppliers, open("spec_suppliers.json", "w"), ensure_ascii=False, indent=1)

# ---------------- How each scale reads on the boards ----------------
# A band's label names its input range; a value exactly on a boundary takes the better score.
# A level names a situation and the objects that are in it; its score must equal theirs.
LOOK = {
    "options": {
        "E1": {"bands": ["pod 0", "0–1", "1–3", "3–5", "5–7", "7 a víc"], "unit": "mil. Kč"},
        "E2": {"bands": ["pod 5", "5–10", "10–20", "20–30", "30 a víc"], "unit": "%"},
        "R1": {"bands": ["do 2", "2–5", "5–10", "10–15", "nad 15"], "unit": "%"},
        "K1": {"bands": ["0", "do 45", "45–90"], "excluded": "nad 90", "unit": "mil. Kč"},
        "K2": {"bands": ["0", "do 3", "3–6", "6–9", "nad 9"], "unit": "mil. Kč"},
        "S1": {"bands": ["1 den", "2 dny", "3 a víc"], "unit": ""},
        "S2": {"bands": ["0", "do 1", "1–2", "2–3", "nad 3"], "unit": "%"},
        "D2": {"bands": ["do 1", "1–2", "2–3", "3–4", "4–5", "nad 5"], "unit": "% ročně"},
        "F2": {"bands": ["pod 0,8", "0,8–0,9", "0,9–1,0", "1,0–1,2", "1,2 a víc"], "unit": "× potřeby"},
        "D1": {"levels": [["vlastní provoz, záloha u 3PL", 8, ["A", "A2"]], ["dva dodavatelé", 7, ["H"]],
                          ["jeden dodavatel s pevnou cenou", 5, ["B2"]], ["jeden dodavatel", 4, ["B", "C"]],
                          ["dva noví dodavatelé", 3, ["C2"]]]},
        "P1": {"levels": [["pevný poplatek", 8, ["B2"]], ["polská minimální mzda", 6, ["C", "C2"]],
                          ["český vzorec (½ růstu mezd)", 5, ["B", "H"]], ["vlastní lidé", 4, ["A", "A2"]]]},
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
        "L1": {"bands": ["do 150", "150–250", "250–350", "nad 350"], "unit": "km"},
        "R1": {"levels": [["doložená bezchybná historie", 9, ["DE"]], ["nic nehlášeno (pravidlo 6)", 8, ["WI", "PO", "DU"]],
                          ["hlášený výpadek", 5, ["MO"]], ["nový provoz", 5, ["VL"]]]},
        "L2": {"levels": [["Kč", 9, ["DE", "VL", "MO"]], ["EUR", 5, ["WI", "DU"]], ["PLN", 4, ["PO"]]]},
    },
}
json.dump(LOOK, open("look.json", "w"), ensure_ascii=False, indent=1)
