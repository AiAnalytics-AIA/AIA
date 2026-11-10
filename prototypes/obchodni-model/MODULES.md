# The MVP as twenty modules

Version 1, 10 November 2026. Written from the product owner's request of the same day: "help me define the
mvp in order to achieve this high level goal, by breaking it down into smaller more defined modules", and
"write up each module as a spec. an important aspect of this software is that each stage and step is
tailored based off of the last. this is a dynamic software that can use AI to tailor its UI to the needs of
an individual study and therefore user."

**The goal.** AIA proposes, designs and executes a whole study: data collection, processing, Sociomap
construction, interpretation and the full report. The user talks to the Lead throughout, and the Lead
controls the valve of every stage.

**What this document is.** The breakdown of that goal into modules a build session can take one at a
time. It sits beside the scope (`MVP-SCOPE.md`, version 3, the record of what the MVP delivers and when)
and the methodology (`methodology/`, version 5, how each step is done). It changes neither: where a
module needs work the scope already plans, it names the scope's chunk; where it needs new work, it
proposes a chunk with the id prefix `MOD-`. The plan files stay the record; a docs PR moves accepted
`MOD-` chunks into them.

**Anchors.** Every claim about code carries `file:line @ b4fb2081c` (develop on 10 November, after
#1147) or a test name. Paths are relative to the repository root; `aia_core/` stands for
`packages/aia_core/src/aia_core/`. An unanchored claim is labelled **hypothesis**.

**The two worked examples.** Each module is checked against two studies:

- **The cost decision**: a firm decides between buying a product and building its own plant at one of
  several sites. It needs a quantitative model, scenario maps and the full release rule. Its acceptance
  case pack is ChemVitro (`prototypes/case-chemvitro/`, AiAnalytics-AIA/AIA#1155, open until its author
  fixes two defects).
- **The competitor analysis (pharmacies)**: a medical company compares pharmacy chains, from their
  financial statements, public registers and a dated price-and-service sample. It needs no
  quantitative model; it needs public data routes, structured collection and observed-data maps.

---

## 1. Purpose and the one rule

A study is a chain of artifacts. Each module takes one defined artifact in and returns one out. Every
module works the same way:

1. **A worker proposes.** A worker is a closed task with a closed output contract
   (`aia_core/domain/lead_workers.py:88 @ b4fb2081c`, `LeadWorkerSpec`). It never writes anything a
   person has not accepted.
2. **The Lead presents.** The proposal reaches the user as a card or an edit in the Lead's conversation
   (`aia_core/domain/research_lead.py:450 @ b4fb2081c`, `LeadOutput`).
3. **A valve takes the user's yes.** Nothing that costs money, fixes a result or reaches a client
   happens without it. The yes is a row in the approval ledger
   (`aia_core/domain/approval_ledger.py:40 @ b4fb2081c`, `ApprovalSubject`).
4. **A fixture with a planted answer proves the module.** A fictional case whose right answer is known
   in advance; the module passes when it finds it (§ module 20).

**A study type is a composition of modules.** The cost decision and the competitor analysis use mostly
the same modules, configured differently, and differ in a few (§ 5). A new study type is a new
composition and, at most, a new configuration of an existing module. It is never a new pipeline.

**What a module is not.** It is not a screen. Screens are how a module's artifact is shown and edited;
which screen, with which fields and in which order, is decided per study by module 4.

---

## 2. The tailoring principle

The owner's principle: **every stage and step is tailored from what came before it, and from the user.**
The pharmacy study's Data stage asks for different sources than the cost decision's; a user who has run
ten studies needs less explanation than one on their first. AIA uses AI to tailor the surface of each
stage to the study and to the user.

Tailoring is powerful and therefore bounded. This section says exactly what it may and may not do.

### 2.1 What AI tailors

For each stage, from the upstream artifacts and the user, a worker may propose:

| What | Example, the competitor analysis | Example, the cost decision |
|---|---|---|
| **Which inputs the stage asks for** | Data asks for the chains' statements and a price basket; no model inputs | Data asks for the purchase history, the plant offer and the site data |
| **Which fields, and their defaults** | the factor families (profitability, efficiency, price, service, location) pre-filled from Zadání's question | the perspectives and their cost lines, from the decision's options |
| **Examples and help text** | "EBIT margin: comparable only once the Rx share is known" | "the overrun applies on the like-for-like basis its source states" |
| **The order of steps and fields** | sources before factors when the user already holds the statements | the rule before the options when the decision owner has stated it |
| **Which visual a result is shown in** | a ranked table beside the financial-profile map | the decision-boundary table beside the scenario map |
| **Explanation depth, for this user** | a first study: every term explained; an experienced user: none | the same |
| **Which configuration is proposed** | the financial-profile and expert configurations of the observed-data map | the futures and weight-settings configurations of the scenario map |

### 2.2 How: a declarative stage specification

A tailored stage is described by a **stage specification**: data, never code. It extends today's
per-artifact contract, which already declares, for each of the eleven workbench stages, what the stage
shows, which edits land on it, the closed set of view operations the Lead may run, the element kinds it
can name, which workers its cards start, its inputs and what it hands on
(`aia_core/domain/lead_artifacts.py:1-21 @ b4fb2081c` for the fields; `:196-225` for `ArtifactContract`
and its consistency rules; `:259` for the table `ARTIFACTS`). The web holds the same contract
(`apps/web/src/lib/workbench-artifacts.ts:55 @ b4fb2081c`), both held to one fixture
(`tests/fixtures/lead_artifacts/contract.json`).

The stage specification adds four things to that row:

1. **Components** from a closed vocabulary: field, table, factor list, source list, chart, map, card,
   explanation block, checklist. Each component is a design-system component the client already draws
   (`apps/web/src/design/tokens.json:9 @ b4fb2081c` for the tokens; `apps/web/src/components/ui/` for the
   controls). The vocabulary is versioned; a component not in it is refused by name.
2. **Bindings**: each component names the artifact field it shows or edits, by the stable item ids the
   working copy already carries (`aia_core/domain/item_ids.py`, WCE1; anchor the line in MOD-4.1).
3. **Order and grouping**, and **defaults** for empty fields, each default marked as proposed.
4. **Explanation level** per component: none, short, full.

The specification is **proposed by a worker** (module 3), shown to the user as a proposal, and
**rendered by the client** from the design system. The model never writes HTML, CSS or script, and the
client never evaluates anything the model wrote. View operations stay the closed set the Lead already
uses (`aia_core/domain/lead_artifacts.py:74-95 @ b4fb2081c`: open_stage, focus, inspect, select, filter,
show_diff), and a filter changes the picture, never a computation (`:96-97`).

### 2.3 What tailoring may never change

A stage specification may change what a stage *shows and asks*. It may never change what a stage *does*.
These are outside its vocabulary and are checked by code on every specification:

- **Valves.** Every valve a module declares stays, in its place. A specification that omits a valve
  component or reorders it after the action it guards is refused.
- **The method and its register status.** The configuration, its parameters and its register entry come
  from module 18; a specification may propose a configuration, never alter one.
- **Evidence and grade rules.** A number reaches a result only as an `AdmittedClaim`
  (`aia_core/domain/evidence/admission.py:188 @ b4fb2081c`), minted only by `admit_numeric_claims`
  (`:298`). A specification displays claims; it cannot mint, hide a grade or relabel one.
- **Numbers.** No component computes. Every number shown is read from an artifact.
- **Data-class and residency gates.** Material keeps the class its rule gives it
  (`aia_core/domain/material_rules.py:68 @ b4fb2081c`); the gateway's route rules stand
  (`aia_core/application/model_gateway.py:203 @ b4fb2081c`).
- **Spend.** Ceilings and confirmations (module 19) are not components a specification controls.
- **Accessibility.** Contrast, focus order, touch targets and labels follow the design system; a
  specification that breaks the look contract's checks is refused (`prototypes/LOOK.md`;
  `apps/web/src/design/look-contract.test.ts`).

### 2.4 The record

Each study stores the stage specification it ran with, as an artifact with a fingerprint of its inputs,
like any other artifact. Three consequences:

- **Reproducible.** Re-opening a study shows the stages as they were when the user worked in them.
- **Auditable.** The audit says which specification was shown when a valve was passed.
- **Invalidated like any artifact.** When an upstream input changes, the downstream specifications are
  marked for re-proposal by the same impact rule the pipeline already applies to stages
  (`aia_core/domain/pipeline.py:531 @ b4fb2081c`, `stage_impacts`; `:464`, `impact_preview`). A stale
  specification is shown with its staleness, never silently replaced.

### 2.5 The user side

- **What informs tailoring.** The Lead's USER file (`aia_core/infrastructure/tables.py:988 @ b4fb2081c`,
  `user_profile`, at most 2,000 characters per ADR 0030) and the user's stated preferences
  (`aia_core/infrastructure/researcher_lead_repository.py:433 @ b4fb2081c`, `set_preferences`; today one
  preference, `auto_accept_text_edits`, `tables.py:997`). Module 4 adds explanation level and preferred
  visuals as preferences the user sets, never inferred silently.
- **See, undo, reach the original.** Every tailored stage shows that it is tailored and why, in one line.
  The user can undo one tailoring, or switch the stage to its **untailored form**: the stage's default
  specification, the same for every study of the type. The untailored form always works.
- **Across users.** Tailoring for one user never changes what another user of the same study sees, except
  for the study's shared artifacts themselves.

---

## 3. The modules

| # | Group | Module | One line |
|---|---|---|---|
| 1 | Orchestration | Lead | the user's words to a proposed plan, cards and progress |
| 2 | Orchestration | Study engine | stages, their state, and invalidation |
| 3 | Orchestration | Worker registry | every worker as one registered, closed row |
| 4 | Orchestration | Adaptive study surface | the tailoring principle as a module |
| 5 | Framing | Zadání and study type | the question, the decision rule, the composition |
| 6 | Evidence acquisition | Client data contracts | the client's files as contracted datasets |
| 7 | Evidence acquisition | Public data routes | register and statistics records, fetched by code |
| 8 | Evidence acquisition | Deep Research | findings, each a quote in a captured source |
| 9 | Evidence acquisition | Structured collection | a declared protocol to a dated sample (new) |
| 10 | Processing | Reconciliation and manifest | every input made comparable, in one manifest |
| 11 | Processing | Declared preparation | transforms fixed before any result |
| 12 | Analysis | Model | the quantitative model, where the study type needs one |
| 13 | Analysis | Sociomap | two map types, configurations pluggable |
| 14 | Analysis | Results and interpretation | what the results mean, in points |
| 15 | Output | Osnova | the report's structure, every point sourced |
| 16 | Output | Report and release | the report and its two release states |
| 17 | Cross-cutting | Evidence ledger and grades | every number with its source and grade |
| 18 | Cross-cutting | Method register (Metodika) | which method version is approved |
| 19 | Cross-cutting | Cost and wallet | every paid step under a ceiling |
| 20 | Cross-cutting | Acceptance cases | fictional cases with planted answers |

---

## 4. Module specs

Each spec has the same headings: Purpose · Contract · Tailored from · Proposes · Valve · Today · To build
· Acceptance fixture · Not in the MVP.

### Module 1. Lead

**Purpose.** The user's one conversation partner. It turns what the user says into a proposed study plan,
presents every worker's proposal as a card or an edit, reports progress in words, and asks for the yes
at every valve. It starts nothing on its own.

**Contract.**
- In: the user's message, the study's frozen context (layers declared in
  `aia_core/domain/lead_context.py:83 @ b4fb2081c`, `LEAD_LAYERS`), the active stage's contract.
- Out: a closed `LeadOutput` (`aia_core/domain/research_lead.py:450 @ b4fb2081c`): a reply, at most three
  view operations (`:454`), edits, one request, a follow, a self-update (`:427`).
- Owner: `ResearchLead` (`aia_core/application/research_lead.py:655 @ b4fb2081c`).

**Tailored from.** The study type and Zadání (module 5) decide which stages the plan contains. The user's
USER file and preferences decide tone and explanation depth. Each stage's specification (module 4) decides
what the Lead can point at there.

**Proposes.** The study plan (MOD-1.1), the next step, and every card the workers return. The Lead itself
is the worker of the study plan; specialist workers are module 3's.

**Valve.** Every card: an edit accepted or dismissed (`application/research_lead.py:1122`,
`decide_edits`), a request approved (`:1308`, `approve_request`). A typed start command is the user's
own (`aia_core/domain/lead_commands.py:96 @ b4fb2081c`).

**Today.** Built for the survey lane: hatching, conversation, cards, edits, queued messages, typed
commands, the context manifest (ADR 0026, ADR 0030, ADR 0041). The plan as one approved object is planned,
not built (`lead-orchestration#LO3`, `#LO4`), as is the continuation turn after a finished step (`#LO6`).
Its context layers and its targets are survey-shaped: the eleven stages of
`apps/web/src/lib/workbench-stages.ts:16-19 @ b4fb2081c` (brief, design, questionnaire, audience,
dimensions, sample, fieldwork, results, sociomap, analysis, report).

**To build.**
- `lead-orchestration#LO3`, `#LO4`: the plan and its card. `#LO6`: the continuation turn. `#LO9d`: every
  stage worker gets its declared inputs. `cost-model-study#CP9`: the Lead on business records.
- **MOD-1.1** The study plan for a business study: the stages the study type composes (§ 5), each with
  its valve and its quoted ceiling, approved once and stopping at every valve it does not cover.
- **MOD-1.2** The Lead's context layers for the business stages: the manifest, the preparation, the model
  and map outputs as typed summaries, never raw tables.
- **MOD-1.3** The Lead's targets for the business stages (factor, source, contract, assumption,
  configuration, point), added to `TargetKind` (`aia_core/domain/lead_artifacts.py:109-132`) and the web's
  copy, both held to the contract fixture.

**Acceptance fixture.** From one sentence, the Lead proposes a plan whose stages and valves equal the
study type's composition. Cost decision: the plan contains Model and the scenario maps. Competitor
analysis: the plan contains no Model stage and proposes the financial-profile and expert configurations.
On the scripted Lead, zero paid calls.

**Not in the MVP.** The Lead running a plan across several studies; the Lead choosing a study type the
catalogue does not hold.

### Module 2. Study engine

**Purpose.** Holds a study's stages, each stage's state and its artifacts, and invalidates what an
upstream change makes stale. It runs paid steps as durable workflow steps, never in the API.

**Contract.**
- In: the approved study plan (module 1), each stage's accepted artifact.
- Out: each stage's state (empty, proposed, accepted, running, done, stale) and the impact of a change on
  every downstream stage.
- Owner: the workflow engine (`aia_core/infrastructure/workflow_repository.py:3864 @ b4fb2081c`,
  `WorkQueue`; `aia_core/domain/workflow_templates.py:144`, `steps_for_workflow`), the pipeline's impact
  rule (`aia_core/domain/pipeline.py:531`, `stage_impacts`).

**Tailored from.** The study type's composition: which stages exist, in which order. Module 5 says
whether the model stages appear (ADR 0046 decision 3,
`docs/architecture/adr/0046-business-decisions-pivot.md:233-262 @ b4fb2081c`).

**Proposes.** Nothing; it is the record. Re-runs are proposed by the Lead.

**Valve.** Starting a paid stage; re-running a stale one.

**Today.** Built for the survey pipeline: durable runs, leases, recovery, budget waits, the impact rule
with CHANGED and RECHECK per stage. The stage a study was left on is now recorded with its workbench stage
(`aia_core/infrastructure/study_workspace_repository.py:633 @ b4fb2081c`, `record_stage`, #1147). The
business study's stage track is planned, not built (`research-findings-stage#FND1`,
`cost-model-study#CP3`); `STAGE_KEYS` are the survey's steps (`aia_core/domain/workspace.py:81`).

**To build.**
- `cost-model-study#CP3`, `research-findings-stage#FND1`: the one study's stage track.
- **MOD-2.1** The business stages' impact rule: each stage's input fingerprint over its upstream
  artifacts, so a change in Zadání, a contract or the manifest marks exactly the stages that read it.
- **MOD-2.2** The stage track composed from the study type (module 5) instead of a fixed list, the
  composition stored with the study.

**Acceptance fixture.** Changing one factor in the competitor analysis's manifest marks preparation, the
map and the outline stale and leaves Zadání, Rešerše and the contracts current. Changing the discount
rate in the cost decision marks the model, the results, the maps and the outline stale.

**Not in the MVP.** Branching a study into variants; partial re-runs inside one stage.

### Module 3. Worker registry

**Purpose.** Every worker the Lead may call, written once: its task, its output contract, what it is
shown, its material rules, its capability, its reservation, its prompt, its switch, its card kind.

**Contract.**
- In: a `LeadWorkerSpec` row (`aia_core/domain/lead_workers.py:88 @ b4fb2081c`).
- Out: a registered worker, refused by name if any field is missing or malformed
  (`:171`, `WorkerRegistry`). Rows held to `tests/fixtures/lead_workers/workers.json`.

**Tailored from.** Nothing at registration. At run time a worker is given its stage's declared inputs
(`lead-orchestration#LO9d`), which is how each stage's proposal is built from the stage before.

**Proposes.** n/a: it registers the workers that propose.

**Valve.** n/a. A worker's switch and its reservation key are deployment settings
(`lead_workers.py:82-85`), not per-study choices.

**Today.** The registry is built. Its eight rows are the survey's design workers
(`aia_core/domain/research_agents.py:38-46 @ b4fb2081c`: analyze_brief, build_questionnaire,
optimize_questionnaire, propose_audience, suggest_dimensions, critique_design, design_copilot,
answer_memory; registered at `:953`). The results workers are planned (`lead-orchestration#LO9b`,
`#LO9c`).

**To build.** Each business worker as one row, with its closed output contract and its fixture:
- **MOD-3.1** `propose_factors`: from Zadání's question and frameworks, the factor families and factors,
  each with its direction and why it matters.
- **MOD-3.2** `plan_sources`: for each factor, its source (a client contract, a public route, a Deep
  Research subject, a collection protocol) and its expected grade.
- **MOD-3.3** `propose_configuration`: from the prepared table's shape (where the rows come from, whether
  the objects share a scale, how the rows depend), the Sociomap type and configuration, with the
  declarations it implies.
- **MOD-3.4** `propose_stage_spec`: module 4's specification for a stage.
- **MOD-3.5** `propose_points`: interpretation points from the results and the map (with
  `lead-orchestration#LO9b`).
- `cost-model-study#CP9` covers the model-side proposals (assumptions, options).

**Acceptance fixture.** Each worker's recorded answer for both worked examples, validated against its
output contract; a row with a missing field is refused by name (the registry's own tests in
`packages/aia_core/tests/`).

**Not in the MVP.** Workers an organization defines itself.

### Module 4. Adaptive study surface

**Purpose.** The tailoring principle of § 2 as a module: per study and per user, a stage specification
for each stage, proposed by a worker, rendered by the client, stored, and invalidated with its inputs.

**Contract.**
- In: the stage's contract (`aia_core/domain/lead_artifacts.py:196-225 @ b4fb2081c`), its upstream
  artifacts, the study type, the user's USER file and preferences.
- Out: a **stage specification** (§ 2.2): components from the closed vocabulary, bindings to item ids,
  order and grouping, defaults marked proposed, an explanation level per component; a fingerprint of its
  inputs.
- Owner: new, beside `lead_artifacts.py`; the web's renderer beside `workbench-artifacts.ts`.

**Tailored from.** Everything upstream, by definition (§ 2.1).

**Proposes.** `propose_stage_spec` (MOD-3.4). The default specification of each stage, per study type,
is data an administrator approves, not a model output.

**Valve.** None for display. The user sees a one-line note "tailored for this study" with Undo and
"Show the standard form". A specification that would move or drop a valve is refused by code before the
user sees it (§ 2.3).

**Today.** The contract rows and their fixture are built and held on both sides
(`tests/fixtures/lead_artifacts/contract.json`). Screens are hand-built per stage
(`apps/web/src/components/rehome/research/`). No stage is rendered from a specification; no study stores
one. The view operations are live (`lead_artifacts.py:84-95`).

**To build.**
- **MOD-4.1** The stage specification as a type: the component vocabulary, bindings to item ids, order,
  defaults, explanation level; its checks of § 2.3 (valves present and in place, no numeric component, no
  grade relabelled); a fixture shared by the server and the web.
- **MOD-4.2** The renderer: the client draws a stage from its specification with existing design-system
  components only; an unknown component is refused and the stage falls back to its default form.
- **MOD-4.3** Storage and invalidation: the specification stored per study and stage as an artifact,
  fingerprinted, marked stale through module 2's impact rule.
- **MOD-4.4** The user side: "tailored" note, Undo, the standard form, and the two new preferences
  (explanation level, preferred visuals) beside `auto_accept_text_edits`.
- **MOD-4.5** The default specification of each business stage for each study type, approved as data.

**Acceptance fixture.** The same Data stage renders two different, valid specifications for the two
worked examples (the competitor analysis asks for statements and a price basket; the cost decision for
the purchase history and the plant offer). A specification that drops the contract valve is refused. A
user who sets "short explanations" sees the competitor analysis's Předpoklady without the full help text,
and "Show the standard form" restores it.

**Not in the MVP.** Tailoring the order of the stages themselves (module 2 owns it); tailoring the report's
layout (module 16 owns it); learning preferences from behaviour.

### Module 5. Zadání and study type

**Purpose.** Fixes what the study is for: the decision, its owner, the question, the decision rule, the
frameworks, and the study type, which is the composition of modules the rest of the study follows.

**Contract.**
- In: the user's first sentence and any files they give.
- Out: the business Zadání as data (`decision-brief#DB0`: decision and goal; options and constraints;
  rule and risk; customers; data and uncertainties; execution), the selected frameworks
  (`analysis-frameworks#AF0`, `#AF1`), and the study type with its composition.
- Owner: the study's working content; the rule frozen before results (`decision-brief#DB3b`).

**Tailored from.** The user's first sentence. The study type then tailors every later stage.

**Proposes.** Triage as an ordinary Lead turn (`decision-brief#DB2`): the eight parts with their sources,
the study type, the frameworks (`analysis-frameworks#AF1`).

**Valve.** The brief and the decision rule, frozen before any result (`decision-brief#DB3b`,
`cost-model-study#CR0`'s analytical contract).

**Today.** The survey brief is built (stage `brief` in `aia_core/domain/lead_artifacts.py:259-271
@ b4fb2081c`). The business Zadání is planned, not built (`decision-brief` DB0–DB6, all open;
`analysis-frameworks` AF0–AF10, all open).

**To build.**
- `decision-brief#DB0`–`#DB5`, `#DB3b`; `analysis-frameworks#AF0`–`#AF2`, `#AF6`.
- **MOD-5.1** The study-type catalogue as data: each type's composition (§ 5), its default frameworks and
  its default stage specifications; two types in the MVP.
- **MOD-5.2** The level choice for comparative studies (entities: chains or single outlets), stored in
  Zadání, because it decides which factors can be sourced.

**Acceptance fixture.** Cost decision: from the case's one-sentence brief, the rule (measure, thresholds,
gates) is captured and frozen. Competitor analysis: "Compare the pharmacy chains we could sell through"
yields the competitor-analysis type, the level "chains", the perspective "a supplier choosing channel
partners", and no Model stage.

**Not in the MVP.** Study types beyond the two; a study that changes type after Zadání is frozen.

### Module 6. Client data contracts

**Purpose.** The client's own files become datasets under a contract: what each column means, its unit
and period, its grade, and what the analysis may do with it.

**Contract.**
- In: files the client gives, kept as the client's sources
  (`aia_core/infrastructure/client_source_repository.py:135 @ b4fb2081c`), each read with locators
  (`aia_core/infrastructure/source_reading.py:656`, `read_source`; `aia_core/domain/client_sources.py:225`,
  `SourceReading`).
- Out: an accepted data contract and a scoped analysis copy (`client-data-in-analysis` 2–3b, 10).

**Tailored from.** Module 5's data needs and module 3's source plan (MOD-3.2): the stage asks for exactly
the files the plan names, and proposes each column's meaning from the file's reading.

**Proposes.** The contract per file: column meanings, units, periods, personal columns, grade.

**Valve.** Each contract.

**Today.** Client sources, their readings and the intake are built (`client_sources.py`,
`source_reading.py`; the intake sheet in the web). Data contracts and analysis copies are planned
(`client-data-in-analysis` 0–12, only 8a done).

**To build.** `client-data-in-analysis#2`, `#2a`, `#3`, `#3a`, `#3b`, `#10`, `#11`, and the new `#13`
(units, currencies, periods, cost scope with dispositions, MVP-SCOPE.md § 2.9).

**Acceptance fixture.** Cost decision: the purchase file's planted traps (a volume in kg, a price in USD, a
spot purchase) are each caught at the contract. Competitor analysis: a client's own sales file by chain
is contracted with its period and currency; a column naming a pharmacist is flagged personal.

**Not in the MVP.** Live connections to the client's systems.

### Module 7. Public data routes

**Purpose.** Records from public registers and statistics, fetched by code under each source's licence and
rate limit, every admitted value equal to what the source returned.

**Contract.**
- In: a source request from the source plan (MOD-3.2): a register, an entity, a field, a period.
- Out: typed records with source, licence, as-of date and locator; never a value a model wrote.
- Owner: `public-data-routes`; retrieval through `RetrievalGate`
  (`aia_core/application/web_retrieval.py:534 @ b4fb2081c`), the only way a query or URL leaves.

**Tailored from.** The factors (MOD-3.1) and the level (MOD-5.2): the competitor analysis asks the
pharmacy register and the statements; the cost decision asks exchange rates and statistics.

**Proposes.** The route and the query per factor; the cost of each priced route.

**Valve.** Each route's cost and licence, once per study.

**Today.** The plan exists with no route built (`public-data-routes` PDR0–PDR10, all open). It covers
SDMX (PDR1), ČNB (PDR2), ARES and the commercial register (PDR6) and Sbírka listin statements (PDR7). It
has **no route for SÚKL's register of pharmacies** and none for ČSÚ population by municipality.

**To build.**
- `public-data-routes#PDR0` (the source register), `#PDR2`, `#PDR6`, `#PDR7`.
- **MOD-7.1** The SÚKL pharmacy register as a route: each pharmacy's operator, address and opening hours,
  with its as-of date. Its licence and its update rhythm confirmed first (**hypothesis**: SÚKL publishes
  the register as open data; not yet checked).
- **MOD-7.2** ČSÚ population per municipality as a route, for density per inhabitant.

**Acceptance fixture.** Competitor analysis: from recorded responses, the statements of three fictional
chains are read with every value located (page and line) and reviewed; the register gives each chain's
count of pharmacies. Cost decision: the ČNB rate for a stated date equals the recorded answer byte for
byte.

**Not in the MVP.** Paid commercial databases (PDR10 stays a buy-or-build decision); ČÚZK (PDR9).

### Module 8. Deep Research

**Purpose.** What registers and the client's files do not hold, found on the web: every finding a quote in
a captured source of the same track, typed values extracted from accepted quotes only.

**Contract.**
- In: subjects from the frameworks and the source plan, frozen at enqueue with the study's chosen
  knowledge.
- Out: a sealed bundle of findings, sources and gaps (`aia_core/application/deep_research.py:476
  @ b4fb2081c`, `DeepResearchRuns`); typed values once `deep-research-v2#DRV3` lands.

**Tailored from.** The frameworks (`analysis-frameworks#AF3`: each framework that needs research becomes
subjects) and the source plan: only factors no route or contract covers become subjects.

**Proposes.** The research plan and its ceiling.

**Valve.** The run and its ceiling; a captured source added to knowledge only by a person
(`aia_core/application/verified_sources.py:47`, "Ověřeno, přidat zdroj").

**Today.** Built: the six steps, grounding, the gate, recorded and live routes, priced holds. Survey-shaped
in its targets (Design and Interpretation Research over a survey design). Typed extraction, citation
recall and credibility v2 are planned (`deep-research-v2` DRV0–DRV9, all open).

**To build.** `deep-research-v2#DRV1`, `#DRV2`, `#DRV3`, `#DRV5`; `analysis-frameworks#AF3`.

**Acceptance fixture.** Competitor analysis: on the recorded web, each chain's services (vaccination,
e-prescription reservation, delivery) are found as quotes in captured pages; a page that names no chain
is not a finding. Cost decision: the case pack's public values are found and typed with their as-of date.

**Not in the MVP.** Scheduled monitoring (DRV8); as-of research beyond the index (DRV7).

### Module 9. Structured collection

**Purpose.** New. Data no register, file or web page holds, collected by a declared protocol: a price
basket sampled at named outlets on a date, a mystery-shopping checklist, an expert scoring form. The
output is a dated sample with its protocol, never an estimate.

**Contract.**
- In: a protocol: what is measured (items, criteria), where and when (outlets, dates), by whom, the scale
  and the direction, the sample size, and how a missing value is recorded.
- Out: a dated sample as a dataset with its protocol and its collector, graded as a sample.

**Tailored from.** The factors that only collection can source (MOD-3.2); the level (chains or outlets).

**Proposes.** The protocol, from the factors; the outlets from module 7's register.

**Valve.** The protocol and its cost before collection; the sample when it is in.

**Today.** Not built. The expert scoring form is planned in `situation-reports#EX1` (named experts, a
scoring form over objects × criteria with scale ends and direction). No price-basket or mystery-shopping
protocol exists anywhere in the plans.

**To build.**
- `situation-reports#EX1`: the expert scoring form.
- **MOD-9.1** The collection protocol as data (items, outlets, dates, scale, direction, missing values),
  and its sample as a dataset with origin "collected".
- **MOD-9.2** The entry form: a person enters the sample against the protocol, each value with its outlet
  and date; a value outside the protocol is refused.
- **MOD-9.3** The price basket as the first protocol kind: a fixed list of products, the price and the
  co-payment per outlet, dated.

**Acceptance fixture.** Competitor analysis: a 20-item basket at 12 fictional outlets, one outlet entered
in the wrong currency and one item off the list, both caught. Cost decision: ten experts score the sites on
four criteria; a score outside 0–10 is refused.

**Not in the MVP.** Collection by a mobile app in the field; paid panels.

### Module 10. Reconciliation and manifest

**Purpose.** Makes every input comparable and puts it in one manifest: each value with its unit, currency,
period, scope, source and grade, every conversion declared, every disposition recorded.

**Contract.**
- In: contracted datasets (module 6), route records (7), typed findings (8), samples (9).
- Out: the parameter manifest (`cost-model-study#CP1b`): every input, fixed or ranged, with unit, period,
  locator, grade attributes, owner and dependencies.

**Tailored from.** The factors and the sources: the competitor analysis reconciles accounting standards,
financial years and group versus local statements; the cost decision reconciles units, currencies and
price years.

**Proposes.** Each conversion and each disposition (kept, converted, excluded with its reason).

**Valve.** The manifest.

**Today.** Not built. Planned: `cost-model-study#CP1b`, `#CR1b`, `client-data-in-analysis#13`.

**To build.** `cost-model-study#CP1b`, `#CR1b`; `client-data-in-analysis#13`.
- **MOD-10.1** Comparability rules for entities across firms: accounting standard (IFRS or Czech), the
  financial year, consolidated or local, online-only or not; a pair that cannot be made comparable is
  marked so, never averaged.

**Acceptance fixture.** Competitor analysis: one fictional chain reports under IFRS with a June year end;
its ratios are restated or marked not comparable, and the manifest says which. Cost decision: the purchase
file's kg row and USD row are converted and declared.

**Not in the MVP.** Automatic restatement between accounting standards; the manifest across studies.

### Module 11. Declared preparation

**Purpose.** Fixes, before any result is seen, how each variable is transformed for analysis: direction,
scaling, logs, detrending, which rows are excluded and why.

**Contract.**
- In: the manifest (module 10).
- Out: a preparation declaration per variable, frozen, with its fingerprint.
- Owner: `sociomapa-systemu#SYS2` (declared preprocessing per variable) and the analytical contract
  (`cost-model-study#CR0`).

**Tailored from.** The variables' kinds and the configuration proposed (MOD-3.3): ratios get a direction
and robust standardisation; size figures a log; monthly series detrending; ratings row centring.

**Proposes.** The declaration per variable, with the reason.

**Valve.** The declaration, frozen before any result. A change after the freeze is a new revision, and the
report says so.

**Today.** Not built. The engine's own preparation for respondent ratings is built (per-person centring in
`aia_core/domain/sociomap/signed_off_inputs.py`, read by `compute_object_map`,
`aia_core/domain/sociomap/engine_v2.py:887 @ b4fb2081c`).

**To build.** `sociomapa-systemu#SYS2`, `#SYS3`.
- **MOD-11.1** Direction alignment: each variable declares whether higher is better, and the declaration
  is printed beside every map and table that reads it.

**Acceptance fixture.** Competitor analysis: debt/equity declared "lower is better" is inverted before
standardisation; a declaration changed after a result is seen is a new revision the report names.

**Not in the MVP.** Learned transformations.

### Module 12. Model

**Purpose.** Where the study type needs one: the quantitative model, its futures and its certified
results. The competitor analysis does not use this module.

**Contract.**
- In: the manifest and the frozen rule.
- Out: model results with their convergence state; each decisive comparison resolved or printed as an
  interval.

**Tailored from.** Zadání's options and rule; the manifest.

**Proposes.** Assumptions and their distributions (`cost-model-study#CP9`).

**Valve.** The model's assumptions; each paid run's ceiling.

**Today.** Not built: `cost-model-study` CP1–CR10 all open. Its scope, chunks and waves are MVP-SCOPE.md
§ 2.5–2.6 and § 7.

**To build.** As MVP-SCOPE.md § 2.9: `cost-model-study#CP1`–`#CP9`, `#CM7`, `#CM8`, `#CR3`, `#CR3b`,
`#CR6`, `#CR6b`, `#CR7b`, `#CR10b`; `quantitative-families#FIN1`, `#FIN2`. No `MOD-` chunk.

**Acceptance fixture.** The oracle fixtures O-CF and O-INFO (MVP-SCOPE.md § 6), then the cost decision's
case pack.

**Not in the MVP.** Model types beyond the cost scenario (MVP-SCOPE.md § 5).

### Module 13. Sociomap

**Purpose.** Shows which objects the rows rate alike, by one engine and two map types. The configuration
is pluggable: a new study type adds a configuration, never an engine.

**Contract.**
- In: the prepared table and a declared configuration (MOD-3.3).
- Out: the map (positions, terrain where defined), the configuration's test result, its tables, its
  register status.
- Owner: the engine (`aia_core/domain/sociomap/engine_v2.py:887 @ b4fb2081c`, `compute_object_map`, under
  `AIA_SOCIOMAP_V5`, `aia_core/domain/sociomap/specification.py:1611`); the register
  (`aia_core/domain/sociomap_register.py:52`).

The two types and their configurations (methodology v5, chapter 9; MVP-SCOPE.md § 2.7):

| Type | Configuration | A row is | The test |
|---|---|---|---|
| Scenario map (rows the model generates) | futures | one draw of the model | stability across declared assumptions and seeds, Spearman of distances ≥ 0,8; no p-value |
| | weight settings | one weight setting around the client's centre | the same, plus shares first / tied per scenario |
| | futures × weights | one future under one weight setting | both |
| Observed-data map (rows observed) | experts | one named expert × one criterion | experts resampled whole; one radius |
| | units | one unit | units bootstrapped, by cluster where they cluster |
| | months | one month | surrogates with Benjamini–Yekutieli; block bootstrap |
| | **financial profile (proposed)** | one ratio or figure; the objects are the entities | resampling by ratio family |

**The financial-profile configuration is proposed, not decided.** It positions entities (the chains) by
the shape of their profile over ratios: each ratio standardised across the entities (median and MAD),
its direction aligned, resampled by family (profitability, liquidity, leverage, growth, efficiency). It
changes no rule of the observed-data type: the two declarations already cover it (scale not shared;
rows clustered by family). It needs a planted-answer fixture and the methodology owner's approval in the
register, like every configuration.

**Tailored from.** The prepared table's shape: where the rows come from, whether the objects share a
scale, how the rows depend. The configuration is proposed from those three facts (MOD-3.3), never chosen
after seeing a map.

**Proposes.** The configuration and its declarations.

**Valve.** The configuration, before the map is computed; the map's register status is read, never
chosen.

**Today.** The engine and the register are built, approved for respondent ratings (`aia-sociomap-5`).
The respondent map is not part of the business MVP (owner, 9 November). The two business types are planned
(`sociomapa-systemu` SYS0–SYS13, open). A demonstration of every configuration on the engine exists as a
page, not as product code (the lifecycle page, `MVP-SCOPE.md` § 2.7's illustrations).

**To build.** `sociomapa-systemu#SYS1`, `#SYS1b`, `#SYS2`–`#SYS13`; `cost-model-study#CS1`–`#CS5`;
`situation-reports#EX2`.
- **MOD-13.1** Configurations as data: each configuration a row (row source, preparation, relation,
  test, height, never-claims), so a study type adds a row, not code paths.
- **MOD-13.2** The financial-profile configuration: its preparation, its family resampling, its
  planted-answer fixture, its register entry for the methodology owner.

**Acceptance fixture.** Every configuration finds the structure planted in its fixture. Competitor
analysis: three fictional chains planted with the same profile shape sit together on the financial-profile
map, a fourth planted apart sits apart, and the family resampling's radius covers them. Cost decision: the
scenario map's planted option clusters, as in the lifecycle page's fixtures.

**Not in the MVP.** The respondent map for business studies; regimes in monthly series without a declared
break.

### Module 14. Results and interpretation

**Purpose.** Turns the model's results, the maps and the tables into interpretation points: each a
sentence with the numbers it rests on, its grade, and what it may not claim.

**Contract.**
- In: model results (12), maps and tables (13), Interpretation Research beside them, never as evidence.
- Out: interpretation points, each linked to its admitted claims.

**Tailored from.** The frameworks (AF6 gives each framework its point slots: SWOT's four quadrants,
Porter's five forces) and the decision rule: points are written toward the decision.

**Proposes.** Points (MOD-3.5, `lead-orchestration#LO9b`).

**Valve.** Each point.

**Today.** Interpretation Research is built (`application/deep_research.py`'s interpretation purpose,
ADR 0021). The analysis modules are survey-shaped (eight modules over respondent data). Points as an
object are planned (`research-findings-stage#FND3`).

**To build.** `research-findings-stage#FND3`, `#FND10`; `lead-orchestration#LO9b`, `#LO9c`.

**Acceptance fixture.** Competitor analysis: a point "chain A and chain B have similar financial profiles"
links to the map and the ratio table; a proposed point naming a cause is refused by the never-claims. Cost
decision: the decision boundary is printed with its resolution state.

**Not in the MVP.** Points across studies.

### Module 15. Osnova

**Purpose.** The report's structure with the prose taken out: every point, number and visual in the order
the report will make them, each linked to its source or method. A point whose link does not resolve
cannot reach the report.

**Contract.**
- In: accepted points (14), tables and graphs built from them.
- Out: the outline as data (`research-findings-stage#FND0`), with its stops.

**Tailored from.** The frameworks' chapters (`analysis-frameworks#AF6`) and the study type's default
outline.

**Proposes.** The outline, a point, a visual or a move (`research-findings-stage#FND7`).

**Valve.** Each stop closed by the researcher (`research-findings-stage#FND8`).

**Today.** Not built (`research-findings-stage` FND0–FND12, open).

**To build.** `research-findings-stage#FND0`–`#FND9`, `#FND13`; `cost-model-study#CP8b`.

**Acceptance fixture.** Competitor analysis: the outline holds a ranked table, the financial-profile map and
a SWOT whose quadrants each carry a sourced point; a point with a broken link is held back. Cost decision:
the outline's points match the case pack's answer key.

**Not in the MVP.** The shared review with the client's decision-makers (FND12).

### Module 16. Report and release

**Purpose.** The report written around exactly the outline's closed points, edited in the report editor,
exported, and released under the release rule: a labelled *předběžná* draft, or an approved
recommendation when its three conditions hold.

**Contract.**
- In: the closed outline (15).
- Out: the report as a document model, DOCX and PDF, its approval, its release state.
- Owner: the renderer (`aia_core/infrastructure/report_docx/renderer.py:48 @ b4fb2081c`), the editor
  (`aia_core/application/report_editor.py:81`), the approval (`aia_core/application/report_approval.py:139`).

**Tailored from.** The outline. The report's sections follow it; nothing is added that the outline does
not hold.

**Proposes.** The prose around each point (`research-findings-stage#FND9`).

**Valve.** The approval. An approved recommendation needs methods approved in the register, the
independent review, and every decisive comparison resolved (R9, MVP-SCOPE.md § 1; methodology v5
chapter 13).

**Today.** Built for the survey lane: the document model, DOCX, PDF, the report editor, approvals, client
report checks. The release states and the business report are planned (`report-delivery#RD13`,
`research-findings-stage#FND9`).

**To build.** `research-findings-stage#FND9`, `#FND13`; `report-delivery#RD1`, `#RD3`, `#RD13`;
`cost-model-study#CP8`.

**Acceptance fixture.** Competitor analysis: the report prints every number with its grade and source; a
report whose method is not yet in the register is *předběžná* and says so. Cost decision: the report with
an unresolved comparison cannot be approved as a recommendation.

**Not in the MVP.** Client-branded templates beyond the current recipes.

### Module 17. Evidence ledger and grades

**Purpose.** Every number that reaches a result, an outline or a report is an admitted claim with its
source and its grade. Prompts state the rules; code enforces them.

**Contract.**
- In: a number and its source (an artifact by id and SHA-256, a manifest entry, a model output).
- Out: an `AdmittedClaim` (`aia_core/domain/evidence/admission.py:188 @ b4fb2081c`), minted only by
  `admit_numeric_claims` (`:298`); the report's ledger (`aia_core/domain/report/evidence.py:74`).

**Tailored from.** Nothing. The ledger is the same for every study and every user.

**Proposes.** n/a.

**Valve.** n/a: admission is code, not a choice.

**Today.** Built for respondent evidence (field policy, joint structure, support, intervals, tiers).
Business grades are planned (`cost-model-study#CP8`, `#CP8b`).

**To build.** `cost-model-study#CP8`, `#CP8b`.
- **MOD-17.1** Grades for collected samples (module 9) and public records (module 7): "measured", with
  the as-of date and the source; a sample's grade carries its size and its date.

**Acceptance fixture.** A number typed into the outline without a source is refused; a register value
reaches the report with its as-of date.

**Not in the MVP.** Grades combined across studies.

### Module 18. Method register (Metodika)

**Purpose.** Which method version, at which exact specification, is approved for which use. A map or a
model result is internal until its configuration's entry is approved by the methodology owner.

**Contract.**
- In: a method version and its specification fingerprint.
- Out: its register status, read whenever a result is read
  (`aia_core/domain/sociomap_register.py:52 @ b4fb2081c`); the methodology in force per organization
  (`aia_core/infrastructure/methodology_repository.py:233`).

**Tailored from.** Nothing. Tailoring never changes a method or its status (§ 2.3).

**Proposes.** n/a. The methodology owner proposes and approves.

**Valve.** The methodology owner's approval of each entry.

**Today.** Built: the register, Metodika's catalogue and versions
(`aia_core/domain/methodology/catalogue.py:263`, `MethodModule`), activation by the Metodik mark.

**To build.** `sociomapa-systemu#SYS12`: one entry per configuration.
- **MOD-18.1** Register entries for the business configurations, including the financial profile if it
  is adopted.

**Acceptance fixture.** A map computed by a configuration without an approved entry prints as internal;
approving the entry changes its status on the next read, not the stored map.

**Not in the MVP.** Methods an organization writes itself.

### Module 19. Cost and wallet

**Purpose.** Every paid step runs under a ceiling, quoted before the user's yes, held before the call, and
settled once.

**Contract.**
- In: a step's quoted ceiling.
- Out: a hold and its settlement; the study's remaining budget.
- Owner: the money rules (`aia_core/domain/money.py:195 @ b4fb2081c`, `threshold_verdict`), the wallet
  (`aia_core/domain/wallet.py:90`, `effective_cap`; `aia_core/infrastructure/study_wallet_repository.py:68`).

**Tailored from.** Nothing; the ceiling is quoted per step.

**Proposes.** The ceiling, with each card.

**Valve.** Spend above the study's threshold; a budget lift.

**Today.** Built for model calls and priced tool calls.

**To build.**
- **MOD-19.1** Ceilings for priced public routes (module 7) and for collection protocols with a cost
  (module 9), on the same ledger.

**Acceptance fixture.** The competitor analysis's plan quotes one ceiling per paid stage; a route call that
would exceed the remaining budget waits for the user.

**Not in the MVP.** Billing a client.

### Module 20. Acceptance cases

**Purpose.** Each study type proves its modules on a fictional case whose answers are planted in advance.
A module passes when it finds the planted answer, and fails visibly when it does not.

**Contract.**
- In: a case pack: the client's files, documents, data, a brief, an answer key kept apart.
- Out: a pass or fail per module and per planted answer, recorded over HTTP on recorded doubles.
- Owner: `tests/acceptance/` (`test_mvp_acceptance.py`), `mvp-master-plan#MP17`.

**Tailored from.** n/a.

**Proposes.** n/a.

**Valve.** n/a.

**Today.** The harness exists (`tests/acceptance/`). Case packs: Velis (`prototypes/case-velis/`, merged)
and ChemVitro (#1155, open). No competitor-analysis case pack exists.

**To build.** `mvp-master-plan#MP17`; `research-findings-stage#FND14`.
- **MOD-20.1** A competitor-analysis case pack: four to six fictional pharmacy chains with statements in
  both accounting standards, a register extract, recorded web pages, a price basket and an answer key
  (the planted profile clusters, one non-comparable statement, one basket error).

**Acceptance fixture.** The case packs themselves, run end to end with zero paid calls.

**Not in the MVP.** Cases with real client data.

---

## 5. The two study types as compositions

| # | Module | The cost decision | The competitor analysis (pharmacies) |
|---|---|---|---|
| 1 | Lead | used | used |
| 2 | Study engine | all stages | no Model stage |
| 3 | Worker registry | the model's workers (CP9) | propose_factors, plan_sources, propose_configuration |
| 4 | Adaptive study surface | used | used |
| 5 | Zadání and study type | decision rule with gates | comparative question, level (chains), perspective |
| 6 | Client data contracts | purchase history, offers, site data | the client's own sales by chain, if any |
| 7 | Public data routes | rates, statistics | SÚKL register, Sbírka listin, ARES, ČSÚ |
| 8 | Deep Research | public values for the model | services, e-shops, hours not in a register |
| 9 | Structured collection | expert scores (optional) | price basket, service checklist |
| 10 | Reconciliation and manifest | units, currencies, price years | accounting standard, financial year, group vs local |
| 11 | Declared preparation | per input, for the model | direction, robust scaling, logs per ratio |
| 12 | Model | used | **not used** |
| 13 | Sociomap | scenario map: futures, weight settings, crossed | observed-data map: financial profile (proposed), experts |
| 14 | Results and interpretation | the decision boundary, value of information | profiles, positions, price and service gaps |
| 15 | Osnova | the answer key's points | ranked table, map, SWOT, per-chain profiles |
| 16 | Report and release | R9, recommendation eligible when resolved | R9, *předběžná* until the configuration is registered |
| 17–19 | Ledger, register, wallet | used | used |
| 20 | Acceptance cases | ChemVitro | the new pharmacy pack (MOD-20.1) |

### The competitor analysis, end to end

What happens, stage by stage, from the user's first sentence to the report, and what is tailored at each
step.

1. **The user:** "We sell medical devices through pharmacies. Compare the chains we could work with."
2. **Zadání (5).** The Lead proposes the competitor-analysis type, the level "chains", the perspective
   "a supplier choosing channel partners", the frameworks (competitor profiles, SWOT, a ranked table).
   *Tailored:* no Model stage; the rule is a ranking with stated criteria, not a cost threshold. **Valve:**
   the brief and the criteria, frozen.
3. **Factors (3, MOD-3.1).** The Lead proposes factor families weighted for a supplier: reach, revenue
   mix, payables days (payment discipline), digital, then profitability and growth. *Tailored:* the
   families and their order follow the perspective; a chain-benchmarking user would see price, service and
   location first. **Valve:** the factor list.
4. **Sources (3, MOD-3.2; 4).** Each factor gets its source: statements (Sbírka listin), the SÚKL
   register, Deep Research for services, a price basket. *Tailored:* the Data stage shows only these four
   source kinds, in this order. **Valve:** the source plan and its ceilings.
5. **Collection (6, 7, 8, 9).** Routes fetch the register and the statements; Deep Research finds the
   services; the user enters the basket against its protocol. *Tailored:* the basket's items follow the
   client's product range from Zadání. **Valves:** each route's cost, the Deep Research run, the
   protocol.
6. **Manifest (10).** Statements reconciled: one chain's IFRS accounts and June year end restated or marked
   not comparable. *Tailored:* the comparability checklist shows only the issues these sources raise.
   **Valve:** the manifest.
7. **Preparation (11).** Directions declared (payables days: lower is better for the supplier); ratios
   standardised robustly; revenue logged. *Tailored:* help text at the user's explanation level.
   **Valve:** the declaration, frozen.
8. **Map (13).** The Lead proposes the financial-profile configuration: rows are ratios, objects are
   chains, resampled by family; and, if experts scored the chains, an expert map beside it. *Tailored:* the
   map stage shows the ranked table first for a user who prefers tables. **Valve:** the configuration.
9. **Interpretation (14).** Points: which chains share a profile, which lead on reach, where the price
   basket shows a gap. **Valve:** each point.
10. **Osnova (15).** A ranked table, the map, a profile per chain, a SWOT. **Valve:** each stop.
11. **Report (16).** Written around the closed points; *předběžná* until the financial-profile
    configuration is registered. **Valve:** the approval.

---

## 6. What is new against MVP-SCOPE.md v3

MVP-SCOPE.md version 3 plans the cost decision. These chunks are what the module breakdown and the
competitor analysis add. None changes the scope's numbers; their effort is stated only where a comparable
chunk of the scope exists.

| Chunk | What | Effort basis |
|---|---|---|
| MOD-1.1 | the study plan for a business study | comparable to `lead-orchestration#LO3`+`#LO4`; unestimated there |
| MOD-1.2 | the Lead's context layers for business stages | unestimated |
| MOD-1.3 | the Lead's targets for business stages | unestimated |
| MOD-2.1 | the business stages' impact rule | unestimated |
| MOD-2.2 | the stage track composed from the study type | unestimated |
| MOD-3.1 | propose_factors | one worker row with its contract; comparable to a design worker; unestimated |
| MOD-3.2 | plan_sources | as MOD-3.1 |
| MOD-3.3 | propose_configuration | as MOD-3.1 |
| MOD-3.4 | propose_stage_spec | as MOD-3.1 |
| MOD-3.5 | propose_points | with `lead-orchestration#LO9b` |
| MOD-4.1 | the stage specification as a type and its checks | unestimated |
| MOD-4.2 | the renderer | unestimated |
| MOD-4.3 | storage and invalidation of specifications | unestimated |
| MOD-4.4 | the user side: note, undo, standard form, two preferences | unestimated |
| MOD-4.5 | default specifications per study type, as data | unestimated |
| MOD-5.1 | the study-type catalogue as data | unestimated |
| MOD-5.2 | the level choice for comparative studies | unestimated |
| MOD-7.1 | the SÚKL pharmacy register route | comparable to `public-data-routes#PDR6`; unestimated there |
| MOD-7.2 | ČSÚ population per municipality | as MOD-7.1 |
| MOD-9.1 | the collection protocol and its sample | unestimated |
| MOD-9.2 | the entry form | unestimated |
| MOD-9.3 | the price basket protocol | unestimated |
| MOD-10.1 | comparability rules for entities across firms | comparable to `cost-model-study#CR1b`; unestimated there |
| MOD-11.1 | direction alignment | unestimated |
| MOD-13.1 | configurations as data | comparable to the scope's SYS13 + CS1 (4–6 session-days, MVP-SCOPE.md § 7, W4) for one configuration's plumbing |
| MOD-13.2 | the financial-profile configuration | comparable to the scope's SYS10 (experts, 2–3 session-days, § 7, W4) |
| MOD-17.1 | grades for samples and public records | unestimated |
| MOD-18.1 | register entries for the business configurations | comparable to SYS12's entries (1–2 session-days, § 7, W5) |
| MOD-19.1 | ceilings for priced routes and collection | unestimated |
| MOD-20.1 | the competitor-analysis case pack | comparable to a case pack's authoring; unestimated |

"Unestimated" means no chunk of the scope is close enough to set it against. The estimates are the next
step, chunk by chunk, as for the maps (MVP-SCOPE.md § 7).

---

## 7. Open decisions

1. **How far tailoring goes in the MVP.**
   (a) Tailoring of content only: fields, factor lists, defaults, examples, explanation depth, the proposed
   configuration, rendered from specifications for the business stages (MOD-4.1–4.5); the layout of each
   stage stays fixed.
   (b) Also the order and grouping within a stage and the choice of visual.
   (c) Tailoring deferred; the stages are hand-built per study type for the MVP.
   **Recommendation: (a)** for the MVP. It delivers the owner's principle where it matters most (each
   stage asks for what this study needs, at this user's level), and it is the part that can be checked by
   code against § 2.3. (b) follows once the specification and its renderer are proven.
2. **The competitor analysis as the second acceptance case.**
   (a) In the MVP: it proves the modules are reusable, and it adds the MOD- chunks above.
   (b) The first study type after the MVP.
   **Recommendation: (a), once the MOD- chunks are estimated.** Without a second study type the module
   boundaries are untested, and the first new type after the MVP would find them wrong.
3. **The financial-profile configuration.** Adopted as a sixth configuration of the observed-data map
   (MOD-13.2), subject to its fixture and the methodology owner's register entry; or not, in which case the
   competitor analysis uses the expert map alone. **Recommendation: adopt**, because ratios are the
   competitor analysis's main evidence and the type's declarations already cover it.
4. **The SÚKL register's licence and access** (MOD-7.1). To be confirmed before the route is built;
   **recommendation:** check it first, in the source register (`public-data-routes#PDR0`).
