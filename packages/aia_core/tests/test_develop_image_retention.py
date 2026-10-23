"""Deletion boundaries and the executable deploy's before-download refusal.

No live Docker, filesystem deletion, registry or AWS account is used. The deploy
harness runs the actual shell script and retention program against a host CLI
double; filesystem capacity is supplied independently of the test machine.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
BIN = ROOT / "deploy/develop/bin"
spec = importlib.util.spec_from_file_location("image_retention", BIN / "image_retention.py")
assert spec and spec.loader
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)
REGISTRY = "registry.example.test"
NOW = datetime(2026, 10, 12, tzinfo=UTC)


def image(n: int, *, age: int = 72, repo: str = "aia-api") -> dict[str, Any]:
    return {
        "Id": f"sha256:{n:064x}",
        "RepoTags": [f"{REGISTRY}/{repo}:{n:040x}"],
        "Created": (NOW - timedelta(hours=age)).isoformat(),
    }


def test_retention_protects_containers_recent_releases_history_and_shared_images() -> None:
    images = [image(n) for n in range(1, 12)]
    images[3]["Created"] = (NOW - timedelta(hours=47)).isoformat()
    images[4]["RepoTags"] = [f"other.example.test/aia-api:{5:040x}"]
    images[5]["RepoTags"] = [*images[5]["RepoTags"], "reference:latest"]
    images[6]["RepoTags"] = []
    images[7]["RepoTags"] = [f"{REGISTRY}/aia-legacy-panel:{8:040x}"]
    images[8]["Created"] = "unknown"
    images[9]["RepoTags"] = [f"{REGISTRY}/aia-web:develop"]
    # 1 is current, 2 rollback (older than the age window), 3 a stopped container.
    selected = retention.candidates(
        images, {images[2]["Id"]}, REGISTRY, [f"{1:040x}", f"{2:040x}"], NOW
    )
    assert [i["Id"] for i in selected] == [images[10]["Id"]]


def test_abbreviated_protected_sha_and_age_boundary_are_conservative() -> None:
    protected = image(1)
    protected["RepoTags"] = [f"{REGISTRY}/aia-web:abcdef1{'2' * 33}"]
    young = image(2, age=47)
    boundary = image(3, age=48)
    future = image(4, age=-1)
    assert retention.candidates(
        [protected, young, boundary, future], set(), REGISTRY, ["abcdef1"], NOW
    ) == [boundary]


def test_unproven_inventory_or_invalid_protection_refuses_deletion() -> None:
    with pytest.raises(ValueError, match="identity"):
        retention.candidates([{"Id": "unknown"}], set(), REGISTRY, [], NOW)
    with pytest.raises(ValueError, match="protected"):
        retention.candidates([image(1)], set(), REGISTRY, ["latest"], NOW)


def test_successful_history_keeps_four_distinct_releases_and_idempotent_redeploy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "state/history.json"
    for n in range(1, 7):
        retention.record(path, f"{n:040x}", f"{n - 1:040x}" if n > 1 else "")
    assert retention.history(path) == [f"{n:040x}" for n in [6, 5, 4, 3]]
    retention.record(path, f"{6:040x}", f"{6:040x}")
    assert retention.history(path) == [f"{n:040x}" for n in [6, 5, 4, 3]]
    retention.record(path, f"{3:040x}", f"{6:040x}")
    assert retention.history(path) == [f"{n:040x}" for n in [3, 6, 5, 4]]
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "data", [{}, {"schema": 1, "releases": ["latest"]}, {"schema": 1, "releases": "invalid"}]
)
def test_corrupt_history_is_never_silently_replaced(tmp_path: Path, data: Any) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    with pytest.raises(ValueError):
        retention.record(path, "a" * 40, "b" * 40)
    assert path.read_bytes() == original


def test_failed_atomic_history_write_keeps_the_previous_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "history.json"
    retention.record(path, "a" * 40, "")
    original = path.read_bytes()

    def refuse(*args: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(retention.os, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        retention.record(path, "b" * 40, "a" * 40)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("free,used,refused", [(8, 40, False), (7, 10, True), (10, 60, True)])
def test_space_gate_checks_available_bytes_and_percentage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, free: int, used: int, refused: bool
) -> None:
    usage = SimpleNamespace(total=100 * 1024**3, free=free * 1024**3, used=used * 1024**3)
    calls = []
    monkeypatch.setattr(retention.shutil, "disk_usage", lambda p: (calls.append(p), usage)[1])
    if refused:
        with pytest.raises(ValueError, match="no images were downloaded"):
            retention.check_disks([tmp_path, tmp_path / "."])
    else:
        retention.check_disks([tmp_path, tmp_path / "."])
    assert len(calls) == 1  # One filesystem, irrespective of how many storage paths.


def test_incomplete_container_inventory_refuses_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        retention, "command", lambda *args: "container\n" if args[1] == "ps" else ""
    )
    with pytest.raises(ValueError, match="incomplete container"):
        retention.inventory()


def _host(
    tmp_path: Path,
    *,
    low_space: bool = False,
    smoke_ok: bool = True,
    removal_ok: bool = True,
    dry: bool = False,
    lock_ok: bool = True,
    warmup: bool = False,
    onlyoffice_enabled: bool = False,
    docs_running: bool = False,
) -> subprocess.CompletedProcess[str]:
    host = tmp_path / "host"
    scripts = host / "bin"
    scripts.mkdir(parents=True)
    # Exercise the first-write branch; rewriting an existing tag uses host GNU
    # sed, whereas this executable harness also runs on macOS.
    (host / ".env").write_text("AWS_REGION=eu-central-1\n")
    for name in ("deploy.sh", "image_retention.py"):
        shutil.copyfile(BIN / name, scripts / name)
    (scripts / "lib.sh").write_text("""set -euo pipefail
COMPOSE=(docker compose)
ENV_FILE="$DEPLOY_DIR/.env"
log(){ printf '%s\\n' "$*"; }
die(){ log "$*"; exit 1; }
require_sha(){ :; }
require_env_file(){ export AIA_IMAGE_REGISTRY=registry.example.test; }
deployed_sha(){ printf '%040d' 1; }
ecr_login(){ printf 'ecr-login\\n' >> "$CALLS"; }
postgres_running(){ return 1; }
unit_volume_exists(){ return 1; }
retire_product_unit(){ :; }
""")
    for name, content in [
        ("population.sh", "exit 0"),
        ("smoke.sh", f"exit {0 if smoke_ok else 1}"),
    ]:
        path = scripts / name
        path.write_text("#!/bin/sh\nprintf '%s\\n' " + name + ' >> "$CALLS"\n' + content + "\n")
        path.chmod(0o755)
    docs = scripts / "docs.sh"
    docs.write_text('#!/bin/sh\nprintf \'docs.sh %s\\n\' "$*" >> "$CALLS"\n')
    docs.chmod(0o755)
    shims = tmp_path / "shims"
    shims.mkdir()
    docker_py = shims / "docker.py"
    # Existing image 1 is in use; 2 is old rollback history; 3 is removable.
    old = [image(n) for n in [1, 2, 3]]
    for i in old:
        i["Created"] = "2020-01-01T00:00:00Z"
    docker_py.write_text("""import os,json,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write('docker '+ ' '.join(args)+'\\n')
if args[:1]==['ps'] and 'label=com.docker.compose.project=aia-docs' in args:
    if os.environ['DOCS_RUNNING']=='1': print('docs-container')
elif args[:1]==['ps']: print('stopped-container')
elif args[:1]==['inspect']: print('sha256:'+format(1,'064x'))
elif args[:2]==['image','ls']: print('\\n'.join(i['Id'] for i in json.loads(os.environ['IMAGES'])))
elif args[:2]==['image','inspect']: print(os.environ['IMAGES'])
elif args[:1]==['info']: print(os.environ['DEPLOY_DIR'])
elif args[:2]==['image','rm']: sys.exit(int(os.environ['RM_FAIL']))
""")
    python_py = shims / "python.py"
    python_py.write_text("""import runpy,sys,os
from types import SimpleNamespace
script=sys.argv.pop(1)
module=runpy.run_path(script,run_name='host_program')
free=1 if os.environ['LOW_SPACE']=='1' else 30
usage=SimpleNamespace(total=77*1024**3,used=40*1024**3,free=free*1024**3)
module['check_disks'].__globals__['shutil'].disk_usage=lambda p: usage
raise SystemExit(module['main']())
""")
    for name, target in [("docker", docker_py), ("python3", python_py)]:
        path = shims / name
        path.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(target))} "$@"\n'
        )
        path.chmod(0o755)
    lock = shims / "flock"
    lock.write_text(f"#!/bin/sh\nexit {0 if lock_ok else 1}\n")
    lock.chmod(0o755)
    state = host / ".deploy-state/successful-releases.json"
    for n in [1, 2] if warmup else [9, 8, 1, 2]:
        retention.record(state, f"{n:040x}", "")
    env = {
        **os.environ,
        "PATH": f"{shims}:{os.environ['PATH']}",
        "DEPLOY_DIR": str(host),
        "CALLS": str(tmp_path / "calls"),
        "IMAGES": json.dumps(old),
        "LOW_SPACE": str(int(low_space)),
        "RM_FAIL": str(int(not removal_ok)),
        "AIA_ONLYOFFICE_ENABLED": "true" if onlyoffice_enabled else "false",
        "DOCS_RUNNING": str(int(docs_running)),
    }
    if dry:
        args = [
            str(shims / "python3"),
            str(scripts / "image_retention.py"),
            "preflight",
            "--registry",
            REGISTRY,
            "--state-file",
            str(state),
            "--deploy-dir",
            str(host),
        ]
    else:
        args = ["bash", str(scripts / "deploy.sh"), f"{4:040x}"]
    return subprocess.run(args, env=env, text=True, capture_output=True, timeout=30)


def test_actual_deploy_cleans_before_pull_and_records_only_after_smoke(tmp_path: Path) -> None:
    result = _host(tmp_path)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text()
    remove = f"docker image rm --no-prune sha256:{3:064x}"
    assert remove in calls
    assert calls.index(remove) < calls.index("ecr-login") < calls.index("pull --quiet")
    assert f"image rm --no-prune sha256:{1:064x}" not in calls
    assert f"image rm --no-prune sha256:{2:064x}" not in calls
    assert "image prune" not in calls and "volume" not in calls and "--force" not in calls
    assert retention.history(tmp_path / "host/.deploy-state/successful-releases.json") == [
        f"{n:040x}" for n in [4, 1, 2, 8]
    ]


@pytest.mark.parametrize("low_space,removal_ok", [(True, True), (False, False)])
def test_actual_deploy_stops_before_download_migration_or_replacement(
    tmp_path: Path, low_space: bool, removal_ok: bool
) -> None:
    result = _host(tmp_path, low_space=low_space, removal_ok=removal_ok)
    assert result.returncode != 0
    calls = (tmp_path / "calls").read_text()
    for refused in ("ecr-login", "pull", "alembic", "compose up"):
        assert refused not in calls
    assert retention.history(tmp_path / "host/.deploy-state/successful-releases.json") == [
        f"{n:040x}" for n in [2, 1, 8, 9]
    ]


def test_failed_smoke_never_records_the_failed_release(tmp_path: Path) -> None:
    result = _host(tmp_path, smoke_ok=False)
    assert result.returncode != 0
    assert "compose up" in (tmp_path / "calls").read_text()
    assert "smoke.sh" in (tmp_path / "calls").read_text()
    assert retention.history(tmp_path / "host/.deploy-state/successful-releases.json") == [
        f"{n:040x}" for n in [2, 1, 8, 9]
    ]


def test_standalone_preflight_does_not_delete_by_default(tmp_path: Path) -> None:
    result = _host(tmp_path, dry=True)
    assert result.returncode == 0, result.stderr
    assert "would remove" in result.stdout
    assert "image rm" not in (tmp_path / "calls").read_text()


def test_simultaneous_deploy_is_refused_before_inventory_or_download(tmp_path: Path) -> None:
    result = _host(tmp_path, lock_ok=False)
    assert result.returncode != 0
    assert "another deployment" in result.stdout
    assert not (tmp_path / "calls").exists()


def test_unseeded_rollback_history_keeps_all_images(tmp_path: Path) -> None:
    result = _host(tmp_path, dry=True, warmup=True)
    assert result.returncode == 0, result.stderr
    assert "history warming up" in result.stdout
    assert "would remove" not in result.stdout
    assert "image rm" not in (tmp_path / "calls").read_text()


def test_multiple_aia_aliases_are_shared_and_never_removed() -> None:
    shared = image(1)
    shared["RepoTags"].append(f"{REGISTRY}/aia-api:{2:040x}")
    assert retention.candidates([shared], set(), REGISTRY, [], NOW) == []


@pytest.mark.parametrize(
    "enabled,running,expected",
    [(True, False, ["docs.sh up"]), (False, True, ["docs.sh down"]), (False, False, [])],
)
def test_the_report_editor_follows_its_switch_on_every_deploy(
    tmp_path: Path, enabled: bool, running: bool, expected: list[str]
) -> None:
    # Switched off while it runs, the deploy stops it: turning it off needs no hand on the host
    # (report-editor-hosting 4a). Nothing runs and it is off: the deploy does not touch it.
    result = _host(tmp_path, onlyoffice_enabled=enabled, docs_running=running)
    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert [c.strip() for c in calls if c.startswith("docs.sh")] == expected
