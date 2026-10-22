"""The signed-off methodology's object height and terrain, number for number against its code.

``fixtures/sociomap/aia/signed_off_terrain.json`` holds ten studies -- five seeded ones (8, 12,
20, 3 and 2 objects) and five edge cases on the first (an object nobody rated, equal heights,
nothing rated, two objects at one point, the object that sets the frame without a known pair)
-- and what the methodology's own code computes from their ratings and ruler positions: the mean
rating, the objects nobody rated (not placed), the relative heights, the objects the frame is
fitted over, the frame and the terrain grid, produced outside this repository under numpy 2.5. The
positions are the fixture's, not BB1's (BB1 differs between platforms), so this stage is
checked exactly: heights, relative heights and every terrain cell to 1e-12, the frame to the
last bits.

The methodology works in frame units (positions x 27, centred, scaled by ``k``); the port in
ruler units, so the frame's half-width is ``62 / (27 k)`` and its axis ``c + g / (27 k)``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.sociomap.engine_v2 import (
    _baseline_corrected,
    _frame_objects,
    _heights,
    _relative_heights,
    _scaled,
    compute_object_map,
)
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem, SociomapArtifactV3
from aia_core.domain.sociomap.relations import PairStatus
from aia_core.domain.sociomap.slots import HEIGHT, KERNEL
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    SociomapSpecV3,
    TerrainMethod,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)
from aia_core.domain.sociomap.terrain import (
    ONE_POINT_HALF_EXTENT,
    EnvelopeHill,
    EnvelopeParameters,
    EnvelopeTerrain,
    fit_frame,
    object_envelope,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sociomap/aia/signed_off_terrain.json").read_text("utf-8")
)
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}
TERRAIN = AIA_SOCIOMAP_V5.terrain
assert TERRAIN is not None and TERRAIN.frame_fill is not None
assert TERRAIN.relative_height_floor is not None
#: The methodology's frame: 62 frame units of half-width, 27 frame units to the ruler unit.
SPAN, SCALE = 62.0, 27.0


def _inputs(name: str, roles: dict[str, str] | None = None) -> ObjectMapInputs:
    ratings = STUDIES[name]["ratings"]
    ids = tuple(f"o{j}" for j in range(len(ratings[0])))
    people = tuple(f"r{k}" for k in range(len(ratings)))
    return ObjectMapInputs(
        respondent_ids=people,
        donor_ids=people,
        items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
        values=tuple(tuple(row) for row in ratings),
        # The fixture's uneven survey weights: the height is weighted, the relations are not.
        weights=tuple(STUDIES[name]["weights"]),
        object_ids=ids,
        object_items=ids,
        roles=roles or dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


def _on_0_1(value: float | None) -> float | None:
    return None if value is None else (value - 1.0) / 9.0


def _known(artifact_status: Any) -> list[list[bool]]:
    return [[s in (PairStatus.RELIABLE, PairStatus.WEAK) for s in row] for row in artifact_status]


def _framed(points: Any, relative: Any, framing: Any, ids: Any = None) -> EnvelopeTerrain:
    centre, half = fit_frame(
        [p for p, f in zip(points, framing, strict=True) if f], TERRAIN.frame_fill
    )
    return object_envelope(
        [
            EnvelopeHill(entity_id=oid, x=p[0], y=p[1], height=t)
            for oid, p, t in zip(
                ids or [f"o{j}" for j in range(len(points))], points, relative, strict=True
            )
            if t is not None
        ],
        EnvelopeParameters(
            grid_resolution=TERRAIN.grid_resolution,
            half_extent=half,
            sigma=TERRAIN.sigma,
            centre=centre,
        ),
        method="framed_relative_envelope",
    )


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_height_frame_and_terrain_match_the_methodologys_own_code(name: str) -> None:
    study, inputs = STUDIES[name], _inputs(name)
    m = len(inputs.object_ids)
    heights = _heights(_scaled(inputs), inputs.weights, inputs.object_columns())
    # The survey-weighted mean rating, on the declared 0-1 scale; nobody rated it: no height.
    assert [v is None for v in heights.values] == study["unrated"]
    for value, expected in zip(heights.values, study["mean_rating"], strict=True):
        assert (value is None) == (expected is None)
        if value is not None:
            assert value == pytest.approx(_on_0_1(expected), abs=1e-12)
    # An object nobody rated is not placed: no relative height.
    relative = _relative_heights(heights.values, [True] * m, TERRAIN.relative_height_floor)
    assert [t is None for t in relative] == [t is None for t in study["relative_height"]]
    np.testing.assert_allclose(
        [t for t in relative if t is not None],
        [t for t in study["relative_height"] if t is not None],
        rtol=0,
        atol=1e-12,
    )
    # The frame is fitted over the rated objects with a known pair (the port's own relations).
    pairs, _, _, _ = _baseline_corrected(inputs.values, inputs.object_ids, AIA_SOCIOMAP_V5)
    framing = _frame_objects(heights.values, _known(pairs.status))
    assert list(framing) == study["frame_objects"]
    # The frame: the middle of their bounding box, and the half-width of the methodology's
    # 62-unit grid at its scale k.
    points = [tuple(p) for p in study["ruler"]]
    framed = [p for p, f in zip(points, framing, strict=True) if f]
    centre, half = fit_frame(framed, TERRAIN.frame_fill)
    assert centre == tuple(study["frame_centre"])
    assert half == pytest.approx(SPAN / (SCALE * study["frame_k"]), rel=1e-15)
    terrain = _framed(points, relative, framing)
    xs, ys = terrain.parameters.axes()
    for axis, c in ((xs, centre[0]), (ys, centre[1])):
        expected_axis = c + np.array(study["grid_frame"]) / (SCALE * study["frame_k"])
        np.testing.assert_allclose(axis, expected_axis, rtol=0, atol=1e-14)
    if not terrain.source_ids:
        # Nothing rated: the methodology would draw a flat grid of 0, but no pair reaches the
        # layout floor, so the map is not mappable and has no terrain at all.
        unmapped = compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)
        assert unmapped.layout is None
        return
    # No cut-off: every cell has a height.
    grid = np.array(terrain.height, dtype=float)
    assert grid.shape == (85, 85) and np.isfinite(grid).all()
    step = study["terrain_step"]
    np.testing.assert_allclose(grid[::step, ::step], study["terrain"], rtol=0, atol=1e-12)


def test_the_studies_cover_the_edge_cases() -> None:
    assert STUDIES["one_unrated"]["unrated"].count(True) == 1
    assert all(STUDIES["all_unrated"]["unrated"])
    assert set(STUDIES["equal_heights"]["relative_height"]) == {0.5}
    # Two objects at one point: no extent to frame, the methodology's scale 1.
    assert STUDIES["one_point"]["frame_k"] == 1.0
    assert fit_frame([(0.0, 0.0), (0.0, 0.0)], 0.7) == ((0.0, 0.0), ONE_POINT_HALF_EXTENT)
    # No object with a known pair: nothing is fitted, the methodology's scale 1 about the origin.
    assert not any(STUDIES["equal_heights"]["frame_objects"])
    assert STUDIES["equal_heights"]["frame_k"] == 1.0
    assert fit_frame([], 0.7) == ((0.0, 0.0), ONE_POINT_HALF_EXTENT)
    # A rated object without a known pair is drawn but does not set the frame; here it is the
    # object that would set it, so leaving it out changes the frame.
    few = STUDIES["frame_without_one"]
    assert not all(few["frame_objects"]) and not any(few["unrated"])
    assert few["frame_k"] != STUDIES["complete"]["frame_k"]
    assert STUDIES["complete"]["terrain_step"] == 1


def test_the_object_map_stores_the_framed_terrain_under_aia_sociomap_5() -> None:
    artifact = compute_object_map(
        _inputs("one_unrated"), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    layout, heights, terrain = artifact.layout, artifact.heights, artifact.terrain
    assert layout is not None and isinstance(terrain, EnvelopeTerrain)
    assert heights.metric == "mean_rating_0_1"
    # The object nobody rated is not placed: left out before anything is computed, listed.
    rated = tuple(f"o{j}" for j in range(8) if j != 2)
    assert artifact.object_ids == rated and artifact.objects_not_placed == ("o2",)
    assert heights.relative is not None and None not in heights.relative
    assert heights.relative == _relative_heights(
        heights.values, [True] * 7, TERRAIN.relative_height_floor
    )
    framing = _frame_objects(heights.values, _known(artifact.relations.status))
    relative_only = terrain.model_copy(update={"absolute_height": None})
    assert relative_only == _framed(layout.points, heights.relative, framing, rated)
    # The panel's Absolutní view: the same envelope with each hill at its 0-1 height, stored.
    absolute = _framed(layout.points, heights.values, framing, rated)
    assert terrain.absolute_height == absolute.height
    assert terrain.absolute_height != terrain.height
    assert terrain.source_ids == rated
    assert all(h is not None for row in terrain.height for h in row)
    # The map is the rated objects' own, as if the object were not in the set.
    alone = _inputs("one_unrated").model_dump() | {
        "object_ids": rated,
        "object_items": rated,
        "roles": dict.fromkeys(rated, ObjectRole.PRIMARY.value),
    }
    without = compute_object_map(
        ObjectMapInputs.model_validate(alone), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert artifact == without.model_copy(update={"objects_not_placed": ("o2",)})
    stored = artifact.model_dump(mode="json")
    assert set(stored["terrain"]["parameters"]) == {
        "grid_resolution",
        "half_extent",
        "sigma",
        "centre",
    }
    assert stored["terrain"]["method"] == "framed_relative_envelope"
    assert stored["objects_not_placed"] == ["o2"]
    assert "heights are weighted means" in artifact.support.weighting
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact


def test_the_object_map_frames_its_terrain_on_the_objects_with_a_known_pair() -> None:
    # The object that sets the frame rated by 7 people: a layout pair (5 co-raters), but no
    # known pair (10). It is placed with a hill, yet the frame leaves it out.
    few = STUDIES["frame_without_one"]["frame_objects"].index(False)
    inputs = _inputs("complete")
    values = tuple(
        tuple(None if k >= 7 and j == few else v for j, v in enumerate(row))
        for k, row in enumerate(inputs.values)
    )
    artifact = compute_object_map(
        inputs.model_copy(update={"values": values}), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    layout, relative = artifact.layout, artifact.heights.relative
    assert layout is not None and relative is not None
    assert isinstance(artifact.terrain, EnvelopeTerrain)
    framing = _frame_objects(artifact.heights.values, _known(artifact.relations.status))
    assert framing == tuple(j != few for j in range(8))
    assert artifact.objects_not_placed == () and relative[few] is not None
    relative_only = artifact.terrain.model_copy(update={"absolute_height": None})
    assert relative_only == _framed(layout.points, relative, framing)
    assert relative_only != _framed(layout.points, relative, [True] * 8)
    absolute = _framed(layout.points, artifact.heights.values, framing)
    assert artifact.terrain.absolute_height == absolute.height
    # Nine people: every pair below the status floor, all at the layout floor. The map is drawn,
    # but no object has a known pair, so nothing is fitted.
    rng = np.random.default_rng(9)
    ratings = rng.integers(1, 11, size=(9, 6)).astype(float).tolist()
    ids = tuple(f"o{j}" for j in range(6))
    people = tuple(f"r{k}" for k in range(9))
    small = compute_object_map(
        ObjectMapInputs(
            respondent_ids=people,
            donor_ids=people,
            items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
            values=tuple(tuple(row) for row in ratings),
            weights=(1.0,) * 9,
            object_ids=ids,
            object_items=ids,
            roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
        ),
        AIA_SOCIOMAP_V5,
        connectedness_interval=False,
    )
    assert small.layout is not None and isinstance(small.terrain, EnvelopeTerrain)
    assert not any(any(row) for row in _known(small.relations.status))
    assert small.terrain.parameters.centre == (0.0, 0.0)
    assert small.terrain.parameters.half_extent == ONE_POINT_HALF_EXTENT


def test_objects_nobody_rated_are_listed_on_a_map_that_cannot_be_drawn() -> None:
    inputs = _inputs("three")
    values = tuple((row[0], None, None) for row in inputs.values)
    artifact = compute_object_map(
        inputs.model_copy(update={"values": values}), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert artifact.layout is None and artifact.object_ids == ("o0",)
    assert artifact.objects_not_placed == ("o1", "o2")
    assert artifact.not_mappable is not None
    assert artifact.not_mappable.message.endswith("the family has 1 (o1, o2 nobody rated)")
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact


def test_earlier_presets_store_exactly_what_they_stored() -> None:
    v4 = compute_object_map(_inputs("three"), AIA_SOCIOMAP_V4, connectedness_interval=False)
    stored = v4.model_dump(mode="json")
    assert "relative" not in stored["heights"] and "objects_not_placed" not in stored
    # Under aia-sociomap-5 too, a map whose objects were all rated stores no list.
    v5 = compute_object_map(_inputs("three"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    assert "objects_not_placed" not in v5.model_dump(mode="json")
    assert set(stored["terrain"]["parameters"]) == {
        "grid_resolution",
        "half_extent",
        "sigma",
        "kernel_cutoff",
    }
    assert set(spec_payload(AIA_SOCIOMAP_V4)["spec"]["terrain"]) == {
        "method",
        "sigma",
        "sigma_basis",
        "grid_resolution",
        "half_extent",
        "kernel_cutoff",
    }


def test_the_height_is_survey_weighted_and_the_relations_are_not() -> None:
    inputs = _inputs("three")
    even = inputs.model_copy(update={"weights": (1.0,) * len(inputs.weights)})
    a = compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)
    b = compute_object_map(even, AIA_SOCIOMAP_V5, connectedness_interval=False)
    assert a.heights.values != b.heights.values and a.relations == b.relations
    # The same weighted mean as the earlier presets'.
    v4 = compute_object_map(inputs, AIA_SOCIOMAP_V4, connectedness_interval=False)
    assert a.heights.values == v4.heights.values


def test_a_context_object_is_left_off_the_map() -> None:
    ids = [f"o{j}" for j in range(8)]
    roles = dict.fromkeys(ids, ObjectRole.PRIMARY.value) | {"o7": ObjectRole.SECONDARY.value}
    with_context = compute_object_map(
        _inputs("complete", roles), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    # The map is the PRIMARY objects' own, as if the context object were not in the set.
    primary = _inputs("complete").model_dump() | {
        "object_ids": tuple(ids[:7]),
        "object_items": tuple(ids[:7]),
        "roles": dict.fromkeys(ids[:7], ObjectRole.PRIMARY.value),
    }
    alone = compute_object_map(
        ObjectMapInputs.model_validate(primary), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert with_context.object_ids == tuple(ids[:7]) and with_context == alone


def _with_terrain(**update: Any) -> SociomapSpecV3:
    assert AIA_SOCIOMAP_V5.terrain is not None
    return AIA_SOCIOMAP_V5.model_copy(
        update={"terrain": AIA_SOCIOMAP_V5.terrain.model_copy(update=update)}
    )


def test_the_framed_envelope_refuses_what_it_does_not_read() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    assert AIA_SOCIOMAP_V5.terrain is not None
    assert AIA_SOCIOMAP_V5.terrain.method == TerrainMethod.FRAMED_RELATIVE_ENVELOPE
    assert AIA_SOCIOMAP_V4.terrain is not None
    for spec, field in (
        (_with_terrain(half_extent=2.75), "terrain.half_extent"),
        (_with_terrain(kernel_cutoff=0.0005), "terrain.kernel_cutoff"),
        (_with_terrain(frame_fill=None), "terrain.frame_fill"),
        (_with_terrain(frame_fill=1.5), "terrain.frame_fill"),
        (_with_terrain(relative_height_floor=1.0), "terrain.relative_height_floor"),
        (
            AIA_SOCIOMAP_V4.model_copy(
                update={"terrain": AIA_SOCIOMAP_V4.terrain.model_copy(update={"frame_fill": 0.7})}
            ),
            "terrain.frame_fill",
        ),
    ):
        with pytest.raises(UnsupportedMethodology) as refused:
            require_supported(spec)
        assert field in refused.value.unsupported


def _map(spec: SociomapSpecV3 = AIA_SOCIOMAP_V5, **slots: Any) -> SociomapArtifactV3:
    return compute_object_map(_inputs("three"), spec, connectedness_interval=False, slots=slots)


def test_every_value_and_formula_of_the_stage_changes_the_map_when_edited() -> None:
    base = _map()
    assert isinstance(base.terrain, EnvelopeTerrain) and base.heights.relative is not None
    wider = _map(_with_terrain(frame_fill=0.5))
    assert isinstance(wider.terrain, EnvelopeTerrain)
    assert wider.terrain.parameters.half_extent > base.terrain.parameters.half_extent
    lower = _map(_with_terrain(relative_height_floor=0.0))
    assert lower.heights.relative is not None
    assert min(t for t in lower.heights.relative if t is not None) == 0.0
    assert lower.terrain != base.terrain
    finer = _map(_with_terrain(grid_resolution=40))
    assert isinstance(finer.terrain, EnvelopeTerrain) and len(finer.terrain.height) == 41
    assert _map(_with_terrain(sigma=0.4)).terrain != base.terrain
    # The height formula reads every rater at weight 1; the kernel formula is read as is.
    highest = _map(**{HEIGHT: lambda a, w: max(a)})
    assert highest.heights.values != base.heights.values
    flat = _map(**{KERNEL: lambda h, d2, sigma: h})
    assert isinstance(flat.terrain, EnvelopeTerrain) and flat.terrain != base.terrain
