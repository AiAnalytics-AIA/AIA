"""Paired question-level validation statistics with bootstrap uncertainty."""
from __future__ import annotations

import numpy as np
import pandas as pd

BASELINES = ("generic", "demographics", "core", "full", "shuffled_full")


def paired_validation_stats(df: pd.DataFrame, *, repeats: int = 5000, seed: int = 20260814,
                            ci: float = 0.95) -> dict:
    if df.empty:
        return {"status": "NO_DATA"}
    piv = df.pivot_table(index="question_id", columns="baseline", values="mae_pp", aggfunc="first")
    missing_cols = [b for b in BASELINES if b not in piv.columns]
    if missing_cols:
        return {"status": "INCOMPLETE", "missing_baselines": missing_cols}
    piv = piv.dropna(subset=list(BASELINES))
    if piv.empty:
        return {"status": "NO_COMPLETE_QUESTIONS"}
    rng = np.random.default_rng(seed)
    n = len(piv)
    alpha = (1-ci)/2
    out = {"status": "OK", "n_complete_questions": int(n), "ci_level": ci, "comparisons": {}}
    full = piv["full"].to_numpy(float)
    for base in ("generic", "demographics", "core", "shuffled_full"):
        b = piv[base].to_numpy(float)
        diff = b - full  # positive means full is better
        means = np.empty(repeats, dtype=float)
        wins = np.empty(repeats, dtype=float)
        for i in range(repeats):
            ix = rng.integers(0, n, n)
            d = diff[ix]
            means[i] = d.mean()
            wins[i] = np.mean(d > 0)
        out["comparisons"][base] = {
            "mean_improvement_pp": round(float(diff.mean()), 4),
            "improvement_ci_low_pp": round(float(np.quantile(means, alpha)), 4),
            "improvement_ci_high_pp": round(float(np.quantile(means, 1-alpha)), 4),
            "win_rate": round(float(np.mean(diff > 0)), 4),
            "win_rate_ci_low": round(float(np.quantile(wins, alpha)), 4),
            "win_rate_ci_high": round(float(np.quantile(wins, 1-alpha)), 4),
            "median_improvement_pp": round(float(np.median(diff)), 4),
        }
    return out


def domain_coverage(df: pd.DataFrame) -> dict:
    if df.empty or "domain" not in df.columns:
        return {"n_domains": 0, "questions_per_domain": {}, "missing_domain": True}
    q = df[["question_id", "domain"]].drop_duplicates("question_id")
    q["domain"] = q["domain"].fillna("").astype(str).str.strip()
    counts = q[q.domain != ""].groupby("domain").size().sort_values(ascending=False).to_dict()
    return {
        "n_domains": len(counts),
        "questions_per_domain": {str(k): int(v) for k, v in counts.items()},
        "missing_domain": bool((q.domain == "").any()),
    }


def per_domain_performance(df: pd.DataFrame) -> dict:
    if df.empty or "domain" not in df.columns:
        return {}
    g = df.groupby(["domain", "baseline"], dropna=False)["mae_pp"].mean().unstack("baseline")
    out = {}
    for dom, row in g.iterrows():
        if not str(dom).strip():
            continue
        d = {str(k): round(float(v), 3) for k, v in row.dropna().items()}
        if "full" in d:
            for b in ("generic", "demographics", "core", "shuffled_full"):
                if b in d:
                    d[f"full_improvement_vs_{b}_pp"] = round(d[b] - d["full"], 3)
        out[str(dom)] = d
    return out
