# ARCHITECTURE

The authoritative spec for **layering, boundaries and their enforcement**. Read it
before any change that crosses a module boundary. Where this file and the code
disagree, this file is the bug report.

It deliberately does not describe the product. That lives in
[`docs/architecture/`](docs/architecture/README.md), which this file governs:

| Document | Covers |
| --- | --- |
| [docs/architecture/README.md](docs/architecture/README.md) | What the system is and why it is shaped that way |
| [domain-map.md](docs/architecture/domain-map.md) | Bounded contexts and their dependency direction |
| [data-model.md](docs/architecture/data-model.md) | Production data model |
| [population.md](docs/architecture/population.md) | The population consumer contract: binding, field policy, joint claims |
| [workflows.md](docs/architecture/workflows.md) | Durable workflow and job model |
| [ai-runtime.md](docs/architecture/ai-runtime.md) | Providers, provenance, budgets, failure behaviour |
| [ai-step-executor-contract.md](docs/architecture/ai-step-executor-contract.md) | The one seam between the model gateway and the workflow worker |
| [artifacts.md](docs/architecture/artifacts.md) | Artifact lifecycle and storage |
| [scope-and-authorization.md](docs/architecture/scope-and-authorization.md) | Client/Study isolation |
| [security.md](docs/architecture/security.md) | Threat model |
| [sociomapa-deterministic-engine.md](docs/architecture/sociomapa-deterministic-engine.md) | Sociomapping engine: what is ported, declared and refused |
| [sociomapa-methodology-decision.md](docs/architecture/sociomapa-methodology-decision.md) | The D6 decision package for the methodology owner |
| [simulation-deterministic-engine.md](docs/architecture/simulation-deterministic-engine.md) | Simulation core boundary and parity status |
| [adr/](docs/architecture/adr/README.md) | Eight decision records, with the reasoning |

---

## 1. The one idea

**A project is the source of truth. Workflows and jobs only orchestrate work
against it.** A content change creates a new immutable revision; each stage's
material inputs are fingerprinted, so only the changed stage and everything
downstream of it reopen. Everything below exists to keep that rule testable
without a database, a network or a provider key.

## 2. Layers

Each layer calls the layer directly below. `aia_core.domain` is the universal
seam, callable from any layer above. Each subsystem has exactly one public entry
point; nothing outside it touches its internals.

| # | Layer | Path | Owns | May depend on |
|---|---|---|---|---|
| 1 | **Domain** | `packages/aia_core/src/aia_core/domain/` | Pure rules: pipeline, project, providers, scope vocabulary, population versions and import contract, Sociomapping mathematics, evidence gates, analysis modules. Shapes and validation. No I/O. | Nothing internal. Stdlib + Pydantic only — numerical code included, which is why the Sociomap engine is pure Python rather than numpy. |
| 2 | **Application** | `packages/aia_core/src/aia_core/application/` | Use cases. **The only issuer of a scope context, and the only loader of population data.** Orchestrates domain + infrastructure. | 1, 3 |
| 3 | **Infrastructure** | `packages/aia_core/src/aia_core/infrastructure/` | SQLAlchemy tables and repositories, object storage, provider gateways. Every external service behind a protocol. | 1 |
| 4 | **Workers** | `apps/worker/src/aia_worker/` | Durable step execution: claim from the PostgreSQL queue, heartbeat, run the `StepExecutor` registered for the step's kind, record the outcome; every worker also reconciles. **Knows nothing about what a step does.** | 1, 2, 3 — never 5 |
| 4b | **Executors** | `apps/executors/src/aia_executors/` | What a step of each kind *does*, under the scope the lease issued and through the worker's `StepContext`. Registered by kind; the worker loads them from `AIA_WORKER_EXECUTORS`. Also the operator commands (seed, smoke) that act as a user would through the application layer. | 1, 2, 3 and `aia_worker.executor` — never 5 |
| 5 | **Transport** | `apps/api/src/aia_api/` | HTTP. Validates, delegates, serialises. **No business rules.** | 1, 2, 3 — through `dependencies.py` only |
| 6 | **Presentation** | `apps/web/` | Next.js client. Renders server-computed state. **No business rules.** | 5, over HTTP |
| — | **Legacy stub** | `src/server.js` | Frozen. The sole surviving login path. | Nothing. Receives no new features. |
| — | **Legacy unit** | `legacy/npc-panel-18.6.6/` | The NPC Panel 18.6.6 product, extracted byte-for-byte from the audited archive ([ADR 0011](docs/architecture/adr/0011-vendor-legacy-product-unit.md)). The rebuild's behavioural baseline and parity oracle. **Frozen: regenerated, never edited.** Outside every code-quality gate by construction; deployed as its own service on its own hostname behind a gate. | Nothing. Nothing depends on it in code; parity tests reach it over HTTP. |

Dependencies point inward only. `infrastructure → domain` is allowed;
`domain → infrastructure` is not. The domain layer must stay importable with
nothing installed but Pydantic — that property is what makes its tests total and
instant, and it is the first thing to decay if it is not checked mechanically.

Two rules keep the outer layers honest rather than decorative:

- **No business logic in a route handler.** A handler that makes a decision is a
  bug; the decision belongs in the domain and the handler should be calling it.
- **No business logic in a React component.** `GET /studies/{id}/projects/{id}/impact`
  exists precisely so the client never reasons about which stages an edit
  invalidates.

## 3. Enforcement — `make layer_check`

Layer violations are the #1 recurring issue in any layered codebase, and review
does not catch them reliably. [`tools/layer_check.sh`](tools/layer_check.sh) is a
grep-level checker with no toolchain of its own — a checker that needs one gets
disabled the first time that toolchain breaks, and then the layering rots
silently.

Run it before every commit. It is blocking in CI.

| Rule | Prevents |
|---|---|
| domain imports no framework, driver or SDK | The domain becoming untestable without a database |
| domain does not import outward | A dependency cycle through application or infrastructure |
| application knows nothing about HTTP | Use cases that only work behind FastAPI |
| infrastructure knows nothing about HTTP | Adapters that cannot be reused by a worker |
| AWS SDK stays behind the storage adapter | `boto3` becoming a mandatory dependency of the whole package |
| no database access in the HTTP layer | A handler opening a Session, and deciding something the domain never saw |
| no ORM tables in the HTTP layer | Queries written where they cannot be tested without the whole stack |
| scope contexts are issued only by `ScopeResolver` | A request body, tool payload or model-generated argument widening its own scope |
| provider SDKs and gateway libraries are not imported (core or API) | A second model-call path that can retry, fall back or substitute without `GovernedModelGateway` deciding to (ADR 0005) |
| the API never builds its own scope context | The same, at the edge where untrusted input arrives |
| the worker never builds its own scope context | The same, inside the process where model-driven code will run |
| the worker knows nothing about HTTP | A worker that only works behind a web server |
| the worker never imports the API | Layer 4 depending on layer 5, and the API's request state leaking into jobs |
| the worker imports nothing domain-specific | The executor seam becoming decoration: the loop importing the AI or research code it is supposed to be ignorant of |
| executors know nothing about HTTP and never import the API | A step implementation that only works behind a web server, or reaches into request state |
| executors never build their own scope context, admit their own claims, or build an unscoped repository | A claimed step writing another client's artifacts, or a number reaching a result without the admission gate, from inside the process where model-driven code will run |
| the API never executes workflow steps | Expensive work inside a request, holding a lease exactly as long as a browser stays connected |
| only the work queue may query across studies | An unscoped `WorkflowRepository` anywhere but `WorkQueue` -- a query over every client's studies |
| runtime populations are issued only by the canonical loader (and never by the API) | A second loader returning different population semantics from the same bytes (reference F10, R4) |
| population panels are parsed only by the canonical loader (and never by the API) | The first step of that second loader: a consumer reading the panel itself |
| population-operator grants are issued only by the population authority (and never by the API) | A study context, an organization owner or a request body moving LIVE for every tenant (OI-8) |
| the Sociomap preset `AIA_SOCIOMAP_V1` is never named outside the Sociomap domain package | An engineering preset silently filling in a missing spec, and becoming client methodology by default ([sociomapa-deterministic-engine.md §13](docs/architecture/sociomapa-deterministic-engine.md#13-computable-is-not-deliverable)) |
| claims are admitted only by the evidence admission gate | A model's number reaching a result without passing field policy, joint structure, support and interval checks |
| the API never admits its own claims | The same, at the edge where untrusted input arrives |
| a joint status is issued only by its loader | A hand-built permissive `CORE_JOINT_STATUS` certificate reaching the claim gate |
| no statically skipped or xfailed tests | Deleting the signal instead of fixing the defect |
| the web client does not talk to a database | The presentation boundary crossed in the most expensive possible way |

Two things make this survive contact with a busy week:

- **Exemptions are named in the rule itself.** `dependencies.py` and `main.py`
  are exempt from the database rule because they are the composition root;
  `storage.py` is exempt from the AWS rule because it *is* the adapter. Each
  carries a comment saying so. Pretending an exception does not exist is what
  kills these scripts.
- **Rules are a ratchet.** A rule is added only once it already passes, so the
  check is green the day it lands and a red run always means a regression, never
  a backlog.

To add one: state it in the table above, then add one `forbid` line to the
script, then confirm it passes before committing.

## 4. Contracts at boundaries

- **A protocol at every swappable seam.** Every external service has a protocol,
  at least one real implementation and a test double. The active implementation
  is resolved from typed configuration — never from an `if env == "test"` branch
  inside the service. Live examples: `ArtifactStore` (S3 / filesystem / memory),
  `IdentityProvider` (Cognito / testing / development), `ProviderAdapter`
  (Anthropic / OpenAI / Claude Code, over `HttpTransport` / `CliRunner` with
  recorded doubles), `CallJournal` (workflow-backed / in-memory).
- **Typed objects across boundaries**, not raw dicts. Pydantic models or
  dataclasses in, Pydantic response schemas out.
- **Type signatures on every public function** in the domain and application
  layers, verified by `mypy --strict`, which is blocking.
- **Scope is a capability, not an argument.** `StudyContext` is issuable only by
  `ScopeResolver` through a module-private sentinel. Repositories refuse anything
  that is not an issued context, by type. This is the isolation boundary; see
  [scope-and-authorization.md](docs/architecture/scope-and-authorization.md).
- **Population data is a capability too.** `RuntimePopulation` is issuable only by
  `PopulationRuntime` through the same sentinel construction, and carries the
  `PopulationBinding` (version, content hash, weight scheme, view) it was loaded
  under, its `FieldPolicy` (what each field may be used for) and its `JointStatus`
  (what may be claimed jointly). A run records its binding once, at creation; a
  step reads the population only through it. Establish and promote need a
  `PopulationOperatorContext`, issued only by `PopulationAuthority`. See
  [population.md](docs/architecture/population.md).
- **Evidence is a capability, not a flag.** A number enters an analysis result
  only as an `AdmittedClaim`, which only `aia_core.domain.evidence.admit_numeric_claims`
  can mint, after the field policy, the `CORE_JOINT_STATUS` certificate, support,
  the interval rule and the tier gate have all passed. The certificate itself is an
  `aia_core.domain.evidence.JointStatus` only `load_joint_status` can issue, bound to the loaded panel's
  hash. A prompt may state a rule; it is never the only thing enforcing it.
- **Every gate returns a `GateDecision`, and allowed means no violations.** There
  is no override field, a missing input blocks, and `combine` keeps every refusal
  so a later gate cannot launder an earlier one.

## 5. Where does this go?

```
What are you building?
│
├─ A rule that could be decided on paper, with no I/O?
│    → packages/aia_core/src/aia_core/domain/<context>.py
│      + packages/aia_core/tests/test_<context>.py
│      Pure function or frozen dataclass. No imports beyond stdlib + Pydantic.
│
├─ A use case that reads or writes, or needs authorization?
│    → packages/aia_core/src/aia_core/application/<use_case>.py
│      Takes an issued scope context as its first argument.
│
├─ A table, a query, or anything touching the database?
│    → infrastructure/tables.py  (shape)
│    + infrastructure/<name>_repository.py  (access)
│    + migrations/versions/  (alembic revision — `make migration m="…"`)
│      Never a query outside infrastructure/.
│
├─ A call to something outside this process (HTTP, LLM, S3, SMS)?
│    → infrastructure/<name>.py behind a Protocol
│      + a test double + config-resolved selection. Never an env check inside.
│    A model call specifically: never directly. Build a ModelRequest naming a
│      capability and a data class, and call ModelGateway.invoke. A new provider
│      is a ProviderAdapter in infrastructure/model_adapters/ + recorded fixtures.
│
├─ An HTTP route?
│    → apps/api/src/aia_api/routers/<resource>.py   (validate, delegate, serialise)
│    + apps/api/src/aia_api/schemas/<resource>.py   (request/response models)
│    + the path asserted in .github/workflows/ci.yml api-contract
│      Project routes live under /api/v1/studies/{study_id}/ — always.
│
├─ Background work that can fail, retry, or cost money?
│    → a step kind named in aia_core.domain.workflow_templates, executed by a
│      StepExecutor in apps/executors/src/aia_executors/ (registered by kind in
│      its registry.py; the seam is apps/worker: aia_worker.executor). Never a
│      bare asyncio task and never in a request handler. It must be durable,
│      resumable and idempotent, and every metered call goes through the
│      context's reserve → dispatching → settled bracket.
│
├─ Something a user sees?
│    → apps/web/src/…  — renders state the server computed. No rules.
│
└─ A framework gotcha you just lost an hour to?
     → AGENTS.md, immediately, with the wrong and right versions side by side.
```

## 6. Anti-patterns — do not do these

Each entry names the real incident behind it and the command that audits for it.
A rule with a story attached survives; an abstract principle does not.

**A1. An import with no declared dependency.**
`pyjwt[crypto]` was imported by the identity layer and installed by hand into one
working virtualenv. A clean install had no `jwt` module and the first push to
`main` went red. Cataloguing this failure mode in someone else's code did not
prevent committing it here — the fix is verification, not vigilance.

```bash
python3 -m venv /tmp/clean && /tmp/clean/bin/pip install -q -e "packages/aia_core[dev,postgres]" -e "apps/api[dev]" && /tmp/clean/bin/python -m pytest -q
```

**A2. A tool path that only exists on one machine.**
The Makefile hardcoded `.venv/bin/python`. CI installs into the runner's
interpreter and has no `.venv`, so `make openapi` died on "No such file or
directory". Tooling resolves its interpreter; it does not assume one.

```bash
grep -rn '\.venv/bin' Makefile tools/ .github/
```

**A3. A contract assertion that outlived the contract.**
Projects moved under `/api/v1/studies/{study_id}/projects` when Client/Study
became isolation boundaries, but CI still asserted the flat `/api/v1/projects`.
The check passed on a route that no longer existed. Contract assertions move in
the same commit as the contract, and an *inverse* assertion is added where the
absence matters — any project route outside a study prefix now fails the build.

**A4. Scoring *unknown* as *good*.**
Coalescing a missing value to a neutral-looking default silently rewards the
absence of data. For every hit, ask one question: *does this treat unknown as
good?*

```bash
grep -rn '|| 0\b\|\.get([^)]*, *0)\|or 0\b' packages/aia_core/src apps/api/src | grep -v tests
```

**A5. Stamping a guess where null was available.**
An upsert that replaces only the fields a source provided will let a *wrong
non-null* value overwrite good data an earlier pass stored, where null would have
left it alone. A parser's catch-all falls back to a reliable secondary source and
then to null — never to a placeholder.

```bash
grep -rn "'other'\|\"other\"\|'unknown'\|\"unknown\"" packages/aia_core/src | grep -v tests
```

**A6. Producer/consumer enum drift.**
An enum emitted in one module and matched in another, with no shared definition,
drifts silently. Anything emitted and never matched, or matched and never
emitted, is a finding. This is the highest-yield check there is — and the reason
every stage id, scope role and provider state has exactly one definition in
`aia_core.domain`.

```bash
grep -rn 'class .*StrEnum' packages/aia_core/src/aia_core/domain/
grep -rn 'StageState\.\|ScopeRole\.\|ProjectStatus\.' apps/ packages/ --include=*.py | grep -v domain/
```

**A7. Boundary parsing without a plausibility guard.**
A parser that strips non-digits will *concatenate* a string holding two numbers.
Audit every integer parse and every config read, and ask what a malformed value
does.

```bash
grep -rn 'int(\|float(\|os.environ\[' packages/aia_core/src apps/api/src | grep -v tests
```

**A8. A guard on one path only.**
If a value can arrive from a structured source *and* from extraction, the same
bounds apply to both. The structured source bypassing the guard is exactly how a
wrong number ships.

**A9. Using the working tree to inspect another ref.**
`git checkout origin/main -- .` was run to check whether some compiler warnings
were pre-existing, and it wrote that branch's version over ~20 working files. It
was recoverable only because everything happened to be committed already. Read
refs; never check them out over your files. See CLAUDE.md §5.

**A10. Deleting the signal to get green.**
No test is skipped, disabled, quarantined or loosened to make a build pass. A
failing test is a finding. Runtime `pytest.skip(...)` for a genuinely absent
environment (no PostgreSQL, no legacy reference checkout) is legitimate and used
deliberately; a static `@pytest.mark.skip` is not, and `layer_check` rejects it.

## 7. Testing contract

| Layer | What must be tested |
|---|---|
| Domain | Every public function, happy + error paths. Valid, invalid, edge |
| Application | Every use case; every authorization refusal, by type |
| Infrastructure / repositories | Round-trip, isolation predicate, concurrent access |
| Adapters (storage, identity, providers) | Mocked transport; ≥3 real fixtures per parser, asserting every field. Model adapters: one recorded exchange per error class, and every fixture states whether it is a live capture |
| Workflow / jobs | Success, missing record, upstream failure, retry, cancellation |
| Worker | Every row of the outcome table in `aia_worker.worker`, in process; contention, `SIGKILL`, `SIGTERM` and cancellation across **real processes** on PostgreSQL |
| API | Response shape, auth guards, error cases, and the path in the contract check |
| Web | Mount, events, auth guards |

**Every public function added to the domain or application layer must have
tests. No exceptions.** Every new job and event module gets its own test file.

Concurrency semantics are tested against real PostgreSQL with
`AIA_REQUIRE_POSTGRES=1`, which turns a missing database into a failure rather
than a skip. Sequential suites pass while two workers claim one step; only real
contention detects it.

## 8. CI tiers

CI runs on every pull request and on every push to `main`
([ci.yml](.github/workflows/ci.yml)). A check that fails for reasons nobody
intends to fix today trains everyone to ignore red, so every step sits in a
declared tier.

| Step | Tier |
|---|---|
| `ruff check` / `ruff format --check` | **blocking** |
| `mypy --strict` | **blocking** |
| `make layer_check` | **blocking** |
| `make exposure_check` | **blocking** |
| `alembic upgrade head` / `alembic check` / downgrade-to-base | **blocking** |
| `pytest` — core + API, on PostgreSQL and on SQLite | **blocking** |
| Parity-matrix consistency (`test_parity_matrix.py`, inside the pytest steps) | **blocking** |
| Concurrency suite with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| Worker suite, including real worker processes, with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| Executor suite (the `develop_snapshot` step under the real loop, the develop seed, the smoke module) with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| API contract (OpenAPI paths + study-scoping assertion, now covering `/runs` and `/artifacts` too) | **blocking** |
| Frontend `lint` / `tsc --noEmit` / `build` | **blocking** |
| Startup smoke: migrate, boot, end-to-end lifecycle over HTTP; the worker boots **with the real executor registry** and stops on `SIGTERM` with no error logged | **blocking** |
| Committed-provider-key scan | **blocking** |
| `pip-audit` | advisory |
| `npm audit --audit-level=high` | advisory |
| Parity suite against the legacy prototype | **blocking when it runs** (no more `|| true`); skips without the withheld archive, reported `NOT_EXECUTED` |
| Golden fixtures F1–F9 (vendored, inside the pytest steps) | **blocking** |
| Golden fixtures F10–F11, pin checks, and population / evidence reference parity against the reference repository | **blocking when they run** (`golden-fixtures` job); skipped without the deploy key *(see below)*. The evidence layer's recovered decision tables need no checkout and run in the blocking `pytest` step |
| Parity status — one verdict per capability from every JUnit file | **blocking on `FAIL`**; `NOT_EXECUTED` / `NOT_RUNNABLE` reported in the step summary |

This deviates deliberately from the tiering in the development rules, which puts
lint and types in the advisory tier. That tier exists for day one of adoption.
Here both are already green and enforced, so demoting them would be a ratchet
running backwards.

### Pending cleanup — what must happen before each advisory check is promoted

| Advisory check | Promotion condition |
|---|---|
| `pip-audit` | Drop `|| true`, and replace the placeholder `--ignore-vuln GHSA-0000-0000-0000` with a real, dated, individually justified allowlist. Blocked on: a first clean run to establish the baseline. |
| `npm audit` | Drop `|| true` once `apps/web` transitive advisories are at zero or explicitly waived. Blocked on: the `apps/web` rewire (it is still mock-backed). |
| Parity suite | 94 parity and characterization tests report as skipped in CI because they execute the legacy code, which exists only inside the withheld archive. **The archive is deliberately not a CI dependency.** Promotion needs the archive's licence decision and an EU-resident home (`REF-WITHHELD-REFERENCE-ARCHIVE`). Until then **anyone changing domain logic runs them locally against `AIA_LEGACY_REFERENCE`**, and `parity-status` reports them as `NOT_EXECUTED` — never as a pass. |
| Golden fixtures | A human provisions a read-only deploy key on `AiAnalytics-AIA/AIA-reference` as the `AIA_REFERENCE_DEPLOY_KEY` secret, then sets the repository variable `AIA_REQUIRE_REFERENCE_REPO=1`. From then on a missing checkout fails the job instead of skipping. |

An advisory check with no promotion plan is decoration — delete it or schedule
it. Never move a check to advisory because it is failing on your branch.

## 9. Deployment

The `develop` environment is one EC2 host under Docker Compose
([ADR 0009](docs/architecture/adr/0009-single-host-develop-environment.md)):
`.github/workflows/deploy-develop.yml` deploys every CI-green head of `develop`;
`deploy/develop/` holds the Compose file, Caddyfile and the host's scripts, and
its `README.md` is the runbook; `infra/develop/` is the Terraform. The running
revision is always visible: `/api/v1/health` reports `build.sha`, the web
client's `/version` reports the same, and every artifact records it as its
`runtime_version`. Production compute remains undecided.

- Deploy only what CI verified: chain CD to CI's *completion* and guard on
  `workflow_run.conclusion == 'success'`, checking out
  `github.event.workflow_run.head_sha` — a `workflow_run` job runs in the
  default-branch context, so the default checkout is an **older** head than the
  one just verified. `deploy-develop.yml` does exactly this.
- **The deploy workflow must be on `main`.** GitHub registers `workflow_run`
  and `workflow_dispatch` only from the default branch, and runs *that* copy.
  A change to `deploy-develop.yml` is inert until a release PR carries it to
  `main`; a `develop` branch whose workflow differs from `main`'s deploys with
  `main`'s procedure (`AGENTS.md` § GitHub Actions; OI-37).
- One deployment at a time (`concurrency: deploy-develop`, never cancelling a
  deploy already running on the host). Migrations run **once, as a distinct
  deploy step** (`alembic upgrade head` from the api image at the SHA being
  deployed, after a `pg_dump`, before the services are replaced); neither the
  API nor the worker migrates on start, and `alembic downgrade` is never run
  automatically. Seeding is idempotent (`aia_executors.seed`).
- **No long-lived cloud keys** in the repository or in repository secrets. AWS
  access uses OIDC federation (`permissions: { id-token: write }`), scoped to one
  repository's `develop` GitHub environment. On the host the only credential is
  the instance role; the two application secrets live in SSM Parameter Store and
  reach the host as a root-only env file, never an image, a log or a step
  summary. Deployed processes must be told their revision (`AIA_BUILD_SHA`) and
  keep artifacts in S3 itself; `Settings.validate_for_production` refuses to
  boot otherwise.
- **CORS origins are an explicit allowlist read from typed config. Never `*`.**
- A scheduled workflow that rebuilds a heavy artefact pushes it tagged and stops.
  Promotion to live is a human command, and the job summary prints it. Nothing
  changes user-visible output on a cron with nobody watching.

## 10. What the system refuses to do

Product requirements expressed as architecture, not preferences. Restated here
because they are the constraints most likely to be "simplified" away by a change
that looks local:

- **No silent provider fallback.** Work parks in `WAITING_PROVIDER` (the
  reference called the quota case `WAITING_CREDITS`) or `WAITING_CAPACITY` and
  asks. It never quietly moves to a provider that costs
  money or changes provenance.
- **No spending past a budget.** A paid call is checked against the ceiling
  *before* it is made. Over budget means park and ask.
- **No invented certainty.** Evidence roles travel with the data. A modelled
  figure is never presented as a measurement.
- **No fake progress.** Real elapsed time and real stage transitions only.
- **No visualisation mutating research truth.** A dragged node saves a view
  override; results stay immutable.
- **Fail closed.** When a methodology precondition is unmet, the system blocks.
  It does not degrade.
