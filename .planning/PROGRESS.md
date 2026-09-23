# PROGRESS

**Single source of truth for what is done, in progress and next.**
Read this at the start of every session, before doing any work.

**Updated:** 2026-09-22 · **Branch:** `claude/sleepy-keller-kg48oz` ·
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
| — | **Development rules adopted**: `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `.planning/`, `tools/layer_check.sh` blocking in CI | `tools/layer_check.sh` @ this change · `.planning/plans/done/development-rules-adoption.md` |

**Verified state.** Re-measured on PostgreSQL 16 and Python 3.12.12 when the
development rules landed: **402 passed / 94 skipped** on PostgreSQL, **386 passed
/ 110 skipped** on SQLite, 16 concurrency tests passing under real contention
with `AIA_REQUIRE_POSTGRES=1`, `mypy --strict` clean across 32 source files,
`ruff` clean, `layer_check` 12/12, migrations reversible with no model drift.

402 + 94 = 496, matching the baseline recorded at df294e2. The 94 skips are the
parity and characterization tests — the prototype is deliberately not vendored
(OI-1). The extra SQLite skips are the concurrency module, which SQLite cannot
express; CI sets `AIA_REQUIRE_POSTGRES=1` so their absence fails rather than
skips (`.github/workflows/ci.yml:99-108` @ df294e2).

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
- [x] Golden-fixture harness — `test_golden_fixtures.py`, first gate F9 against
      `domain.sociomap.view`, every fixture refused unless it hashes to its pin
- [x] `tools/parity_status.py` — `PASS` / `FAIL` / `NOT_EXECUTED` /
      `NOT_RUNNABLE` / `NOT_REQUIRED` from JUnit; `test_parity_status_tool.py`
- [x] CI: JUnit from every pytest step, `golden-fixtures` and `parity-status`
      jobs, `|| true` removed from the legacy parity job
- [x] `REF-GAP-SOCIO-R-SMACOF` / `REF-GAP-SIMULATION-WORLD-MODEL` owned —
      OI-6 / OI-7, `reference_gaps` in the matrix
- [x] Parity status below; findings OI-8, OI-9

## Parity status — this cycle

**Highest-risk unverified capability: `cost.reservations`.** It is
`IMPLEMENTED`, moves money (high-risk R10), owes **EXACT** parity, sits on the
MVP path — and has **no reference-backed gate at all**: every test of it is
production-only, so a divergence from the reference's reservation decisions
would merge green. OI-9 carries the fix.

Measured 2026-09-22 in a cloud session (Python 3.12, PostgreSQL 16 and SQLite,
reference repository @ 678e298, **no legacy tree**), working tree over 17c0a6b,
by running the CI pytest sequence and then
`tools/parity_status.py --available postgres reference_repo`:

| Verdict | All 78 | MVP blockers (52) |
| --- | ---: | ---: |
| `PASS` | 1 (`api.http`, and it is `PARTIAL`) | 1 |
| `NOT_EXECUTED` | 3 (`pipeline.stages`, `ai.provider_policy`, `workflow.engine` — their legacy-tree gates skip) | 3 |
| `NOT_RUNNABLE` | 65 | 48 |
| `FAIL` | 0 | 0 |
| `NOT_REQUIRED` | 9 | — |

**Zero MVP blockers are release-ready**, so `MVP-ACCEPT-1` is `NOT_RUNNABLE`.
Next four by risk: `ai.provider_policy` (R11, legacy gates not executed),
`api.http` (R14, partial), `sociomapping.core` (R16; F9 passes, seven fixtures
await the port), `pipeline.stages` (legacy gates not executed). 68 of 78
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
| `REF-GAP-SOCIO-R-SMACOF` | parity-quality + A8 sociomapa-deterministic — OI-6. Blocked on R + `smacof` **and** the withheld archive |
| `REF-GAP-SIMULATION-WORLD-MODEL` | parity-quality + A7 simulation-engine — OI-7. Blocked on a credential, an ADR 0008 egress route **and** the withheld archive |
| `REF-WITHHELD-REFERENCE-ARCHIVE` | data owner / population-data, after the licensing decision. Its destination must satisfy EU residency — [ADR 0008](../docs/architecture/adr/0008-eu-data-residency.md) |

## Next

Ordered. Take the top item unless told otherwise, and **write the plan to
`.planning/plans/<feature>.md` with its chunks before writing code**.

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
5. **Terraform for the AWS baseline**, with OIDC federation rather than
   long-lived keys (`ARCHITECTURE.md §9`), once the compute service is chosen.

**Removed from this list: "SQS dispatch + reconciler".** It contradicted
[ADR 0002](../docs/architecture/adr/0002-postgresql-authoritative-store.md),
which defers SQS behind a measured trigger and its own ADR: PostgreSQL *is* the
v0.1 queue and workers claim with `FOR UPDATE SKIP LOCKED`. There is no transport
left to build.
6. PostgreSQL row-level security as a second isolation layer.
7. Rate limiting.
8. Delete `src/server.js` + `src/views/` and their root dependencies, once step 4
   removes the last thing that needs them.

## Decisions needed

| # | Decision | Blocks | Anchor |
|---|---|---|---|
| D1 | ~~Confirm or replace ADR 0005~~ — **resolved**. Split into two statuses: the `ModelGateway` contract is *Accepted*; LiteLLM as its transport stays *Proposed* against seven conditions. Phase 4 is unblocked | — | `docs/architecture/adr/0005-llm-gateway.md` @ 8f545a5 |
| D2 | ~~Confirm ADR 0006~~ — **resolved**. *Accepted — constrained use*; the index had contradicted the file and was corrected | — | `docs/architecture/adr/0006-langgraph-agent-execution.md` @ 8f545a5 |
| D3 | ~~How the reference reaches CI~~ — **split.** Golden fixtures: CI checks out `AiAnalytics-AIA/AIA-reference` at the pinned commit; **needs a human to add a read-only deploy key as the `AIA_REFERENCE_DEPLOY_KEY` secret, then set the variable `AIA_REQUIRE_REFERENCE_REPO=1`**. Legacy-code comparison (the 94 tests): needs the withheld archive, which stays out of CI until its licence decision and an EU-resident home | Golden gates running in CI; the legacy parity tier | `ARCHITECTURE.md §8`, OI-1 |
| D6 | **Is the Simulation lifecycle in the MVP?** `MVP-ACCEPT-1` is scoped to one Research study. Bringing Simulation in adds `simulation.*` to the blockers and makes OI-7 release-blocking | MVP scope | `docs/migration/mvp-acceptance.md` §6 |
| D4 | **Which legacy brand tokens name real clients**, and whether the confirmed ones may remain even in a private repository. The candidate list is enumerated in the remediation document, deliberately not duplicated here. Not an engineering judgement | Manifest reduction | `docs/migration/public-exposure-remediation.md` §2 |
| D5 | ~~Rewrite history, go private, or accept~~ — **RESOLVED and APPLIED 2026-09-22T20:21:38Z: the repository is PRIVATE, history PRESERVED.** Frozen. Verified `private: true` via the API | — | `docs/migration/public-exposure-remediation.md` § D5, §8 |

Open defects and questions live in
[`open-items.md`](open-items.md). Plans in flight live in [`plans/`](plans/);
finished ones move to [`plans/done/`](plans/done/).
