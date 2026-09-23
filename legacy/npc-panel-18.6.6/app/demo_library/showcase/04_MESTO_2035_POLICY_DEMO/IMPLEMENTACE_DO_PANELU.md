# Město 2035 DEMO — integrační handoff

## Účel
Read-only showcase projekt typu **Policy acceptance a trade-off research** z oblasti **Veřejná politika / městská správa**. Má se zobrazit v Historii ihned po instalaci/migraci a otevřít bez AI/API volání.

## Co musí uživatel vidět
1. Co projekt přinesl — executive answer, hlavní KPI, rozhodnutí a next steps.
2. Zadání — původní brief, rozhodovací problém, doplňující otázky.
3. Research/design — hypotézy, zdroje/dimenzní vrstvy, nejistoty.
4. Dotazník/metodika — otázky, tracked objects a měřené atributy.
5. Publikum — populace, n=1300, segmenty a dimenze.
6. Objekty & sociomapování — stejné object_id napříč questionnaire/results/mapou.
7. Sběr / modelové světy — 8 samostatných světů s assumptions a výsledky.
8. Výsledky — KPI objektů, segmenty, robustnost a interpretace.
9. Report — celý příběh v UI + skutečný DOCX.
10. Historie — 7 immutable revizí + provenance/impact.
11. Ke stažení — DOCX, XLSX, CSV, JSON, SVG/PNG, world JSONy, analysis JSONy a project ZIP.

## Zásadní pravidla
- Uživatelsky označovat jen **DEMO**; neprezentovat hodnoty jako skutečný výzkum.
- DEMO je deterministický seed a nesmí se dopočítávat.
- Otevření DEMO nesmí spotřebovat Claude/API kredit ani měnit learning/dynamickou populaci.
- Tlačítko **Vytvořit kopii jako nový projekt** vytvoří editovatelnou kopii a teprve ta používá ostrou pipeline.
- Všechny downloady musí používat normální ArtifactStore/Downloads cestu, nikoli speciální demo endpoint.
- Sociomapa je analytický výstup; minimálně vrstvy perception / emotion / segment resonance.
- Každý svět je rozkliknutelný a musí vysvětlit změněný předpoklad a dopad na výsledek.

## Projektový závěr
**Samostatné restrikce mají nízkou podporu. Nejlépe funguje vyvážený balíček „Invest & Manage“: zlepšení MHD + rezidentní parkování + postupné řízení vjezdu do centra. Přijatelnost roste, když lidé vidí konkrétní protihodnotu.**

Doporučení: **Preferovat Invest & Manage a komunikovat trade-off transparentně; největší riziko je zavedení restrikcí před zlepšením alternativ.**

## Acceptance criteria
- Projekt je viditelný v Historii a filtrován jako DEMO.
- Všechny taby mají obsah okamžitě.
- Otevření nevolá provider/web.
- Report a exporty jsou skutečně stažitelné.
- 8 světů, sociomapa a segmenty jsou rozkliknutelné.
- Copy-to-new-project nemutuje seed.
- DEMO se nezapočítává do produkční validace, benchmarků ani učení.
