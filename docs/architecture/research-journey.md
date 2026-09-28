# The research journey — integration contract

**Status:** Phase A of the research integration job (Job 6), 2026-09-27.

- Written against `develop` @ `ceee2dc`. Every anchor holds at `dd27f68`, which adds only the
  design-system reference package (#72; CI run 211, *Deploy develop* run 35).
- **Checked at 17:40 UTC against the PO's first increment**, draft PR #74 @ `7b9e9dc` (CI green).
  §4.2, §4.3 and §5 say what it changes.
- **Phase B has not started.** At 18:05 UTC the component PRs were #74 @ `184699c` and #77 @
  `b28e1bf` (PO; #77 is stacked on #74), #75 @ `efa3971` (J1) and #76 @ `7c46e0c` (J3). J4 and J5
  had none. The live list is PROGRESS's open pull request table, where each PR adds its own row.
  §9 lists what Phase B needs.
- **One cutover, not separate merges** (2026-09-28, 00:40 UTC). The PO's draft #86 @ `619149a`
  assembles #74, #75, #77, #78, #82, #85 and this PR @ `e904b1c` into one release. Every `develop`
  merge deploys, so its parents are not merged one at a time. Where this document says *once #74
  merges*, read *once #74's head reaches `develop`, through #86 or alone*.

Tracker: [PROGRESS](../../.planning/PROGRESS.md). Chunks:
[research-agent-workflows.md](../../.planning/plans/research-agent-workflows.md) § Integration.

**Who does what** (user's scope addendum, 2026-09-27):

| Role | Owns |
|---|---|
| **PO**, the phase-out owner | the current-state inventory and phase-out plan; native research working content and its scoped APIs, attachments, questionnaire import, audience and library catalogues; migration and its validation report; `/app` authorization; removal of `/classic` hand-offs and navigation; product/reference deployment separation; the final legacy-offline browser and deployment acceptance; the phase-out ADR, OI-58 and OI-59. The former Job 2 is retired into this role |
| **J1** | truthful native AI settings and the presentation of Bedrock capabilities |
| **J3** | evidence-backed analysis: adapters, harness, executor modules |
| **J4** | report composition, execution, storage and retrieval, from admitted analysis |
| **J5** | grounded Deep Research: recorded sources, bounded tool contracts |
| **J6** (this document) | the research graph, executor, endpoint and results integration, and a reusable recorded end-to-end research scenario. J6 consumes the PO's workspace and does not duplicate it |

**What this fixes.** It covers the path a research study takes from design to an explicitly
reviewed report, and what each job hands the next. It redesigns nothing: each job keeps its own
plan, and ARCHITECTURE.md's rules apply unchanged.

**Direction (user, 2026-09-27).** AIA is an independent application. 18.6.6 is a frozen
behavioural reference and parity oracle: its logic, methodology and code may be recovered, but it
is **not a runtime fallback**. Native execution uses AIA's study scope, worker, gateway and
Bedrock runtime only, and legacy provider settings never control it (§6, rule 9).

**Production-state direction (user, 2026-09-28).** Studies are product work, not a class of
"fictional clients". INT-1 is a synthetic, recorded test fixture, not an authority to lower the
classification of any material in a production study. Classify each brief, pasted passage,
attachment, approved knowledge item and respondent source by its actual content and provenance.
Unknown or client-supplied material cannot inherit Class C from a client allowlist. A route must
refuse a request containing material outside its approval before anything is sent. The existing
allowlist is refused in production and is retained only for local/test fixture execution until
OI-63 and OI-79's engineering changes are made and verified.

**Two verdicts, always reported apart:**

- **Independence** of the currently supported workflows: the PO's final legacy-offline
  acceptance.
- **Completion** of the intended research process: the GAP rows of §2 closed, and lines 3–6 of
  §7 met.

Neither verdict implies the other, and a supported workflow is never re-labelled unsupported to
make independence pass.

## 1. Four levels of "done"

| Level | Means | Evidence |
|---|---|---|
| **Executable** | The behaviour exists in code and an automated test drives it; recorded adapters allowed | a test name at a SHA |
| **Recorded acceptance** | The INT-1 scenario (§3) passes in the legacy-offline environment: real Chromium, API, worker process, disposable PostgreSQL and artifact store, recorded Bedrock exchanges, captured web sources | the scenario's output at one combined candidate SHA; the recordings' hashes |
| **Production enablement** | The switch, configuration and approval exist for develop | the Compose key; the decision record (ADR or PROGRESS id) |
| **Live verification** | Observed on deployed develop with real calls under an authorised budget | run id, provider request ids, ledger cost, the running build's SHA |

A cell reads `MET (anchor)`, `UNMET`, `BLOCKED (decision)` or `—`. Merging a PR moves the first
column at most. A later level is never inferred from an earlier one, and nothing is "live"
without evidence of the fourth kind.
Recorded acceptance on synthetic inputs does not establish a production study's data route,
methodology approval, or client-facing evidence. Those require their own enablement and live
evidence, with a blocked result where approval is absent.

## 2. Stage map

Product stages: `domain/pipeline.py:101-115`. The reference's 24 nodes, with kind and interaction
mode: `legacy/npc-panel-18.6.6/app/workflow_engine.py:12-37`, executed in `app/worker_job.py`.
AIA's graph today is two templates (`domain/workflow_templates.py:51-69, 94-105`):

- `research` = `compile → preflight → run → {aggregate, sociomap}`;
- `research_agent`, one proposal step with no automatic retry.

**Where bare file names live.** In this document a file named without a path is one of these:

| Kind of file | Directory |
|---|---|
| AIA's executors (`research.py`, `ai_fieldwork.py`, `ai_runtime.py`, `registry.py`) | `apps/executors/src/aia_executors/` |
| The reference's (`worker_job.py`, `job_store.py`, `dotaznik.py`, `prototype_server.py`, `project_engine.py`, `client_report_v2.py`, `output_pack.py`) | `legacy/npc-panel-18.6.6/app/` |
| The research screens (`*Step.tsx`, `ExecutionSteps.tsx`, `ResearchScreen.tsx`, `StepPlaceholder.tsx`, `useAiStep.tsx`) | `apps/web/src/components/rehome/research/` |
| The classic-projects screens (`ProjectsScreen.tsx`, `TrashScreen.tsx`) | `apps/web/src/components/rehome/projects/` |
| The unit store (`store.ts`) | `apps/web/src/unit/research/` on `develop`; `apps/web/src/research/` in #74 |

**IMPLEMENTED**: AIA behaviour exists. **REPLACEMENT**: a deliberate AIA shape instead of the
reference's. **GAP**: nothing yet; the owner is named.

| Stage | Reference node | AIA at `ceee2dc` | Class | Owner |
|---|---|---|---|---|
| Brief | `compile` | `research_compile` turns a Design Revision into a `ResearchSpecification` (`research.py:180-215`). Brief analysis is the native `analyze_brief` job (#63). The working copy, the attachments (`POST /api/project/attachment`) and the stage bootstrap are still the unit's (OI-58) | compile IMPLEMENTED; store GAP | compile: J6. Store, attachments: PO |
| Deep Research | `research` (`background_research`) | Nothing executes it: [plan](../../.planning/plans/deep-research.md) chunk 0 only, ADR 0017 *Proposed*. *Dimenze* hands off to the classic Data Library (`apps/web/src/components/rehome/research/PersonaStep.tsx:293-302`); *Aktualizovat research* is refused before any call (`ResearchScreen.tsx:208`) | GAP | J5; its graph and registration: J6. Live use needs DR-2, plus D6 (route) for Class B |
| Research Design | `design` (snapshot) | The snapshot becomes an immutable Design Revision (ADR 0016). Critique, copilot and memory are proposals, accepted only by `submit_if_current` (`infrastructure/study_design_repository.py:146-160`) | REPLACEMENT | editor: PO; the revision contract stays |
| Questionnaire | `questionnaire` (snapshot) | Editor in the unit store; import through the unit (`/api/questionnaire/upload`); native build and optimise | REPLACEMENT; import GAP | PO |
| Audience | `audience` (snapshot) | The catalogue, check and uploads read the unit (`/api/audience`, `/api/audiences/*`, `/api/audience/dimensions`). The native proposal never sets filters. AC-05's sufficiency gate is not ported (`audience.definition` `NOT_STARTED`) | editor REPLACEMENT; sufficiency GAP | catalogue: PO. **Sufficiency gate: no owner** |
| Dimensions | `dimensions` (snapshot) | The library comes from the unit's bootstrap and `/api/library/*`; native suggestions stay proposals | REPLACEMENT; library GAP | PO |
| Sample Plan | `sample`; `preflight` | `research_preflight` and `GET …/research/readiness`; starting a design that is not ready is refused with 409. The reference parks only on a BLOCKER (`worker_job.py:441-450`) and never reads its `review_if_warning` flag (`job_store.py:18,56,63`) | REPLACEMENT (refuse before start) | J6 |
| Fieldwork | `run` (`respondent_run`) | `research_fieldwork` with the `ai_runtime` source (`ai_fieldwork.py`): fictional roster, gateway preflight, honest park. Every attempt starts again at the first persona and `checkpoint()` persists nothing, so a retry re-asks respondents who already answered (OI-64; `ai_fieldwork.py:167-173`, `apps/worker/src/aia_worker/context.py:125-138`) | IMPLEMENTED; retry cost GAP | J6 (existing executor) |
| Aggregation | `aggregate` | `research_aggregate`, EXACT except the bounds (OI-62). The reference aggregates inside `run` (`dotaznik.py:1405`), and its node only repackages | IMPLEMENTED | — |
| Validation | `donor_qc`, `verify`, `alignment` | Nothing. The validation-state rules exist (`domain/evidence/validation.py`) but no step runs them. The reference's `donor_qc` reads a key its summary lacks and appears always to pass (`worker_job.py:558-566`, `prototype_server.py:118-138`; read, not run) | GAP | QC and validation: J3. `verify` / `alignment`: §2.1 |
| Analysis | `analysis_*` ×8, `interpret` | The eight modules and their runner (`application/analysis.py:145, 225`) have no executor, no node, no production `AnalysisGenerator` and no adapter from the aggregate to an `EvidenceTable`. `research_sociomap` runs here and is `INTERNAL_ONLY` while D6 (Sociomap methodology) is open. The reference computes the Sociomap inside `run` (`project_engine.py:95-149`) | contracts IMPLEMENTED; execution GAP | J3. Node and registration: J6 |
| Report | `report` (`final_report`) | `DocxRenderer` and four templates (R0–R9, PR #62). No composition (R10), no step, storage or download (R11). Results links to the classic report (`ExecutionSteps.tsx:420-422`). The reference's report QA is automatic, and a failed gate still proceeds to delivery (`client_report_v2.py:30-37,135-141`, `worker_job.py:901`) | renderer IMPLEMENTED; rest GAP | J4. Node, Results integration: J6 |
| Delivery | `delivery` | The reference lists files (`worker_job.py:927-941`); its sign-off is only a sentence (`output_pack.py:27`). AIA already has: study status `DELIVERED` behind sign-off authority (`apps/api/src/aia_api/routers/scope.py:485-505`); artifact `approve` (independent, `SIGN_OFF_DELIVERABLE`), `freeze` and `download_url` (`EXPORT_DELIVERABLE`) (`infrastructure/artifact_repository.py:424-432, 506-570`); engine gates. None of it has a caller. No API decides a gate, and nothing ties a report to its review | GAP | J6, over J4's storage |

The Brief, Questionnaire, Audience and Dimensions rows describe `develop`; §4.3 says what #74
changes.

### 2.1 Verification and alignment: owner to be confirmed

In the reference:

- `verify` is web research over the aggregate result. It has explicit `NOT_RUN` and
  `NO_COMPARABLE_TARGET` states.
- `alignment` is a model comparison of research, results and verification into a calibration
  profile.
- `final_report` refuses to run without both (`worker_job.py:648-728`).

Nearest fit: `verify` → J5, since it uses the same owned search and fetch; `alignment` → J3. Until
an owner accepts them they stay a named GAP. The report composition then prints their absence as
an explicit state. That is neither a silent skip nor the reference's hard precondition.

### 2.2 AI helpers outside the graph

| 18.6.6 helper job | AIA | Class |
|---|---|---|
| `research_analysis`, `questionnaire_build`, `questionnaire_optimize`, `audience_propose`, `persona_suggest` | native `analyze_brief`, `build_questionnaire`, `optimize_questionnaire`, `propose_audience`, `suggest_dimensions` (#63) | REPLACEMENT |
| `copilot`, `project_assistant` | `design_copilot`, `answer_memory`; plus `critique_design`, which is new | REPLACEMENT |
| `deep_research` | none | GAP (J5) |
| `questionnaire_repair`, `final_review` | none; readiness is decided by code | GAP, no owner; off the scenario's critical path |
| `result_verify`, `/api/results/contextual_*` | none | GAP (§2.1) |
| `audience_strategy` (*next*), `/api/discovery/from_run` | classic only; unreachable in 18.6.6 as well (OI-47) | outside this journey |

No button of the web client reaches a unit AI job any more (`ResearchScreen.tsx:204-244`). Three
actions still go to the unit: the classic Data Library's Deep Research, *Diagnostika*
(`useAiStep.tsx:72-76,89`) and *Založit v Data Library* (`PersonaStep.tsx:98-115`). In #74 none
does (§4.3).

## 3. INT-1: the scenario every job tests against

### 3.1 The world

| | |
|---|---|
| Client A | `acceptance-client`, a synthetic **test fixture** on the local-only allowlist (`AIA_AI_FICTIONAL_CLIENT_IDS`) with no approved Client Knowledge. Its fixture inputs may exercise the Class C recorded route; this says nothing about a production client's inputs (OI-63, OI-79) |
| Client B | `control-client`, a separate test scope **not** on the allowlist, with one approved knowledge item. Its study proves the refusals of §8 and cross-client denial |
| People | a researcher (A: `RESEARCHER`, which exports), a reviewer (A: `REVIEWER`, which signs off), an outsider (B only), an organization admin |
| Study | `int-1`, `RESEARCH`, budget USD 5, self-approval **disallowed** |
| Brief | MVP-ACCEPT-1's brief, in Czech: *Jak dospělí ve věku 18–65 let hodnotí pět navrhovaných změn služeb městských knihoven a které skupiny by je využily?* (`docs/migration/mvp-acceptance.md` §1) |
| Objects | `service_a` … `service_e`, fictional service concepts |
| Questionnaire | one rating battery over the five objects (it feeds Aggregate and the Sociomap), one single-choice question, one open question |
| Fieldwork | n = 20 from the fictional roster; datasets `SYNTHETIC_AI_FICTIONAL`; no panel lineage (OI-61) |
| Attachment | one generated text fixture, stored and scoped by the PO's workspace. The scenario records each request carrying its text and its class, and separately proves that pasted or attached client/unknown material is refused on a Class C route (OI-79, §6 rule 5) |

The seed (`application/develop_seed.py`, `SEED_PROJECT_CONTENT`) and the 2026-09-26 live fieldwork
study use the same fixture brief and objects, so recorded and live transport evidence stay
comparable. That live call did not establish a production study's data classification or
client-facing methodology.

### 3.2 The recorded composition (J6)

The scenario uses the production composition (`aia_executors.registry`, the real
`BedrockConverseAdapter`, `GovernedModelGateway`, `StepModelCaller`, reservations and ledger) with
**only the transport replaced**:

- Converse-shaped responses keyed by request fingerprint;
- captured web pages keyed by URL.

`build_gateway` and `build_ai_fieldwork` already accept an injected transport (`ai_runtime.py:313-349`).
The composition refuses any `AIA_ENV` except `local`/`test`, and no deployment may name it, as
with `aia_executors.workbench` today (`tools/layer_check.sh:225-244`). A request with no recording
fails the scenario; it never falls through to the network. Every recording says whether it was
captured live (ARCHITECTURE.md §7).

### 3.3 The legacy-offline environment (PO)

The PO provides the environment the final acceptance runs in:

- no `legacy-panel` process;
- a tripwire where the unit would answer;
- no `AIA_LEGACY_*` variable in any process.

The scenario also checks independently: it fails on any browser request to a unit path. The unit
paths are `/classic`, `/interface-document`, `/api/*` outside `/api/v1`, `/files/*`, `/artifacts/*`,
`/project-attachments/*`, `/brand/*`, `/fullsim-arena`, `/health` and `/status`.

This cannot pass on `develop`. Every research stage, Run, Progress and Results included, renders
only after the unit's `GET /api/bootstrap` and `POST /api/projects/load` succeed
(`apps/web/src/components/rehome/research/ResearchScreen.tsx:70-96, 156-180`). That is OI-58.

#74 removes that dependency for the research stages (§4.3). Its PR body reports two browser
journeys passing on AIA alone, with the unit's paths answering 502 (`make ui-workbench-aia`). J6 has
not re-run them.

### 3.4 The scenario's interface (proposed; J6 builds it in Phase B)

**Invocation.** One command that takes:

- the product's base URL;
- a sign-in method for the four fictional people;
- an output directory.

**What it assumes.** The worker runs §3.2's composition.

**What it does**, over HTTP and a browser only, never touching a repository, as MVP-ACCEPT-1 §2
requires:

1. Provisions the §3.1 world.
2. Walks the design → fieldwork → evidence-backed analysis → report → review path of §7 lines 3–6.
3. Walks the negative paths: client B's refusals, the outsider's 404, cancel and reload, a budget
   park, an uncertain delivery.

**What it writes:**

- one JSON record per step, with ids, statuses and ledger totals;
- screenshots;
- the hash of the recording set;
- the requests the tripwire saw, which must be none.

**How it reports gaps.** A stage whose component has not landed reports UNMET by name; it is
never skipped silently. The PO runs this scenario inside §3.3 on one combined candidate.

## 4. Interfaces

Component jobs deliver **callable modules and their tests**; J6 registers them. A component PR that
needs any of these writes it under **"Handoff to integration"** in its PR body, and does not edit
the shared file (§5):

- a template node: node key, kind, dependencies, stage, artifact kind, `max_attempts`;
- an executor registration;
- a capability binding: capability, switch, output cap, reservation formula;
- a research route or a CI contract path.

| Job | Provides | Consumes | Lines (§7) |
|---|---|---|---|
| **PO** | Native, study-scoped working content: load, save with visible state, reload. Stage bootstrap, attachments, questionnaire import and the audience and library catalogues on AIA routes. Migration of bound unit content, with an explicit *no recoverable content* state (OI-58, OI-66). `/app` authorization. `/classic` removal. Deployment separation. The legacy-offline environment and the final acceptance, including this scenario. Publishes the workspace's API shapes, marked proposed or implemented | Design Revisions (§4.2); the scenario (§3.4) | 1, 7 |
| **J1** | The settings document and `/config` state what the worker actually runs: each AI switch, route, model and data-class approval. Disabled and unconfigured are shown as such, invalid values as invalid. Legacy provider fields are labelled persisted provenance, never AIA's default | the switch vocabulary of `aia_executors.ai_runtime` | 2 |
| **J3** | Executor bodies for QC, the eight analysis nodes and `interpret`. An adapter from the `research_aggregate` artifact to an `EvidenceTable`: it copies `data_origin` onto every row (OI-78) and assesses support through `assess_support` (`domain/evidence/support.py:94-118`). The adapter must not reuse the aggregate's `support_status` string. A production `AnalysisGenerator` over `StepModelCaller`. Each module stores its result, or ends BLOCKED naming the refusing gate. J3 also says how `FieldPolicyBook` and `JointStatus` are obtained for a fictional-roster dataset (`load_joint_status` is bound to the measured panel's hash, `domain/evidence/joint_status.py:190-193`). If they cannot be obtained, analysis BLOCKS with that reason | aggregate artifact, `admit_numeric_claims`, a capability binding (handoff) | 4 |
| **J4** | `compose_report(kind, study, results, provenance)` (R10), returning a validated `ReportDocument`. The report executor body: render with `DocxRenderer`, store through `ArtifactRepository` with the DOCX's SHA-256 as its fingerprint. Scoped retrieval, whose download needs `EXPORT_DELIVERABLE` | J3's stored analysis (§4.1), `EvidenceLedger`, templates | 5 |
| **J5** | `domain/deep_research/`, the owned tools and the executor bodies of the plan's graph. Pass 1 runs at brief time; pass 2 reuses unchanged tracks. The evidence bundle becomes a Research Design input and reaches analysis as `external_context` (`application/analysis.py:92-104`). A search route stays unavailable until DR-2 | Client Knowledge `for_study`, `ToolRegistry`, the usage ledger | 3, 5 |
| **J6** | Template nodes, registrations and capability bindings for J3–J5. The research routes and their CI contract paths. The Run, Progress, Results, Report and Review destinations and actions: native report retrieval in Results, and the review and delivery decisions over J4's stored report. The recorded composition and the scenario (§3). OI-64 | every row above | 3–6 |

### 4.1 Contracts J6 fixes now

- **Graph.**
  - A node joins the `research` template only together with its registered executor
    (`domain/workflow_templates.py:14-21`).
  - Reference node keys are kept: `donor_qc`, `analysis_executive` … `analysis_limitations`,
    `interpret`, `verify`, `alignment`, `report`, `delivery`.
  - **Open for Phase B:** J3's #76 specifies the eight analysis nodes as data
    (`domain/analysis/steps.py:1-15, 43 @ 7c46e0c`). Each depends on `aggregate` only, so a blocked
    module strands no other; the reference chains them one after another
    (`legacy/npc-panel-18.6.6/app/workflow_engine.py:24-31`). J6 decides the shape when it adds
    the nodes: parallel, as #76 proposes, unless one module reads another's output. `interpret`
    would then depend on all eight.
  - Deep Research is its own workflow type, pinned to a Design Revision (plan § Approach).
- **Capabilities.**
  - One switch per capability family, off by default. Each has its own output cap and a
    reservation that must cover the worst case, validated when the worker starts
    (`ai_runtime.py:145-256`).
  - `model_document()` binds only what is switched on (`:259-298`).
  - Bound today: `SIMULATION` (respondents), and `RESEARCH_REASONING` + `CRITIC` under
    `AIA_AI_RESEARCH_AGENTS_ENABLED`. `REPORT_WRITING`, `FAST_EXTRACTION` and `EMBEDDING` are unbound.
- **Stored analysis is re-admitted, never deserialised.** J3 confirms it in #76 @ `7c46e0c`: the
  `research_analysis_module` artifact keeps the draft the gate accepted and never a claim
  (`domain/analysis/artifact.py:197`), and `reconstruct_module` re-admits on every read
  (`application/analysis_results.py:594`). J4, which has no PR yet, reads outcomes only through
  that API.
  - An `AdmittedClaim` cannot be rebuilt from a stored payload: its issuer is module-private
    (`domain/evidence/admission.py:185-201`), and `AnalysisModuleResult` has no serialiser.
  - So an analysis artifact stores the checked draft and the evidence table it was admitted
    against. A later step (`interpret`, `report`) re-admits through `admit_numeric_claims`.
  - J3 and J4 also agree how findings map across. Analysis findings are `Finding(text, claim_ids)`
    (`domain/analysis/result.py:45-48`); the report needs `KeyFinding`s that cite evidence refs
    (`domain/report/model.py:142-151`). The mapping keeps checked prose unchanged.
- **Artifacts and reuse.**
  - Every stage output is an artifact of the Study's owned design project, read only through its
    run (`research_artifacts`, ADR 0016). New artifact kinds are named in the handoff.
  - Reuse is keyed on the full input: upstream artifact digests, the revision, and the code
    version (`research.py:408-423` does this for aggregate).
  - The reference reuses by a per-stage fingerprint across revisions (`worker_job.py:331-356`).
    AIA does not copy that.
- **Waiting is a state.**
  - A disabled capability, a refused route or licence, an exhausted budget and an uncertain
    delivery each park with a named reason, and never resume on a timer. That is how the engine
    already treats `ai_runtime_unavailable`, `AWAITING_*` and `RECOVERY_REQUIRED`
    (`domain/workflow.py:715-748`).
  - Only a provider's quota or capacity park resumes by itself.
  - The UI shows the reason.
- **Download is not delivery.**
  - Retrieving the DOCX needs `EXPORT_DELIVERABLE` (researcher, lead) and changes no state.
  - Review and delivery are separate recorded decisions, made by a person other than the producer
    (`SIGN_OFF_DELIVERABLE`: reviewer, lead), unless self-approval is allowed. They reuse
    `ArtifactRepository.approve` / `freeze` and `approval_decisions`, rather than inventing a
    second approval store.
- **The worker image renders reports.** The deployed image installs
  `aia_core[postgres,s3,bedrock]`, without the `report` extra (`deploy/docker/python.Dockerfile:41-46`).
  J6 adds the extra in the change that registers the report executor. #74 adds `documents` on the
  same line (§5).
- **Tests without the shared files.**
  - Executor tests build their own graph with `WorkflowRepository.create_run(steps=[…])`
    (`infrastructure/workflow_repository.py:383`; it validates the DAG, not the workflow type) and
    use their own registry.
  - API tests include their router into `create_app(settings)`.

### 4.2 What the research jobs consume from the workspace

Research execution reads the workspace **only through Design Revisions**. It never reads a draft:
a run, a proposal and every later stage name one immutable revision.

**Implemented on `develop`** (`ceee2dc`; unchanged at `dd27f68`). All paths are under
`/api/v1/studies/{study_id}`; the models are in `apps/api/src/aia_api/routers/research.py`.

| Route | Contract |
|---|---|
| `POST /design/revisions` | `{content, source_stage}` → `201` a new revision, `200` when identical to the newest, `422` when rejected. `EDIT_STUDY` on an open research study (`:74-97, 256-284`) |
| `GET /design/revisions`, `GET /design/revisions/{revision_id}` | newest first; `content` only on the single read |
| `GET /research/readiness?design_revision_id=` | `ready`, `checks[{id,status,message}]`, counts, `fieldwork_source` (`:168-190`) |
| `POST /research/runs`, `GET …`, `…/{run_id}`, `…/cancel`, `…/retry`, `…/events?since=`, `…/artifacts/{artifact_id}` | `RunStart{design_revision_id}`: idempotent per revision, `409 design_not_ready`. Cost only with `VIEW_COSTS`. The Sociomap only with `EDIT_STUDY` (`:106-160, 427-619`) |
| `POST /research/agent-jobs {design_revision_id, action, instruction}`; `GET`; `…/cancel`; `…/result`; `…/accept {expected_revision_id}` | proposals; accept writes a revision through `submit_if_current`, which locks the Study, so a stale baseline answers 409 (`:620-753`; `test_two_reviewed_design_proposals_cannot_overwrite_each_other`) |

**The PO's, in draft PR #74 @ `7b9e9dc`, not merged.** Same prefix; CI green. The line numbers are
in `apps/api/src/aia_api/routers/workspace.py`:

| Route | Contract |
|---|---|
| `GET /workspace/content` | `state` is a `ContentState`: `EMPTY`, `NATIVE`, `MIGRATED`, `RECOVERED`, `UNRECOVERABLE` or `AWAITING_MIGRATION`. It also returns `revision`, `revision_id`, `content`, `analysis`, `can_edit`, `lineage`, and `template`, which takes the place of the unit's bootstrap (`:257-276, 952-964`) |
| `PUT /workspace/content` | `{content, analysis, base_revision, reason}` → `{revision, revision_id, deduplicated}`. A stale base answers `409 stale_revision` with `current_revision`; content awaiting migration answers `409 awaiting_migration`. Needs `EDIT_STUDY` on an open study (`:279-300, 967-1009`; `test_only_editors_of_an_open_research_study_save`) |
| `GET /workspace/revisions` | the draft's history, newest first (`:1012-1028`) |
| `POST /workspace/attachments`, `GET …/{attachment_id}` | `{filename, data_b64}` → a record: `attachment_id`, `sha256`, `text_extracted`, `context_excerpt`. Needs `EDIT_STUDY` and a first save. A download goes only through the study, as `application/octet-stream` (`:1048-1131`) |
| `POST /workspace/questionnaire-import`, `GET …/questionnaire-template` | sections and a summary. Nothing is stored; the stage saves them (`:1134-1195`) |

**Two kinds of revision.**

- A *working revision* (`/workspace/revisions`) is the draft's history. It is never a run's input.
- A *Design Revision* (`/design/revisions`) is immutable. It is the only thing a run, a proposal or a
  later stage names.
- The Run stage turns the first into the second. In #74 it submits the copy the store holds
  (`ExecutionSteps.tsx:89-97 @ 7b9e9dc`). So the plan's I5, the Run stage on the native draft, is
  delivered once #74 merges.
- How an attachment's text is classified when it reaches a model is OI-79 (§6 rule 5).

**Finding at `7b9e9dc`: the Run stage does not save before it submits.**

- *Claim.* The AI steps save first (`useAiStep.tsx:31-33`), and a save refuses a copy that lost a
  conflict (`src/research/store.ts:159`). RunStep does not save (`ExecutionSteps.tsx:76-97`), although
  the store's own header says "flush before a run" (`store.ts:4`). So a copy whose save was refused
  with `409 stale_revision` still becomes a Design Revision that a run can execute.
- *Reproduction.* One Vitest in the style of `ResearchScreen.test.tsx`: open the study's session at
  Brief, edit the goal while the save answers 409, wait for the conflict notice, then open Run.
  `POST /design/revisions` carries the refused edit. The test passes at `7b9e9dc` and fails once
  RunStep saves first; #74's eight `ExecutionSteps` tests still pass with that change.
- *Consequence.* A person told *Obsah studie mezitím uložil někdo jiný…* can still start a run of
  content nobody saved, beside a newer working revision.
- *Smallest fix.* Two lines in RunStep: flush the store before `submitDesign`, as the AI steps do.
  The conflict then shows as the stage's error.
- *Test.* The reproduction, kept in `ExecutionSteps.test.tsx`.
- *Owner.* J6, which owns the Run stage (§5). The fix is cheapest in #74, which already edits the
  file. If #74 merges without it, it becomes an OI.
- **Fixed in #74 @ `184699c`** (`ExecutionSteps.tsx:96-107`), with two tests: *saves a change not
  yet saved before the design becomes a revision* and *never submits a copy whose save AIA refused
  because someone saved a newer one*. Re-run there, the reproduction fails, and #74's ten
  `ExecutionSteps` tests pass.
- **Pinned further at `936702f`** (#74 @ `d5dfb62`, CI green). Two more ways in have tests, and in
  each no revision and no run is created:
  - *submits nothing while an earlier save's conflict stands, and prepares the version AIA holds
    once it is reloaded*;
  - *submits nothing when the save before it fails, and says why* (a 500).
  - Its commit reports both failing on `7b9e9dc`.

### 4.3 What #74 changes, if it merges

- **The research stages run on AIA alone.**
  - They load and save through `/workspace/content`, with no unit bootstrap
    (`ResearchScreen.tsx:48-70 @ 7b9e9dc`).
  - The screen ledger lists no unit route for them.
  - §3.3's blocker is gone for these stages. The classic-projects screens call the unit until
    increment 4.
- **Now native:** the brief's attachments, the questionnaire import and its template. In Dimenze,
  dimensions come from the client's approved knowledge, and a request becomes a knowledge proposal.
- **Marked *V AIA zatím není*:**
  - the audience catalogue, check and preview, special subpanels, own audiences and panel factors
    (`AudienceStep.tsx:59-66`, `PersonaStep.tsx:273-274`). By #74's stated trade-off they return when
    a population version is imported through `PopulationRuntime`;
  - the classic client report (`ExecutionSteps.tsx:417-419`), which returns with J4 and J6 (§7
    line 5).

  The independence verdict names each of these as unavailable without 18.6.6. They are not dropped
  from the supported set (the two verdicts, above). INT-1 needs none of them, because its
  respondents are the fictional roster.
- **Bound studies are read-only until migrated.** A study bound to the unit reads
  `AWAITING_MIGRATION` until increment 2 migrates it. INT-1 creates its study, so the study goes
  from `EMPTY` to `NATIVE` and never meets that state. The migration's acceptance is the PO's.

## 5. Shared files

Ownership is agreed before concurrent change. Changes are applied one after another onto a
reconciled candidate. Migration heads are resolved explicitly: one head, and the later PR
re-points its `down_revision`. The chain has one head on `develop`: `1777fcb96352`; PR #63 added none.
#74 adds `5b1d0f3e9a21` on top of it
(`migrations/versions/20260927_5b1d0f3e9a21_study_working_content_in_aia.py:34-35 @ 7b9e9dc`). A later
migration from J3, J4 or J6 re-points to whichever head `develop` has when it lands.

| File or area | Owner | Rule for others |
|---|---|---|
| `domain/workflow_templates.py`; `apps/executors/src/aia_executors/registry.py`; `aia_executors/ai_runtime.py` bindings; the design jobs' context and request (`context_snapshot`, `agent_request` in `domain/research_agents.py`) | J6 | handoff |
| The worker's `AIA_AI_*` keys in `deploy/develop/docker-compose.yml` and `env.example` | J6 | J1 displays them; the PO owns the rest of the file |
| `apps/api/src/aia_api/main.py` | J6 for research routers; PO for workspace and gate routers | one registration change at a time |
| The `api-contract` paths in `.github/workflows/ci.yml`; `apps/web/src/lib/api.ts` | J6 for research paths and types; PO for workspace paths and types | no edits to the other owner's lines |
| `migrations/versions/` | PO for workspace tables; each author otherwise | one head |
| `ExecutionSteps.tsx`; `lib/research-execution.ts`; the report and review screens | J6 for native destinations and actions | #74 replaced the classic report link (`ExecutionSteps.tsx:420-422`) with a *not in AIA yet* sentence (`:417-419 @ 7b9e9dc`) rather than wait for J6; J6's native report retrieval replaces that sentence |
| `GlobalPages.tsx`; `settings/ControlPanel.tsx`; `apps/web/src/i18n/cs.ts` | J1 for the AI settings panels; PO for legacy navigation and cards; J6 for research-stage copy | each owner edits only its own keys |
| Stage editors; `StudyFrame` and its bootstrap; `apps/web/src/unit/*` and its replacement | PO | — |
| `routers/panel.py`; `deploy/develop/Caddyfile`; `bin/*.sh`; `tools/caddy_routes.py`; `tools/develop_routing_*` | PO | — |
| `deploy/docker/python.Dockerfile` | PO; J6 adds only the `report` extra | agreed first. #74 sets the install line both targets share to `aia_core[postgres,s3,bedrock,documents]` (`:43 @ 7b9e9dc`); J6 adds `report` to that line after #74 |
| This document; the scenario; the research plan's Integration section | J6 | components add rows by handoff |
| OI-58, OI-59, the phase-out ADR, the screen and route ledgers | PO | findings handed over (§11) |

**Checked against #74 @ `7b9e9dc`.**

- Both PRs change `.github/workflows/ci.yml`, `.planning/PROGRESS.md`, `.planning/open-items.md`,
  `ARCHITECTURE.md` and `CLAUDE.md`, each on its own lines.
- A trial merge of `7b9e9dc` into this PR's head is clean, and no OI number is reused.
- The one semantic overlap was the ADR counts, which ADR 0018 would have made wrong. This PR drops
  the numbers.
- **Re-checked at `d5dfb62`** (2026-09-28, 00:45 UTC). A trial merge into this PR's head (`5cc436d`)
  is clean. It leaves one migration head, `5b1d0f3e9a21`, and no OI number twice.

**Checked at 18:05 UTC against #75, #76 and #77.**

- Each trial merge into this PR's head conflicts only where both sides add a row or an entry:
  - #75: `.planning/PROGRESS.md` and `.planning/open-items.md`;
  - #76: `.planning/PROGRESS.md`, `ARCHITECTURE.md` and `docs/architecture/README.md`;
  - #77: `.planning/PROGRESS.md`.
- **One collision of meaning: OI numbers.** #75 numbers its new entries OI-72 to OI-76, and this
  PR numbered its own OI-72 and OI-73. Both started from OI-71 on `develop`.
- **The rule for the register:** an OI number is taken when its PR merges. The PR that merges
  later renumbers its new entries above `develop`'s highest, together with every reference to
  them in that PR.
- **Applied at 22:47 UTC.** #83 merged first (`48bf3e2`) and put OI-76 on `develop`, for the
  flake #75 had filed under that number. This PR's entries became OI-78 and OI-79, above it and
  clear of #84's OI-77, which merged at 23:09 UTC (`8c13a11`). #75 renumbers OI-72 to OI-75 when
  it merges; its OI-76 is `develop`'s
  already.
- #77 adds no migration, so the one head after #74 stays `5b1d0f3e9a21`.

## 6. Rules every PR keeps

1. Scope comes from a server-issued `StudyContext` or `ClientContext`. Nothing sent by the browser
   authorizes anything, and another client's study answers 404.
2. A run executes one immutable Design Revision. A proposal changes a design only when a person
   accepts it against an unchanged baseline (`submit_if_current`).
3. Artifacts carry provenance: revision, harness and prompt fingerprints, model and route,
   request id, cost, population binding and `data_origin`.
4. Every paid call is reserved before dispatch, settled once and ledgered. An uncertain delivery
   goes to `RECOVERY_REQUIRED` and is never retried automatically.
5. **Required product rule:** every material part of a request, including extracted attachment
   text and text pasted into a brief, has a provenance and a class. The whole request takes the
   most restrictive class; missing provenance or classification refuses egress. A test fixture's
   local allowlist cannot lower client or unknown material to Class C (OI-63, OI-79). **Current
   code differs:** `domain/research_agents.py:273, 294-296` chooses from the fictional-client
   allowlist and approved knowledge, while `context_snapshot` includes attachment text without
   classifying it separately. The Class C route is approved only for its stated class and the
   Class A route remains unapproved. Job 6 must close this gap before enabling design jobs for
   studies carrying uploads or pasted material. Panel-derived data is separately refused by the
   licence gate (OI-61).
6. A number reaches a result or a report only as an `AdmittedClaim`. `NON_EVIDENCE_ORIGINS` never
   become client-facing claims, and every evidence row carries the origin of its data (OI-78). The
   Sociomap stays `INTERNAL_ONLY` while D6 (Sociomap methodology) is open.
7. Models propose. Code decides numerical admissibility and method status. People approve
   consequential changes.
8. Recorded adapters and test registries exist only in test and local compositions, never as a
   production success path. At present nothing stops a deployment from naming
   `aia_worker.testing:build_registry`: `tools/layer_check.sh:225-244` has a rule for the
   workbench only. J6 adds the matching rule (§9).
9. No runtime fallback to 18.6.6: no product route, executor or page reaches the unit to finish
   work AIA cannot do. Legacy provider fields (`claude_code_subscription`, `CLAUDE_CODE_ONLY`, a
   unit project's `run_policy`) are persisted provenance. No native path reads them, and
   `domain/research_agents.py:227` strips them from model context.

## 7. Acceptance, line by line

This is the state at `ceee2dc`, unchanged at `dd27f68`; line 1 notes what #74 would change. The
Executable column names what exists; the later columns name what is missing. Lines 1 and 7 decide **independence**. Lines 3–6 decide **completion**.

| # | Must show | Owner | Executable | Recorded | Enablement | Live |
|---|---|---|---|---|---|---|
| 1 | Sign in → client and study → native draft edit, save, reload → scoped attachment | PO | sign-in, client and study creation (`test_client_api.py`); on `develop` the draft is still the unit's (OI-58). In #74, not merged, the draft and its attachments are native (`test_study_workspaces.py`, `test_client_api.py` @ `7b9e9dc`) | UNMET | `/app` needs `AIA_LEGACY_PANEL_ENABLED` and an owner or admin role (`apps/api/src/aia_api/routers/panel.py:53-62`, `application/scope.py:170-197`), and is refused in production (`apps/api/src/aia_api/config.py:213-215`, OI-59) | UNMET |
| 2 | Accurate runtime settings; the disabled and unconfigured behaviour | J1 | `app/config/route.test.ts`; a park on a disabled runtime (`test_ai_fieldwork.py`, `test_research_agent_executor.py`) | UNMET | the settings document calls the legacy subscription provider AIA's default (§10) | UNMET |
| 3 | Recorded Deep Research → reviewed design proposal → immutable revision → stale proposal refused | J5, J6 | proposals, acceptance and the stale refusal (`test_research_agent_executor.py`, `test_two_reviewed_design_proposals_cannot_overwrite_each_other`); Deep Research: none | UNMET | design switch off by default (`docker-compose.yml:176`); no search route (DR-2) | UNMET. The $2 fieldwork budget is spent |
| 4 | Readiness → fieldwork → aggregation and QC → validation → admitted analysis | J3, J6 | readiness to Sociomap (`test_research_executors.py`, `test_ai_fieldwork.py`); QC, validation, analysis execution: none | UNMET | fixture fieldwork: local Class C route approved (ADR 0010); production material route unapproved. Analysis: unbound | fixture fieldwork transport MET at `0310091` (2026-09-26: 20 calls, $0.2303301; the fieldwork executor, gateway and adapter are unchanged since); production study and the rest UNMET |
| 5 | Fixed-object research reuse → verification and alignment → stored report → authorized download → explicit review and delivery state | J4, J5, J6 | renderer and templates (`test_report_docx_*.py`). Nothing composes, stores or delivers a report | UNMET | none | UNMET |
| 6 | Cross-client denial; cancel and reload; failure states; retry and recovery; budgets and settled usage | J6 (and every job for its own stage) | 404 isolation, cancel, park, `RECOVERY_REQUIRED`, reservations (`test_research_api.py`, `test_workflow_concurrency.py`, `test_worker_processes.py`, `test_ai_usage_ledger.py`). A retry repeats paid respondents (OI-64) | UNMET | — | fieldwork settlement MET at `0310091` (all 20 reservations settled); the rest UNMET |
| 7 | AIA starts, deploys and passes readiness and smoke with no reference service and no legacy health requirement | PO | start and readiness need no unit: no `depends_on` on it, and `/api/v1/ready` checks only the database; CI's `startup-smoke` boots the API and worker without it | UNMET | the deploy pulls and starts `legacy-panel` (`deploy/develop/bin/deploy.sh:40,97`); smoke fails without a healthy unit (`bin/smoke.sh:98-105`) | UNMET |

The scenario is accepted only when every line is MET in the Recorded column at one combined
candidate SHA. A line that a decision blocks stays UNMET and names the decision. It is never
forced green with a forged certification. A workspace-only browser test is not full-product
independence.

## 8. Blocked real-client paths: shown, never forced

| Path | Blocked by | How the scenario shows it |
|---|---|---|
| Client or unknown material, including pasted or attached text, sent to a model | OI-79's per-material classification; D6 for any resulting Class A/B route | client B's design jobs park with zero calls; a locally allowlisted test client carrying client/unknown text must also park before OI-79 closes |
| Panel-derived respondents | OI-61 (licence); the withheld archive (population import) | only the fictional roster runs; there is no `v17_4_0` binding |
| Web search | DR-2 (a search route); D8 (a key, for a keyed service) | Deep Research parks at its first external call |
| A client-facing Sociomap | D6 (methodology) | the report omits it and says so |
| A report delivered to a client | AC-11's legal gate (`governance.legal` `NOT_STARTED`); synthetic and modeled origins are not observed evidence | the fixture review records *internal, synthetic*; no client delivery exists |
| Production study routed by a "fictional client" declaration | OI-63 and OI-79; no such production authority exists | `AIA_AI_FICTIONAL_CLIENT_IDS` is local/test-only and refused in production |

## 9. Phase B: what it needs

**From each job:** a PR against `develop` (draft or merged), its head SHA, its "Handoff to
integration" section, and its own checks green. **From the PO, additionally:** the workspace API,
published in #74 (§4.2), and, for the final run, the legacy-offline environment (§3.3). Phase B
integrates the latest heads. An unmerged stack is tested on an isolated integration branch, with
every component head recorded.

**J6's own work, in order:**

1. Register nodes, executors and bindings as J3, J4 and J5 land, adding the `report` extra with the
   report executor.
2. Build the recorded composition and the scenario (§3.2, §3.4). Add two layer rules, both of
   which pass today:
   - one that keeps `aia_worker.testing` out of deployments;
   - one that keeps the legacy provider fields (`run_policy`, `preferred_provider`,
     `provider_policy`) out of `apps/executors` and `apps/worker`. That turns §6 rule 9 from a
     code reading into a check.
3. Build the Results, Report and Review destinations: native report retrieval, and the review and
   delivery decisions over `ArtifactRepository.approve` / `freeze`. They take the place of the
   classic report link, or of #74's *not in AIA yet* sentence once #74 has merged (§5).
4. Fix OI-64 inside the fieldwork executor, or do not claim retry-safe acceptance.
5. The Run stage on the native draft, including the save before it submits, is delivered by #74
   @ `184699c` (§4.2). The scenario checks both.
6. Write the activation and live-acceptance runbook for the combined candidate. It names the
   revision, the switches, the approved data class and route, the scenario, a bounded proposed
   spend, rollback, and the evidence to collect. It is not executed without a new, explicit
   budget: the 2026-09-26 $2 authorisation is spent.

## 10. Stale claims found on 2026-09-27 and 28

"Corrected" means changed in this PR; "handed over" means the owner is named.

| Claim | Where | Evidence now | Action |
|---|---|---|---|
| Native design jobs are "implemented on this branch" and "not deployed" | `ai-runtime.md`, `research-agents.md` | merged in PR #63 (`85fa951`); in every develop build since deploy run 31; off by default (`docker-compose.yml:176`); no live design call is recorded | corrected |
| Only `SIMULATION` is bound | ADR 0010 | `RESEARCH_REASONING` and `CRITIC` are also bound when the design switch is on (`ai_runtime.py:274-276`); the route's approval is unchanged | corrected (dated note) |
| "No complete DOCX renderer exists yet"; reporting "not started" | `research-agent-workflows.md` handoff; PR #63 body; `domain-map.md` | PR #62 (`46b7337`) merged R4–R9; R10 and R11 remain | corrected |
| PRs #69, #70 and #71 are open; `2beafd9` is deployed | PROGRESS | all merged on 2026-09-27; `develop` @ `ceee2dc` deployed by run 34 | corrected |
| Credentials come from Secrets Manager | `mvp-acceptance.md` AC-02; `parity-matrix.json` AC-02 and `ai.credentials`; PROGRESS D7 and D8 | Bedrock signs with the instance or container role (`infrastructure/model_adapters/aws_signing.py`, ADR 0010). A secret store is still needed for a keyed service such as a search API | corrected |
| `preflight` pauses for a person on a warning; no executor exists for a real step; progress is sent as server-sent events | `workflows.md` | the reference pauses only on a BLOCKER. Research, proposal and snapshot executors exist. Events are a cursor-paged JSON list (`routers/research.py:480-507`), and the Progress stage polls the run | corrected |
| The unit stays "as the oracle and a fallback" | ADR 0015 decision 5; OI-58 | the oracle and a frozen reference only; no runtime fallback (the user's direction) | handed to the PO. ADR 0018 in #74 says *reference only*; OI-58's removal condition still ends *as the oracle and a fallback* at `7b9e9dc` |
| AIA's AI default is `claude_code_subscription` / `CLAUDE_CODE_ONLY` | `GET /api/v1/settings` (`routers/settings.py:200-217`) | these are persisted legacy fields; the worker binds Bedrock capabilities only | handed to J1; #75 @ `efa3971` corrects it (its own OI entry) |
| Run, Progress and Results use no unit route; the rebuilt stages call unit AI routes | `docs/migration/interface-screens.json` | all eight stages need `/api/bootstrap` and `/api/projects/load`; the AI actions are native agent jobs | handed to the PO. #74 empties the research stages' `unit_routes`, which is true on that branch |
| Approved knowledge *or an attachment's content* makes a request Class A, so attachment text reaches no Class C call | this document, §3.1 and §6 rule 5, as first published | only knowledge does. `context_snapshot` copies the whole design, attachment text included, and the class comes from the allowlist and knowledge (`domain/research_agents.py:225, 294-296`) | corrected; the product rule is now recorded in OI-79, the code gap remains |
| Implementation states of `ai.gateway`, `ai.usage_ledger`, `ai.credentials`, `reports.generation` (`NOT_STARTED`) and `workflow.step_execution`'s note ("No research step body exists") | `parity-matrix.json` | all have merged code. Re-grading them touches the module inventory (OI-30) | handed to the parity owner |
| The smoke's AI check and the runbook's § AI: no Bedrock adapter or governed route is wired, ADR 0010 is *Proposed*, and no live model call has been made (found 2026-09-28) | `apps/executors/src/aia_executors/smoke.py:16-18, 243-246`, `deploy/develop/bin/smoke.sh:13-14` and `deploy/develop/README.md:288-294` @ `f1c486f`; the smoke prints it on every deploy (run 38) | the adapter is `infrastructure/model_adapters/bedrock.py` (PR #56 @ `0310091`); ADR 0010 is accepted for fictional Class C on develop only (`adr/0010-bedrock-eu-inference-route.md:3`); the fictional acceptance run made 20 model calls for $0.2303301 (`docs/migration/status.md:11-13`). `NOT_RUNNABLE` itself stays right: the smoke makes no model call | handed to the PO, who owns the develop deployment: the reason string and the paragraph. #75, #85 and #86 leave both unchanged at `bd24d20`, `daa3d0b` and `619149a` |

## 11. Handoff to the phase-out owner

These are findings from this inventory, anchored at `ceee2dc`, that sit in the PO's area.

- **Deployment coupling.**
  - The deploy pulls and starts `legacy-panel` (`deploy/develop/bin/deploy.sh:40,97`), and smoke
    fails without a healthy unit (`deploy/develop/bin/smoke.sh:98-105`).
  - The three image lists must change together: `deploy/develop/docker-compose.yml:201`,
    `.github/workflows/deploy-develop.yml:128-142`, `infra/develop/main.tf:17`;
    `packages/aia_core/tests/test_deploy_images.py` pins them.
  - CI's `oracle-parity` job requires the unit whenever `AIA_LEGACY_REFERENCE_URL` is set
    (`.github/workflows/ci.yml` `oracle-parity`). Clear it before the unit leaves.
  - `tools/caddy_routes.py` requires `/app` behind the panel gate (`:143-148`) and the product
    hostname routing to the unit (`:160-164`). `packages/aia_core/tests/test_ui_workbench.py:38-41`
    fails to collect if the Caddyfile has no unit matcher.
  - Stale comments still call `/` the 18.6.6 document: `deploy/develop/docker-compose.yml:102-106`,
    `deploy/develop/Caddyfile:43-45`, `apps/web/src/app/interface-document/route.ts:9-12`,
    `apps/web/src/lib/panel.ts:4-5`.
- **`canEdit` does not stop autosave.** From the code, a signed-in reader's edits still autosave
  to the unit: `canEdit` gates only the AI buttons, revisions and runs (`ResearchScreen.tsx:280`,
  `ExecutionSteps.tsx:98`), and `store.ts` has no read-only mode. This is a hypothesis to
  reproduce; the native draft should enforce `EDIT_STUDY` on save by construction. **#74 answers it
  for AIA's store:** the server refuses a save without `EDIT_STUDY` on an open study
  (`study_workspace_repository.py:228-229 @ 7b9e9dc`; `test_only_editors_of_an_open_research_study_save`).
  On `develop` it stays a hypothesis about the unit store.
- **Legacy-dependent actions a supported workflow still uses:**
  - attachments (`BriefStep.tsx:160-183`);
  - questionnaire import and templates (`QuestionnaireStep.tsx:79-80, 249-254`);
  - audience check, catalogue and uploads (`AudienceStep.tsx:86-95, 337-345, 429`);
  - the library and dimension requests (`PersonaStep.tsx:98-115, 333`);
  - the classic report (`ExecutionSteps.tsx:420-422`);
  - *Diagnostika* (`useAiStep.tsx:72-76`);
  - the classic-projects pages (`ProjectsScreen.tsx:63`, `TrashScreen.tsx:26`).

  #74 moves each research-stage item onto AIA or marks it *V AIA zatím není* (§4.3). The
  classic-projects pages still call the unit until increment 4.
- **A flake in the research screens, fixed.** #75 recorded it: under a loaded full web run, the
  native-job tests in Brief and Audience outran their 15 s wait. #83 found the cause, a failed
  `/config` read left in the cache by an earlier test, and fixed it (`48bf3e2`; OI-76 on
  `develop`).
- **The product README's index links three documents that were never written:**
  `docs/product/README.md:171-173`.
