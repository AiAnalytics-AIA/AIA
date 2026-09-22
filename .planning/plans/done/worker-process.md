# Worker process

**Status:** done · **Owner:** platform-runtime · **Started:** 2026-09-22 · **Finished:** 2026-09-22

## Problem

The durable engine exists — claiming, leases, heartbeats, reservations, gates,
recovery — but nothing drives it. `PROGRESS.md` Next #2 and
`docs/architecture/workflows.md` § "Still owed" both name the missing loop:
`claim_next` → execute → `complete_attempt` / `fail_attempt`, with heartbeats and
a cancellation poll. Until it exists no step executes outside a test, and the
only place work *could* run is an API request, which the architecture forbids.

Reading the engine as a worker would drive it surfaced eight defects that a worker
would turn from latent into live. Each is reproduced by a test in the chunk that
fixes it; none is reachable today only because nothing calls these methods
concurrently yet.

| # | Defect | Anchor @ 17c0a6b |
|---|---|---|
| W1 | **An expired lease can be resurrected.** `heartbeat` reads the attempt, checks it, then writes by primary key. A reconciler that expires the attempt between the read and the write is overwritten: the attempt goes back to `EXECUTING` while its step is `RUNNABLE`, and a second worker claims it | `workflow_repository.py:575-585` |
| W2 | **A stale worker can complete a step it no longer owns.** `complete_attempt` / `fail_attempt` / `abandon_attempt` check neither the owner nor the attempt status. A worker whose lease was recovered and re-claimed can still mark the step `SUCCEEDED` | `workflow_repository.py:846-880`, `897-917`, `1085-1107` |
| W3 | **Completion is not idempotent.** A second `complete_attempt` (a retried commit whose first ack was lost) charges `actual_cost_usd` to the study again | `workflow_repository.py:857-859` |
| W4 | **Cancellation leaks the budget hold.** `abandon_attempt` never touches reservations, so a cancelled paid step leaves its reservation `RESERVED` forever and the study's available budget shrinks permanently | `workflow_repository.py:1083-1107` |
| W5 | **Known spend is dropped on a later failure.** A call whose outcome and cost were recorded (`mark_paid_call_outcome_known`) and whose attempt then fails has its reservation *released*, so the money spent is never charged | `workflow_repository.py:931-933` |
| W6 | **Nothing resumes a provider park.** `WAITING_PROVIDER` and `WAITING_CAPACITY` are not `RUNNABLE`, and no code moves them back; the existing test simulates an operator with `force_step_status` | `test_workflow_engine.py::test_a_parked_quota_step_becomes_claimable_after_its_reset_time` |
| W7 | **A cancelled run whose worker died never finishes.** `request_cancel` leaves a `RUNNING` step for its worker; if the worker dies, recovery returns `RETRY`, the step goes `RUNNABLE` with `cancel_requested` set, `claim_next` never picks it, and the run reads `RUNNING` forever. Found while designing chunk 3 | `workflow_repository.py:1003-1026`, `claim_next` filter at `461` |
| W8 | **Two steps of one run finishing together strand the run.** Each finishing transaction derives the run's status, and releases blocked dependants, from a READ COMMITTED snapshot in which the *other* step is still `RUNNING`. The run then reads `RUNNING` forever with every step `SUCCEEDED`, and a diamond's join step stays `BLOCKED` with nothing left to run. Found in chunk 7 while chasing a worker-suite failure | `workflow_repository.py:336-383` (`_refresh_run`), `385-428` (`release_ready_steps`) |

## Approach

**The lease is the fence.** Every write a worker makes about an attempt —
heartbeat, complete, fail, abandon, release, per-call metering — names the
`worker_id`, locks the attempt row, and proceeds only while that worker still
holds the lease. The deadline is only the *trigger* for recovery; ownership is the
row's status plus its `worker_id`, checked under the row lock. A heartbeat is a
single conditional `UPDATE … WHERE worker_id = :w AND status IN (CLAIMED,
EXECUTING)`, so there is no read-then-write window to lose.

**A cross-study queue, and a scope issued from the lease.** `WorkflowRepository`
is study-scoped and stays that way. A worker must find work in any study, so a
narrow `WorkQueue` exposes exactly the four cross-study operations the loop needs
— claim, recover expired, resume parked, refuse — and nothing that reads
research data. After a claim, `ScopeResolver.execution_context(attempt_id,
worker_id)` issues the `StudyContext` the worker uses for everything else. The
resolver derives scope from the persisted attempt → step → run → study rows and
refuses unless the lease is held, so the capability is the lease: nothing in the
process can get a context for a study it has not claimed work in.

The execution context carries the **RESEARCHER** permission set — doing the work,
never approving it — so neither the worker nor any executor running inside it can
decide a gate or raise a budget. Its actor is the run's `triggered_by`, which is
what makes the separation-of-duties check on gates the worker opens compare
against the human who started the run.

**A narrow executor seam.** `aia_worker.executor` defines `StepExecutor` (one
method: `execute(step, context) -> StepOutcome`) and `StepContext` (checkpoint,
per-call metering, progress, a lease-fenced transaction, the scope). Executors
are registered by step `kind` at composition time from an import path in config.
The worker claims only kinds it has executors for, so a rolling deploy that adds
a kind never has an old worker claim and fail it. The worker imports nothing
domain-specific; `layer_check` enforces that.

**Per-call metering.** Budget is reserved, dispatched and settled per provider
call through the context, each step committed on its own before the call it
guards — the "attempt + reservation before dispatch" invariant, kept at call
granularity. At attempt end every still-open reservation is closed by one rule:
dispatched with unknown outcome → `SETTLED_UNCERTAIN`; known spend not yet
charged → settled at that amount; otherwise released.

**Shutdown releases, termination recovers.** On `SIGTERM` the worker stops
claiming and asks the executor to stop at its next checkpoint; the attempt is
then *released* — `ABANDONED`, step back to `RUNNABLE`, attempt not consumed —
unless a paid call is in flight with unknown outcome, in which case it is
`RECOVERY_REQUIRED` exactly as a crash would be. A second signal, or a `SIGKILL`,
leaves the lease to lapse and the reconciler applies the ordinary recovery
table. Both paths keep ownership semantics: at no point do two workers hold one
attempt.

**Every worker is also a reconciler.** Recovery of expired attempts and resumption
of provider parks run on an interval inside each worker. Both are already safe to
run concurrently (`FOR UPDATE SKIP LOCKED`), so no separate reconciler process is
needed for v0.1.

Rejected alternatives:

- *A system `StudyContext` for all studies.* One object that can read every
  client's research is exactly the widening the scope model exists to prevent.
- *Re-resolving the triggering user's grant on every attempt.* Attractive — a
  revoked researcher's runs would stop — but a denial then has no scoped
  repository to record itself through, and it turns an access-policy question
  into a worker failure mode. Filed as OI-7 rather than decided here.
- *Fencing only when `worker_id` is passed.* A guard on one path only (A8). The
  argument is required.

## Trade-off accepted

Execution is at-least-once, not exactly-once: a worker that stalls past its lease
can have run an executor whose result is then discarded, so executors must be
idempotent (artifact reuse by fingerprint makes that cheap); what the engine
guarantees is one *recorded* completion, one charge per call, and no automatic
re-run of a possibly-billed call.

## Chunks

- [x] 1. **Fence the lease** (W1, W2, W3). *Landed.* W1 reproduced against
  `origin/main` @ 17c0a6b — the old heartbeat returned `True` on a recovered
  attempt — by
  `test_workflow_concurrency.py::test_regression_a_heartbeat_cannot_resurrect_an_attempt_recovered_under_it`;
  W2/W3 by `test_workflow_lease_fencing.py`. `LeaseLost`; conditional heartbeat;
  `worker_id` required on complete / fail / abandon, checked under a row lock;
  idempotent completion; `ClaimedWork` carries the worker and scope ids. Tests:
  engine (sequential) + concurrency (the resurrection race, stale completion after
  re-claim).
- [x] 2. **Close reservations at attempt end** (W4, W5). One closing rule for
  complete, fail, abandon and recovery; `settle_paid_call` for per-call metering;
  the lease fence extended to `reserve_budget` and both `mark_paid_call_*`.
  *Landed.* Reproduced against `origin/main` @ 17c0a6b: cancelling a $5 paid step
  left `reserved_usd` at 5.0 for good (W4); a known $1.80 call followed by a
  failure recorded `spent_usd` 0.0 (W5). Tests: `test_workflow_reservations.py`.
  Filed OI-6 (a quota park can re-issue a call whose outcome is unknown).
- [x] 3. **Release and resume** (W6, W7). Domain: `decide_release`,
  `apply_cancellation`, `resume_due`, `RecoveryAction.CANCEL`. Repository:
  `release_attempt`, `resume_waiting_steps`; `_apply_recovery` lets a
  mid-attempt cancellation win. *Landed.* W7 reproduced against `origin/main`
  @ 17c0a6b (recovery → `RETRY`, run `RUNNING`, step unclaimable). Tests:
  `test_workflow_release_and_resume.py`. `decide_recovery` itself is unchanged;
  the parity suite could not be run here (OI-1).
- [x] 4. **Cross-study queue and execution scope.** `WorkQueue` (claim with a
  kind filter, recover, resume, refuse); `ScopeResolver.execution_context`
  (`EXECUTION_ROLE` = RESEARCHER; actor = `triggered_by`; refuses a non-holder, a
  finished attempt, a run/study scope mismatch and an archived client);
  `decided_gates`. Uncertain exposure is now charged to the reservation's own
  study. *Landed.* Tests: `test_work_queue.py`. Filed OI-7 (should revoking a
  researcher stop their runs?).
- [x] 5. **`apps/worker`.** *Landed.* `aia_worker.executor` (the protocols and
  outcomes; `StopExecution` is a `BaseException` so `except Exception` cannot
  swallow a cancellation), `context`, `heartbeat`, `worker`, `settings`,
  `registry`, `observability`, `__main__`, `testing`. Repository gained
  `assert_lease` and `record_progress`. Tests: `apps/worker/tests/test_worker_loop.py`,
  `test_worker_settings.py`. Executor protocol, context, heartbeat thread, loop,
  typed settings, CLI, test executors. In-process tests on SQLite and PostgreSQL:
  success, retryable / non-retryable failure, possibly-billed failure, budget,
  gate, cancellation, lease loss, idempotent completion, graceful shutdown.
- [x] 6. **Multi-process tests on PostgreSQL.** *Landed.*
  `apps/worker/tests/test_worker_processes.py`: three processes over twelve paid
  steps (one execution, one attempt and one charge per step; ≥2 processes did
  work); `SIGKILL` mid-step (recovered, finished by another); `SIGKILL` mid-paid-
  call (`RECOVERY_REQUIRED`, charged once, never retried); `SIGTERM` (released at
  once, attempt not consumed, exit 0); second signal (exit 130, lease recovered);
  cross-process cancellation. Measured: 48/48 worker tests passing in three
  consecutive runs on PostgreSQL 16, ~27 s each. Two and more `python -m aia_worker`
  processes contending; `SIGKILL` mid-step; `SIGTERM` mid-step; no double
  execution, no double charge.
- [x] 7a. **Serialise step transitions per run** (W8). `_lock_run` — the run row,
  taken before any step row, in completion, failure, recovery, release,
  abandonment and gate transitions; the resume sweep skips a locked run; the
  reconciler selects only lapsed leases on PostgreSQL and orders by run. Reproduced
  deterministically by
  `test_workflow_concurrency.py::test_regression_the_last_two_steps_finishing_together_complete_the_run`
  and `…::test_regression_a_join_step_is_released_when_both_parents_finish_together`
  (both fail with the lock disabled, pass with it). **Not** shown to be the cause
  of the one unexplained worker-suite failure seen during chunk 7: with the lock
  disabled, 0 of 15 contention runs and 0 of 40 two-step runs across two real
  processes stranded a run.
- [x] 7. **Wiring and documents.** *Landed.* Makefile (`dev-worker`,
  `test-worker`; worker in lint, format, typecheck, verify); CI (install, lint,
  one mypy run over all trees, worker suite with `AIA_REQUIRE_POSTGRES=1`, worker
  in the SQLite run, a boot-and-`SIGTERM` smoke that also fails on any `ERROR`
  line); eight new `layer_check` rules (20/20, each shown to fail on a probe
  violation); `ARCHITECTURE.md` §2/§3/§5/§7/§8, `CLAUDE.md` map and commands,
  `AGENTS.md` (lost-update read-check-write, stale identity map under
  `FOR UPDATE`, in-memory SQLite and threads, an unclosed session hanging
  teardown, `py.typed` and mypy, `BaseException` for control flow),
  `workflows.md` § The worker, the architecture README, board spec, module
  inventory, migration status, `PROGRESS.md`, OI-6/7/8.

## Review outcome

Not yet reviewed by a human; nothing has been committed (the session was refused
`git commit`, as CLAUDE.md §5 requires without explicit permission). Follow-ups
filed rather than done: OI-6 (a quota park can re-issue an in-flight paid call —
domain precedence, parity-covered), OI-7 (should revoking a researcher stop their
runs), OI-8 (redaction patterns defined twice).

### Layer-by-layer review map

Walk it in this order; each file's tests sit beside it.

| Layer | Changed / new file | What changed | Tests |
|---|---|---|---|
| 1 Domain | `packages/aia_core/src/aia_core/domain/workflow.py` | `decide_release`, `apply_cancellation`, `resume_due`, `RecoveryAction.CANCEL`, two back-off constants. `decide_recovery` untouched | `packages/aia_core/tests/test_workflow_release_and_resume.py` |
| 2 Application | `packages/aia_core/src/aia_core/application/scope.py` | `ScopeResolver.execution_context`, `EXECUTION_ROLE` | `packages/aia_core/tests/test_work_queue.py` |
| 3 Infrastructure | `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py` | `LeaseLost`; lease fence on every attempt write; conditional heartbeat; idempotent completion; `settle_paid_call`; the reservation closing rule; `release_attempt`; `resume_waiting_steps`; `_lock_run`; `assert_lease`; `record_progress`; `decided_gates`; kind filter; `WorkQueue` | `test_workflow_lease_fencing.py`, `test_workflow_reservations.py`, `test_workflow_release_and_resume.py`, `test_work_queue.py`, `test_workflow_concurrency.py` (W1, W2 race, W8), `test_workflow_engine.py` (call sites only) |
| 4 Worker | `apps/worker/pyproject.toml`, `src/aia_worker/{__init__,__main__,executor,context,heartbeat,worker,settings,registry,observability,testing}.py` | The package | `apps/worker/tests/test_worker_loop.py`, `test_worker_settings.py`, `test_worker_processes.py` |
| 5 Transport | — | Unchanged; `layer_check` now forbids it executing steps | — |
| Tooling | `Makefile`, `.github/workflows/ci.yml`, `tools/layer_check.sh` | Worker wired in; eight layer rules | `./tools/layer_check.sh` |
| Documents | `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `docs/architecture/{workflows,README,boards-v2.2-content-spec}.md`, `docs/migration/{module-inventory,status}.md`, `.planning/{PROGRESS,open-items}.md` | As in chunk 7 | — |
