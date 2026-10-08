"""The design's dimensions and audience filters reach the specification (plan § 8.2, S4/I1).

Reproduction recorded on 2026-10-07 (plan sociomap-formula-corrections § 8.1): two designs
differing only in ``persona_dimensions.approved`` (finance vs ekologie), or only in an age
filter (18-29 vs 60-80), compiled to one specification and one fingerprint. They no longer
do; and the specification says the selection was not applied, because nothing in AIA can
apply it yet.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.domain.research_design import (
    SELECTION_NOT_APPLIED,
    CheckStatus,
    compile_design,
    prepare,
)

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 60,
    "sections": [
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus"],
            "scale": [1, 10],
        }
    ],
}
#: What develop's compiler gave DESIGN (``751d7ae``): a design that selects nothing keeps it.
DEVELOP_FINGERPRINT = "bb149341bbdfbe53acf139aa42869e535b5fe2f07ad2e96965ca1d8b086a80f3"


def _spec(design: dict[str, Any]) -> Any:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


def _with(*, dimensions: Any = None, filters: Any = None) -> dict[str, Any]:
    design = copy.deepcopy(DESIGN)
    if dimensions is not None:
        design["persona_dimensions"] = {"approved": dimensions}
    if filters is not None:
        design["audience"] = {
            "source_mode": "population",
            "strategy": "filters",
            "filters": filters,
        }
    return design


def test_two_designs_differing_only_in_dimensions_are_two_specifications() -> None:
    finance, ecology = _spec(_with(dimensions=["finance"])), _spec(_with(dimensions=["ekologie"]))
    assert finance.fingerprint() != ecology.fingerprint()
    assert finance.selection.dimensions == ("finance",)
    assert ecology.selection.dimensions == ("ekologie",)


def test_two_designs_differing_only_in_an_age_filter_are_two_specifications() -> None:
    young = _spec(_with(filters={"vek": [18, 29]}))
    old = _spec(_with(filters={"vek": [60, 80]}))
    assert young.audience == old.audience  # the coarse summary is unchanged...
    assert young.fingerprint() != old.fingerprint()  # ...the specification is not
    assert young.selection.audience_filters == {"vek": [18, 29]}


def test_the_selection_says_it_was_not_applied() -> None:
    spec = _spec(_with(dimensions=["finance", "media"], filters={"kraj": ["Praha"]}))
    assert spec.selection.applied is False
    assert spec.selection.reason == SELECTION_NOT_APPLIED


def test_a_design_that_selects_nothing_has_no_selection_and_keeps_its_fingerprint() -> None:
    plain = _spec(DESIGN)
    assert plain.selection is None
    assert plain.fingerprint() == DEVELOP_FINGERPRINT
    # Empty approvals and empty filters select nothing: they are not a selection.
    assert _spec(_with(dimensions=[], filters={"vek": [], "kraj": "", "x": None})).selection is None
    # (``_with(filters=...)`` also sets the strategy, which is the audience summary's own.)
    assert _spec(_with(dimensions=[])).fingerprint() == plain.fingerprint()


def test_an_empty_approval_is_not_refilled_with_a_guess() -> None:
    """The screen draws the recommended set when the approval is empty (OI-54); the
    specification records what the design stores, never the refill."""
    assert _spec(_with(dimensions=[])).selection is None


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ({"vek": {"min": 25, "max": None}}, {"vek": {"min": 25}}),
        ({"kraj": ["A", "", "B"], "pohlavi": "  "}, {"kraj": ["A", "B"]}),
        ({"b": ["x"], "a": [1, 2]}, {"a": [1, 2], "b": ["x"]}),
    ],
)
def test_filters_are_kept_without_their_empty_parts(raw: Any, kept: Any) -> None:
    spec = _spec(_with(filters=raw))
    assert spec.selection.audience_filters == kept


def test_dimensions_keep_the_designs_order_once_each() -> None:
    spec = _spec(_with(dimensions=["media", "finance", "media", " ", "KNW-1a"]))
    assert spec.selection.dimensions == ("media", "finance", "KNW-1a")


def test_readiness_names_the_dimensions_it_will_not_apply() -> None:
    _, readiness = prepare(_with(dimensions=["finance"]))
    (check,) = [c for c in readiness.checks if c.id == "dimensions"]
    assert check.status is CheckStatus.WARN and "finance" in check.message
    assert readiness.ready  # recorded and said, not a reason to refuse the run
    _, plain = prepare(DESIGN)
    assert not [c for c in plain.checks if c.id == "dimensions"]


@pytest.mark.parametrize(
    ("n", "status"), [(20, CheckStatus.WARN), (29, CheckStatus.WARN), (30, CheckStatus.PASS)]
)
def test_readiness_tells_a_sample_too_small_for_any_pair_from_one_that_can_collect(
    n: int, status: CheckStatus
) -> None:
    """Plan § 8.2, I3: 20 respondents can be collected (the policy's floor) but no pair can
    reach the audit's provisional n_min of 30, so the object map would be NOT_MAPPABLE."""
    _, readiness = prepare({**DESIGN, "n": n})
    (check,) = [c for c in readiness.checks if c.id == "sociomap_support"]
    assert check.status is status
    assert readiness.ready  # said before anything is paid for; not a refusal


def test_without_a_tracked_set_there_is_no_support_to_check() -> None:
    _, readiness = prepare(
        {
            "n": 20,
            "sections": [
                {
                    "type": "questions",
                    "questions": [{"text": "Jak?", "typ": "skala", "skala": [1, 5]}],
                }
            ],
        }
    )
    assert not [c for c in readiness.checks if c.id == "sociomap_support"]
