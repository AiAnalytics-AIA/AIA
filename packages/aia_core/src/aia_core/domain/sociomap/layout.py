"""Declared Sociomap layout algorithms: row-conditional unfolding, never auto-selected.

The reference chooses its layout algorithm by probing the host::

    if method in {"auto", "r_smacof"} and shutil.which("Rscript"):
        try: return fit_r_smacof(df, seed=seed)
        except Exception: ...            # silently falls through
    return fit_python_unfolding(df, seed=seed)

so one study yields different coordinates on different machines. Here the
algorithm is a spec field, looked up in :data:`LAYOUT_ALGORITHMS`, and an
algorithm this engine cannot run raises :class:`LayoutUnavailable` naming why.
There is no ``auto``, no probing and no fallback.

Three algorithms are known:

``python_weighted_unfolding``
    The reference's Python branch (fixture F4). **Not implemented**: its source
    is in the withheld reference archive, and no candidate reconstruction
    reproduces F4. Refused.
``r_smacof_unfolding``
    The reference's R branch, R ``smacof::unfolding``. **Not implemented** and
    **uncharacterised** (``REF-GAP-SOCIO-R-SMACOF``). Refused.
``aia_rowcond_unfolding_v1``
    Implemented here. Row-conditional metric unfolding by alternating block
    majorisation, fully specified below, deterministic without a seed. It is an
    AIA algorithm; it makes **no parity claim** against either reference branch.

``aia_rowcond_unfolding_v1``, precisely
---------------------------------------

Input: non-negative dissimilarities ``delta[i][j]`` (respondent ``i``, object
``j``), missing cells ``None``; weight ``w = 1`` on observed cells, ``0``
otherwise. See :func:`scale_top_dissimilarity` for the ratings -> dissimilarity
step.

1. **Row-conditional ratio disparities.** ``dhat[i][j] = b_i * delta[i][j]``,
   one free scale ``b_i`` per respondent: dissimilarities are comparable within
   a respondent's row, not across rows (respondents use the scale differently).
   One global normalisation, ``sum_i b_i^2 |delta_i|^2 = C`` with ``C`` the
   number of observed cells, rules out the collapsed solution.
2. **Stress.** ``sigma = sum w (dhat - d)^2``, reported normalised as
   ``sigma / C`` and as Kruskal stress-1 ``sqrt(sigma / sum w d^2)``.
3. **Initialise.** ``b_i`` common. Objects by classical scaling of their profile
   distances ``D[j][k]^2 = mean_i (dhat[i][j] - dhat[i][k])^2`` over co-observing
   rows -- a pair nobody co-rated takes the mean of the known ones, and the
   co-rating graph must be connected -- eigenvectors by cyclic Jacobi;
   respondents at the mean of the objects weighted by
   ``max_k delta[i][k] - delta[i][j]`` (preferred objects pull harder); then one
   least-squares scale against ``dhat``.
4. **Iterate** three exact block steps, none of which can increase ``sigma``:
   respondents given objects (``x_i <- mean_j [y_j + dhat_ij (x_i - y_j) / d_ij]``),
   objects given respondents (symmetrically), then ``b`` given the
   configuration (``b_i`` proportional to ``delta_i . d_i / |delta_i|^2``,
   renormalised). Stop when ``sigma / C`` improves by less than
   ``convergence_tolerance``, or after ``max_iterations``.
   The start is single and deterministic, so like any unfolding the fit can
   stop in a local minimum: low stress does not prove the geometry is the only
   one the data allow. ``stress_1`` is reported for exactly that judgement.
5. **Fix the gauge.** Translate the object centroid to the origin, rotate onto
   the objects' principal axes, reflect each axis so the objects' third moment
   on it is positive. Distances -- and so stress -- are unchanged, and two runs
   compare coordinate by coordinate.

Everything is pure Python in a fixed order of operations, so the result is the
same on every host; that is the property the reference's layout lacked.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

__all__ = [
    "LAYOUT_ALGORITHMS",
    "AlgorithmStatus",
    "LayoutAlgorithm",
    "LayoutAlgorithmInfo",
    "LayoutUnavailable",
    "ProcrustesFit",
    "UnfoldingDesignError",
    "UnfoldingParameters",
    "UnfoldingResult",
    "fit_rowcond_unfolding",
    "procrustes_align",
    "require_layout_algorithm",
    "scale_top_dissimilarity",
    "stress_1",
]

Point = tuple[float, float]
Cells = Sequence[Sequence[float | None]]


class LayoutAlgorithm(StrEnum):
    """Layout algorithm identifiers. Values are recorded in specs and artifacts."""

    AIA_ROWCOND_UNFOLDING_V1 = "aia_rowcond_unfolding_v1"
    LEGACY_PYTHON_WEIGHTED_UNFOLDING = "python_weighted_unfolding"
    LEGACY_R_SMACOF_UNFOLDING = "r_smacof_unfolding"


class AlgorithmStatus(StrEnum):
    """Whether this engine can run an algorithm."""

    IMPLEMENTED = "implemented"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LayoutAlgorithmInfo:
    """What the engine knows about one algorithm, and why it can or cannot run it."""

    algorithm: LayoutAlgorithm
    status: AlgorithmStatus
    parity: str
    reason: str


LAYOUT_ALGORITHMS: dict[LayoutAlgorithm, LayoutAlgorithmInfo] = {
    LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1: LayoutAlgorithmInfo(
        LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1,
        AlgorithmStatus.IMPLEMENTED,
        parity="none claimed; pinned by its own golden fixture",
        reason="AIA row-conditional metric unfolding, specified in this module",
    ),
    LayoutAlgorithm.LEGACY_PYTHON_WEIGHTED_UNFOLDING: LayoutAlgorithmInfo(
        LayoutAlgorithm.LEGACY_PYTHON_WEIGHTED_UNFOLDING,
        AlgorithmStatus.UNAVAILABLE,
        parity="F4, NUMERICAL 1e-6 -- not met",
        reason=(
            "the reference's fit_python_unfolding source is in the withheld reference "
            "archive (REF-WITHHELD-REFERENCE-ARCHIVE) and cannot be reconstructed from F4"
        ),
    ),
    LayoutAlgorithm.LEGACY_R_SMACOF_UNFOLDING: LayoutAlgorithmInfo(
        LayoutAlgorithm.LEGACY_R_SMACOF_UNFOLDING,
        AlgorithmStatus.UNAVAILABLE,
        parity="UNCHARACTERIZED -- no R fixture exists",
        reason=(
            "the reference's R smacof branch has no golden fixture (REF-GAP-SOCIO-R-SMACOF); "
            "R numerical parity cannot be claimed or tested"
        ),
    ),
}


class LayoutUnavailable(ValueError):
    """The declared layout algorithm cannot be run by this engine. Nothing substitutes."""

    def __init__(self, algorithm: str, reason: str) -> None:
        self.algorithm = algorithm
        self.reason = reason
        super().__init__(
            f"layout algorithm {algorithm!r} is unavailable and no other algorithm is "
            f"substituted: {reason}"
        )


def require_layout_algorithm(algorithm: str) -> LayoutAlgorithm:
    """Resolve a declared algorithm id, or raise :class:`LayoutUnavailable`."""
    try:
        chosen = LayoutAlgorithm(algorithm)
    except ValueError:
        known = ", ".join(sorted(a.value for a in LayoutAlgorithm))
        raise LayoutUnavailable(algorithm, f"unknown algorithm; known: {known}") from None
    info = LAYOUT_ALGORITHMS[chosen]
    if info.status is not AlgorithmStatus.IMPLEMENTED:
        raise LayoutUnavailable(chosen.value, info.reason)
    return chosen


class UnfoldingDesignError(ValueError):
    """The ratings cannot be unfolded as declared (too few objects, a disconnected design)."""


class UnfoldingParameters(BaseModel):
    """Parameters of ``aia_rowcond_unfolding_v1``. Every one is required."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimensions: int
    max_iterations: int
    convergence_tolerance: float

    @field_validator("dimensions", "max_iterations", "convergence_tolerance", mode="before")
    @classmethod
    def _not_boolean(cls, v: object) -> object:
        # pydantic would coerce True to 1 before the checks below could see it.
        if isinstance(v, bool):
            raise ValueError("expected a number, not a boolean")
        return v

    @field_validator("dimensions")
    @classmethod
    def _two_d(cls, v: int) -> int:
        if v != 2:
            raise ValueError("aia_rowcond_unfolding_v1 places points in exactly 2 dimensions")
        return v

    @field_validator("max_iterations")
    @classmethod
    def _iterations(cls, v: int) -> int:
        if not 1 <= v <= 100_000:
            raise ValueError("max_iterations must be an integer in [1, 100000]")
        return v

    @field_validator("convergence_tolerance")
    @classmethod
    def _tolerance(cls, v: float) -> float:
        if not (math.isfinite(v) and 0 < v < 1):
            raise ValueError("convergence_tolerance must be in (0, 1)")
        return float(v)


@dataclass(frozen=True, slots=True)
class UnfoldingResult:
    """Gauge-fixed coordinates in layout units, with the fit diagnostics."""

    respondent_xy: tuple[Point, ...]
    object_xy: tuple[Point, ...]
    row_scales: tuple[float, ...]
    stress_1: float
    normalized_stress: float
    iterations: int
    converged: bool
    principal_axis_gap: float


# ------------------------------------------------------------------ targets --


def scale_top_dissimilarity(
    values: Cells, scale_top: float
) -> tuple[tuple[float | None, ...], ...]:
    """Preference -> dissimilarity: ``delta_ij = scale_top - x_ij`` over observed cells.

    A higher rating is a stronger preference and so a smaller distance; only the
    top of the rating scale itself means "at the object". Ratings above
    ``scale_top`` are refused -- they would give a negative distance, and
    clipping them would silently change the data.
    """
    out: list[tuple[float | None, ...]] = []
    for i, row in enumerate(values):
        cells: list[float | None] = []
        for j, v in enumerate(row):
            if v is None:
                cells.append(None)
                continue
            if float(v) > scale_top:
                raise UnfoldingDesignError(
                    f"rating [{i}][{j}] = {v!r} is above the declared scale top {scale_top!r}"
                )
            cells.append(scale_top - float(v))
        out.append(tuple(cells))
    return tuple(out)


# ------------------------------------------------------------- linear algebra --


def _jacobi_eigen(matrix: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    """Eigen-decompose a small symmetric matrix by cyclic Jacobi rotations.

    Returns eigenvalues descending and eigenvectors as columns, each vector's
    largest-magnitude component made positive (first index on ties), so the
    result is fully determined by the input.
    """
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _sweep in range(100):
        off = math.fsum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-30:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    order = sorted(range(n), key=lambda i: (-a[i][i], i))
    values = [a[i][i] for i in order]
    vectors = [[v[k][i] for i in order] for k in range(n)]
    for col in range(n):
        column = [vectors[k][col] for k in range(n)]
        pivot = max(range(n), key=lambda k: (abs(column[k]), -k))
        if column[pivot] < 0:
            for k in range(n):
                vectors[k][col] = -vectors[k][col]
    return values, vectors


# ------------------------------------------------------------------- stress --


def stress_1(
    disparities: Cells, respondent_xy: Sequence[Point], object_xy: Sequence[Point]
) -> float:
    """Kruskal stress-1 over observed cells: ``sqrt(sum (dhat - d)^2 / sum d^2)``."""
    num: list[float] = []
    den: list[float] = []
    for i, row in enumerate(disparities):
        xi, yi = respondent_xy[i]
        for j, t in enumerate(row):
            if t is None:
                continue
            d = math.hypot(xi - object_xy[j][0], yi - object_xy[j][1])
            num.append((float(t) - d) ** 2)
            den.append(d * d)
    total = math.fsum(den)
    return math.sqrt(math.fsum(num) / total) if total > 0 else math.inf


# One respondent's observed cells, as (object index, delta).
RowCells = list[tuple[int, float]]


def _disparities(rows: list[RowCells], b: list[float]) -> list[RowCells]:
    return [[(j, bi * v) for j, v in row] for row, bi in zip(rows, b, strict=True)]


def _raw_stress(dhat: list[RowCells], xs: list[Point], ys: list[Point]) -> float:
    acc: list[float] = []
    for i, row in enumerate(dhat):
        xi, yi = xs[i]
        for j, t in row:
            acc.append((t - math.hypot(xi - ys[j][0], yi - ys[j][1])) ** 2)
    return math.fsum(acc)


# --------------------------------------------------------------------- init --


def _initial_objects(dhat: list[RowCells], m: int) -> list[Point]:
    dense: list[list[float | None]] = []
    for row in dhat:
        cells: list[float | None] = [None] * m
        for j, t in row:
            cells[j] = t
        dense.append(cells)
    # Squared profile distance for every co-rated pair. A pair nobody rated
    # together takes the mean of the known ones -- a neutral start, measured to
    # recover planted geometry far better than a shortest path through co-rated
    # pairs, which overestimates and leads the fit into a reflected block. The
    # design must still be connected: an isolated group of objects has no
    # position relative to the rest, whatever the start.
    known: list[list[float | None]] = [[None] * m for _ in range(m)]
    for j in range(m):
        known[j][j] = 0.0
        for k in range(j + 1, m):
            diffs = [
                (a - c) ** 2
                for a, c in ((cells[j], cells[k]) for cells in dense)
                if a is not None and c is not None
            ]
            if diffs:
                known[j][k] = known[k][j] = math.fsum(diffs) / len(diffs)
    reached = {0}
    frontier = [0]
    while frontier:
        j = frontier.pop()
        for k in range(m):
            if k not in reached and known[j][k] is not None:
                reached.add(k)
                frontier.append(k)
    if len(reached) != m:
        isolated = sorted(set(range(m)) - reached)
        raise UnfoldingDesignError(
            f"objects {isolated} are not connected to object 0 through any chain of "
            "co-rating respondents; the design is disconnected and cannot be placed "
            "on one map"
        )
    observed = [v for j in range(m) for k in range(m) if j != k and (v := known[j][k]) is not None]
    neutral = math.fsum(observed) / len(observed)
    d2 = [[neutral if v is None else v for v in row] for row in known]
    row_mean = [math.fsum(r) / m for r in d2]
    grand = math.fsum(row_mean) / m
    b = [
        [-0.5 * (d2[j][k] - row_mean[j] - row_mean[k] + grand) for k in range(m)] for j in range(m)
    ]
    values, vectors = _jacobi_eigen(b)
    scales = [math.sqrt(max(values[a], 0.0)) for a in range(2)]
    return [(vectors[j][0] * scales[0], vectors[j][1] * scales[1]) for j in range(m)]


def _initial_respondents(rows: list[RowCells], ys: list[Point]) -> list[Point]:
    xs: list[Point] = []
    for row in rows:
        top = max(v for _, v in row)
        weights = [(j, top - v) for j, v in row]
        total = math.fsum(w for _, w in weights)
        if total <= 0:  # every observed cell equally preferred: start at their centroid
            weights = [(j, 1.0) for j, _ in row]
            total = float(len(row))
        xs.append(
            (
                math.fsum(w * ys[j][0] for j, w in weights) / total,
                math.fsum(w * ys[j][1] for j, w in weights) / total,
            )
        )
    return xs


def _least_squares_scale(dhat: list[RowCells], xs: list[Point], ys: list[Point]) -> float:
    td: list[float] = []
    dd: list[float] = []
    for i, row in enumerate(dhat):
        for j, t in row:
            d = math.hypot(xs[i][0] - ys[j][0], xs[i][1] - ys[j][1])
            td.append(t * d)
            dd.append(d * d)
    denominator = math.fsum(dd)
    return math.fsum(td) / denominator if denominator > 0 else 1.0


# ---------------------------------------------------------------- iteration --


def _majorise(movers: list[Point], anchors: list[Point], cells: list[RowCells]) -> list[Point]:
    """One exact majorisation step for every mover, holding the anchors fixed."""
    out: list[Point] = []
    for i, (px, py) in enumerate(movers):
        sx: list[float] = []
        sy: list[float] = []
        for j, t in cells[i]:
            ax, ay = anchors[j]
            dx, dy = px - ax, py - ay
            d = math.hypot(dx, dy)
            ratio = t / d if d > 0 else 0.0
            sx.append(ax + ratio * dx)
            sy.append(ay + ratio * dy)
        count = len(cells[i])
        out.append((math.fsum(sx) / count, math.fsum(sy) / count))
    return out


def _update_scales(
    rows: list[RowCells], norms: list[float], total: float, xs: list[Point], ys: list[Point]
) -> list[float]:
    """Exact minimiser of stress over the row scales under the global normalisation."""
    ratios: list[float] = []
    for i, row in enumerate(rows):
        xi, yi = xs[i]
        p = math.fsum(v * math.hypot(xi - ys[j][0], yi - ys[j][1]) for j, v in row)
        ratios.append(p / norms[i])
    kappa_sq = math.fsum(r * r * q for r, q in zip(ratios, norms, strict=True))
    if kappa_sq <= 0:
        return [math.sqrt(total / math.fsum(norms))] * len(rows)
    kappa = math.sqrt(total / kappa_sq)
    return [kappa * r for r in ratios]


def _fix_gauge(xs: list[Point], ys: list[Point]) -> tuple[list[Point], list[Point], float]:
    m = len(ys)
    cx = math.fsum(p[0] for p in ys) / m
    cy = math.fsum(p[1] for p in ys) / m
    ys = [(x - cx, y - cy) for x, y in ys]
    xs = [(x - cx, y - cy) for x, y in xs]
    sxx = math.fsum(x * x for x, _ in ys) / m
    syy = math.fsum(y * y for _, y in ys) / m
    sxy = math.fsum(x * y for x, y in ys) / m
    values, vectors = _jacobi_eigen([[sxx, sxy], [sxy, syy]])
    (a, b), (c, d) = (vectors[0][0], vectors[1][0]), (vectors[0][1], vectors[1][1])

    def rotate(p: Point) -> Point:
        return (a * p[0] + b * p[1], c * p[0] + d * p[1])

    ys = [rotate(p) for p in ys]
    xs = [rotate(p) for p in xs]
    signs: list[float] = []
    for axis in range(2):
        third = math.fsum(p[axis] ** 3 for p in ys)
        if abs(third) > 1e-12:
            signs.append(1.0 if third > 0 else -1.0)
        else:
            lead = next((p[axis] for p in ys if abs(p[axis]) > 1e-12), 1.0)
            signs.append(1.0 if lead > 0 else -1.0)
    ys = [(p[0] * signs[0], p[1] * signs[1]) for p in ys]
    xs = [(p[0] * signs[0], p[1] * signs[1]) for p in xs]
    total = values[0] + values[1]
    gap = (values[0] - values[1]) / total if total > 0 else 0.0
    return xs, ys, gap


def fit_rowcond_unfolding(delta: Cells, params: UnfoldingParameters) -> UnfoldingResult:
    """Run ``aia_rowcond_unfolding_v1`` on a respondents x objects dissimilarity matrix.

    Every row must be placeable -- at least two observed cells, non-negative,
    not all zero; the engine excludes other rows *before* calling this, because
    they carry no position information and placing them anyway would stamp a
    guess. Raises :class:`UnfoldingDesignError` when the input cannot be placed.
    """
    n = len(delta)
    if n < 1:
        raise UnfoldingDesignError("unfolding needs at least one placeable respondent")
    m = len(delta[0])
    if m < 3 or any(len(row) != m for row in delta):
        raise UnfoldingDesignError("unfolding needs a rectangular matrix of at least 3 objects")
    rows: list[RowCells] = []
    for i, raw in enumerate(delta):
        row = [(j, float(v)) for j, v in enumerate(raw) if v is not None]
        if len(row) < 2 or min(v for _, v in row) < 0 or max(v for _, v in row) == 0:
            raise UnfoldingDesignError(
                f"row {i} is not placeable (needs >= 2 observed, non-negative, not-all-zero cells)"
            )
        rows.append(row)
    for j in range(m):
        if all(raw[j] is None for raw in delta):
            raise UnfoldingDesignError(f"object {j} is rated by no placeable respondent")

    columns: list[list[int]] = [[] for _ in range(m)]
    for i, row in enumerate(rows):
        for j, _ in row:
            columns[j].append(i)
    norms = [math.fsum(v * v for _, v in row) for row in rows]
    total = float(sum(len(row) for row in rows))

    b = [math.sqrt(total / math.fsum(norms))] * n
    dhat = _disparities(rows, b)
    ys = _initial_objects(dhat, m)
    xs = _initial_respondents(rows, ys)
    k = _least_squares_scale(dhat, xs, ys)
    xs = [(k * x, k * y) for x, y in xs]
    ys = [(k * x, k * y) for x, y in ys]

    def by_object(dh: list[RowCells]) -> list[RowCells]:
        lookup = [dict(row) for row in dh]
        return [[(i, lookup[i][j]) for i in columns[j]] for j in range(m)]

    previous = _raw_stress(dhat, xs, ys) / total
    iterations = 0
    converged = False
    for iterations in range(1, params.max_iterations + 1):  # noqa: B007
        xs = _majorise(xs, ys, dhat)
        ys = _majorise(ys, xs, by_object(dhat))
        b = _update_scales(rows, norms, total, xs, ys)
        dhat = _disparities(rows, b)
        current = _raw_stress(dhat, xs, ys) / total
        improvement = previous - current
        previous = current
        if improvement < params.convergence_tolerance:
            converged = True
            break

    xs, ys, gap = _fix_gauge(xs, ys)
    dense: list[list[float | None]] = []
    for row in dhat:
        cells: list[float | None] = [None] * m
        for j, t in row:
            cells[j] = t
        dense.append(cells)
    return UnfoldingResult(
        respondent_xy=tuple(xs),
        object_xy=tuple(ys),
        row_scales=tuple(b),
        stress_1=stress_1(dense, xs, ys),
        normalized_stress=previous,
        iterations=iterations,
        converged=converged,
        principal_axis_gap=gap,
    )


# --------------------------------------------------------------- comparison --


@dataclass(frozen=True, slots=True)
class ProcrustesFit:
    """``target`` aligned onto ``reference`` by translation, rotation/reflection, scale."""

    aligned: tuple[Point, ...]
    rmsd: float
    max_distance: float
    scale: float
    reflected: bool


def procrustes_align(
    reference: Sequence[Point], target: Sequence[Point], *, allow_scale: bool
) -> ProcrustesFit:
    """Orthogonal Procrustes in 2-D, closed form; the better of rotation and reflection.

    For comparing two layouts whose gauge differs -- the parity comparison the
    engine document prescribes for an algorithm that leaves rotation and
    reflection free. Compare pairwise distances as well: an alignment alone can
    make different geometry look close.
    """
    if len(reference) != len(target) or not reference:
        raise ValueError("procrustes needs two non-empty configurations of equal size")
    n = len(reference)
    rcx = math.fsum(p[0] for p in reference) / n
    rcy = math.fsum(p[1] for p in reference) / n
    tcx = math.fsum(p[0] for p in target) / n
    tcy = math.fsum(p[1] for p in target) / n
    ref = [(x - rcx, y - rcy) for x, y in reference]
    tgt = [(x - tcx, y - tcy) for x, y in target]
    best: ProcrustesFit | None = None
    for reflected in (False, True):
        src = [(x, -y) for x, y in tgt] if reflected else tgt
        num = math.fsum(sx * ry - sy * rx for (sx, sy), (rx, ry) in zip(src, ref, strict=True))
        dot = math.fsum(sx * rx + sy * ry for (sx, sy), (rx, ry) in zip(src, ref, strict=True))
        theta = math.atan2(num, dot)
        c, s = math.cos(theta), math.sin(theta)
        rotated = [(c * x - s * y, s * x + c * y) for x, y in src]
        norm = math.fsum(x * x + y * y for x, y in rotated)
        scale = 1.0
        if allow_scale and norm > 0:
            scale = (
                math.fsum(x * rx + y * ry for (x, y), (rx, ry) in zip(rotated, ref, strict=True))
                / norm
            )
        aligned = tuple((scale * x + rcx, scale * y + rcy) for x, y in rotated)
        dists = [
            math.hypot(ax - rx, ay - ry)
            for (ax, ay), (rx, ry) in zip(aligned, reference, strict=True)
        ]
        fit = ProcrustesFit(
            aligned=aligned,
            rmsd=math.sqrt(math.fsum(d * d for d in dists) / n),
            max_distance=max(dists),
            scale=scale,
            reflected=reflected,
        )
        if best is None or fit.rmsd < best.rmsd:
            best = fit
    if best is None:  # unreachable: the loop always runs twice
        raise RuntimeError("procrustes produced no fit")
    return best
