"""Native 18.6.6 workspace geometry, with explicit unsupported-data outcomes.

Port of visualization_lab respondent_map_payload/object_relationship_payload.
Unweighted native views are separate from the research engine's weighted
relationships and unfolding. Undefined pairs refuse object geometry rather than
copying the reference's neutral substitution. No p-values are inferred.
"""

from __future__ import annotations

import hashlib
import math
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from ..pipeline import fingerprint
from .metrics import NormalizationMode
from .models import RatingsMatrix
from .terrain import (
    TERRAIN66_OBJECT,
    TERRAIN66_RESPONDENT,
    TerrainField,
    TerrainMode,
    TerrainSource,
    compute_terrain,
)

WORKSPACE_VERSION = "aia-native-workspace-1"


class Point(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    x: float
    y: float
    status: Literal["POSITIONED", "UNDETERMINED"] = "POSITIONED"
    ratings: tuple[float | None, ...] = ()


class Workspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    version: str = WORKSPACE_VERSION
    input_fingerprint: str
    status: Literal["AVAILABLE", "UNSUPPORTED"]
    reason: str | None = None
    weighting: Literal["UNWEIGHTED"] = "UNWEIGHTED"
    respondent_method: str = "native_1866_barycentre_jitter"
    object_method: str = "native_1866_mutual_strength_800_radius38"
    people: tuple[Point, ...] = ()
    anchors: tuple[Point, ...] = ()
    objects: tuple[Point, ...] = ()
    pair_n: tuple[tuple[int, ...], ...] = ()
    relations: tuple[tuple[float | None, ...], ...] = ()
    object_reason: str | None = None
    metrics: dict[str, tuple[float | None, ...]] = {}
    respondent_terrain: TerrainField | None = None
    object_terrains: dict[str, TerrainField] = {}


def _jitter(key: str) -> tuple[float, float]:
    h = hashlib.sha256(key.encode()).digest()
    angle = int.from_bytes(h[:4], "big") / 2**32 * 2 * math.pi
    radius = (int.from_bytes(h[4:8], "big") / 2**32) ** 0.5 * 1.55
    return math.cos(angle) * radius, math.sin(angle) * radius


def _circle(n: int, radius: float) -> list[list[float]]:
    return [
        [
            radius * math.cos(2 * math.pi * i / n - math.pi / 2),
            radius * math.sin(2 * math.pi * i / n - math.pi / 2),
        ]
        for i in range(n)
    ]


def _object_positions(matrix: list[list[float | None]]) -> list[list[float]]:
    n = len(matrix)
    pos = _circle(n, 28)
    strength = max(1.0, max(cast(float, matrix[i][j]) for i in range(n) for j in range(i + 1, n)))
    for iteration in range(800):
        delta = [[0.0, 0.0] for _ in pos]
        step = 0.1 * (1 - iteration / 1000)
        for i in range(n):
            for j in range(i + 1, n):
                value = matrix[i][j]
                assert value is not None  # caller refuses every undefined pair
                target = 14 + 46 * (1 - value / strength)
                dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                distance = math.hypot(dx, dy) or 1e-6
                force = (distance - target) * step * 0.02
                for axis, d in enumerate((dx, dy)):
                    change = force * d / distance
                    delta[i][axis] += change
                    delta[j][axis] -= change
        for p, movement in zip(pos, delta, strict=True):
            p[0] += movement[0]
            p[1] += movement[1]
    means = [sum(p[k] for p in pos) / n for k in (0, 1)]
    pos = [[p[k] - means[k] for k in (0, 1)] for p in pos]
    radius = max(1.0, max(math.hypot(*p) for p in pos))
    return [[round(v * 38 / radius, 5) for v in p] for p in pos]


def _terrain(
    points: tuple[Point, ...], values: tuple[float | None, ...], *, density: bool, metric: str
) -> TerrainField:
    return compute_terrain(
        TerrainMode.RESPONDENT_DENSITY if density else TerrainMode.OBJECT_METRIC,
        [
            TerrainSource(entity_id=p.id, x=p.x, y=p.y, height=v, colour=v)
            for p, v in zip(points, values, strict=True)
            if v is not None
        ],
        TERRAIN66_RESPONDENT if density else TERRAIN66_OBJECT,
        metric_id=metric,
        normalization=NormalizationMode.RANGE,
        bounds=None,
    )


def compute_workspace(ratings: RatingsMatrix, scale: tuple[int, int]) -> Workspace:
    """Prepare bounded, deterministic 1-10 native views from frozen input rows.

    Low-support/constant pairs stay None. Geometry is not meaningful for them.
    Undetermined respondents retain the legacy perimeter placement and status.
    """
    digest = fingerprint(
        {"ratings": ratings.model_dump(mode="json"), "scale": scale, "version": WORKSPACE_VERSION}
    )
    if scale != (1, 10):
        return Workspace(input_fingerprint=digest, status="UNSUPPORTED", reason="SCALE_NOT_1_10")
    n, count = len(ratings.object_ids), len(ratings.respondent_ids)
    if count > 2000 or n > 32:
        return Workspace(
            input_fingerprint=digest, status="UNSUPPORTED", reason="WORKSPACE_SIZE_LIMIT"
        )
    if any(v is not None and not 1 <= v <= 10 for row in ratings.values for v in row):
        raise ValueError("native workspace ratings must be on the declared 1-10 scale")
    reference = _circle(n, 42)
    anchors = tuple(
        Point(id=key, x=round(p[0], 5), y=round(p[1], 5))
        for key, p in zip(ratings.object_ids, reference, strict=True)
    )
    people = []
    for i, (key, row) in enumerate(zip(ratings.respondent_ids, ratings.values, strict=True)):
        weights = [max(0.0, v - 5) if v is not None else 0.0 for v in row]
        total = sum(weights)
        dx, dy = _jitter(key)
        status: Literal["POSITIONED", "UNDETERMINED"] = "POSITIONED"
        if total > 1e-9:
            x, y = (
                sum(w * p[k] for w, p in zip(weights, reference, strict=True)) / total
                for k in (0, 1)
            )
        else:
            status = "UNDETERMINED"
            angle = hashlib.md5(key.encode(), usedforsecurity=False).digest()[0] / 255 * 2 * math.pi
            radius = 54 + 3 * ((i % 11) / 10)
            x, y = radius * math.cos(angle), radius * math.sin(angle)
        people.append(
            Point(id=key, x=round(x + dx, 5), y=round(y + dy, 5), status=status, ratings=row)
        )
    matrix: list[list[float | None]] = [[0.0] * n for _ in range(n)]
    support = [[0] * n for _ in range(n)]
    missing = False
    for i in range(n):
        for j in range(i + 1, n):
            pairs = [
                (row[i], row[j])
                for row in ratings.values
                if row[i] is not None and row[j] is not None
            ]
            support[i][j] = support[j][i] = len(pairs)
            value = None
            if len(pairs) >= 5:
                a = [cast(float, p[0]) for p in pairs]
                b = [cast(float, p[1]) for p in pairs]
                ma, mb = sum(a) / len(a), sum(b) / len(b)
                va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
                if (va / len(a)) ** 0.5 > 1e-12 and (vb / len(b)) ** 0.5 > 1e-12:
                    corr = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / math.sqrt(
                        va * vb
                    )
                    value = 1 + 9 * (max(-1.0, min(1.0, corr)) + 1) / 2
            missing |= value is None
            matrix[i][j] = matrix[j][i] = value
    columns = [
        [cast(float, row[j]) for row in ratings.values if row[j] is not None] for j in range(n)
    ]
    means = tuple(round(sum(c) / len(c), 4) if c else None for c in columns)
    metrics: dict[str, tuple[float | None, ...]] = {
        "mean_rating": means,
        "support_n": tuple(float(len(c)) for c in columns),
    }
    objects: tuple[Point, ...] = ()
    if not missing:
        classic = tuple(sum(cast(float, v) for v in row) * 2 for row in matrix)
        mean = sum(classic) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in classic) / n)
        metrics["relation_classic"] = tuple(round(v, 4) for v in classic)
        metrics["relation_norm"] = tuple(
            round(50 + 10 * (v - mean) / sd, 4) if sd >= 1e-12 else 50.0 for v in classic
        )
        objects = tuple(
            Point(id=key, x=p[0], y=p[1])
            for key, p in zip(ratings.object_ids, _object_positions(matrix), strict=True)
        )
    return Workspace(
        input_fingerprint=digest,
        status="AVAILABLE",
        people=tuple(people),
        anchors=anchors,
        objects=objects,
        pair_n=tuple(tuple(row) for row in support),
        relations=tuple(tuple(None if v is None else round(v, 4) for v in row) for row in matrix),
        object_reason="INSUFFICIENT_PAIR_SUPPORT_OR_VARIANCE" if missing else None,
        metrics=metrics,
        respondent_terrain=_terrain(
            tuple(people), tuple(1.0 for _ in people), density=True, metric="density"
        ),
        object_terrains={
            key: _terrain(objects, values, density=False, metric=key)
            for key, values in metrics.items()
        }
        if objects
        else {},
    )
