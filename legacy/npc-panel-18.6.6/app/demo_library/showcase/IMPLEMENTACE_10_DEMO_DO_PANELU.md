# NPC Panel — implementace 10 showcase DEMO projektů

## Cíl
Napojit tento balík do aktuální verze panelu jako předvyplněnou sekci Historie / DEMO. Projekty demonstrují různé výzkumné úlohy, nikoli jeden produktový use case.

## 10 typů
1. NOVA Spark — uvedení produktu / FMCG.
2. Aurora Bank — rebranding a brand equity.
3. Volba města — neutrální předvolební veřejné mínění a image fiktivních kandidátů.
4. Město 2035 — public policy acceptance / trade-offy.
5. Medora — patient experience a redesign služby.
6. Nexora — employee climate, leadership a týmová sociomapa.
7. RailMove — service concept + pricing.
8. EduNova — concept + UX research.
9. Streamio — brand positioning + content portfolio.
10. GreenHome — tariff proposition + trust research.

## Globální UI kontrakt
Každý projekt musí po otevření nabídnout tyto pohledy:
- **Co projekt přinesl** — default, executive answer, rozhodnutí, KPI, risks, next steps.
- Zadání — brief, AI interpretace, research questions.
- Research / design — evidence, nejistoty, metodika.
- Dotazník — otázky a tracked objects.
- Publikum — populace, dimenze, segmenty.
- Objekty & sociomapa — perception / emotion / segment resonance.
- Sběr & světy — respondent DB, 8 světů, frozen result.
- Výsledky — object KPI, segmenty, robustnost, interpretace.
- Report — plný text v UI + Word download.
- Historie — 7 immutable revizí.
- Ke stažení — všechny artefakty.

## Technická integrace
- `DEMO_REGISTRY.json` je jediný registry source.
- `install_all_demos.py` je adapter skeleton; přizpůsob názvy metod aktuálnímu ProjectStore/ArtifactStore.
- Každý seed má stabilní `project_id` a `demo_seed_key`; bootstrap musí být idempotentní.
- DEMO otevření je 100% lokální a nesmí volat AI, web ani placené API.
- Soubory se registrují přes běžný ArtifactStore, aby fungoval normální History/Downloads UI.
- Každý DEMO projekt je read-only; uživatel má akci **Vytvořit kopii jako nový projekt**.
- Kopie je běžný ostrý projekt a od té chvíle používá normální pipeline.
- DEMO se nezapočítává do learningu, dynamické populace, benchmarků, OOS validace ani produkčních statistik.

## Sociomapování
Sociomapa musí používat identická `object_id` jako questionnaire/results. Není dekorace. Klik na objekt zobrazí KPI, atributy, emoce, segmentový fit a nejbližší vztahy. U employee DEMO nepoužívat sociomapu k automatickému hodnocení jednotlivců.

## Politický DEMO
`Volba města DEMO` je záměrně fiktivní a deskriptivní. Zobrazovat stav veřejného mínění, témata, image kandidátů, turnout/uncertainty. Neimplementovat z něj cílené přesvědčování nebo mikro-targeting voličů.

## Artefakty v každém projektu
- `DEMO_PROJECT_SEED.json`
- `RESEARCH_DESIGN_DEMO.json`
- `QUESTIONNAIRE_DEMO.json`
- `AUDIENCE_DESIGN_DEMO.json`
- `RESPONDENT_DATABASE_DEMO.csv`
- `RESULTS_TABLES_*.xlsx`
- `CLIENT_REPORT_*.docx`
- `OBJECTS_SOCIOMAP_DEMO.json` + SVG + PNG
- 8× `worlds/WORLD_*.json`
- 8× `analysis/ANALYSIS_*.json`
- `PROJECT_HISTORY_DEMO.json`
- `ARTIFACT_MANIFEST.json`
- `PROJECT_EXPORT_*.zip`
- `SHA256SUMS.txt`

## Acceptance
1. Historie ukáže přesně 10 DEMO projektů.
2. Každý se otevře bez čekání na provider.
3. Každý má plné výsledky a exporty při prvním otevření.
4. Každý má 8 world detailů, sociomapu a segmenty.
5. Word / Excel / DB jsou skutečné stažitelné soubory.
6. Copy-to-new-project nevytváří změny v původním DEMO.
7. Smazání nebo opakovaný bootstrap nevytvoří náhodné duplicity; stable key je zachován.
