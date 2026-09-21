# Migration plan

Incremental, strangler-pattern migration from the NPC Panel prototype to the AIA
production application. The prototype remains available as a reference until each
subsystem has passed parity testing.

Current progress: [status.md](status.md). Behaviour comparison:
[parity-matrix.md](parity-matrix.md).

## Constraints that shape the order

1. **`main` must always start.** No phase may land in a state where the
   application cannot boot.
2. **Projects come first.** Every other context needs the durable project graph
   to answer "is this work still valid" before it spends money.
3. **Parity before switchover.** A subsystem is not migrated until its behaviour
   is compared against the prototype on the same fixtures.
4. **Nothing expensive without the job engine.** Multi-minute AI work cannot run
   in an HTTP handler, so Phase 3 gates Phases 5–9.
5. **Nothing real without authentication.** No environment holding actual client
   data runs until the auth seam is filled.

## Dependency graph

```
Phase 0  Discovery ─────────────────────────────── done
            │
Phase 1  Foundation (structure, DB, CI, config) ── done, except auth
            │
Phase 2  Projects + artifacts ───────────────────── projects done; storage open
            │
    ┌───────┴────────┐
    │                │
Phase 3        Phase 4
Job engine     AI gateway          (independent of each other)
    │                │
    └───────┬────────┘
            │
Phase 5  Research lifecycle
            │
    ┌───────┴────────┐
    │                │
Phase 6        Phase 7
Analysis &     Simulation
reports             │
    │                │
    └───────┬────────┘
            │
Phase 8  Data Library / Population
            │
Phase 9  Sociomapa
            │
Phase 10 Hardening
```

Phase 3 and Phase 4 are genuinely parallel and are the natural point to split
work across owners.

## Phases

### Phase 0 — Discovery ✅

Audit both codebases, establish the test baseline, map the legacy architecture,
identify invariants. Output: this document set.

### Phase 1 — Production foundation ✅ (auth outstanding)

Monorepo structure, domain package, PostgreSQL schema, Alembic migrations, typed
configuration with production guards, structured logging with request
correlation, error contract, Docker Compose development environment, Makefile, CI
with quality gates.

**Outstanding:** authentication. `get_principal` is a development seam that
refuses production. This blocks any deployment with real data and needs a team
decision on the identity provider.

### Phase 2 — Projects and artifacts ◐

Projects, revisions, stages, impact analysis, history, trash, settings, the
tenant-scoped repository and the projects API: **done**.

**Remaining:** the artifact storage abstraction (S3/MinIO adapter, content
hashing, verified read, pre-signed download) and the `datasets` table for
uploaded client data.

- Risk: low. Well-understood, no AI dependency.
- Parity: artifact reuse must select the same artifact the prototype would.

### Phase 3 — Durable workflow engine

Port `job_store.py`'s schema and semantics to PostgreSQL. Workflows, jobs,
dependencies, attempts, leases, heartbeats, stalled-job recovery, retry
classification, cancellation, the three waiting states, approvals, schedules,
cost reservations. Redis for queue transport. A worker process. SSE progress.

- Risk: **high.** This is concurrent, stateful code where bugs manifest as lost
  or duplicated expensive work.
- Parity: characterization tests against the prototype's state transitions
  **before** reimplementation. Especially: quota parks and resets the retry
  counter; a stalled lease recovers; an idempotency key deduplicates.
- Python reuse: schema and semantics carry over; the SQLite implementation does
  not.

### Phase 4 — AI runtime gateway

Provider gateway interface, Anthropic and OpenAI adapters, Claude Code CLI
transport, structured output with schema strictification, model resolution by
role, the 10-way error classifier, token and cost accounting, budget enforcement
at the call site, provider event auditing, encrypted credential storage.

- Risk: medium-high. External dependency; failure modes are the point.
- Parity: `ai_router.py`'s classification and model-substitution logic compared
  against recorded fixtures. No live-credential tests in CI.
- Python reuse: `ai_router.py` is largely portable behind an interface.

### Phase 5 — Research lifecycle

The 13 research stages end to end: intake, deep research and its evidence pack,
research design, questionnaire construction/optimization/repair, instrument
library, audience selection, persona dimensions, sample plan, the respondent
engine with checkpoint/resume, aggregation. Dataset upload with validation.

- Risk: high. The largest body of domain logic (`dotaznik.py`, `pipeline.py`,
  `research_designer.py` ≈ 3,900 LOC).
- Parity: questionnaire compilation and sampling must be compared on fixed seeds.
  The respondent engine's resume behaviour needs explicit tests.
- Python reuse: **substantial.** This is validated methodology; refactor it
  behind clean interfaces rather than rewriting it.

### Phase 6 — Analysis, validation and reporting

The eight durable analysis modules and deterministic assembly, evidence
validation, result verification, reality alignment, validation gates, holdout
protocol, legal and tier gates, client and internal reports, export packs.
`PRODUCT_POLICY.json` and `DATA_CONTRACT_v17.json` become enforced backend rules.

- Risk: high — this is where the product makes claims. Methodology gates must
  fail closed exactly where they currently do.
- Parity: gate decisions compared case by case. A gate that passes where the
  prototype blocks is a release blocker, not a diff.
- Python reuse: high for the validators; report rendering needs replacement.

### Phase 7 — Simulation

Baseline, scenario compiler and approval, independent variant modelling, worlds,
frozen results, comparison, interpretation, the scenario truth log, batch runs.

- Risk: high. `full_simulation.py` is 1,631 LOC of numerical work.
- Parity: seeded runs must reproduce. `linear_interpolation_allowed: false` must
  hold — variants are independently modelled, never interpolated.
- Python reuse: high. Do not rewrite the numerics without parity tests.

### Phase 8 — Data Library, Society Intelligence, Population

Source ingestion and text extraction, AI evidence proposals with human approval,
dimension materialisation, learning and calibration, LIVE population revisions,
the results registry, grounded Q&A. The population panel as a versioned read-only
asset bundle.

- Risk: medium-high. Governs data provenance.
- Parity: the approval ordering must hold —
  `ingest → parse → proposal → review/approve → materialize → validation → learning → new LIVE revision`.
  A `STATIC` population is immutable and no learning step may modify it in place.
- Python reuse: high.

### Phase 9 — Sociomapa

Relation matrix derivation, unfolding and layout mathematics, the two map types,
matrix/comparison/what-if modes, saved segments, AI segment intelligence, object
manager, respondent and segment dialogue.

- Risk: high. Mathematical parity plus a performance-sensitive renderer.
- Parity: **numerical**. Layout coordinates and relation matrices compared within
  tolerance on fixed seeds. `manual_drag` must remain a visual override that
  never mutates raw results; what-if must remain a layer over immutable
  originals.
- Python reuse: `sociomap.py` mathematics ports directly. Rendering is new.
  Profile before choosing the renderer.

### Phase 10 — Hardening

Authentication and authorization completion, rate limiting, RLS, encryption at
rest, performance and load testing, OpenTelemetry tracing, dashboards and alerts,
disaster recovery and restore rehearsal, deployment verification, legacy removal.

## Per-subsystem summary

| Subsystem | Phase | Risk | Python reusable? | Parity requirement |
| --- | --- | --- | --- | --- |
| Projects / revisions | 2 | Low | Ported | Fingerprint + impact byte-identical ✅ |
| Artifact storage | 2 | Low | Concept only | Reuse selects the same artifact |
| Jobs / workflows | 3 | **High** | Schema + semantics | State transitions, quota resume, idempotency |
| AI gateway | 4 | Med-high | Largely | Error classification, model substitution |
| Research lifecycle | 5 | **High** | **Substantial** | Questionnaire + sampling on fixed seeds |
| Analysis / validation | 6 | **High** | High | Gate decisions case by case |
| Reporting | 6 | Medium | Low | Report contract and content rules |
| Simulation | 7 | **High** | High | Seeded reproduction; no interpolation |
| Population / Data Library | 8 | Med-high | High | Approval ordering; STATIC immutability |
| Sociomapa | 9 | **High** | Maths yes, render no | Numerical parity within tolerance |

## Strangler rule

For each subsystem, in order:

1. Identify the old behaviour and read the code.
2. Capture characterization tests or contracts against the prototype.
3. Implement the new architecture.
4. Compare results on shared fixtures.
5. Switch the API and frontend to the new implementation.
6. Remove dead legacy code **only after** verification.

The prototype stays at `../npc-panel-reference`, referenced by
`AIA_LEGACY_REFERENCE`, and is never committed to this repository.

## Open decisions for the team

These block or reshape phases and are not mine to settle:

1. **Identity provider** — blocks Phase 1 completion and any real deployment.
2. **Hosting target.** `chore: trigger Amplify rebuild` implies AWS Amplify for
   the web client, but no infrastructure configuration exists in the repository.
   The API, workers, PostgreSQL, Redis and object storage need a target before
   Phase 10, and ideally before Phase 3.
3. **Scope of the correlation-matrix MVP.** `README.md`, `ROADMAP.md`,
   `docs/mvp-scope.md` and `docs/BACKLOG.md` describe a much narrower product —
   single case, uploaded CSV, Spearman/Pearson matrix, manual Sociomapping SOP.
   The migration brief supersedes this, but those documents still describe it and
   `docs/AGENTS.md` defines a 9-agent/4-gate model that matches neither. They
   should be reconciled or explicitly retired.
4. **Tenancy model** — one organization per user, or several?
5. **Data residency** for Czech client research data.
