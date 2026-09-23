# PROGRESS

**Single source of truth for what is done, in progress and next.**
Read this at the start of every session, before doing any work.

**Updated:** 2026-09-23 · **Branch:** `claude/sleepy-keller-kg48oz` ·
**Trunk:** `main`

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
      OI-15 (already open on `main`, now also in the matrix) / OI-24, `reference_gaps` in the matrix
- [x] Parity status below; findings OI-25, OI-26

## Parity status — this cycle

**Highest-risk unverified capability: `cost.reservations`.** It is
`IMPLEMENTED`, moves money (high-risk R10), owes **EXACT** parity, sits on the
MVP path — and has **no reference-backed gate at all**: every test of it is
production-only, so a divergence from the reference's reservation decisions
would merge green. OI-26 carries the fix.

Measured 2026-09-23 in a cloud session (Python 3.12, PostgreSQL 16 and SQLite,
reference repository @ 678e298, **no legacy tree**), on this branch after merging
`main` @ 8978b99 (Sociomap engine, population readiness, worker), by running the
CI pytest sequence and then
`tools/parity_status.py --available postgres reference_repo`:

| Verdict | All 78 | MVP blockers (52) |
| --- | ---: | ---: |
| `PASS` | 10 — all `PARTIAL` except `workflow.legacy_dispatch` | 10 |
| `NOT_EXECUTED` | 3 (`pipeline.stages`, `ai.provider_policy`, `workflow.engine` — their legacy-tree gates skip) | 3 |
| `NOT_RUNNABLE` | 56 | 39 |
| `FAIL` | 0 | 0 |
| `NOT_REQUIRED` | 9 | — |

**One MVP blocker is release-ready** (`workflow.legacy_dispatch`), so
`MVP-ACCEPT-1` is `NOT_RUNNABLE`. Golden fixtures: F1–F3, F5–F7, F9–F11 gated
and passing; F8 partially gated (OI-14); F4 refused (OI-13); F12/F13 uncaptured.
Next four by risk: `ai.provider_policy` (R11, legacy gates not executed),
`sociomapping.core` (R16; F4 and F8), `pipeline.stages` (legacy gates not
executed), `config.environment` (no test of the new behaviour). 68 of 78
capabilities have no confirmed owner — only A7, A8 and population-data are
named anywhere durable; the rest carry their bounded context as an
*unconfirmed* workstream.

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
| `REF-GAP-SIMULATION-WORLD-MODEL` | parity-quality + A7 simulation-engine — **open, OI-24.** Blocked on a credential, an ADR 0008 egress route **and** the withheld archive |
| `REF-WITHHELD-REFERENCE-ARCHIVE` | data owner / population-data, after the licensing decision. Its destination must satisfy EU residency — [ADR 0008](../docs/architecture/adr/0008-eu-data-residency.md) |

## Next

Ordered. Take the top item unless told otherwise, and **write the plan to
`.planning/plans/<feature>.md` with its chunks before writing code**.

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
3. **Phase 4 — AI runtime.** `AgentDefinition`, `ModelCapability`, `ModelPolicy`,
   `ModelRegistry`, `LLMGateway`, `ToolRegistry`, `AIUsageEvent`.
   **No longer blocked.** [ADR 0005](../docs/architecture/adr/0005-llm-gateway.md)
   decision A — AIA owns the `ModelGateway` contract — is *Accepted*; only
   decision B (LiteLLM as the transport) is still *Proposed*, and the contract
   can be built against without it.
4. **Wire `apps/web` to the real API** and delete `lib/mock.ts`.
   Planned together with the design system in
   [`plans/design-system.md`](plans/design-system.md). Decisions DS-1, DS-2 and
   DS-3 are resolved there. Order: chunks 0–3 (vocabulary, tokens, enum binding,
   primitives + Vitest), then the first real vertical slice (Portfolio → Study →
   workflow state → approval) before any further screens. Cross-context
   dependencies: OI-9 to OI-12.
5. **Terraform for the AWS baseline**, with OIDC federation rather than
   long-lived keys (`ARCHITECTURE.md §9`), once the compute service is chosen.

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
| D1 | ~~Confirm or replace ADR 0005~~ — **resolved**. Split into two statuses: the `ModelGateway` contract is *Accepted*; LiteLLM as its transport stays *Proposed* against seven conditions. Phase 4 is unblocked | — | `docs/architecture/adr/0005-llm-gateway.md` @ 8f545a5 |
| D2 | ~~Confirm ADR 0006~~ — **resolved**. *Accepted — constrained use*; the index had contradicted the file and was corrected | — | `docs/architecture/adr/0006-langgraph-agent-execution.md` @ 8f545a5 |
| D3 | ~~How the reference reaches CI~~ — **split.** Golden fixtures: CI checks out `AiAnalytics-AIA/AIA-reference` at the pinned commit; **needs a human to add a read-only deploy key as the `AIA_REFERENCE_DEPLOY_KEY` secret, then set the variable `AIA_REQUIRE_REFERENCE_REPO=1`**. Legacy-code comparison (the 94 tests): needs the withheld archive, which stays out of CI until its licence decision and an EU-resident home | Golden gates running in CI; the legacy parity tier | `ARCHITECTURE.md §8`, OI-1 |
| D4 | **Which legacy brand tokens name real clients**, and whether the confirmed ones may remain even in a private repository. The candidate list is enumerated in the remediation document, deliberately not duplicated here. Not an engineering judgement | Manifest reduction | `docs/migration/public-exposure-remediation.md` §2 |
| D5 | ~~Rewrite history, go private, or accept~~ — **RESOLVED and APPLIED 2026-09-22T20:21:38Z: the repository is PRIVATE, history PRESERVED.** Frozen. Verified `private: true` via the API | — | `docs/migration/public-exposure-remediation.md` § D5, §8 |
| D6 | **Accept, replace or defer the four AIA Sociomap declarations** — dissimilarity target, `aia_rowcond_unfolding_v1`, the map frame, relation-missing `refuse`. Decision package ready with approval fields; methodology owner, not engineering. **The only methodology decision preventing client use** | Any client-facing Sociomap | `docs/architecture/sociomapa-methodology-decision.md` · OI-16 |
| D7 | **Is the Simulation lifecycle in the MVP?** `MVP-ACCEPT-1` is scoped to one Research study. Bringing Simulation in adds `simulation.*` to the blockers and makes OI-24 release-blocking | MVP scope | `docs/migration/mvp-acceptance.md` §6 |

Open defects and questions live in
[`open-items.md`](open-items.md). Plans in flight live in [`plans/`](plans/);
finished ones move to [`plans/done/`](plans/done/).
