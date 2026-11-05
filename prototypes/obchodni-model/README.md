# AIA Obchodní model – prototyp, 5 Nov 2026 (version 33)

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
| Version | version 33, artifact version `1793897660-3f78` |
| Exported | 5 Nov 2026 (version 14 on 2 Nov; versions 15–22 left every board file as exported then) |
| Core stylesheet | `assets/aia-core.css`, core v4.3 (Petrol), SHA-256 `bd0c156ee4ef23d2dcaef0f7f10fc1a82e675a9eb3e1c9d45a3ed198d54a2b0e`, the same bytes as `../research-stages/assets/aia-core.css` |
| Study stylesheet | `assets/aia-study.css`, the same bytes as `../research-stages/assets/aia-study.css` (`d1a2d23b…`) |
| Other assets | `assets/thinking-orbs.js`, the same bytes as research-stages' copy. Ten uploaded images for SI3 and SI4, the aia-sociomap-5 engine's maps as AIA's report renderer draws them (`tools/engine_assets.json` names each). Three uploaded images: the -5 strategy map's top, 3D and scenario views (`KM5Map`; `MV3SystemMap` reuses the top view) |

In the exported files, the canvas's asset URLs (`/_blob/<id>`) are rewritten to `assets/<id>.jpg`. `canvas.json` lists the
boards, their titles, sizes and positions, and their order.

## What it shows

Every study board carries the same nine-step navigator: Zadání (with its sub-steps), Data, Rešerše, Předpoklady, Model,
Výsledky, Sociomapa, Osnova zprávy and Zpráva. Each also carries a collapsible Lead pane (Ada; a CSS checkbox, `#leadx`)
and a ⋯ menu per stage. The canvas has four rows:

- **Zadání (Z0–Z7).** Free text and files come first. Ada then triages the brief into eight parts. Next come the shared
  core (the decision, the options, a rule with its threshold and risk bound) and the analyses the report will include
  (Z4, the framework picker). Then the model's parts and the hand-off.
- **The model study (M1–M6).** Data, assumptions, the model, and the results in six tabs: Rozhodnutí, Finance,
  Účetnictví, Provoz, Logistika and Trh. M5 is the earlier `aia-sociomap-5` strategy map, labelled internal. M6 is the
  report.
- **The MVP (MV0–MV7).** The scope, the data contract, typed inputs and findings by framework from Rešerše, Sociomapa
  systémů, the report outline (Osnova zprávy), Metodika's validation set and questions, the framework catalogue, and a
  UX audit of open items.
- **Sociomapa z indikátorů (SI1–SI4).** The indicator method of the product owner's cloud-provider analysis
  (indicators scored 1–10 by rule, each with a source and a certainty; category means; a weighted total as height;
  z-scores; profile similarity (r + 1) × 5; futures over weights and certainty), applied to Velis's decision: the
  seven options (SI2, SI3) and six fulfilment suppliers (SI4).

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

- **No filler, labels that fit (v12; the owner: no "filler sections").** Removed the screens' text that only
  explains how AIA works: Z1's "Co se stane potom" and its footnotes, the rule banners on Z4, Z5, M2, MV1,
  MV2 and MV4, Z7's note on R1-R7, and the rule halves of MV1's, MV2's, MV2b's and MV4's footnotes. Kept what
  states facts about the case: legends, provenance lines, M8's reading, MV3's never-claim list, the report's
  grade legend. The "Obchodní model" and "Výzkum" tags wrap inside their pill instead of spilling out (Z1), and
  Ada's mark sits before each framework's name on Z4, so every row lines up.

- **v13:** the NPV median and interval labelled "odhad (interní)" on MV4 3.1, in M6's Finance paragraph and in M4b's header, apart from IRR and payback, which stay "výpočet" (W21; Codex's review of #1152).

- **v14:** a save from the canvas, layout only. M4b (Finance) is taller (1880 → 2248 px), so its last section is no longer cut off, and M4b, M4c and MV1 carry the heights the canvas measured. No text or number changed.

The new numbers (after-tax NPVs, correlations, wage growth) are fictional, like every number here.

**Changed in versions 23–33 (5 Nov): a new row, Sociomapa z indikátorů.** The product owner asked to reproduce the
cloud analysis's method in the business-model study, where the decision differs but the method stands, using
SWOT, PESTEL and Porter as inputs, and saw "a big benefit of using AI and deep research to custom tailor the
methodology to each individual study". Every report is tailored, so SI1 does not divide the method into fixed and tailored parts (an
earlier version did; the owner: "every report is customized … those buttons are useless"). It shows how this study's
method was built, from Zadání, Rešerše and Data to an approval locked before any score, and the six scoring
rules as applied here. It also shows how SWOT, PESTEL
and Porter findings become indicators instead of being counted. One rule is changed for this study: an
undocumented price rise counts as the others' median, not 0 %. SI2 is the 7 × 15 score matrix. SI3 is the map and
its futures: **B2 ranks first (8,35) and C2 overtakes it only once Ekonomika's weight reaches 0,507 (approved
0,22), computed exactly (totals are linear in that weight)**, the gap between the model's rule (C2) and a broader weighing. SI4 maps six suppliers: three from the
client's documents and three, starred, that Rešerše would find (fictional here). The boards' layout (v31, the owner: the ranges in the catalogue were confusing and the frameworks needed more
room): each indicator's scale is a strip of bands or situations showing the range, the score and the options that
fell in it, with one boundary rule (a value on a boundary takes the better score; `tools/look.json`, checked against
the specs). PESTEL, Porter's five forces and SWOT each have their own grid, every finding a card linked to the
indicator it feeds. The steps are a timeline, Ada's pane starts closed and the page uses the full width. SI3 and SI4's maps (v32, the owner: "use the real sociomap 5 engine renders in their full form") are AIA's
own: `tools/engine_maps.py` runs `compute_object_map` under `AIA_SOCIOMAP_V5` on two ratings tables per board (the
indicators as rows, the cloud method's profile; and the 2 000 futures as rows) and draws each map with
`signed_off_snapshots`, the report's renderer (top, 3D, and the futures as respondents), into JPEGs uploaded to the
canvas. It needs the repository's Python with numpy 2.5, scipy 1.18, numba 0.68, matplotlib and python-docx, and
`PYTHONPATH` at `packages/aia_core/src`; a rerun writes `assets/si-*.jpg`, which must be uploaded again and their ids
put in `tools/engine_assets.json`. The numbers come from
`tools/` (`specs.py`, `compute.py`, `build.py`, numpy only), which writes the four boards from MV3's frame in the
canvas's form (`/_blob/<id>`; the export rewrites those to `assets/<id>.jpg`); `check.py`
holds the printed rules to the results (a checklist scores 1 + 9 × share, unrounded; the order flips at the printed crossing). The
model's results they read (NPV, P(best), P(loss)) are the canvas's illustrative ones; P(loss > 10 mil.) per
option is new and equally fictional.

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
| 28 | `SI1Method.dc.html` | SI1 · Sociomapa z indikátorů: metoda |
| 29 | `SI2Matrix.dc.html` | SI2 · Sociomapa z indikátorů: matice skóre |
| 30 | `SI3OptionsMap.dc.html` | SI3 · Sociomapa z indikátorů: mapa možností |
| 31 | `SI4Suppliers.dc.html` | SI4 · Sociomapa z indikátorů: mapa dodavatelů |

## Reference renders

`reference/` holds every board as drawn by `tools/prototype_renders/render.js` with the Design type's runtime: 31 images
in WebP at quality 88, and `renders.json`. No board had a script error or a failed request. The images are numbered in
`canvas.json`'s board order (alphabetical since version 8), not in the order of the table above.

## Known wrong

- **One dead link.** The sidebar's "Klienti" item on the 22 study boards links to `Main.dc.html`, which is not a board of
  this canvas.
- **One upload not exported.** The canvas's asset store also holds `a0f09ea79c8a2fae650f909432204184`, a survey Sociomap
  from the removed customer-research lane. No board references it, so it is not in `assets/`.
- **Unregistered methods.** Numbers marked "odhad (interní)" and the strategy map rest on methods that are not in the
  Sociomap register. The boards say so.
- **The engine's statistics on futures.** On the futures maps the engine finds 10 of 21 (options) and 9 of 15
  (suppliers) pairs reliable, split-half 0,98 and 0,97. Futures are simulated, so that reliability grows with however
  many we run (2 000 here), not with people; the boards say so and keep the maps internal (ADR 0046's concern).
- **The profile maps are weak.** From 15 and 11 indicators the engine finds 1 of 21 and 0 of 15 reliable pairs; the
  options' profile map is weakly determined (split-half 0,56 under 0,59), and the renderer prints that over it.
- **SI4's starred suppliers and their sources are invented** for the demonstration; their values are labelled as
  public sources (veřejný ceník) that do not exist.
- **Z0's board list** does not yet name SI1–SI4.
