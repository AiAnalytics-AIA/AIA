"""Coherences (soudržnosti): a fuzzy matrix's nested groups, by alpha-cuts.

SOMECS writes a matrix's structure in the syntax of alpha-cuts (Software Help, CZ,
§ Slovníček pojmů > Soudržnosti):

    "Select the group of elements (usually two) whose lowest mutual relation is the
    highest in the matrix. Merge them into one (wrap them in parentheses); toward the
    remaining elements the group keeps the lowest of the original relations. Repeat until
    one element remains."

The help's worked example (p. 11), a 4 x 4 matrix, gives ``(C, (D, (A, B)0.5)0.4)0.1``; the
tests reproduce it exactly (evidence register SOMECS-C1). It also decides the one tie in that
matrix: the pairs (A, B) and (B, D) both have a lowest mutual relation of 0.5, and the help
merges (A, B) -- the first pair in element order. That is the tie rule here (SOMECS-C1a,
inferred from one example). A consequence: with ties, the grouping depends on element order;
without ties it does not (``test_without_ties_the_grouping_ignores_element_order``).

The group levels are alpha-cuts: at any ``alpha``, the groups whose level is at least
``alpha`` are the classes of the matrix at that cut (:func:`alpha_cut`). SOMECS uses them
to "zoom" a large matrix down to about ten elements by merging close elements
(help pp. 25-26); :func:`merge_classes` is that merge, keeping each direction's lowest
original relation (SOMECS-C2; between two merged groups the minimum over all member pairs,
an extension the help does not state).

Written order follows the example: a group lists its smaller members first, and among
equals the one whose first element comes first in the matrix. Two nested groups at the
same level are one class at that cut, so they are written as one group (SOMECS-C1b,
proposed: the help has no such case).

Every result is a :class:`CoherenceTree`: the tree with the algorithm's name, the source
matrix's fingerprint and the rule ids that actually shaped it. SOMECS-C1a appears only when
a tie was decided, and each decision is kept (:class:`TieDecision`) with the pairs that
were level and the one taken; SOMECS-C1b appears only when two groups at one level were
written as one. A reader can therefore tell a grouping fixed by the data from one an
inferred or proposed rule decided.

Not here: the "HM correction" that trades H-Model accuracy for keeping coherent groups
close (§ HM Korekce); it belongs to the H-Model (plan chunk 6b).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .fuzzy import FuzzyMatrix, FuzzyMatrixError, FuzzySource

COHERENCE_ALGORITHM = "aia_coherence_complete_linkage_v1"

__all__ = [
    "COHERENCE_ALGORITHM",
    "Coherence",
    "CoherenceTree",
    "TieDecision",
    "alpha_cut",
    "coherences",
    "merge_classes",
]


@dataclass(frozen=True)
class Coherence:
    """One node of the coherence tree.

    A single element has ``element`` set, no ``children`` and no ``level``. A group has
    two or more ``children`` and the ``level`` at which they merged: the lowest mutual
    relation between its members.
    """

    element: str | None
    children: tuple[Coherence, ...]
    level: float | None
    first_index: int  # position of the group's earliest element in the matrix
    size: int

    @property
    def members(self) -> tuple[str, ...]:
        """Every element under this node, in written order."""
        if self.element is not None:
            return (self.element,)
        return tuple(member for child in self.children for member in child.members)

    def written(self) -> str:
        """The SOMECS syntax: ``(C, (D, (A, B)0.5)0.4)0.1``."""
        if self.element is not None:
            return self.element
        assert self.level is not None
        return "(" + ", ".join(child.written() for child in self.children) + f"){self.level:g}"


@dataclass(frozen=True)
class TieDecision:
    """One merge where more than one pair of groups shared the highest level (SOMECS-C1a).

    ``candidates`` are the tied pairs, each written as the members of its two groups;
    ``chosen`` is the pair merged: the first in element order. When candidates share a
    group (``candidates_overlap``), another order could have put different elements together
    at this level; when they do not, every order gives the same classes.
    """

    level: float
    candidates: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]
    chosen: tuple[tuple[str, ...], tuple[str, ...]]
    candidates_overlap: bool


@dataclass(frozen=True)
class CoherenceTree:
    """The coherence tree of one fuzzy matrix, with what made it."""

    root: Coherence
    element_ids: tuple[str, ...]
    algorithm: str
    matrix_fingerprint: str
    matrix_source: FuzzySource
    rules: tuple[str, ...]
    ties: tuple[TieDecision, ...]
    flattened_levels: tuple[float, ...]  # levels where groups were written as one (SOMECS-C1b)

    @property
    def members(self) -> tuple[str, ...]:
        return self.root.members

    @property
    def level(self) -> float | None:
        return self.root.level

    def written(self) -> str:
        return self.root.written()


def coherences(matrix: FuzzyMatrix) -> CoherenceTree:
    """The full coherence tree of a fuzzy matrix (complete linkage on mutual relations)."""
    ids = matrix.element_ids
    mutual = [
        [
            None if r == s else min(matrix.relation(r, s), matrix.relation(s, r))
            for s in range(len(ids))
        ]
        for r in range(len(ids))
    ]
    groups: list[tuple[Coherence, tuple[int, ...]]] = [
        (Coherence(element=e, children=(), level=None, first_index=i, size=1), (i,))
        for i, e in enumerate(ids)
    ]
    ties: list[TieDecision] = []
    flattened: list[float] = []
    while len(groups) > 1:
        best: tuple[int, int] | None = None
        best_level = 0.0
        level_of: dict[tuple[int, int], float] = {}
        for a in range(len(groups)):
            for b in range(a + 1, len(groups)):
                level = min(_cell(mutual, i, j) for i in groups[a][1] for j in groups[b][1])
                level_of[(a, b)] = level
                if best is None or level > best_level:
                    best, best_level = (a, b), level
        assert best is not None
        tied = [pair for pair, level in level_of.items() if level == best_level]
        if len(tied) > 1:
            ties.append(_tie(groups, tied, best, best_level))
        a, b = best
        node = _join(groups[a][0], groups[b][0], best_level)
        if best_level in (groups[a][0].level, groups[b][0].level):
            flattened.append(best_level)
        merged = (node, groups[a][1] + groups[b][1])
        groups = [*groups[:a], merged, *groups[a + 1 : b], *groups[b + 1 :]]
    rules = [*matrix.rules, "SOMECS-C1"]
    if ties:
        rules.append("SOMECS-C1a")
    if flattened:
        rules.append("SOMECS-C1b")
    return CoherenceTree(
        root=groups[0][0],
        element_ids=ids,
        algorithm=COHERENCE_ALGORITHM,
        matrix_fingerprint=matrix.fingerprint(),
        matrix_source=matrix.source,
        rules=tuple(rules),
        ties=tuple(ties),
        flattened_levels=tuple(flattened),
    )


def alpha_cut(tree: CoherenceTree, alpha: float) -> tuple[tuple[str, ...], ...]:
    """The classes at one alpha-cut: the largest groups whose level is at least ``alpha``.

    An element in no such group is a class of its own. Classes are ordered by their
    earliest element in the matrix, and so are the elements within each.
    """
    found: list[Coherence] = []

    def visit(node: Coherence) -> None:
        if node.element is not None or (node.level is not None and node.level >= alpha):
            found.append(node)
        else:
            for child in node.children:
                visit(child)

    visit(tree.root)
    order = _element_order(tree.root)
    return tuple(
        tuple(sorted(node.members, key=order.__getitem__))
        for node in sorted(found, key=lambda n: n.first_index)
    )


def merge_classes(matrix: FuzzyMatrix, classes: Sequence[Sequence[str]]) -> FuzzyMatrix:
    """Merge each class into one element ("zooming", § Matice > Zoomování).

    The relation of class ``G`` to class ``H`` is the lowest relation of any member of
    ``G`` to any member of ``H``, in that direction, as the help keeps "the lowest of the
    original relations". A merged class is named ``(A, B)``; a single element keeps its
    name. Every element must be in exactly one class.
    """
    index = {e: i for i, e in enumerate(matrix.element_ids)}
    seen: list[str] = [e for cls in classes for e in cls]
    if sorted(seen) != sorted(matrix.element_ids) or len(seen) != len(set(seen)):
        raise FuzzyMatrixError("classes must cover every element of the matrix exactly once")
    if any(not cls for cls in classes):
        raise FuzzyMatrixError("a class cannot be empty")
    members = [[index[e] for e in cls] for cls in classes]
    names = [cls[0] if len(cls) == 1 else "(" + ", ".join(cls) + ")" for cls in classes]
    rows = [
        [
            None if g == h else min(matrix.relation(i, j) for i in members[g] for j in members[h])
            for h in range(len(classes))
        ]
        for g in range(len(classes))
    ]
    return FuzzyMatrix.from_square(names, rows, FuzzySource.MERGED, (*matrix.rules, "SOMECS-C2"))


def _cell(mutual: list[list[float | None]], i: int, j: int) -> float:
    value = mutual[i][j]
    assert value is not None  # i != j: members of two distinct groups
    return value


def _tie(
    groups: list[tuple[Coherence, tuple[int, ...]]],
    tied: list[tuple[int, int]],
    chosen: tuple[int, int],
    level: float,
) -> TieDecision:
    def pair(p: tuple[int, int]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        return groups[p[0]][0].members, groups[p[1]][0].members

    used = [g for p in tied for g in p]
    return TieDecision(
        level=level,
        candidates=tuple(pair(p) for p in tied),
        chosen=pair(chosen),
        candidates_overlap=len(used) != len(set(used)),
    )


def _join(a: Coherence, b: Coherence, level: float) -> Coherence:
    children: list[Coherence] = []
    for node in (a, b):
        # Two groups at one level are one class at that cut: write them as one group.
        children.extend(node.children if node.level == level else (node,))
    children.sort(key=lambda node: (node.size, node.first_index))
    return Coherence(
        element=None,
        children=tuple(children),
        level=level,
        first_index=min(a.first_index, b.first_index),
        size=a.size + b.size,
    )


def _element_order(tree: Coherence) -> dict[str, int]:
    order: dict[str, int] = {}

    def visit(node: Coherence) -> None:
        if node.element is not None:
            order[node.element] = node.first_index
        for child in node.children:
            visit(child)

    visit(tree)
    return order
