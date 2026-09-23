"""Pricing research helpers for NPC Panel.

Implements standard survey analysis, not a universal behavioral correction. Any
purchase-intent calibration must be supplied with an explicit factor/model and source;
there is intentionally no hard-coded literature multiplier.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable
import numpy as np
import pandas as pd


@dataclass
class PurchaseCalibration:
    method: str
    source: str
    factor: float | None = None
    intercept: float | None = None
    slope: float | None = None


def calibrate_purchase_probability(p: Iterable[float], calibration: PurchaseCalibration) -> np.ndarray:
    x = np.clip(np.asarray(list(p), dtype=float), 1e-6, 1 - 1e-6)
    if calibration.method == "factor":
        if calibration.factor is None or calibration.factor < 0:
            raise ValueError("factor calibration vyzaduje nezaporny factor")
        return np.clip(x * calibration.factor, 0, 1)
    if calibration.method == "logit":
        if calibration.intercept is None or calibration.slope is None:
            raise ValueError("logit calibration vyzaduje intercept a slope")
        logit = np.log(x / (1 - x))
        z = calibration.intercept + calibration.slope * logit
        return 1 / (1 + np.exp(-z))
    raise ValueError("method musi byt factor | logit")


def gabor_granger(price_acceptance: pd.DataFrame, *, price_col: str = "price",
                   accept_col: str = "accept", weight_col: str | None = None) -> dict[str, Any]:
    """Analyze long-form Gabor-Granger observations: one row per respondent-price."""
    d = price_acceptance[[price_col, accept_col] + ([weight_col] if weight_col else [])].copy()
    d[price_col] = pd.to_numeric(d[price_col], errors="coerce")
    d[accept_col] = d[accept_col].astype(float)
    d = d.dropna(subset=[price_col, accept_col])
    rows = []
    for price, g in d.groupby(price_col):
        w = (pd.to_numeric(g[weight_col], errors="coerce").fillna(0).to_numpy(float)
             if weight_col else np.ones(len(g)))
        y = g[accept_col].to_numpy(float)
        if w.sum() <= 0:
            continue
        demand = float(np.dot(y, w) / w.sum())
        rows.append({"price": float(price), "demand": demand,
                     "revenue_index": float(price) * demand, "n": int(len(g))})
    rows.sort(key=lambda r: r["price"])
    if not rows:
        return {"curve": [], "recommended_price": None}
    best = max(rows, key=lambda r: r["revenue_index"])
    return {"curve": rows, "recommended_price": best["price"],
            "max_revenue_index": best["revenue_index"],
            "note": "Revenue index assumes equal market size/cost and is not a profit model."}


def van_westendorp(df: pd.DataFrame, *, too_cheap: str, cheap: str,
                   expensive: str, too_expensive: str, grid_size: int = 400) -> dict[str, Any]:
    """Van Westendorp Price Sensitivity Meter from four numeric price responses."""
    d = df[[too_cheap, cheap, expensive, too_expensive]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(d) < 20:
        raise ValueError("Van Westendorp potrebuje alespon 20 kompletnich odpovedi")
    lo = max(0.0, float(d.min().min()))
    hi = float(d.max().max())
    if hi <= lo:
        raise ValueError("cenove odpovedi nemaji rozsah")
    grid = np.linspace(lo, hi, grid_size)
    # Standard cumulative/reverse cumulative curves.
    curves = {
        "too_cheap": np.array([(d[too_cheap] >= x).mean() for x in grid]),
        "cheap": np.array([(d[cheap] >= x).mean() for x in grid]),
        "expensive": np.array([(d[expensive] <= x).mean() for x in grid]),
        "too_expensive": np.array([(d[too_expensive] <= x).mean() for x in grid]),
    }
    def cross(a: str, b: str) -> float:
        i = int(np.argmin(np.abs(curves[a] - curves[b])))
        return float(grid[i])
    # Common PSM intersections.
    pmc = cross("too_cheap", "expensive")
    pme = cross("cheap", "too_expensive")
    ipp = cross("too_cheap", "too_expensive")
    opp = cross("cheap", "expensive")
    return {
        "n": int(len(d)), "point_of_marginal_cheapness": pmc,
        "point_of_marginal_expensiveness": pme,
        "indifference_price_point": ipp, "optimal_price_point": opp,
        "acceptable_range": [min(pmc, pme), max(pmc, pme)],
        "curve": [{"price": float(x), **{k: float(v[i]) for k, v in curves.items()}}
                  for i, x in enumerate(grid)],
        "note": "PSM measures stated price perceptions; it is not observed transaction demand.",
    }


def gabor_granger_questions(product: str, prices: Iterable[float], prefix: str = "GG") -> list[dict[str, Any]]:
    """Create standard yes/no purchase-intent questions for a price ladder."""
    out = []
    for i, price in enumerate(prices, 1):
        out.append({
            "id": f"{prefix}{i}",
            "text": f"Koupil(a) byste {product} za {price:g} Kč?",
            "typ": "vyber", "kategorie": ["Ano", "Ne"], "povolit_nevim": True,
            "hypoteticka": True, "topics": ["cena", "nakup"],
            "response_process": {"agreement_scores": {"Ano": 1, "Ne": -1, "Nevím / neodpovím": 0}},
            "metadata": {"price": float(price), "pricing_method": "gabor_granger"},
        })
    return out


def van_westendorp_questions(product: str, prefix: str = "VW") -> list[dict[str, Any]]:
    """Question specification for a PSM workflow. Numeric entry requires open question parsing downstream."""
    prompts = [
        ("too_cheap", f"Při jaké ceně by vám {product} připadal(a) tak levný(á), že byste pochyboval(a) o kvalitě?"),
        ("cheap", f"Při jaké ceně by vám {product} připadal(a) jako výhodná koupě?"),
        ("expensive", f"Při jaké ceně by vám {product} začal(a) připadat drahý(á), ale ještě přijatelný(á)?"),
        ("too_expensive", f"Při jaké ceně by byl(a) {product} tak drahý(á), že byste ho/ji nekoupil(a)?"),
    ]
    return [{"id": f"{prefix}_{k}", "text": t, "typ": "otevrena", "max_slov": 8,
             "topics": ["cena", "nakup"], "metadata": {"pricing_role": k, "pricing_method": "van_westendorp"}} for k, t in prompts]


def budget_consistency(detail: pd.DataFrame, spend_columns: Iterable[str], *,
                       income_col: str = "prijem", horizon_months: float = 1.0,
                       max_income_share: float = 1.0) -> dict[str, Any]:
    """QC for stated spending/WTP against available income where income is known.

    This is a plausibility flag, not a forced correction: real respondents can also
    give inconsistent hypothetical answers. Rows with unknown income are excluded.
    """
    cols = [c for c in spend_columns if c in detail.columns]
    if not cols or income_col not in detail.columns:
        return {"n_evaluable": 0, "share_over_budget": None, "flagged_case_ids": []}
    inc = pd.to_numeric(detail[income_col], errors="coerce") * float(horizon_months)
    spend = detail[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    ok = inc.notna() & (inc > 0)
    over = ok & (spend > inc * float(max_income_share))
    ids = detail.loc[over, "synthetic_case_id"].astype(str).tolist() if "synthetic_case_id" in detail else detail.index[over].astype(str).tolist()
    return {"n_evaluable": int(ok.sum()), "share_over_budget": round(float(over[ok].mean()), 4) if ok.any() else None,
            "flagged_case_ids": ids[:500], "spend_columns": cols,
            "note": "Plausibility QC only; does not silently rewrite respondent answers."}
