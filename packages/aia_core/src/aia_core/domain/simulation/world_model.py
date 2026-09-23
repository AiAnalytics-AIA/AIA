"""The world model contract: the one model-derived input to the numerical core.

A world model is *hypothesis*, produced by an LLM: the topic-specific latent
factors a population might carry, what drives them, and how they co-vary. It is
the boundary between semantic generation and deterministic computation, so it is
treated as untrusted input and crosses into the numerical core only as a frozen,
validated, content-addressed :class:`WorldModel`.

Two entry points, one set of bounds (``ARCHITECTURE.md`` A8):

* :func:`validate_world_model` takes raw model output and **rejects** it with
  every violation listed at once. It never clips, truncates, drops, defaults or
  tops up -- each of those is a reference behaviour recorded as an intentional
  difference in :data:`~aia_core.domain.simulation.reference.FIELD_POLICY`.
* ``WorldModel.model_validate_json`` reloads a frozen model (a fixture, an
  artifact) and re-checks the same bounds plus its own ``sha256``, so a stored
  model that was edited by hand is refused rather than simulated.

What is *not* checked on reload is the panel schema -- whether each driver field
exists in the population. That needs the population, so
:func:`~aia_core.domain.simulation.inoculation.inoculate_population` checks it
again against the actual rows.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..pipeline import fingerprint
from .reference import (
    BOUNDS,
    FACTOR_EPISTEMIC_STATUS,
    SIMULATION_CONSTANTS_VERSION,
    FieldPolicy,
    Objective,
    ViolationCode,
    policy_for,
)

__all__ = [
    "WORLD_MODEL_CONTRACT_VERSION",
    "Driver",
    "Factor",
    "FactorCorrelation",
    "PanelSchema",
    "Violation",
    "WorldModel",
    "WorldModelRejected",
    "validate_world_model",
]

WORLD_MODEL_CONTRACT_VERSION: Literal["1"] = "1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FACTOR_ID = re.compile(BOUNDS.factor_id_pattern)


class PanelSchema(BaseModel):
    """Which population fields a world model may name as drivers.

    Only numeric fields can drive a factor in this implementation. Categorical
    fields are listed so that naming one is reported as *non-numeric* rather than
    *unknown* -- the reference scores categories with an algorithm that has not
    been recovered, and production refuses rather than inventing one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str = Field(min_length=1)
    numeric_fields: frozenset[str]
    categorical_fields: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _disjoint(self) -> Self:
        both = self.numeric_fields & self.categorical_fields
        if both:
            raise ValueError(f"fields cannot be both numeric and categorical: {sorted(both)}")
        return self

    def fingerprint(self) -> str:
        return fingerprint(
            {
                "dataset_version": self.dataset_version,
                "numeric_fields": sorted(self.numeric_fields),
                "categorical_fields": sorted(self.categorical_fields),
            }
        )


# --- The frozen contract -----------------------------------------------------
#
# Field constraints repeat the bounds from reference.BOUNDS so that a reloaded
# model is held to exactly what the validator enforced.


class Driver(BaseModel):
    """A standardised-slope effect of one population field on one factor."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    field: str = Field(min_length=1)
    effect: float = Field(ge=BOUNDS.effect[0], le=BOUNDS.effect[1])

    @field_validator("effect")
    @classmethod
    def _not_negligible(cls, v: float) -> float:
        if abs(v) < BOUNDS.min_abs_effect:
            raise ValueError(f"|effect| must be >= {BOUNDS.min_abs_effect}; got {v}")
        return v


class Factor(BaseModel):
    """One hypothesised latent trait, expressed on the product's 1-10 scale."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    id: str = Field(pattern=BOUNDS.factor_id_pattern)
    label: str = Field(min_length=1, max_length=BOUNDS.max_label_chars)
    description: str = Field(max_length=BOUNDS.max_description_chars)
    target_mean_10: float = Field(ge=BOUNDS.target_mean_10[0], le=BOUNDS.target_mean_10[1])
    target_sd_10: float = Field(ge=BOUNDS.target_sd_10[0], le=BOUNDS.target_sd_10[1])
    confidence: float = Field(ge=BOUNDS.confidence[0], le=BOUNDS.confidence[1])
    drivers: tuple[Driver, ...] = Field(
        min_length=BOUNDS.min_drivers, max_length=BOUNDS.max_drivers
    )
    epistemic_status: Literal["HYPOTHESIZED_JOINT"] = FACTOR_EPISTEMIC_STATUS

    @model_validator(mode="after")
    def _unique_driver_fields(self) -> Self:
        fields = [d.field for d in self.drivers]
        if len(set(fields)) != len(fields):
            raise ValueError(f"factor {self.id!r} names a driver field twice")
        return self


class FactorCorrelation(BaseModel):
    """A hypothesised correlation between two factors' residuals."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    a: str
    b: str
    rho: float = Field(ge=BOUNDS.rho[0], le=BOUNDS.rho[1])
    epistemic_status: Literal["HYPOTHESIZED_JOINT"] = FACTOR_EPISTEMIC_STATUS

    def pair(self) -> frozenset[str]:
        return frozenset((self.a, self.b))


class WorldModel(BaseModel):
    """A validated, frozen, content-addressed world model.

    ``sha256`` is computed over every other field. The model refuses to load when
    it does not match, which is what makes a world model a fixture rather than a
    suggestion. ``contaminated_for_predictive_benchmark`` is derived, never taken
    from the model: true when target-overlap evidence was used or the objective is
    a scenario nowcast.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: Literal["1"] = WORLD_MODEL_CONTRACT_VERSION
    constants_version: Literal["sim-constants-1"] = SIMULATION_CONSTANTS_VERSION
    objective: Objective
    research_sha256: str = Field(pattern=_SHA256.pattern)
    panel_schema_sha256: str = Field(pattern=_SHA256.pattern)
    dataset_version: str = Field(min_length=1)
    summary: str = Field(max_length=BOUNDS.max_summary_chars)
    factors: tuple[Factor, ...] = Field(
        min_length=BOUNDS.min_factors, max_length=BOUNDS.max_factors
    )
    correlations: tuple[FactorCorrelation, ...] = Field(max_length=BOUNDS.max_correlations)
    target_overlap_refs: tuple[str, ...]
    contaminated_for_predictive_benchmark: bool
    sha256: str = Field(pattern=_SHA256.pattern)

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        ids = [f.id for f in self.factors]
        if len(set(ids)) != len(ids):
            raise ValueError("factor ids must be unique")
        known = set(ids)
        pairs: set[frozenset[str]] = set()
        for c in self.correlations:
            if c.a == c.b:
                raise ValueError(f"factor {c.a!r} cannot be correlated with itself")
            if c.a not in known or c.b not in known:
                raise ValueError(f"correlation {c.a!r}~{c.b!r} names an unknown factor")
            if c.pair() in pairs:
                raise ValueError(f"correlation {c.a!r}~{c.b!r} is given twice")
            pairs.add(c.pair())
        if self.objective is Objective.BLIND_FORECAST and self.target_overlap_refs:
            raise ValueError("a blind forecast cannot consume target-overlap evidence")
        if self.contaminated_for_predictive_benchmark != _contaminated(
            self.objective, self.target_overlap_refs
        ):
            raise ValueError("contaminated_for_predictive_benchmark does not match its inputs")
        if self.sha256 != self.content_sha256():
            raise ValueError("sha256 does not match the world model's content")
        return self

    def content_sha256(self) -> str:
        return fingerprint(self.model_dump(mode="json", exclude={"sha256"}))

    @property
    def factor_ids(self) -> tuple[str, ...]:
        return tuple(f.id for f in self.factors)

    def driver_fields(self) -> frozenset[str]:
        return frozenset(d.field for f in self.factors for d in f.drivers)

    def rho(self, a: str, b: str) -> float:
        """Hypothesised residual correlation; an unlisted pair is 0 by contract."""
        if a == b:
            return 1.0
        for c in self.correlations:
            if c.pair() == frozenset((a, b)):
                return c.rho
        return 0.0


def _contaminated(objective: Objective, refs: Sequence[str]) -> bool:
    return bool(refs) or objective is Objective.SCENARIO_NOWCAST


# --- The rejecting validator -------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """One reason a world model was refused.

    ``field`` is the generic path used by :data:`FIELD_POLICY`
    (``factors[].target_mean_10``); ``path`` is the concrete one
    (``factors[3].target_mean_10``). ``policy`` is the recorded difference from the
    reference, or ``None`` for a pure contract error.
    """

    path: str
    field: str
    code: ViolationCode
    detail: str

    @property
    def policy(self) -> FieldPolicy | None:
        return policy_for(self.field, self.code)


class WorldModelRejected(ValueError):
    """Raised with every violation found, not just the first."""

    def __init__(self, violations: Sequence[Violation]) -> None:
        self.violations: tuple[Violation, ...] = tuple(violations)
        lines = "; ".join(f"{v.path}: {v.code.value} ({v.detail})" for v in self.violations)
        super().__init__(f"world model rejected, {len(self.violations)} violation(s): {lines}")

    def codes(self) -> set[tuple[str, ViolationCode]]:
        return {(v.field, v.code) for v in self.violations}


_FACTOR_KEYS = frozenset(
    {
        "id",
        "label",
        "description",
        "target_mean_10",
        "target_sd_10",
        "confidence",
        "drivers",
        "epistemic_status",
    }
)
_DRIVER_KEYS = frozenset({"field", "effect"})
_CORRELATION_KEYS = frozenset({"a", "b", "rho", "epistemic_status"})
_MODEL_KEYS = frozenset({"summary", "factors", "correlations", "target_overlap_refs"})


class _Collector:
    def __init__(self) -> None:
        self.found: list[Violation] = []

    def add(self, path: str, field: str, code: ViolationCode, detail: str) -> None:
        self.found.append(Violation(path, field, code, detail))

    def keys(self, obj: Mapping[str, Any], allowed: frozenset[str], path: str, field: str) -> None:
        for key in sorted(set(obj) - allowed):
            self.add(f"{path}.{key}" if path else key, field, ViolationCode.UNKNOWN_KEY, key)

    def number(
        self,
        obj: Mapping[str, Any],
        key: str,
        path: str,
        field: str,
        bounds: tuple[float, float],
    ) -> float | None:
        where = f"{path}.{key}"
        if key not in obj or obj[key] is None:
            self.add(where, field, ViolationCode.MISSING, "required; no default is applied")
            return None
        raw = obj[key]
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            self.add(where, field, ViolationCode.WRONG_TYPE, f"expected a number, got {raw!r}")
            return None
        value = float(raw)
        if not math.isfinite(value):
            self.add(where, field, ViolationCode.NOT_FINITE, repr(value))
            return None
        lo, hi = bounds
        if not lo <= value <= hi:
            self.add(where, field, ViolationCode.OUT_OF_RANGE, f"{value} not in [{lo}, {hi}]")
            return None
        return value

    def text(
        self,
        obj: Mapping[str, Any],
        key: str,
        path: str,
        field: str,
        max_chars: int,
        *,
        required: bool,
    ) -> str | None:
        where = f"{path}.{key}" if path else key
        raw = obj.get(key)
        if raw is None:
            if required:
                self.add(where, field, ViolationCode.MISSING, "required")
                return None
            return ""
        if not isinstance(raw, str):
            self.add(where, field, ViolationCode.WRONG_TYPE, f"expected text, got {raw!r}")
            return None
        if required and not raw.strip():
            self.add(where, field, ViolationCode.BLANK, "must not be blank")
            return None
        if len(raw) > max_chars:
            self.add(where, field, ViolationCode.TOO_LONG, f"{len(raw)} > {max_chars} chars")
            return None
        return raw

    def epistemic(self, obj: Mapping[str, Any], path: str, field: str) -> None:
        status = obj.get("epistemic_status", FACTOR_EPISTEMIC_STATUS)
        if status != FACTOR_EPISTEMIC_STATUS:
            self.add(
                f"{path}.epistemic_status",
                field,
                ViolationCode.WRONG_EPISTEMIC_STATUS,
                f"{status!r}; a world model is always {FACTOR_EPISTEMIC_STATUS}",
            )

    def items(
        self, obj: Mapping[str, Any], key: str, path: str, field: str
    ) -> list[Mapping[str, Any]] | None:
        where = f"{path}.{key}" if path else key
        raw = obj.get(key)
        if raw is None:
            self.add(where, field, ViolationCode.MISSING, "required")
            return None
        if isinstance(raw, str | bytes) or not isinstance(raw, Sequence):
            self.add(where, field, ViolationCode.WRONG_TYPE, "expected a list")
            return None
        out: list[Mapping[str, Any]] = []
        for i, item in enumerate(raw):
            if not isinstance(item, Mapping):
                self.add(f"{where}[{i}]", field, ViolationCode.WRONG_TYPE, "expected an object")
            else:
                out.append(item)
        return out if len(out) == len(raw) else None


def validate_world_model(
    raw: Mapping[str, Any],
    *,
    schema: PanelSchema,
    objective: Objective,
    research_sha256: str,
) -> WorldModel:
    """Validate raw model output and freeze it, or reject it with every violation.

    ``objective`` and ``research_sha256`` come from the run, never from the model:
    a model cannot declare its own run blind, nor bind itself to research it was
    not given.
    """
    if not _SHA256.match(research_sha256):
        raise ValueError("research_sha256 must be a lowercase hex SHA256")

    bad = _Collector()
    if not isinstance(raw, Mapping):
        raise WorldModelRejected(
            [Violation("", "", ViolationCode.WRONG_TYPE, "a world model is a JSON object")]
        )
    bad.keys(raw, _MODEL_KEYS, "", "")

    summary = bad.text(raw, "summary", "", "summary", BOUNDS.max_summary_chars, required=False)
    factors = _validate_factors(raw, schema, bad)
    correlations = _validate_correlations(raw, factors, bad)
    refs = _validate_refs(raw, objective, bad)

    if bad.found:
        raise WorldModelRejected(bad.found)

    content: dict[str, Any] = {
        "contract_version": WORLD_MODEL_CONTRACT_VERSION,
        "constants_version": SIMULATION_CONSTANTS_VERSION,
        "objective": objective.value,
        "research_sha256": research_sha256,
        "panel_schema_sha256": schema.fingerprint(),
        "dataset_version": schema.dataset_version,
        "summary": summary,
        "factors": factors,
        "correlations": correlations,
        "target_overlap_refs": refs,
        "contaminated_for_predictive_benchmark": _contaminated(objective, refs),
    }
    # Address the canonical JSON of the validated parts -- exactly what
    # WorldModel.content_sha256 recomputes on load.
    content["factors"] = [Factor.model_validate(f).model_dump(mode="json") for f in factors]
    content["correlations"] = [
        FactorCorrelation.model_validate(c).model_dump(mode="json") for c in correlations
    ]
    return WorldModel.model_validate({**content, "sha256": fingerprint(content)})


def _validate_factors(
    raw: Mapping[str, Any], schema: PanelSchema, bad: _Collector
) -> list[dict[str, Any]]:
    items = bad.items(raw, "factors", "", "factors")
    if items is None:
        return []
    if len(items) > BOUNDS.max_factors:
        bad.add(
            "factors", "factors", ViolationCode.TOO_MANY, f"{len(items)} > {BOUNDS.max_factors}"
        )
    if len(items) < BOUNDS.min_factors:
        bad.add("factors", "factors", ViolationCode.TOO_FEW, f"{len(items)} < {BOUNDS.min_factors}")

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, f in enumerate(items):
        path = f"factors[{i}]"
        bad.keys(f, _FACTOR_KEYS, path, "factors[]")
        fid = f.get("id")
        if not isinstance(fid, str) or not _FACTOR_ID.match(fid):
            bad.add(
                f"{path}.id",
                "factors[].id",
                ViolationCode.INVALID_IDENTIFIER,
                f"{fid!r} must match {BOUNDS.factor_id_pattern}",
            )
        elif fid in seen:
            bad.add(f"{path}.id", "factors[].id", ViolationCode.DUPLICATE, fid)
        else:
            seen.add(fid)

        label = bad.text(f, "label", path, "factors[].label", BOUNDS.max_label_chars, required=True)
        description = bad.text(
            f,
            "description",
            path,
            "factors[].description",
            BOUNDS.max_description_chars,
            required=False,
        )
        mean = bad.number(
            f, "target_mean_10", path, "factors[].target_mean_10", BOUNDS.target_mean_10
        )
        sd = bad.number(f, "target_sd_10", path, "factors[].target_sd_10", BOUNDS.target_sd_10)
        conf = bad.number(f, "confidence", path, "factors[].confidence", BOUNDS.confidence)
        bad.epistemic(f, path, "factors[].epistemic_status")
        drivers = _validate_drivers(f, path, schema, bad)
        out.append(
            {
                "id": fid,
                "label": label,
                "description": description,
                "target_mean_10": mean,
                "target_sd_10": sd,
                "confidence": conf,
                "drivers": drivers,
                "epistemic_status": FACTOR_EPISTEMIC_STATUS,
            }
        )
    return out


def _validate_drivers(
    f: Mapping[str, Any], path: str, schema: PanelSchema, bad: _Collector
) -> list[dict[str, Any]]:
    items = bad.items(f, "drivers", path, "factors[].drivers")
    if items is None:
        return []
    where = f"{path}.drivers"
    if len(items) > BOUNDS.max_drivers:
        bad.add(
            where,
            "factors[].drivers",
            ViolationCode.TOO_MANY,
            f"{len(items)} > {BOUNDS.max_drivers}",
        )
    if len(items) < BOUNDS.min_drivers:
        bad.add(
            where,
            "factors[].drivers",
            ViolationCode.TOO_FEW,
            f"{len(items)} < {BOUNDS.min_drivers}",
        )

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for j, d in enumerate(items):
        dpath = f"{where}[{j}]"
        bad.keys(d, _DRIVER_KEYS, dpath, "factors[].drivers[]")
        name = d.get("field")
        fkey = "factors[].drivers[].field"
        if not isinstance(name, str) or not name:
            bad.add(f"{dpath}.field", fkey, ViolationCode.MISSING, "a driver names a field")
        elif name in schema.categorical_fields:
            bad.add(f"{dpath}.field", fkey, ViolationCode.NON_NUMERIC_FIELD, name)
        elif name not in schema.numeric_fields:
            bad.add(f"{dpath}.field", fkey, ViolationCode.UNKNOWN_FIELD, name)
        elif name in seen:
            bad.add(f"{dpath}.field", fkey, ViolationCode.DUPLICATE, name)
        else:
            seen.add(name)
        effect = bad.number(d, "effect", dpath, "factors[].drivers[].effect", BOUNDS.effect)
        if effect is not None and abs(effect) < BOUNDS.min_abs_effect:
            bad.add(
                f"{dpath}.effect",
                "factors[].drivers[].effect",
                ViolationCode.NEGLIGIBLE_EFFECT,
                f"|{effect}| < {BOUNDS.min_abs_effect}",
            )
        out.append({"field": name, "effect": effect})
    return out


def _validate_correlations(
    raw: Mapping[str, Any], factors: list[dict[str, Any]], bad: _Collector
) -> list[dict[str, Any]]:
    items = bad.items(raw, "correlations", "", "correlations")
    if items is None:
        return []
    if len(items) > BOUNDS.max_correlations:
        bad.add(
            "correlations",
            "correlations",
            ViolationCode.TOO_MANY,
            f"{len(items)} > {BOUNDS.max_correlations}",
        )
    known = {f["id"] for f in factors if isinstance(f["id"], str)}
    out: list[dict[str, Any]] = []
    pairs: set[frozenset[str]] = set()
    for k, c in enumerate(items):
        path = f"correlations[{k}]"
        bad.keys(c, _CORRELATION_KEYS, path, "correlations[]")
        a, b = c.get("a"), c.get("b")
        if not isinstance(a, str) or not isinstance(b, str):
            bad.add(path, "correlations[]", ViolationCode.MISSING, "a and b name two factors")
        elif a == b:
            bad.add(path, "correlations[]", ViolationCode.SELF_CORRELATION, a)
        elif a not in known or b not in known:
            bad.add(path, "correlations[]", ViolationCode.UNKNOWN_FACTOR, f"{a}~{b}")
        elif frozenset((a, b)) in pairs:
            bad.add(path, "correlations[]", ViolationCode.DUPLICATE, f"{a}~{b}")
        else:
            pairs.add(frozenset((a, b)))
        rho = bad.number(c, "rho", path, "correlations[].rho", BOUNDS.rho)
        bad.epistemic(c, path, "correlations[].epistemic_status")
        out.append({"a": a, "b": b, "rho": rho, "epistemic_status": FACTOR_EPISTEMIC_STATUS})
    return out


def _validate_refs(raw: Mapping[str, Any], objective: Objective, bad: _Collector) -> list[str]:
    value = raw.get("target_overlap_refs", [])
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        bad.add("target_overlap_refs", "target_overlap_refs", ViolationCode.WRONG_TYPE, "list")
        return []
    refs = list(value)
    if not all(isinstance(r, str) and r for r in refs):
        bad.add(
            "target_overlap_refs",
            "target_overlap_refs",
            ViolationCode.WRONG_TYPE,
            "research item ids are non-blank text",
        )
        return []
    if objective is Objective.BLIND_FORECAST and refs:
        bad.add(
            "target_overlap_refs",
            "target_overlap_refs",
            ViolationCode.BLIND_TARGET_OVERLAP,
            f"{len(refs)} target-overlap reference(s) in a blind forecast",
        )
    return refs
