"""Sociomapa systémů statistics (decisions SM10-SM18), each against a planted or published
answer."""

from __future__ import annotations

import numpy as np
import pytest

from aia_core.domain.sociomap.systems import (
    AWAITING_LABEL,
    MIN_MONTHS,
    SHOW_CIRCLES_BY_DEFAULT,
    STARTING_MINIMUM,
    DeclaredRange,
    DeclaredRates,
    PlantedRun,
    TooFewMonths,
    TooFewRaters,
    arrows_that_pass,
    benjamini_yekutieli,
    check_rows,
    declared_importance,
    effective_months,
    iaaft,
    influence_map,
    input_status,
    krippendorff_alpha,
    map_stability,
    minimum_rows,
    month_relations,
    permutation_importance,
    scale_futures,
    symmetric_part,
    total_influence,
    weighted_coverage,
)


def _ar1(n: int, phi: float, rng: np.random.Generator) -> np.ndarray:
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal()
    return x


# --- SM12, the month test -------------------------------------------------------------------


def test_benjamini_yekutieli_matches_the_hand_computed_adjustment() -> None:
    p = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    c = sum(1 / i for i in range(1, 6))
    rejected, adjusted = benjamini_yekutieli(p, 0.2)
    assert np.allclose(adjusted, 0.05 * c)  # every rank gives p_i * m * c / i = 0.05 * c
    assert rejected.all()
    assert not benjamini_yekutieli(p, 0.05)[0].any()


def test_iaaft_keeps_the_values_exactly_and_the_spectrum_closely() -> None:
    x = _ar1(120, 0.8, np.random.default_rng(1))
    surrogates = iaaft(x, 20, seed=2)
    for s in surrogates:
        assert np.array_equal(np.sort(s), np.sort(x))
    real, made = np.abs(np.fft.rfft(x)), np.abs(np.fft.rfft(surrogates)).mean(0)
    assert np.abs(made - real).sum() / real.sum() < 0.1
    assert not np.allclose(surrogates[0], x)


def test_effective_months_shrink_with_shared_inertia() -> None:
    rng = np.random.default_rng(3)
    white = effective_months(rng.normal(size=120), rng.normal(size=120))
    slow = effective_months(_ar1(120, 0.9, rng), _ar1(120, 0.9, rng))
    assert white > 100
    assert slow < 0.6 * 120
    assert slow <= 120


def test_month_relations_find_a_planted_pair_and_refuse_short_series() -> None:
    rng = np.random.default_rng(4)
    driver = _ar1(60, 0.5, rng)
    series = {
        "driver": driver,
        "follower": driver + 0.5 * rng.normal(size=60),
        "unrelated": _ar1(60, 0.5, rng),
    }
    result = month_relations(
        series, trend="linear", declared_false_pair_rate=0.05, surrogates=200, seed=5
    )
    accepted = {(p.first, p.second) for p in result.pairs if p.accepted}
    assert ("driver", "follower") in accepted
    assert ("driver", "unrelated") not in accepted
    assert result.declared_false_pair_rate == 0.05
    assert all(p.effective_months <= p.months for p in result.pairs)
    short = {name: values[:24] for name, values in series.items()}
    with pytest.raises(TooFewMonths):
        month_relations(short, trend="linear", declared_false_pair_rate=0.05, seed=5)
    assert MIN_MONTHS == 36


def test_month_relations_can_pass_a_planted_pair_among_many_series() -> None:
    # 12 series, 66 pairs: a pair's own 2,001 surrogate correlations could never pass BY here
    rng = np.random.default_rng(13)
    series = {f"s{i}": _ar1(48, 0.3, rng) for i in range(12)}
    series["s1"] = series["s0"] + 0.4 * rng.normal(size=48)
    result = month_relations(
        series, trend="linear", declared_false_pair_rate=0.05, surrogates=200, seed=14
    )
    accepted = {(p.first, p.second) for p in result.pairs if p.accepted}
    assert ("s0", "s1") in accepted
    assert len(accepted) <= 2


def test_month_relations_draw_few_false_pairs_between_independent_slow_series() -> None:
    rng = np.random.default_rng(6)
    series = {f"s{i}": _ar1(60, 0.9, rng) + 0.05 * np.arange(60) * i for i in range(6)}
    result = month_relations(
        series, trend="linear", declared_false_pair_rate=0.05, surrogates=200, seed=7
    )
    assert sum(p.accepted for p in result.pairs) <= 1  # 15 pairs, none planted


# --- SM13, minimum rows ---------------------------------------------------------------------


def test_minimum_rows_is_the_smallest_count_from_which_every_count_passes() -> None:
    rates = DeclaredRates(min_groups_found=0.8, max_false_pair_rate=0.05, min_stability=0.7)
    runs = [
        PlantedRun(24, 0.2, 0.10, 0.5),
        PlantedRun(36, 0.9, 0.04, 0.8),
        PlantedRun(48, 0.6, 0.04, 0.8),  # one replicate fails at 48
        PlantedRun(48, 0.9, 0.03, 0.9),
        PlantedRun(60, 0.95, 0.02, 0.9),
    ]
    assert minimum_rows(runs, rates) == 60
    assert minimum_rows([PlantedRun(60, 0.1, 0.5, 0.1)], rates) is None
    below = check_rows("Experti", 7, STARTING_MINIMUM["experts"])
    assert not below.drawable and "Experti" in below.message and "12" in below.message
    assert check_rows("Měsíce", 40, STARTING_MINIMUM["months"]).drawable


# --- SM14, stability -------------------------------------------------------------------------


def test_stability_circles_shrink_with_more_rows_and_are_off_by_default() -> None:
    def map_of(rows: np.ndarray) -> np.ndarray:
        return np.column_stack([rows.mean(0), rows.std(0)])

    rng = np.random.default_rng(8)
    centres = np.array([0.0, 3.0, 6.0, 9.0])
    few = map_stability(
        rng.normal(centres, 1.0, (12, 4)), map_of, block_length=3, draws=200, seed=9
    )
    many = map_stability(
        rng.normal(centres, 1.0, (240, 4)), map_of, block_length=3, draws=200, seed=9
    )
    assert many.stability < few.stability
    assert few.radii.shape == (4,)
    assert SHOW_CIRCLES_BY_DEFAULT is False


# --- SM15, one-sided relations --------------------------------------------------------------


def test_only_a_stable_asymmetry_gets_an_arrow() -> None:
    rng = np.random.default_rng(10)
    observed = np.array([[0, 4, 2], [1, 0, 2], [2, 2, 0]], float)
    redraws = observed + rng.normal(0, 0.3, (300, 3, 3))
    arrows = arrows_that_pass(observed, redraws)
    assert [(a.source, a.target) for a in arrows] == [(0, 1)]
    assert np.allclose(symmetric_part(observed), symmetric_part(observed).T)
    assert symmetric_part(observed)[0, 1] == 2.5


# --- SM16, Konkurence ------------------------------------------------------------------------


def test_weighted_coverage_counts_only_the_rows_that_matter() -> None:
    scores = np.array([[1.0, 1.0], [1.0, 0.0], [0.0, 1.0]])
    even = weighted_coverage(scores, np.array([1.0, 1.0]))
    assert even[0, 1] == 1.0 and even[1, 0] == 0.5  # one-way: 0 covers 1, 1 covers half of 0
    first_only = weighted_coverage(scores, np.array([1.0, 0.0]))
    assert first_only[1, 0] == 1.0  # the second row no longer counts
    assert np.isnan(first_only[0, 2])  # object 2 has no weighted strength to cover
    assert np.all(np.diag(even) == 1.0)


# --- SM17, Vlivy -----------------------------------------------------------------------------

# Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability", reliability data with
# missing values: 4 observers x 12 units; published alpha nominal 0.743, interval 0.849, and
# ordinal 0.815.
_N = np.nan
_KRIPPENDORFF = np.array(
    [
        [1, 2, 3, 3, 2, 1, 4, 1, 2, _N, _N, _N],
        [1, 2, 3, 3, 2, 2, 4, 1, 2, 5, _N, 3],
        [_N, 3, 3, 3, 2, 3, 4, 2, 2, 5, 1, _N],
        [1, 2, 3, 3, 2, 4, 4, 1, 2, 5, 1, _N],
    ]
)


@pytest.mark.parametrize(
    ("metric", "published"), [("nominal", 0.743), ("interval", 0.849), ("ordinal", 0.815)]
)
def test_krippendorff_alpha_reproduces_the_published_example(metric: str, published: float) -> None:
    assert krippendorff_alpha(_KRIPPENDORFF, metric) == pytest.approx(published, abs=0.0015)  # type: ignore[arg-type]


def test_total_influence_includes_indirect_paths() -> None:
    chain = np.array([[0, 1, 0], [0, 0, 1], [0, 0, 0]], float)
    total = total_influence(chain)
    assert total[0, 2] > 0  # 0 drives 2 only through 1
    assert total[2, 0] == 0


def test_influence_map_needs_five_raters_flags_disputes_and_heights_the_outcome() -> None:
    base = np.array([[0, 3, 0], [0, 0, 3], [1, 0, 0]], float)
    ratings = np.repeat(base[None], 6, axis=0)
    ratings[:, 2, 0] = [0, 4, 0, 4, 0, 4]  # raters split on 2 -> 0
    result = influence_map(ratings, disputed_width=1.0, outcome=2)
    assert result.disputed[2, 0] and result.disputed.sum() == 1
    assert result.heights[0] > 0 and np.isnan(result.heights[2])
    assert result.grade == "odhad"
    with pytest.raises(TooFewRaters):
        influence_map(ratings[:4], disputed_width=1.0, outcome=None)


# --- SM10, importance ------------------------------------------------------------------------


def test_permutation_importance_finds_the_indicator_the_model_uses() -> None:
    rng = np.random.default_rng(11)
    x = rng.normal(size=(400, 2))
    y = x[:, 0] + 0.1 * rng.normal(size=400)

    def predict(rows: np.ndarray) -> np.ndarray:
        return rows[:, 0]

    def score(actual: np.ndarray, predicted: np.ndarray) -> float:
        return float(np.corrcoef(actual, predicted)[0, 1])

    used, unused = permutation_importance(
        ["used", "unused"], x, y, predict, score, model="toy 2020-2023", repeats=50, seed=12
    )
    assert used.interval is not None and used.interval[0] > 0.5 and used.grade == "doloženo"
    assert unused.value == pytest.approx(0.0, abs=1e-12)
    declared = declared_importance({"rent": 2.0}, author="A. Bahbouh")
    assert declared[0].grade == "odhad" and declared[0].source == "A. Bahbouh"
    with pytest.raises(ValueError):
        declared_importance({"rent": 1.0}, author=" ")


# --- SM11, futures against the real world ---------------------------------------------------


def test_futures_are_placed_in_history_else_declared_else_own_spread() -> None:
    history = np.linspace(-0.2, 0.4, 101)
    placed = scale_futures(np.array([-0.2, 0.1, 0.4]), history=history, history_source="Eurostat")
    assert placed.method == "history"
    assert placed.positions[1] == pytest.approx(0.5, abs=0.02)
    narrow = scale_futures(np.linspace(0.09, 0.11, 50), history=history)
    assert narrow.warning is not None and "understated" in narrow.warning
    declared = scale_futures(np.array([5.0, 15.0]), declared=DeclaredRange(0.0, 10.0, "A. Bahbouh"))
    assert declared.method == "declared" and list(declared.positions) == [0.5, 1.0]
    own = scale_futures(np.array([1.0, 3.0]))
    assert own.method.startswith("own spread") and own.warning is not None


# --- SM18, register -------------------------------------------------------------------------


def test_an_input_is_labelled_until_its_own_test_passed_and_it_is_registered() -> None:
    assert input_status("Vlivy", planted_test_passed=True, registered={"Vlivy"}).label is None
    assert (
        input_status("Vlivy", planted_test_passed=False, registered={"Vlivy"}).label
        == AWAITING_LABEL
    )
    assert (
        input_status("Vlivy", planted_test_passed=True, registered={"Experti"}).label
        == AWAITING_LABEL
    )
