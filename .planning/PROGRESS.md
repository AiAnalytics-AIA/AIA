# PROGRESS

**Single source of truth for what is done, in progress and next.**
Read this at the start of every session, before doing any work.

**Updated:** 2026-09-28 · **Code of record:** `develop` @ `8c13a11` · **Release:** `main` @ `9cf1f58`,
263 commits behind it (ADR 0009). This header names `develop`, never a feature branch: a
branch's state is a row under *Open pull requests* below, so a merge cannot leave it stale.

This file is the **tracker**. [`docs/migration/status.md`](../docs/migration/status.md)
is the **narrative** — it carries the reasoning, the verification tables and the
bug write-ups. When the two disagree, **this file wins and the narrative is
stale**. Do not open a third backlog anywhere.

Every claim about code carries `file:line @ SHA` or a test name. An unanchored
entry is a **hypothesis**, not a finding.

---

## Where the code is — consolidation, 2026-09-27

**Combined cutover candidate:** `integration/phaseout-cutover-review` assembles #74/#77/#78/#82, the latest #74 tests, #75 and #73, plus current `develop`. Settings keeps #75's truthful controls and #82's classic-navigation removal. It is isolated and not release-ready: chunks 10–12 and a validated migration-before-exposure or agreed maintenance transition remain open. [The phase-out plan](plans/legacy-phase-out.md) now requires one cutover instead of separate parent deployments.

**`develop` holds the newest code, and nothing merged anywhere else is missing from
it.** Of the 40 remote branches (10:20 UTC), 25 besides `develop` are fully contained in it
(`git rev-list --count origin/develop..<branch>` = 0). The 14 that are not:

- **In flight at 10:20:** `feature/research-agents` (#63), the two fixes (#64, #65), and
  `claude/trusting-turing-2b9oyl` (the settings page, #67); all four merged since. That branch was started
  from `main`, so it carries `main`'s `7f8cb2a` and had to merge `develop` in: the
  cost of `main` being GitHub's default branch (human action 1, below).
- **`main`**: one commit `develop` lacks, `7f8cb2a`, an older copy of
  `deploy-develop.yml` that `develop` has superseded. It exists only so the
  workflow could be dispatched (OI-37). Release PR #60 (`develop` → `main`) was
  closed unmerged on 2026-09-27.
- **`fix/register-develop-workflow`**: the same `7f8cb2a`.
- **`claude/sharp-newton-csu6fz`** (`b445ac6`, ADR 0008): superseded, because
  `docs/architecture/adr/0008-eu-data-residency.md` is on `develop`.
- **The web-component stack**: `feature/web-vocabulary`, `claude/determined-clarke-q6002c`,
  `feature/design-tokens`, `feature/enum-binding`, `feature/web-primitives` and
  `feature/web-first-slice`.
  - Its PRs (#16, #17, #18, #24) were merged into intermediate branches **after**
    their base had already merged (#15 into `main`), so their content never reached `main`
    or `develop`.
  - Missing on `develop`: `tools/enum_parity_check.py` (the Python ⇄ TypeScript
    enum tripwire), `design/status.ts` / `enums.ts` / `evidence.ts` / `lifecycle.ts`,
    the typed API client `lib/api/`, and `tools/dev_seed.py`.
  - This is deliberate for the screens: [design-system.md](plans/design-system.md)
    chunks 2–3 "return when areas are re-homed".
  - `feature/design-tokens` and `feature/enum-binding` are the tips holding
    all of it. **Do not delete them without an archive tag.**
- `fix/develop-bootstrap` is patch-equivalent to `develop` (`git cherry` `-`).

**Latest release status (2026-09-28):** #83's merge `48bf3e2` replaced the running services, but deploy run `36357121087` failed its slice smoke with `ScopeDenied` while loading the existing seed, before creating a fresh run. Web/API/readiness/worker/storage checks passed. #84 merged as `8c13a11` after all head CI checks passed; its develop CI/deployment is pending. No phase-out candidate has been deployed.

**Last fully successful deployment: `dd27f68` (#72's merge), green** (*Deploy develop* run 35, 16:52 UTC), after CI run
211 passed on the same SHA; #72 changed no product code. Run 34 (`ceee2dc`, #70's merge, 16:08,
after CI run 209), run 32 (`4c4c3dd`, 14:28) and run 33 (`53de110`, 15:11) were green too.
Earlier, runs 29 (`14a124b`, 11:11) and 30 (`85fa951`, 11:33) had replaced every service and
passed every smoke check but `legacy: the 18.6.6 unit is healthy`, read as `starting` 19 s after
the unit was recreated. That was a race, not a broken unit (OI-71); run 31 (`2beafd9`, 11:51)
passed the same one-shot read. PR #70, the fix (smoke waits out the unit's start period), merged
at 15:52 and run 34 is the first deploy that carries it. Run 28 @ `e0edf2a` (10:46) was the first
green deploy of the day. Before it, the host had been on `ff463a3`:
- *Deploy develop* run 26 (PR #59 @ `043b0dd`) failed on the host with
  `bin/lib.sh: line 62: HOME: unbound variable`, and run 27 failed too. PR #64 fixed it
  (merged 10:29, OI-67), and run 28 is the first deploy that carried it.
- Merged today after the outage: #61 (10:08), #54 (10:15), #62 (10:16), #64 (10:29),
  #65 (10:30). CI on `develop` @ `46b7337` crashed with a segmentation fault in the
  OI-69 test (run 36312008574). #65 is its fix.

**CI outage, 09:37–10:05 UTC, resolved.** Jobs failed in about 3 s with no runner
and no log: GitHub reported "recent account payments have failed or your spending
limit needs to be increased" (PR #63 body). The organization moved to GitHub Team,
and runners were assigned again from 10:05 UTC (PR #61's re-run, run 36309896393
attempt 3, green).

### Open pull requests, and the order to merge them

| # | Branch | What | State | Order |
|---|---|---|---|---|
| #64 | `fix/deploy-without-home` | Deploy fails when SSM gives no `HOME` (OI-67) | **Merged** 10:29 | 1 |
| #65 | `fix/api-tests-file-backed-sqlite` | Flaky API tests on shared in-memory SQLite (OI-69) | **Merged** 10:30 | 2 |
| #66 | `chore/consolidate-tracker` | This reconciliation | **Merged** 10:57 (`14a124b`) | 3 |
| #63 | `feature/research-agents` | Native Research design agents on Bedrock | **Merged** 11:17 (`85fa951`); CI green on `614b6a7` | 4, see below |
| #67 | `claude/trusting-turing-2b9oyl` | Settings control panel on `/app/settings`: `GET /settings`, `GET`/`PUT /self-approval`, `PUT /clients/{id}/status` ([plan](plans/done/settings-control-panel.md)) | **Merged** 11:34 (`2beafd9`) | 5 |
| #68 | `chore/record-deploy-and-oi-70` | Records run 28, #63's and #67's merges, OI-70, OI-71 | **Merged** 14:13 (`4c4c3dd`) | 6 |
| #71 | `fix/brief-toggle-test-waits` | BriefStep's toggle test waits for the pressed tile (OI-70) | **Merged** 14:54 (`53de110`) | 7 |
| #69 | `claude/loving-hopper-qiflcr` | Refuse to run a worker on an engine whose threads share one connection | **Merged** 15:52 (`1800c31`) | 8 |
| #70 | `fix/smoke-waits-for-unit-start` | Smoke judges the 18.6.6 unit after its start period (OI-71) | **Merged** 15:52 (`ceee2dc`); deployed by run 34 | 9 |
| #72 | `chore/design-system-reference` | Design-system reference package: the AIA Design System artifact as plain files under `design-system/` (tokens CSS + flat JSON, OFL fonts, identity SVGs, `status-map.md` from the domain enums @ `043b0dd`, three no-build HTML pages); the artifact's 12 screens left out; `FailureClass.RUNTIME_UNAVAILABLE` mapped to `world` pending the design owner. Not wired into `apps/web` | **Merged** 16:36 (`dd27f68`) | 10 |
| #73 | `chore/research-journey-integration-contract` | Job 6, Phase A: the research journey's integration contract ([research-journey.md](../docs/architecture/research-journey.md)), stale claims corrected, the agent-job routes in the API contract check | Draft into `develop` | any time: documents and one CI assertion |
| #74 | `feature/native-research-workspace` | Phase-out increment 1: the research flow on AIA's own state (ADR 0018, chunks 1–6) | Draft into `develop`; the Run stage saves before it submits (`184699c`, its tests `936702f`) | before the migration PR, which is stacked on it |
| #77 | `feature/legacy-workspace-migration` | Phase-out increment 2: the one-off migration of Studies' 18.6.6 content from a copy of the unit's store (ADR 0018 decision 2, chunk 7) | Draft, stacked on #74 | after #74 |
| #78 | `feature/aia-session-gate` | Phase-out increment 3: AIA's own gate in front of `/app`, for any active member (ADR 0018 decision 3, chunk 8) | Draft, stacked on #77 | after #77 |
| #82 | `feature/interface-without-classic` | Phase-out increment 4: the interface without 18.6.6 -- no hand-off, no skin, and what AIA lacks says so (ADR 0018 decision 4, chunk 9) | Draft, stacked on #78 | after #78 |
| #75 | `fix/truthful-ai-controls` | Settings says truthfully what powers AIA's AI: `ai_runtime` from code, each switch from `/config`, never "connected"; the prototype's provider fields as collapsed history ([plan](plans/truthful-ai-controls.md), OI-72; handoffs OI-73–OI-76) | Draft into `develop` | any time: no migration, no new variable. Settings overlap resolved in the combined candidate: #75 controls retained, #82 classic navigation removal retained |
| #83 | `fix/native-tests-config-cache` | Native Research tests no longer inherit a `/config` failure an earlier test cached; `loadConfig()` keeps no failed read (OI-76) | **Merged** into `develop` (`48bf3e2`, 22:45 UTC) | complete |
| #84 | `fix/durable-corrupt-mark` | The API keeps a corrupt artifact's `CORRUPT` mark when it refuses to serve it: the artifact routes' 409 no longer rolls it back, and the agent-job proposal routes answer 409, not 500 (OI-77; its worker half stays open) | **Merged** into `develop` (`8c13a11`, 2026-09-27) | complete; deployment verification pending |

**PR #63 merged (11:17 UTC) as one slice**: native design jobs and reviewed proposals, off
by default. The browser journey it named (enqueue → reload → review → accept → stale
refusal) is still to be recorded. Interpretation, report execution and Deep Research are
the next PRs, each against the plan that already exists for it, not one long branch.
- Its handoff tells the next agent to "continue report-docx.md: #58 supplies… not a
  complete renderer". **#62 is that renderer, merged at 10:16.** Merge `develop` into
  #63 and start the report work at R10/R11, not R4.
- Deep Research is planned in `plans/deep-research.md` (#54, merged 10:15).
- Branch state as #63 recorded it before merging (moved here from above the title in the
  merge that brought `develop` @ `14a124b` in):
  **Research agents — full Study process**: Codex implementation on
  `feature/research-agents`, based on develop after PR #57 merged. [Plan](plans/research-agent-workflows.md).
  The user confirmed that design through results belongs to the original goal.
  Respondent fieldwork is already live. Native proposal jobs and eight actions are
  implemented locally (not deployed); analysis/report execution and owned Deep
  Research remain required work. Contract: [research-agents.md](../docs/architecture/research-agents.md).
  Anchors: `test_research_agent_executor.py`, `test_research_agent_jobs_api.py`,
  `useResearchAgents.test.tsx`, and PostgreSQL
  `test_two_reviewed_design_proposals_cannot_overwrite_each_other`. Search provider:
  Tavily free evaluation proposed; no service approval, account, route or live call.
  Local checks on refreshed develop: core 2,575/100 skipped; API 202; worker 43/6
  skipped; executors 64; web 758; PostgreSQL focused suites 65; types/lint clean,
  layer 62 and exposure 7. Browser journey and CI are still pending.

**Is AIA its own application?** Not yet, and the gap is precise.
- **Standalone:** the back end (API, worker, executors, core). None of it calls the
  unit, and no Compose service `depends_on` it.
- **Not standalone:** the interface at `/app`.
  - Five research stages keep their working content in the unit's store, and every
    research stage page loads the unit's bootstrap and project before it renders
    (OI-58).
  - Simulation, verify/next and the 18.6.6 report exist only in `/classic`.
  - `/app` sits behind the legacy-panel gate, which production refuses
    (`apps/api/src/aia_api/config.py:213-215`), so as wired `/app` cannot be served in
    production (OI-59).
- **Ledgers:** route ledger 153 routes, 0 `PORTED`. Screens 28: 6 `REBUILT`,
  3 `REBUILDING`, 19 `CLASSIC`.
- **The path, in order:** OI-58 (store and bootstrap into AIA), the unit-only reads
  (audience, library, populations, uploads), the design helpers as governed steps
  (#63), the classic-only screens, OI-59 (a gate of its own), then remove
  `legacy-panel` from Compose, Caddy, smoke and deploy. The unit stays only as the
  oracle.

### In progress — phase out 18.6.6 from the product ([plan](plans/legacy-phase-out.md), [ADR 0018](../docs/architecture/adr/0018-aia-runs-without-18-6-6.md))

| Increment | Branch | State |
|---|---|---|
| 1. Native research workspace | `feature/native-research-workspace` ([#74](https://github.com/AiAnalytics-AIA/AIA/pull/74), draft) | Chunks 1–6 done: working content in AIA (`GET`/`PUT /studies/{id}/workspace/content`, migration `5b1d0f3e9a21`, stale saves refused), the web store and every stage on it, no unit job runner; brief attachments in AIA storage (`/workspace/attachments`, text read as the unit read it, `test_document_text.py`); the questionnaire import and template in AIA (`/workspace/questionnaire-import`, `-template`, compared with the unit's import on 24 files); Audience and Dimenze call nothing of the unit (the client's knowledge for dimensions; panel-derived features say they are not in AIA), and every stage's tests fail on a unit URL. Run saves the working copy before it submits it as a design, and submits nothing over a conflict or a failed save (`184699c`, `936702f`; `ExecutionSteps.test.tsx` › Run). Verified in Chromium on AIA alone (`make ui-workbench-aia`: the unit not started): `ui-workspace` and `ui-research` pass, no request to the unit. Draft PR open |
| 2. Migration of bound content | `feature/legacy-workspace-migration` ([#77](https://github.com/AiAnalytics-AIA/AIA/pull/77), draft, stacked on #74) | Chunk 7 done: `python -m aia_executors.legacy_workspace` migrates each `AWAITING_MIGRATION` Study from a copy of the unit's store and files, as a named person through their grants, every revision one for one, files into AIA storage or reported, validated against the unit's own hashes, dry run unless `--apply`, missing projects decided only with `--recover-missing` (`test_workspace_migration.py`, `test_legacy_workspace.py`). **Not run on develop**: an operator step (`deploy/develop/README.md` § Migrating 18.6.6 content) |
| 3. AIA's own gate for `/app` | `feature/aia-session-gate` ([#78](https://github.com/AiAnalytics-AIA/AIA/pull/78), draft, stacked on #77) | Chunk 8 done: `/app` behind `GET /api/v1/session/gate`, any active member with an AIA session (`POST /api/v1/session`, audited), independent of every legacy setting and of the retired `/app` switch; `/classic` and the unit keep the owner/admin panel gate until they leave (OI-59). Tests: `test_session_api.py`, `test_caddy_routes.py`, `login/page.test.tsx`, `lib/session.test.ts` |
| 4. Interface without 18.6.6 | `feature/interface-without-classic` ([#82](https://github.com/AiAnalytics-AIA/AIA/pull/82), draft, stacked on #78) | Chunk 9 done: nothing hands off to 18.6.6 (ADR 0018 decision 4). The skin, `/interface-document`, `handoff.js`, `ClassicLink`, the classic projects screens and `src/unit/` are removed; `/classic` is the web client's public page saying 18.6.6 is gone; the simulation, the Data Library, verify/next, the report and the Sociomap's tools say they are not in AIA; `/login` opens AIA's session only. `tools/caddy_routes.py` fails a Caddyfile that serves the 18.6.6 document again. Screens 28: 5 `REBUILT`, 3 `REBUILDING`, 4 `SUPERSEDED`, 16 `NOT_IN_AIA`. Tests: `NotInAia.test.tsx`, `interface-screens.test.ts`, `test_caddy_routes.py`, `lib/session.test.ts` |
| 5. Deployment without 18.6.6 | `feature/deploy-without-legacy` | not started |

### Human actions (repository settings; an agent session cannot make them)

1. **Make `develop` the default branch** (Settings → General → Default branch).
   `main` is the default today (`git ls-remote --symref origin HEAD` → `main` @
   `9cf1f58`, 2026-09-23). Every new clone, agent session and *New pull request*
   therefore starts four days and 208 commits back, as `claude/trusting-turing-2b9oyl`
   did. `main` stays the release branch. `deploy-develop.yml` is already on
   `develop`, so dispatch keeps working, and later changes to it take effect without
   a release (OI-37).
2. **Protect `develop` and `main`**, as [`infra/develop/README.md`](../infra/develop/README.md)
   § Human actions items 10–11 describe. Require the CI checks before merge (OI-32).
   The organization moved to GitHub Team on 2026-09-27, and Team is the plan that
   offers protection rules on a private repository.
3. **Watch Actions usage** (Settings → Billing → budgets and alerts) so a quota
   stop is an email, not a morning of red PRs.
4. **Release `develop` → `main`** once #64 has merged and a deploy is green. PR #60,
   the previous attempt, was closed unmerged.
5. **After the open PRs land, delete the 24 contained feature branches**: the 25 above,
   less `coordination/agent-status`, which CLAUDE.md §5 keeps for agents' status files.
   Tag the web-component stack first (`feature/design-tokens`, `feature/enum-binding`),
   then delete it.

## Completed

| Phase | What | Anchor |
|---|---|---|
| Repair | **PR #57 merged** @ `ff463a3`, 2026-09-27 (deploy run 25 green): saved Research projects survive a restart (OI-66: an edited `state_seed` is kept, a new one installed atomically), live SQLite backups include WAL (export off by default), and the Claude Code / direct API connection controls are retired in favour of Bedrock runtime metadata. Recovery of the affected working copies is operational and still open (OI-66); the fix sits in a hand-edited file of the frozen unit (OI-68) | `legacy/npc-panel-18.6.6/runtime/hydrate_data.py` · `test_legacy_state_hydration.py`, `test_legacy_state_backup.py` · [bedrock-settings-cleanup.md](plans/done/bedrock-settings-cleanup.md) |
| Host | **No registry token at rest on the develop host.** `ecr_login` pulls through Amazon's ECR credential helper (instance role), installs the Ubuntu package on first use, removes the token `docker login` had stored unencrypted in root's `~/.docker/config.json`, and turns the helper's plain-text cache off. If the package cannot be installed, the deploy falls back to `docker login` and logs a warning. No Terraform or user-data change (a changed `user_data` would stop and start the host on apply) | `deploy/develop/bin/lib.sh` › `ecr_login` · `packages/aia_core/tests/test_develop_registry_credentials.py` |
| Agent Runtime | **PR #56 merged and deployed** at `0310091`, 2026-09-26. CI `36234914562` and deploy `36235378083` passed; running worker SHA verified. ADR 0010 human approval recorded for fictional Class C on develop only, retention unspecified. Verified EU prices: input $3.30 / output $16.50 per million tokens. Audited Terraform apply removed only the unused eu-central-2 model grant. Live acceptance study completed: five steps succeeded; 20 primary calls; $0.2303301 ledger cost against $2; all reservations settled. | `apps/executors/src/aia_executors/ai_runtime.py` @ `0310091` · [activation evidence](../docs/architecture/bedrock-develop-activation-2026-09-26.md) · OI-63–65 |
| PR C | **Research execution (ADR 0016)**: Design Revisions, the `research` workflow (`compile → preflight → run → aggregate → sociomap`), the honest park at fieldwork, Aggregate and the internal Sociomap, the Run/Progress/Results stages, the workbench proof. Merged PR #52 @ `b3bd42f`, CI green. Plan: [research-execution.md](plans/done/research-execution.md) | `apps/executors/src/aia_executors/research.py` · OI-61, OI-62 |
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
| — | **The `develop` environment — live at <https://aia-develop.art-chain.io/>.** Build identity (`AIA_BUILD_SHA`) and typed `AIA_STORAGE_*` in every process, deployed-environment guards extended (build SHA required, S3 only); api/worker/web images; one-host Compose with Caddy, deploy/backup/restore/smoke scripts and runbook; Terraform root (EC2 + instance role, S3 ×2, ECR ×3, SSM, Cognito + Google, GitHub OIDC role, DLM, alarms, budget); the vertical slice `develop_snapshot` (template → `start_workflow` → `apps/executors` → `ArtifactRepository` → run/artifact routes → `/studies` pages with Cognito PKCE login); idempotent seed; CI on `develop`; `deploy-develop.yml` registered on `main` (PR #32 @ `7f8cb2a`, OI-37 closed) and dispatched by CI after every green `develop` push. Applied 2026-09-23: the host runs `develop` @ `848ec11`; the live smoke passed HTTPS, build SHA, staging guards, readiness, 401s, schema head, worker, S3 round-trip and one completed vertical slice with provenance (PR #35 body). Later deploy runs passed all smoke checks: the original facade was live by run 12 and the client-first interface by run 20. The earlier run-4 smoke failure is historical (OI-38), not the current deployment verdict. ADR 0009 accepted (develop only). Model calls began with PR #56 (the Agent Runtime row above) | `deploy/develop/`, `infra/develop/`, `apps/executors/`, `.github/workflows/deploy-develop.yml` · `apps/executors/tests/`, `apps/api/tests/test_runs_api.py` · `.planning/plans/done/develop-deployment.md` |
| strangler 1 | **Legacy strangler — slice 1, merged in PR #40 @ `764f9f7`** ([plan](plans/legacy-strangler.md)). The 18.6.6 unit is the oracle; AIA replaces one capability at a time behind it. Slice 1 is Phase 0 + both parity harnesses, no port: the oracle endpoint contract (`AIA_LEGACY_REFERENCE_URL` + `_USER`/`_PASSWORD`, `legacy_oracle` fixture, `oracle` marker, `make test-oracle`, CI `oracle-parity` job, `tools/legacy_oracle.py` probe/record/compare with tolerances and volatile-field masks, proven against a gated local stub); the route ledger (`docs/migration/legacy-route-ledger.json`: 153 routes / 162 arms, **14 `PORTING`, 139 `LEGACY`, 0 `PORTED`**, D9 rows marked, every arm anchored to a line of the unit); the UI function ledger (`docs/migration/legacy-ui-functions.json`: the reference's 88 + `normalizer66` as a recorded addition, REF-DISC-3 / OI-40, each row pinned to its source SHA256); the function-level harness (`tools/ui_functions.py` extracts 737/737 declarations as the reference did; `tools/ui_function_runner.mjs` + `ui_function_capture.py` run them under Node) and its first **10 unit-captured fixtures** `U01`–`U10`, of which U01/U02 gate `build_normalizer` / `object_metric` on inputs F5/F6 never used (two reference quirks recorded as intentional differences: an unknown mode/metric id is refused, a `null` rating stays `null` instead of `0`) and U03–U10 await their port. **Phase 0 found the oracle undeployed** (OI-39): *Deploy develop* run 6 built the unit image from a SHA without the unit; run 7 with it waited on the `develop` environment and was cancelled; run 8 @ `764f9f7` built all four images and was refused pushing `aia-legacy-panel` (ECR 403) because `infra/develop/main.tf` `local.images` — the repository set and the deploy role's push grant — still listed three (OI-41, fixed in code, `terraform apply` pending); cloud sessions cannot reach the develop host, so the oracle gate is `NOT_EXECUTED` until the operator applies, re-runs the deploy and provisions the three secrets Measured 2026-09-23 (SQLite, Python 3.12.3, reference repo @ 678e298, Node v22.22.2, **no PostgreSQL, no oracle**): **2286 passed / 135 skipped** across core, API, worker and executors (2177 / 132 before this slice; the 3 new skips are the oracle tests); `mypy --strict` clean across 121 files including the three new tools; `ruff` clean; `layer_check` 42/42; `exposure_check` 7/7 on the staged tree; `parity_status --available reference_repo`: PASS 9 · NOT_EXECUTED 6 · NOT_RUNNABLE 54 · FAIL 0 (`api.http` moved PASS → NOT_EXECUTED: its new oracle gate skipped, which is the honest reading). Not run here: PostgreSQL suites, the legacy-tree parity suite | `.planning/plans/legacy-strangler.md` · `tools/legacy_oracle.py`, `tools/ui_functions.py`, `tools/ui_function_capture.py` · `packages/aia_core/tests/test_legacy_{oracle,route_ledger,ui_functions}.py`, `apps/api/tests/test_legacy_route_claims.py` · `packages/aia_core/tests/fixtures/legacy_ui/` · OI-39, OI-40 |
| — | **`apps/web` dependency advisories cleared.** `npm audit` 13 → 0 (was 1 critical, 8 high, 3 moderate, 1 low): `next` and `eslint-config-next` 16.1.6 → 16.3.6 (16.3.3 is the first release with no advisory; 16.2.12 still has a critical), which brings `sharp` 0.35.4 and its own `postcss` 8.5.23; the rest are in-range lockfile bumps (`@babel/*`, `@humanfs/node`, `ajv`, `baseline-browser-mapping`, `brace-expansion`, `browserslist`, `flatted`, `js-yaml`, `minimatch`, `picomatch`). Lockfile written with npm 11, installed with CI's npm 10 (`npm ci`). One new lint rule answered at the call site, not by changing the navigation (`AGENTS.md` § Next.js). Unblocks OI-2's npm promotion | Measured 2026-09-24 (Node 22.22.2, npm 10.9.7): `npm run lint` clean, `tsc --noEmit` clean, `npm test` 307/307 in 13 files (after merging `develop` @ `0932c5d`, the React rebuild), `tokens:check` / `skin:check` / `check:design` pass; `next build` from a copy of `apps/web` alone succeeds with the same route table as `develop` and the standalone `server.js` at its root; every route of both standalone builds answers with the same status. Not run: the Docker image build (no daemon in the session) | `apps/web/package.json` · `apps/web/package-lock.json` · `apps/web/src/lib/auth.ts` (`logout`) · OI-2 |
| Agent Runtime (build) | **Agent Runtime Foundation — AI respondent fieldwork** ([plan](plans/done/agent-runtime-foundation.md)). The `ai_runtime` source of the `research_fieldwork` step: AI respondents on a fictional roster, through `GovernedModelGateway` over ADR 0010's Bedrock route, answers drawn by code; Aggregate and the Sociomap unchanged. D11 resolved (one reservation per request). First live path: fictional Class C only (OI-63); panel lineage refused (OI-61); ADR 0010 accepted for fictional Class C on develop, 2026-09-26 — *merged; the state as last recorded in progress:* Chunks 0–1 Bedrock adapter, signer, live transport (`2e8beb5`); 2 gateway preflight (`125a8be`); 3 response process + factual layer against the unit (`b2cc9ff`); 4 the respondent agent (`9b7fa9b`); 5 the bridge and producer, 26 end-to-end tests (`dec2fd1`); 6 deployable configuration, the grant narrowed to six regions (`2840d34`); 7–8 proof and documents (`539085b`); review fix: a TLS failure after sending is UNKNOWN, not NOT_SENT (`4d99e6a`, `test_an_ssl_failure_after_sending_needs_recovery_and_is_never_settled_as_free`); `develop` @ `2990157` (PR #53, DOCX report) merged in (`a44bc13`, extras conflict only). Measured before the merge: `make verify` exit 0 (SQLite core 2388 / API 199 / worker 43 / executors 56, web 741, layer_check 61, exposure_check 7); PostgreSQL 16 with `AIA_REQUIRE_POSTGRES=1` core 2410 / API 199 / worker 49 / executors 56, `alembic check` clean (no migration); legacy parity against the vendored unit 99 passed, 3 failed that need the archive (manifest vs extracted tree, the real panel). Not run: a live Bedrock call (not authorised), `terraform validate` (registry refused), the archive-backed parity tests (no archive) | `apps/executors/src/aia_executors/ai_fieldwork.py` · `apps/executors/tests/test_ai_fieldwork.py` · OI-63–65 |
| strangler 2 | **Legacy strangler — slice 2: the develop site shows 18.6.6** — *`/` superseded by ADR 0015 (2026-09-24): the 18.6.6 document is now the hand-off at `/classic`; the gate stands* ([plan](plans/legacy-strangler.md), [ADR 0012](../docs/architecture/adr/0012-legacy-interface-as-product-facade.md)). Data owner's decision 2026-09-23: the product hostname serves the 18.6.6 interface from the unit, behind AIA sign-in, and features are rebuilt behind the same screens. The API's gate (`POST`/`DELETE /api/v1/panel/session`, `GET /api/v1/panel/gate`) admits active organization owners and admins only (`ScopeResolver.authorize_legacy_panel`), refuses cross-origin writes, sends anonymous navigations to `/login`; Caddy routes everything that is not AIA's to the unit after `forward_auth`, stripping the cookie; the web client lost its mock-up and gained `/login` / `/logout`; CI validates the Caddyfile (`develop-host-config`). Proven locally end to end in Chromium against the real 18.6.6 `ui_server.py` (plan, chunk 3). Merged in PR #42 @ `9e42f24`; `terraform apply` for OI-41 done by the operator. Deploy run 10 took the site down (OI-44), fixed in PR #43 @ `5b51640`. **Live since 2026-09-23 23:34 UTC**: *Deploy develop* run 12 (`35933806783`, attempt 2) passed every smoke check, including `legacy: the 18.6.6 unit is healthy`, after the operator set `aia_legacy_data_prefix` (the bundle was already in the ops bucket). Found on the way: OI-42 (refusals' audit rows roll back), OI-43 (three develop-only gate choices) — *merged; the state as last recorded in progress:* Measured 2026-09-23 (`make verify`, SQLite, Python 3.12.3, **no PostgreSQL, no oracle, no data bundle**): **2318 passed / 135 skipped** across core (2089 / 129), API (168), worker (43 / 6) and executors (18); 2286 / 135 before this slice. `mypy --strict` clean across 119 files; `ruff` clean; `layer_check` 42/42; `exposure_check` 7/7; web `lint`, `tsc --noEmit` and `build` clean; Caddyfile validated and adapted with Caddy 2.11.4 built from source. Not run here: PostgreSQL suites, the legacy-tree parity suite, the CI job itself (Docker images are pulled on the runner) | `apps/api/src/aia_api/routers/panel.py` · `apps/web/src/app/login/page.tsx` · `deploy/develop/Caddyfile` · `apps/api/tests/test_panel_api.py`, `packages/aia_core/tests/test_legacy_panel_access.py` · OI-42, OI-43 |
| Unit | **Legacy product unit** (ADR 0011). Strategy change by the data owner: the working 18.6.6 product becomes the day-one baseline and parity oracle. The reference repository runs the audited snapshot as a hash-verified container (its PRs #1–#3) and extracts the product as a frozen unit: 924 code/config files byte-identical to the archive, 245 data files hydrated from the EU ops bucket at start, 69 client-material files excluded. Proven on the operator's machine: unit built, 245/245 hydrated, tree verified 12/12 + 22/22, UI working — *merged; the state as last recorded in progress:* This branch: `.gitignore` anchored, `.dockerignore`, `exposure_check` path exemptions with real-client names still enforced, `legacy-panel` compose service, Caddy site + basic-auth gate, data sync in `bin/deploy.sh`, smoke check, fourth image in the deploy workflow, docs. **Blocked on the unit commit** (the generated `legacy/npc-panel-18.6.6/` from the operator's extraction) before merge; decisions D-L1 (client identifiers inside code) and reference D4 (which demos ship) recorded in the ADR | `docs/architecture/adr/0011-vendor-legacy-product-unit.md` · `legacy/README.md` · `deploy/develop/docker-compose.yml` · `tools/exposure_check.sh` |
| 4 | **Phase 4 — AI runtime contract** ([plan](plans/done/ai-runtime-contract.md)) — *merged; the state as last recorded in progress:* All 7 chunks on PR #28; Codex findings fixed; `main` merged twice (a15be65: worker, lease fencing, population, evidence governance; b85431f: simulation core). Measured on the latest merge: SQLite 2128 passed / 132 skipped (core + API + worker); PostgreSQL 16 with `AIA_REQUIRE_POSTGRES=1` core 1994 / 104 skipped, API 114, worker 48, concurrency 22; golden fixtures 24 against reference @ 678e298; `mypy --strict` clean (105 files); `layer_check` 36/36; `exposure_check` 7/7; migration `1cd2a5acd29f` single head on `85637e58c7dd`, `alembic check` clean, reversible. Next slice: the AI step executor over `StepContext` (D11) | `application/model_gateway.py` · `infrastructure/ai_call_journal.py` · `tests/test_ai_usage_ledger.py` |
| 7 (core) | **Phase 7 — simulation deterministic core.** Typed, pure-Python core driven from a frozen `WorldModel`: reference constants and bounds (versioned `sim-constants-1`), reject-not-clip validation with a per-field record of intentional differences, nearest-correlation projection, calibrate-on-baseline inoculation producing `FS_*` columns, scenario contracts with approval bound to the contract hash, independently modelled variants and their deltas, frozen predictions, write-once truth, eligibility, scoring — *merged; the state as last recorded in progress:* All 7 chunks landed; in review (PR #27). Measured 2026-09-23 after merging `main` @ a15be65: PostgreSQL 16 core **1699 passed / 104 skipped**, API **114 passed**, concurrency **22 passed** and worker **48 passed** with `AIA_REQUIRE_POSTGRES=1`; SQLite **1833 passed / 132 skipped**; migrations up, check, down to base and up again clean; `mypy --strict` 93 files and `tsc` clean; `layer_check` 34/34; `exposure_check` 7/7; reference-repo parity **45 passed** (the 3 F13 tests skip, not captured). Not run: the legacy-tree parity suite (archive withheld) | `.planning/plans/done/simulation-deterministic-core.md` · `docs/architecture/simulation-deterministic-engine.md` · `tests/test_simulation_*.py` |

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

**The `develop` environment is live** (see *Where the code is* for what is deployed). Research execution and Bedrock respondent fieldwork are merged, and the fictional Class C acceptance completed on 2026-09-26 (Completed, Agent Runtime). Native design proposals are merged (PR #63) and remain off by default. Evidence-backed interpretation/report execution and owned Deep Research remain required for the complete agent workflow.

| What | State | Anchor |
|---|---|---|
| **The complete research journey — split across six jobs** (user's scope addendum, 2026-09-27). The phase-out owner: the native workspace, migration, `/app` authorization, `/classic` removal, deployment separation, the final legacy-offline acceptance, OI-58 and OI-59; the former Job 2 is retired into it. Job 1: native AI settings. Job 3: evidence-backed analysis. Job 4: reports. Job 5: Deep Research. Job 6: the research graph, executor, endpoint and results integration, and a reusable recorded scenario. Independence of the supported workflows and completion of the research process are reported apart | **Job 6, Phase A done** on `chore/research-journey-integration-contract` (PR #73, draft): the contract — every product stage and the reference's 24 nodes marked implemented, replacement or gap, with owner and anchor; interfaces, shared files, INT-1, four acceptance levels, blocked paths; stale claims corrected (§10); the agent-job routes asserted by the API contract check. **Phase B waits on candidate PRs.** The PO's first, draft #74 (`7b9e9dc`), is checked against the contract. It delivers the native draft the Run stage submits; the missing save found at `7b9e9dc` is fixed at `184699c` (contract §4.2). By 18:05 UTC #75 (J1), #76 (J3) and #77 (PO) had opened too; J4 and J5 had no branch. #75 and this PR both numbered new entries from OI-72. When #83 put OI-76 on `develop` (22:45 UTC), this PR's entries became OI-78 and OI-79 under the contract's §5 rule; #84 merged OI-77 at 23:09 UTC; #75 (OI-72–OI-75) keeps its numbers until it merges. No acceptance line is MET in the recorded column. **2026-09-28 direction:** INT-1 is synthetic test data, not a product client category; actual production-study material determines egress classification (OI-63, OI-79), whose code fix remains open | [research-journey.md](../docs/architecture/research-journey.md) · [plan § Integration](plans/research-agent-workflows.md) · OI-64, OI-78, OI-79 |
| **Interface skin — the AIA design system on the 18.6.6 screens** ([plan](plans/interface-skin.md), [ADR 0013](../docs/architecture/adr/0013-interface-skin-at-the-facade.md), Accepted 2026-09-24; only chunk 6, per-area passes, remains). *Superseded by increment 4 of the phase-out (ADR 0018 decision 4, `feature/interface-without-classic`): the 18.6.6 document is no longer served and the skin is removed with it; this row is history.* Data owner's direction 2026-09-23: the develop deployment is the canonical baseline for every screen; the screens get a major design upgrade from the existing design system; skin now, re-home later; verify against the live oracle. The web client adds one token-generated stylesheet to the document the unit serves at `/`, only when its SHA256 is the pinned `ui_app.html` hash; the unit stays byte-identical, the oracle hostname unskinned, `AIA_INTERFACE_SKIN_ENABLED` off by default. Supersedes the screen chunks of [design-system.md](plans/design-system.md) (V, 4–11); its foundation carries forward | Chunks 0 (plan, ADR), 1 (token foundation on `develop`: `tokens.json`, generator with drift check, self-hosted fonts, identity, contrast 146/146, Vitest 4.1.11) 2 (the hash-pinned injector at `/`, gated, off by default; proven end to end locally through the real Caddyfile and `ui_server.py`) 3 (the variable layer: 29 18.6.6 variables re-pointed at tokens, light only, contrast 164/164) and 4 (shared components, token-only; verified on a specimen of 18.6.6's own templates at 1440/1024 px and under the +35 % Czech stress) done. Merged in PR #45 @ `4dc7966`; **live since deploy run 15** @ `230ee7e` (PR #46, OI-45: Caddy is recreated when its Caddyfile changes; smoke "caddy: running the deployed Caddyfile" ok), confirmed by the data owner 2026-09-24. **Blocked for chunk 5** (live baseline): `legacy.aia-develop.art-chain.io` is refused by the cloud session's egress policy and the `AIA_LEGACY_REFERENCE_*` values are not in its secrets; a local run stops at `/api/bootstrap` without the data bundle | `legacy/npc-panel-18.6.6/app-manifest.json` (`ui_app.html` sha256 `d844dd6f…81eaee`) · `plans/interface-skin.md` |
| **UI workbench + the React re-home** ([plan](plans/ui-workbench.md), [re-home plan](plans/interface-rehome.md), [ADR 0014](../docs/architecture/adr/0014-rebuild-the-interface-in-react.md), Proposed). *Since increment 4 of the phase-out (ADR 0018): no skin and no hand-off; the workbench runs AIA with the unit bare at `:8767` as reference, and `up --no-unit` without it.* Data owner 2026-09-24: full UI control, not only the skin, edited quickly and seen by the agent; decided: rebuild the screens in React, area by area, D-L1 extended to the rebuilt screens. Agent sessions cannot reach develop (egress 403), so the workbench runs the real `ui_app.html` locally on a fictional panel with the web client in front, routed by the Caddyfile's `@web` | Workbench chunks 1–2 done: `make ui-workbench` (skinned `:8780`, bare `:8767`, 30 DEMO projects), skin rebuilt on save, `test_ui_workbench.py` 15 passed; `make ui-capture`: 48 screens × 2 widths, bare and skinned, 0 page errors, 0 overflow. Re-home chunks 0–2 and 4 done, 3 in part: `/app` behind the same gate (CI adapt check, smoke), the ledger-checked unit client, the hand-off into the classic interface (`#aia:open=…`), the rail, and **Správa projektů rebuilt in React** (`/app/projects`, ledger `REBUILT`, 0 classic texts missing, 220 parity checks, 7 component tests). Found OI-46: the classic rail prints *Core joint · VALID* as a literal. **Live on develop** (run 16 @ `0932c5d`). Now: **A4 research flow** ([plan](plans/research-flow-rehome.md)) — the data owner's next choice, 2026-09-24; survey done, OI-47 (classic *verify* never renders; *verify*/*next* unreachable) and OI-48 (four aliased unit routes missing from the ledger) recorded; **chunk 1 (foundation) done**: research routes, model, store with visible save state, job runner and panel, `/app/research/<id>/<step>` with the rail, `open@step` hand-off, `make ui-fixtures` (100 tests); **chunk 2 (Zadání) done**: `/app/research/<id>/brief`, 46 parity checks, 9 component tests, capture pair 0 missing; the workbench unit can no longer reach any AI provider (it had found the session's signed-in CLI). **Chunk 3 (Návrh) done**: `/app/research/<id>/plan`, 39 parity checks, 7 component tests, fixture capture pair 0 missing; the open@step hand-off no longer lands on the overview. **PR A complete** (merged, PR #49). **PR B** on `feature/research-flow-b`: survey recorded (OI-49 to OI-55); **chunk 4 (Dotazník) done**: `/app/research/<id>/questionnaire`, 62 parity checks, 10 component tests, fixture capture pair with only the dead button missing. **Chunk 5 (Audience) done**: one project session for all steps (OI-56, a lost-save defect from PR A, fixed); `/app/research/<id>/audience`, 72 parity checks, 8 component tests, capture pair with only the `[object Object]` print missing. **Chunk 6 (Dimenze) done**: `/app/research/<id>/persona`, 45 parity checks, 9 component tests, capture pair 0 missing; the model's *Deep Research* reaches the classic Data Library by a new hand-off verb; OI-57 (a failed audience catalogue re-requested on every draw) recorded. **PR B merged** (PR #50). **PR C merged** as #52 after the client-first IA; its Run, Progress and Results stages are under `/app/clients/<client>/research/<study>/` | `tools/ui_workbench/` · `packages/aia_core/tests/test_ui_workbench.py` |

**Production parity matrix and parity gates** — owner parity-quality. Plan:
the plan below.
**Merged in PR #25** @ `a15be65`; the `golden-fixtures` and `parity-status` jobs
run in CI (`.github/workflows/ci.yml`). Plan archived:
[`plans/done/parity-matrix-and-gates.md`](plans/done/parity-matrix-and-gates.md).

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
the data owner, 2026-09-24: PR C → OI-58 → OI-59.** PR C merged as #52;
PR #56 has merged and deployed, and the fictional Class C acceptance is done (20 calls, $0.2303301). Now: the merge order under *Open pull requests*, then checkpointing (OI-64), persistent lineage (OI-65), OI-58 and OI-59.

- ~~**PR C, research execution**~~ — merged (PR #52 @ `b3bd42f`); see Completed.
- **Agent Runtime Foundation**: AI respondent fieldwork is built and deployed in PR #56 @ `0310091`; ADR 0010 approval and EU pricing are recorded. The runtime is active for the approved synthetic client; the isolated $2 study completed with 20 calls costing $0.2303301. Native design assistants are implemented on this branch, not deployed or activated. Remaining work: checkpointed fieldwork (OI-64), ledger lineage (OI-65), analysis/report execution and owned Deep Research. Panel-derived transmission remains blocked by OI-61.
- **Deep Research** ([plan](plans/deep-research.md), [ADR 0017](../docs/architecture/adr/0017-deep-research-external-retrieval.md),
  Proposed). Asked for by the data owner 2026-09-25: research driven by the study's
  questions and tracked objects, over Client Knowledge and the web, bounded only by
  budget. The first multi-agent workload on the Agent Runtime Foundation; chunks 1–8
  are offline (no model, no network, no decision) and can proceed alongside it.
  Live use waits on DR-2 and D6; AR-2 accepted ADR 0010 for fictional Class C on
  develop only (2026-09-26), so a Class C smoke run needs only DR-2, and Class B
  needs D6. Where it sits against OI-58 / OI-59 is the data owner's call.
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

00. *Superseded by ADR 0015 (the develop site is AIA; 18.6.6 is `/classic`); kept
   for the oracle half.* **Sign in at <https://aia-develop.art-chain.io/> and look at the 18.6.6
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
3. ~~**Phase 4, second slice — live transport and the AI step executor.**~~ —
   **done in PR #56** (`live_transport.py`, the instance-role SigV4 signer,
   `ai_step.py`); D6 answered for fictional Class C by ADR 0010. What follows is history. The
   contract, registry, gateway, ledger and three adapters exist (In progress,
   above). What remains before any model call is real: an approved route per
   data class (D6), a transport (D7), a credential store (D8), a published
   catalog/policy (D9), and a worker executor that drives
   [the contract](../docs/architecture/ai-step-executor-contract.md).
4. ~~**Wire `apps/web` to the real API** and delete `lib/mock.ts`.~~ — **done**:
   `lib/mock.ts` and the `/org/*` demo were deleted in `297b573`
   (`git ls-files apps/web | grep -icE 'mock|/org/'` = 0). History: the live `/studies` pages (Cognito PKCE sign-in, studies → projects →
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
5c. **Implemented in PR #56 @ `0310091`: Bedrock adapter and `aws_bedrock` provider.** Original scope, retained as history: as a
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
   **The DOCX output side is in progress** as its own plan,
   [`plans/report-docx.md`](plans/report-docx.md): the document model, every
   report component, the style sheet generated from the design tokens, and the
   templates. **R0–R9 are done**: `DocxRenderer.render(doc) -> bytes`
   (`infrastructure/report_docx/renderer.py`) renders a validated document to
   a deterministic, lint-clean DOCX — cover, front matter, body, appendices,
   every component, tables, charts, evidence marks — and four templates
   (`domain/report/templates.py`) compose client, final, internal and
   documentation reports (`test_report_docx_*.py`, `test_report_templates.py`).
   R10 (composition from `AnalysisModuleResult`) and R11 (the REPORT step and
   download) are planned in the plan file and wait on analysis-governance and
   platform-runtime. Measured 2026-09-27 on `claude/focused-edison-wglopy`
   (SQLite, Python 3.12, no PostgreSQL): `make verify` exit 0 — core 2507
   passed / 200 skipped, API 199, worker 43 / 6, executors 58, web 750;
   `mypy` clean over 175 files; `layer_check` 62; `exposure_check` 7. The
   four samples were rendered through LibreOffice 24.2 and inspected in
   colour, greyscale and +35 % stress (`make report-preview`). Not run: Word
   itself (no Windows/macOS in the session), PostgreSQL suites.
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
8. Delete `src/server.js` + `src/views/` and their root dependencies. **Unblocked**:
   step 4 is done, and nothing in the Makefile, CI, Compose or any Dockerfile runs
   the root `package.json` (`apps/web/Dockerfile`'s `server.js` is Next.js's own).
9. **Sociomap as a durable job and a route** — *the job and the route exist*: the
   `sociomap` research step (`apps/executors/src/aia_executors/research.py`
   `SociomapExecutor`), served to researchers only (`routers/research.py`
   `_RESEARCHERS_ONLY`) and `INTERNAL_ONLY` while D6 is open. What remains is the
   client-deliverable gate (OI-17) and the web rendering. Originally: the first path that can emit a Sociomap to a client must
   carry the client-deliverable gate (OI-17). Then:
   `compute_sociomap` executed as a workflow step, its payload stored through
   `ArtifactRepository.put_json`, a study-scoped `GET` that serves it, and the
   `apps/web` sociomapping page rewired to render it (it still implements the
   superseded manual SOP). A 1,000-respondent map takes ~3 s, so it is a job,
   not a request (`docs/architecture/sociomapa-deterministic-engine.md` §9).

## Decisions needed

*The ids D6–D11 are used twice: the first set (provider route, transport,
credentials, catalog, capacity, reservations) is the AI runtime's, the second
(Sociomap declarations, RELIGION, field-policy authority, Simulation in the MVP,
world-model factors, simulation numerics) is methodology and simulation. Cite them
with the topic until they are renumbered in one change with every reference.*

| # | Decision | Blocks | Anchor |
|---|---|---|---|
| IA-1 | ~~Who may start a study~~ — **resolved 2026-09-24**: a client-level `RESEARCHER` or `LEAD` (`CREATE_STUDY`); nobody else | — | ADR 0015 decision 6 · `test_client_api.py` |
| IA-2 | ~~Order after the client-first IA~~ — **resolved 2026-09-24**: PR C → OI-58 → OI-59 | — | *Next*, above |
| IA-3 | ~~Does the client-first shell become the develop interface~~ — **resolved 2026-09-24**: yes, once its checks are green; `/classic` stays the temporary 18.6.6 escape hatch and reference | — | [plan](plans/done/client-first-ia.md) · ADR 0015 |
| DR-1 | ~~What drives Deep Research~~ — **resolved 2026-09-25**: both the research questions and the tracked objects | — | [plans/deep-research.md](plans/deep-research.md) |
| DR-2 | **Which search provider route(s) carry Deep Research queries, and is any approved for Class B.** Intent (data owner, 2026-09-25): the best results, which means queries carrying client context — Class B, EU-approved routes only (ADR 0008). Also the list of client terms that make a query Class B. Until decided, only Class C queries leave | Live web research | ADR 0017 decision 2 |
| DR-3 | ~~Client Knowledge to the model~~ — **resolved 2026-09-25**: target Bedrock EU for Class A and B; this is D6's decision for that route, not a separate one | — (D6 blocks live use) | ADR 0017 · D6 |
| DR-4 | **The fifth Deep Research output.** The data owner chose Research Design input, respondent context, knowledge proposals and a report, plus "something else" left unnamed | Completing chunk 11 | [plans/deep-research.md](plans/deep-research.md) § Outputs |
| DR-5 | **Default Deep Research budget and depth presets** — how far "as far as the budget allows" goes by default, and who may extend a parked run | Chunk 10 defaults | [plans/deep-research.md](plans/deep-research.md) § Decisions |
| IA-4 | ~~Commit the files `next dev` regenerates~~ — **resolved 2026-09-24**: only when their diff carries an intentional canonical instruction change | — | `AGENTS.md` § Next.js |
| D1 | ~~Confirm or replace ADR 0005~~ — **resolved**. Split into two statuses: the `ModelGateway` contract is *Accepted*; LiteLLM as its transport stays *Proposed* against seven conditions. Phase 4 is unblocked | — | `docs/architecture/adr/0005-llm-gateway.md` @ 8f545a5 |
| D2 | ~~Confirm ADR 0006~~ — **resolved**. *Accepted — constrained use*; the index had contradicted the file and was corrected | — | `docs/architecture/adr/0006-langgraph-agent-execution.md` @ 8f545a5 |
| D3 | ~~How the reference reaches CI~~ — **split.** Golden fixtures: CI checks out `AiAnalytics-AIA/AIA-reference` at the pinned commit; **needs a human to add a read-only deploy key as the `AIA_REFERENCE_DEPLOY_KEY` secret, then set the variable `AIA_REQUIRE_REFERENCE_REPO=1`**. Legacy-code comparison (the 94 tests): needs the withheld archive, which stays out of CI until its licence decision and an EU-resident home | Golden gates running in CI; the legacy parity tier | `ARCHITECTURE.md §8`, OI-1 |
| D4 | **Which legacy brand tokens name real clients**, and whether the confirmed ones may remain even in a private repository. The candidate list is enumerated in the remediation document, deliberately not duplicated here. Not an engineering judgement | Manifest reduction | `docs/migration/public-exposure-remediation.md` §2 |
| D6 | **Which provider route is approved for which data class.** A vendor/route ADR judged against ADR 0008. Until one exists every route is Class C only, and no client material may reach a model | Any live call on client material | `docs/architecture/adr/0008-eu-data-residency.md` |
| D7 | ~~**Live transport.**~~ — **resolved by PR #56**: `Urllib3Transport`, an HTTP client in the core package with retries off on the pool and the request, and delivery stated per failure (`AGENTS.md` § The AI runtime). A search service would reuse it | — | `infrastructure/model_adapters/live_transport.py` @ `0310091` |
| D8 | **Credential storage — for keyed services only.** The approved Bedrock route stores no credential: SigV4 with the instance or container role (`aws_signing.py`, ADR 0010), so live metered model calls no longer wait on this. Still open for any service that needs a key, such as a web-search API (DR-2): Secrets Manager reference scheme and/or the planned `api_credentials` table; adapters already hold a reference, never a secret | A keyed search or tool route (Deep Research live use) | `infrastructure/model_adapters/aws_signing.py` `ROLE_CREDENTIAL_METHODS` · `transport.py` `CredentialSource` |
| D9 | **Who publishes the model catalog, prices and policy versions**, and where the document lives. `parse_model_config` fails closed; there is deliberately no default | research-engine running anything | `domain/ai_models.py` `parse_model_config` @ this change |
| D10 | **Capacity backoff and the per-run hard cap.** The reference retried capacity 5/15/45 s in-call (not ported) and capped per run (`budget_guard.py`, R10, not ported). Both are scheduler/budget semantics — platform-runtime | Parity for `cost.hard_cap` | `docs/architecture/ai-runtime.md` *Failure classification* |
| D11 | ~~**Per-call or per-attempt reservations for AI steps.**~~ — **resolved 2026-09-25: one reservation per logical request**, settled once with the request's calls (a primary and its one repair); per call would drop the repair's cost (`settle_paid_call` settles once). `aia_executors/ai_step.py` · `docs/architecture/ai-step-executor-contract.md` § How a worker step keeps it | — | `apps/worker/src/aia_worker/executor.py` `StepContext.reserve`; `docs/architecture/ai-step-executor-contract.md` ask 1 |
| D5 | ~~Rewrite history, go private, or accept~~ — **RESOLVED and APPLIED 2026-09-22T20:21:38Z: the repository is PRIVATE, history PRESERVED.** Frozen. Verified `private: true` via the API | — | `docs/migration/public-exposure-remediation.md` § D5, §8 |
| D6 | **Accept, replace or defer the four AIA Sociomap declarations** — dissimilarity target, `aia_rowcond_unfolding_v1`, the map frame, relation-missing `refuse`. Decision package ready with approval fields; methodology owner, not engineering. **The only methodology decision preventing client use** | Any client-facing Sociomap | `docs/architecture/sociomapa-methodology-decision.md` · OI-16 |
| D7 | **Is `RELIGION` a certified matched block?** It is donor-matched and dictionary-eligible, but absent from the certificate's `matched_blocks`, so the claim gate refuses it client-facing. Data owner | Client claims on the five religion fields | `.planning/open-items.md` OI-19 |
| D8 | **One authority for field policy and the joint certificate.** `domain.evidence` and `domain.population` each implement both, with different eligibility (287 vs 115 client measured-claim fields). Pick one; the other consumes it | Consistent claim decisions between a run's recorded policy and the claims admitted from it | `.planning/open-items.md` OI-24 |
| D9 | **Is the Simulation lifecycle in the MVP?** `MVP-ACCEPT-1` is scoped to one Research study. Bringing Simulation in adds `simulation.*` to the blockers and makes OI-27 release-blocking | MVP scope | `docs/migration/mvp-acceptance.md` §6 |
| D10 | **Minimum factors in a world model: 6 or 4.** The reference prompt asks for 6–12, its schema allows 4, and its code tops anything under 4 up to 6. Production declares **6** and rejects fewer. Data owner to confirm or change it; a change bumps `SIMULATION_CONSTANTS_VERSION` | Confirming the simulation bounds as final | `packages/aia_core/src/aia_core/domain/simulation/reference.py` `WorldModelBounds.min_factors` · `test_bounds_are_pinned_to_the_constants_version` |
| D11 | **Port the reference simulation numerics exactly, or accept production-defined v1 as an intentional difference.** Exact `FS_*` parity needs the reference formula bodies (withheld) *and* numpy's PCG64 stream, which the stdlib-only domain layer (`ARCHITECTURE.md §2`) cannot hold without a named exception. Decide once the source is readable | The NUMERICAL half of F13 parity | `docs/architecture/simulation-deterministic-engine.md` §4.3, §5 |
| AR-1 | **Who may declare a client fictional** (making its designs Class C for the first live path): an operator-maintained deployment list today (`AIA_AI_FICTIONAL_CLIENT_IDS`), or a recorded client attribute? Data owner | Class C AI fieldwork on develop beyond the seed's clients | OI-63 |
| AR-2 | ~~ADR 0010 acceptance~~ — resolved 2026-09-26 by explicit authorised operator approval for fictional Class C develop use only; retention unspecified, EU rates $3.30/$16.50 per million input/output tokens. Live fictional acceptance completed: 20 successful calls, $0.2303301. | Wider Class A/B approval remains separate | [ADR 0010](../docs/architecture/adr/0010-bedrock-eu-inference-route.md) |
| AR-3 | **AWS-side cost attribution for Bedrock**: an application inference profile tagged `Environment=develop` (one coordinated Terraform + IAM + model-policy change), or rely on AIA's ledger only. Data owner + operator | Proving Bedrock spend is inside the $100 develop budget | ADR 0010 § Cost attribution |
| D12 | ~~**Merge order for the AI runtime.**~~ — **resolved 2026-09-23.** PR #28 (the `ModelGateway` contract) merged into `main` at `676bc1f`, and this change merges `main` into `develop`, so the gateway, its three recorded-exchange adapters and the `ai_usage_events` ledger are on both branches. Next #5c (the Bedrock adapter) is unblocked. Nothing forked ADR 0005 A | Brief items 11–13; Next #5c; ADR 0010 → Accepted | `.planning/plans/done/develop-deployment.md` § Contradictions, C1 |

Open defects and questions live in
[`open-items.md`](open-items.md). Plans in flight live in [`plans/`](plans/);
finished ones move to [`plans/done/`](plans/done/).

### Research agent publication checkpoint — 2026-09-27

*Merged as PR #63 (`85fa951`, 11:17 UTC); kept as the record of what it left. The complete DOCX
renderer it names as missing merged separately (PR #62); where the rest now sits is under In
progress, "The complete research journey".*

Native backend `c88ec50` and proposal screens `45a2651` on
`feature/research-agents`; full-workflow continuation is in the
[plan handoff](plans/research-agent-workflows.md#claude-continuation-handoff--2026-09-27).
Final review reproduced and fixed fieldwork runs disappearing behind newer design
jobs at a pagination limit. Regression:
`test_design_jobs_do_not_hide_fieldwork_when_the_list_is_limited`; PostgreSQL
Research/native-agent follow-up 30/30. A real browser journey, interpretation,
complete DOCX output and owned Deep Research remain required. Draft publication
is not completion or activation.
