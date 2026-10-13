#!/usr/bin/env python3
"""Capture audience-filter fixtures from the vendored 18.6.6 unit (panel-grounded-respondents 2c).

Two steps, in two environments, because the port lives in a stdlib-only domain and
the unit needs pandas:

    python tools/audience_capture.py inputs
        (repo environment) write the fictional rows and the filter cases to
        packages/aia_core/tests/fixtures/audience_filter/

    <a venv with pandas>=2.1,<3 and numpy>=1.26,<3>/bin/python tools/audience_capture.py capture
        (the unit's environment) load the panel exactly as ``pipeline.Panel.from_csv``
        does (``pd.read_csv(low_memory=False, dtype={'occupation_isco08': 'string'})``),
        attach the unit's runtime dimensions (``audience_dimensions.enrich_panel``, as
        ``Panel.__init__`` does), then run the unit's own, unmodified
        ``audience.sanitize_filters`` and ``audience._mask`` on every case. Writes
        ``expected.json``: each case's kept filters (every value as its type and its
        ``str``), the dropped reasons, and the matching row positions; and every
        factor's kind as ``audience_dimensions.factor_map`` computes it. Pins the
        panel, the cases and the unit sources by SHA256. Writes ``catalogue.json``: the
        unit's own ``audience_dimensions.catalog`` on the same panel, as its
        ``/api/audience/dimensions`` route served it (6b).

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
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "audience_filter"
UNIT_SOURCES = ("audience.py", "audience_dimensions.py")

KRAJE = ("Hlavní město Praha", "Středočeský kraj", "Jihomoravský kraj", "Zlínský kraj")
VZDELANI = ("základní", "střední bez maturity", "střední s maturitou", "VOŠ/VŠ")
STATUS = ("employed", "unemployed", "inactive")

#: Every column the cases touch, chosen to exercise each pandas type the unit's kind
#: rule sees: int (no empty cell), float (an empty cell or a decimal), bool, text, and
#: the one column the unit forces to text. ``is_employed`` is here because the unit's
#: ``attach_derived`` fails without it (``audience_dimensions.py:143``: a scalar default
#: has no ``fillna``); the real panel carries it.
HEADER = (
    "panel_row_id",
    "core_donor_id",
    "vek",
    "vek_skupina",
    "pohlavi",
    "kraj",
    "vzdelani",
    "zamestnani_status",
    "is_student",
    "is_employed",
    "is_parent",
    "has_partner",
    "prijem_decile",
    "price_sensitivity_1_10",
    "internet_user_2025",
    "occupation_isco08",
    "PHQ9_2022",
    "vaha_strukturalni_2025",
)

CASES: list[dict[str, Any]] = [
    {"id": "C01_no_filter", "filters": {}},
    {"id": "C02_equality_text", "filters": {"pohlavi": "žena"}},
    {"id": "C03_list_keeps_existing_only", "filters": {"kraj": ["Hlavní město Praha", "Brno"]}},
    {"id": "C04_numeric_min_max", "filters": {"vek": {"min": 30, "max": 50}}},
    {"id": "C05_numeric_pair_swapped", "filters": {"vek": [50, 30]}},
    {"id": "C06_numeric_scalar", "filters": {"vek": 40}},
    {"id": "C07_numeric_invalid", "filters": {"vek": "abc"}},
    {"id": "C08_numeric_open_max", "filters": {"vek": {"max": 25}}},
    {"id": "C09_scale_open_min", "filters": {"price_sensitivity_1_10": {"min": 7}}},
    {"id": "C10_decile_pair_is_interval", "filters": {"prijem_decile": [1, 2]}},
    {"id": "C11_binary_int_column", "filters": {"is_student": 1}},
    {"id": "C12_binary_float_column_int_value", "filters": {"is_parent": 1}},
    {"id": "C13_binary_float_column_bool_value", "filters": {"is_parent": True}},
    {"id": "C14_binary_float_column_text_value", "filters": {"is_parent": "1.0"}},
    {"id": "C15_binary_both_values", "filters": {"internet_user_2025": [0, 1]}},
    {"id": "C16_bool_column", "filters": {"has_partner": True}},
    {"id": "C17_research_only_refused", "filters": {"PHQ9_2022": 5}},
    {"id": "C18_unknown_column", "filters": {"neexistuje": 1}},
    {"id": "C19_empty_list", "filters": {"vzdelani": []}},
    {"id": "C20_category_list", "filters": {"zamestnani_status": ["employed", "unemployed"]}},
    {"id": "C21_derived_dimension", "filters": {"life_stage_derived": "Rodič"}},
    {
        "id": "C22_and_across_dimensions",
        "filters": {"pohlavi": "muž", "vek": {"min": 18, "max": 39}},
    },
    {"id": "C23_age_group", "filters": {"vek_skupina": ["18-29", "30-44"]}},
    {"id": "C24_not_filterable_text", "filters": {"occupation_isco08": "0110"}},
    {"id": "C25_mixed_kept_and_dropped", "filters": {"kraj": "Zlínský kraj", "neexistuje": 1}},
]


def _rows(n: int = 60, seed: int = 20261012) -> list[list[str]]:
    rng = random.Random(seed)
    rows: list[list[str]] = []
    for i in range(n):
        vek = rng.randint(18, 89)
        group = "18-29" if vek < 30 else "30-44" if vek < 45 else "45-59" if vek < 60 else "60+"
        rows.append(
            [
                f"FIC-ROW-{i + 1:04d}",
                f"FIC-DONOR-{rng.randrange(20) + 1:03d}",
                str(vek),
                group,
                rng.choice(("muž", "žena")),
                rng.choice(KRAJE),
                rng.choice(VZDELANI),
                rng.choice(STATUS),
                str(int(vek < 30 and rng.random() < 0.5)),
                str(int(rng.random() < 0.6)),
                # An empty cell makes pandas read the column as float: "1.0", not "1".
                "" if i % 13 == 0 else str(int(rng.random() < 0.4)),
                rng.choice(("True", "False")),
                str(rng.randint(1, 10)),
                f"{rng.uniform(1, 10):.2f}",
                str(int(rng.random() < 0.8)),
                rng.choice(("0110", "2512", "5223")),
                str(rng.randint(0, 27)),
                f"{rng.uniform(100, 900):.3f}",
            ]
        )
    return rows


def panel_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(_rows())
    return buffer.getvalue().encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rows.csv").write_bytes(panel_csv())
    (OUT / "cases.json").write_text(
        json.dumps(CASES, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'rows.csv'} and {OUT / 'cases.json'}")


def _typed(value: Any) -> dict[str, Any]:
    """A unit value as JSON: its Python type after .item(), and its str (the unit's key)."""
    item = value.item() if hasattr(value, "item") else value
    return {"type": type(item).__name__, "str": str(value)}


def capture() -> None:
    import pandas as pd  # the unit's environment only

    sys.path.insert(0, str(UNIT))
    import audience
    import audience_dimensions
    from audience_dimensions import enrich_panel, factor_map

    panel_bytes = (OUT / "rows.csv").read_bytes()
    cases_bytes = (OUT / "cases.json").read_bytes()
    df = pd.read_csv(
        io.BytesIO(panel_bytes), low_memory=False, dtype={"occupation_isco08": "string"}
    )
    df = enrich_panel(df).reset_index(drop=True)

    factors = {}
    for key, spec in factor_map(df).items():
        entry = {"kind": spec["kind"], "filterable": spec["filterable"]}
        if spec["kind"] == "numeric":
            entry["min"] = spec.get("min")
            entry["max"] = spec.get("max")
        factors[key] = entry

    results = []
    for case in json.loads(cases_bytes):
        clean, dropped = audience.sanitize_filters(df, case["filters"])
        mask = audience._mask(df, clean)
        kept: dict[str, Any] = {}
        for key, value in clean.items():
            if isinstance(value, tuple):
                kept[key] = {"interval": [float(value[0]), float(value[1])]}
            elif isinstance(value, list):
                kept[key] = {"values": [_typed(v) for v in value]}
            else:
                kept[key] = {"value": _typed(value)}
        results.append(
            {
                "id": case["id"],
                "kept": kept,
                "dropped": list(dropped),
                "rows": [int(i) for i in df.index[mask.to_numpy()]],
            }
        )

    # The unit's own runtime dimensions, as text: the filter's input, so the filter's
    # parity does not wait on the enricher's port (a separate chunk).
    derived = {
        name: [None if pd.isna(v) else str(v) for v in df[name]]
        for name in audience_dimensions.DERIVED_COLUMNS
        if name in df.columns
    }
    expected = {
        "captured_with": {"pandas": pd.__version__},
        "derived_columns": derived,
        "panel_sha256": _sha(panel_bytes),
        "cases_sha256": _sha(cases_bytes),
        "unit_sources": {name: _sha((UNIT / name).read_bytes()) for name in UNIT_SOURCES},
        "row_count": len(df),
        "factors": factors,
        "cases": results,
    }
    (OUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'expected.json'}: {len(results)} cases, {len(factors)} factors")

    # The factor catalogue (panel-grounded-respondents 6b) as the unit's route serves it:
    # ``catalog(core.load_panel_cached(), include_research_only=True)``
    # (``ui_server.py:1755``), the loaded panel being the enriched one.
    catalogue = audience_dimensions.catalog(df, include_research_only=True)
    (OUT / "catalogue.json").write_text(
        json.dumps(
            {
                "captured_with": {"pandas": pd.__version__},
                "panel_sha256": _sha(panel_bytes),
                "unit_sources": {name: _sha((UNIT / name).read_bytes()) for name in UNIT_SOURCES},
                "catalogue": catalogue,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'catalogue.json'}: {catalogue['factor_count']} factors")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("inputs", "capture"))
    args = parser.parse_args()
    write_inputs() if args.step == "inputs" else capture()


if __name__ == "__main__":
    main()
