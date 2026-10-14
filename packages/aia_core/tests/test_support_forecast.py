"""A run's evidence support, forecast from the roster fieldwork will draw (plan
run-recovery-and-truth 2a): the 50-respondent run that paid for nothing it could show."""

from __future__ import annotations

from typing import Any

from test_run_cost import DESIGN  # type: ignore[import-not-found]

from aia_core.domain.ai_respondent import fictional_roster, fieldwork_seed
from aia_core.domain.evidence import SupportStatus
from aia_core.domain.evidence.support import AIA_SUPPORT_V1, SupportSpec, SupportThresholds
from aia_core.domain.fieldwork import PersonaSource
from aia_core.domain.research_design import CheckStatus, assess_readiness, compile_design
from aia_core.domain.support_forecast import (
    SUPPORT_FORECAST_CHECK,
    forecast_support,
    with_support_forecast,
)

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


def test_a_population_drawn_run_is_unknown_never_good() -> None:
    spec = _spec(50)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=PersonaSource.PANEL)
    assert not forecast.known and forecast.analysis is None
    check = _check(spec, forecast)
    assert check.status is CheckStatus.WARN and "náhled publika" in check.message


def test_a_forecast_never_makes_a_design_unready() -> None:
    spec = _spec(50)
    base = assess_readiness(spec, pair_n_min=30)
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=ROSTER)
    assert with_support_forecast(base, forecast, support=AIA_SUPPORT_V1).ready is base.ready
