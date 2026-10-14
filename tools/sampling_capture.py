#!/usr/bin/env python3
"""Capture representative-sample fixtures from the vendored 18.6.6 unit (chunk 2e).

The unit's fieldwork sample is ``representative_sampling.draw_representative``
(``representative_sampling.py:131-173``), reached from ``pipeline.sample_representative``
(``pipeline.py:240-298``). AIA ports its stdlib path: largest-remainder quotas
(``_quota_vector_fallback``), the path the unit takes when SciPy's MILP is unavailable. Two
steps, two environments:

    python tools/sampling_capture.py inputs
        (repo environment) write the fictional rows and the cases to
        packages/aia_core/tests/fixtures/representative_draw/

    <a venv with pandas>=2.1,<3 and numpy>=1.26,<3>/bin/python tools/sampling_capture.py capture
        (the unit's environment) read the rows as ``pipeline.Panel.from_csv`` does, apply each
        case's audience filter with the unit's own ``sanitize_filters`` and ``_mask``, take the
        weights as ``sample_representative`` does (``pipeline.py:265-278``), and run the unit's
        own, unmodified ``draw_representative`` with the MILP made to fail, so the unit runs
        its fallback. Records, per case: the targets, the quota fields and the quotas, the
        smallest gap between a remainder that won a seat and one that did not (a tie there
        is decided by noise, so quotas are only comparable above it), the unit's picks (row
        positions, in sample order) with their base and raked weights, the raw and weighted
        audits, and the unit's verdict (its audit, or the error it raised). Then feeds the
        rake cases to the unit's ``_rake`` directly, where its cap binds. Pins the rows, the
        cases and the unit sources by SHA256.

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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "representative_draw"
UNIT_SOURCES = ("representative_sampling.py", "audience.py", "pipeline.py")
WEIGHT = "vaha_strukturalni_2025"

HEADER = (
    "panel_row_id",
    "core_donor_id",
    "vek",
    "vek_skupina",
    "pohlavi",
    "kraj",
    "vzdelani",
    "zamestnani_status",
    # The unit's audience filter enriches the panel first, and its ``attach_derived`` fails
    # without these (``audience_dimensions.py:141-144``); the real panel carries them.
    "is_parent",
    "is_student",
    "is_employed",
    "has_partner",
    WEIGHT,
)
KRAJE = (
    "Hlavní město Praha",
    "Středočeský kraj",
    "Jihomoravský kraj",
    "Moravskoslezský kraj",
    "Zlínský kraj",
    "Karlovarský kraj",
)
VZDELANI = ("základní", "střední bez maturity", "střední s maturitou", "VOŠ/VŠ")
STATUS = ("employed", "unemployed", "inactive")

CASES: list[dict[str, Any]] = [
    {"id": "D01_n50", "filters": {}, "n": 50, "seed": 11},
    {"id": "D02_n200", "filters": {}, "n": 200, "seed": 12},
    {"id": "D03_n20_max_cap", "filters": {}, "n": 20, "seed": 13},
    {"id": "D04_n750_education_joins_cells", "filters": {}, "n": 750, "seed": 14},
    {"id": "D05_constant_sex_not_a_quota", "filters": {"pohlavi": "žena"}, "n": 120, "seed": 15},
    {"id": "D06_one_region", "filters": {"kraj": "Zlínský kraj"}, "n": 60, "seed": 16},
    {"id": "D07_n1000", "filters": {}, "n": 1000, "seed": 17},
    {"id": "D08_n8", "filters": {}, "n": 8, "seed": 18},
    {
        "id": "D09_no_quota_field",
        "filters": {
            "pohlavi": "muž",
            "vek_skupina": "30-44",
            "kraj": "Hlavní město Praha",
            "vzdelani": "VOŠ/VŠ",
            "zamestnani_status": "employed",
        },
        "n": 3,
        "seed": 19,
    },
    {"id": "D10_age_interval", "filters": {"vek": {"min": 60, "max": 89}}, "n": 150, "seed": 20},
    {"id": "D11_n5", "filters": {}, "n": 5, "seed": 21},
    {"id": "D12_n30", "filters": {}, "n": 30, "seed": 22},
    {"id": "D13_n699_education_not_yet", "filters": {}, "n": 699, "seed": 23},
    {"id": "D14_n700_education_joins", "filters": {}, "n": 700, "seed": 24},
    # Full cells: n near the audience's size, so seats move past capped cells.
    {"id": "D15_whole_audience", "filters": {"kraj": "Hlavní město Praha"}, "n": 663, "seed": 25},
    {
        "id": "D16_near_whole_audience",
        "filters": {"kraj": "Hlavní město Praha"},
        "n": 640,
        "seed": 26,
    },
    {"id": "D17_half_audience", "filters": {"kraj": "Hlavní město Praha"}, "n": 330, "seed": 27},
]


def _rake_case(case_id: str, rows: int, heavy: float, seed: int) -> dict[str, Any]:
    """A sample fed to the unit's ``_rake`` directly: one row of category "x" against a 30 %
    target, so its factor is large and the cap (8 x the 99th percentile above 20 rows, 8 x
    the maximum at 20 or fewer) is what stops it; one target category nobody holds."""
    rng = random.Random(seed)
    region = [rng.choice(("A", "B", "C")) for _ in range(rows)]
    group = ["x"] + ["y"] * (rows - 1)
    base = [heavy] + [round(rng.uniform(0.5, 2.0), 6) for _ in range(rows - 1)]
    return {
        "id": case_id,
        "columns": {"kraj": region, "pohlavi": group},
        "base": base,
        "targets": [
            ["pohlavi", [["x", 0.3], ["y", 0.7]]],
            ["kraj", [["A", 0.2], ["B", 0.3], ["C", 0.4], ["Z", 0.1]]],
        ],
    }


RAKE_CASES: list[dict[str, Any]] = [
    _rake_case("R01_20_rows_cap_is_8x_max", 20, 1.0, 31),
    _rake_case("R02_21_rows_cap_is_8x_p99", 21, 1.0, 32),
    _rake_case("R03_60_rows_cap_binds", 60, 0.2, 33),
    _rake_case("R04_8_rows", 8, 3.0, 34),
    # Above ~100 rows the 99th percentile no longer leans on the one heavy row: the cap binds.
    _rake_case("R05_300_rows_cap_binds", 300, 1.0, 35),
]


def _group(age: int) -> str:
    if age < 30:
        return "18-29"
    if age < 45:
        return "30-44"
    if age < 60:
        return "45-59"
    if age < 75:
        return "60-74"
    return "75+"


def _rows(n: int = 3000, seed: int = 20261012) -> list[list[str]]:
    rng = random.Random(seed)
    rows: list[list[str]] = []
    for i in range(n):
        age = rng.randint(18, 89)
        weight = "0" if rng.random() < 0.01 else f"{rng.lognormvariate(0.0, 0.45):.6f}"
        rows.append(
            [
                f"FIC-ROW-{i + 1:05d}",
                f"FIC-DONOR-{rng.randrange(400) + 1:04d}",
                str(age),
                _group(age),
                rng.choices(("muž", "žena"), weights=(48, 52))[0],
                rng.choices(KRAJE, weights=(12, 13, 11, 11, 5, 3))[0],
                rng.choices(VZDELANI, weights=(15, 33, 32, 20))[0],
                "" if rng.random() < 0.03 else rng.choices(STATUS, weights=(58, 4, 38))[0],
                str(int(rng.random() < 0.35)),
                str(int(age < 30 and rng.random() < 0.4)),
                str(int(rng.random() < 0.58)),
                str(int(rng.random() < 0.55)),
                weight,
            ]
        )
    return rows


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
        json.dumps({"draws": CASES, "rakes": RAKE_CASES}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'rows.csv'} and {OUT / 'cases.json'}")


def _composition(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_abs_pp": audit["max_abs_pp"],
        "mean_abs_pp": audit["mean_abs_pp"],
        "diff_pp": audit["diff_pp"],
        "counts": {f: {k: float(v) for k, v in c.items()} for f, c in audit["counts"].items()},
    }


def capture() -> None:
    import numpy as np
    import pandas as pd  # the unit's environment only

    sys.path.insert(0, str(UNIT))
    import representative_sampling as rs
    from audience import _mask, sanitize_filters

    rows_bytes = (OUT / "rows.csv").read_bytes()
    cases_bytes = (OUT / "cases.json").read_bytes()
    panel = pd.read_csv(
        io.BytesIO(rows_bytes), low_memory=False, dtype={"occupation_isco08": "string"}
    )
    panel["_analysis_weight"] = panel[WEIGHT]  # pipeline.py:180-182, the default weight

    seen: dict[str, Any] = {}

    def no_milp(*_: Any, **__: Any) -> Any:
        raise RuntimeError("scipy MILP unavailable (capture: the fallback path)")

    original_fallback = rs._quota_vector_fallback
    original_targets = rs._targets
    original_rake = rs._rake
    original_audit = rs._audit

    def fallback(df: Any, w: Any, fields: list[str], n: int, rng: Any) -> Any:
        keys = df[fields].astype("string").fillna("<missing>").agg("¦".join, axis=1)
        cell = (
            pd.DataFrame({"key": keys, "w": w})
            .groupby("key")
            .agg(weight=("w", "sum"), capacity=("w", "size"))
        )
        exp = n * cell["weight"] / float(cell["weight"].sum())
        floor = np.floor(exp).astype(int).clip(upper=cell["capacity"])
        q, meta = original_fallback(df, w, fields, n, rng)
        frac = (exp - floor).clip(lower=0)
        won = frac[(q - floor) > 0]
        lost = frac[((q - floor) == 0) & (floor < cell["capacity"])]
        gap = float(won.min() - lost.max()) if len(won) and len(lost) else None
        seen["quota_fields"] = list(fields)
        seen["quotas"] = {str(k): int(v) for k, v in q.items()}
        seen["remainder_gap"] = gap
        return q, meta

    def targets(df: Any, w: Any, fields: list[str]) -> Any:
        out = original_targets(df, w, fields)
        seen["targets"] = out
        seen["target_fields"] = list(out)  # raking's order; the JSON's keys are sorted
        return out

    def rake(sample: Any, goal: Any, *args: Any, **kwargs: Any) -> Any:
        out = original_rake(sample, goal, *args, **kwargs)
        seen["picks"] = [int(i) for i in sample["_zdroj_index"]]
        seen["base_weights"] = [float(x) for x in sample["_base_sample_weight"]]
        seen["analysis_weights"] = [float(x) for x in out]
        return out

    def audit(sample: Any, goal: Any, weight_col: Any = None) -> Any:
        out = original_audit(sample, goal, weight_col)
        seen["weighted" if weight_col else "raw"] = _composition(out)
        return out

    rs._milp_cell_quotas = no_milp
    rs._quota_vector_fallback = fallback
    rs._targets = targets
    rs._rake = rake
    rs._audit = audit

    results = []
    cases = json.loads(cases_bytes)
    for case in cases["draws"]:
        seen.clear()
        df = panel
        if case["filters"]:
            clean, dropped = sanitize_filters(df, case["filters"])
            if dropped:
                raise SystemExit(f"{case['id']}: the unit drops {dropped}")
            df = df[_mask(df, clean)]
        # sample_representative, pipeline.py:265-278
        w = df["_analysis_weight"].to_numpy(dtype=float)  # the real panel has both columns
        if not np.isfinite(w).all() or w.sum() <= 0:
            raise SystemExit(f"{case['id']}: the unit would fall back to weight 1.0")
        w = np.clip(w, 1e-12, None)
        audience = ",".join(str(int(i)) for i in df.index)
        result: dict[str, Any] = {
            "id": case["id"],
            "audience_n": len(df),
            "audience_sha256": _sha(audience.encode("ascii")),
        }
        try:
            out, verdict = rs.draw_representative(
                df, int(case["n"]), seed=case["seed"], weights=w, attempts=40
            )
        except (RuntimeError, ValueError) as exc:
            result["refused"] = str(exc)
        else:
            result["verdict"] = {
                k: verdict[k]
                for k in (
                    "status",
                    "population_n",
                    "sample_n",
                    "fields",
                    "raw_tolerance_pp",
                    "weighted_tolerance_pp",
                    "raw_selection_warning",
                    "effective_n",
                    "effective_n_ratio",
                    "weight_min",
                    "weight_max",
                )
                if k in verdict
            }
            if "picks" not in seen:  # no quota field: no raking (representative_sampling.py:137)
                seen["picks"] = [int(i) for i in out["_zdroj_index"]]
                seen["base_weights"] = [float(x) for x in out["_base_sample_weight"]]
                seen["analysis_weights"] = [float(x) for x in out["_analysis_weight"]]
        result.update(seen)
        results.append(result)

    rakes = []
    for case in cases["rakes"]:
        sample = pd.DataFrame(case["columns"])
        sample["_base_sample_weight"] = case["base"]
        goal = {f: dict(shares) for f, shares in case["targets"]}
        rakes.append({"id": case["id"], "weights": [float(x) for x in original_rake(sample, goal)]})

    expected = {
        "rakes": rakes,
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
