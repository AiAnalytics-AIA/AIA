"""Audit F7: one layout, turned onto the previous map as a view, and a label on every map.

Plan ``sociomap-formula-corrections`` chunk 2c. The unit computed four layouts that
disagreed -- opening the scenario view turned the map a quarter and enlarged it by 16 % --
and no map said how far to trust it. Here a new map is aligned to the one the reader was
looking at by a rotation or reflection only, and its Stress-1 carries the audit's label.
"""

from __future__ import annotations

import math

import pytest

from aia_core.domain.sociomap.layout import correlation_distances, fit_smacof_objects
from aia_core.domain.sociomap.view import (
    STRESS_QUALITY_TEXT,
    StressQuality,
    ViewOverrideMismatch,
    align_to_reference,
    stress_quality,
)

FIT = {"max_iterations": 5000, "tolerance": 1e-12}
MAP = {"a": (1.0, 0.0), "b": (0.0, 0.5), "c": (-1.0, -0.25), "d": (0.2, -0.6)}


def _turn(
    points: dict[str, tuple[float, float]], angle: float, *, mirror: bool = False
) -> dict[str, tuple[float, float]]:
    c, s = math.cos(angle), math.sin(angle)
    out = {}
    for k, (x, y) in points.items():
        y = -y if mirror else y
        out[k] = (c * x - s * y, s * x + c * y)
    return out


@pytest.mark.parametrize(
    ("stress", "label"),
    [
        (0.0, StressQuality.GOOD),
        (0.049, StressQuality.GOOD),
        (0.05, StressQuality.FAIR),
        (0.099, StressQuality.FAIR),
        (0.10, StressQuality.WEAK),
        (0.199, StressQuality.WEAK),
        (0.20, StressQuality.UNRELIABLE),
        (0.307, StressQuality.UNRELIABLE),
    ],
)
def test_every_stress_carries_the_audits_label(stress: float, label: StressQuality) -> None:
    """Audit F7 (p. 9): < 0.05 good, < 0.10 fair, < 0.20 weak, >= 0.20 "2D picture
    unreliable"; each bound belongs to the band above it."""
    assert stress_quality(stress) is label
    assert STRESS_QUALITY_TEXT[StressQuality.UNRELIABLE] == "2D picture unreliable"


@pytest.mark.parametrize("bad", [-0.01, math.nan, math.inf])
def test_a_stress_that_is_not_a_fit_is_not_labelled(bad: float) -> None:
    with pytest.raises(ValueError):
        stress_quality(bad)


def test_a_turned_map_is_turned_back_without_scaling() -> None:
    """The unit's scenario jump: a quarter turn (and its 16 % enlargement). The alignment
    undoes the turn, and -- no scaling -- leaves an enlarged map enlarged."""
    turned = _turn(MAP, math.pi / 2)
    view = align_to_reference(turned, MAP)
    assert view.rmsd == pytest.approx(0.0, abs=1e-12) and not view.reflected
    for k in MAP:
        assert view.points[k] == pytest.approx(MAP[k], abs=1e-12)
    enlarged = {k: (1.16 * x, 1.16 * y) for k, (x, y) in turned.items()}
    stretched = align_to_reference(enlarged, MAP)
    assert stretched.rmsd > 0.05  # the enlargement is not hidden
    for k in MAP:
        assert math.hypot(*stretched.points[k]) == pytest.approx(1.16 * math.hypot(*MAP[k]))


def test_a_mirrored_map_is_reflected_back() -> None:
    view = align_to_reference(_turn(MAP, 0.7, mirror=True), MAP)
    assert view.reflected and view.rmsd == pytest.approx(0.0, abs=1e-12)


def test_alignment_never_changes_the_layouts_distances_or_stress() -> None:
    """A view: the aligned points are the layout's, turned. Every pairwise distance -- and so
    the Stress-1 the label reads -- is the layout's own."""
    m = 6
    r = [[1.0 if i == j else math.cos(i - j) * 0.8 for j in range(m)] for i in range(m)]
    layout = fit_smacof_objects(
        correlation_distances(r, [[i != j for j in range(m)] for i in range(m)]), **FIT
    )
    ids = [f"o{i}" for i in range(m)]
    points = dict(zip(ids, layout.points, strict=True))
    view = align_to_reference(points, _turn(points, 1.1, mirror=True))
    for a in ids:
        for b in ids:
            assert math.dist(view.points[a], view.points[b]) == pytest.approx(
                math.dist(points[a], points[b]), abs=1e-12
            )
    assert view.base != view.reference  # each input named by its own fingerprint


def test_a_new_object_is_turned_with_the_rest_and_does_not_steer_the_fit() -> None:
    """A wave with one more object: the fit uses the objects both maps hold."""
    later = {**_turn(MAP, 0.4), "new": (5.0, 5.0)}
    view = align_to_reference(later, MAP)
    assert view.common == ("a", "b", "c", "d")
    assert view.rmsd == pytest.approx(0.0, abs=1e-12)
    assert math.hypot(*view.points["new"]) == pytest.approx(math.hypot(5.0, 5.0))


def test_two_maps_sharing_fewer_than_two_objects_are_not_aligned() -> None:
    with pytest.raises(ViewOverrideMismatch, match="share 1"):
        align_to_reference({"a": (1.0, 0.0), "x": (0.0, 1.0)}, {"a": (0.0, 1.0), "y": (1.0, 1.0)})


def test_the_same_maps_align_to_the_same_bits() -> None:
    turned = _turn(MAP, 2.3)
    assert align_to_reference(turned, MAP) == align_to_reference(turned, MAP)
