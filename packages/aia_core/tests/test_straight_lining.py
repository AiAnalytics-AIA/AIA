"""RQC1: one straight-liner rule, and every place that decided it held to it.

Plan ``run-qc-and-checkpoint`` chunk RQC1. The callers keep their own item sets and their own
reading of one answer (F-RQC1-1, the methodology owner's); what they share is the rule.
"""

from __future__ import annotations

import hashlib
import inspect
import itertools
import math
from typing import Any

import numpy as np
import pytest

from aia_core.domain import straight_lining
from aia_core.domain.sociomap.engine import _placeability
from aia_core.domain.sociomap.models import RatingsMatrix
from aia_core.domain.sociomap.relations import person_minmax
from aia_core.domain.sociomap.signed_off_inputs import centre
from aia_core.domain.sociomap.signed_off_respondents import place_respondents
from aia_core.domain.straight_lining import AnswerSpread, answer_spread


@pytest.mark.parametrize(
    ("answers", "spread"),
    [
        ([], AnswerSpread.NONE),
        ([None, None], AnswerSpread.NONE),
        ([4], AnswerSpread.ONE),
        ([None, 4, None], AnswerSpread.ONE),
        ([4, 4.0, None, 4], AnswerSpread.NO_SPREAD),
        ([1, 1, 1], AnswerSpread.NO_SPREAD),
        ([1, 1, 2], AnswerSpread.SPREAD),
        ([5, None, 1], AnswerSpread.SPREAD),
    ],
)
def test_a_respondents_answers_read_as_none_one_one_value_or_spread(
    answers: list[float | None], spread: AnswerSpread
) -> None:
    assert answer_spread(answers) is spread


def test_two_answers_are_the_same_only_when_equal_never_when_close() -> None:
    assert answer_spread([0.5, 0.5 + 1e-15]) is AnswerSpread.SPREAD


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_a_non_finite_answer_is_refused_never_read_as_missing(bad: float) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        answer_spread([1.0, bad, 1.0])


@pytest.mark.parametrize("bad", ["4", True, b"4"])
def test_an_answer_that_is_not_a_number_is_refused_never_parsed(bad: Any) -> None:
    with pytest.raises(TypeError, match="must be a number"):
        answer_spread([1.0, bad])


def test_the_rule_is_pinned_so_the_methodology_steps_that_read_it_are_re_read() -> None:
    """Metodika pins ``_placeability`` and ``person_minmax`` by their source, and their rule
    now lives here: a change to it is a change to the steps ``placeability`` (the reference
    map), ``f2_person_minmax`` and ``f11_not_placed``. Re-read them against it, then this pin."""
    source = inspect.getsource(straight_lining.answer_spread)
    assert hashlib.sha256(source.encode()).hexdigest() == ANSWER_SPREAD_SHA256


ANSWER_SPREAD_SHA256 = "e3a92bdb30c3c25e17765b8b5a0664475737c13d48a951a2b710548037b6dfa2"


def _units_straight_liner(row: list[float | None]) -> bool:
    """``qc.kontrola``'s per-row test (``qc.py:202-203``): ``nunique(axis=1) == 1``, the
    pandas count of distinct values with missing ones dropped, transcribed by hand over
    numeric rows (the unit's environment is not this one). It is not the unit's own run:
    ``evidence-integrity`` 2 captures ``qc.kontrola`` itself as its EXACT fixture."""
    return len({v for v in row if v is not None}) == 1


ROWS = [
    list(row)
    for size in range(0, 5)
    for row in itertools.product([None, 1.0, 2.0, 3.0], repeat=size)
]


@pytest.mark.parametrize("row", ROWS, ids=str)
def test_the_units_run_qc_is_one_or_no_spread(row: list[float | None]) -> None:
    """The unit counts a respondent who answered one scale as a straight-liner (F-RQC1-1);
    held to the transcription above, the unit's own run being ``evidence-integrity`` 2's."""
    assert _units_straight_liner(row) == (
        answer_spread(row) in (AnswerSpread.ONE, AnswerSpread.NO_SPREAD)
    )


@pytest.mark.parametrize("row", ROWS, ids=str)
def test_the_v2_engine_places_only_a_spread(row: list[float | None]) -> None:
    padded = tuple(row) + (None,) * max(0, 3 - len(row))  # a matrix holds three objects or more
    matrix = RatingsMatrix(
        respondent_ids=("r",),
        object_ids=tuple(f"o{i}" for i in range(len(padded))),
        values=(padded,),
    )
    excluded = _placeability(matrix, 3.0)
    assert ("r" not in excluded) == (answer_spread(row) is AnswerSpread.SPREAD)
    if answer_spread(row) is AnswerSpread.NO_SPREAD:
        assert "straight-liner" in excluded["r"]


@pytest.mark.parametrize("row", ROWS, ids=str)
def test_the_v3_rescaling_keeps_only_a_spread(row: list[float | None]) -> None:
    assert (person_minmax([row]).excluded == ()) == (answer_spread(row) is AnswerSpread.SPREAD)


@pytest.mark.parametrize(("low", "high"), [(1, 5), (1, 7), (0, 10), (1, 10), (0, 100)])
def test_the_signed_off_tolerance_agrees_on_rescaled_integer_scales(low: int, high: int) -> None:
    """``aia-sociomap-5`` reads a spread above 1e-12 on ratings rescaled to 0-1
    (``engine_v2``: ``(v - scale_min) / (scale_max - scale_min)``); it is signed off and not
    changed, so it is held to the rule here: on any integer scale the tolerance and exact
    equality decide alike, for ``centre`` and for ``place_respondents``."""
    span = high - low
    values = [None, *[(v - low) / span for v in range(low, high + 1)]]
    rng = np.random.default_rng(1)
    rows = [list(r) for r in itertools.product(values[:4], repeat=4)]
    # Every pair of scale points, both ends included.
    rows += [[a, b, a, None] for a in values[1:] for b in values[1:]]
    rows += [list(rng.choice(np.array(values[1:], float), size=4)) for _ in range(200)]
    rows += [[values[1]] * 4, [values[-1]] * 4, [values[2], None, values[2], values[2]]]
    ratings = np.array([[np.nan if v is None else float(v) for v in r] for r in rows], float)
    expected = [answer_spread(r) is AnswerSpread.SPREAD for r in rows]

    placed_by_centre = list(np.isfinite(centre(ratings)).any(axis=1))
    assert placed_by_centre == expected

    points = rng.normal(size=(ratings.shape[1], 2))
    placement = place_respondents(points, ratings, chance_level=0.05, min_ratings=2)
    assert [s != "NOT_PLACED" for s in placement.status] == expected
