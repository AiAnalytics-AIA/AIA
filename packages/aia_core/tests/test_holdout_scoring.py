"""Scoring a confirmation run: metrics, the Holm family, P1-P8 and the verdict (7d).

Every case is constructed so the right verdict is known: a system that answers as the people
did passes; one that knows the published marginal but not the person fails P4; one that always
gives the modal answer fails P7 (and P1).
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from aia_core.domain.holdout.scoring import (
    ArmRun,
    ItemTruth,
    Respondent,
    holm,
    item_metrics,
    verdict,
)

CODES = ("1", "2", "3", "4")
DOMAINS = ("family", "health", "work", "trust", "politics")
N = 400
RESAMPLES = 2000


@pytest.fixture(scope="module")
def world() -> tuple[list[Respondent], list[ItemTruth]]:
    """400 respondents in four cells of 100 donors; 40 items in 5 domains whose answers depend
    on the respondent's cell (so the right person matters), half of them person-level."""
    rng = random.Random(3)
    cells = ("muž|18-39", "muž|40+", "žena|18-39", "žena|40+")
    respondents = [Respondent(f"r{i}", f"d{i}", 0.5 + rng.random(), cells[i % 4]) for i in range(N)]
    truths = []
    for k in range(40):
        lean = {cell: rng.randrange(4) for cell in cells}
        answers = {
            r.respondent_id: CODES[lean[r.cell] if rng.random() < 0.7 else rng.randrange(4)]  # type: ignore[index]
            for r in respondents
        }
        truths.append(ItemTruth(f"q{k}", DOMAINS[k % 5], CODES, k % 2 == 0, answers))
    return respondents, truths


def _onehot(code: str, sure: float = 0.97) -> tuple[float, ...]:
    rest = (1 - sure) / (len(CODES) - 1)
    return tuple(sure if c == code else rest for c in CODES)


def _run(
    arm: str,
    rep: int,
    answer: Any,
    probs: Any,
    truths: list[ItemTruth],
    respondents: list[Respondent],
) -> ArmRun:
    answers = {}
    probabilities = {}
    for t in truths:
        for r in respondents:
            a = answer(t, r)
            answers[(t.item, r.respondent_id)] = a
            probabilities[(t.item, r.respondent_id)] = probs(t, r, a)
    return ArmRun(arm, rep, answers, probabilities)


def _arms(world: Any, d_answer: Any, d_probs: Any = None, seed: int = 0) -> dict[str, list[ArmRun]]:
    respondents, truths = world
    rng = random.Random(seed)
    order = [r.respondent_id for r in respondents]
    shifted = dict(zip(order, order[1:] + order[:1], strict=True))  # someone else's answers
    d_probs = d_probs or (lambda t, r, a: _onehot(a))
    uniform = tuple(0.25 for _ in CODES)
    return {
        "D": [_run("D", k, d_answer, d_probs, truths, respondents) for k in range(3)],
        "A": [
            _run(
                "A",
                k,
                lambda t, r: CODES[rng.randrange(4)],
                lambda t, r, a: uniform,
                truths,
                respondents,
            )
            for k in range(3)
        ],
        "S": [
            _run(
                "S",
                k,
                lambda t, r: t.answers[shifted[r.respondent_id]],
                lambda t, r, a: _onehot(a),
                truths,
                respondents,
            )
            for k in range(3)
        ],
    }


def _criteria(result: Any) -> dict[str, bool]:
    return {c.name: c.passed for c in result.criteria}


def test_a_system_that_answers_as_the_people_did_passes_every_criterion(world: Any) -> None:
    respondents, truths = world
    runs = _arms(world, lambda t, r: t.answers[r.respondent_id])
    result = verdict(truths, respondents, runs, bootstrap_seed=1, bootstrap_resamples=RESAMPLES)
    assert _criteria(result) == dict.fromkeys(_criteria(result), True), result.document()
    assert result.passed
    assert result.arms["D"]["tvd"] == pytest.approx(0.0)
    assert result.document()["verdict"] == "PASS"


def test_a_system_that_knows_the_marginal_but_not_the_person_fails_p4(world: Any) -> None:
    respondents, truths = world
    rng = random.Random(9)

    def recall(t: ItemTruth, r: Respondent) -> str:
        # Every respondent answered from the sample's own marginal: right in aggregate.
        return rng.choice(list(t.answers.values()))

    runs = _arms(world, recall)
    runs["A"] = [
        _run("A", k, recall, lambda t, r, a: (0.25,) * 4, truths, respondents) for k in range(3)
    ]
    result = verdict(truths, respondents, runs, bootstrap_seed=1, bootstrap_resamples=RESAMPLES)
    passed = _criteria(result)
    assert passed["P1_mean_tvd"]  # the marginal is right ...
    assert not passed["P4_beats_no_persona"]  # ... but no better than the question alone
    assert not result.passed


def test_a_system_that_always_gives_the_modal_answer_fails_p7(world: Any) -> None:
    respondents, truths = world

    def modal(t: ItemTruth, r: Respondent) -> str:
        values = list(t.answers.values())
        return max(CODES, key=values.count)

    result = verdict(
        truths, respondents, _arms(world, modal), bootstrap_seed=1, bootstrap_resamples=RESAMPLES
    )
    passed = _criteria(result)
    assert not passed["P7_entropy_gap"]
    assert not passed["P1_mean_tvd"]
    assert not result.passed


def test_a_criterion_that_cannot_be_evaluated_fails(world: Any) -> None:
    respondents, truths = world
    matched_only = [ItemTruth(t.item, t.domain, t.codes, False, t.answers) for t in truths]
    runs = _arms((respondents, matched_only), lambda t, r: t.answers[r.respondent_id])
    result = verdict(
        matched_only, respondents, runs, bootstrap_seed=1, bootstrap_resamples=RESAMPLES
    )
    p5 = next(c for c in result.criteria if c.name == "P5_beats_wrong_person")
    assert not p5.passed and p5.detail["D_beats_S_brier"] == {"unknown": True}
    assert not result.passed


def test_the_wrong_persons_answers_match_the_marginal_so_s_is_compared_on_people(
    world: Any,
) -> None:
    """S shows the same sample's personas permuted: its whole-sample marginal is the truth's but
    for the weights each respondent keeps, so comparing D with S on it would test almost nothing.
    That is why P5 compares them on subgroups and on the person-level score instead."""
    respondents, truths = world
    runs = _arms(world, lambda t, r: t.answers[r.respondent_id])
    s = item_metrics(truths, runs["S"], respondents)
    d = item_metrics(truths, runs["D"], respondents)
    whole = sum(m.tvd for m in s) / len(s)
    cells = sum(m.subgroup_tvd for m in s) / len(s)  # type: ignore[misc]
    assert whole < 5.0
    assert cells > 3 * whole
    assert min(sm.subgroup_tvd - dm.subgroup_tvd for sm, dm in zip(s, d, strict=True)) > 0  # type: ignore[operator]


def test_a_replicate_missing_an_answer_is_refused_never_scored(world: Any) -> None:
    respondents, truths = world
    run = _run(
        "D",
        0,
        lambda t, r: t.answers[r.respondent_id],
        lambda t, r, a: _onehot(a),
        truths,
        respondents,
    )
    del run.answers[(truths[0].item, respondents[0].respondent_id)]  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="lacks 1 answers"):
        item_metrics(truths, [run], respondents)


def test_holm_rejects_step_down_and_stops_at_the_first_failure() -> None:
    assert holm({"a": 0.01, "b": 0.02, "c": 0.04}, 0.05) == {"a": True, "b": True, "c": True}
    assert holm({"a": 0.01, "b": 0.03, "c": 0.04}, 0.05) == {"a": True, "b": False, "c": False}
    assert holm({"a": 0.02, "b": 0.001}, 0.05) == {"b": True, "a": True}
