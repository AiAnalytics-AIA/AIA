# CLAUDE.md — standing instructions for AIA

Read this file, then [ARCHITECTURE.md](ARCHITECTURE.md), then
[AGENTS.md](AGENTS.md), before writing any code. Then run
`python tools/progress.py`: every plan's status, from its own front-matter (§4).

These rules are not advisory. They apply to every session, every branch and
every agent working in this repository.

---

## 0. The contract

You are working in someone else's long-lived codebase. Two things are true and
they order everything below.

1. **The repository is the memory.** Nothing you learn survives this session
   unless it lands in code, a test, one of the three documents above, or your
   feature's plan file and PR description (§1, §4). A
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

**Keeping them in sync is mandatory — through a docs PR, never inside a feature
PR.** When you add, rename or remove anything they describe — a module, a table,
a route, a job, a config key, a command — the document must change. The feature
PR does not make that edit. It writes the change under **Doc follow-up** in its
PR description, as exact text or a description precise enough to apply without
the author, and a separate, small, docs-only PR applies the follow-ups of one or
more merged feature PRs. The reviewer reads the Doc follow-up alongside the code
diff. **Stale docs are worse than no docs, because they are believed**, so open
the docs PR soon after the merge; until it lands, the merged PR's Doc follow-up
is the record.

**Shared files no feature PR edits:** `CLAUDE.md`, `ARCHITECTURE.md`,
`AGENTS.md`, `.planning/overview.md`, `.planning/open-items.md`,
`.planning/plans/README.md`, and the indexes and status narratives
(`docs/architecture/README.md`, `docs/architecture/adr/README.md`,
`docs/migration/status.md`). Every open PR was editing them, so each merge
conflicted with every other open PR (the hand-resolved file in 24 of the last 60
merges was the retired `PROGRESS.md`, 21 `open-items.md`, 18 `CLAUDE.md`, 16
`ARCHITECTURE.md`). Files that code or a test is checked against are **not**
shared docs and still change with the code: `parity-matrix.json`, the route and
UI function ledgers, the design tokens, and every generated file — a test fails
otherwise.

When you solve a non-obvious framework problem — a race, a silent truncation, a
config that behaves differently under test — record it immediately, with the
wrong version and the right version side by side, in your plan file and under
Doc follow-up; the docs PR carries it into `AGENTS.md`. That file exists because
the same three-hour debugging session was happening twice.

## 2. The map

```
apps/
  api/src/aia_api/          FastAPI. Validates, delegates, serialises.
    config.py               Typed settings + production guards
    dependencies.py         Composition root: engine, sessions, identity, scope; AudiencePopulation,
                            the population the audience routes read (CZECH_AUDIENCE in every
                            deployment; only the workbench installs another on app.state)
    identity/               IdentityProvider protocol: cognito, testing, development
    observability.py        Structured logging, request correlation, secret redaction
    routers/                health, projects, scope, runs (runs + artifacts under a project),
                            workspace (clients, a client's workspace, its knowledge and proposals,
                            a study's frame and its working content in AIA, ADR 0015, ADR 0018;
                            GET /clients/{id}/memory/search: project memory, one client's studies;
                            POST /clients/{id}/memory/reuse: a new or empty study from a past design;
                            GET /clients/{id} carries the tabs' counts (archived studies out, the
                            knowledge counts null without VIEW_CLIENT_KNOWLEDGE) and the client's
                            effective self_approval_allowed / _source; each listed study its
                            knowledge counts (approved, proposed, rejected); the knowledge's
                            folders and labels (list, create, rename or recolour, delete), PUT
                            …/knowledge/placement, GET …/knowledge?folder=…|unfiled&label=…; the
                            overview's stale_items, unfiled_items and recent_changes; a SOURCE,
                            DOCUMENT or DATASET item names its client's source as
                            content.source_id (422 unknown_source for any other; a study's
                            proposal names none), and a proposal answers its source_id; GET/PUT
                            /clients/{id}/profile (the profile, its contacts, its history),
                            POST /clients/{id}/contacts, PUT/DELETE …/contacts/{contact_id}),
                            client_sources (a client's sources, lifecycle K2: POST/GET
                            /clients/{id}/sources -- 201 when new, 200 with created: false for the
                            same bytes again -- GET …/{source_id} with its reading (a dataset's
                            columns in reading.dataset), GET …/{source_id}/original, always an
                            application/octet-stream attachment; POST …/{source_id}/reading reads a
                            source again with its format's current reader, OI-110),
                            session (AIA's own session + the gate in front of /app: any active
                            member, ADR 0018), research (a study's Design Revisions, readiness, runs, their steps and
                            artifacts (ADR 0016), the budget lift for a step stopped at the study's cap,
                            POST …/runs/{id}/analysis/retry (a finished run's failed analysis modules
                            asked again over its own collected data) and GET …/analysis/retryable
                            (read from the outcomes as stored), each step's analysis_outcome,
                            readiness with the run's cost ceiling and the study's spend limit, and native
                            agent-jobs beneath each Study, with their event feed (…/agent-jobs/{id}/events?
                            since=; a step names the step_id its events carry); GET …/design/source: where a reused design
                            came from; a run's reports: GET …/report, …/report/download,
                            …/report/pdf/download, …/report/context/download (stored, names its
                            artifact), …/report/client/download (a modelled run's client report;
                            409 client_report_refused otherwise), POST …/report/approve (a stored
                            report of the run, once); GET …/research/sociomap-register),
                            deep research (a Study's Deep Research
                            runs; Interpretation Research's start, POST …/deep-research/runs/
                            interpretation, over a result of the Study's own run), scope
                            (PUT /studies/{id}/spend-confirm sets the limit; any member creates a
                            client, its status stays the Admin's),
                            settings (the read-only settings document: every control and how it is set;
                            the access group states membership_is_access and offers no grant;
                            ai_runtime, what powers AIA's model calls from code; ai_history, the
                            prototype's provider fields, readable and never offered),
                            methodology (the Metodika tab, ADR 0023: GET the catalogue, a module and
                            its versions, POST check and compare (any member); POST versions and PUT
                            activation (an organization OWNER or ADMIN)),
                            population (GET /population: the registry, read-only, any member;
                            status derived, never stored; GET /population/versions/{id}/
                            characteristics: a version's weights, blocks, fields and subpanels;
                            GET /population/audience-catalogue: LIVE's kept factor catalogue and the
                            18 subpanels as filters, reading no row; POST /population/audience-preview:
                            what filters select in LIVE and whether n can be drawn, counts only,
                            503 without AIA_POPULATION_ASSET_ROOT, the API's one population read;
                            an owned child listed and readable only within its organization, with its
                            materialized outcome: target beside achieved, target_met never presumed),
                            materialize (POST/GET /studies/{id}/population/materializations: a
                            client's dimension materialized from a study, refused by name (422), an
                            unresolvable LIVE 409; the study's runs and each child's outcome)
    schemas/                Request/response models + the one error contract
  web/                      Next.js 16 / React 19 / Tailwind 4. /login + /logout, the live /studies
                            pages, and /app: AIA, client-first (ADR 0015); no mock data. Nothing of
                            18.6.6: no hand-off, no skin, no call to the unit (ADR 0018)
    src/app/app/            AIA behind AIA's own gate (no switch): /app/clients (home),
                            clients/<client>/{research,simulations,knowledge,data,profile},
                            clients/<client>/research/<study>/<stage>, clients/<client>/memory/<study>
                            (a past research, read-only), intelligence, memory, settings
    src/app/classic/        The public page an old /classic link lands on: 18.6.6 is gone, the way in
    src/components/aia/     The client-first shell: AppShell (four global items, breadcrumbs, one
                            action, tabs; a `track` puts it in study mode: icon-only global
                            navigation, a one-row header, the title in the page), the client
                            workspace and its areas (clients/: StudyList, Výzkumy and Simulace as a
                            table with status filters and two orders; KnowledgeArea, the library:
                            views, folders, labels, kinds and the open item, opened on
                            ?view=review|unfiled|old and ?add=1, read with useSearchParams;
                            KnowledgeLibrary, its table, bulk bar and the open item with its
                            history; ClientOverview, Přehled opening on Čeká na vás; ProfileArea,
                            the details, contacts, brands and competitors as ENTITY knowledge, the
                            self-approval rule and the history; SourceFile: SourcePicker, one file
                            kept as the client's source with its reading in words, and
                            SourceCard, a named file, what was read and the original), ResearchStudy
                            (a study's frame; its content loaded by the study's id), useResource
                            (404 = nothing here),
                            settings/ControlPanel (eight task-based tabs, searchable reference/audit/studies,
                            optional technical details and protected policy drafts; settings-guide.ts
                            explains each setting and its scope; every control from GET /settings, how each is set;
                            live forms over the admin routes with the signed-in token, lib/api.ts `admin`;
                            the one AI section: ai_runtime beside /config's switches, never "connected"),
                            settings/MethodologyPanel (the Metodika tab: searchable modules and grouped steps, formulas
                            as MathML via Temml, every value with its origin), MethodologyVersions (in
                            force, stored versions and what each changes, activation with a reason,
                            history; for an administrator the editor: one section at a time with original values,
                            draft replacement guards, fresh check/compare results and optional expert formula
                            slot, the domain's check at the field) and MethodologyComparison (an edit
                            beside what is in force on fictional panels or support cells); lib/methodology-edit.ts is
                            the editor's pure part,
                            FrontDoor (the Graphite frame of /login, /logout, /auth/callback; the
                            identity's cyan, `brand-apex`, is the signal there)
    src/components/brand/   Wordmark and LatticeField: the identity inline, in currentColor + --signal;
                            ActivityOrb: the thinking-orbs package (MIT, plain canvas), shown only while
                            the API reports a step RUNNING, tinted --ai-ink when a model works on it and
                            --status-running when code does; aria-hidden beside the status it decorates.
                            64 px in a running step's panel and the job dialog, 32 px by default.
                            DotField: the front door's 144-dot field (lib/dot-field.ts, pure) on a
                            full-viewport canvas; on a sign-in the person started (lib/liftoff.ts)
                            25 primes fly into the mark at the launch film's frame-0 geometry
                            (lattice, checked by tools/film_frame0.py) and `aia:mark-formed` fires;
                            LaunchFilm then plays public/skin/brand/aia-liftoff.{webm,mp4}
                            full-screen on `brand-stage`, takes over on its first frame, and its
                            end is the way in
    src/components/rehome/  Primitives (token utilities only) and the research stages, re-homed
                            under the shell above
    src/research/           The research flow's logic ported from ui_app.html (parity-tested under
                            Node): model, the ten steps, the job panel's words, and the store that
                            loads and saves a study's working content in AIA (1.8 s save, visible
                            state, a stale save refused and said, ADR 0018); plan-edit.ts keeps direct human
                            proposal edits consistent in native research_plan and legacy analysis
    src/testing/legacy.ts   Parity harness: a function's effective binding, run in a Node vm (reads
                            the vendored ui_app.html: reference only, never product code)
    src/lib/app-routes.ts   Every /app URL, built in one place (stage slugs: `persona` is `dimensions`)
    src/lib/api.ts          The API client; a stored report's download (requestStored) reads
                            X-AIA-Artifact-Id / X-AIA-Review-State, so the report approved is the
                            one downloaded
    src/components/rehome/research/  The stage frame (StudyFrame: client, study, rights):
                            StageTrack (every stage with its state, Průběh a stage of its own),
                            Inspector (InspectorProvider / InspectorSlot: a stage's readiness beside
                            it, then AI pomoc, then "Do spuštění zbývá"), save state, job panel, the
                            shared brief analysis (useAnalysis), one screen per stage; ProposalReview
                            (a design proposal reviewed inline, its changes listed); CompleteReport
                            (the report card on Výsledky: a part claimed only when the run's steps
                            made it; the one place a run's report is downloaded -- internal or, for a
                            modelled run, client; DOCX or PDF -- and approved, the document approved
                            being the one downloaded); the internal report panel below shows its
                            provenance only; InterpretationResearch approves the report with
                            literature it downloaded; ProposalEditor and PlanStep edit the research narrative
                            and whole comparable measurements with live previews, preserving existing
                            questionnaires (PlanStep tests: direct proposal editing); ExecutionSteps.tsx: Run, Progress, Results (ADR 0016);
                            RunResults, one run's results from the StudyFrame alone (read-only when
                            canEdit is false). DesignSourceNote: on every stage of a reused study, its
                            source study and revision and the labels it carries.
                            ResultsWorkspace.tsx: accessible views of one frozen research run;
                            switching data, maps, analysis and report retains the camera/review choice,
                            changes no result and starts no additional run.
                            The audience step's factor editor, feasibility preview and built-in
                            subpanels come from AIA's population (the two /population audience
                            routes; without them the step says why); special panels, own audiences
                            and panel factors say "V AIA zatím není" where they are met.
                            The Run stage offers the study's client's materialized children
                            ("Populace běhu"; LIVE by default) and sends the one chosen
    src/lib/research-agent-jobs.ts  Native Study jobs: enqueue/follow; proposal review and reload
                            live in useResearchAgents.tsx. No classic provider probe.
    src/lib/research-execution.ts  How a run's state and results read: suppression hides numbers,
                            fictional data is labelled every time, the park is explained;
                            originKind / resultOriginKind: the API's three-way reading of an
                            origin (fictional, modelled, unknown -- never fieldwork), the one
                            every screen's label uses; needsRepair: an analysis step that
                            succeeded with its module stored BLOCKED ("Potřebuje opravu", never
                            "Hotovo"), which reportHolds names as holding the report
    src/lib/population.ts   How Společenská inteligence reads the population registry (summarize,
                            labelOf, shortSha); read-only. children / clientChildren / sharedVersions /
                            targetVerdict / outcomeValue: an organization's materialized children,
                            listed on their own with target beside achieved, unknown never met.
                            components/aia/PopulationCharacteristics.tsx:
                            a version's weights, blocks, the 18 subpanels and every field's uses
    src/lib/knowledge-library.ts  How the client's library reads its views: the year rule
                            (YEAR_MS, the API's STALE_AFTER), the 200-item cap (RESULT_CAP), selection; study-table.ts
                            the studies table's filters and orders
    src/lib/client-sources.ts  How a client's source reads on its knowledge: the kinds that take a
                            file (FILE_KINDS), sourceIdOf / withSource, the reading and its
                            locators in words (readingLine, locatorWords, reasonWords)
    src/lib/memory.ts       How project memory's search reads (sendable, ofKind, evidence);
                            runLabels (a past run's data, report, reach: unknown never good),
                            designSummary (what a past design says, as the search reads it),
                            sourceLabelWords. components/aia/MemorySearch.tsx: one client's search, on
                            Projektová paměť (a client chosen first) and on the client's Výzkumy;
                            components/aia/MemoryStudy.tsx: a past research read-only (revisions, the
                            chosen one's design, its runs with their labels, a run's results under a
                            frame that may not edit) and "Použít tento design"
    src/lib/activity-orb.ts  Which running step shows which orb, and whether it is AI (the steps
                            that hold a model caller): agent jobs, run steps, Deep Research steps; a
                            queued, waiting or finished step shows none
    src/lib/step-activity.ts  A run's events folded into words per step: only what an event says
                            (counts as reported, never a percentage; tokens a provider did not report
                            are unknown, never zero). components/rehome/research/useStepActivity.ts
                            reads the feed after its cursor every 1.5 s while a step runs, once more
                            when it stops; StepActivityPanel.tsx opens under a RUNNING step (64 px orb,
                            latest report, counts, elapsed, a polite live log) on Progress, the job
                            dialog, Deep Research and Interpretation Research
    src/lib/ai-runtime.ts   How Settings reads an AI activity: on in configuration, off and by which
                            switch, invalid (the worker will not start), unknown -- never verified
    src/lib/public-config.ts  Public config type, runtime switch vocabulary and class parser;
                            /config reads server values at request time, never credentials
    src/research/lane.ts    Each stage's state from the study's working content and runs (no new
                            rule: Kontrola's server readiness stays the authority); proposal-diff.ts:
                            a proposal's changes against the working content
    src/lib/object-map-view.ts  The contract-3 object map read from its artifact: mapApproval (a map's
                            approval in the Sociomap register, by the method its run recorded; an
                            unread register is internal); ten display terraces
                            on the absolute 0-1 scale, mapLinks (the one link rule), pairDetail (UNKNOWN
                            with an r apart from an undefined r), mapFrame, screen-space label placement
    src/lib/object-map-3d.ts  terraceLayers (terraces cut from the stored mesh at the band thresholds) and
                            the framed orthographic camera; presentation only, no kernel or relation maths
                            (object-map-boundary.test.ts). ObjectMapTerrain.tsx draws 3D; ObjectMapView.tsx
                            is the approved design's workspace: top view first, 3D unmounts, relief,
                            rotation and opening choreography as display state, an internal PNG snapshot
    src/design/tokens.json  The design system's ONE source: colour, type, spacing, radius, motion
    scripts/build-tokens.mjs  tokens.json -> tokens.css, tokens-theme.css, fonts.css, tokens.ts,
                              and aia_core domain/report/print_tokens.py (the report's print register)
    scripts/check-design.mjs  Contrast, chart-palette and client-accent evidence, re-measured; § 4 the
                              object map's viz-terrace-1..10 ramp (adjacent and CVD ΔE floors) and the
                              contrast of its stage, labels, links, pins and fit badges
    public/skin/            Self-hosted fonts (OFL) and the identity, served at /skin/ (the name is
                            historical: the 18.6.6 skin that shared the path is gone, ADR 0018)
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
    registry.py             The composition root AIA_WORKER_EXECUTORS names; store + build;
                            population_store: the one store the materialize step and the panel
                            loader share
    research.py             The research steps: compile, preflight, fieldwork (parks without a
                            source), aggregate, sociomap; every artifact on the owned design project;
                            the sociomap step computes the run's pinned methods (none: legacy;
                            sociomap_method_invalid for a pin that does not verify) and is reused
                            only under the same engine version and pins
    research_agents.py     Native proposal executor: frozen design/context, StepModelCaller,
                            provenance artifact; no automatic write or retry
    ai_fieldwork.py         The ai_runtime source: AI respondents, fictional or drawn from the run's
                            population as the run pinned (persona_source); class + lineage, gateway
                            preflight (a refusal parks), one request per respondent block, answers
                            drawn by code. population_loader: the run's recorded binding, v17 contract,
                            the ANALYSIS enricher, over the shared directory and, when configured,
                            the population store (a selected child; ai_runtime.panel_population_source);
                            a panel run on a worker without it parks
                            (panel_personas_unavailable); a sample or persona refusal fails by name;
                            answer_plans: the request, draw and ledger loop over given plans, which
                            produce and the validation's arms share; require_binding= fails a
                            different resolved binding before any request; Answered.details: each
                            draw's record
    analysis.py             research_analysis: one module per step over StepModelCaller; preflight
                            BLOCKED stored with 0 calls, turn checkpoints (a retry replays, never pays
                            twice), AnalysisConfig.from_settings; in the default registry: without
                            AIA_AI_ANALYSIS_ENABLED a module parks (analysis_unconfigured); the
                            model-backed module needs it and the AI runtime itself (AIA_AI_RUNTIME_ENABLED
                            and a valid provider configuration), else it parks too (registry.py).
                            Harness 2: a schema failure is stored per failed field, and the repair
                            turn shows the model its own refused answer (a truncated one: asked for
                            less); analysis_round: a person's retry is a new round, in every turn
                            key, and a model-BLOCKED outcome is not reused in a retry round
    report.py               research_report: the internal draft from the eight analysis modules and
                            the run's chapters (report_chapters: maps, question tables, design,
                            respondents); never approved here; with AIA_REPORT_PDF_ENABLED (off by
                            default, on for develop) its PDF rendering beside it (research_internal_pdf,
                            infrastructure/report_pdf.py; a failed conversion fails nothing)
    sociomapping_report.py  The experimental Sociomapping's internal DOCX draft; always registered.
                            AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED decides only whether a newly started
                            run includes its step; turning it off does not stop a run that already has it
    ai_step.py              StepContext -> ExecutionContext: StepModelCaller (one reservation per
                            request, settled once) + StepCallJournal (fenced dispatch, unfenced ledger)
    ai_runtime.py           AIA_AI_* / AIA_BEDROCK_* settings (off by default, fail closed when on) and
                            the one gateway over ADR 0010's route; the only builder of the adapter.
                            AIA_AI_STEP_EVENTS (off by default): a research agent's and an analysis
                            module's model requests write ai_request_sent / ai_request_answered to
                            the run's feed (StepModelCaller(announce=): counts, cost, latency, never
                            text; two writes per request, ~1.3 ms measured)
    workbench.py            The ONLY composition with fictional fieldwork; refuses unless AIA_ENV is
                            local/test, and no deployment may name it (layer_check)
    deep_research/          The six Deep Research steps (in the default registry; a run parks
                            without AIA_DEEP_RESEARCH_ENABLED): plan, investigate, merge, verify,
                            synthesize, publish; StepToolMeter (every tool call journaled, fenced,
                            before it leaves; a retry takes the journal over and never resends a
                            call left in flight; a priced call held against the study's budget and
                            settled once); deep_research_registry(runtime=None) parks.
                            investigate.py: a planned track's _PlannedLog stores every external
                            outcome (the search with its hits in order, each fetch, the round, the
                            answer) before the next call, so a released step continues and never
                            sends a call twice; a journaled call with no stored outcome is uncertain
      fan_out.py            AIA_DEEP_RESEARCH_FAN_OUT (off by default): every track that makes a call
                            in a step of its own, any worker (InvestigateTrackExecutor; its payload,
                            TrackStepPayload); the run's snapshot cache in the store
                            (StoredRunSnapshotCache); investigate joins them
    deep_research_runtime.py  AIA_DEEP_RESEARCH_ENABLED: needs research agents; the search route is
                            AIA_DEEP_RESEARCH_WEB_SEARCH = off | wikipedia | brave (unset: the old
                            AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED decides); off blocks every web track
                            and sends nothing. deep_research_live.py builds each: Czech and English Wikipedia
                            (fee-free, Class C only); brave (priced, NON_EU, Class C only) needs the
                            public fetch's contact, AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000,
                            …_PRICES_AS_OF and …_BRAVE_API_KEY (a reference, never kept or logged).
                            AIA_DEEP_RESEARCH_COMMON_CRAWL (off by default) composes the Athena URL
                            index (us-east-1, priced at its scan cutoff) and the archive beside a
                            search route; every AIA_DEEP_RESEARCH_COMMON_CRAWL_* key required,
                            …_CRAWLS the ladder's. The runtime's sign_off_routes() names the priced
                            live routes; they run only under a pin recording the sign-off (ADR 0022).
                            AIA_DEEP_RESEARCH_FAN_OUT (off by default) needs
                            AIA_DEEP_RESEARCH_MODEL_CONCURRENCY: no default, 1-256, model requests in
                            flight across every worker on the route
    deep_research_recorded.py  The ONLY composition with recorded web retrieval; refuses unless
                            AIA_ENV is local/test, and no deployment may name it (layer_check)
    materialize.py          population_materialize: a client's dimension made into its owned child
                            (PopulationRuntime.materialize_child); parks without a population store or
                            AIA_POPULATION_ASSET_ROOT (population_store_unconfigured)
    validation.py           holdout_sample (the confirmation's respondents, drawn once and recorded)
                            and holdout_arm (one model arm's replicate: the same sample drawn again,
                            the preregistered blocks with each block's exclusion, answered through
                            answer_plans with the preregistered model binding required, codes stored
                            beside their probabilities); both park without the AI runtime or the
                            panel path
    seed.py, smoke.py       Operator commands: idempotent develop seed; deployment proof
    legacy_workspace.py     Operator command: the one-off migration of Studies' content from a copy
                            of the 18.6.6 store (dry run unless --apply; ADR 0018 decision 2)
    population_ops.py       Operator command: status / import / attach / establish / promote over
                            PopulationRuntime, as a person AIA_POPULATION_OPERATORS names (user id
                            -> permissions; unset: nobody); bundles under AIA_POPULATION_ASSET_ROOT;
                            --all-companions reads each companion the contract declares by its id;
                            record-dictionary (acts as no one; run by the develop deploy) keeps a
                            version's verified dictionary with it; record-catalogue (the same) keeps
                            each population's current version's audience catalogue, which establish
                            and promote also keep for the version they move to

packages/aia_core/src/aia_core/
  domain/                   Pure. No I/O. stdlib + Pydantic only.
    ai_models.py            ModelCapability, catalog, ModelPolicy, ModelRegistry (fails closed)
    ai_contracts.py         ModelRequest/Result, AIUsageEvent, 10-way error taxonomy,
                            structured-output validation, AgentDefinition, FallbackPolicy
    ai_execution.py         ModelGateway + ExecutionContext: the step-executor contract
    ai_tools.py             ToolRegistry — scope never from model arguments
    research_agents.py     Eight closed Research task contracts, prompt/harness versions,
                            bounded context and task-owned proposal mapping
    deep_research/          Deep Research (ADR 0017, ADR 0021), pure; the engine is frozen after #166:
      contracts.py          subjects, tracks, snapshots, knowledge sources, evidence, quarantine and
                            stop reasons, the request a run is frozen to; harness 3: the request's
                            settings_method (the approved method digest) and method_identity() in
                            every cross-run reuse key
      settings.py           ADR 0022's catalogue, effective values, the run's pin (pin / read_pin,
                            verified by digest; no fallback); route_allowances / request_limits:
                            what the engine reads from it, never above the code's caps
      workflow.py           the deep_research graph: plan → investigate → merge → verify →
                            synthesize → publish (built from here by the service, not a template)
      integration.py        ADR 0021, around the engine: DeepResearchPurpose (DESIGN_RESEARCH /
                            INTERPRETATION_RESEARCH), ResearchTargetRef (closed: Design Revision,
                            question / battery-object result, analysis module, Sociomap battery,
                            object, object pair), FrozenLineage (artifacts pinned by id + SHA256),
                            DeepResearchRunSpec (its fingerprint keys the run; the engine request's
                            does not move), DeepResearchProvenance; neither purpose may write a
                            design or a deterministic artifact
      interpretation.py     an Interpretation Research run's mission: subjects built by code from
                            its target, the pinned specification and the Design Revision (no
                            respondent number), each with an interpretation:<KIND>:<entity> origin;
                            require_interpretation_mission, the enqueue boundary's check (chunk 30)
      tooling.py            the tool-cost contract: ToolRoute, reserve → dispatching → outcome;
                            needs_sign_off: a live route with a price
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
                            contract, fictional roster, facts by code, interpretation, the dataset;
                            dataset_origin: the origin derived from the personas (a mixed roster refused)
    respondent_behavior.py  18.6.6 behavior.py + styly.py: response process, styles, the seeded draw
    respondent_facts.py     18.6.6 factual_layer.py: facts answered by code, unsupported facts refused
    persona_profile.py      A panel respondent's profile: 18.6.6's generate_persona_text in the mode it
                            ran (calibrated -> core, adaptive), first-person prose cut at 185 words (EXACT)
    persona_topics.py       A question's topics: odvod_temata and a block's union (EXACT)
    persona_signals.py      The persona signal catalog's topic-matched signals: grounded_profile_text
                            (EXACT; a NaN-priority signal ranks last)
    panel_persona.py        A run's sample as personas: every column through
                            decide(PERSONA_CONSTRUCTION), the joint gate per dictionary block (core
                            jointly, each matched donor block within itself), styles over the whole
                            population, a profile per request block; refusals by name
    panel_source.py         A run's panel respondents: panel_plans (the sample under the design's
                            audience filters, the personas, a plan per respondent, in that order);
                            respondent_system (ADR 0024 §4's components); pinned_components: every
                            component but the model binding; PanelPlans.provenance;
                            joint_certificate_record (the population's certificate as a panel
                            dataset records it: text, SHA-256, the panel SHA-256)
    licence.py              Licence eligibility beside residency: DataLineage (no default),
                            LicencePolicy.authorise, LicenceDenied (ADR 0016 decision 5)
    licence_determinations.py  The determinations as data: panel sources APPROVED for
                            bedrock-eu-primary alone (OI-61, data owner 2026-10-12)
    design.py               A Study's Design Revision: immutable content, provenance, the owner tag
    design_reuse.py         A reused design's labels (derive_source_labels: the union over every run of
                            the source revision, never chosen) and its citation (DesignSource)
    research_design.py      A revision -> ResearchSpecification (compile) + AIA's readiness rules;
                            the Sociomap's declarations (sociomap_rating on a scale question,
                            context_objects on a battery: SECONDARY), SpecSelection (the dimensions
                            and audience filters recorded, applied: false), sociomap_support (WARN
                            below n_min 30); a declaration not made is out of the fingerprint
    run_cost.py             The most a run can cost: its model requests x the reservation per request
                            (fieldwork, analysis with its repairs); an upper bound; unknown, never zero
    fieldwork.py            FieldworkSource, FieldworkDataset, validate_dataset; DataOrigin (two
                            synthetic origins and MODELLED_AI_PANEL, ADR 0024), NON_EVIDENCE_ORIGINS,
                            CLIENT_ADMISSIBLE_ORIGINS (the allowlist every client-facing gate reads),
                            origin_kind (SIMULATED / MODELLED / UNKNOWN: the one reading every label
                            uses), MODELLED_DISCLOSURE, RESPONDENT_SYSTEM_METADATA (the dataset's
                            record of its respondent system) and JOINT_CERTIFICATE_METADATA (a panel
                            dataset's record of its population's CORE_JOINT_STATUS, which its evidence
                            is judged under); PersonaSource (fictional_roster | panel)
                            and persona_source_of (a run before the pin: the roster)
    sociomap_register.py    SOCIOMAP_REGISTER: which Sociomap method, at which exact spec fingerprint,
                            is approved (MethodologyStatus); a method absent is INTERNAL_ONLY, never
                            presumed; aia-sociomap-3 approved by the product owner 2026-10-13 (D6);
                            read whenever a map is read (recorded_statuses), never stored on a run
    synthetic_fieldwork.py  Fictional respondents from random.Random(seed), workbench and tests only
    research_aggregate.py   agreguj_otazku's reportable core + uncertainty.py, ported from the unit
                            (EXACT; bootstrap bounds from AIA's generator, OI-62, parity D5)
    research_sociomap.py    The unit's relation matrix -> compute_sociomap; a map's status is the
                            Sociomap register's for its method (sociomap_register.py);
                            require_client_facing refuses anything it does not approve. Beside it each pair's signed r,
                            n, interval and status, relation_rescaled (F2), object_scores (F8), K100
                            only with AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED; rating_universe
                            (every set's items + the declared rating questions); SociomapMethod,
                            default_methods (aia-sociomap-1 + -3; a run that pinned -2 keeps it),
                            read_methods, LEGACY_METHODS: a run computes the methods it pinned;
                            each battery's contract-3 maps; SociomapMethod.formulas: the formulas a
                            stored methodology version replaces, compiled on read (slots()), absent
                            from the stored form when empty
    research.py             A run's phase in words (queued … cancelled), from the engine's state
    holdout/                The respondent system's holdout validation (panel-grounded-respondents 7),
                            pure: bank.py (the item bank: each held-out question's Czech wording and
                            options as fielded, the panel code of each option and the public document
                            and page it was read from; pinned by its canonical SHA-256; one of the
                            seven surveys the panel is built from; item_payload / read_item; repeated
                            option labels refused), eligibility.py (which items a
                            population can hold out: measured, every value an option, 80 % coverage,
                            300 effective donors over the donor behind the answer, nothing the
                            respondent is told; a core item scored only in the ages its survey asked),
                            leakage.py (what a block's respondents are not given, computed: the item,
                            its matched block, every persona field at |r| or Cramér's V >= 0.30, an
                            association that cannot be computed, signals on those or the item's
                            concept), preregistration.py (the seeded split: near-duplicates >= 0.70
                            dropped, 40 % of each domain to development; the hashed record of
                            everything that decides the verdict, P1-P8 included; a confirmation set
                            under 40 items / 5 domains of 4 refused; read_preregistration: a stored
                            record checked as written -- canonical bytes, the code's thresholds, the
                            system's fingerprint and population version, the blocks exactly the
                            confirmation set), arms.py (the model arms: A none,
                            B demographics, C core without catalog signals, D the production persona,
                            S D's profiles deranged; the block's exclusion applied in every arm, each
                            respondent keeping their own facts and styles; D unexcluded is today's
                            PanelPersonas.plan; blocks= asks the preregistered blocks), scoring.py (per item TVD, subgroup TVD, Brier on
                            core items, entropy gap; the P1-P8 verdict: P4 D beats A on TVD, P5 D
                            beats S on subgroups and Brier, one Holm family; a criterion that cannot
                            be evaluated fails), baselines.py (L0 the population marginal, L1 the
                            demographic cell without the respondent's own donor, backing off below
                            30 donors; neither decides the verdict), run.py (a confirmation run from
                            its preregistration: sample, arm x replicate, score; the items as fielded
                            in the preregistered blocks, a fact item refused; requests n x blocks x 5
                            x 3; the system checked but for the gateway's binding; sample_sha256,
                            arm_record / read_arm_record). Tests:
                            conftest.holdout_population, a session-scoped fictional factory, and
                            conftest.holdout_records, a hand-built bank and preregistration
    pipeline.py             Stage order, fingerprints, impact/invalidation rule
    population/             Dataset versions, STATIC/LIVE, lineage, promotion, import
                            contract + validation, weights, bindings, RuntimePopulation
      czech.py              The Czech v17 import contract (pinned by hash, not copied)
      policy.py             Field policy as code: what each field may be used for
      companions.py         Companion assets + the fail-closed joint certificate gate
      authority.py          Population-operator capability (establish / promote)
      runtime.py            RuntimePopulation, issued only by the loader; companion(asset_id): a
                            companion's bytes as the loader verified them at load; joint_certificate:
                            the certificate's verified bytes and the panel SHA-256 it was checked against
      subpanels.py          The 18 built-in subpanels adopted from 18.6.6 (pinned to
                            BUILTIN_SUBPANELS_v17.json), check_subpanel; the counts are 18.6.6's
      audience.py           The audience filter: 18.6.6's sanitize_filters + _mask (EXACT), the kind
                            from the column as pandas types it; subpanel_filters; select_audience over
                            a run's population, refusing where the unit dropped a filter
      audience_catalogue.py The factor catalogue: 18.6.6's catalog (EXACT, fixture catalogue.json),
                            each factor's AUDIENCE_FILTERING answer (catalogue_of), the research-only
                            factors not sent to the screen (for_the_screen)
      audience_preview.py   The audience step's preview: select_audience's counts and
                            draw_panel_sample's verdict at PREVIEW_SEED; counts only
      enrichment.py         The ANALYSIS view's seven runtime dimensions: 18.6.6's attach_derived
                            (EXACT); AudienceDimensionsEnricher, the view's Enricher (composed by
                            the worker's population_loader)
      sampling.py           A run's sample: the audience (audience.py), 18.6.6's largest-remainder
                            quotas over sex x age group x region (+ education from n 700), weighted
                            draw without replacement, raking and the audit; refusals by name;
                            PanelSample.provenance() is what a run records
      materialized.py       A materialized dimension (P4): the hash-pinned contract extension, the M3
                            field policy (modelled; never measured, never weighting),
                            check_child_version; a child is owned by one organization and never a
                            shared population's version (OwnedVersionNotShared); target_met within
                            TARGET_TOLERANCE (binary 0.005, scale 0.01), never presumed
      derivation.py         18.6.6's evidence derivation EXACT (npc-18.6.6-evidence-overlay v1);
                            refuses a dimension no predictor varies for (no_varying_predictor)
      definition.py         DimensionDefinition: the K5 contract as a type (kind, target with its
                            evidence anchor, predictors, missingness, range), hash-identified
      versions.py           owned_version_id: an owned child's id, its content qualified by an
                            owner digest
    project.py              Project, revisions, stage state
    providers.py            Provider policy, model roles, budget and error semantics; NATIVE_PROVIDERS
                            (Bedrock) -- the prototype's providers and policies are read from records only
    residency.py            EU residency, data classes, the fail-closed egress boundary
    scope.py                Organization/Client/Study vocabulary, permissions; one role (Researcher =
                            every permission, ADR 0019) and WORKER_PERMISSIONS, an explicit set that
                            withholds every approval; StudyKind (RESEARCH / SIMULATION);
                            ClientContext + ClientPermission
    deployment.py           AIA_ENV: local / test / develop / staging / production; what each allows
                            (deployed guards, fictional material), the one fictional-material rule the
                            API and the worker both ask
    workspace.py            A research Study's working content: ContentState (EMPTY … AWAITING_MIGRATION),
                            validation, lineage of content migrated from 18.6.6 (ADR 0018, OI-58)
    research_template.py    The research template a new study starts from (the unit's empty project)
    attachments.py          A brief attachment's record and the unit's rules (25 MB, the name, the excerpt)
    questionnaire_import.py The questionnaire template's rows -> sections, as the unit imported them
                            (its row rules and the normalize_project rules an import meets)
    workspace_migration.py  The 18.6.6 migration's rules: file references, the record rewrite, the
                            copy checked against the unit's own hashes, one-for-one validation, report
    knowledge.py            Client Knowledge: layers, kinds, proposals, revisions (ADR 0015);
                            folders and labels (organization, not knowledge: no model sees them, no
                            revision is written), STALE_AFTER (365 days), KnowledgeHealth;
                            source_ref: a file by reference (content.source_id, SOURCE /
                            DOCUMENT / DATASET only)
    client_profile.py       A client's profile on its record (short code, industry, market,
                            description) and its contacts; neither is knowledge, no model reads them
    client_sources.py       A client's sources (lifecycle K2): family by suffix (the owner's format
                            list of 2026-10-13), Locator, Segment, ReadingNote, SourceReading (READ /
                            PARTIAL / UNREADABLE / UNSUPPORTED / REFUSED, never more than happened),
                            display_name (the name as written)
    client_datasets.py      A dataset's preview (K2c): per column the header (row 1 when all text
                            over numbers or dates), kind, fill, distinct values (to 1,000) and five
                            samples; a column flagged personal (header, or a third of its values an
                            e-mail, Czech phone or birth number) has its samples masked; patterns
                            pinned in fixtures/client_datasets/personal.json
    project_memory.py       Project memory's match: every word, accent-folded, a four-letter stem;
                            DIMENSION_LABELS, the canonical dimension titles pinned to the web's
    workflow.py             Workflow DAG, job states, retry classification
    workflow_templates.py   The closed set of workflow types and their step graphs
    methodology/            The Metodika tab's model (ADR 0023), pure: catalogue.py (module, step,
                            group, preset; every step pinned to the function it describes; a step
                            says what it is for, the steps it reads and its audit point, and
                            feeds_of derives the steps that read it), sociomap.py (the object map
                            in the order of its computation, stages S1-S7, each step citing its
                            audit point F1-F16) and
                            sociomap_reference.py (aia-sociomap-1, read-only); expressions.py (the
                            formula language: AST whitelist compiled to closures, no eval; LaTeX
                            written from the expression; slot properties checked on a grid);
                            sociomap_formulas.py (the 14 built-in formulas, bit-identical to the
                            engine; each says what the engine keeps around it, kept_cs, whatever
                            replaces it); aggregation_formulas.py (the aggregate's five
                            estimators, each with what the aggregate keeps around it, kept_cs);
                            versions.py (what a stored version may be: <base>+e<n>);
                            pins.py (the methodology in force -> a run's Sociomap pins;
                            COMPUTED_SLOTS); sociomap_check.py (an edit beside what is in force on
                            three fixed fictional panels, through the run's own pin)
    sociomap/               Sociomapping maths, pure Python: compute_sociomap -> artifact
      slots.py              The formula slots a methodology version replaces (ADR 0023): the ids the
                            engine reads; every engine function takes slots (default none: the code's
                            formula, bit for bit)
      specification.py      SociomapSpec v2 (contract 2, AIA_SOCIOMAP_V1) and SociomapSpecV3
                            (contract 3: AIA_SOCIOMAP_V2, the audit's object map; AIA_SOCIOMAP_V3,
                            the same under AIA's Q5-Q7 decisions: Kish-n pair evidence, the 0.10
                            effect floor, the envelope terrain at provisional sigma 0.25), no defaults,
                            require_supported each; read_spec / spec_payload read a stored spec by
                            the contract it names, never another
      relations.py          scale coercion, mutual projection, ipsatization   F1-F3; pair_status
                            (audit F3: UNKNOWN / RELIABLE / WEAK), person_minmax (F2),
                            coerce_declared_1_10 (F5: a declared matrix type, never detected);
                            kish_effective_n, meets_effect_floor (Q6: two gates, the floor beside
                            the status, never inside it)
      pairs.py              derive_pair_relations (signed r, n, interval, status; with a declared
                            policy, each pair's Kish n and meets_effect_floor) and the unit's
                            derive_relation_matrix
      layout.py             declared layout registry; aia_rowcond_unfolding_v1;
                            fit_smacof_objects (audit F6: objects on the fixed ruler, never rescaled)
      metrics.py            object metrics, T-score, normaliser               F5-F6; primary_scores
                            (audit F8, PRIMARY only, UNKNOWN pairs out); connectedness_100 and
                            rank_with_ties (F9: an order only where intervals part)
      terrain.py            respondent density / object weighted mean         F7-F8;
                            object_envelope (audit F12/F13: max of hills, each its own height; a
                            cell no hill reaches is null; nothing outside the engine computes one)
      engine.py, models.py  the pipeline and the v2 artifact
      engine_v2.py, models_v3.py  compute_object_map -> SociomapArtifactV3 (MAPPED / NOT_MAPPABLE,
                            support); read_artifact reads either contract, refuses any other;
                            read_object_maps: the one reader of a battery's stored maps (contract 3,
                            each map's method equal to its key), for the report and its figures
      view.py               drag overrides, view terrain, scenarios (never write) F9;
                            align_to_reference (a view), stress_quality (the audit's label)
    report/                 The report as data: document model, components, templates (DOCX output)
      print_tokens.py       GENERATED from tokens.json: print colours, type scale in pt, page
      model.py              The document: metadata, sections, every block — numbers only as refs
      evidence.py           EvidenceLedger (built from AdmittedClaims only) and print grades;
                            modelled_panel: the refs that print "modelováno: AI respondenti z
                            populace" beside them (ADR 0024 §7)
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
      validation.py         Validation bound to system fingerprint; tier gate;
                            respondent_system_fingerprint (ADR 0024 §4) and lifts_internal_only (a
                            current holdout on it, nothing else)
      instrument.py         A Study's own items as evidence fields: -1 (simulated) and -2
                            (MODELLED_AI_PANEL), chosen by origin; -2 internal until a holdout lifts
                            it, or, for the client report alone, the owner's lift
      report_lift.py        MODELLED_CLIENT_REPORT_LIFT: the product owner's 2026-10-13 decision as
                            data (ADR 0024 §4 amendment): drops -2's INTERNAL_ONLY for the client
                            report only; only application/client_report.py passes it
      factual.py            Factual layer: panel facts are read, never invented
      admission.py          AdmittedClaim — the ONLY way a number enters a result
    analysis/               The eight analysis modules, drafts, prompts, results
    simulation/             Deterministic simulation core from a frozen WorldModel:
                            reference constants, reject-not-clip validation,
                            inoculation, scenarios, variants, frozen results
  application/
    model_gateway.py        GovernedModelGateway — the ONLY model call path (ADR 0005)
    scope.py                ScopeResolver — the ONLY issuer of a scope context,
                            including a worker's, issued only against a held lease,
                            and of a ClientContext (client_context, accessible_clients);
                            membership of the organization is the access, no grant is read
                            (ADR 0019), and an archived client's studies are not listed
    population.py           PopulationRuntime — the ONLY loader of population data; live_binding:
                            the binding a new run records (None until the population is
                            established; reads no panel); materialize_child: a client's dimension
                            derived over a shared base, written once to the population store and
                            registered as its owned child, never promoted; resolve_child: an owned
                            child, pinned, verified against its base at load; child_binding: a
                            selected child, the study's own client's only
    materialize.py          prepare_materialization: a dimension request checked from a study against
                            LIVE's kept policy (owner from the scope, base, definition);
                            start_materialization: a population_materialize run under the study's
                            population project (owner study_population); child_key, and the run's
                            key within the study; materialization_run / materialization_runs, found
                            only through the study; child_outcome: a child's dimension and what it
                            reached, from its stored extension and registration record
    validation.py           ValidationRuns.start: a confirmation run from the Study's stored
                            preregistration and its pinned bank; refuses a stale system, an unknown
                            or larger ceiling than preregistered, an unconfirmed spend, and a system
                            another Study has started confirming; validation_artifacts: the Study's
                            owned validation project
    population_authority.py PopulationAuthority — the ONLY issuer of an operator context
    population_characteristics.py  A version's weights, blocks, every field's dictionary facts and
                            per-use policy answers, the subpanels checked; from the kept
                            dictionary, re-hashed; reads no row
    audience_catalogue.py   LIVE's kept audience catalogue and the 18 subpanels as filters; reads
                            no row (PopulationRuntime.record_audience_catalogue keeps it)
    audience_preview.py     AudiencePreviewer: LIVE loaded once per process and version through
                            PopulationRuntime, then the domain preview
    project_memory.py       search_client_studies: one client's studies through ScopeResolver,
                            each under its own study context; latest Design Revision, else the
                            working draft, else the name
    design_reuse.py         reuse_design: a new or empty research study of the same client from a past
                            Design Revision (working content, first revision, citation, one transaction);
                            source_runs
    analysis.py             Runs one module: draft → gate → repair ≤2 → COMPLETED/BLOCKED
    analysis_results.py     A module's sources, preparation and stored outcome; reconstruct_run
                            re-judges every outcome under today's harness (refuses an older one);
                            stored_analysis reads them as stored, any harness, judging nothing;
                            retry_failed_modules: a finished run's model-blocked or failed modules
                            asked again as a new linked run over its frozen dataset (no fieldwork),
                            completed ones reused, the preflight's refusals not retried
    report.py               Main internal narrative from eight re-admitted analysis modules;
                            body prose keeps evidence refs and actual headings keep semantic styles;
                            the design chapter after the introduction, "Respondenti a výpočet" and the
                            per-question tables after the methodology, the questionnaire appendix
    report_chapters.py      report_chapters: the map, question, design and method chapters from the
                            run's verified sources (verified_map: the run's Sociomap, derived from its
                            dataset and specification); the worker's report and the report with
                            literature both take them from here
    report_tables.py        question_tables: every question's numbers as tables, each cell a claim
                            admitted question by question for the given surface (internal: a refused
                            question named with its reasons; client: left out and counted)
    report_design.py        compose_design_sections: the design the run executed (questions, sets,
                            sample, audience as stated) and its questionnaire as an appendix
    report_method.py        compose_method_section: who answered (by origin kind), the population
                            recorded and read, filters applied or not, the methods pinned;
                            unrecorded said so
    report_approval.py      approve_report: a person approves a run's stored report (internal, with
                            literature, or client) through ArtifactRepository.approve, once
    client_report.py        compose_client_report / stored_client_report: a modelled run's client
                            report: numbers admitted CLIENT_FACING under the owner's lift and the
                            run's recorded certificate, each labelled modelled with its scope;
                            approved maps only, as figures; the design and the questionnaire;
                            stored once as a draft (research_client_docx); refused by name
                            (ClientReportRefused) for any other run
    contextual_report.py    Combined internal report over an explicitly selected completed interpretation
                            run: scoped ownership, bundle seal and exact frozen lineage; accepted source
                            claims, complete cited numeric context and explicit coverage limits. Generated
                            interpretation remains an unapproved UI draft outside the report; external L
                            citations stay outside respondent evidence. The same chapters as the
                            internal report (report_chapters); stored once per exact source set as
                            research_internal_docx_with_research (DRAFT_UNAPPROVED,
                            stored_contextual_report); the original run is unchanged.
                            See test_citation_valid_inapplicability_inference_is_not_published.
    report_maps.py          Map chapters from frozen object maps and supplied print snapshots, each
                            map with the Sociomap register's status; reading guide, fit/support and
                            signed relationship table; client=True: approved maps only, as figures
    workflows.py            start_workflow: a run from a template, idempotent per revision
    research.py             ResearchRuns: start/list/get/cancel/retry over a Design Revision,
                            found only through the Study; research_artifacts, the ONLY reader;
                            start/retry ask when the run's cost ceiling reaches the study's spend
                            limit, and record the yes (ADR 0019 gate 2); start pins the Sociomap
                            methods -- the organization's methodology in force (ADR 0023: a stored
                            version as aia-sociomap-3+e<n>, its digest in the run's identity) -- and
                            a retry keeps the original's; ResearchAgentJobs.accept: a
                            person applies an agent's proposal (APPROVE_GATE), recorded (gate 1);
                            start records the LIVE population binding, or the study's own client's
                            selected child (population_version_id, pinned), when it creates a run (a
                            found run keeps what it recorded, a retry the original's), and pins
                            its persona source (a panel run is its own identity and needs an
                            established population: PanelPopulationMissing); a retry keeps it.
                            retry_analysis: the same restart under every pin, its fieldwork step
                            given the original's dataset (FrozenDataset: artifact id + SHA-256,
                            verified by the step, never substituted)
    deep_research.py        DeepResearchRuns: the run spec frozen at enqueue (ADR 0021):
                            freeze_design (the engine request: knowledge via for_study, client
                            terms) and freeze_interpretation (a result of this Study's own research
                            run, every artifact pinned and verified, never the latest);
                            start/get/runs/events/cancel/retry (a retry never re-chooses its
                            target); _enqueue, the one enqueue boundary, refuses a spec whose
                            request is not its own purpose's (an interpretation request holds only
                            its target's mission: interpretation_mission_mismatch); an
                            interpretation retry re-freezes the stored target, lineage_changed
                            when a pin moved; legacy runs read legacy-unversioned; the bundle
                            (seal verified), its snapshots and provenance only through the run.
                            The run's effective settings pinned at enqueue (ADR 0022: settings_pin
                            in its metadata and the plan step's input; run_settings reads it back
                            verified); cost_ceiling sized by the pinned allowances and limits;
                            LiveNotApproved (409 live_settings_unapproved, missing + routes) when a
                            priced route is composed and a live setting is not approved
    web_retrieval.py        RetrievalGate: the ONLY way a query or URL leaves -- classify, egress,
                            metering, reserve, journal the dispatch, call, journal the outcome
    develop_seed.py         The synthetic develop world, through the same paths the API uses
    workspace_migration.py  migrate_unit_workspaces: each waiting Study as a named person, through
                            ScopeResolver, in its own transaction; missing is not lost until said so
  infrastructure/
    report_pdf.py           LibreOfficePdf: a stored DOCX rendered as PDF (headless soffice, a private
                            profile per conversion, a timeout); AIA_REPORT_PDF_ENABLED (off by
                            default; on without soffice stops the worker)
    report_docx/            The report as DOCX (python-docx; the `report` extra, imported lazily)
      cover.py, assets/     Original Claude Design lockup/field SVGs in a cover-only header;
                            editable bottom-aligned cover text and preserved draft footer
      object_map_figure.py  Deterministic top/3D PNG snapshots from stored contract-3 points, heights
                            and finite terrain triangles; no layout or terrain recomputation
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
    scope_repository.py     Organizations, clients, studies, budgets; studies in a client, by kind;
                            set_study_spend_confirm (the study's spend limit, audited); any member
                            creates a client (ADR 0019); the grant tables are dropped (chunk 6)
    study_design_repository.py  A Study's design project (owned: projects.owner) and its
                            Design Revisions; the ONLY writer of a Study's design (ADR 0016); a reused
                            design's citation (study_design_sources, insert-once: record_source, source)
    holdout_repository.py   A validation Study's preregistration (holdout_preregistrations): kept once
                            as its canonical bytes, re-hashed and re-checked on every read; found only
                            through the Study; the Study's confirmation (holdout_confirmations), once
                            per respondent system in an organization, held by a unique constraint
    study_workspace_repository.py  A Study's working content in its owned working project
                            (projects.owner = study_workspace): load, save naming its base revision
                            (a stale one refused), history; the brief's attachments as artifacts of
                            that project; found only through the Study (ADR 0018)
    document_text.py        An attachment's text, read as the unit read it (pypdf, python-docx,
                            openpyxl: the `documents` extra), with the ZIP bounds the unit lacked;
                            a PDF's tables through pdfplumber, after pypdf, bounded
                            (`MAX_PDF_TABLES`, 20 s); check_zip_bounds(data, kind) before any
                            Office or OpenDocument ZIP is inflated; grid_from_rows, the one way a
                            reader outside it makes a bounded grid
    source_reading.py       read_source: a client source's bytes -> segments with locators, a pure
                            function: PDF by page and table row, DOCX and ODT by paragraph and table
                            row, PPTX by slide, TXT/MD by paragraph, DOC from its Word 97 piece table
                            (piece_text; olefile only opens the file; a DOC's cells are Word's
                            paragraphs, no row guessed); CSV, XLSX, XLS (xlrd) and ODS by sheet and
                            row, with the dataset preview, an ODS's repeats never materialized past
                            the grid bounds; an XML part declaring a DTD refused
    questionnaire_file.py   A questionnaire file's rows (the unit's CSV and stdlib XLSX readers) and
                            AIA's own template workbook
    unit_project_store.py   A COPY of the 18.6.6 project store, read mode=ro&immutable=1 (a live
                            database refused; the backup ZIP unpacked to scratch); files by base name
    client_knowledge_repository.py  The ONLY reader/writer of Client Knowledge: read inside a
                            resolved scope, changed by a person's write or an accepted proposal
                            (a new revision each time); also of its folders, labels and item filing
                            (no revision, no date moved, every change audited), health and
                            recent_revisions; an edit of an item is approved only against the
                            revision it was written from (base_revision), else
                            StaleKnowledgeProposal (409 knowledge_proposal_stale) unless the
                            reviewer names the current revision (reviewed_revision)
    client_profile_repository.py  The ONLY reader/writer of client_contacts and the profile columns
                            of clients; history read from the audit, never naming an e-mail
    client_source_repository.py  The ONLY reader/writer of client_sources and
                            client_source_occurrences: kept once per client and SHA-256, bytes and
                            reading under org/<org>/client/<client>/sources/<sha256>/, verified on
                            every read; reread: a newer reader's reading beside the first
    artifact_repository.py  Artifact rows, provenance, dependency edges, reuse; find_reusable is
                            newest first within a revision; put(reuse=False) stores beside an
                            artifact under the same fingerprint
    methodology_repository.py  The ONLY reader/writer of the methodology tables (ADR 0023):
                            immutable versions, validated by domain.methodology.versions; append-only
                            activations, newest wins, NULL the code's preset; any member reads,
                            require_administer writes, every change audited;
                            methodology_in_force_for_study, what a run start pins
    deep_research_settings_repository.py  The ONLY reader/writer of the Deep Research settings
                            tables (propose, approve, history); immutable study-test policy proposals and
                            append-only scoped approvals (tables.py:1669 @ db6db022), with catalogue,
                            expiry, fictional-client and USD 20 guards; settings_in_force_for_study,
                            what an enqueue pins (deep_research_settings_repository.py:208 @ db6db022)
    workflow_repository.py  Durable jobs, lease-fenced writes, cost reservations,
                            the population binding each run records; WorkQueue --
                            the only cross-study surface (claim, recover, resume, refuse);
                            resume_budget_wait: a person lifts an AWAITING_BUDGET step, in the
                            approval ledger (the worker's scope cannot); record_spend_confirmation and
                            record_ai_proposal_acceptance (once per agent job): the same ledger;
                            reserve_tool_budget: a priced tool call's hold, the same check, fence
                            and recovery as a model call's
    fan_out_coordination.py  ModelSlots (model requests in flight across processes, PostgreSQL
                            rows) and SharedHostPacer (per-host politeness shared by every worker)
    host_pacing.py          PacedTransport: every fetch waits its host's turn (local or shared pacer)
    population_repository.py  Population registry: versions, populations, history; each version's
                            dictionary bytes (population_version_dictionaries) and audience
                            catalogue (population_version_audience_catalogues), insert-once; an
                            owned child (P4c): versions(…, organization_id=) and visible_version
                            return shared versions plus only that organization's own, the import's
                            lookups see shared alone; extensions insert-once, re-hashed on read
                            (population_contract_extensions)
    population_store.py     Materialized children in EU S3: put_once (a conditional put; the same
                            bytes answer as written, other bytes refused), RoutingPopulationSource
                            (s3:// from the store, else the shared copy), AIA_POPULATION_STORE_BUCKET /
                            _REGION, both or neither
    population_parser.py    Text-preserving panel + dictionary parser (stdlib); write_panel, its
                            deterministic inverse
    population_source.py    PopulationAssetSource: filesystem / memory (EU store later)
    ai_usage_repository.py  Append-only AI usage ledger; uncertain-call resolution
    ai_call_journal.py      CallJournal over the workflow attempt + ledger
    model_adapters/         Anthropic / OpenAI / Claude Code / Bedrock adapters, transports, recorded
                            doubles; live_transport.py (urllib3, no retries), aws_signing.py (SigV4,
                            instance or container role only)
    storage.py              ArtifactStore: S3 / filesystem / memory; s3_client(), the one AWS SDK
                            import site
    storage_settings.py     AIA_STORAGE_*: one typed definition for every composition root
    web_retrieval.py        WebFetcher (every hop and address checked, caps, HTML to a content-
                            addressed snapshot); search/fetch protocols; recorded doubles (they say
                            RECORDED and nothing else). The one live route is web_retrieval_live.py:
                            fee-free Czech/English Wikipedia, separately pinned IP/host, no proxy
    build_identity.py       AIA_BUILD_SHA: the commit a process runs; null, never a guess

migrations/                 Alembic
deploy/docker/              python.Dockerfile (api + worker targets; the worker build arg AIA_WORKER_PDF
                            installs LibreOffice Writer, ~300 MB, on for develop); apps/web/Dockerfile
                            is the client
deploy/develop/             The develop host: Compose, Caddyfile, deploy/backup/restore/smoke, runbook.
                            AIA only: no unit image, service, volume, hostname, credential, data sync
                            or health check (ADR 0018 decision 5); the first deploy without the unit
                            stops its old container and keeps its volume (bin/lib.sh).
                            bin/image_retention.py: protected old release-image cleanup and disk
                            headroom before downloads; a host lock serializes deploys; successful
                            rollback history is recorded only after smoke. Runbook: Disk retention.
                            bin/sync-population.sh (by hand) puts the population's 19 files, listed
                            and pinned in population/v17.files, read-only under AIA_POPULATION_DIR;
                            bin/population.sh runs population_ops in a one-off worker container.
                            AIA's population, never the unit
deploy/reference/           The 18.6.6 unit beside the product, never part of it: Compose project
                            `aia-reference` on the unit's external volume, a basic-auth gate on the
                            host's loopback (127.0.0.1:8765), up/down/backup-state by hand;
                            .github/workflows/reference-unit.yml builds its image and bundle
  bin/backup-legacy-state.py The unit's SQLite databases copied WAL-safe (backup API), for the
                            migration's copy and backup-state.sh
infra/develop/              Terraform for the develop AWS resources (one root, no modules)
docs/architecture/          System design + the ADRs; ai-step-executor-contract.md;
                            research-journey.md (the research journey: stage owners, interfaces, acceptance)
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
tools/film_frame0.py        Checks the launch film's frame 0 is the mark the handoff forms (stdlib
                            over ffmpeg; fails above 0.5 px)
tools/report_preview.py     A report as a reader sees it: DOCX -> PDF -> PNG via LibreOffice,
                            lint, greyscale, +35 % Czech stress (manual)
tools/parity_status.py      Parity verdict per capability, from JUnit XML
tools/progress.py           Every plan's status from its front-matter; `--check` validates it
tools/legacy_oracle.py      Reach the running 18.6.6 unit: probe / record / compare (stdlib)
tools/aggregate_capture.py  Research fixtures from the unit's own functions: `cases`, `capture` (in
                            the unit's venv), `self` (AIA's pinned bounds)
tools/audience_capture.py  Audience-filter fixtures: fictional rows and cases (`inputs`), the unit's
                            own sanitize_filters / _mask / factor_map and catalog on them (`capture`,
                            with pandas)
tools/enrichment_capture.py  Enrichment fixtures: fictional rows (`inputs`), the unit's own
                            enrich_panel on them (`capture`, with pandas)
tools/sampling_capture.py   Sample fixtures: fictional rows and cases (`inputs`), the unit's own
                            draw_representative with the MILP made to fail, and _rake (`capture`)
tools/materialize_capture.py  Materialization fixtures: fictional rows and cases (`inputs`), the
                            unit's own materialize_evidence_dimension (`capture`, pandas + NumPy)
tools/persona_capture.py    Persona fixtures: fictional rows, questions, a fictional signal catalog
                            (`inputs`); the unit's own generate_persona_text, odvod_temata,
                            grounded_profile_text, _render and _compact_anchor (`capture`, with pandas
                            and SciPy)
tools/respondent_capture.py  Respondent behaviour fixtures from the unit's own behavior.py / styly.py
                            (`capture`, in an environment with NumPy, pandas and SciPy)
tools/attachment_text_capture.py  Attachment-text fixtures: fictional documents (`inputs`) and the
                            unit's own `_extract_text` on each (`capture`, with the unit's libraries)
tools/source_fixtures.py    Client-source reader fixtures: fictional text and one fictional export
                            LibreOffice converts into DOC, ODT, DOCX, PPTX, ODS, XLSX and XLS, and a
                            Czech CSV (`write [name …]`: only the named, their pins merged), pinned
                            in fixtures/client_sources/index.json (`verify`)
tools/questionnaire_import_capture.py  Import fixtures: fictional files (`inputs`), AIA's template
                            (`template`), the unit's own import on each (`capture`)
tools/deep_research_capture.py  Leakage-screen and merge fixtures from the unit's own
                            research_context.py (`capture`, `verify`; stdlib only)
tools/bootstrap_seed_sensitivity.py  The unit's bootstrap spread over seeds: the evidence for OI-62
tools/ui_functions.py       Extract ui_app.html's 737 functions verbatim; `effective` prints the binding
                            that runs (the last declaration or reassignment); check the UI ledger
tools/ui_function_runner.mjs, ui_function_capture.py
                            Run extracted functions under Node; capture U<nn> fixtures
tools/caddy_routes.py       CI's check of the adapted develop Caddyfile: one hostname, / -> /app/clients,
                            /app behind AIA's gate, no 18.6.6 document, no upstream but the API and the
                            web client, no panel gate
tools/develop_routing_proof.py, develop_routing_journey.mjs
                            Run the real Caddyfile locally in front of stand-ins; then a browser
tools/ui_workbench/         AIA on this machine, for UI work: the real API on SQLite with local
                            identity and the develop seed, `next dev`, a facade routed by the
                            Caddyfile, a worker with fictional fieldwork; nothing of the unit unless
                            `up --with-unit` runs it beside AIA as reference (scratch copy, fictional
                            panel, its own port, never behind the facade). Never parity. capture.mjs
                            screenshots every AIA screen, and the unit's when it runs;
                            fixture_project.py: fictional research projects; research_journey.mjs:
                            Run -> Results; workspace_journey.mjs: a study's content, file, import,
                            audience, dimensions; both fail on a request to a path the unit served;
                            fictional_population.py: a population of the sampler's 3,000 fictional
                            rows under a contract of its own, established through PopulationRuntime
                            with its catalogue kept, installed as the stand-in's AudiencePopulation
                            (runs still record the Czech LIVE; `--no-audience-population` skips it);
                            audience_journey.mjs: the live audience step (catalogue filters, the
                            preview, subpanels) saved and read back
.planning/                  Progress, plans, open items
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
`legacy/npc-panel-18.6.6/app/` by hand. It is the behavioural baseline every port
is checked against, and runs for that alone: from `deploy/reference/` beside the
develop host's product, on the host's loopback behind a basic-auth gate, started by
hand (ADR 0018 decision 5). The product deployment has no unit in it and needs none.

**The develop site is AIA, client-first** (ADR 0015). `/` answers 302
`/app/clients`; the hierarchy is Clients → client workspace (Přehled, Výzkumy,
Simulace, Znalosti, Data, Profil) → study → stages, and the global navigation has four
items: Klienti, Společenská inteligence, Projektová paměť, Nastavení. Research
and simulation are both `Study` records, told apart by `Study.kind`. The 18.6.6
interface is not part of the product (ADR 0018 decision 4): no page hands off to
it, `/classic` is AIA's public page saying so, and what AIA does not have yet says
so where a person meets it (`docs/migration/interface-screens.json`: every classic
screen REBUILT, REBUILDING, SUPERSEDED or NOT_IN_AIA with where AIA says it). `/app`
sits behind AIA's own gate, `forward_auth` to `GET /api/v1/session/gate` (ADR 0018):
any active member of the organization with an AIA session; what they see inside is
decided per call by the API (user → organization membership; ADR 0019: no client or
study grant is read). No legacy setting touches it. The product hostname serves nothing of the unit (ADR 0018
decision 5): its old paths are the web client's 404, the panel's gate is gone with
it, and `tools/caddy_routes.py` fails a Caddyfile that routes anywhere but the API
and the web client.

**A research study's working content lives in AIA** (ADR 0018, OI-58). The stages load
and save it through `/api/v1/studies/{study_id}/workspace/content`; it is the Study's
owned working project (`projects.owner = study_workspace`), found only through the
Study's `study_workspaces` row, whose `content_state` names where it stands. A save
names the revision it was edited from and a stale one is refused (409), never
applied over a newer one. A study bound to 18.6.6 before ADR 0018 is
`AWAITING_MIGRATION` -- not editable -- until the explicit migration of its 18.6.6
content (`aia_executors.legacy_workspace`, ADR 0018 decision 2) brings it over from a
*copy* of the unit's store, as a named person through their own access; nothing reads
the running unit. `unit_project_id` is lineage only, and nothing finds a study by it. The files a
brief carries are artifacts of the same working project, in AIA's storage
(`/workspace/attachments`), served only through the Study as `application/octet-stream`;
the brief keeps their records, never a URL. A questionnaire file is read in AIA
(`/workspace/questionnaire-import`) and only its sections come back; the stage saves them.

**Client Knowledge is scoped before it is read.** `ClientKnowledgeRepository`
takes a `ClientContext` or `StudyContext` and queries by that client; there is
no global pool filtered afterwards. What a person writes in the client workspace is
knowledge at once; a study proposes and a person accepts (the proposer too, unless
self-approval is turned off), and either writes a new revision with provenance; knowledge
the AI wrote stays a proposal until a person accepts it. An approval never applies an edit
written from an older revision unless the reviewer names the current one (F-K1, OI-111). Nothing changes knowledge otherwise. `make layer_check` keeps the rows inside the
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
Panel-derived data may reach only `bedrock-eu-primary` (OI-61, determined by the data
owner 2026-10-12, `licence_determinations.py`); the licence gate stays beside residency
and refuses it on any other route. A run pins its persona source at start
(`AIA_AI_POPULATION_PERSONAS_ENABLED`, off by default, in the API and the worker): a panel run's
respondents are drawn from the population it recorded and its dataset is `MODELLED_AI_PANEL`; a
worker without the path parks it, never answering with the roster instead
([`panel-grounded-respondents.md`](.planning/plans/panel-grounded-respondents.md)).
A Sociomap's status is the Sociomap register's for the exact method, at its spec fingerprint, that
computed it (`domain/sociomap_register.py`): `aia-sociomap-3` is approved (the product owner,
2026-10-13, D6); `aia-sociomap-1` and anything not registered is `INTERNAL_ONLY`. A study may set a spend limit; a start whose cost
ceiling reaches it needs the person's confirmation, recorded in the approval ledger
(ADR 0019 gate 2).

**The population is resolved once per run.** Research and simulation code gets
population data only from `PopulationRuntime.load_for_run`, which reads the
`PopulationBinding` the run recorded at creation. There is no other loader, no
default weight and no fallback version; `make layer_check` enforces the loader.
Before using a field, a consumer asks `RuntimePopulation.decide(field, use)` and,
before combining fields, `decide_joint(...)` — never the dictionary directly. The
contract is [docs/architecture/population.md](docs/architecture/population.md).
A research run records the LIVE binding at creation (owner, 2026-10-10); only a run that
pinned the panel persona source reads it (fieldwork), and the run says whether its respondents
came from it (`read_by_fieldwork`). On develop,
STATIC is `v17_1_2` and LIVE is `v17_4_0`, imported from 18.6.6 on 2026-10-11.

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
what changed. Its executors are in the worker's default registry and its route in the API, but a
run parks unless `AIA_DEEP_RESEARCH_ENABLED` composes a runtime; the live search routes are
fee-free Czech/English Wikipedia and priced Brave (`AIA_DEEP_RESEARCH_WEB_SEARCH`, Class C), with Common
Crawl's priced index and fee-free archive beside them (`AIA_DEEP_RESEARCH_COMMON_CRAWL`). A priced
call is held against the study's budget before it leaves, and a priced route runs only once its
organization has approved every setting live needs on Settings → Deep Research (ADR 0022). With
no search route the production-shaped composition blocks every web track and sends nothing, and
recorded web retrieval
exists only in `aia_executors.deep_research_recorded` (local and test). Tracks fan out across
workers behind `AIA_DEEP_RESEARCH_FAN_OUT` (off by default), which needs
`AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` (no default, 1-256).

**Deep Research serves two checkpoints, never research truth** (ADR 0021). `DESIGN_RESEARCH`
runs before the methodology freeze and may only *propose*; a person turns a proposal into a new
Design Revision. `INTERPRETATION_RESEARCH` runs over immutable results and has no mutation
authority over respondent data, aggregates, analysis or the canonical Sociomap. Interpretation Research may read the frozen canonical Sociomap. Deep Research and external evidence are never inputs to the canonical Sociomap calculation. Every new run
carries its purpose, a typed target and a frozen lineage (exact artifacts, by SHA256) in an
envelope around the unchanged engine request and sealed bundle; a pre-ADR run reads
`legacy-unversioned`. The engine (retrieval, ladder, investigators, lead, fan-out, recovery,
verification, grounding, confidence, the bundle) is frozen: change it only on a defect or
evaluation finding. Deep Research helps decide what to measure; respondents determine what we
observed; deterministic analysis and Sociomapping determine the computed structure; Deep Research
may then help interpret it. External research never manufactures respondent evidence and never
rewrites deterministic research truth.

**Evidence is a capability, like scope.** A number reaches an analysis result only
as an `AdmittedClaim`, minted only by `admit_numeric_claims` after field policy,
joint structure, support, interval and tier have all passed. Prompts state the
rules; they never enforce them. A modelled number (`MODELLED_AI_PANEL`) reaches a client
only in the client report (`application/client_report.py`): admitted `CLIENT_FACING` under
the owner's recorded lift (`MODELLED_CLIENT_REPORT_LIFT`, ADR 0024 §4 amendment) and the
population certificate its run recorded, labelled modelled; client-facing analysis prose
still waits for a holdout validation.

**The unit is the oracle, and its functions are fixtures.** The strangler plan
([`.planning/plans/legacy-strangler.md`](.planning/plans/legacy-strangler.md))
replaces one capability at a time, compared with the running unit (`deploy/reference`),
reached only through `tools/legacy_oracle.py` and `AIA_LEGACY_REFERENCE_URL`. The 88 research
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
| Operate the population | `python -m aia_executors.population_ops <import\|attach\|establish\|promote> --as <email> …` (needs `DATABASE_URL`, `AIA_POPULATION_ASSET_ROOT`, `AIA_POPULATION_OPERATORS`); `status`, `record-dictionary` and `record-catalogue [--version]` act as no one and take no `--as` (no `AIA_POPULATION_OPERATORS`) |
| **The population on develop** | `bin/sync-population.sh`, then `bin/population.sh import … --all-companions` / `establish` (`deploy/develop/README.md` § The population) |
| **Migrate 18.6.6 content** | `python -m aia_executors.legacy_workspace --store <copy> --attachments <copy> --as <email> [--apply] [--recover-missing]` (needs `DATABASE_URL`, `AIA_STORAGE_*`; dry run by default; runbook `deploy/develop/README.md` § Migrating 18.6.6 content) |
| Tests | `make test` (core + API + worker + executors) |
| Worker tests | `make test-worker` (the multi-process suite needs a PostgreSQL `DATABASE_URL`) |
| Executor tests | `make test-executors` (the snapshot step under the real worker loop; seed; smoke module) |
| Deploy `develop` | Merge to `develop`; [`deploy/develop/README.md`](deploy/develop/README.md) is the runbook. Live at <https://aia-develop.art-chain.io/> |
| **Deployment disk / image dry-run** | On the host, `python3 bin/image_retention.py preflight --registry <deployment-registry> --state-file /opt/aia/develop/.deploy-state/successful-releases.json --protect <current-sha> --protect <incoming-sha>`: no deletion unless `--apply`; the full deploy applies retention under its host lock before pulling. See [`Disk retention`](deploy/develop/README.md#disk-retention) for safeguards, initialization and refusal recovery. |
| Parity vs prototype | `make test-parity` (needs `AIA_LEGACY_REFERENCE`; population parity needs `AIA_REFERENCE_REPO`) |
| Golden-fixture pins and F10/F11 | `make test-golden` (needs the reference repository) |
| **Parity vs the running unit** | `make test-oracle` (needs `AIA_LEGACY_REFERENCE_URL` + `_USER` / `_PASSWORD`; skips cleanly without) |
| Capture UI function fixtures | `python tools/ui_function_capture.py capture` (needs Node); `verify` re-runs and compares |
| **Plan status** | `python tools/progress.py`; `--check` validates every plan's front-matter |
| **Report PDFs** | The worker renders each report's PDF with `AIA_REPORT_PDF_ENABLED=true`, in an image built with `AIA_WORKER_PDF=true` (both on for develop: `.github/workflows/deploy-develop.yml`, `deploy/develop/docker-compose.yml`); on without `soffice` the worker stops at start |
| **Report preview** | `make report-preview` — the four sample reports as pages, in colour, greyscale and +35 % stress (needs `libreoffice-writer`, `poppler-utils`) |
| **Parity verdicts** | `make parity-status` — `PASS` / `FAIL` / `NOT_EXECUTED` / `NOT_RUNNABLE` per capability |
| Lint | `make lint` |
| Format | `make format` |
| Types | `make typecheck` (mypy `--strict` + `tsc --noEmit`) |
| Web tests | `make test-web` (Vitest, pure functions) |
| **Design tokens** | `make web_design` — generated files match `tokens.json`; contrast, palette and accent evidence holds. Change a token: edit `tokens.json`, then `npm run tokens` |
| **UI workbench** | `make ui-workbench` → <http://127.0.0.1:8780/workbench/sign-in>: AIA alone, nothing of 18.6.6; `make ui-workbench-reference`: the same with the unit at `:8767` as reference (its first run installs the unit's requirements into `tmp/ui-workbench/venv`); `make ui-workbench-status`, `make ui-workbench-down`. The API runs on the repo's env (`make setup`) |
| **Develop routing, run** | `sudo python3 tools/develop_routing_proof.py --keep`, then `node tools/develop_routing_journey.mjs` (disposable machine: Caddy on 80/443, `/etc/hosts` names; see the script) |
| Workbench research fixtures | `make ui-fixtures` (workbench running): fictional projects, prints their `/app` links |
| **A research run, end to end** | `make ui-research` (workbench + fixtures): Run → Progress → Results in a browser, on fictional fieldwork |
| **AIA with 18.6.6 absent** | `make ui-workbench` (no unit; its old paths are the web client's 404), `make ui-fixtures`, `make ui-research`, `make ui-workspace` (brief file, template import, audience, dimensions); both journeys fail on a request to a path the unit served |
| **The live audience step, in a browser** | `make ui-audience` (after `make ui-workbench` + `make ui-fixtures`; Playwright + Chromium): `audience_journey.mjs` on the workbench's fictional population: catalogue filters saved as chosen (an empty bound left out, OI-50) and read back after a reload, the preview's count and verdict, a subpanel saved as its filter and a refused one disabled; fails on a request to a path the unit served |
| **The 18.6.6 reference unit** | On the develop host, by hand: `deploy/reference/bin/up.sh <sha>`, `down.sh`, `backup-state.sh <sha> <label>` ([`deploy/reference/README.md`](deploy/reference/README.md)); the oracle through an SSM port forward to `127.0.0.1:8765` |
| Research fixtures from the unit | `python tools/aggregate_capture.py cases` / `self` (repo env), `capture` (the unit's venv) |
| Audience-filter fixtures from the unit | `python tools/audience_capture.py inputs` (repo env), `capture` (a venv with pandas) |
| Enrichment, sample, persona and materialization fixtures from the unit | `python tools/enrichment_capture.py inputs` / `sampling_capture.py inputs` / `persona_capture.py inputs` / `materialize_capture.py inputs` (repo env), `capture` (a venv with pandas and NumPy; persona also SciPy); a re-capture must be byte-identical |
| Deep Research leakage fixtures | `python tools/deep_research_capture.py capture` / `verify` (repo env: the unit module needs only the stdlib) |
| **Deep Research, end to end (recorded)** | `pytest apps/executors/tests/test_deep_research_journey.py` — the real worker, gateway and gate over recorded exchanges: two passes, measured counts, every failure mode; nothing leaves the process |
| **See every screen** | `make ui-capture` (workbench running; needs Playwright + Chromium): every AIA screen, and, with `make ui-workbench-reference`, the unit's router routes and DEMO views as shipped, 1440/1024 → `tmp/ui-workbench/shots/<time>/index.html` + `report.json` (errors, overflow, off-palette colours) |
| **Research UX regression** | After `make ui-fixtures` + `make ui-research`, `node tools/ui_workbench/ux_journey.mjs` (needs Playwright + Chromium): 17 AIA routes at 1440/1024/768/390, result sections, keyboard/hash navigation, client search and preserved 3D camera; real local APIs, fictional fieldwork, no paid calls; evidence → `tmp/ui-workbench/ux-journey/` |
| **Proposal and prompt UX acceptance** | After `make ui-fixtures`, `node tools/ui_workbench/proposal_prompt_journey.mjs` (Playwright + Chromium): real local save/reload, rejected-save retry, unfinished-edit guards, native proposals without legacy analysis, downstream design equality, prompt save/activation/reset and four responsive widths. Local fictional identity only; asserts zero paid jobs. `--facade` and `--out` override the local URL/evidence directory; `AIA_CHROMIUM` selects an installed browser. |
| **Client workspace acceptance** | After `make ui-workbench` + `make ui-fixtures`, `node tools/ui_workbench/client_journey.mjs` (Playwright + Chromium; `AIA_CHROMIUM` selects the browser): six client areas at four widths without overflow; fictional knowledge added, filed, labelled, edited and removed; the profile saved and read back after a reload; a contact added and removed with no e-mail in the history; zero paid jobs. After a migration that adds columns, start the workbench with `python tools/ui_workbench/workbench.py up --fresh` |
| **Settings UX acceptance** | After `make ui-workbench`, `node tools/ui_workbench/settings_journey.mjs` (Playwright + Chromium): all eight tabs at 1440/1024/768/390; real local member/budget persistence, policy proposal/approval/withdrawal, methodology validation/compare/refused-save retry/separate activation, protected drafts and expanded technical details. Fictional local identity only, zero paid jobs. `--facade`, `--out` and `AIA_CHROMIUM` configure the local URL, evidence directory and browser. |
| **The Metodika tab, every module** | `make ui-methodology` (after `make ui-workbench` + `make ui-fixtures`; Playwright + Chromium): every module's steps and links, one edit compared, stored and activated per editable module, a run that pins them; every module restored afterwards. `--facade`, `--out` and `AIA_CHROMIUM` as for the settings journey |
| **Layering** | `make layer_check` |
| **Reference exposure** | `make exposure_check` |
| Everything CI runs | `make check` |
| Docs-only pull request | A PR changing only `.planning/`, `docs/architecture/adr/`, `CLAUDE.md`, `AGENTS.md` or `ARCHITECTURE.md` runs `Documentation checks` instead of the suites; the path list is the `changes` job in `.github/workflows/ci.yml` |
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
├── overview.md        roadmap, decisions (ids `PROGRESS D<n>`), parity status, history
├── plans/             one file per feature, broken into chunks; its status on top
│   └── done/          plans archived before 2026-09-28; nothing new moves here
└── open-items.md      the live defect and question register
```

A feature's status lives in **its own plan file**, as front-matter at the top:

```markdown
---
status: in-progress        # planned | in-progress | done
chunks:
  - "[x] 1. Security audits on a weekly schedule"
  - "[ ] 2. Fold the parity jobs into backend"
---
# <feature>
```

- **At the start of every session, run `python tools/progress.py`** before any
  work: one table of every plan's status and next chunk, read from the
  front-matter. `--check` validates the front-matter (allowed status, well-formed
  chunks, both keys present, no open chunk under `done`); it compares nothing
  with a committed file and is not a CI job. There is no committed status index:
  `PROGRESS.md` was retired on 2026-09-28, and its hand-written parts live in
  `overview.md`, which only docs PRs edit. Its decision ids keep the name
  (`PROGRESS D6`), because code and the interface cite them.
- When a design discussion produces an implementation plan, **save it** to
  `.planning/plans/<feature>.md` with the agreed chunks *before* writing code.
- After each chunk lands, tick it in the plan file's `chunks:` and update
  `status:`. **A feature PR touches only its own plan file**, never another
  feature's, never `overview.md`.
- When every chunk is done, set `status: done`. The file stays where it is: a
  move is a rename, and a rename conflicts with any open PR that edits the file.
- Progress is recorded in two places only: the PR description and the plan file.
  The docs PR carries what crosses features (roadmap, decisions, history) into
  `overview.md` (§1).
- **Do not open a parallel backlog.** If `overview.md` or a narrative document
  disagrees with the plan files, the plan files win and the other is stale.

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

When reporting a defect — to a human, in your plan file, or into
`.planning/open-items.md`:

1. The claim, in one sentence.
2. The anchor: `file:line @ SHA`.
3. A reproduction that fits one command or one test.
4. The user-visible consequence.
5. The smallest fix.
6. The test that would have caught it.

Missing the reproduction makes it a **hypothesis**, and it is labelled as one.
Hypotheses are reproduced or deleted; they are never budgeted for.

A feature PR records a new finding in its plan file under **Findings** and lists
it under Doc follow-up; a fix that closes an existing OI says so there too. The
docs PR moves findings into `open-items.md` and gives them their OI numbers.
Numbers are allocated only there, so two open PRs never take the same one.

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

- [ ] No shared file from §1 is edited on this feature branch; anything they
      describe that moved is written under Doc follow-up in the PR description.
- [ ] The plan file's front-matter reflects the chunk that just landed.
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
