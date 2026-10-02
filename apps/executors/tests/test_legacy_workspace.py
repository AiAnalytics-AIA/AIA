"""``python -m aia_executors.legacy_workspace``: the operator's 18.6.6 migration command.

The command is a thin shell over ``aia_core.application.workspace_migration``, whose
own tests pin what a migration does. These pin what the operator sees: a dry run
unless ``--apply``, the JSON report where it was asked for, a summary on standard
error, and an exit code that says whether anything is left waiting.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.workspace import ContentState
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import StudyWorkspaceRow
from aia_executors import legacy_workspace

PRJ = "PRJ-00c0ffee00c0ff"


def _unit_store() -> Any:
    """The core tests' writer of an 18.6.6 store, loaded by path."""
    name = "aia_test_unit_store"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parents[3] / "packages/aia_core/tests/unit_store.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Engine:
    def dispose(self) -> None:
        pass


@pytest.fixture
def copy(tmp_path: Path, world: Any) -> Any:
    """A copy of a unit store with one project, bound to the world's Study before ADR 0018."""
    helper = _unit_store()
    unit = helper.UnitStore(tmp_path / "unit")
    record = unit.attach("zadani.txt", b"fiktivni zadani", project_id=PRJ)
    unit.save(PRJ, helper.brief("Ranni napoj", "Zjistit zajem", [record]))
    unit.close()
    with world.sessions() as session:
        session.add(
            StudyWorkspaceRow(
                study_id=world.study_id,
                organization_id=world.organization_id,
                client_id=world.client_id,
                content_state=ContentState.AWAITING_MIGRATION.value,
                unit_project_id=PRJ,
                lineage={},
                bound_by=world.lead_id,
            )
        )
        session.commit()
    return unit


@pytest.fixture
def run(
    monkeypatch: pytest.MonkeyPatch, world: Any, store: InMemoryArtifactStore, copy: Any
) -> Any:
    monkeypatch.setattr(legacy_workspace, "engine_from_env", lambda: (_Engine(), world.sessions))
    monkeypatch.setattr(legacy_workspace, "build_artifact_store", lambda _settings: store)
    monkeypatch.setattr(legacy_workspace.StorageSettings, "from_env", staticmethod(lambda: None))

    def main(*extra: str, actor: str = "lead@art-chain.io") -> int:
        return legacy_workspace.main(
            [
                "--store",
                str(copy.database),
                "--attachments",
                str(copy.uploads),
                "--as",
                actor,
                *extra,
            ]
        )

    return main


def _state(world: Any) -> str:
    with world.sessions() as session:
        row = session.get(StudyWorkspaceRow, world.study_id)
        assert row is not None
        return row.content_state


def test_without_apply_it_is_a_dry_run_that_reports_what_it_would_do(
    run: Any,
    world: Any,
    store: InMemoryArtifactStore,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report_path = tmp_path / "report.json"
    assert run("--report", str(report_path)) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["applied"] is False and report["actor"] == "lead@art-chain.io"
    (study,) = report["studies"]
    assert (study["study_id"], study["outcome"], study["applied"]) == (
        world.study_id,
        "MIGRATED",
        False,
    )
    assert "dry run: nothing written" in capsys.readouterr().err
    assert _state(world) == ContentState.AWAITING_MIGRATION.value
    assert store.keys == []


def test_with_apply_it_migrates_and_prints_the_report(
    run: Any, world: Any, store: InMemoryArtifactStore, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run("--apply") == 0
    out = capsys.readouterr()
    report = json.loads(out.out)
    assert [(s["outcome"], s["applied"], len(s["files_migrated"])) for s in report["studies"]] == [
        ("MIGRATED", True, 1)
    ]
    assert "applied" in out.err and "MIGRATED: 1" in out.err
    assert _state(world) == ContentState.MIGRATED.value
    assert len(store.keys) == 1
    # Run again: nothing waits, nothing is written, and it says so.
    assert run("--apply") == 0
    again = json.loads(capsys.readouterr().out)
    assert again["studies"] == [] and [d["study_id"] for d in again["done_before"]] == [
        world.study_id
    ]
    assert len(store.keys) == 1


def test_a_study_left_waiting_is_the_exit_code_and_the_reason(
    run: Any, world: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    # A closed Study is not editable, so it is left waiting (ADR 0019: who the operator is no
    # longer decides it, because no member lacks a grant).
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.scope import StudyStatus
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with world.sessions() as session:
        scope = ScopeResolver(session).study_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
            study_id=world.study_id,
        )
        ScopeRepository(session).set_study_status(scope, status=StudyStatus.DELIVERED)
        session.commit()
    assert run("--apply") == 3
    err = capsys.readouterr().err
    assert "NOT_MIGRATED: 1" in err and "the Study is DELIVERED: reopen it to migrate" in err
    assert _state(world) == ContentState.AWAITING_MIGRATION.value


def test_an_operator_with_no_grant_on_the_client_migrates_it_too(
    run: Any, world: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    # The organization's owner holds no grant on the client's Study, and needs none (ADR 0019).
    assert run("--apply", actor="owner@art-chain.io") == 0
    assert "NOT_MIGRATED" not in capsys.readouterr().err
    assert _state(world) != ContentState.AWAITING_MIGRATION.value


def test_it_does_not_start_without_a_person_or_a_readable_copy(
    run: Any, copy: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(actor="nobody@example.invalid") == 2
    assert "no active AIA user" in capsys.readouterr().err
    missing = tmp_path / "missing.sqlite"
    assert legacy_workspace.main(["--store", str(missing), "--as", "lead@art-chain.io"]) == 2
    assert "cannot read the copy" in capsys.readouterr().err
    # The unit still has its database open: that is not a copy.
    cx = _unit_store().UnitStore(copy.root)
    try:
        assert run() == 2
        assert "live database" in capsys.readouterr().err
    finally:
        cx.close()
