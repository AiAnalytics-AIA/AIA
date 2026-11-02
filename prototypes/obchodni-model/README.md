# AIA Obchodní model – prototyp, 2 Nov 2026 (version 11)

This is the business-decision study's Design canvas. It is the prototype of the pivot that ADR 0046 records
(`docs/architecture/adr/0046-business-decisions-pivot.md`, Proposed, in
[AiAnalytics-AIA/AIA#1150](https://github.com/AiAnalytics-AIA/AIA/pull/1150) until it merges). It shows:

- a fictional client case, Velis Commerce s.r.o.;
- the study from Zadání to Zpráva;
- the MVP it implies.

It is design reference only. Nothing here is imported by `apps/web`, calls an AIA endpoint, calls a model or uses a paid
service. Every client, study, person and number in it is fictional. How to read a `.dc.html` file is in
[`../README.md`](../README.md) § How to read a `.dc.html` file: the files are canvas artboards, and they do not render as
designed in a plain browser.

| | |
|---|---|
| Live canvas | <https://claude.ai/artifact/HM9rmiwAM9asP8hfyn1XHp>, in the product owner's first account, which owns it (2 Nov 2026). Edit this one and export from it |
| Version | version 11, artifact version `1793627006-a6de` |
| Exported | 2 Nov 2026 (versions 7 and 9 exported earlier the same day) |
| Core stylesheet | `assets/aia-core.css`, core v4.3 (Petrol), SHA-256 `bd0c156ee4ef23d2dcaef0f7f10fc1a82e675a9eb3e1c9d45a3ed198d54a2b0e`, the same bytes as `../research-stages/assets/aia-core.css` |
| Study stylesheet | `assets/aia-study.css`, the same bytes as `../research-stages/assets/aia-study.css` (`d1a2d23b…`) |
| Other assets | `assets/thinking-orbs.js`, the same bytes as research-stages' copy. Three uploaded images: the -5 strategy map's top, 3D and scenario views (`KM5Map`; `MV3SystemMap` reuses the top view) |

In the exported files, the canvas's asset URLs (`/_blob/<id>`) are rewritten to `assets/<id>.jpg`. `canvas.json` lists the
boards, their titles, sizes and positions, and their order.

## What it shows

Every study board carries the same nine-step navigator: Zadání (with its sub-steps), Data, Rešerše, Předpoklady, Model,
Výsledky, Sociomapa, Osnova zprávy and Zpráva. Each also carries a collapsible Lead pane (Ada; a CSS checkbox, `#leadx`)
and a ⋯ menu per stage. The canvas has three rows:

- **Zadání (Z0–Z7).** Free text and files come first. Ada then triages the brief into eight parts. Next come the shared
  core (the decision, the options, a rule with its threshold and risk bound) and the analyses the report will include
  (Z4, the framework picker). Then the model's parts and the hand-off.
- **The model study (M1–M6).** Data, assumptions, the model, and the results in six tabs: Rozhodnutí, Finance,
  Účetnictví, Provoz, Logistika and Trh. M5 is the earlier `aia-sociomap-5` strategy map, labelled internal. M6 is the
  report.
- **The MVP (MV0–MV7).** The scope, the data contract, typed inputs and findings by framework from Rešerše, Sociomapa
  systémů, the report outline (Osnova zprávy), Metodika's validation set and questions, the framework catalogue, and a
  UX audit of open items.

The customer-research lane (Výzkum zákazníků, with AI respondents) was removed at the product owner's request: it is
frozen (ADR 0046). The board numbering skips Z6.

**Changed since version 7.** Version 8 was a save from the page: the boards' layout only (MV6's height and two
title notes' widths). Version 9 renames the stage "Rentgen zprávy" (the report X-ray) to **Osnova zprávy**, the
report outline, on every board and in MV4's title, at the product owner's word (2 Nov: "i just called it an xray,
lets change the name for that"). MV4's file keeps its name, `MV4XRay.dc.html`, so every link still resolves.

**Changed in versions 10 and 11** (the product owner's stage-by-stage walkthrough, 2 Nov; ADR 0046 § The owner's
walkthrough, W1-W28, the full record in `.planning/evidence/pivot-walkthrough-2026-11-02.md`):

- **Zadání (v10):** six sub-steps; the badge "Výzkum", plus "Obchodní model" once the model is on; "Potřebuje
  výpočet?" in the decision core (Z3); triage asks every question that matters, the first three open, with
  no crown amount; Z7 hands to Data, Předpoklady, Model and Zpráva.
- **Data and Rešerše (v11):** no data class on screen ("Důvěrný"); source tiers named Úřední / Oborový /
  Ostatní; recall shown as the method's tested level; "Požádat Adu o Deep Research…" instead of a stage start.
- **Předpoklady and Model (v11):** distributions by source, a "Souvislosti" table Ada proposes, people as
  guarantors, a fixed contractual fee, the discount rate and tax as fixed parameters, wage growth, own
  operations rising with wages.
- **Výsledky, Osnova and Zpráva (v11):** the median with its interval leads; NPV after tax beside before tax;
  verdicts labelled as the researcher's judgement; the full grade legend; estimates reach the client labelled
  "metoda čeká na schválení metodikem" with an approval warning (MV0's M-5 too).
- **M5 (v11):** marked "Nahrazeno", off the study's path. What the maps draw is still open (W24).

The new numbers (after-tax NPVs, correlations, wage growth) are fictional, like every number here.

| # | File | Board |
|---|---|---|
| 1 | `Z0Flow.dc.html` | Z0 · Zadání: průchod |
| 2 | `Z1Start.dc.html` | Z1 · Zadání: začátek |
| 3 | `Z2Triage.dc.html` | Z2 · Zadání: triáž |
| 4 | `Z3Decision.dc.html` | Z3 · Zadání: rozhodnutí a pravidlo |
| 5 | `Z4Analyses.dc.html` | Z4 · Zadání: analýzy do zprávy |
| 6 | `Z5Model.dc.html` | Z5 · Zadání: obchodní model |
| 7 | `Z7Ready.dc.html` | Z7 · Zadání: připravenost a předání |
| 8 | `KM1Data.dc.html` | M1 · Model: Data |
| 9 | `KM2Assumptions.dc.html` | M2 · Model: Předpoklady |
| 10 | `KM3Model.dc.html` | M3 · Model: Model |
| 11 | `KM4Results.dc.html` | M4 · Model: Výsledky |
| 12 | `KM7Finance.dc.html` | M4b · Výsledky: Business case a finance |
| 13 | `KM8Accounting.dc.html` | M4c · Výsledky: Účetnictví |
| 14 | `KM9Operations.dc.html` | M4d · Výsledky: Operační výzkum |
| 15 | `KM11Logistics.dc.html` | M4f · Výsledky: Logistika |
| 16 | `KM10Market.dc.html` | M4e · Výsledky: Velikost trhu |
| 17 | `KM5Map.dc.html` | M5 · Dosavadní mapa (aia-sociomap-5) |
| 18 | `KM6Report.dc.html` | M6 · Model: Zpráva |
| 19 | `MV0Scope.dc.html` | MVP · Definované MVP: přehled |
| 20 | `MV1Contract.dc.html` | MV1 · Data: datová smlouva |
| 21 | `MV2PublicData.dc.html` | MV2 · Rešerše: typované vstupy |
| 22 | `MV2bFindings.dc.html` | MV2b · Rešerše: zjištění podle analýz |
| 23 | `MV3SystemMap.dc.html` | MV3 · Výsledky: Sociomapa systémů |
| 24 | `MV4XRay.dc.html` | MV4 · Osnova zprávy |
| 25 | `MV5Validation.dc.html` | MV5 · Metodika: validační sada a otázky |
| 26 | `MV6Catalogue.dc.html` | MV6 · Katalog analýz |
| 27 | `MV7UXAudit.dc.html` | MV7 · Kontrola UX |

## Reference renders

`reference/` holds every board as drawn by `tools/prototype_renders/render.js` with the Design type's runtime: 27 images
in WebP at quality 88, and `renders.json`. No board had a script error or a failed request. The images are numbered in
`canvas.json`'s board order (alphabetical since version 8), not in the order of the table above.

## Known wrong

- **One dead link.** The sidebar's "Klienti" item on the 22 study boards links to `Main.dc.html`, which is not a board of
  this canvas.
- **One upload not exported.** The canvas's asset store also holds `a0f09ea79c8a2fae650f909432204184`, a survey Sociomap
  from the removed customer-research lane. No board references it, so it is not in `assets/`.
- **Unregistered methods.** Numbers marked "odhad (interní)" and the strategy map rest on methods that are not in the
  Sociomap register. The boards say so.
