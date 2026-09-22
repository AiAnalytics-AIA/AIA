# CLAUDE.md — standing instructions for AIA

Read this file, then [ARCHITECTURE.md](ARCHITECTURE.md), then
[AGENTS.md](AGENTS.md), before writing any code. Then read
[`.planning/PROGRESS.md`](.planning/PROGRESS.md).

These rules are not advisory. They apply to every session, every branch and
every agent working in this repository.

---

## 0. The contract

You are working in someone else's long-lived codebase. Two things are true and
they order everything below.

1. **The repository is the memory.** Nothing you learn survives this session
   unless it lands in code, a test, or one of the three documents above. A
   decision explained only in chat is a decision that will be re-litigated in six
   weeks by someone with less context.
2. **Solid over fast.** When you hit a blocker, do not rush to clear only that
   blocker. Step back and ask what the right shape is. A fix that makes the next
   three fixes harder is a loss even when it ships today.

## 1. The document triad

| File | Owns | Rule |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layering, boundaries, contracts, enforcement, anti-patterns, CI tiers | The authoritative spec. Read before any change that crosses a module boundary. |
| **CLAUDE.md** (this file) | The project map, the commands, the working rules | What exists, where, and how work is done here. |
| [AGENTS.md](AGENTS.md) | Framework-level gotchas — FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Next.js | Tool-agnostic. Anyone's agent can use it. |

**Keeping them in sync is mandatory, in the same change set.** When you add,
rename or remove anything they describe — a module, a table, a route, a job, a
config key, a command — the document changes in the same commit range as the
code. The reviewer reads the doc diff alongside the code diff. **Stale docs are
worse than no docs, because they are believed.**

When you solve a non-obvious framework problem — a race, a silent truncation, a
config that behaves differently under test — write it into `AGENTS.md`
immediately, with the wrong version and the right version side by side. That file
exists because the same three-hour debugging session was happening twice.

## 2. The map

```
apps/
  api/src/aia_api/          FastAPI. Validates, delegates, serialises.
    config.py               Typed settings + production guards
    dependencies.py         Composition root: engine, sessions, identity, scope
    identity/               IdentityProvider protocol: cognito, testing, development
    observability.py        Structured logging, request correlation, secret redaction
    routers/                health, projects, scope
    schemas/                Request/response models + the one error contract
  web/                      Next.js 16 / React 19 / Tailwind 4. Still mock-backed.

packages/aia_core/src/aia_core/
  domain/                   Pure. No I/O. stdlib + Pydantic only.
    pipeline.py             Stage order, fingerprints, impact/invalidation rule
    population/             Dataset versions, STATIC/LIVE, lineage, promotion, import
                            contract + validation, weights, bindings, RuntimePopulation
      czech.py              The Czech v17 import contract (pinned by hash, not copied)
    project.py              Project, revisions, stage state
    providers.py            Provider policy, model roles, budget and error semantics
    scope.py                Organization/Client/Study vocabulary, roles, permissions
    workflow.py             Workflow DAG, job states, retry classification
  application/
    scope.py                ScopeResolver — the ONLY issuer of a scope context
    population.py           PopulationRuntime — the ONLY loader of population data
  infrastructure/
    tables.py               SQLAlchemy tables
    db.py                   Engine and session factory
    repositories.py         ProjectRepository
    scope_repository.py     Organizations, clients, studies, grants
    artifact_repository.py  Artifact rows, provenance, dependency edges, reuse
    workflow_repository.py  Durable jobs, leases, heartbeats, cost reservations,
                            the population binding each run records
    population_repository.py  Population registry: versions, populations, history
    population_parser.py    Text-preserving panel + dictionary parser (stdlib)
    population_source.py    PopulationAssetSource: filesystem / memory (EU store later)
    storage.py              ArtifactStore: S3 / filesystem / memory

migrations/                 Alembic
docs/architecture/          System design + 7 ADRs
docs/design/                Brand and UI direction; the design-system brief
docs/migration/             Plan, status, parity matrix, legacy map
docs/product/               Authoritative product scope
docs/archive/original-mvp/  Superseded. NOT requirements.
tools/layer_check.sh        Layering enforcement
tools/exposure_check.sh     Reference-exposure enforcement (private-repo hygiene)
.planning/                  Progress, plans, open items
src/server.js               Legacy Fastify login stub. Frozen. No new features.
```

**Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic,
PostgreSQL 16, Next.js 16, TypeScript, Tailwind 4.
**Target:** AWS — Amplify, ECS Fargate, RDS, S3, SQS, Secrets Manager, KMS,
CloudWatch, Terraform, GitHub Actions. No Kubernetes, no Redis
([ADR 0002](docs/architecture/adr/0002-postgresql-authoritative-store.md)).

**Routes.** Every project route is study-scoped:
`/api/v1/studies/{study_id}/projects/…`. A project route outside a study prefix
fails the build — that would mean scope had stopped being carried in the path.

**The legacy prototype is not in this repository.** It lives at
`../npc-panel-reference`, reached through `AIA_LEGACY_REFERENCE`, and is used by
the parity and characterization suites only. The population parity suite reads the
committed contracts and golden fixtures of `AiAnalytics-AIA/AIA-reference` through
`AIA_REFERENCE_REPO` (default `../aia-reference`) — never the withheld archive.

**The population is resolved once per run.** Research and simulation code gets
population data only from `PopulationRuntime.load_for_run`, which reads the
`PopulationBinding` the run recorded at creation. There is no other loader, no
default weight and no fallback version; `make layer_check` enforces the loader.

## 3. Commands

| Purpose | Command |
|---|---|
| One-time setup | `make setup` |
| Start Postgres / Redis / MinIO | `make services` |
| Migrate | `make migrate` |
| New migration | `make migration m="add jobs"` |
| Run everything | `make dev` |
| Tests | `make test` (core + API) |
| Parity vs prototype | `make test-parity` (needs `AIA_LEGACY_REFERENCE`; population parity needs `AIA_REFERENCE_REPO`) |
| Lint | `make lint` |
| Format | `make format` |
| Types | `make typecheck` (mypy `--strict` + `tsc --noEmit`) |
| **Layering** | `make layer_check` |
| **Reference exposure** | `make exposure_check` |
| Everything CI runs | `make check` |
| **The pre-commit sequence** | `make verify` |
| OpenAPI document | `make openapi` |

There is no compile step in Python. `make typecheck` is this project's
warnings-are-errors gate: `mypy --strict` with `warn_unreachable`, plus
`tsc --noEmit` for the client.

## 4. Planning — `.planning/`

Progress and design live in the repository, not in the chat log.

```
.planning/
├── PROGRESS.md        single source of truth: done / in progress / next
├── plans/             one file per feature, broken into chunks
│   └── done/          archived plans: design decisions + review outcomes
└── open-items.md      the live defect and question register
```

- **Read `.planning/PROGRESS.md` at the start of every session**, before any work.
- When a design discussion produces an implementation plan, **save it** to
  `.planning/plans/<feature>.md` with the agreed chunks *before* writing code.
- After each chunk lands, update both `PROGRESS.md` and the plan file.
- When every chunk is done, move the feature to Completed and the plan file to
  `plans/done/`.
- **Do not open a parallel backlog.** If `PROGRESS.md` and a narrative document
  disagree, `PROGRESS.md` wins and the narrative is stale.

### The anchor rule

**Every claim about code carries `file:line @ SHA`, or a test name.**

An anchored claim is falsifiable with one `git show`. When the cited lines no
longer say what the entry says, the entry is *known* wrong rather than quietly
wrong. Anchors going stale is the feature, not a flaw.

An unanchored entry is a **hypothesis**, not a finding. That is the whole
enforcement mechanism — no tooling, no CI check, because a heavier process does
not survive one developer's busy week. Omitting the anchor costs credibility, not
time.

The specific failure this prevents: *a fix lands under one plan's name and nobody
closes the item filed under another's.* That is how a shipped fix gets carried as
"still open, parked" for weeks.

## 5. Git

### Permission

**Do not run `git add`, `git commit` or `git push` without explicit permission.**
Prepare the change, report what you would commit, and wait.

### Never touch the working tree to inspect another ref

To compare against `main` or any other ref, **read** it:

```bash
git show origin/main:path/to/file       # read one file
git diff origin/main -- path/           # see the difference
git worktree add /tmp/check origin/main # a whole tree, elsewhere
```

These overwrite uncommitted work and must never be used to have a look:

```bash
git checkout <ref> -- .        # silently replaces every file with <ref>'s
git stash / git reset --hard   # only to undo, never to inspect
```

This is a real incident. `git checkout origin/develop -- .` was run to check
whether some compiler warnings were pre-existing, and it wrote that branch's
version over ~20 working files. It was recoverable only because everything
happened to be committed already — a minute earlier it would have destroyed a
day of work. A throwaway worktree had *already been created* for exactly this
purpose and was the right tool.

### Branches

```
main                       integration branch; CI runs on every push and every PR
  ├── feature/<slug>       new capability
  ├── fix/<slug>           defect
  └── chore/<slug>         docs, plan archiving, dependency bumps, tooling
```

Work happens on a prefixed branch, opens a pull request into `main`, and is
merged there. **Never commit directly to `main`.**

This project runs a single integration branch: `main` is both trunk and release.
A separate release branch is deliberately deferred — it buys nothing until there
is something to protect a release *from*, and the condition for adding one is
recorded in [`.planning/open-items.md`](.planning/open-items.md).

### Commit messages

Subject: **imperative mood, plain English, describes the change's effect** — not
the files touched, not a ticket number, **not a `type(scope):` prefix**.

```
Verify the first screen on the turn, the rest in the background
Stop marking a listing analysed before it has anywhere to be
Tell "nothing nearby" apart from "we never looked"
Drop the unreachable email-normalisation fallback
```

Commits before this file landed use Conventional Commit prefixes. They are not
rewritten; the style changes going forward.

Body: **why, not what.** The diff already says what. A good body answers:

1. What was wrong, and how it showed up to a user or an operator.
2. Why the obvious fix is not the fix.
3. What this costs — the trade-off you accepted, stated plainly.
4. What you measured, with numbers, if the change is about performance, cost or
   volume.

Hard rules:

- **One logical change per commit.** Do not bundle unrelated changes.
- **Each commit builds and passes tests on its own.** A bisect that lands on a
  broken commit wastes the next person's afternoon.
- Author: `nigelblount <nigelblount@art-chain.io>`. Agent-assisted commits keep
  the `Co-Authored-By:` and `Claude-Session:` trailers, consistent with all
  existing history.

### Pull requests

- The PR body is the commit body, widened: the problem, the approach, the
  trade-off, what you measured, and what you deliberately did not do.
- Every PR is green on the blocking checks in
  [ARCHITECTURE.md §8](ARCHITECTURE.md#8-ci-tiers) before review is requested.
- **Never skip, disable, quarantine or loosen a test to get green.** A failing
  test is a finding. If it is genuinely flaky, fix the cause (§7) or document it
  — do not delete the signal.

## 6. Work style

- **Chew only what you can chew.** Break every plan into small, digestible chunks
  *before* execution begins. Never attempt the whole thing at once. If a chunk
  feels large, split it again.
- Execute one chunk at a time. Confirm it builds and its tests pass before
  starting the next.
- **Commit per aspect.** When one aspect is finished — schema + logic + tests —
  commit. Never carry uncommitted work across aspects.
- Finish the whole task. If part of the scope turns out to be blocked, complete
  everything else and say explicitly what you left and why. Scaling the work down
  is the human's call, not yours.

## 7. Tests

Coverage expectations by layer are in
[ARCHITECTURE.md §7](ARCHITECTURE.md#7-testing-contract). Operationally:

### Run long suites in the background

```bash
make test > tmp/suite.txt 2>&1 &     # then keep working
grep -E "passed|failed" tmp/suite.txt # collect later
```

The exception is when the test run **is** the task — debugging one failure,
iterating on one file. Then run it in the foreground and watch it. Single files
are fast and stay in the foreground.

### Flakes are defects, and they have one usual cause

- **The shared cause is almost always parallel tests mutating global state** —
  application config, a shared cache key, an environment variable. The durable
  fix is marking the *mutating* test non-parallel, not a retry and not a sleep.
- Any test whose setup mutates global config must be non-parallel.
- Tests that write to a shared cache clear the key in **both** setup and teardown.
- **Size timing assertions generously.** A wait tuned to a fast dev machine fails
  on CI and buys no signal. If the assertion is about *ordering*, give the budget
  room rather than optimising the thing being measured.
- Do not chase a documented flake; do not re-run a suite hoping for green either.

### Known flakes

None recorded. Add an entry here the moment one is confirmed, in this shape:

```
- `packages/aia_core/tests/test_x.py::test_y` — symptom: …
  Confirmation: passes when run alone. Cause: … Fix or waiver: …
```

Mocks live at interface boundaries — external services are mocked through their
protocol, always. Real HTTP only in explicitly manual or integration runs; if a
test needs a real request, stand up a local stub rather than hitting a third
party.

## 8. Correctness habits

The expensive class of bug, with the sweep that finds each, is catalogued as
anti-patterns A1–A10 in
[ARCHITECTURE.md §6](ARCHITECTURE.md#6-anti-patterns--do-not-do-these). The two
worth carrying in your head:

- **Never stamp a guess — prefer null.** A wrong non-null value overwrites good
  data that an earlier pass stored, where null would have left it alone.
- **Never score *unknown* as *good*.** Coalescing a missing value to a
  neutral-looking default silently rewards the absence of data.

**New behaviour on the hot path ships behind a kill switch**, off in test, with
its cost measured before it merges. State the burst size, the latency and the
money in the commit body.

## 9. A finding is only actionable with all six

When reporting a defect — to a human or into `.planning/open-items.md`:

1. The claim, in one sentence.
2. The anchor: `file:line @ SHA`.
3. A reproduction that fits one command or one test.
4. The user-visible consequence.
5. The smallest fix.
6. The test that would have caught it.

Missing the reproduction makes it a **hypothesis**, and it is labelled as one.
Hypotheses are reproduced or deleted; they are never budgeted for.

## 10. Before you say a task is done

```bash
make typecheck     # mypy --strict; this project's warnings-are-errors gate
make layer_check
make exposure_check
ruff format --check packages/aia_core apps/api migrations
make test
```

or `make verify`, which runs exactly that sequence.

- [ ] The three documents in §1 are updated in the same change set, if anything
      they describe moved.
- [ ] `.planning/PROGRESS.md` and the plan file reflect the chunk that just landed.
- [ ] Every new public function has tests; every new job and event has a test file.
- [ ] No test was skipped, disabled or loosened to get green.
- [ ] Nothing was committed or pushed without permission.
- [ ] You can state the trade-off this change accepted in one sentence.

If the change touches domain logic, also run the parity suite locally against a
reference checkout — **CI cannot run it**, and a green CI is not evidence that
parity holds.

After finishing a whole plan, produce a **layer-by-layer review map**: every
changed and new file grouped by architectural layer, with its test files beside
it, walked through in layer order.

## 11. Reporting

Report outcomes faithfully. If tests fail, say so and paste the output. If you
skipped a step, say which and why. If you are unsure whether something works, say
that instead of "should work". When something is done and verified, say so
plainly without hedging.

Do not narrate options you are not going to take, and do not re-explain a
decision that has already been made.
