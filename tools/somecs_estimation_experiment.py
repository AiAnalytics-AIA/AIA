#!/usr/bin/env python3
"""What SOMECS's own H-Model layout tells us about its reported accuracy, and what it does not.

Source: SOMECS Input tutorial p. 21, fig. 22 (Matrix Horizontal Model Estimation): a
generated symmetric 10 x 10 matrix, the 2-D coordinates SOMECS fitted to it, and a list of
SOMECS's Spearman accuracies. Transcribed into
``packages/aia_core/tests/fixtures/sociomapping_sources/somecs_input_fig22.json``.

Prints:

1. the accuracy of SOMECS's coordinates under the two candidate definitions -- one Spearman
   over all pairs (evidence register SOMECS-H3) and the mean of per-row Spearman values --
   beside the listed SOMECS values;
2. how far the transcription's three-decimal rounding alone can move the first figure;
3. what classical MDS and nonmetric (Kruskal) MDS reach on the same matrix, so the gap to
   SOMECS's layout can be seen.

Needs NumPy and scikit-learn (not repository dependencies; run in a scratch environment).
Results recorded on 2026-10-04: SOMECS 0.7858 (per-row mean 0.7233), rounding band
0.7829-0.7929 over 2,000 draws (seed 1), classical MDS 0.6608, nonmetric MDS best of 20
seeds 0.7426 (in this session's container; repeatable here, not checked on other hosts).

What this supports (register SOMECS-H3, AIA-H8): the overall-pairs definition is consistent
with a value SOMECS lists; the per-row mean is not. What it does not support: any statement
about SOMECS's fitting objective. SOMECS's layout scores higher than the two MDS
configurations tried here, which is equally consistent with more starts, a different
optimiser, manual adjustment or a different evaluator. 0.786 is a provisional comparison score
under AIA's evaluator, and the MDS figures are baselines of these configurations only.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "packages/aia_core/tests/fixtures/sociomapping_sources/somecs_input_fig22.json"
sys.path.insert(0, str(REPO / "packages/aia_core/src"))

from aia_core.domain.sociomap.hmodel import spearman  # noqa: E402


def accuracy(matrix: list[list[float]], points: list[tuple[float, float]]) -> tuple[float, float]:
    n = len(matrix)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    overall = spearman(
        [matrix[i][j] for i, j in pairs], [-math.dist(points[i], points[j]) for i, j in pairs]
    )
    rows = []
    for i in range(n):
        others = [j for j in range(n) if j != i]
        rows.append(
            spearman(
                [matrix[i][j] for j in others], [-math.dist(points[i], points[j]) for j in others]
            )
        )
    assert overall is not None and all(r is not None for r in rows)
    return overall, sum(r for r in rows if r is not None) / n


def main() -> int:
    import numpy as np
    from sklearn.manifold import MDS

    data = json.loads(FIXTURE.read_text("utf-8"))
    matrix: list[list[float]] = data["matrix"]
    points = [tuple(p) for p in data["coordinates"]]
    n = len(matrix)
    overall, per_row = accuracy(matrix, points)  # type: ignore[arg-type]
    print(f"SOMECS layout: overall {overall:.4f}, mean per-row {per_row:.4f}")
    print(f"SOMECS lists:  {sorted(data['listed_accuracies'])}")

    rng = random.Random(1)
    band = sorted(
        accuracy(
            matrix,
            [(x + rng.uniform(-5e-4, 5e-4), y + rng.uniform(-5e-4, 5e-4)) for x, y in points],
        )[0]
        for _ in range(2000)
    )
    low, high, median = band[0], band[-1], band[1000]
    print(f"rounding band of the overall figure: {low:.4f} .. {high:.4f} (median {median:.4f})")

    dissimilarity = 1.0 - np.array(matrix)
    centring = np.eye(n) - 1.0 / n
    b = -0.5 * centring @ (dissimilarity**2) @ centring
    values, vectors = np.linalg.eigh(b)
    classical = vectors[:, -2:] * np.sqrt(np.maximum(values[-2:], 0.0))
    print(
        f"classical MDS on 1 - M: overall {accuracy(matrix, [tuple(p) for p in classical])[0]:.4f}"
    )

    best = -1.0
    for seed in range(20):
        model = MDS(
            n_components=2,
            metric=False,
            dissimilarity="precomputed",
            random_state=seed,
            n_init=1,
            max_iter=3000,
            eps=1e-9,
            normalized_stress="auto",
        )
        layout = model.fit_transform(dissimilarity)
        best = max(best, accuracy(matrix, [tuple(p) for p in layout])[0])
    print(f"nonmetric MDS, best of 20 seeds: overall {best:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
