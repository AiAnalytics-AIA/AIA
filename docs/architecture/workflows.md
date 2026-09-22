# Durable workflows and jobs

**Status: implemented and verified under real PostgreSQL contention.**
`WorkflowRun → StepRun → StepAttempt`, claiming, leases, reservations, gates and
the full recovery table are in `aia_core.domain.workflow` and
`aia_core.infrastructure.workflow_repository`. What remains is a worker process to
drive them and the AI runtime the steps will call.

The behavioural contract is
`packages/aia_core/tests/test_legacy_job_store_characterization.py` — 64 tests
describing the prototype's engine.

Related: [ADR 0002](adr/0002-postgresql-authoritative-store.md) (PostgreSQL
authoritative and, for v0.1, the queue itself),
[ADR 0006](adr/0006-langgraph-agent-execution.md) (LangGraph owns reasoning, not
workflow state).

## The requirement

A research project runs 24 pipeline nodes, several making hundreds of AI calls
over tens of minutes. Work must survive browser closure, API restart, worker
termination, provider failure and temporary quota exhaustion. A browser
disconnect must have **no effect** on a job.

That rules out doing the work in a request handler, and rules out holding
progress in memory.

## Two levels of state

The prototype used one 14-value status for both "what is this study waiting for"
and "what is this execution doing", which muddled `RECOVERY_REQUIRED` with
ordinary failure. The new model separates them.

### `WorkflowRun` — business state

What a researcher or an operator sees. Answers *what is this study waiting for?*

| State | Meaning | Clears when |
| --- | --- | --- |
| `PENDING` | Created, nothing claimed yet | A worker claims a step |
| `RUNNING` | Work is progressing | — |
| `AWAITING_GATE` | A human approval or methodology gate is outstanding | **A person decides** |
| `AWAITING_BUDGET` | The study is out of money; needs a budget decision | **A person decides** |
| `WAITING_PROVIDER` | Provider quota exhausted; the account may not call yet | A reset instant passes |
| `WAITING_CAPACITY` | The provider has no capacity right now | By itself, usually in minutes |
| `RECOVERY_REQUIRED` | A human must decide; work may have been billed | **A person decides** |
| `COMPLETED` | Every step succeeded | — |
| `FAILED` | A step failed terminally | — |
| `CANCELLED` | A user cancelled it | — |

**The two prefixes are the contract.** `AWAITING_*` means a person owes us a
decision and nothing moves until somebody acts. `WAITING_*` means a system owes us
capacity and it will clear on its own. A dashboard that mixes them cannot tell an
operator whether to go and find somebody, which is the only question an operator
is actually asking. `needs_attention` is exactly the `AWAITING_*` set plus
`RECOVERY_REQUIRED`.

**`AWAITING_BUDGET` is new.** The prototype routed budget exhaustion through
`WAITING_USER` with an `increase_budget` approval option. "A person must decide
something" and "this study is out of money" need different dashboards and
different alerts, so they are now different states.

**`WAITING_PROVIDER` and `WAITING_CAPACITY` are separate, deliberately.** An
earlier draft merged them on the grounds that a researcher does not care which.
That was wrong operationally: quota is an entitlement wall that clears at a reset
instant and may warrant raising a limit, capacity is an overload that clears by
itself. Merged, a quota wall looks like a blip so nobody raises the limit, and a
blip looks like a quota wall so somebody is paged for nothing. Only the quota park
carries a `runnable_after`, which is the difference made visible.

### `StepAttempt` — technical execution state

What one execution of one step is doing. Answers *what is this worker doing?*

| State | Meaning |
| --- | --- |
| `PENDING` | Created, not yet claimed |
| `CLAIMED` | A worker holds the lease |
| `EXECUTING` | Running, heartbeating |
| `SUCCEEDED` | Finished; output committed |
| `FAILED` | Finished unsuccessfully |
| `EXPIRED` | The lease lapsed; the worker is presumed dead |
| `ABANDONED` | Superseded, e.g. cancelled mid-flight |

Keeping these apart is what stops `RECOVERY_REQUIRED` — a business condition
needing a human — from looking like an ordinary `FAILED` attempt.

### The model

```
WorkflowRun            business state, one per run of a pipeline
└── StepRun            one pipeline node; the record that a step is done
    └── StepAttempt    append-only history; one row per execution attempt
```

**Attempts are append-only history, never overwritten retries.** The prototype
kept an `attempt` integer and only the most recent error, so a step that failed
three different ways retained one. Each attempt now has its own row with its own
error, provider, model, cost and timing.

## Shape

```
  API                  PostgreSQL                          Worker
   │                       │                                  │
   ├─ create run ─────────►│ WorkflowRun                      │
   ├─ create steps ───────►│ StepRun (BLOCKED / RUNNABLE)     │
   │                       │                                  │
   │                       │◄── SELECT … FOR UPDATE SKIP ─────┤  claim
   │                       │    LOCKED, in the same           │
   │                       │    transaction as the claim      │
   │                       │                                  │
   │  ┌─── ONE TRANSACTION ───────────────────┐               │
   │  │ StepAttempt + budget reservation +    │◄──────────────┤
   │  │ execution state                       │               │
   │  └─── COMMIT ────────────────────────────┘               │
   │                       │◄──── lease + heartbeat ──────────┤
   │                       │◄──── events (progress) ──────────┤
   │                       │◄──── artifact + provenance ──────┤
   │                       │◄──── usage + actual cost ────────┤
   ◄─ SSE from events ─────┤                                  │
                           │
                    reconciler ──── finds attempts whose lease lapsed
                                    and applies the recovery table
```

**There is no broker.** PostgreSQL is authoritative *and* is the queue: finding
work is an indexed query on `ix_steps_claimable`, and claiming it is
`SELECT … FOR UPDATE SKIP LOCKED` inside the transaction that records the claim.
Two workers cannot hold one attempt, and there is no second system that can
disagree with the first about what work exists.

At this volume — a handful of users, studies measured in tens of minutes — a queue
would add an operational component, a delivery-semantics problem and a second
place where the truth is kept, and buy nothing. SQS may later be added as a
**wake-up only**, after a measured trigger and its own ADR; PostgreSQL stays
authoritative even then. See
[ADR 0002](adr/0002-postgresql-authoritative-store.md).

## Accounting transactionality

The transaction boundary is the part most worth getting right, because the
failure mode is a lie about money.

**Before any external dispatch, in one transaction:**

```
create StepAttempt
+ reserve budget
+ mark execution state
COMMIT
```

Only then is the provider called. Reconciliation of actual usage and cost happens
after the response.

This makes two impossible states hard to represent:

- *a provider was called but no attempt exists* — the attempt is committed first;
- *usage recorded with no corresponding study or run* — usage rows carry
  `organization_id`, `client_id`, `study_id`, `workflow_run_id` and
  `step_run_id`, all non-null.

## Recovery semantics

Every case is distinguished, because the distinctions are part of the product.

| Situation | Outcome |
| --- | --- |
| Free deterministic step crashes | Safe retry |
| Paid call crashes **before** dispatch | Safe retry (reservation released) |
| Paid call **known rejected** by the provider | Safe retry per policy |
| Paid call **possibly accepted** | **`RECOVERY_REQUIRED`** + `SETTLED_UNCERTAIN` |
| Provider quota exhausted | Parked (`WAITING_PROVIDER`) with a resume instant, not failed |
| Provider capacity unavailable | Parked (`WAITING_CAPACITY`), not failed |
| Subscription runtime, any state | Safe retry — no marginal cost |
| Budget exhausted | `AWAITING_BUDGET` |
| Human gate outstanding | `AWAITING_GATE` |

A capacity failure arriving **after** a metered call was dispatched still reaches
`RECOVERY_REQUIRED`, not a capacity park: the billing question outranks the
provider condition, and a test asserts that ordering rather than trusting it.

### The uncertain paid call

Carried over from the prototype and treated as a fundamental invariant.

```
reserve $2  →  send paid provider call  →  worker dies  →  lease expires
```

Three possibilities, and the system **cannot** know which:

- the provider never received it;
- the provider processed it but the response was lost;
- the provider processed it and billing occurred.

So:

```
automatic retry  = possible double billing
assume success   = possible missing output
assume failure   = an accounting lie
```

`RECOVERY_REQUIRED` + `SETTLED_UNCERTAIN` is the only responsible answer: park it,
record the reservation as uncertain *actual* exposure so the budget reflects money
that may already be gone, and let a researcher decide.

**The UI must surface this plainly**, not as a generic error:

> **Manual recovery required.** The provider call may have been billed, but its
> result was not safely recorded. A researcher must choose whether to retry.
>
> | | |
> |---|---|
> | Reserved | $2.00 |
> | Known usage | unknown |
> | Accounting | $2.00 uncertain |
> | Retry cost | up to +$2.00 |

A `provider_request_id` on every `ModelResult` ([ADR 0005](adr/0005-llm-gateway.md))
is what may later let an uncertain call be reconciled to a fact.

## Guarantees and how each is achieved

**Idempotency.** Every run carries an idempotency key, and a step re-run after a
crash must produce **one** execution, not two — ownership and leasing in
PostgreSQL are what enforce that. It stays an obligation of every step kind even
without a queue, because a recovered attempt is a re-run. Combined with artifact
reuse by input fingerprint, a step that does re-run produces one artifact and makes
no second AI call.

**Exclusive claiming.** `SELECT … FOR UPDATE SKIP LOCKED`, or an equivalent
conditional update. Two workers cannot hold one attempt.

**Heartbeats and expiry.** An executing attempt updates `heartbeat_at`. A
reconciler moves attempts whose lease lapsed to `EXPIRED` and applies the recovery
table above.

**Retry classification.** Errors are classified before any retry, reusing the
prototype's taxonomy. Authentication and permission failures are **permanent** —
retrying burns quota and hides a misconfiguration. Quota is not a retry at all; it
is a park, and it **resets the attempt counter**, because a quota pause is not a
failed attempt and counting it would eventually fail a project that was only
waiting.

**Cooperative cancellation.** `cancel_requested` is a flag the worker polls at
checkpoints, so cancellation leaves a consistent artifact state rather than a
half-written one.

**Dependency gating.** A dependant waits for `SUCCEEDED` specifically, not merely
a terminal state, so a failed upstream step stalls the pipeline instead of letting
downstream work run on missing inputs.

**Concurrency limits and priority.** Per-organization caps stop one tenant
starving another; priority orders the claim query, with creation order breaking
ties so nothing starves.

## Gates and approval

A gate is a durable row, not a graph interrupt: it may sit unanswered for days and
must survive a deploy. Deciding one requires `APPROVE_GATE`, the option must be one
of those offered, and a decided gate cannot be re-decided by a replayed request.

**Independent review is the default, and it is configurable.** For an `approval`
gate the decider must not be the producer, *unless* self-approval has been
explicitly enabled for that scope. The policy resolves
`study > client > organization > false` and arrives on the server-issued
`StudyContext`, so no request payload, tool argument or model output can assert it.
Policy removes the independence objection; it never confers authority, so someone
who could not approve still cannot. See
[scope-and-authorization.md](scope-and-authorization.md).

Gates that are not approvals — a clarification, a methodology question — record the
same facts without enforcing independence, because the producer is frequently the
only person who can answer.

Every gate decision and artifact sign-off is appended to `approval_decisions`:
producer, approver, whether it was self-approved, the effective policy and which
level set it, the exact subject, the decision, the basis and the timestamp. The
gate row holds the decision that stands; only the ledger can say what the rules
were at the time.

## The research DAG

`workflow_engine.STANDARD` in the prototype is the canonical definition — 24
nodes with kind, interaction mode, dependencies, stage and artifact target —
carried over as data:

```
compile → research → design → questionnaire → audience → dimensions → sample
        → preflight → run → aggregate → donor_qc
        → analysis_executive → analysis_research_questions → analysis_objects
        → analysis_audience → analysis_segments → analysis_hypotheses
        → analysis_implications → analysis_limitations
        → interpret → verify → alignment → report → delivery
```

Two details to keep:

- **`preflight` is `review_if_warning`**, not `auto`. A methodological warning
  pauses for a human.
- **Analysis is eight separate nodes**, each independently durable, so a quota
  pause after `analysis_segments` resumes at `analysis_hypotheses` instead of
  recomputing five modules of AI work.

## Progress reporting

Attempts emit events. The API exposes them over Server-Sent Events; the client
reconnects and rebuilds state from the server rather than holding it locally.
Event ids are monotonic, which is what lets a reconnecting client resume without
gaps or duplicates.

**Progress must not be invented.** Real elapsed time, real state transitions, real
counts (respondent 240 of 300), and an empirical range for typical duration. No
synthesised percentage the backend cannot know — a fabricated bar stalling at 90%
is worse than an honest timer.

SSE over WebSockets: traffic is server-to-client only, SSE reconnects
automatically, and it survives ordinary HTTP infrastructure.

## What was proved, and what is still owed

These passed against **real PostgreSQL**, with actual concurrent transactions
rather than sequential mocks, and they are what makes the engine trustworthy:

1. **Lease and concurrency correctness.** Two workers claiming simultaneously →
   exactly one succeeds. Concurrent `recover_expired` calls. Two cancellation
   requests. An approval racing a cancellation. A retry racing another worker.
2. **Idempotency.** A duplicate wake-up produces one execution, not two.
3. **Recovery semantics.** Every row of the recovery table above.
4. **Accounting transactionality.** The attempt/reservation/state transaction
   commits or rolls back as a unit; impossible states are unrepresentable.

Still owed, and not to be described as done anywhere:

- **A worker process.** `claim_next` → execute → `complete_attempt` /
  `fail_attempt`, with heartbeats and a cancellation poll at checkpoints. The
  engine it would drive exists; the loop does not.
- **The AI runtime the steps call.** See
  [ai-runtime.md](ai-runtime.md) and [ADR 0005](adr/0005-llm-gateway.md).
- **A generalized metered-cost ledger.** Budget reservations and `Study.spent_usd`
  are implemented and enforce spending; attribution down to
  `Client → Study → Revision → WorkflowRun → Step → Agent/Tool/Call` across every
  metered source is not. See [ai-runtime.md](ai-runtime.md) § Cost accounting.
