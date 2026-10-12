"""The audience filter against 18.6.6's own functions (panel-grounded-respondents 2c).

``tests/fixtures/population_audience/expected.json`` is what the unit's unmodified
``audience.sanitize_filters`` and ``audience._mask`` returned on a fictional panel,
loaded exactly as the unit loads its panel (``tools/audience_capture.py``). Every
comparison here is EXACT. The last tests run :func:`select_audience` over a population
issued by the canonical loader, where AIA refuses what the unit would drop.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import PopulationKind, PopulationSelector, PopulationView
from aia_core.domain.population.audience import (
    AudienceRefused,
    audience_mask,
    column_type,
    factor,
    sanitize_filters,
    select_audience,
    subpanel_filters,
)
from aia_core.domain.population.subpanels import BUILTIN_SUBPANELS

FIXTURES = Path(__file__).parent / "fixtures" / "population_audience"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))
CASES: list[dict[str, Any]] = json.loads((FIXTURES / "cases.json").read_text("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _columns() -> dict[str, Sequence[str | None]]:
    """The fictional panel as AIA's parser holds it, plus the unit's derived columns."""
    reader = csv.reader(io.StringIO((FIXTURES / "panel.csv").read_text("utf-8")))
    header, *rows = list(reader)
    columns: dict[str, Sequence[str | None]] = {
        name: tuple(None if row[i] == "" else row[i] for row in rows)
        for i, name in enumerate(header)
    }
    columns.update({k: tuple(v) for k, v in EXPECTED["derived_columns"].items()})
    return columns


COLUMNS = _columns()


# --------------------------------------------------------------------------- #
# The fixture is the one the unit produced
# --------------------------------------------------------------------------- #


def test_the_fixture_is_pinned_to_its_inputs_and_the_unit_sources() -> None:
    assert _sha(FIXTURES / "panel.csv") == EXPECTED["panel_sha256"]
    assert _sha(FIXTURES / "cases.json") == EXPECTED["cases_sha256"]
    # A re-extracted unit with different sources needs a fresh capture.
    for name, sha in EXPECTED["unit_sources"].items():
        assert _sha(UNIT / name) == sha, f"{name} changed; re-run tools/audience_capture.py"
    assert [c["id"] for c in CASES] == [c["id"] for c in EXPECTED["cases"]]


# --------------------------------------------------------------------------- #
# Kinds: the unit's rule on the column pandas reads
# --------------------------------------------------------------------------- #


def test_every_factor_has_the_units_kind_and_range() -> None:
    found = {name: factor(name, COLUMNS) for name in COLUMNS}
    assert {n for n, f in found.items() if f is not None} == set(EXPECTED["factors"])
    for name, want in EXPECTED["factors"].items():
        got = found[name]
        assert got is not None
        assert (got.kind, got.filterable) == (want["kind"], want["filterable"]), name
        if want["kind"] == "numeric":
            assert (got.minimum, got.maximum) == (want["min"], want["max"]), name


@pytest.mark.parametrize(
    ("cells", "expected"),
    [
        (("1", "0", "1"), "int"),
        (("1", None, "0"), "float"),  # a missing cell makes an integer column float
        (("1.5", "2"), "float"),
        (("True", "false"), "bool"),
        (("True", None), "text"),  # pandas leaves a bool column with a gap as object
        (("NA", "3"), "float"),  # "NA" is one of pandas' missing-value tokens
        (("a", "1"), "text"),
        ((None, None), "float"),
    ],
)
def test_a_column_is_typed_as_read_csv_types_it(
    cells: tuple[str | None, ...], expected: str
) -> None:
    assert column_type("any", cells) == expected


def test_the_column_the_unit_forces_to_text_stays_text() -> None:
    assert column_type("occupation_isco08", ("0110", "2512")) == "text"


# --------------------------------------------------------------------------- #
# sanitize_filters + _mask, case by case
# --------------------------------------------------------------------------- #


def _kept_as_fixture(clean: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, rule in clean.items():
        if rule.interval is not None:
            out[name] = {"interval": list(rule.interval)}
            continue
        typed = [{"type": type(v).__name__, "str": str(v)} for v in rule.values]
        out[name] = {"value": typed[0]} if len(typed) == 1 else {"values": typed}
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_filter_keeps_drops_and_selects_what_the_unit_does(case: dict[str, Any]) -> None:
    want = next(c for c in EXPECTED["cases"] if c["id"] == case["id"])
    clean, dropped = sanitize_filters(COLUMNS, case["filters"])
    assert _kept_as_fixture(clean) == want["kept"]
    assert dropped == want["dropped"]
    assert list(audience_mask(COLUMNS, clean)) == want["rows"]


def test_a_two_item_list_is_an_interval_only_on_a_numeric_dimension() -> None:
    numeric, _ = sanitize_filters(COLUMNS, {"prijem_decile": [1, 2]})
    category, _ = sanitize_filters(COLUMNS, {"vek_skupina": ["18-29", "30-44"]})
    assert numeric["prijem_decile"].interval == (1.0, 2.0)
    assert category["vek_skupina"].interval is None
    assert [str(v) for v in category["vek_skupina"].values] == ["18-29", "30-44"]


# --------------------------------------------------------------------------- #
# select_audience over a population the canonical loader issued
# --------------------------------------------------------------------------- #


def _analysis_population(session: Session, synthetic_population: Any) -> Any:
    from test_population_runtime import OPERATOR, LifeStageEnricher, import_label

    rt = PopulationRuntime(
        session,
        contract=synthetic_population.contract,
        source=synthetic_population.source,
        enricher=LifeStageEnricher(),
    )
    # The lineage v1_4 is built from, and the STATIC anchor LIVE needs first.
    import_label(rt, synthetic_population, "v1_BASE")
    anchor = import_label(rt, synthetic_population, "v1_1")
    rt.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=OPERATOR,
        reason="the reproducibility anchor",
    )
    version = import_label(rt, synthetic_population, "v1_4")
    rt.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=version.version_id,
        operator=OPERATOR,
        reason="the audience filter's test population",
    )
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"), view=PopulationView.ANALYSIS)
    return rt.load(binding)


def test_select_audience_returns_the_rows_and_the_filters_as_applied(
    session: Session, synthetic_population: Any
) -> None:
    population = _analysis_population(session, synthetic_population)
    ages = population.column("vek")
    selection = select_audience(population, {"vek": {"min": 30, "max": 80}})
    assert selection.rows == tuple(
        i for i, a in enumerate(ages) if a is not None and 30 <= float(a) <= 80
    )
    assert selection.filters_json() == {"vek": {"min": 30.0, "max": 80.0}}
    assert selection.population_rows == population.row_count


def test_select_audience_with_no_filter_is_the_whole_population(
    session: Session, synthetic_population: Any
) -> None:
    population = _analysis_population(session, synthetic_population)
    assert select_audience(population, {}).rows == tuple(range(population.row_count))


def test_a_filter_the_unit_would_drop_refuses_the_selection_with_every_reason(
    session: Session, synthetic_population: Any
) -> None:
    population = _analysis_population(session, synthetic_population)
    with pytest.raises(AudienceRefused) as refused:
        select_audience(population, {"vek": "abc", "neexistuje": 1})
    assert refused.value.reason == "sampling_filter_invalid"
    assert refused.value.reasons == (
        "vek: očekáván interval min/max",
        "neexistuje: není podporovaná filtrační dimenze",
    )


def test_an_unclassified_derived_dimension_is_refused_by_the_field_policy(
    session: Session, synthetic_population: Any
) -> None:
    """The unit filtered on its derived dimensions; AIA asks the field policy first, and
    an unclassified derived field may serve no use until the data owner classifies it."""
    population = _analysis_population(session, synthetic_population)
    stages = [s for s in population.column("life_stage_derived") if s is not None]
    with pytest.raises(AudienceRefused) as refused:
        select_audience(population, {"life_stage_derived": stages[0]})
    assert refused.value.reason == "sampling_field_refused"
    assert refused.value.reasons == ("life_stage_derived: unclassified_derived_field",)


def test_an_audience_with_no_row_is_refused(session: Session, synthetic_population: Any) -> None:
    population = _analysis_population(session, synthetic_population)
    with pytest.raises(AudienceRefused) as refused:
        select_audience(population, {"vek": {"min": 101, "max": 120}})
    assert refused.value.reason == "sampling_empty"


# --------------------------------------------------------------------------- #
# Built-in subpanels go through the same filter
# --------------------------------------------------------------------------- #


def test_every_builtin_subpanel_is_a_filter_on_its_one_field() -> None:
    for subpanel in BUILTIN_SUBPANELS:
        filters = subpanel_filters(subpanel)
        rule = subpanel.filter
        assert list(filters) == [rule.field]
        if rule.equals is not None:
            assert filters[rule.field] == rule.equals
        else:
            assert filters[rule.field] == [rule.minimum, rule.maximum]


def test_a_subpanel_selects_what_the_equivalent_filter_selects() -> None:
    students = next(s for s in BUILTIN_SUBPANELS if s.filter.field == "is_student")
    clean, dropped = sanitize_filters(COLUMNS, subpanel_filters(students))
    assert dropped == []
    want = next(c for c in EXPECTED["cases"] if c["id"] == "C11_binary_int_column")
    assert list(audience_mask(COLUMNS, clean)) == want["rows"]


def test_a_flag_subpanel_on_a_column_with_a_gap_is_refused_as_in_the_unit() -> None:
    """``is_parent`` with an empty cell is a float column to pandas: the unit keys its
    values "1.0", so the subpanel's ``1`` matches nothing and 18.6.6 refuses the
    sample (fixture C12). AIA refuses it the same way rather than widen the audience."""
    parents = next(s for s in BUILTIN_SUBPANELS if s.filter.field == "is_parent")
    _, dropped = sanitize_filters(COLUMNS, subpanel_filters(parents))
    assert dropped == ["is_parent: žádná zadaná hodnota v panelu neexistuje"]
