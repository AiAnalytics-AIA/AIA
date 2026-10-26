"""The Sociomap terrain field, moved out of the browser (``terrain66``).

The reference computes terrain only in ``ui_app.html``, three times over, with no
backend counterpart. It is research computation -- it is what a hill on the map
*asserts* -- so it lives here and is tested against fixtures F7 and F8.

**The two modes compute different quantities.** This is the central contract:

=======================  ==============================  ==============================
                         respondent density              object metric
=======================  ==============================  ==============================
sources                  every respondent, ``h = c = 1``  every object, ``h = metric``
height ``hr``            ``sum w`` -- kernel **density**  ``sum w h / sum w`` -- kernel-
                                                          **weighted mean**
cell without support     ``0`` (grid is always full)      ``None`` (no value to average)
a hill means             *many people here*               *a high score here*
=======================  ==============================  ==============================

Collapsing the two would change what the map claims. They share one kernel,
``w = exp(-(dx^2 + dy^2) / (2 sigma^2))`` with ``w < cutoff`` skipped, on a
``(N + 1) x (N + 1)`` grid spanning ``-span .. +span``. Every constant is a
:class:`TerrainParameters` field, recorded in the spec, and part of the
fingerprint -- the reference's constants (``N = 42``, ``span = 62``,
``sigma = 9.5 | 12``, ``cutoff = 0.0005``, ``z = ht * 26``) are the presets
below, not hidden defaults.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from .metrics import NormalizationMode, build_normalizer
from .slots import KERNEL, NO_SLOTS, Slots

__all__ = [
    "ONE_POINT_HALF_EXTENT",
    "TERRAIN66_OBJECT",
    "TERRAIN66_RESPONDENT",
    "EnvelopeHill",
    "EnvelopeParameters",
    "EnvelopeTerrain",
    "TerrainField",
    "TerrainMode",
    "TerrainParameters",
    "TerrainSource",
    "compute_terrain",
    "envelope_at",
    "fit_frame",
    "idw_at",
    "idw_falloff_at",
    "object_envelope",
    "object_idw",
    "object_idw_falloff",
]


class TerrainMode(StrEnum):
    """Which quantity the terrain height is."""

    RESPONDENT_DENSITY = "respondent_density"
    OBJECT_METRIC = "object_metric"


class TerrainParameters(BaseModel):
    """Every constant of the terrain field. No defaults: use a preset or state them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_resolution: int
    half_extent: float
    sigma: float
    kernel_cutoff: float
    z_scale: float

    @field_validator(
        "grid_resolution", "half_extent", "sigma", "kernel_cutoff", "z_scale", mode="before"
    )
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        # pydantic would coerce True to 1 before the checks below could see it.
        if isinstance(v, bool):
            raise ValueError("terrain parameters must be numbers, not booleans")
        return v

    @field_validator("grid_resolution")
    @classmethod
    def _resolution(cls, v: int) -> int:
        if v < 1:
            raise ValueError("grid_resolution must be a positive integer")
        return v

    @field_validator("half_extent", "sigma", "z_scale")
    @classmethod
    def _positive(cls, v: float) -> float:
        if not (math.isfinite(v) and v > 0):
            raise ValueError("terrain extents, sigma and z scale must be positive and finite")
        return float(v)

    @field_validator("kernel_cutoff")
    @classmethod
    def _cutoff(cls, v: float) -> float:
        if not (math.isfinite(v) and 0 <= v < 1):
            raise ValueError("kernel_cutoff must be in [0, 1)")
        return float(v)

    def axis(self) -> tuple[float, ...]:
        """Grid coordinates along one axis: ``-span + g * 2 span / N`` for ``g = 0..N``."""
        n, span = self.grid_resolution, self.half_extent
        step = 2.0 * span / n
        return tuple(-span + g * step for g in range(n + 1))


# The reference's ``terrain66`` constants, per mode (F7, F8).
TERRAIN66_RESPONDENT = TerrainParameters(
    grid_resolution=42, half_extent=62.0, sigma=9.5, kernel_cutoff=0.0005, z_scale=26.0
)
TERRAIN66_OBJECT = TerrainParameters(
    grid_resolution=42, half_extent=62.0, sigma=12.0, kernel_cutoff=0.0005, z_scale=26.0
)


class TerrainSource(BaseModel):
    """One kernel source: a placed point with its height and colour values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str
    x: float
    y: float
    height: float
    colour: float

    @field_validator("x", "y", "height", "colour", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("terrain sources must be numbers, not booleans")
        return v

    @field_validator("x", "y", "height", "colour")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("terrain sources must be finite")
        return float(v)


Grid = tuple[tuple[float | None, ...], ...]


class TerrainField(BaseModel):
    """A computed terrain: raw height/colour fields plus the normalised height.

    Grids are indexed ``[gy][gx]``. ``height_raw`` is ``hr``, ``colour_raw`` is
    ``cr``, ``height_normalised`` is ``ht`` (``0`` where ``hr`` is ``None``, as
    in the reference). The displayed elevation is ``ht * parameters.z_scale``,
    see :meth:`elevation`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: TerrainMode
    parameters: TerrainParameters
    metric_id: str
    normalization: NormalizationMode
    normalizer_lo: float
    normalizer_hi: float
    source_ids: tuple[str, ...]
    height_raw: Grid
    colour_raw: Grid
    height_normalised: tuple[tuple[float, ...], ...]

    @model_validator(mode="after")
    def _shape(self) -> Self:
        size = self.parameters.grid_resolution + 1
        for name in ("height_raw", "colour_raw", "height_normalised"):
            grid = getattr(self, name)
            if len(grid) != size or any(len(row) != size for row in grid):
                raise ValueError(f"{name} must be a {size} x {size} grid")
        return self

    @property
    def finite_cells(self) -> int:
        """Cells with a height value (all of them in respondent mode)."""
        return sum(1 for row in self.height_raw for v in row if v is not None)

    def elevation(self, gx: int, gy: int) -> float:
        """Displayed elevation ``z = ht * z_scale`` of one cell."""
        return self.height_normalised[gy][gx] * self.parameters.z_scale


def _accumulate(
    sources: Sequence[TerrainSource], params: TerrainParameters
) -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
    axis = params.axis()
    two_sigma_sq = 2.0 * params.sigma * params.sigma
    cutoff = params.kernel_cutoff
    # Squared distance beyond which exp() is certainly below the cutoff. The
    # 1e-9 margin keeps boundary cells on the exact exp() comparison, so the
    # shortcut never changes which contributions are skipped.
    reach_sq = -two_sigma_sq * math.log(cutoff) * (1.0 + 1e-9) if cutoff > 0 else math.inf
    size = len(axis)
    den = [[0.0] * size for _ in range(size)]
    hsum = [[0.0] * size for _ in range(size)]
    csum = [[0.0] * size for _ in range(size)]
    for gy, y in enumerate(axis):
        den_row, h_row, c_row = den[gy], hsum[gy], csum[gy]
        for gx, x in enumerate(axis):
            d_acc = h_acc = c_acc = 0.0
            for s in sources:
                dsq = (x - s.x) ** 2 + (y - s.y) ** 2
                if dsq > reach_sq:
                    continue
                w = math.exp(-dsq / two_sigma_sq)
                if w < cutoff:
                    continue
                d_acc += w
                h_acc += w * s.height
                c_acc += w * s.colour
            den_row[gx], h_row[gx], c_row[gx] = d_acc, h_acc, c_acc
    return den, hsum, csum


def compute_terrain(
    mode: TerrainMode,
    sources: Sequence[TerrainSource],
    params: TerrainParameters,
    *,
    metric_id: str,
    normalization: NormalizationMode,
    bounds: tuple[float, float] | None,
) -> TerrainField:
    """Compute ``terrain66`` for one mode.

    In respondent mode every source must carry ``height = colour = 1`` -- the
    density semantics are not a metric, and a caller passing anything else has
    confused the two modes. The normaliser is fitted to the grid's finite
    ``hr`` values (F7: ``lo = 0``, the minimum over the grid).
    """
    mode = TerrainMode(mode)
    if mode is TerrainMode.RESPONDENT_DENSITY and any(
        s.height != 1.0 or s.colour != 1.0 for s in sources
    ):
        raise ValueError("respondent density terrain sources contribute h = c = 1, not a metric")
    ids = tuple(s.entity_id for s in sources)
    if len(set(ids)) != len(ids):
        raise ValueError("terrain source ids must be unique")

    den, hsum, csum = _accumulate(sources, params)
    size = params.grid_resolution + 1
    hr: list[tuple[float | None, ...]] = []
    cr: list[tuple[float | None, ...]] = []
    for gy in range(size):
        if mode is TerrainMode.RESPONDENT_DENSITY:
            hr.append(tuple(hsum[gy]))
            cr.append(tuple(csum[gy]))
        else:
            hr.append(
                tuple(hsum[gy][gx] / den[gy][gx] if den[gy][gx] > 0 else None for gx in range(size))
            )
            cr.append(
                tuple(csum[gy][gx] / den[gy][gx] if den[gy][gx] > 0 else None for gx in range(size))
            )

    # No source means no terrain, not a raised plane: fit the normaliser to no
    # values, so every cell is 0. Fitted to the all-zero grid instead, range mode
    # would call it constant and lift the whole map to 0.5 -- which is what the
    # reference does, and which draws an empty filter as a uniform plateau.
    fitted = [v for row in hr for v in row] if sources else []
    norm = build_normalizer(fitted, normalization, bounds)
    ht = tuple(tuple(0.0 if v is None else norm(v) for v in row) for row in hr)
    return TerrainField(
        mode=mode,
        parameters=params,
        metric_id=metric_id,
        normalization=norm.mode,
        normalizer_lo=norm.lo,
        normalizer_hi=norm.hi,
        source_ids=ids,
        height_raw=tuple(hr),
        colour_raw=tuple(cr),
        height_normalised=ht,
    )


# ------------------------------------------------------- the envelope (F12) --
#
# Audit F12 and F13: the object terrain is the max-envelope of the objects' hills,
#
#     z(q) = max_j h_j exp(-||q - y_j||^2 / 2 sigma^2),
#
# so each object is a hill of exactly its height and a neighbour can raise a cell
# only to its own hill's height there, never pull it towards a mean (the unit's
# kernel-weighted mean drew a low object beside a high one at 0.66 of the high) or
# pile up with others (a sum of hills peaks a cluster of three at 2.7x one). One
# formula, here; nothing else computes a surface.


class EnvelopeParameters(BaseModel):
    """The envelope's grid and kernel, in the map's own units (the fixed ruler).

    The framed envelope (``aia-sociomap-5``) centres its grid on the map, at ``centre``, and
    lets every hill reach every cell: ``kernel_cutoff`` ``None``. Both are left out of the
    stored form when ``None``, so every terrain stored before them reads, and recomputes, byte
    for byte.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_resolution: int
    half_extent: float
    sigma: float
    kernel_cutoff: float | None = None
    centre: tuple[float, float] | None = None

    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        for key in ("kernel_cutoff", "centre"):
            if body.get(key) is None:
                body.pop(key, None)
        return body

    @field_validator("grid_resolution", "half_extent", "sigma", "kernel_cutoff", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("envelope parameters must be numbers, not booleans")
        return v

    @field_validator("centre", mode="before")
    @classmethod
    def _centre_not_boolean(cls, v: object) -> object:
        if isinstance(v, (list, tuple)) and any(isinstance(c, bool) for c in v):
            raise ValueError("the grid's centre must be numbers, not booleans")
        return v

    @field_validator("grid_resolution")
    @classmethod
    def _resolution(cls, v: int) -> int:
        if v < 1:
            raise ValueError("grid_resolution must be a positive integer")
        return v

    @field_validator("half_extent", "sigma")
    @classmethod
    def _positive(cls, v: float) -> float:
        if not (math.isfinite(v) and v > 0):
            raise ValueError("the envelope's extent and sigma must be positive and finite")
        return float(v)

    @field_validator("kernel_cutoff")
    @classmethod
    def _cutoff(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (math.isfinite(v) and 0 < v < 1):
            raise ValueError("kernel_cutoff must lie strictly between 0 and 1")
        return float(v)

    @field_validator("centre")
    @classmethod
    def _centre(cls, v: tuple[float, float] | None) -> tuple[float, float] | None:
        if v is not None and not all(math.isfinite(c) for c in v):
            raise ValueError("the grid's centre is finite")
        return v

    def axis(self) -> tuple[float, ...]:
        """Grid offsets from the centre along one axis: ``-span + g * 2 span / N``, ``g = 0..N``."""
        n, span = self.grid_resolution, self.half_extent
        step = 2.0 * span / n
        return tuple(-span + g * step for g in range(n + 1))

    def axes(self) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """The grid's x and y coordinates: :meth:`axis`, moved to the centre when it has one."""
        offsets = self.axis()
        if self.centre is None:
            return offsets, offsets
        cx, cy = self.centre
        return tuple(cx + v for v in offsets), tuple(cy + v for v in offsets)


#: The half-width of the framed grid when every object stands at one point, so there is no
#: extent to frame: the signed-off methodology then draws its grid of 62 frame units at 27
#: frame units to the ruler unit (``frame_fit`` with its scale 1), 62 / 27 ruler units.
ONE_POINT_HALF_EXTENT: Final = 62.0 / 27.0
#: The largest offset from the centre at or below which every object stands at one point: the
#: methodology's 1e-12 on its 27-fold frame units, in ruler units.
_NO_EXTENT: Final = 1e-12 / 27.0


def fit_frame(
    points: Sequence[tuple[float, float]], fill: float
) -> tuple[tuple[float, float], float]:
    """The square the framed envelope's grid covers: its centre, the middle of the objects'
    bounding box (not their mean), and its half-width, the largest offset of an object from the
    centre on either axis over ``fill``, so the objects span ``fill`` of the half-width. With
    no extent, :data:`ONE_POINT_HALF_EXTENT`; with no object to fit, nothing is fitted: that
    half-width about the ruler's origin."""
    if not points:
        return (0.0, 0.0), ONE_POINT_HALF_EXTENT
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    reach = max(max(abs(x - cx), abs(y - cy)) for x, y in points)
    return (cx, cy), (reach / fill if reach > _NO_EXTENT else ONE_POINT_HALF_EXTENT)


class EnvelopeHill(BaseModel):
    """One object's hill: where it stands and how high it is (never negative)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_id: str
    x: float
    y: float
    height: float

    @field_validator("x", "y", "height", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("hills must be numbers, not booleans")
        return v

    @field_validator("x", "y")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("a hill stands at a finite position")
        return float(v)

    @field_validator("height")
    @classmethod
    def _height(cls, v: float) -> float:
        # A max-envelope of signed heights would let a negative hill vanish under the
        # zero far away from everything; a signed metric is a colour, not a height (Q7).
        if not (math.isfinite(v) and v >= 0.0):
            raise ValueError("an envelope hill's height is finite and not negative")
        return float(v)


#: The stored terrain methods: the envelope (on the fixed ruler or framed), and on the framed
#: grid the inverse-distance weighting (:func:`idw_at`), alone or under the hills' falloff
#: (:func:`idw_falloff_at`).
TerrainMethodName = Literal[
    "object_envelope",
    "framed_relative_envelope",
    "framed_relative_idw",
    "framed_relative_idw_falloff",
]


class EnvelopeTerrain(BaseModel):
    """The object envelope over a grid, indexed ``[gy][gx]``.

    ``height`` is ``z(q)``; ``None`` where no hill's kernel reaches the cutoff -- nothing
    is there, which is not a height of 0. ``governing`` is the index into ``source_ids``
    of the hill that sets each cell (the first of equals), ``None`` with the height.
    ``framed_relative_envelope`` (``aia-sociomap-5``) has no cutoff: with a hill, every cell
    has a height; ``absolute_height`` is the same envelope with each hill at its height on the
    declared 0-1 scale instead of its relative height, the panel's Absolutní view, so a reader
    draws it without evaluating a kernel. ``None`` (every other method) is left out of the
    stored form. ``framed_relative_idw`` and ``framed_relative_idw_falloff`` are the same grid
    under :func:`idw_at` and :func:`idw_falloff_at`; their ``governing`` hill is the one that
    weighs most in a cell (the object standing on it).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["computed"] = "computed"
    method: TerrainMethodName = "object_envelope"
    parameters: EnvelopeParameters
    source_ids: tuple[str, ...]
    height: tuple[tuple[float | None, ...], ...]
    governing: tuple[tuple[int | None, ...], ...]
    absolute_height: tuple[tuple[float | None, ...], ...] | None = None

    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if body.get("absolute_height") is None:
            body.pop("absolute_height", None)
        return body

    @model_validator(mode="after")
    def _shape(self) -> Self:
        size = self.parameters.grid_resolution + 1
        for name in ("height", "governing", "absolute_height"):
            grid = getattr(self, name)
            if grid is None:
                continue
            if len(grid) != size or any(len(row) != size for row in grid):
                raise ValueError(f"{name} must be a {size} x {size} grid")
        for hrow, grow in zip(self.height, self.governing, strict=True):
            for h, g in zip(hrow, grow, strict=True):
                if (h is None) != (g is None):
                    raise ValueError("a cell has a governing hill exactly when it has a height")
                if g is not None and not 0 <= g < len(self.source_ids):
                    raise ValueError("a governing index names a hill of this terrain")
        return self


def envelope_at(
    x: float,
    y: float,
    hills: Sequence[EnvelopeHill],
    sigma: float,
    cutoff: float | None,
    *,
    slots: Slots = NO_SLOTS,
) -> tuple[float, int] | None:
    """``z`` at ``(x, y)`` and the index of the hill that sets it; ``None`` when no hill's
    kernel reaches ``cutoff`` there. ``cutoff`` ``None``: every hill reaches every point.

    ``slots`` may replace the kernel (``f12.kernel``, ADR 0023): a hill's ``z`` is then the
    replaced kernel at its height, and whether it reaches ``cutoff`` is the kernel at height
    1, as the code's. Taking the maximum over hills stays this rule."""
    kernel = slots.get(KERNEL)
    two_sigma_sq = 2.0 * sigma * sigma
    best: tuple[float, int] | None = None
    for k, hill in enumerate(hills):
        if kernel is not None:
            d2 = (x - hill.x) ** 2 + (y - hill.y) ** 2
            if cutoff is not None and float(kernel(h=1.0, d2=d2, sigma=sigma)) < cutoff:
                continue
            z = float(kernel(h=hill.height, d2=d2, sigma=sigma))
            if best is None or z > best[0]:
                best = (z, k)
            continue
        w = math.exp(-((x - hill.x) ** 2 + (y - hill.y) ** 2) / two_sigma_sq)
        if cutoff is not None and w < cutoff:
            continue
        z = hill.height * w
        if best is None or z > best[0]:
            best = (z, k)
    return best


def object_envelope(
    hills: Sequence[EnvelopeHill],
    params: EnvelopeParameters,
    *,
    slots: Slots = NO_SLOTS,
    method: Literal["object_envelope", "framed_relative_envelope"] = "object_envelope",
) -> EnvelopeTerrain:
    """The F12 envelope of ``hills`` on ``params``' grid. See the section above; ``slots``
    as :func:`envelope_at`'s; ``method`` names what the hills' heights and grid are."""
    ids = tuple(h.entity_id for h in hills)
    if len(set(ids)) != len(ids):
        raise ValueError("envelope hill ids must be unique")
    xs, ys = params.axes()
    height: list[tuple[float | None, ...]] = []
    governing: list[tuple[int | None, ...]] = []
    for y in ys:
        cells = [
            envelope_at(x, y, hills, params.sigma, params.kernel_cutoff, slots=slots) for x in xs
        ]
        height.append(tuple(None if c is None else c[0] for c in cells))
        governing.append(tuple(None if c is None else c[1] for c in cells))
    return EnvelopeTerrain(
        method=method,
        parameters=params,
        source_ids=ids,
        height=tuple(height),
        governing=tuple(governing),
    )


def idw_at(
    x: float, y: float, hills: Sequence[EnvelopeHill], power: float
) -> tuple[float, int] | None:
    """The signed-off methodology's object terrain (``framed_relative_idw``) at ``(x, y)``, as
    the Sociomapy app interpolates it, and the index of the hill that weighs most there; ``None``
    without a hill. ``z`` is the hills' heights weighted by ``1 / d^power``: exactly a hill's
    height at its own point, beside a taller one too, and everywhere else a weighted mean of the
    hills, far from them as well."""
    num = den = 0.0
    best: tuple[float, int] | None = None
    for k, hill in enumerate(hills):
        d2 = (x - hill.x) ** 2 + (y - hill.y) ** 2
        if d2 == 0.0:
            return hill.height, k
        w = 1.0 / math.sqrt(d2) ** power
        num += w * hill.height
        den += w
        if best is None or w > best[0]:
            best = (w, k)
    if best is None:
        return None
    return num / den, best[1]


def idw_falloff_at(
    x: float,
    y: float,
    hills: Sequence[EnvelopeHill],
    sigma: float,
    power: float,
    *,
    slots: Slots = NO_SLOTS,
) -> tuple[float, int] | None:
    """The signed-off methodology's object terrain (``framed_relative_idw_falloff``) at
    ``(x, y)``, and the index of the hill that weighs most there; ``None`` without a hill.

    ``z = I F``: ``I`` the hills' heights weighted by ``1 / d^power`` (inverse-distance
    weighting, exact at a hill), ``F = max_j exp(-d_j^2 / 2 sigma^2)`` the hills' falloff. A
    hill's own point is exactly its height, beside a taller one too; between neighbours their
    heights blend; far from every hill the terrain falls to 0. The envelope's maximum lifted a
    hill next to a taller neighbour. ``slots`` may replace the kernel (``f12.kernel``): the
    falloff is then the replaced kernel at height 1, as :func:`envelope_at` reads it."""
    kernel = slots.get(KERNEL)
    two_sigma_sq = 2.0 * sigma * sigma
    num = den = fall = 0.0
    best: tuple[float, int] | None = None
    exact: tuple[float, int] | None = None
    for k, hill in enumerate(hills):
        d2 = (x - hill.x) ** 2 + (y - hill.y) ** 2
        g = (
            float(kernel(h=1.0, d2=d2, sigma=sigma))
            if kernel is not None
            else math.exp(-d2 / two_sigma_sq)
        )
        fall = max(fall, g)
        if d2 == 0.0:
            if exact is None:
                exact = (hill.height, k)
            continue
        w = 1.0 / math.sqrt(d2) ** power
        num += w * hill.height
        den += w
        if best is None or w > best[0]:
            best = (w, k)
    if exact is not None:
        return exact[0] * fall, exact[1]
    if best is None:
        return None
    return num / den * fall, best[1]


def object_idw(
    hills: Sequence[EnvelopeHill], params: EnvelopeParameters, power: float
) -> EnvelopeTerrain:
    """:func:`idw_at` over ``params``' grid (``framed_relative_idw``)."""
    ids = tuple(h.entity_id for h in hills)
    if len(set(ids)) != len(ids):
        raise ValueError("terrain hill ids must be unique")
    xs, ys = params.axes()
    height: list[tuple[float | None, ...]] = []
    governing: list[tuple[int | None, ...]] = []
    for y in ys:
        cells = [idw_at(x, y, hills, power) for x in xs]
        height.append(tuple(None if c is None else c[0] for c in cells))
        governing.append(tuple(None if c is None else c[1] for c in cells))
    return EnvelopeTerrain(
        method="framed_relative_idw",
        parameters=params,
        source_ids=ids,
        height=tuple(height),
        governing=tuple(governing),
    )


def object_idw_falloff(
    hills: Sequence[EnvelopeHill],
    params: EnvelopeParameters,
    power: float,
    *,
    slots: Slots = NO_SLOTS,
) -> EnvelopeTerrain:
    """:func:`idw_falloff_at` over ``params``' grid (``framed_relative_idw_falloff``)."""
    ids = tuple(h.entity_id for h in hills)
    if len(set(ids)) != len(ids):
        raise ValueError("terrain hill ids must be unique")
    xs, ys = params.axes()
    height: list[tuple[float | None, ...]] = []
    governing: list[tuple[int | None, ...]] = []
    for y in ys:
        cells = [idw_falloff_at(x, y, hills, params.sigma, power, slots=slots) for x in xs]
        height.append(tuple(None if c is None else c[0] for c in cells))
        governing.append(tuple(None if c is None else c[1] for c in cells))
    return EnvelopeTerrain(
        method="framed_relative_idw_falloff",
        parameters=params,
        source_ids=ids,
        height=tuple(height),
        governing=tuple(governing),
    )
