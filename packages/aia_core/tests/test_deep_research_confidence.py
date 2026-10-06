"""Confidence by code (plan ``deep-research-web-search.md`` § 8.6, chunk 13).

Monotone in every input, from versioned weights, and blind to anything an agent said
about its own finding. Fictional hosts (``*-dr.example``); nothing is sent anywhere.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.confidence import (
    BASIS_ORDER,
    CONFIDENCE_RULES_VERSION,
    CONFIDENCE_WEIGHTS_V1,
    CONFIDENCE_WEIGHTS_VERSION,
    CONFLICT_ORDER,
    PROVENANCE_ORDER,
    RECENCY_ORDER,
    TIER_ORDER,
    VERDICT_ORDER,
    BasisLevel,
    ConfidenceBand,
    ConfidenceInputs,
    ConfidenceWeights,
    ConflictState,
    Provenance,
    Recency,
    confidence,
    confidence_inputs,
    evidence_tier,
)
from aia_core.domain.deep_research.contracts import (
    Channel,
    EvidenceItem,
    EvidenceType,
    Measure,
    MeasureBasis,
    RecommendedUse,
    SourceKind,
    evidence_id,
)
from aia_core.domain.deep_research.reputation import (
    Publisher,
    RegisterStatus,
    ReputationRegister,
)
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1, SourceClass, SourceTier
from aia_core.domain.deep_research.tracing import PrimaryStatus, TraceRecord
from aia_core.domain.deep_research.triangulation import (
    Conflict,
    ConflictCause,
    ConflictSide,
    ConflictStatus,
)
from aia_core.domain.deep_research.verifier import ClaimVerdict
from aia_core.domain.residency import DataClass

READ = date(2026, 9, 27)
TABLE = SOURCE_TABLE_V1.extended(
    "test-confidence-table",
    {"stat-dr.example": SourceClass.OFFICIAL_STATISTICS, "zpravy-dr.example": SourceClass.MEDIA},
)
REGISTER = ReputationRegister(
    version="test-register-confidence",
    status=RegisterStatus.PROPOSED,
    publishers=(
        Publisher(
            "Zpravodaj DR",
            ("ZDR",),
            ("zpravy-dr.example",),
            SourceClass.MEDIA,
            SourceTier.T5,
        ),
    ),
)

#: Every input's levels in their declared order, worst first. Completeness is a share.
LEVELS: dict[str, Sequence[Any]] = {
    "tier": TIER_ORDER,
    "provenance": PROVENANCE_ORDER,
    "confirmation_groups": (0, 1, 2, 3, 4),
    "verdict": VERDICT_ORDER,
    "superseded": (True, False),
    "conflict": CONFLICT_ORDER,
    "recency": RECENCY_ORDER,
    "basis": BASIS_ORDER,
    "measure_completeness": (0.0, 1 / 7, 3 / 7, 5 / 7, 1.0),
}


def inputs(**fields: Any) -> ConfidenceInputs:
    defaults: dict[str, Any] = {
        "tier": SourceTier.T3,
        "provenance": Provenance.UNDETERMINED,
        "confirmation_groups": 0,
        "verdict": ClaimVerdict.SUPPORTED,
        "superseded": False,
        "conflict": ConflictState.NONE,
        "recency": Recency.LAGGING,
        "basis": BasisLevel.UNSTATED,
        "measure_completeness": 0.5,
    }
    return ConfidenceInputs(**{**defaults, **fields})


def value(**fields: Any) -> float:
    return confidence("EV-0000000000000001", inputs(**fields)).value


def item(
    url: str | None = "https://stat-dr.example/t",
    *,
    measures: Sequence[Measure] = (),
    quality: float = 0.5,
    kind: SourceKind = SourceKind.WEB_PAGE,
) -> EvidenceItem:
    claim = "Spotřeba vzrostla na 41 milionů litrů."
    return EvidenceItem.model_validate(
        {
            "evidence_id": evidence_id("f" * 64, "S1", claim, claim),
            "track_id": "DRT-W-q-000000000001",
            "subject_key": "q-000000000001",
            "channel": Channel.WEB,
            "source_kind": kind,
            "source_ref": "S1",
            "source_url": url,
            "source_title": "t",
            "claim": claim,
            "quote": claim,
            "quote_span": (0, len(claim)),
            "evidence_type": EvidenceType.OTHER,
            "source_date": None,
            "geography": "",
            "population": "",
            "topics": (),
            "data_class": DataClass.CLASS_C_INTERNAL,
            "agent_outcome_overlap": False,
            "agent_recommended_use": RecommendedUse.CONTEXT_ONLY,
            "agent_source_quality": quality,
            "measures": tuple(measures),
        }
    )


def trace(status: PrimaryStatus, traced_to: str | None = None) -> TraceRecord:
    return TraceRecord(
        evidence_id="EV-x",
        publisher="register:x",
        publisher_name="x",
        status=status,
        cited=(),
        traced_to=traced_to,
        lead_id=None,
        detail="",
    )


def conflict(a: str, b: str, status: ConflictStatus) -> Conflict:
    m = Measure(value=41, unit="l", scale=1_000_000, period="Y2025", geography="CZ")
    side = {"publisher": "p", "publisher_name": "p", "primary": True, "source_url": None}
    return Conflict(
        conflict_id=f"CNF-{a}{b}{status.value}",
        measure_name="spotřeba",
        unit="l",
        geography="CZ",
        sides=(
            ConflictSide(evidence_id=a, measure=m, **side),
            ConflictSide(evidence_id=b, measure=m.model_copy(update={"value": 38}), **side),
        ),
        difference=3e6,
        allowed=5e5,
        cause=ConflictCause.UNEXPLAINED,
        status=status,
        detail="",
    )


# --------------------------------------------------------------------------- #
# Monotone in every input
# --------------------------------------------------------------------------- #


def _grid_points(n: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [{k: rng.choice(list(v)) for k, v in LEVELS.items()} for _ in range(n)]


@pytest.mark.parametrize("name", list(LEVELS))
def test_confidence_never_falls_when_one_input_improves(name: str) -> None:
    # Property over the grid: 1,500 seeded points, each input stepped along its order
    # with every other input held fixed. A better input never lowers the confidence.
    for point in _grid_points(1500, seed=13):
        values = [value(**{**point, name: level}) for level in LEVELS[name]]
        assert values == sorted(values), (name, point, values)


def test_confidence_is_monotone_over_the_whole_grid_of_two_inputs() -> None:
    # Exhaustive over every pair of inputs, the rest at the middle of their orders.
    middle = {k: v[len(v) // 2] for k, v in LEVELS.items()}
    for a, b in itertools.combinations(LEVELS, 2):
        for la, lb in itertools.product(LEVELS[a], LEVELS[b]):
            here = value(**{**middle, a: la, b: lb})
            for na in LEVELS[a][list(LEVELS[a]).index(la) :]:
                assert value(**{**middle, a: na, b: lb}) >= here


@pytest.mark.parametrize(
    ("name", "worse", "better"),
    [
        ("tier", SourceTier.T4, SourceTier.T1),
        ("provenance", Provenance.SECONDARY, Provenance.PRIMARY),
        ("provenance", Provenance.SECONDARY, Provenance.TRACED),
        ("confirmation_groups", 0, 2),
        ("verdict", None, ClaimVerdict.SUPPORTED),
        ("superseded", True, False),
        ("conflict", ConflictState.OPEN, ConflictState.NONE),
        ("conflict", ConflictState.EXPLAINED, ConflictState.RESOLVED),
        ("recency", Recency.STALE, Recency.CURRENT),
        ("basis", BasisLevel.FORECAST, BasisLevel.ACTUAL),
        ("measure_completeness", 0.0, 1.0),
    ],
)
def test_each_input_moves_the_confidence(name: str, worse: Any, better: Any) -> None:
    base = {"tier": SourceTier.T4, "measure_completeness": 0.5}
    assert value(**{**base, name: better}) > value(**{**base, name: worse})


def test_unknown_is_never_scored_as_good() -> None:
    # Undetermined provenance, an unplaceable period, an unstated basis and a claim
    # with no number earn nothing their worst known level does not.
    assert value(provenance=Provenance.UNDETERMINED) == value(provenance=Provenance.SECONDARY)
    assert value(recency=Recency.UNKNOWN) == value(recency=Recency.STALE)
    assert value(basis=BasisLevel.UNSTATED) == value(basis=BasisLevel.PRELIMINARY)
    assert value(measure_completeness=None) == value(measure_completeness=0.0)


def test_confirmations_count_up_to_the_cap_and_no_further() -> None:
    cap = CONFIDENCE_WEIGHTS_V1.confirmation_cap
    assert value(confirmation_groups=cap) > value(confirmation_groups=cap - 1)
    assert value(confirmation_groups=cap + 5) == value(confirmation_groups=cap)


def test_confidence_is_clamped_and_banded() -> None:
    best = {k: v[-1] for k, v in LEVELS.items()}
    worst = {k: v[0] for k, v in LEVELS.items()}
    top, bottom = confidence("EV-a", inputs(**best)), confidence("EV-b", inputs(**worst))
    assert top.value == CONFIDENCE_WEIGHTS_V1.ceiling and top.band is ConfidenceBand.HIGH
    assert bottom.value == 0.0 and bottom.band is ConfidenceBand.LOW
    assert sum(top.terms.values()) > top.value  # the clamp, recorded with every term
    assert top.weights_version == CONFIDENCE_WEIGHTS_VERSION
    assert top.rules_version == CONFIDENCE_RULES_VERSION


def test_a_better_band_never_needs_a_lower_value() -> None:
    order = [ConfidenceBand.LOW, ConfidenceBand.MEDIUM, ConfidenceBand.HIGH]
    points = sorted(
        (confidence("EV-x", inputs(**p)) for p in _grid_points(500, seed=7)),
        key=lambda r: r.value,
    )
    bands = [order.index(r.band) for r in points]
    assert bands == sorted(bands)


# --------------------------------------------------------------------------- #
# The weights are versioned data, monotone by construction, and proposed
# --------------------------------------------------------------------------- #


def test_the_weights_are_proposed_and_versioned() -> None:
    w = CONFIDENCE_WEIGHTS_V1
    assert w.version == "aia-dr-confidence-weights-1 (proposed)"
    assert w.status is RegisterStatus.PROPOSED
    # Every term the rule adds comes from the table; nothing else.
    record = confidence("EV-x", inputs())
    assert set(record.terms) == {
        "tier",
        "provenance",
        "confirmations",
        "verdict",
        "superseded",
        "conflict",
        "recency",
        "basis",
        "completeness",
    }


@pytest.mark.parametrize(
    ("table", "change"),
    [
        ("tier", {SourceTier.T2: 0.5}),  # T2 above T1
        ("provenance", {Provenance.SECONDARY: 0.2}),  # secondary above traced
        ("conflict", {ConflictState.OPEN: 0.1}),  # an open conflict as a bonus
        ("recency", {Recency.UNKNOWN: 0.09}),  # unknown above current
        ("basis", {BasisLevel.FORECAST: 0.1}),  # a forecast above actual
    ],
)
def test_a_table_that_falls_along_its_order_is_refused(
    table: str, change: dict[Any, float]
) -> None:
    current = getattr(CONFIDENCE_WEIGHTS_V1, table)
    with pytest.raises(ValidationError, match="falls along its order"):
        CONFIDENCE_WEIGHTS_V1.model_validate(
            {
                **CONFIDENCE_WEIGHTS_V1.model_dump(),
                "version": "test-falling",
                table: {**current, **change},
            }
        )


def test_a_table_missing_a_level_or_approved_under_the_proposed_version_is_refused() -> None:
    dumped = CONFIDENCE_WEIGHTS_V1.model_dump()
    with pytest.raises(ValidationError, match="weighs no"):
        ConfidenceWeights.model_validate(
            {**dumped, "recency": {k: v for k, v in dumped["recency"].items() if k != "stale"}}
        )
    with pytest.raises(ValidationError, match="needs its own version"):
        ConfidenceWeights.model_validate({**dumped, "status": RegisterStatus.APPROVED})


def test_other_weights_give_other_values_under_their_own_version() -> None:
    louder = ConfidenceWeights.model_validate(
        {
            **CONFIDENCE_WEIGHTS_V1.model_dump(),
            "version": "test-weights-2",
            "per_confirmation": 0.2,
        }
    )
    a = confidence("EV-x", inputs(confirmation_groups=1))
    b = confidence("EV-x", inputs(confirmation_groups=1), louder)
    assert b.value > a.value and b.weights_version == "test-weights-2"


# --------------------------------------------------------------------------- #
# The inputs come from code's records; the model's self-rating decides nothing
# --------------------------------------------------------------------------- #


def _inputs_of(evidence: EvidenceItem, **fields: Any) -> ConfidenceInputs:
    defaults: dict[str, Any] = {
        "tier": SourceTier.T1,
        "trace": trace(PrimaryStatus.PRIMARY),
        "confirmation_groups": 1,
        "verdict": ClaimVerdict.SUPPORTED,
        "superseded": False,
        "conflicts": (),
        "read": READ,
    }
    return confidence_inputs(evidence, **{**defaults, **fields})


@pytest.mark.parametrize("quality", [0.0, 0.3, 0.55, 0.9, 1.0])
def test_the_agent_s_own_source_quality_changes_nothing(quality: float) -> None:
    measures = [Measure(value=41, unit="l", scale=1_000_000, period="Y2025", geography="CZ")]
    baseline = confidence("EV-x", _inputs_of(item(measures=measures, quality=0.5)))
    rated = confidence("EV-x", _inputs_of(item(measures=measures, quality=quality)))
    assert rated == baseline
    # No input field could carry it: nothing an agent wrote is an input.
    assert not {"source_quality", "agent_source_quality", "confidence", "quality"} & set(
        ConfidenceInputs.model_fields
    )


def test_provenance_is_read_from_the_trace() -> None:
    e = item()
    assert _inputs_of(e, trace=None).provenance is Provenance.UNDETERMINED
    assert _inputs_of(e, trace=trace(PrimaryStatus.PRIMARY)).provenance is Provenance.PRIMARY
    assert _inputs_of(e, trace=trace(PrimaryStatus.SECONDARY)).provenance is Provenance.SECONDARY
    assert (
        _inputs_of(e, trace=trace(PrimaryStatus.SECONDARY, "EV-y")).provenance is Provenance.TRACED
    )
    assert (
        _inputs_of(e, trace=trace(PrimaryStatus.UNDETERMINED)).provenance is Provenance.UNDETERMINED
    )


def test_the_worst_conflict_a_finding_stands_in_is_its_input() -> None:
    e = item()
    me = e.evidence_id
    assert _inputs_of(e).conflict is ConflictState.NONE
    explained = conflict(me, "EV-b", ConflictStatus.EXPLAINED)
    opened = conflict("EV-c", me, ConflictStatus.OPEN)
    elsewhere = conflict("EV-d", "EV-e", ConflictStatus.OPEN)
    assert _inputs_of(e, conflicts=[explained]).conflict is ConflictState.EXPLAINED
    assert _inputs_of(e, conflicts=[explained, opened]).conflict is ConflictState.OPEN
    assert _inputs_of(e, conflicts=[elsewhere]).conflict is ConflictState.NONE


@pytest.mark.parametrize(
    ("periods", "read", "expected"),
    [
        (["Y2025"], READ, Recency.CURRENT),
        (["2024/25"], READ, Recency.CURRENT),
        (["Y2023"], READ, Recency.LAGGING),
        (["Y2019"], READ, Recency.STALE),
        (["Y2025", "Y2019"], READ, Recency.STALE),  # the worst of its figures
        (["Q2"], READ, Recency.UNKNOWN),  # cannot be placed
        ([None], READ, Recency.UNKNOWN),
        (["Y2025"], None, Recency.UNKNOWN),  # the source's reading date unknown
        ([], READ, Recency.UNKNOWN),  # no figure
    ],
)
def test_recency_is_each_period_against_the_day_its_source_was_read(
    periods: list[str | None], read: date | None, expected: Recency
) -> None:
    measures = [Measure(value=float(i + 1), period=p) for i, p in enumerate(periods)]
    assert _inputs_of(item(measures=measures), read=read).recency is expected


def test_basis_and_completeness_are_read_from_the_measures() -> None:
    full = Measure(
        value=41,
        unit="l",
        scale=1_000_000,
        period="Y2025",
        geography="CZ",
        population="HOUSEHOLDS",
        denominator="PERSON",
        measure_name="spotřeba",
        basis=MeasureBasis.ACTUAL,
    )
    bare = Measure(value=12.5, unit="%")
    got = _inputs_of(item(measures=[full]))
    assert (got.basis, got.measure_completeness) == (BasisLevel.ACTUAL, 1.0)
    got = _inputs_of(item(measures=[full, bare]))
    assert got.basis is BasisLevel.UNSTATED and got.measure_completeness == round(1 / 7, 6)
    forecast = full.model_copy(update={"basis": MeasureBasis.FORECAST})
    assert _inputs_of(item(measures=[full, forecast])).basis is BasisLevel.FORECAST
    got = _inputs_of(item(measures=[]))
    assert (got.basis, got.measure_completeness) == (BasisLevel.UNSTATED, None)


def test_a_finding_s_tier_is_its_page_s_and_the_register_may_only_lower_it() -> None:
    official = item("https://stat-dr.example/t")
    media = item("https://zpravy-dr.example/a")
    unknown = item("https://neznamy-dr.example/a")
    knowledge = item(None, kind=SourceKind.CLIENT_KNOWLEDGE)

    def tier(e: EvidenceItem, register: ReputationRegister | None = None) -> SourceTier:
        return evidence_tier(e, source_class="UNKNOWN", table=TABLE, register=register)

    assert tier(official) is SourceTier.T1
    assert tier(media) is SourceTier.T4
    assert tier(media, REGISTER) is SourceTier.T5  # the register lowers it
    assert tier(unknown) is SourceTier.T5  # unknown never above T5
    assert tier(knowledge) is SourceTier.CLIENT_KNOWLEDGE
    assert (
        evidence_tier(item(None), source_class="OFFICIAL_STATISTICS", table=TABLE, register=None)
        is SourceTier.T1
    )
