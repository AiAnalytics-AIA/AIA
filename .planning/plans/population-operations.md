---
status: planned
chunks:
  - "[ ] P1. The operator's composition root: PopulationOperatorConfig typed and wired, an operator command over fictional fixtures"
  - "[ ] P2. A read-only population registry: versions, lineage, promotion history, on /app/intelligence"
  - "[ ] P3. A run records its population binding at creation, and population-consuming steps say so"
  - "[ ] P4. Contract (plan before code): how a materialized dimension becomes a new revision"
  - "[ ] P5. An explicit Promote action with a stale-pointer refusal"
---
# Population operations: the core's import and promotion reach a deployment

**Owner:** unassigned. **Written:** 2026-10-09, from `mvp-workflow-assurance.md` A2
(`develop @ c6ee438`). The population core was built under `done/population-version-foundation.md`
and `done/population-consumption-readiness.md`, both closed. `client-knowledge-lifecycle.md`
K5 owns knowledge-to-dimension definitions and materialization and *delegates* loading and
promotion to the existing authority; `sociomap-formula-corrections.md` I0/I1 specify the
run's frozen binding and its use in fieldwork and exclude "any population loader, dimension
materialization or LIVE promotion". Nobody owns the wiring between them. This plan does.

## What exists and where it stops (at `c6ee438`)

| Hop | State | Anchor |
|---|---|---|
| Import, establish, promote LIVE | EXISTS (core) | `application/population.py:345-412`; `domain/population/versions.py:298-425`; `infrastructure/population_repository.py:206-243`; `application/population_authority.py:53-82` |
| Any caller outside the core | ABSENT | `PopulationRuntime` / `PopulationAuthority` are referenced only in `application/` and `domain/population/` |
| Operator configuration at a composition root | ABSENT | `docs/architecture/population.md:105` |
| Asset source | Filesystem and memory only | `infrastructure/population_source.py:43-86` (the EU store is later) |
| A run's binding | Repository only | `infrastructure/workflow_repository.py:423-481`; no production start passes `population=` (`application/workflows.py:96-105`); no step sets `consumes_population=True` |
| An existing run keeps its older binding | Test only | `packages/aia_core/tests/test_population_runtime.py:640-670` |
| Fieldwork | A fictional roster | `apps/executors/src/aia_executors/ai_fieldwork.py:120-124` |
| Selecting a dimension cannot promote | Structural | `domain/research_design.py` `SpecSelection` (`applied: false`) |
| Registry screen | Notice | `apps/web/src/components/aia/GlobalPages.tsx:26-37` |

18.6.6 materialized a dimension and **approved its own calibration into LIVE**
(`legacy/npc-panel-18.6.6/app/data_library.py:621-626`). That is not ported: promotion here is
always a named person's explicit act through `PopulationAuthority`.

## Chunks

- **P1. Operator root.** `PopulationOperatorConfig` as a typed setting, empty by default, read
  at one composition root; an operator command (beside `seed.py`) wrapping `import_version`,
  `attach_companions`, `establish` and `promote_live` over the filesystem source, on fictional
  fixtures only. *Done when:* the command imports, establishes and promotes a fictional
  version, and refuses a person not in the operator configuration.
- **P2. Registry, read-only.** Versions, status, lineage, promotion history and companion state,
  through the API (scoped to the organization) and on `/app/intelligence` in place of its
  notice. No write.
- **P3. Binding at creation.** `ResearchRuns.start` resolves the selected population and
  records the binding; steps that read population data declare `consumes_population`.
  Fieldwork stays fictional and refuses rather than substituting a roster when a real binding
  is named. This wires I0's contract; I1 (selection applied to fieldwork) stays that plan's.
  *Done when:* the test at `test_population_runtime.py:640-670` becomes a connected proof
  through `ResearchRuns.start` and the real worker.
- **P4. Materialization contract (decision, no code).** With K5's dimension definition: does a
  materialized dimension become a child `DatasetVersion` (new hash, parent lineage, re-validated
  against a revised contract; the 400-field import contract is hash-pinned) or a versioned
  overlay? Where may materialization happen, given OI-61 and D8?
- **P5. Promote.** The explicit operator action with expected-current compare-and-set, its
  refusal when the pointer moved, and a test that a dimension selected in a design leaves
  `Population.current_version_id` unchanged.

P1-P3 can land before K2/K5; P4-P5 need K5.

## Blockers and decisions

- **OI-61** (licence determination): no panel-derived material reaches a model provider. It
  blocks real fieldwork on the panel, not import or promotion.
- **D8 / OI-24** (field-policy authority, 287 vs 115 eligible fields): one must be chosen
  before "eligible dimension" is decidable (P4).
- **OI-7** (enrichment derivations, archive-blocked); the 8 derived fields are unclassified
  (`population.md:102`); the archive release, EU asset source and first real import are the
  data owner's.
- An evidence-to-respondent derivation (18.6.6's prevalence/mean plus predictors,
  `data_library.py:583-592`) is a scientific rule; this plan does not invent one.
