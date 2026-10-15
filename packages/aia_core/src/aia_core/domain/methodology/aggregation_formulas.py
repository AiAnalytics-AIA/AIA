"""Aggregation's estimators as editable slots, each with the expression the aggregate computes.

ADR 0023 decision 4; plan ``methodology-tab.md`` G2b. Each expression is written the way
``research_aggregate`` computes, operation for operation, so it gives the aggregate's exact
bits: the aggregate sums with ``math.fsum``, as the formula language's ``sum`` does.
``test_methodology_aggregation_formulas.py`` proves it the strong way: every aggregate fixture
computed with every slot replaced by its own built-in expression is identical, value for value,
to the aggregate computed by the code.

The slots are the aggregate's estimators. What is an algorithm rather than a formula stays code
and has no slot: weight cleaning (a substitution), the weighted median (an interpolation over
sorted answers), the donor resampling and the linear quantile of the replicates.

Pure: stdlib only.
"""

from __future__ import annotations

from typing import Final

from ..research_aggregate import KISH, MEAN, SHARE, TOP_BOX, VARIANCE
from .catalogue import BuiltinFormula
from .expressions import Property, PropertyKind, Slot, Variable

__all__ = ["AGGREGATION_FORMULAS"]

_P: Final = PropertyKind

# Vector samples of one length, so every point of the grid pairs answers with weights.
_W = Variable(
    "w",
    "w",
    "váhy respondentů, kteří odpověděli",
    ((1.0, 1.0, 1.0), (0.5, 2.0, 1.0), (1e-3, 5.0, 2.0)),
    vector=True,
)
_X = Variable(
    "x",
    "x",
    "odpovědi na škále",
    ((1.0, 2.0, 3.0), (2.0, 3.0, 4.0), (5.0, 5.0, 6.0)),  # each at least the one before
    "body škály",
    vector=True,
)

_MEAN = Slot(
    id=MEAN,
    title_cs="Vážený průměr",
    variables=(_X, _W),
    properties=(
        Property(_P.NON_DECREASING_IN, variable="x", description_cs="vyšší odpovědi, vyšší průměr"),
        Property(
            _P.EQUALS_AT,
            at={"x": (5.0, 5.0, 5.0), "w": (0.5, 2.0, 1.0)},
            value=5.0,
            description_cs="průměr stejných odpovědí je ta odpověď",
        ),
    ),
)
_SHARE = Slot(
    id=SHARE,
    title_cs="Vážený podíl odpovědi",
    variables=(
        Variable(
            "hit",
            r"[x_k = c]",
            "1, když respondent zvolil tuto možnost, jinak 0",
            ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (1.0, 1.0, 1.0)),
            vector=True,
        ),
        _W,
    ),
    properties=(
        Property(_P.WITHIN, lo=0.0, hi=100.0, description_cs="podíl leží v [0, 100] %"),
        Property(_P.NON_DECREASING_IN, variable="hit"),
        Property(_P.EQUALS_AT, at={"hit": (1.0, 1.0, 1.0), "w": (0.5, 2.0, 1.0)}, value=100.0),
    ),
)
_TOP_BOX = Slot(
    id=TOP_BOX,
    title_cs="Patří odpověď do top boxu?",
    variables=(
        Variable("x", "x_k", "odpověď na škále", (1.0, 3.0, 4.0, 5.0), "body škály"),
        Variable("top", r"\max", "horní konec škály", (5.0, 10.0), "body škály"),
        Variable("b", "b", "šířka top boxu", (1.0, 2.0, 3.0), "bodů škály"),
    ),
    properties=(
        Property(_P.WITHIN, lo=0.0, hi=1.0, description_cs="ano (1) nebo ne (0)"),
        Property(_P.NON_DECREASING_IN, variable="x"),
        Property(_P.EQUALS_AT, at={"x": 5.0, "top": 5.0, "b": 1.0}, value=1.0),
    ),
)
_KISH = Slot(
    id=KISH,
    title_cs="Kishovo efektivní n",
    variables=(_W,),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(_P.AT_MOST_VARIABLE, variable="w", description_cs="nejvýš počet odpovědí"),
        Property(_P.EQUALS_AT, at={"w": (1.0, 1.0, 1.0)}, value=3.0),
    ),
)
_VARIANCE = Slot(
    id=VARIANCE,
    title_cs="Vážený rozptyl (ddof 0)",
    variables=(_X, _W),
    properties=(
        Property(_P.NON_NEGATIVE),
        Property(
            _P.EQUALS_AT,
            at={"x": (5.0, 5.0, 5.0), "w": (0.5, 2.0, 1.0)},
            value=0.0,
            description_cs="stejné odpovědi nemají rozptyl",
        ),
    ),
)

# What each slot does not cover, as research_aggregate keeps it (the function beside each).
_KEPT_ROWS: Final = (
    "Nevyplněné odpovědi se vynechají; neplatnou váhu (chybí, nula, záporná) kód předem nahradí "
    "mediánem platných vah, a když žádná platná není, dá všem váhu 1."
)
_KEPT_KISH: Final = (
    # aggregate_question -> donor_support -> kish_effective_n(clean_weights(...))
    _KEPT_ROWS,
    "Bez kladné váhy je n 0 a výraz se nepoužije.",
    "Efektivní n otázky kód dál omezí počtem dárců: nejvýš Kishovo n krát podíl dárců na "
    "odpovědích a nejvýš počet dárců. O stavu podpory a potlačení rozhoduje pravidlo podpory.",
)
_KEPT_SHARE: Final = (
    # bootstrap_weighted_distribution; aggregate_question (typ multi)
    _KEPT_ROWS,
    "Bez kladné váhy je podíl 0 a výraz se nepoužije.",
    "U otázky s jednou odpovědí počítá výraz bod i každý bootstrapový vzorek; převzorkování po "
    "dárcích a meze intervalu z kvantilů počítá kód.",
    "U otázky s více odpověďmi počítá výraz jen bod; interval jde přes vážený průměr.",
    "Zaokrouhlení na 0,1 % provede kód.",
)
_KEPT_MEAN: Final = (
    # bootstrap_weighted_mean
    _KEPT_ROWS,
    "Pod dvěma platnými odpověďmi průměr ani interval není; s jediným dárcem je interval bod sám.",
    "Výraz počítá bod i každý bootstrapový vzorek (váhy vynásobené počtem tažení dárce); "
    "převzorkování po dárcích a meze intervalu z kvantilů počítá kód.",
    "Tentýž výraz dává i podíl top boxu a intervaly u otázek s více odpověďmi (průměr jedniček "
    "a nul).",
    "Zaokrouhlení na dvě desetinná místa provede kód.",
)
_KEPT_VARIANCE: Final = (
    # weighted_variance
    _KEPT_ROWS,
    "Pod dvěma platnými odpověďmi rozptyl není a výraz se nepoužije.",
    "Směrodatnou odchylku jako odmocninu z výsledku a její zaokrouhlení počítá kód.",
)
_KEPT_TOP_BOX: Final = (
    # aggregate_question (typ skala)
    "Jen u otázek na škále; horní konec bere kód z otázky a šířku top boxu z metodiky.",
    "Podíl top boxu a jeho interval počítá vážený průměr z těchto jedniček a nul.",
)

AGGREGATION_FORMULAS: Final[tuple[BuiltinFormula, ...]] = (
    BuiltinFormula("kish", _KISH, "sum(w) ** 2 / sum(w * w)", kept_cs=_KEPT_KISH),
    BuiltinFormula("share", _SHARE, "100 * sum(w * hit) / sum(w)", kept_cs=_KEPT_SHARE),
    BuiltinFormula("mean", _MEAN, "sum(w * x) / sum(w)", kept_cs=_KEPT_MEAN),
    BuiltinFormula(
        "sd",
        _VARIANCE,
        "sum(w * (x - sum(w * x) / sum(w)) ** 2) / sum(w)",
        "Směrodatná odchylka je odmocnina z rozptylu.",
        kept_cs=_KEPT_VARIANCE,
    ),
    BuiltinFormula("top_box", _TOP_BOX, "x >= top - (b - 1)", kept_cs=_KEPT_TOP_BOX),
)
