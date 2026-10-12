"""The audience factor catalogue against 18.6.6's own function (panel-grounded-respondents 6b).

``tests/fixtures/audience_filter/catalogue.json`` is what the unit's unmodified
``audience_dimensions.catalog(df, include_research_only=True)`` returned on the audience
filter's fictional panel, loaded and enriched exactly as the unit's route served it
(``tools/audience_capture.py``). The comparison is EXACT but for the three keys AIA states
differently (the module's docstring).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.population import (
    UnknownDatasetVersion,
    VersionIntegrityError,
)
from aia_core.domain.population.audience_catalogue import (
    AUDIENCE_CATALOGUE_VERSION,
    audience_catalogue,
    catalogue_of,
)
from aia_core.infrastructure.tables import PopulationVersionAudienceCatalogueRow

FIXTURES = Path(__file__).parent / "fixtures" / "audience_filter"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))


def _columns() -> dict[str, tuple[str | None, ...]]:
    """The fictional panel as AIA's parser holds it, plus the unit's derived columns."""
    header, *rows = list(csv.reader(io.StringIO((FIXTURES / "rows.csv").read_text("utf-8"))))
    columns = {
        name: tuple(None if row[i] == "" else row[i] for row in rows)
        for i, name in enumerate(header)
    }
    columns.update({k: tuple(v) for k, v in EXPECTED["derived_columns"].items()})
    return columns


COLUMNS = _columns()
CAPTURED: dict[str, Any] = json.loads((FIXTURES / "catalogue.json").read_text("utf-8"))
UNIT_ONLY = ("version", "base_columns", "runtime_columns")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_fixture_is_the_one_the_unit_produced_on_these_rows() -> None:
    assert _sha(FIXTURES / "rows.csv") == CAPTURED["panel_sha256"]
    for name, sha in CAPTURED["unit_sources"].items():
        assert _sha(UNIT / name) == sha, f"{name} changed; re-run tools/audience_capture.py"


def test_the_catalogue_is_the_units_exactly() -> None:
    unit = {k: v for k, v in CAPTURED["catalogue"].items() if k not in UNIT_ONLY}
    ours = audience_catalogue(COLUMNS)
    assert ours.pop("catalogue_version") == AUDIENCE_CATALOGUE_VERSION
    assert [f["id"] for f in ours["factors"]] == [f["id"] for f in unit["factors"]]
    for got, want in zip(ours["factors"], unit["factors"], strict=True):
        assert got == want, got["id"]
    assert ours == unit


def test_the_fixture_exercises_every_shape_a_factor_takes() -> None:
    """So EXACT above means something: each branch of the unit's _factor is in it."""
    factors = {f["id"]: f for f in CAPTURED["catalogue"]["factors"]}
    kinds = {f["kind"] for f in factors.values()}
    assert kinds == {"numeric", "binary", "category"}
    assert factors["price_sensitivity_1_10"]["scale_hint"] == "1–10"  # noqa: RUF001 - the fixed scale
    assert factors["is_parent"]["non_null"] < 60  # empty cells, a float column's "1.0"
    assert any(f["non_null"] == 0 for f in factors.values())  # a derived column with nothing
    assert factors["PHQ9_2022"]["filterable"] is False and factors["PHQ9_2022"]["sensitive"]
    # A tie in counts: first appearance decides, as value_counts keeps it.
    assert any(
        len({v["count"] for v in f.get("values", [])}) < len(f.get("values", []))
        for f in factors.values()
    )


def test_a_column_the_population_does_not_carry_is_left_out() -> None:
    columns = {k: v for k, v in COLUMNS.items() if k != "kraj"}
    ids = [f["id"] for f in audience_catalogue(columns)["factors"]]
    assert "kraj" not in ids and "vek" in ids


#: The fictional population's dictionary marks one curated column as audit-only.
AUDIT_ONLY = {"is_student": ("core", "CANONICAL_CORE", "C", "AUDIT_ONLY", "no")}


def test_a_population_catalogue_carries_each_factors_policy_answer(
    sampled_population: Any,
) -> None:
    """AIA's addition: the field policy is asked, and a refused factor stays listed."""
    population = sampled_population(policy=AUDIT_ONLY).population
    factors = {f["id"]: f for f in catalogue_of(population)["factors"]}
    assert factors["vek"]["policy_allowed"] is True
    student = factors["is_student"]
    assert student["filterable"] is True  # the unit's catalogue offered it
    assert (student["policy_allowed"], student["policy_reason"]) == (False, "audit_only")
    # The rest of each factor is the pure catalogue's, over the same columns.
    columns = {n: population.column(n) for n in population.fields if n != "_analysis_weight"}
    plain = audience_catalogue(columns)
    assert [
        {k: v for k, v in f.items() if not k.startswith("policy_")} for f in factors.values()
    ] == plain["factors"]


def test_a_versions_catalogue_is_computed_once_and_kept(
    session: Session, sampled_population: Any
) -> None:
    built = sampled_population()
    rt, version_id = built.runtime, built.population.binding.version_id
    assert rt.audience_catalogue(version_id) is None
    assert rt.record_audience_catalogue(version_id, recorded_by="test") is True
    assert rt.record_audience_catalogue(version_id, recorded_by="test") is False  # insert-once
    kept = rt.audience_catalogue(version_id)
    assert kept == catalogue_of(built.population)
    assert kept is not None and kept["catalogue_version"] == AUDIENCE_CATALOGUE_VERSION
    row = session.get(
        PopulationVersionAudienceCatalogueRow, (version_id, AUDIENCE_CATALOGUE_VERSION)
    )
    assert row is not None and row.recorded_by == "test"
    assert row.sha256 == hashlib.sha256(row.content.encode("utf-8")).hexdigest()


def test_a_kept_catalogue_that_does_not_hash_is_refused(
    session: Session, sampled_population: Any
) -> None:
    built = sampled_population()
    rt, version_id = built.runtime, built.population.binding.version_id
    rt.record_audience_catalogue(version_id, recorded_by="test")
    row = session.get(
        PopulationVersionAudienceCatalogueRow, (version_id, AUDIENCE_CATALOGUE_VERSION)
    )
    assert row is not None
    row.content = row.content.replace('"vek"', '"vek2"', 1)
    session.flush()
    with pytest.raises(VersionIntegrityError):
        rt.audience_catalogue(version_id)


def test_an_unknown_version_has_no_catalogue_to_record(sampled_population: Any) -> None:
    rt = sampled_population().runtime
    with pytest.raises(UnknownDatasetVersion):
        rt.record_audience_catalogue("panel_source_population@nope", recorded_by="test")
