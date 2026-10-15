"""A dimension definition: what a materialization is asked to make (population-operations P4d2).

K5 (Client Knowledge) will supply this shape once a person accepts a dimension; until then the
materialize service takes it as typed input, so the population side can land and be tested
first. The contract is the plan's "What the contract requires of K5's output"
(``.planning/plans/population-operations.md``): the id and version, construct and label; the
kind; the target anchor with the accepted evidence it came from; the predictors; the
missingness rule and the valid range. A definition alone has no respondent values.

Everything here is checked without a population: the shape, the target's range for its kind,
the predictors' form. Whether each predictor exists in the base and may build a persona is the
service's question (it needs the base version's policy), and the step asks it again of the
loaded population.

Nothing here performs I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .derivation import EvidencePredictor, EvidenceSpec, sanitize_dimension_id
from .materialized import MaterializedKind

__all__ = [
    "DEFINITION_CONTRACT",
    "DefinitionRefused",
    "DimensionDefinition",
    "EvidenceAnchor",
    "MissingnessRule",
    "PredictorSpec",
    "valid_range",
]

#: The version of a definition's stored form; part of its hash.
DEFINITION_CONTRACT: Final = "population-dimension-definition/v1"


class DefinitionRefused(ValueError):
    """A definition does not meet the contract; ``reason`` names the rule."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class MissingnessRule(StrEnum):
    """What a respondent missing a predictor counts as."""

    #: 18.6.6's rule (``_predictor_score``): a missing value is the predictor's mean (z = 0).
    PREDICTOR_MEAN = "predictor_mean"


#: The values a kind's field holds, inclusive; the only valid range for that kind (M2a).
_RANGES: Final = {
    MaterializedKind.BINARY: (0.0, 1.0),
    MaterializedKind.SCALE_1_10: (1.0, 10.0),
}


def valid_range(kind: MaterializedKind) -> tuple[float, float]:
    """The values a field of ``kind`` holds."""
    return _RANGES[kind]


@dataclass(frozen=True, slots=True)
class EvidenceAnchor:
    """The accepted evidence a target came from: a knowledge item, its revision, the span."""

    knowledge_item_id: str
    revision: int
    span: str

    def __post_init__(self) -> None:
        if not self.knowledge_item_id or self.revision < 1 or not self.span.strip():
            raise DefinitionRefused(
                "a target names the knowledge item, the revision and the span it came from",
                reason="evidence_missing",
            )


@dataclass(frozen=True, slots=True)
class PredictorSpec:
    """An existing field of the base that orders respondents, its direction and strength."""

    field: str
    negative: bool = False
    strength: float = 1.0

    def __post_init__(self) -> None:
        if not self.field:
            raise DefinitionRefused("a predictor names its field", reason="predictor_unnamed")
        if not (self.strength > 0):
            # 18.6.6 read 0 as 1; a typed definition says what it means.
            raise DefinitionRefused(
                f"predictor {self.field}: strength must be positive", reason="strength_invalid"
            )


@dataclass(frozen=True, slots=True)
class DimensionDefinition:
    """One dimension to materialize, immutable and identified by its content."""

    dimension_id: str
    version: int
    construct: str
    label: str
    kind: MaterializedKind
    #: A prevalence in (0, 1) for BINARY, a mean in [1, 10] for SCALE_1_10.
    target: float
    evidence: EvidenceAnchor
    predictors: tuple[PredictorSpec, ...]
    missingness: MissingnessRule
    #: Must be the kind's range (:func:`valid_range`): stated, so a reader never assumes it.
    range: tuple[float, float]

    def __post_init__(self) -> None:
        if not self.dimension_id or sanitize_dimension_id(self.dimension_id) != self.dimension_id:
            raise DefinitionRefused(
                f"{self.dimension_id!r} is not a field name (lowercase, digits, underscores)",
                reason="dimension_id_invalid",
            )
        if self.version < 1:
            raise DefinitionRefused("a definition's version starts at 1", reason="version_invalid")
        if not self.construct.strip() or not self.label.strip():
            raise DefinitionRefused("a definition names its construct and label", reason="unnamed")
        if self.kind is MaterializedKind.BINARY and not (0 < self.target < 1):
            raise DefinitionRefused(
                "a binary target is a prevalence between 0 and 1", reason="target_out_of_range"
            )
        if self.kind is MaterializedKind.SCALE_1_10 and not (1 <= self.target <= 10):
            raise DefinitionRefused(
                "a 1-10 target is a mean between 1 and 10", reason="target_out_of_range"
            )
        if not self.predictors:
            raise DefinitionRefused("a definition names its predictors", reason="no_predictor")
        fields = [p.field for p in self.predictors]
        if len(set(fields)) != len(fields):
            raise DefinitionRefused("a predictor is named once", reason="predictor_repeated")
        if tuple(self.range) != valid_range(self.kind):
            raise DefinitionRefused(
                f"the valid range of a {self.kind.value} field is {valid_range(self.kind)}",
                reason="range_invalid",
            )

    def payload(self) -> dict[str, Any]:
        """The stored form, in a fixed order: what :attr:`sha256` is the hash of."""
        return {
            "contract": DEFINITION_CONTRACT,
            "dimension_id": self.dimension_id,
            "version": self.version,
            "construct": self.construct,
            "label": self.label,
            "kind": self.kind.value,
            "target": self.target,
            "evidence": {
                "knowledge_item_id": self.evidence.knowledge_item_id,
                "revision": self.evidence.revision,
                "span": self.evidence.span,
            },
            "predictors": [
                {"field": p.field, "negative": p.negative, "strength": p.strength}
                for p in self.predictors
            ],
            "missingness": self.missingness.value,
            "range": list(self.range),
        }

    @property
    def sha256(self) -> str:
        """The definition's identity: the SHA256 of its canonical JSON."""
        text = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def from_payload(cls, payload: Any) -> DimensionDefinition:
        """Read a stored or submitted definition; refuse any other contract or shape."""
        if not isinstance(payload, dict) or payload.get("contract") != DEFINITION_CONTRACT:
            raise DefinitionRefused(f"not a {DEFINITION_CONTRACT} definition", reason="contract")
        try:
            evidence = payload["evidence"]
            return cls(
                dimension_id=str(payload["dimension_id"]),
                version=int(payload["version"]),
                construct=str(payload["construct"]),
                label=str(payload["label"]),
                kind=MaterializedKind(payload["kind"]),
                target=float(payload["target"]),
                evidence=EvidenceAnchor(
                    knowledge_item_id=str(evidence["knowledge_item_id"]),
                    revision=int(evidence["revision"]),
                    span=str(evidence["span"]),
                ),
                predictors=tuple(
                    PredictorSpec(
                        field=str(p["field"]),
                        negative=bool(p["negative"]),
                        strength=float(p["strength"]),
                    )
                    for p in payload["predictors"]
                ),
                missingness=MissingnessRule(payload["missingness"]),
                range=(float(payload["range"][0]), float(payload["range"][1])),
            )
        except DefinitionRefused:
            raise
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise DefinitionRefused(
                f"the definition does not read: {exc}", reason="malformed"
            ) from None

    def evidence_spec(self) -> EvidenceSpec:
        """What P4b's derivation is given: the kind, the target and the predictors."""
        return EvidenceSpec(
            kind=self.kind,
            target=self.target,
            predictors=tuple(
                EvidencePredictor(column=p.field, negative=p.negative, strength=p.strength)
                for p in self.predictors
            ),
        )
