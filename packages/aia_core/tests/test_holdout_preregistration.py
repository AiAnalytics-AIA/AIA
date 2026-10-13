"""The pinned split and the preregistration (7b)."""

from __future__ import annotations

import json
import random
from typing import Any

import pytest

from aia_core.domain.holdout.bank import BANK_VERSION, ItemBank, read_item_bank
from aia_core.domain.holdout.eligibility import assess_bank
from aia_core.domain.holdout.leakage import block_exclusion
from aia_core.domain.holdout.preregistration import (
    BLOCK_SIZE,
    DEVELOPMENT_SHARE,
    MIN_CONFIRMATION_ITEMS,
    THRESHOLDS,
    HoldoutRefused,
    confirmation_blocks,
    draw_split,
    preregister,
)

N = 700
DOMAINS = ("family", "health", "work", "trust", "politics", "law", "network")
SYSTEM = {
    "respondent_prompt_sha256": "c" * 64,
    "persona_builder": "panel-persona-1/profile-1",
    "persona_mode": "calibrated->core (no active profile)",
    "sampler_version": "sampler-1",
    "population_version": "pv_live",
    "model_binding": "bedrock/claude/bedrock-eu-primary",
    "response_process_version": "behavior-1/facts-1",
}


def _raw_item(field: str, domain: str) -> dict[str, Any]:
    return {
        "field": field,
        "survey": "ISSP_2022_CZ",
        "domain": domain,
        "wording": f"{field}?",
        "options": [{"code": c, "label": c} for c in ("1", "2", "3", "4")],
        "measured_ages": None,
        "ordinal": True,
        "source": {
            "url": "https://example.org/q.pdf",
            "sha256": "d" * 64,
            "page": "1",
            "item_id": field,
        },
    }


@pytest.fixture(scope="module")
def world(holdout_population: Any) -> tuple[Any, ItemBank]:
    """Seven domains of eleven independent items, one item that duplicates another, and a
    persona field."""
    rng = random.Random(11)
    spec: dict[str, Any] = {}
    raw = []
    for domain in DOMAINS:
        spec[f"_donor_{domain}_id"] = (
            "provenance",
            "PROVENANCE_OR_CORE",
            tuple(f"{domain}{i % 650}" for i in range(N)),
        )
        for k in range(11):
            name = f"{domain}_{k}"
            spec[name] = (
                domain,
                "MATCHED_WHOLE_BLOCK",
                tuple(str(rng.randint(1, 4)) for _ in range(N)),
            )
            raw.append(_raw_item(name, domain))
    spec["family_dup"] = ("family", "MATCHED_WHOLE_BLOCK", spec["family_0"][2])
    raw.append(_raw_item("family_dup", "family"))
    spec["persona_income"] = (
        "core",
        "CANONICAL_CORE",
        tuple(str(rng.randint(1, 10)) for _ in range(N)),
    )
    bank = read_item_bank(json.dumps({"bank_version": BANK_VERSION, "items": raw}).encode())
    return holdout_population(spec), bank


_SPLITS: dict[tuple[int, int], Any] = {}


def _split(world: tuple[Any, ItemBank], seed: int = 20261013) -> Any:
    """The split of ``world`` under ``seed``; drawn once per world and seed (it is pure)."""
    key = (id(world), seed)
    if key not in _SPLITS:
        population, bank = world
        _SPLITS[key] = draw_split(population, bank, assess_bank(population, bank), seed)
    return _SPLITS[key]


def test_a_near_duplicate_is_dropped_and_recorded_never_counted_twice(world: Any) -> None:
    split = _split(world)
    assert len(split.duplicates) == 1
    (dup,) = split.duplicates
    assert {dup.field, dup.kept} == {"family_0", "family_dup"}
    assert dup.association == pytest.approx(1.0)
    assert dup.field not in split.pool


def test_the_split_is_by_domain_disjoint_and_moves_only_with_the_seed(world: Any) -> None:
    split = _split(world)
    assert not set(split.development) & set(split.confirmation)
    assert set(split.development) | set(split.confirmation) == set(split.pool)
    _, bank = world
    for domain in DOMAINS:
        pool = [f for f in split.pool if bank.item(f).domain == domain]
        dev = [f for f in split.development if bank.item(f).domain == domain]
        assert len(dev) == round(DEVELOPMENT_SHARE * len(pool))
    population, bank = world
    again = draw_split(population, bank, assess_bank(population, bank), 20261013)
    assert again == split
    assert _split(world, seed=1).confirmation != split.confirmation


def test_the_split_does_not_depend_on_the_banks_order(world: Any) -> None:
    population, bank = world
    reordered = ItemBank(items=tuple(reversed(bank.items)), sha256=bank.sha256)
    split = draw_split(population, reordered, assess_bank(population, reordered), 20261013)
    assert split == _split(world)


def test_blocks_are_by_domain_and_never_larger_than_a_request(world: Any) -> None:
    _, bank = world
    split = _split(world)
    blocks = confirmation_blocks(bank, split.confirmation)
    assert all(0 < len(b) <= BLOCK_SIZE for b in blocks)
    assert all(len({bank.item(f).domain for f in b}) == 1 for b in blocks)
    assert sorted(f for b in blocks for f in b) == sorted(split.confirmation)


def _prereg(world: Any, **overrides: Any) -> Any:
    population, bank = world
    split = _split(world)
    blocks = confirmation_blocks(bank, split.confirmation)
    exclusions = [
        block_exclusion(population, [bank.item(f) for f in b], ("persona_income",)) for b in blocks
    ]
    args: dict[str, Any] = {
        "bank": bank,
        "split": split,
        "exclusions": exclusions,
        "n": 600,
        "sample_seed": 1,
        "replicate_seeds": (11, 12, 13),
        "bootstrap_seed": 7,
        "bootstrap_resamples": 10_000,
        "scoring_version": "aia-holdout-scoring-1",
        "respondent_system": SYSTEM,
        "cost_ceiling_usd": 500.0,
    }
    args.update(overrides)
    return preregister(**args)


def test_a_preregistration_pins_everything_that_decides_the_verdict(world: Any) -> None:
    prereg = _prereg(world)
    document = prereg.document
    assert len(document["split"]["confirmation"]) >= MIN_CONFIRMATION_ITEMS
    assert document["thresholds"] == dict(THRESHOLDS)
    assert document["population_version"] == "pv_live"
    assert document["respondent_system"]["components"] == SYSTEM
    assert len(prereg.respondent_system_fingerprint) == 64
    assert all(b["excluded"] for b in document["blocks"])
    # Its identity is its content: the same inputs, the same hash; a seed moved, another.
    assert _prereg(world).sha256 == prereg.sha256
    assert _prereg(world, sample_seed=2).sha256 != prereg.sha256
    json.dumps(document)  # it is a JSON document, nothing else


def test_a_confirmation_set_below_the_minimums_is_refused_never_run_small(
    world: Any, holdout_population: Any
) -> None:
    population, bank = world
    small = ItemBank(
        items=tuple(i for i in bank.items if i.domain in DOMAINS[:4]), sha256=bank.sha256
    )
    split = draw_split(population, small, assess_bank(population, small), 3)
    with pytest.raises(HoldoutRefused) as refused:
        preregister(
            bank=small,
            split=split,
            exclusions=[],
            n=600,
            sample_seed=1,
            replicate_seeds=(1, 2, 3),
            bootstrap_seed=1,
            bootstrap_resamples=10_000,
            scoring_version="s",
            respondent_system=SYSTEM,
            cost_ceiling_usd=1.0,
        )
    assert refused.value.reason == "holdout_confirmation_short"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"exclusions": []}, "holdout_exclusions_mismatch"),
        ({"n": 0}, "holdout_n"),
        ({"replicate_seeds": (1, 1, 2)}, "holdout_seed"),
        ({"replicate_seeds": (1, 2)}, "holdout_seed"),
        ({"sample_seed": True}, "holdout_seed"),
        ({"bootstrap_resamples": 4000}, "holdout_n"),
        ({"cost_ceiling_usd": 0.0}, "holdout_cost"),
        ({"respondent_system": {**SYSTEM, "model_binding": " "}}, "holdout_system"),
        ({"respondent_system": {**SYSTEM, "extra": "x"}}, "holdout_system"),
    ],
)
def test_a_preregistration_that_cannot_be_made_as_asked_is_refused_by_name(
    world: Any, overrides: dict[str, Any], reason: str
) -> None:
    with pytest.raises(HoldoutRefused) as refused:
        _prereg(world, **overrides)
    assert refused.value.reason == reason


def test_no_eligible_item_and_a_seed_that_is_not_a_number_are_refused(world: Any) -> None:
    population, bank = world
    with pytest.raises(HoldoutRefused) as refused:
        draw_split(population, bank, (), 1)
    assert refused.value.reason == "holdout_pool_empty"
    with pytest.raises(HoldoutRefused):
        draw_split(population, bank, assess_bank(population, bank), "1")  # type: ignore[arg-type]
