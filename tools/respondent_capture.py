#!/usr/bin/env python3
"""Capture respondent response-process fixtures from the vendored 18.6.6 unit.

    <unit venv>/bin/python tools/respondent_capture.py capture

runs the unit's own, unmodified ``behavior.adjust_probabilities`` and
``styly.prirad_styly`` (they need NumPy, pandas and SciPy, which the repository
environment does not install) on fictional inputs generated here from
``random.Random`` with fixed seeds, and writes

    packages/aia_core/tests/fixtures/response_process/behavior.json
    packages/aia_core/tests/fixtures/response_process/styles.json
    packages/aia_core/tests/fixtures/response_process/index.json

``index.json`` pins every fixture and the unit sources it was captured from, by
SHA256. ``test_respondent_behavior.py`` compares AIA's port with them (1e-12 on
probabilities, 1e-9 on style z-scores, where scipy's ``norm.ppf`` and the stdlib's
``NormalDist.inv_cdf`` may differ in the last digits).

No network, no panel data: every input is invented here.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "response_process"
SOURCES = ("behavior.py", "styly.py")
STYLES = (
    "souhlasny_sklon",
    "vyhranenost",
    "ochota_priznat_nevim",
    "sdilnost",
    "satisficing",
    "social_desirability_sensitivity",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def behavior_cases() -> list[dict[str, Any]]:
    """Fictional questions x probability vectors x styles, covering every mechanism."""
    rng = random.Random(20260925)
    cases: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = [
        {"typ": "vyber", "labels": ["A", "B", "C"], "scale": None, "dk": False, "process": None},
        {
            "typ": "vyber",
            "labels": ["A", "B", "C", "Nevím / neodpovím"],
            "scale": None,
            "dk": True,
            "process": None,
        },
        {"typ": "skala", "labels": [], "scale": [1, 5], "dk": False, "process": None},
        {"typ": "skala", "labels": [], "scale": [1, 7], "dk": True, "process": None},
        {"typ": "skala", "labels": [], "scale": [1, 10], "dk": False, "process": None},
        {"typ": "skala", "labels": [], "scale": [0, 1], "dk": False, "process": None},
        {
            "typ": "skala",
            "labels": [],
            "scale": [1, 5],
            "dk": False,
            "process": {"satisficing_strategy": "midpoint"},
        },
        {
            "typ": "vyber",
            "labels": ["A", "B", "C"],
            "scale": None,
            "dk": False,
            "process": {"satisficing_strategy": "first_option", "strength": 0.5},
        },
        {
            "typ": "vyber",
            "labels": ["Souhlasím", "Nesouhlasím"],
            "scale": None,
            "dk": False,
            "process": {
                "agreement_scores": {"Souhlasím": 1.0, "Nesouhlasím": -1.0},
                "social_desirability_scores": [0.5, -0.5],
            },
        },
        {
            "typ": "vyber",
            "labels": ["A", "B"],
            "scale": None,
            "dk": False,
            "process": {"enabled": False},
        },
        {
            "typ": "skala",
            "labels": [],
            "scale": [1, 5],
            "dk": False,
            "process": {"extremity": False, "satisficing_strategy": "none"},
        },
    ]
    for i, shape in enumerate(shapes):
        k = (
            len(shape["labels"])
            if shape["typ"] == "vyber"
            else shape["scale"][1] - shape["scale"][0] + 1 + (1 if shape["dk"] else 0)
        )
        for j in range(6):
            raw = [round(rng.random() ** 2, 6) for _ in range(k)]
            if j == 0:
                raw[0] = 0.0  # a zero option
            if j == 1:
                raw = [v * 3.0 for v in raw]  # unnormalised mass
            style = {s: round(rng.gauss(0.0, 1.2), 6) for s in STYLES}
            if j == 2:
                style = {}
            cases.append({"id": f"B{i:02d}_{j}", **shape, "probabilities": raw, "style": style})
    return cases


def style_rows() -> list[dict[str, Any]]:
    rng = random.Random(20260926)
    education = ["základní", "střední bez maturity", "střední s maturitou", "VOŠ/VŠ", None]
    rows = []
    for i in range(40):
        row: dict[str, Any] = {"respondent_id": f"FIC-R{i + 1:05d}"}
        row["vek"] = rng.randint(18, 90)
        row["pohlavi"] = rng.choice(["muž", "žena"])
        row["vzdelani"] = rng.choice(education)
        rows.append(row)
    return rows


def capture() -> None:
    sys.path.insert(0, str(UNIT))
    import numpy as np
    import pandas as pd
    from behavior import adjust_probabilities
    from styly import prirad_styly

    OUT.mkdir(parents=True, exist_ok=True)
    behavior = []
    for case in behavior_cases():
        question = SimpleNamespace(
            typ=case["typ"],
            volby=case["labels"],
            skala=tuple(case["scale"]) if case["scale"] else None,
            povolit_nevim=case["dk"],
            response_process=case["process"],
        )
        p, meta = adjust_probabilities(np.asarray(case["probabilities"]), question, case["style"])
        behavior.append(
            {
                **case,
                "expected": {
                    "probabilities": [float(x) for x in p],
                    "applied": list(meta.applied),
                    "l1_shift": meta.l1_shift,
                    "base_max_prob": meta.base_max_prob,
                    "adjusted_max_prob": meta.adjusted_max_prob,
                },
            }
        )
    rows = style_rows()
    frame = pd.DataFrame(rows)
    styles = prirad_styly(frame)
    styles_out = {
        "rows": rows,
        "expected": [{s: float(styles.iloc[i][s]) for s in STYLES} for i in range(len(rows))],
    }
    files = {
        "behavior.json": {"cases": behavior},
        "styles.json": styles_out,
    }
    index: dict[str, Any] = {
        "provenance": (
            "Captured by tools/respondent_capture.py from the vendored 18.6.6 unit's own "
            "functions on fictional inputs; never edit by hand."
        ),
        "unit_sources": {name: _sha(UNIT / name) for name in SOURCES},
        "environment": {"numpy": np.__version__, "pandas": pd.__version__},
        "fixtures": {},
    }
    for name, payload in files.items():
        text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
        (OUT / name).write_text(text, encoding="utf-8")
        index["fixtures"][name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(behavior)} behaviour cases and {len(rows)} style rows to {OUT}")


if __name__ == "__main__":
    if sys.argv[1:] != ["capture"]:
        raise SystemExit("usage: respondent_capture.py capture   (in the unit's environment)")
    capture()
