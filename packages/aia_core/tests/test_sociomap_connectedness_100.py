"""Connectedness on 0-100 with a respondent-bootstrap interval (audit F9, plan chunk 4a).

The audit "NPC Sociomapa: faulty formulas in the code" replaces the normative
score 50 + 10 z, which always makes winners and losers, with

    K100_i = 100 K_i,  [K_lo_i, K_hi_i] = 2.5 % / 97.5 % quantiles over B respondent
    bootstraps,  i above j only if their intervals do not overlap.

AIA's readings (register AUDIT-F9): pair status fixed from the full sample; a
resample that cannot compute one of an object's pairs does not score it and is
counted; aggregation's generator and linear quantile (OI-62); a ranking that is
a relation per pair and a rank range per object, because overlap is not transitive.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any

import pytest

from aia_core.domain.research_aggregate import BOOTSTRAP_GENERATOR, _quantile
from aia_core.domain.research_sociomap import derive_pair_relations
from aia_core.domain.sociomap.metrics import (
    CONNECTEDNESS_100_RULE,
    CONNECTEDNESS_BOOTSTRAP_GENERATOR,
    RANK_WITH_TIES_RULE,
    ObjectRole,
    PairCorrelator,
    RankRelation,
    connectedness_100,
    linear_quantile,
    primary_scores,
    rank_with_ties,
)
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN, PairStatus

P = ObjectRole.PRIMARY
R = PairStatus.RELIABLE
U = PairStatus.UNKNOWN

Matrix = list[list[float | None]]
Statuses = list[list[PairStatus | None]]


def _family(n: int, m: int, loading: float, seed: int) -> list[list[float | None]]:
    """``n`` respondents rating ``m`` objects, each on their own 0-1 scale (audit F2).

    Even objects load on one taste, odd ones on another, independent of it: a
    factor every object shared would be a rating habit, which the per-person
    min-max removes. ``loading`` 0 is no relation at all.
    """
    rng = random.Random(seed)
    rows: list[list[float | None]] = []
    for _ in range(n):
        tastes = (rng.gauss(0, 1), rng.gauss(0, 1))
        raw = [loading * tastes[j % 2] + rng.gauss(0, 1) for j in range(m)]
        low, high = min(raw), max(raw)
        rows.append([(v - low) / (high - low) for v in raw])
    return rows


def _pearson(rows: Sequence[Sequence[float | None]]) -> PairCorrelator:
    """The research step's correlator: derive_pair_relations, weight times multiplicity."""

    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        pairs = derive_pair_relations(
            rows,
            [float(k) for k in multiplicities],
            n_min=AUDIT_PROVISIONAL_N_MIN,
            confidence=0.95,
        )
        return [list(row) for row in pairs.r], [list(row) for row in pairs.status]

    return correlate


def _draws(n: int, resamples: int, seed: int) -> list[list[int]]:
    """The multiplicities OI-62's generator gives, replayed by hand."""
    rng = random.Random(seed)
    out = []
    for _ in range(resamples):
        counts = [0] * n
        for _ in range(n):
            counts[min(int(rng.random() * n), n - 1)] += 1
        out.append(counts)
    return out


def _uniform(m: int, value: float | None, status: PairStatus) -> tuple[Matrix, Statuses]:
    r: Matrix = [[None if i == j else value for j in range(m)] for i in range(m)]
    s: Statuses = [[None if i == j else status for j in range(m)] for i in range(m)]
    return r, s


IDS = ["a", "b", "c", "d"]
ROLES = dict.fromkeys(IDS, P)


def test_k100_is_a_hundred_times_connectedness_and_its_interval_contains_it() -> None:
    rows = _family(300, 4, loading=1.0, seed=3)
    correlate = _pearson(rows)
    result = connectedness_100(IDS, ROLES, correlate, respondents=300, resamples=200, seed=11)
    full = primary_scores(IDS, *correlate([1] * 300), ROLES).connectedness()
    assert result.rule == CONNECTEDNESS_100_RULE
    assert (result.resamples, result.seed, result.respondents) == (200, 11, 300)
    for s in result.scores:
        k = full[s.object_id]
        assert k is not None and s.k100 == 100.0 * k
        assert s.low is not None and s.high is not None
        assert s.low <= s.k100 <= s.high, s
        assert s.high - s.low < 20.0  # a margin of error, not the whole scale
        assert s.resamples_scored == 200 and s.known_pairs == 3


def test_near_zero_the_percentile_interval_sits_above_its_point() -> None:
    # Finding F-4a-1 (plan § 10, chunk 4a): K is a mean of |r|. Where the pairs are
    # near zero, a resample's duplicated rows add noise that |.| folds upward, so the
    # percentile interval the audit specifies lies above the full sample's K100 --
    # here for 10 of 20 independent objects. Recorded, not corrected: the interval
    # is the audit's, and a bias-corrected one would be a methodology change.
    ids = [f"o{j}" for j in range(20)]
    rows = _family(200, 20, loading=0.0, seed=1)
    result = connectedness_100(
        ids, dict.fromkeys(ids, P), _pearson(rows), respondents=200, resamples=100, seed=5
    )
    above = [
        s for s in result.scores if s.low is not None and s.k100 is not None and s.low > s.k100
    ]
    assert len(above) == 10
    assert not any(
        s.high is not None and s.k100 is not None and s.high < s.k100 for s in result.scores
    )


def test_the_same_seed_is_bit_identical_and_another_seed_is_not() -> None:
    rows = _family(120, 4, loading=0.8, seed=5)

    def run(seed: int) -> dict[str, Any]:
        return connectedness_100(
            IDS, ROLES, _pearson(rows), respondents=120, resamples=60, seed=seed
        ).to_payload()

    first = run(7)
    assert run(7) == first
    other = run(8)
    assert other != first
    assert [o["k100"] for o in other["objects"]] == [o["k100"] for o in first["objects"]]


def test_the_interval_is_the_linear_quantile_of_the_resampled_scores_by_hand() -> None:
    # Every pair's r is the share of the draws that picked respondent 0, so every
    # K100 of a resample is 100 x that share: the interval can be computed by hand
    # from OI-62's generator and the type 7 quantile.
    n, b, seed = 10, 40, 2026

    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        return _uniform(3, multiplicities[0] / n, R)

    result = connectedness_100(
        ["x", "y", "z"], dict.fromkeys("xyz", P), correlate, respondents=n, resamples=b, seed=seed
    )
    shares = sorted(100.0 * d[0] / n for d in _draws(n, b, seed))
    for s in result.scores:
        assert s.k100 == 10.0  # the full sample takes respondent 0 once
        assert s.low == linear_quantile(shares, 0.025)
        assert s.high == linear_quantile(shares, 0.975)
        assert s.resamples_scored == b


def test_the_quantile_and_the_generator_are_aggregations() -> None:
    assert CONNECTEDNESS_BOOTSTRAP_GENERATOR == BOOTSTRAP_GENERATOR
    rng = random.Random(4)
    for size in (1, 2, 3, 7, 40, 501):
        values = sorted(rng.uniform(-5, 5) for _ in range(size))
        for q in (0.0, 0.025, 0.25, 0.5, 0.975, 1.0):
            assert linear_quantile(values, q) == _quantile(values, q)
    # Type 7 by hand: (n - 1) q = 0.075 between 1 and 2.
    assert linear_quantile([1.0, 2.0, 3.0, 4.0], 0.025) == pytest.approx(1.075, abs=1e-15)
    with pytest.raises(ValueError, match="at least one value"):
        linear_quantile([], 0.5)


def test_an_unscored_object_has_no_interval_and_is_unranked() -> None:
    r, s = _uniform(4, 0.4, R)
    for j in range(1, 4):
        s[0][j] = s[j][0] = U
        r[0][j] = r[j][0] = None

    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        return r, s

    result = connectedness_100(IDS, ROLES, correlate, respondents=5, resamples=10, seed=1)
    first = result.scores[0]
    assert (first.k100, first.low, first.high, first.interval) == (None, None, None, None)
    assert first.resamples_scored == 0 and first.known_pairs == 0
    assert all(
        o.k100 == pytest.approx(40.0) and o.resamples_scored == 10 for o in result.scores[1:]
    )
    ranking = rank_with_ties(result.intervals())
    assert ranking.unranked == ("a",)
    assert [o.object_id for o in ranking.objects] == ["b", "c", "d"]


def test_a_resample_that_cannot_compute_a_pair_does_not_score_its_objects() -> None:
    # (a, b) has no correlation in a resample that did not draw respondent 0: there
    # a and b are not scored (never 0, never over two pairs instead of three);
    # c and d, whose pairs all compute, are scored by every resample.
    n, b, seed = 6, 50, 9

    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        r, s = _uniform(4, 0.5, R)
        if multiplicities[0] == 0:
            r[0][1] = r[1][0] = None
        return r, s

    result = connectedness_100(IDS, ROLES, correlate, respondents=n, resamples=b, seed=seed)
    drew_zero = sum(1 for d in _draws(n, b, seed) if d[0] > 0)
    assert 0 < drew_zero < b
    scored = {s.object_id: s.resamples_scored for s in result.scores}
    assert scored == {"a": drew_zero, "b": drew_zero, "c": b, "d": b}
    assert all(s.low == s.high == pytest.approx(50.0) for s in result.scores)


def test_a_pair_the_full_sample_calls_unknown_stays_out_of_every_resample() -> None:
    # The resamples call (a, b) RELIABLE at r = 1; the full sample called it UNKNOWN,
    # so no resample reads it, and a's interval is its other pairs' alone.
    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        r, s = _uniform(4, 0.2, R)
        if multiplicities == [1, 1, 1, 1]:
            s[0][1] = s[1][0] = U
        else:
            r[0][1] = r[1][0] = 1.0
        return r, s

    result = connectedness_100(IDS, ROLES, correlate, respondents=4, resamples=30, seed=3)
    a = result.scores[0]
    assert a.known_pairs == 2
    assert a.k100 == a.low == a.high == pytest.approx(20.0)
    assert a.resamples_scored == 30


def test_resamples_and_seed_are_the_callers_and_are_recorded() -> None:
    r, s = _uniform(4, 0.3, R)

    def correlate(multiplicities: Sequence[int]) -> tuple[Matrix, Statuses]:
        return r, s

    with pytest.raises(TypeError):
        connectedness_100(IDS, ROLES, correlate, respondents=4, seed=1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        connectedness_100(IDS, ROLES, correlate, respondents=4, resamples=5)  # type: ignore[call-arg]
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ValueError, match="resamples"):
            connectedness_100(IDS, ROLES, correlate, respondents=4, resamples=bad, seed=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="seed"):
        connectedness_100(IDS, ROLES, correlate, respondents=4, resamples=5, seed=True)
    with pytest.raises(ValueError, match="respondents"):
        connectedness_100(IDS, ROLES, correlate, respondents=0, resamples=5, seed=1)
    payload = connectedness_100(
        IDS, ROLES, correlate, respondents=4, resamples=5, seed=12
    ).to_payload()
    assert (payload["resamples"], payload["seed"]) == (5, 12)
    assert payload["generator"] == BOOTSTRAP_GENERATOR
    assert payload["quantiles"] == [0.025, 0.975]


def test_intervals_that_do_not_overlap_are_ordered() -> None:
    ranking = rank_with_ties({"a": (10.0, 20.0), "b": (30.0, 40.0), "c": (50.0, 60.0)})
    assert ranking.rule == RANK_WITH_TIES_RULE
    assert ranking.relation("c", "b") is RankRelation.ABOVE
    assert ranking.relation("a", "c") is RankRelation.BELOW
    by_id = {o.object_id: o for o in ranking.objects}
    assert [(by_id[k].rank_best, by_id[k].rank_worst) for k in "cba"] == [(1, 1), (2, 2), (3, 3)]
    assert by_id["b"].outranks == ("a",) and by_id["b"].outranked_by == ("c",)
    assert all(o.tied_with == () for o in ranking.objects)


def test_intervals_that_overlap_or_touch_are_tied() -> None:
    ranking = rank_with_ties({"a": (10.0, 30.0), "b": (20.0, 40.0), "c": (40.0, 50.0)})
    assert ranking.relation("a", "b") is RankRelation.TIED
    assert ranking.relation("b", "c") is RankRelation.TIED  # touching at 40 is overlap
    assert ranking.relation("c", "a") is RankRelation.ABOVE
    by_id = {o.object_id: o for o in ranking.objects}
    assert (by_id["b"].rank_best, by_id["b"].rank_worst) == (1, 3)
    assert by_id["b"].tied_with == ("a", "c")


def test_overlap_is_not_transitive_so_there_are_no_tie_groups() -> None:
    # a ~ b and b ~ c, yet c is above a: one tie group {a, b, c} would hide that
    # order, and two groups would invent one between b and its neighbours.
    ranking = rank_with_ties({"a": (0.0, 10.0), "b": (9.0, 20.0), "c": (15.0, 30.0)})
    assert ranking.relation("a", "b") is RankRelation.TIED
    assert ranking.relation("b", "c") is RankRelation.TIED
    assert ranking.relation("c", "a") is RankRelation.ABOVE
    ranges = {o.object_id: (o.rank_best, o.rank_worst) for o in ranking.objects}
    assert ranges == {"a": (2, 3), "b": (1, 3), "c": (1, 2)}
    # Input order is kept: the ranking implies no order of its own.
    assert [o.object_id for o in ranking.objects] == ["a", "b", "c"]


def test_a_ranking_refuses_an_interval_it_cannot_read() -> None:
    for bad in ((2.0, 1.0), (math.nan, 1.0), (0.0, math.inf), (True, 2.0), (1.0,), "ab"):
        with pytest.raises(ValueError):
            rank_with_ties({"a": bad})  # type: ignore[dict-item]
    ranking = rank_with_ties({"a": (1.0, 2.0), "b": None})
    with pytest.raises(KeyError):
        ranking.relation("a", "b")
    with pytest.raises(ValueError):
        ranking.relation("a", "a")
    payload = ranking.to_payload()
    assert payload["unranked"] == ["b"]
    assert payload["objects"][0]["interval"] == [1.0, 2.0]
