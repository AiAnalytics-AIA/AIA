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
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .metrics import NormalizationMode, build_normalizer

__all__ = [
    "TERRAIN66_OBJECT",
    "TERRAIN66_RESPONDENT",
    "TerrainField",
    "TerrainMode",
    "TerrainParameters",
    "TerrainSource",
    "compute_terrain",
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
