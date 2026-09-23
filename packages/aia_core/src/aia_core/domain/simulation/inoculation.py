"""Population inoculation: add hypothesised factor traits to a population, per world.

The reference rule, preserved exactly: *the base population rows and weights
remain unchanged; only ``FS_*`` fields are added.* Here that is structural rather
than a promise -- :class:`SimulationPopulation` is frozen, and
:func:`inoculate_population` returns a separate :class:`InoculatedWorld` keyed by
row id. There is no operation that writes to the population.

Algorithm ``fs-inoculation-v1`` (production-defined; see the engine document for
why this is not claimed to be the reference's formula). A world is first
**calibrated** on the baseline population (:func:`calibrate_world`), and any
population -- the baseline itself, or a scenario variant of it -- is then
**evaluated** in that fixed world (:func:`apply_world`). For each factor ``f``:

1. **Driver vector.** Each driver field is standardised with the calibration
   population's weighted mean and SD; ``driver_f = Σ effect_d · z_d``. A missing
   value contributes 0 -- the calibration mean -- and is counted in
   ``FactorStats.missing_driver_values``. A field whose weighted SD is at or below
   1e-9 carries no information and contributes 0 everywhere; it is listed in
   ``FactorStats.degenerate_drivers``.
2. **Correlated residual.** ``e_f = Σ_k F[f][k] · n_k``, where ``F`` factors the
   nearest correlation matrix of the world model's hypothesised correlations and
   ``n_k`` is a counter-based standard normal keyed on ``(world_seed, row_id, k)``
   -- so every variant of a row sees the same draws (common random numbers).
3. **Latent.** ``L_f = driver_f + r_f · e_f`` with
   ``r_f = sqrt(max(0, 1 - var_w(driver_f)))`` on the calibration population, then
   standardised with the calibration latent mean and SD to ``s_f``.
4. **Scale.** ``value = 1 + 9 · sigmoid(a_f + b_f · s_f)``, which cannot leave
   (1, 10). ``b_f = target_sd / (9 p (1 - p))`` with ``p = (target_mean - 1) / 9``
   is the slope that gives ``target_sd`` to first order; ``a_f`` is calibrated by
   bisection so the calibration population's weighted mean equals
   ``target_mean_10`` to 1e-12. The baseline mean is therefore exact; the SD is
   the design value and the realised SD is reported in ``FactorStats``, never
   forced. A scenario variant keeps ``a_f`` and ``b_f``, so its mean moves.
5. **Profile.** ``FS_SIMULATION_PROFILE`` is the factor with the largest ``s_f``
   for that row (first in world-model order on a tie).

Weighting is explicit. The reference falls back through
``_analysis_weight → vaha_strukturalni_2025 → vaha_kalibrovana → 1.0``; production
has no default weight (high-risk behaviour R3), so every row carries the weight
the caller resolved and a missing one is a construction error.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..pipeline import fingerprint
from .numerics import (
    RNG_ALGORITHM,
    SD_DEGENERATE_THRESHOLD,
    CorrelationFactor,
    correlation_factor,
    sigmoid,
    standard_normal,
    weighted_correlation,
    weighted_mean,
    weighted_sd,
)
from .reference import (
    FS_EPISTEMIC_STATUS,
    SIMULATION_CONSTANTS_VERSION,
    world_id,
    world_seed,
)
from .world_model import Driver, WorldModel

__all__ = [
    "INOCULATION_ALGORITHM",
    "DriverFieldMissing",
    "FactorCalibration",
    "FactorStats",
    "FieldScale",
    "InoculatedWorld",
    "PopulationRow",
    "SimulationPopulation",
    "WorldCalibration",
    "apply_world",
    "calibrate_intercept",
    "calibrate_world",
    "driver_vector",
    "fs_column",
    "inoculate_population",
    "world_correlation",
]

INOCULATION_ALGORITHM: Final = "fs-inoculation-v1"
_SCALE_LOW: Final = 1.0
_SCALE_SPAN: Final = 9.0
_CALIBRATION_TOL: Final = 1e-12
_CALIBRATION_MAX_ITER: Final = 400


def fs_column(factor_id: str) -> str:
    """``FS_<factor_id>_10`` -- the reference column name for a factor's value."""
    return f"FS_{factor_id}_10"


class DriverFieldMissing(ValueError):
    """A world model names a driver field that the population does not carry."""


class PopulationRow(BaseModel):
    """One population member: a stable id, an explicit weight and numeric fields.

    ``None`` marks a missing value and is preserved; see the module docstring for
    how inoculation treats it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    row_id: str = Field(min_length=1)
    weight: float = Field(ge=0.0)
    values: Mapping[str, float | None]

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        if isinstance(v, Mapping):
            for key, x in v.items():
                if isinstance(x, bool):
                    raise ValueError(f"field {key!r} is a boolean; encode it as a number")
        return v

    @field_validator("values")
    @classmethod
    def _finite(cls, v: Mapping[str, float | None]) -> Mapping[str, float | None]:
        for key, x in v.items():
            if x is not None and not math.isfinite(x):
                raise ValueError(f"field {key!r} must be finite or None; got {x!r}")
        return dict(v)


class SimulationPopulation(BaseModel):
    """The population a world is inoculated into. Immutable.

    ``weight_basis`` names the weighting scheme the caller resolved (for example a
    declared weight role). It is recorded, not interpreted: choosing it is the
    population context's job, and it must never be defaulted here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str = Field(min_length=1)
    weight_basis: str = Field(min_length=1)
    rows: tuple[PopulationRow, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        ids = [r.row_id for r in self.rows]
        if len(set(ids)) != len(ids):
            raise ValueError("row ids must be unique")
        if not math.fsum(r.weight for r in self.rows) > 0.0:
            raise ValueError("population weights must sum to a positive total")
        return self

    def fingerprint(self) -> str:
        return fingerprint(self.model_dump(mode="json"))

    def fields(self) -> frozenset[str]:
        return frozenset(k for r in self.rows for k in r.values)

    @property
    def weights(self) -> tuple[float, ...]:
        return tuple(r.weight for r in self.rows)


# --- Calibration: fixed once per world, on the baseline population ------------------------
#
# A world is *calibrated* on the population it describes -- driver scales, the
# latent standardisation and the intercept that makes the factor mean equal the
# world model's target -- and those numbers are then frozen. A scenario variant is
# evaluated under the baseline's calibration, which is what lets a shifted driver
# move a factor at all: re-calibrating on the shifted population would pull every
# factor mean straight back to its target and report a change of exactly zero.


@dataclass(frozen=True)
class FieldScale:
    """Weighted mean and SD of one driver field over the calibration population.

    ``degenerate`` when the field has no present values or its SD is at or below
    1e-9; such a field contributes 0 everywhere, and says so.
    """

    field: str
    mean: float
    sd: float
    degenerate: bool


def _field_scale(population: SimulationPopulation, name: str) -> FieldScale:
    present = [(x, r.weight) for r in population.rows if (x := r.values.get(name)) is not None]
    xs = [x for x, _ in present]
    ws = [w for _, w in present]
    if not xs or not math.fsum(ws) > 0.0:
        return FieldScale(name, 0.0, 0.0, True)
    mean = weighted_mean(xs, ws)
    sd = weighted_sd(xs, ws)
    return FieldScale(name, mean, sd, sd <= SD_DEGENERATE_THRESHOLD)


def _drive(
    population: SimulationPopulation, drivers: Sequence[Driver], scales: Sequence[FieldScale]
) -> tuple[list[float], int]:
    total = [0.0] * len(population.rows)
    missing = 0
    for d, scale in zip(drivers, scales, strict=True):
        for i, row in enumerate(population.rows):
            x = row.values.get(d.field)
            if x is None:
                missing += 1
            elif not scale.degenerate:
                total[i] += d.effect * (x - scale.mean) / scale.sd
    return total, missing


def driver_vector(
    population: SimulationPopulation, drivers: Sequence[Driver]
) -> tuple[tuple[float, ...], int, tuple[str, ...]]:
    """``Σ effect · z(field)`` per row, standardised on ``population`` itself.

    Returns the vector, the number of missing driver values (each contributes 0,
    the population mean) and the fields that were degenerate.
    """
    scales = [_field_scale(population, d.field) for d in drivers]
    total, missing = _drive(population, drivers, scales)
    return tuple(total), missing, tuple(s.field for s in scales if s.degenerate)


def _scaled_mean(
    intercept: float, slope: float, latent: Sequence[float], weights: Sequence[float]
) -> float:
    return weighted_mean(
        [_SCALE_LOW + _SCALE_SPAN * sigmoid(intercept + slope * s) for s in latent], weights
    )


def calibrate_intercept(
    target_mean_10: float, slope: float, latent: Sequence[float], weights: Sequence[float]
) -> float:
    """The intercept ``a`` for which the weighted mean of ``1 + 9 sigmoid(a + b·s)`` is the target.

    The mean is strictly increasing in ``a``, so bisection on a bracket that is
    widened until it contains the root always finds it. Fails closed if it cannot.
    """
    if not _SCALE_LOW < target_mean_10 < _SCALE_LOW + _SCALE_SPAN:
        raise ValueError(f"target mean must lie strictly inside (1, 10); got {target_mean_10}")
    lo, hi = -1.0, 1.0
    for _ in range(64):
        if _scaled_mean(lo, slope, latent, weights) <= target_mean_10:
            break
        lo *= 2.0
    else:
        raise ArithmeticError("could not bracket the intercept from below")
    for _ in range(64):
        if _scaled_mean(hi, slope, latent, weights) >= target_mean_10:
            break
        hi *= 2.0
    else:
        raise ArithmeticError("could not bracket the intercept from above")
    for _ in range(_CALIBRATION_MAX_ITER):
        mid = (lo + hi) / 2.0
        value = _scaled_mean(mid, slope, latent, weights)
        if abs(value - target_mean_10) <= _CALIBRATION_TOL or mid in (lo, hi):
            return mid
        if value < target_mean_10:
            lo = mid
        else:
            hi = mid
    raise ArithmeticError(f"intercept calibration did not converge for {target_mean_10}")


def world_correlation(model: WorldModel) -> CorrelationFactor:
    """The world model's hypothesised correlations as a valid, factored matrix."""
    ids = model.factor_ids
    proposed = tuple(tuple(model.rho(a, b) for b in ids) for a in ids)
    return correlation_factor(proposed)


def _residuals(
    population: SimulationPopulation, seed: int, corr: CorrelationFactor
) -> list[list[float]]:
    """Correlated residuals per row, keyed on row id: identical in every variant."""
    n = len(corr.factor)
    out: list[list[float]] = []
    for row in population.rows:
        draws = [standard_normal(seed, row.row_id, k) for k in range(n)]
        out.append([math.fsum(corr.factor[f][k] * draws[k] for k in range(n)) for f in range(n)])
    return out


@dataclass(frozen=True)
class FactorCalibration:
    factor_id: str
    driver_scales: tuple[FieldScale, ...]
    residual_scale: float
    latent_mean: float
    latent_sd: float
    slope: float
    intercept: float


@dataclass(frozen=True)
class WorldCalibration:
    """Everything that fixes one world, computed once on the calibration population."""

    world_index: int
    world_id: str
    world_seed: int
    spec_seed: int
    world_model_sha256: str
    population_sha256: str
    dataset_version: str
    correlation: CorrelationFactor
    factors: tuple[FactorCalibration, ...]

    @property
    def sha256(self) -> str:
        return fingerprint(
            {
                "world_index": self.world_index,
                "world_seed": self.world_seed,
                "world_model_sha256": self.world_model_sha256,
                "population_sha256": self.population_sha256,
                "correlation": self.correlation.matrix,
                "factors": [asdict(f) for f in self.factors],
            }
        )


def _check_drivers_present(model: WorldModel, population: SimulationPopulation) -> None:
    if population.dataset_version != model.dataset_version:
        raise DriverFieldMissing(
            f"world model was validated against {model.dataset_version!r}, "
            f"population is {population.dataset_version!r}"
        )
    absent = sorted(model.driver_fields() - population.fields())
    if absent:
        raise DriverFieldMissing(f"population carries no driver field(s): {absent}")


def calibrate_world(
    population: SimulationPopulation,
    model: WorldModel,
    *,
    world_index: int,
    spec_seed: int,
) -> WorldCalibration:
    """Fix one world on ``population`` (the baseline): scales, slopes, intercepts."""
    _check_drivers_present(model, population)
    seed = world_seed(spec_seed, world_index)
    corr = world_correlation(model)
    residuals = _residuals(population, seed, corr)
    weights = population.weights
    factors: list[FactorCalibration] = []
    for k, factor in enumerate(model.factors):
        scales = tuple(_field_scale(population, d.field) for d in factor.drivers)
        drive, _ = _drive(population, factor.drivers, scales)
        r = math.sqrt(max(0.0, 1.0 - weighted_sd(drive, weights) ** 2))
        raw = [drive[i] + r * residuals[i][k] for i in range(len(drive))]
        mean = weighted_mean(raw, weights)
        sd = weighted_sd(raw, weights)
        if sd <= SD_DEGENERATE_THRESHOLD:
            raise ArithmeticError(f"factor {factor.id!r} has no variance in this world")
        latent = [(x - mean) / sd for x in raw]
        p = (factor.target_mean_10 - _SCALE_LOW) / _SCALE_SPAN
        slope = factor.target_sd_10 / (_SCALE_SPAN * p * (1.0 - p))
        intercept = calibrate_intercept(factor.target_mean_10, slope, latent, weights)
        factors.append(FactorCalibration(factor.id, scales, r, mean, sd, slope, intercept))
    return WorldCalibration(
        world_index=world_index,
        world_id=world_id(world_index),
        world_seed=seed,
        spec_seed=spec_seed,
        world_model_sha256=model.sha256,
        population_sha256=population.fingerprint(),
        dataset_version=population.dataset_version,
        correlation=corr,
        factors=tuple(factors),
    )


# --- Output ------------------------------------------------------------------------


@dataclass(frozen=True)
class FactorStats:
    """Realised statistics of one factor in the evaluated population."""

    factor_id: str
    target_mean_10: float
    target_sd_10: float
    intercept: float
    slope: float
    residual_scale: float
    weighted_mean: float
    weighted_sd: float
    minimum: float
    maximum: float
    missing_driver_values: int
    degenerate_drivers: tuple[str, ...]


@dataclass(frozen=True)
class InoculatedWorld:
    """One world's ``FS_*`` values for every row. Immutable, content-addressed.

    ``values[i][k]`` is row ``row_ids[i]``'s value for ``factor_ids[k]``.
    ``population_sha256`` is the population evaluated; ``calibration_sha256`` and
    ``calibration_population_sha256`` identify the baseline the world was fixed on.
    They are equal for a baseline and differ for a scenario variant.
    """

    world_index: int
    world_id: str
    world_seed: int
    spec_seed: int
    world_model_sha256: str
    population_sha256: str
    calibration_population_sha256: str
    calibration_sha256: str
    dataset_version: str
    weight_basis: str
    constants_version: str
    algorithm: str
    rng_algorithm: str
    epistemic_status: str
    factor_ids: tuple[str, ...]
    row_ids: tuple[str, ...]
    weights: tuple[float, ...]
    values: tuple[tuple[float, ...], ...]
    profiles: tuple[str, ...]
    factor_stats: tuple[FactorStats, ...]
    correlation: CorrelationFactor
    realised_correlation: tuple[tuple[float | None, ...], ...]
    sha256: str

    def column(self, factor_id: str) -> tuple[float, ...]:
        k = self.factor_ids.index(factor_id)
        return tuple(row[k] for row in self.values)

    def fs_columns(self) -> dict[str, tuple[Any, ...]]:
        """The reference column set, row-aligned with :attr:`row_ids`."""
        n = len(self.row_ids)
        columns: dict[str, tuple[Any, ...]] = {
            fs_column(fid): self.column(fid) for fid in self.factor_ids
        }
        columns["FS_SIMULATION_PROFILE"] = self.profiles
        columns["FS_WORLD_ID"] = (self.world_id,) * n
        columns["FS_WORLD_SEED"] = (self.world_seed,) * n
        columns["FS_WORLD_MODEL_SHA256"] = (self.world_model_sha256,) * n
        columns["FS_EPISTEMIC_STATUS"] = (self.epistemic_status,) * n
        return columns

    def content(self) -> dict[str, Any]:
        return {
            "world_index": self.world_index,
            "world_id": self.world_id,
            "world_seed": self.world_seed,
            "spec_seed": self.spec_seed,
            "world_model_sha256": self.world_model_sha256,
            "population_sha256": self.population_sha256,
            "calibration_population_sha256": self.calibration_population_sha256,
            "calibration_sha256": self.calibration_sha256,
            "dataset_version": self.dataset_version,
            "weight_basis": self.weight_basis,
            "constants_version": self.constants_version,
            "algorithm": self.algorithm,
            "rng_algorithm": self.rng_algorithm,
            "epistemic_status": self.epistemic_status,
            "factor_ids": self.factor_ids,
            "row_ids": self.row_ids,
            "values": self.values,
            "profiles": self.profiles,
        }

    def verify(self) -> None:
        """Raise if the world's content no longer matches its address."""
        if fingerprint(self.content()) != self.sha256:
            raise ValueError(f"{self.world_id}: content does not match sha256")


def apply_world(
    population: SimulationPopulation, model: WorldModel, calibration: WorldCalibration
) -> InoculatedWorld:
    """Evaluate ``population`` in a world fixed by ``calibration``. Deterministic.

    Refuses, rather than skips, a driver field the population does not carry --
    the same rule :func:`validate_world_model` applies against the schema, applied
    again against the data (``ARCHITECTURE.md`` A8).
    """
    if calibration.world_model_sha256 != model.sha256:
        raise ValueError("the calibration belongs to a different world model")
    if calibration.dataset_version != population.dataset_version:
        raise DriverFieldMissing(
            f"calibrated on {calibration.dataset_version!r}, "
            f"population is {population.dataset_version!r}"
        )
    _check_drivers_present(model, population)
    corr = calibration.correlation
    residuals = _residuals(population, calibration.world_seed, corr)
    weights = population.weights
    n_rows, n_factors = len(population.rows), len(model.factors)

    columns: list[list[float]] = []
    latents: list[list[float]] = []
    stats: list[FactorStats] = []
    for k, (factor, cal) in enumerate(zip(model.factors, calibration.factors, strict=True)):
        drive, missing = _drive(population, factor.drivers, cal.driver_scales)
        latent = [
            (drive[i] + cal.residual_scale * residuals[i][k] - cal.latent_mean) / cal.latent_sd
            for i in range(n_rows)
        ]
        col = [_SCALE_LOW + _SCALE_SPAN * sigmoid(cal.intercept + cal.slope * s) for s in latent]
        columns.append(col)
        latents.append(latent)
        stats.append(
            FactorStats(
                factor_id=factor.id,
                target_mean_10=factor.target_mean_10,
                target_sd_10=factor.target_sd_10,
                intercept=cal.intercept,
                slope=cal.slope,
                residual_scale=cal.residual_scale,
                weighted_mean=weighted_mean(col, weights),
                weighted_sd=weighted_sd(col, weights),
                minimum=min(col),
                maximum=max(col),
                missing_driver_values=missing,
                degenerate_drivers=tuple(s.field for s in cal.driver_scales if s.degenerate),
            )
        )

    ids = model.factor_ids
    world = InoculatedWorld(
        world_index=calibration.world_index,
        world_id=calibration.world_id,
        world_seed=calibration.world_seed,
        spec_seed=calibration.spec_seed,
        world_model_sha256=model.sha256,
        population_sha256=population.fingerprint(),
        calibration_population_sha256=calibration.population_sha256,
        calibration_sha256=calibration.sha256,
        dataset_version=population.dataset_version,
        weight_basis=population.weight_basis,
        constants_version=SIMULATION_CONSTANTS_VERSION,
        algorithm=INOCULATION_ALGORITHM,
        rng_algorithm=RNG_ALGORITHM,
        epistemic_status=FS_EPISTEMIC_STATUS,
        factor_ids=ids,
        row_ids=tuple(r.row_id for r in population.rows),
        weights=weights,
        values=tuple(tuple(columns[k][i] for k in range(n_factors)) for i in range(n_rows)),
        profiles=tuple(ids[_dominant(latents, i)] for i in range(n_rows)),
        factor_stats=tuple(stats),
        correlation=corr,
        realised_correlation=tuple(
            tuple(
                1.0 if a == b else weighted_correlation(columns[a], columns[b], weights)
                for b in range(n_factors)
            )
            for a in range(n_factors)
        ),
        sha256="",
    )
    return replace(world, sha256=fingerprint(world.content()))


def inoculate_population(
    population: SimulationPopulation,
    model: WorldModel,
    *,
    world_index: int,
    spec_seed: int,
) -> InoculatedWorld:
    """Calibrate one world on ``population`` and evaluate that same population in it.

    The baseline case, and the reference's ``inoculate_population(panel, wm,
    world_index, seed)`` signature. For a scenario variant use
    :func:`calibrate_world` on the baseline and :func:`apply_world` on the variant.
    """
    calibration = calibrate_world(population, model, world_index=world_index, spec_seed=spec_seed)
    return apply_world(population, model, calibration)


def _dominant(latents: Sequence[Sequence[float]], row: int) -> int:
    """Index of the factor with the largest standardised latent; first wins a tie."""
    best = 0
    for k in range(1, len(latents)):
        if latents[k][row] > latents[best][row]:
            best = k
    return best
