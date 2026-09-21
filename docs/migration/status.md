# Migration status

**Updated:** 2026-09-21
**Branch:** `migration/phase-1-foundation`
**Phase:** 1 and 2 complete. Phase 3 characterized, not implemented.

Read this first to continue the work. Companion documents:
[migration-plan.md](migration-plan.md) ·
[parity-matrix.md](parity-matrix.md) ·
[reference-weaknesses.md](reference-weaknesses.md) ·
[legacy-system-map.md](legacy-system-map.md) ·
[../architecture/README.md](../architecture/README.md) ·
[../architecture/adr/README.md](../architecture/adr/README.md)

## Current architecture

```
aia-repo/
├── apps/
│   ├── api/                        FastAPI
│   │   └── src/aia_api/identity/   Cognito, test and development providers
│   └── web/                        Next.js 16 / React 19. Still mock-backed.
├── packages/aia_core/src/aia_core/
│   ├── domain/         pipeline, project, providers, scope  (pure, no I/O)
│   ├── application/    scope resolution; owns authorization
│   └── infrastructure/ tables, repositories, storage, db
├── migrations/         Alembic, 2 revisions
├── docs/product/       authoritative product scope
├── docs/architecture/  + adr/ (7 decision records)
├── docs/migration/     plan, status, parity, weaknesses, legacy map
├── docs/archive/original-mvp/   superseded; not requirements
└── src/server.js       legacy Fastify login stub (retained; see below)
```

**Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic,
PostgreSQL 16, Next.js 16, TypeScript, Tailwind 4.
**Target:** AWS — Amplify (web), ECS Fargate (API + workers), RDS PostgreSQL, S3,
SQS, ECR, Secrets Manager, KMS, CloudWatch, Terraform, GitHub Actions. No
Kubernetes. No Redis ([ADR 0002](../architecture/adr/0002-postgresql-authoritative-store.md)).

The NPC Panel prototype is **not** in this repository. It lives at
`../npc-panel-reference` and is referenced by `AIA_LEGACY_REFERENCE` for parity
and characterization tests only.

## Completed

### Phase 0 — Discovery ✅
Both codebases audited; prototype baseline established; two latent reference bugs
found; architecture and feature maps written.

### Phase 1 — Production foundation ✅
Monorepo structure, pure domain layer, PostgreSQL schema, Alembic migrations,
typed configuration with production guards, structured logging with request
correlation and secret redaction, one error contract, Docker Compose, Makefile,
CI with quality gates. Root `pyproject.toml` holds shared ruff/mypy config.

### Phase 2A — Scope foundation ✅
`Organization → Client → Study`, with Client and Study as hard isolation
boundaries. `User → Organization membership → Client grant → Study grant → Role`,
four scope roles mapped to discrete permissions. `projects` carries
`client_id` and `study_id`; the isolation predicate asserts all three levels.

`StudyContext` is issuable only by `ScopeResolver` via a module-private sentinel,
so no model-generated argument, tool payload or request body can widen scope.
Repositories refuse anything that is not an issued context, by type.

### Phase 2B — Artifact storage ✅
`ArtifactStore` protocol with three backends: S3 (lazy `boto3` import, SSE/KMS),
filesystem (atomic temp/fsync/rename) and in-memory. All enforce identical key
validation and hash verification. `ArtifactRepository` preserves fingerprinting,
dependency edges, full provenance, revision association and cross-revision reuse.
Write order — hash, check reuse, upload, verify, then commit the row — is enforced
rather than left to callers.

### Phase 2C — Authentication boundary ✅
`IdentityProvider` is the only seam. `CognitoIdentityProvider` validates Cognito
JWTs offline-testably: RS256 allow-list, JWKS with rotation pickup and
rate-limited refresh, issuer, `token_use`, audience, expiry with clock skew.
A token proves identity and nothing else — `VerifiedIdentity` carries no role,
client or study, and a test asserts those fields stay absent.

### Documentation reorganisation ✅
`ROADMAP.md`, `mvp-scope.md`, `BACKLOG.md` and `AGENTS.md` moved to
`docs/archive/original-mvp/` with a superseded notice on each. Authoritative
product scope at `docs/product/`. Seven ADRs. `docs/migration/reference-weaknesses.md`.

### Phase 3 — Characterization ✅ (implementation not started)
**64 characterization tests** describe the legacy `job_store.py` before any of it
is reimplemented: the full status set and transition table verbatim, terminal
states, idempotency, dependency gating, exclusive claiming, leases, heartbeats,
lease recovery, cooperative cancellation, the three waiting states, approvals with
option validation and cost-estimate requirements, workflow status precedence, the
event log, and restart durability.

Three tests explicitly document behaviour the new engine will **change**, and each
still asserts the legacy behaviour so the suite reports if the reference differs
from what we believe:

- `attempt` is a counter, not a history → becomes append-only `StepAttempt` rows.
- There is no `WAITING_BUDGET`; budget exhaustion routes through `WAITING_USER`.
- Timestamps are naive local-time strings → become `TIMESTAMP WITH TIME ZONE` UTC.

The single most valuable behaviour found: **`recover_expired` refuses to retry a
possibly-billed paid call.** When a worker dies mid-flight on a metered provider,
it moves the job to `RECOVERY_REQUIRED` and converts any outstanding reservation
to `SETTLED_UNCERTAIN`, adding it to actual cost. Losing that on the port would
turn a worker crash into a silent double-spend.

## PostgreSQL verification ✅ — the Phase 1 caveat is closed

The earlier SQLite-only caveat no longer applies. A real PostgreSQL 16.15 instance
(Homebrew, keg-only, user-level, no system service) was used for:

| Checked | Result |
| --- | --- |
| `alembic upgrade head`, both revisions | clean |
| `alembic check` (model/schema drift) | no drift |
| `alembic downgrade base` then re-upgrade | clean |
| Constraints, check constraints, foreign keys | created and enforced |
| Cascade deletes | verified |
| JSONB columns | exercised |
| Timezone-aware timestamps | exercised |
| Repository behaviour, all suites | 377 passed |
| API behaviour, all suites | included above |

**Still not exercised:** concurrent workflow operations and transaction-isolation
semantics under contention. There is nothing concurrent to test yet — the job
engine is Phase 3. Those tests belong with it, and Phase 3 is not complete without
them.

## Test and quality state

| Suite | Result |
| --- | --- |
| `packages/aia_core` | **263 passed** |
| `apps/api` | **114 passed** |
| **Total** | **377 passed, 0 failed, 0 skipped** |
| of which parity/characterization vs the prototype | **93** |
| `ruff check` / `ruff format --check` | clean |
| `mypy --strict` | clean, 30 source files |

Verified on **PostgreSQL 16.15** and on SQLite. Python 3.14.6, macOS.

## In progress

Nothing. The tree is green and the slice is complete.

## Next

- [ ] **Phase 3 — durable workflow engine.** Characterization is done; implement
      against it. `WorkflowRun → StepRun → StepAttempt` in PostgreSQL, SQS
      dispatch, a reconciler so a lost message loses no work, idempotent step
      execution for at-least-once delivery. **Must include the concurrency and
      transaction-semantics tests listed above.**
- [ ] **Phase 4 — AI runtime.** `AgentDefinition`, `ModelCapability`,
      `ModelPolicy`, `ModelRegistry`, `LLMGateway`, `ToolRegistry`,
      `AIUsageEvent`. Confirm [ADR 0005](../architecture/adr/0005-llm-gateway.md)
      and [ADR 0006](../architecture/adr/0006-langgraph-agent-execution.md) first.
- [ ] Wire `apps/web` to the real API and delete `lib/mock.ts`.
- [ ] Terraform for the AWS baseline.
- [ ] PostgreSQL row-level security as a second isolation layer.
- [ ] Rate limiting.

## Blockers and decisions needed

1. **Confirm ADR 0005 (LiteLLM) before Phase 4.** It is marked *Proposed*, not
   Accepted. `ai_router.py` contains behaviour we are committed to preserving —
   no silent fallback, the ten-way error taxonomy, quota parking distinguished
   from failure — and a library that retries or falls back on our behalf would
   break the product's central provider rule. The ADR lists four things to verify.
2. **Confirm ADR 0006 (LangGraph boundary) before Phase 4.**
3. **AWS provisioning.** The Cognito user pool, app client and Google Workspace
   federation must exist before any deployment. The code is ready and refuses to
   boot without them.
4. **`PRODUCT_POLICY.json` contradicts itself** about the production panel
   (`v17_4_0` at top level, `v17_1_2` under `data_core`). We treat `v17_4_0` as
   authoritative; needs resolving in Phase 6. See W5 in
   [reference-weaknesses.md](reference-weaknesses.md).

## Legacy functionality not yet migrated

Everything except project persistence, scope and artifact storage. Specifically:
the job engine, AI runtime, research and simulation lifecycles, analysis,
validation and methodology gates, reporting, Data Library, Society Intelligence,
population and audience, Sociomapa, demos, ingestion, exports and scheduling.
128 of the prototype's 136 API routes and its entire frontend remain.
See [parity-matrix.md](parity-matrix.md) for the component inventory.

`src/server.js` (44-line Fastify login stub) is **still retained deliberately**.
It holds the only login path that works today without AWS. **Removal condition:**
delete once a Cognito user pool is provisioned and the web client authenticates
against it.

## Known regressions

None. No previously working behaviour has been removed or altered.

The prototype remains fully functional at `../npc-panel-reference` — its own suite
still passes 394 tests.

**One honest note about the reference tree:** running the prototype's *own* test
suite writes to its `data/` directory and creates output under
`full_simulation_runs/` and `full_simulation_benchmarks/`. The tree is therefore
no longer byte-identical to the supplied snapshot, and its file count has grown
from 1,565. That is the prototype's own test behaviour, not an edit by us. Our
own parity and characterization tests were verified to write **nothing** to it:
a before/after stat snapshot over all 1,893 files showed no change after running
all 113 of them.

## Notes for whoever continues

- **Run the parity and characterization suites before changing anything they
  cover.** `AIA_LEGACY_REFERENCE=../npc-panel-reference make test-parity` —
  93 tests comparing against the validated prototype.
- **Phase 3's specification is already written**, in
  `packages/aia_core/tests/test_legacy_job_store_characterization.py`. Implement
  against it rather than reading `job_store.py` again from scratch.
- **`stage_input_payload` changes are migrations, not tweaks.** Adding a field
  changes the fingerprint and invalidates every artifact stored for that stage.
- **Provider transport is excluded from fingerprints on purpose.** Do not "fix"
  it. Mixed-provider continuation depends on it.
- **The waiting states are not errors.** A quota pause resets the retry counter;
  treating it as a failed attempt will eventually fail projects that were only
  waiting.
- **Scope cannot come from an argument.** If you find yourself wanting to pass a
  `client_id` into a service, the design has gone wrong — see
  [ADR 0004](../architecture/adr/0004-client-study-isolation.md).
- **Six documented reference weaknesses and three parity deviations** exist. See
  [reference-weaknesses.md](reference-weaknesses.md) and
  [parity-matrix.md](parity-matrix.md) D1–D3.
- Local PostgreSQL for verification (no Docker on the build machine):
  ```bash
  /opt/homebrew/opt/postgresql@16/bin/pg_ctl -D <datadir> \
    -o "-p 55432 -c listen_addresses=127.0.0.1 -c unix_socket_directories=''" start
  ```
  The empty socket directory is required: a scratchpad path exceeds the 103-byte
  Unix-socket limit.

## Last verified commit

`5c8c6ea` — test(workflow): characterize the legacy job engine before reimplementing it

Verified at that commit: 377 tests passing (263 core + 114 API, of which 93 are
parity/characterization against the prototype), `ruff check` and
`ruff format --check` clean, `mypy --strict` clean over 30 source files,
Alembic upgrade/check/downgrade/re-upgrade clean.

Verified against **PostgreSQL 16.15** and SQLite, on Python 3.14.6, macOS.
