"""The respondent's response process: how a model's probabilities become an answer.

Ported from 18.6.6 (``legacy/npc-panel-18.6.6/app/behavior.py``, ``styly.py``,
``dotaznik._parse_response``). The division of labour is the reference's and it is
the point: *the model estimates one respondent's latent preference as a probability
vector; this module applies explicit, auditable survey-response mechanisms; an
external seeded draw picks the answer.* The model never chooses the answer.

What is ported, EXACT against captures of the unit's own functions
(``tools/respondent_capture.py``, ``tests/fixtures/response_process/``):

* :func:`adjust_probabilities` -- ``behavior.adjust_probabilities``: clip,
  normalise, then social desirability and acquiescence (only when a question
  *declares* their direction), extremity on ordered scales, willingness to admit
  "don't know", and satisficing blended toward a heuristic. Coefficients are the
  unit's, deliberately modest.
* :func:`assign_styles` -- ``styly.prirad_styly``: six style z-scores per
  respondent from weak demographic priors plus stable hash noise, so the same
  respondent always has the same style. ``scipy.stats.norm.ppf`` becomes
  ``statistics.NormalDist().inv_cdf`` (stdlib, ARCHITECTURE.md §2).

What is not ported: the dispersion temperature (``dispersion_calibration``) --
AIA has no calibration, so the temperature is 1.0, the identity -- and NumPy's
``default_rng`` stream for the draw. The draw is :func:`draw_index` over
``random.Random(seed).random()``, the stdlib's guaranteed sequence (OI-62's rule).
A draw therefore differs from the unit's for the same probabilities and seed; the
*distribution* it draws from is the unit's.

Pure: stdlib only.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Final

__all__ = [
    "BEHAVIOR_VERSION",
    "STYLES",
    "BehaviorMeta",
    "ResponseQuestion",
    "adjust_probabilities",
    "assign_styles",
    "draw_index",
    "normalise",
]

BEHAVIOR_VERSION: Final = "aia-respondent-behavior-1 (18.6.6 behavior.py, styly.py)"

#: The style dimensions, in the unit's order (``styly.STYLY``).
STYLES: Final = (
    "souhlasny_sklon",
    "vyhranenost",
    "ochota_priznat_nevim",
    "sdilnost",
    "satisficing",
    "social_desirability_sensitivity",
)

#: ``styly.VAZBY``: style -> (education, age, male) coefficients. Informed priors, not
#: measurements (the unit's own docstring says so); most variance is individual.
_LINKS: Final[dict[str, tuple[float, float, float]]] = {
    "souhlasny_sklon": (-0.30, 0.20, 0.00),
    "vyhranenost": (-0.10, 0.15, 0.05),
    "ochota_priznat_nevim": (-0.25, -0.10, -0.15),
    "sdilnost": (0.30, -0.10, 0.00),
    "satisficing": (-0.25, 0.10, 0.00),
    "social_desirability_sensitivity": (-0.05, 0.05, -0.05),
}

#: ``styly.VZDELANI_PORADI``.
EDUCATION_ORDER: Final[dict[str, int]] = {
    "základní": 1,
    "střední bez maturity": 2,
    "střední s maturitou": 3,
    "VOŠ/VŠ": 4,
}


@dataclass(frozen=True, slots=True)
class ResponseQuestion:
    """What the response process needs to know about a question.

    ``labels`` are the options in order (for ``vyber``, "don't know" last when
    allowed -- the engine contract both systems share). ``process`` is the question's
    declared ``response_process`` metadata; AIA questions declare none yet, so only
    the defaults apply (extremity on scales, DK willingness, uniform satisficing).
    """

    typ: str
    labels: tuple[str, ...] = ()
    scale: tuple[int, int] | None = None
    allow_dont_know: bool = False
    process: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BehaviorMeta:
    """``behavior.BehaviorMeta``: which mechanisms ran, and how far they moved ``p``."""

    applied: tuple[str, ...]
    l1_shift: float
    base_max_prob: float
    adjusted_max_prob: float


def normalise(values: Sequence[float]) -> list[float]:
    """Clip at zero and divide by the sum. Refuses a non-finite value or no mass.

    Non-finite is refused *before* clipping, as ``dotaznik._parse_response`` does:
    ``max(0.0, nan)`` is ``0.0``, which would quietly turn a broken answer into a
    plausible one.
    """
    floats = [float(v) for v in values]
    if not all(math.isfinite(v) for v in floats):
        raise ValueError("a probability vector must be finite")
    clipped = [max(0.0, v) for v in floats]
    total = sum(clipped)
    if not total > 0 or not math.isfinite(total):
        raise ValueError("a probability vector needs positive, finite mass")
    return [v / total for v in clipped]


def _soft_reweight(p: list[float], score: Sequence[float], beta: float) -> list[float]:
    if abs(beta) < 1e-12:
        return p
    q = [pi * math.exp(min(8.0, max(-8.0, beta * si))) for pi, si in zip(p, score, strict=True)]
    total = sum(q)
    if total <= 0:
        return p
    return [x / total for x in q]


def _as_scores(value: Any, labels: Sequence[str], n: int) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return [float(value.get(label, 0.0)) for label in labels]
    try:
        scores = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    return scores if len(scores) == n else None


def adjust_probabilities(
    probabilities: Sequence[float],
    question: ResponseQuestion,
    style: Mapping[str, float] | None,
) -> tuple[list[float], BehaviorMeta]:
    """``behavior.adjust_probabilities``, line for line. Returns ``(p, meta)``."""
    p = normalise(probabilities)
    base = list(p)
    cfg = dict(question.process or {})
    if cfg.get("enabled", True) is False:
        return p, BehaviorMeta((), 0.0, max(base), max(base))
    s = dict(style or {})

    def get(key: str) -> float:
        return float(s.get(key, 0.0))

    strength = float(cfg.get("strength", 1.0))
    applied: list[str] = []
    labels = list(question.labels)

    # 1) Explicit social desirability. Direction must be declared, never guessed.
    scores = _as_scores(cfg.get("social_desirability_scores"), labels, len(p))
    if scores is not None:
        beta = strength * (0.18 + 0.10 * get("social_desirability_sensitivity"))
        p = _soft_reweight(p, scores, beta)
        applied.append("social_desirability")

    # 2) Acquiescence, only when the question declares which direction is agreement.
    agreement = _as_scores(cfg.get("agreement_scores"), labels, len(p))
    if agreement is not None:
        p = _soft_reweight(p, agreement, strength * 0.16 * get("souhlasny_sklon"))
        applied.append("acquiescence")

    # 3) Extremity / midpoint style on ordered scales.
    if question.typ == "skala" and question.scale is not None and cfg.get("extremity", True):
        nscale = int(question.scale[1] - question.scale[0] + 1)
        if nscale >= 3 and len(p) >= nscale:
            # np.linspace(-1, 1, n): start + i * step, the last point exactly 1.
            step = 2.0 / (nscale - 1)
            x = [-1.0 + i * step for i in range(nscale - 1)] + [1.0]
            score = [abs(v) for v in x]
            if len(p) > nscale:
                score.append(0.0)  # DK is neither middle nor extreme
            p = _soft_reweight(p, score, strength * 0.22 * get("vyhranenost"))
            applied.append("extremity")

    # 4) Willingness to admit DK. DK is always the last option by engine contract.
    if question.allow_dont_know and cfg.get("dont_know", True) and len(p) >= 2:
        score = [0.0] * len(p)
        score[-1] = 1.0
        p = _soft_reweight(p, score, strength * 0.24 * get("ochota_priznat_nevim"))
        applied.append("dont_know")

    # 5) Satisficing: blend toward an explicit heuristic.
    strategy = str(cfg.get("satisficing_strategy", "uniform")).lower()
    sat = max(0.0, min(1.0, 0.10 + 0.06 * get("satisficing"))) * strength
    sat = max(0.0, min(0.35, sat))
    if strategy != "none" and sat > 0:
        h = [1.0 / len(p)] * len(p)
        if strategy == "midpoint" and question.typ == "skala" and question.scale is not None:
            h = [0.0] * len(p)
            h[(int(question.scale[1] - question.scale[0] + 1) - 1) // 2] = 1.0
        elif strategy == "first_option":
            h = [0.0] * len(p)
            h[0] = 1.0
        p = [(1 - sat) * pi + sat * hi for pi, hi in zip(p, h, strict=True)]
        total = sum(p)
        p = [pi / total for pi in p]
        applied.append(f"satisficing:{strategy}")

    return p, BehaviorMeta(
        applied=tuple(applied),
        l1_shift=round(sum(abs(a - b) for a, b in zip(p, base, strict=True)), 6),
        base_max_prob=round(max(base), 6),
        adjusted_max_prob=round(max(p), 6),
    )


def draw_index(probabilities: Sequence[float], seed: int) -> int:
    """One index drawn from ``probabilities`` with ``random.Random(seed)``: inverse CDF."""
    u = random.Random(seed).random()
    running = 0.0
    for i, p in enumerate(probabilities):
        running += p
        if u < running:
            return i
    return len(probabilities) - 1


# --------------------------------------------------------------------------- #
# Styles (styly.prirad_styly)
# --------------------------------------------------------------------------- #


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _pstd(values: Sequence[float]) -> float:
    m = _mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _z(values: Sequence[float | None]) -> list[float]:
    """``styly._z``: z-score over the known values (ddof 0); unknown becomes 0."""
    known = [v for v in values if v is not None]
    if not known:
        return [0.0] * len(values)
    m = _mean(known)
    sd = _pstd(known) or 1.0
    return [0.0 if v is None else (v - m) / sd for v in values]


def _stable_noise(ids: Sequence[str], salt: str) -> list[float]:
    """``styly._stabilni_sum``: a standard normal from sha256(id + salt)."""
    normal = NormalDist()
    out: list[float] = []
    for rid in ids:
        h = hashlib.sha256((rid + salt).encode()).hexdigest()
        u = (int(h[:12], 16) + 0.5) / 16**12
        out.append(normal.inv_cdf(min(max(u, 1e-9), 1 - 1e-9)))
    return out


def assign_styles(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, float]]:
    """Six style z-scores per row, as ``styly.prirad_styly`` assigns them.

    Each row carries ``respondent_id`` and, when known, ``vek`` (number),
    ``pohlavi`` and ``vzdelani`` (the unit's labels). A missing attribute contributes
    nothing, exactly as a missing column does in the unit.
    """
    if not rows:
        return []
    n = len(rows)

    def column(key: str) -> list[Any] | None:
        return [r.get(key) for r in rows] if any(key in r for r in rows) else None

    edu_raw = column("vzdelani")
    age_raw = column("vek")
    sex_raw = column("pohlavi")
    edu = (
        _z([EDUCATION_ORDER.get(str(v)) if v is not None else None for v in edu_raw])
        if edu_raw is not None
        else [0.0] * n
    )
    age = (
        _z([float(v) if v is not None else None for v in age_raw])
        if age_raw is not None
        else [0.0] * n
    )
    male = (
        [(1.0 if str(v).lower().startswith("mu") else 0.0) * 2 - 1 for v in sex_raw]
        if sex_raw is not None
        else [0.0] * n
    )
    ids = [str(r["respondent_id"]) for r in rows]

    out: list[dict[str, float]] = [{} for _ in rows]
    for style, (a, b, c) in _LINKS.items():
        signal = [a * e + b * g + c * m for e, g, m in zip(edu, age, male, strict=True)]
        noise = _stable_noise(ids, style)
        m_sig = _mean(signal)
        var = sum((v - m_sig) ** 2 for v in signal) / n
        noise_weight = math.sqrt(max(1 - var, 0.05))
        x = [s + noise_weight * e for s, e in zip(signal, noise, strict=True)]
        mx, sx = _mean(x), _pstd(x)
        for i, v in enumerate(x):
            out[i][style] = (v - mx) / (sx if sx else 1.0)
    return out
