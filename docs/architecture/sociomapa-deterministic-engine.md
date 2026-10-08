# Sociomapa deterministic engine — what is ported, what is declared, what is refused

**Status:** engine implemented (`ENGINE_IMPLEMENTATION_VERSION = "1.2.0"`), spec
and artifact contract **version 2** (`aia-sociomap-1`); since 2026-10-08 a second
method, **`aia-sociomap-2`** (spec and artifact contract **3**, the formula audit's
object map, §5a), is computed beside it. Both are `INTERNAL_ONLY` (D6, §13). Ported against golden fixtures F1–F9 from
`AiAnalytics-AIA/AIA-reference` @ `678e298ad9ca0263da53cc8920d153fdfb956c93`.
**Not ported, and refused:** the reference's two layout algorithms — see §4.
**R numerical parity is not claimed** and cannot be until `REF-GAP-SOCIO-R-SMACOF`
has its fixture.

Normative source: `sociomapping-reference-contract.md` and
`sociomapping-deep-dive.md` in the reference repository. This document records
how the production engine meets that contract, where it deliberately differs,
and what it could not reproduce. Companion to
[ADR 0007 (no LLM for deterministic computation)](adr/0007-deterministic-tools.md)
and [domain-map.md](domain-map.md).

## 1. The boundary

```
deterministic software   establishes numerical research truth   compute_sociomap
LLM agents               choose, interpret, explain              consume artifacts
humans                   approve methodology and conclusions     gates (elsewhere)
```

| Group | Contents | Where |
| --- | --- | --- |
| **A — research truth** | relation coercion and projection, ipsatization, dissimilarities, layout, coordinates, stress, object metrics and T-score, normalisation, both terrain fields | `domain/sociomap/{relations,layout,metrics,terrain,engine}.py` → `SociomapArtifact` |
| **B — methodology** | every choice above, as data | `SociomapSpec` v2, fingerprinted, no defaults, `require_supported` |
| **C — LLM** | hypotheses, segment proposals, which tool, interpretation | consumes artifacts; supplies no number |
| **D — human** | adopting a spec for a client study; methodology exceptions | existing gates |
| **Presentation** | drag state, view terrain over dragged positions, scenario layers, pixels | `view.py` reads an artifact, never writes it; `apps/web` renders |

**The terrain, the normaliser and the object metrics were browser-only in the
reference** (`ui_app.html`, three live terrain implementations, no backend
counterpart). They are now backend computation with Python tests. The client
renders `SociomapArtifact.respondent_terrain` / `object_terrain` and must not
recompute them.

## 2. Pipeline

```
SociomapInputs
  ratings  (respondents × objects, None = unrated)
    → range check against the declared scale          refused, never clipped
    → placeable rows (≥ 2 ratings, not a straight-liner at any score)
                                                       others excluded, with a reason
    → dissimilarity  δ = scale_top − rating
    → aia_rowcond_unfolding_v1                         gauge-fixed coordinates, stress
    → map frame  max |coord| → extent                   terrain-grid units
  object_relation  (objects × objects, directed, optional)
    → missing policy (refuse | reference 5.5 sentinel)
    → coerce_relation_scale_1_10        directed                          F1
    → mutual_relation_for_position      symmetric [0,1], position input   F2
  object metrics   mean_rating, support_n [, relation_classic, T-score]   F6
  terrain          respondent density   σ = 9.5                           F7
                   object weighted mean σ = 12, spec's height metric      F8
→ SociomapArtifact
```

Beside it, stored by the research step (`domain/research_sociomap.py`) and read by no
surface yet: each pair's signed r, rater count, Fisher-z interval and status (audit F3:
UNKNOWN below `n_min`, never stamped 5.5); each pair after the rating habit is removed
(`relation_rescaled`, audit F2); alignment and connectedness over the PRIMARY objects
(`object_scores`, audit F8); K100 with its bootstrap interval (audit F9), only when the
worker's `AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED` is on. The relation step's scale
coercion is either the reference's detection (`aia-sociomap-1`, fixture F1) or a declared
matrix type (`DECLARED_*`, audit F5; a declared strength 1–10 is refused by name).

`aia-sociomap-2` (`domain/sociomap/engine_v2.py`, `compute_object_map`) is its own chain
over `ObjectMapInputs`:

```
ObjectMapInputs  the rating universe (every tracked set's items + the declared standalone
                 rating questions, each on its declared scale), raw ratings, weights,
                 the mapped objects with their items and roles (PRIMARY / SECONDARY)
  → F1 each item onto 0–1 by its own declared ends          refused off scale
  → F2 person_minmax: each person's own 0–1 over every item they rated; straight-liners
       not placed (counted in heights and support)
  → F3/F4 derive_pair_relations: signed r~, n, interval, status; UNKNOWN weight 0
  → F6/F7 sqrt(2 (1 − r~)) on a fixed ruler, weighted SMACOF from a Torgerson start,
       Stress-1 with its band; never rescaled to a radius
  → F8 primary_scores    → F9 connectedness_100 (when asked)
→ SociomapArtifactV3     MAPPED, or NOT_MAPPABLE with its reason (too few objects, no
                         known pair, a disconnected known-pair graph, a singular fit)
```

Respondent placement and terrain are not part of contract 3 yet: the spec declares them
`None` and the artifact carries them as `not_computed` with the reason.

`ipsatize` (F3) is ported and tested, and the spec carries an `ipsatize` flag,
but the one implemented dissimilarity target reads a rating's position on the
declared scale, which an ipsatized value does not have. `ipsatize: true` is
therefore refused rather than silently ignored.

## 3. What each fixture proves

Every fixture was reproduced from the contract's formulas **before** the design
was chosen. The measurement is recorded in
[`.planning/plans/done/sociomap-deterministic-engine.md`](../../.planning/plans/done/sociomap-deterministic-engine.md).

| Fixture | Function | Result | Test |
| --- | --- | --- | --- |
| F1 | `coerce_relation_scale_1_10` | **match**, all 5 cases, branch exact, values to the fixture's 10-decimal serialisation | `test_f1_coercion_matches_the_reference` |
| F2 | `mutual_relation_for_position` | **match** ≤ 1e-9 (fixture serialised to 10 dp; tolerance 1e-12 on unrounded values) | `test_f2_mutual_relation_matches_the_reference` |
| F3 | `ipsatize` | **match** | `test_f3_ipsatization_matches_the_reference` |
| F4 | legacy `fit_python_unfolding` | **not reproduced — refused.** See §4 | `test_legacy_algorithms_fail_closed_and_say_why` |
| F5 | `build_normalizer`, all 7 cases | **match** ≤ 1e-9, labels included | `test_f5_normaliser_matches_the_reference` |
| F6 | `object_metric`, 4 metrics | **match** ≤ 1e-9, directly and through the pipeline | `test_f6_object_metrics_match_the_reference`, `test_relation_metrics_through_the_pipeline_match_f6` |
| F7 | `compute_terrain` respondent density | **match**: every sample's hr/cr/ht/z ≤ 1e-9, 1,849 finite cells, normaliser, Σht | `test_f7_every_sample_matches` |
| F8 | `compute_terrain` object mean | **partial**: constants, bounds, hr → ht → z chain, null-cell semantics. The object *positions* come from `baseObjectLayout66`, source withheld; a 2,000-start inverse fit found no consistent placement | `test_f8_*`, `test_one_object_gives_its_own_value_wherever_it_has_support` |
| F9 | `apply_view_overrides` | **match** on all four assertions (position changes; point, matrix unchanged; view key changes) | `test_f9_manual_drag_is_a_view_override` |

The fixtures are vendored under `packages/aia_core/tests/fixtures/sociomap/`,
each pinned to its SHA256 in `index.json`, so this evidence runs in **every CI
job** — unlike the legacy-source parity tier (OI-1).

## 4. Layout: declared, never detected

The reference picks its algorithm by probing the host (`shutil.which("Rscript")`)
and silently falls back from R to Python — the same study gives different
coordinates on different machines. Production keeps a registry,
`LAYOUT_ALGORITHMS`, and the spec names one entry. There is no `auto`.

| Identifier | Status | Why |
| --- | --- | --- |
| `python_weighted_unfolding` | **unavailable — refused** | Source withheld (`REF-WITHHELD-REFERENCE-ARCHIVE`). F4 pins its output, not its method: ~200 candidate stress definitions evaluated on F4's own coordinates, none reproduces `stress_1 = 0.391394498`, and an optimiser cannot be matched to 1e-6 by guessing |
| `r_smacof_unfolding` | **unavailable — refused** | `REF-GAP-SOCIO-R-SMACOF`: no R fixture exists, so there is nothing to be at parity with |
| `aia_rowcond_unfolding_v1` | **implemented** | Specified in full in `layout.py`'s module docstring |

`aia_rowcond_unfolding_v1`: row-conditional **ratio** unfolding. Disparities
`dhat_ij = b_i · δ_ij` with one free scale per respondent (respondents use the
scale differently) and one global normalisation `Σ b_i²|δ_i|² = C` against
collapse. Stress `Σ (dhat − d)²` is minimised by three alternating exact block
steps — respondents, objects, row scales — none of which can increase it.
Initialisation is classical scaling of object profile distances (cyclic Jacobi)
with preference-weighted respondents; the gauge is fixed afterwards (object
centroid at the origin, principal axes, positive third moment). **No RNG**, so
`layout.seed` must be `null`; a seed would be recorded as if it mattered.

**Sparse designs.** The co-rating graph must be connected; object pairs nobody
co-rated start from the mean known profile distance
(`test_a_connected_sparse_design_recovers_planted_geometry`). A shortest-path
start was tried first and measured worse: on two rating blocks sharing four
objects it settled into a reflected block at RMSD 1.47, against 0.018 for the
mean.

**Local minima.** The start is single and deterministic, so the fit can stop in
a local minimum — measured on one fully observed planted 60 × 8 design at
stress-1 0.017, where two other planted designs reach < 1e-4. Low stress does
not prove the geometry is unique; a design whose blocks share only two objects
admits a reflected block at nearly the same stress. Multiple deterministic
starts are the obvious next step and are not implemented.

What pins it, since no reference can:

- **Recovery.** Data generated from a known configuration, with arbitrary
  per-row scales and missing cells, is recovered to stress-1 < 1e-4 and
  Procrustes RMSD < 1e-3 (`test_recovers_the_geometry_that_generated_the_data`,
  `test_row_scales_absorb_how_each_respondent_uses_the_scale`).
- **Monotone.** Stress never increases with more iterations
  (`test_stress_never_increases_with_more_iterations`).
- **Bit-identical** across runs (`test_identical_input_gives_identical_bits`).
- **Its own golden fixture** on F4's ratings,
  `fixtures/sociomap/aia/AIA1_rowcond_unfolding_on_f4_ratings.json`, written by
  `tools/sociomap_golden.py` (`test_golden_layout_and_terrain_are_reproduced`).
  Regenerate only with an `ENGINE_IMPLEMENTATION_VERSION` bump.

**Distance from the reference, measured.** On F4's ratings, after optimal
translation, rotation, reflection and scale, the AIA configuration sits at
**Procrustes RMSD 1.91 (worst point 2.99) against the legacy configuration's
RMS radius of 2.01** — i.e. unrelated geometry. That is expected: different target, different
optimiser, and F4's ratings are uniform random, so there is no structure for two
methods to agree on. It is stated so nobody mistakes the AIA layout for a port.
Reproduce: run `procrustes_align` on F4's `expected_output` against the golden's
coordinates.

**Deliberately pure Python, not numpy.** `domain/` is stdlib +
Pydantic only (`ARCHITECTURE.md §2`), and a BLAS-backed SVD is not bit-stable
across hosts and thread counts — the host-dependence this work exists to remove.

## 5. `SociomapSpec` v2

Every field is required; `AIA_SOCIOMAP_V1` is a named preset adopted
explicitly. `require_supported` reports every problem at once, as
`UnsupportedMethodology.unsupported = {field path: reason}`.

| Section | Field | Preset | Source |
| --- | --- | --- | --- |
| `ratings` | `ipsatize` | `false` | AIA — see §2 |
| | `dissimilarity` | `scale_top_minus_rating` | **AIA declaration** |
| | `rating_scale_min/max` | `1` / `10` | reference 1–10 scale (F1, F8 bounds) |
| | `missing_data_policy` | `observed_cells_only` | reference (F4 metadata) |
| `relation` (nullable) | `scale_coercion` | `reference_coerce_1_10` | reference (F1) |
| | `position_projection` | `mutual_arithmetic_mean` | reference (F2) |
| | `missing_data_policy` | `refuse` | **AIA — fail closed**; `reference_midpoint_sentinel` is available by declaration |
| `layout` | `algorithm` | `aia_rowcond_unfolding_v1` | **AIA declaration** |
| | `parameters` | `dimensions 2, max_iterations 2000, convergence_tolerance 1e-7` | tolerance from the reference's `\|Δstress\| < 1e-7` |
| | `seed` | `null` | deterministic |
| | `map_frame` | `max_abs_to_extent`, `45` | **AIA declaration** — the reference's layout→screen scaling is unrecovered; 45 matches F7's ±45 synthetic points |
| `metrics` | `object_height_metric` / `colour` | `relation_classic_tscore` | reference default (F6) |
| `terrain` | `respondent` | `N 42, span 62, σ 9.5, cutoff 0.0005, z 26` | reference (F7) |
| | `object` | same, `σ 12` | reference (F8) |
| | `normalization` | `range` | reference default |

The fingerprint is a SHA256 over the contract version and every field;
`test_every_field_changes_the_fingerprint` and
`test_spec_has_no_hidden_defaults` (every path, every depth) pin both rules.

## 5a. `SociomapSpecV3`: contract 3, `aia-sociomap-2`

Contracts are added beside each other, never edited: a stored spec is read by the contract
it names (`read_spec` / `spec_payload`, `SPEC_CONTRACTS`; none or another is
`UnknownSpecContract`). Contract 2 is unchanged and `AIA_SOCIOMAP_V1` keeps its fingerprint
`9d4dffea…` (`test_the_v1_preset_fingerprint_has_not_moved`). Contract 3's members
`DissimilarityTarget.CORRELATION_DISTANCE`, `LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1` and
`MapFrameMethod.FIXED_RULER` are refused by contract 2 by name
(`test_contract_2_refuses_contract_3s_members`).

| Section | Preset `AIA_SOCIOMAP_V2` (`3f1c0122…`) | Source |
| --- | --- | --- |
| `ratings` | `declared_ends_0_1` (F1), `person_minmax_all_rated` (F2) | audit F1, F2 |
| `relation` | `weighted_pearson`, basis `respondent_count`, `n_min` 30, confidence 0.95 | audit F3 (`n_min` provisional, Q6; Kish's n is chunk 1d's) |
| `layout` | `aia_smacof_objects_v1`, `correlation_distance`, 5,000 iterations, tolerance 1e-12, `fixed_ruler` | audit F6, F7; iterations and tolerance AIA declarations |
| `scores` | height `mean_rating_0_1`; the F8 PRIMARY scores beside it | audit F8 (default height provisional, Q7) |
| `connectedness` | K100, B = 500, seed 20261007 | audit F9; OI-62's generator |
| `respondent_placement`, `terrain` | `None` (refused if declared: not computable yet) | chunk 3, 4b |

`require_supported` for contract 3 names each refused field
(`test_contract_3_refuses_what_it_cannot_compute_by_name`).

**A run pins its methods.** `ResearchRuns.start` resolves `default_methods()`
(`aia-sociomap-1` and `aia-sociomap-2`) into `SociomapMethod`s (id, the whole spec as
stored, its fingerprint) on the run's metadata and the `sociomap` step's input; the
executor computes the pin, never the module preset, and fails the step with
`sociomap_method_invalid` for a pin that does not verify. A retry pins what the retried run
pinned; a run stored before pins existed reads as `aia-sociomap-1` (`LEGACY_METHODS`). Only a
set the caller *chooses* over the default changes the run's identity, so re-starting a
revision after the default changed returns the run that exists and pays for no fieldwork
(`test_a_restart_after_the_default_changes_returns_the_run_and_pays_nothing`).

## 6. `SociomapArtifact` v2

| Field | Meaning |
| --- | --- |
| `spec` | the full spec, and so its fingerprint |
| `respondent_ids`, `object_ids` | canonical order |
| `excluded_respondents` | `{id: reason}` for respondents with no recoverable position; every respondent is placed *or* excluded (validated) |
| `layout` | algorithm, `gauge_fixed`, placed ids, respondent and object coordinates in map units, `layout_to_map_scale`, `stress_1`, `normalized_stress`, iterations, converged, diagnostics (row scales, principal-axis gap) |
| `relation` | coercion branch, coerced directed matrix, position-input matrix, any sentinel-substituted cells |
| `object_metrics` | every computable metric, aligned with `object_ids` |
| `respondent_terrain`, `object_terrain` | 43 × 43 `hr`, `cr`, `ht` grids with parameters and normaliser bounds |
| `provenance` | implementation + version, input fingerprints, layout algorithm, seed |
| `warnings` | exclusions, non-convergence, sentinel use, objects missing a height value |

No timestamp and no host detail in the body: either would make identical
computations on two machines look different. `to_payload` / `from_payload`
round-trips and refuses a tampered body. Storage is
`ArtifactRepository.put_json(payload=artifact.to_payload(), …)`; no new table.

`SociomapArtifactV3` (`models_v3.py`, contract 3) is read by its own model: relations with
`abs_r`, `not_placed`, `outcome` with its reason, the layout with Stress-1 and its band,
scores, heights, K100, `roles`, `items` (the rating universe with each item's scale), and
`support` (respondents, placed, not placed, Kish's effective n over the placed, distinct
donors, the weighting rule in words). `read_artifact` reads contract 2 exactly as before,
contract 3 by its model, and refuses anything else. In the research body each battery
carries the contract-3 payloads under `maps`, keyed by method id.

## 7. View and scenario layers

- **Drag** (`ViewOverrides`, `{respondents, objects}` like the reference's
  `st.manual`) is bound to the artifact fingerprint; `apply_view_overrides`
  returns a `DisplayedMap` with `view_key()` — the backend counterpart of the
  reference's terrain cache key. `view_terrain` recomputes terrain over the
  *displayed* positions (as the reference does after a drag), for a respondent
  subset (`terrainScope == 'filter'`) or another metric, and returns a view
  product that is never stored on the artifact.
- **What-if** (`ScenarioLayer` of `RelationEdit`s) implements
  `effectiveMatrix66` in scenario mode on the coerced matrix: edits override
  cells, the diagonal is held at 0 (a diagonal edit is refused rather than
  silently ignored). `apply_scenario` recomputes the relation metrics and the
  object terrain; positions come from the ratings unfolding, which a relation
  edit does not touch, so a scenario moves no point.

## 8. Intentional differences from the reference

| # | Reference | Production | Test |
| --- | --- | --- | --- |
| S1 | layout algorithm chosen by probing for `Rscript`, silent R→Python fallback | declared in the spec; unavailable ⇒ `LayoutUnavailable` | `test_there_is_no_auto_or_alias`, `test_unsupported_methodology_fails_closed` |
| S2 | unknown object-metric id silently renders the T-score | refused | `test_unknown_metric_id_is_refused_not_turned_into_a_tscore` |
| S3 | unknown normaliser mode falls through to `range` | refused | `test_normaliser_refuses_an_unknown_mode` |
| S4 | missing relation → 5.5 midpoint (unknown scored as neutral, A4) | refused unless the spec declares the sentinel; substitutions recorded | `test_a_missing_relation_cell_is_refused_by_default`, `test_the_reference_sentinel_is_used_only_when_declared_and_is_recorded` |
| S5 | sentinel/branch order ambiguous for a matrix mixing NaN with a [0,1]/[-1,1] scale | refused (`AmbiguousCoercion`) — the fixture only covers orders that agree | `test_coercion_refuses_the_unrecovered_sentinel_order` |
| S6 | absolute normalisation against any metric's `metricDef66` bounds | only where bounds were recovered (`density`: none); `mean_rating` is bounded by the spec's declared rating scale, 1–10 in the preset | `test_absolute_bounds_are_used_only_where_recovered`, `test_absolute_normalisation_uses_a_declared_non_default_scale` |
| S7 | terrain with no source (an empty filter) is fitted to the all-zero grid, called constant, and lifted to 0.5 everywhere | flat at 0: no source, no terrain | `test_empty_terrain_is_flat_at_zero_not_a_plateau` |
| S8 | a pair under five raters is 5.5, drawn as a medium relation | the unit's matrix kept for `aia-sociomap-1`; every pair carries its status, UNKNOWN below `n_min` (audit F3) | `test_a_pair_rated_by_too_few_is_unknown_where_the_unit_stamps_five_and_a_half`, `test_below_n_min_a_pair_is_unknown_whatever_its_number_says` |
| S9 | an unplaceable respondent is put on an invented ring (audit F11) | every straight-liner excluded with its reason, out of the density terrain, still counted in `support_n` | `test_a_straight_liner_below_the_top_is_not_placed`, `test_straight_liners_do_not_move_anyone_else` |
| S10 | the classic score `Σ_j (s_ij + s_ji)`, mostly the constant `11 (m − 1)`, a 5.5-stamped pair counted as medium, context objects in the sum | `relation_classic` kept for `aia-sociomap-1`; `primary_scores` beside it over PRIMARY objects, UNKNOWN pairs out (audit F8) | `test_the_scores_are_the_audits_formula_on_a_hand_computed_example`, `test_a_secondary_object_never_moves_a_primary_score_where_it_reshuffles_classic` |
| S11 | a supplied matrix's scale guessed from its values (r = 0.30 is 3.70 or 6.85) | `aia-sociomap-1` keeps the guess for fixture F1; `DECLARED_*` converts by the declaration and refuses what the type cannot hold (audit F5) | `test_the_same_correlation_means_the_same_strength_whatever_the_other_cells`, `test_the_engine_converts_by_the_declared_type_and_records_it` |
| S12 | weighted Pearson on raw ratings: the rating habit inflates r (+0.394 for six independent objects) | the unit's matrix kept for `aia-sociomap-1`'s layout; `relation_rescaled` beside it; `aia-sociomap-2` maps r~ (audit F2) | `test_the_rating_habit_inflates_raw_r_and_the_rescaling_removes_it`, `test_the_rating_habit_is_removed_through_the_engine` |
| S13 | targets `14 + 46 (1 − m / m_max)`, the map stretched to radius 38 or 44 (four copies, F7) | `aia-sociomap-1` keeps its unfolding; `aia-sociomap-2` places objects by SMACOF on the fixed ruler, never stretched (audit F6, F7) | `test_the_map_is_never_stretched_to_a_radius`, `test_a_family_without_structure_keeps_its_size_and_says_so`, `test_the_ruler_is_fixed_a_weak_family_is_drawn_small` |
| S14 | four layout copies that disagree (the scenario view turns the map a quarter and enlarges it 16 %), no fit shown | one layout, aligned to the previous by rotation/reflection only, as a view (`align_to_reference`); every Stress-1 labelled (`stress_quality`) | `test_a_turned_map_is_turned_back_without_scaling`, `test_every_stress_carries_the_audits_label` |
| S15 | the normative score `50 + 10 z` (panel ÷n, report ÷(n−1)), always winners and losers | `tscore` kept for `aia-sociomap-1`; `connectedness_100` with a bootstrap interval and `rank_with_ties` beside it: an order only where intervals part (audit F9) | `test_intervals_that_overlap_or_touch_are_tied`, `test_overlap_is_not_transitive_so_there_are_no_tie_groups` |

The envelope terrain (audit F12) takes the next free number when chunk 4b lands.

## 9. Performance

Measured on CPython 3.12, one core, synthetic structured ratings, full
`compute_sociomap` (layout + metrics + both terrains):

| Respondents × objects | Total | Iterations | Respondent terrain | Payload |
| --- | --- | --- | --- | --- |
| 40 × 8 | 0.11 s | 308 | 0.01 s | 194 kB |
| 200 × 12 | 0.41 s | 160 | 0.06 s | 216 kB |
| 1,000 × 20 | 3.3 s | 133 | 0.26 s | 282 kB |

Team-scale and study-scale maps cost nothing measurable. A 1,000-respondent map
takes seconds, which belongs in a worker job, not a request. The payload is
dominated by the two fixed 43 × 43 grids, not by `n`. Nothing is on a hot path
yet — no route or worker calls the engine — so no kill switch is needed until
one does (CLAUDE.md §8).

## 10. Agent tool boundary

Unchanged in principle: tools take typed inputs and a `SociomapSpec`, call
`require_supported`, and return structured data. `compute_sociomap`,
`view_terrain` and `apply_scenario` are the first three. Scope comes from the
trusted `StudyContext`, never a tool argument.

## 11. Contradictions found, not edited here

Carried over from the contracts-only version of this document. The other item
it listed -- `artifacts.md` calling computed layouts an ephemeral cache -- is
corrected in the same change as this engine.

1. `apps/web` still implements the superseded manual-Sociomapping SOP (an
   uploaded `sociomap` file, "Gate 5", an import pack). It should be rewired to
   render `SociomapArtifact`, not extended.

## 12. Open

Tracked in [`.planning/open-items.md`](../../.planning/open-items.md): OI-13 (the
reference's Python unfolding), OI-14 (`baseObjectLayout66`), OI-15 (R smacof,
`REF-GAP-SOCIO-R-SMACOF`), OI-16 (methodology sign-off for the AIA declarations
in §5, packaged for the owner in
[sociomapa-methodology-decision.md](sociomapa-methodology-decision.md)), OI-17
(the client-deliverable gate, §13). OI-13–15 are archive-acquisition
dependencies: reconstruction by inference has stopped. Not started: saved
segments, A/B comparison, object manager, request arrows, time series — each
needs its reference behaviour read first.

**The formula audit is a source** for `aia-sociomap-2` and the rows S8–S15: where it and an
earlier Sociomap decision disagree on AIA's object map, the audit wins
([`.planning/plans/sociomap-formula-corrections.md`](../../.planning/plans/sociomap-formula-corrections.md)).
Its provisional values (`n_min` 30, Q6; the default height, Q7) and AIA's readings put to its
author are recorded there.

## 13. Computable is not deliverable

Binding on every context that runs, stores, serves or shows a Sociomap.

1. **The engine computes what it is asked to.** `compute_sociomap` runs any
   explicitly supplied `SociomapSpec` that `require_supported` accepts.
   Supported means *computable*, nothing more.
2. **A Sociomap is client-facing only under an approved methodology.** An
   artifact may enter a client deliverable, export or client-role view only if
   its `spec.methodology_version` **and** `spec_fingerprint` are both approved
   in the product/methodology policy. Both, because two specs can share a
   version label and differ in a parameter. Nothing is approved today:
   `aia-sociomap-1` awaits D6
   ([decision document](sociomapa-methodology-decision.md)).
3. **No silent substitution.** No API, worker or UI supplies a spec that the
   caller did not give — not `AIA_SOCIOMAP_V1`, not "the last one used", not a
   per-environment default. A request without a spec is an error.

Where each part is enforced:

| Rule | Enforced by | State |
| --- | --- | --- |
| 1 | `require_supported`, `compute_sociomap` | **done** |
| 2 | the client-deliverable gate, reading an approved-methodology registry | **not built** — cross-context, owned by integration-architecture with product policy (OI-17) |
| 3 | `tools/layer_check.sh`: `AIA_SOCIOMAP_V1` may not appear in `application/`, `infrastructure/`, `apps/api`, `apps/worker` or `apps/web/src` | **done** as a static guard; a runtime "spec required" check lands with the first route or job |

The engine deliberately does not know what is approved. Approval is product
policy that changes on a person's decision; the engine is deterministic
mathematics that must not. Putting approval in the engine would make an
artifact's numbers depend on who signed what.
