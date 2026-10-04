"""Height vectors (register QED-W1, QED-W2, RTS-W3).

Source example: certification material p. 10 -- from Tab. 1 (p. 9), Anna received
2, 1, 3, 5, 2, 3 (16 / 6, printed 2.66), Tomáš 2.5, Karel 2.66; Anna gave 20 / 6 = 3.33,
Tomáš 2.83, Karel 2. Heights are computed on [0, 1] and mapped back to the 1-5 scale.
"""

from __future__ import annotations

import pytest

from aia_core.domain.sociomap.fuzzy import (
    MethodologyUndetermined,
    StormMissingPolicy,
    StormTransform,
    rts_people_matrix,
    rts_scale_answers,
    somecs_transform_storm,
)
from aia_core.domain.sociomap.heights import column_averages, object_average_answers, row_averages
from aia_core.domain.sociomap.models import RatingsMatrix

TEAM = ("Anna", "Tomáš", "Karel", "Marie", "Bára", "David", "Honza")
TAB_1 = (
    (None, 2, 3, 3, 4, 4, 4),
    (2, None, 4, 1, 2, 4, 4),
    (1, 3, None, 2, 1, 2, 3),
    (3, 2, 2, None, 3, 4, 3),
    (5, 2, 1, 4, None, 4, 2),
    (2, 3, 2, 4, 2, None, 4),
    (3, 3, 4, 4, 2, 4, None),
)


def on_scale(h: float) -> float:
    return 1 + 4 * h


def test_certification_table_1_averages() -> None:
    m = rts_people_matrix(TEAM, TAB_1, (1, 5))
    received = [on_scale(h) for h in column_averages(m)]
    given = [on_scale(h) for h in row_averages(m)]
    assert received[:3] == pytest.approx([16 / 6, 15 / 6, 16 / 6])  # printed 2.66, 2.5, 2.66
    assert [int(x * 100) / 100 for x in received[:3]] == [2.66, 2.5, 2.66]  # the print truncates
    assert given[:3] == pytest.approx([20 / 6, 17 / 6, 2.0])  # printed 3.33, 2.83, 2


def test_object_average_answers_rts_only_complete() -> None:
    answers = RatingsMatrix(
        respondent_ids=("p0", "p1", "p2"),
        object_ids=("X", "Y", "Z"),
        values=((1, 10, 4), (4, 10, 7), (7, 1, 10)),
    )
    assert object_average_answers(rts_scale_answers(answers, (1, 10))) == pytest.approx(
        (1 / 3, 2 / 3, 2 / 3)
    )
    gap = answers.model_copy(update={"values": ((1, 10, 4), (4, None, 7), (7, 1, 10))})
    with pytest.raises(MethodologyUndetermined, match="M5"):
        object_average_answers(rts_scale_answers(gap, (1, 10)))
    somecs = somecs_transform_storm(
        answers, StormTransform.SOMECS_WITHIN_ROW, StormMissingPolicy.KEEP_EMPTY
    )
    with pytest.raises(MethodologyUndetermined, match="M1"):
        object_average_answers(somecs)
