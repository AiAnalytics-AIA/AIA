"""ChemVitro case · writes the client's documents: HTML sources in ../documents/html/, PDFs in ../documents/ (headless Chrome).

Run:  ~/.venvs/aia-panel/bin/python ChemVitro/tools/documents.py
Every page carries the 'fictional' banner. Numbers come from params.py; the PDFs differ between runs only in Chrome's
creation date.
"""
import os, subprocess
from pathlib import Path
from params import SITES, SITE_ORDER, TRAPS, COMPANY, BUY, PROCESS, DECISION, TIMING, EPC_ACCURACY

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'documents' / 'html'; HTML.mkdir(parents=True, exist_ok=True)
CHROME = os.environ.get('CHROME', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
BANNER = 'Fiktivní dokument · případová studie AIA ChemVitro · žádná skutečná firma, obec ani osoba'
CSS = """@page { size: A4; margin: 20mm 20mm 18mm 20mm; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; color: #1b1b1b; margin: 0; }
.page { page-break-after: always; position: relative; min-height: 245mm; }
.page:last-child { page-break-after: auto; }
.banner { font: 8pt Helvetica, Arial, sans-serif; color: #8a1c1c; border-bottom: 1px solid #e3c9c9; padding-bottom: 2mm; margin-bottom: 8mm; }
.foot { position: absolute; bottom: 0; left: 0; right: 0; font: 8.5pt Helvetica, Arial, sans-serif; color: #666; border-top: 1px solid #ddd;
  padding-top: 2mm; display: flex; justify-content: space-between; }
h1 { font-size: 17pt; margin: 0 0 3mm; } h2 { font-size: 13pt; margin: 6mm 0 2mm; } .sub { color: #555; margin-bottom: 6mm; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0 5mm; font-size: 10pt; }
th, td { border-bottom: 1px solid #ccc; padding: 2mm 2.5mm; text-align: left; vertical-align: top; } th { background: #f3f3f3; }
td.n { text-align: right; white-space: nowrap; } .small { font-size: 9pt; color: #444; } .letter p { margin: 0 0 3mm; }
"""


def doc(name, title, pages):
    n = len(pages)
    body = ''.join(f'<div class="page"><div class="banner">{BANNER}</div>{p}<div class="foot"><span>{title}</span><span>strana {i + 1} z {n}</span></div></div>'
                   for i, p in enumerate(pages))
    html = f'<!doctype html><html lang="cs"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>'
    path = HTML / f'{name}.html'; path.write_text(html, encoding='utf-8')
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={ROOT / "documents" / (name + ".pdf")}',
                    path.as_uri()], check=True, capture_output=True)
    print(name, n, 'pages')


def eur(x): return f'{x:,.1f}'.replace(',', '\u00a0').replace('.', ',')
def num(x): return f'{x:,}'.replace(',', '\u00a0')
def czdate(iso): y, m, d = iso.split('-'); return f'{int(d)}.\u00a0{int(m)}.\u00a0{y}'


# ---------------------------------------------------------------- 1. project brief
def brief():
    doc('zadani_projektu', 'Projekt VTX-40 Make: zadání', [
        f"""<h1>Projekt VTX-40 Make</h1><div class="sub">ChemVitro a.s. (fiktivní), Brno · interní zadání představenstva · 12. 10. 2026</div>
<p>ChemVitro používá ve svých závodech v Brně a Pardubicích meziprodukt VTX-40. Dnes ho celý kupuje od jediného dodavatele,
Hanshin Fine Chemicals (fiktivní), s dopravou z Asie. Představenstvo chce posoudit vlastní výrobu v EU.</p>
<p>Spotřeba v roce 2026 je asi {num(COMPANY['use_t_2026'])} t a roste o 1–3 % ročně. Prodávat VTX-40 jiným firmám nechceme; závod bude vyrábět jen pro naše dva závody.</p>""",
        f"""<h2>Současné dodávky</h2>
<p>Smlouva s dodavatelem končí {czdate(BUY['contract_end'])}. Dodavatel v září 2026 oznámil,
že prodloužení nabídne jen za vyšší cenu (dopis_dodavatele.pdf). Výpadek dodávek v únoru 2026 jsme řešili nákupem na spotovém trhu.</p>
<h2>Co chceme</h2>
<ul><li>závod na {num(COMPANY['capacity_t'])} t VTX-40 ročně, jeden návrh procesu pro každou lokalitu (proces_emise_odpady.xlsx);</li>
<li>výroba nejpozději od {czdate(DECISION['start_by'])}, aby nebylo nutné prodlužovat smlouvu;</li>
<li>investice nejvýše {DECISION['capex_ceiling_m']} mil. EUR včetně všeho, co lokalita vyžaduje;</li>
<li>osm lokalit v Česku, Německu a Polsku, které prošly prvním výběrem (nabidky_lokalit.pdf).</li></ul>""",
        """<h2>Čeho se bojíme</h2>
<ul><li>konkurence o lidi: v některých regionech nabírají velcí zaměstnavatelé;</li>
<li>odpadní vody z procesu (kyselé, se sírany) a nebezpečné odpady;</li>
<li>poplatky za emise CO₂ a za nebezpečné odpady, které se mohou měnit;</li>
<li>dostupnost a mzdy operátorů v každé zemi;</li>
<li>povolování: jak dlouho trvá a co může úřad požadovat navíc;</li>
<li>doprava surovin a produktu k našim závodům.</li></ul>""",
        f"""<h2>Tým a role</h2>
<table><tr><th>Kód</th><th>Role</th><th>Odpovídá za</th></tr>
<tr><td>FR</td><td>finanční ředitelka</td><td>pravidlo rozhodnutí, diskontní sazba, investiční strop</td></tr>
<tr><td>VR</td><td>výrobní ředitel</td><td>návrh procesu, harmonogram, provoz</td></tr>
<tr><td>EHS</td><td>vedoucí EHS</td><td>povolení, emise, odpady, odpadní vody</td></tr>
<tr><td>HR</td><td>personální ředitelka</td><td>nábor, mzdy, průzkum pracovníků</td></tr>
<tr><td>LOG</td><td>vedoucí logistiky</td><td>doprava surovin a produktu</td></tr>
<tr><td>NAK</td><td>vedoucí nákupu</td><td>smlouva s dodavatelem, nabídky energií a odpadů</td></tr></table>
<p class="small">Hodnocení lokalit (hodnoceni_lokalit.csv) vyplnilo dvanáct lidí včetně externího konzultanta lokalitní agentury LokaPartner, která zprostředkovala část nabídek.</p>"""])


# ---------------------------------------------------------------- 2. supplier letter
def supplier():
    lo, hi = BUY['renewal_rise']
    doc('dopis_dodavatele', 'Hanshin Fine Chemicals: prodloužení smlouvy', [f"""<div class="letter">
<p><b>Hanshin Fine Chemicals Co. (fiktivní)</b> · Europe Sales Office · Rotterdam</p><p>ChemVitro a.s., nákup · Brno</p><p>Rotterdam, 18. 9. 2026</p>
<p><b>Věc: dodávky VTX-40 po skončení smlouvy</b></p>
<p>Vážení, naše smlouva o dodávkách VTX-40 končí 30. 6. 2030. Rádi bychom spolupráci prodloužili. Vzhledem k nákladům na energii a dopravu
a k poptávce v Asii vám ale nemůžeme nabídnout současné podmínky.</p>
<p>Prodloužení na dalších 5 let nabídneme za cenu o <b>{round(100 * lo)}–{round(100 * hi)} %</b> vyšší, než bude cena v roce 2029, podle vývoje trhu.
Podmínkou je odběr nejméně 30 000 t ročně. Závaznou nabídku pošleme nejdříve v polovině roku 2029.</p>
<p>Do konce smlouvy platí cenový vzorec podle čl. 4 (vazba na index surovin, nejvýše ±10 % ročně).</p>
<p>S pozdravem, Regional Sales Director Europe</p></div>"""])


# ---------------------------------------------------------------- 3. site brochures (optimistic, by the agencies)
BROCHURE = {
 'CZ1': ('Průmyslová zóna Labe-jih, Vrbice', 'Tradiční chemická oblast s kvalifikovanou pracovní silou a vlečkou přímo v zóně. Odpadní vody převezme průmyslová ČOV zóny. Kraj podporuje investice do chemie. Pozemek 22 ha připraven, územní plán schválen.'),
 'CZ2': ('Park Lipová', 'Klidná lokalita s nízkými náklady, napojení na městskou ČOV s volnou kapacitou a dobrou dostupností do Brna i Pardubic. Pozemky 19 ha v majetku města, rychlé jednání.'),
 'CZ3': ('Průmyslová zóna Kamenec', 'Zóna těžké výroby u dálnice D1 s provozovanou vlečkou a vlastní průmyslovou ČOV. Velký trh práce. Pobídka až 25 %.'),
 'DE1': ('Chemiepark Wendelstedt', 'Etablierter Chemiepark mit Werksbahn, Industriekläranlage, Dampf- und Energieversorgung sowie Genehmigungsservice. Standortentgelt für Parkleistungen nach Vereinbarung.'),
 'DE2': ('Industriegebiet Lindenau-Ost', 'Erschlossenes Industriegebiet an der B6, Anschluss an die kommunale Kläranlage, günstige Grundstückspreise, GRW-Förderung bis 20 %.'),
 'DE3': ('Gewerbepark Eschfeld', 'Attraktiver Standort in Bayern nahe der tschechischen Grenze, Bahnstrecke in 0,8 km, Anbindung über die Kreisstraße an die A93. Hohe Lebensqualität.'),
 'PL1': ('Park Przemysłowy Odrzyca', 'Duży teren inwestycyjny przy autostradzie A4, bocznica kolejowa w odległości 3,4 km, własna oczyszczalnia przemysłowa parku, zwolnienie z CIT w ramach Polskiej Strefy Inwestycji.'),
 'PL2': ('Strefa Aktywności Gospodarczej Bory', 'Doskonała lokalizacja w sercu Śląska przy A1, bocznica w strefie, podłączenie do miejskiej oczyszczalni, najniższe koszty pracy i gruntów, zwolnienie z CIT do 50 %.'),
}


def brochures():
    pages = []
    for k in SITE_ORDER:
        s = SITES[k]; t, txt = BROCHURE[k]
        pages.append(f"""<h1>{t}</h1><div class="sub">{s['region']} · výtah ChemVitro z nabídky lokalitní agentury · říjen 2026 · lokalita {k}</div><p><i>Agentura (v původním znění):</i> „{txt}“</p>
<table><tr><th>Údaj</th><th>Hodnota</th></tr><tr><td>Plocha k dispozici</td><td>{s['plot_ha']} ha</td></tr>
<tr><td>Cena pozemku</td><td>{s['land_eur_m2']} EUR/m²</td></tr><tr><td>Železnice</td><td>{s['rail']}</td></tr><tr><td>Silnice</td><td>{s['road']}</td></tr>
<tr><td>Odpadní vody</td><td>{s['ww_body']}</td></tr><tr><td>Pobídky</td><td>{s['incentive']}</td></tr></table>
<p class="small">Údaje o pobídkách jsou orientační a podléhají schválení příslušným orgánem.</p>""")
    doc('nabidky_lokalit', 'Nabídky lokalit', pages)


# ---------------------------------------------------------------- 4. EPC estimate
def epc():
    rows = ''.join(f"<tr><td>{k}</td><td>{SITES[k]['name']}</td><td class='n'>{SITES[k]['epc_m']}</td><td class='n'>{eur(SITES[k]['epc_m'] * (1 - EPC_ACCURACY))}–{eur(SITES[k]['epc_m'] * (1 + EPC_ACCURACY))}</td></tr>" for k in SITE_ORDER)
    pmin, plik, pmax = TIMING['permit_months']; bmin, blik, bmax = TIMING['build_months']
    doc('epc_odhad', 'Odhad investice EPC', [
        f"""<h1>Odhad investičních nákladů</h1><div class="sub">IndustrieBau EPC GmbH (fiktivní) pro ChemVitro a.s. · třída odhadu 4 · 20. 10. 2026</div>
<p>Odhad pro závod na 40 000 t VTX-40 ročně podle koncepčního návrhu procesu ChemVitro. Ceny roku 2026, bez DPH, přesnost ±{round(100 * EPC_ACCURACY)} %.</p>
<table><tr><th>Kód</th><th>Lokalita</th><th>Odhad (mil. EUR)</th><th>Pásmo ±{round(100 * EPC_ACCURACY)} %</th></tr>{rows}</table>""",
        f"""<h2>Harmonogram</h2><table><tr><th>Fáze</th><th>Minimum</th><th>Nejspíš</th><th>Maximum</th></tr>
<tr><td>Povolení (EIA, integrované povolení, stavební povolení)</td><td>{pmin} měsíců</td><td>{plik} měsíců</td><td>{pmax} měsíců</td></tr>
<tr><td>Výstavba a najetí</td><td>{bmin} měsíců</td><td>{blik} měsíců</td><td>{bmax} měsíců</td></tr></table>
<p>Harmonogram předpokládá rozhodnutí o lokalitě v únoru 2027 a podání žádostí bezprostředně poté. Pro chemické parky s povolovací službou bývá povolení kratší.</p>""",
        """<h2>Co odhad zahrnuje a co ne</h2><p><b>Zahrnuje:</b> procesní jednotky, sklady surovin a produktu, parní kotel 24 MW, neutralizaci odpadních vod,
oxidaci odpadních plynů v provedení podle BAT, rozvody, řídicí systém, stavební část v areálu, projekt, najetí.</p>
<p><b>Nezahrnuje:</b> pozemek; infrastrukturu mimo areál (vlečky, přípojky, úpravy komunikací a mostů); předčištění odpadních vod nad rámec neutralizace;
kompenzační opatření a technologie nad rámec BAT, pokud je úřad uloží; poplatky za služby chemického parku; rezervu na rizika lokality;
pobídky a dotace.</p><p class="small">Odhad třídy 4 se podle zkušenosti v oboru odchyluje od skutečnosti oběma směry; nejčastěji je skutečnost vyšší.</p>"""])


# ---------------------------------------------------------------- 5. wastewater statements (one per site, comparable detail)
def wastewater():
    t2, d2 = TRAPS['CZ2'], TRAPS['DE2']; n = ' '
    head = lambda title, sub: f'<h1>{title}</h1><div class="sub">{sub}</div>'
    pages = {
     'CZ1': head('Vyjádření: Labe-jih Servis s.r.o.', 'provozovatel průmyslové ČOV zóny Labe-jih · lokalita CZ1 · 14. 10. 2026') +
        f"""<p>Průmyslová ČOV zóny Labe-jih (biologická linka pro průmyslové vody, 6{n}000 m³ denně) převezme odpadní vody ChemVitro
po neutralizaci v areálu. Volná kapacita je v současnosti asi 2{n}400 m³ denně.</p>
<p>Limity pro vody přiváděné do ČOV zóny: sírany do 2{n}500 mg/l, CHSK do 4{n}000 mg/l, pH 6–9, teplota do 40 °C.
Podmínkou je kontinuální měření průtoku a pH na výstupu z areálu a čtvrtletní rozbory. Přípojka do 300 m je součástí zóny.</p>
<p>Stočné podle ceníku zóny (energie_a_poplatky.csv); poplatek za připojení jednorázově 600{n}000 Kč.</p>""",
     'CZ2': head('Vyjádření: Vodovody Lipovsko a.s.', 'provozovatel městské ČOV Lipová · lokalita CZ2 · 16. 10. 2026') +
        f"""<p>Městská ČOV Lipová (12{n}000 EO) má volnou hydraulickou kapacitu asi {t2['spare_m3_day']} m³ denně a odpadní
vody z Parku Lipová převezme podle kanalizačního řádu města. Přípojku k hranici parku vybuduje město.</p>
<p>Kanalizační řád stanoví pro vody vypouštěné do kanalizace mimo jiné: <b>sírany nejvýše {t2['limits']['sulfate']} mg/l,
CHSK nejvýše {t2['limits']['cod']} mg/l</b>, pH 6–9. Při překročení limitů účtujeme příplatek za nadlimitní znečištění
{round(t2['surcharge_eur_m3'] * 24.3)} Kč/m³ nad běžné stočné, nebo může vlastník kanalizace podmínit napojení předčištěním v areálu producenta.</p>
<p>Údaje o složení vašich odpadních vod jsme zatím neobdrželi. Stočné podle ceníku (energie_a_poplatky.csv).</p>""",
     'CZ3': head('Vyjádření: Kamenec Infra a.s.', 'provozovatel průmyslové ČOV zóny Kamenec · lokalita CZ3 · 13. 10. 2026') +
        f"""<p>Průmyslová ČOV zóny Kamenec převezme odpadní vody ChemVitro po neutralizaci v areálu. Volná kapacita je asi
1{n}800 m³ denně; ČOV od roku 2024 zpracovává vody dvou chemických provozů v zóně.</p>
<p>Limity: sírany do 2{n}200 mg/l, CHSK do 3{n}500 mg/l, pH 6–9. Při CHSK nad 3{n}000 mg/l účtujeme příplatek podle ceníku zóny.
Podmínkou je havarijní jímka v areálu na objem jednoho dne a měsíční rozbory.</p>
<p>Stočné podle ceníku zóny (energie_a_poplatky.csv). Připojení v ceně pozemku.</p>""",
     'DE1': head('Stellungnahme: Chemiepark Wendelstedt Services GmbH', 'Industriekläranlage · lokalita DE1 · 15.10.2026') +
        f"""<p>Die Industriekläranlage des Chemieparks (Kapazität 14{n}000 m³/Tag, frei derzeit rund 3{n}000 m³/Tag) übernimmt das
neutralisierte Abwasser über das parkeigene Kanalnetz.</p>
<p>Annahmebedingungen: Sulfat bis 3{n}000 mg/l, CSB bis 5{n}000 mg/l, pH 6–9; Eigenüberwachung nach Parkordnung.
Die Einleitung ist durch die wasserrechtliche Erlaubnis des Parks abgedeckt.</p>
<p>Entgelt laut Preisliste des Parks; die Abwasserbehandlung ist Teil der Parkleistungen. Das Standortentgelt für die Parkleistungen (Infrastruktur, Werkfeuerwehr, Genehmigungsservice) beträgt für ein Baufeld dieser Größe rund 1,1 Mio. € pro Jahr.</p>
<p class="small">Poznámka ChemVitro (překlad): ČOV parku přijme neutralizované vody; sírany do 3{n}000, CHSK do 5{n}000 mg/l; volná kapacita asi 3{n}000 m³ denně; povolení kryje park; poplatek za služby parku asi 1,1 mil. EUR ročně.</p>""",
     'DE2': head('Stellungnahme: Abwasserzweckverband Lindenau', 'kommunale Kläranlage Lindenau · lokalita DE2 · 17.10.2026') +
        f"""<p>Die kommunale Kläranlage Lindenau (25{n}000 EW) kann aus dem Industriegebiet Lindenau-Ost derzeit
<b>höchstens {d2['spare_m3_day']} m³ pro Tag</b> zusätzlich aufnehmen. Für Indirekteinleiter gelten Sulfat bis
{d2['limits']['sulfate']} mg/l und CSB bis {num(d2['limits']['cod'])} mg/l.</p>
<p>Größere Mengen oder höhere Konzentrationen erfordern eine eigene Vorbehandlung auf dem Werksgelände; ein Teil des Abwassers
müsste gegebenenfalls nach Vorbehandlung direkt eingeleitet werden (wasserrechtliche Erlaubnis der unteren Wasserbehörde erforderlich).</p>
<p class="small">Poznámka ChemVitro (překlad): ČOV přijme nejvýše {d2['spare_m3_day']} m³ denně; sírany do {d2['limits']['sulfate']} mg/l, CHSK do {num(d2['limits']['cod'])} mg/l. Větší množství = vlastní předčištění, případně přímé vypouštění s povolením.</p>""",
     'DE3': head('Stellungnahme: Gemeindewerke Eschfeld', 'kommunale Kläranlage Eschfeld · lokalita DE3 · 20.10.2026') +
        f"""<p>Die kommunale Kläranlage Eschfeld (40{n}000 EW, mit separater Linie für Gewerbeabwasser) kann rund 900 m³/Tag
neutralisiertes Abwasser aus dem Gewerbepark aufnehmen.</p>
<p>Grenzwerte laut Indirekteinleitergenehmigung: Sulfat bis 2{n}000 mg/l, CSB bis 2{n}800 mg/l, pH 6,5–9. Ab CSB 2{n}500 mg/l
wird ein Starkverschmutzerzuschlag erhoben.</p>
<p>Entgelt laut Satzung (energie_a_poplatky.csv).</p>
<p class="small">Poznámka ChemVitro (překlad): ČOV přijme asi 900 m³ denně; sírany do 2{n}000, CHSK do 2{n}800 mg/l; od CHSK 2{n}500 mg/l příplatek za silné znečištění.</p>""",
     'PL1': head('Opinia: Odrzyca Park Sp. z o.o.', 'oczyszczalnia przemysłowa parku · lokalita PL1 · 14.10.2026') +
        f"""<p>Oczyszczalnia przemysłowa parku (przepustowość 5{n}000 m³/dobę, wolna ok. 1{n}600 m³/dobę) przyjmie ścieki po neutralizacji.</p>
<p>Dopuszczalne wartości: siarczany do 2{n}000 mg/l, ChZT do 3{n}000 mg/l, pH 6–9. Wymagany zbiornik retencyjny na terenie zakładu
i pomiary ciągłe przepływu.</p><p>Opłata według cennika parku.</p>
<p class="small">Poznámka ChemVitro (překlad): ČOV parku přijme neutralizované vody; sírany do 2{n}000, CHSK do 3{n}000 mg/l; volná kapacita asi 1{n}600 m³ denně; nutná retenční nádrž.</p>""",
     'PL2': head('Opinia: PWiK Bory Sp. z o.o.', 'miejska oczyszczalnia Bory · lokalita PL2 · 15.10.2026') +
        f"""<p>Miejska oczyszczalnia Bory (90{n}000 RLM, po modernizacji w 2023 r.) przyjmie ścieki po neutralizacji ze Strefy Aktywności
Gospodarczej. Wolna przepustowość ok. 2{n}000 m³/dobę.</p>
<p>Warunki wprowadzania ścieków przemysłowych: siarczany do 2{n}000 mg/l, ChZT do 3{n}000 mg/l, pH 6–9; wymagana umowa
o odprowadzanie ścieków i zgłoszenie zgodnie z prawem wodnym.</p><p>Opłata według taryfy PWiK.</p>
<p class="small">Poznámka ChemVitro (překlad): městská ČOV přijme neutralizované vody; sírany do 2{n}000, CHSK do 3{n}000 mg/l; volná kapacita asi 2{n}000 m³ denně.</p>""",
    }
    doc('vyjadreni_cov', 'Vyjádření provozovatelů ČOV', [pages[k] for k in SITE_ORDER])


# ---------------------------------------------------------------- 6. rail and road statements (one per site, comparable detail)
def transport():
    p1, d3 = TRAPS['PL1'], TRAPS['DE3']; n = ' '
    head = lambda title, sub: f'<h1>{title}</h1><div class="sub">{sub}</div>'
    pages = {
     'CZ1': head('Vyjádření: Labe-jih Servis s.r.o., správa vlečky', 'doprava · lokalita CZ1 · 13. 10. 2026') +
        """<p>Vlečka zóny Labe-jih je v provozu (obsluha dvakrát denně). Připojení areálu kolejí do 300 m je součástí zóny; ChemVitro
by hradilo jen kolejiště v areálu, které je v rozsahu EPC.</p>
<p>Příjezd ze silnice I. třídy (2 km) po komunikaci zóny bez omezení hmotnosti. Stáčiště cisteren je v rozsahu EPC.</p>""",
     'CZ2': head('Vyjádření: Město Lipová, odbor dopravy', 'doprava · lokalita CZ2 · 15. 10. 2026') +
        """<p>Železniční stanice Lipová je 1,1 km od parku; vlečka do parku není a město ji neplánuje. Suroviny lze dovážet po železnici
na veřejné překladiště ve stanici (provozovatel Lipovská logistika s.r.o.) a odtud cisternami.</p>
<p>Silnice II. třídy k parku je bez omezení hmotnosti. Pro připojení areálu je třeba odbočovací pruh; jeho stavbu (odhad
2 mil. Kč) hradí investor.</p>""",
     'CZ3': head('Vyjádření: Kamenec Infra a.s., správa vlečky', 'doprava · lokalita CZ3 · 13. 10. 2026') +
        """<p>Provozovaná vlečka zóny Kamenec (kapacita 12 vozů denně, dnes využita z poloviny); připojení areálu je v ceně pozemku.</p>
<p>Přístup k dálnici D1 (4 km) po čtyřpruhové komunikaci zóny bez omezení hmotnosti.</p>""",
     'DE1': head('Stellungnahme: Chemiepark Wendelstedt Services GmbH, Logistik', 'doprava · lokalita DE1 · 15.10.2026') +
        """<p>Werksbahn des Chemieparks mit täglicher Bedienung; Anschluss des Baufelds über vorhandene Gleise, Rangierleistungen im
Parkentgelt enthalten. Straßenanbindung zur A9 (6 km) ohne Gewichtsbeschränkung.</p>
<p class="small">Poznámka ChemVitro (překlad): vlečka parku s denní obsluhou, připojení po stávajících kolejích, posun v poplatku parku; silnice bez omezení hmotnosti.</p>""",
     'DE2': head('Stellungnahme: Stadt Lindenau, Tiefbauamt', 'doprava · lokalita DE2 · 16.10.2026') +
        """<p>Im Industriegebiet Lindenau-Ost gibt es keinen Gleisanschluss; der Bahnhof Lindenau liegt 2,5 km entfernt, Umschlag über das
Güterverkehrszentrum Lindenau. Die Straßenanbindung über die B6 (3 km) ist ohne Einschränkung.</p>
<p class="small">Poznámka ChemVitro (překlad): bez vlečky; nádraží 2,5 km, překládka v nákladním centru; silnice B6 bez omezení.</p>""",
     'DE3': head('Stellungnahme: Landratsamt, Tiefbau', 'Zufahrt Gewerbepark Eschfeld · lokalita DE3 · 22.10.2026') +
        f"""<p>Die Zufahrt zum Gewerbepark führt über die Kreisstraße und die Brücke über den Eschbach. Die Brücke ist für ein zulässiges
Gesamtgewicht von <b>{d3['bridge_limit_t']} t</b> ausgelegt. Für den regelmäßigen Verkehr mit Tankwagen bis {d3['tanker_t']} t ist eine Ertüchtigung erforderlich.</p>
<p>Die Kosten trägt der Vorhabenträger (Schätzung {str(d3['reinforcement_m'][0]).replace('.', ',')}–{str(d3['reinforcement_m'][1]).replace('.', ',')} Mio. €).
Eine Genehmigung der Zufahrt für den Schwerverkehr kann erst nach Abschluss der Ertüchtigung erteilt werden. Die Bahnstrecke (0,8 km) hat keinen Anschluss.</p>
<p class="small">Poznámka ChemVitro (překlad): most má limit {d3['bridge_limit_t']} t; cisterny {d3['tanker_t']} t vyžadují zesílení na náklady investora, povolení příjezdu až po dokončení. Trať bez vlečky.</p>""",
     'PL1': head('Opinia: Zarząd Infrastruktury Kolejowej Opole (fiktivní)', 'bocznica Park Przemysłowy Odrzyca · lokalita PL1 · 19.10.2026') +
        f"""<p>Przyłączenie parku do linii kolejowej jest technicznie możliwe w odległości ok. <b>{str(p1['spur_km']).replace('.', ',')} km</b>.
Budowę bocznicy, wykup gruntów pod tor i uzgodnienia finansuje inwestor. Szacunkowy czas realizacji: 14–24 miesiące od uzyskania praw do gruntu.</p>
<p>Do czasu budowy bocznicy dostawy możliwe wyłącznie transportem drogowym przez terminal przeładunkowy. Dojazd do A4 (5 km) bez ograniczeń tonażu.</p>
<p class="small">Poznámka ChemVitro (překlad): vlečku asi {str(p1['spur_km']).replace('.', ',')} km i výkup pozemků platí investor; 14–24 měsíců od získání pozemků. Do té doby jen kamiony přes překladiště. Silnice bez omezení.</p>""",
     'PL2': head('Opinia: Zarząd Strefy Aktywności Gospodarczej Bory', 'doprava · lokalita PL2 · 16.10.2026') +
        """<p>Bocznica w strefie jest czynna; przyłączenie działki w cenie gruntu. Dojazd do A1 (3 km) drogą powiatową bez ograniczeń
tonażu (nośność 11,5 t/oś).</p>
<p class="small">Poznámka ChemVitro (překlad): vlečka v zóně v provozu, připojení v ceně pozemku; silnice k A1 bez omezení hmotnosti.</p>""",
    }
    doc('vyjadreni_doprava', 'Vyjádření k dopravě', [pages[k] for k in SITE_ORDER])


# ---------------------------------------------------------------- 7. air permitting memo
def air_memo():
    doc('memo_povolovani_ovzdusi', 'Memo: povolování emisí do ovzduší', [
        f"""<h1>Povolování zdroje emisí do ovzduší: Česko, Německo, Polsko</h1><div class="sub">EnviroConsult (fiktivní) pro vedoucí EHS ChemVitro · 21. 10. 2026</div>
<p>Závod VTX-40 bude zdrojem VOC, NOx a CO₂. Parní kotel o příkonu {PROCESS['boiler_mw']} MW přesahuje 20 MW, takže zařízení spadá do systému EU pro obchodování
s emisemi (EU ETS) a za emise CO₂ z kotle bude nutné vyřazovat povolenky. Proces podléhá integrovanému povolení (IPPC) a závěrům o BAT.</p>
<p>Kde stanice v okolí ukazují překročení imisních limitů, bývá povolování přísnější. Doporučujeme porovnat data nejbližší stanice s limity:
PM10 40 µg/m³, PM2,5 25 µg/m³, NO₂ 40 µg/m³ (roční průměry) a cílovým imisním limitem benzo[a]pyrenu 1 ng/m³.</p>""",
        """<h2>Česko</h2><p>V oblastech, kde je překročen imisní limit, může orgán ochrany ovzduší podmínit povolení nového zdroje kompenzačním opatřením,
tedy snížením emisí jinde v téže oblasti, které investor zajistí a zaplatí (např. výměna kotlů v domácnostech, modernizace cizího zdroje).
Úřad také obvykle požaduje emisní limity na spodní hranici rozmezí BAT a technologii nad jejich rámec.</p>
<p>Ze zkušenosti: kompenzační opatření stojí jednotky až nižší desítky milionů eur a povolení se prodlouží o 9–15 měsíců, protože opatření je třeba najít,
smluvně zajistit a doložit.</p>""",
        """<h2>Německo a Polsko</h2><p><b>Německo:</b> v oblastech s plánem čistoty ovzduší (Luftreinhalteplan) úřad uplatní TA Luft přísněji a může omezit
přírůstek emisí. Chemické parky mají povolování zavedené a obvykle rychlejší.</p>
<p><b>Polsko:</b> v zónách, kde jsou limity překročeny a platí program ochrany ovzduší (program ochrony powietrza), lze uložit přísnější podmínky a vyrovnání emisí; povolení se tam prodlužuje
o 12–18 měsíců. Slezsko patří dlouhodobě k oblastem s nejhorší kvalitou ovzduší v EU.</p>
<p class="small">Memo nehodnotí jednotlivé lokality; data stanic jsou v ovzdusi_stanice.csv.</p>"""])


if __name__ == '__main__':
    brief(); supplier(); brochures(); epc(); wastewater(); transport(); air_memo()
