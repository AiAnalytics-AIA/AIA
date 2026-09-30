"""Operator classifications bound to material bytes, never a client label.

An approval is trusted composition data, not a field supplied by a model or a
research design. Changing a single pasted passage or extracted attachment text
changes its digest and requires a new classification. Empty instructions contain
no material; all other missing classifications fail closed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ai_contracts import canonical_json
from .residency import DataClass


class MaterialApproval(BaseModel):
    """A deployment operator's classification of one exact JSON material value."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_class: DataClass
    provenance: str = Field(min_length=1, max_length=1000)
    synthetic: bool = False


class MaterialDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: str
    data_class: DataClass | None
    provenance: str | None


def material_sha256(value: Any) -> str:
    """Identity of the actual material, including every nested extracted text."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def classify_material(value: Any, approvals: Sequence[MaterialApproval]) -> MaterialDecision:
    """Resolve a trusted, content-bound classification; absence is unknown."""
    digest = material_sha256(value)
    matches = [approval for approval in approvals if approval.sha256 == digest]
    if len(matches) > 1:
        raise ValueError("duplicate material classification; the operator must resolve it")
    approval = matches[0] if matches else None
    return MaterialDecision(
        sha256=digest,
        data_class=approval.data_class if approval else None,
        provenance=approval.provenance if approval else None,
    )


def most_restrictive_material(classes: Sequence[DataClass | None]) -> DataClass | None:
    """Unknown refuses the whole request; otherwise A over B over C."""
    if not classes or any(data_class is None for data_class in classes):
        return None
    for data_class in (
        DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        DataClass.CLASS_B_DERIVED_CLIENT,
        DataClass.CLASS_C_INTERNAL,
    ):
        if data_class in classes:
            return data_class
    raise AssertionError("every data class has a restrictive rank")
