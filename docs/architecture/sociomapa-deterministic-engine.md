# Sociomapa deterministic engine — what is ported, what is declared, what is refused

**Status:** engine implemented (`ENGINE_IMPLEMENTATION_VERSION = "1.1.0"`), spec
and artifact contract **version 2**. Ported against golden fixtures F1–F9 from
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
    → placeable rows (≥ 2 ratings, not all at the top) others excluded, with a reason
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
