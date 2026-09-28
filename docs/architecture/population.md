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

runtime = PopulationRuntime(session, contract=CZ_SYNTHETIC_V17, source=asset_source,
                            enricher=enricher)          # enricher: see OI-7

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

## Not yet available to consumers

| Missing | Blocks | Tracked |
|---|---|---|
| The seven enrichment derivations | the ANALYSIS view | OI-7, [archive dependency](../migration/population-enrichment-archive-dependency.md) |
| Classification of the 8 derived fields | any use of them | [decision checklist](../migration/population-derived-fields-decision.md) |
| The EU asset source and the first real import | any real data at all | `.planning/overview.md` Next |
| Typed / columnar views (numbers, the M07 age floor) | numeric work without re-parsing text | `.planning/overview.md` Next |
| An operator configuration key at the composition root | establish / promote in a deployment | OI-8 note |
