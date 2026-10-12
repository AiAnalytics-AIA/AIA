"""The response process on the Metodika tab (plan ``methodology-tab.md`` R1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: its preset is the
unit's values and the code computes from it (the EXACT captures in
``test_respondent_behavior.py`` hold it to the unit), a specification that cannot be read is
refused, and finding D6 is reproduced.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_respondent import describe_style, fictional_roster
from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.methodology import MODULES, describe, module_problems
from aia_core.domain.methodology.response import RESPONSE
from aia_core.domain.respondent_behavior import (
    AIA_RESPONSE_V1,
    STYLES,
    ResponseProcessSpec,
    ResponseQuestion,
    adjust_probabilities,
    assign_styles,
)

_SCALE = ResponseQuestion(
    typ="skala",
    labels=("1", "2", "3", "4", "5", "nevím"),
    scale=(1, 5),
    allow_dont_know=True,
    process={
        "agreement_scores": [0, 0, 0, 1, 1, 0],
        "social_desirability_scores": [1, 0, 0, 0, 0, 0],
    },
)
_STYLE = dict.fromkeys(STYLES, 1.3)
_P = [0.1, 0.2, 0.3, 0.2, 0.1, 0.1]
_ROWS = [
    {
        "respondent_id": f"R{i}",
        "vek": 20 + 7 * i,
        "pohlavi": "muž" if i % 2 else "žena",
        "vzdelani": "VOŠ/VŠ" if i % 3 else "základní",
    }
    for i in range(9)
]


def _with(**change: object) -> ResponseProcessSpec:
    return ResponseProcessSpec.model_validate({**AIA_RESPONSE_V1.model_dump(), **change})


def test_it_is_registered_after_weighting_and_is_complete() -> None:
    assert [m.id for m in MODULES][-2:] == ["weighting", "response"]
    assert module_problems(RESPONSE) == {}


def test_the_preset_is_the_units_values_and_the_code_reads_it() -> None:
    spec = AIA_RESPONSE_V1
    assert spec.methodology_version == "aia-response-1"
    assert (spec.social_desirability.base, spec.social_desirability.slope) == (0.18, 0.10)
    assert (spec.acquiescence, spec.extremity, spec.dont_know) == (0.16, 0.22, 0.24)
    assert (spec.satisficing.base, spec.satisficing.slope, spec.satisficing.cap) == (
        0.10,
        0.06,
        0.35,
    )
    assert (spec.reweight_limit, spec.style_noise_floor, spec.describe_threshold) == (
        8.0,
        0.05,
        0.7,
    )
    assert tuple(spec.style_links) == STYLES
    # The default is the preset, bit for bit.
    assert adjust_probabilities(_P, _SCALE, _STYLE) == adjust_probabilities(
        _P, _SCALE, _STYLE, spec
    )
    assert assign_styles(_ROWS) == assign_styles(_ROWS, spec)
    # And every declared value is read: changing any one changes what is computed.
    base, _ = adjust_probabilities(_P, _SCALE, _STYLE)
    for change in (
        {"social_desirability": {"base": 0.5, "slope": 0.10}},
        {"social_desirability": {"base": 0.18, "slope": 0.5}},
        {"acquiescence": 0.5},
        {"extremity": 0.5},
        {"dont_know": 0.5},
        {"satisficing": {"base": 0.2, "slope": 0.06, "cap": 0.35}},
        {"satisficing": {"base": 0.10, "slope": 0.2, "cap": 0.35}},
        {"satisficing": {"base": 0.10, "slope": 0.06, "cap": 0.15}},
        {"reweight_limit": 0.1},
    ):
        assert adjust_probabilities(_P, _SCALE, _STYLE, _with(**change))[0] != base, change
    styles = assign_styles(_ROWS)
    links = AIA_RESPONSE_V1.model_dump()["style_links"]
    links["sdilnost"]["education"] = 0.9
    assert assign_styles(_ROWS, _with(style_links=links)) != styles
    assert assign_styles(_ROWS, _with(style_noise_floor=1.0)) != styles


def test_every_value_is_shown_from_the_specification() -> None:
    values = {v.reference: v.value for s in describe(RESPONSE).steps for v in s.values}
    assert values["acquiescence"] == 0.16
    assert values["satisficing.cap"] == 0.35
    assert values["style_links.ochota_priznat_nevim.male"] == -0.15
    assert values["describe_threshold"] == 0.7


def test_it_is_declared_in_force_and_not_editable_yet() -> None:
    assert [p.name for p in RESPONSE.presets] == ["aia-response-1"]
    assert RESPONSE.in_force == "aia-response-1"
    assert RESPONSE.editable is False  # R1c
    assert RESPONSE.formulas == ()


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"style_links": {}}, "six styles in order"),
        ({"satisficing": {"base": 0.1, "slope": 0.06, "cap": 1.5}}, "between 0 and 1"),
        ({"style_noise_floor": 0.0}, "above 0"),
        ({"reweight_limit": 0.0}, "greater than zero"),
        ({"describe_threshold": -1.0}, "greater than zero"),
        ({"acquiescence": math.nan}, "finite"),
        ({"temperature": 1.0}, "Extra inputs"),
    ],
)
def test_a_response_process_that_cannot_be_read_is_refused(
    change: dict[str, object], says: str
) -> None:
    with pytest.raises(ValidationError, match=says):
        _with(**change)


def test_a_style_is_put_into_words_from_the_threshold() -> None:
    assert describe_style({"vyhranenost": 0.69}) == ""
    assert describe_style({"vyhranenost": 0.7}) == "volí krajní hodnoty škál, málokdy střed"
    assert describe_style({"vyhranenost": -0.7}).startswith("drží se středu")
    assert describe_style({"vyhranenost": 0.5}, threshold=0.5) != ""


def test_d6_a_fictional_run_below_75_respondents_has_too_few_donors() -> None:
    """D6, reproduced: a fictional roster has max(3, n // 3) donors, so under aia-support-1
    (25 donors for a donor-layer value) every run below 75 respondents is suppressed there."""
    floor = AIA_SUPPORT_V1.results.min_layer_donors
    assert floor == 25
    for n in (10, 30, 60, 74):
        donors = {p.donor_id for p in fictional_roster(n, seed=7)}
        assert len(donors) <= max(3, n // 3) < floor, n
    assert {p.weight for p in fictional_roster(30, seed=7)} == {1.0}
    assert max(3, 75 // 3) == floor  # from 75 the roster can reach the floor
