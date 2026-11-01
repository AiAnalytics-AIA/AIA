#!/usr/bin/env python3
"""Capture run-QC fixtures from the vendored 18.6.6 unit's own ``qc.kontrola``.

    python tools/run_qc_capture.py inputs                     # repo env: the fictional runs
    <venv with pandas + NumPy>/bin/python tools/run_qc_capture.py capture
    python tools/run_qc_capture.py verify                     # repo env: the pins hold

``inputs`` writes fictional runs (questions and every respondent's answers) generated here
from ``random.Random`` with fixed seeds. ``capture`` builds each run's ``detail`` frame as the
unit's ``run_dotaznik`` allocates it (``dotaznik.py:697-712``: every per-question column
``None``, ``_eligible_`` set for the respondents asked, the probability and behaviour columns
NaN, ``_chyba`` from no errors) and runs the unit's unmodified ``kontrola`` on it. It writes

    packages/aia_core/tests/fixtures/run_qc/cases.json
    packages/aia_core/tests/fixtures/run_qc/kontrola.json
    packages/aia_core/tests/fixtures/run_qc/index.json

``index.json`` pins both fixtures and ``qc.py`` by SHA-256. ``test_run_qc.py`` compares AIA's
port (``domain/run_qc.py``, evidence-integrity 2a) with them. No network, no panel data, no
demographic column: the checks that read demographics or each draw's probabilities are 2b and
2c, and the unit skips them on these runs exactly as it does on a run without those columns.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "run_qc"
DONT_KNOW = "Nevím / neodpovím"
WORDS = ("cena", "kvalita", "dostupnost", "chuť", "obal", "značka", "doprava", "servis")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _choice(rng: random.Random, options: list[str], weights: list[float]) -> str:
    return rng.choices(options, weights=weights)[0]


def _run(
    case_id: str,
    seed: int,
    *,
    n: int,
    scales: int,
    straight: float,
    dont_know: float,
    concentrated: bool,
    missing: float,
    flat_scale: bool,
    open_repeats: bool,
    mode: str,
    ablation: bool,
    choice_options: int = 4,
) -> dict[str, Any]:
    rng = random.Random(seed)
    options = [f"Možnost {k + 1}" for k in range(choice_options)]
    questions: list[dict[str, Any]] = [
        {"id": "q_choice", "typ": "vyber", "volby": [*options, DONT_KNOW]},
        {"id": "q_plain", "typ": "vyber", "volby": ["Ano", "Ne"]},
        {"id": "q_multi", "typ": "multi", "volby": ["A", "B", "C"]},
        *({"id": f"q_scale_{k}", "typ": "skala", "volby": []} for k in range(scales)),
        {"id": "q_open", "typ": "otevrena", "volby": []},
    ]
    rows: list[dict[str, Any]] = []
    for _ in range(n):
        row: dict[str, Any] = {}
        weights = [60.0, 1.0, 1.0, 1.0][:choice_options] if concentrated else [1.0] * choice_options
        row["q_choice"] = DONT_KNOW if rng.random() < dont_know else _choice(rng, options, weights)
        row["q_plain"] = rng.choice(["Ano", "Ne"])
        row["q_multi"] = sorted(rng.sample(["A", "B", "C"], rng.randint(1, 3)))
        liner = rng.random() < straight
        level = rng.randint(1, 5)
        for k in range(scales):
            if flat_scale and k == 0:
                row[f"q_scale_{k}"] = 3
            elif liner:
                row[f"q_scale_{k}"] = level
            else:
                row[f"q_scale_{k}"] = None if rng.random() < 0.05 else rng.randint(1, 5)
        if open_repeats:
            row["q_open"] = rng.choice(["Je to dobré.", "je to dobré. ", "Nevím."])
        else:
            row["q_open"] = " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 6)))
        for qid in list(row):
            if rng.random() < missing:
                row[qid] = None
        rows.append(row)
    return {"id": case_id, "mode": mode, "ablation": ablation, "otazky": questions, "rows": rows}


def cases() -> list[dict[str, Any]]:
    base: dict[str, Any] = {
        "n": 60,
        "scales": 4,
        "straight": 0.0,
        "dont_know": 0.10,
        "concentrated": False,
        "missing": 0.0,
        "flat_scale": False,
        "open_repeats": False,
        "mode": "live",
        "ablation": False,
    }
    variants: list[tuple[str, dict[str, Any]]] = [
        ("clean", {}),
        ("straight_liners_above", {"straight": 0.40}),
        ("straight_liners_below", {"straight": 0.08}),
        ("two_scales_no_straight_lining_read", {"scales": 2, "straight": 0.60}),
        ("three_scales", {"scales": 3, "straight": 0.30}),
        ("no_dont_know", {"dont_know": 0.0}),
        ("too_much_dont_know", {"dont_know": 0.50}),
        ("concentrated", {"concentrated": True, "dont_know": 0.0}),
        ("missing_answers", {"missing": 0.30}),
        ("flat_scale", {"flat_scale": True}),
        ("open_repeats_live", {"open_repeats": True}),
        ("open_repeats_dry", {"open_repeats": True, "mode": "dry"}),
        ("ablation_verified", {"ablation": True}),
        ("small_space_duplicates", {"scales": 0, "n": 200, "choice_options": 2}),
        ("large_space_duplicates", {"scales": 6, "straight": 0.5, "n": 40}),
        ("tiny_run", {"n": 3, "straight": 0.5}),
        ("one_respondent", {"n": 1}),
        ("everything_missing", {"missing": 1.0}),
        ("big_run", {"n": 400, "straight": 0.16}),
    ]
    out = []
    for k, (name, change) in enumerate(variants):
        params = {**base, **change}
        out.append(_run(name, 20261028 + k, **params))
    return out


def _nan_safe(value: Any) -> Any:
    """JSON holds no NaN: a NaN is written as the string ``"NaN"``, numpy scalars as Python's."""
    if isinstance(value, dict):
        return {str(k): _nan_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_nan_safe(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return value


def capture() -> None:
    import numpy as np
    import pandas as pd

    sys.path.insert(0, str(UNIT))
    from qc import kontrola  # the unit's own, unmodified

    runs = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))
    results = []
    for run in runs:
        n = len(run["rows"])
        detail = pd.DataFrame(index=range(n))
        for o in run["otazky"]:
            oid = o["id"]
            detail[oid] = [None] * n
            detail[f"_eligible_{oid}"] = [False] * n
            detail[f"_chyba_{oid}"] = [None] * n
            detail[f"_entropy_{oid}"] = [np.nan] * n
            detail[f"_maxprob_{oid}"] = [np.nan] * n
            detail[f"_behavior_l1_{oid}"] = [np.nan] * n
        for i, row in enumerate(run["rows"]):
            for oid, value in row.items():
                if value is not None:
                    detail.at[i, oid] = value
        for o in run["otazky"]:
            detail.loc[:, f"_eligible_{o['id']}"] = True  # no display condition: everyone asked
        detail["_chyba"] = [None] * n
        v = {
            "detail": detail,
            "otazky": run["otazky"],
            "mode": run["mode"],
            "ablation": run["ablation"],
        }
        results.append({"id": run["id"], "result": _nan_safe(kontrola(v))})
    _write("kontrola.json", results)
    index = {
        "unit_source": {"qc.py": _sha(UNIT / "qc.py")},
        "captured_with": {"pandas": pd.__version__, "numpy": np.__version__},
        "fixtures": {name: _sha(OUT / name) for name in ("cases.json", "kontrola.json")},
    }
    _write("index.json", index)


def _write(name: str, payload: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False)
    (OUT / name).write_text(text + "\n", encoding="utf-8")


def verify() -> None:
    index = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    bad = [name for name, sha in index["fixtures"].items() if _sha(OUT / name) != sha]
    if _sha(UNIT / "qc.py") != index["unit_source"]["qc.py"]:
        bad.append("qc.py")
    if json.loads((OUT / "cases.json").read_text(encoding="utf-8")) != cases():
        bad.append("cases.json (no longer what `inputs` writes)")
    if bad:
        sys.exit(f"run QC fixtures out of date: {', '.join(bad)}")
    print("run QC fixtures verified")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "inputs":
        _write("cases.json", cases())
    elif command == "capture":
        capture()
    elif command == "verify":
        verify()
    else:
        sys.exit(__doc__)
