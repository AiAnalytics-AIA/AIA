"""A fictional fieldwork dataset: invented respondents answering a specification.

ADR 0016 D1. This exists to prove the chain after fieldwork -- aggregation, the
Sociomap, the results screens -- in tests and the workbench while the AI
respondent engine does not exist. It is **not fieldwork**: no panel, no person,
no model. Every dataset it builds says so (``origin = SYNTHETIC_FIXTURE``), and
every artifact computed from one inherits that origin.

It is kept out of production structurally, not by convention: ``make
layer_check`` allows only the test/workbench executor composition and tests to
import this module, the production registry never provides the source, the API
refuses the setting on staging and production, and the worker refuses a run whose
recorded source its composition does not provide.

Deterministic from ``(spec, seed)``. Randomness comes only from
``random.Random(seed).random()`` -- the one sequence Python guarantees across
versions -- with normal deviates by Box-Muller, so the same inputs build the same
dataset on any host.

The respondents have structure, so the maps drawn from them are legible: each has
a position on two latent axes, each object a position on the same plane, and a
rating falls with distance. That structure is invented; nothing about it is a
finding.
"""

from __future__ import annotations

import math
import random
from typing import Final

from .fieldwork import (
    DATASET_VERSION,
    Answer,
    DataOrigin,
    FieldworkDataset,
    FieldworkRespondent,
    FieldworkSource,
)
from .research_design import DONT_KNOW, ResearchSpecification

__all__ = ["GENERATOR", "synthetic_dataset"]

GENERATOR: Final = "aia-synthetic-fieldwork-1"
_DONT_KNOW_RATE: Final = 0.03


class _Draws:
    """Uniform and normal draws from ``random()`` alone."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self._spare: float | None = None

    def uniform(self) -> float:
        return self._rng.random()

    def normal(self) -> float:
        if self._spare is not None:
            value, self._spare = self._spare, None
            return value
        u1 = max(self._rng.random(), 1e-12)
        u2 = self._rng.random()
        radius = math.sqrt(-2.0 * math.log(u1))
        self._spare = radius * math.sin(2 * math.pi * u2)
        return radius * math.cos(2 * math.pi * u2)

    def index(self, size: int) -> int:
        return min(int(self._rng.random() * size), size - 1)


def _choose(d: _Draws, scores: list[float]) -> int:
    top = max(scores)
    weights = [math.exp(s - top) for s in scores]
    target = d.uniform() * sum(weights)
    running = 0.0
    for i, w in enumerate(weights):
        running += w
        if target < running:
            return i
    return len(weights) - 1


def synthetic_dataset(spec: ResearchSpecification, *, seed: int) -> FieldworkDataset:
    """Build ``spec.n`` fictional respondents. Refuses a specification without ``n``."""
    if spec.n is None or spec.n < 1:
        raise ValueError("a synthetic dataset needs the specification's n")
    d = _Draws(seed)
    donors = max(3, spec.n // 3)

    # Fixed per question / object: directions and positions on the latent plane.
    directions = {
        q.id: [(d.normal(), d.normal()) for _ in range(max(1, len(q.options)))]
        for q in spec.questions
    }
    placements = {
        b.question_id(o): (2.0 * d.normal(), 2.0 * d.normal())
        for b in spec.batteries
        for o in b.objects
    }

    respondents: list[FieldworkRespondent] = []
    for i in range(spec.n):
        x, y = 1.5 * d.normal(), 1.5 * d.normal()
        answers: dict[str, Answer] = {}
        for q in spec.questions:
            if q.typ == "vyber":
                real = [o for o in q.options if o != DONT_KNOW]
                if q.allow_dont_know and d.uniform() < _DONT_KNOW_RATE:
                    answers[q.id] = DONT_KNOW
                    continue
                scores = [dx * x + dy * y for dx, dy in directions[q.id][: len(real)]]
                answers[q.id] = real[_choose(d, scores)]
            elif q.typ == "multi":
                real = [o for o in q.options if o != DONT_KNOW]
                picked = [
                    o
                    for o, (dx, dy) in zip(real, directions[q.id], strict=False)
                    if d.uniform() < 1.0 / (1.0 + math.exp(-(dx * x + dy * y) - 0.3))
                ]
                answers[q.id] = picked
            elif q.typ == "skala" and q.scale is not None:
                low, high = q.scale
                if q.allow_dont_know and d.uniform() < _DONT_KNOW_RATE:
                    answers[q.id] = None
                    continue
                dx, dy = directions[q.id][0]
                mid, half = (low + high) / 2.0, (high - low) / 2.0
                value = mid + half * math.tanh(0.6 * (dx * x + dy * y)) + 0.8 * d.normal()
                answers[q.id] = int(min(high, max(low, round(value))))
            else:
                answers[q.id] = f"Fiktivní odpověď {i + 1} (syntetická data, ne respondent)"
        for b in spec.batteries:
            low, high = b.scale
            for o in b.objects:
                qid = b.question_id(o)
                ox, oy = placements[qid]
                distance = math.hypot(x - ox, y - oy)
                value = high - (high - low) * min(1.0, distance / 5.0) + 0.7 * d.normal()
                answers[qid] = int(min(high, max(low, round(value))))
        respondents.append(
            FieldworkRespondent(
                respondent_id=f"SYN-R{i + 1:05d}",
                donor_id=f"SYN-D{d.index(donors) + 1:04d}",
                weight=round(math.exp(0.35 * d.normal()), 6),
                answers=answers,
            )
        )
    return FieldworkDataset(
        dataset_version=DATASET_VERSION,
        source=FieldworkSource.SYNTHETIC_FIXTURE,
        origin=DataOrigin.SYNTHETIC_FIXTURE,
        spec_fingerprint=spec.fingerprint(),
        seed=seed,
        generator=GENERATOR,
        respondents=tuple(respondents),
    )
