"""The fuzzy matrix and the documented ways data become one.

Sociomapping (Radvan Bahbouh, QED Group) builds every map in four stages,
DATA -> MATRIX -> H-MODEL -> MAPS (SOMECS Software Help, CZ, p. 1). This module is the MATRIX
stage's contract and the DATA-stage rules the method's documents state. Plan:
``.planning/plans/sociomapping-engine.md``; every rule below has an id in the evidence
register ``docs/migration/sociomapping-evidence-register.json`` (source, page, formula,
validation, uncertainty), and every output records the ids of the rules that made it.

**Two products, two pipelines, kept apart.** A rule documented for one is not applied to the
other:

* **RTS** (Real-Time Sociomapping, the questionnaire product; RTS designs doc pp. 18-19).
  A *people* question is already a square matrix: row = who rated, column = who was rated,
  diagonal excluded (RTS-P1). Answers are normalised by the question's scale points, never by
  the data's range (RTS-N1). An *object* question is respondents x objects; by default it
  becomes an object x object matrix by the correlation of the answer columns (RTS-O1), and
  the documented example puts those correlations into the relation matrix as they are
  (RTS-O2). RTS requires every question answered (design description p. 3), so its data are
  complete.
* **SOMECS** (the desktop software). STORM data (subjects x objects) are transformed within
  each row or within the whole database (SOMECS-D2, -D3), or turned into ranks (SOMECS-D4,
  not documented enough to build); an empty field is filled with 0 (SOMECS-D1). How SOMECS
  then turns transformed STORM data into an n x n fuzzy matrix is not documented (M1), so
  :func:`somecs_transform_storm` has no consumer yet.
* **Legacy AIA**: the 1-10 relation scale of ``relations.coerce_relation_scale_1_10`` (F1),
  mapped back by :func:`legacy_fuzzy_from_relation_1_10` (LEGACY-R1).

**Order of normalisation and correlation.** Pearson's r is unchanged by a positive affine
map of a column, so normalising answers by the scale (the same map for every cell) before
correlating gives the same r as correlating the raw answers. Normalising each *respondent's
row* is not such a map: it changes r (``test_row_normalisation_changes_correlation``). RTS
documents scale normalisation then correlation; nothing documents row transforms followed by
correlation, so :func:`rts_object_correlations` accepts only RTS-scaled data.

**Negative correlations are data.** :func:`rts_object_correlations` keeps the signed matrix
(``ObjectCorrelations``), with every pair's support. Turning it into a ``[0, 1]`` relation is
documented only for ``r >= 0`` (the RTS example has no negative pair); a negative pair is
refused there, by name, and stays in the signed matrix (M12). Nothing shifts, clips or drops it.

**Computable is not adequate.** A correlation exists from two respondents and a map renders
from two questionnaires (Cloud RTS specification p. 54); neither says the result is
statistically meaningful. Support is recorded; adequacy is a separate, open policy (M14).

**Averaging is not aggregation.** SOMECS aggregates compatible matrices as a weighted mean
*after* a discrepancy check whose measure is undocumented (SOMECS help pp. 12, 31-32;
M11). :func:`weighted_mean_fuzzy` computes the mean and records that the check was not
performed, with the inputs and weights; it does not claim to be SOMECS aggregation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import field_validator, model_validator

from ..pipeline import fingerprint
from .models import RatingsMatrix, _check_finite, _check_ids, _Frozen, _reject_booleans

__all__ = [
    "MIN_FUZZY_ELEMENTS",
    "FuzzyMatrix",
    "FuzzyMatrixError",
    "FuzzySource",
    "MethodologyUndetermined",
    "NormalisedStorm",
    "ObjectCorrelations",
    "Product",
    "StormMissingPolicy",
    "StormTransform",
    "WeightedMeanFuzzy",
    "legacy_fuzzy_from_relation_1_10",
    "rts_fuzzy_from_correlations",
    "rts_object_correlations",
    "rts_people_matrix",
    "rts_scale_answers",
    "somecs_transform_storm",
    "weighted_mean_fuzzy",
]

MIN_FUZZY_ELEMENTS = 2

# SOMECS help p. 22: a subject who rated every object the same gets 0.5 everywhere.
_EQUAL_ROW_VALUE = 0.5

# AIA's legacy relation scale (coerce_relation_scale_1_10, F1): similarity s -> 1 + 9 s.
_RELATION_SCALE = (1.0, 10.0)


class FuzzyMatrixError(ValueError):
    """The input breaks a contract of this module (shape, range, completeness)."""


class MethodologyUndetermined(ValueError):
    """A rule the method's documents do not state, waiting on evidence or the method owner.

    ``question`` names the open question in ``.planning/plans/sociomapping-engine.md``.
    """

    def __init__(self, question: str, detail: str) -> None:
        self.question = question
        super().__init__(f"{detail} (open methodology question {question})")


class Product(StrEnum):
    """Whose rule produced a value: the products are documented separately."""

    RTS = "rts"
    SOMECS = "somecs"
    LEGACY_AIA = "legacy_aia"
    ENTERED = "entered"  # a matrix typed or pasted, as SOMECS's matrix editor accepts


class FuzzySource(StrEnum):
    """Where a fuzzy matrix's values came from."""

    ENTERED = "entered"
    RTS_PEOPLE = "rts_people"
    RTS_OBJECT_CORRELATION = "rts_object_correlation"
    LEGACY_RELATION_1_10 = "legacy_relation_1_10"
    WEIGHTED_MEAN = "weighted_mean"
    MERGED = "merged"  # coherence classes merged into elements (coherence.py)


class StormTransform(StrEnum):
    """How STORM answers were put on ``[0, 1]``."""

    RTS_SCALE = "rts_scale"  # RTS-N1: by the question's scale points
    SOMECS_WITHIN_ROW = "somecs_within_row"  # SOMECS-D2
    SOMECS_WITHIN_DATABASE = "somecs_within_database"  # SOMECS-D3
    SOMECS_ORDINAL = "somecs_ordinal"  # SOMECS-D4: rank convention undocumented (M1)


class StormMissingPolicy(StrEnum):
    """What an empty answer becomes. No default: the caller names one."""

    KEEP_EMPTY = "keep_empty"  # the cell stays None; anything needing it refuses
    SOMECS_ZERO = "somecs_zero"  # SOMECS-D1: the empty field becomes 0 before transforming


_SOMECS_TRANSFORMS = {StormTransform.SOMECS_WITHIN_ROW, StormTransform.SOMECS_WITHIN_DATABASE}


def _rules(v: tuple[str, ...]) -> tuple[str, ...]:
    if not v or any(not isinstance(r, str) or not r.strip() for r in v):
        raise ValueError("rules must name at least one evidence-register rule id")
    return v


class FuzzyMatrix(_Frozen):
    """A square, possibly asymmetric matrix of relations on ``[0, 1]`` (QED-F1).

    ``values[r][s]`` is the relation of element ``r`` to element ``s``; the higher, the
    closer. Every off-diagonal cell is required -- a missing relation is refused, not read
    as neutral (A4). The diagonal is ``None``. ``rules`` is the lineage of rule ids.
    """

    element_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    source: FuzzySource
    rules: tuple[str, ...]

    @field_validator("element_ids")
    @classmethod
    def _elements(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=MIN_FUZZY_ELEMENTS, what="fuzzy element")

    @field_validator("rules")
    @classmethod
    def _rule_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _rules(v)

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @model_validator(mode="after")
    def _square(self) -> Self:
        n = len(self.element_ids)
        if len(self.values) != n:
            raise ValueError(f"fuzzy matrix has {len(self.values)} rows for {n} elements")
        checked: list[tuple[float | None, ...]] = []
        for r, row in enumerate(self.values):
            if len(row) != n:
                raise ValueError(f"fuzzy matrix row {r} has {len(row)} cells for {n} elements")
            cells: list[float | None] = []
            for s, raw in enumerate(row):
                value = _check_finite(raw, f"values[{r}][{s}]")
                if r == s:
                    if value is not None:
                        raise ValueError(f"values[{r}][{r}] is the diagonal and must be None")
                elif value is None:
                    raise ValueError(f"values[{r}][{s}] is missing; a fuzzy matrix is complete")
                elif not 0.0 <= value <= 1.0:
                    raise ValueError(f"values[{r}][{s}] = {value!r} is outside [0, 1]")
                cells.append(value)
            checked.append(tuple(cells))
        object.__setattr__(self, "values", tuple(checked))
        return self

    @classmethod
    def from_square(
        cls,
        element_ids: Sequence[str],
        rows: Sequence[Sequence[float | None]],
        source: FuzzySource,
        rules: Sequence[str],
    ) -> FuzzyMatrix:
        """Build from a full square table, ignoring whatever its diagonal holds.

        SOMECS's clipboard format carries a diagonal (1 in the help's example, p. 25) and
        the certification material's tables a dash (p. 9); neither is a relation.
        """
        n = len(element_ids)
        if len(rows) != n or any(len(row) != n for row in rows):
            raise FuzzyMatrixError(f"a fuzzy matrix over {n} elements needs {n} rows of {n}")
        return cls(
            element_ids=tuple(element_ids),
            values=tuple(
                tuple(None if r == s else cell for s, cell in enumerate(row))
                for r, row in enumerate(rows)
            ),
            source=source,
            rules=tuple(rules),
        )

    @property
    def size(self) -> int:
        return len(self.element_ids)

    def relation(self, row: int, column: int) -> float:
        """The relation of element ``row`` to element ``column`` (off-diagonal only)."""
        value = self.values[row][column]
        if value is None:
            raise FuzzyMatrixError("the diagonal of a fuzzy matrix is not a relation")
        return value

    def is_symmetric(self) -> bool:
        return all(
            self.values[r][s] == self.values[s][r]
            for r in range(self.size)
            for s in range(r + 1, self.size)
        )

    def permuted(self, order: Sequence[int]) -> FuzzyMatrix:
        """The same matrix with its elements in ``order`` (a relabelling, nothing else)."""
        if sorted(order) != list(range(self.size)):
            raise FuzzyMatrixError("order must be a permutation of the element positions")
        return FuzzyMatrix.from_square(
            [self.element_ids[i] for i in order],
            [[self.values[i][j] for j in order] for i in order],
            self.source,
            self.rules,
        )

    def fingerprint(self) -> str:
        """Stable SHA256 of the element order, every cell, the source and the lineage."""
        return fingerprint(self.model_dump(mode="json"))


class NormalisedStorm(_Frozen):
    """Respondents x objects answers on ``[0, 1]``, with how they got there.

    ``None`` is an unanswered cell, possible only under ``KEEP_EMPTY``. ``scale`` is the
    question's scale when, and only when, the transform is ``RTS_SCALE``.
    """

    subject_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    transform: StormTransform
    missing_policy: StormMissingPolicy
    scale: tuple[float, float] | None
    product: Product
    rules: tuple[str, ...]
    ratings_fingerprint: str

    @field_validator("subject_ids")
    @classmethod
    def _subjects(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=1, what="subject")

    @field_validator("object_ids")
    @classmethod
    def _objects(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=MIN_FUZZY_ELEMENTS, what="object")

    @field_validator("rules")
    @classmethod
    def _rule_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _rules(v)

    @field_validator("values", mode="before")
    @classmethod
    def _no_booleans(cls, v: Any) -> Any:
        return _reject_booleans(v, "values")

    @model_validator(mode="after")
    def _contract(self) -> Self:
        n, m = len(self.subject_ids), len(self.object_ids)
        if len(self.values) != n:
            raise ValueError(f"answers have {len(self.values)} rows for {n} subjects")
        keep_empty = self.missing_policy is StormMissingPolicy.KEEP_EMPTY
        checked: list[tuple[float | None, ...]] = []
        for i, row in enumerate(self.values):
            if len(row) != m:
                raise ValueError(f"answers row {i} has {len(row)} cells for {m} objects")
            cells: list[float | None] = []
            for j, raw in enumerate(row):
                value = _check_finite(raw, f"values[{i}][{j}]")
                if value is None and not keep_empty:
                    raise ValueError(f"values[{i}][{j}] is empty under {self.missing_policy}")
                if value is not None and not 0.0 <= value <= 1.0:
                    raise ValueError(f"values[{i}][{j}] = {value!r} is outside [0, 1]")
                cells.append(value)
            checked.append(tuple(cells))
        object.__setattr__(self, "values", tuple(checked))
        is_rts = self.transform is StormTransform.RTS_SCALE
        if (self.scale is not None) != is_rts:
            raise ValueError("a scale is recorded with, and only with, the RTS scale transform")
        if self.scale is not None:
            _check_scale(self.scale)
        expected = Product.RTS if is_rts else Product.SOMECS
        if self.product is not expected:
            raise ValueError(
                f"transform {self.transform} belongs to {expected}, not {self.product}"
            )
        if self.missing_policy is StormMissingPolicy.SOMECS_ZERO and is_rts:
            raise ValueError("the SOMECS zero fill is not an RTS rule")
        return self

    def is_complete(self) -> bool:
        return all(cell is not None for row in self.values for cell in row)


class ObjectCorrelations(_Frozen):
    """Signed Pearson correlations between object answer columns (RTS-O1).

    ``r[a][b]`` is in ``[-1, 1]``, or ``None`` when undefined because an object's answers
    are all equal; ``undefined`` names each such pair and why. ``support`` is the number of
    respondents behind every pair (RTS data are complete, so it is the same for all).
    Support is recorded, not judged: adequacy is an open policy (M14).
    """

    object_ids: tuple[str, ...]
    r: tuple[tuple[float | None, ...], ...]
    undefined: tuple[tuple[str, str, str], ...]
    support: int
    rules: tuple[str, ...]
    answers_fingerprint: str

    @field_validator("object_ids")
    @classmethod
    def _objects(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _check_ids(v, minimum=MIN_FUZZY_ELEMENTS, what="object")

    @field_validator("rules")
    @classmethod
    def _rule_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return _rules(v)

    @model_validator(mode="after")
    def _contract(self) -> Self:
        n = len(self.object_ids)
        if len(self.r) != n or any(len(row) != n for row in self.r):
            raise ValueError(f"correlations over {n} objects need {n} rows of {n}")
        if self.support < 2:
            raise ValueError("a correlation needs at least two respondents")
        for a in range(n):
            if self.r[a][a] is not None:
                raise ValueError("the diagonal of a correlation matrix is not stored")
            for b in range(n):
                value = self.r[a][b]
                if value != self.r[b][a]:
                    raise ValueError("a correlation matrix is symmetric")
                if value is not None and not (math.isfinite(value) and -1.0 <= value <= 1.0):
                    raise ValueError(f"r[{a}][{b}] = {value!r} is outside [-1, 1]")
        named = {(a, b) for a, b, _ in self.undefined}
        missing = {
            (self.object_ids[a], self.object_ids[b])
            for a in range(n)
            for b in range(a + 1, n)
            if self.r[a][b] is None
        }
        if named != missing:
            raise ValueError("every undefined pair, and only those, is named in `undefined`")
        return self

    def negative_pairs(self) -> tuple[tuple[str, str, float], ...]:
        n = len(self.object_ids)
        return tuple(
            (self.object_ids[a], self.object_ids[b], value)
            for a in range(n)
            for b in range(a + 1, n)
            if (value := self.r[a][b]) is not None and value < 0.0
        )


class WeightedMeanFuzzy(_Frozen):
    """A weighted mean of compatible matrices, with its inputs and what was not checked.

    SOMECS aggregation (SOMECS-A1) is this mean after a discrepancy check (SOMECS-A2) whose
    measure is undocumented; ``discrepancy_check`` says it was not performed and why.
    """

    mean: FuzzyMatrix
    input_fingerprints: tuple[str, ...]
    input_sources: tuple[FuzzySource, ...]
    weights: tuple[float, ...]
    normalised_weights: tuple[float, ...]
    discrepancy_check: Literal["NOT_PERFORMED"]
    discrepancy_reason: str


# --------------------------------------------------------------------- RTS --


def rts_people_matrix(
    element_ids: Sequence[str],
    ratings: Sequence[Sequence[float | None]],
    scale: tuple[float, float],
) -> FuzzyMatrix:
    """An RTS people question as a fuzzy matrix (RTS-P1, RTS-N1).

    Row ``r`` holds what person ``r`` gave, column ``s`` what person ``s`` received
    (certification material p. 9; RTS designs doc p. 18). Each rating maps by the
    question's scale, ``(x - low) / (high - low)`` (RTS-N1; linear form inferred). Every
    off-diagonal rating is required, as RTS requires every answer; one off the scale is
    refused, never clipped. The diagonal is ignored.
    """
    _check_scale(scale)
    n = len(element_ids)
    if len(ratings) != n or any(len(row) != n for row in ratings):
        raise FuzzyMatrixError(f"ratings among {n} people need {n} rows of {n}")
    rows = [
        [
            None if r == s else _on_scale(cell, scale, f"rating [{r}][{s}]")
            for s, cell in enumerate(row)
        ]
        for r, row in enumerate(ratings)
    ]
    return FuzzyMatrix.from_square(element_ids, rows, FuzzySource.RTS_PEOPLE, ("RTS-P1", "RTS-N1"))


def rts_scale_answers(ratings: RatingsMatrix, scale: tuple[float, float]) -> NormalisedStorm:
    """RTS object answers on ``[0, 1]`` by the question's scale points (RTS-N1).

    An unanswered cell stays empty: RTS itself never has one, so what consumes these
    answers decides, and the correlation refuses (M5).
    """
    _check_scale(scale)
    values = tuple(
        tuple(
            None if cell is None else _on_scale(cell, scale, f"rating [{i}][{j}]")
            for j, cell in enumerate(row)
        )
        for i, row in enumerate(ratings.values)
    )
    return NormalisedStorm(
        subject_ids=ratings.respondent_ids,
        object_ids=ratings.object_ids,
        values=values,
        transform=StormTransform.RTS_SCALE,
        missing_policy=StormMissingPolicy.KEEP_EMPTY,
        scale=scale,
        product=Product.RTS,
        rules=("RTS-N1",),
        ratings_fingerprint=ratings.fingerprint(),
    )


def rts_object_correlations(answers: NormalisedStorm) -> ObjectCorrelations:
    """Pearson correlations between object answer columns, signed (RTS-O1).

    Only RTS-scaled answers are accepted: a SOMECS row transform before correlating is
    undocumented and changes r. Every answer is required (M5). An object whose answers are
    all equal has no correlation with anything: its pairs are ``None`` and named. Equality
    is decided on the answers themselves, before any arithmetic: the floating-point mean of
    a repeated fraction such as 1/9 need not equal it, and centring on that mean leaves
    residues near 1e-17 whose correlation with another such column is +-1, not undefined.
    Sums use ``math.fsum``. Rounding that lands ``|r|`` a hair above 1 is pulled back to 1.
    """
    if answers.transform is not StormTransform.RTS_SCALE:
        raise MethodologyUndetermined(
            "M1", f"correlating answers after {answers.transform} is not a documented pipeline"
        )
    for i, row in enumerate(answers.values):
        for j, cell in enumerate(row):
            if cell is None:
                raise MethodologyUndetermined(
                    "M5",
                    f"respondent {answers.subject_ids[i]!r} did not answer "
                    f"{answers.object_ids[j]!r}; RTS data are complete",
                )
    n_subjects, n_objects = len(answers.subject_ids), len(answers.object_ids)
    if n_subjects < 2:
        raise FuzzyMatrixError("a correlation needs at least two respondents")
    centred: list[list[float] | None] = []
    norms: list[float] = []
    for j in range(n_objects):
        column = [_cast_float(answers.values[i][j]) for i in range(n_subjects)]
        if len(set(column)) == 1:
            centred.append(None)
            norms.append(0.0)
            continue
        mean = math.fsum(column) / n_subjects
        deviations = [x - mean for x in column]
        centred.append(deviations)
        norms.append(math.sqrt(math.fsum(d * d for d in deviations)))
    rows: list[list[float | None]] = [[None] * n_objects for _ in range(n_objects)]
    undefined: list[tuple[str, str, str]] = []
    ids = answers.object_ids
    for a in range(n_objects):
        for b in range(a + 1, n_objects):
            ca, cb = centred[a], centred[b]
            if ca is None or cb is None:
                constant = [ids[k] for k, c in ((a, ca), (b, cb)) if c is None]
                undefined.append((ids[a], ids[b], "every answer equal for " + ", ".join(constant)))
                continue
            dot = math.fsum(x * y for x, y in zip(ca, cb, strict=True))
            r = max(-1.0, min(1.0, dot / (norms[a] * norms[b])))
            rows[a][b] = rows[b][a] = r
    return ObjectCorrelations(
        object_ids=ids,
        r=tuple(tuple(row) for row in rows),
        undefined=tuple(undefined),
        support=n_subjects,
        rules=(*answers.rules, "RTS-O1"),
        answers_fingerprint=fingerprint(answers.model_dump(mode="json")),
    )


def rts_fuzzy_from_correlations(correlations: ObjectCorrelations) -> FuzzyMatrix:
    """The RTS object relation matrix: the correlations as they are, for ``r >= 0`` (RTS-O2).

    The documented example (RTS designs doc p. 19) holds only positive correlations and
    puts them into the relation matrix unchanged. An undefined pair is refused, naming it;
    a negative one is refused, naming it, because no source says how RTS places it on
    ``[0, 1]`` (M12). The signed matrix stays available to the caller.
    """
    if correlations.undefined:
        a, b, why = correlations.undefined[0]
        raise FuzzyMatrixError(f"{a!r} and {b!r} have no correlation ({why})")
    negatives = correlations.negative_pairs()
    if negatives:
        listed = "; ".join(f"{a}/{b} r={r:.4f}" for a, b, r in negatives)
        raise MethodologyUndetermined(
            "M12", f"negative correlations have no documented place on [0, 1]: {listed}"
        )
    return FuzzyMatrix.from_square(
        correlations.object_ids,
        [list(row) for row in correlations.r],
        FuzzySource.RTS_OBJECT_CORRELATION,
        (*correlations.rules, "RTS-O2"),
    )


# ------------------------------------------------------------------ SOMECS --


def somecs_transform_storm(
    ratings: RatingsMatrix, transform: StormTransform, missing_policy: StormMissingPolicy
) -> NormalisedStorm:
    """A documented SOMECS transform of STORM data (SOMECS-D1..D3; help p. 22, p. 14).

    ``SOMECS_WITHIN_ROW``: each subject's answers to ``0-1``, ``(x - min) / (max - min)``
    (linear form inferred); a subject who rated everything equally gets ``0.5`` everywhere
    (documented). ``SOMECS_WITHIN_DATABASE``: the database's highest value to ``1`` and
    lowest to ``0`` (documented), linearly between (inferred). SOMECS fills an empty field
    with ``0`` first (``SOMECS_ZERO``). Both transforms are documented for complete data:
    under ``KEEP_EMPTY`` a row with an empty cell is refused (M5), not transformed over its
    answered cells. The ordinal transform and a database of equal values are refused (M1).
    """
    transform = StormTransform(transform)
    missing_policy = StormMissingPolicy(missing_policy)
    if transform is StormTransform.SOMECS_ORDINAL:
        raise MethodologyUndetermined(
            "M1", "the ordinal transform's rank direction, ties and scale are not documented"
        )
    if transform not in _SOMECS_TRANSFORMS:
        raise FuzzyMatrixError(f"{transform} is not a SOMECS transform")
    fill = missing_policy is StormMissingPolicy.SOMECS_ZERO
    rows: list[list[float]] = []
    for i, row in enumerate(ratings.values):
        filled: list[float] = []
        for j, cell in enumerate(row):
            if cell is None and not fill:
                raise MethodologyUndetermined(
                    "M5",
                    f"respondent {ratings.respondent_ids[i]!r} left {ratings.object_ids[j]!r} "
                    "empty; SOMECS transforms are documented for complete data",
                )
            filled.append(0.0 if cell is None else cell)
        rows.append(filled)
    if transform is StormTransform.SOMECS_WITHIN_ROW:
        out = [_minmax(row, min(row), max(row)) for row in rows]
        rules = ("SOMECS-D2",)
    else:
        low = min(cell for row in rows for cell in row)
        high = max(cell for row in rows for cell in row)
        if low == high:
            raise MethodologyUndetermined(
                "M1", "the database transform of a database whose answers are all equal"
            )
        out = [_minmax(row, low, high) for row in rows]
        rules = ("SOMECS-D3",)
    return NormalisedStorm(
        subject_ids=ratings.respondent_ids,
        object_ids=ratings.object_ids,
        values=tuple(tuple(row) for row in out),
        transform=transform,
        missing_policy=missing_policy,
        scale=None,
        product=Product.SOMECS,
        rules=(("SOMECS-D1",) if fill else ()) + rules,
        ratings_fingerprint=ratings.fingerprint(),
    )


def weighted_mean_fuzzy(
    matrices: Sequence[FuzzyMatrix], weights: Sequence[float]
) -> WeightedMeanFuzzy:
    """``sum_k w_k M_k / sum_k w_k`` over compatible matrices, with full provenance.

    Compatible means the same elements, by name and in the same order (SOMECS help p. 31).
    A weight of ``0`` leaves a matrix out, as in SOMECS; weights are kept as given and as
    normalised. SOMECS's discrepancy gate is not applied (M11), and the record says so.
    """
    if not matrices:
        raise FuzzyMatrixError("a weighted mean needs at least one matrix")
    if len(weights) != len(matrices):
        raise FuzzyMatrixError(f"{len(weights)} weights for {len(matrices)} matrices")
    clean: list[float] = []
    for k, weight in enumerate(weights):
        if isinstance(weight, bool):
            raise FuzzyMatrixError(f"weight {k} must be a number, not a boolean")
        value = float(weight)
        if not math.isfinite(value) or value < 0.0:
            raise FuzzyMatrixError(f"weight {k} = {weight!r} must be finite and not negative")
        clean.append(value)
    total = sum(clean)
    if total <= 0.0:
        raise FuzzyMatrixError("every weight is 0; nothing to average")
    ids = matrices[0].element_ids
    for k, matrix in enumerate(matrices[1:], start=1):
        if matrix.element_ids != ids:
            raise FuzzyMatrixError(f"matrix {k} needs the same elements in the same order")
    n = len(ids)
    rows = [
        [
            None
            if r == s
            else sum(w * m.relation(r, s) for w, m in zip(clean, matrices, strict=True)) / total
            for s in range(n)
        ]
        for r in range(n)
    ]
    lineage = tuple(dict.fromkeys(rule for m in matrices for rule in m.rules))
    return WeightedMeanFuzzy(
        mean=FuzzyMatrix.from_square(ids, rows, FuzzySource.WEIGHTED_MEAN, (*lineage, "SOMECS-A1")),
        input_fingerprints=tuple(m.fingerprint() for m in matrices),
        input_sources=tuple(m.source for m in matrices),
        weights=tuple(clean),
        normalised_weights=tuple(w / total for w in clean),
        discrepancy_check="NOT_PERFORMED",
        discrepancy_reason="SOMECS's discrepancy measure is undocumented (M11)",
    )


# -------------------------------------------------------------- legacy AIA --


def legacy_fuzzy_from_relation_1_10(
    element_ids: Sequence[str], matrix: Sequence[Sequence[float | None]]
) -> FuzzyMatrix:
    """AIA's legacy directed 1-10 relation as a fuzzy matrix: ``(r - 1) / 9`` (LEGACY-R1).

    The exact inverse of the similarity branch of ``coerce_relation_scale_1_10`` (F1). Not
    an RTS or SOMECS rule. A cell off ``[1, 10]`` or missing is refused, never clipped.
    """
    n = len(element_ids)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise FuzzyMatrixError(f"a relation matrix over {n} elements needs {n} rows of {n}")
    rows = [
        [
            None if r == s else _on_scale(cell, _RELATION_SCALE, f"relation [{r}][{s}]")
            for s, cell in enumerate(row)
        ]
        for r, row in enumerate(matrix)
    ]
    return FuzzyMatrix.from_square(
        element_ids, rows, FuzzySource.LEGACY_RELATION_1_10, ("LEGACY-R1",)
    )


# ----------------------------------------------------------------- helpers --


def _cast_float(value: float | None) -> float:
    if value is None:  # pragma: no cover - callers refuse empty cells first
        raise FuzzyMatrixError("an empty cell reached a computation that needs every value")
    return value


def _check_scale(scale: tuple[float, float]) -> None:
    if len(scale) != 2:
        raise FuzzyMatrixError(f"a scale is (low, high); got {scale!r}")
    low, high = scale
    if (
        isinstance(low, bool)
        or isinstance(high, bool)
        or not (math.isfinite(low) and math.isfinite(high))
        or high <= low
    ):
        raise FuzzyMatrixError(f"scale {scale!r} must run from a lower to a higher finite value")


def _on_scale(cell: float | None, scale: tuple[float, float], where: str) -> float:
    _check_scale(scale)
    low, high = scale
    if cell is None or isinstance(cell, bool):
        raise FuzzyMatrixError(f"{where} is missing or not a number")
    value = float(cell)
    if not low <= value <= high:
        raise FuzzyMatrixError(f"{where} = {value!r} is outside the scale [{low:g}, {high:g}]")
    return (value - low) / (high - low)


def _minmax(row: Sequence[float], low: float, high: float) -> list[float]:
    if high == low:
        return [_EQUAL_ROW_VALUE for _ in row]
    return [(cell - low) / (high - low) for cell in row]
