"""Terrain field against F7 (respondent density) and F8 (object weighted mean).

F7 is reproduced end to end. F8 is reproduced only as far as its inputs allow:
its object positions come from the reference frontend's ``baseObjectLayout66``,
whose source is withheld (see ``.planning/open-items.md``), so the fixture pins
the constants, the bounds and the hr -> ht -> z chain, and the weighted-mean
semantics are pinned by constructed cases below.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from aia_core.domain.sociomap.metrics import METRIC_BOUNDS, NormalizationMode, build_normalizer
from aia_core.domain.sociomap.terrain import (
    TERRAIN66_OBJECT,
    TERRAIN66_RESPONDENT,
    TerrainMode,
    TerrainParameters,
    TerrainSource,
    compute_terrain,
)

SERIALISATION = 1e-9


def _density(points: list[tuple[float, float]], params: TerrainParameters = TERRAIN66_RESPONDENT):
    sources = [
        TerrainSource(entity_id=f"r{i}", x=x, y=y, height=1, colour=1)
        for i, (x, y) in enumerate(points)
    ]
    return compute_terrain(
        TerrainMode.RESPONDENT_DENSITY,
        sources,
        params,
        metric_id="density",
        normalization=NormalizationMode.RANGE,
        bounds=None,
    )


def _weighted(
    objects: list[tuple[float, float, float]], params: TerrainParameters = TERRAIN66_OBJECT
):
    sources = [
        TerrainSource(entity_id=f"o{i}", x=x, y=y, height=h, colour=h)
        for i, (x, y, h) in enumerate(objects)
    ]
    return compute_terrain(
        TerrainMode.OBJECT_METRIC,
        sources,
        params,
        metric_id="mean_rating",
        normalization=NormalizationMode.RANGE,
        bounds=None,
    )


# --------------------------------------------------------------------- F7 --


@pytest.fixture(scope="module")
def f7(sociomap_fixture: Any) -> tuple[dict[str, Any], Any]:
    fixture = sociomap_fixture("F7")
    points = [(p["x"], p["y"]) for p in fixture["input"]["respondent_points"]]
    return fixture["expected_output"], _density(points)


def test_f7_uses_the_reference_constants(f7: Any) -> None:
    expected, field = f7
    assert expected["N"] == TERRAIN66_RESPONDENT.grid_resolution
    assert expected["span"] == TERRAIN66_RESPONDENT.half_extent
    assert expected["sigma"] == TERRAIN66_RESPONDENT.sigma
    assert expected["terrain_mode"] == field.mode.value == "respondent_density"
    assert expected["height_def"]["bounds"] is METRIC_BOUNDS["density"] is None


def test_f7_grid_shape_and_every_cell_finite(f7: Any) -> None:
    expected, field = f7
    assert len(field.height_raw) == expected["grid_rows"]
    assert len(field.height_raw[0]) == expected["grid_cols"]
    assert field.finite_cells == expected["finite_hr_cells"] == 43 * 43


def test_f7_normaliser_and_total_height(f7: Any) -> None:
    expected, field = f7
    assert field.normalizer_lo == pytest.approx(expected["normalizer"]["lo"], abs=SERIALISATION)
    assert field.normalizer_hi == pytest.approx(expected["normalizer"]["hi"], abs=SERIALISATION)
    total = math.fsum(v for row in field.height_normalised for v in row)
    assert total == pytest.approx(expected["sum_ht"], abs=1e-6)  # fixture rounds to 6 dp


def test_f7_every_sample_matches(f7: Any) -> None:
    expected, field = f7
    axis = field.parameters.axis()
    for s in expected["samples"]:
        gx, gy = s["gx"], s["gy"]
        assert axis[gx] == pytest.approx(s["x"], abs=SERIALISATION)
        assert axis[gy] == pytest.approx(s["y"], abs=SERIALISATION)
        assert field.height_raw[gy][gx] == pytest.approx(s["hr"], abs=SERIALISATION)
        assert field.colour_raw[gy][gx] == pytest.approx(s["cr"], abs=SERIALISATION)
        assert field.height_normalised[gy][gx] == pytest.approx(s["ht"], abs=SERIALISATION)
        assert field.elevation(gx, gy) == pytest.approx(s["z"], abs=SERIALISATION)


# --------------------------------------------------------------------- F8 --


def test_f8_uses_the_reference_constants_and_bounds(sociomap_fixture: Any) -> None:
    expected = sociomap_fixture("F8")["expected_output"]
    assert expected["N"] == TERRAIN66_OBJECT.grid_resolution
    assert expected["span"] == TERRAIN66_OBJECT.half_extent
    assert expected["sigma"] == TERRAIN66_OBJECT.sigma
    assert expected["terrain_mode"] == TerrainMode.OBJECT_METRIC.value
    assert tuple(expected["height_def"]["bounds"]) == METRIC_BOUNDS["mean_rating"]
    assert expected["finite_hr_cells"] < expected["grid_rows"] * expected["grid_cols"]


def test_f8_height_to_elevation_chain(sociomap_fixture: Any) -> None:
    """The fixture's own hr values normalise and scale to its ht and z."""
    expected = sociomap_fixture("F8")["expected_output"]
    lo, hi = expected["normalizer"]["lo"], expected["normalizer"]["hi"]
    norm = build_normalizer([lo, hi], NormalizationMode.RANGE, None)
    for s in expected["samples"]:
        if s["hr"] is None:
            assert s["ht"] == 0 and s["z"] == 0  # unsupported cells are flat, not averaged
            continue
        assert norm(s["hr"]) == pytest.approx(s["ht"], abs=SERIALISATION)
        assert norm(s["hr"]) * TERRAIN66_OBJECT.z_scale == pytest.approx(s["z"], abs=SERIALISATION)


# ------------------------------------------------------- dual semantics --


def test_one_object_gives_its_own_value_wherever_it_has_support() -> None:
    field = _weighted([(0.0, 0.0, 7.5)])
    values = [v for row in field.height_raw for v in row if v is not None]
    # A weighted MEAN, not a density: it does not fall off with distance.
    assert all(v == pytest.approx(7.5, abs=1e-12) for v in values)


def test_object_mode_leaves_unsupported_cells_empty() -> None:
    field = _weighted([(0.0, 0.0, 7.5)])
    assert field.height_raw[0][0] is None and field.height_normalised[0][0] == 0.0
    assert 0 < field.finite_cells < 43 * 43


def test_weighted_mean_lies_between_the_object_values() -> None:
    field = _weighted([(-10.0, 0.0, 2.0), (10.0, 0.0, 8.0)])
    for row in field.height_raw:
        for v in row:
            assert v is None or 2.0 - 1e-12 <= v <= 8.0 + 1e-12
    centre = field.parameters.grid_resolution // 2
    assert field.height_raw[centre][centre] == pytest.approx(5.0)


def test_density_doubles_where_two_people_stand_and_the_mean_does_not() -> None:
    one = _density([(0.0, 0.0)])
    two = _density([(0.0, 0.0), (1e-12, 0.0)])
    c = one.parameters.grid_resolution // 2
    assert two.height_raw[c][c] == pytest.approx(2 * one.height_raw[c][c])  # type: ignore[operator]
    mean_one = _weighted([(0.0, 0.0, 4.0)])
    mean_two = _weighted([(0.0, 0.0, 4.0), (1e-12, 0.0, 4.0)])
    assert mean_two.height_raw[c][c] == mean_one.height_raw[c][c] == pytest.approx(4.0)


def test_density_terrain_refuses_metric_valued_sources() -> None:
    source = TerrainSource(entity_id="r0", x=0, y=0, height=7, colour=1)
    with pytest.raises(ValueError, match="density"):
        compute_terrain(
            TerrainMode.RESPONDENT_DENSITY,
            [source],
            TERRAIN66_RESPONDENT,
            metric_id="density",
            normalization=NormalizationMode.RANGE,
            bounds=None,
        )


def test_kernel_cutoff_is_strict_and_the_shortcut_changes_nothing() -> None:
    # A source whose kernel at the nearest grid node is exactly at the cutoff
    # boundary region must be treated by the exp() comparison, not the shortcut.
    params = TERRAIN66_RESPONDENT
    reach = math.sqrt(-2 * params.sigma**2 * math.log(params.kernel_cutoff))
    inside = _density([(-62.0 + reach * 0.999, -62.0)])
    outside = _density([(-62.0 + reach * 1.001, -62.0)])
    assert inside.height_raw[0][0] > 0.0  # type: ignore[operator]
    assert outside.height_raw[0][0] == 0.0


def test_empty_terrain_is_flat_at_zero_not_a_plateau() -> None:
    # The reference fits range normalisation to the all-zero grid, calls it
    # constant and lifts the whole map to 0.5 -- an empty filter drawn as a
    # plateau. No source means no terrain (deviation S7).
    for field in (_density([]), _weighted([])):
        assert all(v == 0.0 for row in field.height_normalised for v in row)
        assert (field.normalizer_lo, field.normalizer_hi) == (0.0, 1.0)


def test_a_single_flat_density_still_normalises_as_the_reference_does() -> None:
    # Only the source-free case changed: real sources keep the F7 semantics.
    field = _density([(0.0, 0.0)])
    assert field.normalizer_lo == 0.0 and field.normalizer_hi > 0.0


@pytest.mark.parametrize("field", ["half_extent", "sigma", "kernel_cutoff", "z_scale"])
def test_terrain_parameters_reject_booleans(field: str) -> None:
    with pytest.raises(ValueError, match="boolean"):
        TerrainParameters(**{**TERRAIN66_OBJECT.model_dump(), field: True})


def test_source_ids_must_be_unique() -> None:
    sources = [TerrainSource(entity_id="o", x=0, y=0, height=1, colour=1)] * 2
    with pytest.raises(ValueError, match="unique"):
        compute_terrain(
            TerrainMode.OBJECT_METRIC,
            sources,
            TERRAIN66_OBJECT,
            metric_id="mean_rating",
            normalization=NormalizationMode.RANGE,
            bounds=None,
        )


@pytest.mark.parametrize(
    "field",
    ["grid_resolution", "half_extent", "sigma", "kernel_cutoff", "z_scale"],
)
def test_terrain_parameters_have_no_defaults(field: str) -> None:
    values = TERRAIN66_OBJECT.model_dump()
    del values[field]
    with pytest.raises(ValueError):
        TerrainParameters(**values)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("grid_resolution", 0),
        ("grid_resolution", True),
        ("sigma", -1.0),
        ("half_extent", math.inf),
        ("kernel_cutoff", 1.0),
    ],
)
def test_terrain_parameters_reject_implausible_values(field: str, bad: Any) -> None:
    with pytest.raises(ValueError):
        TerrainParameters(**{**TERRAIN66_OBJECT.model_dump(), field: bad})
