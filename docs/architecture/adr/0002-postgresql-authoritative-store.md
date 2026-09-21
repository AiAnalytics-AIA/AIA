# ADR 0002 — PostgreSQL is authoritative; SQS is dispatch only

**Status:** Accepted. PostgreSQL implemented; SQS pending Phase 3.
**Date:** 2026-09-21

## Context

The prototype stored durable state in three SQLite files plus filesystem
artifacts. SQLite is single-writer and file-local, which blocks concurrent
workers and multi-instance deployment.

AWS is the production target: ECS Fargate for the API and workers, RDS
PostgreSQL, S3, SQS. Redis is explicitly not being introduced yet.

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
