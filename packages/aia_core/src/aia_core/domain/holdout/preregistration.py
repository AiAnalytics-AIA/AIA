"""The pinned split and the preregistration (panel-grounded-respondents 7a).

Before any confirmation item is asked, everything that decides the verdict is fixed in one
immutable record, hashed over its canonical JSON (18.6.6's ``prereg_sha256``,
``holdout_protocol.py:23-28``):

- the item bank's and the eligible pool's hashes;
- the split: the eligible pool, near-duplicates removed, drawn by domain into a development set
  (:data:`DEVELOPMENT_SHARE`) and a confirmation set, under a recorded seed;
- the confirmation set's request blocks and what each block's respondents are not given;
- the arms, n, the seeds, the bootstrap;
- the pass criteria P1-P8 with their thresholds (:data:`THRESHOLDS`);
- the scoring code's version and the respondent system (its components and fingerprint),
  whose population version is the run's: there is no second place to name it.

:func:`draw_split` and :func:`preregister` refuse by name; neither repairs. A confirmation set
smaller than the minimums is refused, never run small.

Pure: stdlib only.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from ..evidence.validation import RESPONDENT_SYSTEM_COMPONENTS, respondent_system_fingerprint
from .bank import ItemBank, canonical_json
from .eligibility import HoldoutPopulation, ItemAssessment, scored_rows
from .leakage import BlockExclusion, ParsedColumns, association

__all__ = [
    "ARMS",
    "BLOCK_SIZE",
    "DEVELOPMENT_SHARE",
    "MIN_CONFIRMATION_DOMAINS",
    "MIN_CONFIRMATION_ITEMS",
    "MIN_ITEMS_PER_DOMAIN",
    "MODEL_ARMS",
    "NEAR_DUPLICATE",
    "PREREGISTRATION_VERSION",
    "THRESHOLDS",
    "DroppedDuplicate",
    "HoldoutRefused",
    "Preregistration",
    "Split",
    "confirmation_blocks",
    "draw_split",
    "preregister",
]

PREREGISTRATION_VERSION: Final = "aia-holdout-prereg-1"
#: 7a: 40 % of the eligible pool is the development set, the rest confirmation.
DEVELOPMENT_SHARE: Final = 0.40
#: 7a: two items at or above this association are one construct counted twice; one is kept.
NEAR_DUPLICATE: Final = 0.70
#: 7a: a confirmation set has at least 40 items, across at least 5 domains of at least 4.
MIN_CONFIRMATION_ITEMS: Final = 40
MIN_CONFIRMATION_DOMAINS: Final = 5
MIN_ITEMS_PER_DOMAIN: Final = 4
#: One request per block of at most 8 closed items, as fieldwork asks them.
BLOCK_SIZE: Final = 8
#: The arms (7a): two code baselines, then the model arms.
ARMS: Final = ("L0", "L1", "A", "B", "C", "D", "S")
MODEL_ARMS: Final = ("A", "B", "C", "D", "S")

#: P1-P8 (7a), fixed before any confirmation item is drawn. Percentage points, bits, a share,
#: or the family-wise alpha of the Holm-corrected comparisons.
THRESHOLDS: Final[Mapping[str, float]] = {
    "P1_mean_tvd_pp_max": 10.0,
    "P1_mean_tvd_upper_95_pp_max": 12.0,
    "P2_worst_domain_tvd_pp_max": 15.0,
    "P3_items_over_20pp_share_max": 0.10,
    "P4_P5_family_alpha": 0.05,
    "P6_subgroup_tvd_pp_max": 12.5,
    "P7_entropy_gap_bits_min": -0.25,
    "P8_replicate_sd_pp_max": 1.5,
}


class HoldoutRefused(ValueError):
    """The split or the preregistration cannot be made as asked. ``reason`` names the rule."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class DroppedDuplicate:
    """An eligible item left out of the pool as a near-duplicate of one kept."""

    field: str
    kept: str
    association: float


@dataclass(frozen=True, slots=True)
class Split:
    """The eligible pool, drawn once into development and confirmation."""

    seed: int
    pool: tuple[str, ...]
    development: tuple[str, ...]
    confirmation: tuple[str, ...]
    duplicates: tuple[DroppedDuplicate, ...]

    @property
    def pool_sha256(self) -> str:
        """The hash of the pool the split was drawn from."""
        return hashlib.sha256(canonical_json(sorted(self.pool))).hexdigest()


def _order(names: Sequence[str], seed: int, salt: str) -> list[str]:
    ordered = sorted(names)
    random.Random(f"{seed}:{salt}").shuffle(ordered)
    return ordered


def draw_split(
    population: HoldoutPopulation,
    bank: ItemBank,
    assessments: Sequence[ItemAssessment],
    seed: int,
) -> Split:
    """Draw the split from the eligible items.

    Near-duplicates are settled first, in a seeded order: an item whose association with one
    already kept reaches :data:`NEAR_DUPLICATE` (on the rows both are scored on) is dropped and
    recorded. The pool is then drawn within each domain, in a seeded order, the first
    :data:`DEVELOPMENT_SHARE` of it (rounded) into development. Every order is sorted before it
    is shuffled, so the split depends on the seed and the pool, never on the bank's order.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise HoldoutRefused("the split's seed must be an integer", reason="holdout_seed")
    eligible = [a.field for a in assessments if a.eligible]
    if not eligible:
        raise HoldoutRefused("no item of the bank is eligible", reason="holdout_pool_empty")
    kept: list[str] = []
    duplicates: list[DroppedDuplicate] = []
    columns = ParsedColumns(population)
    rows_of = {name: frozenset(scored_rows(population, bank.item(name))) for name in eligible}
    for name in _order(eligible, seed, "duplicates"):
        item = bank.item(name)
        clash: DroppedDuplicate | None = None
        for other in kept:
            shared = sorted(rows_of[name] & rows_of[other])
            value = association(population, item, other, shared, columns=columns)
            if value is not None and value >= NEAR_DUPLICATE:
                clash = DroppedDuplicate(name, other, round(value, 6))
                break
        if clash is None:
            kept.append(name)
        else:
            duplicates.append(clash)

    by_domain: dict[str, list[str]] = {}
    for name in kept:
        by_domain.setdefault(bank.item(name).domain, []).append(name)
    development: list[str] = []
    confirmation: list[str] = []
    for domain in sorted(by_domain):
        drawn = _order(by_domain[domain], seed, f"split:{domain}")
        cut = round(DEVELOPMENT_SHARE * len(drawn))
        development.extend(drawn[:cut])
        confirmation.extend(drawn[cut:])
    return Split(
        seed=seed,
        pool=tuple(sorted(kept)),
        development=tuple(sorted(development)),
        confirmation=tuple(sorted(confirmation)),
        duplicates=tuple(sorted(duplicates, key=lambda d: d.field)),
    )


def confirmation_blocks(bank: ItemBank, confirmation: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """The confirmation items as request blocks: by domain, at most :data:`BLOCK_SIZE` each."""
    by_domain: dict[str, list[str]] = {}
    for name in sorted(confirmation):
        by_domain.setdefault(bank.item(name).domain, []).append(name)
    blocks: list[tuple[str, ...]] = []
    for domain in sorted(by_domain):
        names = by_domain[domain]
        blocks.extend(tuple(names[i : i + BLOCK_SIZE]) for i in range(0, len(names), BLOCK_SIZE))
    return tuple(blocks)


def _check_minimums(bank: ItemBank, confirmation: Sequence[str]) -> None:
    counts: dict[str, int] = {}
    for name in confirmation:
        domain = bank.item(name).domain
        counts[domain] = counts.get(domain, 0) + 1
    full = sorted(d for d, c in counts.items() if c >= MIN_ITEMS_PER_DOMAIN)
    short = []
    if len(confirmation) < MIN_CONFIRMATION_ITEMS:
        short.append(f"{len(confirmation)} items < {MIN_CONFIRMATION_ITEMS}")
    if len(full) < MIN_CONFIRMATION_DOMAINS:
        short.append(
            f"{len(full)} domains with {MIN_ITEMS_PER_DOMAIN}+ items < {MIN_CONFIRMATION_DOMAINS}"
        )
    if short:
        raise HoldoutRefused(
            "the confirmation set is too small: " + "; ".join(short),
            reason="holdout_confirmation_short",
        )


def _seed(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HoldoutRefused(f"{name} must be an integer", reason="holdout_seed")
    return value


@dataclass(frozen=True, slots=True)
class Preregistration:
    """Everything that decides a confirmation run's verdict, fixed before its first call."""

    document: Mapping[str, Any]

    @property
    def sha256(self) -> str:
        """The record's identity: SHA-256 over its canonical JSON."""
        return hashlib.sha256(canonical_json(self.document)).hexdigest()

    @property
    def respondent_system_fingerprint(self) -> str:
        """The respondent system the confirmation run validates (arm D's)."""
        return str(self.document["respondent_system"]["fingerprint"])


def preregister(
    *,
    bank: ItemBank,
    split: Split,
    exclusions: Sequence[BlockExclusion],
    n: int,
    sample_seed: int,
    replicate_seeds: Sequence[int],
    bootstrap_seed: int,
    bootstrap_resamples: int,
    scoring_version: str,
    respondent_system: Mapping[str, str],
    cost_ceiling_usd: float,
) -> Preregistration:
    """Pin a confirmation run. Every block's exclusion must match the confirmation's blocks
    exactly, the respondent system must fingerprint, and the minimums must hold."""
    _check_minimums(bank, split.confirmation)
    blocks = confirmation_blocks(bank, split.confirmation)
    if tuple(e.items for e in exclusions) != blocks:
        raise HoldoutRefused(
            "the exclusions do not cover the confirmation's blocks exactly",
            reason="holdout_exclusions_mismatch",
        )
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise HoldoutRefused("n must be a positive integer", reason="holdout_n")
    seeds = tuple(_seed(s, "a replicate seed") for s in replicate_seeds)
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise HoldoutRefused("three distinct replicate seeds are required", reason="holdout_seed")
    resamples = _seed(bootstrap_resamples, "bootstrap_resamples")
    if resamples < 10_000:
        raise HoldoutRefused("the bootstrap needs at least 10,000 resamples", reason="holdout_n")
    if not (cost_ceiling_usd > 0):
        raise HoldoutRefused("the cost ceiling must be a positive amount", reason="holdout_cost")
    components = dict(respondent_system)
    try:
        fingerprint = respondent_system_fingerprint(components)
    except ValueError as exc:
        raise HoldoutRefused(str(exc), reason="holdout_system") from None
    document = {
        "preregistration_version": PREREGISTRATION_VERSION,
        "bank_sha256": bank.sha256,
        "pool_sha256": split.pool_sha256,
        "split": {
            "seed": split.seed,
            "development_share": DEVELOPMENT_SHARE,
            "near_duplicate": NEAR_DUPLICATE,
            "development": list(split.development),
            "confirmation": list(split.confirmation),
            "duplicates": [
                {"field": d.field, "kept": d.kept, "association": d.association}
                for d in split.duplicates
            ],
        },
        "blocks": [
            {
                "items": list(e.items),
                "excluded": [
                    {
                        "field": x.field,
                        "item": x.item,
                        "reason": x.reason.value,
                        "association": x.association,
                    }
                    for x in e.excluded
                ],
                "signals": list(e.signals),
            }
            for e in exclusions
        ],
        "arms": list(ARMS),
        "model_arms": list(MODEL_ARMS),
        "n": n,
        "sample_seed": _seed(sample_seed, "sample_seed"),
        "replicate_seeds": list(seeds),
        "bootstrap": {"seed": _seed(bootstrap_seed, "bootstrap_seed"), "resamples": resamples},
        "thresholds": dict(THRESHOLDS),
        "scoring_version": scoring_version,
        "population_version": components["population_version"],
        "respondent_system": {
            "components": {k: components[k] for k in RESPONDENT_SYSTEM_COMPONENTS},
            "fingerprint": fingerprint,
        },
        "cost_ceiling_usd": cost_ceiling_usd,
    }
    return Preregistration(document=document)
