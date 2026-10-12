---
status: in-progress
chunks:
  - "[x] 0. Record the OI-61 determination: PIAAC, ISSP and the Czech panel APPROVED for bedrock-eu-primary"
  - "[x] 1. ADR: panel-grounded AI respondents are modelled evidence, never measured"
  - "[x] 2a. Sampler contract (plan before code): inputs, quota fields, the audience filter, refusals, what a sample records"
  - "[x] 2b. Verify the quota and donor fields against the imported v17 dictionary on develop"
  - "[ ] 2c. Audience filter: sanitize_filters + _mask as one function, the factor map's kinds, subpanels through it; parity fixtures"
  - "[ ] 2d. Quotas, draw, raking and audit (draw_representative's stdlib path); parity fixtures"
  - "[ ] 3. Persona: facts and the structured profile from the sampled row, every field through decide(PERSONA_CONSTRUCTION)"
  - "[ ] 4. Origin: MODELLED_AI_PANEL through dataset, analysis, Sociomap and report, MODELED basis with disclosure"
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

**The sample (2d).** `draw_panel_sample(population, filters, n, seed) -> PanelSample`:

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
that is decided here before 2d is written.

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
icons for `AUDIENCE_FILTERING` (they did not survive the copy); 2d asks
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

**3. Persona.** Port `generate_persona_text` (persona modes, top-k traits,
structured format). Every field shown or used asks
`RuntimePopulation.decide(field, FieldUse.PERSONA_CONSTRUCTION)` and, combined,
`decide_joint`. The fact layer reads the row's columns: a question the panel answers
becomes DIRECT (answered by code) instead of UNSUPPORTED. Styles from
`assign_styles` over the real rows. Real weights and donor ids. Parity fixtures.

**4. Origin.** `DataOrigin.MODELLED_AI_PANEL`; dataset, analysis harness
(`analysis/harness.py:141`, `analysis/native.py:491`), Sociomap labelling
(`research_sociomapping.py:359`) and report read it as modelled, never synthetic
fiction and never measured.

**5. Executor.** `ai_fieldwork` takes a persona source per run: fictional roster or
panel. Behind `AIA_AI_PANEL_PERSONAS_ENABLED`, off by default and in test. The
profile is longer than four facts: measure input tokens and cost per respondent and
state them in the commit body. The run's provenance names the source, binding,
roster or sample version and the persona mode.

**6. Screens.** Audience filters and the 18 subpanels become live where they now say
"V AIA zatím není"; results say "modelováno" every time.

**7. Validation.** Port the unit's persona ablation (`persona_ablation.py`: arms
none / demographics / full, TVD per question) and add a holdout: questions whose
population marginals are known (ISSP items in the panel), asked of panel-grounded
respondents, compared. No client-facing claim until the holdout result is recorded.

## Findings

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

## Doc follow-up

- `CLAUDE.md` § research run: "Panel-derived data reaches no model provider until OI-61
  records a licence determination" → panel-derived data may reach `bedrock-eu-primary`
  (OI-61 determined 2026-10-12, owner); fictional and panel persona sources.
- `.planning/open-items.md` OI-61: resolved, citing chunk 0's commit.
- `ARCHITECTURE.md` / evidence: the new origin and its MODELED-only admission.
