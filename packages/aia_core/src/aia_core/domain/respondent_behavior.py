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

Every coefficient is declared in :class:`ResponseProcessSpec`, whose preset
``aia-response-1`` holds the unit's values, and the functions here read it: the
declaration the Metodika tab shows is what computes (plan ``methodology-tab`` R1a), and
the EXACT captures hold it to the unit.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

__all__ = [
    "AIA_RESPONSE_V1",
    "BEHAVIOR_VERSION",
    "STYLES",
    "BehaviorMeta",
    "ResponseProcessSpec",
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


class _Declared(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def _finite(cls, v: Any) -> Any:
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("a coefficient is a finite number")
        return v


class Line(_Declared):
    """``base + slope * z``: a coefficient that grows with a respondent's style score."""

    base: float
    slope: float


class Satisficing(_Declared):
    """``lambda = min(cap, clamp(base + slope * z, 0, 1) * strength)``."""

    base: float
    slope: float
    cap: float

    @field_validator("cap")
    @classmethod
    def _a_share(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("the satisficing cap is a share between 0 and 1")
        return v


class StyleLink(_Declared):
    """One style's prior on (education, age, male), each a z-score (``styly.VAZBY``)."""

    education: float
    age: float
    male: float


class ResponseProcessSpec(_Declared):
    """How a model's probabilities become an answer, and how styles are assigned (plan
    ``methodology-tab`` R1a). Every number ``adjust_probabilities``, ``assign_styles`` and
    ``ai_respondent.describe_style`` use, declared."""

    methodology_version: str
    #: beta for a declared social-desirability direction: base + slope * the style's z.
    social_desirability: Line
    #: beta per unit of ``souhlasny_sklon`` toward a declared agreement direction.
    acquiescence: float
    #: beta per unit of ``vyhranenost`` toward a scale's ends.
    extremity: float
    #: beta per unit of ``ochota_priznat_nevim`` toward "don't know".
    dont_know: float
    satisficing: Satisficing
    #: The exponent of one reweighting is clamped to +-this.
    reweight_limit: float
    #: ``styly.VAZBY``, in the unit's style order.
    style_links: dict[str, StyleLink]
    #: The noise weight is sqrt(max(1 - var(signal), this)): a style is never all prior.
    style_noise_floor: float
    #: A style is put into words (the persona's profile) from |z| >= this.
    describe_threshold: float

    @field_validator("reweight_limit", "describe_threshold")
    @classmethod
    def _positive(cls, v: float) -> float:
        if not v > 0:
            raise ValueError("must be greater than zero")
        return v

    @field_validator("style_noise_floor")
    @classmethod
    def _noise_share(cls, v: float) -> float:
        if not 0.0 < v <= 1.0:
            raise ValueError("the noise floor is a share above 0 and at most 1")
        return v

    @model_validator(mode="after")
    def _every_style_once(self) -> ResponseProcessSpec:
        if tuple(self.style_links) != STYLES:
            raise ValueError(f"style links name the six styles in order: {', '.join(STYLES)}")
        return self


#: 18.6.6's own values (``behavior.py``, ``styly.py``), inline there, declared here. Informed
#: priors, not measurements (the unit's own docstring says so); most variance is individual.
AIA_RESPONSE_V1: Final = ResponseProcessSpec(
    methodology_version="aia-response-1",
    social_desirability=Line(base=0.18, slope=0.10),
    acquiescence=0.16,
    extremity=0.22,
    dont_know=0.24,
    satisficing=Satisficing(base=0.10, slope=0.06, cap=0.35),
    reweight_limit=8.0,
    style_links={
        "souhlasny_sklon": StyleLink(education=-0.30, age=0.20, male=0.00),
        "vyhranenost": StyleLink(education=-0.10, age=0.15, male=0.05),
        "ochota_priznat_nevim": StyleLink(education=-0.25, age=-0.10, male=-0.15),
        "sdilnost": StyleLink(education=0.30, age=-0.10, male=0.00),
        "satisficing": StyleLink(education=-0.25, age=0.10, male=0.00),
        "social_desirability_sensitivity": StyleLink(education=-0.05, age=0.05, male=-0.05),
    },
    style_noise_floor=0.05,
    describe_threshold=0.7,
)

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


def _soft_reweight(
    p: list[float], score: Sequence[float], beta: float, limit: float
) -> list[float]:
    if abs(beta) < 1e-12:
        return p
    q = [pi * math.exp(min(limit, max(-limit, beta * si))) for pi, si in zip(p, score, strict=True)]
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
    spec: ResponseProcessSpec = AIA_RESPONSE_V1,
) -> tuple[list[float], BehaviorMeta]:
    """``behavior.adjust_probabilities``, line for line, its coefficients ``spec``'s.
    Returns ``(p, meta)``."""
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
        sd = spec.social_desirability
        beta = strength * (sd.base + sd.slope * get("social_desirability_sensitivity"))
        p = _soft_reweight(p, scores, beta, spec.reweight_limit)
        applied.append("social_desirability")

    # 2) Acquiescence, only when the question declares which direction is agreement.
    agreement = _as_scores(cfg.get("agreement_scores"), labels, len(p))
    if agreement is not None:
        beta = strength * spec.acquiescence * get("souhlasny_sklon")
        p = _soft_reweight(p, agreement, beta, spec.reweight_limit)
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
            beta = strength * spec.extremity * get("vyhranenost")
            p = _soft_reweight(p, score, beta, spec.reweight_limit)
            applied.append("extremity")

    # 4) Willingness to admit DK. DK is always the last option by engine contract.
    if question.allow_dont_know and cfg.get("dont_know", True) and len(p) >= 2:
        score = [0.0] * len(p)
        score[-1] = 1.0
        beta = strength * spec.dont_know * get("ochota_priznat_nevim")
        p = _soft_reweight(p, score, beta, spec.reweight_limit)
        applied.append("dont_know")

    # 5) Satisficing: blend toward an explicit heuristic.
    strategy = str(cfg.get("satisficing_strategy", "uniform")).lower()
    rule = spec.satisficing
    sat = max(0.0, min(1.0, rule.base + rule.slope * get("satisficing"))) * strength
    sat = max(0.0, min(rule.cap, sat))
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


def assign_styles(
    rows: Sequence[Mapping[str, Any]], spec: ResponseProcessSpec = AIA_RESPONSE_V1
) -> list[dict[str, float]]:
    """Six style z-scores per row, as ``styly.prirad_styly`` assigns them, its priors and
    noise floor ``spec``'s.

    Each row carries ``respondent_id`` and, when known, ``vek`` (number),
    ``pohlavi`` and ``vzdelani`` (the unit's labels). A column no row has contributes
    nothing; a missing education or age contributes nothing; a missing sex where the column
    exists counts as not male (-1), as the unit's ``astype(str)`` makes it. Only the hash
    noise is the respondent's own: the z-scores, the signal's variance and the final
    standardisation are over ``rows``, so the same respondent in another roster has another
    style.
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
    for style, link in spec.style_links.items():
        a, b, c = link.education, link.age, link.male
        signal = [a * e + b * g + c * m for e, g, m in zip(edu, age, male, strict=True)]
        noise = _stable_noise(ids, style)
        m_sig = _mean(signal)
        var = sum((v - m_sig) ** 2 for v in signal) / n
        noise_weight = math.sqrt(max(1 - var, spec.style_noise_floor))
        x = [s + noise_weight * e for s, e in zip(signal, noise, strict=True)]
        mx, sx = _mean(x), _pstd(x)
        for i, v in enumerate(x):
            out[i][style] = (v - mx) / (sx if sx else 1.0)
    return out
