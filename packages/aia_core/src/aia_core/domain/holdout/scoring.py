"""Scoring a confirmation run: the metrics, the comparisons, P1-P8 and the verdict (7a, 7d).

The truth is **the same sampled people's own answers**: each respondent's real answer to each
item, read from the population on the rows the item is scored on. So the error of drawing the
respondents is never counted against the model, and an arm's marginal is compared with the
marginal of the very people it answered for.

Per item, for an arm's replicate:

1. ``tvd`` -- total variation distance, in percentage points, between the weighted distribution
   of the drawn answers and that of the true answers;
2. ``subgroup_tvd`` -- the same within each sex x age-band cell holding at least
   :data:`MIN_CELL_DONORS` donors, averaged over those cells (``None`` when no cell holds
   enough);
3. ``brier`` -- the weighted mean Brier score of each respondent's predicted probabilities
   against their own answer, on an item whose answer is that person's own (a core item); a
   matched block's answer is another donor's, so it has no ``brier``;
4. ``entropy_gap`` -- the modelled marginal's entropy minus the true marginal's, in bits.

An item's metric for an arm is its mean over the arm's replicates. Uncertainty is a bootstrap
over items, paired between arms.

The verdict (:func:`verdict`) applies P1-P8 to arm D. The comparisons are one Holm-corrected
family at :data:`~.preregistration.THRESHOLDS` ``P4_P5_family_alpha``:

- D beats **A** on ``tvd`` (P4): the persona adds to what the question alone gets;
- D beats **S** on ``subgroup_tvd`` and on ``brier`` (P5): the right person matters.

D is not compared with S on the whole-sample ``tvd``: S shows a permutation of the same
sample's personas, so its whole-sample marginal matches D's by construction, and the
comparison would test nothing (a finding of 7d, recorded in the plan).

A criterion that cannot be evaluated -- no subgroup cell large enough, no core item for the
Brier score -- fails: unknown is never scored as good.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from .preregistration import THRESHOLDS

__all__ = [
    "MIN_CELL_DONORS",
    "SCORING_VERSION",
    "ArmRun",
    "Criterion",
    "ItemMetrics",
    "ItemTruth",
    "Respondent",
    "Verdict",
    "holm",
    "item_metrics",
    "verdict",
]

SCORING_VERSION: Final = "aia-holdout-scoring-1"
#: 7a: a sex x age-band cell is scored when it holds at least 50 donors.
MIN_CELL_DONORS: Final = 50
_BOOTSTRAP_PERCENTILE: Final = 0.95


@dataclass(frozen=True, slots=True)
class Respondent:
    """A sampled respondent as the scoring reads them."""

    respondent_id: str
    donor_id: str
    weight: float
    #: The sex x age-band cell, ``None`` when either is unknown (then in no cell).
    cell: str | None


@dataclass(frozen=True, slots=True)
class ItemTruth:
    """One confirmation item and the sampled people's own answers to it."""

    item: str
    domain: str
    codes: tuple[str, ...]
    #: True when the answer is the respondent's own (a core item): the Brier score applies.
    person_level: bool
    #: Each scored respondent's real answer; a respondent outside the scored rows is absent.
    answers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ArmRun:
    """One replicate of one arm: each respondent's drawn answer and predicted probabilities."""

    arm: str
    replicate: int
    #: ``(item, respondent) -> drawn code``.
    answers: Mapping[tuple[str, str], str]
    #: ``(item, respondent) -> probabilities in the item's code order``.
    probabilities: Mapping[tuple[str, str], tuple[float, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ItemMetrics:
    """One item's metrics for one arm, averaged over its replicates."""

    item: str
    domain: str
    tvd: float
    subgroup_tvd: float | None
    brier: float | None
    entropy_gap: float


@dataclass(frozen=True, slots=True)
class Criterion:
    """One pass criterion: its value, the threshold it met or missed, and the outcome."""

    name: str
    passed: bool
    value: float | None
    threshold: float
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Verdict:
    """PASS only when every criterion passed; every criterion is kept either way."""

    passed: bool
    criteria: tuple[Criterion, ...]
    arms: Mapping[str, Mapping[str, float | None]]
    ablation: Mapping[str, Any]
    scoring_version: str = SCORING_VERSION

    def document(self) -> dict[str, Any]:
        """The verdict as a JSON document, for the immutable verdict artifact."""
        return {
            "scoring_version": self.scoring_version,
            "verdict": "PASS" if self.passed else "FAIL",
            "criteria": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "value": c.value,
                    "threshold": c.threshold,
                    "detail": dict(c.detail),
                }
                for c in self.criteria
            ],
            "arms": {arm: dict(metrics) for arm, metrics in self.arms.items()},
            "ablation": dict(self.ablation),
        }


def _distribution(weighted: Sequence[tuple[str, float]], codes: Sequence[str]) -> dict[str, float]:
    total = math.fsum(w for _, w in weighted)
    out = dict.fromkeys(codes, 0.0)
    if total <= 0:
        return out
    for code, w in weighted:
        if code in out:
            out[code] += w / total
    return out


def _tvd_pp(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return 50.0 * math.fsum(abs(a[c] - b[c]) for c in a)


def _entropy_bits(p: Mapping[str, float]) -> float:
    return -math.fsum(v * math.log2(v) for v in p.values() if v > 0)


def _one_replicate(
    truth: ItemTruth, run: ArmRun, respondents: Mapping[str, Respondent]
) -> tuple[float, float | None, float | None, float]:
    scored = [r for r in truth.answers if (truth.item, r) in run.answers]
    if len(scored) != len(truth.answers):
        missing = len(truth.answers) - len(scored)
        raise ValueError(
            f"arm {run.arm} replicate {run.replicate} lacks {missing} answers to {truth.item}"
        )
    true = _distribution([(truth.answers[r], respondents[r].weight) for r in scored], truth.codes)
    drawn = _distribution(
        [(run.answers[(truth.item, r)], respondents[r].weight) for r in scored], truth.codes
    )
    tvd = _tvd_pp(drawn, true)

    cells: dict[str, list[str]] = {}
    for r in scored:
        cell = respondents[r].cell
        if cell is not None:
            cells.setdefault(cell, []).append(r)
    cell_tvds = []
    for members in cells.values():
        if len({respondents[r].donor_id for r in members}) < MIN_CELL_DONORS:
            continue
        t = _distribution([(truth.answers[r], respondents[r].weight) for r in members], truth.codes)
        d = _distribution(
            [(run.answers[(truth.item, r)], respondents[r].weight) for r in members], truth.codes
        )
        cell_tvds.append(_tvd_pp(d, t))
    subgroup = statistics.fmean(cell_tvds) if cell_tvds else None

    brier: float | None = None
    if truth.person_level:
        total = math.fsum(respondents[r].weight for r in scored)
        acc = 0.0
        for r in scored:
            probs = run.probabilities.get((truth.item, r))
            if probs is None or len(probs) != len(truth.codes):
                raise ValueError(
                    f"arm {run.arm} replicate {run.replicate} lacks probabilities for "
                    f"{truth.item} / {r}"
                )
            own = truth.codes.index(truth.answers[r])
            acc += respondents[r].weight * math.fsum(
                (p - (1.0 if k == own else 0.0)) ** 2 for k, p in enumerate(probs)
            )
        brier = acc / total if total > 0 else None
    return tvd, subgroup, brier, _entropy_bits(drawn) - _entropy_bits(true)


def item_metrics(
    truths: Sequence[ItemTruth], runs: Sequence[ArmRun], respondents: Sequence[Respondent]
) -> tuple[ItemMetrics, ...]:
    """Every item's metrics for one arm, averaged over ``runs`` (its replicates)."""
    if not runs:
        raise ValueError("an arm needs at least one replicate")
    by_id = {r.respondent_id: r for r in respondents}
    out = []
    for truth in truths:
        per = [_one_replicate(truth, run, by_id) for run in runs]
        subgroups = [p[1] for p in per if p[1] is not None]
        briers = [p[2] for p in per if p[2] is not None]
        out.append(
            ItemMetrics(
                item=truth.item,
                domain=truth.domain,
                tvd=statistics.fmean(p[0] for p in per),
                subgroup_tvd=statistics.fmean(subgroups) if len(subgroups) == len(per) else None,
                brier=statistics.fmean(briers) if len(briers) == len(per) else None,
                entropy_gap=statistics.fmean(p[3] for p in per),
            )
        )
    return tuple(out)


def _bootstrap_means(values: Sequence[float], resamples: int, rng: random.Random) -> list[float]:
    n = len(values)
    return [statistics.fmean(values[rng.randrange(n)] for _ in range(n)) for _ in range(resamples)]


def _p_improvement(
    worse: Sequence[float], better: Sequence[float], resamples: int, rng: random.Random
) -> tuple[float, float]:
    """The mean paired improvement (worse - better) and its one-sided bootstrap p-value."""
    diffs = [w - b for w, b in zip(worse, better, strict=True)]
    means = _bootstrap_means(diffs, resamples, rng)
    p = (sum(1 for m in means if m <= 0) + 1) / (resamples + 1)
    return statistics.fmean(diffs), p


def holm(p_values: Mapping[str, float], alpha: float) -> dict[str, bool]:
    """Holm's step-down: which hypotheses are rejected at family-wise ``alpha``."""
    ordered = sorted(p_values.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(ordered)
    out: dict[str, bool] = {}
    still = True
    for k, (name, p) in enumerate(ordered):
        still = still and p <= alpha / (m - k)
        out[name] = still
    return out


def _paired(
    worse: Sequence[ItemMetrics], better: Sequence[ItemMetrics], metric: str
) -> tuple[list[float], list[float]] | None:
    pairs = [
        (getattr(w, metric), getattr(b, metric))
        for w, b in zip(worse, better, strict=True)
        if getattr(w, metric) is not None and getattr(b, metric) is not None
    ]
    if not pairs:
        return None
    return [w for w, _ in pairs], [b for _, b in pairs]


def _summary(metrics: Sequence[ItemMetrics]) -> dict[str, float | None]:
    def mean(name: str) -> float | None:
        values = [getattr(m, name) for m in metrics if getattr(m, name) is not None]
        return statistics.fmean(values) if values else None

    return {
        "tvd": mean("tvd"),
        "subgroup_tvd": mean("subgroup_tvd"),
        "brier": mean("brier"),
        "entropy_gap": mean("entropy_gap"),
    }


def verdict(
    truths: Sequence[ItemTruth],
    respondents: Sequence[Respondent],
    runs: Mapping[str, Sequence[ArmRun]],
    *,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> Verdict:
    """Apply P1-P8 to arm D, with A and S for the comparisons and every arm summarised.

    ``runs`` maps an arm to its replicates; D, A and S are required, B and C feed the
    ablation's record. The code baselines L0 / L1 are summarised by the caller beside this.
    """
    for arm in ("A", "D", "S"):
        if not runs.get(arm):
            raise ValueError(f"the verdict needs arm {arm}")
    metrics = {arm: item_metrics(truths, arm_runs, respondents) for arm, arm_runs in runs.items()}
    d = metrics["D"]
    rng = random.Random(f"holdout-bootstrap:{bootstrap_seed}")
    criteria: list[Criterion] = []

    # P1: the mean TVD and its 95 % bootstrap upper bound.
    tvds = [m.tvd for m in d]
    means = sorted(_bootstrap_means(tvds, bootstrap_resamples, rng))
    upper = means[min(len(means) - 1, math.ceil(_BOOTSTRAP_PERCENTILE * len(means)) - 1)]
    mean_tvd = statistics.fmean(tvds)
    criteria.append(
        Criterion(
            "P1_mean_tvd",
            mean_tvd <= THRESHOLDS["P1_mean_tvd_pp_max"]
            and upper <= THRESHOLDS["P1_mean_tvd_upper_95_pp_max"],
            mean_tvd,
            THRESHOLDS["P1_mean_tvd_pp_max"],
            {"upper_95": upper, "upper_threshold": THRESHOLDS["P1_mean_tvd_upper_95_pp_max"]},
        )
    )

    # P2: the worst domain.
    by_domain: dict[str, list[float]] = {}
    for m in d:
        by_domain.setdefault(m.domain, []).append(m.tvd)
    domain_means = {k: statistics.fmean(v) for k, v in sorted(by_domain.items())}
    worst = max(domain_means.values())
    criteria.append(
        Criterion(
            "P2_worst_domain_tvd",
            worst <= THRESHOLDS["P2_worst_domain_tvd_pp_max"],
            worst,
            THRESHOLDS["P2_worst_domain_tvd_pp_max"],
            {"domains": domain_means},
        )
    )

    # P3: items missing by more than 20 pp.
    share = sum(1 for t in tvds if t > 20.0) / len(tvds)
    criteria.append(
        Criterion(
            "P3_items_over_20pp",
            share <= THRESHOLDS["P3_items_over_20pp_share_max"],
            share,
            THRESHOLDS["P3_items_over_20pp_share_max"],
        )
    )

    # P4 and P5: one Holm family.
    alpha = THRESHOLDS["P4_P5_family_alpha"]
    tests: dict[str, tuple[float, float] | None] = {}
    for name, worse_arm, metric in (
        ("D_beats_A_tvd", "A", "tvd"),
        ("D_beats_S_subgroup_tvd", "S", "subgroup_tvd"),
        ("D_beats_S_brier", "S", "brier"),
    ):
        paired = _paired(metrics[worse_arm], d, metric)
        tests[name] = None if paired is None else _p_improvement(*paired, bootstrap_resamples, rng)
    known = {k: v[1] for k, v in tests.items() if v is not None}
    rejected = holm(known, alpha) if known else {}
    for criterion, names in (
        ("P4_beats_no_persona", ("D_beats_A_tvd",)),
        ("P5_beats_wrong_person", ("D_beats_S_subgroup_tvd", "D_beats_S_brier")),
    ):
        detail: dict[str, dict[str, object]] = {}
        for n in names:
            test = tests[n]
            detail[n] = (
                {"unknown": True}
                if test is None
                else {"mean_improvement": test[0], "p": test[1], "rejected": rejected[n]}
            )
        passed = all(tests[n] is not None and rejected.get(n, False) for n in names)
        criteria.append(Criterion(criterion, passed, None, alpha, detail))

    # P6: subgroup TVD, P7: mode collapse, P8: replicate noise.
    subgroup = _summary(d)["subgroup_tvd"]
    criteria.append(
        Criterion(
            "P6_subgroup_tvd",
            subgroup is not None and subgroup <= THRESHOLDS["P6_subgroup_tvd_pp_max"],
            subgroup,
            THRESHOLDS["P6_subgroup_tvd_pp_max"],
        )
    )
    gap = statistics.fmean(m.entropy_gap for m in d)
    criteria.append(
        Criterion(
            "P7_entropy_gap",
            gap >= THRESHOLDS["P7_entropy_gap_bits_min"],
            gap,
            THRESHOLDS["P7_entropy_gap_bits_min"],
        )
    )
    replicate_means = [
        statistics.fmean(m.tvd for m in item_metrics(truths, [run], respondents))
        for run in runs["D"]
    ]
    sd = statistics.stdev(replicate_means) if len(replicate_means) > 1 else None
    criteria.append(
        Criterion(
            "P8_replicate_sd",
            sd is not None and sd <= THRESHOLDS["P8_replicate_sd_pp_max"],
            sd,
            THRESHOLDS["P8_replicate_sd_pp_max"],
            {"replicate_mean_tvd": replicate_means},
        )
    )
    return Verdict(
        passed=all(c.passed for c in criteria),
        criteria=tuple(criteria),
        arms={arm: _summary(m) for arm, m in sorted(metrics.items())},
        ablation=_ablation(truths, respondents, runs),
    )


def _ablation(
    truths: Sequence[ItemTruth],
    respondents: Sequence[Respondent],
    runs: Mapping[str, Sequence[ArmRun]],
) -> dict[str, Any]:
    """18.6.6's own rule (``LLM_ABLATION_STATUS_v17_1``): the catalog signals earn their place
    only if D beats C, and C beats B, by more than twice the between-replicate SD."""
    if not all(runs.get(a) for a in ("B", "C", "D")):
        return {"evaluated": False}
    means: dict[str, float] = {}
    sds: dict[str, float | None] = {}
    for arm in ("B", "C", "D"):
        per = [
            statistics.fmean(m.tvd for m in item_metrics(truths, [run], respondents))
            for run in runs[arm]
        ]
        means[arm] = statistics.fmean(per)
        sds[arm] = statistics.stdev(per) if len(per) > 1 else None
    known = [s for s in sds.values() if s is not None]
    noise = 2 * max(known) if known else None
    return {
        "evaluated": True,
        "mean_tvd": means,
        "replicate_sd": sds,
        "noise": noise,
        "signals_earn_place": noise is not None
        and means["C"] - means["D"] > noise
        and means["B"] - means["C"] > noise,
    }
