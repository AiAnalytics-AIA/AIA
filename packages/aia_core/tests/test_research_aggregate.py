"""Aggregation against the vendored 18.6.6 unit (PR C chunk 5, OI-62).

The fixtures under ``fixtures/research_aggregate/`` were captured by running the
unit's own ``agreguj_otazku`` (``tools/aggregate_capture.py``) on fictional
datasets. The contract OI-62 decided:

* every estimate, count, weight summary, donor-support field, suppression status,
  distribution and evidence rating is **EXACT** against the unit's output;
* every interval bound lies within the unit's **own** seed-to-seed spread --
  ``mean +/- (4 sd + rounding step)`` over 100 seeds -- because the unit's printed
  bound is one draw of a Monte Carlo estimator, and AIA draws from its own
  generator, not NumPy's stream;
* AIA's bounds are pinned by ``aia_self.json``: same input, same seed, same bounds.

Every fixture and the unit sources it came from are pinned by SHA256 in
``index.json``; a changed unit makes the fixtures known-stale, not quietly wrong.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.research_aggregate import (
    BOOTSTRAP_GENERATOR,
    aggregate_dataset,
    bootstrap_weighted_mean,
    donor_support,
    kish_effective_n,
    weighted_quantile,
)
from aia_core.domain.research_design import ResearchSpecification

FIXTURES = Path(__file__).parent / "fixtures" / "research_aggregate"
REPO = Path(__file__).resolve().parents[3]
UNIT = REPO / "legacy" / "npc-panel-18.6.6" / "app"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
CASES = sorted(p.stem for p in (FIXTURES / "cases").glob("*.json"))

# Keys whose values are interval bounds: compared against the unit's spread.
_INTERVAL_KEYS = {"intervaly_95", "prumer_interval_95", "top2box_interval_95"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    case = json.loads((FIXTURES / "cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    fixture = json.loads((FIXTURES / f"{case_id}.json").read_text(encoding="utf-8"))
    return case, fixture


def _aggregate(case: dict[str, Any]) -> dict[str, Any]:
    spec = ResearchSpecification.model_validate(case["spec"])
    dataset = FieldworkDataset.model_validate(case["dataset"])
    return aggregate_dataset(spec, dataset)


def _at(tree: dict[str, Any], path: str) -> Any:
    node: Any = tree
    for part in path.split("."):
        node = node[part]
    return node


def _flatten(prefix: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out.update(_flatten(f"{prefix}.{k}", v))
        return out
    return {prefix: value}


def test_every_fixture_and_the_unit_it_came_from_are_pinned() -> None:
    for name, digest in INDEX["files"].items():
        assert _sha256(FIXTURES / name) == digest, f"{name} changed; recapture, never edit"
    for name, digest in INDEX["unit_sources"].items():
        assert _sha256(UNIT / name) == digest, f"the unit's {name} changed; recapture"
    assert {Path(n).stem for n in INDEX["files"] if n.startswith("cases/")} == set(CASES)


@pytest.mark.parametrize("case_id", CASES)
def test_estimates_support_and_suppression_are_exact_against_the_unit(case_id: str) -> None:
    case, fixture = _load(case_id)
    ours = _aggregate(case)
    compared = 0
    for path, unit in fixture["expected"].items():
        mine = _at(ours, path)
        for key, value in unit.items():
            if key in _INTERVAL_KEYS:
                continue
            assert key in mine, f"{path}.{key} missing"
            if isinstance(value, float):
                assert math.isclose(mine[key], value, rel_tol=0, abs_tol=1e-9), f"{path}.{key}"
            else:
                assert mine[key] == value, f"{path}.{key}: {mine[key]!r} != {value!r}"
            compared += 1
    assert compared > 0


@pytest.mark.parametrize("case_id", CASES)
def test_every_bound_lies_within_the_units_own_seed_spread(case_id: str) -> None:
    case, fixture = _load(case_id)
    ours = _aggregate(case)
    spread = fixture["bound_spread"]
    checked = 0
    for path, unit in fixture["expected"].items():
        mine = _at(ours, path)
        for key in _INTERVAL_KEYS & set(unit):
            if unit[key] is None:
                assert mine[key] is None
                continue
            for leaf, value in _flatten(f"{path}.{key}", mine[key]).items():
                band = spread[leaf]
                step = 0.01 if key == "prumer_interval_95" else 0.1
                margin = 4 * band["sd"] + step
                assert abs(value - band["mean"]) <= margin, (
                    f"{leaf}: AIA {value} outside the unit's {band['mean']:.3f} +/- {margin:.3f}"
                )
                checked += 1
    assert checked == len(spread), "every captured bound is checked"


def test_aias_own_bounds_are_pinned() -> None:
    """The self-fixture: AIA's generator gives the same bounds for the same input."""
    pinned = json.loads((FIXTURES / "aia_self.json").read_text(encoding="utf-8"))
    for case_id in CASES:
        case, _ = _load(case_id)
        assert _aggregate(case) == pinned[case_id], case_id
        assert pinned[case_id]["bootstrap_generator"] == BOOTSTRAP_GENERATOR


def test_the_artifact_carries_its_origin_and_generator() -> None:
    case, _ = _load(CASES[0])
    ours = _aggregate(case)
    assert ours["data_origin"] == "SYNTHETIC_FIXTURE"
    assert ours["validation_status"] == "UNVALIDATED"
    assert ours["respondents"] == len(case["dataset"]["respondents"])


# --------------------------------------------------------------------------- #
# The unit's edge cases, by hand
# --------------------------------------------------------------------------- #


def test_kish_and_donor_support_follow_the_units_thresholds() -> None:
    assert kish_effective_n([1.0, 1.0, 1.0, 1.0]) == 4.0
    assert kish_effective_n([]) == 0.0 and kish_effective_n([0.0, -1.0]) == 0.0
    for donors, status in (
        (24, "SUPPRESS"),
        (25, "INDICATIVE"),
        (49, "INDICATIVE"),
        (50, "REPORTABLE"),
    ):
        ids = [f"d{i}" for i in range(donors)]
        support = donor_support(ids, [1.0] * donors)
        assert support["support_status"] == status and support["n_unique_layer_donors"] == donors
    repeated = donor_support(["a", "a", "a", "b"], [1.0] * 4)
    assert repeated["max_donor_share"] == 0.75
    assert repeated["effective_n_combined"] == 2.0  # kish 4 x (2 donors / 4 rows)


def test_a_single_donor_has_no_interval_to_draw_and_says_so() -> None:
    result = bootstrap_weighted_mean([1.0, 2.0, 3.0], [1.0] * 3, reps=10, seed=1, donors=["a"] * 3)
    assert result == {"estimate": 2.0, "low": 2.0, "high": 2.0, "reps": 0}
    assert bootstrap_weighted_mean([1.0], [1.0], reps=10, seed=1, donors=None) is None


def test_the_weighted_median_interpolates_like_numpy() -> None:
    assert weighted_quantile([1.0, 2.0, 3.0, 4.0], [1.0] * 4, 0.5) == 2.0
    assert weighted_quantile([5.0], [2.0], 0.5) == 5.0
    assert weighted_quantile([], [], 0.5) is None
