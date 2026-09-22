# Durable workflows and jobs

**Status: specified, implementation in progress (Phase 3).** The behavioural
contract is `packages/aia_core/tests/test_legacy_job_store_characterization.py` —
64 tests describing the prototype's engine. Implement against that rather than
re-reading `job_store.py`.

Related: [ADR 0002](adr/0002-postgresql-authoritative-store.md) (PostgreSQL
authoritative, SQS dispatch only), [ADR 0006](adr/0006-langgraph-agent-execution.md)
(LangGraph owns reasoning, not workflow state).

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

| State | Meaning |
| --- | --- |
| `RUNNING` | Work is progressing |
| `WAITING_GATE` | A human approval or methodology gate is outstanding |
| `WAITING_BUDGET` | The study is out of money; needs a budget decision |
| `WAITING_PROVIDER` | Provider quota or capacity; will clear on its own |
| `RECOVERY_REQUIRED` | A human must decide; work may have been billed |
| `COMPLETED` | Every step succeeded |
| `FAILED` | A step failed terminally |
| `CANCELLED` | A user cancelled it |

**`WAITING_BUDGET` is new.** The prototype routed budget exhaustion through
`WAITING_USER` with an `increase_budget` approval option. "A person must decide
something" and "this study is out of money" need different dashboards and
different alerts, so they are now different states.

**`WAITING_PROVIDER`** merges the prototype's `WAITING_CREDITS` and
`WAITING_CAPACITY` at the business level — a researcher does not care which — while
the attempt's error classification retains the distinction, because the retry
behaviour differs.

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
  API                  PostgreSQL                SQS            Worker
   │                       │                      │                │
   ├─ create run ─────────►│ WorkflowRun          │                │
   ├─ create steps ───────►│ StepRun (PENDING)    │                │
   │                       │                      │                │
   │  ┌─── ONE TRANSACTION ───────────────────┐   │                │
   ├──┤ StepAttempt + budget reservation +    │   │                │
   │  │ execution state                       │   │                │
   │  └─── COMMIT ────────────────────────────┘   │                │
   ├─ enqueue (id only) ───┼─────────────────────►│ ──── claim ───►│
   │                       │◄──── lease + heartbeat ───────────────┤
   │                       │◄──── events (progress) ───────────────┤
   │                       │◄──── artifact + provenance ───────────┤
   │                       │◄──── usage + actual cost ─────────────┤
   ◄─ SSE from events ─────┤                      │                │
                           │                      │
                    reconciler ──── finds runnable work with no
                                    in-flight message, re-enqueues
```

PostgreSQL is authoritative. An SQS message carries an **identifier, never
state**. Losing the queue loses no work: the reconciler finds runnable rows and
re-enqueues them.

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
| Provider capacity or rate limit | Parked (`WAITING_PROVIDER`), not failed |
| Subscription runtime, any state | Safe retry — no marginal cost |
| Budget exhausted | `WAITING_BUDGET` |
| Human gate outstanding | `WAITING_GATE` |

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

**Idempotency.** Every step carries an idempotency key. A duplicate SQS delivery
must produce **one** execution, not two — ownership and leasing in PostgreSQL are
what enforce that, not the queue. Combined with artifact reuse by input
fingerprint, a step that does re-run produces one artifact and makes no second AI
call.

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
starving another; priority orders the queue, with creation order breaking ties so
nothing starves.

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

## Phase 3 is not complete until these pass

Against **real PostgreSQL**, with actual concurrent transactions rather than
sequential mocks:

1. **Lease and concurrency correctness.** Two workers claiming simultaneously →
   exactly one succeeds. Concurrent `recover_expired` calls. Two cancellation
   requests. An approval racing a cancellation. A retry racing another worker.
2. **Idempotency.** A duplicate wake-up produces one execution, not two.
3. **Recovery semantics.** Every row of the recovery table above.
4. **Accounting transactionality.** The attempt/reservation/state transaction
   commits or rolls back as a unit; impossible states are unrepresentable.
