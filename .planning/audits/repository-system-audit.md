# AIA Repository System Audit

**Status:** investigation complete; review before refactoring  
**Audit date:** 2026-10-08  
**Baseline:** latest `develop` inspected on 2026-10-08, after PR #196 (DOCX export integration)  
**Scope:** architecture, structure, maintainability, connectivity, redundancy, stale/legacy surfaces, state, terminology, methodology provenance, Deep Research, frontend/backend contracts, infrastructure and documentation  
**Primary rule:** this is not a bug hunt. Do not begin broad refactoring from this document without reviewing the evidence and the decision-gated items.

## Audit posture

This audit treats code, ADRs, plans, tests, current routes and call-site evidence as separate evidence sources. Documentation is not assumed correct merely because it is present. In particular, several root/current-state documents materially lag the implementation.

The audit is deliberately conservative around methodology, frozen runs, provenance, cost accounting, scope and compatibility. Similar-looking methodology implementations are not classified as duplicates unless their semantics and version identities match. Migration/reference code is not classified as dead merely because it is not in the normal product path.

Confidence meanings:

- **HIGH** — current `develop` contains direct evidence of the finding.
- **MEDIUM** — strong evidence, but runtime/external-consumer or migration-state verification is still required before change.
- **LOW** — concern worth investigating; insufficient evidence for a change.

Priority aid:

`priority = (architectural benefit + maintenance benefit + complexity reduction) × confidence factor / (effort + risk)`

with HIGH = 1.0, MEDIUM = 0.7, LOW = 0.4. Scores are aids, not automatic sequencing.

---

# A. Executive assessment

## Is AIA structurally coherent?

**Yes, at the core.** The current production architecture is substantially more coherent than the migration-era documents imply. The strongest parts are:

- explicit `domain -> application -> infrastructure` boundaries with CI enforcement;
- PostgreSQL as the authoritative operational store, with SQLite constrained to tests/offline development;
- a Study-scoped research lifecycle that freezes a Design Revision before execution;
- a durable workflow model separating business run state, step state and technical attempt state;
- governed model execution through one gateway, a pre-dispatch journal and an append-only usage ledger;
- explicit methodology/version identities for Sociomapping and Deep Research;
- immutable project/design revisions and artifact provenance;
- client/study scope derived from persisted authenticated context rather than model/request authority;
- report generation as a derived artifact consuming admitted canonical outputs rather than recalculating research.

The codebase does **not** need a wholesale architectural rewrite.

## Where has architectural entropy accumulated?

Entropy is concentrated at migration seams rather than uniformly throughout the system:

1. **Documentation describes multiple historical architectures at once.** Root README, scope documentation, `.planning/overview.md`, report planning state and comments in source still describe grants, old routes, old defaults and old executor composition that no longer match `develop`.
2. **`Project` still has two meanings.** It remains a useful internal immutable-revision substrate, but generic Project/Run product APIs and frontend client methods coexist beside the newer Study-centric product and ResearchRun model.
3. **Known transitional features exist in partial states.** Population/Data Library is architecturally substantial but not product/API connected; Simulation is a Study shell without its 13-stage AIA implementation; Project Memory is currently a study index, not reusable-artifact memory; Social Intelligence is explicitly unavailable.
4. **Deep Research settings are mid-migration.** Catalogue/store/admin UI are present, while run pinning and live-approval enforcement remain planned work.
5. **Legacy migration/reference surfaces are intentionally retained, but some now have clear removal conditions.** They should be removed as coherent packages after those conditions are satisfied, not piecemeal.
6. **Some domain names overlap while representing different semantics.** Evidence and population both define `FieldPolicy`/`JointStatus`; this is more dangerous than ordinary duplicate code because accidental interchange would alter methodological authority.

## Is there meaningful redundant architecture?

Yes, but less than directory/file names initially suggest.

- The strongest actual overlap is the **public generic Project/pipeline surface vs the Study-centric product/runtime surface**.
- Evidence/population naming has **semantic duplication of names, not safe implementation duplication**.
- Sociomap `engine.py` / `engine_v2.py`, spec contracts, H-Model evaluator and experimental candidate are **deliberate methodology/version separation and must not be collapsed**.
- The workflow run/step/attempt state split is deliberate and should remain.
- SQLite support is a controlled test/offline adapter, not a second authority.
- Deep Research code defaults plus approved DB values are a deliberate transitional mechanism in ADR 0022, not an accidental dual source of truth once run pinning is completed.

## Are major capabilities actually connected?

**Research execution, AI runtime, analysis, Sociomapping and DOCX reporting are connected.** Population/Data Library, Simulation, full Project Memory and Social Intelligence are not yet complete product workflows. Their disconnected status is explicit enough that they should be finished or kept visibly unavailable, not simulated with mocks.

## What legacy surfaces are still active?

- `/classic` is now a notice-only compatibility page; it does not expose 18.6.6.
- `/app/research/*` and `/app/projects/*` are redirect compatibility aliases to the client-first interface.
- the 18.6.6 unit remains a separate parity/reference oracle and source for a one-off workspace migration;
- read-only `UnitProjectStore` and `legacy_workspace` exist only for that migration;
- Project identifiers, project pipeline parity and some compatibility parsing still preserve legacy contracts;
- generic Project/Run API routes remain mounted and need an explicit current-consumer inventory before retirement.

## Largest maintainability risk

**Developers learning the wrong architecture from canonical-looking documentation and then extending the wrong seam.** The current root README still teaches old routes, old access grants, old approval defaults and Project-as-product-source-of-truth. This can recreate retired architecture even if the runtime is currently correct.

The second-largest risk is leaving the generic Project product API alive indefinitely beside the Study/ResearchRun architecture, allowing new callers to choose either substrate.

## Highest-leverage cleanup

1. Correct current-state documentation and source comments first.
2. Decide and document the target role of `Project`: internal immutable revision container, not a parallel product aggregate.
3. Inventory generic Project/Run API consumers and retire that public surface if no supported consumer remains.
4. Complete Deep Research settings pinning/live enforcement before expanding live usage.
5. Namespace evidence vs population policy/status concepts to prevent semantic interchange.
6. Convert migration/reference compatibility into explicit removal packages with measurable exit criteria.

---

# B. Repository topology

## Product/domain

`Organization -> Client -> Study`

- `Study.kind`: `RESEARCH` or `SIMULATION`.
- Study is the product unit of budget, lifecycle, delivery and client context.
- Research Study working content is stored in an AIA-owned working Project reached only through `StudyWorkspaceRow`/`StudyWorkspaceRepository`.
- Run-executable design is stored separately as immutable Design Revisions in a Study-owned design Project reached through `StudyDesignRow`/`StudyDesignRepository`.
- Client Knowledge is client-scoped, append-only by revision and provenance-aware.
- Scope contexts are issued from authenticated persisted state.

## Backend

- `packages/aia_core/domain`: pure rules, methodology, contracts and state machines.
- `packages/aia_core/application`: use cases/orchestration: scope, research, population, analysis, report, model gateway, Deep Research.
- `packages/aia_core/infrastructure`: PostgreSQL tables/repositories, artifact stores, provider adapters, journals, usage ledger, migration readers.
- `apps/api`: FastAPI composition and transport schemas.
- `apps/worker`: claims durable workflow attempts and executes through the executor protocol.
- `apps/executors`: research/analysis/report/AI/Deep Research implementations and operational compositions.

## Frontend

Current product navigation is client-first under `/app/clients`.

- `/app/clients/[clientId]` owns research/simulation/data/knowledge areas.
- Research screens resolve a Study through the workspace API, then run within the Study frame.
- old `/app/research/*` and `/app/projects/*` routes redirect to `/app/clients`.
- `/classic` is a retired-interface notice only.
- Simulation and Social Intelligence visibly state that the capability is not in AIA yet.
- Project Memory currently searches/list Studies, not approved reusable artifacts.

## Data layer

- PostgreSQL is authoritative.
- Project revisions are immutable and underpin working-content/design history.
- workflow run/step/attempt state is durable in PostgreSQL.
- artifact bytes are external (S3 in develop/production shape), metadata and provenance are in PostgreSQL.
- Study workspace/design tables prevent reverse lookup by caller-supplied Project IDs.
- population registry/version/promotion/run-binding infrastructure is implemented.
- AI call journal and usage ledger are append-only/fail-safe.
- SQLite exists only for tests/offline development and is rejected for production composition.

## AI/runtime layer

- `GovernedModelGateway` is the single governed model-call semantic.
- provider-specific details are infrastructure adapters.
- dispatch is journaled before a potentially billed call leaves.
- cost usage is append-only and scoped.
- workers own execution; API requests do not invoke model runtime.
- Deep Research owns a separate frozen/versioned research harness while still using governed model execution beneath it.

## Deterministic methodology

- deterministic research logic lives in domain/application code, not React.
- Sociomap has explicit spec contracts/methodology versions and immutable artifacts.
- analysis/evidence admission is deterministic and provenance-bound.
- population policies/versioning are deterministic.
- the report renderer consumes canonical admitted outputs and does not reproduce research logic.

## Infrastructure

The current **develop** architecture is deliberately lean:

- one EC2 host in `eu-central-1` under Docker Compose;
- Caddy, web, API, worker, PostgreSQL;
- S3, Cognito, ECR, SSM, IAM/CloudWatch/Bedrock as AWS services;
- no claim that App Runner/ECS/RDS is already the production answer.

This is an accepted develop-environment decision, not infrastructure residue.

---

# C. Canonical concept matrix

| Concept | Canonical implementation | Other representations | Status | Recommended action |
|---|---|---|---|---|
| Organization | `domain.scope` + scope persistence | old docs describing grant-era model | canonical | keep; update docs |
| Client | `domain.scope.Client`, `ClientRow`, client-first UI | old `unit/project` navigation language | canonical | keep |
| Study | `domain.scope.Study`, `StudyRow`, `StudyContext` | generic Project still exposed as product API | canonical product aggregate | make Study/product relationship explicit everywhere |
| Study kind | `StudyKind.RESEARCH/SIMULATION` | `ProjectType.research/simulation` | Study kind canonical for product; ProjectType internal/legacy substrate | avoid presenting ProjectType as separate product truth |
| Study workspace | `StudyWorkspaceRepository`, `StudyWorkspaceRow` | legacy unit project lineage | canonical | keep |
| Design Revision | `StudyDesignRepository` over owned immutable Project revisions | working workspace revisions | canonical executable design | keep separation |
| Project | `ProjectRepository` immutable revision substrate | generic Project CRUD/API/product language | mixed | internalise product meaning after consumer inventory |
| ResearchRun | `application.research.ResearchRuns` + durable workflow | generic Project Run API | canonical research execution | keep; retire competing public entrypoint if unused |
| Workflow run/step/attempt | `domain.workflow` | legacy `StageStatus` project pipeline | canonical execution state | keep explicit split; clarify project-stage legacy/internal role |
| Population registry | `PopulationRuntime` + registry repository | legacy panel/import source concepts | canonical backend foundation | expose only after product/operator decisions |
| Population LIVE revision | version/promotion records and run binding | imported dataset/version terminology | canonical data authority | keep version semantics |
| Evidence FieldPolicy | `domain.evidence.field_policy.FieldPolicy` | population `FieldPolicy` | separate semantic concept | rename/domain-qualify rather than merge |
| Evidence JointStatus | certificate-bound evidence authority | population `JointStatus` | separate semantic concept | rename/domain-qualify rather than merge |
| Sociomap spec | versioned `SociomapSpec` / `SociomapSpecV3` | presets V1/V2 | deliberate versioning | keep explicit contracts |
| Sociomap engine | `compute_sociomap` for contract 2; `compute_object_map` for corrected contract 3 | H-Model evaluator/candidate | deliberate methodology variants | do not consolidate without methodology decision |
| H-Model candidate | `hmodel_candidate`, status `EXPERIMENTAL_AIA` | SOMECS evidence/evaluator | experimental by design | keep isolated and visibly non-canonical |
| Deep Research request | frozen request in `application.deep_research` | legacy pre-contract readable runs | canonical current harness | keep versioned compatibility |
| Deep Research settings | code catalogue + immutable approved versions | code proposed defaults | intentional transition | finish run pin + live readiness enforcement |
| Model execution | `GovernedModelGateway` | provider adapters | canonical | keep |
| AI dispatch record | `ai_call_journal` | usage ledger | complementary, not duplicate | keep both |
| Cost accounting | append-only AI usage ledger + reservations | Study `spent_usd` projection | ledger authoritative | keep |
| Report model | domain report document built from admitted outputs | DOCX renderer | canonical data vs rendering split | keep |
| DOCX output | `infrastructure/report_docx` and research report artifact endpoint | plan still marked in-progress | canonical output | update plan/docs only |
| Client Knowledge | client knowledge repository + append-only revisions | future Project Memory/reuse | canonical approved client context | keep |
| Project Memory | current UI lists/searches Studies | intended historical/reusable artifacts | incomplete | define/reconnect before calling it complete |
| Simulation | Simulation Study shell | legacy Project simulation stages/18.6.6 capability | incomplete product capability | client decision, then implement one canonical workflow |
| `/classic` | notice-only page | 18.6.6 separate reference deployment | compatibility notice | keep until inbound-link retirement decision |

---

# D. Redundancy register

## RED-001 — Evidence and population policy/status names collide

**Locations**

- `aia_core.domain.evidence.field_policy.FieldPolicy`
- `aia_core.domain.population.policy.FieldPolicy`
- `aia_core.domain.evidence.joint_status.JointStatus`
- population-side `JointStatus`
- `.planning/open-items.md` OI-24

**Duplicated responsibility/name:** both domains use the same names for different authority/row semantics.

**Canonical implementation:** there is no single canonical implementation; these are distinct concepts.

**Recommended action:** domain-qualify/rename the concepts (`EvidenceFieldPolicy`, `PopulationFieldPolicy`, etc.) and make any conversion explicit. Do **not** merge semantics. Add a boundary test preventing accidental interchange.

**Risk:** 5/5  
**Architectural benefit:** 5  
**Maintenance benefit:** 5  
**Complexity reduction:** 4  
**Effort:** 3  
**Confidence:** HIGH  
**Priority:** 1.75

## RED-002 — `Project` is both a public product surface and an internal Study revision container

**Locations**

- `domain/project.py`
- `domain/pipeline.py`
- `infrastructure/repositories.py`
- `routers/projects.py`
- `routers/runs.py`
- `apps/web/src/lib/api.ts`
- `StudyWorkspaceRepository`
- `StudyDesignRepository`
- `application/research.py`

**Duplicated responsibility:** the newer product is Study-centric, while generic Project CRUD/run APIs still expose Project as a user-level source of truth. Internally, Project is also a valuable immutable-revision storage primitive for Study workspace/design.

**Likely canonical implementation:** Study is the product aggregate; Project remains an internal immutable version/work substrate unless a supported external Project use case is demonstrated.

**Recommended action:** inventory callers of generic Project/Run routes and frontend methods, then retire the public product surface while keeping the internal Project repository/revision graph. Rename/internalise only where doing so lowers ambiguity without destabilising migration history.

**Risk:** 4  
**Architectural benefit:** 5  
**Maintenance benefit:** 5  
**Complexity reduction:** 5  
**Effort:** 4  
**Confidence:** MEDIUM  
**Priority:** 1.31

## RED-003 — Deep Research policy values temporarily have code and DB homes

**Locations**

- `domain/deep_research/settings`
- `deep_research_settings_repository`
- `routers/deep_research_settings.py`
- ADR 0022
- `.planning/plans/deep-research-web-search.md` chunks 40–44

**Classification:** intentional transitional duplication. Code owns a bounded proposed default; approved immutable DB versions can override it. The remaining architectural requirement is to freeze the effective setting set into each run.

**Recommended action:** complete chunks 43–44; do not collapse defaults into mutable DB-only configuration or allow runs to read current settings mid-flight.

**Risk:** 4  
**Architectural benefit:** 5  
**Maintenance benefit:** 4  
**Complexity reduction:** 4  
**Effort:** 4  
**Confidence:** HIGH  
**Priority:** 1.63

---

# E. Stale-code register

## STALE-001 — Generic frontend Project/Run API client appears orphaned from current client-first UI

**Location:** `apps/web/src/lib/api.ts`

The module still exposes generic Project types and calls such as project listing/creation and Project-level run operations beside the newer workspace/client APIs. The current product routes and Research Study component use the workspace/Study path.

**Evidence caveat:** GitHub code search does not search arbitrary refs reliably; an exhaustive local `develop` call-site scan must be the deletion gate.

**Recommended action:** verify imports/callers across current `develop`, tests, workbench and any supported external UI; remove uncalled frontend methods/types as part of the Project-surface retirement package.

**Risk:** 2  
**Benefit:** A4 / M4 / C5  
**Effort:** 2  
**Confidence:** MEDIUM  
**Priority:** 2.28

## STALE-002 — Grant-era authorization comments remain after ADR 0019 implementation

**Locations:** `domain/scope.py`, `infrastructure/tables.py`, root README and scope docs.

These comments describe client/study grants, organization admins without research access and grant-denial audit events that the current resolver no longer implements.

**Recommended action:** remove or rewrite stale comments now. This is safe documentation cleanup; do not wait for a larger refactor.

**Risk:** 1  
**Benefit:** A5 / M5 / C4  
**Effort:** 1  
**Confidence:** HIGH  
**Priority:** 7.0

## STALE-003 — Sociomapping frontend fixture may be a leftover fixture

**Location:** `apps/web/src/lib/fixtures/sociomapping.json`

The fixture is present on `develop`; a repository search did not identify a current consumer, but JSON/import indexing is not sufficient proof.

**Recommended action:** verify direct/dynamic/test/workbench references locally. Delete only if no consumer exists; otherwise move it under the test/workbench surface and name its purpose.

**Risk:** 1  
**Benefit:** A2 / M2 / C2  
**Effort:** 1  
**Confidence:** LOW  
**Priority:** 1.2

---

# F. Disconnected-capability register

## DISC-001 — Population/Data Library backend is implemented but not product-connected

**Evidence**

- `application/population.py` centralises population/version/promotion/run-binding behavior.
- `application/population_authority.py` defines operator authority.
- no population router is mounted in the current API router set.
- the client scope still marks Data Library / societal intelligence as awaiting client confirmation.

**Status:** implemented foundation, disconnected product capability.

**Recommended action:** retain. Before wiring UI/API, decide the operator model, ingestion approval flow and client-facing vocabulary. Connect through one Study/client-aware surface; do not create a second registry.

**Risk:** 4  
**Benefit:** A5 / M4 / C3  
**Effort:** 5  
**Confidence:** HIGH  
**Priority:** 1.33

## DISC-002 — Simulation Study exists but the 13-stage AIA simulation workflow does not

**Evidence:** `SimulationFrame.tsx` explicitly states the workflow is not in AIA. Legacy project pipeline constants still describe simulation stages, but the product does not execute the promised canonical AIA simulation flow.

**Status:** intentional product shell / pending client confirmation.

**Recommended action:** keep unavailable state honest. Once confirmed, implement the Simulation Study workflow against the same frozen-result/provenance principles as Research; do not revive a generic Project product flow as the implementation shortcut.

**Confidence:** HIGH.

## DISC-003 — Project Memory page is a Study index, not reusable-artifact memory

**Evidence:** `GlobalPages.tsx::MemoryPage` lists Studies per client and searches names. It does not search approved artifacts/findings/report sections/history.

**Status:** partial UX placeholder.

**Recommended action:** define the canonical reusable-artifact contract first: what may be reused, approval/provenance requirements, version identity, scope and invalidation. Then build search over that authority.

**Confidence:** HIGH.

## DISC-004 — Social Intelligence is an explicit placeholder while population capability exists separately

**Evidence:** `GlobalPages.tsx::IntelligencePage` says the capability is not in AIA; population/runtime infrastructure exists independently.

**Recommended action:** after client confirmation, connect the product concept to the existing population/data authority rather than building a new parallel data store.

**Confidence:** HIGH.

---

# G. Boundary-violation register

## ARCH-001 — Legacy Project product ontology leaks above its intended storage role

**Evidence**

- `domain/project.py` says “the project is the source of truth”.
- API description and generic Project/Run routers expose this directly.
- current Client -> Study UI and research orchestration treat Study as the product aggregate and internal owned Projects as storage/version containers.

**Correct ownership:** Study at product/application boundary; owned Project repository/revision graph beneath the Study as an implementation substrate.

**Recommended action:** fix language first; then retire unsupported public generic Project routes after caller verification.

**Confidence:** HIGH on the boundary ambiguity; MEDIUM on route deletion.

## ARCH-002 — No high-confidence core layer violations found

This is a positive result, not an absence of scrutiny. `tools/layer_check.sh` actively forbids:

- domain imports of framework/driver/provider SDKs;
- application/infrastructure HTTP dependencies;
- provider SDK bypasses;
- API-side model execution;
- unscoped workflow access;
- direct table access for scoped knowledge/settings;
- mutable Project Revision updates;
- production use of fictional fieldwork composition.

**Recommended action:** keep the lightweight architecture ratchet and add rules only when a new invariant has first been made true.

---

# H. Architecture-fossil register

## FOSSIL-001 — Retired grant/role compatibility terminology in scope

`ScopeRole.from_stored()` retains retired role spellings for compatibility; `ScopeGrant` now means a private issued-context proof rather than the old persisted access grant.

**Why it existed:** migration from the four-role/client-grant model.

**Does the reason still exist?** Possibly for old stored values; current access semantics no longer need grants.

**Action:** verify persisted/migration readers. Remove retired-role parsing only after old values can no longer be loaded. Consider renaming the private issuer token only if it materially reduces confusion.

**Risk:** 3  
**Effort:** 2  
**Confidence:** MEDIUM.

## FOSSIL-002 — One-off 18.6.6 workspace migration reader/CLI

**Locations:** `apps/executors/.../legacy_workspace.py`, `infrastructure/unit_project_store.py`, workspace lineage/state.

**Why it exists:** explicit read-only migration of Study working content from 18.6.6.

**Removal condition:**

1. no Study remains `AWAITING_MIGRATION`;
2. migration report is accepted;
3. rollback window is closed;
4. a decision is made on how much legacy lineage remains queryable.

**Action:** remove as one coherent package only after those conditions.

**Confidence:** HIGH that it is transitional; MEDIUM on timing.

## FOSSIL-003 — `/app/research/*` and `/app/projects/*` redirects

**Why:** preserve old bookmarks/links while moving to `/app/clients`.

**Action:** keep until inbound-link compatibility is intentionally retired. Add a removal condition/telemetry date rather than leaving aliases permanent.

**Confidence:** HIGH.

## FOSSIL-004 — `/classic` retired-interface notice

`/classic` no longer runs or embeds 18.6.6. It explains retirement and links into AIA.

**Action:** keep while old links/bookmarks remain a supported migration concern. It is not technical debt by itself.

**Confidence:** HIGH.

---

# I. Terminology inconsistencies

## TERM-001 — Study vs Project

**Canonical product term:** Study.  
**Internal implementation term:** Project can remain for revision/workspace storage.

Avoid telling users/developers that Project is a parallel product aggregate.

## TERM-002 — Grant

Access grants are retired under ADR 0019, while `ScopeGrant` now names an unforgeable issued-context token. This creates avoidable ambiguity in code review and documentation.

Recommendation: either rename the token in a deliberate cleanup or explicitly document that it is not persisted access authority.

## TERM-003 — Project Memory

The current page name implies reusable historical knowledge; implementation currently means searchable Study listing. Until the artifact-reuse contract exists, label docs/status as partial rather than declaring the product capability complete.

## TERM-004 — “Approved”

Approval can mean human acceptance of AI proposal, artifact/evidence admission, client-facing release or other gates. Keep existing open-item governance and prefer domain-qualified terms (`accepted proposal`, `admitted claim`, `released deliverable`) over a generic boolean where semantics differ.

---

# J. State-machine inconsistencies

## STATE-001 — Study/Project/workflow states overlap conceptually and need ownership clarification

Current state machines include:

- `StudyStatus`: engagement lifecycle (`DRAFT`, `ACTIVE`, `IN_REVIEW`, `DELIVERED`, `ARCHIVED`, `CANCELLED`).
- `ProjectStatus`: legacy/internal project lifecycle (`DRAFT`, `READY_TO_CONTINUE`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `ARCHIVED`, `TRASHED`).
- `StageStatus`: legacy/project-stage state.
- `WorkflowRunStatus`, `StepRunStatus`, `AttemptStatus`: current durable execution model.

The workflow run/step/attempt split is intentional and should remain. The concern is that generic Project APIs keep Project/Stage lifecycle visible as a parallel orchestration model.

**Recommendation:** as the public Project surface is retired, document ProjectStatus/StageStatus as revision/workspace compatibility state or retire portions that no longer drive current execution. Do not mechanically merge them into workflow status.

**Confidence:** MEDIUM.

---

# K. Configuration/dependency cleanup

## CONFIG-001 — Finish Deep Research settings freeze before live expansion

ADR 0022 chunks 40–42 are implemented: typed catalogue, immutable versions/approvals and settings UI/API. The plan still leaves:

- **43:** pin effective settings into the run and include method settings in reuse identity/harness update;
- **44:** refuse live execution unless required settings were approved for that organization.

Until those land, settings are an incomplete governance migration.

**Action:** finish before live activation/evaluation expansion.

**Confidence:** HIGH.

## CONFIG-002 — Production compute remains an explicit decision, not stale configuration

Develop on one EC2/Compose host is intentional ADR 0009. Do not remove EC2/Compose configuration merely because older plans discussed App Runner/ECS/RDS. Decide production compute separately when scale/availability requirements justify it.

**Confidence:** HIGH.

## DEP-001 — No high-confidence unused runtime dependency deletion identified

This audit found no dependency whose removal is sufficiently evidenced to recommend deletion. Do a generated import/package-graph pass immediately before a dependency-cleanup PR rather than inferring from package names. Provider/AWS/document libraries have deliberate lazy/extra boundaries and should not be collapsed casually.

---

# L. Documentation drift

## DOC-001 — `.planning/overview.md` is not a current-state overview

It is dated 2026-09-28 and references an older develop commit while the branch has materially advanced through Deep Research/settings/report work.

**Action:** regenerate/rewrite from current plan front matter and current develop state.

**Confidence:** HIGH.

## DOC-002 — `CLAUDE.md` says analysis executor is not composed

Current executor registry imports/registers research analysis and swaps in the gateway-backed implementation when enabled.

**Action:** correct the map.

**Confidence:** HIGH.

## DOC-003 — report plan status contradicts current implementation

`report-docx.md` front matter/checklist remains in-progress while its body and current develop/report API show the DOCX report path integrated, including PR #196.

**Action:** reconcile front matter/chunk log with actual completion and leave only genuinely open report-quality/client-release work open.

**Confidence:** HIGH.

## DOC-004 — root README teaches retired routes/product ontology

The README still states:

- `/studies` is the live frontend slice;
- `/org/*` is mock data;
- Project is the product source of truth;
- client/study grants control access;
- independent review/self-approval-off is the default.

These conflict with current client-first routes and ADR 0019.

**Action:** rewrite README immediately around Organization -> Client -> Study, current `/app/clients`, current access model, current AI gates and internal Project substrate.

**Confidence:** HIGH.

## DOC-005 — scope-and-authorization document is a superseded model still presented in the body

Its header acknowledges ADR 0019, but the majority of the document still explains four roles/grant precedence and says grant tables/routes remain until a future chunk, while current resolver/tables have already moved past that model.

**Action:** replace the body with the current two-role/membership access model; move historical grant architecture to an archived/superseded appendix or rely on ADR history.

**Confidence:** HIGH.

## DOC-006 — migration status is narrative history but README points to it as “exactly what works today”

`docs/migration/status.md` explicitly admits that its body is historical and stale. The README nevertheless directs contributors there for exact current state.

**Action:** remove that promise; point current status to plan front matter/progress output and a refreshed overview.

**Confidence:** HIGH.

---

# M. Suggested target architecture changes

These are changes justified by the findings, not a redesign wish list.

## 1. Make Study the only product-level execution aggregate

Target:

`Organization -> Client -> Study -> {workspace revisions, design revisions, runs, artifacts}`

Keep ProjectRepository/revision tables as an internal version/work substrate if they continue to provide immutable revisioning, dedupe and provenance. Stop exposing Project as a parallel generic user concept unless a supported use case proves necessary.

## 2. Keep execution state in one current workflow engine

Research/Simulation business workflows should converge on `WorkflowRun -> StepRun -> StepAttempt`. Legacy `ProjectStatus`/`StageStatus` may remain where they describe revision/workspace compatibility, but should not remain a second public orchestration API.

## 3. Make methodology namespaces explicit

Evidence and population policies/statuses must not share generic names where their authority differs. Sociomap versioned contracts must remain side-by-side until methodology decisions supersede them explicitly.

## 4. Finish frozen Deep Research settings

A run must carry the effective approved/proposed settings it was enqueued with; reuse identity must change for method/admission settings. Live execution must fail closed until required policy settings are approved.

## 5. Treat incomplete product capabilities as explicit bounded modules

Population/Data Library, Simulation, Social Intelligence and Project Memory should each receive a product decision and one canonical integration path. Until then, explicit “not in AIA” is preferable to temporary mocks becoming architecture.

## 6. Turn compatibility into expiring contracts

Every redirect, legacy parser or migration adapter should have a consumer, owner and removal condition recorded in one compatibility register.

---

# N. Cleanup dependency graph

```text
[Correct canonical docs: README / scope / overview / plans]
                      |
                      v
[Confirm Study is sole product aggregate; Project is internal substrate]
                      |
          +-----------+------------+
          |                        |
          v                        v
[Inventory Project API callers]  [Clarify Project/Workflow state ownership]
          |                        |
          +-----------+------------+
                      v
       [Retire unsupported public Project/Run surface]
                      |
                      v
       [Remove orphan frontend Project API/types]

[OI-24 semantic decision / namespace]
                      |
                      v
[Rename evidence/population policy/status concepts]

[DR settings 40-42]
        |
        v
[43 pin settings + reuse identity]
        |
        v
[44 live approval enforcement]
        |
        v
[Deep Research live evaluation/activation]

[Run legacy workspace migration + accept report]
        |
        v
[Close rollback window]
        |
        v
[Retire migration CLI/read-only legacy store]

[Client confirms Data Library / Simulation / Memory / Social Intelligence]
        |
        v
[Connect each to existing canonical authorities; no parallel stores]
```

---

# O. Proposed cleanup sequence

## Phase 0 — verify before touching

1. Confirm the product decision that **Study is the sole user-level aggregate** and generic Project is internal implementation only.
2. Exhaustively inventory callers of generic Project/Run APIs and `apps/web/src/lib/api.ts` Project methods, including workbench/tests/scripts/external consumers.
3. Resolve/record OI-24 naming/ownership for evidence vs population policy/status.
4. Confirm whether any persisted retired scope roles still require compatibility parsing.
5. Determine actual workspace migration state (`AWAITING_MIGRATION` count, accepted migration report, rollback window).
6. Complete Deep Research settings chunks 43–44 before live enablement.
7. Obtain client decisions for Simulation, Data Library/Social Intelligence and Project Memory behavior.

## Phase 1 — safe cleanup

- Rewrite README current architecture/access/routes.
- Rewrite scope-and-authorization docs for ADR 0019.
- Refresh `.planning/overview.md`.
- Reconcile report plan front matter/status.
- Correct CLAUDE executor composition.
- Remove stale grant/self-approval comments in code/tables.
- Add explicit removal conditions to compatibility redirects/migration surfaces.
- Delete/move the Sociomapping frontend fixture if local call-site verification proves it unused.

## Phase 2 — consolidation

- Namespace evidence/population FieldPolicy/JointStatus concepts.
- Make Project’s internal role explicit in names/docs/API boundaries.
- Remove orphaned frontend generic Project DTO/API methods after caller verification.
- Consolidate any duplicated transport schemas found during the Project API retirement into Study/ResearchRun schemas.

## Phase 3 — reconnect

- Complete Deep Research settings pin/live enforcement.
- Connect Population/Data Library only after operator/product decisions.
- Implement canonical Simulation Study workflow after client confirmation.
- Build Project Memory on approved reusable artifacts rather than just Study listings.
- Connect Social Intelligence to the population/data authority rather than creating another data model.

## Phase 4 — boundary repair

- Remove unsupported generic Project/Run API entrypoints if caller inventory confirms they are transitional.
- Ensure every product route enters through Study/Client scope and application services.
- Keep ProjectRepository ownership hidden behind Study workspace/design/research services.

## Phase 5 — deeper simplification

- Retire legacy workspace migration code after the migration/removal conditions are met.
- Retire redirect aliases and `/classic` only after inbound-link policy permits.
- Remove retired role parsing once old persisted representations are impossible.
- Revisit ProjectStatus/StageStatus after generic Project product surface is gone; remove only states with no remaining internal compatibility/revision purpose.

---

# Cleanup work packages

## Package 1 — Current-state documentation reset

**Purpose:** make the repository teach the architecture it actually runs.  
**Files:** README, `.planning/overview.md`, scope docs, CLAUDE, report plan, relevant source comments.  
**Prerequisite:** none.  
**Outcome:** one current Organization -> Client -> Study narrative and ADR0019 access model.  
**Risk:** low.  
**Tests:** docs checks, progress check, link checks, layer check.  
**Rollback:** revert docs commit.  
**Docs:** this package is the docs change.

## Package 2 — Canonical Study / internal Project contract

**Purpose:** formally separate product aggregate from revision storage primitive.  
**Files:** architecture/domain docs, Project/Study module docs, API descriptions.  
**Prerequisite:** owner confirms target.  
**Outcome:** no ambiguity over which object a new feature should extend.  
**Risk:** low if docs/contract only; medium when routes are removed.  
**Tests:** architecture/layer checks; no behavioral change in first PR.  
**Rollback:** revert contract documentation before route retirement.

## Package 3 — Generic Project API consumer inventory and retirement

**Purpose:** remove the second public execution substrate if unsupported.  
**Files:** `routers/projects.py`, `routers/runs.py`, API composition/schemas/tests, web `api.ts`.  
**Prerequisite:** Package 2 and exhaustive caller inventory.  
**Outcome:** one Study/ResearchRun entry path.  
**Risk:** medium-high because unknown external callers are possible.  
**Tests:** OpenAPI contract diff, web build/tests, API integration tests, workbench/smoke, migration compatibility.  
**Rollback:** restore routes during deprecation window.

## Package 4 — Policy/status namespace safety

**Purpose:** prevent evidence and population policy/status concepts from being confused.  
**Files:** evidence/population domain modules and typed call sites.  
**Prerequisite:** OI-24 semantics reviewed.  
**Outcome:** names encode authority/context; no implicit conversion.  
**Risk:** medium because methodology-sensitive.  
**Tests:** full methodology/evidence/population suites; parity where applicable.  
**Rollback:** mechanical rename revert; no data migration if wire/storage values stay unchanged.

## Package 5 — Deep Research frozen-settings completion

**Purpose:** make approved policy values part of immutable run identity.  
**Files:** Deep Research settings/run/reuse/executor composition and tests.  
**Prerequisite:** ADR0022 chunks 43/44 decisions.  
**Outcome:** later setting changes cannot affect existing runs or reuse old work under new methodology.  
**Risk:** high if reuse identity is wrong.  
**Tests:** old-pin/new-pin no-reuse tests, harness compatibility, crash/retry, live refusal, usage/cost tests.  
**Rollback:** disable live route; preserve readable old harnesses.

## Package 6 — Legacy workspace migration closeout

**Purpose:** remove one-off 18.6.6 migration infrastructure after it has served its purpose.  
**Files:** legacy workspace CLI, unit store reader, reference backup/migration docs, workspace states/lineage if approved.  
**Prerequisite:** accepted migration report, zero waiting studies, rollback window closed.  
**Outcome:** product repository no longer carries operational migration code indefinitely.  
**Risk:** high if removed early.  
**Tests:** migration state query, archive/lineage read tests, backup/reference tests.  
**Rollback:** retain tagged/reference implementation; do not destroy source volume in same change.

## Package 7 — Compatibility-route expiry

**Purpose:** keep redirects/notices intentional rather than permanent.  
**Files:** `/app/research`, `/app/projects`, `/classic`, route tests/docs.  
**Prerequisite:** inbound-link/telemetry policy and communication.  
**Outcome:** smaller route surface when safe.  
**Risk:** medium.  
**Tests:** route/redirect tests and deploy smoke.  
**Rollback:** restore static redirects/notices.

## Package 8 — Population/Data Library product connection

**Purpose:** connect existing population authority to the internal product.  
**Files:** population application/authority, new API/UI surface, client Data area.  
**Prerequisite:** client confirmation + operator/approval decisions.  
**Outcome:** no second dataset registry; controlled LIVE revisions from one authority.  
**Risk:** high due data governance.  
**Tests:** immutable versions, promotion, run binding, scope, provenance, import validation.  
**Rollback:** keep registry backend; disable product write surface.

## Package 9 — Canonical Simulation Study workflow

**Purpose:** implement the confirmed 13-phase deterministic simulation process under Study.  
**Prerequisite:** client confirmation and frozen process specification.  
**Outcome:** frozen results and deterministic comparison under the same workflow/provenance architecture as Research.  
**Risk:** high.  
**Tests:** state-machine, frozen inputs/results, deterministic comparison, retry/reuse, report derivation.  
**Rollback:** keep Simulation Study unavailable; never fall back silently to legacy unit.

## Package 10 — Project Memory reusable-artifact contract

**Purpose:** turn Memory from Study index into governed reuse.  
**Prerequisite:** define approved reusable artifact types and scope/lineage rules.  
**Outcome:** searchable history without copying stale truth into new studies.  
**Risk:** medium-high.  
**Tests:** cross-client isolation, version identity, approval/provenance, retrieval determinism.  
**Rollback:** fall back to read-only Study history listing.

## Package 11 — Social Intelligence connection

**Purpose:** connect the shared intelligence concept to the existing data/population authority.  
**Prerequisite:** client confirmation and Package 8 decisions.  
**Outcome:** one data lineage, no parallel societal-intelligence store.  
**Risk:** high.  
**Tests:** provenance, versioning, access, materialisation lineage.  
**Rollback:** keep feature unavailable.

## Package 12 — Project/workflow state cleanup

**Purpose:** remove only obsolete legacy Project/Stage state once the public Project surface is gone.  
**Prerequisite:** Packages 2–3 complete.  
**Outcome:** developers see one execution state machine and a clearly bounded revision state model.  
**Risk:** medium-high.  
**Tests:** workflow recovery, revision carry-forward, artifact reuse, legacy-characterization where still supported.  
**Rollback:** schema/code compatibility migration where needed; do not rewrite frozen run history.

---

# Tests as architectural evidence

## Keep

- layer-check ratchet;
- PostgreSQL concurrency/transaction suite;
- immutable-revision checks;
- paid-call crash/recovery tests;
- methodology/parity fixtures where licensing/reference access permits them;
- Deep Research harness/readability/reuse tests;
- report evidence/fingerprint tests;
- scope/cross-tenant tests.

## Characterization tests

Legacy-characterization tests are not automatically stale. They are valuable when they state the behavior being preserved or intentionally changed. Reclassify/remove one only when the compatibility behavior itself has been retired and the test no longer guards a supported migration/reference contract.

## Avoid

Do not rewrite tests merely to make cleanup easy. In particular, do not weaken frozen-run, evidence, methodology, cost/recovery or scope tests.

---

# Historical compatibility map

| Surface | Classification | Consumer/purpose | Removal condition |
|---|---|---|---|
| 18.6.6 reference unit | read-only reference/parity oracle | methodology/behavior comparison | retain while parity/reference needed |
| `legacy_workspace` / `UnitProjectStore` | temporary migration bridge | unmigrated Study working content | accepted migration, zero waiting, rollback closed |
| `/classic` | compatibility notice | old bookmarks/links | explicit inbound-link retirement |
| `/app/research/*` redirect | route compatibility | old links | explicit inbound-link retirement |
| `/app/projects/*` redirect | route compatibility | old links | explicit inbound-link retirement |
| retired scope-role parsing | persisted compatibility | old stored values, if any | no old value can be loaded |
| Sociomap contract 2 | methodology/version compatibility | historical/parity artifacts | never delete solely for age; retain while artifacts must be readable/reproducible |
| old Deep Research harness versions | frozen-run readability | historical runs | retain readers; execution may refuse stale harness by design |

---

# Deep Research architecture assessment

Canonical trace:

`Study purpose/target -> frozen request -> plan/tracks -> acquisition/evidence -> verification -> synthesis -> brief/result`

## Deterministic/code-owned responsibilities

- request validation/fingerprints/harness identity;
- purpose/target/lineage freeze;
- budgets/caps/reservations;
- transport/admission/robots and host policies;
- reuse keys;
- grounding checks;
- confidence calculation where specified as code;
- durable state/recovery/fan-out coordination;
- evidence provenance;
- run/result persistence;
- settings catalogue validation and, once chunk 43 lands, setting pin/reuse identity.

## Agentic/model responsibilities

- lead planning/delegation within frozen rails;
- investigator query/lead reasoning;
- model readers/triage where allowed;
- verifier reasoning;
- synthesis under the evidence contract.

## Assessment

The outer workflow remains AIA-controlled. There is no evidence that LangGraph/model reasoning has become the authoritative run state machine. The main unfinished governance seam is settings freeze/live approval, not a need to redesign the engine.

Do not simplify away harness versions, readable old versions, reuse fingerprints, request limits, prompt/tool versions or stale-run refusal.

---

# Infrastructure residue assessment

No high-confidence infrastructure residue was identified in the current develop deployment direction.

- Develop EC2/Compose is an accepted deliberate environment.
- The reference unit is deliberately separate and manual.
- PostgreSQL is intentionally both authority and current durable work queue; SQS is not required merely because earlier architecture discussions considered it.
- Production compute remains undecided and should be decided from production SLO/scale requirements, not cleaned up speculatively.

The infrastructure residue worth retiring is the **workspace migration operational path after migration**, not the entire legacy reference oracle.

---

# Dependency graph / high fan-in observations

The highest-risk modules are not necessarily bad; they are central authorities:

- scope resolver/context issuance;
- ProjectRepository/revision graph;
- WorkflowRepository/queue;
- GovernedModelGateway;
- model call journal/usage ledger;
- Study design/workspace repositories;
- Deep Research contracts/reuse identity;
- Sociomap specification/version readers.

These deserve tighter change review because broad portions of the system depend on their contracts. The current lightweight layer checker is an effective protection against upward dependency drift.

---

# Stop-condition answers

1. **Canonical Study representation?** `domain.scope.Study` / `StudyRow`, resolved through `ScopeResolver` into an issued `StudyContext`; product routes are client-first/Study-centric.
2. **Canonical research-run lifecycle?** submit/freeze an immutable Study Design Revision -> `ResearchRuns.start` -> durable `WorkflowRun/StepRun/StepAttempt` -> executor artifacts -> admitted analysis/Sociomap/report -> run-bound retrieval/retry/cancel.
3. **Canonical population source?** versioned population registry/runtime with immutable dataset versions, explicit LIVE promotion and run binding; asset sources are inputs, not parallel authorities.
4. **Where does deterministic methodology live?** domain/application packages (`sociomap`, evidence/analysis, population and other deterministic computation), never as frontend truth.
5. **Where does AI orchestration live?** AIA application/workflow/executor code owns outer orchestration; model/provider execution sits under `GovernedModelGateway`; agent reasoning remains internal to agent tasks.
6. **Deep Research deterministic vs agentic?** code owns freeze, state, budgets, retrieval/admission rails, reuse, grounding/confidence/provenance; agents own lead/investigator/verifier/synthesis reasoning within those rails.
7. **How are model calls recorded/costed?** pre-dispatch durable call journal + append-only usage ledger/reservations under Study scope, including uncertain-settlement recovery.
8. **How are frozen runs reproducible?** immutable Design Revision/request, fingerprints, harness/methodology versions, explicit model/prompt/tool identities and reuse keys; DR settings pin is the remaining planned gap before those settings may govern live runs.
9. **Which NPC implementations remain intentionally?** separate 18.6.6 reference/parity oracle, characterization/parity knowledge, read-only workspace migration reader, explicit methodology compatibility where versioned.
10. **What is `/classic` responsible for?** only a public notice explaining that 18.6.6 is retired from AIA and linking to AIA; it reads no research data.
11. **Which frontend screens still use mocks/transitional paths?** current canonical client/research flow uses real workspace/research APIs. Simulation and Social Intelligence are explicit unavailable shells; Project Memory is partial. One Sociomapping fixture requires local call-site verification before deletion.
12. **Which backend capabilities have no real product consumer?** Population/Data Library is the clearest implemented-but-not-product-connected capability. Simulation’s canonical AIA engine is not implemented rather than hidden. Generic Project API may have no current UI consumer and requires inventory.
13. **Which API surfaces have no current caller?** generic Project/Project-Run routes are the primary candidates; do not remove until current `develop`, workbench, scripts and external consumers are inventoried.
14. **Which concepts have multiple incompatible representations?** product Study vs public/internal Project roles; evidence vs population `FieldPolicy`/`JointStatus`; historical grant documentation vs current membership access; several approval meanings; Project/Stage vs Workflow state layers.
15. **Which config values have multiple sources?** Deep Research policy values intentionally have code proposed defaults plus approved DB versions; this becomes safe only when effective values are frozen into each run. Provider routes/secrets remain deployment-owned by design.
16. **Which state machines overlap?** Study lifecycle, legacy/internal Project lifecycle/stage state and current Workflow run/step/attempt state. Current workflow split is canonical for execution; Project state ownership should narrow as generic Project product surface retires.
17. **Which architecture documentation is stale?** README, `.planning/overview.md`, scope/authorization body, parts of CLAUDE, report plan status, migration status/current-state pointer and several grant-era source comments.
18. **Which compatibility layers can be removed?** migration reader/CLI only after migration acceptance; route redirects and `/classic` only after inbound-link retirement; retired-role parsing only after persisted-value verification; generic Project API only after consumer inventory.
19. **Which cleanup reduces the most future complexity?** correct canonical docs and make Study the sole product aggregate, then remove unsupported generic Project/Run entrypoints while preserving internal immutable revision storage.
20. **What should not be cleaned up?** versioned Sociomap engines/specs, H-Model experimental separation, workflow run/step/attempt split, model gateway/journal/usage ledger, immutable revisions, scope issuance, frozen-run/version compatibility, parity/reference oracle and migration code before its removal conditions.

All twenty questions have an evidence-backed answer; items that still require product/methodology/migration state are explicitly marked as decisions rather than assumed conclusions.

---

# Final recommendation

## Keep

- pure domain/application/infrastructure layering and `layer_check` ratchet;
- PostgreSQL authority and immutable revision model;
- Study-scoped design/workspace repositories;
- `WorkflowRun -> StepRun -> StepAttempt` state split;
- GovernedModelGateway, dispatch journal and append-only usage ledger;
- explicit scope-context issuance;
- versioned/fail-closed Sociomap methodology contracts;
- Deep Research harness/frozen request/reuse/provenance architecture;
- report domain-data vs DOCX-renderer separation;
- separate legacy reference oracle and explicit parity/characterization contracts.

## Connect

- Population/Data Library into the product after governance/client decisions;
- canonical Simulation Study workflow after client confirmation;
- Project Memory to approved reusable artifacts;
- Social Intelligence to the existing population/data authority;
- Deep Research settings into run pins/live readiness (chunks 43–44).

## Consolidate

- product entrypoint around Study rather than Study + generic public Project;
- evidence/population naming so different policy authorities cannot be confused;
- current-state documentation into one coherent architecture narrative;
- frontend/API schemas around Study/ResearchRun as obsolete Project clients retire.

## Remove

Only after the stated verification/removal conditions:

- orphaned frontend generic Project API/types;
- generic Project/Run product routes if no supported consumer remains;
- obsolete grant-era comments/docs immediately;
- legacy workspace migration implementation after migration closeout;
- compatibility redirects/notices after inbound-link retirement;
- unused Sociomapping frontend fixture if call-site verification confirms no consumer.

## Redesign

No wholesale redesign is justified. Deliberate redesign is limited to:

- Project’s public vs internal boundary;
- reusable-artifact/Project Memory contract;
- confirmed Simulation workflow;
- Data Library/Social Intelligence product integration.

## Decide

- confirm Study as sole product aggregate;
- OI-24 evidence/population semantic naming/authority;
- client approval of Simulation/Data Library/Social Intelligence/Memory scope;
- legacy workspace migration completion/rollback close;
- production compute when production SLOs demand a decision;
- remaining Sociomap methodology questions before changing contract-3 formulas;
- Deep Research policy values/sign-offs for live activation.

---

# Ten highest-leverage cleanup actions

1. **Rewrite README + scope/current-state docs to match ADR0019 and Client -> Study reality.** This prevents new work from reintroducing retired architecture.
2. **Approve one explicit architecture statement: Study is the product aggregate; Project is an internal immutable revision/work substrate.**
3. **Inventory and then retire the generic Project/Run public API and matching web client if no supported consumer remains.**
4. **Finish Deep Research settings pinning and live-approval enforcement before live expansion.**
5. **Namespace evidence vs population `FieldPolicy`/`JointStatus`; never merge their semantics by similarity.**
6. **Refresh `.planning/overview.md`, report plan status and CLAUDE executor map from current develop, and make plan front matter the mechanically checked tracker.**
7. **Give every compatibility surface an owner and removal condition; execute the legacy workspace-migration closeout when its conditions are true.**
8. **Connect Population/Data Library through the existing registry only after product/operator approval; do not build a second data authority.**
9. **Implement Simulation as a Study-scoped frozen deterministic workflow only after the client confirms the 13-stage contract; keep the current honest unavailable state until then.**
10. **Define Project Memory as governed artifact reuse before building search; provenance/version/scope must be part of the retrieval contract.**

Do **not** begin major refactoring until this audit is reviewed. The next implementation step should be a documentation/current-state cleanup PR plus the explicit Study-vs-Project architecture decision, followed by a call-site inventory for the generic Project API.