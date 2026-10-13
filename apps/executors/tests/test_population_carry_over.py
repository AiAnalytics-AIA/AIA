"""18.6.6's v17 population reaches the develop worker as the contract pins it (P6).

``deploy/develop/population/v17.files`` lists the files ``bin/sync-population.sh``
puts where the worker reads them. These tests hold the list to the three things it
must agree with -- the Czech import contract, the unit's data manifest and the
frozen unit's own files -- check that Compose and the deploy bundle carry what the
command needs, and run the sync script itself with ``aws`` replaced by a stub: every
file verified before anything is replaced, a mismatch leaving the previous files as
they were.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17

REPO = Path(__file__).resolve().parents[3]
DEVELOP = REPO / "deploy" / "develop"
FILES = DEVELOP / "population" / "v17.files"
SYNC = DEVELOP / "bin" / "sync-population.sh"
UNIT_APP = REPO / "legacy" / "npc-panel-18.6.6" / "app"
DATA_MANIFEST = REPO / "legacy" / "npc-panel-18.6.6" / "data-manifest.json"


def _entries(text: str) -> list[tuple[str, int, str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sha, size, origin, path = line.split()
        rows.append((sha, int(size), origin, path))
    return rows


LISTED = _entries(FILES.read_text(encoding="utf-8"))
BY_NAME = {path.rsplit("/", 1)[-1]: (sha, size, origin, path) for sha, size, origin, path in LISTED}


def _panel_name(label: str) -> str:
    return f"FINALNI_KOMPLETNI_PANEL_{label}.csv.gz"


# ------------------------------------------------------------- the list itself


def test_the_list_is_exactly_the_contracts_versions_dictionary_and_companions() -> None:
    contract = CZ_SYNTHETIC_V17
    expected = {_panel_name(v.label): (v.sha256, v.byte_size) for v in contract.known_versions}
    expected |= {c.asset_id: (c.sha256, c.byte_size) for c in contract.companions}
    dictionary = BY_NAME["FIELD_DICTIONARY_v17_1.csv"]
    assert dictionary[0] == contract.dictionary_sha256
    listed = {name: (sha, size) for name, (sha, size, _, _) in BY_NAME.items()}
    del listed["FIELD_DICTIONARY_v17_1.csv"]
    assert listed == expected
    assert len(BY_NAME) == len(LISTED), "two entries share a base name"


def test_every_bucket_file_is_in_the_units_data_bundle_with_the_same_bytes() -> None:
    manifest = {f["path"]: f for f in json.loads(DATA_MANIFEST.read_text("utf-8"))["files"]}
    bucket = [(sha, size, path) for sha, size, origin, path in LISTED if origin == "bucket"]
    assert bucket
    for sha, size, path in bucket:
        assert path in manifest, path
        assert (manifest[path]["sha256"], manifest[path]["bytes"]) == (sha, size), path


def test_every_unit_file_is_the_frozen_units_own_bytes() -> None:
    unit = [(sha, size, path) for sha, size, origin, path in LISTED if origin == "unit"]
    assert {path for _, _, path in unit} == {
        "CORE_JOINT_STATUS.json",
        "PERSONA_VALUE_LABELS_v17.json",
        "BUILTIN_SUBPANELS_v17.json",
        "SPECIAL_PANEL_REGISTRY_v17.json",
    }
    for sha, size, path in unit:
        data = (UNIT_APP / path).read_bytes()
        assert (hashlib.sha256(data).hexdigest(), len(data)) == (sha, size), path


def test_only_bucket_and_unit_origins_are_listed() -> None:
    assert {origin for _, _, origin, _ in LISTED} == {"bucket", "unit"}


# ---------------------------------------------------- Compose and the bundle


def _service(name: str) -> str:
    compose = (DEVELOP / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(
        rf"^  {name}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|^[a-z]|\Z)", compose, re.M | re.S
    )
    assert match, name
    return match.group(1)


def test_the_worker_alone_gets_the_operators_and_the_api_only_the_read_only_population() -> None:
    """The API reads the population for the audience preview (panel-grounded-respondents 6c,
    the owner's choice): read-only, and never the operators -- nobody operates it from there."""
    worker = _service("worker")
    assert "AIA_POPULATION_OPERATORS: ${AIA_POPULATION_OPERATORS:-}" in worker
    assert "AIA_POPULATION_ASSET_ROOT: /srv/population/v17" in worker
    assert "- ${AIA_POPULATION_DIR:-/opt/aia/population}:/srv/population:ro" in worker
    api = _service("api")
    assert "AIA_POPULATION_OPERATORS" not in api
    assert "AIA_POPULATION_ASSET_ROOT: ${AIA_API_POPULATION_ASSET_ROOT-/srv/population/v17}" in api
    assert "- ${AIA_POPULATION_DIR:-/opt/aia/population}:/srv/population:ro" in api
    for other in ("web", "caddy", "postgres"):
        assert "AIA_POPULATION" not in _service(other), other


def test_the_deploy_bundle_carries_the_list_and_the_units_files_it_names() -> None:
    workflow = (REPO / ".github" / "workflows" / "deploy-develop.yml").read_text("utf-8")
    assert "deploy/develop/population" in workflow
    assert "legacy/npc-panel-18.6.6/app/$name" in workflow
    assert re.search(r"tar -czf deploy-bundle\.tar\.gz -C \"\$stage\" .*\bpopulation\b", workflow)


# ------------------------------------------------------------- the sync script


@pytest.fixture
def host(tmp_path: Path) -> dict[str, Path]:
    for tool in ("bash", "sha256sum", "mktemp"):
        if shutil.which(tool) is None:
            pytest.skip(f"{tool} is not installed")
    deploy = tmp_path / "deploy"
    (deploy / "population").mkdir(parents=True)
    (deploy / ".env").write_text(
        "AIA_IMAGE_REGISTRY=registry.example.test\nAWS_REGION=eu-central-1\n"
        "AIA_PUBLIC_HOSTNAME=aia.example.test\nAIA_OPS_BUCKET=ops\n"
        "AIA_POPULATION_SOURCE_PREFIX=legacy-data/abc\n",
        encoding="utf-8",
    )
    bucket = tmp_path / "bucket" / "ops" / "legacy-data" / "abc"
    (bucket / "audit_reference").mkdir(parents=True)
    stub = tmp_path / "stub"
    stub.mkdir()
    # `aws s3 cp s3://<bucket>/<key> <dest> ...`, from a directory standing in for S3.
    (stub / "aws").write_text(
        '#!/bin/bash\n[ "$1 $2" = "s3 cp" ] || exit 9\n'
        f'echo "$3" >> "{tmp_path / "calls"}"\n'
        f'cp "{tmp_path / "bucket"}/${{3#s3://}}" "$4"\n',
        encoding="utf-8",
    )
    (stub / "aws").chmod(0o755)
    return {"root": tmp_path, "deploy": deploy, "bucket": bucket, "stub": stub}


def _fictional_bundle(host: dict[str, Path], *, wrong: str | None = None) -> None:
    """Three fictional files and a list naming them; ``wrong`` gets other bytes."""
    files = {
        "audit_reference/PANEL_BASE.csv.gz": ("bucket", b"fictional base panel\n"),
        "PANEL_LIVE.csv.gz": ("bucket", b"fictional live panel\n"),
        "NOTES.json": ("unit", b'{"fictional": true}\n'),
    }
    lines = ["# fictional"]
    for path, (origin, data) in files.items():
        lines.append(f"{hashlib.sha256(data).hexdigest()} {len(data)} {origin} {path}")
        stored = data if path != wrong else data.upper()
        target = (
            host["bucket"] / path if origin == "bucket" else host["deploy"] / "population" / path
        )
        target.write_bytes(stored)
    (host["deploy"] / "population" / "v17.files").write_text("\n".join(lines) + "\n", "utf-8")


def _sync(host: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{host['stub']}:{os.environ.get('PATH', '/usr/bin:/bin')}",
        "DEPLOY_DIR": str(host["deploy"]),
        "AIA_POPULATION_DIR": str(host["root"] / "population"),
    }
    return subprocess.run(["bash", str(SYNC)], env=env, capture_output=True, text=True, check=False)


def test_every_file_is_verified_and_lands_read_only_under_its_base_name(
    host: dict[str, Path],
) -> None:
    _fictional_bundle(host)
    result = _sync(host)
    assert result.returncode == 0, result.stderr
    target = host["root"] / "population" / "v17"
    assert sorted(p.name for p in target.iterdir()) == [
        "NOTES.json",
        "PANEL_BASE.csv.gz",
        "PANEL_LIVE.csv.gz",
    ]
    assert {oct(p.stat().st_mode & 0o777) for p in target.iterdir()} == {"0o444"}
    assert oct(target.stat().st_mode & 0o777) == "0o555"
    calls = (host["root"] / "calls").read_text("utf-8").split()
    assert calls == [
        "s3://ops/legacy-data/abc/audit_reference/PANEL_BASE.csv.gz",
        "s3://ops/legacy-data/abc/PANEL_LIVE.csv.gz",
    ]
    assert [p.name for p in (host["root"] / "population").iterdir()] == ["v17"]


def test_a_file_with_other_bytes_replaces_nothing(host: dict[str, Path]) -> None:
    _fictional_bundle(host)
    assert _sync(host).returncode == 0
    before = {p.name: p.read_bytes() for p in (host["root"] / "population" / "v17").iterdir()}
    _fictional_bundle(host, wrong="PANEL_LIVE.csv.gz")
    result = _sync(host)
    assert result.returncode != 0
    assert "PANEL_LIVE.csv.gz does not have the listed SHA256" in result.stderr
    after = {p.name: p.read_bytes() for p in (host["root"] / "population" / "v17").iterdir()}
    assert after == before
    assert [p.name for p in (host["root"] / "population").iterdir()] == ["v17"]


def test_a_missing_object_or_prefix_stops_before_anything_lands(host: dict[str, Path]) -> None:
    _fictional_bundle(host)
    (host["bucket"] / "PANEL_LIVE.csv.gz").unlink()
    result = _sync(host)
    assert result.returncode != 0 and "could not fetch PANEL_LIVE.csv.gz" in result.stderr
    assert not (host["root"] / "population" / "v17").exists()

    env_file = host["deploy"] / ".env"
    env_file.write_text(env_file.read_text("utf-8").replace("AIA_POPULATION_SOURCE_PREFIX", "X"))
    result = _sync(host)
    assert result.returncode != 0 and "AIA_POPULATION_SOURCE_PREFIX" in result.stderr


def test_a_second_run_lands_the_same_bytes_again(host: dict[str, Path]) -> None:
    _fictional_bundle(host)
    assert _sync(host).returncode == 0
    first = {p.name: p.read_bytes() for p in (host["root"] / "population" / "v17").iterdir()}
    result = _sync(host)
    assert result.returncode == 0, result.stderr
    second = {p.name: p.read_bytes() for p in (host["root"] / "population" / "v17").iterdir()}
    assert first == second
    assert [p.name for p in (host["root"] / "population").iterdir()] == ["v17"]


@pytest.mark.parametrize(
    "line",
    [
        "{sha} 3 bucket ../escape.csv",
        "{sha} 3 bucket /abs.csv",
        "{sha} 3 elsewhere PANEL.csv",
        "{sha} 3 unit sub/NOTES.json",
        "not-a-sha 3 bucket PANEL.csv",
    ],
)
def test_a_line_that_does_not_read_stops_the_sync(host: dict[str, Path], line: str) -> None:
    sha = hashlib.sha256(b"abc").hexdigest()
    (host["deploy"] / "population" / "v17.files").write_text(line.format(sha=sha) + "\n", "utf-8")
    result = _sync(host)
    assert result.returncode != 0
    assert not (host["root"] / "population" / "v17").exists()


def test_the_deploy_keeps_each_versions_dictionary_without_failing_on_a_refusal() -> None:
    deploy = (DEVELOP / "bin" / "deploy.sh").read_text(encoding="utf-8")
    step = deploy.index('"$DEPLOY_DIR/bin/population.sh" record-dictionary')
    assert deploy.index('log "replacing services"') < step < deploy.index('log "smoke tests"')
    assert 'if ! "$DEPLOY_DIR/bin/population.sh" record-dictionary; then' in deploy


def test_the_deploy_keeps_each_populations_catalogue_after_its_dictionary() -> None:
    deploy = (DEVELOP / "bin" / "deploy.sh").read_text(encoding="utf-8")
    dictionary = deploy.index('"$DEPLOY_DIR/bin/population.sh" record-dictionary')
    step = deploy.index('"$DEPLOY_DIR/bin/population.sh" record-catalogue')
    assert dictionary < step < deploy.index('log "smoke tests"')
    assert (
        'timeout --kill-after=30 300 "$DEPLOY_DIR/bin/population.sh" record-catalogue'
        " || catalogue_status=$?"
    ) in deploy
    assert "124|137)" in deploy[step:]
