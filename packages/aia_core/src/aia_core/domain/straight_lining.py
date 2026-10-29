"""A straight-liner: one rule for "this respondent's answers hold one value" (RQC1).

Plan ``run-qc-and-checkpoint`` chunk RQC1. Five functions in four places decided this on their
own; they now share :func:`answer_spread`, or are held to it by test:

- the unit's run QC (``legacy/npc-panel-18.6.6/app/qc.py:200-207``): ``nunique(axis=1) ==
  1`` over every scale question, missing answers dropped -- a respondent who answered one
  scale is a straight-liner there; ported by ``evidence-integrity`` chunk 2 over this rule;
- the Sociomap's v2 engine (``sociomap/engine.py`` ``_placeability``): fewer than two rated
  is its own reason, two or more rated with one value a straight-liner;
- the v3 rescaling (``sociomap/relations.py`` ``person_minmax``, audit F2): none rated or
  one value (one rated included) is excluded;
- ``aia-sociomap-5`` (``signed_off_inputs.centre``, ``signed_off_respondents.place_respondents``):
  a spread above ``1e-12``, signed off and ported as written, so not changed here; on ratings
  rescaled from an integer scale it agrees with this rule
  (``test_straight_lining.py::test_the_signed_off_tolerance_agrees_on_rescaled_integer_scales``).

What differs between them is not the rule but its scope -- which items a caller hands it --
and what the caller makes of one answer. Both stay each caller's own: whether they should
become one is the methodology owner's question (the plan's Findings, F-RQC1-1). The rule
itself is exact: two answers are the same when they are equal, never "close".
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from enum import StrEnum

__all__ = ["AnswerSpread", "answer_spread"]


class AnswerSpread(StrEnum):
    """What a respondent's answers over a set of items say about their spread."""

    NONE = "none"
    """No item answered."""
    ONE = "one"
    """Exactly one item answered: no spread to read, and no evidence of one value either."""
    NO_SPREAD = "no_spread"
    """Two or more items answered, every answer the same value."""
    SPREAD = "spread"
    """Two or more items answered, at least two answers different."""


def answer_spread(answers: Iterable[object]) -> AnswerSpread:
    """The spread of one respondent's answers; ``None`` is an item not answered.

    A non-finite answer is refused, never read as missing: a NaN is a defect upstream,
    and dropping it would count the respondent's spread over fewer items than they answered.
    An answer that is not a number (text, a boolean) is refused too, never parsed: ``"4"`` and
    ``"4.0"`` are one value as numbers and two as text, and which a caller meant is its own.
    """
    first: float | None = None
    count = 0
    differs = False
    for answer in answers:
        if answer is None:
            continue
        if isinstance(answer, bool) or not isinstance(answer, (int, float)):
            raise TypeError(f"an answer must be a number; got {type(answer).__name__}")
        value = float(answer)
        if not math.isfinite(value):
            raise ValueError(f"a non-finite answer ({answer!r}) has no spread to read")
        count += 1
        if first is None:
            first = value
        elif value != first:
            differs = True
    if count == 0:
        return AnswerSpread.NONE
    if count == 1:
        return AnswerSpread.ONE
    return AnswerSpread.SPREAD if differs else AnswerSpread.NO_SPREAD
