"""The signed-off methodology's respondent map, number for number against its code.

``fixtures/sociomap/aia/signed_off_placement.json`` holds ten studies -- five from the layout
fixture (8, 12, 20, 3 and 2 objects, their ratings taken from ``signed_off_layout.json``), one
with clear tastes on 12 objects, and four edge cases on the first (an object nobody rated, five
objects, respondents with two ratings or all ratings equal, nobody placed) -- and what the
methodology's own code computes from their ratings (scale 1-10) and ruler positions, with the AIA
panel's caller rules: each respondent's position, misfit, chance-test p-value and status, the
counts, whether the map is informative, the frame and the density of the PLACED respondents on
it, produced outside this repository under numpy 2.5. The positions are the fixture's, not
BB1's (BB1 differs between platforms), so this stage is checked exactly: positions, misfits,
p-values and every density cell checked to 1e-12, statuses and counts as they are.

The methodology works in frame units (positions x 27, centred, scaled by ``k``); the port in
ruler units, so the frame's half-width is ``62 / (27 k)`` and its axis ``c + g / (27 k)``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.pipeline import fingerprint
from aia_core.domain.sociomap.engine_v2 import (
    RESPONDENTS_NOT_COMPUTED,
    RESPONDENTS_NOT_MAPPED,
    _baseline_corrected,
    _frame_objects,
    _heights,
    _scaled,
    compute_object_map,
)
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import (
    ObjectMapInputs,
    RatingItem,
    RespondentMap,
    SociomapArtifactV3,
)
from aia_core.domain.sociomap.relations import PairStatus
from aia_core.domain.sociomap.signed_off_respondents import place_respondents, respondent_density
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    SociomapSpecV3,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)
from aia_core.domain.sociomap.terrain import EnvelopeParameters, EnvelopeTerrain, fit_frame

_HERE = Path(__file__).parent / "fixtures/sociomap/aia"
FIXTURE = json.loads((_HERE / "signed_off_placement.json").read_text("utf-8"))
LAYOUT = {
    study["name"]: study
    for study in json.loads((_HERE / "signed_off_layout.json").read_text("utf-8"))["studies"]
}
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}
RESPONDENT_MAP = AIA_SOCIOMAP_V5.respondent_map
TERRAIN = AIA_SOCIOMAP_V5.terrain
assert RESPONDENT_MAP is not None and TERRAIN is not None and TERRAIN.frame_fill is not None
#: The methodology's frame: 62 frame units of half-width, 27 frame units to the ruler unit.
SPAN, SCALE = 62.0, 27.0


def _ratings(name: str) -> list[list[float | None]]:
    study = STUDIES[name]
    rows = study["ratings"] if "ratings" in study else LAYOUT[study["ratings_from"]]["ratings"]
    return [list(row) for row in rows]


def _inputs(name: str) -> ObjectMapInputs:
    ratings = _ratings(name)
    ids = tuple(f"o{j}" for j in range(len(ratings[0])))
    people = tuple(f"r{k}" for k in range(len(ratings)))
    return ObjectMapInputs(
        respondent_ids=people,
        donor_ids=people,
        items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
        values=tuple(tuple(row) for row in ratings),
        weights=(1.0,) * len(people),
        object_ids=ids,
        object_items=ids,
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


def _on_0_1(name: str) -> Any:
    # The engine's own scaling onto each item's declared 0-1 scale.
    inputs = _inputs(name)
    return np.array(
        [[np.nan if v is None else v for v in row] for row in _scaled(inputs)], dtype=float
    )


def _stored(values: Any) -> tuple[float | None, ...]:
    return tuple(round(float(v), 5) if np.isfinite(v) else None for v in values)


def _close(port: Any, expected: list[float | None]) -> None:
    port = [None if not np.isfinite(v) else float(v) for v in port]
    assert [v is None for v in port] == [v is None for v in expected]
    np.testing.assert_allclose(
        [v for v in port if v is not None],
        [v for v in expected if v is not None],
        rtol=0,
        atol=1e-12,
    )


def _placement(name: str) -> Any:
    assert RESPONDENT_MAP is not None
    return place_respondents(
        np.array(STUDIES[name]["ruler"], dtype=float),
        _on_0_1(name),
        chance_level=RESPONDENT_MAP.chance_level,
        min_ratings=RESPONDENT_MAP.min_ratings,
    )


def _frame(name: str) -> EnvelopeParameters:
    """The fixture's frame on the ruler: its centre, and the half-width of the methodology's
    62-unit grid at its scale k."""
    assert RESPONDENT_MAP is not None and TERRAIN is not None
    study = STUDIES[name]
    return EnvelopeParameters(
        grid_resolution=TERRAIN.grid_resolution,
        half_extent=SPAN / (SCALE * study["frame_k"]),
        sigma=RESPONDENT_MAP.density_sigma,
        centre=tuple(study["frame_centre"]),
    )


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_placement_matches_the_methodologys_own_code(name: str) -> None:
    assert RESPONDENT_MAP is not None
    study, placed = STUDIES[name], _placement(name)
    assert list(placed.status) == study["status"]
    _close(placed.x[:, 0], [None if p[0] is None else p[0] for p in study["x"]])
    _close(placed.x[:, 1], [None if p[1] is None else p[1] for p in study["x"]])
    _close(placed.misfit, study["misfit"])
    _close(placed.p_value, study["pval"])
    assert {s: placed.status.count(s) for s in study["counts"]} == study["counts"]
    objects = len(study["ruler"])
    assert (objects >= RESPONDENT_MAP.informative_min_objects) is study["informative"]


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_density_matches_the_methodologys_own_code(name: str) -> None:
    assert RESPONDENT_MAP is not None and TERRAIN is not None
    study, inputs = STUDIES[name], _inputs(name)
    # The frame is the object terrain's: fitted over the rated objects with a known pair, by
    # the port's own relations, on the fixture's positions.
    pairs, _, _, _ = _baseline_corrected(inputs.values, inputs.object_ids, AIA_SOCIOMAP_V5)
    known = [[s in (PairStatus.RELIABLE, PairStatus.WEAK) for s in row] for row in pairs.status]
    heights = _heights(_scaled(inputs), inputs.weights, inputs.object_columns())
    framing = _frame_objects(heights.values, known)
    assert list(framing) == study["frame_objects"]
    points = [tuple(p) for p in study["ruler"]]
    centre, half = fit_frame(
        [p for p, f in zip(points, framing, strict=True) if f], TERRAIN.frame_fill
    )
    frame = _frame(name)
    assert centre == frame.centre
    assert half == pytest.approx(frame.half_extent, rel=1e-15)
    xs, ys = frame.axes()
    for axis, c in zip((xs, ys), study["frame_centre"], strict=True):
        expected = c + np.array(study["grid_frame"]) / (SCALE * study["frame_k"])
        np.testing.assert_allclose(axis, expected, rtol=0, atol=1e-14)
    placed = _placement(name)
    density = respondent_density(placed.x, placed.status, frame.axes(), frame.sigma)
    assert density.shape == (TERRAIN.grid_resolution + 1,) * 2
    step = study["terrain_step"]
    np.testing.assert_allclose(density[::step, ::step], study["terrain"], rtol=0, atol=1e-12)


def test_the_studies_cover_the_edge_cases() -> None:
    # Fewer than three objects: nobody can be placed; three ratings fit exactly: never PLACED.
    assert STUDIES["two"]["counts"]["NOT_PLACED"] == len(STUDIES["two"]["status"])
    assert STUDIES["three"]["counts"]["PLACED"] == 0 and STUDIES["three"]["counts"]["FADED"]
    # Below six objects the map is drawn but not informative.
    assert not STUDIES["five"]["informative"] and STUDIES["five"]["counts"]["PLACED"]
    # Two ratings, or all ratings equal: not placed.
    assert STUDIES["not_placed"]["counts"]["NOT_PLACED"] == 20
    # Nobody PLACED: a flat density of 0, not a division by zero.
    assert not np.any(STUDIES["nobody_placed"]["terrain"])
    assert len(STUDIES["one_unrated"]["ruler"]) == 7
    # With the fixture's positions, some respondents stand outside the object terrain's frame.
    placed, frame = _placement("sparse"), _frame("sparse")
    assert frame.centre is not None
    outside = np.abs(placed.x - np.array(frame.centre)).max(1) > frame.half_extent
    assert outside.any()


def test_the_object_map_stores_the_respondent_map_under_aia_sociomap_5() -> None:
    assert RESPONDENT_MAP is not None
    artifact = compute_object_map(_inputs("sparse"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    layout, terrain, respondents = artifact.layout, artifact.terrain, artifact.respondents
    assert layout is not None and isinstance(terrain, EnvelopeTerrain)
    assert isinstance(respondents, RespondentMap)
    # The positions are BB1's on this machine: the stored map is checked against the ported
    # functions on its own layout, not against the fixture.
    placed = place_respondents(
        np.array(layout.points, dtype=float),
        _on_0_1("sparse"),
        chance_level=RESPONDENT_MAP.chance_level,
        min_ratings=RESPONDENT_MAP.min_ratings,
    )
    # Every position is stored as placed, inside the frame or not: whether one stands outside
    # depends on the layout (the edge cases show it does on the fixture's positions).
    assert respondents.placement == placed.status
    assert respondents.x == _stored(placed.x[:, 0]) and respondents.y == _stored(placed.x[:, 1])
    assert respondents.misfit == _stored(placed.misfit)
    assert respondents.p_value == _stored(placed.p_value)
    assert sum(respondents.counts.values()) == len(artifact.respondent_ids)
    assert respondents.informative and respondents.min_objects == 6
    # The density stands on the object terrain's own grid, with its own kernel width.
    grid = respondents.density.parameters
    assert grid.centre == terrain.parameters.centre
    assert grid.half_extent == terrain.parameters.half_extent
    assert grid.grid_resolution == terrain.parameters.grid_resolution
    assert grid.sigma == RESPONDENT_MAP.density_sigma
    np.testing.assert_array_equal(
        respondents.density.height,
        respondent_density(placed.x, placed.status, grid.axes(), grid.sigma),
    )
    assert max(max(row) for row in respondents.density.height) == 1.0
    stored = artifact.model_dump(mode="json")
    assert set(stored["respondents"]) == {
        "status",
        "x",
        "y",
        "placement",
        "misfit",
        "p_value",
        "counts",
        "informative",
        "min_objects",
        "density",
        "segments",
    }
    assert set(stored["respondents"]["density"]["parameters"]) == {
        "grid_resolution",
        "half_extent",
        "sigma",
        "centre",
    }
    assert stored["spec"]["respondent_map"] == RESPONDENT_MAP.model_dump(mode="json")
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact


def test_survey_weights_do_not_enter_the_respondent_map() -> None:
    inputs = _inputs("complete")
    uneven = inputs.model_copy(
        update={"weights": tuple(1.0 + (k % 3) for k in range(len(inputs.weights)))}
    )
    a = compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)
    b = compute_object_map(uneven, AIA_SOCIOMAP_V5, connectedness_interval=False)
    assert a.heights != b.heights and a.respondents == b.respondents


def test_a_map_that_cannot_be_drawn_places_nobody() -> None:
    unmapped = compute_object_map(
        _inputs("nobody_placed"), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert unmapped.layout is None and unmapped.respondents == RESPONDENTS_NOT_MAPPED
    assert SociomapArtifactV3.from_payload(unmapped.to_payload()) == unmapped


def test_earlier_presets_store_exactly_what_they_stored() -> None:
    v4 = compute_object_map(_inputs("three"), AIA_SOCIOMAP_V4, connectedness_interval=False)
    assert v4.respondents == RESPONDENTS_NOT_COMPUTED
    # The block every earlier map has stored, byte for byte.
    assert fingerprint(v4.model_dump(mode="json")["respondents"]) == (
        "60e9c49c3b16765b6eab1149b94a62dfab94c95f07d163cd38ff528f3938f116"
    )
    for spec in (AIA_SOCIOMAP_V2, AIA_SOCIOMAP_V3, AIA_SOCIOMAP_V4):
        assert spec.respondent_map is None
        assert set(spec_payload(spec)["spec"]) == {
            "methodology_version",
            "ratings",
            "relation",
            "layout",
            "scores",
            "connectedness",
            "respondent_placement",
            "terrain",
        }


def _with(**update: Any) -> SociomapSpecV3:
    assert RESPONDENT_MAP is not None
    return AIA_SOCIOMAP_V5.model_copy(
        update={"respondent_map": RESPONDENT_MAP.model_copy(update=update)}
    )


def test_the_respondent_map_is_declared_exactly_under_the_signed_off_methodology() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    assert AIA_SOCIOMAP_V5.terrain is not None and AIA_SOCIOMAP_V4.terrain is not None
    for spec, field in (
        (AIA_SOCIOMAP_V5.model_copy(update={"respondent_map": None}), "respondent_map"),
        (AIA_SOCIOMAP_V4.model_copy(update={"respondent_map": RESPONDENT_MAP}), "respondent_map"),
        (AIA_SOCIOMAP_V5.model_copy(update={"terrain": None}), "respondent_map"),
        (_with(chance_level=0.0), "respondent_map.chance_level"),
        (_with(chance_level=1.0), "respondent_map.chance_level"),
        (_with(min_ratings=2), "respondent_map.min_ratings"),
        (_with(informative_min_objects=0), "respondent_map.informative_min_objects"),
        (_with(density_sigma=0.0), "respondent_map.density_sigma"),
        (_with(density_sigma=float("inf")), "respondent_map.density_sigma"),
    ):
        with pytest.raises(UnsupportedMethodology) as refused:
            require_supported(spec)
        assert field in refused.value.unsupported


def test_every_value_of_the_stage_changes_the_map_when_edited() -> None:
    def respondents(spec: SociomapSpecV3) -> RespondentMap:
        artifact = compute_object_map(_inputs("complete"), spec, connectedness_interval=False)
        assert isinstance(artifact.respondents, RespondentMap)
        return artifact.respondents

    base = respondents(AIA_SOCIOMAP_V5)
    assert base.counts["PLACED"] and base.counts["FADED"] and base.informative
    looser = respondents(_with(chance_level=0.5))
    assert looser.counts["PLACED"] > base.counts["PLACED"] and looser.x == base.x
    # Every respondent of the complete study rated its eight objects.
    assert respondents(_with(min_ratings=9)).counts["NOT_PLACED"] == len(base.placement)
    indicative = respondents(_with(informative_min_objects=9))
    assert not indicative.informative and indicative.min_objects == 9
    # Informative from exactly the declared number of objects (eight here).
    assert respondents(_with(informative_min_objects=8)).informative
    wider = respondents(_with(density_sigma=0.5))
    assert wider.density.parameters.sigma == 0.5 and wider.density != base.density
    assert wider.placement == base.placement


def test_a_respondent_exactly_at_the_chance_level_is_placed() -> None:
    # PLACED when the p-value is at most the level: at a level equal to the smallest FADED
    # p-value, that respondent is PLACED and nobody else changes but those at or below it.
    placed = _placement("complete")
    faded = np.where(np.asarray(placed.status) == "FADED", placed.p_value, np.inf)
    k = int(np.argmin(faded))
    at = place_respondents(
        np.array(STUDIES["complete"]["ruler"], dtype=float),
        _on_0_1("complete"),
        chance_level=float(faded[k]),
        min_ratings=3,
    )
    assert placed.status[k] == "FADED" and at.status[k] == "PLACED"


def test_objects_on_different_scales_are_not_mapped() -> None:
    # One scale per set: three of eight items declared on 1-20 make the set unmappable.
    inputs = _inputs("complete")
    items = tuple(
        i.model_copy(update={"scale_max": 20.0}) if k < 3 else i for k, i in enumerate(inputs.items)
    )
    artifact = compute_object_map(
        inputs.model_copy(update={"items": items}), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert artifact.layout is None and artifact.not_mappable is not None
    assert artifact.not_mappable.reason == "MIXED_SCALES"
    assert artifact.respondents.status == "not_computed"
