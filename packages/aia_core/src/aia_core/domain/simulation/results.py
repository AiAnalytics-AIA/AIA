"""World outcomes, ensembles, variant comparisons, frozen predictions and truth.

The pre-registration discipline is ported exactly, because it is the part of the
reference that keeps a forecasting engine honest:

* **Truth is written once per frozen prediction** and never again
  (:class:`TruthAlreadyRecorded`).
* **Eligibility is inherited from the frozen prediction.** Truth cannot make a
  scenario run blind; :class:`TruthRecord` has no eligibility field to set.
* **Only a prediction frozen before truth, and not contaminated by target-overlap
  research, counts as a benchmark** (:attr:`FrozenPrediction.benchmark_eligible`).

Variant comparison follows the Phase 7 rule that variants are **independently
modelled, never interpolated**: every :class:`VariantResult` is computed from its
own population through the full chain, and :func:`compare_variants` only
subtracts two such results. Both arms use the same world seeds (common random
numbers), so a delta measures the scenario rather than sampling noise.

The outcome of a world here is the banded distribution of each ``FS_*`` factor on
the 1-10 scale. The respondent run that answers a questionnaire per world is the
respondent engine's (Phase 5); its per-world distributions have the same shape and
flow through :func:`ensemble_worlds` and the truth/scoring chain unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Final, Literal

from ..pipeline import fingerprint
from .inoculation import (
    InoculatedWorld,
    SimulationPopulation,
    apply_world,
    calibrate_world,
    fs_column,
)
from .reference import LINEAR_INTERPOLATION_ALLOWED, Objective
from .scenario import Variant, apply_scenario
from .world_model import PanelSchema, WorldModel

__all__ = [
    "SCALE_OPTIONS",
    "TRUTH_SUM_TOLERANCE_PP",
    "Delta",
    "Distribution",
    "DistributionScore",
    "EnsembleOutcome",
    "FrozenPrediction",
    "IncomparableResults",
    "PredictionScore",
    "TruthAlreadyRecorded",
    "TruthPrecedesFreeze",
    "TruthRecord",
    "VariantComparison",
    "VariantResult",
    "WorldOutcome",
    "compare_variants",
    "ensemble_worlds",
    "freeze_prediction",
    "record_truth",
    "run_variant",
    "score_distribution",
    "score_prediction",
    "world_outcome",
]

# question id -> option -> percentage of weighted population (sums to 100)
Distribution = Mapping[str, Mapping[str, float]]

SCALE_OPTIONS: Final = tuple(str(i) for i in range(1, 11))
# Human-entered truth is usually rounded; a total this far from 100 is accepted and
# normalised explicitly, and the factor is recorded. Anything further is refused.
TRUTH_SUM_TOLERANCE_PP: Final = 0.5
_SUM_TOLERANCE_PP: Final = 1e-6


class IncomparableResults(ValueError):
    """Two results that do not share what a comparison requires."""


class TruthAlreadyRecorded(ValueError):
    """Truth has been written for this frozen prediction; the benchmark is immutable."""


class TruthPrecedesFreeze(ValueError):
    """Truth recorded before the prediction was frozen cannot score it."""


def _band(value: float) -> str:
    return str(min(10, max(1, math.floor(value + 0.5))))


def _freeze_distribution(d: Distribution) -> dict[str, dict[str, float]]:
    return {q: dict(sorted(opts.items())) for q, opts in sorted(d.items())}


# --- One world ---------------------------------------------------------------------


@dataclass(frozen=True)
class WorldOutcome:
    world_id: str
    world_seed: int
    world_sha256: str
    distributions: Mapping[str, Mapping[str, float]]
    means: Mapping[str, float]


def world_outcome(world: InoculatedWorld) -> WorldOutcome:
    """Weighted share of each 1-10 scale point, and the weighted mean, per factor."""
    total = math.fsum(world.weights)
    distributions: dict[str, dict[str, float]] = {}
    means: dict[str, float] = {}
    for k, fid in enumerate(world.factor_ids):
        shares = dict.fromkeys(SCALE_OPTIONS, 0.0)
        acc: dict[str, list[float]] = {o: [] for o in SCALE_OPTIONS}
        for row, w in zip(world.values, world.weights, strict=True):
            acc[_band(row[k])].append(w)
        for option in SCALE_OPTIONS:
            shares[option] = 100.0 * math.fsum(acc[option]) / total
        distributions[fs_column(fid)] = shares
        means[fs_column(fid)] = next(
            s.weighted_mean for s in world.factor_stats if s.factor_id == fid
        )
    return WorldOutcome(world.world_id, world.world_seed, world.sha256, distributions, means)


# --- Across worlds -----------------------------------------------------------------


@dataclass(frozen=True)
class EnsembleOutcome:
    """Equal-weight mean across worlds, with the across-world range kept visible.

    The range is the honest uncertainty statement a multi-world run can make: it
    is how much the answer moved between independently seeded worlds.
    """

    world_ids: tuple[str, ...]
    distributions: Mapping[str, Mapping[str, float]]
    distribution_range: Mapping[str, Mapping[str, tuple[float, float]]]
    means: Mapping[str, float]
    mean_range: Mapping[str, tuple[float, float]]


def ensemble_worlds(outcomes: Sequence[WorldOutcome]) -> EnsembleOutcome:
    if not outcomes:
        raise ValueError("an ensemble needs at least one world")
    ids = [o.world_id for o in outcomes]
    if len(set(ids)) != len(ids):
        raise ValueError("an ensemble cannot count the same world twice")
    shape = {q: tuple(sorted(opts)) for q, opts in outcomes[0].distributions.items()}
    for o in outcomes[1:]:
        if {q: tuple(sorted(opts)) for q, opts in o.distributions.items()} != shape:
            raise IncomparableResults(f"{o.world_id} answers different questions or options")
    n = len(outcomes)
    dist: dict[str, dict[str, float]] = {}
    rng: dict[str, dict[str, tuple[float, float]]] = {}
    for q, options in shape.items():
        dist[q], rng[q] = {}, {}
        for opt in options:
            xs = [o.distributions[q][opt] for o in outcomes]
            dist[q][opt] = math.fsum(xs) / n
            rng[q][opt] = (min(xs), max(xs))
    means = {q: math.fsum(o.means[q] for o in outcomes) / n for q in outcomes[0].means}
    mean_range = {
        q: (min(o.means[q] for o in outcomes), max(o.means[q] for o in outcomes))
        for q in outcomes[0].means
    }
    return EnsembleOutcome(tuple(ids), dist, rng, means, mean_range)


# --- A variant -----------------------------------------------------------------------


@dataclass(frozen=True)
class VariantResult:
    """One variant simulated end to end across ``n_worlds`` worlds."""

    variant_id: str
    scenario_sha256: str | None
    world_model_sha256: str
    base_population_sha256: str
    simulated_population_sha256: str
    spec_seed: int
    worlds: tuple[WorldOutcome, ...]
    ensemble: EnsembleOutcome
    interpolated: Literal[False]
    sha256: str

    def content(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "scenario_sha256": self.scenario_sha256,
            "world_model_sha256": self.world_model_sha256,
            "base_population_sha256": self.base_population_sha256,
            "simulated_population_sha256": self.simulated_population_sha256,
            "spec_seed": self.spec_seed,
            "world_sha256": [w.world_sha256 for w in self.worlds],
            "distributions": _freeze_distribution(self.ensemble.distributions),
            "interpolated": self.interpolated,
        }


def run_variant(
    model: WorldModel,
    population: SimulationPopulation,
    schema: PanelSchema,
    variant: Variant,
    *,
    spec_seed: int,
    n_worlds: int,
) -> VariantResult:
    """Simulate one variant from scratch: apply its scenario, evaluate it in every world.

    ``population`` is the baseline. Every world is calibrated on it, whichever
    variant is being run, so baseline and scenario share one set of worlds.
    """
    if n_worlds < 1:
        raise ValueError(f"n_worlds must be >= 1; got {n_worlds}")
    if schema.fingerprint() != model.panel_schema_sha256:
        raise IncomparableResults("the world model was validated against a different schema")
    simulated = (
        population
        if variant.scenario is None
        else apply_scenario(population, variant.scenario, schema)
    )
    # Each world is fixed on the baseline and the variant is evaluated in it; see
    # inoculation.py for why re-calibrating on the variant would erase its effect.
    outcomes = tuple(
        world_outcome(
            apply_world(
                simulated,
                model,
                calibrate_world(population, model, world_index=i, spec_seed=spec_seed),
            )
        )
        for i in range(n_worlds)
    )
    result = VariantResult(
        variant_id=variant.variant_id,
        scenario_sha256=variant.scenario_sha256,
        world_model_sha256=model.sha256,
        base_population_sha256=population.fingerprint(),
        simulated_population_sha256=simulated.fingerprint(),
        spec_seed=spec_seed,
        worlds=outcomes,
        ensemble=ensemble_worlds(outcomes),
        interpolated=LINEAR_INTERPOLATION_ALLOWED,
        sha256="",
    )
    return replace(result, sha256=fingerprint(result.content()))


# --- Comparison ----------------------------------------------------------------------


@dataclass(frozen=True)
class Delta:
    """``alternative - baseline``, with the range of that difference across worlds.

    Units follow the quantity: percentage points for a distribution option, 1-10
    scale points for a factor mean.
    """

    delta: float
    world_min: float
    world_max: float

    @property
    def sign_consistent(self) -> bool:
        """True when every world agrees on the direction of the change."""
        return self.world_min > 0.0 or self.world_max < 0.0


@dataclass(frozen=True)
class VariantComparison:
    baseline_id: str
    alternative_id: str
    baseline_sha256: str
    alternative_sha256: str
    scenario_sha256: str
    distribution_deltas: Mapping[str, Mapping[str, Delta]]
    mean_deltas: Mapping[str, Delta]
    common_random_numbers: Literal[True]
    interpolated: Literal[False]


def _delta(base: float, alt: float, per_world: Sequence[float]) -> Delta:
    return Delta(alt - base, min(per_world), max(per_world))


def compare_variants(baseline: VariantResult, alternative: VariantResult) -> VariantComparison:
    """Deltas between two independently simulated variants of one world model."""
    if baseline.scenario_sha256 is not None:
        raise IncomparableResults(f"{baseline.variant_id!r} is not a baseline")
    if alternative.scenario_sha256 is None:
        raise IncomparableResults(f"{alternative.variant_id!r} applies no scenario")
    for name in ("world_model_sha256", "base_population_sha256", "spec_seed"):
        if getattr(baseline, name) != getattr(alternative, name):
            raise IncomparableResults(f"variants differ in {name}; a delta would be meaningless")
    if [w.world_id for w in baseline.worlds] != [w.world_id for w in alternative.worlds]:
        raise IncomparableResults("variants were simulated in different worlds")
    for r in (baseline, alternative):
        if fingerprint(r.content()) != r.sha256:
            raise IncomparableResults(f"{r.variant_id!r} does not match its sha256")

    b, a = baseline.ensemble, alternative.ensemble
    pairs = list(zip(baseline.worlds, alternative.worlds, strict=True))
    dist: dict[str, dict[str, Delta]] = {}
    for q, options in b.distributions.items():
        dist[q] = {
            opt: _delta(
                options[opt],
                a.distributions[q][opt],
                [wa.distributions[q][opt] - wb.distributions[q][opt] for wb, wa in pairs],
            )
            for opt in options
        }
    means = {
        q: _delta(b.means[q], a.means[q], [wa.means[q] - wb.means[q] for wb, wa in pairs])
        for q in b.means
    }
    return VariantComparison(
        baseline_id=baseline.variant_id,
        alternative_id=alternative.variant_id,
        baseline_sha256=baseline.sha256,
        alternative_sha256=alternative.sha256,
        scenario_sha256=alternative.scenario_sha256,
        distribution_deltas=dist,
        mean_deltas=means,
        common_random_numbers=True,
        interpolated=LINEAR_INTERPOLATION_ALLOWED,
    )


# --- Freezing, truth and scoring --------------------------------------------------------


def _aware(at: datetime, name: str) -> datetime:
    if at.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return at


@dataclass(frozen=True)
class FrozenPrediction:
    """An immutable prediction, eligibility fixed at the moment it was frozen."""

    variant_result_sha256: str
    world_model_sha256: str
    objective: Objective
    contaminated_for_predictive_benchmark: bool
    frozen_at: datetime
    distributions: Mapping[str, Mapping[str, float]]
    sha256: str

    @property
    def benchmark_eligible(self) -> bool:
        return (
            self.objective is Objective.BLIND_FORECAST
            and not self.contaminated_for_predictive_benchmark
        )

    def content(self) -> dict[str, Any]:
        return {
            "variant_result_sha256": self.variant_result_sha256,
            "world_model_sha256": self.world_model_sha256,
            "objective": self.objective.value,
            "contaminated_for_predictive_benchmark": self.contaminated_for_predictive_benchmark,
            "frozen_at": self.frozen_at.isoformat(),
            "distributions": _freeze_distribution(self.distributions),
        }


def freeze_prediction(
    model: WorldModel, result: VariantResult, *, frozen_at: datetime
) -> FrozenPrediction:
    if result.world_model_sha256 != model.sha256:
        raise IncomparableResults("the result was not produced from this world model")
    frozen = FrozenPrediction(
        variant_result_sha256=result.sha256,
        world_model_sha256=model.sha256,
        objective=model.objective,
        contaminated_for_predictive_benchmark=model.contaminated_for_predictive_benchmark,
        frozen_at=_aware(frozen_at, "frozen_at"),
        distributions=_freeze_distribution(result.ensemble.distributions),
        sha256="",
    )
    return replace(frozen, sha256=fingerprint(frozen.content()))


@dataclass(frozen=True)
class TruthRecord:
    """Observed truth for one frozen prediction. Carries no eligibility of its own."""

    frozen_sha256: str
    recorded_by: str
    recorded_at: datetime
    distributions: Mapping[str, Mapping[str, float]]
    # question -> 100 / entered total; 1.0 when the entry already summed to 100.
    normalisation: Mapping[str, float]


def record_truth(
    frozen: FrozenPrediction,
    distributions: Distribution,
    *,
    recorded_by: str,
    recorded_at: datetime,
    existing: TruthRecord | None,
) -> TruthRecord:
    """Write truth once. ``existing`` is whatever the store already holds for ``frozen``."""
    if existing is not None:
        raise TruthAlreadyRecorded(
            f"truth for {frozen.sha256[:12]} was recorded at {existing.recorded_at.isoformat()}"
        )
    if not recorded_by.strip():
        raise ValueError("truth is recorded by someone")
    if _aware(recorded_at, "recorded_at") <= frozen.frozen_at:
        raise TruthPrecedesFreeze("truth must be recorded after the prediction was frozen")
    if not distributions:
        raise ValueError("truth covers at least one question")
    clean: dict[str, dict[str, float]] = {}
    factors: dict[str, float] = {}
    for q, options in distributions.items():
        if q not in frozen.distributions:
            raise IncomparableResults(f"the prediction has no question {q!r}")
        if set(options) != set(frozen.distributions[q]):
            raise IncomparableResults(f"{q!r}: truth options differ from the prediction's")
        for opt, pct in options.items():
            if isinstance(pct, bool) or not math.isfinite(pct) or pct < 0.0:
                raise ValueError(f"{q}.{opt}: a share is a finite non-negative number")
        total = math.fsum(options.values())
        if abs(total - 100.0) > TRUTH_SUM_TOLERANCE_PP:
            raise ValueError(f"{q!r}: shares sum to {total}, not 100")
        factors[q] = 100.0 / total
        clean[q] = {opt: pct * factors[q] for opt, pct in sorted(options.items())}
    return TruthRecord(frozen.sha256, recorded_by, recorded_at, clean, factors)


@dataclass(frozen=True)
class DistributionScore:
    mae_pp: float
    max_abs_error_pp: float
    total_variation: float


def score_distribution(
    predicted: Mapping[str, float], truth: Mapping[str, float]
) -> DistributionScore:
    """Error of one predicted distribution against truth, both in percent."""
    if set(predicted) != set(truth) or not predicted:
        raise IncomparableResults("prediction and truth must have the same, non-empty options")
    for name, d in (("prediction", predicted), ("truth", truth)):
        total = math.fsum(d.values())
        if abs(total - 100.0) > _SUM_TOLERANCE_PP:
            raise ValueError(f"{name} sums to {total}, not 100")
    errors = [abs(predicted[o] - truth[o]) for o in sorted(predicted)]
    return DistributionScore(
        mae_pp=math.fsum(errors) / len(errors),
        max_abs_error_pp=max(errors),
        total_variation=math.fsum(errors) / 200.0,
    )


@dataclass(frozen=True)
class PredictionScore:
    frozen_sha256: str
    benchmark_eligible: bool
    per_question: Mapping[str, DistributionScore]


def score_prediction(frozen: FrozenPrediction, truth: TruthRecord) -> PredictionScore:
    """Score every question truth covers. Eligibility comes from ``frozen`` only."""
    if truth.frozen_sha256 != frozen.sha256:
        raise IncomparableResults("the truth record belongs to a different prediction")
    return PredictionScore(
        frozen_sha256=frozen.sha256,
        benchmark_eligible=frozen.benchmark_eligible,
        per_question={
            q: score_distribution(frozen.distributions[q], truth.distributions[q])
            for q in sorted(truth.distributions)
        },
    )
