"""Alignment and connectedness over PRIMARY objects (audit F8, plan chunk 1b).

The audit "NPC Sociomapa: faulty formulas in the code" replaces the classic
score sum_j (s_ij + s_ji) with two scores over the PRIMARY objects, read from the
signed correlation and the pair's status (F3):

    A_i = mean of r_ij,   K_i = mean of |r_ij|,   over i's known PRIMARY pairs.

UNKNOWN pairs are out of the sums and the denominator (AIA's reading, register
AUDIT-F8); an object with no known pair is unscored; SECONDARY objects are never
read.
"""

from __future__ import annotations

import random

import pytest

from aia_core.domain.sociomap.metrics import (
    AUDIT_PROVISIONAL_DEFAULT_HEIGHT,
    PRIMARY_SCORE_RULE,
    ObjectMetric,
    ObjectRole,
    alignment,
    connectedness,
    primary_scores,
    relation_classic,
)
from aia_core.domain.sociomap.relations import PairStatus

P = ObjectRole.PRIMARY
S = ObjectRole.SECONDARY
R = PairStatus.RELIABLE
W = PairStatus.WEAK
U = PairStatus.UNKNOWN


def _matrices(
    ids: list[str], pairs: dict[tuple[str, str], tuple[float | None, PairStatus]]
) -> tuple[list[list[float | None]], list[list[PairStatus | None]]]:
    """Symmetric r and status matrices over ``ids``; every off-diagonal pair given."""
    m = len(ids)
    r: list[list[float | None]] = [[None] * m for _ in range(m)]
    status: list[list[PairStatus | None]] = [[None] * m for _ in range(m)]
    for (a, b), (value, st) in pairs.items():
        i, j = ids.index(a), ids.index(b)
        r[i][j] = r[j][i] = value
        status[i][j] = status[j][i] = st
    return r, status


def _strength(r: list[list[float | None]]) -> list[list[float]]:
    """The unit's 1-10 strength of each pair (``1 + 9 (r + 1) / 2``), diagonal 0."""
    m = len(r)
    return [
        [0.0 if i == j else 1.0 + 9.0 * ((float(r[i][j] or 0.0)) + 1.0) / 2.0 for j in range(m)]
        for i in range(m)
    ]


IDS = ["a", "b", "c", "d"]
HAND: dict[tuple[str, str], tuple[float | None, PairStatus]] = {
    ("a", "b"): (0.6, R),
    ("a", "c"): (-0.2, W),
    ("a", "d"): (0.4, R),
    ("b", "c"): (0.1, W),
    ("b", "d"): (-0.5, R),
    ("c", "d"): (0.3, R),
}


def test_the_scores_are_the_audits_formula_on_a_hand_computed_example() -> None:
    r, status = _matrices(IDS, HAND)
    result = primary_scores(IDS, r, status, dict.fromkeys(IDS, P))
    # a: (0.6 - 0.2 + 0.4) / 3, (0.6 + 0.2 + 0.4) / 3
    # b: (0.6 + 0.1 - 0.5) / 3, (0.6 + 0.1 + 0.5) / 3
    # c: (-0.2 + 0.1 + 0.3) / 3, (0.2 + 0.1 + 0.3) / 3
    # d: (0.4 - 0.5 + 0.3) / 3, (0.4 + 0.5 + 0.3) / 3
    expected_a = {"a": 0.8 / 3, "b": 0.2 / 3, "c": 0.2 / 3, "d": 0.2 / 3}
    expected_k = {"a": 0.4, "b": 0.4, "c": 0.2, "d": 0.4}
    assert result.alignment() == pytest.approx(expected_a, abs=1e-15)
    assert result.connectedness() == pytest.approx(expected_k, abs=1e-15)
    assert [s.known_pairs for s in result.scores] == [3, 3, 3, 3]
    assert result.excluded_pairs == () and result.rule == PRIMARY_SCORE_RULE
    # WEAK pairs are known: the audit leaves out UNKNOWN only.
    assert alignment(IDS, r, status, dict.fromkeys(IDS, P)) == result.alignment()
    assert connectedness(IDS, r, status, dict.fromkeys(IDS, P)) == result.connectedness()


def test_an_unknown_pair_is_out_of_sum_and_denominator_where_a_fixed_one_scores_zero() -> None:
    pairs = {**HAND, ("a", "b"): (0.99, U)}  # a number on an UNKNOWN pair is never read
    r, status = _matrices(IDS, pairs)
    result = primary_scores(IDS, r, status, dict.fromkeys(IDS, P))
    a, b, c, _ = result.scores
    assert a.alignment == pytest.approx((-0.2 + 0.4) / 2) and a.connectedness == pytest.approx(0.3)
    assert b.alignment == pytest.approx((0.1 - 0.5) / 2) and b.connectedness == pytest.approx(0.3)
    # A fixed m_P - 1 would have scored the unknown pair as "not connected".
    assert a.alignment != pytest.approx((-0.2 + 0.4) / 3)
    assert (a.known_pairs, a.unknown_partners) == (2, ("b",))
    assert (b.known_pairs, b.unknown_partners) == (2, ("a",))
    assert (c.known_pairs, c.unknown_partners) == (3, ())
    assert result.excluded_pairs == (("a", "b"),)


def test_an_object_with_only_unknown_pairs_is_unscored_where_zero_would_be_a_guess() -> None:
    pairs = {**HAND, ("a", "b"): (None, U), ("a", "c"): (None, U), ("a", "d"): (0.0, U)}
    r, status = _matrices(IDS, pairs)
    result = primary_scores(IDS, r, status, dict.fromkeys(IDS, P))
    a = result.scores[0]
    assert a.alignment is None and a.connectedness is None
    assert a.known_pairs == 0 and a.unknown_partners == ("b", "c", "d")
    assert result.alignment()["b"] == pytest.approx((0.1 - 0.5) / 2)
    assert result.excluded_pairs == (("a", "b"), ("a", "c"), ("a", "d"))


def test_a_single_primary_object_is_unscored_where_it_has_no_pair() -> None:
    result = primary_scores(["a"], [[None]], [[None]], {"a": P})
    assert result.alignment() == {"a": None} and result.connectedness() == {"a": None}


def test_a_secondary_object_never_moves_a_primary_score_where_it_reshuffles_classic() -> None:
    roles = dict.fromkeys(IDS, P)
    r, status = _matrices(IDS, HAND)
    alone = primary_scores(IDS, r, status, roles)

    # A context object tied strongly against a, strongly with d; its own row is
    # left half-filled and one cell is off any scale: nothing of it is read.
    ids = [*IDS, "s"]
    with_s = {
        **HAND,
        ("a", "s"): (-0.9, R),
        ("b", "s"): (0.0, W),
        ("c", "s"): (None, U),
        ("d", "s"): (0.9, R),
    }
    r2, status2 = _matrices(ids, with_s)
    r2[2][4] = 7.0
    status2[1][4] = None
    joined = primary_scores(ids, r2, status2, {**roles, "s": S})

    assert joined.scores == alone.scores  # bit-identical
    assert joined.primary == tuple(IDS) and joined.secondary == ("s",)
    assert "s" not in joined.alignment()

    # The classic score over all five puts a first without s and last with it.
    r2[2][4] = r2[4][2] = None
    classic_alone = relation_classic(_strength(r))
    classic_joined = relation_classic(_strength(r2))[:4]
    assert max(range(4), key=lambda k: classic_alone[k]) == 0
    assert min(range(4), key=lambda k: classic_joined[k]) == 0


def test_the_scores_stay_in_their_bounds_where_the_inputs_do() -> None:
    rng = random.Random(20261007)
    ids = [f"o{k}" for k in range(7)]
    for _ in range(200):
        pairs: dict[tuple[str, str], tuple[float | None, PairStatus]] = {}
        for x, a in enumerate(ids):
            for b in ids[x + 1 :]:
                st = rng.choice([R, W, U])
                pairs[(a, b)] = (rng.uniform(-1.0, 1.0), st)
        r, status = _matrices(ids, pairs)
        for score in primary_scores(ids, r, status, dict.fromkeys(ids, P)).scores:
            if score.known_pairs == 0:
                assert score.alignment is None and score.connectedness is None
                continue
            assert score.alignment is not None and score.connectedness is not None
            assert -1.0 <= score.alignment <= 1.0
            assert 0.0 <= score.connectedness <= 1.0
            assert abs(score.alignment) <= score.connectedness + 1e-15

    ends = {("a", "b"): (1.0, R), ("a", "c"): (-1.0, R), ("b", "c"): (-1.0, R)}
    r, status = _matrices(["a", "b", "c"], ends)
    result = primary_scores(["a", "b", "c"], r, status, dict.fromkeys("abc", P))
    assert result.alignment() == {"a": 0.0, "b": 0.0, "c": -1.0}
    assert result.connectedness() == {"a": 1.0, "b": 1.0, "c": 1.0}


def test_the_classic_score_is_mostly_constant_where_alignment_and_connectedness_differ() -> None:
    # The audit's C8 point on a small synthetic family: seven objects that go
    # together (r = +0.3) and three that go against them (r = -0.3), alike
    # among themselves (+0.3).
    ids = [f"o{k}" for k in range(10)]
    pairs: dict[tuple[str, str], tuple[float | None, PairStatus]] = {}
    for x, a in enumerate(ids):
        for y, b in enumerate(ids[x + 1 :], start=x + 1):
            pairs[(a, b)] = (0.3 if (x < 7) == (y < 7) else -0.3, R)
    r, status = _matrices(ids, pairs)
    classic = relation_classic(_strength(r))
    scores = primary_scores(ids, r, status, dict.fromkeys(ids, P))
    a = [v for v in scores.alignment().values() if v is not None]
    # Every classic score sits within 15 % of 11 (m - 1) = 99: the constant, not
    # the relations (107.1 with the family, 85.5 against it).
    assert all(abs(c - 99.0) / 99.0 < 0.15 for c in classic)
    assert classic[0] == pytest.approx(107.1) and classic[9] == pytest.approx(85.5)
    # Alignment says which side each object is on: +0.1 with, -1/6 against.
    assert a[:7] == pytest.approx([0.1] * 7) and a[7:] == pytest.approx([-1.5 / 9] * 3)

    # Opposite ties cancel in the classic score and in alignment; connectedness
    # tells a strongly split object from an unconnected one.
    split = ["x", "y", "p", "q"]
    four = {
        ("x", "p"): (0.8, R),
        ("x", "q"): (-0.8, R),
        ("x", "y"): (0.0, W),
        ("y", "p"): (0.0, W),
        ("y", "q"): (0.0, W),
        ("p", "q"): (0.0, W),
    }
    r4, status4 = _matrices(split, four)
    classic4 = relation_classic(_strength(r4))
    result = primary_scores(split, r4, status4, dict.fromkeys(split, P))
    assert classic4[0] == pytest.approx(classic4[1])
    assert result.alignment()["x"] == pytest.approx(result.alignment()["y"])
    assert result.connectedness()["x"] == pytest.approx(1.6 / 3)
    assert result.connectedness()["y"] == 0.0


def test_every_role_must_be_declared_where_a_default_would_make_everything_primary() -> None:
    r, status = _matrices(IDS, HAND)
    with pytest.raises(ValueError, match="nothing defaults to PRIMARY"):
        primary_scores(IDS, r, status, {"a": P, "b": P, "c": P})
    with pytest.raises(ValueError, match="does not have"):
        primary_scores(IDS, r, status, {**dict.fromkeys(IDS, P), "z": P})
    with pytest.raises(ValueError, match="unknown role"):
        primary_scores(IDS, r, status, {**dict.fromkeys(IDS, P), "d": "context"})
    with pytest.raises(ValueError, match="unique"):
        primary_scores(["a", "a"], [[None, 0.1], [0.1, None]], [[None, R], [R, None]], {"a": P})


def test_a_known_pair_needs_a_correlation_in_range_where_a_gap_would_be_scored() -> None:
    roles = dict.fromkeys(IDS, P)
    for bad in (None, 1.5, float("nan")):
        r, status = _matrices(IDS, {**HAND, ("a", "b"): (bad, R)})
        with pytest.raises(ValueError, match=r"\[-1, 1\]"):
            primary_scores(IDS, r, status, roles)
    r, status = _matrices(IDS, HAND)
    status[1][0] = W
    with pytest.raises(ValueError, match="two statuses"):
        primary_scores(IDS, r, status, roles)
    r, status = _matrices(IDS, HAND)
    r[1][0] = 0.5
    with pytest.raises(ValueError, match="two correlations"):
        primary_scores(IDS, r, status, roles)
    r, status = _matrices(IDS, HAND)
    status[0][1] = status[1][0] = None
    with pytest.raises(ValueError, match="no status"):
        primary_scores(IDS, r, status, roles)
    with pytest.raises(ValueError, match="4 x 4"):
        primary_scores(IDS, r[:3], status, roles)


def test_statuses_read_from_a_stored_body_are_accepted_where_they_name_a_status() -> None:
    r, status = _matrices(IDS, HAND)
    as_text = [[None if s is None else s.value for s in row] for row in status]
    roles = {k: v.value for k, v in dict.fromkeys(IDS, P).items()}
    assert primary_scores(IDS, r, as_text, roles).scores == (
        primary_scores(IDS, r, status, dict.fromkeys(IDS, P)).scores
    )
    as_text[0][1] = as_text[1][0] = "medium"
    with pytest.raises(ValueError, match="unknown status"):
        primary_scores(IDS, r, as_text, roles)


def test_the_payload_records_what_the_scores_were_computed_over() -> None:
    r, status = _matrices(IDS, {**HAND, ("c", "d"): (0.3, U)})
    body = primary_scores(IDS, r, status, dict.fromkeys(IDS, P)).to_payload()
    assert body["rule"] == PRIMARY_SCORE_RULE and "Q7" in body["rule_text"]
    assert body["primary"] == IDS and body["secondary"] == []
    assert body["excluded_pairs"] == [["c", "d"]]
    c = body["objects"][2]
    assert c == {
        "id": "c",
        "alignment": pytest.approx(-0.05),
        "connectedness": pytest.approx(0.15),
        "known_pairs": 2,
        "unknown_partners": ["d"],
    }


def test_mean_rating_is_the_audits_provisional_default_height() -> None:
    assert AUDIT_PROVISIONAL_DEFAULT_HEIGHT is ObjectMetric.MEAN_RATING
