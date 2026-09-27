"""The smoke check judges the 18.6.6 unit once it has finished starting.

The unit is recreated on every deploy (its image is tagged by SHA) and hydrates
its data on start, so its healthcheck says "starting" for up to its start period
(``legacy/npc-panel-18.6.6/Dockerfile``: 120 s). The deploy deliberately does not
wait for it, so ``smoke.sh`` used to read that state once: *Deploy develop* runs 29
and 30 (2026-09-27) failed on ``state 'starting'`` while every other check passed.

These run ``legacy_unit_health`` from ``deploy/develop/bin/lib.sh`` in bash, with
``docker`` and ``sleep`` replaced by stubs on a PATH that holds nothing else.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
LIB = REPO / "deploy" / "develop" / "bin" / "lib.sh"
SMOKE = REPO / "deploy" / "develop" / "bin" / "smoke.sh"
TOOLS = ("bash", "cat", "date")


@pytest.fixture
def host(tmp_path: Path) -> dict[str, Path]:
    for tool in TOOLS:
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is not installed")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in TOOLS:
        (bin_dir / tool).symlink_to(shutil.which(tool) or tool)
    calls = tmp_path / "calls"
    calls.write_text("", encoding="utf-8")
    sleeps = tmp_path / "sleeps"
    sleeps.write_text("", encoding="utf-8")
    (bin_dir / "sleep").write_text(f'#!/bin/bash\necho "$1" >> {sleeps}\n', encoding="utf-8")
    (bin_dir / "sleep").chmod(0o755)
    return {"bin": bin_dir, "calls": calls, "sleeps": sleeps, "root": tmp_path}


def _docker(host: dict[str, Path], states: list[str]) -> None:
    """A docker whose `inspect` answers each state in turn, then the last one forever."""
    script = host["root"] / "states"
    script.write_text("\n".join(states) + "\n", encoding="utf-8")
    body = (
        f'n=$(($(cat {host["calls"]} | wc -l) + 1)); echo "$*" >> {host["calls"]}\n'
        f'[ "$1" = inspect ] || exit 1\n'
        f'[ -n "${{!#}}" ] || exit 1\n'
        f"total=$(wc -l < {script})\n"
        f'[ "$n" -gt "$total" ] && n=$total\n'
        f'sed -n "${{n}}p" {script}\n'
    )
    for tool in ("wc", "sed"):
        target = host["bin"] / tool
        if not target.exists():
            target.symlink_to(shutil.which(tool) or tool)
    (host["bin"] / "docker").write_text(f"#!/bin/bash\n{body}", encoding="utf-8")
    (host["bin"] / "docker").chmod(0o755)


def _health(host: dict[str, Path], container: str = "abc123", limit: str = "150") -> str:
    result = subprocess.run(
        [str(host["bin"] / "bash"), "-c", f'. "{LIB}"; legacy_unit_health "{container}"'],
        env={
            "PATH": str(host["bin"]),
            "DEPLOY_DIR": str(host["root"] / "deploy"),
            "LEGACY_START_WAIT_SECONDS": limit,
            "LEGACY_POLL_SECONDS": "5",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _count(path: Path) -> int:
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line])


def test_a_unit_still_starting_is_waited_for_until_it_is_healthy(host: dict[str, Path]) -> None:
    _docker(host, ["starting", "starting", "starting", "healthy"])

    assert _health(host) == "healthy"
    assert _count(host["calls"]) == 4
    assert _count(host["sleeps"]) == 3


def test_a_unit_that_never_finishes_starting_is_judged_at_the_limit(
    host: dict[str, Path],
) -> None:
    _docker(host, ["starting"])

    assert _health(host, limit="20") == "starting"
    assert _count(host["sleeps"]) == 4, "20 s at 5 s steps, then judged"


def test_an_unhealthy_unit_fails_at_once(host: dict[str, Path]) -> None:
    _docker(host, ["unhealthy"])

    assert _health(host) == "unhealthy"
    assert _count(host["sleeps"]) == 0


def test_a_missing_unit_is_reported_missing_without_waiting(host: dict[str, Path]) -> None:
    _docker(host, ["healthy"])

    assert _health(host, container="") == "missing"
    assert _count(host["sleeps"]) == 0


def test_the_smoke_check_reads_the_unit_through_the_wait() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    assert 'legacy_health="$(legacy_unit_health "$legacy_id")"' in text
    assert ".State.Health.Status" not in text, "the one-shot health read is gone"
