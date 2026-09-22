# ADR 0002 — PostgreSQL is authoritative; SQS is dispatch only

**Status:** Accepted. PostgreSQL implemented; SQS pending Phase 3.
Compute target amended 2026-09-22 (ECS Fargate → App Runner).
**Date:** 2026-09-21

## Context

The prototype stored durable state in three SQLite files plus filesystem
artifacts. SQLite is single-writer and file-local, which blocks concurrent
workers and multi-instance deployment.

AWS is the production target: RDS PostgreSQL, S3, SQS, and App Runner for
the API and workers (amended 2026-09-22 — see below). Redis is explicitly
not being introduced yet.

## Decision

**PostgreSQL is the durable source of truth for all workflow state. SQS is a
dispatch mechanism and must never become the only record that work exists.**

Concretely, for Phase 3:

- A `WorkflowRun`, its `StepRun`s and every `StepAttempt` are PostgreSQL rows,
  written before anything is enqueued.
- An SQS message carries an identifier, never state.
- A reconciler finds runnable work in PostgreSQL that has no in-flight message
  and re-enqueues it. Losing the queue therefore loses no work.
- Step execution is **idempotent**, because SQS delivers at least once. A
  duplicate delivery must find the step already complete, or complete it again to
  the same effect. Artifact reuse by input fingerprint is what makes this cheap:
  a re-run finds the existing artifact and does no AI call.

## Why not the queue as the record

A queue answers "what should happen next", not "what is true". Making SQS
authoritative would mean a message-retention expiry, a misconfigured dead-letter
queue or a purge could silently delete a client's in-progress study. It would also
make "why did project X stop during stage Y" unanswerable, since a consumed
message leaves no history.

## Why no Redis yet

It was considered for queueing and caching and deliberately deferred. SQS covers
dispatch, PostgreSQL covers durability, and there is no measured cache pressure
yet. Adding Redis now would be a component to operate with no problem to solve.
`docker-compose.yml` should drop its Redis service to match.

## Consequences

- Every enqueue is preceded by a database write: slightly slower, and correct.
- A reconciler is required, not optional, and needs its own tests for the
  lost-message case.
- Idempotency is a per-step-kind obligation and must be part of each step's test
  suite, not assumed.

## Amendment — 2026-09-22: App Runner replaces ECS Fargate

The original context named **ECS Fargate** as the compute target. That is amended
to **AWS App Runner in `eu-central-1`**. Nothing else in this ADR changes: the
PostgreSQL-authoritative / SQS-dispatch-only decision is independent of where
containers run.

**Why.** The team is one engineer, the first client study is 2–3 months out, and
44k lines of validated Python are still being ported. ECS Fargate brings a VPC,
subnets, security groups, task definitions, an ALB and a Terraform estate — all of
which must be built, operated and patched by the same person writing the domain
code. App Runner delivers managed containers, TLS and autoscaling with none of
that surface, while staying inside AWS alongside Bedrock, Cognito and RDS, which
[ADR 0008](0008-eu-data-residency.md) requires for residency.

**What we give up.** Less control over networking and scaling policy, and App
Runner's own service limits in place of Fargate's. Both are acceptable at roughly
5–20 studies per month.

**What would make us revisit.** App Runner service limits becoming binding;
a requirement for VPC-internal networking it cannot express; or sustained
concurrency that makes explicit task-level scaling control worth the operational
cost. Moving to Fargate later is a deployment change, not an architecture change —
the container image and the Postgres-authoritative design are unaffected.
