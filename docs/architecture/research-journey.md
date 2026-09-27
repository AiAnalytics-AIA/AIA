# The research journey — integration contract

**Status:** Phase A of the research integration job (Job 6), 2026-09-27, against `develop` @
`ceee2dc` (CI run 209 green; *Deploy develop* run 34 green). **Phase B has not started**: at that
SHA there is no open pull request and no branch from the other jobs (§9 lists what Phase B needs).
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

## 2. Stage map

Product stages: `domain/pipeline.py:101-115`. The reference's 24 nodes, with kind and interaction
mode: `legacy/npc-panel-18.6.6/app/workflow_engine.py:12-37`, executed in `app/worker_job.py`.
AIA's graph today is two templates (`domain/workflow_templates.py:51-69, 94-105`):

- `research` = `compile → preflight → run → {aggregate, sociomap}`;
- `research_agent`, one proposal step with no automatic retry.

Unless stated, stage code named below is under `apps/executors/src/aia_executors/`.

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
(`useAiStep.tsx:72-76,89`) and *Založit v Data Library* (`PersonaStep.tsx:98-115`).

## 3. INT-1: the scenario every job tests against

### 3.1 The world

| | |
|---|---|
| Client A | `acceptance-client`, *Akceptační klient (fiktivní)*. On the local fictional allowlist (`AIA_AI_FICTIONAL_CLIENT_IDS`) and with **no approved Client Knowledge**, so its design material is Class C (OI-63) |
| Client B | `control-client`, *Kontrolní klient (fiktivní)*. **Not** allowlisted, with one approved knowledge item. Its study proves the refusals of §8 and cross-client denial |
| People | a researcher (A: `RESEARCHER`, which exports), a reviewer (A: `REVIEWER`, which signs off), an outsider (B only), an organization admin |
| Study | `int-1`, `RESEARCH`, budget USD 5, self-approval **disallowed** |
| Brief | MVP-ACCEPT-1's brief, in Czech: *Jak dospělí ve věku 18–65 let hodnotí pět navrhovaných změn služeb městských knihoven a které skupiny by je využily?* (`docs/migration/mvp-acceptance.md` §1) |
| Objects | `service_a` … `service_e`, fictional service concepts |
| Questionnaire | one rating battery over the five objects (it feeds Aggregate and the Sociomap), one single-choice question, one open question |
| Fieldwork | n = 20 from the fictional roster; datasets `SYNTHETIC_AI_FICTIONAL`; no panel lineage (OI-61) |
| Attachment | one fictional text file, stored and scoped by the PO's workspace. Its content reaches no Class C call (§6 rule 5) |

The seed (`application/develop_seed.py`, `SEED_PROJECT_CONTENT`) and the 2026-09-26 live fieldwork
study use the same brief and objects, so recorded and live evidence stay comparable.

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

This cannot pass today. Every research stage, Run, Progress and Results included, renders only
after the unit's `GET /api/bootstrap` and `POST /api/projects/load` succeed
(`apps/web/src/components/rehome/research/ResearchScreen.tsx:70-96, 156-180`). That is OI-58.

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
| **J3** | Executor bodies for QC, the eight analysis nodes and `interpret`. An adapter from the `research_aggregate` artifact to an `EvidenceTable`: it copies `data_origin` onto every row (OI-72) and assesses support through `assess_support` (`domain/evidence/support.py:94-118`). The adapter must not reuse the aggregate's `support_status` string. A production `AnalysisGenerator` over `StepModelCaller`. Each module stores its result, or ends BLOCKED naming the refusing gate. J3 also says how `FieldPolicyBook` and `JointStatus` are obtained for a fictional-roster dataset (`load_joint_status` is bound to the measured panel's hash, `domain/evidence/joint_status.py:190-193`). If they cannot be obtained, analysis BLOCKS with that reason | aggregate artifact, `admit_numeric_claims`, a capability binding (handoff) | 4 |
| **J4** | `compose_report(kind, study, results, provenance)` (R10), returning a validated `ReportDocument`. The report executor body: render with `DocxRenderer`, store through `ArtifactRepository` with the DOCX's SHA-256 as its fingerprint. Scoped retrieval, whose download needs `EXPORT_DELIVERABLE` | J3's stored analysis (§4.1), `EvidenceLedger`, templates | 5 |
| **J5** | `domain/deep_research/`, the owned tools and the executor bodies of the plan's graph. Pass 1 runs at brief time; pass 2 reuses unchanged tracks. The evidence bundle becomes a Research Design input and reaches analysis as `external_context` (`application/analysis.py:92-104`). A search route stays unavailable until DR-2 | Client Knowledge `for_study`, `ToolRegistry`, the usage ledger | 3, 5 |
| **J6** | Template nodes, registrations and capability bindings for J3–J5. The research routes and their CI contract paths. The Run, Progress, Results, Report and Review destinations and actions: native report retrieval in Results, and the review and delivery decisions over J4's stored report. The recorded composition and the scenario (§3). OI-64 | every row above | 3–6 |

### 4.1 Contracts J6 fixes now

- **Graph.**
  - A node joins the `research` template only together with its registered executor
    (`domain/workflow_templates.py:14-21`).
  - Reference node keys are kept: `donor_qc`, `analysis_executive` … `analysis_limitations`,
    `interpret`, `verify`, `alignment`, `report`, `delivery`.
  - Deep Research is its own workflow type, pinned to a Design Revision (plan § Approach).
- **Capabilities.**
  - One switch per capability family, off by default. Each has its own output cap and a
    reservation that must cover the worst case, validated when the worker starts
    (`ai_runtime.py:145-256`).
  - `model_document()` binds only what is switched on (`:259-298`).
  - Bound today: `SIMULATION` (respondents), and `RESEARCH_REASONING` + `CRITIC` under
    `AIA_AI_RESEARCH_AGENTS_ENABLED`. `REPORT_WRITING`, `FAST_EXTRACTION` and `EMBEDDING` are unbound.
- **Stored analysis is re-admitted, never deserialised** *(proposed; J3 and J4 confirm the stored
  form before either lands).*
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
    delivery each park with a named reason, and never resume on a timer
    (`domain/workflow.py:733-734`).
  - The UI shows the reason.
- **Download is not delivery.**
  - Retrieving the DOCX needs `EXPORT_DELIVERABLE` (researcher, lead) and changes no state.
  - Review and delivery are separate recorded decisions, made by a person other than the producer
    (`SIGN_OFF_DELIVERABLE`: reviewer, lead), unless self-approval is allowed. They reuse
    `ArtifactRepository.approve` / `freeze` and `approval_decisions`, rather than inventing a
    second approval store.
- **The worker image renders reports.** The deployed image installs
  `aia_core[postgres,s3,bedrock]`, without the `report` extra (`deploy/docker/python.Dockerfile:41-46`).
  J6 adds the extra in the change that registers the report executor.
- **Tests without the shared files.**
  - Executor tests build their own graph with `WorkflowRepository.create_run(steps=[…])`
    (`infrastructure/workflow_repository.py:383`; it validates the DAG, not the workflow type) and
    use their own registry.
  - API tests include their router into `create_app(settings)`.

### 4.2 What the research jobs consume from the workspace

Research execution reads the workspace **only through Design Revisions**. It never reads a draft:
a run, a proposal and every later stage name one immutable revision.

**Implemented at `ceee2dc`.** All paths are under `/api/v1/studies/{study_id}`; the models are in
`apps/api/src/aia_api/routers/research.py`.

| Route | Contract |
|---|---|
| `POST /design/revisions` | `{content, source_stage}` → `201` a new revision, `200` when identical to the newest, `422` when rejected. `EDIT_STUDY` on an open research study (`:74-97, 256-284`) |
| `GET /design/revisions`, `GET /design/revisions/{revision_id}` | newest first; `content` only on the single read |
| `GET /research/readiness?design_revision_id=` | `ready`, `checks[{id,status,message}]`, counts, `fieldwork_source` (`:168-190`) |
| `POST /research/runs`, `GET …`, `…/{run_id}`, `…/cancel`, `…/retry`, `…/events?since=`, `…/artifacts/{artifact_id}` | `RunStart{design_revision_id}`: idempotent per revision, `409 design_not_ready`. Cost only with `VIEW_COSTS`. The Sociomap only with `EDIT_STUDY` (`:106-160, 427-619`) |
| `POST /research/agent-jobs {design_revision_id, action, instruction}`; `GET`; `…/cancel`; `…/result`; `…/accept {expected_revision_id}` | proposals; accept writes a revision through `submit_if_current`, which locks the Study, so a stale baseline answers 409 (`:620-753`; `test_two_reviewed_design_proposals_cannot_overwrite_each_other`) |

**Proposed, to be published by the PO.** None of these exists at `ceee2dc`:

- draft load and save, and its concurrency semantics;
- the stage bootstrap;
- attachment upload and reference;
- questionnaire import;
- the audience and library catalogues.

The Run stage (J6) will submit the PO's native draft through the existing `POST /design/revisions`;
today it submits the unit's working copy (`ExecutionSteps.tsx:91-107`). How an attachment is cited
from a design, and classified, is the PO's proposal (§6 rule 5).

## 5. Shared files

Ownership is agreed before concurrent change. Changes are applied one after another onto a
reconciled candidate. Migration heads are resolved explicitly: one head, and the later PR
re-points its `down_revision`. The chain has one head today: `1777fcb96352`; PR #63 added none.

| File or area | Owner | Rule for others |
|---|---|---|
| `domain/workflow_templates.py`; `apps/executors/src/aia_executors/registry.py`; `aia_executors/ai_runtime.py` bindings | J6 | handoff |
| The worker's `AIA_AI_*` keys in `deploy/develop/docker-compose.yml` and `env.example` | J6 | J1 displays them; the PO owns the rest of the file |
| `apps/api/src/aia_api/main.py` | J6 for research routers; PO for workspace and gate routers | one registration change at a time |
| The `api-contract` paths in `.github/workflows/ci.yml`; `apps/web/src/lib/api.ts` | J6 for research paths and types; PO for workspace paths and types | no edits to the other owner's lines |
| `migrations/versions/` | PO for workspace tables; each author otherwise | one head |
| `ExecutionSteps.tsx`; `lib/research-execution.ts`; the report and review screens | J6 for native destinations and actions | the PO removes classic links (`ExecutionSteps.tsx:420-422`) once J6's replacement is in |
| `GlobalPages.tsx`; `settings/ControlPanel.tsx`; `apps/web/src/i18n/cs.ts` | J1 for the AI settings panels; PO for legacy navigation and cards; J6 for research-stage copy | each owner edits only its own keys |
| Stage editors; `StudyFrame` and its bootstrap; `apps/web/src/unit/*` and its replacement | PO | — |
| `routers/panel.py`; `deploy/develop/Caddyfile`; `bin/*.sh`; `tools/caddy_routes.py`; `tools/develop_routing_*` | PO | — |
| `deploy/docker/python.Dockerfile` | PO; J6 adds only the `report` extra | agreed first |
| This document; the scenario; the research plan's Integration section | J6 | components add rows by handoff |
| OI-58, OI-59, the phase-out ADR, the screen and route ledgers | PO | findings handed over (§11) |

## 6. Rules every PR keeps

1. Scope comes from a server-issued `StudyContext` or `ClientContext`. Nothing sent by the browser
   authorizes anything, and another client's study answers 404.
2. A run executes one immutable Design Revision. A proposal changes a design only when a person
   accepts it against an unchanged baseline (`submit_if_current`).
3. Artifacts carry provenance: revision, harness and prompt fingerprints, model and route,
   request id, cost, population binding and `data_origin`.
4. Every paid call is reserved before dispatch, settled once and ledgered. An uncertain delivery
   goes to `RECOVERY_REQUIRED` and is never retried automatically.
5. Class C applies only to an allowlisted fictional client with no transmitted client material.
   Approved knowledge, or an attachment's content, makes a request Class A, and the approved route
   refuses Class A. Panel-derived data is refused by the licence gate (OI-61).
6. A number reaches a result or a report only as an `AdmittedClaim`. `NON_EVIDENCE_ORIGINS` never
   become client-facing claims, and every evidence row carries the origin of its data (OI-72). The
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

This is the state at `ceee2dc`. The Executable column names what exists; the later columns name
what is missing. Lines 1 and 7 decide **independence**. Lines 3–6 decide **completion**.

| # | Must show | Owner | Executable | Recorded | Enablement | Live |
|---|---|---|---|---|---|---|
| 1 | Sign in → client and study → native draft edit, save, reload → scoped attachment | PO | sign-in, client and study creation (`test_client_api.py`); the draft is still the unit's (OI-58) | UNMET | `/app` needs `AIA_LEGACY_PANEL_ENABLED` and an owner or admin role (`panel.py:53-62`, `application/scope.py:170-197`), and is refused in production (`config.py:213-215`, OI-59) | UNMET |
| 2 | Accurate runtime settings; the disabled and unconfigured behaviour | J1 | `app/config/route.test.ts`; a park on a disabled runtime (`test_ai_fieldwork.py`, `test_research_agent_executor.py`) | UNMET | the settings document calls the legacy subscription provider AIA's default (§10) | UNMET |
| 3 | Recorded Deep Research → reviewed design proposal → immutable revision → stale proposal refused | J5, J6 | proposals, acceptance and the stale refusal (`test_research_agent_executor.py`, `test_two_reviewed_design_proposals_cannot_overwrite_each_other`); Deep Research: none | UNMET | design switch off by default (`docker-compose.yml:176`); no search route (DR-2) | UNMET. The $2 fieldwork budget is spent |
| 4 | Readiness → fieldwork → aggregation and QC → validation → admitted analysis | J3, J6 | readiness to Sociomap (`test_research_executors.py`, `test_ai_fieldwork.py`); QC, validation, analysis execution: none | UNMET | fieldwork: fictional Class C approved (ADR 0010). Analysis: unbound | fieldwork MET (2026-09-26 activation: 20 calls, $0.2303301); the rest UNMET |
| 5 | Fixed-object research reuse → verification and alignment → stored report → authorized download → explicit review and delivery state | J4, J5, J6 | renderer and templates (`test_report_docx_*.py`). Nothing composes, stores or delivers a report | UNMET | none | UNMET |
| 6 | Cross-client denial; cancel and reload; failure states; retry and recovery; budgets and settled usage | J6 (and every job for its own stage) | 404 isolation, cancel, park, `RECOVERY_REQUIRED`, reservations (`test_research_api.py`, `test_workflow_concurrency.py`, `test_worker_processes.py`, `test_ai_usage_ledger.py`). A retry repeats paid respondents (OI-64) | UNMET | — | fieldwork settlement MET (2026-09-26); the rest UNMET |
| 7 | AIA starts, deploys and passes readiness and smoke with no reference service and no legacy health requirement | PO | start and readiness need no unit: no `depends_on` on it, and `/api/v1/ready` checks only the database; CI's `startup-smoke` boots the API and worker without it | UNMET | the deploy pulls and starts `legacy-panel` (`deploy/develop/bin/deploy.sh:40,97`); smoke fails without a healthy unit (`bin/smoke.sh:98-105`) | UNMET |

The scenario is accepted only when every line is MET in the Recorded column at one combined
candidate SHA. A line that a decision blocks stays UNMET and names the decision. It is never
forced green with a forged certification. A workspace-only browser test is not full-product
independence.

## 8. Blocked real-client paths: shown, never forced

| Path | Blocked by | How the scenario shows it |
|---|---|---|
| Client material, or an attachment's content, sent to a model | D6 (a Class A/B route) | client B's design jobs park on the egress refusal with zero calls |
| Panel-derived respondents | OI-61 (licence); the withheld archive (population import) | only the fictional roster runs; there is no `v17_4_0` binding |
| Web search | DR-2 (a search route); D8 (a key, for a keyed service) | Deep Research parks at its first external call |
| A client-facing Sociomap | D6 (methodology) | the report omits it and says so |
| A report delivered to a real client | AC-11's legal gate (`governance.legal` `NOT_STARTED`); every claim here is fictional | the review records *internal, fictional*; no client delivery exists |
| Fictional status beyond the allowlist | OI-63 | `AIA_AI_FICTIONAL_CLIENT_IDS` only, refused in production |

## 9. Phase B: what it needs

**From each job:** a PR against `develop` (draft or merged), its head SHA, its "Handoff to
integration" section, and its own checks green. **From the PO, additionally:** the published
workspace API shapes (§4.2) and, for the final run, the legacy-offline environment (§3.3). Phase B
integrates the latest heads. An unmerged stack is tested on an isolated integration branch, with
every component head recorded.

**J6's own work, in order:**

1. Register nodes, executors and bindings as J3, J4 and J5 land, adding the `report` extra with the
   report executor.
2. Build the recorded composition and the scenario (§3.2, §3.4). Add the layer rule that keeps
   `aia_worker.testing` out of deployments.
3. Build the Results, Report and Review destinations: native report retrieval, and the review and
   delivery decisions over `ArtifactRepository.approve` / `freeze`. Then the PO can remove the
   classic report link.
4. Fix OI-64 inside the fieldwork executor, or do not claim retry-safe acceptance.
5. Move the Run stage from the unit's working copy to the PO's native draft, once it exists.
6. Write the activation and live-acceptance runbook for the combined candidate. It names the
   revision, the switches, the approved data class and route, the scenario, a bounded proposed
   spend, rollback, and the evidence to collect. It is not executed without a new, explicit
   budget: the 2026-09-26 $2 authorisation is spent.

## 10. Stale claims found on 2026-09-27

"Corrected" means changed in this PR; "handed over" means the owner is named.

| Claim | Where | Evidence now | Action |
|---|---|---|---|
| Native design jobs are "implemented on this branch" and "not deployed" | `ai-runtime.md`, `research-agents.md` | merged in PR #63 (`85fa951`); in every develop build since deploy run 31; off by default (`docker-compose.yml:176`); no live design call is recorded | corrected |
| Only `SIMULATION` is bound | ADR 0010 | `RESEARCH_REASONING` and `CRITIC` are also bound when the design switch is on (`ai_runtime.py:274-276`); the route's approval is unchanged | corrected (dated note) |
| "No complete DOCX renderer exists yet"; reporting "not started" | `research-agent-workflows.md` handoff; PR #63 body; `domain-map.md` | PR #62 (`46b7337`) merged R4–R9; R10 and R11 remain | corrected |
| PRs #69, #70 and #71 are open; `2beafd9` is deployed | PROGRESS | all merged on 2026-09-27; `develop` @ `ceee2dc` deployed by run 34 | corrected |
| Credentials come from Secrets Manager | `mvp-acceptance.md` AC-02; `parity-matrix.json` AC-02 and `ai.credentials`; PROGRESS D7 and D8 | Bedrock signs with the instance or container role (`infrastructure/model_adapters/aws_signing.py`, ADR 0010). A secret store is still needed for a keyed service such as a search API | corrected |
| `preflight` pauses for a person on a warning; no executor exists for a real step; progress is sent as server-sent events | `workflows.md` | the reference pauses only on a BLOCKER. Research, proposal and snapshot executors exist. Events are a cursor-paged JSON list (`routers/research.py:480-507`), and the Progress stage polls the run | corrected |
| The unit stays "as the oracle and a fallback" | ADR 0015 decision 5; OI-58 | the oracle and a frozen reference only; no runtime fallback (the user's direction) | handed to the PO |
| AIA's AI default is `claude_code_subscription` / `CLAUDE_CODE_ONLY` | `GET /api/v1/settings` (`routers/settings.py:200-217`) | these are persisted legacy fields; the worker binds Bedrock capabilities only | handed to J1 |
| Run, Progress and Results use no unit route; the rebuilt stages call unit AI routes | `docs/migration/interface-screens.json` | all eight stages need `/api/bootstrap` and `/api/projects/load`; the AI actions are native agent jobs | handed to the PO |
| Implementation states of `ai.gateway`, `ai.usage_ledger`, `ai.credentials`, `reports.generation` (`NOT_STARTED`) and `workflow.step_execution`'s note ("No research step body exists") | `parity-matrix.json` | all have merged code. Re-grading them touches the module inventory (OI-30) | handed to the parity owner |

## 11. Handoff to the phase-out owner

These are findings from this inventory, anchored at `ceee2dc`, that sit in the PO's area.

- **Deployment coupling.**
  - The deploy pulls and starts `legacy-panel` (`deploy.sh:40,97`), and smoke fails without a
    healthy unit (`smoke.sh:98-105`).
  - The three image lists must change together: `docker-compose.yml:201`,
    `deploy-develop.yml:128-142`, `infra/develop/main.tf:17`; `test_deploy_images.py` pins them.
  - CI's `oracle-parity` job requires the unit whenever `AIA_LEGACY_REFERENCE_URL` is set
    (`ci.yml` `oracle-parity`). Clear it before the unit leaves.
  - `tools/caddy_routes.py` requires `/app` behind the panel gate (`:143-148`) and the product
    hostname routing to the unit (`:160-164`). `test_ui_workbench.py:38-41` fails to collect if
    the Caddyfile has no unit matcher.
  - Stale comments still call `/` the 18.6.6 document: `docker-compose.yml:102-106`,
    `Caddyfile:43-45`, `apps/web/src/app/interface-document/route.ts:9-12`, `lib/panel.ts:4-5`.
- **`canEdit` does not stop autosave.** From the code, a signed-in reader's edits still autosave
  to the unit: `canEdit` gates only the AI buttons, revisions and runs (`ResearchScreen.tsx:280`,
  `ExecutionSteps.tsx:98`), and `store.ts` has no read-only mode. This is a hypothesis to
  reproduce; the native draft should enforce `EDIT_STUDY` on save by construction.
- **Legacy-dependent actions a supported workflow still uses:**
  - attachments (`BriefStep.tsx:160-183`);
  - questionnaire import and templates (`QuestionnaireStep.tsx:79-80, 249-254`);
  - audience check, catalogue and uploads (`AudienceStep.tsx:86-95, 337-345, 429`);
  - the library and dimension requests (`PersonaStep.tsx:98-115, 333`);
  - the classic report (`ExecutionSteps.tsx:420-422`);
  - *Diagnostika* (`useAiStep.tsx:72-76`);
  - the classic-projects pages (`ProjectsScreen.tsx:63`, `TrashScreen.tsx:26`).
- **The product README's index links three documents that were never written:**
  `docs/product/README.md:171-173`.
