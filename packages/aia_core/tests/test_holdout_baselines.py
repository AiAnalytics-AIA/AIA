"""The validation's code baselines L0 and L1 (7d)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aia_core.domain.holdout.bank import BANK_VERSION, HoldoutItem, read_item_bank
from aia_core.domain.holdout.baselines import (
    baseline_metrics,
    l0_predictions,
    l1_predictions,
)
from aia_core.domain.holdout.scoring import ItemTruth, Respondent

N = 1200


def _item(field: str = "q") -> HoldoutItem:
    raw = {
        "bank_version": BANK_VERSION,
        "items": [
            {
                "field": field,
                "survey": "ISSP_2022_CZ",
                "domain": "family",
                "wording": "Otázka?",
                "options": [{"code": c, "label": c} for c in ("1", "2")],
                "measured_ages": None,
                "ordinal": False,
                "source": {
                    "url": "https://example.org/q.pdf",
                    "sha256": "f" * 64,
                    "page": "1",
                    "item_id": "Q",
                },
            }
        ],
    }
    return read_item_bank(json.dumps(raw).encode()).item(field)


@pytest.fixture(scope="module")
def world(holdout_population: Any) -> Any:
    """Men answer 1, women answer 2, each row its own donor; one Prague graduate is the only
    person in their cell who answers against their sex."""

    def cells(f: Any) -> tuple[str | None, ...]:
        return tuple(f(i) for i in range(N))

    sex = cells(lambda i: "muž" if i % 2 == 0 else "žena")
    answer = list(cells(lambda i: "1" if i % 2 == 0 else "2"))
    answer[0] = "2"  # row 0, a man, answers as women do
    return holdout_population(
        {
            "pohlavi": ("core", "POPULATION_ANCHOR", sex),
            "vek_skupina": (
                "core",
                "POPULATION_ANCHOR",
                cells(lambda i: ("18-39", "40+")[i % 4 // 2]),
            ),
            "vzdelani": ("core", "POPULATION_ANCHOR", cells(lambda i: ("ZŠ", "SŠ", "VŠ")[i % 3])),
            "kraj": ("core", "POPULATION_ANCHOR", cells(lambda i: ("Praha", "Brno")[i % 5 // 3])),
            "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", cells(lambda i: f"d{i}")),
            "q": ("core", "CANONICAL_CORE", tuple(answer)),
        }
    )


def test_l0_predicts_the_population_marginal_for_everyone(world: Any) -> None:
    item = _item()
    predictions = l0_predictions(world, [item], {"a": 0, "b": 1})
    share_1 = sum(1 for v in world.column("q") if v == "1") / N
    assert predictions[("q", "a")] == predictions[("q", "b")]
    assert predictions[("q", "a")][0] == pytest.approx(share_1)


def test_l1_predicts_the_cell_and_never_the_respondent_themselves(world: Any) -> None:
    item = _item()
    predictions = l1_predictions(world, [item], {"man": 0, "woman": 1})
    # Row 0 is the one man answering 2; left out, his cell says 1 with certainty.
    assert predictions[("q", "man")] == pytest.approx((1.0, 0.0))
    assert predictions[("q", "woman")] == pytest.approx((0.0, 1.0))


def test_a_small_cell_backs_off_to_a_coarser_one(holdout_population: Any) -> None:
    n = 400

    def cells(f: Any) -> tuple[str | None, ...]:
        return tuple(f(i) for i in range(n))

    population = holdout_population(
        {
            "pohlavi": ("core", "POPULATION_ANCHOR", cells(lambda i: "muž")),
            "vek_skupina": ("core", "POPULATION_ANCHOR", cells(lambda i: "18-39")),
            "vzdelani": ("core", "POPULATION_ANCHOR", cells(lambda i: "VŠ" if i < 5 else "SŠ")),
            "kraj": ("core", "POPULATION_ANCHOR", cells(lambda i: "Praha")),
            "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", cells(lambda i: f"d{i}")),
            "q": ("core", "CANONICAL_CORE", cells(lambda i: "1" if i < 5 else "2")),
        }
    )
    # Row 0's cell has 4 other donors, all answering 1: too few, so it backs off to the
    # whole men 18-39 group, mostly answering 2.
    (prediction,) = l1_predictions(population, [_item()], {"r": 0}).values()
    assert prediction[1] > 0.9


def test_perfect_predictions_score_zero_and_a_flat_one_does_not(world: Any) -> None:
    item = _item()
    respondents = [
        Respondent(f"r{i}", f"d{i}", 1.0, world.column("pohlavi")[i]) for i in range(200)
    ]
    truth = ItemTruth(
        "q", "family", item.codes, True, {f"r{i}": world.column("q")[i] for i in range(200)}
    )  # type: ignore[misc]
    perfect = {
        ("q", r.respondent_id): (1.0, 0.0) if truth.answers[r.respondent_id] == "1" else (0.0, 1.0)
        for r in respondents
    }
    (m,) = baseline_metrics([truth], respondents, perfect)
    assert m.tvd == pytest.approx(0.0) and m.brier == pytest.approx(0.0)
    flat = dict.fromkeys(perfect, (0.5, 0.5))
    (f,) = baseline_metrics([truth], respondents, flat)
    assert f.brier == pytest.approx(0.5)
    assert f.subgroup_tvd is not None and f.subgroup_tvd > 40
