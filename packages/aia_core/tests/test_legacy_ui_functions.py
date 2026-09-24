"""The function-level parity harness: the UI function ledger, unit-captured fixtures, first gates.

The 88 research functions of ``ui_app.html`` (``docs/migration/legacy-ui-functions.json``)
move server-side from their JavaScript. Before a port, a fixture is captured by
running the original function under Node (``tools/ui_function_capture.py``) on
authored inputs; after the port, the AIA implementation is compared with that
fixture at its tolerance. Everything here runs without the reference repository:
the oracle's own bytes are in the vendored unit. With a checkout, the ledger is
also checked against the reference's UI capability ledger at its pinned hash.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.sociomap.metrics import (
    NormalizationMode,
    ObjectMetric,
    build_normalizer,
    object_metric,
)

REPO = Path(__file__).resolve().parents[3]
LEDGER_PATH = REPO / "docs" / "migration" / "legacy-ui-functions.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "legacy_ui"
CASES = FIXTURES / "cases"
INDEX = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
LEDGER: dict[str, Any] = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
ARCHIVE_SHA256 = "86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216"
UI_AREAS = frozenset(
    {
        "shell",
        "sociomapping",
        "simulation",
        "data_library",
        "audience",
        "project",
        "questionnaire",
        "results",
        "ai_runtime",
        "analysis",
        "workflow",
        "population",
        "reports",
        "governance",
        "settings",
    }
)
STATUSES = frozenset({"LEGACY", "PORTING", "PORTED"})
SERIALISATION = 1e-9


@pytest.fixture(scope="module")
def ui(tool_loader: Any) -> Any:
    """The ``tools/ui_functions.py`` module."""
    return tool_loader("ui_functions")


@pytest.fixture(scope="module")
def extracted(ui: Any) -> dict[str, Any]:
    js = ui.extract_scripts(ui.load_ui_app())
    return {"js": js, "functions": ui.extract_functions(js), "arrows": ui.arrow_helpers(js)}


def _fixture(fixture_id: str) -> dict[str, Any]:
    entry = INDEX["fixtures"][fixture_id]
    document: dict[str, Any] = json.loads((FIXTURES / entry["file"]).read_text(encoding="utf-8"))
    return document


# --------------------------------------------------------------------------- #
# Extraction agrees with the reference's own count
# --------------------------------------------------------------------------- #


def test_extraction_finds_every_declaration(ui: Any, extracted: dict[str, Any]) -> None:
    found, scanned = ui.check_agreement(extracted["js"])
    assert found == scanned == 737, "the reference ledger counts 737 function declarations"
    assert LEDGER["extraction"] == {
        "functions": len(extracted["functions"]),
        "declarations_found": found,
        "declarations_scanned": scanned,
    }


def test_the_effective_binding_is_the_last_assignment_when_one_follows(
    ui: Any, extracted: dict[str, Any]
) -> None:
    # briefFingerprint1780 is declared once and reassigned twice; the browser runs
    # the last, which is the one that reads the selected problem types.
    js = extracted["js"]
    declared = extracted["functions"]["briefFingerprint1780"].body
    effective = ui.effective_binding(js, "briefFingerprint1780")
    assert effective != declared
    assert effective.startswith("var briefFingerprint1780=function(){")
    assert "selectedProblemTypes1789()" in effective and effective.endswith("};")


def test_the_effective_binding_is_the_declaration_when_nothing_reassigns_it(
    ui: Any, extracted: dict[str, Any]
) -> None:
    js = extracted["js"]
    assert ui.effective_binding(js, "defaultsMerge") == extracted["functions"]["defaultsMerge"].body
    assert ui.effective_binding(js, "noSuchFunction1234") is None


def test_the_ledger_pins_the_unit_it_describes(ui: Any) -> None:
    assert LEDGER["unit"]["ui_app_sha256"] == ui.ui_app_sha256()
    assert LEDGER["unit"]["archive_sha256"] == ARCHIVE_SHA256
    assert LEDGER["unit"]["path"] == "legacy/npc-panel-18.6.6/app/ui_app.html"


# --------------------------------------------------------------------------- #
# The UI function ledger
# --------------------------------------------------------------------------- #


def _reference_rows() -> list[dict[str, Any]]:
    return [r for r in LEDGER["functions"] if r["source"] == "reference_ledger"]


def test_the_ledger_holds_the_88_research_functions_and_names_every_addition() -> None:
    rows = LEDGER["functions"]
    names = [r["name"] for r in rows]
    assert len(set(names)) == len(names)
    reference = _reference_rows()
    assert len(reference) == 88
    classes = {r["class"] for r in rows}
    assert classes == {"METHODOLOGY_SEMANTICS", "DETERMINISTIC_COMPUTATION"}
    assert sum(r["class"] == "METHODOLOGY_SEMANTICS" for r in reference) == 38
    assert sum(r["class"] == "DETERMINISTIC_COMPUTATION" for r in reference) == 50
    additions = [r for r in rows if r["source"] == "aia_addition"]
    assert {r["name"] for r in additions} == {"normalizer66"}, (
        "an addition to the reference's 88 is a recorded discrepancy, never a quiet edit"
    )
    for r in additions:
        assert r["reference_class"] and "REF-DISC-" in r["notes"], r["name"]


def test_every_ledger_row_is_well_formed() -> None:
    for r in LEDGER["functions"]:
        assert r["area"] in UI_AREAS, r["name"]
        assert r["status"] in STATUSES, r["name"]
        assert isinstance(r["slice"], int) and r["slice"] >= 2, r["name"]
        assert len(r["source_sha256"]) == 64, r["name"]
        if r["status"] == "LEGACY":
            assert r["implementation"] == [] and r["fixtures"] == [], r["name"]
        else:
            assert r["implementation"], f"{r['name']}: a ported function names its implementation"
            for path in r["implementation"]:
                assert (REPO / path).is_file(), f"{r['name']}: {path} does not exist"
        for fixture_id in r["fixtures"]:
            assert fixture_id in INDEX["fixtures"], (r["name"], fixture_id)
            assert INDEX["fixtures"][fixture_id]["function"] == r["name"]


def test_every_ledger_row_is_current_against_the_unit(ui: Any, extracted: dict[str, Any]) -> None:
    """A regenerated unit that changes a function is known, not guessed."""
    assert ui.check_ledger(LEDGER, extracted["functions"]) == []


def test_nothing_is_ported_yet() -> None:
    """PORTED means parity PASS against unit-captured fixtures for the whole function.

    Replace with the per-function gate assertion when the first row moves.
    """
    assert all(r["status"] != "PORTED" for r in LEDGER["functions"])


def test_the_ledger_agrees_with_the_reference_ui_ledger(reference_repo: Path) -> None:
    path = reference_repo / "ui-capability-ledger.json"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == LEDGER["reference"]["ui_capability_ledger_sha256"]
    )
    reference = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        (f["name"], "METHODOLOGY_SEMANTICS", f["area"]) for f in reference["methodology_functions"]
    } | {
        (f["name"], "DETERMINISTIC_COMPUTATION", f["area"])
        for f in reference["computation_functions"]
    }
    ours = {(r["name"], r["class"], r["area"]) for r in _reference_rows()}
    assert ours == expected
    by_name = {f["name"]: f for f in reference["functions"]}
    for r in LEDGER["functions"]:
        assert r["reference_chars"] == by_name[r["name"]]["chars"], r["name"]


# --------------------------------------------------------------------------- #
# The unit-captured fixtures are pinned and current
# --------------------------------------------------------------------------- #


def test_index_names_the_unit() -> None:
    assert INDEX["unit"]["archive_sha256"] == ARCHIVE_SHA256
    assert INDEX["unit"]["path"] == "legacy/npc-panel-18.6.6/app/ui_app.html"


def test_index_lists_exactly_the_fixture_files_present() -> None:
    present = {p.name for p in FIXTURES.glob("U*.json")}
    assert present == {e["file"] for e in INDEX["fixtures"].values()}
    assert {p.stem for p in CASES.glob("*.json")} == set(INDEX["fixtures"]), (
        "every fixture has its case file and every case file its fixture"
    )


@pytest.mark.parametrize("fixture_id", sorted(INDEX["fixtures"]))
def test_fixture_matches_its_pin(fixture_id: str) -> None:
    entry = INDEX["fixtures"][fixture_id]
    actual = hashlib.sha256((FIXTURES / entry["file"]).read_bytes()).hexdigest()
    assert actual == entry["sha256"], f"{entry['file']} was edited after it was captured"


@pytest.mark.parametrize("fixture_id", sorted(INDEX["fixtures"]))
def test_fixture_document_is_well_formed(fixture_id: str) -> None:
    document = _fixture(fixture_id)
    entry = INDEX["fixtures"][fixture_id]
    assert document["schema"] == "aia-legacy-ui-fixture-1"
    assert document["fixture_id"] == fixture_id
    assert document["reference_zip_sha256"] == ARCHIVE_SHA256
    assert document["reference_function"] == f"ui_app.html::{entry['function']}"
    assert document["source_sha256"] == entry["source_sha256"]
    assert document["parity_type"] == entry["parity_type"]
    assert document["tolerance"] == entry["tolerance"]
    assert document["capability_id"] == entry["capability"]
    assert set(document["input"]) == set(document["expected_output"]) and document["input"]
    assert document["runtime_environment"]["node"].startswith("v")


@pytest.mark.parametrize("fixture_id", sorted(INDEX["fixtures"]))
def test_fixture_was_captured_from_the_current_function_source(
    fixture_id: str, extracted: dict[str, Any]
) -> None:
    """The unit is regenerated, never edited; when a function changes, its fixture is stale."""
    document = _fixture(fixture_id)
    function = extracted["functions"][INDEX["fixtures"][fixture_id]["function"]]
    assert document["source_sha256"] == function.sha256
    for entry, sha in document["helpers"].items():
        name = entry.split(":", 1)[-1]
        source = (
            extracted["arrows"][name]
            if entry.startswith("arrow:") or name not in extracted["functions"]
            else extracted["functions"][name].body
        )
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == sha, (fixture_id, entry)


def test_every_captured_function_is_in_the_ledger() -> None:
    names = {r["name"] for r in LEDGER["functions"]}
    for fixture_id, entry in INDEX["fixtures"].items():
        assert entry["function"] in names, fixture_id


def test_capture_reproduces_every_fixture(tool_loader: Any) -> None:
    """Re-running the runner reproduces the committed outputs: the capture is deterministic."""
    if shutil.which("node") is None:
        pytest.skip("capture reproducibility needs Node.js on PATH")
    capture = tool_loader("ui_function_capture")
    ui = tool_loader("ui_functions")
    js = ui.extract_scripts(ui.load_ui_app())
    functions = ui.extract_functions(js)
    arrows = ui.arrow_helpers(js)
    for path in sorted(CASES.glob("*.json")):
        case = capture.load_case_file(path)
        assert capture.verify_one(ui, functions, arrows, case) == [], case["fixture_id"]


# --------------------------------------------------------------------------- #
# The first gates: functions already ported, on inputs the reference did not use
# --------------------------------------------------------------------------- #

U01_MODES = {
    "range_negative_spread": NormalizationMode.RANGE,
    "sigma_negative_spread": NormalizationMode.SIGMA,
    "percentile_with_duplicates": NormalizationMode.PERCENTILE,
    "absolute_default_uses_largest_magnitude": NormalizationMode.ABSOLUTE,
    "absolute_with_clipping_bounds": NormalizationMode.ABSOLUTE,
    "absolute_inverted_bounds_fall_back": NormalizationMode.ABSOLUTE,
    "single_value_range": NormalizationMode.RANGE,
    "non_finite_values_are_ignored": NormalizationMode.RANGE,
}


@pytest.mark.parametrize("case", sorted(U01_MODES))
def test_u01_normaliser_matches_the_unit(case: str) -> None:
    fixture = _fixture("U01_normalizer66")
    args = fixture["input"][case]["args"]
    values = [v for v in args[0] if isinstance(v, int | float) and not isinstance(v, bool)]
    bounds = tuple(args[2]) if args[2] is not None else None
    if case == "absolute_inverted_bounds_fall_back":
        # The reference falls back to the largest magnitude; AIA refuses inverted
        # bounds outright (test_normaliser_refuses_inverted_bounds). Recorded as
        # reference behaviour here; the fail-closed difference is deliberate.
        with pytest.raises(ValueError):
            build_normalizer(values, U01_MODES[case], bounds)  # type: ignore[arg-type]
        return
    norm = build_normalizer(values, U01_MODES[case], bounds)  # type: ignore[arg-type]
    expected = fixture["expected_output"][case]
    assert norm.lo == pytest.approx(expected["lo"], abs=SERIALISATION), case
    assert norm.hi == pytest.approx(expected["hi"], abs=SERIALISATION), case
    assert norm.label_cs == expected["label"], case
    probes = fixture["input"][case]["extra"]["probe_points"]
    for probe, want in zip(probes, expected["transform"], strict=True):
        assert norm(probe) == pytest.approx(want, abs=SERIALISATION), (case, probe)


def test_u01_unknown_mode_is_reference_behaviour_that_aia_refuses() -> None:
    """normalizer66 falls through to range on a typo; AIA refuses the mode (fail closed)."""
    fixture = _fixture("U01_normalizer66")
    assert fixture["expected_output"]["unknown_mode_falls_through_to_range"]["label"] == "rozsah"
    with pytest.raises(ValueError):
        NormalizationMode("typo")


def _u02_state(case: str) -> dict[str, Any]:
    fixture = _fixture("U02_objectMetricArray66")
    state: dict[str, Any] = fixture["input"][case]["globals"]["window"]["SOCIOMAP1866"]
    return state


def _effective_matrix(state: dict[str, Any]) -> list[list[float]]:
    matrix = [list(map(float, row)) for row in state["objects"]["matrix"]]
    if state["sourceMode"] == "scenario":
        for key, value in state["edits"].items():
            i, j = (int(k) for k in key.split(":"))
            matrix[i][j] = 0.0 if i == j else float(value)
    return matrix


@pytest.mark.parametrize(
    ("case", "metric"),
    [
        ("relation_classic", ObjectMetric.RELATION_CLASSIC),
        ("mean_rating", ObjectMetric.MEAN_RATING),
        ("support_n", ObjectMetric.SUPPORT_N),
        ("tscore_via_unknown_id", ObjectMetric.RELATION_CLASSIC_TSCORE),
        ("constant_relations_give_tscore_fifty", ObjectMetric.RELATION_CLASSIC_TSCORE),
        ("relation_classic_under_a_scenario_edit", ObjectMetric.RELATION_CLASSIC),
    ],
)
def test_u02_object_metrics_match_the_unit(case: str, metric: ObjectMetric) -> None:
    fixture = _fixture("U02_objectMetricArray66")
    state = _u02_state(case)
    objects = state["objects"]
    values = object_metric(
        metric,
        mean_rating=objects.get("mean_rating"),
        support_n=objects.get("support_n"),
        relation=_effective_matrix(state),
    )
    assert values == pytest.approx(fixture["expected_output"][case], abs=SERIALISATION), case


def test_u02_a_missing_rating_is_zero_in_the_reference_and_null_here() -> None:
    """``safeNum(null)`` is ``Number(null) === 0``: the reference scores a missing rating as 0.

    That is anti-pattern A4 (unknown scored as a value). AIA keeps ``None`` and
    refuses a non-numeric string instead of turning it into ``null``. Recorded as
    reference behaviour; the difference is deliberate.
    """
    fixture = _fixture("U02_objectMetricArray66")
    assert fixture["expected_output"]["missing_ratings_are_null"] == [4.5, 0, None]
    assert object_metric(ObjectMetric.MEAN_RATING, mean_rating=[4.5, None, None]) == (
        4.5,
        None,
        None,
    )
    with pytest.raises(ValueError):
        object_metric(ObjectMetric.MEAN_RATING, mean_rating=[4.5, None, "n/a"])  # type: ignore[list-item]


def test_u02_unknown_metric_id_is_reference_behaviour_that_aia_refuses() -> None:
    """objectMetricArray66 answers a T-score for any unknown id; AIA refuses the id."""
    fixture = _fixture("U02_objectMetricArray66")
    assert fixture["input"]["tscore_via_unknown_id"]["args"] == ["relation_norm"]
    with pytest.raises(ValueError):
        ObjectMetric("relation_norm")
