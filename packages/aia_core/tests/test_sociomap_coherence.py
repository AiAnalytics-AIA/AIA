"""Coherences against the SOMECS help's worked example.

Documentation fixture: SOMECS Software Help (CZ), § Slovníček pojmů > Soudržnosti. The
4 x 4 matrix below is the help's own; its written coherences are
``(C, (D, (A, B)0.5)0.4)0.1``. The matrix holds one tie -- (A, B) and (B, D) both have a
lowest mutual relation of 0.5 -- and the help merges (A, B), which pins the tie rule.
"""

from __future__ import annotations

import pytest

from aia_core.domain.sociomap.coherence import alpha_cut, coherences, merge_classes
from aia_core.domain.sociomap.fuzzy import FuzzyMatrix, FuzzyMatrixError, FuzzySource

HELP = FuzzyMatrix.from_square(
    "ABCD",
    [
        [None, 0.5, 0.2, 0.4],
        [0.6, None, 0.1, 0.5],
        [0.6, 0.3, None, 0.1],
        [0.6, 0.5, 0.7, None],
    ],
    FuzzySource.ENTERED,
    ("QED-F1",),
)


def test_the_help_example_is_reproduced_exactly() -> None:
    tree = coherences(HELP)
    assert tree.written() == "(C, (D, (A, B)0.5)0.4)0.1"
    assert tree.level == 0.1
    assert tree.members == ("C", "D", "A", "B")


@pytest.mark.parametrize(
    ("alpha", "classes"),
    [
        (0.6, (("A",), ("B",), ("C",), ("D",))),
        (0.5, (("A", "B"), ("C",), ("D",))),
        (0.4, (("A", "B", "D"), ("C",))),
        (0.1, (("A", "B", "C", "D"),)),
        (0.0, (("A", "B", "C", "D"),)),
    ],
)
def test_alpha_cuts_are_the_classes_at_each_level(
    alpha: float, classes: tuple[tuple[str, ...], ...]
) -> None:
    assert alpha_cut(coherences(HELP), alpha) == classes


def test_zooming_keeps_each_directions_lowest_relation() -> None:
    zoomed = merge_classes(HELP, (("A", "B"), ("C",), ("D",)))
    assert zoomed.element_ids == ("(A, B)", "C", "D")
    assert zoomed.source is FuzzySource.MERGED
    assert zoomed.rules == ("QED-F1", "SOMECS-C2")
    assert zoomed.values == (
        (None, 0.1, 0.4),  # min(A->C .2, B->C .1); min(A->D .4, B->D .5)
        (0.3, None, 0.1),  # min(C->A .6, C->B .3)
        (0.5, 0.7, None),  # min(D->A .6, D->B .5); asymmetry kept
    )
    # The zoomed matrix keeps the structure above the cut; "(A, B)" is now one element.
    assert coherences(zoomed).written() == "(C, ((A, B), D)0.4)0.1"


def test_a_class_at_one_level_is_written_as_one_group() -> None:
    triangle = FuzzyMatrix.from_square(
        "ABCD",
        [
            [None, 0.5, 0.5, 0.1],
            [0.5, None, 0.5, 0.1],
            [0.5, 0.5, None, 0.2],
            [0.3, 0.3, 0.3, None],
        ],
        FuzzySource.ENTERED,
        ("QED-F1",),
    )
    assert coherences(triangle).written() == "(D, (A, B, C)0.5)0.1"


def test_two_elements_and_the_order_of_equal_groups() -> None:
    pair = FuzzyMatrix.from_square(
        "XY", [[None, 0.9], [0.4, None]], FuzzySource.ENTERED, ("QED-F1",)
    )
    assert coherences(pair).written() == "(X, Y)0.4"
    two_pairs = FuzzyMatrix.from_square(
        "ABCD",
        [
            [None, 0.9, 0.1, 0.1],
            [0.9, None, 0.1, 0.1],
            [0.1, 0.1, None, 0.8],
            [0.1, 0.1, 0.8, None],
        ],
        FuzzySource.ENTERED,
        ("QED-F1",),
    )
    assert coherences(two_pairs).written() == "((A, B)0.9, (C, D)0.8)0.1"


def test_merging_needs_a_partition_of_the_elements() -> None:
    for classes in [
        (("A", "B"), ("C",)),  # D missing
        (("A", "B"), ("B", "C"), ("D",)),  # B twice
        (("A", "B", "C", "D"), ()),  # an empty class
        (("A", "B", "C", "E"),),  # an unknown element
    ]:
        with pytest.raises(FuzzyMatrixError):
            merge_classes(HELP, classes)


def test_without_ties_the_grouping_ignores_element_order() -> None:
    no_ties = FuzzyMatrix.from_square(
        "ABCDE",
        [
            [None, 0.91, 0.12, 0.33, 0.24],
            [0.88, None, 0.15, 0.36, 0.27],
            [0.11, 0.14, None, 0.71, 0.45],
            [0.32, 0.37, 0.69, None, 0.52],
            [0.21, 0.26, 0.47, 0.55, None],
        ],
        FuzzySource.ENTERED,
        ("QED-F1",),
    )
    base = coherences(no_ties)
    for order in ([4, 3, 2, 1, 0], [2, 0, 4, 1, 3], [1, 4, 0, 3, 2]):
        shuffled = coherences(no_ties.permuted(order))
        for alpha in (0.9, 0.8, 0.6, 0.5, 0.3, 0.1):
            assert set(map(frozenset, alpha_cut(shuffled, alpha))) == set(
                map(frozenset, alpha_cut(base, alpha))
            )
    # With the help's tie, the order decides: (B, D) merges first once B and D lead.
    tied = coherences(HELP.permuted([1, 3, 0, 2]))
    assert tied.written() == "(C, (A, (B, D)0.5)0.4)0.1"
