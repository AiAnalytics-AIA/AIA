"""The layering guard must fail when it cannot see, and exempt only the file it names.

``tools/layer_check.sh`` is the enforcement behind ARCHITECTURE.md §3. Two of its
behaviours made it quietly weaker than it read. A rule whose path did not exist
printed ``skip`` and passed, so a moved package turned its rules off without a red
run. And an exemption was a ``grep --exclude`` basename, so exempting
``infrastructure/tables.py`` also exempted ``infrastructure/report_docx/tables.py``
and every other ``tables.py`` under the rule's path.

These tests source the real script, which then defines ``forbid`` and stops
before its own rules, and run ``forbid`` against a scratch tree. The working
repository is never read, so this holds on a dirty checkout.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "layer_check.sh"
RULE = "no widget is built outside its factory"
PATTERN = r"Widget\("


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    if shutil.which("bash") is None or shutil.which("grep") is None:
        pytest.skip("bash and grep are needed to run the layering guard")
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "tools" / "layer_check.sh")
    pkg = root / "pkg"
    (pkg / "infra" / "report").mkdir(parents=True)
    (pkg / "infra" / "factory.py").write_text("w = Widget()\n", encoding="utf-8")
    (pkg / "infra" / "clean.py").write_text("x = 1\n", encoding="utf-8")
    return root


def _forbid(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    quoted = " ".join("'" + a.replace("'", "'\\''") + "'" for a in args)
    driver = f'source tools/layer_check.sh\nforbid {quoted}\nexit "$FAILED"\n'
    return subprocess.run(
        ["bash", "-c", driver],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_sourcing_the_script_runs_none_of_its_rules(scratch: Path) -> None:
    result = subprocess.run(
        ["bash", "-c", "source tools/layer_check.sh; echo sourced"],
        cwd=scratch,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout == "sourced\n", result.stdout + result.stderr
    assert result.returncode == 0


def test_a_violation_is_caught(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg")

    assert result.returncode != 0, result.stdout
    assert f"FAIL  {RULE}" in result.stdout, result.stdout
    assert "pkg/infra/factory.py:1:w = Widget()" in result.stdout


def test_an_exempted_path_passes(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg", "pkg/infra/factory.py")

    assert result.returncode == 0, result.stdout
    assert f"ok    {RULE}" in result.stdout, result.stdout


def test_a_trailing_slash_on_the_rule_path_changes_nothing(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg/", "pkg/infra/factory.py")

    assert result.returncode == 0, result.stdout
    assert f"ok    {RULE}" in result.stdout, result.stdout


def test_a_same_basename_file_in_another_directory_is_not_exempt(scratch: Path) -> None:
    """The defect: --exclude=tables.py also exempted report_docx/tables.py."""
    (scratch / "pkg" / "infra" / "report" / "factory.py").write_text(
        "y = Widget()\n", encoding="utf-8"
    )

    result = _forbid(scratch, RULE, PATTERN, "pkg", "pkg/infra/factory.py")

    assert result.returncode != 0, result.stdout
    assert f"FAIL  {RULE}" in result.stdout, result.stdout
    assert "pkg/infra/report/factory.py:1:y = Widget()" in result.stdout
    assert "pkg/infra/factory.py:" not in result.stdout


def test_a_basename_exemption_exempts_nothing(scratch: Path) -> None:
    """A bare basename is a path from the root that does not exist: it fails."""
    result = _forbid(scratch, RULE, PATTERN, "pkg", "factory.py")

    assert result.returncode != 0, result.stdout
    assert "exempt path factory.py does not exist" in result.stdout


def test_a_missing_rule_path_fails(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg/moved_away")

    assert result.returncode != 0, result.stdout
    assert f"FAIL  {RULE}" in result.stdout, result.stdout
    assert "path pkg/moved_away does not exist" in result.stdout
    assert "skip" not in result.stdout


def test_a_missing_exempt_path_fails(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg", "pkg/infra/renamed.py")

    assert result.returncode != 0, result.stdout
    assert "exempt path pkg/infra/renamed.py does not exist" in result.stdout


def test_a_clean_single_file_path_passes(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg/infra/clean.py")

    assert result.returncode == 0, result.stdout
    assert f"ok    {RULE}" in result.stdout, result.stdout


def test_a_violating_single_file_path_names_the_file(scratch: Path) -> None:
    result = _forbid(scratch, RULE, PATTERN, "pkg/infra/factory.py")

    assert result.returncode != 0, result.stdout
    assert "pkg/infra/factory.py:1:w = Widget()" in result.stdout
