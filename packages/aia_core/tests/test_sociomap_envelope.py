"""The object terrain as the max-envelope of hills (audit F12, F13; chunk 4b).

``z(q) = max_j h_j exp(-||q - y_j||^2 / 2 sigma^2)`` over the PRIMARY objects: each object is
a hill of exactly its height, a neighbour raises a cell only to its own hill's height there,
and nothing else in AIA computes a surface. The kernel width is AIA's provisional one
(2026-10-09; the audit leaves it to its author, A5): a hill falls below 5 % of its height at
the correlation distance of r = 0.8.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

import pytest

from aia_core.domain.sociomap import (
    AIA_OBJECT_ENVELOPE,
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    PROVISIONAL_ENVELOPE_SIGMA,
    ObjectMapInputs,
    RatingItem,
    compute_object_map,
    read_artifact,
)
from aia_core.domain.sociomap.engine_v2 import TERRAIN_NOT_COMPUTED, TERRAIN_NOT_MAPPED
from aia_core.domain.sociomap.models_v3 import ObjectRole
from aia_core.domain.sociomap.terrain import (
    EnvelopeHill,
    EnvelopeParameters,
    EnvelopeTerrain,
    envelope_at,
    object_envelope,
)

REPO = Path(__file__).resolve().parents[3]
SIGMA = PROVISIONAL_ENVELOPE_SIGMA
CUT = AIA_OBJECT_ENVELOPE.kernel_cutoff


def _hill(name: str, x: float, y: float, h: float) -> EnvelopeHill:
    return EnvelopeHill(entity_id=name, x=x, y=y, height=h)


def _z(x: float, y: float, hills: list[EnvelopeHill]) -> float | None:
    found = envelope_at(x, y, hills, SIGMA, CUT)
    return None if found is None else found[0]


# --------------------------------------------------------------- F12, F13 --


def test_each_hill_is_exactly_its_height_and_a_high_neighbour_does_not_pull_it() -> None:
    low, high = _hill("low", 0.0, 0.0, 0.2), _hill("high", 0.5, 0.0, 1.0)
    assert _z(0.0, 0.0, [low, high]) == pytest.approx(0.2)
    assert _z(0.5, 0.0, [low, high]) == pytest.approx(1.0)
    # The unit's kernel-weighted mean at the low object's position, for contrast (F12):
    w = math.exp(-0.25 / (2 * SIGMA**2))
    weighted_mean = (0.2 + w * 1.0) / (1.0 + w)
    assert weighted_mean > 0.2 + 0.05  # pulled up; the envelope is not


def test_a_cluster_of_equal_hills_peaks_at_one_hills_height_never_their_sum() -> None:
    cluster = [_hill(f"c{k}", 0.05 * k, 0.0, 0.7) for k in range(3)]
    peak = max(_z(0.05 * k, 0.0, cluster) or 0.0 for k in range(3))
    assert peak == pytest.approx(0.7)


def test_far_from_every_hill_there_is_nothing_not_a_height_of_zero() -> None:
    hills = [_hill("a", 0.0, 0.0, 0.9)]
    assert _z(2.5, 2.5, hills) is None
    assert envelope_at(0.0, 0.0, [], SIGMA, CUT) is None


def test_the_cell_names_the_hill_that_sets_it() -> None:
    hills = [_hill("a", -1.0, 0.0, 0.4), _hill("b", 1.0, 0.0, 0.8)]
    assert envelope_at(-1.0, 0.0, hills, SIGMA, CUT) == (pytest.approx(0.4), 0)
    assert envelope_at(1.0, 0.0, hills, SIGMA, CUT) == (pytest.approx(0.8), 1)


def test_the_grid_is_the_envelope_cell_by_cell_and_deterministic() -> None:
    hills = [_hill("a", -0.6, 0.2, 0.5), _hill("b", 0.4, -0.3, 0.9)]
    params = EnvelopeParameters(
        grid_resolution=16, half_extent=2.75, sigma=SIGMA, kernel_cutoff=CUT
    )
    terrain = object_envelope(hills, params)
    axis = params.axis()
    for gy, y in enumerate(axis):
        for gx, x in enumerate(axis):
            expected = envelope_at(x, y, hills, SIGMA, CUT)
            if expected is None:
                assert terrain.height[gy][gx] is None and terrain.governing[gy][gx] is None
            else:
                assert terrain.height[gy][gx] == expected[0]
                assert terrain.governing[gy][gx] == expected[1]
    assert object_envelope(hills, params) == terrain
    assert EnvelopeTerrain.model_validate(terrain.model_dump(mode="json")) == terrain


@pytest.mark.parametrize("height", [-0.1, math.nan, math.inf])
def test_a_hill_is_finite_and_not_negative(height: float) -> None:
    with pytest.raises(ValueError, match="finite and not negative"):
        _hill("a", 0.0, 0.0, height)


def test_a_hill_is_not_a_boolean_and_ids_are_unique() -> None:
    with pytest.raises(ValueError, match="not booleans"):
        EnvelopeHill(entity_id="a", x=0.0, y=0.0, height=True)
    params = EnvelopeParameters(grid_resolution=4, half_extent=2.75, sigma=SIGMA, kernel_cutoff=CUT)
    with pytest.raises(ValueError, match="unique"):
        object_envelope([_hill("a", 0, 0, 1), _hill("a", 1, 1, 1)], params)


# ------------------------------------------------- the provisional width --


def _delta(r: float) -> float:
    return math.sqrt(2.0 * (1.0 - r))


def test_the_provisional_width_keeps_its_definition() -> None:
    """Below 5 % of its height at the correlation distance of r = 0.8; still above it at
    r = 0.9, so strongly related objects visibly share a ridge."""

    def kernel(d: float) -> float:
        return math.exp(-(d**2) / (2 * SIGMA**2))

    assert kernel(_delta(0.8)) < 0.05
    assert kernel(_delta(0.9)) > 0.05
    assert math.sqrt(0.4 / (2 * math.log(20))) >= SIGMA
    assert AIA_OBJECT_ENVELOPE.sigma_basis == "aia_provisional_r08_5pct"
    assert AIA_OBJECT_ENVELOPE.half_extent == pytest.approx(2.0 + 3 * SIGMA)


def _two_tastes(seed: int, n: int) -> list[list[float | None]]:
    """Fictional 1-10 ratings: objects 0-2 share one taste, 3-5 another, independent."""
    rng = random.Random(seed)
    rows: list[list[float | None]] = []
    for _ in range(n):
        g, a, b = rng.gauss(0, 1.0), rng.gauss(0, 1.0), rng.gauss(0, 1.0)
        level = [7.0, 6.0, 5.0, 4.0, 3.0, 2.5]  # different popularity per object
        rows.append(
            [
                float(
                    min(
                        10,
                        max(1, round(level[j] + g + 2.2 * (a if j < 3 else b) + rng.gauss(0, 0.8))),
                    )
                )
                for j in range(6)
            ]
        )
    return rows


def _inputs(rows: list[list[float | None]], roles: dict[str, str] | None = None) -> ObjectMapInputs:
    m = len(rows[0])
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{i}" for i in range(len(rows))),
        donor_ids=tuple(f"D{i}" for i in range(len(rows))),
        items=tuple(RatingItem(item_id=f"i{j}", scale_min=1.0, scale_max=10.0) for j in range(m)),
        values=tuple(tuple(r) for r in rows),
        weights=tuple([1.0] * len(rows)),
        object_ids=tuple(f"o{j}" for j in range(m)),
        object_items=tuple(f"i{j}" for j in range(m)),
        roles=roles or {f"o{j}": ObjectRole.PRIMARY.value for j in range(m)},
    )


def test_on_planted_tastes_objects_of_another_taste_never_raise_each_other() -> None:
    """The calibration on planted fictional structure: across the two tastes no hill lifts
    another object's position by more than 5 % of its own height."""
    art = compute_object_map(
        _inputs(_two_tastes(23, 400)), AIA_SOCIOMAP_V3, connectedness_interval=False
    )
    assert art.layout is not None and isinstance(art.terrain, EnvelopeTerrain)
    points, heights = art.layout.points, art.heights.values
    hills = [
        _hill(f"o{j}", points[j][0], points[j][1], h)
        for j, h in enumerate(heights)
        if h is not None
    ]
    r = art.relations.r
    for i in range(3):
        for j in range(3, 6):
            assert r[i][j] is not None and abs(r[i][j]) < 0.8  # planted independent
            d = math.dist(points[i], points[j])
            hj = heights[j]
            assert hj is not None
            assert hj * math.exp(-(d**2) / (2 * SIGMA**2)) < 0.05 * hj
    for i, h in enumerate(heights):
        assert h is not None
        z = _z(points[i][0], points[i][1], hills)
        assert z is not None and z >= h - 1e-12  # each object stands at least its own height


# ------------------------------------------------------------- the engine --


def test_the_v3_map_carries_its_envelope_and_the_v2_map_says_it_has_none() -> None:
    inputs = _inputs(_two_tastes(29, 300))
    v3 = compute_object_map(inputs, AIA_SOCIOMAP_V3, connectedness_interval=False)
    v2 = compute_object_map(inputs, AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert isinstance(v3.terrain, EnvelopeTerrain)
    assert v3.terrain.parameters.sigma == SIGMA
    assert len(v3.terrain.height) == AIA_OBJECT_ENVELOPE.grid_resolution + 1
    assert v3.terrain.source_ids == v3.object_ids
    assert v2.terrain == TERRAIN_NOT_COMPUTED  # the reason v2 maps were stored with
    assert read_artifact(v3.to_payload()) == v3


def test_a_secondary_object_raises_no_hill() -> None:
    """F8: context objects never enter terrain. (An object nobody rated has no height, but
    it has no pair either, so it is never mapped: no case reaches the terrain.)"""
    roles = {f"o{j}": ObjectRole.PRIMARY.value for j in range(6)}
    roles["o4"] = ObjectRole.SECONDARY.value
    art = compute_object_map(
        _inputs(_two_tastes(31, 300), roles), AIA_SOCIOMAP_V3, connectedness_interval=False
    )
    assert isinstance(art.terrain, EnvelopeTerrain)
    assert art.terrain.source_ids == ("o0", "o1", "o2", "o3", "o5")


def test_an_unmappable_family_has_no_terrain_and_says_why() -> None:
    rows = _two_tastes(37, 20)  # every pair below n_min: nothing places the objects
    art = compute_object_map(_inputs(rows), AIA_SOCIOMAP_V3, connectedness_interval=False)
    assert art.layout is None
    assert art.terrain == TERRAIN_NOT_MAPPED


# ------------------------------------------------- one formula only (F13) --


_KERNEL = re.compile(r"\b(?:Math|math|np|numpy)\.exp\(")
_SURFACE_READERS = (
    "apps/web/src",
    "apps/api/src",
    "apps/executors/src",
    "packages/aia_core/src/aia_core/application",
    "packages/aia_core/src/aia_core/infrastructure/report_docx",
)


def test_nothing_outside_the_engine_computes_a_surface() -> None:
    """F13: the report, the API, the executors and the web client read the terrain from the
    artifact; none of them evaluates a kernel of its own."""
    found = []
    for root in _SURFACE_READERS:
        for path in (REPO / root).rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".mjs", ".js"}:
                continue
            if ".test." in path.name or "node_modules" in path.parts:
                continue
            if _KERNEL.search(path.read_text(encoding="utf-8")):
                found.append(str(path.relative_to(REPO)))
    assert found == []
