"""Writes SI1-SI4 into the canvas folder from MV3's frame and the two computed maps.

Run from this folder: python3 specs.py; python3 compute.py spec_options.json res_options.json;
python3 compute.py spec_suppliers.json res_suppliers.json; python3 build.py
"""
import json, html, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
.art .abody{max-width:none}
.tl{display:flex;flex-direction:column;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.tl .tr{display:grid;grid-template-columns:34px 170px repeat(3,minmax(0,1fr));gap:14px;padding:12px 16px;border-top:1px solid var(--border);font-size:13.5px;line-height:20px;background:var(--raised);align-items:start}
.tl .tr:first-child{border-top:0}
.tl .tr.you{background:var(--youwash)}
.tl .n{font:600 13px/20px var(--mono);color:var(--signal)}
.tl .nm{display:flex;flex-direction:column}.tl .nm b{font-size:14.5px}.tl .nm span{font-size:12px;color:var(--muted)}
.tl .lb{display:block;font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.05em}
.cat{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:14px;background:var(--raised)}
.cat .ch{display:flex;align-items:center;gap:12px;padding:10px 16px;background:var(--sunken)}
.cat .ch b{font-size:14.5px}
.wbar{width:110px;height:8px;border-radius:4px;background:var(--border);overflow:hidden;display:inline-block}.wbar i{display:block;height:100%;background:var(--signal)}
.wv{font:600 12.5px var(--mono)}.why{font-size:12.5px;color:var(--muted)}
.ind{display:grid;grid-template-columns:250px minmax(0,1fr);gap:18px;padding:14px 16px;border-top:1px solid var(--border)}
.il{display:flex;flex-direction:column;gap:5px;font-size:13.5px}
.il .code{font:600 12px var(--mono);color:var(--signal)}
.tags{display:flex;flex-wrap:wrap;gap:4px}.itg{font-size:11px;background:var(--sunken);color:var(--muted);border-radius:4px;padding:2px 6px}.itg.k{background:var(--swash);color:var(--signal)}
.il .inote{font-size:12px;color:var(--muted);line-height:17px}
.scale{display:flex;flex-direction:column;gap:5px}
.su{font-size:11.5px;color:var(--muted)}
.strip{display:flex;gap:5px;flex-wrap:wrap}
.seg{flex:1 1 0;min-width:96px;border-radius:6px;border:1px solid var(--border);padding:7px 9px;display:flex;flex-direction:column;gap:4px;background:var(--surface)}
.seg.wide{flex:1 1 100%}
.seg.hi{background:var(--swash);border-color:color-mix(in srgb,var(--signal) 35%,var(--border))}
.seg.lo{background:var(--youwash);border-color:color-mix(in srgb,var(--you) 35%,var(--border))}
.seg.ex{background:var(--sunken);color:var(--muted)}
.seg.est{border-style:dashed}
.seg .rg{font-size:12px;color:var(--muted);line-height:16px}
.seg .sc{font:600 18px/1.1 var(--mono)}.seg .sc.x{font:500 12px var(--sans)}
.seg .mem{display:flex;flex-wrap:wrap;gap:3px;min-height:18px}
.mb{font:500 11px/16px var(--mono);background:var(--raised);border:1px solid var(--border);border-radius:4px;padding:0 5px;white-space:nowrap}
.mb.none{color:var(--faint);border-color:transparent;background:transparent}
.tool{margin-bottom:16px}.tool h3{margin:0 0 8px;font-size:15px}
.fgrid{display:grid;gap:10px}
.fc{display:flex;flex-direction:column;gap:8px;min-width:0}
.fh{display:flex;align-items:baseline;gap:8px;font-size:12.5px;color:var(--muted);padding-bottom:4px;border-bottom:2px solid var(--border)}
.fh b{font:600 15px var(--mono);color:var(--ink)}
.fd{border:1px solid var(--border);border-radius:8px;background:var(--raised);padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.fd.none{background:transparent;border-style:dashed;color:var(--faint);font-size:12.5px}
.fd .t{font-size:13.5px;font-weight:500;line-height:19px}
.fd .src{font-size:11.5px;color:var(--muted)}
.fd .to{display:flex;gap:5px;flex-wrap:wrap;align-items:center;font-size:12px;color:var(--muted)}
.ic{font:600 11px var(--mono);background:var(--swash);color:var(--signal);border-radius:4px;padding:2px 6px}
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
.plist{display:flex;flex-direction:column;gap:6px;font-size:13px}.plist div{display:flex;gap:10px;align-items:center}
.pr{font:600 12px var(--mono);border-radius:4px;padding:2px 6px;min-width:44px;text-align:center}.pr.w{background:#ffe9cf;color:#8a4a00}.pr.c{background:#dde9ff;color:#1d4f9c}
.ztag{font-size:11.5px;border-radius:4px;padding:2px 7px;margin-left:4px}.ztag.hi{background:var(--swash);color:var(--signal)}.ztag.lo{background:var(--youwash);color:var(--youink)}
"""


def frame(title, h1, aria, conv, sees, ahd_btns, body, prev, nxt, code, height):
    L = list(MV3)
    out = []
    for i, l in enumerate(L, 1):
        if i == 5:
            l = f"<title>{e(title)}</title>"
        if l.startswith("</style>") and i < 160:
            l = EXTRA_CSS + l
        if i == 172:
            l = l.replace('class="leadx"', 'class="leadx" checked=""')
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
        return cz(v, 2).rstrip("0") if abs(v) < 2 else cz(v, 1)
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


LOOK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "look.json")))


def tone(score):
    return "hi" if score >= 8 else ("lo" if score <= 3 else "mid")


def sc_txt(x):
    return cz(x, 0) if float(x).is_integer() else cz(x, 1)


def band_of(v, cuts):
    for k, (up, _) in enumerate(cuts):
        if v <= up:
            return k
    return len(cuts)


def seg(label, score, members, extra=""):
    mem = "".join(f'<span class="mb">{e(m)}</span>' for m in members) or '<span class="mb none">—</span>'
    sc = f'<span class="sc">{sc_txt(score)}</span>' if score is not None else '<span class="sc x">vyřazeno</span>'
    return f'<div class="seg {tone(score) if score is not None else "ex"} {extra}"><span class="rg">{e(label)}</span>{sc}<span class="mem">{mem}</span></div>'


def scale(ind, look, res, short):
    sc = res["scores"][ind["code"]]
    objs = res["objs"]
    known = [o for o in objs if sc[o]["raw"] is not None]
    missing = [o for o in objs if sc[o]["raw"] is None]
    unit = ""
    segs = []
    if ind["kind"] == "pásmo":
        unit = look.get("unit", "")
        for k, ((up, score), lab) in enumerate(zip(ind["cuts"], look["bands"])):
            segs.append(seg(lab, score, [f'{short[o]} {fmt_raw(sc[o]["raw"])}' for o in known if band_of(sc[o]["raw"], ind["cuts"]) == k]))
        if look.get("excluded"):
            segs.append(seg(look["excluded"], None, [], "ex"))
    elif ind["kind"] == "slovní":
        for lab, score, mem in look["levels"]:
            segs.append(seg(lab, score, [short[o] for o in mem]))
    elif ind["kind"] == "checklist":
        n = ind["items"]
        unit = f"splněno z {n}"
        for k in range(n + 1):
            segs.append(seg(f"{k} z {n}", 1 + 9 * k / n, [short[o] for o in known if sc[o]["raw"] == k]))
    else:
        unit = "skóre = hodnota"
        segs.append('<div class="seg mid wide"><span class="rg">hodnota se použije přímo</span><span class="mem">' +
                    "".join(f'<span class="mb">{e(short[o])} {sc_txt(sc[o]["score"])}</span>' for o in known) + "</span></div>")
    if missing:
        med = sc[missing[0]]["score"]
        segs.append(seg("chybí → medián", med, [short[o] for o in missing], "est"))
    head = f'<span class="su">{e(unit)}</span>' if unit else ""
    return f'<div class="scale">{head}<div class="strip">{"".join(segs)}</div></div>'


KIND_WORDS = {"pásmo": "číselná pásma", "slovní": "slovní škála", "checklist": "checklist", "přímo": "přímo z dat"}


def catalogue(spec, res, short, look):
    out = []
    for c in spec["categories"]:
        out.append(f'<div class="cat"><div class="ch"><b>{e(c["name"])}</b><span class="wbar"><i style="width:{c["w"]*100/0.25:.0f}%"></i></span>'
                   f'<span class="wv">{cz(c["w"]*100,0)} %</span><span class="why">{e(c["why"])}</span></div>')
        for ind in c["indicators"]:
            note = ""
            if ind["kind"] == "checklist":
                note = f'<span class="inote">{e(ind["rule"].split(";")[0])}</span>'
            elif ind["kind"] == "přímo":
                note = f'<span class="inote">{e(ind["rule"])}</span>'
            out.append(f'<div class="ind"><div class="il"><span class="code">{ind["code"]}</span><b>{e(ind["name"])}</b>'
                       f'<span class="tags"><span class="itg">{e(ind["from"])}</span><span class="itg k">{KIND_WORDS[ind["kind"]]}</span></span>{note}</div>'
                       f'{scale(ind, look.get(ind["code"], {}), res, short)}</div>')
        out.append("</div>")
    out.append('<p class="zcap">Každý dílek je jedno pásmo nebo situace: nahoře rozsah, uprostřed skóre 1–10, dole možnosti, které do něj padly, s hodnotou. '
               'Hodnota přesně na hranici dostane lepší skóre. Barva: zelená 8 a víc, oranžová 3 a míň.</p>')
    return "".join(out)


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


BTN_MENU = ('<details class="mnu"><summary class="btn quiet sm ic" aria-label="Další akce" title="Další akce"><i class="ph ph-dots-three"></i></summary><div class="mnu-p" role="menu">'
            '<button type="button"><i class="ph ph-download-simple s"></i>Stáhnout matici (XLSX)</button><a href="MV5Validation.dc.html"><i class="ph ph-book-open s"></i>Metoda v Metodice</a></div></details>')
WARN = '<div class="zbar warn"><i class="ph ph-lock-simple"></i>Interní · metoda „Sociomapa z indikátorů“ čeká na zápis metodika do registru · hodnoty z Modelu jsou ukázkové z tohoto prototypu.</div>'

ON = {o["id"]: o["name"] for o in so["objects"]}
OS = {o: o for o in ON}
SN = {o["id"]: o["name"] for o in ss["objects"]}
SS = {"DE": "Delta", "WI": "Wisła", "VL": "Vlastní", "MO": "Morava*", "PO": "Polaris*", "DU": "Dunaj*"}

# ============ SI1 ============
steps = [("1", "Zadání", "Ada", "cíl, pravidlo a podmínky klienta", "navrhne kategorie a jejich váhy", "kategorie s váhou a důvodem"),
         ("2", "Rešerše", "Ada · Deep Research", "SWOT, PESTEL, Porter, veřejné zdroje", "nálezy převede na indikátory a pásma", "indikátor, pásmo a citace"),
         ("3", "Data", "kód", "soubory klienta", "tvrdé hodnoty použije přímo", "hodnota se souborem a řádkem"),
         ("4", "Schválení", "výzkumník", "návrh metody", "upraví, schválí a zamkne před prvním skóre", "zamčená verze v záznamu"),
         ("5", "Výpočet", "kód", "zamčená metoda a hodnoty", "skóre, výška, mapa, budoucnosti", "matice, mapa, tvrzení")]
s1_io = ('<div class="tl">' + "".join(
    f'<div class="tr{" you" if who == "výzkumník" else ""}"><span class="n">{k}</span><div class="nm"><b>{e(n)}</b><span>{e(who)}</span></div>'
    f'<div><span class="lb">vstup</span>{e(i)}</div><div><span class="lb">proces</span>{e(p)}</div><div><span class="lb">výstup</span><b>{e(o)}</b></div></div>'
    for k, n, who, i, p, o in steps) + "</div>")

rules = [("1", "Tvrdá data se použijí přímo", "Tvrdá data se použijí přímo", "beze změny", "X1 průměr manažerů 6,60 pro A"),
         ("2", "Neověřená znalost = Střední", "Neověřený úsudek = Střední, bez dokladu Nízká", "zpřesněno", "D1, P1 slovní škály"),
         ("3", "Chybí číslo = medián ostatních (Odhad)", "Chybí číslo = medián ostatních (Odhad)", "beze změny", "K2 přechod do haly: v plánu přechodu chybí"),
         ("4", "Nezdokumentovaná služba = nenabízí", "Nezdokumentovaná podmínka nebo služba = nesplněno", "beze změny", "checklisty dodavatelů"),
         ("5", "Nezdokumentované zdražení = 0 %", "Nezdokumentované zdražení = medián ostatních (Odhad)", "upraveno", "0 % by odměnilo dodavatele, který mlčí"),
         ("6", "Žádný hlášený výpadek = 8, ne 10", "Žádný hlášený výpadek = 8; 9 jen s dokladem", "zpřesněno", "R1: Delta 9 z faktur bez slev")]
s1_rules = '<table class="zt"><thead><tr><th>#</th><th>V analýze cloudu</th><th>Ve studii Velis</th><th>Stav</th><th>Kde to působí</th></tr></thead><tbody>' + "".join(
    f'<tr{" class=\"miss\"" if st == "upraveno" else ""}><td class="num">{n}</td><td>{e(a)}</td><td><b>{e(b)}</b></td><td>{e(st)}</td><td style="font-size:12.5px;color:var(--muted)">{e(w)}</td></tr>' for n, a, b, st, w in rules) + "</tbody></table>"

def fcard(t, src, to):
    chips = "".join(f'<span class="ic">{e(c)}</span>' for c in to[0])
    return f'<div class="fd"><span class="t">{e(t)}</span><span class="src">{e(src)}</span><span class="to"><i class="ph ph-arrow-right"></i>{chips}<span>{e(to[1])}</span></span></div>'


EMPTY = '<div class="fd none">Nic, co by měnilo skóre.</div>'
PESTEL = [("P", "Politické", []), ("E", "Ekonomické", [("Mzdy v dopravě a skladování rostou", "Rešerše · ČSÚ, GUS", (["P1"], "slovní škála citlivosti")),
                                                   ("Wisła fakturuje v EUR", "nabidka_3PL_PL.pdf s. 1", (["P2", "L2"], "slovní škála měny"))]),
          ("S", "Sociální", [("46 % zákazníků je pod 35 let a čeká rychlé doručení", "zakaznici_souhrn_2025.xlsx", (["váha S"], "Slib a zákazníci 16 %"))]),
          ("T", "Technologické", []), ("E", "Ekologické", []),
          ("L", "Legislativní", [("Výpověď 6 měsíců", "smlouva s. 8 · zákon 89/2012 Sb.", (["F1", "T1"], "vratnost a začátek")),
                                 ("Daň 21 % a odpisová skupina haly", "zákon 586/1992 Sb.", (["E1"], "přes NPV v Modelu"))])]
PORTER = [("Dodavatelé", [("Jediný 3PL, indexace 3–7 % ročně", "smlouva s. 6", (["D1", "D2"], "závislost a indexace"))]),
          ("Rivalita", [("Konkurence doručuje ve městech druhý den", "Rešerše", (["S1"], "1 den = norma trhu"))]),
          ("Odběratelé", [("Po zpoždění o den odejde 3,6 % objednávek", "zpozdeni_2024.xlsx", (["S2"], "pásmo ztráty"))]),
          ("Substituty", []), ("Noví hráči", [])]
SWOT = [("S", "Silné stránky", [("Povolení haly je pravomocné", "nabidka_hala.pdf s. 2", (["T1"], "začátek 1. 1. 2028"))]),
        ("W", "Slabé stránky", [("Hotovost 4 mil. Kč, EBITDA 27,3 mil. Kč", "vysledovka_rozvaha_2023-2025.xlsx", (["K1"], "pásmo investice"))]),
        ("O", "Příležitosti", [("Polský 3PL je o 6 Kč levnější na objednávku", "nabidka_3PL_PL.pdf s. 1–3", (["E1"], "přes NPV v Modelu"))]),
        ("T", "Hrozby", [("Český 3PL zdražuje o 3–7 % ročně", "smlouva s. 6", (["D2"], "pásmo indexace"))])]


def tool(title, cols, n):
    body = "".join(f'<div class="fc"><div class="fh"><b>{e(k)}</b>{e(name)}</div>{"".join(fcard(*f) for f in fs) or EMPTY}</div>'
                   for k, name, fs in cols)
    return f'<div class="tool"><h3>{e(title)}</h3><div class="fgrid" style="grid-template-columns:repeat({n},minmax(0,1fr))">{body}</div></div>'


s1_finds = (tool("PESTEL", PESTEL, 6) + tool("Porter · pět sil", [(str(k + 1), n, f) for k, (n, f) in enumerate(PORTER)], 5) + tool("SWOT", SWOT, 4) +
            '<p class="zcap">Nálezy se nesčítají: počet silných stránek nic neměří. Každý nález se stane indikátorem s pravidlem, nebo zdůvodní pásmo či váhu. '
            'Prázdné pole znamená, že Rešerše nenašla nic, co by měnilo skóre.</p>')

body1 = (WARN + sec("01", "Jak vznikne metoda pro tuto studii", "vstup → proces → výstup", s1_io) +
         sec("02", "Šest pravidel bodování", "převzato z analýzy cloudu", s1_rules) +
         sec("03", "SWOT, PESTEL a Porter jako vstupy", "z Rešerše a Zadání (Z4)", s1_finds) +
         sec("04", "Katalog indikátorů: mapa možností", "9 kategorií · 15 indikátorů · návrh Ady, schváleno 5. 11.", catalogue(so, ro, OS, LOOK["options"]) +
             '<p class="zcap">Katalog mapy dodavatelů je na <a href="SI4Suppliers.dc.html">SI4</a>. Stejná metoda, jiné indikátory.</p>'))
conv1 = ada("10:12", ["Metodu jsem ušila na rozhodnutí Velis. Kategorie a váhy vycházejí z pravidla FR: <b>Ekonomika 22 %</b>, <b>Slib a zákazníci 16 %</b>, ostatní pod tím.",
                      "Pásma mají zdroj: z dokumentů klienta, z Rešerše, nebo jsou označená jako úsudek. Upravila jsem pravidlo 5: zdražení, které dodavatel nezveřejní, nepočítám jako 0 %."],
            "Můžeme váhy měnit, až uvidíme výsledky?", "10:14",
            ["Ne potichu. Metodu jsem zamkla před prvním skóre. Každá změna je nová verze s důvodem a mapa ukáže obě. Jak moc pořadí na vahách visí, ukážou budoucnosti na SI3."])
btn1 = BTN_MENU + '<a class="btn primary sm" href="SI2Matrix.dc.html">Matice skóre<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI1Method.dc.html", "w").write(frame("Sociomapa z indikátorů: metoda", "Sociomapa z indikátorů: metoda", "Sociomapa · metoda", conv1,
                                                    "Sociomapa · metoda", btn1, body1, ("MV3SystemMap.dc.html", "Sociomapa systémů"), ("SI2Matrix.dc.html", "Matice skóre"), "SI1 Metoda", 4530))

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
                                                    "Matice skóre", btn2, body2, ("SI1Method.dc.html", "Metoda"), ("SI3OptionsMap.dc.html", "Mapa možností"), "SI2 Matice", 2240))

# ============ the aia-sociomap-5 engine's maps (engine_maps.py) ============
ENG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.json")))
BLOB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine_assets.json")))
METHOD_WORDS = {"soft_rank_spearman_coulomb": "soft-rank Spearman s Coulombem (BB1)", "interval_mds": "Interval MDS"}


def reliable(key):
    return sorted((p for p in ENG[key]["pairs"] if p[2] == "reliable"), key=lambda p: -abs(p[3]))


def img(name, alt):
    return f'<div class="zstage"><img src="/_blob/{BLOB[name]}" alt="{e(alt)}"></div>'


def eng_facts(key, rows):
    v = ENG[key]
    c = v["credibility"]
    m = len(v["heights"])
    n = m * (m - 1) // 2
    seg = v["segments"] or {}
    seg_words = {"TOO_FEW_RESPONDENTS": "nepočítají se (málo řádků)", "NO_CLEAR_SEGMENTS": "žádné zřetelné"}.get(seg.get("reason"), "—")
    verdict = ('<span class="ztag lo">slabě určená</span>' if c["weakly_determined"] else '<span class="ztag hi">určená</span>')
    rows_html = "".join(f'<div class="zrow"><span class="zk">{e(k)}</span><span class="zv">{x}</span></div>' for k, x in (
        ("Řádky mapy", e(rows)),
        ("Rozložení", e(METHOD_WORDS.get(v["method"], v["method"] or "—"))),
        ("Věrohodnost", f'split-half {cz(c["split_half"], 2)} · práh {cz(c["threshold"], 2)} · {verdict}'),
        ("Spolehlivé dvojice", f'{c["reliable_pairs"]} z {n} (Benjamini–Hochberg)'),
        ("Segmenty", e(seg_words)),
    ))
    return f'<div class="zcard"><h3>Co spočítal engine</h3>{rows_html}</div>'


def pair_list(key, names, k=6):
    ps = reliable(key)[:k]
    if not ps:
        return '<p class="zcap">Žádná dvojice neprošla.</p>'
    return '<div class="plist">' + "".join(
        f'<div><span class="pr {"w" if r > 0 else "c"}">{cz(r, 2)}</span>{e(names[a])} ↔ {e(names[b])}</div>' for a, b, _, r in ps) + "</div>"


def engine_section(map_key, kind, names, rows, caption):
    key = f"{map_key}/{kind}"
    figs = f'<div class="zgrid2">{img(f"si-{map_key}-{kind}-top", "pohled shora")}{img(f"si-{map_key}-{kind}-3d", "pohled z boku")}</div>'
    side = eng_facts(key, rows) + '<div class="zcard"><h3>Nejsilnější spolehlivé dvojice</h3>' + pair_list(key, names) + \
        '<p class="zcap">teplá: daří se jim spolu · studená: když jedné, druhé ne</p></div>'
    if kind == "budoucnosti":
        third = f'<div class="zgrid2" style="margin-top:12px">{img(f"si-{map_key}-{kind}-respondents", "budoucnosti jako body")}<div class="zlead" style="gap:12px">{side}</div></div>'
    else:
        third = f'<div class="zgrid2" style="margin-top:12px">{side}</div>'
    return figs + third + f'<p class="zcap">{caption}</p>'


FUT_CAVEAT = ("Spočítal engine aia-sociomap-5 a nakreslil renderer AIA, kterým zpráva kreslí mapy. Místo respondentů jsou řádky 2 000 budoucností "
              "s vahami a nejistými buňkami podle jistoty; v pohledu s body engine nazývá budoucnosti respondenty. Pozor: spolehlivost dvojic tu "
              "roste s počtem budoucností, který volíme my, ne s počtem lidí. Statistika enginu je stavěná na respondenty, proto mapa zůstává interní.")
PROF_CAVEAT = ("Řádky jsou indikátory: každý „hodnotí“ všechny objekty 1–10, jako v analýze cloudu. Mapa staví k sobě objekty, které bodují podobně napříč indikátory.")

# ============ SI3 ============
XB2, XB = ro["crossings"]["C2>B2"], ro["crossings"]["C2>B"]
sweep = (f'<div class="claim"><span class="n">!</span><div>C2 předběhne B2 až při váze Ekonomiky <b>{cz(XB2, 3)}</b> (schváleno 0,22).'
         f'<span class="w">ostatní váhy klesají v poměru · B zůstává před C2 jen do {cz(XB, 3)}, pak je C2 druhá · při schválených vahách vede B2 ve všech 2 000 budoucnostech</span></div></div>')
_rf = reliable("options/budoucnosti")
_pos = [p for p in _rf if p[3] > 0]
_neg = [p for p in _rf if p[3] < 0]
_prof = reliable("options/profil")
_pc = ENG["options/profil"]["credibility"]
claims3 = [(f"{ON[_pos[0][0]]} a {ON[_pos[0][1]]} se daří ve stejných budoucnostech (r = {cz(_pos[0][3], 2)})",
            "nejsilnější kladná dvojice na mapě budoucností; " + ", ".join(f"{a}–{b} {cz(r, 2)}" for a, b, _, r in _pos[1:3])),
           (f"Nejsilněji proti sobě: {ON[_neg[0][0]]} a {ON[_neg[0][1]]} (r = {cz(_neg[0][3], 2)})",
            "když se daří jedné, druhé ne; dál " + ", ".join(f"{a}–{b} {cz(r, 2)}" for a, b, _, r in _neg[1:4])),
           (f"Mapa profilu je slabě určená (split-half {cz(_pc['split_half'], 2)}, práh {cz(_pc['threshold'], 2)})",
            "z 15 indikátorů tvrdíme jen " + (", ".join(f"{a} a {b} (r = {cz(r, 2)})" for a, b, _, r in _prof) or "nic") + "; víc indikátorů by ji zpevnilo"),
           ("Mapa neříká, co doporučit", "doporučení dává pravidlo FR nad Modelem (C2); mapa ukazuje, co za to klient platí")]
claims3_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims3))
body3 = (WARN + sec("01", "Mapa budoucností", "aia-sociomap-5 · 2 000 budoucností jako řádky · 7 objektů",
                    engine_section("options", "budoucnosti", ON, "2 000 budoucností (součty 1–10)", FUT_CAVEAT)) +
         sec("02", "Mapa profilu z indikátorů", "aia-sociomap-5 · 15 indikátorů jako řádky",
             engine_section("options", "profil", ON, "15 indikátorů (skóre 1–10)", PROF_CAVEAT)) +
         sec("03", "Budoucnosti: kdo je nejlepší, když se váhy a nejisté buňky hýbou", "2 000 budoucností · váhy kolem schválených · šum podle jistoty",
             scen_bars(ro, ON) + sweep) +
         sec("04", "Podobnost profilů", "číslo 0–10 jako v analýze cloudu · r profilu · s = souběh v budoucnostech",
             sim_table(ro, OS) + f'<p class="zcap">Podbarvené: |r| ≥ {cz(ro["rcrit"],2)}. Souběh s je korelace součtů napříč budoucnostmi po odečtení průměru budoucnosti; kladný = daří se jim ve stejných budoucnostech.</p>') +
         sec("05", "Co mapy tvrdí a co ne", "tvrzení do osnovy zprávy", claims3_html))
conv3 = ada("10:48", [f"Obě mapy spočítal engine aia-sociomap-5. Mapa budoucností je věrohodná (split-half {cz(ENG['options/budoucnosti']['credibility']['split_half'], 2)}), mapa profilu z 15 indikátorů ne ({cz(_pc['split_half'], 2)} pod prahem {cz(_pc['threshold'], 2)}).",
                      f"Nejdůležitější je řádek v části 03: <b>C2 předběhne B2 až při váze Ekonomiky {cz(XB2, 2)}</b>. Rozdíl mezi Modelem a maticí je tedy otázka vah, ne chyba."],
            "Co z toho řekneme FR?", "10:50",
            ["Že pravidlo doporučí C2 a mapa ukáže cenu: dva noví dodavatelé, EUR a smlouva na 7 let. A že B2 vyhraje, kdykoli váha peněz klesne pod polovinu."])
btn3 = BTN_MENU + '<a class="btn primary sm" href="SI4Suppliers.dc.html">Mapa dodavatelů<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI3OptionsMap.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa možností", "Mapa možností", "Sociomapa · mapa možností", conv3,
                                                        "Mapa možností", btn3, body3, ("SI2Matrix.dc.html", "Matice skóre"), ("SI4Suppliers.dc.html", "Mapa dodavatelů"), "SI3 Mapa možností", 3600))

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
claims4 = [(f"Delta vede: {cz(rs['total'][0], 2)}, nejlepší v {cz(rs['best'][0]*100, 0)} % budoucností", "smlouva má všech 5 podmínek z checklistu a historie je doložená"),
           (f"Wisła a Polaris se daří ve stejných budoucnostech (r = {cz([p for p in reliable('suppliers/budoucnosti') if {p[0], p[1]} == {'WI', 'PO'}][0][3], 2)})", "levnější, dál, v cizí měně, slabší smlouva; mapa profilu z 11 indikátorů nemá žádnou spolehlivou dvojici"),
           ("Část náskoku Delty je náskok v dokladech", "Dunaj má 5 z 11 buněk Odhad a 4 Nízká; Rešerše by ho mohla posunout"),
           (f"Vlastní provoz je druhý ({cz(rs['total'][2], 2)})", "47,1 Kč na objednávku a nejblíž Praze, ale kapacita jen 0,83 potřeby roku 2032")]
claims4_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims4))
body4 = (WARN + sec("01", "Koho mapa porovná", "6 skladů pro e-shop Velis", s4_objs) +
         sec("02", "Katalog indikátorů: mapa dodavatelů", "7 kategorií · 11 indikátorů · stejná pravidla", catalogue(ss, rs, SS, LOOK["suppliers"])) +
         sec("03", "Matice skóre", "skóre 1–10 · jistota · vstupní hodnota", matrix(ss, rs, SS) + CT_LEG) +
         sec("04", "Mapa budoucností", "aia-sociomap-5 · 2 000 budoucností jako řádky · 6 objektů",
             engine_section("suppliers", "budoucnosti", SN, "2 000 budoucností (součty 1–10)", FUT_CAVEAT)) +
         sec("05", "Mapa profilu z indikátorů", "aia-sociomap-5 · 11 indikátorů jako řádky",
             engine_section("suppliers", "profil", SN, "11 indikátorů (skóre 1–10)", PROF_CAVEAT)) +
         sec("06", "Budoucnosti", "2 000 budoucností · váhy a nejisté buňky se hýbou", scen_bars(rs, SN)) +
         sec("07", "Co mapy tvrdí a co ne", "a co doplnit před závěrem", claims4_html +
             '<div class="zhand" style="margin-top:10px"><i class="ph ph-magnifying-glass"></i><div><b>Další krok pro Rešerši:</b> ceník a smlouva Dunaj 3PL a kapacita Delty. To jsou buňky, které nejvíc hýbou pořadím.</div></div>'))
conv4 = ada("11:05", ["Stejná metoda, jiné objekty: šest skladů. Tři znám z dokumentů klienta, tři našla Rešerše. Ty jsou v ukázce smyšlené a označené hvězdičkou.",
                      "Pozor na <b>náskok v dokladech</b>. Delta má skoro všechno doložené, Dunaj skoro nic. Pravidla 3 a 4 za chybějící údaj nedají body navíc, takže málo prozkoumaný dodavatel vyjde hůř. Než to dáme do zprávy, doplním Dunaj."])
btn4 = BTN_MENU + '<a class="btn primary sm" href="MV4XRay.dc.html">Osnova zprávy<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI4Suppliers.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa dodavatelů", "Mapa dodavatelů", "Sociomapa · mapa dodavatelů", conv4,
                                                       "Mapa dodavatelů", btn4, body4, ("SI3OptionsMap.dc.html", "Mapa možností"), ("MV4XRay.dc.html", "Osnova zprávy"), "SI4 Mapa dodavatelů", 6240))
print("ok")
