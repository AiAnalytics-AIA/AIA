#!/usr/bin/env python3
"""Write the web's experimental Sociomapping fixture from the real builder.

``apps/web/src/lib/fixtures/sociomapping.json`` is what the Results page tests render. It
is produced here, by ``research_sociomappings`` on fictional answers, never by hand, so the
browser's types are checked against the artifact the worker actually stores;
``packages/aia_core/tests/test_research_sociomapping.py`` fails when the two drift.

    python tools/sociomapping_web_fixture.py           # rewrite the fixture
    python tools/sociomapping_web_fixture.py --check   # exit 1 if it is stale
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.research_sociomapping import research_sociomappings
from aia_core.domain.sociomap.hmodel_candidate import CandidateParameters

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "apps/web/src/lib/fixtures/sociomapping.json"

# Fictional answers on 1-10: Altair, Borealis and Cirrus move together, Delta against them,
# Echo is answered 6 by everyone (constant), and two respondents skip an object.
ROWS: list[list[int | None]] = [
    [2, 3, 2, 9, 6],
    [4, 4, 5, 7, 6],
    [6, 7, 6, 4, 6],
    [8, 8, 7, 2, 6],
    [9, 10, 9, 1, 6],
    [5, 5, 4, 6, 6],
    [3, 2, 3, 8, 6],
    [7, 6, 8, 3, 6],
    [3, None, 2, 8, 6],
    [7, 6, None, 3, 6],
]


def build() -> dict[str, Any]:
    spec, problems = compile_design(
        {
            "n": len(ROWS),
            "sections": [
                {
                    "type": "object_battery",
                    "title": "Fiktivní značky",
                    "object_family": "značky",
                    "objects": ["Altair", "Borealis", "Cirrus", "Delta", "Echo"],
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
        for i, row in enumerate(ROWS)
    ]
    dataset = FieldworkDataset.model_validate(
        {
            "dataset_version": "web-fixture",
            "generator": "tools/sociomapping_web_fixture.py",
            "origin": "SYNTHETIC_FIXTURE",
            "respondents": respondents,
            "seed": 0,
            "source": "synthetic_fixture",
            "spec_fingerprint": spec.fingerprint(),
        }
    )
    result = research_sociomappings(spec, dataset, CandidateParameters(random_starts=1))
    return {"kind": "research_sociomapping", "sociomapping": result}


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        return 0 if FIXTURE.exists() and FIXTURE.read_text("utf-8") == text else 1
    FIXTURE.write_text(text, "utf-8")
    print(f"wrote {FIXTURE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
