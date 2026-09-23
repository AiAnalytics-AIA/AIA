"""The parity verdict tool must never turn "did not run" into "passed".

``tools/parity_status.py`` derives a verdict per capability from the parity
matrix and a run's JUnit XML. The distinction it exists for is between a gate
that passed and a gate that simply did not execute -- skipped because the
reference was absent, or never collected because a test was renamed. CI read
94 skips as a green parity job for weeks (OI-1); these tests pin the rules that
stop that recurring.

Synthetic matrices and synthetic JUnit are used throughout, plus one run over
the committed matrix, so the rules are tested without any reference present.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "parity_status.py"
MATRIX_PATH = REPO_ROOT / "docs" / "migration" / "parity-matrix.json"
MATRIX_DOC = REPO_ROOT / "docs" / "migration" / "parity-matrix.md"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    """Import the tool by path -- `tools/` is a script directory, not a package."""
    spec = importlib.util.spec_from_file_location("parity_status", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["parity_status"] = module
    spec.loader.exec_module(module)
    return module


def junit(tmp_path: Path, body: str, name: str = "run.xml") -> Path:
    path = tmp_path / name
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>')
    return path


def case(file: str, name: str, outcome: str = "passed", classname: str = "") -> str:
    inner = {"passed": "", "failed": "<failure/>", "error": "<error/>", "skipped": "<skipped/>"}
    return (
        f'<testcase classname="{classname}" file="{file}" name="{name}">{inner[outcome]}</testcase>'
    )


def gate(
    gid: str, kind: str, tests: list[str], requires: list[str] | None = None
) -> dict[str, Any]:
    return {"id": gid, "kind": kind, "tests": tests, "requires": requires or []}


def capability(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "owner": {"workstream": "ws", "confirmed": True},
        "implementation_state": "IMPLEMENTED",
        "parity_type": "EXACT",
        "release_blocker": {"blocking": True, "reason": "r"},
        "high_risk": [],
        "fixtures": [],
        "gates": [],
    }
    base.update(overrides)
    return base


REF = "packages/aia_core/tests/test_ref.py"
PROD = "packages/aia_core/tests/test_prod.py"


# --------------------------------------------------------------------------- #
# Reading JUnit
# --------------------------------------------------------------------------- #


def test_parses_xunit1_outcomes(tool: ModuleType, tmp_path: Path) -> None:
    path = junit(
        tmp_path,
        case("tests/test_ref.py", "test_a")
        + case("tests/test_ref.py", "test_b", "failed")
        + case("tests/test_ref.py", "test_c", "error")
        + case("tests/test_ref.py", "test_d", "skipped"),
    )
    outcomes = {c.name: c.outcome for c in tool.parse_junit(path)}
    assert outcomes == {
        "test_a": "passed",
        "test_b": "failed",
        "test_c": "failed",
        "test_d": "skipped",
    }


def test_recovers_file_and_class_from_an_xunit2_classname(tool: ModuleType, tmp_path: Path) -> None:
    body = '<testcase classname="packages.aia_core.tests.test_ref.TestThing" name="test_a"/>'
    (parsed,) = tool.parse_junit(junit(tmp_path, body))
    assert parsed.file == "packages/aia_core/tests/test_ref.py"
    assert parsed.name == "TestThing::test_a"


def test_a_failure_anywhere_wins_then_any_pass(tool: ModuleType) -> None:
    tc = tool.TestCase
    merged = tool.merge_results(
        [
            tc("f.py", "a", "skipped"),
            tc("f.py", "a", "passed"),
            tc("f.py", "b", "passed"),
            tc("f.py", "b", "failed"),
            tc("f.py", "c", "skipped"),
        ]
    )
    assert merged == {("f.py", "a"): "passed", ("f.py", "b"): "failed", ("f.py", "c"): "skipped"}


def test_rootdir_relative_paths_match_repository_paths(tool: ModuleType) -> None:
    assert tool._same_file(REF, "tests/test_ref.py")
    assert tool._same_file(REF, REF)
    assert not tool._same_file(REF, "tests/test_other.py")
    assert not tool._same_file(REF, "ref.py")


def test_a_named_test_matches_its_parametrizations_and_nothing_else(tool: ModuleType) -> None:
    results = {
        ("tests/test_ref.py", "test_a"): "passed",
        ("tests/test_ref.py", "test_a[x]"): "passed",
        ("tests/test_ref.py", "test_ab"): "failed",
    }
    assert tool.matching_outcomes(f"{REF}::test_a", results) == ["passed", "passed"]
    assert sorted(tool.matching_outcomes(REF, results)) == ["failed", "passed", "passed"]


def test_one_test_under_two_rootdirs_is_merged_before_it_is_judged(tool: ModuleType) -> None:
    """Found running the CI sequence against real PostgreSQL: the concurrency
    step reports ``tests/test_x.py`` (package rootdir) and passes, the SQLite
    step reports ``packages/aia_core/tests/test_x.py`` (root rootdir) and skips.
    Judged per path, that pass read as "skipped"; judged per test, it is a pass.
    """
    results = {
        ("tests/test_ref.py", "test_a"): "passed",
        ("packages/aia_core/tests/test_ref.py", "test_a"): "skipped",
    }
    assert tool.matching_outcomes(f"{REF}::test_a", results) == ["passed"]
    g = gate("c/g", "production_contract", [f"{REF}::test_a"], ["postgres"])
    assert tool.evaluate_gate(g, results, frozenset({"postgres"})).verdict == "PASS"


# --------------------------------------------------------------------------- #
# Gate verdicts
# --------------------------------------------------------------------------- #


def test_no_results_means_nothing_executed(tool: ModuleType) -> None:
    result = tool.evaluate_gate(gate("c/g", "golden_fixture", [REF]), None, None)
    assert result.verdict == "NOT_EXECUTED"


def test_a_skipped_gate_is_not_executed_never_passed(tool: ModuleType) -> None:
    results = {("tests/test_ref.py", "test_a"): "skipped"}
    result = tool.evaluate_gate(gate("c/g", "reference_comparison", [REF]), results, None)
    assert result.verdict == "NOT_EXECUTED"
    assert result.skipped == 1


def test_a_partially_skipped_gate_is_not_a_pass(tool: ModuleType) -> None:
    results = {
        ("tests/test_ref.py", "test_a"): "passed",
        ("tests/test_ref.py", "test_b"): "skipped",
    }
    result = tool.evaluate_gate(gate("c/g", "reference_comparison", [REF]), results, None)
    assert result.verdict == "NOT_EXECUTED"


def test_an_uncollected_test_is_not_executed(tool: ModuleType) -> None:
    """A renamed test must not vanish from the gate and leave it green."""
    results = {("tests/test_ref.py", "test_a"): "passed"}
    g = gate("c/g", "production_contract", [f"{REF}::test_a", f"{REF}::test_renamed"])
    assert tool.evaluate_gate(g, results, None).verdict == "NOT_EXECUTED"


def test_not_running_where_it_could_have_is_a_failure(tool: ModuleType) -> None:
    results = {("tests/test_ref.py", "test_a"): "skipped"}
    g = gate("c/g", "golden_fixture", [REF], ["reference_repo"])
    assert tool.evaluate_gate(g, results, frozenset({"reference_repo"})).verdict == "FAIL"
    assert tool.evaluate_gate(g, results, frozenset({"postgres"})).verdict == "NOT_EXECUTED"


def test_every_test_passing_passes_the_gate(tool: ModuleType) -> None:
    results = {("tests/test_ref.py", "test_a"): "passed", ("tests/test_ref.py", "t[1]"): "passed"}
    g = gate("c/g", "golden_fixture", [f"{REF}::test_a", f"{REF}::t"])
    result = tool.evaluate_gate(g, results, None)
    assert result.verdict == "PASS"
    assert result.passed == 2


def test_one_failure_fails_the_gate(tool: ModuleType) -> None:
    results = {("tests/test_ref.py", "test_a"): "passed", ("tests/test_ref.py", "test_b"): "failed"}
    assert tool.evaluate_gate(gate("c/g", "golden_fixture", [REF]), results, None).verdict == "FAIL"


# --------------------------------------------------------------------------- #
# Capability verdicts
# --------------------------------------------------------------------------- #


PASSING = {("tests/test_ref.py", "t"): "passed", ("tests/test_prod.py", "t"): "passed"}


def test_no_parity_required_is_not_required(tool: ModuleType) -> None:
    cap = capability(parity_type="NO_PARITY_REQUIRED", release_blocker={"blocking": False})
    assert tool.evaluate_capability("x.y", cap, {}, PASSING, None).verdict == "NOT_REQUIRED"


@pytest.mark.parametrize("parity_type", ["EXACT", "NUMERICAL", "SEMANTIC"])
def test_production_only_tests_cannot_establish_parity_with_the_reference(
    tool: ModuleType, parity_type: str
) -> None:
    """Self-consistency is not equivalence. These types need a reference-backed gate."""
    cap = capability(parity_type=parity_type, gates=[gate("x.y/p", "production_contract", [PROD])])
    status = tool.evaluate_capability("x.y", cap, {}, PASSING, None)
    assert status.verdict == "NOT_RUNNABLE"
    assert "no reference-backed gate" in status.detail


def test_an_intentional_difference_passes_on_the_test_of_the_new_behaviour(
    tool: ModuleType,
) -> None:
    cap = capability(
        parity_type="INTENTIONAL_DIFFERENCE",
        gates=[gate("x.y/p", "production_contract", [PROD])],
    )
    assert tool.evaluate_capability("x.y", cap, {}, PASSING, None).verdict == "PASS"
    no_test = capability(parity_type="INTENTIONAL_DIFFERENCE")
    assert tool.evaluate_capability("x.y", no_test, {}, PASSING, None).verdict == "NOT_RUNNABLE"


def test_an_ungated_fixture_leaves_the_capability_not_runnable(tool: ModuleType) -> None:
    fixtures = {
        "F1": {"gates_capability": True, "gate": {"state": "AWAITING_IMPLEMENTATION"}},
        "F2": {"gates_capability": False, "gate": {"state": "AWAITING_CAPTURE"}},
    }
    cap = capability(fixtures=["F1", "F2"], gates=[gate("x.y/r", "golden_fixture", [REF])])
    status = tool.evaluate_capability("x.y", cap, fixtures, PASSING, None)
    assert status.verdict == "NOT_RUNNABLE"
    assert status.missing == ["F1: AWAITING_IMPLEMENTATION"]


def test_a_failure_outranks_a_missing_gate(tool: ModuleType) -> None:
    fixtures = {"F1": {"gates_capability": True, "gate": {"state": "AWAITING_IMPLEMENTATION"}}}
    cap = capability(fixtures=["F1"], gates=[gate("x.y/r", "golden_fixture", [REF])])
    results = {("tests/test_ref.py", "t"): "failed"}
    assert tool.evaluate_capability("x.y", cap, fixtures, results, None).verdict == "FAIL"


def test_release_ready_needs_a_pass_and_a_finished_implementation(tool: ModuleType) -> None:
    gates = [gate("x.y/r", "reference_comparison", [REF])]
    done = tool.evaluate_capability("x.y", capability(gates=gates), {}, PASSING, None)
    partial = tool.evaluate_capability(
        "x.y", capability(gates=gates, implementation_state="PARTIAL"), {}, PASSING, None
    )
    assert done.verdict == partial.verdict == "PASS"
    assert done.release_ready and not partial.release_ready


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #


def _status(tool: ModuleType, cid: str, **kw: Any) -> Any:
    defaults: dict[str, Any] = {
        "owner": "ws",
        "owner_confirmed": True,
        "implementation_state": "IMPLEMENTED",
        "parity_type": "EXACT",
        "verdict": "NOT_RUNNABLE",
        "release_blocker": True,
        "release_ready": False,
        "high_risk": [],
    }
    defaults.update(kw)
    return tool.CapabilityStatus(id=cid, **defaults)


def test_ranking_puts_the_riskiest_unverified_capability_first(tool: ModuleType) -> None:
    statuses = [
        _status(tool, "a.off_path", release_blocker=False, high_risk=["R1"]),
        _status(tool, "b.unstarted_r1", implementation_state="NOT_STARTED", high_risk=["R1"]),
        _status(tool, "c.built_r10", high_risk=["R10"]),
        _status(tool, "d.built_r2_semantic", high_risk=["R2"], parity_type="SEMANTIC"),
        _status(tool, "e.failed", release_blocker=False, verdict="FAIL"),
        _status(tool, "f.ready", verdict="PASS", release_ready=True),
        _status(tool, "g.not_required", verdict="NOT_REQUIRED"),
        _status(
            tool,
            "h.passing_partial",
            implementation_state="PARTIAL",
            verdict="PASS",
            high_risk=["R1"],
        ),
    ]
    ranked = [s.id for s in tool.rank_unverified(statuses)]
    assert ranked == [
        "e.failed",  # a failed gate outranks everything
        "d.built_r2_semantic",  # built, blocker, R2 beats R10
        "c.built_r10",
        "b.unstarted_r1",  # not built yet: a risk for later, not unverified code
        "h.passing_partial",  # gates pass; incomplete, not unverified
        "a.off_path",
    ]


# --------------------------------------------------------------------------- #
# The committed matrix
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def matrix(tool: ModuleType) -> dict[str, Any]:
    data: dict[str, Any] = tool.load_matrix(MATRIX_PATH)
    return data


def test_the_declared_picture_contains_no_pass(tool: ModuleType, matrix: dict[str, Any]) -> None:
    """With no run supplied, nothing may read as verified."""
    report = tool.build_report(matrix, None, None)
    assert report.counts.get("PASS", 0) == 0
    assert report.counts.get("FAIL", 0) == 0
    assert sum(report.counts.values()) == 78
    assert report.highest_risk_unverified
    assert report.acceptance["verdict"] == "NOT_RUNNABLE"


def test_a_failed_gate_test_fails_the_cli(tool: ModuleType, tmp_path: Path) -> None:
    body = case("tests/test_sociomap_engine.py", "test_f9_manual_drag_is_a_view_override", "failed")
    path = junit(tmp_path, body)
    assert tool.main(["--junit", str(path)]) == 1
    assert tool.main(["--junit", str(junit(tmp_path, "", "empty.xml"))]) == 0


def test_the_cli_writes_json_and_markdown(tool: ModuleType, tmp_path: Path) -> None:
    out_json, out_md = tmp_path / "s.json", tmp_path / "s.md"
    assert tool.main(["--json", str(out_json), "--markdown", str(out_md)]) == 0
    report = json.loads(out_json.read_text())
    assert len(report["capabilities"]) == 78
    assert "No test results were supplied" in out_md.read_text()


def test_the_markdown_matrix_is_rendered_from_the_json(
    tool: ModuleType, matrix: dict[str, Any]
) -> None:
    """The human table cannot drift from the tracker: it is generated from it."""
    document = MATRIX_DOC.read_text(encoding="utf-8")
    assert tool.TABLE_BEGIN in document, "parity-matrix.md lost its generated section"
    expected = tool.splice_table(document, tool.render_table(matrix))
    assert document == expected, (
        "docs/migration/parity-matrix.md is stale. Regenerate it with\n"
        "  python tools/parity_status.py render --write docs/migration/parity-matrix.md"
    )


def test_the_rendered_table_has_one_row_per_capability(
    tool: ModuleType, matrix: dict[str, Any]
) -> None:
    rows = [line for line in tool.render_table(matrix).splitlines() if line.startswith("| `")]
    assert len(rows) == 78
    tampered = copy.deepcopy(matrix)
    tampered["capabilities"]["pipeline.stages"]["implementation_state"] = "PARTIAL"
    assert tool.render_table(tampered) != tool.render_table(matrix)
