"""The develop host pulls from ECR without keeping a registry token on disk.

``docker login`` wrote the 12-hour ECR token unencrypted into
``~/.docker/config.json``, and Docker warned about it on every deploy. ``ecr_login``
in ``deploy/develop/bin/lib.sh`` now names Amazon's credential helper for the
registry instead (it asks the instance role on each pull), removes a token an
earlier login stored, and falls back to ``docker login`` -- loudly -- only when
the helper cannot be installed.

These run the real function in bash, with ``docker``, ``aws``, ``apt-get`` and the
helper replaced by stubs on a PATH that holds nothing else, so nothing reaches
AWS or the machine's package manager.
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
LIB = REPO / "deploy" / "develop" / "bin" / "lib.sh"
REGISTRY = "123456789012.dkr.ecr.eu-central-1.amazonaws.com"
TOOLS = ("bash", "jq", "mktemp", "date", "chmod", "mv", "mkdir", "rm", "cat")


def _stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


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
    calls.touch()
    _stub(bin_dir, "aws", f'echo "aws $*" >> {calls}; echo registry-token')
    _stub(bin_dir, "docker", f'echo "docker $* stdin=$(cat)" >> {calls}')
    return {"bin": bin_dir, "calls": calls, "docker": tmp_path / "docker", "root": tmp_path}


def _helper(bin_dir: Path) -> None:
    _stub(bin_dir, "docker-credential-ecr-login", "exit 0")


def _ecr_login(host: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": str(host["bin"]),
        "HOME": str(host["root"]),
        "DOCKER_CONFIG": str(host["docker"]),
        "DEPLOY_DIR": str(host["root"] / "deploy"),
        "AIA_IMAGE_REGISTRY": REGISTRY,
        "AWS_REGION": "eu-central-1",
    }
    return subprocess.run(
        [str(host["bin"] / "bash"), "-c", f'. "{LIB}"; ecr_login'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _config(host: dict[str, Path]) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((host["docker"] / "config.json").read_text())
    return loaded


def test_the_helper_replaces_a_stored_token_and_nothing_logs_in(host: dict[str, Path]) -> None:
    _helper(host["bin"])
    host["docker"].mkdir()
    (host["docker"] / "config.json").write_text(
        json.dumps(
            {
                "auths": {REGISTRY: {"auth": "QVdTOnRva2Vu"}, "ghcr.io": {"auth": "b3RoZXI="}},
                "detachKeys": "ctrl-q",
            }
        )
    )

    result = _ecr_login(host)

    assert result.returncode == 0, result.stderr
    config = _config(host)
    assert config["credHelpers"] == {REGISTRY: "ecr-login"}
    assert config["auths"] == {"ghcr.io": {"auth": "b3RoZXI="}}, "only this registry's token goes"
    assert config["detachKeys"] == "ctrl-q"
    assert host["calls"].read_text() == "", "no docker login and no token fetched"
    assert stat.S_IMODE((host["docker"] / "config.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(host["docker"].stat().st_mode) == 0o700
    assert list(host["docker"].glob(".config.json.*")) == []
    assert "nothing stored" in result.stdout


def test_a_host_without_the_helper_installs_it_then_uses_it(host: dict[str, Path]) -> None:
    helper = host["bin"] / "docker-credential-ecr-login"
    _stub(
        host["bin"],
        "apt-get",
        f'echo "apt-get $*" >> {host["calls"]}\n'
        f'[ "$1" = install ] && printf "#!/bin/bash\\nexit 0\\n" > {helper} && chmod 755 {helper}',
    )

    result = _ecr_login(host)

    assert result.returncode == 0, result.stderr
    assert _config(host) == {"credHelpers": {REGISTRY: "ecr-login"}}
    calls = host["calls"].read_text()
    assert "apt-get install -y -qq amazon-ecr-credential-helper" in calls
    assert "docker login" not in calls


def test_without_the_helper_the_deploy_still_pulls_and_says_why(host: dict[str, Path]) -> None:
    _stub(host["bin"], "apt-get", f'echo "apt-get $*" >> {host["calls"]}; exit 100')

    result = _ecr_login(host)

    assert result.returncode == 0, result.stderr
    calls = host["calls"].read_text()
    assert "apt-get update -qq" in calls, "a stale package list is refreshed once"
    assert "aws ecr get-login-password --region eu-central-1" in calls
    assert f"docker login --username AWS --password-stdin {REGISTRY} stdin=registry-token" in calls
    assert "WARNING: the ECR credential helper is not installed" in result.stdout


def test_an_unreadable_docker_config_stops_the_deploy_and_is_left_alone(
    host: dict[str, Path],
) -> None:
    _helper(host["bin"])
    host["docker"].mkdir()
    (host["docker"] / "config.json").write_text("{not json")

    result = _ecr_login(host)

    assert result.returncode != 0
    assert "is not valid JSON" in result.stderr
    assert (host["docker"] / "config.json").read_text() == "{not json"
    assert list(host["docker"].glob(".config.json.*")) == []


def test_every_script_turns_the_helpers_plaintext_cache_off(host: dict[str, Path]) -> None:
    """The helper would otherwise keep the same token in ~/.ecr/cache.json."""
    result = subprocess.run(
        [str(host["bin"] / "bash"), "-c", f'. "{LIB}"; echo "cache=$AWS_ECR_DISABLE_CACHE"'],
        env={"PATH": str(host["bin"]), "DEPLOY_DIR": str(host["root"])},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == "cache=true"
