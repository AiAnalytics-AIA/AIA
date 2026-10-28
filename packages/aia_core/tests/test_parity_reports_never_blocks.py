"""Parity reports and never blocks (the owner, 2026-10-19, MVP-21; ``mvp-cohesion.md`` F9;
plan ``mvp-acceptance-harness`` chunk 8).

The jobs that compare AIA with 18.6.6 -- ``parity``, ``golden-fixtures`` (the reference
repository's contract parity) and ``oracle-parity`` -- still run every test and keep every
failure in their JUnit, but a comparison that differed no longer fails the job or holds back a
deploy: ``tools/parity_report_only.py`` turns test bodies that failed, with no error, into a
warning and a step-summary line, and ``tools/parity_status.py --report-only`` prints each
capability's FAIL without failing the run. What stays blocking: a suite that errored or could not
run (the reference and oracle ratchets among them), the golden fixtures' pin check, an acceptance
criterion's FAIL, a malformed matrix, and every test outside those jobs (the vendored Sociomap
golden fixtures F1-F9 among them). The workflow is read as text, as ``test_parity_matrix.py``
reads it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CI = REPO / ".github" / "workflows" / "ci.yml"
SCRIPT = REPO / "tools" / "parity_report_only.py"
#: The jobs that compare AIA with 18.6.6, and the pytest command each runs through the wrapper.
COMPARISONS = {
    "parity": "pytest packages/aia_core -q -m parity",
    "golden-fixtures": "pytest packages/aia_core/tests/test_population_reference_parity.py",
    "oracle-parity": "pytest packages/aia_core -q -m oracle",
}
#: Jobs whose comparisons never block a deploy, even through parity-status.
NEVER_BLOCK_A_DEPLOY = {"parity", "oracle-parity"}


def _job(name: str) -> str:
    """One job's block of the workflow: from its key to the next top-level job."""
    text = CI.read_text(encoding="utf-8")
    found = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z-]*:\n|\Z)", text, re.M | re.S)
    assert found, name
    return found.group(1)


def _case(outcome: str) -> str:
    inner = {"passed": "", "failed": "<failure/>", "error": "<error/>"}[outcome]
    return f'<testcase classname="c" name="t_{outcome}">{inner}</testcase>'


def _run(
    tmp_path: Path, code: int, outcomes: list[str] | None = None, *, write: bool = True
) -> tuple[subprocess.CompletedProcess[str], str]:
    """The wrapper over a stand-in for pytest that writes the JUnit and exits ``code``."""
    junit = tmp_path / "run.xml"
    body = "".join(_case(o) for o in outcomes or [])
    xml = f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>'
    fake = (
        f"import pathlib, sys; pathlib.Path({str(junit)!r}).write_text({xml!r}); sys.exit({code})"
        if write
        else f"import sys; sys.exit({code})"
    )
    summary = tmp_path / "summary.md"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "A suite",
            sys.executable,
            "-c",
            fake,
            f"--junit-xml={junit}",
        ],
        env={"PATH": "/usr/bin:/bin", "GITHUB_STEP_SUMMARY": str(summary)},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return completed, summary.read_text("utf-8") if summary.exists() else ""


def test_a_comparison_that_differed_is_reported_and_passes_the_step(tmp_path: Path) -> None:
    completed, summary = _run(tmp_path, 1, ["passed", "failed", "failed"])
    assert completed.returncode == 0, completed.stderr
    assert "::warning::A suite: 2 comparison(s) with 18.6.6 failed" in completed.stdout
    assert "### A suite: 2 comparison(s) with 18.6.6 failed" in summary


@pytest.mark.parametrize(
    "outcomes",
    [
        ["error"],  # a fixture broke, or a ratchet (AIA_REQUIRE_*) failed in its fixture
        ["failed", "error"],  # one error is enough: the suite did not run as a comparison
        [],  # exit 1 with nothing failed is not a comparison that differed
    ],
)
def test_an_error_fails_the_step_whatever_else_failed(tmp_path: Path, outcomes: list[str]) -> None:
    completed, summary = _run(tmp_path, 1, outcomes)
    assert completed.returncode == 1
    assert summary == ""


def test_an_unreadable_junit_fails_the_step(tmp_path: Path) -> None:
    completed, summary = _run(tmp_path, 1, write=False)
    assert completed.returncode == 1 and summary == ""


@pytest.mark.parametrize("code", [0, 2, 3, 4, 5])
def test_any_other_exit_is_the_step_s_own(tmp_path: Path, code: int) -> None:
    """A pass passes; a suite that was interrupted, broke, was misused or collected nothing
    did not compare anything, and fails the step."""
    completed, summary = _run(tmp_path, code, ["failed"])
    assert completed.returncode == code
    assert summary == ""


def test_the_golden_fixture_pin_check_still_blocks() -> None:
    """Integrity, not parity: a vendored fixture edited to pass fails its pin here."""
    block = _job("golden-fixtures")
    pins = block[block.index("pytest packages/aia_core/tests/test_golden_fixtures.py") - 40 :]
    pins = pins.split("\n\n", 1)[0]
    assert "parity_report_only" not in pins and "--junit-xml=" in pins


@pytest.mark.parametrize(("job", "command"), sorted(COMPARISONS.items()))
def test_each_comparison_job_runs_its_suite_through_the_report_only_wrapper(
    job: str, command: str
) -> None:
    block = _job(job)
    run = block[block.index("tools/parity_report_only.py") :]
    assert command in run, job
    assert "--junit-xml=" in run, job
    # The comments say "never a `|| true`"; the command must not carry one.
    assert "|| true" not in run.split("\n\n", 1)[0], job
    assert "continue-on-error" not in block, job


def test_parity_status_reports_parity_and_still_blocks_on_acceptance() -> None:
    block = _job("parity-status")
    assert "python tools/parity_status.py" in block and "--report-only" in block
    for escape in ("|| true", "continue-on-error"):
        assert escape not in block, escape
    assert "exit $status" in block


def test_the_deploy_waits_for_no_comparison_job() -> None:
    """Neither directly nor through parity-status: the deploy reads each direct need's result
    by name, because success() also looks through parity-status to the jobs it needs."""
    block = _job("dispatch-develop")
    needs = re.search(r"^    needs: \[(.*)\]$", block, re.M)
    assert needs
    jobs = {j.strip() for j in needs.group(1).split(",")}
    assert not jobs & NEVER_BLOCK_A_DEPLOY, jobs & NEVER_BLOCK_A_DEPLOY
    assert {"backend", "golden-fixtures", "parity-status"} <= jobs
    condition = block[block.index("    if: >-") :].split("\n    runs-on:", 1)[0]
    assert "success()" not in condition
    for job in jobs:
        assert f"needs.{job}.result == 'success'" in condition, job
