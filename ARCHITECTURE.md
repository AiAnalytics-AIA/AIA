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
| [analysis.md](docs/architecture/analysis.md) | A native run's analysis: evidence from its artifacts, the stored outcome, reconstruction by re-admission |
| [research-agents.md](docs/architecture/research-agents.md) | Native design-proposal jobs: the eight actions, frozen context, review and acceptance |
| [research-journey.md](docs/architecture/research-journey.md) | The research journey's integration contract: who owns each stage, the interfaces between jobs, shared files, what "accepted" means |
| [artifacts.md](docs/architecture/artifacts.md) | Artifact lifecycle and storage |
| [scope-and-authorization.md](docs/architecture/scope-and-authorization.md) | Client/Study isolation |
| [deep-research.md](docs/architecture/deep-research.md) | Deep Research: tracks, grounding, query classes, quarantine, the tool-cost contract |
| [security.md](docs/architecture/security.md) | Threat model |
| [sociomapa-deterministic-engine.md](docs/architecture/sociomapa-deterministic-engine.md) | Sociomapping engine: what is ported, declared and refused |
| [sociomapa-methodology-decision.md](docs/architecture/sociomapa-methodology-decision.md) | The D6 decision package for the methodology owner |
| [simulation-deterministic-engine.md](docs/architecture/simulation-deterministic-engine.md) | Simulation core boundary and parity status |
| [adr/](docs/architecture/adr/README.md) | The decision records, with the reasoning |

---

## 1. The one idea

**A project is the source of truth. Workflows and jobs only orchestrate work
against it.** A content change creates a new immutable revision; each stage's
material inputs are fingerprinted, so only the changed stage and everything
downstream of it reopen. Everything below exists to keep that rule testable
without a database, a network or a provider key.

## 2. Layers

Each layer depends only on the layers its row names, and every dependency points
toward the domain; `make layer_check` holds the rows (§3). `aia_core.domain` is the universal
seam, callable from any layer above. Each subsystem has exactly one public entry
point; nothing outside it touches its internals.

| # | Layer | Path | Owns | May depend on |
|---|---|---|---|---|
| 1 | **Domain** | `packages/aia_core/src/aia_core/domain/` | Pure rules: pipeline, project, providers, scope vocabulary, population versions and import contract, Sociomapping mathematics, evidence gates, analysis modules. Shapes and validation. No I/O. | Nothing internal. Stdlib and Pydantic, plus numpy, scipy and numba for numerical code (agreed 2026-10-19 for the methodology owner's `aia-sociomap-5`, #504). No I/O either way. The earlier Sociomap presets stay pure Python and byte-identical. |
| 2 | **Application** | `packages/aia_core/src/aia_core/application/` | Use cases. **The only issuer of a scope context, and the only loader of population data.** Orchestrates domain + infrastructure. Reaches rows only through a repository. | 1, 3 |
| 3 | **Infrastructure** | `packages/aia_core/src/aia_core/infrastructure/` | SQLAlchemy tables and repositories, object storage, provider gateways. Every external service behind a protocol. | 1 |
| 4 | **Workers** | `apps/worker/src/aia_worker/` | Durable step execution: claim from the PostgreSQL queue, heartbeat, run the `StepExecutor` registered for the step's kind, record the outcome; every worker also reconciles. **Knows nothing about what a step does.** | 1, 2, 3 — never 5 |
| 4b | **Executors** | `apps/executors/src/aia_executors/` | What a step of each kind *does*, under the scope the lease issued and through the worker's `StepContext`. Registered by kind; the worker loads them from `AIA_WORKER_EXECUTORS`. Also the operator commands (seed, smoke) that act as a user would through the application layer. | 1, 2, 3 and `aia_worker.executor` — never 5 |
| 5 | **Transport** | `apps/api/src/aia_api/` | HTTP. Validates, delegates, serialises. **No business rules.** | 1, 2; 3 only outside `routers/` (the composition root `dependencies.py` and `main.py`, and `config.py` and `observability.py` for settings and redaction). Routers that import infrastructure today are a ratchet in `pyproject.toml` and leave it when next touched |
| 6 | **Presentation** | `apps/web/` | Next.js client. Renders server-computed state. **No business rules.** | 5, over HTTP |
| — | **Legacy unit** | `legacy/npc-panel-18.6.6/` | The NPC Panel 18.6.6 product, extracted byte-for-byte from the audited archive ([ADR 0011](docs/architecture/adr/0011-vendor-legacy-product-unit.md)). The rebuild's behavioural baseline and parity oracle. **Frozen: regenerated, never edited** (one exception to date: `runtime/hydrate_data.py`, hand-edited by PR #57, OI-68). Outside every code-quality gate by construction. Not part of the product deployment (ADR 0018 decision 5): it runs, when a comparison needs it, from `deploy/reference/` beside the develop host's product, behind a basic-auth gate on the host's loopback. | Nothing. Neither the back end nor the web client calls it (ADR 0018); parity tests reach it over HTTP. |

Settings shows AI from two sources and calls neither a connection. The settings
document's `ai_runtime` describes the native runtime from code: the providers the
worker calls (`aia_core.domain.providers.NATIVE_PROVIDERS`), its role credential,
and each native AI activity with its capabilities, versions and switches
(`apps/executors/tests/test_settings_presentation.py` holds it to the worker's
composition); the study Research Lead is one of them, `study_lead` (capability `STUDY_LEAD`,
switches `AIA_AI_RUNTIME_ENABLED` and `AIA_AI_RESEARCH_LEAD_ENABLED`;
`apps/api/src/aia_api/routers/settings.py:521-529 @ 1648e6d5`). The prototype's providers are marked `HISTORICAL` and its project
fields sit in `ai_history`: readable, never offered. The web `/config` endpoint
may expose nonsecret runtime configuration for Settings (each switch by variable
name, Bedrock model/profile, source region and approved data classes). Neither is
a provider health test or authority to invoke a capability, and the page never
says connected or verified. Native design jobs have a separate activation switch;
an active fieldwork route does not enable them. Product-only Caddy
retirement blocks legacy credential/login/probe endpoints after the existing
gate; the independent oracle and pinned reference application stay unchanged.

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

`make layer_check` runs two halves: `tools/layer_check.sh` (grep rules) and `lint-imports`
(import contracts, `[tool.importlinter]` in the root `pyproject.toml`). CI's Backend job runs the
target; the docs-only job runs the script alone. Network egress is fenced by ruff (`TID251`,
banned-api in the same file). Both bans are by import name, so `importlib.import_module` and
`__import__` are not seen; two dynamic-import sites exist, `domain/methodology/resolution.py`
(restricted to `aia_core.domain.`) and `aia_worker/registry.py` (the module
`AIA_WORKER_EXECUTORS` names: under `aia_executors.`, refused before it is imported, except
under `AIA_ENV=local` or `test`; an unset or unknown `AIA_ENV` counts as deployed).

| Rule | Prevents |
|---|---|
| domain imports no framework, driver or SDK | The domain becoming untestable without a database |
| the core's layers: application above infrastructure above domain (import contract) | A domain that reaches infrastructure, or infrastructure that reaches application, by any import form (the grep rule it replaced missed `from ...` and `import a.b`) |
| the application reaches the tables only through a repository (import contract, a ratchet: `develop_seed`, `scope` and `workspace_migration` listed, leaving as their queries move behind repositories; a line no import matches fails) | A use case that queries a table itself and drops the isolation predicate its repository carries (`owner=`, the resolved client, the study) |
| application knows nothing about HTTP | Use cases that only work behind FastAPI |
| infrastructure knows nothing about HTTP | Adapters that cannot be reused by a worker |
| AWS SDK stays behind the storage adapter and the Bedrock signer (`aws_signing.py`: SigV4 and the role credential only) | `boto3` becoming a mandatory dependency of the whole package, or a botocore client calling Bedrock behind the gateway |
| `sentry_sdk` is imported only by the error reporter (`infrastructure/error_tracking.py`; the tests that drive it over a capturing transport named) | A second error client that sends without the redaction, the dropped bodies and the missing locals the reporter guarantees |
| no botocore client is built for Bedrock | A second call path under the adapter that retries and chooses endpoints on its own (ADR 0005 A, ADR 0010) |
| no database access in the HTTP layer | A handler opening a Session, and deciding something the domain never saw |
| no ORM tables in the HTTP layer | Queries written where they cannot be tested without the whole stack |
| routers reach infrastructure only through the application layer (import contract, a ratchet: the routers that did when it landed are listed edge by edge, and leave the list when next touched; a line no import matches fails) | A route that queries or stores where the application layer never sees it |
| scope contexts are issued only by `ScopeResolver` | A request body, tool payload or model-generated argument widening its own scope |
| provider SDKs and gateway libraries are not imported (core or API) | A second model-call path that can retry, fall back or substitute without `GovernedModelGateway` deciding to (ADR 0005) |
| only the executor compositions import the model adapters (import contract) | A second model-call path: an adapter driven without the gateway's retry, budget, egress and provenance (ADR 0005) |
| only the AI runtime composition builds the model gateway | A gateway nobody configured: a route, policy or registry outside `ai_runtime.py`'s validated settings |
| only the step's model caller invokes the model gateway | A model call with no reservation, no settle and no journal under the lease (`ai_step.py`, StepModelCaller) |
| network egress only from the transport modules (ruff TID251: `urllib3`, `httpx`, `requests`, `urllib.request`, `http.client`, `socket`, `ssl`; exemptions per file in the root `pyproject.toml`) | A connection with no residency check, pacing, TLS-refusal handling or record: web reads around RetrievalGate, model calls around GovernedModelGateway |
| only the executor compositions import a live network wire: `deep_research_live` and `deep_research_runtime` (web search, Common Crawl), `ai_runtime` (the model transport); every app and the core's domain and application layers are checked, indirect imports included (import contract; RetrievalGate reaches the index and archive through `infrastructure/archive_index.py`, which loads no wire) | A module building a connection no composition configured |
| the API never builds its own scope context | The same, at the edge where untrusted input arrives |
| the worker never builds its own scope context | The same, inside the process where model-driven code will run |
| the worker knows nothing about HTTP | A worker that only works behind a web server |
| the API, the worker and the executors are independent but for the executor seam, `aia_worker.executor` (import contract) | A worker that loads a step, an executor that drives the loop, or anything of the API outside the API, and its request state leaking into jobs |
| the worker imports nothing domain-specific | The executor seam becoming decoration: the loop importing the AI or research code it is supposed to be ignorant of |
| executors know nothing about HTTP | A step implementation that only works behind a web server |
| executors never build their own scope context, admit their own claims, or build an unscoped repository | A claimed step writing another client's artifacts, or a number reaching a result without the admission gate, from inside the process where model-driven code will run |
| the API never executes workflow steps | Expensive work inside a request, holding a lease exactly as long as a browser stays connected |
| the API never builds or invokes the model gateway or an adapter | A model call inside a request: no lease, no reservation, no heartbeat, no recovery |
| only the AI runtime composition (`aia_executors/ai_runtime.py`) builds the Bedrock adapter | A route nobody configured, built from values nobody validated |
| only the work queue may query across studies | An unscoped `WorkflowRepository` anywhere but `WorkQueue` -- a query over every client's studies |
| Client Knowledge rows are reached only through `ClientKnowledgeRepository` (never by the API, the worker or the executors), its folders, labels and item filing included | Knowledge read from a global pool and filtered afterwards, or changed without a person's write or an accepted proposal, and a revision (ADR 0015, 0019) |
| a client's contacts are reached only through `ClientProfileRepository` (never by the API, the worker or the executors) | Personal data on the client record reaching a study context or a model request |
| a client's sources are reached only through `ClientSourceRepository` (never by the API, the worker or the executors) | Stored material read outside its client, or taken for knowledge without a person accepting a proposal from it |
| runtime populations are issued only by the canonical loader (and never by the API) | A second loader returning different population semantics from the same bytes (reference F10, R4) |
| population panels are parsed only by the canonical loader (and never by the API) | The first step of that second loader: a consumer reading the panel itself |
| population-operator grants are issued only by the population authority (and never by the API) | A study context, an organization owner or a request body moving LIVE for every tenant (OI-8) |
| the Sociomap preset `AIA_SOCIOMAP_V1` is never named outside the Sociomap domain package | An engineering preset silently filling in a missing spec, and becoming client methodology by default ([sociomapa-deterministic-engine.md §13](docs/architecture/sociomapa-deterministic-engine.md#13-computable-is-not-deliverable)) |
| the study design table is touched only by its repository (never by the API, the worker or the executors) | A Study's design project -- and the revisions its runs execute -- found by something other than the Study's scope (ADR 0016) |
| only the design repository and the research runs name the design project's owner (`projects.owner`), and no app does | A generic project route reading or writing a Study's design, around the validation that makes content a Design Revision |
| no statement updates a project revision (the ORM refuses an UPDATE; this forbids the bulk one) | A run's executed content changing under it |
| licence determinations and policies are built only in their policy-data module, never by an app | An approval of panel-derived transmission nobody gave (ADR 0016 decision 5, OI-61) |
| the fictional fieldwork generator is imported only by the workbench composition; nothing in the API or worker imports either, and no deployment names it | Fictional respondents reaching a deployed run, or a deployed worker configured with the test composition |
| recorded web retrieval (Deep Research's search and fetch doubles) is defined only beside the web adapters and built only by the recorded composition (`aia_executors/deep_research_recorded.py`); application and domain code never name it, nothing in the API or worker imports it, and no deployment names it | A replayed page standing in for a live source: a recorded route selected as a production fallback, or a deployed worker composed with it |
| a validation's persona arms are built only by the validation executor (`aia_executors/validation.py`); nothing else in the core, and nothing in the API or worker, imports `holdout.arms` | A client research run showing a respondent another person's profile, or none, or carrying a validation's exclusions |
| claims are admitted only by the evidence admission gate | A model's number reaching a result without passing field policy, joint structure, support and interval checks |
| the API never admits its own claims | The same, at the edge where untrusted input arrives |
| a joint status is issued only by its loader | A hand-built permissive `CORE_JOINT_STATUS` certificate reaching the claim gate |
| no statically skipped or xfailed tests | Deleting the signal instead of fixing the defect |
| the web client does not talk to a database | The presentation boundary crossed in the most expensive possible way |

Two things make this survive contact with a busy week:

- **Exemptions are named in the rule itself.** `dependencies.py` and `main.py`
  are exempt from the database rule because they are the composition root;
  `storage.py` is exempt from the AWS rule because it *is* the adapter. Each
  carries a comment saying so. An exempt path is the file's path from the repository
  root, never a basename; a rule whose path or exempt path does not exist fails
  rather than skipping (`test_layer_check_tool.py`). Pretending an exception does not exist is what
  kills these scripts.
- **Rules are a ratchet.** A rule is added only once it already passes, so the
  check is green the day it lands and a red run always means a regression, never
  a backlog.

To add one: state it in the script beside its `forbid` line and under Doc
follow-up in the PR (the docs PR adds it to the table above; CLAUDE.md §1), then
confirm it passes before committing.


### Scoped research testing

An organization administrator may propose and approve a separate expiring test policy
for one explicitly fictional study (`infrastructure/deep_research_settings_repository.py:437
@ db6db022`). It never writes organization setting versions or approvals. The normal
organization reader remains unchanged. The repository resolves the newest study approval
only in local/test/develop, through the exact organization, client and study, with the
client on the existing fictional-client allowlist, a live expiry and a positive study
budget no larger than the approved cap (maximum USD 20). It validates every required
live setting and records provider test permission; values do not establish a permanent
provider entitlement. Proposals carry a seal, and approvals/withdrawals are append-only
and audited under the existing independent-review rule. Newest withdrawal or expiry
never revives an older grant (`test_deep_research_sandbox_policy.py @ db6db022`).

The enqueue stores the exact `test_policy_approval` receipt alongside its normal settings
pin (`application/deep_research.py:657 @ db6db022`). An existing run retains its pinned
authority; later scope, environment, budget, expiry or withdrawal checks apply to new
enqueues. Per-call study reservations, material classification, network/robots rules and
evidence admission continue to apply. The two test-policy tables are readable/writable
only by the settings repository (`tools/layer_check.sh:217 @ db6db022`); no request body
can grant approval or supply deployment prices.

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
  `ScopeResolver` through a module-private sentinel, and so is the
  `ClientContext` a client workspace reads through (`ClientPermission` says what it
  allows). A context is issued to any active member of the organization, who holds
  the one Researcher role on every client and study of it
  ([ADR 0019](docs/architecture/adr/0019-two-roles-and-human-ai-gates.md)); the
  organization is the isolation boundary. Repositories refuse anything that is not
  an issued context, by type; see
  [scope-and-authorization.md](docs/architecture/scope-and-authorization.md).
  Client Knowledge is read only inside such a context -- never a global pool
  filtered afterwards -- and changes only by a person's own write or when a study's
  proposal is accepted, either of which writes a new revision ([ADR 0019](docs/architecture/adr/0019-two-roles-and-human-ai-gates.md), [ADR 0015](docs/architecture/adr/0015-client-first-product-interface.md)).
  A client's document reaches a model only through the client's own work, paid by
  the client: grounded quotes only, filed as proposals a person accepts (lifecycle K2d).
  Three things beside it are deliberately not knowledge, and `for_study` reads none
  of them. **Filing** -- a client's folders and labels -- is organization: it writes
  no revision, moves no date (an item's folder is kept off the item row so
  `modified_at` never moves) and no model sees it. **The profile and contacts** live
  on the client record; no study context or model request reads them. **A source** --
  the client's stored original, kept once per client by its SHA-256 with every
  occurrence -- accepts nothing by being stored; knowledge comes from it only as a
  proposal a person accepts (lifecycle plan § K2). A SOURCE, DOCUMENT or DATASET item
  may name one of its client's sources by id (`content.source_id`, `knowledge.source_ref`;
  the API answers 422 `unknown_source` for any other client's); the item never holds the
  file, and a study's proposal cannot attach one (client-workspace C7a).
- **A research study's working content is AIA's, found only through the Study**
  ([ADR 0018](docs/architecture/adr/0018-aia-runs-without-18-6-6.md), OI-58).
  `StudyWorkspaceRepository` keeps it in the Study's owned working project
  (`projects.owner = study_workspace`, invisible to the generic project routes) and
  names its state (`ContentState`); a save names its base revision and a stale one
  is refused, so two editors never overwrite each other silently. A study bound to
  18.6.6 before ADR 0018 is `AWAITING_MIGRATION` and refuses edits until its content
  is migrated; the 18.6.6 project id it keeps is lineage, never a way in. The
  migration (`application/workspace_migration.py`, run as `aia_executors.legacy_workspace`)
  reads a *copy* of the unit's store (`infrastructure/unit_project_store.py`, read-only,
  a live database refused) and writes each Study through the scope the named operator
  holds on it, validated against the copy in the Study's own transaction; nothing in
  the product reads the unit's state.
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
  hash. A prompt may state a rule; it is never the only thing enforcing it. Decided and not built yet:
  every key finding of an analysis module cites an admitted claim or is refused (MVP-23,
  `evidence-integrity#1`); 18.6.6's run QC is a warning, never a gate (MVP-24,
  `evidence-integrity#2`, `#3`); a module with no supported finding blocks the report (MVPQ-04,
  `evidence-integrity#9a`, `#9b`).
- **A research run executes a Design Revision, and nothing else**
  ([ADR 0016](docs/architecture/adr/0016-research-execution-and-model-transmission.md)).
  The browser submits the design it shows; `StudyDesignRepository` stores it as
  an immutable, content-deduplicated revision of the Study's own design project,
  which is *owned* (`projects.owner = study_design`) so no generic project
  repository can see it. A run names a revision by id; it is found only through
  the Study (`ResearchRuns`), and its artifacts are read only through the run
  (`research_artifacts`, `ArtifactRepository(owner=)`), never by id alone.
  Respondent rows are never sent to the browser, with one named exception, decided and not
  built yet (`mvp-cohesion.md` F2, MVPQ-03; `segment-maps-and-drilldown#6`): one route, under
  `EDIT_STUDY`, returns one respondent's stored attributes and answers, every field labelled
  modelled, never generated persona prose; it is internal only, never in an export, a report or a
  map snapshot, and never an `AdmittedClaim`. The Sociomap artifact is served only with `EDIT_STUDY`. An analysis retry (`retry_failed_modules`) is a new run
  linked to the original whose fieldwork step takes the original's dataset by
  artifact id and SHA-256 (`frozen_dataset`), verified and never substituted: it
  collects nothing, and the report's gate over all eight modules is unchanged.
- **Research assistants propose; a person accepts against an unchanged revision.**
  The `research_agent` workflow freezes approved Study-visible knowledge and
  harness context at enqueue. Its eight closed actions use `StepModelCaller`;
  no API or browser invokes Bedrock. Results and artifacts stay Study-scoped.
  `StudyDesignRepository.submit_if_current` locks the Study against every design
  writer; stale proposals cannot overwrite a newer revision. Library instruments,
  audience filters and approved dimensions remain controlled by code or a person.
  Reload follows existing jobs; it never creates another call. Advice is not an
  admitted report claim. Activation, budget and classification are independent
  of fieldwork; confidential knowledge cannot use the fictional Class C allowance.
  See [native Research agents](docs/architecture/research-agents.md).
  An accept is one server transaction under the Study lock
  (`application/proposal_accept.py:92 @ c7327072`, `accept_into_working_copy`; ADR 0026
  decision 6): the item-level stale rule against the working revision the proposal's Design
  Revision names, the merge into the working copy item by item (`domain/design_items.py`
  `merge_items`: what the proposal touches takes its value, everything else keeps the person's),
  the Design Revision naming that working revision, and the approval-ledger row; a failure at any
  step writes none of them (`test_a_failure_at_the_ledger_leaves_no_revision_written`). A
  stale proposal is refused, naming its items: 409 `stale_proposal`, `details.conflicting_items`,
  why `design_moved`, `unknown_baseline` (refused, never presumed current), `items_changed` or
  `lineage_changed`
  (`test_a_job_started_after_an_edit_is_checked_against_its_designs_working_revision`). Every
  Design Revision names the working revision it was made from, checked by canonical hash
  (`study_design_repository.py:147-177 @ c7327072`, `design_not_from_workspace`). Design
  Research's accept writes the working copy through the same function
  (`application/design_research.py:135-142 @ c7327072`, reason `design_research_accepted`).
- **The Research Lead proposes; a person decides**
  ([ADR 0026](docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md)). A Lead turn
  is a `research_lead` worker step (`aia_executors.research_lead`); the API calls no model. Its
  output is closed (`domain/research_lead.py:360 @ c7327072`, `LeadOutput`) and holds no tools.
  Beside the agent-proposal accept, the Lead has its own human-only routes, each needing
  `APPROVE_GATE` and writing its approval-ledger row in the same transaction
  (`apps/api/src/aia_api/routers/lead.py:386-446 @ c7327072`):
  `POST …/lead/turns/{turn_id}/edits` accepts or dismisses the turn's edits under the Study lock,
  a stale `base_revision` refused with the current one (`subject_type = 'lead_edit'`);
  `POST …/lead/turns/{turn_id}/request` starts the job a turn prepared, behind the study's spend
  limit (`'lead_job_request'`); `POST …/lead/turns/{turn_id}/self-update` applies, on the
  turn's own researcher's yes, what would reach every client (`'lead_self_update'`). The ledger's
  `subject_type` check admits the three (`infrastructure/tables.py:1697-1701 @ c7327072`,
  migration `7b3c32892aa9`). The generic run, events and artifact routes never serve a
  `research_lead` run (`test_the_generic_run_routes_never_serve_a_lead_turn`). An accept may be
  automatic only by the researcher's own standing choice (`researcher_leads.auto_accept_text_edits`,
  off by default, `PUT /lead/preferences`): the same `…/edits` route with `auto: true`, refused
  `auto_accept_off` without the choice, taking text edits only (`domain/research_lead.py:314-327
  @ 0b4e05e5`, `is_text_edit`; anything else `not_a_text_edit`), refused whole as `stale_turn`
  when the turn's frozen working revision is not the current one, and each ledger row says
  `"auto": true` (`application/research_lead.py:541-566 @ 0b4e05e5`;
  `test_research_lead_api.py::test_an_automatic_accept_takes_text_edits_only_and_says_so_in_the_ledger`).
- **A Deep Research finding is a quote in a captured source, or it is nothing**
  ([ADR 0017](docs/architecture/adr/0017-deep-research-external-retrieval.md),
  [deep-research.md](docs/architecture/deep-research.md)). `domain/deep_research/` is pure: code
  chooses the subjects and tracks (research questions and tracked objects), and a model only
  proposes queries and findings in closed schemas, holding no tools. A finding is admitted only
  when its quote occurs in a content-addressed snapshot the same track retrieved and every number
  of its claim is in that quote; source quality comes from declared tables, never the agent's
  score. A query's data class is the most restrictive of its context, its client terms and any
  Class A overlap, and nothing lowers it; a design's class there is an operator's exact-bytes
  classification, not the design rule, so a run on an edited design parks until an operator
  classifies it (`apps/executors/src/aia_executors/deep_research/plan.py:163 @ 64cc1380`; the
  product owner, 2026-10-19, OI-129). A captured source reaches Client Knowledge only when a
  person checked it and clicked "Ověřeno, přidat zdroj": `POST …/deep-research/runs/{id}/sources/
  {source_ref}/knowledge` reads the URL, title and quote from the run's verified sealed bundle,
  never from the browser, and writes a `SOURCE` item once per client and address, or a proposal
  where self-approval is off (`application/verified_sources.py:47 @ 0b4e05e5`,
  `apps/api/tests/test_verified_sources_api.py`). The 18.6.6 leakage rule (EXACT) bars a finding from
  respondent context; respondent context is re-screened against the final questionnaire. Tool
  calls follow the model-call bracket (reserve, durable dispatch, outcome, uncertain at its
  ceiling), and a priced tool route is refused until tool spend is held against the study budget.
  A query or URL leaves only through `RetrievalGate`; a run is frozen at enqueue
  (`DeepResearchRuns`) and executed by six steps whose completed tracks, snapshots, verification
  batches and brief are reused by fingerprint, while anything a gate refused is its run's alone.
  Production has no retrieval, so web tracks are blocked; recorded retrieval is local and test only.
  Decided and not built yet (the owner, 2026-10-19, #500): for the MVP, classification in Deep
  Research is replaced by one declared posture per client, `OPEN` or `CLASSIFIED` (the default),
  pinned in the run's request at enqueue and copied by a retry. An `OPEN` client's design and
  queries are not classified and may go to any composed route; a `CLASSIFIED` client behaves as
  above, so its web tracks stay parked (`deep-research-web-search#53`; ADR 0008 amendment pending).
  The Class B route is deferred whole (`class-b-search-route`). Model routes, EU residency,
  grounding and the evidence gates are unchanged.
- **Fieldwork is a boundary, and `ai_runtime` is answered only by AI respondents.**
  The deployed composition (`aia_executors.registry`) has no deterministic dataset
  producer. It builds the AI respondent engine (`aia_executors.ai_fieldwork`) only
  when `AIA_AI_RUNTIME_ENABLED` is set and every AI runtime key validates (the
  worker refuses to start otherwise); without it a run parks at fieldwork
  (`WAITING_PROVIDER`, `ai_runtime_unavailable`) and is never resumed by time. The
  engine asks the gateway's `preflight` before reserving anything, and a residency
  or licence refusal parks the run the same way, naming the gate; nothing is sent.
  The model returns only one respondent's probabilities, selections or short text
  under a strict per-block contract; facts the persona has are answered by code
  (`respondent_facts`), the response process and a seeded draw decide the answer
  (`respondent_behavior`). Who the personas are is the run's pin, set at start and kept by a
  retry (`PersonaSource`): the fictional roster, whose datasets carry
  `data_origin = SYNTHETIC_AI_FICTIONAL`, or -- behind `AIA_AI_POPULATION_PERSONAS_ENABLED` --
  respondents drawn from the population the run recorded (`panel_source.panel_plans`), Class A,
  `MODELLED_AI_PANEL`, the dataset naming its respondent system; a worker without that path
  parks such a run, and a sample or persona the population cannot give is refused by name
  before any call. The fixture's
  `SYNTHETIC_FIXTURE` (in `aia_executors.workbench`, refused unless `AIA_ENV` is
  `local`/`test`). The client-facing origin gate is an allowlist,
  `CLIENT_ADMISSIBLE_ORIGINS` (ADR 0024 §2): a synthetic origin is refused as
  `SYNTHETIC_DATA_ORIGIN`, and a missing origin or any origin not on the list as
  `ORIGIN_NOT_ADMISSIBLE`, so an origin added later is refused until it is decided.
  Labels read an origin only through `origin_kind` (SIMULATED / MODELLED / UNKNOWN);
  no surface tests origin-set membership itself, and an unknown origin is labelled
  unknown, never read as real fieldwork.
- **A model call from a step goes through `StepModelCaller`, and nowhere else.**
  One reservation per logical request (PROGRESS D11, resolved), checked by the
  gateway on every call and settled once with their sum; dispatch is
  `StepContext.dispatching` (checkpoint, fenced, committed) before the call leaves;
  outcomes are ledgered by `StepContext.record_usage`, unfenced, so a lost lease
  still records the provider's answer; an uncertain outcome is left for
  `RECOVERY_REQUIRED`. The heartbeat thread holds the lease through a blocking call.
- **A respondent request takes its design's class**: Class B by the owner's rule
  (`domain/material_rules.py`, ADR 0008 Amendment 2026-10-19), raised and never lowered by an
  operator's exact-bytes classification or the personas' class
  (`apps/executors/src/aia_executors/ai_fieldwork.py:418-432 @ 64cc1380`). A client the operator
  declared fictional (`AIA_AI_FICTIONAL_CLIENT_IDS`) no longer makes it Class C: a route approved
  for Class C alone refuses it before anything is sent
  (`test_an_unclassified_questionnaire_is_class_b_by_rule_and_a_class_c_route_refuses_it`).
- **Two gates before any model call carries panel-derived data.** Residency
  (where the data may go) and licence eligibility (whether its source's licence
  permits that route) are separate refusals; `ModelRequest.data_lineage` has no
  default, and `GovernedModelGateway` runs both before any adapter. Every panel
  source is `APPROVED` for `bedrock-eu-primary` alone (OI-61, data owner,
  2026-10-12); any other route refuses it.
- **Integrated is not exposed.** The research Sociomap is computed from the
  unit's own relation matrix by AIA's engine, and its status is the Sociomap
  register's for the exact method and spec fingerprint that computed it
  (`domain/sociomap_register.py`): `aia-sociomap-3` is approved (the product owner,
  2026-10-13, D6), and every other method, `aia-sociomap-5` included, is `INTERNAL_ONLY`
  until registered. Every client-facing surface, export or report calls
  `require_client_facing`, which refuses an unapproved map and fails closed on a missing status.
- **A stored method is read by the contract it names; contracts are added beside
  each other, never edited.** A Sociomap spec and artifact carry their contract
  number (`read_spec` / `spec_payload`, `read_artifact`): contract 2 is
  `aia-sociomap-1`, unchanged and still fingerprinted `9d4dffea…`; contract 3 is
  `aia-sociomap-2`, the formula audit's object map. A payload naming no contract or
  an unknown one is refused, never read as the nearest. A research run pins the
  methods it computes (`SociomapMethod`: id, the spec as stored, its fingerprint)
  when it starts; the executor computes the pin, never the module's current preset;
  a retry keeps the original's pins; a run stored before pins existed reads as
  `aia-sociomap-1`. Only a method set the caller *chooses* changes a run's identity,
  so changing the default never re-pays for a revision's fieldwork. The same rule
  holds for Deep Research's envelope (ADR 0021): a run's purpose, target and lineage
  wrap the unchanged engine request.
- **A native run's analysis is internal, and an outcome is re-admitted whenever it is
  read** ([analysis.md](docs/architecture/analysis.md)). The Study's own questionnaire
  items become evidence fields only from what the run recorded
  (`domain/evidence/instrument.py`), under the policy their answers' origin selects --
  never a caller: `aia-instrument-evidence-1` for simulated answers, `-2` for
  `MODELLED_AI_PANEL` (ADR 0024 §3); any other origin is refused. Both are modelled,
  aggregate only, never one person's and never a measured fact. `-1` is `INTERNAL_ONLY`,
  which the claim gate refuses client-facing whatever the certificate or origin says. `-2`
  also needs a scope and the modelled-value disclosure on every client-facing claim
  (`MODELED_DISCLOSURE_ALWAYS`; it and `INTERNAL_ONLY` are AIA-only rules, never extracted
  from dictionary prose), and is `INTERNAL_ONLY` unless a `HOLDOUT_VALIDATED` validation was
  earned on the run's current respondent system (`validation.lifts_internal_only` over
  `respondent_system_fingerprint`: prompt, persona builder and mode, sampler, population
  version, model binding, response process). Native preflight and the gate both read the
  book, so a lift is honoured by both. A run with no panel has no certificate, and says so
  (`MISSING`). A stored module outcome holds the
  accepted draft, never claims: `application/analysis_results.py` rebuilds the evidence
  from the run's own artifacts, requires every fingerprint to match and puts the draft
  through the gate again, so a file cannot mint an `AdmittedClaim`. The executor
  (`aia_executors/analysis.py`) runs one module per step: what code can refuse is stored
  `BLOCKED` before anything is reserved, a gate refusal after three turns is an outcome
  too, and a provider failure is never one -- it goes back to the worker's recovery rules.
- **An internal report is a view of admitted analysis and the same run's frozen map.**
  `aia_executors/report.py` waits for eight analysis nodes and `sociomap`, rebuilds
  admission, then verifies the map's dataset SHA and specification fingerprint.
  Native report contract `aia-internal-report-4` includes the map SHA in reuse
  identity and stores all nine dependencies. Its images project contract-3 stored
  positions, heights and finite terrain triangles without fitting new geometry.
  The reading guide describes signed correlation distance targets, the planar
  approximation and each pair's sign/support; gaps remain gaps.
  `application/report_maps.py` supplies prose/table blocks and takes image bytes;
  print drawing remains in infrastructure. Missing maps are explained, missing
  required images and corrupt inputs are refused. The user-supplied 10 October
  2026 Claude Design Client Report Template is
  the print authority: original lockup and field, bottom-aligned editable cover,
  Source Serif 4 prose, IBM Plex Sans metadata and AIA/study/client running head
  with fine horizontal rules. Methodology precedes audience context, object
  findings and maps; admitted module prose is preserved. Table column weights
  are finite and positive and affect layout only. Frozen historical exports
  stay immutable; new exports use the new contract. The experimental companion
  report shares the updated renderer under `aia-sociomapping-report-3`. Internal,
  synthetic and pending-methodology gates do not become client approvals.
- **A contextual report selects its literature run explicitly.**
  `application/contextual_report.py:265 @ b3f1a881` verifies both study-owned runs,
  completed interpretation status, provenance, bundle seal and the exact frozen
  research/design lineage, then re-admits all eight analyses and validates the same
  run's sociomap dependencies. Contract `aia-contextual-report-2` exports a separate
  internal DOCX; it never overwrites the original report or calls models during export.
  Only accepted source claims enter its targeted literature chapter. Citation and
  number checks do not establish semantic validity: generated conclusions and
  model-authored gap reasons remain unapproved drafts outside the report. Complete
  numbers and periods stay in their cited source claims; extracted numeric metadata
  cannot independently establish comparability. External L citations stay outside
  the respondent evidence ledger. Unmet source needs and recorded acquisition steps
  remain explicit, alongside synthetic-data and targeted-review disclosures. The
  results panel starts interpretation research over a pinned analysis, selects the
  completed review in the download query and keeps generated interpretation behind
  a closed, explicitly unapproved disclosure. Publication anchors:
  `application/contextual_report.py:62 @ b3f1a881` and
  `apps/web/src/components/rehome/research/InterpretationResearch.tsx:125 @ b3f1a881`.
  See `test_source_claims_have_separate_citations_limits_and_fixture_disclosure`,
  `test_citation_valid_inapplicability_inference_is_not_published`,
  `test_partial_measure_period_does_not_replace_the_source_claims_full_range`,
  `test_corrupt_seal_and_foreign_synthesis_citations_refuse`, and the full report
  journey in `apps/executors/tests/test_analysis_executor.py`.
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
     → AGENTS.md, with the wrong and right versions side by side: written
       immediately under Doc follow-up in your PR, added by the docs PR
       (CLAUDE.md §1).
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

A pull request that changes only `.planning/`, `docs/architecture/adr/`, `CLAUDE.md`,
`AGENTS.md` or `ARCHITECTURE.md` runs `Documentation checks` (layering, exposure, plan
front-matter, committed-key scan) instead of the suites; the path list is the `changes` job in
`ci.yml`. A push to `main` or `develop` always runs everything.

| Step | Tier |
|---|---|
| `ruff check` / `ruff format --check` | **blocking** |
| `mypy --strict` | **blocking** |
| `make layer_check` | **blocking** |
| `make exposure_check` | **blocking** |
| `alembic upgrade head` / `alembic check` / downgrade-to-base | **blocking** |
| `pytest` — core + API, on PostgreSQL on every pull request; the SQLite run only on a push to `develop`, where it blocks the deploy; a collect-only pass over all four test trees in one session on every pull request, so a cross-tree module-name collision fails before the SQLite run on `develop` | **blocking** |
| Parity-matrix consistency (`test_parity_matrix.py`, inside the pytest steps) | **blocking**. Parity with 18.6.6 is information, never a release criterion (MVP-21): no capability is a release blocker, and a failing parity test still fails a pull request like any test (`mvp-cohesion.md` F9) |
| Concurrency suite with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| Worker suite, including real worker processes, with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| Executor suite (the `develop_snapshot` step under the real loop, the develop seed, the smoke module) with `AIA_REQUIRE_POSTGRES=1` | **blocking** |
| API contract (OpenAPI paths + study-scoping assertion, now covering `/runs`, `/artifacts` and the research `agent-jobs` routes) | **blocking** |
| Frontend `lint` / `tsc --noEmit` / `build` | **blocking** |
| Startup smoke: migrate, boot, end-to-end lifecycle over HTTP; the worker boots **with the real executor registry** and stops on `SIGTERM` with no error logged | **blocking** |
| Develop host configuration: `caddy validate` on the Caddyfile; from `caddy adapt`, `tools/caddy_routes.py` (the product hostname the only site, `/` → `/app/clients`, `/app` behind AIA's own gate and without the session cookie, no route to the 18.6.6 document and `/classic` only the web client's page, no upstream but the API and the web client, no panel gate); `docker compose config` on the product stack and on `deploy/reference` (its gate's rules validated too); `bash -n` on the host scripts | **blocking** |
| Committed-provider-key scan | **blocking** |
| `pip-audit` | advisory |
| `npm audit --audit-level=high` | advisory |
| Parity suite against the legacy prototype | **blocking when it runs** (no more `|| true`); skips without the withheld archive, reported `NOT_EXECUTED` |
| Golden fixtures F1–F9 (vendored, inside the pytest steps) | **blocking** |
| Golden fixtures F10–F11, pin checks, and population / evidence reference parity against the reference repository | **blocking when they run** (`golden-fixtures` job); skipped without the deploy key *(see below)*. The evidence layer's recovered decision tables need no checkout and run in the blocking `pytest` step |
| Unit-captured UI function fixtures `U<nn>` (`test_legacy_ui_functions.py`, inside the pytest steps) | **blocking** — the vendored unit's own JavaScript is the reference, so they need nothing |
| Route and UI function ledgers (`test_legacy_route_ledger.py`, `test_legacy_route_claims.py`, `test_legacy_ui_functions.py`, inside the pytest steps) | **blocking**; the reference-pin halves run in the `golden-fixtures` job |
| Parity against the running 18.6.6 unit (`oracle-parity` job, `-m oracle`) | **blocking when it runs**; skips without the `AIA_LEGACY_REFERENCE_*` secrets, reported `NOT_EXECUTED`; `AIA_REQUIRE_LEGACY_ORACLE=1` once they exist |
| Parity status — one verdict per capability from every JUnit file | **blocking on `FAIL`**; `NOT_EXECUTED` / `NOT_RUNNABLE` reported in the step summary |

This deviates deliberately from the tiering in the development rules, which puts
lint and types in the advisory tier. That tier exists for day one of adoption.
Here both are already green and enforced, so demoting them would be a ratchet
running backwards.

### Pending cleanup — what must happen before each advisory check is promoted

| Advisory check | Promotion condition |
|---|---|
| `pip-audit` | Drop `|| true`, and replace the placeholder `--ignore-vuln GHSA-0000-0000-0000` with a real, dated, individually justified allowlist. Blocked on: a first clean run to establish the baseline. |
| `npm audit` | Drop `|| true` once `apps/web` transitive advisories are at zero or explicitly waived. The mock-up and its editor dependencies are gone (ADR 0012). The baseline is clean: 0 advisories since `next` 16.3.6 and the transitive patch bumps (2026-09-24, OI-2); the promotion itself is the remaining step. |
| Parity suite | 94 parity and characterization tests report as skipped in CI because they execute the legacy code, which exists only inside the withheld archive. **The archive is deliberately not a CI dependency.** Promotion needs the archive's licence decision and an EU-resident home (`REF-WITHHELD-REFERENCE-ARCHIVE`). Until then **anyone changing domain logic runs them locally against `AIA_LEGACY_REFERENCE`**, and `parity-status` reports them as `NOT_EXECUTED` — never as a pass. |
| Golden fixtures | A human provisions a read-only deploy key on `AiAnalytics-AIA/AIA-reference` as the `AIA_REFERENCE_DEPLOY_KEY` secret, then sets the repository variable `AIA_REQUIRE_REFERENCE_REPO=1`. From then on a missing checkout fails the job instead of skipping. |
| Oracle parity | The reference unit listens only on the develop host's loopback (`deploy/reference`, ADR 0018 decision 5), which a GitHub-hosted runner cannot reach. Promotion needs a runner that can (inside the VPC, or on the host), and `AIA_LEGACY_REFERENCE_URL`, `AIA_LEGACY_REFERENCE_USER` and `AIA_LEGACY_REFERENCE_PASSWORD` (the reference gate's basic-auth credentials from SSM) as repository secrets. The job then sets `AIA_REQUIRE_LEGACY_ORACLE=1` itself, so an unreachable oracle fails rather than skips (OI-39). Until then an operator runs `make test-oracle` through an SSM port forward. |

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

The host deployment lock serializes both CI and operator deploys. Before ECR
login or downloads, `bin/image_retention.py` removes only unused, singly tagged
product images older than 48 hours in this deployment's registry, preserving
all container references, incoming/current SHAs, recent images and four recorded
successful releases (current plus three rollback releases). Unknown/shared/unit
images, registry copies, volumes, backups and research files are outside that
authority. History is written atomically only after smoke passes; until four
releases are recorded, all images are kept. Corrupt history/inventory or less
than 8 GiB available / more than 85% used on any relevant filesystem refuses
deployment before pull, migration or replacement. The existing CloudWatch disk
alarm remains enabled. Policy, dry-run, bootstrap and recovery are in the
[runbook](deploy/develop/README.md#disk-retention); executable ordering and
refusal proofs are in `test_develop_image_retention.py`.

**The product hostname is AIA, client-first
([ADR 0015](docs/architecture/adr/0015-client-first-product-interface.md)).**
Caddy answers `/` itself with `302 /app/clients`. `/api/v1/*` goes to the API;
AIA's own pages (`/login`, `/logout`, `/auth/*`, `/config`, `/version`,
`/studies*`, `/_next/*`, the fonts and identity under `/skin/` and the icon set)
to the web client. `/app` and `/app/*` -- Clients → client workspace → study → stages -- go
through `forward_auth` to AIA's own gate, `GET /api/v1/session/gate` (ADR 0018): any
active member of the organization with an AIA session (`aia_session`, opened by
`POST /api/v1/session` and admitted by `ScopeResolver.authorize_session`), GET and
HEAD only, then the web client. No legacy setting touches it; what a page shows is
authorized per call by the API. The 18.6.6 interface is not served
(ADR 0018 decision 4): no page hands off to it, `/classic` is the web client's page
saying so, and what AIA does not have yet says so where a person meets it. Nothing
of the vendored unit is served or run by the product deployment (ADR 0018 decision
5): no unit image, service, volume mount, hostname, credential, data sync or health
check. Every other path is the web client's, with its own 404, the unit's old paths
(`/api/*` outside `/api/v1`, `/files/*`, `/artifacts/*`, `/project-attachments/*`,
`/brand/*`, `/fullsim-arena`, `/health`, `/status`) among them; the panel's gate that
guarded them (ADR 0012) is gone, `/api/v1/panel/*` with it. `tools/caddy_routes.py`
holds the adapted Caddyfile to this paragraph in CI (one hostname; no upstream but
the API and the web client); `tools/develop_routing_proof.py` runs it, and the smoke
check fails a deploy on which a unit path answers or a `legacy-panel` container of
the product's Compose project exists.

**The 18.6.6 unit is a reference beside the product** (ADR 0018 decision 5).
`deploy/reference/` runs it as the Compose project `aia-reference`, on the unit's
working volume declared `external` (never created or removed there), behind a
basic-auth gate published only on the host's loopback, started and stopped by
hand; `.github/workflows/reference-unit.yml` (dispatched by hand) builds its image
and ships its bundle, and changes nothing on the host. The two stacks share no
network, file or Compose project, and the product starts, deploys and passes its
smoke checks whether the reference is up, down or absent. The first product deploy
after the change stops the unit's old container and fails if its volume vanished,
because until the migration's report is accepted that volume holds the only copy of
the content of Studies still waiting for it (OI-58).

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
- **No invented fieldwork.** Without the AI runtime, or when its gates refuse the
  material, a research run waits at fieldwork and says so; fictional respondents
  -- invented by code, or answered by a model as invented people -- are labelled
  on every view and never become a finding. A model never answers a fact the
  respondent already has, and never an individual fact it does not.
- **No visualisation mutating research truth.** A dragged node saves a view
  override; results stay immutable.
- **Fail closed.** When a methodology precondition is unmet, the system blocks.
  It does not degrade.
