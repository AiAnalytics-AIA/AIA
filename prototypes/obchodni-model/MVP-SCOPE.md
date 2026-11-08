# MVP scope: the report-2 pipeline on today's AIA

8 Nov 2026. Session A of `BRIEF-mvp-r2.md`. The spine is study type 2 of the ChemVitro case
(`prototypes/case-chemvitro/STUDIES.md`), end to end, producing a report with the content and quality of
`exemplar/ChemVitro_2_model-lokality_nigel.pdf` (parts R2-P01 to R2-P18, tables T1 to T9). Code anchors are
`file:line @ b28ce091` (`origin/develop`, the base of this branch; `apps/` and `packages/` are identical there).
Paths under `packages/aia_core/src/aia_core/` are written from `domain/`, `application/` or `infrastructure/`.
Plan ids are `plan#CHUNK`; a chunk marked **new** exists in no plan file yet and is defined here in one line. `cost-model-study`, `client-data-in-analysis`, `quantitative-families`, `situation-reports`, `report-delivery` and `lead-orchestration` are on `develop`; `decision-brief`, `deep-research-v2`, `public-data-routes`, `legal-context`, `sociomapa-systemu`, `research-findings-stage`, `analysis-frameworks`, `diagrams` and `register-personal-data` are read from `origin/chore/pivot-business-decisions` @ d8dc8ec5 (ADR 0046, Proposed, unmerged).
Board codes are the canvas's (`README.md`); the brief's session table says who builds which.

## 1. The decision

**Type 2 is the spine.** The MVP is one study, the nine-step navigator the canvas already has, walked end to end on
the ChemVitro files until AIA renders a report with the exemplar's content: the rule as written at three rates, the
decision boundary, the value of information for the rule, the futures map, and every number with a grade and a source.
Everything else is parked (§5), planned and not deleted.

**What it replaces.** A1 of 2 Nov ("Keep all in MVP": no spine, every core plan in the MVP; ADR 0046 § The owner's
answers) is superseded by the owner's words of 8 Nov in the brief. The methodology review's order of 5 Nov still holds
(R1–R10): contracts and release conditions before the catalogue of analyses grows, then the whole process on a computed
case with known behaviour. ChemVitro is that case; its answer key is the test (§6).

**What stays as decided.** One merged study (A2); models propose, code computes, a person approves; the client's rule
decides and the maps inform; a Monte Carlo number is *odhad* and internal until the methodologist registers the
method (W21, W27, Q10); the report is Czech (W28); develop runs advisory class gates on fictional data (A4).

**The pipeline in eight steps.** Zadání · Data · Rešerše · Předpoklady · Model · Výsledky · Sociomapa · Osnova a
Zpráva. The navigator keeps nine; the last two are one step here, built once (the outline) and printed once (the report).

## 2. The pipeline in eight steps

### 2.1 Zadání (boards Z1–Z5, Z7)

- **Needs.** The decision, eight options plus the buy baseline, four constraints, the CFO's rule written on 2. 11. 2026
  before any result, with four conditions (median saving; P(beats buying) ≥ 0,75; P(loss > 20) ≤ 0,10; P(start by
  1. 7. 2030) ≥ 0,80; investment ≤ 175) and one interpretation record (investment judged on the base case, confirmed
  by the CFO) (R2-P02 §1.3). The hand-off names the files each step takes (R2-P18 A).
- **Today.** A research study's Brief on the working copy with revision-checked saves
  (`infrastructure/study_workspace_repository.py:241`, a stale save refused; `:194` one revision read back), the edit
  vocabulary (`domain/edit_ops.py:496` `apply_edit`; `application/working_copy.py:57` `apply_edit_ops`), immutable
  Design Revisions (`infrastructure/study_design_repository.py:153` `submit`, `design_not_from_workspace`), the Lead's
  turn and closed output (`domain/research_lead.py:450` `LeadOutput`, `:1491` `lead_request`;
  `application/research_lead.py:807` `post`, `:1122` `decide_edits`). Study kinds are RESEARCH and SIMULATION only
  (`domain/scope.py:457`; `infrastructure/tables.py:645` `study_kind_known`).
- **New.** The business Zadání as data; a rule with several conditions, each with its own threshold and, where
  stated, a probability, judged per option at the stated rate and two alternates; the interpretation record a named
  person confirms; the model switch.
- **Builds it.** `decision-brief#DB0` (the eight parts as data), `#DB2` (triage as a Lead turn), `#DB3` (the decision
  core and the rule), `#DB4` (readiness R1–R7), `#DB5` (the hand-off); **new** `decision-brief#DB3b`: a rule of n
  conditions with per-condition thresholds and rates, and the interpretation record (extends `cost-model-study#CR7`,
  which judges one quantity against one threshold).

### 2.2 Data (boards M1, MV1)

- **Needs.** Every file and document used, with a contract per file (which columns, how); 42 data-check findings
  (units kg vs t, currencies CZK/PLN/USD, price years, a duplicate plant, a spot purchase, a capacity in t/day), each with
  its disposition; the findings that change the result in P1 (R2-P04 §3.4, R2-P18 B, C); a number read from a
  document with its page, cited as *z dat klienta* (every chapter's ZDROJE A STUPNĚ).
- **Today.** Client sources kept once per SHA-256 and read into segments with locators: PDF by page and table row,
  DOCX by paragraph, XLSX and CSV by sheet and row (`infrastructure/source_reading.py:656` `read_source`;
  `domain/client_sources.py:176` `Locator`, `:225` `SourceReading`); a dataset's preview per column with personal
  columns masked (`domain/client_datasets.py:208` `DatasetPreview`, `:54` `PERSONAL_SHARE`); a quote grounded
  literally in its segment (`domain/source_proposals.py:332` `ground`); the Brief's materials naming a dataset by
  source, reading and intended contract, eligible only under an accepted contract that nothing stores yet
  (`domain/brief_materials.py:61` `BriefMaterial`, `:111` `eligibility_of`, version `aia-brief-materials-0-proposed`
  at `:55`). No contract table, no analysis copy, no computation on a client row.
- **New.** The contract accepted on Data with its quality report; the analysis copy of named columns; unit, currency
  and price-year normalisation as declared conversions, each a finding with its disposition; a number from a
  document proposed with its page and checked literally on that page; the findings table P1 with dispositions.
- **Builds it.** `client-data-in-analysis#2` (the contract and its accept route), `#2a` (the quality report), `#3`,
  `#3a`, `#3b` (the analysis copy and its accessor), `#5` (admission, *z dat klienta*), `#10` (accepted on the Data
  step, W6), `#11` (a number from a document with its page, W7), `#12` (an estimate from client rows as a Metodika
  method, W8); `cost-model-study#CR1` (reconciliation, coverage, currency, outliers, accepted on record); **new**
  `client-data-in-analysis#13`: declared conversions (unit, currency at a dated rate, price year) and the P1 table of
  findings with dispositions (použito / opraveno / vynecháno / převzato jako předpoklad).

### 2.3 Rešerše (boards MV2, MV2b)

- **Needs.** Sixteen of 54 inputs are public: the ETS price and its drift, free allocation, energy drift and
  volatility, exchange rates, employer contributions, tax rates, depreciation, the form of incentives, directive
  (EU) 2024/2881; each *veřejný zdroj* or *právní předpis*, *prozatímní* until verified at the source, named on
  page 1 (Stav podkladů) and in T9's Stav column; a literature chapter with cited works (R2-P03, R2-P16).
- **Today.** Deep Research's six steps with two purposes (`domain/deep_research/integration.py:146`
  `DeepResearchPurpose`), every quote located in a captured snapshot (`domain/deep_research/grounding.py:116`
  `locate_quote`), the sealed bundle (`domain/deep_research/bundle.py:112` `EvidenceBundle`), every query and fetch
  through one gate (`application/web_retrieval.py:534` `RetrievalGate`), a run frozen at enqueue with its settings
  pin (`application/deep_research.py:617` `freeze_design`, `:781` `start`, `:1051` `quote`;
  `domain/deep_research/settings.py:765` `pin`), a captured source added to knowledge by a person's click
  (`application/verified_sources.py:47` `add_verified_source`). A finding is a quote; no typed number comes out of it.
- **New.** Typed inputs (value, unit, period, range, source, as-of date) extracted by code from accepted quotes and
  from structured routes, with a state *prozatímní / ověřeno u pramene*; credibility tiers Úřední / Oborový /
  Ostatní; a legal point as a verbatim provision that becomes a parameter (tax rate, depreciation, contributions).
- **Builds it.** `deep-research-v2#DRV1` (the typed input), `#DRV2` (the extractor), `#DRV3` (the extraction step),
  `#DRV5` (credibility tiers); `public-data-routes#PDR1` (SDMX: Eurostat, ECB), `#PDR2` (ČNB rates);
  `legal-context#LGL1`, `#LGL2`, `#LGL3` (e-Sbírka and EUR-Lex routes, the legal point, legal parameters).

### 2.4 Předpoklady (board M2)

- **Needs.** 54 inputs in one table T9: low / likely / high, distribution (PERT, fixed, yes/no, uniform), source,
  grade, who stands behind it, state; estimates from client data where possible (EPC overrun 17 % median from 36
  plants; overrun and delay drawn together from one plant per future, Spearman 0,89); the EPC estimate's scope
  checked against each site's documents and the exclusions priced (land, bridge, spur, pre-treatment, compensation,
  park fee); correlations declared as judgement with a stability test fixed before computing (R2-P05, T5, T9).
- **Today.** Nothing holds an input with a range and a guarantor. The pieces exist: a design's assumptions on the
  working copy, the Lead's per-change proposals, client numbers with locators (2.2).
- **New.** The input type with provenance and range; a guarantor on each; PERT, fixed and stated distributions;
  declared rank correlations; empirical joint draws from a client table; the scope check of an estimate against each
  option's documents; the stability test declared before computing.
- **Builds it.** `cost-model-study#CP1` (the input with its provenance), `#CR2` (low / base / high and a guarantor),
  `#CR3` (PERT, Iman-Conover correlations, a non-PSD matrix refused; people who disagree sampled as a mixture, W14, R6),
  W13–W16 as written there; **new**
  `cost-model-study#CR3b`: empirical joint draws, one row of a client table per future carrying several inputs
  together (overrun and delay), the table pinned by SHA-256; **new** `cost-model-study#CR1b`: the scope check, what
  an estimate's document excludes against what each option's documents require, each exclusion an input with its
  range; the stability test's declaration is `sociomapa-systemu#SYS9b` (2.7).

### 2.5 Model (board M3)

- **Needs.** One cost-of-supply model for eight sites and the buy baseline on a shared timeline (decision 1. 2.
  2027 → permits 8–11 months, longer with compensation → construction 22 months plus a comparable plant's delay →
  ramp-up 60–90 %; spot purchases while late; demand above 40 000 t bought at spot; residual value 30 % in 2044;
  taxes inside the model), base case plus 20 000 futures, seed 20270201, same bytes on rerun (R2-P04 §3.3, R2-P18 B).
- **Today.** The workflow engine runs typed templates (`domain/workflow_templates.py:66` names `research` only), a
  run's cost ceiling (`domain/run_cost.py:99` `run_cost_ceiling`), results as artifacts with fingerprints
  (`application/research.py:691` `start`). No model type, no compute step, no `Decimal` quantities.
- **New.** The model platform and a model type of its own: `site_cost_of_supply`, a timeline per option whose dates
  are inputs, yearly cash flows, NPV before and after tax at a stated rate, the futures run until the rule's verdict
  is stable (R6: precise enough to tell passing from failing, ±0,5 pp), every result an artifact.
- **Builds it.** `cost-model-study#CP2` (the model-type contract and the determinism harness), `#CP3` (the kind and
  the working copy), `#CP5` (the run), `#CP6` (the API), `#CM7` (NPV and discounted payback), `#CR3` (the futures),
  `#CP10` (the ESTIMATED grade, seed and method pinned, the Metodika module of defaults); `quantitative-families#FIN1`
  (the cash-flow schedule), `#FIN2` (IRR by a stated root rule); **new** `cost-model-study#CM8`: the
  `site_cost_of_supply` type (timeline, purchases, operations, residual value, tax as a fixed parameter, T4–T6 as its
  results) and the convergence rule tied to the decision.

### 2.6 Výsledky (boards M4, M4b, M4d, new M4g)

- **Needs.** *Rozhodnutí* (R2-P06–P09): T1–T3, the rule at 8, 6 and 10 %; the verdict as a boundary (compensation
  chance 14 / 15 / 16 %); delay tables (0/2/4/6 months, with and without compensation); hiring delay as a stress
  test; tornado; break-even prices; post-2035 terms; correlation settings leave the verdict unchanged; value of
  information for the rule first, EVPPI second, neither a budget; the enquiry table (output, duration, cost).
  *Finance* (R2-P10, T4): NPV pre- and post-tax at three rates, IRR, payback, incentives as tax reliefs vs grants.
  *Provoz* (R2-P11, T6): cost per tonne by category in 2032. *Harmonogram*: start-date distribution per site against
  the deadline, P(včas), every month of delay (R2-P07).
- **Today.** Every printed number is an admitted claim (`domain/evidence/admission.py:298` `admit_numeric_claims`,
  `:188` `AdmittedClaim`), support is respondent-shaped (`domain/evidence/support.py:235` `assess_support`;
  `domain/evidence/metrics.py:32` `MetricKind`), seven chart kinds with the median-and-interval chart the exemplar
  uses (`domain/report/model.py:264` `ChartKind`: BAR … DOT_INTERVAL, HEATMAP; renderers
  `infrastructure/report_docx/charts.py:364–370`), the per-question tables export (`application/report_tables.py:176`).
  No rule verdict, no tornado, no stacked absolute bar, no value of information.
- **New.** The rule's verdict table at three rates; the decision boundary over one input's range; delay and hiring
  tables; one-change-at-a-time recomputations as stored results; value of information for the rule; the enquiry
  table; the start-date distribution; a Harmonogram board.
- **Builds it.** `cost-model-study#CR7` (the rule judged as written), `#CM2` (break-even, one-way sensitivity),
  `#CR4` (global sensitivity beside the tornado), `#CR6` (EVPPI), `#CR8` (the method on screen), `#CP8` (three chart
  kinds: absolute stacked bar, tornado, line with marked points); `quantitative-families#FIN3` (scenarios on NPV and
  IRR); `legal-context#LGL3` (tax relief vs grant as legal parameters); **new** `cost-model-study#CR7b`: the rule at
  three rates, the decision boundary, delay and hiring tables, post-2035 and correlation recomputations, each one
  change at a time and said so; **new** `cost-model-study#CR6b`: value of information for the rule (R7: the rule
  re-applied per answer branch, the average of what it then picks against today's "nic") and the enquiry table with
  its effect on the deadline (K5); **new** `cost-model-study#CM9`: Harmonogram, the start-date distribution per option
  against the deadline, P(včas) and the months-of-delay table, board M4g.

### 2.7 Sociomapa (boards MV3, SI1–SI4 reduced, new MV9)

- **Needs.** The futures map (R2-P12, T7): eight sites, 20 000 futures as observers, each future centred, heights
  the mean saving, links only where reliable, relative and absolute readings, the stability test over three
  correlation settings declared in advance (the map failed it at 0,75 against 0,8, and the report says so); the
  shared-failure table T8 ("no site is a backup"); internal until the methodologist approves. Then the
  weighting-scenario map of §4.
- **Today.** The `-5` engine: per-row centring, pair statistics with floors and Benjamini-Hochberg, split-half
  agreement, the layout from 4 objects (`domain/sociomap/signed_off_inputs.py:55` `centre`, `:69` `pair_stats`,
  `:103` `bh`; `signed_off_credibility.py:41` `split_half_agreement`; `signed_off_layout.py:71` `choose_method`;
  `engine_v2.py:887` `compute_object_map`), the register approving `aia-sociomap-5` for respondent ratings
  (`domain/sociomap_register.py:52` `SOCIOMAP_REGISTER`, `:70`; `domain/research_sociomap.py:214`
  `require_client_facing`), the report's figures from stored maps (`infrastructure/report_docx/object_map_figure.py:128`
  `object_map_snapshots`), and the prototype's proof that the engine takes a futures table as rows
  (`tools/engine_maps.py`, SI3's images). The engine's statistics hold for respondents, not for chosen rows (ADR 0046
  decision 5, MV3).
- **New.** The scenario mode's contract: rows a model's draws, the baseline the imposed input correlation, stability
  as the sensitivity to seeds and correlation settings, no p-value; the three-setting test with its threshold declared
  before computing; T8; the weighting-scenario map; a register entry per mode.
- **Builds it.** `sociomapa-systemu#SYS9` (the scenario mode), `#SYS12` (each mode its own Metodika entry, internal
  until approved); `cost-model-study#CS1` (declared extremes and direction per property, reused by §4), `#CS5` (the
  map on Výsledky and in the report); **new** `sociomapa-systemu#SYS9b`: the shared-failure table T8 and the stability
  test (Spearman on the 28 distances between every two settings ≥ 0,8, three settings declared before computing, a
  failure printed as the exemplar prints it); **new** `sociomapa-systemu#SYS13`: Mapa scénářů vah, the ten lines of §4,
  board MV9. SI1–SI4 keep only what MV9 reads: states, gates, coverage, the overlap check.

### 2.8 Osnova a Zpráva (boards MV4, MV8, M6)

- **Needs.** Shrnutí (Doporučení · Důvod · Jistota · Další rozhodnutí, the rule table, Stav podkladů), Úvod, Přehled
  literatury, Metodika, Předpoklady, the result chapters, Diskuse, Doporučení a provedení (a dated plan with who and
  what output), Meze studie, Literatura, Zkratky, Přílohy A–D, T1–T9; every number with one of seven grades in small
  type and a numbered source at the chapter's end; a part id on every part (R2-P01…P18); every table generated from
  the same computation as the text (R2-P18 D).
- **Today.** The report as data with every number a ref (`domain/report/model.py:98` `Paragraph`, `:243` `Table`,
  `:295` `Figure`), the stored document model `aia-report-document-6` (`domain/report/document_model.py:99`
  `document_payload`), the DOCX renderer with deterministic bytes (`infrastructure/report_docx/renderer.py:48`
  `DocxRenderer`), Czech number printing that never re-rounds (`domain/report/numbers.py:41`, `:68` `interval`),
  the section-source manifest (`domain/report/sources.py:56` `report_sources`), locked content controls on every
  printed number (`domain/report/control_tags.py:46`), the client gate and the sentence check
  (`domain/report/client_gate.py:68`; `domain/report/sentence_check.py:134`), approval once per version
  (`application/report_approval.py:139` `approve_report`), the grades MEASURED, CALIBRATED, MODELLED,
  HOLDOUT_PENDING, UNKNOWN (`domain/report/evidence.py:41` `PrintGrade`; neither CALCULATED nor ESTIMATED exists), the
  chapters composed from a run's verified sources (`application/report_chapters.py:125`;
  `application/report.py:174` `compose_internal_report`), the report editor (ONLYOFFICE) and its saved versions, the
  Lead's report sections (`domain/lead_artifacts.py:180` `REPORT_SECTIONS`).
- **New.** The report outline as data with a provenance link on every point; the report-2 recipe with the
  exemplar's parts and ids; the seven grades mapped to the code's with one table; numbered sources per chapter;
  the Stav podkladů box; the literature chapter from Rešerše; the validity review before approval (R1, MV8); the
  release label for a recommendation on an unregistered method (R9, proposed).
- **Builds it.** `research-findings-stage#FND0` (the outline as data), `#FND2` (every point a resolving link), `#FND3`
  (findings in), `#FND4` (tables from points), `#FND5` (graphs from tables), `#FND8` (stops), `#FND9` (Zpráva written
  from the outline); `situation-reports#RC1` (chapter kinds and outline presets), `#RC4` (fixed method texts signed by
  the methodology owner); `cost-model-study#CP8` (the frame and CALCULATED), `#CP10` (ESTIMATED), `#CR9` (the method
  appendix); `report-delivery#RD3` (approve and export); **new** `research-findings-stage#FND13`: the report-2 recipe,
  R2-P01…P18 as an outline preset with part ids, the grade legend, numbered sources per chapter, Stav podkladů and
  Literatura; **new** `cost-model-study#CP8b`: the seven print grades mapped to the code's (Q1, A5: *z dat klienta* =
  CLIENT_REPORTED, *výpočet* = CALCULATED, *odhad* = ESTIMATED, *úsudek* = a labelled judgement with its author (A3),
  *veřejný zdroj*, *právní předpis* (`legal-context#LGL5`), *průzkum* = the survey origins), each with its admission
  rule; the validity review is MV8 (**new** `research-findings-stage#FND14`: the five questions, four extreme-input
  tests and a named reviewer recorded on the ledger before approval, R1).

## 3. Perspectives

The owner (8 Nov): "all business perspectives: financial, strategic, operational, marketing, logistics". A
**perspective** is a set of **components** of the decision. A component is one measure per option, with a source
(a model result, a client-data number, a cited finding, or a named expert's score), a grade (the exemplar's seven:
*z dat klienta, výpočet, odhad, úsudek, veřejný zdroj, právní předpis, průzkum*), a direction (↑ higher is better,
↓ lower is better) and a declared value scale (the worst and the best anchor as 0 and 10, linear between, clipped
outside). The weighting-scenario map (§4) scores components; the client's rule does not read them. Board MV9 and
`tools/specs_weights.py` (session D) realise this table.

Rules, from the methodology review of 5 Nov (ADR 0046 § The methodology review):
- **Gates are not components** (R2). The rule's four conditions are pass / fail / unknown per option; an unknown
  gate is "cannot be recommended until evidenced", and no weight compensates a failed one.
- **A missing or distributional figure keeps a range, never a point** (R2). A country-level or comparables figure
  (permitting extension, pre-treatment, spur, bridge, trucking surcharge) enters as its range, the base the
  documented minimum; a component that does not apply to an option is null and takes no weight there.
- **One mechanism, one component** (R3). Each component has one of three roles: **úspora**, the saving and its
  restatements (IRR, návratnost, NPV po zdanění); **v modelu**, a part of the saving the model already holds;
  **mimo model**, what the model leaves out. The split is what lets the overlap check (§4, line 6) refuse a vector
  that weights the saving and one of its parts.
- **Judgement is labelled** (A3). A component scored by a person carries that person's name and the grade *úsudek*.
- **An empty perspective stays and says so** (ChemVitro's marketing; central for Velis). **A sum row is not scored**
  when its items are: the cost per tonne in 2032 is drawn by item, never as a total.

### ChemVitro's components

Sources are the exemplar's tables and parts. *Stejné pro všechny lokality* names a build-versus-buy figure that does
not separate the sites, *informační* one the model holds in another form; both are shown and not scored.

| Perspective | Component (per site) | Source | Grade | Direction | Role |
|---|---|---|---|---|---|
| **Finanční** | F1 Medián úspory proti nákupu, NPV 2027–2044 při 8 % | T1, R2-P06 | odhad | ↑ | úspora |
| | F2 Investice v základním případě (gate ≤ 175 beside it) | T5 | výpočet | ↓ | v modelu |
| | F3 P(investice ≤ 175) | T5 | odhad | ↑ | v modelu |
| | F4 IRR; F5 rok návratnosti; F6 NPV po zdanění při 8 % | T4 | výpočet | ↑; ↓; ↑ | úspora |
| | Pobídky: daňová úleva (CZ, PL) nebo dotace (DE), podíl, P(schválení) 0,5 | R2-P10, T9 | z dat klienta; právní předpis; úsudek | informační | in the after-tax view |
| | P(porazí nákup) ≥ 0,75; P(ztráta > 20) ≤ 0,10 | T1 | odhad | gates | |
| **Strategická** | S1 Společné selhání s vedoucí lokalitou pravidla (Odrzyca): podíl budoucností, v nichž je horší než nákup i tato lokalita; n/a pro Odrzycu | T8, R2-P12 | odhad | ↓ | mimo model |
| | Závislost na jednom dodavateli; přirážka 12–22 %; podmínky po roce 2035; zůstatková hodnota 30 % | R2-P03 §2.4, R2-P08 §7.2, T9 | z dat klienta; úsudek | stejné pro všechny lokality | |
| | Tržní pozice | — | — | n/a: the plant supplies Brno (62 %) and Pardubice (38 %) only | |
| **Provozní** | P1 energie; P2 údržba, pojištění a poplatek parku; P3 odpad a voda, each EUR/t in 2032 | T6 | výpočet | ↓ | v modelu |
| | Provozní náklad na tunu 2032 celkem (1 290–1 463 EUR/t) | T6 | výpočet | sum row, unscored | |
| | Najíždění 60–90 % v prvním půlroce | T9 | úsudek | stejné pro všechny lokality | |
| **Marketingová / obchodní** | — | — | — | empty for ChemVitro: captive demand, no customer promise at stake. Velis: customer promise, delivery time, demand growth | |
| **Logistická** | L1 Doprava produktu do Brna a Pardubic, EUR/t | T6 | výpočet | ↓ | v modelu |
| | L2 Vlečka k postavení: 3,4 km × 1,9–2,8 mil. EUR/km (Odrzyca; a range) | T5, T9 | z dat klienta; odhad | ↓ | v modelu |
| | L3 Zesílení mostu, nosnost 16 t proti 40 t: 3,2–5,0 mil. EUR (Eschfeld; a range) | T5, T9 | z dat klienta | ↓ | v modelu |
| | L4 Doprava surovin přes překladiště do stavby vlečky, 10–40 EUR/t (Odrzyca; a range) | T9 | úsudek | ↓ | v modelu |
| **Prostředí a povolování** | E1 Šance na kompenzační opatření: 0,8 kde stanice překračuje limit memoranda, 0,2 jinde v CZ a PL, 0 v DE | R2-P05, T9 | z dat klienta; úsudek | ↓ | v modelu (the decisive input) |
| | E2 Prodloužení povolování s kompenzací: CZ 9–15, PL 12–18 měsíců (ranges) | T9 | z dat klienta | ↓ | v modelu |
| | E3 Předčištění odpadních vod: 6,7–14,1 mil. EUR (Lipová, Lindenau; a range) | T5, T9 | z dat klienta; odhad | ↓ | v modelu |
| | E4 Poplatek chemického parku, 1,1 mil. EUR ročně (Wendelstedt) | T9 | z dat klienta | ↓ | v modelu |
| | P(výroba k 1. 7. 2030) ≥ 0,80 | T1, R2-P07 | odhad | gate | |
| | Emise CO₂ a EU ETS, 56 EUR/t | T6 | výpočet | stejné pro všechny lokality | |
| **Lidé** | H1 Náklady na zaměstnance na tunu 2032 (mzda × skladba mezd × odvody) | T6, T9 | výpočet; právní předpis (prozatímní) | ↓ | v modelu |
| | H2 Doba obsazení místa operátora: Eschfeld 118 dní, ostatní regiony 49–71 (a range) | R2-P07 §6.2, Trh práce v regionech | z dat klienta | ↓ | mimo model (stress test only) |
| | H3 Velký nábor v okolí do roku 2028: Kamenec 380; Bory named without a number, 0–380 (R2-P14) | Trh práce v regionech | z dat klienta | ↓ | mimo model |
| | Růst mezd po roce 2031 | T9 | úsudek | stejné pro všechny lokality | |

What the table shows for the map: 21 scored components; 4 are the saving (F1, F4, F5, F6), 14 are *v modelu* and 3
*mimo model* (S1, H2, H3). The owner's vector "finance 0,5 · provoz 0,3 · logistika 0,2" over every component would
count operations and logistics twice, because the saving already holds their cost per tonne. Two honest scenario
families exist: (a) **úspora + mimo model**, the saving against what the model leaves out; (b) **v modelu + mimo
model**, the parts of the saving against each other, without the saving itself. A scenario names its family.

## 4. The weighting-scenario map (Mapa scénářů vah, board MV9)

1. **Objects** are the options: the eight sites. The buy baseline is the rule's reference, not an object.
2. **Rows** are named weight vectors over the perspectives, each with its family, composed by the researcher or the
   client's people ("LOG · b: logistika 0,3 · provoz 0,5 · finance 0,2"), with who composed it and when, recorded in
   the approval ledger before results where the composer has not seen them (swing weighting, R3).
3. **The fan** around each row is k perturbed vectors from a declared concentration (MV9: 300 draws, concentration
   60, a seed); a sensitivity setting, never a probability (R4). The map prints "podíl testovaných nastavení, v
   nichž je možnost první", never P.
4. **A cell** is the option's weighted score: each component on its declared anchors and direction (0–10, linear,
   clipped; `cost-model-study#CS1`), a perspective's weight shared equally by its admitted components, gates
   excluded and shown as pass / fail / unknown beside the map under a named gate setting (R2).
5. **A range** stays a range: the cell is an interval, the map is drawn at the documented minimum and the row says
   what the top of the range would change; a component null for an option takes no weight there (R2).
6. **The overlap check** reads the roles of §3: a vector that weights the saving (*úspora*) together with one of its
   parts (*v modelu*) is refused by name and offered the two families, (a) úspora + mimo model, (b) v modelu + mimo
   model. Within a family each mechanism counts once.
7. **Height** is the weighted score under the scenario the reader chooses; relative (centred per row) and absolute
   readings side by side, as MV3's contract for the scenario mode (R5).
8. **Layout** is the `aia-sociomap-5` engine's over the rows × objects table, as the prototype already runs it
   (`tools/engine_maps.py`, `compute_object_map`, `domain/sociomap/engine_v2.py:887`); its pair statistics are not read,
   because the rows are settings we chose (MV3). Options close together win under the same weightings.
9. **Apart from the futures map.** The futures map's rows are the model's draws; this map's rows are preferences. They
   sit side by side and are never merged.
10. **Where it goes.** The map is preference information. It enters the report under "Co by závěr změnilo", never the
    recommendation; the client's rule decides (R3). Its method is a Metodika register entry of its own
    (`sociomapa-systemu#SYS12`), internal until the methodologist approves it, labelled *metoda čeká na schválení
    metodikem* wherever it appears.

## 5. Parked

Planned, not deleted; nothing waits on it; it moves on the owner's word.

| Parked | Why | Where it stays |
|---|---|---|
| Type 3, the worker survey; imported fieldwork | the survey lane is frozen (ADR 0046 decision 2); type 2 needs no respondent | the frozen lane; `situation-reports#FW1` |
| Blue Ocean, governance and enterprise-architecture frameworks, the portfolio frameworks | no component of the decision reads them | `analysis-frameworks#AF8`, `#AF10` |
| The analysis catalogue beyond the perspectives (board MV6) | the perspectives name what the report needs | `analysis-frameworks#AF0`, `#AF7` |
| The six diagram stacks: BPMN, flowcharts, framework templates, editors | the exemplar needs tables and five chart kinds, no diagram | `diagrams#DG4`, `#DG5`, `#DG8`; charts stay in `#DG3` |
| Unit and period maps | after the synthetic suite passes | `sociomapa-systemu#SYS11` |
| The expert map beyond what MV9 reads (SI1–SI4's scoring rules, SI4) | the futures map and the weighting map are the MVP's two | `situation-reports#EX1`, `#EX2` |
| Účetnictví (M4c) and Velikost trhu (M4e); operations research beyond cost per tonne (LP, forecasts, safety stock) | no part of the exemplar | `quantitative-families#ACC1–5`, `#MKT1–5`, `#OR1–5` |
| The GDPR register and personal-data records | no register field naming a person enters type 2 | `register-personal-data` |
| Deep Research v2 beyond typed inputs and credibility: triangulation, as-of, monitoring, precedents | after the typed inputs work on ChemVitro | `deep-research-v2#DRV6–DRV9` |
| Public routes beyond SDMX and ČNB; commercial data | the exemplar's public inputs are rates, ETS, taxes | `public-data-routes#PDR3–PDR10` |
| Legal version watch | after the first legal parameter is in a run | `legal-context#LGL4` |
| The shared review with the client's decision-makers | the owner's W26, after the outline works | `research-findings-stage#FND12` |

## 6. Acceptance

**The ChemVitro answer key is the test** (`prototypes/case-chemvitro/ANSWER-KEY.md` on `origin/chore/case-chemvitro`):
whether the pipeline finds the planted facts and applies the rule honestly, not whether it hits the reference's numbers.

| # | The pipeline on the ChemVitro files must | Where it shows |
|---|---|---|
| A1 | price the three traps: wastewater at Lipová and Lindenau (limits against 1 800 / 2 400 mg/l), air at Vrbice and Bory (station values against the memo, compensation and 9–18 months), logistics at Odrzyca (the 3,4 km spur) and Eschfeld (the 16 t bridge) | T5, T9, P1 |
| A2 | add the EPC exclusions, take the overrun from the 36 comparable plants (median 17 %), buy at spot while late, keep tax reliefs out of the pre-tax rule, read 2025-07 as kilograms and the USD row as USD | P1, T5, T9 |
| A3 | apply the rule as written at 8, 6 and 10 %: on the reference's inputs CZ3 Kamenec passes at 8 % with CZ2 close behind, nothing passes at 10 %; where a declared judgement moves the verdict (the exemplar's 20 % compensation chance), print the boundary and say so | T1–T3, R2-P06 §5.3 |
| A4 | name the renewal price (and the Hanshin price) as the assumption most worth checking, through the tornado and the value of information | R2-P08, R2-P09 |
| A5 | render the report's structure: R2-P01…P18, every number with a grade and a numbered source, the tables from the same computation as the text, Stav podkladů | the DOCX and its document model |
| A6 | give the same bytes on rerun under seed 20270201, and refuse a changed input without re-running downstream | the run's artifacts (K4) |

**The review's criteria** (ADR 0046, MV0 M-11 to M-16): K1 decision fitness (the independent review, MV8); K2
uncertainty fitness (decisive distributions, dependence and stress cases justified, T9); K3 recommendation integrity
(the rule, the weighting map and the exploratory analysis kept distinct); K4 change propagation (a revised input
invalidates downstream results and approvals until reviewed); K5 decision timing (every enquiry states its effect on
the deadline, R2-P09 §8.3); K6 claim integrity (automated and human checks for contradictions between text, tables and
figures, as `tools/check.py` holds the canvas to KM4 today).

## 7. Waves

Two weeks each; every wave ends in a slice that runs on the ChemVitro files, nothing paid, recorded model answers.

| Wave | Builds | The slice at its end |
|---|---|---|
| **W1 · Zadání a Data** (weeks 1–2) | `decision-brief#DB0`, `#DB3`, **DB3b**; `client-data-in-analysis#2`, `#2a`, `#3`, `#3a`, `#3b`, `#10`, **#13**; `cost-model-study#CR1`, **CR1b** | the ChemVitro brief with the rule's four conditions and the interpretation record; the 18 files under accepted contracts; the findings code can make (kg vs t, the duplicate, the USD row, the 91 kt capacity, price years) with dispositions; the EPC scope check listed per site |
| **W2 · Předpoklady a Model** (3–4) | `cost-model-study#CP1`, `#CP2`, `#CP3`, `#CP5`, `#CP6`, `#CM7`, **CM8**, `#CR2`; `quantitative-families#FIN1`, `#FIN2`; `client-data-in-analysis#11`, `#5` | T9 as data with ranges, sources and guarantors; the base case: T4 (finance), T5 (investment by item), T6 (cost per tonne 2032) within rounding of the exemplar |
| **W3 · Budoucnosti a Rozhodnutí** (5–6) | `cost-model-study#CR3`, **CR3b**, `#CP10`, `#CR7`, **CR7b**, `#CM2`, `#CR4`, **CM9**; `deep-research-v2#DRV1`, `#DRV2`, `#DRV3`; `legal-context#LGL1–3` | 20 000 futures under seed 20270201; T1–T3 and the verdict at three rates; the decision boundary; delay and hiring tables; the tornado and break-even; Harmonogram; public inputs typed and marked *prozatímní* |
| **W4 · Informace a mapy** (7–8) | `cost-model-study#CR6`, **CR6b**; `sociomapa-systemu#SYS9`, **SYS9b**, **SYS13**, `#SYS12`; `cost-model-study#CS1`, `#CS5`; `research-findings-stage#FND0`, `#FND2`, `#FND3`, `#FND4`, `#FND5` | value of information for the rule and EVPPI with the enquiry table; the futures map with T7, T8 and the three-setting test; the weighting map on the perspectives; the outline with every point linked |
| **W5 · Zpráva a přijetí** (9–10) | `research-findings-stage#FND8`, `#FND9`, **FND13**, **FND14**; `situation-reports#RC1`, `#RC4`; `cost-model-study#CP8`, **CP8b**, `#CR9`; `report-delivery#RD3`; `decision-brief#DB2`, `#DB4`, `#DB5`; `cost-model-study#CP9` | the report-2 DOCX and PDF from the ChemVitro files, every number graded and sourced; MV8's review recorded; A1–A6 and K1–K6 checked; the Lead's triage and proposals on every step |

The order follows the review's (contracts before catalogue) and `cost-model-study`'s dependencies. Typed inputs and
the legal routes run beside W3 and do not gate it: a public input typed by hand, *prozatímní*, is what the exemplar carries.

## 8. Open decisions

**For the product owner**
1. R9, the release label: a recommendation resting on a method outside the register stays *předběžné doporučení*
   (MV0 M-5); it changes W27 and RD0 of 22 Oct. The exemplar labels every such number *odhad (metoda čeká na
   schválení metodikem)* and still recommends; which of the two does report 2 ship with?
2. The weight vectors: is "finance 0,5 · provoz 0,3 · logistika 0,2" meant as family (b) of §3 (the parts of the
   saving against each other), or as the saving against what the model leaves out (family (a))? The overlap check
   refuses the mix; the owner's example needs one reading.
3. Who may compose a weighting scenario: the researcher alone, or the client's people through the shared review
   (`research-findings-stage#FND12`, parked)?
4. The Velis boards M4c and M4e are marked parked; keep them on the canvas as parked, or move them off the path?

**For the methodology owner, A. Bahbouh**
1. The futures map's contract (R5, `SYS9`): rows are 20 000 chosen draws, so what does it print instead of the
   respondent method's "2 of 28 reliable" and split-half 0,91 against 0,59 (R2-P12 §11.2)?
2. The stability test (R2-P18 B): Spearman on the 28 distances between every two of three correlation settings,
   threshold 0,8; approve, or replace the statistic and the threshold.
3. The empirical joint draw (**CR3b**): one comparable plant per future carrying overrun and delay together, as an
   alternative to PERT with a declared correlation.
4. PERT λ, the number of futures and the convergence rule tied to the rule (±0,5 pp on each pass probability, R6).
5. Value of information for the rule (**CR6b**, R7): the rule re-applied per answer branch; approve the definition.
6. The weighting map's fan: the concentration and k, and the statement that its shares are shares of tested
   settings (R4).
7. The seven print grades mapped to the code's (**CP8b**, Q1): one table, Czech labels, admission rules.
8. A register entry for `aia-sociomap-5` with futures or settings as observers (today's entry covers respondents'
   ratings, `domain/sociomap_register.py:70`), or a separate method id per mode (`SYS12`).
