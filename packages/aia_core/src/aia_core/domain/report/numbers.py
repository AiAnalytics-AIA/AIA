"""Czech print formatting for the numbers a report prints (pure).

Every number in a report arrives already decided: an ``EvidenceRow`` carries its
value rounded to its ``decimals``. This module only *writes* it — decimal comma,
no-break space as the thousands separator and before the unit, an en dash in
ranges — and never rounds it again. The one exception is effective n, which the
support assessment keeps as a float: it prints **rounded down**, so a report
never states more support than it has.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Final

from aia_core.domain.evidence.metrics import MetricUnit
from aia_core.domain.evidence.support import Interval

NBSP: Final = "\u00a0"
NARROW_NBSP: Final = "\u202f"
EN_DASH: Final = "\u2013"
MINUS: Final = "\u2212"

_MONTHS_GENITIVE: Final = (
    "ledna",
    "února",
    "března",
    "dubna",
    "května",
    "června",
    "července",
    "srpna",
    "září",
    "října",
    "listopadu",
    "prosince",
)


def number(value: float, decimals: int) -> str:
    """``1204.5, 1`` → ``1 204,5`` (no-break space groups, decimal comma, true minus).

    ``value`` is printed at exactly ``decimals`` places. It must already be
    rounded there: the report never re-rounds a number the evidence decided.
    """
    if not math.isfinite(value):
        raise ValueError("a report never prints a non-finite number")
    if decimals < 0:
        raise ValueError("decimals must be >= 0")
    if round(value, decimals) != value:
        raise ValueError(f"{value} is not rounded to {decimals} dp; the evidence decides rounding")
    text = f"{abs(value):,.{decimals}f}"
    whole, _, frac = text.partition(".")
    whole = whole.replace(",", NBSP)
    out = f"{whole},{frac}" if frac else whole
    return f"{MINUS}{out}" if value < 0 else out


def with_unit(value: float, decimals: int, unit: MetricUnit) -> str:
    """A value with its unit: ``42,5 %``; a scale mean and a count carry none."""
    text = number(value, decimals)
    if unit is MetricUnit.PERCENT:
        return f"{text}{NBSP}%"
    return text


def interval(iv: Interval, decimals: int, unit: MetricUnit) -> str:
    """``(38,1-46,9)`` for percentages, the unit written once after the range."""
    lo = number(round(iv.lower, decimals), decimals)
    hi = number(round(iv.upper, decimals), decimals)
    suffix = f"{NBSP}%" if unit is MetricUnit.PERCENT else ""
    return f"({lo}{EN_DASH}{hi}{suffix})"


def effective_n(value: float) -> str:
    """Effective n, rounded **down**: never state more support than there is."""
    if not math.isfinite(value) or value < 0:
        raise ValueError("effective n must be a finite, non-negative number")
    return number(float(math.floor(value)), 0)


def base_n(value: float) -> str:
    """The base label a caption carries: ``n = 1 204`` with no-break spaces."""
    return f"n{NBSP}={NBSP}{effective_n(value)}"


def czech_date(d: date) -> str:
    """``25. září 2026`` — day, genitive month, year; no-break spaces inside."""
    return f"{d.day}.{NBSP}{_MONTHS_GENITIVE[d.month - 1]}{NBSP}{d.year}"


def page_of(page: int, total: int) -> str:
    """Only for tests of the footer text: ``3 z 42``."""
    return f"{page}{NBSP}z{NBSP}{total}"
