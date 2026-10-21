"""MVP-ACCEPT-2's tier A can fail CI, and nothing else stands in for it.

Plan ``mvp-acceptance-harness`` chunks 3 and 9. The acceptance tree (``tests/acceptance``) runs
in a CI step of its own: collected with every other tree, under a registered marker, writing
JUnit that ``tools/parity_status.py`` judges each criterion by. A green CI said nothing about a
tree no step ran (``.github/workflows/ci.yml`` @ 085abe0: no step named it), so these hold the
wiring itself -- read from the workflow as text, as ``test_parity_matrix.py`` reads it -- and
prove the failing case for real: a deliberately failing acceptance test, run the way CI runs the
step, exits non-zero and fails its criterion; a skipped one is never a pass.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
CI = REPO / ".github" / "workflows" / "ci.yml"
ROOT_CONFIG = REPO / "pyproject.toml"
MATRIX = REPO / "docs" / "migration" / "parity-matrix.json"
ACC = "tests/acceptance/test_mvp_acceptance.py"


def _steps() -> list[str]:
    return re.split(r"\n\s+- (?=name:|uses:|run:)", CI.read_text(encoding="utf-8"))


def _step(needle: str) -> str:
    found = [step for step in _steps() if needle in step]
    assert len(found) == 1, f"{len(found)} CI steps contain {needle!r}"
    return found[0]


def test_the_acceptance_tree_is_collected_with_every_other_tree() -> None:
    step = _step("--collect-only")
    for tree in ("packages/aia_core", "apps/api", "apps/worker", "apps/executors"):
        assert tree in step
    assert "tests/acceptance" in step


def test_the_acceptance_step_is_blocking_selects_the_marker_and_writes_junit() -> None:
    step = _step("pytest tests/acceptance -q -m acceptance")
    assert "--junit-xml=tmp/junit/acceptance.xml" in step
    assert "-o junit_family=xunit1" in step
    assert "AIA_ACCEPTANCE_DATABASE_URL: postgresql" in step
    # Nothing that would let a failure through: the exit code is the step's.
    for escape in ("continue-on-error", "|| true", "set +e", "exit 0"):
        assert escape not in step, escape
    # Its JUnit is uploaded with the rest of the backend job's (tmp/junit/).
    upload = _step("name: junit-backend")
    assert "path: tmp/junit/" in upload


def test_parity_status_is_told_the_acceptance_step_ran() -> None:
    """With ``acceptance`` available, a criterion test the step did not run is a FAIL."""
    step = _step("python tools/parity_status.py --junit")
    assert re.search(r'available="[^"]*\bacceptance\b', step), step


def test_the_marker_is_registered_where_pytest_reads_it() -> None:
    """``--strict-markers`` is on: an unregistered ``acceptance`` would stop collection."""
    text = ROOT_CONFIG.read_text(encoding="utf-8")
    assert '"acceptance: ' in text
    assert 'addopts = "-ra --strict-markers"' in text


def _tree(tmp_path: Path, body: str) -> Path:
    """A throwaway acceptance tree laid out as the real one, with one module."""
    tree = tmp_path / "tests" / "acceptance"
    tree.mkdir(parents=True)
    (tree / "test_mvp_acceptance.py").write_text(body, encoding="utf-8")
    return tree


def _run_like_ci(tmp_path: Path, tree: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    """The acceptance step's command, under the repository's own pytest configuration."""
    xml = tmp_path / "acceptance.xml"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tree),
            "-q",
            "-m",
            "acceptance",
            "-p",
            "no:cacheprovider",
            "-c",
            str(ROOT_CONFIG),
            "--rootdir",
            str(tmp_path),
            f"--junit-xml={xml}",
            "-o",
            "junit_family=xunit1",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return completed, xml


DELIBERATE = """
import pytest

pytestmark = pytest.mark.acceptance


def test_ac01_fails_on_purpose():
    assert False, "deliberately failing: the step must go red"


def test_ac02_is_skipped_on_purpose():
    pytest.skip("deliberately skipped: never a pass")
"""


def test_a_deliberately_failing_acceptance_test_fails_the_step_and_its_criterion(
    tmp_path: Path, tool_loader: Any
) -> None:
    completed, xml = _run_like_ci(tmp_path, _tree(tmp_path, DELIBERATE))
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "1 failed, 1 skipped" in completed.stdout, completed.stdout

    tool = tool_loader("parity_status")
    matrix: dict[str, Any] = copy.deepcopy(json.loads(MATRIX.read_text(encoding="utf-8")))
    for crit in matrix["mvp_acceptance"]["criteria"]:
        crit["tests"] = {
            "AC-01": [f"{ACC}::test_ac01_fails_on_purpose"],
            "AC-02": [f"{ACC}::test_ac02_is_skipped_on_purpose"],
        }.get(crit["id"], [])
    results = tool.merge_results(tool.parse_junit(xml))

    ran = tool.build_report(matrix, results, frozenset({"acceptance"}))
    verdicts = {c["id"]: c["verdict"] for c in ran.acceptance["criteria"]}
    assert verdicts["AC-01"] == "FAIL"
    assert verdicts["AC-02"] == "FAIL", "skipped where the step ran: it should have run"
    assert ran.acceptance["verdict"] == "FAIL" and ran.failed()
    unknown = tool.build_report(matrix, results, None)
    assert {c["id"]: c["verdict"] for c in unknown.acceptance["criteria"]}["AC-02"] == (
        "NOT_EXECUTED"
    )

    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    assert tool.main(["--matrix", str(path), "--junit", str(xml), "--available", "acceptance"]) == 1


def test_a_misspelt_marker_stops_the_step(tmp_path: Path) -> None:
    """``--strict-markers``: a typo is an error, not a test silently left out of ``-m``."""
    body = "import pytest\n\n\n@pytest.mark.acceptence\ndef test_ac01_x():\n    pass\n"
    completed, _ = _run_like_ci(tmp_path, _tree(tmp_path, body))
    assert completed.returncode not in (0, 5), completed.stdout
    assert "acceptence" in completed.stdout + completed.stderr
