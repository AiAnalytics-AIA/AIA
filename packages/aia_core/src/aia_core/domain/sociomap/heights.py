"""Height vectors: the third dimension of a Sociomap, before any surface is drawn.

"The height of each person on the Sociomap is proportional to the chosen output variable"
(certification material p. 7). The documented sources of a height (evidence register):

* **column average** -- the average rating a person *received* (certification material
  p. 10, with worked numbers; RTS designs doc ``.column.average``, p. 14) -- QED-W1;
* **row average** -- the average rating a person *gave* (p. 10) -- QED-W2;
* **object average answer** -- for an object question, the average answer respondents gave
  each object (RTS ``.storm.average``, p. 17) -- RTS-W3.

The diagonal never enters an average: "diagonal is excluded and does not affect any
aggregation calculations" (RTS designs doc p. 18). Averages are taken on the ``[0, 1]``
values; a height on the question's own scale is ``low + (high - low) * h``, which is how the
tests check the certification material's printed figures.

Not here, each for a stated reason: SOMECS's "sum of STORM ratings" and "inverse column sum"
(help p. 58) are SOMECS rules, not RTS ones, and a sum equals ``n`` times a mean only on
complete data; the weighted "effectiveness" height has a formula QED has not published
(certification material p. 17, M13); how heights are rescaled for display (Cloud RTS
specification p. 28) belongs to the surface (plan chunk 4b).
"""

from __future__ import annotations

from .fuzzy import FuzzyMatrix, MethodologyUndetermined, NormalisedStorm, StormTransform

__all__ = ["column_averages", "object_average_answers", "row_averages"]


def column_averages(matrix: FuzzyMatrix) -> tuple[float, ...]:
    """The average relation each element received, diagonal excluded (QED-W1)."""
    n = matrix.size
    return tuple(sum(matrix.relation(r, s) for r in range(n) if r != s) / (n - 1) for s in range(n))


def row_averages(matrix: FuzzyMatrix) -> tuple[float, ...]:
    """The average relation each element gave, diagonal excluded (QED-W2)."""
    n = matrix.size
    return tuple(sum(matrix.relation(r, s) for s in range(n) if s != r) / (n - 1) for r in range(n))


def object_average_answers(answers: NormalisedStorm) -> tuple[float, ...]:
    """Each object's average answer (RTS-W3). RTS data only, and complete (M5)."""
    if answers.transform is not StormTransform.RTS_SCALE:
        raise MethodologyUndetermined(
            "M1", f"an RTS average answer over {answers.transform} answers is not documented"
        )
    if not answers.is_complete():
        raise MethodologyUndetermined("M5", "RTS averages are documented for complete answers")
    n = len(answers.subject_ids)
    return tuple(
        sum(row[j] or 0.0 for row in answers.values) / n for j in range(len(answers.object_ids))
    )
