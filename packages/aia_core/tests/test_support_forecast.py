"""A run's evidence support, forecast from the roster fieldwork will draw (plan
run-recovery-and-truth 2a): the 50-respondent run that paid for nothing it could show."""

from __future__ import annotations

from typing import Any

from aia_core.domain.ai_respondent import fictional_roster, fieldwork_seed
from aia_core.domain.evidence import SupportStatus
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, SupportSpec, SupportThresholds
from aia_core.domain.fieldwork import PersonaSource
from aia_core.domain.methodology.pins import aggregation_pin_for, read_aggregation_pin
from aia_core.domain.research_design import CheckStatus, assess_readiness, compile_design
from aia_core.domain.support_forecast import (
    SUPPORT_FORECAST_CHECK,
    ReportableState,
    forecast_support,
    with_support_forecast,
)

#: Two questions and a battery: every question is asked of every respondent.
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často pijete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                },
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}

ROSTER = PersonaSource.FICTIONAL_ROSTER


def _spec(n: int) -> Any:
    spec, problems = compile_design({**DESIGN, "n": n})
    assert spec is not None, problems
    return spec


def _check(spec: Any, forecast: Any, support: SupportSpec = AIA_SUPPORT_V1) -> Any:
    readiness = with_support_forecast(
        assess_readiness(spec, pair_n_min=30), forecast, support=support
    )
    return next(c for c in readiness.checks if c.id == SUPPORT_FORECAST_CHECK)


def test_the_forecast_counts_the_donors_fieldwork_will_draw() -> None:
    for n in (50, 90, 200):
        spec = _spec(n)
        roster = fictional_roster(n, seed=fieldwork_seed(spec))
        forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
        assert forecast.donors == len({p.donor_id for p in roster})
        assert forecast.respondents == n


def test_fifty_fictional_respondents_are_suppressed_and_the_check_says_what_n_would_do() -> None:
    spec = _spec(50)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    assert forecast.donors is not None and forecast.donors < 25
    assert forecast.analysis is SupportStatus.SUPPRESS
    assert forecast.reportable_n is not None and forecast.reportable_n > 50
    sufficient = forecast_support(
        _spec(forecast.reportable_n), support=AIA_SUPPORT_V1, persona_source=ROSTER
    )
    assert sufficient.analysis is not SupportStatus.SUPPRESS, "the n it names does suffice"
    check = _check(spec, forecast)
    assert check.status is CheckStatus.WARN
    assert f"n = {forecast.reportable_n}" in check.message
    assert "nevzniknou" in check.message


def test_two_hundred_respondents_pass() -> None:
    spec = _spec(200)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    assert forecast.analysis is SupportStatus.REPORTABLE and forecast.reportable_n is None
    assert _check(spec, forecast).status is CheckStatus.PASS


def test_the_pinned_rule_decides_not_a_copy_of_the_thresholds() -> None:
    lenient = SupportSpec(
        methodology_version="test",
        results=SupportThresholds(
            min_cell=None, n_guard=None, indicative=None, min_layer_donors=5,
            indicative_layer_donors=10,
        ),
        analysis=SupportThresholds(
            min_cell=None, n_guard=None, indicative=None, min_layer_donors=5,
            indicative_layer_donors=10,
        ),
    )  # fmt: skip
    forecast = forecast_support(_spec(50), support=lenient, persona_source=ROSTER)
    assert forecast.analysis is SupportStatus.REPORTABLE


def test_the_aggregation_formulas_a_start_would_pin_are_applied() -> None:
    """A version replacing Kish's formula changes every cell's effective n; the forecast
    reads it as the aggregate does (``read_aggregation_pin``), never the code's formula."""
    _, slots = read_aggregation_pin({**aggregation_pin_for(None), "formulas": {"agg.kish": "3"}})
    spec = _spec(200)
    code = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    pinned = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER, slots=slots)
    assert code.analysis is SupportStatus.REPORTABLE
    assert pinned.analysis is SupportStatus.SUPPRESS


def test_the_search_for_a_sufficient_n_is_bounded_whatever_the_rules() -> None:
    """Rules no n can meet: the search stops within its budget and finds nothing."""
    never = SupportSpec(
        methodology_version="test",
        results=AIA_SUPPORT_V1.results,
        analysis=SupportThresholds(
            min_cell=None, n_guard=None, indicative=None, min_layer_donors=100_000,
            indicative_layer_donors=100_000,
        ),
    )  # fmt: skip
    forecast = forecast_support(_spec(2500), support=never, persona_source=ROSTER)
    assert forecast.analysis is SupportStatus.SUPPRESS and forecast.reportable_n is None


def test_a_population_drawn_run_is_unknown_never_good() -> None:
    spec = _spec(50)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=PersonaSource.PANEL)
    assert not forecast.known and forecast.analysis is None
    check = _check(spec, forecast)
    assert check.status is CheckStatus.WARN and "náhled publika" in check.message


def test_what_a_reportable_n_stands_for_is_named_so_none_is_never_read_as_good() -> None:
    """SMP9 (stand-in review of #1010): ``reportable_n`` is ``None`` when n already suffices, when
    the evidence is indicative, when nothing was forecast and when the search found nothing; the
    state tells them apart."""

    def rule(minimum: int, indicative: int) -> SupportSpec:
        line = SupportThresholds(
            min_cell=None, n_guard=None, indicative=None, min_layer_donors=minimum,
            indicative_layer_donors=indicative,
        )  # fmt: skip
        return SupportSpec(methodology_version="test", results=line, analysis=line)

    def state(n: int, support: SupportSpec = AIA_SUPPORT_V1, source: Any = ROSTER) -> Any:
        return forecast_support(_spec(n), support=support, persona_source=source).reportable_state

    assert state(200) is ReportableState.MET
    assert state(50, rule(5, 100_000)) is ReportableState.INDICATIVE
    assert state(50) is ReportableState.NEEDS_MORE
    assert state(2500, rule(100_000, 100_000)) is ReportableState.NOT_FOUND
    assert state(450, source=PersonaSource.PANEL) is ReportableState.UNKNOWN


def test_a_forecast_never_makes_a_design_unready() -> None:
    spec = _spec(50)
    base = assess_readiness(spec, pair_n_min=30)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    assert with_support_forecast(base, forecast, support=AIA_SUPPORT_V1).ready is base.ready
