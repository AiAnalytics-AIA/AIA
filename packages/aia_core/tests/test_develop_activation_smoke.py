"""The smoke's activation rows read in the shell (mvp-master-plan MP6).

``bin/smoke.sh`` reads the web's switch, the research workbench, from the deployed ``/config``
(the worker's rows are ``aia_executors.activation``'s). Run here as smoke.sh runs it: its own
``pass``, ``not_ready`` and ``json`` helpers and the row itself, read from smoke.sh, with
``curl`` stubbed on the PATH. A row that is not on is kept as NOT_READY and never fails the
smoke; the closing verdict counts what is not ready.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

SMOKE = (Path(__file__).resolve().parents[3] / "deploy" / "develop" / "bin" / "smoke.sh").read_text(
    encoding="utf-8"
)
HELPERS = ("pass", "not_ready", "json")
ROW = "activation: workbench for the research workbench (AC-02)"


def _lifted() -> str:
    helpers = [
        m.group(0)
        for name in HELPERS
        for m in [re.search(rf"^{name}\(\) \{{.*\}}$", SMOKE, re.M)]
        if m
    ]
    assert len(helpers) == len(HELPERS), "smoke.sh no longer defines every helper the row uses"
    row = re.search(r'^workbench="\$\(.*?\n(?:.*\n)*?else not_ready .*; fi$', SMOKE, re.M)
    assert row, "smoke.sh no longer reads the workbench's row from /config"
    verdict = re.search(r"^NOT_READY_ROWS=.*$", SMOKE, re.M)
    assert verdict, "smoke.sh no longer counts the rows that are not ready"
    return "\n".join([*helpers, row.group(0), verdict.group(0)])


def _run(tmp_path: Path, config: str) -> tuple[subprocess.CompletedProcess[str], str]:
    shims = tmp_path / "shims"
    shims.mkdir()
    curl = shims / "curl"
    curl.write_text(
        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(f'print({config!r})')}\n"
    )
    curl.chmod(0o755)
    python3 = shims / "python3"  # the json helper's, whatever the host's python3 is
    python3.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
    python3.chmod(0o755)
    results = tmp_path / "results"
    results.touch()
    driver = tmp_path / "driver.sh"
    driver.write_text(
        "set -euo pipefail\nFAILED=0\nBASE=https://aia.test\n"
        f"RESULTS={shlex.quote(str(results))}\n"
        + _lifted()
        + '\necho "rows=$NOT_READY_ROWS failed=$FAILED"\n'
    )
    result = subprocess.run(
        ["bash", str(driver)],
        env={"PATH": f"{shims}:/usr/bin:/bin"},  # no venv: the shims stand in for it
        text=True,
        capture_output=True,
        timeout=30,
    )
    return result, results.read_text()


def test_the_workbench_on_is_an_ok_row(tmp_path: Path) -> None:
    result, kept = _run(tmp_path, '{"workbench": true}')
    assert result.returncode == 0, result.stderr
    assert kept == f"ok    {ROW} -- /config reports it on\n"
    assert "rows=0 failed=0" in result.stdout


@pytest.mark.parametrize("config", ['{"workbench": false}', "not json"])
def test_the_workbench_off_or_unread_is_kept_not_ready_and_fails_nothing(
    tmp_path: Path, config: str
) -> None:
    result, kept = _run(tmp_path, config)
    assert result.returncode == 0, result.stderr
    assert kept.startswith(f"NOT_READY  {ROW} -- /config reports workbench '")
    assert "(AIA_WEB_RESEARCH_WORKBENCH)" in kept
    assert "rows=1 failed=0" in result.stdout
