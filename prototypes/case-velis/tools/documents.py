"""Write the Velis case pack's client documents as HTML, one page per <section>.

Run from the repo root:  python prototypes/case-velis/tools/documents.py
then:                    node prototypes/case-velis/tools/pdf.mjs
The PDFs land in prototypes/case-velis/documents/. Every company, person and number is fictional.
Page numbers matter: the case's facts sit on the pages CASE.md cites (e.g. the 3PL fee on p. 4).
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "documents" / "html"
OUT.mkdir(parents=True, exist_ok=True)

CSS = """
@page{size:A4;margin:22mm 20mm 20mm}
body{font:11pt/1.5 'DejaVu Serif',Georgia,serif;color:#111}
section{page-break-after:always;position:relative;min-height:240mm}
section:last-child{page-break-after:auto}
h1{font:600 18pt/1.25 'DejaVu Sans',Arial,sans-serif;margin:0 0 6mm}
h2{font:600 13pt/1.3 'DejaVu Sans',Arial,sans-serif;margin:7mm 0 3mm}
table{border-collapse:collapse;width:100%;margin:3mm 0;font-size:10pt}
td,th{border:1px solid #999;padding:4px 6px;text-align:left;vertical-align:top}
th{background:#eee}
.num{text-align:right;white-space:nowrap}
.fict{font:9pt 'DejaVu Sans',Arial,sans-serif;color:#a33;border:1px solid #a33;padding:2px 6px;display:inline-block;margin-bottom:6mm}
.foot{position:absolute;bottom:0;left:0;right:0;font:9pt 'DejaVu Sans',Arial,sans-serif;color:#555;border-top:1px solid #ccc;padding-top:2mm;display:flex;justify-content:space-between}
.mail{font:10.5pt/1.5 'DejaVu Sans Mono',monospace;white-space:pre-wrap}
"""


def doc(name: str, title: str, pages: list[str]) -> None:
    n = len(pages)
    body = "".join(
        f"<section>{'<div class="fict">Fiktivní dokument · případová studie AIA Velis · žádná skutečná firma ani osoba</div>' if i == 0 else ''}"
        f"{p}<div class='foot'><span>{title}</span><span>strana {i + 1} z {n}</span></div></section>"
        for i, p in enumerate(pages)
    )
    (OUT / f"{name}.html").write_text(
        f"<!doctype html><html lang='cs'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>",
        encoding="utf-8",
    )


# ------------------------------------------------------------------ 3PL CZ contract, 9 pages
doc(
    "smlouva_3PL_CZ",
    "Smlouva o logistických službách č. 2021/014",
    [
        """<h1>Smlouva o logistických službách č. 2021/014</h1>
    <p>uzavřená podle § 1746 odst. 2 zákona č. 89/2012 Sb., občanský zákoník</p>
    <h2>Smluvní strany</h2>
    <p><b>Delta Fulfillment CZ s.r.o.</b> (fiktivní), se sídlem Logistická 12, Modřice, dále jen „poskytovatel“</p>
    <p><b>Velis Commerce s.r.o.</b> (fiktivní), se sídlem Vinohradská 210, Praha, dále jen „klient“</p>
    <p>Datum uzavření: 1. 3. 2021. Účinnost: 1. 4. 2021.</p>""",
        """<h2>1. Předmět smlouvy</h2>
    <p>1.1 Poskytovatel zajišťuje pro klienta příjem zboží, skladování, vychystání, balení a předání zásilek dopravcům
    (dále „expedice“) ze skladu Modřice. 1.2 Doprava k zákazníkovi není předmětem smlouvy; zajišťují ji dopravci
    sjednaní klientem, poskytovatel jim zásilky předává. 1.3 Vratky přijímá poskytovatel a vrací je na sklad do 48 hodin.</p>""",
        """<h2>2. Úroveň služeb</h2>
    <p>2.1 Objednávky přijaté do 14:00 poskytovatel expeduje týž pracovní den. 2.2 Při této expedici dopravci klienta
    doručují v Praze, Brně, Ostravě a Plzni zpravidla následující pracovní den a jinde do dvou pracovních dnů.
    2.3 Za každý den zpoždění expedice z viny poskytovatele náleží klientovi sleva 2 % z poplatku za dotčené objednávky.</p>""",
        """<h2>3. Ceny za expedici</h2>
    <table><tr><th>Služba</th><th class='num'>Cena bez DPH</th></tr>
    <tr><td>Expedice jedné objednávky (vychystání, balení, předání dopravci), do 5 položek</td><td class='num'>46,00 Kč</td></tr>
    <tr><td>Každá další položka nad 5</td><td class='num'>3,00 Kč</td></tr>
    <tr><td>Zpracování vratky</td><td class='num'>18,00 Kč</td></tr></table>
    <p>3.2 Ceny platí v letech 2025 a 2026; úprava podle článku 5 k 1. 1. 2026 byla dodatkem č. 3 odložena na 1. 1. 2027. Průměrná objednávka klienta má 2,3 položky.</p>""",
        """<h2>4. Skladné</h2>
    <p>4.1 Skladné činí 400 000 Kč bez DPH měsíčně za vyhrazenou kapacitu do 6 000 paletových míst.
    4.2 Nad tuto kapacitu 75 Kč za paletové místo a měsíc. 4.3 Skladné se upravuje podle článku 5.</p>""",
        """<h2>5. Úprava cen</h2>
    <p>5.1 Ceny podle článků 3 a 4 se k 1. 1. každého roku upraví o součet meziroční míry inflace (ČSÚ) a poloviny
    meziročního růstu průměrné mzdy v odvětví doprava a skladování (ČSÚ), nejméně však o 3 % a nejvýše o 7 %.
    5.2 Poskytovatel oznámil, že pro rok 2027 očekává úpravu o 5 %.</p>""",
        """<h2>6. Odpovědnost a pojištění</h2>
    <p>6.1 Poskytovatel odpovídá za zboží od převzetí do předání dopravci, do výše 2 000 000 Kč za škodní událost.
    6.2 Poskytovatel je pojištěn u pojišťovny s limitem 50 000 000 Kč.</p>""",
        """<h2>7. Trvání a výpověď</h2>
    <p>7.1 Smlouva se uzavírá na dobu neurčitou. 7.2 Každá ze stran ji může vypovědět bez udání důvodu.
    <b>Výpovědní doba činí šest (6) měsíců</b> a počíná prvním dnem měsíce následujícího po doručení výpovědi.
    7.3 Výpověď doručená v prosinci 2026 tedy ukončí smlouvu 30. 6. 2027. 7.4 Po skončení smlouvy poskytovatel
    součinně předá zásoby novému poskytovateli; náklady převozu nese klient.</p>""",
        """<h2>8. Závěrečná ustanovení</h2><p>Změny smlouvy jen písemnými dodatky.</p>
    <p>V Modřicích dne 1. 3. 2021</p><p>za poskytovatele: jednatel · za klienta: jednatel</p>""",
    ],
)

# ------------------------------------------------------------------ 3PL CZ fixed-price offer (B2), e-mail
doc(
    "dodatek_3PL_CZ_email",
    "E-mail: nabídka dodatku s pevnou cenou",
    [
        """<div class='mail'>Od: obchod@delta-fulfillment.example
Komu: logistika@velis.example
Datum: 12. 10. 2026
Předmět: Pevná cena na 5 let – návrh dodatku ke smlouvě 2021/014

Dobrý den,

jak jsme se domluvili, nabízíme dodatek ke smlouvě:

- poplatek za expedici objednávky pevně 50,50 Kč bez DPH
  (dnešních 46,00 Kč + příplatek 4,50 Kč za pevnou cenu)
  na 5 let od 1. 1. 2027 do 31. 12. 2031, bez úpravy podle čl. 5;
- skladné se dál upravuje podle čl. 5;
- výpovědní doba se po dobu dodatku prodlužuje na 12 měsíců.

Příplatek můžeme snížit až na 3,50 Kč, pokud klient garantuje
aspoň 400 000 objednávek ročně; při nižší garanci až 6,00 Kč.
Nabídka platí do 31. 12. 2026.

S pozdravem
obchodní ředitel, Delta Fulfillment CZ s.r.o. (fiktivní)</div>""",
    ],
)

# ------------------------------------------------------------------ warehouse extension offer (A), 6 pages
doc(
    "nabidka_hala",
    "Nabídka: rozšíření skladu Velis o 2 000 m²",
    [
        """<h1>Nabídka: rozšíření skladu o 2 000 m² a vlastní expedice</h1>
    <p><b>Haly Morava stavební a.s.</b> (fiktivní) pro Velis Commerce s.r.o., 30. 9. 2026</p>
    <p>Klient dnes používá vlastní sklad 800 m² v Jihlavě jen pro vratky a výprodeje. Nabízíme jeho rozšíření o 2 000 m²
    a vybavení pro plnou expedici e-shopu.</p>
    <h2>Cena</h2>
    <table><tr><th>Varianta vybavení</th><th class='num'>Cena bez DPH</th></tr>
    <tr><td>Základní (regály, ruční vychystávání)</td><td class='num'>62 mil. Kč</td></tr>
    <tr><td><b>Doporučená</b> (třídicí linka, WMS)</td><td class='num'><b>70 mil. Kč</b></td></tr>
    <tr><td>S automatizací (shuttle systém)</td><td class='num'>84 mil. Kč</td></tr></table>""",
        """<h2>Harmonogram</h2>
    <p>Stavba a vybavení trvají <b>12 měsíců</b> od podpisu smlouvy a vydání stavebního povolení. Povolení očekáváme
    do 3 měsíců. Etapové řešení je možné: 60 % kapacity hned (cena 42 mil. Kč), zbytek později (35 mil. Kč, cena
    roku 2029).</p>""",
        """<h2>Kapacita</h2>
    <p>Ve dvousměnném provozu <b>620 000 objednávek ročně</b>; se třetí směnou ve špičkách (listopad, prosinec) až
    680 000. Při základní variantě vybavení 560 000. Potřeba lidí: 34 FTE ve dvou směnách.</p>""",
        """<h2>Zůstatková hodnota</h2>
    <p>Znalecký odhad zůstatkové hodnoty haly a vybavení po 7 letech: <b>55 % pořizovací ceny</b>, v rozmezí
    40–65 % podle stavu trhu průmyslových nemovitostí v kraji.</p>""",
        """<h2>Provozní náklady (odhad dodavatele)</h2>
    <table><tr><th>Položka</th><th class='num'>Hodnota</th></tr>
    <tr><td>Fixní provoz (energie, údržba, ostraha, vedoucí skladu)</td><td class='num'>6,2 mil. Kč ročně</td></tr>
    <tr><td>Náklad na objednávku (mzdy skladníků, obaly)</td><td class='num'>32 Kč</td></tr></table>
    <p>Ceny roku 2026; mzdy rostou s trhem práce.</p>""",
        """<h2>Podmínky</h2><p>Platnost nabídky do 31. 1. 2027. Záloha 20 % při podpisu, zbytek podle etap.
    Záruka na stavbu 5 let, na technologii 2 roky.</p>""",
    ],
)

# ------------------------------------------------------------------ Polish 3PL offer (C), 7 pages
doc(
    "nabidka_3PL_PL",
    "Oferta: fulfilment z Polska pro Velis",
    [
        """<h1>Nabídka fulfilmentu ze skladu Katovice</h1>
    <p><b>Wisła Fulfilment sp. z o.o.</b> (fiktivní) pro Velis Commerce s.r.o., 25. 9. 2026</p>
    <p>Nabízíme převzetí celé expedice e-shopu Velis ze skladu v Katovicích na 7 let.</p>""",
        """<h2>Ceny</h2>
    <table><tr><th>Služba</th><th class='num'>Cena bez DPH</th></tr>
    <tr><td>Expedice jedné objednávky</td><td class='num'>34,00 Kč (1,36 EUR)</td></tr>
    <tr><td>Skladné, vyhrazená kapacita 7 000 paletových míst</td><td class='num'>3,1 mil. Kč ročně</td></tr></table>
    <p>Ceny přepočteny kurzem 25,00 Kč/EUR; fakturace v EUR. Podle rozsahu služeb 31–38 Kč za objednávku.</p>""",
        """<h2>Doprava do ČR a doba doručení</h2>
    <p>Svoz do třídicího centra dopravce v ČR: <b>6 Kč za objednávku</b> (5–8 Kč podle naplnění vozu).
    Doba doručení zákazníkům v ČR: <b>ve velkých městech do 2 pracovních dnů, jinde do 3</b>, tedy všude
    o den déle než dnes.</p>""",
        """<h2>Kapacita</h2><p>Vyhrazeno <b>50 000 objednávek měsíčně</b>; navýšení na 70 000 s výpovědní lhůtou 3 měsíce.
    Ve špičce listopad–prosinec garantujeme 60 000 měsíčně.</p>""",
        """<h2>Úprava cen</h2><p>Ceny se upravují k 1. 1. o růst minimální mzdy v Polsku, v pásmu 2–5 %; v posledních
    třech letech v průměru 3 % ročně.</p>""",
        """<h2>Úroveň služeb a sankce</h2><p>Expedice týž den do 13:00. Sleva 3 % z poplatku za každý den zpoždění z naší viny.</p>""",
        """<h2>Doba a ukončení</h2><p>Smlouva na 7 let. Předčasné ukončení klientem po 3. roce s poplatkem 6 měsíčních
    skladných. Převzetí zásob a napojení systémů zajistíme s klientem; náklady přechodu nese klient.</p>""",
    ],
)

# ------------------------------------------------------------------ express courier offer (C2)
doc(
    "nabidka_kuryr_expres",
    "Nabídka: expresní doručení ve velkých městech",
    [
        """<h1>Expresní doručení ve velkých městech</h1>
    <p><b>Rychlík Kurýr s.r.o.</b> (fiktivní) pro Velis Commerce s.r.o., 8. 10. 2026</p>
    <p>Pro zásilky z polského skladu nabízíme doručení <b>následující pracovní den</b> v Praze, Brně, Ostravě a Plzni
    přes noční svoz a překládku v Ostravě.</p>
    <table><tr><th>Objem měsíčně</th><th class='num'>Příplatek za objednávku</th></tr>
    <tr><td>do 10 000</td><td class='num'>14 Kč</td></tr><tr><td>10 000–20 000</td><td class='num'>10 Kč</td></tr>
    <tr><td>nad 20 000</td><td class='num'>8 Kč</td></tr></table>
    <p>Odhad pro Velis: 38 % objednávek ve velkých městech, tj. kolem 13 000 měsíčně, tedy 10 Kč.</p>""",
    ],
)
print("html written to", OUT)
