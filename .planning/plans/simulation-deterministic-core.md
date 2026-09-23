# Simulation deterministic core

**Status:** all chunks landed, in review · **Owner:** simulation-engine · **Started:** 2026-09-22

## Problem

Phase 7 (Simulation) had no production code. The reference Full Simulation
mixes two different kinds of thing in one pipeline: an LLM-generated
*world model* (semantic, non-reproducible) and a deterministic numerical chain
driven from it (seeded, reproducible). The reference also **clips** invalid model
output rather than refusing it, so a misbehaving model is silently normalised
and a degenerate one is silently topped up with fallback factors.

Authority: `AiAnalytics-AIA/AIA-reference` @ `678e298ad9ca0263da53cc8920d153fdfb956c93`,
`simulation-reference-contract.md`, `parity-plan.md`, `high-risk-behaviors.md`
(R3), `reference-gaps.md` (`REF-GAP-SIMULATION-WORLD-MODEL`).

## Approach

A pure domain package, `aia_core.domain.simulation`, that takes a **frozen,
validated `WorldModel`** as its only model-derived input. Nothing in it calls a
provider. A live model is never needed to test it; the tests drive it from a
committed, hand-authored structured fixture.

```
raw model output (untrusted mapping)
  → validate_world_model()     REJECTS every out-of-bound field, lists all violations
  → WorldModel                 frozen, content-addressed (sha256), epistemic markers
  → calibrate_world()          per world, on the baseline: correlation projection,
                               driver scales, intercepts
  → apply_world()              any variant in that fixed world; FS_* columns only
  → world_outcome() → ensemble_worlds()
  → compare_variants()         deltas between independently modelled variants
  → freeze_prediction() → record_truth() (write once) → score_distribution()
```

Reference constants (seed, world-seed stride, bounds, markers) live in one
versioned module, `reference.py`. Every field the reference sanitiser corrects is
listed there with the legacy mechanism and the production handling, so the
difference is recorded as data and asserted by a test, not described in prose.

### Why not the obvious alternatives

- **numpy.** The reference uses `numpy.random.default_rng`. The domain layer is
  stdlib + Pydantic only (`ARCHITECTURE.md §2`), and adopting numpy for PCG64
  bit-parity would only buy parity if the *formula bodies* were also known — they
  are not (the archive is withheld). So the RNG is a counter-based SHA-256
  generator, which is also independent of row order and population subsetting.
- **Clip like the reference.** The contract's production target is *reject*.
  A clip is a silent correction of untrusted input.
- **Fall back to `DEFAULT_FACTORS` when a model is degenerate.** Rejected: that is
  the silent top-up the contract calls out. The fallback values are not ported.

## Trade-off accepted

Numerical parity with the reference `FS_*` columns is **not** claimed: the
seed derivation, bounds, markers and eligibility rules are ported exactly, but
the formula bodies (`_driver_vector`, `_calibrate_intercept`, `_nearest_psd_corr`,
`inoculate_population`, scoring) are production-defined and versioned until the
reference source is readable and F13 exists.

## Chunks

- [x] 1. Reference constants, field policy, `WorldModel` contract and
      rejecting validator — `reference.py`, `world_model.py`,
      `tests/test_simulation_world_model.py`
- [x] 2. Numerics: clip/logit/sigmoid, weighted stats, Jacobi eigen, nearest
      correlation matrix, counter-based normal draws — `numerics.py`,
      `tests/test_simulation_numerics.py`
- [x] 3. Population inoculation: world seeds, driver vector, intercept
      calibration, `FS_*` columns, factor stats — `inoculation.py`,
      `tests/test_simulation_inoculation.py`
- [x] 4. Scenario contract, approval, variants — `scenario.py`,
      `tests/test_simulation_scenarios.py`
- [x] 5. Outcomes, ensembling, comparisons/deltas, frozen predictions,
      write-once truth, eligibility, scoring — `results.py`,
      `tests/test_simulation_results.py`
- [x] 6. Regression golden pinned on the frozen fixture; F13 parity scaffold that
      skips without the fixture — `tests/test_simulation_golden.py`,
      `tests/test_simulation_parity.py`
- [x] 7. Documents: engine doc, domain map, parity matrix, CLAUDE.md map,
      reference-source, module inventory, PROGRESS (REF-GAP ownership,
      decisions D6 and D7)

## What changed during the work

- **Calibration moved to the baseline.** Chunk 3 first calibrated every
  population on itself. Chunk 5's variant test then showed that every scenario
  reported a factor-mean change of exactly 0, because re-calibration pulls each
  mean back to its target. The fix, in chunk 3's module: `calibrate_world` on
  the baseline, then `apply_world` for any variant. Covered by
  `test_a_shifted_population_is_evaluated_in_the_baseline_world` and
  `test_trust_scenario_moves_trust_up_and_privacy_down`.
- **`Delta`, not `OptionDelta.delta_pp`.** Mean deltas are in 1–10 scale
  points, not percentage points, so the field name was wrong for half its uses.
- **Realised SD is below target** by 10–18% on the fixture (ratio 0.82–0.90).
  It is recorded in the engine document §6, reported in `FactorStats`, and not
  forced.

## Left open, deliberately

- `REF-GAP-SIMULATION-WORLD-MODEL` (F13) needs the withheld reference source, a
  project-authorized credential and an ADR 0008 egress route. None was available
  (`PROGRESS.md`, reference ownership).
- Decisions D6 (minimum factors) and D7 (exact numerics vs production v1).

## Review outcome

Filled in when the plan is archived.
