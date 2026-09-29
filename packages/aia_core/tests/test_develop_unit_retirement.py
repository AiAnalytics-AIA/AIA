"""The first deploy without the 18.6.6 unit stops its container and keeps its volume.

Until ADR 0018 the develop stack ran the unit as its service ``legacy-panel``,
on the named volume ``aia-develop_legacy_state``: the unit's working databases
and the files people attached (OI-58). The product stack no longer declares
either, so ``compose up --remove-orphans`` removes the old container. Before it
does, the deploy stops the unit the way its service did, and afterwards it fails
if the volume were gone; the smoke check says the product runs no unit and that
the volume is still there.

These run the functions from ``deploy/develop/bin/lib.sh`` in bash, with
``docker`` replaced by a stub on a PATH that holds nothing else.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BIN = REPO / "deploy" / "develop" / "bin"
LIB, DEPLOY, SMOKE = BIN / "lib.sh", BIN / "deploy.sh", BIN / "smoke.sh"
TOOLS = ("bash", "cat", "date", "printf")


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
    return {"bin": bin_dir, "calls": calls, "root": tmp_path}


def _docker(host: dict[str, Path], *, containers: str, volume: bool) -> None:
    """A docker that lists `containers` for the product's unit and has the volume or not."""
    body = (
        f'echo "$*" >> {host["calls"]}\n'
        'case "$1" in\n'
        f'  ps) printf "%s" "{containers}" ;;\n'
        f'  volume) [ "$2" = inspect ] && {"true" if volume else "false"} ;;\n'
        "  stop) true ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    (host["bin"] / "docker").write_text(f"#!/bin/bash\n{body}", encoding="utf-8")
    (host["bin"] / "docker").chmod(0o755)


def _run(host: dict[str, Path], script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(host["bin"] / "bash"), "-c", f'. "{LIB}"; {script}'],
        env={"PATH": str(host["bin"]), "DEPLOY_DIR": str(host["root"] / "deploy")},
        capture_output=True,
        text=True,
        check=False,
    )


def _calls(host: dict[str, Path]) -> list[str]:
    return [line for line in host["calls"].read_text(encoding="utf-8").splitlines() if line]


def test_the_units_container_is_stopped_as_its_service_stopped_it(host: dict[str, Path]) -> None:
    _docker(host, containers="abc123", volume=True)

    result = _run(host, "retire_product_unit")

    assert result.returncode == 0, result.stderr
    assert "docker stop -t 30 abc123" in [f"docker {c}" for c in _calls(host)]
    assert "its volume aia-develop_legacy_state stays" in result.stdout
    # Stopped, never removed, and the volume is not touched at all.
    assert not any(c.startswith(("rm", "volume rm", "volume prune")) for c in _calls(host))


def test_a_host_that_never_ran_the_unit_is_left_alone(host: dict[str, Path]) -> None:
    _docker(host, containers="", volume=False)

    result = _run(host, "retire_product_unit; unit_volume_exists && echo has || echo none")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "none"
    assert not any(c.startswith("stop") for c in _calls(host))


def test_only_the_product_projects_unit_is_found(host: dict[str, Path]) -> None:
    # deploy/reference runs the unit too, as project aia-reference: never the deploy's to stop.
    _docker(host, containers="abc123", volume=True)

    assert _run(host, "product_unit_containers").returncode == 0
    (listing,) = [c for c in _calls(host) if c.startswith("ps")]
    assert "label=com.docker.compose.project=aia-develop" in listing
    assert "label=com.docker.compose.service=legacy-panel" in listing


def test_the_deploy_stops_the_unit_before_replacing_services_and_proves_the_volume_after() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    remembered = text.index("unit_volume_exists && had_unit_volume=1")
    retired = text.index("\nretire_product_unit\n")
    replaced = text.index("up -d --remove-orphans --wait")
    proved = text.index('[ "$had_unit_volume" = 1 ] && ! unit_volume_exists')
    assert remembered < retired < replaced < proved


def test_the_smoke_check_says_the_product_runs_no_unit_and_kept_its_volume() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    assert 'product_unit="$(product_unit_containers)"' in text
    assert "host: the product stack runs no 18.6.6 unit" in text
    assert "if unit_volume_exists; then" in text
