# Migration status

**Updated:** 2026-09-21
**Branch:** `migration/phase-1-foundation`
**Phase:** 1 and 2 complete. Phase 3 implemented and verified under real
PostgreSQL contention.

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

### Phase 3 — Durable workflow engine ✅

`WorkflowRun → StepRun → StepAttempt`, with the two-level state split: business
state on the run (what a researcher waits for) and technical execution state on
the attempt (what a worker is doing). Attempts are **append-only history** -- each
keeps its own error, provider, model and cost, replacing the prototype's single
counter and latest-error-only.

Implemented: DAG validation at definition time, dependency gating on `SUCCEEDED`
specifically, exclusive claiming via `FOR UPDATE SKIP LOCKED`, leases and
heartbeats, the full recovery table, budget reservations with a study-row lock,
cooperative cancellation, gates with separation of duties, and an append-only
event feed with monotonic ids.

**Four bugs were found by tests, three of which the sequential suite could not
see.** Details in "Bugs found" below.

Two counters where the prototype had one: `attempts_recorded` is monotonic and
numbers the append-only rows; `attempts_consumed` counts only failures that
should count against `max_attempts`. One counter cannot do both -- decrementing
for a quota park collided with attempt numbering and raised a unique-constraint
violation.

### Phase 3 — Characterization ✅
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
| Suite, on PostgreSQL | **496 passed, 0 failed, 0 skipped** |
| Suite, on SQLite | **480 passed, 16 skipped** (the concurrency module) |
| of which parity/characterization vs the prototype | **94** |
| of which real-contention concurrency tests | **16** |
| `ruff check` / `ruff format --check` | clean |
| `mypy --strict` | clean, 32 source files |

Verified on **PostgreSQL 16.15** and on SQLite. Python 3.14.6, macOS.

The 16 skips on SQLite are correct and deliberate: SQLite has no
`FOR UPDATE SKIP LOCKED` and a single-writer model, so it cannot express the
contention being tested. **CI sets `AIA_REQUIRE_POSTGRES=1`, which turns a
missing database into a failure rather than a skip** -- otherwise a build could go
green with none of the concurrency guarantees checked.

## In progress

Nothing. The tree is green and the slice is complete.

## Next

- [ ] **SQS dispatch + reconciler.** The engine is complete and PostgreSQL is
      authoritative; what remains is the transport. An SQS message carries an id
      only, and a reconciler re-enqueues runnable work with no in-flight message,
      so a lost message loses nothing. Idempotency is already proven under
      contention, which is the hard part.
- [ ] **A worker process.** `claim_next` → execute → `complete_attempt` /
      `fail_attempt`, with heartbeats and a cancellation poll at checkpoints.
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

## Bugs found by tests in Phase 3

Three of these four could not have been caught by the sequential suite. They are
recorded because each was a genuine defect in code that looked correct and had
passing tests.

1. **Lock convoy on the run row.** `_refresh_run` issued an unconditional
   `UPDATE workflow_runs SET updated_at` on every claim, completion and recovery.
   Every concurrent worker on the same run queued behind that single row lock,
   which serialised the whole engine and defeated the point of
   `FOR UPDATE SKIP LOCKED`. With eight workers it **deadlocked outright** -- the
   test suite hung rather than failing. Now the run row is written only when the
   derived status actually changes, so most calls take no lock at all.

2. **Concurrent budget overspend.** The budget check read outstanding
   reservations and then inserted -- a read-modify-write with no lock. Four
   workers each reserving $40 against a $100 budget **all succeeded**: $160 of a
   client's money. The sequential test passed because it was sequential. Fixed by
   taking a blocking `FOR UPDATE` lock on the study row across the check.

3. **Timezone portability.** `DateTime(timezone=True)` round-trips on PostgreSQL
   but SQLite stores no offset, so a lease deadline came back naive and the
   expiry comparison raised `TypeError`. Every recovery path crashed on SQLite
   while passing on PostgreSQL -- found only because CI runs both. Fixed with an
   `as_utc` normalisation, since every timestamp written is UTC.

4. **`UNKNOWN` was documented as permanent but omitted from the permanent set**,
   so an error the system could not classify would have been retried against a
   metered provider on the assumption it was transient.

Also fixed: the concurrency module's engine fixture dropped the schema the
session-scoped fixture still owned, which surfaced as ~105 unrelated errors in
other modules.

## Bugs found by CI on the first push

The first push to `main` went red, which is the gate doing its job.

5. **`pyjwt[crypto]` was imported but never declared.** Installed into a working
   virtualenv by hand and never added to `apps/api/pyproject.toml`, so a clean
   install had no `jwt` module and every Cognito verification failed at import.

   **This is exactly W1** -- the defect catalogued against the reference
   implementation. Flagged in someone else's code, then committed in ours.

   The lesson is about verification rather than care: a developer virtualenv
   accumulates packages and stops resembling a clean install. There is now a
   clean virtualenv built from **declared dependencies only**, and the full suite
   runs in it before a push. That is what CI does; doing it first turns a red
   build into a local failure.

6. **The Makefile hardcoded `.venv/bin/python`**, so every target using it failed
   in CI, which installs into the runner's interpreter. It now prefers the
   project venv and falls back to `python3` on PATH.

7. **The API contract check asserted routes that no longer existed.** Projects
   moved under `/api/v1/studies/{study_id}/projects` in Phase 2A but the
   required-paths list still named the flat `/api/v1/projects`. Corrected, and an
   inverse assertion added: a project route *outside* a study prefix now fails
   the build, because that would mean scope had stopped being carried in the
   path. The startup smoke test had the same staleness and now provisions a real
   organization/client/study/grant through the authorization path before
   exercising the study-scoped URL.

## `main` and GitHub — done

**`main` on GitHub is now this work**, and CI is green on it.

The replacement needed nothing destructive: `migration/phase-1-foundation` was a
direct descendant of `main`, so every old commit is an ancestor of the current
head. `main` fast-forwarded — the ten original MVP commits are still in the
history, and nothing was discarded or force-pushed.

```
0a9ee1d (old main, now an ancestor)  →  fast-forward  →  57c2ec8 (main)
```

CI status on `main`: **all six jobs green** — backend lint/types/tests on
PostgreSQL and SQLite, migration apply/drift/reversibility, API contract,
frontend lint/types/build, real-server startup smoke, dependency and secret scan.

**One honest limitation:** the 94 parity and characterization tests **do not run
in CI**, because the prototype is deliberately not committed. The parity job
reports `94 skipped` with a warning rather than claiming a pass. They run only
where a reference checkout exists:

```bash
AIA_LEGACY_REFERENCE=../npc-panel-reference make test-parity
```

Anyone changing domain logic must run them locally. CI cannot be the safety net
for that particular class of regression.

## The old application code — still present, deliberately

The old code is still in the tree and unmodified:

| Still there | State |
| --- | --- |
| `src/server.js` | 44-line Fastify stub. The only login path that works without AWS |
| `src/views/` | Its two EJS templates |
| `apps/web` | 1,629 LOC of Next.js, still entirely mock-backed |
| `docs/archive/original-mvp/` | Archived, not deleted, each file carrying a superseded notice |

This is the strangler rule: the new system was built alongside, and the old code
is removed only once nothing depends on it.

**Two distinct things remain, and they should not be conflated:**

**`src/server.js` + `src/views/` — disposable.** A 44-line stub comparing a
plaintext password from an env var. It protects nothing: the UI behind it is
mock-backed. The new API covers local development through
`DevelopmentIdentityProvider` and refuses to boot in production without Cognito,
which is a stronger posture. Deleting this loses nothing, and the root
`package.json` dependencies only it needed (`fastify`, `ejs`, `better-sqlite3`,
`exceljs`, `papaparse`) go with it.

**`apps/web` — real work, to be rewired rather than deleted.** 1,629 lines
someone built: a TipTap document workspace with agent propose/accept-reject, a
Word-like ribbon, an A4 page canvas, an artifacts panel, and Czech
(`Studie`) terminology. The plan is to point it at the live API and delete
`lib/mock.ts` and `lib/mockArtifacts.ts` -- not to discard the UI. Throwing it
away would repeat the mistake the migration exists to avoid.

**Order:**

1. **Provision the Cognito user pool.** Gates everything else.
2. **Wire `apps/web` to the real API**; delete the mock modules.
3. **Delete `src/server.js`, `src/views/`** and their root dependencies.

Step 1 is the blocker. Steps 2–3 are then straightforward.

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

`8102551` — feat(workflow): durable workflow engine with real-contention verification

Verified at that commit:

| | |
| --- | --- |
| Suite on PostgreSQL 16.15 | **496 passed**, 0 failed, 0 skipped |
| Suite on SQLite | **480 passed**, 16 correctly skipped |
| Parity / characterization vs the prototype | **94** |
| Real-contention concurrency tests | **16** |
| `ruff check` / `ruff format --check` | clean |
| `mypy --strict` | clean, 32 source files |
| Alembic upgrade / check / downgrade / re-upgrade | clean, 3 revisions |
| Canonical reference files unchanged | 1,324 verified by hash |

Python 3.14.6, macOS. `main` untouched; nothing pushed.
