"""deploy/reference: the 18.6.6 unit beside the product, never part of it (ADR 0018).

The unit has no authentication (AIA-reference R14), holds the only copy of the
working content not yet migrated (OI-58), and must never again be something
the product needs. So: it is published only through a basic-auth gate on the
host's loopback; its working volume is external, never created and never
removed by these scripts; and the product and the reference share no file,
network or Compose project. The Compose file is validated with Docker in CI
(develop-host-config); these read the files as text and run the scripts with
``docker`` stubbed.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
REFERENCE = REPO / "deploy" / "reference"
COMPOSE = REFERENCE / "docker-compose.yml"
GATE = REFERENCE / "Caddyfile"
DEVELOP = REPO / "deploy" / "develop"


def _service(name: str) -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|^[a-z]|\Z)", text, re.M | re.S)
    assert match, name
    return match.group(1)


def test_the_unit_is_reached_only_through_the_gate_on_the_hosts_loopback() -> None:
    unit, gate = _service("legacy-panel"), _service("gate")
    assert "ports:" not in unit, "the unit itself is never published"
    published = re.findall(
        r'^\s+- "([^"]+)"$', gate.split("ports:", 1)[1].split("volumes:", 1)[0], re.M
    )
    assert published == ["127.0.0.1:${AIA_REFERENCE_PORT:-8765}:8765"]
    rules = GATE.read_text(encoding="utf-8")
    body = rules[rules.index(":8765 {") :]
    assert body.index("basic_auth") < body.index("reverse_proxy legacy-panel:8765")
    assert "admin off" in rules


def test_the_working_volume_is_the_one_the_product_used_and_is_never_created_here() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    volumes = text[text.index("\nvolumes:\n") :]
    assert "    external: true\n" in volumes
    assert "name: ${AIA_REFERENCE_STATE_VOLUME:-aia-develop_legacy_state}" in volumes
    assert "legacy_state:/app" in _service("legacy-panel")


def test_it_starts_only_when_asked_and_shares_nothing_with_the_product() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert re.search(r"^name: aia-reference$", text, re.M)
    for service in ("legacy-panel", "gate"):
        assert 'restart: "no"' in _service(service)
        assert "networks: [reference]" in _service(service)
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "internal" not in code and "edge" not in code
    # The reference sources nothing of the product's scripts (it may name them in a message).
    for script in (REFERENCE / "bin").glob("*.sh"):
        sourced = re.findall(r"^\s*(?:\.|source)\s+(\S+)", script.read_text(encoding="utf-8"), re.M)
        assert all("develop" not in x for x in sourced), (script.name, sourced)
    for path in [
        DEVELOP / "docker-compose.yml",
        DEVELOP / "Caddyfile",
        *(DEVELOP / "bin").glob("*.sh"),
    ]:
        lines = [
            x
            for x in path.read_text(encoding="utf-8").splitlines()
            if not x.lstrip().startswith("#")
        ]
        assert not any("deploy/reference" in x and "README" not in x for x in lines), path.name


def test_no_script_removes_the_volume() -> None:
    for script in (REFERENCE / "bin").glob("*.sh"):
        text = script.read_text(encoding="utf-8")
        for removal in ("--volumes", "down -v", "volume rm", "volume prune", "volume create"):
            code = "\n".join(x for x in text.splitlines() if not x.lstrip().startswith("#"))
            assert removal not in code, f"{script.name}: {removal}"


@pytest.fixture
def stubbed(tmp_path: Path) -> dict[str, object]:
    for tool in ("bash", "cat", "date", "printf", "dirname", "pwd"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is not installed")
    commands = tmp_path / "commands"
    commands.mkdir()
    log = tmp_path / "docker-calls"
    (commands / "docker").write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> {log}\n'
        'if [[ "$1 $2" == "volume inspect" ]]; then [ -n "$HAS_VOLUME" ]; exit; fi\n'
        "exit 0\n"
    )
    (commands / "docker").chmod(0o755)
    (commands / "aws").write_text("#!/bin/bash\nexit 0\n")
    (commands / "aws").chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIA_IMAGE_REGISTRY=example.invalid\nAWS_REGION=eu-central-1\nAIA_OPS_BUCKET=ops\n"
        "AIA_LEGACY_BASIC_USER=oracle\nAIA_LEGACY_BASIC_HASH=x\n"
    )
    env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}", "ENV_FILE": str(env_file)}
    return {"env": env, "log": log}


def test_up_refuses_a_missing_volume_before_pulling_anything(stubbed: dict[str, object]) -> None:
    env = dict(stubbed["env"])  # type: ignore[call-overload]
    env["HAS_VOLUME"] = ""
    result = subprocess.run(
        ["bash", str(REFERENCE / "bin" / "up.sh"), "abc1234"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "working volume aia-develop_legacy_state does not exist" in result.stderr
    calls = Path(stubbed["log"]).read_text()  # type: ignore[arg-type]
    assert "pull" not in calls and " up " not in f" {calls} "


def test_down_stops_the_containers_and_keeps_the_volume(stubbed: dict[str, object]) -> None:
    env = dict(stubbed["env"])  # type: ignore[call-overload]
    env["HAS_VOLUME"] = "1"
    result = subprocess.run(
        ["bash", str(REFERENCE / "bin" / "down.sh")], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    (call,) = [x for x in Path(stubbed["log"]).read_text().splitlines() if x]  # type: ignore[arg-type]
    assert call.startswith("compose ") and call.endswith(" down")
    assert "volume aia-develop_legacy_state is kept" in result.stdout
