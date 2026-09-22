"""Normaliser (F5) and object metrics (F6), plus the fail-closed departures."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.sociomap.metrics import (
    METRIC_BOUNDS,
    NormalizationMode,
    ObjectMetric,
    UnknownMetricBounds,
    bounds_for,
    build_normalizer,
    object_metric,
    object_rating_summaries,
    population_mean_sd,
    relation_classic,
    tscore,
)

SERIALISATION = 1e-9

F5_CASES = {
    "range": (NormalizationMode.RANGE, "values", None),
    "absolute": (NormalizationMode.ABSOLUTE, "values", None),
    "absolute_with_bounds": (NormalizationMode.ABSOLUTE, "values", "bounds_case"),
    "sigma": (NormalizationMode.SIGMA, "values", None),
    "percentile": (NormalizationMode.PERCENTILE, "values", None),
    "empty_values": (NormalizationMode.RANGE, None, None),
    "zero_variance_sigma": (NormalizationMode.SIGMA, "constant", None),
}


def _case_values(fixture: dict[str, Any], source: str | None) -> list[float]:
    if source is None:
        return []
    if source == "constant":
        return [7.0, 7.0, 7.0]  # lo = hi = 7 in the fixture
    return list(fixture["input"][source])


# --------------------------------------------------------------------- F5 --


@pytest.mark.parametrize("case", sorted(F5_CASES))
def test_f5_normaliser_matches_the_reference(sociomap_fixture: Any, case: str) -> None:
    fixture = sociomap_fixture("F5")
    mode, source, bounds_key = F5_CASES[case]
    bounds = tuple(fixture["input"][bounds_key]) if bounds_key else None
    norm = build_normalizer(_case_values(fixture, source), mode, bounds)  # type: ignore[arg-type]
    expected = fixture["expected_output"][case]
    assert norm.lo == pytest.approx(expected["lo"], abs=SERIALISATION)
    assert norm.hi == pytest.approx(expected["hi"], abs=SERIALISATION)
    assert norm.label_cs == expected["label"]
    for probe, want in zip(fixture["input"]["probe_points"], expected["transform"], strict=True):
        assert norm(probe) == pytest.approx(want, abs=SERIALISATION), (case, probe)


def test_f5_covers_every_reference_case(sociomap_fixture: Any) -> None:
    assert set(sociomap_fixture("F5")["expected_output"]) == set(F5_CASES)


def test_normaliser_ignores_missing_values() -> None:
    norm = build_normalizer([None, 2.0, None, 4.0], NormalizationMode.RANGE, None)
    assert (norm.lo, norm.hi, norm(3.0)) == (2.0, 4.0, 0.5)


def test_normaliser_refuses_an_unknown_mode() -> None:
    # normalizer66 falls through to "range"; a typo must not.
    with pytest.raises(ValueError):
        build_normalizer([1.0, 2.0], "ranged", None)  # type: ignore[arg-type]


def test_normaliser_refuses_inverted_bounds() -> None:
    with pytest.raises(ValueError):
        build_normalizer([1.0], NormalizationMode.ABSOLUTE, (10.0, 1.0))


def test_constant_range_normalises_to_the_middle() -> None:
    norm = build_normalizer([3.0, 3.0], NormalizationMode.RANGE, None)
    assert norm(3.0) == 0.5 and norm(100.0) == 0.5


def test_sigma_mode_spans_plus_minus_two_and_a_half_sd() -> None:
    norm = build_normalizer([0.0, 2.0], NormalizationMode.SIGMA, None)  # mean 1, sd 1
    assert norm(1.0 - 2.5) == 0.0 and norm(1.0 + 2.5) == 1.0 and norm(1.0) == 0.5


def test_population_divisor_is_used() -> None:
    assert population_mean_sd([0.0, 2.0]) == (1.0, 1.0)  # sample sd would be 1.414...


def test_absolute_bounds_are_used_only_where_recovered() -> None:
    assert bounds_for("mean_rating", NormalizationMode.ABSOLUTE) == (1.0, 10.0)
    assert bounds_for("density", NormalizationMode.ABSOLUTE) is None
    assert bounds_for("support_n", NormalizationMode.RANGE) is None
    with pytest.raises(UnknownMetricBounds):
        bounds_for("support_n", NormalizationMode.ABSOLUTE)


def test_mean_rating_is_bounded_by_the_declared_rating_scale() -> None:
    # A 0-5 study normalised against the reference's 1-10 would put a perfect
    # mean of 5 at 4/9 instead of 1.
    bounds = bounds_for("mean_rating", NormalizationMode.ABSOLUTE, rating_scale=(0.0, 5.0))
    assert bounds == (0.0, 5.0)
    assert build_normalizer([5.0], NormalizationMode.ABSOLUTE, bounds)(5.0) == 1.0
    with pytest.raises(UnknownMetricBounds):
        bounds_for("support_n", NormalizationMode.ABSOLUTE, rating_scale=(0.0, 5.0))


def test_metric_bounds_carry_only_the_recovered_entries() -> None:
    assert dict(METRIC_BOUNDS) == {"density": None, "mean_rating": (1.0, 10.0)}


# --------------------------------------------------------------------- F6 --


@pytest.mark.parametrize(
    ("metric", "key"),
    [
        (ObjectMetric.MEAN_RATING, "mean_rating"),
        (ObjectMetric.SUPPORT_N, "support_n"),
        (ObjectMetric.RELATION_CLASSIC, "relation_classic"),
        (ObjectMetric.RELATION_CLASSIC_TSCORE, "tscore_default"),
    ],
)
def test_f6_object_metrics_match_the_reference(
    sociomap_fixture: Any, metric: ObjectMetric, key: str
) -> None:
    fixture = sociomap_fixture("F6")
    inputs = fixture["input"]
    values = object_metric(
        metric,
        mean_rating=inputs["mean_rating"],
        support_n=inputs["support_n"],
        relation=inputs["matrix"],
    )
    expected = fixture["expected_output"][key]
    assert values == pytest.approx(expected, abs=SERIALISATION)


def test_unknown_metric_id_is_refused_not_turned_into_a_tscore(sociomap_fixture: Any) -> None:
    inputs = sociomap_fixture("F6")["input"]
    with pytest.raises(ValueError, match="unknown object metric"):
        object_metric("popularity", relation=inputs["matrix"])


@pytest.mark.parametrize("metric", list(ObjectMetric))
def test_a_metric_without_its_input_is_refused(metric: ObjectMetric) -> None:
    with pytest.raises(ValueError):
        object_metric(metric)


def test_relation_classic_counts_both_directions() -> None:
    assert relation_classic([[0, 1, 0], [0, 0, 0], [5, 0, 0]]) == (6.0, 1.0, 5.0)


def test_relation_classic_refuses_a_ragged_matrix() -> None:
    with pytest.raises(ValueError):
        relation_classic([[0, 1], [1]])


def test_tscore_is_fifty_for_a_constant_distribution() -> None:
    assert tscore([4.0, 4.0, 4.0]) == (50.0, 50.0, 50.0)


def test_tscore_has_mean_fifty_and_sd_ten() -> None:
    mean, sd = population_mean_sd(list(tscore([1.0, 5.0, 2.0, 9.0])))
    assert mean == pytest.approx(50.0) and sd == pytest.approx(10.0)


def test_rating_summaries_use_observed_cells_only() -> None:
    means, support = object_rating_summaries([[2.0, None], [4.0, None], [None, None]])
    assert means == (3.0, None) and support == (2.0, 0.0)


def test_rating_summaries_refuse_ragged_or_empty_input() -> None:
    with pytest.raises(ValueError):
        object_rating_summaries([])
    with pytest.raises(ValueError):
        object_rating_summaries([[1.0, 2.0], [1.0]])
