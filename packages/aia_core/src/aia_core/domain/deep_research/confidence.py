"""Confidence, by code: a finding's confidence from what code established, by versioned weights.

Plan ``deep-research-web-search.md`` § 8.6, chunk 13. A confidence is computed, never
self-reported. Its inputs are what earlier rules decided about one accepted finding:

* the **tier** of its source (:mod:`.sources`, lowered by :mod:`.reputation`);
* its **provenance** (:mod:`.tracing`): primary, secondary traced to a captured
  primary, secondary, or undetermined;
* the number of **independent confirmation groups** (:mod:`.triangulation`, one per
  group other than its own, as :func:`~.verification.independent_confirmations` counts);
* the independent **verifier's verdict** (:mod:`.verifier`);
* whether it is **superseded** (:mod:`.verification`);
* the worst **conflict** it stands in (:mod:`.triangulation`);
* the **recency** of its periods against the date its source was read;
* the **basis** of its figures (actual, preliminary, estimate, forecast, unstated);
* the **completeness** of its measures: the share of a measure's seven attributes
  (unit, period, geography, population, denominator, name, basis) it states.

The model's own ratings are not inputs. :class:`ConfidenceInputs` has no field an
agent wrote -- ``agent_source_quality`` stays on the evidence item, recorded, and
decides nothing; the synthesizer's contract has no confidence to give.

**The rule** is a clamped sum of one term per input, each read from a table of
:class:`ConfidenceWeights` (:func:`confidence`). Each table is ordered from the worst
level of its input to the best, and :class:`ConfidenceWeights` refuses a table whose
weights fall along that order, so the confidence is monotone in every input by
construction: a better input never lowers it. *Unknown is never scored as good*
(CLAUDE.md § 8): an undetermined provenance weighs what a secondary one does, an
unplaceable period what a stale one does, an unstated basis what a preliminary one
does, and a claim with no number earns no completeness.

**The weights are a proposal** (:data:`CONFIDENCE_WEIGHTS_V1`, status ``proposed``),
to be approved with the tiers and the register (plan chunk 1). They are data: a change
is a new version, and the version travels with every confidence computed under it.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from enum import StrEnum
from itertools import pairwise
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import EvidenceItem, Measure, MeasureBasis, SourceKind
from .reputation import RegisterStatus, ReputationRegister
from .sources import SourceClass, SourceTable, SourceTier, tier_of, web_tier
from .tracing import PrimaryStatus, TraceRecord
from .triangulation import Conflict, ConflictStatus, period_span
from .verifier import ClaimVerdict

__all__ = [
    "BASIS_ORDER",
    "CONFIDENCE_RULES_VERSION",
    "CONFIDENCE_WEIGHTS_V1",
    "CONFIDENCE_WEIGHTS_VERSION",
    "CONFLICT_ORDER",
    "MEASURE_ATTRIBUTES",
    "PROVENANCE_ORDER",
    "RECENCY_ORDER",
    "TIER_ORDER",
    "VERDICT_ORDER",
    "BasisLevel",
    "ConfidenceBand",
    "ConfidenceInputs",
    "ConfidenceRecord",
    "ConfidenceWeights",
    "ConflictState",
    "Provenance",
    "Recency",
    "confidence",
    "confidence_inputs",
    "evidence_tier",
]

#: The rule of this module: the inputs, their orders and the clamped sum.
CONFIDENCE_RULES_VERSION: Final = "aia-dr-confidence-1"
#: The proposed weights' version; approving them is a new version, set by a person.
CONFIDENCE_WEIGHTS_VERSION: Final = "aia-dr-confidence-weights-1 (proposed)"

#: The attributes of a measure whose statement counts toward completeness.
MEASURE_ATTRIBUTES: Final[tuple[str, ...]] = (
    "unit",
    "period",
    "geography",
    "population",
    "denominator",
    "measure_name",
    "basis",
)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Provenance(StrEnum):
    """Where a finding's number comes from, as tracing established it."""

    #: Code could not tell. Weighs no more than secondary: unknown is not good.
    UNDETERMINED = "undetermined"
    #: Repeated by someone other than its publisher, and not traced.
    SECONDARY = "secondary"
    #: Secondary, and the same figure was captured from its publisher too.
    TRACED = "traced"
    #: Captured from the publisher of the number.
    PRIMARY = "primary"


class ConflictState(StrEnum):
    """The worst conflict a finding stands in (:class:`~.triangulation.ConflictStatus`)."""

    #: Nothing explains the difference yet; a resolve track is requested.
    OPEN = "open"
    #: A resolve track ran and nothing explains it.
    UNRESOLVED = "unresolved"
    #: The measures explain it (a definition, basis or period difference).
    EXPLAINED = "explained"
    #: A resolve track's primary sources explained it.
    RESOLVED = "resolved"
    #: The finding conflicts with nothing captured.
    NONE = "none"


class Recency(StrEnum):
    """How recent a finding's periods are against the date its source was read."""

    #: A period code cannot place, or no period at all. Weighs what stale does.
    UNKNOWN = "unknown"
    STALE = "stale"
    LAGGING = "lagging"
    CURRENT = "current"


class BasisLevel(StrEnum):
    """The least final basis among a finding's figures."""

    FORECAST = "forecast"
    ESTIMATE = "estimate"
    PRELIMINARY = "preliminary"
    #: Not stated, or no figure. Weighs what preliminary does: unknown is not final.
    UNSTATED = "unstated"
    ACTUAL = "actual"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#: Each input's levels from the worst to the best. A table's weights may not fall along it.
TIER_ORDER: Final[tuple[SourceTier, ...]] = (
    SourceTier.EXCLUDED,
    SourceTier.T5,
    SourceTier.T4,
    SourceTier.T3,
    SourceTier.T2,
    SourceTier.T1,
)
PROVENANCE_ORDER: Final[tuple[Provenance, ...]] = tuple(Provenance)
CONFLICT_ORDER: Final[tuple[ConflictState, ...]] = tuple(ConflictState)
RECENCY_ORDER: Final[tuple[Recency, ...]] = tuple(Recency)
BASIS_ORDER: Final[tuple[BasisLevel, ...]] = tuple(BasisLevel)
#: ``None`` is "no verdict" (unverified); only ``supported`` is ever accepted.
VERDICT_ORDER: Final[tuple[ClaimVerdict | None, ...]] = (
    None,
    ClaimVerdict.UNSUPPORTED,
    ClaimVerdict.OVERSTATED,
    ClaimVerdict.SUPERSEDED,
    ClaimVerdict.SUPPORTED,
)

_UNVERIFIED: Final = "unverified"


def _verdict_key(verdict: ClaimVerdict | None) -> str:
    return _UNVERIFIED if verdict is None else verdict.value


def _ordered[K](version: str, name: str, table: Mapping[K, float], order: Sequence[K]) -> None:
    """Refuse a table that weighs no level of its input, or falls along its order."""
    missing = [str(k) for k in order if k not in table]
    if missing:
        raise ValueError(f"weights {version}: {name} weighs no {missing}")
    if any(b < a for a, b in pairwise(table[k] for k in order)):
        raise ValueError(
            f"weights {version}: {name} falls along its order {[str(k) for k in order]}; "
            "a better input may never lower confidence"
        )


class ConfidenceWeights(_Closed):
    """The weights confidence is computed with: versioned data, monotone by construction."""

    version: str = Field(min_length=1)
    status: RegisterStatus
    #: Per web tier; ``CLIENT_KNOWLEDGE`` (a person approved it) is weighed on its own.
    tier: dict[SourceTier, float]
    provenance: dict[Provenance, float]
    #: Added per independent confirmation group, for at most ``confirmation_cap`` groups.
    per_confirmation: float = Field(ge=0.0)
    confirmation_cap: int = Field(ge=0)
    #: Keyed by the verdict's value, and ``unverified`` for none.
    verdict: dict[str, float]
    #: Subtracted from a superseded finding.
    superseded_penalty: float = Field(ge=0.0)
    conflict: dict[ConflictState, float]
    recency: dict[Recency, float]
    #: A period ending at most this many years before the source was read is current;
    #: at most ``lagging_years``, lagging; anything older, stale.
    current_years: int = Field(ge=0)
    lagging_years: int = Field(ge=0)
    basis: dict[BasisLevel, float]
    #: Times the share of attributes stated (the least complete measure's).
    completeness: float = Field(ge=0.0)
    #: The confidence never exceeds this: nothing code can see makes a finding certain.
    ceiling: float = Field(gt=0.0, le=1.0)
    #: At or above ``high`` is high; at or above ``medium``, medium; else low.
    high: float = Field(gt=0.0, le=1.0)
    medium: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _monotone(self) -> ConfidenceWeights:
        _ordered(self.version, "tier", self.tier, TIER_ORDER)
        _ordered(self.version, "provenance", self.provenance, PROVENANCE_ORDER)
        _ordered(self.version, "verdict", self.verdict, [_verdict_key(v) for v in VERDICT_ORDER])
        _ordered(self.version, "conflict", self.conflict, CONFLICT_ORDER)
        _ordered(self.version, "recency", self.recency, RECENCY_ORDER)
        _ordered(self.version, "basis", self.basis, BASIS_ORDER)
        if SourceTier.CLIENT_KNOWLEDGE not in self.tier:
            raise ValueError(f"weights {self.version}: tier weighs no CLIENT_KNOWLEDGE")
        if self.lagging_years < self.current_years:
            raise ValueError(f"weights {self.version}: lagging_years is below current_years")
        if not self.medium <= self.high <= self.ceiling:
            raise ValueError(f"weights {self.version}: bands need medium <= high <= ceiling")
        if self.status is RegisterStatus.APPROVED and "proposed" in self.version:
            raise ValueError(f"weights {self.version}: an approved table needs its own version")
        return self


#: The proposed weights (plan § 8.6; for the data owner's approval with the tiers).
CONFIDENCE_WEIGHTS_V1: Final = ConfidenceWeights(
    version=CONFIDENCE_WEIGHTS_VERSION,
    status=RegisterStatus.PROPOSED,
    tier={
        SourceTier.EXCLUDED: 0.0,
        SourceTier.T5: 0.10,
        SourceTier.T4: 0.22,
        SourceTier.T3: 0.30,
        SourceTier.T2: 0.38,
        SourceTier.T1: 0.45,
        SourceTier.CLIENT_KNOWLEDGE: 0.38,
    },
    provenance={
        Provenance.UNDETERMINED: 0.0,
        Provenance.SECONDARY: 0.0,
        Provenance.TRACED: 0.10,
        Provenance.PRIMARY: 0.15,
    },
    per_confirmation=0.08,
    confirmation_cap=2,
    verdict={
        _UNVERIFIED: 0.0,
        ClaimVerdict.UNSUPPORTED.value: 0.0,
        ClaimVerdict.OVERSTATED.value: 0.0,
        ClaimVerdict.SUPERSEDED.value: 0.0,
        ClaimVerdict.SUPPORTED.value: 0.12,
    },
    superseded_penalty=0.30,
    conflict={
        ConflictState.OPEN: -0.20,
        ConflictState.UNRESOLVED: -0.20,
        ConflictState.EXPLAINED: -0.05,
        ConflictState.RESOLVED: 0.0,
        ConflictState.NONE: 0.0,
    },
    recency={
        Recency.UNKNOWN: 0.0,
        Recency.STALE: 0.0,
        Recency.LAGGING: 0.04,
        Recency.CURRENT: 0.08,
    },
    current_years=1,
    lagging_years=3,
    basis={
        BasisLevel.FORECAST: -0.06,
        BasisLevel.ESTIMATE: -0.02,
        BasisLevel.PRELIMINARY: -0.02,
        BasisLevel.UNSTATED: -0.02,
        BasisLevel.ACTUAL: 0.03,
    },
    completeness=0.05,
    ceiling=0.98,
    high=0.8,
    medium=0.6,
)


class ConfidenceInputs(_Closed):
    """Everything a confidence depends on. No field here is anything an agent wrote."""

    tier: SourceTier
    provenance: Provenance
    confirmation_groups: int = Field(ge=0)
    verdict: ClaimVerdict | None
    superseded: bool
    conflict: ConflictState
    recency: Recency
    basis: BasisLevel
    #: The least complete measure's share of :data:`MEASURE_ATTRIBUTES` stated, or
    #: ``None`` when the claim states no number (and so earns no completeness).
    measure_completeness: float | None = Field(ge=0.0, le=1.0)


class ConfidenceRecord(_Closed):
    """One finding's confidence, every term of it, and the weights it was computed by."""

    evidence_id: str
    value: float = Field(ge=0.0, le=1.0)
    band: ConfidenceBand
    inputs: ConfidenceInputs
    #: Each input's contribution, by input name, before the clamp.
    terms: dict[str, float]
    weights_version: str
    rules_version: str


def confidence(
    evidence_id: str,
    inputs: ConfidenceInputs,
    weights: ConfidenceWeights = CONFIDENCE_WEIGHTS_V1,
) -> ConfidenceRecord:
    """The clamped sum of one term per input (module doc). Monotone in every input."""
    terms = {
        "tier": weights.tier[inputs.tier],
        "provenance": weights.provenance[inputs.provenance],
        "confirmations": weights.per_confirmation
        * min(inputs.confirmation_groups, weights.confirmation_cap),
        "verdict": weights.verdict[_verdict_key(inputs.verdict)],
        "superseded": -weights.superseded_penalty if inputs.superseded else 0.0,
        "conflict": weights.conflict[inputs.conflict],
        "recency": weights.recency[inputs.recency],
        "basis": weights.basis[inputs.basis],
        "completeness": weights.completeness * (inputs.measure_completeness or 0.0),
    }
    value = round(max(0.0, min(weights.ceiling, sum(terms.values()))), 3)
    band = (
        ConfidenceBand.HIGH
        if value >= weights.high
        else ConfidenceBand.MEDIUM
        if value >= weights.medium
        else ConfidenceBand.LOW
    )
    return ConfidenceRecord(
        evidence_id=evidence_id,
        value=value,
        band=band,
        inputs=inputs,
        terms={k: round(v, 6) for k, v in terms.items()},
        weights_version=weights.version,
        rules_version=CONFIDENCE_RULES_VERSION,
    )


# --------------------------------------------------------------------------- #
# Reading the inputs from what earlier rules decided
# --------------------------------------------------------------------------- #


def evidence_tier(
    item: EvidenceItem,
    *,
    source_class: str,
    table: SourceTable,
    register: ReputationRegister | None,
) -> SourceTier:
    """A finding's tier: Client Knowledge's own, else its page's (the register may lower it).

    ``source_class`` is the class the merge scored the source as; without a URL to
    read again, that class's tier stands.
    """
    if item.source_kind is SourceKind.CLIENT_KNOWLEDGE:
        return SourceTier.CLIENT_KNOWLEDGE
    if item.source_url is None:
        return tier_of(SourceClass(source_class))
    if register is not None:
        return register.tier_for_url(item.source_url, table)
    return web_tier(item.source_url, table)


def _provenance(trace: TraceRecord | None) -> Provenance:
    if trace is None:
        return Provenance.UNDETERMINED
    if trace.status is PrimaryStatus.PRIMARY:
        return Provenance.PRIMARY
    if trace.status is PrimaryStatus.SECONDARY:
        return Provenance.TRACED if trace.traced_to is not None else Provenance.SECONDARY
    return Provenance.UNDETERMINED


_CONFLICT_STATES: Final[dict[ConflictStatus, ConflictState]] = {
    ConflictStatus.OPEN: ConflictState.OPEN,
    ConflictStatus.UNRESOLVED: ConflictState.UNRESOLVED,
    ConflictStatus.EXPLAINED: ConflictState.EXPLAINED,
    ConflictStatus.RESOLVED: ConflictState.RESOLVED,
}


def _conflict(evidence_id: str, conflicts: Iterable[Conflict]) -> ConflictState:
    states = [
        _CONFLICT_STATES[c.status]
        for c in conflicts
        if any(s.evidence_id == evidence_id for s in c.sides)
    ]
    return min(states, key=CONFLICT_ORDER.index) if states else ConflictState.NONE


def _recency(measures: Sequence[Measure], read: date | None, weights: ConfidenceWeights) -> Recency:
    if not measures or read is None:
        return Recency.UNKNOWN
    levels = []
    for m in measures:
        span = period_span(m.period)
        if span is None:
            return Recency.UNKNOWN
        lag = read.year - span.end // 12
        levels.append(
            Recency.CURRENT
            if lag <= weights.current_years
            else Recency.LAGGING
            if lag <= weights.lagging_years
            else Recency.STALE
        )
    return min(levels, key=RECENCY_ORDER.index)


_BASIS: Final[dict[MeasureBasis, BasisLevel]] = {
    MeasureBasis.ACTUAL: BasisLevel.ACTUAL,
    MeasureBasis.PRELIMINARY: BasisLevel.PRELIMINARY,
    MeasureBasis.ESTIMATE: BasisLevel.ESTIMATE,
    MeasureBasis.FORECAST: BasisLevel.FORECAST,
}


def _basis(measures: Sequence[Measure]) -> BasisLevel:
    if not measures:
        return BasisLevel.UNSTATED
    levels = [_BASIS[m.basis] if m.basis is not None else BasisLevel.UNSTATED for m in measures]
    return min(levels, key=BASIS_ORDER.index)


def _completeness(measures: Sequence[Measure]) -> float | None:
    if not measures:
        return None
    shares = [
        sum(1 for a in MEASURE_ATTRIBUTES if getattr(m, a) is not None) / len(MEASURE_ATTRIBUTES)
        for m in measures
    ]
    return round(min(shares), 6)


def confidence_inputs(
    item: EvidenceItem,
    *,
    tier: SourceTier,
    trace: TraceRecord | None,
    confirmation_groups: int,
    verdict: ClaimVerdict | None,
    superseded: bool,
    conflicts: Iterable[Conflict],
    read: date | None,
    weights: ConfidenceWeights = CONFIDENCE_WEIGHTS_V1,
) -> ConfidenceInputs:
    """One finding's inputs, read from the records earlier rules wrote (module doc).

    ``read`` is the date its source was read (a snapshot's retrieval); ``None`` makes
    its recency unknown. Nothing here reads ``item.agent_source_quality``.
    """
    return ConfidenceInputs(
        tier=tier,
        provenance=_provenance(trace),
        confirmation_groups=confirmation_groups,
        verdict=verdict,
        superseded=superseded,
        conflict=_conflict(item.evidence_id, conflicts),
        recency=_recency(item.measures, read, weights),
        basis=_basis(item.measures),
        measure_completeness=_completeness(item.measures),
    )
