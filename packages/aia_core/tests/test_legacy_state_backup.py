"""The pre-deploy backup includes committed edits even while they are in WAL."""

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
        "legacy_state_backup", REPO / "deploy/develop/bin/backup-legacy-state.py"
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


@pytest.mark.parametrize("enabled", [None, "false"])
def test_working_database_export_requires_explicit_enablement(
    tmp_path: Path, enabled: str | None
) -> None:
    """Exercise the real host script without AWS or a running container."""
    commands = tmp_path / "commands"
    commands.mkdir()
    docker = commands / "docker"
    docker.write_text(
        "#!/bin/bash\n"
        'if [[ "$*" == *"exec -T legacy-panel"* ]]; then exit 93; fi\n'
        'if [[ "$*" == *"ps --status running --services"* ]]; then echo postgres; '
        'elif [[ "$*" == *"exec -T postgres"* ]]; then echo postgres-dump; '
        'elif [[ "$*" == *"ps --status running -q legacy-panel"* ]]; then echo running; fi\n'
    )
    aws = commands / "aws"
    aws.write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'if [[ "$1" == s3 ]]; then cat > /dev/null; else echo 2048; fi\n'
    )
    docker.chmod(0o755)
    aws.chmod(0o755)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AIA_IMAGE_REGISTRY=example.invalid\nAWS_REGION=eu-central-1\n"
        "AIA_PUBLIC_HOSTNAME=example.invalid\nAIA_OPS_BUCKET=test-bucket\n"
    )
    log = tmp_path / "calls"
    env = {
        **os.environ,
        "PATH": f"{commands}:{os.environ['PATH']}",
        "DEPLOY_DIR": str(tmp_path),
        "CALL_LOG": str(log),
    }
    env.pop("AIA_LEGACY_STATE_BACKUP_ENABLED", None)
    if enabled is not None:
        env["AIA_LEGACY_STATE_BACKUP_ENABLED"] = enabled
    result = subprocess.run(
        ["bash", str(REPO / "deploy/develop/bin/backup.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "working database export is disabled" in result.stdout
    assert ".dump" in log.read_text()
    assert "legacy-state" not in log.read_text()
