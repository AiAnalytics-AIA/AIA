---
status: in-progress
chunks:
  - "[x] 0. This plan, first draft: the goal, the document map, the plan register, the activation matrix, the execution protocol"
  - "[x] 1. Fold the five cohesion traces: the gap register (§6) and the interface register (§5), anchors spot-checked"
  - "[ ] 2. Add each gap's chunk to its plan (the plan's owner reviews; a gap with no plan gets one)"
  - "[ ] 3. Disposition edits: close or re-scope the plans §3 marks 'close' or 'fold' (each plan's owner confirms)"
  - "[ ] 4. Contracts written before the work that needs them (mvp-development-plan.md §5): edit vocabulary, LeadWorkerSpec, ResultsContext, plan authority, CLIENT_REPORTED, acceptance fixtures"
  - "[ ] 5. The ADRs (mvp-development-plan.md §6) and the ADR 0008 amendment for the open posture"
  - "[ ] 6. The activation profile: deploy/develop declares the MVP switches and the smoke reports each READY or NOT_READY without a paid call"
  - "[ ] 7. The operator runbook run once on develop: AI route classes, Brave sign-off, secrets, the reach switches, with the evidence recorded"
  - "[ ] 8. A register check: a stdlib script beside progress.py fails when an active plan is missing from §3 or a wave names a chunk that does not exist"
  - "[ ] 9. The production release checklist exercised once on develop: delete path, backups and restore, alarms, rollback"
  - "[ ] 10. This plan re-verified at each gate (I-0 to I-5), its register and gap list brought up to date"
  - "[ ] 11. The owner answers §11's questions; each answer is recorded in mvp-cohesion.md's register and the plans it moves are edited"
  - "[ ] 12. The V2 prototype's scenarios become acceptance journeys (.planning/evidence/mvp-prototype-v2/), each with the plan chunk that builds what it shows"
  - "[ ] 13. The five new plan files of §6.3 written and registered"
---
# The MVP master plan

Written 2026-10-19 on the owner's request: "ensure all the plans work together towards the same goal,
write the master plan". Written against `develop` @ `769917f` plus #500 (the reach plan, not yet merged).
**Owner: the owner of the lane, S3 (`mvp-development-plan.md` §2), who keeps §3, §5 and §6 true.**
Every claim about code carries `file:line @ SHA`; one without is a hypothesis, marked ◇.

## 1. What this plan is

AIA has 96 plan files, 31 of them not done, with 158 open chunks. Each is a good plan for its own
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
   caller, and the connectors run only under `AIA_DEEP_RESEARCH_AGENT_DIRECTED`.) Rule: a status that a machine can read is read by a machine (chunk 52 of
   `deep-research-web-search`), and a status a person writes names its SHA.
2. **A switch nobody threw.** Every AI button in every stage fails on develop with `route
   bedrock-eu-primary is not approved for CLASS_A_CLIENT_CONFIDENTIAL`, because the route is approved
   for Class C only until an operator records the Bedrock retention and sets four parameters
   (`deploy/develop/README.md` § AI route classes), and the deploy's smoke never looks:
   `smoke.py:207-214 @ 769917f` reports the AI check "not runnable ... never a pass". A green deploy
   hid a product that could not run. Rule: §4's activation matrix is declared in the repository and
   checked on every deploy (chunk 6).
3. **Two plans owning one surface.** `client-workspace` C8 says a dataset's use in a study is "V AIA
   zatím není"; `client-data-in-analysis` builds exactly that. Rule: §3 names one owner per surface
   and one disposition per plan; a plan that disagrees is re-scoped, not left to win by being later.

## 3. The plan register

**Role.** `CORE`: carries an MVP gate. `SUPPORT`: needed, gates nothing alone. `CLOSE`: finished or
superseded, to be verified and closed by its owner. `FOLD`: its remaining work belongs inside another
plan. `POST`: after the MVP, by decision. The dispositions of plans outside the development plan are
**proposed** (◇): each plan's owner confirms in chunk 3.

### 3.1 Core: named in the development plan (17)

| Plan | Open | Session | Waves | Gate | Needs first |
|---|---|---|---|---|---|
| `research-lead-workbench` | 15/26 | S1 | W0 (11), W1 (11, 14-19), W2 (20, 22), W3 (21), W4 (23) | I-1 to I-4 | edit vocabulary, `LeadWorkerSpec` |
| `evidence-integrity` | 5/5 | S2 | W0 (1, 5), W1 (2-3), W3 (4) | I-3 | none |
| `sociomap-formula-corrections` | 12/24 | S2 | W2 | I-2 | method owner (0b is open; 0a is done) |
| `segment-maps-and-drilldown` | 9/9 | S2 | W2 | I-2 | method owner, register entries |
| `audience-catalogue-cpu` | 1/4 | S2 | W0 (4) | I-0 | none |
| `complete-study-report` | 1/11 | S2 | W0 (B6) | I-0 | the AI route widened for Class A and B (§4), audience 4 |
| `deep-research-web-search` | 19/56 | S2 | W0 (1, 51, 53), W1 (52), W2 (6, 33-37), W4 (27, 38) | I-R, I-4 | Brave sign-off (owner) |
| `deep-research` | 1/12 | S2 | with the above | I-4 | chunk 4 (tool usage in the ledger, a migration) is in no wave and not in the lane (§6, G11) |
| `client-budget` | 1/6 | S3 | W1 (CB5) | I-1 | none |
| `client-knowledge-lifecycle` | 8/21 | S3 | W1 (K2e, K2f, K3), W2 (K4, K5) | I-3 | none |
| `client-data-in-analysis` | 8/8 | S3 (4-5 S2) | W3 | I-3 | ADR 0027 policy decision |
| `research-integrity-report` | 4/14 | S3 | W3 (6-8) | I-3 | none |
| `two-roles-human-ai-gates` | 2/12 | S3 | W2, W3 (5b.4) | I-2, I-3 | a client-report contract |
| `develop-spend-attribution` | 4/4 | S3 | W0 (1-2) | I-0 | none |
| `mvp-acceptance-harness` | 8/8 | S3 | W0 (1-3), then every wave | I-0, I-5 | #495 merged |
| `system-prompts-settings` | 1/12 | S1 | W3 (7) | I-3 | worker row |
| `class-b-search-route` | 7/7 | S2 | **after the MVP** (deferred 2026-10-19, owner) | none | none |

### 3.2 Outside the development plan (14), proposed disposition

| Plan | Open | Proposed role | Why | Action |
|---|---|---|---|---|
| `productization-coherence` | 2/18 | SUPPORT (S1) | PC5 (stage track says the design changed after the run) and PC16 (rewording a question keeps its links) land inside artifacts 17-18 | add to workbench 17-18 as acceptance lines |
| `client-workspace` | 4/13 | FOLD into `client-knowledge-lifecycle` (S3) | C6-C9 overlap K3, K2, K6; C8 contradicts ADR 0027 and F19 | re-scope C8, point C6-C9 at the lifecycle chunks |
| `architecture-enforcement` | 4/11 | SUPPORT (S3) | the new tables must pass its contracts; chunk 9 (a digest on scope and claims) is security | schedule beside M1-M6; not gating |
| `ai-research-activation` | 1/4 | FOLD into §4 and chunk 7 | its open chunk is the activation the AI route still lacks | close when chunk 7 here is done |
| `run-recovery-and-truth` | 1/19 | CLOSE | chunk 4 (search beyond Wikipedia) is `deep-research-web-search` 51-52 | owner closes with a pointer |
| `research-agent-workflows` | 4/9 | FOLD | 5-8 are covered by D17's workers, Interpretation Research (30) and `evidence-integrity`, **but its I4 (OI-64, a per-respondent checkpoint) is open and owned by nothing else** (§6, G27) | move I4 to a chunk of the new `run-qc-and-checkpoint` plan, then close with a pointer |
| `mvp-workflow-assurance` | 3/13 | CLOSE A4, A5; keep A3 optional | A4-A5 define an older four-area MVP including Simulation; `mvp-acceptance-harness` replaces them | owner re-scopes, A3 is measured simplification |
| `connected-research-assurance`, `contextual-research-settings-ux`, `desktop-ux-overhaul-handoff` | 1, 1, 3 | CLOSE (verify) | housekeeping chunks ("release checks, deploy, reconcile documentation") of finished work | owners verify against `develop`, close |
| `methodology-tab` | 3/45 | POST | S4d waits on the audit's author, W1c on panel source weighting, X1 is Simulation | none |
| `panel-grounded-respondents` | 3/44 | POST | 7f-7h are the holdout validation that lifts client-facing analysis prose; the MVP's client report carries none (AC-13) | none |
| `sociomapping-engine` | 14/27 | POST | the SOMECS engine depends on the method owner's exports and decisions; the MVP uses `aia-sociomap-3` | none |
| `simulation-studio` | 8/8 | POST | Simulation is out of the MVP (`mvp-acceptance.md`) | S0 recorded as deferred |

A plan not in §3 is a defect of this plan: chunk 8's check fails on it.

## 4. The activation matrix: what must be switched on, and who throws it

A feature that is built and not switched on does not exist for the owner. **The route row reaches further than the first diagnosis said:** with the route at Class C only, every Lead turn, design job, panel fieldwork request and modelled-run analysis parks (a design is Class B by rule, approved knowledge and panel personas Class A: `material_rules.py:79-91`, `ai_fieldwork.py:418-432`, `harness.py:192-203`), and the planned results layer, report writer and map interpreter would too. Production needs the same approval and retention evidence, and `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` for panel lineage (`licence_determinations.py:44`). Each row is a switch, the
gate that needs it, who sets it, and the evidence that it is on. **Chunk 6 declares this profile in
the repository and makes the smoke report each row `READY` or `NOT_READY` with the reason, never a
paid call**, so a green deploy can no longer hide a dead product.

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

| # | Interface | Crosses | Owner | Needed by |
|---|---|---|---|---|
| I1 | **`ResultsContext`**: type, classes, lineage, bound, an external-evidence slot (labelled L, never respondent evidence) | S1 type; S2 and S3 providers; Deep Research bundle (T3 C1, T5 C5) | S1, **in W1**, as an ADR addendum with a `MaterialRule` and a lineage test | before any results layer |
| I2 | **Stage and item vocabulary**: `pipeline.RESEARCH_STAGES`, `StepKey`, the workbench stages, the Lead's `Stage`, `IMPACT_ROOTS`, `design_items` kinds. No Sociomap stage in the pipeline | S1, S2, S3 (T1 C2, T3 C8) | S1, one table beside `domain/edit_ops.py` | W1 |
| I3 | **Three ways to start a run** (Run button, plan card, typed `start_run`) over one `ResearchRuns.start`: which pins and confirmations each passes. The confirmation is a function argument, so a plan authority without `APPROVE_GATE` does not protect it | S1, S2, S3 (T2 C2, T4 A4) | S1 in the orchestration ADR, with a typed start API that has no `confirm_cost_usd` and an import rule | W1 |
| I4 | **The money vocabulary**: envelope cap, `budget_usd`, `spend_confirm_usd`, client ceiling, `clients.budget_usd`, OI-64. The spend limit is a confirmation threshold and `None` means never; the cap is `budget_usd` | S1 envelope, S3 ledger (T2 B1, T4 B1 and B15) | S1 in the orchestration ADR, defined against `budget_usd` | W1 |
| I5 | **What a "dimension" is**: a persona topic, a materialized column, or a segment descriptor | S2 (segments, personas), S3 (K5 materialization) (T2 C1, T3 A2) | S2, in `sociomap-formula-corrections` I0 | W2 |
| I6 | **Straight-liner**: the engine's, the unit QC's and the worker's definition; one flag artifact; what "replace" means | S1 worker, S2 engine and QC (T2 C5, T3 C3) | S2, one definition in `domain/` | W1 |
| I7 | **Fieldwork events to the Fieldwork artifact**: heartbeat, quota-cell fill, respondent grid, park reason | S2 produces, S1 consumes (T2 C9) | S2 writes the payload first | W1 |
| I8 | **The working copy's writers**: `apply_edit_ops` against the PUT, import, reuse, migration, Design Research accept, the web's whole-content autosave. A lock held in one writer is bypassed by the others | S1, S3 (T1 C7, T4 C9) | S1, with a test that no writer changes a locked item | W1 |
| I9 | **Per-change identity** across three accept routes (agent job, Design Research `item_ids`, Lead `indices`) | S1, S2 (T1 C1) | S1 | W1 |
| I10 | **Brief materials, client sources and the data contract**: `briefing.attachments`, `brief_signature` in Python and TypeScript, `design_material` | S1, S3 (T1 C3) | S3 writes the contract, S1 adopts it | W1 |
| I11 | **Sociomap declarations, lock and unlock**: the editor, the lock rule and the ledger row | S1, S2, S3 (T1 C5, T3 C9) | S1 builds the editor against S2's fields | W1 |
| I12 | **Approve and Export panel** inside the Report artifact | S3 panel, S1 slot (T3 C2) | S1 hosts a slot, same wave | W2 |
| I13 | **Map snapshot**: the renderer, the approvable object, the ledger shape | S2 figure, S3 approval (T3 C5) | S3 owns the object, S2 the deterministic function with camera parameters | W2 |
| I14 | **Accepted report wording, map readings, flags**: an artifact type and the composer input that carries them into a report's fingerprint | S1 workers, S3 composer (T3 C7) | S3 defines the type, S1 writes the worker against it | W3 |
| I15 | **Settings**: the router (S1), the Reach panel (S2, which needs a worker-published composition record the API can read), posture and ceiling (S3) | S1, S2, S3 (T4 C3, T5 C2) | S1 owns the router; S2 writes the record | W1 |
| I16 | **Class and residency rules**: `material_rules.py`, `residency.py`, and the classification code in `web_retrieval.py`, `application/deep_research.py`, `aia_executors/deep_research/*` | S1, S2, S3 (T4 C2, T5 C1) | S2 for Deep Research, S1 for `material_rules`; others open small PRs | W0 |
| I17 | **Ledger writers and closed sets**: `workflow_repository.py`, `workflow_templates.py`, `executors/registry.py` | S1, S2, S3 (T4 C1, C4) | S3 (the lane owner) reviews; each session registers its own kind | W1 |
| I18 | **Population in production**: provisioning, the licence route id, the tier A double for AC-05 | S2, S3 (T2 C10, T4 C7) | S3 | W1 |
| I19 | **Evidence into Client Knowledge**: three plans (`verified_sources`, K2e, deep-research chunk 37), three semantics (item or proposal) | S2, S3 (T5 C3, C6) | S3 decides once; S2 supplies the bundle reader | W2 |
| I20 | **Tool spend, the ledger and AC-15**: Brave and Athena spend is in `budget_reservations`, not the usage ledger | S2 ledger, S3 reconciliation (T5 C9) | S3 | W3 |
| I21 | **A single-origin analysis input** against client-reported numbers | S2, S3 (T3 C4) | S2 designs a two-origin input and its fingerprint before S3's client-data chunk 5 | W3 |
| I22 | **The cost function for a Deep Research start** lives in `routers/deep_research.py:292-340` on the API's env copy; a plan step in the worker needs the same ceiling | S1, S2 (T5 C4) | S2 moves it to the application layer | W1 |
| I23 | **Client-level paid AI** (source proposals, `clients.budget_usd`) against "every AI action goes through the Lead" | S3, S1 (T4 C10) | S3, with an explicit exception recorded in AC-02 | W1 |
| I24 | **`apps/web/src/lib/api.ts` and `i18n/cs.ts`**: one large file each, edited by every session, carrying every refusal message | S1, S2, S3 (T4 C8) | S1 for refusal wording; others by area | W0 |
| I25 | **Prompt slots**: wiring the analysis and Deep Research prompts needs those executors to take a pin | S1 slots, S2 executors (T4 C5) | S2 for the executor half | W3 |
| I26 | **Delete path, ledger, audit and backups**: the ledger FK, audit rows and a restore after a deletion need one rule | all S3 (T5 C7) | S3 | before W5 |


## 6. The gap register

### 6.1 Gaps: a link is missing and no plan builds it

Grouped by what they block. **Goes into** is the plan that takes the chunk (or the new plan of §6.3).

**Activation and operations**

| # | Gap | Goes into |
|---|---|---|
| G1 | **No one can tell a user how to fix a route-class refusal.** Each surface says what is refused (the job error, the Lead pane, source proposals, Progress parks); none says who fixes it; the API cannot evaluate class; `/config` omits retention. The fix is an operator's (SSM), Settings is read-only (T4 A2, B9) | `research-lead-workbench` 11; S3 smoke |
| G2 | **Production route classes and retention evidence** are in no plan; ADR 0010's amendment is develop-only (T4 A3) | `production-environment` |
| G3 | **Readiness cannot see worker egress**: the panel default parks every run when the route lacks Class A, and the API reads no egress key (T2 A1) | `audience-catalogue-cpu` or a readiness chunk (S2), S3 smoke |
| G4 | **The activation profile is not declared** (chunk 6 of this plan) | this plan 6 |
| G5 | **Each connector is UNVERIFIED**, none run live; Common Crawl's AWS side has no Terraform; the focused crawler, triage readers and procurement source are not usable though chunks 16 and 20 were ticked (T5 A5, A6, A16, B1, B15) | `deep-research-web-search` 54, 16, 20, 36 |
| G6 | **No Terraform validation in CI**; two documents assume it; no freeze of auto-deploys during a tier B run; production needs its own ADR 0022 approvals (T5 A10, A11, A17, B9) | `production-environment`, `mvp-acceptance-harness` |
| G7 | **Production environment has no plan file**: `infra/production`, the workflow, RDS, Cognito, the egress proxy (which contradicts fetch from any public host), tag-conditioned IAM (T5 A8, A9, B14) | `production-environment` |
| G8 | **The delete path is blocked four ways**: `ai_usage_events.study_id` and `population_dataset_versions.owner_client_id` have no `ondelete` (`tables.py:1833, 1938-1939`); IAM grants no delete on population children (`main.tf:364-368`); `delete_prefix` exists only on the filesystem store (`storage.py:366`); versioned buckets keep deleted objects 30 days with no `DeleteObjectVersion` grant (T5 A7, B12) | `study-data-lifecycle` |
| G9 | **The tagged-profile plan conflicts with the code**: its ARNs would be refused at worker start (`ai_runtime.py:254, 516` need an `eu.` id), "no Environment tag" is wrong (`versions.tf:34-40`), tool spend is not in the usage ledger so AC-15 reconciles model spend only (T5 A12, B8) | `develop-spend-attribution`, `deep-research` 4 |
| G10 | **The harness is not scheduled**: chunks 4 (doubles for the Lead and workers) and 8 (parity never blocks) are in no wave, the `acceptance` marker is unregistered under `--strict-markers` (`pyproject.toml:276-282`), tier B depends on the deferred `class-b-search-route`; tier A has no population double so cannot prove AC-05 (T5 A13, B6; T2 A11) | `mvp-acceptance-harness` |

**Money and orchestration**

| # | Gap | Goes into |
|---|---|---|
| G11 | **The envelope is defined against the wrong quantity.** The architecture and F13/F16 call the spend limit "the hard stop"; in code it is a confirmation threshold (null means never ask) and the cap is `budget_usd`, defaulting to 0 for a new study (T2 B1, T4 B1; `routers/scope.py:95`) | `lead-orchestration` |
| G12 | **The envelope, plan card and typed `start_run` are in no plan file.** The workbench plan puts "continue until you need me" after the MVP (D16, chunk 24) and MVP-13 says "one card at a time" (T2 B3, T4 B3) | `lead-orchestration` |
| G13 | **There is no continuation turn**: turns are person-started only; the Lead sees run id and status, not park reasons or spend (T4 A1, T2 C3) | `lead-orchestration` |
| G14 | **A plan's own steps defeat its stale rule**: `proposal_accept.py:117-118` refuses on "head moved" before comparing items, and any job start, rebuild, Lead approval or a visit to the Run stage submits a Design Revision, killing every other pending proposal; a second researcher's action kills the first's (T1 #2, T4 B7) | `working-copy-edit-ops` |
| G15 | **`approve_request` is not bound to the card's revision**; the Lead's 96 KB context against the agents' 64 KB likely returns a 500 on approval ◇ (T4 A10) | `research-lead-workbench` 11 |
| G16 | **The three new workers have no binding, accept path, price or `MaterialRule`**: no `REPORT_WRITING` binding, no result kind for interpretation, wording or flags, no rule for results, module text, maps or report text (T4 A5, T3 A9, A10, T2 A5) | `lead-orchestration`, `report-delivery` |
| G17 | **Lead files cannot be rolled back** (`revisions()` has no caller); admin read and handover, the USER file's handover rule and a departure trigger are unplanned; a second researcher cannot accept the first Lead's edit blocks (turns are private) (T4 A6, A7, A12) | `lead-orchestration` (lifecycle) |

**Working copy and design stages**

| # | Gap | Goes into |
|---|---|---|
| G18 | **Edit vocabulary, operations log, presence, change feed and per-change accept have no chunk**; `apply_edit_ops` as sole writer ignores six existing writers including the web's autosave; the person's editing is 33 `store.update` sites in 9 files and about 1,900 lines of TypeScript with 18.6.6 parity tests: moving it server-side is unsized (T1 A1, A8, T4 A9) | `working-copy-edit-ops` |
| G19 | **Stable identity for objectives, research questions, hypotheses and options**: keyed by normalised text (`design_items.py:120-172`), so a reword is remove plus add, `FOCUS_ID` cannot encode them, two people adding different questions both touch `content:section:s1`, section reorder is no item (T1 A3, #7) | `working-copy-edit-ops` |
| G20 | **The Lead is never told what a person did with its edits, what others changed, or readiness and outlook**; ADR 0026 decision 2 (Accepted) lists them and `freeze_context` has none (T1 A2, B6) | `lead-orchestration` |
| G21 | **Nobody can set `sociomap_rating` or `context_objects`** (zero web hits), so the hard lock and `sociomap_unlock` have no subject and no chunk (T1 A4, T3 A3) | `working-copy-edit-ops` |
| G22 | **No readiness on a working revision**, no impact or "stage current with revision" surface for a study, so AC-07 as worded cannot be tested; hand edits create no Design Revision (T1 A5, A6, B11, B12) | `working-copy-edit-ops` |
| G23 | **The Lead cannot edit Audience, Dimensions or Sample** (its ops are `set_text`, `list_*`, `question_*`, `set_n`; `propose_audience` returns prose; `suggest_dimensions` returns an empty list); the valid n differs in four places (web 50-5000, Lead 30-40,000, readiness 20-10,000, sampler) (T2 A7, B5) | `research-lead-workbench` 22, S2 |
| G24 | **`touched_items` never reaches the browser; no undo or old-revision route; no dependency rule between coupled change blocks; the Lead vocabulary extension needs a prompt version** (T1 A7, A10-A12) | `working-copy-edit-ops` |
| G25 | **Brief to client-source contract**, the attachment-bytes lifecycle and the 64 KB design ceiling with uncapped attachments (T1 A9, C8, C9) | `client-data-in-analysis`, `study-data-lifecycle` |

**Sample and execution**

| # | Gap | Goes into |
|---|---|---|
| G26 | **Fieldwork repays every respondent on every attempt (OI-64, open) and AC-06 is marked built.** Each attempt starts at the first respondent and stores the dataset at the end (`ai_fieldwork.py:283-326`), `max_attempts=3`, a clean shutdown is a RETRY, and a whole-run retry repays fieldwork (`research.py:834-895`), so each post-fieldwork step the MVP adds is another way to repay (T2 #1, A2, A3, B2) | `run-qc-and-checkpoint` |
| G27 | **QC is not wired**: no template node, step kind, `AIA_RUN_QC_ENABLED` switch or run-key identity; three definitions of straight-liner; no "replace" path from a completed run; no `MaterialRule` for run-derived data (T2 A4-A6, B7, T3 A15) | `run-qc-and-checkpoint` |
| G28 | **An own dimension is built but read by nothing**: K5 (the definition step) is open, no web code calls the materialize route, personas read a fixed column list so a run over a child draws the same respondents; and building costs no money, so "refused when the envelope has no room" has nothing to refuse (T2 #3, A8, B4, B11) | `client-knowledge-lifecycle` K5, S2 |
| G29 | **Quotas and a panel support forecast before a run** do not exist; the Fieldwork artifact's feeds (heartbeat, quota fill, respondent grid, park reason) are unspecified (T2 A9, A10) | `run-qc-and-checkpoint`, workbench 19 |

**Evidence and delivery**

| # | Gap | Goes into |
|---|---|---|
| G30 | **No respondent attributes are stored** (`FieldworkRespondent` holds id, donor, weight, answers: `fieldwork.py:172-181`), so segment maps, filters and the drill-down have nothing to read; "segments by the study's dimensions" has no variable (a dimension is a persona-topic allowlist) (T3 A1, A2; T2 B6) | `segment-maps-and-drilldown` 0 (new) |
| G31 | **Results shows raw aggregates, not admitted claims**, with suppression decided in the browser (`research-execution.ts:373`); no API serves the evidence table or `PrintGrade`; workbench chunk 20 lists "Missing: —" (T3 A4, B15) | `evidence-integrity`, workbench 20 |
| G32 | **MVP-23 is a new rule, not a tightening.** AIA has no 95 % threshold (that is the unit's); it checks numbers in prose only, a finding with no claim ids passes, and the report needs all eight modules complete, so one uncitable module blocks the whole internal report; two parity cases flip (T3 #1) | `evidence-integrity` 1 |
| G33 | **External context never reaches the analysis modules**: `analysis_context` has no caller outside tests and `AnalysisInputs` carries none; the Lead has no Deep Research provider (T3 A5, T5 A15) | `evidence-integrity`, I1 |
| G34 | **AC-13 asks for what does not exist**: no client report PDF (`report_variants.py:78`); "evidence audit" and "legal source-use gate" are NOT_STARTED with no plan; "exports only after approval" contradicts the code (drafts download freely, approval follows: `research.py:2395-2449`); no map-snapshot object, route or renderer; two ledger shapes for it; no reader of the approval ledger for "approved by whom" (T3 A6-A8, A13, B3, B4, B9) | `report-delivery` |
| G35 | **Client-data steps are not placed in the run**: no graph node, no contract-version pin, no impact root; no class or lineage for client-reported numbers going to a model; no accept target for the three new workers (T3 A9, A11, A12) | `client-data-in-analysis`, `report-delivery` |
| G36 | **Evidence into knowledge has three semantics** and a document item holds only `source_id`, so Deep Research never sees the file text (`knowledge_access.py:75-90`); the data-contract permission differs between plans (`APPROVE_GATE` against `PROPOSE_CLIENT_KNOWLEDGE`); ADR 0027 decision 3 uses a blocklist, the plans an allowlist (T5 #8, B10; T3 B8) | `client-knowledge-lifecycle`, `client-data-in-analysis` |

**Deep Research and the open posture**

| # | Gap | Goes into |
|---|---|---|
| G37 | **The open posture needs a setter route, permission test, audit row, profile UI and `api-contract` entry** (specified in `deep-research-web-search` 53 after this review) (T5 A2, T4 A8) | `deep-research-web-search` 53 |
| G38 | **A second live Deep Research run (Interpretation) is needed for "cited context in the report"** (`contextual_report.py:985`) and is absent from AC-11's wording, gate I-4 and the USD 25 budget table (T5 A14) | `mvp-acceptance-harness` 1, 7 |

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

The traces found work no plan owns. Each becomes one plan file with its chunks (master-plan chunk 13),
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

Segment attributes (G30) are chunk 0 of `segment-maps-and-drilldown`, not a plan, because the method owner
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
This plan's register is re-verified at every gate (chunk 10), and a session that finds a plan not in
§3, or a chunk a wave names that does not exist, fixes §3 in its PR, never in chat.

**Incidents and rollback.** A bad deploy is rolled back by the workflow's own input (an older
schema-compatible SHA with migrations unchecked, `deploy-develop.yml:24`); the runbook is
`deploy/develop/README.md`. Production adds the same with an RDS snapshot first.

**Who throws a switch.** An operator, from the runbook, with the evidence written down (chunk 7). A
session never asks for credentials in chat: a read-only credential goes in the environment's secrets,
and a write step is a person's.

## 9. The release to production

Before the first release: the delete path (database cascade, S3 prefixes, backups, with RDS snapshot
retention of 14 days stated), backups and a restore exercised once, the cost alarms and the tagged
Bedrock profiles reconciling to the usage ledger within USD 0.01 (AC-15), the cutover rollback
rehearsed on develop, the Cognito and Google callbacks for the production hostname, and the
activation profile of §4 `READY` on the production host. The hostname, RDS sizing and Bedrock quota are
still the owner's and an operator's (`mvp-target-architecture.md` §9).

## 10. Risks of the whole

| Risk | Consequence | What holds it |
|---|---|---|
| A built feature stays switched off | the owner sees a broken product (§2.2) | §4 and chunk 6 |
| S1 is the critical path and carries the Lead, the artifacts and the plan card | the date slips | the fewest side tasks; S2 and S3 carry everything that can wait |
| The method owner has not answered | segment maps, clustering and register entries wait | decisions named in `mvp-cohesion.md`; no dates yet |
| Classification is deferred and a client is marked OPEN | an OPEN client's queries reach Brave unchecked | the audited flag is the only guard, stated |
| Plans drift again | this plan goes stale | chunk 8, and the rule in §8 |

## 11. Questions for the owner

Ordered by what each blocks. Each has a recommendation; none is decided until the owner answers, and each
answer is recorded in `mvp-cohesion.md`'s register (chunk 11). "Row" means a row of
`.planning/evidence/mvp-prototype-v2/conformance.md`; `G` and `I` rows are §6.1 and §5.

| # | Question | Why it matters | Recommendation |
|---|---|---|---|
| 1 | **Which design is canonical, the V2 prototype or the V3 boards?** They overlap: V3 draws per-step artifacts with content the prototype may lack (breadth options, assumptions tracked across stages) | the artifact chunks 17-22 build one of them | V2 is the behaviour spec (it runs and has twenty scenarios); V3 stays the content spec wherever it adds; chunk 12 lists the differences |
| 2 | **How does a run start?** The prototype: each start is a person's decision card and "continue" stops at the first human decision. Your decision: a plan is approved once and the Lead runs its steps inside the envelope, fieldwork included (rows 6, 7) | the envelope, the plan card and the I-1 gate; workbench D16 puts "continue" after the MVP | The prototype's decision card **is** the plan card with one item. The plan lists "start fieldwork, ceiling 18.40 USD" and you approve the card once; nothing paid starts outside an approved card. Fixes D16 and chunk 24 |
| 3 | **One Lead per researcher, or one conversation per Study?** The prototype has one per Study with a return summary (row 1); you decided each researcher has their own, private (Q18, Q19, Q26) | storage, retention, the return summary (row 29), what a second researcher sees | Keep yours. The return summary is built from the researcher's own turns plus the study's change feed |
| 4 | **The Deep Research permission panel states strict class rules** ("a query derived from confidential material inherits its class; client material not allowed, even paraphrased"). You deferred classification on 2026-10-19 (row 30) | the panel is the screen the owner reads | Show the client's posture (OPEN or CLASSIFIED) and what it means; the strict text applies to CLASSIFIED only |
| 5 | **Money.** The prototype shows one meter and a breakdown: limit, spent, remaining, a confirmation threshold, research per run. You decided two meters and an envelope as a slice of the spend limit. In code the "spend limit" is a confirmation threshold (null means never) and the cap is `budget_usd` (G11, row 9) | the envelope is defined against the wrong quantity until this is settled | The envelope is a cap the researcher sets per study, below `budget_usd`; `spend_confirm_usd` stays a per-start threshold beside it; the header shows spent against `budget_usd`, the envelope on click |
| 6 | **What is a segment?** A cell of "the study's dimensions" has no variable: a dimension is a persona topic, and no respondent attribute is stored (G30, I5) | segment maps, filters and the drill-down have nothing to read | Segments are the quota-cell fields that sampling already uses (age group, sex, region, education from n 700), stored per respondent; clustering waits for the method owner |
| 7 | **AC-13**: is a client PDF in the MVP, what are the "evidence audit" and the "legal source-use gate" (both NOT_STARTED, no plan), and are exports allowed only after approval or approved after download (G34)? | the report's release criterion | Client report DOCX only in the MVP and the criterion amended; the two gates defined as the existing report validation plus the source-class check; client exports only after approval, internal drafts downloadable |
| 8 | **Which prototype capabilities marked "navrženo" are in the MVP?** Assumptions with Deep Research evidence, open-answer coding, semantic report edits, respondent replacement, the return summary (rows 16, 21, 27, 28, 29) | each is a design item, a worker or a methodology decision | In: assumptions (a design-item kind) and bounded semantic report edits with a claim check. After: open-answer coding and replacement (methodology undetermined). The return summary follows question 3 |
| 9 | **Auto-accept**: D18 lets structural edits auto-apply per stage; cohesion and the architecture say text only | the edit vocabulary's contract, `is_text_edit` | Text only in the MVP; D18 after |
| 10 | **Report proposal kinds and draft numbering** against ADR 0016 | whether a report edit can reopen fieldwork | A separate draft counter; a report edit never reopens a run (the prototype's D6) |
| 11 | **Fix OI-64 first?** Fieldwork repays every respondent on every attempt (G26), and every step the MVP adds after fieldwork is another way to repay | cost, and AC-06 is marked built | Yes: the first S2 item in W1, before QC or segment steps |
| 12 | **MVP-23's rule**: a module with no citable finding blocks the whole internal report (the report needs all eight modules). Is that wanted? (G32) | whether one weak module stops a report | An explicit "no finding stated, and why" marker per module; the report proceeds with the gap named |
| 13 | **The delete path** is blocked four ways (G8); retention is "until a person deletes it" | production release | Approve `study-data-lifecycle` as a new plan; state backups 14 days and bucket versions 30 days as the deletion horizon |
| 14 | **Common Crawl in the first activation?** It needs AWS pieces with no Terraform and a us-east-1 residency exception (G5) | the I-R exit | Leave it out of the first activation; Brave, public fetch and the connectors probed live only |
| 15 | **Which scenarios are release-blocking?** Eleven artifacts are release-blocking (D16); the prototype has twenty scenarios | the I-1 to I-4 exits | A to G, L and the exceptions X1, X3, X4, X5, X7; H to K, M and X2, X6 after the first release |
| 16 | **Operator and owner items still open**: the Brave plan, production hostname, RDS size, Bedrock quota and model per tier, the retention evidence for the AI route, the Lead's cost per turn | production release and tier B | Measured on develop in W0-W1; the activation profile (chunk 6) makes each READY or NOT_READY |
| 17 | **Revision semantics.** The prototype shows a version line per artifact ("Obsah z revize 12 · studie je na revizi 14") and marks old Lead answers "platilo pro revizi 13". AIA has a working revision and Design Revisions, not a per-stage content revision (row 10, G22) | the stale markers, the stage track's "changed since" and AC-07 | One study-level Design Revision counter; an artifact's "content from revision n" is **computed** from the revision where its items last changed, never a second store |
