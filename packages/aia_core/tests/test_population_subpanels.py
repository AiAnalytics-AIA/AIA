"""The 18 built-in subpanels, adopted from 18.6.6 (population-operations P7b).

The catalogue in ``domain/population/subpanels.py`` is a copy of the frozen unit's
``BUILTIN_SUBPANELS_v17.json``; this holds it equal to that file field by field, and that file
equal to the companion the Czech contract pins. Whether a subpanel can be used on a version
is the version's field policy's answer for its filter field, never the catalogue's.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.population import CZ_SYNTHETIC_V17
from aia_core.domain.population.policy import build_field_policy
from aia_core.domain.population.subpanels import (
    BUILTIN_SUBPANELS,
    MEASURED_ON,
    MEASURED_UNDER_WEIGHT,
    SUBPANEL_NOTE,
    BuiltinSubpanel,
    SubpanelFilter,
    UnitMeasurement,
    check_subpanel,
)

UNIT_FILE = (
    Path(__file__).resolve().parents[3]
    / "legacy"
    / "npc-panel-18.6.6"
    / "app"
    / "BUILTIN_SUBPANELS_v17.json"
)


def _unit() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(UNIT_FILE.read_text(encoding="utf-8"))
    return document


def _filter_as_unit(f: SubpanelFilter) -> dict[str, Any]:
    if f.equals is not None:
        return {f.field: f.equals}
    return {f.field: [f.minimum, f.maximum]}


def test_the_catalogue_is_the_units_file_field_by_field() -> None:
    unit = _unit()
    assert (unit["version"], unit["weight"]) == (MEASURED_ON, MEASURED_UNDER_WEIGHT)
    assert len(BUILTIN_SUBPANELS) == len(unit["subpanels"]) == 18
    for ours, theirs in zip(BUILTIN_SUBPANELS, unit["subpanels"], strict=True):
        assert {
            "key": ours.key,
            "name": ours.name,
            "description": ours.description,
            "filter": _filter_as_unit(ours.filter),
            "focus_domains": list(ours.focus_domains),
            "status": ours.status,
            "support_tier": ours.support_tier,
            "note": SUBPANEL_NOTE,
            "rows": ours.measured.rows,
            "weighted_population": ours.measured.weighted_population,
            "unique_core_donors": ours.measured.unique_core_donors,
            "effective_core_donors": ours.measured.effective_core_donors,
            "max_core_reuse": ours.measured.max_core_reuse,
        } == theirs, ours.key


def test_the_units_file_is_the_companion_the_contract_pins() -> None:
    data = UNIT_FILE.read_bytes()
    spec = next(c for c in CZ_SYNTHETIC_V17.companions if c.asset_id == UNIT_FILE.name)
    assert (hashlib.sha256(data).hexdigest(), len(data)) == (spec.sha256, spec.byte_size)


def test_the_counts_were_measured_under_the_contracts_default_weight() -> None:
    default = next(
        w for w in CZ_SYNTHETIC_V17.weight_schemes if w.role == CZ_SYNTHETIC_V17.default_weight_role
    )
    assert default.column == MEASURED_UNDER_WEIGHT


def test_keys_are_unique() -> None:
    keys = [s.key for s in BUILTIN_SUBPANELS]
    assert len(set(keys)) == len(keys)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"field": "vek"}, "a range or a value"),
        ({"field": "vek", "minimum": 1, "maximum": 2, "equals": 1}, "a range or a value"),
        ({"field": "vek", "minimum": 30, "maximum": 18}, "an empty range"),
    ],
)
def test_a_filter_is_a_range_or_a_value(kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        SubpanelFilter(**kwargs)


# ----------------------------------------------------------- the check


def _policy(dictionary_rows: list[dict[str, str]], **extra: dict[str, str]) -> Any:
    rows = [*dictionary_rows, *extra.values()]
    return build_field_policy(rows, dictionary_sha256="0" * 64, weight_columns=())


def _subpanel(field: str) -> BuiltinSubpanel:
    return BuiltinSubpanel(
        key=f"on_{field}",
        name=field,
        description="fictional",
        filter=SubpanelFilter(field=field, equals=1),
        focus_domains=(),
        status="ready",
        support_tier="GOOD",
        measured=UnitMeasurement(1, 1.0, 1, 1.0, 1),
    )


def test_a_filter_field_the_policy_lets_filter_is_usable(
    dictionary_rows: list[dict[str, str]],
) -> None:
    check = check_subpanel(_subpanel("vek"), _policy(dictionary_rows))
    assert (check.usable, check.reason) == (True, None)


def test_a_field_the_version_lacks_is_not_usable_and_says_so(
    dictionary_rows: list[dict[str, str]],
) -> None:
    check = check_subpanel(_subpanel("is_student"), _policy(dictionary_rows))
    assert (check.usable, check.reason) == (False, "unknown_field")


def test_an_audit_only_field_is_not_usable_and_says_so(
    dictionary_rows: list[dict[str, str]],
) -> None:
    audit = {
        "field": "is_audited",
        "block": "provenance",
        "source": "fictional",
        "evidence_status": "PROVENANCE_OR_CORE",
        "production_grade": "T",
        "recommended_use": "AUDIT_ONLY",
        "description": "fictional",
        "persona_eligible": "no",
    }
    check = check_subpanel(_subpanel("is_audited"), _policy(dictionary_rows, audit=audit))
    assert (check.usable, check.reason) == (False, "audit_only")
