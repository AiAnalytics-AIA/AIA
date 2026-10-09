"""The most a research run can cost, worked out from its design before anything is sent.

A *ceiling*, not a forecast: the number of model requests the run can make, each priced at what
the worker reserves for one. The reservations are the worker's settings; the caller passes them
in, so this module stays pure. A request settles for its actual cost, which is never more than
the reservation (the worker refuses a reservation that cannot cover one call), so the ceiling
holds and the real cost is usually well below it.

Unknown is not zero. When a number the ceiling needs is missing it says which, and carries no
total: a person asked to confirm a cost must never be shown a missing one as a small one.

A Deep Research run's ceiling (:func:`deep_research_cost_ceiling`, plan
``deep-research-web-search.md`` chunk 22) is the same idea over more kinds of call: each
kind's most calls (``deep_research.budgets.call_bounds``) times what one may cost -- a
model request at its reservation, a search, fetch or connector call at its route's price,
a Common Crawl query at its scan cutoff billed. A route the composition does not offer
sends nothing and costs nothing (:meth:`RoutePrice.off`); a route it offers without a
price makes the ceiling unknown, whatever the other routes cost.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from .ai_respondent import max_blocks_per_respondent
from .analysis import ANALYSIS_MODULES
from .deep_research.budgets import (
    MODEL_KINDS,
    ROUTE_ALLOWANCES,
    CallBounds,
    CallKind,
    ResearchMode,
    RouteAllowance,
    TrackCounts,
    call_bounds,
)
from .deep_research.common_crawl import AthenaPricing
from .deep_research.planning import PRESET_TABLE_VERSION, DepthPreset
from .fieldwork import FieldworkSource
from .research_design import ResearchSpecification

__all__ = [
    "CeilingUnknown",
    "DeepResearchCeiling",
    "DeepResearchPrices",
    "RoutePrice",
    "RunCostCeiling",
    "deep_research_cost_ceiling",
    "price_bounds",
    "run_cost_ceiling",
]


class CeilingUnknown(StrEnum):
    """Why a run's ceiling cannot be given."""

    SAMPLE_SIZE_MISSING = "sample_size_missing"
    FIELDWORK_RESERVATION_MISSING = "fieldwork_reservation_missing"
    ANALYSIS_RESERVATION_MISSING = "analysis_reservation_missing"
    #: A Deep Research run would call a route (or a model) whose price is not configured.
    DEEP_RESEARCH_PRICE_MISSING = "deep_research_price_missing"


@dataclass(frozen=True, slots=True)
class RunCostCeiling:
    """What a run can cost at most, in model requests and in dollars."""

    fieldwork_requests: int
    fieldwork_usd: float | None
    analysis_calls: int
    analysis_usd: float | None
    total_usd: float | None
    unknown: CeilingUnknown | None = None


def _unknown(why: CeilingUnknown, *, requests: int = 0, calls: int = 0) -> RunCostCeiling:
    return RunCostCeiling(requests, None, calls, None, None, why)


def run_cost_ceiling(
    spec: ResearchSpecification,
    *,
    fieldwork_source: FieldworkSource,
    fieldwork_reservation_usd: float | None,
    analysis_enabled: bool,
    analysis_reservation_usd: float | None,
    analysis_calls_per_module: int,
) -> RunCostCeiling:
    """The ceiling for running ``spec``: fieldwork requests plus analysis calls, each reserved.

    Fieldwork is one request per respondent block for an AI-runtime source and nothing for the
    fixture, which answers by code. Analysis is each module's calls (a draft and its repairs)
    when analysis is switched on, and nothing when it is off.
    """
    requests = 0
    fieldwork_usd = 0.0
    if fieldwork_source is FieldworkSource.AI_RUNTIME:
        if spec.n is None:
            return _unknown(CeilingUnknown.SAMPLE_SIZE_MISSING)
        requests = spec.n * max_blocks_per_respondent(spec)
        if fieldwork_reservation_usd is None or not fieldwork_reservation_usd > 0:
            return _unknown(CeilingUnknown.FIELDWORK_RESERVATION_MISSING, requests=requests)
        fieldwork_usd = requests * fieldwork_reservation_usd

    calls = 0
    analysis_usd = 0.0
    if analysis_enabled:
        calls = len(ANALYSIS_MODULES) * analysis_calls_per_module
        if analysis_reservation_usd is None or not analysis_reservation_usd > 0:
            return _unknown(
                CeilingUnknown.ANALYSIS_RESERVATION_MISSING, requests=requests, calls=calls
            )
        analysis_usd = calls * analysis_reservation_usd

    return RunCostCeiling(
        fieldwork_requests=requests,
        fieldwork_usd=fieldwork_usd,
        analysis_calls=calls,
        analysis_usd=analysis_usd,
        total_usd=fieldwork_usd + analysis_usd,
    )


# --------------------------------------------------------------------------- #
# Deep Research
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RoutePrice:
    """What one call of a kind may cost: off, a price, or unknown -- never a default.

    ``off``: the composition does not offer the route, so nothing is sent on it. A price:
    a model request's reservation (covering its repair), or a tool call's price per call.
    ``unknown``: the route is offered and its price is not configured.
    """

    state: Literal["off", "priced", "unknown"]
    usd: float | None = None

    def __post_init__(self) -> None:
        if self.state == "priced":
            if self.usd is None or not math.isfinite(self.usd) or self.usd < 0:
                raise ValueError("a price is a finite, non-negative number")
        elif self.usd is not None:
            raise ValueError(f"a route that is {self.state} carries no price")

    @classmethod
    def off(cls) -> RoutePrice:
        return cls("off")

    @classmethod
    def per_call(cls, usd: float) -> RoutePrice:
        return cls("priced", float(usd))

    @classmethod
    def unknown(cls) -> RoutePrice:
        return cls("unknown")

    @classmethod
    def of(cls, usd: float | None) -> RoutePrice:
        """A configured value: ``None`` is unknown, never zero."""
        return cls.unknown() if usd is None else cls.per_call(usd)

    @classmethod
    def athena(cls, pricing: AthenaPricing, scan_cutoff_bytes: int) -> RoutePrice:
        """A URL index query: its workgroup's scan cutoff, billed -- what each one reserves."""
        return cls.per_call(pricing.cost_usd(scan_cutoff_bytes))


@dataclass(frozen=True, slots=True)
class DeepResearchPrices:
    """Every kind of call's price, stated. A kind left out is an error here, not a zero.

    A model kind that is priced is priced above zero: a request reserves before it leaves
    (``StepModelCaller`` refuses a reservation of zero), so zero would be a guess.
    """

    prices: Mapping[CallKind, RoutePrice]

    def __post_init__(self) -> None:
        missing = set(CallKind) - set(self.prices)
        if missing:
            raise ValueError(
                f"every kind of call states its price; missing {sorted(k.value for k in missing)}"
            )
        for kind in MODEL_KINDS:
            price = self.prices[kind]
            if price.state == "priced" and not (price.usd or 0) > 0:
                raise ValueError(f"the {kind.value} reservation must be above zero")

    def __getitem__(self, kind: CallKind) -> RoutePrice:
        return self.prices[kind]


@dataclass(frozen=True, slots=True)
class DeepResearchCeiling:
    """What a Deep Research run can cost at most: calls, dollars by kind, and the total.

    ``mode`` is the mode whose ceiling this is (the highest, when several were asked).
    ``unknown_kinds`` name the kinds the run would call with no price; then ``total_usd``
    is ``None`` and ``unknown`` says why.
    """

    preset: str
    preset_table: str
    mode: ResearchMode
    calls: Mapping[CallKind, int]
    usd: Mapping[CallKind, float]
    total_usd: float | None
    unknown: CeilingUnknown | None = None
    unknown_kinds: tuple[CallKind, ...] = ()


def price_bounds(
    bounds: CallBounds, prices: DeepResearchPrices, *, preset: str, mode: ResearchMode
) -> DeepResearchCeiling:
    """``bounds`` priced: each kind's calls times its price; unknown if any called is unpriced."""
    usd: dict[CallKind, float] = {}
    unknown: list[CallKind] = []
    for kind in CallKind:
        n, price = bounds[kind], prices[kind]
        if n == 0 or price.state == "off":
            usd[kind] = 0.0
        elif price.state == "unknown":
            unknown.append(kind)
        else:
            assert price.usd is not None
            usd[kind] = n * price.usd
    return DeepResearchCeiling(
        preset=preset,
        preset_table=PRESET_TABLE_VERSION,
        mode=mode,
        calls=dict(bounds.counts),
        usd=usd,
        total_usd=None if unknown else sum(usd.values()),
        unknown=CeilingUnknown.DEEP_RESEARCH_PRICE_MISSING if unknown else None,
        unknown_kinds=tuple(unknown),
    )


def deep_research_cost_ceiling(
    depth: DepthPreset,
    tracks: TrackCounts,
    prices: DeepResearchPrices,
    *,
    modes: Collection[ResearchMode],
    allowances: Mapping[str, RouteAllowance] = ROUTE_ALLOWANCES,
) -> DeepResearchCeiling:
    """The most a Deep Research run of ``depth`` over ``tracks`` can cost.

    ``modes`` are the modes the run may be researched in: the composition's one, when the
    caller knows it, or every mode when it does not -- the ceiling is then the highest of
    them. Unknown in any of them is unknown: a ceiling is never the cheaper of two guesses.
    ``allowances`` are the route allowances in force (the run's settings, chunk 43c).
    """
    if not modes:
        raise ValueError("a ceiling is for at least one mode")
    ceilings = [
        price_bounds(
            call_bounds(depth, tracks, mode, allowances=allowances),
            prices,
            preset=depth.name,
            mode=mode,
        )
        for mode in ResearchMode
        if mode in modes
    ]
    unknown = [c for c in ceilings if c.total_usd is None]
    if unknown:
        return unknown[0]
    return max(ceilings, key=lambda c: c.total_usd or 0.0)
