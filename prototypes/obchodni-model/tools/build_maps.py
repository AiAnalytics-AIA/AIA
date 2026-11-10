"""Writes MV3 (the futures map) and MV9 (the weighting-scenario map) into the canvas folder.

Run from this folder, after specs_weights.py, compute_weights.py (both specs) and engine_weights.py:
    python3 build_maps.py
The frame is MV3 as committed in 2a2bb471 (the board before this rewrite), read from git and
edited by its markup, not by line numbers. ChemVitro's numbers are report 2's (tables T1, T7,
T8, chapter 11, appendix B); the Velis numbers are the canvas's illustrative ones and say so.
"""
import html
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..")
FRAME = subprocess.run(["git", "show", "2a2bb471:prototypes/obchodni-model/MV3SystemMap.dc.html"], cwd=OUT,
                       capture_output=True, text=True, check=True).stdout
e = html.escape
RC = json.load(open(os.path.join(HERE, "res_scenarios_chemvitro.json")))
RV = json.load(open(os.path.join(HERE, "res_scenarios_velis.json")))
SC = json.load(open(os.path.join(HERE, "spec_scenarios_chemvitro.json")))
SV = json.load(open(os.path.join(HERE, "spec_scenarios_velis.json")))
ENG = json.load(open(os.path.join(HERE, "engine_scenarios.json")))
ASSETS = json.load(open(os.path.join(HERE, "engine_assets.json")))


def img(name):
    """A map image in the export's form, assets/<file>.jpg: the uploaded id's file where the canvas
    already holds it, else the file engine_weights.py wrote (the coordinator uploads it and rewrites the id)."""
    return f"assets/{ASSETS[name]}.jpg" if name in ASSETS else f"assets/{name}.jpg"


def cz(x, d=1):
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def pct(x):
    return f"{round(x * 100):d} %"


EXTRA_CSS = """
.art .abody{max-width:none}
.zbar>span{flex:1 1 auto}
.zt td.num{white-space:nowrap}
.case{display:inline-flex;align-items:center;gap:6px;height:22px;padding:0 9px;border-radius:11px;font:600 11px/1 var(--sans);letter-spacing:.02em;white-space:nowrap;vertical-align:2px}
.case.cv{background:#e6eef7;color:#1d4f7c}.case.ve{background:var(--sunken);color:var(--muted)}
.rules{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.rules div{border:1px solid var(--border);border-radius:8px;background:var(--raised);padding:9px 11px;font-size:12.5px;line-height:17px}
.rules b{display:block;font-size:12.5px;margin-bottom:2px}
.mx td.rel{font-family:var(--mono);font-size:12px}
.mx td.rel.ok{background:var(--swash);font-weight:600}
.mx td.rel.neg{color:var(--muted)}
.mx td.dash{color:var(--faint)}
.mx th.rowh,.mx td.rowh{text-align:left;font-weight:500;white-space:nowrap}
.smx{border-collapse:collapse;width:100%;font-size:12.5px}
.smx th,.smx td{border:1px solid var(--border);padding:5px 7px;vertical-align:middle}
.smx th{background:var(--sunken);font-weight:500;color:var(--muted);font-size:12px;text-align:center}
.smx td.l{text-align:left}
.smx td.s{font:600 12.5px/1 var(--mono);text-align:center;white-space:nowrap}
.smx td.s small{display:block;font:400 10px/1.3 var(--mono);color:var(--faint);margin-top:3px}
.smx td.s.hi{background:var(--swash)}.smx td.s.lo{background:var(--youwash)}
.smx td.s.u{background:repeating-linear-gradient(135deg,var(--surface),var(--surface) 5px,var(--sunken) 5px,var(--sunken) 10px)}
.smx tr.cat td{background:var(--sunken);font-weight:600}
.smx tr.cat td span{font-weight:400;color:var(--muted);font-size:12px}
.smx tr.inforow td{color:var(--muted);background:var(--surface);font-size:12px}
.smx tr.inforow td b{color:var(--ink)}
.smx .ck{font:600 11px var(--mono);color:var(--signal);margin-right:5px}
.smx .sub{display:block;font-size:11px;color:var(--muted);font-weight:400;line-height:15px}
.gp{font:600 11px/1 var(--sans);border-radius:4px;padding:3px 6px;white-space:nowrap}.gp.pass{background:var(--swash);color:var(--signal)}.gp.fail{background:#fbe0dc;color:#9b2c1c}.gp.unknown{border:1px dashed var(--youink);color:var(--youink)}
.gp small{font-weight:400;margin-left:3px;opacity:.8}
.wbar{width:70px;height:8px;border-radius:4px;background:var(--border);overflow:hidden;display:inline-block;vertical-align:middle;margin-right:5px}.wbar i{display:block;height:100%;background:var(--signal)}
.wv{font:600 12px var(--mono)}
.fam td.num{font-family:var(--mono);font-size:12px;text-align:center;white-space:nowrap}
.fam td.num.lead{background:var(--swash);font-weight:700}
.fam td.num.nil{color:var(--faint)}
.zt td.first{font-weight:600}
.verd{display:flex;gap:12px;align-items:flex-start;border:1px solid var(--you);background:var(--youwash);border-radius:8px;padding:12px 14px;font-size:13.5px;line-height:20px}
.verd i{color:var(--you);font-size:18px;margin-top:1px}
.okv{border-color:var(--signal);background:var(--stint)}.okv i{color:var(--signal)}
.stab{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.stab .zkpi .v{font-size:20px}
.stab .zkpi.bad .v{color:var(--youink)}
.src{font-size:11.5px;color:var(--muted)}
.smx tr.refused td{background:#fdf1ef}
.fam-a,.fam-b{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:9px;font:700 11px/1 var(--mono);margin-right:6px}
.fam-a{background:var(--swash);color:var(--signal)}.fam-b{background:var(--sunken);color:var(--ink)}
"""


def frame(title, h1, aria, conv, sees, body, prev, nxt, code, height, banner, next_label):
    s = FRAME
    s = re.sub(r"<title>.*?</title>", f"<title>{e(title)}</title>", s, count=1)
    s = s.replace("</style>\n</helmet>", EXTRA_CSS + "</style>\n</helmet>")
    s = s.replace('class="leadx" aria-label="Skrýt panel Vedoucího">', 'class="leadx" aria-label="Skrýt panel Vedoucího" checked="">')
    s = re.sub(r'<div class="conv">.*?</div>\n  <div class="cfdock">', f'<div class="conv">{conv}</div>\n  <div class="cfdock">', s, count=1, flags=re.S)
    s = re.sub(r'<div class="cfctx"><i class="ph ph-eye s"></i>Vidí: [^<]*</div>', f'<div class="cfctx"><i class="ph ph-eye s"></i>Vidí: {e(sees)}</div>', s, count=1)
    s = re.sub(r'<main class="art" aria-label="[^"]*">', f'<main class="art" aria-label="{e(aria)}">', s, count=1)
    s = re.sub(r"<h1>[^<]*</h1>", f"<h1>{e(h1)}</h1>", s, count=1)
    s = re.sub(r'<a class="btn primary sm" href="MV4XRay.dc.html">Osnova zprávy<i class="ph ph-caret-right s"></i></a>',
               f'<a class="btn primary sm" href="{nxt[0]}">{e(next_label)}<i class="ph ph-caret-right s"></i></a>', s, count=1)
    s = re.sub(r'<div class="abody">.*?</div>\n      </main>', f'<div class="abody">{banner}{body}</div>\n      </main>', s, count=1, flags=re.S)
    s = re.sub(r'<div class="zseq" role="navigation" aria-label="Průchod ukázkou">.*?</div>\n  </div>\n</div>\n</x-dc>',
               f'<div class="zseq" role="navigation" aria-label="Průchod ukázkou"><a href="{prev[0]}"><i class="ph ph-caret-left s"></i>{e(prev[1])}</a>'
               f'<span class="grow" style="text-align: center">Velis Commerce s.r.o. · MVP · <b>{e(code)}</b> · <a href="MV0Scope.dc.html">přehled MVP</a></span>'
               f'<a href="{nxt[0]}">{e(nxt[1])}<i class="ph ph-caret-right s"></i></a></div>\n  </div>\n</div>\n</x-dc>', s, count=1, flags=re.S)
    s = s.replace('"height":3480', f'"height":{height}')
    assert f'"height":{height}' in s and e(h1) in s and banner in s
    return s


def sec(num, title, cap, inner, cls=""):
    return (f'<section class="sec {cls}"><div class="sh"><span class="num">{num}</span><h2>{title}</h2><span class="grow"></span>'
            f'<span class="cap">{e(cap)}</span></div><div class="sb">{inner}</div></section>')


def ada(day, turns):
    s = f'<div class="day">{day}</div>'
    for who, t, ps in turns:
        if who == "me":
            s += f'<div class="me">{e(t)}</div>'
        else:
            s += ('<div class="reply"><span class="lav" aria-hidden="true"><i class="ph ph-sparkle"></i></span><div class="body">'
                  f'<div class="who"><b>Ada</b>{t}</div>' + "".join(f"<p>{p}</p>" for p in ps) + "</div></div>")
    return s


CV = '<span class="case cv">ChemVitro · vzor ze zprávy 2</span>'
VE = '<span class="case ve">Velis · pracovní případ, smyšlené hodnoty</span>'
HOW = '<div class="zcard"><h3>Jak mapu číst</h3>{rows}</div>'


def rows(items):
    return "".join(f'<div class="zrow"><span class="zk">{e(k)}</span><span class="zv">{v}</span></div>' for k, v in items)


# ====================================================================== MV3
SITES = ["Vrbice", "Lipová", "Kamenec", "Wendelstedt", "Lindenau", "Eschfeld", "Odrzyca", "Bory"]
T7 = [  # report 2, table T7: the relation matrix the futures map is drawn from (judged correlations)
    [None, 0.50, 0.52, -0.27, -0.27, -0.26, -0.15, -0.07],
    [0.50, None, 0.55, -0.22, -0.23, -0.27, -0.14, -0.15],
    [0.52, 0.55, None, -0.23, -0.23, -0.26, -0.14, -0.15],
    [-0.27, -0.22, -0.23, None, 0.56, 0.70, -0.12, -0.17],
    [-0.27, -0.23, -0.23, 0.56, None, 0.71, -0.12, -0.15],
    [-0.26, -0.27, -0.26, 0.70, 0.71, None, -0.15, -0.15],
    [-0.15, -0.14, -0.14, -0.12, -0.12, -0.15, None, 0.48],
    [-0.07, -0.15, -0.15, -0.17, -0.15, -0.15, 0.48, None],
]
RELIABLE = {(3, 5), (4, 5)}  # the two pairs the program marked reliable: Wendelstedt–Eschfeld, Lindenau–Eschfeld
T8 = {  # table T8: when the row's site is worse than buying, how often each other site is worse too
    "Odrzyca": [0.90, 0.84, 0.79, 0.98, 0.97, 0.99, None, 0.91],
    "Kamenec": [0.99, 0.93, None, 0.98, 0.98, 1.00, 0.75, 0.83],
}


def t7_table():
    th = "".join(f"<th>{s}</th>" for s in SITES)
    body = []
    for i, s in enumerate(SITES):
        tds = []
        for j in range(8):
            v = T7[i][j]
            if v is None:
                tds.append('<td class="rel dash">–</td>')
            else:
                cls = "ok" if (min(i, j), max(i, j)) in RELIABLE else ("neg" if v < 0 else "")
                tds.append(f'<td class="rel {cls}">{cz(v, 2)}</td>')
        body.append(f'<tr><td class="rowh">{s}</td>{"".join(tds)}</tr>')
    return f'<table class="mx"><thead><tr><th class="rowh"></th>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def t8_table():
    th = "".join(f"<th>{s}</th>" for s in SITES)
    body = []
    for who, vs in T8.items():
        tds = []
        for v in vs:
            if v is None:
                tds.append('<td class="rel dash">–</td>')
            else:
                tds.append(f'<td class="rel {"ok" if v <= 0.80 else ""}">{pct(v)}</td>')
        body.append(f'<tr><td class="rowh">{who}</td>{"".join(tds)}</tr>')
    return f'<table class="mx"><thead><tr><th class="rowh">Když je horší než nákup …</th>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def mv3():
    banner = ('<div class="zbar warn"><i class="ph ph-lock-simple"></i><span>Interní · mapy, jejichž pozorovateli jsou budoucnosti modelu, čekají na schválení metodikem '
              '(mapy z hodnocení lidí schváleny 21. 10. 2026) · do zprávy jen se stupněm <span class="zg est">odhad</span> a touto výhradou.</span></div>')
    s01 = sec("01", "Režim mapy", "čtyři režimy, čtyři různá tvrzení",
              '<div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px">'
              '<div class="mode on"><h3><i class="ph ph-arrows-clockwise"></i>Budoucnosti</h3><span class="cap">řádky: budoucnosti modelu Monte Carlo, každá vycentrovaná na průměr objektů</span>'
              '<span>„V tomto modelu se A a B daří relativně lépe v týchž budoucnostech.“</span><span><span class="zg mod">modelováno</span> <span class="pill sig">vybráno</span></span></div>'
              '<div class="mode"><h3><i class="ph ph-users"></i>Expertní mapa</h3><span class="cap">řádky: varianty hodnocené lidmi podle kritérií</span><span>„Tak to vidí jmenovaní hodnotitelé.“</span><span><span class="zg mod">modelováno</span> vstupy zadali lidé</span></div>'
              '<div class="mode lock"><h3><i class="ph ph-lock-simple"></i>Jednotky</h3><span class="cap">řádky: pobočky, zboží, zákazníci</span><span>souvislost napříč jednotkami s intervalem</span><span><span class="zg est">odhad</span> čeká na validační sadu</span></div>'
              '<div class="mode lock"><h3><i class="ph ph-lock-simple"></i>Období</h3><span class="cap">řádky: 24–36 měsíců</span><span>slabá souvislost v daném časovém měřítku</span><span><span class="zg est">odhad</span> čeká na validační sadu</span></div></div>'
              '<p class="zcap">Mapa scénářů vah (<a href="MV9ScenarioWeights.dc.html">MV9</a>) je pátý způsob čtení téhož enginu: řádky jsou testované váhy, ne budoucnosti. Stojí vedle této mapy, nikdy se s ní neslučuje. '
              'Jednotky a období se odemknou, až <a href="MV5Validation.dc.html">validační sada</a> projde na prazích metodika.</p>')
    s02 = sec("02", "Statistická smlouva režimu", "každý režim tvrdí něco jiného, a proto se jinak ověřuje",
              '<table class="zt ctr"><thead><tr><th></th><th>Budoucnosti</th><th>Expertní mapa</th><th>Jednotky</th><th>Období</th></tr></thead><tbody>'
              '<tr><td><b>Co je řádek</b></td><td>jedna budoucnost modelu (los), vycentrovaná na průměr objektů; losy jsou nezávislé</td><td>hodnocení jednoho hodnotitele podle jednoho kritéria; blok = hodnotitel</td><td>jedna jednotka klienta (pobočka, zboží, zákazník)</td><td>jedno období (měsíc) téže firmy</td></tr>'
              '<tr><td><b>O čem je tvrzení</b></td><td>o modelu a jeho předpokladech, ne o trhu ani o příčinách</td><td>o jmenovaných hodnotitelích, ne o všech manažerech</td><td>o jednotkách klienta v daném roce</td><td>o této firmě v tomto období</td></tr>'
              '<tr><td><b>Co se měří</b></td><td>souběh relativního výsledku objektů mezi budoucnostmi; společná absolutní ztráta zvlášť, z nevycentrovaných hodnot (06)</td><td>shoda profilů variant napříč kritérii</td><td>souvislost ukazatelů napříč jednotkami</td><td>souběh ukazatelů v čase po odstranění trendu a sezónnosti</td></tr>'
              '<tr><td><b>Co znamená nula</b></td><td>nemá smysl: vazby vytváří model; žádná p-hodnota</td><td>hodnotitelé nesdílejí žádný vzor</td><td>žádná souvislost napříč jednotkami</td><td>žádný souběh nad trend a sezónnost; fázově náhodné surogáty</td></tr>'
              '<tr><td><b>Převzorkování</b></td><td>žádný bootstrap; určenost: mapy ze dvou polovin budoucností (práh 0,59)</td><td>po hodnotitelích (celé bloky); efektivní n = počet hodnotitelů</td><td>shlukový bootstrap po regionech; nezávislost jednotek uvedena</td><td>blokový bootstrap sousedních období; test strukturního zlomu</td></tr>'
              '<tr><td><b>Co měří zobrazená stabilita</b></td><td>citlivost tvaru na předpoklady, stanovené před výpočtem (07); víc budoucností snižuje jen numerický šum, ne chybu předpokladů</td><td>závislost na hodnotitelích a na způsobu spojení (průměr, směs, jeden vynechán)</td><td>nejistotu výběru jednotek</td><td>nejistotu z časové závislosti</td></tr>'
              '</tbody></table>')
    s03 = sec("03", f"Mapa budoucností {CV}", "8 lokalit · 20 000 budoucností jako pozorovatelé",
              f'<div class="zgrid2"><div class="zstage"><img src="{img("mv3-futures-chemvitro-3d")}" alt="Mapa budoucností, prostorový pohled: osm lokalit, korelace cen podle úsudku"></div>'
              f'<div class="zstage"><img src="{img("mv3-futures-chemvitro-top")}" alt="Mapa budoucností, pohled shora: tytéž polohy"></div></div>'
              '<div class="zgrid2" style="margin-top:12px">' + HOW.format(rows=rows([
                  ("Řádky", "20 000 budoucností modelu; každá hodnotí lokalitu její úsporou proti nákupu a je vycentrovaná na průměr osmi lokalit"),
                  ("Výška", "průměrná úspora proti nákupu: 74,2 mil. EUR Eschfeld (modré údolí) až 147,6 mil. EUR Odrzyca (červený vrchol) <span class=\"zg est\">odhad</span>"),
                  ("Spojnice", "jen dvojice, jejichž vztah program vyhodnotil jako spolehlivý: 2 z 28, obě mezi německými lokalitami; teplá barva souhlasný pohyb, šířka síla"),
                  ("Blízko sebe", "lokality, kterým se relativně daří v týchž budoucnostech: německé v údolí, české a polské na hřebeni"),
                  ("Verze", "korelace cen podle úsudku (kapitola 4 zprávy); dvě další verze slouží jako zkouška stability (07)"),
              ])) + '<div class="zcard"><h3>Co z ní jde přečíst</h3><p>Výšky a rozdělení na německou skupinu v údolí a česko-polskou stranu na hřebeni: to se objevuje ve všech třech verzích.</p>'
              '<p>Ne přesné vzdálenosti ani jemné polohy uvnitř česko-polské strany (zda má Vrbice blíž ke Kamenci, nebo k Borům), ne příčiny, ne pravděpodobnosti.</p>'
              '<p class="src">Program AIA, metodika aia-sociomap-5; zpráva 2, oddíl 11.2. Pohled shora nezkresluje vzdálenosti perspektivou.</p></div></div>')
    s04 = sec("04", f"Matice vztahů T7 {CV}", "z této matice se mapa kreslí",
              t7_table() +
              '<p class="zcap">Vztahy uvnitř zemí jsou kladné: německé 0,56–0,71, české 0,50–0,55, polské 0,48. Všechny vztahy mezi zeměmi jsou slabé a záporné, −0,07 až −0,27: zčásti kvůli centrování, '
              'které z každé budoucnosti odečte průměr; když se jedné skupině daří relativně lépe, ostatním se musí dařit hůř. Zvýrazněny jsou dvě dvojice označené za spolehlivé. '
              'Lokality jedné země sdílejí mzdy, ceny energie, kurz a povolovací režim, takže je stejné budoucnosti posouvají stejným směrem (úsudek).</p>')
    s05 = sec("05", f"Společná selhání T8 {CV}", "když je lokalita horší než nákup, jak často je horší i jiná",
              t8_table() +
              '<div class="verd" style="margin-top:12px"><i class="ph ph-warning-circle"></i><div><b>Žádná lokalita není zálohou jiné.</b> Nejlepší záloha selže spolu s vybranou lokalitou v 75 až 79 % takových budoucností (Odrzyca a Kamenec navzájem), německé lokality téměř ve všech. '
              'Vlastní závod prodělá hlavně tehdy, když je nákup levný, a levný nákup postihne všechny lokality najednou; rozdíly mezi lokalitami jsou proti tomu malé. '
              'Pro otázku zálohy platí tabulka, ne mapa (06). <span class="zg est">odhad</span></div></div>'
              '<p class="zcap">Zvýrazněna je jediná dvojice pod 80 %. Pokud by klient chtěl mít náhradní lokalitu pro případ, že úřad na první uloží kompenzační opatření, je jí pro Odrzycu Kamenec a naopak; před levným nákupem neochrání ani tato dvojice.</p>')
    s06 = sec("06", "Relativní výkon, nebo společná ztráta", "dvě čtení týchž budoucností",
              '<div class="zgrid2"><div>' + CV +
              '<table class="zt" style="margin-top:8px"><thead><tr><th style="width:150px">Dvojice</th><th style="width:120px">Na mapě (po centrování)</th><th style="width:170px">V tabulce T8</th><th>Co to znamená</th></tr></thead><tbody>'
              '<tr><td style="white-space:nowrap">Odrzyca · Kamenec</td><td class="num">−0,14</td><td class="num">75–79 % společných selhání</td><td>na mapě vypadají jako lokality s nezávislými osudy; sdílejí jen riziko levného nákupu, ne národní rizika</td></tr>'
              '<tr><td style="white-space:nowrap">Odrzyca · Eschfeld</td><td class="num">−0,15</td><td class="num">99 %</td><td>relativně opačné, absolutně prodělají skoro vždy spolu</td></tr>'
              '</tbody></table><p class="zcap">Centrování odstraní společnou úroveň všech lokalit, tedy právě vliv levného nákupu, hlavní příčiny společných selhání. Tabulka na korelace cen energie tolik citlivá není.</p></div>'
              '<div>' + VE +
              '<table class="zt" style="margin-top:8px"><thead><tr><th style="width:80px">Dvojice</th><th style="width:120px">Po odečtení průměru losu</th><th style="width:100px">Bez odečtení</th><th>Co to znamená</th></tr></thead><tbody>'
              '<tr><td>C2 · B2</td><td class="num">+0,41</td><td class="num">+0,78</td><td>relativně podobné jen trochu; absolutně ztrácejí spolu, když klesnou objednávky; B2 proti tomu C2 nechrání</td></tr>'
              '<tr><td>A · C2</td><td class="num">−0,52</td><td class="num">+0,12</td><td>relativně opačné losy; společnou ztrátu téměř nesdílejí</td></tr>'
              '<tr><td>A · A2</td><td class="num">+0,88</td><td class="num">+0,95</td><td>v obou čteních skoro jedna varianta</td></tr>'
              '<tr><td>H · B2</td><td class="num">−0,20</td><td class="num">+0,61</td><td>relativně opačné, absolutně ztrácejí spolu</td></tr>'
              '</tbody></table><p class="zcap">Mapa (08) je relativní; tabulka patří k ní.</p></div></div>')
    s07 = sec("07", f"Zkouška stability {CV}", "tři nastavení korelací, stanovená před výpočtem",
              '<div class="zgrid2"><div class="zcard"><h3>Co bylo stanoveno předem</h3>'
              '<p>Mapa se spočítá ve třech verzích: s korelacemi podle úsudku (elektřina mezi zeměmi 0,8, elektřina a plyn 0,6, plyn a povolenka 0,4), bez korelací (nulové korelace cen energie; překročení rozpočtu a zpoždění losována nezávisle) a se silnými korelacemi (0,95 · 0,85 · 0,4).</p>'
              '<p><b>Práh:</b> mapa je stabilní, jen pokud se každé dvě verze shodnou v pořadí 28 vzdáleností mezi lokalitami alespoň na úrovni 0,8.</p></div>'
              '<div class="zcard"><h3>Co vyšlo</h3><div class="stab">'
              '<div class="zkpi"><span class="src">úsudek × bez korelací</span><span class="v">0,95</span></div>'
              '<div class="zkpi"><span class="src">úsudek × silné</span><span class="v">0,84</span></div>'
              '<div class="zkpi bad"><span class="src">bez korelací × silné</span><span class="v">0,75</span></div></div>'
              '<p style="margin-top:8px">Vztahy v matici jsou stálejší než nakreslené polohy: shoda 0,966 · 0,899 · 0,826. Určenost: mapy z obou polovin budoucností se shodují na 0,91 proti prahu 0,59.</p></div></div>'
              f'<div class="zgrid2" style="margin-top:12px"><div><div class="src" style="margin-bottom:4px">Bez korelací: 7 spolehlivých dvojic, české lokality splývají</div><div class="zstage"><img src="{img("mv3-futures-chemvitro-nocorr")}" alt="Mapa budoucností bez korelací cen"></div></div>'
              f'<div><div class="src" style="margin-bottom:4px">Silné korelace: žádná spolehlivá dvojice, Vrbice se vzdálí od Lipové a Kamence</div><div class="zstage"><img src="{img("mv3-futures-chemvitro-strong")}" alt="Mapa budoucností se silnými korelacemi cen"></div></div></div>'
              '<div class="verd" style="margin-top:12px"><i class="ph ph-warning-circle"></i><div><b>Mapa je určená, ale není stabilní.</b> Rozložení bodů není dílem náhody při losování (0,91 proti 0,59), tvar však závisí na předpokladech o korelaci cen: dvojice verzí bez korelací a se silnými korelacemi se shoduje jen na 0,75, pod prahem 0,8. '
              'Zpráva to říká takto a z mapy čte jen výšky a dvě skupiny. Výpočet verze bez korelací podle záznamu programu nedokonvergoval; i proto jemné polohy číst opatrně. <span class="zg est">odhad</span></div></div>'
              '<p class="zcap">Výška a barva jsou ve všech třech verzích prakticky stejné (74,0–74,2 až 147,6–147,7 mil. EUR), protože průměrná úspora na korelaci téměř nezávisí. Náhodnost losování není podstatnou nejistotou: budoucnosti jsou losy modelu, ne vzorek pozorovatelů; proto zkouška určenosti a zkouška stability vůči předpokladům, obě stanovené předem.</p>')
    s08 = sec("08", f"Sedm variant v 800 scénářích {VE}", "rozložení a terén enginu; stabilita podle smlouvy režimu",
              f'<div class="zgrid2"><div class="zstage"><img src="{img("mv3-velis-scenarios")}" alt="Sociomapa systémů: sedm variant v 800 scénářích modelu, pohled shora"></div>'
              '<div><table class="zt"><thead><tr><th>Test</th><th>Výsledek</th><th style="width:60px">Práh</th><th style="width:130px">Stav</th></tr></thead><tbody>'
              '<tr><td>Chyba Monte Carlo: 10 opakování s jinými seedy, 800 losů v každém</td><td>největší odchylka r 0,02 · 11 vazeb s |r| ≥ 0,30 ve všech 10</td><td>≤ 0,03</td><td><span class="row" style="gap: 6px"><span class="stg sm done" aria-hidden="true"><i class="ph ph-check"></i></span>kreslí se jen těch 11</span></td></tr>'
              '<tr><td>Citlivost na předpoklady: korelace vstupů vypnuté · rozsah poplatku 3PL PL o polovinu širší · růst objednávek 0–14 %</td><td>posun po Procrustově zarovnání: C2 0,04 · B2 0,06 · A 0,05 · H 0,19</td><td>≤ 0,10</td><td><span class="row" style="gap: 6px"><span class="stg sm youq" aria-hidden="true"><i class="ph ph-pause"></i></span>H citlivý, označeno</span></td></tr>'
              '<tr><td>Kvalita rozložení: stres-1 proti zamíchaným datům</td><td>0,08 proti 0,31</td><td>lepší</td><td><span class="row" style="gap: 6px"><span class="stg sm done" aria-hidden="true"><i class="ph ph-check"></i></span>splněno</span></td></tr>'
              '<tr><td>Opakovaný výpočet se stejným seedem (PCG64, 20261030): ověřuje implementaci, ne vhodnost modelu (<a href="MV8Validity.dc.html">MV8</a>)</td><td>shodný bajt po bajtu</td><td>shoda</td><td><span class="row" style="gap: 6px"><span class="stg sm done" aria-hidden="true"><i class="ph ph-check"></i></span>splněno</span></td></tr>'
              '</tbody></table><p class="zcap">Stejný engine, 800 losů Modelu Velis. Zkouška stability se třemi nastaveními korelací, jak ji stanovil vzor, tu ještě není: Předpoklady Velis korelace deklarují (M2), zkoušku je třeba zapsat před dalším výpočtem.</p></div></div>')
    s09 = sec("09", "Co mapa smí tvrdit", "na obrazovce i ve zprávě",
              '<div class="zgrid2"><div class="zcard on"><b>Tvrdí ' + CV + '</b><p>V tomto modelu se německým lokalitám daří relativně lépe v týchž budoucnostech a leží v údolí nižších úspor; české a polské leží na hřebeni. '
              'Záloha mezi lokalitami neexistuje, to říká tabulka T8: Odrzyca a Kamenec selžou spolu v 75–79 % špatných budoucností.</p></div>'
              '<div class="zcard on"><b>Tvrdí ' + VE + '</b><p>V tomto modelu se C2 a B2 daří ve stejných scénářích a obě drží slib doručení; když klesnou objednávky, ztrácejí spolu. Hala (A, A2) se relativně vyplácí v opačných scénářích než C2.</p></div></div>'
              '<p style="margin: 12px 0 6px"><b>Nikdy netvrdí:</b></p><div class="never">'
              '<div><i class="ph ph-x"></i><span>že souvislost je příčinná nebo že jedna proměnná řídí druhou</span></div>'
              '<div><i class="ph ph-x"></i><span>že mapa budoucností ukazuje chování trhu nebo firmy</span></div>'
              '<div><i class="ph ph-x"></i><span>že vazba je pozorovaná; je to vlastnost modelu a obstojí jen ve smlouvě svého režimu</span></div>'
              '<div><i class="ph ph-x"></i><span>že vzdálenost na mapě je velikost účinku v jakékoli jednotce, nebo že jemné polohy platí, když zkouška stability neprošla</span></div>'
              '<div><i class="ph ph-x"></i><span>že výška terénu mezi body je odhad (je to interpolace)</span></div>'
              '<div><i class="ph ph-x"></i><span>že záloha mezi objekty existuje nebo neexistuje: to čte tabulka společných selhání, ne mapa</span></div></div>')
    s10 = sec("10", f"Expertní mapa: varianty × kritéria {VE}", "druhý režim v MVP",
              '<table class="mx"><thead><tr><th style="text-align: left">Varianta</th><th>Riziko provedení</th><th>Závislost na dodavateli</th><th>Slib doručení</th><th>Pružnost kapacity</th><th>Kapitálová náročnost</th></tr></thead><tbody>'
              '<tr><td class="l">A · Vlastní sklad</td><td>4</td><td>9</td><td>8</td><td class="dis">5 · rozptyl 2,9</td><td>2</td></tr>'
              '<tr><td class="l">A2 · Sklad po etapách</td><td>6</td><td>9</td><td>8</td><td>7</td><td>4</td></tr>'
              '<tr><td class="l">B2 · 3PL CZ, pevná cena</td><td class="hi">9</td><td>4</td><td>8</td><td>6</td><td class="hi">10</td></tr>'
              '<tr><td class="l">C2 · 3PL PL + expres</td><td>6</td><td>5</td><td class="hi">8</td><td class="dis">6 · rozptyl 3,1</td><td class="hi">9</td></tr>'
              '<tr><td class="l">H · Hybrid</td><td>4</td><td>6</td><td>8</td><td>7</td><td>8</td></tr></tbody></table>'
              '<p class="zcap">Známky 1–10 (10 = nejlepší), průměr tří hodnotitelů: výzkumník AIA, provozní ředitel klienta, finanční ředitel klienta. Kde se hodnotitelé rozcházejí (rozptyl nad 2,5), mapa nepoužije průměr, ale vzorkuje směs jejich hodnocení se stejnou vahou; mapa se ukáže i s každým hodnotitelem vynechaným. Efektivní n jsou 3 hodnotitelé, ne 15 známek.</p>')
    conv = ada("5. 11.", [
        ("ada", "15:02", ["Mapa budoucností ve vzoru je <b>určená, ale ne stabilní</b>: poloviny budoucností se shodují na 0,91, verze bez korelací a se silnými korelacemi jen na 0,75 proti prahu 0,8. Čtěte výšky a dvě skupiny, ne jemné polohy."]),
        ("me", "A záloha mezi lokalitami?", None),
        ("ada", "15:04", ["Tu čtěte z tabulky T8, ne z mapy: Odrzyca a Kamenec selžou společně v 75–79 % špatných budoucností. Centrování z mapy odstranilo právě společný vliv levného nákupu.",
                          "Pro Velis platí smlouva režimu stejně; zkoušku stability se třemi nastaveními korelací zapíšeme před dalším výpočtem."]),
    ])
    body = s01 + s02 + s03 + s04 + s05 + s06 + s07 + s08 + s09 + s10
    return frame("Model – Výsledky: Sociomapa systémů (MVP)", "Sociomapa systémů", "Výsledky · Sociomapa systémů", conv, "Sociomapa systémů",
                 body, ("KM10Market.dc.html", "Trh"), ("MV9ScenarioWeights.dc.html", "Mapa scénářů vah"), "MV3 Sociomapa systémů", 5250, banner, "Mapa scénářů vah")


# ====================================================================== MV9
ROLE_CHIP = {"saving": '<span class="zg est">úspora</span>', "part": '<span class="zg calc">v modelu</span>', "outside": '<span class="zg mod">mimo model</span>'}
ROLE_WORDS = {"saving": "úspora sama nebo její jiné vyjádření", "part": "mechanismus je uvnitř úspory", "outside": "model to nepočítá"}


def grade_chip(g):
    cls = {"odhad": "est", "výpočet": "calc", "z dat klienta": "data", "úsudek": "mod", "jmenovaní hodnotitelé": "mod", "doklad": "data"}.get(g.split(" · ")[0], "calc")
    return f'<span class="zg {cls}">{e(g)}</span>'


def fmt_val(v):
    if isinstance(v, list):
        return f"{fmt_val(v[0])}–{fmt_val(v[1])}"
    if isinstance(v, float) and not float(v).is_integer():
        return cz(v, 2).rstrip("0") if abs(v) < 2 else cz(v, 1)
    return cz(v, 0)


def components_matrix(spec, res, short, show_raw=True):
    objs = res["objs"]
    n = len(objs)
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    out = [f'<table class="smx"><thead><tr><th style="text-align:left">Perspektiva · součást</th><th style="text-align:left;width:140px">Zdroj a škála</th><th style="width:84px">Úspora</th>{th}</tr></thead><tbody>']
    for p in spec["perspectives"]:
        if not p["components"]:
            out.append(f'<tr class="cat"><td class="l" colspan="3">{e(p["name"])} <span>· bez součásti</span></td><td class="l" colspan="{n}" style="font-weight:400;color:var(--muted)">{e(p["note"])}</td></tr>')
            continue
        out.append(f'<tr class="cat"><td class="l" colspan="{3 + n}">{e(p["name"])} <span>· váha perspektivy jednou, připuštěné součásti ji sdílejí rovným dílem</span></td></tr>')
        for c in p["components"]:
            if c.get("info"):
                src = f'<span class="sub">{e(c["source"] or "")} {grade_chip(c["grade"]) if c.get("grade") else ""}</span>'
                out.append(f'<tr class="inforow"><td class="l"><b style="font-weight:500">{e(c["name"])}</b></td><td class="l">{src}</td>'
                           f'<td class="l" colspan="{1 + n}">{e(c["text"])}</td></tr>')
                continue
            lo, hi = c["anchors"]
            sub = []
            if c.get("gate"):
                sub.append(f"také brána {c['gate']}")
            if c.get("overlap"):
                sub.append(f"Překryv: {e(c['overlap'])}")
            if c.get("state"):
                sub.append(e(c["state"]))
            label = (f'<td class="l"><span class="ck">{c["code"]}</span><b>{e(c["name"])}</b> <span class="sub">{e(c["unit"])}' + (("<br>" + " · ".join(sub)) if sub else "") + '</span></td>'
                     f'<td class="l"><span class="sub">{e(c["source"])} {grade_chip(c["grade"])}</span><span class="sub">0 = {fmt_val(lo)} · 10 = {fmt_val(hi)}</span></td>'
                     f'<td style="text-align:center">{ROLE_CHIP[c["role"]]}</td>')
            tds = []
            for o in objs:
                x = res["cells"][c["code"]][o]
                raw = c["values"][o]
                if x is None:
                    tds.append('<td class="s"><span class="na">n/a</span><small>neuplatní se</small></td>')
                elif x["ranged"]:
                    tds.append(f'<td class="s u">{cz(x["lo"], 1)}–{cz(x["hi"], 1)}<small>{fmt_val(raw)}</small></td>')
                else:
                    cls = "hi" if x["lo"] >= 8 else ("lo" if x["lo"] <= 2 else "")
                    tds.append(f'<td class="s {cls}">{cz(x["lo"], 1)}' + (f'<small>{fmt_val(raw)}</small>' if show_raw else "") + '</td>')
            out.append(f"<tr>{label}{''.join(tds)}</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def gates_table(spec, res, short):
    objs = res["objs"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows_ = []
    for g in spec["gates"]:
        tds = "".join(f'<td style="text-align:center"><span class="gp {g["values"][o][0]}">{ {"pass": "ano", "fail": "ne", "unknown": "?"}[g["values"][o][0]] }<small>{e(g["values"][o][1])}</small></span></td>' for o in objs)
        rows_.append(f'<tr><td class="l"><b>{g["code"]}</b> {e(g["name"])}<span class="sub">{e(g["source"])}</span></td>{tds}</tr>')
    for s in spec["gate_settings"]:
        st = res["settings"][s["code"]]["state"]
        tds = "".join(f'<td style="text-align:center"><span class="gp {st[o]}">{ {"pass": "prošla", "fail": "ne", "unknown": "?"}[st[o]] }</span></td>' for o in objs)
        rows_.append(f'<tr class="cat"><td class="l">{e(s["name"])}' + (f'<span class="sub">{e(s["source"])}</span>' if s.get("source") else "") + f'</td>{tds}</tr>')
    return f'<table class="smx"><thead><tr><th style="text-align:left">Brána</th>{th}</tr></thead><tbody>{"".join(rows_)}</tbody></table>'


def fam_name(spec, f):
    return f'<span class="fam-{f}">{f}</span> {e(spec["families"][f]["name"])}' if f else "—"


def scenarios_table(spec, res):
    ps = spec["perspectives"]
    th = "".join(f'<th>{e(p["name"])}</th>' for p in ps if res["scenarios"] and any(s["w"].get(p["code"]) for s in res["scenarios"]))
    shown = [p for p in ps if any(s["w"].get(p["code"]) for s in res["scenarios"])]
    rows_ = []
    for r in res["refused"]:
        tds = "".join((f'<td class="num">{cz(r["weights"][p["code"]], 2)}</td>' if r["weights"].get(p["code"]) else '<td class="num" style="color:var(--faint)">0</td>') for p in shown)
        rows_.append(f'<tr class="refused"><td class="l"><b>{e(r["name"])}</b><span class="sub">{e(r["who"])} · přes všechny součásti</span></td><td class="l"><span class="gp fail">odmítnuto</span><span class="sub">{e(r["reason"])}: ' +
                     ", ".join(ROLE_WORDS[x] for x in r["roles"] if x in ("saving", "part")) + f'; nabídnuty rodiny {" a ".join(r["offered"])}</span></td>{tds}</tr>')
    for s in res["scenarios"]:
        tds = "".join((f'<td style="white-space:nowrap"><span class="wbar"><i style="width:{s["w"][p["code"]] * 100:.0f}%"></i></span><span class="wv">{cz(s["w"][p["code"]], 2)}</span></td>' if s["w"].get(p["code"]) else '<td class="num" style="color:var(--faint)">0</td>') for p in shown)
        rows_.append(f'<tr><td class="l"><b>{e(s["name"])}</b><span class="sub">{e(s["who"])}</span></td><td class="l" style="white-space:nowrap">{fam_name(spec, s["family"])}</td>{tds}</tr>')
    return f'<table class="smx"><thead><tr><th style="text-align:left;width:210px">Scénář</th><th style="text-align:left;width:230px">Rodina</th>{th}</tr></thead><tbody>{"".join(rows_)}</tbody></table>'


def firsts_table(spec, res, short, setting_code=None):
    objs = res["objs"]
    th = "".join(f"<th>{e(short[o])}</th>" for o in objs)
    rows_ = []
    for s in res["scenarios"]:
        lead = s["first"]
        tds = "".join(f'<td class="num {"lead" if o == lead else ""} {"nil" if s["share"][o] == 0 else ""}">{pct(s["share"][o])}</td>' for o in objs)
        gate = ""
        if setting_code:
            f = s["by_setting"][setting_code]["first"]
            gate = f'<td class="first">{e(short[f]) if f else "žádná"}</td>'
        rows_.append(f'<tr><td class="l"><b>{e(s["name"])}</b></td><td class="first">{e(short[lead])} <span class="src">{cz(s["centre"][lead], 2)}</span></td>{gate}{tds}</tr>')
    pooled = "".join(f'<td class="num {"nil" if res["pooled"][o] == 0 else ""}"><b>{pct(res["pooled"][o])}</b></td>' for o in objs)
    rows_.append(f'<tr class="cat"><td class="l">Všechna testovaná nastavení</td><td>{res["rows"]} řádků</td>{"<td></td>" if setting_code else ""}{pooled}</tr>')
    gh = '<th style="text-align:left">První po branách</th>' if setting_code else ""
    return (f'<table class="smx fam"><thead><tr><th style="text-align:left;width:130px">Scénář</th><th style="text-align:left">Vede ve středu (preference)</th>{gh}{th}</tr></thead>'
            f'<tbody>{"".join(rows_)}</tbody></table>')


def critical_lines(spec, res, short):
    comps = {c["code"]: c for p in spec["perspectives"] for c in p["components"] if not c.get("info")}
    seen = {}
    for s in res["scenarios"]:
        for k, o, t in s["critical"]:
            seen.setdefault((k, o), []).append((s["name"], t))
    if not seen:
        return '<p class="zcap">Žádný rozsah by sám o sobě nezměnil, kdo vede: chybějící údaje tu o pořadí nerozhodují.</p>'
    items = []
    for (k, o), hits in seen.items():
        c = comps[k]
        items.append(f'<div class="zq"><span class="n">?</span><div><b>{e(short[o])}</b> · {k} {e(c["name"])}: na horní mezi rozsahu ({fmt_val(c["values"][o])} {e(c["unit"])}) by vedla ve scénáři '
                     + ", ".join(f"{e(n)} ({cz(t, 2)})" for n, t in hits) + f'.<span class="why">Rozhodující neznámá: doložit ({e(c["source"])}), jinak zpráva uvede oba případy.</span></div></div>')
    return '<div class="zlead" style="gap:8px">' + "".join(items) + "</div>"


def coincident(case, objs, short):
    """Objects the renderer drew on one spot (within 6 % of the layout's extent), so the board names what the labels cannot."""
    g = ENG[case]
    pts = g.get("points")
    if not pts:
        return ""
    ext = g["extent"] or 1.0
    groups = []
    seen = set()
    for i, (xi, yi) in enumerate(pts):
        if i in seen:
            continue
        grp = [j for j, (xj, yj) in enumerate(pts) if ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5 < 0.06 * ext]
        if len(grp) > 1:
            groups.append(grp)
            seen.update(grp)
    if not groups:
        return "každý objekt na svém místě"
    return "na jednom místě " + "; ".join(" a ".join(e(short[objs[j]]) for j in grp) for grp in groups)


def engine_note(case):
    g = ENG[case]
    cred = g["credibility"] or {}
    seg = g["segments"] or {}
    return (f'{g["rows"]} řádků · rozložení {e(str(g["method"]))} · určenost (dvě poloviny řádků) {cz(cred.get("split_half"), 2) if cred.get("split_half") is not None else "nespočtena"} proti prahu {cz(cred.get("threshold", 0.59), 2)}'
            + (f' · engine rozlišil {seg.get("k")} skupiny řádků' if seg.get("decision") == "SEGMENTS" or (seg.get("k") or 0) > 1 else "")
            + '; statistiku dvojic nečteme (řádky jsou nastavení, která volíme).')


def mv9():
    short_cv = {o["id"]: o["name"] for o in SC["objects"]}
    short_ve = {"A": "A", "A2": "A2", "B": "B", "B2": "B2", "C": "C", "C2": "C2", "H": "H"}
    owner = next(s for s in RC["scenarios"] if s["code"] == RC["owner_scenario"])
    log = next(s for s in RC["scenarios"] if s["code"] == "LOG_B")
    refused = RC["refused"][0]
    fam_a, fam_b = SC["families"]["a"], SC["families"]["b"]
    banner = ('<div class="zbar"><i class="ph ph-scales"></i><span>Informace o preferencích, ne doporučení · podíly jsou podíly testovaných nastavení, ne pravděpodobnosti · rozhoduje pravidlo klienta · '
              'brány se nekompenzují · stojí vedle mapy budoucností (<a href="MV3SystemMap.dc.html">MV3</a>), nikdy se s ní neslučuje · ve zprávě patří do „Co by závěr změnilo“ · '
              'metoda čeká na schválení metodikem (vlastní zápis v Metodice).</span></div>')
    s01 = sec("01", f"Perspektivy a součásti {CV}", f"{RC['scored']} skórovaných součástí · zdroj, stupeň, směr, schválená škála · co model už počítá",
              components_matrix(SC, RC, short_cv) +
              '<p class="zcap">Velké číslo je skóre 0–10 na škále schválené se zadavatelem (0 = horší kotva, 10 = lepší, mezi nimi lineárně, mimo ně oříznuto); pod ním hodnota ze zprávy. '
              'Čárkovaná buňka je rozsah: zpráva údaj neuvádí jedním číslem, součást si rozsah ponechá a základem výpočtu je doložené minimum; n/a se neuplatní a nenese váhu. '
              'Sloupec Úspora je kontrola překryvů: <span class="zg est">úspora</span> je úspora sama nebo její jiné vyjádření (IRR, návratnost, NPV po zdanění), '
              '<span class="zg calc">v modelu</span> je její část, <span class="zg mod">mimo model</span> model nepočítá. Řádky bez skóre jsou stejné pro všechny lokality, informační, nebo se neuplatní; brány (02) součástmi nejsou. '
              'Čísla: zpráva 2, tabulky T1, T4, T5, T6, T8, T9, kapitoly 4, 6, 9 a 13.</p>')
    s02 = sec("02", f"Brány: pravidlo finanční ředitelky {CV}", "čtyři podmínky zapsané 2. 11. 2026, žádná není součást, žádná se nekompenzuje",
              gates_table(SC, RC, short_cv) +
              '<div class="verd" style="margin-top:12px"><i class="ph ph-warning-circle"></i><div><b>Dnes branami neprojde žádná lokalita</b>, a mapa proto nemůže nikoho označit za první po branách: ukazuje jen preference. '
              'Po písemném stanovisku úřadů, že kompenzační opatření uložena nebudou, by prošly Lipová, Kamenec a Odrzyca (výroba včas 0,942); Vrbice a Bory překračují limity a kompenzace u nich zůstává, německé lokality nesplní riziko ztráty. '
              'Lokalita vyřazená branou je na mapě pro srovnání, první nikdy; neznámá brána by znamenala „nelze doporučit, dokud není doloženo“.</div></div>')
    s03 = sec("03", f"Kontrola překryvů a scénáře vah {CV}", f"{len(RC['scenarios'])} připuštěných scénářů ve dvou rodinách · jeden odmítnutý · vějíř {RC['fan']['draws']} losů",
              f'<div class="verd" style="margin-bottom:12px"><i class="ph ph-prohibit"></i><div><b>{e(refused["name"])}: finance 0,5 · provoz 0,3 · logistika 0,2 přes všechny součásti je odmítnuto.</b> '
              'Úspora (F1) už drží provozní náklad i dopravu; provoz a logistika by se tak počítaly dvakrát. Kontrola překryvů nabídne místo toho dvě poctivé rodiny: '
              f'<b>a</b> {e(fam_a["name"])} (úspora, společné selhání, obsazení míst, nábor v okolí) a <b>b</b> {e(fam_b["name"])} (investice, energie, údržba, odpad, doprava, vlečka, most, povolování, lidé). '
              'Zadání („logistika 0,3, provoz 0,5, finance 0,2“) je v rodině b scénář LOG · b, finance v něm znamenají investici a její strop.</div></div>'
              + scenarios_table(SC, RC) +
              f'<p class="zcap">Scénář je pojmenovaný vektor vah nad perspektivami s rodinou; připuštěné součásti perspektivy sdílejí její váhu, perspektiva bez připuštěné součásti váhu nemá (Strategická v rodině b, Provozní a Prostředí v rodině a). '
              f'Skládá ho zadavatel nebo lidé klienta; tady {e(SC["composed"])}. Kolem každého středu losuje vějíř váhy z Dirichletova rozdělení s koncentrací {RC["fan"]["concentration"]} '
              f'(směrodatná odchylka váhy kolem 0,04–0,06), {RC["fan"]["draws"]} losů na scénář, seed {RC["fan"]["seed"]}; ostatní vstupy zůstávají na základu, takže vějíř zkouší jen váhy.</p>')
    s04 = sec("04", f"Mapa scénářů vah {CV}", f"aia-sociomap-5 · {RC['rows']} testovaných vah jako řádky · 8 lokalit",
              f'<div class="zgrid2"><div class="zstage"><img src="{img("si-weights-chemvitro-top")}" alt="Mapa scénářů vah, pohled shora: osm lokalit"></div>'
              f'<div class="zstage"><img src="{img("si-weights-chemvitro-3d")}" alt="Mapa scénářů vah, pohled z boku"></div></div>'
              f'<div class="zgrid2" style="margin-top:12px"><div class="zstage"><img src="{img("si-weights-chemvitro-respondents")}" alt="Testované váhy jako body"></div>'
              + HOW.format(rows=rows([
                  ("Řádky", f"{RC['rows']} testovaných vah: {len(RC['scenarios'])} středů obou rodin a jejich vějíře; každý řádek hodnotí lokalitu jejím váženým skóre 0–10"),
                  ("Výška", f"skóre pod scénářem {e(owner['name'])} (vlastník pravidla): {e(short_cv[owner['first']])} {cz(owner['centre'][owner['first']], 2)} nejvýš; mapa je relativní (každý řádek vycentrován), absolutní čtení jsou skóre v tabulce 05"),
                  ("Blízko sebe", "lokality, které vycházejí dobře ve stejných vahách; v pohledu s body se vějíře shlukují podle scénářů a rodin"),
                  ("Brány", "lokalita vyřazená branou je na mapě pro srovnání (02)"),
                  ("Překryvy", coincident("chemvitro", RC["objs"], short_cv) + ": tytéž váhy jim prospívají stejně, renderer popíše jen jeden štítek"),
                  ("Engine", engine_note("chemvitro")),
              ])) + '</div>'
              '<p class="zcap">Spočítal engine aia-sociomap-5 a nakreslil renderer AIA, kterým zpráva kreslí mapy; v pohledu s body engine nazývá testované váhy respondenty. Mapa je interní: režim čeká na zápis metodika do registru metod.</p>')
    s05 = sec("05", f"Kdo je první v každém scénáři {CV}", "ve středu scénáře a v podílu losů vějíře",
              firsts_table(SC, RC, short_cv, "urady") +
              '<p class="zcap">Vede ve středu: lokalita s nejvyšším skóre při vahách scénáře a doloženém minimu, mezi všemi osmi: informace o preferencích. První po branách: totéž jen mezi lokalitami, které by prošly po stanovisku úřadů (02); dnes neprojde žádná. '
              'Podíl v %: v kolika losech vějíře je lokalita první mezi všemi; podíly testovaných nastavení, ne pravděpodobnosti. Spodní řádek pojí všechny scénáře obou rodin.</p>'
              '<div style="margin-top:12px"><b style="font-size:13.5px">Rozhodující rozsah</b>' + critical_lines(SC, RC, short_cv) + '</div>')
    velis_owner = next(s for s in RV["scenarios"] if s["code"] == RV["owner_scenario"])
    s06 = sec("06", f"Druhý případ {VE}", f"sedm možností · {RV['scored']} součástí ze SI1 · {RV['rows']} testovaných vah · jen rodina a",
              components_matrix(SV, RV, short_ve, show_raw=False) +
              '<p class="zcap">Skóre jsou buňky matice SI2 (pravidla SI1); neznámá kapacita 3PL CZ (F2 u B a B2) zůstává rozsahem. E1 a R1 jsou úspora a její chvost z téhož modelu, ostatní součásti model nepočítá; části úspory SI1 vypustil, takže Velis má jen rodinu a. '
              'Slib doručení je brána G1 (C ji nesplní), investiční strop G2.</p>'
              '<div style="margin-top:12px">' + scenarios_table(SV, RV) + f'<p class="zcap">{e(SV["composed"])}; sečteno po perspektivách.</p></div>'
              '<div style="margin-top:12px">' + firsts_table(SV, RV, short_ve, "dnes") + '<p class="zcap">Vede ve středu mezi všemi sedmi; první po branách mezi těmi, které G1 a G2 pustí (C ne). Podíly: losy vějíře, ve kterých je možnost první.</p></div>'
              f'<div class="zgrid2" style="margin-top:12px"><div class="zstage"><img src="{img("si-weights-velis-top")}" alt="Mapa scénářů vah Velis, pohled shora"></div>'
              f'<div class="zstage"><img src="{img("si-weights-velis-respondents")}" alt="Testované váhy Velis jako body"></div></div>'
              + '<div class="zcard" style="margin-top:12px"><div class="zrow"><span class="zk">Jiná stavba, jiný první</span><span class="zv">SI3 váží sedm kritérií přímo a na doloženém minimu vede C2 (7,70). Tady perspektiva počítá jednou a součásti ji sdílejí, takže Finanční je průměr E1, R1 a P2; '
              f'pod vahami FR vede {e(short_ve[velis_owner["first"]])} ({cz(velis_owner["centre"][velis_owner["first"]], 2)}), pod OR, VL a rovnými vahami H. To je citlivost na stavbu (SI3 §02), ne nový výsledek: pravidlo klienta zůstává u Výsledků.</span></div>'
              f'<div class="zrow"><span class="zk">Engine</span><span class="zv">{engine_note("velis")} Překryvy: {coincident("velis", RV["objs"], short_ve)}.</span></div>'
              + '<div class="zrow"><span class="zk">Rozhodující rozsah</span><span class="zv">' + ("; ".join(f"{e(s['name'])}: {', '.join(e(short_ve[o]) + ' přes ' + k for k, o, _ in s['critical'])}" for s in RV["scenarios"] if s["critical"]) or "žádný") + '</span></div></div>')
    s07 = sec("07", "Co mapa tvrdí a co ne", "pravidla revize metodiky z 5. 11.",
              '<div class="rules">'
              '<div><b>Preference, ne doporučení</b>Mapa říká, komu se daří pod kterými vahami. Doporučení dává pravidlo klienta nad Výsledky; mapa jde do „Co by závěr změnilo“.</div>'
              '<div><b>Podíly nastavení, ne pravděpodobnosti</b>Vějíř i jeho koncentraci volíme my; podíl popisuje test, ne svět.</div>'
              '<div><b>Brány se nekompenzují</b>Lokalita vyřazená branou není první, ať skóruje jakkoli; neznámá brána znamená „nelze doporučit, dokud není doloženo“.</div>'
              '<div><b>Jeden mechanismus jednou</b>Vektor, který váží úsporu i její část, je odmítnut jménem a dostane dvě rodiny; chybějící součást je rozsah, ne skóre.</div>'
              '<div><b>Vedle mapy budoucností</b>Řádky mapy budoucností jsou losy modelu, řádky této mapy váhy lidí; nikdy v jedné mapě. Metoda má vlastní zápis v Metodice, interní do schválení.</div></div>')
    conv = ada("8. 11.", [
        ("ada", "10:12", [f"Váhy „finance 0,5 · provoz 0,3 · logistika 0,2“ přes všechno jsem <b>odmítla</b>: úspora už provoz a dopravu drží, počítaly by se dvakrát. Nabízím dvě rodiny: úsporu proti tomu, co model nepočítá, a části úspory proti sobě."]),
        ("me", "A kdo vede?", None),
        ("ada", "10:13", [f"V rodině a pod vahami finanční ředitelky <b>{e(short_cv[owner['first']])}</b> ({cz(owner['centre'][owner['first']], 2)}); v rodině b pod zadáním (LOG · b) {e(short_cv[log['first']])} v {pct(log['share'][log['first']])} losů vějíře. Dnes ale branami neprojde nikdo: pravidlo čeká na stanovisko úřadů.",
                          "Jsou to preference. Do zprávy to patří do „Co by závěr změnilo“, ne do doporučení."]),
    ])
    body = s01 + s02 + s03 + s04 + s05 + s06 + s07
    return frame("Model – Sociomapa: mapa scénářů vah (MVP)", "Sociomapa: mapa scénářů vah", "Sociomapa · mapa scénářů vah", conv, "Mapa scénářů vah",
                 body, ("MV3SystemMap.dc.html", "Sociomapa systémů"), ("SI1Method.dc.html", "Sociomapa z indikátorů"), "MV9 Mapa scénářů vah", 7560, banner, "Sociomapa z indikátorů")


if __name__ == "__main__":
    for name, fn in (("MV3SystemMap.dc.html", mv3), ("MV9ScenarioWeights.dc.html", mv9)):
        with open(os.path.join(OUT, name), "w") as f:
            f.write(fn())
        print("wrote", name)
