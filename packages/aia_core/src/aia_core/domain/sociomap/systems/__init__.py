"""Sociomapa systémů: the statistics the methodologist decided on 24 Nov 2026 (SM10-SM18).

One module per decision, all pure numerical code (no I/O):

* :mod:`.importance` -- indicator height from a tested model's drop, else declared (SM10)
* :mod:`.future_scale` -- futures against real history, else declared, else own spread (SM11)
* :mod:`.months` -- the month test: BY, declared trend, Pyper-Peterman, 36 months, IAAFT (SM12)
* :mod:`.minimum_rows` -- each input's minimum from its planted-answer test (SM13)
* :mod:`.stability` -- uncertainty circles and the stability number (SM14)
* :mod:`.one_sided` -- symmetric layout input and tested arrows (SM15)
* :mod:`.coverage` -- Konkurence's weighted coverage (SM16)
* :mod:`.influence` -- Vlivy: raters, Krippendorff's alpha, total influence (SM17)
* :mod:`.register` -- the awaiting-approval label per input (SM18)

The plan is ``.planning/plans/sociomapa-systemu.md``; the decisions are on the AIA MVP Map's
Decisions tab (SM10-SM18).
"""

from .coverage import weighted_coverage
from .future_scale import DeclaredRange, ScaledFutures, scale_futures
from .importance import IndicatorHeight, declared_importance, permutation_importance
from .influence import (
    MIN_RATERS,
    InfluenceMap,
    TooFewRaters,
    influence_map,
    krippendorff_alpha,
    total_influence,
)
from .minimum_rows import (
    STARTING_MINIMUM,
    DeclaredRates,
    PlantedRun,
    RowsCheck,
    check_rows,
    minimum_rows,
)
from .months import (
    MIN_MONTHS,
    MonthPair,
    MonthRelations,
    TooFewMonths,
    benjamini_yekutieli,
    detrend,
    effective_months,
    iaaft,
    month_relations,
)
from .one_sided import Arrow, arrows_that_pass, symmetric_part
from .register import AWAITING_LABEL, InputStatus, input_status
from .stability import SHOW_CIRCLES_BY_DEFAULT, MapStability, map_stability

__all__ = [
    "AWAITING_LABEL",
    "MIN_MONTHS",
    "MIN_RATERS",
    "SHOW_CIRCLES_BY_DEFAULT",
    "STARTING_MINIMUM",
    "Arrow",
    "DeclaredRange",
    "DeclaredRates",
    "IndicatorHeight",
    "InfluenceMap",
    "InputStatus",
    "MapStability",
    "MonthPair",
    "MonthRelations",
    "PlantedRun",
    "RowsCheck",
    "ScaledFutures",
    "TooFewMonths",
    "TooFewRaters",
    "arrows_that_pass",
    "benjamini_yekutieli",
    "check_rows",
    "declared_importance",
    "detrend",
    "effective_months",
    "iaaft",
    "influence_map",
    "input_status",
    "krippendorff_alpha",
    "map_stability",
    "minimum_rows",
    "month_relations",
    "permutation_importance",
    "scale_futures",
    "symmetric_part",
    "total_influence",
    "weighted_coverage",
]
