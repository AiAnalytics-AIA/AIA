"""Study readiness on the Metodika tab (plan ``methodology-tab.md`` V1a).

What every registered module must be (complete, pinned, its tests present) is held by
``test_methodology.py``; this file pins what is particular to this one: the preset is
18.6.6's product policy, the checks and the compile read the limits they are given, a version
is refused for limits no design could keep, and a run's pin reads back or refuses.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.methodology import MODULES, module_problems
from aia_core.domain.methodology.pins import read_readiness_pin, readiness_spec_for
from aia_core.domain.methodology.readiness import READINESS
from aia_core.domain.methodology.versions import (
    MethodologyVersionInvalid,
    named,
    validate_version,
)
from aia_core.domain.research_design import (
    AIA_READINESS_V1,
    SAMPLE_SIZE_BOUNDS,
    TRACKED_SET_LIMITS,
    CheckStatus,
    ReadinessSpec,
    compile_design,
    prepare,
)
from aia_core.domain.sociomap.relations import AUDIT_PROVISIONAL_N_MIN


def _design(n: int | None, objects: int) -> dict[str, Any]:
    return {
        "title": "Fiktivní nápoje",
        "n": n,
        "audience": {"source_mode": "population", "strategy": "population", "filters": {}},
        "sections": [
            {
                "type": "object_battery",
                "title": "Nápoje",
                "object_type": "nápoje",
                "objects": [f"Nápoj {i}" for i in range(1, objects + 1)],
            }
        ],
    }


def _limits(**change: Any) -> dict[str, Any]:
    spec = AIA_READINESS_V1.model_dump(mode="json")
    for path, value in change.items():
        part, field = path.split("__")
        spec[part][field] = value
    return spec


def _status(readiness: Any, check_id: str) -> CheckStatus | None:
    """The status of the check ``check_id``, or of the first whose id starts with it."""
    return next((c.status for c in readiness.checks if c.id.startswith(check_id)), None)


def test_the_preset_is_the_units_policy() -> None:
    assert [m.id for m in MODULES][-1] == "readiness"
    assert module_problems(READINESS) == {}
    assert READINESS.editable and READINESS.in_force == "aia-readiness-1"
    assert [p.name for p in READINESS.presets] == ["aia-readiness-1"]
    assert READINESS.presets[0].spec is AIA_READINESS_V1
    n, s = AIA_READINESS_V1.sample_size, AIA_READINESS_V1.tracked_set
    assert (n.min, n.max) == SAMPLE_SIZE_BOUNDS == (20, 10000)
    assert ((s.min, s.max), (s.recommended_min, s.recommended_max)) == TRACKED_SET_LIMITS


def test_the_limits_in_force_decide_the_checks() -> None:
    wider = ReadinessSpec.model_validate(
        _limits(sample_size__min=10, tracked_set__recommended_max=20)
    )
    for limits, n, objects, sample, size in (
        (AIA_READINESS_V1, 15, 18, CheckStatus.FAIL, CheckStatus.WARN),
        (wider, 15, 18, CheckStatus.PASS, None),
        (wider, 9, 18, CheckStatus.FAIL, None),
        (wider, 15, 21, CheckStatus.PASS, CheckStatus.WARN),
    ):
        _, readiness = prepare(
            _design(n, objects), pair_n_min=AUDIT_PROVISIONAL_N_MIN, limits=limits
        )
        assert _status(readiness, "sample_size") is sample
        assert _status(readiness, "battery_size:") is size, (limits, objects)
        assert readiness.ready is (sample is CheckStatus.PASS)
    # A missing n blocks under any limits: that stays code.
    _, readiness = prepare(_design(None, 5), pair_n_min=AUDIT_PROVISIONAL_N_MIN, limits=wider)
    assert _status(readiness, "sample_size") is CheckStatus.FAIL and not readiness.ready


def test_a_set_compiles_under_the_limits_it_is_given() -> None:
    spec, problems = compile_design(_design(100, 41))
    assert spec is None and [p.code for p in problems] == ["battery_size"]
    assert "3\u201340" in problems[0].message
    wider = ReadinessSpec.model_validate(_limits(tracked_set__max=50))
    spec, problems = compile_design(_design(100, 41), limits=wider)
    assert spec is not None and problems == ()
    # The limits decide whether a design compiles, never what it compiles to.
    same, _ = compile_design(_design(100, 12), limits=wider)
    preset, _ = compile_design(_design(100, 12))
    assert same is not None and preset is not None
    assert same.fingerprint() == preset.fingerprint()


def _validate(spec: dict[str, Any]) -> Any:
    return validate_version(
        READINESS,
        base_preset="aia-readiness-1",
        spec=spec,
        formulas={},
        version_name=named("aia-readiness-1", 1),
    )


def test_a_version_moves_every_limit_both_ways() -> None:
    edited = _limits(
        sample_size__min=10,
        sample_size__max=20000,
        tracked_set__min=4,
        tracked_set__max=30,
        tracked_set__recommended_min=5,
        tracked_set__recommended_max=12,
    )
    version = _validate(edited)
    assert version.spec.methodology_version == "aia-readiness-1+e1"
    assert version.spec.sample_size.max == 20000 and version.spec.tracked_set.min == 4


@pytest.mark.parametrize(
    ("change", "where"),
    [
        ({"sample_size__min": 500, "sample_size__max": 500}, "spec.sample_size.max"),
        ({"sample_size__min": 0}, "spec.sample_size.min"),
        ({"tracked_set__min": 2}, "spec.tracked_set.min"),
        ({"tracked_set__recommended_min": 2}, "spec.tracked_set.recommended_min"),
        ({"tracked_set__recommended_max": 41}, "spec.tracked_set.recommended_max"),
        (
            {"tracked_set__recommended_min": 10, "tracked_set__recommended_max": 8},
            "spec.tracked_set.recommended_max",
        ),
        ({"sample_size__min": 20.5}, "spec.sample_size.min"),
        ({"sample_size__min": True}, "spec.sample_size.min"),
        ({"tracked_set__max": "40"}, "spec.tracked_set.max"),
    ],
)
def test_limits_no_design_could_keep_are_refused_at_the_field(
    change: dict[str, Any], where: str
) -> None:
    with pytest.raises(MethodologyVersionInvalid) as refused:
        _validate(_limits(**change))
    assert where in refused.value.problems


def test_a_runs_pin_reads_back_or_refuses() -> None:
    assert readiness_spec_for(None) is AIA_READINESS_V1
    assert read_readiness_pin(None) is AIA_READINESS_V1
    stored = _validate(_limits(sample_size__min=10))
    payload = {"spec": stored.spec.model_dump(mode="json")}
    assert readiness_spec_for(payload) == stored.spec
    assert read_readiness_pin(payload["spec"]) == stored.spec
    with pytest.raises(ValueError, match=r"sample_size\.max"):
        read_readiness_pin(_limits(sample_size__max=10))
    with pytest.raises(ValueError):
        read_readiness_pin({"sample_size": {"min": 1, "max": 2}})
