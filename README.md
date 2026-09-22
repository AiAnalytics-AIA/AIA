# AIA — Agentic AI Analytics

AIA is a research and simulation platform. A user states a business question; the
system designs a study, runs it against a calibrated synthetic population of the
Czech Republic, analyses the results and produces a consulting-grade report.

This repository is being rebuilt from a working prototype (NPC Panel 18.6.6) into
a production application. **See [docs/migration/status.md](docs/migration/status.md)
for exactly what works today** — a large majority of the product is not migrated
yet.

## Quick start

Requires Python 3.12+, Node 20+, Docker.

```bash
make setup      # venv, Python packages, npm packages, .env
make services   # Postgres, Redis, MinIO (waits until healthy)
make migrate    # apply database migrations
make dev        # API on :8000, web client on :3000
```

API docs: http://localhost:8000/api/v1/docs

```bash
make help       # list every target
make check      # everything CI runs: lint, typecheck, layering, tests
make verify     # the pre-commit sequence from CLAUDE.md §10
```

## Before you contribute

Read these three, in this order. They are the spec; the code is the
implementation.

| File | Owns |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layering, boundaries, contracts, enforcement, anti-patterns, CI tiers |
| [CLAUDE.md](CLAUDE.md) | The project map, the commands, and how work is done here |
| [AGENTS.md](AGENTS.md) | Framework gotchas, with the wrong and right versions side by side |

Then [.planning/PROGRESS.md](.planning/PROGRESS.md) for what is done, in progress
and next. Keeping all four current is part of every change set, not a follow-up.

Authentication is Amazon Cognito federated to Google Workspace. There are no
local AIA passwords. For local development, `AIA_IDENTITY_PROVIDER=development`
accepts a subject header instead:

```bash
curl -H 'X-AIA-Subject: you@art-chain.io' \
     http://localhost:8000/api/v1/studies
```

That provider refuses to construct outside `local`/`test`, and a deployed
environment refuses to boot unless it is configured for Cognito — two independent
guards. See [docs/architecture/adr/0003](docs/architecture/adr/0003-cognito-identity-boundary.md).

## Layout

```
apps/web                    Next.js client (still mock-backed)
apps/api                    FastAPI service
  src/aia_api/identity/     Identity providers: Cognito, test, development
packages/aia_core
  src/aia_core/domain/      Pure rules: no framework, driver or SDK imports
  src/aia_core/application/ Use cases; owns authorization
  src/aia_core/infrastructure/  PostgreSQL, S3, repositories
migrations/                 Alembic
docs/product/               What we are building
docs/architecture/          How it is built, and why
docs/architecture/adr/      Decision records
docs/migration/             How we get there from the prototype
docs/archive/original-mvp/  Superseded. Not requirements.
```

Dependencies point inward: `infrastructure → domain` is allowed, the reverse is
not. No business logic in route handlers or React components.

## The core idea

**A project is the source of truth. Workflows only orchestrate work against it.**

Every expensive operation is an AI call, so the architecture is organised around
one question: after a user edits something, what work can we *prove* is still
valid?

```
Organization → Client → Study → Project
                                  → immutable Revision
                                    → Stage (input fingerprint)
                                      → Artifact (provenance)
```

**Client and Study are hard isolation boundaries.** Every client-derived object
resolves to a client and a study, and scope is injected from authenticated
context — never from a request body or a model-generated argument. A resource the
caller holds no grant on returns 404, not 403.

A content change creates a new revision. Each stage's material inputs are
fingerprinted, so stages upstream of the change keep their artifacts and only the
changed stage and its dependants reopen. Editing the audience of a finished
project does not re-run deep research; switching AI provider mid-project costs
nothing already paid for.

## What the system refuses to do

- **No silent provider fallback.** Work parks and asks rather than quietly moving
  to a provider that costs money or changes provenance.
- **No spending past a budget.** Paid calls are checked before they are made.
- **No invented certainty.** Evidence roles travel with the data; a modelled
  figure is never shown as a measurement. External predictive validation is
  `EXTERNAL_HOLDOUT_PENDING` and the product says so.
- **No fake progress.** Real elapsed time and real stage transitions, never a
  synthesised percentage.
- **No visualisation mutating research truth.** Dragging a node saves a view
  override; results stay immutable.

## Documentation

**Product** (what we are building) —
[scope](docs/product/README.md)

**Architecture** (how) — [overview](docs/architecture/README.md) ·
[domain map](docs/architecture/domain-map.md) ·
[scope & authorization](docs/architecture/scope-and-authorization.md) ·
[data model](docs/architecture/data-model.md) ·
[workflows](docs/architecture/workflows.md) ·
[AI runtime](docs/architecture/ai-runtime.md) ·
[artifacts](docs/architecture/artifacts.md) ·
[security](docs/architecture/security.md) ·
[decision records](docs/architecture/adr/README.md)

**Migration** (how we get there) — [status](docs/migration/status.md) ·
[plan](docs/migration/migration-plan.md) ·
[parity matrix](docs/migration/parity-matrix.md) ·
[legacy system map](docs/migration/legacy-system-map.md) ·
[reference weaknesses](docs/migration/reference-weaknesses.md)

## The prototype

The NPC Panel reference implementation is **not committed to this repository**. It
is expected beside it:

```
AIA/
├── aia-repo/              this repository
└── npc-panel-reference/   the prototype (read-only reference)
```

Point `AIA_LEGACY_REFERENCE` at it to enable the parity suite, which compares
this implementation against the prototype on shared fixtures:

```bash
AIA_LEGACY_REFERENCE=../npc-panel-reference make test-parity
```

The tests skip cleanly when it is absent.

## Archived documents — not current requirements

[`docs/archive/original-mvp/`](docs/archive/original-mvp/) holds the *earlier*
AIA MVP: a single-case workspace producing a copy/paste correlation matrix for
**manual** Sociomapping, plus a 9-agent/4-gate workflow.

That product was superseded by the production rebuild. Every file there carries a
superseded notice. **Do not implement from them.** The authoritative sources are
`docs/product/`, `docs/architecture/` and `docs/migration/`.
