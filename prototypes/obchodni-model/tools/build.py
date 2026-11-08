"""Writes SI1-SI4 (method v2) into the canvas folder from MV3's frame and the two computed maps.

Run from this folder: python3 specs.py; python3 compute.py spec_options.json res_options.json;
python3 compute.py spec_suppliers.json res_suppliers.json; (engine_maps.py); python3 build.py
The frame is MV3 as merged in b28ce0919 (its line numbers are what frame() edits), read from git.
"""
import json, html, sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MV3 = subprocess.run(["git", "show", "b28ce0919:prototypes/obchodni-model/MV3SystemMap.dc.html"], cwd=OUT,
                     capture_output=True, text=True, check=True).stdout.split("\n")
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


def sc_txt(x):
    return cz(x, 0) if float(x).is_integer() else cz(x, 1)


# ---------------- v2: states, ranges, gates, families ----------------
CT_LEG = ('<div class="zleg" style="margin-top:8px"><span>Jistota dokladu:</span><span>' + ct("Vysoká") + ' Vysoká: doklad klienta nebo výpočet</span><span>' + ct("Střední") +
          ' Střední: veřejný zdroj nebo ověřený úsudek</span><span>' + ct("Nízká") + ' Nízká: úsudek bez dokladu</span>'
          '<span><span class="unk">?</span> neznámo: rozsah, ne skóre</span><span><span class="na">n/a</span> neuplatní se</span></div>')
EXTRA_CSS += """
.unk{display:inline-flex;align-items:center;justify-content:center;min-width:15px;height:15px;border-radius:3px;font:700 10px/1 var(--mono);border:1px dashed var(--youink);color:var(--youink);padding:0 3px}
.na{font:500 10.5px/1 var(--mono);color:var(--faint)}
.smx td.s.u{background:repeating-linear-gradient(135deg,var(--surface),var(--surface) 5px,var(--sunken) 5px,var(--sunken) 10px)}
.smx tr.gate td{background:var(--raised)}
.gp{font:600 11px/1 var(--sans);border-radius:4px;padding:3px 6px;white-space:nowrap}.gp.pass{background:var(--swash);color:var(--signal)}.gp.fail{background:#fbe0dc;color:#9b2c1c}.gp.unknown{border:1px dashed var(--youink);color:var(--youink)}
.rng{display:flex;flex-direction:column;gap:7px}
.rng .b{display:grid;grid-template-columns:200px minmax(0,1fr) 230px;gap:10px;align-items:center;font-size:13px}
.rng .t{height:18px;background:var(--sunken);border-radius:4px;position:relative}
.rng .t i{position:absolute;top:3px;bottom:3px;background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--signal) 30%,transparent),color-mix(in srgb,var(--signal) 30%,transparent) 4px,transparent 4px,transparent 8px);border-radius:3px}
.rng .t em{position:absolute;top:1px;bottom:1px;width:4px;background:var(--signal);border-radius:1px}
.rng .b.out{color:var(--faint)}.rng .b.out .t em{background:var(--faint)}
.rng .v{font:500 12px var(--mono);color:var(--muted);text-align:right}
.fam td.num b{font:600 13px var(--mono)}
.fam td.lead{background:var(--swash)}
"""


def gate_pill(st):
    return f'<span class="gp {st}">{ {"pass": "splněno", "fail": "nesplněno", "unknown": "neznámo"}[st] }</span>'


def cell_html(ind, x):
    st = x["state"]
    if st == "na":
        return '<td class="s"><span class="na">n/a</span><small>neuplatní se</small></td>'
    if st == "unknown":
        return f'<td class="s u"><span class="unk">?</span><small>{sc_txt(x["lo"])}–{sc_txt(x["hi"])}</small></td>'
    if st == "partial":
        it = x["raw"]
        return (f'<td class="s u">{sc_txt(x["lo"])}–{sc_txt(x["hi"])}{ct(x["cert"])}<small>{it.count("y")} ano · {it.count("n")} ne · {it.count("?")} ?</small></td>')
    s = x["lo"]
    cls = "hi" if s >= 8 else ("lo" if s <= 3 else "")
    if ind["kind"] == "checklist":
        rw = f'{x["raw"].count("y")} z {len(x["raw"])}'
    elif ind["kind"] in ("slovní", "přímo"):
        rw = ""
    else:
        rw = fmt_raw(x["raw"])
    return f'<td class="s {cls}">{sc_txt(s)}{ct(x["cert"])}' + (f'<small>{rw}</small>' if rw else '') + '</td>'


def matrix(spec, res, short):
    objs = res["objs"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows = [f'<table class="smx"><thead><tr><th style="text-align:left">Brána / kritérium · indikátor</th>{th}</tr></thead><tbody>']
    for g in spec.get("gates", []):
        rows.append(f'<tr class="gate"><td class="l"><span class="mono" style="color:var(--faint)">{g["code"]}</span> {e(g["name"])}</td>' +
                    "".join(f'<td class="s">{gate_pill(g["values"][o][0])}</td>' for o in objs) + "</tr>")
    for ci, c in enumerate(spec["categories"]):
        for ind in c["indicators"]:
            rows.append(f'<tr><td class="l"><span class="mono" style="color:var(--faint)">{ind["code"]}</span> {e(ind["name"])}</td>' +
                        "".join(cell_html(ind, res["cells"][ind["code"]][o]) for o in objs) + "</tr>")
        cm = ""
        for oi in range(len(objs)):
            a, b = res["Mlo"][oi][ci], res["Mhi"][oi][ci]
            cm += '<td class="s">—</td>' if a is None or a != a else (f'<td class="s">{cz(a)}</td>' if a == b else f'<td class="s">{cz(a)}–{cz(b)}</td>')
        rows.append(f'<tr class="cat"><td class="l">{e(c["name"])} · váha {cz(res["W"][ci]*100,1)} %</td>{cm}</tr>')
    rows.append('<tr class="tot"><td class="l">Doložené minimum (neznámé na dolní mezi)</td>' + "".join(f'<td class="s">{cz(t, 2)}</td>' for t in res["total"]) + "</tr>")
    rows.append('<tr class="cat"><td class="l">Horní případ (neznámé na horní mezi)</td>' + "".join(f'<td class="s">{cz(t, 2)}</td>' for t in res["thi"]) + "</tr>")
    rows.append('<tr class="cat"><td class="l">Pokrytí vah doklady</td>' + "".join(f'<td class="s">{cz(c*100,0)} %</td>' for c in res["coverage"]) + "</tr></tbody></table>")
    return "".join(rows)


def gates_table(spec, short):
    objs = [o["id"] for o in spec["objects"]]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows = "".join(f'<tr><td><b>{g["code"]}</b> {e(g["name"])}<br><span style="font-size:12px;color:var(--muted)">{e(g["from"])}</span></td>' +
                   "".join(f'<td title="{e(g["values"][o][1])}">{gate_pill(g["values"][o][0])}<br><span style="font-size:11px;color:var(--faint)">{e(g["values"][o][1])}</span></td>' for o in objs) + "</tr>"
                   for g in spec["gates"])
    return f'<table class="zt"><thead><tr><th>Brána</th>{th}</tr></thead><tbody>{rows}</tbody></table>'


def ranges(res, names):
    objs = res["objs"]
    order = sorted(range(len(objs)), key=lambda i: (res["gate"][objs[i]] == "fail", -res["total"][i]))
    lo_s, hi_s = 2.0, 10.0
    out = ['<div class="rng">']
    for i in order:
        o = objs[i]
        a = (res["total"][i] - lo_s) / (hi_s - lo_s) * 100
        b = (res["thi"][i] - lo_s) / (hi_s - lo_s) * 100
        g = res["gate"][o]
        tag = {"pass": "", "fail": " · vyřazeno bránou", "unknown": " · brána neznámá"}[g]
        rng_t = cz(res["total"][i], 2) if res["thi"][i] == res["total"][i] else f'{cz(res["total"][i], 2)}–{cz(res["thi"][i], 2)}'
        out.append(f'<div class="b{" out" if g == "fail" else ""}"><span>{e(names[o])}</span><span class="t"><i style="left:{a:.1f}%;width:{max(b-a,0):.1f}%"></i><em style="left:{a:.1f}%"></em></span>'
                   f'<span class="v">{rng_t} · pokrytí {cz(res["coverage"][i]*100,0)} %{tag}</span></div>')
    out.append('<div class="zleg"><span>Čárka: doložené minimum · šrafovaný pruh: kam by mohly posunout chybějící doklady · stupnice 2–10</span></div></div>')
    return "".join(out)


FAM_WORDS = {
    "váhy": "váhy tří lidí z vedení a Dirichlet kolem schválených (koncentrace 20, 60, 200)",
    "důkazy": "šum skóre podle jistoty dokladu, tři rozptyly (Vysoká 0,1–0,5 bodu, Střední 0,5–1,5, Nízká 1–2,5)",
    "chybějící údaje": "každá neznámá buňka kdekoli ve svém rozsahu",
    "vše najednou": "vše výše zároveň, střední nastavení",
}


def families(res, short):
    objs = res["objs"]
    alive = [o for o in objs if res["gate"][o] != "fail"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in alive)
    rows = []
    for k, v in res["families"].items():
        best = max(v[objs.index(o)] for o in alive)
        cells = "".join(f'<td class="num{" lead" if v[objs.index(o)] == best and best > 0 else ""}"><b>{cz(v[objs.index(o)]*100,0)} %</b></td>' for o in alive)
        words = FAM_WORDS.get(k) or ("jiné obhajitelné stavby: " + ", ".join(s for s in res["structure_first"] if s != "schválená"))
        rows.append(f'<tr><td><b>{e(k)}</b> · {res["family_sizes"][k]} nastavení<br><span style="font-size:12px;color:var(--muted)">{e(words)}</span></td>{cells}</tr>')
    return (f'<table class="zt fam"><thead><tr><th>Co se mění</th>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
            '<p class="zcap">Číslo je podíl testovaných nastavení, ve kterých je možnost první mezi těmi, které brány nevyřadily. Nastavení i jejich počty volíme my: je to citlivost, ne pravděpodobnost. '
            'Budoucí výsledky firmy tu nesimulujeme; jsou ve Výsledcích a E1 a R1 je odtud čtou.</p>')


def who_first(res, spec, names):
    st = ", ".join(f'{k} ({e(spec["stakeholders"][k].split(" (")[0])}): {e(names[v])}' for k, v in res["stakeholder_first"].items())
    sf = ", ".join(f'{e(k)}: {e(names[v])}' for k, v in res["structure_first"].items())
    return (f'<div class="zrow"><span class="zk">První podle vah jednotlivých lidí</span><span class="zv">{st}</span></div>'
            f'<div class="zrow"><span class="zk">První podle stavby</span><span class="zv">{sf}</span></div>')


def swing_table(spec, res):
    cats = spec["categories"]
    ks = list(spec["swing"])
    th = "".join(f'<th>{k}{" · schvaluje" if k == spec["owner"] else ""}</th>' for k in ks)
    rows = ""
    for ci, c in enumerate(cats):
        rows += f'<tr><td><b>{e(c["name"])}</b></td>' + "".join(
            f'<td class="num">{spec["swing"][k][c["code"]]} b. · {cz(res["stakeholder_weights"][k][ci]*100,0)} %</td>' for k in ks) + "</tr>"
    return (f'<table class="zt"><thead><tr><th>Kritérium (výkyv od nejhorší k nejlepší možnosti)</th>{th}</tr></thead><tbody>{rows}</tbody></table>'
            '<p class="zcap">Swing weighting: každý z vedení seřadí výkyvy od nejhorší k nejlepší možnosti, největšímu dá 100 bodů a ostatním poměrem. Váha = body / součet. '
            'Platí váhy vlastníka rozhodnutí, schválené spolu s hodnotovými škálami před prvním skóre; váhy ostatních jsou test citlivosti.</p>')


def critical_html(res, spec, names):
    ind_name = {i["code"]: i["name"] for c in spec["categories"] for i in c["indicators"]}
    out = []
    for code, o, t1, others in res["critical"]:
        out.append(f'<div class="claim"><span class="n">?</span><div><b>{e(names[o])} · {code} {e(ind_name[code])}</b>: s dokladem na horní mezi by měl {cz(t1, 2)}, víc než ostatní ({cz(others, 2)}).'
                   f'<span class="w">rozhodující neznámá: vyžádat doklad, jinak ve zprávě dva případy</span></div></div>')
    return "".join(out) or '<p class="zcap">Žádná jednotlivá neznámá buňka nemění, kdo je první.</p>'


BTN_MENU = ('<details class="mnu"><summary class="btn quiet sm ic" aria-label="Další akce" title="Další akce"><i class="ph ph-dots-three"></i></summary><div class="mnu-p" role="menu">'
            '<button type="button"><i class="ph ph-download-simple s"></i>Stáhnout matici (XLSX)</button><a href="MV5Validation.dc.html"><i class="ph ph-book-open s"></i>Metoda v Metodice</a></div></details>')
WARN = ('<div class="zbar warn"><i class="ph ph-lock-simple"></i>Interní · metoda „Sociomapa z indikátorů“ v2 čeká na zápis metodika do registru · '
        'podíly jsou podíly testovaných nastavení, ne pravděpodobnosti · čísla z Modelu jsou ukázková.</div>')

ON = {o["id"]: o["name"] for o in so["objects"]}
OS = {o: o for o in ON}
SN = {o["id"]: o["name"] for o in ss["objects"]}
SS = {"DE": "Delta", "WI": "Wisła", "VL": "Vlastní", "MO": "Morava*", "PO": "Polaris*", "DU": "Dunaj*"}

# ============ SI1 ============
states = [("Známo", "hodnota s dokladem", "skóre podle pravidla a jistota dokladu", "E1 C2: +7,3 mil. → 10"),
          ("Neznámo", "doklad chybí", "bez skóre: buňka drží rozsah, který by mohla mít; ukazuje se pokrytí vah doklady", "F2 B2: 3PL CZ limit nehlásí → 2–10"),
          ("Neuplatní se", "kritérium se objektu netýká", "vynechá se; váhu nesou ostatní kritéria objektu, test ukáže oba konce", "P1 vlastní provoz: žádná smlouva s 3PL"),
          ("Položka doloženě chybí", "u checklistu doklad říká ne", "počítá se jako nesplněná; nedoložená položka je neznámá", "P1 Wisła: strop indexace ne"),
          ("Brána", "podmínka, která se nekompenzuje", "nesplněno: vyřazeno; neznámo: nelze doporučit, dokud chybí doklad, ať boduje jakkoli", "G1 C: 2 dny do měst")]
s1_states = '<table class="zt"><thead><tr><th>Stav</th><th>Kdy</th><th>Jak vstupuje do výpočtu</th><th>Příklad</th></tr></thead><tbody>' + "".join(
    f'<tr><td><b>{e(a)}</b></td><td>{e(b)}</td><td>{e(c)}</td><td style="font-size:12.5px;color:var(--muted)">{e(d)}</td></tr>' for a, b, c, d in states) + "</tbody></table>"
v1 = [("3", "Chybí číslo = medián ostatních", "neznámo, rozsah"), ("4", "Nezdokumentovaná služba = nenabízí", "neznámá položka; nesplněná jen s dokladem"),
      ("5", "Nezdokumentované zdražení = medián", "neznámo, rozsah"), ("6", "Nic nehlášeno = 8", "neznámo; 9 jen s dokladem")]
s1_states += ('<p class="zcap" style="margin-top:10px"><b>Proti verzi 1.</b> Pravidla 1 (tvrdá data přímo) a 2 (úsudek bez dokladu = Nízká) zůstávají. Pravidla 3–6 dávala chybějícímu údaji skóre: ' +
              "; ".join(f"{n}. {e(a)} → {e(b)}" for n, a, b in v1) + '. Jedno neznámé číslo už nikdy nepřebije podmínku a nepřidá body.</p>')
s1_overlap = ('<table class="zt"><thead><tr><th>Indikátor ve verzi 1</th><th>Teď</th><th>Proč</th></tr></thead><tbody>' + "".join(
    f'<tr><td><b>{e(r["code"])}</b> {e(r["name"])}</td><td>{e(r["to"])}</td><td>{e(r["why"])}</td></tr>' for r in so["removed"]) + "</tbody></table>" +
    '<p class="zcap">E1 je medián NPV z Modelu: obsahuje investici, přechod, ztrátu objednávek, indexaci, mzdy a daň. Indikátor, jehož mechanismus už NPV počítá, by ho započítal podruhé. '
    'Ve verzi 1 tak pevná cena B2 bodovala třikrát (E1, D2, P1). Ponechané indikátory hodnotí, co Model nepočítá: závislost, měnu, vratnost, rezervu a termín.</p>')

use = [("Pravidlo klienta rozhoduje", "doporučení dává pravidlo FR nad Modelem; mapa z indikátorů ho nepřepisuje"),
       ("Mapa je informace o preferencích", "ukazuje, co za doporučenou možnost klient platí v kritériích, která Model nepočítá"),
       ("Smí ovlivnit doporučení, jen když", "pravidlo nechá projít víc možností, kritéria a váhy schválil vlastník před výsledky, brány jsou doložené a závěr přežije všech pět rodin testů"),
       ("Jinak jde do zprávy jako doplněk", "v části „Co by závěr změnilo“, s rozsahy a podíly nastavení, ne v doporučení"),
       ("Totéž platí pro mapu scénářů vah", "MV9 váží perspektivy místo kritérií a losuje vějíř vah; brány, stavy důkazů a překryvy bere odtud")]
s1_use = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(use))

body1 = (WARN + sec("01", "Stavy důkazů a brány", "chybějící údaj zůstává chybějící", s1_states) +
         sec("02", "Kontrola překryvů: co Model už počítá", "každý mechanismus jednou", s1_overlap +
             '<p class="zcap">Pravidla škál jednotlivých indikátorů jsou u každé buňky matice (SI2, SI4) a v tools/specs.py; nálezy SWOT, PESTEL a Porter, ze kterých vznikly, drží Rešerše (MV2b).</p>') +
         sec("03", "Váhy: swing weighting", f'schválil {so["owner"]} 4. 11. před prvním skóre', swing_table(so, ro)) +
         sec("04", "Kdy smí mapa ovlivnit doporučení", "a kdy je jen doplněk", s1_use))
conv1 = ada("10:12", ["Metodu jsem postavila na rozhodnutí Velis ve verzi 2. Slib ve městech a strop investice jsou <b>brány</b>: nekompenzují se.",
                      "Indikátory, které už počítá NPV z Modelu (přechod, ztráta objednávek, indexace, mzdy), jsem vypustila. Ve verzi 1 se pevná cena B2 počítala třikrát.",
                      "Chybějící údaj nemá skóre, jen rozsah. Váhy dal FR výkyvy mezi nejhorší a nejlepší možností."],
            "Můžeme váhy měnit, až uvidíme výsledky?", "10:14",
            ["Ne potichu. Váhy a škály schválil FR před prvním skóre a metoda je zamčená. Váhy OR a VL jsou test citlivosti na SI3; jiné váhy perspektiv zkouší mapa scénářů vah (MV9)."])
btn1 = BTN_MENU + '<a class="btn primary sm" href="SI2Matrix.dc.html">Matice skóre<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI1Method.dc.html", "w").write(frame("Sociomapa z indikátorů: metoda", "Sociomapa z indikátorů: metoda", "Sociomapa · metoda", conv1,
                                                    "Sociomapa · metoda", btn1, body1, ("MV9ScenarioWeights.dc.html", "Mapa scénářů vah"), ("SI2Matrix.dc.html", "Matice skóre"), "SI1 Metoda", 2080))

# ============ SI2 ============
from collections import Counter
cnt_rows = ""
for o in ro["objs"]:
    c = Counter(v[o]["state"] for v in ro["cells"].values())
    cnt_rows += f'<tr><td>{e(ON[o])}</td>' + "".join(f'<td class="num">{c.get(k,0)}</td>' for k in ["known", "unknown", "na"]) + f'<td class="num">{cz(ro["coverage"][ro["objs"].index(o)]*100,0)} %</td></tr>'
cnt_t = '<table class="zt"><thead><tr><th>Možnost</th><th>Známo</th><th>Neznámo</th><th>Neuplatní se</th><th>Pokrytí vah</th></tr></thead><tbody>' + cnt_rows + "</tbody></table>"
ex = so["experts"]
ex_rank = sorted(ro["objs"], key=lambda o: -ex[o])
ind_rank = sorted([o for o in ro["objs"] if ro["gate"][o] != "fail"], key=lambda o: -ro["total"][ro["objs"].index(o)])
ex_t = ('<table class="zt"><thead><tr><th>Možnost</th><th>Průměr manažerů</th><th>Buněk</th><th>Pořadí manažerů</th><th>Pořadí indikátorů</th></tr></thead><tbody>' + "".join(
    f'<tr><td>{e(ON[o])}</td><td class="num">{cz(ex[o],2)}</td><td class="num">{so["expert_cells"][o]}</td><td class="num">{ex_rank.index(o)+1}</td>'
    f'<td class="num">{(ind_rank.index(o)+1) if o in ind_rank else "vyřazeno"}</td></tr>' for o in ro["objs"]) + "</tbody></table>"
    '<p class="zcap">Pět kritérií manažerů (náklady, riziko dodavatele, služba, kapacita, kapitál) už hodnotí E1, D1, F2 a brány. Jako další kritérium by je započítalo podruhé, proto jsou kontrola: '
    'kde se pořadí rozchází, ptáme se proč. Prázdná buňka OR · A · Služba zůstává prázdná (24 buněk u A).</p>')
iB2, iC2 = ro["objs"].index("B2"), ro["objs"].index("C2")
claims2 = [(f"C2 má nejvyšší doložené minimum: {cz(ro['total'][iC2], 2)}", "vede v Ekonomice (10) a Riziku (10); ztrácí na závislosti, měně a vratnosti"),
           (f"B2 má {cz(ro['total'][iB2], 2)}–{cz(ro['thi'][iB2], 2)}: rozhodne kapacita 3PL CZ", "jediná neznámá buňka matice, která mění první místo (F2)"),
           ("C je vyřazená bránou G1", "ve městech doručí o den později; v matici zůstává pro srovnání, do pořadí nevstupuje"),
           ("A a A2 drží slib a dodavatele, ale padají na vratnosti (2 a 3) a Ekonomice", "investice 70 a 77 mil. Kč; hala se nedá vrátit")]
claims_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims2))
body2 = (WARN + sec("01", "Matice: brány a sedm kritérií × sedm možností", "skóre 1–10 · jistota dokladu · vstupní hodnota pod číslem",
                    matrix(so, ro, OS) + CT_LEG + '<p class="zcap">Zelená: 8 a víc. Oranžová: 3 a míň. Šrafovaná buňka nemá doklad: místo skóre rozsah. Výška na mapě je doložené minimum.</p>') +
         sec("02", "Kolik matice ví", "buňky podle stavu · pokrytí vah doklady", cnt_t +
             '<p class="zcap">Neznámé jsou jen F2 u B a B2: český 3PL kapacitní limit nehlásí. Dotaz odešel 4. 11.; do odpovědi zpráva ukáže oba případy.</p>') +
         sec("03", "Co z matice plyne", "jen z matice, bez testů", claims_html) +
         sec("04", "Manažeři jako kontrola, ne kritérium", "hodnoceni_expertu.csv · 5 hodnotitelů × 5 kritérií", ex_t))
conv2 = ada("10:31", ["Matice je hotová. Každá buňka má pravidlo, zdroj a stav. Neznámé buňky jsou dvě a nedostaly číslo.",
                      f"<b>Na doloženém minimu vede C2 ({cz(ro['total'][iC2], 2)}).</b> B2 může být první, jen pokud 3PL CZ doloží kapacitu aspoň 1,0 potřeby roku 2032. Na to čekáme."])
btn2 = BTN_MENU + '<a class="btn primary sm" href="SI3OptionsMap.dc.html">Mapa možností<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI2Matrix.dc.html", "w").write(frame("Sociomapa z indikátorů: matice skóre", "Matice skóre: možnosti", "Sociomapa · matice skóre", conv2,
                                                    "Matice skóre", btn2, body2, ("SI1Method.dc.html", "Metoda"), ("SI3OptionsMap.dc.html", "Mapa možností"), "SI2 Matice", 2410))

# ============ SI3 ============
XB2 = ro["crossings"]["C2>B2"]
fam = ro["families"]
f_c2 = {k: v[iC2] for k, v in fam.items()}
f_b2 = {k: v[iB2] for k, v in fam.items()}
sweep = (f'<div class="claim"><span class="n">!</span><div>C2 zůstane před B2, dokud váha Ekonomiky neklesne pod <b>{cz(XB2, 3)}</b> (schváleno {cz(ro["W"][0], 3)}), ostatní váhy v poměru.'
         f'<span class="w">na doloženém minimu; s kapacitou B2 na horní mezi vede B2 i při schválených vahách</span></div></div>')
alt_cases = ('<table class="zt"><thead><tr><th>Případ</th><th>F2 u B2</th><th>B2</th><th>C2</th><th>První</th></tr></thead><tbody>'
             f'<tr><td>3PL CZ doloží kapacitu ≥ 1,2 potřeby</td><td class="num">10</td><td class="num">{cz(ro["thi"][iB2],2)}</td><td class="num">{cz(ro["total"][iC2],2)}</td><td><b>B2</b></td></tr>'
             f'<tr><td>doloží 1,0–1,2</td><td class="num">8</td><td class="num">{cz(ro["total"][iB2] + (8-2)*ro["W"][5],2)}</td><td class="num">{cz(ro["total"][iC2],2)}</td><td><b>{"B2" if ro["total"][iB2] + 6*ro["W"][5] > ro["total"][iC2] else "C2"}</b></td></tr>'
             f'<tr><td>doloží pod 1,0, nebo neodpoví</td><td class="num">2–6</td><td class="num">{cz(ro["total"][iB2],2)}–{cz(ro["total"][iB2] + 4*ro["W"][5],2)}</td><td class="num">{cz(ro["total"][iC2],2)}</td><td><b>C2</b></td></tr>'
             '</tbody></table>')
claims3 = [(f"Na doloženém minimu vede C2 ({cz(ro['total'][iC2], 2)}) ve vahách ({cz(f_c2['váhy']*100,0)} %), důkazech ({cz(f_c2['důkazy']*100,0)} %) i stavbě ({cz(f_c2['struktura']*100,0)} %)",
             "stejná možnost jako podle pravidla FR nad Modelem; mapa doporučení nepřepisuje"),
           (f"Chybějící údaj to dělí napůl: C2 {cz(f_c2['chybějící údaje']*100,0)} %, B2 {cz(f_b2['chybějící údaje']*100,0)} % nastavení", "jediná rozhodující neznámá je kapacita 3PL CZ (F2 u B2)"),
           (f"Vše najednou: B2 {cz(f_b2['vše najednou']*100,0)} %, C2 {cz(f_c2['vše najednou']*100,0)} %", "závěr „C2 i podle indikátorů“ nepřežije všechny rodiny: do zprávy jde jako podmíněný"),
           (f"Vedoucí logistiky by s vlastními vahami dal první {ON[ro['stakeholder_first']['VL']]}", "váží závislost a vratnost víc než peníze; váhy schvaluje FR, ale rozdíl patří do zprávy"),
           ("Podíly nejsou pravděpodobnosti", "jsou to podíly nastavení, která jsme zvolili; budoucí výsledky firmy jsou ve Výsledcích")]
claims3_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims3))
body3 = (WARN + sec("01", "Pořadí: doložené minimum a rozsah", "brány · rozsahy · pokrytí vah doklady", ranges(ro, ON) + sweep) +
         sec("02", "Testy citlivosti: kdo je první", "pět rodin · podíl testovaných nastavení", families(ro, OS) + '<div class="zcard" style="margin-top:12px">' + who_first(ro, so, ON) + "</div>" +
             '<p class="zcap">Mapu enginu z testovaných nastavení kreslí <a href="MV9ScenarioWeights.dc.html">MV9</a>: řádky jsou tam pojmenované scénáře vah nad perspektivami a jejich vějíře.</p>') +
         sec("03", "Rozhodující neznámá", "dokud chybí doklad, zpráva ukáže případy", critical_html(ro, so, ON) + alt_cases) +
         sec("04", "Co mapa tvrdí a co ne", "tvrzení do osnovy zprávy", claims3_html))
conv3 = ada("10:48", [f"Bez dvojího počítání a s čísly přímo z Výsledků vede <b>C2 ({cz(ro['total'][iC2], 2)})</b>, stejně jako pravidlo FR. Ve verzi 1 vedla B2, protože se pevná cena počítala třikrát.",
                      f"Jednu věc nevíme: kapacitu 3PL CZ. Pokud doloží aspoň 1,0 potřeby, vede B2 ({cz(ro['total'][iB2] + 6*ro['W'][5], 2)}–{cz(ro['thi'][iB2], 2)}). Proto je závěr podmíněný."],
            "Co z toho řekneme FR?", "10:50",
            ["Že doporučení dává pravidlo (C2) a indikátory s ním souhlasí, pokud 3PL CZ nedoloží kapacitu aspoň 1,0 potřeby. Odpověď na dotaz čekáme do 20. 11., před termínem 8. 12."])
btn3 = BTN_MENU + '<a class="btn primary sm" href="SI4Suppliers.dc.html">Mapa dodavatelů<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI3OptionsMap.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa možností", "Mapa možností", "Sociomapa · mapa možností", conv3,
                                                        "Mapa možností", btn3, body3, ("SI2Matrix.dc.html", "Matice skóre"), ("SI4Suppliers.dc.html", "Mapa dodavatelů"), "SI3 Mapa možností", 2070))

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
s4_rem = ('<table class="zt"><thead><tr><th>Ve verzi 1</th><th>Teď</th><th>Proč</th></tr></thead><tbody>' + "".join(
    f'<tr><td><b>{e(r["code"])}</b> {e(r["name"])}</td><td>{e(r["to"])}</td><td>{e(r["why"])}</td></tr>' for r in ss["removed"]) + "</tbody></table>")
sobj = rs["objs"]
iVL, iDE, iMO, iDU = (sobj.index(k) for k in ("VL", "DE", "MO", "DU"))
nat = rs["na_test"]["VL"]
claims4 = [(f"Na doloženém minimu vede vlastní provoz ({cz(rs['total'][iVL], 2)})", f"ve vahách {cz(rs['families']['váhy'][iVL]*100,0)} %, důkazech {cz(rs['families']['důkazy'][iVL]*100,0)} %, stavbě {cz(rs['families']['struktura'][iVL]*100,0)} %"),
           (f"Smluvní podmínky se ho netýkají; s nejhorší hodnotou by měl {cz(nat['at1'], 2)}, pod Deltou ({cz(rs['total'][iDE], 2)})", "vede i proto, že nemá smlouvu s 3PL: jeho riziko je řízení vlastního skladu, které mapa neměří"),
           (f"Delta může vést s doloženou kapacitou: až {cz(rs['thi'][iDE], 2)}", "jediná neznámá buňka, která sama mění první místo (K1)"),
           (f"Morava* je první v {cz(rs['families']['chybějící údaje'][iMO]*100,0)} % nastavení chybějících údajů", f"pokrytí vah doklady jen {cz(rs['coverage'][iMO]*100,0)} %: rozsah {cz(rs['total'][iMO], 2)}–{cz(rs['thi'][iMO], 2)}"),
           ("Polaris* a Dunaj* nelze doporučit, dokud nedoloží slib ve městech", f"brána G1 neznámá; Dunaj má doklady jen u {cz(rs['coverage'][iDU]*100,0)} % vah")]
claims4_html = "".join(f'<div class="claim"><span class="n">{i+1}</span><div>{e(a)}<span class="w">{e(b)}</span></div></div>' for i, (a, b) in enumerate(claims4))
body4 = (WARN + sec("01", "Koho mapa porovná", "6 skladů pro e-shop Velis", s4_objs) +
         sec("02", "Brána a co se změnilo proti verzi 1", "slib ve městech se nekompenzuje", gates_table(ss, SS) + s4_rem) +
         sec("03", "Váhy: swing weighting", f'schválil {ss["owner"]} 4. 11. před prvním skóre', swing_table(ss, rs)) +
         sec("04", "Matice skóre", "skóre 1–10 · jistota · rozsah u neznámých · pravidlo škály u každého indikátoru", matrix(ss, rs, SS) + CT_LEG) +
         sec("05", "Pořadí a testy citlivosti", "doložené minimum · rozsah · pět rodin", ranges(rs, SN) + families(rs, SS) +
             '<div class="zcard" style="margin-top:12px">' + who_first(rs, ss, SN) + "</div>") +
         sec("06", "Co mapy tvrdí a co doplnit před závěrem", "rozhodující neznámé", claims4_html + critical_html(rs, ss, SN) +
             '<div class="zhand" style="margin-top:10px"><i class="ph ph-magnifying-glass"></i><div><b>Vyžádat doklad:</b> kapacitní závazek Delty (K1); u Moravy* indexaci, historii výpadků a smluvní podmínky; '
             'u Polaris* a Dunaj* expresního partnera pro města (G1). Do té doby zpráva uvádí rozsahy, ne pořadí.</div></div>'))
conv4 = ada("11:05", ["Stejná metoda, jiné objekty: šest skladů. Tři znám z dokumentů klienta, tři našla Rešerše. Ty jsou v ukázce smyšlené a označené hvězdičkou.",
                      f"Chybějící údaj už nedostává body ani nebere body. Proto je vidět, co nevíme: <b>Morava* má doklady jen u {cz(rs['coverage'][iMO]*100,0)} % vah</b> a mohla by vést. Než to dáme do zprávy, vyžádám doklady."])
btn4 = BTN_MENU + '<a class="btn primary sm" href="MV4XRay.dc.html">Osnova zprávy<i class="ph ph-caret-right s"></i></a>'
open(f"{OUT}/SI4Suppliers.dc.html", "w").write(frame("Sociomapa z indikátorů: mapa dodavatelů", "Mapa dodavatelů", "Sociomapa · mapa dodavatelů", conv4,
                                                       "Mapa dodavatelů", btn4, body4, ("SI3OptionsMap.dc.html", "Mapa možností"), ("MV4XRay.dc.html", "Osnova zprávy"), "SI4 Mapa dodavatelů", 3820))
print("ok")
