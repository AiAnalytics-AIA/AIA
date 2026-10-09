#!/usr/bin/env python3
"""Write the web's contract-3 object map fixture from the real builder.

``apps/web/src/lib/fixtures/object-map.json`` is what the Results page's object map tests
render. It is the ``research_sociomap`` payload the worker stores, produced here by
``research_sociomaps`` under the default pins (``aia-sociomap-1`` + ``aia-sociomap-3``) on
fictional answers, never by hand; ``packages/aia_core/tests/test_object_map_web_fixture.py``
fails when the two drift.

    python tools/object_map_web_fixture.py           # rewrite the fixture
    python tools/object_map_web_fixture.py --check   # exit 1 if it is stale
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.research_sociomap import default_methods, research_sociomaps

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "apps/web/src/lib/fixtures/object-map.json"

OBJECTS = ["Altair", "Borealis", "Cirrus", "Deneb", "Elara", "Fomalhaut"]
RESPONDENTS = 80


def _rows() -> list[list[int]]:
    """Fictional 1-10 answers: Altair, Borealis and Cirrus share one taste, Deneb and Elara
    another, Fomalhaut moves against the first; each object has its own popularity, and the
    last respondent answers 5 to everything (a straight-liner, not placed)."""
    rng = random.Random(20261009)
    level = [7.0, 6.0, 5.5, 4.5, 4.0, 3.0]
    rows: list[list[int]] = []
    for _ in range(RESPONDENTS - 1):
        g, a, b = rng.gauss(0, 0.8), rng.gauss(0, 1.0), rng.gauss(0, 1.0)
        taste = [a, a, a, b, b, -a]
        rows.append(
            [
                int(min(10, max(1, round(level[j] + g + 2.0 * taste[j] + rng.gauss(0, 0.9)))))
                for j in range(len(OBJECTS))
            ]
        )
    rows.append([5] * len(OBJECTS))
    return rows


def build() -> dict[str, Any]:
    spec, problems = compile_design(
        {
            "n": RESPONDENTS,
            "sections": [
                {
                    "type": "object_battery",
                    "title": "Fiktivní značky",
                    "object_family": "značky",
                    "objects": OBJECTS,
                    "scale": [1, 10],
                }
            ],
        }
    )
    assert spec is not None, problems
    battery = spec.batteries[0]
    respondents = [
        {
            "respondent_id": f"FIC-{i:03d}",
            "donor_id": f"FIC-D{i:03d}",
            "weight": 1.0,
            "answers": {
                battery.question_id(o): v for o, v in zip(battery.objects, row, strict=True)
            },
        }
        for i, row in enumerate(_rows())
    ]
    dataset = FieldworkDataset.model_validate(
        {
            "dataset_version": "web-fixture",
            "generator": "tools/object_map_web_fixture.py",
            "origin": "SYNTHETIC_FIXTURE",
            "respondents": respondents,
            "seed": 0,
            "source": "synthetic_fixture",
            "spec_fingerprint": spec.fingerprint(),
        }
    )
    result = research_sociomaps(
        spec, dataset, methods=default_methods(), connectedness_interval=False
    )
    return {"kind": "research_sociomap", "sociomap": result}


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        return 0 if FIXTURE.exists() and FIXTURE.read_text("utf-8") == text else 1
    FIXTURE.write_text(text, "utf-8")
    print(f"wrote {FIXTURE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
