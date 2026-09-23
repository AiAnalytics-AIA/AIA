"""The exposure guard must keep catching agent coordination state in product history.

``tools/exposure_check.sh`` rule 4 refuses a tracked ``.agent-status/`` directory.
The bus lives on the never-merged ``coordination/agent-status`` branch, and it has
reached ``main`` twice anyway: once before ``026577e``, and again through PR #26,
removed by ``7a022b3``. Both times the rule caught it and the red check was merged
over. Nothing in CI can stop a red check being merged; that is branch protection.
What a test can stop is the other way this regresses silently: the rule being
weakened, narrowed or deleted, after which the next merge of the bus would be
green.

So these tests run the real script against a throwaway git repository, tracking
nothing but the script itself, and assert on its verdict. The working repository
is never touched, so this holds on a dirty checkout.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "exposure_check.sh"
RULE = ".agent-status must not be in product history"


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None or shutil.which("bash") is None:
        pytest.skip("git and bash are needed to run the exposure guard")
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(SCRIPT, root / "tools" / "exposure_check.sh")
    _git(root, "init", "-q")
    _git(root, "add", "tools/exposure_check.sh")
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(root / "tools" / "exposure_check.sh")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_clean_tree_passes_the_agent_status_rule(scratch_repo: Path) -> None:
    result = _run(scratch_repo)
    assert f"ok    {RULE}" in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout


def test_tracked_agent_status_fails_the_build(scratch_repo: Path) -> None:
    status = scratch_repo / ".agent-status"
    status.mkdir()
    (status / "simulation-engine.md").write_text("progress\n", encoding="utf-8")
    _git(scratch_repo, "add", ".agent-status/simulation-engine.md")

    result = _run(scratch_repo)

    assert result.returncode != 0, "a tracked .agent-status/ must fail exposure_check"
    assert f"FAIL  {RULE}" in result.stdout, result.stdout
    assert ".agent-status/simulation-engine.md" in result.stdout


def test_an_untracked_agent_status_is_not_product_history(scratch_repo: Path) -> None:
    """The rule reads what is tracked, which is what a merge adds; a local file is not."""
    status = scratch_repo / ".agent-status"
    status.mkdir()
    (status / "simulation-engine.md").write_text("progress\n", encoding="utf-8")

    result = _run(scratch_repo)

    assert f"ok    {RULE}" in result.stdout, result.stdout
