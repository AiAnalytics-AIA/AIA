# Trace 2: the SAMPLE and EXECUTION stages (Audience, Dimensions, Sample, Fieldwork: Run and Progress)

Read-only audit, branch `chore/mvp-master-plan`. Anchors are `file:line @ 82be9e03` (HEAD when written).
The only commit between `f7e80bb9` (where I started) and `82be9e03` adds `.planning/plans/mvp-master-plan.md`,
so every code anchor holds at both. **◇ = I did not open the lines cited (hypothesis).** A claim with no
anchor and no ◇ is a statement about what a plan says, with the plan file named.

Status words: **EXISTS** (anchor opened), **PARTIAL**, **MISSING** (plan and chunk named, or NONE),
**CONTRADICTION** (both sides quoted).

Inputs read first: `CLAUDE.md` §2, `mvp-development-plan.md`, `mvp-target-architecture.md`,
`mvp-cohesion.md`, `plans/research-lead-workbench.md`, `docs/migration/mvp-acceptance.md`, plus (found while
tracing) `mvp-consolidation.md` §4-6, `plans/mvp-master-plan.md`, `plans/evidence-integrity.md`,
`plans/segment-maps-and-drilldown.md`, `plans/mvp-acceptance-harness.md`, `plans/sociomap-formula-corrections.md`
I0-I5, `plans/productization-coherence.md` (ledger and remaining list), `docs/architecture/population.md`,
`docs/architecture/research-journey.md`, and the code named in each row.

**What I could not verify.** Nothing was run (no tests, no workbench, no develop host). Whether LIVE `v17_4_0` is
established on develop, whether its audience catalogue is kept there (`audience-catalogue-cpu` 4 is the open
check), whether n = 300 with age 18-65 passes the sampler's representativeness judgement on LIVE, and what the
Bedrock retention evidence says are all unverified. I did not open `domain/population/audience.py`,
`subpanels.py`, `application/audience_catalogue.py` beyond its `def`, `useStepActivity.ts` or `budget-line.ts`;
rows that rest on them carry ◇.

---

## Capability 1. The audience filter and feasibility preview

**Verdict: the filter, catalogue and counts-only preview are built and consistent with the sampler; the preview is
LIVE-only, drops the quota composition it already computes, is not consulted by readiness or by a run start, and
the Lead has no way to set a filter. Three documents describing it are stale.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Web: catalogue loaded, preview button | EXISTS | `AudienceStep.tsx:100` (catalogue), `:425` (preview), `lib/api.ts:793-795` |
| API: `GET /population/audience-catalogue`, `POST /population/audience-preview` | EXISTS | `routers/population.py:479-555`, `:603-648` |
| Application: LIVE loaded once per process and version, never a row | EXISTS | `application/audience_preview.py:35-86` |
| Application: kept catalogue read | EXISTS (◇ body) | `application/audience_catalogue.py:38` |
| Domain: the preview asks the same two functions a run asks (`select_audience`, `draw_panel_sample`) | EXISTS | `domain/population/audience_preview.py:49-80` |
| Domain: filter language EXACT, 18 subpanels, factor catalogue | EXISTS (◇ not opened) | `domain/population/audience.py`, `subpanels.py`, `audience_catalogue.py` per CLAUDE.md §2 |
| Table: catalogue kept per version, insert-once | EXISTS | `migrations/versions/20261012_a2c4e6f8b0d3_population_version_audience_catalogues.py:29` |
| Operator: catalogue recorded on every develop deploy, bounded to 5 minutes | EXISTS | `deploy/develop/bin/deploy.sh:121,135-138` |
| Develop actually holds a catalogue and CPU is healthy | PARTIAL | `audience-catalogue-cpu` chunk 4 is the one open chunk (`[ ] 4. Pass CI, deploy and verify`); not verified by me |
| API process has the panel mounted | EXISTS | `deploy/develop/docker-compose.yml:185` (`AIA_API_POPULATION_ASSET_ROOT`), `config.py:104-108` (empty means no preview) |
| Preview shows the quota composition before a run | PARTIAL | the audit holds `raw`/`weighted` counts and diffs (`domain/population/sampling.py:403-444`); the preview returns only `status`, `sample_donors`, `effective_n` (`audience_preview.py:73-78`). Build: `research-lead-workbench` 19, named only in `mvp-consolidation.md` §6.2 ("Return the quota composition from the preview", S) |
| Preview over the child population a run may be started on | MISSING | NONE. `AudiencePopulation` is `CZECH_AUDIENCE` (LIVE) in every deployment (`dependencies.py:126-160`); the Run stage offers children (`ExecutionSteps.tsx:866`); the catalogue is kept per LIVE version, a child has none |
| Readiness consults the sampler before a run starts | PARTIAL | readiness's `audience` check is structural (`domain/research_design.py:953-981`); `sampling_unrepresentative`, `sampling_n_exceeds_support` arrive only inside the fieldwork step (`ai_fieldwork.py:378-384`), after the run exists and was confirmed. `GET /research/readiness` never calls the previewer (`routers/research.py:1088-1169`). Plan: NONE |
| The filters reach the respondents | EXISTS | `panel_source.py:103` (filters from `spec.selection`), settled as applied only after the draw: `research_design.py:759-785`, `routers/research.py:990-1000` |
| Lead / AI writes filters or a subpanel | MISSING | NONE. `propose_audience` returns prose; filters "remain researcher-controlled" (`domain/research_agents.py:808-815`). The Lead's edit vocabulary has no audience op (`TextField`, `PlanList`, `SetN`: `domain/research_lead.py:157-167, 293-296`), `FOCUS_ID` has no `audience:` kind (`:176`). Target-architecture §3.1's extended vocabulary (move, merge, section, set, route, scale, comparison) adds none. `research-lead-workbench` 22 assumes the Lead can call "that stage's worker" (D15); the worker cannot apply anything |
| Special panels, own audiences, panel factors | MISSING | by design "V AIA zatím není" (`docs/architecture/research-journey.md:432`); not on the MVP path of AC-05; no plan |
| Docs say what exists | CONTRADICTION | `research-journey.md:121`: "The catalogue, check and uploads read the unit ... AC-05's sufficiency gate is not ported (`audience.definition` `NOT_STARTED`) ... **Sufficiency gate: no owner**"; `parity-matrix.json:1164` `audience.definition` `NOT_STARTED`. Code: the whole preview above |

---

## Capability 2. Dimensions, including an own dimension proposed to client knowledge and built by materialization

**Verdict: the 18 system dimensions work as persona-topic filters; the own-dimension chain has all its ends built
(proposal, approval, materializer, child, run selection) and nothing in the middle (K5) or at the consumer end
(nothing reads the built column). A run "over" a child is a second paid run that changes no respondent.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Web Dimenze: 18 system dimensions plus the client's approved `DIMENSION` items | EXISTS | `PersonaStep.tsx:68-101`, `research/persona.ts:17-37, 53-57` |
| System dimension -> persona topic allowlist, applied at the panel draw | EXISTS | `domain/persona_topics.py:313-322`; I ran `dimension_topic` over all 18 catalogue ids: all map to a topic. `panel_source.py:61-86` records `persona_topic_allowlist` |
| Own dimension request becomes a `DIMENSION` knowledge proposal | EXISTS | `research/persona.ts:282-295`, `PersonaStep.tsx:117-134`, `routers/workspace.py:2308` |
| Proposal approved by a person (gate 1) | EXISTS (◇) | `routers/workspace.py:1936` decision route; not opened |
| Accepted item -> an executable `DimensionDefinition` | MISSING | `client-knowledge-lifecycle` K5 (open, S3, development plan W2). `domain/population/definition.py:3-6`: "K5 will supply this shape ... until then the materialize service takes it as typed input". The proposal's content is `{source_strategy, spec, origin, requested_from}` (`persona.ts:293`), not a definition (kind, target with `EvidenceAnchor`, predictors, missingness) |
| `suggest_dimensions` worker produces something applicable | PARTIAL | `new_dimension_suggestions` with free-text `suggested_predictors`; `result["dimensions"] = []` (`research_agents.py:170-181, 817-820`); no `DimensionDefinition` |
| Materialize route, check, enqueue | EXISTS | `routers/materialize.py:216-290`, `application/materialize.py:136,220`; `docs/architecture/population.md` § Materialized dimensions |
| Worker step `population_materialize`, child to EU S3, registry | EXISTS | `executors/materialize.py:48-133` (header at `:15`); bucket `infra/develop/main.tf:122,311-314`; compose `deploy/develop/docker-compose.yml:306-307` |
| A web caller that starts it ("Build" on the own-dimension chip) | MISSING | `lib/api.ts` has no `population/materializations` call (grep empty); the ledger calls it `operator_only` (`productization-coherence.md` ledger, runs / population_materialize). Named only in `mvp-development-plan.md` W2 S3 "own-dimension chips" and `mvp-cohesion.md` F19; no plan-file chunk text |
| Chip status (waiting, building, ready) joining item, run and child | MISSING | NONE named; no table joins a knowledge item to its materialization run (◇ the extension's `EvidenceAnchor.knowledge_item_id` is the only link) |
| Own dimension is paid by the envelope | CONTRADICTION | `mvp-cohesion.md:545-548` (F19): "it is a run with a cost ... refused when the envelope has no room"; `executors/materialize.py:15`: "No model call and no money" |
| Run selects a child, pinned in identity | EXISTS | `application/research.py:437-448, 605, 636-638`; `routers/research.py:1222`; `ExecutionSteps.tsx:622, 866` |
| Fieldwork loads the child (worker store) | EXISTS (◇ test) | `docs/architecture/population.md` § Selected at run start (P4e2); `executors/registry.py:211-222` |
| Any step reads the child's added column | MISSING | `sociomap-formula-corrections` I1 (open, S2, development plan W2). `panel_personas` reads only `PROFILE/STYLE/FACT_COLUMNS` and signal columns (`panel_persona.py:225-239`); quotas read `QUOTA_FIELDS`. `productization-coherence.md` D-6 ("a run 'over' a materialized child draws the same respondents as over LIVE") is still true. Its recommended disclosure is not on the Run stage: `cs.ts:2410-2414` says only "tentýž návrh nad LIVE a nad dimenzí jsou dva běhy" |
| Audience filter on a child column | MISSING | NONE (catalogue is LIVE's) |
| Segments "defined by the study's dimensions" | MISSING | `segment-maps-and-drilldown` 1 names `DIMENSION_TOPICS` / `persona_topics.py`, but a topic id has no per-respondent value, and the stored respondent is `respondent_id, donor_id, weight, answers` only (`domain/fieldwork.py:172-181`). The producer is `sociomap-formula-corrections` I3 ("Carry eligible dimension values ... beside answers"), which is **not** in segment-maps' "Needs" line |
| Recorded selection says what it is | CONTRADICTION | `domain/research_design.py:280-285`: `SELECTION_NOT_APPLIED` = "no dimension materialization or population binding exists in AIA yet", written into every compiled spec's `selection.reason` (`:712-730`); `docs/architecture/research-journey.md:409` repeats it. Code: `materialize.py`, `population_binding`, the persona allowlist all exist |

---

## Capability 3. The sample and quotas before a run

**Verdict: the sampler, quotas, judgement and cost ceiling are built; the browser, the Lead, readiness and the sampler
each hold a different idea of a valid n; quotas are visible after the run, not before; the default (panel) path has no
support forecast.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Sample stage screen | EXISTS (read-only) | `components/workbench/SampleView.tsx:1-40` (n is set in Dimenze, audience in its step) |
| Recommended n | PARTIAL | a business rule in the browser: 300/400/500 (`research/persona.ts:165-175`); no server twin |
| n bounds | CONTRADICTION | web clamps 50-5000 (`persona.ts:178-181`); the Lead's `set_n` accepts 30-40,000 (`domain/research_lead.py:293-296`); readiness default 20-10,000 (`domain/research_design.py:82, 849-858`); the sampler refuses n above the audience's rows, LIVE has 18,766 (`domain/population/sampling.py:516-521`) |
| Quotas by code, weighted draw, raking, audit | EXISTS | `sampling.py:164-200, 333, 496-598` |
| Representativeness judgement and refusal by name | EXISTS | `sampling.py:453-467` (`sampling_unrepresentative`) |
| Weight declared, none = fail | EXISTS | `sampling.py:522-528` (`sampling_no_weight`) |
| Quotas shown before a run | PARTIAL | see Capability 1 (preview drops them); the sample is drawn only inside the fieldwork step and recorded in provenance after (`panel_source.py:64-86`, `sampling.py:483-493`) |
| Support forecast, roster | EXISTS | `domain/support_forecast.py:150-227`, wired at `application/research.py:683-691, 1106-1113` |
| Support forecast, panel (the default path) | PARTIAL | "unknown", WARN, "se ukáže až při výběru respondentů" (`support_forecast.py:175-186`); the preview already knows `sample_donors` but is not joined. Plan: NONE |
| Run cost ceiling shown before start | EXISTS | `domain/run_cost.py:79-120`, `application/research.py:456-477`, `routers/research.py:1113-1148`; fieldwork and analysis only, one pass |
| Quota-cell fill during fieldwork | MISSING | `research-lead-workbench` 19 ("Per-respondent and quota fill ... Missing"; `mvp-consolidation.md` §6.2 "S-M"); today `progress` fires every 10 respondents with counts only (`ai_fieldwork.py:146, 324-325`) |
| n = 300, age 18-65 on LIVE passes the judgement | unverified | the acceptance study (`mvp-acceptance.md` §1) assumes it; tolerances are `max(0.50, 100/n)` raw and `max(0.25, 100/n)` weighted (`sampling.py:447-450`); not run by me |

---

## Capability 4. Starting a run: readiness, persona source, population binding, spend confirmation, budget reservation, the planned envelope

**Verdict: the start path is complete and honest about its gates today. The MVP's envelope, plan card and typed
`start_run` command are described in the development plan and the target architecture but are in no plan file, and the
documents disagree about what "the spend limit" is. The population-built default is gated by six independent switches,
one of which the API cannot see.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Web Run stage: readiness, `CostCard`, respondent choice, population choice, start | EXISTS | `ExecutionSteps.tsx:227, 622, 817-826, 866, 910` |
| API readiness (checks, ceiling, `persona_sources`, answerability) and `POST /research/runs` | EXISTS | `routers/research.py:1088-1169`, `:1199-1244` |
| Persona source: offered by the deployment, never swapped | EXISTS | `routers/research.py:1003-1056` |
| Population-built is the default | PARTIAL | only when `AIA_AI_POPULATION_PERSONAS_ENABLED` is on **and** the source is `ai_runtime` (`routers/research.py:1003-1013`); the flag defaults `False` in `config.py:103`, `docker-compose.yml:36, 262`, `env.example:147`. Switch: `complete-study-report` B6 (open) |
| Panel requests are Class A, route is Class C | PARTIAL | `domain/ai_respondent.py:322-325` ("Anything else is Class A"); route Class C only until an operator records retention and sets four parameters (`deploy/develop/README.md:412-419`). Plan: operator step in `mvp-development-plan.md` W0 S3 and `mvp-master-plan.md` §4 row 127, listed there for "every design job", not for fieldwork |
| Readiness knows the worker will park | MISSING | NONE. The API reads no egress key (grep of `routers/research.py`, `config.py`, `application/research.py` empty); `productization-coherence.md` F024 "readiness-blind-to-worker-egress" has no chunk (it is a "safe engineering, M" candidate only). The master plan's evidence for the switch ("the Run stage offers the panel", `mvp-master-plan.md:130`) is true while every default run still parks |
| `ResearchRuns.start`: readiness, answerability, pins, key | EXISTS | `application/research.py:479-832` |
| Population binding recorded | EXISTS | `research.py:414-448`, `tables.py:2056`, `workflow_repository.py:727` |
| Same design after LIVE moves returns the old run | PARTIAL | `research.py:426-428` (a found run keeps its binding) with the key carrying only a child id (`:636-638`); `productization-coherence.md` D-7 still true; no chunk |
| Spend confirmation at a threshold, recorded in the ledger | EXISTS | `research.py:724-741, 824-831`; ADR 0019 gate 2 ("above a threshold ... confirmed", `0019-*.md:66`) |
| Budget reserved per paid call under the study row lock; park when the cap is reached | EXISTS | `workflow_repository.py:1140-1262` (`budget_usd - spent - outstanding`, `BudgetExceeded`), `domain/workflow.py:579-585` (`PARK_BUDGET`) |
| A study is created with budget 0 | PARTIAL | `routers/scope.py:95` default `0.0`, `scope_repository.py:378`; every paid step parks until a person sets it. Not mentioned in the acceptance setup (`mvp-acceptance.md` §1 says "budget USD 25") |
| "The spend limit stays the hard stop" | CONTRADICTION | `mvp-target-architecture.md:133-134`: "The spend limit (`PUT /studies/{id}/spend-confirm`) stays the hard stop for everything"; `mvp-cohesion.md` F13/F16 "envelope is a slice of the spend limit". Code: `spend_confirm_usd` is a confirmation threshold, null = never asks (`application/research.py:452-454, 724-741`); the hard cap is `budget_usd` (`workflow_repository.py:1240-1244`) |
| Per-study envelope, plan card, `lead_plan` workflow, plan authority (M4, M5) | MISSING | no code (grep `envelope` hits only terrain/DOCX code). Home: `mvp-development-plan.md` W1 and `mvp-target-architecture.md` §3.3-3.4. **No plan-file chunk**: `research-lead-workbench` front-matter has none and puts "continue until you need me" in chunk 24, after the MVP (D16) |
| Envelope plan vs older decisions | CONTRADICTION | `overview.md:584` MVP-13 "one card at a time ... no standing budget in the MVP" and `mvp-acceptance.md:77` AC-02 "a paid worker job starts only on a person's approval card", against `mvp-development-plan.md` W1 "the envelope and plan card (M4, M5)" |
| Envelope accounting by cost ceiling "never exceeds the cap" | PARTIAL | `mvp-target-architecture.md:128-131`; the run's ceiling counts one pass of fieldwork (`run_cost.py:99-120`) but a retry or a rolling deploy asks every respondent again (OI-64, Capability 5), so the sum of ceilings is not an upper bound of spend. The real stop is the per-call reservation |
| Typed `start_run {revision_id}` command | MISSING | `mvp-target-architecture.md:159-169, 267` (◇ name). The body would have to carry what `RunStart` carries (`routers/research.py:270-281`): `persona_source`, `population_version_id`, `acknowledge_research_questions`, `confirm_cost_usd`; none is specified |
| Lead's approved job holds the limit | EXISTS | `application/research_lead.py:678-760` (agent jobs only; runs "open the stage", D7) |
| Manual agent-job start holds the limit | MISSING | `ResearchAgentJobs.start` (`research.py:1311-1410`) reads no limit (grep empty). Fix is "W0 S1, a fix" in `mvp-development-plan.md` §3 and `mvp-cohesion.md` F5; only `research-lead-workbench` F1 (a finding, not a chunk) carries it |
| "Every AI action through the Lead" vs the Run stage's Start button | PARTIAL | `mvp-acceptance.md:77` AC-02, `overview.md` MVP-8 vs `research-lead-workbench` D7 (runs start from their stage); whether chunk 19's Fieldwork artifact keeps the button is unstated |

---

## Capability 5. Fieldwork in the worker: claim, lease, heartbeat, recovery, cancel, retry, park reasons

**Verdict: the engine is sound and is the best-built part of this group. Its one hole is the fieldwork step itself:
every attempt asks every respondent again (OI-64), up to three attempts, on a retry, a quota resume, a clean worker
shutdown or a lapsed lease. No MVP document owns it; the acceptance criterion that depends on it is marked built.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Claim | EXISTS | `workflow_repository.py:892` (`claim_next`), `worker.py:245` |
| Lease and heartbeat thread, fenced writes | EXISTS | `workflow_repository.py:1040-1080`, `worker/heartbeat.py:1-80`, `worker/context.py:125-138` (checkpoint order: lease, cancel, shutdown) |
| Recovery decisions | EXISTS | `domain/workflow.py:538-657`; paid call with unknown outcome -> `RECOVERY_REQUIRED`; `recover_expired_attempts` `workflow_repository.py:1954` |
| Cancel | EXISTS | `application/research.py:1030`, `routers/research.py:1312-1326` |
| Retry whole run | PARTIAL | `research.py:834-895`; only `FAILED`/`CANCELLED` are retryable (`domain/research.py:56-68`); a whole-run retry buys fieldwork again; `retry_analysis` alone passes a `FrozenDataset` (`:865-895`). `productization-coherence.md` remaining list R3 ("a whole-run retry ... reuses its dataset") is a candidate, not a chunk |
| Fieldwork attempt never resumes a half-done respondent list | CONTRADICTION | `mvp-acceptance.md:81` AC-06 "Killing the worker mid-stage loses no work"; `mvp-cohesion.md:558` marks AC-06 "○ built, needs only the release run"; `open-items.md:2240-2271` OI-64 "a retry ... asks every respondent again and the earlier attempt's answered calls stay charged", **Open**. Code: one loop with no persistence (`ai_fieldwork.py:283-326`), dataset stored once at the end with the attempt id in its fingerprint (`executors/research.py:441-470`), `max_attempts=3` (`workflow_templates.py:223`), a clean release is a RETRY (`workflow.py:660-686`) |
| Owner of the OI-64 fix | MISSING | `research-agent-workflows.md:96` "I4. OI-64 ..." sits in a body list, not the front-matter; that plan is dispositioned CLOSE (verify) at `mvp-master-plan.md:107`, "5-8 are covered by ...", which would drop I4. `productization-coherence.md` D-17 / F022 say "Fix OI-64 (per-respondent checkpoint, planned)". Precedent for the shape: `client_work_journal` (F-K5, `client-knowledge-lifecycle.md:656-668`) |
| Park: `ai_runtime_unavailable` | EXISTS | `domain/workflow.py:404, 601-607`; resume `application/research.py:294-320`, `routers/research.py:1408-1430`, `ExecutionSteps.tsx:1249` |
| Park: `panel_personas_unavailable`, `population_unavailable`, `egress_route_not_approved_for_class` | PARTIAL | `ai_fieldwork.py:349-359, 393-401, 252-262`. All end as `waiting_reason = ai_runtime_unavailable`; the specific code is in `error_json`, and the step response exposes only `error_message` (`routers/research.py:294-326, 915`), so neither the screen nor the Lead can tell them apart |
| Fieldwork reaches `RECOVERY_REQUIRED` and the person can act | PARTIAL | `recovery_reason` is on the step (`routers/research.py:322-326`); retry is refused for it, the way out is cancel then retry, which repays all fieldwork; `productization-coherence.md` F021 (not reported to an operator) open |
| Post-fieldwork steps in the research template | PARTIAL | graph is compile, preflight, run, aggregate, sociomap (+ analysis, report, sociomapping) (`domain/workflow_templates.py:109-117, 213-258`); QC and segment maps are not nodes |
| Executors registered in the worker's default composition | EXISTS | `executors/registry.py:211-222` (◇ body) |

---

## Capability 6. The straight-liner and run QC check (planned)

**Verdict: nothing is built. The plan is `evidence-integrity` 2-4 and workbench worker 11. Three different "straight-liner"
rules are already in play, the QC step is wired nowhere, the worker has no data-class rule, and "replace" has no start path.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| QC pure function EXACT against `qc.kontrola` | MISSING | `evidence-integrity` 2 (S2, W1); legacy `legacy/npc-panel-18.6.6/app/qc.py:70, 200-207`; `parity-matrix.json:1000` `analysis.qc` `NOT_STARTED` |
| QC stored beside the run and shown as warnings, never a gate | MISSING | `evidence-integrity` 3 (S2, W1). The chunk says "one artifact per run"; **no chunk adds a node** to `_RESEARCH_GRAPH` / `RESEARCH_KINDS` (`workflow_templates.py:101-117`), registers an executor, adds the kill switch `AIA_RUN_QC_ENABLED` (named only in `mvp-target-architecture.md:244`), or decides whether the node is in the run key. Plan: NONE |
| What "straight-liner" means | CONTRADICTION | engine: every rated object given the same score, excluded from the map (`domain/sociomap/engine.py:84-109`, EXISTS, chunk 1c done); legacy QC: same answer on all scale questions, share above 0.15 (`qc.py:200-207`); worker D17: "identical battery answers" (`research-lead-workbench.md` D17). Three populations, one word |
| Worker `flag_straightliners` | MISSING | `research-lead-workbench` 11 (registry, open) then `evidence-integrity` 4 (W3); `ResearchAction` has eight values (`research_agents.py:35-43`) |
| Worker's data-class rule | MISSING | NONE. `MaterialRule` names nine rules and none is for run flags or dataset-derived material (`domain/material_rules.py:59-70`); "material no rule names still refuses" (CLAUDE.md §2). `LeadWorkerSpec` row promises a "data-class rule" column, not its values |
| Replace a flagged respondent = a new linked run | MISSING | `evidence-integrity` 4 "decide first"; `retryable` accepts only FAILED/CANCELLED (`domain/research.py:56-68`), so a COMPLETED run has no restart path; no mechanism reuses the unflagged respondents (fingerprint includes the attempt, `executors/research.py:441-444`); a replacement run repays all fieldwork |
| QC reaches the Lead | PARTIAL | `ResultsContext` includes QC (`mvp-development-plan.md` §5 table); the runs layer today is id, status, revision (`application/research_lead.py:882-889`) |
| Speeder check | n/a | no response time exists for an AI respondent (`evidence-integrity.md` "What exists"); recorded as not applicable |

---

## Capability 7. The Progress screen: step activity, events, spend, provenance

**Verdict: Progress is built and truthful for what the engine reports. The Fieldwork artifact V3 draws five things the
backend does not produce (heartbeat, respondent grid, quota fill, live per-request spend, a park code), and the Lead cannot
see execution at all.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Run with steps, polled | EXISTS | `routers/research.py:1262-1296`, `ExecutionSteps.tsx:1191` |
| Events after a cursor; step id on each | EXISTS | `routers/research.py:1280-1309` |
| Step activity folded in words, orb | EXISTS (◇ hook) | `lib/step-activity.ts:67-158`, `ExecutionSteps.tsx:1283`, `components/rehome/research/StepActivityPanel.tsx` |
| Fieldwork reports per respondent or per request | PARTIAL | `AIA_AI_STEP_EVENTS` covers "a research agent's and an analysis module's" requests only (`ai_runtime.py:462-464`); fieldwork writes a count every 10 respondents (`ai_fieldwork.py:146, 324-325`) |
| Spend and ceiling | EXISTS | `actual_cost_usd` with VIEW_COSTS (`routers/research.py:452-453`), `CostCard` `ExecutionSteps.tsx:227` |
| Provenance: who answered, population, selection applied or not | EXISTS | `ExecutionSteps.tsx:186` (`RespondentsReceipt`), `research_design.py:786-815`, `panel_source.py:64-86` |
| Heartbeat and lease on screen | MISSING | `ResearchStepResponse` has no heartbeat or lease field (`routers/research.py:294-326`) while `step_attempts.heartbeat_at` exists (`workflow_repository.py:1073`); `research-lead-workbench` 19 lists "run state and heartbeat" |
| Respondent grid and quota fill | MISSING | `research-lead-workbench` 19, `mvp-consolidation.md` §6.2 ("Per-quota-cell fill would need the draw's cells in the event", S-M); producer is the fieldwork step (S2), consumer the artifact (S1), no payload contract |
| Park reason code on the step | PARTIAL | see Capability 5 |
| Lead sees run state, steps, park, spend, selection receipt | MISSING | NONE. Lead context's runs layer: id, status, design revision only (`application/research_lead.py:882-889`); it does see budget, spent, spend limit (`:869-875`). `ResultsContext` (F4) covers results, not execution |
| Stage track says the design changed after the run it shows | PARTIAL | `productization-coherence` PC5 second half, R7 (server-side digest); open |

---

## Capability 8. The budget cap park and lift

**Verdict: built end to end and consistent for every kind of study work. The only trouble is vocabulary (cap versus limit)
and what the envelope will mean beside it.**

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Reservation fails, step parks without spending an attempt | EXISTS | `workflow_repository.py:1243-1244`, `domain/workflow.py:579-585` |
| Lift: raise the study budget, resume each waiting step, ledger row per step | EXISTS | `application/research.py:253-291`, `:1036`; needs `APPROVE_BUDGET` + `MANAGE_STUDY_BUDGET` |
| API and web | EXISTS | `routers/research.py:1341-1379`, `ExecutionSteps.tsx:1285` + `BudgetLift.tsx` |
| Same lift for agent jobs and Deep Research | EXISTS | `routers/research.py:2815`, `routers/deep_research.py:636` (PC4 `[x]`) |
| Ledger row says it does | CONTRADICTION | `productization-coherence.md:856` "Lift a budget wait (Deep Research, research-agent jobs) | no | There is no route" and `:857`, `:872-873`; stale against the rows above |
| Lead and envelope respect lift as human-only | EXISTS (design) | `adr/0026-...md:191` (budget.lift, study.spend_limit human-only); planned `mvp-target-architecture.md:154-157` |
| Whether a plan step parks at a lift | MISSING | no code (envelope unbuilt); see Capability 4 |
| Per-run hard cap (18.6.6 `budget_guard`) | n/a | `parity-matrix.json:1329` `cost.hard_cap` `NOT_STARTED`; AIA's cap is the study's; AC-04 names `cost.hard_cap` and `cost.estimation` (`NOT_STARTED`, `run_cost.py` exists): the matrix is stale |

---

## Other cross-cutting findings in this group

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Tier A cannot run AC-05 through HTTP | MISSING | AC-05 says "LIVE v17_4_0". The existing panel tests inject a fictional loader because "the production loader reads the v17 contract, which fictional rows cannot meet" (`apps/executors/tests/grounded_world.py:1-9`); the workbench installs a fictional population in the API stand-in only (`dependencies.py:126-135`). `mvp-acceptance-harness` 4 lists model and retrieval doubles, no population double. Owner: NONE |
| AC-07 "reuses every other stage's artifacts" | CONTRADICTION | `mvp-acceptance.md:82`. `impact_preview` is reachable only through the generic project routes (`routers/projects.py:308-340`), which the research flow does not use; a new revision is a new run key (`application/research.py:609`) and AI fieldwork never reuses (`executors/research.py:441-444`; `run-recovery-and-truth.md:74`). Cohesion §3 marks AC-07 "○ built" |
| Production has the population | MISSING | NONE. Develop syncs 19 licence-bound files by hand and imports, establishes, records (`deploy/develop/README.md`, `bin/sync-population.sh`); target architecture §6.2 lists the `population` bucket, not the asset root, the import or `record-*`; there is no `infra/production` and no production plan file |
| Doc and ledger staleness (low severity) | CONTRADICTION | `parity-matrix.json:2405` ("Not yet consumed by any research step"), `:2474` ("The ANALYSIS view refuses to load"), `:1164` `audience.definition` `NOT_STARTED`, `respondents.layers` "Not ported: dispozice, osobnost ..." (`:3005`) against `panel_persona.py:225-239`, `AudienceDimensionsEnricher` (`dependencies.py:155`) |

---

## Counts (rows above with a status word in the Status column)

109 link rows: EXISTS 48, PARTIAL 21, MISSING 26, CONTRADICTION 11, not applicable 2, unverified 1 (counted from the Status column of the tables above; some EXISTS rows are marked ◇ for unopened bodies).

---

## (A) GAPS: a link MISSING and no plan builds it

1. **Readiness is blind to worker egress.** The panel becomes the default with one flag, every default run then parks if the route is not approved for Class A; the API reads no egress key. `productization-coherence.md` F024; `routers/research.py:1003-1056` vs `domain/ai_respondent.py:322-325`. Owner: S2 (readiness) with S3's activation smoke.
2. **No owner for OI-64** (per-respondent checkpoint). Only `research-agent-workflows` I4, a plan the master plan closes (`mvp-master-plan.md:107`). Owner: S2 (`ai_fieldwork.py`), shape of `client_work_journal`.
3. **Whole-run retry repays fieldwork** (R3, `productization-coherence.md` remaining list). Every new post-fieldwork step (QC, segment maps, client-data compute) adds a way to fail after fieldwork. Owner: S2, before those steps land.
4. **QC step wiring**: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, run-key identity. `evidence-integrity` 2-3 stop at "an artifact". Owner: S2.
5. **A `MaterialRule` (and lineage) for run-derived material** sent to `flag_straightliners` and the map interpreter (`material_rules.py:59-70`). Owner: S1 (worker row) with S2.
6. **"Replace" a flagged respondent**: no start path from a COMPLETED run, no exclusion pin, no reuse of the other respondents' paid answers. Owner: S2.
7. **The Lead cannot edit audience filters, the dimension selection, the persona source or the population choice**, and `propose_audience` / `suggest_dimensions` apply nothing (`research_lead.py:157-167, 293`; `research_agents.py:808-820`). `research-lead-workbench` 22 assumes it. Owner: S1 (vocabulary) with S2 (what a valid filter is).
8. **A web caller for materialization** (the own-dimension "Build" chip) and its status join (item, run, child). Only `mvp-development-plan.md` W2 prose. Owner: S3 (K5).
9. **Quotas and a panel support forecast before a run**: preview drops the composition, readiness does not call the previewer for the panel path. Quotas are named only in `mvp-consolidation.md` §6.2. Owner: S2.
10. **Fieldwork artifact feeds**: heartbeat, per-quota-cell fill, respondent grid, park reason code. Owner: S2 produces, S1 chunk 19 consumes.
11. **Tier A population double** for AC-05 (fictional population composed in both API and worker over HTTP). Owner: S3 (harness chunk 4) with S2.
12. **Population provisioning in production** (asset root, import, establish, `record-dictionary`, `record-catalogue`, the store). Owner: S3.
13. **Production-safe disclosure of D-6** (a child is read by no respondent) on the Run stage; `cs.ts:2410-2414` does not say it. Owner: S2 until I1 lands.

## (B) CONTRADICTIONS

1. **Spend limit is a hard stop** (`mvp-target-architecture.md:133-134`, cohesion F13/F16) vs a confirmation threshold with `budget_usd` as the hard cap (`application/research.py:452-454, 724-741`; `workflow_repository.py:1240-1244`; `adr/0019:66`).
2. **AC-06 "loses no work" built** (`mvp-acceptance.md:81`, `mvp-cohesion.md:558`) vs OI-64 open (`open-items.md:2240-2271`; `ai_fieldwork.py:283-326`).
3. **Envelope and plan card in W1** (`mvp-development-plan.md`) vs MVP-13 "one card at a time" (`overview.md:584`), AC-02 (`mvp-acceptance.md:77`) and workbench D16 / chunk 24 "after the MVP".
4. **An own dimension is "a run with a cost" the envelope can refuse** (`mvp-cohesion.md:545-548`) vs "no model call and no money" (`executors/materialize.py:15`).
5. **Four valid-n ranges**: web 50-5000 (`persona.ts:178-181`), Lead 30-40,000 (`research_lead.py:293-296`), readiness 20-10,000 (`research_design.py:82`), sampler at most the audience's rows (`sampling.py:516-521`).
6. **Segments by "selected dimensions"** (`segment-maps-and-drilldown` 1, naming `persona_topics.py`) vs a stored respondent with no descriptors (`fieldwork.py:172-181`); the producer I3 is not in the plan's "Needs".
7. **Three straight-liner definitions** (`sociomap/engine.py:84-109`, `qc.py:200-207`, workbench D17).
8. **`SELECTION_NOT_APPLIED` text** says no materialization or binding exists (`research_design.py:280-285`, `research-journey.md:409`); both exist.
9. **AC-07 reuse** vs AI fieldwork never reused and `impact_preview` unused by the research flow (`mvp-acceptance.md:82`; `executors/research.py:441-444`; `routers/projects.py:308-340`).
10. **Activation evidence "the Run stage offers the panel"** (`mvp-master-plan.md:130`) vs a default run that still parks on the route class (F024).
11. **Master plan closes `research-agent-workflows`** (`mvp-master-plan.md:107`) while its I4 (OI-64) is open (`research-agent-workflows.md:96`).
12. **Stale status text**: `research-journey.md:121`, `parity-matrix.json:1164, 2405, 2474, 3005`, `productization-coherence.md:856-857, 872-873`.

## (C) INTERFACES crossing plans or sessions with no owner

1. **K5 (S3) <-> sociomap I1/I3 (S2) <-> segment-maps (S2): what a "dimension" is.** Three meanings (persona topic, materialized column, segment descriptor). Owner: S2 writes the role in `sociomap-formula-corrections` I0, S3's K5 produces to it.
2. **Three ways to start a run** (Run stage button, plan card, typed `start_run`) over one `ResearchRuns.start`: which pins each passes (persona source, child, acknowledgement, confirmation). Owner: S1 in the orchestration ADR, S2 reviews.
3. **Execution state in the Lead's context** (status, steps, park code, spend, selection receipt, QC). `ResultsContext` covers results only. Owner: S1 type, S2 provider.
4. **Envelope cap <-> study `budget_usd` <-> `spend_confirm_usd` <-> client ceiling <-> OI-64**: one vocabulary and one precedence. Owner: S1 (ADR) with S3's ledger.
5. **QC (S2) <-> straight-liner worker (S1) <-> engine placeability (S2)**: one definition and one flag artifact. Owner: S2.
6. **Panel-default switch chain** (route classes S3 operator, personas flag S2, asset root, store, API/worker parity): one READY check that reads the worker's side. Owner: S3 (`mvp-master-plan` chunk 6).
7. **Audience preview (API, LIVE) <-> Run stage child <-> readiness**: one sampler call serving all three. Owner: S2.
8. **n bounds**: the domain's readiness limits as the single authority, read by the web and the Lead. Owner: S2 (domain), S1 (Lead), web follows.
9. **Fieldwork events (S2) -> Fieldwork artifact (S1)**: payload for quota cells, respondents, heartbeat. Owner: S2 writes the contract first.
10. **Production population (S3) <-> acceptance AC-05 (S3 harness)**: the same provisioning and a tier A double. Owner: S3.
