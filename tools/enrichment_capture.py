#!/usr/bin/env python3
"""Capture enrichment fixtures from the vendored 18.6.6 unit (panel-grounded-respondents 2d).

The seven ``*_derived`` fields the ANALYSIS population view needs are computed by the
unit's ``audience_dimensions.attach_derived`` (``audience_dimensions.py:137-182``), which
OI-7 believed lost and which is vendored byte-identical. Two steps, two environments:

    python tools/enrichment_capture.py inputs
        (repo environment) write the fictional rows to
        packages/aia_core/tests/fixtures/enrichment/: ``full.csv`` (every input the
        derivation reads) and ``partial.csv`` (the leisure inputs and the financial score
        absent, as a population without them would be)

    <a venv with pandas>=2.1,<3 and numpy>=1.26,<3>/bin/python tools/enrichment_capture.py capture
        (the unit's environment) read each file exactly as ``pipeline.Panel.from_csv``
        does, run the unit's own, unmodified ``audience_dimensions.enrich_panel``, and
        write ``expected.json``: each derived field per row as text (``null`` where the
        unit holds NA), pinned to the inputs and the unit sources by SHA256.

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
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "enrichment"
UNIT_SOURCES = ("audience_dimensions.py",)

FLAGS = ("is_parent", "is_student", "is_employed", "has_partner")
DIGITAL = (
    "smartphone_use_intensity_1_10",
    "computer_use_intensity_1_10",
    "digital_communication_intensity_1_10",
    "online_information_intensity_1_10",
    "online_entertainment_intensity_1_10",
    "online_transactions_intensity_1_10",
    "digital_personal_management_intensity_1_10",
)
MEDIA = (
    "tv_intensity_1_10",
    "radio_intensity_1_10",
    "print_intensity_1_10",
    "social_media_intensity_1_10",
)
LEISURE = (
    "gaming_intensity_1_10",
    "travel_intensity_1_10",
    "sport_activity_1_10",
    "outdoor_activity_1_10",
    "socializing_offline_1_10",
    "dining_out_1_10",
    "culture_activity_1_10",
    "nightlife_1_10",
    "diy_home_activity_1_10",
    "cooking_activity_1_10",
)
SHOPPING = (
    "price_sensitivity_1_10",
    "deal_proneness_1_10",
    "premium_willingness_1_10",
    "status_consumption_1_10",
    "research_orientation_1_10",
    "review_reliance_1_10",
    "convenience_orientation_1_10",
)
ADVERTISING = (
    "social_proof_susceptibility_1_10",
    "influencer_receptivity_1_10",
    "authority_receptivity_1_10",
    "scarcity_response_1_10",
    "tv_ad_attention_1_10",
    "social_ad_attention_1_10",
    "search_ad_attention_1_10",
    "advertising_skepticism_1_10",
    "reactance_1_10",
    "ad_avoidance_1_10",
)
FINANCE = ("financial_capability_1_10",)
SCORES = (*DIGITAL, *MEDIA, *LEISURE, *SHOPPING, *ADVERTISING, *FINANCE)
HEADER = ("panel_row_id", "vek", *FLAGS, *SCORES)

#: Values that sit exactly on a tier boundary or tie with each other.
_EDGES = ("3", "3.0", "5.5", "7.5", "3.25", "5.75", "7.25", "1", "10")


def _score(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.12:
        return ""
    if roll < 0.30:
        return rng.choice(_EDGES)
    if roll < 0.65:
        return str(rng.randint(1, 10))
    return f"{rng.uniform(1, 10):.2f}"


def _rows(seed: int = 20261012) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    # Ages on every cut the life-stage rule uses, then random ones.
    ages = ["", "18", "29", "30", "34", "35", "64", "65", "89"]
    ages += [str(rng.randint(18, 89)) for _ in range(111)]
    for i, age in enumerate(ages):
        row = {"panel_row_id": f"FIC-ROW-{i + 1:04d}", "vek": age}
        for flag in FLAGS:
            row[flag] = "" if rng.random() < 0.05 else str(int(rng.random() < 0.4))
        for name in SCORES:
            row[name] = _score(rng)
        rows.append(row)
    # A row with no score at all: every "dominant" field falls back, every tier is NA.
    rows.append({**dict.fromkeys(HEADER, ""), "panel_row_id": "FIC-ROW-EMPTY", "vek": "40"})
    # A row where every media and leisure input ties.
    tie = dict.fromkeys(SCORES, "5")
    rows.append({**tie, "panel_row_id": "FIC-ROW-TIE", "vek": "50", **dict.fromkeys(FLAGS, "0")})
    return rows


def _csv(header: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([[row.get(h, "") for h in header] for row in rows])
    return buffer.getvalue().encode("utf-8")


FILES: dict[str, tuple[str, ...]] = {
    "full.csv": HEADER,
    "partial.csv": tuple(h for h in HEADER if h not in LEISURE and h not in FINANCE),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_inputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = _rows()
    for name, header in FILES.items():
        (OUT / name).write_bytes(_csv(header, rows))
    print(f"wrote {', '.join(FILES)} to {OUT}")


def capture() -> None:
    import pandas as pd  # the unit's environment only

    sys.path.insert(0, str(UNIT))
    import audience_dimensions  # the unit's own module

    files: dict[str, Any] = {}
    for name in FILES:
        data = (OUT / name).read_bytes()
        df = pd.read_csv(io.BytesIO(data), low_memory=False, dtype={"occupation_isco08": "string"})
        enriched = audience_dimensions.enrich_panel(df)
        files[name] = {
            "sha256": _sha(data),
            "derived": {
                field: [None if pd.isna(v) else str(v) for v in enriched[field]]
                for field in audience_dimensions.DERIVED_COLUMNS
            },
        }
    expected = {
        "captured_with": {"pandas": pd.__version__},
        "unit_sources": {name: _sha((UNIT / name).read_bytes()) for name in UNIT_SOURCES},
        "files": files,
    }
    (OUT / "expected.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT / 'expected.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=("inputs", "capture"))
    args = parser.parse_args()
    write_inputs() if args.step == "inputs" else capture()


if __name__ == "__main__":
    main()
