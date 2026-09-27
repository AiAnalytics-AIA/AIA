"""Validation/stability diagnostics that do not pretend larger synthetic N removes bias."""
from __future__ import annotations

import json
from typing import Any, Iterable
import numpy as np
import pandas as pd


def _prob_matrix(detail: pd.DataFrame, question_id: str) -> np.ndarray:
    col = f"_probs_{question_id}"
    if col not in detail.columns:
        raise KeyError(f"{col} chybi; N-saturation vyzaduje probability response mode")
    rows = []
    for x in detail[col].dropna():
        try:
            a = np.asarray(json.loads(x), dtype=float)
            if len(a) and np.isfinite(a).all() and a.sum() > 0:
                rows.append(a / a.sum())
        except Exception:
            pass
    if not rows:
        raise ValueError("zadne validni probability vectors")
    k = len(rows[0])
    rows = [x for x in rows if len(x) == k]
    return np.vstack(rows)


def n_saturation(detail: pd.DataFrame, question_id: str, *, sizes: Iterable[int] = (100, 250, 500, 1000, 2500),
                 repeats: int = 100, seed: int = 0) -> dict[str, Any]:
    """Subsample stored probability vectors; reports MC stability as N grows.

    This measures finite synthetic-sample noise only. It explicitly does not estimate
    model bias versus humans.
    """
    M = _prob_matrix(detail, question_id)
    rng = np.random.default_rng(seed)
    full = M.mean(axis=0)
    rows = []
    for n in sizes:
        n = int(n)
        if n <= 0 or n > len(M):
            continue
        draws = []
        for _ in range(int(repeats)):
            idx = rng.choice(len(M), size=n, replace=False)
            draws.append(M[idx].mean(axis=0))
        D = np.vstack(draws)
        mae = np.mean(np.abs(D - full), axis=1)
        rows.append({
            "n": n,
            "mean_abs_deviation_pp": round(float(100 * mae.mean()), 4),
            "p95_abs_deviation_pp": round(float(100 * np.quantile(mae, .95)), 4),
            "max_category_sd_pp": round(float(100 * D.std(axis=0, ddof=1).max()), 4),
        })
    return {"question_id": question_id, "available_n": int(len(M)), "curve": rows,
            "full_expected_pct": [round(float(100*x), 3) for x in full],
            "interpretation": "Sampling/Monte-Carlo stability only; says nothing about bias versus real respondents."}


def behavior_impact(detail: pd.DataFrame, question_id: str) -> dict[str, Any]:
    """Compare pre/post behavioral-process probability vectors."""
    a_col, b_col = f"_probs_base_{question_id}", f"_probs_{question_id}"
    if a_col not in detail.columns or b_col not in detail.columns:
        raise KeyError("behavior impact requires stored base and adjusted probabilities")
    shifts = []
    for a, b in zip(detail[a_col], detail[b_col]):
        if pd.isna(a) or pd.isna(b):
            continue
        try:
            pa = np.asarray(json.loads(a), float); pb = np.asarray(json.loads(b), float)
            if len(pa) == len(pb) and len(pa):
                shifts.append(np.abs(pa/pa.sum() - pb/pb.sum()).sum())
        except Exception:
            continue
    if not shifts:
        return {"question_id": question_id, "n": 0}
    x = np.asarray(shifts)
    return {"question_id": question_id, "n": int(len(x)),
            "mean_l1_shift": round(float(x.mean()), 5),
            "p95_l1_shift": round(float(np.quantile(x, .95)), 5),
            "max_l1_shift": round(float(x.max()), 5)}


def variance_decomposition(repeated: pd.DataFrame, *, case_col: str, value_col: str) -> dict[str, Any]:
    """ANOVA-style within/between decomposition for repeated runs of same cases.

    Input must contain repeated observations of identical synthetic cases. Useful for
    live provider repeatability experiments; with deterministic probability mode the
    within component should be small.
    """
    d = repeated[[case_col, value_col]].copy()
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce")
    d = d.dropna()
    groups = [g[value_col].to_numpy(float) for _, g in d.groupby(case_col) if len(g) >= 2]
    if len(groups) < 2:
        raise ValueError("variance decomposition needs >=2 cases with repeats")
    within = float(np.mean([np.var(g, ddof=1) for g in groups]))
    means = np.asarray([np.mean(g) for g in groups])
    between_observed = float(np.var(means, ddof=1))
    mean_r = float(np.mean([len(g) for g in groups]))
    between = max(0.0, between_observed - within / max(mean_r, 1.0))
    total = within + between
    return {"n_cases": len(groups), "mean_repeats": round(mean_r, 2),
            "within_variance": round(within, 6), "between_variance": round(between, 6),
            "within_share": round(within/total, 4) if total else None,
            "between_share": round(between/total, 4) if total else None}
