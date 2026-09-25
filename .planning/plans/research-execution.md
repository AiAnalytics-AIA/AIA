# PR C — Research execution: Run → Progress → Results, under the client

**Status:** in progress on `feature/research-execution` (from `develop` @ `4ad5f66`, PR #51 merged).
**Decided by:** the data owner, 2026-09-25 (D1–D3 and design ingestion below).
**Follows:** [client-first-ia.md](client-first-ia.md) (ADR 0015) · research-flow-rehome chunks 7–9 are
replaced by this plan · **precedes** the Agent Runtime Foundation (Study → AgentRun → AIA
Orchestrator → ModelGateway → Bedrock).

## Problem

A researcher can design a study in AIA (Zadání … Dimenze, ADR 0015) but cannot run it there: the
Run, Progress and Results stages are a hand-off to 18.6.6 (`StepPlaceholder`, `ResearchScreen.tsx:264`).
Behind that, three things are missing, each anchored at `develop` @ `4ad5f66`:

1. **No research workflow.** `WORKFLOW_TYPES = {"develop_snapshot"}`
   (`packages/aia_core/src/aia_core/domain/workflow_templates.py:34`); the reference's 24-node
   research DAG exists only in `docs/architecture/workflows.md:314-332`.
2. **Runs cannot see the design.** `workflow_runs.project_id` is an FK to AIA `projects`
   (`infrastructure/tables.py:830`), while the stages' working content lives in the unit's store,
   reached through `study_workspaces` (OI-58). A research Study has no AIA project.
3. **None of the deterministic research methods runs in AIA.** The Sociomap engine is ported
   (`domain/sociomap/`, F1–F9) but nothing feeds it; aggregation, donor QC, battery gates and
   segments exist only in the vendored unit (`legacy/npc-panel-18.6.6/app/dotaznik.py:1405`,
   `uncertainty.py`, `qc.py`, `study_validation.py`, `sociomap.py`).

## What the reference says the pipeline is

`AIA-reference` (`rebuild-contract.md`, `inference-document.md:71-77, 394-468`,
`dependency-map.md:53-110`): 24 nodes, `compile → research → design → questionnaire → audience →
dimensions → sample → preflight[review] → run → aggregate → donor_qc[review] → analysis_*×8 →
interpret → verify → alignment → report → delivery`. The rule: *everything downstream of the answers
is deterministic statistics; the model interprets numbers, it does not produce them.* Even inside
fieldwork the model returns a probability distribution per respondent and question; code applies
response-style effects and draws the answer with a seeded RNG, and facts already in the panel are
answered by code (`factual_layer`, EXACT).

## Decisions (data owner, 2026-09-25)

| # | Decision |
|---|---|
| D1 | **Pre-AI fieldwork.** On develop a real run progresses honestly to fieldwork and **parks** in an explicit waiting-for-AI-runtime state; nothing is fabricated, no fixture is substituted, no downstream stage is shown as done. Tests and the workbench may use a clearly labelled **fictional synthetic dataset** to prove Design → synthetic fieldwork → Aggregate → Sociomap → Results. The synthetic path is **structurally prevented** from being production fieldwork. |
| D2 | **First methods: Aggregate + Sociomap.** Aggregate proves the respondent-data → analysis-result boundary; Sociomap proves a real deterministic methodology artifact downstream. Next, in order: Donor QC → battery quality gates → segments. Not in PR C. |
| D3 | **Provider transmission.** The licensing question is unresolved (reference `open-decisions.md` D3). Until positively approved, PIAAC, ISSP and any panel-derived microdata are **prohibited from transmission to any model provider, Bedrock included**. Enforced fail-closed: a dataset/provider combination without an explicit approved classification → no external transmission. The **determination** (a legal fact, changeable) is recorded separately from the **engineering rule** (code), so approval changes policy data, not the runtime. AI fieldwork may be built and tested on synthetic or explicitly cleared data only. |
| DI | **Design ingestion.** The browser submits the design; AIA validates it against the authenticated Study and persists it as a versioned, Study-scoped **Design Revision** with provenance. The browser supplies content, never authority. A run binds to an explicit Design Revision ID; a later edit creates a new revision and never mutates the one under an existing run. |

## Shape

```
Browser (research stages)                 AIA API                                  Worker
  ─ submit design ───────────────────▶ POST /studies/{s}/design/revisions   (EDIT_STUDY)
                                        → Design Revision (immutable, sha256, provenance)
  ─ Spustit ─────────────────────────▶ POST /studies/{s}/research/runs      (RUN_WORKFLOW)
                                        {design_revision_id, client_request_id}
                                        → run of the `research` workflow, pinned to the revision
  ◀─ poll ───────────────────────────  GET  /studies/{s}/research/runs/{run}  (state, steps,
                                        checkpoints, timestamps, failure, artifacts, usage)
                                                                                claim → execute:
                                                                                compile
                                                                                preflight
                                                                                fieldwork ─▶ source?
                                                                                  ai_runtime: none yet
                                                                                    → PARK (waiting AI)
                                                                                  synthetic (tests/
                                                                                    workbench only)
                                                                                aggregate  (ported)
                                                                                sociomap   (engine)
  ◀─ results ────────────────────────  GET  …/runs/{run}/artifacts/{id}      (VIEW_RESULTS)
```

- **The execution seam is the one that exists.** `execute(study_context, stage, input_revision)` is
  `start_workflow(scope, project_id, workflow_type="research", …)` pinned to a Design Revision; a
  step is a `StepExecutor` kind (`apps/worker/src/aia_worker/executor.py:275`). The Agent Runtime
  adds executor kinds (fieldwork, analysis, report) that drive `ModelGateway` inside a step
  (`docs/architecture/ai-step-executor-contract.md`); AIA keeps the workflow, the budget
  reservation, the ledger and recovery (ADR 0006). No new framework.
- **Steps are tools.** Each deterministic method is a pure function in `aia_core` with a typed
  input and output, run by a step executor now and registered in `ToolRegistry`
  (`domain/ai_tools.py`) for agents later. The step and the tool call the same function.
- **Fieldwork is a boundary, not a method.** The fieldwork step's only job is to produce a
  **fieldwork dataset** (respondent rows + weights + donor ids + answers) from a declared source,
  and every later step reads only that dataset. PR C has two sources: `ai_runtime` (absent → park)
  and `synthetic_fixture` (tests/workbench composition only). The Agent Runtime PR adds the AI
  respondent engine as the `ai_runtime` source.
- **Nothing here calls a model.** No provider, no Bedrock, no agent loop.

## Chunks

Each chunk: schema + logic + tests, its own commit(s), `make verify` green before the next.

| # | Chunk | State |
|---|---|---|
| 0 | This plan; ADR 0016 (research execution, fieldwork boundary, the model-transmission rule); open items for D3's determination and the numerics question | done: ADR 0016, OI-61 (licensing determination), OI-62 (NumPy random stream); the IA plan archived and its PROGRESS row moved to Completed |
| 1 | **Design Revisions.** `study_designs` (Study → its AIA design project, one per research Study); submit/list/get over `/studies/{s}/design/revisions`; immutable, deduplicated by content, provenance (actor, time, source stage, base revision); cross-client and invalid-Study tests | done: `domain/design.py`, `study_design_repository.py`, migration `eff3c6ed26b4` (upgrade, `alembic check`, downgrade on PostgreSQL 16), `routers/research.py`; `test_design_revisions.py` (11), `test_research_api.py` (3); the Study filter mutation-checked; two layer rules |
| 2 | **The `research` workflow and the execution API.** Template `compile → preflight → fieldwork → aggregate → sociomap` (reference node keys); start (idempotent by `client_request_id` and by revision), list, get, cancel, retry (a new run linked to the one it retries); the explicit waiting-for-AI-runtime park (no auto-resume; resumed only when the runtime exists); 404/403 semantics; cost fields only under `VIEW_COSTS` | pending |
| 3 | **Model-transmission rule (D3).** Dataset licence classes and the provider rule in `aia_core` (fail closed; unknown ⇒ prohibited); the determinations as separate policy data (all panel-derived sources: *not approved*); enforced at the gateway's egress boundary so no caller can transmit panel-derived material; tests and a layer rule | pending |
| 4 | **compile, preflight and the fieldwork boundary.** compile: the design → a typed research specification (questions, object batteries, audience, N) as an artifact; preflight: structural readiness (AIA's rules, labelled as such; the legacy technical check stays in /classic); fieldwork: source resolution, the park, and the synthetic source — refused outside the test/workbench composition, stamped `data_origin=SYNTHETIC_FIXTURE`, never client-facing | pending |
| 5 | **Aggregate.** Port `uncertainty.py` (weights, Kish n, donor support and status, weighted mean/distribution/quantile/variance) and the reportable core of `agreguj_otazku` for `vyber`/`multi`/`skala`/`otevrena`, with fixtures captured by running the vendored unit's own functions. Bootstrap intervals need NumPy's PCG64 stream: attempt a pure-Python PCG64 + `integers`, proven against captured draws; if it cannot be made exact, intervals are a recorded INTENTIONAL_DIFFERENCE and the decision goes to the data owner | pending |
| 6 | **Sociomap.** Port `derive_relation_matrix` (object×object from common respondent ratings) with a captured fixture; the step builds `SociomapInputs` from the specification's object batteries and the fieldwork dataset and calls `compute_sociomap`; the artifact carries the spec and its methodology status (D6 open ⇒ not client-facing) | pending |
| 7 | **Web: Run, Progress, Results** under `/app/clients/<c>/research/<s>/{run,progress,results}`. Run: what will run, the Design Revision, readiness, one dominant *Spustit*; Progress: status in words, step checkpoints, timestamps, the park explained, cancel/retry; Results: artifacts with provenance, aggregate tables with suppression and intervals, the sociomap summary, the synthetic banner. The legacy analytical report stays an explicit /classic hand-off | pending |
| 8 | **Workbench and proof.** A worker in the workbench (synthetic source on), fixtures bound to studies, capture of the three stages; the routing journey extended: start → park (production composition) and start → completed with results (synthetic) | pending |
| 9 | Documents (CLAUDE.md, ARCHITECTURE.md, AGENTS.md, PROGRESS.md, ledgers, plans), `make verify`, PostgreSQL suites, per-commit checks, PR | pending |

## Structural guarantees (tested)

- A run names a Design Revision by id; the revision's content is never mutated (a new save is a new
  revision); a revision of another Study, or of another client, is 404.
- The browser never supplies a unit project id, client id or organization id to any new route;
  nothing finds a Study by a unit id.
- The synthetic fieldwork source cannot run in the production composition (`aia_executors.registry`
  never registers it; the worker refuses a run whose recorded source it does not provide; the
  artifact carries its origin; the evidence gate never admits a client-facing claim from it).
- No executor in this PR reaches `ModelGateway`; `make layer_check` keeps provider SDKs out.
- Panel-derived material cannot be transmitted to any provider while its determination is not
  approved, whatever the caller does.

## Not in PR C

AI fieldwork, analysis modules, interpretation, report and delivery (Agent Runtime PR); Bedrock;
Donor QC, battery quality gates, segments (next, in that order); the legacy analytical report
(hand-off); OI-58 (the unit store still holds the editing copy); OI-59; Simulation runtime; the
Data Library; Project Memory; Sociomap redesign or client-facing sociomaps (D6).

## Exit criteria

An authorized researcher enters a client-scoped Research Study, submits the design, starts the run,
watches truthful durable state, and on develop sees it park at fieldwork waiting for the AI runtime;
in tests and the workbench the same run, fed by the labelled synthetic dataset, completes and its
Aggregate and Sociomap artifacts are inspectable from Results with their provenance — without a
unit-project identity anywhere in the product surface.
