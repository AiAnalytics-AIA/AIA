---
status: in-progress
chunks:
  - "[x] P1. The operator's composition root: PopulationOperatorConfig typed and wired, an operator command over fictional fixtures"
  - "[ ] P2. A read-only population registry: versions, lineage, promotion history, on /app/intelligence"
  - "[x] P3. A run records its population binding at creation, and population-consuming steps say so"
  - "[ ] P4. Contract (plan before code): how a materialized dimension becomes a new revision"
  - "[ ] P5. An explicit Promote action with a stale-pointer refusal"
  - "[ ] P6. Carry 18.6.6's v17 population into AIA on develop: its three versions, companions and field dictionary, STATIC v17_1_2 and LIVE v17_4_0"
  - "[ ] P7. Show the population's characteristics on Společenská inteligence: weights, blocks, each field's evidence status and permitted uses, no row"
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

## Progress

**P1, 2026-10-10** (`feature/population-operator-root`). `aia_executors.population_ops` is
the population core's one operator surface, beside `seed` and `legacy_workspace`:
`status` (versions, populations, history; acts as no one), `import`, `attach`, `establish`,
`promote` (`--to` and `--expected`, the core's compare-and-set). Every command but `status`
acts as an active AIA user (`--as <email>`) whom `AIA_POPULATION_OPERATORS` names: a JSON
object of verified user id to permissions, read by `operator_config` there and nowhere else,
unset or blank meaning nobody; a value that does not read (not JSON, not an object, not a
list, an empty id, an unknown permission) stops the command naming the key. Import, too,
needs a configured operator, though the core does not ask it: a version is platform data.
Bundles are read through `FilesystemPopulationSource` under `AIA_POPULATION_ASSET_ROOT` and
judged against the Czech contract (`CZ_SYNTHETIC_V17`); `run` takes another for tests. Each
command is one transaction; exit 2 is refused before anything is written, 3 is the
population's own refusal with its failures listed. Tests (`apps/executors/tests/
test_population_ops.py`, 15): a fictional four-version bundle on disk, imported, STATIC and
LIVE established, LIVE promoted, the history naming the operator by user id; nobody operates
until named; an unknown person; an operator without `POPULATION_PROMOTE` cannot move LIVE; a
stale `--expected` is `PromotionConflict` and LIVE stays; refused bytes register nothing; a
malformed companion; every malformed key; `main` without an asset root. **Not in P1:** the
develop host passes neither key to its containers (run with `docker compose run -e`), and the
first real import is the data owner's (`docs/architecture/population.md` § Not yet available).

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

## Progress (P3) and the 18.6.6 carry-over

**Decision (owner, 2026-10-10).** Once LIVE exists, every new research run records the LIVE
binding while fieldwork keeps answering with fictional respondents, labelled as such. Of the
three options put (record and stay fictional; record and refuse fieldwork until OI-61; record
only when a study opts in) the owner chose the first, so research keeps running on develop and
the record is in place for when panel fieldwork is allowed. The owner also asked that the data
and population characteristics be carried over from 18.6.6 (P6, P7).

**P3, 2026-10-11** (`feature/population-run-binding`). `application/population.py`
`live_binding` resolves a population as it stands (ANALYSIS view, the contract's default
weight) through a runtime whose asset source refuses every read: resolving reads the registry,
never a panel. It returns `None` only while the population is not established; any other
refusal raises, so a run never records a population it could not later load.
`ResearchRuns.start` records it through `start_workflow(population=)` only when it creates a
run: a start that finds its run names the binding that run recorded (so a run made before LIVE
existed, or before LIVE moved, is returned as before and `create_run`'s binding check holds),
and a retry keeps its original's, as it keeps its Sociomap methods. The run's metadata carries
`population` (id, version, label, `read_by_fieldwork: false`), the API returns it on the run,
and the run page says which version was recorded and that the respondents did not come from
it. No research step declares `consumes_population`; fieldwork is unchanged. `ResearchRuns`
takes the contract and population id as fields (the Czech contract and `CZ_LIVE` by default)
so the tests run over the fictional population. Tests:
`packages/aia_core/tests/test_research_population_binding.py` (6),
`apps/api/tests/test_research_api.py::test_a_run_says_which_population_it_recorded_and_that_fieldwork_did_not_read_it`,
`apps/web/src/lib/research-execution.test.ts` (`populationNote`, 3).

**P6, what the carry-over is.** 18.6.6's population is a synthetic model of the Czech adult
population (`legacy/npc-panel-18.6.6/app/DATA_CONTRACT_v17.json`, `CORE_JOINT_STATUS.json`):
a 2021 Census skeleton, a whole-person core from PIAAC 2023 (18-65) and ISSP 2022 (66+), and
constrained donor blocks; 18,766 rows x 400 fields in `v17_4_0`; four weights; the
400-field dictionary `FIELD_DICTIONARY_v17_1.csv` with each field's block, source, evidence
status, grade, recommended use and persona eligibility; 15 companion assets. AIA already pins
all of it in `domain/population/czech.py` (`CZ_SYNTHETIC_V17`). The bytes are licence-bound and
live in the EU ops bucket (`s3://$AIA_OPS_BUCKET/legacy-data/86b70bfb5c1b/`,
`legacy/npc-panel-18.6.6/AIA-INTEGRATION.md` section 4), listed with their hashes in
`data-manifest.json`; they are never in Git or an image. P6 needs: the develop host syncing the
population's files (three panels, the dictionary, the companions) from that prefix onto a
read-only path; Compose passing `AIA_POPULATION_OPERATORS` and `AIA_POPULATION_ASSET_ROOT` to
the worker; a runbook (`population_ops import` x3 with `--companion`, `establish` STATIC
`v17_1_2` and LIVE `v17_4_0`) run by a named operator. Importing is not blocked by OI-61 (no
model sees the panel), but it is the data owner's act on the develop host: the code and runbook
land in a PR, the run is the owner's.

**P7, what "characteristics" are.** What a researcher should see without any row: the four
weights and their meaning, the field blocks (provenance, population anchor, core, modelled
marketing priors, weights...), and for every field its evidence status and the uses its policy
permits (`RuntimePopulation.decide`), from the imported dictionary through the one loader. The
18.6.6 built-in subpanels (`BUILTIN_SUBPANELS_v17.json`, 18 views such as Mladí 18-29 or
Senioři 80+) are configuration, not part of the import contract; whether AIA adopts them is a
question for P7.

