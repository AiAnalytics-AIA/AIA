# Migration status

**Updated:** 2026-09-22
**Branch:** `main`
**Phase:** 1 and 2 complete. Phase 3 implemented and verified under real
PostgreSQL contention. Architecture v2.1 reconciliation applied.

> **This document is the narrative, not the tracker.** What is done, in
> progress and next lives in [`../../.planning/PROGRESS.md`](../../.planning/PROGRESS.md),
> and open defects in [`../../.planning/open-items.md`](../../.planning/open-items.md).
> Where the two disagree, the tracker wins and this document is stale.

Read this for the reasoning behind the state. Companion documents:
[reference-source.md](reference-source.md) ·
[migration-plan.md](migration-plan.md) ·
[module-inventory.md](module-inventory.md) ·
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
**Target:** AWS — RDS PostgreSQL, S3, ECR, Secrets Manager, KMS, CloudWatch,
Terraform, GitHub Actions. No Kubernetes. **No Redis and no SQS**: PostgreSQL is
both the authoritative store and the v0.1 queue, claimed with
`FOR UPDATE SKIP LOCKED`
([ADR 0002](../architecture/adr/0002-postgresql-authoritative-store.md)).

The **compute service is not decided**. ECS Fargate and App Runner both remain
options; neither is frozen, and nothing here should be read as selecting one. The
web client's hosting is likewise open.

The NPC Panel prototype is **not** in this repository. The authoritative
reference specification lives in the private repository
**`AiAnalytics-AIA/AIA-reference`** at tag
`reference-18.6.6-gemo-2026-09-11-v1` — capability map, methodology ledger,
subsystem contracts and 11 executable golden fixtures. See
[reference-source.md](reference-source.md) for the archive identity
(`86b70bfb…d53216`), the `AIA_LEGACY_REFERENCE` contract and bootstrap
instructions. A local checkout at `../npc-panel-reference` still satisfies
`AIA_LEGACY_REFERENCE` for parity and characterization tests.

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
- There is no `AWAITING_BUDGET`; budget exhaustion routes through `WAITING_USER`.
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

Measured after the Architecture v2.1 reconciliation, on **PostgreSQL 16.13**,
Python 3.12.3, Linux, in a virtualenv built from declared dependencies only:

| Suite | Result |
| --- | --- |
| Suite, on PostgreSQL | **449 passed, 94 skipped** |
| Suite, on SQLite | **433 passed, 110 skipped** |
| of which real-contention concurrency tests | **16** |
| `ruff check` / `ruff format --check` | clean, 51 files |
| `mypy --strict` | clean, 33 source files |
| Alembic upgrade / check / downgrade base / re-upgrade | clean, 4 revisions |
| API contract (OpenAPI) | 19 paths, every project route study-scoped |
| Startup smoke over HTTP | health, ready, create, read, content edit, 401 |
| Frontend lint / tsc / build | clean (1 pre-existing lint warning, 0 errors) |

**The 94 skips are the parity and characterization suite, and they are not
passes.** They need a checkout of the NPC Panel prototype, which is deliberately
not committed, and no reference was available for this run -- so the comparison
against the prototype **did not happen** and nothing here should be read as saying
it did. CI is in the same position and its parity job prints a warning rather than
claiming a pass. Anyone changing domain logic must run them locally:

```bash
AIA_LEGACY_REFERENCE=../npc-panel-reference make test-parity
```

The additional 16 skips on SQLite are correct and deliberate: SQLite has no
`FOR UPDATE SKIP LOCKED` and a single-writer model, so it cannot express the
contention being tested. **CI sets `AIA_REQUIRE_POSTGRES=1` for the concurrency
module, which turns a missing database into a failure rather than a skip** --
otherwise a build could go green with none of the concurrency guarantees checked.

The migration's data rewrite was verified against **live rows**, not only an empty
schema: runs and steps written as `WAITING_GATE` / `WAITING_BUDGET` come back as
`AWAITING_GATE` / `AWAITING_BUDGET` after the upgrade, and a `WAITING_CAPACITY` row
folds back into `WAITING_PROVIDER` on the downgrade. A migration exercised only on
an empty database is not a verified migration.

## Architecture v2.1 reconciliation ✅

The frozen v2.1 decision set was compared against this repository and the
divergences corrected. What changed in behaviour:

**Self-approval is configurable.** The code enforced `producer != approver`
absolutely. The frozen decision is that independent review is the *default* and
the same person may approve where policy explicitly allows it.
`allow_self_approval` is nullable on organizations, clients and studies, resolving
`study > client > organization > false`, read from persisted state by the
authorization layer and carried on the `StudyContext` — so nothing a model, agent,
tool argument or request body can produce is able to assert it. It never confers
authority: a RESEARCHER still cannot sign off. `approval_decisions` is a new
append-only ledger recording every decision with the policy that allowed it.

**Canonical workflow states.** `WAITING_GATE` → `AWAITING_GATE`,
`WAITING_BUDGET` → `AWAITING_BUDGET`, and provider capacity split out of
`WAITING_PROVIDER` into its own `WAITING_CAPACITY`. `AWAITING_*` means a person
owes us a decision; `WAITING_*` means a system owes us capacity. The two provider
waits recover differently -- only the quota park carries a resume instant -- and
merging them made a quota wall look like a blip.

**EU residency is enforceable.** It had been sitting in a "decisions needed" list
while nothing in the code could enforce it. `aia_core.domain.residency` is now a
fail-closed egress boundary with three data classes; see
[ADR 0008](../architecture/adr/0008-eu-data-residency.md).

**ADRs.** 0002 rewritten (PostgreSQL is the v0.1 queue; SQS explicitly deferred
behind a measured trigger). 0005 split into two statuses — the gateway contract
Accepted, LiteLLM still Proposed against seven conditions — so the architecture is
no longer blocked on a vendor question. 0006 corrected to *Accepted — constrained
use* in the index, which had contradicted the file.

Paid-call recovery was **not** touched, and has one more guard: a capacity failure
after a dispatched metered call still reaches `RECOVERY_REQUIRED` rather than
parking.

## Evidence governance foundation and the eight analysis modules ✅

The first Phase 6 slice, and deliberately not reporting. The reference enforced
most of its epistemic discipline as prose — the 400-field dictionary is read by
no runtime code (M02), and the allowed-metric set existed only inside a prompt
(M17) — so the claim layer was built before anything that could publish a claim.

- `aia_core.domain.evidence`: the dictionary as typed policy, re-derived and
  checked, EXACT against the reference export for all 400 fields; the
  `CORE_JOINT_STATUS` certificate, honoured only when bound to the loaded panel's
  hash; a claim policy that keeps modelled priors from backing measured claims and
  cross-block relationships from becoming same-person truth; effective-n support
  that suppresses by default; validation bound to a system fingerprint; the tier
  gate; the factual layer's explicit contract; and admission — the only way a
  number becomes an `AdmittedClaim`.
- `aia_core.domain.analysis` + `application.analysis`: the eight modules with
  fingerprints and resume, a closed draft schema, 100% prose number coverage
  (the reference passed at 95%), and a runner that ends COMPLETED or BLOCKED.

Where the legacy source would have to confirm a decision, the fail-closed reading
is taken and recorded (`.planning/open-items.md` OI-18); two further items went to
the register (OI-19 `RELIGION`, OI-20 factual keyword detection). The plan and its
review map are in `.planning/plans/done/evidence-governance-foundation.md`.

## In progress

Nothing. The tree is green and the slice is complete.

## Next

- [x] **A worker process.** Built as `apps/worker`; see
      [`.planning/plans/done/worker-process.md`](../../.planning/plans/done/worker-process.md)
      and [workflows.md § The worker](../architecture/workflows.md#the-worker).
      `PROGRESS.md` is the tracker; this line is narrative.
- [ ] **Phase 4 — AI runtime.** `AgentDefinition`, `ModelCapability`,
      `ModelPolicy`, `ModelRegistry`, `ModelGateway`, `ToolRegistry`,
      `AIUsageEvent`. [ADR 0005](../architecture/adr/0005-llm-gateway.md) decision
      A is accepted, so this is not blocked; only the choice of transport is.
- [ ] **A generalized metered-cost ledger.** Reservations control spend today at
      study granularity. Attribution across every metered source down to
      `Client → Study → Revision → WorkflowRun → Step → Agent/Tool/Call`, with
      compensating entries rather than edits, is outstanding.
- [ ] **OpenTelemetry instrumentation.** Structured logging and request
      correlation exist; spans, propagation and metrics do not.
- [ ] Wire `apps/web` to the real API and delete `lib/mock.ts`.
- [ ] Terraform for the AWS baseline, once the compute service is chosen.
- [ ] PostgreSQL row-level security as a second isolation layer.
- [ ] Rate limiting.

## Blockers and decisions needed

1. **Choose the compute service.** ECS Fargate or App Runner, on operational
   grounds, recorded as an ADR. Blocks Terraform, not Phase 4.
2. **Declare approved egress routes.** The residency boundary is enforceable and
   currently approves nothing, which is the correct failure mode but means no
   client inference can run until routes are declared and justified against
   [ADR 0008](../architecture/adr/0008-eu-data-residency.md). Choosing a provider
   to fill them is a vendor decision needing its own ADR — the residency invariant
   does not choose one.
3. **AWS provisioning.** The Cognito user pool, app client and Google Workspace
   federation must exist before any deployment. The code is ready and refuses to
   boot without them.
4. **Test LiteLLM against ADR 0005's seven conditions**, or write the adapters.
   Not a blocker for the gateway contract, which is accepted.
5. **`PRODUCT_POLICY.json` contradicts itself** about the production panel
   (`v17_4_0` at top level, `v17_1_2` under `data_core`). We treat `v17_4_0` as
   authoritative; needs resolving in Phase 6. See W5 in
   [reference-weaknesses.md](reference-weaknesses.md).

## Legacy functionality not yet migrated

Everything except project persistence, scope and artifact storage. Specifically:
the job engine, AI runtime, the research lifecycle, the simulation lifecycle beyond
its deterministic core (`aia_core.domain.simulation`), analysis,
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

The Architecture v2.1 reconciliation, on the branch opened against `main`.

Earlier verification of the workflow engine at `8102551`, on PostgreSQL 16.15 with
a reference checkout present, reported **496 passed / 0 skipped** on PostgreSQL and
**480 passed / 16 skipped** on SQLite, including the 94 parity and characterization
tests. Those numbers are not comparable to the table above, because that run had
the prototype available and this one did not. Both are recorded rather than one
being rewritten into the other: the difference *is* the parity suite, and
collapsing them would hide exactly the thing worth knowing.
