"""The respondents a run's fieldwork draws from its population: 18.6.6's representative sample.

A port of ``representative_sampling.draw_representative``
(``legacy/npc-panel-18.6.6/app/representative_sampling.py:131-173``), the sampler the unit's
``pipeline.sample_representative`` returns through (``pipeline.py:298``), on the path the unit
ships for when SciPy's MILP is unavailable: largest-remainder quotas over the joint cells
(``_quota_vector_fallback``, ``:117-128``). The owner chose that path on 2026-10-12 because the
domain is stdlib only (plan ``panel-grounded-respondents.md`` § 2a).

What the unit does, kept:

* the base weight is the population's analysis weight over the audience, clipped below at
  ``1e-12`` (``pipeline.py:278``), so a zero-weight row is drawn only when its cell needs it;
* a quota field is used only when it holds more than one value in the audience
  (``:134``); a category is the ``str`` of the value as ``read_csv`` types it, a missing cell
  ``"<missing>"`` (``:26``);
* targets are each used field's weighted shares (``_targets``, ``:22-30``);
* quotas are the largest remainder over ``pohlavi x vek_skupina x kraj``, plus ``vzdelani`` from
  ``n >= 700`` (``:142-144``), capped by each cell's rows; a remainder tie goes to the seeded
  noise the unit adds (``1e-9``), so quotas are exact wherever no two remainders lie that close;
* each cell's quota is drawn by weight without replacement, the picks shuffled (``:147-158``);
* the sample is raked to every used field's targets (``_rake``, ``:53-66``) and audited raw and
  weighted (``_audit``, ``:32-50``) against ``max(0.50, 100/n)`` and ``max(0.25, 100/n)``
  percentage points (``:164-171``);
* with no usable quota field, ``n`` rows are drawn by weight and weighted by their base weight
  over its mean (``:136-137``).

Deliberate differences (plan § 2a, § 2e): a refusal where the unit carried on -- an audience
filter it would drop, an all-zero weight (the unit used 1.0), a declared quota field the
population lacks (the unit skipped it), a field the policy refuses -- and one sample where the
unit refused: when ``n`` nears the audience's size and cells fill, the unit's tie-break noise can
hand a full cell a seat and its draw fails ("Buňka … nemá dost respondentů", fixture D15, D16);
here a full cell takes no seat. The draws differ from the
unit's: they come from :class:`random.Random`, not NumPy's PCG64 (the constraint OI-62 records),
so parity is EXACT for targets, quotas, raking and the audit given the same picks, and by property
for the draw (``tools/sampling_capture.py``; ``tests/fixtures/representative_draw/``).

Pure: stdlib only.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from .audience import AUDIENCE_FILTER_VERSION, _typed, column_type, select_audience
from .errors import PopulationError
from .policy import FieldUse
from .runtime import Cell, RuntimePopulation

__all__ = [
    "DONOR_FIELD",
    "MISSING",
    "QUOTA_FIELDS",
    "SAMPLER_VERSION",
    "Composition",
    "Draw",
    "PanelSample",
    "SampleAudit",
    "SampledRespondent",
    "SamplingRefused",
    "audit_composition",
    "category_keys",
    "draw_panel_sample",
    "joint_fields",
    "quantile",
    "quotas",
    "rake",
    "representative_draw",
    "targets",
    "usable_fields",
]

SAMPLER_VERSION: Final = (
    "aia-panel-sampler-1 (18.6.6 representative_sampling 17.7, largest remainder)"
)

#: The unit's ``DEFAULT_FIELDS`` (``representative_sampling.py:6``): declared, versioned here.
QUOTA_FIELDS: Final = ("pohlavi", "vek_skupina", "kraj", "vzdelani", "zamestnani_status")

#: The fields the quota cells are built from, in key order (``:142``).
_JOINT: Final = ("pohlavi", "vek_skupina", "kraj")
_JOINT_LARGE: Final = "vzdelani"
_JOINT_LARGE_FROM: Final = 700

DONOR_FIELD: Final = "core_donor_id"
MISSING: Final = "<missing>"
SELECTION_METHOD: Final = "largest_remainder"

_WEIGHT_FLOOR: Final = 1e-12
_RAKE_ITERATIONS: Final = 60
_RAKE_FLOOR: Final = 1e-6
_RAKE_CAP: Final = 8.0
_RAKE_CONVERGED: Final = 1e-8
_NOISE: Final = 1e-9
_CELL_SEPARATOR: Final = "¦"

Keys = Sequence[str]
Targets = dict[str, dict[str, float]]


class SamplingRefused(PopulationError):
    """The sample cannot be drawn as asked; ``reason`` names why."""

    reason = "sampling_refused"


# --------------------------------------------------------------------------- #
# The unit's arithmetic, over category keys and weights
# --------------------------------------------------------------------------- #


def category_keys(name: str, cells: Sequence[Cell]) -> tuple[str, ...]:
    """``column.astype("string").fillna("<missing>")`` of a column as ``read_csv`` types it."""
    kind = column_type(name, cells)
    out: list[str] = []
    for cell in cells:
        value = _typed(cell, kind)
        out.append(MISSING if value is None else str(value))
    return tuple(out)


def usable_fields(keys: Mapping[str, Keys], declared: Sequence[str]) -> tuple[str, ...]:
    """The declared fields holding more than one value, missing aside (``nunique() > 1``)."""
    return tuple(f for f in declared if f in keys and len({k for k in keys[f] if k != MISSING}) > 1)


def joint_fields(fields: Sequence[str], n: int) -> tuple[str, ...]:
    """The fields the quota cells are built from (``representative_sampling.py:142-144``)."""
    joint = [f for f in _JOINT if f in fields]
    if n >= _JOINT_LARGE_FROM and _JOINT_LARGE in fields:
        joint.append(_JOINT_LARGE)
    return tuple(joint) if joint else tuple(fields[:2])


def _grouped(keys: Keys, weights: Sequence[float]) -> dict[str, float]:
    """``groupby(key, sort=True)["w"].sum()``: a weight per key, keys in sorted order."""
    sums: dict[str, float] = {}
    for key, weight in zip(keys, weights, strict=True):
        sums[key] = sums.get(key, 0.0) + weight
    return {k: sums[k] for k in sorted(sums)}


def targets(keys: Mapping[str, Keys], weights: Sequence[float], fields: Sequence[str]) -> Targets:
    """Each field's weighted share per category (``_targets``, ``:22-30``)."""
    out: Targets = {}
    for f in fields:
        if f not in keys:
            continue
        sums = _grouped(keys[f], weights)
        total = math.fsum(sums.values())
        if total > 0:
            out[f] = {k: v / total for k, v in sums.items()}
    return out


def _cells(keys: Mapping[str, Keys], fields: Sequence[str], rows: int) -> tuple[str, ...]:
    return tuple(_CELL_SEPARATOR.join(keys[f][i] for f in fields) for i in range(rows))


def quotas(cells: Keys, weights: Sequence[float], n: int, rng: random.Random) -> dict[str, int]:
    """Largest-remainder quotas per cell (``_quota_vector_fallback``, ``:117-128``)."""
    sums = _grouped(cells, weights)
    capacity: dict[str, int] = {}
    for cell in cells:
        capacity[cell] = capacity.get(cell, 0) + 1
    names = list(sums)
    total = math.fsum(sums.values())
    expected = [n * sums[c] / total for c in names]
    q = [min(math.floor(e), capacity[c]) for e, c in zip(expected, names, strict=True)]
    frac = [max(e - k, 0.0) for e, k in zip(expected, q, strict=True)]
    left = n - sum(q)
    while left > 0:
        available = [q[j] < capacity[c] for j, c in enumerate(names)]
        if not any(available):
            break
        # The unit adds its noise to every cell, a full one too (``:124``), so once the
        # remainders are spent a full cell can win a seat it has no row for, and the draw
        # then fails (``:153``). A full cell takes no seat here; the noise is still drawn for
        # every cell, and wherever the unit produced a sample the quotas are the same.
        noise = [rng.random() * _NOISE for _ in names]
        scores = [frac[j] + noise[j] if available[j] else 0.0 for j in range(len(names))]
        if sum(scores) <= 0:
            scores = [1.0 if a else 0.0 for a in available]
        j = max(range(len(names)), key=lambda i: (scores[i], -i))
        q[j] += 1
        frac[j] = max(0.0, frac[j] - 1.0)
        left -= 1
    if sum(q) != n:
        raise SamplingRefused(
            f"no sample of {n} distinct rows can be built from this audience",
            reason="sampling_n_exceeds_support",
        )
    return dict(zip(names, q, strict=True))


def quantile(values: Sequence[float], q: float) -> float:
    """``numpy.quantile(values, q)``, the default linear method, numpy's own interpolation."""
    ordered = sorted(values)
    virtual = (len(ordered) - 1) * q
    below = math.floor(virtual)
    above = min(below + 1, len(ordered) - 1)
    gamma = virtual - below
    a, b = ordered[below], ordered[above]
    diff = b - a
    return b - diff * (1 - gamma) if gamma >= 0.5 else a + diff * gamma


def rake(keys: Mapping[str, Keys], goal: Targets, base: Sequence[float]) -> tuple[float, ...]:
    """The sample's weights raked to ``goal`` (``_rake``, ``:53-66``), mean 1."""
    w = [max(b, 1e-9) for b in base]
    rows = len(w)
    for _ in range(_RAKE_ITERATIONS):
        old = list(w)
        for f, shares in goal.items():
            if f not in keys:
                continue
            values = keys[f]
            total = math.fsum(w) or 1.0
            for category, share in shares.items():
                members = [i for i in range(rows) if values[i] == category]
                current = math.fsum(w[i] for i in members) / total
                if members and current > 0:
                    factor = share / current
                    for i in members:
                        w[i] *= factor
        cap = (quantile(w, 0.99) if rows > 20 else max(w)) * _RAKE_CAP
        upper = max(cap, _RAKE_FLOOR)
        w = [min(max(x, _RAKE_FLOOR), upper) for x in w]
        mean = math.fsum(w) / rows or 1.0
        w = [x / mean for x in w]
        if max(abs(a - b) for a, b in zip(w, old, strict=True)) < _RAKE_CONVERGED:
            break
    return tuple(w)


@dataclass(frozen=True, slots=True)
class Composition:
    """``_audit``'s result: the sample's shares against the targets, in percentage points."""

    max_abs_pp: float
    mean_abs_pp: float
    diff_pp: dict[str, dict[str, float]]
    counts: dict[str, dict[str, float]]

    def as_json(self) -> dict[str, Any]:
        return {
            "max_abs_pp": self.max_abs_pp,
            "mean_abs_pp": self.mean_abs_pp,
            "diff_pp": self.diff_pp,
            "counts": self.counts,
        }


def audit_composition(
    keys: Mapping[str, Keys], goal: Targets, weights: Sequence[float] | None = None
) -> Composition:
    """The sample's composition against ``goal``, raw or weighted (``_audit``, ``:32-50``)."""
    diffs: dict[str, dict[str, float]] = {}
    counts: dict[str, dict[str, float]] = {}
    largest = 0.0
    parts: list[float] = []
    for f, shares in goal.items():
        if f not in keys:
            continue
        values = keys[f]
        if weights is None:
            tally: dict[str, int] = {}
            for v in values:
                tally[v] = tally.get(v, 0) + 1
            got = {k: c / len(values) for k, c in tally.items()}
            counts[f] = {k: float(c) for k, c in tally.items()}
        else:
            sums = _grouped(values, weights)
            denominator = math.fsum(sums.values()) or 1.0
            got = {k: v / denominator for k, v in sums.items()}
            counts[f] = {k: round(v, 3) for k, v in sums.items()}
        field_diffs: dict[str, float] = {}
        for category, share in shares.items():
            d = 100.0 * (got.get(category, 0.0) - share)
            field_diffs[category] = round(d, 3)
            largest = max(largest, abs(d))
            parts.append(abs(d))
        diffs[f] = field_diffs
    mean = math.fsum(parts) / len(parts) if parts else 0.0
    return Composition(round(largest, 3), round(mean, 3), diffs, counts)


def _weighted_without_replacement(
    rows: Sequence[int], weights: Sequence[float], count: int, rng: random.Random
) -> list[int]:
    """``rng.choice(rows, size=count, replace=False, p=weights)``: successive weighted picks."""
    pool = list(rows)
    mass = list(weights)
    if math.fsum(mass) <= 0:
        mass = [1.0] * len(pool)
    chosen: list[int] = []
    for _ in range(count):
        total = math.fsum(mass)
        point = rng.random() * total
        running = 0.0
        pick = len(pool) - 1
        for j, m in enumerate(mass):
            running += m
            if point < running and m > 0:
                pick = j
                break
        while mass[pick] <= 0:  # a rounding overshoot lands on the last row with mass
            pick -= 1
        chosen.append(pool.pop(pick))
        mass.pop(pick)
    return chosen


@dataclass(frozen=True, slots=True)
class Draw:
    """What :func:`representative_draw` returns: positions in the audience, in sample order."""

    picks: tuple[int, ...]
    base_weights: tuple[float, ...]
    analysis_weights: tuple[float, ...]
    fields: tuple[str, ...]
    quota_fields: tuple[str, ...]
    quotas: dict[str, int]
    targets: Targets
    raw: Composition | None
    weighted: Composition | None


def representative_draw(
    keys: Mapping[str, Keys], weights: Sequence[float], n: int, rng: random.Random
) -> Draw:
    """``draw_representative`` (``:131-158``) over the audience's category keys and weights.

    ``weights`` are the base weights, already floored; positions are into the audience.
    """
    rows = len(weights)
    fields = usable_fields(keys, QUOTA_FIELDS)
    if not fields:
        drawn = _weighted_without_replacement(range(rows), weights, n, rng)
        base = tuple(weights[i] for i in drawn)
        mean = math.fsum(base) / n
        return Draw(
            picks=tuple(drawn),
            base_weights=base,
            analysis_weights=tuple(b / mean for b in base),
            fields=(),
            quota_fields=(),
            quotas={},
            targets={},
            raw=None,
            weighted=None,
        )
    goal = targets(keys, weights, fields)
    joint = joint_fields(fields, n)
    cells = _cells(keys, joint, rows)
    allotted = quotas(cells, weights, n, rng)
    members: dict[str, list[int]] = {}
    for i, cell in enumerate(cells):
        members.setdefault(cell, []).append(i)
    picks: list[int] = []
    for cell, count in allotted.items():
        if count > 0:
            pos = members[cell]
            picks.extend(_weighted_without_replacement(pos, [weights[i] for i in pos], count, rng))
    rng.shuffle(picks)
    sample = {f: tuple(keys[f][i] for i in picks) for f in fields}
    base = tuple(weights[i] for i in picks)
    analysis = rake(sample, goal, base)
    return Draw(
        picks=tuple(picks),
        base_weights=base,
        analysis_weights=analysis,
        fields=fields,
        quota_fields=joint,
        quotas=allotted,
        targets=goal,
        raw=audit_composition(sample, goal),
        weighted=audit_composition(sample, goal, analysis),
    )


# --------------------------------------------------------------------------- #
# The sample a run records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SampledRespondent:
    """One drawn row: where it is in the population, its donor, its weights, its place."""

    row: int
    donor: str | None
    base_weight: float
    analysis_weight: float
    order: int


@dataclass(frozen=True, slots=True)
class SampleAudit:
    """The representativeness record (``representative_sampling.py:164-171``)."""

    status: str
    population_n: int
    sample_n: int
    fields: tuple[str, ...]
    quota_fields: tuple[str, ...]
    selection_method: str
    raw: Composition | None
    weighted: Composition | None
    raw_tolerance_pp: float
    weighted_tolerance_pp: float
    raw_selection_warning: bool
    effective_n: float
    effective_n_ratio: float
    weight_min: float
    weight_max: float
    #: Distinct donors behind the audience and behind the sample; None without a donor column.
    audience_donors: int | None
    sample_donors: int | None

    def as_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "population_n": self.population_n,
            "sample_n": self.sample_n,
            "fields": list(self.fields),
            "quota_fields": list(self.quota_fields),
            "selection_method": self.selection_method,
            "raw": None if self.raw is None else self.raw.as_json(),
            "weighted": None if self.weighted is None else self.weighted.as_json(),
            "raw_tolerance_pp": self.raw_tolerance_pp,
            "weighted_tolerance_pp": self.weighted_tolerance_pp,
            "raw_selection_warning": self.raw_selection_warning,
            "effective_n": self.effective_n,
            "effective_n_ratio": self.effective_n_ratio,
            "weight_min": self.weight_min,
            "weight_max": self.weight_max,
            "audience_donors": self.audience_donors,
            "sample_donors": self.sample_donors,
        }


def tolerances(n: int) -> tuple[float, float]:
    """The raw and the weighted tolerance in percentage points (``:164``)."""
    grain = 100.0 / max(n, 1)
    return max(0.50, grain), max(0.25, grain)


def judge(draw: Draw, n: int) -> tuple[str, bool]:
    """``PASS`` / ``PASS_WEIGHTED``, or the refusal the unit raised (``:165-167``)."""
    if draw.raw is None or draw.weighted is None:
        return "PASS", False
    raw_tol, weighted_tol = tolerances(n)
    if draw.weighted.max_abs_pp > weighted_tol + 1e-9:
        raise SamplingRefused(
            f"a sample of {n} is not representative of this audience after calibration "
            f"(selection max {draw.raw.max_abs_pp} pp; calibrated max "
            f"{draw.weighted.max_abs_pp} pp, limit {round(weighted_tol, 3)} pp); "
            "a larger n or a wider audience is needed",
            reason="sampling_unrepresentative",
        )
    warn = draw.raw.max_abs_pp > raw_tol + 1e-9
    return ("PASS_WEIGHTED" if warn else "PASS"), warn


@dataclass(frozen=True, slots=True)
class PanelSample:
    """The respondents a run's fieldwork draws, and how they were drawn. Frozen, recorded."""

    respondents: tuple[SampledRespondent, ...]
    audit: SampleAudit
    filters: dict[str, Any]
    seed: int
    version_id: str
    content_sha256: str
    sampler_version: str = SAMPLER_VERSION
    audience_filter_version: str = AUDIENCE_FILTER_VERSION

    def provenance(self) -> dict[str, Any]:
        """What the run's fieldwork provenance records about its sample."""
        return {
            "sampler_version": self.sampler_version,
            "audience_filter_version": self.audience_filter_version,
            "filters": self.filters,
            "seed": self.seed,
            "version_id": self.version_id,
            "content_sha256": self.content_sha256,
            "audit": self.audit.as_json(),
        }


def draw_panel_sample(
    population: RuntimePopulation, filters: Mapping[str, Any] | None, n: int, seed: int
) -> PanelSample:
    """``n`` respondents for a run, from the population its binding recorded -- or a refusal.

    Refuses, naming the reason, never drawing a smaller or different sample:
    ``sampling_filter_invalid``, ``sampling_field_refused`` (a filter or a quota field the
    policy does not allow, or quota fields it does not allow jointly), ``sampling_empty``,
    ``sampling_n_invalid``, ``sampling_n_exceeds_support``, ``sampling_field_unknown``,
    ``sampling_no_weight``, ``sampling_unrepresentative``.
    """
    if n < 1:
        raise SamplingRefused(f"a sample needs n >= 1, not {n}", reason="sampling_n_invalid")
    unknown = [f for f in QUOTA_FIELDS if f not in population.fields]
    if unknown:
        raise SamplingRefused(
            f"the population lacks the quota fields {unknown}", reason="sampling_field_unknown"
        )
    selection = select_audience(population, filters)
    audience = selection.rows
    if n > len(audience):
        raise SamplingRefused(
            f"the audience holds {len(audience)} distinct rows and the sample asks for {n}; "
            "the sample is drawn without replacement",
            reason="sampling_n_exceeds_support",
        )
    every = population.analysis_weight
    raw_weights = [every[i] for i in audience]
    if math.fsum(raw_weights) <= 0:
        raise SamplingRefused(
            "every row of this audience has weight 0; there is no default weight",
            reason="sampling_no_weight",
        )
    weights = [max(w, _WEIGHT_FLOOR) for w in raw_weights]

    keys: dict[str, tuple[str, ...]] = {}
    for f in QUOTA_FIELDS:
        column = population.column(f)
        keys[f] = category_keys(f, [column[i] for i in audience])
    fields = usable_fields(keys, QUOTA_FIELDS)
    refused = [
        f"{f}: {decision.reason}"
        for f in fields
        if not (decision := population.decide(f, FieldUse.AUDIENCE_FILTERING)).allowed
    ]
    joint = population.decide_joint(fields, client_facing=False)
    if not joint.allowed:
        refused.append(f"{', '.join(fields)} jointly: {joint.reason}")
    if refused:
        raise SamplingRefused(
            "the field policy does not allow sampling on: " + "; ".join(refused),
            reason="sampling_field_refused",
        )

    draw = representative_draw(keys, weights, n, random.Random(seed))
    status, warn = judge(draw, n)

    donors: tuple[Cell, ...] | None = None
    if DONOR_FIELD in population.fields:
        column = population.column(DONOR_FIELD)
        donors = tuple(column[i] for i in audience)
    respondents = tuple(
        SampledRespondent(
            row=audience[p],
            donor=None if donors is None else donors[p],
            base_weight=draw.base_weights[order],
            analysis_weight=draw.analysis_weights[order],
            order=order,
        )
        for order, p in enumerate(draw.picks)
    )
    aw = draw.analysis_weights
    ess = math.fsum(aw) ** 2 / (math.fsum(w * w for w in aw) or 1.0)
    raw_tol, weighted_tol = tolerances(n)
    audit = SampleAudit(
        status=status,
        population_n=len(audience),
        sample_n=n,
        fields=draw.fields,
        quota_fields=draw.quota_fields,
        selection_method=SELECTION_METHOD,
        raw=draw.raw,
        weighted=draw.weighted,
        raw_tolerance_pp=round(raw_tol, 3),
        weighted_tolerance_pp=weighted_tol,
        raw_selection_warning=warn,
        effective_n=round(ess, 3),
        effective_n_ratio=round(ess / max(float(n), 1.0), 4),
        weight_min=round(min(aw), 4),
        weight_max=round(max(aw), 4),
        audience_donors=None if donors is None else len({d for d in donors if d is not None}),
        sample_donors=None
        if donors is None
        else len({r.donor for r in respondents if r.donor is not None}),
    )
    return PanelSample(
        respondents=respondents,
        audit=audit,
        filters=selection.filters_json(),
        seed=seed,
        version_id=population.binding.version_id,
        content_sha256=population.binding.content_sha256,
    )
