"""What a respondent is not given while holdout items are asked (7b, the leakage rule)."""

from __future__ import annotations

import json
import random
from typing import Any

import pytest

from aia_core.domain.holdout.bank import BANK_VERSION, HoldoutItem, read_item_bank
from aia_core.domain.holdout.leakage import (
    ASSOCIATION_THRESHOLD,
    CatalogSignal,
    ExclusionReason,
    association,
    block_exclusion,
)

N = 1200


def _item(
    field: str, *, ordinal: bool = True, codes: tuple[str, ...] = ("1", "2", "3", "4")
) -> HoldoutItem:
    raw = {
        "bank_version": BANK_VERSION,
        "items": [
            {
                "field": field,
                "survey": "ISSP_2022_CZ",
                "domain": "family_health",
                "wording": "Otázka?",
                "options": [{"code": c, "label": c} for c in codes],
                "measured_ages": None,
                "ordinal": ordinal,
                "source": {
                    "url": "https://example.org/q.pdf",
                    "sha256": "b" * 64,
                    "page": "1",
                    "item_id": "Q1",
                },
            }
        ],
    }
    return read_item_bank(json.dumps(raw).encode()).item(field)


@pytest.fixture
def world(holdout_population: Any) -> Any:
    """An item, a matched-block sibling, a field that tracks it, one that does not, a nominal
    field that tracks it, a constant field and one never answered where the item is."""
    rng = random.Random(7)
    item = [rng.randint(1, 4) for _ in range(N)]
    tracks = [min(4, max(1, v + rng.choice((-1, 0, 0, 0, 1)))) for v in item]
    independent = [rng.randint(1, 5) for _ in range(N)]
    nominal = ["sever" if v <= 2 else "jih" for v in item]

    def cells(values: list[Any]) -> tuple[str | None, ...]:
        return tuple(str(v) for v in values)

    return holdout_population(
        {
            "q_item": ("family_health", "MATCHED_WHOLE_BLOCK", cells(item)),
            "q_sibling": ("family_health", "MATCHED_WHOLE_BLOCK", cells(independent)),
            "core_tracks": ("core", "CANONICAL_CORE", cells(tracks)),
            "core_independent": ("core", "CANONICAL_CORE", cells(independent)),
            "core_nominal": ("core", "CANONICAL_CORE", cells(nominal)),
            "core_constant": ("core", "CANONICAL_CORE", cells(["1"] * N)),
            "core_never": ("core", "CANONICAL_CORE", tuple(None for _ in range(N))),
        }
    )


PERSONA = (
    "q_sibling",
    "core_tracks",
    "core_independent",
    "core_nominal",
    "core_constant",
    "core_never",
    "not_in_population",
)


def _reasons(exclusion: Any) -> dict[str, ExclusionReason]:
    return {e.field: e.reason for e in exclusion.excluded}


def test_the_item_its_matched_block_and_what_tracks_it_are_left_out(world: Any) -> None:
    exclusion = block_exclusion(world, [_item("q_item")], PERSONA)
    reasons = _reasons(exclusion)
    assert reasons["q_item"] is ExclusionReason.ITEM
    # The sibling is independent of the item, but one donor answered both: out regardless.
    assert reasons["q_sibling"] is ExclusionReason.MATCHED_BLOCK
    assert reasons["core_tracks"] is ExclusionReason.ASSOCIATED
    assert reasons["core_nominal"] is ExclusionReason.ASSOCIATED
    assert "core_independent" not in reasons
    assert "not_in_population" not in reasons


def test_an_association_that_cannot_be_computed_leaves_the_field_out(world: Any) -> None:
    reasons = _reasons(block_exclusion(world, [_item("q_item")], PERSONA))
    assert reasons["core_constant"] is ExclusionReason.ASSOCIATION_UNKNOWN
    assert reasons["core_never"] is ExclusionReason.ASSOCIATION_UNKNOWN


def test_the_association_is_recorded_and_reaches_the_threshold(world: Any) -> None:
    exclusion = block_exclusion(world, [_item("q_item")], PERSONA)
    tracked = next(e for e in exclusion.excluded if e.field == "core_tracks")
    assert tracked.association is not None and tracked.association >= ASSOCIATION_THRESHOLD
    item = _item("q_item")
    rows = tuple(range(N))
    independent = association(world, item, "core_independent", rows)
    assert independent is not None and independent < ASSOCIATION_THRESHOLD


def test_a_nominal_item_is_measured_by_cramers_v_never_a_correlation(world: Any) -> None:
    item = _item("q_item", ordinal=False)
    rows = tuple(range(N))
    v = association(world, item, "core_tracks", rows)
    r = association(world, _item("q_item"), "core_tracks", rows)
    assert v is not None and r is not None and v != r


def test_a_signal_on_a_left_out_column_or_an_items_concept_is_left_out(world: Any) -> None:
    signals = (
        CatalogSignal("core_tracks", "rodina"),
        CatalogSignal("q_item", "postoj_k_rodine"),
        CatalogSignal("core_independent", "postoj_k_rodine"),
        CatalogSignal("core_independent_2", "zdravi"),
    )
    exclusion = block_exclusion(world, [_item("q_item")], PERSONA, signals)
    assert exclusion.signals == ("core_independent", "core_tracks", "q_item")
    assert _reasons(exclusion)["core_independent"] is ExclusionReason.SIGNAL_CONCEPT
    assert "core_independent_2" not in exclusion.fields


def test_a_blocks_exclusion_is_the_union_over_its_items_and_is_deterministic(world: Any) -> None:
    a = block_exclusion(
        world,
        [_item("q_item"), _item("core_independent", codes=("1", "2", "3", "4", "5"))],
        PERSONA,
    )
    b = block_exclusion(
        world,
        [_item("q_item"), _item("core_independent", codes=("1", "2", "3", "4", "5"))],
        PERSONA,
    )
    assert a == b
    assert {"q_item", "core_independent", "q_sibling", "core_tracks"} <= a.fields


def test_an_ordinal_item_against_a_field_without_numbers_is_measured_by_cramers_v(
    world: Any,
) -> None:
    rows = tuple(range(N))
    ordinal = association(world, _item("q_item"), "core_nominal", rows)
    nominal = association(world, _item("q_item", ordinal=False), "core_nominal", rows)
    assert ordinal is not None and ordinal == nominal
