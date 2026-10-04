#!/usr/bin/env python3
"""The Sociomapping acceptance journey on the fictional reference study R1.

Runs every engine stage that exists today on
``packages/aia_core/tests/fixtures/sociomapping_reference/study.json`` and prints every
intermediate value as JSON, so a person can follow the study from inputs to fit diagnostics
and see exactly where it stops and why.

    python tools/sociomapping_journey.py            # the whole journey as JSON
    python tools/sociomapping_journey.py --summary  # one line per stage

Stages: inputs -> fuzzy matrix -> heights -> coherences -> H-Model -> STORM/WIND -> 3D -> report.
A stage the engine cannot compute yet is reported as ``pending`` with the open question that
blocks it (``.planning/plans/sociomapping-engine.md``); nothing is filled in to make it run.
``packages/aia_core/tests/test_sociomapping_reference_journey.py`` runs the same function.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
STUDY = REPO / "packages/aia_core/tests/fixtures/sociomapping_reference/study.json"

from aia_core.domain.sociomap.coherence import coherences  # noqa: E402
from aia_core.domain.sociomap.fuzzy import (  # noqa: E402
    FuzzyMatrix,
    rts_fuzzy_from_correlations,
    rts_object_correlations,
    rts_people_matrix,
    rts_scale_answers,
)
from aia_core.domain.sociomap.heights import (  # noqa: E402
    column_averages,
    object_average_answers,
    row_averages,
)
from aia_core.domain.sociomap.models import RatingsMatrix  # noqa: E402

PENDING = [
    {
        "stage": "H-Model layout",
        "blocked_by": ["AIA-H8", "M2"],
        "note": (
            "SOMECS's objective is unknown; the experimental AIA candidate and its acceptance "
            "are in docs/architecture/sociomapping-hmodel.md section 4."
        ),
    },
    {
        "stage": "H-Model significance",
        "blocked_by": ["SOMECS-H5", "M15"],
        "note": "Null = random symmetric matrices of the same size, each refitted.",
    },
    {
        "stage": "STORM map (respondents)",
        "blocked_by": ["SOMECS-M1", "M3"],
        "note": "SOMECS only; RTS places no respondents.",
    },
    {
        "stage": "WIND surface",
        "blocked_by": ["SOMECS-M2", "M4"],
        "note": "Heights exist; the interpolation does not.",
    },
    {
        "stage": "Interactive 3D",
        "blocked_by": ["H-Model layout", "WIND surface"],
        "note": "Renderer reused from PR 116.",
    },
    {
        "stage": "Report",
        "blocked_by": ["AIA-S1", "M14", "D6"],
        "note": "Adequacy policy and methodology approval.",
    },
]


def _matrix(m: FuzzyMatrix) -> dict[str, Any]:
    return {
        "elements": list(m.element_ids),
        "values": [[None if v is None else round(v, 6) for v in row] for row in m.values],
        "symmetric": m.is_symmetric(),
        "source": m.source.value,
        "rules": list(m.rules),
        "fingerprint": m.fingerprint(),
    }


def run(study: dict[str, Any]) -> dict[str, Any]:
    """Every intermediate value of the journey, stage by stage."""
    people = study["people"]
    low, high = people["scale"]
    out: dict[str, Any] = {"study": study["provenance"], "people": {}, "objects": {}}
    for key, question in people["questions"].items():
        m = rts_people_matrix(people["ids"], question["ratings"], (low, high))
        tree = coherences(m)
        out["people"][key] = {
            "fuzzy_matrix": _matrix(m),
            "heights_on_scale": {
                "received (column average, QED-W1)": [
                    round(low + (high - low) * h, 6) for h in column_averages(m)
                ],
                "given (row average, QED-W2)": [
                    round(low + (high - low) * h, 6) for h in row_averages(m)
                ],
            },
            "coherences": tree.written(),
        }
    objects = study["objects"]
    answers = RatingsMatrix(
        respondent_ids=tuple(objects["respondents"]),
        object_ids=tuple(objects["ids"]),
        values=tuple(tuple(row) for row in objects["ratings"]),
    )
    scaled = rts_scale_answers(answers, tuple(objects["scale"]))  # type: ignore[arg-type]
    signed = rts_object_correlations(scaled)
    relation = rts_fuzzy_from_correlations(signed)
    o_low, o_high = objects["scale"]
    out["objects"] = {
        "scaled_answers": [[round(v or 0.0, 6) for v in row] for row in scaled.values],
        "signed_correlations": [
            [None if v is None else round(v, 6) for v in row] for row in signed.r
        ],
        "support": signed.support,
        "negative_pairs": [list(p) for p in signed.negative_pairs()],
        "relation_matrix": _matrix(relation),
        "average_answer_on_scale (RTS-W3)": [
            round(o_low + (o_high - o_low) * h, 6) for h in object_average_answers(scaled)
        ],
        "coherences": coherences(relation).written(),
    }
    out["pending"] = PENDING
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--summary", action="store_true", help="one line per stage")
    args = parser.parse_args(argv)
    result = run(json.loads(STUDY.read_text("utf-8")))
    if not args.summary:
        json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
        print()
        return 0
    for key, part in result["people"].items():
        print(
            f"people/{key}: fuzzy {len(part['fuzzy_matrix']['elements'])}x"
            f"{len(part['fuzzy_matrix']['elements'])}, coherences {part['coherences']}"
        )
    o = result["objects"]
    print(
        f"objects: support {o['support']}, negative pairs {len(o['negative_pairs'])}, "
        f"coherences {o['coherences']}"
    )
    for p in result["pending"]:
        print(f"pending: {p['stage']} -- blocked by {', '.join(p['blocked_by'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
