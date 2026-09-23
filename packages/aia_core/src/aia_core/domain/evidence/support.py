"""Effective-n support: a client-facing number needs support and an interval, or it is removed.

Methodology-ledger M16 (``dotaznik.agreguj_otazku``, ``uncertainty.py``,
``fidelity.evidence_rating``): aggregation is interval-first; a cell whose Kish
effective n falls below threshold is **removed**, not greyed out; and
``support_status`` **defaults to SUPPRESS**, so the gate fails closed. The rule
as stated: *a client-facing number is meaningful only together with its
interval and evidence context* (10.13).

Constants, all from the reference (:data:`REFERENCE_THRESHOLDS`):

=====================  =====  =========================================
``min_cell``           50     raw cell n below this is suppressed
``n_guard``            25.0   Kish effective n below this is suppressed
``indicative``         50.0   Kish effective n below this is indicative
``min_layer_donors``   25     unique donors behind a donor-layer value
=====================  =====  =========================================

The reference also compares the donor-layer count against 50
(``uncertainty.py:129``); this port reads that as the donor-layer indicative
line, mirroring the effective-n pair. It is a reading of a threshold, not of
recovered code, and is listed for the legacy-source parity run.

Three states, named here because the reference's non-default names are not
recoverable without the withheld source: ``SUPPRESS`` (the reference's own
default), ``INDICATIVE`` and ``REPORTABLE``. Parity is on the decision.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "REFERENCE_THRESHOLDS",
    "Interval",
    "ReportableEstimate",
    "SupportAssessment",
    "SupportEvidence",
    "SupportStatus",
    "SupportThresholds",
    "Suppression",
    "UnsupportedEstimate",
    "assess_support",
    "kish_effective_n",
    "suppress_cells",
    "top2box_pct",
    "weighted_mean",
    "weighted_share_pct",
]


class UnsupportedEstimate(ValueError):
    """A number was about to be reported without the support or interval it needs."""


class SupportStatus(StrEnum):
    SUPPRESS = "SUPPRESS"
    INDICATIVE = "INDICATIVE"
    REPORTABLE = "REPORTABLE"


@dataclass(frozen=True, slots=True)
class SupportThresholds:
    min_cell: int
    n_guard: float
    indicative: float
    min_layer_donors: int
    indicative_layer_donors: int


REFERENCE_THRESHOLDS: Final = SupportThresholds(
    min_cell=50,
    n_guard=25.0,
    indicative=50.0,
    min_layer_donors=25,
    indicative_layer_donors=50,
)


@dataclass(frozen=True, slots=True)
class SupportEvidence:
    """What is known about the support behind one cell. ``None`` means unknown."""

    n: int | None
    effective_n: float | None
    requires_donor_support: bool = False
    n_unique_layer_donors: int | None = None


# Proves an assessment came from assess_support. SUPPRESS needs no proof -- it is the
# fail-closed default anyone may state -- but INDICATIVE and REPORTABLE do: a status
# that lets a number reach a client must have been computed from support evidence,
# never written by hand or decoded from a payload.
_SUPPORT_ISSUER: Final = object()


@dataclass(frozen=True, slots=True)
class SupportAssessment:
    """A support decision and every reason for it. The default is SUPPRESS.

    Only :func:`assess_support` can produce an INDICATIVE or REPORTABLE assessment.
    """

    status: SupportStatus = SupportStatus.SUPPRESS
    reasons: tuple[str, ...] = ("no support evidence",)
    effective_n: float | None = None
    _issuer: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.status is not SupportStatus.SUPPRESS and self._issuer is not _SUPPORT_ISSUER:
            raise UnsupportedEstimate(
                f"a {self.status} assessment is issued only by assess_support, "
                "from support evidence"
            )

    @property
    def reportable(self) -> bool:
        return self.status is not SupportStatus.SUPPRESS


def assess_support(
    evidence: SupportEvidence, thresholds: SupportThresholds = REFERENCE_THRESHOLDS
) -> SupportAssessment:
    """Decide a cell's support. Unknown, inconsistent or thin support suppresses."""
    n, eff = evidence.n, evidence.effective_n
    if n is None or eff is None or not math.isfinite(eff) or eff < 0 or n < 0:
        return SupportAssessment(reasons=("support unknown: n or effective n missing",))
    if eff > n + 1e-9:
        return SupportAssessment(
            reasons=(f"effective n {eff:g} exceeds n {n}: inconsistent support",), effective_n=eff
        )

    suppress: list[str] = []
    indicative: list[str] = []
    if n < thresholds.min_cell:
        suppress.append(f"n {n} < min_cell {thresholds.min_cell}")
    if eff < thresholds.n_guard:
        suppress.append(f"effective n {eff:g} < {thresholds.n_guard:g}")
    elif eff < thresholds.indicative:
        indicative.append(f"effective n {eff:g} < {thresholds.indicative:g}")

    if evidence.requires_donor_support:
        donors = evidence.n_unique_layer_donors
        if donors is None or donors < 0:
            suppress.append("donor-layer support unknown")
        elif donors < thresholds.min_layer_donors:
            suppress.append(f"{donors} unique layer donors < {thresholds.min_layer_donors}")
        elif donors < thresholds.indicative_layer_donors:
            indicative.append(
                f"{donors} unique layer donors < {thresholds.indicative_layer_donors}"
            )

    if suppress:
        return SupportAssessment(SupportStatus.SUPPRESS, tuple(suppress), eff)
    if indicative:
        return SupportAssessment(
            SupportStatus.INDICATIVE, tuple(indicative), eff, _issuer=_SUPPORT_ISSUER
        )
    return SupportAssessment(SupportStatus.REPORTABLE, (), eff, _issuer=_SUPPORT_ISSUER)


@dataclass(frozen=True, slots=True)
class Suppression:
    """Cells split into those kept (with their assessment) and those removed."""

    kept: Mapping[str, SupportAssessment]
    removed: Mapping[str, SupportAssessment]


def suppress_cells(
    cells: Mapping[str, SupportEvidence], thresholds: SupportThresholds = REFERENCE_THRESHOLDS
) -> Suppression:
    """Remove every suppressed cell. Removed cells keep only their id and reasons."""
    kept: dict[str, SupportAssessment] = {}
    removed: dict[str, SupportAssessment] = {}
    for cell_id, evidence in cells.items():
        assessment = assess_support(evidence, thresholds)
        (kept if assessment.reportable else removed)[cell_id] = assessment
    return Suppression(kept, removed)


@dataclass(frozen=True, slots=True)
class Interval:
    lower: float
    upper: float
    level: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) for x in (self.lower, self.upper, self.level)):
            raise UnsupportedEstimate("an interval must be finite")
        if self.lower > self.upper:
            raise UnsupportedEstimate(f"interval lower {self.lower} > upper {self.upper}")
        if not 0 < self.level < 1:
            raise UnsupportedEstimate(f"interval level {self.level} is not in (0, 1)")

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


@dataclass(frozen=True, slots=True)
class ReportableEstimate:
    """A number that may reach a client: finite, inside its interval, and supported.

    There is no way to build one without an interval, and no way to build one
    from a suppressed cell.
    """

    value: float
    interval: Interval
    support: SupportAssessment

    def __post_init__(self) -> None:
        if not isinstance(self.interval, Interval):
            raise UnsupportedEstimate("a client-facing number requires its interval")
        if not math.isfinite(self.value):
            raise UnsupportedEstimate("a client-facing number must be finite")
        if not self.interval.contains(self.value):
            raise UnsupportedEstimate(
                f"{self.value} lies outside its interval [{self.interval.lower}, "
                f"{self.interval.upper}]"
            )
        if not self.support.reportable:
            raise UnsupportedEstimate(
                "a suppressed cell cannot be reported: " + "; ".join(self.support.reasons)
            )


# --- deterministic estimators ----------------------------------------------------------


def _pairs(values: Sequence[float | None], weights: Sequence[float]) -> list[tuple[float, float]]:
    if len(values) != len(weights):
        raise ValueError(f"{len(values)} values but {len(weights)} weights")
    for w in weights:
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"weight {w!r} is not a finite non-negative number")
    return [(v, w) for v, w in zip(values, weights, strict=True) if v is not None]


def kish_effective_n(weights: Iterable[float]) -> float:
    """Kish effective sample size, ``(sum w)^2 / sum w^2`` (M06, M16).

    Refuses negative, non-finite or all-zero weights rather than cleaning them:
    by the time weights reach analysis they must already be the declared scheme.
    """
    ws = list(weights)
    for w in ws:
        if not math.isfinite(w) or w < 0:
            raise ValueError(f"weight {w!r} is not a finite non-negative number")
    total = math.fsum(ws)
    if total <= 0:
        raise ValueError("effective n of an empty or all-zero weight vector is undefined")
    return total * total / math.fsum(w * w for w in ws)


def weighted_mean(values: Sequence[float | None], weights: Sequence[float]) -> float | None:
    """Weighted mean over answered cases; None when nothing carries weight."""
    pairs = _pairs(values, weights)
    total = math.fsum(w for _, w in pairs)
    if total <= 0:
        return None
    return math.fsum(v * w for v, w in pairs) / total


def weighted_share_pct(flags: Sequence[bool | None], weights: Sequence[float]) -> float | None:
    """Weighted percentage of answered cases where the flag holds; None when unanswered."""
    as_float = [None if f is None else (1.0 if f else 0.0) for f in flags]
    mean = weighted_mean(as_float, weights)
    return None if mean is None else 100.0 * mean


def top2box_pct(
    values: Sequence[float | None], weights: Sequence[float], *, scale_max: int
) -> float | None:
    """Weighted percentage in the top two points of a ``1..scale_max`` scale."""
    if scale_max < 2:
        raise ValueError(f"a top-two box needs a scale of at least 2 points, got {scale_max}")
    for v in values:
        if v is not None and not 1 <= v <= scale_max:
            raise ValueError(f"answer {v} is outside the 1..{scale_max} scale")
    flags = [None if v is None else v >= scale_max - 1 for v in values]
    return weighted_share_pct(flags, weights)
