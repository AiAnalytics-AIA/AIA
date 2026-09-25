#!/usr/bin/env python3
"""How far do 18.6.6's bootstrap bounds move when only the seed moves? (OI-62, D11)

The evidence behind PR C's aggregation contract. It runs the vendored unit's own
``uncertainty.py`` -- unmodified, imported from ``legacy/npc-panel-18.6.6/app`` --
on fictional cells shaped like research aggregates (a 1-5 scale and a four-option
choice, lognormal weights, donors reused across rows), once with the unit's seed
and then with ``--seeds`` others, and reports per cell:

* whether the point estimate depends on the seed (it must not);
* the unit's own seed-to-seed range of each rounded bound;
* the share of other seeds that reproduce the unit's rounded bounds exactly.

If the unit's own bounds move by more than their rounding step when only the seed
changes, the seed is an arbitrary draw of a Monte Carlo estimator, and exact
agreement with it is a property of NumPy's random stream, not of the method.

Needs NumPy and pandas (the unit's requirements, e.g. ``tmp/ui-workbench/venv``):

    tmp/ui-workbench/venv/bin/python tools/bootstrap_seed_sensitivity.py [--seeds 200]

Prints JSON. No network, no files written, no real panel data.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

UNIT = Path(__file__).resolve().parents[1] / "legacy" / "npc-panel-18.6.6" / "app"
UNIT_SEED = 20260816  # dotaznik.py agreguj_otazku: the skala mean and the vyber distribution
CELLS = ((450, 450), (450, 150), (120, 60), (60, 30))  # (rows, donor pool)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, default=200)
    args = parser.parse_args()
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        print("needs numpy and pandas: run with the unit's environment", file=sys.stderr)
        return 1
    sys.path.insert(0, str(UNIT))
    import uncertainty as unit  # the vendored 18.6.6 module, unmodified

    seeds = [UNIT_SEED] + [UNIT_SEED + k * 7919 for k in range(1, args.seeds)]
    cells = {}
    for rows, pool in CELLS:
        g = np.random.default_rng(7)  # the fictional data only; not the bootstrap
        donors = g.integers(0, pool, rows).astype(str)
        weights = g.lognormal(0, 0.5, rows)
        scale = np.clip(np.round(g.normal(3.3, 1.1, rows)), 1, 5)
        choice = np.array(["A", "B", "C", "D"])[g.choice(4, rows, p=[0.4, 0.3, 0.2, 0.1])]

        means = [
            unit.bootstrap_weighted_mean(scale, weights, reps=400, seed=s, donors=donors)
            for s in seeds
        ]
        pcts = [
            unit.bootstrap_weighted_distribution(
                pd.Series(choice), ["A", "B", "C", "D"], weights, reps=400, seed=s, donors=donors
            )["A"]
            for s in seeds
        ]
        mean_bounds = [(round(m["low"], 2), round(m["high"], 2)) for m in means]
        pct_bounds = [(p["low"], p["high"]) for p in pcts]
        support = unit.donor_support(
            pd.DataFrame({"core_donor_id": donors, "_analysis_weight": weights})
        )
        cells[f"rows={rows} donors={len(set(donors))}"] = {
            "support_status": support["support_status"],
            "estimate_depends_on_seed": len({round(m["estimate"], 12) for m in means}) > 1,
            "skala_mean": {
                "estimate": round(means[0]["estimate"], 4),
                "unit_bounds": mean_bounds[0],
                "low_range": [min(b[0] for b in mean_bounds), max(b[0] for b in mean_bounds)],
                "high_range": [min(b[1] for b in mean_bounds), max(b[1] for b in mean_bounds)],
                "low_sd": round(statistics.pstdev(b[0] for b in mean_bounds), 4),
                "rounding_step": 0.01,
                "seeds_reproducing_unit_bounds": round(
                    sum(b == mean_bounds[0] for b in mean_bounds) / len(seeds), 3
                ),
            },
            "vyber_pct_A": {
                "estimate": pcts[0]["estimate"],
                "unit_bounds": pct_bounds[0],
                "low_range": [min(b[0] for b in pct_bounds), max(b[0] for b in pct_bounds)],
                "high_range": [min(b[1] for b in pct_bounds), max(b[1] for b in pct_bounds)],
                "rounding_step": 0.1,
                "seeds_reproducing_unit_bounds": round(
                    sum(b == pct_bounds[0] for b in pct_bounds) / len(seeds), 3
                ),
            },
        }
    print(
        json.dumps(
            {"numpy": np.__version__, "seeds": len(seeds), "cells": cells},
            indent=1,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
