# Medora Patient Experience DEMO — integrační handoff

## Účel
Read-only showcase projekt typu **Patient experience / service redesign** z oblasti **Zdravotní služby**. Má se zobrazit v Historii ihned po instalaci/migraci a otevřít bez AI/API volání.

## Co musí uživatel vidět
1. Co projekt přinesl — executive answer, hlavní KPI, rozhodnutí a next steps.
2. Zadání — původní brief, rozhodovací problém, doplňující otázky.
3. Research/design — hypotézy, zdroje/dimenzní vrstvy, nejistoty.
4. Dotazník/metodika — otázky, tracked objects a měřené atributy.
5. Publikum — populace, n=900, segmenty a dimenze.
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
**Největší problém není samotná péče, ale nejistota před návštěvou: objednání, čekání a nedostatek informací. Koncept „Guided Care“ s jasným časem, přednávštěvními instrukcemi a jednoduchým follow-upem má nejvyšší experience score.**

Doporučení: **Implementovat Guided Care jako standard služby; prioritou je transparentní čekání a navigace, nikoli další digitální funkce.**

## Acceptance criteria
- Projekt je viditelný v Historii a filtrován jako DEMO.
- Všechny taby mají obsah okamžitě.
- Otevření nevolá provider/web.
- Report a exporty jsou skutečně stažitelné.
- 8 světů, sociomapa a segmenty jsou rozkliknutelné.
- Copy-to-new-project nemutuje seed.
- DEMO se nezapočítává do produkční validace, benchmarků ani učení.
