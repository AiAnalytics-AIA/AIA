---
status: planned
chunks:
  - "[ ] CP1. Platform types: Quantity (Amount, Rate, Count, Ratio, Duration; Decimal, currency, period), Input with its provenance (client_dataset, stated, public_source; research_result declared and refused until built), Scenario, the Model Revision envelope and its canonical hash; reject-not-coerce validation"
  - "[ ] CP2. The model-type contract: ModelTypeSpec (elements schema, inputs, compute, results schema with each output's grade, charts, report blocks, proposal operations), the registry, a run's pin of type id and version; the determinism test harness"
  - "[ ] CP3. StudyKind.BUSINESS_MODEL and the working copy: the kind, the CHECK constraint migration, a model content kind on the study's owned working project (revision-checked saves, the operation log), the immutable Model Revision; every kind != RESEARCH refusal tested against the new kind"
  - "[ ] CP4. Data bindings: an input from a dataset's analysis copy under its accepted contract (sum, count, mean over a stated filter and period), admitted CLIENT_REPORTED with MQ-18's support, the contract version and copy SHA-256 pinned"
  - "[ ] CP5. The run: workflow type business_model (prepare, compute, report), inputs frozen by artifact id and SHA-256, a known 0.00 USD ceiling for a CALCULATED type, results stored as artifacts; the ledger subject business_model for a submitted revision"
  - "[ ] CP6. The API: /studies/{id}/model content, revisions, submit, runs, results; study-scoped, refused for any other kind; the client page's count"
  - "[ ] CP7. The web platform: the area \"Modely\" beside Výzkumy (Q8), list and create with a model type, the study frame with Data, Předpoklady, Model, Výsledky and Zpráva; Data (each dataset's contract state) and Předpoklady (every input with unit and provenance, edited in place) generic over the type's schema"
  - "[ ] CP8. The report frame and grades: PrintGrade CALCULATED (výpočet) and its admission beside admit_numeric_claims, the platform template frame (question, type blocks, inputs table, method, sources), report kind business_model approvable through approve_report, three chart kinds (absolute stacked bar, tornado, line with marked points) in the model and the renderer"
  - "[ ] CP9. The Lead: lead_artifacts rows for the five stages, a model read tool, MaterialRule.BUSINESS_MODEL (Class A), per-change proposal operations generic over a type's declared operations, accepted through the Lead's edit path"
  - "[ ] CM1. Cost scenarios, its types: Driver (input, or a × b / a ÷ b), the four cost-line kinds (FIXED, VARIABLE, STEP, CAPITAL annuity), at most five scenarios; registered as model type cost_scenarios v1"
  - "[ ] CM2. Cost scenarios, compute: totals per year, exact break-even on one driver in a stated range (where the driver enters through one monotone form, else refused by name), one-way sensitivity, cumulative cost over N stated years with capital in year 0 and the payback year; unknown propagated by name; the warehouse golden fixture"
  - "[ ] CM3. Cost scenarios, the Model stage: lines, drivers and scenarios edited in place (input standard I1-I11)"
  - "[ ] CM4. Cost scenarios, charts: scenario comparison stacked by line, cumulative cost with the payback year, break-even lines with the crossing marked, the sensitivity tornado; the same drawing on Výsledky and in the DOCX"
  - "[ ] CM5. Cost scenarios, report blocks and method text"
  - "[ ] CM6. The journey: the warehouse case as fictional inputs (24 months), AC-16 over HTTP and a browser journey from upload to the approved report, ESTIMATED kept out of the client report until registered; zero paid calls without the Lead"
  - "[ ] CM7. NPV of each scenario's costs and discounted payback at a stated discount rate (CALCULATED)"
  - "[ ] CP10. The ESTIMATED grade on the platform: interval or percentiles, seed and method version pinned, results stored, the rerun-equals-bytes test; the method register (internal until A. Bahbouh's entry approves); the Metodika module 'Nákladové modely' holding every default as written (final, Q13), versioned, pinned per run"
  - "[ ] CR1. Data checks before use: reconciliation across files and against stated totals, period coverage and currency, robust outlier flags, seasonality only with two cycles; accepted by the person as part of the binding; missing stays missing"
  - "[ ] CR2. Ranges: low / base / high and a guarantor on every input; exact range of every total by vertex enumeration over closed STEP cells (each end with that cell's step count, one-sided limits included), only where code verifies every input enters through one monotone form (else range_not_exact, cap 2^14); dominance, and the inputs that flip the ranking with their flip values"
  - "[ ] CR3. Monte Carlo (ESTIMATED): PERT by default, triangular or a stated distribution; declared rank correlations by Iman-Conover, a non-PSD matrix refused; PCG64 under the run's seed; five-stream convergence check; P(A cheaper than B) with its standard error and the 90 % interval of the difference"
  - "[ ] CR4. Global sensitivity (ESTIMATED): Sobol first-order and total (Jansen, bootstrap intervals) for independent inputs, partial rank correlation when inputs are correlated, beside the tornado"
  - "[ ] CR5. Backtested forecasts (ESTIMATED): naive, seasonal naive, drift and Holt-Winters additive; rolling-origin backtest scoring the candidate and the baseline on the same held-out origins; a forecast whose held-out MAE is not strictly below the baseline's not used, said in words; MASE and MAPE reported, not the gate; its errors become the volume input's range and distribution"
  - "[ ] CR6. Value of information (ESTIMATED): EVPPI per input from the Monte Carlo draws; an input marked measurable by a survey with material EVPPI offers the Výzkum path, a research study proposed with its question, nothing started"
  - "[ ] CR7. The decision rule (Z3): the person's own rule, stated before the data (option, quantity, threshold, optionally the confidence needed), judged as written; the default confidence 0.90 / 0.10 only when the rule names none, said on the page; no rule, no recommendation (R2); dominance beside it; internal until the Monte Carlo method is registered"
  - "[ ] CR8. The method on screen: the data-check review on Data; on Výsledky the range table, dominance and flip inputs, the probability and zone, the difference's distribution, the Sobol or rank-correlation bars, the forecast with its backtest, the value-of-information table; every ESTIMATED value marked odhad (interní) until registered"
  - "[ ] CR9. The method in the report: blocks for each layer, a method appendix naming each method's id, version and register status, the client report carrying only CALCULATED and registered ESTIMATED numbers"
  - "[ ] CS1. The properties table: objects are the run's scenarios; properties are chosen results (CALCULATED or ESTIMATED refs) and stated scenario attributes, each with declared scale extremes and direction"
  - "[ ] CS2. The objects × properties fuzzy matrix (new FuzzySource): Euclidean, Manhattan or correlation similarity after scale extremes, converted to 0-1 by the registered rule; checked against SOMECS Input fig. 6"
  - "[ ] CS3. Layout and fit: the H-Model candidate or the -5 layout (A. Bahbouh's choice), Spearman accuracy, significance through sociomapping-engine 2c; results stored, the rerun equal in bytes"
  - "[ ] CS4. The WIND height on the layout: one chosen property, the surface from sociomapping-engine 4b with the registered exponent, radius and grid; ESTIMATED, internal until registered"
  - "[ ] CS5. The map on Výsledky and in the report: the WIND view from sociomapping-engine 11, the property chosen as height, fit and its significance, odhad (interní) until registered; beside a linked survey's respondent map, never merged"
  - "[ ] CR10. The method validation pack: each method against its published reference as tests (Ishigami, PERT moments, Iman-Conover, MASE, a closed-form EVPPI), and the report the method owner signs"
---
# The MVP build: the quantitative-model platform and its first model type, cost scenarios

Written 2026-10-29. The rules are [ADR 0044](../../docs/architecture/adr/0044-quantitative-model-studies.md)
(Proposed). The other families are designed in
[quantitative-families](quantitative-families.md), and none is scheduled.

**The product owner's decisions** (2026-10-29, in the PM coordinator's chat, relayed):
- Scope: "Scenario cost model". Placement: "A new study type beside Výzkumy".
- Q3: "Two kinds, linked later". Q6: "Add a fourth build session". Q7: "Yes, labelled výpočet".
- The families: "we need to do a whole set of accounting, business and operations research upgrade";
  all four ticked; "Design all now, build later", building **only the cost-scenario model** for the MVP.
- 2026-10-30, 08:41 UTC, on the six method layers: "we need to make it as robust and methodologically
  impresive in the MVP" (ADR 0044 decision 14). All six are in the MVP, `ESTIMATED` included; every
  `ESTIMATED` method is internal until its register entry approves it.
- 2026-10-30, 08:44 UTC, Q9: "aram owns statistical models". A. Bahbouh signs every `ESTIMATED` method's
  register entry (§ The methodology owner's sign-off sheet).
- By 09:15 UTC, on the decision page:
  - Q9: "Aram signs these too". He also signs the `CALCULATED` definitions; there is no other owner.
  - Q10: "Yes, once Aram registers it". An `ESTIMATED` number reaches a client report labelled *odhad*
    with its interval and method version, only after his register entry; until then the client report
    carries `CALCULATED` numbers and ranges only.
  - Q13: "Final as written". The defaults are the method, kept in the versioned Metodika module.
  - "Add a fifth session": the method chunks are its lane (§ Lanes).
  - Z3: the coordinator's correction (CR7).
- Q1, Q2, Q4 and Q5 at this plan's recommendations:
  - Q1: CZK, one currency per model.
  - Q2: (a) + (c), the year plus a cumulative N-year view with the payback year.
  - Q4: the four line kinds, at most five scenarios, the four results.
  - Q5: the warehouse fixture and a proposed AC-16. The fixture now holds 24 months of orders and
    invoices, so seasonality can be tested and a forecast backtested.

**Owner:** the fourth build session (Q6), as its own track. It is named when it starts. Anchors are
`@ 861e19fc` unless stated.

## The question it answers

*Should the client expand its warehouse to order and store larger quantities, rather than keep paying
the logistics costs it pays now?*

The client uploads a year of orders, its freight invoices and a quote for 2,000 m² more storage. The
researcher states the rent per m², the capital cost and the order size. AIA shows:
- each option's yearly cost, line by line;
- the order volume at which they break even;
- the cumulative cost over the years stated, and the year the warehouse pays back;
- what happens to all of it if freight rises 10 %.

Every number says where it came from: *z dat klienta*, *předpoklad*, *veřejný zdroj* or *výpočet*.

## What exists, and what is missing

- **Study kinds.** Two kinds (`domain/scope.py:457-466`), held by
  `CheckConstraint("kind in ('RESEARCH','SIMULATION')")` (`infrastructure/tables.py:645`). The working
  content refuses a non-research study (`infrastructure/study_workspace_repository.py:142-145`).
- **Client data.** A client's dataset is kept and previewed (`domain/client_datasets.py`), never
  computed on. The path to an admitted client number is `client-data-in-analysis` chunks 1, 2, 2a, 3,
  3a, 3b, 5 and 10. Chunks 2, 3, 3a and 3b move to W2 by Q6 (Doc follow-up); the others stay in W3.
- **Metrics.** They are respondent-shaped (`domain/evidence/metrics.py:32-52`). MQ-18 adds count, amount
  and rate (`client-data-in-analysis#5`, `evidence-integrity#8b`).
- **The Lead.** Its read tools (`lead-orchestration#LO8d`) and per-change accept (`working-copy-edit-ops`)
  are the mechanisms CP9 extends.
- **Reports.** The report document model, its chart kinds (`domain/report/model.py:264-271`) and its
  approval (`application/report_approval.py:77, 95, 139`) are what CP8 extends.

## Chunks and estimates

Session-days are one session working one day, review and CI included. A range means the work is UI, or
depends on another plan's shape.

| Chunk | Estimate | Needs | Proposed wave |
|---|---|---|---|
| CP1 | 1.5 | ADR 0044 | W2 |
| CP2 | 2-2.5 | CP1 | W2 |
| CP3 | 2-2.5 | CP1; one migration in the serial lane; `working-copy-edit-ops#WCE2` | W2 |
| CP4 | 1.5 | CP1; `client-data-in-analysis#1`, `#2`, `#3`, `#3a`, `#3b`, `#5` | W3 |
| CP5 | 1.5-2 | CP2, CP3; the ledger owner (`mvp-master-plan` I17) | W2 |
| CP6 | 2 | CP3, CP5 | W2 |
| CP7 | 3.5-4.5 | CP6; `client-data-in-analysis#10` for Data's contract | W3 |
| CP8 | 3-3.5 | CP5; `report-delivery#RD3`, `#RD5a`; `client-data-in-analysis#5` | W3 |
| CP9 | 3-4 | CP6; `lead-orchestration#LO8d`, `#LO21`, `#LO12a`; `working-copy-edit-ops#WCE6` | W4 |
| CM1 | 1 | CP2 | W2 |
| CM2 | 3-3.5 | CM1 | W2 |
| CM3 | 2-2.5 | CM1, CP7 | W3 |
| CM4 | 1-1.5 | CM2, CP8 | W3 |
| CM5 | 1-1.5 | CM2, CP8 | W3 |
| CM6 | 2 | every chunk above | W4 |
| CM7 | 1.5-2 | CM2 | W2 |
| CP10 | 4-5 | CP2; the methodology store (ADR 0023) | W2 |
| CR1 | 3.5-4.5 | CP4; `client-data-in-analysis#2a`, `#3a` | W3 |
| CR2 | 3-4 | CM2 | W2 |
| CR3 | 5-6 | CP10, CR2 | W2 |
| CR4 | 3-4 | CR3 | W3 |
| CR5 | 5-7 | CP10, CP4, CR1 | W3 |
| CR6 | 3-4 | CR3; CP6 for the Výzkum offer | W3 |
| CR7 | 1-1.5 | CR3, CR4, CR6; the Brief's rule (Zadání Z3, R2) | W3 |
| CR8 | 4-5 | CP7, CR1-CR7 | W3/W4 |
| CR9 | 2-2.5 | CP8, CR1-CR7 | W4 |
| CR10 | 2 | CR3-CR6 | W3/W4 |
| CS1 | 1.5-2 | CM2, CR3 (P(cheapest)), CP2 | W3 |
| CS2 | 2-3 | CS1; `sociomapping-engine#1a` (built) | W3 |
| CS3 | 2-3 | CS2; `sociomapping-engine#2a` (built), `#2c` (significance) | W3 |
| CS4 | 3-4.5 | CS3; `sociomapping-engine#4b` (its WIND part built here, ticked there) | W3 |
| CS5 | 3-4.5 | CS4, CP7, CP8; `sociomapping-engine#11` (its WIND view built here) | W4 |
| **Platform core (CP1-CP10)** | **24-29** | | |
| **Cost scenarios (CM1-CM7)** | **11.5-14** | | |
| **The robust method (CR1-CR10)** | **31.5-40.5** | | |
| **The model's WIND map (CS1-CS5)** | **11.5-17** | | |
| **MVP total** | **78.5-100.5** | | |

**The platform's added cost.** The cost model built alone was estimated at 27-31 session-days (types,
compute with the cumulative view, kind, bindings, run, API, stages, charts, Lead, report, journey). The
platform shape adds about **3-5**: the type contract and registry (CP2), stages and Lead operations
generic over a type's schema (CP7, CP9), and the report frame apart from the type's blocks (CP8). Every
later model type saves about that much (`quantitative-families`).

**The robust method's added cost** (2026-10-30) is about **37-47.5**: CP10, CM7 and CR1-CR10. Before it,
the MVP total was 30-36.

**The WIND map's added cost** (2026-10-30) is about **11.5-17** (CS1-CS5): S5 takes 8.5-12.5 of it
(CS1-CS4) and S4 3-4.5 (CS5).

### Lanes (a fifth session approved, 2026-10-30)

| Lane | Chunks | Session-days | Starts |
|---|---|---|---|
| **S4**: platform, data, UI, Lead, report, cost type | CP1-CP9, CM1-CM7, CR1, CR8, CR9, CS5 | 44-54.5 | W2, on the merged ADR and plan |
| **S5**: the method, pure domain code | CP10, CR2-CR7, CR10, CS1-CS4 | 34.5-46 | W2, once S4's CP1 and CP2 have merged; CR2 also after CM2 |

S5's chunks need no UI, data, Lead or route. They read CP1's types and CP2's contract, CM2's compute
(for CR2) and CP4's bindings (for CR5's data). S4 consumes S5's results in CR8 and CR9. Both lanes run
in parallel from W2, so the track takes about **9-11 weeks** (8-10 before the WIND map,
2026-10-30). CR5 is the only S5 chunk that waits on
client data (CP4).

**What moves on the critical path.**
- `client-data-in-analysis#2a` (the quality report) joins #2, #3, #3a and #3b in W2: CR1 builds on it.
- A. Bahbouh's sign-off (Q9, CR10) gates every `ESTIMATED` number in a client report, not the
  build. Without it AC-16's client deliverable carries `CALCULATED` numbers and layer 2's ranges, and the
  probability, zone, sensitivity, forecast and value of information stay internal.
- The fixture needs 24 months of data (Q5).

**What the dates hang on.** Not this plan's effort, but `client-data-in-analysis` #2, #3, #3a and #3b,
which Q6 moves to W2, and #5 and #10, which stay in W3. Without them a model runs on `stated` and
`public_source` inputs only. CP1-CP3, CP5, CP6, CM1 and CM2 need no client data and start in W2.

**Not chosen, recorded for later:** the core plus four or five `CALCULATED` types in the MVP (cost
scenarios, budget vs actual, ratios, NPV/IRR/payback, EOQ), at about 38-48 session-days.

### CP1. Platform types (`domain/business_model/model.py`)

- Frozen Pydantic types with `Decimal` values and no I/O: `Amount(value, currency, per)`,
  `Rate(value, currency, per_unit)`, `Count(value, unit, per)`, `Ratio`, `Duration`.
- `Input(name, quantity_kind, provenance, overrides)`.
- `Provenance`:
  - `ClientDataset(source_id, reading_sha256, contract_id, contract_version, column, aggregation,
    filter, period)`;
  - `Stated(by, at, revision, note)`;
  - `PublicSource(knowledge_item_id, revision, quote)`;
  - `ResearchResult(...)`, declared and refused `provenance_not_available` until built.
- `Scenario`: the baseline plus at most four.
- `ModelRevision`: type id, type version, elements, inputs, scenarios, its canonical JSON and SHA-256.
- Refusals, each by name: `unit_mismatch`, `currency_mismatch` (CZK by default, Q1), `no_provenance`,
  `too_many_scenarios`.

**Tests:** `packages/aia_core/tests/test_business_model_types.py`:
- each refusal by name;
- the hash is stable under key order;
- a `research_result` input is refused until built.

### CP2. The model-type contract (`domain/business_model/registry.py`)

- `ModelTypeSpec`: id, version, `elements_schema`, the inputs it reads with their required units, a
  pure `compute`, its results schema with each output's grade, its charts (result refs to chart kinds),
  its report blocks, and its proposal operations.
- The registry is a closed set, like `workflow_templates`. A run pins the type's id and version.
- The determinism harness: any type's compute run twice on the same revision gives identical bytes; a
  `CALCULATED` output never depends on the clock or on randomness.

**Tests:** a type missing any field is refused at registration; the harness fails a type that reads the
clock.

### CP3. The kind and the working copy

- `StudyKind.BUSINESS_MODEL`, and one migration that extends the CHECK constraint and nothing else.
- The model's working content lives on the study's owned working project, as a research study's does
  (ADR 0018), with revision-checked saves (a stale save is 409) and every write logged as its writer's
  (ADR 0029).
- Whether it reuses `study_workspaces` and `workspace_edit_ops` with a content-kind column, or has its
  own two tables, is decided here after reading `working-copy-edit-ops`'s state. The rule (one writer,
  stale refused, every write logged) is not open.
- The Model Revision is immutable and names its working revision.

**Tests:**
- a round trip;
- a stale save refused;
- cross-organization 404;
- every research route refuses a model study by name, and every model route refuses a research study;
- the migration up and down.

### CP4. Data bindings (`domain/business_model/bindings.py`)

- A `ClientDataset` input is the sum, count or mean of a contract-named column, over a stated filter on
  contract-named columns and a stated period. It is computed over the analysis copy
  (`client-data-in-analysis#3`, read through `#3b`'s accessor) and admitted `CLIENT_REPORTED` with
  MQ-18's "not a sample" support.
- Each of these is refused by name: an unnamed column; a contract that was not accepted; a contract
  version other than the one the input names.

**Tests:**
- a year of fictional freight invoices summed into a driver;
- an unnamed column refused;
- a new contract version makes a pinned input stale, and the revision cannot be submitted until a person
  picks again.

### CP5. The run

- `domain/workflow_templates.py` gains `business_model`, with steps `business_model_prepare`, `_compute`
  and `_report`. The executors are in `apps/executors/src/aia_executors/business_model.py`.
- Prepare freezes the revision and each dataset input by artifact id and SHA-256. Compute calls the
  pinned type's `compute` and stores the results artifact. Report composes the document (CP8).
- The ceiling of a `CALCULATED` type is a known 0.00 USD (`domain/run_cost.py`), never unknown. There is
  no hold, no charge and no confirmation.
- Ledger subject `business_model` (a migration on `approval_decisions.subject_type`): a submitted
  revision, with the hash of its input list.

**Tests:**
- the run end to end under the real worker loop on `stated` inputs;
- a retry with unchanged inputs reuses the results;
- the run never reads the working copy;
- the usage ledger holds no row.

### CP6. The API

- `apps/api/src/aia_api/routers/business_model.py`:
  - `GET/PUT /studies/{id}/model/content`;
  - `POST …/model/revisions` (submit, under `APPROVE_GATE`, the ledger row in the same transaction);
  - `POST/GET …/model/runs[/{run_id}]` and `GET …/runs/{run_id}/results`.
- Study-scoped. Any other kind is refused `not_business_model`.
- `GET /clients/{id}` counts `business_models`.

**Tests:** the cross-organization sweep; each refusal; OpenAPI regenerated.

### CP7. The web platform

- The area "Modely" beside Výzkumy (Q8, 2026-10-30; `lib/app-routes.ts`); list, and create with a model type.
- The study frame and its five stages.
- **Data:** each dataset with its contract state. A dataset without an accepted contract is shown and
  cannot feed an input.
- **Předpoklady:** every input with its unit, currency, provenance and label, edited in place with the
  input standard's controls, generic over the type's schema.
- **Výsledky** and **Zpráva:** frames the type fills.
- Unknown is said as *neznámé*, never 0.

**Tests:** Vitest for `lib/business-model.ts`, and component tests per stage.

### CP8. The report frame, the grade and the chart kinds

- `PrintGrade.CALCULATED` (*výpočet*), and `admit_model_results` in `domain/evidence/admission.py`: an
  output is admitted only when every input it reads is admitted client-reported or an accepted input of
  the run's revision, and none is unknown.
- The frame template in `domain/report/templates.py`: the question, the type's blocks, the inputs table
  with provenance and label, the method, and the sources manifest.
- Report kind `business_model` in `application/report_approval.py`; DOCX and PDF as for the internal
  report. The client surface prints *výpočet* (Q7).
- Three `ChartKind`s and their renderers (`infrastructure/report_docx/charts.py:361`): an absolute
  stacked bar, a tornado, and a line with marked points.

**Tests:**
- every printed number is a ref;
- an unknown total prints *neznámé* with its missing input;
- a ref resolves to its output and inputs;
- an output over an unaccepted input is refused;
- each chart's series are exactly the artifact's refs, and an unknown value is a gap;
- the DOCX lint and `make web_design` pass.

### CP9. The Lead

- `domain/lead_artifacts.py` rows for the five stages.
- The `model_read` tool in LO8d's `ToolRegistry`.
- `MaterialRule.BUSINESS_MODEL` (Class A) in `domain/material_rules.py`.
- Proposals as per-change operations, generic over the type's declared operations, plus a dataset
  mapping. Each is accepted or dismissed under `APPROVE_GATE` as a `lead_edit`.
- The Lead states no number that is not in its context, and computes none. On a route not approved for
  Class A, its turn parks with LO12a's refusal.

**Tests:**
- a proposed value becomes an input only on accept;
- a dismissed proposal changes nothing;
- a Class-C-only route parks the turn by name under `enforce`;
- the recorded Lead wire proposes the warehouse's lines from a fictional invoice summary.

### CM1. Cost scenarios: types (`domain/business_model/types/cost_scenarios.py`)

- `Driver`: an input, or `a × b` / `a ÷ b`.
- `CostLine`:
  - `FIXED`: per period;
  - `VARIABLE`: rate × driver;
  - `STEP`: per block × ceil(driver ÷ block);
  - `CAPITAL`: amount, life, rate; annuity.
- Registered as `cost_scenarios` v1. It also refuses `driver_cycle`.

**Tests:** every refusal; the type passes CP2's registration and harness.

### CM2. Cost scenarios: compute

- `totals`: per line and in sum, per year.
- `break_even(a, b, driver, low, high)`: every crossing in the range.
  - **When it is exact:** the driver enters the difference through one monotone form (itself, its
    reciprocal, an annuity or a discount factor). The difference is then α + β·g(driver) on each
    `STEP` cell, with that cell's step count held fixed. It is solved in closed form for the driver and
    its reciprocal, and by bisection to a stated `Decimal` tolerance for a rate.
  - A jump at a breakpoint that changes the sign is reported as a crossing at the breakpoint, with its
    side named.
  - `curve(a, b, driver, low, high)`: the chart's points, each a stored `CALCULATED` ref. They are the
    exact totals at a fixed grid of 64 evenly spaced points, plus both one-sided values at every `STEP`
    breakpoint, plus every crossing. A curve through a reciprocal or rate form is therefore drawn as the
    function is, and its crossings lie on the drawn lines.
  - **When it is refused:** a driver entering in two forms (x and 1/x) is refused
    `break_even_not_exact`, naming it.
  - Otherwise the result is `none_in_range` or `identical`.
- `sensitivity(inputs, step, pair)`: ±step (10 % unless stated), ordered by the swing.
- `cumulative(years)`: the capital paid in year 0 and the yearly costs after it, with no growth and no
  discounting, and the payback year at which the cumulative curves cross (`none_within_horizon`
  otherwise).

All `CALCULATED`, in `Decimal`.

**Tests:**
- the warehouse case as a hand-computed golden fixture
  (`packages/aia_core/tests/fixtures/business_model/cost_scenarios/warehouse.json`, fictional figures,
  computed by hand in its README);
- break-even on a `STEP` boundary; two crossings; none in range;
- an unknown freight rate makes every total, break-even, sensitivity row and payback year that reads it
  unknown, and nothing zero;
- the annuity against a published worked example;
- totals are additive over lines, as a property test.

### CM3. Cost scenarios: the Model stage

Lines, drivers and scenarios are edited in place. A scenario is its overrides of the baseline, shown
against it.

**Tests:** component tests, and the journey (CM6).

### CM4. Cost scenarios: charts

- The comparison: each scenario's yearly total stacked by line.
- Cumulative cost over the stated years, with the payback year marked.
- Break-even: two totals across the range, drawn through CM2's `curve` points (the fixed grid, both
  sides of every `STEP` jump, every crossing), the jumps drawn as jumps and each crossing marked.
- The tornado.

**Tests:**
- the series are the artifact's refs, every point an exact evaluation;
- for A(x) = 1/x against B(x) = 0.5 on [1, 4], the drawn curves cross at x = 2, the marked crossing,
  not at x = 3, where the straight endpoint line would put it;
- a `STEP` jump is drawn with both one-sided values.

### CM5. Cost scenarios: report blocks

The scenarios, the lines, the totals, the cumulative view and payback, break-even and sensitivity, and
the method in words (the four line kinds, the annuity, what is not modelled).

**Tests:** the blocks validate; the method text names every line kind used.

### CM7. NPV and discounted payback

Each scenario's yearly costs over the stated horizon, the capital in year 0, discounted at a stated rate
(an input with a range like any other); the NPV of each scenario and of the difference; discounted
payback (`none_within_horizon` otherwise). `CALCULATED`, in `Decimal`.
**Tests:** NPV against a published worked example; a zero rate equals the undiscounted cumulative view.

### CP10. The `ESTIMATED` grade, the method register and the defaults

ADR 0044 decisions 4, 6 and 14.
- `PrintGrade.ESTIMATED` (*odhad*). An `ESTIMATED` output carries its interval or percentiles, the run's
  seed (drawn once at start, stored in its identity), the generator (`numpy` PCG64) and the method's id
  and version.
- Results are stored, never recomputed on read.
- `domain/business_model/method_register.py` works as `domain/sociomap_register.py`: a method absent
  from it is internal only. The client surface refuses an `ESTIMATED` ref whose method the register does
  not approve; the internal surface prints it *odhad (interní)*.
- A Metodika module, "Nákladové modely" (ADR 0023 store, as 0037-Q4's client-data module): every default
  of decision 14 (PERT λ, N, the convergence tolerances and cap, the vertex cap, the backtest window,
  the outlier threshold, the zone thresholds), versioned, pinned per run. The code's preset is marked
  final as written (Q13, "Final as written"); a change is a new version, which a run pins. A. Bahbouh's
  register entry, not the module, is what lets an `ESTIMATED` number reach a client (Q10).

**Tests:**
- a rerun reproduces the results bytes;
- an `ESTIMATED` output without a seed or interval is refused at admission;
- an unregistered method's output is refused on the client surface and printed internal;
- a run pins the module version, and a new version is a new run.

### CR1. Data checks before use (`domain/business_model/checks.py`)

- Reconciliation: pairs of inputs the person declares as the same quantity in two files (for example
  shipments in orders and in invoices), and stated control totals. The difference is shown in its unit
  and as a share.
- Coverage: every period of the stated span present once. Currency: every amount column in the model's
  currency.
- Outliers: modified z (median, MAD) above the module's threshold, flagged, kept or excluded by the
  person on record.
- Seasonality: tested only with two full cycles (seasonal-index range against the module's threshold);
  otherwise "nelze ověřit".
- The check report is versioned and hashed. The person accepts it with the binding; an input reading a
  missing value is unknown.

**Tests:** a fictional pair of files that disagree by 3 % is shown as 3 %; a missing month is named; an
outlier is flagged and kept unless excluded; 12 months say seasonality cannot be tested.

### CR2. Ranges, dominance and flip inputs

- Each input carries low, base and high, and a guarantor (a member, or a client contact recorded by a
  member); low ≤ base ≤ high or refused by name.
- The exact range of every total and of each difference, by vertex enumeration over the low/high grid
  cut into closed `STEP` cells. Each end of a cell is evaluated with that cell's step count, so a cell's
  left end gives the one-sided limit. An extreme reached only at an open end is reported as a limit.
- Dominance needs A strictly below B at every vertex of every closed cell. A difference whose infimum
  is 0 at an open end is not certified.
- **The exactness check runs first.** Every input must enter the compared quantity through one and the
  same monotone form (itself, its reciprocal, an annuity or a discount factor), at most once per term,
  and a `STEP` driver must be a single input. The quantity is then multilinear in the transformed
  inputs within each `STEP` cell.
- Otherwise the result is `range_not_exact`, naming the input, with no dominance claim and the Monte
  Carlo as the range view. Above the vertex cap it is `range_too_large`.
- Dominance ("A je levnější ve všech kombinacích"), or the inputs that flip the ranking, each with its
  flip value, and the vertices where B wins.

**Tests:** a hand-computed three-input case; B = x + 1/x against a fixed 2.25 on x in [0.5, 2] refused `range_not_exact` (its minimum 2 lies inside the range), never certified as dominated; a `STEP` breakpoint inside a range found; a flip value equal
to the one-way break-even; the cap refused by name; A(x) = 9.05 + ceil(x) against B(x) = 10 + x on
[0.1, 1.1] not certified as dominated (B is cheaper just above x = 1, which the cell (1, 1.1] with step 2
shows).

### CR3. Monte Carlo (`domain/business_model/montecarlo.py`)

- PERT (λ from the module) by default; triangular, uniform or truncated normal when a person states it.
- Declared rank correlations imposed by Iman-Conover. A non-PSD matrix is refused (`correlation_not_psd`)
  and the nearest valid matrix offered as a proposal.
- N from the module, PCG64 under the run's seed, element-wise arithmetic only.
- Convergence: five spawned streams, P(A cheaper) within the module's tolerance and the difference's
  5th/95th percentiles within theirs; otherwise N doubles to the cap, then `not_converged`.
- Outputs: P(A cheaper) with its standard error, the difference's 90 % interval, each scenario's
  percentiles, stored with the seed.

**Tests:** PERT moments analytic; Iman-Conover hits its target rank correlation within tolerance; the
same seed gives the same bytes, a different seed a result within tolerance; a dominated case gives P = 1; two scenarios with equal base costs and different ranges converge under the non-zero percentile tolerance.

### CR4. Global sensitivity

- Independent inputs: Sobol first-order and total indices (Jansen estimator, N(k+2) evaluations), with
  bootstrap intervals.
- Correlated inputs: partial rank correlation coefficients; Sobol not shown, the page says why.

**Tests:** the Ishigami function's analytic indices recovered within tolerance; a correlated model shows
PRCC and no Sobol.

### CR5. Backtested forecasts

- Methods: naive, seasonal naive, drift, Holt-Winters additive (parameters by a pinned deterministic
  optimiser, `scipy.optimize` with a fixed start).
- Rolling-origin backtest over the module's window. The candidate and its baseline (the seasonal naive;
  the naive without two cycles) are forecast from the same origins and scored on the same held-out
  periods.
- The gate: a candidate whose held-out MAE is not strictly below the baseline's is not used, the
  baseline is, and the page says so.
- MASE (in-sample naive scale) and MAPE (only without zero actuals) are reported, never the gate.
- The kept method's backtest errors give the volume input's range and its distribution in CR3.

**Tests:**
- MASE on a published example;
- a series where Holt-Winters loses to the naive keeps the naive and says so;
- a series whose held-out volatility differs from its training volatility, where MASE < 1 and the
  candidate still loses on the held-out origins, keeps the baseline; the fit is byte-identical on a rerun.

### CR6. Value of information

- EVPPI per input by binning CR3's draws on that input (bins from the module), in the model's currency.
- An input a person marks `measurable_by: survey` with EVPPI above the module's share of the expected
  difference offers "Ověřit výzkumem": a research study of the same client proposed with its question,
  linked later (Q3). Nothing starts or is charged until a person starts it there.

**Tests:** a two-option toy's closed-form EVPPI recovered; an input with no effect has EVPPI near 0; the
offer creates nothing until accepted.

### CR7. The decision rule (Z3)

ADR 0044 decision 14, from the Zadání design (board Z3; R2 makes the threshold required).
- `DecisionRule` is an element of the Model Revision: the option, the quantity (the difference in yearly
  cost or in NPV), the comparison, the threshold, and optionally the confidence needed ("zvolíme A, když
  P(A levnější) ≥ 0,8"). The time it was first stated and each change are kept in the operation log.
- The verdict is judged against the stated rule: doporučeno A, doporučeno B (its mirror), or
  nerozhodnuto, which names CR4's and CR6's top inputs.
- No confidence stated: the module's default (0.90 / 0.10) applies, and the page says the
  default is in use.
- No rule: no recommendation. P and the dominance are shown, with "rozhodovací pravidlo chybí" (R2).
- A rule stated or changed after a run's results were shown is marked so.
- CR2's dominance is printed beside the verdict. The verdict is internal until CR3's method is
  registered; the client report then carries CR2's range alone.

**Tests:**
- a stated 0.8 judged at 0.8, not 0.90;
- the default is used and said when no confidence is stated;
- no rule gives no "doporučeno";
- a rule changed after results is marked;
- each verdict at its boundary;
- the client surface refuses the verdict while unregistered.

### CR8. The method on screen

Data's check review; Výsledky's range table, dominance and flips, probability and zone, the difference's
histogram, the sensitivity bars, the forecast with its backtest and baseline, the value-of-information
table. Every `ESTIMATED` value marked *odhad (interní)* until registered. Charts from stored refs only
(two more chart kinds: a histogram and an interval band).
**Tests:** component tests per view; the journey (CM6) at four widths.

### CR9. The method in the report

A block per layer and a method appendix: each method's id, version, defaults as pinned and register
status. The client report carries `CALCULATED` numbers and registered `ESTIMATED` ones only, and says
which layers are internal.
**Tests:** an unregistered method's numbers absent from the client document and present, marked, in the
internal one.

### CS1-CS5. The model's own map (ADR 0044 decision 12, 2026-10-30)

The product owner, 09:52 UTC: the model's map is "the "wind map" in the current sociomapping", built
from the model and not from respondents. It reuses `sociomapping-engine` where that plan already has
the part, and builds only what is new: the objects × properties fuzzy matrix, the properties table
from a model's run, and WIND for this input.

- **CS1. The properties table** (`domain/business_model/map_table.py`).
  - Objects: the run's scenarios. With fewer than the registered minimum, the result is
    `too_few_objects`.
  - Properties: results chosen by a person (NPV of cost, its interval width, yearly cost, capex,
    P(cheapest)) as `CALCULATED` or `ESTIMATED` refs, plus stated scenario attributes (delivery time,
    customer loss, flexibility) with their provenance.
  - Each property has declared scale extremes and a direction (lower-is-better negated, as SOMECS
    Input does).
  - An unknown cell is unknown, never 0. SOMECS's 0 fill is not adopted (engine M5).

  **Tests:** every cell resolves to a ref; an unknown cell refuses the map by name; a property without
  extremes is refused.
- **CS2. The objects × properties fuzzy matrix** (`domain/sociomap/fuzzy.py`, a new
  `FuzzySource.OBJECT_PROPERTIES`).
  - Euclidean, Manhattan or correlation similarity of the scaled profiles. Correlation only above the
    registered number of properties (SOMECS: "correlation for more than 15 properties").
  - The conversion to a 0-1 relation follows the registered rule. Until then it is
    `MethodologyUndetermined`, by name, as the module does for every undocumented SOMECS rule.

  **Tests:** SOMECS Input fig. 6's example reproduced; the three measures on a hand-computed case; a
  property's direction reverses its contribution.
- **CS3. Layout and fit.**
  - The H-Model candidate (`hmodel_candidate.py`) or the `-5` layout (`signed_off_layout.py`, 4
    objects and up), as A. Bahbouh registers.
  - Spearman accuracy (`hmodel.py`), and its significance through `sociomapping-engine#2c` once it
    lands. Until then the fit is shown with "významnost nezjištěna", never presumed significant.
  - Stored, and reproduced in bytes on a rerun under the same pins.

  **Tests:** the fig. 22 accuracy reproduced on this input's path; the rerun is equal in bytes; with
  three objects the `-5` layout is refused by name.
- **CS4. The WIND height.**
  - One chosen property as each object's height; the surface by weighted inverse distance with the
    registered exponent, radius and grid. It is built as `sociomapping-engine#4b`'s WIND part, there
    for every WIND map, and ticked there.
  - `ESTIMATED`, internal until registered.
  - AUDIT-F12's envelope terrain for respondent maps is not touched.
  - The evidence register's `SOMECS-M2` entry gains this map as what it applies to, with its
    implementation and validation, in the same PR. `AUDIT-F12` still supersedes it for respondent maps.

  **Tests:** at each object the surface equals its height; between objects it lies within their
  heights; E7's three-element case once the export exists; the respondent map's terrain is unchanged
  in bytes (a regression test on a stored `-5` map).
- **CS5. On screen and in the report.**
  - Výsledky's map view, built as `sociomapping-engine#11`'s WIND view and ticked there: the top view
    first, 3D on request, the property chosen as height, the fit and its significance, every value a
    ref, *odhad (interní)* until registered.
  - The report figure through the existing figure renderer.
  - A linked survey's respondent map shown beside it, never merged.

  **Tests:** component tests; the figure's values are the artifact's refs; the client document carries
  no map until registered.

### CR10. The method validation pack

Every reference check of CR3-CR6 as a test, and a generated report of the results, the defaults and
the known limits. This is what the method owner reads to sign each register entry and the module's
defaults (Q9), item by item as the sign-off sheet below lists them.

### The methodology owner's sign-off sheet (A. Bahbouh, Q9)

What he is asked to sign, one register entry per method. Each entry covers:
- (i) the method is appropriate for its use;
- (ii) CR10's reference checks passed;
- (iii) the client label, *odhad*, with its interval and method version.

The defaults below are final as written (Q13, "Final as written"). They are listed so he signs the method
as it runs. Changing one, if he asks, is a new version of the Metodika module, never an edit. Until his
entry, a method's numbers stay internal (Q10).

| # | Method (id) | What it does | Defaults to sign | Reference check (CR10) |
|---|---|---|---|---|
| S1 | Data checks, statistical part (`aia-cost-checks-1`) | flags outliers and tests seasonality before data feeds an input | outliers: modified z (median, MAD) > 3.5, flagged and never dropped; seasonality: tested only with ≥ 2 full cycles of 12 months, seasonal-index range > 10 % of the mean level; reconciliation: any difference shown, flagged above 1 % | Iglewicz-Hoaglin's published example; a synthetic series with a known seasonal amplitude |
| S2 | Input distributions (`aia-cost-mc-1`, part) | turns low / base / high into a distribution | PERT with λ = 4 by default; triangular, uniform or normal truncated at low and high only when a person states it, on record | PERT's analytic mean and variance |
| S3 | Correlations (`aia-cost-mc-1`, part) | imposes declared dependence between inputs | pairwise rank (Spearman) correlations declared by a person; Iman-Conover; a matrix that is not positive semi-definite refused, the nearest valid one offered as a proposal | achieved rank correlation within ±0.02 of its target at N = 20,000 |
| S4 | Monte Carlo (`aia-cost-mc-1`) | P(A cheaper than B) and the difference's interval | N = 20,000; `numpy` PCG64 under the run's seed; 5 spawned streams; converged when P agrees within ±0.01, and the 5th and 95th percentiles of the difference within the larger of 1 % of the absolute base difference and 0.1 % of the larger scenario's base total; otherwise N doubles to at most 160,000, then `not_converged`; reported: P with its Monte Carlo standard error, the 90 % interval (5th-95th percentile) | a dominated case gives P = 1; a symmetric case gives P = 0.5 within its standard error; equal base costs converge |
| S5 | Global sensitivity (`aia-cost-gsa-1`) | which inputs drive the difference's variance | independent inputs: Sobol first-order and total indices, Jansen estimator, base N = 8,192 (N(k+2) evaluations), 1,000 bootstrap resamples, 90 % intervals; correlated inputs: partial rank correlation coefficients, Sobol not shown | the Ishigami function (a = 7, b = 0.1), analytic indices recovered within ±0.02 |
| S6 | Forecasting and backtesting (`aia-cost-forecast-1`) | projects a volume over the horizon, tested on held-out months | methods: naive, seasonal naive (m = 12), drift, Holt-Winters additive (α, β, γ in [0, 1] by L-BFGS-B on in-sample squared error from a fixed start of 0.3 / 0.1 / 0.1); rolling origin over the last 6 months with ≥ 3 origins; MASE scaled by the in-sample seasonal naive (the naive below 24 months); the candidate and the baseline scored on the same held-out origins, the candidate used only if its held-out MAE is strictly below the baseline's, otherwise the baseline used and said; MASE (in-sample naive scale) and MAPE (no zero actual) reported, not the gate; interval from the backtest errors' 5th-95th percentiles | MASE on Hyndman's published worked example; a series where Holt-Winters must lose to the naive |
| S7 | Value of information (`aia-cost-evppi-1`) | what knowing an input exactly could save | EVPPI by binning the Monte Carlo draws on the input into 20 equal-frequency bins; material when ≥ 5 % of the absolute expected difference, which offers the Výzkum path | a two-option toy with a closed-form EVPPI; an input with no effect gives ≈ 0 |
| S8 | The decision rule's default confidence, Z3 (`aia-cost-decision-1`) | judges a person's stated rule against P(A cheaper) | the person's stated confidence decides; when the rule states none, the default is 0.90 for A and 0.10 for B, said on the page; no rule, no recommendation | a stated 0.8 judged at 0.8; the default used and said; each verdict at its boundary |
| S9 | The model's WIND map (`aia-cost-map-1`) | places the options by their property profiles, with one property as height | the similarity measure (Euclidean, Manhattan, or correlation above 15 properties) and its conversion to 0-1; scale extremes and direction declared per property; the layout (the H-Model candidate, or the `-5` layout from 4 objects); the fit as Spearman accuracy, and its significance null; the WIND exponent, radius and grid; the minimum number of objects | SOMECS Input fig. 6; SOMECS fig. 22 accuracy; E7's three-element WIND when it exists; the respondent map's terrain unchanged |

**The `CALCULATED` definitions he also signs** (Q9, "Aram signs these too"), one definitions page each,
checked against published worked examples:

| # | Definition | What he signs | Reference check |
|---|---|---|---|
| D1 | Cost line kinds and the annuity (CM1) | fixed, variable (rate × driver), step (per block × ceil(driver ÷ block)), capital (annuity at a stated rate over a stated life); drivers as input, a × b or a ÷ b | the annuity against a published worked example |
| D2 | Break-even, cumulative cost and payback (CM2) | exact crossings where the driver enters through one monotone form, refused by name otherwise; cumulative cost with capital in year 0, no growth or discounting; payback where the cumulative curves cross | a hand-computed fixture |
| D3 | NPV and discounted payback (CM7) | each scenario's costs over the stated horizon, discounted at a stated rate, capital in year 0 | a published NPV worked example |
| D4 | Data checks, deterministic part (CR1) | reconciliation of declared pairs and stated totals, period coverage, the currency check, missing stays missing | a fictional pair of files differing by a known share |
| D5 | Ranges and dominance (CR2) | low ≤ base ≤ high with a guarantor; the exactness check (each input through one monotone form); vertex enumeration over closed `STEP` cells, one-sided limits included; dominance and flip values | a hand-computed three-input case |

**Later, in the same form:** statements and the chart-of-accounts mapping (ACC1-ACC2), ratios (ACC3),
variance (ACC4), the IRR root rule (FIN2), price elasticity (FIN5) and fitted safety stock (OR1).

**Not his to sign** (engineering, not method): the vertex cap of 2^14 for the exact range (CR2),
`Decimal` arithmetic, storage and reruns.



**Tests:** the pack is generated in CI and fails when a reference check fails.

### CM6. The journey

- Fictional inputs under `tests/acceptance/inputs/business_model/warehouse/` (orders, freight invoices,
  a storage quote), pinned by SHA-256.
- `tests/acceptance/test_business_model.py` over HTTP: the contract accepted, the assumptions stated,
  the revision submitted, the run, the report approved, and every number traced. This is AC-16's tier A
  proof.
- The browser journey `tools/ui_workbench/business_model_journey.mjs` at 1440/1100/768/390 px.
- No paid calls without the Lead; with the recorded Lead, its turns are at USD 0.

## Depends on / feeds

- **Needs:**
  - `client-data-in-analysis#1`, `#2`, `#2a`, `#3`, `#3a`, `#3b`, `#5`, `#10`;
  - `lead-orchestration#LO8d`, `#LO21`, `#LO12a`;
  - `working-copy-edit-ops#WCE2`, `#WCE6`;
  - `report-delivery#RD3`, `#RD5a`;
  - `client-knowledge-lifecycle` K3: a `public_source` input names a typed SOURCE revision.
- **Feeds:** AC-16 (proposed), and every family in `quantitative-families`.

## Risks

| Risk | Consequence | What holds it |
|---|---|---|
| `client-data-in-analysis` slips | the demo runs on stated inputs only | the W2 chunks need no client data; Q6 pulls #2-3b into W2 |
| The Lead's production route is not approved for Class A | the Lead parks on every model turn | ADR 0044 decision 9 says so; it is a runbook step for the operator |
| Families creep into the MVP | the date moves | "Design all now, build later"; each family is a later decision |

## Findings

None yet.

## Doc follow-up

The docs PR applies these after this PR merges; they touch shared files, which this PR does not edit.

- **`.planning/plans/mvp-master-plan.md`:**
  - §3.1: register `cost-model-study` as a core plan, owned by the fourth build session (Q6), gates I-3
    (CP1-CP8, CP10, CM1-CM5, CM7, CR1-CR7, CR10) and I-4 (CP9, CR8, CR9, CM6). Note: "Nigel 2026-10-29: Scenario cost model in the MVP;
    Q3, Q6, Q7 answered; families designed, build later".
  - §3.3: register `quantitative-families` as after the MVP, by decision.
  - The scope baseline: under In, a row *Quantitative models: the platform and cost scenarios* →
    `cost-model-study#CP1` … `#CM6`; under Out, "every other quantitative family, designed in
    `quantitative-families`".
  - §11.1: Q8 "Modely", Q11 "all of thesw" (`quantitative-families` § Lanes), Q12 "Yes, labelled
    modelováno" (2026-10-30).
  - §5: a new interface, "a client dataset's admitted aggregate as a model input"
    (`client-data-in-analysis#4` with `cost-model-study#CP4`; S3 owns the contract).
  - §2 / `mvp-development-plan.md` §2: a fourth build session, S4, and a fifth, S5 (approved 2026-10-30,
    "Add a fifth session"), owning this track in the lanes of § Lanes; about 9-11 weeks.
  - §11.1 (settled, 2026-10-30): Q9, A. Bahbouh owns every `ESTIMATED` method and signs the
    `CALCULATED` definitions ("aram owns statistical models", "Aram signs these too"); Q10, "Yes, once
    Aram registers it"; Q13, "Final as written"; a fifth session. Nothing of this plan is left in §11.4.
  - `mvp-methodology-packet.md`: the sign-off sheet S1-S8 and D1-D5 as A. Bahbouh's items, in the
    packet's MQ form.
- **`.planning/mvp-execution-contracts.md`:**
  - a row per chunk, with this plan's waves;
  - `client-data-in-analysis#2`, `#3`, `#3a`, `#3b` moved from W3 to W2 (Q6), and `#2a` with them
    (CR1 builds on it, 2026-10-30). The basis for each: "Nigel
    2026-10-29, Q6: pulled into W2 for the fourth session's track". Check that #2a (after #3a) and #10
    still order correctly;
  - every `quantitative-families` chunk UNSCHEDULED, "after the MVP by decision, 2026-10-29".
- **`.planning/plans/sociomapping-engine.md`** (another feature's plan, so it is not edited here):
  - 4b and 11 note that `cost-model-study` CS4 and CS5 build their WIND parts for the Model path's
    objects × properties map, and tick them when they land;
  - M4 notes that A. Bahbouh's register entry (S9) can settle WIND's parameters for that map ahead of
    E7.
- **`.planning/overview.md`:** MVP-1 becomes "All scenarios out, except quantitative models: the cost
  scenarios type in the MVP, other families designed (Nigel, 2026-10-29; ADR 0044)". The MVP roadmap
  gains the track.
- **`docs/architecture/adr/README.md`:** row 0044, Proposed — 2026-10-29.
- **`docs/architecture/adr/0027-client-data-is-client-reported-evidence.md`:** a note under Consequences
  that "no scenario inputs (MVP-1)" now reads "except a quantitative model's inputs, ADR 0044
  decision 7".
- **`docs/migration/mvp-acceptance.md` and `parity-matrix.json` `mvp_acceptance`:** AC-16, "A cost model
  from a client's dataset and stated assumptions to an approved report, every number traced to its
  input" (Q5). Its tier A test is CM6.
- **`CLAUDE.md` § The map:** `domain/business_model/`, `routers/business_model.py`,
  `executors/business_model.py` and the web area, each named by its own chunk's Doc follow-up as built.
- **Metodika:** a module "Nákladové modely" in the methodology catalogue (ADR 0023), its preset the
  defaults as written (Q13), each `ESTIMATED` method's client status from A. Bahbouh's register entry
  (CP10); `docs/architecture/` gains a page for the cost
  model's method once CR10's pack exists.
- **`ARCHITECTURE.md` §4:** a third study kind; the `CALCULATED` and `ESTIMATED` grades beside the
  origins.
