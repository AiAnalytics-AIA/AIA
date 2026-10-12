"""18.6.6's evidence derivation, ported EXACT (population-operations P4b).

The fixtures are the unit's own ``materialize_evidence_dimension`` over fictional rows
(``tools/materialize_capture.py``); this port must write the same value for every row.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.population import MaterializedKind
from aia_core.domain.population.derivation import (
    DerivationRefused,
    EvidencePredictor,
    EvidenceSpec,
    derive_dimension,
    derive_dimension_as_unit,
    sanitize_dimension_id,
)

FIXTURES = Path(__file__).parent / "fixtures" / "materialize_dimension"
ROOT = Path(__file__).resolve().parents[3]
UNIT = ROOT / "legacy" / "npc-panel-18.6.6" / "app"
WEIGHT = "vaha_strukturalni_2025"

# The unit's kind words (audience_dimensions.py:321-342).
_KINDS = {
    "binary": MaterializedKind.BINARY,
    "boolean": MaterializedKind.BINARY,
    "prevalence": MaterializedKind.BINARY,
    "scale_1_10": MaterializedKind.SCALE_1_10,
    "1_10": MaterializedKind.SCALE_1_10,
    "continuous": MaterializedKind.SCALE_1_10,
}


def _expected() -> dict[str, Any]:
    return json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


def _cases() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))


def _population() -> tuple[list[str], dict[str, list[float | None]], list[float | None]]:
    """The rows as pandas types them: a column is numeric when every present value is."""
    with (FIXTURES / "rows.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    numeric: dict[str, list[float | None]] = {}
    for name in rows[0]:
        if name == "panel_row_id":
            continue
        try:
            numeric[name] = [float(r[name]) if r[name] != "" else None for r in rows]
        except ValueError:
            continue  # a text column: no numeric dtype, no usable predictor
    return [r["panel_row_id"] for r in rows], numeric, numeric[WEIGHT]


def _spec(raw: dict[str, Any]) -> EvidenceSpec | None:
    kind_word = str(raw.get("kind") or raw.get("scale") or "binary").lower()
    kind = _KINDS.get(kind_word)
    if kind is None:
        return None
    target = raw.get("target_prevalence" if kind is MaterializedKind.BINARY else "target_mean")
    return EvidenceSpec(
        kind=kind,
        target=float(target) if target is not None else float("nan"),
        predictors=tuple(
            EvidencePredictor(
                column=str(p.get("column") or p.get("id") or ""),
                negative=str(p.get("direction") or "positive").lower()
                in {"negative", "-", "inverse"},
                strength=float(p.get("strength") or p.get("weight") or 1.0),
            )
            for p in raw.get("predictors") or []
        ),
    )


def test_the_fixtures_are_the_ones_the_unit_produced_from_these_inputs() -> None:
    expected = _expected()
    assert (
        expected["rows_sha256"] == hashlib.sha256((FIXTURES / "rows.csv").read_bytes()).hexdigest()
    )
    assert (
        expected["cases_sha256"]
        == hashlib.sha256((FIXTURES / "cases.json").read_bytes()).hexdigest()
    )
    source = UNIT / "audience_dimensions.py"
    if source.exists():
        assert (
            expected["unit_sources"]["audience_dimensions.py"]
            == hashlib.sha256(source.read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_every_row_gets_the_value_the_unit_wrote(case: dict[str, Any]) -> None:
    got_expected = {c["id"]: c for c in _expected()["cases"]}[case["id"]]
    row_ids, columns, weights = _population()
    spec = _spec(case["spec"])
    if "refused" in got_expected:
        if spec is None:
            return  # an unsupported kind cannot be named here: MaterializedKind has two
        if spec.kind is MaterializedKind.BINARY and spec.target != spec.target:
            return  # a missing target: the typed spec cannot hold one (E03)
        with pytest.raises(DerivationRefused) as refused:
            derive_dimension_as_unit(
                row_ids, columns, weights, dimension_id=case["dimension_id"], spec=spec
            )
        assert str(refused.value) == got_expected["refused"]
        return
    assert spec is not None
    got = derive_dimension_as_unit(
        row_ids, columns, weights, dimension_id=case["dimension_id"], spec=spec
    )
    assert got.dimension_id == got_expected["dimension_id"]
    assert got_expected["row_ids"] == row_ids
    assert list(got.values) == [float(v) for v in got_expected["values"]]
    anchor = got_expected["target_anchor"]
    assert got.target == anchor["target"]
    assert got.achieved == anchor["achieved"]
    assert [p.column for p in got.usable] == [
        str(p.get("column") or p.get("id")) for p in got_expected["predictors"]
    ]


def test_aia_refuses_what_the_unit_materialized_from_noise_alone() -> None:
    # M06: the only predictor has one value, so the unit's score is the hash noise and its
    # values say nothing about anyone. AIA refuses; the unit's behaviour is kept above.
    case = {c["id"]: c for c in _cases()}["M06_only_flat_predictor"]
    row_ids, columns, weights = _population()
    spec = _spec(case["spec"])
    assert spec is not None
    with pytest.raises(DerivationRefused) as refused:
        derive_dimension(row_ids, columns, weights, dimension_id=case["dimension_id"], spec=spec)
    assert refused.value.reason == "no_varying_predictor"
    # A case with a varying predictor is the unit's, value for value.
    m05 = {c["id"]: c for c in _cases()}["M05_flat_predictor_skipped"]
    spec5 = _spec(m05["spec"])
    assert spec5 is not None
    kept = derive_dimension(row_ids, columns, weights, dimension_id=m05["dimension_id"], spec=spec5)
    unit = derive_dimension_as_unit(
        row_ids, columns, weights, dimension_id=m05["dimension_id"], spec=spec5
    )
    assert kept == unit


def test_the_dimension_id_is_the_units() -> None:
    assert sanitize_dimension_id("Kupuje BIO") == "kupuje_bio"
    assert sanitize_dimension_id("!!!") == ""
    assert sanitize_dimension_id("  ranní   káva ") == "rann_k_va"
