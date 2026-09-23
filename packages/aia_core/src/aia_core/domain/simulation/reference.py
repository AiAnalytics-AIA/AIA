"""Reference constants and the recorded differences from the reference sanitiser.

Everything in this module is either **ported exactly** from the reference Full
Simulation contract or is a **production decision** that deliberately departs
from it. Which is which is stated per item, because a constant whose provenance
is unknown is a constant nobody can safely change.

Authority: ``AiAnalytics-AIA/AIA-reference`` @ ``678e298``,
``simulation-reference-contract.md`` -- see
``docs/architecture/simulation-deterministic-engine.md`` for the pointer table.
Nothing here is copied from the reference source, which is withheld; only the
values its contract records.

Versioning. :data:`SIMULATION_CONSTANTS_VERSION` names this whole table. It is
recorded on every world model and every computed world, so a result produced
under one set of bounds can never be mistaken for one produced under another.
Change any value below and the version must change with it;
``test_simulation_world_model.py`` pins the table so that cannot happen by
accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "ABLATION_SEED_OFFSET",
    "BOUNDS",
    "DEFAULT_SPEC_SEED",
    "FACTOR_EPISTEMIC_STATUS",
    "FIELD_POLICY",
    "FS_EPISTEMIC_STATUS",
    "LINEAR_INTERPOLATION_ALLOWED",
    "REFERENCE_ARCHIVE_SHA256",
    "SIMULATION_CONSTANTS_VERSION",
    "WORLD_SEED_STRIDE",
    "FieldPolicy",
    "LegacyMechanism",
    "Objective",
    "ProductionHandling",
    "ViolationCode",
    "WorldModelBounds",
    "ablation_seed",
    "policy_for",
    "world_id",
    "world_seed",
]

SIMULATION_CONSTANTS_VERSION: Final = "sim-constants-1"

# The authoritative snapshot these values were read against (reference-source.md).
REFERENCE_ARCHIVE_SHA256: Final = "86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216"


class Objective(StrEnum):
    """What a simulation run is for. Ported exactly (``VALID_OBJECTIVES``).

    The distinction is load-bearing: only a blind forecast can ever be
    benchmark-eligible, and a blind run may not consume target-overlap evidence.
    """

    BLIND_FORECAST = "blind_forecast"
    SCENARIO_NOWCAST = "scenario_nowcast"


# --- Seeding: ported exactly -------------------------------------------------

DEFAULT_SPEC_SEED: Final = 20260816
# 104729 is the 10,000th prime; the reference derives each world's seed from it.
WORLD_SEED_STRIDE: Final = 104729
ABLATION_SEED_OFFSET: Final = 88000


def world_seed(spec_seed: int, world_index: int) -> int:
    """``seed + 104729 * (world_index + 1)``. EXACT parity with the reference."""
    if world_index < 0:
        raise ValueError(f"world_index must be >= 0; got {world_index}")
    return spec_seed + WORLD_SEED_STRIDE * (world_index + 1)


def world_id(world_index: int) -> str:
    """``world_001`` for index 0. EXACT parity with the reference ``FS_WORLD_ID``."""
    if world_index < 0:
        raise ValueError(f"world_index must be >= 0; got {world_index}")
    return f"world_{world_index + 1:03d}"


def ablation_seed(spec_seed: int, model_index: int, sample_index: int, temperature: float) -> int:
    """``seed + 88000 + mi*1000 + si*100 + int(temp*10)``. EXACT, truncation included.

    ``int`` truncates toward zero exactly as the reference does, so
    ``temperature=0.7`` contributes 7 and ``0.75`` also contributes 7.
    """
    return (
        spec_seed
        + ABLATION_SEED_OFFSET
        + model_index * 1000
        + sample_index * 100
        + int(temperature * 10)
    )


# --- Epistemic markers: ported exactly ---------------------------------------

FACTOR_EPISTEMIC_STATUS: Final = "HYPOTHESIZED_JOINT"
FS_EPISTEMIC_STATUS: Final = "EXPERIMENTAL_HYPOTHESIZED_JOINT"

# Variants are modelled independently and never interpolated (migration plan,
# Phase 7). A constant rather than a comment so that it is recorded on results.
LINEAR_INTERPOLATION_ALLOWED: Final[Literal[False]] = False


# --- Bounds ------------------------------------------------------------------


@dataclass(frozen=True)
class WorldModelBounds:
    """The numeric envelope a world model must sit inside.

    Every value is the reference's own bound except ``min_factors`` and
    ``min_drivers``, which the reference does not enforce in code (see
    :data:`FIELD_POLICY`).
    """

    # The reference prompt asks for 6-12 factors, its JSON schema says 4-12 and
    # its code tops up anything under 4 to 6 from fallback factors. The contract
    # requires one declared value. 6 is chosen: it is the only count the model
    # is ever asked for, and it is what the reference's own top-up restores.
    # Recorded as decision D9 in .planning/PROGRESS.md for data-owner sign-off.
    min_factors: int = 6
    max_factors: int = 12
    target_mean_10: tuple[float, float] = (1.2, 9.8)
    target_sd_10: tuple[float, float] = (0.6, 3.2)
    confidence: tuple[float, float] = (0.05, 0.95)
    min_drivers: int = 1
    max_drivers: int = 6
    effect: tuple[float, float] = (-1.0, 1.0)
    # |effect| below this is treated as no effect by the reference (and dropped).
    min_abs_effect: float = 0.02
    rho: tuple[float, float] = (-0.65, 0.65)
    max_correlations: int = 30
    max_label_chars: int = 120
    max_description_chars: int = 600
    max_summary_chars: int = 1800
    # FS_<factor_id>_10 is a column name; the id is constrained to what the
    # reference's ``_slug`` produces, so a model cannot inject a column name.
    factor_id_pattern: str = r"^[a-z][a-z0-9_]{0,39}$"


BOUNDS: Final = WorldModelBounds()


# --- The recorded differences ------------------------------------------------


class ViolationCode(StrEnum):
    """Why a world model was rejected. One definition, shared by producer and tests."""

    MISSING = "missing"
    WRONG_TYPE = "wrong_type"
    UNKNOWN_KEY = "unknown_key"
    NOT_FINITE = "not_finite"
    OUT_OF_RANGE = "out_of_range"
    TOO_FEW = "too_few"
    TOO_MANY = "too_many"
    TOO_LONG = "too_long"
    BLANK = "blank"
    INVALID_IDENTIFIER = "invalid_identifier"
    DUPLICATE = "duplicate"
    NEGLIGIBLE_EFFECT = "negligible_effect"
    UNKNOWN_FIELD = "unknown_field"
    NON_NUMERIC_FIELD = "non_numeric_field"
    UNKNOWN_FACTOR = "unknown_factor"
    SELF_CORRELATION = "self_correlation"
    WRONG_EPISTEMIC_STATUS = "wrong_epistemic_status"
    BLIND_TARGET_OVERLAP = "blind_target_overlap"


class LegacyMechanism(StrEnum):
    """What the reference sanitiser does with the invalid value."""

    CLIP = "clip"
    TRUNCATE = "truncate"
    CAP = "cap"
    DROP = "drop"
    TOP_UP_FROM_FALLBACK = "top_up_from_fallback"
    DEFAULT = "default"
    DEDUPLICATE = "deduplicate"
    NORMALISE = "normalise"
    STAMP = "stamp"
    STRIP = "strip"
    SCORE_AS_CATEGORY = "score_as_category"
    NOT_ENFORCED = "not_enforced"
    # The reference contract does not describe this case. Stated rather than guessed.
    NOT_RECORDED = "not_recorded"


class ProductionHandling(StrEnum):
    """What production does. ``REJECT`` is the only value in use.

    ``CLAMP`` exists so the table can say so if a future decision chooses it for a
    field. ``test_policy_table_is_reject_only_and_unambiguous`` fails while any
    entry uses it, so adopting it is a deliberate change to that test and to
    :data:`SIMULATION_CONSTANTS_VERSION`, never a quiet edit to one row.
    """

    REJECT = "reject"
    CLAMP = "clamp"


@dataclass(frozen=True)
class FieldPolicy:
    """One recorded difference between the reference sanitiser and production."""

    field: str
    code: ViolationCode
    legacy: LegacyMechanism
    legacy_detail: str
    production: ProductionHandling
    parity: Literal["INTENTIONAL_DIFFERENCE"] = "INTENTIONAL_DIFFERENCE"


_R = ProductionHandling.REJECT
_L = LegacyMechanism
_V = ViolationCode

FIELD_POLICY: Final[tuple[FieldPolicy, ...]] = (
    FieldPolicy("factors", _V.TOO_MANY, _L.CAP, "factors[:12]", _R),
    FieldPolicy(
        "factors", _V.TOO_FEW, _L.TOP_UP_FROM_FALLBACK, "< 4 topped up to >= 6 from fallback", _R
    ),
    FieldPolicy("factors[].id", _V.DUPLICATE, _L.DEDUPLICATE, "de-duplicated by _slug", _R),
    FieldPolicy("factors[].id", _V.INVALID_IDENTIFIER, _L.NORMALISE, "passed through _slug", _R),
    FieldPolicy("factors[].label", _V.TOO_LONG, _L.TRUNCATE, "truncated to 120 chars", _R),
    FieldPolicy("factors[].description", _V.TOO_LONG, _L.TRUNCATE, "truncated to 600 chars", _R),
    FieldPolicy("factors[].target_mean_10", _V.OUT_OF_RANGE, _L.CLIP, "clip(x, 1.2, 9.8)", _R),
    FieldPolicy("factors[].target_mean_10", _V.MISSING, _L.DEFAULT, "defaults to 5.0", _R),
    FieldPolicy("factors[].target_sd_10", _V.OUT_OF_RANGE, _L.CLIP, "clip(x, 0.6, 3.2)", _R),
    FieldPolicy("factors[].target_sd_10", _V.MISSING, _L.DEFAULT, "defaults to 2.0", _R),
    FieldPolicy("factors[].confidence", _V.OUT_OF_RANGE, _L.CLIP, "clip(x, 0.05, 0.95)", _R),
    FieldPolicy("factors[].confidence", _V.MISSING, _L.DEFAULT, "defaults to 0.3", _R),
    FieldPolicy(
        "factors[].epistemic_status",
        _V.WRONG_EPISTEMIC_STATUS,
        _L.STAMP,
        "overwritten with HYPOTHESIZED_JOINT",
        _R,
    ),
    FieldPolicy("factors[].drivers", _V.TOO_MANY, _L.TRUNCATE, "drivers[:6]", _R),
    FieldPolicy(
        "factors[].drivers", _V.TOO_FEW, _L.NOT_ENFORCED, "prompt asks for 1-6; code accepts 0", _R
    ),
    FieldPolicy("factors[].drivers[].effect", _V.OUT_OF_RANGE, _L.CLIP, "clip(x, -1.0, 1.0)", _R),
    FieldPolicy(
        "factors[].drivers[].effect", _V.NEGLIGIBLE_EFFECT, _L.DROP, "dropped when abs < 0.02", _R
    ),
    FieldPolicy(
        "factors[].drivers[].field",
        _V.UNKNOWN_FIELD,
        _L.DROP,
        "skipped when not in panel.columns",
        _R,
    ),
    FieldPolicy(
        "factors[].drivers[].field",
        _V.NON_NUMERIC_FIELD,
        _L.SCORE_AS_CATEGORY,
        "scored by _stable_category_score; algorithm not recovered",
        _R,
    ),
    FieldPolicy(
        "factors[].drivers[].field", _V.DUPLICATE, _L.NOT_RECORDED, "not in the contract", _R
    ),
    FieldPolicy("correlations", _V.TOO_MANY, _L.CAP, "cors[:30]", _R),
    FieldPolicy("correlations[].rho", _V.OUT_OF_RANGE, _L.CLIP, "clip(x, -0.65, 0.65)", _R),
    FieldPolicy("correlations[]", _V.UNKNOWN_FACTOR, _L.NOT_RECORDED, "not in the contract", _R),
    FieldPolicy("correlations[]", _V.SELF_CORRELATION, _L.NOT_RECORDED, "not in the contract", _R),
    FieldPolicy("correlations[]", _V.DUPLICATE, _L.NOT_RECORDED, "not in the contract", _R),
    FieldPolicy(
        "correlations[].epistemic_status",
        _V.WRONG_EPISTEMIC_STATUS,
        _L.STAMP,
        "overwritten with HYPOTHESIZED_JOINT",
        _R,
    ),
    FieldPolicy("summary", _V.TOO_LONG, _L.TRUNCATE, "truncated to 1800 chars", _R),
    FieldPolicy(
        "target_overlap_refs",
        _V.BLIND_TARGET_OVERLAP,
        _L.STRIP,
        "if objective == BLIND: requested_leaks = []",
        _R,
    ),
)


def policy_for(field: str, code: ViolationCode) -> FieldPolicy | None:
    """The recorded difference for ``(field, code)``, or ``None`` for a pure contract error.

    Contract errors -- a wrong type, an unknown key, a non-finite number -- have no
    reference counterpart worth recording: the reference would have crashed or
    coerced, and production refuses either way.
    """
    for entry in FIELD_POLICY:
        if entry.field == field and entry.code == code:
            return entry
    return None
