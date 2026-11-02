# ADR 0046 — AIA serves business decisions: the AI-respondent survey lane is frozen; client data contracts, then the quantitative model platform, come first

**Status:** Proposed — 2026-11-02. Decisions 1 to 4 are the product owner's, given in the PM
coordinator's chat on 2026-11-02 and quoted below. Later the same day he answered the six questions this
record left open and ten more (§ The owner's answers, later on 2 Nov). Those answers settle parts of
decisions 2, 3, 4, 5, 6 and 8, and each of those decisions says where. A stage-by-stage walkthrough of
the canvas the same day gave 28 more (§ The owner's walkthrough, W1-W28). The rest are this record's
proposals, which take effect when he approves this record. What still needs the methodology owner's
answer is listed under § Open.

**The product owner's words** (2026-11-02, in the PM coordinator's chat, coordinator 3):
- On sharing the research document: "we are pivoting".
- The survey lane: "Freeze it now". The code stays and keeps running on develop, its open chunks are
  parked rather than deleted, and an ADR records the retirement.
- #1149 (LO18b, a questionnaire from a file): "Merge it". It merged at `560c4f18`, the lane's last
  change.
- Who plans the pivot: first "The other account"; then, the same day, "actually we will plan it here".
  This session plans it.
- The first deliverable: "Pivot ADR + replanned waves". That is one docs PR, approved before any build
  work.
- The survey Sociomap plans: "Park with the lane".
- What a research study is after the freeze: "Brief, Design, Deep Research, Report", with "another step
  before, where the user goes through the findings, checks the outcomes of the deep research, build
  tables, graphs, processs maps. basically a stop or more if needed wheere the user discusses with the
  lead the outcome of the deep research and builds what goes into the report which will be shown in the
  zprava section. ofcourse we still need a step for the sociomaps."
- ADR 0044: "Keep it Proposed".
- The expert map: "Both maps in the MVP". The scenario map and the expert objects × properties map are
  both in the MVP.

**The owner's answers, later on 2 Nov** (the PM coordinator's chat, coordinator 4, to questions the
coordinator put to him; the label of the option he chose, or his own words where he typed them):

| # | Question | His answer |
|---|---|---|
| A1 | Which single journey is the MVP's spine? | "Keep all in MVP": no spine; every core plan stays in the MVP |
| A2 | One study kind, or a research study beside a "Modely" area? | "One merged study", as on the canvas "AIA Obchodní model – prototyp" (decision 3) |
| A3 | How does a researcher's own judgement enter a framework? | "Allow, labelled": with its own grade and the author's name, never mixed with sourced points (decision 3) |
| A4 | Do class gates enforce once a real client's data is held? (Q2) | "Enforce for real data": in any deployment holding a real client's data; develop stays advisory on fictional data (decision 8) |
| A5 | One grade vocabulary (Q1) | "Add to the code's": the code's grades stay, `CALCULATED` and `ESTIMATED` are added as print grades, one table maps them (§ Open) |
| A6 | What must Sociomapa systémů do for the MVP? | "Show option clusters": which options win in the same futures, and which hedge each other (decision 5) |
| A7 | Frozen-lane defects (Q5) | "we will be decomissioning after fully defining the MVP" (decision 2) |
| A8 | How is the lane decommissioned? | "Archive to a branch": moved to an archive branch and removed from develop, data included (decision 2) |
| A9 | When does decommissioning start? | "MVP accepted": only once the new MVP passes its acceptance (decision 2) |
| A10 | Market size (Q6) | "Top-down is enough": MKT2, MKT4 and MKT5 (decision 4) |
| A11 | The panel and the population (Q3) | "Retire it too", with the lane (decision 2) |
| A12 | The SOMECS name (Q4) | "Sociomapa systémů; Aram checks": never SOMECS; A. Bahbouh confirms the name and the method's licence before any client use (decision 5) |
| A13 | How wide are the diagrams in the MVP? | "All six in MVP": every rendering stack of `diagrams` (decision 3) |
| A14 | Deep Research's engine freeze and v2 | "Lift for v2 only": v2's listed capabilities are sanctioned; retrieval, grounding and the bundle stay frozen (decision 6) |
| A15 | The stage's name | "i just called it an xray, lets change the name for that", then "Osnova zprávy": in English, the report outline (decision 3) |

**The owner's walkthrough, 2 Nov** ([`pivot-walkthrough-2026-11-02.md`](../../../.planning/evidence/pivot-walkthrough-2026-11-02.md); the PM coordinator's chat, coordinator 4: the canvas "AIA Obchodní
model – prototyp" gone through stage by stage; the option he chose, or his own words). Each decision lands
in the plan named:

| # | Stage | Decision | Where |
|---|---|---|---|
| W1 | Zadání | The business Zadání is built by a plan of its own | new plan [`decision-brief`](../../../.planning/plans/decision-brief.md) |
| W2 | Zadání | Triage asks every question that matters, by importance; the first three open, the rest under "Další otázky" | `decision-brief#DB2` |
| W3 | Zadání | No crown amount in triage; the value of information in Kč appears only on Výsledky, computed | `decision-brief#DB2` |
| W4 | Zadání | "Potřebuje rozhodnutí výpočet?" is asked in the decision core; the model steps appear only on yes | `decision-brief#DB3`, `research-findings-stage#FND1` |
| W5 | Zadání | The study's badge reads "Výzkum", with "Obchodní model" once the model is on | canvas v10 |
| W6 | Data | A data contract and its quality report are accepted on the Data step (D-37's Zadání drawer superseded) | `client-data-in-analysis#10` |
| W7 | Data | A number from a client's document: Ada proposes it with its page, code checks it is literally on that page, the researcher accepts | `client-data-in-analysis#11` |
| W8 | Data | An estimate from client rows is a Metodika method, internal until registered | `client-data-in-analysis#12` |
| W9 | Rešerše | A source's credibility tier is named Úřední / Oborový / Ostatní, never A/B/C | `deep-research-v2#DRV5` |
| W10 | Rešerše | A rating beside a cited quote (Porter's force strength) is the researcher's labelled judgement | `analysis-frameworks` |
| W11 | Rešerše | A run shows citation accuracy and unsupported claims; recall is the method's tested level, never per run | `deep-research-v2#DRV4` |
| W12 | Rešerše | A paid Deep Research run starts only from the Lead's priced card, never from a stage | the workbench rule (#550) |
| W13 | Předpoklady | Ada proposes inputs that move together, with a strength and a reason; the researcher accepts each; independence is stated | `cost-model-study#CR3` |
| W14 | Předpoklady | Each input's distribution follows its source: client data, its estimate; a person's range, PERT; people who disagree, a mixture | `cost-model-study#CR3` |
| W15 | Předpoklady | A guarantor is a person at the client; a value fixed by contract is fixed unless the contract allows a change | `cost-model-study#CR2` |
| W16 | Předpoklady | The discount rate is a fixed study parameter with its guarantor; Výsledky shows the verdict at other rates | `cost-model-study#CR2` |
| W17 | Model | One composable cash-flow model: line items from a closed set of kinds, formulas from a closed vocabulary; cost scenarios its first template | `cost-model-study#CP2`, `#CM1` |
| W18 | Model | NPV before and after tax; the rule reads one, the other beside it | `cost-model-study#CM7` |
| W19 | Model | Legal context: Czech and EU tax, contract and employment law as cited provisions that become parameters and constraints; never legal advice; the researcher accepts | decision 7; new plan [`legal-context`](../../../.planning/plans/legal-context.md) |
| W20 | Výsledky | The headline is the median with its 90 % interval; the base case only as "v základu" | `cost-model-study#CP8` |
| W21 | Výsledky | A result's grade follows its method: a deterministic formula is "výpočet", Monte Carlo and statistics "odhad" | `cost-model-study#CP8` |
| W22 | Výsledky | A verdict such as "realistické" is the researcher's labelled judgement | `cost-model-study#CP8` |
| W23 | Sociomapa | The earlier `-5` strategy map is kept for history, marked superseded, off the study's path | canvas |
| W24 | Sociomapa | **Open:** what the maps draw is to be rethought ("lets leave this open for now"), with who scores on the expert map and how many | decision 5; `sociomapa-systemu` |
| W25 | Osnova zprávy | An unverified point holds the hand-off until its source is found or it is removed | `research-findings-stage#FND8` |
| W26 | Osnova zprávy | A closed stop may be shared with the client's decision-makers for comments; their agreement recorded | `research-findings-stage#FND12` |
| W27 | Zpráva | An estimate whose method is not yet registered still reaches the client report, labelled, with an approval warning; never refused | decision 5; M-5; `cost-model-study#CM6` |
| W28 | Zpráva | The report is Czech in the MVP; English after | `research-findings-stage#FND9` |

**The evidence:** [`.planning/evidence/pivot-research-2026-11-02.md`](../../../.planning/evidence/pivot-research-2026-11-02.md),
the owner's document "AIA pivot research: rebuilding for business decisions" (2 Nov 2026). Its
anchors are `@ 57c133a`. Section letters below (A1, B2, C2 …) are its own.

**Builds on:**
- [ADR 0008](0008-eu-data-residency.md): residency and data classes.
- [ADR 0017](0017-deep-research-external-retrieval.md) and
  [ADR 0021](0021-deep-research-purpose-target-lineage.md): Deep Research.
- [ADR 0023](0023-methodology-is-data-the-methodologist-owns.md): methods are data the methodologist
  owns.
- [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md): panel respondents.
- [ADR 0027](0027-client-data-is-client-reported-evidence.md): client data is client-reported
  evidence.
- [ADR 0038](0038-mvp-sociomap-method-is-aia-sociomap-5.md): `aia-sociomap-5`.
- [ADR 0044](0044-quantitative-model-studies.md): quantitative model studies, still Proposed.
- [ADR 0045](0045-reports-composed-per-situation.md): reports composed per situation, still Proposed.

## Context

AIA was built around one study shape: a brief, a questionnaire, AI respondents drawn from a licensed
Czech panel, results, a Sociomap of respondents' ratings, eight analysis modules, and a report. The
owner is changing what AIA is for. It now answers a business's own decision with:
- the client's data, under a contract;
- public data;
- external research grounded in quotes;
- quantitative models computed by code;
- maps of the business system;
- a report in which every number traces to its origin.

The research found that almost all of AIA carries over, but five things in the repository did not
match the new direction (§ "Where the brief and the code differ", @ 57c133a):
- No decision retiring survey fieldwork was recorded anywhere, and the lane was still being extended.
- The quantitative model platform (ADR 0044, Proposed) and its build plan (`cost-model-study`, 0 of 32
  chunks) exist only on paper.
- Client data contracts do not exist, so no client dataset can enter an analysis
  (`client-data-in-analysis` 8a).
- The Sociomap engine's statistics do not hold on business rows, although its layout does (A1-A4).
  Two independent random walks look related about three times in four at the 5 % level. BH is not
  guaranteed for two-sided correlation tests. Split-half compares two periods, not two samples.
- No published validation of Sociomapping on business data exists (A5).

## Decisions

### 1. What AIA is for

AIA researches business decisions for small and mid-size EU firms. It does so with:
- the client's own data, under an accepted data contract;
- Czech and EU public registers and statistics;
- Deep Research, whose findings are quotes in captured sources;
- quantitative models computed by code (ADR 0044);
- Sociomapa systémů, maps of a business system;
- a report in which every number is a reference to its origin.

The rule that orders AIA does not change: models propose, code computes, a person approves. Traceable
evidence is the position AIA leads with (E3).

### 2. The AI-respondent survey lane is frozen

From 2026-11-02 the following get no new work. That means no new feature, no new chunk and no
re-scope:
- fieldwork with AI respondents, fictional or panel-grounded (`ai_fieldwork`, ADR 0024);
- the questionnaire, the audience, the sample and the dimensions;
- the panel and the population as a respondent source;
- the survey Sociomap: `aia-sociomap-5` and its predecessors on respondents' ratings, with their
  segments and drill-down;
- the survey results and the eight analysis modules over fieldwork data;
- run QC and the fieldwork checkpoint;
- assumptions evidenced by respondent claims, and open-answer coding;
- the holdout validation.

The plans and chunks parked by this freeze are listed in the master plan (§ The pivot, and §3.3) and
in the execution contracts (§ The pivot's critical path).

- **The code stays and keeps running on develop until the MVP is accepted.** Until then nothing is
  deleted, no test is removed, skipped or loosened, and every built route keeps answering. A stored study
  or run keeps its data and stays readable.
- **Open chunks are parked, not deleted.** A parked chunk keeps its text and its `[ ]`. It counts toward
  no wave's gate, and nothing waits on it. It moves only on the owner's word.
- **Then it is decommissioned** (A7-A9). Once the new MVP passes its acceptance, the lane is moved to an
  archive branch and removed from develop, its stored data included (develop holds only fictional data).
  The parts the new work reuses stay on develop: the Sociomap layout, terrain and determinism, the
  report engine with its locked numbers, and the evidence model (decision 9; the coordinator's reading,
  stated to the owner before he said "fold them into #1150"). The work is
  `mvp-master-plan#MP19`.
- **Until then, the lane is maintained only as far as develop needs.** Its code and tests keep running,
  so a change elsewhere keeps them green; it gets no other fix.
- **The panel and the population are retired with it** (A11). Production gets no population import and
  no panel route (`production-environment#PE6` is parked), and never will.

### 3. A research study after the freeze

There is one study for a business decision (A2: "One merged study"). It replaces the separate "Modely"
area that ADR 0044 and `cost-model-study` planned (Q8 of 2026-10-30). Its steps are the canvas's
nine, in five groups:

| Group | Step | What it holds |
|---|---|---|
| Zadání | **Zadání**, with its sub-steps | the decision, the rule, the frameworks (below), what the model needs |
| Vstupy | **Data** | the client's files under their data contracts |
| | **Rešerše** | Design Research: Deep Research's findings and typed values (decision 6) |
| | **Předpoklady** | every input with its range, source and guarantor |
| Výpočet | **Model** | the quantitative model (ADR 0044) |
| Evidence | **Výsledky** | the model's results in their views |
| | **Sociomapa** | a Sociomapa systémů map (decision 5) |
| Předání | **Osnova zprávy**, the report outline | see below |
| | **Zpráva** | the report |

- **The model steps appear when the decision needs a model.** Data, Předpoklady, Model and Výsledky
  are shown when Zadání says a model is needed. A study whose decision needs none goes from Rešerše to
  the report outline.
- **The report outline (Osnova zprávy)** is new and may have more than one stop. It is the report's own structure with the
  prose taken out: every finding, data point and point the report will make, each with its table, graph,
  process diagram or other visual. Every number and claim is a link to its source or its method. The
  researcher works through what Deep Research found, the results and the map with their Lead, checks
  them, and builds the report outline. A point whose link does not resolve cannot reach the report.
- **Zpráva** is prose written around exactly the report outline's closed points, each number and claim keeping
  its link, composed and approved there.

This changes the order the owner's first words gave: Sociomapa now comes before the report outline, as on the
canvas, so the map's points can enter it.

The owner's words on the stage he first called the X-ray (2026-11-02): "a stage where the bare bone findings are presented in a
structure of the report … its almost as if you had the report but took out all hte claims and data and
got an xray view of the report with all the main points. everything should be verifiable and ideally
numbers or claims have hyperlinks connected to see what the source or methodology for that claim/figure
is".

New research studies don't show the survey stages, from Dotazník to Analýza. A study that already
holds survey content or runs keeps those stages read-only, so nothing stored becomes unreachable. The
stages, the routes and the stop rule belong to the new plan
[`research-findings-stage`](../../../.planning/plans/research-findings-stage.md).

In Zadání the researcher also chooses which analysis frameworks the study includes (the owner,
2026-11-02: "i want the user to be able to chose whether to include SWOT, PESTEL, BLUE OCEAN. TAM SAM
SOM, and any and all relevant business/ operations/ accounting frameworks for the deep research and lead
researcher to include into the report"). The groups are strategy and market, finance and accounting,
operations, logistics, corporate governance and enterprise architecture, with the portfolio frameworks
after the MVP. Ada proposes a set for each decision type ("Ada proposes per decision"), and every point a
framework holds is a cited finding, a client-data number, a model result or a named expert's score
("Sourced points only"). The one exception is the researcher's own judgement (A3: "Allow, labelled"): a
point may be it, printed with its own grade and its author's name, never mixed with sourced points. The selection drives Deep Research's plan, the model's views, the expert forms
and the report outline. The work is
[`analysis-frameworks`](../../../.planning/plans/analysis-frameworks.md).

The report outline's visuals are specs, never pictures: BPMN, data-flow, state and the other diagrams, every chart
and every table are typed specs the Lead proposes, code validates, the researcher accepts and the server
renders (the owner, 2026-11-02, "bpmn diagrams, data flow diagrams, state diagrasm, any type of graph,
and table"). All six rendering stacks are in the MVP (A13: "All six in MVP"). The work is
[`diagrams`](../../../.planning/plans/diagrams.md).

ADR 0044's model platform runs inside this study, not in an area of its own. ADR 0044 stays Proposed;
its "Modely" area is superseded here, and its amendment (decision 10) records that when it is accepted.

### 4. The order: data contracts, then the model platform

1. **Data contracts.** `client-data-in-analysis` 0 to 3b and 10 integrate in wave W1. That covers the
   evidence policy, the contract as a type, the analysis copy, the quality report and the drawer.
2. **The model platform.** `cost-model-study` CP1 to CP9 and the cost-scenario type CM1 to CM7 follow
   in W2. Its `ESTIMATED` layers CP10 and CR1 to CR10 come in W3, after the methodology owner's answers.
   The four result views follow in W3, in the MVP "from the beginning" (the owner, 1 Nov 2026, the
   research-stages prototype v29): finance, accounting, operations research and market size
   (`quantitative-families`, except its survey-derived MKT1, MKT3 and LINK1).
3. **Then the maps.** Sociomapa systémů and its validation suite come in W2-W4 (decision 5).

Deep Research v2, the public data routes and the register personal-data records run beside the
platform.

Everything in this order is in the MVP (A1: "Keep all in MVP"); no single journey is its spine. Market
size is top-down (A10): public statistics (MKT2), the market-sizing Deep Research purpose (MKT4) and its
stages (MKT5).

ADR 0044 stays Proposed, at the owner's word. The platform is planned and waved here, and it is
accepted separately.

### 5. Sociomapa systémů: keep the layout, replace the statistics

These stay:
- the layout;
- the terrain;
- the sparse design;
- determinism (seeds and PCG64 streams recorded).

These are replaced for business rows:
- per-person centring, by a per-variable transformation declared before results are seen;
- the unrelated baseline, by per-variable surrogates that reproduce each series' autocorrelation;
- the pair floors, by an autocorrelation-adjusted effective-sample-size floor;
- Benjamini-Hochberg, by Benjamini-Yekutieli by default;
- split-half, by a block bootstrap with Procrustes-aligned displacement.

The map has four modes, each with its own claim and grade:

| Mode | Rows | It may claim | Grade |
|---|---|---|---|
| Scenario map | a model's Monte Carlo scenarios (≥ 800) | in this model, A and B move together | MODELLED |
| Expert map | options or competitors scored by people | the scorers' judgement, named | MODELLED, inputs stated by a person |
| Unit map | comparable units (branches, SKUs, customers) | association across units, with an interval | ESTIMATED |
| Period map | 24-36 months | weak association at a stated time scale | ESTIMATED, failing edges not drawn |

- **The scenario map and the expert map ship first**, at the owner's word ("Both maps in the MVP"):
  `cost-model-study` CS1-CS5 and `situation-reports` EX1-EX2.
- **The unit and period maps ship only after the synthetic validation suite passes.** The suite plants
  structure and runs null worlds.
- **What the MVP's maps must do** (A6: "Show option clusters"): show which options win in the same
  futures, and which hedge each other. The map explains a decision; it never makes one.
- **The name is Sociomapa systémů, never SOMECS** (A12). A. Bahbouh confirms the name and the published
  method's licence before any client reads it.
- **The never-claim list holds in every mode.** It is the method recommendation's § Never claim. A map
  never claims cause, never presents a scenario map as how the market behaves, and never reads a
  distance as an effect size.
- **The methodology owner decides before anything is built.** A. Bahbouh decides the research's ten
  statistical questions, or the subset each chunk needs, before any replaced statistic is built. Each
  mode is registered separately in Metodika (ADR 0023). Until its entry is approved a mode's result is
  labelled "metoda čeká na schválení metodikem" wherever it appears, and in a client report its approval
  shows a warning recorded on the ledger row, never a refusal (W27; as report-delivery RD0, 22 Oct).
- **Open: what the maps draw** (W24). The owner: "i think we still have to rethink what the maps draw,
  lets leave this open for now". Who scores on the expert map and how many raters wait on it, and the
  maps' chunks (`sociomapa-systemu` SYS9-SYS10, `situation-reports` EX1-EX2) do not start before it is
  answered.

The work is the new plan [`sociomapa-systemu`](../../../.planning/plans/sociomapa-systemu.md).

### 6. Deep Research: keep the core, add typed numbers

These stay as built:
- the six steps;
- `RetrievalGate`;
- the content-addressed snapshots;
- the rule that a finding is a quote in a captured source (B1).

Version 2 adds the following, in the research's rank order:
1. structured registers and statistical series, where the model proposes a query key and code fetches
   it;
2. numeric extraction into typed inputs (value, unit, period, range, source, licence), by a rule-based
   extractor in code, accepted by a person;
3. citation precision and recall, and link health;
4. source credibility v2, set by declared tables, never by a model;
5. triangulation and contradiction, resolved by a person;
6. as-of-date research through Memento and Wayback;
7. scheduled monitoring;
8. precedents, as candidates only.

**The engine's freeze is lifted for these capabilities only** (A14: "Lift for v2 only"). Retrieval,
grounding and the sealed bundle stay frozen, changed only on a defect or an evaluation finding, as
before (ADR 0017, ADR 0021).

The gate gains three checks before structured or archive routes go live:
- per-source rate limits;
- a robots.txt and text-and-data-mining reservation check before any fetch for mining;
- a retention limit on mined copies.

The plans:
- [`deep-research-v2`](../../../.planning/plans/deep-research-v2.md) owns the extraction, citation,
  credibility, triangulation, as-of, monitoring and precedent capabilities, and the gate additions;
- [`public-data-routes`](../../../.planning/plans/public-data-routes.md) owns the routes.

### 7. Public data, and the law

The research's data source register (§ Data source register, C2-C3) is the basis for which public
source AIA may use, and how:
- Czech registers are official works with no database right.
- VIES results are validated once and never stored, because their reuse is forbidden.
- NEN data behind its login is never collected.
- ARES is queried at most 500 times a minute.
- A machine-readable text-and-data-mining opt-out is honoured.
- A personal-data record exists before any register field that names a natural person reaches a study:
  the purpose, a balancing test in the approval ledger, an Art. 14 notice where it is owed, retention
  and erasure. The work is [`register-personal-data`](../../../.planning/plans/register-personal-data.md).
- Financial statements (Sbírka listin) are the data gap. Proposed: extract them from PDF with a person's
  review first, and decide on buying structured data after measuring that review's cost
  (`public-data-routes` PDR7).
- **The law itself** (W19). Czech law (e-Sbírka) and EU law (EUR-Lex) in tax, contract and employment:
  a legal point is a verbatim quote of a specific provision in the version in force on a stated date,
  captured from the official source, and it becomes a model parameter (tax rate, depreciation, notice
  period, minimum wage) or a constraint the researcher accepts. AIA flags what applies and never gives
  legal advice; every report that uses one says so. The work is
  [`legal-context`](../../../.planning/plans/legal-context.md).

### 8. Data classes: the code's definitions stand

The brief behind the research defined Class B as design and Class C as public. The code defines them
differently (`domain/residency.py:51-67 @ 57c133a`), and its definitions stand:
- **A**: raw client material.
- **B**: derived client material (aggregates, summaries, segment profiles).
- **C**: internal and non-client material (methodology, public sources, prompts with no client
  information).

[ADR 0008 Amendment 2026-10-19](0008-eu-data-residency.md) already takes a design as Class B by rule,
which agrees with these definitions.

Advisory class gates have been allowed in every environment since commit `4959b1cb` (2026-10-29),
on the owner's "Advisory everywhere" of 2026-10-28 (`prototype-build#PB6`). Develop runs advisory.
`enforce` stays the default, so a deployment is advisory only where its configuration says so. The
research reads this as "advisory everywhere". The owner's answer (A4, Q2: "Enforce for real data"): a
deployment that holds a real client's data enforces, staging and production included, so a client
dataset's rows reach a model only over a route approved for their class. Develop stays advisory on
fictional data.

### 9. The component verdicts

The research's keep / extend / replace table (§ "Keep, extend, replace", @ 57c133a) is adopted as the
plan's starting point.

- **Kept as built:**
  - FastAPI and PostgreSQL;
  - the workflow engine;
  - budgets and wallets;
  - the governed gateway;
  - "models propose, code computes";
  - the report engine with locked numbers;
  - ONLYOFFICE;
  - client knowledge;
  - Deep Research's core;
  - the Sociomap layout, terrain and determinism.
- **Extended:**
  - the approval ledger: data-contract approvals, GDPR balancing tests, Art. 14 notices;
  - the admitted claims: an autocorrelation-adjusted effective n beside Kish's;
  - the grades: one vocabulary, § Open Q1;
  - Metodika: quantitative methods and each map mode;
  - client sources: both Czech P&L layouts, and PDF statements with review;
  - personal-column masking: the register personal-data record;
  - the Lead: per-change accept and the plan card, already planned;
  - the gate's egress: decision 6.
- **Replaced:** the Sociomap engine's statistics (decision 5).
- **Built first:** the data contracts and the model-type contract.

### 10. ADR 0044's four corrections, proposed as its amendment

The research's corrections to the designed quantitative methods (D1, finding 9) are proposed as an
amendment to ADR 0044, whose status is unchanged:
1. Input correlations are included. Omitting them is the larger documented error.
2. PERT's beta shape is tested against data where data exist. Disagreeing experts are sampled as a
   mixture, not averaged.
3. Forecasts are judged by MASE, scaled by the seasonal naive for seasonal series, never by MAPE where
   zeros occur. This replaces "held-out MAE" in `cost-model-study` CR5.
4. A study declares one discount rate, applies it to every option, reports how sensitive the verdict is
   to it, and never lowers it because a model is simulated.

Each correction reaches its chunk's text when A. Bahbouh answers the matching question (8, 9 and 10 of
the ten). Until then the chunk's current text stands.

## Consequences

- **The master plan's register changes.** The survey-lane plans move from §3.1 to §3.3 as PARKED, and
  `cost-model-study`, `situation-reports`, `quantitative-families`, `analysis-frameworks`, `diagrams`, the five new plans and,
  from the walkthrough, `decision-brief` and `legal-context` become core.
  The goal sentence and § The pivot record the new MVP. `tools/master_check.py` passes on the result.
- **The execution contracts change.**
  - The data contracts row (E17) moves from W3 to W1.
  - New rows E35 to E50 carry the platform, the maps, Deep Research v2, the data routes and the
    personal-data records.
  - Every parked row and chunk is listed once, and stops counting toward its wave's gate.
- **The acceptance criteria are redefined.** MVP-ACCEPT-2's fifteen criteria were written for the survey
  study, and several of them (AC-05, AC-06, AC-07 and parts of AC-08, AC-09 and AC-13) test the frozen
  lane. Their redefinition is a separate change, `mvp-master-plan#MP17`, which edits
  `docs/migration/mvp-acceptance.md` and `parity-matrix.json` with their tests. The owner approves it.
  Until it lands, the register keeps AC-01 to AC-15, marks the frozen ones, and adds AC-16, the
  cost-model journey (`cost-model-study#CM6`).
- **USD 25 tier B is re-allocated** when MP17 lands. The survey lines go and the model and Deep
  Research v2 lines come in.
- **The survey lane is decommissioned after the MVP's acceptance** (decision 2, `mvp-master-plan#MP19`).
- **Nothing is switched on, called or deleted by this record.**

## Alternatives considered

- **Delete the survey lane now.** Rejected by the owner ("Freeze it now"). It is archived only after
  the new MVP is accepted (A8, A9), and its engine parts (layout, terrain, the report's evidence model)
  stay, because the new work reuses them.
- **Run both lanes at full speed.** There is no capacity for that. The research finds that the business
  lane needs the data contracts and the model platform first, and those are the work the survey lane
  would delay.
- **Reuse the survey Sociomap's statistics on business rows.** Rejected on the evidence (A1-A4): they
  find structure in independent random walks.
- **Rebuild from scratch.** Rejected: the research's verdict is to keep almost everything (§ Keep,
  extend, replace).

## Open

**For the product owner: answered.** The six questions this record first left open were answered on
2 Nov (§ The owner's answers, later on 2 Nov). What each settled:

| # | Question | Answer | Where it lands |
|---|---|---|---|
| Q1 | One grade vocabulary | A5: the code's grades (`MEASURED`, `CALIBRATED`, `MODELLED`, `HOLDOUT_PENDING`; `domain/report/evidence.py:41-46 @ 57c133a`) stay, `CALCULATED` and `ESTIMATED` are added as print grades, and one table maps every grade to its Czech label and admission rule before the first quantitative result reaches a report. The researcher's judgement (A3) is a grade of its own in that table | `cost-model-study#CP8`, `#CP10` |
| Q2 | Do class gates enforce before client data flows? | A4: yes, in any deployment holding a real client's data; develop advisory | `client-data-in-analysis#9`, `production-environment#PE5` |
| Q3 | May the frozen panel feed market counts? | A11: no; the panel is retired with the lane | `quantitative-families#MKT3` stays parked |
| Q4 | The SOMECS name and licence | A12: Sociomapa systémů, never SOMECS; A. Bahbouh checks the name and licence before client use | `sociomapa-systemu#SYS0`, `#SYS12`, `situation-reports#EX2` |
| Q5 | Are frozen-lane defects fixed? | A7: the lane is decommissioned after the MVP's acceptance, and maintained only as far as develop needs until then | decision 2, `mvp-master-plan#MP19` |
| Q6 | Is top-down market sizing enough? | A10: yes | `quantitative-families#MKT2`, `#MKT4`, `#MKT5` |

**For the methodology owner, A. Bahbouh.** These are the research's ten questions (§ Questions for the
methodology lead), each with its recommendation there:
1. multiple testing on maps;
2. levels or changes for trending KPIs;
3. the effective-sample-size formula and floor;
4. credibility resampling for 24-36 rows;
5. the surrogate null;
6. the relation statistic;
7. the synthetic suite's pass thresholds;
8. the discount rate in probabilistic decision rules;
9. PERT inputs;
10. forecast evaluation.

They are sent to him as one message (`sociomapa-systemu#SYS0`), with the SOMECS name and licence check
(Q4). No replaced statistic is built before its question is answered.
