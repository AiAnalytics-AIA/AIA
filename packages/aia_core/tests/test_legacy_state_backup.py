"""The unit's state backup includes committed edits even while they are in WAL."""

from __future__ import annotations

import importlib.util
import io
import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _backup():
    spec = importlib.util.spec_from_file_location(
        "legacy_state_backup", REPO / "deploy/reference/bin/backup-legacy-state.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write_backup


def test_backup_captures_wal_edits_and_other_state_databases(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    project = sqlite3.connect(data / "project_store.sqlite")
    project.execute("PRAGMA journal_mode=WAL")
    project.execute("PRAGMA wal_autocheckpoint=0")
    project.execute("CREATE TABLE projects (id TEXT, title TEXT)")
    project.execute("INSERT INTO projects VALUES ('PRJ-kept', 'Saved design')")
    project.commit()
    assert (data / "project_store.sqlite-wal").stat().st_size > 0
    with sqlite3.connect(data / "research_os.sqlite") as other:
        other.execute("CREATE TABLE jobs (id TEXT)")
    output = io.BytesIO()
    try:
        assert _backup()(data, output) == ["project_store.sqlite", "research_os.sqlite"]
        with zipfile.ZipFile(io.BytesIO(output.getvalue())) as bundle:
            assert sorted(bundle.namelist()) == ["project_store.sqlite", "research_os.sqlite"]
            restore = tmp_path / "restored.sqlite"
            restore.write_bytes(bundle.read("project_store.sqlite"))
        with sqlite3.connect(restore) as connection:
            assert connection.execute("SELECT * FROM projects").fetchall() == [
                ("PRJ-kept", "Saved design")
            ]
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        project.close()


def test_missing_project_store_fails_instead_of_producing_an_empty_backup(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="working project database is missing"):
        _backup()(tmp_path, io.BytesIO())


def _stubs(tmp_path: Path, docker_body: str) -> tuple[dict[str, str], Path]:
    """docker and aws stubs on PATH, an env file, and the log aws writes its calls to."""
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "docker").write_text(
        "#!/bin/bash\n" + 'printf "%s\\n" "$*" >> "$DOCKER_LOG"\n' + docker_body
    )
    (commands / "aws").write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'if [[ "$1" == s3 ]]; then cat > /dev/null; else echo 2048; fi\n'
    )
    for tool in ("docker", "aws"):
        (commands / tool).chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIA_IMAGE_REGISTRY=example.invalid\nAWS_REGION=eu-central-1\n"
        "AIA_PUBLIC_HOSTNAME=example.invalid\nAIA_OPS_BUCKET=test-bucket\n"
    )
    env = {
        **os.environ,
        "PATH": f"{commands}:{os.environ['PATH']}",
        "DEPLOY_DIR": str(tmp_path),
        "ENV_FILE": str(env_file),
        "CALL_LOG": str(tmp_path / "calls"),
        "DOCKER_LOG": str(tmp_path / "docker-calls"),
    }
    env.pop("AIA_LEGACY_STATE_BACKUP_ENABLED", None)
    return env, tmp_path


@pytest.mark.parametrize("enabled", [None, "false", "true"])
def test_the_product_backup_never_exports_the_units_state(
    tmp_path: Path, enabled: str | None
) -> None:
    """The unit is not the product's (ADR 0018): its databases are the reference's to copy."""
    env, root = _stubs(
        tmp_path,
        'if [[ "$*" == *"ps --status running --services"* ]]; then echo postgres; '
        'elif [[ "$*" == *"exec -T postgres"* ]]; then echo postgres-dump; '
        'elif [[ "$*" == *legacy-panel* ]]; then exit 93; fi\n',
    )
    if enabled is not None:
        env["AIA_LEGACY_STATE_BACKUP_ENABLED"] = enabled
    subprocess.run(
        ["bash", str(REPO / "deploy/develop/bin/backup.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert ".dump" in (root / "calls").read_text()
    assert "legacy-state" not in (root / "calls").read_text()
    assert "legacy-panel" not in (root / "docker-calls").read_text()


REFERENCE_BACKUP = REPO / "deploy/reference/bin/backup-state.sh"
# docker for the reference stack: the volume exists; `ps` says whether the unit runs.
REFERENCE_DOCKER = (
    'if [[ "$1 $2" == "volume inspect" ]]; then exit 0; '
    'elif [[ "$*" == *"ps --status running -q legacy-panel"* ]]; then '
    '[ -n "$UNIT_RUNNING" ] && echo abc123; '
    'elif [[ "$*" == *"exec -T legacy-panel"* || "$1" == run ]]; then '
    "cat > /dev/null; echo PK-zip; "
    # `docker login --password-stdin` reads the token, as the real one does.
    'elif [[ "$1" == login ]]; then cat > /dev/null; '
    "fi; exit 0\n"
)


@pytest.mark.parametrize("enabled", [None, "false"])
def test_the_reference_backup_needs_the_data_owners_approval(
    tmp_path: Path, enabled: str | None
) -> None:
    env, root = _stubs(tmp_path, REFERENCE_DOCKER)
    if enabled is not None:
        env["AIA_LEGACY_STATE_BACKUP_ENABLED"] = enabled
    result = subprocess.run(
        ["bash", str(REFERENCE_BACKUP), "abc1234"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "needs the data owner's approval" in result.stderr
    assert not (root / "calls").exists(), "nothing was sent to the bucket"


@pytest.mark.parametrize("running", [True, False])
def test_the_reference_backup_copies_inside_the_units_own_image(
    tmp_path: Path, running: bool
) -> None:
    """In the running unit; otherwise in a one-off of its image, no network, no entrypoint."""
    env, root = _stubs(tmp_path, REFERENCE_DOCKER)
    env["AIA_LEGACY_STATE_BACKUP_ENABLED"] = "true"
    env["UNIT_RUNNING"] = "1" if running else ""
    result = subprocess.run(
        ["bash", str(REFERENCE_BACKUP), "abc1234", "pre-migration"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    docker = (root / "docker-calls").read_text()
    if running:
        assert "exec -T legacy-panel python3 -" in docker
        assert "\nrun " not in "\n" + docker
    else:
        one_off = [line for line in docker.splitlines() if line.startswith("run ")]
        assert one_off == [
            "run --rm -i --network none --entrypoint python3 "
            "-v aia-develop_legacy_state:/app example.invalid/aia-legacy-panel:abc1234 -"
        ]
    uploads = (root / "calls").read_text()
    assert "s3://test-bucket/backups/legacy-state-" in uploads and "-pre-migration.zip" in uploads
    # Read, copied, uploaded: never a removal of the volume or of a container.
    assert not any(w in docker for w in ("volume rm", "volume prune", "\nrm ", " down"))
