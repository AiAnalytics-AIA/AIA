# platform-runtime

**STATUS: ACTIVE — worker MERGED to main (PR #23, merge 0424667, 2026-09-22T23:29Z). Awaiting next task.**
Cloud session. No local-machine dependency. PostgreSQL 16.13 and Python 3.12.3
provisioned in-session; every number below was measured here.

## Mission

Make durable workflows actually execute safely in production.

## Done this turn — the worker process (`apps/worker`)

Plan: `.planning/plans/done/worker-process.md`. PR: https://github.com/AiAnalytics-AIA/AIA/pull/23
(draft). 8 commits, 7864ed1..7326e29; each verified on its own: mypy clean,
full suite green on PostgreSQL and SQLite at every commit.

- `claim_next` → `StepExecutor.execute` → `complete_attempt` / `fail_attempt`,
  heartbeat thread, cancellation observed at checkpoints within one heartbeat,
  per-call metering (`reserve → dispatching → send → settled`), lease-fenced
  writes, `SIGTERM` = release (runnable at once, not counted), second signal /
  `SIGKILL` = lease lapses → recovery. Every worker also reconciles and resumes
  provider parks.
- Narrow executor seam: `aia_worker.executor.StepExecutor` / `StepContext`;
  executors registered by kind from `AIA_WORKER_EXECUTORS=module:factory`; the
  worker claims only kinds it has. `layer_check` forbids the worker importing
  anything domain-specific, and the API executing steps.
- Scope: `WorkQueue` is the only cross-study surface (claim, recover, resume,
  refuse); `ScopeResolver.execution_context` issues a RESEARCHER-permission
  `StudyContext` only against a held lease, actor = `triggered_by`.

## Engine defects found and fixed (each reproduced by a test)

| # | Defect |
|---|---|
| W1 | heartbeat could resurrect an attempt a reconciler had just expired (reproduced on origin/main) |
| W2 | a stale worker could complete / fail / abandon a step it no longer owned |
| W3 | a retried completion charged the study twice |
| W4 | cancelling a paid step leaked its reservation forever (reproduced on origin/main) |
| W5 | known spend was released, not charged, when the attempt then failed (reproduced on origin/main) |
| W6 | nothing ever resumed WAITING_PROVIDER / WAITING_CAPACITY |
| W7 | a cancelled run whose worker died stayed RUNNING forever (reproduced on origin/main) |
| W8 | two steps of one run finishing together left the run RUNNING / a join step BLOCKED forever |

## Observed test results (this session)

- final commit: PostgreSQL 688 passed / 100 skipped (core+API+worker); core 526 / API 114; concurrency 21
  passed with `AIA_REQUIRE_POSTGRES=1`; worker 48 passed (6 drive real worker
  processes: 3-way contention, SIGKILL mid-step, SIGKILL mid-paid-call, SIGTERM,
  second signal, cross-process cancellation); SQLite 661 passed / 127 skipped.
- mypy --strict clean (47 files); layer_check 20/20; exposure_check 7/7;
  alembic check clean (no schema change).
- PR #23 was unmergeable (main moved 21 commits), so no CI had run. Merged main in (66bd1dc): all conflicts additive. After the merge, measured locally: core 938 / API 114 / concurrency 22 / worker 48 on PostgreSQL, SQLite 1072 passed / 146 skipped, mypy clean (66 files), layer_check 29/29, alembic upgrade/check/downgrade clean, worker boot smoke OK.
- CI on 66bd1dc, observed 23:02Z: 6/6 jobs success (Backend, Application starts, API contract, Frontend, Security, Parity-advisory). Backend log: core 938 passed / 118 skipped, API 114, concurrency 22, worker 48 (incl. real-process suite), SQLite 1072 / 146 -- identical to the local run.
- One unexplained worker-suite failure, seen once in ~11 runs before W8 was
  fixed (its output was lost). Not reproduced since: soak of the full worker suite
  on PostgreSQL, **0 failures in 20**, plus 9 earlier clean runs. W8 is real and
  reproduced deterministically, but not shown to be that failure (0/15 and 0/40
  targeted probes with the fix disabled). Treated as open, not closed.

## Open, needs a human

- OI-21 (was OI-6; renumbered, main uses 6-8): quota park with a paid call in flight re-issues it on resume — domain
  precedence decision, parity-covered.
- OI-22: should revoking a researcher stop the runs they started?
- OI-23: secret-redaction patterns duplicated between API and worker.

## Proposed next platform task (not started; awaiting go-ahead)

**Generalized metered-cost ledger**, ahead of OpenTelemetry: it is on Phase 4's
critical path (the first `ModelGateway` call needs somewhere to write an
`AIUsageEvent` attributed to the call), it is the only way to reconcile
`SETTLED_UNCERTAIN` spend via compensating entries, and spend is client-facing
while traces are operator convenience that JSON logs cover at v0.1. Reasoning in
`.planning/PROGRESS.md` Next #2.
