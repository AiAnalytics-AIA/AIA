"""Whether a run's evidence will be shown, worked out before anything is paid for.

A 50-respondent fictional run passed readiness, paid for its fieldwork, and then every
question's evidence was suppressed: the roster had 15 distinct donors against the
support rule's 25, so every analysis module was blocked. A 200-respondent run of the same
design had 62 and worked. Nothing about that was uncertain. Fieldwork seeds its roster
from the specification (:func:`~.ai_respondent.fieldwork_seed`) and draws its donors from
``max(3, n // 3)`` ids with replacement (:func:`~.ai_respondent.fictional_roster`), so
the donors a run will have are known from the design alone.

:func:`forecast_support` draws that same roster and puts it through the aggregate's own
support computation (:func:`~.research_aggregate.donor_support`, under the run's pinned
``results`` rule) and the analysis gate (:func:`~.analysis.native.reassess_support`,
under its ``analysis`` rule): the status every question will carry, before the run, by
the code that will decide it after. Every question is asked of every respondent (a
conditional question is refused at readiness), so the forecast is one status for all.

A run whose respondents come from the population draws them at fieldwork with the same
seed, under the design's filters (:func:`~.panel_source.panel_plans`), so the sample a
start would draw over the population it would record is that run's sample: given it, the
forecast reads its donors and analysis weights through the same two gates. What it cannot
know it says so, and never scores as good: a panel run with no sample given (no population
to draw from, a refused draw) is unknown. The aggregation formulas a start
would pin are applied as the aggregate applies them (``slots``). An answer a respondent
leaves empty lowers a question's donors below the forecast, so the forecast is an upper
bound on support, never a promise of more.

Pure: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .ai_respondent import fictional_roster, fieldwork_seed
from .analysis.native import reassess_support
from .evidence import SupportStatus
from .evidence.support import SupportSpec
from .fieldwork import PersonaSource
from .population.sampling import PanelSample
from .research_aggregate import donor_support
from .research_design import (
    SAMPLE_SIZE_BOUNDS,
    CheckStatus,
    Readiness,
    ReadinessCheck,
    ResearchSpecification,
)
from .sociomap.slots import NO_SLOTS, Slots

__all__ = [
    "SUPPORT_FORECAST_CHECK",
    "ReportableState",
    "SupportForecast",
    "forecast_support",
    "with_support_forecast",
]

#: The readiness check this module adds.
SUPPORT_FORECAST_CHECK: Final = "support_forecast"

#: How far above the design's n the search for a sufficient n looks: four times n, and
#: never less than this many respondents above it.
_SEARCH_FLOOR: Final = 200
#: The most respondents the search may draw over all its candidates, so one readiness
#: read stays bounded whatever methodology is in force (about 1 s at 25 ms per 1,000).
_SEARCH_BUDGET: Final = 40_000


class ReportableState(StrEnum):
    """What :attr:`SupportForecast.reportable_n` stands for, so its ``None`` is never read as good
    (artifact-sample SMP9). ``MET``: the analysis gate already admits the evidence at the design's
    n. ``INDICATIVE``: it admits it as indicative. ``NEEDS_MORE``: it suppresses it, and
    ``reportable_n`` names the smallest n that would not. ``NOT_FOUND``: it suppresses it, and no
    n was found within the search. ``UNKNOWN``: nothing was forecast (a panel run without the
    sample a start would draw, no n)."""

    MET = "met"
    INDICATIVE = "indicative"
    NEEDS_MORE = "needs_more"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SupportForecast:
    """What the run's evidence will be, from the roster fieldwork will draw.

    ``donors`` ``None``: unknown before fieldwork (a population-drawn run). ``results``
    is the status every question will carry on Results, ``analysis`` the status the
    analysis gate will give it (the stricter of the two); a question SUPPRESSED for
    analysis gives the modules nothing to cite. ``reportable_n`` is the smallest n, with
    everything else in the design as it is, at which the analysis gate admits the
    evidence; ``None`` when none was found within the search, or when it is already met.
    """

    persona_source: PersonaSource
    respondents: int | None
    donors: int | None
    results: SupportStatus | None
    analysis: SupportStatus | None
    reportable_n: int | None = None

    @property
    def known(self) -> bool:
        return self.donors is not None

    @property
    def reportable_state(self) -> ReportableState:
        """What :attr:`reportable_n` stands for: unknown, never good, when nothing was forecast."""
        if self.analysis is None:
            return ReportableState.UNKNOWN
        if self.analysis is SupportStatus.REPORTABLE:
            return ReportableState.MET
        if self.analysis is SupportStatus.INDICATIVE:
            return ReportableState.INDICATIVE
        if self.reportable_n is None:
            # A panel forecast never searches for a sufficient n (each candidate would draw the
            # population again), so its missing n is unknown, never a search that found nothing.
            if self.persona_source is PersonaSource.PANEL:
                return ReportableState.UNKNOWN
            return ReportableState.NOT_FOUND
        return ReportableState.NEEDS_MORE


def _statuses(
    spec: ResearchSpecification, support: SupportSpec, slots: Slots
) -> tuple[int, SupportStatus, SupportStatus]:
    assert spec.n is not None
    roster = fictional_roster(spec.n, seed=fieldwork_seed(spec))
    return _judged([p.donor_id for p in roster], [p.weight for p in roster], support, slots)


def _judged(
    donors: list[str], weights: list[float], support: SupportSpec, slots: Slots
) -> tuple[int, SupportStatus, SupportStatus]:
    """The status every question will carry, from the respondents' donors and weights."""
    cell = donor_support(donors, weights, rule=support.results, slots=slots)
    results = SupportStatus(str(cell["support_status"]))
    # The question result as the aggregate writes it (research_aggregate: n_platnych,
    # effective_n from the combined estimate), read by the analysis gate as it reads one.
    question = {
        "n_platnych": cell["n"],
        "effective_n": cell["effective_n_combined"],
        "n_unique_layer_donors": cell["n_unique_layer_donors"],
        "support_status": cell["support_status"],
    }
    analysis = reassess_support(question, support.analysis).status
    return int(cell["n_unique_layer_donors"]), results, analysis


def _reportable_n(spec: ResearchSpecification, support: SupportSpec, slots: Slots) -> int | None:
    """The smallest n above the design's that the analysis gate admits, the rest unchanged.

    Each candidate is compiled as the run would see it: n is part of the specification's
    fingerprint, so a different n is a different seed and a different roster. The search
    stops at ``max(4n, n + 200)`` or when it has drawn :data:`_SEARCH_BUDGET` respondents,
    whichever comes first; ``None`` then says only that none was found within it.
    """
    assert spec.n is not None
    high = min(SAMPLE_SIZE_BOUNDS[1], max(4 * spec.n, spec.n + _SEARCH_FLOOR))
    drawn = 0
    for n in range(spec.n + 1, high + 1):
        drawn += n
        if drawn > _SEARCH_BUDGET:
            return None
        _, _, analysis = _statuses(spec.model_copy(update={"n": n}), support, slots)
        if analysis is not SupportStatus.SUPPRESS:
            return n
    return None


def forecast_support(
    spec: ResearchSpecification,
    *,
    support: SupportSpec,
    persona_source: PersonaSource,
    slots: Slots = NO_SLOTS,
    sample: PanelSample | None = None,
) -> SupportForecast:
    """The support a run of ``spec`` will have, under the support rules it will pin and the
    aggregation formulas it will pin (``slots``: the in-force version's replacements, as
    ``read_aggregation_pin`` compiles them; none, the code's formulas).

    ``sample``: for a panel run, the sample a start would draw (``draw_panel_sample`` over the
    population the run would record, the design's filters, ``fieldwork_seed(spec)``). Without
    one, or with one drawn at another seed, of another size or with a respondent without a
    donor (which fieldwork refuses), the forecast is unknown."""
    unknown = SupportForecast(
        persona_source=persona_source,
        respondents=spec.n,
        donors=None,
        results=None,
        analysis=None,
    )
    if spec.n is None or spec.n < 1:
        return unknown
    if persona_source is PersonaSource.PANEL:
        # A sample drawn at any other seed (the audience preview's) is not the run's.
        if (
            sample is None
            or sample.seed != fieldwork_seed(spec)
            or len(sample.respondents) != spec.n
        ):
            return unknown
        drawn = [r.donor for r in sample.respondents if r.donor is not None]
        if len(drawn) != spec.n:
            return unknown
        known, results, analysis = _judged(
            drawn,
            [r.analysis_weight for r in sample.respondents],
            support,
            slots,
        )
        # No sufficient n is searched: each candidate would draw the population again.
        return SupportForecast(
            persona_source=persona_source,
            respondents=spec.n,
            donors=known,
            results=results,
            analysis=analysis,
        )
    donors, results, analysis = _statuses(spec, support, slots)
    return SupportForecast(
        persona_source=persona_source,
        respondents=spec.n,
        donors=donors,
        results=results,
        analysis=analysis,
        reportable_n=_reportable_n(spec, support, slots)
        if analysis is SupportStatus.SUPPRESS
        else None,
    )


def _below(line: int | None, tail: str, *, prefix: str = " Pod ", suffix: str = " dárci") -> str:
    """A threshold in words, or nothing when the rule does not check that line."""
    return "" if line is None else f"{prefix}{line}{suffix}{tail}"


def _check(forecast: SupportForecast, support: SupportSpec) -> ReadinessCheck:
    if not forecast.known:
        return ReadinessCheck(
            id=SUPPORT_FORECAST_CHECK,
            status=CheckStatus.WARN,
            message=(
                "Kolik různých dárců běh bude mít, se ukáže až při výběru respondentů z "
                "populace; náhled publika ukazuje dárce vybraného publika."
                + _below(support.results.min_layer_donors, " se výsledky nezobrazí.")
                if forecast.persona_source is PersonaSource.PANEL
                else "Oporu výsledků nelze předem spočítat."
            ),
        )
    lines = support.results
    head = f"Běh bude mít {forecast.donors} různých dárců na {forecast.respondents} respondentů"
    if forecast.analysis is SupportStatus.SUPPRESS:
        more = (
            f" Při stejném návrhu by stačilo n = {forecast.reportable_n}."
            if forecast.reportable_n is not None
            else ""
        )
        return ReadinessCheck(
            id=SUPPORT_FORECAST_CHECK,
            status=CheckStatus.WARN,
            message=(
                f"{head}: čísla všech otázek budou pro AI analýzu potlačená a nebude mít "
                "co citovat (rozhoduje platná metodika opory). Běh za sběr dat zaplatí, "
                f"ale analýza ani report nevzniknou.{more}"
            ),
        )
    if forecast.analysis is SupportStatus.INDICATIVE:
        return ReadinessCheck(
            id=SUPPORT_FORECAST_CHECK,
            status=CheckStatus.WARN,
            message=(
                f"{head}: čísla budou jen indikativní"
                + _below(lines.indicative_layer_donors, "", prefix=" (pod ", suffix=" dárci)")
                + ". Zobrazí se, ale se slabou oporou."
            ),
        )
    return ReadinessCheck(
        id=SUPPORT_FORECAST_CHECK,
        status=CheckStatus.PASS,
        message=f"{head}: opora stačí, pokud respondenti odpovědi nevynechají.",
    )


def with_support_forecast(
    readiness: Readiness, forecast: SupportForecast, *, support: SupportSpec
) -> Readiness:
    """``readiness`` with the forecast's check after its own. A forecast never FAILs: it
    says what the run will show; whether to pay for that stays the person's call."""
    return Readiness(
        rules=readiness.rules,
        ready=readiness.ready,
        checks=(*readiness.checks, _check(forecast, support)),
    )
