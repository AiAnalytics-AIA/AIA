"""The most a research run can cost: an upper bound from the design, never a forecast.

The ceiling is the number of model requests a run can make times what each one reserves.
It is unknown, not zero, when something it needs is missing: a missing number must not read
as a cheap run (ARCHITECTURE: never score unknown as good).
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.ai_respondent import (
    fictional_roster,
    max_blocks_per_respondent,
    plan_respondent,
)
from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.research_design import compile_design
from aia_core.domain.run_cost import CeilingUnknown, run_cost_ceiling

#: Five questions (the open one asks alone) and a battery of seven objects: twelve items.
DESIGN: dict[str, Any] = {
    "title": "Fiktivní ranní nápoj",
    "n": 20,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q_sex",
                    "text": "Jaké je vaše pohlaví?",
                    "typ": "vyber",
                    "kategorie": ["muž", "žena"],
                },
                {
                    "id": "q1",
                    "text": "Jak často pijete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "povolit_nevim": True,
                },
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                    "povolit_nevim": True,
                },
                {
                    "id": "q3",
                    "text": "Co ještě pijete?",
                    "typ": "multi",
                    "kategorie": ["Džus", "Vodu", "Mléko"],
                },
                {"id": "q4", "text": "Proč?", "typ": "otevrena"},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda", "Limonáda", "Mošt"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


def _spec(**override: Any) -> Any:
    spec, problems = compile_design({**DESIGN, **override})
    assert spec is not None, problems
    return spec


def _ceiling(spec: Any, **kw: Any) -> Any:
    args: dict[str, Any] = {
        "fieldwork_source": FieldworkSource.AI_RUNTIME,
        "fieldwork_reservation_usd": 0.5,
        "analysis_enabled": True,
        "analysis_reservation_usd": 2.0,
        "analysis_calls_per_module": 3,
    }
    args.update(kw)
    return run_cost_ceiling(spec, **args)


def test_the_most_blocks_is_every_item_asked_with_each_open_question_alone() -> None:
    # Four closed questions, the open one alone, then the battery's seven objects.
    assert max_blocks_per_respondent(_spec()) == 3


def test_no_persona_ever_needs_more_blocks_than_the_bound() -> None:
    spec = _spec()
    bound = max_blocks_per_respondent(spec)
    for persona in fictional_roster(spec.n, seed=7):
        assert len(plan_respondent(spec, persona).blocks) <= bound


def test_a_run_is_respondents_times_blocks_times_the_reservation_plus_the_analysis() -> None:
    ceiling = _ceiling(_spec())
    assert ceiling.fieldwork_requests == 20 * 3
    assert ceiling.fieldwork_usd == pytest.approx(60 * 0.5)
    assert ceiling.analysis_calls == len(ANALYSIS_MODULES) * 3
    assert ceiling.analysis_usd == pytest.approx(len(ANALYSIS_MODULES) * 3 * 2.0)
    assert ceiling.total_usd == pytest.approx(ceiling.fieldwork_usd + ceiling.analysis_usd)
    assert ceiling.unknown is None


def test_a_bigger_sample_costs_more_and_nothing_else_changes() -> None:
    small, big = _ceiling(_spec(n=20)), _ceiling(_spec(n=40))
    assert big.fieldwork_usd == pytest.approx(2 * small.fieldwork_usd)
    assert big.analysis_usd == small.analysis_usd


def test_analysis_that_is_switched_off_costs_nothing() -> None:
    ceiling = _ceiling(_spec(), analysis_enabled=False, analysis_reservation_usd=None)
    assert ceiling.analysis_calls == 0
    assert ceiling.analysis_usd == 0.0
    assert ceiling.total_usd == ceiling.fieldwork_usd


def test_the_fixture_source_calls_no_model() -> None:
    ceiling = _ceiling(
        _spec(),
        fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        fieldwork_reservation_usd=None,
        analysis_enabled=False,
        analysis_reservation_usd=None,
    )
    assert ceiling.total_usd == 0.0
    assert ceiling.unknown is None


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"fieldwork_reservation_usd": None}, CeilingUnknown.FIELDWORK_RESERVATION_MISSING),
        ({"analysis_reservation_usd": None}, CeilingUnknown.ANALYSIS_RESERVATION_MISSING),
        ({"fieldwork_reservation_usd": 0.0}, CeilingUnknown.FIELDWORK_RESERVATION_MISSING),
    ],
)
def test_a_missing_reservation_makes_the_ceiling_unknown_not_zero(
    override: dict[str, Any], reason: CeilingUnknown
) -> None:
    ceiling = _ceiling(_spec(), **override)
    assert ceiling.unknown is reason
    assert ceiling.total_usd is None


def test_a_design_without_a_sample_size_has_no_ceiling() -> None:
    spec = _spec()
    ceiling = _ceiling(spec.model_copy(update={"n": None}))
    assert ceiling.unknown is CeilingUnknown.SAMPLE_SIZE_MISSING
    assert ceiling.total_usd is None
