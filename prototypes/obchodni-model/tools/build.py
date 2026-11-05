"""Writes SI1-SI4 into the canvas folder from MV3's frame and the two computed maps.

Run from this folder: python3 specs.py; python3 compute.py spec_options.json res_options.json;
python3 compute.py spec_suppliers.json res_suppliers.json; python3 build.py
"""
import json, html, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute import terrain_svg

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MV3 = open(os.path.join(OUT, "MV3SystemMap.dc.html")).read().split("\n")
so, ss = json.load(open("spec_options.json")), json.load(open("spec_suppliers.json"))
ro, rs = json.load(open("res_options.json")), json.load(open("res_suppliers.json"))
e = html.escape


def cz(x, d=1):
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


EXTRA_CSS = """
.ct{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;border-radius:3px;font:600 9.5px/1 var(--mono);margin-left:4px;vertical-align:1px}
.ct.v{background:var(--sunken);color:var(--muted)}
.ct.s{background:var(--swash);color:var(--signal)}
.ct.n{background:var(--youwash);color:var(--youink)}
.ct.o{background:var(--youink);color:#fff}
.smx td.s{font:600 13px/1 var(--mono);text-align:center;white-space:nowrap}
.smx td.s.hi{background:var(--swash)}
.smx td.s.lo{background:var(--youwash)}
.smx td.s small{display:block;font:400 10.5px/1.3 var(--mono);color:var(--faint);margin-top:3px}
.smx tr.cat td{background:var(--sunken);font-weight:600}
.smx tr.tot td{background:var(--stint);font-weight:700;border-top:2px solid var(--signal)}
.smx{border-collapse:collapse;width:100%;font-size:12.5px}
.smx th,.smx td{border:1px solid var(--border);padding:6px 8px;vertical-align:middle}
.smx th{background:var(--sunken);font-weight:500;color:var(--muted);font-size:12px;text-align:center}
.smx td.l{text-align:left}
.io{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.io .st{border:1px solid var(--border);border-radius:8px;background:var(--raised);padding:10px 11px;display:flex;flex-direction:column;gap:6px;font-size:12.5px;line-height:18px}
.io .st.ai{border-color:var(--aiedge);background:var(--aiwash)}
.io .st.you{border-color:var(--you);background:var(--youwash)}
.io .st .k{font:600 10.5px/1 var(--mono);color:var(--faint);letter-spacing:.04em}
.io .st h3{margin:0;font-size:14px}
.io .st .r{display:grid;grid-template-columns:52px minmax(0,1fr);gap:4px}
.io .st .r>span:first-child{color:var(--muted);font-size:11.5px}
.bars{display:flex;flex-direction:column;gap:7px}
.bars .b{display:grid;grid-template-columns:190px minmax(0,1fr) 190px;gap:10px;align-items:center;font-size:13px}
.bars .t{height:18px;background:var(--sunken);border-radius:4px;position:relative;overflow:hidden}
.bars .t i{position:absolute;top:0;bottom:0;background:var(--signal);opacity:.25}
.bars .t em{position:absolute;top:2px;bottom:2px;width:3px;background:var(--signal);border-radius:1px}
.bars .v{font:500 12px var(--mono);color:var(--muted);text-align:right}
.claim{display:grid;grid-template-columns:26px minmax(0,1fr);gap:10px;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px;line-height:21px}
.claim:last-child{border-bottom:0}
.claim .n{font:600 12px/21px var(--mono);color:var(--signal)}
.claim .w{display:block;font-size:12.5px;color:var(--muted)}
.mapw{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;align-items:start}
.mleg{display:flex;flex-direction:column;gap:8px;font-size:13px}
.mleg .o{display:grid;grid-template-columns:70px minmax(0,1fr) 44px;gap:8px;align-items:baseline}
.mleg .o b{font:600 12px var(--mono)}
.mleg .o .h{font:500 12px var(--mono);text-align:right;color:var(--muted)}
"""


def frame(title, h1, aria, conv, sees, ahd_btns, body, prev, nxt, code, height):
    L = list(MV3)
    out = []
    for i, l in enumerate(L, 1):
        if i == 5:
            l = f"<title>{e(title)}</title>"
        if l.startswith("</style>") and i < 160:
            l = EXTRA_CSS + l
        if i == 177:
            l = f'  <div class="conv">{conv}</div>'
        if i == 179:
            l = f'  <div class="cfctx"><i class="ph ph-eye s"></i>Vidí: {e(sees)}</div></div>'
        if i == 181:
            l = f'      <main class="art" aria-label="{e(aria)}">'
        if i == 182:
            l = (f'<div class="ahd"><label for="leadx" class="btn quiet sm leadopen" title="Ukázat Vedoucího"><i class="ph ph-sidebar-simple s"></i>Ada</label>'
                 f'<h1>{e(h1)}</h1><span class="saved"><i class="ph ph-check s"></i>Uloženo</span><span class="grow"></span>{ahd_btns}</div>'
                 f'<div class="abody">{body}</div>')
        if i == 185:
            l = (f'    <div class="zseq" role="navigation" aria-label="Průchod ukázkou"><a href="{prev[0]}"><i class="ph ph-caret-left s"></i>{e(prev[1])}</a>'
                 f'<span class="grow" style="text-align: center">Velis Commerce s.r.o. · Sociomapa z indikátorů · <b>{e(code)}</b> · <a href="SI1Method.dc.html">začátek metody</a></span>'
                 f'<a href="{nxt[0]}">{e(nxt[1])}<i class="ph ph-caret-right s"></i></a></div>')
        if i == 189:
            l = l.replace('"height":2350', f'"height":{height}')
        out.append(l)
    return "\n".join(out)


def sec(num, title, cap, inner, cls=""):
    return (f'<section class="sec {cls}"><div class="sh"><span class="num">{num}</span><h2>{e(title)}</h2><span class="grow"></span>'
            f'<span class="cap">{e(cap)}</span></div><div class="sb">{inner}</div></section>')


def ada(time, ps, me=None, time2=None, ps2=None, day="5. 11."):
    s = f'<div class="day">{day}</div>' + _reply(time, ps)
    if me:
        s += f'<div class="me">{e(me)}</div>' + _reply(time2, ps2)
    return s


def _reply(t, ps):
    return ('<div class="reply"><span class="lav" aria-hidden="true"><i class="ph ph-sparkle"></i></span><div class="body">'
            f'<div class="who"><b>Ada</b>{t}</div>' + "".join(f"<p>{p}</p>" for p in ps) + "</div></div>")


CT = {"Vysoká": ("v", "V"), "Střední": ("s", "S"), "Nízká": ("n", "N"), "Odhad": ("o", "O")}


def ct(c):
    k, l = CT[c]
    return f'<span class="ct {k}" title="Jistota: {c}">{l}</span>'


CT_LEG = ('<div class="zleg" style="margin-top:8px"><span>Jistota:</span><span>' + ct("Vysoká") + ' Vysoká: doklad klienta nebo výpočet</span><span>' + ct("Střední") +
          ' Střední: veřejný zdroj nebo ověřený úsudek</span><span>' + ct("Nízká") + ' Nízká: úsudek bez dokladu</span><span>' + ct("Odhad") + ' Odhad: chybělo, doplněn medián</span></div>')


def fmt_raw(v):
    if v is None:
        return "—"
    if isinstance(v, float) and not v.is_integer():
        return cz(v, 2 if abs(v) < 2 else 1)
    return cz(v, 0)


def matrix(spec, res, short):
    objs = res["objs"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows = [f'<table class="smx"><thead><tr><th style="text-align:left">Indikátor</th>{th}</tr></thead><tbody>']
    for ci, c in enumerate(spec["categories"]):
        for ind in c["indicators"]:
            sc = res["scores"][ind["code"]]
            cells = ""
            for o in objs:
                x = sc[o]
                s = x["score"]
                cls = "hi" if s >= 8 else ("lo" if s <= 3 else "")
                sv = cz(s, 1) if not float(s).is_integer() else cz(s, 0)
                rw = "" if ind["kind"] in ("slovní", "přímo") else (f'{fmt_raw(x["raw"])} z {ind["items"]}' if ind["kind"] == "checklist" and x["raw"] is not None else fmt_raw(x["raw"]))
                cells += f'<td class="s {cls}">{sv}{ct(x["cert"])}' + (f'<small>{rw}</small>' if rw else '') + '</td>'
            rows.append(f'<tr><td class="l"><span class="mono" style="color:var(--faint)">{ind["code"]}</span> {e(ind["name"])}</td>{cells}</tr>')
        cm = "".join(f'<td class="s">{cz(res["M"][oi][ci])}</td>' for oi in range(len(objs)))
        rows.append(f'<tr class="cat"><td class="l">{e(c["name"])} · průměr · váha {cz(c["w"]*100,0)} %</td>{cm}</tr>')
    tot = "".join(f'<td class="s">{cz(t, 2)}</td>' for t in res["total"])
    rows.append(f'<tr class="tot"><td class="l">Vážený součet = výška na mapě</td>{tot}</tr></tbody></table>')
    return "".join(rows)


def catalogue(spec):
    rows = ['<table class="zt"><thead><tr><th>Kód</th><th>Indikátor</th><th>Odkud</th><th>Typ</th><th>Pravidlo bodování 1–10</th></tr></thead><tbody>']
    for c in spec["categories"]:
        rows.append(f'<tr><td colspan="5" style="background:var(--sunken);font-weight:600">{e(c["name"])} · váha {cz(c["w"]*100,0)} % <span style="font-weight:400;color:var(--muted)">· {e(c["why"])}</span></td></tr>')
        for ind in c["indicators"]:
            rows.append(f'<tr><td class="num">{ind["code"]}</td><td>{e(ind["name"])}</td><td>{e(ind["from"])}</td><td>{e(ind["kind"])}</td><td style="font-size:12.5px">{e(ind["rule"])}</td></tr>')
    rows.append("</tbody></table>")
    return "".join(rows)


def scen_bars(res, names):
    objs = res["objs"]
    order = sorted(range(len(objs)), key=lambda i: -res["median"][i])
    lo, hi = 4.0, 9.0
    out = ['<div class="bars">']
    for i in order:
        a = (res["p05"][i] - lo) / (hi - lo) * 100
        b = (res["p95"][i] - lo) / (hi - lo) * 100
        m = (res["median"][i] - lo) / (hi - lo) * 100
        out.append(f'<div class="b"><span>{e(names[objs[i]])}</span><span class="t"><i style="left:{a:.1f}%;width:{b-a:.1f}%"></i><em style="left:{m:.1f}%"></em></span>'
                   f'<span class="v">{cz(res["median"][i],2)} · nejlepší {cz(res["best"][i]*100,0)} %</span></div>')
    out.append('<div class="zleg"><span>Pruh: 5–95 % z 2 000 budoucností · čárka: medián · stupnice 4–9</span></div></div>')
    return "".join(out)


def sim_table(res, short):
    objs = res["objs"]
    rc = res["rcrit"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows = [f'<table class="mx"><thead><tr><th></th>{th}</tr></thead><tbody>']
    for i, a in enumerate(objs):
        cells = ""
        for j in range(len(objs)):
            if i == j:
                cells += '<td style="color:var(--faint)">—</td>'
                continue
            r = res["R"][i][j]
            cls = ' class="hi"' if abs(r) >= rc else ""
            cells += f'<td{cls}><b style="font-size:15px">{res["sim"][i][j]}</b><br><span class="mono" style="font-size:11px;color:var(--muted);white-space:nowrap">r {cz(r,2)}</span><br><span class="mono" style="font-size:11px;color:var(--faint);white-space:nowrap">s {cz(res["C"][i][j],2)}</span></td>'
        rows.append(f'<tr><th>{e(short[a])}</th>{cells}</tr>')
    rows.append("</tbody></table>")
    return "".join(rows)


def links(res):
    rc = res["rcrit"]
    n = len(res["objs"])
    return [(i, j, res["R"][i][j]) for i in range(n) for j in range(i + 1, n) if abs(res["R"][i][j]) >= rc]


def mapleg(res, names, short):
    objs = res["objs"]
    order = sorted(range(len(objs)), key=lambda i: -res["total"][i])
    s = '<div class="mleg"><b style="font-size:12px;color:var(--muted)">Výška = vážený součet</b>'
    for i in order:
        s += f'<div class="o"><b>{e(short[objs[i]])}</b><span>{e(names[objs[i]])}</span><span class="h">{cz(res["total"][i],2)}</span></div>'
    s += ('<div class="zleg" style="flex-direction:column;gap:6px;margin-top:6px"><span><i style="background:#f4f1ec;border:1px solid #929ca4"></i>plná čára: podobný profil (r ≥ ' + cz(res["rcrit"], 2) +
          ')</span><span><i style="background:#ff7a59"></i>čárkovaná: opačný profil (r ≤ −' + cz(res["rcrit"], 2) + ')</span>'
          '<span class="zramp" style="width:100%">' + "".join(f'<i style="background:{c}"></i>' for c in ["#2c3e9e", "#2f6fd1", "#2aa3d8", "#37c2a9", "#2bb53f", "#99d02d", "#e7ee31", "#f5a332", "#e8672b", "#c8302a"]) +
          '</span><span>terasy 1–10 na absolutní stupnici</span></div></div>')
    return s


BTN_MENU = ('<details class="mnu"><summary class="btn quiet sm ic" aria-label="Další akce" title="Další akce"><i class="ph ph-dots-three"></i></summary><div class="mnu-p" role="menu">'
            '<button type="button"><i class="ph ph-download-simple s"></i>Stáhnout matici (XLSX)</button><a href="MV5Validation.dc.html"><i class="ph ph-book-open s"></i>Metoda v Metodice</a></div></details>')
WARN = '<div class="zbar warn"><i class="ph ph-lock-simple"></i>Interní · metoda „Sociomapa z indikátorů“ čeká na zápis metodika do registru · hodnoty z Modelu jsou ukázkové z tohoto prototypu.</div>'

ON = {o["id"]: o["name"] for o in so["objects"]}
OS = {o: o for o in ON}
SN = {o["id"]: o["name"] for o in ss["objects"]}
SS = {"DE": "Delta", "WI": "Wisła", "VL": "Vlastní", "MO": "Morava*", "PO": "Polaris*", "DU": "Dunaj*"}

# ============ SI1 ============
steps = [("1", "Zadání", "cíl, pravidlo, podmínky", "Ada navrhne kategorie a váhy", "kategorie s váhou a důvodem", ""),
         ("2", "Rešerše", "Deep Research · SWOT, PESTEL, Porter", "nálezy převede na indikátory a pásma", "indikátor + pásmo + citace", "ai"),
         ("3", "Data", "soubory klienta", "tvrdé hodnoty se použijí přímo", "hodnota + soubor a řádek", ""),
         ("4", "Schválení", "návrh metody", "člověk upraví, schválí, zamkne", "zamčená verze v záznamu", "you"),
         ("5", "Výpočet", "zamčená metoda + hodnoty", "kód: skóre, výška, mapa, budoucnosti", "matice, mapa, tvrzení", "")]
s1_io = '<div class="io">' + "".join(
    f'<div class="st {c}"><span class="k">KROK {k}</span><h3>{e(n)}</h3><div class="r"><span>vstup</span><span>{e(i)}</span></div>'
    f'<div class="r"><span>proces</span><span>{e(p)}</span></div><div class="r"><span>výstup</span><span><b>{e(o)}</b></span></div></div>' for k, n, i, p, o, c in steps) + "</div>"

rules = [("1", "Tvrdá data se použijí přímo", "Tvrdá data se použijí přímo", "beze změny", "X1 průměr manažerů 6,60 pro A"),
         ("2", "Neověřená znalost = Střední", "Neověřený úsudek = Střední, bez dokladu Nízká", "zpřesněno", "D1, P1 slovní škály"),
         ("3", "Chybí číslo = medián ostatních (Odhad)", "Chybí číslo = medián ostatních (Odhad)", "beze změny", "K2 přechod do haly: v plánu přechodu chybí"),
         ("4", "Nezdokumentovaná služba = nenabízí", "Nezdokumentovaná podmínka nebo služba = nesplněno", "beze změny", "checklisty dodavatelů"),
         ("5", "Nezdokumentované zdražení = 0 %", "Nezdokumentované zdražení = medián ostatních (Odhad)", "upraveno", "0 % by odměnilo dodavatele, který mlčí"),
         ("6", "Žádný hlášený výpadek = 8, ne 10", "Žádný hlášený výpadek = 8; 9 jen s dokladem", "zpřesněno", "R1: Delta 9 z faktur bez slev")]
s1_rules = '<table class="zt"><thead><tr><th>#</th><th>V analýze cloudu</th><th>Ve studii Velis</th><th>Stav</th><th>Kde to působí</th></tr></thead><tbody>' + "".join(
    f'<tr{" class=\"miss\"" if st == "upraveno" else ""}><td class="num">{n}</td><td>{e(a)}</td><td><b>{e(b)}</b></td><td>{e(st)}</td><td style="font-size:12.5px;color:var(--muted)">{e(w)}</td></tr>' for n, a, b, st, w in rules) + "</tbody></table>"

finds = [("PESTEL · E", "Mzdy v dopravě a skladování rostou (ČSÚ, GUS)", "slovní škála citlivosti", "P1"),
         ("PESTEL · E", "Wisła fakturuje v EUR (nabídka s. 1)", "slovní škála měny", "P2 · L2"),
         ("PESTEL · L", "Výpověď 6 měsíců (smlouva s. 8, zákon 89/2012 Sb.)", "vratnost a začátek", "F1 · T1"),
         ("PESTEL · L", "Odpisová skupina haly a daň 21 % (zákon 586/1992 Sb.)", "vstupuje do NPV v Modelu", "E1"),
         ("PESTEL · S", "46 % zákazníků je pod 35 let; čekají rychlé doručení", "zdůvodní váhu Slibu 16 %", "váha S"),
         ("Porter", "Síla dodavatele: jediný 3PL, indexace 3–7 % ročně", "slovní škála závislosti; pásmo indexace", "D1 · D2"),
         ("Porter", "Konkurence doručuje ve městech druhý den", "pásmo: 1 den = norma trhu", "S1"),
         ("SWOT · S", "Povolení haly je pravomocné (nabídka s. 2)", "začátek 1. 1. 2028", "T1"),
         ("SWOT · W", "Hotovost 4 mil. Kč, EBITDA 27,3 mil. Kč", "pásmo investice", "K1"),
         ("SWOT · T", "Zpoždění o den stojí 3,6 % objednávek (data o zpožděních)", "pásmo ztráty", "S2")]
s1_finds = ('<table class="zt"><thead><tr><th>Nástroj</th><th>Nález</th><th>Stane se</th><th>Indikátor</th></tr></thead><tbody>' + "".join(
    f'<tr><td>{e(t)}</td><td>{e(f)}</td><td>{e(b)}</td><td class="num">{e(i)}</td></tr>' for t, f, b, i in finds) + "</tbody></table>"
            '<p class="zcap">Nálezy se nesčítají. Počet silných stránek nic neměří. Každý nález se stane indikátorem s pravidlem, nebo zdůvodní pásmo či váhu.</p>')

body1 = (WARN + sec("01", "Jak vznikne metoda pro tuto studii", "vstup → proces → výstup", s1_io) +
         sec("02", "Šest pravidel bodování", "převzato z analýzy cloudu", s1_rules) +
         sec("03", "SWOT, PESTEL a Porter jako vstupy", "z Rešerše a Zadání (Z4)", s1_finds) +
         sec("04", "Katalog indikátorů: mapa možností", "9 kategorií · 15 indikátorů · návrh Ady, schváleno 5. 11.", catalogue(so) +
             '<p class="zcap">Katalog mapy dodavatelů je na <a href="SI4Suppliers.dc.html">SI4</a>. Stejná metoda, jiné indikátory.</p>'))
conv1 = ada("10:12", ["Metodu jsem ušila na rozhodnutí Velis. Kategorie a váhy vycházejí z pravidla FR: <b>Ekonomika 22 %</b>, <b>Slib a zákazníci 16 %</b>, ostatní pod tím.",
                      "Pásma mají zdroj: z dokumentů klienta, z Rešerše, nebo jsou označená jako úsudek. Upravila jsem pravidlo 5: zdražení, které dodavatel nezveřejní, nepočítám jako 0 %."],
            "Můžeme váhy měnit, až uvidíme výsledky?", "10:14",
            ["Ne potichu. Metodu jsem zamkla před prvním skóre. Každá změna je nová verze s důvodem a mapa ukáže obě. Jak moc pořadí na vahách visí, ukážou budoucnosti na SI3."])
btn1 = BTN_MENU + '<a class="btn primary sm" href="SI2Matrix.dc.html">Matice skóre<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI1Method.dc.html", "w").write(frame("Sociomapa z indikátorů: metoda", "Sociomapa z indikátorů: metoda", "Sociomapa · metoda", conv1,
                                                    "Sociomapa · metoda", btn1, body1, ("MV3SystemMap.dc.html", "Sociomapa systémů"), ("SI2Matrix.dc.html", "Matice skóre"), "SI1 Metoda", 2850))

# ============ SI2 ============
cert_rows = ""
from collections import Counter
for o in ro["objs"]:
    c = Counter(v[o]["cert"] for v in ro["scores"].values())
    cert_rows += f'<tr><td>{e(ON[o])}</td>' + "".join(f'<td class="num">{c.get(k,0)}</td>' for k in ["Vysoká", "Střední", "Nízká", "Odhad"]) + "</tr>"
cert_t = '<table class="zt"><thead><tr><th>Možnost</th><th>Vysoká</th><th>Střední</th><th>Nízká</th><th>Odhad</th></tr></thead><tbody>' + cert_rows + "</tbody></table>"
claims2 = [("B2 má nejvyšší vážený součet: 8,35", "vyhrává na riziku, kapitálu, flexibilitě a vnějších tlacích; na ekonomice je druhá (8,0)"),
           ("C2 vede v Ekonomice (10,0), ale ztrácí na Dodavatelích, Prostředí a Flexibilitě", "dva noví dodavatelé, fakturace v EUR, smlouva na 7 let"),
           ("C porušuje podmínku OR: ve městech doručí o den později", "S1 = 3; v mapě zůstává, ve zprávě je vyřazená"),
           ("A a A2 drží Slib a Dodavatele, ale padají na Flexibilitě (3 a 3,5) a Kapitálu (5)", "investice 70 a 77 mil. Kč; hala se nedá vrátit")]
claims_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims2))
body2 = (WARN + sec("01", "Matice skóre: sedm možností × 15 indikátorů", "skóre 1–10 · jistota · vstupní hodnota pod číslem",
                    matrix(so, ro, OS) + CT_LEG + '<p class="zcap">Zelená: 8 a víc. Oranžová: 3 a míň. Průměr kategorie je prostý průměr jejích indikátorů. Výška je vážený součet kategorií.</p>') +
         sec("02", "Jak jisté jsou buňky", "počet buněk podle jistoty", cert_t + '<p class="zcap">Odhad u A a A2 je K2 (přechod do haly v plánu chybí) a D2 (indexace vlastních nákladů). Budoucnosti na SI3 mají u těchto buněk šum 1,5 bodu.</p>') +
         sec("03", "Co z matice plyne", "jen z matice, bez mapy", claims_html))
conv2 = ada("10:31", ["Matice je hotová. Každá buňka má pravidlo, zdroj a jistotu. Kliknutím na buňku uvidíte výpočet.",
                      "<b>B2 vychází nejvýš (8,35).</b> To není doporučení. Pravidlo FR čte jen NPV a riziko ztráty, a tam vede C2. Matice přidává to, co pravidlo nečte: závislost, měnu, vratnost."])
btn2 = BTN_MENU + '<a class="btn primary sm" href="SI3OptionsMap.dc.html">Mapa možností<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI2Matrix.dc.html", "w").write(frame("Sociomapa z indikátorů: matice skóre", "Matice skóre: možnosti", "Sociomapa · matice skóre", conv2,
                                                    "Matice skóre", btn2, body2, ("SI1Method.dc.html", "Metoda"), ("SI3OptionsMap.dc.html", "Mapa možností"), "SI2 Matice", 2270))

# ============ SI3 ============
svg_o = terrain_svg(ro, {"aria": "Sociomapa možností z indikátorů", "names": [OS[o] for o in ro["objs"]]}, links=links(ro))
s3_map = f'<div class="mapw"><div>{svg_o}<p class="zcap">Blízko sebe = podobný profil přes 9 kategorií (z-skóre). Výška = vážený součet. Body bližší než 46 px jsou odsunuté kvůli čitelnosti. Čára jen tam, kde |r| ≥ {cz(ro["rcrit"],2)}: to při 9 kategoriích projde na p &lt; 0,05. Prošly {len(links(ro))} z 21 dvojic.</p></div>{mapleg(ro, ON, OS)}</div>'
XB2, XB = ro["crossings"]["C2>B2"], ro["crossings"]["C2>B"]
sweep = (f'<div class="claim"><span class="n">!</span><div>C2 předběhne B2 až při váze Ekonomiky <b>{cz(XB2, 3)}</b> (schváleno 0,22).'
         f'<span class="w">ostatní váhy klesají v poměru · B zůstává před C2 jen do {cz(XB, 3)}, pak je C2 druhá · při schválených vahách vede B2 ve všech 2 000 budoucnostech</span></div></div>')
claims3 = [("A a B mají opačný profil", "r = −0,71: kde hala boduje (závislost, slib), B ne, a naopak; A a A2 mají profil podobný, r = 0,70"),
           ("A a C stojí nejdál od sebe", "r = −0,76: vlastní provoz proti zahraničnímu dodavateli"),
           ("B2 stojí sama a nejvýš", "s žádnou možností nemá spolehlivou čáru; vyhrává v každé budoucnosti"),
           ("Mapa neříká, co doporučit", "doporučení dává pravidlo FR nad Modelem (C2); mapa ukazuje, co za to klient platí")]
claims3_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims3))
body3 = (WARN + sec("01", "Mapa možností", "7 objektů · 9 kategorií · výška = vážený součet", s3_map) +
         sec("02", "Budoucnosti: kdo je nejlepší, když se váhy a nejisté buňky hýbou", "2 000 budoucností · váhy kolem schválených · šum podle jistoty",
             scen_bars(ro, ON) + sweep) +
         sec("03", "Podobnost profilů", "číslo 0–10 jako v analýze cloudu · r profilu · s = souběh v budoucnostech",
             sim_table(ro, OS) + f'<p class="zcap">Podbarvené: |r| ≥ {cz(ro["rcrit"],2)}. Souběh s je korelace součtů napříč budoucnostmi po odečtení průměru budoucnosti; kladný = daří se jim ve stejných budoucnostech.</p>') +
         sec("04", "Co mapa tvrdí a co ne", "tvrzení do osnovy zprávy", claims3_html))
conv3 = ada("10:48", ["Mapa ukazuje tři spolehlivé čáry z 21. Ostatní dvojice se od nuly při 9 kategoriích odlišit nedají, tak je nekreslím.",
                      f"Nejdůležitější je řádek v části 02: <b>C2 předběhne B2 až při váze Ekonomiky {cz(XB2, 2)}</b>. Rozdíl mezi Modelem a maticí je tedy otázka vah, ne chyba."],
            "Co z toho řekneme FR?", "10:50",
            ["Že pravidlo doporučí C2 a mapa ukáže cenu: dva noví dodavatelé, EUR a smlouva na 7 let. A že B2 je pojistka, která vyhraje, kdykoli váha peněz klesne pod polovinu."])
btn3 = BTN_MENU + '<a class="btn primary sm" href="SI4Suppliers.dc.html">Mapa dodavatelů<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI3OptionsMap.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa možností", "Mapa možností", "Sociomapa · mapa možností", conv3,
                                                        "Mapa možností", btn3, body3, ("SI2Matrix.dc.html", "Matice skóre"), ("SI4Suppliers.dc.html", "Mapa dodavatelů"), "SI3 Mapa možností", 2260))

# ============ SI4 ============
objs_t = [("Delta Fulfillment CZ", "Modřice", "dnešní 3PL", "smlouva, faktury 2025"),
          ("Wisła Fulfilment", "Katovice", "nabídka C", "nabidka_3PL_PL.pdf"),
          ("Vlastní provoz Velis", "Jihlava", "hala A", "nabidka_hala.pdf"),
          ("Morava Fulfil*", "Ostrava", "našla Rešerše", "veřejný ceník a podmínky*"),
          ("Polaris Logistyka*", "Wrocław", "našla Rešerše", "veřejný ceník*"),
          ("Dunaj 3PL*", "Bratislava", "našla Rešerše", "jen web*")]
s4_objs = '<table class="zt"><thead><tr><th>Dodavatel</th><th>Sklad</th><th>Proč na mapě</th><th>Podklad</th></tr></thead><tbody>' + "".join(
    f"<tr><td><b>{e(a)}</b></td><td>{e(b)}</td><td>{e(c)}</td><td>{e(d)}</td></tr>" for a, b, c, d in objs_t) + "</tbody></table>"
s4_objs += '<p class="zcap">* Smyšlení dodavatelé pro ukázku. V ostré studii je najde Rešerše a u každé hodnoty bude citace. Rychlík Kurýr na mapě není: je to dopravce, ne sklad.</p>'
svg_s = terrain_svg(rs, {"aria": "Sociomapa dodavatelů fulfilmentu", "names": [SS[o] for o in rs["objs"]]}, links=links(rs))
s4_map = f'<div class="mapw"><div>{svg_s}<p class="zcap">Vlastní provoz a Morava mají skoro stejné místo; odsunuté kvůli čitelnosti. 7 kategorií: čára jen při |r| ≥ {cz(rs["rcrit"],2)}. Prošly {len(links(rs))} z 15 dvojic.</p></div>{mapleg(rs, SN, SS)}</div>'
claims4 = [(f"Delta vede: {cz(rs['total'][0], 2)}, nejlepší v {cz(rs['best'][0]*100, 0)} % budoucností", "smlouva má všech 5 podmínek z checklistu a historie je doložená"),
           (f"Wisła a Polaris mají podobný profil (r = {cz(rs['R'][1][4], 2)})", "levnější, dál, v cizí měně, slabší smlouva"),
           ("Část náskoku Delty je náskok v dokladech", "Dunaj má 5 z 11 buněk Odhad a 4 Nízká; Rešerše by ho mohla posunout"),
           (f"Vlastní provoz je druhý ({cz(rs['total'][2], 2)})", "47,1 Kč na objednávku a nejblíž Praze, ale kapacita jen 0,83 potřeby roku 2032")]
claims4_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims4))
body4 = (WARN + sec("01", "Koho mapa porovná", "6 skladů pro e-shop Velis", s4_objs) +
         sec("02", "Katalog indikátorů: mapa dodavatelů", "7 kategorií · 11 indikátorů · stejná pravidla", catalogue(ss)) +
         sec("03", "Matice skóre", "skóre 1–10 · jistota · vstupní hodnota", matrix(ss, rs, SS) + CT_LEG) +
         sec("04", "Mapa dodavatelů", "výška = vážený součet", s4_map) +
         sec("05", "Budoucnosti", "2 000 budoucností · váhy a nejisté buňky se hýbou", scen_bars(rs, SN)) +
         sec("06", "Co mapa tvrdí a co ne", "a co doplnit před závěrem", claims4_html +
             '<div class="zhand" style="margin-top:10px"><i class="ph ph-magnifying-glass"></i><div><b>Další krok pro Rešerši:</b> ceník a smlouva Dunaj 3PL a kapacita Delty. To jsou buňky, které nejvíc hýbou pořadím.</div></div>'))
conv4 = ada("11:05", ["Stejná metoda, jiné objekty: šest skladů. Tři znám z dokumentů klienta, tři našla Rešerše. Ty jsou v ukázce smyšlené a označené hvězdičkou.",
                      "Pozor na <b>náskok v dokladech</b>. Delta má skoro všechno doložené, Dunaj skoro nic. Pravidla 3 a 4 za chybějící údaj nedají body navíc, takže málo prozkoumaný dodavatel vyjde hůř. Než to dáme do zprávy, doplním Dunaj."])
btn4 = BTN_MENU + '<a class="btn primary sm" href="MV4XRay.dc.html">Osnova zprávy<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI4Suppliers.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa dodavatelů", "Mapa dodavatelů", "Sociomapa · mapa dodavatelů", conv4,
                                                       "Mapa dodavatelů", btn4, body4, ("SI3OptionsMap.dc.html", "Mapa možností"), ("MV4XRay.dc.html", "Osnova zprávy"), "SI4 Mapa dodavatelů", 3850))
print("ok")
