"""Benchmark drift guard for model/prompt/runtime upgrades."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from benchmark import summarize_benchmark
from validation_stats import paired_validation_stats


def compare_benchmarks(reference: pd.DataFrame, candidate: pd.DataFrame,
                       *, max_full_mae_regression_pp: float = 0.75,
                       min_candidate_win_rate_vs_demographics: float = 0.60) -> dict:
    rs = summarize_benchmark(reference); cs = summarize_benchmark(candidate)
    rf = rs.get("mean_mae_pp", {}).get("full"); cf = cs.get("mean_mae_pp", {}).get("full")
    reasons = []
    if rf is None or cf is None:
        reasons.append("missing full baseline")
    elif cf - rf > max_full_mae_regression_pp:
        reasons.append(f"full MAE regressed by {cf-rf:.3f} pp")
    st = paired_validation_stats(candidate, repeats=1500)
    wr = st.get("comparisons", {}).get("demographics", {}).get("win_rate")
    if wr is None or wr < min_candidate_win_rate_vs_demographics:
        reasons.append("candidate full persona no longer wins often enough vs demographics")
    return {
        "status": "PASS" if not reasons else "DRIFT_BLOCK",
        "reasons": reasons,
        "reference_summary": rs,
        "candidate_summary": cs,
        "candidate_paired_stats": st,
    }


def write_drift_report(reference_csv: str | Path, candidate_csv: str | Path,
                       out_path: str | Path) -> Path:
    r = pd.read_csv(reference_csv); c = pd.read_csv(candidate_csv)
    obj = compare_benchmarks(r, c)
    obj["reference_csv"] = str(Path(reference_csv).resolve())
    obj["candidate_csv"] = str(Path(candidate_csv).resolve())
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
