"""Versioned Sociomapping methodology: the ``SociomapSpec`` contract.

A Sociomapa is only reproducible if every methodology choice that shaped it is
written down: which relation was derived, how the matrix was transformed and
normalised, how missing cells were treated, which layout algorithm ran with which
parameters and seed, and which metrics drive height and colour. This module makes
those choices an explicit, fingerprinted value rather than prompt prose, hidden
defaults or constants scattered across a frontend.

Two rules are enforced here rather than documented:

* **No hidden defaults.** Every methodology field is required. A spec that does
  not say how missing data is treated cannot be constructed.
* **Fail closed.** :func:`require_supported` refuses any spec naming a method the
  deterministic engine has not implemented. Nothing silently falls back to a
  different algorithm.

The registry of implemented methods is **empty by design** at this stage. The
legacy ``sociomap.py`` reference checkout was not available when this contract
was written, so no algorithm has been ported yet. Method identifiers are added to
:data:`IMPLEMENTED` only alongside the tested code that implements them and the
parity evidence for it -- never before.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from ..pipeline import fingerprint

__all__ = [
    "IMPLEMENTED",
    "SPEC_CONTRACT_VERSION",
    "ImplementedMethods",
    "MapKind",
    "SociomapSpec",
    "UnsupportedMethodology",
    "require_supported",
]

# Version of this *contract* (the shape of a spec), distinct from
# ``SociomapSpec.methodology_version`` (which methodology the spec describes).
SPEC_CONTRACT_VERSION = "1"


class MapKind(StrEnum):
    """The two map families the product defines.

    Both are named in ``docs/product/README.md`` ("respondent and object maps over
    a shared data contract"). A respondent map places respondents; an object map
    places the tracked objects (brands, concepts, statements) they evaluated.
    """

    RESPONDENT = "respondent"
    OBJECT = "object"


def _non_blank(value: str, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{field} must name a method explicitly; blank is not a default")
    return text


class SociomapSpec(BaseModel):
    """Every methodology decision behind one Sociomapa, as data.

    All method fields are free identifiers validated against
    :data:`IMPLEMENTED` at computation time, not at construction time: a spec
    describing a not-yet-ported method is a legitimate *description* (for
    example, recorded from a legacy artifact), but it cannot be *executed*.

    ``layout_parameters`` and ``layout_seed`` are part of the spec, and therefore
    part of its fingerprint, because they change the result. A seed of ``None``
    is an explicit statement that the algorithm is deterministic without one; it
    must not be read as "unspecified".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    methodology_version: str
    map_kind: MapKind
    relation_method: str
    matrix_transform: str
    normalization_method: str
    missing_data_policy: str
    weighting_policy: str
    layout_algorithm: str
    layout_parameters: dict[str, Any]
    layout_seed: int | None
    height_metric: str
    colour_metric: str

    @field_validator(
        "methodology_version",
        "relation_method",
        "matrix_transform",
        "normalization_method",
        "missing_data_policy",
        "weighting_policy",
        "layout_algorithm",
        "height_metric",
        "colour_metric",
    )
    @classmethod
    def _method_names_are_explicit(cls, v: str, info: Any) -> str:
        return _non_blank(v, info.field_name)

    @field_validator("layout_parameters")
    @classmethod
    def _parameters_are_json(cls, v: dict[str, Any]) -> dict[str, Any]:
        # The fingerprint is a JSON hash; a parameter that cannot be serialised
        # would be stringified silently and two different objects could collide.
        _assert_json_scalar_tree(v, "layout_parameters")
        return v

    def fingerprint(self) -> str:
        """Stable SHA256 over the whole methodology, independent of key order.

        Two specs with the same fingerprint are the same methodology. Any change
        to any field -- including one layout parameter or the seed -- changes it,
        which is how an artifact produced under one methodology can never be
        mistaken for one produced under another.
        """
        return fingerprint(
            {"contract_version": SPEC_CONTRACT_VERSION, **self.model_dump(mode="json")}
        )


def _assert_json_scalar_tree(value: Any, path: str) -> None:
    """Reject anything json.dumps would stringify via ``default=str``."""
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{path} must be finite; got {value!r}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings; got {key!r}")
            _assert_json_scalar_tree(item, f"{path}.{key}")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _assert_json_scalar_tree(item, f"{path}[{index}]")
        return
    raise ValueError(f"{path} must be JSON data (str, int, float, bool, None, list, dict)")


@dataclass(frozen=True, slots=True)
class ImplementedMethods:
    """The methods the deterministic engine can actually compute.

    One set per methodology dimension. Kept as data so that a test can assert the
    exact set and so that the artifact provenance can record which engine version
    supported what.
    """

    relation_methods: frozenset[str] = frozenset()
    matrix_transforms: frozenset[str] = frozenset()
    normalization_methods: frozenset[str] = frozenset()
    missing_data_policies: frozenset[str] = frozenset()
    weighting_policies: frozenset[str] = frozenset()
    layout_algorithms: frozenset[str] = frozenset()
    height_metrics: frozenset[str] = frozenset()
    colour_metrics: frozenset[str] = frozenset()

    def unsupported_in(self, spec: SociomapSpec) -> dict[str, str]:
        """Return ``{field: requested_value}`` for every method not implemented."""
        checks = (
            ("relation_method", spec.relation_method, self.relation_methods),
            ("matrix_transform", spec.matrix_transform, self.matrix_transforms),
            ("normalization_method", spec.normalization_method, self.normalization_methods),
            ("missing_data_policy", spec.missing_data_policy, self.missing_data_policies),
            ("weighting_policy", spec.weighting_policy, self.weighting_policies),
            ("layout_algorithm", spec.layout_algorithm, self.layout_algorithms),
            ("height_metric", spec.height_metric, self.height_metrics),
            ("colour_metric", spec.colour_metric, self.colour_metrics),
        )
        return {field: value for field, value, supported in checks if value not in supported}


# Deliberately empty. See the module docstring: identifiers are registered here
# only together with the ported, tested, parity-checked implementation.
IMPLEMENTED = ImplementedMethods()


class UnsupportedMethodology(ValueError):
    """The spec names a method this engine has not implemented.

    Raised instead of substituting another algorithm. ``unsupported`` maps each
    offending field to the value requested, so the caller (or the agent that
    proposed the spec) can see exactly what is missing.
    """

    def __init__(self, unsupported: dict[str, str]) -> None:
        self.unsupported = dict(unsupported)
        detail = ", ".join(f"{field}={value!r}" for field, value in sorted(unsupported.items()))
        super().__init__(
            "Sociomapping methodology not implemented by this engine, and no fallback is "
            f"permitted: {detail}"
        )


def require_supported(spec: SociomapSpec, implemented: ImplementedMethods = IMPLEMENTED) -> None:
    """Raise :class:`UnsupportedMethodology` unless every method is implemented.

    Call this before any computation. It is the enforcement point for the rule
    that an unsupported methodology value must never silently become a different
    algorithm.
    """
    missing = implemented.unsupported_in(spec)
    if missing:
        raise UnsupportedMethodology(missing)
