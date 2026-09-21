# Migration status

**Updated:** 2026-09-21
**Branch:** `migration/phase-1-foundation`
**Phase:** 1 complete except authentication; Phase 2 project core complete

Read this first to continue the work. Companion documents:
[migration-plan.md](migration-plan.md) ·
[parity-matrix.md](parity-matrix.md) ·
[legacy-system-map.md](legacy-system-map.md) ·
[../architecture/README.md](../architecture/README.md)

## Current architecture

```
aia-repo/
├── apps/
│   ├── api/                  FastAPI. Projects API, config, observability, deps
│   └── web/                  Next.js 16 / React 19. Still mock-backed (untouched)
├── packages/aia_core/
│   └── src/aia_core/
│       ├── domain/           Pure rules: pipeline, project, providers
│       ├── application/      (empty; Phase 2+)
│       └── infrastructure/   tables, repositories, db engine
├── migrations/               Alembic; one migration, verified up/check/down
├── docs/architecture/        7 documents
├── docs/migration/           4 documents
├── .github/workflows/ci.yml  7 jobs
├── docker-compose.yml        Postgres 16, Redis 7, MinIO
├── Makefile                  22 targets
└── src/server.js             Legacy Fastify login stub (retained, see below)
```

**Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic,
PostgreSQL 16, Next.js 16, TypeScript, Tailwind 4.

The NPC Panel prototype is **not** in this repository. It lives at
`../npc-panel-reference` and is referenced by `AIA_LEGACY_REFERENCE` for parity
tests only.

## Completed

- [x] **Phase 0 — Discovery.** Both codebases audited. Prototype baseline
      established at 394 passed / 0 skipped. Legacy architecture mapped, invariants
      identified, two latent bugs found.
- [x] Monorepo structure extending the existing `apps/` convention
- [x] **Domain layer**, pure and I/O-free: `pipeline.py` (stages, statuses,
      fingerprinting, impact analysis), `project.py` (revisions, stage
      carry-forward, save planning), `providers.py` (identity, policy, budget)
- [x] **Parity with the prototype, verified by 29 automated tests** — stage lists
      and Czech labels, status set, impact roots, stage input payloads
      (byte-identical, both pipelines, all 13 stages), fingerprint hashes, impact
      previews, cross-pipeline stage routing, provider normalisation, UI labels,
      `provider_for_stage` across a ~700-case matrix, budget decisions including
      the exact-limit boundary
- [x] **PostgreSQL schema**: 7 tables — projects, revisions, stages, artifacts,
      artifact dependencies, events, provider events. Portable JSON (JSONB on
      PostgreSQL), aware UTC timestamps, explicit constraint naming, indexes for
      the portfolio listing and the artifact-reuse lookup
- [x] **Alembic migrations** verified end to end: `upgrade head`, `check` (no
      drift), `downgrade base`, re-upgrade
- [x] **Tenant-scoped repository.** `ProjectRepository` cannot be constructed
      without an `organization_id`; there is no unfiltered read path
- [x] **Projects API** — 10 routes: create, list (paged/filtered/searched), get
      (any revision), save content, update settings, impact preview, revision
      history, project history, trash, restore
- [x] **Observability**: JSON logs, request ids returned and logged, secret
      redaction by key name and value shape, one error contract
- [x] **Production config guards**: refuses to boot on missing/SQLite
      `DATABASE_URL`, debug mode, or wildcard CORS; docs disabled in production
- [x] **Auth gate**: production refuses header-based identity in middleware,
      before any dependency resolves
- [x] **CI**: 7 jobs — backend lint/types/tests on PostgreSQL *and* SQLite,
      migration apply/drift/reversibility, parity, OpenAPI generation and
      validation, frontend lint/types/build, real-server startup smoke with an
      end-to-end project lifecycle over HTTP, dependency and secret scanning
- [x] **Development environment**: Docker Compose, `.env.example`, 22 Makefile
      targets
- [x] 11 architecture and migration documents

### Test and quality state

| Suite | Result |
| --- | --- |
| `packages/aia_core` | **99 passed** (29 parity against the prototype) |
| `apps/api` | **69 passed** |
| **Total** | **168 passed, 0 failed, 0 skipped** |
| `ruff check` / `ruff format --check` | clean |
| `mypy --strict` | clean, 20 source files |
| Alembic up / check / down / re-up | clean |

Verified locally against **SQLite**. The PostgreSQL run is configured in CI but
**has not been executed** — there is no Docker or PostgreSQL on this machine. The
schema is written portably and CI runs both, but PostgreSQL-specific behaviour is
unverified until CI runs.

## In progress

Nothing. The slice is complete and the tree is green.

## Next

Recommended order. Phase 3 and Phase 4 are independent and can run in parallel.

- [ ] **Authentication** — fill `aia_api.dependencies.get_principal` with a real
      token verifier. Blocks every deployment with real data. **Needs a team
      decision on the identity provider first.**
- [ ] **Artifact storage adapter** — completes Phase 2. S3/MinIO, content
      hashing, verified read, pre-signed download, the write protocol in
      [../architecture/artifacts.md](../architecture/artifacts.md)
- [ ] **Phase 3 — durable job engine.** Highest-risk remaining work and it gates
      Phases 5–9. Write characterization tests against `job_store.py`'s state
      transitions *before* reimplementing
- [ ] **Phase 4 — AI provider gateway.** Port `ai_router.py` behind an interface
- [ ] Wire `apps/web` to the real projects API and delete `lib/mock.ts`
- [ ] `organizations` / `users` / `organization_members` tables

## Blockers and decisions needed

1. **Identity provider — blocking.** No SSO or auth configuration exists in the
   repository. Until this is decided, no environment may hold real client data.
2. **Hosting target — blocking Phase 10, wanted before Phase 3.** A commit
   message (`chore: trigger Amplify rebuild`) implies AWS Amplify for the web
   client, but there is no infrastructure configuration in the repository. The
   API, workers, PostgreSQL, Redis and object storage need a target.
3. **MVP scope contradiction — needs an explicit decision.** `README.md`,
   `ROADMAP.md`, `docs/mvp-scope.md` and `docs/BACKLOG.md` describe a much
   narrower product: single case, uploaded CSV/XLSX, a Spearman/Pearson
   correlation matrix, manual Sociomapping SOP. `docs/AGENTS.md` defines a
   9-agent/4-gate workflow matching neither that nor the prototype. The migration
   brief supersedes all of it, but those documents still stand unedited. Per
   `docs/execution-cadence.md`, scope trade-offs escalate to Nigel. **They have
   been left untouched pending that call.**
4. **Tenancy model.** `apps/web` already routes `/org/[orgSlug]/…`. One
   organization per user, or several?
5. **Data residency** for Czech client research data.

## Legacy functionality not yet migrated

Everything except project persistence. Specifically: 128 of the prototype's 136
API routes, the entire frontend, the job engine, AI runtime, research lifecycle,
simulation, analysis, validation and methodology gates, reporting, Data Library,
Society Intelligence, population and audience, Sociomapa, demos, ingestion,
exports and scheduling. See [parity-matrix.md](parity-matrix.md) for the
component-level inventory.

`src/server.js` (44-line Fastify login stub) is **retained deliberately**. It has
no domain logic, but it holds the only working login path in the repository, and
the new auth seam is explicitly unfinished. Removing it now would leave no
authentication at all. **Removal condition:** delete once `get_principal` has a
real verifier.

## Known regressions

None. No previously working behaviour has been removed or altered.

The prototype remains fully functional and untouched at
`../npc-panel-reference`.

## Notes for whoever continues

- **Run the parity suite before changing domain logic.**
  `AIA_LEGACY_REFERENCE=../npc-panel-reference make test-parity`. Those 29 tests
  are the evidence that artifact reuse decisions match validated behaviour.
- **`stage_input_payload` is a migration, not a tweak.** Adding a field to a
  stage's payload changes its fingerprint and invalidates every artifact
  previously stored for that stage.
- **Provider transport is excluded from fingerprints on purpose.** Do not "fix"
  this. Mixed-provider continuation depends on it.
- **The three `WAITING_*` states are not errors.** A quota pause resets the retry
  counter; treating it as a failed attempt will eventually fail projects that
  were only waiting.
- **Three documented deviations from the prototype** — see
  [parity-matrix.md](parity-matrix.md) D1–D3. Each has a test asserting the
  legacy behaviour is still what we believe, so the tests will tell you if the
  reference changes.
- `python-pptx` is undeclared in the prototype's `requirements.txt` but imported
  by `output_pack.py`. Install it to get a green prototype baseline.

## Last verified commit

`11f48ab` — feat(migration): production foundation + durable project persistence

Verified at that commit: 168 tests passing (99 core incl. 29 parity, 69 API),
`ruff check` and `ruff format --check` clean, `mypy --strict` clean, Alembic
`upgrade head` / `check` / `downgrade base` / re-upgrade clean.

Verified against **SQLite** on Python 3.14.6, macOS. The PostgreSQL path is
configured in CI but has not been executed — there is no Docker or PostgreSQL on
the machine this was built on.
