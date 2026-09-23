"""NPC Panel — data-driven audience/segment engine.

The engine never invents new synthetic people. It learns or receives a membership
propensity over the existing population and changes sampling probability only.

Confidence classes:
A = membership/labels measured in linked human/microdata evidence.
B = membership shape learned synthetically, prevalence anchored to external reality.
C = exploratory synthetic segment without an external prevalence anchor.

This module intentionally separates *who belongs* (shape) from *how common the
segment is* (level). An external prevalence target shifts only the intercept of the
propensity model; it does not rewrite respondent attributes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from dimension_catalog import DIMENZE

CORE_CATEGORICAL = ["pohlavi", "vek_skupina", "vzdelani", "kraj", "trida_spolecenska"]
CORE_NUMERIC = ["vek", "prijem"]


@dataclass
class SegmentSpec:
    name: str
    membership_source: str = "synthetic_screener"  # human | microdata | synthetic_screener | prior
    prevalence_target: float | None = None
    prevalence_source: str | None = None
    positive_answers: list[Any] = field(default_factory=list)
    min_ess: float = 150.0
    min_positive_train: int = 20
    include_sensitive_features: bool = False
    include_own_estimates: bool = False
    exclude_features: list[str] = field(default_factory=list)


@dataclass
class SegmentModel:
    name: str
    confidence_class: str
    membership_source: str
    prevalence_raw: float
    prevalence_calibrated: float
    prevalence_target: float | None
    prevalence_source: str | None
    ess_population: float
    n_train: int
    n_positive: int
    feature_columns: list[str]
    top_drivers: list[dict[str, Any]]
    cv_auc: float | None = None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _weighted_mean(x: np.ndarray, w: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(w) & (w >= 0)
    if not ok.any() or w[ok].sum() <= 0:
        return float("nan")
    return float(np.dot(x[ok], w[ok]) / w[ok].sum())


def effective_sample_size(weights: Iterable[float]) -> float:
    w = np.asarray(list(weights), dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if not len(w):
        return 0.0
    return float((w.sum() ** 2) / np.dot(w, w))


def confidence_class(membership_source: str, prevalence_target: float | None) -> str:
    s = str(membership_source).lower()
    if s in {"human", "human_screener", "microdata", "measured"}:
        return "A"
    if prevalence_target is not None:
        return "B"
    return "C"


def safe_feature_columns(df: pd.DataFrame, *, include_sensitive: bool = False,
                         include_own_estimates: bool = False,
                         exclude: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """Return (numeric, categorical) features safe for propensity learning.

    OWN_ESTIMATE and sensitive dimensions are excluded by default. This prevents a
    newly created commercial audience from being defined by unmeasured priors or by
    health/political latent variables unless a methodologist explicitly opts in.
    """
    ex = set(exclude)
    num = [c for c in CORE_NUMERIC if c in df.columns and c not in ex]
    cat = [c for c in CORE_CATEGORICAL if c in df.columns and c not in ex]
    for dim, meta in DIMENZE.items():
        col = f"D_{dim}"
        if col not in df.columns or col in ex:
            continue
        prov = meta.get("prov", {})
        if prov.get("zdroj_role") == "OWN_ESTIMATE" and not include_own_estimates:
            continue
        if prov.get("citlive") and not include_sensitive:
            continue
        num.append(col)
    # deterministic order, no accidental duplicates
    return list(dict.fromkeys(num)), list(dict.fromkeys(cat))


def _make_pipeline(df: pd.DataFrame, numeric: list[str], categorical: list[str]):
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as e:  # pragma: no cover - packaging guard
        raise RuntimeError("Segment Engine vyzaduje scikit-learn>=1.4") from e

    num_pipe = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    cat_pipe = Pipeline([
        ("imp", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
    ])
    prep = ColumnTransformer([
        ("num", num_pipe, numeric),
        ("cat", cat_pipe, categorical),
    ], remainder="drop")
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
    return Pipeline([("prep", prep), ("clf", clf)])


def _feature_importance(pipe, numeric: list[str], categorical: list[str], limit: int = 20) -> list[dict[str, Any]]:
    try:
        names = pipe.named_steps["prep"].get_feature_names_out()
        coef = pipe.named_steps["clf"].coef_[0]
    except Exception:
        return []
    rows = []
    for n, c in zip(names, coef):
        clean = str(n).replace("num__", "").replace("cat__", "")
        rows.append({"feature": clean, "coef": round(float(c), 4),
                     "direction": "higher" if c > 0 else "lower"})
    return sorted(rows, key=lambda r: abs(r["coef"]), reverse=True)[:limit]


def _cv_auc(pipe, X: pd.DataFrame, y: np.ndarray, seed: int = 0) -> float | None:
    if min(int(y.sum()), int((1-y).sum())) < 10:
        return None
    try:
        from sklearn.model_selection import StratifiedKFold, cross_val_score
        folds = min(5, int(y.sum()), int((1-y).sum()))
        cv = StratifiedKFold(n_splits=max(2, folds), shuffle=True, random_state=seed)
        s = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
        return round(float(np.mean(s)), 4)
    except Exception:
        return None


def calibrate_prevalence(prob: np.ndarray, base_weights: np.ndarray,
                         target: float | None) -> np.ndarray:
    """Intercept-only logit shift so weighted mean propensity equals target."""
    p = np.clip(np.asarray(prob, dtype=float), 1e-6, 1 - 1e-6)
    w = np.asarray(base_weights, dtype=float)
    w = np.where(np.isfinite(w) & (w > 0), w, 0.0)
    if target is None:
        return p
    target = float(target)
    if not 0 < target < 1:
        raise ValueError("prevalence_target musi byt mezi 0 a 1")
    logits = np.log(p / (1 - p))
    lo, hi = -30.0, 30.0
    for _ in range(100):
        mid = (lo + hi) / 2
        q = 1 / (1 + np.exp(-(logits + mid)))
        m = _weighted_mean(q, w)
        if m < target:
            lo = mid
        else:
            hi = mid
    shift = (lo + hi) / 2
    return 1 / (1 + np.exp(-(logits + shift)))


def fit_propensity_segment(panel_df: pd.DataFrame, train_index: Iterable[int], labels: Iterable[Any],
                           spec: SegmentSpec, *, seed: int = 0) -> tuple[pd.Series, SegmentModel, Any]:
    """Fit P(segment|profile) from observed screener labels and score whole panel."""
    idx = np.asarray(list(train_index), dtype=int)
    y = np.asarray(list(labels)).astype(int)
    if len(idx) != len(y) or not len(y):
        raise ValueError("train_index a labels musi mit stejnou nenulovou delku")
    if not set(np.unique(y)).issubset({0, 1}):
        raise ValueError("labels musi byt binarni 0/1")
    if int(y.sum()) < spec.min_positive_train:
        raise ValueError(f"Segment ma jen {int(y.sum())} pozitivnich screeneru; minimum je {spec.min_positive_train}.")
    if int((1-y).sum()) < spec.min_positive_train:
        raise ValueError("Screener nema dost negativnich prikladu pro stabilni propensity model.")

    numeric, categorical = safe_feature_columns(
        panel_df, include_sensitive=spec.include_sensitive_features,
        include_own_estimates=spec.include_own_estimates,
        exclude=spec.exclude_features)
    feats = numeric + categorical
    if not feats:
        raise ValueError("Pro segment nejsou dostupne zadne povolene feature sloupce")
    X = panel_df.loc[idx, feats].copy()
    pipe = _make_pipeline(panel_df, numeric, categorical)
    auc = _cv_auc(pipe, X, y, seed=seed)
    pipe.fit(X, y)
    raw = pipe.predict_proba(panel_df[feats])[:, 1]
    bw = pd.to_numeric(panel_df.get("_analysis_weight",df.get("vaha_strukturalni_2025",df.get("vaha_kalibrovana", 1.0))), errors="coerce").fillna(0).to_numpy(float)
    raw_prev = _weighted_mean(raw, bw)
    cal = calibrate_prevalence(raw, bw, spec.prevalence_target)
    cal_prev = _weighted_mean(cal, bw)
    target_w = bw * cal
    ess = effective_sample_size(target_w)
    warning = None
    if ess < spec.min_ess:
        warning = (f"ESS segmentu {ess:.1f} je pod minimem {spec.min_ess:.0f}; "
                   "segment se nema reportovat jako standardni survey audience.")
    model = SegmentModel(
        name=spec.name,
        confidence_class=confidence_class(spec.membership_source, spec.prevalence_target),
        membership_source=spec.membership_source,
        prevalence_raw=round(raw_prev, 6),
        prevalence_calibrated=round(cal_prev, 6),
        prevalence_target=spec.prevalence_target,
        prevalence_source=spec.prevalence_source,
        ess_population=round(ess, 2),
        n_train=len(y), n_positive=int(y.sum()), feature_columns=feats,
        top_drivers=_feature_importance(pipe, numeric, categorical), cv_auc=auc,
        warning=warning,
    )
    return pd.Series(cal, index=panel_df.index, name=f"segment_{spec.name}_propensity"), model, pipe


def screener_labels(detail: pd.DataFrame, question_id: str, positive_answers: Iterable[Any]) -> tuple[np.ndarray, np.ndarray]:
    if question_id not in detail.columns or "_zdroj_index" not in detail.columns:
        raise KeyError("Screener detail musi obsahovat question_id a _zdroj_index")
    pos = {str(x) for x in positive_answers}
    sub = detail[detail[question_id].notna()].copy()
    y = sub[question_id].astype(str).isin(pos).astype(int).to_numpy()
    return sub["_zdroj_index"].astype(int).to_numpy(), y


def profile_segment(panel_df: pd.DataFrame, propensity: pd.Series, *, top_n: int = 20) -> list[dict[str, Any]]:
    """Explain how the propensity-weighted segment differs from the whole population."""
    p = pd.to_numeric(propensity.reindex(panel_df.index), errors="coerce").fillna(0).clip(0, 1).to_numpy(float)
    bw = pd.to_numeric(panel_df.get("_analysis_weight",df.get("vaha_strukturalni_2025",df.get("vaha_kalibrovana", 1.0))), errors="coerce").fillna(0).to_numpy(float)
    sw = bw * p
    out: list[dict[str, Any]] = []
    numeric, categorical = safe_feature_columns(panel_df, include_sensitive=False, include_own_estimates=False)
    for c in numeric:
        x = pd.to_numeric(panel_df[c], errors="coerce").to_numpy(float)
        pop = _weighted_mean(x, bw); seg = _weighted_mean(x, sw)
        ok = np.isfinite(x) & np.isfinite(bw) & (bw > 0)
        if not ok.any():
            continue
        mu = pop
        sd = math.sqrt(max(_weighted_mean((x - mu) ** 2, bw), 1e-12))
        effect = (seg - pop) / sd if np.isfinite(seg) and np.isfinite(pop) else 0.0
        out.append({"feature": c, "kind": "numeric", "population": round(pop, 4),
                    "segment": round(seg, 4), "effect": round(float(effect), 4)})
    for c in categorical:
        vals = panel_df[c].astype(str).fillna("<NA>")
        for value in vals.value_counts().head(12).index:
            x = (vals == value).to_numpy(float)
            pop = _weighted_mean(x, bw); seg = _weighted_mean(x, sw)
            if pop <= 0:
                continue
            lift = seg / pop
            out.append({"feature": c, "value": value, "kind": "categorical",
                        "population": round(pop, 4), "segment": round(seg, 4),
                        "effect": round(float(math.log(max(lift, 1e-9))), 4),
                        "lift": round(float(lift), 3)})
    return sorted(out, key=lambda r: abs(r.get("effect", 0)), reverse=True)[:top_n]


def discover_audience(detail: pd.DataFrame, question_id: str, positive_answers: Iterable[Any],
                      *, min_positive: int = 20, seed: int = 0) -> dict[str, Any]:
    """Reverse segmentation: learn who over-indexes on an observed survey outcome.

    This is descriptive model discovery, not causal inference. The output is explicitly
    labelled synthetic when the source detail comes from NPC responses.
    """
    if question_id not in detail.columns:
        raise KeyError(question_id)
    pos = {str(x) for x in positive_answers}
    valid = detail[detail[question_id].notna()].copy()
    y = valid[question_id].astype(str).isin(pos).astype(int).to_numpy()
    if int(y.sum()) < min_positive or int((1-y).sum()) < min_positive:
        raise ValueError("Pro discovery neni dost pozitivnich/negativnich pripadu")
    # Here the detail already is a sample. Use safe features present in it.
    spec = SegmentSpec(name=f"discovery_{question_id}", membership_source="synthetic_screener",
                       min_positive_train=min_positive)
    # fit_propensity_segment expects panel-style index mapping; use a reset local population.
    local = valid.reset_index(drop=True)
    prop, model, _ = fit_propensity_segment(local, range(len(local)), y, spec, seed=seed)
    model_dict = model.to_dict()
    model_dict["epistemic_status"] = "synthetic_outcome_discovery"
    model_dict["target_question"] = question_id
    model_dict["positive_answers"] = list(positive_answers)
    model_dict["profile"] = profile_segment(local, prop)
    return model_dict


def save_segment_artifacts(directory: str | Path, propensity: pd.Series, model: SegmentModel,
                           profile: list[dict[str, Any]] | None = None) -> Path:
    d = Path(directory); d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"panel_index": propensity.index, "propensity": propensity.values}).to_csv(
        d / "segment_propensity.csv", index=False)
    payload = model.to_dict(); payload["profile"] = profile or []
    (d / "segment_model.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def discover_audience_on_panel(panel_df: pd.DataFrame, detail: pd.DataFrame, question_id: str,
                               positive_answers: Iterable[Any], *, min_positive: int = 20,
                               seed: int = 0, prevalence_target: float | None = None,
                               prevalence_source: str | None = None) -> tuple[pd.Series, dict[str, Any]]:
    """Reverse discovery trained on survey outcomes, then scored over the full panel.

    Because labels come from NPC answers this is class C without an external prevalence
    anchor, or class B when a real external prevalence is supplied. It never becomes A
    merely because the propensity model is accurate on its own synthetic labels.
    """
    if question_id not in detail.columns or "_zdroj_index" not in detail.columns:
        raise KeyError("detail needs target question and _zdroj_index")
    pos = {str(x) for x in positive_answers}
    sub = detail[detail[question_id].notna()].copy()
    y = sub[question_id].astype(str).isin(pos).astype(int).to_numpy()
    if int(y.sum()) < min_positive or int((1-y).sum()) < min_positive:
        raise ValueError("Pro reverse discovery neni dost pozitivnich/negativnich pripadu")
    idx = sub["_zdroj_index"].astype(int).to_numpy()
    spec = SegmentSpec(
        name=f"discovery_{question_id}", membership_source="synthetic_screener",
        prevalence_target=prevalence_target, prevalence_source=prevalence_source,
        min_positive_train=min_positive,
    )
    prop, model, _ = fit_propensity_segment(panel_df, idx, y, spec, seed=seed)
    meta = model.to_dict()
    meta.update({
        "mode": "discovery",
        "epistemic_status": "synthetic_outcome_discovery",
        "target_question": question_id,
        "positive_answers": list(positive_answers),
        "profile": profile_segment(panel_df, prop),
    })
    return prop, meta
