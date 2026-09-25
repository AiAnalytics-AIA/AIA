# PROGRESS

**Single source of truth for what is done, in progress and next.**
Read this at the start of every session, before doing any work.

**Updated:** 2026-09-25 · **Branch:** `feature/research-execution` ·
**Trunk:** `main` (release) · **Integration:** `develop` (deployed, ADR 0009)

This file is the **tracker**. [`docs/migration/status.md`](../docs/migration/status.md)
is the **narrative** — it carries the reasoning, the verification tables and the
bug write-ups. When the two disagree, **this file wins and the narrative is
stale**. Do not open a third backlog anywhere.

Every claim about code carries `file:line @ SHA` or a test name. An unanchored
entry is a **hypothesis**, not a finding.

---

## Completed

| Phase | What | Anchor |
|---|---|---|
| IA | **Client-first IA (ADR 0015)**: `/` → `/app/clients`; Clients → workspace → study → stages; Study.kind; ClientContext; Client Knowledge; the study↔unit binding (OI-58); `/classic` hand-off; no catch-all to the unit. Merged PR #51 @ `4ad5f66`, **live since deploy run 20** (2026-09-24 18:53 UTC, every smoke check ok). Plan archived: [done/client-first-ia.md](plans/done/client-first-ia.md) | `deploy/develop/Caddyfile` · `apps/api/src/aia_api/routers/workspace.py` · OI-58, OI-59, OI-60 |
| 0 | Discovery: both codebases audited, prototype baseline, two latent reference bugs found | `docs/migration/legacy-system-map.md`, `docs/migration/reference-weaknesses.md` @ df294e2 |
| 1 | Production foundation: monorepo, pure domain, PostgreSQL schema, Alembic, typed config with production guards, structured logging with secret redaction, one error contract, Compose, Makefile, CI | `packages/aia_core/src/aia_core/domain/` @ df294e2 |
| 2A | Scope foundation: `Organization → Client → Study`; `StudyContext` issuable only by `ScopeResolver` via a module-private sentinel | `packages/aia_core/src/aia_core/application/scope.py:231` @ df294e2 · `tests/test_scope_isolation.py` |
| 2B | Artifact storage: `ArtifactStore` with S3 / filesystem / memory backends; hash-then-reuse-then-upload-then-verify-then-commit write order enforced | `packages/aia_core/src/aia_core/infrastructure/storage.py` @ df294e2 · `tests/test_artifacts.py` |
| 2C | Authentication boundary: `IdentityProvider` as the only seam; offline-testable Cognito JWT validation; `VerifiedIdentity` carries identity and nothing else | `apps/api/src/aia_api/identity/cognito.py` @ df294e2 · `apps/api/tests/test_identity.py` |
| 3 | Durable workflow engine: `WorkflowRun → StepRun → StepAttempt`, append-only attempts, `FOR UPDATE SKIP LOCKED` claiming, leases, heartbeats, budget reservations under a study-row lock, cooperative cancellation | `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py` @ df294e2 · `tests/test_workflow_engine.py`, `tests/test_workflow_concurrency.py` |
| 3 | Characterization of the legacy job engine: 64 tests describing `job_store.py` before any of it was reimplemented | `packages/aia_core/tests/test_legacy_job_store_characterization.py` @ df294e2 |
| 8 (foundation) | **Population version + import foundation.** Content-addressed `DatasetVersion`, STATIC/LIVE with explicit compare-and-set promotion, lineage, lossless import validation against a hash-pinned 400-field contract, canonical weight resolution with no fallback, one loader (`PopulationRuntime`) issuing an unforgeable `RuntimePopulation`, a `PopulationBinding` recorded per run. Merged in PR #12 after automated verification; no human review comments recorded | `packages/aia_core/src/aia_core/domain/population/` @ `8da7261` · `tests/test_population_*.py` · `.planning/plans/done/population-version-foundation.md` |
| 8 (readiness) | **Population consumption readiness.** Field policy as code over the 400-field dictionary (closed tables; unmapped refused; client use needs positive support); companion-set validation for the 15 v17 companions with the fail-closed `CORE_JOINT_STATUS` gate; population-operator authority closing OI-8; bindings and loaded populations carry policy and joint identity. OI-7 proven archive-blocked; 8-field decision checklist prepared | `domain/population/{policy,companions,authority}.py` · `application/population_authority.py` · `tests/test_population_{policy,companions,authority}.py` · `docs/architecture/population.md` · `.planning/plans/done/population-consumption-readiness.md` |
| — | **Development rules adopted**: `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `.planning/`, `tools/layer_check.sh` blocking in CI | `tools/layer_check.sh` @ this change · `.planning/plans/done/development-rules-adoption.md` |
| 3 | **The worker process** (`apps/worker`): claim → execute through a `StepExecutor` → record, with heartbeats, checkpointed cancellation, per-call metering, lease-fenced writes, clean `SIGTERM` release and in-worker reconciliation. Eight engine defects found and fixed on the way (W1–W8) | `apps/worker/src/aia_worker/worker.py` · `apps/worker/tests/test_worker_processes.py` · `.planning/plans/done/worker-process.md` |


| 9 (core) | **Sociomap deterministic engine**: spec + artifact contract v2; relation coercion, mutual projection, ipsatization, normaliser, object metrics / T-score and both terrain fields ported from the browser and the reference backend; layout **declared** (legacy algorithms refused, AIA row-conditional unfolding implemented, no parity claimed); drag and what-if as layers. F1–F9 vendored and run in every CI job | `packages/aia_core/src/aia_core/domain/sociomap/` · `test_sociomap_{relations,metrics,terrain,layout,engine,contracts,golden_fixtures}.py` · `docs/architecture/sociomapa-deterministic-engine.md` · `.planning/plans/done/sociomap-deterministic-engine.md` |
| 6 | **Evidence governance foundation**: field dictionary as enforced policy (all 400 fields re-derive identically to the reference export), `CORE_JOINT_STATUS` hash-bound certificate, permissible-claim policy, effective-n `SUPPRESS`-by-default support, allowed-metric enum, validation bound to system fingerprint, tier gate, factual layer, `AdmittedClaim` capability enforced by `layer_check` | `packages/aia_core/src/aia_core/domain/evidence/` · `tests/test_evidence_gate_parity.py` · `.planning/plans/done/evidence-governance-foundation.md` |
| 6 | **The eight analysis modules** against those contracts: order, input fingerprints and resume, closed draft schema, 100% prose number coverage, prompts rendered from the enums, results that hold only admitted claims; runner with repair ≤ 2 and pre-flight blocking | `packages/aia_core/src/aia_core/domain/analysis/`, `application/analysis.py` · `tests/test_analysis_runner.py` |
| — | **The `develop` environment — live at <https://aia-develop.art-chain.io/>.** Build identity (`AIA_BUILD_SHA`) and typed `AIA_STORAGE_*` in every process, deployed-environment guards extended (build SHA required, S3 only); api/worker/web images; one-host Compose with Caddy, deploy/backup/restore/smoke scripts and runbook; Terraform root (EC2 + instance role, S3 ×2, ECR ×3, SSM, Cognito + Google, GitHub OIDC role, DLM, alarms, budget); the vertical slice `develop_snapshot` (template → `start_workflow` → `apps/executors` → `ArtifactRepository` → run/artifact routes → `/studies` pages with Cognito PKCE login); idempotent seed; CI on `develop`; `deploy-develop.yml` registered on `main` (PR #32 @ `7f8cb2a`, OI-37 closed) and dispatched by CI after every green `develop` push. Applied 2026-09-23: the host runs `develop` @ `848ec11`; the live smoke passed HTTPS, build SHA, staging guards, readiness, 401s, schema head, worker, S3 round-trip and one completed vertical slice with provenance (PR #35 body). **Not yet green end to end:** the first four *Deploy develop* runs failed, each one step further along (OIDC trust → PR #34; API startup on `AIA_CORS_ORIGINS=""` → PR #35, merged; the smoke check conflating the executing build with a reused artifact's producer → OI-38, fixed in this change); the host runs `848ec11` after run 4 deployed it and only the smoke verdict failed. ADR 0009 accepted (develop only), ADR 0010 proposed. **No model call yet**: the gateway is merged (D12), the Bedrock adapter is Next #5c | `deploy/develop/`, `infra/develop/`, `apps/executors/`, `.github/workflows/deploy-develop.yml` · `apps/executors/tests/`, `apps/api/tests/test_runs_api.py` · `.planning/plans/done/develop-deployment.md` |
| strangler 1 | **Legacy strangler — slice 1, merged in PR #40 @ `764f9f7`** ([plan](plans/legacy-strangler.md)). The 18.6.6 unit is the oracle; AIA replaces one capability at a time behind it. Slice 1 is Phase 0 + both parity harnesses, no port: the oracle endpoint contract (`AIA_LEGACY_REFERENCE_URL` + `_USER`/`_PASSWORD`, `legacy_oracle` fixture, `oracle` marker, `make test-oracle`, CI `oracle-parity` job, `tools/legacy_oracle.py` probe/record/compare with tolerances and volatile-field masks, proven against a gated local stub); the route ledger (`docs/migration/legacy-route-ledger.json`: 153 routes / 162 arms, **14 `PORTING`, 139 `LEGACY`, 0 `PORTED`**, D9 rows marked, every arm anchored to a line of the unit); the UI function ledger (`docs/migration/legacy-ui-functions.json`: the reference's 88 + `normalizer66` as a recorded addition, REF-DISC-3 / OI-40, each row pinned to its source SHA256); the function-level harness (`tools/ui_functions.py` extracts 737/737 declarations as the reference did; `tools/ui_function_runner.mjs` + `ui_function_capture.py` run them under Node) and its first **10 unit-captured fixtures** `U01`–`U10`, of which U01/U02 gate `build_normalizer` / `object_metric` on inputs F5/F6 never used (two reference quirks recorded as intentional differences: an unknown mode/metric id is refused, a `null` rating stays `null` instead of `0`) and U03–U10 await their port. **Phase 0 found the oracle undeployed** (OI-39): *Deploy develop* run 6 built the unit image from a SHA without the unit; run 7 with it waited on the `develop` environment and was cancelled; run 8 @ `764f9f7` built all four images and was refused pushing `aia-legacy-panel` (ECR 403) because `infra/develop/main.tf` `local.images` — the repository set and the deploy role's push grant — still listed three (OI-41, fixed in code, `terraform apply` pending); cloud sessions cannot reach the develop host, so the oracle gate is `NOT_EXECUTED` until the operator applies, re-runs the deploy and provisions the three secrets Measured 2026-09-23 (SQLite, Python 3.12.3, reference repo @ 678e298, Node v22.22.2, **no PostgreSQL, no oracle**): **2286 passed / 135 skipped** across core, API, worker and executors (2177 / 132 before this slice; the 3 new skips are the oracle tests); `mypy --strict` clean across 121 files including the three new tools; `ruff` clean; `layer_check` 42/42; `exposure_check` 7/7 on the staged tree; `parity_status --available reference_repo`: PASS 9 · NOT_EXECUTED 6 · NOT_RUNNABLE 54 · FAIL 0 (`api.http` moved PASS → NOT_EXECUTED: its new oracle gate skipped, which is the honest reading). Not run here: PostgreSQL suites, the legacy-tree parity suite | `.planning/plans/legacy-strangler.md` · `tools/legacy_oracle.py`, `tools/ui_functions.py`, `tools/ui_function_capture.py` · `packages/aia_core/tests/test_legacy_{oracle,route_ledger,ui_functions}.py`, `apps/api/tests/test_legacy_route_claims.py` · `packages/aia_core/tests/fixtures/legacy_ui/` · OI-39, OI-40 |
| — | **`apps/web` dependency advisories cleared.** `npm audit` 13 → 0 (was 1 critical, 8 high, 3 moderate, 1 low): `next` and `eslint-config-next` 16.1.6 → 16.3.6 (16.3.3 is the first release with no advisory; 16.2.12 still has a critical), which brings `sharp` 0.35.4 and its own `postcss` 8.5.23; the rest are in-range lockfile bumps (`@babel/*`, `@humanfs/node`, `ajv`, `baseline-browser-mapping`, `brace-expansion`, `browserslist`, `flatted`, `js-yaml`, `minimatch`, `picomatch`). Lockfile written with npm 11, installed with CI's npm 10 (`npm ci`). One new lint rule answered at the call site, not by changing the navigation (`AGENTS.md` § Next.js). Unblocks OI-2's npm promotion | Measured 2026-09-24 (Node 22.22.2, npm 10.9.7): `npm run lint` clean, `tsc --noEmit` clean, `npm test` 307/307 in 13 files (after merging `develop` @ `0932c5d`, the React rebuild), `tokens:check` / `skin:check` / `check:design` pass; `next build` from a copy of `apps/web` alone succeeds with the same route table as `develop` and the standalone `server.js` at its root; every route of both standalone builds answers with the same status. Not run: the Docker image build (no daemon in the session) | `apps/web/package.json` · `apps/web/package-lock.json` · `apps/web/src/lib/auth.ts` (`logout`) · OI-2 |

**Verified state, evidence governance merged with main @ `121b746` (population,
Sociomap, worker, population readiness) plus the four review fixes (2026-09-23).**
PostgreSQL 16.13 / Python 3.12: **1592 passed / 101 skipped** across core, API and
worker; SQLite: **1564 passed / 129 skipped**; concurrency 22/22 with
`AIA_REQUIRE_POSTGRES=1`; migrations upgrade, `alembic check` no drift, downgrade
to base and back; `mypy --strict` clean across 86 source files; `ruff` clean;
`layer_check` 34/34 (one named exemption pending D8 / OI-24); `exposure_check` 7/7.

**Verified state, population consumption readiness** (PostgreSQL 16.13, Python
3.12.3, core + API): **911 passed / 100 skipped** on PostgreSQL with
`AIA_REQUIRE_POSTGRES=1` (791 / 100 at `8da7261`), **893 / 118** on SQLite (773 /
118), 18 concurrency tests under real contention, `mypy --strict` clean across 55
source files, `layer_check` 18/18, `exposure_check` 7/7, migrations `cadbca872dc5`
and `85637e58c7dd` reversible with no model drift. 36 population parity tests ran
against AIA-reference @ `678e298`; without it they skip (857 / 154 on SQLite).

**Verified state, population foundation** (PostgreSQL 16.13, Python 3.12.3,
core + API): **791 passed / 100 skipped** on PostgreSQL with
`AIA_REQUIRE_POSTGRES=1` (563 / 100 at `17c0a6b`), **773 / 118** on SQLite (546 /
117), 17 concurrency tests under real contention, `mypy --strict` clean across 51
source files, `layer_check` 16/16, `exposure_check` 7/7, migration `1068fd22455d`
reversible with no model drift. The 18 population parity tests ran against
AIA-reference @ `678e298`; without it they skip (755 / 136 on SQLite).

**Verified state, earlier.** Re-measured on PostgreSQL 16 and Python 3.12.12 when the
development rules landed: **402 passed / 94 skipped** on PostgreSQL, **386 passed
/ 110 skipped** on SQLite, 16 concurrency tests passing under real contention
with `AIA_REQUIRE_POSTGRES=1`, `mypy --strict` clean across 32 source files,
`ruff` clean, `layer_check` 12/12, migrations reversible with no model drift.

402 + 94 = 496, matching the baseline recorded at df294e2. The 94 skips are the
parity and characterization tests — the prototype is deliberately not vendored
(OI-1). The extra SQLite skips are the concurrency module, which SQLite cannot
express; CI sets `AIA_REQUIRE_POSTGRES=1` so their absence fails rather than
skips (`.github/workflows/ci.yml:99-108` @ df294e2).

**Worker, re-measured** on PostgreSQL 16.13 / Python 3.12.3 when it landed:
core **526 passed / 100 skipped**, API **114 passed**, concurrency **21 passed**
under `AIA_REQUIRE_POSTGRES=1`, worker **48 passed** including six tests driving
real `python -m aia_worker` processes; SQLite **661 passed / 127 skipped** (the
extra skips are the concurrency and process suites, which SQLite cannot express);
`mypy --strict` clean across 47 source files; `layer_check` 20/20;
`exposure_check` 7/7; `alembic check` clean — no schema change.


**Sociomap engine, measured when it landed** (SQLite, Python 3.12, no
PostgreSQL in the session): **733 passed / 117 skipped**, against 546 / 117 on
the parent commit — +187 tests, no new skips. `mypy --strict` clean across 42
source files, `ruff` clean, `layer_check` 12/12. F4 and F8 are only partly
reproducible and are carried as OI-13 / OI-14; R parity is OI-15.

## In progress

**The `develop` environment is live** (Completed, above; plan archived at
[`plans/done/develop-deployment.md`](plans/done/develop-deployment.md)). What
remains in flight is the first dispatched *Deploy develop* run that ends green.
Run 4 (35869042785, `848ec11`, after PR #35 merged) built, pushed, migrated and
replaced the containers, and 21 of 22 smoke checks passed; the one failure is
the smoke module's own (OI-38): it required the artifact's `runtime_version` to
be the deployed build, while the snapshot executor reuses the artifact by
content fingerprint by design, so the second deploy over the unchanged seed
read back `b5c331f`. This change fixes the check (`apps/executors/smoke.py`,
`test_slice_check_accepts_an_artifact_reused_from_an_earlier_build`); the run
its merge dispatches is the next chance.

| What | State | Anchor |
|---|---|---|
| **PR C — Research execution: Run → Progress → Results under the client** ([plan](plans/research-execution.md), [ADR 0016](../docs/architecture/adr/0016-research-execution-and-model-transmission.md)). Data owner 2026-09-25: a research run is an AIA workflow run pinned to an immutable, Study-scoped Design Revision the browser submits; the `research` workflow (`compile → preflight → run → aggregate → sociomap`, the reference's node keys; `run` is fieldwork); fieldwork is a boundary that **parks** on develop until the Agent Runtime (D1) and runs on a labelled fictional synthetic dataset only in tests and the workbench; Aggregate and Sociomap are the first methods ported (D2; next Donor QC → battery gates → segments); panel-derived microdata may not be transmitted to any model provider until a per-source determination approves it (D3, OI-61) — licence eligibility is a gate of its own beside residency; Sociomap is integrated but not exposed while D6 is open; intervals follow the unit's estimator, not NumPy's stream (OI-62, decided on evidence) | Chunks 0–3 done: plan and ADR (`41932a8`), Design Revisions (`10090db`), the run and its API (`7e0fa7c`), the plan adjustments on evidence (`3215c8b`), 1b — only the design repository writes a Study's design, a `/projects` bypass found while verifying the revision reuse (`d738f53`), 3 — the licence gate beside residency (`ee5aac0`), 4 — compile, readiness, the fieldwork boundary and the fictional source confined to the workbench; research artifacts read only through their run (`765ad86`), 5 — Aggregate ported from the unit, exact against its captures, bounds within its seed spread (OI-62, D5) (`975c791`), 6 — the Sociomap step: the unit's relation matrix, AIA's engine, INTERNAL_ONLY while D6 is open (`155b382`), 7 — the Run, Progress and Results stages in AIA. Next: 8 (workbench and routing proof) | `.planning/plans/research-execution.md` · OI-61, OI-62 |
| **Legacy strangler — slice 2: the develop site shows 18.6.6** — *`/` superseded by ADR 0015 (2026-09-24): the 18.6.6 document is now the hand-off at `/classic`; the gate stands* ([plan](plans/legacy-strangler.md), [ADR 0012](../docs/architecture/adr/0012-legacy-interface-as-product-facade.md)). Data owner's decision 2026-09-23: the product hostname serves the 18.6.6 interface from the unit, behind AIA sign-in, and features are rebuilt behind the same screens. The API's gate (`POST`/`DELETE /api/v1/panel/session`, `GET /api/v1/panel/gate`) admits active organization owners and admins only (`ScopeResolver.authorize_legacy_panel`), refuses cross-origin writes, sends anonymous navigations to `/login`; Caddy routes everything that is not AIA's to the unit after `forward_auth`, stripping the cookie; the web client lost its mock-up and gained `/login` / `/logout`; CI validates the Caddyfile (`develop-host-config`). Proven locally end to end in Chromium against the real 18.6.6 `ui_server.py` (plan, chunk 3). Merged in PR #42 @ `9e42f24`; `terraform apply` for OI-41 done by the operator. Deploy run 10 took the site down (OI-44), fixed in PR #43 @ `5b51640`. **Live since 2026-09-23 23:34 UTC**: *Deploy develop* run 12 (`35933806783`, attempt 2) passed every smoke check, including `legacy: the 18.6.6 unit is healthy`, after the operator set `aia_legacy_data_prefix` (the bundle was already in the ops bucket). Found on the way: OI-42 (refusals' audit rows roll back), OI-43 (three develop-only gate choices) | Measured 2026-09-23 (`make verify`, SQLite, Python 3.12.3, **no PostgreSQL, no oracle, no data bundle**): **2318 passed / 135 skipped** across core (2089 / 129), API (168), worker (43 / 6) and executors (18); 2286 / 135 before this slice. `mypy --strict` clean across 119 files; `ruff` clean; `layer_check` 42/42; `exposure_check` 7/7; web `lint`, `tsc --noEmit` and `build` clean; Caddyfile validated and adapted with Caddy 2.11.4 built from source. Not run here: PostgreSQL suites, the legacy-tree parity suite, the CI job itself (Docker images are pulled on the runner) | `apps/api/src/aia_api/routers/panel.py` · `apps/web/src/app/login/page.tsx` · `deploy/develop/Caddyfile` · `apps/api/tests/test_panel_api.py`, `packages/aia_core/tests/test_legacy_panel_access.py` · OI-42, OI-43 |
| **Interface skin — the AIA design system on the 18.6.6 screens** ([plan](plans/interface-skin.md), [ADR 0013](../docs/architecture/adr/0013-interface-skin-at-the-facade.md), Proposed). Data owner's direction 2026-09-23: the develop deployment is the canonical baseline for every screen; the screens get a major design upgrade from the existing design system; skin now, re-home later; verify against the live oracle. The web client adds one token-generated stylesheet to the document the unit serves at `/`, only when its SHA256 is the pinned `ui_app.html` hash; the unit stays byte-identical, the oracle hostname unskinned, `AIA_INTERFACE_SKIN_ENABLED` off by default. Supersedes the screen chunks of [design-system.md](plans/design-system.md) (V, 4–11); its foundation carries forward | Chunks 0 (plan, ADR), 1 (token foundation on `develop`: `tokens.json`, generator with drift check, self-hosted fonts, identity, contrast 146/146, Vitest 4.1.11) 2 (the hash-pinned injector at `/`, gated, off by default; proven end to end locally through the real Caddyfile and `ui_server.py`) 3 (the variable layer: 29 18.6.6 variables re-pointed at tokens, light only, contrast 164/164) and 4 (shared components, token-only; verified on a specimen of 18.6.6's own templates at 1440/1024 px and under the +35 % Czech stress) done. Merged in PR #45 @ `4dc7966`; **live since deploy run 15** @ `230ee7e` (PR #46, OI-45: Caddy is recreated when its Caddyfile changes; smoke "caddy: running the deployed Caddyfile" ok), confirmed by the data owner 2026-09-24. **Blocked for chunk 5** (live baseline): `legacy.aia-develop.art-chain.io` is refused by the cloud session's egress policy and the `AIA_LEGACY_REFERENCE_*` values are not in its secrets; a local run stops at `/api/bootstrap` without the data bundle | `legacy/npc-panel-18.6.6/app-manifest.json` (`ui_app.html` sha256 `d844dd6f…81eaee`) · `plans/interface-skin.md` |
| **UI workbench + the React re-home** ([plan](plans/ui-workbench.md), [re-home plan](plans/interface-rehome.md), [ADR 0014](../docs/architecture/adr/0014-rebuild-the-interface-in-react.md), Proposed). Data owner 2026-09-24: full UI control, not only the skin, edited quickly and seen by the agent; decided: rebuild the screens in React, area by area, D-L1 extended to the rebuilt screens. Agent sessions cannot reach develop (egress 403), so the workbench runs the real `ui_app.html` locally on a fictional panel with the web client in front, routed by the Caddyfile's `@web` | Workbench chunks 1–2 done: `make ui-workbench` (skinned `:8780`, bare `:8767`, 30 DEMO projects), skin rebuilt on save, `test_ui_workbench.py` 15 passed; `make ui-capture`: 48 screens × 2 widths, bare and skinned, 0 page errors, 0 overflow. Re-home chunks 0–2 and 4 done, 3 in part: `/app` behind the same gate (CI adapt check, smoke), the ledger-checked unit client, the hand-off into the classic interface (`#aia:open=…`), the rail, and **Správa projektů rebuilt in React** (`/app/projects`, ledger `REBUILT`, 0 classic texts missing, 220 parity checks, 7 component tests). Found OI-46: the classic rail prints *Core joint · VALID* as a literal. **Live on develop** (run 16 @ `0932c5d`). Now: **A4 research flow** ([plan](plans/research-flow-rehome.md)) — the data owner's next choice, 2026-09-24; survey done, OI-47 (classic *verify* never renders; *verify*/*next* unreachable) and OI-48 (four aliased unit routes missing from the ledger) recorded; **chunk 1 (foundation) done**: research routes, model, store with visible save state, job runner and panel, `/app/research/<id>/<step>` with the rail, `open@step` hand-off, `make ui-fixtures` (100 tests); **chunk 2 (Zadání) done**: `/app/research/<id>/brief`, 46 parity checks, 9 component tests, capture pair 0 missing; the workbench unit can no longer reach any AI provider (it had found the session's signed-in CLI). **Chunk 3 (Návrh) done**: `/app/research/<id>/plan`, 39 parity checks, 7 component tests, fixture capture pair 0 missing; the open@step hand-off no longer lands on the overview. **PR A complete** (merged, PR #49). **PR B** on `feature/research-flow-b`: survey recorded (OI-49 to OI-55); **chunk 4 (Dotazník) done**: `/app/research/<id>/questionnaire`, 62 parity checks, 10 component tests, fixture capture pair with only the dead button missing. **Chunk 5 (Audience) done**: one project session for all steps (OI-56, a lost-save defect from PR A, fixed); `/app/research/<id>/audience`, 72 parity checks, 8 component tests, capture pair with only the `[object Object]` print missing. **Chunk 6 (Dimenze) done**: `/app/research/<id>/persona`, 45 parity checks, 9 component tests, capture pair 0 missing; the model's *Deep Research* reaches the classic Data Library by a new hand-off verb; OI-57 (a failed audience catalogue re-requested on every draw) recorded. **PR B merged** (PR #50). **PR C paused** by the data owner for the client-first IA (row above); it resumes under the client, at `/app/clients/<client>/research/<study>/run` | `tools/ui_workbench/` · `packages/aia_core/tests/test_ui_workbench.py` |
| **Legacy product unit** (ADR 0011). Strategy change by the data owner: the working 18.6.6 product becomes the day-one baseline and parity oracle. The reference repository runs the audited snapshot as a hash-verified container (its PRs #1–#3) and extracts the product as a frozen unit: 924 code/config files byte-identical to the archive, 245 data files hydrated from the EU ops bucket at start, 69 client-material files excluded. Proven on the operator's machine: unit built, 245/245 hydrated, tree verified 12/12 + 22/22, UI working | This branch: `.gitignore` anchored, `.dockerignore`, `exposure_check` path exemptions with real-client names still enforced, `legacy-panel` compose service, Caddy site + basic-auth gate, data sync in `bin/deploy.sh`, smoke check, fourth image in the deploy workflow, docs. **Blocked on the unit commit** (the generated `legacy/npc-panel-18.6.6/` from the operator's extraction) before merge; decisions D-L1 (client identifiers inside code) and reference D4 (which demos ship) recorded in the ADR | `docs/architecture/adr/0011-vendor-legacy-product-unit.md` · `legacy/README.md` · `deploy/develop/docker-compose.yml` · `tools/exposure_check.sh` |
| **Phase 4 — AI runtime contract** ([plan](plans/ai-runtime-contract.md)) | All 7 chunks on PR #28; Codex findings fixed; `main` merged twice (a15be65: worker, lease fencing, population, evidence governance; b85431f: simulation core). Measured on the latest merge: SQLite 2128 passed / 132 skipped (core + API + worker); PostgreSQL 16 with `AIA_REQUIRE_POSTGRES=1` core 1994 / 104 skipped, API 114, worker 48, concurrency 22; golden fixtures 24 against reference @ 678e298; `mypy --strict` clean (105 files); `layer_check` 36/36; `exposure_check` 7/7; migration `1cd2a5acd29f` single head on `85637e58c7dd`, `alembic check` clean, reversible. Next slice: the AI step executor over `StepContext` (D11) | `application/model_gateway.py` · `infrastructure/ai_call_journal.py` · `tests/test_ai_usage_ledger.py` |
| **Phase 7 — simulation deterministic core.** Typed, pure-Python core driven from a frozen `WorldModel`: reference constants and bounds (versioned `sim-constants-1`), reject-not-clip validation with a per-field record of intentional differences, nearest-correlation projection, calibrate-on-baseline inoculation producing `FS_*` columns, scenario contracts with approval bound to the contract hash, independently modelled variants and their deltas, frozen predictions, write-once truth, eligibility, scoring | All 7 chunks landed; in review (PR #27). Measured 2026-09-23 after merging `main` @ a15be65: PostgreSQL 16 core **1699 passed / 104 skipped**, API **114 passed**, concurrency **22 passed** and worker **48 passed** with `AIA_REQUIRE_POSTGRES=1`; SQLite **1833 passed / 132 skipped**; migrations up, check, down to base and up again clean; `mypy --strict` 93 files and `tsc` clean; `layer_check` 34/34; `exposure_check` 7/7; reference-repo parity **45 passed** (the 3 F13 tests skip, not captured). Not run: the legacy-tree parity suite (archive withheld) | `.planning/plans/simulation-deterministic-core.md` · `docs/architecture/simulation-deterministic-engine.md` · `tests/test_simulation_*.py` |

**Production parity matrix and parity gates** — owner parity-quality. Plan:
[`plans/parity-matrix-and-gates.md`](plans/parity-matrix-and-gates.md).
All seven chunks are written, verified and committed as one change on
`claude/sleepy-keller-kg48oz`. The plan moves to `done/` once the PR merges and
CI has run the new jobs once.

- [x] `docs/migration/parity-matrix.json` — all 78 capabilities, keyed by
      capability id; `test_parity_matrix.py`
- [x] MVP acceptance test defined — `docs/migration/mvp-acceptance.md`
      (`MVP-ACCEPT-1`, criteria AC-01…AC-14); release blocker ≡ named by a criterion
- [x] Golden-fixture pins — `test_golden_fixtures.py`: the checkout is the pinned
      commit, every fixture hashes to its pin, every vendored copy (F1–F9, from
      `main`) is byte-identical to the reference; gates point at the engine's and
      population's own fixture tests
- [x] `tools/parity_status.py` — `PASS` / `FAIL` / `NOT_EXECUTED` /
      `NOT_RUNNABLE` / `NOT_REQUIRED` from JUnit; `test_parity_status_tool.py`
- [x] CI: JUnit from every pytest step, `golden-fixtures` and `parity-status`
      jobs, `|| true` removed from the legacy parity job
- [x] `REF-GAP-SOCIO-R-SMACOF` / `REF-GAP-SIMULATION-WORLD-MODEL` owned —
      OI-15 (already open on `main`, now also in the matrix) / OI-27, `reference_gaps` in the matrix
- [x] Parity status below; findings OI-28, OI-29

## Parity status — this cycle

**Highest-risk unverified capability: `analysis.modules`.** It is on the MVP
path, turns population data into client-facing claims (high-risk R5), and its
eight modules, draft check and admitted-claim results are ported — with **no
reference-backed gate**: nothing compares a module's output, or its
evidence-reference discipline, with the reference. The evidence layer beneath it
*is* reference-backed (`governance.evidence_gates`); the modules on top are not.
The smallest fix is a recovered decision table for the reference's analysis
evidence integrity check (methodology-ledger M17), as
`test_evidence_gate_parity.py` already does for the gates.

Second is `cost.reservations` (implemented, money, R10, no reference-backed gate;
OI-29).

Measured 2026-09-23 in a cloud session (Python 3.12, PostgreSQL 16 and SQLite,
reference repository @ 678e298, **no legacy tree**), on this branch after merging
`main` @ 2dbe2cf (Sociomap engine, population readiness, worker, evidence
governance), by running the CI pytest sequence and then
`tools/parity_status.py --available postgres reference_repo`:

| Verdict | All 78 | MVP blockers (52) |
| --- | ---: | ---: |
| `PASS` | 11 — all `PARTIAL` except `workflow.legacy_dispatch` | 11 |
| `NOT_EXECUTED` | 4 (`pipeline.stages`, `ai.provider_policy`, `workflow.engine`, `governance.evidence_gates` — their legacy-tree gates skip) | 4 |
| `NOT_RUNNABLE` | 54 | 37 |
| `FAIL` | 0 | 0 |
| `NOT_REQUIRED` | 9 | — |

**One MVP blocker is release-ready** (`workflow.legacy_dispatch`), so
`MVP-ACCEPT-1` is `NOT_RUNNABLE`. Golden fixtures: F1–F3, F5–F7, F9–F11 gated
and passing; F8 partially gated (OI-14); F4 refused (OI-13); F12/F13 uncaptured.
Next by risk after the top two: `ai.provider_policy` (R11, legacy gates not
executed), `governance.validation_state` (R12, no reference-backed gate),
`sociomapping.core` (R16; F4 and F8). 68 of 78 capabilities have no confirmed
owner — only A7, A8 and population-data are named in the matrix; the rest carry
their bounded context as an *unconfirmed* workstream.

Re-run each cycle with `make parity-status`, or read the `parity-status` job's
summary; update this section from it, anchored.

## Repository visibility — D5, frozen

**`AiAnalytics-AIA/AIA` is to be PRIVATE.** Product/security decision, taken
2026-09-22 and not open for re-litigation. The production codebase is not for
public distribution, and legacy filenames already expose real client
associations.

**History is preserved.** Going private lowers the urgency of a rewrite to the
point where keeping history is the better trade. Commits stay unless a later
legal or data-owner review requires expunging them.

**The cleanup still applies in full.** Private is not need-to-know and is a
setting somebody can change back: detailed reference material stays out of this
repository, the exposure guard stays blocking, and
`AiAnalytics-AIA/AIA-reference` remains the only home for detail.

✅ **APPLIED 2026-09-22T20:21:38Z**, verified against the API at 20:22:17Z:
`private: true`, `visibility: private`, `forks_count: 0`. Applied by a human — an
agent session cannot, as the proxy refuses repository settings writes.

Surface measured immediately before the change: 0 forks, 0 network, 0 stars,
0 watchers, 0 releases, 0 tags, no Pages, over a ~7-month public window. The
`openapi` workflow artifacts and workflow logs closed with it. What did **not**
close: anonymous clones and third-party indexing during that window leave no API
trace and cannot be measured — which is why the cleanup proceeds anyway.
`docs/migration/public-exposure-remediation.md` §8.

## The reference is a private repository

**`AiAnalytics-AIA/AIA-reference` @ `678e298ad9ca0263da53cc8920d153fdfb956c93`,
tag `reference-18.6.6-gemo-2026-09-11-v1`, is authoritative for every question
about legacy behaviour and methodology.** It is private. The tag
itself points at `90d4c5b`, two commits behind `678e298`; the two commits touch
only `tools/bootstrap_reference.sh` and `tools/verify_reference_inventory.py`,
so every fixture and plan file is identical at both. Parity pins the **commit**
and the SHA256 of every fixture (`docs/migration/parity-matrix.json`), never the
tag. This repository holds pointers only — see
[`docs/migration/reference-source.md`](../docs/migration/reference-source.md).

**`reference-rebuild-local` is COMPLETED / INACTIVE.** Nothing may depend on it
again. Specifically, no future work may rely on:

- a path under `/Users/…`, or any other local machine,
- the local extracted reference tree,
- manual copy/paste of reference material from the human.

A question about the legacy system is answered from the reference repository, or
it is not answered. "The local agent said so" is not an anchor.

### Reference ownership — now cloud-owned

| Item | Owner |
|---|---|
| `REF-GAP-SOCIO-R-SMACOF` | parity-quality + A8 sociomapa-deterministic — **open, OI-15.** R installs in cloud sessions but CRAN is blocked there, and the recipe needs the reference's withheld R wrapper. `r_smacof_unfolding` is refused; no R parity is claimed |
| `REF-GAP-SIMULATION-WORLD-MODEL` | parity-quality + A7 simulation-engine — **open, OI-27.** Blocked on a credential, an ADR 0008 egress route **and** the withheld archive. The deterministic core is built without it (PR #27); the F13 scaffold `test_simulation_parity.py` skips until it lands; status in [simulation-deterministic-engine.md](../docs/architecture/simulation-deterministic-engine.md) §7 |
| `REF-WITHHELD-REFERENCE-ARCHIVE` | data owner / population-data, after the licensing decision. Its destination must satisfy EU residency — [ADR 0008](../docs/architecture/adr/0008-eu-data-residency.md) |

## Next

Ordered. Take the top item unless told otherwise, and **write the plan to
`.planning/plans/<feature>.md` with its chunks before writing code**.

**After the client-first IA (ADR 0015), merged in PR #51.** **Order confirmed by
the data owner, 2026-09-24: PR C → OI-58 → OI-59.** PR C is in progress (above);
the Agent Runtime Foundation follows it, then OI-58, then OI-59.

- **PR C, research execution** ([plan](plans/research-execution.md)), in progress.
- **Agent Runtime Foundation**: Study → AgentRun → AIA Orchestrator →
  ModelGateway → Bedrock, against ADR 0016's seam: the `ai_runtime` fieldwork
  source, analysis and report agents over AIA's deterministic tools. AI fieldwork
  stays off the Czech panel until OI-61 is resolved.
- **OI-58**: port the research store from the unit into AIA's study-scoped
  project, stage by stage; remove `study_workspaces` when no stage reads the unit.
- **OI-59**: open `/app` to members by client and study grant once OI-58 no
  longer needs the owner/admin gate in front of the stages.
- Simulation screens under the client; knowledge ingestion into *Znalosti*.

**Before the research engine can consume the population.** Field policy,
companion validation and OI-8 are done (Completed, above). What remains, with its
owner — the consumer contract is [`docs/architecture/population.md`](../docs/architecture/population.md):

- a. **Archive release** (`REF-WITHHELD-REFERENCE-ARCHIVE`, data owner) to an
  approved EU destination. Unblocks b, c and e. *External dependency.*
- b. **Enrichment** (OI-7) — outcome B proven: port `attach_derived` behind
  `Enricher` against a new EXACT fixture F12 captured from the archive
  ([archive dependency](../docs/migration/population-enrichment-archive-dependency.md)).
  Until then the ANALYSIS view refuses to load. population-data + parity-quality.
- c. **The EU asset source** behind `PopulationAssetSource`, and the first real
  import of all three versions with their 15 companions. population-data.
- d. **Classify the 8 runtime fields** — an 8-row checklist
  ([decision](../docs/migration/population-derived-fields-decision.md)). Data owner +
  analysis-governance.
- e. **Review the client-facing permits** in `RECOMMENDED_USE_POLICY` (115 of 400
  fields may back a measured claim; the reference would have allowed 287).
  analysis-governance. *Not a blocker; the default is the conservative reading.*
- f. **Stage fingerprints from the binding**, not free text (OI-6). research-engine.
- g. **Operator configuration key** at the composition root, when the first route,
  worker or CLI exposes establish/promote. integration-architecture.
- h. **Typed / columnar views** (numeric fields, the M07 age floor) and a
  process-wide cache for workers. population-data, when the research engine needs
  them.

00. **Sign in at <https://aia-develop.art-chain.io/> and look at the 18.6.6
   screens** (data owner): the smoke test proves the gate and the unit's health,
   not what a person sees. Then, optional for the interface but needed for the
   parity gate: the oracle hostname's three `aia_legacy_*` parameters and the
   `AIA_LEGACY_REFERENCE_URL` / `_USER` / `_PASSWORD` repository secrets
   (OI-39). Then slice 3 of [`plans/legacy-strangler.md`](plans/legacy-strangler.md):
   Projects, after the open question on where a legacy-shaped request gets its
   study.
0. ~~**Release once, so the deploy workflow exists** (OI-37).~~ — **done
   2026-09-23.** PR #32 put `deploy-develop.yml` on `main` (`7f8cb2a`, merged
   12:41 UTC); CI on `develop` has dispatched it on every green push since
   (first run 35863981545 at 12:59 UTC). What is still open is the first
   *green* dispatched run (see In progress; OI-38). Then the change to the
   workflow file itself remains inert until released, as a standing rule
   (`AGENTS.md` § GitHub Actions).
1. **Classify the ambiguous legacy brand tokens** (data owner, D4 below). Blocks
   the manifest reduction in
   [`public-exposure-remediation.md`](../docs/migration/public-exposure-remediation.md)
   §3 and the history-rewrite decision in §4.
2. **The generalized metered-cost ledger** — *proposed next platform task*
   (platform-runtime), ahead of OpenTelemetry. Reasoning, so it can be
   overruled on its merits:
   - **It is on Phase 4's critical path; OpenTelemetry is not.** The first
     `ModelGateway` call must write an `AIUsageEvent` somewhere with its
     provider, model, tokens, cost and `provider_request_id`, attributed to
     `Client → Study → Revision → WorkflowRun → Step → Attempt → Call`. Today
     there is nowhere to write it: reservations carry a study, run, step and
     attempt, and nothing finer.
   - **Uncertain spend cannot be resolved without it.** `SETTLED_UNCERTAIN`
     charges the reserved ceiling and keeps the `provider_request_id`, but there
     is no ledger to post the reconciled fact to as a *compensating* entry, so
     every uncertain dollar stays at its ceiling.
   - **Spend is a client-facing number; traces are an operator convenience.** The
     worker and API already log JSON with run/step/attempt ids bound, which
     CloudWatch can search. A handful of users and studies measured in minutes
     do not need spans to be operable at v0.1; they do need every charged dollar
     to be explainable to a client.
   Shape: an append-only `cost_ledger_entries` table (reserve / settle /
   uncertain / release / compensate) written by the same lease-fenced paths the
   worker already uses, `budget_position` derived from it, and `Study.spent_usd`
   kept as a checked projection rather than the source. **Write the plan to
   `.planning/plans/` before code.**
   **Since PR #28:** model calls now have an append-only ledger,
   `ai_usage_events`, with compensating entries for uncertain calls. The
   generalized ledger should extend it or derive from it, not duplicate it, and
   the reconciliation of `Study.spent_usd` it would own is OI-36.
3. **Phase 4, second slice — live transport and the AI step executor.** The
   contract, registry, gateway, ledger and three adapters exist (In progress,
   above). What remains before any model call is real: an approved route per
   data class (D6), a transport (D7), a credential store (D8), a published
   catalog/policy (D9), and a worker executor that drives
   [the contract](../docs/architecture/ai-step-executor-contract.md).
4. **Wire `apps/web` to the real API** and delete `lib/mock.ts`. **Partly
   done:** the live `/studies` pages (Cognito PKCE sign-in, studies → projects →
   runs → artifact) are real and the `/org/*` demo is labelled mock; the demo
   pages and `lib/mock.ts` remain until the design-system rewire replaces them.
   Planned together with the design system in
   [`plans/design-system.md`](plans/design-system.md). Decisions DS-1, DS-2 and
   DS-3 are resolved there. Order: chunks 0–3 (vocabulary, tokens, enum binding,
   primitives + Vitest), then the first real vertical slice (Portfolio → Study →
   workflow state → approval) before any further screens. Cross-context
   dependencies: OI-9 to OI-12.
5. ~~**Terraform for the AWS baseline**~~ — **done for `develop`**
   (`infra/develop/`, ADR 0009). Production compute is still open.
5c. **The Bedrock adapter and the `aws_bedrock` provider** (ADR 0010), as a
   `ProviderAdapter` over a SigV4 `HttpTransport` with recorded fixtures —
   **unblocked** now that PR #28 is on `main` and `develop` (D12) — with the
   route declared in the develop
   configuration and the smoke module's AI check turned from `NOT_RUNNABLE`
   into a real Class C call. Then the human completes ADR 0010's verification
   table and flips it to Accepted.
5a. **Reporting on admitted claims** — `client_report_v2` + `output_pack`
   (authoritative, `report-export-inventory.md` in the reference repository),
   consuming only `AnalysisModuleResult`. Now unblocked: the evidence layer is
   enforceable. Needs the worker (2) and the gateway (3) to run for real.
5b. **`statistics.uncertainty`** — Kish n, donor support and bootstrap intervals
   computed rather than supplied; `EvidenceRow` already refuses a client
   estimate without one. NUMERICAL parity, tolerance 1e-9, needs the archive.

**Removed: "A worker process"** — done; see Completed.

**Removed from this list: "SQS dispatch + reconciler".** It contradicted
[ADR 0002](../docs/architecture/adr/0002-postgresql-authoritative-store.md),
which defers SQS behind a measured trigger and its own ADR: PostgreSQL *is* the
v0.1 queue and workers claim with `FOR UPDATE SKIP LOCKED`. There is no transport
left to build.
6. PostgreSQL row-level security as a second isolation layer.
7. Rate limiting.
8. Delete `src/server.js` + `src/views/` and their root dependencies, once step 4
   removes the last thing that needs them.
9. **Sociomap as a durable job and a route** — **blocked on the shared worker
   (platform-runtime)**; the Sociomap context is paused until the worker execution
   contract lands, and the first path that can emit a Sociomap to a client must
   carry the client-deliverable gate (OI-17). Then:
   `compute_sociomap` executed as a workflow step, its payload stored through
   `ArtifactRepository.put_json`, a study-scoped `GET` that serves it, and the
   `apps/web` sociomapping page rewired to render it (it still implements the
   superseded manual SOP). A 1,000-respondent map takes ~3 s, so it is a job,
   not a request (`docs/architecture/sociomapa-deterministic-engine.md` §9).

## Decisions needed

| # | Decision | Blocks | Anchor |
|---|---|---|---|
| IA-1 | ~~Who may start a study~~ — **resolved 2026-09-24**: a client-level `RESEARCHER` or `LEAD` (`CREATE_STUDY`); nobody else | — | ADR 0015 decision 6 · `test_client_api.py` |
| IA-2 | ~~Order after the client-first IA~~ — **resolved 2026-09-24**: PR C → OI-58 → OI-59 | — | *Next*, above |
| IA-3 | ~~Does the client-first shell become the develop interface~~ — **resolved 2026-09-24**: yes, once its checks are green; `/classic` stays the temporary 18.6.6 escape hatch and reference | — | [plan](plans/client-first-ia.md) · ADR 0015 |
| IA-4 | ~~Commit the files `next dev` regenerates~~ — **resolved 2026-09-24**: only when their diff carries an intentional canonical instruction change | — | `AGENTS.md` § Next.js |
| D1 | ~~Confirm or replace ADR 0005~~ — **resolved**. Split into two statuses: the `ModelGateway` contract is *Accepted*; LiteLLM as its transport stays *Proposed* against seven conditions. Phase 4 is unblocked | — | `docs/architecture/adr/0005-llm-gateway.md` @ 8f545a5 |
| D2 | ~~Confirm ADR 0006~~ — **resolved**. *Accepted — constrained use*; the index had contradicted the file and was corrected | — | `docs/architecture/adr/0006-langgraph-agent-execution.md` @ 8f545a5 |
| D3 | ~~How the reference reaches CI~~ — **split.** Golden fixtures: CI checks out `AiAnalytics-AIA/AIA-reference` at the pinned commit; **needs a human to add a read-only deploy key as the `AIA_REFERENCE_DEPLOY_KEY` secret, then set the variable `AIA_REQUIRE_REFERENCE_REPO=1`**. Legacy-code comparison (the 94 tests): needs the withheld archive, which stays out of CI until its licence decision and an EU-resident home | Golden gates running in CI; the legacy parity tier | `ARCHITECTURE.md §8`, OI-1 |
| D4 | **Which legacy brand tokens name real clients**, and whether the confirmed ones may remain even in a private repository. The candidate list is enumerated in the remediation document, deliberately not duplicated here. Not an engineering judgement | Manifest reduction | `docs/migration/public-exposure-remediation.md` §2 |
| D6 | **Which provider route is approved for which data class.** A vendor/route ADR judged against ADR 0008. Until one exists every route is Class C only, and no client material may reach a model | Any live call on client material | `docs/architecture/adr/0008-eu-data-residency.md` |
| D7 | **Live transport.** An HTTP client in the core package (new dependency), provider SDKs behind the adapters, or LiteLLM if ADR 0005 B's seven conditions are proved. The adapters already take a transport protocol, so this is additive | Any live call | `infrastructure/model_adapters/transport.py` @ this change |
| D8 | **Credential storage.** Secrets Manager reference scheme and/or the planned `api_credentials` table; adapters already hold a reference, never a secret | Live metered calls | `infrastructure/model_adapters/transport.py` `CredentialSource` @ this change |
| D9 | **Who publishes the model catalog, prices and policy versions**, and where the document lives. `parse_model_config` fails closed; there is deliberately no default | research-engine running anything | `domain/ai_models.py` `parse_model_config` @ this change |
| D10 | **Capacity backoff and the per-run hard cap.** The reference retried capacity 5/15/45 s in-call (not ported) and capped per run (`budget_guard.py`, R10, not ported). Both are scheduler/budget semantics — platform-runtime | Parity for `cost.hard_cap` | `docs/architecture/ai-runtime.md` *Failure classification* |
| D11 | **Per-call or per-attempt reservations for AI steps.** The worker's `StepContext` reserves per metered call; `GovernedModelGateway` checks every call against one attempt reservation. The AI step executor needs one answer, shared by ai-runtime and platform-runtime | The AI step executor | `apps/worker/src/aia_worker/executor.py` `StepContext.reserve`; `docs/architecture/ai-step-executor-contract.md` ask 1 |
| D5 | ~~Rewrite history, go private, or accept~~ — **RESOLVED and APPLIED 2026-09-22T20:21:38Z: the repository is PRIVATE, history PRESERVED.** Frozen. Verified `private: true` via the API | — | `docs/migration/public-exposure-remediation.md` § D5, §8 |
| D6 | **Accept, replace or defer the four AIA Sociomap declarations** — dissimilarity target, `aia_rowcond_unfolding_v1`, the map frame, relation-missing `refuse`. Decision package ready with approval fields; methodology owner, not engineering. **The only methodology decision preventing client use** | Any client-facing Sociomap | `docs/architecture/sociomapa-methodology-decision.md` · OI-16 |
| D7 | **Is `RELIGION` a certified matched block?** It is donor-matched and dictionary-eligible, but absent from the certificate's `matched_blocks`, so the claim gate refuses it client-facing. Data owner | Client claims on the five religion fields | `.planning/open-items.md` OI-19 |
| D8 | **One authority for field policy and the joint certificate.** `domain.evidence` and `domain.population` each implement both, with different eligibility (287 vs 115 client measured-claim fields). Pick one; the other consumes it | Consistent claim decisions between a run's recorded policy and the claims admitted from it | `.planning/open-items.md` OI-24 |
| D9 | **Is the Simulation lifecycle in the MVP?** `MVP-ACCEPT-1` is scoped to one Research study. Bringing Simulation in adds `simulation.*` to the blockers and makes OI-27 release-blocking | MVP scope | `docs/migration/mvp-acceptance.md` §6 |
| D10 | **Minimum factors in a world model: 6 or 4.** The reference prompt asks for 6–12, its schema allows 4, and its code tops anything under 4 up to 6. Production declares **6** and rejects fewer. Data owner to confirm or change it; a change bumps `SIMULATION_CONSTANTS_VERSION` | Confirming the simulation bounds as final | `packages/aia_core/src/aia_core/domain/simulation/reference.py` `WorldModelBounds.min_factors` · `test_bounds_are_pinned_to_the_constants_version` |
| D11 | **Port the reference simulation numerics exactly, or accept production-defined v1 as an intentional difference.** Exact `FS_*` parity needs the reference formula bodies (withheld) *and* numpy's PCG64 stream, which the stdlib-only domain layer (`ARCHITECTURE.md §2`) cannot hold without a named exception. Decide once the source is readable | The NUMERICAL half of F13 parity | `docs/architecture/simulation-deterministic-engine.md` §4.3, §5 |
| D12 | ~~**Merge order for the AI runtime.**~~ — **resolved 2026-09-23.** PR #28 (the `ModelGateway` contract) merged into `main` at `676bc1f`, and this change merges `main` into `develop`, so the gateway, its three recorded-exchange adapters and the `ai_usage_events` ledger are on both branches. Next #5c (the Bedrock adapter) is unblocked. Nothing forked ADR 0005 A | Brief items 11–13; Next #5c; ADR 0010 → Accepted | `.planning/plans/done/develop-deployment.md` § Contradictions, C1 |

Open defects and questions live in
[`open-items.md`](open-items.md). Plans in flight live in [`plans/`](plans/);
finished ones move to [`plans/done/`](plans/done/).
