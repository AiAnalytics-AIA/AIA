#!/usr/bin/env python3
"""Recompute a stored experimental Sociomapping with NumPy, independently of aia_core.

    python tools/sociomapping_independent_check.py [--db tmp/ui-workbench/aia.sqlite]
                                                   [--artifacts tmp/ui-workbench/artifacts]

Reads the newest ``research_sociomapping`` artifact of a workbench (or any SQLite +
filesystem store) and the fieldwork dataset it names, then, without importing anything of
AIA's sociomap code:

* recomputes each set's complete respondents, the Pearson correlations between objects
  (``numpy.corrcoef``) and each object's average answer, and compares them with what was
  stored;
* recomputes the stored layout's accuracy -- Spearman over all defined ordered pairs of
  (relation, -distance), average ranks -- and its per-point values.

It checks arithmetic and the evaluator's definition, nothing more: it says nothing about
whether the layout is SOMECS's (it is AIA's experimental method) or whether it is the best
layout. Needs NumPy (a scratch or repository environment). Exit 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def _load(conn: sqlite3.Connection, root: Path, artifact_id: str) -> dict:
    key = conn.execute(
        "select storage_key from project_artifacts where artifact_id = ?", (artifact_id,)
    ).fetchone()[0]
    return json.loads((root / key).read_text("utf-8"))


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values))
    sorted_values = values[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and sorted_values[j + 1] == sorted_values[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or np.all(a == a[0]) or np.all(b == b[0]):
        return None
    return float(np.corrcoef(_ranks(a), _ranks(b))[0, 1])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(REPO / "tmp/ui-workbench/aia.sqlite"))
    parser.add_argument("--artifacts", default=str(REPO / "tmp/ui-workbench/artifacts"))
    args = parser.parse_args(argv)
    conn = sqlite3.connect(args.db)
    root = Path(args.artifacts)
    row = conn.execute(
        "select artifact_id from project_artifacts where artifact_type = 'research_sociomapping' "
        "order by created_at desc limit 1"
    ).fetchone()
    if row is None:
        print("no research_sociomapping artifact")
        return 1
    result = _load(conn, root, row[0])["sociomapping"]
    dataset = _load(conn, root, result["inputs"]["dataset_artifact_id"])["dataset"]
    print(f"result {row[0]}: {result['method']['name']} ({result['method_status']})")
    worst = 0.0
    problems: list[str] = []
    for battery in result["batteries"]:
        ids = [o["id"] for o in battery["objects"]]
        questions = [f"{battery['battery_id']}_obj_{i}" for i in ids]
        rows = []
        for respondent in dataset["respondents"]:
            values = [respondent["answers"].get(q) for q in questions]
            if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
                rows.append(values)
        answers = np.array(rows, dtype=float)
        if len(rows) != battery["support"]["respondents_complete"]:
            problems.append(f"{battery['title']}: complete respondents differ")
        r = np.corrcoef(answers, rowvar=False)
        stored = battery["relations"]["matrix"]
        for i in range(len(ids)):
            for j in range(len(ids)):
                if i == j or stored[i][j] is None:
                    continue
                worst = max(worst, abs(r[i, j] - stored[i][j]))
        means = answers.mean(axis=0)
        worst = max(worst, float(np.max(np.abs(means - np.array(battery["heights"]["on_scale"])))))
        layout = battery["layout"]
        if layout is None:
            print(f"  {battery['title']}: not mapped ({battery['reason']})")
            continue
        index = [ids.index(e) for e in layout["element_ids"]]
        points = np.array(layout["positions"])
        relations, closeness = [], []
        per_point = []
        for a, ia in enumerate(index):
            row_rel, row_close = [], []
            for b, ib in enumerate(index):
                if a == b or stored[ia][ib] is None:
                    continue
                d = float(np.hypot(*(points[a] - points[b])))
                relations.append(stored[ia][ib])
                closeness.append(-d)
                row_rel.append(stored[ia][ib])
                row_close.append(-d)
            per_point.append(_spearman(np.array(row_rel), np.array(row_close)))
        overall = _spearman(np.array(relations), np.array(closeness))
        stored_overall = layout["accuracy"]["overall"]
        assert overall is not None and stored_overall is not None
        worst = max(worst, abs(overall - stored_overall))
        for mine, theirs in zip(per_point, layout["accuracy"]["per_point"], strict=True):
            if (mine is None) != (theirs is None):
                problems.append(f"{battery['title']}: a per-point value is undefined on one side")
            elif mine is not None:
                worst = max(worst, abs(mine - theirs))
        print(
            f"  {battery['title']}: {len(rows)} complete respondents, {len(ids)} objects, "
            f"{len(index)} placed; accuracy stored {stored_overall:.6f}, recomputed {overall:.6f}"
        )
    print(f"largest absolute difference: {worst:.2e}")
    if worst > 1e-9:
        problems.append(f"difference {worst:.2e} exceeds 1e-9")
    for p in problems:
        print(f"MISMATCH {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
