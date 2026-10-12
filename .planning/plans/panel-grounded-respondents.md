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
  - "[ ] 4e. aia-instrument-evidence-2 and the validation gate (ADR 0024 §3-§5): client-facing only when validated"
  - "[ ] 5. Executor: the panel source behind AIA_AI_PANEL_PERSONAS_ENABLED (off by default), cost measured"
  - "[ ] 6. Screens: audience and subpanels live where they say 'V AIA zatím není'; modelled labelling"
  - "[ ] 7. Validation: persona ablation and a holdout against known marginals before any client-facing claim"
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

**4. Origin.** `DataOrigin.MODELLED_AI_PANEL`; dataset, analysis harness
(`analysis/harness.py:141`, `analysis/native.py:491`), Sociomap labelling
(`research_sociomapping.py:359`) and report read it as modelled, never synthetic
fiction and never measured.

**5. Executor.** `ai_fieldwork` takes a persona source per run: fictional roster or
panel. Behind `AIA_AI_PANEL_PERSONAS_ENABLED`, off by default and in test. The
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

## Findings

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
