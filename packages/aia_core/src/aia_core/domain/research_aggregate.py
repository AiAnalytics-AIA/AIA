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

Pure: no I/O, no clock.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Sequence
from typing import Any, Final

from .fieldwork import FieldworkDataset
from .research_design import ResearchSpecification, SpecQuestion

__all__ = [
    "AGGREGATE_VERSION",
    "BOOTSTRAP_GENERATOR",
    "aggregate_dataset",
    "aggregate_question",
    "bootstrap_weighted_distribution",
    "bootstrap_weighted_mean",
    "classify_question",
    "clean_weights",
    "donor_support",
    "evidence_rating",
    "kish_effective_n",
    "weighted_distribution",
    "weighted_mean",
    "weighted_quantile",
    "weighted_variance",
]

AGGREGATE_VERSION: Final = "aia-research-aggregate-1"
#: OI-62: the named generator, recorded on every artifact that holds an interval.
BOOTSTRAP_GENERATOR: Final = "python-random-mt19937:floor(u*m)"

# dotaznik.py agreguj_otazku: the unit's notes and thresholds, verbatim.
UNCERTAINTY_NOTE: Final = (
    "95% interval = vážený bootstrap přes reálné donor clustery příslušné vrstvy. "
    "n_unique_layer_donors <25 se nereportuje; 25\u201349 je INDIKATIVNÍ. "
    "Interval není důkaz externí prediktivní validity."
)
_SUPPRESS_BELOW: Final = 25
_REPORTABLE_FROM: Final = 50


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


def kish_effective_n(weights: Sequence[float]) -> float:
    w = [x for x in weights if _positive(x)]
    if not w:
        return 0.0
    den = sum(x * x for x in w)
    return float(sum(w) ** 2 / den) if den > 0 else 0.0


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float | None:
    pairs = [
        (x, w) for x, w in zip(values, weights, strict=True) if math.isfinite(x) and _positive(w)
    ]
    if not pairs:
        return None
    return sum(x * w for x, w in pairs) / sum(w for _, w in pairs)


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


def weighted_variance(values: Sequence[float], weights: Sequence[float]) -> float | None:
    pairs = [
        (x, w) for x, w in zip(values, weights, strict=True) if math.isfinite(x) and _positive(w)
    ]
    if len(pairs) < 2:
        return None
    total = sum(w for _, w in pairs)
    mu = sum(x * w for x, w in pairs) / total
    return sum(w * (x - mu) ** 2 for x, w in pairs) / total


def donor_support(donors: Sequence[str], weights: Sequence[float]) -> dict[str, Any]:
    """``donor_support`` for the core layer: the only layer a fieldwork dataset carries."""
    n = len(donors)
    kish = kish_effective_n(clean_weights(weights))
    counts: dict[str, int] = {}
    for d in donors:
        counts[d] = counts.get(d, 0) + 1
    nlayer = len(counts)
    ncore = nlayer
    maxshare = max(counts.values()) / n if n and counts else 0.0
    combined = kish * (nlayer / max(n, 1))
    combined = min(combined, kish, float(nlayer), float(ncore))
    status = (
        "SUPPRESS"
        if nlayer < _SUPPRESS_BELOW
        else "INDICATIVE"
        if nlayer < _REPORTABLE_FROM
        else "REPORTABLE"
    )
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
) -> dict[str, float] | None:
    """``bootstrap_weighted_mean``: resample donor clusters, not rows."""
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
    point = sum(x * w for x, w in zip(xs, ws, strict=True)) / sum(ws)
    codes, m = _factorize([r[2] for r in rows])
    if m < 2:
        return {"estimate": point, "low": point, "high": point, "reps": 0}
    vals: list[float] = []
    for mult in _multipliers(m, reps, seed):
        den = 0.0
        num = 0.0
        for x, w, c in zip(xs, ws, codes, strict=True):
            wb = mult[c] * w
            den += wb
            num += wb * x
        if den > 0:
            vals.append(num / den)
    vals.sort()
    return {
        "estimate": point,
        "low": _quantile(vals, 0.025),
        "high": _quantile(vals, 0.975),
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
) -> dict[str, dict[str, float]]:
    """``bootstrap_weighted_distribution``: a share per category, each with its interval."""
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
    denom0 = sum(ws)
    per_rep: list[tuple[float, dict[str, float]]] = []
    if m >= 2:
        for mult in _multipliers(m, reps, seed):
            den = 0.0
            nums: dict[str, float] = {}
            for label, weight, code in zip(ss, ws, codes, strict=True):
                wb = mult[code] * weight
                den += wb
                nums[label] = nums.get(label, 0.0) + wb
            per_rep.append((den, nums))
    out: dict[str, dict[str, float]] = {}
    for c0 in categories:
        c = str(c0)
        point = (
            100.0 * sum(w for s, w in zip(ss, ws, strict=True) if s == c) / denom0
            if denom0
            else 0.0
        )
        if m < 2:
            lo = hi = point
            rr = 0
        else:
            vals = sorted(
                (100.0 * nums.get(c, 0.0) / den) if den > 0 else 0.0 for den, nums in per_rep
            )
            lo, hi = _quantile(vals, 0.025), _quantile(vals, 0.975)
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
) -> dict[str, Any]:
    """One question's weighted, interval-first aggregate, as the unit reports it."""
    rows = [(a, w, d) for a, w, d in zip(answers, weights, donors, strict=True) if a is not None]
    ok_answers = [r[0] for r in rows]
    w = clean_weights([r[1] for r in rows])
    ok_donors = [r[2] for r in rows]
    support = donor_support(ok_donors, [r[1] for r in rows])
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
        "n_guard_threshold": float(_SUPPRESS_BELOW),
        "indicative_threshold": float(_REPORTABLE_FROM),
        "uncertainty_note": UNCERTAINTY_NOTE,
        "evidence": evidence_rating(q.text, q.typ, validation_status=validation_status),
    }
    if q.typ == "vyber":
        dist = (
            bootstrap_weighted_distribution(
                ok_answers, q.options, w, reps=400, seed=20260816, donors=ok_donors
            )
            if rows
            else {}
        )
        out["celkem_pct"] = {k: float(v["estimate"]) for k, v in dist.items()}
        out["intervaly_95"] = {k: {"low": v["low"], "high": v["high"]} for k, v in dist.items()}
    elif q.typ == "multi":
        denom = sum(w) if w else 0.0
        pct: dict[str, float] = {}
        intervals: dict[str, dict[str, float]] = {}
        for ii, choice in enumerate(q.options):
            hit = [1.0 if choice in (a or []) else 0.0 for a in ok_answers]
            point = (
                100.0 * sum(h * x for h, x in zip(hit, w, strict=True)) / denom
                if denom > 0
                else 0.0
            )
            pct[choice] = round(point, 1)
            bci = (
                bootstrap_weighted_mean(hit, w, reps=350, seed=20260816 + ii, donors=ok_donors)
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
        ci = bootstrap_weighted_mean(v, w, reps=400, seed=20260816, donors=ok_donors) if v else None
        var = weighted_variance(v, w)
        top = q.scale[1] if q.scale else 0
        top_hit = [1.0 if x >= top - 1 else 0.0 for x in v]
        top_ci = (
            bootstrap_weighted_mean(top_hit, w, reps=400, seed=20260818, donors=ok_donors)
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
    validation_status: str = "UNVALIDATED",
) -> dict[str, Any]:
    """Every question and every battery object of ``spec``, aggregated over ``dataset``.

    A battery object is aggregated as the scale question the unit compiles it to
    (``research_project.py`` ``_prefixed_battery_questions``).
    """
    weights = [r.weight for r in dataset.respondents]
    donors = [r.donor_id for r in dataset.respondents]

    def column(qid: str) -> list[Any]:
        return [r.answers.get(qid) for r in dataset.respondents]

    questions = {
        q.id: aggregate_question(
            q, column(q.id), weights, donors, validation_status=validation_status
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
