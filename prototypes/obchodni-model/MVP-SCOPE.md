# MVP scope: the report-2 pipeline on today's AIA

Version 3, 9 Nov 2026. Version 1 was session A's of 8 Nov (`BRIEF-mvp-r2.md`); version 2 applied the owner's
decisions of 9 Nov morning (status page R2-Q01 to R2-Q14) after the external review of the package; version 3 applies
his afternoon decisions: respondent maps are not in the business MVP and every other map is (15:10, "omitting the
respondent maps, we need the rest of the maps in the MVP"), as two map types in five configurations (R2-Q15 a),
released with the rest (R2-Q16 b); the map supports the recommendation and never makes it (R2-Q17 a); the scope's
three targets adopted (R2-Q18 a); R2-Q02 a and R2-Q04 a. The spine is study type 2
of the ChemVitro case (`prototypes/case-chemvitro/STUDIES.md`), end to end, producing a report with the content and
quality of `exemplar/ChemVitro_2_model-lokality_nigel.pdf` (parts R2-P01 to R2-P18, tables T1 to T9). Code anchors are
`file:line @ b28ce091` (`origin/develop` on 8 Nov; `apps/` and `packages/` are unchanged since). Paths under
`packages/aia_core/src/aia_core/` are written from `domain/`, `application/` or `infrastructure/`. Plan ids are
`plan#CHUNK`; a chunk marked **new** exists in no plan file yet and is defined here in one line (§2.9 lists them all).
`cost-model-study`, `client-data-in-analysis`, `quantitative-families`, `situation-reports`, `report-delivery` and
`lead-orchestration` are on `develop`; `decision-brief`, `deep-research-v2`, `public-data-routes`, `legal-context`,
`sociomapa-systemu`, `research-findings-stage`, `analysis-frameworks`, `diagrams` and `register-personal-data` are read
from `origin/chore/pivot-business-decisions` @ d8dc8ec5 (ADR 0046, Proposed; the owner said "merge as is" on 9 Nov).
Board codes are the canvas's (`README.md`).

## 1. The decision

**Type 2 is the spine.** The MVP is one study, the nine-step navigator the canvas already has, walked end to end on
the ChemVitro files until AIA renders a report with the exemplar's content: the rule as written at three rates, the
decision boundary with its resolution state, the value of information for the rule, the maps in their two types
(§2.7: the scenario map for the futures and the weighting settings, the observed-data map for experts, units and
months), and every number with a grade and a source. Everything else is parked (§5), planned and not
deleted.

**What it replaces.** A1 of 2 Nov ("Keep all in MVP") is superseded by the owner's words of 8 Nov. The methodology
review's order of 5 Nov holds (R1–R10): contracts and release conditions first, then the whole process on a computed
case with known behaviour. Version 2 adds what the external review of 9 Nov showed was missing: a case with known
behaviour means an independent numerical oracle before ChemVitro (§6), not ChemVitro alone.

**What stays as decided.** One merged study (A2); models propose, code computes, a person approves; the client's rule
makes the recommendation and the maps support it, never make it (R2-Q17); the report is Czech (W28); develop runs advisory class gates on fictional data (A4).

**The analytical contract** (R2-Q10). Seven defaults every build session works to. The methodologist changes what he
disagrees with on his first review day; until then they are the baseline.

| Decided before code | Who decides | The default | What breaks if it stays open |
|---|---|---|---|
| Comparable-cost basis | methodologist the basis; owner the business assumptions; code enforces | Overrun = actual like-for-like EPC scope ÷ original EPC estimate − 1, in one currency and price year; exclusions (land, spur, bridge, pre-treatment, compensation, park fee) added once. The overrun applies only on the like-for-like basis its source states; an ambiguous footnote is clarified in a new version of the source before use, approved by the methodologist (R2-Q02 a) | the investment figure and the 175 gate have no defensible basis |
| Parameter manifest | code the schema; methodologist the uncertainty semantics; owner the business values | Every input, fixed or ranged, structured tables included (tax, depreciation, tax capacity, timing dependencies, distributions, cross-option dependence, scales, method settings), each with unit, period, locator, grade attributes, owner and dependencies. An unjustified bound blocks every numerical claim that reads it | hidden defaults escape provenance and invalidation |
| Rule freeze and amendments | the client confirms the meaning; code records and enforces | Objective, gates, rates, currency and price year, the investment reading and tie treatment frozen before any ChemVitro model result. The fixture reads the investment as total base-case installed investment in 2026 EUR (R2-Q01). Exposure to earlier results is recorded. An amendment is a new revision with reason, approver, rerun, and the old and new outcomes disclosed | there is no authorised rule to apply |
| Distribution endpoints | methodologist; the client supplies business judgements | A hard bound defines support; an elicited quantile is fitted as a quantile; reconciled observations keep their joint structure; disagreement is separate scenarios or an approved mixture; missing evidence keeps a justified range, never an automatic midpoint or distribution | tail risk acquires precision nobody gave it |
| Numerical convergence | methodologist the error control; code the batching | 20 000 independent joint futures, doubled at declared checkpoints up to 1,28 million; exact binomial bounds for gates, order-statistic bounds for medians, widened for repeated looks under one 5 % error budget; a comparison whose bound still crosses its threshold is unresolved and prints as an interval. ±0,5 pp alone certifies nothing | a seed or a resource cap becomes the decision rule |
| Enquiry updating | methodologist the update; the client the acceptable evidence and action | An enquiry has answer branches, reliability, cost and duration, and shared dependencies; the joint model is conditioned, the timetable shifts, the enquiry's cost enters, the rule is re-applied. A letter does not remove uncertainty by itself | the value of information supports no action or deadline |
| Release eligibility (R9, R2-Q05) | owner the policy; methodologist the register; code enforces | Document approval and recommendation eligibility are two states. Labelled unregistered estimates may appear internally and in an independently reviewed *předběžné* client draft. An approved recommendation needs registered methods, the independent review and every decisive comparison resolved | "approved" means different things on different pages |

**The pipeline in eight steps.** Zadání · Data · Rešerše · Předpoklady · Model · Výsledky · Sociomapa · Osnova a
Zpráva. The navigator keeps nine; the last two are one step here, built once (the outline) and printed once (the report).

## 2. The pipeline in eight steps

### 2.1 Zadání (boards Z1–Z5, Z7)

- **Needs.** The decision, eight options plus the buy baseline, four constraints, the CFO's rule written on 2. 11. 2026
  before any result: the objective (the highest median saving against buying) and four conditions (P(beats buying)
  ≥ 0,75; P(loss > 20) ≤ 0,10; P(start by 1. 7. 2030) ≥ 0,80; investment ≤ 175) and one interpretation record (the
  exemplar leaves the CFO's confirmation pending; the rule is not frozen until confirmed) (R2-P02 §1.3). The hand-off
  names the files each step takes (R2-P18 A).
- **Today.** A research study's Brief on the working copy with revision-checked saves
  (`infrastructure/study_workspace_repository.py:241`, a stale save refused; `:194` one revision read back), the edit
  vocabulary (`domain/edit_ops.py:496` `apply_edit`; `application/working_copy.py:57` `apply_edit_ops`), immutable
  Design Revisions (`infrastructure/study_design_repository.py:153` `submit`, `design_not_from_workspace`), the Lead's
  turn and closed output (`domain/research_lead.py:450` `LeadOutput`, `:1491` `lead_request`;
  `application/research_lead.py:807` `post`, `:1122` `decide_edits`). Study kinds are RESEARCH and SIMULATION only
  (`domain/scope.py:457`; `infrastructure/tables.py:645` `study_kind_known`); the model lives inside the one study
  (CP3, no new kind).
- **New.** The analytical contract as a record with its seven items, who decided each and when (C1); the business
  Zadání as data; the rule frozen with its interpretations, what the approver had already seen, and amendments as new
  revisions (B1); the model switch.
- **Builds it.** **new** `cost-model-study#CR0`: the analytical contract as data, seven items with decider, approval
  and version, read by every step that depends on one; `decision-brief#DB0` (the eight parts as data), `#DB2` (triage
  as a Lead turn), `#DB3` (the decision core and the rule), `#DB4` (readiness R1–R7), `#DB5` (the hand-off); **new**
  `decision-brief#DB3b`: a rule of n conditions with per-condition thresholds and rates, the interpretation record a
  named person confirms, the freeze with its exposure record, an amendment as a new revision (extends
  `cost-model-study#CR7`, which judges one quantity against one threshold). Acceptance: no model result before the
  freeze; a stale revision or an undeclared amendment is refused.

### 2.2 Data (boards M1, MV1)

- **Needs.** Every file and document used, with a contract per file (which columns, how); 42 data-check findings
  (units kg vs t, currencies CZK/PLN/USD, price years, a duplicate plant, a spot purchase, a capacity in t/day), each
  with its disposition; the findings that change the result in P1 (R2-P04 §3.4, R2-P18 B, C); a number read from a
  document with its page, cited as *z dat klienta*; the cost scope reconciled (what the comparables' totals and the EPC
  estimate each contain).
- **Today.** Client sources kept once per SHA-256 and read into segments with locators: PDF by page and table row,
  DOCX by paragraph, XLSX and CSV by sheet and row (`infrastructure/source_reading.py:656` `read_source`;
  `domain/client_sources.py:176` `Locator`, `:225` `SourceReading`); a dataset's preview per column with personal
  columns masked (`domain/client_datasets.py:208` `DatasetPreview`, `:54` `PERSONAL_SHARE`); a quote grounded
  literally in its segment (`domain/source_proposals.py:332` `ground`); the Brief's materials naming a dataset by
  source, reading and intended contract, eligible only under an accepted contract that nothing stores yet
  (`domain/brief_materials.py:61` `BriefMaterial`, `:111` `eligibility_of`, version `aia-brief-materials-0-proposed`
  at `:55`). No contract table, no analysis copy, no computation on a client row.
- **New.** The contract accepted on Data with its quality report and the full scoped analysis copy (D1); unit,
  currency, period and cost-scope reconciliation as declared conversions, each a finding with its disposition (D2);
  admitted aggregates, paired comparable rows and document values bound to inputs by locator (D3).
- **Builds it.** `client-data-in-analysis#2` (the contract and its accept route), `#2a` (the quality report), `#3`,
  `#3a`, `#3b` (the analysis copy and its accessor), `#5` (admission, *z dat klienta*), `#10` (accepted on the Data
  step, W6), `#11` (a number from a document with its page, W7); `cost-model-study#CR1` (reconciliation, coverage,
  currency, outliers, accepted on record), `#CP4` (data bindings under the accepted contract, copy SHA-256 pinned);
  **new** `client-data-in-analysis#13`: declared conversions (unit, currency at a dated rate, price year, cost scope)
  and the P1 table of findings with dispositions (použito / opraveno / vynecháno / převzato jako předpoklad); **new**
  `cost-model-study#CR1b`: the scope check, what an estimate's document excludes against what each option's documents
  require, each exclusion an input with its range, added once. Acceptance: kg/t, USD, the duplicate plant, the spot row
  and Bory 120 resolve to source cells; an unused source cannot feed computation.

### 2.3 Rešerše (boards MV2, MV2b)

- **Needs.** Sixteen of the inputs are public: the ETS price and its drift, free allocation, energy drift and
  volatility, exchange rates, employer contributions, tax rates, depreciation, the form of incentives, directive
  (EU) 2024/2881; each *veřejný zdroj* or *právní předpis*, *prozatímní* until verified at the source, named on
  page 1 (Stav podkladů) and in T9's Stav column; a literature chapter with cited works (R2-P03, R2-P16). (The
  exemplar's text says 54 inputs and 16 public; its table T9 has 67 rows. Counts come from the manifest, §2.4.)
- **Today.** Deep Research's six steps with two purposes (`domain/deep_research/integration.py:146`
  `DeepResearchPurpose`), every quote located in a captured snapshot (`domain/deep_research/grounding.py:116`
  `locate_quote`), the sealed bundle (`domain/deep_research/bundle.py:112` `EvidenceBundle`), every query and fetch
  through one gate (`application/web_retrieval.py:534` `RetrievalGate`), a run frozen at enqueue with its settings
  pin (`application/deep_research.py:617` `freeze_design`, `:781` `start`, `:1051` `quote`;
  `domain/deep_research/settings.py:765` `pin`), a captured source added to knowledge by a person's click
  (`application/verified_sources.py:47` `add_verified_source`). A finding is a quote; no typed number comes out of it.
- **New.** A public or legal value typed by hand from an accepted quote into the manifest (value, unit, period,
  locator, as-of date, state *prozatímní / ověřeno u pramene*), credibility tier Úřední / Oborový / Ostatní; a legal
  provision as a verbatim quote that becomes a parameter. Automatic extraction and the SDMX, ČNB, e-Sbírka and
  EUR-Lex routes are parked (§5): a value typed and sourced by hand is what the exemplar carries.
- **Builds it.** `deep-research-v2#DRV1` (the typed input), `#DRV5` (credibility tiers); `legal-context#LGL3` (a
  legal point as a parameter, typed); the manifest itself is **new** `cost-model-study#CP1b` (2.4). Acceptance: every
  public or legal value has unit, period, locator and state; the directive's 2030 applicability is a named scenario or
  an open request, never a silent default.

### 2.4 Předpoklady (board M2)

- **Needs.** Every input in one table T9: low / likely / high, distribution (PERT, fixed, yes/no, uniform), source,
  grade, who stands behind it, state; estimates from client data where possible (EPC overrun median 17 % from 36
  plants; overrun and delay drawn together from one plant per future, Spearman 0,89); the EPC estimate's scope checked
  against each site's documents and the exclusions priced; correlations declared as judgement with a stability test
  fixed before computing (R2-P05, T5, T9).
- **Today.** Nothing holds an input with a range and a guarantor. The pieces exist: a design's assumptions on the
  working copy, the Lead's per-change proposals, client numbers with locators (2.2).
- **New.** The complete parameter manifest (P1): fixed values, ranges, structured tables, taxes and depreciation,
  tax capacity, timing dependencies, distributions, cross-option dependence, scales and method settings, each with
  unit, period, locator, grade attributes, owner and dependencies; the endpoint semantics of the contract (a quantile
  fitted as a quantile, a bound as a bound); a guarantor on each; empirical joint draws from a client table; the scope
  check of an estimate against each option's documents; the stability test declared before computing; the oracle
  fixtures frozen before any of it is built (A1, §6).
- **Builds it.** `cost-model-study#CP1` (the input with its provenance), `#CR2` (low / base / high and a guarantor),
  `#CR3` (PERT and declared dependence; **amended**: an iid Gaussian copula over the continuous inputs with a
  validated rank-to-latent conversion and a valid latent matrix replaces Iman-Conover reordering, so the numerical
  error contract matches the sampler; people who disagree sampled as a mixture, W14, R6); **new** `cost-model-study#CP1b`:
  the parameter manifest, complete and typed, counts and warnings generated from it; **new** `cost-model-study#CR3b`:
  empirical joint draws, one row of a client table per future carrying several inputs together (overrun and delay), the
  table pinned by SHA-256; **new** `cost-model-study#CR1b` (2.2); **new** `cost-model-study#CR10b`: the independent
  oracle (§6) as frozen fixtures with expected intermediates and tolerances, written by a session that never writes
  the model, signed by the methodologist; the stability test's declaration is `sociomapa-systemu#SYS9b` (2.7).
  Acceptance: a quantile is never treated as a bound; moments, dependence and cohort selection match the oracle.

### 2.5 Model (board M3)

- **Needs.** One cost-of-supply model for eight sites and the buy baseline on a shared timeline (decision 1. 2.
  2027 → permits 8–11 months, longer with compensation → construction 22 months plus a comparable plant's delay →
  ramp-up 60–90 %; spot purchases while late; demand above 40 000 t bought at spot; residual value 30 % in 2044;
  taxes inside the model), base case plus the futures, seed 20270201, same bytes on rerun (R2-P04 §3.3, R2-P18 B).
- **Today.** The workflow engine runs typed templates (`domain/workflow_templates.py:66` names `research` only), a
  run's cost ceiling (`domain/run_cost.py:99` `run_cost_ceiling`), results as artifacts with fingerprints
  (`application/research.py:691` `start`). No model type, no compute step, no `Decimal` quantities.
- **New.** The model platform and one model type, `site_cost_of_supply`: event dates, monthly production and
  purchases, itemised cash flows aggregated under the declared discount convention (M1); tax-capacity cases, NPV
  before and after tax, IRR with its root status, payback, residual treatment (M2); the worker and API run it over
  pinned inputs, outputs and dependencies (R1); the futures run under the convergence default of §1, so the verdict
  carries its resolution state.
- **Builds it.** `cost-model-study#CP2` (the model-type contract and the determinism harness), `#CP3` (the model
  inside the one study and its working copy), `#CP5` (the run), `#CP6` (the API), `#CM7` (NPV and discounted
  payback), `#CR3` (the futures), `#CP10` (the ESTIMATED grade, seed and method pinned, the Metodika module of
  defaults); `quantitative-families#FIN1` (the cash-flow schedule), `#FIN2` (IRR by a stated root rule); **new**
  `cost-model-study#CM8`: the `site_cost_of_supply` type (timeline, purchases, operations, residual value, tax as a
  parameter with its capacity cases, T4–T6 as its results) and the doubling convergence rule of §1 with its
  checkpoints and error budget. Acceptance: cash flows reconcile to the oracle's checkpoints; bridge prerequisites and
  temporary trucking behave as the documents say; zero usable tax capacity yields no immediate tax benefit.

### 2.6 Výsledky (boards M4, M4b, M4d, new M4g)

- **Needs.** *Rozhodnutí* (R2-P06–P09): T1–T3, the rule at 8, 6 and 10 %; the verdict as a boundary (compensation
  chance 14 / 15 / 16 %) with each comparison's resolution; delay tables (0/2/4/6 months, with and without
  compensation); hiring delay as a stress test; tornado; break-even prices; post-2035 terms; correlation settings
  leave the verdict unchanged; value of information for the rule first, EVPPI second, neither a budget; the enquiry
  table (output, duration, cost). *Finance* (R2-P10, T4): NPV pre- and post-tax at three rates, IRR, payback,
  incentives as tax reliefs vs grants. *Provoz* (R2-P11, T6): cost per tonne by category in 2032. *Harmonogram*:
  start-date distribution per site against the deadline, P(včas), every month of delay (R2-P07).
- **Today.** Every printed number is an admitted claim (`domain/evidence/admission.py:298` `admit_numeric_claims`,
  `:188` `AdmittedClaim`), support is respondent-shaped (`domain/evidence/support.py:235` `assess_support`;
  `domain/evidence/metrics.py:32` `MetricKind`), seven chart kinds with the median-and-interval chart the exemplar
  uses (`domain/report/model.py:264` `ChartKind`: BAR … DOT_INTERVAL, HEATMAP; renderers
  `infrastructure/report_docx/charts.py:364–370`), the per-question tables export (`application/report_tables.py:176`).
  No rule verdict, no tornado, no stacked absolute bar, no value of information.
- **New.** The rule's verdict table at three rates with gates, median comparisons and the boundary certified under
  the repeated-look bounds, or printed unresolved (U2); one-way and joint stresses, the tornado and bracketed
  break-evens (X1); answer-conditioned policies for the value of information for the rule, practical enquiry ranges
  and EVPPI apart, with estimator checks (V1); the start-date distribution and a Harmonogram board; the Lead reading
  admitted business records and proposing on them (L1).
- **Builds it.** `cost-model-study#CR7` (the rule judged as written), `#CM2` (break-even, one-way sensitivity),
  `#CR6` (EVPPI), `#CR8` (the method on screen), `#CP8` (three chart kinds: absolute stacked bar, tornado, line with
  marked points), `#CP9` (the Lead's model tools and proposals); `quantitative-families#FIN3` (scenarios on NPV and
  IRR); `legal-context#LGL3` (tax relief vs grant as parameters); **new** `cost-model-study#CR7b`: the rule at three
  rates, the decision boundary with each comparison's resolution state (resolved at n draws / unresolved, printed as an
  interval), delay and hiring tables, post-2035 and correlation recomputations, each one change at a time and said so;
  **new** `cost-model-study#CR6b`: value of information for the rule (R7: the rule re-applied per answer branch under
  the enquiry's reliability, cost, duration and dependencies, the policy evaluated on independent draws) against
  EVPPI, and the enquiry table with its effect on the deadline (K5); **new** `cost-model-study#CM9`: Harmonogram, the
  start-date distribution per option against the deadline, P(včas) and the months-of-delay table, board M4g. `#CR4`
  (Sobol) is parked. Acceptance: a near-threshold result stays unresolved where the bounds say so; answer branches
  keep their dependence; waiting and cost change the result.

### 2.7 Sociomapa (boards MV3, SI1–SI4 reduced, new MV9)

**Two map types, five configurations** (R2-Q15 a). What decides a map's test is where its rows come from, so the
types split there and nowhere else. Respondent maps are not in the business MVP (the owner, 9 Nov 15:10; the survey
lane is frozen, ADR 0046 decision 2); the `-5` engine stays, and both types reuse its layout, terrain and determinism.

| Type | Configuration | A row is | Prepared | The test, declared before computing | Height |
|---|---|---|---|---|---|
| **Scenario map** (rows the model generates) | futures | one draw of the cost model | each row centred | stability across the declared assumptions and seeds: Spearman of the distances between every two settings ≥ 0,8; no p-value; shared-loss table with counts | mean saving |
| | weight settings | one weight setting from the fans around the client's centre (§4) | weighted score, each row centred | shares first / tied / unresolved per scenario and fan, never pooled; the same stability test | mean score, the centre score beside, NPV beside unweighted |
| | both crossed | one future scored under one weight setting | as above | as above, per named scenario | as above |
| **Observed-data map** (rows observed) | experts | one named expert × one criterion | objects share a scale: each row centred | experts resampled whole, each sample laid out by the engine; one radius per map | mean score |
| | units | one branch, product or customer | objects do not share a scale: each measure standardised | units bootstrapped, by cluster where they cluster; a pair is drawn only where its interval excludes zero | open, for the methodologist |
| | months | one month of a firm's series | each series detrended, then standardised | surrogates with the same autocorrelation, Benjamini–Yekutieli at 5 %, effective-n floor, block bootstrap; a pair is drawn only where it beats its surrogates | open, for the methodologist |

The analyst declares, before any result, what the rows are; that selects the preparation and the test. Nobody chooses
a test after seeing results. Merging the two types is refused: a scenario map would gain a significance it cannot
have, or an observed map would lose its sampling uncertainty.

- **Needs.** The futures configuration (R2-P12, T7): eight sites, the futures as rows, each future centred, heights the
  mean saving, relative and absolute readings, the stability test over three correlation settings declared in
  advance (the map failed it at 0,75 against 0,8, and the report says so); the shared-failure table T8 as the tested
  downside dependence, never "no site is a backup" without a switching analysis. The weight-settings configuration of
  §4. The observed-data configurations on the synthetic suite's planted structures (§6), and on a case's data where a
  study has them. Every configuration internal until its register entry is approved.
- **Today.** The `-5` engine: per-row centring, pair statistics with floors and Benjamini-Hochberg, split-half
  agreement, the layout from 4 objects (`domain/sociomap/signed_off_inputs.py:55` `centre`, `:69` `pair_stats`,
  `:103` `bh`; `signed_off_credibility.py:41` `split_half_agreement`; `signed_off_layout.py:71` `choose_method`;
  `engine_v2.py:887` `compute_object_map`), the register approving `aia-sociomap-5` for respondent ratings
  (`domain/sociomap_register.py:52` `SOCIOMAP_REGISTER`, `:70`; `domain/research_sociomap.py:214`
  `require_client_facing`), the report's figures from stored maps (`infrastructure/report_docx/object_map_figure.py:128`
  `object_map_snapshots`), and the prototype's proof that the engine takes a futures table as rows
  (`tools/engine_maps.py`, SI3's images). The engine's statistics hold for respondents, not for chosen or
  autocorrelated rows (ADR 0046 decision 5, MV3).
- **New.** The scenario map's contract, fit and stability checks, correct labels and no respondent inference (G1),
  layout convergence reported apart from representation fit; the observed-data map's declared preparation, relation
  statistic, null and resampling per configuration (`sociomapa-systemu` SYS2–SYS8), with the engine's layout fed the
  configuration's relation matrix. A register entry per configuration.
- **Builds it.** The scenario map: `sociomapa-systemu#SYS9` (the futures configuration), **new** `#SYS9b` (the
  shared-failure table T8 with its denominators and the stability test: Spearman on the 28 distances between every two
  settings ≥ 0,8, three settings declared before computing, a failure printed as the exemplar prints it and the
  retained readings tested on their own), **new** `#SYS13` (the weight-settings configuration as §4 defines it: the
  disjoint allocation, the common scales and weights, score bounds, the sensitivity settings and the first / tie /
  unresolved shares, board MV9), `cost-model-study#CS1` (declared anchors and direction per perspective scale), `#CS5`
  (the map on Výsledky and in the report). The observed-data map, the plan's existing chunks brought into the MVP:
  `sociomapa-systemu#SYS1` and `#SYS1b` (the synthetic suite with planted answers, and today's statistics run on it as
  the baseline: the configurations' acceptance fixtures), `#SYS2`–`#SYS8` (declared preparation, relation statistic,
  surrogate baseline, effective-n floor, Benjamini–Yekutieli, resampling, fit), `#SYS10` (experts), `#SYS11` (units and
  months; its "only after the suite passes" gate is replaced by R2-Q16 b, below). Both types: `#SYS12` (each
  configuration its own Metodika entry, internal until approved). SI1–SI4 keep only what MV9 reads. Acceptance: the
  allocation conserves costs; splitting a line changes nothing; eight labels stay readable; no respondent inference is
  attached to chosen rows; every configuration finds the structure the suite planted and no other.
- **Release** (R2-Q16 b, the owner's choice against the recommendation). The unit and month configurations are built
  and released in the MVP with the rest; no separate validation-suite gate follows the MVP. What still holds for every
  configuration: its acceptance fixtures pass (§6), its register entry is approved by the methodology owner before a
  client reads it, and R9 governs the recommendation. The risk, stated once: short autocorrelated series show false
  patterns; the surrogate null and the register entry are the guard.

### 2.8 Osnova a Zpráva (boards MV4, MV8, M6)

- **Needs.** Shrnutí (Doporučení · Důvod · Jistota · Další rozhodnutí, the rule table, Stav podkladů), Úvod, Přehled
  literatury, Metodika, Předpoklady, the result chapters, Diskuse, Doporučení a provedení (a dated plan with who and
  what output), Meze studie, Literatura, Zkratky, Přílohy A–D, T1–T9; every number with one of seven grades in small
  type and a numbered source at the chapter's end; every table generated from the same computation as the text
  (R2-P18 D). The report is organised around the decision (R10): the argument first, the technical substantiation in
  appendices; the exemplar's eighteen parts are the content checklist, not a mandatory order.
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
- **New.** Admission and the outline extended to findings, judgements and inferences, with the seven printed grades as
  projections of four attributes (source, method, uncertainty, validation), so a calculation from a judgement prints
  *výpočet* and carries its lineage and validation state apart (T1); the report, charts and annexes composed through
  the DOCX renderer, with PDF export (T2); staleness, the independent review and release eligibility enforced as
  states (T3); the recorded end-to-end acceptance (Q1) and the review dossier with one review-and-fix cycle (Q2).
- **Builds it.** `research-findings-stage#FND0` (the outline as data), `#FND2` (every point a resolving link), `#FND3`
  (findings in), `#FND4` (tables from points), `#FND5` (graphs from tables), `#FND8` (stops), `#FND9` (Zpráva written
  from the outline); `situation-reports#RC1` (chapter kinds and outline presets), `#RC4` (fixed method texts signed by
  the methodology owner); `cost-model-study#CP8` (the frame and CALCULATED), `#CP10` (ESTIMATED), `#CR9` (the method
  appendix); `report-delivery#RD3` (approve and export), `#RD1` (PDF); `mvp-master-plan#MP17` (MVP-ACCEPT-2 redefined
  as the recorded browser, API and worker acceptance on the ChemVitro files); **new** `research-findings-stage#FND13`:
  the report-2 recipe, the eighteen parts as a content checklist with part ids, the grade legend, numbered sources per
  chapter, Stav podkladů and Literatura, organised around the decision; **new** `cost-model-study#CP8b`: the seven
  print grades as projections of the four attributes mapped to the code's (*z dat klienta* = CLIENT_REPORTED,
  *výpočet* = CALCULATED, *odhad* = ESTIMATED, *úsudek* = a labelled judgement with its author (A3), *veřejný zdroj*,
  *právní předpis*, *průzkum* = the survey origins), each with its admission rule, lineage and validation carried apart;
  **new** `report-delivery#RD13`: release eligibility as a state apart from document approval (R9): *předběžné* after
  the independent review, *schválené doporučení* only on registered methods with every decisive comparison resolved,
  a changed root invalidating descendants and approvals; **new** `research-findings-stage#FND14`: the validity review
  MV8 as a dossier (the five questions, the extreme-input cases with independently expected outcomes, a named
  reviewer on the ledger before approval, one review-and-fix cycle, R1). Acceptance: every claim resolves; a changed
  root invalidates its descendants and their approval; an unsupported definitive verdict cannot be released.

### 2.9 Work ids in this scope

The external review of 9 Nov named the work with plan-local ids. The plan chunks stay the record; the table maps each.

| Review id | What it is | Plan chunk |
|---|---|---|
| C1 | the analytical contract recorded | **new** `cost-model-study#CR0` |
| B1 | rule freeze, interpretations, exposure, amendments | **new** `decision-brief#DB3b` |
| S1 | the eight steps on the one study, no new kind | `cost-model-study#CP3`, `research-findings-stage#FND1` |
| D1 | contracts and full scoped analysis copies | `client-data-in-analysis#2`, `#2a`, `#3`, `#3a`, `#3b`, `#10` |
| D2 | units, currencies, periods, cost scope with dispositions | **new** `client-data-in-analysis#13`, **new** `cost-model-study#CR1b` |
| D3 | aggregates, paired rows and document values bound to inputs | `cost-model-study#CP4`, `client-data-in-analysis#11`, **new** `cost-model-study#CR3b` |
| P1 | the complete typed parameter manifest | **new** `cost-model-study#CP1b` (+ `deep-research-v2#DRV1`, `#DRV5`, `legal-context#LGL3` for typed public and legal values) |
| A1 | the independent oracle fixtures | **new** `cost-model-study#CR10b` |
| U1 | distributions, copula, paired observations, cross-option dependence | `cost-model-study#CR3` (amended), **new** `#CR3b` |
| R1 | worker and API over pinned model inputs | `cost-model-study#CP5`, `#CP6` |
| M1, M2 | cash flows; tax, NPV, IRR, payback, residual | **new** `cost-model-study#CM8`, `#CM7`, `quantitative-families#FIN1`, `#FIN2` |
| U2 | gates, medians and the boundary certified | **new** `cost-model-study#CR7b` (with CM8's convergence rule) |
| X1 | stresses, tornado, break-even | `cost-model-study#CM2`, **new** `#CR7b` |
| V1 | value of information for the rule, enquiry, EVPPI | **new** `cost-model-study#CR6b`, `#CR6` |
| L1 | the Lead on business records and proposals | `cost-model-study#CP9` |
| W1, W2 | the weight-settings configuration's allocation, scales, bounds, sensitivity, shares | **new** `sociomapa-systemu#SYS13`, `cost-model-study#CS1` |
| G1 | the engine and renderer for the scenario map | `sociomapa-systemu#SYS9`, **new** `#SYS9b`, `#SYS12`, `cost-model-study#CS5` |
| (version 3) | the observed-data map: suite, statistics, experts, units, months | `sociomapa-systemu#SYS1`, `#SYS1b`, `#SYS2`–`#SYS8`, `#SYS10`, `#SYS11`, `#SYS12` |
| T1 | admission and outline for findings, judgements, grades | `research-findings-stage#FND0`, `#FND2`, **new** `cost-model-study#CP8b` |
| T2 | the report, charts, annexes, PDF | `research-findings-stage#FND9`, **new** `#FND13`, `cost-model-study#CP8`, `report-delivery#RD3`, `#RD1` |
| T3 | staleness, review and release eligibility | **new** `report-delivery#RD13`, `research-findings-stage#FND8` |
| Q1 | recorded end-to-end acceptance | `mvp-master-plan#MP17` |
| Q2 | the independent review dossier | **new** `research-findings-stage#FND14` |

**Seventeen new chunks:** `decision-brief#DB3b`; `client-data-in-analysis#13`; `cost-model-study#CR0`, `#CP1b`,
`#CR1b`, `#CR3b`, `#CM8`, `#CR7b`, `#CR6b`, `#CM9`, `#CR10b`, `#CP8b`; `sociomapa-systemu#SYS9b`, `#SYS13`;
`research-findings-stage#FND13`, `#FND14`; `report-delivery#RD13`. Version 1 had thirteen; CR0, CP1b, CR10b and RD13
are the review's additions. They enter the plan files in the docs PR written from this version (R2-Q09). Version 3
adds no new chunk: the observed-data map is the plan's existing SYS1, SYS1b, SYS2–SYS8, SYS10 and SYS11; the docs PR
amends SYS11's release condition to R2-Q16 b and moves the respondent mode out of the MVP.

## 3. Perspectives

The owner (8 Nov): "all business perspectives: financial, strategic, operational, marketing, logistics". Version 1
scored twenty components in three roles and let two families of weight vectors avoid double counting. The review
showed the overlap check did not hold inside a family and that a component absent for one site dropped that site's
weight. The owner chose the partition (R2-Q03): **every pre-tax cash-flow line of a site goes to exactly one leaf
under one perspective; a perspective's score is its discounted cost through a value function shared by all sites; the
total NPV saving stands beside the weighted score, unweighted.**

Rules:
- **Gates are not components** (R2). The rule's four conditions are pass / fail / unknown per option, shown beside the
  map; no weight compensates a failed one.
- **One expenditure, one leaf** (R3). Distinct expenditures caused by one event may appear in different leaves; the
  same expenditure never appears twice. Delay costs enter through the purchases they cause. Total investment is not a
  leaf: its items are.
- **Leaves are an accounting breakdown, not weighted subcriteria.** Splitting a line leaves its perspective's total,
  the score and the rank unchanged; scoring a parent beside its children fails admission.
- **Perspective totals reconcile** to the site's cost; buying cost minus site cost reconciles to the NPV saving.
- **A perspective with no line in the case** (strategic and marketing for ChemVitro) stays visible at weight 0 for
  every site, approved as such, and the map says so; nothing is redistributed silently (R2-Q04 a). A nonzero weight on an empty
  perspective is refused until clarified.
- **Absence versus unknown.** An evidenced absence of an applicable expenditure is cost 0 through the common scale; an
  unknown expenditure keeps its range (§4).
- **What cannot be compared across sites** is not admitted as a scored criterion. Hiring time enters the timetable
  and the gates, not a second weighted penalty. The shared-failure analysis (T8) stays a table of its own.
- **Judgement is labelled** (A3). A value a person set carries that person's name and the grade *úsudek*.

### ChemVitro's leaves

| Perspective | Leaves (per site, discounted, pre-tax) | ChemVitro lines placed | Source |
|---|---|---|---|
| **Finanční** | core plant capital; main-plot land; working capital where applicable; remaining ordinary and spot purchases; residual credits and other financial adjustments not allocated below | EPC capital with its overrun; land; spot purchases while late and above 40 000 t; residual value 30 % in 2044 | T4, T5, T9 |
| **Strategická** | no scored leaf until an independently defined consequence is approved | the shared-failure table T8 stays a separate analysis; supplier dependence and the 12–22 % renewal premium are the buy baseline's terms, the same for every site | T8, R2-P03 §2.4 |
| **Provozní** | raw materials; electricity and gas; maintenance and insurance, excluding services allocated elsewhere | T6's energy and maintenance items; the Wendelstedt park fee, 1,1 mil. EUR a year, here once (environmental and park services are a leaf of their own only where itemised) | T6, T9 |
| **Marketingová / obchodní** | no scored leaf for captive supply | the plant supplies Brno (62 %) and Pardubice (38 %); no customer promise at stake. Velis would fill it | R2-P03 |
| **Logistická** | product freight; spur construction and spur land; bridge works; temporary transhipment and haulage | freight to Brno and Pardubice (T6); Odrzyca's 3,4 km spur at 1,9–2,8 mil. EUR/km and its land; Eschfeld's 16 t bridge at 3,2–5,0 mil. EUR; transhipment 10–40 EUR/t during the spur's construction | T5, T6, T9 |
| **Prostředí a povolování** | pre-treatment capital and operation; air abatement; compensation; water and sewer, hazardous waste, carbon and separately itemised environmental services | Lipová's and Lindenau's pre-treatment 6,7–14,1 mil. EUR; compensation where the station exceeds the memo's limit (chance 0,8 / 0,2 / 0 by country, a judgement) and its 9–18 months through the timetable; ETS at 56 EUR/t where itemised | T5, T9, R2-P05 |
| **Lidé** | wages, employer contributions, evidenced recruitment expenditure | T6's labour cost per tonne; Eschfeld's 118-day hiring time and the nearby hiring (Kamenec 380, Bory 120 from `trh_prace_regiony.xlsx` PL2; the exemplar left Bory unnumbered) enter the timetable and the gates, not a leaf | T6, T9, R2-P07 |

Every disposition in the case pack's documents, the air-abatement technology and the spur land among them
(ANSWER-KEY.md §2.2–2.3), is a leaf line or a justified exclusion. Board MV9 and `tools/specs_weights.py` are rebuilt
to this table at the next canvas version (R2-Q13).

## 4. The scenario map's weight-settings configuration (Mapa scénářů vah, board MV9)

1. **Objects** are the options: the eight sites. The buy baseline is the rule's reference, not an object.
2. **Scenarios** are named weight vectors over the seven perspectives, composed by the researcher from what the
   client's people approved (R2-Q06), each with who approved it and when, recorded in the approval ledger before the
   composer sees results (swing weighting over the perspectives' declared scales, R3). The owner's example reads
   0,20 finance · 0,50 operations · 0,30 logistics · 0 elsewhere, and is admitted.
3. **One scoring structure for every site:** score(site) = Σ over perspectives of w(p) · v(p, cost(site, p)), where
   cost is the discounted pre-tax sum of the perspective's leaves and v the perspective's value function on fixed 0–10
   anchors, approved together with the weights before any site score is shown (`cost-model-study#CS1`). A value outside
   the anchors triggers review, never silent clipping. One weight vector for all sites; a globally inactive perspective
   is weight 0 everywhere.
4. **A range keeps its direction:** a cost range gives a lower and an upper score bound; neither the minimum cost nor a
   midpoint stands in for the missing fact. The table shows both bound views and the interval, labelled as bounds, not
   as jointly feasible futures.
5. **A robust leader** needs a positive lower bound on its score difference against every rival over all admitted
   unknowns jointly; overlapping intervals mean no leader is established, and the map says so.
6. **Sensitivity**, per named scenario: the approved centre; Dirichlet fans at concentration 20, 60 and 180 with 300
   settings each, on positive-weight coordinates only, explicit zeros kept; directed weight transfers and a simplex
   grid where manageable; approved alternative scales and uncertain cost allocations; evidence bounds and coherent
   joint stress cases. Results are reported per scenario, fan and setting; unique-first, tie and unresolved shares
   reconcile to 100 %; scenarios are never pooled into one popularity figure (R4).
7. **Height** is the weighted score under the setting the reader chooses; relative (centred per row) and absolute
   readings side by side (R5).
8. **Layout** is the `aia-sociomap-5` engine's over the settings × sites table (`tools/engine_maps.py`,
   `compute_object_map`, `domain/sociomap/engine_v2.py:887`): proximity means similar score responses to the tested
   settings, no more. The map records its fit, numerical convergence and sensitivity under its own mode contract;
   unsupported geometry produces no spatial claim. No respondent labels, reliable-pair claims, respondent segments or
   sampling-error circles appear.
9. **Gate status** stands beside each site; the rule's verdict has a panel of its own. A hypothetical change of a gate
   is a named scenario.
10. **Apart from the futures, and where it goes.** The futures configuration's rows are the model's draws; this
    configuration's rows are preferences; they are mapped apart unless a named scenario crosses them (§2.7). The map is
    preference information. It enters the report under "Co by závěr změnilo": it supports the recommendation and never
    makes it; the recommendation comes from the decision rule (R3, R2-Q17). Its method is a Metodika register entry of its
    own (`sociomapa-systemu#SYS12`), internal until the methodologist approves it.

## 5. Parked

Planned, not deleted; nothing in the ten weeks waits on it; it moves on the owner's word.

| Parked | Why | Where it stays |
|---|---|---|
| Type 3, the worker survey; imported fieldwork; survey processing | the survey lane is frozen (ADR 0046 decision 2); type 2 needs no respondent | the frozen lane; `situation-reports#FW1` |
| The framework picker in Zadání and every analysis framework | the decision names its components; nothing reads a framework | `analysis-frameworks#AF0`, `#AF7`, `#AF8`, `#AF10` |
| Other model types; the generic cost-scenario infrastructure beyond `site_cost_of_supply` | one type, one case, ten weeks | `cost-model-study#CP2`'s template registry beyond one template; `quantitative-families#ACC1–5`, `#MKT1–5`, `#OR1–5` |
| Automatic public-data and legal connectors (SDMX, ČNB, e-Sbírka, EUR-Lex) and automatic extraction | a value typed by hand from an accepted quote, *prozatímní*, is what the exemplar carries | `public-data-routes#PDR1–PDR10`; `legal-context#LGL1`, `#LGL2`, `#LGL4`; `deep-research-v2#DRV2`, `#DRV3` |
| Fitted demand forecasting; Sobol / PRCC global sensitivity | the tornado and the one-change-at-a-time runs are the exemplar's | `quantitative-families#MKT4`; `cost-model-study#CR4` |
| The respondent map mode (survey rows) | the survey lane is frozen and the business MVP has no respondents; the engine stays, and both map types reuse its layout and terrain | `sociomapa-systemu`'s respondent mode; the frozen lane |
| The six diagram stacks and the diagram editor | the exemplar needs tables and five chart kinds | `diagrams#DG4`, `#DG5`, `#DG8`; charts stay in `#DG3` |
| The shared client-review interface; monitoring | the researcher records client approvals (R2-Q06); monitoring after the first release | `research-findings-stage#FND12`; `deep-research-v2#DRV8` |
| Účetnictví (M4c) and Velikost trhu (M4e) | no part of the exemplar; kept on the canvas as parked | `quantitative-families#ACC1–5`, `#MKT1–5` |
| The GDPR register and personal-data records | no register field naming a person enters type 2 | `register-personal-data` |
| Deep Research v2 beyond typed inputs and credibility | after the typed inputs work on ChemVitro | `deep-research-v2#DRV6–DRV9` |

## 6. Acceptance

**Independent oracle first, ChemVitro second** (R2-Q11, R2-Q12). An analyst session that never writes the model code
freezes the fixtures: equations, inputs, expected intermediates, tolerances and conventions. The oracle imports no
production function. The methodologist signs the fixtures before wave 2 starts.

### O-CF, the cash-flow fixture

Two years, end-year flows, 10 % discount, no inflation, tax, residual or uncertainty, in toy units.
C = I + c₁/1,1 + c₂/1,1²; saving = C(buying) − C(site).

| | Buying | A | B |
|---|---|---|---|
| initial capital | 0 | 50 | 20 |
| cost, year 1 / year 2 | 100 / 100 | 60 / 60 | 80 / 80 |
| present cost | 173,5537190083 | 154,1322314050 | 158,8429752066 |
| saving against buying | 0 | 19,4214876033 | 14,7107438017 |
| saving at zero discount | 0 | 30 | 20 |

A terminal receipt of 12,1 at year 2 lowers A's present cost by exactly 10. A separate dated-flow fixture tests the
ChemVitro convention; the toy prescribes none.

### O-INFO, the information fixture

Two equally likely states; A saves 40 / −20, B saves 5 / 5, buying 0. Start and investment gates pass; the gates
P(beats buying) ≥ 0,75 and P(loss > 20) ≤ 0,10 apply. Without information the rule picks B (value 5). Perfect
information picks A in the good state and B in the bad: 22,5. **Value of information for the rule: 17,5.**
Expected-benefit optimisation without gates starts at A (10), so its EVPI is **12,5**. Both must be reproduced and told
apart.

### O-CHEM

After the cost basis is reconciled (R2-Q02): file hashes, transformations, the manifest, equations, event precedence,
shared and site-specific shock structure, rule and method versions frozen; investment, timing and site cash-flow
checkpoints computed independently before production results are compared. The reference's and the exemplar's
readings are frozen apart where both are kept; neither 39,8 nor 137,1 (Kamenec with compensation at zero) is a target
for the other configuration (ANSWER-KEY.md §1; exemplar p. 13).

### The tests

| Test | Fixture and the failure it must produce |
|---|---|
| Units, currency, periods | the kg row against its hand-normalised 2 844 t; the USD row with a frozen dated rate; a quote deliberately misclassified as non-hazardous; a silent substitution is rejected |
| Accounting identities and scope | O-CF plus dated ramp-up, spot, excess demand, pre-treatment, bridge, spur and land, tax-capacity cases; every expense appears once; totals reconcile; zero usable tax capacity yields no immediate benefit |
| Criterion splitting | one logistics cost split while its total, scale and weight are conserved: scores, ranks and shares unchanged; parent beside children fails admission |
| Missing-data states | known amount, evidenced zero, global irrelevance, unknown range, several unknowns that jointly reverse a ranking; no site-specific reweighting, no false robust leader |
| Threshold uncertainty | known probabilities below, at and above a threshold; samples around 0,797 and 0,804; nearly tied medians; repeated-seed runs of the whole stopping procedure, not one final interval |
| Correlated information branches | a finite joint-state table with known masses, dependence and impossible answer combinations, plus O-INFO; an independent-marginal substitution must fail |
| Distributions and dependence | analytic PERT moments; quantile-fitted marginals; paired observations; common national and site shocks; achieved dependence and each stress change checked |
| Maps, scenario type | known matrices; identical profiles; a dominated option with a similar profile; poor geometry; deliberate instability across declared settings; 800 scenarios × 7 options from a cost model with a known correlation; similarity never becomes an unsupported co-winning claim |
| Maps, observed-data type | `sociomapa-systemu#SYS1`'s suite, 1 000 seeded replicates at T or n 24, 36, 60, 120: experts with planted rater clusters (a whole-expert resample must widen the radius as experts fall); 40 units × 10 drivers from known factors, with 10 % outliers and one level shift; null worlds (independent random walks, AR(1) at 0,3, 0,7 and 0,95, seasonal series with no cross-relation) where no pair may be drawn beyond the declared false-discovery rate; 12 KPIs from 3 factors and a sparse VAR(1) where the planted pairs must be found; the baseline run of today's statistics on the same fixtures (`#SYS1b`) beside each |
| Downstream invalidation | stored source, copy, contract, manifest, rule, scales, methods, run, maps, outline and approval; each root mutated makes its descendants stale; old artifacts stay immutable |
| Claim meaning and release | wrong percentile wording; rounding that hides a gate failure; an unregistered method; an unresolved comparison; the check reads meaning, not only matching refs |

**ChemVitro, the integration check.** The answer key (`prototypes/case-chemvitro/ANSWER-KEY.md`, branch
`chore/case-chemvitro`) stays: whether the pipeline finds the planted facts and applies the rule honestly.

| # | The pipeline on the ChemVitro files must | Where it shows |
|---|---|---|
| A1 | price the three traps: wastewater at Lipová and Lindenau (limits against 1 800 / 2 400 mg/l), air at Vrbice and Bory (station values against the memo, compensation, abatement and 9–18 months), logistics at Odrzyca (the 3,4 km spur and its land) and Eschfeld (the 16 t bridge); every cost and dependency in the documents has a disposition | T5, T9, P1 |
| A2 | add the EPC exclusions once on the reconciled basis, take the overrun from the 36 comparable plants, buy at spot while late, keep tax reliefs out of the pre-tax rule, read 2025-07 as kilograms and the USD row as USD | P1, T5, T9 |
| A3 | apply the rule as written at 8, 6 and 10 % with each comparison's resolution state; where a declared judgement moves the verdict (the 20 % compensation chance), print the boundary and say so | T1–T3, R2-P06 §5.3 |
| A4 | separate the verification of model inputs (the renewal and Hanshin prices through the tornado) from information acquisition inside the accepted model (compensation, through the value of information) | R2-P08, R2-P09 |
| A5 | render the report around the decision: every number with a grade and a numbered source, the tables from the same computation as the text, Stav podkladů, the eighteen parts covered | the DOCX, its document model and PDF |
| A6 | give the same bytes on rerun under seed 20270201, and refuse a changed input without re-running downstream | the run's artifacts (K4) |

**The review's criteria** (ADR 0046, MV0 M-11 to M-16): K1 decision fitness (the independent review, MV8); K2
uncertainty fitness (decisive distributions, dependence and stress cases justified, T9); K3 recommendation integrity
(the rule, the weighting map and the exploratory analysis kept distinct); K4 change propagation (a revised input
invalidates downstream results and approvals until reviewed); K5 decision timing (every enquiry states its effect on
the deadline, R2-P09 §8.3); K6 claim integrity (automated and human checks for contradictions between text, tables and
figures; counts and warnings generated from the manifest, never typed).

**Integration exit.** One real browser, API and worker journey on the case files produces the T1–T9 equivalents, both
map types in their configurations (the observed-data map on the suite where the case has no such rows), the enquiry table and the QA annex from frozen artifacts, and passes the independent review. Recorded
acceptance and bounded live source verification stay separate (`docs/architecture/research-journey.md` §1).

## 7. Waves

Five waves of two weeks (R2-Q07): three build sessions (data and backend; numerical methods; product and report), one
analyst session at half time that never writes model code, the methodologist one day a week, the owner's and the
client's decisions in time. A session-day is implementation with its tests and routine review; waiting for a decision
is not counted. **116–168 session-days in all; plan against the upper end.** Version 2's 97–139 plus 19–29 for the
observed-data map (the table below the waves). Three build sessions have 150 session-days in ten weeks, so the upper
end is 18 over: a fourth build session for the map work in weeks 1–8, or about two more weeks (§8).

| Wave | Builds (session-days) | Exit; the ChemVitro slice | Beside it; the assumption |
|---|---|---|---|
| **W1 · Smlouvy a Data** (weeks 1–2) | CR0 2–3; CR10b 3–4; CP3 + FND1 3–4; DB3b 3–4; client-data #2, #2a, #3, #3a, #3b, #10 6–8; CP1b schema 1–2; SYS9/SYS12 engine feasibility 1–2; FND0/FND2 evidence schema 2–3; SYS1 suite generators 3–4. **24–34** | contracts and oracles accepted; the investment reading confirmed in the fixture or marked unresolved; the purchase file's contract and full copy work; the eight-step shell and the evidence interfaces exist | the analyst freezes O-CF and O-INFO; the engine is tried on both business matrices at once. Assumes no reader or engine algorithm needs replacing |
| **W2 · Vstupy a Model** (3–4) | client-data #13 4–6; CP4 + #11 + CR3b 4–6; CP1b completion 3–4; CP5, CP6 3–4; CM8 7–10; SYS1b baseline run 1–2; SYS2, SYS3 declared preparation and relation statistic 2–3. **24–35** | the used sources reconciled; the model reads pinned bindings; production, purchases and the investment ledger match the oracle's checkpoints | source verification beside cash modelling. Assumes one process, one ledger schema, bounded manual extraction |
| **W3 · Budoucnosti a Rozhodnutí** (5–6) | CM7, FIN1, FIN2 4–6; CR3 (copula) 5–7; CR7, CR7b 4–6; CM2 3–4; CP9 first integration 2–3; SYS4–SYS7 surrogate null, effective-n floor, Benjamini–Yekutieli, resampling per configuration 5–7. **23–33** | T1–T6 equivalents and the timing distributions at three rates; every decisive comparison resolved or printed unresolved; commercial, delay, hiring and dependence stresses run | sampling beside finance and tax cases and the Lead's first integration. Assumes signed distributions and dependence, fixed tax-capacity cases, bracketed break-even solving |
| **W4 · Informace a mapy** (7–8) | CR6, CR6b 6–9; SYS13 + CS1 4–6; CR9 shares and views 3–4; SYS9, SYS9b, CS5 completion 4–5; FND3, FND4, FND5, CP8b 3–4; SYS8 fit 1–2; SYS10 experts 2–3; SYS11 units and months 3–4. **26–37** | the information fixtures pass; T7, T8 and the weighting scenarios run; the observed-data configurations find the suite's planted structures; score bounds and gate status visible; the outline holds only resolving admitted claims | information, weighting and outline work share frozen result schemas. Assumes finite approved answer branches, one cost hierarchy, two adapters and no new layout algorithm |
| **W5 · Zpráva a přijetí** (9–10) | CP9 completion 2–3; FND9, FND13, CP8, RD1, RD3 5–7; RD13, FND8 3–4; MP17 4–6; FND14 3–5; SYS12 register entries for the three observed configurations 1–2; the suite over the finished configurations in the acceptance run 1–2. **19–29** | the recorded end-to-end report, annexes and PDF; invalidation and approval checks pass; the independent review determines release eligibility | composition, export, failure injection and review together. Assumes the DOCX renderer and editor reused, bounded PDF conversion, one review-and-fix cycle |

**The observed-data map's 19–29 session-days, and their basis.** No plan chunk carries an estimate, so each is set
against a chunk of this scope that does comparable work:

| Added | Session-days | Compared with |
|---|---|---|
| SYS1 suite generators (five configurations, seeded, pinned by SHA-256) | 3–4 | CR10b, the oracle fixtures, 3–4 |
| SYS1b baseline run + SYS2, SYS3 (declared preparation, relation statistic) | 3–5 | SYS9/SYS12 feasibility 1–2 for the run; CP1b schema 1–2 for the declarations |
| SYS4–SYS7 (surrogates, effective-n floor, Benjamini–Yekutieli, three resampling schemes) | 5–7 | SYS13 + CS1, one new configuration with its sensitivity, 4–6, plus one day for the third scheme |
| SYS8 fit, SYS10 experts, SYS11 units and months | 6–9 | SYS9, SYS9b, CS5 completion 4–5, for three configurations on a shared path |
| SYS12 three register entries; the suite in the acceptance run | 2–4 | RD13, FND8 3–4, halved: entries and runs, no new interface |

Two types rather than five save design and code; no saving is taken from it in these figures.

**The critical path:** approved contracts, oracles and rule → data and bindings → the cash-flow model → joint
uncertainty and the rule → information and maps → admitted report claims → independent review and release. The study
shell, the evidence schema and the engine feasibility test start in week 1. An unresolved rule interpretation blocks
the decision results, not the engineering or the oracle.

**Not estimable yet:** acquiring evidence to reconcile the comparables; a method change the methodology owner's answers on the observed-data statistics require (`sociomapa-systemu#SYS0`); research for the empty perspectives; missing
commercial or tax evidence; replacing an engine algorithm after a failed feasibility test; runtime at the convergence
cap (benchmark by wave 2); live-provider remediation; a structural redesign the review demands. Each is a named
dependency, not a zero-day task. Week 10 may produce a reviewed *předběžné* report if that is the justified state; the
calendar cannot turn an unresolved comparison into an approved recommendation.

## 8. Decisions

**Taken by the product owner** (R2-Q01 to R2-Q18, all answered on 9 Nov and applied above): among them the
comparable-cost basis (R2-Q02 a: the overrun only on the like-for-like basis its source states, an ambiguous footnote
clarified in a new version of the source first, approved by the methodologist; the case pack is its author's, PR
#1155, and the request goes to him directly, R2-Q14), the empty perspectives (R2-Q04 a: strategic and marketing
visible at weight 0 for this case, the map says so), the map types (R2-Q15 a), their release (R2-Q16 b), the map's
place beside the recommendation (R2-Q17 a) and the three targets (R2-Q18 a). The Velis boards M4c and M4e stay on the
canvas as parked.

**Open for the product owner**
1. **Capacity for the maps** (new with version 3). The upper end, 168 session-days, is 18 over three build sessions'
   150. (a) A fourth build session for the map work in weeks 1–8, on the engine behind frozen result schemas;
   (b) about two more weeks for the three sessions; (c) plan against the lower end and cut on overrun. Recommendation:
   (a), because the map work is separable and the critical path does not run through it.

**For the methodology owner, A. Bahbouh** (one review day a week; the first day signs the oracle fixtures)
1. The analytical contract's seven defaults (§1): confirm or amend each; the distribution families, the copula, the
   tail stresses and the 5 % numerical error allocation are his.
2. The futures configuration's contract (R5, `SYS9`): what it prints instead of the respondent method's reliable
   pairs and split-half agreement; layout convergence, representation fit and robustness reported apart.
3. The stability test (R2-P18 B): Spearman on the 28 distances between settings at 0,8; and whether the retained
   country-group readings need a test of their own after a failed global one.
4. The empirical joint draw (**CR3b**) beside the copula (**CR3**): when each is used.
5. Value of information for the rule (**CR6b**, R7) against EVPPI: the estimator's bias and precision checks.
6. The weight-settings configuration (**SYS13**): the value functions' anchors, the fan concentrations, the
   robust-leader rule, the map-fit thresholds.
7. The seven print grades as projections of four attributes (**CP8b**, Q1): the table, its admission rules.
8. A register entry per configuration (`SYS12`): one method id per configuration, or one entry per type with its
   configurations.
9. The observed-data map's statistics (`sociomapa-systemu#SYS0`, the research's ten questions): the preparation, the
   relation statistic, the surrogate null, the effective-n floor, the multiple-testing rule, the resampling schemes,
   and the suite's thresholds. With R2-Q16 b they are on the MVP's path, not after it.
