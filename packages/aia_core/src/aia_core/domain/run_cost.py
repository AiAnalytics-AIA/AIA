"""The most a research run can cost, worked out from its design before anything is sent.

A *ceiling*, not a forecast: the number of model requests the run can make, each priced at what
the worker reserves for one. The reservations are the worker's settings; the caller passes them
in, so this module stays pure. A request settles for its actual cost, which is never more than
the reservation (the worker refuses a reservation that cannot cover one call), so the ceiling
holds and the real cost is usually well below it.

Unknown is not zero. When a number the ceiling needs is missing it says which, and carries no
total: a person asked to confirm a cost must never be shown a missing one as a small one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .ai_respondent import max_blocks_per_respondent
from .analysis import ANALYSIS_MODULES
from .fieldwork import FieldworkSource
from .research_design import ResearchSpecification

__all__ = ["CeilingUnknown", "RunCostCeiling", "run_cost_ceiling"]


class CeilingUnknown(StrEnum):
    """Why a run's ceiling cannot be given."""

    SAMPLE_SIZE_MISSING = "sample_size_missing"
    FIELDWORK_RESERVATION_MISSING = "fieldwork_reservation_missing"
    ANALYSIS_RESERVATION_MISSING = "analysis_reservation_missing"


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
