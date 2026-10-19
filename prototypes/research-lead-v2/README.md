# AIA Research Lead workbench · prototype V2

An isolated design-from-code prototype: one Study, one persistent Research Lead
conversation on the left (40 %), the current stage artifact on the right (60 %).
It is **not product code**. Nothing here calls an AIA endpoint, a model, a
provider or a paid service. All content is a fictional study ("Mladí zákazníci
2026" / "Young Customer Perception 2026" for Fio banka); none of it is a fact
about Fio banka.

## Run

```bash
cd prototypes/research-lead-v2
npm ci
npm run dev            # http://127.0.0.1:5174/   (?s=<A…M|X1…X7>&fast=1&auto=0)
npm run typecheck
node scripts/verify.mjs http://127.0.0.1:5174/ screenshots   # 112 browser checks + screenshots
npm run build          # dist/index.html, one self-contained file (fonts inlined)
npm run docs           # docs/*.md from src/model/inventory.ts
```

Chromium comes from `/opt/pw-browsers/chromium` (playwright-core, no download).

## Layout of the code

| Path | What |
|---|---|
| `src/model/fixture.ts` | The one fixture: study, element-model documents, results, map, sources, claims, findings, report, AI contracts, Deep Research envelope |
| `src/model/types.ts`, `doc.ts`, `status.ts` | State model, edit operations over the element model, derived stage status |
| `src/model/proposals.ts` | Specialist proposals as data (exact ops, coverage, implications, impact) |
| `src/model/terms.ts` | All interface copy (Czech), stage order and phases |
| `src/app/commands.ts` | Scoped application commands. UI controls and the Lead call the same functions; the human-only rules live here |
| `src/app/scenarios.ts`, `lead.ts`, `seed.ts` | Scenario scripts A–M and exceptions, the Lead's request router, seeded study states |
| `src/components/` | Study header, stage navigator + lifecycle, split + focus modes, conversation, composer, activity and decision cards, inspector, entry view, demo controls |
| `src/artifacts/` | The eleven purpose-built stage artifacts |
| `scripts/verify.mjs` | Browser verification (real Chromium) |
| `docs/` | Information hierarchy, capability, interaction and donor inventories, boundary matrix, decision log and production gaps |
| `screenshots/` | Views at 1600 px, overviews at 1280 / 1440 / 1920, `results.json` from the last verification run |

Design tokens and fonts are imported from `apps/web` (`src/app/tokens.css`,
`public/skin/fonts`), not copied.

## Scenarios

Open the dashed **PROTOTYP · scénář** control at the bottom right (deliberately
unlike product UI). Labels are the same as in `docs/information-hierarchy.md`.

A open study · B questionnaire · C audience research · D manual editing ·
E stale proposal · F fieldwork · G results · H Sociomap · I map-context research ·
J analysis · K report · L continue until you need me · M return after days ·
X1 budget limit · X2 missing evidence · X3 provider failure · X4 failed analysis
validation · X5 reopened work · X6 methodology restriction · X7 unavailable capability.

## Boundaries kept

No production endpoint, architecture, method default, approval, AWS setting or
route was changed. No live model or paid call. No Open WebUI code was copied
(patterns re-implemented; licence verified at `aa8ce52`, see `docs/donor-inventory.md`).
The four supplied exports were not available to this session and were not inspected.
