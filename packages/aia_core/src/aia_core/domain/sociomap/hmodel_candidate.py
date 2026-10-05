"""``aia_hmodel_candidate_v1``: an experimental AIA H-Model layout. Not SOMECS's method.

SOMECS reports an H-Model's fit as a Spearman correlation (register SOMECS-H3) and the method
reads a map ordinally (QED-H2); how SOMECS *searches* for a layout is not documented (AIA-H8,
open). This module is AIA's own candidate, specified in
``docs/architecture/sociomapping-hmodel.md`` § 4 and registered as AIA-H9 (proposed). Every
result says so: ``status`` is ``EXPERIMENTAL_AIA``, and nothing here can make it otherwise.

**Objective, versioned as** :data:`CANDIDATE_METHOD`. Maximise the reported accuracy
(:func:`~aia_core.domain.sociomap.hmodel.hmodel_accuracy`, :data:`EVALUATOR_VERSION`): the
Spearman correlation over every defined ordered pair ``(r, s)`` between the relation
``v_rs`` and the negated distance ``-d_rs``. Undefined pairs are not observations. All points
weigh the same (SOMECS's per-point importance, help p. 56, is not modelled).

**Search.** Elements are processed in a canonical order (sorted ids), so the same relations
in another order give the same map; results are reported in the caller's order. From each
start:

1. *Smooth.* Gradient ascent on ``corr(L, -D)``: the Pearson correlation between the fixed
   average ranks ``L`` of the defined relations and the negated distances. Differentiable,
   with the accuracy's invariances. Backtracking step: x1.2 on success, /2 on failure.
2. Two branches from the smooth layout, the better one kept (ties to the first):
   *direct* -- straight to the exact phase; *ordinal* -- first Kruskal-style ordinal stress
   (isotonic targets over the relation order, made strictly increasing by a small gap so a
   violated pair cannot settle into a tie), then the exact phase. The classical MDS start
   also refines its raw start (branch *start*), so the result never scores below that
   baseline.
3. *Exact.* Local search on the accuracy itself: each point in turn tries ``directions``
   moves of the current step and takes the best that raises the accuracy; when a sweep moves
   nothing the step halves, down to ``min_step``. Between rounds, a *repair* step pushes on
   the pairs still out of order (a hinge with a small margin), kept only if the accuracy
   rises.

Why both branches: on planted data (relations a strictly decreasing function of planted
distances) the ordinal branch reaches accuracy 1 where the direct one stalls a pair short;
on SOMECS's fig. 22 matrix the direct branch from the classical MDS start finds the higher
accuracy. Neither alone did both (measured while building; ``docs/architecture/
sociomapping-hmodel.md`` § 4 records the numbers).

**Starts.** Classical MDS on a dissimilarity built from the relations' ranks (scale-free, so
signed correlations need no conversion; a pair undefined both ways takes the mean
dissimilarity, for this start only) plus ``random_starts`` uniform starts from
``random.Random(seed + k)``. The highest final accuracy wins; ties go to the earliest start.
Every start's accuracies are kept, so the spread of local optima is visible. The classical
MDS start's own accuracy is reported as a baseline.

**Elements that cannot be placed.** An element with no defined relation to any other (every
answer equal, so no correlation) is not placed. It is listed in ``unplaced`` with the reason,
never dropped silently and never put at a default position.

**Frame (SOMECS-H7).** Centred, rotated onto principal axes, each axis reflected so its third
moment is non-negative, scaled uniformly into ``[0.05, 0.95]``. The accuracy is unchanged.

**Determinism.** Pure Python floats in a fixed order, seeded generators: identical input and
parameters give identical output on the same platform (tested). Across platforms identical
output is expected but claimed only where it has been run.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Final, Literal

from .declared import DeclaredRelations
from .fuzzy import FuzzyMatrixError
from .hmodel import EVALUATOR_VERSION, HModelAccuracy, average_ranks, hmodel_accuracy
from .models import _Frozen

__all__ = [
    "CANDIDATE_METHOD",
    "CANDIDATE_STATUS",
    "CandidateParameters",
    "HModelLayout",
    "StartRecord",
    "UnplacedElement",
    "fit_hmodel_candidate",
]

CANDIDATE_METHOD: Final = "aia_hmodel_candidate_v1"
CANDIDATE_STATUS: Final = "EXPERIMENTAL_AIA"
_RULES: Final = ("AIA-H8", "AIA-H9", "SOMECS-H6", "SOMECS-H7")
_FRAME: Final = (0.05, 0.95)


class CandidateParameters(_Frozen):
    """Every tunable of the search; recorded on each result."""

    seed: int = 20261005
    random_starts: int = 4
    smooth_iterations: int = 150
    ordinal_iterations: int = 300
    ordinal_gap: float = 0.05
    exact_max_sweeps: int = 400
    directions: int = 16
    initial_step: float = 0.25  # of the start layout's RMS radius (1 after normalising)
    min_step: float = 1e-6
    repair_rounds: int = 30


class StartRecord(_Frozen):
    label: str  # "classical_mds_on_ranks" or "random_<k>"
    start_accuracy: float | None
    smooth_correlation: float | None
    direct_accuracy: float | None  # smooth -> exact
    ordinal_stress: float | None
    ordinal_accuracy: float | None  # smooth -> ordinal -> exact
    start_refined_accuracy: float | None  # start -> exact, classical MDS start only
    final_accuracy: float | None  # the best branch; ties to the earlier one
    branch: Literal["direct", "ordinal", "start"]
    sweeps: int


class UnplacedElement(_Frozen):
    element_id: str
    reason: str


class HModelLayout(_Frozen):
    """An experimental AIA H-Model layout of declared relations, with how it was found."""

    method: str
    status: Literal["EXPERIMENTAL_AIA"]
    evaluator: str
    parameters: CandidateParameters
    element_ids: tuple[str, ...]  # placed, in the input's order
    positions: tuple[tuple[float, float], ...]  # in the 0-1 frame
    unplaced: tuple[UnplacedElement, ...]
    accuracy: HModelAccuracy
    starts: tuple[StartRecord, ...]
    chosen_start: int
    baseline_classical_mds: float | None
    relations_fingerprint: str
    relation_scale: str
    frame: str
    rules: tuple[str, ...]


def fit_hmodel_candidate(
    relations: DeclaredRelations, parameters: CandidateParameters | None = None
) -> HModelLayout:
    """Lay out ``relations`` with the experimental candidate. Refuses what it cannot place.

    Raises :class:`FuzzyMatrixError` when fewer than three elements have a defined relation,
    or when every defined relation is equal (no order to represent).
    """
    params = parameters or CandidateParameters()
    _check_parameters(params)
    canonical = sorted(range(relations.size), key=lambda i: relations.element_ids[i])
    relations_in_order = relations
    relations = relations.permuted(canonical)
    placed, unplaced = _placeable(relations)
    if len(placed) < 3:
        raise FuzzyMatrixError(
            f"an H-Model needs at least three elements with a defined relation; "
            f"{len(placed)} have one"
        )
    sub = _restrict(relations, placed)
    observations = _observations(sub)
    values = [v for _, _, v in observations]
    if len(set(values)) == 1:
        raise FuzzyMatrixError("every defined relation is equal: there is no order to lay out")
    ranks = average_ranks(values)
    problem = _Problem(len(placed), [(r, s) for r, s, _ in observations], ranks)

    starts: list[list[tuple[float, float]]] = [_classical_start(sub, problem)]
    for k in range(params.random_starts):
        rng = random.Random(params.seed + k)
        starts.append([(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in placed])

    records: list[StartRecord] = []
    best: tuple[float, int, list[tuple[float, float]]] | None = None
    baseline: float | None = None
    for k, start in enumerate(starts):
        points = _normalise(start)
        start_accuracy = problem.accuracy(points)
        if k == 0:
            baseline = start_accuracy
        points, smooth = _smooth(problem, points, params)
        direct, direct_value, direct_sweeps = _refine(problem, list(points), params)
        ordered, stress = _ordinal(problem, list(points), params)
        ordinal, ordinal_value, ordinal_sweeps = _refine(problem, ordered, params)
        branches: list[tuple[str, list[tuple[float, float]], float | None]] = [
            ("direct", direct, direct_value),
            ("ordinal", ordinal, ordinal_value),
        ]
        start_value: float | None = None
        if k == 0:  # never end below the classical MDS baseline
            refined, start_value, start_sweeps = _refine(problem, _normalise(start), params)
            branches.append(("start", refined, start_value))
            direct_sweeps += start_sweeps
        branch, points, final = branches[0]
        for name, candidate_points, value in branches[1:]:
            if _score(value) > _score(final):
                branch, points, final = name, candidate_points, value
        label = "classical_mds_on_ranks" if k == 0 else f"random_{k - 1}"
        records.append(
            StartRecord(
                label=label,
                start_accuracy=start_accuracy,
                smooth_correlation=smooth,
                direct_accuracy=direct_value,
                ordinal_stress=stress,
                ordinal_accuracy=ordinal_value,
                start_refined_accuracy=start_value,
                final_accuracy=final,
                branch=branch,
                sweeps=direct_sweeps + ordinal_sweeps,
            )
        )
        score = _score(final)
        if best is None or score > best[0]:
            best = (score, k, points)
    assert best is not None
    _, chosen, points = best
    framed_canonical = _frame(points)
    # Report in the caller's element order: placed elements as they came in.
    position_of = dict(zip(sub.element_ids, framed_canonical, strict=True))
    placed_ids = tuple(e for e in relations_in_order.element_ids if e in position_of)
    sub = _restrict(
        relations_in_order, [relations_in_order.element_ids.index(e) for e in placed_ids]
    )
    framed = [position_of[e] for e in placed_ids]
    caller_order = {e: i for i, e in enumerate(relations_in_order.element_ids)}
    unplaced = sorted(unplaced, key=lambda u: caller_order[u.element_id])
    accuracy = hmodel_accuracy(sub, framed)
    return HModelLayout(
        method=CANDIDATE_METHOD,
        status=CANDIDATE_STATUS,
        evaluator=EVALUATOR_VERSION,
        parameters=params,
        element_ids=sub.element_ids,
        positions=tuple(framed),
        unplaced=tuple(unplaced),
        accuracy=accuracy,
        starts=tuple(records),
        chosen_start=chosen,
        baseline_classical_mds=baseline,
        relations_fingerprint=relations_in_order.fingerprint(),
        relation_scale=relations_in_order.scale.value,
        frame="centred; principal axes; third moment >= 0 per axis; uniform scale into 0.05-0.95",
        rules=(
            *relations_in_order.rules,
            *accuracy.rules[len(relations_in_order.rules) :],
            *_RULES,
        ),
    )


# ------------------------------------------------------------------ problem


class _Problem:
    """The observations, with the relations' ranks centred once."""

    def __init__(self, n: int, pairs: list[tuple[int, int]], ranks: list[float]) -> None:
        self.n = n
        self.pairs = pairs
        mean = math.fsum(ranks) / len(ranks)
        self.lc = [x - mean for x in ranks]
        self.lnorm = math.sqrt(math.fsum(x * x for x in self.lc))
        m = len(pairs)
        # Without ties, centred ranks 1..m have this sum of squares; ties lower it.
        self.untied_norm = math.sqrt(m * (m * m - 1) / 12.0)
        self.touching: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        for k, (r, s) in enumerate(pairs):
            self.touching[r].append((k, s))
            self.touching[s].append((k, r))

    def closeness(self, points: Sequence[tuple[float, float]]) -> list[float]:
        return self._closeness(points)

    def fast_accuracy(self, ys: list[float]) -> float | None:
        """The accuracy from closeness values: ranks, then one dot with the fixed ranks.

        The relations' centred ranks sum to zero, so the distance ranks need no centring for
        the dot product; their norm is the untied constant unless distances tie.
        """
        m = len(ys)
        order = sorted(range(m), key=ys.__getitem__)
        ranks = [0.0] * m
        tied = False
        i = 0
        while i < m:
            j = i
            value = ys[order[i]]
            while j + 1 < m and ys[order[j + 1]] == value:
                j += 1
            shared = (i + j) / 2.0 + 1.0
            if j > i:
                tied = True
            for k in range(i, j + 1):
                ranks[order[k]] = shared
            i = j + 1
        if tied:
            if all(r == ranks[0] for r in ranks):
                return None
            mean = (m + 1) / 2.0
            norm = math.sqrt(sum((r - mean) ** 2 for r in ranks))
        else:
            norm = self.untied_norm
        dot = sum(a * b for a, b in zip(self.lc, ranks, strict=True))
        return max(-1.0, min(1.0, dot / (self.lnorm * norm)))

    def _closeness(self, points: Sequence[tuple[float, float]]) -> list[float]:
        return [-math.dist(points[r], points[s]) for r, s in self.pairs]

    def _corr_with(self, ys: list[float]) -> float | None:
        if len(set(ys)) == 1:
            return None
        mean = math.fsum(ys) / len(ys)
        yc = [y - mean for y in ys]
        ynorm = math.sqrt(math.fsum(y * y for y in yc))
        dot = math.fsum(a * b for a, b in zip(self.lc, yc, strict=True))
        return max(-1.0, min(1.0, dot / (self.lnorm * ynorm)))

    def accuracy(self, points: Sequence[tuple[float, float]]) -> float | None:
        """Spearman of (relation, -distance): Pearson of the fixed ranks and distance ranks."""
        return self._corr_with(average_ranks(self._closeness(points)))

    def smooth(self, points: Sequence[tuple[float, float]]) -> float | None:
        return self._corr_with(self._closeness(points))

    def smooth_gradient(
        self, points: Sequence[tuple[float, float]]
    ) -> tuple[float | None, list[tuple[float, float]]]:
        ys = self._closeness(points)
        grad = [(0.0, 0.0)] * self.n
        if len(set(ys)) == 1:
            return None, grad
        mean = math.fsum(ys) / len(ys)
        yc = [y - mean for y in ys]
        ynorm = math.sqrt(math.fsum(y * y for y in yc))
        f = math.fsum(a * b for a, b in zip(self.lc, yc, strict=True)) / (self.lnorm * ynorm)
        gx = [0.0] * self.n
        gy = [0.0] * self.n
        for (r, s), lk, yk in zip(self.pairs, self.lc, yc, strict=True):
            # d f / d y_k, then y_k = -|p_r - p_s|
            dfdy = (lk / self.lnorm - f * yk / ynorm) / ynorm
            dx = points[r][0] - points[s][0]
            dy = points[r][1] - points[s][1]
            d = math.hypot(dx, dy)
            if d == 0.0:
                continue
            ux, uy = dx / d, dy / d
            gx[r] -= dfdy * ux
            gy[r] -= dfdy * uy
            gx[s] += dfdy * ux
            gy[s] += dfdy * uy
        return f, list(zip(gx, gy, strict=True))


def _smooth(
    problem: _Problem, points: list[tuple[float, float]], params: CandidateParameters
) -> tuple[list[tuple[float, float]], float | None]:
    current, grad = problem.smooth_gradient(points)
    if current is None:
        return points, None
    eta = 0.1
    for _ in range(params.smooth_iterations):
        trial = [
            (x + eta * gx, y + eta * gy) for (x, y), (gx, gy) in zip(points, grad, strict=True)
        ]
        value = problem.smooth(trial)
        if value is not None and value > current:
            points = _normalise(trial)
            current, grad = problem.smooth_gradient(points)
            if current is None:
                break
            eta *= 1.2
        else:
            eta /= 2
            if eta < 1e-9:
                break
    return points, current


def _pava(values: list[float], blocks: list[list[int]]) -> list[float]:
    """Non-decreasing least-squares fit over ``blocks`` (each block one level, its mean)."""
    level: list[float] = []
    weight: list[int] = []
    span: list[int] = []
    for block in blocks:
        level.append(math.fsum(values[k] for k in block) / len(block))
        weight.append(len(block))
        span.append(1)
        while len(level) > 1 and level[-2] > level[-1]:
            w = weight[-2] + weight[-1]
            merged = (level[-2] * weight[-2] + level[-1] * weight[-1]) / w
            spans = span[-2] + span[-1]
            del level[-1], weight[-1], span[-1]
            level[-1], weight[-1], span[-1] = merged, w, spans
    fitted = [0.0] * len(values)
    b = 0
    for value, count in zip(level, span, strict=True):
        for block in blocks[b : b + count]:
            for k in block:
                fitted[k] = value
        b += count
    return fitted


def _ordinal(
    problem: _Problem, points: list[tuple[float, float]], params: CandidateParameters
) -> tuple[list[tuple[float, float]], float | None]:
    """Kruskal-style ordinal stress: distances fitted by a monotone function of the order.

    Observations are sorted from the highest relation to the lowest; tied relations form one
    block (one target distance). Isotonic regression gives the targets, made *strictly*
    increasing by a gap of ``ordinal_gap`` x mean distance / blocks between successive blocks
    (plain isotonic targets let a violating pair settle into a tie, which the accuracy also
    counts against). A backtracking gradient step on stress-1 moves the points toward them.
    """
    if params.ordinal_iterations == 0:
        return points, None
    order = sorted(range(len(problem.pairs)), key=lambda k: (-problem.lc[k], k))
    blocks: list[list[int]] = []
    for k in order:
        if blocks and problem.lc[blocks[-1][0]] == problem.lc[k]:
            blocks[-1].append(k)
        else:
            blocks.append([k])

    block_of = [0] * len(problem.pairs)
    for b, block in enumerate(blocks):
        for k in block:
            block_of[k] = b

    def stress_and_targets(
        pts: list[tuple[float, float]],
    ) -> tuple[float, list[float], list[float]]:
        d = [math.dist(pts[r], pts[s]) for r, s in problem.pairs]
        gap = params.ordinal_gap * (math.fsum(d) / len(d)) / len(blocks)
        shifted = [dk - gap * block_of[k] for k, dk in enumerate(d)]
        target = [t + gap * block_of[k] for k, t in enumerate(_pava(shifted, blocks))]
        num = math.fsum((a - b) ** 2 for a, b in zip(d, target, strict=True))
        den = math.fsum(a * a for a in d) or 1.0
        return math.sqrt(num / den), d, target

    current, d, target = stress_and_targets(points)
    eta = 0.05
    for _ in range(params.ordinal_iterations):
        grad = [[0.0, 0.0] for _ in range(problem.n)]
        for (r, s), dk, tk in zip(problem.pairs, d, target, strict=True):
            if dk == 0.0:
                continue
            g = (dk - tk) / dk
            ux = (points[r][0] - points[s][0]) * g
            uy = (points[r][1] - points[s][1]) * g
            grad[r][0] += ux
            grad[r][1] += uy
            grad[s][0] -= ux
            grad[s][1] -= uy
        trial = _normalise(
            [(x - eta * g[0], y - eta * g[1]) for (x, y), g in zip(points, grad, strict=True)]
        )
        value, d2, t2 = stress_and_targets(trial)
        if value < current:
            points, current, d, target = trial, value, d2, t2
            eta *= 1.2
        else:
            eta /= 2
            if eta < 1e-9:
                break
    return points, current


def _score(value: float | None) -> float:
    return -math.inf if value is None else value


def _refine(
    problem: _Problem, points: list[tuple[float, float]], params: CandidateParameters
) -> tuple[list[tuple[float, float]], float | None, int]:
    """The exact phase, with repair steps on discordant pairs between rounds."""
    points, value, sweeps = _exact(problem, points, params)
    for _ in range(params.repair_rounds):
        repaired = _repair(problem, points)
        if repaired is None:
            break
        points, value, more = _exact(problem, repaired, params)
        sweeps += more
    return points, value, sweeps


def _repair(
    problem: _Problem, points: list[tuple[float, float]]
) -> list[tuple[float, float]] | None:
    """One step on the discordant pairs; ``None`` when there are none or nothing helps.

    For every two observations whose relations are ordered (``a`` higher than ``b``) while
    their distances are not (``d_a >= d_b``), push ``d_a`` down and ``d_b`` up (a hinge with
    a small margin). The step is kept only if the accuracy rises.
    """
    ys = problem.closeness(points)
    current = problem.fast_accuracy(ys)
    if current is None or current >= 1.0:
        return None
    d = [-y for y in ys]
    order = sorted(range(len(d)), key=lambda k: (-problem.lc[k], k))
    margin = 1e-3 * (math.fsum(d) / len(d))
    weight = [0.0] * len(d)
    for i, a in enumerate(order):
        for b in order[i + 1 :]:
            if problem.lc[a] > problem.lc[b] and d[a] + margin > d[b]:
                weight[a] += 1.0
                weight[b] -= 1.0
    if not any(weight):
        return None
    grad = [[0.0, 0.0] for _ in range(problem.n)]
    for (r, s), w, dk in zip(problem.pairs, weight, d, strict=True):
        if w == 0.0 or dk == 0.0:
            continue
        ux = (points[r][0] - points[s][0]) / dk * w
        uy = (points[r][1] - points[s][1]) / dk * w
        grad[r][0] += ux
        grad[r][1] += uy
        grad[s][0] -= ux
        grad[s][1] -= uy
    norm = math.sqrt(math.fsum(g[0] ** 2 + g[1] ** 2 for g in grad)) or 1.0
    eta = 0.05
    while eta > 1e-7:
        trial = [
            (x - eta * g[0] / norm, y - eta * g[1] / norm)
            for (x, y), g in zip(points, grad, strict=True)
        ]
        value = problem.fast_accuracy(problem.closeness(trial))
        if value is not None and value > current + 1e-12:
            return trial
        eta /= 2
    return None


def _exact(
    problem: _Problem, points: list[tuple[float, float]], params: CandidateParameters
) -> tuple[list[tuple[float, float]], float | None, int]:
    ys = problem.closeness(points)
    current = problem.fast_accuracy(ys)
    if current is None:
        return points, None, 0
    moves = [
        (
            math.cos(2 * math.pi * k / params.directions),
            math.sin(2 * math.pi * k / params.directions),
        )
        for k in range(params.directions)
    ]
    step = params.initial_step
    sweeps = 0
    while sweeps < params.exact_max_sweeps and step >= params.min_step:
        sweeps += 1
        moved = False
        for r in range(problem.n):
            x, y = points[r]
            touching = problem.touching[r]
            best_value, best_point = current, None
            for cx, cy in moves:
                candidate = (x + step * cx, y + step * cy)
                trial = ys[:]
                for k, other in touching:
                    trial[k] = -math.dist(candidate, points[other])
                value = problem.fast_accuracy(trial)
                if value is not None and value > best_value + 1e-12:
                    best_value, best_point = value, candidate
            if best_point is not None:
                points[r] = best_point
                for k, other in touching:
                    ys[k] = -math.dist(best_point, points[other])
                current = best_value
                moved = True
        if not moved:
            step /= 2
    return points, current, sweeps


# ------------------------------------------------------------------ inputs


def _check_parameters(p: CandidateParameters) -> None:
    if p.random_starts < 0 or p.smooth_iterations < 0 or p.exact_max_sweeps < 0:
        raise FuzzyMatrixError("candidate counts must be non-negative")
    if p.directions < 4:
        raise FuzzyMatrixError("the exact phase needs at least four directions")
    if not (0 < p.min_step <= p.initial_step):
        raise FuzzyMatrixError("steps must satisfy 0 < min_step <= initial_step")


def _placeable(relations: DeclaredRelations) -> tuple[list[int], list[UnplacedElement]]:
    placed: list[int] = []
    unplaced: list[UnplacedElement] = []
    reasons = {(a, b): why for a, b, why in relations.undefined}
    for r, element in enumerate(relations.element_ids):
        defined = any(
            relations.values[r][s] is not None or relations.values[s][r] is not None
            for s in range(relations.size)
            if s != r
        )
        if defined:
            placed.append(r)
            continue
        other = relations.element_ids[1 if r == 0 else 0]
        why = reasons.get((element, other), "no defined relation")
        unplaced.append(UnplacedElement(element_id=element, reason=f"no defined relation: {why}"))
    return placed, unplaced


def _restrict(relations: DeclaredRelations, keep: list[int]) -> DeclaredRelations:
    if len(keep) == relations.size:
        return relations
    ids = [relations.element_ids[i] for i in keep]
    kept = set(ids)
    return relations.model_copy(
        update={
            "element_ids": tuple(ids),
            "values": tuple(tuple(relations.values[i][j] for j in keep) for i in keep),
            "undefined": tuple(u for u in relations.undefined if u[0] in kept and u[1] in kept),
        }
    )


def _observations(relations: DeclaredRelations) -> list[tuple[int, int, float]]:
    return [
        (r, s, v)
        for r in range(relations.size)
        for s in range(relations.size)
        if r != s and (v := relations.values[r][s]) is not None
    ]


# ------------------------------------------------------------------ geometry


def _classical_start(relations: DeclaredRelations, problem: _Problem) -> list[tuple[float, float]]:
    """Classical MDS on a rank dissimilarity: 1 - (mean rank of the pair's relations) / max."""
    n = relations.size
    rank_of: dict[tuple[int, int], float] = {}
    for (r, s), lc in zip(problem.pairs, problem.lc, strict=True):
        rank_of[(r, s)] = lc
    top = max(abs(v) for v in problem.lc) or 1.0
    delta = [[0.0] * n for _ in range(n)]
    known: list[float] = []
    for r in range(n):
        for s in range(r + 1, n):
            both = [rank_of[p] for p in ((r, s), (s, r)) if p in rank_of]
            if both:
                value = 1.0 - (sum(both) / len(both)) / top  # 0 (closest) .. 2 (farthest)
                delta[r][s] = delta[s][r] = value
                known.append(value)
    fill = sum(known) / len(known)
    for r in range(n):
        for s in range(r + 1, n):
            if not any(p in rank_of for p in ((r, s), (s, r))):
                delta[r][s] = delta[s][r] = fill
    sq = [[d * d for d in row] for row in delta]
    row_mean = [sum(row) / n for row in sq]
    grand = sum(row_mean) / n
    b = [
        [-0.5 * (sq[i][j] - row_mean[i] - row_mean[j] + grand) for j in range(n)] for i in range(n)
    ]
    values, vectors = _jacobi(b)
    first, second = sorted(range(n), key=lambda k: (-values[k], k))[:2]
    scale_1 = math.sqrt(max(values[first], 0.0))
    scale_2 = math.sqrt(max(values[second], 0.0))
    coords = [(vectors[i][first] * scale_1, vectors[i][second] * scale_2) for i in range(n)]
    if len(set(coords)) == 1:  # a degenerate dissimilarity: start on a circle instead
        coords = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    return coords


def _jacobi(a: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    """Eigenvalues and column eigenvectors of a symmetric matrix (cyclic Jacobi)."""
    n = len(a)
    m = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = math.fsum(m[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-22:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(m[p][q]) < 1e-300:
                    continue
                theta = (m[q][q] - m[p][p]) / (2 * m[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(n):
                    mkp, mkq = m[k][p], m[k][q]
                    m[k][p] = c * mkp - s * mkq
                    m[k][q] = s * mkp + c * mkq
                for k in range(n):
                    mpk, mqk = m[p][k], m[q][k]
                    m[p][k] = c * mpk - s * mqk
                    m[q][k] = s * mpk + c * mqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    return [m[i][i] for i in range(n)], v


def _normalise(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Centre and scale to unit RMS radius (the accuracy is invariant to both)."""
    n = len(points)
    cx = math.fsum(p[0] for p in points) / n
    cy = math.fsum(p[1] for p in points) / n
    centred = [(x - cx, y - cy) for x, y in points]
    rms = math.sqrt(math.fsum(x * x + y * y for x, y in centred) / n)
    if rms == 0.0:
        return centred
    return [(x / rms, y / rms) for x, y in centred]


def _frame(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    centred = _normalise(points)
    sxx = math.fsum(x * x for x, _ in centred)
    syy = math.fsum(y * y for _, y in centred)
    sxy = math.fsum(x * y for x, y in centred)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    c, s = math.cos(angle), math.sin(angle)
    rotated = [(c * x + s * y, -s * x + c * y) for x, y in centred]
    flips = []
    for axis in (0, 1):
        third = math.fsum(p[axis] ** 3 for p in rotated)
        flips.append(-1.0 if third < 0 else 1.0)
    rotated = [(x * flips[0], y * flips[1]) for x, y in rotated]
    extent = max(max(abs(x), abs(y)) for x, y in rotated) or 1.0
    low, high = _FRAME
    half = (high - low) / 2
    middle = (high + low) / 2
    return [(middle + half * x / extent, middle + half * y / extent) for x, y in rotated]
