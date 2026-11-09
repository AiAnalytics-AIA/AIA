# AIA Obchodní model – prototyp, 8 Nov 2026 (version 66)

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
| Version | version 66, artifact version `1794159099-d2fb` (versions 53–64 came from the Design type's own releases; the four boards this export did not change were identical on the canvas) |
| Exported | 8 Nov 2026 (version 14 on 2 Nov; versions 15–22 and 34–36 changed no board file; version 51 on 6 Nov) |
| Core stylesheet | `assets/aia-core.css`, core v4.3 (Petrol), SHA-256 `bd0c156ee4ef23d2dcaef0f7f10fc1a82e675a9eb3e1c9d45a3ed198d54a2b0e`, the same bytes as `../research-stages/assets/aia-core.css` |
| Study stylesheet | `assets/aia-study.css`, the same bytes as `../research-stages/assets/aia-study.css` (`d1a2d23b…`) |
| Other assets | `assets/thinking-orbs.js`, the same bytes as research-stages' copy. Six uploaded images for SI3 and SI4, the aia-sociomap-5 engine's maps of the tested settings as AIA's report renderer draws them (`tools/engine_assets.json` names each). Eleven uploaded images: the Velis scenario map's top view (`MV3SystemMap`), the exemplar's four futures-map figures (`MV3SystemMap`), and six renders of the weighting-scenario map by the aia-sociomap-5 engine (`MV9ScenarioWeights`; `tools/engine_assets.json` names each) |

In the exported files, the canvas's asset URLs (`/_blob/<id>`) are rewritten to `assets/<id>.jpg`. `canvas.json` lists the
boards, their titles, sizes and positions, and their order.

## What it shows

Every study board carries the same nine-step navigator: Zadání (with its sub-steps), Data, Rešerše, Předpoklady, Model,
Výsledky, Sociomapa, Osnova zprávy and Zpráva. Each also carries a collapsible Lead pane (Ada; a CSS checkbox, `#leadx`)
and a ⋯ menu per stage. Since version 51 the canvas has one row per phase of the navigator, in the order a study walks
through them, and each board's arrows at the bottom follow that order (Z1 → … → M6 Zpráva):

| Row | Boards |
|---|---|
| Zadání | Z0 průchod · Z1 · Z2 · Z3 · Z4 · Z5 · Z7 |
| Vstupy | M1 Data · MV1 datová smlouva · MV2 typované vstupy · MV2b zjištění podle analýz · M2 Předpoklady |
| Výpočet | M3 Model · M4 Rozhodnutí · M4b Finance · M4d Provoz · M4g Harmonogram · M4f Logistika · M4c Účetnictví (parked) · M4e Trh (parked) |
| Sociomapa | MV3 Sociomapa systémů · MV9 Mapa scénářů vah · SI1–SI4 the indicator method, reduced to what MV9 reads |
| Předání | MV4 Osnova zprávy · MV8 kontrola platnosti modelu · M6 Zpráva |
| MVP a Metodika | MV0 scope · MV5 validation and register · MV6 catalogue (parked) |

The board codes keep the row they were first drawn in (Z, M, MV, SI), so every link and file name still resolves.

- **Zadání (Z0–Z7).** Free text and files come first. Ada then triages the brief into eight parts. Next come the shared
  core (the decision, the options, a rule with its threshold and risk bound) and the analyses the report will include
  (Z4, the framework picker). Then the model's parts and the hand-off.
- **The model study (M1–M6).** Data, assumptions, the model, and the results in six tabs: Rozhodnutí, Finance,
  Účetnictví, Provoz, Logistika and Trh. M6 is the report.
- **The MVP (MV0–MV8).** The scope, the data contract, typed inputs and findings by framework from Rešerše, Sociomapa
  systémů, the report outline (Osnova zprávy), Metodika's validation set and questions, the framework catalogue, and
  the model-validity review that the recommendation waits for (MV8).
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

**Changed in versions 23–33 (5 Nov): a new row, Sociomapa z indikátorů** (its method and numbers were replaced in version 37, below). The product owner asked to reproduce the
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

**Changed in version 37 (5 Nov): method v2, after an external methodology review.** The product owner's review of the
methodology write-up named ten changes and seven inconsistencies ("we have just defined changes and upgrades to make very
specifically"). The boards now carry them:

- **Validity apart from reproducibility (MV8, new; Z7 R8 and R9).** Before the recommendation can be approved, an
  independent reviewer answers five questions (options comparable, material costs and dependencies in, exclusions that
  could reverse it, extreme inputs, the structure and decisive assumptions challenged), with four extreme-input tests and
  the six acceptance criteria. Hashes verify the implementation, not fitness for the decision.
- **Missing data (SI1–SI4).** v1's rules 3–6 gave a missing fact a score (median, "not offered", "nothing reported = 8").
  A cell is now known, unknown (it keeps the range of scores it could take), not applicable, or a checklist of items met,
  evidenced absent or unknown; the matrix shows each object's coverage of the weights. Non-compensable requirements are
  gates (pass, fail, unknown): an unknown gate means "cannot be recommended until evidenced". The base point of every test
  is the documented minimum; a decision-critical unknown (one whose top value alone would change who is first) becomes an
  evidence request with alternative cases.
- **No double counting, swing weights (SI1–SI4).** Indicators whose mechanism the model's NPV already holds are dropped
  (v1 counted B2's fixed price three times); the managers' ratings are a cross-check, not a criterion. Weights come from
  swing weighting by the decision owner, approved with the value scales before any score; the other stakeholders' weights
  are a sensitivity test. SI1 states when the map may influence the recommendation.
- **Sensitivity, not probability (SI3, SI4).** Five families of tested settings (weights, evidence, missing data,
  structure, all at once), each reported as the share of settings in which an option is first. The engine maps the tested
  settings; its pair statistics are not read, because we choose the number of rows.
- **The model's own numbers.** v1's SI read other medians and loss probabilities than Výsledky printed (3,9 vs 2,6 for A;
  12 % vs 4 %). E1 and R1 now read KM4, and `tools/check.py` parses KM4 to hold them to it. Result: on the documented
  minimum C2 leads (7,70), as the client's rule does; B2 (7,30–8,06) leads if the Czech 3PL documents capacity of at least
  1,0 of the 2032 need. C2 stays ahead until Ekonomika's weight falls below 0,224 (approved 0,377).
- **A statistical contract per Sociomapa mode (MV3).** What a row is, what the claim is about, the relationship, the null,
  the resampling scheme and what the stability measures, for scenarios, experts, units and periods. No block bootstrap
  over Monte Carlo draws; centred (relative) and raw (shared downside) relations side by side.
- **Uncertainty, causality, value of information (KM1–KM4).** Each decisive input has an uncertainty type, the meaning of
  its endpoints and a justification; expert mixtures; stress tests outside the distributions; alternative model structures;
  futures run until the rule's verdict is stable (±0,5 pp). The delay → order-loss link records its causal assumption,
  alternatives and identification; the shipping-price elasticity is a labelled assumption with scenarios; the backtest has
  horizons, rolling origins and interval coverage. The value of information answers the client's rule (how often perfect
  information changes the choice), apart from a practical enquiry with its cost, duration and effect on the deadline;
  EVPPI stays as a labelled proxy. B2 is assessed as a switch (feasibility, timing, cost, shared risks), not called a hedge.
- **Release and report (MV0, MV4, MV5, KM6).** A recommendation that rests on an unvalidated method stays "Předběžné
  doporučení"; approval records the version and the unresolved qualifications (proposed, waiting for the product owner's
  decision, since it changes his RD0 of 22 Oct). The report follows the argument (the decision; why the option is
  acceptable; what could change it; implementation; supporting evidence), and the outline records why each point matters,
  with typed judgement and inference records. Grades split into source, method, uncertainty and validation status.
- **Tools.** `tools/specs.py` (the two specs, the experts' table read as it is), `compute.py` (states, gates, ranges,
  coverage, the five families, decision-critical unknowns, the n/a test), `engine_maps.py` (the settings maps only),
  `build.py` (SI1–SI4 from MV3's frame as merged in b28ce0919, read from git) and `check.py` (checklists unrounded, unknown
  cells without a score, E1 and R1 equal to KM4, a failed gate first nowhere, the crossing exact, scales match the specs).
- **Inconsistencies.** Data and its contracts stay in every study type (Z0, Z3); the rule is frozen before comparative
  results, with intake reading recorded as feasibility work (Z3); income tax is inside the model, so Z5 agrees with KM7;
  illustrative numbers are labelled apart from validation evidence (MV5).

**Changed in version 38 (5 Nov).** KM4, MV4 and KM6 agree on B2 and the pilot: B2 can be signed only until the Czech
3PL is given notice (31. 12. 2026), and going back later costs 4–9 mil. Kč (KM6 had said 31. 1. 2027 and "nic nestojí",
with an option to 31. 5. 2027); the C2 pilot is three months in Olomoucký kraj, 0,4 mil. Kč, result in 6/2027 (KM4 had
six weeks). The remaining "záloha" wording on MV4 and KM6 now says "přechod". Found while writing the methodology's
version 2 (acceptance criterion K6).

**Changed in version 51 (6 Nov): one study, no old versions.** At the product owner's word ("we need to consolidate the
mvp prototype screens. get rid of any old versions. lets leave the latest working idea up"):

- **Removed.** M5 (`KM5Map`, the earlier `aia-sociomap-5` strategy map, marked "Nahrazeno" since version 11; MV3 and
  SI1–SI4 replace it) and MV7 (`MV7UXAudit`, the UX audit of 2 Nov, whose findings the boards already carry), with M5's
  two images that no other board uses. Git history keeps them.
- **One path.** The rows follow the navigator (table above), and the arrows run Z1 → … → M6: MV3 now leads to SI1, Osnova
  zprávy to MV8, MV8 to Zpráva. Z0's board list is in the same order and names every board (MV2b and M4f were missing);
  MV0 no longer points at M5 or MV7.

**Changed in versions 65–66 (8 Nov): the MVP that produces report 2.** The executive chose study type 2 of the ChemVitro case
(`exemplar/ChemVitro_2_model-lokality_nigel.pdf`, 44 pages) as the report AIA must produce. The owner: "focus the MVP to
be able to create the reports like report 2 … all business perspectives: financial, strategic, operational, marketing,
logistics … one MVP prototype, one methodology PDF, and one MVP scope." Six sessions built it from `BRIEF-mvp-r2.md`:

- **Scope** (`MVP-SCOPE.md`, MV0, Z0): type 2 is the MVP's spine, replacing "Keep all in MVP" (A1 of 2 Nov); eight steps,
  each with what the exemplar needs, what AIA has today (`file:line @ b28ce091`), what is new and the plan chunk; seven
  perspectives with ChemVitro's 22 components; the weighting-scenario map's contract; acceptance = the ChemVitro answer
  key plus K1–K6; five two-week waves.
- **Inputs** (Z3, Z5, M1, MV1, MV2, M2): a rule of four gated conditions with an interpretation record; the data-check
  findings table with dispositions and the planted problems located by row; a contract per file; 16 provisional public
  inputs with a state (ověřeno u pramene / prozatímní / úsudek); the T9 inputs table, estimates from the 36 comparable
  plants, the EPC scope check, correlations as judgement with the stability test declared first.
- **Model and results** (M3, M4, M4b, M4d, M4f, new **M4g Harmonogram**): shared timeline and stopping rule; the rule
  table at three rates with ✔/✘, the decision boundary (14 / 15 / 16 %), delay and hiring tables, value of information
  for the rule before EVPPI, the enquiry table; T4–T6; start-date distributions against the deadline. Every ChemVitro
  number is held to the exemplar's text by `tools/results_build.py`. M4c and M4e carry one parked line.
- **Maps** (MV3, new **MV9 Mapa scénářů vah**, SI1–SI4): the futures map as the exemplar draws it (T7, T8, "no site is a
  backup of another", the three-setting stability test the map failed); the weighting-scenario map on the real engine:
  20 scored components by perspective with their role (úspora / v modelu / mimo model), gates never compensated, six named
  weight vectors in two families with a Dirichlet fan (concentration 60 × 300 draws, 1 806 tested weightings as rows),
  the owner's "finance 0,5 · provoz 0,3 · logistika 0,2" shown refused by the overlap check, first-per-scenario and
  shares of tested settings, decision-critical ranges. SI1–SI4 keep only the method MV9 reads.
- **Report** (MV4, M6, MV8, MV5): the outline in the exemplar's 18 parts with typed judgement and inference records; the
  report as AIA renders it with grades after numbers, numbered sources per chapter, the Stav podkladů box and the dated
  plan; the validity review run on the exemplar's own ten admitted limits (3 caught today, 7 open); the register entries
  the exemplar waits on. One claim-integrity case found on the way: the exemplar's text says 54 inputs, its table T9 has 67.
- **Methodology** version 4 (`methodology/`, 43 pages, 9 Nov): the analytical contract (seven defaults, two release states,
  R9 adopted), the perspectives as a disjoint cost partition with one weight vector for all sites, convergence by doubling
  under repeated-look bounds, grades with lineage and validation apart, oracle-first acceptance (O-CF, O-INFO, O-CHEM); v3
  (37 pages, 8 Nov) kept beside it.
- **MVP scope, executive edition** (`scope/`, `AIA_MVP-scope_cs.pdf`, 10 pages, 9 Nov, "pro vedení"): the scope as the
  executive reads it, in Czech, one idea and one figure per page, no plan or board codes: what the client gets, the
  eight steps and who does what, today / new, the weighting-scenario map answered in the owner's own question, the
  three gates before a client sees a report, the ten-week plan with the honest expectation, the technology stack, the
  two open decisions and the methodologist's three asks, a glossary. `MVP-SCOPE.md` version 2 stays the team's record
  (chunk ids, code anchors, the review-id mapping in § 2.9, acceptance, waves); built by `scope/build.js`.

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
| 9 | `MV1Contract.dc.html` | MV1 · Data: datová smlouva |
| 10 | `MV2PublicData.dc.html` | MV2 · Rešerše: typované vstupy |
| 11 | `MV2bFindings.dc.html` | MV2b · Rešerše: zjištění podle analýz |
| 12 | `KM2Assumptions.dc.html` | M2 · Model: Předpoklady |
| 13 | `KM3Model.dc.html` | M3 · Model: Model |
| 14 | `KM4Results.dc.html` | M4 · Model: Výsledky |
| 15 | `KM7Finance.dc.html` | M4b · Výsledky: Business case a finance |
| 16 | `KM9Operations.dc.html` | M4d · Výsledky: Operační výzkum |
| 17 | `KM12Schedule.dc.html` | M4g · Výsledky: Harmonogram |
| 18 | `KM11Logistics.dc.html` | M4f · Výsledky: Logistika |
| 19 | `KM8Accounting.dc.html` | M4c · Výsledky: Účetnictví |
| 20 | `KM10Market.dc.html` | M4e · Výsledky: Velikost trhu |
| 21 | `MV3SystemMap.dc.html` | MV3 · Výsledky: Sociomapa systémů |
| 22 | `MV9ScenarioWeights.dc.html` | MV9 · Sociomapa: mapa scénářů vah |
| 23 | `SI1Method.dc.html` | SI1 · Sociomapa z indikátorů: metoda |
| 24 | `SI2Matrix.dc.html` | SI2 · Sociomapa z indikátorů: matice skóre |
| 25 | `SI3OptionsMap.dc.html` | SI3 · Sociomapa z indikátorů: mapa možností |
| 26 | `SI4Suppliers.dc.html` | SI4 · Sociomapa z indikátorů: mapa dodavatelů |
| 27 | `MV4XRay.dc.html` | MV4 · Osnova zprávy |
| 28 | `MV8Validity.dc.html` | MV8 · Zpráva: kontrola platnosti modelu |
| 29 | `KM6Report.dc.html` | M6 · Model: Zpráva |
| 30 | `MV0Scope.dc.html` | MVP · Definované MVP: přehled |
| 31 | `MV5Validation.dc.html` | MV5 · Metodika: validační sada a otázky |
| 32 | `MV6Catalogue.dc.html` | MV6 · Katalog analýz |

## Reference renders

`reference/` holds every board as drawn by `tools/prototype_renders/render.js` with the Design type's runtime: 32 images
in WebP at quality 88, and `renders.json`. No board had a script error or a failed request. The images are numbered in
`canvas.json`'s board order, not in the order of the table above.

## Known wrong

- **One dead link.** The sidebar's "Klienti" item on the 22 study boards links to `Main.dc.html`, which is not a board of
  this canvas.
- **One upload not exported.** The canvas's asset store also holds `a0f09ea79c8a2fae650f909432204184`, a survey Sociomap
  from the removed customer-research lane. No board references it, so it is not in `assets/`.
- **Unregistered methods.** Numbers marked "odhad (interní)" and the strategy map rest on methods that are not in the
  Sociomap register. The boards say so.
- **The engine's statistics on tested weightings are not read.** MV9's rows are weight vectors we chose, so the board
  prints no pair statistic and keeps the map internal (MV3's contract for the scenario mode).
- **The exemplar's futures-map figures on MV3 are images cut from the report**, not renders from this repository; the
  weighting map's images are the engine's own renders.
- **The release policy is a proposal.** MV0, MV5 and KM6 show "Předběžné doporučení" as proposed; it changes the product
  owner's RD0 decision of 22 Oct and waits for his word.
- **Number chips on most boards keep the single grade.** MV4 and KM6 split a number's grade into source, method,
  uncertainty and validation status; the other boards' chips still show one grade.
- **The swing points, the named weight scenarios and the managers' alternative weights are invented**, like every number
  here; MV8's reviewer is fictional and its extreme-input rows are the exemplar's own additional computations.
- **SI4's starred suppliers and their sources are invented** for the demonstration; their values are labelled as
  public sources (veřejný ceník) that do not exist.
