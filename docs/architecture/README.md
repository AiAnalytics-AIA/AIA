# AIA architecture

AIA is a research and simulation platform. A user states a business question, the
system designs a study, runs it against a calibrated synthetic population of the
Czech Republic, analyses the results and produces a consulting-grade report.

This document is the entry point. It describes the shape of the system and why it
is shaped that way. The companion documents go deeper:

| Document | Covers |
| --- | --- |
| [domain-map.md](domain-map.md) | Bounded contexts and their dependencies |
| [data-model.md](data-model.md) | Production data model |
| [population.md](population.md) | Population consumer contract: binding, field policy, joint claims |
| [workflows.md](workflows.md) | Durable workflow and job model |
| [ai-runtime.md](ai-runtime.md) | Provider abstraction, provenance, budgets, failure behaviour |
| [ai-step-executor-contract.md](ai-step-executor-contract.md) | The contract between the model gateway and the step executor |
| [artifacts.md](artifacts.md) | Artifact lifecycle and storage |
| [scope-and-authorization.md](scope-and-authorization.md) | Who may touch which client's work, and approval policy |
| [security.md](security.md) | Threat model and security architecture |
| [simulation-deterministic-engine.md](simulation-deterministic-engine.md) | Simulation core: model-generated vs deterministic boundary, ported constants, intentional differences, parity status |
| [adr/](adr/) | Decision records, with a list of what is deliberately still open |
| [boards-v2.2-content-spec.md](boards-v2.2-content-spec.md) | What the visual architecture boards must assert, and must not |

Migration documents live in [`../migration/`](../migration/). Start with
[status.md](../migration/status.md) to see where the work currently stands.

## The one idea that explains the rest

**A project is the source of truth. Workflows and jobs only orchestrate work
against it.**

Everything expensive in this product is an AI call. A single research project runs
hundreds of them across thirteen stages. So the architecture is organised around
one question: *after a user edits something, what work can we prove is still
valid?*

The answer is a durable graph:

```
Project
└── Revision                (immutable content snapshot)
    ├── Stage               (one per pipeline step, with an input fingerprint)
    │   └── Artifact        (metadata + provenance; bytes in object storage)
    ├── Event               (append-only history)
    └── Provider event      (audited usage, cost and every provider switch)
```

A content change creates a new immutable revision. Each stage's *material inputs*
are fingerprinted; stages upstream of the change keep their fingerprints and
therefore keep their artifacts. Only the changed stage and everything downstream
of it reopen.

This is why editing the audience of a finished project does not re-run deep
research, and why switching from the Claude Code subscription to the Claude API
mid-project costs nothing already paid for.

The rules live in one place, `aia_core.domain.pipeline` and
`aia_core.domain.project`, as pure functions with no I/O. They are verified
against the validated prototype by the parity suite
(`packages/aia_core/tests/test_pipeline_parity.py`).

## Layers

```
apps/web         Next.js client. No business rules. Still mock-backed.
apps/api         FastAPI. Validates, delegates, serialises. No business rules.
apps/worker      The execution loop: claims steps from PostgreSQL, heartbeats,
                 runs the StepExecutor registered for each kind, records the
                 outcome. No executor for a real step kind exists yet.
packages/aia_core
  domain/        Pure rules. No framework, no driver, no SDK imports.
  application/   Use cases that orchestrate domain + infrastructure.
  infrastructure/ SQLAlchemy, object storage, provider gateways.
```

Dependencies point inward only: `infrastructure -> domain` is allowed,
`domain -> infrastructure` is not. The domain layer is importable with nothing
installed but Pydantic, which is what makes its tests fast and total.

Two rules keep this honest rather than decorative:

- **No business logic in route handlers.** A handler that makes a decision is a
  bug; the decision belongs in the domain and the handler should be calling it.
- **No business logic in React components.** The client renders state the server
  computed. `GET /projects/{id}/impact` exists precisely so the client never has
  to reason about which stages an edit invalidates.

## Technology, and why

| Concern | Choice | Reason |
| --- | --- | --- |
| Web client | Next.js 16, React 19, TypeScript, Tailwind 4 | Already established in `apps/web`, including the `/org/[orgSlug]/…` tenant routing |
| API | FastAPI + Pydantic | The validated domain engine is 44k lines of Python with 394 passing tests. Rewriting it in another language would discard the only evidence that the methodology works |
| Durable store | PostgreSQL + Alembic | The prototype's SQLite is single-writer and file-local; production needs concurrent workers and shared state |
| Queue | **PostgreSQL itself**, claimed with `FOR UPDATE SKIP LOCKED` | At this volume a broker adds an operational component and a second place the truth is kept, and buys nothing. No Redis, no SQS ([ADR 0002](adr/0002-postgresql-authoritative-store.md)) |
| Artifact bytes | S3-compatible object storage | Research outputs are large, immutable blobs that must outlive any container |
| Identity | Amazon Cognito, federated to Google Workspace | A token proves identity only; authorization is a PostgreSQL read ([ADR 0003](adr/0003-cognito-identity-boundary.md)) |
| Instrumentation | OpenTelemetry | Vendor-neutral by decision; the backend it exports to is replaceable and unchosen |
| Compute | AWS. `develop`: one EC2 host under Docker Compose ([ADR 0009](adr/0009-single-host-develop-environment.md)). Production: **not yet decided** | ECS Fargate and App Runner both remain open for production; the develop decision is explicitly not that decision |
| Local development | Docker Compose (Postgres, MinIO) | Development exercises the same engines as production |

The root `src/server.js` Fastify stub predates this work and is retained only
because it holds the sole existing login path. See
[../migration/status.md](../migration/status.md) for its removal condition.

`apps/web` is real work and is to be rewired to the live API, not replaced.

## What the system refuses to do

These are product requirements expressed as architecture, not preferences:

- **No silent provider fallback.** When a provider cannot serve a request, work
  parks in `WAITING_PROVIDER` or `WAITING_CAPACITY` and asks the user. It never
  quietly moves to a provider that costs money or changes provenance.
- **No client data leaving the EU.** The egress boundary fails closed:
  unclassified material does not leave, an unknown route is a refusal rather than a
  substitution, and a denial offers no cheaper alternative
  ([ADR 0008](adr/0008-eu-data-residency.md)).
- **No one clearing their own gate by default.** Independent review is the
  default; self-approval exists only where an administrator has explicitly enabled
  it in persisted policy, and it never confers authority someone did not have.
- **No spending past a budget.** A paid call is checked against the project's
  ceiling *before* it is made. Over budget means park and ask, not proceed.
- **No invented certainty.** Evidence roles (`MEASURED_JOINT`, `CALIBRATED_CORE`,
  `MODELED_BEHAVIOR_PRIOR`, …) travel with the data. The UI must not present a
  modelled figure as a measurement. External predictive validation is currently
  `EXTERNAL_HOLDOUT_PENDING` and the product says so.
- **No fake progress.** Progress reporting shows real elapsed time and real stage
  transitions. It does not synthesise a percentage the backend cannot know.
- **No visualisation mutating research truth.** Dragging a node on the Sociomapa
  saves a view override. The underlying results are immutable.

## Current state

Implemented in software, with tests: the domain model; the PostgreSQL schema and
migrations; `Organization → Client → Study` isolation with server-issued
`StudyContext`; the Cognito identity boundary with authorization in PostgreSQL;
artifact storage across S3, filesystem and in-memory backends with hashing,
verified reads and cross-revision reuse; the durable workflow engine with
`FOR UPDATE SKIP LOCKED` claiming, leases, budget reservations and uncertain
paid-call recovery, verified under real contention; approval policy with an
append-only decision ledger; the fail-closed residency and egress boundary;
structured logging with request correlation and secret redaction; and CI.

The worker process that drives the engine is built and verified with real
processes contending, killed and stopped mid-step.

**Not built:** executors for real step kinds, the AI provider gateway and
adapters, OpenTelemetry instrumentation, a generalized metered-cost ledger, and
every stage that actually calls a model. `apps/web` is still mock-backed.

**Built but not provisioned** — a distinction worth keeping, because the code
being finished is not the same as the system being deployable: the Cognito user
pool and federation, the S3 bucket, and approved egress routes. Until those exist
no environment holds real client data, and the API refuses to boot in production
without them.

Sequencing is in [../migration/migration-plan.md](../migration/migration-plan.md);
current state is in [../migration/status.md](../migration/status.md).
