"""Evidence admission: the only way a number becomes a claim a result may carry.

The reference's analysis rule (methodology-ledger M17): "every number in a
client analysis must carry an evidence reference and a metric drawn from a fixed
set", values are copied exactly from the evidence, and external research is
context only. The reference states that in the system prompt, constrains it with
a JSON schema, and checks it with an evidence gate -- which lets 5% of numbers
through uncovered (``evidence_validator.py``: ``coverage >= 0.95``).

Here a model's numeric claim is untrusted input (:class:`NumericClaim`) until
:func:`admit_numeric_claims` has checked it against the deterministic
:class:`EvidenceTable` *and* through every governance gate -- field policy,
joint structure, support, interval, tier. Only then does it become an
:class:`AdmittedClaim`, which carries a module-private issuer sentinel and so
cannot be constructed anywhere else (``make layer_check`` enforces that no other
module even spells the constructor). A result type that accepts only
``AdmittedClaim`` therefore cannot contain an unchecked number, whatever the
prompt said.

Admission is all or nothing. A draft with one bad claim admits nothing; the
caller repairs or blocks. There is no coverage threshold.

External research cannot back a claim because it is not in the table: the table
holds only rows produced by deterministic aggregation of the population.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from ..pipeline import fingerprint
from .claims import (
    ClaimBasis,
    ClaimLevel,
    ClaimRequest,
    ClaimSurface,
    Disclosure,
    evaluate_claim,
)
from .field_policy import FieldPolicyBook
from .gate import GateDecision, Violation, ViolationCode, block, combine
from .joint_status import JointStatus
from .metrics import AnalysisMetric, MetricKind, MetricUnit, UnknownMetric, parse_metric
from .support import Interval, SupportAssessment, SupportStatus
from .validation import TierUseCase, evaluate_tier

__all__ = [
    "Admission",
    "AdmittedClaim",
    "EvidenceRow",
    "EvidenceTable",
    "NumericClaim",
    "admit_numeric_claims",
]

_COUNT_METRICS: Final = frozenset({MetricKind.N, MetricKind.EFFECTIVE_N})
_MAX_DECIMALS: Final = 6


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """One deterministic, citable number, with everything needed to decide a claim on it.

    ``value`` is the display value, already rounded to ``decimals``; a claim
    must copy it exactly. ``unit`` is derived from the metric, never supplied.
    """

    evidence_ref: str
    metric: AnalysisMetric
    value: float
    decimals: int
    support: SupportAssessment
    fields: tuple[str, ...]
    basis: ClaimBasis
    level: ClaimLevel
    cell: str
    question_id: str | None = None
    interval: Interval | None = None
    joint: bool = False
    disclosures: frozenset[Disclosure] = frozenset()
    weight_scheme: str | None = None
    use_case: TierUseCase | None = None
    dimension_tiers: Mapping[str, str | None] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.evidence_ref.strip():
            raise ValueError("an evidence row needs an evidence_ref")
        if not self.fields:
            raise ValueError(f"{self.evidence_ref}: an evidence row names the fields behind it")
        if not math.isfinite(self.value):
            raise ValueError(f"{self.evidence_ref}: value must be finite")
        if not 0 <= self.decimals <= _MAX_DECIMALS:
            raise ValueError(f"{self.evidence_ref}: decimals must be 0..{_MAX_DECIMALS}")
        if round(self.value, self.decimals) != self.value:
            raise ValueError(
                f"{self.evidence_ref}: value {self.value} is not rounded to {self.decimals} dp"
            )
        if self.interval is not None and not self.interval.contains(self.value):
            raise ValueError(f"{self.evidence_ref}: value lies outside its interval")
        if self.dimension_tiers and self.use_case is None:
            raise ValueError(f"{self.evidence_ref}: dimension tiers need the use case they back")
        object.__setattr__(self, "dimension_tiers", MappingProxyType(dict(self.dimension_tiers)))

    @property
    def unit(self) -> MetricUnit:
        return self.metric.unit

    @property
    def is_estimate(self) -> bool:
        """Counts are support; everything else is an estimate that needs an interval."""
        return self.metric.kind not in _COUNT_METRICS

    def canonical(self) -> dict[str, Any]:
        return {
            "evidence_ref": self.evidence_ref,
            "metric": str(self.metric),
            "value": self.value,
            "decimals": self.decimals,
            "support": self.support.status.value,
            "effective_n": self.support.effective_n,
            "fields": list(self.fields),
            "basis": self.basis.value,
            "level": self.level.value,
            "cell": self.cell,
            "question_id": self.question_id,
            "interval": None
            if self.interval is None
            else [self.interval.lower, self.interval.upper, self.interval.level],
            "joint": self.joint,
            "disclosures": sorted(d.value for d in self.disclosures),
            "weight_scheme": self.weight_scheme,
            "use_case": None if self.use_case is None else self.use_case.value,
            "dimension_tiers": dict(sorted(self.dimension_tiers.items())),
        }


@dataclass(frozen=True, slots=True)
class EvidenceTable:
    """The rows a module may cite. Suppressed rows are removed, keeping only why."""

    rows: Mapping[str, EvidenceRow]
    suppressed: Mapping[str, SupportAssessment]

    @classmethod
    def build(cls, rows: Iterable[EvidenceRow]) -> EvidenceTable:
        kept: dict[str, EvidenceRow] = {}
        removed: dict[str, SupportAssessment] = {}
        for row in rows:
            if row.evidence_ref in kept or row.evidence_ref in removed:
                raise ValueError(f"evidence_ref {row.evidence_ref!r} appears twice")
            if row.support.status is SupportStatus.SUPPRESS:
                removed[row.evidence_ref] = row.support
            else:
                kept[row.evidence_ref] = row
        return cls(MappingProxyType(kept), MappingProxyType(removed))

    def fingerprint(self) -> str:
        return fingerprint(
            {
                "rows": [self.rows[k].canonical() for k in sorted(self.rows)],
                "suppressed": sorted(self.suppressed),
            }
        )


@dataclass(frozen=True, slots=True)
class NumericClaim:
    """A number a model says it took from the evidence. Untrusted until admitted."""

    claim_id: str
    evidence_ref: str
    metric: str
    value: float
    unit: str


# Proves a claim was admitted by admit_numeric_claims. Module-private: a claim
# decoded from model output, a request body or a stored payload cannot carry it.
_ADMISSION_ISSUER: Final = object()


@dataclass(frozen=True, slots=True)
class AdmittedClaim:
    """A numeric claim that passed every gate, bound to the row that backs it."""

    claim_id: str
    row: EvidenceRow
    surface: ClaimSurface
    _issuer: Any

    def __post_init__(self) -> None:
        if self._issuer is not _ADMISSION_ISSUER:
            raise ValueError("claims are admitted only by admit_numeric_claims")

    @property
    def value(self) -> float:
        return self.row.value

    @property
    def indicative(self) -> bool:
        return self.row.support.status is SupportStatus.INDICATIVE


@dataclass(frozen=True, slots=True)
class Admission:
    decision: GateDecision
    admitted: tuple[AdmittedClaim, ...]


def _prefixed(claim_id: str, decision: GateDecision) -> GateDecision:
    return GateDecision(
        tuple(Violation(v.code, f"{claim_id}:{v.subject}", v.detail) for v in decision.violations)
    )


def _check_claim(
    claim: NumericClaim,
    table: EvidenceTable,
    book: FieldPolicyBook,
    joint_status: JointStatus,
    surface: ClaimSurface,
) -> GateDecision:
    cid = claim.claim_id
    if claim.evidence_ref in table.suppressed:
        reasons = "; ".join(table.suppressed[claim.evidence_ref].reasons)
        return block(ViolationCode.EVIDENCE_SUPPRESSED, cid, f"{claim.evidence_ref}: {reasons}")
    row = table.rows.get(claim.evidence_ref)
    if row is None:
        return block(
            ViolationCode.EVIDENCE_REF_UNKNOWN,
            cid,
            f"{claim.evidence_ref!r} is not in the evidence table",
        )

    decisions: list[GateDecision] = []
    try:
        metric = parse_metric(claim.metric)
    except UnknownMetric as exc:
        decisions.append(block(ViolationCode.METRIC_NOT_ALLOWED, cid, str(exc)))
    else:
        if metric != row.metric:
            decisions.append(
                block(ViolationCode.METRIC_MISMATCH, cid, f"{metric} cited, row is {row.metric}")
            )
    if claim.unit != row.unit.value:
        decisions.append(
            block(ViolationCode.UNIT_MISMATCH, cid, f"{claim.unit!r} cited, row is {row.unit}")
        )
    if not (math.isfinite(claim.value) and claim.value == row.value):
        decisions.append(
            block(ViolationCode.VALUE_MISMATCH, cid, f"{claim.value} cited, row is {row.value}")
        )
    if surface is ClaimSurface.CLIENT_FACING and row.is_estimate and row.interval is None:
        decisions.append(
            block(
                ViolationCode.INTERVAL_MISSING, cid, "a client-facing estimate needs its interval"
            )
        )

    request = ClaimRequest(
        fields=row.fields,
        basis=row.basis,
        surface=surface,
        level=row.level,
        joint=row.joint,
        disclosures=row.disclosures,
        weight_scheme=row.weight_scheme,
    )
    decisions.append(_prefixed(cid, evaluate_claim(request, book, joint_status)))
    if row.dimension_tiers:
        # A row with tiers always names its use case (EvidenceRow.__post_init__); an
        # empty use case would be refused by the tier gate rather than skipped.
        use_case = row.use_case.value if row.use_case is not None else ""
        decisions.append(_prefixed(cid, evaluate_tier(row.dimension_tiers, use_case)))
    return combine(decisions)


def admit_numeric_claims(
    claims: Sequence[NumericClaim],
    table: EvidenceTable,
    *,
    book: FieldPolicyBook,
    joint_status: JointStatus,
    surface: ClaimSurface,
) -> Admission:
    """Admit every claim or none. The decision lists every violation, per claim."""
    decisions: list[GateDecision] = []
    seen: set[str] = set()
    for claim in claims:
        if not claim.claim_id or claim.claim_id in seen:
            decisions.append(
                block(
                    ViolationCode.DUPLICATE_CLAIM_ID,
                    claim.claim_id or "<empty>",
                    "claim ids are unique",
                )
            )
            continue
        seen.add(claim.claim_id)
        decisions.append(_check_claim(claim, table, book, joint_status, surface))

    decision = combine(decisions)
    if not decision.allowed:
        return Admission(decision, ())
    return Admission(
        decision,
        tuple(
            AdmittedClaim(c.claim_id, table.rows[c.evidence_ref], surface, _ADMISSION_ISSUER)
            for c in claims
        ),
    )
