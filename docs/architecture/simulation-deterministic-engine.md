# Simulation deterministic engine: boundary, contracts, parity status

**Status:** deterministic core implemented in `aia_core.domain.simulation`
(Phase 7, first slice). World-model *generation*, the per-world respondent run,
the learning layer and persistence are **not** built.
**Reference:** `AiAnalytics-AIA/AIA-reference` @ `678e298ad9ca0263da53cc8920d153fdfb956c93`
— `simulation-reference-contract.md`, `parity-plan.md`, `high-risk-behaviors.md`,
`reference-gaps.md`. Those documents are authoritative. This one records only
what production does with them.

> Numerical parity of the `FS_*` columns against the reference is **not claimed**.
> The reference formula bodies are in the withheld archive, and fixture F13 does
> not exist yet (§7).

## 1. The boundary

The reference Full Simulation runs two different kinds of work in one pipeline:
an LLM invents a *world model* (topic-specific latent factors, their drivers, and
how they co-vary), and a seeded numerical chain drives a population through it.
Production splits them at a typed boundary:

| Side | Contents | Where |
| --- | --- | --- |
| **Semantic** (model-generated) | factors, labels, drivers, effects, correlations; a scenario's narrative and proposed shifts | produced later by the AI runtime (Phase 4); enters only as a validated, frozen `WorldModel` and an approved `ScenarioContract` |
| **Deterministic** | world seeds, bound validation, correlation projection, inoculation, outcomes, ensembles, variant deltas, frozen predictions, write-once truth, eligibility, scoring | `packages/aia_core/src/aia_core/domain/simulation/` — pure, no I/O, no clock, no provider |

The core never calls a model, so a live model is never needed to test it. The
tests drive it from a frozen, hand-authored structured world model
(`packages/aia_core/tests/fixtures/simulation/world_model_frozen_v1.json`) and a
synthetic population generated from a fixed seed (`build_sim_population` in
`packages/aia_core/tests/conftest.py`). Neither is provider output or
reference material.

## 2. Pipeline and public API

```
raw model output (untrusted mapping)
  → validate_world_model(raw, schema, objective, research_sha256)   reject, list every violation
  → WorldModel                         frozen, sha256-addressed, markers, contamination derived
  → calibrate_world(baseline, wm, world_index, spec_seed)           fixed once per world
  → apply_world(population, wm, calibration) → InoculatedWorld       FS_* columns only
  → world_outcome → ensemble_worlds
  → run_variant(wm, baseline, schema, variant, spec_seed, n_worlds)  one variant, end to end
  → compare_variants(baseline_result, alternative_result)            deltas, per-world range
  → freeze_prediction → record_truth (write once) → score_prediction
```

`inoculate_population(population, wm, world_index=, spec_seed=)` keeps the
reference signature and is `calibrate_world` + `apply_world` on the same
population.

| Module | Owns |
| --- | --- |
| `reference.py` | Versioned constants, bounds, markers, seed derivation, and `FIELD_POLICY` — the per-field record of intentional differences |
| `world_model.py` | `PanelSchema`, `WorldModel`, `validate_world_model`, `Violation` |
| `numerics.py` | logit/sigmoid, weighted statistics, Jacobi eigensolver, nearest correlation matrix, counter-based RNG |
| `inoculation.py` | `SimulationPopulation`, calibration, `FS_*` columns, factor statistics |
| `scenario.py` | `ScenarioContract`, approval bound to the contract hash, `apply_scenario`, `VariantSet` |
| `results.py` | Outcomes, ensembles, `compare_variants`, `FrozenPrediction`, `TruthRecord`, scoring |

## 3. Ported exactly (EXACT parity with the reference contract)

| Item | Value | Test |
| --- | --- | --- |
| Default spec seed | `20260816` | `test_reference_constants_are_the_recovered_values` |
| Per-world seed | `seed + 104729 · (world_index + 1)` | `test_world_seed_is_seed_plus_stride_times_index_plus_one` |
| World id | `world_001` for index 0 | `test_world_id_and_seed_refuse_a_negative_index` |
| Ablation seed | `seed + 88000 + mi·1000 + si·100 + int(temp·10)`, truncation included | `test_ablation_seed_truncates_temperature_like_the_reference` |
| Objectives | `blind_forecast`, `scenario_nowcast` | `test_reference_constants_are_the_recovered_values` |
| Every numeric bound | 12 factors max, mean 1.2–9.8, SD 0.6–3.2, confidence 0.05–0.95, 6 drivers max, effect ±1 with \|effect\| ≥ 0.02, \|ρ\| ≤ 0.65, 30 correlations max, text 120/600/1800 | `test_bounds_are_pinned_to_the_constants_version` |
| Epistemic markers | `HYPOTHESIZED_JOINT` on every factor and correlation; `EXPERIMENTAL_HYPOTHESIZED_JOINT` on every inoculated row | `test_frozen_model_carries_markers_and_bindings`, `test_fs_columns_are_exactly_the_reference_set` |
| Output columns | `FS_<factor>_10`, `FS_SIMULATION_PROFILE`, `FS_WORLD_ID`, `FS_WORLD_SEED`, `FS_WORLD_MODEL_SHA256`, `FS_EPISTEMIC_STATUS` | `test_fs_columns_are_exactly_the_reference_set` |
| Base population unchanged | only `FS_*` values are produced; rows and weights are frozen | `test_base_population_is_unchanged` |
| Contamination | `True` when target-overlap refs were used **or** objective is scenario | `test_scenario_run_is_contaminated_even_without_overlap` |
| Research binding | `research_sha256` on the world model; content-addressed `sha256` | `test_frozen_model_carries_markers_and_bindings`, `test_reload_refuses_a_hand_edited_model` |
| Eligibility | only a blind, uncontaminated prediction frozen before truth is benchmark-eligible; truth cannot change it | `test_scenario_prediction_is_never_eligible_and_truth_cannot_change_that` |
| Frozen truth | written once per frozen prediction | `test_truth_is_written_once`, `test_truth_before_freeze_is_refused` |
| No interpolation | every variant is simulated from its own population | `test_a_bigger_shift_moves_the_factor_further` |

## 4. Intentional differences

### 4.1 Invalid model output is rejected, not clipped

This is parity-matrix deviation **D4**. The reference sanitiser corrects invalid
model output silently. Production rejects **every** such field. No field is
clamped. `FIELD_POLICY` in `reference.py` holds one row per `(field, violation)`,
giving the legacy mechanism (clip, truncate, cap, drop, default, top up, stamp,
strip, normalise, deduplicate) and the production handling (`REJECT`). Two tests
keep the table honest:

- `test_production_rejects_what_the_reference_corrected` checks one mutated
  fixture per row. Each must be rejected and attributed to that row.
- `test_every_recorded_difference_is_exercised` fails when a row has no test, or
  a test has no row. This guards against producer/consumer drift (`ARCHITECTURE.md` A6).

Some decisions sit beside the table:

| Field | Reference | Production | Why |
| --- | --- | --- | --- |
| Minimum factors | prompt 6, schema 4, code tops `< 4` up to 6 | **6**, declared | The only count the model is asked for, and the reference's own top-up target. Decision **D9** in `PROGRESS.md` |
| Minimum drivers | prompt 1, code accepts 0 | **1** | A factor with no driver is pure noise dressed as a hypothesis |
| Missing mean / SD / confidence | defaults 5.0 / 2.0 / 0.3 | reject | Never stamp a guess (`CLAUDE.md §8`) |
| Epistemic status | stamped over whatever the model said | may be omitted, then stamped; a *different* value is rejected | A model claiming its factor is measured is misbehaving |
| Blind run with target-overlap refs | refs silently emptied | reject | The run was built on evidence it was not allowed to see |
| Categorical driver field | scored by `_stable_category_score` | reject (`non_numeric_field`) | That algorithm is not recovered; production does not invent one |
| Degenerate model | topped up from `DEFAULT_FACTORS` | reject; the fallback factors are **not ported** | A top-up simulates factors the model never proposed |
| `objective` / `research_sha256` | from the spec | from the run, never from the model; a model key naming them is `unknown_key` | A model cannot declare its own run blind |

### 4.2 Weighting has no fallback

The reference resolves weight through `_analysis_weight → vaha_strukturalni_2025
→ vaha_kalibrovana → 1.0`. That is high-risk behaviour R3 and fixture F11.
`PopulationRow.weight` is required. `SimulationPopulation.weight_basis` names the
scheme the caller resolved and is recorded unchanged. Nothing here defaults it.

### 4.3 Randomness is counter-based, not `numpy.random.default_rng`

The domain layer is stdlib + Pydantic only (`ARCHITECTURE.md §2`). Each draw is
computed as `NormalDist().inv_cdf(u)`, where `u` comes from
`SHA-256("sha256-counter-inv-normal-v1|world_seed|row_id|k")`
(`RNG_ALGORITHM`). There is no generator state, and that has two consequences:

- A row's draws depend on its id, not on its position. Reversing the population
  changes no row (`test_row_order_does_not_change_any_row`).
- Every variant of a row sees the same draws (common random numbers). A factor
  the scenario does not drive therefore moves by exactly 0
  (`test_a_factor_the_scenario_does_not_drive_does_not_move`).

The seed *derivation* matches the reference. The streams do not. Bit parity
would need PCG64 and the reference formula bodies together, so it is decision
**D10**.

## 5. Production-defined algorithms (versioned, parity pending)

The reference contract names these functions but its formula bodies are in the
withheld archive. So each one is a written, tested production algorithm with a
version string on every output. None of them claims to be the reference formula.

| Reference function | Production | Version |
| --- | --- | --- |
| `_driver_vector` | `Σ effect · z(field)`, z standardised on the calibration population; missing value → 0 and counted; SD ≤ 1e-9 → degenerate, reported | `fs-inoculation-v1` |
| `_calibrate_intercept` | bisection on `a` so the weighted mean of `1 + 9·sigmoid(a + b·s)` equals the target to 1e-12 | `fs-inoculation-v1` |
| `_corr_matrix` → `_nearest_psd_corr` | Higham (2002) alternating projections with Dykstra's correction, then a unit-row factor `F` with `F Fᵀ` the matrix; `adjustment` reports the Frobenius distance moved | `higham2002-dykstra-v1` |
| `inoculate_population` | calibrate on the baseline, then evaluate any variant in that fixed world (§6) | `fs-inoculation-v1` |
| `FS_SIMULATION_PROFILE` | the factor with the largest standardised latent for that row | `fs-inoculation-v1` |
| `ensemble_world_results` | equal-weight mean across worlds, keeping the min–max range | — |
| `score_distribution` | MAE and max absolute error in percentage points; total variation distance | — |

The regression golden (`test_simulation_golden.py`,
`fixtures/simulation/golden_outputs_v1.json`) pins this implementation's own
outputs at 1e-9. It is **not** parity: it catches an unintended change. It names
the versions it pins and refuses to pass after a version bump unless it is
regenerated too.

## 6. Properties worth knowing (measured)

**Calibrate on the baseline, evaluate the variant.** The first draft calibrated
each variant's intercept on its own population. Every factor mean was then
pulled back to its target, so every scenario reported a mean change of exactly
0. The mistake showed up when the variant test was written. The fix: each world
is fixed on the baseline (`WorldCalibration`), and the variant is evaluated in
that fixed world.

**The realised SD falls short of the target.** The logistic map calibrates the
mean exactly. The slope is set from `target_sd` to first order only, so
sigmoid compression makes the realised SD come out low. On the fixture,
18,766 rows, world 0, the realised-to-target ratio ranges from **0.82**
(`privacy_concern`, target 2.4) to **0.90** (`civic_engagement`, target 1.6).
`FactorStats.weighted_sd` reports the realised value. Forcing the SD exactly
needs a second calibration loop, which is left for when the reference formula
is readable.

**Cost.** Pure Python, one world, 18,766 rows × 6 factors: calibration 1.39 s,
evaluation 0.84 s, on the development container. A 10-world, 2-variant run is
therefore about 36 s of CPU. That belongs in a worker (Phase 3 layer 4), not in
a request.

**The correlation proposal is often infeasible.** The fixture's hypothesised
correlations are jointly non-PSD, although each pair is within bounds. The
projection moves them by a Frobenius distance of 0.381
(`test_world_correlation_is_a_valid_correlation_matrix`).

## 7. `REF-GAP-SIMULATION-WORLD-MODEL` (fixture F13) — owned here

**Owner:** simulation-engine + parity-quality. **Status:** OPEN, blocked on the
environment rather than on discovery.

F13 needs the reference's own `build_world_model()` to run once against a real
provider. The sanitised world model is frozen, then driven through the
reference's `inoculate_population(panel_v17_4_0, wm, world_index=0,
seed=20260816)`. The recipe is in the reference repository's `reference-gaps.md`
and is not repeated here. Running it needs **all** of the following:

| Precondition | State on 2026-09-22 |
| --- | --- |
| The reference source (`full_simulation.py`) | **Withheld** — the archive awaits its licence decision (`REF-WITHHELD-REFERENCE-ARCHIVE`) |
| An authorized model-provider credential for this project | **Absent** in the session that built the core |
| An egress route that satisfies [ADR 0008](adr/0008-eu-data-residency.md) | **Not established** — no approved inference route exists yet (Phase 4) |

No capture was attempted, and none will be without all three. Credentials
that happen to exist in an agent's own environment are not project-authorized
and must not be used for it.

When F13 lands:

1. `test_simulation_parity.py` runs its EXACT checks: seed, world identity,
   marker, declared tolerance and dataset. It reads the AIA-reference checkout
   through `AIA_REFERENCE_REPO`, like the other reference-repository suites.
2. The captured world model's JSON shape must be mapped to this contract.
   Production names its keys (`factors[].drivers[].field/effect`,
   `correlations[].a/b/rho`, `target_overlap_refs`); the reference's key names
   are not recorded. The mapping is an adapter. Validation is not loosened to
   fit it.
3. The NUMERICAL comparison of `FS_*` columns, the correlation matrix and the
   factor statistics becomes meaningful once the reference formula bodies are
   readable and **D10** is decided. It is deliberately not written before then,
   because it would fail by construction.

## 8. Not built

- World-model generation behind the `ModelGateway` (Phase 4), with the semantic
  parity criterion "bounds and markers hold". Its output goes through
  `validate_world_model` and nothing else.
- The scenario compiler's LLM step. This slice builds the contract, the
  approval binding and application.
- The respondent run per world (Phase 5). Its per-world distributions fit
  `WorldOutcome` and flow through `ensemble_worlds` unchanged.
- `fullsim_learning` (calibration, meta-error, residual learning),
  `simulation_batch` response-curve diagnostics, `simulation_context`.
- The append-only scenario truth log's persistence, and any table, migration,
  workflow step or route. `record_truth` takes the stored record as `existing`.
  The repository that supplies it must enforce write-once under concurrency,
  with a unique constraint, when it is built.
