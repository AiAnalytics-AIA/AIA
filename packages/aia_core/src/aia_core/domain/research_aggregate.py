"""Aggregation: a fieldwork dataset -> weighted, donor-aware, interval-first results.

ADR 0016 D2, PR C chunk 5. Ported from the vendored unit's own code:
``legacy/npc-panel-18.6.6/app/uncertainty.py`` (weights, Kish n, donor support,
the cluster bootstrap) and the reportable core of ``dotaznik.py``
``agreguj_otazku`` for ``vyber`` / ``multi`` / ``skala`` / ``otevrena``, plus
``fidelity.py`` ``evidence_rating``. Every number is computed the way the unit
computes it, with its rounding.

The one deliberate difference (OI-62, decided on evidence): the bootstrap draws
come from AIA's generator -- ``random.Random(seed).random()``, cluster index
``floor(u*m)`` -- not NumPy's PCG64 stream. Estimates, Kish n, donor support and
suppression are exact against the unit; each interval bound lies within the
unit's own seed-to-seed spread. Same inputs, same seed, same bounds, on any host.

What the unit does and this does not, because the fieldwork dataset has no input
for it: donor *layers* other than ``core`` (the dataset carries the core donor
only, so ``choose_donor_layer`` would return ``core`` in the unit too), segment
and variant tables (``SEGMENTY`` columns and ``_variant_*`` are absent), the
AI-probability summaries (``_probs_*``, ``_entropy_*``), and coded open answers.

The values the unit wrote inline -- the bootstrap's replicates, seeds and percentile
quantiles, and the top-2-box width -- are declared (plan ``methodology-tab`` G2a) in
:class:`AggregationSpec`, whose preset :data:`AIA_AGGREGATE_V1` is the unit's literals, bit
for bit. Every aggregate is computed under it; a run does not yet pin it (G3).

Pure: no I/O, no clock.
"""

from __future__ import annotations

import math
import operator
import random
import re
from collections.abc import Sequence
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .evidence.support import (
    UNIT_DONOR_THRESHOLDS,
    SupportEvidence,
    SupportSpec,
    SupportThresholds,
    support_status,
)
from .fieldwork import FieldworkDataset
from .research_design import ResearchSpecification, SpecQuestion
from .sociomap.slots import NO_SLOTS, Slots

__all__ = [
    "AGGREGATE_SLOTS",
    "AGGREGATE_VERSION",
    "AIA_AGGREGATE_V1",
    "BOOTSTRAP_GENERATOR",
    "KISH",
    "MEAN",
    "SHARE",
    "TOP_BOX",
    "VARIANCE",
    "AggregationSpec",
    "BootstrapSpec",
    "aggregate_dataset",
    "aggregate_question",
    "bootstrap_weighted_distribution",
    "bootstrap_weighted_mean",
    "classify_question",
    "clean_weights",
    "donor_support",
    "evidence_rating",
    "kish_effective_n",
    "uncertainty_note",
    "weighted_distribution",
    "weighted_mean",
    "weighted_quantile",
    "weighted_variance",
]

AGGREGATE_VERSION: Final = "aia-research-aggregate-1"
#: OI-62: the named generator, recorded on every artifact that holds an interval.
BOOTSTRAP_GENERATOR: Final = "python-random-mt19937:floor(u*m)"

# The estimators a methodology version may replace (ADR 0023 decision 4, plan G2b), by the id
# ``domain.methodology.aggregation_formulas`` declares them under. A replaced slot is called
# with its variables by name, vectors as tuples; with none replaced the code computes, and its
# sums are ``math.fsum``, so each built-in expression gives the code's exact bits.
MEAN: Final = "agg.mean"
SHARE: Final = "agg.share"
TOP_BOX: Final = "agg.top_box"
KISH: Final = "agg.kish"
VARIANCE: Final = "agg.variance"
#: Every slot the aggregate reads from a version.
AGGREGATE_SLOTS: Final = frozenset({MEAN, SHARE, TOP_BOX, KISH, VARIANCE})


class _Declared(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _a_number_not_a_boolean(cls, v: object) -> object:
        if isinstance(v, bool):
            raise ValueError("expected a number, not a boolean")
        return v


class BootstrapSpec(_Declared):
    """The donor-cluster bootstrap behind every interval (``uncertainty.py``).

    ``reps`` resamples a share distribution, a mean and the top-2-box; ``reps_multi`` each
    option of a multiple-choice question, whose seed is ``seed`` plus the option's index;
    ``seed_top_box`` the top-2-box. The interval is the fixed-weight percentile interval
    between ``quantiles`` of the resampled estimates (finding D5: the method was undeclared).
    """

    reps: int
    reps_multi: int
    seed: int
    seed_top_box: int
    quantiles: tuple[float, float]

    @model_validator(mode="after")
    def _usable(self) -> BootstrapSpec:
        if self.reps < 1 or self.reps_multi < 1:
            raise ValueError("a bootstrap needs at least one replicate")
        if self.seed < 0 or self.seed_top_box < 0:
            raise ValueError("a seed is a non-negative integer")
        low, high = self.quantiles
        if not (math.isfinite(low) and math.isfinite(high) and 0.0 < low < high < 1.0):
            raise ValueError("quantiles must satisfy 0 < low < high < 1")
        return self


class AggregationSpec(_Declared):
    """How a question is aggregated (plan ``methodology-tab`` G2a). ``top_box`` is how many of
    a scale's top points count as its top box: an answer ``x`` counts when
    ``x >= max - (top_box - 1)``."""

    methodology_version: str
    bootstrap: BootstrapSpec
    top_box: int

    @field_validator("top_box")
    @classmethod
    def _at_least_one_point(cls, v: int) -> int:
        if v < 1:
            raise ValueError("the top box holds at least one scale point")
        return v


#: 18.6.6's own values (``dotaznik.py`` ``agreguj_otazku``), inline there, declared here.
AIA_AGGREGATE_V1: Final = AggregationSpec(
    methodology_version="aia-aggregate-1",
    bootstrap=BootstrapSpec(
        reps=400,
        reps_multi=350,
        seed=20260816,
        seed_top_box=20260818,
        quantiles=(0.025, 0.975),
    ),
    top_box=2,
)

# dotaznik.py agreguj_otazku: the unit's note, verbatim, around the lines of the rule.
_NOTE_INTERVAL: Final = (
    "95% interval = vážený bootstrap přes reálné donor clustery příslušné vrstvy. "
)
_NOTE_VALIDITY: Final = "Interval není důkaz externí prediktivní validity."


def _support_lines(rule: SupportThresholds) -> str:
    """The lines ``rule`` checks, in the unit's words: ``<a`` is not reported, ``a-b`` is
    INDIKATIVNÍ. A line the rule does not check is not written."""
    parts: list[str] = []
    if rule.min_cell is not None:
        parts.append(f"n_platnych <{rule.min_cell} se nereportuje")
    if rule.n_guard is not None:
        parts.append(f"effective_n <{rule.n_guard:g} se nereportuje")
    if rule.indicative is not None and (rule.n_guard is None or rule.indicative > rule.n_guard):
        parts.append(f"effective_n <{rule.indicative:g} je INDIKATIVNÍ")
    low, high = rule.min_layer_donors, rule.indicative_layer_donors
    if low is not None:
        parts.append(f"n_unique_layer_donors <{low} se nereportuje")
    if high is not None and (low is None or high > low):
        band = f"{low}\u2013{high - 1}" if low is not None else f"n_unique_layer_donors <{high}"
        parts.append(f"{band} je INDIKATIVNÍ")
    return "; ".join(parts) + ". " if parts else "Podpora se nekontroluje. "


def uncertainty_note(rule: SupportThresholds) -> str:
    """The note every cell carries, written from the rule that decides its status (plan
    ``methodology-tab`` G1d): under 18.6.6's donor rule it is the unit's text, verbatim."""
    return _NOTE_INTERVAL + _support_lines(rule) + _NOTE_VALIDITY


#: The unit's note, verbatim: what :func:`uncertainty_note` writes under its donor rule.
UNCERTAINTY_NOTE: Final = uncertainty_note(UNIT_DONOR_THRESHOLDS)


# --------------------------------------------------------------------------- #
# fidelity.py
# --------------------------------------------------------------------------- #

_ABSOLUTE_PATTERNS: Final = (
    r"kolik\s+(?:kč|korun|byste\s+zaplat|zaplatil)",
    r"maxim[aá]ln[ií]\s+cena",
    r"ochot[an]\w*\s+zaplat",
    r"velikost\s+trhu",
    r"kolik\s+lid[ií]",
    r"kolik\s+z[aá]kazn[ií]k",
    r"tržb",
    r"obrat",
    r"v\s*kč",
)
_RELATIVE_PATTERNS: Final = (
    r"kter[áý]\s+variant",
    r"porovnej",
    r"prefer",
    r"pořad",
    r"znění",
    r"koncept\s+[ab]",
)


def classify_question(text: str, qtype: str = "") -> str:
    """``fidelity.py`` ``classify_question``."""
    t = str(text or "").lower()
    if any(re.search(p, t) for p in _ABSOLUTE_PATTERNS):
        return "absolute_value"
    if any(re.search(p, t) for p in _RELATIVE_PATTERNS):
        return "relative_comparison"
    if qtype == "otevrena":
        return "open_ended"
    if qtype == "skala":
        return "rating_scale"
    return "distribution"


def evidence_rating(text: str, qtype: str = "", *, validation_status: str) -> dict[str, str]:
    """``fidelity.py`` ``evidence_rating``. AIA has no validated holdout: say so explicitly."""
    kind = classify_question(text, qtype)
    status = validation_status.upper()
    if kind == "absolute_value":
        return {
            "rating": "RED",
            "mode": "REFUSE",
            "question_type": kind,
            "reason": (
                "Absolutní WTP/velikost trhu není validovaný claim. Přeformulujte na relativní "
                "pořadí, cenové pásmo nebo A/B srovnání."
            ),
        }
    mode = "RECOMMEND" if kind == "relative_comparison" else "JUST_SHOW"
    if status == "VALIDATED":
        return {
            "rating": "GREEN",
            "mode": mode,
            "question_type": kind,
            "reason": (
                "K dispozici je validovaný human holdout pro release; stále zobrazujeme interval "
                "a manifest."
            ),
        }
    return {
        "rating": "AMBER",
        "mode": mode,
        "question_type": kind,
        "reason": (
            "Syntetický výsledek bez dostatečného blind human holdoutu; používejte pro "
            "exploraci/relativní rozhodnutí, ne jako publikovatelný populační fakt."
        ),
    }


# --------------------------------------------------------------------------- #
# uncertainty.py
# --------------------------------------------------------------------------- #


def _positive(w: float) -> bool:
    return math.isfinite(w) and w > 0


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def clean_weights(weights: Sequence[float]) -> list[float]:
    """``clean_weights``: an invalid weight becomes the median of the valid ones."""
    ok = [w for w in weights if _positive(w)]
    if not ok:
        return [1.0] * len(weights)
    med = _median(ok)
    fill = med if math.isfinite(med) and med > 0 else 1.0
    return [w if _positive(w) else fill for w in weights]


def kish_effective_n(weights: Sequence[float], slots: Slots = NO_SLOTS) -> float:
    w = [x for x in weights if _positive(x)]
    if not w:
        return 0.0
    if KISH in slots:
        return float(slots[KISH](w=tuple(w)))
    den = math.fsum(x * x for x in w)
    return float(math.fsum(w) ** 2 / den) if den > 0 else 0.0


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float | None:
    pairs = [
        (x, w) for x, w in zip(values, weights, strict=True) if math.isfinite(x) and _positive(w)
    ]
    if not pairs:
        return None
    return math.fsum(x * w for x, w in pairs) / math.fsum(w for _, w in pairs)


def weighted_distribution(
    values: Sequence[Any], categories: Sequence[str], weights: Sequence[float]
) -> dict[str, float]:
    ok = [
        (str(v), w) for v, w in zip(values, weights, strict=True) if v is not None and _positive(w)
    ]
    if not ok:
        return {str(c): 0.0 for c in categories}
    denom = sum(w for _, w in ok)
    return {
        str(c): round(100.0 * sum(w for v, w in ok if v == str(c)) / denom, 1) for c in categories
    }


def weighted_quantile(
    values: Sequence[float], weights: Sequence[float], q: float = 0.5
) -> float | None:
    pairs = sorted(
        ((x, w) for x, w in zip(values, weights, strict=True) if math.isfinite(x) and _positive(w)),
        key=lambda p: p[0],
    )
    if not pairs:
        return None
    total = sum(w for _, w in pairs)
    cum: list[float] = []
    running = 0.0
    for _, w in pairs:
        running += w
        cum.append(running / total)
    xs = [x for x, _ in pairs]
    return _interp(float(q), cum, xs)


def _interp(q: float, xp: Sequence[float], fp: Sequence[float]) -> float:
    """``np.interp`` for increasing ``xp``: clamp outside, linear inside."""
    if q <= xp[0]:
        return float(fp[0])
    if q >= xp[-1]:
        return float(fp[-1])
    for i in range(1, len(xp)):
        if q <= xp[i]:
            x0, x1 = xp[i - 1], xp[i]
            if x1 == x0:
                return float(fp[i])
            return float(fp[i - 1] + (fp[i] - fp[i - 1]) * (q - x0) / (x1 - x0))
    return float(fp[-1])  # pragma: no cover - the loop returns


def weighted_variance(
    values: Sequence[float], weights: Sequence[float], slots: Slots = NO_SLOTS
) -> float | None:
    pairs = [
        (x, w) for x, w in zip(values, weights, strict=True) if math.isfinite(x) and _positive(w)
    ]
    if len(pairs) < 2:
        return None
    if VARIANCE in slots:
        return float(slots[VARIANCE](x=tuple(x for x, _ in pairs), w=tuple(w for _, w in pairs)))
    total = math.fsum(w for _, w in pairs)
    mu = math.fsum(x * w for x, w in pairs) / total
    return math.fsum(w * (x - mu) ** 2 for x, w in pairs) / total


def _line(value: float | None) -> float | None:
    """A rule's line as the aggregate records it; ``None`` where the rule does not check it."""
    return None if value is None else float(value)


def donor_support(
    donors: Sequence[str],
    weights: Sequence[float],
    *,
    rule: SupportThresholds,
    slots: Slots = NO_SLOTS,
) -> dict[str, Any]:
    """``donor_support`` for the core layer: the only layer a fieldwork dataset carries.

    ``rule`` decides ``support_status``: the run's pinned support specification's
    ``results`` rule (plan ``methodology-tab`` G1c), 18.6.6's donor lines 25 / 50 unless a
    version is in force."""
    n = len(donors)
    kish = kish_effective_n(clean_weights(weights), slots)
    counts: dict[str, int] = {}
    for d in donors:
        counts[d] = counts.get(d, 0) + 1
    nlayer = len(counts)
    ncore = nlayer
    maxshare = max(counts.values()) / n if n and counts else 0.0
    combined = kish * (nlayer / max(n, 1))
    combined = min(combined, kish, float(nlayer), float(ncore))
    status = support_status(
        SupportEvidence(
            n=n,
            effective_n=round(combined, 1),
            requires_donor_support=True,
            n_unique_layer_donors=nlayer,
        ),
        rule,
    ).value
    return {
        "n": n,
        "effective_n_kish": round(kish, 1),
        "n_unique_core_donors": ncore,
        "donor_layer": "core",
        "donor_column": "core_donor_id",
        "n_unique_layer_donors": nlayer,
        "max_donor_share": round(maxshare, 4),
        "effective_n_combined": round(combined, 1),
        "support_status": status,
    }


_times: Final = operator.mul


def _factorize(donors: Sequence[str]) -> tuple[list[int], int]:
    index: dict[str, int] = {}
    codes = [index.setdefault(d, len(index)) for d in donors]
    return codes, len(index)


def _multipliers(m: int, reps: int, seed: int) -> list[list[int]]:
    """Per resample, how often each of ``m`` donor clusters was drawn (OI-62 generator)."""
    rng = random.Random(seed)
    out: list[list[int]] = []
    for _ in range(reps):
        counts = [0] * m
        for _ in range(m):
            counts[min(int(rng.random() * m), m - 1)] += 1
        out.append(counts)
    return out


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """``np.quantile`` default (linear) on already sorted values."""
    h = (len(sorted_values) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (h - lo)


def bootstrap_weighted_mean(
    values: Sequence[float],
    weights: Sequence[float],
    *,
    reps: int,
    seed: int,
    donors: Sequence[str] | None,
    quantiles: tuple[float, float],
    slots: Slots = NO_SLOTS,
) -> dict[str, float] | None:
    """``bootstrap_weighted_mean``: resample donor clusters, not rows; the interval lies
    between ``quantiles`` of the resampled means. A replaced ``agg.mean`` computes the point
    and every replicate."""
    d = [str(i) for i in range(len(values))] if donors is None else [str(x) for x in donors]
    rows = [
        (x, w, dd)
        for x, w, dd in zip(values, weights, d, strict=True)
        if math.isfinite(x) and _positive(w)
    ]
    if len(rows) < 2:
        return None
    xs = [r[0] for r in rows]
    ws = [r[1] for r in rows]
    mean = slots.get(MEAN)
    x_all = tuple(xs)
    if mean is None:
        point = math.fsum(x * w for x, w in zip(xs, ws, strict=True)) / math.fsum(ws)
    else:
        point = float(mean(x=x_all, w=tuple(ws)))
    codes, m = _factorize([r[2] for r in rows])
    if m < 2:
        return {"estimate": point, "low": point, "high": point, "reps": 0}
    vals: list[float] = []
    for mult in _multipliers(m, reps, seed):
        wbs = list(map(_times, map(mult.__getitem__, codes), ws))
        den = math.fsum(wbs)
        if den > 0:
            if mean is None:
                vals.append(math.fsum(map(_times, wbs, xs)) / den)
            else:
                vals.append(float(mean(x=x_all, w=tuple(wbs))))
    vals.sort()
    return {
        "estimate": point,
        "low": _quantile(vals, quantiles[0]),
        "high": _quantile(vals, quantiles[1]),
        "reps": len(vals),
    }


def bootstrap_weighted_distribution(
    values: Sequence[Any],
    categories: Sequence[str],
    weights: Sequence[float],
    *,
    reps: int,
    seed: int,
    donors: Sequence[str] | None,
    quantiles: tuple[float, float],
    slots: Slots = NO_SLOTS,
) -> dict[str, dict[str, float]]:
    """``bootstrap_weighted_distribution``: a share per category, each with its interval
    between ``quantiles`` of the resampled shares. A replaced ``agg.share`` computes the point
    and every replicate."""
    d = [str(i) for i in range(len(values))] if donors is None else [str(x) for x in donors]
    rows = [
        (str(v), w, dd)
        for v, w, dd in zip(values, weights, d, strict=True)
        if v is not None and _positive(w)
    ]
    if not rows:
        return {str(c): {"estimate": 0.0, "low": 0.0, "high": 0.0, "reps": 0} for c in categories}
    ss = [r[0] for r in rows]
    ws = [r[1] for r in rows]
    codes, m = _factorize([r[2] for r in rows])
    denom0 = math.fsum(ws)
    share = slots.get(SHARE)
    hits = {str(c): tuple(1.0 if s == str(c) else 0.0 for s in ss) for c in categories}
    per_rep: list[tuple[float, dict[str, float], tuple[float, ...]]] = []
    if m >= 2:
        rows_of: dict[str, list[int]] = {}
        for i, label in enumerate(ss):
            rows_of.setdefault(label, []).append(i)
        for mult in _multipliers(m, reps, seed):
            wbs = list(map(_times, map(mult.__getitem__, codes), ws))
            nums = (
                {label: math.fsum(map(wbs.__getitem__, rows)) for label, rows in rows_of.items()}
                if share is None
                else {}
            )
            per_rep.append((math.fsum(wbs), nums, tuple(wbs) if share is not None else ()))
    out: dict[str, dict[str, float]] = {}
    for c0 in categories:
        c = str(c0)
        if not denom0:
            point = 0.0
        elif share is None:
            point = 100.0 * math.fsum(w for s, w in zip(ss, ws, strict=True) if s == c) / denom0
        else:
            point = float(share(hit=hits[c], w=tuple(ws)))
        if m < 2:
            lo = hi = point
            rr = 0
        else:
            vals = sorted(
                0.0
                if den <= 0
                else (
                    100.0 * nums.get(c, 0.0) / den
                    if share is None
                    else float(share(hit=hits[c], w=wbs))
                )
                for den, nums, wbs in per_rep
            )
            lo, hi = _quantile(vals, quantiles[0]), _quantile(vals, quantiles[1])
            rr = reps
        out[c] = {
            "estimate": round(point, 1),
            "low": round(lo, 1),
            "high": round(hi, 1),
            "reps": rr,
        }
    return out


# --------------------------------------------------------------------------- #
# dotaznik.py agreguj_otazku -- the reportable core
# --------------------------------------------------------------------------- #


def _numeric(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return math.nan
    return float(value)


def aggregate_question(
    q: SpecQuestion,
    answers: Sequence[Any],
    weights: Sequence[float],
    donors: Sequence[str],
    *,
    validation_status: str,
    support_rule: SupportThresholds,
    method: AggregationSpec,
    slots: Slots = NO_SLOTS,
) -> dict[str, Any]:
    """One question's weighted, interval-first aggregate, as the unit reports it, its status
    decided by ``support_rule`` and its intervals and top box by ``method``. ``slots`` are the
    estimators a methodology version replaced (none: the code computes every one)."""
    boot = method.bootstrap
    rows = [(a, w, d) for a, w, d in zip(answers, weights, donors, strict=True) if a is not None]
    ok_answers = [r[0] for r in rows]
    w = clean_weights([r[1] for r in rows])
    ok_donors = [r[2] for r in rows]
    support = donor_support(ok_donors, [r[1] for r in rows], rule=support_rule, slots=slots)
    out: dict[str, Any] = {
        "typ": q.typ,
        "n_eligible": len(answers),
        "n_filtered": 0,
        "n_platnych": len(rows),
        "n_chybi": len(answers) - len(rows),
        "effective_n": support["effective_n_combined"],
        "effective_n_kish": support["effective_n_kish"],
        "n_unique_core_donors": support["n_unique_core_donors"],
        "donor_layer": support["donor_layer"],
        "n_unique_layer_donors": support["n_unique_layer_donors"],
        "max_donor_share": support["max_donor_share"],
        "support_status": support["support_status"],
        "n_guard_threshold": _line(support_rule.min_layer_donors),
        "indicative_threshold": _line(support_rule.indicative_layer_donors),
        "uncertainty_note": uncertainty_note(support_rule),
        "evidence": evidence_rating(q.text, q.typ, validation_status=validation_status),
    }
    if q.typ == "vyber":
        dist = (
            bootstrap_weighted_distribution(
                ok_answers,
                q.options,
                w,
                reps=boot.reps,
                seed=boot.seed,
                donors=ok_donors,
                quantiles=boot.quantiles,
                slots=slots,
            )
            if rows
            else {}
        )
        out["celkem_pct"] = {k: float(v["estimate"]) for k, v in dist.items()}
        out["intervaly_95"] = {k: {"low": v["low"], "high": v["high"]} for k, v in dist.items()}
    elif q.typ == "multi":
        denom = math.fsum(w) if w else 0.0
        pct: dict[str, float] = {}
        intervals: dict[str, dict[str, float]] = {}
        for ii, choice in enumerate(q.options):
            hit = [1.0 if choice in (a or []) else 0.0 for a in ok_answers]
            if denom <= 0:
                point = 0.0
            elif SHARE in slots:
                point = float(slots[SHARE](hit=tuple(hit), w=tuple(w)))
            else:
                point = 100.0 * math.fsum(h * x for h, x in zip(hit, w, strict=True)) / denom
            pct[choice] = round(point, 1)
            bci = (
                bootstrap_weighted_mean(
                    hit,
                    w,
                    reps=boot.reps_multi,
                    seed=boot.seed + ii,
                    donors=ok_donors,
                    quantiles=boot.quantiles,
                    slots=slots,
                )
                if rows
                else None
            )
            intervals[choice] = (
                {"low": round(100.0 * bci["low"], 1), "high": round(100.0 * bci["high"], 1)}
                if bci
                else {"low": 0.0, "high": 0.0}
            )
        out["celkem_pct"] = pct
        out["intervaly_95"] = intervals
        out["pozn"] = "více odpovědí, součet > 100 %"
    elif q.typ == "skala":
        v = [_numeric(a) for a in ok_answers]
        ci = (
            bootstrap_weighted_mean(
                v,
                w,
                reps=boot.reps,
                seed=boot.seed,
                donors=ok_donors,
                quantiles=boot.quantiles,
                slots=slots,
            )
            if v
            else None
        )
        var = weighted_variance(v, w, slots)
        top = q.scale[1] if q.scale else 0
        in_box = slots.get(TOP_BOX)
        top_hit = (
            [1.0 if x >= top - (method.top_box - 1) else 0.0 for x in v]
            if in_box is None
            else [float(in_box(x=x, top=float(top), b=float(method.top_box))) for x in v]
        )
        top_ci = (
            bootstrap_weighted_mean(
                top_hit,
                w,
                reps=boot.reps,
                seed=boot.seed_top_box,
                donors=ok_donors,
                quantiles=boot.quantiles,
                slots=slots,
            )
            if v
            else None
        )
        counts: dict[float, int] = {}
        for x in v:
            counts[x] = counts.get(x, 0) + 1
        out.update(
            {
                "prumer": round(float(ci["estimate"]), 2) if ci else None,
                "prumer_interval_95": (
                    {"low": round(float(ci["low"]), 2), "high": round(float(ci["high"]), 2)}
                    if ci
                    else None
                ),
                "median": weighted_quantile(v, w, 0.5) if v else None,
                "sd": round(float(var**0.5), 2) if var is not None else None,
                "rozlozeni": {str(k): counts[k] for k in sorted(counts)},
                "top2box_pct": round(100.0 * float(top_ci["estimate"]), 1) if top_ci else None,
                "top2box_interval_95": (
                    {
                        "low": round(100.0 * float(top_ci["low"]), 1),
                        "high": round(100.0 * float(top_ci["high"]), 1),
                    }
                    if top_ci
                    else None
                ),
            }
        )
    else:
        out["verbatimy"] = [str(a) for a in ok_answers][:200]
        out["pozn"] = f"{len(rows)} syntetických ilustračních odpovědí"
    return out


def aggregate_dataset(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    support: SupportSpec,
    validation_status: str = "UNVALIDATED",
    slots: Slots = NO_SLOTS,
) -> dict[str, Any]:
    """Every question and every battery object of ``spec``, aggregated over ``dataset``.

    ``support`` is the run's pinned support specification; its ``results`` rule decides
    every cell's ``support_status`` (plan ``methodology-tab`` G1c). Every question is
    aggregated under :data:`AIA_AGGREGATE_V1`, the unit's own values (G2a). ``slots`` are the
    estimators a methodology version replaced (G2b); a run does not pin any yet (G3).

    A battery object is aggregated as the scale question the unit compiles it to
    (``research_project.py`` ``_prefixed_battery_questions``).
    """
    weights = [r.weight for r in dataset.respondents]
    donors = [r.donor_id for r in dataset.respondents]

    def column(qid: str) -> list[Any]:
        return [r.answers.get(qid) for r in dataset.respondents]

    questions = {
        q.id: aggregate_question(
            q,
            column(q.id),
            weights,
            donors,
            validation_status=validation_status,
            support_rule=support.results,
            method=AIA_AGGREGATE_V1,
            slots=slots,
        )
        for q in spec.questions
    }
    batteries: dict[str, dict[str, Any]] = {}
    for b in spec.batteries:
        objects: dict[str, Any] = {}
        for o in b.objects:
            as_question = SpecQuestion(
                id=b.question_id(o),
                section_id=b.id,
                text=b.question_template.replace("{object}", o.label),
                typ="skala",
                scale=b.scale,
            )
            objects[o.id] = {
                "label": o.label,
                **aggregate_question(
                    as_question,
                    column(as_question.id),
                    weights,
                    donors,
                    validation_status=validation_status,
                    support_rule=support.results,
                    method=AIA_AGGREGATE_V1,
                    slots=slots,
                ),
            }
        batteries[b.id] = {"title": b.title, "family": b.family, "objects": objects}
    return {
        "aggregate_version": AGGREGATE_VERSION,
        "bootstrap_generator": BOOTSTRAP_GENERATOR,
        "validation_status": validation_status,
        "data_origin": dataset.origin.value if dataset.origin else None,
        "respondents": len(dataset.respondents),
        "questions": questions,
        "batteries": batteries,
    }
