# NPC Panel — 10 kompletních DEMO projektů

Tento balík obsahuje 10 read-only showcase projektů z odlišných oborů a typů výzkumu. Cílem je, aby Historie panelu na první spuštění ukazovala šíři produktu, nikoli jen jeden typ produktového testu.

## Projekty
1. **NOVA Spark DEMO** — Uvedení nového produktu / FMCG / nápoje
2. **Aurora Bank Rebrand DEMO** — Rebranding a brand equity / Bankovnictví / fintech
3. **Volba města DEMO** — Předvolební veřejné mínění a image kandidátů / Politika / veřejné mínění
4. **Město 2035 DEMO** — Policy acceptance a trade-off research / Veřejná politika / městská správa
5. **Medora Patient Experience DEMO** — Patient experience / service redesign / Zdravotní služby
6. **Nexora Employee Climate DEMO** — Employee climate, leadership a týmová sociomapa / HR / organizace
7. **RailMove Service Concept DEMO** — Service concept a pricing research / Doprava / mobilita
8. **EduNova Learning Platform DEMO** — Concept + UX research / Vzdělávání / edtech
9. **Streamio Brand & Content DEMO** — Brand positioning + content portfolio / Média / streaming
10. **GreenHome Tariff DEMO** — Tariff proposition + trust research / Energetika / utility

## Globální implementační pravidla
- Všechny projekty jsou označené **DEMO** a jsou read-only.
- Otevření nesmí volat AI, web ani placeného providera.
- Každý projekt používá stejný ProjectStore/ArtifactStore/History/Downloads jako ostré projekty.
- Každý projekt má tlačítko **Vytvořit kopii jako nový projekt**.
- Kopie je editovatelná a od té chvíle používá normální ostrou pipeline.
- DEMO projekty se nezapočítávají do learningu, dynamické populace, benchmarků ani validačních metrik.
- Default tab je **Co projekt přinesl**. Uživatel se teprve potom může vracet od zadání k metodice.
- Každý projekt obsahuje skutečné download artefakty: DOCX, XLSX, CSV, SVG/PNG, JSONy, 8 světů, 8 analysis modulů a projektový ZIP.
- U politického DEMO výstup zůstává deskriptivní a nesmí být transformován na cílený persuasion engine.

## Doporučené filtry Historie
`Vše | DEMO | Výzkum | Politika | Značka | Produkt | Public policy | Employee | Service/UX`

## Loader
Použij `DEMO_REGISTRY.json` jako registry. Na bootstrap/migraci projdi položky a zavolej lokální adapter v každé složce pouze pokud seed ještě neexistuje.
