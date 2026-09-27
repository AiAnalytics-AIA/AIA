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
    routers/                health, projects, scope, runs (runs + artifacts under a project),
                            workspace (clients, a client's workspace, its knowledge and proposals,
                            a study's frame and its unit-project binding, ADR 0015),
                            panel (the session + gate in front of /app, /classic and the unit, ADR 0012),
                            research (a study's Design Revisions, readiness, runs, their steps and
                            artifacts (ADR 0016), and native agent-jobs beneath each Study,
                            settings (the read-only settings document: every control and how it is set)
    schemas/                Request/response models + the one error contract
  web/                      Next.js 16 / React 19 / Tailwind 4. /login + /logout, the live /studies
                            pages, and /app: AIA, client-first (ADR 0015); no mock data.
    src/app/app/            AIA behind the gate, AIA_INTERFACE_REHOME_ENABLED: /app/clients (home),
                            clients/<client>/{research,simulations,knowledge,data},
                            clients/<client>/research/<study>/<stage>, intelligence, memory,
                            settings (+ settings/classic-projects, the unit's store, OI-58)
    src/components/aia/     The client-first shell: AppShell (four global items, breadcrumbs, one
                            action, tabs), the client workspace and its areas, ResearchStudy
                            (a study's frame from its AIA binding), useResource (404 = nothing here),
                            settings/ControlPanel (every control from GET /settings, how each is set;
                            live forms over the admin routes with the signed-in token, lib/api.ts `admin`),
                            FrontDoor (the branded frame of /login, /logout, /auth/callback)
    src/components/brand/   Wordmark and LatticeField: the identity inline, in currentColor + --signal
    src/components/rehome/  Primitives (token utilities only), the research stages and the classic
                            projects screens, re-homed under the shell above
    src/unit/               The ONLY way it reaches the unit: routes named by ledger row, parsers,
                            and each area's logic ported from the JS (parity-tested under Node)
      research/             The research flow's model, project store (1.8 s save, visible state),
                            AI jobs (POST -> job_id, read /api/job) and the ten steps
      testing/legacy.ts     Parity harness: a function's effective binding, run in a Node vm
    src/lib/app-routes.ts   Every /app URL, built in one place (stage slugs: `persona` is `dimensions`)
    src/components/rehome/research/  The stage frame (StudyFrame: client, study, binding): rail,
                            save state, job panel, the shared brief analysis (useAnalysis), one
                            screen per stage; ExecutionSteps.tsx: Run, Progress, Results (ADR 0016)
    src/lib/research-agent-jobs.ts  Native Study jobs: enqueue/follow; proposal review and reload
                            live in useResearchAgents.tsx. No classic provider probe.
    src/lib/research-execution.ts  How a run's state and results read: suppression hides numbers,
                            fictional data is labelled every time, the park is explained
    src/design/tokens.json  The design system's ONE source: colour, type, spacing, radius, motion
    scripts/build-tokens.mjs  tokens.json -> tokens.css, tokens-theme.css, fonts.css, tokens.ts,
                              and aia_core domain/report/print_tokens.py (the report's print register)
    scripts/check-design.mjs  Contrast, chart-palette and client-accent evidence, re-measured
    public/skin/            Self-hosted fonts (OFL), identity and skin.css, served at /skin/ (ADR 0013);
                            handoff.js: /app's links into /classic (#aia:open=…, ADR 0014) and the
                            classic page's "Zpět do AIA" bar (sessionStorage aia:return, /app only)
    src/skin/               The 18.6.6 skin's sources: legacy-variables.json (each 18.6.6 variable ->
                            a token, with why) and components.css (token-only rules, linted)
    scripts/build-skin.mjs  -> public/skin/skin.css; refuses raw colour/radius/shadow/font values
    src/lib/interface-skin.ts  The skin decision: pinned SHA256 -> two tags, else byte-for-byte
    src/app/interface-document/  The document Caddy serves at /classic: fetch the unit, apply the skin
  worker/src/aia_worker/    The execution loop. Claims, heartbeats, records. Does no work itself.
    executor.py             StepExecutor / StepContext protocols, outcomes -- the seam
    worker.py               The loop: claim, execute, record; reconcile on an interval.
                            Refuses a one-connection engine (in-memory SQLite)
    context.py              Checkpoints, per-call metering, lease-fenced transactions
    heartbeat.py            Lease extension + cancellation carried back, one thread per attempt
    settings.py             Typed, validated settings from the environment
    registry.py             Loads executors from AIA_WORKER_EXECUTORS=module:factory
    testing.py              Scripted executor for the tests (and the multi-process suite)
  executors/src/aia_executors/  Step implementations the worker runs, registered by kind
    snapshot.py             develop_snapshot: a project revision as a JSON artifact (S3)
    registry.py             The composition root AIA_WORKER_EXECUTORS names; store + build
    research.py             The research steps: compile, preflight, fieldwork (parks without a
                            source), aggregate, sociomap; every artifact on the owned design project
    research_agents.py     Native proposal executor: frozen design/context, StepModelCaller,
                            provenance artifact; no automatic write or retry
    ai_fieldwork.py         The ai_runtime source: fictional roster, class + lineage, gateway preflight
                            (a refusal parks), one request per respondent block, answers drawn by code
    ai_step.py              StepContext -> ExecutionContext: StepModelCaller (one reservation per
                            request, settled once) + StepCallJournal (fenced dispatch, unfenced ledger)
    ai_runtime.py           AIA_AI_* / AIA_BEDROCK_* settings (off by default, fail closed when on) and
                            the one gateway over ADR 0010's route; the only builder of the adapter
    workbench.py            The ONLY composition with fictional fieldwork; refuses unless AIA_ENV is
                            local/test, and no deployment may name it (layer_check)
    deep_research/          The six Deep Research steps (not registered): plan, investigate, merge,
                            verify, synthesize, publish; StepToolMeter (every tool call journaled,
                            fenced, before it leaves); deep_research_registry(runtime=None) parks
    deep_research_runtime.py  AIA_DEEP_RESEARCH_ENABLED: needs research agents; no web retrieval
                            exists, so web tracks are blocked and nothing is sent
    deep_research_recorded.py  The ONLY composition with recorded web retrieval; refuses unless
                            AIA_ENV is local/test, and no deployment may name it (layer_check)
    seed.py, smoke.py       Operator commands: idempotent develop seed; deployment proof

packages/aia_core/src/aia_core/
  domain/                   Pure. No I/O. stdlib + Pydantic only.
    ai_models.py            ModelCapability, catalog, ModelPolicy, ModelRegistry (fails closed)
    ai_contracts.py         ModelRequest/Result, AIUsageEvent, 10-way error taxonomy,
                            structured-output validation, AgentDefinition, FallbackPolicy
    ai_execution.py         ModelGateway + ExecutionContext: the step-executor contract
    ai_tools.py             ToolRegistry — scope never from model arguments
    research_agents.py     Eight closed Research task contracts, prompt/harness versions,
                            bounded context and task-owned proposal mapping
    deep_research/          Deep Research (ADR 0017), pure; recorded/offline, nothing registered:
      contracts.py          subjects, tracks, snapshots, knowledge sources, evidence, quarantine and
                            stop reasons, the request a run is frozen to
      workflow.py           the deep_research graph: plan → investigate → merge → verify →
                            synthesize → publish (defined here; registration is the integrator's)
      tooling.py            the tool-cost contract: ToolRoute, reserve → dispatching → outcome
      legacy.py             18.6.6 research_context leakage screen + merge, EXACT (unit captures)
      grounding.py          a quote must be in a source the same track retrieved; numbers too
      sources.py            source class + score from declared tables; unknown scores lowest
      classification.py     a query's class: inherited from its context, never lowered by keywords
      web.py                what a fetch may reach: public http(s), every hop, every address
      knowledge_access.py   Client Knowledge frozen at enqueue, classed by kind, retrieved by code
      planning.py           subjects → tracks → fingerprints; presets (DR-5, proposed); stop rule
      agents.py             five agents: closed contracts, prompts from the enums, no tools
      merge.py              declared scores, dedupe, confirmation bonus, the verifier's verdicts
      synthesis.py          the brief: cite accepted evidence, write only its quotes' numbers
      bundle.py, quarantine.py  the sealed bundle; respondent context (re-screened against the
                            final questionnaire), design input, analysis context
      steps.py              what each step stores; reusable (by content) vs this run's own;
                            tally: what a run bought, a reused unit costing nothing
    ai_respondent.py        The AI respondent: agent aia.research.respondent, prompt v1, per-block strict
                            contract, fictional roster, facts by code, interpretation, the dataset
    respondent_behavior.py  18.6.6 behavior.py + styly.py: response process, styles, the seeded draw
    respondent_facts.py     18.6.6 factual_layer.py: facts answered by code, unsupported facts refused
    licence.py              Licence eligibility beside residency: DataLineage (no default),
                            LicencePolicy.authorise, LicenceDenied (ADR 0016 decision 5)
    licence_determinations.py  The determinations as data: panel sources UNDETERMINED (OI-61)
    design.py               A Study's Design Revision: immutable content, provenance, the owner tag
    research_design.py      A revision -> ResearchSpecification (compile) + AIA's readiness rules
    fieldwork.py            FieldworkSource, FieldworkDataset, validate_dataset; data_origin
    synthetic_fieldwork.py  Fictional respondents from random.Random(seed), workbench and tests only
    research_aggregate.py   agreguj_otazku's reportable core + uncertainty.py, ported from the unit
                            (EXACT; bootstrap bounds from AIA's generator, OI-62, parity D5)
    research_sociomap.py    The unit's relation matrix -> compute_sociomap; INTERNAL_ONLY while D6
                            is open; require_client_facing refuses it
    research.py             A run's phase in words (queued … cancelled), from the engine's state
    pipeline.py             Stage order, fingerprints, impact/invalidation rule
    population/             Dataset versions, STATIC/LIVE, lineage, promotion, import
                            contract + validation, weights, bindings, RuntimePopulation
      czech.py              The Czech v17 import contract (pinned by hash, not copied)
      policy.py             Field policy as code: what each field may be used for
      companions.py         Companion assets + the fail-closed joint certificate gate
      authority.py          Population-operator capability (establish / promote)
    project.py              Project, revisions, stage state
    providers.py            Provider policy, model roles, budget and error semantics
    residency.py            EU residency, data classes, the fail-closed egress boundary
    scope.py                Organization/Client/Study vocabulary, roles, permissions; StudyKind
                            (RESEARCH / SIMULATION); ClientContext + ClientPermission
    workspace.py            StudyWorkspace: a study's AIA-owned binding to its unit project (OI-58)
    knowledge.py            Client Knowledge: layers, kinds, proposals, revisions (ADR 0015)
    workflow.py             Workflow DAG, job states, retry classification
    workflow_templates.py   The closed set of workflow types and their step graphs
    sociomap/               Sociomapping maths, pure Python: compute_sociomap -> artifact
      specification.py      SociomapSpec v2 (no defaults) + require_supported
      relations.py          scale coercion, mutual projection, ipsatization   F1-F3
      layout.py             declared layout registry; aia_rowcond_unfolding_v1
      metrics.py            object metrics, T-score, normaliser               F5-F6
      terrain.py            respondent density / object weighted mean         F7-F8
      engine.py, models.py  the pipeline and the v2 artifact
      view.py               drag overrides, view terrain, scenarios (never write) F9
    report/                 The report as data: document model, components, templates (DOCX output)
      print_tokens.py       GENERATED from tokens.json: print colours, type scale in pt, page
      model.py              The document: metadata, sections, every block — numbers only as refs
      evidence.py           EvidenceLedger (built from AdmittedClaims only) and print grades
      validation.py         Every rule a report must keep before it renders; fails closed
      numbers.py            Czech print formatting; never re-rounds; effective n rounds down
      copy.py               The report's own Czech vocabulary
      outline.py            Every printed number: chapters, appendices, headings, figures, cross-ref labels
      rendering.py          ReportRenderer protocol: the seam to the DOCX adapter
      templates.py          client / final / internal / documentation recipes; the client report
                            keeps the legacy client_report_v2 section order
    evidence/               What may be claimed — every gate fails closed
      field_policy.py       400-field dictionary as typed policy; FieldPolicyBook
      joint_status.py       CORE_JOINT_STATUS certificate, hash-bound; joint units
      claims.py             Permissible-claim policy: measured vs modelled, disclosures
      support.py            Kish effective n, SUPPRESS by default, intervals required
      metrics.py            The allowed analysis metrics, one unit each
      validation.py         Validation bound to system fingerprint; tier gate
      factual.py            Factual layer: panel facts are read, never invented
      admission.py          AdmittedClaim — the ONLY way a number enters a result
      instrument.py         A Study's own questionnaire items as evidence fields: declared
                            from the run's record, modelled, aggregate only, INTERNAL_ONLY
    analysis/               The eight analysis modules, drafts, prompts, results
      native.py             A native run's specification + aggregate -> evidence table,
                            instrument policy, MISSING certificate; research questions; preflight
      harness.py            One module turn = one governed request: agent aia.analysis.module,
                            no gateway schema repair (<= 3 calls a module), Class C/A, lineage
      artifact.py           The stored outcome (aia-analysis-module-artifact-1), turn
                            checkpoints, reuse keys; no claim is ever stored
      steps.py              The eight analysis nodes as data, for the research template
    simulation/             Deterministic simulation core from a frozen WorldModel:
                            reference constants, reject-not-clip validation,
                            inoculation, scenarios, variants, frozen results
  application/
    model_gateway.py        GovernedModelGateway — the ONLY model call path (ADR 0005)
    scope.py                ScopeResolver — the ONLY issuer of a scope context,
                            including a worker's, issued only against a held lease,
                            and of a ClientContext (client_context, accessible_clients)
    population.py           PopulationRuntime — the ONLY loader of population data
    population_authority.py PopulationAuthority — the ONLY issuer of an operator context
    analysis.py             Runs one module: draft → gate → repair ≤2 → COMPLETED/BLOCKED
    analysis_results.py     A native run's analysis: its sources in scope, one module prepared,
                            outcomes reconstructed by re-admission (the reader Job 4 uses)
    workflows.py            start_workflow: a run from a template, idempotent per revision
    research.py             ResearchRuns: start/list/get/cancel/retry over a Design Revision,
                            found only through the Study; research_artifacts, the ONLY reader
    deep_research.py        DeepResearchRuns: the request frozen at enqueue (knowledge via
                            for_study, client terms), start/get/runs/events/cancel/retry; the
                            bundle (seal verified) and its snapshots only through the run
    web_retrieval.py        RetrievalGate: the ONLY way a query or URL leaves -- classify, egress,
                            metering, reserve, journal the dispatch, call, journal the outcome
    develop_seed.py         The synthetic develop world, through the same paths the API uses
  infrastructure/
    report_docx/            The report as DOCX (python-docx; the `report` extra, imported lazily)
      embed.py              ECMA-376 obfuscated font embedding; deterministic keys
      styles.py             The Word style sheet, built from print_tokens (S = every style name)
      renderer.py           DocxRenderer.render(doc) -> bytes: validate, outline, write, finish;
                            deterministic bytes (fixed zip timestamps)
      layout.py             Sections (cover / front i, ii / body 1, 2 / appendix), running heads,
                            the draft footer, cover, document control, TOC fields
      blocks.py             One renderer per model block; no direct formatting
      tables.py             The data table: SEQ caption with base n, repeating header, suppressed
                            rows removed and counted, landscape sections
      charts.py, figures.py Charts from the ledger with the viz tokens (7 kinds, hatched modelled
                            series, direct labels); figures; the Sociomap gate (require_client_facing)
      dispatch.py           Which renderer draws which block
      marks.py, images.py   Evidence marks (one glyph per grade; unknown prints "?"), SVG + PNG
                            fallback images with alt text (asvg:svgBlip)
      plotting.py           Matplotlib for the report: vendored fonts, tokens, deterministic SVG/PNG
      context.py            RenderContext: the state of one render
      lint.py               lint_docx: no direct formatting, schema order kept
      ooxml.py, numbering.py, footnotes.py  Fields and bookmarks; lists; the footnotes part
      fonts/                Upstream TTFs, unmodified, with licences + SHA256SUMS
    tables.py               SQLAlchemy tables
    db.py                   Engine and session factory
    repositories.py         ProjectRepository (owner= in its isolation predicate)
    scope_repository.py     Organizations, clients, studies, grants; studies in a client, by kind
    study_design_repository.py  A Study's design project (owned: projects.owner) and its
                            Design Revisions; the ONLY writer of a Study's design (ADR 0016)
    study_workspace_repository.py  The study <-> unit project binding: bound once, under
                            EDIT_STUDY, never looked up by unit id (OI-58)
    client_knowledge_repository.py  The ONLY reader/writer of Client Knowledge: read inside a
                            resolved scope, changed only by an approved proposal (new revision)
    artifact_repository.py  Artifact rows, provenance, dependency edges, reuse
    workflow_repository.py  Durable jobs, lease-fenced writes, cost reservations,
                            the population binding each run records; WorkQueue --
                            the only cross-study surface (claim, recover, resume, refuse)
    population_repository.py  Population registry: versions, populations, history
    population_parser.py    Text-preserving panel + dictionary parser (stdlib)
    population_source.py    PopulationAssetSource: filesystem / memory (EU store later)
    ai_usage_repository.py  Append-only AI usage ledger; uncertain-call resolution
    ai_call_journal.py      CallJournal over the workflow attempt + ledger
    model_adapters/         Anthropic / OpenAI / Claude Code / Bedrock adapters, transports, recorded
                            doubles; live_transport.py (urllib3, no retries), aws_signing.py (SigV4,
                            instance or container role only)
    storage.py              ArtifactStore: S3 / filesystem / memory
    storage_settings.py     AIA_STORAGE_*: one typed definition for every composition root
    web_retrieval.py        WebFetcher (every hop and address checked, caps, HTML to a content-
                            addressed snapshot); search/fetch protocols; recorded doubles (they say
                            RECORDED and nothing else); no live adapter exists (DR-2)
    build_identity.py       AIA_BUILD_SHA: the commit a process runs; null, never a guess

migrations/                 Alembic
deploy/docker/              python.Dockerfile (api + worker targets); apps/web/Dockerfile is the client
deploy/develop/             The develop host: Compose, Caddyfile, deploy/backup/restore/smoke, runbook
  bin/backup-legacy-state.py Live SQLite database copies for pre-deploy/nightly backup (WAL-safe)
infra/develop/              Terraform for the develop AWS resources (one root, no modules)
docs/architecture/          System design + 16 ADRs; ai-step-executor-contract.md
docs/design/                Brand and UI direction; the design-system brief
design-system/              The AIA Design System artifact as a static reference package for design tools:
                            tokens (CSS + flat JSON), fonts, identity SVGs, status-map.md (from the domain
                            enums), three no-build HTML pages, the artifact verbatim. Not imported by apps/web,
                            whose token source stays apps/web/src/design/tokens.json
docs/migration/             Plan, status, legacy map, MVP acceptance test
  parity-matrix.json        THE parity tracker: 78 capabilities, gates, blockers
  legacy-route-ledger.json  The strangler's route ledger: 153 legacy routes, LEGACY/PORTING/PORTED/RETIRED
  interface-screens.json    Every classic screen (router routes + DEMO views) and its React rebuild state (ADR 0014)
  legacy-ui-functions.json  The 88 research functions of ui_app.html (+ recorded additions), hash-pinned
docs/product/               Authoritative product scope
docs/archive/original-mvp/  Superseded. NOT requirements.
tools/layer_check.sh        Layering enforcement
tools/exposure_check.sh     Reference-exposure enforcement (private-repo hygiene)
tools/sociomap_golden.py    Regenerates the Sociomap engine's own golden fixture
tools/report_preview.py     A report as a reader sees it: DOCX -> PDF -> PNG via LibreOffice,
                            lint, greyscale, +35 % Czech stress (manual)
tools/parity_status.py      Parity verdict per capability, from JUnit XML
tools/legacy_oracle.py      Reach the running 18.6.6 unit: probe / record / compare (stdlib)
tools/aggregate_capture.py  Research fixtures from the unit's own functions: `cases`, `capture` (in
                            the unit's venv), `self` (AIA's pinned bounds)
tools/respondent_capture.py  Respondent behaviour fixtures from the unit's own behavior.py / styly.py
                            (`capture`, in an environment with NumPy, pandas and SciPy)
tools/deep_research_capture.py  Leakage-screen and merge fixtures from the unit's own
                            research_context.py (`capture`, `verify`; stdlib only)
tools/bootstrap_seed_sensitivity.py  The unit's bootstrap spread over seeds: the evidence for OI-62
tools/ui_functions.py       Extract ui_app.html's 737 functions verbatim; `effective` prints the binding
                            that runs (the last declaration or reassignment); check the UI ledger
tools/ui_function_runner.mjs, ui_function_capture.py
                            Run extracted functions under Node; capture U<nn> fixtures
tools/caddy_routes.py       CI's check of the adapted develop Caddyfile: / -> /app/clients, /classic and
                            /app gated, the unit only on its own paths, the oracle hostname
tools/develop_routing_proof.py, develop_routing_journey.mjs
                            Run the real Caddyfile locally in front of stand-ins; then a browser
tools/ui_workbench/         AIA and the classic interface on this machine, for UI work: the unit on a
                            scratch copy with a fictional panel, the real API on SQLite with local
                            identity and the develop seed, `next dev`, the skin rebuilt on save, a
                            facade routed by the Caddyfile. Never parity. capture.mjs screenshots every
                            screen; fixture_project.py: fictional research projects bound to studies;
                            a worker with fictional fieldwork; research_journey.mjs: Run -> Results
.planning/                  Progress, plans, open items
src/server.js               Legacy Fastify login stub. Frozen. No new features.
legacy/npc-panel-18.6.6/    The NPC Panel 18.6.6 product, extracted from the audited archive
                            by AIA-reference/tools/extract_legacy.py. Frozen: regenerated,
                            never edited. The baseline and parity oracle (ADR 0011).
```

**Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic,
PostgreSQL 16, Next.js 16, TypeScript, Tailwind 4.
**Target:** AWS. The `develop` environment is one EC2 host under Docker Compose
with S3, Cognito, ECR, SSM and Bedrock used for real
([ADR 0009](docs/architecture/adr/0009-single-host-develop-environment.md));
production compute is undecided (ECS Fargate expected, with RDS). Terraform,
GitHub Actions with OIDC. No Kubernetes, no Redis, no SQS
([ADR 0002](docs/architecture/adr/0002-postgresql-authoritative-store.md)).

**Model calls.** Nothing calls a provider except through
`GovernedModelGateway.invoke`; `make layer_check` forbids a provider SDK or gateway
library anywhere in the core or API. Domain code names a `ModelCapability` and a
`DataClass`, never a model.

**Routes.** Every project route is study-scoped:
`/api/v1/studies/{study_id}/projects/…`. A project route outside a study prefix
fails the build — that would mean scope had stopped being carried in the path.

**The legacy prototype's archive is not in this repository.** The raw tree
lives at `../npc-panel-reference`, reached through `AIA_LEGACY_REFERENCE`, and is
used by the parity suites. What *is* here, since ADR 0011, is the extracted
**product unit** at `legacy/npc-panel-18.6.6/`: the 924 code and configuration
files of 18.6.6, byte-identical to the archive, with their licence-bound data
kept in EU object storage and hydrated at container start. It is frozen and
regenerated by `AIA-reference/tools/extract_legacy.py`; never edit a file under
`legacy/npc-panel-18.6.6/app/` by hand. It runs as the `legacy-panel` service
on the develop host and is the behavioural baseline every port is checked
against.

**The develop site is AIA, client-first** (ADR 0015). `/` answers 302
`/app/clients`; the hierarchy is Clients → client workspace (Přehled, Výzkumy,
Simulace, Znalosti, Data) → study → stages, and the global navigation has four
items: Klienti, Společenská inteligence, Projektová paměť, Nastavení. Research
and simulation are both `Study` records, told apart by `Study.kind`. The 18.6.6
interface is a labelled, temporary hand-off at `/classic` with a way back, and
the oracle stays on its own basic-auth hostname. `/app`, `/classic` and the
unit's own paths sit behind `forward_auth` to `GET /api/v1/panel/gate`; only
organization owners and admins pass -- **a temporary restriction, not the target
model** (OI-59: user → organization membership → client grant → study grant).
There is no catch-all to the unit. The classic document passes through the web
client, which adds the skin only when it is the pinned `ui_app.html` (ADR 0013);
the unit's bytes never change.

**The unit store is migration debt.** A research stage's working content still
lives in the unit's project store, reached only through the study's AIA-owned
binding (`study_workspaces`, `StudyWorkspaceRepository`), resolved after AIA
authorization; a unit project id from the browser authorizes nothing, and
nothing finds a study by it. The removal condition is in OI-58.

**Client Knowledge is scoped before it is read.** `ClientKnowledgeRepository`
takes a `ClientContext` or `StudyContext` and queries by that client; there is
no global pool filtered afterwards. A study proposes, a person other than the
proposer approves (unless the client's self-approval policy allows it), and
approval writes a new revision with provenance; nothing
changes knowledge otherwise. `make layer_check` keeps the rows inside the
repository.

**A research run executes a Design Revision** (ADR 0016). The browser submits the
design it shows; the revision is immutable and belongs to the Study's owned design
project, which no generic project route can see. Runs are found only through the
Study and their artifacts only through the run. Fieldwork for an `ai_runtime` run is
answered by AI respondents (`aia_executors.ai_fieldwork`) only when the worker's AI
runtime is configured and the gateway's gates pass; otherwise it **parks**
(`ai_runtime_unavailable`, the refusing gate named). Its personas are fictional and
its datasets say so (`SYNTHETIC_AI_FICTIONAL`); the fixture's invented respondents
exist only in `aia_executors.workbench` and tests (`SYNTHETIC_FIXTURE`). The model
returns one respondent's probabilities; code answers facts and draws the answer.
Panel-derived data reaches no model provider until OI-61 records a licence
determination -- a gate of its own beside residency. The Sociomap is computed but
`INTERNAL_ONLY` while D6 is open.

**The population is resolved once per run.** Research and simulation code gets
population data only from `PopulationRuntime.load_for_run`, which reads the
`PopulationBinding` the run recorded at creation. There is no other loader, no
default weight and no fallback version; `make layer_check` enforces the loader.
Before using a field, a consumer asks `RuntimePopulation.decide(field, use)` and,
before combining fields, `decide_joint(...)` — never the dictionary directly. The
contract is [docs/architecture/population.md](docs/architecture/population.md).

**Sociomapping golden fixtures are.** F1–F9 are synthetic inputs with the
reference's recorded outputs, vendored under
`packages/aia_core/tests/fixtures/sociomap/` and pinned by SHA256 in its
`index.json`. They run in every CI job. Never edit one to make a test pass.

**A Deep Research finding is a quote in a captured source, or it is nothing** (ADR 0017,
[deep-research.md](docs/architecture/deep-research.md)). Code picks the subjects and tracks,
sends every query and fetch, and grounds every quote in a content-addressed snapshot of the same
track; models only propose. A query's data class is inherited from what it was written from and
never lowered by keywords. The 18.6.6 leakage rule is kept exactly and bars a finding from
respondent context, which is re-screened against the final questionnaire. It runs through the
worker as six steps whose every unit is an artifact with a fingerprint, so a later pass buys only
what changed. It is recorded/offline: no live search, no route, nothing registered in production;
the production-shaped composition blocks every web track and sends nothing, and recorded web
retrieval exists only in `aia_executors.deep_research_recorded` (local and test).

**Evidence is a capability, like scope.** A number reaches an analysis result only
as an `AdmittedClaim`, minted only by `admit_numeric_claims` after field policy,
joint structure, support, interval and tier have all passed. Prompts state the
rules; they never enforce them.

**The unit is the oracle, and its functions are fixtures.** The strangler plan
([`.planning/plans/legacy-strangler.md`](.planning/plans/legacy-strangler.md))
replaces one capability at a time behind the running `legacy-panel`, reached only
through `tools/legacy_oracle.py` and `AIA_LEGACY_REFERENCE_URL`. The 88 research
functions of `ui_app.html` are ported *from the JavaScript*: a fixture is captured
first by running the extracted function under Node
(`packages/aia_core/tests/fixtures/legacy_ui/`, `U<nn>_<function>`), pinned to the
function's source hash, and the port is compared with it. The two ledgers in
`docs/migration/legacy-route-ledger.json` and `legacy-ui-functions.json` are the
state; the plan is the order.

**The golden fixtures need no archive.** F1–F9 are vendored, byte for byte,
under `packages/aia_core/tests/fixtures/sociomap/`; F10–F11 are read from a
checkout of the private `AiAnalytics-AIA/AIA-reference` at `../aia-reference` or
`AIA_REFERENCE_REPO`. Every fixture is pinned by SHA256 in
`docs/migration/parity-matrix.json`. When a capability lands, its fixture gate
lands with it — `test_parity_matrix.py` fails an `IMPLEMENTED` capability with an
ungated fixture.

## 3. Commands

| Purpose | Command |
|---|---|
| One-time setup | `make setup` |
| Start Postgres / MinIO | `make services` |
| Migrate | `make migrate` |
| New migration | `make migration m="add jobs"` |
| Run everything | `make dev` |
| Run one worker | `make dev-worker` (needs `DATABASE_URL`; the real executors, over `AIA_STORAGE_*`) |
| Seed the synthetic develop world | `make seed-develop` (needs `DATABASE_URL`, `AIA_SEED_OWNER_EMAIL`; idempotent) |
| Tests | `make test` (core + API + worker + executors) |
| Worker tests | `make test-worker` (the multi-process suite needs a PostgreSQL `DATABASE_URL`) |
| Executor tests | `make test-executors` (the snapshot step under the real worker loop; seed; smoke module) |
| Deploy `develop` | Merge to `develop`; [`deploy/develop/README.md`](deploy/develop/README.md) is the runbook. Live at <https://aia-develop.art-chain.io/> |
| Parity vs prototype | `make test-parity` (needs `AIA_LEGACY_REFERENCE`; population parity needs `AIA_REFERENCE_REPO`) |
| Golden-fixture pins and F10/F11 | `make test-golden` (needs the reference repository) |
| **Parity vs the running unit** | `make test-oracle` (needs `AIA_LEGACY_REFERENCE_URL` + `_USER` / `_PASSWORD`; skips cleanly without) |
| Capture UI function fixtures | `python tools/ui_function_capture.py capture` (needs Node); `verify` re-runs and compares |
| **Report preview** | `make report-preview` — the four sample reports as pages, in colour, greyscale and +35 % stress (needs `libreoffice-writer`, `poppler-utils`) |
| **Parity verdicts** | `make parity-status` — `PASS` / `FAIL` / `NOT_EXECUTED` / `NOT_RUNNABLE` per capability |
| Lint | `make lint` |
| Format | `make format` |
| Types | `make typecheck` (mypy `--strict` + `tsc --noEmit`) |
| Web tests | `make test-web` (Vitest, pure functions) |
| **Design tokens** | `make web_design` — generated files match `tokens.json`; contrast, palette and accent evidence holds. Change a token: edit `tokens.json`, `npm run tokens`, `npm run skin` |
| **UI workbench** | `make ui-workbench` → <http://127.0.0.1:8780/workbench/sign-in> (AIA), `/classic` skinned, `:8767` bare; `make ui-workbench-status`, `make ui-workbench-down`. First run installs the unit's requirements into `tmp/ui-workbench/venv`; the API runs on the repo's env (`make setup`) |
| **Develop routing, run** | `sudo python3 tools/develop_routing_proof.py --keep`, then `node tools/develop_routing_journey.mjs` (disposable machine: Caddy on 80/443, `/etc/hosts` names; see the script) |
| Workbench research fixtures | `make ui-fixtures` (workbench running): fictional projects, prints their `/app` links |
| **A research run, end to end** | `make ui-research` (workbench + fixtures): Run → Progress → Results in a browser, on fictional fieldwork |
| Research fixtures from the unit | `python tools/aggregate_capture.py cases` / `self` (repo env), `capture` (the unit's venv) |
| Deep Research leakage fixtures | `python tools/deep_research_capture.py capture` / `verify` (repo env: the unit module needs only the stdlib) |
| **Deep Research, end to end (recorded)** | `pytest apps/executors/tests/test_deep_research_journey.py` — the real worker, gateway and gate over recorded exchanges: two passes, measured counts, every failure mode; nothing leaves the process |
| **See every screen** | `make ui-capture` (workbench running; needs Playwright + Chromium): every AIA screen, every router route and DEMO view, bare and skinned, 1440/1024 → `tmp/ui-workbench/shots/<time>/index.html` + `report.json` (errors, overflow, off-palette colours) |
| **The 18.6.6 skin** | Edit `apps/web/src/skin/*`, then `npm run skin` (in `apps/web`); `npm run skin:check` is the drift check |
| **Layering** | `make layer_check` |
| **Reference exposure** | `make exposure_check` |
| Everything CI runs | `make check` |
| **The pre-commit sequence** | `make verify` |
| OpenAPI document | `make openapi` |

There is no compile step in Python. `make typecheck` is this project's
warnings-are-errors gate: `mypy --strict` with `warn_unreachable`, plus
`tsc --noEmit` for the client. mypy runs over all three Python source trees in
one invocation, because `aia_core` ships no `py.typed` (`AGENTS.md` § mypy).

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

**One standing exception:** an agent may commit and push its own
`.agent-status/<AGENT_ID>.md` to the `coordination/agent-status` branch whenever
it wants to record progress. That file must reflect real work done, materially
verified and measured, never intentions. Use a separate worktree, never this
checkout. Anything else, that branch's README included, still needs permission.

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
main                       release branch; receives release PRs from develop
  └── develop              integration branch; CI on every push; every green head is
       │                   deployed to https://aia-develop.art-chain.io/ (ADR 0009)
       ├── feature/<slug>  new capability
       ├── fix/<slug>      defect
       └── chore/<slug>    docs, plan archiving, dependency bumps, tooling
```

Work happens on a prefixed branch, opens a pull request into `develop`, and is
merged there; a release is a pull request from `develop` into `main`. **Never
commit directly to `main` or `develop`.** The recommended protection for both,
and who has to configure it, is in
[`infra/develop/README.md` § Human actions](infra/develop/README.md#human-actions).
OI-3 recorded the condition for a second branch: a deployed environment to
protect a release from. That condition is met by `develop`.

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
make web_design    # token drift + design evidence
make test-web
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

## Native Research agents (2026-09-27)

[research-agents.md](docs/architecture/research-agents.md) describes contracts,
context, acceptance and activation. Fieldwork activation does not activate design
jobs. The additional worker keys are `AIA_AI_RESEARCH_AGENTS_ENABLED`,
`AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS` and `AIA_AI_RESEARCH_RESERVATION_USD`; the
reservation covers primary plus one schema repair. Analysis/report execution and
owned web retrieval remain in the complete-workflow plan, not delivered by the
proposal executor. Do not describe model recollection as web research.
