# Durable workflows and jobs

**Status: designed, not yet implemented.** This document is the specification for
Phase 3. The domain state machine it describes is already encoded in
`aia_core.domain.pipeline.StageStatus`; the job engine around it is not built.

## The requirement

A research project runs 24 pipeline nodes, several of which make hundreds of AI
calls and take tens of minutes. Work must survive:

- browser reload or tab close
- API process restart or redeploy
- worker crash or rescheduling
- provider rate limits and quota exhaustion
- temporary provider capacity failures
- database failover

A browser disconnect must have **no effect** on a job. This rules out doing the
work in an HTTP request handler, and it rules out holding progress state in
memory.

## Shape

```
  API                  PostgreSQL              Redis            Worker
   │                       │                     │                 │
   ├─ create workflow ────►│ workflows           │                 │
   ├─ create jobs ────────►│ jobs (QUEUED)       │                 │
   ├─ enqueue ─────────────┼────────────────────►│ ──── claim ────►│
   │                       │◄──── lease + heartbeat ───────────────┤
   │                       │◄──── job_events (PROGRESS) ───────────┤
   │                       │◄──── artifact + provenance ───────────┤
   │                       │◄──── stage transition ────────────────┤
   ◄─ SSE from events ─────┤                     │                 │
```

PostgreSQL is authoritative. Redis is transport and ephemeral coordination only:
if Redis is lost, no work is lost — jobs are still `QUEUED` in PostgreSQL and are
re-enqueued by a reconciler.

## Job state machine

```
                  ┌──────────────────┐
                  │      DRAFT       │  created with the workflow graph
                  └────────┬─────────┘
                           │ activate
              ┌────────────▼────────────┐
              │   WAITING_DEPENDENCY    │◄──── upstream not COMPLETED
              └────────────┬────────────┘
                           │ dependencies satisfied
                    ┌──────▼──────┐
              ┌────►│   QUEUED    │
              │     └──────┬──────┘
              │            │ worker claims (lease acquired)
              │     ┌──────▼──────┐
              │     │   RUNNING   │──── heartbeat every 10s
              │     └──┬───┬───┬──┘
              │        │   │   │
     retry    │        │   │   └──────────────► COMPLETED
     (classified       │   │
      as transient)    │   └──► WAITING_CREDITS   (subscription quota)
              │        │        WAITING_CAPACITY  (provider capacity)
              │        │        WAITING_USER      (approval / over budget)
              └────────┤             │
                       │             │ condition cleared or user decides
                       │             └──────────► QUEUED
                       │
                       ├──► FAILED     (terminal, classified as permanent)
                       └──► CANCELLED  (user requested)

     RUNNING with a stale lease ──► RECOVERY_REQUIRED ──► QUEUED
```

### The waiting states are not errors

This is the most important distinction in the model. A job in `WAITING_CREDITS`
has not failed; it is parked until the subscription quota resets, and the user
sees "continues at 14:00", not an error. The prototype's behaviour, which we
preserve:

| State | Trigger | Recovery |
| --- | --- | --- |
| `WAITING_CREDITS` | Claude Code subscription usage limit | Lease cleared, retry counter **reset**, one-time resume scheduled at `quota_reset_at` |
| `WAITING_CAPACITY` | Recoverable provider capacity error | Backoff, then re-queue |
| `WAITING_USER` | Approval needed, or budget would be exceeded | Waits indefinitely for an explicit decision |

Resetting the retry counter on quota matters: a quota pause is not a failed
attempt, and counting it would eventually exhaust `max_attempts` and fail a
project that was only waiting.

## Guarantees and how each is achieved

**Idempotency.** Every job carries a unique `idempotency_key`. Creating a
workflow with a key that already exists returns the existing workflow rather than
duplicating it. Combined with artifact fingerprint reuse, a job that runs twice
produces one artifact.

**Leasing.** A worker claims a job by writing `lease_owner` and `lease_until`
inside a transaction. Two workers cannot hold the same job.

**Heartbeats and stalled recovery.** A `RUNNING` job updates `heartbeat_at`. A
reconciler moves jobs whose lease expired to `RECOVERY_REQUIRED`, then re-queues
them. This is what makes a worker crash survivable.

**Retry classification.** Errors are classified before any retry, reusing the
prototype's taxonomy from `ai_router.classify_provider_exception`:
`MISSING`, `AUTHENTICATION`, `PERMISSION`, `QUOTA`, `MODEL`, `SCHEMA`,
`TRANSPORT`, `SDK_OUTDATED`, `MAX_TURNS`, `OTHER`. Authentication and permission
failures are permanent and must not be retried — retrying them burns quota and
hides a configuration problem. Quota is not a retry at all; it is a park.

**Cancellation.** `cancel_requested` is a flag the worker polls at checkpoints,
so cancellation is cooperative and leaves a consistent artifact state rather than
killing a process mid-write.

**Cost reservation.** Before a paid call, the job reserves its estimate against
the project budget. Reservations count as spent, so two concurrent workers cannot
each pass the budget check and collectively overspend. The reservation is settled
with the actual cost afterwards.

**Concurrency limits and priority.** Per-organization concurrency caps stop one
tenant starving another; `priority` orders the queue.

## The research DAG

The prototype's `workflow_engine.STANDARD` is the canonical definition — 24 nodes
with their kind, interaction mode, dependencies, stage and artifact target. It is
carried over as-is:

```
compile → research → design → questionnaire → audience → dimensions → sample
        → preflight → run → aggregate → donor_qc
        → analysis_executive → analysis_research_questions → analysis_objects
        → analysis_audience → analysis_segments → analysis_hypotheses
        → analysis_implications → analysis_limitations
        → interpret → verify → alignment → report → delivery
```

Two details worth keeping:

- **`preflight` has interaction mode `review_if_warning`**, not `auto`. A
  methodological warning pauses for a human rather than proceeding.
- **Analysis is eight separate nodes**, each an independently durable job. A quota
  pause after `analysis_segments` resumes at `analysis_hypotheses` instead of
  recomputing five modules of AI work.

## Progress reporting

Jobs emit `PROGRESS` events into `job_events`. The API exposes them over
Server-Sent Events; the client reconnects and rebuilds state from the server
rather than holding it locally.

**Progress must not be invented.** The prototype is explicit about this and the
rule stands: show real elapsed time, real stage transitions, real counts
(respondent 240 of 300), and an empirical range for typical duration. Do not
synthesise a percentage the backend cannot know. A fabricated progress bar that
stalls at 90% is worse than an honest elapsed timer.

SSE is chosen over WebSockets because the traffic is server-to-client only, SSE
reconnects automatically, and it survives ordinary HTTP infrastructure. The
decision is revisitable if interactive features later need a duplex channel.

## What is reused from the prototype

`job_store.py` is genuinely good work: 10 tables with leases, heartbeats,
idempotency keys, cost reservations, approvals and cron-style schedules. The
*design* survives the migration; only SQLite is replaced. Phase 3 should port its
schema and semantics rather than redesign them, and characterization tests should
be written against its state transitions first.
