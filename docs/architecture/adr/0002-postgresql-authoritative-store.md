# ADR 0002 — PostgreSQL is authoritative, and is the v0.1 queue

**Status:** Accepted. Implemented.
**Date:** 2026-09-21 · **Reconciled:** 2026-09-22 (Architecture v2.1)

## Context

The prototype stored durable state in three SQLite files plus filesystem
artifacts. SQLite is single-writer and file-local, which blocks concurrent workers
and multi-instance deployment.

The production target is AWS: RDS PostgreSQL, S3, and a container compute service
that remains ADR-governed rather than settled here (see *Compute* below). Redis is
not being introduced.

An earlier revision of this ADR presented SQS as accepted dispatch infrastructure
for the first release. That was drift: it committed the system to operating a
second piece of infrastructure before anything had shown that PostgreSQL alone was
insufficient. This revision corrects it.

## Decision

**PostgreSQL is the durable source of truth for all workflow state, and for v0.1
it is also the queue. Workers claim runnable work transactionally in the database.
No Redis. No SQS.**

Concretely:

- A `WorkflowRun`, its `StepRun`s and every `StepAttempt` are PostgreSQL rows.
- Claiming is `SELECT … FOR UPDATE SKIP LOCKED` inside the transaction that
  records the claim, so two workers cannot hold one attempt. This is implemented
  and verified under real contention, not asserted.
- Liveness is a lease with a heartbeat. A reconciler finds attempts whose lease
  lapsed and applies the recovery table, which is what makes a worker crash
  survivable.
- Finding work is a query, not a message. A worker polls for runnable steps whose
  dependencies are satisfied and whose `runnable_after` has passed.
- Step execution is **idempotent** regardless, because a step may be re-run after
  a crash. Artifact reuse by input fingerprint is what makes that cheap: a re-run
  finds the existing artifact and makes no AI call.

### Why the database is enough at this scale

This is an internal research system: a handful of users, studies that run for tens
of minutes, work measured in hundreds of steps per day rather than thousands per
second. Polling costs an indexed query on `ix_steps_claimable`. `SKIP LOCKED` is
precisely the mechanism PostgreSQL provides for this, and it gives exactly-one
claiming without a second system that can disagree with the first.

A queue would add an operational component, a delivery-semantics problem, and a
second place where the answer to "what work exists" is kept. None of that buys
anything at this volume.

### Why not the queue as the record

A queue answers "what should happen next", not "what is true". Making a broker
authoritative would mean a retention expiry, a misconfigured dead-letter queue or
a purge could silently delete a client's in-progress study, and "why did project X
stop during stage Y" would be unanswerable, since a consumed message leaves no
history.

## SQS is a future option, not a decision

SQS may later be introduced as a **wake-up and dispatch mechanism only**, to
replace polling latency with a push. It is not part of v0.1 and must not be
assumed by any code, document or diagram.

Introducing it requires **both**:

1. **A measured trigger.** Claim contention, polling load or dispatch latency
   observed in a deployed environment and recorded with numbers. "It would scale
   better" is not a trigger.
2. **Its own ADR**, recording the measurement and the design.

Even then, the constraint below is permanent:

> **PostgreSQL remains authoritative.** A message carries an identifier, never
> state. A reconciler finds runnable work with no in-flight message and re-drives
> it, so losing the queue loses no work. Step execution stays idempotent, because
> at-least-once delivery means a duplicate must find the step already complete or
> complete it again to the same effect.

## Why no Redis

Considered for queueing and caching and rejected. PostgreSQL covers durability and
claiming, and there is no measured cache pressure. Adding Redis would be a
component to operate with no problem to solve. `docker-compose.yml` has no Redis
service, deliberately.

## Compute

The API and workers run on AWS in staging and production, and locally in
development. **Which container service is not decided in this ADR.** ECS Fargate
and App Runner both remain open; neither is frozen, and no document should present
either as settled. That choice gets its own ADR when it is made, on operational
grounds.

## Consequences

- The worker loop is a database poll, which is simple to reason about and simple
  to test. Its latency floor is the poll interval, which is acceptable for work
  measured in minutes.
- A reconciler is required, not optional, and has its own tests for the crashed
  worker case.
- Idempotency is a per-step-kind obligation and part of each step's test suite,
  not an assumption.
- If dispatch latency ever matters, the fix is additive: a wake-up path in front
  of a claiming mechanism that already works.

## Revisit when

- Claim contention or dispatch latency is **measured** to be a problem.
- Worker count grows past what a polled claim comfortably serves.
- A step kind appears whose latency requirement the poll interval cannot meet.
