# Population — the consumer contract

**Status:** foundation and consumption-readiness implemented
(`aia_core.domain.population`, `aia_core.application.population`). Owner:
population-data. This is the contract the research engine (A4), simulation and
Sociomapping consume; anything they need that is not here is a request to
population-data, not something to resolve locally.

## The one rule

**A run reads the population it recorded, through the one loader, and asks the
population what each field may be used for.** No consumer resolves a version,
chooses a weight, parses a panel, reads the field dictionary or reads the joint
certificate itself. `make layer_check` refuses a second loader and a forged
`RuntimePopulation`.

## The sequence

```python
from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    CZ_LIVE, CZ_SYNTHETIC_V17, FieldUse, PopulationSelector, PopulationView,
)
from aia_core.domain.population.enrichment import AudienceDimensionsEnricher

runtime = PopulationRuntime(session, contract=CZ_SYNTHETIC_V17, source=asset_source,
                            enricher=AudienceDimensionsEnricher())

# 1. When the run is created -- once.
binding = runtime.resolve(PopulationSelector.population(CZ_LIVE),
                          view=PopulationView.ANALYSIS)  # weight_role=None -> contract default
run_id = workflow.create_run(..., steps=[StepDefinition(..., consumes_population=True)],
                             population=binding)

# 2. In every step that reads respondents.
population = runtime.load_for_run(workflow, run_id)

# 3. Before a field is used, and before fields are combined.
population.decide("vek", FieldUse.CLIENT_MEASURED_CLAIM)       # -> UsageDecision
population.field_policy.require("vek", FieldUse.AGGREGATE_ANALYSIS)  # obligations or raise
population.decide_joint(["vek", "pohlavi"], client_facing=True)       # -> JointDecision
population.analysis_weight                                    # the resolved column, exactly
```

For a research run, `ResearchRuns.start` performs step 1 when it creates the run:
`application/population.py` `live_binding` resolves `CZ_LIVE` without reading a panel, and the
binding goes to `create_run` through `start_workflow(population=)`. A start that finds its run
keeps what that run recorded, and a retry keeps its original's. No research step declares
`consumes_population` yet, so step 2 does not run, and the run says its respondents did not come
from the population (fieldwork stays fictional until a panel persona source lands:
`.planning/plans/panel-grounded-respondents.md`; the licence, OI-61, is closed).

## What the binding records (`PopulationBinding`)

Stored once per run in `run_population_bindings`, never updated; `as_record()` is
the provenance form for artifacts and reports.

| Field | Meaning |
|---|---|
| `version_id`, `version_label`, `content_sha256` | exactly which bytes |
| `dataset_id`, `contract_id` | under which import contract |
| `population_id`, `resolution` | `LIVE_CURRENT`, `STATIC_REFERENCE` or `PINNED` — why this version |
| `weight_role`, `weight_column` | the canonical analysis weight; no fallback exists |
| `view` | `BASE` (400 source fields) or `ANALYSIS` (+ 7 enrichment + `_analysis_weight`) |
| `dictionary_sha256`, `field_policy_version` | which claim rules applied |
| `companion_set_sha256`, `joint_state` | which companion set and what the joint certificate said |
| `resolved_at` | when |

Two submissions of the same run that resolve differently on any of these are
refused (`PopulationBindingConflict`); a load under different rules than recorded
is refused (`VersionIntegrityError`). **Research stage fingerprints should be built
from these fields, not from project free text** — that change is research-engine's
(OI-6).

## What a field may be used for (`FieldUse`)

`AUDIENCE_FILTERING`, `PERSONA_CONSTRUCTION`, `AGGREGATE_ANALYSIS`, `SIMULATION`,
`CLIENT_MEASURED_CLAIM`, `CLIENT_MODELLED_CLAIM`, `WEIGHTING`. A permitted use
returns `Obligation`s the consumer must carry to its output: `DISCLOSE_SCOPE`,
`DISCLOSE_MODELLED`, `AGGREGATE_ONLY`, `USE_SPECIFIED_WEIGHT`. Refusals carry a
stable `reason` (`audit_only`, `unmapped_policy`, `unclassified_derived_field`,
`phrase_permits_no_client_claim`, `evidence_*_is_not_measured`, …).

On the real v17 dictionary: 400/400 fields map; 115 may back a client measured
claim (the reference's own flags would have allowed 287); `never measured fact`,
`never claim direct Schwartz measurement` and `AUDIT_ONLY` fields never reach a
client (parity-tested). The eight derived fields are refused until classified —
[the decision checklist](../migration/population-derived-fields-decision.md).

## What may be claimed jointly (`JointStatus`)

From `CORE_JOINT_STATUS.json`, evaluated fail-closed. For `v17_4_0` it is
`CERTIFIED`: descriptive core and matched-block outputs are allowed; **client
joint outputs and cross-block same-person claims are forbidden**. For every other
version the certificate does not bind and every joint use is refused. A single
field is never a joint claim.

## Usability

A version is usable only when it was imported under the contract, its companion
set (15 assets for v17) is attached and valid, it is runtime-eligible (not the
`v17_0_BASE` lineage root), and — for ANALYSIS — an enricher is configured.
Establish and promote additionally need a `PopulationOperatorContext`
(`POPULATION_ESTABLISH` / `POPULATION_PROMOTE`) from `PopulationAuthority`.

That context is issued from `AIA_POPULATION_OPERATORS` (verified user id to permissions;
unset means nobody), which `aia_executors.population_ops` reads, and nothing else does. The
command imports, attaches, establishes and promotes, acting as a named person. The registry
(versions, populations and promotion history, with status derived and never stored) is
readable at `GET /api/v1/population` and shown on **Společenská inteligence**.

On develop the bundle's files are synced read-only from the EU ops bucket to the host
(`deploy/develop/bin/sync-population.sh`, `population/v17.files`), and
`FilesystemPopulationSource` reads them. The first import ran on 2026-10-11: STATIC
`CZ_STATIC_REFERENCE` is `v17_1_2` and LIVE `CZ_LIVE` is `v17_4_0`
(`.planning/plans/population-operations.md` P6b).

## Characteristics

Each version keeps its field dictionary beside it: `import_version` stores the verified bytes
in `population_version_dictionaries` (insert-once), and `population_ops record-dictionary`
stores it for a version imported before the table existed, taking the file at the version's
own `dictionary_location` only when it hashes to `dictionary_sha256`. It never reads the
panel. The develop deploy runs `record-dictionary` after replacing services.

`application/population_characteristics.py` reads those bytes, re-hashes them and builds the
field policy exactly as `load()` does, so the page and a run cannot disagree on what a field
may serve. `GET /api/v1/population/versions/{id}/characteristics` returns the weights, the
field blocks, every field with its answer for each `FieldUse`, and the 18 built-in subpanels
adopted from 18.6.6 (owner, 2026-10-11; `domain/population/subpanels.py`, pinned to the
unit's `BUILTIN_SUBPANELS_v17.json`). Each subpanel is checked against the version's policy
for `AUDIENCE_FILTERING`. Its counts are 18.6.6's, measured on `17.1.2`, never AIA's. A
version without a kept dictionary says `dictionary_kept: false`, and every subpanel check is
unknown (`null`), never usable. A mismatch is a 409, `population_dictionary_mismatch`. The
section sits under the registry on **Společenská inteligence**. A subpanel is not yet
applied to a study's audience (OI-91).

## A run's sample

`domain/population/sampling.py` draws a run's respondents from the population its binding
loaded: `draw_panel_sample(population, filters, n, seed)` narrows by the audience filter
(`audience.py`, 18.6.6's `sanitize_filters` + `_mask`), then ports 18.6.6's
`draw_representative` on its stdlib path: largest-remainder quotas over sex x age group x region
(education joins from n 700), a weighted draw without replacement within each cell, raking to the
five quota fields' weighted shares, and the unit's audit and tolerances. Every quota field must
pass `decide(field, AUDIENCE_FILTERING)` and `decide_joint(..., client_facing=False)`; an
all-zero weight, a missing quota field or an unrepresentative sample is refused by name, never
drawn smaller. `PanelSample.provenance()` is what a run records: the sampler and filter
versions, filters, seed, the binding's `version_id` and `content_sha256`, and the audit with the
audience's and the sample's distinct donors. Nothing calls it yet; small samples are refused on
this path (OI-99).

A run's personas come from that sample through `domain/panel_persona.py` (18.6.6's adaptive
persona, EXACT): every column it reads asks `decide(field, PERSONA_CONSTRUCTION)`, and
`decide_joint` is asked for the core fields together and for each matched donor block within
itself, since the certificate refuses cross-block same-person joints. Its two companions, the
persona signal catalog and the value labels, are read only through
`RuntimePopulation.companion(asset_id)`: the bytes the loader verified against their recorded
SHA256 at load, never the asset source.

## Materialized dimensions (P4)

An accepted dimension becomes respondent values as an **owned child** `DatasetVersion`: the
shared base's panel plus one column per materialized field, the base as its parent, owned by the
organization and client it was made for (`VersionOwner`; plan
`population-operations.md` P4, M1-M5). What a child adds is a `PopulationContractExtension`
pinned by its own SHA256 (`domain/population/materialized.py @ d44e178a`); the base's import
contract is unchanged. `check_child_version` refuses any child that is not exactly its shared
base extended, and `plan_establish` / `plan_promotion` refuse an owned version
(`OwnedVersionNotShared`, reason `owned_version`): STATIC and LIVE stay shared
(`test_an_owned_child_is_never_a_shared_populations_version`).

A materialized field's policy is fixed, not read from the dictionary (M3): modelled, persona-,
audience- and simulation-eligible, a client claim only as a disclosed modelled aggregate, never a
measured claim and never weighting (`materialized_policy_entry`). Its values come from 18.6.6's
evidence rule, ported EXACT (`domain/population/derivation.py`, method
`npc-18.6.6-evidence-overlay` v1, fixtures `tests/fixtures/materialize_dimension/` from
`tools/materialize_capture.py`), with one named deviation: a dimension no predictor varies for
is refused (`no_varying_predictor`) where the unit wrote hash noise.

**Stored (P4c, migration `f0b2d4e6a8c1`).** An owned child's id is its content qualified by an
opaque owner digest (`owned_version_id`), so two clients' identical children are two versions.
It is seen only by its organization: `PopulationRegistryRepository.versions(…, organization_id=)`
and `visible_version` return shared versions plus that organization's own, and the import's
lookups (`version_by_sha`, `version_by_label`) see shared versions alone. Its extension is kept
insert-once in `population_contract_extensions` and re-hashed on read
(`test_population_owned_versions.py`).

**Made by a worker step (P4d).** A researcher asks from a study:
`prepare_materialization` (`application/materialize.py`) checks a `DimensionDefinition`
(`domain/population/definition.py`, hash-identified) against LIVE's kept policy before anything
is enqueued: the name is free and every predictor is a field that may build a persona. The owner
is the study's organization and client, from the scope, never an argument.
`start_materialization` enqueues a `population_materialize` run under the study's population
project (`projects.owner = study_population`), recording LIVE as the run's population. The step
(`aia_executors.materialize`) runs `PopulationRuntime.materialize_child`: the base read and
verified as every load is, each predictor asked again of its policy, the values derived, the
child written once to the population store and registered. It never promotes. Without a
population store or `AIA_POPULATION_ASSET_ROOT` the run parks (`population_store_unconfigured`).

The population store (`infrastructure/population_store.py`) keeps children in EU S3
(`AIA_POPULATION_STORE_BUCKET` / `_REGION`, both or neither) under `materialized/`, written with a
conditional put: the same bytes answer as written, other bytes are refused. A
`RoutingPopulationSource` reads `s3://` locations from the store and every other location from the
shared copy.

**Loaded through the one loader (P4e1).** `PopulationRuntime.resolve_child(version_id,
organization_id=)` resolves only that organization's own child, to a `PINNED` binding with no
population. Loading it verifies the base by its contract, then the child against the base: its
SHA256 and `check_child_version`, a header that is the base's plus exactly the extension's
fields, the same rows with the base's columns equal cell for cell, and every added cell valid for
its kind. Any drift is refused; a child is never partly used. Companions, the joint certificate
and the policy are the base's, the policy with the materialized fields added
(`test_population_load_child.py`).

**Selected at run start (P4e2).** `ResearchRuns.start(population_version_id=)` and
`POST …/research/runs {population_version_id}` record the child's binding instead of LIVE.
`child_binding` resolves only a child of the study's own client: another client's (in the same
organization or another), a shared version and an unknown id are all unknown (404
`population_version_not_found`), checked before the spend confirmation, and nothing starts. The
selection is part of the run's identity, and a retry keeps the binding its original recorded
(`test_research_population_child.py`). A panel run over a child reads it from the population
store: the worker gives the panel loader the same store as the materialize step
(`ai_runtime.panel_population_source`); without a store the run parks
(`test_a_panel_run_over_the_clients_child_reads_it_from_the_population_store`).

**Asked for and read in AIA (P4d4).** `POST /studies/{study_id}/population/materializations
{definition}` starts a materialization from a study (422 `materialization_refused` with the
domain's reason; 409 `population_unavailable` for a LIVE that exists but cannot be resolved), and
`GET …/materializations[/{run_id}]` reads the study's runs. The registry gives each owned child
its outcome: the target beside what was achieved and `target_met`, within the kind's
`TARGET_TOLERANCE` (binary 0.005, scale 0.01) and never presumed; P4b's M04 (2.0 asked, 2.68
achieved) reads not met. Společenská inteligence lists the organization's children on their own
with that outcome ("neznámo" when a child's record carries none), and the Run stage offers the
study's client's children beside LIVE.

## Not yet available to consumers

| Missing | Blocks | Tracked |
|---|---|---|
| A step that composes `AudienceDimensionsEnricher` (the derivation landed, `domain/population/enrichment.py`, EXACT vs 18.6.6) | the ANALYSIS view in any run | OI-7; `plans/panel-grounded-respondents.md` chunk 5 |
| Classification of the 8 derived fields | any use of them | [decision checklist](../migration/population-derived-fields-decision.md) |
| An S3 asset source read directly by the loader (today: the host's synced copy) | a deployment without a host disk | `.planning/overview.md` Next |
| Typed / columnar views (numbers, the M07 age floor) | numeric work without re-parsing text | `.planning/overview.md` Next |
| A form to compose a dimension's definition from accepted Client Knowledge (today the route takes a whole definition) | a researcher materializing without writing the definition | `plans/client-knowledge-lifecycle.md` K5 |
