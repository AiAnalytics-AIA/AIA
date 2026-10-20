---
status: in-progress
chunks:
  - "[x] MP0. This plan, first draft: the goal, the document map, the plan register, the activation matrix, the execution protocol"
  - "[x] MP1. The five cohesion traces folded in: the gap register (§6) and the interface register (§5), anchors spot-checked"
  - "[x] MP2. Each gap's chunk added to its plan, with a named ID (§6.1, §5); each plan's owner reviews before its wave"
  - "[ ] MP3. Disposition edits: close or re-scope the plans §3.2 marks CLOSE or FOLD (each plan's owner confirms)"
  - "[ ] MP4. Contracts written before the work that needs them (mvp-development-plan.md §5), and the shared-surface owners of §2 of that plan"
  - "[ ] MP5. The ADRs (mvp-development-plan.md §6), the ADR 0008 amendment for the open posture, and the ADRs ADR 0026 decision 4 requires before semantic report edits, respondent replacement, assumption evidence and open-answer coding; ADRs awaiting an owner decision stay Proposed"
  - "[ ] MP6. The activation profile: deploy/develop declares the MVP switches and the smoke reports each READY or NOT_READY without a paid call"
  - "[ ] MP7. The operator runbook run once on develop: AI route classes, Brave sign-off, secrets, the reach switches, with the evidence recorded"
  - "[x] MP8. A register check: tools/master_check.py fails on a dangling plan#ID reference, a plan missing from §3, an AC or G or I row with no resolvable chunk, or a count that does not match the tables"
  - "[ ] MP9. The production release checklist exercised once on develop: delete path, backups and restore, alarms, rollback"
  - "[ ] MP10. This plan re-verified at each gate (I-0 to I-5), its register and gap list brought up to date"
  - "[ ] MP11. The owner answers §11.4's questions; each answer is recorded in mvp-cohesion.md's register and the plans it moves are edited"
  - "[x] MP12. Canonical V2 precedence and eleven-artifact / 34-row planning conformance inventory recorded; implementation and owner/methodology questions remain open"
  - "[x] MP13. The six child plans written and registered (each session reviews its plan before its wave)"
  - "[ ] MP14. tools/master_check.py wired into the Documentation checks job (a ci.yml change, in its own pull request)"
  - "[x] MP15. Execution dependencies, partial wave checks and the owner decision packet reconciled; implementation remains open"
---
# The MVP master plan

Written 2026-10-19 on the owner's request: "ensure all the plans work together towards the same goal,
write the master plan". Written against `develop` @ `769917f` plus #500 (the reach plan, not yet merged).
**Owner: the owner of the lane, S3 (`mvp-development-plan.md` §2), who keeps §3, §5 and §6 true.**
Every claim about code carries `file:line @ SHA`; one without is a hypothesis, marked ◇.

## 1. What this plan is

AIA has many plan files (`python tools/progress.py` counts them; no number is typed here, because it would rot). Each is a good plan for its own
feature. What did not exist is one place that says which of them are the MVP, in what order, who owns
what, what each hands to the next, and what has to be switched on for any of it to work. This is
that place. It does **not** copy any plan's chunks: a chunk is built from its own plan. It owns four
things: the **register** (§3), the **activation matrix** (§4), the **interfaces between plans** (§5)
and the **gaps** (§6), plus the **protocol** the sessions work by (§8).

**The goal, in one sentence.** A researcher, with their own Lead, takes a study from brief to an
approved client deliverable: respondents built from the population, Deep Research reaching the open
web, the client's own data in the analysis, every number and quote traceable to its origin, inside a
spend limit the researcher set. It is done when `MVP-ACCEPT-2`'s fifteen criteria pass in CI (tier A),
once live on develop within USD 25 (tier B), and the system is released to production.

**The document map.** One document owns each kind of question; on a disagreement the owner of that
kind wins, and the others are stale until fixed.

| Question | Owner | Document |
|---|---|---|
| What is the MVP, and what is out | the product owner's decisions MVP-1 to 33 | `overview.md` § MVP roadmap, `mvp-consolidation.md` |
| How is it accepted | the fifteen criteria and two tiers | `docs/migration/mvp-acceptance.md`, `parity-matrix.json` |
| What was decided, and what was found inconsistent | the decision register F1 to F19, Q1 to Q29 | `mvp-cohesion.md` |
| What is the shape: tables, workers, routes, AWS | the target architecture | `mvp-target-architecture.md` |
| In what order, by whom, behind which gate | gates, sessions, waves, the migration lane | `mvp-development-plan.md` |
| Which plan is in play, what links to what, what is missing, how sessions work | **this plan** | `mvp-master-plan.md` |
| How a chunk is built | each feature plan | `.planning/plans/<feature>.md` |
| Why a rule is what it is | ADRs | `docs/architecture/adr/` |

## 2. The three failures this plan exists to prevent

1. **A plan that is right and not connected.** `deep-research.md`'s status table said Wikipedia was the
   only live search route while Brave, public fetch and most connectors were built; the owner was
   told "only Wikipedia". (The first version of the reach plan swung the other way and said every route
   family was built; tracing showed procurement has no live source, the crawler and the triage readers no
   caller, and the connectors run only under `AIA_DEEP_RESEARCH_AGENT_DIRECTED`.) Rule: a status that a machine can read is read by a machine (`deep-research-web-search#52`), and a status a person writes names its SHA.
2. **A switch nobody threw.** Every AI button in every stage fails on develop with `route
   bedrock-eu-primary is not approved for CLASS_A_CLIENT_CONFIDENTIAL`, because the route is approved
   for Class C only until an operator records the Bedrock retention and sets four parameters
   (`deploy/develop/README.md` § AI route classes), and the deploy's smoke never looks:
   `smoke.py:207-214 @ 769917f` reports the AI check "not runnable ... never a pass". A green deploy
   hid a product that could not run. Rule: §4's activation matrix is declared in the repository and
   checked on every deploy (`mvp-master-plan#MP6`).
3. **Two plans owning one surface.** `client-workspace` C8 says a dataset's use in a study is "V AIA
   zatím není"; `client-data-in-analysis` builds exactly that. Rule: §3 names one owner per surface
   and one disposition per plan; a plan that disagrees is re-scoped, not left to win by being later.

## 3. The plan register

**Role.** `CORE`: carries an MVP gate. `SUPPORT`: needed, gates nothing alone. `CLOSE`: finished or
superseded, to be verified and closed by its owner. `FOLD`: its remaining work belongs inside another
plan. `POST`: after the MVP, by decision. The dispositions of plans outside the development plan are
**proposed** (◇): each plan's owner confirms in `MP3`.

### 3.1 Core: carry an MVP gate

| Plan | Session | Gate | Needs first |
|---|---|---|---|
| `research-lead-workbench` | S1 | I-1 to I-4 | edit vocabulary, `LeadWorkerSpec` |
| `evidence-integrity` | S2 | I-1, I-3 | D04 before final empty-module policy; external-context producer/consumer contract |
| `sociomap-formula-corrections` | S2 | I-2 | method owner (0b is open; 0a is done) |
| `segment-maps-and-drilldown` | S2 | I-2 | method owner, register entries |
| `audience-catalogue-cpu` | S2 | I-0 | none |
| `complete-study-report` | S2 | I-0 | the AI route widened for Class A and B (§4), audience 4 |
| `deep-research-web-search` | S2 | I-R, I-4 | Brave sign-off (owner) |
| `deep-research` | S2; migration reviewed by S3 | I-4, I-5 | tool-spend contract and serial migration lane; before AC-15 reconciliation |
| `client-budget` | S3 | I-1 | none |
| `client-knowledge-lifecycle` | S3 | I-1, I-3, I-5 | reviewed-source contract; K7 Simulation coverage remains post-MVP |
| `client-data-in-analysis` | S3 (4-5 S2) | I-3 | accepted ADR 0027 before runtime; the early interface proposal does not admit data |
| `research-integrity-report` | S3 | I-3 | none |
| `two-roles-human-ai-gates` | S3 | I-2, I-3 | a client-report contract |
| `develop-spend-attribution` | S3 | I-0, I-5 | semantic model identity versus invocation target resolved before profile configuration |
| `mvp-acceptance-harness` | S3 | I-0, I-5 | #503 acceptance reconciliation and one shared provider fixture |
| `system-prompts-settings` | S1 | I-3 | worker row |
| `working-copy-edit-ops` | S1 | I-1, I-2 | WCE0 covers structural operations and text-only default; S2 supplies lock fields before W1 writers |
| `assumptions-and-open-answer-coding` | S1 (assumption item), S2 (evidence, coding), S3 (report chapters) | I-1, I-3, I-5 | the methods `MVPQ-02a` and `MVPQ-02b` before any status or count is produced |
| `lead-orchestration` | S1 | I-1, I-3 | money/authority and early worker contracts; card revision binding before the first card |
| `run-qc-and-checkpoint` | S2 | I-1, I-2, I-3 | checkpoint before resumed fieldwork; event payload before Fieldwork UI; replacement method decision before RQC5 |
| `report-delivery` | S3 | I-2, I-3 | a client-report contract, the evidence gate definitions (§11.4) |
| `study-data-lifecycle` | S3 | I-5 | the deletion horizons (§11.4) |
| `production-environment` | S3 | I-5 | operator items (§11.5) |

The waves of every chunk are in `.planning/mvp-execution-contracts.md` (the predecessor graph and the table of every other open chunk); this table no longer repeats them, so there is one place to keep true. `tools/master_check.py` fails on an open chunk of these plans with no wave.

### 3.2 Outside the development plan: proposed disposition

| Plan | Proposed role | Why | Action |
|---|---|---|---|
| `productization-coherence` | SUPPORT (S1) | PC5 (stage track says the design changed after the run) and PC16 (rewording a question keeps its links) land inside artifacts 17-18 | add to workbench 17-18 as acceptance lines |
| `client-workspace` | FOLD into `client-knowledge-lifecycle` (S3) | C6-C9 overlap K3, K2, K6; C8 contradicts ADR 0027 and F19 | re-scope C8, point C6-C9 at the lifecycle chunks |
| `architecture-enforcement` | SUPPORT (S3) | the new tables must pass its contracts; chunk 9 (a digest on scope and claims) is security | schedule beside M1-M6; not gating |
| `ai-research-activation` | FOLD into §4 and `MP7` | its open chunk is the activation the AI route still lacks | close when `MP7` is done |
| `run-recovery-and-truth` | CLOSE | chunk 4 (search beyond Wikipedia) is `deep-research-web-search` 51-52 | owner closes with a pointer |
| `research-agent-workflows` | FOLD | 5-8 are covered by D17's workers, Interpretation Research (30) and `evidence-integrity`, **but its I4 (OI-64, a per-respondent checkpoint) is open and owned by nothing else** (§6, G27) | move I4 to a chunk of the new `run-qc-and-checkpoint` plan, then close with a pointer |
| `mvp-workflow-assurance` | CLOSE A4, A5; keep A3 optional | A4-A5 define an older four-area MVP including Simulation; `mvp-acceptance-harness` replaces them | owner re-scopes, A3 is measured simplification |
| `connected-research-assurance`, `contextual-research-settings-ux`, `desktop-ux-overhaul-handoff` | CLOSE (verify) | housekeeping chunks ("release checks, deploy, reconcile documentation") of finished work | owners verify against `develop`, close |
| `methodology-tab` | POST | S4d waits on the audit's author, W1c on panel source weighting, X1 is Simulation | none |
| `panel-grounded-respondents` | POST | 7f-7h are the holdout validation that lifts client-facing analysis prose; the MVP's client report carries none (AC-13) | none |
| `sociomapping-engine` | POST | the SOMECS engine depends on the method owner's exports and decisions; the MVP uses `aia-sociomap-3` | none |
| `simulation-studio` | POST | Simulation is out of the MVP (`mvp-acceptance.md`) | S0 recorded as deferred |

### 3.3 In the development plan and after the MVP, by decision

| Plan | Why |
|---|---|
| `class-b-search-route` | deferred whole on 2026-10-19: the open posture replaces classification for Deep Research in the MVP (`deep-research-web-search#53`); the content rule stays in it as the redesign's starting point. It is **not** core. |

Counts are derived, not typed: `python tools/master_check.py` prints how many plans each table holds and
checks them against the plan files' front matter.

A plan not in §3 is a defect of this plan: `tools/master_check.py` (`MP8`) fails on it.

### 3.4 Acceptance criteria and what builds them

Every criterion of `docs/migration/mvp-acceptance.md` (MVP-ACCEPT-2) maps to named chunks; the proof each
needs beyond a checked box is in `.planning/evidence/mvp-master-review/codex-coordination.md` §4. The
register check fails on a criterion with no resolvable chunk.

| AC | Built by |
|---|---|
| AC-01 | `mvp-acceptance-harness#5`, `lead-orchestration#LO11` |
| AC-02 | `research-lead-workbench#11`, `research-lead-workbench#14`, `research-lead-workbench#15`, `research-lead-workbench#16`, `working-copy-edit-ops#WCE2`, `working-copy-edit-ops#WCE6`, `lead-orchestration#LO3`, `lead-orchestration#LO4`, `lead-orchestration#LO5`, `lead-orchestration#LO13`, `mvp-acceptance-harness#10`, `lead-orchestration#LO15`, `research-lead-workbench#26`, `research-lead-workbench#27` |
| AC-03 | `research-lead-workbench#11`, `system-prompts-settings#7`, `system-prompts-settings#13`, `lead-orchestration#LO9a`, `lead-orchestration#LO9b`, `assumptions-and-open-answer-coding#AOC0`, `assumptions-and-open-answer-coding#AOC1`, `assumptions-and-open-answer-coding#AOC2`, `assumptions-and-open-answer-coding#AOC3`, `assumptions-and-open-answer-coding#AOC7` |
| AC-04 | `lead-orchestration#LO0`, `lead-orchestration#LO1`, `client-budget#CB5`, `lead-orchestration#LO15` |
| AC-05 | `audience-catalogue-cpu#4`, `complete-study-report#B6`, `run-qc-and-checkpoint#RQC6`, `run-qc-and-checkpoint#RQC8`, `run-qc-and-checkpoint#RQC10` |
| AC-06 | `run-qc-and-checkpoint#RQC0` |
| AC-07 | `working-copy-edit-ops#WCE7` |
| AC-08 | `evidence-integrity#1`, `evidence-integrity#2`, `evidence-integrity#3`, `evidence-integrity#6`, `run-qc-and-checkpoint#RQC2`, `evidence-integrity#9`, `assumptions-and-open-answer-coding#AOC4`, `assumptions-and-open-answer-coding#AOC5`, `assumptions-and-open-answer-coding#AOC6`, `assumptions-and-open-answer-coding#AOC8`, `assumptions-and-open-answer-coding#AOC9` |
| AC-09 | `sociomap-formula-corrections#I0`, `segment-maps-and-drilldown#0a`, `segment-maps-and-drilldown#5`, `segment-maps-and-drilldown#6`, `working-copy-edit-ops#WCE8`, `mvp-acceptance-harness#10` |
| AC-10 | `client-knowledge-lifecycle#K2`, `client-knowledge-lifecycle#K5`, `client-data-in-analysis#2`, `client-data-in-analysis#3`, `client-data-in-analysis#9` |
| AC-11 | `deep-research-web-search#51`, `deep-research-web-search#52`, `deep-research-web-search#53`, `deep-research-web-search#54`, `deep-research-web-search#27`, `mvp-acceptance-harness#11` |
| AC-12 | `mvp-acceptance-harness#5`, `client-knowledge-lifecycle#K7a` |
| AC-13 | `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD3`, `report-delivery#RD4`, `research-integrity-report#6`, `report-delivery#RD9`, `report-delivery#RD10` |
| AC-14 | `mvp-master-plan#MP6`, `mvp-acceptance-harness#5` |
| AC-15 | `develop-spend-attribution#1`, `develop-spend-attribution#3`, `develop-spend-attribution#5a`, `develop-spend-attribution#5b`, `deep-research#4`, `production-environment#PE7` |

## 4. The activation matrix: what must be switched on, and who throws it

A feature that is built and not switched on does not exist for the owner. **The route row reaches further than the first diagnosis said:** with the route at Class C only, every Lead turn, design job, panel fieldwork request and modelled-run analysis parks (a design is Class B by rule, approved knowledge and panel personas Class A: `material_rules.py:79-91`, `ai_fieldwork.py:418-432`, `harness.py:192-203`), and the planned results layer, report writer and map interpreter would too. Production needs the same approval and retention evidence, and `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` for panel lineage (`licence_determinations.py:44`). Each row is a switch, the
gate that needs it, who sets it, and the evidence that it is on. **`MP6` declares this profile in the repository and makes the smoke report each row `READY` or `NOT_READY` with the reason, never a paid call**, so a green deploy can no longer hide a dead product.

| Switch or parameter | Needed by | Set by | Evidence |
|---|---|---|---|
| `aia_ai_runtime_enabled`, route id, model and prices | every AI step (AC-03) | operator, SSM | Settings → AI |
| **`aia_ai_route_approved_for` = A, B, C** with `..._retention_days`, `..._eu_processing_approved`, `..._excluded_from_training` | **every design job** (the design is Class B by rule, approved knowledge Class A: `research_agents.py:675-686 @ 769917f`) | operator after the retention evidence | Settings → AI shows three classes; smoke `READY` |
| `aia_ai_research_agents_enabled` and its token and reservation limits | the workers (AC-03) | operator | Settings → AI |
| `aia_ai_research_lead_enabled` and the Lead's model keys | the Lead (AC-02) | operator | a Lead turn answers |
| `aia_ai_population_personas_enabled` | population-built respondents (AC-05); panel requests are Class A (`ai_respondent.py:322-325`), so the route row above must be widened first, or **every default run parks** and the API cannot see why (G4) | operator, after `audience-catalogue-cpu` 4 | the Run stage offers the panel **and** the smoke's route row is READY |
| `aia_ai_analysis_enabled` | the eight analysis modules (AC-08) | operator | a module is not `analysis_unconfigured` |
| `aia_ai_client_source_proposals_enabled` | AI proposals from a client document (AC-10) | operator | `client_source_proposals_unconfigured` gone |
| `aia_deep_research_enabled`, `..._web_search=brave`, key, price, `..._connectors`, Common Crawl keys | Deep Research reach (AC-11) | operator, owner signs the Brave plan | Settings → Deep Research lists each route active |
| **`aia_deep_research_agent_directed=true`** | the ladder, hence every connector, Wayback and Common Crawl (`agent_directed.py:466-528`); default false (`docker-compose.yml:102`) | operator | a run's record names a connector |
| ADR 0022 approvals on Nastavení → Deep Research | any priced route | an organization approver | `live_settings_unapproved` gone |
| `aia_web_research_workbench` | the workbench (AC-02) | operator | `/config` |
| `AIA_LEAD_PLANS_ENABLED` (new, off) | the plan card and envelope (AC-04) | S1 on develop when built | the I-1 exit passes |
| `aia_report_pdf_enabled` | the PDF beside the internal DOCX (AC-13); the client report is DOCX only today (`report_variants.py:78`, G35) | operator, on for develop | an internal report has a PDF artifact |
| `AIA_RUN_QC_ENABLED` (new, off) | the run QC node (AC-08) | S2 when built | a run's QC artifact exists |
| `clients.data_posture` per client | web search for a real client (AC-11) | an organization OWNER or ADMIN | the client's profile |
| Cognito, Google callbacks, population assets, the error tracker | sign-in, respondents, diagnostics | operator | `smoke.sh`, `/health` |

## 5. The interfaces between plans

An interface is something one plan produces and another consumes: a table, a route, an event, a file,
an enum value, a prompt. Each has one producer, one consumer, one owner, a test, and a wave. **The
contract is written before either side builds** (`mvp-development-plan.md` §5 lists six). The
traces (§7) add the twenty-six below.

Each row is one interface with no owner in the plans before the traces. **Owner** is the session that
writes the contract first; the other side reviews. Rows are grouped by what they carry. T1-T5 name the
trace that found each (`.planning/evidence/mvp-master-traces/`).

| # | Interface | Crosses | Owner | Needed by | Contract chunk |
|---|---|---|---|---|---|
| I1 | **`ResultsContext`**: type, classes, lineage, bound, an external-evidence slot (labelled L, never respondent evidence) | S1 type; S2 and S3 providers; Deep Research bundle (T3 C1, T5 C5) | S1, **in W1**, as an ADR addendum with a `MaterialRule` and a lineage test | before any results layer | `lead-orchestration#LO8` |
| I2 | **Stage and item vocabulary**: `pipeline.RESEARCH_STAGES`, `StepKey`, the workbench stages, the Lead's `Stage`, `IMPACT_ROOTS`, `design_items` kinds. No Sociomap stage in the pipeline | S1, S2, S3 (T1 C2, T3 C8) | S1, one table beside `domain/edit_ops.py` | W1 | `working-copy-edit-ops#WCE0` |
| I3 | **Three ways to start a run** (Run button, plan card, typed `start_run`) over one `ResearchRuns.start`: which pins and confirmations each passes. The confirmation is a function argument, so a plan authority without `APPROVE_GATE` does not protect it | S1, S2, S3 (T2 C2, T4 A4) | S1 in the orchestration ADR, with a typed start API that has no `confirm_cost_usd` and an import rule | W1 | `lead-orchestration#LO2` |
| I4 | **The money vocabulary**: envelope cap, `budget_usd`, `spend_confirm_usd`, client ceiling, `clients.budget_usd`, OI-64. The spend limit is a confirmation threshold and `None` means never; the cap is `budget_usd` | S1 envelope, S3 ledger (T2 B1, T4 B1 and B15) | S1 in the orchestration ADR, defined against `budget_usd` | W1 | `lead-orchestration#LO0`, `lead-orchestration#LO15` |
| I5 | **What a "dimension" is**: a persona topic, a materialized column, or a segment descriptor | S2 (segments, personas), S3 (K5 materialization) (T2 C1, T3 A2) | S2, in `sociomap-formula-corrections` I0 | W2 | `segment-maps-and-drilldown#0a` |
| I6 | **Straight-liner**: the engine's, the unit QC's and the worker's definition; one flag artifact; what "replace" means | S1 worker, S2 engine and QC (T2 C5, T3 C3) | S2, one definition in `domain/` | W1 | `run-qc-and-checkpoint#RQC1` |
| I7 | **Fieldwork events to the Fieldwork artifact**: heartbeat, quota-cell fill, respondent grid, park reason | S2 produces, S1 consumes (T2 C9) | S2 writes the payload first | W1 | `run-qc-and-checkpoint#RQC7` |
| I8 | **The working copy's writers**: `apply_edit_ops` against the PUT, import, reuse, migration, Design Research accept, the web's whole-content autosave. A lock held in one writer is bypassed by the others | S1, S3 (T1 C7, T4 C9) | S1, with a test that no writer changes a locked item | W1 | `working-copy-edit-ops#WCE2` |
| I9 | **Per-change identity** across three accept routes (agent job, Design Research `item_ids`, Lead `indices`) | S1, S2 (T1 C1) | S1 | W1 | `working-copy-edit-ops#WCE6` |
| I10 | **Brief materials, client sources and the data contract**: `briefing.attachments`, `brief_signature` in Python and TypeScript, `design_material` | S1, S3 (T1 C3) | S3 writes the contract, S1 adopts it | W1 | `client-data-in-analysis#8a` |
| I11 | **Sociomap declarations, lock and unlock**: the editor, the lock rule and the ledger row | S1, S2, S3 (T1 C5, T3 C9) | S1 builds the editor against S2's fields | W0 lock contract; W2 editor | `working-copy-edit-ops#WCE0`, `working-copy-edit-ops#WCE8` |
| I12 | **Approve and Export panel** inside the Report artifact | S3 panel, S1 slot (T3 C2) | S1 hosts a slot, same wave | W2 | `report-delivery#RD3` |
| I13 | **Map snapshot**: the renderer, the approvable object, the ledger shape | S2 figure, S3 approval (T3 C5) | S3 owns the object, S2 the deterministic function with camera parameters | W2 | `report-delivery#RD4` |
| I14 | **Accepted report wording, map readings, flags**: an artifact type and the composer input that carries them into a report's fingerprint | S1 workers, S3 composer (T3 C7) | S3 defines the type, S1 writes the worker against it | W3 | `report-delivery#RD6` |
| I15 | **Settings**: the router (S1), the Reach panel (S2, which needs a worker-published composition record the API can read), posture and ceiling (S3) | S1, S2, S3 (T4 C3, T5 C2) | S1 owns the router; S2 writes the record | W1 | `lead-orchestration#LO12b`, `deep-research-web-search#52` |
| I16 | **Class and residency rules**: `material_rules.py`, `residency.py`, and the classification code in `web_retrieval.py`, `application/deep_research.py`, `aia_executors/deep_research/*` | S1, S2, S3 (T4 C2, T5 C1) | S2 for Deep Research, S1 for `material_rules`; others open small PRs | W0 | `mvp-master-plan#MP4` |
| I17 | **Ledger writers and closed sets**: `workflow_repository.py`, `workflow_templates.py`, `executors/registry.py` | S1, S2, S3 (T4 C1, C4) | S3 (the lane owner) reviews; each session registers its own kind | W1 | `mvp-master-plan#MP4` |
| I18 | **Population in production**: provisioning, the licence route id, the tier A double for AC-05 | S2, S3 (T2 C10, T4 C7) | S3 | W1 (tier A double); W3 (production provisioning) | `production-environment#PE6`, `run-qc-and-checkpoint#RQC10` |
| I19 | **Evidence into Client Knowledge**: three plans (`verified_sources`, K2e, deep-research chunk 37), three semantics (item or proposal) | S2, S3 (T5 C3, C6) | S3 decides once; S2 supplies the bundle reader | W2 | `client-knowledge-lifecycle#K8` |
| I20 | **Tool spend, the ledger and AC-15**: Brave and Athena spend is in `budget_reservations`, not the usage ledger | S2 ledger, S3 reconciliation (T5 C9) | S3 | W3 | `deep-research#4` |
| I21 | **A single-origin analysis input** against client-reported numbers | S2, S3 (T3 C4) | S2 designs a two-origin input and its fingerprint before S3's client-data chunk 5 | W3 | `evidence-integrity#8a`, `evidence-integrity#8b` |
| I22 | **The cost function for a Deep Research start** lives in `routers/deep_research.py:292-340` on the API's env copy; a plan step in the worker needs the same ceiling | S1, S2 (T5 C4) | S2 moves it to the application layer | W1 | `deep-research-web-search#55` |
| I23 | **Client-level paid AI** (source proposals, `clients.budget_usd`) against "every AI action goes through the Lead" | S3, S1 (T4 C10) | S3, with an explicit exception recorded in AC-02 | W1 | `lead-orchestration#LO13` |
| I24 | **`apps/web/src/lib/api.ts` and `i18n/cs.ts`**: one large file each, edited by every session, carrying every refusal message | S1, S2, S3 (T4 C8) | S1 for refusal wording; others by area | W0 | `lead-orchestration#LO12a` |
| I25 | **Prompt slots**: wiring the analysis and Deep Research prompts needs those executors to take a pin | S1 slots, S2 executors (T4 C5) | S2 for the executor half | W3 | `system-prompts-settings#7`, `system-prompts-settings#13` |
| I26 | **Delete path, ledger, audit and backups**: the ledger FK, audit rows and a restore after a deletion need one rule | all S3 (T5 C7) | S3 | before W5 | `study-data-lifecycle#SDL0`, `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL5` |


## 6. The gap register

### 6.1 Gaps and their implementation owners

These rows preserve the original findings; assigning chunks resolves planning ownership, not the implementation gap. Grouped by what they block. **Chunks** are the named chunks (written plan, then #, then the chunk ID) that close the row; a row is closed when they are built and tested, never because it has a destination plan.

**Activation and operations**

| # | Gap | Chunks |
|---|---|---|
| G1 | **No one can tell a user how to fix a route-class refusal.** Each surface says what is refused (the job error, the Lead pane, source proposals, Progress parks); none says who fixes it; the API cannot evaluate class; `/config` omits retention. The fix is an operator's (SSM), Settings is read-only (T4 A2, B9) | `lead-orchestration#LO12a`, `lead-orchestration#LO12b`, `research-lead-workbench#11`, `mvp-master-plan#MP6` |
| G2 | **Production route classes and retention evidence** are in no plan; ADR 0010's amendment is develop-only (T4 A3) | `production-environment#PE5` |
| G3 | **Readiness cannot see worker egress**: the panel default parks every run when the route lacks Class A, and the API reads no egress key (T2 A1) | `run-qc-and-checkpoint#RQC8`, `mvp-master-plan#MP6` |
| G4 | **The activation profile is not declared** (chunk 6 of this plan) | `mvp-master-plan#MP6` |
| G5 | **Each connector is UNVERIFIED**, none run live; Common Crawl's AWS side has no Terraform; the focused crawler, triage readers and procurement source are not usable though chunks 16 and 20 were ticked (T5 A5, A6, A16, B1, B15) | `deep-research-web-search#54`, `deep-research-web-search#16`, `deep-research-web-search#20`, `deep-research-web-search#36` |
| G6 | **No Terraform validation in CI**; two documents assume it; no freeze of auto-deploys during a tier B run; production needs its own ADR 0022 approvals (T5 A10, A11, A17, B9) | `production-environment#PE3`, `production-environment#PE5`, `production-environment#PE8` |
| G7 | **Production environment has no plan file**: `infra/production`, the workflow, RDS, Cognito, the egress proxy (which contradicts fetch from any public host), tag-conditioned IAM (T5 A8, A9, B14) | `production-environment#PE0`, `production-environment#PE1`, `production-environment#PE2`, `production-environment#PE4` |
| G8 | **The delete path is blocked four ways**: `ai_usage_events.study_id` and `population_dataset_versions.owner_client_id` have no `ondelete` (`tables.py:1833, 1938-1939`); IAM grants no delete on population children (`main.tf:364-368`); `delete_prefix` exists only on the filesystem store (`storage.py:366`); versioned buckets keep deleted objects 30 days with no `DeleteObjectVersion` grant (T5 A7, B12) | `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL2`, `study-data-lifecycle#SDL3`, `study-data-lifecycle#SDL5` |
| G9 | **The tagged-profile plan conflicts with the code**: its ARNs would be refused at worker start (`ai_runtime.py:254, 516` need an `eu.` id), "no Environment tag" is wrong (`versions.tf:34-40`), tool spend is not in the usage ledger so AC-15 reconciles model spend only (T5 A12, B8) | `develop-spend-attribution#5a`, `develop-spend-attribution#5b`, `deep-research#4`, `production-environment#PE7` |
| G10 | **The harness is not scheduled**: chunks 4 (doubles for the Lead and workers) and 8 (parity never blocks) are in no wave, the `acceptance` marker is unregistered under `--strict-markers` (`pyproject.toml:276-282`), tier B depends on the deferred `class-b-search-route`; tier A has no population double so cannot prove AC-05 (T5 A13, B6; T2 A11) | `mvp-acceptance-harness#4`, `mvp-acceptance-harness#8`, `mvp-acceptance-harness#9`, `run-qc-and-checkpoint#RQC10` |

**Money and orchestration**

| # | Gap | Chunks |
|---|---|---|
| G11 | **The envelope is defined against the wrong quantity.** The architecture and F13/F16 call the spend limit "the hard stop"; in code it is a confirmation threshold (null means never ask) and the cap is `budget_usd`, defaulting to 0 for a new study (T2 B1, T4 B1; `routers/scope.py:95`) | `lead-orchestration#LO0`, `lead-orchestration#LO1` |
| G12 | **The envelope, plan card and typed `start_run` are in no plan file.** The workbench plan puts "continue until you need me" after the MVP (D16, chunk 24) and MVP-13 says "one card at a time" (T2 B3, T4 B3) | `lead-orchestration#LO2`, `lead-orchestration#LO3`, `lead-orchestration#LO4`, `lead-orchestration#LO5` |
| G13 | **There is no continuation turn**: turns are person-started only; the Lead sees run id and status, not park reasons or spend (T4 A1, T2 C3) | `lead-orchestration#LO6` |
| G14 | **A plan's own steps defeat its stale rule**: `proposal_accept.py:117-118` refuses on "head moved" before comparing items, and any job start, rebuild, Lead approval or a visit to the Run stage submits a Design Revision, killing every other pending proposal; a second researcher's action kills the first's (T1 #2, T4 B7) | `working-copy-edit-ops#WCE5` |
| G15 | **`approve_request` is not bound to the card's revision**; the Lead's 96 KB context against the agents' 64 KB likely returns a 500 on approval ◇ (T4 A10) | `lead-orchestration#LO10` |
| G39 | **No chunk enforces the spend limit on the server.** `ResearchAgentJobs.start` reads no `spend_confirm_usd` (`application/research.py:1311-1407`, against `ResearchRuns.start` at `:739`); cohesion F5 adopts the check as the first code change, the development plan's W0 names it, but no child chunk did, and workbench D15 said removing the buttons closed F1. `budget_usd` is the cap; the envelope and the confirmation are distinct (review of 2026-10-20, item 1) | `lead-orchestration#LO15` |
| G40 | **D12 and D15 disagreed below 1100 px or with the switch off**; settled by MVPQ-11 (2026-10-20): the Lead stays accessible at every width (a compact drawer or stacked layout), no manual AI start in any layout, and an honest fallback with the workbench or the Lead's kill switch off | `research-lead-workbench#26`, `research-lead-workbench#27`, `lead-orchestration#LO15` |
| G16 | **The three new workers have no binding, accept path, price or `MaterialRule`**: no `REPORT_WRITING` binding, no result kind for interpretation, wording or flags, no rule for results, module text, maps or report text (T4 A5, T3 A9, A10, T2 A5) | `lead-orchestration#LO9a`, `lead-orchestration#LO9b`, `report-delivery#RD6`, `run-qc-and-checkpoint#RQC3` |
| G17 | **Lead files cannot be rolled back** (`revisions()` has no caller); admin read and handover, the USER file's handover rule and a departure trigger are unplanned; (T4 A6, A7, A12); turns stay private (Q26), and shared proposals are G42, not this row | `lead-orchestration#LO11` |

**Working copy and design stages**

| # | Gap | Chunks |
|---|---|---|
| G18 | **Edit vocabulary, operations log, presence, change feed and per-change accept have no chunk**; `apply_edit_ops` as sole writer ignores six existing writers including the web's autosave; the person's editing is 33 `store.update` sites in 9 files and about 1,900 lines of TypeScript with 18.6.6 parity tests: moving it server-side is unsized (T1 A1, A8, T4 A9) | `working-copy-edit-ops#WCE2`, `working-copy-edit-ops#WCE3a`, `working-copy-edit-ops#WCE3b`, `working-copy-edit-ops#WCE3c` |
| G19 | **Stable identity for objectives, research questions, hypotheses and options**: keyed by normalised text (`design_items.py:120-172`), so a reword is remove plus add, `FOCUS_ID` cannot encode them, two people adding different questions both touch `content:section:s1`, section reorder is no item (T1 A3, #7) | `working-copy-edit-ops#WCE1` |
| G20 | **The Lead is never told what a person did with its edits, what others changed, or readiness and outlook**; ADR 0026 decision 2 (Accepted) lists them and `freeze_context` has none (T1 A2, B6) | `lead-orchestration#LO7` |
| G21 | **Nobody can set `sociomap_rating` or `context_objects`** (zero web hits), so the hard lock and `sociomap_unlock` have no subject and no chunk (T1 A4, T3 A3) | `working-copy-edit-ops#WCE8` |
| G22 | **No readiness on a working revision**, no impact or "stage current with revision" surface for a study, so AC-07 as worded cannot be tested; hand edits create no Design Revision (T1 A5, A6, B11, B12) | `working-copy-edit-ops#WCE7` |
| G23 | **The Lead cannot edit Audience, Dimensions or Sample** (its ops are `set_text`, `list_*`, `question_*`, `set_n`; `propose_audience` returns prose; `suggest_dimensions` returns an empty list); the valid n differs in four places (web 50-5000, Lead 30-40,000, readiness 20-10,000, sampler) (T2 A7, B5) | `working-copy-edit-ops#WCE10`, `run-qc-and-checkpoint#RQC9` |
| G24 | **`touched_items` never reaches the browser; no undo or old-revision route; no dependency rule between coupled change blocks; the Lead vocabulary extension needs a prompt version** (T1 A7, A10-A12) | `working-copy-edit-ops#WCE6`, `working-copy-edit-ops#WCE9` |
| G25 | **Brief to client-source contract**, the attachment-bytes lifecycle and the 64 KB design ceiling with uncapped attachments (T1 A9, C8, C9) | `client-data-in-analysis#8`, `study-data-lifecycle#SDL4` |

**Sample and execution**

| # | Gap | Chunks |
|---|---|---|
| G26 | **Fieldwork repays every respondent on every attempt (OI-64, open) and AC-06 is marked built.** Each attempt starts at the first respondent and stores the dataset at the end (`ai_fieldwork.py:283-326`), `max_attempts=3`, a clean shutdown is a RETRY, and the plain whole-run `retry` of a failed or cancelled run "spends again" (`research.py:835-862`). **An analysis-only retry does not: `retry_analysis` reuses the frozen dataset (`research.py:865-895`).** So the claim covers interrupted fieldwork and the plain retry, and each post-fieldwork step the MVP adds is another way to repay unless the checkpoint exists (T2 #1, A2, A3, B2; narrowed by the independent review, CR-11) | `run-qc-and-checkpoint#RQC0` |
| G27 | **QC is not wired**: no template node, step kind, `AIA_RUN_QC_ENABLED` switch or run-key identity; three definitions of straight-liner; no "replace" path from a completed run; no `MaterialRule` for run-derived data (T2 A4-A6, B7, T3 A15) | `run-qc-and-checkpoint#RQC1`, `run-qc-and-checkpoint#RQC2`, `run-qc-and-checkpoint#RQC3`, `run-qc-and-checkpoint#RQC4`, `run-qc-and-checkpoint#RQC5` |
| G28 | **An own dimension is built but read by nothing**: K5 (the definition step) is open, no web code calls the materialize route, personas read a fixed column list so a run over a child draws the same respondents; and building costs no money, so "refused when the envelope has no room" has nothing to refuse (T2 #3, A8, B4, B11) | `client-knowledge-lifecycle#K5`, `research-lead-workbench#22` |
| G29 | **Quotas and a panel support forecast before a run** do not exist; the Fieldwork artifact's feeds (heartbeat, quota fill, respondent grid, park reason) are unspecified (T2 A9, A10) | `run-qc-and-checkpoint#RQC6`, `run-qc-and-checkpoint#RQC7` |

**Evidence and delivery**

| # | Gap | Chunks |
|---|---|---|
| G30 | **No respondent attributes are stored** (`FieldworkRespondent` holds id, donor, weight, answers: `fieldwork.py:172-181`), so segment maps, filters and the drill-down have nothing to read; "segments by the study's dimensions" has no variable (a dimension is a persona-topic allowlist) (T3 A1, A2; T2 B6) | `segment-maps-and-drilldown#0a` |
| G31 | **Results shows raw aggregates, not admitted claims**, with suppression decided in the browser (`research-execution.ts:373`); no API serves the evidence table or `PrintGrade`; workbench chunk 20 lists "Missing: —" (T3 A4, B15) | `evidence-integrity#6` |
| G32 | **MVP-23 is a new rule, not a tightening.** AIA has no 95 % threshold (that is the unit's); it checks numbers in prose only, a finding with no claim ids passes, and the report needs all eight modules complete, so one uncitable module blocks the whole internal report; two parity cases flip (T3 #1) | `evidence-integrity#1` |
| G33 | **The live external-context producer is not wired**: `AnalysisInputs.external_context` already exists and participates in the prompt/fingerprint (`application/analysis.py:101,138,176`); `application/analysis_results.py:570-579 @ 0d525bc8` constructs it without external context. Trace the sealed-bundle provider into preparation and the Lead, preserving the existing context-not-evidence boundary (corrected T3 A5, T5 A15) | `evidence-integrity#7`, `lead-orchestration#LO8` |
| G34 | **AC-13 asks for what does not exist**: no client report PDF (`report_variants.py:78`); "evidence audit" and "legal source-use gate" are NOT_STARTED with no plan; "exports only after approval" contradicts the code (drafts download freely, approval follows: `research.py:2395-2449`); no map-snapshot object, route or renderer; two ledger shapes for it; no reader of the approval ledger for "approved by whom" (T3 A6-A8, A13, B3, B4, B9) | `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD2`, `report-delivery#RD3`, `report-delivery#RD4` |
| G35 | **Client-data steps are not placed in the run**: no graph node, no contract-version pin, no impact root; no class or lineage for client-reported numbers going to a model; no accept target for the three new workers (T3 A9, A11, A12) | `client-data-in-analysis#9`, `report-delivery#RD6` |
| G36 | **Evidence into knowledge has three semantics** and a document item holds only `source_id`, so Deep Research never sees the file text (`knowledge_access.py:75-90`); the data-contract permission differs between plans (`APPROVE_GATE` against `PROPOSE_CLIENT_KNOWLEDGE`); ADR 0027 decision 3 uses a blocklist, the plans an allowlist (T5 #8, B10; T3 B8) | `client-knowledge-lifecycle#K8`, `client-data-in-analysis#2` |
| G41 | **Two settled features have no ADR yet.** ADR 0026 decision 4 (Accepted) gives semantic report edits and respondent replacement no command until each has its own ADR and a deterministic admission rule; the report-wording worker and replacement chunks did not name that prerequisite (review item 4) | `report-delivery#RD6`, `run-qc-and-checkpoint#RQC5` |
| G42 | **A proposal one researcher's Lead prepared cannot be accepted by another member.** Q16 (decided 2026-10-19): any member with the accept permission may accept another's proposal; the chat stays private (Q26). Today `decide_edits` takes the caller's own completed turn (`application/research_lead.py:515-518`; `study_lead_repository.py:60-76` reads only the caller's turns), so an edit block is reachable only through its author's private turn. A proposal must be a shared artifact-level item identified by its change identity, with no chat text (review of 2026-10-20) | `working-copy-edit-ops#WCE6`, `working-copy-edit-ops#WCE4`, `working-copy-edit-ops#WCE12` |
| G43 | **Three lane migrations had no owning chunk.** M3 (the ledger's subject types, W0, first) was in a development-plan row only; M8 (`client_data_contracts`, `client_dataset_copies`) and M9 (`inference_profile_arn`) named no chunk that creates them, while consumers write those subjects and tables (review of 2026-10-20) | `lead-orchestration#LO16`, `client-data-in-analysis#2`, `client-data-in-analysis#3`, `develop-spend-attribution#5a` |
| G44 | **Tracked assumptions have no producer, store or consumer.** MVPQ-02 (2026-10-20) requires them at first release; an item kind with a stable id and a status, evidence from Deep Research as cited context, human-approved status changes, and the Design artifact, Lead context, analysis payload and report as consumers, all behind a method not yet approved (`MVPQ-02a`) | `assumptions-and-open-answer-coding#AOC0`, `assumptions-and-open-answer-coding#AOC1`, `assumptions-and-open-answer-coding#AOC2`, `assumptions-and-open-answer-coding#AOC3`, `report-delivery#RD9` |
| G45 | **Open-answer coding has a raw-answer producer and nothing after it.** MVPQ-02 requires it; per-answer codes under a versioned method, a coding node with its impact root, deterministic counts as admitted claims, a model coder only if the method permits one, and Results, Analysis and report consumers, behind a method not yet approved (`MVPQ-02b`) | `assumptions-and-open-answer-coding#AOC4`, `assumptions-and-open-answer-coding#AOC5`, `assumptions-and-open-answer-coding#AOC6`, `assumptions-and-open-answer-coding#AOC7`, `assumptions-and-open-answer-coding#AOC8`, `report-delivery#RD10` |
| G46 | **A module with no supported finding had no stored form and no refusal.** MVPQ-04 (2026-10-20): the report is blocked until it is resolved; a structured diagnostic, not a finding, and a composer and exports that refuse while any module is blocked or empty | `evidence-integrity#9` |

**Deep Research and the open posture**

| # | Gap | Chunks |
|---|---|---|
| G37 | **The open posture needs a setter route, permission test, audit row, profile UI and `api-contract` entry** (specified in `deep-research-web-search` 53 after this review) (T5 A2, T4 A8) | `deep-research-web-search#53` |
| G38 | **A second live Deep Research run (Interpretation) is needed for "cited context in the report"** (`contextual_report.py:985`) and is absent from AC-11's wording, gate I-4 and the USD 25 budget table (T5 A14) | `mvp-acceptance-harness#1`, `mvp-acceptance-harness#11` |

### 6.2 Statements that are wrong or stale: fix the document, not the code

| Statement | Where | What is true | Fix |
|---|---|---|---|
| "The spend limit is the hard stop for everything" | `mvp-target-architecture.md:134`, F13, F16 | a confirmation threshold; the cap is `budget_usd` | `lead-orchestration`, the architecture's docs PR |
| "Every route family is built" | the first reach plan | procurement, crawler, triage not usable | fixed in #500 |
| "An administrator widens the route on Nastavení → AI" | the first W0 note | Settings is read-only; an operator does it | fixed in #500 |
| "Czech Wikipedia is the only live route" | `deep-research.md:519` (contradicts its own `:3-9`) | not true; see the Reach section | chunk 52, then replace with a pointer |
| "Three maps are approved only after D6" | `ARCHITECTURE.md:395-398`, `native.py:20-34` | the register approves `aia-sociomap-3` since 2026-10-13 | docs PR |
| AIA "passes when 95 % of findings cite" | `evidence-integrity.md` | the unit's rule; AIA has none | `evidence-integrity` 1 |
| Analysis modules receive the Deep Research bundle | `deep-research.md:260`, `research-journey.md:265` | `analysis_results.py:570-578` passes none | G33 |
| AC-06 "loses no work" is built | `mvp-acceptance.md:81`, `mvp-cohesion.md:558` | OI-64 is open | G26 |
| AC-07 "reuses every other stage's artifacts" | `mvp-acceptance.md:82` | AI fieldwork is never reused; `impact_preview` is unused for studies | `working-copy-edit-ops` |
| AC-13 "DOCX and PDF", "exports after approval", "evidence audit and legal gate" | `mvp-acceptance.md:88`, `overview.md:332` | G34 | `report-delivery`, then the criterion |
| "A second person for the client report" | `mvp-acceptance.md:40, 88`, target-architecture §7 | withdrawn by the owner; follows self-approval | docs PR |
| "The working copy is written only by `apply_edit_ops`" | target-architecture §8 against §3.1 | the whole-copy route stays | I8 |
| "After any accept the head equals the working copy" | target-architecture `:179-183` | the Lead's accept saves only and submits no revision (`research_lead.py:592-601`) | G14 |
| "A plan stops at the next step if the design moved" | target-architecture `:144-146` | an accepted `agent_job` moves the head | G14 |
| Structural edits may auto-apply per stage (D18, MVP-14) | `research-lead-workbench.md:141-144` | cohesion and architecture say text only | owner decision (§11 Q9) |
| MVP-13 "one card at a time" | `overview.md:584`, AC-02 | superseded by the envelope (F13) | docs PR |
| "A client report is produced by whoever first downloads it" | `research.py:2478-2485` | with self-approval off, the reviewer who opens it first cannot approve it ◇ | `report-delivery` |
| Settings "FAST_EXTRACTION unused", analysis and Deep Research prompt slots "not run" | `settings.py:529`, `prompt_slots.py:121-140` | both are registered and run | `system-prompts-settings` |
| "No Environment tag" | `develop-spend-attribution.md:28` | `versions.tf:34-40`, `main.tf:597-607` | G9 |
| "Segments by the study's dimensions" | `segment-maps-and-drilldown` 1 | a dimension does not partition respondents | G30 |
| Chunks 16, 20, 23 ticked | `deep-research-web-search.md` | procurement, triage, the light-model key not built | 16 and 20 reopened in #500 |
| `class-b-search-route.md:61` "mandatory" | the plan | deferred | fixed in #500 |

### 6.3 New plan files these gaps need

The traces found work no plan owns. Each is now one plan file with open, named chunks (`MP13`),
written by the session named, before its wave starts. A plan is not new work: its first line says which
gap rows it takes.

| New plan | Takes | Session | Before |
|---|---|---|---|
| `working-copy-edit-ops` | G14, G18, G19, G21, G22, G24 and I2, I8, I9, I11 | S1 | W1 |
| `lead-orchestration` | G11, G12, G13, G16, G17, G20 and I1, I3, I4, I22 | S1 | W1 plan code |
| `run-qc-and-checkpoint` | G26, G27, G29 and I6, I7 | S2 | W1 |
| `report-delivery` | G34, G35 (the accept paths), I12, I13, I14 | S3 | W2 |
| `study-data-lifecycle` | G8, G25 (bytes), I26 | S3 | before W5 |
| `production-environment` | G2, G6, G7, I18 | S3 | W1 infra apply |

Segment attributes (G30) are `segment-maps-and-drilldown#0a`, not a plan, because the method owner
decides what a segment is.


## 7. How this was checked

**Five read-only traces** followed each stage and each cross-cutting capability down and back up the stack
(screen, route, service, rule, table, worker, external call, artifact, back to the screen and the Lead),
one line per link: EXISTS with an anchor, PARTIAL, MISSING with the plan chunk that builds it or NONE,
CONTRADICTION. About 530 links were traced: 200 EXISTS, 92 PARTIAL, 166 MISSING, 70 CONTRADICTION. They
are kept as evidence under `.planning/evidence/mvp-master-traces/`, with their method and limits in its
README. They are an audit, not a proof: nothing was run, and what the live develop host holds in SSM is
unknown. Eight findings that contradicted earlier statements were opened against the code before they
were written down here, and all eight held. The first version of this plan and of the reach plan
contained claims the traces disproved; §6.2 lists them and the corrections are in #500.

**The V2 prototype** (`prototypes/research-lead-v2`, the owner's "desired state") was walked in a real
browser, all twenty scenarios and the panels, and compared row by row with AIA in
`.planning/evidence/mvp-prototype-v2/conformance.md`.

## 8. The execution protocol

The cross-plan predecessor table and gate evidence rules are in
[execution contracts](../mvp-execution-contracts.md). This is a schedule/contract view, not another progress store.

**Environments.** `local` (the UI workbench, SQLite, fictional respondents, USD 0) → **CI tier A** (every
PR; `ci.yml` jobs: What changed, Backend, Frontend, API contract, Application starts, Security and
dependency scan, Documentation checks on a docs-only PR, and the parity jobs, informational by the
owner's decision of 2026-10-19) → **develop** (deployed when CI is green on a push to `develop`:
the `Dispatch verified develop deployment` job; `deploy-develop.yml` serialises deploys with
`concurrency: deploy-develop, cancel-in-progress: false`, `:30-32 @ 769917f`) → **tier B** (the live
acceptance on develop, within USD 25, run by a person) → **production** (a second Terraform root and
workflow in the same AWS account, with RDS; manual release).

**Branches and merges.** One prefixed branch per chunk group from a fresh `origin/develop`; a PR into
`develop`; never a direct commit to `develop` or `main`. A feature PR edits only its own plan file;
the shared files (CLAUDE.md, ARCHITECTURE.md, AGENTS.md, `overview.md`, `open-items.md`, the indexes)
change in a docs PR that applies the merged PRs' Doc follow-ups. **Merge order inside a wave:** the
contract, then its producer, then its consumer.

**The migration lane.** One Alembic head. S3 owns the lane. A migration PR names its `down_revision`,
is rebased on `develop` immediately before merge, and migration PRs merge one at a time (`§4` of the
development plan lists M1 to M10).

**Gates.** A wave ends when its gate passes in CI over HTTP, not when its chunks are ticked
(`mvp-development-plan.md` §1). A gate that needs a switch (§4) says so in its exit line.

**Definition of done for a chunk.** Its tests pass, including a test of the refusal path; `make
verify` is green; its anchors are in its plan; any shared-file change is written as Doc follow-up; its
switch, if any, is in §4 with its evidence; the plan's front matter is ticked.

**Status.** Progress lives only in plan front matter and the PR body (`python tools/progress.py`).
This plan's register is re-verified at every gate (`MP10`), and a session that finds a plan not in
§3, or a chunk a wave names that does not exist, fixes §3 in its PR, never in chat.

**Incidents and rollback.** A bad deploy is rolled back by the workflow's own input (an older
schema-compatible SHA with migrations unchecked, `deploy-develop.yml:24`); the runbook is
`deploy/develop/README.md`. Production adds the same with an RDS snapshot first.

**Who throws a switch.** An operator, from the runbook, with the evidence written down (`MP7`). A
session never asks for credentials in chat: a read-only credential goes in the environment's secrets,
and a write step is a person's.

## 9. Gates, and the release to production

**Three states, never one.** *Tier A passed*: every criterion green in CI over HTTP, with browser journeys
where the criterion is an interaction (hand edits, pointing, proposals, keyboard and focus, stale states,
the eleven stages, view-only map operations: `mvp-acceptance-harness#10`). *Tier B passed*: the live
acceptance on develop, run by a person, inside the USD 25 allocation. *Released*: production, after the
checklist below. Each is evidenced separately; an HTTP pass is not browser evidence, and tier B passing
does not release anything.

**Allocation.** The USD 25 of tier B is a table with a ceiling per category, summed before any recorded
run (`mvp-acceptance-harness#1`): fieldwork, analysis and its repairs, the Lead's turns and each worker,
Deep Research search and tool spend (priced search, the archive), the Interpretation run, a retry round.
The Deep Research evaluations (25, 26, 39) and the commercial comparison arm (50) have an allowance stated
apart. Model usage, tool and search spend, open reservations and uncertain calls are separate lines;
AC-15's tolerance (USD 0.01 against the usage ledger) applies to what the ledger holds, and tool spend
reconciles against `budget_reservations` until `deep-research#4` moves it (`develop-spend-attribution#5b`).
Cloud billing lag is recorded, never read as zero.

**Deep Research order.** Early activation (`deep-research-web-search#51`) on a fictional client or a public
topic proves reach, not quality, and gives no acceptance evidence. Evaluations 25, 26 and 39 come before
the final live run 27; their thresholds and owner are an open question (§11.4); waiving one is a labelled
scope override, never an omission. A W0 smoke may omit the archive; **I-R is then BLOCKED, not passed**,
unless the owner changes I-R.

### Before the first production release

Before the first release: the delete path and approved backup/object-version deletion horizons
(14/30 days remain infrastructure defaults until decided), an exercised restore, cost alarms and
tagged profiles. AC-15 reconciles model usage to the usage ledger within USD 0.01; tagged cloud billing
has its own stated window, lag and tolerance and must not be called that exact model-ledger check.
Also required are the cutover rollback
rehearsed on develop, the Cognito and Google callbacks for the production hostname, and the
activation profile of §4 `READY` on the production host. The hostname, RDS sizing and Bedrock quota are
still the owner's and an operator's (`mvp-target-architecture.md` §9).

## 10. Risks of the whole

| Risk | Consequence | What holds it |
|---|---|---|
| A built feature stays switched off | the owner sees a broken product (§2.2) | §4 and `MP6` |
| S1 is the critical path and carries the Lead, the artifacts and the plan card | the date slips | the fewest side tasks; S2 and S3 carry everything that can wait |
| The method owner has not answered | segment maps, clustering and register entries wait | decisions named in `mvp-cohesion.md`; no dates yet |
| Classification is deferred and a client is marked OPEN | an OPEN client's queries reach Brave unchecked | the audited flag is the only guard, stated |
| Plans drift again | this plan goes stale | the register check (`MP8`), and the rule in §8 |

## 11. Questions for the owner

Only choices that are genuinely open are asked. Decisions already made are listed in 11.1 and are not
re-asked; a different answer to one of them is a **scope override** and is said to be one (11.3), with the
work it moves. Each answer is recorded in `mvp-cohesion.md`'s register (`MP11`). "Row" means a row of
`.planning/evidence/mvp-prototype-v2/conformance.md`.

### 11.1 Settled, not asked again

MVPQ-01 was answered on 2026-10-20: the browser's Czech Research Lead V2 build is the canonical reference for both the workspace and all eleven artifact bodies; V3 is supporting reference only. Preserve newer recorded domain/methodology decisions; verify deltas in MP12.

| Decision | Settled by | Where it is built |
|---|---|---|
| Canonical design is the browser's Czech V2 build, including its artifact bodies; the earlier V2/V3 blend recommendation is superseded | MVPQ-01, owner 2026-10-20 | `research-lead-workbench#15`, `research-lead-workbench#17`, `research-lead-workbench#22`, `mvp-master-plan#MP12` |
| Tracked assumptions and open-answer coding are both required at first release (scope only; the methods stay open, `MVPQ-02a`, `MVPQ-02b`) | MVPQ-02, owner 2026-10-20 | `assumptions-and-open-answer-coding#AOC1`, `assumptions-and-open-answer-coding#AOC5` |
| A module with no supported finding blocks the report until resolved; no invented finding | MVPQ-04, owner 2026-10-20 | `evidence-integrity#9`, `report-delivery#RD0` |
| The Lead stays accessible on narrow screens (a compact drawer or a stacked layout); no alternate AI start; availability stated honestly on switch-off and rollback, compact Lead access kept while its backend is enabled and a disabled backend kept disabled | MVPQ-11, owner 2026-10-20 | `research-lead-workbench#26`, `research-lead-workbench#27` |
| Each researcher has their own private Lead | F12, Q26 | `lead-orchestration#LO0`, `lead-orchestration#LO11` |
| The Deep Research open posture replaces classification for the MVP; the posture is pinned at enqueue and a retry copies it | #500, owner 2026-10-19 | `deep-research-web-search#53` |
| Respondent replacement is a new linked run, never an edit of a completed one | F18 | `run-qc-and-checkpoint#RQC5` |
| The report wording worker exists | MVP-12 | `report-delivery#RD6` |
| Structural edits may auto-accept per stage | MVP-14, D18 | `working-copy-edit-ops#WCE11`, `research-lead-workbench#11` |
| The report and the map snapshot are approved separately; the client report follows self-approval, no second person | F17 (withdrawn requirement) | `report-delivery#RD3`, `report-delivery#RD4` |
| A person may start a conversation with the Lead directly | Q25 | `lead-orchestration#LO5` |
| Client PDF, the evidence audit and the legal source-use gate stay in AC-13 | the acceptance document, until the owner overrides | `report-delivery#RD0`, `report-delivery#RD1` |
| The negative cases X2 (missing evidence) and X6 (methodology refusal) are release tests | prototype review | `mvp-acceptance-harness#13` |
| OI-64 (fieldwork repays every respondent) is an engineering prerequisite, not a product question | G26 | `run-qc-and-checkpoint#RQC0` |
| The delete path is required before release | MVP-30 | `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL3` |

### 11.2 Implementation fixes, no answer needed

The plans are corrected, with the owner told in the pull request:

- The spend limit is a **confirmation threshold** (`spend_confirm_usd`, null means never ask); the cap is
  `budget_usd`. The envelope is defined against `budget_usd` and never against the threshold
  (`lead-orchestration#LO1`; G11; `application/research.py:452-454`, `:724-742`).
- `retry_analysis` reuses the frozen dataset (`research.py:865-895`), so G26 covers interrupted fieldwork
  and the plain whole-run retry only (`run-qc-and-checkpoint#RQC0`).
- The evidence rule is a new rule that every finding cites admitted claims, not "a 95 % tightening"
  (`evidence-integrity#1`).
- "No Environment tag" is wrong (`versions.tf:34-40`); the tagged profile must account for the `eu.`
  identifier the worker validates (`develop-spend-attribution#5a`).
- `two-roles-human-ai-gates#5b.4` no longer says no client report exists.
- The Deep Research evaluations and the USD 25 allocation are in the harness and in §9.
- Production release is a blocker (§9, §10).
- **The server enforces the spend limit.** `ResearchAgentJobs.start` and `rebuild` get the check
  `ResearchRuns.start` has (`lead-orchestration#LO15`, W0); `research-lead-workbench` D15 no longer claims
  removing buttons closes F1, and F1 is no longer an owner decision.
- **The worker contract comes first.** `lead-orchestration#LO9a` (the `LeadWorkerSpec` row) is W0 and chunk
  11's first deliverable; `LO9b` (the three new workers' bindings) stays W3. W1 depends on `LO9a`.
- **The analysis prompt pin reaches every use.** The reuse identity and the system prompt in
  `application/analysis.py:125-139, :171` still read the code's template; `system-prompts-settings#7` and
  `#13` cover assembly, fingerprint, initial and repair calls, executor and usage provenance, with a test that
  queued work keeps its pin after an activation.
- **Semantic report edits and respondent replacement need their ADRs first** (ADR 0026 decision 4,
  Accepted): the features are settled and not re-asked; the ADR and a deterministic admission rule are the
  work (`report-delivery#RD6`, `run-qc-and-checkpoint#RQC5`).
- **Engineering invariants, not questions:** a report wording edit never reopens completed fieldwork
  (`report-delivery#RD5`); a coupled change is one group, accepted or refused together, and the server's
  validation refuses a split that leaves the copy invalid (`working-copy-edit-ops#WCE6`); an artifact's
  "content from revision n" is computed from where its items last changed, never a second store
  (`working-copy-edit-ops#WCE7`).

### 11.3 Proposed scope overrides: only if you want them

The earlier S1 (draw the V3 header strip) is closed by MVPQ-01: the canonical V2 build's compact header is the reference, which is what `research-lead-workbench#15` plans. S2 and S3 stay labelled overrides because the recorded budget and private-Lead decisions govern where the prototype shows otherwise.

| # | The plans say | The override | What it moves |
|---|---|---|---|
| S2 | Two meters (envelope and spend) | One meter, as the prototype shows | `lead-orchestration#LO1`, `research-lead-workbench#15` |
| S3 | One private Lead per researcher | One conversation per study, as the prototype has it | storage, retention, the return summary; reopens F12/Q26 |
| S4 | The permission panel shows the client's posture (OPEN or CLASSIFIED) and the strict class text applies to CLASSIFIED | Show the strict text for every client | `deep-research-web-search#54`; contradicts the open posture's intent |
| S5 | Client PDF in the MVP | Client report DOCX only; amend AC-13 | `report-delivery#RD1`, `docs/migration/mvp-acceptance.md` |

### 11.4 Open, with the chunks each blocks

Answer-ready wording, stable decision ids, decision owner and permitted independent work are in
[the owner decision packet](../mvp-owner-decisions.md). These are unanswered choices, not expired questions.

| # | Question | Blocks | Recommendation |
|---|---|---|---|
| 3 | **What is a segment?** Which stored descriptors, how do approved own dimensions take part, and may internal drill-down show generated profile prose? | `segment-maps-and-drilldown#0a`, `segment-maps-and-drilldown#1` | Start from the sampler's existing descriptors; the method owner defines support, clustering and register entries |
| 5 | **Client dataset policy.** Is the accepted data contract the evidence-policy source? ADR 0027's benchmark interval, grounding permission and label decisions | `client-data-in-analysis#2`, `client-data-in-analysis#9` | Owner and methodologist decide before the dependent code; the population field list is not a blanket fit |
| 6 | **Deep Research reach.** Is the archive (Common Crawl) required for I-R, or deferred with a revised exit? Which measured thresholds and owner for evaluations 25, 26, 39, and what allowance apart from the USD 25? | `deep-research-web-search#25`, `#26`, `#39`, `#27`, `mvp-acceptance-harness#11` | Keep I-R as it is until you change it; a W0 smoke without the archive reports I-R BLOCKED |
| 7 | **Deletion semantics.** The deletion horizon for backups and bucket versions, and how a deleted subject stays deleted after a restore | `study-data-lifecycle#SDL0`, `study-data-lifecycle#SDL5` | Document the horizons you approve and a deletion journal replayed after restore; 14 and 30 days are infrastructure defaults, not an approval |
| 8 | **Paid work outside a study.** Client-level source extraction stays in Client Knowledge under the client budget while every study-stage AI action goes through the Lead? | `client-knowledge-lifecycle#K8` | Yes, as a recorded exception to AC-02 with client isolation, approval and a budget |
| 9 | **The two AC-13 gates.** Which exact evidence and source-use checks must pass? Export after the exact version is approved is settled by F17 and is not asked again. | `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD3`, `report-delivery#RD7` | Evidence audit = the existing report validation plus the admitted-claim check; legal gate = the source-class check; preserve exact-version approval before all deliverable downloads; an unapproved-draft exception would need an explicit scope override |
| 10 | **Replacement weighting and support.** What a replaced respondent does to the weights, the effective n and the support rules (a methodology dependency; the feature itself is settled, F18) | `run-qc-and-checkpoint#RQC5` | The method owner defines it; until then the chunk builds the mechanism and labels the limit |

| 12 | **Canonical Sociomap decisions.** Confirm the still-open Q5/Q6/Q7 meaning and evidence policy, fixed-ruler kernel widths, F10 misfit threshold and F16 disposition with the methodology owner; use the existing decision sheets, not new invented defaults | `sociomap-formula-corrections#0b`, `sociomap-formula-corrections#I0`, `sociomap-formula-corrections#3`, `sociomap-formula-corrections#4c` | Canonical F1-F16 remain the baseline; checked implementation chunks do not approve the audit's provisional parameters |
| 02a | **The assumptions method (`MVPQ-02a`, a subpart of MVPQ-02).** What an assumption's status means, who sets it, and what counts as evidence for or against it. The feature is settled; the scientific rule is the methodology owner's | `assumptions-and-open-answer-coding#AOC0` | The methodology owner writes it; until then the contract and refusal tests proceed and no status is produced from prose |
| 02b | **The open-answer coding method (`MVPQ-02b`, a subpart of MVPQ-02).** The codebook and rules, permitted labels and multi-label semantics, denominator and missing-answer treatment, review and acceptance, support and suppression of small codes, what a model may do. The feature is settled; the method is the methodology owner's | `assumptions-and-open-answer-coding#AOC4` | The methodology owner writes it; until then the contract and refusal tests proceed and no count is produced from prose |

### 11.5 Operator and owner checklist (not methodology, not yet done)

The Brave plan and sign-off; the production hostname, Cognito and Google callbacks; RDS sizing; Bedrock
quota and the model per tier; the Bedrock retention evidence that lets the four route parameters be set
(`MP7`); the Lead's cost per turn, measured on develop; provider terms. None is portrayed as performed. The
activation profile (`MP6`) makes each READY or NOT_READY.

### 11.6 Recommendations withdrawn

Earlier drafts of this question list recommended things that reduced approved scope: a text-only edit
vocabulary (Q9), client DOCX only and amending AC-13 (Q7), skipping replacement and the return summary
(Q8), leaving out the archive "for good" (Q14), and releasing scenarios H to K, M, X2 and X6 only after the
first release (Q15). They are withdrawn; the first four now appear above as scope overrides or open
questions, and X2 and X6 stay release tests.

## 12. The independent review (2026-10-20): where each finding is closed

`.planning/evidence/mvp-master-review/codex-coordination.md` lists fifteen findings. The table names their implementation owners. They are planned, not closed: each remains open until its chunks are built and tested.

| Finding | Implementation owners |
|---|---|
| CR-01 executable chunks | the six child plans (`MP13`); §5 and §6.1 name a chunk per row |
| CR-02 threshold against budget | `lead-orchestration#LO1`, `develop-spend-attribution#5a`, §11.2 |
| CR-03 plan authority and AC-02 | `lead-orchestration#LO3`, `lead-orchestration#LO4`, `lead-orchestration#LO5`, `mvp-acceptance-harness#14` |
| CR-04 OPEN posture in the harness | `deep-research-web-search#53`, `mvp-acceptance-harness#11` |
| CR-05 reach is not a side chain | `mvp-development-plan.md` § Reach, `deep-research-web-search#54`, §9 |
| CR-06 stale 5b.4 | `two-roles-human-ai-gates#5b.4`, `report-delivery#RD3`, `report-delivery#RD4` |
| CR-07 client PDF | `report-delivery#RD1` |
| CR-08 evidence rule wording | `evidence-integrity#1` |
| CR-09 prompt scope | `system-prompts-settings#7`, `system-prompts-settings#13`, `lead-orchestration#LO9a`, `lead-orchestration#LO9b` |
| CR-10 segment descriptors | `segment-maps-and-drilldown#0a`, `client-knowledge-lifecycle#K5` |
| CR-11 checkpoint | `run-qc-and-checkpoint#RQC0` |
| CR-12 browser journeys | `mvp-acceptance-harness#10` |
| CR-13 tier A, tier B, release | §9, `production-environment#PE9a`, `production-environment#PE9b`, `mvp-acceptance-harness#12` |
| CR-14 evaluations 25, 26, 39 | `deep-research-web-search#27`, `mvp-acceptance-harness#11`, §9 |
| CR-15 spend reconciliation | `develop-spend-attribution#5b`, `deep-research#4`, §9 |

Readiness conditions 1 to 7 of that review: 1 and 2 are the tables of §3.4, §5 and §6.1; 3 is
`tools/master_check.py`; 4 is the settled list of §11.1 and the acceptance follow-up; 5 is §11.3 and §11.4;
6 is that ADRs awaiting owner decisions stay Proposed and every implementation chunk stays open; 7 is that
no calendar is promised: capacity and external decisions (§11.4 1, 3, 5, 6, 7) are the dependency risk.



## MP12 conformance inventory (2026-10-20)

[Canonical V2 disposition](../evidence/mvp-prototype-v2/current-disposition.md)
compares every artifact and all 34 historical walk rows with the recorded decisions
and executable child chunks. It records private-Lead/shared-proposal, budget,
own-dimension, replacement, permission and evidence deltas. The historical audit is
preserved with a supersession notice. Workbench 15/20/21 explicitly own message
origin/return UI and the four-way result/display/interpretation/context distinction;
their minimal context/cursor contract is W1, their complete UI W4.

MP12 is complete as a planning inventory only. It does not pass any acceptance
criterion or close UI implementation, MVPQ-02–12, scientific approvals or the
parallel crosscheck's not-yet-received final output. Segment-map/filter work is not
proof that compare_segments supplies admitted comparative analysis; until a named
producer/method passes admission, the capability and affected coverage remain
explicitly unavailable. Apply the owner's empty-module/report policy when answered.
