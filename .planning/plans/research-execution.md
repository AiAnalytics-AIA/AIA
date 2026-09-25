# PR C — Research execution: Run → Progress → Results, under the client

**Status:** in progress on `feature/research-execution` (from `develop` @ `4ad5f66`, PR #51 merged).
**Decided by:** the data owner, 2026-09-25 (D1–D3 and design ingestion below; D3′, D6′, D11′ and DI′ the same day).
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
| D3′ | **Two gates, not one** (data owner, 2026-09-25, adjusting D3). Dataset/provider **licence eligibility** and **EU residency** are separate policies with separate owners, reasons and records: licence eligibility is `domain/licence.py` + the determinations in `domain/licence_determinations.py`; residency is `domain/residency.py` (ADR 0008). Both are enforced at the one egress boundary, `GovernedModelGateway`, and **both must pass** before any adapter is reached; neither implies the other, and a refusal names which gate refused. |
| D6′ | **Integration is not exposure** (adjusting D2/D6). PR C integrates the deterministic Sociomap engine into the research run and proves synthetic fieldwork → aggregate → sociomap → results internally. Whether a Sociomap may be shown in production or in a report stays gated on PROGRESS D6 (the four AIA declarations, `sociomapa-methodology-decision.md`); the artifact carries that status and every client-facing surface refuses it while D6 is open. D6 does not block the seam. |
| D11′ | **The smallest stable deterministic contract for intervals** (adjusting chunk 5). Characterised first: in 18.6.6 only the interval *bounds* depend on the random stream, no research decision reads a bound, and the unit's own bounds move by up to 12 rounding steps when only the seed changes (OI-62, `tools/bootstrap_seed_sensitivity.py`). So: estimates, support and suppression EXACT; intervals the same estimator under AIA's own seeded generator, inside the unit's seed envelope; **no PCG64** unless a consumer later needs bound equality. |
| DI′ | **Reuse `project_revisions.revision_id` — after closing the gap verification found** (adjusting DI). Verified @ `7e0fa7c`: a revision row is only ever inserted (`repositories.py:446`, via `save`/`create`); no statement updates one except chunk 1's own `reason` stamp on a just-inserted row; the id is unique (`tables.py:155`); a run records `(project_id, project_revision)` and `metadata.design_revision_id` once, at creation (`workflow_repository.py:448`), never rewritten; a design project cannot be purged while its Study binds it (`study_designs.project_id` RESTRICT). **Not verified — a defect:** the design project was also an ordinary project to the generic `/studies/{s}/projects` routes, so a researcher could list it, `PUT` content that skipped `validate_design` (a `client_id` key was accepted as revision 2, source `autosave`), and trash it while runs still started on it. Reuse holds once only the design repository can write it (chunk 1b). |

## Shape

```
Browser (research stages)                 AIA API                                  Worker
  ─ submit design ───────────────────▶ POST /studies/{s}/design/revisions   (EDIT_STUDY)
                                        → Design Revision (immutable, sha256, provenance)
  ─ Spustit ─────────────────────────▶ POST /studies/{s}/research/runs      (RUN_WORKFLOW)
                                        {design_revision_id}  (idempotent per revision)
                                        → run of the `research` workflow, pinned to the revision
  ◀─ poll ───────────────────────────  GET  /studies/{s}/research/runs/{run}  (state, steps,
                                        checkpoints, timestamps, failure, artifacts, usage)
                                                                                claim → execute:
                                                                                compile
                                                                                preflight
                                                                                run (fieldwork) ─▶ source?
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
| 1b | **Only the design repository writes a Study's design** (DI′). `projects.owner` (`NULL` for an ordinary project, `study_design` for a Study's design project), backfilled from `study_designs`; `ProjectRepository(owner=…)` adds the owner to its isolation predicate, so a repository without the owner cannot list, read, save, patch, trash, restore, purge or run the design project (404, as for any project outside scope); `create()` takes the revision reason, so no revision row is ever mutated; an ORM guard refuses any UPDATE of a `project_revisions` row, and a layer rule forbids a bulk one | done: migration `1777fcb96352` (upgrade with backfill of a bound design project, `alembic check`, downgrade on PostgreSQL 16); `ProjectRepository(owner=)`, `create(reason=)`, `start_workflow(owner=)`; `tables.py` `_revisions_are_never_updated`; three layer rules (51 pass). Tests: `test_design_revisions.py::test_only_the_design_repository_can_see_or_write_the_design`, `::test_a_revision_row_is_never_updated`, `test_research_api.py::test_the_generic_project_routes_cannot_see_or_write_a_design` (the reproduction, now 404 on read, save, patch, trash and run); dropping the owner predicate fails three tests, dropping the listener fails one. Left as is: the generic `/projects/{p}/artifacts/{a}` route checks only that a project is the Study's, so a researcher of the same Study could read a research artifact by id outside its run -- within scope, recorded for chunk 4 |
| 2 | **The `research` workflow and the execution API.** Template `compile → preflight → run → aggregate → sociomap` (reference node keys; `run` is fieldwork); start (idempotent by revision), list, get, cancel, retry (a new run linked to the one it retries); the explicit waiting-for-AI-runtime park (no auto-resume; resumed only when the runtime exists); 404/403 semantics; cost fields only under `VIEW_COSTS` | done: `FailureClass.RUNTIME_UNAVAILABLE` parks `WAITING_PROVIDER` with reason `ai_runtime_unavailable`, non-consuming, and `resume_due` never resumes it; `ResearchRuns` finds a run only through the Study's design project and `workflow_type`; the phase is QUEUED until a step has an attempt (the engine stamps `RUNNING` at creation); the fieldwork source is the deployment's (`AIA_RESEARCH_FIELDWORK_SOURCE`, `synthetic_fixture` refused on staging/production). Idempotency is per revision (`research:<REV>`, a retry `…:retry:<RUN>`): a second key from the browser would only let one revision have two live runs. Tests: `test_research_runs.py`, `test_research_api.py` (runs), `test_config_and_security.py::test_synthetic_fieldwork_is_refused_on_every_deployed_environment`. The positive artifact read lands with chunk 4's first artifact |
| 3 | **Licence eligibility, a gate beside residency (D3, D3′).** `domain/licence.py`: `DataLineage` (declared, never defaulted; `DataLineage.none()` is itself a declaration), `LicenceDetermination`, `LicencePolicy.authorise` (undeclared lineage, unknown dataset, undetermined or refused, or approved for another route ⇒ refused), `LicenceDenied` — its own refusal, deliberately not an `EgressDenied`. `domain/licence_determinations.py`: the determinations as data (PIAAC, ISSP, the Czech panel: UNDETERMINED, OI-61; AIA's fictional fixture: approved). `ModelRequest.data_lineage` (no default, like `data_classification`); `GovernedModelGateway(licence=…)` (no default) runs residency, then licence, before any adapter, each refusal `PERMISSION` with its gate's reason (`egress_*` / `licence_*`); layer rules: determinations and policies built only in their module | done: 13 tests in `test_licence_gate.py`; `test_model_gateway.py::test_licence_is_a_second_gate_refused_before_dispatch` (5 cases), `::test_each_gate_refuses_on_its_own_and_names_itself`; removing the gateway's licence call fails 5 tests; two layer rules (53 pass). No production composition builds a gateway yet — the Agent Runtime PR is the first, and must pass `recorded_policy()`. Not done: lineage is not yet written to the usage ledger (a ledger column; with the first real call) |
| 4 | **compile, preflight and the fieldwork boundary.** compile: the design → a typed research specification (questions, object batteries, audience, N) as an artifact; preflight: structural readiness (AIA's rules, labelled as such; the legacy technical check stays in /classic); fieldwork: source resolution, the park, and the synthetic source — refused outside the test/workbench composition, stamped `data_origin=SYNTHETIC_FIXTURE`, never client-facing | done: `domain/research_design.py` (`compile_design`, `assess_readiness`, `prepare`: rules cited to the unit where they follow it; conditional questions and familiarity batteries are a readiness FAIL, never skipped; filters and non-population audiences a WARN the AI source must honour), `domain/fieldwork.py` (`FieldworkDataset`, `validate_dataset`), `domain/synthetic_fieldwork.py` (from `random.Random(seed).random()` only); executors `aia_executors/research.py` (compile, preflight, fieldwork) and `aia_executors/workbench.py` (the only composition with the fictional source; refuses unless `AIA_ENV` is `local`/`test`); `GET …/research/readiness`, start refuses a not-ready design (409 `design_not_ready`); every research artifact lives on the owned design project and is read only through its run (`research_artifacts`, `ArtifactRepository(owner=)`), which closes the recorded artifact-read gap; respondent rows are never inlined to the browser; the evidence gate blocks a client-facing claim on `SYNTHETIC_FIXTURE` data (`ViolationCode.SYNTHETIC_DATA_ORIGIN`); five layer rules keep the generator and the workbench composition out of production code and deployments. Tests: `test_research_design.py` (14), `test_research_executors.py` (10), `test_research_api.py` readiness + artifact scoping, `test_evidence_admission.py::test_a_number_from_fictional_fieldwork_is_never_a_client_facing_claim` |
| 5 | **Aggregate** (D11′, OI-62). Port `uncertainty.py` (weights, Kish n, donor support and status, weighted mean/distribution/quantile/variance, the cluster bootstrap) and the reportable core of `agreguj_otazku` for `vyber`/`multi`/`skala`/`otevrena`. Fixtures captured by running the unit's own functions: estimates, support and suppression compared EXACT; each bound compared against the unit's envelope over K seeds; AIA's own bounds pinned by a self-fixture. Generator: `random.Random(seed).random()`, index `floor(u·m)` — no PCG64. `statistics.uncertainty` gains the documented deviation for bounds with its gate | pending |
| 6 | **Sociomap, integrated; exposure still gated (D6′).** Port `derive_relation_matrix` (object×object from common respondent ratings) with a captured fixture; the step builds `SociomapInputs` from the specification's object batteries and the fieldwork dataset and calls `compute_sociomap`; the artifact records the engine version, the SociomapSpec and `methodology_status` (D6 open ⇒ `INTERNAL_ONLY`). The API serves it to the Study's own researchers flagged internal; no client-facing surface, export or report renders an `INTERNAL_ONLY` sociomap (tested) | pending |
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
  approved, whatever the caller does; a call reaches an adapter only when residency **and** licence
  eligibility both pass, and a refusal names the gate.
- Only the design repository can write a Study's design project; no revision row is ever updated.
- No `INTERNAL_ONLY` Sociomap reaches a client-facing surface while D6 is open.

## Implemented now, blocked, deferred

**Implemented in PR C** (when every chunk lands): Design Revisions the browser submits and only the
design repository writes; the `research` run over one revision — start, read, events, cancel,
retry — Study-scoped with 404/403 semantics; the honest park at fieldwork; compile, preflight and
the fieldwork boundary; the synthetic source, refused in every deployed composition; Aggregate
(exact estimates and support, the stable interval contract); the Sociomap step as an internal
artifact; licence eligibility and residency as two gates at the gateway; the Run, Progress and
Results stages; the workbench and routing proof.

**Blocked by D3 (OI-61, legal and the data owner)** — built and enforced, not live:
- AI fieldwork against PIAAC, ISSP, the Czech panel or anything computed from its rows. The rule
  refuses it at the gateway; AI fieldwork can only be exercised on the fictional fixture or on data
  whose determination approves a route.
- Any model interpretation of panel-derived aggregates, for the same reason.

**Blocked by D6 (PROGRESS D6, the methodology owner)** — integrated, not exposed:
- A Sociomap in any client-facing surface, export or report. PR C produces and stores it, labelled
  `INTERNAL_ONLY`, and proves the chain on synthetic data.

**Deferred — not in PR C:**
- The Agent Runtime Foundation (next PR): `AgentRun`, the orchestrator, the `ai_runtime` fieldwork
  source, Bedrock behind `ModelGateway`.
- Analysis modules, interpretation, report and delivery.
- Donor QC, then battery quality gates, then segments (D2's order).
- The legacy analytical report (an explicit /classic hand-off).
- OI-58: the unit store still holds the editing copy.
- OI-59: membership → client grant → study grant.
- Simulation runtime; the Data Library; Project Memory; the Sociomap redesign.
- A PCG64 port (only if a consumer needs bound equality, OI-62).

## Exit criteria

An authorized researcher enters a client-scoped Research Study, submits the design, starts the run,
watches truthful durable state, and on develop sees it park at fieldwork waiting for the AI runtime;
in tests and the workbench the same run, fed by the labelled synthetic dataset, completes and its
Aggregate and Sociomap artifacts are inspectable from Results with their provenance — without a
unit-project identity anywhere in the product surface.
