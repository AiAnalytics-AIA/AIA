# Architecture Boards v2.2 — content specification

**Purpose:** a factual source for regenerating the visual architecture boards. The
current boards are stale. This document is **not** a design brief and contains no
layout, colour or styling guidance — it says what each board must assert, and what
it must not.

**Authority:** this file is derived from the repository at the v2.1 reconciliation
and must be regenerated from it rather than edited to match a board. Where a board
and this file disagree, the repository decides.

## The rule that governs every board

> **A board may not show as built what is not built, and may not show as chosen
> what is not chosen.**

Both failure modes have already happened. The previous boards implied SQS
infrastructure that does not exist and a compute service that was never selected.
A diagram is read as a statement of fact by people who will not open the code, so
each board below carries an explicit legend distinguishing three states:

| Legend state | Means |
| --- | --- |
| **Built** | Implemented in this repository, with tests |
| **Not built** | Designed or decided, no implementation |
| **Not decided** | Deliberately open; an ADR will settle it |

A fourth distinction matters and is easy to lose: **built in software** is not
**provisioned in an environment**. Where a board shows infrastructure, it must say
which.

---

## Board 1 — System context

**Asserts:** AIA is an internal research operating system. A small team runs paid
client studies against a calibrated synthetic population.

| Element | State |
| --- | --- |
| Next.js web client (`apps/web`) | Built; still mock-backed |
| FastAPI service (`apps/api`) | Built |
| Worker process | **Not built** |
| PostgreSQL | Built |
| Object storage (S3-compatible) | Built in software; **not provisioned** |
| Cognito, federated to Google Workspace | Built in software; **not provisioned** |
| Model providers | **Not decided**; no vendor selected |

**Must not show:** Redis. A message broker. A named model provider. A named
compute service.

## Board 2 — Scope and isolation

**Asserts:** `Organization → Client → Study → Project → Revision → Stage →
Artifact`, with Client and Study as hard isolation boundaries.

Show the resolution chain `User → Organization membership → Client grant → Study
grant → Role → Permissions`, and show that a study grant overrides a client grant
**in both directions** — the narrowing case is the one the boundary exists for.

Show `StudyContext` as issued by the authorization layer only, with the arrow from
"model / agent / tool argument / request body" into it **crossed out**. That
negative is the whole point of the design and a board that omits it shows an
ordinary parameter.

Denials render as 404, not 403. The single exception is `insufficient_role`, 403.

## Board 3 — Workflow states

**Asserts:** the canonical v2.1 business-state vocabulary, and the two-level split.

Run states: `PENDING`, `RUNNING`, `AWAITING_GATE`, `AWAITING_BUDGET`,
`WAITING_PROVIDER`, `WAITING_CAPACITY`, `RECOVERY_REQUIRED`, `COMPLETED`,
`FAILED`, `CANCELLED`.

Group them by prefix, visibly:

- `AWAITING_*` — **a person owes us a decision.** Nothing moves until someone acts.
- `WAITING_*` — **a system owes us capacity.** Clears on its own.

`WAITING_PROVIDER` (quota; resumes at a reset instant, carries `runnable_after`)
and `WAITING_CAPACITY` (overload; clears by itself) must appear as **separate
states**. A board that merges them reintroduces the defect this reconciliation
fixed.

Attempt states are a **separate** track: `PENDING`, `CLAIMED`, `EXECUTING`,
`SUCCEEDED`, `FAILED`, `EXPIRED`, `ABANDONED`. The whole reason for two tracks is
that `RECOVERY_REQUIRED` must not look like a `FAILED` attempt.

**Must not show:** `WAITING_GATE`, `WAITING_BUDGET`, or a single merged status.

## Board 4 — Execution and claiming

**Asserts:** PostgreSQL is authoritative and, for v0.1, is the queue.

Show a worker claiming with `SELECT … FOR UPDATE SKIP LOCKED` inside the
transaction that records the claim, the lease and heartbeat, and the reconciler
recovering lapsed leases.

**There is no broker on this board.** If SQS appears at all it is in a clearly
separated "future option, not built, not decided" area, annotated with its gate: a
measured trigger plus its own ADR, and PostgreSQL authoritative even then.

## Board 5 — Paid-call recovery

**Asserts:** the invariant that a possibly-billed call is never auto-retried.

Show the three unknowable outcomes after a worker dies mid-call — never received,
processed but response lost, processed and billed — and the three unacceptable
responses: auto-retry is possible double billing, assume success is possible
missing output, assume failure is an accounting lie.

Show `RECOVERY_REQUIRED` + `SETTLED_UNCERTAIN` as the resolution, with the
reservation converted to actual exposure so the budget reflects money that may
already be gone.

Show that a capacity failure after dispatch still lands here, not in a capacity
park. This is the ordering that the state split had to preserve.

## Board 6 — Approval and separation of duties

**Asserts:** independent review is the default and self-approval is configurable.

Show `study > client > organization > false`, with every level nullable and null
meaning *ask my parent* rather than *no*.

Show the two arrows that are **not** the same:

- policy → independence (can be lifted by configuration)
- permission → authority (cannot be lifted by configuration)

A board that draws one arrow shows a privilege escalation.

Show the policy arriving on the `StudyContext` from persisted state, and show
`approval_decisions` as the append-only record.

## Board 7 — Residency and egress

**Asserts:** EU residency is a frozen invariant and the boundary fails closed.

Show data classes A (client confidential), B (derived/aggregate) and C
(internal/non-client) with their constraints, and show the refusal paths as
prominently as the permitted one — unclassified material, no route, unknown route,
unknown zone, no training exclusion, unspecified retention.

Show that approval is **per class, not per provider**.

**Must not show:** a named provider, a named managed inference service, a specific
cloud region, or a hosted search product. Route boxes are generic and labelled by
their properties, not their vendors.

## Board 8 — Decision status

**Asserts:** what is settled and what is open. This board exists because the
absence of it is what let stale assumptions spread.

| Decision | Status |
| --- | --- |
| 0001 Python/FastAPI | Accepted |
| 0002 PostgreSQL authoritative + v0.1 queue | Accepted |
| 0002 SQS as non-authoritative wake-up | **Deferred** |
| 0003 Cognito identity boundary | Accepted |
| 0004 Client/Study isolation | Accepted |
| 0005 A — `ModelGateway` contract | Accepted |
| 0005 B — LiteLLM as transport | **Proposed** |
| 0006 LangGraph | **Accepted — constrained use** |
| 0007 Deterministic tools | Accepted |
| 0008 EU data residency | Accepted |
| Compute service | **Not decided** |
| Model provider / hosting | **Not decided** |
| Observability backend | **Not decided** |

## Board 9 — LangGraph boundary

**Asserts:** LangGraph orchestrates reasoning **inside** an agent step and owns
nothing durable.

Draw the boundary explicitly, with AIA/PostgreSQL owning workflow state, step
completion, gates, human approval, budget, reservations, retry eligibility,
`RECOVERY_REQUIRED`, Client/Study ownership, artifacts, cost ledger — and
LangGraph owning reasoning topology, tool selection and the model call within one
attempt.

A LangGraph run must not outlive a `StepAttempt`, and its state is debugging
information, never evidence.

---

## Source of truth for each board

| Board | Regenerate from |
| --- | --- |
| 1 | `README.md`, `docs/architecture/README.md` |
| 2 | `docs/architecture/scope-and-authorization.md`, `aia_core/domain/scope.py` |
| 3 | `aia_core/domain/workflow.py`, `docs/architecture/workflows.md` |
| 4 | `adr/0002`, `aia_core/infrastructure/workflow_repository.py` |
| 5 | `decide_recovery` in `aia_core/domain/workflow.py` |
| 6 | `docs/architecture/scope-and-authorization.md` § Self-approval |
| 7 | `aia_core/domain/residency.py`, `adr/0008` |
| 8 | `docs/architecture/adr/README.md` |
| 9 | `adr/0006` |
