#!/usr/bin/env python3
"""Write the golden fixture that pins ``aia_rowcond_unfolding_v1`` and the engine.

The reference fixtures F1-F9 pin what was ported. The AIA layout algorithm has no
reference to be compared with, so it is pinned by its own output instead: this
script runs the engine on F4's ratings (the only real unfolding input the
reference ships) and records the coordinates, stress and terrain samples. The
test ``test_sociomap_engine.py::test_golden_*`` recomputes and compares.

Regenerate ONLY when the engine's output is meant to change, in the same commit
as the change, with ``ENGINE_IMPLEMENTATION_VERSION`` bumped and the reason in
the commit body. A regenerated golden with an unchanged version is the defect
this fixture exists to catch.

    python tools/sociomap_golden.py            # rewrite the fixture
    python tools/sociomap_golden.py --check    # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "packages/aia_core/tests/fixtures/sociomap"
OUTPUT = FIXTURES / "aia" / "AIA1_rowcond_unfolding_on_f4_ratings.json"

SAMPLE_CELLS = ((0, 0), (10, 10), (21, 21), (30, 12), (42, 42), (15, 27))


def build() -> dict[str, Any]:
    """Compute the golden document."""
    sys.path.insert(0, str(REPO / "packages/aia_core/src"))
    from aia_core.domain.sociomap import (
        AIA_SOCIOMAP_V1,
        ENGINE_IMPLEMENTATION_VERSION,
        MetricsSpec,
        RatingsMatrix,
        SociomapInputs,
        compute_sociomap,
    )

    f4 = json.loads((FIXTURES / "F4_python_unfolding_layout.json").read_text(encoding="utf-8"))
    columns = f4["input"]["columns"]
    rows = [list(r) for r in zip(*(f4["input"]["ratings"][c] for c in columns), strict=True)]
    ratings = RatingsMatrix(
        respondent_ids=tuple(f"r{i:02d}" for i in range(len(rows))),
        object_ids=tuple(columns),
        values=rows,
    )
    spec = AIA_SOCIOMAP_V1.model_copy(
        update={
            "relation": None,
            "metrics": MetricsSpec(
                object_height_metric="mean_rating", object_colour_metric="mean_rating"
            ),
        }
    )
    artifact = compute_sociomap(SociomapInputs(ratings=ratings, object_relation=None), spec)

    def samples(field: Any) -> list[dict[str, Any]]:
        return [
            {
                "gx": gx,
                "gy": gy,
                "hr": field.height_raw[gy][gx],
                "ht": field.height_normalised[gy][gx],
            }
            for gx, gy in SAMPLE_CELLS
        ]

    return {
        "fixture_id": "AIA1_rowcond_unfolding_on_f4_ratings",
        "description": (
            "Output of aia_core.domain.sociomap on F4's ratings under AIA_SOCIOMAP_V1 without a "
            "relation matrix (height = mean_rating). Pins the AIA algorithm against silent "
            "change. NOT a parity fixture: no reference produced these numbers."
        ),
        "input": {
            "ratings_from": "F4_python_unfolding_layout.json",
            "respondent_id_format": "r%02d",
        },
        "engine_implementation_version": ENGINE_IMPLEMENTATION_VERSION,
        "spec": spec.model_dump(mode="json"),
        "tolerance": 1e-9,
        "expected_output": {
            "layout_algorithm": artifact.layout.algorithm,
            "respondent_ids": list(artifact.layout.respondent_ids),
            "excluded_respondents": artifact.excluded_respondents,
            "respondent_xy": [list(p) for p in artifact.layout.respondent_xy],
            "object_xy": [list(p) for p in artifact.layout.object_xy],
            "layout_to_map_scale": artifact.layout.layout_to_map_scale,
            "stress_1": artifact.layout.stress_1,
            "normalized_stress": artifact.layout.normalized_stress,
            "iterations": artifact.layout.iterations,
            "converged": artifact.layout.converged,
            "object_metrics": {k: list(v.values) for k, v in artifact.object_metrics.items()},
            "respondent_terrain": {
                "normalizer": [
                    artifact.respondent_terrain.normalizer_lo,
                    artifact.respondent_terrain.normalizer_hi,
                ],
                "samples": samples(artifact.respondent_terrain),
            },
            "object_terrain": {
                "finite_cells": artifact.object_terrain.finite_cells,
                "normalizer": [
                    artifact.object_terrain.normalizer_lo,
                    artifact.object_terrain.normalizer_hi,
                ],
                "samples": samples(artifact.object_terrain),
            },
            "warnings": list(artifact.warnings),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the fixture would change")
    args = parser.parse_args(argv)
    text = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"{OUTPUT.relative_to(REPO)} is stale", file=sys.stderr)
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
