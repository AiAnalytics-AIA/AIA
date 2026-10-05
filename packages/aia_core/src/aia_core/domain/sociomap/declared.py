"""The declared relationship matrix: what an H-Model is fitted to, as it was measured.

An H-Model layout uses relations **only through their order** (its evaluator is a rank
correlation, ``hmodel.py``; the experimental candidate's objective likewise, ``hmodel_candidate``).
So a layout needs no relation on ``[0, 1]``: a signed Pearson correlation can be laid out as
it is, and the open question of how RTS places a negative correlation on ``[0, 1]`` (M12) does
not change the layout -- any strictly increasing conversion gives the same ranks. What a
conversion *would* change (coherence levels, a matrix shown to a reader as 0-1 relations) is
left to the caller, which refuses it by name while M12 is open.

A :class:`DeclaredRelations` keeps every value as measured, the scale it is on, every
undefined pair with its reason, the fingerprint of what it was built from and the rule ids
that built it. Nothing is clipped, shifted, imputed or dropped:

* :func:`declared_from_fuzzy` -- a complete fuzzy matrix (``FUZZY_0_1``);
* :func:`declared_from_correlations` -- RTS object correlations, signed (``SIGNED_CORRELATION``);
  a pair with no correlation (a constant column) stays undefined and names why.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Self

from pydantic import field_validator, model_validator

from ..pipeline import fingerprint
from .fuzzy import FuzzyMatrix, FuzzyMatrixError, ObjectCorrelations
from .models import _check_finite, _check_ids, _Frozen, _reject_booleans

__all__ = [
    "DeclaredRelations",
    "RelationScale",
    "declared_from_correlations",
    "declared_from_fuzzy",
]


class RelationScale(StrEnum):
    """What a declared relation's number means. Higher is always closer."""

    FUZZY_0_1 = "fuzzy_0_1"  # QED-F1 relations on [0, 1]
    SIGNED_CORRELATION = "signed_correlation"  # Pearson r on [-1, 1], kept signed (RTS-O1)


_RANGE = {RelationScale.FUZZY_0_1: (0.0, 1.0), RelationScale.SIGNED_CORRELATION: (-1.0, 1.0)}


class DeclaredRelations(_Frozen):
    """A square, possibly asymmetric relation matrix with undefined pairs kept and named."""

    element_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    scale: RelationScale
    undefined: tuple[tuple[str, str, str], ...]  # (row element, column element, reason)
    source_fingerprint: str
    rules: tuple[str, ...]

    @field_validator("element_ids")
    @classmethod
    def _elements(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=2, what="element")

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @model_validator(mode="after")
    def _contract(self) -> Self:
        n = len(self.element_ids)
        if len(self.values) != n or any(len(row) != n for row in self.values):
            raise ValueError(f"a declared relation matrix over {n} elements is {n} x {n}")
        if not self.rules:
            raise ValueError("rules must name the evidence-register rules that built it")
        low, high = _RANGE[self.scale]
        index = {e: i for i, e in enumerate(self.element_ids)}
        named = set()
        for a, b, reason in self.undefined:
            if a not in index or b not in index or a == b or not reason.strip():
                raise ValueError(f"undefined pair ({a!r}, {b!r}) is not a named off-diagonal pair")
            named.add((index[a], index[b]))
        checked: list[tuple[float | None, ...]] = []
        for r, row in enumerate(self.values):
            cells: list[float | None] = []
            for s, raw in enumerate(row):
                value = _check_finite(raw, f"values[{r}][{s}]")
                if r == s:
                    if value is not None:
                        raise ValueError(f"values[{r}][{r}] is the diagonal and must be None")
                elif value is None:
                    if (r, s) not in named:
                        raise ValueError(f"values[{r}][{s}] is undefined without a reason")
                else:
                    if (r, s) in named:
                        raise ValueError(f"values[{r}][{s}] is named undefined but has a value")
                    if not low <= value <= high:
                        raise ValueError(f"values[{r}][{s}] = {value!r} is outside {low}..{high}")
                cells.append(value)
            checked.append(tuple(cells))
        object.__setattr__(self, "values", tuple(checked))
        return self

    @property
    def size(self) -> int:
        return len(self.element_ids)

    def relation(self, row: int, column: int) -> float | None:
        """The relation of ``row`` to ``column``; ``None`` when undefined (see ``undefined``)."""
        if row == column:
            raise FuzzyMatrixError("the diagonal is not a relation")
        return self.values[row][column]

    def is_symmetric(self) -> bool:
        return all(
            self.values[r][s] == self.values[s][r]
            for r in range(self.size)
            for s in range(r + 1, self.size)
        )

    def negative_pairs(self) -> tuple[tuple[str, str, float], ...]:
        """Every pair ``r < s`` with a negative relation (only possible for correlations)."""
        return tuple(
            (self.element_ids[r], self.element_ids[s], v)
            for r in range(self.size)
            for s in range(r + 1, self.size)
            if (v := self.values[r][s]) is not None and v < 0
        )

    def permuted(self, order: Sequence[int]) -> DeclaredRelations:
        if sorted(order) != list(range(self.size)):
            raise FuzzyMatrixError("order must be a permutation of the element positions")
        return self.model_copy(
            update={
                "element_ids": tuple(self.element_ids[i] for i in order),
                "values": tuple(tuple(self.values[i][j] for j in order) for i in order),
            }
        )

    def fingerprint(self) -> str:
        return fingerprint(self.model_dump(mode="json"))


def declared_from_fuzzy(matrix: FuzzyMatrix) -> DeclaredRelations:
    """A complete fuzzy matrix, as declared relations on ``[0, 1]``."""
    return DeclaredRelations(
        element_ids=matrix.element_ids,
        values=matrix.values,
        scale=RelationScale.FUZZY_0_1,
        undefined=(),
        source_fingerprint=matrix.fingerprint(),
        rules=matrix.rules,
    )


def declared_from_correlations(correlations: ObjectCorrelations) -> DeclaredRelations:
    """RTS object correlations as declared relations: signed, undefined pairs kept."""
    undefined: list[tuple[str, str, str]] = []
    for a, b, why in correlations.undefined:
        undefined.extend([(a, b, why), (b, a, why)])
    return DeclaredRelations(
        element_ids=correlations.object_ids,
        values=correlations.r,
        scale=RelationScale.SIGNED_CORRELATION,
        undefined=tuple(undefined),
        source_fingerprint=fingerprint(correlations.model_dump(mode="json")),
        rules=correlations.rules,
    )
