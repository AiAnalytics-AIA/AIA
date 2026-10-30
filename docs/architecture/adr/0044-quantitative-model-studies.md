# ADR 0044 — Quantitative models are a study kind of their own: typed models as data, pluggable model types computed by code, every input accepted by a person

**Status:** Proposed — 2026-10-29. Written on the product owner's decisions of 2026-10-29, in the PM
coordinator's chat, relayed to this session:
- ~21:30-21:45 UTC: "ok well we need to incorporate this into the mvp". He chose Scope "Scenario cost
  model", Placement "A new study type beside Výzkumy" and Timing "Plan it first, then decide".
- ~22:05 UTC: Q3 "Two kinds, linked later"; Q6 "Add a fourth build session"; Q7 "Yes, labelled výpočet".
  On the shape: "we need to do a whole set of accounting, business and operations research upgrade".
- ~22:06 UTC: all four families (accounting, business case and finance, operations research, market
  sizing), and "Design all now, build later": the platform and every family designed now, **only the
  cost-scenario model type built for the MVP**.
- 2026-10-30, 08:41 UTC, on six method layers the coordinator proposed for the cost model: "we need to
  make it as robust and methodologically impresive in the MVP". All six are in the MVP, the `ESTIMATED`
  ones included (decision 14).
- 2026-10-30, 08:44 UTC, Q9: "aram owns statistical models". A. Bahbouh, the methodology owner, owns
  every `ESTIMATED` method (decision 14).
- 2026-10-30, by 09:15 UTC, on the decision page:
  - Q9: "Aram signs these too". He also signs the `CALCULATED` accounting and finance rules; there is no
    separate owner.
  - Q10: "Yes, once Aram registers it".
  - Q13: "Final as written". The defaults are the method, not provisional.
  - "Add a fifth session".
  - Z3 as the coordinator corrected it (decision 14).
- 2026-10-30, 09:52 UTC: the model's map is "the "wind map" in the current sociomapping" (decision 12,
  rewritten).
- 2026-10-30, by 09:25 UTC: Q8 "Modely"; Q11 "all of thesw", every family after the MVP, side by side;
  Q12 "Yes, labelled modelováno".

**Builds on:**
- [ADR 0015](0015-client-first-product-interface.md): a study is one object for scope, approvals and
  artifacts, and the workflow beneath it differs by kind.
- [ADR 0019](0019-two-roles-and-human-ai-gates.md): a person decides what the AI produced.
- [ADR 0021](0021-deep-research-purpose-target-lineage.md): external research is context, never
  research truth.
- [ADR 0023](0023-methodology-is-data-the-methodologist-owns.md): a method is versioned data a run pins.
- [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md): panel answers are modelled
  evidence.
- [ADR 0026](0026-research-lead-proposes-a-person-decides.md): the Lead proposes, through its read tools
  since the amendment of 2026-10-28.
- [ADR 0027](0027-client-data-is-client-reported-evidence.md) and
  [ADR 0037](0037-client-data-evidence-policy.md): a client dataset is client-reported evidence under its
  accepted data contract.
- [ADR 0029](0029-working-copy-operation-log-merge-and-per-change-accept.md): the working copy and
  per-change accept.
- The report document model (`domain/report/`).

**Amends** MVP-1 ("All scenarios out", `.planning/overview.md:575 @ 861e19fc`) for quantitative models
only. Simulation and every what-if over respondents stay out.
**Changes** the closed set of study kinds and adds to the evidence ledger's grades.
**Leaves unchanged** research studies, their runs, the Sociomap, the population and every existing
artifact.
**Date:** 2026-10-29.
**Plans:**
- [cost-model-study](../../../.planning/plans/cost-model-study.md): the MVP build, the platform core
  plus the cost-scenario model type.
- [quantitative-families](../../../.planning/plans/quantitative-families.md): every other family,
  designed and not scheduled.

## Context

The product owner asked whether AIA can answer this: a company wants to analyse its costs, and whether
expanding its warehouse to order and store larger quantities beats paying the logistics costs it pays
now. AIA cannot today. It is an opinion and market research product: a study's numbers come from
respondents, and its only deterministic numerical paths are the aggregate, the Sociomap and the
Simulation core.

The agreed example: the client uploads a year of orders, its freight invoices and a quote for 2,000 m²
more storage. The researcher states the rent per m², the capital cost and the order size. AIA shows
three things:
- each option's yearly cost;
- the volume at which the options break even;
- what happens if freight rises 10 %.

The owner then widened the scope to accounting, business-case and finance, operations research and
market sizing. All are to be designed now; the cost model alone is built for the MVP.

What the code has, and does not:

- **Two study kinds, one study object.**
  - `StudyKind` is `RESEARCH` or `SIMULATION` (`packages/aia_core/src/aia_core/domain/scope.py:457-466
    @ 861e19fc`), held by a CHECK constraint, `kind in ('RESEARCH','SIMULATION')`
    (`infrastructure/tables.py:645 @ 861e19fc`).
  - A study is created with a kind (`infrastructure/scope_repository.py:973 @ 861e19fc`).
  - The working content refuses any study that is not research, with `not_research`
    (`infrastructure/study_workspace_repository.py:142-145 @ 861e19fc`).
  - The client page counts studies by kind (`apps/api/src/aia_api/routers/workspace.py:972-973
    @ 861e19fc`), and the web routes a simulation to its own area (`apps/web/src/lib/app-routes.ts:10,
    19-20 @ 861e19fc`). Simulace is hidden for the MVP (MVP-31).
- **A client's dataset is kept and previewed, not computed on.**
  - Sources up to 25 MB are kept and read, and the stored reading is cut at 250,000 characters
    (`domain/client_sources.py:53-55 @ 861e19fc`).
  - The preview shows five samples per column and flags personal columns
    (`domain/client_datasets.py:52, 70 @ 861e19fc`).
  - The path from a dataset to an admitted number is ADR 0027/0037's, accepted 2026-10-29, and is not
    built. There is no `CLIENT_REPORTED` origin (`domain/fieldwork.py:59, 88 @ 861e19fc`), and no data
    contract, full-grid reader or analysis copy (`client-data-in-analysis` chunks 1-3b).
- **The evidence path is respondent-shaped.**
  - `MetricKind` holds mean, top-2-box, n, effective n and percent
    (`domain/evidence/metrics.py:32-52 @ 861e19fc`). MQ-18 adds count, amount and rate (ADR 0027,
    amendment of 2026-10-29).
  - An `EvidenceRow` is a float with support, fields and an origin
    (`domain/evidence/admission.py:64-89 @ 861e19fc`), and only `admit_numeric_claims` mints an
    `AdmittedClaim` (`:182-205`).
  - A report prints ledger refs only (`domain/report/model.py:10-14 @ 861e19fc`), and the ledger is
    built from admitted claims alone (`domain/report/evidence.py:74-80 @ 861e19fc`).
- **A deterministic core beside the respondents exists once.** The Simulation core computes "numbers
  from a frozen world model, never from a model call" (`domain/simulation/__init__.py:1-15
  @ 861e19fc`). Its shape is followed here (frozen and validated input, reject-not-clip, pure
  functions); its code is not reused.
- **Methods are already versioned data.** Metodika's modules are versioned, activated per organization
  and pinned by a run (ADR 0023). The Sociomap's client status comes from a register entry
  (`domain/sociomap_register.py:70-80 @ 861e19fc`).
- **Data classes.**
  - Row-level client data is Class A; aggregates derived from it are Class B
    (`domain/residency.py:61-67 @ 861e19fc`). By rule a client source is Class A
    (`domain/material_rules.py:68-102 @ 861e19fc`).
  - Develop's model route may be approved for every class (`deploy/develop/README.md:544-545
    @ 861e19fc`), and develop's class gates are advisory (`deploy/develop/docker-compose.yml:36
    @ 861e19fc`).
  - Deep Research's search routes take Class C (`apps/executors/src/aia_executors/deep_research_live.py:30,
    116 @ 861e19fc`); Brave also takes design-derived Class B (master plan Q20).
- **The approval ledger is a closed set of subjects** (`domain/approval_ledger.py:40-65 @ 861e19fc`).

## Decisions

### 1. One study kind, `BUSINESS_MODEL`, in an area named "Modely" (Q8)

`StudyKind` gains `BUSINESS_MODEL`. A study of this kind is a study like the others: one client, one
scope, one budget, the same permissions (ADR 0019's one role), the same ledger and artifacts.

It holds **one model of one model type**. The first type is cost scenarios ("Nákladové scénáře"), and
the others come from the four families (decision 13). The study sits in the client workspace as an area
of its own beside Výzkumy.

Every model type uses the same five stages:
- **Data:** the client's datasets and their contracts.
- **Předpoklady:** every input, with its unit and provenance.
- **Model:** the type's own editor.
- **Výsledky:** results and charts.
- **Zpráva:** the report.

Nothing reads such a study as a research study. Every `kind != RESEARCH` refusal above stays, and
refuses it by name. One kind for every family is the point: the families share scope, data, provenance,
grades, the Lead and the report. A kind per family would build those five times.

### 2. The model is data: typed, unit-bearing, versioned

A model is a frozen, validated document. The stages edit a working copy; a person submits a **Model
Revision**, which is immutable, names the working revision it came from, and is what a run computes.

The platform's shared types:
- **Quantity.** `Amount(value, currency, per)`, `Rate(value, currency, per_unit)`, `Count(value, unit,
  per)`, `Ratio`, `Duration`. Values are `Decimal`, never floats. One currency per model (Q1 answered:
  CZK by default), no currency conversion, no unit conversion. A quantity whose unit does not fit where
  it is used is refused by name, never coerced.
- **Input.** A named quantity a model type reads, with one provenance (decision 3) and an optional
  per-scenario override.
- **Scenario.** A baseline and at most four alternatives. A scenario is a set of input overrides and,
  where the type allows, the elements it includes.
- **The type's own elements** (cost lines, accounts, cash flows, constraints): declared by the model
  type (decision 5), validated by it, carried inside the revision.

### 3. Every input has exactly one provenance

| Provenance | What it names | Its label on the page | In the MVP |
|---|---|---|---|
| `client_dataset` | the source, its reading's SHA-256, the accepted data contract's id and version, the column, the aggregation (sum, count, mean over a stated filter and period) | *z dat klienta* (ADR 0027 decision 6) | yes |
| `stated` | the person who stated it, when, the revision, an optional note | *předpoklad* | yes |
| `public_source` | a SOURCE item in the client's knowledge (Deep Research captured it and a person checked it, "Ověřeno, přidat zdroj", or a person added it), its revision, the quote the number is in | *veřejný zdroj* | yes |
| `research_result` | one admitted claim of an approved research run of the same client: run id, evidence ref, the approved artifact's id and SHA-256 | the claim's own grade (*modelováno* for AI respondents, ADR 0024; *z dat klienta* for a client's own survey) | no: designed for market sizing and the survey link |

The rules:
- An input with no provenance is refused.
- **A number a model proposed is never an input until a person accepts it.** Once accepted, it is that
  person's input under the provenance it cites, and the proposal is recorded on the ledger row.
- No computation reads a model's text.

### 4. Two grades, both built in the MVP

- **`CALCULATED`** (*výpočet*) is arithmetic and closed-form formulas over accepted inputs, in `Decimal`.
  A number is admitted `CALCULATED` only when every input it reads is admitted or accepted and none is
  unknown. It carries no interval and makes no sample claim. **It is client-facing**, labelled
  *výpočet* (Q7).
- **`ESTIMATED`** (*odhad*) covers a number a statistical method produced: fitted, forecast, simulated
  or solved over estimated parameters. It always carries:
  - an interval, or its distribution's stated percentiles;
  - the seed;
  - the method's id and version, which the run pins.

  It reaches a client only once its method's register entry approves it, as the Sociomap's map does
  (Q10). Before that it is internal, printed *odhad (interní)*. It is built in the MVP for the cost
  model's method (decision 14).
- **Unknown is never zero.** An input with no value makes every result that reads it unknown, names the
  input, and prints *neznámé*. A line, account or flow is never dropped to make a total.

### 5. The model-type contract: what the platform owns and what a type owns

A model type is a **registered, versioned spec**, as a Metodika module is: `ModelTypeSpec` in
`domain/business_model/registry.py`. A run pins the type's id and version, and a new version is a new
run.

| The platform owns | A model type owns |
|---|---|
| Quantity, currency, period; inputs and their four provenances; scenarios | its elements' types and validation (`elements_schema`) |
| the working copy, the Model Revision, the operation log, per-change accept | its stage editor on Model, from its schema |
| data bindings: a dataset column, aggregated under its accepted contract | which inputs may come from data, and their required units |
| the run: freeze, compute step, store, a 0.00 USD ceiling when no model is called | `compute(revision) -> Results`: pure, declared `CALCULATED` or `ESTIMATED` per output |
| the two grades and their admission into the ledger | its results schema; which outputs are which grade |
| the chart kinds and the renderer | which charts it draws, from which result refs |
| the report frame (question, inputs table with provenance, method, sources manifest) and its approval | its report blocks and its method text |
| the Lead's read tool, material rule and per-change proposal operations | the proposal operations its elements accept |
| determinism tests (decision 6) | its golden fixtures, hand-computed or from a published worked example |
| the register of methods (`ESTIMATED` types) | its method's register entry, by its method owner |

A model type adds no route, table, ledger subject or grade. If it needs one, the platform gains it by
an amendment of this ADR.

### 6. Determinism

- `CALCULATED`: `Decimal` throughout. No clock, no randomness, no I/O. The same revision gives the same
  results bytes.
- `ESTIMATED`, once built:
  - The run records its seed, drawn once at start and stored in its identity, and the generator
    algorithm (`numpy` PCG64).
  - Solvers and libraries are pinned by version in the method's spec. LP uses HiGHS through `scipy`,
    which is already pinned at 1.18.
  - Results are **stored** and never recomputed on read.
  - A rerun of the same revision under the same pins must reproduce the same results bytes. A test per
    type holds it, on the platform the CI runs.
  - A method whose result differs across platforms says so in its register entry, and its client
    status waits for it.
- A solver's non-answer (infeasible, unbounded, not converged, several or no IRR roots) is a **named
  result**, never a number.

### 7. Client data reaches a model only as ADR 0027/0037's admitted, client-reported numbers

- A `client_dataset` input is a deterministic aggregate over the dataset's **analysis copy**, under its
  **accepted data contract** (`client-data-in-analysis` chunks 2, 3, 3a, 3b; moved to W2 by Q6):
  - only the columns the contract names;
  - personal columns never copied;
  - every row read, or the dataset refused by name.
- It is admitted `CLIENT_REPORTED` with MQ-18's support. Records are "not a sample": the exact figure,
  no interval, no tests.
- The run pins the contract version and the copy's SHA-256.
- Rows never leave AIA's storage and are never sent to a model.
- A family that needs more than a column's meaning extends the contract, never the analysis copy.
  Accounting, for example, needs a chart-of-accounts mapping (`quantitative-families` ACC1).

### 8. A person accepts every number; the Lead only proposes

- A person's own edit is their write, logged as theirs (ADR 0029).
- **The Lead may propose** elements, inputs and dataset mappings ("this column is the freight amount;
  sum it per year"), from what it reads through its read tools. A new read covers the model's own state.
- Each proposal is accepted or dismissed per change under `APPROVE_GATE` (`lead_edit`).
- The Lead **never computes a number**: every number in its reply must be in its context
  (`lead_contract`).
- Submitting a Model Revision is one ledger row, under a new subject `business_model`. It names the
  revision and the hash of its input list, and records that the person accepted that set of inputs.
- A run computes only a submitted revision.

### 9. Data class and residency

A model's content is client financial information: **Class A**, by a new rule
`MaterialRule.BUSINESS_MODEL`. Its dataset rows are Class A and never sent anywhere.

- **The Lead** receives a model's content only on a route approved for Class A.
  - On develop it passes: the operator approves A, B and C, and the gates are advisory.
  - In production under `enforce`, a route not approved for Class A **parks the turn** with the
    route-class refusal, which names who fixes it (`lead-orchestration#LO12a`). It never sends a
    reduced context silently.
- **Deep Research receives nothing from a model.** A query written from Class A material inherits
  Class A and is refused (ADR 0017). On develop's advisory gates such a refusal would be a recorded
  pass, so no model type starts Deep Research from its content.
- A public number enters as `public_source`, citing a SOURCE item a person added. Market sizing's own
  Deep Research run is designed in decision 13: queries from a person's Class B focus, never from the
  model, under an ADR 0021 amendment.

### 10. The report and its charts

- A model's report is a `ReportDocument` from the platform's frame: the question as the person framed
  it, the type's blocks, an inputs table (every input, its unit, provenance and label), the method in
  words, and the section-source manifest (`domain/report/sources.py`).
- Numbers are ledger refs, admitted by one new function beside `admit_numeric_claims` in
  `domain/evidence/admission.py`; the issuer stays module-private.
- Each ref resolves to the output that produced it and to that output's inputs.
- The report is approved through `approve_report` as exactly the version shown, as report kind
  `business_model`. The client report carries `CALCULATED` numbers labelled *výpočet*.
- Charts are drawn from the results artifact alone. Every plotted value is a ledger ref, never a
  model's text, and the renderer recomputes nothing. An unknown value is a gap with its reason, never
  a zero bar.
- The chart vocabulary (`domain/report/model.py:264-271 @ 861e19fc`, drawn by
  `infrastructure/report_docx/charts.py:361`) gains three kinds, so the screen and the DOCX draw the
  same thing: an absolute stacked bar, a tornado, and a line with marked points.

### 11. Money and the ledger

- A run of a `CALCULATED` type calls no model. Its **ceiling is a known 0.00 USD**, not unknown: no
  hold, no charge, no confirmation.
- It is still a recorded run: workflow type `business_model`, with steps prepare, compute and report.
  Its inputs are frozen by artifact id and SHA-256, and its results are artifacts.
- The Lead's turns cost money and are held in the study's wallet as in a research study.
- Ledger rows:
  - `business_model` (new): a submitted revision;
  - `lead_edit`: a proposal decided;
  - `data_contract`: already admitted;
  - `artifact`: the report's approval.

### 12. The model's own map: a SOMECS objects × properties map with a WIND height (2026-10-30)

**The product owner, 09:52 UTC, 2026-10-30:** "In this case (in the model), the sociomap isn't
supposed to be based on respondents, this is the "wind map" in the current sociomapping". It
overrules this decision's first version, "a Sociomap is never computed from a model".

**What it is.** The published Sociomapping has a second input besides respondents. A fuzzy matrix can
be built "from an objects × properties table by Euclidean, Manhattan or correlation similarity after
declared scale extremes" (SOMECS Input, fig. 6). The H-Model places the objects, and its accuracy is
the Spearman correlation between the distances and the fuzzy matrix. A **WIND map** (Weighted INverse
Distance) "keeps the same horizontal positions and interpolates one object variable as height"
(`.planning/plans/sociomapping-engine.md:55-79 @ 61230f5e`).

**The Model path's map:**
- **The objects** are the decision options: the model's scenarios (A, A phased, B, B renegotiated,
  C, C + express for cities, a hybrid …).
- **The properties** are the model's results and the scenarios' stated attributes: NPV of cost and
  its interval, yearly cost, capex, P(cheapest), delivery time, customer loss, flexibility. Each
  property has declared scale extremes and a direction (lower-is-better entered negative, as SOMECS
  does).
- **Every cell is a ref:** a `CALCULATED` or `ESTIMATED` result of the run, or a `stated` attribute with
  its provenance. Nothing is typed into the map.
- **Placement:** the objects are placed by the similarity of their property profiles.
- **Height:** the WIND height is one chosen property, for example P(cheapest) or NPV.
- **No respondents are involved.** Where a survey is linked (Q3, later), its approved respondent map
  sits beside this one, as before. The two are never merged: a preference never changes a cost, and a
  cost never changes a rating.

**What it reuses and what is new.**
- **Reused from `sociomapping-engine`:**
  - the fuzzy matrix contract (`domain/sociomap/fuzzy.py`);
  - the H-Model accuracy (`hmodel.py`) and its significance (engine chunk 2c);
  - the experimental H-Model candidate (`hmodel_candidate.py`), or the `-5` layout
    (`signed_off_layout.py`, from 4 objects);
  - the WIND surface (engine chunk 4b) and its view (engine chunk 11).
- **New here:**
  - the objects × properties fuzzy matrix, a new `FuzzySource`;
  - the adapter that builds the properties table from a model's run;
  - the method's register entry.

**Its register entry is A. Bahbouh's** (Q9). He signs the method as a whole (sign-off S9):
- the similarity measure and its conversion to 0-1;
- the scale extremes and direction rule;
- the layout (the H-Model, or the `-5` layout reused);
- the fit (Spearman accuracy) and its significance null;
- the WIND exponent, radius and grid;
- the minimum number of objects.

The map is `ESTIMATED` (its layout is a fit). It is **internal until he registers it**, like every
`ESTIMATED` method (Q10). Before then, Výsledky and the internal report show it marked *odhad
(interní)*; the client report does not.

**Its relation to AUDIT-F12.**
- In the Sociomap evidence register, SOMECS-M2 (WIND) is OPEN: its exponent, radius and grid are
  unstated. For AIA's respondent object map, AUDIT-F12 supersedes it: the terrain is the max-envelope
  of each object's hill, the owner's rule of 2026-10-07 (`docs/migration/sociomapping-evidence-register.json`,
  entries `SOMECS-M2` and `AUDIT-F12` @ 61230f5e).
- **That stays as it is.** Respondent maps (`aia-sociomap-5`, and every older method a stored run
  keeps) are unaffected: same terrain, same register, same client status.
- The WIND surface applies only to the Model path's objects × properties map. It is a separate input
  and a separate method, with its own register entry. Its parameters come from A. Bahbouh's entry, or
  from export E7 when it exists (engine question M4).

### 13. The families: cost scenarios in the MVP, the rest designed and built after it

Each family is a set of model types on decision 5's contract; the families plan holds its design,
chunks and estimates.

- **Cost scenarios (MVP).** Cost lines of four kinds:
  - fixed: per period;
  - variable: a rate × a driver;
  - step: a cost per block × the number of blocks the driver needs;
  - capital: annualised at a stated rate over a stated life.

  Drivers are an input, or a × b / a ÷ b of two drivers. It computes, all `CALCULATED`:
  - totals per year;
  - exact break-even on one driver, within a stated range, where the driver enters each total through
    one monotone form (decision 14, layer 2's exactness rule); otherwise refused by name;
  - one-way sensitivity;
  - cumulative cost over N stated years with capital paid in year 0, and the payback year (Q2 (a)+(c));
  - NPV of each scenario's costs and discounted payback, at a stated discount rate;
  - and the robust method of decision 14 (data checks, ranges, Monte Carlo, global sensitivity,
    backtested forecasts, value of information, the decision rule).
- **Accounting.**
  - Statements (profit and loss, balance sheet) built from a trial balance or ledger export through the
    contract's chart-of-accounts mapping.
  - A closed, defined list of ratios.
  - Budget against actual, with price, volume and mix variance.

  All `CALCULATED`.
- **Business case and finance.**
  - NPV, payback and discounted payback (built for cost scenarios in the MVP, extended here), and IRR,
    which follows a stated root rule:
    the one root in the stated range, or a named refusal for several or none.
  - Scenarios and sensitivity reused from cost scenarios.
  - Pricing break-even.

  All `CALCULATED`. Price elasticity fitted from the client's price and volume data is `ESTIMATED`.
- **Operations research.**
  - EOQ and reorder point, closed forms (`CALCULATED`).
  - Safety stock: `CALCULATED` from a stated demand deviation, `ESTIMATED` when the deviation is fitted
    from data.
  - Linear optimisation: HiGHS pinned. It reports the optimum, the binding constraints and their shadow
    prices in words; infeasible or unbounded is a named result.
  - Demand forecasting and Monte Carlo: built for cost scenarios in the MVP (decision 14), extended
    here to any model type's inputs.
- **Market sizing.**
  - TAM, SAM and SOM top-down, as a chain of inputs (`stated`, `public_source`).
  - Bottom-up from a survey's admitted share × a population count (`research_result`).
  - Each step keeps its own label, so the chain prints the weakest of its labels. **Panel answers enter
    only as `research_result`, modelled evidence under ADR 0024**, labelled *modelováno*. They reach a
    client only within ADR 0024's client-report lift, labelled "modelováno: AI respondenti z
    populace" with its scope, under the same rule as every other modelled number, and never as a
    "measured" size (Q12, "Yes, labelled modelováno").
  - **Deep Research findings enter only as `public_source`:** external context, never respondent
    evidence (ADR 0021).
  - A market-sizing Deep Research run is a third purpose. It needs an ADR 0021 amendment, and its
    queries are written from a person's Class B focus, never from the model.

### 14. The cost model's method: robust, in the MVP (2026-10-30)

Six layers on top of decision 13's arithmetic. Each layer is a method with its own id and version. Its
defaults live in a Metodika module of their own, "Nákladové modely", versioned and pinned per run under
ADR 0023.

**Who owns the methods** (the product owner, Q9, 2026-10-30: "aram owns statistical models", then "Aram
signs these too"):
- A. Bahbouh, the methodology owner, owns every `ESTIMATED` method: Monte Carlo, global sensitivity,
  forecasting and backtesting, the value of information, the decision zones judged on a probability,
  the statistical data checks (outliers, seasonality), and every later fitted or simulated method
  (price elasticity, fitted safety stock).
- Each such method needs **its own register entry from him** before any of its numbers reaches a client
  report (Q10, "Yes, once Aram registers it"). Until then its numbers are internal, shown on Výsledky
  and in the internal report as *odhad (interní)*. Once registered, each number is labelled *odhad* with
  its interval and method version.
- **The defaults are final** (Q13, "Final as written"): distribution, draws, streams, convergence
  tolerances and cap, backtest window, baseline rule and thresholds are the method as written here, not
  provisional. They live in the versioned Metodika module, so a change is a new version a run pins. The
  register entry still gates the client report.
- What he signs, method by method, is `cost-model-study` § The methodology owner's sign-off sheet.
- He also signs the `CALCULATED` accounting and finance definitions (Q9, "Aram signs these too"): the
  cost line kinds and the annuity, NPV and discounted payback, the data checks' reconciliation rules, the
  range method, and later statements, ratios, the IRR root rule and the chart-of-accounts mapping.
  There is no separate accounting or operations owner.

1. **Data checks before use** (`CALCULATED`). Before a dataset feeds an input, code checks it, and the
   person accepts the result as part of the input's binding. The data contract's quality report
   (`client-data-in-analysis#2a`) is the base. The checks:
   - **Reconciliation.** Files that state the same thing must agree: orders against freight invoices,
     for example shipments counted in both, and every total against a control total the person states.
     A difference is shown in its unit and as a share; it is never absorbed.
   - **Periods and currency.** Every period of the stated span is present once; a gap or an overlap is
     named. Every amount column is in the model's currency.
   - **Outliers.** A robust score (median and MAD, modified z above 3.5) flags values.
     A flagged value is shown, never dropped; the person keeps it or excludes it, on record.
   - **Seasonality.** Tested only with at least two full cycles. With fewer, it says that seasonality
     cannot be tested; it is never presumed absent.
   - **A missing value stays missing**, and every input that reads it is unknown.
2. **Ranges, not points** (`CALCULATED`). Every accepted input has a low, base and high value and a
   guarantor: the person who stands behind it, a member or a client contact recorded by a member.
   - A `client_dataset` input's base is the data's value; its low and high are stated by a person.
   - Every scenario's total, and each difference between two scenarios, is reported over the whole box
     of ranges by vertex enumeration over the low/high grid, refined at every `STEP` breakpoint.
   - **When vertices are exact.** Code checks, before it claims an exact range, that in the compared
     quantity every input:
     - enters every term through one and the same monotone form: as itself, as its reciprocal (a
       ÷ b driver, its range strictly positive), as the annuity factor of a rate, or as a discount factor;
     - appears at most once in any term;
     - when it drives a `STEP` line, is a single input, not a derived driver.

     Then, in the transformed inputs, the quantity is multilinear within each `STEP` cell, and the
     box maps to a box, so its extremes are at the vertices.
   - **When they are not.** An input that enters the same quantity in two forms makes vertices
     insufficient: for example x in one line and 1/x in another, where x + 1/x is lowest inside the
     range. The exact range and dominance are then refused by name (`range_not_exact`, naming the
     input). The Monte Carlo is the range view, and the page says why.
   - Above a cap of 2^14 vertices the exact range is likewise refused by name.
   - **Dominance:** "A je levnější ve všech kombinacích" when the exactness check holds and A's total is
     below B's at every vertex.
     Otherwise the inputs that flip the ranking are named, each with the value at which it flips (the
     break-even machinery, one input at a time with the others at base), and the vertices where B wins.
3. **Monte Carlo over the ranges** (`ESTIMATED`). All inputs move together.
   - **Distribution per input:** PERT from low, base and high (λ = 4) by default; triangular, or
     another a person states (uniform, normal truncated at low and high), on record.
   - **Correlations** are declared by a person as pairwise rank correlations, and imposed by
     Iman-Conover, which keeps each marginal. A matrix that is not positive semi-definite is refused by
     name; the nearest valid matrix is offered as a proposal, never applied silently.
   - **Draws:** N = 20,000, from `numpy` PCG64 under the run's seed, with element-wise
     arithmetic only, so a rerun reproduces the bytes.
   - **Convergence:** five independent streams (`SeedSequence.spawn`). The result stands when
     P(A cheaper than B) agrees across streams within ±0.01, and the difference's 5th and
     95th percentiles agree within a tolerance that never shrinks to zero: the larger of 1 % of the
     absolute base difference and 0.1 % of the larger scenario's base total. Scenarios with equal base
     costs therefore have a stable, non-zero tolerance. Otherwise N doubles, up to
     160,000, and then the result is refused as `not_converged`.
   - **Outputs:** P(A cheaper than B) with its Monte Carlo standard error; the 90 % interval of the
     difference; each scenario's percentiles. The percentiles and the seed are stored, and the samples
     can be regenerated from them.
4. **Global sensitivity** (`ESTIMATED`), beside the one-way tornado: which inputs drive the variance of
   the difference when everything moves together.
   - Inputs independent: Sobol first-order and total indices by the Jansen estimator, with bootstrap
     intervals.
   - Inputs correlated: Sobol indices are not defined, so they are not shown; partial rank correlation
     coefficients are, and the page says why.
   - It answers "which number is worth checking before deciding".
5. **Backtested forecasts** (`ESTIMATED`), wherever the model projects a volume over its horizon.
   - A closed set of methods: naive, seasonal naive, drift, Holt-Winters additive with its parameters
     fitted by a pinned, deterministic optimiser.
   - Rolling-origin backtest on the most recent held-out periods (the last 6 months, at least 3
     origins). The candidate and its baseline (the seasonal naive; the naive without two cycles) are
     forecast from the **same origins** and scored on the **same held-out periods**.
   - **A forecast that does not beat its baseline is not used**: its held-out mean absolute error
     must be strictly below the baseline's on those same origins. The baseline is used instead, and
     the page says so in words.
   - MASE (scaled by the in-sample naive) and MAPE (where no actual is zero) are reported beside it,
     never used as the gate. MASE < 1 does not show that a forecast beats the held-out baseline when
     held-out volatility differs from the training period's.
   - The kept forecast's backtest errors give its interval, which becomes that volume input's range and
     its distribution in the Monte Carlo.
6. **Value of information** (`ESTIMATED`). For each input, the expected value of perfect information on
   it (EVPPI, by binning the Monte Carlo draws on that input) in the model's currency: what knowing it
   exactly could save in expectation.
   - An input a person marks as measurable by a survey ("ztráta zákazníků při pomalejším doručení") whose
     EVPPI is material is said so, and AIA offers the Výzkum path.
   - The offer is a research study of the same client, proposed with its question prefilled, linked
     later (Q3, decision 12). Nothing starts and nothing is charged until a person starts it there.
   - EVPPI is never compared with a research run's USD price in one number (no currency conversion);
     both are shown.

**The decision rule is the person's own, written before any data** (the Zadání design, board Z3: "zvolíme
X, když ukazatel ≥ práh"; R2 makes the threshold required).
- **The rule is part of the model.** It names the option, the quantity (for example the difference in
  yearly cost or in NPV), the comparison and the threshold. It may also name the confidence the person
  needs, for example "zvolíme A, když P(A levnější) ≥ 0,8".
- **The stated rule decides.** The result is judged against it as written: "doporučeno A" when the rule
  holds at its stated confidence, "doporučeno B" when its mirror holds, "nerozhodnuto" otherwise. An
  undecided result names layer 4's and layer 6's inputs as what to check.
- **The default confidence.** When a rule names a quantity and a threshold but no confidence, the
  default (0.90 for A and 0.10 for B, in the Metodika module) applies, and the page says
  the default is in use.
- **Without a stated rule, nothing is "doporučeno".** The page reports P and the dominance, and says the
  rule is missing (R2).
- **Written before the data.** The run records when the rule was stated. A rule first stated or changed
  after a run's results were shown is marked so on the page and in the report, never silently.
- Layer 2's dominance is printed beside the verdict either way.
- Until the Monte Carlo method's register entry approves it, the verdict is internal, and the client
  report carries layer 2's deterministic range alone.

**Validation.** Each method is checked against a published reference before its register entry is asked
for:
- Sobol on the Ishigami function's analytic indices;
- PERT on its analytic moments;
- Iman-Conover on its target rank correlation;
- MASE on a published worked example, and the gate on a series whose held-out volatility differs from
  its training volatility;
- equal-base scenarios converging under the percentile tolerance;
- `range_not_exact` on a quantity where an input enters as both x and 1/x;
- EVPPI on a two-option toy with a closed form.

The checks are tests, and their report is what the method owner signs.

## Consequences

- **What it costs.**
  - A third study kind, which every list, count, scope check and route must place.
  - A second working-copy content kind.
  - Two grades and an admission path.
  - A type registry.
  - A report frame and three chart kinds.
  - Five generic stages.

  The MVP builds all of that once, with one model type and decision 14's method, in about 78.5-100.5
  session-days (the model's WIND map included, decision 12), on the fourth build session and a fifth
  for the method chunks: about 9-11 weeks
  (`cost-model-study`). The platform costs about 3-5 session-days more than a cost
  model built alone. The robust method adds about 37-47.5, and the WIND map 11.5-17. The other families are designed at about
  53-65.5 session-days (`quantitative-families`); building decision 14 in the MVP takes the `ESTIMATED`
  platform, Monte Carlo, forecasting and NPV out of their scope.
- **What it buys.** Questions AIA could not answer, under the same rules as the rest of AIA: code
  computes, a person decides, every number has an origin, and unknown is never good.
- **What it does not do.**
  - no simulation;
  - no what-if over respondents;
  - no survey inside a model study;
  - no respondent Sociomap from a model: the model's own map is an objects × properties WIND map, and
    respondent maps are unchanged (decision 12);
  - no Deep Research from a model's content;
  - no `ESTIMATED` number in a client report before its method's register entry;
  - no tax, depreciation schedule or currency conversion in any family as designed.

## Alternatives considered

- **A kind per family** (cost, accounting, finance, operations research, market sizing). Rejected: five
  copies of the same scope, data, provenance, grade, Lead and report wiring.
- **A module inside a research study.** Rejected by the owner's placement, "a new study type beside
  Výzkumy". It would also make every research stage tolerate a study with no questionnaire.
- **Reusing the Simulation kind and core.** It models a population's responses; a business model has
  no population.
- **A free formula language** (as Metodika's formulas, ADR 0023). Rejected: every formula would be a
  model a person must audit. Each model type's closed element set makes its results exact and its
  report explainable.
- **Letting the Lead compute.** Rejected by "No LLM for deterministic computation" and ADR 0027
  decision 5.
- **A separate ledger for model numbers.** Rejected: one ledger, one admission rule and one renderer
  keep "every number is a ref" true everywhere.
- **The core plus four or five `CALCULATED` types in the MVP** (cost scenarios, budget vs actual,
  ratios, NPV/IRR/payback, EOQ): about 38-48 session-days. Not chosen ("Design all now, build later").
  It stays available as a later choice (decision page).

## The decision page

Every question is answered.

Answered on 2026-10-29: Q1 (CZK), Q2 ((a)+(c)), Q3 (two kinds, linked later), Q4 (the minimum set), Q5
(the warehouse case and AC-16), Q6 (a fourth build session; `client-data-in-analysis` 2-3b to W2), Q7
(yes, *výpočet*). Answered on 2026-10-30: the robust method in the MVP (decision 14); Q9, "aram owns statistical
models". By 09:15 UTC: Q9 "Aram signs these too", Q10 "Yes, once Aram registers it", Q13
"Final as written", and a fifth build session. By 09:25 UTC: Q8 "Modely"; Q11 "all of thesw" (every
family after the MVP, in parallel lanes, `quantitative-families`); Q12 "Yes, labelled modelováno".
