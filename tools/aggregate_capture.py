#!/usr/bin/env python3
"""Capture aggregation fixtures from the vendored 18.6.6 unit (PR C chunk 5, OI-62).

Two steps, in two environments, because the port lives in a stdlib-only domain and
the unit needs NumPy and pandas:

    python tools/aggregate_capture.py cases
        (repo environment) compile each case's fictional design with AIA's compiler
        and build its fictional dataset with AIA's generator; write the inputs to
        packages/aia_core/tests/fixtures/research_aggregate/cases/<id>.json

    python tools/aggregate_capture.py self
        (repo environment) AIA's own aggregate of every case, written to aia_self.json:
        the pin that holds AIA's bounds still (same input, same seed, same bounds)

    tmp/ui-workbench/venv/bin/python tools/aggregate_capture.py capture [--seeds 100]
        (the unit's environment) run the unit's own, unmodified
        ``dotaznik.agreguj_otazku`` on every question and battery object of each
        case, and -- for every interval bound it reports -- the same bootstrap call
        at ``--seeds`` seeds; write <id>.json beside the cases, and index.json
        pinning every file and the unit sources it was captured from.

A fixture holds ``expected`` (the unit's output, compared EXACT by the test) and
``bound_spread`` (per bound: the unit's mean, sd, min and max over the seeds). The
test accepts an AIA bound within ``mean +/- (4 sd + rounding step)``: the unit's
own seed-to-seed variation, which is what OI-62 decided the port must match.

No network, no real panel data: every design and respondent is fictional.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
OUT = ROOT / "packages" / "aia_core" / "tests" / "fixtures" / "research_aggregate"
UNIT_SOURCES = ("dotaznik.py", "uncertainty.py", "fidelity.py")

CASES: dict[str, dict[str, Any]] = {
    "A01_full_questionnaire": {
        "seed": 20260816,
        "design": {
            "title": "Fiktivní ranní nápoj",
            "n": 450,
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {
                            "id": "q1",
                            "text": "Jak často pijete kávu?",
                            "typ": "skala",
                            "skala": [1, 5],
                            "povolit_nevim": True,
                        },
                        {
                            "id": "q2",
                            "text": "Co si ráno koupíte?",
                            "typ": "vyber",
                            "kategorie": ["Kávu", "Čaj", "Nic"],
                            "povolit_nevim": True,
                        },
                        {
                            "id": "q3",
                            "text": "Co k tomu?",
                            "typ": "multi",
                            "kategorie": ["Pečivo", "Ovoce", "Jogurt"],
                        },
                        {"id": "q4", "text": "Proč?", "typ": "otevrena"},
                    ],
                },
                {
                    "type": "object_battery",
                    "title": "Nápoje",
                    "object_family": "nápoje",
                    "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
                    "object_question": "Jak hodnotíte {object}?",
                    "scale": [1, 10],
                },
            ],
        },
    },
    "A02_indicative_support": {
        "seed": 7,
        "design": {
            "title": "Fiktivní malá studie",
            "n": 120,
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {
                            "id": "s1",
                            "text": "Jak jste spokojeni?",
                            "typ": "skala",
                            "skala": [1, 10],
                        },
                        {
                            "id": "s2",
                            "text": "Doporučili byste nás?",
                            "typ": "vyber",
                            "kategorie": ["Ano", "Ne"],
                        },
                    ],
                }
            ],
        },
    },
    "A03_suppressed_support": {
        "seed": 11,
        "design": {
            "title": "Fiktivní potlačená buňka",
            "n": 60,
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {"id": "t1", "text": "Kolikrát týdně?", "typ": "skala", "skala": [0, 7]},
                        {
                            "id": "t2",
                            "text": "Který obchod?",
                            "typ": "multi",
                            "kategorie": ["A", "B"],
                        },
                    ],
                }
            ],
        },
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# step 1: cases (repo environment)
# --------------------------------------------------------------------------- #


def cases() -> int:
    from aia_core.domain.research_design import compile_design
    from aia_core.domain.synthetic_fieldwork import synthetic_dataset

    for case_id, case in CASES.items():
        spec, problems = compile_design(case["design"])
        if spec is None:
            print(f"{case_id}: {problems}", file=sys.stderr)
            return 1
        dataset = synthetic_dataset(spec, seed=case["seed"])
        _dump(
            OUT / "cases" / f"{case_id}.json",
            {
                "case_id": case_id,
                "spec": spec.model_dump(mode="json"),
                "dataset": dataset.model_dump(mode="json"),
            },
        )
        print(f"wrote cases/{case_id}.json ({len(dataset.respondents)} respondents)")
    return 0


def self_fixture() -> int:
    from aia_core.domain.fieldwork import FieldworkDataset
    from aia_core.domain.research_aggregate import aggregate_dataset
    from aia_core.domain.research_design import ResearchSpecification

    pinned: dict[str, Any] = {}
    for case_path in sorted((OUT / "cases").glob("*.json")):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        spec = ResearchSpecification.model_validate(case["spec"])
        dataset = FieldworkDataset.model_validate(case["dataset"])
        pinned[case["case_id"]] = aggregate_dataset(spec, dataset)
    _dump(OUT / "aia_self.json", pinned)
    print(f"wrote aia_self.json ({len(pinned)} cases)")
    return 0


# --------------------------------------------------------------------------- #
# step 2: capture (the unit's environment)
# --------------------------------------------------------------------------- #

DONT_KNOW = "Nevím / neodpovím"


def _unit_questions(spec: dict[str, Any], dotaznik: Any) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for q in spec["questions"]:
        kw: dict[str, Any] = {
            "id": q["id"],
            "text": q["text"],
            "typ": q["typ"],
            "povolit_nevim": q["allow_dont_know"],
        }
        if q["typ"] in ("vyber", "multi"):
            kw["kategorie"] = [o for o in q["options"] if o != DONT_KNOW]
        if q["typ"] == "skala":
            kw["skala"] = tuple(q["scale"])
        out.append((f"questions.{q['id']}", dotaznik.Otazka(**kw)))
    for b in spec["batteries"]:
        for o in b["objects"]:
            qid = f"{b['id']}_obj_{o['id']}"
            out.append(
                (
                    f"batteries.{b['id']}.objects.{o['id']}",
                    dotaznik.Otazka(
                        id=qid,
                        text=b["question_template"].replace("{object}", o["label"]),
                        typ="skala",
                        skala=tuple(b["scale"]),
                        povolit_nevim=False,
                    ),
                )
            )
    return out


def _frame(dataset: dict[str, Any], qids: list[str], pd: Any) -> Any:
    """The unit's frame: one column per item, NaN for no answer, its weight and donor."""
    rows = []
    for r in dataset["respondents"]:
        row: dict[str, Any] = {"_analysis_weight": r["weight"], "core_donor_id": r["donor_id"]}
        for qid in qids:
            value = r["answers"].get(qid)
            row[qid] = float("nan") if value is None else value
        rows.append(row)
    return pd.DataFrame(rows)


def _spread(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "sd": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def _bounds(
    path: str, o: Any, frame: Any, seeds: list[int], unc: Any, np: Any, pd: Any
) -> dict[str, dict[str, float]]:
    """The unit's own bootstrap calls from agreguj_otazku, at every seed."""
    s = frame[o.id]
    ok = frame[s.notna()].copy()
    if not len(ok):
        return {}
    w = unc.clean_weights(ok)
    donors = unc.donor_ids(ok, "core_donor_id")
    out: dict[str, list[float]] = {}

    def add(key: str, value: float) -> None:
        out.setdefault(f"{path}.{key}", []).append(value)

    for seed_shift in seeds:
        if o.typ == "vyber":
            ci = unc.bootstrap_weighted_distribution(
                ok[o.id], o.volby, w, reps=400, seed=20260816 + seed_shift, donors=donors
            )
            for cat, v in ci.items():
                add(f"intervaly_95.{cat}.low", v["low"])
                add(f"intervaly_95.{cat}.high", v["high"])
        elif o.typ == "multi":
            lists = ok[o.id].tolist()
            for ii, choice in enumerate(o.volby):
                hit = np.array([choice in (lst or []) for lst in lists], dtype=float)
                bci = unc.cluster_bootstrap_binary(
                    hit, w, donors, reps=350, seed=20260816 + ii + seed_shift
                )
                if bci:
                    add(f"intervaly_95.{choice}.low", round(100.0 * float(bci["low"]), 1))
                    add(f"intervaly_95.{choice}.high", round(100.0 * float(bci["high"]), 1))
        elif o.typ == "skala":
            v = pd.to_numeric(ok[o.id], errors="coerce").to_numpy(float)
            ci = unc.bootstrap_weighted_mean(
                v, w, reps=400, seed=20260816 + seed_shift, donors=donors
            )
            top = (v >= o.skala[1] - 1).astype(float)
            tci = unc.bootstrap_weighted_mean(
                top, w, reps=400, seed=20260818 + seed_shift, donors=donors
            )
            if ci:
                add("prumer_interval_95.low", round(float(ci["low"]), 2))
                add("prumer_interval_95.high", round(float(ci["high"]), 2))
            if tci:
                add("top2box_interval_95.low", round(100.0 * float(tci["low"]), 1))
                add("top2box_interval_95.high", round(100.0 * float(tci["high"]), 1))
    return {key: _spread(vals) for key, vals in out.items()}


def capture(n_seeds: int) -> int:
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        print("capture needs numpy and pandas: run it with the unit's environment", file=sys.stderr)
        return 1
    sys.path.insert(0, str(UNIT))
    import dotaznik  # the vendored 18.6.6 modules, unmodified
    import uncertainty as unc

    seeds = [7919 * k for k in range(n_seeds)]  # shift 0 is the unit's own seed
    files: dict[str, str] = {}
    for case_path in sorted((OUT / "cases").glob("*.json")):
        case = json.loads(case_path.read_text(encoding="utf-8"))
        questions = _unit_questions(case["spec"], dotaznik)
        frame = _frame(case["dataset"], [o.id for _, o in questions], pd)
        expected: dict[str, Any] = {}
        spread: dict[str, dict[str, float]] = {}
        for path, o in questions:
            result = dotaznik.agreguj_otazku(frame, o)
            expected[path] = json.loads(json.dumps(result, ensure_ascii=False, default=str))
            spread.update(_bounds(path, o, frame, seeds, unc, np, pd))
        fixture = OUT / f"{case['case_id']}.json"
        _dump(
            fixture,
            {
                "case_id": case["case_id"],
                "case_sha256": _sha256(case_path),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "seeds": n_seeds,
                "tolerance_rule": (
                    "bound within mean +/- (4*sd + rounding step) of the unit's bound "
                    "over the seeds"
                ),
                "expected": expected,
                "bound_spread": spread,
            },
        )
        files[f"cases/{case_path.name}"] = _sha256(case_path)
        files[fixture.name] = _sha256(fixture)
        print(f"captured {fixture.name}: {len(expected)} items, {len(spread)} bounds")
    _dump(
        OUT / "index.json",
        {
            "description": (
                "Aggregation fixtures captured from legacy/npc-panel-18.6.6 by "
                "tools/aggregate_capture.py"
            ),
            "unit_sources": {name: _sha256(UNIT / name) for name in UNIT_SOURCES},
            "files": files,
        },
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cases")
    sub.add_parser("self")
    cap = sub.add_parser("capture")
    cap.add_argument("--seeds", type=int, default=100)
    args = parser.parse_args()
    if args.command == "cases":
        return cases()
    if args.command == "self":
        return self_fixture()
    return capture(args.seeds)


if __name__ == "__main__":
    raise SystemExit(main())
