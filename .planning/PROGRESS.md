# PROGRESS

**Single source of truth for what is done, in progress and next.**
Read this at the start of every session, before doing any work.

**Updated:** 2026-09-22 · **Branch:** `claude/peaceful-davinci-xuhrld` ·
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
| 8 (foundation) | **Population version + import foundation.** Content-addressed `DatasetVersion`, STATIC/LIVE with explicit compare-and-set promotion, lineage, lossless import validation against a hash-pinned 400-field contract, canonical weight resolution with no fallback, one loader (`PopulationRuntime`) issuing an unforgeable `RuntimePopulation`, a `PopulationBinding` recorded per run. Uncommitted at time of writing — see the plan | `packages/aia_core/src/aia_core/domain/population/` · `application/population.py` · `tests/test_population_*.py` · `.planning/plans/done/population-version-foundation.md` |
| — | **Development rules adopted**: `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `.planning/`, `tools/layer_check.sh` blocking in CI | `tools/layer_check.sh` @ this change · `.planning/plans/done/development-rules-adoption.md` |
| 9 (core) | **Sociomap deterministic engine**: spec + artifact contract v2; relation coercion, mutual projection, ipsatization, normaliser, object metrics / T-score and both terrain fields ported from the browser and the reference backend; layout **declared** (legacy algorithms refused, AIA row-conditional unfolding implemented, no parity claimed); drag and what-if as layers. F1–F9 vendored and run in every CI job | `packages/aia_core/src/aia_core/domain/sociomap/` · `test_sociomap_{relations,metrics,terrain,layout,engine,contracts,golden_fixtures}.py` · `docs/architecture/sociomapa-deterministic-engine.md` · `.planning/plans/done/sociomap-deterministic-engine.md` |
| 6 | **Evidence governance foundation**: field dictionary as enforced policy (all 400 fields re-derive identically to the reference export), `CORE_JOINT_STATUS` hash-bound certificate, permissible-claim policy, effective-n `SUPPRESS`-by-default support, allowed-metric enum, validation bound to system fingerprint, tier gate, factual layer, `AdmittedClaim` capability enforced by `layer_check` | `packages/aia_core/src/aia_core/domain/evidence/` · `tests/test_evidence_gate_parity.py` · `.planning/plans/done/evidence-governance-foundation.md` |
| 6 | **The eight analysis modules** against those contracts: order, input fingerprints and resume, closed draft schema, 100% prose number coverage, prompts rendered from the enums, results that hold only admitted claims; runner with repair ≤ 2 and pre-flight blocking | `packages/aia_core/src/aia_core/domain/analysis/`, `application/analysis.py` · `tests/test_analysis_runner.py` |

**Verified state, evidence governance merged with the population and Sociomap
work (2026-09-22).** PostgreSQL 16.13 / Python 3.12: **1325 passed / 101
skipped**; SQLite: **1307 passed / 119 skipped**; concurrency 18/18 with
`AIA_REQUIRE_POSTGRES=1`; migrations upgrade, `alembic check` no drift, downgrade
to base and back; `mypy --strict` clean across 72 source files; `ruff` clean;
`layer_check` 23/23; `exposure_check` 7/7. With `AIA_REFERENCE_REPO` at the
reference repository @ `678e298`, the evidence and population parity suites run
60 cases and skip 1 (the real certificate against the real panel, which needs the
archive).

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

**Sociomap engine, measured when it landed** (SQLite, Python 3.12, no
PostgreSQL in the session): **733 passed / 117 skipped**, against 546 / 117 on
the parent commit — +187 tests, no new skips. `mypy --strict` clean across 42
source files, `ruff` clean, `layer_check` 12/12. F4 and F8 are only partly
reproducible and are carried as OI-13 / OI-14; R parity is OI-15.

## In progress

Nothing. The tree is green.

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
about legacy behaviour and methodology.** It is private. This repository is
public and holds pointers only — see
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
| `REF-GAP-SOCIO-R-SMACOF` | parity-quality + sociomapa-deterministic — **open, OI-15.** R installs in cloud sessions but CRAN is blocked there, and the recipe needs the reference's withheld R wrapper. `r_smacof_unfolding` is refused; no R parity is claimed |
| `REF-GAP-SIMULATION-WORLD-MODEL` | parity-quality + simulation-engine |
| `REF-WITHHELD-REFERENCE-ARCHIVE` | data owner / population-data, after the licensing decision. Its destination must satisfy EU residency — [ADR 0008](../docs/architecture/adr/0008-eu-data-residency.md) |

## Next

Ordered. Take the top item unless told otherwise, and **write the plan to
`.planning/plans/<feature>.md` with its chunks before writing code**.

**Before the research engine can consume the population** (population-data owns
these; none is started):

- a. **Enrichment** — recover the seven `*_derived` derivations and port them behind
  `Enricher` with an EXACT fixture, or decide they are not needed. Until then the
  ANALYSIS view refuses to load (OI-7).
- b. **Classify the 8 runtime fields** (data owner). `DerivedField.client_claims_allowed`
  is False for all of them.
- c. **Field policy as code** (R5) — derive typed per-field claim rules from the
  dictionary that already travels with every version.
- d. **Companion assets** — scorecard, persona catalogue, respondent audit and the
  `CORE_JOINT_STATUS.json` hash-bound certificate (R6) validated at import;
  `ImportReport.companions_validated` is False today.
- e. **The EU asset store** behind `PopulationAssetSource`, and the first real import
  of all three versions (needs `REF-WITHHELD-REFERENCE-ARCHIVE` resolved).
- f. **A permission on establish/promote** before anything exposes them (OI-8).
- g. **Stage fingerprints from the binding**, not free text (OI-6).
- h. **Typed / columnar views** (numeric fields, the M07 age floor) as named,
  recorded transformations over the text-preserving load, and a process-wide cache
  for workers.

1. **Classify the ambiguous legacy brand tokens** (data owner, D4 below). Blocks
   the manifest reduction in
   [`public-exposure-remediation.md`](../docs/migration/public-exposure-remediation.md)
   §3 and the history-rewrite decision in §4.
2. **A worker process.** `claim_next` → execute → `complete_attempt` /
   `fail_attempt`, with heartbeats and a cancellation poll at checkpoints.
   Creates `apps/worker/` — layer 4 in `ARCHITECTURE.md §2`.
3. **Phase 4 — AI runtime.** `AgentDefinition`, `ModelCapability`, `ModelPolicy`,
   `ModelRegistry`, `LLMGateway`, `ToolRegistry`, `AIUsageEvent`.
   **No longer blocked.** [ADR 0005](../docs/architecture/adr/0005-llm-gateway.md)
   decision A — AIA owns the `ModelGateway` contract — is *Accepted*; only
   decision B (LiteLLM as the transport) is still *Proposed*, and the contract
   can be built against without it.
4. **Wire `apps/web` to the real API** and delete `lib/mock.ts`.
   Planned together with the design system in
   [`plans/design-system.md`](plans/design-system.md): 12 chunks, starting with
   the vocabulary purge (chunk 0) and the enum-bound status maps (chunk 2).
   Needs decisions DS-1 (web test runner), DS-2 (`clients.accent_slot`) and
   DS-3 (who owns `WAITING_CREDITS`), recorded in the plan.
5. **Terraform for the AWS baseline**, with OIDC federation rather than
   long-lived keys (`ARCHITECTURE.md §9`), once the compute service is chosen.
5a. **Reporting on admitted claims** — `client_report_v2` + `output_pack`
   (authoritative, `report-export-inventory.md` in the reference repository),
   consuming only `AnalysisModuleResult`. Now unblocked: the evidence layer is
   enforceable. Needs the worker (2) and the gateway (3) to run for real.
5b. **`statistics.uncertainty`** — Kish n, donor support and bootstrap intervals
   computed rather than supplied; `EvidenceRow` already refuses a client
   estimate without one. NUMERICAL parity, tolerance 1e-9, needs the archive.

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
| D3 | How the legacy prototype reaches CI so the 94 parity tests stop reporting as skipped — private submodule, or a published fixture pack. The reference repository being private makes a submodule viable now | Promoting the parity tier to blocking | `.planning/open-items.md` OI-1 |
| D4 | **Which legacy brand tokens name real clients**, and whether the confirmed ones may remain even in a private repository. The candidate list is enumerated in the remediation document, deliberately not duplicated here. Not an engineering judgement | Manifest reduction | `docs/migration/public-exposure-remediation.md` §2 |
| D5 | ~~Rewrite history, go private, or accept~~ — **RESOLVED and APPLIED 2026-09-22T20:21:38Z: the repository is PRIVATE, history PRESERVED.** Frozen. Verified `private: true` via the API | — | `docs/migration/public-exposure-remediation.md` § D5, §8 |
| D6 | **Accept, replace or defer the four AIA Sociomap declarations** — dissimilarity target, `aia_rowcond_unfolding_v1`, the map frame, relation-missing `refuse`. Decision package ready with approval fields; methodology owner, not engineering. **The only methodology decision preventing client use** | Any client-facing Sociomap | `docs/architecture/sociomapa-methodology-decision.md` · OI-16 |
| D7 | **Is `RELIGION` a certified matched block?** It is donor-matched and dictionary-eligible, but absent from the certificate's `matched_blocks`, so the claim gate refuses it client-facing. Data owner | Client claims on the five religion fields | `.planning/open-items.md` OI-19 |

Open defects and questions live in
[`open-items.md`](open-items.md). Plans in flight live in [`plans/`](plans/);
finished ones move to [`plans/done/`](plans/done/).
