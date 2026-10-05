"""The declared relationship matrix keeps every value as measured (AIA's own contract)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aia_core.domain.sociomap.declared import (
    DeclaredRelations,
    RelationScale,
    declared_from_correlations,
    declared_from_fuzzy,
)
from aia_core.domain.sociomap.fuzzy import (
    FuzzyMatrix,
    FuzzySource,
    rts_object_correlations,
    rts_scale_answers,
)
from aia_core.domain.sociomap.models import RatingsMatrix


def test_correlations_stay_signed_and_undefined_pairs_keep_their_reason() -> None:
    answers = RatingsMatrix(
        respondent_ids=("p0", "p1", "p2", "p3"),
        object_ids=("X", "Y", "Z", "W"),
        values=((1, 9, 5, 4), (4, 6, 5, 7), (7, 2, 5, 2), (9, 1, 5, 8)),
    )
    correlations = rts_object_correlations(rts_scale_answers(answers, (1, 10)))
    declared = declared_from_correlations(correlations)
    assert declared.scale is RelationScale.SIGNED_CORRELATION
    assert declared.values == correlations.r  # nothing clipped, shifted or filled
    assert declared.relation(0, 1) is not None and declared.relation(0, 1) < 0  # type: ignore[operator]
    assert declared.relation(0, 2) is None  # Z is constant
    assert ("X", "Z", "every answer equal for Z") in declared.undefined
    assert ("Z", "X", "every answer equal for Z") in declared.undefined
    assert [(a, b) for a, b, _ in declared.negative_pairs()] == [("X", "Y"), ("Y", "W")]
    assert declared.rules == correlations.rules and declared.is_symmetric()


def test_a_fuzzy_matrix_is_declared_as_it_is() -> None:
    m = FuzzyMatrix.from_square("AB", [[0, 0.2], [0.7, 0]], FuzzySource.ENTERED, ("QED-F1",))
    declared = declared_from_fuzzy(m)
    assert declared.values == m.values and declared.scale is RelationScale.FUZZY_0_1
    assert declared.source_fingerprint == m.fingerprint() and not declared.is_symmetric()


def test_the_contract_refuses_unnamed_gaps_and_values_off_the_scale() -> None:
    base = {
        "element_ids": ("A", "B"),
        "scale": RelationScale.FUZZY_0_1,
        "undefined": (),
        "source_fingerprint": "f",
        "rules": ("QED-F1",),
    }
    for values, undefined, why in [
        (((None, None), (0.5, None)), (), "without a reason"),
        (((None, 1.5), (0.5, None)), (), "outside"),
        (((None, 0.5), (0.5, None)), (("A", "B", "x"),), "named undefined"),
        (((0.1, 0.5), (0.5, None)), (), "diagonal"),
    ]:
        with pytest.raises(ValidationError, match=why):
            DeclaredRelations(**{**base, "values": values, "undefined": undefined})
    with pytest.raises(ValidationError, match="outside"):
        DeclaredRelations(**{**base, "values": ((None, -0.5), (0.5, None))})
    DeclaredRelations(
        **{**base, "scale": RelationScale.SIGNED_CORRELATION, "values": ((None, -0.5), (0.5, None))}
    )
