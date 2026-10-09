"""The pair evidence policy: two gates on the approved n basis (Q6, chunk 1d).

AIA's decision of 2026-10-09 (plan ``sociomap-formula-corrections`` § 4a, Q6 (b) + (c)):
a pair's state stays UNKNOWN / WEAK / RELIABLE, read on Kish's effective n under weights,
and beside it, never inside it, whether ``|r|`` reaches the practical floor of 0.10.
``aia-sociomap-3`` declares the policy; ``aia-sociomap-2``, pinned before it, reads and
recomputes exactly as it was stored.
"""

from __future__ import annotations

import math
import random

import pytest

from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    EFFECT_FLOOR_AIA_Q6,
    ObjectMapInputs,
    RatingItem,
    SociomapSpecV3,
    UnsupportedMethodology,
    compute_object_map,
    read_artifact,
    read_spec,
    require_supported,
    spec_payload,
)
from aia_core.domain.sociomap.models_v3 import ObjectRole
from aia_core.domain.sociomap.pairs import PairRelations, derive_pair_relations
from aia_core.domain.sociomap.relations import (
    PairStatus,
    fisher_interval,
    kish_effective_n,
    meets_effect_floor,
    pair_status,
)
from aia_core.domain.sociomap.specification import ObjectHeightMetric, PairEvidenceBasis

V2_FINGERPRINT_PREFIX = "3f1c0122"


def _panel(seed: int, n: int, m: int, loading: float) -> list[list[float | None]]:
    """1-10 ratings sharing one taste with ``loading``, plus a generosity habit and noise."""
    rng = random.Random(seed)
    rows: list[list[float | None]] = []
    for _ in range(n):
        g, f = rng.gauss(0.0, 1.2), rng.gauss(0.0, 1.0)
        rows.append(
            [
                float(min(10, max(1, round(5.5 + g + 2.0 * loading * f + rng.gauss(0, 1.5)))))
                for _ in range(m)
            ]
        )
    return rows


def _inputs(rows: list[list[float | None]], weights: list[float]) -> ObjectMapInputs:
    m = len(rows[0])
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{i}" for i in range(len(rows))),
        donor_ids=tuple(f"D{i}" for i in range(len(rows))),
        items=tuple(RatingItem(item_id=f"i{j}", scale_min=1.0, scale_max=10.0) for j in range(m)),
        values=tuple(tuple(r) for r in rows),
        weights=tuple(weights),
        object_ids=tuple(f"o{j}" for j in range(m)),
        object_items=tuple(f"i{j}" for j in range(m)),
        roles={f"o{j}": ObjectRole.PRIMARY.value for j in range(m)},
    )


# --------------------------------------------------------------- Kish's n --


def test_kish_n_is_the_count_under_equal_weights_and_less_under_unequal() -> None:
    assert kish_effective_n([1.0] * 40) == pytest.approx(40.0)
    assert kish_effective_n([2.5] * 40) == pytest.approx(40.0)
    unequal = [1.0] * 20 + [4.0] * 20
    assert kish_effective_n(unequal) == pytest.approx(100.0**2 / 340.0)
    assert kish_effective_n(unequal) < 40
    assert kish_effective_n([]) == 0.0


@pytest.mark.parametrize("bad", [[0.0, 1.0], [-1.0], [math.nan], [math.inf], [True]])
def test_kish_n_reads_positive_finite_weights_only(bad: list[float]) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        kish_effective_n(bad)


def test_the_interval_reads_a_real_n() -> None:
    whole = fisher_interval(0.3, 40, 0.95)
    fractional = fisher_interval(0.3, 29.4, 0.95)
    assert whole is not None and fractional is not None
    assert fractional[1] - fractional[0] > whole[1] - whole[0]
    assert pair_status(0.3, 29.4, 30, 0.95) is PairStatus.UNKNOWN  # below the floor


# ---------------------------------------------------------- the two gates --


def test_a_precisely_small_relation_is_reliable_and_below_the_floor() -> None:
    assert pair_status(0.09, 2000, 30, 0.95) is PairStatus.RELIABLE
    assert meets_effect_floor(0.09, EFFECT_FLOOR_AIA_Q6) is False


def test_a_large_uncertain_relation_meets_the_floor_and_stays_weak() -> None:
    assert pair_status(0.30, 30, 30, 0.95) is PairStatus.WEAK
    assert meets_effect_floor(-0.30, EFFECT_FLOOR_AIA_Q6) is True  # the floor reads |r|


def test_no_correlation_meets_no_floor() -> None:
    assert meets_effect_floor(None, 0.1) is None


@pytest.mark.parametrize("floor", [0.0, 1.0, -0.1, math.nan])
def test_an_effect_floor_lies_strictly_between_0_and_1(floor: float) -> None:
    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        meets_effect_floor(0.5, floor)


# ------------------------------------------------------- pair relations --


def test_under_unequal_weights_a_pair_with_enough_rows_can_lack_enough_evidence() -> None:
    rows = _panel(3, 40, 3, loading=0.8)
    weights = [1.0] * 20 + [6.0] * 20  # Kish n = 140^2 / 740 = 26.5 < 30
    count = derive_pair_relations(rows, weights, n_min=30, confidence=0.95)
    kish = derive_pair_relations(
        rows, weights, n_min=30, confidence=0.95, basis="kish_effective_n", effect_floor=0.1
    )
    assert count.n[0][1] == kish.n[0][1] == 40
    assert count.status[0][1] is not PairStatus.UNKNOWN
    assert kish.n_effective is not None
    assert kish.n_effective[0][1] == pytest.approx(140.0**2 / 740.0)
    assert kish.status[0][1] is PairStatus.UNKNOWN
    assert kish.evidence_n(0, 1) == kish.n_effective[0][1]
    assert count.evidence_n(0, 1) == 40
    assert count.r == kish.r  # the policy reads the estimate; it never changes it


def test_kish_n_widens_the_interval_it_reads() -> None:
    rows = _panel(5, 200, 3, loading=0.5)
    weights = [1.0 + 3.0 * (k % 2) for k in range(200)]
    count = derive_pair_relations(rows, weights, n_min=30, confidence=0.95)
    kish = derive_pair_relations(rows, weights, n_min=30, confidence=0.95, basis="kish_effective_n")
    a, b = count.interval[0][1], kish.interval[0][1]
    assert a is not None and b is not None
    assert b[1] - b[0] > a[1] - a[0]


def test_the_floor_is_recorded_beside_the_status_never_inside_it() -> None:
    rows = _panel(7, 120, 4, loading=0.6)
    plain = derive_pair_relations(rows, [1.0] * 120, n_min=30, confidence=0.95)
    gated = derive_pair_relations(
        rows, [1.0] * 120, n_min=30, confidence=0.95, basis="respondent_count", effect_floor=0.1
    )
    assert gated.status == plain.status
    assert gated.meets_effect_floor is not None
    for i in range(4):
        for j in range(4):
            r = gated.r[i][j]
            expected = None if i == j or r is None else abs(r) >= 0.1
            assert gated.meets_effect_floor[i][j] is expected


def test_a_resample_counts_the_people_it_drew_not_their_duplicates() -> None:
    rows = _panel(9, 60, 3, loading=0.7)
    weights = [1.0] * 60
    draws = [2] * 30 + [0] * 30  # thirty people, each drawn twice
    drawn = derive_pair_relations(
        rows,
        [k * w for k, w in zip(draws, weights, strict=True)],
        n_min=30,
        confidence=0.95,
        basis="kish_effective_n",
        design_weights=weights,
    )
    assert drawn.n_effective is not None
    assert drawn.n_effective[0][1] == pytest.approx(30.0)


def test_a_relation_stored_before_the_policy_reads_and_serialises_as_stored() -> None:
    rows = _panel(11, 50, 3, loading=0.5)
    plain = derive_pair_relations(rows, [1.0] * 50, n_min=30, confidence=0.95)
    body = plain.model_dump(mode="json")
    assert not {"basis", "n_effective", "effect_floor", "meets_effect_floor"} & set(body)
    assert PairRelations.model_validate(body) == plain


def test_the_policy_fields_travel_together() -> None:
    rows = _panel(13, 50, 3, loading=0.5)
    gated = derive_pair_relations(
        rows, [1.0] * 50, n_min=30, confidence=0.95, basis="kish_effective_n", effect_floor=0.1
    )
    body = gated.model_dump(mode="json")
    assert PairRelations.model_validate(body) == gated
    with pytest.raises(ValueError, match="exactly when the basis is Kish"):
        PairRelations.model_validate({**body, "basis": "respondent_count"})
    with pytest.raises(ValueError, match="exactly when a floor is declared"):
        PairRelations.model_validate({**body, "effect_floor": None})
    with pytest.raises(ValueError, match="unknown evidence basis"):
        derive_pair_relations(rows, [1.0] * 50, n_min=30, confidence=0.95, basis="kish")


# ------------------------------------------------------------ the presets --


def test_aia_sociomap_3_is_aia_sociomap_2_under_the_q5_to_q7_decisions() -> None:
    v3 = AIA_SOCIOMAP_V3
    assert v3.methodology_version == "aia-sociomap-3"
    assert v3.relation.basis == PairEvidenceBasis.KISH_EFFECTIVE_N
    assert v3.relation.effect_floor == EFFECT_FLOOR_AIA_Q6 == 0.10
    assert v3.relation.n_min == 30
    assert v3.scores.height == ObjectHeightMetric.MEAN_RATING_0_1  # Q7 (a) as the default
    same = {"ratings", "layout", "scores", "connectedness", "respondent_placement", "terrain"}
    for name in same:
        assert getattr(v3, name) == getattr(AIA_SOCIOMAP_V2, name), name
    require_supported(v3)
    assert read_spec(spec_payload(v3)) == v3


def test_aia_sociomap_2_keeps_its_pinned_fingerprint_and_stored_form() -> None:
    assert AIA_SOCIOMAP_V2.fingerprint().startswith(V2_FINGERPRINT_PREFIX)
    assert "effect_floor" not in spec_payload(AIA_SOCIOMAP_V2)["spec"]["relation"]


@pytest.mark.parametrize("floor", [0.0, 1.0, -0.2])
def test_a_spec_with_an_impossible_floor_is_refused_by_name(floor: float) -> None:
    spec = AIA_SOCIOMAP_V3.model_copy(
        update={"relation": AIA_SOCIOMAP_V3.relation.model_copy(update={"effect_floor": floor})}
    )
    with pytest.raises(UnsupportedMethodology) as exc:
        require_supported(spec)
    assert "relation.effect_floor" in str(exc.value)


def test_a_boolean_floor_does_not_read() -> None:
    body = spec_payload(AIA_SOCIOMAP_V3)
    body["spec"]["relation"]["effect_floor"] = True
    with pytest.raises(ValueError, match="not a boolean"):
        SociomapSpecV3.model_validate(body["spec"])


# ------------------------------------------------------------ the engine --


def test_the_v3_map_records_both_gates_and_the_v2_map_records_neither() -> None:
    rows = _panel(17, 160, 5, loading=0.7)
    weights = [1.0 + 2.0 * (k % 3) for k in range(160)]
    inputs = _inputs(rows, weights)
    v2 = compute_object_map(inputs, AIA_SOCIOMAP_V2, connectedness_interval=False)
    v3 = compute_object_map(inputs, AIA_SOCIOMAP_V3, connectedness_interval=False)
    assert v2.relations.basis is None and v2.relations.meets_effect_floor is None
    assert v3.relations.basis == "kish_effective_n"
    assert v3.relations.effect_floor == 0.10
    assert v3.relations.n_effective is not None and v3.relations.meets_effect_floor is not None
    assert v3.relations.r == v2.relations.r
    assert v3.relations.n_effective[0][1] < v3.relations.n[0][1]  # unequal weights
    assert "Kish effective n" in v3.support.weighting
    assert "not the weight" in v2.support.weighting  # the text v2 maps were stored with
    assert read_artifact(v3.to_payload()) == v3
    assert read_artifact(v2.to_payload()) == v2
    stored = v2.to_payload()["artifact"]["relations"]
    assert not {"basis", "n_effective", "effect_floor", "meets_effect_floor"} & set(stored)


def test_the_v3_map_with_a_connectedness_interval_computes() -> None:
    rows = _panel(19, 90, 4, loading=0.8)
    art = compute_object_map(
        _inputs(rows, [1.0] * 90), AIA_SOCIOMAP_V3, connectedness_interval=True
    )
    assert art.relations.basis == "kish_effective_n"
    assert art.relations.n_effective is not None
    # Equal weights: Kish's n is each pair's own count of valid raters, exactly.
    for i in range(4):
        for j in range(4):
            if i != j:
                assert art.relations.n_effective[i][j] == pytest.approx(art.relations.n[i][j])
