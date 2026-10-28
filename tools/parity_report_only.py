#!/usr/bin/env python3
"""Run one 18.6.6 comparison suite so that it reports and never blocks.

    python tools/parity_report_only.py "<label>" pytest ... --junit-xml=PATH ...

Parity reports and never blocks (the owner, 2026-10-19, MVP-21; plan
``mvp-acceptance-harness`` chunk 8). A comparison that ran and differed is a finding to
read, not a reason to stop a merge or a deploy. So exactly one outcome becomes a pass:
pytest exited 1, and its JUnit (``--junit-xml``) shows test bodies that failed and no
errors. That outcome produces a ``::warning::``, a line in the step summary, and exit 0.
The failures stay in the JUnit, where ``parity_status.py`` prints each capability's FAIL.

Every other outcome is the step's own, because then the suite did not compare. An error is
a fixture or setup that broke, and includes the ``AIA_REQUIRE_REFERENCE_REPO`` and
``AIA_REQUIRE_LEGACY_ORACLE`` ratchets, which ``pytest.fail`` in their fixtures. A JUnit
that is missing or unreadable, or any exit but 0 and 1 (interrupted, internal error, usage
error, nothing collected), also fails the step. Never ``|| true``: that would hide a suite
that could not run.

Stdlib only, like the rest of ``tools/``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path

#: pytest's exit when tests ran and some failed.
TESTS_FAILED = 1


def _junit(command: Sequence[str]) -> Path | None:
    for i, arg in enumerate(command):
        if arg.startswith("--junit-xml="):
            return Path(arg.split("=", 1)[1])
        if arg == "--junit-xml" and i + 1 < len(command):
            return Path(command[i + 1])
    return None


def outcome_counts(path: Path) -> tuple[int, int] | None:
    """(failures, errors) among the JUnit's test cases; None when it cannot be read."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    cases = list(root.iter("testcase"))
    failures = sum(1 for c in cases if c.find("failure") is not None)
    errors = sum(1 for c in cases if c.find("error") is not None)
    return failures, errors


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print(f"usage: {Path(__file__).name} <label> <command> [args...]", file=sys.stderr)
        return 64
    label, command = argv[0], list(argv[1:])
    junit = _junit(command)
    if junit is None:
        print(f"{label}: the command names no --junit-xml; nothing to judge by", file=sys.stderr)
        return 64
    status = subprocess.call(command)
    if status != TESTS_FAILED:
        return status
    counts = outcome_counts(junit)
    if counts is None:
        print(f"{label}: pytest failed and its JUnit ({junit}) cannot be read", file=sys.stderr)
        return status
    failures, errors = counts
    if errors or not failures:
        print(
            f"{label}: {errors} error(s) and {failures} failure(s): the suite did not run as a "
            "comparison, so this step fails",
            file=sys.stderr,
        )
        return status
    print(
        f"::warning::{label}: {failures} comparison(s) with 18.6.6 failed. Parity reports and "
        "never blocks (MVP-21); each capability's FAIL is in Parity status."
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(
                f"### {label}: {failures} comparison(s) with 18.6.6 failed\n\n"
                "Reported, not blocking (MVP-21). Each failing capability is listed under "
                "**Parity status**; the tests are in the JUnit artifact.\n"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
