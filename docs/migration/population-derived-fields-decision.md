# Decision needed — classify the 8 runtime-derived population fields

**Owner of the decision:** data owner (with analysis-governance for claim rules).
**Asked by:** population-data, 2026-09-22.
**Status:** open. Until each row is decided, the production default stands.

## What is being asked

The runtime population carries 408 columns: the 400 source fields of
`FIELD_DICTIONARY_v17_1.csv`, plus **8 fields that have no dictionary entry** — no
`evidence_status`, no `production_grade`, no `recommended_use`, no
`persona_eligible` (AIA-reference `field-policy.json`
`runtime_columns_without_dictionary_entry`; `data-import-contracts/czech-population.md`
OUTPUT). The reference used them anyway. Production refuses to guess what they may
be used for, so each needs a classification row, in the dictionary's own
vocabulary, before it can be used for anything.

**Current production default, for all 8** (`aia_core.domain.population.policy`,
`FieldPolicy.decide`): refused for every use — audience filtering, persona
construction, aggregate analysis, simulation, client measured claims and client
modelled claims — with reason `unclassified_derived_field`. The one exception is
`_analysis_weight`, which is allowed for `WEIGHTING` only.
`DerivedField.client_claims_allowed` is `False`. Test:
`tests/test_population_policy.py::test_unclassified_derived_fields_are_refused_and_the_weight_is_weighting_only`,
parity: `tests/test_population_reference_parity.py::test_derived_runtime_fields_are_refused_until_classified`.

## What the reference establishes — and what it does not

For the seven `*_derived` fields the reference repository records **where** they
come from but **not how**: they are appended by
`audience_dimensions.enrich_panel → attach_evidence_overlays(attach_derived(df))`
at load time (`population-subsystem.md` §5). The derivation code is in the withheld
archive only; see [population-enrichment-archive-dependency.md](population-enrichment-archive-dependency.md)
(OI-7). Their names suggest semantics; **names are not evidence**, and none is
inferred here.

`audience_dimensions` is imported by `audience`, `data_library`, `pipeline`,
`prototype_server` and `ui_server` (AIA-reference `dependency-graph.json`); its
`catalog` backs `GET /api/audience/dimensions` (`api-ledger.json`), and the reference
test `test_real_sampling_honors_derived_factor_filter` (`test-ledger.json`) shows
derived factors were usable as **audience filters in respondent sampling**. Beyond
that, which derived field reached which consumer is not recorded.

## The checklist — one row per field

For every row, the data owner supplies the five dictionary columns
(`evidence_status`, `production_grade`, `recommended_use` — one of the sixteen
known phrases or a new one with its meaning — `persona_eligible`, `block`). A new
phrase or code needs an analysis-governance entry in
`RECOMMENDED_USE_POLICY` / `EVIDENCE_STATUS_CLASS` and a `FIELD_POLICY_VERSION` bump.

| # | Field | Derivation / source | Known consumers in the reference | Can influence | Production default | Decision required |
|---|---|---|---|---|---|---|
| 1 | `ad_receptivity_tier_derived` | `audience_dimensions.attach_derived` (formula withheld, OI-7) | enriched panel of both loaders; audience catalogue | filtering / sampling (reference); analysis, personas: **unknown** | all uses refused | classification row; whether it is a measurement, a model, or a transparent derivation of which inputs |
| 2 | `digital_engagement_tier_derived` | same | same | same | all uses refused | same |
| 3 | `dominant_leisure_derived` | same | same | same | all uses refused | same |
| 4 | `dominant_media_derived` | same | same | same | all uses refused | same |
| 5 | `financial_capability_tier_derived` | same | same | same | all uses refused | same — note it would sit beside 25 `FINANCIAL_CAPABILITY` fields that are mostly `CALIBRATED_MODELED` / aggregate-only |
| 6 | `life_stage_derived` | same | same | same | all uses refused | same |
| 7 | `shopping_orientation_derived` | same | same | same | all uses refused | same — note it would sit beside 61 `marketing_behavior` fields that are `never measured fact` |
| 8 | `_analysis_weight` | `pipeline.Panel.__init__`: the resolved weight scheme's column (`default_current` → `vaha_strukturalni_2025`), fixtures F10/F11 | the research engine's weighted estimates | weighting only | `WEIGHTING` allowed; everything else refused | confirm it stays weighting-only (recommended: yes — it is a copy of a declared weight, never a claim) |

**Recommended conservative classification, if the data owner wants a default to
approve rather than write:** for rows 1–7, `recommended_use` =
`HISTORICAL_OR_EXPLORATORY` (internal filtering, analysis and simulation;
no client claims), `evidence_status` = `DERIVED_TRANSPARENT` only if the recovered
formula reads exclusively from source fields and adds no model, otherwise a
`MODELED_*` code; `persona_eligible` = `no` until the formula is reviewed. This is
a proposal, not a classification — it is not applied.

## What changes once decided

The eight rows become a classification artifact that travels with the population
version (like the dictionary, hash-pinned); `build_field_policy` reads them instead
of `_derived_entry`. Nothing about the source 400 fields changes.
