#!/usr/bin/env python3
"""Capture materialization fixtures from the vendored 18.6.6 unit (population-operations P4b).

18.6.6 turned an approved evidence-based dimension into respondent values with
``audience_dimensions.materialize_evidence_dimension`` (``audience_dimensions.py:308-345``):
every row scored from numeric predictors (``_predictor_score``, ``:291-305``), then a binary
dimension filled to a weighted target prevalence, or a 1-10 one ranked and shifted to a
target mean. AIA ports it EXACT (P4, M2). Two steps, two environments:

    python tools/materialize_capture.py inputs
        (repo environment) write the fictional rows and the cases to
        packages/aia_core/tests/fixtures/materialize_dimension/

    <a venv with pandas>=2.1,<3 and numpy>=1.26,<3>/bin/python tools/materialize_capture.py capture
        (the unit's environment) read the rows as ``data_library.materialize_dimension`` does
        (``pd.read_csv(..., low_memory=False)``) and run the unit's own, unmodified
        ``materialize_evidence_dimension`` on each case, its overlay written to a scratch
        directory. Records, per case, the values in row order, the kind, the target anchor and
        the usable predictors, or the error the unit raised. Pins the rows, the cases and the
        unit source by SHA256. A re-capture must be byte-identical.

No network and no real panel data: every row is fictional.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "materialize_dimension"
UNIT_SOURCES = ("audience_dimensions.py",)

HEADER = (
    "panel_row_id",
    "vek",
    "prijem",  # income, with gaps
    "skore_zdravi",  # 1-10
    "deti",  # 0/1
    "konstanta",  # one value: no spread, skipped by the unit
    "kraj",  # text: not a numeric predictor
    "vaha_strukturalni_2025",  # with gaps and zeros
)

CASES: list[dict[str, Any]] = [
    {
        "id": "M01_binary_one_predictor",
        "dimension_id": "pije_kavu_rano",
        "spec": {"kind": "binary", "target_prevalence": 0.3, "predictors": [{"column": "vek"}]},
    },
    {
        "id": "M02_binary_percent_two_predictors",
        "dimension_id": "Kupuje BIO",
        "spec": {
            "kind": "prevalence",
            "target_prevalence": 34,
            "predictors": [
                {"column": "prijem", "strength": 2},
                {"id": "vek", "direction": "negative"},
            ],
        },
    },
    {
        "id": "M03_scale_mean",
        "dimension_id": "duvera_v_media",
        "spec": {
            "kind": "scale_1_10",
            "target_mean": 6.2,
            "predictors": [{"column": "skore_zdravi"}, {"column": "deti", "weight": 0.5}],
        },
    },
    {
        "id": "M04_scale_low_mean_clips",
        "dimension_id": "ochota_platit",
        "spec": {"scale": "1_10", "target_mean": 2.0, "predictors": [{"column": "prijem"}]},
    },
    {
        "id": "M05_flat_predictor_skipped",
        "dimension_id": "sportuje",
        "spec": {
            "kind": "boolean",
            "target_prevalence": 0.55,
            "predictors": [{"column": "konstanta"}, {"column": "skore_zdravi"}],
        },
    },
    {
        "id": "M06_only_flat_predictor",
        "dimension_id": "jen_konstanta",
        "spec": {
            "kind": "binary",
            "target_prevalence": 0.2,
            "predictors": [{"column": "konstanta"}],
        },
    },
    {
        "id": "M07_continuous_strength_zero_is_one",
        "dimension_id": "spokojenost",
        "spec": {
            "kind": "continuous",
            "target_mean": 7.5,
            "predictors": [
                {"column": "vek", "strength": 0},
                {"column": "prijem", "direction": "-"},
            ],
        },
    },
    {
        "id": "M08_default_kind_is_binary",
        "dimension_id": "vychozi",
        "spec": {"target_prevalence": "0.4", "predictors": [{"column": "deti"}]},
    },
    {
        "id": "E01_no_usable_predictor",
        "dimension_id": "text_only",
        "spec": {"kind": "binary", "target_prevalence": 0.3, "predictors": [{"column": "kraj"}]},
    },
    {
        "id": "E02_prevalence_out_of_range",
        "dimension_id": "spatne",
        "spec": {"kind": "binary", "target_prevalence": 0, "predictors": [{"column": "vek"}]},
    },
    {
        "id": "E03_prevalence_missing",
        "dimension_id": "chybi",
        "spec": {"kind": "binary", "predictors": [{"column": "vek"}]},
    },
    {
        "id": "E04_mean_out_of_range",
        "dimension_id": "mimo",
        "spec": {"kind": "scale_1_10", "target_mean": 11, "predictors": [{"column": "vek"}]},
    },
    {
        "id": "E05_unsupported_kind",
        "dimension_id": "kategorie",
        "spec": {"kind": "categorical", "predictors": [{"column": "vek"}]},
    },
    {
        "id": "E06_empty_dimension_id",
        "dimension_id": "!!!",
        "spec": {"kind": "binary", "target_prevalence": 0.3, "predictors": [{"column": "vek"}]},
    },
]

KRAJE = ("Praha", "Brno", "Ostrava", "Plzeň")


def _rows(n: int = 160, seed: int = 20261012) -> list[list[str]]:
    rng = random.Random(seed)
    out: list[list[str]] = []
    for i in range(n):
        vek = rng.randint(18, 89)
        prijem = "" if rng.random() < 0.1 else str(rng.randint(8, 120) * 1000)
        skore = str(rng.randint(1, 10))
        deti = str(int(rng.random() < 0.35))
        weight = "" if i % 37 == 5 else ("0" if i % 41 == 7 else f"{rng.uniform(200, 900):.4f}")
        out.append([f"FIC-{i:04d}", str(vek), prijem, skore, deti, "5", rng.choice(KRAJE), weight])
    return out


def rows_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(_rows())
    return buffer.getvalue().encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rows.csv").write_bytes(rows_csv())
    (OUT / "cases.json").write_text(
        json.dumps(CASES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'rows.csv'} and {OUT / 'cases.json'}")


def capture() -> None:
    import numpy as np
    import pandas as pd  # the unit's environment only

    sys.path.insert(0, str(UNIT))
    import audience_dimensions as ad

    rows_bytes = (OUT / "rows.csv").read_bytes()
    cases_bytes = (OUT / "cases.json").read_bytes()
    panel = pd.read_csv(io.BytesIO(rows_bytes), low_memory=False)

    results = []
    with tempfile.TemporaryDirectory() as scratch:
        for case in json.loads(cases_bytes):
            result: dict[str, Any] = {"id": case["id"]}
            try:
                mat = ad.materialize_evidence_dimension(
                    panel,
                    dimension_id=case["dimension_id"],
                    spec=case["spec"],
                    output_dir=Path(scratch),
                )
            except ValueError as exc:
                result["refused"] = str(exc)
            else:
                written = pd.read_csv(Path(scratch) / f"{mat['dimension_id']}.csv.gz")
                values = written[mat["dimension_id"]].tolist()
                result.update(
                    {
                        "dimension_id": mat["dimension_id"],
                        "kind": mat["kind"],
                        "rows": int(mat["rows"]),
                        "target_anchor": {
                            k: (float(v) if isinstance(v, (int, float)) else v)
                            for k, v in mat["target_anchor"].items()
                        },
                        "predictors": mat["predictors"],
                        "row_ids": [str(x) for x in written["panel_row_id"]],
                        "values": [
                            int(v)
                            if mat["kind"] in {"binary", "boolean", "prevalence"}
                            else float(v)
                            for v in values
                        ],
                    }
                )
            results.append(result)

    expected = {
        "captured_with": {"pandas": pd.__version__, "numpy": np.__version__},
        "rows_sha256": _sha(rows_bytes),
        "cases_sha256": _sha(cases_bytes),
        "unit_sources": {name: _sha((UNIT / name).read_bytes()) for name in UNIT_SOURCES},
        "cases": results,
    }
    (OUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'expected.json'}: {len(results)} cases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("inputs", "capture"))
    args = parser.parse_args()
    write_inputs() if args.step == "inputs" else capture()


if __name__ == "__main__":
    main()
