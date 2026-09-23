"""Behavioral response-process layer for NPC Panel.

The LLM estimates latent preference probabilities. This module then applies explicit,
auditable survey-response mechanisms before external RNG selects an answer. It does
not infer social-desirability direction from stereotypes: directional corrections
must be declared in question metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd


@dataclass
class BehaviorMeta:
    applied: list[str]
    l1_shift: float
    base_max_prob: float
    adjusted_max_prob: float


def _soft_reweight(p: np.ndarray, score: np.ndarray, beta: float) -> np.ndarray:
    if abs(beta) < 1e-12:
        return p
    z = np.clip(beta * score, -8, 8)
    q = p * np.exp(z)
    if q.sum() <= 0:
        return p
    return q / q.sum()


def _as_scores(value: Any, labels: list[str], n: int) -> np.ndarray | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return np.asarray([float(value.get(lbl, 0.0)) for lbl in labels], dtype=float)
    try:
        a = np.asarray(value, dtype=float)
        return a if len(a) == n else None
    except Exception:
        return None


def adjust_probabilities(probabilities: np.ndarray, question: Any, style: pd.Series | dict[str, Any] | None,
                         respondent: pd.Series | dict[str, Any] | None = None) -> tuple[np.ndarray, BehaviorMeta]:
    """Apply response-process effects configured on ``question.response_process``.

    Supported metadata:
    - social_desirability_scores: option->[-1,1] or vector. No auto-inference.
    - agreement_scores: explicit directional scores for acquiescence.
    - extremity: bool (default true for scale questions)
    - dont_know: bool (default true when a DK option exists)
    - satisficing_strategy: uniform | midpoint | first_option | none
    - strength: global multiplier, default 1.0

    The respondent style supplies z-scores; all coefficients are deliberately modest.
    """
    p = np.asarray(probabilities, dtype=float)
    p = np.clip(p, 0, None)
    p = p / p.sum()
    base = p.copy()
    cfg = getattr(question, "response_process", None) or {}
    if cfg.get("enabled", True) is False:
        return p, BehaviorMeta([], 0.0, float(base.max()), float(base.max()))
    s = style if style is not None else {}
    get = (lambda k: float(s.get(k, 0.0))) if hasattr(s, "get") else (lambda k: 0.0)
    strength = float(cfg.get("strength", 1.0))
    applied: list[str] = []

    # 1) Explicit social desirability. Direction must be authored/researched, never guessed.
    labels = list(getattr(question, "volby", []) or [])
    scores = _as_scores(cfg.get("social_desirability_scores"), labels, len(p))
    if scores is not None:
        sensitivity = get("social_desirability_sensitivity")
        beta = strength * (0.18 + 0.10 * sensitivity)
        p = _soft_reweight(p, scores, beta)
        applied.append("social_desirability")

    # 2) Acquiescence only when question metadata declares which direction is agreement.
    agreement = _as_scores(cfg.get("agreement_scores"), labels, len(p))
    if agreement is not None:
        p = _soft_reweight(p, agreement, strength * 0.16 * get("souhlasny_sklon"))
        applied.append("acquiescence")

    # 3) Extremity / midpoint response style on ordered scales.
    if getattr(question, "typ", None) == "skala" and cfg.get("extremity", True):
        nscale = int(question.skala[1] - question.skala[0] + 1)
        if nscale >= 3 and len(p) >= nscale:
            x = np.linspace(-1, 1, nscale)
            score = np.abs(x)
            if len(p) > nscale:
                score = np.r_[score, 0.0]  # DK is neither middle nor extreme
            p = _soft_reweight(p, score, strength * 0.22 * get("vyhranenost"))
            applied.append("extremity")

    # 4) Willingness to admit DK. In choice questions DK is always the last option by engine contract.
    has_dk = bool(getattr(question, "povolit_nevim", False))
    if has_dk and cfg.get("dont_know", True) and len(p) >= 2:
        score = np.zeros(len(p)); score[-1] = 1.0
        p = _soft_reweight(p, score, strength * 0.24 * get("ochota_priznat_nevim"))
        applied.append("dont_know")

    # 5) Satisficing: reduce deliberative sharpness by blending toward an explicit heuristic.
    strategy = str(cfg.get("satisficing_strategy", "uniform")).lower()
    sat = max(0.0, min(1.0, 0.10 + 0.06 * get("satisficing"))) * strength
    sat = max(0.0, min(0.35, sat))
    if strategy != "none" and sat > 0:
        h = np.ones(len(p), dtype=float) / len(p)
        if strategy == "midpoint" and getattr(question, "typ", None) == "skala":
            h[:] = 0
            nscale = int(question.skala[1] - question.skala[0] + 1)
            h[(nscale - 1) // 2] = 1
        elif strategy == "first_option":
            h[:] = 0; h[0] = 1
        p = (1 - sat) * p + sat * h
        p = p / p.sum()
        applied.append(f"satisficing:{strategy}")

    return p, BehaviorMeta(
        applied=applied,
        l1_shift=round(float(np.abs(p - base).sum()), 6),
        base_max_prob=round(float(base.max()), 6),
        adjusted_max_prob=round(float(p.max()), 6),
    )
