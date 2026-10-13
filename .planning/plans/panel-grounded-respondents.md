---
status: in-progress
chunks:
  - "[x] 0. Record the OI-61 determination: PIAAC, ISSP and the Czech panel APPROVED for bedrock-eu-primary"
  - "[x] 1. ADR: panel-grounded AI respondents are modelled evidence, never measured"
  - "[x] 2a. Sampler contract (plan before code): inputs, quota fields, the audience filter, refusals, what a sample records"
  - "[x] 2b. Verify the quota and donor fields against the imported v17 dictionary on develop"
  - "[x] 2c. Audience filter: sanitize_filters + _mask as one function, the factor map's kinds, subpanels through it; parity fixtures"
  - "[x] 2d. Enricher: attach_derived as the population's Enricher (OI-7 is unblocked: its source is vendored), EXACT fixtures"
  - "[x] 2e. Quotas, draw, raking and audit (draw_representative's stdlib path); parity fixtures"
  - "[x] 3a. Persona contract (plan before code): the mode 18.6.6 ran, its inputs, topics, the policy gate, parity"
  - "[x] 3b. Profile core: base, socio-economic and household lines, first-person prose with the word cap; EXACT"
  - "[x] 3c. Topics: odvod_temata and a block's union of topics; EXACT"
  - "[x] 3d. Grounded signals: the persona signal catalog and value labels through the population; EXACT"
  - "[x] 3e. Panel persona: a Persona per sampled row (facts, styles over the population, donor, weight, lineage); refusals"
  - "[x] 4a. Origin contract (plan before code): every site that reads an origin, and what each does with a new one"
  - "[x] 4b. MODELLED_AI_PANEL and the allowlist gate: CLIENT_ADMISSIBLE_ORIGINS, assemble_dataset derives it, mixed refused"
  - "[x] 4c. One reading of an origin (simulated / modelled / unknown) and the labels on every Python surface"
  - "[x] 4d. The web client's labels: modelled said every time, an unknown origin never read as real"
  - "[x] 4e1. aia-instrument-evidence-2: the modelled origin's policy, internal only without a validation"
  - "[x] 4e2. The respondent system fingerprint, and a current holdout validation as the one thing that lifts INTERNAL_ONLY"
  - "[x] 4e3. Native evidence builds -2 for a modelled run, bound to its respondent system (no validation stored: internal)"
  - "[x] 4e4. Support counted in donors, proved for a modelled run (1,000 respondents on 40 donors is 40-donor evidence)"
  - "[x] 4e5. The report's mark beside a modelled number, with the validation's date and fingerprint when one holds"
  - "[x] 5a. Persona source contract (plan before code): pinned at start, the panel path, refusals, provenance, cost"
  - "[x] 5b. The panel source as a pure function: sample, personas, plans, the respondent system and the provenance"
  - "[x] 5c. A run pins its persona source at start (AIA_AI_POPULATION_PERSONAS_ENABLED, off by default); a retry keeps it"
  - "[x] 5d. The executor: a panel-pinned run loads its recorded population, or parks; the dataset names its system"
  - "[x] 5e. Cost measured and the end-to-end proof under the real worker on a fictional population"
  - "[x] 6a. Screens contract (plan before code): catalogue at import, the API's preview, readiness, the screen"
  - "[x] 6b. The audience catalogue: computed once per version (EXACT), kept insert-once, served by the API"
  - "[x] 6c. The feasibility preview: the API counts LIVE under the filters and asks the sampler; measured"
  - "[x] 6d. Readiness says whether the filters will be applied, by what a run started now would pin"
  - "[x] 6e. The audience step: live filters, built-in subpanels and the preview; OI-50's empty bound is no bound"
  - "[x] 6f. Journey: the audience step in the workbench, and a modelled run's results labelled"
  - "[x] 7a. Validation contract (plan before code): the claim, held-out truth, leakage, arms, metrics, P1-P8, money, recording"
  - "[x] 7b. The item bank and the preregistration: eligibility, the pinned split, exclusion sets by association; pure"
  - "[x] 7c. Persona arms (A, B, C, D, S) and exclusions for a validation run only; D without exclusions is today's persona"
  - "[x] 7d. Scoring: L0, L1, TVD, subgroup TVD, Brier, entropy, replicate SD, paired bootstrap, Holm, the verdict; pure"
  - "[x] 7e1. Fieldwork's answering extracted (answer_plans): plans from any source answered exactly as a run answers them"
  - "[ ] 7e2. The preregistration stored insert-once under the validation Study, before any confirmation call"
  - "[ ] 7e3. The respondent_validation workflow: sample, arm x replicate fieldwork steps, score; started with the study's ceiling, budget and confirmation"
  - "[ ] 7e4. Its executors: an arm's replicate answered through answer_plans, the score step's verdict artifact; the layer rule on arms"
  - "[ ] 7f. Recording: the researcher records the computed verdict; ValidationState with date and evidence; analysis and report read it"
  - "[ ] 7g. The item bank compiled from the eight source questionnaires (Czech as fielded), checked by a person, pinned"
  - "[ ] 7h. On develop: the development pass prices the run, then preregistration, the confirmation run and the recorded verdict"
---
# Panel-grounded AI respondents

## Why

Today an AI respondent inherits nothing from the population. `fictional_roster`
(`packages/aia_core/src/aia_core/domain/ai_respondent.py:255 @ 5d545eb`) draws sex,
age (18-89), education and region **uniformly** from `random.Random(seed)`, weight 1.0,
an invented donor. Only the six response styles depend on those attributes
(`respondent_behavior.py:66`, `_LINKS`; `assign_styles` :275). A run records the LIVE
population binding at creation, but no step reads it (CLAUDE.md § population).

18.6.6 drew respondents from the panel: PPS without replacement, probability
proportional to `vaha_kalibrovana`, audience filters through the one canonical mask
(`legacy/npc-panel-18.6.6/app/pipeline.py:240`, `sample_representative`), and built
each persona from the row in a structured "survey format" with only the most
pronounced traits (`pipeline.py:528`, `generate_persona_text`; `dispozice.py:494,579`).

The blocker was OI-61. On 2026-10-12 the owner determined that licensing is not a
problem (decisions below).

## Decisions (owner, 2026-10-12, in session)

1. **Licence.** PIAAC, ISSP and `czech_population_panel` may be sent to a model
   provider. Basis: owner determination. Route: **`bedrock-eu-primary` only**
   (ADR 0010; `deploy/develop/env.example:51`), not `ANY_APPROVED_ROUTE`. A future
   route needs its own determination.
2. **Evidence status.** Answers of panel-grounded respondents are **modelled
   evidence**: admissible only as `ClaimBasis.MODELED` with the `MODELED_VALUE`
   disclosure (`domain/evidence/claims.py:67-100`), never `MEASURED`. That makes
   this a new origin outside `NON_EVIDENCE_ORIGINS` (`domain/fieldwork.py:50-68`)
   and needs an ADR before code (chunk 1).

## Chunks

**0. Determination.** Replace the three UNDETERMINED records in
`domain/licence_determinations.py` with APPROVED, `decided_by` the owner,
`decided_on=2026-10-12`, the basis above, `approved_routes={"bedrock-eu-primary"}`.
Tests: the gate passes panel lineage on that route and refuses it on any other
(`test_licence_gate.py`). Residency still applies unchanged: a client study's
material stays Class A.
*Open:* OI-61's text asks for legal's confirmation beside the data owner; the owner's
determination is recorded as the basis, and the docs PR closes OI-61 citing it.

*Landed:* `licence_determinations.py` records the three datasets APPROVED for
`PANEL_APPROVED_ROUTE = "bedrock-eu-primary"`
(`test_licence_gate.py::test_each_panel_derived_dataset_reaches_the_eu_bedrock_route_and_no_other`).
Over any other route the gateway now refuses panel lineage as
`licence_not_approved_for_route`, no longer `licence_undetermined`
(`test_model_gateway.py::test_licence_is_a_second_gate_refused_before_dispatch`). The
fieldwork step fails `persona_source_unsupported` before anything is reserved or sent
when a persona is not fictional, until chunk 5 gives it a panel source
(`test_ai_fieldwork.py::test_panel_derived_personas_fail_before_any_call_while_no_panel_source_exists`;
see Findings).

**1. ADR.** Panel-grounded respondents as modelled evidence. It covers: what an
analysis may claim from them (aggregate and segment, MODELED, disclosed); what it may
not (MEASURED, individual-level facts the model produced); how support and Kish n
read for a sample drawn from a synthetic population; the interaction with D6 (Sociomap
`INTERNAL_ONLY`); report wording.
*Landed:* [ADR 0024](../../docs/architecture/adr/0024-panel-grounded-respondents-are-modelled-evidence.md),
**Proposed**; accepting it is the owner's. It fixes what chunks 2-7 build: the origin
`MODELLED_AI_PANEL` stamped from facts; the client-facing origin gate as an allowlist
(`CLIENT_ADMISSIBLE_ORIGINS`), because today's denylist at `evidence/admission.py:244 @ ea5210e`
passes `None` and any new origin; `aia-instrument-evidence-2` (MODELED only, aggregate or
segment, disclosed); client-facing only under a current validation bound to the respondent
system's fingerprint (`evidence/validation.py:87,115`); support counted in unique donors.

**2. Sample.** *Corrected 2026-10-12:* the plan first said "PPS without replacement".
That is not what 18.6.6 runs. `sample_representative` returns at `pipeline.py:298`
through `representative_sampling.draw_representative`; the systematic-PPS code after that
`return` (`pipeline.py:300-358`) is dead. The live method calibrates integer quotas over
joint cells with a scipy MILP, draws within cells, rakes analysis weights to the
population margins and refuses a sample still off after raking
(`representative_sampling.py:131-173`). AIA's domain is stdlib only (`ARCHITECTURE.md`
layer 1), so the owner chose (2026-10-12) the path the unit ships for when the MILP is
unavailable: largest-remainder quotas (`representative_sampling.py:117-128`).

### 2a. The sampler contract

Unit anchors below (`pipeline.py`, `representative_sampling.py`, `audience.py`,
`audience_dimensions.py`, `uncertainty.py`) are under `legacy/npc-panel-18.6.6/app/`, which is
frozen, so they do not move.

**Where.** `domain/population/audience.py` (the filter) and `domain/population/sampling.py`
(the sample), pure. Both take a `RuntimePopulation`, which only `PopulationRuntime` issues
(`domain/population/runtime.py:1-12`), so a sample can only come from a run's recorded
binding: fieldwork loads it with `load_for_run` (`application/population.py:494`). A
run's binding is the ANALYSIS view (`live_binding`, `application/population.py:731`), so
`analysis_weight` is present. Nothing here loads a population, reads a file or names a
version.

**Inputs.**

| Input | From | Rule |
|---|---|---|
| `population` | `load_for_run` | the binding the run recorded; no other |
| `filters` | `SpecSelection.audience_filters` (`research_design.py:179`), or a built-in subpanel's `SubpanelFilter`s converted to the same shape | the one filter function; never a second reader |
| `n` | `ResearchSpecification.n` | `1 <= n <= support after the filter`, else refused |
| `seed` | `fieldwork_seed(spec)` (`ai_fieldwork.py:93`) | `random.Random(seed)`; one generator for quotas' tie-break, draws and shuffle |
| `quota_fields` | `QUOTA_FIELDS = ("pohlavi", "vek_skupina", "kraj", "vzdelani", "zamestnani_status")`, the unit's `DEFAULT_FIELDS` (`representative_sampling.py:6`) | declared, versioned with the sampler |

**The filter (2c).** One function, `audience_mask(population, filters) -> (rows, dropped)`,
porting `sanitize_filters` + `_mask` (`audience.py:217`, `:34`) together, so preview and
fieldwork cannot disagree (the bug 18.6.6 records at `pipeline.py:255-257`). The dimension's
kind (numeric or categorical) comes from a declared factor map ported from
`audience_dimensions.factor_map` (`audience_dimensions.py:267`), never from the value's shape: in the unit a two-item list
is a category list to `_mask` but an interval to `sanitize_filters` on a numeric dimension.
Every filtered field must pass `decide(field, FieldUse.AUDIENCE_FILTERING)`. A filter the
unit would drop is **refused** here (`sampling_filter_invalid`, every reason listed), as
`sample_representative` itself refuses (`pipeline.py:259-260`).

**The sample (2e).** `draw_panel_sample(population, filters, n, seed) -> PanelSample`:

1. Rows after the filter; base weight = `analysis_weight`, non-finite or non-positive -> 0.
   If every weight is 0 the unit falls back to 1.0 (`representative_sampling.py:18`); AIA
   **refuses** (`sampling_no_weight`): no default weight (CLAUDE.md § population).
2. Quota fields used = the declared ones with more than one value after the filter (a
   filter on `pohlavi` makes it constant, which is meaningful, as in the unit). A declared
   field **absent** from the population is refused (`sampling_field_unknown`); the unit
   skips it silently. Each used field must pass `decide(field, AUDIENCE_FILTERING)` and the
   set `decide_joint(..., client_facing=False)`.
3. Targets: each used field's weighted share per category (`_targets`).
4. Quotas: largest remainder over the joint cells of `pohlavi x vek_skupina x kraj`, plus
   `vzdelani` when `n >= 700` (`representative_sampling.py:142-143`), capacity-capped. Ties
   broken by the seeded generator. Deterministic apart from exact ties.
5. Draw within each cell, weighted, without replacement; then shuffle.
6. Rake the sample's weights to every used field's targets: 60 iterations, the cap at
   `8 x` the 99th percentile (n > 20) or `8 x` the maximum, mean-normalised
   (`_rake`, `representative_sampling.py:53-64`).
7. Audit raw and weighted composition (`_audit`). Refuse when the weighted maximum
   deviation exceeds `max(0.25, 100/n)` percentage points (`sampling_unrepresentative`);
   `PASS_WEIGHTED` when only the raw one exceeds `max(0.50, 100/n)`.
8. With no usable quota field: weighted draw without replacement, analysis weight = base
   weight over its mean (`representative_sampling.py:136-137`).

**Output: `PanelSample`.** Frozen, recorded with the run's fieldwork provenance:

- per respondent: the row's position in the population, its `core_donor_id`, base weight,
  raked analysis weight, sample order;
- the audit: population n after the filter, sample n, fields used, quota fields,
  `selection_method = "largest_remainder"`, raw and weighted deviation per category,
  both tolerances, Kish effective n of the analysis weights, min and max weight, status;
- `SAMPLER_VERSION`, the filters as applied, the seed, the binding's `version_id` and
  `content_sha256`.

**Refusals, each a named reason, never a smaller sample:** `sampling_filter_invalid`,
`sampling_empty`, `sampling_n_exceeds_support`, `sampling_field_unknown`,
`sampling_field_refused` (policy), `sampling_no_weight`, `sampling_unrepresentative`.

**Parity.** Exact draws cannot match: the unit draws from NumPy's PCG64 stream, AIA's
domain from `random.Random` (the same constraint as OI-62 and D11). So each part is
compared where it is deterministic, from fixtures captured by running the unit's own
functions on a fictional panel (`tools/aggregate_capture.py` pattern):

| Part | Parity |
|---|---|
| filter (`sanitize_filters` + `_mask`) | EXACT: the same rows and the same dropped reasons (AIA refuses where the unit drops) |
| targets, quotas (largest remainder) | EXACT, on panels without exact ties |
| raking, audit | EXACT given the same sample: the fixture feeds the unit's picks to both |
| draw | PROPERTIES: no duplicates, counts equal the quotas, every pick in its cell, the same seed gives the same sample |

**Known differences from the unit, each deliberate:** quotas from the fallback, not the
MILP (owner, 2026-10-12); a missing field, an invalid filter and an all-zero weight are
refused, not skipped or defaulted; the population comes only from the run's binding.

### 2b. Fields to verify before 2c

`vek_skupina`, `zamestnani_status` and `core_donor_id` are used by 18.6.6 as panel columns
(`audience.py:29`, `pipeline.py:110`; `uncertainty.py:114` `donor_support`), and nothing in the
unit derives them, but the dictionary that would confirm it, `FIELD_DICTIONARY_v17_1.csv`,
ships in the EU bucket (`deploy/develop/population/v17.files`), not in this repository.
Check on develop: `GET /api/v1/population/versions/{v17_4_0}/characteristics` lists every
field with its per-use policy. If one is missing, it is either declared as a `DerivedField`
in the population contract (not computed in the sampler) or dropped from `QUOTA_FIELDS`;
that is decided here before 2e is written.

*Verified 2026-10-12* by the owner, from develop's Společenská inteligence → Česká
populace screen (the characteristics route above): the version's dictionary,
`FIELD_DICTIONARY_v17_1.csv`, shared by v17_0_BASE, v17_1_2 and v17_4_0
(`deploy/develop/population/v17.files`), 408 fields (400 dictionary + 8 derived at runtime).

| Field | Block | Evidence class | Grade | Persona use |
|---|---|---|---|---|
| `pohlavi`, `kraj`, `vek` | population_anchor | POPULATION_ANCHOR | A | yes |
| `vek_skupina` | derived | DERIVED_TRANSPARENT | A | yes; "allowed only in the audited v15.2.1 semantics" |
| `vzdelani`, `zamestnani_status` | core | CANONICAL_CORE | B | yes |
| `core_donor_id` | provenance | PROVENANCE_OR_CORE | T | no (an identifier, never shown to a model) |

All five quota fields and the donor column are dictionary columns of the panel, so none
becomes a `DerivedField` and `QUOTA_FIELDS` stands. Not read from the screen: the per-use
icons for `AUDIENCE_FILTERING` (they did not survive the copy); 2e asks
`decide(field, AUDIENCE_FILTERING)` at run time and refuses on a no, so nothing is assumed.

**The base weight.** The binding's default role is `default_current` =
`vaha_strukturalni_2025` (`domain/population/czech.py:212-226 @ ea5210e`; on the screen
"Strukturální 2025 (výchozí)"). 18.6.6's `_analysis_weight` is the same column
(`CORE_JOINT_STATUS.json:49`, `current_default_weight`; set from the contract's `default_current` role at `pipeline.py:180-182`), so
`analysis_weight` is the weight the unit's live sampler used; the `vaha_kalibrovana`
fallback in `representative_sampling.py:13-14` is never reached there.

**Support to expect.** The screen repeats 18.6.6's own counts per subpanel (on v17_1_2,
`vaha_strukturalni_2025`). Two sit below `min_layer_donors` 25 in effective donors
(Senioři 80+: 48 donors, 20.7 effective; Lékaři: 9, 6.3); a sample drawn
there is legal, and Aggregate suppresses what its donors cannot support. The sampler
records the audience's donor count so the run can say so before fieldwork is paid for
(chunk 5's preflight).

### 2c. Landed: the audience filter

`domain/population/audience.py`: `sanitize_filters` + `audience_mask` (the unit's pair, over
plain text columns), `factor` and `column_type` (the unit's kind rule on the column as
`read_csv` types it, `pipeline.py:192`), `subpanel_filters` (`population_subpanels.
runtime_filters`), and `select_audience(population, filters)`, which refuses
(`sampling_filter_invalid`, `sampling_field_refused`, `sampling_empty`) where the unit
dropped. Parity is EXACT on 25 cases and all 21 factors, captured from the unit's own
`sanitize_filters`, `_mask` and `factor_map` (`tools/audience_capture.py`;
`tests/fixtures/audience_filter/` (no "population" or "panel" in a fixture path: `tools/exposure_check.sh` rule 2c), re-captured byte-identical), in
`tests/test_population_audience.py`.

What the fixture showed, each pinned by a case:

- **A flag on a column with a gap is matched as a float.** pandas reads an integer column
  with an empty cell as float, so the unit's lookup keys it `"1.0"`; `{"is_parent": 1}`
  and `{"is_parent": true}` match nothing and are dropped, only `"1.0"` matches (C12-C14).
  A built-in subpanel is that same filter (`population_subpanels.runtime_filters`), so if
  a v17 flag column has an empty cell, 18.6.6 itself refused that subpanel; AIA refuses it
  identically (`test_a_flag_subpanel_on_a_column_with_a_gap_is_refused_as_in_the_unit`).
  Whether any v17 flag has a gap is unknown here (no panel rows in this repository); 2e's
  preflight on develop will say.
- **A two-item list is an interval only on a numeric dimension** (C10, C23), from the
  column's kind, never the value's shape.
- **The derived dimensions are refused by AIA's field policy** while unclassified
  (`policy.py:387`, `unclassified_derived_field`), though the unit filtered on them (C21).
  That stays until the data owner classifies them.

### 2d. The enricher (added 2026-10-12)

The sampler loads the run's binding, which is the ANALYSIS view, and that view refuses to
load without an `Enricher` for the seven `*_derived` fields
(`application/population.py:668-675 @ ea5210e`). None is composed anywhere, because OI-7
records their logic as recoverable only from the withheld archive. It is not: the vendored
`legacy/npc-panel-18.6.6/app/audience_dimensions.py` **is** that file, SHA256
`6ae1d1f8…c754bf`, the exact hash OI-7 and
`docs/migration/population-enrichment-archive-dependency.md:21` wait for (Findings). 2d
ports `attach_derived` (`audience_dimensions.py:137-182`) as an `Enricher`, EXACT against
fixtures from the unit's own function, and composes it where the worker builds
`PopulationRuntime`. `attach_evidence_overlays` adds nothing: the vendored unit has no
overlay metadata (`app/data/` holds none), so the port records that and adds no overlay.

*Landed:* `domain/population/enrichment.py`: `derive_audience_dimensions` and
`AudienceDimensionsEnricher` (the `Enricher` protocol, `enricher_id`
`aia-audience-dimensions-1`), producing exactly the Czech contract's seven
`enrichment_fields` (`test_the_enricher_produces_exactly_what_the_czech_contract_declares`).
EXACT, cell by cell, against the unit's own `enrich_panel` on 122 fictional rows, once with
every input and once with the leisure inputs and the financial score absent
(`tools/enrichment_capture.py`; `tests/fixtures/enrichment/`; re-captured byte-identical),
in `tests/test_population_enrichment.py`; mutating the 5.5 tier boundary or the tie rule fails
it. A missing flag column refuses with `EnrichmentInputMissing` where the unit raised an
`AttributeError`. Nothing composes the enricher yet: no research step loads the ANALYSIS view
until chunk 5, which builds `PopulationRuntime(..., enricher=AudienceDimensionsEnricher())`.

*Noted:* on a row with no media or leisure score the unit's `idxmax` relies on behaviour
pandas 2 deprecates (an all-NA row returns NA, then the fallback label; pandas 3 raises
`ValueError`). The unit pins `pandas>=2.1,<3`, the fixture is captured on pandas 2.3.3, and
the port keeps the pandas 2 result. A unit re-extracted onto pandas 3 would need a re-capture.

### 2e. Landed: the sample

`domain/population/sampling.py`: `draw_panel_sample(population, filters, n, seed) ->
PanelSample` over `select_audience` (2c), and its parts, each the unit's function on category
keys and weights: `category_keys` (`astype("string").fillna("<missing>")` of the column as
`read_csv` types it), `usable_fields`, `targets` (`_targets`), `joint_fields` and `quotas`
(`_quota_vector_fallback`), `representative_draw` (`draw_representative`), `rake` (`_rake`, with
`quantile`, NumPy's linear interpolation), `audit_composition` (`_audit`), `tolerances` and
`judge` (`:164-171`). A `PanelSample` holds each respondent (population row, `core_donor_id`,
base and raked weight, order), the `SampleAudit`, the filters as applied, the seed, the
binding's `version_id` and `content_sha256`, `SAMPLER_VERSION` and the filter's version;
`provenance()` is the JSON a run records. Nothing calls it yet: chunk 5 does.

Parity, in `tests/test_population_sampling.py` against `tests/fixtures/representative_draw/`
(`tools/sampling_capture.py`: the unit's own `draw_representative` with the MILP made to fail,
on 3,000 fictional rows; 17 draw cases and 5 direct `_rake` cases; re-captured byte-identical):
the audience, targets, quota fields and quotas EXACT (every case's winning and losing remainders
lie further apart than the unit's 1e-9 noise; the fixture records the gap); raking the unit's
picks matches its weights to 1e-12 relative (NumPy sums pairwise, AIA with `math.fsum`); the raw
and weighted audits and the verdict (PASS, PASS_WEIGHTED, refused) EXACT; the draw by property
(distinct rows, each cell exactly its quota, mean weight 1, the same seed the same sample, the
order shuffled out of the cells'). Through the canonical loader: a run's sample and its record,
and each refusal by name. Mutating the raking cap, the 700 threshold, the weight floor, the
missing-value rule, the full-cell rule, either tolerance, the no-weight refusal or the shuffle
fails the suite; two mutations are equivalent and survive (the cap's switch at 20 rows: at 20
rows neither cap can bind; `current > 0` beside a non-empty member set: weights are floored).

Corrections to the § 2a contract, from reading the unit's caller:

- **Base weight.** Not "non-positive -> 0": `sample_representative` clips the weight at
  `1e-12` before the sampler sees it (`pipeline.py:278`), so a zero-weight row is drawn only
  when its cell needs it. Ported as that (`test_a_zero_weight_row_keeps_the_units_floor_when_it_is_drawn`).
  An audience whose weights are all zero is still refused (`sampling_no_weight`).
- **`sampling_n_invalid`** is added for `n < 1`; `sampling_n_exceeds_support` keeps its
  meaning.
- **Donors.** The audit records `audience_donors` and `sample_donors` (distinct
  `core_donor_id`), `None` when the population has no donor column (§ 2b: the run says what its
  donors can support before fieldwork is paid for).
- **A full cell takes no seat** (Findings): the one place AIA draws where the unit refused.

### 3a. The persona contract (2026-10-12)

Unit anchors are under `legacy/npc-panel-18.6.6/app/`, frozen. Nothing under its `tests/`
pins persona content, so parity is by capture from the unit's own functions, as in 2c-2e.

**What 18.6.6 ran.** `RUN_DEFAULTS["persona_mode"] = "calibrated"` (`runtime_config.py:149-152`).
`generate_persona_text` (`pipeline.py:528-784`) resolves it through
`persona_calibration.resolve_effective_mode` (`persona_calibration.py:131-153`), which returns
`core` when no active calibration profile exists (`:135-137`). None ships: neither the unit's Git
tree nor its data bundle (`data-manifest.json`) has `data/persona_calibration/active_profile.json`.
So every live 18.6.6 persona was **`core`, adaptive** (`adaptive_persona = True`, `:552`). Adaptive
mode drops the HEXACO anchors, "Povaha", the life trajectory, dispositions, attitudes and the
style line (`:655-739`); none of them needs the population-wide z-scores. AIA ports that mode
and no other. `full`, `demographics` and `none` are the persona ablation's arms (chunk 7), not
fieldwork; `PERSONA_MODE = "calibrated->core (no active profile)"` is recorded in the sample's
provenance.

**The profile, in the unit's order** (`pipeline.py:560-784`), as `KEY: value` lines turned into
first-person prose by `_first_person_persona` (`:450-501`), at most 185 words, cut at the last
`. ` or `; ` past 55 % (`:491-501`):

1. Base (3b): `pohlavi`, `vek` (exact years, else `_age_band_label`), `vzdelani`, `kraj`.
2. Socio-economic and household (3b): `prijem_osobni_mesicni` else `prijem_cisty_mesicni`
   (`_income_band_label`, labelled by `prijem_definice`), `prijem_pozice_0_1` else
   `prijem_decile`, `zamestnani_status` (+ `is_student`), `occupation_major` (the ISCO map),
   `velikost_domacnosti`, `pocet_deti_celkem`, `has_partner` / `partner_cohabiting`,
   `zdravi_sebehodnoceni` (only for the topics `zdravi`, `mentalni_zdravi`),
   `kraj_kvalita_zivota_poradi`. `trida_spolecenska` is never shown (adaptive, `:639-642`).
3. Behaviour (3d): `persona_depth.deep_profile_text(row, topics, mode="core", adaptive=True)`
   (`persona_depth.py:497`): `persona_grounded.grounded_profile_text` (`persona_grounded.py:270`)
   over `PERSONA_SIGNAL_CATALOG_v17.csv` (in the unit's data bundle; AIA imports it as the
   `PERSONA_SIGNAL_CATALOG` companion, `czech.py:82`) and `PERSONA_VALUE_LABELS_v17.json` (unit
   configuration, `czech.py:173`): candidates whose topics meet the question's, at most 3 per
   block and one per concept, within `persona_signal_budget` (`product_policy.py:91`). The `P_*`
   compatibility fallback runs only when the catalog yields nothing. AIA records each companion's
   location at import (`application/population.py:244-249`) but hands none to a consumer; 3d adds
   one read through the canonical loader, re-verified against the contract's SHA256 (`czech.py:82`),
   never a second path to the files.
4. Household facts (3b): `dispozice.popis_faktu(row, topics)` (`dispozice.py:579`) over `F_*`.
5. The brand disclaimer for the topics `znacka`, `kampan`, `reklama` (`pipeline.py:757-762`).
   `AUDIENCE_FACTS_TEXT` (uploaded audiences, `audience_registry.py:193`) and
   `FS_SIMULATION_PROFILE` (Simulation Lab, `full_simulation.py:626`) are not panel columns: absent.

**Topics (3c).** A question's topics are its declared ones, else
`dispozice.odvod_temata(text + options)` (`dispozice.py:431`), as `dotaznik.py:1046-1057`.
AIA asks one block (at most 8 closed items) per request, as the unit's block mode did
(`dotaznik.py:985-990`): one persona per block, over the union of its items' topics.

**The policy gate.** Every column the profile reads asks
`RuntimePopulation.decide(column, PERSONA_CONSTRUCTION)`. A refused column is left out, never
replaced, and the refusal is listed once per run in the sample's provenance (field, reason). The
fields read jointly ask `decide_joint(..., client_facing=False)`; if refused, the run is refused
(`persona_joint_refused`), since a persona is a same-person combination. A catalog signal from a
`MODELED_BEHAVIOR_PRIOR` row is skipped as in the unit (`persona_grounded.py`), and every column
it names passes the same gate.

**The persona (3e).** One `Persona` per `SampledRespondent`:
- `facts`: the row's columns that the factual layer reads (`respondent_facts._DIRECT_PATTERNS`), as
  the row holds them. The unit's `zamestnan` pattern names a column the v17 panel lacks
  (`factual_layer.py:34-47`), so that question is `UNSUPPORTED` there, and here too.
- `style`: `assign_styles` over the **whole** population, as `Panel.__init__` z-scored it
  (`pipeline.py:172-173`, `styly.py:66`), then read at the sampled rows. Its id is
  `panel_row_id` when there is no `respondent_id` (`styly.py`).
- `donor_id`: `core_donor_id`; `weight`: the raked analysis weight; `lineage`: the panel's
  datasets (`licence_determinations.py`); `fictional = False`.
- the profile text per block from 3b-3d. The style line is not shown (adaptive).

**Parity.** EXACT against the unit's own `generate_persona_text(row, temata=topics,
persona_mode="calibrated")` on fictional rows, with a fictional catalog patched in for
`persona_grounded.CATALOG` and the unit's own value labels; `odvod_temata` EXACT on question
texts. Styles: EXACT against `styly.prirad_styly` over a fictional population.

**Refusals:** `persona_joint_refused`; `persona_catalog_missing` when the version has no
`PERSONA_SIGNAL_CATALOG` companion (the unit returned an empty block silently, `_catalog`,
`persona_grounded.py:63-65`).

### 3b. Landed: the profile's core

`domain/persona_profile.py`: `profile_lines(row, topics, behaviour)` (the unit's `KEY: value`
lines in its order, `pipeline.py:560-783`), `first_person` (`_first_person_persona`,
`:450-501`, cut at 185 words), `household_facts` (`dispozice.popis_faktu`), `age_band`,
`income_band`, `persona_text`; `PROFILE_VERSION` and `PERSONA_MODE`. A row is a mapping of
column to the value `read_csv` holds (`audience._typed` over the column's `column_type`); the
behavioural block (3d) arrives as lines, the topics (3c) as a list. Nothing calls it yet.

Parity, in `tests/test_persona_profile.py` against `tests/fixtures/persona_profile/`
(`tools/persona_capture.py`: the unit's own `generate_persona_text(row, temata=topics,
persona_mode="calibrated")` with the catalog pointed away, on 86 fictional rows (6 with incomes on
the band edges) and 13 topic sets, 99 cases; and its `_first_person_persona` on 6 line lists that
reach its prefix rewrites, its drops and its word cap; re-captured byte-identical): every text
EXACT, character for character. Mutating the cap, the clause floor, a band edge, a topic set, a
partner branch or a label fails the suite.

Two deliberate differences, each a guess the unit stamped on a missing cell (tested beside the
fixture, which holds neither): a missing `pohlavi` is "neuvedeno", where `str(NaN)` made it
"žena" (`pipeline.py:561-562`); a missing `is_student` is not a student, where `bool(NaN)` made an
employed person "Současně: student/ka" (`:598`). Kept from the unit, because it states the gap
rather than filling it: a missing age reads "ve věku neuvedeno".

### 3c. Landed: topics

`domain/persona_topics.py`: `question_topics` (`dispozice.odvod_temata`, `dispozice.py:431-462`)
over `TOPIC_KEYS` (its `TEMATA_KLICE`, `:348-422`, 54 topics), and `block_topics`, the union
`run_dotaznik` built for a block (`dotaznik.py:937-948`). AIA's questions declare no topics, so
each is derived from its text and options, as the unit did for a question without them.
EXACT in `tests/test_persona_profile.py` against the unit's own function on 56 fictional
questions (every topic reached; `auto`/`automaticky`, `byt`/`být`, a phrase key's first word
alone, more than five topics) and 4 blocks; the table compared with the unit's own dictionary
(`tools/persona_capture.py`; re-captured byte-identical). Mutating the phrase rule, the short-stem
rule, the `byt` and `auto`/`obec` rules, the tie order or the cap fails it.

### 3d. Landed: grounded signals

`domain/persona_signals.py`: `parse_catalog` (`persona_grounded._catalog` as `read_csv` reads the
catalog: an empty `block`, `kind`, `wave` or `topics` cell reads `"nan"`, an empty `priority` or
`min_abs_z` NaN; a `wave` column with a gap reads as float, so "ISSP 2021.0"), `parse_value_labels`,
`render` (`_render`: value labels first, then the 15 kinds, each with the unit's score),
`grounded_text` (`grounded_profile_text`: topic match, the `MODELED_BEHAVIOR_PRIOR` gate, the
specific-topic multiplier, the order, three per block, one per concept, the budget
`signal_budget`, `PRODUCT_POLICY.json:34-38`), `_compact_anchor`, `compatibility_columns`. The
`P_*` compatibility block (`persona_depth.py:521-560`) is not ported: v17 replaced it
(`persona_grounded.py:10`), and 3e refuses a population that carries its columns rather than
differ silently.

The companions reach it only through the loader: `RuntimePopulation.companion(asset_id)` hands
out the bytes `_verified_joint` already reads and checks against the recorded SHA256 at every load
(`application/population.py`), `companion_missing` otherwise
(`test_population_companions.py::test_a_loaded_population_hands_out_its_verified_companions`).
The cache keeps them with the population (about 3 MB for v17's 15 companions).

Parity, in `tests/test_persona_profile.py` against the unit's own functions with a fictional
`catalog.csv` (26 signals: every kind and evidence role, a five-signal block, a repeated concept,
a modelled prior, empty cells, an absent column, four real column names the unit's value labels
describe) and the unit's own `PERSONA_VALUE_LABELS_v17.json`, on 40 fictional `signals.csv` rows:
the parsed catalog; every signal's text and score on every row (`_render`); 6 anchors
(`_compact_anchor`); `grounded_profile_text` and the whole persona with its signals on 60 cases
across 11 topic sets. All EXACT; re-captured byte-identical. Mutating a score constant, the
specific-topic multiplier or the generic set, the per-block cap, the concept rule, the prior gate,
the order, the budget, a threshold, the anchor rules or the `"nan"` reading fails it.

One difference, found by CI: an empty catalog `priority` reads NaN, so the signal's score is NaN,
and `candidates.sort(key=lambda x: (-x[0], x[1]["column"]))` (`persona_grounded.py:290`) leaves a
NaN key where the sort's internals put it. The unit's own output then differs by Python version:
captured on 3.13, the first fixture ranked `SIG_risk01` (empty priority) before `SIG_brand`; CI's
Python ranked it after (PR #315, run 38250340111, `test_the_grounded_signals_are_the_units[3]`).
AIA ranks a NaN score last (`test_a_signal_with_an_unknown_priority_ranks_last`); the fixture's
ranked signals all carry a priority, and the empty one sits on `SIG_raw`, which never renders, so
the parse of an empty priority is still compared.

### 3e. Landed: panel personas

`domain/panel_persona.py`: `panel_personas(population, sample) -> PanelPersonas`, one `Persona`
per sampled respondent (id `panel_row_id`, donor `core_donor_id`, the sample's raked weight,
lineage `PANEL_DERIVED_DATASETS`, `fictional=False`, the factual layer's fields as the row holds
them, styles from `assign_styles` over every row of the population, as `Panel.__init__` styled its
whole panel), and `PanelPersonas.plan(spec, persona)`: `plan_respondent` with each block's profile
(`RespondentPlan.profiles`, by block index) built from that block's topics. `build_request` shows
`plan.profile(block)`: the block's profile for a panel persona, `persona.profile()` otherwise, so
the fictional roster's requests are unchanged. `Persona.facts` widens to `str | int | float | bool`
to hold a typed row's values. Nothing calls it yet: chunk 5's executor does, after the sample.

**The joint gate, refined from § 3a.** One `decide_joint` over every persona column would refuse
every v17 persona: the catalog's signals come from matched donor blocks, and the certificate
refuses cross-block same-person joints (`CORE_JOINT_STATUS.json`: `core_same_person_joint`,
`specialist_block_internal_joint`, `cross_block_same_person_joint: false`). It is also not what
18.6.6 claimed: each matched signal carries "statisticky přiřazený celý donor blok"
(`persona_grounded.py:93-95`). So the core fields (every dictionary block not in the certificate's
`matched_blocks`) are decided jointly, and each matched block's fields within that block; a
refusal refuses every persona (`persona_joint_refused`). The certificate certifies `v17_4_0`, the
LIVE panel a run binds (its `panel_sha256` is `deploy/develop/population/v17.files:17`); a run
bound to an uncertified version gets no personas
(`test_a_population_whose_joint_use_is_refused_gets_no_personas`).

Tests, in `tests/test_panel_persona.py`, through the canonical loader on a population built from
the persona fixture's rows with the fictional catalog and the unit's value labels as companions:
a persona's profile equals what 18.6.6 showed for its row and topics (`expected.json`, EXACT), each
block gets the profile of its own topics and the request carries it, styles are the population's
(not the sample's), a policy-refused field is left out and recorded, the joint gate, and every
refusal by name. Mutating the policy gate, the joint grouping, the age check, the compatibility
check, the style scope, the weight or the block profile fails them.

**3. Persona.** Port `generate_persona_text` (persona modes, top-k traits,
structured format). Every field shown or used asks
`RuntimePopulation.decide(field, FieldUse.PERSONA_CONSTRUCTION)` and, combined,
`decide_joint`. The fact layer reads the row's columns: a question the panel answers
becomes DIRECT (answered by code) instead of UNSUPPORTED. Styles from
`assign_styles` over the real rows. Real weights and donor ids. Parity fixtures.

### 4a. The origin contract (2026-10-12)

ADR 0024 decides what `MODELLED_AI_PANEL` is; this is where it lands. Anchors @ `c1c8ec1`, under
`packages/aia_core/src/aia_core/` unless a path says otherwise.

**What a new origin gets today.** `DataOrigin` has two members (`domain/fieldwork.py:50-62`), both
in `NON_EVIDENCE_ORIGINS` (`:66-68`), and every reader asks "is it in that set?". So a new member
is refused only where a reader demands membership, and is read as **real, measured data**
everywhere else:

| Site | Today | A new origin |
|---|---|---|
| `domain/evidence/instrument.py:73-80` `_require_simulated` | `-1` for both | refused (fail-closed) |
| `domain/analysis/native.py:465-476` `native_evidence` | via the instrument book | refused |
| `domain/ai_respondent.py:685-689` `assemble_dataset` | fictional only | refused |
| `apps/executors/.../ai_fieldwork.py:122-132` guard | fictional only | refused |
| `domain/evidence/admission.py:244` client-facing gate | denylist | **passes** (and so does `None`) |
| `domain/analysis/native.py:531-539` preflight | denylist | **passes** (`FIELD_INTERNAL_ONLY` still blocks, `:540-546`) |
| `domain/analysis/harness.py:136-143` labels, `_FRAME` `:82-88` | "simulated" | **read as real**; the frame calls every respondent fictional |
| `application/report.py:153,294`, `contextual_report.py:334`, `apps/executors/.../report.py:135` | synthetic callouts | **no callout, no disclosure**: "Výzkum" |
| `domain/research_sociomapping.py:358-359`, `application/sociomapping_report.py:325,347` | "Fiktivní data" | **no callout** |
| `domain/design_reuse.py:36,77-84` | synthetic | "unlabelled" (safe, wrong) |
| `apps/executors/.../research.py:396` progress | "fiktivní data připravena" | **"sběr dat dokončen"** (fieldwork done) |
| `apps/api/.../routers/research.py:212,938,1067,1197,143` | `synthetic` flags | **synthetic: false**, no modelled flag |
| `apps/web/src/lib/research-execution.ts:85-94`, `ExecutionSteps.tsx:491,639,668,855,976`, `memory.ts:55`, `ObjectMapView.tsx:60`, `SociomappingView.tsx:50,308` | "Fiktivní data" | **no label**; the raw string shown as a fault chip |
| `tests/test_evidence_admission.py:233` | `set(DataOrigin) == NON_EVIDENCE_ORIGINS` | fails: the one exhaustive test |

**Decisions.**

1. **4b, the origin and the gate.** `DataOrigin.MODELLED_AI_PANEL`; not in `NON_EVIDENCE_ORIGINS`.
   `CLIENT_ADMISSIBLE_ORIGINS = {MODELLED_AI_PANEL}` (ADR 0024 §2), and both client-facing gates
   (`admission.py:244`, `native.py:531`) become the allowlist: any other origin, `None` and any
   member added later, is refused client-facing. A non-evidence origin keeps its code
   (`SYNTHETIC_DATA_ORIGIN`); anything else outside the list is `ORIGIN_NOT_ADMISSIBLE`.
   Nothing becomes client-facing in 4b: `FIELD_INTERNAL_ONLY`, the joint certificate and (4e) the
   validation still block. `assemble_dataset` derives the origin from the personas: every persona
   fictional -> `SYNTHETIC_AI_FICTIONAL`; every persona panel-built (not fictional, lineage
   `PANEL_DERIVED_DATASETS`) -> `MODELLED_AI_PANEL`; anything else refused (mixed rosters are
   refused, not labelled). The exhaustive test becomes a partition test: every member is either
   non-evidence or admissible, never both, never neither.
2. **4c, one reading, every Python surface.** `domain/fieldwork.py` gains `origin_kind(origin) ->
   SIMULATED | MODELLED | UNKNOWN` (`None` and an unrecognised string are `UNKNOWN`), the one
   function every label reads; no surface tests set membership itself. `ModuleLabels` gains
   `modelled_respondents`; the harness frame, the report (beside the number, with
   "modelováno: AI respondenti z populace", ADR 0024 §7), the sociomapping view and report,
   design reuse, the progress text ("modelovaná data připravena") and the API's flags read it.
   An `UNKNOWN` origin is labelled unknown, never real.
3. **4d, the web client.** The same three-way vocabulary in `research-execution.ts`, used by every
   surface listed; the modelled chip and banner say "modelováno: AI respondenti z populace";
   `ObjectMapView`'s prefix test goes; an unknown origin is shown as unknown, never as fieldwork.
4. **4e, the evidence policy and validation** (ADR 0024 §3-§5): `aia-instrument-evidence-2` for
   `MODELLED_AI_PANEL` (aggregate only, MODELED with `MODELED_VALUE` and `SCOPE`), the validation
   fingerprint and `effective_validation_status` as the client-facing gate, support counted in
   donors. Split again when it starts; it is the only sub-chunk that can open a client-facing
   route, and it opens none until a validation is recorded.

Out of scope here: producing the origin (chunk 5's executor), the Sociomap's `INTERNAL_ONLY` (D6).

### 4b. Landed: the origin and the allowlist

`domain/fieldwork.py`: `DataOrigin.MODELLED_AI_PANEL`, not in `NON_EVIDENCE_ORIGINS`;
`CLIENT_ADMISSIBLE_ORIGINS = {MODELLED_AI_PANEL}`. Both client-facing gates are the allowlist
(`domain/evidence/admission.py`, `domain/analysis/native.py` preflight): a synthetic origin keeps
`SYNTHETIC_DATA_ORIGIN`, a missing or undecided one is `ORIGIN_NOT_ADMISSIBLE` (new,
`evidence/gate.py`). `domain/ai_respondent.py`: `dataset_origin(personas)`, which
`assemble_dataset` now calls: all fictional -> `SYNTHETIC_AI_FICTIONAL`, all panel-built (not
fictional, lineage `PANEL_DERIVED_DATASETS`) -> `MODELLED_AI_PANEL`, anything else refused. Nothing
became client-facing: `FIELD_INTERNAL_ONLY` and the instrument policy (`-1` refuses the new
origin) still hold.

Tests: `test_every_origin_is_decided_once` (the partition replaces the exhaustive denylist test),
`test_only_an_admissible_origin_passes_the_client_facing_gate`,
`test_a_row_with_no_origin_no_longer_slips_the_origin_gate`,
`test_the_dataset_origin_is_derived_from_the_personas_never_chosen`,
`test_a_panel_dataset_says_it_is_modelled_and_not_synthetic`. The shared `evidence_row` fixture
defaults to the admissible origin: 81 tests built client-facing rows with no origin, a state the
one production builder (`native.py:334`, which stamps the dataset's origin) never makes.

### 4c. Landed: one reading of an origin, every Python surface

`domain/fieldwork.py`: `OriginKind` (SIMULATED / MODELLED / UNKNOWN), `origin_kind(origin)` (`None`
and an unrecognised string are UNKNOWN; there is no measured kind) and `MODELLED_DISCLOSURE`
("modelováno: AI respondenti z populace", ADR 0024 §7). Every label below reads `origin_kind`; no
surface tests set membership:

* analysis harness: a modelled frame beside the simulated one (`harness_frame` refuses an UNKNOWN
  kind; `harness_sha256` covers both frames, so it moves once); `harness_labels` and
  `ModuleLabels` gain `modelled_respondents` (default `False`: artifacts written before read);
  `classify_analysis_material` keeps a modelled run Class A.
* internal report (`application/report.py`): the introduction always carries a "Rámec
  interpretace" callout and Limity a limitation, one text per kind; `RESEARCH_SUBTITLE` is the one
  subtitle table (executor report, contextual report): "Modelovaný výzkum", "Výzkum neznámého
  původu", never plain "Výzkum". The executor's report metadata records `data_origin`.
* Sociomapping (`research_sociomapping.py`, `application/sociomapping_report.py`, its executor):
  the stored result is unchanged (`synthetic_data` now read through `origin_kind`); the report's
  note and `SOCIOMAPPING_SUBTITLE` read the stored `data_origin`, an unknown one said; a
  `synthetic_data` flag that disagrees with the origin's kind is refused.
* design reuse: `SourceLabels.modelled` (default `False`: stored labels read); only an origin of
  unknown kind, or none, is unlabelled.
* fieldwork progress (`aia_executors/research.py` `_DATA_READY`): "modelovaná data připravena";
  no kind says "sběr dat dokončen".
* API (`routers/research.py`): a step's `data_origin_kind`; analysis and both report reads add
  `modelled` and `data_origin_kind` (mixed kinds read UNKNOWN; a report artifact written before
  `data_origin` was recorded reads SIMULATED from `synthetic`, else UNKNOWN);
  `DesignSourceLabels.modelled`.

Tests: `test_every_origin_has_one_kind_and_nothing_reads_as_measured`,
`test_a_modelled_origin_is_framed_as_modelled_never_fictional_or_measured`,
`test_modelled_respondents_are_client_material_never_class_c`,
`test_a_modelled_run_is_framed_as_modelled_in_the_introduction_and_the_limits`,
`test_every_origin_is_said_and_an_unknown_one_is_never_read_as_real`,
`test_a_synthetic_flag_beside_an_origin_of_another_kind_is_refused`,
`test_a_modelled_run_is_labelled_modelled_never_unlabelled_or_synthetic`,
`test_labels_recorded_before_the_modelled_origin_still_read`,
`test_the_fieldwork_step_never_says_fieldwork_is_done_for_answers_no_person_gave`,
`test_a_report_artifact_reads_its_origin_kind_and_an_unknown_one_is_never_real`.

Not here: the "beside the number" mark in the DOCX ledger is 4e's, with the policy that makes a
modelled number admissible; the web client is 4d.

### 4d. Landed: the web client's labels

`apps/web/src/lib/research-execution.ts`: `OriginKind`, `originKind` (the same three-way reading as
`domain/fieldwork.py`; `null`, empty and unknown strings are UNKNOWN), `MODELLED_ORIGINS`,
`MODELLED_DISCLOSURE`; `stepOriginKind` (the API's `data_origin_kind` when it is one of the three,
else the page's own reading; `null` when the step stamped no origin), `runOriginKinds`,
`isModelled`, `hasUnknownOrigin` beside `isSynthetic`, and `resultOriginKind` for an analysis or a
report (an older API's `synthetic` flag reads SIMULATED, its absence UNKNOWN). Every surface reads
them:

* `ExecutionSteps.tsx`: `OriginBanners` (fictional, modelled, unknown; each said when it applies) on
  Progress and Results; the run list's chips; a step's chip says its kind ("Modelovaná data"), the
  raw origin moved to its title (it was a fault chip); the report and analysis notes, one text per
  kind.
* `ObjectMapView.tsx`: the `startsWith("SYNTHETIC")` test is gone; one origin chip per kind
  (`object-map-origin`, `data-origin-kind`), and a map with no recorded origin says unknown.
* `SociomappingView.tsx`: one sentence per kind, unknown said.
* `memory.ts`: `RunDataLabel` gains `modelled` (an unknown origin outranks it); `sourceLabelWords`
  says `modelled`.
* `api.ts`: optional `data_origin_kind` / `modelled` on steps, analysis, reports and design-source
  labels (absent from an older API).

Tests: `research-execution.test.ts` (three new), `memory.test.ts`
(`labels a modelled run modelled, and an origin it has no word for unknown, never good`),
`ObjectMapView.test.tsx` (`says modelled data is modelled, never fictional and never measured`),
`ExecutionSteps.test.tsx` (`says a modelled run is modelled on its banner and its steps…`,
`says an origin it has no word for is unknown, never real`).

### 4e. The split (ADR 0024 §3-§5, §7)

Anchors @ `2dc834b1`, under `packages/aia_core/src/aia_core/domain/evidence/`.

* **4e1, the `-2` policy.** `instrument.py` declares by origin: a simulated origin keeps `-1`
  unchanged (`INSTRUMENT_POLICY_VERSION`, `_require_simulated` :73-80); `MODELLED_AI_PANEL` gets
  `aia-instrument-evidence-2`, status `InstrumentStatus.MODELLED_PANEL_RESPONSE`, provenance
  `MODELLED`, and the rules its declared use extracts (`NEVER_MEASURED_FACT`,
  `PERSON_VALUE_MODELED`, `AGGREGATE_ONLY`, `REQUIRES_SCOPE`, `REQUIRES_MODELED_DISCLOSURE`).
  Two AIA-only rules beside them, never extracted from prose (like `INTERNAL_ONLY`,
  `field_policy.py:143`): `MODELED_DISCLOSURE_ALWAYS` -- the dictionary's
  `REQUIRES_MODELED_DISCLOSURE` fires only on a *measured* claim (`claims.py:155-161`), which
  `NEVER_MEASURED_FACT` already refuses, so on its own it would let a modelled claim reach a
  client undisclosed -- and `INTERNAL_ONLY`, which 4e1 always adds. Any other origin, `None`
  included, is still refused.
* **4e2, the validation.** `validation.py` gains the respondent system fingerprint (ADR §4: the
  respondent prompt SHA-256, persona builder and mode, sampler version, population version,
  model binding, response-process version; every component required) beside today's panel
  fingerprint. `instrument_policy_book` takes the validation state and the current respondent
  system; only `HOLDOUT_VALIDATED` earned on that fingerprint (`effective_validation_status`
  :115) drops `INTERNAL_ONLY` from `-2`. Smoke never does; a stale one never does. The book's
  identity (`source_sha256`) carries the system fingerprint and the effective status, so a
  module judged under one validation is not reused under another.
* **4e3, native evidence.** `analysis/native.py` (`native_evidence` :465-476) builds `-2` for a
  modelled dataset, with the respondent system the run records; no validation is stored
  anywhere yet (chunk 7 earns the first), so every modelled claim stays internal.
* **4e4, support in donors.** Native evidence already asks donor support
  (`native.py:257-258`, `requires_donor_support=True`); a test proves a modelled run of 1,000
  respondents on 40 donors is assessed as 40-donor evidence (ADR §5), never as 1,000.
* **4e5, the report.** The DOCX marks a modelled number with "modelováno: AI respondenti z
  populace" beside it and, when a validation holds, its date and fingerprint (ADR §7).

**4e1 landed.** `evidence/instrument.py` declares by origin kind (`_declared`): simulated ->
`-1`, unchanged byte for byte (its declaration identity does not move); `MODELLED_AI_PANEL` ->
`MODELLED_INSTRUMENT_POLICY_VERSION` (`aia-instrument-evidence-2`),
`InstrumentStatus.MODELLED_PANEL_RESPONSE`, the rules `MODELLED_INSTRUMENT_RECOMMENDED_USE`
extracts plus `MODELED_DISCLOSURE_ALWAYS` and `INTERNAL_ONLY`; anything else refused.
`instrument_policy_version(origin)` is what a module's `AuthoritySummary.field_policy_version`
now records (`application/analysis_results.py`; it recorded `-1` for every origin). `claims.py`:
a client-facing claim on a `MODELED_DISCLOSURE_ALWAYS` field needs `Disclosure.MODELED_VALUE`
whatever its basis. Because `native_evidence` asks the book, a modelled run's evidence is now
declared under `-2` -- internal only -- ahead of 4e3, which binds it to the respondent system.

Tests: `test_a_modelled_origin_is_declared_under_its_own_policy_chosen_by_the_origin`,
`test_the_two_policies_never_share_a_declaration_identity`,
`test_without_a_validation_a_modelled_claim_is_internal_even_fully_disclosed`,
`test_a_client_facing_modelled_claim_needs_both_disclosures_whatever_its_basis`,
`test_a_modelled_answer_is_never_a_measured_fact_nor_one_persons` (both surfaces),
`test_a_segment_claim_on_modelled_answers_is_allowed_internally`,
`test_no_dictionary_can_declare_the_modelled_status`,
`test_internal_only_is_never_extracted_from_dictionary_prose` (now both AIA-only rules),
`test_a_modelled_run_is_judged_under_the_modelled_policy_and_stays_internal`.

**4e2 landed.** `evidence/validation.py`: `RESPONDENT_SYSTEM_COMPONENTS` (the respondent
prompt's SHA-256, persona builder, persona mode, sampler version, population version, model
binding, response-process version) and `respondent_system_fingerprint` (every component
required, none blank, no extra name, the prompt a SHA-256), beside the panel's
`system_fingerprint`; `lifts_internal_only(state, current)`: true only for `HOLDOUT_VALIDATED`
earned on `current` -- none, stale, smoke or no current system keep a claim internal.
`evidence/instrument.py`: `instrument_policy`, `instrument_declaration_sha256` and
`instrument_policy_book` take `respondent_system` and `validation`; `-2` drops `INTERNAL_ONLY`
only when `lifts_internal_only`, every other rule kept. A modelled declaration's identity binds
the system and whether the validation lifted it (a stale validation is the same declaration as
none). A simulated origin is never validated: a system or a validation for it is refused, and
`-1`'s identity does not move.

Tests: `test_the_respondent_system_fingerprint_moves_with_every_component`,
`test_the_respondent_system_refuses_a_missing_or_blank_component`,
`test_the_respondent_system_refuses_a_name_it_does_not_bind_and_a_prompt_not_hashed`,
`test_only_a_current_holdout_lifts_internal_only`,
`test_a_current_holdout_takes_a_fully_disclosed_modelled_claim_to_a_client`,
`test_no_validation_a_stale_one_or_smoke_keeps_a_modelled_claim_internal`,
`test_the_declaration_identity_moves_with_the_system_and_the_validation`,
`test_simulated_answers_are_never_validated_and_their_identity_never_moves`,
`test_a_validation_needs_the_current_system_and_a_system_is_a_fingerprint`.

**4e3 landed.** `domain/fieldwork.py`: `RESPONDENT_SYSTEM_METADATA` (`"respondent_system"`), the
fieldwork dataset artifact's metadata key for the respondent system's components; chunk 5's
executor writes it. `application/analysis_results.py`: `NativeSources.respondent_system`, read by
`_respondent_system` for a modelled origin only (a simulated dataset names none, whatever it
recorded), fingerprinted by `respondent_system_fingerprint`; a record that does not fingerprint
is refused (`SourcesRefused("respondent_system")`), never read as no system.
`domain/analysis/native.py`: `native_evidence(respondent_system=, validation=)` passes both to
the book, so they enter the evidence's system fingerprint. `prepare_module` passes the dataset's
system and `validation=None`: nothing stores a validation yet, so a modelled run's analysis is
judged internal, bound to the system it came from.

Tests: `test_a_modelled_run_is_bound_to_its_respondent_system_and_lifted_only_by_its_validation`,
`test_a_modelled_dataset_names_its_respondent_system_and_a_bad_record_is_refused`.

**4e4 landed (a test, no code).** Native evidence already re-assesses support from the donors the
aggregate counted (`domain/analysis/native.py` `reassess_support`, `requires_donor_support=True`);
`test_a_modelled_run_counts_its_donors_not_its_respondents` proves it for a modelled run: 1,000
respondents on 40 donors are INDICATIVE (under the donor floor of 50), the same answers on 1,000
donors REPORTABLE, and on 20 donors (under 25) no row is shown at all.

**4e5 landed.** `domain/report/evidence.py`: `EvidenceLedger.modelled_panel(refs)` -- does any
held ref rest on `MODELLED_AI_PANEL` (read through `origin_kind`). The DOCX
(`infrastructure/report_docx/`) prints "(modelováno: AI respondenti z populace)" beside such a
number wherever one is printed: an inline value (before "orientační"), a paragraph's marks, a
callout's or finding's title marks, a KPI tile; a table or a figure says it once in its caption
beside its base and grade, not in every cell. A simulated run's report never says it (its own
"syntetičtí respondenti" callout frames it, 4c). The grade mark is unchanged.

Not here: the validation's date and fingerprint beside the disclosure (ADR §7). No validation is
recorded, and `ValidationState` carries no date; chunk 7, which records the first, prints them.

Tests: `test_only_numbers_on_ai_respondents_from_the_population_carry_the_modelled_words`;
`test_values_print_as_the_evidence_rounded_them_with_intervals`,
`test_captions_number_figures_and_state_base_and_suppression` and
`test_the_caption_numbers_titles_and_states_the_base` now expect the words: every client-facing
number in the shared `report_ledger` rests on the one admissible origin.

Nothing in 4e records a validation: chunk 7's ablation and holdout earn the first one. Until then
4e changes no client-facing outcome; it decides what a validation will unlock and what it will not.

### 5. The persona source (contract, 5a)

Anchors @ `8d89a682`. Today `AIFieldwork.produce` builds `fictional_roster(spec.n, seed)`
(`apps/executors/src/aia_executors/ai_fieldwork.py`) and refuses any non-fictional persona before a
call (`persona_source_unsupported`). Everything a panel source needs exists and is called by
nothing: `draw_panel_sample` (2e), `panel_personas` and `PanelPersonas.plan` (3e),
`dataset_origin` (4b), `respondent_system_fingerprint` and `RESPONDENT_SYSTEM_METADATA` (4e).

**Decisions.**

1. **The source is pinned to the run at start, never read at execution.** `ResearchRuns.start`
   records `persona_source` in the run's metadata (`fictional_roster` | `panel`) beside the
   methods it pins (`application/research.py:315-384`): `panel` only when the API's
   `AIA_AI_POPULATION_PERSONAS_ENABLED` is on and the source is `ai_runtime`; otherwise
   `fictional_roster`. A panel run is its own identity (its idempotency key carries
   `:personas:panel`, so a start never returns the revision's fictional run), and a panel start
   with no population established is refused (`PanelPopulationMissing`, API 409
   `population_not_established`) -- never started fictional instead (amended in 5c: the first
   draft fell back to the roster). A retry keeps the original's; a run
   recorded before 5c has no key and reads as `fictional_roster`. Reading the switch at
   execution would let a retry of a fictional run come back modelled, under the same run.
2. **The worker composes the panel path only behind the same switch**, off by default and in
   test; on, it requires `AIA_POPULATION_ASSET_ROOT` (fail closed at start, like every
   `AIA_AI_*` key). A `panel` run on a worker without it **parks**
   (`RUNTIME_UNAVAILABLE`, `panel_personas_unavailable`), never falls back to the roster.
3. **The panel path, in order, each refusal by name and before any call is paid for:**
   `PopulationRuntime.load_for_run` (the run's recorded binding, the ANALYSIS view through
   `AudienceDimensionsEnricher`) -> `draw_panel_sample(population, spec.selection's audience
   filters, spec.n, fieldwork_seed(spec))` -> `panel_personas(population, sample)` ->
   `PanelPersonas.plan(spec, persona)` per respondent. A population that does not load parks
   (`population_unavailable`); a `SamplingRefused` or `PersonaRefused` fails the step with its
   own reason (`sampling_unrepresentative` included: OI-99 is the owner's, and until it is
   decided a small study is refused, never drawn smaller). Material is classified with the
   panel lineage; the licence gate allows it on `bedrock-eu-primary` only (OI-61).
4. **The audience filters are applied.** The design's recorded filters (`spec.selection`) are
   what the sample draws under, as 18.6.6 did. The compiled spec is not changed: its
   `applied: false` is part of its fingerprint and says what the specification records; the
   sample's provenance says they were applied, and to how many rows.
5. **What a modelled dataset records.** The origin is derived (`MODELLED_AI_PANEL`, 4b). The
   artifact's provenance names the source, the binding (version, content SHA-256, weight role),
   the sample (`PanelSample.provenance()`), the persona source (`PanelPersonas.provenance()`:
   persona source and profile versions, mode, refused fields) and the seed. Its metadata carries
   `RESPONDENT_SYSTEM_METADATA`: prompt SHA-256, persona builder (`PANEL_PERSONA_VERSION` /
   `PROFILE_VERSION`), persona mode, `SAMPLER_VERSION`, the binding's population version, the
   model binding the preflight resolved (provider / model / route), and the response process
   (`BEHAVIOR_VERSION` / `FACT_LAYER_VERSION`) -- so analysis is judged on it (4e3).
6. **Cost.** A panel profile is longer than the roster's four facts. 5e measures the request
   characters per respondent and block on the fictional test population against the roster,
   states the token estimate and the reservation it implies, and says that the real number is
   the first develop run's ledger; nothing is called to measure it.
7. **Stale reasons.** The comments that give OI-61 as why fieldwork is fictional change with 5c-5d
   (`domain/ai_respondent.py:19-24`, `application/research.py:176,216`,
   `apps/api/src/aia_api/routers/research.py:187`, `apps/web/src/lib/research-execution.ts`): the
   reason is now the pinned source.

Out of scope: the screens (chunk 6) and any client-facing route (chunk 7's validation).

**5b landed.** `domain/panel_source.py`: `panel_plans(population, spec, seed)` draws the sample
under the design's recorded audience filters, builds the personas for exactly those rows and a
plan per respondent, in that order; each refusal is its own step's (`SamplingRefused`,
`PersonaRefused`), before anything else is built. `PanelPlans.provenance(population)` is what the
dataset records (source, binding, sample, personas, `fictional: false`).
`respondent_system(population, model_binding=)` gives ADR 0024 §4's components, the model binding
being what the gateway resolves. `PANEL_SOURCE = "panel"`, the value a run pins (5c).

Tests (`test_panel_source.py`, over the sampler's 3,000 fictional rows with the persona
companions): `test_a_panel_run_is_sampled_built_and_planned_in_that_order`,
`test_the_designs_audience_filters_are_what_the_sample_draws_under`,
`test_a_sampling_refusal_surfaces_by_name_before_any_persona_is_built` (n over support, and n = 8
refused as unrepresentative: OI-99), `test_a_persona_refusal_surfaces_by_name`,
`test_the_respondent_system_names_every_component_and_fingerprints`.

**5c landed.** `domain/fieldwork.py`: `PersonaSource` (`fictional_roster` | `panel`) and
`persona_source_of(metadata)` (no key: the roster; an unknown value refused).
`application/research.py`: `ResearchRuns.start(persona_source=)` pins it in the run's metadata and
the `run` step's input; a panel run's key carries `:personas:panel`; a panel start needs
`ai_runtime` and an established population (`PanelPopulationMissing`); the population note's
`read_by_fieldwork` is true exactly for a panel run. `retry` passes the original's pin. API:
`AIA_AI_POPULATION_PERSONAS_ENABLED` (`Settings.ai_population_personas_enabled`, off by default) decides a
new run's pin; `persona_source` on every run response; 409 `population_not_established`. The switch is named for the population, not "panel":
`test_session_api.py::test_the_session_and_its_gate_need_nothing_of_18_6_6` refuses any API
setting naming "panel", so the 18.6.6 panel gate cannot return (ADR 0018). The step
templates keep `consumes_population: false`: whether fieldwork reads the population is the run's
pin, enforced at start, not the template's.

Tests: `test_a_run_pins_its_persona_source_and_a_run_before_the_pin_reads_as_the_roster`,
`test_a_panel_run_is_its_own_run_reads_its_population_and_needs_one`,
`test_a_retry_keeps_the_persona_source_its_original_pinned` (both sources),
`test_a_run_says_who_its_respondents_are_and_a_panel_start_needs_a_population`,
`test_a_run_stored_before_the_pin_reads_as_the_fictional_roster`.

**5d landed.** `apps/executors/src/aia_executors/ai_fieldwork.py`: `AIFieldwork` reads the run's
pin from its step input. A panel pin on a worker without a population loader parks
(`panel_personas_unavailable`); with one, the population the run recorded is loaded in the step's
transaction (`population_loader`: `PopulationRuntime(CZ_SYNTHETIC_V17, the asset source,
AudienceDimensionsEnricher).load_for_run`; a load failure parks, `population_unavailable`), then
`panel_plans` -- a `SamplingRefused` or `PersonaRefused` fails the step by its own reason before any
call. The rest is the roster's path: Class A (panel personas are never internal), the gateway's
gates, one request per respondent per block. The provenance's `persona_source` is
`PanelPlans.provenance`; `ProducedDataset.respondent_system` (from the preflight's resolved model
binding) goes into the dataset artifact's metadata as `RESPONDENT_SYSTEM_METADATA`
(`aia_executors/research.py`). `ai_runtime.py`: `AIA_AI_POPULATION_PERSONAS_ENABLED` (off by
default) needs `AIA_POPULATION_ASSET_ROOT` (refused at start without it); `build_ai_fieldwork(population=)`
replaces the loader for a test's fictional population and never adds a path the switch did not.
The OI-61 reasons are rewritten (`ai_respondent.py`, `ai_fieldwork.py`, `research-execution.ts`).

Tests (`apps/executors/tests/test_ai_fieldwork.py`, over the sampler's 3,000 fictional rows
imported and established LIVE in the worker's database, `grounded_world.py`):
`test_a_run_pinned_to_its_population_is_answered_by_respondents_drawn_from_it` (the real worker,
200 respondents: `MODELLED_AI_PANEL`, row and donor ids, panel provenance, Class A on the ledger,
the respondent system in the metadata, aggregate and sociomap over it),
`test_a_design_the_population_cannot_sample_fails_before_any_call`,
`test_a_population_that_cannot_build_personas_fails_before_any_call`,
`test_the_population_switch_needs_the_directory_it_reads`,
`test_a_run_pinned_to_its_population_waits_on_a_worker_without_that_path`.

**5e, cost (measured, nothing called).** Request characters, built by `build_request` exactly as
the executor builds them, never sent. Measured @ `2163d0e8` with two throwaway tests that were not
committed:

| What | Requests | Mean chars | Max chars | Profile chars (mean / max) |
|---|---|---|---|---|
| Fictional roster, 2-question design, n 200 | 200 | 3,018 | 3,174 | none |
| Population, same design, the sampler's rows (few profile columns, no signals) | 200 | 2,849 | 2,908 | 147 / 206 |
| Population, the 3e fixture's 39 rows (every profile column, catalog signals) | 39 | 3,561 | 3,687 | 832 / 958 |
| The same 39 personas without a profile (`plan_respondent`) | | 3,052 | | none |

So a full profile adds about 509 characters to a request (+17 %), bounded by the 185-word cap and
the signal budget (3-9 signals): the longest seen is 958. At an assumed ~3 characters per token
for Czech (an assumption, not measured), that is ~170 input tokens more per request, ~$0.0005 per
request at $3 / MTok input -- far inside the per-request reservation
(`AIA_AI_FIELDWORK_RESERVATION_USD`, which caps a request at the model's window and output
limit), so the run's cost ceiling does not move. The real number is the first develop run's
ledger (`ai_usage_events.input_tokens` per call), which records what Bedrock counted.

### 6. Screens (contract, 6a)

Anchors @ `abd3ce88`. The audience step (`apps/web/src/components/rehome/research/AudienceStep.tsx`)
says "V AIA zatím není" for four things the unit computed from its panel and audience store:
the factor catalogue and its filters (`FilterEditor`, :206-233), the feasibility preview, the
special subpanels (:146) and customer audience upload (:113). Their pure ports are kept and
parity-tested in `apps/web/src/research/audience.ts` (`filterableFactors`, `setAudienceCategory`,
`setAudienceRange`, `applyPopulationSubpanel`, `previewVerdict`), waiting for a population to
compute from. Since 5c a panel-pinned run draws its sample under the design's recorded filters
(`domain/panel_source.py:86`), so filters now change who is asked -- but only in a run pinned to
its population. Readiness still says they are never used (`domain/research_design.py:655-661`).

**Decisions (owner, 2026-10-12, in session).**

1. **The factor catalogue is computed once per version, at import, and kept beside it.** The
   unit computed it on every request from the loaded panel (`audience_dimensions.catalog`,
   `audience_dimensions.py:239`, served at `/api/audience/dimensions`, `ui_server.py:1755`). AIA
   computes it once, from the version's ANALYSIS view, keeps it insert-once with its SHA-256, and
   serves it without reading a row -- as `record-dictionary` keeps a version's dictionary. The
   API never loads the population for the catalogue.
2. **The feasibility preview is counted by the API.** The API loads LIVE itself (its own
   `AIA_POPULATION_ASSET_ROOT`, read-only mount; unset: the preview says it is unavailable) and
   answers with counts only, never a row.
3. **Matched-block persona signals stay, labelled** ("statisticky přiřazený celý donor blok"),
   as 3d built them. Nothing in chunk 6 changes them.
4. **OI-99 stays open.** The owner has not decided a minimum n; a design the sampler refuses as
   unrepresentative is refused at run time, never drawn smaller, and the preview says so before
   a run is started (it asks the sampler itself, decision 7). On the sampler's 3,000 fictional
   rows refusals stop at about n = 200 (`test_panel_source.py`); that is a measurement on a
   fixture, not a threshold.

**The contract.**

5. **The catalogue, EXACT.** `domain/population/audience_catalogue.py`:
   `audience_catalogue(population)` ports `catalog(df, include_research_only=True)` -- the
   curated columns per category, then `DERIVED_COLUMNS`, then `RESEARCH_ONLY` as non-filterable
   and sensitive; per factor `id`, `label` (`_label`/`LABELS`), `category`, `category_label`
   (`CATEGORY_META`), `kind`, `status`, `filterable`, `sensitive`, `source`, `non_null`; numeric:
   `min`/`max`/`p10`/`p90` (pandas' linear quantile) and the `_1_10` scale hint; otherwise the 60
   most frequent values with their row counts, in `value_counts` order. Then `categories` (with
   `count`, `filterable_count`), `filterable_count`, `factor_count`, `logic`. The kind is
   :func:`~.audience.factor`'s, so the catalogue and the filter cannot disagree. Left out: the
   Data Library's materialized overlays (`custom`; AIA has none yet -- P4) and the unit's
   `version`, `base_columns`, `runtime_columns` (AIA states its own `catalogue_version` and the
   version id). Parity: the unit's own `catalog` on the audience-filter fixture's fictional rows
   (`tools/audience_capture.py capture`, extended), compared EXACT. AIA adds one thing per
   factor: the field policy's answer for `AUDIENCE_FILTERING` (`policy_allowed`,
   `policy_reason`); a factor the policy refuses stays listed and is not offered as a filter
   (`select_audience` would refuse it anyway).
6. **Kept and served.** Table `population_version_audience_catalogues` (version id, catalogue
   version, SHA-256 of the canonical JSON, the JSON, recorded at/by), insert-once like the
   dictionaries. `PopulationRuntime.record_audience_catalogue(version_id, recorded_by=)` loads
   the version and stores its catalogue (false when already kept). `population_ops
   record-catalogue [--version]`, acting as no one, run by the develop deploy after
   `record-dictionary`. API `GET /api/v1/population/audience-catalogue` (any member): LIVE's
   version id and label, its kept catalogue with the research-only factors reduced to their
   count (the screen shows only that count, `filterCategories`), and the 18 built-in subpanels
   with their filters (`subpanel_filters`), 18.6.6's support counts (`BUILTIN_SUBPANELS_v17.json`,
   stated as the unit's) and this version's `check_subpanel` answer. 404
   `population_not_established` without a LIVE population; 404 `audience_catalogue_missing`
   when LIVE's version has none kept.
7. **The preview.** API `POST /api/v1/population/audience-preview` `{filters, n}` (any member):
   LIVE loaded once per process and version (the ANALYSIS view, `AudienceDimensionsEnricher`),
   then `select_audience` (rows matched, unique donors, the filters kept) and, when `n` is
   given, `draw_panel_sample` with a fixed seed -- the same function the run calls, so "this
   would sample" and the run cannot disagree -- answering `ok` or the refusal's reason and
   message. Counts only. 503 `audience_preview_unavailable` when the API has no asset root; 404
   `population_not_established`. 6c measures the load's memory and time and the preview's
   latency on the fictional population, and states what v17 implies.
8. **Readiness says what the run will do.** `readiness(spec, filters_applied=)`: the API passes
   whether a run started now would be pinned to the population
   (`AIA_AI_POPULATION_PERSONAS_ENABLED`, the design's source `ai_runtime`). Pinned: filters
   PASS, "Filtry se uplatní při výběru respondentů z populace." Not pinned: today's WARN. An own
   audience or special dataset (`source_mode` other than `population`) stays WARN either way:
   AIA still has no audience store.
9. **The screen.** On the ČR 18+ branch the "filters" strategy is live: the factor editor from
   the catalogue, the chips, and the preview's count and verdict. On the special branch the
   built-in population subpanels are selectable (`applyPopulationSubpanel`), with this
   version's policy answer beside each; special panels (`special_panels`) and own audiences
   stay "V AIA zatím není". Without a catalogue (404) or a preview (503) the editor says why,
   where it is met, and keeps the filters a study already stores. **OI-50 changes with it:** a
   live editor that changes who is sampled cannot store an empty bound as 0, so
   `setAudienceRange` stores an empty bound as `null` (no bound); the classic behaviour stays
   characterised in its parity test as the classic's, not AIA's. OI-51 does not arise: a
   special preset is not live.
10. **Modelled, every time.** A panel run's results already say "modelováno" on every surface
    (4c, 4d); 6e adds a screen test over a run whose dataset is `MODELLED_AI_PANEL`.
    `docs/migration/interface-screens.json` (a code-checked ledger, it changes with the code)
    records the audience screen's new state.

**6b landed.** `domain/population/audience_catalogue.py`: `audience_catalogue(columns)` is the
unit's `catalog` EXACT on the audience filter's fictional panel
(`tools/audience_capture.py capture` now also writes `fixtures/audience_filter/catalogue.json`,
the unit's own `catalog` on the same rows; `expected.json` re-captured byte-identical);
quantiles are NumPy's linear `_lerp`, bit for bit; value ties keep first appearance (stable),
which is `value_counts`' order wherever NumPy's quicksort is stable (16 distinct values or
fewer) -- a declared difference beyond that, in the display order of equal counts only.
`with_policy` / `catalogue_of(population)` add each factor's `AUDIENCE_FILTERING` answer;
`for_the_screen` drops the research-only factors (their category and count stay).
`PopulationRuntime.record_audience_catalogue` loads the version's ANALYSIS view and keeps the
canonical JSON in `population_version_audience_catalogues` (migration `a2c4e6f8b0d3`,
insert-once, keyed by version and catalogue version), re-hashed on read
(`kept_audience_catalogue`). A version no population has been on cannot be loaded, so it has no
catalogue until it is promoted (`VersionNotRuntimeEligible`). `population_ops record-catalogue
[--version]` (no one; default: every population's current version), run by the develop deploy
after `record-dictionary`, a refusal said and not failing the deploy. `establish` and `promote`
also keep the new version's catalogue once their own change has committed (Codex on #345: a
promotion between deploys left LIVE without one); a version that will not load is said in the
command's answer and does not undo the change (`test_a_promotion_keeps_the_new_versions_catalogue_at_once`,
`test_a_catalogue_that_cannot_be_kept_does_not_undo_the_promotion`). `GET
/api/v1/population/audience-catalogue` (any member): CZ_LIVE's current version, its kept
catalogue for the screen, and the 18 subpanels with their filters (`subpanel_filters`),
18.6.6's counts and this version's `check_subpanel`; 404 `population_not_established` / 404
`audience_catalogue_missing`; 409 `audience_catalogue_mismatch`.

Tests: `test_population_audience_catalogue.py` (`test_the_catalogue_is_the_units_exactly`,
`test_the_fixture_exercises_every_shape_a_factor_takes`,
`test_a_population_catalogue_carries_each_factors_policy_answer`,
`test_a_versions_catalogue_is_computed_once_and_kept`,
`test_a_kept_catalogue_that_does_not_hash_is_refused`); `test_population_ops.py`
(`test_record_catalogue_acts_as_no_one_and_keeps_each_populations_version_once`,
`test_record_catalogue_of_an_unknown_version_writes_nothing`); `test_population_carry_over.py`
(`test_the_deploy_keeps_each_populations_catalogue_after_its_dictionary`);
`test_population_api.py` (`test_the_audience_catalogue_is_lives_kept_one_without_what_is_not_drawn`,
`test_no_live_population_or_no_kept_catalogue_says_which`,
`test_a_kept_catalogue_that_does_not_hash_is_a_conflict`).

**6c landed.** `domain/population/audience_preview.py`: `audience_preview(population, filters,
n)` asks `select_audience` (rows, distinct donors, the filters as applied) and, given `n`,
`draw_panel_sample` with `PREVIEW_SEED` (stated in the answer: the run draws with its own seed,
so where the verdict depends on the draw the run's may differ); every refusal by its reason,
message and reasons; counts only. `application/audience_preview.py`: `AudiencePreviewer` loads
`population_id`'s current version through `PopulationRuntime` (ANALYSIS view, every hash
re-verified) once per process and version under a lock, and lets the old one go when LIVE
moves. API: `AIA_POPULATION_ASSET_ROOT` (`Settings.population_asset_root`, empty by default:
no previewer); `POST /api/v1/population/audience-preview` `{filters, n}` (any member): 503
`audience_preview_unavailable` without a root, 404 `population_not_established`, 503
`population_unavailable` when LIVE will not load; a boolean `n` is a 422, not 1 (a
`mode="before"` validator, AGENTS.md; Codex on #345). Develop: the API service mounts the
population directory read-only and points the key at it
(`AIA_API_POPULATION_ASSET_ROOT=` empty turns it off). The compose guard that only the worker
sees the population is narrowed, not dropped, by the owner's choice:
`test_population_carry_over.py::test_the_worker_alone_gets_the_operators_and_the_api_only_the_read_only_population`
(the API gets the read-only directory and its root, never `AIA_POPULATION_OPERATORS`; web, Caddy
and PostgreSQL nothing).

Measured (nothing deployed; scratch scripts, not committed). The population's text
columns for a fictional panel of v17's shape (18,766 rows x 400 columns, 9.1 MB gzip): parse
3.6 s; ~97 MB held after parsing, 360 MB peak during it (tracemalloc); process max RSS 492 MB
including building the fictional CSV in the same process. The real panel holds more distinct
strings than this fixture, so the held figure is a floor; the real one is the develop API
container's after its first preview. Preview latency over the 3,000-row fixture (median of 5,
loaded): no filter, count only 1 ms; an age filter 6 ms; n = 200 17-18 ms; n = 1,000 35 ms --
scaling with rows, about 6x that on v17's 18,766. The first preview after a deploy or a
promotion pays the load (seconds); the rest only the count.

Tests: `test_population_audience_preview.py` (`test_a_filter_and_an_n_the_sampler_can_draw`,
`test_without_an_n_only_the_audience_is_counted`,
`test_a_filter_the_run_would_refuse_is_said_with_every_reason`,
`test_an_n_the_sampler_refuses_is_said_before_a_run_is_started`); `test_population_api.py`
(`test_the_preview_counts_the_audience_and_asks_the_sampler`,
`test_the_preview_loads_live_once_per_version`, `test_without_an_asset_root_there_is_no_preview`,
`test_a_preview_over_no_live_population_is_404_and_needs_a_member`,
`test_a_population_that_will_not_load_is_unavailable_not_an_error`) over a fictional LIVE in
the API's database (`apps/api/tests/conftest.py` `fictional_live`).

**6d landed.** `assess_readiness(spec, pair_n_min=, filters_applied=False)` (and `prepare`):
with `filters_applied`, a population audience's filters PASS ("Filtry se uplatní při výběru
respondentů z populace."); an own audience or special dataset stays WARN and says the run draws
from the population instead (under the stored filters, if any); without it, today's WARN.
`READINESS_RULES` is unchanged: a roster run's checks are the same, and its preflight
artifact's key is too (`filters_applied` enters the key only when true). The API's readiness
asks with the pin a start would make now (`_persona_source`); `ResearchRuns.start` pins
`persona_source` in the `preflight` step's input too, which the worker's preflight reads (a run
stored before reads as the roster; an unknown value fails the step, `persona_source_unknown`).

Tests: `test_research_design.py::test_the_audience_check_says_whether_the_run_will_apply_the_filters`,
`test_research_api.py::test_readiness_says_the_filters_apply_only_where_a_new_run_would_draw_from_the_population`,
`test_ai_fieldwork.py::test_a_panel_runs_preflight_says_its_filters_apply_and_its_sample_keeps_them`
(the real worker: the stored readiness PASSes and the sample's recorded filters are the design's).

**6e landed.** `lib/api.ts`: `population.audienceCatalogue()` / `audiencePreview(filters, n)`
and their types. `research/audience.ts`: `liveCatalog` (a factor keeps its policy answer),
`factorRefusal` (research-only, or the policy's reason), `liveSubpanels` (18.6.6's counts kept
as 18.6.6's), `setRange` (an empty bound is left out, so the population's own bound stands --
OI-50 does not carry over; the classic `setAudienceRange` stays as the parity port), `liveVerdict`
(the preview in Czech, each refusal reason in words, the unit's own reasons appended).
`AudienceStep.tsx`: the step reads the catalogue once; with it, the "filters" strategy and Special
Audience lose their "V AIA zatím není" tag, the factor editor offers categories, search, a range
per numeric factor and values with counts per other factor (a refused factor listed and
disabled, its reason said), the chips say "Vybrané filtry", and "Ověřit proveditelnost" asks the
preview (the seed it drew with said); Special Audience offers the 18 built-in subpanels (an
unusable one disabled with its reason; unknown while the dictionary is not kept), and special
panels and own audience still say they are not in AIA. Without a catalogue -- no population
(`population_not_established`), none kept, or a failure -- the step is as before, with the
reason first. Results already say "modelováno" on every surface for a modelled run (4d,
`ExecutionSteps.test.tsx` › *says a modelled run is modelled on its banner and its steps*), so
no new screen test was needed for it. `docs/migration/interface-screens.json`: the audience
screen's notes.

Tests: `research/audience.live.test.ts` (catalogue, subpanels, the range without OI-50, the
preview in words); `AudienceStep.test.tsx` › *from AIA's population* (filters chosen and saved,
an empty bound left out, a refused factor disabled; the preview counted and its body; the
preview unavailable; a subpanel chosen as its filter and the step ready, a refused one disabled).

**6f landed.** The workbench has a population for the audience step. Its API stand-in
imports the sampler's 3,000 fictional rows under a contract of its own
(`tools/ui_workbench/fictional_population.py`, idempotent across restarts, about 15 s on a
fresh start), keeps LIVE's catalogue, and points the audience routes at it through one seam
in the composition root: `aia_api.dependencies.AudiencePopulation` on `app.state` (the Czech
LIVE in every deployment, `CZECH_AUDIENCE`; nothing in configuration changes it) and the
installed previewer. Research runs keep recording the Czech LIVE, which the workbench never
establishes. `make ui-audience` (`audience_journey.mjs`) drives the step in Chromium: filters
from the catalogue saved as chosen with the empty bound left out and read back after a reload,
the preview's count and verdict, a usable subpanel saved as its filter and a policy-refused
one disabled, no request to a unit path. **Run 2026-10-12: PASS**, 104 requests.

Finding, fixed here: the journey's first run got a 503 from the preview. The stand-in installs
its previewer, then the server's startup runs `init_app_state` again (the setup client's
shutdown disposed the engine), which rebuilt the previewer from settings: none. `init_app_state`
now keeps a previewer already installed, as it keeps the engine
(`test_population_api.py::test_a_previewer_already_installed_survives_the_servers_startup`).
In a deployment nothing installs one, so nothing changes there.

Tests: `test_population_api.py::test_the_audience_routes_read_the_population_the_composition_names`,
`::test_a_previewer_already_installed_survives_the_servers_startup`; the journey.

**Two findings on #332 (Codex, after it merged), fixed here.** (1) A panel start with no
population and a spend limit the run reaches was asked to confirm its cost before being refused
(`application/research.py`, the population check after the cost gate @ `abd3ce88`): the person
would confirm a run that can never start. The population is now resolved and checked before the
gate; `test_research_runs.py::test_a_panel_start_with_no_population_is_refused_as_that_before_any_cost_is_asked`
fails on the old order (`CostConfirmationRequired`) and passes on the new. (2) `test_panel_source.py`
imported `conftest` and `test_population_runtime` as modules, which AGENTS.md § tests forbids;
the fictional population is now `conftest.sampled_population`, used by it and by 6b-6c's tests, and
the API's fictional LIVE is `conftest.fictional_live` (no helper module). The older
cross-module imports elsewhere in the suites (about 40, e.g. `test_population_audience.py`,
`apps/executors/tests/grounded_world.py`) are left as they are: not this PR's.

Out of scope: own audience upload and special panels (no audience store in AIA), the AI's
proposal of filters (the native job proposes a description only, `research_agents.py`),
materialized dimensions in the catalogue (P4), any client-facing claim (chunk 7).

**4. Origin.** `DataOrigin.MODELLED_AI_PANEL`; dataset, analysis harness
(`analysis/harness.py:141`, `analysis/native.py:491`), Sociomap labelling
(`research_sociomapping.py:359`) and report read it as modelled, never synthetic
fiction and never measured.

**5. Executor.** `ai_fieldwork` takes a persona source per run: fictional roster or
panel. Behind `AIA_AI_POPULATION_PERSONAS_ENABLED`, off by default and in test. The
profile is longer than four facts: measure input tokens and cost per respondent and
state them in the commit body. The run's provenance names the source, binding,
roster or sample version and the persona mode.
Code comments that still give OI-61 as the reason fieldwork is fictional change with it:
`domain/ai_respondent.py:19-24`, `application/research.py:176,216`,
`apps/api/src/aia_api/routers/research.py:187`, `apps/web/src/lib/research-execution.ts:98`
(all @ `ea5210e`); after OI-61 the reason is that no panel persona source exists.

**6. Screens.** Audience filters and the 18 subpanels become live where they now say
"V AIA zatím není"; results say "modelováno" every time.

**7. Validation.** Port the unit's persona ablation (`persona_ablation.py`: arms
none / demographics / full, TVD per question) and add a holdout: questions whose
population marginals are known (ISSP items in the panel), asked of panel-grounded
respondents, compared. No client-facing claim until the holdout result is recorded.

### 7. Validation (contract, 7a)

Anchors @ `ccddfd87`; unit anchors under `legacy/npc-panel-18.6.6/app/`, frozen.

**Owner decisions (2026-10-13, in session).** Design the validation to be the most
methodologically robust it can be, and decide its thresholds here. The cost ceiling is the
validation study's own money: its budget and spend limit. The researcher records the result.

#### The claim being validated

A client asks questions the population never asked. Chunk 7 has to support one claim and no
other:

> On a closed question that was not in its persona, the current respondent system's AI
> respondents answer, in aggregate, close to how the people they were drawn from actually
> answered, and closer than a model given no person, or the wrong person.

So the test reproduces a client's situation on questions whose real answers AIA holds. A real
answer for each sampled person sits in the panel, but is kept out of everything the model
sees. The validation is earned by **one** respondent system (`respondent_system_fingerprint`,
`domain/evidence/validation.py:106-136`). Any change to the prompt, the persona builder, the
sampler, the population version, the model binding or the response process makes it stale.
4e2 already enforces that (`effective_validation_status` :151-157).

#### What exists, and why it is not enough

**What 18.6.6 has.** It specifies more than it runs:

- `persona_ablation.py` measures sensitivity, not accuracy. Its arms are `none` /
  `demographics` / `full`, its metric is TVD, and its status is `EFFECT_TEST_ONLY_NOT_ACCURACY`.
- `LLM_ABLATION_STATUS_v17_1.json` asks for four arms, three seeds and "D beats C beats B by
  more than between-seed noise on preregistered external truth". It was never run
  (`llm_ablation_run: false`).
- The holdout gate (`validation_gate.py:28-46`) requires:
  - at least 30 questions across at least 5 domains, with at least 3 per domain;
  - full-persona MAE of at most 7.5 pp;
  - a paired-bootstrap improvement over the demographics, generic and shuffled baselines;
  - preregistration and a hash-chained ledger (`holdout_protocol.py`).
- It was never run either: its benchmark calls an unimported `resolve_model`
  (`benchmark.py:212-239`). Its truth is uploaded by a person (`VALIDATION_ANCHORS.json`:
  `anchors: []`).

**Where 18.6.6 falls short.** Its own design has four weaknesses AIA corrects:

1. **No sampling floor for the truth.** Every arm is scored against a survey marginal, so
   the error of drawing n respondents is counted as the model's error. Here every sampled
   person's real answer is in the panel, so the modelled answers are compared with *the same
   people's* answers and the respondent draw cancels.
2. **No baseline without a model.** All of its baselines are LLM runs. AIA adds two code
   baselines, a population marginal and a demographic-cell lookup. These show what the panel
   alone already knows, and therefore how much the model adds.
3. **No correction across comparisons.** It makes four uncorrected 95 % comparisons. Here
   the confirmatory comparisons are Holm-corrected.
4. **No leakage rule beyond source names.** It matches cited-source strings
   (`holdout_registry.py:75-136`). Here the excluded set is computed from the data: the item,
   its matched block, and any persona field associated with it.

AIA today has the validation's *effect* (4e2: only a current `HOLDOUT_VALIDATED` lifts
`INTERNAL_ONLY`) but not the validation itself:

- nothing stores one (`application/analysis_results.py:509-511` passes `validation=None`);
- `ValidationState` has no date or evidence;
- a run cannot leave a field out of its personas: `panel_persona.py:193-294` takes no
  exclusion.

#### The truth: what may be held out

**The surveys behind the panel** (`legacy/npc-panel-18.6.6/app/DONOR_BLOCK_REGISTRY.json`,
`CORE_JOINT_STATUS.json`, both 17.x). The panel is not built from ISSP and PIAAC alone.

| Part | Source | Wave | Donors (effective) | Who it is measured for |
|---|---|---|---|---|
| Core | PIAAC Cycle 2 CZ | 2023 | the core | 18-65 only |
| Core | ISSP CZ | 2022 | the core | 66+ only |
| Matched block `mental_health` | NUDZ CAPI | 2022 | 3,063 (2,240) | everyone, a matched donor's answer |
| Matched block `social_network` | JRC Loneliness CZ | 2022 | 1,000 (564) | the same |
| Matched block `institutions` | QoG EQI CZ | 2024 | 5,033 (3,884) | the same |
| Matched block `rule_of_law` | CSDA Rule of Law | 2024 | 981 (511) | the same |
| Matched block `politics` | CSES Module 5 CZE | 2021 | 1,451 (1,123) | the same |
| Matched block `family_health` | ISSP CZ | 2022 | 1,243 (831) | the same |

These give seven natural domains (the core's skills and work, plus the six blocks). Two
consequences for the item bank:

- **A core item is scored only where it was measured.** PIAAC items exist for 18-65 and
  ISSP core items for 66+. Such an item is asked of the whole sample, as a client run would
  ask it, but scored only on the age range whose answers are real: a row outside it has no
  truth, never a guessed one. Its support (criterion 4) is counted in that range.
- **A matched block's support is its effective donors.** `rule_of_law` (511) and
  `social_network` (564) pass the 300 floor; any block under it would not.

**The item bank.** Each candidate item is a panel field whose answers are a survey's
measured responses. Each item needs:

- the field's dictionary entry: block, source and evidence status;
- the source questionnaire's **exact wording and options in Czech, as fielded**, with the
  map from the panel's codes to those options. The international master (English) is not
  enough: a translation made by us would be our wording;
- the source item id.

The dictionary carries no question wording (`POLICY_COLUMNS`, `population/policy.py:233-243`).
So the bank is a separate, hash-pinned file, an import-contract companion like
`PERSONA_VALUE_LABELS`, compiled from the source questionnaires (ISSP CZ, PIAAC CZ). An item
without its source wording is ineligible. A question re-worded by us would test our wording,
not the system.

**Eligible.** A field is eligible only when every one of these holds:

1. **Measured, never modelled.** Its `evidence_status` is one of the measured classes:
   `CANONICAL_CORE`, `MEASURED_CORE_PIAAC`, `MATCHED_WHOLE_BLOCK(_CANONICAL)` or
   `MATCHED_POLITICS_CANONICAL`. `CALIBRATED_*` and `MODELED_*` are models, and a model
   scored against a model proves nothing.
2. **Closed.** A single choice of 2-11 options, or an ordinal scale of at most 11 points,
   since the respondent contract answers closed items.
3. **Answered.** Non-null for at least 80 % of LIVE's weighted rows. A missing answer is
   never scored as an option.
4. **Supported.** At least 300 effective donors (Kish, over `core_donor_id` or the block's
   donor). This is 18.6.6's `human_n >= 300`, counted in donors as 4e4 counts support.
5. **Not given.** Not a sampling or raking field (sex, age, education, region), not an
   audience dimension (`DERIVED_COLUMNS`), and not a fact the factual layer answers by code
   (`respondent_facts._DIRECT_PATTERNS`). A respondent is told those, so predicting them
   proves nothing.
6. **Not near-duplicate.** Among items with |r| (or Cramér's V) >= 0.7 between them, only
   one is kept, chosen by the draw. This stops one construct being counted several times.

**Domains.** A domain is the dictionary's `block` grouped by the bank's declared domain map,
pinned in the bank. Examples: family and gender roles, work, health, trust and institutions,
politics, environment, skills use.

**The split, made once and pinned.** The eligible pool is drawn by stratified random
sampling within domain, under a seed recorded in the preregistration, into two sets:

| Set | Share | What it is for |
|---|---|---|
| **Development** | 40 % | Any number of runs: debugging, cost measurement, the ablation's design questions. Never scores a validation. |
| **Confirmation** | 60 % | Used once per respondent system; never seen by any development run, prompt or person tuning the system. |

A confirmation set is **consumed** when its run completes, pass or fail, as 18.6.6's
`assert_holdout_unconsumed` consumes a holdout (`holdout_protocol.py:214-218`).
- After a failure, the system must change (a new fingerprint), and a new confirmation draw
  comes from the items not yet consumed.
- When fewer than the minimum remain, validation needs an external truth (below). The pool
  is never re-used.

**Minimums for a confirmation set.** At least 40 items, across at least 5 domains, with at
least 4 per domain. 18.6.6 required 30 / 5 / 3. The higher numbers buy a tighter interval
over items, at about a third more cost.

#### Leakage: what each respondent is not given

For each confirmation item, the persona of every arm leaves out:

1. the item itself;
2. if the item is in a **matched block**, every field of that block. The block is one
   donor's answers, so any sibling item carries the answer;
3. every field whose weighted association with the item, computed on LIVE, is
   |r| >= 0.30 (ordinal or numeric) or Cramér's V >= 0.30 (nominal). The set is computed and
   pinned at preregistration, never chosen by hand;
4. every catalog signal whose `column` is excluded, or whose `concept` is the item's.

**Unit of exclusion.** Items are asked in blocks of at most 8 by domain (one request per
block, as fieldwork does), so a block's exclusion is the **union** over its items.

**The persona is never filled in.** An excluded field is left out, never replaced. The
profile reads one line shorter, as a policy refusal reads today (3a).

**Conservative by construction.** Leaving correlated fields out makes the test **harder**
than production. A client's question also correlates with fields that stay in, so a pass
here understates the production system's performance and never overstates it. The
exclusion is an input to the validation run only; no client run accepts one.

**Contamination is measured, not assumed away.** ISSP and PIAAC marginals are public, and a
model may have seen them in training. Two arms isolate that:
- arm **A** (no persona) shows what recall alone gets;
- arm **S** (the shuffled persona) shows whether the *right* person matters.

The validation requires D to beat both. A model that knows the published marginal but not
the person cannot pass.

#### The arms

Every arm has:
- one sample: LIVE, no audience filter, the production sampler (`draw_panel_sample`), n 600,
  its seed in the preregistration;
- the same block plans;
- the same prompt, response process and model binding.

Only the persona text differs.

| Arm | What the respondent is given | Model | What it shows |
|---|---|---|---|
| **L0** | -- | code | The population's weighted marginal of the item, predicted for everyone: what knowing the population, with no person, already gets |
| **L1** | -- | code | The weighted distribution of the item in the respondent's sex × age band × education × region cell, the respondent's own donor left out; backs off to a coarser cell under 30 donors: what demographics alone get, by lookup |
| **A** | No persona: the question only | model | Recall and priors |
| **B** | Demographics: the base lines (3b, 1) | model | Demographics, through the model |
| **C** | Core profile: base, socio-economic and household lines, no catalog signals | model | What the signals add (D vs C) |
| **D** | The production persona (`panel_personas`), with the exclusions | model | **The system being validated** |
| **S** | D's personas deranged: each respondent gets another sampled respondent's persona | model | Whether the right person matters |

**Replicates.** The model arms run 3 replicates each: answer-draw seed and request order
change, and the sample and personas do not. That gives the between-replicate noise the
ablation's decision rule needs (18.6.6's `required_seeds: 3`).

**Arm D is production.** Its prompt, builder and response process are byte-identical to a
client run's, so its respondent system fingerprint equals production's. A test proves that D
with no exclusions builds the same requests as `panel_plans` does today.

#### The metrics

All metrics are per item i, on the confirmation set. The truth is **the same sampled
people's own answers** (weighted, the raked analysis weight), so no respondent-draw error is
counted against the model. The model returns each respondent's probabilities and code draws
the answer (`ai_respondent`); the metrics use both.

1. **Marginal error (primary).** `TVD_i` is the total variation distance, in percentage
   points, between the weighted distribution of the drawn answers and the weighted
   distribution of the true answers.
2. **Subgroup error.** The same TVD within each sex × age-band cell (6 cells) holding at
   least 50 donors, averaged per item. A client's breakdown is a subgroup, so the tier gate's
   `demographic_breakdown` needs this criterion as well as criterion 1.
3. **Person-level score.** The mean Brier score of each respondent's predicted probabilities
   against their own answer, compared between arms. It is scored **only on core-block items**,
   whose answer is the same person's. A matched block's answer is another donor's, matched
   on covariates, so a person-level score there would grade the matching, not the model.
4. **Dispersion.** The entropy gap: modelled minus true entropy, in bits. Mode collapse (the
   known failure of persona simulation) shows as a negative gap.
5. **Stability.** The standard deviation of mean TVD over the 3 replicates.

**Uncertainty is computed by bootstrap over items** (an item is the unit of replication),
10,000 resamples, seed recorded. Item-level differences between arms are paired.

#### Pass: every criterion, on the confirmation set, arm D

Thresholds are fixed here, before any confirmation item is drawn, and copied into the
preregistration. They cannot change after it is pinned.

| # | Criterion | Threshold | Why this number |
|---|---|---|---|
| P1 | Mean `TVD_i` over items | <= 10 pp, **and** its 95 % bootstrap upper bound <= 12 pp | 18.6.6's 7.5 pp was MAE per category. For a typical 4-option item, MAE = TVD / 2, so 7.5 pp MAE is about 15 pp TVD. In general MAE = 2 TVD / k, so 7.5 pp MAE allows 3.75 k pp TVD: 10 pp TVD is stricter than 18.6.6 for every item of 3 or more options and looser only for a 2-option item (7.5). The upper bound stops a lucky mean from passing |
| P2 | Worst domain's mean `TVD_i` | <= 15 pp | One domain the system cannot model must not hide in the average |
| P3 | Share of items with `TVD_i` > 20 pp | <= 10 % | A client asks one question, not the average |
| P4 | D beats **A** on mean `TVD_i` | paired-bootstrap improvement > 0, Holm-corrected at family-wise α = 0.05 over the three comparisons of P4 and P5 | Without this, a pass could be recall: a model that knows the published marginal with no person at all |
| P5 | D beats **S** on mean subgroup TVD **and** on the mean Brier score (core items) | lower for both, Holm-corrected as in P4 (same family) | The right person drives the answer. S is not compared on the whole-sample TVD: it shows a permutation of the same sample's personas, so its whole-sample marginal is D's but for the weights (7d finding) |
| P6 | Mean subgroup TVD | <= 12.5 pp | Needed before any breakdown reaches a client |
| P7 | Mean entropy gap | >= −0.25 bits | No mode collapse |
| P8 | Replicate SD of mean TVD | <= 1.5 pp | Otherwise the run's own noise is the size of the effect |

`PASS` holds only if all eight hold. Each criterion is recorded with its value and interval,
so a failure says which part failed.

**What does not decide the pass, but is recorded and reported:**

- **L0 and L1.** They have the truth's own column, which no client question has. Measuring D
  against them shows how much of what the panel already knows the model recovers. A system
  that passes yet sits far above L1 has room to improve, which is a finding, not a failure.
- **The ablation's ladder (B, C, D).** Its rule is 18.6.6's own (`LLM_ABLATION_STATUS_v17_1`):
  the catalog signals stay in the persona only if D beats C, and C beats B, by more than
  twice the between-replicate SD. If not, that is a finding naming the part of the persona
  that does not earn its place. Changing it changes the fingerprint and needs a new
  confirmation draw.

**A failed validation is recorded as failed.** It is not retried on the same items, and the
system stays internal. A negative result is a result.

#### Preregistration: pinned before the first confirmation call

One immutable record, SHA-256 over its canonical JSON (18.6.6's `prereg_sha256`,
`holdout_protocol.py:23-28`), stored insert-once. It holds:

- the item bank's hash and the eligible pool's hash;
- the split seed and both sets;
- each block's items and its exclusion set, with the association values that put each field
  in it;
- the arms, n, sample seed, replicate seeds and bootstrap seed;
- the metrics and P1-P8 with their thresholds;
- the scoring code's version;
- the population version;
- the respondent system's components and fingerprint (arm D's).

The confirmation run refuses to start without it, and refuses one whose system fingerprint
is not the current one. Development runs need no preregistration and never score a
validation.

#### Money: the validation study's own budget and spend limit

A validation runs as a **Study** (`kind` RESEARCH) of an internal client, through the same
gates as any run. No new money mechanism:

- **The study's budget** (`budget_usd`, `scope_repository.set_study_budget`) is the hard cap.
  Every request reserves against it before it leaves (`reserve_budget`,
  `workflow_repository.py:1017-1059`).
- **When the budget runs out.** The step parks in `AWAITING_BUDGET` and waits for a person to
  lift it (`lift_budget_wait`). It is never silently cut, because a run cut part-way would
  compare unbalanced arms, as 18.6.6's `ABLATION_BUDGET_EXHAUSTED` refused.
- **The study's spend limit** (`spend_confirm_usd`). If the run's cost ceiling reaches it,
  starting needs the researcher's confirmation, recorded in the approval ledger (ADR 0019
  gate 2; `ResearchRuns.start`, `research.py:441-457`).
- **The ceiling** is computed as `run_cost` computes one: n × blocks × model arms ×
  replicates requests × the fieldwork reservation. The code baselines L0 and L1 cost
  nothing.

**Size, as designed.**

| Pass | Requests | Arithmetic |
|---|---|---|
| Confirmation | 45,000 | n 600; 40 items in 5 blocks; 5 model arms (A, B, C, D, S); 3 replicates. 600 × 5 × 5 × 3 |
| Development | about 4,500 | n 300; the development items in 3 blocks; 5 arms; 1 replicate |

5e measured about 3,500 characters per request, roughly 1,200 input tokens. With about 300
output tokens and an assumed $3 / $15 per MTok, that is about $0.008 per request: roughly
$360 for the confirmation pass. The ceiling, at the reservation, is higher. **The real price
is the development pass's ledger** (`ai_usage_events`). The confirmation study's budget is
set from it, and the preregistration records the ceiling the researcher confirmed.

#### Who records it, and what recording changes

**The researcher.** Under ADR 0019, a Researcher holds every permission; the worker's scope
withholds approvals. Recording works like this:

- **Code computes the verdict.** The scoring step writes an immutable verdict artifact:
  every metric, interval and criterion, `PASS` or `FAIL`, the preregistration's hash and the
  run's ledger totals.
- **A person records it.** A member records the verdict as themselves, in the approval
  ledger (gate `validation`), with an attestation that no confirmation item was seen while
  the system was tuned (18.6.6's `--attest-holdout-excluded`).
- **The verdict cannot be overridden.** Recording copies the computed verdict; nobody can
  record a `PASS` over a computed `FAIL`.
- **The record.** A recorded `PASS` becomes the respondent system's `ValidationState` with
  the fingerprint, status `HOLDOUT_VALIDATED`, the recorder, the date, and the
  preregistration and verdict hashes. A recorded `FAIL` is kept as well, and lifts nothing.

**What it changes, through code 4e already wired:**

- `analysis_results` reads the current validation instead of `None` (:509-511).
- `lifts_internal_only` then drops `INTERNAL_ONLY` from `-2`.
- A modelled claim may reach a client with both disclosures.
- The DOCX prints the validation's date and fingerprint beside "modelováno: AI respondenti z
  populace" (4e5, ADR §7).
- Segment breakdowns still need the tier gate.
- A stale validation (any component changed) lifts nothing, exactly as 4e2 tested.

**No time expiry beyond the fingerprint.** Every input that can change the answers is in it,
pinned model binding included. A validation older than 12 months is shown with its age,
because Czech opinion moves and the population version does not, but it is not expired by
date. That is a methodology call to revisit with the first re-validation.

#### External truth: a second route, never a weaker one

When the panel's pool is consumed, or a client domain lies outside it (brand, media,
purchase), the same protocol takes an **external** truth instead. That is a survey not used
to build the population (18.6.6's `HOLDOUT_ZDROJE`, `holdout_registry.py:28-52`), with
its wording, its weighted marginals, and n >= 1,000 with a stated margin of error.

Because no sampled person's own answer exists for it:
- P1-P3 are scored against its marginal, with the survey's sampling error subtracted as the
  floor (18.6.6's `_human_moe_pp`, `benchmark.py:61-78`);
- P5 is not scored.

The record names which truth earned it: `PANEL_HELD_OUT` or `EXTERNAL`.

#### Chunks

- **7a.** This contract.
- **7b.** The item bank and the preregistration, pure:
  - eligibility, the pinned split and the exclusion sets;
  - the preregistration record and its hash;
  - refusals by name.

  Tests on a fictional population, including one where a sibling field leaks the answer.
- **7c.** Persona arms and exclusions (`panel_persona`):
  - A, B, C, D and S as inputs of a validation run only;
  - D with no exclusions is byte-identical to today's `panel_plans`;
  - a client run cannot carry an arm or an exclusion.
- **7d.** Scoring, pure:
  - L0, L1, the five metrics, paired bootstrap, Holm, P1-P8 and the verdict.

  Tested on constructed answers where the right verdict is known: a perfect system, a
  recall-only system that fails P4, a collapsed one that fails P7.
- **7e.** The validation run:
  - a `respondent_validation` workflow under a Study: sample once, arms × replicates through
    the real fieldwork executor, scoring, the verdict artifact;
  - the cost ceiling, the study budget and the confirmation;
  - the preregistration refused if missing or stale.
- **7f.** Recording:
  - the insert-once tables (preregistration, verdict, validation record);
  - the researcher's record in the approval ledger;
  - `ValidationState` gains the date and evidence;
  - `analysis_results` reads the current validation;
  - the report prints the date and fingerprint;
  - Settings shows the respondent system's validation state.
- **7g.** The item bank compiled from the eight source questionnaires (the table above):
  the Czech wording and options as fielded, mapped to the panel's codes.

  This is the one input code cannot produce. Each item records its source document (URL and
  SHA-256 of the file read) and the page it came from. A person checks it against the source
  documents, then it is pinned. The owner says the documents are public (2026-10-13);
  where only an international master exists, the item is ineligible, never translated.
- **7h.** On develop:
  - the development pass (real Bedrock, development items), whose ledger sets the
    confirmation budget;
  - then the preregistration;
  - then the confirmation run;
  - then the researcher records the verdict.

  The result is whatever it is.

**7b landed.** `packages/aia_core/src/aia_core/domain/holdout/`, pure:

- `bank.py`: `read_item_bank` reads `aia-holdout-bank-1`. Each item carries:
  - its field, survey (one of the seven in `SURVEYS`) and domain;
  - its Czech wording, and its options with their panel codes;
  - `measured_ages` (a core item's range, or `None` for a matched block);
  - `ordinal`;
  - its source document (an https URL, the SHA-256 of the file read, the page and the item id).

  The bank is pinned by the SHA-256 of its canonical JSON. A malformed bank is refused by
  name (`item_bank_malformed`, `item_not_closed`, `item_survey`, `item_source_missing`,
  `item_bank_version`).
- `eligibility.py`: `assess_item` / `assess_bank` apply eligibility rules 1-5 and list every
  failing reason:
  - `not_measured`, `value_not_an_option`, `low_coverage`;
  - `low_support` (Kish over the donor behind the answer: `core_donor_id` or
    `_donor_<block>_id`);
  - `given_to_respondent`, `not_in_population`, `donor_unknown`, `age_unknown`.

  `scored_rows` gives a core item only the ages its survey asked; an unknown age is in no
  range.
- `leakage.py`: `block_exclusion` returns, for a block, what its respondents are not given:
  `ITEM`, `MATCHED_BLOCK`, `ASSOCIATED` (|r| or Cramér's V >= 0.30, recorded),
  `ASSOCIATION_UNKNOWN` (left out, never read as none) and `SIGNAL_CONCEPT`.
  `ParsedColumns` parses each column once per computation.
- `preregistration.py`:
  - `draw_split`: near-duplicates (>= 0.70) are dropped in a seeded order and recorded, then
    a 40 / 60 split is drawn within each domain. Every order is sorted before it is
    shuffled, so the split moves with the seed and the pool, never with the bank's order.
  - `confirmation_blocks`: by domain, at most 8 items each.
  - `preregister`: the record and its SHA-256. It refuses:
    - a confirmation set under the minimums (`holdout_confirmation_short`);
    - exclusions that do not match the blocks;
    - fewer than three distinct replicate seeds;
    - under 10,000 bootstrap resamples;
    - a non-positive ceiling;
    - a respondent system that does not fingerprint.

  The population version is the respondent system's own: there is no second place to name it.

**Measured.** This is the cost of one preregistration, on a fictional population of v17's
size: 18,766 rows, 105 items in 7 domains, 150 persona fields.

| Step | Time |
|---|---|
| Eligibility | 1.0 s |
| Split, including the near-duplicate pass over every pair | 57.9 s |
| Exclusions over 63 confirmation items | 88.9 s |

About 2.5 minutes, once per preregistration, never on a run's path.

Tests (`test_holdout_bank.py`, `test_holdout_leakage.py`, `test_holdout_preregistration.py`), among them:
- `test_a_modelled_field_is_never_truth`
- `test_a_core_item_is_scored_only_in_the_ages_its_survey_asked`
- `test_a_missing_donor_makes_support_unknown_never_counted`
- `test_the_item_its_matched_block_and_what_tracks_it_are_left_out`
- `test_an_association_that_cannot_be_computed_leaves_the_field_out`
- `test_a_near_duplicate_is_dropped_and_recorded_never_counted_twice`
- `test_the_split_does_not_depend_on_the_banks_order`
- `test_a_confirmation_set_below_the_minimums_is_refused_never_run_small`
- `test_a_preregistration_pins_everything_that_decides_the_verdict`

The fictional population is `conftest.holdout_population`, a session-scoped factory.

**7c landed.** `domain/holdout/arms.py`, pure. `arm_plans(personas, spec, arm, exclusions=,
shuffle_seed=)` builds every respondent's plan under an arm.

- **The block's exclusion is applied first.** A block's exclusion is the union of its items'
  exclusions, and it is taken off the row and the catalog before any profile is written.
- **What each arm shows:**

  | Arm | Profile |
  |---|---|
  | `A` | An empty profile; the request's frame is unchanged |
  | `B` | `persona_text` over the four base columns (`BASE_COLUMNS`) |
  | `C` | `persona_text` with no behaviour block, so no catalog signal |
  | `D` | `PanelPersonas.profile`'s own composition, without the excluded fields and signals |
  | `S` | D's profiles shown through `derangement` |

- **`derangement`.** Sattolo's algorithm over the sorted ids, under a seed: one cycle, so no
  respondent is shown their own profile.
- **What every arm keeps.** The respondent's own facts and styles: the response process is the
  system's and does not change between arms. `S` therefore isolates the description.
- **Refusals:** `arm_seed_missing` (S without its seed) and `arm_too_few` (fewer than two
  respondents).
- **Not yet enforced.** That only a validation run builds arms is held by `panel_plans` taking
  no arm. 7e's validation executor is the one module that will import `arms`, and its
  `layer_check` rule lands with it.

Tests (`test_holdout_arms.py`, on `conftest.sampled_population`, 200 respondents):
- `test_the_production_arm_without_exclusions_is_todays_persona`: D with no exclusion is equal,
  plan for plan, to `PanelPersonas.plan`;
- `test_arm_a_shows_no_persona_and_keeps_the_facts_and_styles`;
- `test_arm_b_shows_the_demographic_lines_alone_and_c_no_signal`;
- `test_an_excluded_field_is_never_shown_in_any_arm`;
- `test_the_shuffled_arm_shows_each_respondent_someone_elses_profile`;
- `test_a_derangement_has_no_fixed_point_and_moves_only_with_its_seed`;
- `test_the_shuffled_arm_needs_its_seed`.

The fixture's rows carry no catalog-signal columns, so D and C coincide there. That D adds the
signals is held by the equality with `PanelPersonas.plan`, whose signal content 3d's EXACT
fixtures pin.

**7d landed.** The scoring code is in `domain/holdout/`, pure.

- **`scoring.py`.** `item_metrics(truths, runs, respondents)` computes each item's metrics for
  one arm, averaged over its replicates: `tvd`, `subgroup_tvd`, `brier` and `entropy_gap`.
  - A replicate missing an answer is refused, never scored.
  - `subgroup_tvd` counts only cells with at least 50 donors.
  - `brier` is computed on person-level (core) items only.
- **`verdict`.** It applies P1-P8 to D:
  - P1's upper bound is the 95th percentile of the bootstrap mean.
  - P4 and P5 are one Holm family of three one-sided paired-bootstrap tests:
    `D_beats_A_tvd`, `D_beats_S_subgroup_tvd` and `D_beats_S_brier`.
  - A criterion that cannot be evaluated fails.
  - The B/C/D ladder is recorded (`signals_earn_place`) and decides nothing.
  - `Verdict.document()` is what 7e stores.
- **`baselines.py`.**
  - `l0_predictions` predicts the item's weighted population marginal.
  - `l1_predictions` predicts the respondent's sex x age group x education x region cell, with
    every row of the respondent's own donor left out. A cell with fewer than 30 other donors
    backs off through region, education, age group and sex to the whole population.
  - `baseline_metrics` scores a baseline from its expected marginal.

**Finding (7d, fixed here in the contract).** P4 as 7a wrote it compared D with S on the
whole-sample TVD. S shows a permutation of the same sample's personas, so its whole-sample
marginal equals the truth's but for the weights each respondent keeps. On the test world that is
under 5 pp against a subgroup TVD more than three times larger. The comparison would have failed
a perfect system, or passed a broken one, by noise.

The fix: P4 compares D with A on TVD, and P5 compares D with S on subgroup TVD and the Brier
score. The same Holm family now holds three tests at α 0.05. Nothing was preregistered yet, so
nothing is moved after the fact.

Tests:
- `test_holdout_scoring.py`:
  - `test_a_system_that_answers_as_the_people_did_passes_every_criterion`
  - `test_a_system_that_knows_the_marginal_but_not_the_person_fails_p4`
  - `test_a_system_that_always_gives_the_modal_answer_fails_p7`
  - `test_a_criterion_that_cannot_be_evaluated_fails`
  - `test_the_wrong_persons_answers_match_the_marginal_so_s_is_compared_on_people`
  - `test_a_replicate_missing_an_answer_is_refused_never_scored`
  - `test_holm_rejects_step_down_and_stops_at_the_first_failure`
- `test_holdout_baselines.py`:
  - `test_l1_predicts_the_cell_and_never_the_respondent_themselves`
  - `test_a_small_cell_backs_off_to_a_coarser_one`

**7e, split (2026-10-13).** The fieldwork executor chose its plans inline and had no seam a
validation could hand its arm plans to. The preregistration must also exist before the run, so
storing it moves from 7f to 7e2. The sub-chunks are 7e1-7e4 above.

**7e1 landed.** `AIFieldwork.answer_plans(plans, spec, context, *, seed, response, data_class,
lineage) -> Answered | Failed` is everything fieldwork did after choosing its plans:
- the preflight on the first plan with a block;
- one request per respondent block;
- the draw by code;
- the call ledger and the progress.

`produce` now calls it, and its behaviour is unchanged: the executor suite passes, 467 passed and
2 skipped, the same as before. A validation's replicate calls it with its arm plans and its own
seed.

Test: `test_ai_fieldwork_answer_plans.py`, `test_plans_from_elsewhere_are_answered_block_by_block_and_drawn_by_code`
(a scripted caller, no network).

**Out of scope:**
- tuning the persona to pass (a change after a failure is a new system, with a new draw);
- calibration layers (18.6.6's `output_calibration` / `persona_calibration`);
- any external survey's acquisition.

## Findings

- **A client-facing number can print "měřeno" beside "modelováno: AI respondenti z populace".**
  Hypothesis about production, reproduced in tests: the print grade follows the claim's basis
  and the composer's `field_grades` (`domain/report/evidence.py:58-65 @ 5f204ce1`), never the
  row's origin, and since 4b the only client-admissible origin is `MODELLED_AI_PANEL`. So a
  measured-basis claim on a population field graded `MEASURED` prints the measured mark beside
  the modelled disclosure. Reproduction:
  `pytest packages/aia_core/tests/test_report_docx_tables.py -k caption_numbers` (the caption
  reads "n = 480; měřeno; modelováno: AI respondenti z populace"). Consequence: once a
  client report exists, a reader sees two contradictory words on one number. No production
  composer passes `field_grades` today (OI-9), so no report prints it yet. Smallest fix, for
  analysis-governance with OI-9: a `MODELLED_AI_PANEL` row grades `MODELLED` whatever its
  basis, or such a row cannot back a measured claim at admission. Test that catches it: a
  ledger test asserting a modelled-panel row never grades `MEASURED`.

- **OI-7 is not archive-blocked: the source it waits for is vendored.** OI-7 says the seven
  enrichment derivations exist only in the withheld archive, so the ANALYSIS view, which every
  research run's binding names, cannot load. The archive source it pins,
  `audience_dimensions.py` SHA256 `6ae1d1f8d9ae8a5a9e007e0aee1b842b2c087ca16e888cc2cbf0e55ab7c754bf`
  (`docs/migration/population-enrichment-archive-dependency.md:21`), is byte-identical to
  `legacy/npc-panel-18.6.6/app/audience_dimensions.py @ ea5210e` (vendored by ADR 0011).
  Reproduction: `sha256sum legacy/npc-panel-18.6.6/app/audience_dimensions.py`. Consequence:
  a blocker carried as "data/archive acquisition, not engineering" has been an engineering
  task since the extraction; no research step could read the population meanwhile. Smallest
  fix: chunk 2d. The test that would have caught it: a check that every archive dependency
  pinned by hash in `docs/migration/` is absent from `legacy/` before it is called blocked.

- **Opening the licence gate alone would have made a non-fictional persona cost money
  before failing.** With chunk 0's records and no guard, a non-fictional persona on
  `bedrock-eu-primary` passed preflight; every respondent's blocks were sent and paid
  for, and only then `assemble_dataset` refused the dataset
  (`domain/ai_respondent.py:682 @ 5d545eb`), so the attempt ended `UNKNOWN`. No
  production path built such a persona, since `fictional_roster` is the only source.
  Reproduction: remove the guard and run
  `test_ai_fieldwork.py -k panel`; it fails with `FailureClass.UNKNOWN`. Fix: the
  pre-call guard in `ai_fieldwork.py` (chunk 0). Chunk 5 replaces it with the panel
  source.

- **The unit's fallback quotas can give a full cell a seat, and the sample then fails.**
  Once the remainders are spent and capped cells pass their seats on, `_quota_vector_fallback`
  adds its tie-break noise to every cell, full ones included
  (`legacy/npc-panel-18.6.6/app/representative_sampling.py:124`), so a full cell can win a seat
  it has no row for and the draw raises "Buňka … nemá dost respondentů" (`:153`).
  Reproduction: `pytest packages/aia_core/tests/test_population_sampling.py -k overfilled`
  (fixture D15: 663 of a 663-row audience; D16: 640 of 663; both refused by the unit).
  Consequence: in 18.6.6, only where the MILP was unavailable, a sample near its audience's
  size failed though it could be drawn. AIA keeps full cells out of the seat
  (`domain/population/sampling.py`, `quotas`); wherever the unit produced a sample the quotas
  are identical. The test that catches it: `test_where_the_unit_overfilled_a_cell_aia_keeps_every_quota_within_its_rows`.

- **On the fallback path a small sample is refused as unrepresentative; owner decision
  needed before chunk 5.** The largest-remainder quotas balance only the joint cells of
  `pohlavi x vek_skupina x kraj`; `vzdelani` and `zamestnani_status` are left to raking, and
  when a sample holds none of a category raking cannot reach its target, so the weighted
  deviation passes `max(0.25, 100/n)` and the sample is refused (`sampling_unrepresentative`,
  the unit's own rule, `representative_sampling.py:165-166`). Measured on the fixture's 3,000
  fictional rows (60 joint cells), AIA's draw over seeds 0-39: n = 5 to 40 refused 40/40;
  n = 50 12/40; 60 9/40; 75 1/40; 100 2/40; 150 1/40; 200, 300, 500 0/40. The unit's own
  fallback refuses n = 8, 20 and 30 in the fixture (D08, D03, D12). The seed is fixed per run
  (`fieldwork_seed(spec)`), so a refused study stays refused until its n or audience changes.
  v17 has more joint cells (14 regions), which raises the floor. The unit's live path, the
  MILP, solves every margin jointly and was not built to this limit; its `attempts=40`
  parameter is never read (`representative_sampling.py:131-173`), though the 17.7 comment at
  `pipeline.py:288-292` says it draws repeatedly and keeps the best. Reproduction: the loop in
  this section's measurement, `representative_draw` + `judge` over `_audience({})`. Options
  for the owner: (a) accept it and say the minimum n where the study is set; (b) a stdlib
  integer calibration of all five margins (controlled rounding), parity then by property
  only; (c) the attempts the comment describes: redraw under derived seeds and keep the
  first that passes, recorded in the sample. Not decided here.

- **18.6.6 sampled and styled only rows with an age of 18 or more; AIA's 2e sampler takes every
  row.** `Panel(df, min_vek=18)` drops rows whose `vek` is missing or under 18 before anything
  else (`legacy/npc-panel-18.6.6/app/pipeline.py:147-152`); `draw_panel_sample` has no such step
  (`domain/population/sampling.py @ a1fcc60`). Hypothesis for v17: no row is affected (its core
  donors are PIAAC 18-65 and ISSP 66+, `CORE_JOINT_STATUS.json` `core_sources`); not verified, no
  panel rows here. Consequence if wrong: AIA could sample a row 18.6.6 never could, and its column
  types (hence filter keys) could differ. Fix taken: `panel_personas` refuses a population with
  any such row (`persona_age_out_of_scope`), so a run fails closed before fieldwork; chunk 5's
  preflight reports the count on develop. Tests:
  `test_a_persona_that_cannot_be_built_as_18_6_6_built_it_is_refused[minor]`, `[no_age]`.

## Doc follow-up

- `CLAUDE.md` § research run: "Panel-derived data reaches no model provider until OI-61
  records a licence determination" → panel-derived data may reach `bedrock-eu-primary`
  (OI-61 determined 2026-10-12, owner); fictional and panel persona sources.
- `.planning/open-items.md` OI-61: resolved, citing chunk 0's commit.
- `ARCHITECTURE.md` / evidence: the new origin and its MODELED-only admission.
- `CLAUDE.md` § 2 map, under `domain/population/`: `sampling.py`, "the run's sample: the
  audience (audience.py), 18.6.6's largest-remainder quotas over sex x age group x region
  (+ education from n 700), weighted draw without replacement, raking and the audit; refusals
  by name; PanelSample.provenance() is what a run records"; under `tools/`:
  `sampling_capture.py`, "Sample fixtures from the unit's own draw_representative, the MILP
  made to fail (`inputs`, `capture` in the unit's venv)".
- `CLAUDE.md` § 2 map, `domain/`: `persona_profile.py` ("a panel respondent's profile:
  18.6.6's generate_persona_text in the mode it ran, calibrated -> core adaptive, EXACT"),
  `persona_topics.py` ("a question's topics: odvod_temata, a block's union, EXACT"),
  `persona_signals.py` ("the catalog's topic-matched signals: grounded_profile_text, EXACT"),
  `panel_persona.py` ("a run's sample as personas: the policy and joint gates, styles over the
  population, a profile per block; refusals by name"); `population/runtime.py`:
  "`companion(asset_id)`: a companion's bytes as the loader verified them"; `tools/`:
  `persona_capture.py`.
- `AGENTS.md` § mypy: running `mypy` over a subset of the source trees (e.g.
  `packages/aia_core/src apps/executors/src`) then the full invocation reported three false
  `create_model` errors in `domain/ai_respondent.py`; `rm -rf .mypy_cache` and the full
  invocation passed. Wrong: a partial run on a shared cache. Right: always the Makefile's four
  trees, or clear the cache after a partial run.
- `docs/architecture/population.md`: `RuntimePopulation.companion` is the one way a consumer reads
  a companion.
- `.planning/open-items.md`: the two 2e findings above (the overfilled cell, fixed here; the
  small-n refusal, open for the owner).
- (6b) `CLAUDE.md` § 2 map: under `domain/population/`, `audience_catalogue.py`, "the audience
  factor catalogue: 18.6.6's `catalog` (EXACT, `catalogue.json`), each factor's
  AUDIENCE_FILTERING answer (`catalogue_of`), research-only factors not sent (`for_the_screen`)";
  under `application/`, `audience_catalogue.py`, "LIVE's kept catalogue and the 18 subpanels as
  filters; reads no row"; `routers/population`: "GET /population/audience-catalogue: LIVE's kept
  catalogue and the subpanels as filters, any member"; `population_ops`: "record-catalogue (acts
  as no one; run by the develop deploy) keeps each population's current version's catalogue";
  `population_repository.py`: "each version's audience catalogue
  (population_version_audience_catalogues), insert-once"; `tools/audience_capture.py`: "also the
  unit's own `catalog` (`catalogue.json`)".
- (6b) `deploy/develop/README.md` § The population: each deploy runs `bin/population.sh
  record-catalogue` after `record-dictionary`; a version no population has been on has no
  catalogue until it is promoted (the next deploy records it).
- (6c) `CLAUDE.md` § 2 map: under `domain/population/`, `audience_preview.py`, "the audience
  step's preview: select_audience's counts and draw_panel_sample's verdict at PREVIEW_SEED;
  counts only"; under `application/`, `audience_preview.py`, "AudiencePreviewer: LIVE loaded
  once per process and version, through PopulationRuntime"; `routers/population`: "POST
  /population/audience-preview (any member; 503 without AIA_POPULATION_ASSET_ROOT)"; `config.py`
  / § The develop site: the API reads `AIA_POPULATION_ASSET_ROOT` for the preview only.
- (6c) `deploy/develop/README.md` § The population: the API service mounts the population
  read-only for the preview; `AIA_API_POPULATION_ASSET_ROOT=` (empty) turns it off; the first
  preview after a deploy or a promotion loads LIVE (seconds, memory as measured in 6c).
- (6e) `CLAUDE.md` § 2 map, `src/components/rehome/`: "the audience step's factor editor, preview
  and built-in subpanels from AIA's population (GET /population/audience-catalogue, POST
  /population/audience-preview); special panels and own audience say V AIA zatím není";
  `.planning/open-items.md` OI-50: AIA's live editor leaves an empty bound out
  (`research/audience.ts` `setRange`, `audience.live.test.ts`); the classic port keeps the
  classic's 0 for parity only.
- (6f) `CLAUDE.md` § 3 commands: "**Audience step, end to end** | After `make ui-workbench` +
  `make ui-fixtures`, `make ui-audience` (Playwright + Chromium): filters from the workbench's
  fictional population, the preview, the built-in subpanels; fictional rows only"; § 2 map,
  `tools/ui_workbench/`: "fictional_population.py: the audience step's fictional LIVE (the
  sampler's rows), installed through `aia_api.dependencies.AudiencePopulation`";
  `dependencies.py`: "AudiencePopulation: the population the audience routes read (the Czech
  LIVE; the workbench's fictional one)".
