"""Runtime seeds initialise state once; restarts must retain edited projects."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _hydrator():
    spec = importlib.util.spec_from_file_location(
        "state_hydrator", REPO / "legacy/npc-panel-18.6.6/runtime/hydrate_data.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restart_preserves_saved_project_and_still_verifies_assets(tmp_path: Path) -> None:
    source, tree = tmp_path / "source", tmp_path / "tree"
    (source / "data").mkdir(parents=True)
    db = source / "data/project_store.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, title TEXT)")
    asset = source / "asset.txt"
    asset.write_text("verified asset")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {
                        "path": "data/project_store.sqlite",
                        "class": "state_seed",
                        "sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
                    },
                    {
                        "path": "asset.txt",
                        "class": "data_asset",
                        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    },
                ]
            }
        )
    )
    args = [str(tree), "--source", str(source), "--manifest", str(manifest)]
    hydrate = _hydrator().main
    assert hydrate(args) == 0
    working = tree / "data/project_store.sqlite"
    with sqlite3.connect(working) as connection:
        connection.execute("INSERT INTO projects VALUES ('PRJ-saved', 'Saved study')")
    assert hydrate(args) == 0
    with sqlite3.connect(working) as connection:
        assert connection.execute("SELECT * FROM projects").fetchall() == [
            ("PRJ-saved", "Saved study")
        ]
    # Assets remain strict, even while mutable state differs from its seed hash.
    (tree / "asset.txt").write_text("changed")
    asset.write_text("untrusted source")
    assert hydrate(args) == 1
    assert (tree / "asset.txt").read_text() == "changed"


def test_first_state_seed_with_wrong_digest_is_not_installed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.sqlite").write_bytes(b"wrong seed")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [
                    {"path": "state.sqlite", "class": "state_seed", "sha256": "0" * 64},
                ]
            }
        )
    )
    tree = tmp_path / "tree"
    assert _hydrator().main([str(tree), "--source", str(source), "--manifest", str(manifest)]) == 1
    assert not (tree / "state.sqlite").exists()
