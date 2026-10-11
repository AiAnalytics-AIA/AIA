"""Every built-in formula of the object map gives the engine's exact bits.

Plan ``methodology-tab.md`` S3; ADR 0023 decision 4. Each slot's built-in expression is
evaluated beside the engine function it stands for, on random and boundary inputs, and the
two must be equal as floats -- not close: equal. That is what lets a stored edit replace a
formula while an unedited methodology computes exactly what it always did. A slot without an
adapter here fails the completeness test, so no formula goes unproven.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from statistics import NormalDist
from typing import Any

import pytest

from aia_core.domain.methodology.expressions import compile_formula
from aia_core.domain.methodology.sociomap_formulas import SOCIOMAP_FORMULAS
from aia_core.domain.sociomap.engine_v2 import WEIGHTING, _heights, _scaled, _support
from aia_core.domain.sociomap.layout import _object_stress, correlation_distance
from aia_core.domain.sociomap.metrics import ObjectRole, connectedness_100, primary_scores
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem
from aia_core.domain.sociomap.relations import (
    PairStatus,
    fisher_interval,
    kish_effective_n,
    meets_effect_floor,
    person_minmax,
)
from aia_core.domain.sociomap.terrain import EnvelopeHill, envelope_at

Case = tuple[dict[str, Any], float]
RNG_SEED = 20261011


def _inputs(
    values: list[list[float | None]], scales: list[tuple[float, float]], weights: list[float]
) -> ObjectMapInputs:
    p = len(scales)
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{k}" for k in range(len(values))),
        donor_ids=tuple(f"D{k}" for k in range(len(values))),
        items=tuple(
            RatingItem(item_id=f"i{j}", scale_min=lo, scale_max=hi)
            for j, (lo, hi) in enumerate(scales)
        ),
        values=tuple(tuple(r) for r in values),
        weights=tuple(weights),
        object_ids=tuple(f"o{j}" for j in range(p)),
        object_items=tuple(f"i{j}" for j in range(p)),
        roles={f"o{j}": ObjectRole.PRIMARY.value for j in range(p)},
    )


def _f1(rng: random.Random) -> Iterator[Case]:
    for lo, hi in ((1.0, 10.0), (0.0, 5.0), (1.0, 7.0), (-3.0, 3.0)):
        for _ in range(40):
            a = rng.choice([lo, hi, round(rng.uniform(lo, hi)), rng.uniform(lo, hi)])
            got = _scaled(_inputs([[a]], [(lo, hi)], [1.0]))[0][0]
            assert got is not None
            yield {"a": a, "lo": lo, "hi": hi}, got


def _f2(rng: random.Random) -> Iterator[Case]:
    for _ in range(200):
        row = [rng.uniform(0, 1) for _ in range(rng.randint(2, 9))]
        if max(row) == min(row):
            continue
        scaled = person_minmax([row]).values[0]
        i = rng.randrange(len(row))
        got = scaled[i]
        assert got is not None
        yield {"a": row[i], "low": min(row), "high": max(row)}, got


def _weights(rng: random.Random) -> Iterator[tuple[float, ...]]:
    yield (1.0,)
    yield (1.0, 1.0, 1.0)
    for _ in range(200):
        yield tuple(rng.uniform(0.01, 5) for _ in range(rng.randint(1, 60)))


def _kish(rng: random.Random) -> Iterator[Case]:
    for w in _weights(rng):
        yield {"w": w}, kish_effective_n(w)


def _interval(side: int) -> Callable[[random.Random], Iterator[Case]]:
    def cases(rng: random.Random) -> Iterator[Case]:
        for c in (0.9, 0.95, 0.99):
            z = NormalDist().inv_cdf(0.5 + c / 2.0)  # the engine's own z_c
            for r in (-1.0, 1.0, 0.0, *(rng.uniform(-0.999, 0.999) for _ in range(40))):
                for n in (4, 5, 30, rng.uniform(4, 900)):
                    bounds = fisher_interval(r, n, c)
                    assert bounds is not None
                    yield {"r": r, "n": n, "z": z}, bounds[side]

    return cases


def _floor(rng: random.Random) -> Iterator[Case]:
    for floor in (0.1, 0.3, rng.uniform(0.01, 0.99)):
        for r in (-floor, floor, 0.0, -1.0, 1.0, *(rng.uniform(-1, 1) for _ in range(40))):
            met = meets_effect_floor(r, floor)
            assert met is not None
            yield {"r": r, "floor": floor}, 1.0 if met else 0.0


def _distance(rng: random.Random) -> Iterator[Case]:
    for r in (-1.0, 0.0, 1.0, 1.0 - 1e-16, *(rng.uniform(-1, 1) for _ in range(200))):
        yield {"r": r}, correlation_distance(r)


def _stress(rng: random.Random) -> Iterator[Case]:
    for _ in range(100):
        m = rng.randint(3, 9)
        points = [(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(m)]
        delta: list[list[float | None]] = [[0.0] * m for _ in range(m)]
        d: list[float] = []
        t: list[float] = []
        for i in range(m):
            for j in range(i + 1, m):
                value = None if rng.random() < 0.2 else rng.uniform(0, 2)
                delta[i][j] = delta[j][i] = value
                if value is not None:
                    d.append(math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]))
                    t.append(value)
        if not t:
            continue
        yield {"d": tuple(d), "delta": tuple(t)}, _object_stress(points, delta)[1]


def _scores(which: str) -> Callable[[random.Random], Iterator[Case]]:
    def cases(rng: random.Random) -> Iterator[Case]:
        for _ in range(100):
            m = rng.randint(2, 8)
            ids = [f"o{i}" for i in range(m)]
            r: list[list[float | None]] = [[None] * m for _ in range(m)]
            status: list[list[PairStatus | None]] = [[None] * m for _ in range(m)]
            for i in range(m):
                for j in range(i + 1, m):
                    r[i][j] = r[j][i] = rng.uniform(-1, 1)
                    status[i][j] = status[j][i] = PairStatus.RELIABLE
            roles = dict.fromkeys(ids, ObjectRole.PRIMARY.value)
            score = primary_scores(ids, r, status, roles).scores[0]
            known = tuple(r[0][j] for j in range(1, m))
            got = score.alignment if which == "alignment" else score.connectedness
            assert got is not None and all(v is not None for v in known)
            yield {"r": known}, got

    return cases


def _height(rng: random.Random) -> Iterator[Case]:
    for _ in range(150):
        n = rng.randint(1, 30)
        column = [None if rng.random() < 0.2 else rng.uniform(0, 1) for _ in range(n)]
        weights = [rng.uniform(0.05, 4) for _ in range(n)]
        if all(v is None for v in column):
            continue
        got = _heights([[v] for v in column], weights, [0]).values[0]
        assert got is not None
        a = tuple(v for v in column if v is not None)
        w = tuple(x for v, x in zip(column, weights, strict=True) if v is not None)
        yield {"a": a, "w": w}, got


def _k100(rng: random.Random) -> Iterator[Case]:
    for _ in range(60):
        m = rng.randint(2, 6)
        ids = [f"o{i}" for i in range(m)]
        r: list[list[float | None]] = [[None] * m for _ in range(m)]
        status: list[list[PairStatus | None]] = [[None] * m for _ in range(m)]
        for i in range(m):
            for j in range(i + 1, m):
                r[i][j] = r[j][i] = rng.uniform(-1, 1)
                status[i][j] = status[j][i] = PairStatus.RELIABLE
        roles = dict.fromkeys(ids, ObjectRole.PRIMARY.value)

        def correlate(_m: Any, r: Any = r, status: Any = status) -> tuple[Any, Any]:
            return r, status

        k = primary_scores(ids, r, status, roles).scores[0].connectedness
        k100 = connectedness_100(ids, roles, correlate, respondents=3, resamples=1, seed=1)
        got = k100.scores[0].k100
        assert k is not None and got is not None
        yield {"k": k}, got


def _kernel(rng: random.Random) -> Iterator[Case]:
    for _ in range(500):
        hx, hy, x, y = (rng.uniform(-2.75, 2.75) for _ in range(4))
        h, sigma = rng.uniform(0, 1), rng.choice([0.25, rng.uniform(0.05, 1)])
        hit = envelope_at(x, y, [EnvelopeHill(entity_id="o", x=hx, y=hy, height=h)], sigma, 0.0)
        assert hit is not None
        yield {"h": h, "d2": (x - hx) ** 2 + (y - hy) ** 2, "sigma": sigma}, hit[0]


def _support_n(rng: random.Random) -> Iterator[Case]:
    for w in _weights(rng):
        inputs = _inputs([[1.0] for _ in w], [(1.0, 10.0)], list(w))
        got = _support(inputs, {}, WEIGHTING).effective_n
        assert got is not None
        yield {"w": w}, got


ADAPTERS: dict[str, Callable[[random.Random], Iterator[Case]]] = {
    "f1.scale": _f1,
    "f2.person": _f2,
    "f3.effective_n": _kish,
    "f3.interval_low": _interval(0),
    "f3.interval_high": _interval(1),
    "f3.effect_floor": _floor,
    "f6.distance": _distance,
    "f7.stress_1": _stress,
    "f8.alignment": _scores("alignment"),
    "f8.connectedness": _scores("connectedness"),
    "f8.height": _height,
    "f9.k100": _k100,
    "f12.kernel": _kernel,
    "support.effective_n": _support_n,
}


def test_every_built_in_formula_has_its_engine_adapter() -> None:
    assert {f.slot.id for f in SOCIOMAP_FORMULAS} == set(ADAPTERS)


@pytest.mark.parametrize("formula", SOCIOMAP_FORMULAS, ids=lambda f: f.slot.id)
def test_the_built_in_expression_gives_the_engines_exact_bits(formula: Any) -> None:
    compiled = compile_formula(formula.slot, formula.expression)
    cases = list(ADAPTERS[formula.slot.id](random.Random(RNG_SEED)))
    assert len(cases) >= 20
    mismatches = [
        (values, engine, compiled(**values))
        for values, engine in cases
        if compiled(**values) != engine
    ]
    assert mismatches[:3] == []
