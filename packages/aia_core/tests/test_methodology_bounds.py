"""Each editable field's bound is its check's own (settings-redesign F13, AUD-10 (b)).

A bound is declared beside its module and the editor says it beside the field ("mez …"). It is
never more than the check: for every preset that gives the field a number, the value at each
limit is kept and the value just past it is refused, by the module's own validation
(:func:`validate_version`), at the field or the part that holds it. A limit read from another
field is read from the same preset.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from aia_core.domain.methodology import MODULES, Bound, Limit, MethodModule, read_path
from aia_core.domain.methodology.resolution import ABSENT
from aia_core.domain.methodology.versions import MethodologyVersionInvalid, validate_version

EDITABLE = [m for m in MODULES if m.editable]
CASES = [(m, b) for m in EDITABLE for b in m.bounds]


def _number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _set(spec: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    parts = path.split(".")
    node = spec
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    return spec


def _problems_at(module: MethodModule, preset: str, data: dict[str, Any], path: str) -> list[str]:
    """The problems the module's validation reports at ``path`` or a part that holds it."""
    try:
        validate_version(
            module, base_preset=preset, spec=data, formulas={}, version_name=f"{preset}+e1"
        )
    except MethodologyVersionInvalid as exc:
        parts = path.split(".")
        held = {"spec", *(f"spec.{'.'.join(parts[: i + 1])}" for i in range(len(parts)))}
        return [f"{k}: {v}" for k, v in exc.problems.items() if k in held]
    return []


def _limit_value(limit: Limit, spec: Any) -> float | None:
    if isinstance(limit.value, str):
        value = read_path(spec, limit.value)
        return value if _number(value) else None
    return limit.value


def _probes(limit: Limit, at: float, whole: bool) -> tuple[float, float]:
    """The value at the limit that is kept and the value just past it that is refused."""
    outward = -1 if limit.side == "low" else 1
    if whole:
        inside = at - outward if limit.strict else at
        return int(inside), int(inside + outward)
    if limit.strict:
        return math.nextafter(at, -outward * math.inf), at
    return at, math.nextafter(at, outward * math.inf)


def _tightest(limits: list[tuple[Limit, float]], whole: bool) -> tuple[Limit, float] | None:
    """The limit that binds on one side; a whole number's strict limit read as the next one."""

    def closed(limit: Limit, at: float) -> float:
        if not limit.strict:
            return at
        if whole:
            return at + 1 if limit.side == "low" else at - 1
        return math.nextafter(at, math.inf if limit.side == "low" else -math.inf)

    if not limits:
        return None
    pick = max if limits[0][0].side == "low" else min
    return pick(limits, key=lambda pair: closed(*pair))


@pytest.mark.parametrize(("module", "bound"), CASES, ids=[f"{m.id}:{b.path}" for m, b in CASES])
def test_each_limit_is_the_checks_own(module: MethodModule, bound: Bound) -> None:
    binding: set[int] = set()
    for preset in module.presets:
        value = read_path(preset.spec, bound.path)
        if value is ABSENT or not _number(value):
            continue  # no number here: a value would be refused for another reason
        whole = isinstance(value, int)
        for side in ("low", "high"):
            read = [
                (limit, at)
                for limit in bound.limits
                if limit.side == side and (at := _limit_value(limit, preset.spec)) is not None
            ]
            tight = _tightest(read, whole)
            if tight is None:
                continue
            limit, at = tight
            kept, refused = _probes(limit, at, whole)
            base = preset.spec.model_dump(mode="json")
            assert (
                _problems_at(module, preset.name, _set(base, bound.path, kept), bound.path) == []
            ), f"{preset.name}: {bound.path} = {kept} is inside the bound but refused"
            base = preset.spec.model_dump(mode="json")
            assert _problems_at(module, preset.name, _set(base, bound.path, refused), bound.path), (
                f"{preset.name}: {bound.path} = {refused} is past the bound but kept"
            )
            binding.add(bound.limits.index(limit))
    unproved = [bound.limits[i] for i in range(len(bound.limits)) if i not in binding]
    assert not unproved, (
        f"{bound.path}: no preset makes these limits bind, so none proves them: {unproved}"
    )


def test_every_editable_module_declares_bounds_and_the_catalogue_holds_them() -> None:
    from aia_core.domain.methodology import module_problems

    for module in EDITABLE:
        assert module.bounds, f"{module.id} declares no bound"
        assert module_problems(module) == {}


def test_a_bound_on_a_field_no_step_shows_is_a_catalogue_problem() -> None:
    from dataclasses import replace

    from aia_core.domain.methodology import module_problems
    from aia_core.domain.methodology.catalogue import at_least
    from aia_core.domain.methodology.readiness import READINESS

    broken = replace(
        READINESS,
        bounds=(
            *READINESS.bounds,
            Bound("sample_size.nowhere", (at_least(1),), READINESS.bounds[0].guard),
            Bound("sample_size.min", (at_least("tracked_set.nowhere"),), "aia_core.domain:nothing"),
        ),
    )
    problems = module_problems(broken)
    assert problems["bound:sample_size.nowhere:path"] == "no step shows this field"
    assert problems["bound:sample_size.min"] == "bounded more than once"
    assert (
        problems["bound:sample_size.min:tracked_set.nowhere"]
        == "the limit reads a field no step shows"
    )
    assert "bound:sample_size.min:guard" in problems
