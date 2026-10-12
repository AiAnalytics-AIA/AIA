---
status: in-progress
chunks:
  - "[x] P1. The operator's composition root: PopulationOperatorConfig typed and wired, an operator command over fictional fixtures"
  - "[x] P2. A read-only population registry: versions, lineage, promotion history, on /app/intelligence"
  - "[x] P3. A run records its population binding at creation, and population-consuming steps say so"
  - "[x] P4. Contract (plan before code): how a materialized dimension becomes a new revision"
  - "[x] P4a. Domain: a hash-pinned contract extension and an organization-owned child version"
  - "[x] P4b. 18.6.6's evidence derivation ported EXACT, from fixtures captured from the unit"
  - "[x] P4c. Storage: the child's owner and extension recorded; the registry shows it to its organization only"
  - "[x] P4d1. A population store in EU S3: a private bucket, an object written once and checked by hash, read by the one loader"
  - "[x] P4d2. The materialize service: a typed definition checked against K5's contract and the field policy, frozen to one run key per owner, base and definition"
  - "[x] P4d3. The materialize step: its template, executor and enqueue; the base loaded through PopulationRuntime, derived, the child written to S3 and registered; never promotes"
  - "[ ] P4d4. A researcher starts it and reads its outcome: the route, and target beside achieved on Společenská inteligence"
  - "[x] P4e1. The loader resolves and loads an owned child: base by its contract, child by its extension, the base's companions"
  - "[ ] P4e2. A study selects its organization's child; the run records that binding; another organization's run is refused"
  - "[ ] P5. An explicit Promote action with a stale-pointer refusal"
  - "[x] P6. The develop host can carry 18.6.6's v17 population: its files listed and pinned to the contract, a verified read-only sync, the worker's keys, the runbook"
  - "[x] P6b. The data owner imports it on develop: three versions with companions and dictionary, STATIC v17_1_2 and LIVE v17_4_0 (deploy/develop/README.md § The population)"
  - "[x] P7a. Keep each version's field dictionary with it (stored at import, hash-checked; a deploy step records it for versions imported before)"
  - "[x] P7b. Adopt 18.6.6's 18 built-in subpanels as AIA's catalogue, each checked against a version's dictionary"
  - "[x] P7c. A version's characteristics through the API: weights, blocks, every field's evidence and permitted uses, the subpanels; no row"
  - "[x] P7d. Show them on Společenská inteligence"
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
  `Population.current_version_id` unchanged. Shared versions only: an organization's
  materialized child is never promoted (P4, M5).

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
## Progress (P2)

**P2, 2026-10-10** (`feature/population-registry-view`). `GET /api/v1/population`
(`apps/api/src/aia_api/routers/population.py`): the Czech dataset's versions, each with
its status derived by the domain's `version_status` from the populations and their history
(never stored) and `runtime_eligible`, whether its companion set is attached, its lineage
parent and who imported it; the STATIC and LIVE populations; every promotion with actor
and reason. Any member reads it (`OrganizationDep`; ADR 0019), nothing unauthenticated,
and the route has no write method. Společenská inteligence shows it under its notice:
LIVE and the reference by label and short hash, the count of registered, unused versions,
every version with its status, and the history newest first (`lib/population.ts`
`summarize`, `labelOf`, `shortSha`). An empty registry says that research answers with
fictional respondents until an operator imports and establishes LIVE. The Data Library
stays `NOT_IN_AIA` in `interface-screens.json`: a registry is not intake. Tests:
`apps/api/tests/test_population_api.py` (4), `apps/web/src/lib/population.test.ts` (3).

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

**P6, 2026-10-11** (`feature/population-develop-carry-over`). What the host needs, in code;
the import itself is P6b, the data owner's.
`deploy/develop/population/v17.files` lists the 19 files by SHA256, size, origin and path:
three panels, the dictionary and 15 companions. `apps/executors/tests/
test_population_carry_over.py` holds that list equal to `CZ_SYNTHETIC_V17` (every known
version, the dictionary hash, every companion), to `data-manifest.json` for the 15 "bucket"
files, and to the frozen unit's bytes for the four "unit" files. Those four
(`CORE_JOINT_STATUS.json`, `PERSONA_VALUE_LABELS_v17.json`, `BUILTIN_SUBPANELS_v17.json`,
`SPECIAL_PANEL_REGISTRY_v17.json`) are companions the contract requires but the data bundle
does not carry. They are configuration in Git (`legacy/npc-panel-18.6.6/app/`), and the deploy
workflow copies them into the bundle beside the list.

`bin/sync-population.sh` (by hand) fetches the bucket files from
`AIA_POPULATION_SOURCE_PREFIX` and copies the unit files into a staging directory. It refuses
any size or hash that differs, and only then swaps the directory in, read-only, at
`AIA_POPULATION_DIR/v17`. It reads a key of its own, never the reference unit's
`AIA_LEGACY_DATA_PREFIX`, so the product stack still reads no `AIA_LEGACY_*` setting
(ADR 0018 decision 5).

Compose gives the worker alone `AIA_POPULATION_OPERATORS` (SSM) and
`AIA_POPULATION_ASSET_ROOT=/srv/population/v17` over a read-only mount. `bin/population.sh`
runs `population_ops` in a one-off worker container. `population_ops import` and `attach`
gain `--all-companions`: every companion the contract declares, at its asset id under the
root, in place of fifteen `--companion` pairs.

Measured: parsing a fictional panel of the real shape (18,766 x 400, 5.4 MB gzip) took
3.1 s and peaked at about 430 MB RSS, on a 4 GB host. Not measured: an import of the real
files, which this session cannot reach. A `3` from that import (the `v17_1_2` weight totals
were never measured by the reference, `czech.py` docstring) is a finding for this plan, not a
reason to loosen the contract.

Tests: `test_population_carry_over.py` (15) and `test_population_ops.py` (5 new,
`--all-companions`).

**P6b, 2026-10-11** (develop host, deployed `999be17`). The data owner signed in, and the
runbook's six steps were run as `USR-a97fa3d62eea4c`, each through SSM on `aia-develop`, with
every step's output read before the next.

- **Parameters:** `aia_population_source_prefix` = `legacy-data/86b70bfb5c1b` and
  `aia_population_operators` (that user, `POPULATION_ESTABLISH` + `POPULATION_PROMOTE`) were
  created, and `bin/write-env.sh` was run.
- **Backup:** `backups/aia-20261011T222511Z-pre-population.dump` (661,230 bytes).
- **Sync:** `bin/sync-population.sh` placed 19 files in `/opt/aia/population/v17`, each
  matching `population/v17.files`.
- **Imports:**
  - `v17_0_BASE`: `cz_synthetic_population@sha256:5300c1aeeef4ead1`, no companions, 8.9 s.
  - `v17_1_2`: `…@sha256:d6a9ef120b81982e`, with companions, parent `v17_0_BASE`.
  - `v17_4_0`: `…@sha256:864f8dbcd101e4be`, with companions, parent `v17_1_2`.
  - Every import exited 0. The contract's two weight totals, never measured on `v17_1_2` by
    the reference, held for it as well.
- **Establish:** `CZ_STATIC_REFERENCE` on `v17_1_2`, then `CZ_LIVE` on `v17_4_0`.
  `population_ops status` reads three versions (companions: no, yes, yes), both populations,
  and two history entries naming the operator.

From here every new research run on develop records `CZ_LIVE` / `v17_4_0`
(`read_by_fieldwork: false`). Runs made before keep what they recorded, which is nothing.
Fieldwork is unchanged.

**Findings:** none from the import. On how the run was done: the operator signed in as the
AWS account's root user, in an account that also runs other production systems. A role
limited to `ssm:SendCommand` on the develop instance and `ssm:PutParameter` under
`/aia/develop/` would be enough for the next import (a finding for the docs PR, not this plan).

**P7, what "characteristics" are.** What a researcher should see without any row: the four
weights and their meaning, the field blocks (provenance, population anchor, core, modelled
marketing priors, weights...), and for every field its evidence status and the uses its policy
permits (`RuntimePopulation.decide`), from the imported dictionary through the one loader. The
18.6.6 built-in subpanels (`BUILTIN_SUBPANELS_v17.json`, 18 views such as Mladí 18-29 or
Senioři 80+) are configuration, not part of the import contract; whether AIA adopts them is a
question for P7.

## P7, the design (2026-10-11)

**Decision (owner, 2026-10-11): AIA adopts 18.6.6's 18 built-in subpanels.**

**What the code has.** A field's block, source, evidence status, grade, recommended use and
description come only from the version's dictionary (`FIELD_DICTIONARY_v17_1.csv`). The
registry keeps only its hash and location (`tables.py` `PopulationDatasetVersionRow`), and the
policy exists only behind a full panel load (`application/population.py` `load`). The API has
no asset source, and `layer_check` forbids building field policy anywhere in `apps/`. The
subpanels file (`BUILTIN_SUBPANELS_v17.json`) is a companion the contract pins by hash
(`czech.py`), and it is in Git: 18 entries, each filtering on one field (`vek` 18-29 or an
`is_*` flag equal to 1), with 18.6.6's own row counts and donor support from `17.1.2`.

**Shape chosen.** The dictionary is a version's metadata, not a respondent row.

- **P7a.** `import_version` stores the dictionary's bytes in
  `population_version_dictionaries` beside the version, after the import has verified them.
  `population_ops record-dictionary` stores it for a version imported before. It reads
  `dictionary_location` under the asset root and stores the bytes only when they hash to the
  version's `dictionary_sha256`; it acts as no one, because it decides nothing. The develop
  deploy runs it once per version that lacks a dictionary, so the three versions already
  imported need nobody to sign in.
- **P7c.** `aia_core.application.population_characteristics` reads those stored bytes,
  re-hashes them against the version (refusing on a mismatch), parses them, and builds the
  policy with `build_field_policy`. It answers, per field: its block, source, evidence status
  and grade, recommended use and description, and `decide()` for every `FieldUse` (allowed,
  reason, obligations). It answers too for the contract's weights with their roles and
  totals, and for the block counts. The API only serialises it. Rejected alternative:
  mounting the population directory into the API, which would put every panel within the
  API's reach to show 84 KB of metadata.
- **P7b.** The 18 subpanels become AIA's own catalogue: a copy in `aia_core` that a test pins
  to the frozen unit's bytes and the contract's companion hash. Each subpanel is checked
  against a version's dictionary: its filter field exists, and its policy permits
  `AUDIENCE_FILTERING`; otherwise it is shown and marked not usable, with the reason.
  18.6.6's counts are shown as 18.6.6 measured them on `v17_1_2`; AIA computes none, because
  that would read rows.
- **Not in P7:** applying a subpanel to a study's audience. The selection is recorded, not
  applied (OI-91), until panel fieldwork exists.

**P7, 2026-10-12** (`feature/population-characteristics`).

- **P7a.** `population_version_dictionaries` (migration `d6f8a0c2e4b6`) keeps a version's
  dictionary bytes, insert-once. `import_version` writes them after verifying them.
  `PopulationRuntime.record_dictionary` stores the file at the version's own
  `dictionary_location` only when it hashes to `dictionary_sha256`, never reads the panel,
  and acts as no one (`population_ops record-dictionary`). The develop deploy runs it after
  replacing services; a refusal warns and does not fail the deploy.
- **P7b.** `domain/population/subpanels.py` is the catalogue. It is held equal, field by
  field, to `BUILTIN_SUBPANELS_v17.json`, whose hash the contract pins.
  `check_subpanel` asks the version's policy for `AUDIENCE_FILTERING`. The counts are
  `UnitMeasurement`: 18.6.6's, on `17.1.2`.
- **P7c.** `application/population_characteristics.py` re-hashes the kept bytes and builds
  the policy as `load()` does. `GET /api/v1/population/versions/{id}/characteristics`
  answers with the weights, blocks, every field and its seven `FieldUse` answers, and the
  subpanels. A version without its dictionary answers `dictionary_kept: false` with every
  subpanel unknown; a mismatch is a 409.
- **P7d.** Společenská inteligence opens on LIVE, and can switch versions. It shows the
  weights with their declared totals, the blocks, the 18 subpanels (usable, not usable with
  the reason, or unknown, with 18.6.6's counts said as 18.6.6's), and every field: searchable,
  filterable by block, with each use allowed or refused, why, and its obligations.

Tests:
- `packages/aia_core/tests/test_population_dictionary_kept.py` (4),
  `test_population_subpanels.py` (10), `test_population_characteristics.py` (6);
- `apps/executors/tests/test_population_ops.py` (+2) and `test_population_carry_over.py`
  (+1);
- `apps/api/tests/test_population_api.py` (+4);
- `apps/web/src/lib/population.test.ts` (+5) and
  `src/components/aia/PopulationCharacteristics.test.tsx` (3).

Verified: `alembic upgrade / check / downgrade / upgrade` on PostgreSQL 16, and `next build`.

**Not seen yet:** the real `v17_4_0` dictionary on the page. Which of the 18 subpanels its
policy lets filter (the `is_*` flags' recommended use) is first known after the deploy
records the dictionaries. Until then the claim "usable" is the test's, on fictional rows.


## P4, the materialization contract (draft for the owner, 2026-10-12, `develop @ c1c8ec1e`)

P4 decides, before any code, how an accepted dimension becomes respondent values in a population
revision. It writes no code. K5 (`client-knowledge-lifecycle.md`) owns the *definition* of a
dimension and the journey to it; this contract is what K5's output must satisfy and what the
population core does with it. Promotion stays P5's explicit act.

### What 18.6.6 did (the reference, read, not run)

`data_library.py:576-593` `dimension_materialization_readiness`: an approved proposal whose spec
names a kind (`binary`/`prevalence` with `target_prevalence`, or `scale_1_10` with
`target_mean`) and at least one existing predictor. `audience_dimensions.py:308-345`
`materialize_evidence_dimension`: scores every panel row from the numeric predictors, then
(binary) marks the top-scored rows until the weighted share reaches the target, or (scale)
maps score ranks to 1-10 and shifts them to the target mean; it writes a
`panel_row_id -> value` overlay (`<id>.csv.gz`) with its SHA256. `data_library.py:595-626`
`materialize_dimension` then **proposes and approves its own calibration into LIVE in the same
call** (`propose_calibration` + `decide_calibration(..., 'APPROVE')` + `register_applied_overlay`).
That last step is not ported (this plan, "What exists").

### The four decisions

**M1. Shape: a child version, or an overlay?**
- *(a) Child `DatasetVersion` (recommended).* The materialized panel is the base's bytes plus one
  column, stored as a new content-addressed version whose `parent_version_id` is the base
  (`domain/population/versions.py:135-180`). Every existing rule holds unchanged: a run binds one
  `version_id` (P3), `PopulationRuntime.load_for_run` stays the only loader
  (`application/population.py:494`), LIVE moves only by promotion, and STATIC is untouched.
  Cost: the import contract is pinned to 400 fields by hash (`domain/population/czech.py:202-207`),
  so a child needs a **contract extension**: the base contract plus the declared added fields,
  itself hash-pinned and naming the dimension definition's hash. One full panel per
  materialization (the v17 panel is 18,766 rows).
- *(b) Versioned overlay.* 18.6.6's shape: a small `panel_row_id -> value` artifact bound to one
  base version. Cheaper to store, but a run's binding becomes "base + an ordered set of
  overlays", and the one loader, `decide` / `decide_joint` and the companions' joint certificate
  all have to learn to merge it. That spreads one rule across the gates this codebase keeps
  single.

**M2. The derivation rule.** Turning evidence (a prevalence or a mean, with a source) into
per-respondent values is a scientific rule, and this plan does not invent one.
- *(a) Port 18.6.6's rule EXACTLY as the first declared method (recommended)*, captured as
  fixtures from the unit's own function (as `tools/sampling_capture.py` does), with a method id
  and version recorded in the child version's provenance. Every value it writes is **modelled**:
  `ClaimBasis.MODELED` (`domain/evidence/claims.py:67-71`), never measured.
- *(b) No derivation yet.* Only a dimension whose values already exist per respondent (a
  measured column joined by `panel_row_id`) may be materialized; evidence-anchored dimensions
  wait for an approved method.

**M3. What the new field may be used for (the D8 / OI-24 question).** Two field-policy
authorities still disagree (`domain.evidence` vs `domain.population`). P4 does not need D8 to be
resolved if a materialized field's policy is fixed and narrow:
- *(a) Recommended:* `PERSONA_CONSTRUCTION`, `AUDIENCE_FILTERING` and `SIMULATION`
  (`domain/population/policy.py:120-129`); `CLIENT_MODELLED_CLAIM` only with its method
  disclosed; **never** `CLIENT_MEASURED_CLAIM` or `WEIGHTING`. The extension declares this policy,
  and the D8 decision, when it is made, adopts it rather than reopening it.
- *(b)* Decide D8 first, then let that one authority classify materialized fields.

**M4. Who materializes, and where.** Materialization is code over the population's rows, with
no model call, so OI-61 (closed 2026-10-12: panel data may reach only `bedrock-eu-primary`)
does not block it. It reads rows, so it goes through `PopulationRuntime` like every other reader.
- *(a) Recommended:* an operator act first, `population_ops materialize` beside `import` and
  `promote` (P1), as a person `AIA_POPULATION_OPERATORS` names and holding a new
  `POPULATION_MATERIALIZE` permission. It registers the child version; it never promotes. A
  research or client user's acceptance of a dimension (K5) makes it *eligible* to be
  materialized, never materialized.
- *(b)* A worker step any researcher can start from the knowledge area, with the operator's
  role only at promotion.

### What the contract requires of K5's output

A dimension definition, hash-identified and immutable, carrying:
- the id and version, construct and label;
- the kind (`binary` or `scale_1_10` under M2a);
- the target anchor, with the accepted evidence reference (source revision and span) it came from;
- the predictors: existing fields of the base version, each one the field policy allows for
  `PERSONA_CONSTRUCTION`;
- the missingness rule and the valid range.

A definition alone has no respondent values (K1's table, `client-knowledge-lifecycle.md:83-84`).

### What it does not change

- Selecting a dimension in a design still promotes nothing (`SpecSelection`, `applied: false`).
- An existing run keeps its binding (P3).
- STATIC is never a child's target.
- P5's compare-and-set promotion is unchanged.

### Decisions (owner, 2026-10-12)

| | Decision | Consequence |
|---|---|---|
| M1 | **(a) child `DatasetVersion`** | one binding shape and one loader; a contract extension per child |
| M2 | **(a) port 18.6.6's rule EXACT** | fixtures from the unit's own `materialize_evidence_dimension`; every value MODELED, the method recorded |
| M3 | **(a) narrow, fixed uses** | `PERSONA_CONSTRUCTION`, `AUDIENCE_FILTERING`, `SIMULATION`; `CLIENT_MODELLED_CLAIM` with the method disclosed; never `CLIENT_MEASURED_CLAIM` or `WEIGHTING`; D8 adopts this rather than reopening it |
| M4 | **(b) any researcher** | a worker step a member starts (ADR 0019: every member is a Researcher); no new operator permission; promotion is not part of it |
| M5 | **its organization only** (asked once M4 was chosen) | see below |

**M5, why it was asked.** Population versions carry no organization: the registry reads them
as "the shared layer every study is…" (`apps/api/src/aia_api/routers/population.py:6, 96`),
and the tables have no `organization_id` (`infrastructure/tables.py:1362-1445`). With M4 (b),
one organization's client-derived dimension would otherwise appear in every organization's
registry, and a promotion would move every organization's LIVE. So a child version:
- records the organization and client it was materialized for, and the definition it came from;
- is visible in the registry, and its characteristics are readable, only within that
  organization;
- may be bound only by that organization's runs, and only when a study selects it explicitly;
- is never the target of a promotion: STATIC and LIVE stay shared, and P5's promotion applies
  to shared versions only.

### Implementation chunks (from the decisions)

- **P4a. Domain.** `PopulationContractExtension`: the base contract's id, the added fields with
  their kind and the M3 policy, and the definition's hash, all hash-pinned. A child
  `DatasetVersion` names its extension and its owner. Pure validation: a child's parent is the
  extension's base, its fields are the base's plus the declared ones, and it can be no
  promotion's target.
- **P4b. The derivation.**
  - `tools/materialize_capture.py` captures fixtures from the unit's own
    `audience_dimensions.materialize_evidence_dimension` over fictional rows (`inputs` in the
    repo env, `capture` with pandas and NumPy), byte-identical on re-capture.
  - A stdlib port in `domain/population/` reproduces them: binary prevalence by weighted cut,
    and `scale_1_10` by rank and shift.
  - It records the method id and version, the target and the achieved anchor. It is EXACT
    against the fixtures, or each deviation is named.
- **P4c. Storage.**
  - A migration adds the owner and the extension to `population_dataset_versions`, with an
    extension table, insert-once.
  - `GET /population` and `…/characteristics` show a child only to its organization.
  - `layer_check` keeps the rows in the repository.
- **P4d. Materialize.**
  - An application service and a worker step started through the API by a member, from an
    eligible definition. Until K5 lands, the definition is typed input, refused unless it meets
    "What the contract requires of K5's output".
  - The step reads the base through `PopulationRuntime`, writes the child's bytes to the
    population asset store and registers the child.
  - It never promotes.
- **P4e. Bind.**
  - A study may select its organization's child.
  - `ResearchRuns.start` records that binding instead of LIVE; a found run keeps what it
    recorded, and a retry keeps the original's (P3).
  - Another organization's study is refused (404, like any scope miss).

K5 still owns the knowledge-side definition and its acceptance. P4d accepts a typed definition
so the population side can land and be tested first, and K5 then supplies that same shape.

**P4a, 2026-10-12** (`feature/population-child-versions`). `domain/population/versions.py`
`VersionOwner` (organization and client) and `DatasetVersion.owner` / `extension_sha256`, both or
neither, an owned version always a child; `plan_establish` and `plan_promotion` refuse an owned
version (`OwnedVersionNotShared`, reason `owned_version`), so STATIC and LIVE stay shared.
`domain/population/materialized.py`: `MaterializedField` (name, `binary` / `scale_1_10`, the
definition's hash, the method and its version), `PopulationContractExtension` (the base
contract, its ordered field names and dictionary by hash, the added fields; its identity the
SHA256 of its canonical JSON, `from_payload` refusing any other contract), `field_names` (the
base's in order, then the added; a shadowing name refused), `materialized_policy_entry` (M3 as
one policy entry: `MODELLED`, persona-eligible, `PERSON_VALUE_MODELED` +
`REQUIRES_MODELED_DISCLOSURE`, `MODELLED_AGGREGATE`; so `FieldPolicy.decide` allows persona,
audience, simulation and internal aggregate analysis, a disclosed aggregate modelled claim, and
refuses a measured claim and weighting), `with_materialized_fields`, and `check_child_version`
(owned, the base shared and its parent, same dataset, contract, dictionary and rows, the
extension by hash, the fields the base's followed by the added ones). Internal aggregate
analysis follows from the existing rules for any classified field; M3's list did not name it.
Tests: `test_population_materialized.py` (16); the guard in `plan_promotion` and the parent
check each fail a test when removed (checked by mutation).

**P4b, 2026-10-12** (`feature/population-materialize-derivation`). `tools/materialize_capture.py`
writes 160 fictional rows and 14 cases (`inputs`), and runs the unit's own, unmodified
`audience_dimensions.materialize_evidence_dimension` on each (`capture`, pandas 2.3.3 and
NumPy 2.5.4 in a scratch venv). A second capture was byte-identical. The cases cover:
- binary to a prevalence, including one given as a percentage;
- scale to a mean, including one the clip pulls off target;
- a negative direction, `strength` / `weight`, and a `strength` of 0 read as 1;
- a flat predictor skipped; a text column unusable; missing values and zero weights;
- six refusals.

`domain/population/derivation.py` is the stdlib port, `derive_dimension`, with method
`npc-18.6.6-evidence-overlay` v1:
- the score is the mean of `direction * strength * z` plus `0.35 * (hash noise - 0.5)`;
- binary values are a weighted cut in descending score;
- scale values are `1 + 9 * percentile rank`, shifted, clipped and rounded to two decimals.

Every value, and every achieved anchor, is **bit-identical** to the unit's. That needs NumPy's
pairwise summation and pandas' two-pass variance (with a plain left-to-right sum, 7 of the 8
value cases fail; checked by mutation), and NumPy's `rint` rounding.

**One named deviation:** where no usable predictor varies, the unit writes values from the
hash noise alone (fixture M06). `derive_dimension` refuses that (`no_varying_predictor`);
`derive_dimension_as_unit` keeps the unit's behaviour, for the parity tests only.

**Noted for P4d:** a scale target can be left unmet by the clip (M04: target 2.0, achieved
2.68). The unit accepts that silently. P4d must show `achieved` beside `target`, and must
not present the target as met.

Tests: `test_population_derivation.py` (17).

The parity matrix's `data_library.ingestion` and `audience.definition` stay `NOT_STARTED`. The
fixture gate joins them when materialization lands as a capability (Doc follow-up).

**P4c, 2026-10-12** (`feature/population-child-storage`).

*Identity, found while writing the schema.* A version's id was its content alone
(`dataset_version_id`) and `content_sha256` was unique over the whole table. The derivation is
deterministic, so two clients materializing the same definition over the same base write the
same bytes: the second child would have collided with the first, and the constraint error
would have told one organization that another had made it. An owned child's id is now its
content id qualified by an opaque owner digest (`owned_version_id`, `versions.py`, 48 bits of
SHA256 over organization and client; neither appears in clear), and `DatasetVersion` checks it.
Content and label stay unique among shared versions and within one owner's, by four partial
unique indexes; the same owner's same bytes are still one version. Test:
`test_two_clients_identical_children_are_two_versions`.

*Storage.* Migration `f0b2d4e6a8c1`:
- `population_dataset_versions` gains `owner_organization_id`, `owner_client_id` and
  `extension_sha256`, all set or all NULL, an owned version always with a parent
  (`population_version_owned_child`); foreign keys to organizations, clients and the
  extension, none cascading;
- `population_contract_extensions` keeps each extension by its hash, insert-once; the
  repository re-hashes the payload on every read and refuses one that no longer matches;
- every existing row is shared and keeps both uniqueness guarantees.
Applied, `alembic check` clean, downgrade to base and up again, on PostgreSQL 16.

*Visibility.* `PopulationRegistryRepository`:
- `versions(dataset, organization_id=)`: shared versions, plus only that organization's own
  (none without one);
- `visible_version`: another organization's child answers `None`, as an unknown id does;
- `version_by_sha` and `version_by_label`, the import's lookups, see shared versions alone;
- `get_version` stays unfiltered, for the run that recorded a version and the operator.

`GET /population` lists the organization's own children with `owner_client_id` and
`extension_sha256`. `…/characteristics` answers 404 for another organization's child. For
the organization's own child it reads the base's dictionary (from the child's row or else
its parent's, re-hashed either way) and lists the added fields last, marked `materialized`,
under the fixed M3 policy. `PopulationRuntime.establish` and `promote_live` refuse an owned
child first (`OwnedVersionNotShared`), before companions or lineage are checked.

`layer_check` adds six rules:
- the version and extension tables are touched only by their repository (four rules: core,
  API, worker, executors);
- the API never calls `get_version`, `version_by_sha` or `version_by_label`;
- `population_characteristics.py` never calls `get_version`.
The first and fifth were checked by mutation.

Tests:
- `test_population_owned_versions.py` (10): round trip, two owners, labels, visibility,
  half-owned rows refused by the database, a tampered extension, characteristics, the operator;
- `test_population_api.py`: two new tests, our child listed and readable, another
  organization's never.
Mutation: listing every owned version fails two of them.

**Noted for P4d / P4e:**
- `population_ops status` reads shared versions only.
- A child's status derives as `REGISTERED`, not runtime-eligible, because no population
  points at it. P4e decides how a study's explicit selection makes it resolvable.
- `owner_client_id` is not tied to `owner_organization_id` by the database: `clients` has no
  `(organization_id, client_id)` key to reference. P4d takes both from one `ClientContext`.

### P4d, the plan (owner, 2026-10-12: the child's bytes go to S3)

P4d is where a researcher materializes a dimension. P4a gave the shape, P4b the rule and P4c the
rows; nothing yet runs them. The owner chose S3 for the child's bytes. Today the population is
a read-only copy synced to the develop host (`deploy/develop/bin/sync-population.sh`), and
`PopulationAssetSource` only reads: its own docstring names the EU object store as "the seam
this protocol exists for", not written because the bucket was undecided
(`infrastructure/population_source.py:1-18 @ 06409e04`).

**P4d1. The population store.**
- Terraform, `infra/develop/`: a population bucket of its own, separate from the artifacts
  bucket because it holds licence-bound data with its own access. It is in the develop
  region, private (public access blocked), versioned, encrypted, TLS only, like the two
  existing buckets (`infra/develop/main.tf:97-150 @ 06409e04`). The host's one instance role
  (the API and the worker share it on develop) may get and put under `materialized/`, never
  delete; only the worker container is given the store's settings.
- `S3PopulationStore` (infrastructure): `read(location)` for the loader, and `put_once(key,
  bytes, sha256)`. `put_once` writes only when the key is absent (a conditional put); an
  existing object with the same hash is the same child, and a different one is refused.
- A composing source: an `s3://` location reads from the store, a relative one from the host's
  synced directory, so shared versions are unchanged. `AIA_POPULATION_STORE_*` settings are
  typed and fail closed; nothing is read or written when they are unset.
- Tests over a recorded S3 double. **Human action:** `terraform apply`, and the worker's
  environment on the develop host.

**P4d2. The materialize service** (application).
- Input: a typed definition (until K5 supplies the same shape) and the `ClientContext` it is
  for. The owner is that context's organization and client; never an argument.
- Refused before anything is enqueued:
  - unless it meets "What the contract requires of K5's output" (kind, target with its
    evidence reference, predictors, the missingness rule and the valid range);
  - for each predictor, unless the base version's policy allows `PERSONA_CONSTRUCTION`
    (`RuntimePopulation.decide`, never the dictionary);
  - for a name that would shadow a base field.
- The base is the LIVE version at the time of the request, recorded; it is never re-chosen on
  a retry.
- Enqueued once: the run key is the owner, the base and the definition's hash. The same
  request again finds the same run.

**P4d3. The materialize step** (executor, through the real worker).
- It loads the base through `PopulationRuntime.load_for_run` (the one loader), runs
  `derive_dimension` (P4b; `no_varying_predictor` refuses), and writes the child panel. The
  child is the base's rows and columns in order plus the new one, gzip CSV with fixed bytes,
  so the same inputs give the same hash.
- `put_once` to S3, then the extension, the child version and its dictionary row in one
  transaction, after `check_child_version`. A retry after the put finds the object and
  registers; a retry after registration finds the version (P4c's owner-qualified id).
- It records `target`, `achieved` and the usable predictors. It never promotes.
- No model call and no money. Before it merges, measure the panel's size, the step's time and
  its memory on the v17 shape.

**P4d4. The route and the screen.**
- A route under the client starts it and reads its run.
- Společenská inteligence shows the organization's children with each one's target beside
  what was achieved: a scale target the clip left unmet (P4b's M04: 2.0 asked, 2.68 achieved)
  says so, never "met".

**Open before P4d1:** the bucket's exact name and the worker role's policy are written in
Terraform; who applies it is the human action above.

**P4d1, 2026-10-12** (`feature/population-store`, stacked on P4c).
- `infrastructure/population_store.py`:
  - `S3PopulationStore.put_once` is a conditional put (`IfNoneMatch="*"`, SSE-S3, the
    SHA256 in the object's metadata). The same bytes already at the key answer as written (a
    retried step); other bytes are `PopulationStoreConflict` and the object is never
    replaced. `read` takes only a location under this bucket's `materialized/`.
  - `RoutingPopulationSource`: `s3://` from the store, anything else from the shared
    source, so shared versions read as before. A child's location with no store configured
    is `PopulationAssetMissing`, never a substitute.
  - `PopulationStoreSettings.from_env`: `AIA_POPULATION_STORE_BUCKET` and `…_REGION`, both or
    neither.
  - Tests: `test_population_store.py` (6), over a stand-in client with S3's conditional-put
    and missing-key errors.
- Terraform, `infra/develop/main.tf`:
  - the bucket `aia-develop-population-<account>`, without `force_destroy`, with the shared
    public-access, versioning, SSE and TLS-only rules;
  - two `MaterializedPopulation` statements on the instance role;
  - SSM `aia_population_store_bucket` and `aia_population_store_region` as a resource of
    their own. As keys of the `config` map, planning them planned the Google identity
    provider too, because that map carries the Cognito ids.
- Compose passes both keys to the worker only.
- Nothing composes the store yet; P4d3 gives it to the materialize step's loader.

**How the plan was made, and what it does not cover.** The real `terraform.tfvars` is not in
the repository, and copying the Google client secret out of the state was refused. So the
plan is targeted at the eight new resources and the instance policy, with placeholders for
the variables none of them reads. `terraform plan -target=…`: 8 to add, 1 to change (the
instance policy), 0 to destroy; Cognito untouched. An untargeted plan needs the owner's
tfvars.

**P4d1 applied, 2026-10-12** (owner's go-ahead). The targeted plan above was applied: 8 added,
1 changed, 0 destroyed, and nothing else in the account. Write-once was then proved against the
real bucket `aia-develop-population-<account>` through `S3PopulationStore` itself:
- a first write stored the object;
- the same bytes again answered as written;
- different bytes were refused (`PopulationStoreConflict`), and one object version remained;
- reading back through `RoutingPopulationSource` returned the original bytes;
- SSE `AES256`, with the SHA256 in the object's metadata; public access fully blocked;
  versioning enabled.

The proof object was deleted afterwards. The worker receives the two settings on the first
deploy after #334 merges; nothing reads or writes the store until P4d3.

**P4d2, 2026-10-12** (`feature/population-materialize-request`, stacked on P4d1).

*Decision (owner, 2026-10-12): a materialize run lives under a study.* Every workflow run
belongs to a study and its project (`workflow_runs.study_id`, `project_id`; `infrastructure/
tables.py:877-881 @ e6c176f1`), and the worker's scope, lease and budget hang off it. A
researcher asks from a study of the client the dimension is for. The run lives under that
study and is charged to its budget; the child is still the client's (M5), usable by all of its
studies. Client-level runs were the alternative, and were not taken.

*Enqueue moved to P4d3.* `domain/workflow_templates.py` adds no step without an executor,
because a step no worker can claim would leave its run "running" forever. So the template,
the executor and the enqueue land together in P4d3; P4d2 is the checks and the frozen
request.

What landed:
- `domain/population/definition.py`: `DimensionDefinition`, the K5 contract as a type.
  - Fields: the id (a field name), version, construct, label, kind, target, the
    `EvidenceAnchor` (knowledge item, revision, span), the predictors, `MissingnessRule`
    (`PREDICTOR_MEAN`, 18.6.6's z = 0) and the valid range, which must be the kind's.
  - Its identity is the SHA256 of its canonical JSON; `from_payload` refuses any other
    contract. `evidence_spec()` is what P4b's derivation takes.
  - A strength of 0, which 18.6.6 read as 1, is refused in a typed definition.
- `application/materialize.py`: `prepare_materialization(session, StudyContext, definition)`
  refuses, by name, before anything is enqueued:
  - `ScopeDenied`: the scope may not run work, or the study is closed;
  - `population_not_established` and `base_not_shared`;
  - `dictionary_not_kept`;
  - `name_taken`: the dimension's name is already a field of the base;
  - `predictor_unknown` and `predictor_not_permitted`: the base's policy does not allow
    `PERSONA_CONSTRUCTION`.
  
  The checks build the policy the loader builds, from the kept dictionary
  (`population_characteristics.shared_version_policy`, now shared with the characteristics
  page); no respondent row is read.
- `MaterializationRequest`:
  - The owner is the scope's organization and client, never an argument. The base is LIVE
    as it stood, and the definition is held by its hash.
  - `idempotency_key` is the owner, the base and the definition, so the same request from
    any of the client's studies finds one run.
  - `step_input()` is everything the step needs and nothing it could re-choose.
- Tests: `test_population_materialize_request.py` (14). Dropping the predictor's policy check
  fails one; dropping the client from the run key fails one (both checked by mutation).

**P4d3, 2026-10-12** (`feature/population-materialize-step`, stacked on P4d2).

- **The template:** `workflow_templates.POPULATION_MATERIALIZE` is one step, `materialize`, of
  kind `population_materialize`. It is `consumes_population`, so no run is made without the
  binding it records, and it has 3 attempts.
- **The enqueue:** `application/materialize.start_materialization` refuses a request from
  another study, then starts the run under the study's population project
  (`projects.owner = study_population`, `MATERIALIZE_PROJECT_OWNER`, created on first use; no
  generic route sees it). LIVE's binding is the run's population.
  - *A key split, found while wiring it:* a run's idempotency key is unique across every study
    but looked up within one (`workflow_repository.py:444-451 @ 09a94e53`). P4d2's one key
    (owner, base, definition) would have made a sibling study's request collide on insert.
    The request now has `child_key` (owner, base, definition: the one child) and
    `idempotency_key` (that, within the study).
  - The child is still made once: its owner-qualified id and the write-once store
    deduplicate it.
- **The work:** `PopulationRuntime.materialize_child`, inside the one loader (`parse_panel` is
  allowed only there, `tools/layer_check.sh`):
  - the base is verified as every load is, and must be shared;
  - every predictor is asked again of its policy (`PERSONA_CONSTRUCTION`), and the name must
    be free;
  - predictors and the weight are read as numbers the way pandas read them
    (`derivation.numeric_column`), and P4b's `derive_dimension` writes the values;
  - the child is the base's columns in order plus the new one: `population_parser.write_panel`
    gives deterministic gzip CSV, binary as `0`/`1`, scale with two decimals;
  - it is `put_once` to the store under `<dataset>/<sha256>.csv.gz`, then
    `check_child_version`, then the extension and the version are registered. The validation
    record holds the target, the achieved value and the usable predictors.
  - A retry finds the version; another client gets its own version over the same object.
- **The executor:** `aia_executors/materialize.py` checks that the definition is the requested
  hash, the owner is the study's client, and the base is the binding the run recorded, then
  calls the runtime.
  - Without a population store or `AIA_POPULATION_ASSET_ROOT`, the run parks
    (`RUNTIME_UNAVAILABLE`, `population_store_unconfigured`) and nothing is written.
  - A request the data does not support is `SCHEMA_VIOLATION`, by name, and never retried.
  - Registered in `registry_for`; `materialize_executor(env)` composes it from the
    environment.
- **Tests:**
  - `test_population_materialize_child.py` (5, on SQLite and PostgreSQL): bytes read back as
    base plus column, values equal to P4b's derivation, retry, second client, scale format,
    refusals before any write, an owned base refused;
  - `test_materialize_executor.py` (2): a run under the real worker loop registers the child;
    with no store it parks and nothing is written;
  - `test_population_materialize_request.py` updated for the split keys.
- **Measured, on a fictional panel of the v17 shape** (18,766 rows by 400 columns, 6.7 MB
  gzip; three predictors, scale kind): `materialize_child` took 4.6 s and the process peaked at
  315 MB RSS (226 MB traced); the child is 6.8 MB. The worker container has no memory limit, on
  a 4 GB host. No model call, no money.

**Finding for P4e (reproduced).** The loader refuses a child. `_verified_panel` re-applies
the *base* contract to every panel it loads (`application/population.py`, `validate_import`),
and a child has one more column than the contract declares.
- Reproduced by calling `PopulationRuntime._verified_panel(child.version)` on a child made
  in `test_population_materialize_child.py`'s fixture: `VersionIntegrityError ... schema.
  column_count: expected 6 columns; panel has 7`.
- Consequence: no run can yet load a child, which P4e needs.
- Smallest fix: when loading an owned child, validate the base's columns against the base
  contract and the added ones against the stored extension (`check_child_version`'s rule),
  rather than the base contract alone. The policy then becomes `with_materialized_fields`.
- Test that would catch it: a P4e test that loads a child through `load()` and reads its
  added field through `RuntimePopulation.decide`.

**P4e1, 2026-10-12** (`feature/population-load-child`, stacked on P4d3). It closes P4d3's
finding: the loader refused a child.
- `PopulationRuntime.resolve_child(version_id, organization_id=)` resolves only that
  organization's own child; any other id answers as unknown, as does a shared one. A child is
  never a population's version, so it is eligible when its shared base is runtime-eligible and
  usable. The binding pins the child (`PINNED`, no population), and its companion set and joint
  state are the base's.
- `load()` of an owned child goes through `_verified_child`:
  - the base is read and verified by its own contract, as any load;
  - the child's bytes must hash to their pin, and `check_child_version` must hold;
  - every base column must be the base's cell for cell;
  - every added cell must be a value its kind holds (binary `0`/`1`, a scale in [1, 10]).
  
  The policy is the base's plus `with_materialized_fields`. The certificate is evaluated
  against the base panel's hash, which the cell-for-cell check makes sound
  (`_joint_version`).
- Tests: `test_population_load_child.py` (3, on SQLite and PostgreSQL):
  - a child resolves pinned and loads, its added field answers `decide` with the M3 policy, and
    its base fields equal LIVE's;
  - another organization's child, or a shared version, is unknown;
  - an added value its kind cannot hold, a base column not the base's, or bytes that moved are
    each refused. Dropping the base-column comparison fails the test (checked by mutation).
- Measured on the v17-shape fictional panel: verifying a child's load took 3.5 s (the base
  and the child are each parsed once), at 393 MB peak RSS in the measuring process. The
  loader's cache keeps a loaded child for later steps of the same run.

P4e2 is what remains: the research start names a selected child instead of LIVE, records its
binding, and refuses another organization's.

