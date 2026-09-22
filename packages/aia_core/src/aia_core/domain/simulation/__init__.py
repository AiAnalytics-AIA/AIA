"""Deterministic simulation core: numbers from a frozen world model, never from a model call.

Boundary this package enforces (see
``docs/architecture/simulation-deterministic-engine.md``):

* **Semantic, model-generated** -- the world model's factors, drivers and
  correlations, and a scenario's narrative. These enter only as a validated,
  frozen :class:`WorldModel` and an approved :class:`ScenarioContract`.
* **Deterministic** -- everything else: world seeds, the correlation projection,
  population inoculation, outcomes, ensembles, variant deltas, frozen predictions,
  write-once truth and scoring. Pure functions of their inputs; no provider, no
  I/O, no clock.

:mod:`.reference` holds the reference constants and the per-field record of where
production rejects what the reference silently clipped.
"""

from .numerics import (
    NEAREST_CORRELATION_ALGORITHM,
    RNG_ALGORITHM,
    CorrelationFactor,
    NotPositiveDefinite,
    correlation_factor,
    nearest_correlation,
)
from .reference import (
    BOUNDS,
    DEFAULT_SPEC_SEED,
    FACTOR_EPISTEMIC_STATUS,
    FIELD_POLICY,
    FS_EPISTEMIC_STATUS,
    LINEAR_INTERPOLATION_ALLOWED,
    SIMULATION_CONSTANTS_VERSION,
    WORLD_SEED_STRIDE,
    FieldPolicy,
    LegacyMechanism,
    Objective,
    ProductionHandling,
    ViolationCode,
    ablation_seed,
    world_id,
    world_seed,
)
from .world_model import (
    Driver,
    Factor,
    FactorCorrelation,
    PanelSchema,
    Violation,
    WorldModel,
    WorldModelRejected,
    validate_world_model,
)

__all__ = [
    "BOUNDS",
    "DEFAULT_SPEC_SEED",
    "FACTOR_EPISTEMIC_STATUS",
    "FIELD_POLICY",
    "FS_EPISTEMIC_STATUS",
    "LINEAR_INTERPOLATION_ALLOWED",
    "NEAREST_CORRELATION_ALGORITHM",
    "RNG_ALGORITHM",
    "SIMULATION_CONSTANTS_VERSION",
    "WORLD_SEED_STRIDE",
    "CorrelationFactor",
    "Driver",
    "Factor",
    "FactorCorrelation",
    "FieldPolicy",
    "LegacyMechanism",
    "NotPositiveDefinite",
    "Objective",
    "PanelSchema",
    "ProductionHandling",
    "Violation",
    "ViolationCode",
    "WorldModel",
    "WorldModelRejected",
    "ablation_seed",
    "correlation_factor",
    "nearest_correlation",
    "validate_world_model",
    "world_id",
    "world_seed",
]
