# Domain map

Bounded contexts, what each owns, and which direction the dependencies run.

These contexts were derived from the prototype's actual module structure and
call graph, not chosen in advance. Where the prototype had several generations of
the same feature, the context reflects the surviving one.

## Dependency graph

```
                         ┌─────────────┐
                         │  Projects   │  revisions, stages, history
                         │  (core)     │  ← everything depends on this
                         └──────┬──────┘
                                │
        ┌───────────────┬───────┴────────┬────────────────┐
        │               │                │                │
 ┌──────▼──────┐ ┌──────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
 │  Workflows  │ │  Artifacts  │ │  Validation  │ │  Providers   │
 │  & Jobs     │ │  & Storage  │ │  & Evidence  │ │  (AI runtime)│
 └──────┬──────┘ └──────┬──────┘ └───────┬──────┘ └───────┬──────┘
        │               │                │                │
        └───────┬───────┴────────┬───────┴────────────────┘
                │                │
        ┌───────▼──────┐ ┌───────▼───────┐
        │   Research    │ │  Simulation   │   the two lifecycles
        └───────┬───────┘ └───────┬───────┘
                │                 │
        ┌───────┴─────────────────┴───────┐
        │                                 │
 ┌──────▼──────┐ ┌──────────────┐ ┌───────▼────────┐
 │  Population │ │   Analysis   │ │ Visualisation  │
 │  & Audience │ │  & Reporting │ │  (Sociomapa)   │
 └──────┬──────┘ └──────────────┘ └────────────────┘
        │
 ┌──────▼───────────────┐
 │  Data Library &      │  sources → evidence → dimensions → LIVE population
 │  Society Intelligence│
 └──────────────────────┘
```

Nothing above depends on anything below it in a cycle. Population and Data
Library are leaves: they publish immutable population revisions that Research and
Simulation consume.

## The contexts

### Projects (core)

**Owns:** project identity, immutable revisions, stage state, stage input
fingerprints, the impact/invalidation rule, project history, trash, settings.

**Status:** implemented. `aia_core.domain.project`, `aia_core.domain.pipeline`,
`aia_core.infrastructure.repositories`.

**Why it is the core:** it answers "what work is still valid", which every other
context needs before it spends money. Legacy source: `project_store.py`,
`project_pipeline.py`, `project_engine.py`, `project_migration.py`.

### Workflows & Jobs

**Owns:** the workflow DAG, job records, dependencies, leases, heartbeats,
retries and their classification, cancellation, waiting states, approvals,
schedules, cost reservations, stalled-job recovery.

**Status:** not started (Phase 3). Legacy source: `job_store.py` (10 tables),
`workflow_engine.py` (the canonical 24-node research DAG), `worker_job.py`,
`worker_daemon.py`, `scheduler.py`, `cost_controller.py`.

**Note:** the prototype's `workflow_engine.STANDARD` list is the single most
valuable artifact in the reference. It encodes stage order, dependency edges,
interaction mode and artifact targets for the whole research pipeline.

### Artifacts & Storage

**Owns:** artifact identity, content hashing, provenance, dependency edges,
approval and freeze flags, the storage abstraction, retention.

**Status:** schema implemented, storage adapter not started (Phase 2 completion).
Legacy source: `artifact_store.py`, `project_artifact_sync.py`, `output_pack.py`.

### Providers (AI runtime)

**Owns:** provider identity and policy, model roles, structured-output contracts,
error classification, quota and capacity semantics, token and cost accounting,
budget enforcement, the audit trail of every provider switch.

**Status:** domain rules implemented (`aia_core.domain.providers`); the gateway
and SDK adapters are not (Phase 4). Legacy source: `ai_router.py`,
`provider_runtime.py`, `provider_auth.py`, `claude_code_provider.py`,
`ai_runtime.py`, `cost_estimator.py`, `pricing_engine.py`.

### Validation & Evidence

**Owns:** evidence roles and their permitted uses, numeric evidence traces,
validation gates, holdout protocol and registry, legal and tier gates, the
methodology policy itself.

**Status:** foundation implemented in `aia_core.domain.evidence`: the 400-field
dictionary as typed, fail-closed policy; the `CORE_JOINT_STATUS` certificate,
hash-bound; the permissible-claim policy (measured vs modelled basis,
disclosures, joint restrictions); effective-n support with `SUPPRESS` by
default; the allowed-metric set; validation bound to a system fingerprint; the
tier gate; the factual layer's explicit contract; and evidence admission, the
only way a number becomes an `AdmittedClaim`. Not yet: the holdout protocol and
registry, the legal gate, benchmarks, and the parts listed in
`.planning/open-items.md` OI-18 that need the withheld legacy source. Legacy
source: `validation_gate.py`, `evidence_validator.py`, `tier_gate.py`,
`fidelity.py`, `core_joint.py`, `validation_status.py`, `smoke_validation.py`,
`factual_layer.py`, `holdout_protocol.py`, `legal_gate.py`, `product_policy.py`,
`provenance.py`, and the machine-readable `PRODUCT_POLICY.json`,
`DATA_CONTRACT_v17.json` and `FIELD_DICTIONARY_v17_1.csv`.

**Note:** this context must fail closed. The prototype deliberately blocks rather
than degrades when a methodology precondition is unmet, and that behaviour is a
product requirement, not a limitation.

### Research

**Owns:** the 13-stage research lifecycle — brief, deep research, design,
questionnaire, audience, dimensions, sample plan, fieldwork, aggregation,
validation, analysis, report, delivery. Questionnaire construction and repair,
instrument library, respondent engine, budget guard, checkpoint/resume.

**Status:** not started (Phase 5). Legacy source: `research_designer.py`,
`research_project.py`, `research_context.py`, `dotaznik.py`, `pipeline.py`,
`project_intake.py`, `instrument_library.py`, `analysis_agent.py`.

### Simulation

**Owns:** the 13-stage simulation lifecycle — baseline, scenario contract,
variants, worlds, frozen results, comparison, interpretation. Independent variant
modelling (never linear interpolation), scenario compilation and approval, the
scenario truth log.

**Status:** not started (Phase 7). Legacy source: `full_simulation.py`,
`scenario_compiler.py`, `simulation_batch.py`, `fullsim_learning.py`,
`simulation_context.py`, `scenario_truth_log.py`.

### Population & Audience

**Owns:** the calibrated synthetic population (18,766 rows × 400 columns), donor
fusion, same-person core, weighting contracts, audience registry and selection,
persona dimensions, calibration.

**Status:** version, import and consumption-readiness landed —
`aia_core.domain.population`, `aia_core.application.population.PopulationRuntime`
(content-addressed versions, STATIC/LIVE, operator-gated explicit promotion,
lossless import validation, canonical weight resolution, one loader, a binding
recorded per run, field policy as code, companion-set validation, the fail-closed
joint certificate). Consumer contract: [population.md](population.md). Sampling,
audience, donor fusion, calibration and the seven enrichment derivations (OI-7) are
not started. Legacy source: `population_context.py`,
`population_subpanels.py`, `donor_fusion.py`, `core_joint.py`,
`audience_registry.py`, `audience_dimensions.py`, `persona_grounded.py`,
`persona_calibration.py`, `dimension_catalog.py`, `mrp.py`,
`representative_sampling.py`.

**Invariant to preserve:** cross-block relationships are **not** same-person
truth. `DATA_CONTRACT_v17.json` sets `cross_block_same_person: false` and latent
cross-block claims fail closed.

### Analysis & Reporting

**Owns:** the eight durable analysis modules (executive, research questions,
objects, audience, segments, hypotheses, implications, limitations), deterministic
assembly, client and internal report variants, export packs.

**Status:** the eight modules are implemented in `aia_core.domain.analysis` —
identity, order, input fingerprints, the closed draft schema, the prose
number-coverage check, prompts rendered from the evidence enums, and a result
type that holds only admitted claims — and run one at a time by
`aia_core.application.analysis`. Reporting and export are **not started, by
design**: they come after the evidence layer is enforceable. Legacy source:
`analysis_agent.py`, `client_report_v2.py`, `final_client_report.py`,
`report.py`, `report_html.py`, `output_pack.py`, `segment_intelligence.py`.

**Invariant to preserve:** the eight modules are independently durable jobs, so a
quota failure after module 5 continues at module 6 instead of recomputing 1–5.

### Visualisation (Sociomapa)

**Owns:** relation matrices, unfolding and layout mathematics, map view state,
saved segments, A/B area comparison, what-if layers, object manager.

**Status:** core engine implemented — `aia_core.domain.sociomap`, specified in
[sociomapa-deterministic-engine.md](sociomapa-deterministic-engine.md): relation
transforms, declared layout, object metrics, both terrain fields, drag and
what-if layers. Not started: saved segments, A/B comparison, object manager,
dialogue. Legacy source: `sociomap.py`, `visualization_lab.py`,
`segment_orchestration.py`, `respondent_dialogue.py`, and the `*66` functions of
`ui_app.html`, which held the terrain mathematics.

**Invariant to preserve:** manual drag is a *visual override only and never
mutates raw results*; what-if is a scenario layer over immutable originals.
Position is relationship-derived and stays stable when the displayed metric
changes; height and colour are independently selectable.

### Data Library & Society Intelligence

**Owns:** source ingestion, text extraction, AI evidence proposals, human
approval, dimension materialisation, learning and calibration, LIVE population
revisions, the results registry, grounded question answering.

**Status:** not started (Phase 8). Legacy source: `data_library.py`,
`library_batch_import.py`, `library_system_catalog.py`, `society_insights.py`,
`ingest_automation.py`, `results_registry.py`.

**Invariant to preserve:** importing a source never overwrites the LIVE
population. The required order is
`ingest → parse → proposal → review/approve → materialize → validation → learning/calibration → new LIVE revision`,
and `STATIC` populations are immutable snapshots no learning step may modify in
place.

## Contexts the prototype had that we are not carrying forward

| Prototype area | Decision |
| --- | --- |
| Windows launcher and Python bootstrap (19 `.bat` files, `launcher_bootstrap.py`, `desktop_launcher.py`) | Drop. Replaced by containers and CI. |
| `prototype_server.py`, `research_arena.py`, `demo_showcase.py` dashboards | Drop. Superseded by the web client. |
| `legacy_job_dispatch.py`, `LEGACY_STAGE_MAP` | Drop after Phase 3. They exist only to keep pre-17.8 jobs running. |
| `anthropic_compat.py`, `spawn_env.py`, `system_fingerprint.py`, `portability_check.py` | Drop. Local-machine and SDK-version workarounds. |
| Several generations of release scorecards and acceptance manifests | Keep as reference documents only; not code. |

## Naming

The prototype uses Czech identifiers throughout (`dotaznik` = questionnaire,
`dispozice`, `navrh` = proposal, `kalibrace` = calibration, `vystupy` = outputs,
`osobnost` = personality, `biografie`). New code uses English identifiers, and
Czech is retained **only** in user-facing copy and in population column names,
where it is data rather than code. Stage display labels stay Czech because they
are product copy, and the parity suite asserts they are unchanged.
