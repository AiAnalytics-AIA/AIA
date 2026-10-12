"""18.6.6's evidence derivation: respondent values for a materialized dimension (P4b).

A port of ``audience_dimensions.materialize_evidence_dimension`` and ``_predictor_score``
(``legacy/npc-panel-18.6.6/app/audience_dimensions.py:283-345``), EXACT against fixtures the
unit's own function produced (``tools/materialize_capture.py``,
``tests/fixtures/materialize_dimension/``; owner, P4 M2). Every value it writes is a
model's, never a measurement (``ClaimBasis.MODELED``).

The rule, as the unit has it:

* every row is scored: the mean, over the usable predictors that vary, of
  ``direction * strength * z`` (``z`` the predictor's population z-score, a missing value 0),
  plus ``0.35 * (u - 0.5)``, ``u`` a deterministic hash of the row id salted with the
  dimension id, so no two rows tie;
* **binary**: rows in descending score are set to 1 until the weighted share reaches the
  target prevalence (the row that crosses it included);
* **scale 1-10**: ``1 + 9 * percentile rank``, shifted so the mean is the target, clipped to
  [1, 10] and rounded to two decimals; the clip can leave the mean off target, and
  ``achieved`` says by how much.

The arithmetic follows NumPy and pandas, not Python's defaults, where the result depends on
it: sums are NumPy's pairwise summation (:func:`_pairwise_sum`), the standard deviation is
pandas' two-pass ``nanvar`` (missing values left out), rounding is ``rint(x * 100) / 100``.

**One named deviation (AIA refuses where the unit materialized noise).** When no usable
predictor varies, the unit's score is the hash noise alone, and it writes values that carry
nothing about the respondents (fixture M06). :func:`derive_dimension` refuses that
(``no_varying_predictor``); :func:`derive_dimension_as_unit` keeps the unit's behaviour for
the parity tests only.

Nothing here performs I/O.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .materialized import MaterializedKind

__all__ = [
    "DERIVATION_METHOD_ID",
    "DERIVATION_METHOD_VERSION",
    "DerivationRefused",
    "DerivedDimension",
    "EvidencePredictor",
    "EvidenceSpec",
    "derive_dimension",
    "derive_dimension_as_unit",
    "numeric_column",
    "sanitize_dimension_id",
]

DERIVATION_METHOD_ID: Final = "npc-18.6.6-evidence-overlay"
DERIVATION_METHOD_VERSION: Final = "1"

_NEGATIVE: Final = frozenset({"negative", "-", "inverse"})
_NOISE_SCALE: Final = 0.35
_PW_BLOCKSIZE: Final = 128


class DerivationRefused(ValueError):
    """A dimension cannot be derived; ``reason`` names why (the unit's message in ``str``)."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class EvidencePredictor:
    """One existing numeric field that orders respondents (the unit's predictor row)."""

    column: str
    negative: bool = False
    #: The unit's ``strength`` or ``weight``; 0 or absent reads as 1 there, so here too.
    strength: float = 1.0


@dataclass(frozen=True, slots=True)
class EvidenceSpec:
    """What the evidence supplies: a kind, a population target and its predictors."""

    kind: MaterializedKind
    #: A prevalence in (0, 1) for BINARY (a value above 1 is read as a percentage, as the
    #: unit reads it), a mean in [1, 10] for SCALE_1_10.
    target: float
    predictors: tuple[EvidencePredictor, ...]


@dataclass(frozen=True, slots=True)
class DerivedDimension:
    """The values, one per row in row order, and what they achieved."""

    dimension_id: str
    kind: MaterializedKind
    values: tuple[float, ...]
    target: float
    achieved: float
    #: The predictors that were usable (present and numeric), in the spec's order.
    usable: tuple[EvidencePredictor, ...]


def sanitize_dimension_id(dimension_id: str) -> str:
    """The unit's id: lowercase, every run of other characters one underscore, trimmed."""
    return re.sub(r"[^a-z0-9_]+", "_", str(dimension_id or "").lower()).strip("_")


def numeric_column(cells: Sequence[str | None]) -> list[float | None] | None:
    """A text column as the unit's pandas read it: numbers when every present cell is one.

    ``None`` for a column with a cell that is not a number: pandas types it as text, and the
    unit's derivation cannot use it (``no_usable_predictor``). A missing cell stays ``None``.
    """
    values: list[float | None] = []
    for cell in cells:
        if cell is None:
            values.append(None)
            continue
        try:
            values.append(float(cell))
        except ValueError:
            return None
    return values


def _pairwise_sum(values: Sequence[float]) -> float:
    """NumPy's pairwise summation of a contiguous float64 array, bit for bit.

    ``numpy/core/src/umath/loops_utils.h.src`` ``pairwise_sum``: fewer than 8 values are
    added in order; up to the block size, eight running sums advance in steps of eight and
    are combined as ``((r0+r1)+(r2+r3))+((r4+r5)+(r6+r7))``, the tail added in order; a
    longer array is split at half its length rounded down to a multiple of eight.
    """
    n = len(values)
    if n < 8:
        total = 0.0
        for v in values:
            total += v
        return total
    if n <= _PW_BLOCKSIZE:
        r = [values[i] for i in range(8)]
        i = 8
        while i < n - (n % 8):
            for j in range(8):
                r[j] += values[i + j]
            i += 8
        total = (r[0] + r[1] + (r[2] + r[3])) + (r[4] + r[5] + (r[6] + r[7]))
        while i < n:
            total += values[i]
            i += 1
        return total
    half = n // 2
    half -= half % 8
    return _pairwise_sum(values[:half]) + _pairwise_sum(values[half:])


def _noise(row_id: str, salt: str) -> float:
    digest = hashlib.sha256((salt + "|" + row_id).encode()).digest()
    return (int.from_bytes(digest[:8], "big") + 0.5) / (2**64)


def _zscores(column: Sequence[float | None]) -> list[float] | None:
    """Pandas' ``(x - x.mean()) / x.std(ddof=0)``, missing values filled with 0 after.

    ``None`` when the spread is not finite or at most 1e-12: the unit skips that predictor.
    """
    present = [v for v in column if v is not None]
    count = len(present)
    if count == 0:
        return None
    filled = [0.0 if v is None else v for v in column]
    mean = _pairwise_sum(filled) / count
    squares = [0.0 if v is None else (mean - v) ** 2 for v in column]
    variance = _pairwise_sum(squares) / count
    sd = math.sqrt(variance) if variance >= 0 else float("nan")
    if not math.isfinite(sd) or sd <= 1e-12:
        return None
    return [0.0 if v is None else (v - mean) / sd for v in column]


def _score(
    row_ids: Sequence[str],
    columns: Mapping[str, Sequence[float | None]],
    usable: Sequence[EvidencePredictor],
    salt: str,
) -> tuple[list[float], bool]:
    """Each row's score, and whether any predictor varied (the unit's ``_predictor_score``)."""
    parts: list[list[float]] = []
    for p in usable:
        z = _zscores(columns[p.column])
        if z is None:
            continue
        factor = (-1.0 if p.negative else 1.0) * (p.strength or 1.0)
        parts.append([factor * value for value in z])
    n = len(row_ids)
    if parts:
        base = []
        for i in range(n):
            total = parts[0][i]
            for part in parts[1:]:
                total += part[i]
            base.append(total / len(parts))
    else:
        base = [0.0] * n
    return (
        [base[i] + _NOISE_SCALE * (_noise(row_ids[i], salt) - 0.5) for i in range(n)],
        bool(parts),
    )


def _percentile_ranks(scores: Sequence[float]) -> list[float]:
    """Pandas' ``rank(method='average', pct=True)``: the mean 1-based position of ties / n."""
    n = len(scores)
    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        average = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return [r / n for r in ranks]


def _derive(
    row_ids: Sequence[str],
    columns: Mapping[str, Sequence[float | None]],
    weights: Sequence[float | None],
    *,
    dimension_id: str,
    spec: EvidenceSpec,
    refuse_noise: bool,
) -> DerivedDimension:
    did = sanitize_dimension_id(dimension_id)
    if not did:
        raise DerivationRefused("Chybí dimension_id.", reason="no_dimension_id")
    usable = tuple(p for p in spec.predictors if p.column in columns)
    if not usable:
        raise DerivationRefused(
            "Dosimulování vyžaduje alespoň jeden existující numerický/binary predictor z panelu.",
            reason="no_usable_predictor",
        )
    scores, varied = _score(row_ids, columns, usable, did)
    if refuse_noise and not varied:
        raise DerivationRefused(
            "No usable predictor varies across the population; the values would be noise.",
            reason="no_varying_predictor",
        )
    n = len(row_ids)
    if spec.kind is MaterializedKind.BINARY:
        prevalence = float(spec.target)
        if prevalence > 1:
            prevalence /= 100.0
        if not (0 < prevalence < 1):
            raise DerivationRefused(
                "target_prevalence musí být mezi 0 a 1 (nebo 0–100 %).",  # noqa: RUF001 - the unit's own text
                reason="prevalence_out_of_range",
            )
        w = [0.0 if v is None or math.isnan(v) else float(v) for v in weights]
        total = _pairwise_sum(w)
        # np.argsort(-score): descending; the hash noise leaves no ties to break.
        order = sorted(range(n), key=lambda i: -scores[i])
        target = prevalence * total
        cumulative = 0.0
        cut = n
        for position, i in enumerate(order):
            cumulative += w[i]
            if cumulative >= target:
                cut = position
                break
        chosen = set(order[: min(n, cut + 1)])
        values = tuple(1.0 if i in chosen else 0.0 for i in range(n))
        if total > 0:
            achieved = _pairwise_sum([w[i] * values[i] for i in range(n)]) / total
        else:
            achieved = _pairwise_sum(list(values)) / n
        return DerivedDimension(did, spec.kind, values, prevalence, achieved, usable)

    mean = float(spec.target)
    if not (1 <= mean <= 10):
        raise DerivationRefused(
            "target_mean pro scale_1_10 musí být 1–10.",  # noqa: RUF001 - the unit's own text
            reason="mean_out_of_range",
        )
    raw = [1 + 9 * r for r in _percentile_ranks(scores)]
    shift = mean - _pairwise_sum(raw) / n
    values = tuple(round(min(10.0, max(1.0, v + shift)) * 100) / 100 for v in raw)
    achieved = _pairwise_sum(list(values)) / n
    return DerivedDimension(did, spec.kind, values, mean, achieved, usable)


def derive_dimension(
    row_ids: Sequence[str],
    columns: Mapping[str, Sequence[float | None]],
    weights: Sequence[float | None],
    *,
    dimension_id: str,
    spec: EvidenceSpec,
) -> DerivedDimension:
    """Derive a dimension's values, one per row, in row order.

    ``columns`` holds the population's numeric fields (``None`` for a missing value); a
    predictor naming any other field is unusable, as a non-numeric column is to the unit.
    ``weights`` is the default weight column (a missing weight counts 0). Refused, by
    :class:`DerivationRefused`, wherever the unit raised, and where no usable predictor
    varies.
    """
    return _derive(
        row_ids, columns, weights, dimension_id=dimension_id, spec=spec, refuse_noise=True
    )


def derive_dimension_as_unit(
    row_ids: Sequence[str],
    columns: Mapping[str, Sequence[float | None]],
    weights: Sequence[float | None],
    *,
    dimension_id: str,
    spec: EvidenceSpec,
) -> DerivedDimension:
    """The unit's behaviour exactly, noise included: for the parity tests, never for a run."""
    return _derive(
        row_ids, columns, weights, dimension_id=dimension_id, spec=spec, refuse_noise=False
    )
